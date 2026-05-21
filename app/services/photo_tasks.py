import os
import re
import threading
import csv
import urllib.request

from PIL import Image, ImageOps

from app.services.jobs import Job
from app.services.storage import store
from app import config


MAX_DIMENSION = 800
JPEG_QUALITY = 85


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


def download_and_save(photo_url, exam_no, output_folder):
    if not photo_url or not str(photo_url).startswith("http"):
        return False, "No photo link"

    file_id = extract_file_id(photo_url)
    if not file_id:
        return False, "Could not extract file ID"

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    output_path = os.path.join(output_folder, f"{safe_filename(exam_no)}.jpg")

    try:
        urllib.request.urlretrieve(download_url, output_path)
        with Image.open(output_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > MAX_DIMENSION:
                img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
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
    task.total = len(data)
    task.status = "running"
    task.phase = "downloading"

    photo_folder = os.path.join(config.OUTPUT_FOLDER, f"photos_{job.job_id}")
    os.makedirs(photo_folder, exist_ok=True)
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

            for idx, (_, row) in enumerate(data.iterrows()):
                if job.should_stop("photos"):
                    task.status = "cancelled"
                    task.phase = "cancelled"
                    job.save()
                    return

                row_dict = row.to_dict()
                name = str(row_dict.get("Name", ""))
                exam_no = str(row_dict.get("ExamNo", ""))
                photo_url = str(row_dict.get("PhotoLink", ""))

                success, error = download_and_save(photo_url, exam_no, photo_folder)

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
                task.progress = idx + 1

        store.save_local_file(log_path)
        task.status = "complete"
        task.phase = "complete"
        job.save()

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        job.save()


def start_photo_download(job: Job):
    thread = threading.Thread(target=run_photo_download, args=(job,), daemon=True)
    thread.start()
