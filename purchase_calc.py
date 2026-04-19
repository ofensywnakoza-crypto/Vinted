import time
import statistics
import requests
from typing import Optional

EBAY_FINDING_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
_VINTED_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.vinted.pl/",
}


def _vinted_keyword_search(keywords: str, per_page: int = 96) -> list[dict]:
    try:
        time.sleep(2.0)
        resp = requests.get(
            "https://www.vinted.pl/api/v2/catalog/items",
            params={"search_text": keywords, "per_page": per_page, "order": "relevance"},
            headers=_VINTED_HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("items", [])
    except Exception:
        pass
    return []


def _ebay_sold_prices(keywords: str, app_id: str) -> list[float]:
    try:
        time.sleep(1.0)
        resp = requests.get(
            EBAY_FINDING_URL,
            params={
                "OPERATION-NAME": "findCompletedItems",
                "SERVICE-VERSION": "1.0.0",
                "SECURITY-APPNAME": app_id,
                "RESPONSE-DATA-FORMAT": "JSON",
                "GLOBAL-ID": "EBAY-PL",
                "keywords": keywords,
                "itemFilter(0).name": "SoldItemsOnly",
                "itemFilter(0).value": "true",
                "paginationInput.entriesPerPage": "50",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        raw_items = (
            resp.json()
            .get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
            .get("item", [])
        )
        prices = []
        for item in raw_items:
            try:
                price_info = item["sellingStatus"][0]["currentPrice"][0]
                value    = float(price_info.get("_value_", 0))
                currency = price_info.get("@currencyId", "")
                if value > 0:
                    prices.append(value * (4.25 if currency == "EUR" else 1))
            except (KeyError, IndexError, ValueError):
                continue
        return prices
    except Exception:
        return []


def estimate_profit(
    title: str,
    brand_name: str,
    max_buy_price: float,
    vinted_client=None,
    ebay_app_id: Optional[str] = None,
) -> dict:
    keywords = f"{brand_name} {title}".strip() if brand_name else title

    # --- Vinted prices ---
    raw_vinted = []
    if vinted_client:
        try:
            raw_vinted = vinted_client.search_similar(per_page=96) or []
        except Exception:
            pass
    if not raw_vinted:
        raw_vinted = _vinted_keyword_search(keywords)

    vinted_prices = []
    for item in raw_vinted:
        try:
            p = float(item.get("price", {}).get("amount", 0))
            if p > 0:
                vinted_prices.append(p)
        except (TypeError, ValueError):
            continue

    # --- eBay prices ---
    ebay_prices = _ebay_sold_prices(keywords, ebay_app_id) if ebay_app_id else []

    # --- Calculate ---
    vinted_median = round(statistics.median(vinted_prices), 2) if len(vinted_prices) >= 3 else None
    ebay_median   = round(statistics.median(ebay_prices),   2) if len(ebay_prices)   >= 3 else None

    if vinted_median is None and ebay_median is None:
        return {
            "error": None,
            "vinted_median": None,
            "ebay_median": None,
            "recommended_sell_price": None,
            "estimated_profit": None,
            "estimated_margin_pct": None,
            "days_to_sell_estimate": "brak danych",
            "verdict": "brak danych",
            "vinted_active_count": len(vinted_prices),
            "ebay_sold_count": len(ebay_prices),
        }

    if vinted_median and ebay_median:
        recommended = round(ebay_median * 0.6 + vinted_median * 0.4, 0)
    else:
        recommended = round(vinted_median or ebay_median, 0)  # type: ignore[arg-type]

    profit     = round(recommended - max_buy_price, 2)
    margin_pct = round(profit / max_buy_price * 100, 1) if max_buy_price > 0 else 0

    count = len(vinted_prices)
    if count <= 10:
        days_estimate = "szybko ~7 dni"
    elif count <= 30:
        days_estimate = "ok. 14 dni"
    else:
        days_estimate = "wolniej ~30 dni+"

    if margin_pct >= 60:
        verdict = "opłacalne"
    elif margin_pct >= 30:
        verdict = "ryzykowne"
    else:
        verdict = "nieopłacalne"

    return {
        "error": None,
        "vinted_median": vinted_median,
        "ebay_median": ebay_median,
        "recommended_sell_price": recommended,
        "estimated_profit": profit,
        "estimated_margin_pct": margin_pct,
        "days_to_sell_estimate": days_estimate,
        "verdict": verdict,
        "vinted_active_count": len(vinted_prices),
        "ebay_sold_count": len(ebay_prices),
    }
