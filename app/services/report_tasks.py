import os

import pandas as pd

from app.services.jobs import Job
from app.services.storage import store
from app import config


# Per-channel report config: (sheet name, log file prefix, success column in that log).
# The per-task logs are the source of truth — the report just presents them, so it
# stays accurate and automatically covers whatever tasks have completed.
_CHANNELS = [
    ("Email", "run", "EmailSent"),
    ("SMS", "sms_run", "Sent"),
    ("PDFs", "pdf_run", "PDFGenerated"),
    ("Photos", "photo_download", "Downloaded"),
]

_TRUTHY = {"true", "1", "yes", "y"}


def _read_csv_log(timestamp: str, prefix: str):
    """Read a task log CSV by its deterministic storage key; None if absent/unreadable."""
    key = f"logs/{prefix}_{timestamp}.csv"
    if not store.exists(key):
        return None
    try:
        return pd.read_csv(store.ensure_local(key)).fillna("")
    except Exception:
        return None


def _is_success(value) -> bool:
    return str(value).strip().lower() in _TRUTHY


def generate_report(job: Job) -> str:
    """Build a multi-channel delivery report (Summary + one sheet per channel) from each
    task's per-row log. Reads logs by `job.timestamp` (NOT `job.log_path`, which is None
    after a DB load — the old bug that dumped every successful send into 'Not Sent')."""
    summary_rows = []
    sheets = []  # list of (sheet_name, DataFrame)

    for sheet_name, prefix, status_col in _CHANNELS:
        df = _read_csv_log(job.timestamp, prefix)
        if df is None:
            continue
        attempted = len(df)
        successful = int(df[status_col].apply(_is_success).sum()) if status_col in df.columns else 0
        summary_rows.append({
            "Channel": sheet_name,
            "Attempted": attempted,
            "Successful": successful,
            "Failed": attempted - successful,
        })
        sheets.append((sheet_name, df))

    # Invalid emails filtered out before sending (written as .xlsx by validate_emails).
    invalid_key = f"logs/invalid_emails_{job.timestamp}.xlsx"
    if store.exists(invalid_key):
        try:
            invalid_df = pd.read_excel(store.ensure_local(invalid_key)).fillna("")
            if not invalid_df.empty:
                summary_rows.append({
                    "Channel": "Invalid Emails",
                    "Attempted": len(invalid_df),
                    "Successful": 0,
                    "Failed": len(invalid_df),
                })
                sheets.append(("Invalid Emails", invalid_df))
        except Exception:
            pass

    summary_df = pd.DataFrame(
        summary_rows or [{"Channel": "(no completed tasks yet)", "Attempted": 0, "Successful": 0, "Failed": 0}],
        columns=["Channel", "Attempted", "Successful", "Failed"],
    )

    os.makedirs(config.LOG_FOLDER, exist_ok=True)
    report_path = os.path.join(config.LOG_FOLDER, f"report_{job.job_id}.xlsx")
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        for sheet_name, df in sheets:
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    return report_path
