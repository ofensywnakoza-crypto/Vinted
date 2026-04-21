"""Zakladka: Ustawienia - klucze API, Telegram, testy."""
import streamlit as st

from config import (
    ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, CLAUDE_MODEL,
    MONTHLY_GOAL_PLN, MORNING_REPORT_HOUR, EVENING_REPORT_HOUR,
)
from core import database, telegram_bot


def render():
    st.markdown("## ⚙️ Ustawienia")

    tab1, tab2, tab3 = st.tabs(["🔑 API", "📱 Telegram", "📊 Baza danych"])

    with tab1:
        st.markdown("### Klucze API")
        st.caption("Edytuj plik `.env` w folderze aplikacji aby zmienic klucze.")

        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Claude API",
                "✅ skonfigurowany" if ANTHROPIC_API_KEY else "❌ brak klucza",
            )
            st.caption(f"Model: `{CLAUDE_MODEL}`")
        with col2:
            st.metric(
                "Telegram Bot",
                "✅ skonfigurowany" if TELEGRAM_BOT_TOKEN else "❌ brak tokenu",
            )

    with tab2:
        st.markdown("### Bot Telegram")

        chat_id = database.get_setting("telegram_chat_id")
        if chat_id:
            st.success(f"Chat ID zapisane: `{chat_id}`")
        else:
            st.warning("Brak chat_id. Wyslij `/start` do swojego bota na Telegramie.")
            if st.button("🔄 Sprawdz nowe wiadomosci"):
                result = telegram_bot.poll_and_register_chat()
                if result:
                    st.success(f"Zarejestrowano! Chat ID: {result}")
                    st.rerun()
                else:
                    st.info("Nie znalazlem nowych wiadomosci /start.")

        st.markdown("---")
        st.markdown(f"**Godziny raportow:** {MORNING_REPORT_HOUR:02d}:00 i {EVENING_REPORT_HOUR:02d}:00")
        st.caption("Zmien w pliku `config.py` jesli chcesz inne godziny.")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📤 Testowy poranny raport"):
                with st.spinner("Wysylam..."):
                    ok = telegram_bot.send_morning_report()
                (st.success if ok else st.error)("Wyslano!" if ok else "Nie udalo sie.")
        with col_b:
            if st.button("📤 Testowe podsumowanie"):
                with st.spinner("Wysylam..."):
                    ok = telegram_bot.send_evening_report()
                (st.success if ok else st.error)("Wyslano!" if ok else "Nie udalo sie.")

    with tab3:
        st.markdown("### Baza danych")

        all_listings = database.get_all_listings()
        st.metric("Laczna liczba ogloszen", len(all_listings))
        st.metric("Cel miesieczny", f"{MONTHLY_GOAL_PLN:.0f} zl")

        st.markdown("---")
        st.markdown("**Niebezpieczna strefa**")
        if st.button("🗑️ Usun wszystkie ogloszenia", type="secondary"):
            if st.session_state.get("confirm_delete"):
                database.delete_all_listings()
                st.success("Usunieto.")
                st.session_state.confirm_delete = False
            else:
                st.session_state.confirm_delete = True
                st.warning("Kliknij jeszcze raz aby potwierdzic usuniecie.")
