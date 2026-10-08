"""Быстрые тесты контрактов без скачивания моделей и запуска PostgreSQL."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from fastapi.testclient import TestClient
import app
import step1_text_docs as text
import step2_vision_images as vision
import step3_embeddings as embeddings
import step4_ktru_catalog as catalog
import step6_confidence as confidence


def product():
    return {"name": "Клавиатура", "raw_text": "Клавиотура USB 5 шт",
            "brand": "", "model": "", "quantity": 5, "unit": "шт",
            "attributes": [{"name": "Интерфейс", "value": "USB", "unit": ""}],
            "corrections": ["Клавиотура -> Клавиатура"], "uncertain": False}


class BackendTests(unittest.TestCase):
    def test_extraction_uses_schema(self):
        answer = {"message": {"content": json.dumps({"products": [product()]})}}
        with patch.object(text, "ollama_request", return_value=answer) as request:
            goods = text.extract_products("Клавиотура USB 5 шт", "test.txt")
        self.assertEqual(goods[0]["quantity"], 5)
        self.assertIn("format", request.call_args.args[1])
        self.assertFalse(request.call_args.args[1]["think"])

    def test_fabricated_quote_rejected(self):
        answer = {"message": {"content": json.dumps({"products": [product()]})}}
        with patch.object(text, "ollama_request", return_value=answer):
            with self.assertRaises(RuntimeError):
                text.extract_products("Другой текст", "test")

    def test_invalid_json_rejected(self):
        with patch.object(text, "ollama_request", return_value={"message": {"content": "wrong"}}):
            with self.assertRaises(RuntimeError):
                text.extract_products("text", "test")

    def test_embeddings_normalized_not_padded(self):
        with patch.object(embeddings, "ollama_request", return_value={"embeddings": [[3, 4]]}):
            self.assertEqual(embeddings.to_vectors(["Товар"]), [[0.6, 0.8]])
        with patch.object(embeddings, "ollama_request", return_value={"embeddings": [[0, 0]]}):
            with self.assertRaises(RuntimeError):
                embeddings.to_vectors(["Товар"])

    def test_catalog_rejects_okpd_and_external_source(self):
        data = {"source_url": catalog.OFFICIAL_CATALOG, "exported_at": "2026-01-01",
                "items": [{"code": "26.20.16.120", "name": "Тест",
                           "source_url": catalog.OFFICIAL_CATALOG, "active": True}]}
        with self.assertRaises(ValueError):
            catalog.validate_catalog(data)
        data["items"][0]["code"] = "26.20.16.120-00000001"
        data["source_url"] = "https://example.org/catalog"
        with self.assertRaises(ValueError):
            catalog.validate_catalog(data)

    def test_vision_sends_image(self):
        buffer = io.BytesIO()
        Image.new("RGB", (30, 30), "white").save(buffer, format="PNG")
        result = text.Extraction(products=[text.Product(**product())])
        with patch.object(vision, "ask_model", return_value=result) as request:
            goods = vision.extract_image_bytes(buffer.getvalue(), "photo.png")
        self.assertTrue(request.call_args.kwargs["images"])
        self.assertEqual(goods[0]["evidence_type"], "vision_not_verified")

    def test_judge_cannot_invent_code(self):
        decision = confidence.Decision(code="invented", confidence=0.99,
            reason="test", missing_attributes=[], conflicts=[], verdict="ok")
        with patch.object(confidence, "ask_model", return_value=decision):
            with self.assertRaises(RuntimeError):
                confidence.judge(product(), [{"code": "real", "name": "Товар"}])

    def test_judge_abstains_on_conflict(self):
        decision = confidence.Decision(code="real", confidence=0.8,
            reason="Конфликт", missing_attributes=[], conflicts=["не тот тип"], verdict="ok")
        with patch.object(confidence, "ask_model", return_value=decision):
            result = confidence.judge(product(), [{"code": "real", "name": "Товар"}])
        self.assertIsNone(result["ktru_code"])
        self.assertEqual(result["verdict"], "manual")

    def test_judge_does_not_accept_missing_catalog_attribute(self):
        decision = confidence.Decision(code="real", confidence=0.99,
            reason="Совпадение", missing_attributes=[], conflicts=[], verdict="ok")
        with patch.object(confidence, "ask_model", return_value=decision):
            result = confidence.judge({"name": "Клавиатура", "attributes": []},
                [{"code": "real", "name": "Клавиатура", "attributes": {"Интерфейс": "USB"}}])
        self.assertEqual(result["verdict"], "check")
        self.assertIn("Интерфейс", result["missing_attributes"])

    def test_csv_and_xlsx_keep_zero_and_first_row(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "test.csv"
            path.write_bytes("Товар;0\nКлавиатура;5".encode("cp1251"))
            self.assertIn("Товар | 0", text.read_document(path)[0][1])
            book = Workbook()
            book.active.append(["Первый товар", 0])
            book.create_sheet("Второй").append(["Второй товар", 2])
            path = Path(directory) / "test.xlsx"
            book.save(path)
            sections = text.read_document(path)
            self.assertEqual(len(sections), 2)
            self.assertIn("Первый товар | 0", sections[0][1])

    def test_api_and_upload_errors(self):
        with TestClient(app.app) as client:
            self.assertEqual(client.post("/extract", files={"file": ("x.exe", b"test")}).status_code, 415)
            self.assertEqual(client.post("/extract", files={"file": ("x.txt", b"")}).status_code, 400)
            goods = [dict(product(), source="upload.txt")]
            with patch.object(app, "parse_text_file", return_value=goods):
                response = client.post("/extract", files={"file": ("test.txt", b"test")})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["persisted"])
            self.assertEqual(response.json()["items"][0]["source"], "test.txt")


if __name__ == "__main__":
    unittest.main()
