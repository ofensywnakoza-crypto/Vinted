# 🛍️ Vinted Manager

Aplikacja dla sprzedawcow na Vinted: automatyczna analiza ogloszen, bot Telegram,
rekomendacje AI, trendy rynkowe, strefa fotografii.

---

## 📋 Wymagania

- **Windows** (albo Mac/Linux — wszystko dziala, tylko bez plikow `.bat`)
- **Python 3.11+** (najlepiej 3.12)
- Przegladarka **Brave** (lub Chrome — rozszerzenie dziala na obu)
- Klucz **Anthropic API** (Claude) — masz
- Token **Telegram Bot** — masz

---

## 🚀 Instalacja - krok po kroku

### 1. Wpisz klucze API

Utworz w glownym folderze plik `.env` (skopiuj `.env.example` i zmien nazwe).

Otworz go w Notatniku i wklej swoje klucze:

```
ANTHROPIC_API_KEY=sk-ant-twoj-klucz
TELEGRAM_BOT_TOKEN=123456:twoj-token-od-BotFather
TELEGRAM_CHAT_ID=
```

`TELEGRAM_CHAT_ID` zostaw puste — aplikacja sama go wykryje.

### 2. Zainstaluj biblioteki

Kliknij dwa razy **`install.bat`** — poczekaj 2-3 minuty.

Jesli wolisz recznie, otworz CMD w folderze i wpisz:
```
pip install -r requirements.txt
```

### 3. Uruchom aplikacje

Kliknij dwa razy **`start_all.bat`** — otworza sie 3 okna:
- **Sync Server** — odbiera dane z rozszerzenia (port 8765)
- **Scheduler** — wysyla raporty Telegram o 6:00 i 22:00
- **Streamlit App** — glowny panel (otworzy sie w przegladarce)

Aplikacja bedzie dostepna pod: **http://localhost:8501**

### 4. Zainstaluj rozszerzenie Brave

1. Otworz Brave'a
2. Wejdz na: `brave://extensions/`
3. Wlacz **"Tryb programisty"** (prawy gorny rog)
4. Kliknij **"Zaluduj rozpakowane"**
5. Wybierz folder `extension/` z tej aplikacji
6. Gotowe — rozszerzenie jest aktywne

### 5. Polacz bota Telegram

1. Otworz swojego bota w Telegramie
2. Wyslij do niego wiadomosc **`/start`**
3. W aplikacji przejdz do **Ustawienia → Telegram → "Sprawdz nowe wiadomosci"**
4. Chat ID zostanie zapisany automatycznie

### 6. Zaimportuj dane z Excela

1. W aplikacji przejdz do **Moje ogloszenia → Import**
2. Wybierz swoj plik `.xlsx`
3. Kliknij **Zaimportuj**

---

## 📖 Jak uzywac

### Codzienna rutyna:

**Rano (automatycznie):**
- O 6:00 dostajesz Telegramem liste akcji (co obnizyc, co odswiezyc, co wywalic)

**W ciagu dnia:**
- Otwierasz Vinted w Brave — rozszerzenie automatycznie pobiera swieze dane
- Zostaw Vinted otwarte w tle — dane odswiezaja sie na biezaco

**Wieczorem (automatycznie):**
- O 22:00 dostajesz Telegramem podsumowanie sprzedazy dnia i miesiaca

### Gdy wystawiasz nowe ogloszenie:

1. Wejdz w **Strefa fotografii → Wygeneruj tytul i opis**
2. Wgraj zdjecie
3. Wpisz marke, kategorie, rozmiar
4. Claude AI wygeneruje Ci tytul (EN), hashtagi (EN), opis (PL) i sugerowana cene

### Szukanie okazji do odsprzedazy:

1. Wejdz w **Okazje do kupienia**
2. Kliknij **"Szukaj okazji"**
3. Aplikacja przeskanuje OLX i Vinted dla wybranych marek
4. Pokaze przedmioty wystawione ponizej sredniej ceny — mozesz kupic i odsprzedac drozej

### Analiza trendow:

