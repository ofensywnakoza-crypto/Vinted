"""Centralna konfiguracja aplikacji Vinted Manager."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
EXTENSION_DIR = BASE_DIR / "extension"

DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

DB_PATH = DATA_DIR / "vinted.db"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

MORNING_REPORT_HOUR = 6
EVENING_REPORT_HOUR = 22

COOKIE_SERVER_HOST = "127.0.0.1"
COOKIE_SERVER_PORT = 8765

MONTHLY_GOAL_PLN = 3499.0
VINTED_COMMISSION_RATE = 0.05

DAYS_NO_SALE_THRESHOLD = 7
DAYS_NO_VIEWS_THRESHOLD = 7
NO_LIKES_THRESHOLD = 0

VINTED_PRIMARY = "#09B1BA"
VINTED_DARK = "#003438"
VINTED_LIGHT = "#E8FAFB"
VINTED_ACCENT = "#FF6B35"

DESCRIPTION_RULES = """
Zasady pisania tytułu i opisu na Vinted:
- Tytuł: w języku angielskim, bez emotek, max 50 znaków, z marką i modelem
- Hashtagi: w języku angielskim, 5-10 sztuk
- Opis: w języku polskim, max 5 krótkich linii (nie ściana tekstu)
- Wymiary: zawsze w opisie (długość, szerokość, ramiona dla góry; pas, długość, udo dla dołu)
- Cena: sugerowana na podstawie wartości rynkowej
"""
