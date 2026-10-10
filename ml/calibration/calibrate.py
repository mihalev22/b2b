"""Калибровка уверенности по размеченной выборке.

Вход — jsonl, одна позиция на строку:
    {"item_id": "...", "query": "...", "true_code": "...",
     "candidates": [{"ktru_code": "...", "ktru_name": "...", "score": 0.83}, ...]}

Запуск из каталога ml:
    python -m calibration.calibrate ../data/labeled.jsonl --report calibration/report.md
    python -m calibration.calibrate ../data/labeled.jsonl --save --embedding-model sergeyzh/BERTA
"""

import argparse
import json
import random
from datetime import date
from pathlib import Path

import numpy as np

from app.confidence import FEATURES, PARAMS_PATH, ConfidenceParams, candidate_features, score_item

TARGET_HIGH = 0.85
DEFAULT_HIGH = 85.0
DEFAULT_MEDIUM = 60.0
MIN_ITEMS_IN_ZONE = 30
BINS = 10


def load_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def to_arrays(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    k = max(len(r["candidates"]) for r in rows)
    x = np.zeros((len(rows), k, len(FEATURES)))
    mask = np.zeros((len(rows), k), dtype=bool)
    y = np.full(len(rows), k)
    for n, row in enumerate(rows):
        feats = candidate_features(row["candidates"], row.get("query", ""))
        for i, f in enumerate(feats):
            x[n, i] = [f[name] for name in FEATURES]
            mask[n, i] = True
            if row["candidates"][i]["ktru_code"] == row["true_code"]:
                y[n] = i
    return x, mask, y


def fit(rows: list[dict], steps: int = 3000, lr: float = 0.05, l2: float = 1e-3) -> dict:
    x, mask, y = to_arrays(rows)
    n, k, _ = x.shape
    valid = x[mask]
    mu, sd = valid.mean(axis=0), valid.std(axis=0) + 1e-9
    xs = (x - mu) / sd
    params = np.zeros(len(FEATURES) + 1)
    m, v = np.zeros_like(params), np.zeros_like(params)
    target = np.zeros((n, k + 1))
    target[np.arange(n), y] = 1.0
    for t in range(1, steps + 1):
        z = np.where(mask, xs @ params[:-1] + params[-1], -np.inf)
        z = np.concatenate([z, np.zeros((n, 1))], axis=1)
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(axis=1, keepdims=True)
        err = (p - target)[:, :k]
        grad_w = np.einsum("nk,nkf->f", err, xs) / n + l2 * params[:-1]
        grad_b = err.sum() / n
        grad = np.append(grad_w, grad_b)
        m = 0.9 * m + 0.1 * grad
        v = 0.999 * v + 0.001 * grad**2
        params -= lr * (m / (1 - 0.9**t)) / (np.sqrt(v / (1 - 0.999**t)) + 1e-8)
    weights = params[:-1] / sd
    bias = params[-1] - float((params[:-1] * mu / sd).sum())
    return {"weights": dict(zip(FEATURES, map(float, weights), strict=True)), "bias": float(bias)}


def best_predictions(rows: list[dict], params: ConfidenceParams) -> tuple[np.ndarray, np.ndarray]:
    conf, correct = [], []
    for row in rows:
        result = score_item(row["candidates"], row.get("query", ""), params)
        best = result["best"]
        conf.append(best["confidence"] if best else 0.0)
        correct.append(bool(best) and best["ktru_code"] == row["true_code"])
    return np.array(conf), np.array(correct)


def ece(conf: np.ndarray, correct: np.ndarray) -> float:
    edges = np.linspace(0, 100, BINS + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1]), 0, BINS - 1)
    total = 0.0
    for b in range(BINS):
        sel = idx == b
        if sel.any():
            total += sel.mean() * abs(conf[sel].mean() / 100 - correct[sel].mean())
    return float(total)


def pick_thresholds(conf: np.ndarray, correct: np.ndarray) -> dict[str, float]:
    high = 100.0
    for t in range(int(DEFAULT_HIGH), 100):
        sel = conf >= t
        if sel.sum() >= MIN_ITEMS_IN_ZONE and correct[sel].mean() >= TARGET_HIGH:
            high = float(t)
            break
    return {"high": high, "medium": min(DEFAULT_MEDIUM, high)}


