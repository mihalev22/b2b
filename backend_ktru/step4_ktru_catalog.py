"""Шаг 4: проверенный снимок КТРУ, а не выдуманные моделью коды."""
import argparse
import json
import os
import ssl
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

LOCAL = Path(os.getenv("KTRU_CATALOG", str(Path(__file__).parent / "data" / "ktru_catalog.json")))
OFFICIAL_CATALOG = "https://zakupki.gov.ru/epz/ktru/start/startPage.html"


def eis_client():
    """TLS проверяется всегда. Дополнительный CA задаётся администратором."""
    context = ssl.create_default_context()
    certificate = os.getenv("EIS_CA_BUNDLE")
    if certificate:
        context.load_verify_locations(cafile=certificate)
    return httpx.Client(verify=context, timeout=30, follow_redirects=False,
                        headers={"User-Agent": "KTRU-backend/1.0"})


def check_connection():
    """Проверка стартовой HTML-страницы, не загрузка каталога и не проверка кодов."""
    try:
        with eis_client() as client:
            response = client.get(OFFICIAL_CATALOG)
            if response.is_redirect:
                raise RuntimeError("ЕИС возвращает перенаправление: " +
                                   response.headers.get("location", "не указан адрес"))
            response.raise_for_status()
            return {"url": OFFICIAL_CATALOG, "status": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "catalog_downloaded": False}
    except httpx.HTTPError as error:
        raise RuntimeError("Не удалось подключиться к ЕИС с проверкой TLS. "
                           "Проверьте сеть, цепочку сертификатов и EIS_CA_BUNDLE. "
                           "Ошибка: " + str(error)) from error


class CatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^\d{2}\.\d{2}\.\d{2}\.\d{3}-\d{8}$")
    name: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=1500)
    attributes: dict[str, str] = Field(default_factory=dict, max_length=40)
    source_url: str
    active: bool


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: str
    exported_at: date
    items: list[CatalogItem] = Field(min_length=1)


def validate_catalog(data):
    catalog = Catalog.model_validate(data)
    urls = [catalog.source_url] + [item.source_url for item in catalog.items]
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "zakupki.gov.ru" or parsed.username:
            raise ValueError("Источником должна быть HTTPS-страница zakupki.gov.ru")
    if catalog.exported_at > date.today():
        raise ValueError("Дата выгрузки не может быть в будущем")
    codes = set()
    for item in catalog.items:
        if item.code in codes:
            raise ValueError("Повторяющийся код: " + item.code)
        codes.add(item.code)
    if not any(item.active for item in catalog.items):
        raise ValueError("В каталоге нет действующих позиций")
    # Схема и домен проверены, но подлинность содержания обязан проверить поставщик выгрузки.
    return catalog


def load_catalog():
    if not LOCAL.exists():
        raise RuntimeError("Нет проверенного каталога. Импортируйте снимок по инструкции README.")
    if LOCAL.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Каталог превышает 100 МБ")
    catalog = validate_catalog(json.loads(LOCAL.read_text(encoding="utf-8")))
    return [item.model_dump() for item in catalog.items if item.active]


def import_catalog(source):
    """Импорт нормализованного JSON. HTML-страницу ЕИС невозможно выдать за каталог."""
    source = Path(source)
    if source.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Каталог превышает 100 МБ")
    catalog = validate_catalog(json.loads(source.read_text(encoding="utf-8")))
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    temporary = LOCAL.with_suffix(".tmp")
    temporary.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(LOCAL)
    return len(catalog.items)


def refresh_catalog(url):
    """Только явно заданный HTTPS JSON-ресурс ЕИС, без неподтверждённого API."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "zakupki.gov.ru" or parsed.port not in (None, 443):
        raise ValueError("Разрешён только HTTPS-ресурс zakupki.gov.ru")
    data = bytearray()
    with eis_client() as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if "json" not in response.headers.get("content-type", ""):
                raise ValueError("Ресурс не возвращает JSON. Используйте импорт официальной выгрузки.")
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > 100 * 1024 * 1024:
                    raise ValueError("Каталог превышает 100 МБ")
    catalog = validate_catalog(json.loads(data))
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    temporary = LOCAL.with_suffix(".tmp")
    temporary.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(LOCAL)
    return len(catalog.items)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Импорт проверенного снимка КТРУ")
    parser.add_argument("source", nargs="?", help="Путь к нормализованному JSON каталога")
    parser.add_argument("--check", action="store_true", help="Проверить TLS-подключение к ЕИС")
    args = parser.parse_args()
    if args.check:
        try:
            print(json.dumps(check_connection(), ensure_ascii=False, indent=2))
        except (RuntimeError, OSError) as error:
            parser.exit(1, str(error) + "\n")
    elif args.source:
        print("Импортировано позиций:", import_catalog(args.source))
    else:
        parser.error("Укажите source или --check")
