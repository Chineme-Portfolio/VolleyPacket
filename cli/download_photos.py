# --- IMPORT ---
import os
import sys
import csv
import re
import urllib.request
import argparse
from datetime import datetime

import pandas as pd
from PIL import Image, ImageOps
from tqdm import tqdm


# --- CONFIG ---
PHOTO_FOLDER = "./photo_id"
LOGS_FOLDER = "./logs"
DEFAULT_INPUT = "./data/allocated_exam_schedule.xlsx"

MAX_DIMENSION = 800
JPEG_QUALITY = 85


# --- ARG PARSING ---
def parse_args():
    parser = argparse.ArgumentParser(
        description="Download candidate photos and save them named by ExamNo."
    )
    parser.add_argument(
        "input_file", nargs="?", default=DEFAULT_INPUT,
        help=f"Path to the allocated Excel file (default: {DEFAULT_INPUT})."
    )
    return parser.parse_args()


# --- HELPERS ---
def safe_filename(value):
    """Turn an ExamNo like 'RV/TE/UOE/AS/F/0001' into 'RV-TE-UOE-AS-F-0001'."""
    return re.sub(r'[\/\\:*?"<>|]', '-', str(value))


def extract_file_id(url):
    """Pull the Google Drive file ID from either /open?id=... or /file/d/.../view formats."""
    if not isinstance(url, str):
        return None
    if "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    if "/d/" in url:
        return url.split("/d/")[-1].split("/")[0]
    return None


def download_and_save(photo_url, exam_no):
    """Download one photo, resize, save to photo_id folder. Returns (success, error_msg)."""
    if not photo_url or not str(photo_url).startswith("http"):
        return False, "No photo link"

    file_id = extract_file_id(photo_url)
    if not file_id:
        return False, "Could not extract file ID from URL"

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    output_path = os.path.join(PHOTO_FOLDER, f"{safe_filename(exam_no)}.jpg")

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
        # Clean up any partial download
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass
        return False, str(e)


# --- MAIN LOOP ---
def process_rows(data, log_path):
    downloaded = 0
    failed = 0

    with open(log_path, "w", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=["Name", "ExamNo", "PhotoLink", "Downloaded", "Error"],
        )
        writer.writeheader()
        log_file.flush()

        for _, row in tqdm(data.iterrows(), total=len(data), desc="Downloading photos"):
            name = str(row.get("Name", ""))
            exam_no = str(row.get("ExamNo", ""))
            photo_url = row.get("PhotoLink", "")

            success, error = download_and_save(photo_url, exam_no)

            if success:
                downloaded += 1
            else:
                failed += 1

            writer.writerow({
                "Name": name,
                "ExamNo": exam_no,
                "PhotoLink": photo_url,
                "Downloaded": success,
                "Error": error,
            })
            log_file.flush()

    return downloaded, failed


# --- MAIN ---
def main():
    args = parse_args()

    if not os.path.isfile(args.input_file):
        print(f"Error: input file not found: {args.input_file}")
        sys.exit(1)

    os.makedirs(PHOTO_FOLDER, exist_ok=True)
    os.makedirs(LOGS_FOLDER, exist_ok=True)

    print(f"Loading data from {args.input_file}...")
    data = pd.read_excel(args.input_file, engine="openpyxl")
    print(f"Loaded {len(data)} candidates.")

    required_cols = {"Name", "ExamNo", "PhotoLink"}
    missing = required_cols - set(data.columns)
    if missing:
        print(f"Error: missing required columns: {missing}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOGS_FOLDER, f"photo_download_{timestamp}.csv")
    print(f"Writing download log to {log_path}")

    downloaded, failed = process_rows(data, log_path)

    total = len(data)
    print("\n--- Summary ---")
    print(f"  Total candidates   : {total}")
    print(f"  Photos downloaded  : {downloaded}")
    print(f"  Failed / skipped   : {failed}")
    print(f"  Photo folder       : {PHOTO_FOLDER}")
    print(f"  Log file           : {log_path}")


if __name__ == "__main__":
    main()