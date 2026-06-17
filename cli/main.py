# --- IMPORT ---
import os
import sys
import csv
import shutil
import argparse
import re
from datetime import datetime
import pandas as pd
from tqdm import tqdm

from function.read_data import load_data
from function.allocator import (
    generate_combination_slots,
    allocate_combinations,
    assign_numbers,
    CAPACITY_PER_SLOT,
)
from function.generator import generate_pdf, safe_filename
from function.mailer import send_email


# --- CONFIG ---
PDF_FOLDER = "./pdf"
TEMP_FOLDER = "./temp"
LOG_FOLDER = "./logs"
ALLOCATED_OUTPUT = "./data/allocated_exam_schedule.xlsx"


# --- ARG PARSING ---
def parse_args():
    parser = argparse.ArgumentParser(
        description="VolleyPacket — generate and send exam invitations."
    )
    parser.add_argument("input_file", help="Path to the input Excel file.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate PDFs but do not send emails."
    )
    parser.add_argument(
        "--allocated", action="store_true",
        help="Skip the allocator — input file is already allocated."
    )
    return parser.parse_args()


# --- SETUP ---
def setup_folders():
    for folder in (PDF_FOLDER, TEMP_FOLDER, LOG_FOLDER, "./data"):
        os.makedirs(folder, exist_ok=True)


def clean_temp():
    if os.path.exists(TEMP_FOLDER):
        shutil.rmtree(TEMP_FOLDER)
    os.makedirs(TEMP_FOLDER, exist_ok=True)


# --- ALLOCATION ---
def run_allocator(data):
    print("Allocating exam slots...")
    pool = generate_combination_slots() * CAPACITY_PER_SLOT
    allocated = allocate_combinations(data, pool)
    allocated = assign_numbers(allocated)
    allocated.to_excel(ALLOCATED_OUTPUT, index=False)
    print(f"Allocation complete — saved to {ALLOCATED_OUTPUT}")
    return allocated


# --- CORE PROCESSING WITH INCREMENTAL LOGGING ---
def process_rows(data, dry_run, log_path):
    pdfs_ok = 0
    emails_sent = 0
    emails_failed = 0

    # Open the log file and write the header immediately
    with open(log_path, "w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=["Name", "Email", "ExamNo", "PDFGenerated", "EmailSent", "Error"],
        )
        writer.writeheader()
        log_file.flush()

        for _, row in tqdm(data.iterrows(), total=len(data), desc="Processing candidates"):
            entry = {
                "Name": row["Name"],
                "Email": row["Email"],
                "ExamNo": row["ExamNo"],
                "PDFGenerated": False,
                "EmailSent": False,
                "Error": "",
            }

            # 1. Generate PDF
            pdf_path = f"{PDF_FOLDER}/{safe_filename(str(row['ExamNo']))}.pdf"
            try:
                generate_pdf(row, PDF_FOLDER)
                entry["PDFGenerated"] = True
                pdfs_ok += 1
            except Exception as e:
                entry["Error"] = f"PDF: {e}"
                writer.writerow(entry)
                log_file.flush()
                continue

            # 2. Send email (unless dry-run)
            if not dry_run:
                try:
                    if send_email(row, pdf_path):
                        entry["EmailSent"] = True
                        emails_sent += 1
                    else:
                        emails_failed += 1
                        entry["Error"] = "Email send returned False"
                except Exception as e:
                    emails_failed += 1
                    entry["Error"] = f"Email: {e}"

            # 3. Write this row to the log immediately
            writer.writerow(entry)
            log_file.flush()

    return pdfs_ok, emails_sent, emails_failed

# --- EMAIL VALIDATION ---
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_emails(data):
    """Split the DataFrame into (valid, invalid) based on email format."""
    emails = data["Email"].astype(str).str.strip()
    is_valid = emails.apply(lambda e: bool(EMAIL_RE.match(e)))

    valid_rows = data[is_valid].copy()
    invalid_rows = data[~is_valid].copy()
    invalid_rows["Reason"] = "Invalid email format"

    return valid_rows, invalid_rows


def save_invalid_rows(invalid_rows, timestamp):
    """Write invalid rows to an Excel file in the logs folder."""
    if invalid_rows.empty:
        return None
    path = os.path.join(LOG_FOLDER, f"invalid_emails_{timestamp}.xlsx")
    invalid_rows.to_excel(path, index=False)
    return path

# --- MAIN ---
def main():
    args = parse_args()

    if not os.path.isfile(args.input_file):
        print(f"Error: input file not found: {args.input_file}")
        sys.exit(1)

    setup_folders()

    if args.dry_run:
        print("DRY-RUN mode — emails will NOT be sent.")

    # 1. Load data
    print(f"Loading data from {args.input_file}...")
    if args.allocated:
        print("Skipping allocator — input is pre-allocated.")
        data = pd.read_excel(args.input_file)
    else:
        data = load_data(args.input_file)
        data = run_allocator(data)

    print(f"Loaded {len(data)} candidates.")

    # Set timestamp now so all log files from this run share it
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 2. Validate emails — separate valid from invalid
    valid_data, invalid_data = validate_emails(data)
    if not invalid_data.empty:
        invalid_path = save_invalid_rows(invalid_data, timestamp)
        print(f"Filtered out {len(invalid_data)} invalid emails → {invalid_path}")
    else:
        print("All emails passed validation.")

    print(f"Proceeding with {len(valid_data)} valid candidates.")

    # 3. Set up incremental log file
    log_path = os.path.join(LOG_FOLDER, f"run_{timestamp}.csv")
    print(f"Writing run log to {log_path}")


    # 3. Process rows (PDF + email + incremental log)
    pdfs_ok, emails_sent, emails_failed = process_rows(valid_data, args.dry_run, log_path)

    # 4. Clean up temp photos
    clean_temp()

    # 5. Summary
    total = len(valid_data)
    print("\n--- Summary ---")
    print(f"  Valid candidates  : {total}")
    print(f"  Filtered out      : {len(invalid_data)}")
    print(f"  PDFs generated    : {pdfs_ok} / {total}")
    if args.dry_run:
        print("  Emails          : skipped (dry-run)")
    else:
        print(f"  Emails sent     : {emails_sent}")
        print(f"  Emails failed   : {emails_failed}")
    print(f"  Log file        : {log_path}")


if __name__ == "__main__":
    main()