"""
Photography advisor for Vinted listings.

Two modes:
  basic  — rule-based, free, instant
  ai     — Claude claude-sonnet-4-6, ~0.03 PLN per query, personalized
"""
from typing import Optional
import re

# ------------------------------------------------------------------ #
# Category detection
# ------------------------------------------------------------------ #

_KEYWORDS: dict[str, list[str]] = {
    "kurtka":    ["kurtka", "kurtki", "parka", "anorak", "wiatrówk", "bomberka", "przejściówka", "jacket"],
    "plaszcz":   ["płaszcz", "płaszcza", "trencz", "trench", "coat"],
    "sukienka":  ["sukienka", "sukienki", "dress", "kombinezon"],
    "bluza":     ["bluza", "bluzy", "sweter", "swetr", "kardigan", "hoodie", "rozpinana"],
    "spodnie":   ["spodnie", "jeansy", "dżinsy", "dzinsy", "szorty", "jogger"],
    "spodnica":  ["spódnica", "spódniczka", "mini", "midi", "maxi skirt"],
    "koszula":   ["koszula", "koszule", "bluzka", "top ", "shirt"],
    "tshirt":    ["t-shirt", "tshirt", "koszulk", "polo"],
    "marynarka": ["marynarka", "garnitur", "żakiet", "blazer"],
    "buty":      ["but", "sneaker", "trampki", "szpilki", "sandał", "kozak", "botki", "mokasyn"],
    "torebka":   ["torebka", "torba", "plecak", "saszetka", "portfel"],
    "bielizna":  ["bielizna", "biustonosz", "majtki", "bokserki"],
    "sport":     ["sportow", "legginsy", "dres", "komplet sport"],
}

def detect_category(description: str) -> str:
    desc = description.lower()
    for cat, keywords in _KEYWORDS.items():
        if any(k in desc for k in keywords):
            return cat
    return "odziez"


# ------------------------------------------------------------------ #
# Photography rules per category
# ------------------------------------------------------------------ #

_BASE_AVOID = [
    "Bałagan w tle (łóżko, podłoga z rzeczami)",
    "Zdjęcia z flashem — tworzy brzydkie cienie",
    "Zbyt ciemne lub prześwietlone kadry",
    "Jedno zdjęcie — minimum 5",
    "Zdjęcia z bardzo daleka — szczegóły niewidoczne",
]

