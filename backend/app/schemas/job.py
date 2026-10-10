import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal["queued", "processing", "done", "failed"]
ItemStatus = Literal["pending", "auto", "needs_review", "accepted", "corrected", "failed"]
SortField = Literal["row_number", "confidence", "updated_at"]
SortOrder = Literal["asc", "desc"]
ExportFormat = Literal["csv", "xlsx"]


class Characteristic(BaseModel):
    name: str
    value: str
    unit: str | None = None


class ItemAttributes(BaseModel):
    name: str
    brand: str | None = None
    model: str | None = None
    characteristics: list[Characteristic] = Field(default_factory=list)

    @field_validator("brand", "model", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        return None if value in (None, "") else value


class CandidateOut(BaseModel):
    ktru_code: str
    ktru_name: str | None = None
    confidence: float


class JobCreated(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "c82cc353-9233-4ba2-8270-4f0139f37774",
                "status": "queued",
                "filename": "spec.csv",
            }
        }
    )

    job_id: uuid.UUID
    status: JobStatus
    filename: str


class JobOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "c82cc353-9233-4ba2-8270-4f0139f37774",
                "filename": "spec.csv",
                "status": "done",
                "total_count": 4,
                "processed_count": 4,
                "failed_count": 0,
                "auto_count": 3,
                "needs_review_count": 1,
                "corrected_count": 0,
                "error": None,
                "parse_seconds": 0.019,
                "created_at": "2026-10-05T15:41:27.454156Z",
                "started_at": "2026-10-05T15:41:27.792843Z",
                "finished_at": "2026-10-05T15:41:27.817763Z",
            }
        }
    )

    id: uuid.UUID
    filename: str
    status: JobStatus
    total_count: int
    processed_count: int
    failed_count: int
    auto_count: int = 0
    needs_review_count: int = 0
    corrected_count: int = 0
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
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "01aaa595-b008-4229-8a74-c3ac387f0261",
                "job_id": "c82cc353-9233-4ba2-8270-4f0139f37774",
                "row_number": 2,
                "raw_name": "Ноутбук Dell Latitude 5540 16 ГБ",
                "raw_columns": {"№": "1", "Наименование товара": "Ноутбук Dell"},
                "attributes": {
                    "name": "Ноутбук",
                    "brand": "Dell",
                    "model": "Latitude 5540",
                    "characteristics": [{"name": "ОЗУ", "value": "16", "unit": "ГБ"}],
                },
                "ktru_code": "26.20.11.110-00000009",
                "ktru_name": "Машины вычислительные портативные",
                "confidence": 94.0,
                "method": "hybrid",
                "status": "auto",
                "candidates": [
                    {
                        "ktru_code": "26.20.11.110-00000009",
                        "ktru_name": "Машины вычислительные портативные",
                        "confidence": 94.0,
                    }
                ],
                "updated_at": "2026-10-05T15:41:27.812874Z",
            }
        }
    )

    id: uuid.UUID
    job_id: uuid.UUID
    row_number: int
    raw_name: str
    raw_columns: dict
    attributes: ItemAttributes | None = None
    ktru_code: str | None
    ktru_name: str | None
    confidence: float | None
    method: str | None
    status: ItemStatus
    candidates: list[CandidateOut] = Field(default_factory=list)
    failure_reason: str | None = None
    updated_at: datetime

    @field_validator("candidates", mode="before")
    @classmethod
    def none_candidates(cls, value):
        return [] if value is None else value


class ItemPage(BaseModel):
    items: list[ItemOut]
    total: int
    limit: int
    offset: int


class ItemCorrection(BaseModel):
    ktru_code: str = Field(min_length=1, max_length=32)
    ktru_name: str | None = Field(default=None, max_length=512)


class BulkAccept(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"min_confidence": 85}})

    min_confidence: float = Field(
        ge=0,
        le=100,
        description="Принять все позиции с уверенностью не ниже",
    )


class BulkAcceptResult(BaseModel):
    accepted_count: int


class KtruPositionOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ktru_code": "26.20.11.110-00000009",
                "ktru_name": "Машины вычислительные портативные",
                "okpd2_code": "26.20.11.110",
                "characteristics": [{"name": "масса", "value": "не более 10", "unit": "кг"}],
            }
        }
    )

    ktru_code: str
    ktru_name: str
    okpd2_code: str | None = None
    characteristics: list[Characteristic] = Field(default_factory=list)


class KtruSearchPage(BaseModel):
    items: list[KtruPositionOut]
    total: int
    limit: int


class HealthComponent(BaseModel):
    name: str
    ok: bool
    detail: str


class HealthResponse(BaseModel):
    status: str
    version: str
    components: list[HealthComponent]
