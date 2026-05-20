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
from app.services.allocator import generate_combination_slots, allocate_combinations, assign_numbers, CAPACITY_PER_SLOT
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
        self.is_allocated = False
        self.allocated_path = None

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
        self.paused = {
            "pdfs": False,
            "emails": False,
            "sms": False,
            "photos": False,
        }
        self._lock = threading.Lock()

        # Job mode: "dynamic_pdf", "static_attachment", "email_only"
        self.job_mode = "dynamic_pdf"
        self.static_attachment_path = None

        # Email content (customizable per job)
        self.email_subject = ""
        self.email_body = ""  # HTML with {Name}, {Email}, {ExamNo} placeholders

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
            is_allocated=self.is_allocated,
            job_mode=getattr(self, "job_mode", "dynamic_pdf"),
            email_subject=getattr(self, "email_subject", ""),
            email_body=getattr(self, "email_body", ""),
            tasks=self.tasks,
        )

    # --- Persistence ---

    @property
    def _job_folder(self) -> str:
        return os.path.join(config.JOBS_FOLDER, self.job_id)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "owner_id": getattr(self, "owner_id", ""),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "timestamp": self.timestamp,
            "candidate_file": self.candidate_file,
            "columns": self.columns,
            "is_allocated": self.is_allocated,
            "allocated_path": self.allocated_path,
            "template_id": self.template_id,
            "pdf_folder": self.pdf_folder,
            "log_path": self.log_path,
            "cancelled": self.cancelled,
            "paused": self.paused,
            "tasks": {k: v.model_dump() for k, v in self.tasks.items()},
            "job_mode": getattr(self, "job_mode", "dynamic_pdf"),
            "static_attachment_path": getattr(self, "static_attachment_path", None),
            "email_subject": getattr(self, "email_subject", ""),
            "email_body": getattr(self, "email_body", ""),
        }

    def save(self, include_data=False):
        # Always save to JSON files (local dev / backup)
        folder = self._job_folder
        os.makedirs(folder, exist_ok=True)

        with open(os.path.join(folder, "job.json"), "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        if include_data:
            self.data.to_excel(os.path.join(folder, "data.xlsx"), index=False)
            if self.valid_data is not None:
                self.valid_data.to_excel(os.path.join(folder, "valid_data.xlsx"), index=False)
            if self.invalid_data is not None:
                self.invalid_data.to_excel(os.path.join(folder, "invalid_data.xlsx"), index=False)

    @classmethod
    def from_folder(cls, folder_path: str) -> "Job":
        with open(os.path.join(folder_path, "job.json"), "r") as f:
            d = json.load(f)

        data = pd.read_excel(os.path.join(folder_path, "data.xlsx"))
        data = data.fillna("")

        job = cls.__new__(cls)
        job.job_id = d["job_id"]
        job.owner_id = d.get("owner_id", "")
        job.status = d["status"]
        job.created_at = datetime.fromisoformat(d["created_at"])
        job.timestamp = d["timestamp"]
        job.candidate_file = d["candidate_file"]
        job.data = data
        job.columns = d["columns"]
        job.is_allocated = d["is_allocated"]
        job.allocated_path = d.get("allocated_path")
        job.template_id = d.get("template_id")
        job.pdf_folder = d.get("pdf_folder")
        job.log_path = d.get("log_path")
        job.cancelled = d.get("cancelled", False)
        job.paused = d.get("paused", {k: False for k in ("pdfs", "emails", "sms", "photos")})
        job._lock = threading.Lock()

        job.tasks = {k: TaskStatus(**v) for k, v in d.get("tasks", {}).items()}

        valid_path = os.path.join(folder_path, "valid_data.xlsx")
        job.valid_data = pd.read_excel(valid_path).fillna("") if os.path.isfile(valid_path) else None
        invalid_path = os.path.join(folder_path, "invalid_data.xlsx")
        job.invalid_data = pd.read_excel(invalid_path).fillna("") if os.path.isfile(invalid_path) else None

        job.job_mode = d.get("job_mode", "dynamic_pdf")
        job.static_attachment_path = d.get("static_attachment_path")
        job.email_subject = d.get("email_subject", "")
        job.email_body = d.get("email_body", "")

        job.template = None
        if job.template_id:
            tpl_path = os.path.join(config.TEMPLATE_FOLDER, f"{job.template_id}.json")
            if os.path.isfile(tpl_path):
                with open(tpl_path, "r") as f:
                    job.template = TemplateConfig(**json.load(f))

        for task in job.tasks.values():
            if task.status == "running":
                task.status = "interrupted"
                task.phase = "interrupted"

        return job

    # --- State mutations ---

    def cancel(self):
        with self._lock:
            self.cancelled = True
            self.status = "cancelled"
        self.save()

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
        if self.cancelled:
            return True
        while self.paused.get(task_name, False):
            if self.cancelled:
                return True
            time.sleep(0.5)
        return False

    def reset_tasks(self):
        for key in self.tasks:
            self.tasks[key] = TaskStatus()
        self.paused = {k: False for k in self.paused}
        self.cancelled = False
        self.valid_data = None
        self.invalid_data = None
        self.pdf_folder = None
        self.log_path = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save(include_data=True)

    def allocate(self):
        pool = generate_combination_slots() * CAPACITY_PER_SLOT
        self.data = allocate_combinations(self.data, pool)
        self.data = assign_numbers(self.data)
        self.is_allocated = True
        self.columns = list(self.data.columns)

        os.makedirs(config.DATA_FOLDER, exist_ok=True)
        self.allocated_path = os.path.join(config.DATA_FOLDER, f"allocated_{self.timestamp}.xlsx")
        self.data.to_excel(self.allocated_path, index=False)
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

        self.save(include_data=True)
        return len(self.valid_data), len(self.invalid_data)

    def get_pdf_folder(self) -> str:
        if not self.pdf_folder:
            self.pdf_folder = os.path.join(config.OUTPUT_FOLDER, f"pdfs_{self.job_id}")
            os.makedirs(self.pdf_folder, exist_ok=True)
        return self.pdf_folder


# --- JOB STORE ---
_jobs: dict[str, Job] = {}


def create_job(candidate_file: str, data: pd.DataFrame, owner_id: str = "") -> Job:
    job_id = str(uuid.uuid4())[:8]
    job = Job(job_id=job_id, candidate_file=candidate_file, data=data, owner_id=owner_id)
    _jobs[job_id] = job
    job.save(include_data=True)
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def get_job_for_user(job_id: str, user_id: str) -> Job | None:
    """Get a job only if it belongs to the user (or has no owner for legacy jobs)."""
    job = _jobs.get(job_id)
    if not job:
        return None
    owner = getattr(job, "owner_id", "")
    if owner and owner != user_id:
        return None
    return job


def list_jobs() -> list[Job]:
    return list(_jobs.values())


def list_jobs_for_user(user_id: str) -> list[Job]:
    """List only jobs owned by the user (or legacy unowned jobs)."""
    return [j for j in _jobs.values() if not getattr(j, "owner_id", "") or j.owner_id == user_id]


def load_all_jobs():
    """Load all jobs from JSON files on disk."""
    if not os.path.isdir(config.JOBS_FOLDER):
        return
    for entry in os.listdir(config.JOBS_FOLDER):
        folder = os.path.join(config.JOBS_FOLDER, entry)
        json_path = os.path.join(folder, "job.json")
        if os.path.isdir(folder) and os.path.isfile(json_path):
            try:
                job = Job.from_folder(folder)
                _jobs[job.job_id] = job
            except Exception as e:
                print(f"Warning: failed to load job {entry}: {e}")
