import os
import re
import threading
import csv
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image, ImageOps

from app.services.jobs import Job
from app.services.storage import store
from app import config


MAX_DIMENSION = 800
JPEG_QUALITY = 85
DOWNLOAD_WORKERS = 4


def safe_filename(value):
    return re.sub(r'[\/\\:*?"<>|]', '-', str(value))


def extract_file_id(url):
    if not isinstance(url, str):
        return None
    if "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    if "/d/" in url:
        return url.split("/d/")[-1].split("/")[0]
    return None


def download_and_save(photo_url, exam_no, output_folder, cache_folder=None):
    if not photo_url or not str(photo_url).startswith("http"):
        return False, "No photo link"

    file_id = extract_file_id(photo_url)
    if not file_id:
        return False, "Could not extract file ID"

    output_path = os.path.join(output_folder, f"{safe_filename(exam_no)}.jpg")

    # Check cache first (same photo ID already downloaded)
    if cache_folder:
        cached_path = os.path.join(cache_folder, f"{file_id}.jpg")
        if os.path.exists(cached_path):
            import shutil
            shutil.copy2(cached_path, output_path)
            return True, ""

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            # Google Drive returns HTML for CAPTCHAs, virus scan pages, etc.
            if "text/html" in content_type:
                return False, "Google Drive returned HTML (rate-limited or CAPTCHA)"
            data = response.read()

        with open(output_path, "wb") as f:
            f.write(data)

        with Image.open(output_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > MAX_DIMENSION:
                img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=JPEG_QUALITY, optimize=True)

        # Cache the processed photo
        if cache_folder:
            os.makedirs(cache_folder, exist_ok=True)
            import shutil
            shutil.copy2(output_path, os.path.join(cache_folder, f"{file_id}.jpg"))

        return True, ""
    except Exception as e:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False, str(e)


def run_photo_download(job: Job):
    task = job.tasks["photos"]
    data = job.data

    photo_folder = os.path.join(config.OUTPUT_FOLDER, f"photos_{job.job_id}")
    cache_folder = os.path.join(config.OUTPUT_FOLDER, f"photo_cache_{job.job_id}")
    os.makedirs(photo_folder, exist_ok=True)
    os.makedirs(cache_folder, exist_ok=True)
    os.makedirs(config.LOG_FOLDER, exist_ok=True)

    log_path = os.path.join(config.LOG_FOLDER, f"photo_download_{job.timestamp}.csv")

    try:
        with open(log_path, "w", newline="", encoding="utf-8") as log_file:
            writer = csv.DictWriter(
                log_file,
                fieldnames=["Name", "ExamNo", "PhotoLink", "Downloaded", "Error"],
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
                    job.save()
                    return

                batch = rows_list[batch_start:batch_start + batch_size]
                futures = {}

                with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as executor:
                    for idx_offset, (_, row) in enumerate(batch):
                        row_dict = row.to_dict()
                        exam_no = str(row_dict.get("ExamNo", ""))
                        photo_url = str(row_dict.get("PhotoLink", ""))
                        future = executor.submit(
                            download_and_save, photo_url, exam_no, photo_folder, cache_folder
                        )
                        futures[future] = (batch_start + idx_offset, row_dict)

                    for future in as_completed(futures):
                        if job.should_stop("photos"):
                            task.status = "cancelled"
                            task.phase = "cancelled"
                            job.save()
                            return

                        idx, row_dict = futures[future]
                        name = str(row_dict.get("Name", ""))
                        exam_no = str(row_dict.get("ExamNo", ""))
                        photo_url = str(row_dict.get("PhotoLink", ""))

                        try:
                            success, error = future.result()
                        except Exception as e:
                            success, error = False, str(e)

                        if success:
                            task.photos_downloaded += 1
                        else:
                            task.photos_failed += 1

                        writer.writerow({
                            "Name": name, "ExamNo": exam_no,
                            "PhotoLink": photo_url, "Downloaded": success,
                            "Error": error,
                        })
                        log_file.flush()
                        task.progress = task.photos_downloaded + task.photos_failed

                        if task.progress % 10 == 0:
                            job.save()

        # Clean up cache folder
        import shutil
        if os.path.exists(cache_folder):
            shutil.rmtree(cache_folder, ignore_errors=True)

        store.save_local_file(log_path)
        task.status = "complete"
        task.phase = "complete"
        job.save()

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        job.save()


def start_photo_download(job: Job):
    from app.models import TaskStatus
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["photos"] = TaskStatus(status="running", phase="downloading", total=len(job.data))
    job.status = "running"
    job.save()
    thread = threading.Thread(target=run_photo_download, args=(job,), daemon=True)
    thread.start()
