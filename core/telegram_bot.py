"""Bot Telegram - wysyla raporty 6:00 i 22:00 oraz obsluguje komendy."""
import asyncio
from datetime import date

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core import database, rules


API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, chat_id: str | None = None, parse_mode: str = "Markdown") -> bool:
    """Synchronizne wyslanie wiadomosci - uzywane przez scheduler."""
    if not TELEGRAM_BOT_TOKEN:
        print("[Telegram] Brak tokenu - pomijam wysylke.")
        return False

    target = chat_id or TELEGRAM_CHAT_ID or database.get_setting("telegram_chat_id")
    if not target:
        print("[Telegram] Brak chat_id - wyslij /start do bota aby zapisal twoje ID.")
        return False

    url = f"{API_BASE}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": target,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            print(f"[Telegram] Blad: {resp.status_code} {resp.text}")
            return False
        return True
    except Exception as exc:
        print(f"[Telegram] Wyjatek: {exc}")
        return False


def send_morning_report() -> bool:
    recs = rules.get_recommendations(only_actionable=True)
    text = rules.format_for_telegram(recs)
    for r in recs:
        database.log_action(r.listing_id, r.action, r.reason)
    return send_message(text)


def send_evening_report() -> bool:
    text = rules.format_sales_summary()
    return send_message(text)


def get_updates(offset: int | None = None) -> list:
    """Pobiera nowe wiadomosci do bota - zeby wykryc chat_id uzytkownika."""
    if not TELEGRAM_BOT_TOKEN:
        return []
    params = {"timeout": 1}
    if offset is not None:
        params["offset"] = offset
    try:
        resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=5)
        data = resp.json()
        return data.get("result", [])
    except Exception:
        return []


def poll_and_register_chat() -> str | None:
    """Czeka na wiadomosc /start i zapisuje chat_id."""
    updates = get_updates()
    for upd in updates:
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id"))
        text = msg.get("text", "")
        if chat_id and text.startswith("/start"):
            database.set_setting("telegram_chat_id", chat_id)
            send_message(
                "🎉 *Witaj w Vinted Manager!*\n\n"
                "Jestem Twoim asystentem sprzedazy.\n\n"
                "📅 Codziennie o *6:00* wysle Ci liste akcji.\n"
                "💰 Codziennie o *22:00* wysle Ci podsumowanie sprzedazy.\n\n"
                "Komendy:\n"
                "/status - sprawdz aktualny stan\n"
                "/sales - podsumowanie dnia\n"
                "/actions - akcje do wykonania",
                chat_id=chat_id,
            )
            return chat_id
    return None


def handle_command(command: str, chat_id: str) -> None:
    """Obsluga prostych komend."""
    cmd = command.strip().lower().split()[0] if command else ""

    if cmd == "/status":
        active = database.get_active_listings()
        month = date.today().month
        year = date.today().year
        sales = database.get_sales_in_month(year, month)
        total = sum((s.get("net_profit") or 0) for s in sales)
        from config import MONTHLY_GOAL_PLN
        text = (
            f"📊 *Status*\n\n"
            f"Aktywne ogloszenia: *{len(active)}*\n"
            f"Sprzedaz w tym miesiacu: *{total:.2f} / {MONTHLY_GOAL_PLN:.0f} zl*\n"
            f"Postep: {total / MONTHLY_GOAL_PLN * 100:.1f}%"
        )
        send_message(text, chat_id=chat_id)

    elif cmd == "/sales":
        send_message(rules.format_sales_summary(), chat_id=chat_id)

    elif cmd == "/actions":
        recs = rules.get_recommendations(only_actionable=True)
        send_message(rules.format_for_telegram(recs), chat_id=chat_id)

    elif cmd == "/start":
        database.set_setting("telegram_chat_id", chat_id)
        send_message(
            "🎉 Witaj! Zapisalem Twoje chat ID. Beda przychodzic raporty o 6:00 i 22:00.",
            chat_id=chat_id,
        )


def listen_for_commands_loop() -> None:
    """Dlugi loop do nasluchiwania komend - moze byc uruchomiony w osobnym watku."""
    last_update_id: int | None = None
    while True:
        try:
            offset = (last_update_id + 1) if last_update_id is not None else None
            updates = get_updates(offset=offset)
            for upd in updates:
                last_update_id = upd["update_id"]
                msg = upd.get("message") or {}
                chat = msg.get("chat") or {}
                chat_id = str(chat.get("id"))
                text = msg.get("text", "")
                if chat_id and text.startswith("/"):
                    handle_command(text, chat_id)
        except Exception as exc:
            print(f"[Telegram] Loop error: {exc}")
        import time
        time.sleep(3)


if __name__ == "__main__":
    print("Test: wysylanie porannego raportu...")
    ok = send_morning_report()
    print("OK" if ok else "Nie udalo sie wyslac.")
