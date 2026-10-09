"""Третий проход: поисковые запросы по названиям товаров для максимального покрытия."""
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://tzfz.ru/api/ktru/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
DELAY = 0.25
OUTPUT = Path("data/ktru_full.json")

SEARCH_TERMS = [
    "автомобиль", "аппарат", "бумага", "баллон", "бензин", "бетон", "блок",
    "валидатор", "вентилятор", "витрина", "вода", "выключатель", "вычисл",
    "газ", "генератор", "гипс", "глав", "графит", "двигатель", "дерево",
    "дверь", "деталь", "дизель", "документ", "доска", "древесина",
    "железо", "жидкость", "жалюзи", "запчасть", "защита", "звук",
    "изделие", "изоляция", "инструмент", "интернет", "информац",
    "кабель", "камень", "камера", "канал", "капсула", "картридж",
    "касса", "качество", "кирпич", "клавиатура", "комплект", "компьютер",
    "конструкция", "контейнер", "контроллер", "концентратор", "корпус",
    "краска", "кресло", "кровать", "кронштейн", "ламп", "лекарство",
    "лента", "лист", "линия", "локатор", "лоток", "машина", "мебель",
    "медицин", "металл", "микроскоп", "монитор", "масло", "маска",
    "насос", "носитель", "накопитель", "оборудование", "окно", "опора",
    "осветитель", "основание", "отходы", "пакет", "панель", "бумага",
    "печать", "пиломатериал", "питание", "плита", "покрытие", "пол",
    "порт", "прибор", "привод", "принтер", "программ", "проектор",
    "прокладка", "противогаз", "профиль", "радиатор", "радио", "рама",
    "расходник", "рейка", "ремень", "реле", "решетка", "розетка",
    "сантехника", "сверло", "светильник", "сервер", "система", "скоба",
    "скоба", "смесь", "снабжение", "соевый", "соединение", "состав",
    "спецодежда", "сталь", "стекло", "стол", "стойка", "строение",
    "сумка", "табло", "телевизор", "телефон", "ткань", "товар",
    "ток", "толщина", "трансформатор", "труба", "ткань", "уборка",
    "указатель", "упаковка", "установка", "устройство", "учебник",
    "файл", "фанера", "фильтр", "форма", "фотография", "химия",
    "холодильник", "хранение", "цилиндр", "цифровой", "чайник",
    "чехол", "шкаф", "шланг", "шприц", "штатив", "экран",
    "электрод", "элемент", "энергия", "ярлык",
]


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

    done_terms = set(state.get("done_terms", []))
    terms = [t for t in SEARCH_TERMS if t not in done_terms]

    for term in terms:
        items = fetch(session, term)
        new = 0
        for item in items:
            code = item.get("ktru_code", "")
            if code and code not in all_items:
                all_items[code] = item
                new += 1

        done_terms.add(term)
        if new > 0:
            print(f"[{term}] +{new} → всего {len(all_items)}", flush=True)

    save(all_items, state, done_terms)
    print(f"\nИТОГО: {len(all_items)} позиций")
    return 0


def save(items, state, done_terms):
    state["items"] = items
    state["done_terms"] = list(done_terms)
    tmp = OUTPUT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    tmp.replace(OUTPUT)


if __name__ == "__main__":
    sys.exit(main())
