"""
Monthly revenue goal tracker.
Stores sales in a local JSON file and tracks progress toward the 3499 PLN limit.
"""
import json
import os
from datetime import datetime
from typing import Optional

GOAL_LIMIT = 3499.0
DATA_PATH = os.path.join(os.path.dirname(__file__), ".revenue_data.json")


# ------------------------------------------------------------------ #
# Persistence
# ------------------------------------------------------------------ #

def _load() -> dict:
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH) as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _month_key(dt: datetime = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m")


# ------------------------------------------------------------------ #
# Public API
# ------------------------------------------------------------------ #

def add_sale(amount: float, item_name: str = "", date: datetime = None) -> dict:
    """Record a sale. Returns updated monthly summary."""
    dt = date or datetime.now()
    key = _month_key(dt)
    data = _load()

    if key not in data:
        data[key] = {"revenue": 0.0, "entries": []}

    data[key]["entries"].append({
        "date": dt.strftime("%Y-%m-%d"),
        "amount": round(amount, 2),
        "item": item_name,
    })
    data[key]["revenue"] = round(sum(e["amount"] for e in data[key]["entries"]), 2)
    _save(data)
    return get_monthly_summary(dt)


def get_monthly_summary(dt: datetime = None) -> dict:
    dt = dt or datetime.now()
    key = _month_key(dt)
    data = _load()
    month_data = data.get(key, {"revenue": 0.0, "entries": []})

    revenue = month_data["revenue"]
    remaining = max(0.0, GOAL_LIMIT - revenue)
    progress_pct = min(100.0, round(revenue / GOAL_LIMIT * 100, 1))
    entries = sorted(month_data["entries"], key=lambda x: x["date"], reverse=True)

    # Days left in month
    last_day = (dt.replace(month=dt.month % 12 + 1, day=1) if dt.month < 12
                else dt.replace(year=dt.year + 1, month=1, day=1))
    days_left = (last_day - dt).days

    # Daily target to hit goal
    daily_needed = round(remaining / days_left, 2) if days_left > 0 else 0

    # Status
    if progress_pct >= 100:
        status = "osiagniety"
        advice = "Cel osiągnięty! Wstrzymaj sprzedaż lub poczekaj do następnego miesiąca."
    elif progress_pct >= 85:
        status = "uwaga"
        advice = f"Zostało tylko {remaining:.0f} zł do limitu — sprzedawaj ostrożnie, nie obniżaj cen za mocno."
    elif progress_pct >= 50:
        status = "dobry"
        advice = f"Dobry postęp! Potrzebujesz {daily_needed:.0f} zł dziennie przez {days_left} dni."
    else:
        status = "niski"
        advice = f"Przyspiesz sprzedaż — potrzebujesz {daily_needed:.0f} zł dziennie przez {days_left} dni."

    return {
        "miesiac": dt.strftime("%B %Y"),
        "przychod": revenue,
        "cel": GOAL_LIMIT,
        "pozostalo_do_celu": remaining,
        "progress_procent": progress_pct,
        "status": status,
        "porada": advice,
        "dni_do_konca_miesiaca": days_left,
        "potrzeba_dziennie": daily_needed,
        "ostatnie_sprzedaze": entries[:10],
    }


def get_last_months(n: int = 3) -> list[dict]:
    """Returns summaries for the last N months."""
    data = _load()
    results = []
    now = datetime.now()
    for i in range(n):
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        dt = datetime(year, month, 1)
        key = _month_key(dt)
        month_data = data.get(key, {"revenue": 0.0, "entries": []})
        results.append({
            "miesiac": dt.strftime("%B %Y"),
            "przychod": month_data["revenue"],
            "liczba_sprzedazy": len(month_data["entries"]),
        })
    return results
