import json

import numpy as np

from app.confidence import ConfidenceParams, lexical_overlap, score_item
from calibration.calibrate import best_predictions, ece, fit
from calibration.synthetic import generate

PARAMS = ConfidenceParams.load()


def make_candidates(scores: list[float]) -> list[dict]:
    return [
        {"ktru_code": f"code-{i}", "ktru_name": "Ноутбук портативный", "score": s}
        for i, s in enumerate(scores)
    ]


def test_confidence_in_range_and_sum_not_above_100():
    result = score_item(make_candidates([0.9, 0.8, 0.79, 0.7, 0.6]), "ноутбук dell", PARAMS)
    values = [c["confidence"] for c in result["candidates"]]
    assert all(0 <= v <= 100 for v in values)
    assert sum(values) <= 100.5
    assert values == sorted(values, reverse=True)


def test_higher_score_gives_higher_confidence():
    low = score_item(make_candidates([0.80, 0.78]), "ноутбук", PARAMS)
    high = score_item(make_candidates([0.90, 0.78]), "ноутбук", PARAMS)
    assert high["best"]["confidence"] > low["best"]["confidence"]


def test_close_candidates_need_review():
    result = score_item(make_candidates([0.85, 0.849, 0.848]), "ноутбук", PARAMS)
    assert result["needs_review"] is True
    assert result["best"]["confidence"] < 50


def test_empty_candidates():
    result = score_item([], "ноутбук", PARAMS)
    assert result == {"candidates": [], "best": None, "needs_review": True, "zone": "none"}


def test_lexical_overlap():
    assert lexical_overlap("Ноутбуки портативные", "Ноутбук портативный") == 1.0
    assert lexical_overlap("Бумага офисная", "Ноутбук") == 0.0
    assert lexical_overlap("", "Ноутбук") == 0.0


def test_calibration_on_synthetic_data(tmp_path):
    train, holdout = generate(1500, seed=1), generate(600, seed=2)
    fitted = fit(train)
    params = ConfidenceParams(fitted["weights"], fitted["bias"], 85.0, 60.0, True)
    conf, correct = best_predictions(holdout, params)
    assert ece(conf, correct) < 0.07
    assert correct[conf >= 85].mean() >= 0.85
    path = tmp_path / "params.json"
    path.write_text(
        json.dumps({**fitted, "thresholds": {"high": 85, "medium": 60}, "calibrated": True}),
        encoding="utf-8",
    )
    loaded = ConfidenceParams.load(path)
    assert np.isclose(loaded.bias, fitted["bias"])


def test_params_for_other_model_are_not_calibrated():
    params = ConfidenceParams({"score": 1, "margin": 1, "lexical": 1}, 0, 85, 60, True, "model-a")
    assert params.for_model("model-a").calibrated is True
    assert params.for_model("model-b").calibrated is False
    assert params.for_model("model-b").thresholds()["high"] == 85
