import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.utils import ImageReader

from app.models import TemplateConfig


WIDTH, HEIGHT = A4
MARGIN_LEFT = 20 * mm
MARGIN_RIGHT = WIDTH - 20 * mm
MARGIN_BOTTOM = 18 * mm  # Space reserved for footer
CENTER = WIDTH / 2
CONTENT_WIDTH = MARGIN_RIGHT - MARGIN_LEFT

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

SAMPLE_ROW = {
    "Name": "John Doe",
    "ExamNo": "RV/TE/UOE/AS/F/0001",
    "ExamDate": "2026-05-21",
    "ExamTime": "9:00 AM",
    "AssignedHall": "Hall 1",
    "Number": 1,
    "Email": "johndoe@example.com",
    "PhotoLink": "",
    "PhoneNumber": "08012345678",
}


def fill_placeholders(text, row):
    def replacer(match):
        key = match.group(1)
        val = row.get(key, match.group(0))
        return str(val)[:10] if key == "ExamDate" else str(val)
    return PLACEHOLDER_RE.sub(replacer, str(text))


def render_pdf(template: TemplateConfig, row: dict, output_path: str, photo_path: str = None):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=A4)

    theme = template.theme
    primary = colors.HexColor(theme.primary_color)
    secondary = colors.HexColor(theme.secondary_color)
    accent = colors.HexColor(theme.accent_color)
    text_color = colors.HexColor(theme.text_color)
    label_color = colors.HexColor(theme.label_color)

    L = MARGIN_LEFT
    R = MARGIN_RIGHT

    # cur_y tracks the current drawing position (top of page = HEIGHT)
    # We draw downward, so cur_y decreases as we add content
    cur_y = HEIGHT - 15 * mm  # Start 15mm from top

    # === HEADER ===
    header = template.header

    # Logo
    logo_w = 16 * mm
    logo_h = 16 * mm
    logo_x = CENTER - logo_w / 2
    logo_y = cur_y - logo_h

    logo_path = header.logo_path
    logo_drawn = False
    if logo_path and os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            c.drawImage(img, logo_x, logo_y, width=logo_w, height=logo_h,
                        preserveAspectRatio=True, mask='auto')
            logo_drawn = True
        except Exception:
            pass

    if not logo_drawn:
        c.setFillColor(accent)
        c.setStrokeColor(primary)
        c.setLineWidth(1)
        c.circle(CENTER, logo_y + logo_h / 2, logo_w / 2, fill=1, stroke=1)
        c.setFillColor(primary)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(CENTER, logo_y + logo_h / 2 - 2, "LOGO")

    # Number (top right, aligned with logo)
    if header.show_number:
        c.setFillColor(primary)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(R, cur_y - 5 * mm, f"Number: {row.get('Number', '')}")

    cur_y = logo_y - 3 * mm

    # Company name
    c.setFillColor(primary)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(CENTER, cur_y, header.company_name)
    cur_y -= 5 * mm

    # Address + contact lines
    c.setFillColor(text_color)
    c.setFont("Helvetica", 8.5)
    for line in header.address_lines + header.contact_lines:
        c.drawCentredString(CENTER, cur_y, line)
        cur_y -= 4 * mm

    # Motto
    if header.motto:
        cur_y -= 1 * mm
        c.setFillColor(primary)
        c.setFont("Helvetica-BoldOblique", 9)
        c.drawCentredString(CENTER, cur_y, header.motto)
        cur_y -= 4 * mm

    # Divider
    cur_y -= 2 * mm
    c.setStrokeColor(primary)
    c.setLineWidth(1.2)
    c.line(L, cur_y, R, cur_y)
    c.setStrokeColor(secondary)
    c.setLineWidth(0.4)
    c.line(L, cur_y - 1 * mm, R, cur_y - 1 * mm)
    cur_y -= 6 * mm

    # === REFERENCE LINE ===
    ref = template.reference
    if ref.our_ref or ref.date:
        c.setFont("Helvetica", 8.5)
        c.setFillColor(text_color)
        if ref.our_ref:
            c.drawString(L, cur_y, f"Our Ref: {ref.our_ref}")
        c.drawCentredString(CENTER, cur_y, "Your Ref: ___________________")
        if ref.date:
            c.drawRightString(R, cur_y, f"Date: {ref.date}")
        cur_y -= 8 * mm

    # === SUBJECT ===
    if template.subject:
        cur_y -= 2 * mm
        c.setFillColor(primary)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(CENTER, cur_y, template.subject)
        c.setStrokeColor(secondary)
        c.setLineWidth(1)
        c.line(L, cur_y - 2 * mm, R, cur_y - 2 * mm)
        cur_y -= 8 * mm

    # === SALUTATION ===
    c.setFont("Helvetica", 10)
    c.setFillColor(text_color)
    c.drawString(L, cur_y, fill_placeholders(template.salutation, row))
    cur_y -= 7 * mm

    # === PHOTO BOX (positioned to the right, body text wraps around it) ===
    photo_box_top = cur_y
    photo_box_height = 38 * mm
    photo_box_width = 33 * mm
    if template.show_photo:
        bx = R - photo_box_width
        by = cur_y - photo_box_height

        c.setFillColor(accent)
        c.setStrokeColor(colors.HexColor("#CCCCCC"))
        c.setLineWidth(0.8)
        c.rect(bx, by, photo_box_width, photo_box_height, fill=1, stroke=1)

        if photo_path and os.path.exists(photo_path):
            try:
                img = ImageReader(photo_path)
                c.drawImage(img, bx + 1.5 * mm, by + 1.5 * mm,
                            width=photo_box_width - 3 * mm, height=photo_box_height - 3 * mm,
                            preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        else:
            c.setStrokeColor(secondary)
            c.setDash(2, 3)
            c.setLineWidth(0.5)
            c.rect(bx + 1.5 * mm, by + 1.5 * mm,
                   photo_box_width - 3 * mm, photo_box_height - 3 * mm, fill=0, stroke=1)
            c.setDash()
            c.setFillColor(label_color)
            c.setFont("Helvetica", 7)
            cx = bx + photo_box_width / 2
            c.drawCentredString(cx, by + photo_box_height / 2 + 3, "PASSPORT")
            c.drawCentredString(cx, by + photo_box_height / 2 - 6, "PHOTOGRAPH")

    # === BODY PARAGRAPHS ===
    # Narrow width while photo box is beside text
    text_width = CONTENT_WIDTH
    if template.show_photo:
        text_width = CONTENT_WIDTH - photo_box_width - 5 * mm

    style = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9.5,
        textColor=text_color, leading=14, alignment=TA_JUSTIFY
    )

    for para_text in template.body_paragraphs:
        filled = fill_placeholders(para_text, row)
        p = Paragraph(filled, style)

        # If we've passed the photo box bottom, use full width
        if template.show_photo and cur_y - 14 < photo_box_top - photo_box_height:
            text_width = CONTENT_WIDTH

        w, h = p.wrapOn(c, text_width, 200 * mm)
        cur_y -= h
        p.drawOn(c, L, cur_y)
        cur_y -= 4 * mm

    # Make sure we're past the photo box before continuing
    if template.show_photo:
        photo_bottom = photo_box_top - photo_box_height - 4 * mm
        if cur_y > photo_bottom:
            cur_y = photo_bottom

    cur_y -= 4 * mm

    # === DETAIL BOX ===
    detail_box = template.detail_box
    if detail_box and detail_box.field_rows:
        num_rows = len(detail_box.field_rows)
        row_height = 13 * mm
        header_height = 9 * mm
        box_height = header_height + (num_rows * row_height) + 2 * mm
        bw = CONTENT_WIDTH

        # Check if we need a new page
        if cur_y - box_height < MARGIN_BOTTOM:
            c.showPage()
            cur_y = HEIGHT - 15 * mm

        box_top = cur_y
        box_bottom = cur_y - box_height

        c.setFillColor(accent)
        c.setStrokeColor(primary)
        c.setLineWidth(1)
        c.rect(L, box_bottom, bw, box_height, fill=1, stroke=1)

        # Header strip
        c.setFillColor(primary)
        c.rect(L, box_top - header_height, bw, header_height, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(L + 4 * mm, box_top - 6 * mm, detail_box.title)

        col1 = L + 4 * mm
        col2 = L + bw / 2 + 4 * mm
        field_y = box_top - header_height - 5 * mm

        for field_row in detail_box.field_rows:
            if len(field_row) == 1:
                field = field_row[0]
                c.setFont("Helvetica", 7.5)
                c.setFillColor(label_color)
                c.drawString(col1, field_y, field.label)
                c.setFont("Helvetica-Bold", 9.5)
                c.setFillColor(primary)
                c.drawString(col1, field_y - 5.5 * mm, fill_placeholders(field.value, row))
            elif len(field_row) >= 2:
                f1, f2 = field_row[0], field_row[1]
                c.setFont("Helvetica", 7.5)
                c.setFillColor(label_color)
                c.drawString(col1, field_y, f1.label)
                c.drawString(col2, field_y, f2.label)
                c.setFont("Helvetica-Bold", 9.5)
                c.setFillColor(primary)
                c.drawString(col1, field_y - 5.5 * mm, fill_placeholders(f1.value, row))
                c.drawString(col2, field_y - 5.5 * mm, fill_placeholders(f2.value, row))
            field_y -= row_height

        cur_y = box_bottom - 4 * mm

    # === NOTICE ===
    if template.notice:
        if cur_y - 10 * mm < MARGIN_BOTTOM:
            c.showPage()
            cur_y = HEIGHT - 15 * mm

        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(label_color)
        c.drawString(L, cur_y, fill_placeholders(template.notice, row))
        cur_y -= 8 * mm

    # === INSTRUCTIONS ===
    if template.instructions and template.instructions.items:
        # Estimate height: heading + items
        est_height = 8 * mm + len(template.instructions.items) * 6 * mm
        if cur_y - est_height < MARGIN_BOTTOM:
            c.showPage()
            cur_y = HEIGHT - 15 * mm

        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(primary)
        c.drawString(L, cur_y, template.instructions.heading)
        c.setStrokeColor(secondary)
        c.setLineWidth(0.6)
        c.line(L, cur_y - 1.5 * mm, R, cur_y - 1.5 * mm)
        cur_y -= 6 * mm

        bullet_style = ParagraphStyle(
            "bul", fontName="Helvetica", fontSize=9,
            textColor=text_color, leading=13
        )
        for item in template.instructions.items:
            filled = fill_placeholders(item, row)
            p = Paragraph(f"• {filled}", bullet_style)
            w, h = p.wrapOn(c, CONTENT_WIDTH - 2 * mm, 30 * mm)

            if cur_y - h < MARGIN_BOTTOM:
                c.showPage()
                cur_y = HEIGHT - 15 * mm

            cur_y -= h
            p.drawOn(c, L + 2 * mm, cur_y)
            cur_y -= 1.5 * mm

        cur_y -= 4 * mm

    # === COMPLIANCE ===
    if template.compliance and template.compliance.text:
        comp_style = ParagraphStyle(
            "comp", fontName="Helvetica", fontSize=9,
            textColor=text_color, leading=13, alignment=TA_JUSTIFY
        )
        filled = fill_placeholders(template.compliance.text, row)
        p = Paragraph(filled, comp_style)
        w, h = p.wrapOn(c, CONTENT_WIDTH, 60 * mm)

        # heading + text
        total_h = 8 * mm + h
        if cur_y - total_h < MARGIN_BOTTOM:
            c.showPage()
            cur_y = HEIGHT - 15 * mm

        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(primary)
        c.drawString(L, cur_y, template.compliance.heading)
        c.setStrokeColor(secondary)
        c.setLineWidth(0.6)
        c.line(L, cur_y - 1.5 * mm, R, cur_y - 1.5 * mm)
        cur_y -= 6 * mm

        cur_y -= h
        p.drawOn(c, L, cur_y)
        cur_y -= 6 * mm

    # === SIGNATURE ===
    sig_height = 25 * mm
    if cur_y - sig_height < MARGIN_BOTTOM:
        c.showPage()
        cur_y = HEIGHT - 15 * mm

    sig = template.signature
    c.setFont("Helvetica", 9)
    c.setFillColor(text_color)
    c.drawString(L, cur_y, "Thank you.")
    cur_y -= 6 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(L, cur_y, sig.closing)
    cur_y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(primary)
    c.drawString(L, cur_y, sig.name)
    cur_y -= 5 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(text_color)
    c.drawString(L, cur_y, sig.title)

    # === FOOTER (always at page bottom) ===
    footer = template.footer
    c.setFillColor(primary)
    c.rect(0, 0, WIDTH, 12 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(WIDTH / 2, 7 * mm, footer.text)
    if footer.credit:
        c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(WIDTH / 2, 3 * mm, footer.credit)

    c.save()
    return output_path


def render_preview(template: TemplateConfig, output_path: str):
    return render_pdf(template, SAMPLE_ROW, output_path)
