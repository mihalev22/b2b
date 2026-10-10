"""Синтетическая размеченная выборка для проверки калибровки, пока нет настоящей.

Запуск из каталога ml:
    python -m calibration.synthetic ../data/synthetic.jsonl --n 2000
"""

import argparse
import json
import random
from pathlib import Path

ALPHABET = "абвгдежзиклмнопрстуфхцчшэюя"


def make_vocab(rng: random.Random, size: int) -> list[str]:
    words: dict[str, str] = {}
    while len(words) < size:
        word = "".join(rng.choice(ALPHABET) for _ in range(7))
        words.setdefault(word[:5], word)
    return list(words.values())


def make_name(rng: random.Random, vocab: list[str], query: list[str], share: float) -> str:
    words = [w for w in query if rng.random() < share]
    words += rng.sample(vocab, 3 - min(len(words), 2))
    rng.shuffle(words)
    return " ".join(words)


def generate(n: int, seed: int = 0, in_top5: float = 0.9) -> list[dict]:
    rng = random.Random(seed)
    vocab = make_vocab(rng, 400)
    rows = []
    for item in range(n):
        query = rng.sample(vocab, 3)
        difficulty = rng.random()
        candidates = []
        for j in range(5):
            candidates.append(
                {
                    "ktru_code": f"00.00.00.000-{item:05d}{j}",
                    "ktru_name": make_name(rng, vocab, query, 0.15),
                    "score": round(rng.gauss(0.78, 0.035), 4),
                }
            )
        true_code = f"99.99.99.999-{item:05d}"
        if rng.random() < in_top5:
            hit = candidates[rng.randrange(5)]
            hit["ktru_code"] = true_code
            hit["ktru_name"] = make_name(rng, vocab, query, 0.7 - 0.4 * difficulty)
            hit["score"] = round(rng.gauss(0.86 - 0.08 * difficulty, 0.03), 4)
        candidates.sort(key=lambda c: c["score"], reverse=True)
        rows.append(
            {
                "item_id": str(item),
                "query": " ".join(query),
                "true_code": true_code,
                "candidates": candidates,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Синтетическая выборка для калибровки")
    parser.add_argument("out", type=Path)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for row in generate(args.n, args.seed):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Записано {args.n} позиций в {args.out}")


if __name__ == "__main__":
    main()
