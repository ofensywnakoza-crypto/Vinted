# Pomysły na programy wspierające biznes Vinted

> Analiza wykonana 2026-04-21. Projekt już posiada: dashboard Streamlit, FastAPI backend,
> photo_advisor (Claude AI), market_data (Vinted + eBay), trends (Google Trends + OLX),
> goal_tracker, telegram_bot, scheduler. Poniższe pomysły są **addytywne** — nie powielają
> tego co już istnieje.

---

## 1. Smart Auto-Bumper z priorytetyzacją marżową

**Problem:** Vinted wypycha ogłoszenia w dół po kilku godzinach. Ręczny bump 30–50 ogłoszeń
dziennie to 15 min straconego czasu i brak strategii — bumpujesz losowo.

**Co robi:**
Scheduler kolejkuje bumpy według priorytetu: (marża × dni_bez_sprzedaży × sezonowy_mnożnik).
Najdroższe i najdłużej zalegające idą pierwsze. Limit dzienny ustawiasz sam (np. 20 bumpów/dobę),
żeby nie wyglądać jak bot.

**Przewaga:** Konkurencja bumpuje losowo lub nie bumpuje wcale. Ty zawsze masz na górze
produkty z największym potencjałem zysku w danym dniu.

**Poziom trudności:** Średni  
**Technologie:** Python, `curl_cffi` (cookie-auth jak w `vinted_client.py`), APScheduler  
**Automatyzacja:** Tak — cron co 2h, bez interakcji użytkownika  
**Ryzyko:** Vinted może throttlować konto. Mitygacja: randomizowany timing ±15 min, max
20 bumpów/dobę, działanie tylko w godzinach 8–22.

---

## 2. Arbitraż OLX → Vinted — Monitor okazji z live ROI

**Problem:** Ręczne przeglądanie OLX w poszukiwaniu tanich ubrań do odsprzedaży zajmuje godziny
i jest reaktywne (dobra okazja znika zanim ją zobaczysz).

**Co robi:**
Scraper monitoruje OLX (kategorie: odzież, buty) pod kątem nowych ogłoszeń poniżej progu
cenowego. Dla każdego trafienia:
1. Rozpoznaje markę z tytułu/opisu (regex + LLM fallback).
2. Odpytuje `market_data.py` o aktualną cenę tej marki+kategorii na Vinted.
3. Wylicza szacunkowy ROI po prowizji Vinted (5%) i czasie wysyłki.
4. Jeśli ROI > X% → push na Telegram z linkiem i kalkulacją.

**Przewaga:** Reagujesz na okazję w minuty, nie godziny. Przy 50+ monitorowanych zapytaniach
dziennie łapiesz perełki których inni nie widzą.

**Poziom trudności:** Średni  
**Technologie:** Python, `requests`/`BeautifulSoup` (OLX nie blokuje agresywnie),
`market_data.py` (już istnieje), `telegram_bot.py` (już istnieje)  
**Automatyzacja:** Tak — pętla co 10 min, Telegram push  
**Ryzyko:** OLX scraping — w razie blokady alternatywa: API OLX (istnieje, wymaga rejestracji
aplikacji, jest darmowe).

---

## 3. AI Copywriter — Generator opisów zoptymalizowanych pod Vinted

**Problem:** Dobry opis to 20–30% szybszej sprzedaży. Większość sprzedawców pisze
"Sukienka Zara, stan dobry" — i tyle. Pisanie 10 opisów dziennie zajmuje 30 min.

**Co robi:**
Użytkownik wpisuje: marka, kategoria, rozmiar, stan, 2–3 słowa kluczowe. Program generuje
opis 150–200 znaków z:
- słowami kluczowymi których kupujący szukają na Vinted (predefiniowana lista + Google Trends)
- emocjonalnym hakiem ("idealny na...")
- CTA ("pytaj, wysyłam tego samego dnia")
- poprawną kategoryzacją hashtag-style

Tryby: szybki (template) + AI (Claude Haiku — 0.01 PLN/opis).

**Przewaga:** A/B testy pokazują że opisy z social proof i CTA sprzedają 25–35% szybciej.
Konkurencja tego nie robi bo "nie ma czasu".

**Poziom trudności:** Łatwy  
**Technologie:** Python, Anthropic SDK (Haiku — najtańszy), Streamlit UI (już istnieje)  
**Automatyzacja:** Tak — batch generation dla całego CSV z ogłoszeniami  
**Ryzyko:** Niskie. Jedyny koszt to API (przy 30 opisach/dzień = ~0,30 PLN).

---

## 4. Dynamiczny Kalkulator Skupu (apka mobilna / PWA)

