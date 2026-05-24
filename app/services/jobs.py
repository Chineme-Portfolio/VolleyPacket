"""
Job management — DB-backed with in-memory cache for running jobs.

Source of truth: PostgreSQL/SQLite (JobRow table)
Files (spreadsheets, PDFs, zips): S3 or local filesystem via storage layer
In-memory cache: only for jobs with active background tasks (real-time progress)
"""

import os
import json
import uuid
import re
import time
import threading
import logging
from datetime import datetime

import pandas as pd

from app.models import TemplateConfig, TaskStatus, JobResponse
from app.services.storage import store
from app import config

logger = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


KNOWN_DOMAINS = ("gmail", "yahoo", "yahoomail", "outlook", "hotmail", "aol", "icloud")
KNOWN_TLDS = (".com", ".org", ".net", ".co", ".edu", ".gov", ".io")


def clean_email(raw: str) -> str:
    e = raw.strip()
    if not e or e.lower() in ("nan", "nil", "none", ""):
        return e

    # # -> @
    e = e.replace("#", "@")

    # Q/q used as @ before a known domain
    for dom in KNOWN_DOMAINS:
        pattern = re.compile(rf"[Qq]({re.escape(dom)})", re.IGNORECASE)
        if pattern.search(e) and "@" not in e:
            e = pattern.sub(rf"@\1", e, count=1)
            break

    # spaces around @
    e = re.sub(r"\s*@\s*", "@", e)

    # missing @ before known domain (e.g. "templeanaele54gmail.com")
    if "@" not in e:
        for dom in KNOWN_DOMAINS:
            idx = e.lower().find(dom)
            if idx > 0:
                e = e[:idx] + "@" + e[idx:]
                break

    if "@" not in e:
        return e

    local, domain = e.split("@", 1)

    # remove spaces in local part ("Jared Christian2018" -> "jaredchristian2018")
    if " " in local:
        local = local.replace(" ", "").lower()

    # strip duplicate @domain ("@gmail.com@gmail.com")
    if "@" in domain:
        domain = domain.split("@")[-1]

    # commas -> dots in domain
    domain = domain.replace(",", ".")

    # spaces in domain ("gmail. com" or "outlook com")
    domain = domain.replace(" ", "")

    # missing dot before tld ("gmailcom" -> "gmail.com")
    domain_lower = domain.lower()
    for tld in KNOWN_TLDS:
        bare = tld.lstrip(".")
        if domain_lower.endswith(bare) and not domain_lower.endswith(tld):
            domain = domain[:-(len(bare))] + "." + domain[-(len(bare)):]
            break

    # missing tld ("@gmail" -> "@gmail.com")
    if "." not in domain:
        for dom in KNOWN_DOMAINS:
            if domain.lower() == dom:
                domain = f"{domain}.com"
                break

    # trailing dot or @
    domain = domain.rstrip(".@")

    e = f"{local}@{domain}"
    return e


