"""
Market data module — fetches competitor prices from Vinted and eBay.

Vinted  : active listings (what competitors charge right now)
eBay PL : completed/sold listings (what buyers actually paid)

Groups items by (brand_id, catalog_id) to minimise API calls.
"""
import time
import statistics
import requests
from typing import Optional
from urllib.parse import quote


# ------------------------------------------------------------------ #
# Vinted market prices
# ------------------------------------------------------------------ #

def _vinted_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": "https://www.vinted.pl/",
    })
    return s


def fetch_vinted_prices(
    catalog_id: int,
    brand_id: Optional[int],
    per_page: int = 96,
) -> list[float]:
    """Return list of active Vinted prices for the given category/brand."""
    params: dict = {"per_page": per_page, "order": "newest_first"}
    if catalog_id:
        params["catalog_ids[]"] = catalog_id
    if brand_id:
        params["brand_ids[]"] = brand_id

    try:
        time.sleep(2.0)
        resp = _vinted_session().get(
            "https://www.vinted.pl/api/v2/catalog/items",
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("items", [])
        return [
            float(i["price"]["amount"])
            for i in items
            if i.get("price", {}).get("amount")
        ]
    except Exception:
        return []


# ------------------------------------------------------------------ #
# eBay market prices (Finding API — free, no OAuth needed)
# ------------------------------------------------------------------ #

EBAY_FINDING_URL = "https://svcs.ebay.com/services/search/FindingService/v1"


def fetch_ebay_sold_prices(keywords: str, app_id: str, entries: int = 50) -> list[float]:
    """Return list of PLN prices from completed/sold eBay PL listings."""
    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "GLOBAL-ID": "EBAY-PL",
        "keywords": keywords,
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "paginationInput.entriesPerPage": str(entries),
    }
    try:
        time.sleep(1.0)
        resp = requests.get(EBAY_FINDING_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        items = (
            data
            .get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
            .get("item", [])
        )
        prices = []
        for item in items:
            try:
                price_info = item["sellingStatus"][0]["currentPrice"][0]
                currency = price_info.get("@currencyId", "")
                value = float(price_info.get("_value_", 0))
                if value > 0:
                    if currency == "PLN":
                        prices.append(value)
                    elif currency == "EUR":
                        prices.append(value * 4.25)  # approximate EUR→PLN
            except (KeyError, IndexError, ValueError):
                continue
        return prices
    except Exception:
        return []


# ------------------------------------------------------------------ #
# Price analysis
# ------------------------------------------------------------------ #

def analyse_price(
    your_price: float,
    vinted_prices: list[float],
    ebay_prices: list[float],
) -> dict:
    """
    Returns a dict with market summary and a price recommendation.
    All prices in PLN.
    """
    result: dict = {
        "vinted_count": len(vinted_prices),
        "ebay_count": len(ebay_prices),
        "vinted_median": None,
        "ebay_median": None,
        "recommended_price": None,
        "verdict": "brak danych rynkowych",
        "detail": "",
    }

    if len(vinted_prices) >= 3:
        result["vinted_median"] = round(statistics.median(vinted_prices), 2)

    if len(ebay_prices) >= 3:
        result["ebay_median"] = round(statistics.median(ebay_prices), 2)

    v_med = result["vinted_median"]
    e_med = result["ebay_median"]

    if v_med is None and e_med is None:
        return result

    # Choose reference: prefer eBay sold (actual transactions) over Vinted active
    ref = e_med if e_med else v_med

    pct_diff = ((your_price - ref) / ref) * 100

    if pct_diff > 20:
        result["verdict"] = "za wysoka"
        result["recommended_price"] = round(ref * 1.05, 0)
        result["detail"] = (
            f"Twoja cena {your_price:.0f} zł jest o {pct_diff:.0f}% wyżej niż rynek ({ref:.0f} zł). "
            f"Sugerowana cena: {result['recommended_price']:.0f} zł."
        )
    elif pct_diff < -20:
        result["verdict"] = "prawdopodobnie za niska"
        result["recommended_price"] = round(ref * 0.95, 0)
        result["detail"] = (
            f"Twoja cena {your_price:.0f} zł jest o {abs(pct_diff):.0f}% niżej niż rynek ({ref:.0f} zł). "
            f"Możesz podnieść do ok. {result['recommended_price']:.0f} zł."
        )
    elif pct_diff > 10:
        result["verdict"] = "lekko za wysoka"
        result["recommended_price"] = round(ref * 1.0, 0)
        result["detail"] = (
            f"Konkurencja sprzedaje za ok. {ref:.0f} zł. "
            f"Rozważ obniżkę do {result['recommended_price']:.0f} zł."
        )
    else:
        result["verdict"] = "cena ok"
        result["detail"] = f"Cena zgodna z rynkiem (rynek: ~{ref:.0f} zł)."

    return result


# ------------------------------------------------------------------ #
# Batch enrichment — call once per unique (brand_id, catalog_id) group
# ------------------------------------------------------------------ #

def enrich_with_market_data(items: list[dict], ebay_app_id: Optional[str] = None) -> list[dict]:
    """
    Adds 'rynek' key to each item dict with price analysis.
    Groups by (brand_id, catalog_id) to avoid duplicate API calls.
    Only processes items with priorytet != 'niski' to limit calls.
    """
    # Build lookup of unique groups → market prices
    cache: dict[tuple, dict] = {}

    for item in items:
        if item.get("priorytet") == "niski":
            item["rynek"] = None
            continue

        key = (item.get("catalog_id"), item.get("brand_id"))

        if key not in cache:
            catalog_id, brand_id = key
            v_prices = fetch_vinted_prices(catalog_id or 0, brand_id) if catalog_id else []

            e_prices = []
            if ebay_app_id:
                keywords = f"{item.get('marka', '')} {item.get('kategoria', '')}".strip()
                if keywords:
                    e_prices = fetch_ebay_sold_prices(keywords, ebay_app_id)

            cache[key] = {"vinted": v_prices, "ebay": e_prices}

        market = cache[key]
        item["rynek"] = analyse_price(
            item["cena"],
            market["vinted"],
            market["ebay"],
        )

    return items
