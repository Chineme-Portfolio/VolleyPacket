import os
import csv
import logging
import threading

from app.services.jobs import Job
from app.services.generator import safe_filename
from app.services.email_providers import EmailProvider, EmailMessage
from app.services.storage import store, _key_from_local
from app.services.codes import expand_codes
from app import config

logger = logging.getLogger(__name__)


def _render_body(template_html: str, row_dict: dict) -> str:
    """Replace {Column} placeholders in the email body with row values."""
    body = template_html
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

    try:
        data = job.valid_data if job.valid_data is not None else job.data
        logger.info(f"[email_send] Job {job.job_id}: starting email send — {len(data)} recipients")

        job_mode = getattr(job, "job_mode", "dynamic_pdf")
        pdf_folder = job.get_pdf_folder() if job_mode == "dynamic_pdf" else None
        static_attachment_path = getattr(job, "static_attachment_path", None)

        # Email content — use job's custom content or defaults
        email_subject_tpl = getattr(job, "email_subject", "") or "Message for {Name}"
        # Use the job's email content verbatim — never a hardcoded generic message.
        # The /emails/send route guarantees this is non-empty before the task starts.
        email_body_tpl = job.email_body or ""

        os.makedirs(config.LOG_FOLDER, exist_ok=True)
        log_path = os.path.join(config.LOG_FOLDER, f"run_{job.timestamp}.csv")
        job.log_path = log_path

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
                    job.update_status_from_tasks()
                    job.save()
                    logger.info(f"[email_send] Job {job.job_id}: cancelled at {idx}/{len(data)}")
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
                    # Use same column priority as PDF generator for filename lookup
                    file_id = None
                    for col in ["Name", "ExamNo", "Email", "ID", "Id", "id"]:
                        if col in row_dict and row_dict[col]:
                            file_id = str(row_dict[col])
                            break
                    if not file_id:
                        file_id = f"recipient_{idx + 1}"
                    pdf_path = os.path.join(pdf_folder, f"{safe_filename(file_id)}.pdf")

                    # Try local first, fall back to S3 download
                    if not os.path.isfile(pdf_path):
                        try:
                            store.ensure_local(_key_from_local(pdf_path))
                        except Exception:
                            pass  # still not found — handled below

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
                body_html = _render_body(email_body_tpl, row_dict)
                # Expand {QR:…}/{BARCODE:…} into hosted code images (clients block data: images).
                body_html = expand_codes(body_html, row_dict, mode="url", base_url=config.PUBLIC_API_URL)

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
                    logger.warning(f"[email_send] Job {job.job_id}: failed to send to {email_addr}: {e}")

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
        job.update_status_from_tasks()
        job.save()
        logger.info(f"[email_send] Job {job.job_id}: complete — {task.emails_sent} sent, {task.emails_failed} failed")

    except Exception as e:
        logger.exception(f"[email_send] Job {job.job_id}: CRASHED — {e}")
        task.status = "failed"
        task.error = str(e)
        try:
            job.update_status_from_tasks()
            job.save()
        except Exception:
            logger.error(f"[email_send] Job {job.job_id}: failed to save error state")


def start_email_send(job: Job, provider: EmailProvider, from_name: str = "", from_email: str = ""):
    from app.models import TaskStatus
    data = job.valid_data if job.valid_data is not None else job.data
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["emails"] = TaskStatus(status="running", phase="sending", total=len(data))
    job.paused["emails"] = False  # clear stale pause from previous run
    job.status = "running"
    job.save()
    thread = threading.Thread(
        target=run_email_send,
        args=(job, provider, from_name, from_email),
        daemon=True,
    )
    thread.start()
