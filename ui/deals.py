"""Zakladka: Okazje do kupienia - szuka tanich przedmiotow markowych na OLX/Vinted."""
import streamlit as st

from core import database, trends


def render():
    st.markdown("## 💎 Okazje do kupienia")
    st.caption("Markowe przedmioty wystawione znacznie ponizej ceny rynkowej")

    col1, col2 = st.columns([3, 1])
    with col1:
        default_brands = ["Nike", "Adidas", "Tommy Hilfiger", "Levi's", "Carhartt", "Ralph Lauren"]
        brand_input = st.text_input(
            "Marki (oddzielone przecinkami)",
            value=", ".join(default_brands),
        )
    with col2:
        st.write("")
        st.write("")
        refresh = st.button("🔍 Szukaj okazji", type="primary")

    if refresh:
        brands = [b.strip() for b in brand_input.split(",") if b.strip()]
        with st.spinner(f"Skanuje OLX i Vinted dla {len(brands)} marek..."):
            deals = trends.find_deals(brands)
        st.success(f"Znaleziono {len(deals)} okazji")
    else:
        deals = database.get_recent_deals(limit=50)

    if not deals:
        st.info("Kliknij 'Szukaj okazji' aby rozpoczac skanowanie.")
        return

    st.markdown(f"### Top okazje ({len(deals)})")

    for deal in deals[:20]:
        with st.container():
            col_img, col_info, col_price = st.columns([1, 3, 1])
            with col_img:
                if deal.get("image_url"):
                    try:
                        st.image(deal["image_url"], width=100)
                    except Exception:
                        st.caption("🖼️")
                else:
                    st.caption("🖼️")
            with col_info:
                st.markdown(f"**{deal['title'][:60]}**")
                st.caption(f"Marka: {deal.get('brand', '?')} | Zrodlo: {deal.get('source', '?')}")
                if deal.get("url"):
                    st.markdown(f"[🔗 Zobacz ogloszenie]({deal['url']})")
            with col_price:
                st.metric(
                    "Cena",
                    f"{deal.get('price', 0):.0f} zl",
                    delta=f"+{deal.get('margin_pct', 0):.0f}% marza",
                )
            st.markdown("---")
