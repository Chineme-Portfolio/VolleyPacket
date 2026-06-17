# --- IMPORT ---
import os
import sys
import re
import glob
import argparse

import pandas as pd


# --- CONFIG ---
LOGS_FOLDER = "./logs"
DEFAULT_CANDIDATES = "./data/allocated_exam_schedule.xlsx"
DEFAULT_OUTPUT = "./volley_packet_report.xlsx"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# --- ARG PARSING ---
def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a post-send report comparing candidates, Brevo logs, and local run logs."
    )
    parser.add_argument(
        "brevo_log", help="Path to the Brevo delivery log CSV."
    )
    parser.add_argument(
        "--candidates", default=DEFAULT_CANDIDATES,
        help=f"Path to the candidate spreadsheet (default: {DEFAULT_CANDIDATES})."
    )
    parser.add_argument(
        "--logs-folder", default=LOGS_FOLDER,
        help=f"Folder containing run_*.csv files (default: {LOGS_FOLDER})."
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT,
        help=f"Output report path (default: {DEFAULT_OUTPUT})."
    )
    return parser.parse_args()


# --- LOADERS ---
def load_candidates(path):
    df = pd.read_excel(path)
    df = df.fillna("")
    df["_email_key"] = df["Email"].astype(str).str.strip().str.lower()
    return df


def load_brevo_log(path):
    df = pd.read_csv(path)
    df = df.fillna("")
    df["_email_key"] = df["email"].astype(str).str.strip().str.lower()
    success = df[df["st_text"].str.strip().str.lower().isin(["sent", "delivered"])]
    return set(success["_email_key"].unique())


def load_run_logs(logs_folder):
    pattern = os.path.join(logs_folder, "run_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        return pd.DataFrame()

    frames = []
    for f in files:
        try:
            frames.append(pd.read_csv(f))
        except Exception as e:
            print(f"  Warning: could not read {f}: {e}")

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = df.fillna("")
    df["_email_key"] = df["Email"].astype(str).str.strip().str.lower()
    return df


# --- REPORT LOGIC ---
def build_report(candidates, brevo_success, run_logs):
    # --- Sheet 1: Sent ---
    sent = candidates[candidates["_email_key"].isin(brevo_success)].copy()

    # --- Sheet 2: Missing ---
    missing = candidates[~candidates["_email_key"].isin(brevo_success)].copy()

    # --- Sheet 3: Bad Emails ---
    is_bad = ~candidates["_email_key"].apply(lambda e: bool(EMAIL_RE.match(e)))
    bad_emails = candidates[is_bad].copy()
    bad_emails["Reason"] = "Invalid email format"

    # --- Sheet 4: Failed Locally ---
    failed_locally = pd.DataFrame()
    if not run_logs.empty:
        pdf_ok = run_logs[run_logs["PDFGenerated"].astype(str).str.strip().str.lower() == "true"]
        not_delivered = pdf_ok[~pdf_ok["_email_key"].isin(brevo_success)]

        if not not_delivered.empty:
            deduped = not_delivered.sort_index().drop_duplicates(subset="_email_key", keep="last")
            error_map = deduped.set_index("_email_key")["Error"]
            failed_locally = candidates[candidates["_email_key"].isin(deduped["_email_key"])].copy()
            failed_locally["Error"] = failed_locally["_email_key"].map(error_map).fillna("")

    return sent, missing, bad_emails, failed_locally


# --- MAIN ---
def main():
    args = parse_args()

    if not os.path.isfile(args.candidates):
        print(f"Error: candidates file not found: {args.candidates}")
        sys.exit(1)

    if not os.path.isfile(args.brevo_log):
        print(f"Error: Brevo log not found: {args.brevo_log}")
        sys.exit(1)

    print(f"Loading candidates from {args.candidates}...")
    candidates = load_candidates(args.candidates)
    print(f"  {len(candidates)} candidates loaded.")

    print(f"Loading Brevo delivery log from {args.brevo_log}...")
    brevo_success = load_brevo_log(args.brevo_log)
    print(f"  {len(brevo_success)} unique emails confirmed sent/delivered.")

    print(f"Loading local run logs from {args.logs_folder}/run_*.csv...")
    run_logs = load_run_logs(args.logs_folder)
    print(f"  {len(run_logs)} total log entries loaded.")

    sent, missing, bad_emails, failed_locally = build_report(candidates, brevo_success, run_logs)

    # Drop internal key column before writing
    drop_key = lambda df: df.drop(columns=["_email_key"], errors="ignore")

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        drop_key(sent).to_excel(writer, sheet_name="Sent", index=False)
        drop_key(missing).to_excel(writer, sheet_name="Missing", index=False)
        drop_key(bad_emails).to_excel(writer, sheet_name="Bad Emails", index=False)
        drop_key(failed_locally).to_excel(writer, sheet_name="Failed Locally", index=False)

    print(f"\nReport saved to {args.output}")
    print("\n--- Summary ---")
    print(f"  Sent             : {len(sent)}")
    print(f"  Missing          : {len(missing)}")
    print(f"  Bad Emails       : {len(bad_emails)}")
    print(f"  Failed Locally   : {len(failed_locally)}")


if __name__ == "__main__":
    main()
