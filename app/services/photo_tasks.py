import os
import re
import logging
import threading
import csv
import zipfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageOps

from app.services.jobs import Job
from app.services.storage import store
from app import config

logger = logging.getLogger(__name__)


MAX_DIMENSION = 800
JPEG_QUALITY = 85
DOWNLOAD_WORKERS = 4


def safe_filename(value):
    return re.sub(r'[\/\\:*?"<>|]', '-', str(value))


# ─── URL Handling ────────────────────────────────────────────────────────────

def _extract_google_drive_direct_url(url: str) -> str | None:
    """Convert a Google Drive share link to a direct download URL."""
    # Format: https://drive.google.com/file/d/FILE_ID/view
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    # Format: https://drive.google.com/open?id=FILE_ID
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return None


def _extract_dropbox_direct_url(url: str) -> str | None:
    """Convert a Dropbox share link to a direct download URL."""
    # Replace dl=0 with dl=1, or add dl=1
    if "dropbox.com" in url:
        if "dl=0" in url:
            return url.replace("dl=0", "dl=1")
        elif "dl=1" not in url:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}dl=1"
        return url
    return None


def _get_download_url(photo_url: str) -> str:
    """Convert any cloud storage share link to a direct download URL.

    Supports:
    - Google Drive (share links → direct download)
    - Dropbox (share links → dl=1)
    - OneDrive (share links → direct download)
    - Any direct image URL (returned as-is)
    """
    url = str(photo_url).strip()

    # Google Drive
    if "drive.google.com" in url:
        direct = _extract_google_drive_direct_url(url)
        if direct:
            return direct

    # Dropbox
    if "dropbox.com" in url:
        direct = _extract_dropbox_direct_url(url)
        if direct:
            return direct

    # OneDrive — replace "redir" with "download"
    if "onedrive.live.com" in url or "1drv.ms" in url:
        if "redir" in url:
            return url.replace("redir", "download")
        return url

    # Direct URL (anything that starts with http) — just use it as-is
    return url


# ─── Download & Process ──────────────────────────────────────────────────────

