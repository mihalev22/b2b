import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Correction, Item
from app.schemas.job import ItemCorrection, ItemOut

router = APIRouter(prefix="/items", tags=["items"])


@router.patch("/{item_id}", response_model=ItemOut)
async def correct_item(
    item_id: uuid.UUID,
    payload: ItemCorrection,
    session: AsyncSession = Depends(get_session),
) -> ItemOut:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Позиция не найдена")
    old_code = item.ktru_code
    item.ktru_code = payload.ktru_code
    if payload.ktru_name is not None:
        item.ktru_name = payload.ktru_name
    item.method = "manual"
    item.status = "corrected"
    session.add(
        Correction(
            item_id=item.id,
            job_id=item.job_id,
            old_code=old_code,
            new_code=payload.ktru_code,
        )
    )
    await session.commit()
    await session.refresh(item)
    return ItemOut.model_validate(item)