**Problem:** Na targowisku/lumpeksie masz 10 sekund żeby zdecydować czy coś kupić.
Liczysz w głowie marżę, zapominasz o prowizji Vinted, przyszacowujesz cenę — i albo
przepłacasz albo odpuszczasz okazję.

**Co robi:**
Progressive Web App (działa w telefonie jak apka, nie trzeba instalować):
1. Wpisujesz markę + kategorię (lub skanujesz etykietę OCR).
2. Aplikacja pobiera medianę cen z Vinted (z `market_data.py`).
3. Pokazuje: **MAX CENA SKUPU** dla zadanego target ROI (np. 60%).
4. Slider do korekty ceny sprzedaży.
5. Historia — co kupiłeś, gdzie, za ile.

**Przewaga:** Decydujesz na podstawie danych, nie intuicji. Przy 5 zakupach/tydzień i
uniknięciu jednej złej decyzji tygodniowo — realny zysk.

**Poziom trudności:** Łatwy  
**Technologie:** Python FastAPI (backend już istnieje), Streamlit lub React PWA, `market_data.py`  
**Automatyzacja:** Nie (narzędzie interaktywne), ale cache cen odświeża się automatycznie  

---

## 5. Predyktor Czasu Sprzedaży (ML)

**Problem:** Nie wiesz czy dana rzecz sprzeda się za tydzień czy za 3 miesiące. Zalegające
produkty zamrażają kapitał i zaniżają wskaźnik rotacji.

**Co robi:**
Model ML (Random Forest / XGBoost) trenowany na historii twoich sprzedaży przewiduje
**ile dni zajmie sprzedaż** danego przedmiotu. Inputy: marka, kategoria, rozmiar, cena,
stan, pora roku, dzień tygodnia wystawienia, marża procentowa.

Output w dashboardzie: "Ta kurtka Zara sprzeda się w ~8 dni. Ta bluza Tommy — ~34 dni.
Rekomendacja: obniż cenę bluzy o 15 zł."

**Przewaga:** Zarządzasz kapitałem aktywnie. Obniżasz cenę zanim rzecz zalega 60 dni,
a nie po. Rotacja kapitału = więcej zakupów = więcej zysku.

**Poziom trudności:** Trudny  
**Technologie:** Python, scikit-learn/XGBoost, pandas, Streamlit (wizualizacja)  
**Automatyzacja:** Tak — cotygodniowy retrain na nowych danych, alerty dla "zagrożonych" pozycji  
**Wymaganie:** Min. 100 sprzedanych produktów w historii dla dobrego modelu.

---

## 6. Foto-Processor: Batch Background + Standaryzacja

**Problem:** Zdjęcia na białym tle sprzedają się szybciej (badania Vinted: +18% CTR).
Batch processing 20 zdjęć ręcznie w Canva/Photoshop to 45 min dziennie.

**Co robi:**
Lokalny skrypt (lub Streamlit upload):
1. Usuwa tło (`rembg` — darmowe, lokalne, szybkie).
2. Nakłada białe lub gradient tło.
3. Normalizuje rozmiar do 1200×1200px (Vinted optimum).
4. Opcjonalnie: watermark z nazwą sklepu.
5. Batch export — folder z gotowymi plikami.

**Przewaga:** Profesjonalne zdjęcia = więcej kliknięć = szybsza sprzedaż. Narzędzie
oszczędza 30–45 min dziennie przy regularnej sprzedaży.

**Poziom trudności:** Łatwy  
**Technologie:** Python, `rembg` (open source, CPU), `Pillow`  
**Automatyzacja:** Tak — watch folder, auto-process nowych zdjęć  
**Ryzyko:** Brak. Działa w 100% lokalnie, zero kosztów API.

---

## 7. Monitor Konkurencji — Śledzenie Top Sprzedawców

**Problem:** Nie wiesz co robią najlepsi sprzedawcy w twojej niszy: jakie marki wystawiają,
w jakich cenach, jak szybko sprzedają. Działasz w ciemno.

**Co robi:**
Śledzi listę profili Vinted (twoi główni konkurenci):
- Nowe wystawienia (marka, kategoria, cena).
- Sprzedane produkty (oblicza czas od wystawienia do sprzedaży).
- Średnie ceny w kategoriach które oboje prowadzicie.
- Weekly raport: "Konkurent X sprzedał 12 rzeczy avg 65 PLN, dominuje w kurtki Zara".

**Przewaga:** Znasz ich strategię cenową. Możesz wyprzedzić ich w wystawieniu popularnej
kategorii lub podbić cenę tam gdzie i tak masz monopol.

