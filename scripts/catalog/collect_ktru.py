"""╨Я╨╛╨╗╨╜╤Л╨╣ ╤Б╨▒╨╛╤А ╨║╨░╤В╨░╨╗╨╛╨│╨░ ╨Ъ╨в╨а╨г ╤Б╨╛ ╨▓╤Б╨╡╤Е ╤А╨░╨╖╨┤╨╡╨╗╨╛╨▓ ╨Ю╨Ъ╨Я╨Ф2."""
import json
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://zakupki.gov.ru"
SEARCH = f"{BASE}/epz/ktru/search/results.html"
CARD = f"{BASE}/epz/ktru/ktruCard/commonInfo.html"
DELAY = 3.0
RETRIES = 5


def all_prefixes():
    sections = {
        "A": range(1, 4), "B": range(5, 10), "C": range(10, 34), "D": [35],
        "E": range(36, 40), "F": range(41, 44), "G": range(45, 48),
        "H": range(49, 54), "I": range(55, 57), "J": range(58, 64),
        "K": range(64, 67), "L": [68], "M": range(69, 76), "N": range(77, 83),
        "O": [84], "P": [85], "Q": range(86, 89), "R": range(90, 94),
        "S": range(94, 97), "T": [97], "U": [99],
    }
    result = []
    for codes in sections.values():
        for code in codes:
            result.append(f"{code:02d}")
    return sorted(set(result))


def build_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
        "Connection": "keep-alive",
    })
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        pass
    s.verify = False
    return s


