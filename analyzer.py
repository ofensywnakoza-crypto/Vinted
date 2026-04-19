from datetime import datetime, timezone
from collections import defaultdict


# ------------------------------------------------------------------ #
# Raw API → structured dicts
# ------------------------------------------------------------------ #

def parse_items(raw_items: list[dict]) -> list[dict]:
    result = []
    now = datetime.now(timezone.utc)
    for item in raw_items:
        try:
            price = float(item.get("price", {}).get("amount", 0))
            created_raw = item.get("created_at_ts") or item.get("created_at", "")
            if created_raw:
                created_raw = created_raw.replace("Z", "+00:00")
                created_at = datetime.fromisoformat(created_raw)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                days_on_market = (now - created_at).days
            else:
                days_on_market = 0

            stats = item.get("stats_visible") or {}
            result.append({
                "id": item["id"],
                "tytul": item.get("title", "—"),
                "marka": item.get("brand_title") or "Inna",
                "kategoria": item.get("catalog_title") or "—",
                "cena": price,
                "dni_na_rynku": days_on_market,
                "wyswietlen": stats.get("view_count", 0),
                "polubionych": item.get("favourite_count", 0),
                "status": item.get("status", "active"),
                "rozmiar": item.get("size_title") or "—",
                "url": f"https://www.vinted.pl/items/{item['id']}",
                "catalog_id": item.get("catalog_id"),
                "brand_id": item.get("brand_id"),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return result


# ------------------------------------------------------------------ #
# Recommendations
# ------------------------------------------------------------------ #

_PRIORITY_ORDER = {"wysoki": 0, "sredni": 1, "niski": 2}


def _score_item(item: dict) -> tuple[str, list[str]]:
    tips = []
    priority = "niski"
    days = item["dni_na_rynku"]
    views = item["wyswietlen"]
    fav = item["polubionych"]
    price = item["cena"]

    # --- Market data tips (highest confidence — based on real transactions) ---
    rynek = item.get("rynek")
    if rynek and rynek.get("verdict") not in (None, "brak danych rynkowych", "cena ok"):
        v_med = rynek.get("vinted_median")
        e_med = rynek.get("ebay_median")
        rec   = rynek.get("recommended_price")
        sources = []
        if e_med:
            sources.append(f"eBay: {e_med:.0f} zł ({rynek['ebay_count']} sprzedanych)")
        if v_med:
            sources.append(f"Vinted: {v_med:.0f} zł ({rynek['vinted_count']} aktywnych)")
        source_str = " | ".join(sources)

        verdict = rynek["verdict"]
        if verdict == "za wysoka":
            tips.append(
                f"Cena za wysoka wg rynku ({source_str}). "
                f"Sugerowana cena: {rec:.0f} zł."
            )
            priority = "wysoki"
        elif verdict == "lekko za wysoka":
            tips.append(
                f"Cena lekko powyżej rynku ({source_str}). "
                f"Rozważ obniżkę do {rec:.0f} zł."
            )
            if priority == "niski":
                priority = "sredni"
        elif verdict == "prawdopodobnie za niska":
            tips.append(
                f"Możesz zarobić więcej — rynek płaci ok. {rec:.0f} zł ({source_str})."
            )

    # --- Behaviour-based tips ---
    if days > 60:
        tips.append(f"Stoi {days} dni — obniż cenę o 20% lub dodaj do promocji")
        priority = "wysoki"
    elif days > 30:
        tips.append(f"Stoi {days} dni — obniż cenę o 10–15%")
        priority = "wysoki"
    elif days > 14:
        tips.append("Ponad 2 tygodnie bez sprzedaży — rozważ obniżkę o 5–10%")
        if priority == "niski":
            priority = "sredni"

    if views > 80 and days > 7:
        tips.append(f"{views} wyświetleń bez zakupu — cena prawdopodobnie za wysoka")
        priority = "wysoki"
    elif views < 10 and days > 4:
        tips.append("Mało wyświetleń — popraw tytuł, zdjęcia lub opis")
        if priority == "niski":
            priority = "sredni"

    if fav >= 10 and days > 5:
        suggestion = round(price * 0.93, 0)
        tips.append(f"{fav} osób obserwuje — obniż do {suggestion:.0f} zł żeby ich zachęcić")
        priority = "wysoki"
    elif fav >= 5 and days > 7:
        tips.append(f"{fav} polubień — mała obniżka może sfinalizować sprzedaż")
        if priority == "niski":
            priority = "sredni"

    if not tips:
        if rynek and rynek.get("verdict") == "cena ok":
            tips.append(f"Cena zgodna z rynkiem ({rynek['detail']}) — czekaj na kupca")
        else:
            tips.append("Ogłoszenie wygląda dobrze — czekaj na kupca")

    return priority, tips


def add_recommendations(items: list[dict]) -> list[dict]:
    for item in items:
        priority, tips = _score_item(item)
        item["priorytet"] = priority
        item["wskazowki"] = tips
    return sorted(items, key=lambda x: _PRIORITY_ORDER.get(x["priorytet"], 9))


# ------------------------------------------------------------------ #
# Summary stats
# ------------------------------------------------------------------ #

def calc_stats(items: list[dict]) -> dict:
    if not items:
        return {}

    prices = [i["cena"] for i in items]
    days = [i["dni_na_rynku"] for i in items]
    urgent = sum(1 for i in items if i.get("priorytet") == "wysoki")

    brand_profit: dict[str, float] = defaultdict(float)
    brand_count: dict[str, int] = defaultdict(int)
    for i in items:
        brand_profit[i["marka"]] += i["cena"]
        brand_count[i["marka"]] += 1

    top_brands = sorted(brand_profit.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "lacznie_ogloszen": len(items),
        "wymagaja_uwagi": urgent,
        "srednia_cena": round(sum(prices) / len(prices), 2),
        "lacznie_wartosc": round(sum(prices), 2),
        "sredni_czas_na_rynku": round(sum(days) / len(days), 1),
        "najdluzej_stojace_dni": max(days),
        "top_marki": [{"marka": b, "wartosc_pln": round(v, 2), "sztuk": brand_count[b]} for b, v in top_brands],
    }
