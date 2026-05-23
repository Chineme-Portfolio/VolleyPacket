import os
import re
import csv
import threading

import pandas as pd
import requests

from app.services.jobs import Job
from app.services.storage import store
from app import config


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


def build_message(row):
    return (
        "Rivers State Government & Osalasi Company Limited\n"
        "SUBJECT: ALLOCATION OF COMPUTER-BASED TEST (CBT) EXAMINATION TIMETABLE\n"
        "Print your Examination Notification Letter from Your Email and Come With it to the exam Center"
    )


def build_detail_message(row):
    first_name = str(row.get("Name", "")).strip().split()[0].title()
    date = pd.to_datetime(row.get("ExamDate", "")).strftime("%a %d %b")
    time = str(row.get("ExamTime", "")).strip()
    hall = str(row.get("AssignedHall", "")).strip()
    exam_no = str(row.get("ExamNo", "")).strip()

    return (
        f"Dear {first_name}, Rivers State Govt CBT invitation (Osalasi Ltd):\n"
        f"Exam No: {exam_no}\n"
        f"Date: {date}\n"
        f"Exam Time: {time}\n"
        f"Hall: {hall}\n"
        f"Venue: ICTC, Ignatius Ajuru Uni of Education, Rumuolumeni, Port Harcourt.\n"
        f"Arrive 1hr early. Bring valid ID. Phones prohibited.\n"
        f"Enquiries: +234 803 451 3313\n"
        f"-Osalasi"
    )


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


def run_sms_send(job: Job, detailed: bool = False):
    task = job.tasks["sms"]
    data = job.data
    task.total = len(data)

    os.makedirs(config.LOG_FOLDER, exist_ok=True)
    log_path = os.path.join(config.LOG_FOLDER, f"sms_run_{job.timestamp}.csv")

    try:
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

                message = build_detail_message(row_dict) if detailed else build_message(row_dict)

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

        store.save_local_file(log_path)
        task.status = "complete"
        task.phase = "complete"
        job.save()

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        job.save()


def start_sms_send(job: Job, detailed: bool = False):
    job.tasks["sms"].status = "running"
    job.tasks["sms"].phase = "sending"
    job.status = "running"
    thread = threading.Thread(target=run_sms_send, args=(job, detailed), daemon=True)
    thread.start()
