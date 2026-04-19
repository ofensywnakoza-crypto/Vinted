"""
Trend analysis module — finds what sells fast and where to source cheap.

Data sources:
  Vinted   : trending categories/brands (high engagement, fast moving)
  OLX      : cheap sourcing opportunities (arbitrage vs Vinted prices)
  Google Trends : seasonal demand patterns for Poland
"""
import time
import statistics
import requests
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _get(url: str, params: dict = None, headers: dict = None, timeout: int = 15) -> Optional[dict]:
    try:
        time.sleep(2.0)
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


_VINTED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.vinted.pl/",
}


# ------------------------------------------------------------------ #
# 1. Vinted — trending categories and brands
# ------------------------------------------------------------------ #

# Categories worth tracking on Vinted Poland
TRACKED_CATALOGS = [
    {"id": 1904, "name": "Kurtki damskie"},
    {"id": 1903, "name": "Płaszcze damskie"},
    {"id": 2050, "name": "Sukienki"},
    {"id": 2054, "name": "Spodnie damskie"},
    {"id": 1900, "name": "Bluzy damskie"},
    {"id": 2646, "name": "Kurtki męskie"},
    {"id": 2642, "name": "Bluzy męskie"},
    {"id": 2648, "name": "Spodnie męskie"},
    {"id": 1187, "name": "Buty damskie"},
    {"id": 1190, "name": "Buty męskie"},
]

TOP_BRANDS = [
    "Zara", "H&M", "Reserved", "Mango", "Levi's",
    "Nike", "Adidas", "Pull&Bear", "Stradivarius", "Bershka",
]


def _vinted_search(catalog_id: int, per_page: int = 96, order: str = "relevance") -> list[dict]:
    data = _get(
        "https://www.vinted.pl/api/v2/catalog/items",
        params={"catalog_ids[]": catalog_id, "per_page": per_page, "order": order},
        headers=_VINTED_HEADERS,
    )
    return data.get("items", []) if data else []


def _engagement_score(item: dict) -> float:
    """Higher score = more interest relative to time listed."""
    fav = item.get("favourite_count", 0)
    created_raw = item.get("created_at_ts") or item.get("created_at", "")
    if not created_raw:
        return fav
    try:
        created_raw = created_raw.replace("Z", "+00:00")
        created_at = datetime.fromisoformat(created_raw)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days = max((datetime.now(timezone.utc) - created_at).days, 1)
        return fav / days  # favourites per day
    except Exception:
        return fav


def get_vinted_trending() -> list[dict]:
    """
    Returns categories ranked by average engagement score.
    High score = items get many favourites quickly = strong demand.
    """
    results = []
    for cat in TRACKED_CATALOGS:
        items = _vinted_search(cat["id"], per_page=48)
        if not items:
            continue

        scores = [_engagement_score(i) for i in items]
        prices = [float(i.get("price", {}).get("amount", 0)) for i in items if i.get("price")]
        avg_score = statistics.mean(scores) if scores else 0
        avg_price = round(statistics.median(prices), 0) if prices else 0

        # Top brands in this category
        brand_counts: dict[str, int] = defaultdict(int)
        for i in items:
            b = i.get("brand_title", "")
            if b:
                brand_counts[b] += 1
        top_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:3]

        results.append({
            "kategoria": cat["name"],
            "catalog_id": cat["id"],
            "popularnosc": round(avg_score, 3),
            "mediana_ceny": avg_price,
            "top_marki": [b for b, _ in top_brands],
            "liczba_ogloszen": len(items),
        })

    return sorted(results, key=lambda x: x["popularnosc"], reverse=True)


# ------------------------------------------------------------------ #
# 2. OLX — cheap sourcing opportunities
# ------------------------------------------------------------------ #

OLX_CATEGORY_MAP = {
    "Kurtki damskie":   {"id": "1548", "query": "kurtka damska"},
    "Płaszcze damskie": {"id": "1548", "query": "płaszcz damski"},
    "Sukienki":         {"id": "1549", "query": "sukienka"},
    "Spodnie damskie":  {"id": "1549", "query": "spodnie damskie"},
    "Bluzy damskie":    {"id": "1549", "query": "bluza damska"},
    "Kurtki męskie":    {"id": "1550", "query": "kurtka męska"},
    "Bluzy męskie":     {"id": "1550", "query": "bluza męska"},
    "Spodnie męskie":   {"id": "1550", "query": "spodnie męskie"},
}


