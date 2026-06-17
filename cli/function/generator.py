# --- IMPORT ---
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps
import urllib

def safe_filename(value):
    """Convert a string into a filesystem-safe filename."""
    unsafe = '/\\:*?"<>|'
    for ch in unsafe:
        value = value.replace(ch, "-")
    return value

def extract_file_id(url):
    if "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    elif "/d/" in url:
        return url.split("/d/")[-1].split("/")[0]
    else:
        return None

def download_photo(url, temp_folder):
    if not url or not str(url).startswith("http"):
        return None
    os.makedirs(temp_folder, exist_ok=True)
    file_id = extract_file_id(url)
    if not file_id:
        print(f"Could not extract file ID from URL: {url}")
        return None
    try:
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        local_path = os.path.join(temp_folder, f"{file_id}.jpg")
        urllib.request.urlretrieve(download_url, local_path)

        # Fix orientation, resize, and compress
        with Image.open(local_path) as img:
            img = ImageOps.exif_transpose(img)

            # Convert any non-RGB (e.g. PNG with transparency) to RGB for JPEG
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Shrink if largest dimension > 800px (keeps passport photo sharp, drastically smaller file)
            MAX_DIMENSION = 800
            if max(img.size) > MAX_DIMENSION:
                img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)

            # Save with quality=85 (good balance of quality and size)
            img.save(local_path, "JPEG", quality=85, optimize=True)

        return local_path
    except Exception as e:
        print(f"Failed to download photo from {url}: {e}")
        return None

# --- PAGE CONSTANTS ---
WIDTH, HEIGHT = A4
L = 20 * mm
R = WIDTH - 20 * mm
CENTER = WIDTH / 2

# --- OSALASI GREEN THEME ---
DARK_GREEN  = colors.HexColor("#08764F")
MID_GREEN   = colors.HexColor("#08AB52")
LIGHT_GREEN = colors.HexColor("#E8F4EC")
RULE_COLOR  = colors.HexColor("#CCCCCC")
TEXT_COLOR  = colors.HexColor("#2C2C2C")
LABEL_COLOR = colors.HexColor("#777777")

# --- LOGO ---
# place the downloaded logo here; if the file does not exist, a placeholder is drawn instead
LOGO_PATH = "./assets/logo.jpg"

# --- HELPERS ---
def y(mm_from_top):
    return HEIGHT - mm_from_top * mm


# --- HEADER ---
def draw_logo(c):
    """Draw logo centered above the company name. Falls back to a green circle placeholder."""
    logo_w = 16 * mm
    logo_h = 16 * mm
    logo_x = CENTER - logo_w / 2
    logo_y = y(20)                      # bottom of logo at 20mm from top

    if os.path.exists(LOGO_PATH):
        try:
            img = ImageReader(LOGO_PATH)
            c.drawImage(img, logo_x, logo_y, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask='auto')
            return
        except Exception as e:
            print(f"Could not load logo: {e}")

    # placeholder circle
    c.setFillColor(LIGHT_GREEN)
    c.setStrokeColor(DARK_GREEN)
    c.setLineWidth(1)
    c.circle(CENTER, logo_y + logo_h / 2, logo_w / 2, fill=1, stroke=1)
    c.setFillColor(DARK_GREEN)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(CENTER, logo_y + logo_h / 2 - 2, "LOGO")


def draw_header(c, row):
    draw_logo(c)

    # Number
    c.setFillColor(DARK_GREEN)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(R, y(20), f"Number: {row['Number']}")

    # Company name
    c.setFillColor(DARK_GREEN)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(CENTER, y(25), "OSALASI COMPANY LIMITED")

    # Address + contact (centered, grey)
    c.setFillColor(TEXT_COLOR)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(CENTER, y(30),
        "H/Office: Gwada_Shiroro Dam Express Road, Sabon Gurusu, Niger State")
    c.drawCentredString(CENTER, y(34),
        "Phone: +234 803 451 3313  |  +234 813 466 5224  |  +234 703 835 8897")
    c.drawCentredString(CENTER, y(38),
        "Email: osalasifarms.ng.ltd@gmail.com")

    # Motto
    c.setFillColor(DARK_GREEN)
    c.setFont("Helvetica-BoldOblique", 9)
    c.drawCentredString(CENTER, y(43), "Motto: Hard Work Pays")

    # Thick green divider
    c.setStrokeColor(DARK_GREEN)
    c.setLineWidth(1.2)
    c.line(L, y(46), R, y(46))
    c.setStrokeColor(MID_GREEN)
    c.setLineWidth(0.4)
    c.line(L, y(47), R, y(47))


# --- REF & SUBJECT ---
def draw_ref_line(c):
    c.setFont("Helvetica", 8.5)
    c.setFillColor(TEXT_COLOR)
    c.drawString(L, y(53), "Our Ref: Osa/CBT/PA/01/2026")
    c.drawCentredString(CENTER, y(53), "Your Ref: ___________________")
    c.drawRightString(R, y(53), "Date: April 16, 2026")


