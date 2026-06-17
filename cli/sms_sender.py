# --- IMPORT ---
import os
import sys
import csv
import re
import argparse
from datetime import datetime

import pandas as pd
import requests
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()


# --- CONFIG ---
LOGS_FOLDER = "./logs"
# Use sandbox URL for testing without spending credits; switch to production when ready
BULKSMS_API_URL = "https://www.bulksmsnigeria.com/api/v2/sms"
# BULKSMS_API_URL = "https://www.bulksmsnigeria.com/api/sandbox/v2/sms"   # ← uncomment for free testing
BULKSMS_API_TOKEN = os.getenv("BULKSMS_API_TOKEN")

BREVO_API_URL = "https://api.brevo.com/v3/transactionalSMS/send"
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

SENDER_NAME = "Osalasi"  # max 11 alphanumeric chars


# --- ARG PARSING ---
def parse_args():
    parser = argparse.ArgumentParser(
        description="VolleyPacket SMS — send exam reminders via Brevo."
    )
    parser.add_argument("input_file", help="Path to the allocated Excel file.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Build SMS messages but do not actually send them."
    )
    parser.add_argument(
    "--detailed", action="store_true",
    help="Send the longer detailed SMS (for candidates who didn't receive email)."
    )
    return parser.parse_args()


# --- HELPERS ---
def normalize_phone(raw):
    if pd.isna(raw):
        return []

    # Split on common separators candidates actually use
    parts = re.split(r'[,/;]', str(raw))

    normalized = []
    for part in parts:
        phone = part.strip().replace(" ", "").replace("-", "").replace("+", "")
        if not phone.isdigit():
            continue
        # Local format: 11 digits starting with 0
        if len(phone) == 11 and phone.startswith("0"):
            normalized.append("234" + phone[1:])
        # International format: 13 digits starting with 234
        elif len(phone) == 13 and phone.startswith("234"):
            normalized.append(phone)
        # 10 digits missing leading 0
        elif len(phone) == 10 and phone.startswith(("7", "8", "9")):
            normalized.append("234" + phone)

    # Deduplicate — sometimes people enter the same number twice by accident
    return list(dict.fromkeys(normalized))


def build_message(row):
    """Reminder SMS for all candidates — prompts them to print their email notification."""
    msg = (
        "Rivers State Government & Osalasi Company Limited\n"
        "SUBJECT: ALLOCATION OF COMPUTER-BASED TEST (CBT) EXAMINATION TIMETABLE\n"
        "Print your Examination Notification Letter from Your Email and Come With it to the exam Center"
    )
    return msg

def build_detail_message(row):
    """Detailed SMS for candidates who did not receive the email."""
    first_name = str(row["Name"]).strip().split()[0].title()
    date = pd.to_datetime(row["ExamDate"]).strftime("%a %d %b")
    time = str(row["ExamTime"]).strip()
    hall = str(row["AssignedHall"]).strip()
    exam_no = str(row["ExamNo"]).strip()

    msg = (
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
    return msg


def send_sms(phone, message):
    headers = {
        "Authorization": f"Bearer {BULKSMS_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "from": SENDER_NAME,
        "to": phone,
        "body": message,
    }
    try:
        response = requests.post(BULKSMS_API_URL, json=payload, headers=headers, timeout=30)
        data = response.json()
        if data.get("status") == "success":
            return True, ""
        else:
            error = data.get("error", {}).get("message") or data.get("message", "Unknown error")
            code = data.get("code", "")
            return False, f"{code}: {error}"
    except Exception as e:
        return False, str(e)


# --- MAIN LOOP ---
def process_rows(data, dry_run, log_path, detailed=False):
    sent_count = 0
    failed_count = 0
    skipped_count = 0

    with open(log_path, "w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=["Name", "PhoneNumber", "NormalizedPhone", "ExamNo", "Message", "Sent", "Error"],
        )
        writer.writeheader()
        log_file.flush()

        for _, row in tqdm(data.iterrows(), total=len(data), desc="Sending SMS"):
            name = str(row.get("Name", ""))
            exam_no = str(row.get("ExamNo", ""))
            raw_phone = row.get("PhoneNumber", "")
            numbers = normalize_phone(raw_phone)

            # Skip if no usable numbers found
            if not numbers:
                entry = {
                    "Name": name,
                    "PhoneNumber": raw_phone,
                    "NormalizedPhone": "",
                    "ExamNo": exam_no,
                    "Message": "",
                    "Sent": False,
                    "Error": "Invalid or missing phone number",
                }
                skipped_count += 1
                writer.writerow(entry)
                log_file.flush()
                continue

            # Build the message once per candidate
            try:
                message = build_detail_message(row) if detailed else build_message(row)
            except Exception as e:
                entry = {
                    "Name": name,
                    "PhoneNumber": raw_phone,
                    "NormalizedPhone": ", ".join(numbers),
                    "ExamNo": exam_no,
                    "Message": "",
                    "Sent": False,
                    "Error": f"Message build error: {e}",
                }
                failed_count += 1
                writer.writerow(entry)
                log_file.flush()
                continue

            # Send to each number separately
            for phone in numbers:
                entry = {
                    "Name": name,
                    "PhoneNumber": raw_phone,
                    "NormalizedPhone": phone,
                    "ExamNo": exam_no,
                    "Message": message,
                    "Sent": False,
                    "Error": "",
                }

                if dry_run:
                    entry["Error"] = "DRY RUN — not sent"
                else:
                    success, error = send_sms(phone, message)
                    entry["Sent"] = success
                    entry["Error"] = error
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1

                writer.writerow(entry)
                log_file.flush()

    return sent_count, failed_count, skipped_count


# --- MAIN ---
def main():
    args = parse_args()

    if not BULKSMS_API_TOKEN:
        print("Error: BULKSMS_API_TOKEN not set in .env file.")
        sys.exit(1)

    if not os.path.isfile(args.input_file):
        print(f"Error: input file not found: {args.input_file}")
        sys.exit(1)

    os.makedirs(LOGS_FOLDER, exist_ok=True)

    if args.dry_run:
        print("DRY-RUN mode — SMS messages will NOT be sent.")
    if args.detailed:
        print("DETAILED mode — longer message will be sent.")

    # Load allocated data
    print(f"Loading allocated data from {args.input_file}...")
    data = pd.read_excel(args.input_file, engine='openpyxl')
    data = data.rename(columns={'Phone Number': 'PhoneNumber'})
    print(f"Loaded {len(data)} candidates.")

    # Sanity check — verify the expected columns exist
    required_cols = {"Name", "PhoneNumber", "ExamNo", "ExamDate", "ExamTime"}
    missing = required_cols - set(data.columns)
    if missing:
        print(f"Error: missing required columns in input: {missing}")
        sys.exit(1)

    # Set up log
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOGS_FOLDER, f"sms_run_{timestamp}.csv")
    print(f"Writing SMS log to {log_path}")

    # Process
    sent_count, failed_count, skipped_count = process_rows(
        data, args.dry_run, log_path, detailed=args.detailed
    )

    # Summary
    total = len(data)
    print("\n--- Summary ---")
    print(f"  Total candidates         : {total}")
    if args.dry_run:
        print(f"  Messages prepared        : {total - skipped_count}")
        print(f"  Skipped (bad phones)     : {skipped_count}")
        print("  SMS                      : none sent (dry-run)")
    else:
        print(f"  SMS sent successfully    : {sent_count}")
        print(f"  SMS failed               : {failed_count}")
        print(f"  Skipped (bad phones)     : {skipped_count}")
    print(f"  Log file                 : {log_path}")


if __name__ == "__main__":
    main()