class Job:
    def __init__(self, job_id: str, candidate_file: str, data: pd.DataFrame, owner_id: str = ""):
        self.job_id = job_id
        self.owner_id = owner_id
        self.status = "created"
        self.created_at = datetime.now()
        self.timestamp = self.created_at.strftime("%Y%m%d_%H%M%S")

        # Data
        self.candidate_file = candidate_file
        self.data = data
        self.columns = list(data.columns)
        # Filtered data
        self.valid_data = None
        self.invalid_data = None

        # Template
        self.template_id = None
        self.template = None

        # PDF output
        self.pdf_folder = None

        # Task tracking
        self.tasks = {
            "pdfs": TaskStatus(),
            "emails": TaskStatus(),
            "sms": TaskStatus(),
            "photos": TaskStatus(),
        }

        # Control flags
        self.cancelled = False
        self.column_mapping_confirmed = False
        self.paused = {
            "pdfs": False,
            "emails": False,
            "sms": False,
            "photos": False,
        }
        self.stop_flags = {
            "pdfs": False,
            "emails": False,
            "sms": False,
            "photos": False,
        }
        self._lock = threading.Lock()
        self._last_flag_check = 0.0

        # Job mode: "dynamic_pdf", "static_attachment", "email_only"
        self.job_mode = "dynamic_pdf"
        self.static_attachment_path = None

        # Email content (customizable per job)
        self.email_subject = ""
        self.email_body = ""  # HTML with {Name}, {Email}, {ExamNo} placeholders

        # SMS content (customizable per job)
        self.sms_body = ""  # Plain text with {Name}, {ExamNo} placeholders

        # Logs
        self.log_path = None

    def to_response(self) -> JobResponse:
        return JobResponse(
            job_id=self.job_id,
            status=self.status,
            candidate_file=self.candidate_file,
            candidate_count=len(self.data),
            columns=self.columns,
            template_id=self.template_id,
            job_mode=self.job_mode,
            email_subject=self.email_subject,
            email_body=self.email_body,
            sms_body=self.sms_body,
            tasks=self.tasks,
        )

    # --- Database persistence ---

    def save(self, include_data=False):
        """Persist job metadata to database and optionally save data files."""
        from app.database import get_session, JobRow

        session = get_session()
        try:
            row = session.get(JobRow, self.job_id)
            if not row:
                row = JobRow(id=self.job_id)
                session.add(row)

            # Check for externally-set stop flags before saving tasks
            # (prevents background thread from overwriting a cancel signal)
            if row.stop_flags_json:
                try:
                    db_flags = json.loads(row.stop_flags_json)
                    for task_name, stopped in db_flags.items():
                        if stopped and task_name in self.tasks:
                            if self.tasks[task_name].status == "running":
                                self.tasks[task_name].status = "cancelled"
                                self.tasks[task_name].phase = "cancelled"
                            self.stop_flags[task_name] = True
                except (json.JSONDecodeError, TypeError):
                    pass

            row.owner_id = self.owner_id
            row.status = self.status
            row.created_at = self.created_at
            row.timestamp = self.timestamp
            row.candidate_file = self.candidate_file
            row.candidate_count = len(self.data)
            row.columns_json = json.dumps(self.columns)
            row.template_id = self.template_id
            row.job_mode = self.job_mode
            row.email_subject = self.email_subject
            row.email_body = self.email_body
            row.sms_body = self.sms_body
            row.cancelled = self.cancelled
            row.column_mapping_confirmed = self.column_mapping_confirmed
            row.paused_json = json.dumps(self.paused)
            row.tasks_json = json.dumps({k: v.model_dump() for k, v in self.tasks.items()})

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save job {self.job_id} to DB: {e}")
            raise
        finally:
            session.close()

        # Save data files to storage (S3 or local)
        if include_data:
            self._save_data_files()

    def _save_data_files(self):
        """Save DataFrame files to storage."""
        folder = os.path.join(config.JOBS_FOLDER, self.job_id)
        os.makedirs(folder, exist_ok=True)

        data_path = os.path.join(folder, "data.xlsx")
        self.data.to_excel(data_path, index=False)
        store.save_local_file(data_path)

        if self.valid_data is not None:
            valid_path = os.path.join(folder, "valid_data.xlsx")
            self.valid_data.to_excel(valid_path, index=False)
            store.save_local_file(valid_path)

        if self.invalid_data is not None:
            invalid_path = os.path.join(folder, "invalid_data.xlsx")
            self.invalid_data.to_excel(invalid_path, index=False)
            store.save_local_file(invalid_path)

    @classmethod
    def from_db_row(cls, row) -> "Job":
        """Reconstruct a Job from a JobRow database record."""
        from app.services.storage import _key_from_local

        job = cls.__new__(cls)
        job.job_id = row.id
        job.owner_id = row.owner_id
        job.status = row.status
        job.created_at = row.created_at
        job.timestamp = row.timestamp
        job.candidate_file = row.candidate_file
        job.columns = json.loads(row.columns_json)
        job.template_id = row.template_id
        job.job_mode = row.job_mode
        job.email_subject = row.email_subject
        job.email_body = row.email_body
        job.sms_body = row.sms_body or ""
        job.cancelled = row.cancelled
        job.column_mapping_confirmed = getattr(row, 'column_mapping_confirmed', False) or False
        job.paused = json.loads(row.paused_json)
        job.stop_flags = json.loads(getattr(row, 'stop_flags_json', None) or '{"pdfs":false,"emails":false,"sms":false,"photos":false}')
        job._lock = threading.Lock()
        job._last_flag_check = 0.0

        # Restore task statuses
        tasks_data = json.loads(row.tasks_json) if row.tasks_json else {}
        job.tasks = {}
        for key in ("pdfs", "emails", "sms", "photos"):
            if key in tasks_data:
                job.tasks[key] = TaskStatus(**tasks_data[key])
            else:
                job.tasks[key] = TaskStatus()

        # Mark any "running" tasks as interrupted (server restarted)
        for task in job.tasks.values():
            if task.status == "running":
                task.status = "interrupted"
                task.phase = "interrupted"

        # Load DataFrame from storage
        folder = os.path.join(config.JOBS_FOLDER, job.job_id)
        data_key = _key_from_local(os.path.join(folder, "data.xlsx"))
        try:
            local_path = store.ensure_local(data_key)
            job.data = pd.read_excel(local_path).fillna("")
        except Exception as e:
            logger.warning(f"Could not load data file for job {job.job_id}: {e}")
            job.data = pd.DataFrame(columns=job.columns)

        # Load valid/invalid data if they exist
        valid_key = _key_from_local(os.path.join(folder, "valid_data.xlsx"))
        try:
            valid_path = store.ensure_local(valid_key)
            job.valid_data = pd.read_excel(valid_path).fillna("")
        except Exception:
            job.valid_data = None

        invalid_key = _key_from_local(os.path.join(folder, "invalid_data.xlsx"))
        try:
            invalid_path = store.ensure_local(invalid_key)
            job.invalid_data = pd.read_excel(invalid_path).fillna("")
        except Exception:
            job.invalid_data = None

        # Load template
        job.template = None
        job.pdf_folder = None
        job.static_attachment_path = None
        job.log_path = None

        if job.template_id:
            try:
                from app.database import get_session as _get_session, TemplateRow
                s = _get_session()
                try:
                    tpl_row = s.get(TemplateRow, job.template_id)
                    if tpl_row:
                        job.template = TemplateConfig(**json.loads(tpl_row.config_json))
                finally:
                    s.close()
            except Exception:
                pass

            if not job.template:
                tpl_path = os.path.join(config.TEMPLATE_FOLDER, f"{job.template_id}.json")
                if os.path.isfile(tpl_path):
                    with open(tpl_path, "r") as f:
                        job.template = TemplateConfig(**json.load(f))

        return job

    # --- State mutations ---

    def cancel(self):
        with self._lock:
            self.cancelled = True
            self.status = "cancelled"
        self.save()

    def cancel_task(self, task_name: str):
        """Cancel a specific task (works across workers via DB flag)."""
        with self._lock:
            self.stop_flags[task_name] = True
            self.tasks[task_name].status = "cancelled"
            self.tasks[task_name].phase = "cancelled"
        # Write stop flag to a separate DB column so the background thread's
        # regular save() never overwrites it.
        from app.database import get_session, JobRow
        session = get_session()
        try:
            row = session.get(JobRow, self.job_id)
            if row:
                row.stop_flags_json = json.dumps(self.stop_flags)
                # Also update tasks_json to reflect cancellation immediately
                tasks = json.loads(row.tasks_json) if row.tasks_json else {}
                if task_name in tasks:
                    tasks[task_name]["status"] = "cancelled"
                    tasks[task_name]["phase"] = "cancelled"
                row.tasks_json = json.dumps(tasks)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save stop flag for {self.job_id}/{task_name}: {e}")
        finally:
            session.close()

    def _clear_stop_flag(self, task_name: str):
        """Clear the stop flag for a task (called before restart)."""
        from app.database import get_session, JobRow
        session = get_session()
        try:
            row = session.get(JobRow, self.job_id)
            if row:
                flags = json.loads(row.stop_flags_json) if row.stop_flags_json else {}
                flags[task_name] = False
                row.stop_flags_json = json.dumps(flags)
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def _refresh_control_flags(self):
        """Reload cancel/pause/stop flags from DB for cross-worker signal propagation."""
        from app.database import get_session, JobRow
        session = get_session()
        try:
            row = session.get(JobRow, self.job_id)
            if row:
                if row.cancelled:
                    self.cancelled = True
                self.paused.update(json.loads(row.paused_json))
                if row.stop_flags_json:
                    db_flags = json.loads(row.stop_flags_json)
                    for k, v in db_flags.items():
                        if v:
                            self.stop_flags[k] = True
        except Exception:
            pass
        finally:
            session.close()

    def pause_task(self, task_name: str):
        with self._lock:
            self.paused[task_name] = True
            if self.tasks[task_name].status == "running":
                self.tasks[task_name].phase = "paused"
        self.save()

    def resume_task(self, task_name: str):
        with self._lock:
            self.paused[task_name] = False
            if self.tasks[task_name].phase == "paused":
                self.tasks[task_name].phase = "running"
        self.save()

    def should_stop(self, task_name: str) -> bool:
        if self.cancelled or self.stop_flags.get(task_name, False):
            return True
        # Periodic DB refresh for cross-worker cancel/pause signals
        now = time.time()
        if now - self._last_flag_check > 3:
            self._last_flag_check = now
            self._refresh_control_flags()
            if self.cancelled or self.stop_flags.get(task_name, False):
                return True
        while self.paused.get(task_name, False):
            if self.cancelled or self.stop_flags.get(task_name, False):
                return True
            time.sleep(0.5)
            now = time.time()
            if now - self._last_flag_check > 3:
                self._last_flag_check = now
                self._refresh_control_flags()
        return False

    def reset_tasks(self):
        for key in self.tasks:
            self.tasks[key] = TaskStatus()
        self.paused = {k: False for k in self.paused}
        self.stop_flags = {k: False for k in self.stop_flags}
        self.cancelled = False
        self.valid_data = None
        self.invalid_data = None
        self.pdf_folder = None
        self.log_path = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save(include_data=True)

    def validate_emails(self):
        data = self.data.copy()
        data = data.fillna("")
        data["Email"] = data["Email"].astype(str).apply(clean_email)
        emails = data["Email"]
        is_valid = emails.apply(lambda e: bool(EMAIL_RE.match(e)))

        self.valid_data = data[is_valid].copy()
        self.invalid_data = data[~is_valid].copy()
        self.invalid_data["Reason"] = "Invalid email format"

        if not self.invalid_data.empty:
            os.makedirs(config.LOG_FOLDER, exist_ok=True)
            invalid_path = os.path.join(config.LOG_FOLDER, f"invalid_emails_{self.timestamp}.xlsx")
            self.invalid_data.to_excel(invalid_path, index=False)
            store.save_local_file(invalid_path)

        self.save(include_data=True)
        return len(self.valid_data), len(self.invalid_data)

    def get_pdf_folder(self) -> str:
        if not self.pdf_folder:
            self.pdf_folder = os.path.join(config.OUTPUT_FOLDER, f"pdfs_{self.job_id}")
            os.makedirs(self.pdf_folder, exist_ok=True)
        return self.pdf_folder


