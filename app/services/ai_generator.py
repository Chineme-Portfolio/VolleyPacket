"""
AI-powered HTML template generation using Anthropic Claude.
Generates complete, self-contained HTML/CSS documents for PDF rendering.
"""

import json
import re
import anthropic

from app.models import TemplateConfig
from app import config


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
- Include a footer with the organization info and "Powered by VolleyPacket" credit.

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

Return ONLY valid JSON. No markdown, no explanation, no code fences."""


def generate_template_from_content(
    parsed_content: dict,
    instructions: str = None,
    columns: list[str] = None,
) -> TemplateConfig:
    """Generate an HTML template using AI."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    # Check if this is an image upload (vision mode)
    is_image = (
        parsed_content
        and parsed_content.get("detected_fields", {}).get("is_image")
    )

    # Build the message content blocks
    content_blocks = []

    if is_image:
        # Send image directly to Claude's vision
        fields = parsed_content.get("detected_fields", {})
        image_data = fields.get("image_data", "")
        media_type = fields.get("image_media_type", "image/png")

        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data,
            },
        })
        text_part = "Look at this document/template image carefully. Recreate it as a professional HTML/CSS template, matching the layout, styling, and structure as closely as possible. Replace any personal data or blank fields with {Placeholder} merge fields.\n\n"
    else:
        text_part = ""
        if parsed_content and parsed_content.get("raw_text"):
            text_part += f"Document content to base the template on:\n\n{json.dumps(parsed_content, indent=2)}\n\n"

    if columns:
        text_part += f"Available data columns from the spreadsheet: {', '.join(columns)}\n"
        text_part += f"Use these as placeholders: {', '.join('{' + c + '}' for c in columns)}\n\n"

    if instructions:
        text_part += f"User instructions:\n{instructions}\n"

    if not text_part.strip() and not is_image:
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

    # Also scan the HTML for any {Placeholder} patterns the AI used
    found = set(re.findall(r"\{([A-Za-z_]\w*)\}", html))
    # Filter out CSS/JS braces by only keeping capitalized or known patterns
    placeholders = sorted(
        set(declared_placeholders) | {p for p in found if p[0].isupper() or p in declared_placeholders}
    )

    return TemplateConfig(
        name=data.get("name", "Untitled Template"),
        description=data.get("description", ""),
        html_content=html,
        placeholders=placeholders,
    )
