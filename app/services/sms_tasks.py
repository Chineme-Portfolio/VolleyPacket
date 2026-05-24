import os
import re
import csv
import logging
import threading

import pandas as pd
import requests

from app.services.jobs import Job
from app.services.storage import store
from app import config

logger = logging.getLogger(__name__)


def normalize_phone(raw):
    if pd.isna(raw):
        return []
    parts = re.split(r'[,/;]', str(raw))
    normalized = []
    for part in parts:
        phone = part.strip().replace(" ", "").replace("-", "").replace("+", "")
        if not phone.isdigit():
            continue
        if len(phone) == 11 and phone.startswith("0"):
            normalized.append("234" + phone[1:])
        elif len(phone) == 13 and phone.startswith("234"):
            normalized.append(phone)
        elif len(phone) == 10 and phone.startswith(("7", "8", "9")):
            normalized.append("234" + phone)
    return list(dict.fromkeys(normalized))


DEFAULT_SMS_BODY = "Dear {Name}, this is a notification regarding your application. Please check your email for further details."


def render_sms(template: str, row: dict) -> str:
    """Replace {Placeholder} tokens in SMS body with row values."""
    message = template
    for key, val in row.items():
        message = message.replace(f"{{{key}}}", str(val))
    return message


def send_one_sms(phone, message):
    headers = {
        "Authorization": f"Bearer {config.BULKSMS_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"from": "Osalasi", "to": phone, "body": message}
    try:
        resp = requests.post(config.BULKSMS_API_URL, json=payload, headers=headers, timeout=30)
        data = resp.json()
        if data.get("status") == "success":
            return True, ""
        error = data.get("error", {}).get("message") or data.get("message", "Unknown error")
        return False, f"{data.get('code', '')}: {error}"
    except Exception as e:
        return False, str(e)


def run_sms_send(job: Job):
    task = job.tasks["sms"]

    try:
        if not config.BULKSMS_API_TOKEN:
            raise ValueError("BULKSMS_API_TOKEN is not configured — set it in environment variables")

        data = job.data
        logger.info(f"[sms_send] Job {job.job_id}: starting SMS send — {len(data)} recipients")

        sms_template = getattr(job, "sms_body", "") or DEFAULT_SMS_BODY

        os.makedirs(config.LOG_FOLDER, exist_ok=True)
        log_path = os.path.join(config.LOG_FOLDER, f"sms_run_{job.timestamp}.csv")
        with open(log_path, "w", newline="", encoding="utf-8") as log_file:
            writer = csv.DictWriter(
                log_file,
                fieldnames=["Name", "PhoneNumber", "NormalizedPhone", "ExamNo", "Sent", "Error"],
            )
            writer.writeheader()
            log_file.flush()

            for idx, (_, row) in enumerate(data.iterrows()):
                if job.should_stop("sms"):
                    task.status = "cancelled"
                    task.phase = "cancelled"
                    job.save()
                    return

                row_dict = row.to_dict()
                name = str(row_dict.get("Name", ""))
                exam_no = str(row_dict.get("ExamNo", ""))
                raw_phone = row_dict.get("PhoneNumber", "")
                numbers = normalize_phone(raw_phone)

                if not numbers:
                    writer.writerow({
                        "Name": name, "PhoneNumber": raw_phone,
                        "NormalizedPhone": "", "ExamNo": exam_no,
                        "Sent": False, "Error": "Invalid or missing phone number",
                    })
                    log_file.flush()
                    task.sms_skipped += 1
                    task.progress = idx + 1
                    continue

                message = render_sms(sms_template, row_dict)

                for phone in numbers:
                    success, error = send_one_sms(phone, message)
                    writer.writerow({
                        "Name": name, "PhoneNumber": raw_phone,
                        "NormalizedPhone": phone, "ExamNo": exam_no,
                        "Sent": success, "Error": error,
                    })
                    log_file.flush()

                    if success:
                        task.sms_sent += 1
                    else:
                        task.sms_failed += 1

                task.progress = idx + 1

                if (idx + 1) % 10 == 0 or (idx + 1) == len(data):
                    job.save()

        store.save_local_file(log_path)
        task.status = "complete"
        task.phase = "complete"
        job.save()

        logger.info(f"[sms_send] Job {job.job_id}: complete — {task.sms_sent} sent, {task.sms_failed} failed, {task.sms_skipped} skipped")

    except Exception as e:
        logger.exception(f"[sms_send] Job {job.job_id}: CRASHED — {e}")
        task.status = "failed"
        task.error = str(e)
        try:
            job.save()
        except Exception:
            logger.error(f"[sms_send] Job {job.job_id}: failed to save error state")


def start_sms_send(job: Job):
    from app.models import TaskStatus
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["sms"] = TaskStatus(status="running", phase="sending", total=len(job.data))
    job.paused["sms"] = False  # clear stale pause from previous run
    job.status = "running"
    job.save()
    thread = threading.Thread(target=run_sms_send, args=(job,), daemon=True)
    thread.start()
