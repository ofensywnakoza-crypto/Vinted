"""
Photo Pipeline — core logic.

Flow per product:
  raw photo(s)
    → background removal (rembg) + resize/normalize (Pillow)
    → Claude Vision analysis  (brand, category, condition, color…)
    → Vinted price lookup     (text-based market search)
    → Claude listing gen      (title + description + hashtags)
    → output/{slug}/          (processed JPEGs + listing.json + listing_vinted.txt)

Modes:
  batch    — each image = separate product
  single   — all images = one product (first image used for AI analysis)
  grouped  — images grouped by filename prefix: kurtka_1.jpg + kurtka_2.jpg = one product
"""

import base64
import json
import os
import re
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import requests

# ------------------------------------------------------------------ #
# Optional heavy deps — fail gracefully
# ------------------------------------------------------------------ #

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    from rembg import remove as _rembg_remove
    REMBG_OK = True
except ImportError:
    REMBG_OK = False

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
OUTPUT_SIZE = (1200, 1200)


# ================================================================== #
# IMAGE PROCESSING
# ================================================================== #

def _open_rgba(path: str) -> "Image.Image":
    return Image.open(path).convert("RGBA")


def _remove_bg(img: "Image.Image") -> "Image.Image":
    return _rembg_remove(img)


def _fit_on_canvas(
    img: "Image.Image",
    size: tuple = OUTPUT_SIZE,
    bg: tuple = (255, 255, 255),
) -> "Image.Image":
    """Fit image into size×size canvas preserving aspect ratio."""
    canvas = Image.new("RGBA", size, bg + (255,))
    img.thumbnail(size, Image.LANCZOS)
    offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
    canvas.paste(img, offset, img)
    return canvas.convert("RGB")


def process_image(
    input_path: str,
    output_path: str,
    remove_bg: bool = True,
    bg_color: tuple = (255, 255, 255),
) -> bool:
    """
    Process a single image: optional bg removal + resize to 1200×1200.
    Returns True on success.
    """
    if not PIL_OK:
        raise RuntimeError("Pillow nie jest zainstalowane — uruchom: pip install Pillow")
    try:
        img = _open_rgba(input_path)
        if remove_bg and REMBG_OK:
            img = _remove_bg(img)
        result = _fit_on_canvas(img, bg=bg_color)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        result.save(output_path, "JPEG", quality=92, optimize=True)
        return True
    except Exception as e:
        print(f"[pipeline] process_image error ({input_path}): {e}")
        return False


# ================================================================== #
# PRICE LOOKUP — text-based Vinted search
# ================================================================== #

def _fetch_vinted_prices(query: str, per_page: int = 50) -> list[float]:
    try:
        time.sleep(2.0)
        resp = requests.get(
            "https://www.vinted.pl/api/v2/catalog/items",
            params={"search_text": query, "per_page": per_page, "order": "relevance"},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Referer": "https://www.vinted.pl/",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        return [
            float(item["price"]["amount"])
            for item in resp.json().get("items", [])
            if item.get("price", {}).get("amount")
        ]
    except Exception:
        return []


def get_price_estimate(brand: str, category: str) -> dict:
    """Return price suggestion based on live Vinted market data."""
    query = f"{brand} {category}".strip()
    prices = _fetch_vinted_prices(query) if query else []
    if len(prices) < 3:
        return {"suggested_price": None, "vinted_median": None, "vinted_count": len(prices)}
    median = round(statistics.median(prices), 0)
    # Slightly under median to sell faster
    suggested = round(median * 0.93, 0)
    return {"suggested_price": suggested, "vinted_median": median, "vinted_count": len(prices)}


# ================================================================== #
# CLAUDE VISION — image analysis
# ================================================================== #

