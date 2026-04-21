"""Claude AI - analiza zdjec + generowanie tytulu i opisu."""
import base64
from io import BytesIO
from pathlib import Path
from typing import Union

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, DESCRIPTION_RULES


def _client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Brak klucza ANTHROPIC_API_KEY. Dodaj go do pliku .env w glownym folderze."
        )
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _image_to_b64(image_input: Union[bytes, str, Path, BytesIO]) -> tuple[str, str]:
    """Zwraca (base64, media_type)."""
    if isinstance(image_input, bytes):
        data = image_input
    elif isinstance(image_input, BytesIO):
        data = image_input.getvalue()
    else:
        with open(image_input, "rb") as f:
            data = f.read()

    media_type = "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        media_type = "image/png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        media_type = "image/webp"

    return base64.standard_b64encode(data).decode("utf-8"), media_type


PHOTO_ADVICE_PROMPT = """Jestes ekspertem od sprzedazy na Vinted. Ocen to zdjecie przedmiotu i powiedz sprzedawcy konkretnie:

1. **Co jest dobre** na tym zdjeciu (2-3 punkty)
2. **Co mozna poprawic** (3-5 konkretnych wskazowek, np. oswietlenie, tlo, kadrowanie, pokazanie detali)
3. **Dodatkowe zdjecia ktore warto zrobic** (np. metka, defekty, zblizenie na material)
4. **Jak wyeksponowac zalety przedmiotu** zeby przyciagnac uwage kupujacego

Pisz zwiezle, konkretnie, po polsku. Uzywaj punktow. Maksymalnie 250 slow."""


DESCRIPTION_PROMPT_TEMPLATE = """Jestes ekspertem od pisania ogloszen na Vinted. Na podstawie zdjecia i danych przedmiotu wygeneruj:

**DANE PRZEDMIOTU:**
- Marka: {brand}
- Kategoria: {category}
- Rozmiar: {size}
- Kolor: {color}
- Stan: {condition}
- Dodatkowe informacje: {notes}

**ZASADY (OBOWIAZKOWE):**
{rules}

**WYGENERUJ DOKLADNIE W TYM FORMACIE:**

TYTUL:
<tytul po angielsku, max 50 znakow, bez emotek, z marka i modelem>

HASHTAGI:
<5-10 hashtagow po angielsku, oddzielone spacjami, kazdy z #>

OPIS:
<opis po polsku, maksymalnie 5 krotkich linii, z wymiarami, bez sciany tekstu>

SUGEROWANA CENA:
<cena w PLN na podstawie wartosci rynkowej tego typu przedmiotu, tylko liczba>

UWAGA: Zwracaj DOKLADNIE ten format, nic wiecej."""


def analyze_photo(image: Union[bytes, str, Path]) -> str:
    """Zwroc tekstowa porade fotograficzna dla ogloszenia na Vinted."""
    b64, media_type = _image_to_b64(image)
    client = _client()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": PHOTO_ADVICE_PROMPT},
                ],
            }
        ],
    )
    return response.content[0].text


def generate_listing_content(
    image: Union[bytes, str, Path],
    brand: str = "",
    category: str = "",
    size: str = "",
    color: str = "",
    condition: str = "bardzo dobry",
    notes: str = "",
) -> dict:
    """Wygeneruj tytul, hashtagi, opis i sugerowana cene."""
    b64, media_type = _image_to_b64(image)
    client = _client()

    prompt = DESCRIPTION_PROMPT_TEMPLATE.format(
        brand=brand or "nieznana",
        category=category or "nieznana",
        size=size or "nieznany",
        color=color or "nieznany",
        condition=condition,
        notes=notes or "brak",
        rules=DESCRIPTION_RULES,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    raw = response.content[0].text
    return _parse_listing_response(raw)


def _parse_listing_response(text: str) -> dict:
    result = {"title": "", "hashtags": "", "description": "", "suggested_price": None, "raw": text}
    current_section = None
    buffer: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("TYTUL:") or upper.startswith("TYTUŁ:"):
            if current_section and buffer:
                result[current_section] = "\n".join(buffer).strip()
                buffer = []
            current_section = "title"
            rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if rest:
                buffer.append(rest)
        elif upper.startswith("HASHTAGI:"):
            if current_section and buffer:
                result[current_section] = "\n".join(buffer).strip()
                buffer = []
            current_section = "hashtags"
            rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if rest:
                buffer.append(rest)
        elif upper.startswith("OPIS:"):
            if current_section and buffer:
                result[current_section] = "\n".join(buffer).strip()
                buffer = []
            current_section = "description"
            rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if rest:
                buffer.append(rest)
        elif upper.startswith("SUGEROWANA CENA:") or upper.startswith("CENA:"):
            if current_section and buffer:
                result[current_section] = "\n".join(buffer).strip()
                buffer = []
            current_section = "suggested_price"
            rest = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if rest:
                buffer.append(rest)
        else:
            if current_section:
                buffer.append(line)

    if current_section and buffer:
        if current_section == "suggested_price":
            raw_price = "\n".join(buffer).strip()
            digits = "".join(c for c in raw_price if c.isdigit() or c in ".,")
            digits = digits.replace(",", ".")
            try:
                result["suggested_price"] = float(digits)
            except ValueError:
                result["suggested_price"] = None
        else:
            result[current_section] = "\n".join(buffer).strip()

    return result


def analyze_listing_performance(listing: dict) -> str:
    """AI ocenia dlaczego ogloszenie sie nie sprzedaje i co zmienic."""
    client = _client()
    prompt = f"""Przeanalizuj to ogloszenie na Vinted i powiedz co moze byc przyczyna slabej sprzedazy.
Daj 3-5 konkretnych sugestii co zmienic.

Tytul: {listing.get('title')}
Marka: {listing.get('brand')}
Kategoria: {listing.get('category')}
Cena: {listing.get('list_price')} PLN
Dni na rynku: {listing.get('days_on_market', '?')}
Wyswietlenia: {listing.get('current_views', 0)}
Polubienia: {listing.get('current_likes', 0)}

Pisz zwiezle, po polsku, maksymalnie 200 slow."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