# --- JOB STORE (DB-backed with in-memory cache for running jobs) ---

_cache: dict[str, Job] = {}
_cache_lock = threading.Lock()


def _cache_job(job: Job):
    """Add a job to the in-memory cache."""
    with _cache_lock:
        _cache[job.job_id] = job


def _uncache_job(job_id: str):
    """Remove a job from the cache."""
    with _cache_lock:
        _cache.pop(job_id, None)


def delete_job_fully(job: Job):
    """Delete a job: DB record, cached object, and ALL associated files."""
    job_id = job.job_id

    # 1. Remove from DB
    from app.database import get_session, JobRow
    session = get_session()
    try:
        row = session.get(JobRow, job_id)
        if row:
            session.delete(row)
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete job {job_id} from DB: {e}")
        raise
    finally:
        session.close()

    # 2. Remove from cache
    _uncache_job(job_id)

    # 3. Delete job data folder (data.xlsx, valid_data.xlsx, etc.)
    job_data_key = f"data/jobs/{job_id}"
    store.delete_dir(job_data_key)

    # 4. Delete PDF folder
    pdf_key = f"output/pdfs_{job_id}"
    store.delete_dir(pdf_key)

    # 5. Delete PDF zip
    for suffix in ("", "_partial"):
        zip_key = f"output/pdfs_{job_id}{suffix}.zip"
        try:
            store.delete(zip_key)
        except Exception:
            pass

    # 6. Delete logs (run_*, sms_run_*, etc.) — use job timestamp
    timestamp = job.timestamp
    if timestamp:
        for prefix in ("run", "sms_run", "photo_download", "invalid_emails"):
            for ext in (".csv", ".xlsx"):
                log_key = f"logs/{prefix}_{timestamp}{ext}"
                try:
                    store.delete(log_key)
                except Exception:
                    pass

    # 7. Delete report
    report_key = f"logs/report_{job_id}.xlsx"
    try:
        store.delete(report_key)
    except Exception:
        pass

    logger.info(f"Job {job_id} fully deleted (DB + files)")


