import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api import health as api_health
from app.api import jobs as api_jobs
from app.core.config import get_settings
from app.db import session as db_session
from app.db.session import get_session
from app.main import app
from app.models.entities import Base
from app.workers.tasks import run_job


@pytest.fixture
def sync_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch, sync_factory):
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "AsyncSessionLocal", async_factory)

    async def override_session():
        async with async_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    settings = get_settings()
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path / "uploads"))

    async def fake_check_redis():
        return True, "ok"

    monkeypatch.setattr(api_health, "check_redis", fake_check_redis)

    def immediate_process(job_id):
        run_job(job_id, sync_factory)

    monkeypatch.setattr(api_jobs, "enqueue_process_job", immediate_process)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    await async_engine.dispose()


CSV_CONTENT = (
    "№;Наименование товара;Кол-во\n"
    "1;Ноутбук Dell Latitude 5540;1\n"
    "2;Кабель ПВС 3х1.5;10\n"
    ";Итого;11\n"
).encode()