_ANALYSIS_PROMPT = """\
Przeanalizuj zdjęcie produktu odzieżowego lub akcesoriów przeznaczonego do sprzedaży na Vinted.

Odpowiedz WYŁĄCZNIE czystym JSON-em (bez markdown, bez objaśnień):
{
  "marka": "nazwa marki lub 'nieznana'",
  "kategoria": "kurtka|plaszcz|sukienka|bluza|spodnie|spodnica|koszula|tshirt|marynarka|buty|torebka|sport|odziez",
  "plec": "damskie|meskie|unisex",
  "stan": "nowe z metką|nowe bez metki|bardzo dobry|dobry|akceptowalny",
  "kolor_glowny": "nazwa koloru po polsku",
  "rozmiar_hint": "rozmiar widoczny na metce lub null",
  "widoczne_wady": [],
  "cechy_szczegolne": [],
  "material_hint": "materiał widoczny na metce lub null",
  "pewnosc_marki": "wysoka|srednia|niska"
}\
"""

_MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",  ".webp": "image/webp",
}


def analyze_image(image_path: str, api_key: str) -> dict:
    """Send image to Claude Vision and return structured analysis dict."""
    import anthropic

    ext = Path(image_path).suffix.lower()
    media_type = _MEDIA_TYPES.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": img_b64},
                },
                {"type": "text", "text": _ANALYSIS_PROMPT},
            ],
        }],
    )

    raw = resp.content[0].text.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "marka": "nieznana", "kategoria": "odziez", "plec": "unisex",
            "stan": "dobry", "kolor_glowny": "", "rozmiar_hint": None,
            "widoczne_wady": [], "cechy_szczegolne": [], "material_hint": None,
            "pewnosc_marki": "niska", "_parse_error": raw[:200],
        }


# ================================================================== #
# CLAUDE TEXT — listing generation
# ================================================================== #

_LISTING_PROMPT = """\
Wygeneruj ogłoszenie na Vinted na podstawie analizy produktu i danych rynkowych.

ANALIZA:
{analysis}

DANE RYNKOWE:
{price_data}

=== ZASADY — stosuj BEZWZGLĘDNIE ===

TYTUŁ (po angielsku, max 60 znaków):
Format: [Brand] [Item type] [Key feature/style] [Color] [Size jeśli znany]
- Wyłącznie po angielsku — szerszy zasięg (PL, DE, FR, NL)
- Marka ZAWSZE na początku jeśli rozpoznawalna
- Pakuj słowa kluczowe jak kupujący szuka, nie jak opisujesz
- Dodaj estetykę/styl: vintage, y2k, streetwear, grunge, oversized, slim fit itp.
- Zero emotek, kropek, przecinków — same słowa oddzielone spacją
- Przykład: "Adidas hoodie oversize vintage washed grey M"

OPIS (po polsku, max 5 linii, ZERO ozdobników):
Linia 1: Wymiary: pierś ? cm, długość ? cm, rękaw ? cm  ← wpisz ? jeśli niewidoczne na zdjęciu
Linia 2: Stan: [nowa z metką / bardzo dobry / dobry / akceptowalny]
Linia 3: Skład: [jeśli widoczny na metce, np. "100% bawełna"] ← pomiń jeśli niewidoczny
Linia 4: [JEDEN suchy fakt o kroju/cesze/wadie — BEZ "elegancka", "klasa", "idealna do", "świetna na"]
Linia 5: Skorzystaj z opcji Zestaw — przy zakupie kilku rzeczy z profilu automatyczny rabat 5-15%
Linia 6: Przyjmuję zwroty

HASHTAGI (po angielsku, 15–20 sztuk):
Struktura: #brand #sub-linie #itemtype1 #itemtype2_synonim #style #color #size #aesthetic #trend #gender #fit
- Wyłącznie po angielsku
- Marka + jej sub-linie (#adidas #adidasoriginals #trefoil)
- Typ kilkoma synonimami (#hoodie #sweatshirt #pullover)
- Estetyka i trend (#y2k #vintage #streetwear #gorpcore)
- NIE dawaj hashtagów niezwiązanych z przedmiotem

Odpowiedz WYŁĄCZNIE czystym JSON-em (bez markdown, bez komentarzy):
{
  "tytul": "...",
  "opis": "...",
  "hashtagi": ["#tag1", "#tag2"]
}\
"""


