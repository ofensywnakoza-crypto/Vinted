"""Scheduler - dziala w tle i wysyla raporty o 6:00 i 22:00.

Uruchom: python scheduler_runner.py
Zostaw to okno otwarte - dziala jako uslugowy proces.
"""
import signal
import sys
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import MORNING_REPORT_HOUR, EVENING_REPORT_HOUR
from core import database, telegram_bot


def job_morning():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Wysylanie porannego raportu...")
    ok = telegram_bot.send_morning_report()
    print("  OK" if ok else "  Blad wysylki.")


def job_evening():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Wysylanie wieczornego podsumowania...")
    ok = telegram_bot.send_evening_report()
    print("  OK" if ok else "  Blad wysylki.")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Warsaw")
    scheduler.add_job(
        job_morning,
        CronTrigger(hour=MORNING_REPORT_HOUR, minute=0),
        id="morning_report",
        replace_existing=True,
    )
    scheduler.add_job(
        job_evening,
        CronTrigger(hour=EVENING_REPORT_HOUR, minute=0),
        id="evening_report",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


def main():
    database.init_db()
    print("=" * 50)
    print("  VINTED MANAGER - Scheduler")
    print("=" * 50)
    print(f"Poranny raport: codziennie o {MORNING_REPORT_HOUR:02d}:00")
    print(f"Wieczorny raport: codziennie o {EVENING_REPORT_HOUR:02d}:00")
    print("Czas strefa: Europe/Warsaw")
    print()
    print("Zostaw to okno otwarte. Nacisnij Ctrl+C zeby zakonczyc.")
    print("=" * 50)

    scheduler = start_scheduler()

    import threading
    bot_thread = threading.Thread(
        target=telegram_bot.listen_for_commands_loop,
        daemon=True,
    )
    bot_thread.start()
    print("Bot Telegram nasluchuje komend (/start, /status, /sales, /actions)")
    print()

    def handle_shutdown(signum, frame):
        print("\nZatrzymuje scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
