"""Import pliku Excel uzytkownika z danymi ogloszen."""
from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd

from core import database


COLUMN_MAP = {
    "nr": ["nr", "lp", "lp.", "numer"],
    "title": ["tytul", "tytuł", "nazwa", "nazwa produktu", "produkt"],
    "brand": ["marka", "brand"],
    "category": ["kategoria", "category", "typ"],
    "size": ["rozmiar", "size"],
    "color": ["kolor", "color"],
    "cost": ["koszt", "koszt (zl)", "koszt (zł)", "cena zakupu"],
    "list_price": ["cena wyst.", "cena wystawienia", "cena wyst", "cena wyst. (zl)", "cena wyst. (zł)"],
    "sold_price": ["cena sprzed.", "cena sprzedazy", "cena sprzedaży", "cena sprzed", "cena sprzed. (zl)", "cena sprzed. (zł)"],
    "commission": ["prowizja", "prowizja vinted", "prowizja vinted (zl)", "prowizja vinted (zł)"],
    "net_profit": ["zysk netto", "zysk", "zysk netto (zl)", "zysk netto (zł)"],
    "margin": ["marza", "marża", "marza (%)", "marża (%)"],
    "status": ["status"],
    "platform": ["platforma"],
    "channel": ["kanal", "kanał"],
    "listed_date": ["data wystaw.", "data wystawienia", "data wystaw"],
    "sold_date": ["data sprzed.", "data sprzedazy", "data sprzedaży", "data sprzed"],
    "days_to_sell": ["dni na sprzedaz", "dni na sprzedaż", "dni"],
}


def _normalize(text: str) -> str:
    return str(text).strip().lower().replace("\n", " ").replace("  ", " ")


def _match_columns(df_columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    normalized = {_normalize(c): c for c in df_columns}
    for canonical, aliases in COLUMN_MAP.items():
        for alias in aliases:
            if alias in normalized:
                mapping[canonical] = normalized[alias]
                break
    return mapping


def _parse_date(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_number(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "").replace(",", ".").replace("%", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(value) -> int | None:
    n = _parse_number(value)
    return int(n) if n is not None else None


def _parse_title_from_first_row(df: pd.DataFrame) -> str | None:
    """Plik uzytkownika moze miec tytul w nazwie kolumny zamiast naglowka."""
    cols = list(df.columns)
    for c in cols:
        if len(str(c)) > 15 and not any(
            key in _normalize(c)
            for keylist in COLUMN_MAP.values()
            for key in keylist
        ):
            return str(c)
    return None


def import_excel(file_path: Union[str, Path, bytes], sheet_name: int | str = 0) -> dict:
    """Zaimportuj plik Excel lub CSV i zapisz do bazy. Zwraca statystyki importu."""
    path_str = str(file_path) if isinstance(file_path, (str, Path)) else None

    if path_str and path_str.lower().endswith(".csv"):
        df = pd.read_csv(file_path, dtype=str)
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name, dtype=object)

    df.columns = [str(c) for c in df.columns]
    col_map = _match_columns(df.columns)

    if "title" not in col_map:
        probable_title = _parse_title_from_first_row(df)
        if probable_title:
            col_map["title"] = probable_title

    imported = 0
    skipped = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            title = row.get(col_map.get("title", ""), None)
            if title is None or (isinstance(title, float) and pd.isna(title)):
                skipped += 1
                continue
            title = str(title).strip()
            if not title:
                skipped += 1
                continue

            data = {
                "nr": _parse_int(row.get(col_map.get("nr"))) if "nr" in col_map else None,
                "title": title,
                "brand": str(row.get(col_map.get("brand"), "") or "").strip() or None,
                "category": str(row.get(col_map.get("category"), "") or "").strip() or None,
                "size": str(row.get(col_map.get("size"), "") or "").strip() or None,
                "color": str(row.get(col_map.get("color"), "") or "").strip() or None,
                "cost": _parse_number(row.get(col_map.get("cost"))) or 0,
                "list_price": _parse_number(row.get(col_map.get("list_price"))),
                "sold_price": _parse_number(row.get(col_map.get("sold_price"))),
                "commission": _parse_number(row.get(col_map.get("commission"))),
                "net_profit": _parse_number(row.get(col_map.get("net_profit"))),
                "margin": _parse_number(row.get(col_map.get("margin"))),
                "status": str(row.get(col_map.get("status"), "") or "").strip() or "Wystawiony",
                "platform": str(row.get(col_map.get("platform"), "") or "").strip() or "Vinted PL",
                "channel": str(row.get(col_map.get("channel"), "") or "").strip() or None,
                "listed_date": _parse_date(row.get(col_map.get("listed_date"))),
                "sold_date": _parse_date(row.get(col_map.get("sold_date"))),
                "days_to_sell": _parse_int(row.get(col_map.get("days_to_sell"))),
            }
            database.upsert_listing(data)
            imported += 1
        except Exception as exc:
            errors.append(f"Wiersz {idx + 2}: {exc}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "columns_matched": col_map,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uzycie: python excel_import.py <sciezka do pliku .xlsx>")
        sys.exit(1)
    database.init_db()
    result = import_excel(sys.argv[1])
    print(f"Zaimportowano: {result['imported']}")
    print(f"Pominieto: {result['skipped']}")
    if result["errors"]:
        print("Bledy:")
        for e in result["errors"][:10]:
            print(f"  {e}")
