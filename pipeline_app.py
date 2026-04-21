"""
Vinted Pipeline — samodzielna aplikacja Streamlit.

Uruchomienie:
    streamlit run pipeline_app.py

Tryby:
  1. Batch          — wrzucasz N zdjęć, każde = osobny produkt
  2. Jeden produkt  — wrzucasz N zdjęć, wszystkie = jeden produkt
  3. Auto-grupuj    — wrzucasz np. kurtka_1.jpg, kurtka_2.jpg, bluza_1.jpg
                      → program sam wykrywa grupy po nazwie pliku
  4. ZIP z folderami— ziperujesz foldery (każdy folder = produkt), wrzucasz raz
"""

import io
import json
import os
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path
from datetime import datetime

import streamlit as st

from photo_pipeline import (
    PIL_OK,
    REMBG_OK,
    group_by_prefix,
    run_batch,
    run_grouped,
    run_single,
)

# ------------------------------------------------------------------ #
# Page config
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Vinted Pipeline",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.tag   { display:inline-block; background:#e2e8f0; border-radius:4px;
         padding:2px 8px; margin:2px; font-size:13px; }
.group-box { background:#f0fff4; border-left:4px solid #38a169;
             padding:8px 12px; border-radius:4px; margin:4px 0; font-size:14px; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Sidebar
# ------------------------------------------------------------------ #

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


with st.sidebar:
    st.title("⚡ Vinted Pipeline")
    st.markdown("---")

    st.markdown("### Klucz Claude API")
    api_key = st.text_input(
        "Klucz", type="password", placeholder="sk-ant-…",
        label_visibility="collapsed",
    )
    st.caption("Wymagany do analizy AI i generowania opisów.")

    st.markdown("---")
    st.markdown("### Zdjęcia")
    remove_bg = st.checkbox("Usuń tło (rembg)", value=REMBG_OK, disabled=not REMBG_OK)
    if not REMBG_OK:
        st.caption("Zainstaluj: `pip install rembg`")
    bg_hex   = st.color_picker("Kolor tła", "#FFFFFF")
    bg_color = _hex_to_rgb(bg_hex)

    st.markdown("---")
    st.markdown("### Folder wynikowy")
    output_dir = st.text_input("Ścieżka", value="pipeline_output")
    st.caption(f"`{os.path.abspath(output_dir)}`")

    st.markdown("---")
    libs = (
        f"- Pillow: {'✅' if PIL_OK else '❌'}\n"
        f"- rembg:  {'✅' if REMBG_OK else '❌'}\n"
        f"- Claude: {'✅' if api_key else '❌'}"
    )
    st.markdown(libs)


# ================================================================== #
# Main
# ================================================================== #

st.title("⚡ Vinted Pipeline")
st.markdown(
    "Wrzuć surowe zdjęcia → program usuwa tło, analizuje AI, sprawdza ceny "
    "i generuje gotowe ogłoszenia na Vinted."
)

# ------------------------------------------------------------------ #
# Mode selector
# ------------------------------------------------------------------ #

MODE_BATCH   = "Batch — każde zdjęcie = osobny produkt"
MODE_SINGLE  = "Jeden produkt — wszystkie zdjęcia razem"
MODE_GROUP   = "Auto-grupuj — wiele produktów, wiele zdjęć naraz"
MODE_ZIP     = "ZIP z folderami — każdy folder = produkt"

mode = st.radio(
    "Tryb przetwarzania",
    [MODE_BATCH, MODE_SINGLE, MODE_GROUP, MODE_ZIP],
    horizontal=True,
)

# Help text per mode
help_texts = {
    MODE_BATCH:  "Każde zdjęcie = osobny produkt. Wrzucasz 10 zdjęć → 10 ogłoszeń.",
    MODE_SINGLE: "Wszystkie zdjęcia = jeden produkt. Przydatne gdy jeden przedmiot ma wiele zdjęć.",
    MODE_GROUP:  (
        "Wrzucasz wiele produktów naraz. Zdjęcia grupowane po nazwie pliku:  \n"
        "`kurtka_1.jpg`, `kurtka_2.jpg`, `kurtka_3.jpg` → **1 produkt 'kurtka'**  \n"
        "`bluza_1.jpg`, `bluza_2.jpg` → **1 produkt 'bluza'**  \n"
        "Wystarczy odpowiednio nazwać pliki przed wrzuceniem."
    ),
    MODE_ZIP: (
        "Ziperujesz foldery ze zdjęciami, wrzucasz jeden plik ZIP:  \n"
        "```\n📦 produkty.zip\n"
        "  📁 kurtka_zara/\n"
        "    1.jpg, 2.jpg, 3.jpg\n"
        "  📁 bluza_reserved/\n"
        "    1.jpg, 2.jpg\n```"
    ),
}
st.info(help_texts[mode])

# ------------------------------------------------------------------ #
# Upload area
# ------------------------------------------------------------------ #

st.markdown("---")

if mode == MODE_ZIP:
    zip_file = st.file_uploader("Wrzuć plik ZIP z folderami", type=["zip"])
    uploaded_files = None
else:
    uploaded_files = st.file_uploader(
        "Wrzuć zdjęcia",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )
    zip_file = None

# ------------------------------------------------------------------ #
# Preview + group detection
# ------------------------------------------------------------------ #

groups: dict[str, list] = {}   # {group_name: [paths]} — filled in tmpdir later
preview_groups: dict[str, list] = {}   # {group_name: [UploadedFile]} — for preview

if mode == MODE_ZIP and zip_file:
    # Peek into ZIP to show folder structure
    try:
        with zipfile.ZipFile(io.BytesIO(zip_file.getvalue())) as zf:
            folders: dict[str, list] = {}
            for name in zf.namelist():
                p = Path(name)
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    folder_name = p.parts[0] if len(p.parts) > 1 else "_root"
                    folders.setdefault(folder_name, []).append(name)
            if folders:
                st.markdown(f"**Wykryto {len(folders)} folderów (produktów):**")
                for fname, files in folders.items():
                    st.markdown(
                        f'<div class="group-box">📁 <b>{fname}</b> — {len(files)} zdjęć</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.warning("ZIP nie zawiera obsługiwanych zdjęć w podfolderach.")
    except Exception as e:
        st.error(f"Błąd odczytu ZIP: {e}")

elif uploaded_files:
    n = len(uploaded_files)
    # Thumbnail preview (max 8)
    st.markdown(f"**Wrzucono: {n} zdjęć**")
    thumb_cols = st.columns(min(n, 8))
    for i, f in enumerate(uploaded_files[:8]):
        thumb_cols[i].image(f, caption=f.name, use_container_width=True)
    if n > 8:
        st.caption(f"…i {n - 8} więcej")

    # Group preview for MODE_GROUP
    if mode == MODE_GROUP:
        # Build preview groups from uploaded file names
        name_to_file = {f.name: f for f in uploaded_files}
        raw_paths = list(name_to_file.keys())
        detected = group_by_prefix(raw_paths)

        st.markdown(f"**Wykryte grupy ({len(detected)} produktów):**")
        for gname, gpaths in detected.items():
            files_str = ", ".join(Path(p).name for p in gpaths)
            count = len(gpaths)
            st.markdown(
                f'<div class="group-box">'
                f'🗂 <b>{gname}</b> — {count} zdjęć: <span style="color:#718096">{files_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        preview_groups = {g: [name_to_file[p] for p in ps] for g, ps in detected.items()}

# ------------------------------------------------------------------ #
# Run button
# ------------------------------------------------------------------ #

st.markdown("---")

nothing_uploaded = (uploaded_files is None or len(uploaded_files) == 0) and zip_file is None
if nothing_uploaded:
    st.info("Wrzuć zdjęcia lub ZIP żeby zacząć.")
    st.stop()

if not api_key:
    st.warning("Wpisz klucz Claude API w panelu bocznym.")
    st.stop()

run_clicked = st.button("⚡ Uruchom pipeline", type="primary", use_container_width=True)

if run_clicked:
    progress_bar    = st.progress(0.0)
    status_text     = st.empty()

    def on_progress(msg: str, cur: int, tot: int) -> None:
        progress_bar.progress(min(cur / max(tot, 1), 1.0))
        status_text.markdown(f"⏳ {msg}")

    results: list[dict] = []

    with tempfile.TemporaryDirectory() as tmpdir:

        # --- ZIP mode ---
        if mode == MODE_ZIP and zip_file:
            zip_bytes = zip_file.getvalue()
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(tmpdir)

            # Build groups from extracted folder structure
            zip_groups: dict[str, list[str]] = {}
            for root, dirs, files in os.walk(tmpdir):
                image_files = sorted(
                    os.path.join(root, f) for f in files
                    if Path(f).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                )
                if not image_files:
                    continue
                folder_name = os.path.relpath(root, tmpdir).replace(os.sep, "/")
                if folder_name == ".":
                    # Files at root of ZIP → batch
                    for img in image_files:
                        zip_groups[Path(img).stem] = [img]
                else:
                    zip_groups[folder_name] = image_files

            if zip_groups:
                results = run_grouped(
                    zip_groups, output_dir, api_key,
                    remove_bg=remove_bg, bg_color=bg_color,
                    progress=on_progress,
                )
            else:
                st.error("Brak zdjęć w ZIP.")

        else:
            # Save uploaded files to tmpdir
            tmp_paths: list[str] = []
            for uf in uploaded_files:
                p = os.path.join(tmpdir, uf.name)
                with open(p, "wb") as fh:
                    fh.write(uf.getvalue())
                tmp_paths.append(p)

            if mode == MODE_BATCH:
                results = run_batch(
                    tmp_paths, output_dir, api_key,
                    remove_bg=remove_bg, bg_color=bg_color,
                    progress=on_progress,
                )

            elif mode == MODE_SINGLE:
                results = [run_single(
                    tmp_paths, output_dir, api_key,
                    remove_bg=remove_bg, bg_color=bg_color,
                    progress=on_progress,
                )]

            elif mode == MODE_GROUP:
                file_groups = group_by_prefix(tmp_paths)
                results = run_grouped(
                    file_groups, output_dir, api_key,
                    remove_bg=remove_bg, bg_color=bg_color,
                    progress=on_progress,
                )

    progress_bar.progress(1.0)
    status_text.markdown("✅ Gotowe!")
    st.session_state["pipeline_results"] = results

# ================================================================== #
# Results
# ================================================================== #

if "pipeline_results" not in st.session_state:
    st.stop()

results: list[dict] = st.session_state["pipeline_results"]
ok_results  = [r for r in results if r.get("status") == "ok"]
err_results = [r for r in results if r.get("status") != "ok"]

# Summary
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Przetworzono", f"{len(ok_results)}/{len(results)}")
sc2.metric("Błędy", len(err_results))
sc3.metric("Folder", output_dir)

if err_results:
    with st.expander(f"Błędy ({len(err_results)})", expanded=False):
        for r in err_results:
            label = r.get("group_name") or Path(r.get("input", "?")).name
            st.error(f"{label}: {r.get('reason', 'nieznany błąd')}")

st.markdown("---")

# Per-product cards
for i, r in enumerate(ok_results, 1):
    analysis  = r["analysis"]
    listing   = r["listing"]
    price     = r["price_data"]
    folder    = r["folder"]

    brand  = analysis.get("marka", "?")
    cat    = analysis.get("kategoria", "?")
    title  = listing.get("tytul") or "—"
    photos = r.get("photo_count", 1)
    gname  = r.get("group_name", "")

    label_extra = f" ({photos} zdjęć)" if photos > 1 else ""
    header = f"#{i}  {brand} {cat}{label_extra}  —  {title[:50]}{'…' if len(title) > 50 else ''}"

    with st.expander(header, expanded=(i == 1)):
        col_img, col_data = st.columns([1, 2], gap="large")

        with col_img:
            proc_imgs = sorted(Path(folder).glob("*_processed.jpg"))
            for img_path in proc_imgs[:6]:
                st.image(str(img_path), use_container_width=True)
            if not proc_imgs:
                st.caption("Brak przetworzonych zdjęć w folderze.")

        with col_data:
            # Price
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric(
                "Sugerowana cena",
                f"{price.get('suggested_price'):.0f} zł" if price.get("suggested_price") else "—",
            )
            pc2.metric(
                "Mediana Vinted",
                f"{price.get('vinted_median'):.0f} zł" if price.get("vinted_median") else "—",
            )
            pc3.metric("Próbka", f"{price.get('vinted_count', 0)} ogł.")

            st.markdown("---")

            st.markdown("**Tytuł**")
            st.code(listing.get("tytul", ""), language=None)

            st.markdown("**Opis**")
            st.code(listing.get("opis", ""), language=None)

            st.markdown("**Hashtagi**")
            hashtags = listing.get("hashtagi", [])
            if hashtags:
                st.markdown(
                    " ".join(f'<span class="tag">{t}</span>' for t in hashtags),
                    unsafe_allow_html=True,
                )
                st.code(" ".join(hashtags), language=None)

            st.markdown("---")

            with st.expander("Szczegóły analizy AI", expanded=False):
                d1, d2 = st.columns(2)
                d1.markdown(
                    f"**Marka:** {brand} *(pewność: {analysis.get('pewnosc_marki', '—')})*  \n"
                    f"**Kategoria:** {cat}  \n"
                    f"**Płeć:** {analysis.get('plec', '—')}  \n"
                )
                d2.markdown(
                    f"**Stan:** {analysis.get('stan', '—')}  \n"
                    f"**Kolor:** {analysis.get('kolor_glowny', '—')}  \n"
                    f"**Rozmiar:** {analysis.get('rozmiar_hint') or '—'}  \n"
                    f"**Materiał:** {analysis.get('material_hint') or '—'}  \n"
                )
                wady  = analysis.get("widoczne_wady") or []
                cechy = analysis.get("cechy_szczegolne") or []
                if wady:
                    st.markdown(f"**Wady:** {', '.join(wady)}")
                if cechy:
                    st.markdown(f"**Cechy:** {', '.join(cechy)}")

            txt_path = Path(folder) / "listing_vinted.txt"
            if txt_path.exists():
                st.download_button(
                    "Pobierz listing_vinted.txt",
                    data=txt_path.read_bytes(),
                    file_name=f"{r['slug']}_listing.txt",
                    mime="text/plain",
                    key=f"dl_txt_{i}",
                )

# ------------------------------------------------------------------ #
# Download all as ZIP
# ------------------------------------------------------------------ #

if ok_results:
    st.markdown("---")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in ok_results:
            folder = r["folder"]
            slug   = r["slug"]
            for fpath in Path(folder).iterdir():
                if fpath.is_file():
                    zf.write(fpath, f"{slug}/{fpath.name}")
    buf.seek(0)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        f"Pobierz wszystko jako ZIP  ({len(ok_results)} produktów)",
        data=buf.getvalue(),
        file_name=f"vinted_pipeline_{ts}.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )
    st.caption(
        f"Pliki zapisane też lokalnie: `{os.path.abspath(output_dir)}/`  \n"
        "Każdy produkt ma własny podfolder z przetworzonymi zdjęciami, "
        "`listing.json` i `listing_vinted.txt`."
    )