def requirement_line(conf: np.ndarray, correct: np.ndarray) -> str:
    sel = conf >= DEFAULT_HIGH
    if not sel.any():
        return "- Требование «от 85 % уверенности — не меньше 85 % верных»: нет таких позиций"
    share = correct[sel].mean()
    verdict = "выполнено" if share >= TARGET_HIGH else "НЕ выполнено"
    return (
        f"- Требование «от 85 % уверенности — не меньше 85 % верных»: {verdict} "
        f"({share:.1%} верных среди {sel.sum()} позиций)"
    )


def report(rows: list[dict], params: ConfidenceParams, title: str) -> str:
    conf, correct = best_predictions(rows, params)
    in_top5 = np.mean(
        [any(c["ktru_code"] == r["true_code"] for c in r["candidates"]) for r in rows]
    )
    raw = np.array([max((c["score"] for c in r["candidates"]), default=0) * 100 for r in rows])
    lines = [
        f"## {title}",
        "",
        f"- Позиций: {len(rows)}",
        f"- Верный код на первом месте: {correct.mean():.1%}",
        f"- Верный код среди кандидатов: {in_top5:.1%}",
        f"- Ошибка калибровки ECE: {ece(conf, correct):.3f}"
        f" (если брать косинус как процент: {ece(raw, correct):.3f})",
        requirement_line(conf, correct),
        "",
        "| Уверенность | Позиций | Средняя уверенность | Доля верных |",
        "|---|---|---|---|",
    ]
    edges = np.linspace(0, 100, BINS + 1)
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        sel = (conf >= lo) & ((conf < hi) | (hi == 100))
        if sel.any():
            lines.append(
                f"| {lo:.0f}–{hi:.0f} | {sel.sum()} | {conf[sel].mean():.1f} "
                f"| {correct[sel].mean():.1%} |"
            )
    lines += ["", "| Порог | Позиций не ниже порога | Доля верных среди них |", "|---|---|---|"]
    for t in (50, 60, 70, 80, 85, 90, 95):
        sel = conf >= t
        share = f"{correct[sel].mean():.1%}" if sel.any() else "—"
        lines.append(f"| {t} | {sel.mean():.1%} | {share} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Калибровка уверенности КТРУ")
    parser.add_argument("data", type=Path)
    parser.add_argument("--holdout", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--embedding-model", help="модель, которой посчитаны score в выборке")
    args = parser.parse_args()
    if args.save and not args.embedding_model:
        parser.error("с --save укажите --embedding-model: веса привязаны к модели эмбеддингов")

    rows = load_rows(args.data)
    random.Random(args.seed).shuffle(rows)
    cut = int(len(rows) * (1 - args.holdout))
    train, holdout = rows[:cut], rows[cut:]

    before = ConfidenceParams.load()
    fitted = fit(train)
    draft = ConfidenceParams(fitted["weights"], fitted["bias"], DEFAULT_HIGH, DEFAULT_MEDIUM, True)
    thresholds = pick_thresholds(*best_predictions(holdout, draft))
    after = ConfidenceParams(fitted["weights"], fitted["bias"], **thresholds, calibrated=True)

    text = "\n\n".join(
        [
            f"# Калибровка уверенности — {date.today().isoformat()}",
            f"Обучение: {len(train)} позиций, проверка: {len(holdout)} позиций.",
            report(holdout, before, "До калибровки (стартовые веса), проверочная часть"),
            report(holdout, after, "После калибровки, проверочная часть"),
            f"Пороги зон: высокая от {thresholds['high']:.0f}, "
            f"средняя от {thresholds['medium']:.0f}.",
            f"Веса: {json.dumps(fitted, ensure_ascii=False)}",
        ]
    )
    print(text)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    if args.save:
        payload = {
            "calibrated": True,
            "embedding_model": args.embedding_model,
            "note": f"Калибровка {date.today()}, {len(train)} позиций, {args.data.name}",
            "weights": fitted["weights"],
            "bias": fitted["bias"],
            "thresholds": thresholds,
        }
        PARAMS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"\nВеса записаны в {PARAMS_PATH}")


if __name__ == "__main__":
    main()
