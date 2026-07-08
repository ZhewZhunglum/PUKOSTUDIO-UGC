import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tabular import normalize_format, parse_tabular, tabular_response
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.template import (
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services import template_service

router = APIRouter()


class ConvertRequest(BaseModel):
    raw_subject: str = Field(default="", max_length=500)
    raw_body: str = Field(..., min_length=1, max_length=20000)
    use_ai: bool = False


class ConvertResponse(BaseModel):
    subject: str
    body_html: str
    variables: list[str]
    method: str  # "rule" | "ai"


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.list_templates(db, current_user.team_id)


@router.get("/export")
async def export_templates(
    format: str = Query("csv"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fmt = normalize_format(format)
    templates = await template_service.list_templates(db, current_user.team_id)
    columns = template_service.TEMPLATE_EXPORT_COLUMNS
    rows = [
        [
            t.name,
            t.subject,
            t.body_html,
            t.body_text or "",
            t.category.value if t.category else "",
            t.language or "",
        ]
        for t in templates
    ]
    return tabular_response(
        fmt=fmt,
        filename_stem="templates",
        headers=columns,
        rows=rows,
        sheet_title="Templates",
    )


@router.post("/import")
async def import_templates(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    rows = parse_tabular(file.filename, content)
    return await template_service.import_templates_from_rows(
        db, current_user.team_id, rows
    )


@router.get("/library", response_model=list[TemplateResponse])
async def list_library_templates(
    language: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.list_library_templates(
        db, current_user.team_id, language
    )


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.create_template(db, current_user.team_id, data)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.get_template(db, template_id, current_user.team_id)


@router.post("/{template_id}/clone", response_model=TemplateResponse, status_code=201)
async def clone_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.clone_template(db, template_id, current_user.team_id)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await template_service.update_template(
        db, template_id, current_user.team_id, data
    )


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await template_service.delete_template(db, template_id, current_user.team_id)


@router.post("/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    data: TemplatePreviewRequest,
    finalize: bool = Query(False, description="Run CSS-inlining to preview final send-ready HTML"),
):
    subject, body = template_service.render_template(
        data.subject, data.body_html, data.variables
    )
    if finalize:
        from app.integrations.email.manager import finalize_html_for_send

        body = finalize_html_for_send(body)
    return {"subject": subject, "body_html": body}


@router.post("/convert", response_model=ConvertResponse)
async def convert_template(
    data: ConvertRequest,
    current_user: User = Depends(get_current_user),
):
    if data.use_ai:
        try:
            result = await template_service.ai_convert(data.raw_subject, data.raw_body)
            return result
        except Exception:
            # Fall back to rule-based if AI fails
            pass
    return template_service.rule_convert(data.raw_subject, data.raw_body)