def download_and_save(photo_url, identifier, output_folder, cache_folder=None):
    """Download a photo from any URL, process it, and save as JPEG."""
    if not photo_url or not str(photo_url).strip().startswith("http"):
        return False, "No photo link"

    output_path = os.path.join(output_folder, f"{safe_filename(identifier)}.jpg")

    download_url = _get_download_url(photo_url)

    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0 (VolleyPacket Photo Downloader)"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            # Google Drive returns HTML for CAPTCHAs, virus scan pages, etc.
            if "text/html" in content_type and "drive.google.com" in download_url:
                return False, "Google Drive returned HTML (rate-limited or requires sign-in)"
            data = response.read()

        if len(data) < 100:
            return False, "Downloaded file too small (likely an error page)"

        with open(output_path, "wb") as f:
            f.write(data)

        # Try to process as image — resize and convert to JPEG
        try:
            with Image.open(output_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                if max(img.size) > MAX_DIMENSION:
                    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
                img.save(output_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        except Exception:
            # If it's not a valid image, keep the raw file but log the issue
            pass

        return True, ""
    except Exception as e:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False, str(e)


# ─── Main Task ───────────────────────────────────────────────────────────────

def run_photo_download(job: Job):
    task = job.tasks["photos"]

    try:
        data = job.data
        logger.info(f"[photo_dl] Job {job.job_id}: starting photo download — {len(data)} recipients")

        photo_folder = os.path.join(config.OUTPUT_FOLDER, f"photos_{job.job_id}")
        os.makedirs(photo_folder, exist_ok=True)
        os.makedirs(config.LOG_FOLDER, exist_ok=True)

        # Detect photo column name — flexible matching
        photo_col = None
        for col in data.columns:
            if col.lower() in ("photolink", "photourl", "photo_link", "photo_url", "photo", "image", "imageurl", "image_url", "picture", "headshot"):
                photo_col = col
                break

        if not photo_col:
            # Try columns containing "photo" or "image" in name
            for col in data.columns:
                if "photo" in col.lower() or "image" in col.lower():
                    photo_col = col
                    break

        if not photo_col:
            task.status = "failed"
            task.error = "No photo column found (expected PhotoLink, PhotoURL, Image, etc.)"
            job.update_status_from_tasks()
            job.save()
            return

        # Detect identifier column for filenames — prefer ExamNo, fall back to Name, then index
        id_col = None
        for col in data.columns:
            if col.lower() in ("examno", "exam_no", "id", "studentid", "student_id", "employeeid"):
                id_col = col
                break
        if not id_col:
            for col in data.columns:
                if col.lower() == "name":
                    id_col = col
                    break

        log_path = os.path.join(config.LOG_FOLDER, f"photo_download_{job.timestamp}.csv")
        with open(log_path, "w", newline="", encoding="utf-8") as log_file:
            writer = csv.DictWriter(
                log_file,
                fieldnames=["Identifier", "PhotoLink", "Downloaded", "Error"],
            )
            writer.writeheader()
            log_file.flush()

            # Process in batches for parallel download
            rows_list = list(data.iterrows())
            batch_size = DOWNLOAD_WORKERS * 2

            for batch_start in range(0, len(rows_list), batch_size):
                if job.should_stop("photos"):
                    task.status = "cancelled"
                    task.phase = "cancelled"
                    job.update_status_from_tasks()
                    job.save()
                    return

                batch = rows_list[batch_start:batch_start + batch_size]
                futures = {}

                with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
                    for idx_offset, (row_idx, row) in enumerate(batch):
                        row_dict = row.to_dict()
                        identifier = str(row_dict.get(id_col, row_idx)) if id_col else str(row_idx)
                        photo_url = str(row_dict.get(photo_col, ""))
                        future = executor.submit(
                            download_and_save, photo_url, identifier, photo_folder
                        )
                        futures[future] = (batch_start + idx_offset, identifier, photo_url)

                    for future in as_completed(futures):
                        if job.should_stop("photos"):
                            task.status = "cancelled"
                            task.phase = "cancelled"
                            job.update_status_from_tasks()
                            job.save()
                            return

                        _, identifier, photo_url = futures[future]

                        try:
                            success, error = future.result()
                        except Exception as e:
                            success, error = False, str(e)

                        if success:
                            task.photos_downloaded += 1
                        else:
                            task.photos_failed += 1

                        writer.writerow({
                            "Identifier": identifier,
                            "PhotoLink": photo_url, "Downloaded": success,
                            "Error": error,
                        })
                        log_file.flush()
                        task.progress = task.photos_downloaded + task.photos_failed

                        if task.progress % 10 == 0:
                            job.save()

        # ZIP the downloaded photos and upload to S3
        photos_in_folder = [f for f in os.listdir(photo_folder) if os.path.isfile(os.path.join(photo_folder, f))]
        if photos_in_folder:
            zip_path = os.path.join(config.OUTPUT_FOLDER, f"photos_{job.job_id}.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename in sorted(photos_in_folder):
                    zf.write(os.path.join(photo_folder, filename), filename)
            store.save_local_file(zip_path)
            logger.info(f"[photo_dl] Job {job.job_id}: zipped {len(photos_in_folder)} photos")

        store.save_local_file(log_path)
        task.status = "complete"
        task.phase = "complete"
        job.update_status_from_tasks()
        job.save()

        logger.info(f"[photo_dl] Job {job.job_id}: complete — {task.photos_downloaded} downloaded, {task.photos_failed} failed")

    except Exception as e:
        logger.exception(f"[photo_dl] Job {job.job_id}: CRASHED — {e}")
        task.status = "failed"
        task.error = str(e)
        try:
            job.update_status_from_tasks()
            job.save()
        except Exception:
            logger.error(f"[photo_dl] Job {job.job_id}: failed to save error state")


def start_photo_download(job: Job):
    from app.models import TaskStatus
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["photos"] = TaskStatus(status="running", phase="downloading", total=len(job.data))
    job.paused["photos"] = False  # clear stale pause from previous run
    job.status = "running"
    job.save()
    thread = threading.Thread(target=run_photo_download, args=(job,), daemon=True)
    thread.start()
