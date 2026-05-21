"""
AI-powered email content generation.
Uses Anthropic Claude to generate email subject + body based on user instructions.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app import config
from app.database import UserRow
from app.dependencies import get_current_user
from app.services.billing import check_ai_limit, increment_ai_usage

router = APIRouter()


class GenerateEmailRequest(BaseModel):
    prompt: str  # User's description of what email they want
    columns: list[str] = []  # Available column names from the spreadsheet
    context: str = ""  # Optional: previous AI response for refinement


class GenerateEmailResponse(BaseModel):
    subject: str
    body: str  # HTML with placeholders


@router.post("/generate", response_model=GenerateEmailResponse)
def generate_email_content(req: GenerateEmailRequest, user: UserRow = Depends(get_current_user)):
    """Generate email subject and HTML body using AI."""
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="AI features require an Anthropic API key")

    # Check AI usage limit
    allowed, current, limit = check_ai_limit(user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {limit} AI messages this month. Upgrade your plan for more.",
        )

    try:
        import anthropic
    except ImportError:
        raise HTTPException(status_code=503, detail="anthropic package not installed")

    # Build available placeholders from columns
    placeholders = ", ".join(f"{{{col}}}" for col in req.columns) if req.columns else "{Name}, {Email}"

    system_prompt = f"""You are an email content generator for VolleyPacket, a batch email platform.

Generate a professional email with an HTML body. The email will be sent to multiple recipients using mail merge.

AVAILABLE PLACEHOLDERS (from spreadsheet columns): {placeholders}
Also available: {{sender_name}}, {{sender_title}}

RULES:
- Return ONLY valid JSON with "subject" and "body" keys
- "subject" should be a concise email subject line (can include placeholders)
- "body" should be clean HTML email content with inline styles
- Use placeholders like {{Name}} to personalize
- Keep the HTML simple — use inline styles, no external CSS
- Use a professional font stack: Arial, sans-serif
- Body color: #2C2C2C, line-height: 1.6
- Do NOT include <html> or <head> tags — just the <body> inner content wrapped in a div
- End with a signature using {{sender_name}} and {{sender_title}}"""

    user_prompt = req.prompt
    if req.context:
        user_prompt = f"Previous version:\n{req.context}\n\nUser's refinement request:\n{req.prompt}"

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text.strip()

        # Parse JSON from response
        import json
        # Handle markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)

        subject = result.get("subject", "")
        body = result.get("body", "")

        # Wrap in html/body if not present
        if "<html" not in body.lower():
            body = f"""<html>
<body style="font-family: Arial, sans-serif; color: #2C2C2C; line-height: 1.6;">
{body}
</body>
</html>"""

        increment_ai_usage(user.id)
        return GenerateEmailResponse(subject=subject, body=body)

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid JSON. Please try again.")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
