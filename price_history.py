import json
import os
from datetime import datetime

HISTORY_PATH = os.path.join(os.path.dirname(__file__), ".price_history.json")


def _load() -> dict:
    if not os.path.exists(HISTORY_PATH):
        return {}
    with open(HISTORY_PATH) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(HISTORY_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_snapshot(items: list[dict]) -> None:
    data = _load()
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False

    for item in items:
        key = str(item["id"])
        if key not in data:
            data[key] = {"tytul": item["tytul"], "url": item["url"], "historia": []}

        existing_dates = {s["data"] for s in data[key]["historia"]}
        if today not in existing_dates:
            data[key]["historia"].append({
                "data": today,
                "cena": item["cena"],
                "wyswietlen": item["wyswietlen"],
                "polubionych": item["polubionych"],
            })
            data[key]["tytul"] = item["tytul"]
            data[key]["url"] = item["url"]
            changed = True

    if changed:
        _save(data)


def get_item_history(item_id) -> list[dict]:
    data = _load()
    return data.get(str(item_id), {}).get("historia", [])


def get_all_history() -> dict:
    return _load()


def get_price_changes(item_id) -> dict | None:
    data = _load()
    key = str(item_id)
    if key not in data:
        return None

    historia = sorted(data[key]["historia"], key=lambda x: x["data"])
    if len(historia) < 2:
        return None

    cena_pierwsza = historia[0]["cena"]
    cena_obecna = historia[-1]["cena"]
    zmiana_pln = round(cena_obecna - cena_pierwsza, 2)
    zmiana_procent = round((zmiana_pln / cena_pierwsza * 100), 1) if cena_pierwsza else 0

    first_dt = datetime.strptime(historia[0]["data"], "%Y-%m-%d")
    last_dt  = datetime.strptime(historia[-1]["data"], "%Y-%m-%d")

    return {
        "item_id": item_id,
        "tytul": data[key]["tytul"],
        "url": data[key].get("url", ""),
        "cena_pierwsza": cena_pierwsza,
        "cena_obecna": cena_obecna,
        "zmiana_pln": zmiana_pln,
        "zmiana_procent": zmiana_procent,
        "liczba_snapshotow": len(historia),
        "dni_obserwacji": (last_dt - first_dt).days,
        "historia": historia,
    }