def create_job(candidate_file: str, data: pd.DataFrame, owner_id: str = "") -> Job:
    job_id = str(uuid.uuid4())[:8]
    job = Job(job_id=job_id, candidate_file=candidate_file, data=data, owner_id=owner_id)
    job.save(include_data=True)
    _cache_job(job)
    return job


def get_job(job_id: str) -> Job | None:
    """Get a job by ID — checks cache first, then DB."""
    # Check cache (running jobs)
    with _cache_lock:
        if job_id in _cache:
            return _cache[job_id]

    # Load from DB
    return _load_job_from_db(job_id)


def get_job_for_user(job_id: str, user_id: str) -> Job | None:
    """Get a job only if it belongs to the user."""
    job = get_job(job_id)
    if not job:
        return None
    if job.owner_id and job.owner_id != user_id:
        return None
    return job


def list_jobs() -> list[Job]:
    """List all jobs from DB (returns lightweight job objects)."""
    return _list_jobs_from_db()


def list_jobs_for_user(user_id: str) -> list[Job]:
    """List only jobs owned by the user."""
    return _list_jobs_from_db(user_id=user_id)


def _load_job_from_db(job_id: str) -> Job | None:
    """Load a single job from the database."""
    from app.database import get_session, JobRow

    session = get_session()
    try:
        row = session.get(JobRow, job_id)
        if not row:
            return None
        job = Job.from_db_row(row)
        _cache_job(job)
        # Persist interrupted status so SSE (which reads raw DB) sees it too
        if any(t.status == "interrupted" for t in job.tasks.values()):
            job.save()
        return job
    except Exception as e:
        logger.error(f"Failed to load job {job_id} from DB: {e}")
        return None
    finally:
        session.close()


