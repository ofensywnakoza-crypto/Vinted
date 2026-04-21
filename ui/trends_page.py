"""Zakladka: Trendy rynkowe - Google Trends + analiza marek."""
import plotly.express as px
import streamlit as st

from core import trends


def render():
    st.markdown("## 📈 Trendy rynkowe")
    st.caption("Co jest teraz na topie - dane z Google Trends")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Ranking marek (ostatni miesiac)")
    with col2:
        if st.button("🔄 Odswiez"):
            from core import database
            database.set_setting("cache_trending_brands", "")
            st.rerun()

    with st.spinner("Ladowanie trendow..."):
        data = trends.trending_brands_score(limit=15)

    if not data:
        st.warning("Nie udalo sie pobrac danych Google Trends. Sprawdz polaczenie.")
        return

    fig = px.bar(
        data,
        x="recent_interest",
        y="brand",
        orientation="h",
        text="momentum",
        labels={"recent_interest": "Zainteresowanie (ostatni tydzien)", "brand": ""},
        color="momentum",
        color_continuous_scale=["#FF6B35", "#FFD700", "#09B1BA"],
    )
    fig.update_layout(
        height=500,
        yaxis={"categoryorder": "total ascending"},
        plot_bgcolor="white",
        paper_bgcolor="#FAFAFA",
    )
    fig.update_traces(texttemplate="%{text:+.1f}", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "*Momentum* = zmiana zainteresowania w ostatnim tygodniu. "
        "Dodatnia wartosc = marka zyskuje na popularnosci."
    )

    st.markdown("### 🔍 Sprawdz wlasne slowa kluczowe")
    keywords_input = st.text_input(
        "Wpisz slowa kluczowe oddzielone przecinkami (max 5)",
        placeholder="Nike, Adidas, Patagonia",
    )
    if keywords_input and st.button("Sprawdz trend"):
        keywords = [k.strip() for k in keywords_input.split(",") if k.strip()][:5]
        with st.spinner("Pobieram dane..."):
            df = trends.google_trends(keywords, timeframe="today 3-m")
        if df.empty:
            st.warning("Brak danych dla tych slow.")
        else:
            fig = px.line(df, labels={"value": "Zainteresowanie", "date": "Data"})
            fig.update_layout(height=400, plot_bgcolor="white", paper_bgcolor="#FAFAFA")
            st.plotly_chart(fig, use_container_width=True)
