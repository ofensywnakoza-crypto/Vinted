import requests
from typing import Optional


def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def get_bump_candidates(items: list[dict], min_days: int = 14) -> list[dict]:
    candidates = [
        i for i in items
        if i.get("dni_na_rynku", 0) >= min_days
        and i.get("polubionych", 0) >= 3
        and i.get("priorytet") != "wysoki"
    ]
    return sorted(candidates, key=lambda x: x["polubionych"], reverse=True)[:5]


def build_message(items: list[dict], stats: dict, login: str, monthly: dict) -> str:
    urgent = [i for i in items if i["priorytet"] == "wysoki"]
    medium = [i for i in items if i["priorytet"] == "sredni"]
    ok     = [i for i in items if i["priorytet"] == "niski"]
    bumps  = get_bump_candidates(items)

    lines = [
        f"🛍️ <b>Vinted Tracker — raport dla {login}</b>",
        (f"📦 Aktywnych: {stats.get('lacznie_ogloszen', 0)} | "
         f"🚨 Uwagi: {stats.get('wymagaja_uwagi', 0)} | "
         f"💰 {stats.get('lacznie_wartosc', 0):.0f} zł"),
        "",
    ]

    if urgent:
        lines.append(f"🔴 <b>PILNE — działaj teraz ({len(urgent)}):</b>")
        for item in urgent[:5]:
            lines.append(
                f"• <a href=\"{item['url']}\">{item['tytul'][:40]}</a>"
                f" — {item['cena']:.0f} zł | {item['dni_na_rynku']} dni"
            )
            for tip in item["wskazowki"][:2]:
                lines.append(f"  → {tip[:80]}")
        lines.append("")

    if medium:
        lines.append(f"🟡 <b>Warto sprawdzić ({len(medium)}):</b>")
        for item in medium[:3]:
            lines.append(
                f"• <a href=\"{item['url']}\">{item['tytul'][:40]}</a>"
                f" — {item['cena']:.0f} zł"
            )
        lines.append("")

    lines.append(f"✅ Ogłoszeń w porządku: {len(ok)}")
    lines.append(
        f"🎯 Ten miesiąc: {monthly['przychod']:.0f} zł"
        f" / {monthly['cel']:.0f} zł ({monthly['progress_procent']:.0f}%)"
    )

    if bumps:
        lines.append("")
        lines.append(f"💡 <b>Rozważ płatne podbicie ({len(bumps)} ogłoszeń):</b>")
        for item in bumps:
            lines.append(
                f"• <a href=\"{item['url']}\">{item['tytul'][:35]}</a>"
                f" — stoi {item['dni_na_rynku']} dni,"
                f" {item['wyswietlen']} wyśw., {item['polubionych']} pol."
            )

    return "\n".join(lines)[:4096]


def send_alert(cfg: dict, items: list[dict], stats: dict, login: str, monthly: dict) -> bool:
    token   = cfg.get("telegram_token")
    chat_id = cfg.get("telegram_chat_id")
    if not token or not chat_id:
        return False

    urgent_count = stats.get("wymagaja_uwagi", 0)
    bumps = get_bump_candidates(items)

    if urgent_count == 0 and not bumps:
        msg = (
            f"✅ <b>Vinted Tracker</b> — Wszystko w porządku!\n"
            f"📦 {stats.get('lacznie_ogloszen', 0)} ogłoszeń, żadne nie wymaga uwagi.\n"
            f"🎯 Ten miesiąc: {monthly['przychod']:.0f} zł / {monthly['cel']:.0f} zł"
        )
    else:
        msg = build_message(items, stats, login, monthly)

    return send_telegram_message(token, chat_id, msg)
