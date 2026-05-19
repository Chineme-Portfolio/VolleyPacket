import os
import csv
import threading

import resend

from app.services.jobs import Job
from app.services.generator import safe_filename
from app import config


def run_email_send(job: Job):
    task = job.tasks["emails"]
    data = job.valid_data if job.valid_data is not None else job.data
    task.total = len(data)
    task.status = "running"
    task.phase = "sending"

    pdf_folder = job.get_pdf_folder()

    os.makedirs(config.LOG_FOLDER, exist_ok=True)
    log_path = os.path.join(config.LOG_FOLDER, f"run_{job.timestamp}.csv")
    job.log_path = log_path

    resend.api_key = config.RESEND_API_KEY

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
                pdf_path = os.path.join(pdf_folder, f"{safe_filename(exam_no)}.pdf")

                entry = {
                    "Name": name,
                    "Email": email_addr,
                    "ExamNo": exam_no,
                    "PDFGenerated": os.path.isfile(pdf_path),
                    "EmailSent": False,
                    "Error": "",
                }

                if not os.path.isfile(pdf_path):
                    entry["Error"] = "PDF not found"
                    task.emails_failed += 1
                    writer.writerow(entry)
                    log_file.flush()
                    task.progress = idx + 1
                    continue

                try:
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()

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
                        <strong>{job.template.signature.name}</strong><br>
                        <em>{job.template.signature.title}</em></p>
                      </body>
                    </html>
                    """

                    resend.Emails.send({
                        "from": f"{config.SENDER_NAME} <{config.SENDER_EMAIL}>",
                        "to": [email_addr],
                        "subject": f"{job.template.subject} — {name}",
                        "html": body_html,
                        "attachments": [
                            {
                                "filename": os.path.basename(pdf_path),
                                "content": list(pdf_bytes),
                            }
                        ],
                    })

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


def start_email_send(job: Job):
    thread = threading.Thread(target=run_email_send, args=(job,), daemon=True)
    thread.start()
