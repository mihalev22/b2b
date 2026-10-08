"""HTTP-обвязка шести шагов. Тяжёлая обработка выполняется вне event loop."""
import logging
import tempfile
import threading
import uuid
from pathlib import Path

import httpx
import psycopg2
from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from step1_text_docs import OLLAMA_URL, TEXT_MODEL, parse_text_file
from step2_vision_images import VISION_MODEL, parse_image_file
from step3_embeddings import EMBED_MODEL, product_text, to_vectors
from step4_ktru_catalog import LOCAL
from step5_match import FindKtru, save_products
from step6_confidence import judge

app = FastAPI(title="KTRU Ollama backend", version="3.0")
finder = FindKtru()
processing_lock = threading.Lock()
DOCUMENTS = {".xlsx", ".csv", ".txt", ".pdf", ".docx", ".pptx"}
IMAGES = {".png", ".jpg", ".jpeg"}


def process_file(path, filename, classify):
    if not processing_lock.acquire(blocking=False):
        raise HTTPException(429, "Другой файл уже обрабатывается. Повторите позже.")
    try:
        if classify and not finder.ready:
            finder.prepare()
        if path.suffix.lower() in IMAGES:
            products = parse_image_file(path)
        else:
            products = parse_text_file(path)
        if not products:
            raise ValueError("В файле не найдено товаров")
        if len(products) > 1000:
            raise ValueError("Не более 1000 товаров в одном запросе")
        for number, product in enumerate(products, 1):
            product["row_id"] = number
            product["source"] = product["source"].replace(path.name, filename)
        job_id = str(uuid.uuid4())
        if classify:
            vectors = to_vectors([product_text(product) for product in products])
            candidates = finder.search(vectors)
            for product, top in zip(products, candidates):
                product.update(judge(product, top))
            save_products(job_id, filename, products, vectors)
        return {"job_id": job_id, "filename": filename, "total": len(products),
                "persisted": classify, "items": products}
    finally:
        processing_lock.release()


async def handle_upload(file, classify):
    filename = Path((file.filename or "").replace("\\", "/")).name
    ext = Path(filename).suffix.lower()
    if ext not in DOCUMENTS | IMAGES:
        await file.close()
        raise HTTPException(415, "Неподдерживаемый формат файла")
    try:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ("upload" + ext)
            size = 0
            with path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 20 * 1024 * 1024:
                        raise HTTPException(413, "Максимальный размер файла — 20 МБ")
                    output.write(chunk)
            if size == 0:
                raise HTTPException(400, "Пустой файл")
            return await run_in_threadpool(process_file, path, filename, classify)
    except HTTPException:
        raise
    except RuntimeError as error:
        logging.exception("Ошибка модели или каталога")
        raise HTTPException(503, str(error)) from error
    except psycopg2.Error as error:
        logging.exception("Ошибка PostgreSQL")
        raise HTTPException(503, "PostgreSQL недоступен или запись не выполнена") from error
    except Exception as error:
        logging.exception("Ошибка обработки файла")
        raise HTTPException(422, "Файл не удалось прочитать или проверить") from error
    finally:
        await file.close()


@app.get("/health")
def health():
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.get(OLLAMA_URL + "/api/tags")
            response.raise_for_status()
            installed = {model["name"] for model in response.json()["models"]}
        missing = sorted({TEXT_MODEL, VISION_MODEL, EMBED_MODEL} - installed)
        return {"status": "ready" if not missing and LOCAL.exists() and finder.ready else "not_ready",
                "missing_models": missing, "catalog_available": LOCAL.exists(),
                "catalog_indexed": finder.ready}
    except Exception:
        return {"status": "not_ready", "reason": "Ollama недоступна"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    return await handle_upload(file, False)


@app.post("/classify")
async def classify(file: UploadFile = File(...)):
    return await handle_upload(file, True)