RULES: dict[str, dict] = {
    "kurtka": {
        "styl_prezentacji": "Na wieszaku lub na sobie",
        "tlo": "Biała lub szara ściana",
        "swiatlo": "Naturalne, boczne — stań bokiem do okna. Unikaj bezpośredniego słońca",
        "orientacja": "Pionowy (portrait)",
        "min_zdjec": 6,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość z przodu",
             "opis": "Cała kurtka widoczna, wieszak schowany lub neutralny",
             "dlaczego": "Pierwsze zdjęcie decyduje o kliknięciu — musi być idealne"},
            {"nr": 2, "tytul": "Całość z tyłu",
             "opis": "Ten sam kadr co #1, kurtka obrócona",
             "dlaczego": "Kupujący zawsze sprawdzają tył"},
            {"nr": 3, "tytul": "Wnętrze / podszewka",
             "opis": "Otwarta kurtka, podszewka wyraźnie widoczna",
             "dlaczego": "Uszkodzona podszewka to główna obawa kupujących"},
            {"nr": 4, "tytul": "Detale — zamki, guziki, kaptur",
             "opis": "Zbliżenie na elementy — pokaż jakość i stan",
             "dlaczego": "Detale budują zaufanie i uzasadniają cenę"},
            {"nr": 5, "tytul": "Metka z rozmiarem",
             "opis": "Wyraźna metka z rozmiarem i składem materiału",
             "dlaczego": "Kupujący sprawdzają skład, zwłaszcza przy alergiach"},
            {"nr": 6, "tytul": "Ewentualne wady",
             "opis": "Nawet małe przetarcia, piling — pokaż w dobrym świetle",
             "dlaczego": "Transparentność = mniej zwrotów i lepsze opinie"},
        ],
        "pro_tips": [
            "Kurtki puchowe — lekko napompuj przed zdjęciem żeby wyglądały pełniej",
            "Skórzane kurtki — przetrzyj wilgotną ściereczką przed sesją",
            "Pokaż kurtkę zapiętą I rozpiętą — dwie wersje sprzedają się lepiej",
        ],
        "unikaj": _BASE_AVOID + ["Zdjęć na kolorowym kocu lub kanapie"],
    },
    "plaszcz": {
        "styl_prezentacji": "Na wieszaku lub na sobie — płaszcze lepiej wyglądają noszone",
        "tlo": "Biała ściana lub neutralne tło miejskie (outdoor)",
        "swiatlo": "Naturalne, najlepiej na zewnątrz w pochmurny dzień (miękkie światło)",
        "orientacja": "Pionowy (portrait)",
        "min_zdjec": 6,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość z przodu — zapięty",
             "opis": "Płaszcz zapięty, widać fason i długość",
             "dlaczego": "Fason płaszcza to najważniejszy czynnik zakupu"},
            {"nr": 2, "tytul": "Całość z przodu — rozpięty",
             "opis": "Płaszcz otwarty — widać podszewkę i krój",
             "dlaczego": "Kupujący chcą zobaczyć jak leży otwarty"},
            {"nr": 3, "tytul": "Całość z tyłu",
             "opis": "Tył płaszcza, widoczna długość",
             "dlaczego": "Długość to kluczowy parametr przy zakupie"},
            {"nr": 4, "tytul": "Podszewka i wewnętrzne kieszenie",
             "opis": "Wnętrze płaszcza — podszewka, kieszenie",
             "dlaczego": "Stan podszewki = stan płaszcza w oczach kupującego"},
            {"nr": 5, "tytul": "Materiał z bliska",
             "opis": "Zbliżenie na tkaninę — pokaż teksturę",
             "dlaczego": "Skład i jakość materiału to główny powód zakupu płaszcza"},
            {"nr": 6, "tytul": "Metka i ewentualne wady",
             "opis": "Metka z rozmiarem + uczciwe pokazanie śladów użycia",
             "dlaczego": "Transparentność eliminuje spory"},
        ],
        "pro_tips": [
            "Płaszcze wełniane — wyparuj przed sesją (żelazko na odległość)",
            "Zdjęcia na zewnątrz przy pochmurnej pogodzie dają najlepsze efekty dla płaszczy",
            "Pokaż sylwetkę — jak leży na ciele to 50% decyzji zakupowej",
        ],
        "unikaj": _BASE_AVOID + ["Gniecenia — wyprasuj lub wyparuj przed sesją"],
    },
    "sukienka": {
        "styl_prezentacji": "Flat lay (na podłodze/łóżku) LUB na wieszaku LUB na sobie",
        "tlo": "Białe lub jasne tło. Flat lay: biała podłoga lub czyste łóżko",
        "swiatlo": "Naturalne, okno od góry (flat lay) lub boczne (wieszak)",
        "orientacja": "Pionowy (portrait)",
        "min_zdjec": 5,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość — flat lay lub wieszak",
             "opis": "Sukienka rozłożona symetrycznie lub na wieszaku, widać całość",
             "dlaczego": "Kształt i długość sukienki to priorytet"},
            {"nr": 2, "tytul": "Góra sukienki — dekolt, ramiączka",
             "opis": "Zbliżenie na górną część — dekolt, rękawy, zapięcie",
             "dlaczego": "Dekolt i rękawy są kluczowe dla kupujących"},
            {"nr": 3, "tytul": "Dół sukienki — fason, długość",
             "opis": "Widoczny fason spódnicy, wykończenie dołu",
             "dlaczego": "Długość sukienki trudno ocenić z jednego zdjęcia"},
            {"nr": 4, "tytul": "Materiał z bliska + wzór",
             "opis": "Zbliżenie na tkaninę — tekstura, wzór, kolor",
             "dlaczego": "Kolor na ekranie często kłamie — zbliżenie daje pewność"},
            {"nr": 5, "tytul": "Metka + tyłek / zapięcie z tyłu",
             "opis": "Metka z rozmiarem, zamek lub guziki z tyłu",
             "dlaczego": "Kupujący sprawdzają zapięcia i skład"},
        ],
        "pro_tips": [
            "Flat lay wychodzi lepiej gdy sukienka ma wyraźny wzór lub kolor",
            "Sukienki tiulowe / z falbanami — koniecznie na sobie lub manekinie",
            "Dodaj zdjęcie jak wyglądasz w sukience — to najczęściej udostępniane zdjęcie",
        ],
        "unikaj": _BASE_AVOID + ["Gniecenia — wyprasuj PRZED sesją", "Flat lay na kolorowej pościeli"],
    },
    "bluza": {
        "styl_prezentacji": "Na wieszaku lub flat lay",
        "tlo": "Białe lub szare",
        "swiatlo": "Naturalne, przy oknie",
        "orientacja": "Pionowy lub poziomy (flat lay)",
        "min_zdjec": 4,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość z przodu",
             "opis": "Bluza złożona lub na wieszaku — widać napis/logo jeśli jest",
             "dlaczego": "Logo i nadruk to główny powód zakupu bluz"},
            {"nr": 2, "tytul": "Tył i szczegóły",
             "opis": "Tył bluzy, ewentualny nadruk z tyłu",
             "dlaczego": "Bluzy często mają grafikę z tyłu"},
            {"nr": 3, "tytul": "Zbliżenie na materiał i stan",
             "opis": "Czy jest piling? Czy materiał jest miękki? Pokaż to",
             "dlaczego": "Piling to największa obawa przy bluzach używanych"},
            {"nr": 4, "tytul": "Metka i rozmiar",
             "opis": "Wyraźna metka — rozmiar, skład, marka",
             "dlaczego": "Rozmiary bluz bardzo się różnią między markami"},
        ],
        "pro_tips": [
            "Sprawdź czy jest piling (kuleczki na materiale) — jeśli jest, usuń maszynką do pilingu",
            "Bluzy oversize — pokaż na sobie żeby kupujący zrozumiał rozmiar",
            "Jeśli jest sznurek przy kapturze — sprawdź czy jest kompletny",
        ],
        "unikaj": _BASE_AVOID,
    },
    "spodnie": {
        "styl_prezentacji": "Flat lay lub na wieszaku (złożone w pasie)",
        "tlo": "Białe lub jasna podłoga",
        "swiatlo": "Naturalne, od góry (flat lay)",
        "orientacja": "Pionowy",
        "min_zdjec": 5,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość — rozłożone flat lay",
             "opis": "Spodnie rozłożone symetrycznie, widać całą długość",
             "dlaczego": "Krój i długość nóg to priorytet"},
            {"nr": 2, "tytul": "Pas i zapięcie",
             "opis": "Zbliżenie na pas, zamek, guziki, pętelki na pasek",
             "dlaczego": "Kupujący sprawdzają stan zamka i zapięcia"},
            {"nr": 3, "tytul": "Tył — kieszenie, tyłek",
             "opis": "Tył spodni — kieszenie tylne, przeszycia",
             "dlaczego": "Przy jeansach tył jest często ważniejszy niż przód"},
            {"nr": 4, "tytul": "Nogawki — dół i szwy",
             "opis": "Dół nogawek — czy są przetarte? Jaka długość?",
             "dlaczego": "Przetarcia przy dole to częsta ukryta wada"},
            {"nr": 5, "tytul": "Metka z rozmiarem",
             "opis": "Metka z rozmiarem (W/L dla jeansów lub S/M/L)",
             "dlaczego": "Rozmiary spodni to najczęstsze pytania kupujących"},
        ],
        "pro_tips": [
            "Jeansy — podaj wymiary w centymetrach (pas, biodra, długość nogawki) — zwiększa sprzedaż o 40%",
            "Pokaż spodnie złożone od strony kieszeni — kupujący widzą czy są wytarte",
            "Legginsy — koniecznie pokazuj rozciąganie materiału zbliżeniem",
        ],
        "unikaj": _BASE_AVOID + ["Zdjęć zwisających spodni — rozłóż płasko"],
    },
    "buty": {
        "styl_prezentacji": "Na neutralnym tle — para razem lub z boku",
        "tlo": "Biała kartka A3 lub białe płytki. Można outdoor na asfalcie",
        "swiatlo": "Naturalne, bez cienia",
        "orientacja": "Poziomy (landscape) lub pionowy — zależy od modelu",
        "min_zdjec": 6,
        "zdjecia": [
            {"nr": 1, "tytul": "Para z boku",
             "opis": "Oba buty ustawione równolegle, widok z boku",
             "dlaczego": "Profil buta to najbardziej charakterystyczny widok"},
            {"nr": 2, "tytul": "Para z przodu / skos",
             "opis": "Buty lekko pod kątem — widać czubki i cholewkę",
             "dlaczego": "Ten kąt pokazuje kształt i proporcje"},
            {"nr": 3, "tytul": "Podeszwa",
             "opis": "Widok podeszwy — stan zużycia wyraźnie widoczny",
             "dlaczego": "Stan podeszwy = informacja o stopniu używania"},
            {"nr": 4, "tytul": "Wnętrze — wkładka",
             "opis": "Wnętrze buta — wkładka i stan wyściółki",
             "dlaczego": "Zniszczona wkładka to główna obawa przy butach używanych"},
            {"nr": 5, "tytul": "Detal — materiał i szwy",
             "opis": "Zbliżenie na materiał, zamki, sznurówki, szwy",
             "dlaczego": "Jakość wykończenia decyduje o cenie"},
            {"nr": 6, "tytul": "Metka z rozmiarem + wady",
             "opis": "Rozmiar widoczny + uczciwe pokazanie zarysowań/przetarć",
             "dlaczego": "Rozmiar butów to absolutny priorytet kupujących"},
        ],
        "pro_tips": [
            "Wyczyść buty przed sesją — błoto i kurz odejmują 30% wartości wizualnej",
            "Białe podeszwy — wyczyść gumką do butów lub Magic Eraser",
            "Sneakersy — włóż do środka papier żeby trzymały kształt",
            "Obcasy — pokaż stan obcasów z bliska, to częsta ukryta wada",
        ],
        "unikaj": _BASE_AVOID + [
            "Zdjęć na stopach — kupujący chcą zobaczyć but, nie Twoje nogi",
            "Fotografowania pojedynczego buta — zawsze para",
        ],
    },
    "torebka": {
        "styl_prezentacji": "Stojąca na neutralnym tle",
        "tlo": "Białe lub szare. Droższa torebka zasługuje na ciemne tło",
        "swiatlo": "Naturalne, równomierne — unikaj cieni",
        "orientacja": "Pionowy",
        "min_zdjec": 7,
        "zdjecia": [
            {"nr": 1, "tytul": "Cała torebka z przodu",
             "opis": "Stojąca, wypełniona papierem żeby trzymała kształt",
             "dlaczego": "Kształt torebki to priorytet — musi być widoczny"},
            {"nr": 2, "tytul": "Tył torebki",
             "opis": "Tył — kieszonki, logo, okucia",
             "dlaczego": "Tył często ma dodatkowe kieszenie lub logo"},
            {"nr": 3, "tytul": "Wnętrze",
             "opis": "Otwarta torebka — wnętrze, przegródki, podszewka",
             "dlaczego": "Stan wnętrza = główna obawa przy torebkach"},
            {"nr": 4, "tytul": "Dno torebki",
             "opis": "Dno — nóżki, przetarcia, stan",
             "dlaczego": "Dno się najbardziej zużywa — kupujący zawsze sprawdzają"},
            {"nr": 5, "tytul": "Uszy / rączki / pasek",
             "opis": "Stan uchwytów — przeszycia, przetarcia przy łączeniach",
             "dlaczego": "Urwane uszko = dyskwalifikacja w oczach kupującego"},
            {"nr": 6, "tytul": "Zamki i zapięcia",
             "opis": "Zamki błyskawiczne, klamry, magnesy — działają?",
             "dlaczego": "Niedziałający zamek to najczęstsza wada torebek"},
            {"nr": 7, "tytul": "Metka / certyfikat autentyczności (jeśli jest)",
             "opis": "Oryginalna metka, dust bag, certyfikat",
             "dlaczego": "Przy markowych torebkach brak metki = niższa cena"},
        ],
        "pro_tips": [
            "Wypełnij torebkę papierem przed sesją — trzyma kształt i wygląda droziej",
            "Skórzane torebki — nałóż odżywkę do skóry, będą wyglądać jak nowe",
            "Markowe torebki (LV, Gucci, Coach) — zrób zdjęcie wszystkich zabezpieczeń i hologramów",
        ],
        "unikaj": _BASE_AVOID + ["Zdjęć pustej, zwiotczałej torebki — zawsze wypełnij"],
    },
    "marynarka": {
        "styl_prezentacji": "Na wieszaku lub na sobie",
        "tlo": "Białe lub szare — marynarki wymagają czystego tła",
        "swiatlo": "Naturalne, boczne",
        "orientacja": "Pionowy",
        "min_zdjec": 6,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość z przodu — zapięta",
             "opis": "Marynarka zapięta, klapy leżące równo",
             "dlaczego": "Fason marynarki = pierwsza ocena kupującego"},
            {"nr": 2, "tytul": "Całość z przodu — rozpięta",
             "opis": "Marynarka otwarta — widać wnętrze i krój",
             "dlaczego": "Podszewka i wewnętrzne kieszenie to ważne detale"},
            {"nr": 3, "tytul": "Tył",
             "opis": "Tył marynarki — rozcięcia, szwy",
             "dlaczego": "Rozcięcia w marynarce to kwestia fasonu i gustu"},
            {"nr": 4, "tytul": "Guziki i klapy",
             "opis": "Zbliżenie na guziki, klapy — stan i kolor",
             "dlaczego": "Brakujący guzik = minus 30% wartości"},
            {"nr": 5, "tytul": "Rękawy — długość i mankiety",
             "opis": "Długość rękawów, guziki mankietów, podszewka rękawa",
             "dlaczego": "Długość rękawów to najczęstszy powód zwrotu"},
            {"nr": 6, "tytul": "Metka i skład",
             "opis": "Metka z rozmiarem, składem i marką",
             "dlaczego": "Wełna vs poliester = ogromna różnica ceny"},
        ],
        "pro_tips": [
            "Marynarki wełniane — sprawdź czy są mole (charakterystyczne dziurki)",
            "Sprawdź wszystkie guziki — brakujące usuń z cenę",
            "Podaj dokładne wymiary: szerokość barków, długość rękawa",
        ],
        "unikaj": _BASE_AVOID + ["Gniecenia — koniecznie wyparuj przed sesją"],
    },
    "odziez": {
        "styl_prezentacji": "Na wieszaku lub flat lay",
        "tlo": "Białe lub szare",
        "swiatlo": "Naturalne, przy oknie",
        "orientacja": "Pionowy",
        "min_zdjec": 5,
        "zdjecia": [
            {"nr": 1, "tytul": "Całość z przodu", "opis": "Cały produkt widoczny", "dlaczego": "Pierwsze wrażenie"},
            {"nr": 2, "tytul": "Całość z tyłu", "opis": "Tył produktu", "dlaczego": "Kupujący zawsze sprawdzają tył"},
            {"nr": 3, "tytul": "Detale i materiał", "opis": "Zbliżenie na materiał, szwy, detale", "dlaczego": "Jakość materiału"},
            {"nr": 4, "tytul": "Metka z rozmiarem", "opis": "Wyraźna metka", "dlaczego": "Rozmiar i skład"},
            {"nr": 5, "tytul": "Ewentualne wady", "opis": "Uczciwe pokazanie stanu", "dlaczego": "Zaufanie kupującego"},
        ],
        "pro_tips": [
            "Minimum 5 zdjęć zawsze zwiększa szansę sprzedaży",
            "Naturalne światło zawsze lepsze niż lampa",
        ],
        "unikaj": _BASE_AVOID,
    },
}

