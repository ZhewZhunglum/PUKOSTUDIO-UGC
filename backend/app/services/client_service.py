import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.pagination import PaginationParams, paginate
from app.models.client import Client, ClientRelationshipType, ClientStatus
from app.schemas.client import ClientCreate, ClientUpdate

_VALID_RELATIONSHIP_TYPES = {t.value for t in ClientRelationshipType}


async def list_clients(
    db: AsyncSession,
    team_id: uuid.UUID,
    params: PaginationParams,
    search: str | None = None,
    status: str | None = None,
    relationship_type: str | None = None,
    industry: str | None = None,
    source: str | None = None,
) -> dict:
    query = select(Client).where(Client.team_id == team_id)

    if search:
        query = query.where(
            or_(
                Client.company_name.ilike(f"%{search}%"),
                Client.contact_name.ilike(f"%{search}%"),
                Client.email.ilike(f"%{search}%"),
            )
        )
    if status:
        query = query.where(Client.status == status)
    if relationship_type:
        query = query.where(Client.relationship_type == relationship_type)
    if industry:
        query = query.where(Client.industry == industry)
    if source:
        query = query.where(Client.source == source)

    query = query.order_by(Client.created_at.desc())
    return await paginate(db, query, params)


async def get_client(db: AsyncSession, client_id: uuid.UUID, team_id: uuid.UUID) -> Client:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.team_id == team_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise NotFoundException("Client not found")
    return client


async def create_client(db: AsyncSession, team_id: uuid.UUID, data: ClientCreate) -> Client:
    if data.relationship_type not in _VALID_RELATIONSHIP_TYPES:
        raise BadRequestException(f"Invalid relationship_type: {data.relationship_type}")

    client = Client(
        team_id=team_id,
        company_name=data.company_name,
        contact_name=data.contact_name,
        title=data.title,
        email=data.email,
        phone=data.phone,
        industry=data.industry,
        website=data.website,
        relationship_type=ClientRelationshipType(data.relationship_type),
        notes=data.notes,
        source=data.source,
    )
    db.add(client)
    await db.flush()
    return client


async def update_client(
    db: AsyncSession, client_id: uuid.UUID, team_id: uuid.UUID, data: ClientUpdate
) -> Client:
    client = await get_client(db, client_id, team_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "relationship_type" and value is not None:
            setattr(client, field, ClientRelationshipType(value))
        elif field == "status" and value is not None:
            setattr(client, field, ClientStatus(value))
        else:
            setattr(client, field, value)

    await db.flush()
    return client


async def delete_client(db: AsyncSession, client_id: uuid.UUID, team_id: uuid.UUID) -> None:
    client = await get_client(db, client_id, team_id)
    await db.delete(client)


async def import_clients_from_rows(
    db: AsyncSession, team_id: uuid.UUID, rows: list[dict]
) -> dict:
    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows):
        try:
            company_name = (row.get("company_name") or "").strip()
            email = (row.get("email") or "").strip() or None

            if not company_name:
                errors.append(f"Row {i + 1}: Missing company_name")
                skipped += 1
                continue

            relationship_type = (row.get("relationship_type") or "").strip().lower() or "buyer"
            if relationship_type not in _VALID_RELATIONSHIP_TYPES:
                relationship_type = "buyer"

            if email:
                existing = await db.execute(
                    select(Client).where(Client.email == email, Client.team_id == team_id)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

            client = Client(
                team_id=team_id,
                company_name=company_name,
                contact_name=(row.get("contact_name") or "").strip() or None,
                title=(row.get("title") or "").strip() or None,
                email=email,
                phone=(row.get("phone") or "").strip() or None,
                industry=(row.get("industry") or "").strip() or None,
                website=(row.get("website") or "").strip() or None,
                relationship_type=ClientRelationshipType(relationship_type),
                notes=(row.get("notes") or "").strip() or None,
                source="csv_import",
            )
            db.add(client)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i + 1}: {str(e)}")
            skipped += 1

    await db.flush()
    return {"total_rows": len(rows), "imported": imported, "skipped": skipped, "errors": errors}
