import os
import csv
import threading

from app.services.jobs import Job
from app.services.generator import safe_filename
from app.services.email_providers import EmailProvider, EmailMessage
from app.services.storage import store, _key_from_local
from app import config


DEFAULT_EMAIL_BODY = """<html>
<body style="font-family: Arial, sans-serif; color: #2C2C2C; line-height: 1.6;">
  <p>Dear {Name},</p>
  <p>Please find your document attached to this email.</p>
  <p>If you have any questions, please do not hesitate to reach out.</p>
  <p>Best regards,<br>
  <strong>{sender_name}</strong></p>
</body>
</html>"""


def _render_body(template_html: str, row_dict: dict, sender_name: str, sender_title: str) -> str:
    """Replace placeholders in the email body with row values and sender info."""
    body = template_html
    # Replace known placeholders
    body = body.replace("{sender_name}", sender_name)
    body = body.replace("{sender_title}", sender_title)
    # Replace any column-based placeholders like {Name}, {Email}, {ExamNo}, etc.
    for key, val in row_dict.items():
        body = body.replace(f"{{{key}}}", str(val))
    return body


def _render_subject(template_subject: str, row_dict: dict) -> str:
    """Replace placeholders in the subject line with row values."""
    subject = template_subject
    for key, val in row_dict.items():
        subject = subject.replace(f"{{{key}}}", str(val))
    return subject


def run_email_send(job: Job, provider: EmailProvider, from_name: str, from_email: str):
    task = job.tasks["emails"]
    data = job.valid_data if job.valid_data is not None else job.data
    # total already set by start_email_send before thread starts

    job_mode = getattr(job, "job_mode", "dynamic_pdf")
    pdf_folder = job.get_pdf_folder() if job_mode == "dynamic_pdf" else None
    static_attachment_path = getattr(job, "static_attachment_path", None)

    # Email content — use job's custom content or defaults
    email_subject_tpl = getattr(job, "email_subject", "") or "Message for {Name}"
    email_body_tpl = getattr(job, "email_body", "") or DEFAULT_EMAIL_BODY

    # Sender info for template
    if job.template and job.template.signature:
        sig_name = job.template.signature.name or from_name
        sig_title = job.template.signature.title or ""
    else:
        sig_name = from_name
        sig_title = ""

    os.makedirs(config.LOG_FOLDER, exist_ok=True)
    log_path = os.path.join(config.LOG_FOLDER, f"run_{job.timestamp}.csv")
    job.log_path = log_path

    try:
        with open(log_path, "w", newline="", encoding="utf-8") as log_file:
            writer = csv.DictWriter(
                log_file,
                fieldnames=["Name", "Email", "ExamNo", "PDFGenerated", "EmailSent", "Error"],
            )
            writer.writeheader()
            log_file.flush()

            for idx, (_, row) in enumerate(data.iterrows()):
                if job.should_stop("emails"):
                    task.status = "cancelled"
                    task.phase = "cancelled"
                    job.save()
                    return

                row_dict = row.to_dict()
                exam_no = str(row_dict.get("ExamNo", ""))
                email_addr = str(row_dict.get("Email", "")).strip()
                name = str(row_dict.get("Name", ""))

                entry = {
                    "Name": name,
                    "Email": email_addr,
                    "ExamNo": exam_no,
                    "PDFGenerated": "N/A",
                    "EmailSent": False,
                    "Error": "",
                }

                # --- Build attachment based on job mode ---
                attachment_filename = None
                attachment_bytes = None

                if job_mode == "dynamic_pdf":
                    pdf_path = os.path.join(pdf_folder, f"{safe_filename(exam_no)}.pdf")
                    entry["PDFGenerated"] = os.path.isfile(pdf_path)

                    if not os.path.isfile(pdf_path):
                        entry["Error"] = "PDF not found"
                        task.emails_failed += 1
                        writer.writerow(entry)
                        log_file.flush()
                        task.progress = idx + 1
                        continue

                    with open(pdf_path, "rb") as f:
                        attachment_bytes = f.read()
                    attachment_filename = os.path.basename(pdf_path)

                elif job_mode == "static_attachment":
                    entry["PDFGenerated"] = "N/A"
                    if static_attachment_path and os.path.isfile(static_attachment_path):
                        with open(static_attachment_path, "rb") as f:
                            attachment_bytes = f.read()
                        attachment_filename = os.path.basename(static_attachment_path)

                else:  # email_only
                    entry["PDFGenerated"] = "N/A"

                # --- Render email content with placeholders ---
                subject_line = _render_subject(email_subject_tpl, row_dict)
                body_html = _render_body(email_body_tpl, row_dict, sig_name, sig_title)

                try:
                    message = EmailMessage(
                        from_name=from_name,
                        from_email=from_email,
                        to=email_addr,
                        subject=subject_line,
                        html=body_html,
                        attachment_filename=attachment_filename,
                        attachment_bytes=attachment_bytes,
                    )

                    provider.send(message)

                    entry["EmailSent"] = True
                    task.emails_sent += 1

                except Exception as e:
                    entry["Error"] = str(e)
                    task.emails_failed += 1

                writer.writerow(entry)
                log_file.flush()
                task.progress = idx + 1
                if not job.paused.get("emails", False):
                    task.phase = "sending"

                if (idx + 1) % 10 == 0 or (idx + 1) == len(data):
                    job.save()

        store.save_local_file(log_path)
        task.status = "complete"
        task.phase = "complete"
        job.save()

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        job.save()


def start_email_send(job: Job, provider: EmailProvider, from_name: str = "", from_email: str = ""):
    from app.models import TaskStatus
    data = job.valid_data if job.valid_data is not None else job.data
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["emails"] = TaskStatus(status="running", phase="sending", total=len(data))
    job.status = "running"
    job.save()
    thread = threading.Thread(
        target=run_email_send,
        args=(job, provider, from_name, from_email),
        daemon=True,
    )
    thread.start()
