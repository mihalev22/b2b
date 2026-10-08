from fastapi import APIRouter

from app.api import catalog, health, items, jobs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(jobs.router)
api_router.include_router(items.router)
api_router.include_router(catalog.router)
