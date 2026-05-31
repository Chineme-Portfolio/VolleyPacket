"""
AI-powered HTML template generation using Anthropic Claude.
Generates complete, self-contained HTML/CSS documents for PDF rendering.
"""

import base64
import json
import re
import anthropic

from app.models import TemplateConfig
from app import config


def _detect_media_type_from_b64(b64_data: str, fallback: str = "image/png") -> str:
    """Detect the real image media type from base64-encoded data."""
    try:
        header = base64.b64decode(b64_data[:32])
        if header[:2] == b'\xff\xd8':
            return "image/jpeg"
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return "image/webp"
    except Exception:
        pass
    return fallback


SYSTEM_PROMPT = """You are a professional document designer for VolleyPacket, a platform that generates personalized PDF letters and invitations.

Given a user's description (and optionally parsed document content), design a COMPLETE, self-contained HTML/CSS template.

DESIGN RULES:
- Create visually DISTINCT designs. Vary layouts, typography, color schemes, and visual elements.
- Use the @page CSS rule for A4 sizing: @page { size: A4; margin: 15mm 20mm; }
- All CSS must be in a <style> block inside <head> — NO external stylesheets or fonts.
- Use only system fonts: Arial, Helvetica, Georgia, Times New Roman, Courier New, Verdana, Tahoma.
- Design for PRINT, not screen. Think formal letters, event invitations, certificates, reports.
- Use color creatively — backgrounds, accent bars, borders, colored headers. Don't just make everything black and white.
- Make it look professional and polished — like something from a real organization.
- The ENTIRE template must fit on ONE page. Do not design content that overflows onto a second page.
- Include a footer with "Powered by VolleyPacket.com" unless the user explicitly requests otherwise.

IMAGE RULES:
- If the user uploads a logo, letterhead, or design image, use the placeholder {EMBEDDED_IMAGE_1} as the src for an <img> tag where that image should appear. The system will replace it with the actual image data automatically.
  Example: <img src="{EMBEDDED_IMAGE_1}" alt="Logo" style="width: 150px;" />
- If multiple images are uploaded, use {EMBEDDED_IMAGE_1}, {EMBEDDED_IMAGE_2}, etc. in order.
- For per-row dynamic photos (e.g. passport photos, headshots from a spreadsheet), use {PhotoURL} as the src:
  Example: <img src="{PhotoURL}" alt="Photo" style="width: 100px; height: 120px; object-fit: cover;" />
- Do NOT include {EMBEDDED_IMAGE_N} or {PhotoURL} in the "placeholders" array — they are handled separately.

PLACEHOLDER RULES:
- Use curly brace placeholders like {Name}, {Email}, {Date} for personalized data.
- The user will tell you which fields/columns they have — use EXACTLY those names.
- If no specific columns are given, use sensible defaults based on the use case.
- Placeholders should appear naturally in the document content.

OUTPUT FORMAT:
Return ONLY a JSON object with these keys:
{
  "name": "Template name",
  "description": "One-line description",
  "html_content": "<!DOCTYPE html><html>...</html>",
  "placeholders": ["Name", "Email", "Date"]
}

The html_content must be a COMPLETE HTML document (<!DOCTYPE html> through </html>).
The placeholders array must list every {Placeholder} name used in the HTML.
Do NOT include EMBEDDED_IMAGE_N or PhotoURL in the placeholders array.

Return ONLY valid JSON. No markdown, no explanation, no code fences."""


