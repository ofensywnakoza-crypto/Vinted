"""Zakladka: Akcje do wykonania - pelna lista z rekomendacjami."""
import streamlit as st

from core import database, rules


def render():
    st.markdown("## 🎯 Akcje do wykonania")
    st.caption("Lista ogloszen wymagajacych Twojej uwagi")

    recs = rules.get_recommendations(only_actionable=True)

    col1, col2, col3, col4 = st.columns(4)
    by_action: dict[str, int] = {}
    for r in recs:
        by_action[r.action] = by_action.get(r.action, 0) + 1

    col1.metric("🔄 Usun i wystaw", by_action.get("RELIST", 0))
    col2.metric("⬇️ Obniz cene", by_action.get("LOWER_PRICE", 0))
    col3.metric("✨ Odswiez", by_action.get("REFRESH", 0))
    col4.metric("🚀 Promuj", by_action.get("BOOST", 0))

    st.markdown("---")

    if not recs:
        st.success("🎉 Brak pilnych akcji. Wszystkie ogloszenia wygladaja dobrze.")
        return

    filter_action = st.selectbox(
        "Filtruj po akcji",
        ["Wszystkie"] + list({r.action for r in recs}),
    )

    filtered = recs if filter_action == "Wszystkie" else [r for r in recs if r.action == filter_action]

    for r in filtered:
        emoji = rules.EMOJIS.get(r.action, "•")
        label = rules.LABELS.get(r.action, r.action)
        price = f"{r.current_price:.0f} zl" if r.current_price else "?"
        suggested = f" → **{r.suggested_price:.0f} zl**" if r.suggested_price else ""

        with st.container():
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"### {emoji} {r.title}")
                st.caption(
                    f"Cena: {price}{suggested} | "
                    f"Dni: {r.days_on_market} | "
                    f"Wyswietlenia: {r.views} | "
                    f"Polubienia: {r.likes}"
                )
                st.info(r.reason)
            with col_b:
                st.markdown(f"**Akcja:** {label}")
                if st.button("✅ Oznacz jako wykonane", key=f"done_{r.listing_id}_{r.action}"):
                    database.log_action(r.listing_id, r.action, "Wykonane recznie")
                    st.success("Zapisano.")
            st.markdown("---")
