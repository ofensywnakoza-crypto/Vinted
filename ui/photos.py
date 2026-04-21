"""Strefa fotografii - upload zdjecia -> Claude AI."""
import streamlit as st

from core import ai_assistant


def render():
    st.markdown("## 📸 Strefa fotografii")
    st.caption("Wgraj zdjecie przedmiotu - Claude AI doradzi i wygeneruje opis")

    tab1, tab2 = st.tabs(["🎯 Porady fotograficzne", "✍️ Wygeneruj tytul i opis"])

    with tab1:
        _render_advice()

    with tab2:
        _render_generate()


def _render_advice():
    st.markdown("### Porady dla Twojego zdjecia")
    uploaded = st.file_uploader(
        "Wgraj zdjecie",
        type=["jpg", "jpeg", "png", "webp"],
        key="advice_upload",
    )
    if uploaded is None:
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        st.image(uploaded, use_container_width=True)

    with col2:
        if st.button("🤖 Analizuj zdjecie", type="primary", key="analyze_photo"):
            try:
                with st.spinner("Claude ocenia zdjecie..."):
                    advice = ai_assistant.analyze_photo(uploaded.getvalue())
                st.markdown(advice)
            except Exception as exc:
                st.error(f"Blad: {exc}")


def _render_generate():
    st.markdown("### Wygeneruj tytul i opis wg Twojego szablonu")

    uploaded = st.file_uploader(
        "Wgraj zdjecie",
        type=["jpg", "jpeg", "png", "webp"],
        key="generate_upload",
    )

    col1, col2 = st.columns(2)
    with col1:
        brand = st.text_input("Marka", placeholder="np. Nike")
        category = st.text_input("Kategoria", placeholder="np. t-shirt")
        size = st.text_input("Rozmiar", placeholder="np. M")
    with col2:
        color = st.text_input("Kolor", placeholder="np. czarny")
        condition = st.selectbox(
            "Stan",
            ["nowy z metka", "bardzo dobry", "dobry", "zadowalajacy"],
        )
        notes = st.text_input("Dodatkowe info", placeholder="opcjonalnie")

    if uploaded is not None:
        st.image(uploaded, width=300)

    if st.button("✍️ Wygeneruj ogloszenie", type="primary", disabled=uploaded is None):
        try:
            with st.spinner("Claude pisze ogloszenie..."):
                result = ai_assistant.generate_listing_content(
                    image=uploaded.getvalue(),
                    brand=brand, category=category, size=size, color=color,
                    condition=condition, notes=notes,
                )

            st.success("Gotowe!")

            st.markdown("**Tytul:**")
            st.code(result["title"], language=None)

            st.markdown("**Hashtagi:**")
            st.code(result["hashtags"], language=None)

            st.markdown("**Opis:**")
            st.code(result["description"], language=None)

            if result.get("suggested_price"):
                st.metric("Sugerowana cena", f"{result['suggested_price']:.2f} zl")

            with st.expander("Pelna odpowiedz AI"):
                st.text(result["raw"])

        except Exception as exc:
            st.error(f"Blad: {exc}")
