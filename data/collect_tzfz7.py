"""Добор: трёхбуквенные комбинации русского алфавита."""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://tzfz.ru/api/ktru/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
DELAY = 0.15
OUTPUT = Path("data/ktru_full.json")

LETTERS = "абвгдежзиклмнопрстуфхцчшщэюя"


def fetch(session, query):
    try:
        r = session.get(f"{BASE}?q={query}", timeout=15)
        if r.status_code == 200:
            time.sleep(DELAY)
            return r.json().get("items", [])
    except:
        time.sleep(2)
    return []


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    with open(OUTPUT, encoding="utf-8") as f:
        state = json.load(f)

    all_items = state["items"]
    print(f"Загружено: {len(all_items)} позиций")

    done = set(state.get("done_triple", []))
    total_combos = len(LETTERS) ** 3
    print(f"Комбинаций для проверки: {total_combos}")

    count = 0
    new_total = 0
    for a in LETTERS:
        for b in LETTERS:
            for c in LETTERS:
                combo = a + b + c
                if combo in done:
                    continue
                count += 1
                items = fetch(session, combo)
                new = 0
                for item in items:
                    code = item.get("ktru_code", "")
                    if code and code not in all_items:
                        all_items[code] = item
                        new += 1
                        new_total += 1
                done.add(combo)

                if count % 500 == 0:
                    print(f"[{count}/{total_combos}] {combo}: +{new} → {len(all_items)}", flush=True)
                    save(all_items, state, done)

                if count >= 5000:
                    save(all_items, state, done)
                    print(f"Лимит запросов, итог: {len(all_items)} позиций (+{new_total})")
                    return 0

    save(all_items, state, done)
    print(f"\nИТОГО: {len(all_items)} позиций (+{new_total})")
    return 0


def save(items, state, done):
    state["items"] = items
    state["done_triple"] = list(done)
    tmp = OUTPUT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    tmp.replace(OUTPUT)


if __name__ == "__main__":
    sys.exit(main())
