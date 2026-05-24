import os
import csv
import json
import uuid
import asyncio

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

import pandas as pd

import re
from app.models import AttachTemplateRequest, TemplateConfig
from app.services.jobs import create_job, get_job_for_user, get_job_light_for_user, list_jobs_for_user
from app.services.read_data import load_data
from app.services.pdf_tasks import start_pdf_generation
from app.services.email_tasks import start_email_send
from app.services.sms_tasks import start_sms_send
from app.services.photo_tasks import start_photo_download
from app.services.report_tasks import generate_report
from app.services.storage import store
from app.dependencies import get_current_user
from app.database import UserRow, EmailSettingsRow, get_session
from app.services.encryption import decrypt_credentials
from app.services.email_providers import create_provider
from app import config

router = APIRouter()

VALID_TASKS = ("pdfs", "emails", "sms", "photos")
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


async def _read_upload(file: UploadFile, max_size: int = MAX_UPLOAD_SIZE) -> bytes:
    """Read an uploaded file with size limit enforcement."""
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size // (1024*1024)} MB.",
        )
    return content


def _get_job_or_404(job_id: str, user: UserRow) -> "Job":
    """Fetch a job, ensuring it belongs to the user."""
    job = get_job_for_user(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_job_or_404_light(job_id: str, user: UserRow) -> "Job":
    """Fetch a lightweight job (no DataFrame loading).

    Use for read-only endpoints that only need metadata, task status, or timestamps.
    Do NOT use for endpoints that call job.save() — would write candidate_count=0.
    """
    job = get_job_light_for_user(job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _get_user_provider(user: UserRow):
    """Fetch and instantiate the user's configured email provider."""
    session = get_session()
    try:
        settings = session.get(EmailSettingsRow, user.id)
    finally:
        session.close()

    if not settings:
        raise HTTPException(
            status_code=400,
            detail="No email provider configured. Go to Settings > Email Provider to set one up.",
        )

    credentials = decrypt_credentials(settings.credentials_encrypted)
    provider = create_provider(settings.provider_name, credentials)
    return provider, settings


# --- LIST JOBS ---

@router.get("")
def get_all_jobs(user: UserRow = Depends(get_current_user)):
    return [job.to_response().model_dump() for job in list_jobs_for_user(user.id)]


# --- CREATE JOB ---

@router.post("")
async def create_new_job(
    candidate_file: UploadFile = File(...),
    user: UserRow = Depends(get_current_user),
):
    import logging
    logger = logging.getLogger(__name__)

    ext = os.path.splitext(candidate_file.filename)[1].lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(status_code=400, detail="Candidate file must be .xlsx, .xls, or .csv")

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    file_id = str(uuid.uuid4())[:8]
    save_path = os.path.join(config.UPLOAD_FOLDER, f"candidates_{file_id}{ext}")
    content = await _read_upload(candidate_file)
    with open(save_path, "wb") as f:
        f.write(content)
    store.save_local_file(save_path)

    try:
        data = load_data(save_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read file: {e}")

    try:
        job = create_job(candidate_file=candidate_file.filename, data=data, owner_id=user.id)
    except Exception as e:
        logger.exception(f"Failed to create job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

    return job.to_response().model_dump()


# --- GET JOB ---

@router.get("/{job_id}")
def get_job_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)
    return job.to_response().model_dump()


# --- SSE STREAM ---

@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str, user: UserRow = Depends(get_current_user)):
    """SSE stream pushing task progress and log availability.

    Reads directly from DB each tick (bypasses the in-memory cache) so that
    progress updates from background threads on OTHER workers are visible.
    """
    from fastapi.responses import StreamingResponse
    from app.database import get_session as db_session, JobRow

    async def generate():
        while True:
            try:
                session = db_session()
                try:
                    row = session.get(JobRow, job_id)
                    if not row or row.owner_id != user.id:
                        yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                        return

                    tasks_data = json.loads(row.tasks_json) if row.tasks_json else {}
                    job_status = row.status
                    timestamp = row.timestamp
                finally:
                    session.close()

                available_logs = []
                for key, meta in LOG_TYPES.items():
                    for ext in (".csv", ".xlsx"):
                        log_key = f"logs/{meta['prefix']}_{timestamp}{ext}"
                        try:
                            if store.exists(log_key):
                                available_logs.append(key)
                                break
                        except Exception:
                            pass

                yield "data: " + json.dumps({
                    "job_status": job_status,
                    "tasks": tasks_data,
                    "available_logs": available_logs,
                }) + "\n\n"

                has_running = any(
                    t.get("status") == "running"
                    for t in tasks_data.values()
                    if isinstance(t, dict)
                )
                await asyncio.sleep(2 if has_running else 10)

            except (asyncio.CancelledError, GeneratorExit):
                return
            except Exception:
                return

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- CANCEL TASK ---

@router.post("/{job_id}/{task_name}/cancel")
def cancel_task(job_id: str, task_name: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)
    if task_name not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task. Must be one of: {VALID_TASKS}")

    task = job.tasks[task_name]
    if task.status not in ("running", "created"):
        raise HTTPException(status_code=409, detail=f"Task '{task_name}' is not running (status: {task.status})")

    job.cancel_task(task_name)
    return {"message": f"Task '{task_name}' cancelled", "task": task_name}


# --- DELETE JOB ---

@router.delete("/{job_id}")
def delete_job(job_id: str, user: UserRow = Depends(get_current_user)):
    from app.services.jobs import delete_job_fully
    job = _get_job_or_404_light(job_id, user)

    # Block delete if any task is running
    running = [k for k, t in job.tasks.items() if t.status == "running"]
    if running:
        raise HTTPException(status_code=409, detail=f"Cannot delete while tasks are running: {running}")

    delete_job_fully(job)
    return {"message": "Job deleted", "job_id": job_id}


# --- PAUSE / RESUME TASK ---

@router.post("/{job_id}/{task_name}/pause")
def pause_task(job_id: str, task_name: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    if task_name not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task. Must be one of: {VALID_TASKS}")

    task = job.tasks[task_name]
    if task.status != "running":
        raise HTTPException(status_code=409, detail=f"Task '{task_name}' is not running (status: {task.status})")

    job.pause_task(task_name)
    return {"message": f"Task '{task_name}' paused", "progress": task.progress, "total": task.total}


@router.post("/{job_id}/{task_name}/resume")
def resume_task(job_id: str, task_name: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    if task_name not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task. Must be one of: {VALID_TASKS}")

    task = job.tasks[task_name]
    if task.phase != "paused":
        raise HTTPException(status_code=409, detail=f"Task '{task_name}' is not paused (phase: {task.phase})")

    job.resume_task(task_name)
    return {"message": f"Task '{task_name}' resumed"}


# --- RE-UPLOAD DATA ---

@router.post("/{job_id}/data")
async def reupload_data(
    job_id: str,
    candidate_file: UploadFile = File(...),
    user: UserRow = Depends(get_current_user),
):
    job = _get_job_or_404(job_id, user)

    # Block re-upload if any task is currently running
    running_tasks = [name for name, t in job.tasks.items() if t.status == "running"]
    if running_tasks:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot re-upload while tasks are running: {running_tasks}"
        )

    ext = os.path.splitext(candidate_file.filename)[1].lower()
    if ext not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(status_code=400, detail="Candidate file must be .xlsx, .xls, or .csv")

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    save_path = os.path.join(config.UPLOAD_FOLDER, f"candidates_{file_id}{ext}")
    content = await _read_upload(candidate_file)
    with open(save_path, "wb") as f:
        f.write(content)
    store.save_local_file(save_path)

    try:
        data = load_data(save_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read file: {e}")

    # Replace data without resetting completed tasks
    job.data = data
    job.columns = list(data.columns)
    job.candidate_file = candidate_file.filename
    # Clear filtered data (will be re-validated when tasks start)
    job.valid_data = None
    job.invalid_data = None
    job.save(include_data=True)

    return job.to_response().model_dump()


# --- ATTACH TEMPLATE ---

@router.post("/{job_id}/template")
def attach_template(job_id: str, request: AttachTemplateRequest, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    if request.template_id:
        # Sanitize template_id to prevent path traversal
        safe_id = os.path.basename(request.template_id)
        tpl_key = f"templates/{safe_id}.json"
        if not store.exists(tpl_key):
            raise HTTPException(status_code=404, detail=f"Template '{safe_id}' not found")
        tpl_data = store.load_bytes(tpl_key)
        job.template = TemplateConfig(**json.loads(tpl_data))
        job.template_id = safe_id

    elif request.template:
        job.template = request.template
        job.template_id = request.template.id

    else:
        raise HTTPException(status_code=400, detail="Provide either template_id or template config")

    # Reset column mapping confirmation when template changes (new placeholders)
    job.column_mapping_confirmed = False
    job.save()
    return {"message": "Template attached", "template_id": job.template_id}


# --- SET JOB MODE ---

@router.post("/{job_id}/mode")
async def set_job_mode(
    job_id: str,
    mode: str = Form(...),
    static_attachment: UploadFile = File(None),
    user: UserRow = Depends(get_current_user),
):
    """
    Set the job mode:
      - email_only: just send emails, no attachments
      - static_attachment: same file attached to every email
      - dynamic_pdf: generate a unique PDF per recipient (default)
    """
    job = _get_job_or_404(job_id, user)

    valid_modes = ("email_only", "static_attachment", "dynamic_pdf")
    if mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {valid_modes}")

    job.job_mode = mode

    if mode == "static_attachment" and static_attachment:
        os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
        file_id = str(uuid.uuid4())[:8]
        ext = os.path.splitext(static_attachment.filename)[1].lower()
        save_path = os.path.join(config.UPLOAD_FOLDER, f"attachment_{file_id}{ext}")
        content = await _read_upload(static_attachment)
        with open(save_path, "wb") as f:
            f.write(content)
        store.save_local_file(save_path)
        job.static_attachment_path = save_path

    job.save()
    return {"message": f"Job mode set to '{mode}'", "job_mode": mode}


# --- SET EMAIL CONTENT ---

class EmailContentRequest(BaseModel):
    subject: str
    body: str  # HTML with placeholders like {Name}, {Email}


@router.post("/{job_id}/email-content")
def set_email_content(job_id: str, req: EmailContentRequest, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    job.email_subject = req.subject
    job.email_body = req.body
    job.save()
    return {"message": "Email content saved"}


# --- COLUMN MAPPING ---

def _fuzzy_match_columns(placeholders: list[str], data_columns: list[str]) -> dict[str, str | None]:
    """Try to auto-match template placeholders to data columns.
    Returns {placeholder: matched_column_or_None}."""

    def normalize(s: str) -> str:
        return re.sub(r'[\s_\-]+', '', s).lower()

    mapping: dict[str, str | None] = {}
    used_columns: set[str] = set()

    for ph in placeholders:
        ph_norm = normalize(ph)
        best_match = None

        # Exact normalized match
        for col in data_columns:
            if col in used_columns:
                continue
            if normalize(col) == ph_norm:
                best_match = col
                break

        # Substring match (placeholder contained in column or vice versa)
        if not best_match:
            for col in data_columns:
                if col in used_columns:
                    continue
                col_norm = normalize(col)
                if ph_norm in col_norm or col_norm in ph_norm:
                    best_match = col
                    break

        mapping[ph] = best_match
        if best_match:
            used_columns.add(best_match)

    return mapping


@router.get("/{job_id}/column-mapping")
def get_column_mapping(job_id: str, user: UserRow = Depends(get_current_user)):
    """Return auto-matched and unmatched placeholders vs data columns."""
    job = _get_job_or_404(job_id, user)

    if not job.template:
        raise HTTPException(status_code=400, detail="No template attached")

    placeholders = job.template.placeholders or []
    mapping = _fuzzy_match_columns(placeholders, job.columns)

    auto_matched = {k: v for k, v in mapping.items() if v is not None}
    unmatched = [k for k, v in mapping.items() if v is None]

    return {
        "placeholders": placeholders,
        "columns": job.columns,
        "auto_matched": auto_matched,
        "unmatched": unmatched,
        "confirmed": job.column_mapping_confirmed,
    }


class ColumnMappingRequest(BaseModel):
    mapping: dict[str, str]  # {placeholder_name: data_column_name}


@router.post("/{job_id}/column-mapping")
def apply_column_mapping(job_id: str, req: ColumnMappingRequest, user: UserRow = Depends(get_current_user)):
    """Rename data columns to match template placeholders."""
    job = _get_job_or_404(job_id, user)

    # Block if tasks are running
    running = [k for k, t in job.tasks.items() if t.status == "running"]
    if running:
        raise HTTPException(status_code=409, detail=f"Cannot remap while tasks are running: {running}")

    # Build rename map: {old_column_name: new_placeholder_name}
    rename_map = {}
    for placeholder, column in req.mapping.items():
        if column in job.columns and column != placeholder:
            rename_map[column] = placeholder

    if rename_map:
        job.data = job.data.rename(columns=rename_map)
        job.columns = list(job.data.columns)

    # Mark mapping as confirmed (persists across refreshes)
    job.column_mapping_confirmed = True
    job.save(include_data=bool(rename_map))

    return {
        "message": f"Mapped {len(rename_map)} columns",
        "columns": job.columns,
    }


# --- SET SMS CONTENT ---

class SmsContentRequest(BaseModel):
    body: str  # Plain text with {Name}, {ExamNo} placeholders


@router.post("/{job_id}/sms-content")
def set_sms_content(job_id: str, req: SmsContentRequest, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    job.sms_body = req.body
    job.save()
    return {"message": "SMS content saved"}


# --- GENERATE PDFs ---

@router.post("/{job_id}/pdfs/generate")
def generate_pdfs(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    if not job.template:
        raise HTTPException(status_code=400, detail="No template attached — attach one first")

    if job.tasks["pdfs"].status == "running":
        raise HTTPException(status_code=409, detail="PDF generation already running")

    # Check data is loaded
    if job.data is None or len(job.data) == 0:
        raise HTTPException(
            status_code=400,
            detail="No recipient data loaded. The data file may have been lost after a deploy. Please re-upload the spreadsheet.",
        )

    # Validate emails if an Email column exists
    if "Email" in job.columns:
        job.validate_emails()

    # Clear stop flag before (re)start
    job.stop_flags["pdfs"] = False
    job._clear_stop_flag("pdfs")

    start_pdf_generation(job)
    return {"message": "PDF generation started", "total": job.tasks["pdfs"].total}


@router.get("/{job_id}/pdfs/status")
def get_pdf_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)
    return job.tasks["pdfs"].model_dump()


@router.get("/{job_id}/pdfs/download")
def download_pdfs(
    job_id: str,
    partial: bool = Query(False),
    user: UserRow = Depends(get_current_user),
):
    import zipfile

    job = _get_job_or_404_light(job_id, user)
    task = job.tasks["pdfs"]

    if partial:
        # Zip whatever PDFs exist so far (for paused/running jobs)
        pdf_folder = job.get_pdf_folder()
        if not os.path.isdir(pdf_folder) or not os.listdir(pdf_folder):
            raise HTTPException(status_code=404, detail="No PDFs generated yet")

        zip_path = os.path.join(config.OUTPUT_FOLDER, f"pdfs_{job_id}_partial.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in sorted(os.listdir(pdf_folder)):
                if filename.endswith(".pdf"):
                    zf.write(os.path.join(pdf_folder, filename), filename)

        from fastapi.responses import FileResponse
        return FileResponse(zip_path, media_type="application/zip", filename=f"pdfs_{job_id}_partial.zip")

    # Full download — only when complete
    if task.status != "complete":
        raise HTTPException(status_code=409, detail=f"PDFs not ready (status: {task.status})")

    zip_key = f"output/pdfs_{job_id}.zip"
    if not store.exists(zip_key):
        raise HTTPException(status_code=404, detail="ZIP file not found")

    return store.serve(zip_key, media_type="application/zip", filename=f"pdfs_{job_id}.zip")


# --- SEND EMAILS ---

@router.post("/{job_id}/emails/send")
def send_emails(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    job_mode = getattr(job, "job_mode", "dynamic_pdf")

    if job_mode == "dynamic_pdf":
        if not job.template:
            raise HTTPException(status_code=400, detail="No template attached")
        pdf_task = job.tasks["pdfs"]
        if pdf_task.status != "complete":
            raise HTTPException(status_code=400, detail="Generate PDFs first before sending emails")
    elif job_mode == "static_attachment":
        if not job.template:
            raise HTTPException(status_code=400, detail="No template/email config attached")
    # email_only: no extra checks

    if job.tasks["emails"].status == "running":
        raise HTTPException(status_code=409, detail="Email send already running")

    # Check data is loaded (survives redeploys via S3)
    data = job.valid_data if job.valid_data is not None else job.data
    if data is None or len(data) == 0:
        raise HTTPException(
            status_code=400,
            detail="No recipient data loaded. The data file may have been lost after a deploy. Please re-upload the spreadsheet.",
        )

    provider, settings = _get_user_provider(user)

    # Clear stop flag before (re)start
    job.stop_flags["emails"] = False
    job._clear_stop_flag("emails")

    start_email_send(job, provider, from_name=settings.from_name, from_email=settings.from_email)
    return {"message": "Email send started", "total": job.tasks["emails"].total}


@router.get("/{job_id}/emails/status")
def get_email_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)
    return job.tasks["emails"].model_dump()


# --- SEND SMS ---

@router.post("/{job_id}/sms/send")
def send_sms(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    # SMS needs a phone number column
    phone_cols = [c for c in job.columns if c.lower() in ("phone", "phonenumber", "phone_number", "mobile", "tel")]
    if not phone_cols:
        raise HTTPException(status_code=400, detail="No phone number column found in data (expected Phone, PhoneNumber, or Mobile)")

    if job.tasks["sms"].status == "running":
        raise HTTPException(status_code=409, detail="SMS send already running")

    # Check data is loaded
    if job.data is None or len(job.data) == 0:
        raise HTTPException(
            status_code=400,
            detail="No recipient data loaded. The data file may have been lost after a deploy. Please re-upload the spreadsheet.",
        )

    # Clear stop flag before (re)start
    job.stop_flags["sms"] = False
    job._clear_stop_flag("sms")

    start_sms_send(job)
    return {"message": "SMS send started", "total": job.tasks["sms"].total}


@router.get("/{job_id}/sms/status")
def get_sms_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)
    return job.tasks["sms"].model_dump()


# --- DOWNLOAD PHOTOS ---

@router.post("/{job_id}/photos/download")
def download_photos(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    if job.tasks["photos"].status == "running":
        raise HTTPException(status_code=409, detail="Photo download already running")

    # Clear stop flag before (re)start
    job.stop_flags["photos"] = False
    job._clear_stop_flag("photos")

    start_photo_download(job)
    return {"message": "Photo download started", "total": job.tasks["photos"].total}


@router.get("/{job_id}/photos/status")
def get_photo_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)
    return job.tasks["photos"].model_dump()


# --- REPORT ---

@router.get("/{job_id}/report")
def get_report(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    email_task = job.tasks["emails"]
    if email_task.status != "complete":
        raise HTTPException(status_code=409, detail="Emails not sent yet — send emails first")

    try:
        report_path = generate_report(job)
        store.save_local_file(report_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    from app.services.storage import _key_from_local
    report_key = _key_from_local(report_path)
    return store.serve(
        report_key,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"report_{job_id}.xlsx",
    )


# --- LOG TYPES REGISTRY ---
# To add a new log type: add an entry here and ensure the task writes a file
# named {prefix}_{job.timestamp}.csv (or .xlsx) to config.LOG_FOLDER.
LOG_TYPES = {
    "emails": {"prefix": "run", "label": "Email Log"},
    "sms": {"prefix": "sms_run", "label": "SMS Log"},
    "photos": {"prefix": "photo_download", "label": "Photo Download Log"},
    "invalid_emails": {"prefix": "invalid_emails", "label": "Invalid Emails"},
}


def _read_log_file(path: str, limit: int, offset: int) -> dict:
    ext = os.path.splitext(path)[1].lower()
    rows = []
    headers = []

    if ext == ".csv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            for i, row in enumerate(reader):
                if i < offset:
                    continue
                if len(rows) >= limit:
                    break
                rows.append(row)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)
        df = df.fillna("")
        headers = list(df.columns)
        sliced = df.iloc[offset:offset + limit]
        for _, row in sliced.iterrows():
            rows.append({col: str(val) for col, val in row.items()})

    return {"headers": headers, "rows": rows}


@router.get("/{job_id}/logs")
def list_job_logs(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404_light(job_id, user)

    available = []
    for key, meta in LOG_TYPES.items():
        for ext in (".csv", ".xlsx"):
            filename = f"{meta['prefix']}_{job.timestamp}{ext}"
            log_key = f"logs/{filename}"
            if store.exists(log_key):
                available.append({
                    "key": key,
                    "label": meta["label"],
                    "filename": filename,
                    "size": store.get_size(log_key),
                })
                break

    return available


@router.get("/{job_id}/logs/{log_key}")
def get_job_log(
    job_id: str,
    log_key: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserRow = Depends(get_current_user),
):
    job = _get_job_or_404_light(job_id, user)

    if log_key not in LOG_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown log type: {log_key}")

    meta = LOG_TYPES[log_key]
    path = None
    for ext in (".csv", ".xlsx"):
        log_storage_key = f"logs/{meta['prefix']}_{job.timestamp}{ext}"
        if store.exists(log_storage_key):
            path = store.ensure_local(log_storage_key)
            break

    if not path:
        raise HTTPException(status_code=404, detail=f"No {meta['label']} found for this job")

    data = _read_log_file(path, limit, offset)
    return {
        "key": log_key,
        "label": meta["label"],
        "headers": data["headers"],
        "rows": data["rows"],
        "offset": offset,
        "limit": limit,
    }
