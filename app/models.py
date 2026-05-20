from pydantic import BaseModel, Field
from typing import Optional
import uuid


# --- TEMPLATE MODELS ---

class ThemeConfig(BaseModel):
    primary_color: str = "#08764F"
    secondary_color: str = "#08AB52"
    accent_color: str = "#E8F4EC"
    text_color: str = "#2C2C2C"
    label_color: str = "#777777"


class HeaderConfig(BaseModel):
    logo_path: Optional[str] = None
    company_name: str = ""
    address_lines: list[str] = []
    contact_lines: list[str] = []
    motto: Optional[str] = None
    show_number: bool = True


class ReferenceConfig(BaseModel):
    our_ref: Optional[str] = None
    date: Optional[str] = None


class DetailField(BaseModel):
    label: str
    value: str


class DetailBoxConfig(BaseModel):
    title: str = "DETAILS"
    field_rows: list[list[DetailField]] = []


class InstructionsConfig(BaseModel):
    heading: str = "Important Instructions"
    items: list[str] = []


class ComplianceConfig(BaseModel):
    heading: str = "Compliance Notice"
    text: str = ""


class SignatureConfig(BaseModel):
    closing: str = "Yours faithfully,"
    name: str = ""
    title: str = ""


class FooterConfig(BaseModel):
    text: str = ""
    credit: Optional[str] = None


class TemplateConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Untitled Template"
    description: str = ""
    theme: ThemeConfig = ThemeConfig()
    header: HeaderConfig = HeaderConfig()
    reference: ReferenceConfig = ReferenceConfig()
    subject: str = ""
    salutation: str = "Dear {Name},"
    show_photo: bool = True
    body_paragraphs: list[str] = []
    detail_box: Optional[DetailBoxConfig] = None
    notice: Optional[str] = None
    instructions: Optional[InstructionsConfig] = None
    compliance: Optional[ComplianceConfig] = None
    signature: SignatureConfig = SignatureConfig()
    footer: FooterConfig = FooterConfig()


# --- UPLOAD MODELS ---

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    raw_text: str
    detected_fields: dict


class GenerateTemplateRequest(BaseModel):
    parsed_content: dict
    instructions: Optional[str] = None


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


class SendSMSRequest(BaseModel):
    detailed: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: str
    candidate_file: Optional[str] = None
    candidate_count: int = 0
    columns: list[str] = []
    template_id: Optional[str] = None
    is_allocated: bool = False
    job_mode: str = "dynamic_pdf"  # "dynamic_pdf", "static_attachment", "email_only"
    email_subject: str = ""
    email_body: str = ""
    tasks: dict[str, TaskStatus] = {}
