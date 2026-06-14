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


# Matches an inline base64 image data URI (e.g. the src of an embedded logo).
_DATA_URI_RE = re.compile(r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")


def strip_embedded_images(html: str) -> tuple[str, dict[str, str]]:
    """Replace inline base64 image data URIs with {EMBEDDED_IMAGE_N} placeholders.

    Returns (stripped_html, image_map). Used before showing template HTML to the
    AI or the raw-HTML editor so megabytes of base64 never reach them (token blowup
    / mangled images / unusable textarea). Re-inject with reinject_embedded_images.
    Mirrors the {EMBEDDED_IMAGE_N} convention the generator already emits.
    """
    image_map: dict[str, str] = {}
    counter = {"n": 0}

    def repl(match):
        counter["n"] += 1
        token = f"EMBEDDED_IMAGE_{counter['n']}"
        image_map[token] = match.group(0)
        return "{" + token + "}"

    stripped = _DATA_URI_RE.sub(repl, html)
    return stripped, image_map


def reinject_embedded_images(html: str, image_map: dict[str, str]) -> str:
    """Replace {EMBEDDED_IMAGE_N} placeholders with their original base64 data URIs."""
    if not image_map:
        return html
    for token, data_uri in image_map.items():
        html = html.replace("{" + token + "}", data_uri)
    return html


def extract_placeholders(html: str) -> list[str]:
    """Return the sorted {Placeholder} merge-field names used in an HTML template.

    Excludes the internal {PhotoURL}/{PhotoLink} (per-row photos) and
    {EMBEDDED_IMAGE_N} (embedded images) tokens, which are handled separately.
    """
    found = set(re.findall(r"\{([A-Za-z_]\w*)\}", html))
    internal = {"PhotoURL", "PhotoLink"}
    return sorted(p for p in found if p not in internal and not p.startswith("EMBEDDED_IMAGE_"))


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
    image_map = {f"EMBEDDED_IMAGE_{i}": uri for i, uri in enumerate(image_data_uris, start=1)}
    html = reinject_embedded_images(html, image_map)

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


EDIT_SYSTEM_PROMPT = """You are editing an existing HTML/CSS document template for VolleyPacket, a platform that generates personalized PDF letters and invitations rendered with WeasyPrint.

You are given the CURRENT template HTML and a conversation describing the change the user wants. EDIT the existing document — do NOT rebuild it from scratch.

EDITING RULES:
- Make ONLY the change the user asks for. Preserve all other markup, text, structure, and styling exactly as-is.
- Keep every {EMBEDDED_IMAGE_N} placeholder (embedded logos/signatures/letterheads) and every {PhotoURL}/{PhotoLink} placeholder (per-row photos) intact and in place, unless the user explicitly asks to remove that image. NEVER invent or output base64 image data yourself.
- Keep {Placeholder} merge fields working. Use ONLY the spreadsheet columns provided as placeholder names — do not introduce placeholders for columns that don't exist.
- Keep the document a COMPLETE, single-page HTML document (<!DOCTYPE html> … </html>) with an @page rule for A4 sizing.

WEASYPRINT / PRINT CONSTRAINTS (rendered to PDF, not shown in a browser):
- All CSS stays in a <style> block in <head>. No external stylesheets, no web fonts.
- Use only system fonts: Arial, Helvetica, Georgia, Times New Roman, Courier New, Verdana, Tahoma.
- Avoid CSS WeasyPrint can't render (no reliance on flexbox/grid); prefer tables, block, inline-block, and floats for layout.
- The result must still fit on ONE page.

OUTPUT FORMAT:
Return ONLY a JSON object:
{
  "html_content": "<!DOCTYPE html>…</html>",
  "summary": "One short sentence describing what you changed."
}
The html_content must be the COMPLETE updated document. Return ONLY valid JSON — no markdown, no code fences, no explanation."""


def edit_template_with_ai(
    current_html: str,
    columns: list[str] = None,
    sample_rows: list[dict] = None,
    messages: list[dict] = None,
) -> tuple[str, str]:
    """Edit an existing template via AI (edit, don't regenerate).

    The job's columns + a few sample rows are passed as context, and the current
    HTML is the base the model modifies. Embedded base64 images are stripped to
    {EMBEDDED_IMAGE_N} before the model sees the HTML and re-injected into the
    result, so logos/signatures always survive an edit.

    `messages` is the client-held chat transcript ([{role, content}], short
    assistant summaries — not full HTML). Must end with a user turn.

    Returns (updated_html_with_images, summary).
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    stripped_html, image_map = strip_embedded_images(current_html or "")

    context_lines = []
    if columns:
        context_lines.append(
            "Spreadsheet columns available as placeholders (use ONLY these): "
            + ", ".join("{" + str(c) + "}" for c in columns)
        )
    if sample_rows:
        try:
            sample = json.dumps([dict(r) for r in sample_rows[:3]], indent=2, default=str)
            context_lines.append(f"Sample data rows (for realistic content):\n{sample}")
        except Exception:
            pass
    context_block = ("\n\n".join(context_lines) + "\n\n") if context_lines else ""

    base_user = (
        "Here is the current template you will edit. Apply the change(s) I describe "
        "next, keeping everything else intact.\n\n"
        f"{context_block}CURRENT TEMPLATE HTML:\n{stripped_html}"
    )

    api_messages = [
        {"role": "user", "content": base_user},
        {"role": "assistant", "content": "Got it — I have the current template and the available columns. What change would you like?"},
    ]
    for m in (messages or []):
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            api_messages.append({"role": role, "content": content})

    if api_messages[-1]["role"] != "user":
        raise ValueError("The conversation must end with a user instruction.")

    response = client.messages.create(
        model=config.AI_MODEL_TEMPLATE_EDIT,
        max_tokens=8192,
        system=EDIT_SYSTEM_PROMPT,
        messages=api_messages,
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    html = (data.get("html_content") or "").strip()
    if not html:
        raise ValueError("AI returned an empty template.")
    summary = (data.get("summary") or "").strip() or "Updated the template."

    html = reinject_embedded_images(html, image_map)
    return html, summary


# ── Ask Volley: email + SMS drafting ────────────────────────────────────────

def _ask_volley_messages(base_user: str, ack: str, messages: list) -> list:
    """Build the Anthropic messages[] for an Ask Volley turn: a base-context user
    turn + assistant ack, then the client-held transcript (must end with a user turn)."""
    api_messages = [
        {"role": "user", "content": base_user},
        {"role": "assistant", "content": ack},
    ]
    for m in (messages or []):
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            api_messages.append({"role": role, "content": content})
    if api_messages[-1]["role"] != "user":
        raise ValueError("The conversation must end with a user instruction.")
    return api_messages


def _parse_ai_json(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


def _columns_context(columns: list, sample_rows: list) -> str:
    lines = []
    if columns:
        lines.append(
            "Spreadsheet columns available as placeholders (use ONLY these): "
            + ", ".join("{" + str(c) + "}" for c in columns)
        )
    if sample_rows:
        try:
            lines.append("Sample data rows (for realistic content):\n"
                         + json.dumps([dict(r) for r in sample_rows[:3]], indent=2, default=str))
        except Exception:
            pass
    return ("\n\n".join(lines) + "\n\n") if lines else ""


EMAIL_SYSTEM_PROMPT = """You are "Ask Volley", the email assistant for VolleyPacket, a batch mail-merge platform.

You draft and refine an email's SUBJECT and HTML BODY that will be sent to many recipients via mail merge. You are given the current draft and a conversation — refine it to exactly what the user asks; do not rebuild from scratch unless they ask.

PLACEHOLDERS:
- Use {Column} merge fields from the spreadsheet columns provided — ONLY those names. Do not use {sender_name}/{sender_title} or any placeholder that isn't a real column.
- End with a simple closing (e.g. "Best regards,"). Do not invent a sender name or title — leave the sign-off for the user to fill in if they want one.

EMAIL HTML RULES (the body is an email, not a web page):
- The body is an HTML FRAGMENT — inner content only. No <html>/<head>/<body>/<style> tags and no external CSS.
- Inline styles only. Professional font stack: Arial, sans-serif. Text color #2C2C2C, line-height 1.6.
- Keep it clean and email-client-safe (divs/tables + inline styles).
- Include a small footer line "Powered by VolleyPacket.com" unless the user asks to remove it.

OUTPUT FORMAT — return ONLY a JSON object:
{
  "subject": "the subject line (may include placeholders)",
  "body": "the HTML fragment body",
  "summary": "one short sentence describing what you changed"
}
Return ONLY valid JSON — no markdown, no code fences, no explanation."""


def draft_email_with_ai(
    columns: list = None,
    sample_rows: list = None,
    current_subject: str = "",
    current_body: str = "",
    messages: list = None,
) -> tuple[str, str, str]:
    """Draft/refine an email (subject + HTML body) via Ask Volley. Returns (subject, body, summary)."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    current = (
        f"CURRENT SUBJECT:\n{current_subject or '(none yet)'}\n\n"
        f"CURRENT BODY (HTML fragment):\n{current_body or '(none yet)'}"
    )
    base_user = (
        "Here is the current email draft to edit/refine. Apply the change(s) I describe "
        "next, keeping the rest intact.\n\n" + _columns_context(columns, sample_rows) + current
    )
    api_messages = _ask_volley_messages(
        base_user,
        "Got it — I have the current email and the available columns. What would you like?",
        messages,
    )
    response = client.messages.create(
        model=config.AI_MODEL_EMAIL_SMS,
        max_tokens=4096,
        system=EMAIL_SYSTEM_PROMPT,
        messages=api_messages,
    )
    data = _parse_ai_json(response.content[0].text)
    subject = (data.get("subject") or "").strip()
    body = (data.get("body") or "").strip()
    if not body:
        raise ValueError("AI returned an empty email body.")
    summary = (data.get("summary") or "").strip() or "Updated the email."
    return subject, body, summary


