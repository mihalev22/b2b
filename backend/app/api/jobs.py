import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger, set_job_context
from app.db.session import get_session
from app.models.entities import Item, Job
from app.schemas.job import (
    BulkAccept,
    BulkAcceptResult,
    ExportFormat,
    ItemPage,
    JobCreated,
    JobOut,
    JobPage,
    SortField,
    SortOrder,
)
from app.services.exporter import items_to_csv, items_to_xlsx
from app.services.queue import enqueue_process_job
from app.services.storage import (
    BadFileContent,
    UploadTooLarge,
    check_magic,
    save_upload,
    upload_path,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

ALLOWED_EXTENSIONS = {".xlsx", ".csv"}
COUNTED_STATUSES = ("auto", "needs_review", "corrected")


async def status_counts(
    session: AsyncSession, job_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    if not job_ids:
        return {}
    stmt = (
        select(Item.job_id, Item.status, func.count())
        .where(Item.job_id.in_(job_ids), Item.status.in_(COUNTED_STATUSES))
        .group_by(Item.job_id, Item.status)
    )
    result: dict[uuid.UUID, dict[str, int]] = {job_id: {} for job_id in job_ids}
    for job_id, status, count in await session.execute(stmt):
        result[job_id][status] = count
    return result


def job_to_out(job: Job, counts: dict[str, int]) -> JobOut:
    return JobOut(
        id=job.id,
        filename=job.filename,
        status=job.status,
        total_count=job.total_count,
        processed_count=job.processed_count,
        failed_count=job.failed_count,
        auto_count=counts.get("auto", 0),
        needs_review_count=counts.get("needs_review", 0),
        corrected_count=counts.get("corrected", 0),
        error=job.error,
        parse_seconds=job.parse_seconds,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post("", status_code=202, response_model=JobCreated)
async def create_job(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    settings = get_settings()
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Ожидается файл спецификации в формате .xlsx или .csv")

    job = Job(filename=filename, file_ext=extension)
    session.add(job)
    await session.flush()

    destination = upload_path(job)
    try:
        await save_upload(file, destination, settings.max_upload_mb * 1024 * 1024)
        await check_magic(destination, extension)
    except UploadTooLarge:
        destination.unlink(missing_ok=True)
        await session.rollback()
        raise HTTPException(413, f"Файл больше {settings.max_upload_mb} МБ") from None
    except BadFileContent as exc:
        destination.unlink(missing_ok=True)
        await session.rollback()
        raise HTTPException(422, str(exc)) from None
    set_job_context(job.id)
    await session.commit()

    try:
        enqueue_process_job(job.id)
    except Exception:
        job.status = "failed"
        job.error = "Не удалось поставить задание в очередь"
        await session.commit()
        logger.exception("enqueue failed")
        raise HTTPException(503, "Очередь задач недоступна, попробуйте позже") from None

    logger.info("job created: file=%s, size_limit=%sMB", filename, settings.max_upload_mb)
    return JobCreated(job_id=job.id, status=job.status, filename=filename)


@router.get("", response_model=JobPage)
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobPage:
    total = await session.scalar(select(func.count()).select_from(Job))
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    jobs = (await session.scalars(stmt)).all()
    counts = await status_counts(session, [job.id for job in jobs])
    return JobPage(
        items=[job_to_out(job, counts.get(job.id, {})) for job in jobs],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


async def get_job_or_404(session: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    return job


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> JobOut:
    job = await get_job_or_404(session, job_id)
    counts = await status_counts(session, [job.id])
    return job_to_out(job, counts.get(job.id, {}))


@router.get("/{job_id}/items", response_model=ItemPage)
async def list_items(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, max_length=32),
    min_confidence: float | None = Query(default=None, ge=0, le=100),
    max_confidence: float | None = Query(default=None, ge=0, le=100),
    q: str | None = Query(default=None, max_length=256),
    sort_by: SortField = Query(default="row_number"),
    sort_order: SortOrder = Query(default="asc"),
) -> ItemPage:
    await get_job_or_404(session, job_id)
    filters = [Item.job_id == job_id]
    if status:
        filters.append(Item.status == status)
    if min_confidence is not None:
        filters.append(Item.confidence >= min_confidence)
    if max_confidence is not None:
        filters.append(Item.confidence <= max_confidence)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters.append(Item.raw_name.ilike(f"%{escaped}%", escape="\\"))
    total = await session.scalar(select(func.count()).select_from(Item).where(*filters))
    column = {
        "row_number": Item.row_number,
        "confidence": Item.confidence,
        "updated_at": Item.updated_at,
    }[sort_by]
    order = column.asc() if sort_order == "asc" else column.desc()
    stmt = select(Item).where(*filters).order_by(order).limit(limit).offset(offset)
    items = (await session.scalars(stmt)).all()
    return ItemPage(items=list(items), total=total or 0, limit=limit, offset=offset)


@router.post("/{job_id}/accept", response_model=BulkAcceptResult)
async def accept_items(
    job_id: uuid.UUID,
    payload: BulkAccept,
    session: AsyncSession = Depends(get_session),
) -> BulkAcceptResult:
    await get_job_or_404(session, job_id)
    stmt = (
        select(func.count())
        .select_from(Item)
        .where(
            Item.job_id == job_id,
            Item.confidence >= payload.min_confidence,
            Item.status.in_(("auto", "needs_review")),
        )
    )
    count = await session.scalar(stmt) or 0
    if count:
        await session.execute(
            Item.__table__.update()
            .where(
                Item.job_id == job_id,
                Item.confidence >= payload.min_confidence,
                Item.status.in_(("auto", "needs_review")),
            )
            .values(status="accepted")
        )
        await session.commit()
    return BulkAcceptResult(accepted_count=count)


@router.get("/{job_id}/export")
async def export_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    format: ExportFormat = Query(default="csv"),
) -> Response:
    job = await get_job_or_404(session, job_id)
    stmt = select(Item).where(Item.job_id == job_id).order_by(Item.row_number)
    items = (await session.scalars(stmt)).all()
    if format == "xlsx":
        return Response(
            content=items_to_xlsx(items),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="job_{job.id}.xlsx"'},
        )
    return Response(
        content=items_to_csv(items),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="job_{job.id}.csv"'},
    )