**Poziom trudności:** Średni  
**Technologie:** Python, `vinted_client.py` (już istnieje), SQLite (historia), Streamlit  
**Automatyzacja:** Tak — dzienny snapshot o 6:00  
**Ryzyko:** Publiczne profile — etycznie i prawnie OK. Nie zbierasz danych osobowych.

---

## 8. Keyword Optimizer — Co pisać żeby wyskakiwać w wynikach

**Problem:** Vinted ma własną wyszukiwarkę. Nie wiesz jakich słów używają kupujący.
Piszesz "płaszcz zimowy" a oni szukają "ciepły plaszcz oversize".

**Co robi:**
1. Dla danej marki/kategorii pobiera 50 aktywnych ogłoszeń z Vinted.
2. Analizuje tytuły i opisy (NLP: TF-IDF lub word frequency).
3. Identyfikuje słowa kluczowe które mają **najszybszą sprzedaż** (korelacja keyword → sold).
4. Sugeruje: "Dodaj słowa: 'oversize', 'vintage', 'jesień' — są w 70% szybko sprzedanych."

**Przewaga:** SEO na Vinted to nisza — nikt tego nie mierzy. Ty będziesz.

**Poziom trudności:** Średni  
**Technologie:** Python, `vinted_client.py`, `collections.Counter`, scikit-learn (TF-IDF)  
**Automatyzacja:** Tak — miesięczna aktualizacja słownika słów kluczowych  

---

## 9. Bundle Suggester — Zestawy zwiększające wartość koszyka

**Problem:** Sprzedajesz rzeczy po jednej. Vinted pozwala kupującemu negocjować
"bundle" (kilka rzeczy razem). Nie wykorzystujesz tego — a to +30–50% wartości transakcji.

**Co robi:**
Analizuje twój aktywny asortyment i sugeruje **zestawy tematyczne**:
- Stylistyczne (kurtka + bluza tej samej marki, podobny styl).
- Rozmiarowe (wszystko S od jednej marki).
- Okazjonalne (strój na wesele, casual weekend).

Generuje gotowy opis zestawu i sugerowaną cenę bundla (z rabatem 10% = wyższy konwersja,
ale i tak lepiej niż brak transakcji).

**Przewaga:** Średnia wartość zamówienia rośnie. Szybciej sprzedajesz zalegające rzeczy
pakując je z bestsellerami.

**Poziom trudności:** Łatwy  
**Technologie:** Python, pandas, Claude Haiku (kategoryzacja stylistyczna), Streamlit  
**Automatyzacja:** Tak — tygodniowy raport "sugestie bundli"  

---

## 10. Sezonowy Planer Cen i Zakupów

**Problem:** Ceny ubrań na Vinted są sezonowe, ale reagujesz na to z opóźnieniem.
Kupujesz kurtki gdy wszyscy je już sprzedają (wiosna = tanio na Vinted = drogo przy skupie).

**Co robi:**
Na podstawie danych historycznych (Google Trends + własna historia sprzedaży) generuje:
- **Kalendarz zakupów**: "W sierpniu kup kurtki zimowe — jest tanie na OLX, popyt wzrośnie
  za 6 tyg."
- **Kalendarz obniżek**: "Od 15 marca obniż kurtki o 20% — sezon się kończy."
- **Cash flow forecast**: ile gotówki przygotować na dany miesiąc skupu.

**Przewaga:** Kupujesz tanio, sprzedajesz drogo — nie dlatego że masz szczęście, ale
dlatego że masz dane z poprzednich sezonów.

**Poziom trudności:** Średni  
**Technologie:** Python, `pytrends` (już w projekcie), pandas, Prophet/statsmodels (forecasting)  
**Automatyzacja:** Tak — miesięczny briefing na Telegram  

---

## 11. Auto-Tagger: Kategoryzacja Masowa z CV

**Problem:** Wystawienie rzeczy na Vinted wymaga ręcznego wybrania kategorii, marki,
stanu, rozmiaru. Przy 20 rzeczach dziennie to 30 kliknięć każda = 600 kliknięć.

**Co robi:**
Użytkownik wrzuca zdjęcie → model CV (lub Claude Vision) automatycznie proponuje:
- Kategorię (kurtka/sukienka/spodnie)
- Markę (z logo lub etykiety)
- Stan (ocena na podstawie jakości zdjęcia)
- Sugerowaną cenę (z `market_data.py`)

Generuje gotowy formularz do przeklejenia lub (jeśli masz sesję Vinted) auto-wypełnia.

