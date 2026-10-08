# Заглушка сервиса ml: только healthcheck, чтобы стек поднимался целиком.
# Контракт /embed и /classify определяет ИИ-инженер (docs/api).
from fastapi import FastAPI

app = FastAPI(title="КТРУ ml (заглушка)", version="0.0.1")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "stub": True}
