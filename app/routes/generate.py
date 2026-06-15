import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.models import GenerateTemplateRequest, TemplateConfig
from app.services.ai_generator import generate_template_from_content, edit_template_with_ai
from app.services.template_renderer import render_preview, render_html_preview
from app.services.storage import store
from app.services.billing import check_ai_limit, increment_ai_usage
from app.dependencies import get_current_user
from app.database import UserRow
from app import config

router = APIRouter()


@router.post("-template")
def generate_template(request: GenerateTemplateRequest, user: UserRow = Depends(get_current_user)):
    # Check AI usage limit
    allowed, current, limit = check_ai_limit(user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {limit} AI messages this month. Upgrade your plan for more.",
        )

    # Normalize: support both singular parsed_content and plural parsed_contents
    contents = request.parsed_contents or []
    if request.parsed_content:
        contents.insert(0, request.parsed_content)

    try:
        template = generate_template_from_content(
            contents,
            request.instructions,
            request.columns,
        )
        increment_ai_usage(user.id)
        return template.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@router.post("-template/preview")
def preview_generated_template(template: TemplateConfig, user: UserRow = Depends(get_current_user)):
    """Return an HTML preview with placeholders highlighted."""
    html = render_html_preview(template)
    return HTMLResponse(content=html, status_code=200)


class _ChatTurn(BaseModel):
    role: str
    content: str


class TemplateEditRequest(BaseModel):
    html_content: str = ""
    messages: list[_ChatTurn] = []
    columns: Optional[list[str]] = None


@router.post("-template/edit")
def edit_generated_template(req: TemplateEditRequest, user: UserRow = Depends(get_current_user)):
    """Refine a draft template via AI (edit, don't regenerate). Quota-gated.

    Stateless sibling of the in-job editor's ai-edit — operates on raw html_content
    so the new-template builder can refine a draft before it's ever saved.
    """
    allowed, current, limit = check_ai_limit(user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"You've used all {limit} AI messages this month. Upgrade your plan for more.",
        )
    try:
        new_html, summary = edit_template_with_ai(
            current_html=req.html_content,
            columns=req.columns or [],
            sample_rows=[],
            messages=[m.model_dump() for m in req.messages],
            allow_redesign=True,
        )
        increment_ai_usage(user.id)
        return {"html_content": new_html, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI edit failed: {e}")
