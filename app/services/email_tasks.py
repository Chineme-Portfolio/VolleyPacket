import os
import csv
import threading

from app.services.jobs import Job
from app.services.generator import safe_filename
from app.services.email_providers import EmailProvider, EmailMessage
from app import config


def run_email_send(job: Job, provider: EmailProvider, from_name: str, from_email: str):
    task = job.tasks["emails"]
    data = job.valid_data if job.valid_data is not None else job.data
    task.total = len(data)
    task.status = "running"
    task.phase = "sending"

    job_mode = getattr(job, "job_mode", "dynamic_pdf")
    pdf_folder = job.get_pdf_folder() if job_mode == "dynamic_pdf" else None
    static_attachment_path = getattr(job, "static_attachment_path", None)

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

                # --- Build the email based on job mode ---
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

                # --- Build email body ---
                if job.template and job.template.signature:
                    sig_name = job.template.signature.name
                    sig_title = job.template.signature.title
                    subject_line = f"{job.template.subject} — {name}" if job.template.subject else f"Message for {name}"
                else:
                    sig_name = from_name
                    sig_title = ""
                    subject_line = f"Message for {name}"

                body_html = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; color: #2C2C2C; line-height: 1.5;">
                    <p>Dear {name},</p>
                    <p>Please find attached your examination invitation letter with all details
                    including your assigned date, time slot, hall, and examination centre.</p>
                    <p>Please download, print, and bring the attached letter to the examination venue
                    along with a valid means of identification.</p>
                    <p>We wish you success.</p>
                    <p>Yours faithfully,<br>
                    <strong>{sig_name}</strong><br>
                    <em>{sig_title}</em></p>
                  </body>
                </html>
                """

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
                task.phase = "sending"

        task.status = "complete"
        task.phase = "complete"
        job.save()

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        job.save()


def start_email_send(job: Job, provider: EmailProvider, from_name: str = "", from_email: str = ""):
    thread = threading.Thread(
        target=run_email_send,
        args=(job, provider, from_name, from_email),
        daemon=True,
    )
    thread.start()
