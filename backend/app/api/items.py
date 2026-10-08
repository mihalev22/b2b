import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Correction, Item
from app.schemas.job import ItemCorrection, ItemOut

router = APIRouter(prefix="/items", tags=["items"])


async def get_item_or_404(session: AsyncSession, item_id: uuid.UUID) -> Item:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "Позиция не найдена")
    return item


@router.patch("/{item_id}", response_model=ItemOut)
async def correct_item(
    item_id: uuid.UUID,
    payload: ItemCorrection,
    session: AsyncSession = Depends(get_session),
) -> ItemOut:
    item = await get_item_or_404(session, item_id)
    old_code = item.ktru_code
    previous_status = item.status
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
            previous_status=previous_status,
        )
    )
    await session.commit()
    await session.refresh(item)
    return ItemOut.model_validate(item)


@router.post("/{item_id}/accept", response_model=ItemOut)
async def accept_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ItemOut:
    item = await get_item_or_404(session, item_id)
    if item.status == "pending":
        raise HTTPException(409, "Позиция ещё не обработана, принять нельзя")
    item.status = "accepted"
    await session.commit()
    await session.refresh(item)
    return ItemOut.model_validate(item)


@router.post("/{item_id}/revert", response_model=ItemOut)
async def revert_item(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ItemOut:
    item = await get_item_or_404(session, item_id)
    stmt = (
        select(Correction)
        .where(Correction.item_id == item_id)
        .order_by(Correction.created_at.desc(), Correction.id.desc())
        .limit(1)
    )
    correction = (await session.scalars(stmt)).first()
    if correction is None:
        raise HTTPException(409, "У позиции нет правок, отменять нечего")
    item.ktru_code = correction.old_code
    item.status = correction.previous_status or "needs_review"
    if item.method == "manual":
        item.method = None
    await session.delete(correction)
    await session.commit()
    await session.refresh(item)
    return ItemOut.model_validate(item)
