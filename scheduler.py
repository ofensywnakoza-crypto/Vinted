"""
Vinted Tracker — background scheduler
Uruchom: python scheduler.py
Zatrzymaj: Ctrl+C
"""
import time
import json
import os
import sys
from datetime import datetime

from vinted_client import VintedClient
from analyzer import parse_items, add_recommendations, calc_stats
from email_sender import send_email
from telegram_bot import send_alert as send_telegram
from goal_tracker import get_monthly_summary

CONFIG_PATH = os.path.join(os.path.dirname(__file__), ".vinted_config.json")


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH) as f:
        return json.load(f)


def check_config(cfg: dict) -> list[str]:
    errors = []
    if not cfg.get("cookie"):
        errors.append("Brak ciasteczka sesji Vinted — skonfiguruj w: streamlit run app.py")
    has_email    = cfg.get("email_to") and cfg.get("email_from") and cfg.get("email_password")
    has_telegram = cfg.get("telegram_token") and cfg.get("telegram_chat_id")
    if not has_email and not has_telegram:
        errors.append("Skonfiguruj przynajmniej jeden kanał powiadomień: email lub Telegram")
    return errors


def run_once(cfg: dict) -> bool:
    """Fetch data, analyse, send email. Returns True on success."""
    client = VintedClient()
    client.set_cookie(cfg["cookie"])

    log("Łączę się z Vinted...")
    user = client.get_current_user()
    if user is None:
        log("BŁĄD: Nie udało się zalogować. Ciasteczko mogło wygasnąć.")
        log("Rozwiązanie: otwórz 'streamlit run app.py' i zaktualizuj ciasteczko.")
        return False

    login = user.get("login", "?")
    log(f"Zalogowano jako: {login} (ID: {user['id']})")

    log("Pobieram ogłoszenia...")
    raw = client.get_all_user_items(user["id"])
    items = parse_items(raw)
    items = add_recommendations(items)
    stats = calc_stats(items)

    urgent = stats.get("wymagaja_uwagi", 0)
    total  = stats.get("lacznie_ogloszen", 0)
    log(f"Pobrano {total} ogłoszeń, {urgent} wymaga uwagi.")

    monthly    = get_monthly_summary()
    only_urgent = cfg.get("email_only_if_urgent", True)
    skip_quiet  = only_urgent and urgent == 0

    success = True

    # --- Email ---
    if cfg.get("email_to") and cfg.get("email_from") and cfg.get("email_password"):
        if skip_quiet:
            log("Wszystko w porządku — email pominięty (brak pilnych ogłoszeń).")
        else:
            log(f"Wysyłam email na {cfg['email_to']}...")
            try:
                send_email(cfg, items, stats, login)
                log("Email wysłany pomyślnie.")
            except Exception as e:
                log(f"BŁĄD email: {e}")
                success = False

    # --- Telegram ---
    if cfg.get("telegram_token") and cfg.get("telegram_chat_id"):
        if skip_quiet:
            log("Telegram — pominięty (brak pilnych ogłoszeń).")
        else:
            log("Wysyłam alert Telegram...")
            ok = send_telegram(cfg, items, stats, login, monthly)
            if ok:
                log("Telegram wysłany pomyślnie.")
            else:
                log("BŁĄD Telegram — sprawdź token i Chat ID.")
                success = False

    return success


def main() -> None:
    print("=" * 60)
    print("  Vinted Tracker — Scheduler")
    print("  Zatrzymaj: Ctrl+C")
    print("=" * 60)

    cfg = load_config()
    errors = check_config(cfg)
    if errors:
        print("\nBrak konfiguracji. Uruchom najpierw:\n")
        print("  streamlit run app.py\n")
        print("i skonfiguruj Vinted + email w panelu bocznym.\n")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    interval_h = float(cfg.get("email_interval_hours", 12))
    log(f"Scheduler uruchomiony. Raporty będą wysyłane co {interval_h:.0f}h.")
    log(f"Odbiorca: {cfg['email_to']}")
    log(f"Tylko gdy są pilne ogłoszenia: {cfg.get('email_only_if_urgent', True)}")
    print()

    consecutive_errors = 0

    while True:
        try:
            cfg = load_config()  # reload in case user updated config

            success = run_once(cfg)
            consecutive_errors = 0 if success else consecutive_errors + 1

            if consecutive_errors >= 3:
                log("3 błędy z rzędu — sprawdź konfigurację i uruchom ponownie.")
                sys.exit(1)

            next_run = datetime.now().strftime("%H:%M")
            wait_seconds = interval_h * 3600
            log(f"Następny raport za {interval_h:.0f}h. Wciśnij Ctrl+C żeby zatrzymać.\n")
            time.sleep(wait_seconds)

        except KeyboardInterrupt:
            print()
            log("Scheduler zatrzymany przez użytkownika.")
            sys.exit(0)
        except Exception as e:
            log(f"Nieoczekiwany błąd: {e}")
            consecutive_errors += 1
            log("Ponawiam za 5 minut...")
            time.sleep(300)


if __name__ == "__main__":
    main()