SMS_SYSTEM_PROMPT = """You are "Ask Volley", the SMS assistant for VolleyPacket, a batch SMS platform.

You draft and refine ONE SMS message sent to many recipients via mail merge. You are given the current draft and a conversation — refine it to what the user asks.

RULES:
- SMS is PLAIN TEXT only — no HTML, no markdown, no emojis unless the user asks.
- Be concise. Aim for a single segment (~160 characters) unless the user wants longer; longer messages cost more segments.
- Use {Column} merge fields from the spreadsheet columns provided — ONLY those names.
- No links unless the user provides one. No "Powered by" footer.

OUTPUT FORMAT — return ONLY a JSON object:
{
  "body": "the plain-text SMS",
  "summary": "one short sentence describing what you changed"
}
Return ONLY valid JSON — no markdown, no code fences, no explanation."""


def draft_sms_with_ai(
    columns: list = None,
    sample_rows: list = None,
    current_body: str = "",
    messages: list = None,
) -> tuple[str, str]:
    """Draft/refine a plain-text SMS via Ask Volley. Returns (body, summary)."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    base_user = (
        "Here is the current SMS draft to edit/refine. Apply the change(s) I describe "
        "next, keeping the rest intact.\n\n"
        + _columns_context(columns, sample_rows)
        + f"CURRENT SMS:\n{current_body or '(none yet)'}"
    )
    api_messages = _ask_volley_messages(
        base_user,
        "Got it — I have the current SMS and the available columns. What would you like?",
        messages,
    )
    response = client.messages.create(
        model=config.AI_MODEL_EMAIL_SMS,
        max_tokens=1024,
        system=SMS_SYSTEM_PROMPT,
        messages=api_messages,
    )
    data = _parse_ai_json(response.content[0].text)
    body = (data.get("body") or "").strip()
    if not body:
        raise ValueError("AI returned an empty SMS body.")
    summary = (data.get("summary") or "").strip() or "Updated the SMS."
    return body, summary
