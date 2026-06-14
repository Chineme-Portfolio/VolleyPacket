import os
import csv
import logging
import threading

from app.services.jobs import Job
from app.services.storage import store
from app.services.sms_providers import SmsMessage, to_e164
from app.services.sms_providers.base import SmsProvider
from app import config

logger = logging.getLogger(__name__)


def render_sms(template: str, row: dict) -> str:
    """Replace {Placeholder} tokens in SMS body with row values."""
    message = template
    for key, val in row.items():
        message = message.replace(f"{{{key}}}", str(val))
    return message


def run_sms_send(job: Job, provider: SmsProvider, sender_id: str, default_region: str = "NG"):
    task = job.tasks["sms"]

    try:
        data = job.data
        logger.info(f"[sms_send] Job {job.job_id}: starting SMS send via {provider.name} — {len(data)} recipients")

        # Use the job's SMS content verbatim — the /sms/send route guarantees it's non-empty.
        sms_template = job.sms_body or ""

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
                    job.update_status_from_tasks()
                    job.save()
                    return

                row_dict = row.to_dict()
                name = str(row_dict.get("Name", ""))
                exam_no = str(row_dict.get("ExamNo", ""))
                raw_phone = row_dict.get("PhoneNumber", "")
                numbers = to_e164(raw_phone, default_region)  # multi-country → canonical E.164

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
                    try:
                        provider.send(SmsMessage(to=phone, body=message, sender_id=sender_id))
                        success, error = True, ""
                    except Exception as e:
                        success, error = False, str(e)
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
        job.update_status_from_tasks()
        job.save()

        logger.info(f"[sms_send] Job {job.job_id}: complete — {task.sms_sent} sent, {task.sms_failed} failed, {task.sms_skipped} skipped")

    except Exception as e:
        logger.exception(f"[sms_send] Job {job.job_id}: CRASHED — {e}")
        task.status = "failed"
        task.error = str(e)
        try:
            job.update_status_from_tasks()
            job.save()
        except Exception:
            logger.error(f"[sms_send] Job {job.job_id}: failed to save error state")


def start_sms_send(job: Job, provider: SmsProvider, sender_id: str, default_region: str = "NG"):
    from app.models import TaskStatus
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["sms"] = TaskStatus(status="running", phase="sending", total=len(job.data))
    job.paused["sms"] = False  # clear stale pause from previous run
    job.status = "running"
    job.save()
    thread = threading.Thread(
        target=run_sms_send, args=(job, provider, sender_id, default_region), daemon=True
    )
    thread.start()
