"""Analiza trendow - Google Trends + OLX + Vinted public search."""
import json
import re
import urllib.parse
from datetime import datetime
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None

from core import database


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

POPULAR_BRANDS_EU = [
    "Nike", "Adidas", "Levi's", "Tommy Hilfiger", "Ralph Lauren",
    "Hugo Boss", "Lacoste", "Calvin Klein", "Diesel", "Carhartt",
    "The North Face", "Patagonia", "Stone Island", "Moncler",
    "Zara", "H&M", "COS", "Reserved", "Massimo Dutti",
]


def google_trends(keywords: list[str], timeframe: str = "today 3-m", geo: str = "PL") -> pd.DataFrame:
    """Zwraca DataFrame z trendami Google dla listy slow kluczowych."""
    if TrendReq is None:
        return pd.DataFrame()
    try:
        pytrends = TrendReq(hl="pl-PL", tz=60, timeout=(10, 25))
        pytrends.build_payload(keywords[:5], cat=0, timeframe=timeframe, geo=geo, gprop="")
        df = pytrends.interest_over_time()
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        return df
    except Exception as exc:
        print(f"Google Trends blad: {exc}")
        return pd.DataFrame()


def trending_brands_score(limit: int = 15) -> list[dict]:
    """Zwroc ranking marek na podstawie Google Trends."""
    cached = _get_cached("trending_brands", max_age_hours=12)
    if cached:
        return cached[:limit]

    results: list[dict] = []
    batch_size = 5
    for i in range(0, len(POPULAR_BRANDS_EU), batch_size):
        batch = POPULAR_BRANDS_EU[i:i + batch_size]
        df = google_trends(batch, timeframe="today 1-m", geo="PL")
        if df.empty:
            continue
        for brand in batch:
            if brand in df.columns:
                avg = float(df[brand].mean())
                recent = float(df[brand].tail(7).mean()) if len(df) >= 7 else avg
                momentum = recent - avg
                results.append({
                    "brand": brand,
                    "avg_interest": round(avg, 1),
                    "recent_interest": round(recent, 1),
                    "momentum": round(momentum, 1),
                })

    results.sort(key=lambda r: (r["recent_interest"] + r["momentum"]), reverse=True)
    _save_cache("trending_brands", results)
    return results[:limit]


def search_olx(query: str, max_pages: int = 1) -> list[dict]:
    """Publiczne wyszukiwanie na OLX (HTML scraping)."""
    results: list[dict] = []
    encoded = urllib.parse.quote(query)
    headers = {"User-Agent": UA, "Accept-Language": "pl-PL,pl;q=0.9"}

    for page in range(1, max_pages + 1):
        url = f"https://www.olx.pl/moda/q-{encoded}/?page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select('[data-cy="l-card"]')
            for card in cards[:30]:
                title_el = card.select_one("h6, h4")
                price_el = card.select_one('[data-testid="ad-price"], p.css-10b0gli')
                link_el = card.select_one("a")
                img_el = card.select_one("img")
                if not title_el or not price_el or not link_el:
                    continue
                price_txt = price_el.get_text(strip=True)
                price_match = re.search(r"(\d+[\s ]?\d*)", price_txt.replace(",", "."))
                if not price_match:
                    continue
                price = float(price_match.group(1).replace(" ", "").replace(" ", ""))
                href = link_el.get("href", "")
                if href.startswith("/"):
                    href = "https://www.olx.pl" + href
                results.append({
                    "source": "OLX",
                    "title": title_el.get_text(strip=True),
                    "price": price,
                    "url": href,
                    "image_url": img_el.get("src") if img_el else None,
                })
        except Exception as exc:
            print(f"OLX search error: {exc}")
            break
    return results


def search_vinted_public(query: str, catalog: Optional[str] = None, max_items: int = 30) -> list[dict]:
    """Publiczne wyszukiwanie na Vinted (bez logowania)."""
    results: list[dict] = []
    encoded = urllib.parse.quote(query)
    url = f"https://www.vinted.pl/catalog?search_text={encoded}&order=price_low_to_high"
    headers = {"User-Agent": UA, "Accept-Language": "pl-PL"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return results
        soup = BeautifulSoup(resp.text, "lxml")
        items = soup.select('[data-testid^="product-item-id-"]')
        for item in items[:max_items]:
            title_el = item.select_one('[data-testid$="--description-title"]')
            price_el = item.select_one('[data-testid$="--price-text"]')
            link_el = item.select_one("a")
            img_el = item.select_one("img")
            if not title_el or not price_el:
                continue
            price_txt = price_el.get_text(strip=True).replace(",", ".")
            price_match = re.search(r"(\d+\.?\d*)", price_txt)
            if not price_match:
                continue
            results.append({
                "source": "Vinted",
                "title": title_el.get_text(strip=True),
                "price": float(price_match.group(1)),
                "url": link_el.get("href", "") if link_el else "",
                "image_url": img_el.get("src") if img_el else None,
            })
    except Exception as exc:
        print(f"Vinted search error: {exc}")

    return results


def find_deals(brands: Optional[list[str]] = None, price_threshold_factor: float = 0.5) -> list[dict]:
    """Znajduje okazje - rzeczy wystawione znacznie ponizej sredniej ceny."""
    brands = brands or ["Nike", "Adidas", "Tommy Hilfiger", "Levi's", "Carhartt", "Ralph Lauren"]
    deals: list[dict] = []

    for brand in brands:
        olx_items = search_olx(brand, max_pages=1)
        vinted_items = search_vinted_public(brand, max_items=30)

        all_items = olx_items + vinted_items
        if len(all_items) < 3:
            continue
        prices = [i["price"] for i in all_items if i["price"] > 5]
        if not prices:
            continue
        avg_price = sum(prices) / len(prices)
        median_price = sorted(prices)[len(prices) // 2]
        threshold = median_price * price_threshold_factor

        for item in all_items:
            if item["price"] <= threshold and item["price"] > 5:
                item["brand"] = brand
                item["estimated_resell"] = round(median_price, 2)
                item["margin_pct"] = round((median_price - item["price"]) / median_price * 100, 1)
                deals.append(item)
                database.save_deal(item)

    deals.sort(key=lambda d: d.get("margin_pct", 0), reverse=True)
    return deals[:50]


def _get_cached(key: str, max_age_hours: int = 12) -> Optional[list]:
    value = database.get_setting(f"cache_{key}")
    if not value:
        return None
    try:
        payload = json.loads(value)
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        age_hours = (datetime.now() - fetched_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            return None
        return payload["data"]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _save_cache(key: str, data: list) -> None:
    payload = json.dumps({
        "fetched_at": datetime.now().isoformat(),
        "data": data,
    })
    database.set_setting(f"cache_{key}", payload)


if __name__ == "__main__":
    print("Top marki (Google Trends):")
    for b in trending_brands_score(10):
        print(f"  {b['brand']:20} score={b['recent_interest']:5.1f} momentum={b['momentum']:+5.1f}")
