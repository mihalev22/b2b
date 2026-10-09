import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
BASE = "https://tzfz.ru/api/ktru/search"

EXTRA_TERMS = [
    "медицинское оборудование",
    "продукты питания",
    "одежда спец",
    "стройматериалы",
    "транспорт средство",
    "образование",
    "медицин",
    "питание",
    "телефон",
    "пожар",
    "безопасность",
    "связь",
    "спорт",
    "сельское хозяйство",
    "лаборатор",
    "измеритель",
    "контроль",
    "автоматизац",
    "робот",
    "дрон",
    "сеть",
    "серверное",
    "хранение данных",
    "копирование",
    "сканирование",
    "ламинирование",
    "переплет",
    "письменные принадлежности",
    "канцеляр",
    "инструмент ручной",
    "инструмент электрический",
    "сварка",
    "измерительный прибор",
    "весы",
    "термометр",
    "микроскоп",
    "анализатор",
    "реактив",
    "кислород",
    "инвалид",
    "протез",
    "ортопед",
    "зубные",
    "рентген",
    "ультразвук",
    "стерилизац",
    "шовный",
    "перевязочн",
    "кровь",
    "вакцина",
    "питательн смесь",
    "молочная",
    "мясная",
    "хлеб",
    "кондитер",
    "овощи",
    "фрукты",
    "напиток",
    "кофе",
    "чай",
    "вода питьевая",
    "сок",
    "мука",
    "крупа",
    "масло растительное",
    "сахар",
    "соль",
    "консервы",
    "заморожен",
    "сухофрукт",
    "орехи",
    "специи",
    "пряности",
    "детское питание",
    "специализированное питание",
]

session = requests.Session()
session.headers.update(HEADERS)

import json
import time

OUTPUT = "data/ktru_full.json"
with open(OUTPUT, encoding="utf-8") as f:
    state = json.load(f)

all_items = state["items"]
done_terms = set(state.get("done_terms", []))
print(f"Загружено: {len(all_items)} позиций")

for term in EXTRA_TERMS:
    if term in done_terms:
        continue
    try:
        r = session.get(f"{BASE}?q={term}", timeout=15)
        items = r.json().get("items", [])
        new = 0
        for item in items:
            code = item.get("ktru_code", "")
            if code and code not in all_items:
                all_items[code] = item
                new += 1
        done_terms.add(term)
        if new:
            print(f"[{term}] +{new} → {len(all_items)}", flush=True)
        time.sleep(0.3)
    except Exception as e:
        print(f"[{term}] error: {e}")
        time.sleep(1)

state["items"] = all_items
state["done_terms"] = list(done_terms)
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False)

print(f"\nИТОГО: {len(all_items)} позиций")
