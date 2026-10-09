"""Расширенный сбор: все возможные 3-значные и 4-значные ОКПД2 префиксы."""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://tzfz.ru/api/ktru/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
DELAY = 0.2
OUTPUT = Path("data/ktru_full.json")


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

    known_okpd2 = set()
    for item in all_items.values():
        ok = item.get("okpd2_code", "")
        if ok:
            known_okpd2.add(ok)

    prefixes_3 = set()
    for ok in known_okpd2:
        parts = ok.split(".")
        if len(parts) >= 2:
            prefixes_3.add(f"{parts[0]}.{parts[1]}")
        if len(parts) >= 3:
            prefixes_3.add(f"{parts[0]}.{parts[1]}.{parts[2]}")

    done = set(state.get("done_deep", []))
    to_search = sorted(prefixes_3 - done)
    print(f"3-значных префиксов для поиска: {len(to_search)}")

    new_total = 0
    for idx, prefix in enumerate(to_search):
        if prefix in done:
            continue
        items = fetch(session, prefix)
        new = 0
        for item in items:
            code = item.get("ktru_code", "")
            if code and code not in all_items:
                all_items[code] = item
                new += 1
                new_total += 1
                ok = item.get("okpd2_code", "")
                if ok and ok not in known_okpd2:
                    known_okpd2.add(ok)
                    parts = ok.split(".")
                    if len(parts) >= 3:
                        p3 = f"{parts[0]}.{parts[1]}.{parts[2]}"
                        if p3 not in to_search:
                            to_search.append(p3)

        done.add(prefix)

        if new > 0 or idx % 100 == 0:
            print(f"[{idx+1}/{len(to_search)}] {prefix}: +{new} → {len(all_items)}", flush=True)
            save(all_items, state, done)

    save(all_items, state, done)
    print(f"\nИТОГО: {len(all_items)} позиций (+{new_total} новых)")
    return 0


def save(items, state, done):
    state["items"] = items
    state["done_deep"] = list(done)
    tmp = OUTPUT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    tmp.replace(OUTPUT)


if __name__ == "__main__":
    sys.exit(main())
