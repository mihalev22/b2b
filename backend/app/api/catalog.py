from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.job import KtruPositionOut, KtruSearchPage

router = APIRouter(prefix="/ktru", tags=["catalog"])


@router.get("/search", response_model=KtruSearchPage)
async def search_catalog(
    session: AsyncSession = Depends(get_session),
    q: str = Query(..., min_length=2, max_length=256),
    limit: int = Query(default=10, ge=1, le=50),
) -> KtruSearchPage:
    raise HTTPException(
        501,
        "Поиск по каталогу КТРУ будет подключён после загрузки справочника (модуль инженера БД)",
    )


@router.get("/{ktru_code}", response_model=KtruPositionOut)
async def get_position(
    ktru_code: str,
    session: AsyncSession = Depends(get_session),
) -> KtruPositionOut:
    raise HTTPException(
        501,
        "Карточка позиции КТРУ будет подключена после загрузки справочника (модуль инженера БД)",
    )
