"""╨д╨╕╨╜╨░╨╗╤М╨╜╤Л╨╣ ╨┤╨╛╨▒╨╛╤А: ╨░╨╗╤Д╨░╨▓╨╕╤В╨╜╤Л╨╣ ╨┐╨╡╤А╨╡╨▒╨╛╤А ╨┐╨╛ ╨▓╤Б╨╡╨╝ ╨▒╤Г╨║╨▓╨░╨╝ ╤А╤Г╤Б╤Б╨║╨╛╨│╨╛ ╨░╨╗╤Д╨░╨▓╨╕╤В╨░."""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://tzfz.ru/api/ktru/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
DELAY = 0.2
OUTPUT = Path("data/ktru_full.json")

LETTERS = "╨░╨▒╨▓╨│╨┤╨╡╨╢╨╖╨╕╨║╨╗╨╝╨╜╨╛╨┐╤А╤Б╤В╤Г╤Д╤Е╤Ж╤З╤И╤Й╤Н╤О╤П"
PAIRS = [
    a + b for a in LETTERS for b in LETTERS
]
COMBOS = LETTERS.split() + PAIRS


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
    print(f"╨Ч╨░╨│╤А╤Г╨╢╨╡╨╜╨╛: {len(all_items)} ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣")

    done = set(state.get("done_alpha", []))

    for combo in COMBOS:
        if combo in done:
            continue
        items = fetch(session, combo)
        new = 0
        for item in items:
            code = item.get("ktru_code", "")
            if code and code not in all_items:
                all_items[code] = item
                new += 1
        done.add(combo)
        if new:
            print(f"[{combo}] +{new} тЖТ {len(all_items)}", flush=True)

    state["items"] = all_items
    state["done_alpha"] = list(done)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)

    print(f"\n╨Ш╨в╨Ю╨У╨Ю: {len(all_items)} ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣")
    return 0


if __name__ == "__main__":
    sys.exit(main())
