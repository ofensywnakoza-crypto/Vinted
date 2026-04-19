import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime

from vinted_client import VintedClient
from analyzer import parse_items, add_recommendations, calc_stats

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


# ------------------------------------------------------------------ #
# Config persistence
# ------------------------------------------------------------------ #

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f)


# ------------------------------------------------------------------ #
# Data fetching (cached 30 min)
# ------------------------------------------------------------------ #

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_data(cookie: str, user_id_override: int = None) -> tuple[list, dict, dict]:
    client = VintedClient()
    client.set_cookie(cookie)

    user = client.get_current_user()
    if user is None and user_id_override:
        user = client.get_user_by_id(user_id_override)

    if user is None:
        return [], {}, {}

    uid = user["id"]
    raw = client.get_all_user_items(uid)
    items = parse_items(raw)
    items = add_recommendations(items)
    stats = calc_stats(items)
    return items, stats, user


# ------------------------------------------------------------------ #
# Sidebar — setup
# ------------------------------------------------------------------ #

cfg = load_config()

with st.sidebar:
    st.title("⚙️ Ustawienia")
    st.markdown("---")

    st.markdown("### 🔑 Logowanie do Vinted")
    st.markdown("""
**Jak skopiować ciasteczko sesji:**
1. Otwórz [vinted.pl](https://www.vinted.pl) i zaloguj się
2. Wciśnij **F12** → zakładka **Application** (Chrome) lub **Storage** (Firefox)
3. Kliknij **Cookies → https://www.vinted.pl**
4. Znajdź `_vinted_fr_session` i skopiuj **Value**
""")

    cookie = st.text_input(
        "Wklej wartość ciasteczka `_vinted_fr_session`",
        value=cfg.get("cookie", ""),
        type="password",
        placeholder="eyJhb...",
    )

    user_id_override = st.number_input(
        "ID użytkownika (opcjonalnie, jako backup)",
        value=int(cfg.get("user_id", 0)),
        min_value=0,
        step=1,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Zapisz", use_container_width=True):
            save_config({
                "cookie": cookie,
                "user_id": user_id_override,
                "email_to": cfg.get("email_to", ""),
                "email_from": cfg.get("email_from", ""),
                "email_password": cfg.get("email_password", ""),
                "email_smtp_host": cfg.get("email_smtp_host", "smtp.gmail.com"),
                "email_smtp_port": cfg.get("email_smtp_port", 587),
                "email_interval_hours": cfg.get("email_interval_hours", 12),
                "email_only_if_urgent": cfg.get("email_only_if_urgent", True),
            })
            st.success("Zapisano!")
    with col2:
        if st.button("🔄 Odśwież dane", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")
    st.markdown("### 📧 Raporty na email")
    st.markdown("""
**Wymaga konta Gmail z hasłem aplikacji:**
1. Wejdź na [myaccount.google.com](https://myaccount.google.com)
2. Bezpieczeństwo → Weryfikacja dwuetapowa (włącz)
3. Szukaj „Hasła do aplikacji" → stwórz nowe
4. Wklej wygenerowane hasło poniżej
""")

    email_to = st.text_input("Twój email (odbiorca)", value=cfg.get("email_to", ""), placeholder="twoj@gmail.com")
    email_from = st.text_input("Email nadawcy (Gmail)", value=cfg.get("email_from", ""), placeholder="twoj@gmail.com")
    email_password = st.text_input("Hasło aplikacji Gmail", value=cfg.get("email_password", ""), type="password", placeholder="xxxx xxxx xxxx xxxx")
    email_interval = st.selectbox(
        "Jak często wysyłać raport?",
        options=[6, 12, 24],
        index=[6, 12, 24].index(int(cfg.get("email_interval_hours", 12))),
        format_func=lambda x: f"Co {x} godzin",
    )
    email_only_urgent = st.checkbox(
        "Wysyłaj tylko gdy są pilne ogłoszenia",
        value=cfg.get("email_only_if_urgent", True),
    )

    if st.button("💾 Zapisz ustawienia email", use_container_width=True):
        updated = load_config()
        updated.update({
            "email_to": email_to,
            "email_from": email_from,
            "email_password": email_password,
            "email_smtp_host": "smtp.gmail.com",
            "email_smtp_port": 587,
            "email_interval_hours": email_interval,
            "email_only_if_urgent": email_only_urgent,
        })
        save_config(updated)
        st.success("Ustawienia email zapisane!")

    if st.button("📨 Wyślij testowy email teraz", use_container_width=True):
        test_cfg = load_config()
        if not all([test_cfg.get("email_to"), test_cfg.get("email_from"), test_cfg.get("email_password")]):
            st.error("Najpierw zapisz ustawienia email powyżej.")
        else:
            try:
                from email_sender import send_email as _send
                cached = fetch_data(cookie, user_id_override or None)
                _send(test_cfg, cached[0], cached[1], cached[2].get("login", ""))
                st.success(f"Email wysłany na {test_cfg['email_to']}!")
            except Exception as e:
                st.error(f"Błąd: {e}")

    st.markdown("---")
    st.markdown("### ▶️ Uruchom scheduler w tle")
    st.code("python scheduler.py", language="bash")
    st.markdown("Dane są cachowane przez **30 minut**. Kliknij Odśwież aby pobrać aktualne dane z Vinted.")


# ------------------------------------------------------------------ #
# Main dashboard
# ------------------------------------------------------------------ #

st.title("👗 Vinted Tracker — Twoja sprzedaż w jednym miejscu")

if not cookie:
    st.info("👈 Wklej ciasteczko sesji w panelu po lewej, żeby zacząć.")
    st.markdown("""
### Jak to działa?
1. Podajesz swoje ciasteczko sesji z przeglądarki (instrukcja w panelu bocznym)
2. Program automatycznie pobiera Twoje ogłoszenia z Vinted
3. Analizuje każde ogłoszenie i mówi co zrobić żeby sprzedać szybciej
4. Dane odświeżają się co 30 minut
""")
    st.stop()

with st.spinner("Pobieram dane z Vinted..."):
    items, stats, user = fetch_data(cookie, user_id_override or None)

if not items and not stats:
    st.error("""
❌ Nie udało się pobrać danych. Możliwe przyczyny:
- Ciasteczko sesji wygasło — skopiuj nowe z przeglądarki
- Jesteś wylogowany z Vinted — zaloguj się i skopiuj ciasteczko ponownie
- Vinted chwilowo niedostępny — spróbuj za kilka minut
""")
    st.stop()

# ---- User greeting ------------------------------------------------- #

login = user.get("login", "Użytkowniku")
st.markdown(f"Cześć **{login}**! Oto analiza Twoich ogłoszeń. *(ostatnia aktualizacja: {datetime.now().strftime('%H:%M')})*")
st.markdown("---")

# ------------------------------------------------------------------ #
# KPI row
# ------------------------------------------------------------------ #

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("📦 Aktywnych ogłoszeń", stats.get("lacznie_ogloszen", 0))
k2.metric("🚨 Wymaga uwagi", stats.get("wymagaja_uwagi", 0), help="Ogłoszenia z wysokim priorytetem działania")
k3.metric("💰 Łączna wartość", f"{stats.get('lacznie_wartosc', 0):.0f} zł")
k4.metric("📊 Średnia cena", f"{stats.get('srednia_cena', 0):.0f} zł")
k5.metric("⏳ Śr. czas na rynku", f"{stats.get('sredni_czas_na_rynku', 0):.0f} dni")

st.markdown("---")

# ------------------------------------------------------------------ #
# Charts row
# ------------------------------------------------------------------ #

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📅 Jak długo stoją Twoje ogłoszenia?")
    df = pd.DataFrame(items)

    def bucket(days):
        if days <= 7:
            return "0–7 dni"
        if days <= 14:
            return "8–14 dni"
        if days <= 30:
            return "15–30 dni"
        return "ponad 30 dni"

    df["przedział"] = df["dni_na_rynku"].apply(bucket)
    bucket_counts = df["przedział"].value_counts().reindex(
        ["0–7 dni", "8–14 dni", "15–30 dni", "ponad 30 dni"], fill_value=0
    ).reset_index()
    bucket_counts.columns = ["Czas na rynku", "Liczba ogłoszeń"]

    color_map = {
        "0–7 dni": "#38a169",
        "8–14 dni": "#d69e2e",
        "15–30 dni": "#e07b39",
        "ponad 30 dni": "#e53e3e",
    }
    fig = px.bar(
        bucket_counts, x="Czas na rynku", y="Liczba ogłoszeń",
        color="Czas na rynku", color_discrete_map=color_map,
        text="Liczba ogłoszeń",
    )
    fig.update_layout(showlegend=False, height=300, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("🏷️ Top marki wg wartości")
    top = stats.get("top_marki", [])
    if top:
        top_df = pd.DataFrame(top)
        fig2 = px.pie(
            top_df, names="marka", values="wartosc_pln",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig2.update_layout(height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ------------------------------------------------------------------ #
# Recommendations — urgent first
# ------------------------------------------------------------------ #

st.subheader("🎯 Co zrobić żeby sprzedawać szybciej?")

urgent_items = [i for i in items if i["priorytet"] == "wysoki"]
medium_items = [i for i in items if i["priorytet"] == "sredni"]
ok_items     = [i for i in items if i["priorytet"] == "niski"]


def render_item_card(item: dict) -> None:
    css_class = {"wysoki": "urgent", "sredni": "medium", "niski": "ok"}.get(item["priorytet"], "ok")
    icon = {"wysoki": "🔴", "sredni": "🟡", "niski": "🟢"}.get(item["priorytet"], "🟢")
    days = item["dni_na_rynku"]
    views = item["wyswietlen"]
    fav = item["polubionych"]

    tips_html = "".join(f"<li>{t}</li>" for t in item["wskazowki"])
    st.markdown(f"""
<div class="{css_class}">
  <strong>{icon} <a href="{item['url']}" target="_blank">{item['tytul']}</a></strong>
  &nbsp;&nbsp;|&nbsp;&nbsp; 💰 {item['cena']:.0f} zł
  &nbsp;&nbsp;|&nbsp;&nbsp; 📅 {days} dni
  &nbsp;&nbsp;|&nbsp;&nbsp; 👁 {views} wyśw.
  &nbsp;&nbsp;|&nbsp;&nbsp; ❤️ {fav} polubionych
  <br><ul style="margin:6px 0 0 0">{tips_html}</ul>
</div>
""", unsafe_allow_html=True)


if urgent_items:
    with st.expander(f"🔴 Pilne — wymagają działania TERAZ ({len(urgent_items)} ogłoszeń)", expanded=True):
        for item in urgent_items:
            render_item_card(item)

if medium_items:
    with st.expander(f"🟡 Warto się przyjrzeć ({len(medium_items)} ogłoszeń)", expanded=True):
        for item in medium_items:
            render_item_card(item)

if ok_items:
    with st.expander(f"🟢 W porządku — czekaj spokojnie ({len(ok_items)} ogłoszeń)", expanded=False):
        for item in ok_items:
            render_item_card(item)

st.markdown("---")

# ------------------------------------------------------------------ #
# Full table
# ------------------------------------------------------------------ #

st.subheader("📋 Wszystkie ogłoszenia")

table_df = pd.DataFrame([{
    "Tytuł": i["tytul"],
    "Marka": i["marka"],
    "Cena (zł)": i["cena"],
    "Dni na rynku": i["dni_na_rynku"],
    "Wyświetlenia": i["wyswietlen"],
    "Polubienia": i["polubionych"],
    "Priorytet": i["priorytet"],
    "Link": i["url"],
} for i in items])


def highlight_priority(row):
    colors = {"wysoki": "background-color:#fff3f3", "sredni": "background-color:#fffbf0", "niski": ""}
    return [colors.get(row["Priorytet"], "")] * len(row)


st.dataframe(
    table_df.style.apply(highlight_priority, axis=1),
    use_container_width=True,
    height=400,
    column_config={"Link": st.column_config.LinkColumn("Link")},
)

# ------------------------------------------------------------------ #
# Tips footer
# ------------------------------------------------------------------ #

st.markdown("---")
st.markdown("""
### 💡 Ogólne wskazówki jak sprzedawać szybciej na Vinted
| Co zrobić | Efekt |
|---|---|
| Dodaj 5+ zdjęć w dobrym świetle | +40–60% wyświetleń |
| Odśwież ogłoszenie co 7 dni (edytuj i zapisz) | Wyżej w wynikach |
| Obniż cenę o 5–10% jeśli masz polubionych | Szybka konwersja obserwujących na kupujących |
| Opisz stan, rozmiar, markę w tytule | Więcej wyświetleń z wyszukiwarki |
| Wyceniaj o 10–15% wyżej niż chcesz dostać | Miejsce na negocjacje |
""")