def get_with_retry(session, url, retries=RETRIES):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 200:
                time.sleep(DELAY)
                return r.text
            if r.status_code in (403, 429, 503):
                wait = 60 * (attempt + 1)
                print(f"  ╨▒╨╗╨╛╨║ ({r.status_code}), ╨╢╨┤╤Г {wait}╤Б...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            if attempt == retries - 1:
                print(f"  ! ╨┐╤А╨╛╨▓╨░╨╗: {e}", flush=True)
                return None
            time.sleep(30 * (attempt + 1))
    return None


def parse_codes_from_search(html):
    soup = BeautifulSoup(html, "html.parser")
    codes = []
    for a in soup.find_all("a", href=True):
        if "ktruCard/commonInfo.html?itemId=" in a["href"]:
            code = a["href"].split("itemId=")[1].split("&")[0]
            if code not in codes:
                codes.append(code)
    return codes


def parse_card(html, code):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    def after(marker, span=300):
        pos = text.find(marker)
        return text[pos + len(marker):pos + len(marker) + span].strip() if pos >= 0 else ""

    name = after("╨Э╨░╨╕╨╝╨╡╨╜╨╛╨▓╨░╨╜╨╕╨╡ ╤В╨╛╨▓╨░╤А╨░, ╤А╨░╨▒╨╛╤В╤Л, ╤Г╤Б╨╗╤Г╨│╨╕", 200)
    if "╨Х╨┤╨╕╨╜╨╕╤Ж╤Л" in name:
        name = name[:name.find("╨Х╨┤╨╕╨╜╨╕╤Ж╤Л")].strip()

    okpd2_raw = after("╨Ю╨Ъ╨Я╨Ф2", 200)
    okpd2_code = ""
    okpd2_name = ""
    if ":" in okpd2_raw:
        okpd2_code, _, okpd2_name = okpd2_raw.partition(":")
        okpd2_code = okpd2_code.strip()[:15]
        okpd2_name = okpd2_name.strip()[:200]

    status = "╨Т╨║╨╗╤О╤З╨╡╨╜╨╛ ╨▓ ╨Ъ╨в╨а╨г" if "╨Т╨║╨╗╤О╤З╨╡╨╜╨╛ ╨▓ ╨Ъ╨в╨а╨г" in text else "╨г╤В╤А╨░╤В╨╕╨╗╨╛ ╤Б╨╕╨╗╤Г" if "╨г╤В╤А╨░╤В╨╕╨╗╨╛ ╤Б╨╕╨╗╤Г" in text else "╨Э╨╡╨╕╨╖╨▓╨╡╤Б╤В╨╜╨╛"

    return {
        "code": code,
        "name": name,
        "okpd2_code": okpd2_code,
        "okpd2_name": okpd2_name,
        "status": status,
        "source_url": f"{CARD}?itemId={code}",
    }


def load_state(output):
    if output.exists():
        with open(output, encoding="utf-8") as f:
            return json.load(f)
    return {"items": {}, "scanned_prefixes": []}


def save_state(state, output):
    tmp = output.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    tmp.replace(output)


def collect_page_codes(session, prefix, page):
    url = f"{SEARCH}?searchString={prefix}&pageNumber={page}&sortBy=CODE"
    html = get_with_retry(session, url)
    if html is None:
        return [], False
    codes = parse_codes_from_search(html)
    return codes, True


def main():
    output = Path("data/ktru_catalog.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    session = build_session()
    state = load_state(output)
    items = state["items"]

    prefixes = all_prefixes()
    total_prefixes = len(prefixes)
    print(f"╨Т╤Б╨╡╨│╨╛ ╤А╨░╨╖╨┤╨╡╨╗╨╛╨▓ ╨Ю╨Ъ╨Я╨Ф2 ╨┤╨╗╤П ╤Б╨║╨░╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╤П: {total_prefixes}", flush=True)
    print(f"╨г╨╢╨╡ ╤Б╨╛╨▒╤А╨░╨╜╨╛ ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣: {len(items)}", flush=True)
    print(f"╨г╨╢╨╡ ╨┐╤А╨╛╤Б╨║╨░╨╜╨╕╤А╨╛╨▓╨░╨╜╨╛ ╨┐╤А╨╡╤Д╨╕╨║╤Б╨╛╨▓: {len(state['scanned_prefixes'])}", flush=True)

    codes_to_fetch = []

    for prefix in prefixes:
        if prefix in state["scanned_prefixes"]:
            continue

        print(f"[{prefix}] ╤Б╨║╨░╨╜╨╕╤А╤Г╤О...", flush=True)
        prefix_codes = []
        seen_pages = set()

        for page in range(1, 200):
            codes, ok = collect_page_codes(session, prefix, page)
            if not ok:
                print(f"  {prefix}: ╨╛╤И╨╕╨▒╨║╨░ ╨╜╨░ ╤Б╤В╤А╨░╨╜╨╕╤Ж╨╡ {page}, ╨┐╤А╨╛╨┐╤Г╤Б╨║╨░╤О ╨┐╤А╨╡╤Д╨╕╨║╤Б", flush=True)
                break
            if not codes:
                break

            page_key = ",".join(sorted(codes))
            if page_key in seen_pages:
                break
            seen_pages.add(page_key)

            new_codes = [c for c in codes if c not in prefix_codes]
            if not new_codes and page > 1:
                break
            prefix_codes.extend(new_codes)

            if page % 10 == 0:
                print(f"  {prefix}: ╤Б╤В╤А {page}, ╨║╨╛╨┤╨╛╨▓ {len(prefix_codes)}", flush=True)

        for code in prefix_codes:
            if code not in items:
                codes_to_fetch.append(code)

        print(f"  {prefix}: {len(prefix_codes)} ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣", flush=True)
        state["scanned_prefixes"].append(prefix)
        save_state(state, output)

        if codes_to_fetch and len(codes_to_fetch) >= 50:
            fetch_cards(session, codes_to_fetch, items, output, state)
            codes_to_fetch = []

    if codes_to_fetch:
        fetch_cards(session, codes_to_fetch, items, output, state)

    save_state(state, output)
    print(f"\n╨У╨Ю╨в╨Ю╨Т╨Ю: {len(items)} ╨┐╨╛╨╖╨╕╤Ж╨╕╨╣ ╨▓ {output}", flush=True)
    return 0


def fetch_cards(session, codes, items, output, state):
    batch_start = time.time()
    fetched = 0
    for code in codes:
        if code in items:
            continue
        url = f"{CARD}?itemId={code}"
        html = get_with_retry(session, url)
        if html is None:
            print(f"  ! ╨║╨░╤А╤В╨╛╤З╨║╨░ {code} ╨╜╨╡ ╨╖╨░╨│╤А╤Г╨╖╨╕╨╗╨░╤Б╤М, ╨┐╤А╨╛╨┐╤Г╤Б╨║╨░╤О", flush=True)
            continue
        items[code] = parse_card(html, code)
        fetched += 1
        if fetched % 20 == 0:
            save_state(state, output)
            rate = fetched / (time.time() - batch_start + 0.1)
            print(f"  ╨║╨░╤А╤В╨╛╤З╨╡╨║: {fetched}/{len(codes)} ({rate:.1f}/╤Б╨╡╨║), ╨▓╤Б╨╡╨│╨╛: {len(items)}", flush=True)
    save_state(state, output)


if __name__ == "__main__":
    sys.exit(main())
