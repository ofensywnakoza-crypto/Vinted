"""Lista ogloszen - przeglad, import, edycja."""
import pandas as pd
import streamlit as st

from core import database, excel_import, rules


def render():
    st.markdown("## 📦 Moje ogloszenia")

    tab1, tab2, tab3 = st.tabs(["📋 Lista", "📥 Import Excel/CSV", "✏️ Rekomendacja AI"])

    with tab1:
        _render_list()

    with tab2:
        _render_import()

    with tab3:
        _render_ai_analysis()


def _render_list():
    all_listings = database.get_all_listings()
    if not all_listings:
        st.info("Brak ogloszen w bazie. Zaimportuj plik Excel w zakladce 'Import'.")
        return

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["Wszystkie", "Wystawiony", "Sprzedany", "Do wyrzucenia"],
        )
    with col2:
        brand_filter = st.selectbox(
            "Marka",
            ["Wszystkie"] + sorted({l.get("brand") or "" for l in all_listings if l.get("brand")}),
        )
    with col3:
        search = st.text_input("Szukaj", placeholder="tytul...")

    filtered = all_listings
    if status_filter != "Wszystkie":
        filtered = [l for l in filtered if l.get("status") == status_filter]
    if brand_filter != "Wszystkie":
        filtered = [l for l in filtered if l.get("brand") == brand_filter]
    if search:
        s = search.lower()
        filtered = [l for l in filtered if s in l.get("title", "").lower()]

    st.caption(f"Wyswietlono: {len(filtered)} z {len(all_listings)}")

    df = pd.DataFrame(filtered)
    if df.empty:
        st.info("Brak wynikow.")
        return

    display_cols = {
        "nr": "Nr",
        "title": "Tytul",
        "brand": "Marka",
        "category": "Kategoria",
        "size": "Rozmiar",
        "list_price": "Cena",
        "sold_price": "Sprzedana za",
        "current_views": "Wyswietlenia",
        "current_likes": "Polubienia",
        "status": "Status",
        "listed_date": "Data wystawienia",
        "sold_date": "Data sprzedazy",
    }
    df_show = df[[c for c in display_cols if c in df.columns]].rename(columns=display_cols)

    st.dataframe(df_show, use_container_width=True, hide_index=True, height=500)


def _render_import():
    st.markdown("### Import ogloszen z pliku Excel lub CSV")
    st.caption("Aplikacja sama rozpozna kolumny. Powtorny import nadpisuje istniejace wpisy (po numerze).")

    uploaded = st.file_uploader(
        "Wybierz plik .xlsx lub .csv",
        type=["xlsx", "xls", "csv"],
    )
    if uploaded is None:
        return

    if st.button("📥 Zaimportuj", type="primary"):
        with st.spinner("Importuje..."):
            try:
                result = excel_import.import_excel(uploaded)
                st.success(
                    f"✅ Zaimportowano {result['imported']} ogloszen "
                    f"(pominieto {result['skipped']})"
                )
                if result["errors"]:
                    with st.expander(f"Bledy ({len(result['errors'])})"):
                        for e in result["errors"][:20]:
                            st.text(e)
                with st.expander("Dopasowane kolumny"):
                    st.json(result["columns_matched"])
            except Exception as exc:
                st.error(f"Blad importu: {exc}")


def _render_ai_analysis():
    st.markdown("### Rekomendacje AI dla poszczegolnych ogloszen")
    listings = database.get_active_listings()
    if not listings:
        st.info("Brak aktywnych ogloszen.")
        return

    titles = {f"{l['title']} ({l.get('list_price', 0):.0f} zl)": l["id"] for l in listings}
    choice = st.selectbox("Wybierz ogloszenie", list(titles.keys()))
    listing_id = titles[choice]
    listing = database.get_listing(listing_id)

    rec = rules.analyze_listing(listing)
    emoji = rules.EMOJIS.get(rec.action, "•")
    label = rules.LABELS.get(rec.action, rec.action)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Rekomendacja", f"{emoji} {label}")
        st.metric("Dni na rynku", rec.days_on_market)
        st.metric("Wyswietlenia", rec.views)
        st.metric("Polubienia", rec.likes)

    with col2:
        st.markdown("**Uzasadnienie:**")
        st.info(rec.reason)

        if rec.suggested_price:
            st.markdown(f"**Sugerowana cena:** {rec.suggested_price:.2f} zl")

        if st.button("🤖 Zapytaj AI o szczegolowa analize"):
            from core import ai_assistant
            try:
                with st.spinner("Claude analizuje..."):
                    listing_with_days = {**listing, "days_on_market": rec.days_on_market}
                    analysis = ai_assistant.analyze_listing_performance(listing_with_days)
                    st.markdown(analysis)
            except Exception as exc:
                st.error(f"Blad AI: {exc}")