# Fill missing categories with default
for _cat in ["spodnica", "koszula", "tshirt", "bielizna", "sport"]:
    if _cat not in RULES:
        RULES[_cat] = RULES["odziez"].copy()


# ------------------------------------------------------------------ #
# Basic advisor (free, rule-based)
# ------------------------------------------------------------------ #

def get_basic_advice(
    description: str,
    market_data: Optional[dict] = None,
) -> dict:
    category = detect_category(description)
    rules = RULES.get(category, RULES["odziez"])

    market_context = ""
    price_tip = ""
    if market_data:
        v_med = market_data.get("vinted_median")
        e_med = market_data.get("ebay_median")
        if v_med or e_med:
            prices = [p for p in [v_med, e_med] if p]
            avg = sum(prices) / len(prices)
            market_context = f"Podobne produkty sprzedają się za ok. {avg:.0f} zł."
            if avg > 100:
                price_tip = "Przy cenie powyżej 100 zł warto zainwestować więcej czasu w zdjęcia — zwrot jest wart wysiłku."
            elif avg < 40:
                price_tip = "Przy niskiej cenie skup się na 4–5 dobrych zdjęciach — nie ma sensu robić 10."

    return {
        "kategoria": category,
        "opis_produktu": description,
        "styl_prezentacji": rules["styl_prezentacji"],
        "tlo": rules["tlo"],
        "swiatlo": rules["swiatlo"],
        "orientacja": rules["orientacja"],
        "min_zdjec": rules["min_zdjec"],
        "plan_zdjec": rules["zdjecia"],
        "pro_tips": rules["pro_tips"],
        "unikaj": rules["unikaj"],
        "kontekst_rynkowy": market_context,
        "porada_cenowa": price_tip,
        "tryb": "basic",
    }


