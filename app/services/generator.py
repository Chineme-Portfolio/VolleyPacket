import os
import urllib.request

from PIL import Image, ImageOps


def safe_filename(value):
    unsafe = '/\\:*?"<>|'
    for ch in unsafe:
        value = str(value).replace(ch, "-")
    return value


def extract_file_id(url):
    if not isinstance(url, str):
        return None
    if "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    if "/d/" in url:
        return url.split("/d/")[-1].split("/")[0]
    return None


def download_photo(url, temp_folder):
    if not url or not str(url).startswith("http"):
        return None
    os.makedirs(temp_folder, exist_ok=True)
    file_id = extract_file_id(url)
    if not file_id:
        return None

    # Return cached if already downloaded
    local_path = os.path.join(temp_folder, f"{file_id}.jpg")
    if os.path.exists(local_path):
        return local_path

    try:
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type:
                return None  # Rate-limited or CAPTCHA
            data = response.read()

        with open(local_path, "wb") as f:
            f.write(data)

        with Image.open(local_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > 800:
                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
            img.save(local_path, "JPEG", quality=85, optimize=True)

        return local_path
    except Exception:
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        return None