def generate_listing(analysis: dict, price_data: dict, api_key: str) -> dict:
    """Generate Vinted listing text (title, description, hashtags) via Claude."""
    import anthropic

    price_str = (
        f"Mediana Vinted: {price_data.get('vinted_median') or 'brak'} zł | "
        f"Próbka: {price_data.get('vinted_count', 0)} ogłoszeń | "
        f"Sugerowana cena: {price_data.get('suggested_price') or 'brak'} zł"
    )
    prompt = _LISTING_PROMPT.format(
        analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
        price_data=price_str,
    )

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"tytul": "", "opis": "", "hashtagi": [], "_parse_error": raw[:200]}


# ================================================================== #
# OUTPUT SAVING
# ================================================================== #

def _make_slug(analysis: dict, idx: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    brand = re.sub(r"[^\w]", "", analysis.get("marka", "").lower().replace(" ", "_"))[:12]
    cat = analysis.get("kategoria", "produkt")[:10]
    return f"{cat}_{brand}_{idx:03d}_{ts}"


def save_result(
    output_dir: str,
    slug: str,
    processed_images: list[str],
    analysis: dict,
    listing: dict,
    price_data: dict,
) -> str:
    """Write all outputs to output_dir/slug/. Returns the folder path."""
    from shutil import copy2

    folder = os.path.join(output_dir, slug)
    os.makedirs(folder, exist_ok=True)

    for i, img_path in enumerate(processed_images, 1):
        copy2(img_path, os.path.join(folder, f"{i:02d}_processed.jpg"))

    full = {
        "slug": slug,
        "created_at": datetime.now().isoformat(),
        "tytul": listing.get("tytul", ""),
        "opis": listing.get("opis", ""),
        "hashtagi": listing.get("hashtagi", []),
        "sugerowana_cena": price_data.get("suggested_price"),
        "vinted_mediana": price_data.get("vinted_median"),
        "vinted_count": price_data.get("vinted_count", 0),
        "analiza": analysis,
    }
    with open(os.path.join(folder, "listing.json"), "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)

    defects = ", ".join(analysis.get("widoczne_wady") or []) or "brak"
    features = ", ".join(analysis.get("cechy_szczegolne") or []) or "—"
    price_line = (
        f"{price_data.get('suggested_price')} zł"
        if price_data.get("suggested_price") else "— (brak danych rynkowych)"
    )
    hashtags_str = " ".join(listing.get("hashtagi", []))
    opis_z_hasztagami = f"{listing.get('opis', '')}\n\n{hashtags_str}"
    txt = (
        f"TYTUŁ:\n{listing.get('tytul', '')}\n\n"
        f"OPIS + HASHTAGI (skopiuj razem):\n{opis_z_hasztagami}\n\n"
        f"SUGEROWANA CENA: {price_line}\n"
        f"(Mediana Vinted: {price_data.get('vinted_median') or '—'} zł"
        f" | Próbka: {price_data.get('vinted_count', 0)} ogłoszeń)\n\n"
        f"---\nANALIZA ZDJĘCIA:\n"
        f"Marka:    {analysis.get('marka', '—')} (pewność: {analysis.get('pewnosc_marki', '—')})\n"
        f"Kategoria:{analysis.get('kategoria', '—')} | Płeć: {analysis.get('plec', '—')}\n"
        f"Stan:     {analysis.get('stan', '—')}\n"
        f"Kolor:    {analysis.get('kolor_glowny', '—')}\n"
        f"Rozmiar:  {analysis.get('rozmiar_hint') or '—'}\n"
        f"Materiał: {analysis.get('material_hint') or '—'}\n"
        f"Cechy:    {features}\n"
        f"Wady:     {defects}\n"
    )
    with open(os.path.join(folder, "listing_vinted.txt"), "w", encoding="utf-8") as f:
        f.write(txt)

    return folder


# ================================================================== #
# PIPELINE ORCHESTRATION
# ================================================================== #

Progress = Callable[[str, int, int], None]


def _process_one(
    img_path: str,
    tmp_out: str,
    remove_bg: bool,
    bg_color: tuple,
    api_key: str,
    output_dir: str,
    idx: int,
    progress: Optional[Progress],
    total_steps: int,
    step_offset: int,
) -> dict:
    """Internal: process one image as one product."""
    result: dict = {"input": img_path, "status": "error"}

    if progress:
        progress(f"[{idx}] Obrabiam zdjęcie…", step_offset + 1, total_steps)
    if not process_image(img_path, tmp_out, remove_bg=remove_bg, bg_color=bg_color):
        result["reason"] = "Błąd przetwarzania zdjęcia"
        return result

    if progress:
        progress(f"[{idx}] Analizuję AI…", step_offset + 2, total_steps)
    try:
        analysis = analyze_image(img_path, api_key)
    except Exception as e:
        analysis = {
            "marka": "nieznana", "kategoria": "odziez", "plec": "unisex",
            "stan": "dobry", "kolor_glowny": "", "rozmiar_hint": None,
            "widoczne_wady": [], "cechy_szczegolne": [], "material_hint": None,
            "pewnosc_marki": "niska", "_error": str(e),
        }

    if progress:
        progress(f"[{idx}] Sprawdzam ceny…", step_offset + 3, total_steps)
    price_data = get_price_estimate(analysis.get("marka", ""), analysis.get("kategoria", ""))

    if progress:
        progress(f"[{idx}] Generuję ogłoszenie…", step_offset + 4, total_steps)
    try:
        listing = generate_listing(analysis, price_data, api_key)
    except Exception as e:
        listing = {"tytul": "", "opis": "", "hashtagi": [], "_error": str(e)}

    slug = _make_slug(analysis, idx)
    folder = save_result(output_dir, slug, [tmp_out], analysis, listing, price_data)
    try:
        os.remove(tmp_out)
    except OSError:
        pass

    result.update({
        "status": "ok",
        "folder": folder,
        "slug": slug,
        "analysis": analysis,
        "listing": listing,
        "price_data": price_data,
    })
    return result


def run_batch(
    image_paths: list[str],
    output_dir: str,
    api_key: str,
    remove_bg: bool = True,
    bg_color: tuple = (255, 255, 255),
    progress: Optional[Progress] = None,
) -> list[dict]:
    """
    Batch mode: each image in image_paths = one independent product.
    Returns list of result dicts.
    """
    os.makedirs(output_dir, exist_ok=True)
    steps_per_item = 4
    total = len(image_paths) * steps_per_item
    results = []

    for idx, img_path in enumerate(image_paths, 1):
        tmp_out = img_path + f"__proc_{idx}.jpg"
        offset = (idx - 1) * steps_per_item
        r = _process_one(
            img_path, tmp_out, remove_bg, bg_color,
            api_key, output_dir, idx, progress, total, offset,
        )
        results.append(r)

    return results


def run_single(
    image_paths: list[str],
    output_dir: str,
    api_key: str,
    remove_bg: bool = True,
    bg_color: tuple = (255, 255, 255),
    progress: Optional[Progress] = None,
) -> dict:
    """
    Single-product mode: multiple photos → one product.
    Processes all images, uses FIRST for AI analysis.
    Returns one result dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    n = len(image_paths)
    total = n + 3  # n photo steps + analyze + price + listing
    processed: list[str] = []

    for i, img_path in enumerate(image_paths, 1):
        if progress:
            progress(f"Obrabiam zdjęcie {i}/{n}…", i, total)
        tmp_out = img_path + f"__proc_{i}.jpg"
        if process_image(img_path, tmp_out, remove_bg=remove_bg, bg_color=bg_color):
            processed.append(tmp_out)

    if not processed:
        return {"status": "error", "reason": "Żadne zdjęcie nie zostało przetworzone"}

    if progress:
        progress("Analizuję AI (pierwsze zdjęcie)…", n + 1, total)
    try:
        analysis = analyze_image(image_paths[0], api_key)
    except Exception as e:
        analysis = {
            "marka": "nieznana", "kategoria": "odziez", "plec": "unisex",
            "stan": "dobry", "kolor_glowny": "", "rozmiar_hint": None,
            "widoczne_wady": [], "cechy_szczegolne": [], "material_hint": None,
            "pewnosc_marki": "niska", "_error": str(e),
        }

    if progress:
        progress("Sprawdzam ceny rynkowe…", n + 2, total)
    price_data = get_price_estimate(analysis.get("marka", ""), analysis.get("kategoria", ""))

    if progress:
        progress("Generuję ogłoszenie…", n + 3, total)
    try:
        listing = generate_listing(analysis, price_data, api_key)
    except Exception as e:
        listing = {"tytul": "", "opis": "", "hashtagi": [], "_error": str(e)}

    slug = _make_slug(analysis, 1)
    folder = save_result(output_dir, slug, processed, analysis, listing, price_data)
    for p in processed:
        try:
            os.remove(p)
        except OSError:
            pass

    return {
        "status": "ok",
        "folder": folder,
        "slug": slug,
        "analysis": analysis,
        "listing": listing,
        "price_data": price_data,
    }


# ================================================================== #
# VISION-BASED GROUPING
# ================================================================== #

_FINGERPRINT_PROMPT = """\
Opisz ten produkt odzieżowy w 6 cechach do celów automatycznego grupowania zdjęć.
Bądź konsekwentny — różne zdjęcia tego samego produktu (przód/tył/detal) muszą dawać identyczny wynik.

Odpowiedz WYŁĄCZNIE czystym JSON-em:
{
  "kategoria": "kurtka|plaszcz|sukienka|bluza|spodnie|spodnica|koszula|tshirt|marynarka|buty|torebka|sport|odziez",
  "marka": "nazwa marki lub 'nieznana'",
  "kolor1": "dominujący kolor (jeden wyraz po polsku, np. czarny, granatowy, biały)",
  "kolor2": "drugi kolor lub 'brak'",
  "wzor": "jednolity|paski|kratka|nadruk|kwiaty|geometryczny|inny",
  "material": "jeans|skora|dzianina|tkanina|syntetyk|welna|bawelna|inny"
}\
"""


def fingerprint_image(image_path: str, api_key: str) -> dict:
    """
    Quick Claude Vision call to extract a compact product fingerprint.
    Used for grouping photos of the same item. Cheap: ~200 tokens per call.
    """
    import anthropic

    ext = Path(image_path).suffix.lower()
    media_type = _MEDIA_TYPES.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",   # cheapest model — enough for fingerprinting
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": img_b64},
                },
                {"type": "text", "text": _FINGERPRINT_PROMPT},
            ],
        }],
    )
    raw = resp.content[0].text.strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "kategoria": "odziez", "marka": "nieznana",
            "kolor1": "nieznany", "kolor2": "brak",
            "wzor": "inny", "material": "inny",
            "_parse_error": raw[:100],
        }


def _similarity_score(fp1: dict, fp2: dict) -> int:
    """
    Compute similarity score between two fingerprints.
    Returns 0 if definitely different products, higher = more similar.

    Scoring:
      category match (required) : +3
      brand match (both known)  : +3  (known mismatch → return 0 immediately)
      primary color match       : +2
      secondary color match     : +1
      pattern match             : +1
      material match            : +1
    Max possible: 11
    """
    if fp1.get("kategoria") != fp2.get("kategoria"):
        return 0

    score = 3  # same category

    b1 = (fp1.get("marka") or "nieznana").lower().strip()
    b2 = (fp2.get("marka") or "nieznana").lower().strip()
    if b1 != "nieznana" and b2 != "nieznana":
        if b1 == b2:
            score += 3
        else:
            return 0  # known different brands = definitely different products

    if fp1.get("kolor1") == fp2.get("kolor1"):
        score += 2
    if fp1.get("kolor2") == fp2.get("kolor2"):
        score += 1
    if fp1.get("wzor") == fp2.get("wzor"):
        score += 1
    if fp1.get("material") == fp2.get("material"):
        score += 1

    return score


_MATCH_THRESHOLD = 6  # category(3) + color(2) + one more feature


def group_by_vision(
    paths: list[str],
    api_key: str,
    progress: Optional[Progress] = None,
) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """
    Group images by visual similarity via Claude Vision fingerprints.

    1. Fingerprint each image (one cheap Haiku call per photo).
    2. Greedy clustering: first unassigned photo starts a group;
       subsequent photos join if similarity score >= threshold.

    Returns:
      groups       — {group_label: [paths]}
      fingerprints — {path: fingerprint_dict}
    """
    total = len(paths)
    fingerprints: dict[str, dict] = {}

    for i, path in enumerate(paths, 1):
        if progress:
            progress(f"Analizuję zdjęcie {i}/{total}: {Path(path).name}", i, total)
        fingerprints[path] = fingerprint_image(path, api_key)

    # Greedy clustering
    assigned: set[str] = set()
    groups: dict[str, list[str]] = {}
    group_idx = 1

    for path in paths:
        if path in assigned:
            continue

        fp = fingerprints[path]
        group: list[str] = [path]
        assigned.add(path)

        for other in paths:
            if other in assigned:
                continue
            if _similarity_score(fp, fingerprints[other]) >= _MATCH_THRESHOLD:
                group.append(other)
                assigned.add(other)

        cat   = fp.get("kategoria", "produkt")
        brand = fp.get("marka", "").replace(" ", "_") or "nieznana"
        color = fp.get("kolor1", "")
        label = f"{cat}_{brand}_{color}_{group_idx:02d}"
        groups[label] = group
        group_idx += 1

    return groups, fingerprints


# ================================================================== #
# GROUPING HELPERS (prefix-based)
# ================================================================== #

def group_by_prefix(paths: list[str]) -> dict[str, list[str]]:
    """
    Group image paths by filename prefix, ignoring trailing _N / -N / (N) suffixes.

    Examples:
      kurtka_1.jpg, kurtka_2.jpg, kurtka_3.jpg  →  group "kurtka"
      bluza-01.jpg, bluza-02.jpg                 →  group "bluza"
      IMG_4521.jpg                               →  group "IMG_4521" (solo)
      DSC_0001.jpg, DSC_0002.jpg                 →  group "DSC" (by common prefix)

    Returns OrderedDict: {group_name: [sorted list of paths]}
    """
    groups: dict[str, list[str]] = {}
    for path in sorted(paths):
        stem = Path(path).stem
        # Strip trailing separator + digits: kurtka_1 → kurtka, bluza-02 → bluza
        base = re.sub(r'[\s_\-]+\d+$', '', stem).strip() or stem
        groups.setdefault(base, []).append(path)
    return groups


def run_grouped(
    groups: dict[str, list[str]],
    output_dir: str,
    api_key: str,
    remove_bg: bool = True,
    bg_color: tuple = (255, 255, 255),
    progress: Optional[Progress] = None,
) -> list[dict]:
    """
    Grouped mode: each key in `groups` = one product with potentially multiple photos.
    Internally calls run_single per group.
    Returns list of result dicts (one per group).
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []
    group_names = list(groups.keys())
    total_groups = len(group_names)

    for idx, name in enumerate(group_names, 1):
        paths = groups[name]

        def scoped_progress(msg: str, cur: int, tot: int, _idx=idx, _total=total_groups) -> None:
            if progress:
                # Map inner progress to outer slice
                outer = (_idx - 1) / _total + (cur / max(tot, 1)) / _total
                progress(f"Produkt {_idx}/{_total} — {msg}", int(outer * 100), 100)

        result = run_single(
            paths, output_dir, api_key,
            remove_bg=remove_bg, bg_color=bg_color,
            progress=scoped_progress,
        )
        result["group_name"] = name
        result["photo_count"] = len(paths)
        results.append(result)

    return results
