from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/ktru", tags=["catalog"])


@router.get("/search")
async def search_catalog(
    q: str = Query(..., min_length=2, max_length=256),
    limit: int = Query(default=10, ge=1, le=50),
) -> None:
    raise HTTPException(
        501,
        "Поиск по каталогу КТРУ будет подключён после загрузки справочника (модуль инженера БД)",
    )
