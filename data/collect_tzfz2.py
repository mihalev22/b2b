"""Второй проход: поиск по 4-значным ОКПД2 кодам для полного покрытия."""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://tzfz.ru/api/ktru/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
DELAY = 0.25
OUTPUT = Path("data/ktru_full.json")


def fetch(session, query):
    for attempt in range(3):
        try:
            r = session.get(f"{BASE}?q={query}", timeout=20)
            if r.status_code == 200:
                time.sleep(DELAY)
                return r.json().get("items", [])
            time.sleep(3)
        except requests.RequestException:
            time.sleep(3)
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
        okpd2 = item.get("okpd2_code", "")
        if okpd2:
            known_okpd2.add(okpd2)

    print(f"Известных ОКПД2 групп: {len(known_okpd2)}")

    done_groups = set(state.get("done_groups", []))
    groups_to_search = sorted(known_okpd2 - done_groups)
    print(f"Групп для поиска: {len(groups_to_search)}")

    batch_start = time.time()
    for idx, okpd2 in enumerate(groups_to_search):
        items = fetch(session, okpd2)
        new = 0
        for item in items:
            code = item.get("ktru_code", "")
            if code and code not in all_items:
                all_items[code] = item
                new += 1
                ok = item.get("okpd2_code", "")
                if ok and ok not in known_okpd2:
                    known_okpd2.add(ok)
                    groups_to_search.append(ok)

        done_groups.add(okpd2)

        if idx % 50 == 0 or new > 0:
            print(
                f"[{idx+1}/{len(groups_to_search)}] {okpd2}: "
                f"{len(items)} поз, новых {new}, всего {len(all_items)}",
                flush=True,
            )
            save(all_items, state, done_groups)

        if len(all_items) >= 55000:
            print("Достигнуто 55k+ позиций")
            break

    save(all_items, state, done_groups)
    print(f"\nИТОГО: {len(all_items)} позиций из ~60174")
    return 0


def save(items, state, done_groups):
    state["items"] = items
    state["done_groups"] = list(done_groups)
    tmp = OUTPUT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    tmp.replace(OUTPUT)


if __name__ == "__main__":
    sys.exit(main())
