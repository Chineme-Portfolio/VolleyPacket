import os
import csv
import json
import uuid

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

import pandas as pd

from app.models import AttachTemplateRequest, SendSMSRequest, TemplateConfig
from app.services.jobs import create_job, get_job_for_user, list_jobs_for_user
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
    is_allocated: bool = Form(False),
    user: UserRow = Depends(get_current_user),
):
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
        if is_allocated:
            data = pd.read_excel(save_path) if ext != ".csv" else pd.read_csv(save_path)
            data = data.fillna("")
        else:
            data = load_data(save_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read file: {e}")

    job = create_job(candidate_file=candidate_file.filename, data=data, owner_id=user.id)
    job.is_allocated = is_allocated
    job.save()

    return job.to_response().model_dump()


# --- GET JOB ---

@router.get("/{job_id}")
def get_job_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    return job.to_response().model_dump()


# --- CANCEL JOB ---

@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    job.cancel()
    return {"message": "Job cancelled", "job_id": job_id}


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
    is_allocated: bool = Form(False),
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
        if is_allocated:
            data = pd.read_excel(save_path) if ext != ".csv" else pd.read_csv(save_path)
            data = data.fillna("")
        else:
            data = load_data(save_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read file: {e}")

    # Reset job state with new data
    job.data = data
    job.columns = list(data.columns)
    job.candidate_file = candidate_file.filename
    job.is_allocated = is_allocated
    job.allocated_path = None
    job.status = "created"
    job.reset_tasks()
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


# --- ALLOCATE ---

@router.post("/{job_id}/allocate")
def allocate_job(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    if job.is_allocated:
        raise HTTPException(status_code=409, detail="Data is already allocated")

    if "ExamDate" not in job.columns:
        raise HTTPException(status_code=422, detail="Data missing 'ExamDate' column — required for allocation")

    try:
        job.allocate()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Allocation failed: {e}")

    return {
        "message": "Allocation complete",
        "allocated_path": job.allocated_path,
        "columns": job.columns,
        "candidate_count": len(job.data),
    }


# --- GENERATE PDFs ---

@router.post("/{job_id}/pdfs/generate")
def generate_pdfs(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    if not job.template:
        raise HTTPException(status_code=400, detail="No template attached — attach one first")

    if job.tasks["pdfs"].status == "running":
        raise HTTPException(status_code=409, detail="PDF generation already running")

    # Validate emails if an Email column exists
    if "Email" in job.columns:
        job.validate_emails()

    start_pdf_generation(job)
    return {"message": "PDF generation started", "total": job.tasks["pdfs"].total}


@router.get("/{job_id}/pdfs/status")
def get_pdf_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    return job.tasks["pdfs"].model_dump()


@router.get("/{job_id}/pdfs/download")
def download_pdfs(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    task = job.tasks["pdfs"]
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

    provider, settings = _get_user_provider(user)

    start_email_send(job, provider, from_name=settings.from_name, from_email=settings.from_email)
    return {"message": "Email send started", "total": job.tasks["emails"].total}


@router.get("/{job_id}/emails/status")
def get_email_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    return job.tasks["emails"].model_dump()


# --- SEND SMS ---

@router.post("/{job_id}/sms/send")
def send_sms(job_id: str, request: SendSMSRequest = SendSMSRequest(), user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    # SMS needs a phone number column
    phone_cols = [c for c in job.columns if c.lower() in ("phone", "phonenumber", "phone_number", "mobile", "tel")]
    if not phone_cols:
        raise HTTPException(status_code=400, detail="No phone number column found in data (expected Phone, PhoneNumber, or Mobile)")

    if job.tasks["sms"].status == "running":
        raise HTTPException(status_code=409, detail="SMS send already running")

    start_sms_send(job, detailed=request.detailed)
    return {"message": "SMS send started", "total": job.tasks["sms"].total}


@router.get("/{job_id}/sms/status")
def get_sms_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
    return job.tasks["sms"].model_dump()


# --- DOWNLOAD PHOTOS ---

@router.post("/{job_id}/photos/download")
def download_photos(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    if job.tasks["photos"].status == "running":
        raise HTTPException(status_code=409, detail="Photo download already running")

    start_photo_download(job)
    return {"message": "Photo download started", "total": job.tasks["photos"].total}


@router.get("/{job_id}/photos/status")
def get_photo_status(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)
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
    job = _get_job_or_404(job_id, user)

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
    job = _get_job_or_404(job_id, user)

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
