import os
import csv
import json
import uuid
import asyncio

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import pandas as pd

import re
from app.models import AttachTemplateRequest, TemplateConfig
from app.services.jobs import create_job, get_job_for_user, get_job_light_for_user, list_jobs_for_user
from app.services.read_data import load_data
from app.services.pdf_tasks import start_pdf_generation
from app.services.email_tasks import start_email_send
from app.services.sms_tasks import start_sms_send
from app.services.sms_providers import create_sms_provider
from app.services.photo_tasks import start_photo_download
from app.services.report_tasks import generate_report
from app.services.storage import store
from app.services.ai_generator import edit_template_with_ai, extract_placeholders, draft_email_with_ai, draft_sms_with_ai
from app.services.template_renderer import fill_placeholders, render_html_preview, add_preview_page_margins
from app.dependencies import get_current_user
from app.database import UserRow, EmailSettingsRow, SMSSettingsRow, get_session
from app.services.encryption import decrypt_credentials
from app.services.email_providers import create_provider
from app.services.billing import (
    check_job_limit,
    check_row_limit,
    check_template_access,
    check_ai_limit,
    increment_ai_usage,
    get_user_tier,
)
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

    # ── Tier guard: active job limit ──
    existing_jobs = list_jobs_for_user(user.id)
    if not check_job_limit(user.id, len(existing_jobs)):
        raise HTTPException(
            status_code=403,
            detail="You've reached your active job limit. Delete a completed job or upgrade your plan.",
        )

    # ── Tier guard: row limit (with image link detection) ──
    columns = list(data.columns)
    allowed, max_rows = check_row_limit(user.id, len(data), columns)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"This spreadsheet has {len(data):,} rows, which exceeds your plan's limit of {max_rows:,} rows per job. Upgrade your plan for higher limits.",
        )

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

    # ── Tier guard: row limit on re-upload ──
    columns = list(data.columns)
    allowed, max_rows = check_row_limit(user.id, len(data), columns)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"This spreadsheet has {len(data):,} rows, which exceeds your plan's limit of {max_rows:,} rows per job. Upgrade your plan for higher limits.",
        )

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
        tpl_config = json.loads(tpl_data)

        # ── Tier guard: check user can access this template's tier ──
        tpl_tier = tpl_config.get("tier_required", "free")
        user_tier = get_user_tier(user.id)
        if not check_template_access(user_tier, tpl_tier):
            raise HTTPException(
                status_code=403,
                detail=f"This template requires the {tpl_tier} plan or higher. Upgrade to use it.",
            )

        job.template = TemplateConfig(**tpl_config)
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


# --- IN-JOB TEMPLATE EDITING ---
# A template attached to a job is FORKED into a job-local copy (JobRow.template_json)
# via job.save(), so edits here never touch the shared library TemplateRow.

def _require_editable_template(job):
    """Shared guard for template-edit endpoints: template attached + nothing running."""
    if not job.template:
        raise HTTPException(status_code=400, detail="No template attached to this job yet. Choose one first.")
    running = [k for k, t in job.tasks.items() if t.status == "running"]
    if running:
        raise HTTPException(status_code=409, detail=f"Cannot edit the template while tasks are running: {running}")


def _job_sample_rows(job, n: int = 3) -> list[dict]:
    """A few real rows from the job's data — for AI context and realistic preview."""
    df = job.valid_data if getattr(job, "valid_data", None) is not None else job.data
    if df is None or len(df) == 0:
        return []
    return df.head(n).fillna("").to_dict(orient="records")


@router.get("/{job_id}/template")
def get_job_template(job_id: str, user: UserRow = Depends(get_current_user)):
    """Return the job-local template (the editable fork)."""
    job = _get_job_or_404(job_id, user)
    if not job.template:
        raise HTTPException(status_code=404, detail="No template attached to this job")
    return job.template.model_dump()


class JobTemplateHtmlRequest(BaseModel):
    html_content: str