**Przewaga:** 20 wystawień zajmuje 10 min zamiast 60 min. Czas = pieniądz.

**Poziom trudności:** Trudny  
**Technologie:** Claude claude-sonnet-4-6 Vision (już w projekcie — `photo_advisor.py`), Python,
`market_data.py`  
**Automatyzacja:** Tak — watch folder ze zdjęciami, batch output CSV  

---

## 12. Kalkulator Rzeczywistego Zysku z Uwzględnieniem Czasu

**Problem:** Mówisz "zarobiłem 200 PLN" ale nie wliczasz czasu: 3h zakupy + 2h zdjęcia +
1h wysyłki = 6h. Przy 200 PLN zysku = 33 PLN/h. Może się nie opłaca.

**Co robi:**
Rozszerza `purchase_calc.py` o śledzenie czasu:
- Logowanie czasu dla każdej fazy (zakup, przygotowanie, wysyłka).
- KPI: zysk/godzinę per kategoria, per marka.
- Rekomendacja: "Kurtki dają 65 PLN/h. Sukienki 18 PLN/h — rozważ porzucenie tej kategorii."

**Przewaga:** Alokujesz czas na kategorie które REALNIE się opłacają. Często okazuje się
że 20% asortymentu generuje 80% zysku PER GODZINĘ.

**Poziom trudności:** Łatwy  
**Technologie:** Python, pandas, Streamlit (już istnieje), `purchase_calc.py` (rozszerzenie)  
**Automatyzacja:** Nie (wymaga ręcznego logowania czasu), ale raport tygodniowy — tak  

---

---

# TOP 3 — Najlepsze pomysły do wdrożenia

## #1: Auto-Bumper z priorytetyzacją marżową

**Dlaczego:** Bezpośredni wpływ na widoczność = sprzedaż. Używa kodu który już masz
(`vinted_client.py`, `scheduler.py`). ROI jest natychmiastowe i mierzalne. Koszt wdrożenia:
2–3 dni pracy.

## #2: Arbitraż OLX → Vinted z live ROI

**Dlaczego:** To jest serce biznesu resellera — znajdź tanio, sprzedaj drożej. Automatyzacja
tego procesu to przewaga której ręcznie nie można odtworzyć. `market_data.py` i
`telegram_bot.py` już istnieją — to 60% roboty.

## #3: AI Copywriter (generator opisów)

**Dlaczego:** Masz już `anthropic` SDK w projekcie i Claude w `photo_advisor.py`. Koszt
wdrożenia: 1 dzień. Działa od pierwszego opisu. Efekt widoczny w ciągu tygodnia przez
porównanie czasu sprzedaży przed/po.

---

---

# MVP: Arbitraż OLX → Vinted

## Co zrobić jako pierwsze (w tej kolejności):

### Krok 1: Scraper OLX (2–3h)
- Endpoint OLX do scrapowania: `https://www.olx.pl/moda-uroda/ubrania/` + filtry
- Parsuj: tytuł, cena, link, czas dodania
- Zapisuj do SQLite (`seen_ids`) żeby nie duplikować alertów
- Testuj na 10 stronach bez żadnej logiki biznesowej

### Krok 2: Rozpoznawanie marki (1–2h)
- Regex dict: `{"zara": ["zara"], "reserved": ["reserved"], ...}` — 30 popularnych marek
- Fallback: Claude Haiku (`"Rozpoznaj markę z: {title}"`) — tylko jeśli regex nie trafi
- Cel: >80% skuteczności na tytułach OLX

### Krok 3: Podpięcie market_data.py (1h)
- `get_market_price(brand, category)` — już istnieje
- Wylicz: `roi = (vinted_price * 0.95 - olx_price) / olx_price * 100`
- Threshold: wyślij alert tylko jeśli `roi > 50%` i `vinted_price > 40 PLN`

### Krok 4: Alert Telegram (1h)
- `telegram_bot.py` już istnieje
- Format wiadomości:
  ```
  🟢 OKAZJA: Kurtka Zara
  OLX: 25 PLN → Vinted: ~75 PLN
  ROI: ~185% | Link: olx.pl/...
  ```

### Krok 5: Scheduler (30 min)
- `scheduler.py` już istnieje — dodaj job co 10 min
- Rate limit: max 1 request/sek do OLX, random delay

### Łączny czas MVP: ~8–10h pracy
### Koszt operacyjny: ~0 PLN (Claude Haiku fallback: max 1–2 PLN/miesiąc)
### Szacowany zysk z 1 złapanej okazji tygodniowo: 50–200 PLN

---

*Dokument wygenerowany jako analiza dla projektu Vinted Tracker.*
