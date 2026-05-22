"""
Template routes with ownership, visibility, and tier-gating.

Templates can be:
  - System templates (owner_id=null, owner_name="VolleyPacket")
  - User private templates (visibility="private")
  - User public templates (visibility="public", shared with everyone)
"""

import os
import json
import uuid

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from app.models import TemplateConfig, SaveTemplateRequest
from app.services.template_renderer import render_preview, render_html_preview
from app.services.storage import store
from app.database import get_session, UserRow, TemplateRow
from app.dependencies import get_current_user
from app.services.billing import get_user_tier, check_template_access, get_tier_limits
from app import config

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_id: Optional[str] = None
    owner_name: str = "VolleyPacket"
    visibility: str = "private"
    tier_required: str = "free"
    is_own: bool = False


class UpdateVisibilityRequest(BaseModel):
    visibility: str  # "public" or "private"


# ── Helpers ───────────────────────────────────────────────────────────


def _seed_system_templates():
    """Migrate file-based system templates into the database (runs once)."""
    if not os.path.isdir(config.TEMPLATE_FOLDER):
        return

    session = get_session()
    try:
        for filename in sorted(os.listdir(config.TEMPLATE_FOLDER)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(config.TEMPLATE_FOLDER, filename)
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                template_id = data.get("id", filename.replace(".json", ""))

                existing = session.get(TemplateRow, template_id)
                if existing:
                    continue

                session.add(TemplateRow(
                    id=template_id,
                    name=data.get("name", "Untitled"),
                    description=data.get("description", ""),
                    owner_id=None,
                    owner_name="VolleyPacket",
                    visibility="public",
                    tier_required="free",
                    config_json=json.dumps(data),
                ))
            except Exception:
                continue
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


# ── Routes ────────────────────────────────────────────────────────────


@router.get("")
def list_templates(
    filter: str = Query("all", pattern="^(all|mine|public|system)$"),
    user: UserRow = Depends(get_current_user),
):
    """
    List templates visible to the current user.
    Filters: all | mine | public | system
    """
    _seed_system_templates()

    user_tier = get_user_tier(user.id)

    session = get_session()
    try:
        query = session.query(TemplateRow)

        if filter == "mine":
            query = query.filter(TemplateRow.owner_id == user.id)
        elif filter == "public":
            query = query.filter(
                TemplateRow.visibility == "public",
                TemplateRow.owner_id != None,  # noqa: E711  — exclude system
            )
        elif filter == "system":
            query = query.filter(TemplateRow.owner_id == None)  # noqa: E711
        else:
            # "all" — show: own templates + public templates + system templates
            query = query.filter(
                (TemplateRow.owner_id == user.id) |
                (TemplateRow.visibility == "public") |
                (TemplateRow.owner_id == None)  # noqa: E711
            )

        rows = query.order_by(TemplateRow.created_at.desc()).all()

        templates = []
        for row in rows:
            # Tier gating: skip templates the user can't access
            if not check_template_access(user_tier, row.tier_required):
                continue

            templates.append(TemplateResponse(
                id=row.id,
                name=row.name,
                description=row.description,
                owner_id=row.owner_id,
                owner_name=row.owner_name,
                visibility=row.visibility,
                tier_required=row.tier_required,
                is_own=row.owner_id == user.id,
            ))

        return [t.model_dump() for t in templates]
    finally:
        session.close()


@router.get("/{template_id}")
def get_template(template_id: str, user: UserRow = Depends(get_current_user)):
    """Get a template's full config by ID."""
    session = get_session()
    try:
        row = session.get(TemplateRow, template_id)
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")

        # Access check: own template, public, or system
        if row.owner_id and row.owner_id != user.id and row.visibility != "public":
            raise HTTPException(status_code=403, detail="You don't have access to this template")

        # Tier check
        user_tier = get_user_tier(user.id)
        if not check_template_access(user_tier, row.tier_required):
            raise HTTPException(status_code=403, detail=f"This template requires the {row.tier_required} plan or higher")

        return json.loads(row.config_json)
    finally:
        session.close()


@router.get("/{template_id}/preview")
def preview_template(template_id: str, user: UserRow = Depends(get_current_user)):
    """Return an HTML preview of a template with placeholders highlighted."""
    from fastapi.responses import HTMLResponse

    session = get_session()
    try:
        row = session.get(TemplateRow, template_id)
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")

        template = TemplateConfig(**json.loads(row.config_json))
    finally:
        session.close()

    html = render_html_preview(template)
    return HTMLResponse(content=html, status_code=200)


@router.post("/save")
def save_template(request: SaveTemplateRequest, user: UserRow = Depends(get_current_user)):
    """Save or update a template. New templates are owned by the current user."""
    template = request.template
    template_id = template.id

    session = get_session()
    try:
        existing = session.get(TemplateRow, template_id)

        if existing:
            # Can only edit own templates
            if existing.owner_id and existing.owner_id != user.id:
                raise HTTPException(status_code=403, detail="You can only edit your own templates")
            if not existing.owner_id:
                raise HTTPException(status_code=403, detail="System templates cannot be modified")

            existing.name = template.name
            existing.description = template.description
            existing.config_json = json.dumps(template.model_dump())
            existing.updated_at = __import__("datetime").datetime.utcnow()
        else:
            # New template — user owns it
            session.add(TemplateRow(
                id=template_id,
                name=template.name,
                description=template.description,
                owner_id=user.id,
                owner_name=user.email.split("@")[0],
                visibility="private",
                tier_required="free",
                config_json=json.dumps(template.model_dump()),
            ))

        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Also save to disk for backward compatibility + S3 sync
    os.makedirs(config.TEMPLATE_FOLDER, exist_ok=True)
    path = os.path.join(config.TEMPLATE_FOLDER, f"{template.id}.json")
    with open(path, "w") as f:
        json.dump(template.model_dump(), f, indent=2)
    store.save_local_file(path)

    return {"message": "Template saved", "id": template.id}


@router.post("/{template_id}/visibility")
def update_visibility(
    template_id: str,
    req: UpdateVisibilityRequest,
    user: UserRow = Depends(get_current_user),
):
    """Toggle a template between public and private. Only the owner can do this."""
    if req.visibility not in ("public", "private"):
        raise HTTPException(status_code=400, detail="Visibility must be 'public' or 'private'")

    # Only classic+ can publish
    if req.visibility == "public":
        tier = get_user_tier(user.id)
        limits = get_tier_limits(tier)
        if not limits.get("can_publish_templates"):
            raise HTTPException(
                status_code=403,
                detail="Publishing templates requires the Classic plan or higher",
            )

    session = get_session()
    try:
        row = session.get(TemplateRow, template_id)
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        if row.owner_id != user.id:
            raise HTTPException(status_code=403, detail="You can only change visibility of your own templates")

        row.visibility = req.visibility
        row.updated_at = __import__("datetime").datetime.utcnow()
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {"message": f"Template is now {req.visibility}", "visibility": req.visibility}


@router.delete("/{template_id}")
def delete_template(template_id: str, user: UserRow = Depends(get_current_user)):
    """Delete a template. Only the owner can delete their templates."""
    session = get_session()
    try:
        row = session.get(TemplateRow, template_id)
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        if not row.owner_id:
            raise HTTPException(status_code=403, detail="System templates cannot be deleted")
        if row.owner_id != user.id:
            raise HTTPException(status_code=403, detail="You can only delete your own templates")

        session.delete(row)
        session.commit()
    except HTTPException:
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # Remove from disk and S3
    store.delete(f"templates/{template_id}.json")

    return {"message": "Template deleted"}