def _list_jobs_from_db(user_id: str | None = None) -> list[Job]:
    """List jobs from the database. Returns Job objects with data loaded."""
    from app.database import get_session, JobRow

    session = get_session()
    try:
        query = session.query(JobRow)
        if user_id:
            query = query.filter(JobRow.owner_id == user_id)
        query = query.order_by(JobRow.created_at.desc())
        rows = query.all()

        jobs = []
        for row in rows:
            # Use cached version if available (has live task progress)
            with _cache_lock:
                if row.id in _cache:
                    jobs.append(_cache[row.id])
                    continue

            # Build a lightweight response without loading DataFrame
            try:
                job = _lightweight_job_from_row(row)
                jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to build job {row.id} from DB: {e}")

        return jobs
    except Exception as e:
        logger.error(f"Failed to list jobs from DB: {e}")
        return []
    finally:
        session.close()


def _lightweight_job_from_row(row) -> Job:
    """Build a Job object from a DB row WITHOUT loading the DataFrame.
    Suitable for list views where we only need metadata."""
    job = Job.__new__(Job)
    job.job_id = row.id
    job.owner_id = row.owner_id
    job.status = row.status
    job.created_at = row.created_at
    job.timestamp = row.timestamp
    job.candidate_file = row.candidate_file
    job.columns = json.loads(row.columns_json)
    job.template_id = row.template_id
    job.job_mode = row.job_mode
    job.email_subject = row.email_subject
    job.email_body = row.email_body
    job.sms_body = row.sms_body or ""
    job.cancelled = row.cancelled
    job.column_mapping_confirmed = getattr(row, 'column_mapping_confirmed', False) or False
    job.paused = json.loads(row.paused_json)
    job.stop_flags = json.loads(getattr(row, 'stop_flags_json', None) or '{"pdfs":false,"emails":false,"sms":false,"photos":false}')
    job._lock = threading.Lock()
    job._last_flag_check = 0.0

    # Use candidate_count from DB instead of loading DataFrame
    job.data = pd.DataFrame(columns=job.columns)
    # Override len(self.data) for to_response
    job._candidate_count = row.candidate_count

    job.valid_data = None
    job.invalid_data = None
    job.template = None
    job.pdf_folder = None
    job.static_attachment_path = None
    job.log_path = None

    # Restore task statuses
    tasks_data = json.loads(row.tasks_json) if row.tasks_json else {}
    job.tasks = {}
    for key in ("pdfs", "emails", "sms", "photos"):
        if key in tasks_data:
            job.tasks[key] = TaskStatus(**tasks_data[key])
        else:
            job.tasks[key] = TaskStatus()

    return job


# Override to_response to use _candidate_count when available
_original_to_response = Job.to_response


def _patched_to_response(self) -> JobResponse:
    count = getattr(self, "_candidate_count", None)
    if count is None:
        count = len(self.data)
    return JobResponse(
        job_id=self.job_id,
        status=self.status,
        candidate_file=self.candidate_file,
        candidate_count=count,
        columns=self.columns,
        template_id=self.template_id,
        job_mode=self.job_mode,
        email_subject=self.email_subject,
        email_body=self.email_body,
        sms_body=self.sms_body,
        tasks=self.tasks,
    )


Job.to_response = _patched_to_response
