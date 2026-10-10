"""Процент уверенности для кандидатов КТРУ.

Модель — softmax с вариантом «верного кода нет среди кандидатов»:
    z_i = bias + w_score * score_i + w_margin * margin_i + w_lexical * lexical_i
    p_i = exp(z_i) / (1 + sum_j exp(z_j))
Единица в знаменателе — это вариант «ни один кандидат не подходит», поэтому сумма
уверенностей по пяти кандидатам не превышает 100 %. Веса подбираются по размеченной
выборке скриптом ml/calibration/calibrate.py.
"""

import json
import logging
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)

PARAMS_PATH = Path(__file__).with_name("confidence_params.json")
FEATURES = ("score", "margin", "lexical")
TOKEN_RE = re.compile(r"[a-zа-я0-9]+")
STEM_LEN = 5


@dataclass(frozen=True)
class ConfidenceParams:
    weights: dict[str, float]
    bias: float
    high: float
    medium: float
    calibrated: bool
    embedding_model: str | None = None

    @classmethod
    def load(cls, path: Path = PARAMS_PATH) -> "ConfidenceParams":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            weights={name: float(data["weights"][name]) for name in FEATURES},
            bias=float(data["bias"]),
            high=float(data["thresholds"]["high"]),
            medium=float(data["thresholds"]["medium"]),
            calibrated=bool(data.get("calibrated", False)),
            embedding_model=data.get("embedding_model"),
        )

    def for_model(self, embedding_model: str) -> "ConfidenceParams":
        """Веса годятся только для модели, на которой калибровали. Иначе — не откалиброваны."""
        if self.embedding_model == embedding_model:
            return self
        if self.calibrated:
            logger.warning(
                "Веса уверенности откалиброваны на %s, а сервис работает на %s — "
                "уверенность не откалибрована, запустите calibration/calibrate.py",
                self.embedding_model,
                embedding_model,
            )
        return replace(self, calibrated=False)

    def thresholds(self) -> dict:
        return {
            "high": self.high,
            "medium": self.medium,
            "calibrated": self.calibrated,
            "embedding_model": self.embedding_model,
        }


def stems(text: str) -> set[str]:
    tokens = TOKEN_RE.findall(text.lower().replace("ё", "е"))
    return {token[:STEM_LEN] for token in tokens if len(token) >= 3 or token.isdigit()}


def lexical_overlap(query: str, ktru_name: str) -> float:
    query_stems = stems(query)
    if not query_stems:
        return 0.0
    return len(query_stems & stems(ktru_name)) / len(query_stems)


def candidate_features(candidates: list[dict], query: str) -> list[dict[str, float]]:
    scores = [float(c["score"]) for c in candidates]
    rows = []
    for i, candidate in enumerate(candidates):
        others = scores[:i] + scores[i + 1 :]
        rows.append(
            {
                "score": scores[i],
                "margin": scores[i] - (max(others) if others else 0.0),
                "lexical": lexical_overlap(query, candidate.get("ktru_name") or ""),
            }
        )
    return rows


def probabilities(features: list[dict[str, float]], params: ConfidenceParams) -> list[float]:
    if not features:
        return []
    logits = [
        params.bias + sum(params.weights[name] * row[name] for name in FEATURES) for row in features
    ]
    top = max(0.0, max(logits))
    exps = [math.exp(z - top) for z in logits]
    denominator = math.exp(-top) + sum(exps)
    return [e / denominator for e in exps]


def zone(confidence: float | None, params: ConfidenceParams) -> str:
    if confidence is None:
        return "none"
    if confidence >= params.high:
        return "high"
    if confidence >= params.medium:
        return "medium"
    return "low"


def score_item(candidates: list[dict], query: str, params: ConfidenceParams) -> dict:
    """Возвращает кандидатов с полем confidence (0–100), лучший код и needs_review.

    candidates — до пяти позиций {ktru_code, ktru_name, score}, score — косинусная близость.
    query — текст позиции, по которому искали (наименование и ключевые характеристики).
    """
    probs = probabilities(candidate_features(candidates, query), params)
    scored = [
        {**candidate, "confidence": round(100 * p, 1)}
        for candidate, p in zip(candidates, probs, strict=True)
    ]
    scored.sort(key=lambda c: c["confidence"], reverse=True)
    if not scored:
        return {"candidates": [], "best": None, "needs_review": True, "zone": "none"}
    best = {"ktru_code": scored[0]["ktru_code"], "confidence": scored[0]["confidence"]}
    return {
        "candidates": scored,
        "best": best,
        "needs_review": best["confidence"] < params.high,
        "zone": zone(best["confidence"], params),
    }
