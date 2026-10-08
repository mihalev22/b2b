from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.job import HealthComponent, HealthResponse

router = APIRouter(tags=["health"])


async def check_redis() -> tuple[bool, str]:
    import redis.asyncio as aioredis

    client = aioredis.from_url(get_settings().redis_url)
    try:
        pong = await client.ping()
        return bool(pong), "ok" if pong else "нет ответа"
    except Exception as exc:
        return False, f"redis недоступен: {type(exc).__name__}"
    finally:
        await client.aclose()


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    components: list[HealthComponent] = []
    try:
        await session.execute(text("SELECT 1"))
        components.append(HealthComponent(name="postgres", ok=True, detail="ok"))
    except Exception as exc:
        detail = f"база недоступна: {type(exc).__name__}"
        components.append(HealthComponent(name="postgres", ok=False, detail=detail))
    redis_ok, redis_detail = await check_redis()
    components.append(HealthComponent(name="redis", ok=redis_ok, detail=redis_detail))
    healthy = all(component.ok for component in components)
    body = HealthResponse(
        status="ok" if healthy else "error",
        version=get_settings().app_version,
        components=components,
    )
    return JSONResponse(status_code=200 if healthy else 503, content=body.model_dump())
