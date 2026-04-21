"""Silnik rekomendacji - analiza ogloszen i generowanie akcji."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from core import database


ActionType = Literal["LOWER_PRICE", "REFRESH", "RELIST", "BOOST", "KEEP", "RAISE_PRICE"]

PRIORITY = {
    "RELIST": 1,
    "LOWER_PRICE": 2,
    "REFRESH": 3,
    "BOOST": 4,
    "RAISE_PRICE": 5,
    "KEEP": 6,
}

LABELS = {
    "RELIST": "Usun i wystaw od nowa",
    "LOWER_PRICE": "Obniz cene",
    "REFRESH": "Odswiez ogloszenie",
    "BOOST": "Promuj (podbij)",
    "RAISE_PRICE": "Podwyzsz cene",
    "KEEP": "Zostaw",
}

EMOJIS = {
    "RELIST": "🔄",
    "LOWER_PRICE": "⬇️",
    "REFRESH": "✨",
    "BOOST": "🚀",
    "RAISE_PRICE": "⬆️",
    "KEEP": "✅",
}


@dataclass
class Recommendation:
    listing_id: int
    title: str
    current_price: float | None
    days_on_market: int
    views: int
    likes: int
    action: ActionType
    reason: str
    suggested_price: float | None = None


def _days_since(date_str: str | None) -> int:
    if not date_str:
        return 0
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days
    except ValueError:
        return 0


def _suggest_new_price(current: float | None, discount_pct: float = 10.0) -> float | None:
    if current is None or current <= 0:
        return None
    new_price = current * (1 - discount_pct / 100)
    return round(new_price, 2)


def analyze_listing(listing: dict) -> Recommendation:
    listing_id = listing["id"]
    title = listing.get("title", "")
    price = listing.get("list_price")
    views = listing.get("current_views") or 0
    likes = listing.get("current_likes") or 0
    days = _days_since(listing.get("listed_date"))

    if days >= 7 and views == 0 and likes == 0:
        return Recommendation(
            listing_id=listing_id, title=title, current_price=price,
            days_on_market=days, views=views, likes=likes,
            action="RELIST",
            reason=f"7+ dni bez zadnego zainteresowania ({days} dni, 0 wyswietlen, 0 polubien). "
                   "Usun i wystaw od nowa ze zmienionymi zdjeciami i tytulem.",
        )

    if days >= 7 and views > 0 and likes == 0:
        return Recommendation(
            listing_id=listing_id, title=title, current_price=price,
            days_on_market=days, views=views, likes=likes,
            action="LOWER_PRICE",
            reason=f"{days} dni na rynku, {views} wyswietlen, 0 polubien. "
                   "Ludzie ogladaja ale nie kupuja - obniz cene o 10%.",
            suggested_price=_suggest_new_price(price, 10),
        )

    if days >= 7 and views == 0:
        return Recommendation(
            listing_id=listing_id, title=title, current_price=price,
            days_on_market=days, views=views, likes=likes,
            action="REFRESH",
            reason=f"{days} dni bez wyswietlen. Odswiez ogloszenie (edycja tytulu / hashtagi).",
        )

    if days >= 14 and likes >= 3 and views >= 30:
        return Recommendation(
            listing_id=listing_id, title=title, current_price=price,
            days_on_market=days, views=views, likes=likes,
            action="LOWER_PRICE",
            reason=f"Duze zainteresowanie ({likes} polubien, {views} wyswietlen) ale brak sprzedazy "
                   f"od {days} dni. Obniz cene o 5-10% zeby zamknac transakcje.",
            suggested_price=_suggest_new_price(price, 7),
        )

    if days <= 3 and likes >= 5:
        return Recommendation(
            listing_id=listing_id, title=title, current_price=price,
            days_on_market=days, views=views, likes=likes,
            action="RAISE_PRICE",
            reason=f"Swietne zainteresowanie w krotkim czasie ({likes} polubien w {days} dni). "
                   "Mozesz sprobowac podniesc cene o 5-10%.",
            suggested_price=round(price * 1.07, 2) if price else None,
        )

    if days >= 5 and 1 <= likes < 3:
        return Recommendation(
            listing_id=listing_id, title=title, current_price=price,
            days_on_market=days, views=views, likes=likes,
            action="BOOST",
            reason=f"{days} dni, {likes} polubien - umiarkowane zainteresowanie. "
                   "Rozwaz promowanie ogloszenia (Vinted Push).",
        )

    return Recommendation(
        listing_id=listing_id, title=title, current_price=price,
        days_on_market=days, views=views, likes=likes,
        action="KEEP",
        reason=f"Ogloszenie wyglada dobrze ({days} dni, {views} wyswietlen, {likes} polubien).",
    )


def get_recommendations(only_actionable: bool = True) -> list[Recommendation]:
    active = database.get_active_listings()
    recs = [analyze_listing(l) for l in active]
    if only_actionable:
        recs = [r for r in recs if r.action != "KEEP"]
    recs.sort(key=lambda r: (PRIORITY.get(r.action, 99), -r.days_on_market))
    return recs


def format_for_telegram(recs: list[Recommendation]) -> str:
    if not recs:
        return "🎉 *Dzien dobry!*\n\nBrak pilnych akcji - wszystkie Twoje ogloszenia wygladaja dobrze."

    lines = [f"🌅 *Poranny raport Vinted*\n"]
    lines.append(f"Znalazlem *{len(recs)}* ogloszen wymagajacych akcji:\n")

    by_action: dict[str, list[Recommendation]] = {}
    for r in recs:
        by_action.setdefault(r.action, []).append(r)

    for action_type in sorted(by_action.keys(), key=lambda a: PRIORITY.get(a, 99)):
        group = by_action[action_type]
        emoji = EMOJIS.get(action_type, "•")
        label = LABELS.get(action_type, action_type)
        lines.append(f"\n{emoji} *{label}* ({len(group)}):")
        for r in group[:10]:
            price_str = f"{r.current_price:.0f} zl" if r.current_price else "?"
            extra = ""
            if r.suggested_price:
                extra = f" → *{r.suggested_price:.0f} zl*"
            lines.append(f"  • {r.title[:40]} ({price_str}{extra}, {r.days_on_market}d)")
        if len(group) > 10:
            lines.append(f"  ... i {len(group) - 10} wiecej")

    lines.append("\n_Szczegoly w aplikacji._")
    return "\n".join(lines)


def format_sales_summary(target_date: str | None = None) -> str:
    target = target_date or date.today().isoformat()
    sales_today = database.get_sales_on_date(target)

    y, m, _ = target.split("-")
    sales_month = database.get_sales_in_month(int(y), int(m))

    total_today = sum((s.get("net_profit") or 0) for s in sales_today)
    total_month = sum((s.get("net_profit") or 0) for s in sales_month)

    from config import MONTHLY_GOAL_PLN
    pct = (total_month / MONTHLY_GOAL_PLN * 100) if MONTHLY_GOAL_PLN else 0

    lines = [f"🌙 *Podsumowanie dnia - {target}*\n"]

    if sales_today:
        lines.append(f"💰 Sprzedano *{len(sales_today)}* sztuk za *{total_today:.2f} zl*:")
        for s in sales_today[:10]:
            lines.append(f"  • {s['title'][:40]} - {s.get('sold_price', 0):.0f} zl")
    else:
        lines.append("Dzis brak sprzedazy.")

    lines.append(f"\n📊 *W tym miesiacu:* {total_month:.2f} / {MONTHLY_GOAL_PLN:.0f} zl ({pct:.1f}%)")

    if pct >= 100:
        lines.append("⚠️ Przekroczono limit 3 499 zl - uwazaj na podatki!")
    elif pct >= 85:
        lines.append("⚠️ Zblizasz sie do limitu 3 499 zl.")

    return "\n".join(lines)


if __name__ == "__main__":
    database.init_db()
    recs = get_recommendations()
    print(format_for_telegram(recs))