def _get_olx_offers(query: str, max_price: int = 80) -> list[dict]:
    data = _get(
        "https://www.olx.pl/api/v1/offers/",
        params={
            "query": query,
            "price[to]": max_price,
            "limit": 50,
            "offset": 0,
            "currency": "PLN",
            "sort_by": "created_at:desc",
        },
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    if not data:
        return []
    return data.get("data", [])


def find_olx_arbitrage(vinted_trending: list[dict], top_n: int = 5) -> list[dict]:
    """
    For top trending Vinted categories, find cheap OLX listings.
    Returns opportunities sorted by potential margin.
    """
    opportunities = []
    for cat in vinted_trending[:top_n]:
        cat_name = cat["kategoria"]
        olx_info = OLX_CATEGORY_MAP.get(cat_name)
        if not olx_info:
            continue

        vinted_median = cat["mediana_ceny"]
        if not vinted_median:
            continue

        max_buy = round(vinted_median * 0.45, 0)  # target max 45% of sell price
        offers = _get_olx_offers(olx_info["query"], max_price=int(max_buy))

        olx_prices = []
        sample_offers = []
        for offer in offers[:20]:
            try:
                price = float(offer["params"]["price"]["value"]["value"])
                title = offer.get("title", "")
                url = offer.get("url", "")
                olx_prices.append(price)
                sample_offers.append({"tytul": title, "cena": price, "url": url})
            except (KeyError, TypeError, ValueError):
                continue

        if not olx_prices:
            continue

        avg_olx = round(statistics.median(olx_prices), 0)
        margin_pct = round((vinted_median - avg_olx) / avg_olx * 100, 0)

        if margin_pct < 30:
            continue

        opportunities.append({
            "kategoria": cat_name,
            "top_marki": cat["top_marki"],
            "cena_skupu_olx": avg_olx,
            "cena_sprzedazy_vinted": vinted_median,
            "marza_procent": margin_pct,
            "max_cena_skupu": max_buy,
            "przykladowe_oferty": sample_offers[:3],
            "popularnosc_vinted": cat["popularnosc"],
        })

    return sorted(opportunities, key=lambda x: x["marza_procent"], reverse=True)


# ------------------------------------------------------------------ #
# 3. Google Trends — seasonal demand in Poland
# ------------------------------------------------------------------ #

SEASONAL_KEYWORDS = {
    "Kurtki zimowe":   ["kurtka zimowa", "kurtka puchowa"],
    "Kurtki letnie":   ["kurtka letnia", "wiatrówka"],
    "Sukienki letnie": ["sukienka letnia", "sukienka midi"],
    "Płaszcze":        ["płaszcz wełniany", "płaszcz damski"],
    "Bluzy":           ["bluza oversize", "bluza dresowa"],
    "Buty zimowe":     ["buty zimowe", "śniegowce"],
    "Sandały":         ["sandały damskie", "klapki"],
}


def get_seasonal_trends() -> list[dict]:
    """Returns categories with rising/falling demand based on Google Trends."""
    if not PYTRENDS_AVAILABLE:
        return [{"info": "Zainstaluj pytrends: pip install pytrends"}]

    results = []
    pytrends = TrendReq(hl="pl-PL", tz=60)
    now = datetime.now()

    for category, keywords in SEASONAL_KEYWORDS.items():
        try:
            pytrends.build_payload(keywords[:2], geo="PL", timeframe="today 3-m")
            df = pytrends.interest_over_time()
            if df.empty:
                continue

            col = keywords[0]
            if col not in df.columns:
                continue

            values = df[col].tolist()
            if len(values) < 4:
                continue

            recent = statistics.mean(values[-4:])    # last 4 weeks
            previous = statistics.mean(values[-12:-4]) if len(values) >= 12 else statistics.mean(values[:-4])

            if previous == 0:
                continue

            trend_pct = round((recent - previous) / previous * 100, 0)
            trend_label = "rosnący" if trend_pct > 10 else ("spadający" if trend_pct < -10 else "stabilny")

            results.append({
                "kategoria": category,
                "trend": trend_label,
                "zmiana_procent": trend_pct,
                "aktualny_popyt": round(recent, 0),
                "rekomendacja": (
                    "Kup teraz — popyt rośnie" if trend_pct > 10
                    else ("Poczekaj — sezon się kończy" if trend_pct < -10
                          else "Stabilny rynek")
                ),
            })
            time.sleep(1.0)  # be gentle with Google Trends API
        except Exception:
            continue

    return sorted(results, key=lambda x: x["zmiana_procent"], reverse=True)


# ------------------------------------------------------------------ #
# 4. Full sourcing list — combines all sources
# ------------------------------------------------------------------ #

def generate_sourcing_list(monthly_remaining: float = 3499.0) -> dict:
    """
    Main function — generates a complete weekly sourcing recommendation.
    monthly_remaining: how much more revenue can be earned this month
    """
    # How many items can we sell this month
    avg_sell_price = 75.0
    items_budget = max(0, int(monthly_remaining / avg_sell_price))

    trending = get_vinted_trending()
    arbitrage = find_olx_arbitrage(trending, top_n=6)
    seasonal = get_seasonal_trends()

    # Build shopping list
    shopping_list = []
    for opp in arbitrage[:5]:
        item_count = max(1, min(3, items_budget // 3))
        shopping_list.append({
            "co_kupic": opp["kategoria"],
            "marki": ", ".join(opp["top_marki"]) or "dowolna znana marka",
            "max_cena_zakupu": opp["max_cena_skupu"],
            "oczekiwana_sprzedaz": opp["cena_sprzedazy_vinted"],
            "marza_procent": opp["marza_procent"],
            "ile_sztuk": item_count,
            "gdzie_szukac": "OLX.pl",
            "przykladowe_oferty": opp["przykladowe_oferty"],
        })

    return {
        "data_generowania": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "mozliwy_przychod_w_miesiacu": round(monthly_remaining, 0),
        "trending_kategorie": trending[:5],
        "arbitraz_olx": arbitrage,
        "trendy_sezonowe": seasonal,
        "lista_zakupow": shopping_list,
    }
