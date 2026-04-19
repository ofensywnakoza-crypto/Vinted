# Vinted Sales API

Prosty backend w FastAPI do analizy sprzedaży produktów na Vinted.

## Struktura projektu

```
Vinted/
├── main.py              # Aplikacja FastAPI (wszystkie endpointy)
├── requirements.txt     # Zależności Python
├── data/
│   └── products.csv     # Dane produktów (edytuj lub podmień)
└── README.md
```

## Wymagania

- Python 3.10+

## Uruchomienie

### 1. Utwórz wirtualne środowisko (opcjonalne, ale zalecane)

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 2. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

### 3. Uruchom serwer

```bash
uvicorn main:app --reload
```

Serwer startuje domyślnie pod adresem: http://127.0.0.1:8000

### 4. Interaktywna dokumentacja API

Otwórz w przeglądarce: http://127.0.0.1:8000/docs

---

## Endpointy

### `GET /stats`
Ogólne statystyki sprzedaży.

**Odpowiedź:**
```json
{
  "liczba_produktow_lacznie": 30,
  "liczba_sprzedanych": 23,
  "liczba_niesprzedanych": 7,
  "wskaznik_sprzedazy_procent": 76.67,
  "srednia_marza_procent": 89.45,
  "srednia_marza_sprzedanych_procent": 91.23,
  "laczny_zysk_pln": 1340.00,
  "laczny_przychod_pln": 2560.00,
  "laczny_koszt_zakupu_pln": 1220.00
}
```

---

### `GET /best-brands`
Top 5 marek według łącznego zysku ze sprzedanych produktów.

**Odpowiedź:**
```json
{
  "top_5_marek": [
    {
      "marka": "Zara",
      "laczny_zysk_pln": 268.00,
      "liczba_sprzedanych": 5,
      "laczny_przychod_pln": 413.00,
      "srednia_marza_procent": 93.5
    }
  ]
}
```

---

### `GET /recommendations`
Rekomendacje: najlepsze produkty, marki z najwyższą stopą sprzedaży, analiza przedziałów cenowych.

**Odpowiedź:**
```json
{
  "top_5_produktow_wg_zysku": [...],
  "marki_wg_stopy_sprzedazy": [...],
  "analiza_przedzialow_cenowych": [...],
  "wnioski": {
    "srednia_marza_sprzedanych": "91.23%",
    "srednia_marza_niesprzedanych": "82.10%",
    "rekomendacja": "Skup się na markach o stopie sprzedaży >80%..."
  }
}
```

---

## Format pliku CSV

Plik `data/products.csv` musi zawierać następujące kolumny:

| Kolumna          | Typ    | Opis                                      |
|------------------|--------|-------------------------------------------|
| `nazwa`          | tekst  | Nazwa produktu                            |
| `marka`          | tekst  | Marka produktu                            |
| `cena_zakupu`    | liczba | Cena zakupu w PLN                         |
| `cena_sprzedazy` | liczba | Cena sprzedaży w PLN                      |
| `data_sprzedazy` | data   | Data sprzedaży (YYYY-MM-DD), puste = brak |
| `status`         | tekst  | `sprzedane` lub `niesprzedane`            |

### Przykładowy wiersz CSV:

```
Sukienka letnia w kwiaty,Zara,25.00,55.00,2024-01-05,sprzedane
```
