"""
Manual listings management via CSV.
User maintains their listings in a CSV file or via Streamlit forms — no Vinted API scraping.
"""
import csv
import os
import uuid
from datetime import date, datetime

LISTINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "my_listings.csv")

FIELDS = [
    "id",
    "tytul",
    "marka",
    "kategoria",
    "cena",
    "data_wystawienia",
    "wyswietlen",
    "polubionych",
    "rozmiar",
    "url",
]


def _ensure_file() -> None:
    os.makedirs(os.path.dirname(LISTINGS_PATH), exist_ok=True)
    if not os.path.exists(LISTINGS_PATH):
        with open(LISTINGS_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()


def load_listings() -> list[dict]:
    _ensure_file()
    rows: list[dict] = []
    today = date.today()
    with open(LISTINGS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            try:
                wystawione = raw.get("data_wystawienia", "").strip()
                if wystawione:
                    data_wyst = datetime.strptime(wystawione, "%Y-%m-%d").date()
                    days = (today - data_wyst).days
                else:
                    days = 0

                rows.append({
                    "id": raw.get("id") or str(uuid.uuid4())[:8],
                    "tytul": raw.get("tytul", "—"),
                    "marka": raw.get("marka") or "Inna",
                    "kategoria": raw.get("kategoria") or "—",
                    "cena": float(raw.get("cena") or 0),
                    "dni_na_rynku": max(0, days),
                    "wyswietlen": int(raw.get("wyswietlen") or 0),
                    "polubionych": int(raw.get("polubionych") or 0),
                    "rozmiar": raw.get("rozmiar") or "—",
                    "url": raw.get("url") or "",
                    "status": "active",
                    "catalog_id": None,
                    "brand_id": None,
                })
            except (ValueError, TypeError):
                continue
    return rows


def save_listings(rows: list[dict]) -> None:
    _ensure_file()
    with open(LISTINGS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})


def add_listing(
    tytul: str,
    marka: str,
    kategoria: str,
    cena: float,
    data_wystawienia: str,
    wyswietlen: int = 0,
    polubionych: int = 0,
    rozmiar: str = "",
    url: str = "",
) -> None:
    _ensure_file()
    with open(LISTINGS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerow({
            "id": str(uuid.uuid4())[:8],
            "tytul": tytul,
            "marka": marka,
            "kategoria": kategoria,
            "cena": cena,
            "data_wystawienia": data_wystawienia,
            "wyswietlen": wyswietlen,
            "polubionych": polubionych,
            "rozmiar": rozmiar,
            "url": url,
        })


def delete_listing(listing_id: str) -> None:
    rows = []
    _ensure_file()
    with open(LISTINGS_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("id") != listing_id:
                rows.append(r)
    with open(LISTINGS_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def import_from_upload(uploaded_bytes: bytes) -> int:
    """Import CSV uploaded via Streamlit. Returns count of imported rows."""
    _ensure_file()
    text = uploaded_bytes.decode("utf-8-sig")
    lines = text.splitlines()
    if not lines:
        return 0

    reader = csv.DictReader(lines)
    count = 0
    with open(LISTINGS_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        for raw in reader:
            row = {k: raw.get(k, "") for k in FIELDS}
            if not row.get("id"):
                row["id"] = str(uuid.uuid4())[:8]
            if not row.get("tytul"):
                continue
            writer.writerow(row)
            count += 1
    return count
