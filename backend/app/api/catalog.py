from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.job import KtruPositionOut, KtruSearchPage

router = APIRouter(prefix="/ktru", tags=["catalog"])

SEARCH_SQL = text(
    "SELECT code, name, okpd2_code FROM ktru_position "
    "WHERE lower(name) LIKE lower(:pattern) "
    "   OR lower(code) LIKE lower(:pattern) "
    "   OR lower(okpd2_code) LIKE lower(:pattern) "
    "ORDER BY code LIMIT :lim"
)

COUNT_SQL = text(
    "SELECT COUNT(*) FROM ktru_position "
    "WHERE lower(name) LIKE lower(:pattern) "
    "   OR lower(code) LIKE lower(:pattern) "
    "   OR lower(okpd2_code) LIKE lower(:pattern)"
)

GET_SQL = text(
    "SELECT code, name, okpd2_code FROM ktru_position WHERE code = :code"
)


def like_pattern(query: str) -> str:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/search", response_model=KtruSearchPage)
async def search_catalog(
    session: AsyncSession = Depends(get_session),
    q: str = Query(..., min_length=2, max_length=256),
    limit: int = Query(default=10, ge=1, le=50),
) -> KtruSearchPage:
    pattern = like_pattern(q.strip())
    count_result = await session.execute(COUNT_SQL, {"pattern": pattern})
    total = count_result.scalar() or 0

    rows = await session.execute(SEARCH_SQL, {"pattern": pattern, "lim": limit})
    items = [
        KtruPositionOut(ktru_code=row[0], ktru_name=row[1], okpd2_code=row[2])
        for row in rows
    ]
    return KtruSearchPage(items=items, total=total, limit=limit)


@router.get("/{ktru_code}", response_model=KtruPositionOut)
async def get_position(
    ktru_code: str,
    session: AsyncSession = Depends(get_session),
) -> KtruPositionOut:
    rows = await session.execute(GET_SQL, {"code": ktru_code})
    row = rows.first()
    if row is None:
        raise HTTPException(404, "Позиция КТРУ не найдена")
    return KtruPositionOut(ktru_code=row[0], ktru_name=row[1], okpd2_code=row[2])