def generate_template_from_content(
    parsed_contents: list[dict],
    instructions: str = None,
    columns: list[str] = None,
) -> TemplateConfig:
    """Generate an HTML template using AI.

    Accepts a list of parsed content dicts. Each can be a document (with raw_text)
    or an image (with is_image flag + base64 data). Multiple files are combined
    into a single prompt — e.g. a letterhead image + a body text document.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Build the message content blocks from all uploaded files
    content_blocks = []
    has_image = False
    has_document = False
    # Track uploaded images for post-processing {EMBEDDED_IMAGE_N} placeholders
    image_data_uris: list[str] = []

    for pc in parsed_contents:
        # Support both nested (detected_fields.is_image) and flat (is_image) formats
        fields = pc.get("detected_fields", {}) if isinstance(pc.get("detected_fields"), dict) else {}
        is_image = fields.get("is_image", False) or pc.get("is_image", False)
        image_intent = pc.get("image_intent", "reference")  # "embed" or "reference"

        if is_image:
            has_image = True
            image_data = fields.get("image_data", "") or pc.get("image_data", "")
            declared_type = fields.get("image_media_type", "") or pc.get("image_media_type", "image/png")
            # Always verify from actual bytes — file extension / frontend can be wrong
            media_type = _detect_media_type_from_b64(image_data, declared_type)
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            })
            if image_intent == "embed":
                # This image will be baked into the template HTML
                embed_index = len(image_data_uris) + 1
                image_data_uris.append(f"data:{media_type};base64,{image_data}")
                content_blocks.append({
                    "type": "text",
                    "text": f"[This is image #{embed_index} to EMBED in the template. Use <img src=\"{{EMBEDDED_IMAGE_{embed_index}}}\" /> where this image should appear.]\n",
                })
            else:
                # Reference image — Claude sees it for design inspiration only
                content_blocks.append({
                    "type": "text",
                    "text": "[This image is a DESIGN REFERENCE. Recreate the look/layout with HTML/CSS — do NOT use {EMBEDDED_IMAGE_N} for this image.]\n",
                })
        elif pc.get("raw_text"):
            has_document = True
            # Strip image data from document content to avoid bloating the prompt
            clean_pc = {k: v for k, v in pc.items() if k not in ("detected_fields", "image_intent")}
            content_blocks.append({
                "type": "text",
                "text": f"Document content:\n\n{json.dumps(clean_pc, indent=2)}\n\n",
            })

    # Build the instruction text
    text_part = ""
    if has_image and has_document:
        text_part = "I've uploaded both an image and a document. Use the image as a visual reference for the design/layout (letterhead, colors, logo placement, styling) and the document text for the body content. Combine them into one cohesive HTML/CSS template. Replace any personal data or blank fields with {Placeholder} merge fields.\n\n"
    elif has_image:
        text_part = "Look at this document/template image carefully. Recreate it as a professional HTML/CSS template, matching the layout, styling, and structure as closely as possible. Replace any personal data or blank fields with {Placeholder} merge fields.\n\n"

    if columns:
        text_part += f"Available data columns from the spreadsheet: {', '.join(columns)}\n"
        text_part += f"Use these as placeholders: {', '.join('{' + c + '}' for c in columns)}\n\n"

    if instructions:
        text_part += f"User instructions:\n{instructions}\n"

    if not text_part.strip() and not has_image:
        text_part = "Create a professional, modern invitation letter template with common fields like Name, Email, Date, and Venue."

    content_blocks.append({"type": "text", "text": text_part})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    # Extract placeholders from HTML if not provided
    html = data.get("html_content", "")
    declared_placeholders = data.get("placeholders", [])

    # Post-process: replace {EMBEDDED_IMAGE_N} with actual base64 data URIs
    for idx, data_uri in enumerate(image_data_uris, start=1):
        html = html.replace(f"{{EMBEDDED_IMAGE_{idx}}}", data_uri)

    # Also scan the HTML for any {Placeholder} patterns the AI used
    found = set(re.findall(r"\{([A-Za-z_]\w*)\}", html))
    # Filter out CSS/JS braces and internal placeholders
    internal_placeholders = {"PhotoURL", "PhotoLink"}
    placeholders = sorted(
        (set(declared_placeholders) | {p for p in found if p[0].isupper() or p in declared_placeholders})
        - internal_placeholders
    )

    return TemplateConfig(
        name=data.get("name", "Untitled Template"),
        description=data.get("description", ""),
        html_content=html,
        placeholders=placeholders,
    )
