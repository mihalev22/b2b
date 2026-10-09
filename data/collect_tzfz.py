"""Быстрый сбор полного каталога КТРУ через API tzfz.ru (60k+ позиций за ~30 мин)."""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://tzfz.ru/api/ktru/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
DELAY = 0.3
OUTPUT = Path("data/ktru_full.json")

SECTIONS = {
    "A": range(1, 4), "B": range(5, 10), "C": range(10, 34), "D": [35],
    "E": range(36, 40), "F": range(41, 44), "G": range(45, 48),
    "H": range(49, 54), "I": range(55, 57), "J": range(58, 64),
    "K": range(64, 67), "L": [68], "M": range(69, 76), "N": range(77, 83),
    "O": [84], "P": [85], "Q": range(86, 89), "R": range(90, 94),
    "S": range(94, 97), "T": [97], "U": [99],
}

ALL_PREFIXES = sorted(
    {f"{code:02d}" for codes in SECTIONS.values() for code in codes}
)


def fetch(session, query):
    for attempt in range(3):
        try:
            r = session.get(f"{BASE}?q={query}", timeout=20)
            if r.status_code == 200:
                time.sleep(DELAY)
                return r.json().get("items", [])
            time.sleep(5)
        except requests.RequestException:
            time.sleep(5)
    return []


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    all_items = {}
    if OUTPUT.exists():
        with open(OUTPUT, encoding="utf-8") as f:
            state = json.load(f)
            all_items = state.get("items", {})
        print(f"Продолжаю: {len(all_items)} уже собрано")

    done_prefixes = set()
    if OUTPUT.exists():
        done_prefixes = set(state.get("done_prefixes", []))

    for prefix in ALL_PREFIXES:
        if prefix in done_prefixes:
            continue

        items = fetch(session, prefix)
        new = 0
        for item in items:
            code = item.get("ktru_code", "")
            if code and code not in all_items:
                all_items[code] = item
                new += 1

        print(f"[{prefix}] {len(items)} позиций, новых {new}, всего {len(all_items)}", flush=True)
        done_prefixes.add(prefix)

        if len(all_items) % 1000 < 100 or prefix == ALL_PREFIXES[-1]:
            save(all_items, done_prefixes)

    save(all_items, done_prefixes)
    print(f"\nГОТОВО: {len(all_items)} позиций")
    return 0


def save(items, done_prefixes):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"items": items, "done_prefixes": list(done_prefixes)}, f, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
