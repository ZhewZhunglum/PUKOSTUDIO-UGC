import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import PaginationParams, get_pagination
from app.core.tabular import normalize_format, parse_tabular, tabular_response
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.client import (
    ClientCreate,
    ClientImportResponse,
    ClientListResponse,
    ClientResponse,
    ClientUpdate,
)
from app.services import client_service

router = APIRouter()


@router.get("", response_model=ClientListResponse)
async def list_clients(
    search: str | None = Query(None),
    status: str | None = Query(None),
    relationship_type: str | None = Query(None),
    industry: str | None = Query(None),
    source: str | None = Query(None),
    pagination: PaginationParams = Depends(get_pagination),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_service.list_clients(
        db,
        team_id=current_user.team_id,
        params=pagination,
        search=search,
        status=status,
        relationship_type=relationship_type,
        industry=industry,
        source=source,
    )


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_service.create_client(db, current_user.team_id, data)


@router.post("/import", response_model=ClientImportResponse)
async def import_clients(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    rows = parse_tabular(file.filename, content)
    return await client_service.import_clients_from_rows(db, current_user.team_id, rows)


@router.get("/export")
async def export_clients(
    format: str = Query("csv"),
    search: str | None = Query(None),
    status: str | None = Query(None),
    relationship_type: str | None = Query(None),
    industry: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.config import settings

    fmt = normalize_format(format)
    BATCH_SIZE = 500
    headers = [
        "company_name", "contact_name", "title", "email", "phone",
        "industry", "website", "relationship_type", "status", "source", "created_at",
    ]

    rows: list[list] = []
    page = 1
    while len(rows) < settings.export_max_rows:
        result = await client_service.list_clients(
            db,
            team_id=current_user.team_id,
            params=PaginationParams(page=page, per_page=BATCH_SIZE),
            search=search,
            status=status,
            relationship_type=relationship_type,
            industry=industry,
        )
        items = result["items"]
        if not items:
            break
        for c in items:
            rows.append([
                c.company_name,
                c.contact_name or "",
                c.title or "",
                c.email or "",
                c.phone or "",
                c.industry or "",
                c.website or "",
                c.relationship_type.value,
                c.status.value,
                c.source or "",
                c.created_at.isoformat() if c.created_at else "",
            ])
        if len(items) < BATCH_SIZE:
            break
        page += 1

    return tabular_response(
        fmt=fmt,
        filename_stem="clients",
        headers=headers,
        rows=rows[: settings.export_max_rows],
        sheet_title="Clients",
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_service.get_client(db, client_id, current_user.team_id)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await client_service.update_client(db, client_id, current_user.team_id, data)


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await client_service.delete_client(db, client_id, current_user.team_id)
