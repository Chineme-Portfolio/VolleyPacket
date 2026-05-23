"""
HTML → PDF renderer using WeasyPrint.
Replaces placeholders in HTML templates and renders to PDF.
"""

import os
import re

from weasyprint import HTML

from app.models import TemplateConfig


PLACEHOLDER_RE = re.compile(r"\{([^}]+)\}")


def fill_placeholders(html: str, row: dict) -> str:
    """Replace {Placeholder} tokens with values from the data row."""
    def replacer(match):
        key = match.group(1)
        if key in row:
            return str(row[key])
        return match.group(0)  # Leave unmatched placeholders as-is
    return PLACEHOLDER_RE.sub(replacer, html)


def render_pdf(template: TemplateConfig, row: dict, output_path: str, photo_path: str = None):
    """Render a template to PDF with data from one row."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    html = fill_placeholders(template.html_content, row)

    # If a photo path is provided, replace photo placeholder
    if photo_path and os.path.exists(photo_path):
        abs_photo = os.path.abspath(photo_path)
        html = html.replace("{PhotoURL}", f"file://{abs_photo}")
        html = html.replace("{PhotoLink}", f"file://{abs_photo}")

    HTML(string=html).write_pdf(output_path)
    return output_path


def render_preview(template: TemplateConfig, output_path: str):
    """Render a preview PDF using placeholder names as sample values."""
    sample_row = {}
    for p in template.placeholders:
        sample_row[p] = p  # Show the placeholder name itself as sample data

    # Add some realistic defaults for common fields
    defaults = {
        "Name": "John Doe",
        "Email": "johndoe@example.com",
        "Date": "2026-06-15",
        "Time": "9:00 AM",
        "Venue": "Main Hall",
        "Number": "001",
        "Phone": "+234 801 234 5678",
        "PhoneNumber": "+234 801 234 5678",
    }
    for key, val in defaults.items():
        if key in sample_row:
            sample_row[key] = val

    return render_pdf(template, sample_row, output_path)


def render_html_preview(template: TemplateConfig) -> str:
    """Return HTML with sample data filled in (for iframe preview, no PDF)."""
    sample_row = {}
    for p in template.placeholders:
        sample_row[p] = f'<span style="background:#fef3c7;padding:1px 4px;border-radius:3px;font-weight:600;">{p}</span>'

    return fill_placeholders(template.html_content, sample_row)