- **Trendy rynkowe** — wykres co jest teraz na topie (Google Trends)
- Mozesz sprawdzic konkretne slowa kluczowe

---

## 📱 Komendy bota Telegram

- `/start` — inicjalizacja (pierwsza wiadomosc)
- `/status` — aktualny stan (ile ogloszen, ile sprzedane w miesiacu)
- `/sales` — podsumowanie dnia
- `/actions` — lista akcji do wykonania

---

## 🗂️ Struktura projektu

```
Vinted/
├── app.py                 # Aplikacja Streamlit (glowny panel)
├── sync_server.py         # Lokalny serwer HTTP (odbiera dane z rozszerzenia)
├── scheduler_runner.py    # Scheduler - wysyla raporty 6:00 i 22:00
├── config.py              # Klucze API, progi, kolory
├── .env                   # Twoje klucze (nie wrzucaj do git!)
├── install.bat            # Instalacja bibliotek (Windows)
├── start_all.bat          # Uruchomienie wszystkiego (Windows)
├── core/                  # Logika biznesowa
│   ├── database.py        # SQLite
│   ├── excel_import.py    # Import pliku Excel
│   ├── rules.py           # Silnik rekomendacji
│   ├── ai_assistant.py    # Claude AI
│   ├── trends.py          # Google Trends + OLX
│   └── telegram_bot.py    # Bot Telegram
├── ui/                    # Ekrany aplikacji Streamlit
│   ├── dashboard.py
│   ├── listings.py
│   ├── actions.py
│   ├── photos.py
│   ├── trends_page.py
│   ├── deals.py
│   └── settings.py
├── extension/             # Rozszerzenie Brave
│   ├── manifest.json
│   ├── content.js
│   ├── background.js
│   ├── popup.html
│   └── popup.js
└── data/
    └── vinted.db          # Baza danych SQLite
```

---

## ❓ Problemy?

**"Nie mozna polaczyc z aplikacja"** w rozszerzeniu:
- Sprawdz czy okno `Vinted Sync Server` jest otwarte
- Port 8765 moze byc zajety — zmien w `config.py`

**Bot Telegram nie wysyla:**
- Sprawdz w Ustawieniach czy jest zapisany Chat ID
- Wyslij `/start` do bota i kliknij "Sprawdz nowe wiadomosci"

**Google Trends zwraca bledy:**
- Google blokuje zbyt czeste zapytania — poczekaj 30 minut
- Dane sa cache'owane na 12h — nie odswiezaj zbyt czesto

**Rozszerzenie nie synchronizuje:**
- Otworz konsole (F12 w Brave) i sprawdz komunikaty `[Vinted Manager]`
- Upewnij sie ze jestes zalogowany na Vinted

---

## 📊 Reguly rekomendacji

| Warunek | Akcja |
|---|---|
| 7+ dni, 0 wyswietlen, 0 polubien | **Usun i wystaw od nowa** |
| 7+ dni, sa wyswietlenia, 0 polubien | **Obniz cene o 10%** |
| 7+ dni, 0 wyswietlen | **Odswiez ogloszenie** |
| 14+ dni, duze zainteresowanie, brak sprzedazy | **Obniz cene o 7%** |
| 3 dni, 5+ polubien | **Mozesz podniesc cene** |
| Inne z umiarkowanym zainteresowaniem | **Promuj (Vinted Push)** |

Zmien progi w pliku `config.py`.

---

## 💰 Koszty

- Claude API: ~0.01-0.03 PLN za porade fotograficzna
- Miesieczny koszt przy 30-50 analiz: ~15-25 PLN
- Google Trends: **bezplatne**
- OLX / Vinted search: **bezplatne**
- Telegram Bot: **bezplatne**

---

## ⚖️ Uwagi prawne

- Aplikacja do **osobistego uzytku** — czytasz wlasne dane z wlasnego konta
- Nie omija zabezpieczen Vinted — dziala w ramach normalnej przegladarki
- Limit 3 499 PLN/mies. to prog zwolnienia z podatku PL (aktualny na 2025)
- Przy przekroczeniu limitu — obowiazek rozliczenia PIT

---

Powodzenia! 🚀
