import os
import re

import pandas as pd

from app.services.jobs import Job
from app import config


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def generate_report(job: Job) -> str:
    """
    Generate a delivery report using our own email send log.
    No external service logs needed — we track everything ourselves.
    """
    # Source 1: All candidates from the job
    candidates = job.data.copy()
    candidates = candidates.fillna("")
    candidates["_email_key"] = candidates["Email"].astype(str).str.strip().str.lower()

    # Source 2: Our own run log (written by email_tasks.py)
    run_log = pd.DataFrame()
    if job.log_path and os.path.isfile(job.log_path):
        run_log = pd.read_csv(job.log_path)
        run_log = run_log.fillna("")
        run_log["_email_key"] = run_log["Email"].astype(str).str.strip().str.lower()

    # Build delivery status from our log
    sent_emails = set()
    failed_emails = set()
    error_map = {}

    if not run_log.empty:
        for _, row in run_log.iterrows():
            key = row["_email_key"]
            email_sent = str(row.get("EmailSent", "")).strip().lower() == "true"
            if email_sent:
                sent_emails.add(key)
            else:
                failed_emails.add(key)
                error_msg = str(row.get("Error", ""))
                if error_msg:
                    error_map[key] = error_msg

    # Sheet 1: Successfully Sent
    sent = candidates[candidates["_email_key"].isin(sent_emails)].copy()

    # Sheet 2: Not Sent (in candidate list but not successfully sent)
    not_sent = candidates[~candidates["_email_key"].isin(sent_emails)].copy()

    # Sheet 3: Bad Emails (invalid format)
    is_bad = ~candidates["_email_key"].apply(lambda e: bool(EMAIL_RE.match(e)))
    bad_emails = candidates[is_bad].copy()
    bad_emails["Reason"] = "Invalid email format"

    # Sheet 4: Failed (attempted but errored)
    failed_df = candidates[candidates["_email_key"].isin(failed_emails)].copy()
    if not failed_df.empty:
        failed_df["Error"] = failed_df["_email_key"].map(error_map).fillna("")

    # Summary stats
    total = len(candidates)
    sent_count = len(sent)
    failed_count = len(failed_df)
    bad_count = len(bad_emails)
    not_attempted = total - sent_count - failed_count

    summary_data = {
        "Metric": [
            "Total Candidates",
            "Emails Sent Successfully",
            "Emails Failed",
            "Invalid Email Addresses",
            "Not Attempted",
        ],
        "Count": [total, sent_count, failed_count, bad_count, not_attempted],
    }
    summary_df = pd.DataFrame(summary_data)

    # Write report
    drop_key = lambda df: df.drop(columns=["_email_key"], errors="ignore")
    os.makedirs(config.LOG_FOLDER, exist_ok=True)
    report_path = os.path.join(config.LOG_FOLDER, f"report_{job.job_id}.xlsx")

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        drop_key(sent).to_excel(writer, sheet_name="Sent", index=False)
        drop_key(not_sent).to_excel(writer, sheet_name="Not Sent", index=False)
        drop_key(bad_emails).to_excel(writer, sheet_name="Bad Emails", index=False)
        drop_key(failed_df).to_excel(writer, sheet_name="Failed", index=False)

    return report_path
