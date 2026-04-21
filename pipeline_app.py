"""
Vinted Pipeline — samodzielna aplikacja Streamlit.

Uruchomienie:
    streamlit run pipeline_app.py

Flow:
  Wrzucasz surowe zdjęcia
    → usunięcie tła + normalizacja do 1200×1200
    → analiza AI (marka, kategoria, stan, kolor, wady)
    → wycena rynkowa (live Vinted)
    → generowanie tytułu, opisu i hashtagów
    → foldery z gotowymi plikami do wystawienia
"""

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime

import streamlit as st

from photo_pipeline import (
    PIL_OK,
    REMBG_OK,
    run_batch,
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
.result-card  { background:#f8f9fa; border-radius:10px; padding:16px; margin-bottom:12px; }
.tag          { display:inline-block; background:#e2e8f0; border-radius:4px;
                padding:2px 8px; margin:2px; font-size:13px; }
.price-big    { font-size:32px; font-weight:700; color:#09b1ba; }
.status-ok    { color:#38a169; font-weight:600; }
.status-err   { color:#e53e3e; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ #
# Sidebar — settings
# ------------------------------------------------------------------ #

def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


with st.sidebar:
    st.title("⚡ Vinted Pipeline")
    st.markdown("---")

    st.markdown("### Klucz Claude API")
    api_key = st.text_input(
        "Klucz Claude API",
        type="password",
        placeholder="sk-ant-...",
        label_visibility="collapsed",
    )
    if api_key:
        st.success("Klucz wpisany")
    else:
        st.warning("Wymagany do analizy AI")

    st.markdown("---")
    st.markdown("### Zdjęcia")

    remove_bg = st.checkbox(
        "Usuń tło (rembg)",
        value=REMBG_OK,
        disabled=not REMBG_OK,
    )
    if not REMBG_OK:
        st.caption("Brak rembg — `pip install rembg`")

    bg_hex = st.color_picker("Kolor tła", "#FFFFFF")
    bg_color = _hex_to_rgb(bg_hex)

    st.markdown("---")
    st.markdown("### Tryb przetwarzania")
    batch_mode = st.radio(
        "Tryb",
        ["Batch — każde zdjęcie = osobny produkt",
         "Jeden produkt — wszystkie zdjęcia razem"],
        label_visibility="collapsed",
    ).startswith("Batch")

    st.markdown("---")
    st.markdown("### Folder wynikowy")
    output_dir = st.text_input("Ścieżka", value="pipeline_output")
    st.caption(f"Pliki trafią do: `{os.path.abspath(output_dir)}`")

    st.markdown("---")
    st.markdown("### Status bibliotek")
    st.markdown(
        f"- Pillow: {'✅' if PIL_OK else '❌ `pip install Pillow`'}\n"
        f"- rembg:  {'✅' if REMBG_OK else '❌ `pip install rembg`'}\n"
        f"- Claude: {'✅' if api_key else '❌ brak klucza'}"
    )


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

st.title("⚡ Vinted Pipeline")
st.markdown(
    "Wrzuć surowe zdjęcia → program obrobi je, przeanalizuje AI, "
    "sprawdzi ceny i wygeneruje gotowe ogłoszenia."
)

# ------------------------------------------------------------------ #
# Upload
# ------------------------------------------------------------------ #

uploaded = st.file_uploader(
    "Wrzuć zdjęcia",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if not uploaded:
    st.info("Wrzuć jedno lub więcej zdjęć żeby zacząć.")
    st.stop()

# Thumbnail preview
st.markdown(f"**Wrzucono: {len(uploaded)} zdjęć**")
cols = st.columns(min(len(uploaded), 6))
for i, f in enumerate(uploaded[:6]):
    cols[i].image(f, caption=f.name, use_container_width=True)
if len(uploaded) > 6:
    st.caption(f"…i {len(uploaded) - 6} więcej")

st.markdown("---")

# Mode summary
if batch_mode:
    st.info(
        f"**Tryb Batch** — {len(uploaded)} zdjęć = {len(uploaded)} osobnych produktów. "
        "Każde zdjęcie dostanie własną analizę i ogłoszenie."
    )
else:
    st.info(
        f"**Tryb Jeden produkt** — {len(uploaded)} zdjęć → 1 ogłoszenie. "
        "AI przeanalizuje pierwsze zdjęcie."
    )

# ------------------------------------------------------------------ #
# Run button
# ------------------------------------------------------------------ #

if not api_key:
    st.warning("Wpisz klucz Claude API w panelu bocznym żeby uruchomić.")
    st.stop()

run_btn = st.button("⚡ Uruchom pipeline", type="primary", use_container_width=True)

if run_btn:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save uploads to temp dir
        tmp_paths: list[str] = []
        for uf in uploaded:
            p = os.path.join(tmpdir, uf.name)
            with open(p, "wb") as fh:
                fh.write(uf.getvalue())
            tmp_paths.append(p)

        # Progress UI
        progress_bar = st.progress(0.0)
        status_placeholder = st.empty()

        def on_progress(msg: str, current: int, total: int) -> None:
            frac = min(current / max(total, 1), 1.0)
            progress_bar.progress(frac)
            status_placeholder.markdown(f"⏳ {msg}")

        try:
            if batch_mode:
                results = run_batch(
                    tmp_paths, output_dir, api_key,
                    remove_bg=remove_bg, bg_color=bg_color,
                    progress=on_progress,
                )
            else:
                results = [run_single(
                    tmp_paths, output_dir, api_key,
                    remove_bg=remove_bg, bg_color=bg_color,
                    progress=on_progress,
                )]

            progress_bar.progress(1.0)
            status_placeholder.markdown("✅ Gotowe!")
            st.session_state["pipeline_results"] = results

        except Exception as exc:
            st.error(f"Błąd pipeline: {exc}")
            st.exception(exc)
            st.stop()

# ------------------------------------------------------------------ #
# Results
# ------------------------------------------------------------------ #

if "pipeline_results" not in st.session_state:
    st.stop()

results: list[dict] = st.session_state["pipeline_results"]
ok = [r for r in results if r.get("status") == "ok"]
err = [r for r in results if r.get("status") != "ok"]

# Summary row
sc1, sc2, sc3 = st.columns(3)
sc1.metric("Przetworzono", f"{len(ok)}/{len(results)}")
sc2.metric("Błędy", len(err))
sc3.metric("Folder", output_dir)

if err:
    with st.expander(f"Błędy ({len(err)})", expanded=False):
        for r in err:
            st.error(f"{Path(r.get('input', '?')).name}: {r.get('reason', 'nieznany błąd')}")

st.markdown("---")

# Per-product result cards
for i, r in enumerate(ok, 1):
    analysis  = r["analysis"]
    listing   = r["listing"]
    price     = r["price_data"]
    folder    = r["folder"]

    brand = analysis.get("marka", "?")
    cat   = analysis.get("kategoria", "?")
    title = listing.get("tytul") or "—"
    cond  = analysis.get("stan", "—")
    color = analysis.get("kolor_glowny", "—")
    size  = analysis.get("rozmiar_hint") or "—"

    header = f"#{i} — {brand} {cat}  |  {title[:45]}{'…' if len(title) > 45 else ''}"

    with st.expander(header, expanded=(i == 1)):
        col_img, col_data = st.columns([1, 2], gap="large")

        # --- Left: processed images ---
        with col_img:
            proc_imgs = sorted(Path(folder).glob("*_processed.jpg"))
            if proc_imgs:
                for img_path in proc_imgs[:6]:
                    st.image(str(img_path), use_container_width=True)
            else:
                st.caption("Brak przetworzonych zdjęć w folderze.")

        # --- Right: listing + analysis ---
        with col_data:

            # Price row
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

            # Listing text
            st.markdown("**Tytuł** *(skopiuj do Vinted)*")
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

            # Analysis details
            with st.expander("Szczegóły analizy AI", expanded=False):
                detail_cols = st.columns(2)
                detail_cols[0].markdown(
                    f"**Marka:** {brand}  \n"
                    f"**Pewność marki:** {analysis.get('pewnosc_marki', '—')}  \n"
                    f"**Kategoria:** {cat}  \n"
                    f"**Płeć:** {analysis.get('plec', '—')}  \n"
                )
                detail_cols[1].markdown(
                    f"**Stan:** {cond}  \n"
                    f"**Kolor:** {color}  \n"
                    f"**Rozmiar:** {size}  \n"
                    f"**Materiał:** {analysis.get('material_hint') or '—'}  \n"
                )
                wady = analysis.get("widoczne_wady") or []
                cechy = analysis.get("cechy_szczegolne") or []
                if wady:
                    st.markdown(f"**Widoczne wady:** {', '.join(wady)}")
                if cechy:
                    st.markdown(f"**Cechy szczególne:** {', '.join(cechy)}")

            # Download single listing
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
# Download ALL as ZIP
# ------------------------------------------------------------------ #

if ok:
    st.markdown("---")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in ok:
            folder = r["folder"]
            slug   = r["slug"]
            for fpath in Path(folder).iterdir():
                if fpath.is_file():
                    zf.write(fpath, f"{slug}/{fpath.name}")
    buf.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        f"Pobierz wszystko jako ZIP ({len(ok)} produktów)",
        data=buf.getvalue(),
        file_name=f"vinted_pipeline_{timestamp}.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )

    st.caption(
        f"Pliki zapisane lokalnie w: `{os.path.abspath(output_dir)}/`  \n"
        "Każdy produkt ma własny folder z przetworzonymi zdjęciami "
        "i plikami `listing.json` oraz `listing_vinted.txt`."
    )
