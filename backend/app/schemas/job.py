import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobCreated(BaseModel):
    job_id: uuid.UUID
    status: str
    filename: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: str
    total_count: int
    processed_count: int
    failed_count: int
    error: str | None
    parse_seconds: float | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobPage(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    row_number: int
    raw_name: str
    raw_columns: dict
    attributes: dict | None
    ktru_code: str | None
    ktru_name: str | None
    confidence: float | None
    method: str | None
    status: str
    updated_at: datetime


class ItemPage(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int


class ItemCorrection(BaseModel):
    ktru_code: str = Field(min_length=1, max_length=32)
    ktru_name: str | None = Field(default=None, max_length=512)


class HealthComponent(BaseModel):
    name: str
    ok: bool
    detail: str


class HealthResponse(BaseModel):
    status: str
    version: str
    components: list[HealthComponent]
