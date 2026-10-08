"""Шаг 3: настоящие нейроэмбеддинги Ollama, без TF-IDF и обрезания векторов."""
import json
import math
import os

from step1_text_docs import ollama_request

EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma:300m")


def product_text(product):
    """Одинаковое представление товара для поиска и нейросетевой проверки."""
    lines = [product["name"]]
    if product.get("brand"):
        lines.append("Бренд: " + product["brand"])
    if product.get("model"):
        lines.append("Модель: " + product["model"])
    for attribute in product.get("attributes", []):
        lines.append(f"{attribute['name']}: {attribute['value']} {attribute.get('unit', '')}".strip())
    return "\n".join(lines)


def to_vectors(texts):
    if not texts:
        return []
    vectors = []
    dimension = None
    for start in range(0, len(texts), 32):
        batch = texts[start:start + 32]
        if any(not text.strip() or len(text) > 6000 for text in batch):
            raise ValueError("Текст эмбеддинга пустой или превышает 6000 символов")
        answer = ollama_request("/api/embed", {
            "model": EMBED_MODEL, "input": batch, "truncate": False, "keep_alive": "5m",
        })
        result = answer.get("embeddings", [])
        if len(result) != len(batch):
            raise RuntimeError("Ollama вернула неверное количество эмбеддингов")
        for vector in result:
            if not vector or not all(isinstance(n, (int, float)) and math.isfinite(n) for n in vector):
                raise RuntimeError("Получен некорректный вектор")
            dimension = dimension or len(vector)
            if len(vector) != dimension:
                raise RuntimeError("Размерности эмбеддингов различаются")
            length = math.sqrt(sum(n * n for n in vector))
            if length <= 0:
                raise RuntimeError("Нейросеть вернула нулевой вектор")
            vectors.append([n / length for n in vector])
    return vectors


def vector_sql(vector):
    return json.dumps(vector, allow_nan=False)
