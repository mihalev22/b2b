from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.core.config import get_settings
from app.models.entities import Job


class UploadTooLarge(Exception):
    pass


class BadFileContent(Exception):
    pass


async def check_magic(destination: Path, extension: str) -> None:
    if extension != ".xlsx":
        return
    async with aiofiles.open(destination, "rb") as source:
        header = await source.read(2)
    if header != b"PK":
        raise BadFileContent("Файл повреждён или не является корректным xlsx")


def upload_path(job: Job) -> Path:
    return Path(get_settings().uploads_dir) / f"{job.id}{job.file_ext}"


async def save_upload(source: UploadFile, destination: Path, max_bytes: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    async with aiofiles.open(destination, "wb") as output:
        while chunk := await source.read(512 * 1024):
            written += len(chunk)
            if written > max_bytes:
                raise UploadTooLarge
            await output.write(chunk)
    return written
