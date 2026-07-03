from dataclasses import dataclass
from math import ceil

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class PaginationParams:
    page: int = 1
    per_page: int = 20


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=1000, description="Items per page"),
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)


async def paginate(db: AsyncSession, query: Select, params: PaginationParams) -> dict:
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    paginated = query.offset((params.page - 1) * params.per_page).limit(params.per_page)
    result = await db.execute(paginated)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": params.page,
        "per_page": params.per_page,
        "pages": ceil(total / params.per_page) if params.per_page > 0 else 0,
    }
