import os
import logging
import zipfile
import threading

from app.services.jobs import Job
from app.services.template_renderer import render_pdf
from app.services.generator import safe_filename, download_photo
from app.services.storage import store
from app import config

logger = logging.getLogger(__name__)


def run_pdf_generation(job: Job):
    task = job.tasks["pdfs"]

    try:
        data = job.valid_data if job.valid_data is not None else job.data
        logger.info(f"[pdf_gen] Job {job.job_id}: starting PDF generation — {len(data)} recipients")

        pdf_folder = job.get_pdf_folder()  # also restores from S3/ZIP if empty
        temp_folder = os.path.join(config.OUTPUT_FOLDER, f"temp_{job.job_id}")
        os.makedirs(temp_folder, exist_ok=True)

        skipped = 0
        for idx, (_, row) in enumerate(data.iterrows()):
            if job.should_stop("pdfs"):
                task.status = "cancelled"
                task.phase = "cancelled"
                job.save()
                return

            row_dict = row.to_dict()

            # Use first available identifier column for filename, fallback to index
            file_id = None
            for col in ["Name", "ExamNo", "Email", "ID", "Id", "id"]:
                if col in row_dict and row_dict[col]:
                    file_id = str(row_dict[col])
                    break
            if not file_id:
                file_id = f"recipient_{idx + 1}"
            output_path = os.path.join(pdf_folder, f"{safe_filename(file_id)}.pdf")

            # Skip if PDF already exists (restored from S3/ZIP or previous partial run)
            if os.path.isfile(output_path):
                skipped += 1
            else:
                # Check for photo URL in any photo-related column
                photo_path = None
                for col in ["PhotoLink", "PhotoURL", "Photo", "photo_url", "photo"]:
                    photo_url = row_dict.get(col, "")
                    if photo_url and str(photo_url).startswith("http"):
                        photo_path = download_photo(str(photo_url), temp_folder)
                        break

                render_pdf(job.template, row_dict, output_path, photo_path=photo_path)

                # Upload individual PDF to S3 so email task can find it after redeploy
                store.save_local_file(output_path)

                if photo_path and os.path.exists(photo_path):
                    os.remove(photo_path)

                if not job.paused.get("pdfs", False):
                    task.phase = "generating"

            # Progress tracking runs for BOTH skipped and rendered PDFs
            task.pdfs_generated = idx + 1
            task.progress = idx + 1

            if (idx + 1) % 10 == 0 or (idx + 1) == len(data):
                job.save()

        if skipped:
            logger.info(f"[pdf_gen] Job {job.job_id}: skipped {skipped} already-existing PDFs")

        # Zip
        task.phase = "zipping"
        zip_path = os.path.join(config.OUTPUT_FOLDER, f"pdfs_{job.job_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in os.listdir(pdf_folder):
                zf.write(os.path.join(pdf_folder, filename), filename)
        store.save_local_file(zip_path)

        task.status = "complete"
        task.phase = "complete"
        job.save()

        logger.info(f"[pdf_gen] Job {job.job_id}: complete — {task.pdfs_generated} generated")

    except Exception as e:
        logger.exception(f"[pdf_gen] Job {job.job_id}: CRASHED — {e}")
        task.status = "failed"
        task.error = str(e)
        try:
            job.save()
        except Exception:
            logger.error(f"[pdf_gen] Job {job.job_id}: failed to save error state")

    finally:
        import shutil
        temp_folder = os.path.join(config.OUTPUT_FOLDER, f"temp_{job.job_id}")
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder, ignore_errors=True)


def start_pdf_generation(job: Job):
    from app.models import TaskStatus
    data = job.valid_data if job.valid_data is not None else job.data
    # Fresh TaskStatus resets all counters (supports restart)
    job.tasks["pdfs"] = TaskStatus(status="running", phase="generating", total=len(data))
    job.status = "running"
    job.save()
    thread = threading.Thread(target=run_pdf_generation, args=(job,), daemon=True)
    thread.start()