@router.put("/{job_id}/template")
def save_job_template(job_id: str, req: JobTemplateHtmlRequest, user: UserRow = Depends(get_current_user)):
    """Save edited HTML to the job-local template (HTML + rich-text tabs)."""
    job = _get_job_or_404(job_id, user)
    _require_editable_template(job)

    job.template.html_content = req.html_content
    job.template.placeholders = extract_placeholders(req.html_content)
    job.column_mapping_confirmed = False  # new placeholders may need remapping
    job.save()
    return job.template.model_dump()


class AiEditMessage(BaseModel):
    role: str
    content: str


class AiEditRequest(BaseModel):
    messages: list[AiEditMessage]


@router.post("/{job_id}/template/ai-edit")
def ai_edit_job_template(job_id: str, req: AiEditRequest, user: UserRow = Depends(get_current_user)):
    """Edit the job-local template via AI (edit, don't regenerate). Quota-gated."""
    job = _get_job_or_404(job_id, user)
    _require_editable_template(job)

    if not req.messages or req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Provide a conversation ending with a user instruction.")

    # ── AI quota guard (every AI endpoint is paired: check before, increment after) ──
    allowed, current, limit = check_ai_limit(user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {limit} AI messages this month. Upgrade your plan for more.",
        )

    try:
        new_html, summary = edit_template_with_ai(
            current_html=job.template.html_content,
            columns=job.columns,
            sample_rows=_job_sample_rows(job),
            messages=[m.model_dump() for m in req.messages],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI edit failed: {e}")

    increment_ai_usage(user.id)

    job.template.html_content = new_html
    job.template.placeholders = extract_placeholders(new_html)
    job.column_mapping_confirmed = False
    job.set_ai_chat("template", [m.model_dump() for m in req.messages] + [{"role": "assistant", "content": summary}])
    job.save()

    return {"template": job.template.model_dump(), "summary": summary}


@router.post("/{job_id}/template/reset")
def reset_job_template(job_id: str, user: UserRow = Depends(get_current_user)):
    """Re-fork the job template from the original library template, discarding edits."""
    job = _get_job_or_404(job_id, user)
    running = [k for k, t in job.tasks.items() if t.status == "running"]
    if running:
        raise HTTPException(status_code=409, detail=f"Cannot reset the template while tasks are running: {running}")
    if not job.template_id:
        raise HTTPException(status_code=400, detail="This job has no original template to reset to.")

    safe_id = os.path.basename(job.template_id)
    tpl_key = f"templates/{safe_id}.json"
    if not store.exists(tpl_key):
        raise HTTPException(status_code=404, detail="The original template no longer exists in your library.")
    tpl_config = json.loads(store.load_bytes(tpl_key))

    job.template = TemplateConfig(**tpl_config)
    job.column_mapping_confirmed = False
    job.save()
    return job.template.model_dump()


# --- ASK VOLLEY: EMAIL + SMS DRAFTING + CHAT TRANSCRIPTS ---
# AI drafts apply to the job immediately and persist the conversation on the job
# (JobRow.ai_chats_json), so it survives logout/device/refresh. The AI calls stay
# stateless — the client replays the full messages[] each turn; the DB is the backup.

_AI_CHANNELS = ("template", "email", "sms")


@router.post("/{job_id}/email/ai-draft")
def ai_draft_email(job_id: str, req: AiEditRequest, user: UserRow = Depends(get_current_user)):
    """Draft/refine the job's email (subject + HTML body) via Ask Volley; applies + persists."""
    job = _get_job_or_404(job_id, user)
    if job.tasks["emails"].status == "running":
        raise HTTPException(status_code=409, detail="Cannot edit the email while it is sending")
    if not req.messages or req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Provide a conversation ending with a user instruction.")

    allowed, current, limit = check_ai_limit(user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"You've used all {limit} AI messages this month. Upgrade your plan for more.")

    sent = [m.model_dump() for m in req.messages]
    try:
        subject, body, summary = draft_email_with_ai(
            columns=job.columns,
            sample_rows=_job_sample_rows(job),
            current_subject=job.email_subject,
            current_body=job.email_body,
            messages=sent,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI draft failed: {e}")

    increment_ai_usage(user.id)
    job.email_subject = subject
    job.email_body = body
    job.set_ai_chat("email", sent + [{"role": "assistant", "content": summary}])
    job.save()
    return {"subject": subject, "body": body, "summary": summary}


@router.post("/{job_id}/sms/ai-draft")
def ai_draft_sms(job_id: str, req: AiEditRequest, user: UserRow = Depends(get_current_user)):
    """Draft/refine the job's SMS (plain text) via Ask Volley; applies + persists."""
    job = _get_job_or_404(job_id, user)
    if job.tasks["sms"].status == "running":
        raise HTTPException(status_code=409, detail="Cannot edit the SMS while it is sending")
    if not req.messages or req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Provide a conversation ending with a user instruction.")

    allowed, current, limit = check_ai_limit(user.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"You've used all {limit} AI messages this month. Upgrade your plan for more.")

    sent = [m.model_dump() for m in req.messages]
    try:
        body, summary = draft_sms_with_ai(
            columns=job.columns,
            sample_rows=_job_sample_rows(job),
            current_body=job.sms_body,
            messages=sent,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI draft failed: {e}")

    increment_ai_usage(user.id)
    job.sms_body = body
    job.set_ai_chat("sms", sent + [{"role": "assistant", "content": summary}])
    job.save()
    return {"body": body, "summary": summary}


@router.get("/{job_id}/ai-chats")
def get_ai_chats(job_id: str, user: UserRow = Depends(get_current_user)):
    """Return the per-channel Ask Volley transcripts for this job (fast, light load)."""
    job = _get_job_or_404_light(job_id, user)
    return {ch: job.get_ai_chat(ch) for ch in _AI_CHANNELS}


@router.get("/{job_id}/sample-row")
def get_sample_row(job_id: str, user: UserRow = Depends(get_current_user)):
    """First data row as a dict — for live previews (e.g. SMS placeholder fill). {} if no data."""
    job = _get_job_or_404(job_id, user)
    rows = _job_sample_rows(job, 1)
    return rows[0] if rows else {}


@router.put("/{job_id}/ai-chats/{channel}")
def set_ai_chat_route(job_id: str, channel: str, req: AiEditRequest, user: UserRow = Depends(get_current_user)):
    """Replace one channel's transcript (e.g. 'Clear'). Targeted DB write — avoids a full load + save."""
    if channel not in _AI_CHANNELS:
        raise HTTPException(status_code=400, detail="Invalid channel")
    _get_job_or_404_light(job_id, user)  # ownership check (raises 404 if not owner)

    from app.database import get_session, JobRow
    session = get_session()
    try:
        row = session.get(JobRow, job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        try:
            chats = json.loads(row.ai_chats_json or "{}")
            if not isinstance(chats, dict):
                chats = {}
        except (json.JSONDecodeError, TypeError):
            chats = {}
        chats[channel] = [m.model_dump() for m in req.messages]
        row.ai_chats_json = json.dumps(chats)
        session.commit()
    finally:
        session.close()
    return {"message": "saved"}


@router.get("/{job_id}/template/preview")
def preview_job_template(job_id: str, user: UserRow = Depends(get_current_user)):
    """Render the job-local template filled with the first real data row (iframe preview)."""
    job = _get_job_or_404(job_id, user)
    if not job.template:
        raise HTTPException(status_code=404, detail="No template attached to this job")

    rows = _job_sample_rows(job, 1)
    if rows:
        html = add_preview_page_margins(fill_placeholders(job.template.html_content, rows[0]))
    else:
        html = render_html_preview(job.template)  # highlight placeholders when there's no data
    return HTMLResponse(content=html, status_code=200)


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

    # Email body must be set — we never silently send a generic fallback message.
    if not (job.email_body or "").strip():
        raise HTTPException(status_code=400, detail="Set email content before sending emails.")

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

    # SMS body must be set — we never silently send a generic fallback message.
    if not (job.sms_body or "").strip():
        raise HTTPException(status_code=400, detail="Set SMS content before sending SMS.")

    if job.tasks["sms"].status == "running":
        raise HTTPException(status_code=409, detail="SMS send already running")

    # Check data is loaded
    if job.data is None or len(job.data) == 0:
        raise HTTPException(
            status_code=400,
            detail="No recipient data loaded. The data file may have been lost after a deploy. Please re-upload the spreadsheet.",
        )

    # Resolve the SMS provider: per-user settings win; fall back to the global BulkSMS env
    # (transition) so existing Nigeria sending keeps working until a provider is configured.
    s = get_session()
    try:
        sms_settings = s.get(SMSSettingsRow, user.id)
    finally:
        s.close()

    if sms_settings:
        provider = create_sms_provider(
            sms_settings.provider_name, decrypt_credentials(sms_settings.credentials_encrypted)
        )
        sender_id = sms_settings.sender_id
        default_region = sms_settings.default_region or "NG"
    elif config.BULKSMS_API_TOKEN:
        provider = create_sms_provider("bulksms", {"api_token": config.BULKSMS_API_TOKEN})
        sender_id = config.SMS_DEFAULT_SENDER
        default_region = "NG"
    else:
        raise HTTPException(status_code=400, detail="No SMS provider configured. Set one up in Settings → SMS.")

    # Clear stop flag before (re)start
    job.stop_flags["sms"] = False
    job._clear_stop_flag("sms")

    start_sms_send(job, provider, sender_id, default_region)
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


@router.get("/{job_id}/photos/zip")
def download_photos_zip(job_id: str, user: UserRow = Depends(get_current_user)):
    """Download the ZIP of all downloaded photos."""
    job = _get_job_or_404_light(job_id, user)
    task = job.tasks["photos"]

    if task.status != "complete":
        raise HTTPException(status_code=409, detail=f"Photos not ready (status: {task.status})")

    zip_key = f"output/photos_{job_id}.zip"
    if not store.exists(zip_key):
        raise HTTPException(status_code=404, detail="Photo ZIP not found")

    return store.serve(zip_key, media_type="application/zip", filename=f"photos_{job_id}.zip")


# --- REPORT ---

@router.get("/{job_id}/report")
def get_report(job_id: str, user: UserRow = Depends(get_current_user)):
    job = _get_job_or_404(job_id, user)

    # Available once ANY task completes; regenerated on each download so it reflects
    # whatever has finished so far.
    if not any(t.status == "complete" for t in job.tasks.values()):
        raise HTTPException(status_code=409, detail="Run at least one task (PDFs, emails, SMS, or photos) before downloading the report.")

    try:
        report_path = generate_report(job)
        store.save_local_file(report_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    # Stream the freshly-written local file directly — never a presigned redirect — so the
    # downloaded bytes are always the real report.
    return FileResponse(
        report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"report_{job_id}.xlsx",
    )


# --- LOG TYPES REGISTRY ---
# To add a new log type: add an entry here and ensure the task writes a file
# named {prefix}_{job.timestamp}.csv (or .xlsx) to config.LOG_FOLDER.
LOG_TYPES = {
    "emails": {"prefix": "run", "label": "Email Log"},
    "pdfs": {"prefix": "pdf_run", "label": "PDF Log"},
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


@router.get("/{job_id}/logs/{log_key}/download")
def download_job_log(
    job_id: str,
    log_key: str,
    user: UserRow = Depends(get_current_user),
):
    """Download the raw log file (CSV or XLSX)."""
    job = _get_job_or_404_light(job_id, user)

    if log_key not in LOG_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown log type: {log_key}")

    meta = LOG_TYPES[log_key]
    storage_key = None
    for ext in (".csv", ".xlsx"):
        candidate_key = f"logs/{meta['prefix']}_{job.timestamp}{ext}"
        if store.exists(candidate_key):
            storage_key = candidate_key
            break

    if not storage_key:
        raise HTTPException(status_code=404, detail=f"No {meta['label']} found for this job")

    ext = os.path.splitext(storage_key)[1]
    media_type = (
        "text/csv; charset=utf-8" if ext == ".csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"{meta['label'].lower().replace(' ', '_')}_{job_id}{ext}"

    # Stream the file (downloading from storage if needed) instead of a presigned redirect,
    # so the downloaded bytes are always the real file (fixes the "gibberish download").
    local_path = store.ensure_local(storage_key)
    return FileResponse(local_path, media_type=media_type, filename=filename)
