from pydantic import BaseModel, Field
from typing import Optional
import uuid


# --- TEMPLATE MODEL ---

class TemplateConfig(BaseModel):
    """
    A template is an HTML/CSS document with {placeholder} merge fields.
    The AI generates the full HTML; WeasyPrint renders it to PDF.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Untitled Template"
    description: str = ""
    html_content: str = ""  # Full HTML/CSS template with {Placeholder} merge fields
    placeholders: list[str] = []  # List of placeholder names used in the HTML


# --- UPLOAD MODELS ---

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    raw_text: str
    detected_fields: dict


class GenerateTemplateRequest(BaseModel):
    parsed_content: Optional[dict] = None  # single doc (backward compat)
    parsed_contents: Optional[list[dict]] = None  # multiple docs (image + document combo)
    instructions: Optional[str] = None
    columns: Optional[list[str]] = None  # CSV column names to use as placeholders


class SaveTemplateRequest(BaseModel):
    template: TemplateConfig


# --- TASK MODELS ---

class TaskStatus(BaseModel):
    status: str = "idle"
    phase: str = ""
    progress: int = 0
    total: int = 0
    error: Optional[str] = None

    # Counters specific to each task type
    pdfs_generated: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    sms_sent: int = 0
    sms_failed: int = 0
    sms_skipped: int = 0
    photos_downloaded: int = 0
    photos_failed: int = 0
    filtered_out: int = 0


# --- JOB MODELS ---

class AttachTemplateRequest(BaseModel):
    template_id: Optional[str] = None
    template: Optional[TemplateConfig] = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    candidate_file: Optional[str] = None
    candidate_count: int = 0
    columns: list[str] = []
    template_id: Optional[str] = None
    job_mode: str = "dynamic_pdf"  # "dynamic_pdf", "static_attachment", "email_only"
    email_subject: str = ""
    email_body: str = ""
    sms_body: str = ""
    tasks: dict[str, TaskStatus] = {}
