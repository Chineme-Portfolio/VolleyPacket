import os

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse

from app.models import GenerateTemplateRequest, TemplateConfig
from app.services.ai_generator import generate_template_from_content
from app.services.template_renderer import render_preview
from app.services.storage import store
from app.dependencies import get_current_user
from app.database import UserRow
from app import config

router = APIRouter()


@router.post("-template")
def generate_template(request: GenerateTemplateRequest, user: UserRow = Depends(get_current_user)):
    try:
        template = generate_template_from_content(
            request.parsed_content,
            request.instructions,
        )
        return template.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@router.post("-template/preview")
def preview_generated_template(template: TemplateConfig, user: UserRow = Depends(get_current_user)):
    os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)
    preview_path = os.path.join(config.OUTPUT_FOLDER, f"preview_{template.id}.pdf")
    render_preview(template, preview_path)
    store.save_local_file(preview_path)
    return store.serve_inline(f"output/preview_{template.id}.pdf", media_type="application/pdf")
