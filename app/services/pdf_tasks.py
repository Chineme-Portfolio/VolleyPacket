import os
import zipfile
import threading

from app.services.jobs import Job
from app.services.template_renderer import render_pdf
from app.services.generator import safe_filename, download_photo
from app.services.storage import store
from app import config


def run_pdf_generation(job: Job):
    task = job.tasks["pdfs"]
    data = job.valid_data if job.valid_data is not None else job.data
    task.total = len(data)
    task.status = "running"
    task.phase = "generating"

    pdf_folder = job.get_pdf_folder()
    temp_folder = os.path.join(config.OUTPUT_FOLDER, f"temp_{job.job_id}")
    os.makedirs(temp_folder, exist_ok=True)

    try:
        for idx, (_, row) in enumerate(data.iterrows()):
            if job.should_stop("pdfs"):
                task.status = "cancelled"
                task.phase = "cancelled"
                job.save()
                return

            row_dict = row.to_dict()
            exam_no = str(row_dict.get("ExamNo", f"candidate_{idx}"))
            output_path = os.path.join(pdf_folder, f"{safe_filename(exam_no)}.pdf")

            photo_path = None
            if job.template and job.template.show_photo:
                photo_url = row_dict.get("PhotoLink", "")
                if photo_url:
                    photo_path = download_photo(photo_url, temp_folder)

            render_pdf(job.template, row_dict, output_path, photo_path=photo_path)

            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)

            task.pdfs_generated = idx + 1
            task.progress = idx + 1
            task.phase = "generating"

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

    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        job.save()

    finally:
        import shutil
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder, ignore_errors=True)


def start_pdf_generation(job: Job):
    thread = threading.Thread(target=run_pdf_generation, args=(job,), daemon=True)
    thread.start()