def draw_subject(c):
    c.setFillColor(DARK_GREEN)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(CENTER, y(62),
        "SUBJECT: ALLOCATION OF COMPUTER-BASED TEST (CBT) EXAMINATION TIMETABLE")
    c.setStrokeColor(MID_GREEN)
    c.setLineWidth(1)
    c.line(L, y(62) - 2 * mm, R, y(62) - 2 * mm)


# --- SALUTATION & BODY ---
def draw_salutation(c, row):
    c.setFont("Helvetica", 10)
    c.setFillColor(TEXT_COLOR)
    c.drawString(L, y(72), f"Dear {row['Name']},")


def draw_photo_box(c, photo_path):
    bw = 33 * mm
    bh = 38 * mm
    bx = R - bw
    by = y(120)

    # Box outline
    c.setFillColor(LIGHT_GREEN)
    c.setStrokeColor(RULE_COLOR)
    c.setLineWidth(0.8)
    c.rect(bx, by, bw, bh, fill=1, stroke=1)

    if photo_path:
        # Draw the actual photo
        try:
            img = ImageReader(photo_path)
            c.drawImage(img, bx + 1.5 * mm, by + 1.5 * mm,
                        width=bw - 3 * mm, height=bh - 3 * mm,
                        preserveAspectRatio=True, mask='auto')
            return
        except Exception as e:
            print(f"Could not load photo: {e}")

    # Fallback placeholder
    c.setStrokeColor(MID_GREEN)
    c.setDash(2, 3)
    c.setLineWidth(0.5)
    c.rect(bx + 1.5 * mm, by + 1.5 * mm, bw - 3 * mm, bh - 3 * mm, fill=0, stroke=1)
    c.setDash()

    c.setFillColor(LABEL_COLOR)
    c.setFont("Helvetica", 7)
    cx = bx + bw / 2
    c.drawCentredString(cx, by + bh / 2 + 3, "PASSPORT")
    c.drawCentredString(cx, by + bh / 2 - 6, "PHOTOGRAPH")


def draw_body(c):
    """Two body paragraphs — wraps around photo on the right."""
    text_width = WIDTH - 2 * 20 * mm - 33 * mm - 5 * mm

    body1 = (
        "Following your successful shortlisting in the ongoing recruitment exercise to employ "
        "teachers into primary and secondary schools in Rivers State, we are pleased to formally "
        "notify you that the <b>Rivers State Government</b> is conducting the exercise in partnership "
        "with the Consultant, <b>Osalasi Company Limited</b>."
    )
    body2 = (
        "You are hereby invited to participate in the Computer-Based Test (CBT) as scheduled below:"
    )

    style = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9.5,
        textColor=TEXT_COLOR, leading=14, alignment=TA_JUSTIFY
    )
    p1 = Paragraph(body1, style)
    w1, h1 = p1.wrapOn(c, text_width, 80 * mm)
    p1.drawOn(c, L, y(82) - h1)

    p2 = Paragraph(body2, style)
    w2, h2 = p2.wrapOn(c, text_width, 20 * mm)
    p2.drawOn(c, L, y(82) - h1 - 4 * mm - h2)