# ------------------------------------------------------------------ #
# AI advisor (Claude claude-sonnet-4-6)
# ------------------------------------------------------------------ #

_SYSTEM_PROMPT = """Jesteś ekspertem od fotografii produktowej dla sprzedaży odzieży używanej na Vinted.

Twoje porady są:
- Praktyczne i możliwe do wykonania zwykłym telefonem
- Konkretne (nie ogólnikowe) — podajesz dokładny kadr, kąt, odległość
- Dostosowane do konkretnego produktu i jego specyfiki
- Świadome ceny — im droższy produkt, tym więcej wysiłku warto włożyć

Odpowiadasz po polsku. Używasz prostego języka zrozumiałego dla osoby bez doświadczenia fotograficznego.

Format odpowiedzi (zawsze taki sam):
1. OCENA PRODUKTU — 1-2 zdania co jest najważniejsze przy tym produkcie
2. PLAN ZDJĘĆ — numerowana lista (min. 5 zdjęć) z opisem co i jak sfotografować
3. ŚWIATŁO I TŁO — konkretna rekomendacja
4. WSKAZÓWKI PRZED SESJĄ — co zrobić z produktem zanim zaczniesz fotografować
5. NAJWAŻNIEJSZA WSKAZÓWKA — jedna rzecz która najbardziej zwiększy szansę sprzedaży"""


def get_ai_advice(
    description: str,
    api_key: str,
    market_data: Optional[dict] = None,
) -> dict:
    try:
        import anthropic
    except ImportError:
        return {"error": "Zainstaluj: pip install anthropic", "tryb": "ai_error"}

    market_context = ""
    if market_data:
        v_med = market_data.get("vinted_median")
        e_med = market_data.get("ebay_median")
        if v_med or e_med:
            prices = [p for p in [v_med, e_med] if p]
            avg = sum(prices) / len(prices)
            market_context = f"\n\nDANE RYNKOWE: Podobne produkty sprzedają się za ok. {avg:.0f} zł na Vinted."

    user_message = f"Produkt do sfotografowania: {description}{market_context}\n\nStwórz szczegółowy plan fotograficzny."

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        ai_text = response.content[0].text

        # Estimate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = (input_tokens / 1_000_000 * 3.0) + (output_tokens / 1_000_000 * 15.0)
        cost_pln = round(cost_usd * 4.2, 3)

        return {
            "kategoria": detect_category(description),
            "opis_produktu": description,
            "ai_porada": ai_text,
            "koszt_pln": cost_pln,
            "tryb": "ai",
        }
    except Exception as e:
        return {"error": str(e), "tryb": "ai_error"}
