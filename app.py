import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

from analyzer import add_recommendations, calc_stats
from market_data import enrich_with_market_data
from goal_tracker import add_sale, get_monthly_summary, get_last_months, GOAL_LIMIT
from trends import generate_sourcing_list
from photo_advisor import get_basic_advice, get_ai_advice, detect_category
from price_history import record_snapshot, get_price_changes, get_all_history
from listings_csv import (
    load_listings, save_listings, add_listing,
    delete_listing, import_from_upload, LISTINGS_PATH, FIELDS,
)
import json
import os

# ------------------------------------------------------------------ #
# Page config
# ------------------------------------------------------------------ #

st.set_page_config(
    page_title="Vinted Tracker",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.metric-box { background:#f8f9fa; border-radius:10px; padding:16px; text-align:center; }
.urgent { background:#fff3f3; border-left:4px solid #e53e3e; padding:8px 12px; border-radius:4px; margin:4px 0; }
.medium { background:#fffbf0; border-left:4px solid #d69e2e; padding:8px 12px; border-radius:4px; margin:4px 0; }
.ok     { background:#f0fff4; border-left:4px solid #38a169; padding:8px 12px; border-radius:4px; margin:4px 0; }
</style>
""", unsafe_allow_html=True)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), ".vinted_config.json")


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)


@st.cache_data(ttl=1800, show_spinner=False)
def analyse_listings(ebay_app_id: str = "") -> tuple[list, dict]:
    items = load_listings()
    if not items:
        return [], {}
    items = add_recommendations(items)
    items = enrich_with_market_data(items, ebay_app_id or None)
    items = add_recommendations(items)
    record_snapshot(items)
    stats = calc_stats(items)
    return items, stats


# ------------------------------------------------------------------ #
# Sidebar
# ------------------------------------------------------------------ #

cfg = load_config()

with st.sidebar:
    st.title("⚙️ Ustawienia")
    st.markdown("---")

    st.markdown("### 🛒 Dane rynkowe eBay (opcjonalne)")
    st.markdown("""
Program porówna Twoje ceny z tym **za ile rzeczy sprzedają się na eBay**.

**Jak uzyskać darmowy klucz eBay:**
1. Wejdź na **developer.ebay.com**
2. Zarejestruj się (bezpłatne)
3. Kliknij **Get an Application Key** → skopiuj **App ID (Client ID)**
""")
    ebay_app_id = st.text_input(
        "Klucz eBay App ID",
        value=cfg.get("ebay_app_id", ""),
        type="password",
        placeholder="TwojaAp-VintedTr-PRD-...",
    )
    if ebay_app_id:
        st.success("eBay aktywny — ceny będą porównywane z rynkiem")
    else:
        st.info("Bez klucza eBay program analizuje tylko Twoje dane")

    if st.button("💾 Zapisz ustawienia", use_container_width=True):
        updated = load_config()
        updated["ebay_app_id"] = ebay_app_id
        save_config(updated)
        st.success("Zapisano!")

    if st.button("🔄 Przelicz od nowa", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 🤖 Claude AI (porady foto, opcjonalnie)")
    claude_api_key = st.text_input(
        "Klucz Claude API",
        value=cfg.get("claude_api_key", ""),
        type="password",
        placeholder="sk-ant-...",
    )
    if st.button("💾 Zapisz klucz Claude", use_container_width=True):
        updated = load_config()
        updated["claude_api_key"] = claude_api_key
        save_config(updated)
        st.success("Zapisano!")


# ------------------------------------------------------------------ #
# Main dashboard
# ------------------------------------------------------------------ #

st.title("👗 Vinted Tracker — Twoja sprzedaż w jednym miejscu")

items, stats = analyse_listings(ebay_app_id)

monthly = get_monthly_summary()
st.markdown(
    f"🎯 Ten miesiąc: **{monthly['przychod']:.0f} zł** / {GOAL_LIMIT:.0f} zł &nbsp;&nbsp;"
    f"*(ostatnia aktualizacja: {datetime.now().strftime('%H:%M')})*"
)
prog_color = "#e53e3e" if monthly["progress_procent"] >= 90 else "#38a169"
st.markdown(
    f'<div style="background:#edf2f7;border-radius:8px;height:12px;margin-bottom:16px;">'
    f'<div style="background:{prog_color};width:{monthly["progress_procent"]}%;height:12px;border-radius:8px;"></div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ #
# Tabs
# ------------------------------------------------------------------ #

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📦 Moje ogłoszenia",
    "➕ Dodaj / edytuj",
    "🛒 Co kupić",
    "🧮 Kalkulator zakupu",
    "🎯 Cel miesięczny",
    "📸 Jak fotografować?",
])


# ================================================================== #
# TAB 1 — My listings
# ================================================================== #
with tab1:
    if not items:
        st.info("""
📋 **Jeszcze nie dodałeś żadnych ogłoszeń.**

Przejdź do zakładki **➕ Dodaj / edytuj** żeby wpisać swoje ogłoszenia.
Możesz też zaimportować plik CSV ze wszystkimi ogłoszeniami naraz.
""")
    else:
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("📦 Ogłoszeń", stats.get("lacznie_ogloszen", 0))
        k2.metric("🚨 Wymaga uwagi", stats.get("wymagaja_uwagi", 0))
        k3.metric("💰 Łączna wartość", f"{stats.get('lacznie_wartosc', 0):.0f} zł")
        k4.metric("📊 Średnia cena", f"{stats.get('srednia_cena', 0):.0f} zł")
        k5.metric("⏳ Śr. czas na rynku", f"{stats.get('sredni_czas_na_rynku', 0):.0f} dni")

        st.markdown("---")
        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.subheader("📅 Jak długo stoją ogłoszenia?")
            df = pd.DataFrame(items)

            def bucket(days):
                if days <= 7:   return "0–7 dni"
                if days <= 14:  return "8–14 dni"
                if days <= 30:  return "15–30 dni"
                return "ponad 30 dni"

            df["przedział"] = df["dni_na_rynku"].apply(bucket)
            bc = df["przedział"].value_counts().reindex(
                ["0–7 dni", "8–14 dni", "15–30 dni", "ponad 30 dni"], fill_value=0
            ).reset_index()
            bc.columns = ["Czas na rynku", "Liczba ogłoszeń"]
            color_map = {"0–7 dni": "#38a169", "8–14 dni": "#d69e2e",
                         "15–30 dni": "#e07b39", "ponad 30 dni": "#e53e3e"}
            fig = px.bar(bc, x="Czas na rynku", y="Liczba ogłoszeń",
                         color="Czas na rynku", color_discrete_map=color_map, text="Liczba ogłoszeń")
            fig.update_layout(showlegend=False, height=280, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("🏷️ Top marki wg wartości")
            top = stats.get("top_marki", [])
            if top:
                top_df = pd.DataFrame(top)
                fig2 = px.pie(top_df, names="marka", values="wartosc_pln", hole=0.45,
                              color_discrete_sequence=px.colors.qualitative.Pastel)
                fig2.update_layout(height=280, margin=dict(t=10, b=10))
                st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.subheader("🎯 Co zrobić żeby sprzedawać szybciej?")

        urgent_items = [i for i in items if i["priorytet"] == "wysoki"]
        medium_items = [i for i in items if i["priorytet"] == "sredni"]
        ok_items     = [i for i in items if i["priorytet"] == "niski"]

        def render_item_card(item: dict) -> None:
            css_class = {"wysoki": "urgent", "sredni": "medium", "niski": "ok"}.get(item["priorytet"], "ok")
            icon = {"wysoki": "🔴", "sredni": "🟡", "niski": "🟢"}.get(item["priorytet"], "🟢")
            rynek = item.get("rynek")
            market_html = ""
            if rynek and rynek.get("vinted_count", 0) + rynek.get("ebay_count", 0) > 0:
                v_str = f"Vinted: {rynek['vinted_median']:.0f} zł" if rynek.get("vinted_median") else ""
                e_str = f"eBay: {rynek['ebay_median']:.0f} zł" if rynek.get("ebay_median") else ""
                parts = " &nbsp;|&nbsp; ".join(p for p in [v_str, e_str] if p)
                vc = {"za wysoka": "#c53030", "lekko za wysoka": "#b7791f",
                      "prawdopodobnie za niska": "#276749", "cena ok": "#276749"}.get(rynek.get("verdict", ""), "#718096")
                market_html = (
                    f'<br><span style="font-size:12px;color:#718096;">📊 Rynek: {parts} &nbsp;'
                    f'<span style="color:{vc};font-weight:600;">({rynek.get("verdict","")})</span></span>'
                )
            tips_html = "".join(f"<li>{t}</li>" for t in item["wskazowki"])
            link_html = f'<a href="{item["url"]}" target="_blank">{item["tytul"]}</a>' if item.get("url") else item["tytul"]
            st.markdown(f"""
<div class="{css_class}">
  <strong>{icon} {link_html}</strong>
  &nbsp;|&nbsp; 💰 {item['cena']:.0f} zł
  &nbsp;|&nbsp; 📅 {item['dni_na_rynku']} dni
  &nbsp;|&nbsp; 👁 {item['wyswietlen']} wyśw.
  &nbsp;|&nbsp; ❤️ {item['polubionych']} pol.
  {market_html}
  <br><ul style="margin:6px 0 0 0">{tips_html}</ul>
</div>""", unsafe_allow_html=True)

        if urgent_items:
            with st.expander(f"🔴 Pilne — działaj TERAZ ({len(urgent_items)})", expanded=True):
                for item in urgent_items: render_item_card(item)
        if medium_items:
            with st.expander(f"🟡 Warto sprawdzić ({len(medium_items)})", expanded=True):
                for item in medium_items: render_item_card(item)
        if ok_items:
            with st.expander(f"🟢 W porządku ({len(ok_items)})", expanded=False):
                for item in ok_items: render_item_card(item)


# ================================================================== #
# TAB 2 — Add / edit listings
# ================================================================== #
with tab2:
    st.subheader("➕ Dodaj nowe ogłoszenie")
    with st.form("add_listing"):
        c1, c2 = st.columns(2)
        tytul = c1.text_input("Tytuł *", placeholder="Bluza Nike rozmiar M")
        marka = c2.text_input("Marka *", placeholder="Nike")
        c3, c4, c5 = st.columns(3)
        kategoria = c3.text_input("Kategoria", placeholder="Bluzy")
        cena = c4.number_input("Cena (zł) *", min_value=0.0, step=1.0)
        rozmiar = c5.text_input("Rozmiar", placeholder="M")
        c6, c7, c8 = st.columns(3)
        data_wyst = c6.date_input("Data wystawienia", value=date.today())
        wyswietlen = c7.number_input("Wyświetlenia", min_value=0, step=1)
        polubionych = c8.number_input("Polubienia", min_value=0, step=1)
        url = st.text_input("Link do ogłoszenia (opcjonalnie)", placeholder="https://www.vinted.pl/items/...")

        if st.form_submit_button("➕ Dodaj", use_container_width=True):
            if tytul and marka and cena > 0:
                add_listing(
                    tytul=tytul, marka=marka, kategoria=kategoria,
                    cena=cena, data_wystawienia=data_wyst.isoformat(),
                    wyswietlen=int(wyswietlen), polubionych=int(polubionych),
                    rozmiar=rozmiar, url=url,
                )
                st.cache_data.clear()
                st.success(f"Dodano: {tytul}")
                st.rerun()
            else:
                st.error("Wypełnij przynajmniej: tytuł, markę i cenę.")

    st.markdown("---")
    st.subheader("📋 Twoje ogłoszenia")

    current = load_listings()
    if current:
        for listing in current:
            c = st.columns([5, 2, 2, 2, 1])
            c[0].write(f"**{listing['tytul']}** ({listing['marka']})")
            c[1].write(f"{listing['cena']:.0f} zł")
            c[2].write(f"{listing['dni_na_rynku']} dni")
            c[3].write(f"👁 {listing['wyswietlen']} / ❤️ {listing['polubionych']}")
            if c[4].button("🗑️", key=f"del_{listing['id']}"):
                delete_listing(listing["id"])
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("Brak ogłoszeń. Dodaj pierwsze powyżej.")

    st.markdown("---")
    st.subheader("📁 Import / eksport CSV")
    st.markdown("""
Możesz też importować ogłoszenia z pliku CSV.
**Wymagane kolumny:** `tytul, marka, kategoria, cena, data_wystawienia, wyswietlen, polubionych, rozmiar, url`

Data w formacie **RRRR-MM-DD** (np. `2026-04-05`).
""")

    uploaded = st.file_uploader("Wybierz plik CSV", type=["csv"])
    if uploaded is not None:
        if st.button("📥 Importuj"):
            count = import_from_upload(uploaded.getvalue())
            st.cache_data.clear()
            st.success(f"Zaimportowano {count} ogłoszeń.")
            st.rerun()

    if current:
        with open(LISTINGS_PATH, "rb") as f:
            st.download_button(
                "⬇️ Pobierz aktualny CSV",
                data=f.read(),
                file_name="moje_ogloszenia.csv",
                mime="text/csv",
            )


# ================================================================== #
# TAB 3 — Sourcing trends
# ================================================================== #
with tab3:
    st.subheader("🛒 Co kupić — trendy i okazje")
    st.markdown("Analiza trendów Vinted + okazje na OLX + sezonowość Google Trends.")

    if st.button("🔍 Przeanalizuj teraz", use_container_width=True):
        with st.spinner("Analizuję rynek... to potrwa ok. 1 minuty"):
            try:
                sugestie = generate_sourcing_list(max_results=8)
                st.session_state["sourcing"] = sugestie
            except Exception as e:
                st.error(f"Błąd analizy: {e}")

    if "sourcing" in st.session_state:
        sugestie = st.session_state["sourcing"]
        if not sugestie:
            st.info("Brak danych. Spróbuj ponownie za chwilę.")
        else:
            for idx, s in enumerate(sugestie, 1):
                with st.container():
                    st.markdown(f"""
### {idx}. {s.get('tytul', '—')}
**Marka:** {s.get('marka', '—')} | **Kategoria:** {s.get('kategoria', '—')}
- 💰 **Max cena zakupu:** {s.get('max_cena_zakupu', 0):.0f} zł
- 📈 **Oczekiwana marża:** {s.get('oczekiwana_marza_pct', 0):.0f}%
- 🎯 **Źródło:** {s.get('zrodlo', '—')}
""")
                    if s.get("url"):
                        st.markdown(f"[Zobacz ofertę]({s['url']})")
                    st.markdown("---")


# ================================================================== #
# TAB 4 — Purchase calculator
# ================================================================== #
with tab4:
    from purchase_calc import estimate_profit
    st.subheader("🧮 Kalkulator zakupu — czy to się opłaca?")
    st.markdown("Wpisz produkt który chcesz kupić, a program sprawdzi za ile się sprzedaje.")

    c1, c2 = st.columns(2)
    calc_title = c1.text_input("Co chcesz kupić?", placeholder="Bluza Nike Tech Fleece")
    calc_brand = c2.text_input("Marka", placeholder="Nike")
    calc_price = st.number_input("Za ile możesz kupić (zł)", min_value=0.0, step=1.0)

    if st.button("📊 Oblicz opłacalność", use_container_width=True):
        if calc_title and calc_price > 0:
            with st.spinner("Sprawdzam ceny..."):
                result = estimate_profit(calc_title, calc_brand, calc_price, ebay_app_id=ebay_app_id or None)

            colors = {"opłacalne": "#38a169", "ryzykowne": "#d69e2e", "nieopłacalne": "#e53e3e"}
            vc = colors.get(result.get("verdict", ""), "#718096")

            st.markdown(f"""
### Werdykt: <span style="color:{vc};font-weight:bold;">{result.get('verdict', '—').upper()}</span>
""", unsafe_allow_html=True)

            rec = result.get("recommended_sell_price")
            profit = result.get("estimated_profit")
            margin = result.get("estimated_margin_pct")

            c1, c2, c3 = st.columns(3)
            c1.metric("Cena sprzedaży", f"{rec:.0f} zł" if rec else "—")
            c2.metric("Zysk", f"{profit:.0f} zł" if profit else "—")
            c3.metric("Marża", f"{margin:.0f}%" if margin else "—")

            c1, c2, c3 = st.columns(3)
            c1.metric("Mediana Vinted", f"{result.get('vinted_median', 0):.0f} zł" if result.get('vinted_median') else "—")
            c2.metric("Mediana eBay", f"{result.get('ebay_median', 0):.0f} zł" if result.get('ebay_median') else "—")
            c3.metric("Czas sprzedaży", result.get("days_to_sell_estimate", "—"))
        else:
            st.error("Wpisz tytuł i cenę zakupu.")


# ================================================================== #
# TAB 5 — Goal tracker
# ================================================================== #
with tab5:
    st.subheader(f"🎯 Cel miesięczny: {GOAL_LIMIT:.0f} zł (limit dział. nierejestr.)")

    m = monthly
    c1, c2, c3 = st.columns(3)
    c1.metric("Przychód ten miesiąc", f"{m['przychod']:.0f} zł", f"{m['progress_procent']:.0f}%")
    c2.metric("Do limitu", f"{GOAL_LIMIT - m['przychod']:.0f} zł")
    c3.metric("Średnio dziennie", f"{m['daily_needed']:.0f} zł")

    if m["progress_procent"] >= 90:
        st.warning(f"⚠️ Zbliżasz się do limitu! Zostało ci tylko **{GOAL_LIMIT - m['przychod']:.0f} zł** do końca miesiąca.")

    st.info(f"💡 **Porada:** {m['porada']}")

    st.markdown("---")
    st.subheader("➕ Dodaj sprzedaż")
    with st.form("add_sale"):
        c1, c2, c3 = st.columns(3)
        sale_title = c1.text_input("Co sprzedałeś?", placeholder="Bluza Nike")
        sale_price = c2.number_input("Za ile (zł)?", min_value=0.0, step=1.0)
        sale_date = c3.date_input("Kiedy?", value=date.today())
        if st.form_submit_button("💰 Zapisz sprzedaż", use_container_width=True):
            if sale_title and sale_price > 0:
                add_sale(sale_title, sale_price, sale_date.isoformat())
                st.success(f"Zapisano: {sale_title} za {sale_price:.0f} zł")
                st.rerun()

    st.markdown("---")
    st.subheader("📈 Ostatnie 6 miesięcy")
    hist = get_last_months(6)
    if hist:
        hist_df = pd.DataFrame(hist)
        fig = px.bar(hist_df, x="miesiac", y="przychod",
                     labels={"miesiac": "Miesiąc", "przychod": "Przychód (zł)"},
                     color_discrete_sequence=["#09b1ba"])
        fig.add_hline(y=GOAL_LIMIT, line_dash="dash", line_color="red",
                      annotation_text="Limit 3499 zł")
        st.plotly_chart(fig, use_container_width=True)


# ================================================================== #
# TAB 6 — Photo advisor
# ================================================================== #
with tab6:
    st.subheader("📸 Jak dobrze sfotografować produkt?")
    st.markdown("Program powie ci jak zrobić zdjęcia żeby twój produkt lepiej się sprzedawał.")

    photo_title = st.text_input("Co fotografujesz?", placeholder="Bluza Nike w kolorze szarym")

    if photo_title:
        kategoria = detect_category(photo_title)
        st.info(f"Wykryta kategoria: **{kategoria}**")

        st.markdown("### 📋 Podstawowe porady:")
        for porada in get_basic_advice(kategoria):
            st.markdown(f"- {porada}")

        if claude_api_key and st.button("🤖 Pobierz zaawansowaną poradę AI"):
            with st.spinner("Claude analizuje..."):
                try:
                    ai_advice = get_ai_advice(photo_title, claude_api_key)
                    st.markdown("### 🎯 Porady AI:")
                    st.markdown(ai_advice)
                except Exception as e:
                    st.error(f"Błąd: {e}")