# --- EXAM DETAILS BOX ---
def draw_exam_box(c, row):
    bx = L
    bw = WIDTH - 2 * 20 * mm
    bh = 48 * mm                    # taller: 5 rows now (including centre)
    by = y(172)

    # box background
    c.setFillColor(LIGHT_GREEN)
    c.setStrokeColor(DARK_GREEN)
    c.setLineWidth(1)
    c.rect(bx, by, bw, bh, fill=1, stroke=1)

    # header strip
    c.setFillColor(DARK_GREEN)
    c.rect(bx, by + bh - 9 * mm, bw, 9 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(bx + 4 * mm, by + bh - 6 * mm, "EXAMINATION DETAILS")

    col1 = bx + 4 * mm
    col2 = bx + bw / 2 + 4 * mm

    fields = [
        ("EXAMINATION NUMBER", row["ExamNo"],                  "TIME SLOT",     row["ExamTime"]),
        ("EXAMINATION DATE",   str(row["ExamDate"])[:10],      "ASSIGNED HALL", row["AssignedHall"]),
    ]

    row_top = by + bh - 9 * mm - 5 * mm
    for label1, val1, label2, val2 in fields:
        c.setFont("Helvetica", 7.5)
        c.setFillColor(LABEL_COLOR)
        c.drawString(col1, row_top, label1)
        c.drawString(col2, row_top, label2)
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(DARK_GREEN)
        c.drawString(col1, row_top - 5.5 * mm, str(val1))
        c.drawString(col2, row_top - 5.5 * mm, str(val2))
        row_top -= 13 * mm

    # Centre field spans both columns
    c.setFont("Helvetica", 7.5)
    c.setFillColor(LABEL_COLOR)
    c.drawString(col1, row_top, "EXAMINATION CENTRE")
    c.setFont("Helvetica-Bold", 9.5)
    c.setFillColor(DARK_GREEN)
    c.drawString(col1, row_top - 5.5 * mm,
        "ICTC, Ignatius Ajuru University of Education, Rumuolumeni, Port Harcourt")


# --- NOTICE, INSTRUCTIONS, COMPLIANCE ---
def draw_notice(c):
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(LABEL_COLOR)
    c.drawString(L, y(176),
        "Please note that your examination number determines your specific date. You must strictly adhere to the assigned schedule.")


def section_heading(c, text, y_mm):
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(DARK_GREEN)
    c.drawString(L, y(y_mm), text)
    c.setStrokeColor(MID_GREEN)
    c.setLineWidth(0.6)
    c.line(L, y(y_mm) - 1.5 * mm, R, y(y_mm) - 1.5 * mm)


def draw_instructions(c):
    section_heading(c, "Important Instructions", 184)
    items = [
        "Candidates must report to the examination venue at least <b>one (1) hour</b> before the scheduled time.",
        "You are required to present a <b>valid means of identification</b> before entry into the examination hall.",
        "The use of <b>mobile phones, smart devices, or any electronic gadgets</b> is strictly prohibited during the examination.",
        "Any form of <b>examination malpractice</b> will result in immediate disqualification.",
    ]
    style = ParagraphStyle("bul", fontName="Helvetica", fontSize=9,
                           textColor=TEXT_COLOR, leading=13)
    cur_y = y(189)
    for item in items:
        p = Paragraph(f"• {item}", style)
        w, h = p.wrapOn(c, R - L - 2 * mm, 20 * mm)
        cur_y -= h
        p.drawOn(c, L + 2 * mm, cur_y)
        cur_y -= 1.5 * mm


def draw_compliance(c):
    section_heading(c, "Compliance Notice", 225)
    text = (
        "Failure to appear on your assigned date, as indicated by your examination number, may lead to "
        "automatic forfeiture of your opportunity to proceed in the recruitment process. "
        "We wish you success as you proceed to this important stage of the selection process."
    )
    style = ParagraphStyle("body", fontName="Helvetica", fontSize=9,
                           textColor=TEXT_COLOR, leading=13, alignment=TA_JUSTIFY)
    p = Paragraph(text, style)
    w, h = p.wrapOn(c, R - L, 30 * mm)
    p.drawOn(c, L, y(230) - h)


# --- SIGNATURE & FOOTER ---
def draw_signature(c):
    c.setFont("Helvetica", 9)
    c.setFillColor(TEXT_COLOR)
    c.drawString(L, y(254), "Thank you.")
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(L, y(260), "Yours faithfully,")

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(DARK_GREEN)
    c.drawString(L, y(268), "Prof. Yunusa Danladi Hakimi")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(TEXT_COLOR)
    c.drawString(L, y(273), "For: Rivers State Government & Osalasi Company Limited")


def draw_footer(c):
    # green footer bar
    c.setFillColor(DARK_GREEN)
    c.rect(0, 0, WIDTH, 12 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(
        WIDTH / 2, 7 * mm,
        "This document is system-generated and is unique to the candidate. "
        "Please bring a printed copy to the examination venue."
    )
    c.setFont("Helvetica-Oblique", 7)
    c.drawCentredString(WIDTH / 2, 3 * mm, "Developed by Chineme Dimkpa, Software Specialist (TX, USA)")


# --- MAIN BUILDER ---
def generate_pdf(row, output_folder, temp_folder="./temp"):
    os.makedirs(output_folder, exist_ok=True)
    filename = f"{output_folder}/{safe_filename(row['ExamNo'])}.pdf"

    photo_path = download_photo(row.get("PhotoLink", ""), temp_folder)

    c = canvas.Canvas(filename, pagesize=A4)
    draw_header(c, row)
    draw_ref_line(c)
    draw_subject(c)
    draw_salutation(c, row)
    draw_photo_box(c, photo_path)     # now takes photo_path
    draw_body(c)
    draw_exam_box(c, row)
    draw_notice(c)
    draw_instructions(c)
    draw_compliance(c)
    draw_signature(c)
    draw_footer(c)
    c.save()

    # Clean up temp photo
    if photo_path and os.path.exists(photo_path):
        os.remove(photo_path)


if __name__ == "__main__":
    import pandas as pd
    data = pd.read_excel('./data/allocated_exam_schedule.xlsx')
    row = data.iloc[0]
    generate_pdf(row, './pdf')
    print(f"Generated PDF for {row['Name']}")