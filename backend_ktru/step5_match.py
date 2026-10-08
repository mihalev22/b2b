"""Шаг 5: нейроэмбеддинги -> поиск кандидатов и хранение в PostgreSQL/pgvector."""
import hashlib
import json
import os

import psycopg2
from psycopg2.extras import Json, execute_batch
from step1_text_docs import ollama_request
from step3_embeddings import EMBED_MODEL, product_text, to_vectors, vector_sql
from step4_ktru_catalog import load_catalog

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ktru")


def connect_database():
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)


def create_tables(connection):
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ktru_index_meta (
                singleton BOOLEAN PRIMARY KEY CHECK (singleton),
                fingerprint TEXT NOT NULL, dimension INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ktru_candidates (
                code TEXT PRIMARY KEY, item JSONB NOT NULL, embedding vector NOT NULL
            );
            CREATE TABLE IF NOT EXISTS parsed_products (
                job_id UUID NOT NULL, row_id INTEGER NOT NULL, filename TEXT NOT NULL,
                item JSONB NOT NULL, embedding vector NOT NULL,
                embedding_model TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(),
                PRIMARY KEY (job_id, row_id)
            )
        """)


class FindKtru:
    """Модель не придумывает коды: кандидаты приходят только из каталога."""

    def __init__(self):
        self.ready = False
        self.dimension = None
        self.catalog_count = 0

    def prepare(self):
        rows = load_catalog()
        model_info = ollama_request("/api/show", {"model": EMBED_MODEL})
        content = json.dumps([rows, EMBED_MODEL, model_info.get("model_info"),
                              model_info.get("details"), model_info.get("modelfile")], ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256(content.encode()).hexdigest()
        connection = connect_database()
        try:
            with connection:
                create_tables(connection)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(742618)")
                    cursor.execute("SELECT fingerprint, dimension FROM ktru_index_meta WHERE singleton=true")
                    previous = cursor.fetchone()
                    if previous and previous[0] == fingerprint:
                        self.dimension = previous[1]
                    else:
                        texts = []
                        for row in rows:
                            attributes = json.dumps(row["attributes"], ensure_ascii=False)
                            texts.append(row["name"] + "\n" + row["description"] + "\n" + attributes)
                        vectors = to_vectors(texts)
                        self.dimension = len(vectors[0])
                        cursor.execute("DELETE FROM ktru_candidates")
                        execute_batch(cursor, """
                            INSERT INTO ktru_candidates(code,item,embedding) VALUES (%s,%s,%s::vector)
                        """, [(row["code"], Json(row), vector_sql(vector))
                              for row, vector in zip(rows, vectors)], page_size=100)
                        cursor.execute("""
                            INSERT INTO ktru_index_meta VALUES (true,%s,%s)
                            ON CONFLICT(singleton) DO UPDATE SET
                            fingerprint=excluded.fingerprint, dimension=excluded.dimension
                        """, (fingerprint, self.dimension))
            self.catalog_count = len(rows)
            self.ready = True
        finally:
            connection.close()

    def search(self, vectors, limit=5):
        if not self.ready:
            self.prepare()
        if any(len(vector) != self.dimension for vector in vectors):
            raise RuntimeError("Размерность модели отличается от индекса; пересоздайте индекс")
        connection = connect_database()
        results = []
        try:
            with connection, connection.cursor() as cursor:
                for vector in vectors:
                    cursor.execute("""
                        SELECT item, 1 - (embedding <=> %s::vector) AS similarity
                        FROM ktru_candidates ORDER BY embedding <=> %s::vector LIMIT %s
                    """, (vector_sql(vector), vector_sql(vector), limit))
                    candidates = []
                    for item, score in cursor.fetchall():
                        item["similarity"] = round(float(score), 5)
                        candidates.append(item)
                    results.append(candidates)
            return results
        finally:
            connection.close()

    def top5(self, text, brand="", model=""):
        return self.search(to_vectors([text]))[0]


def save_products(job_id, filename, products, vectors):
    if len(products) != len(vectors):
        raise ValueError("Количество товаров и векторов различается")
    connection = connect_database()
    try:
        with connection:
            create_tables(connection)
            with connection.cursor() as cursor:
                execute_batch(cursor, """
                    INSERT INTO parsed_products(job_id,row_id,filename,item,embedding,embedding_model)
                    VALUES (%s,%s,%s,%s,%s::vector,%s)
                """, [(job_id, number, filename, Json(product), vector_sql(vector), EMBED_MODEL)
                      for number, (product, vector) in enumerate(zip(products, vectors), 1)])
    finally:
        connection.close()
