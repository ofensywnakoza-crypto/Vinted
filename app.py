import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime

from vinted_client import VintedClient
from analyzer import parse_items, add_recommendations, calc_stats
from market_data import enrich_with_market_data
from goal_tracker import add_sale, get_monthly_summary, get_last_months, GOAL_LIMIT
from trends import generate_sourcing_list
from photo_advisor import get_basic_advice, get_ai_advice, detect_category
from price_history import record_snapshot, get_price_changes, get_all_history
from cookie_server import read_synced_cookie

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


def check_cookie_update(cfg: dict) -> tuple[dict, bool]:
    """If Chrome extension synced a new cookie, update cfg and persist. Returns (cfg, updated)."""
    synced = read_synced_cookie()
    if synced and synced.get("cookie") and synced["cookie"] != cfg.get("cookie"):
        cfg = dict(cfg)
        cfg["cookie"] = synced["cookie"]
        save_config(cfg)
        return cfg, True
    return cfg, False


# ------------------------------------------------------------------ #
# Data fetching (cached 30 min)
# ------------------------------------------------------------------ #

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_data(cookie: str, ebay_app_id: str = "", user_id_override: int = None) -> tuple[list, dict, dict]:
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
    items = add_recommendations(items)          # first pass — behaviour-based
    items = enrich_with_market_data(items, ebay_app_id or None)
    items = add_recommendations(items)          # second pass — now includes market tips
    record_snapshot(items)
    stats = calc_stats(items)
    return items, stats, user


# ------------------------------------------------------------------ #
# Sidebar — setup
# ------------------------------------------------------------------ #

cfg = load_config()
cfg, _cookie_auto_updated = check_cookie_update(cfg)

with st.sidebar:
    st.title("⚙️ Ustawienia")
    st.markdown("---")

    st.markdown("### 🔑 Logowanie do Vinted")
    st.markdown("""
**Metoda 1 — pełny ciąg ciasteczek (zalecana):**
1. Otwórz [vinted.pl](https://www.vinted.pl) i zaloguj się
2. Wciśnij **F12** → zakładka **Network** (Sieć)
3. Odśwież stronę (F5), kliknij pierwsze żądanie do `vinted.pl`
4. W zakładce **Headers** znajdź `Cookie:` w sekcji Request Headers
5. Skopiuj **całą wartość** (długi ciąg: `foo=bar; _vinted_fr_session=eyJ...`)

**Metoda 2 — samo _vinted_fr_session:**
1. F12 → **Application** → **Cookies → https://www.vinted.pl**
2. Znajdź `_vinted_fr_session` i skopiuj **Value**
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

    st.markdown("---")
    st.markdown("### 🛒 Dane rynkowe eBay (opcjonalne)")
    st.markdown("""
Dzięki temu program porówna Twoje ceny z tym **za ile rzeczy faktycznie się sprzedają** na eBay.

**Jak uzyskać darmowy klucz eBay:**
1. Wejdź na **developer.ebay.com**
2. Zarejestruj się (bezpłatne)
3. Kliknij **Get an Application Key**
4. Skopiuj **App ID (Client ID)**
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
        st.info("Bez klucza eBay program korzysta tylko z danych Vinted")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Zapisz", use_container_width=True):
            save_config({
                "cookie": cookie,
                "user_id": user_id_override,
                "ebay_app_id": ebay_app_id,
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
                cached = fetch_data(cookie, ebay_app_id, user_id_override or None)
                _send(test_cfg, cached[0], cached[1], cached[2].get("login", ""))
                st.success(f"Email wysłany na {test_cfg['email_to']}!")
            except Exception as e:
                st.error(f"Błąd: {e}")

    st.markdown("---")
    st.markdown("### 💬 Telegram — alerty")
    st.markdown("""
**Jak ustawić bota Telegram:**
1. Napisz do [@BotFather](https://t.me/BotFather) na Telegramie
2. Wyślij `/newbot` i podaj nazwę
3. Skopiuj token (format: `1234567890:ABCdef...`)
4. Napisz cokolwiek do swojego bota
5. Otwórz: `https://api.telegram.org/botTWÓJ_TOKEN/getUpdates`
6. Znajdź `"chat":{"id":LICZBA}` — to Twój Chat ID
""")
    telegram_token = st.text_input(
        "Token bota", value=cfg.get("telegram_token", ""), type="password",
        placeholder="1234567890:ABCdef...",
    )
    telegram_chat_id = st.text_input(
        "Chat ID", value=cfg.get("telegram_chat_id", ""), placeholder="123456789",
    )
    if telegram_token and telegram_chat_id:
        if st.button("🔔 Wyślij testowy alert Telegram", use_container_width=True):
            from telegram_bot import send_telegram_message
            ok = send_telegram_message(
                telegram_token, telegram_chat_id,
                "✅ <b>Vinted Tracker</b> — połączenie działa!"
            )
            if ok:
                st.success("Alert wysłany! Sprawdź Telegram.")
            else:
                st.error("Błąd. Sprawdź token i Chat ID.")

    if st.button("💾 Zapisz ustawienia Telegram", use_container_width=True):
        updated = load_config()
        updated.update({
            "telegram_token": telegram_token,
            "telegram_chat_id": telegram_chat_id,
        })
        save_config(updated)
        st.success("Zapisano!")

    st.markdown("---")
    st.markdown("### 🤖 Claude AI (poradnik fotograficzny)")
    st.markdown("""
Opcjonalnie — ulepsza poradnik fotograficzny o spersonalizowane porady AI.
**Koszt: ~0,03 zł za jedno zapytanie.**

Jak uzyskać klucz:
1. Wejdź na **console.anthropic.com**
2. Zarejestruj się → API Keys → Create Key
3. Skopiuj klucz (zaczyna się od `sk-ant-...`)
""")
    claude_api_key = st.text_input(
        "Klucz Claude API (opcjonalnie)",
        value=cfg.get("claude_api_key", ""),
        type="password",
        placeholder="sk-ant-...",
    )
    if claude_api_key:
        st.success("Claude AI aktywny — poradnik fotograficzny będzie używał AI")

    if st.button("💾 Zapisz klucz Claude", use_container_width=True):
        updated = load_config()
        updated["claude_api_key"] = claude_api_key
        save_config(updated)
        st.success("Zapisano!")

    st.markdown("---")
    st.markdown("### 🔌 Auto-sync ciasteczka (rozszerzenie Chrome)")
    synced = read_synced_cookie()
    if synced:
        st.success(
            f"Rozszerzenie aktywne — ostatnia sync: **{synced.get('updated_at', '?')}**"
        )
        if _cookie_auto_updated:
            st.info("Ciasteczko zostało właśnie zaktualizowane automatycznie.")
    else:
        st.info("Brak danych z rozszerzenia Chrome.")
    st.markdown("""
**Jak zainstalować rozszerzenie:**
1. Otwórz Chrome → `chrome://extensions/`
2. Włącz **Tryb deweloperski** (prawy górny róg)
3. Kliknij **Wczytaj rozpakowane** i wskaż folder `chrome_extension/`
4. Uruchom tracker: `python scheduler.py` (serwer cookie startuje automatycznie)
5. Wejdź na [vinted.pl](https://www.vinted.pl) — ciasteczko zsynchronizuje się samo
""")

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

spinner_msg = "Pobieram dane z Vinted i porównuję z rynkiem..." if ebay_app_id else "Pobieram dane z Vinted..."
with st.spinner(spinner_msg):
    items, stats, user = fetch_data(cookie, ebay_app_id, user_id_override or None)

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
monthly = get_monthly_summary()
st.markdown(
    f"Cześć **{login}**! &nbsp;&nbsp; "
    f"🎯 Ten miesiąc: **{monthly['przychod']:.0f} zł** / {GOAL_LIMIT:.0f} zł &nbsp;&nbsp; "
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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📦 Moje ogłoszenia",
    "🛒 Co kupić — trendy i okazje",
    "🧮 Kalkulator zakupu",
    "🎯 Cel miesięczny",
    "📸 Jak sfotografować?",
])


# ================================================================== #
# TAB 1 — My listings
# ================================================================== #
with tab1:

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📦 Aktywnych ogłoszeń", stats.get("lacznie_ogloszen", 0))
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
        st.markdown(f"""
<div class="{css_class}">
  <strong>{icon} <a href="{item['url']}" target="_blank">{item['tytul']}</a></strong>
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

    st.markdown("---")
    st.subheader("📋 Wszystkie ogłoszenia")

    def _market_summary(item: dict) -> str:
        r = item.get("rynek")
        if not r: return "—"
        parts = []
        if r.get("vinted_median"): parts.append(f"V: {r['vinted_median']:.0f} zł")
        if r.get("ebay_median"):   parts.append(f"eBay: {r['ebay_median']:.0f} zł")
        verdict = r.get("verdict", "")
        suffix = f" ({verdict})" if verdict and verdict != "brak danych rynkowych" else ""
        return (", ".join(parts) + suffix) if parts else "brak danych"

    table_df = pd.DataFrame([{
        "Tytuł": i["tytul"], "Marka": i["marka"], "Cena (zł)": i["cena"],
        "Rynek": _market_summary(i), "Dni na rynku": i["dni_na_rynku"],
        "Wyświetlenia": i["wyswietlen"], "Polubienia": i["polubionych"],
        "Priorytet": i["priorytet"], "Link": i["url"],
    } for i in items])

    def highlight_priority(row):
        colors = {"wysoki": "background-color:#fff3f3", "sredni": "background-color:#fffbf0", "niski": ""}
        return [colors.get(row["Priorytet"], "")] * len(row)

    st.dataframe(
        table_df.style.apply(highlight_priority, axis=1),
        use_container_width=True, height=400,
        column_config={"Link": st.column_config.LinkColumn("Link")},
    )

    # ---- Price history -------------------------------------------- #
    st.markdown("---")
    st.subheader("📈 Historia zmian cen")

    all_history = get_all_history()
    changed_items = []
    for item in items:
        changes = get_price_changes(item["id"])
        if changes and changes["liczba_snapshotow"] >= 2:
            changed_items.append(changes)

    if not changed_items:
        st.info(
            "Historia cen buduje się automatycznie przy każdej wizycie. "
            "Wróć jutro żeby zobaczyć zmiany. 📊"
        )
    else:
        changed_items.sort(key=lambda x: abs(x["zmiana_pln"]), reverse=True)
        for ch in changed_items[:10]:
            arrow = "📉" if ch["zmiana_pln"] < 0 else ("📈" if ch["zmiana_pln"] > 0 else "➡️")
            color = "#f0fff4" if ch["zmiana_pln"] < 0 else ("#fff5f5" if ch["zmiana_pln"] > 0 else "#f8f9fa")
            st.markdown(f"""
<div style="background:{color};padding:10px 14px;border-radius:6px;margin:6px 0;">
  {arrow} <strong><a href="{ch['url']}" target="_blank">{ch['tytul'][:50]}</a></strong><br>
  <span style="color:#718096;font-size:13px;">
    Pierwsza cena: {ch['cena_pierwsza']:.0f} zł → Obecna: {ch['cena_obecna']:.0f} zł
    ({ch['zmiana_pln']:+.0f} zł / {ch['zmiana_procent']:+.0f}%) ·
    obserwowane {ch['dni_obserwacji']} dni ({ch['liczba_snapshotow']} pomiarów)
  </span>
</div>""", unsafe_allow_html=True)

            if ch["liczba_snapshotow"] > 2:
                hist_df = pd.DataFrame(ch["historia"])
                hist_df["data"] = pd.to_datetime(hist_df["data"])
                fig_h = px.line(hist_df, x="data", y="cena", markers=True, height=120,
                                color_discrete_sequence=["#667eea"])
                fig_h.update_layout(margin=dict(t=5, b=5, l=5, r=5), showlegend=False,
                                    xaxis_title="", yaxis_title="zł",
                                    xaxis=dict(showgrid=False))
                st.plotly_chart(fig_h, use_container_width=True)


# ================================================================== #
# TAB 2 — Trends & sourcing
# ================================================================== #
with tab2:
    st.subheader("🛒 Co kupić żeby szybko zarobić?")
    st.markdown("Program analizuje co aktualnie sprzedaje się najlepiej na Vinted i gdzie można to kupić tanio.")

    monthly_remaining = GOAL_LIMIT - monthly["przychod"]

    if st.button("🔍 Analizuj trendy i znajdź okazje", type="primary", use_container_width=True):
        with st.spinner("Analizuję trendy Vinted, szukam okazji na OLX i sprawdzam Google Trends... (może zająć 1–2 min)"):
            sourcing = generate_sourcing_list(monthly_remaining=monthly_remaining)
            st.session_state["sourcing"] = sourcing

    sourcing = st.session_state.get("sourcing")

    if sourcing:
        st.markdown(f"*Wygenerowano: {sourcing['data_generowania']}*")
        st.markdown("---")

        # Shopping list
        lista = sourcing.get("lista_zakupow", [])
        if lista:
            st.subheader("📋 Lista zakupów na ten tydzień")
            st.markdown(f"Możesz jeszcze zarobić **{monthly_remaining:.0f} zł** w tym miesiącu.")
            for i, item in enumerate(lista, 1):
                marza = item["marza_procent"]
                color = "#f0fff4" if marza >= 80 else "#fffff0"
                border = "#38a169" if marza >= 80 else "#d69e2e"
                offers_html = ""
                for o in item.get("przykladowe_oferty", []):
                    offers_html += f'&nbsp;&nbsp;→ <a href="{o["url"]}" target="_blank">{o["tytul"][:40]}</a> ({o["cena"]:.0f} zł)<br>'

                st.markdown(f"""
<div style="background:{color};border-left:4px solid {border};padding:12px 16px;border-radius:4px;margin:8px 0;">
  <strong>#{i} {item['co_kupic']}</strong> &nbsp;&nbsp;
  <span style="color:#718096;">Marki: {item['marki']}</span><br>
  💰 Kup za max <strong>{item['max_cena_zakupu']:.0f} zł</strong> &nbsp;→&nbsp;
  Sprzedaj za <strong>{item['oczekiwana_sprzedaz']:.0f} zł</strong> &nbsp;
  <span style="color:{border};font-weight:700;">(marża {marza:.0f}%)</span><br>
  📦 Ile sztuk: {item['ile_sztuk']} &nbsp;|&nbsp; 🔍 Gdzie: {item['gdzie_szukac']}<br>
  {f'<small style="color:#718096;">Przykłady na OLX:<br>{offers_html}</small>' if offers_html else ''}
</div>""", unsafe_allow_html=True)
        else:
            st.info("Nie znaleziono okazji arbitrażowych w tym momencie. Spróbuj ponownie za kilka godzin.")

        st.markdown("---")

        # Trending categories
        trending = sourcing.get("trending_kategorie", [])
        if trending:
            st.subheader("📈 Najgorętsze kategorie na Vinted teraz")
            trend_df = pd.DataFrame(trending[:8])
            fig = px.bar(
                trend_df, x="kategoria", y="popularnosc",
                color="popularnosc", color_continuous_scale="Greens",
                text="mediana_ceny",
            )
            fig.update_traces(texttemplate="%{text:.0f} zł")
            fig.update_layout(height=300, showlegend=False,
                              xaxis_title="", yaxis_title="Popularność",
                              margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)

        # Seasonal trends
        seasonal = sourcing.get("trendy_sezonowe", [])
        if seasonal and not (len(seasonal) == 1 and "info" in seasonal[0]):
            st.subheader("🗓️ Trendy sezonowe (Google Trends Polska)")
            for s in seasonal:
                icon = "📈" if s["trend"] == "rosnący" else ("📉" if s["trend"] == "spadający" else "➡️")
                color = "#f0fff4" if s["trend"] == "rosnący" else ("#fff5f5" if s["trend"] == "spadający" else "#f8f9fa")
                st.markdown(f"""
<div style="background:{color};padding:8px 12px;border-radius:4px;margin:4px 0;">
  {icon} <strong>{s['kategoria']}</strong> &nbsp;·&nbsp;
  Zmiana: {s['zmiana_procent']:+.0f}% &nbsp;·&nbsp;
  <em>{s['rekomendacja']}</em>
</div>""", unsafe_allow_html=True)
    else:
        st.info("Kliknij przycisk powyżej żeby wygenerować analizę. Pierwsze uruchomienie trwa ok. 1–2 minut.")


# ================================================================== #
# TAB 3 — Purchase calculator
# ================================================================== #
with tab3:
    st.subheader("🧮 Kalkulator opłacalności zakupu")
    st.markdown(
        "Sprawdź czy warto kupić towar **zanim** go kupisz. "
        "Wpisz co chcesz kupić i za ile — program sprawdzi ceny rynkowe."
    )

    client_calc = VintedClient()
    if cookie:
        client_calc.set_cookie(cookie)

    col1, col2 = st.columns([3, 1])
    with col1:
        calc_title = st.text_input(
            "Co chcesz kupić?",
            placeholder="np. kurtka zimowa Reserved rozmiar M",
            key="calc_title",
        )
    with col2:
        calc_price = st.number_input(
            "Max cena zakupu (zł)",
            min_value=1.0, max_value=5000.0, value=30.0, step=5.0,
            key="calc_price",
        )

    if st.button("🔍 Sprawdź opłacalność", type="primary",
                 use_container_width=True, disabled=not calc_title):
        with st.spinner("Szukam cen na Vinted i eBay..."):
            from purchase_calc import estimate_profit
            result = estimate_profit(
                title=calc_title,
                brand_name="",
                max_buy_price=calc_price,
                vinted_client=client_calc,
                ebay_app_id=cfg.get("ebay_app_id"),
            )
            st.session_state["calc_result"] = result

    calc_result = st.session_state.get("calc_result")
    if calc_result:
        if calc_result.get("error"):
            st.error(f"Błąd: {calc_result['error']}")
        else:
            verdict_styles = {
                "opłacalne":    ("#f0fff4", "#38a169", "✅"),
                "ryzykowne":    ("#fffbf0", "#d69e2e", "⚠️"),
                "nieopłacalne": ("#fff5f5", "#e53e3e", "❌"),
                "brak danych":  ("#f8f9fa", "#718096", "❓"),
            }
            v = calc_result.get("verdict", "brak danych")
            bg, border, icon = verdict_styles.get(v, ("#f8f9fa", "#718096", "❓"))
            margin   = calc_result.get("estimated_margin_pct") or 0
            profit   = calc_result.get("estimated_profit") or 0
            sell_p   = calc_result.get("recommended_sell_price") or 0

            st.markdown(f"""
<div style="background:{bg};border-left:5px solid {border};padding:20px;border-radius:8px;margin:16px 0;">
  <h3 style="margin:0;color:{border};">{icon} {v.upper()} — marża {margin:.0f}%</h3>
  <p style="margin:8px 0 0;">
    Kup za max <strong>{calc_price:.0f} zł</strong> →
    Sprzedaj za ok. <strong>{sell_p:.0f} zł</strong> →
    Zysk: <strong>{profit:.0f} zł</strong>
  </p>
</div>""", unsafe_allow_html=True)

            ca, cb, cc = st.columns(3)
            ca.metric(
                "Vinted — mediana cen",
                f"{calc_result['vinted_median']:.0f} zł" if calc_result.get("vinted_median") else "brak danych",
                f"{calc_result.get('vinted_active_count', 0)} ofert aktywnych",
            )
            cb.metric(
                "eBay — mediana cen",
                f"{calc_result['ebay_median']:.0f} zł" if calc_result.get("ebay_median") else "brak danych",
                f"{calc_result.get('ebay_sold_count', 0)} sprzedanych",
            )
            cc.metric("Szacowany czas sprzedaży", calc_result.get("days_to_sell_estimate", "—"))

            if margin < 30:
                st.warning("💡 Ta transakcja prawdopodobnie nie jest opłacalna. Szukaj tańszego źródła.")
            elif margin < 60:
                better = round(calc_price * 0.7, 0)
                st.info(f"💡 Marża umiarkowana. Za {better:.0f} zł byłoby bardzo opłacalne.")
            else:
                max_pay = round(sell_p * 0.5, 0)
                st.success(f"💡 Świetna okazja! Możesz zapłacić nawet {max_pay:.0f} zł i nadal dobrze zarobić.")


# ================================================================== #
# TAB 4 — Monthly goal
# ================================================================== #
with tab4:
    st.subheader("🎯 Cel miesięczny — 3 499 zł")
    st.markdown("Śledź przychody żeby nie przekroczyć limitu działalności nierejestrowanej.")

    # Big progress display
    revenue = monthly["przychod"]
    remaining = monthly["pozostalo_do_celu"]
    pct = monthly["progress_procent"]

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Przychód w tym miesiącu", f"{revenue:.0f} zł")
    c2.metric("📊 Postęp", f"{pct:.1f}%")
    c3.metric("🏁 Pozostało do limitu", f"{remaining:.0f} zł")

    bar_color = "#e53e3e" if pct >= 90 else ("#d69e2e" if pct >= 70 else "#38a169")
    st.markdown(f"""
<div style="background:#edf2f7;border-radius:10px;height:24px;margin:12px 0;">
  <div style="background:{bar_color};width:{min(pct,100)}%;height:24px;border-radius:10px;
              display:flex;align-items:center;justify-content:center;color:white;font-weight:700;font-size:13px;">
    {pct:.1f}%
  </div>
</div>""", unsafe_allow_html=True)

    status_colors = {"osiagniety": "#fff5f5", "uwaga": "#fffbf0", "dobry": "#f0fff4", "niski": "#f8f9fa"}
    st.markdown(f"""
<div style="background:{status_colors.get(monthly['status'],'#f8f9fa')};
            padding:12px 16px;border-radius:8px;margin:8px 0;">
  💡 {monthly['porada']}
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Add sale form
    st.subheader("➕ Dodaj sprzedaż")
    col_a, col_b, col_c = st.columns([2, 3, 1])
    with col_a:
        sale_amount = st.number_input("Kwota (zł)", min_value=1.0, max_value=2000.0,
                                       value=50.0, step=5.0)
    with col_b:
        sale_item = st.text_input("Co sprzedałeś? (opcjonalnie)", placeholder="Kurtka Zara")
    with col_c:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ Dodaj", use_container_width=True):
            add_sale(sale_amount, sale_item)
            st.success(f"Dodano {sale_amount:.0f} zł!")
            st.rerun()

    st.markdown("---")

    # Last sales
    if monthly["ostatnie_sprzedaze"]:
        st.subheader("🕐 Ostatnie sprzedaże")
        sales_df = pd.DataFrame(monthly["ostatnie_sprzedaze"])
        sales_df.columns = ["Data", "Kwota (zł)", "Przedmiot"]
        st.dataframe(sales_df, use_container_width=True, hide_index=True)

    # History chart
    history = get_last_months(4)
    if any(m["przychod"] > 0 for m in history):
        st.markdown("---")
        st.subheader("📊 Historia przychodów")
        hist_df = pd.DataFrame(history)
        hist_df.columns = ["Miesiąc", "Przychód (zł)", "Liczba sprzedaży"]
        fig = px.bar(hist_df, x="Miesiąc", y="Przychód (zł)",
                     text="Przychód (zł)", color_discrete_sequence=["#667eea"])
        fig.add_hline(y=GOAL_LIMIT, line_dash="dash", line_color="#e53e3e",
                      annotation_text=f"Limit {GOAL_LIMIT:.0f} zł")
        fig.update_traces(texttemplate="%{text:.0f} zł")
        fig.update_layout(height=300, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)


# ================================================================== #
# TAB 5 — Photography advisor
# ================================================================== #
with tab5:
    st.subheader("📸 Jak najlepiej sfotografować produkt?")
    st.markdown("Opisz produkt który chcesz wystawić — program powie Ci dokładnie jak go sfotografować.")

    col_desc, col_brand = st.columns([3, 1])
    with col_desc:
        product_desc = st.text_input(
            "Opisz produkt",
            placeholder="np. czarna kurtka Reserved rozmiar M, stan bardzo dobry",
        )
    with col_brand:
        use_ai = st.toggle(
            "🤖 Użyj Claude AI",
            value=bool(cfg.get("claude_api_key")),
            help="Spersonalizowana porada AI (~0,03 zł). Wymaga klucza w ustawieniach.",
            disabled=not cfg.get("claude_api_key"),
        )

    generate_btn = st.button("📋 Generuj poradnik fotograficzny", type="primary",
                              use_container_width=True, disabled=not product_desc)

    if generate_btn and product_desc:
        with st.spinner("Przygotowuję poradnik..."):
            if use_ai and cfg.get("claude_api_key"):
                advice = get_ai_advice(product_desc, cfg["claude_api_key"])
            else:
                advice = get_basic_advice(product_desc)

        if advice.get("tryb") == "ai_error":
            st.error(f"Błąd Claude AI: {advice.get('error')} — wyświetlam wersję podstawową.")
            advice = get_basic_advice(product_desc)

        st.markdown("---")

        # Market context banner
        if advice.get("kontekst_rynkowy"):
            st.info(f"💰 {advice['kontekst_rynkowy']} {advice.get('porada_cenowa','')}")

        # ---- AI mode ----
        if advice.get("tryb") == "ai":
            cost = advice.get("koszt_pln", 0)
            st.markdown(f"*🤖 Wygenerowano przez Claude AI · koszt: {cost:.3f} zł*")
            st.markdown("---")
            st.markdown(advice["ai_porada"])

        # ---- Basic mode ----
        else:
            cat_labels = {
                "kurtka": "Kurtka", "plaszcz": "Płaszcz", "sukienka": "Sukienka",
                "bluza": "Bluza / Sweter", "spodnie": "Spodnie / Jeansy",
                "buty": "Buty", "torebka": "Torebka", "marynarka": "Marynarka",
                "odziez": "Odzież",
            }
            cat_label = cat_labels.get(advice["kategoria"], advice["kategoria"].capitalize())
            st.markdown(f"**Wykryta kategoria:** {cat_label} &nbsp;·&nbsp; "
                        f"**Minimum zdjęć:** {advice['min_zdjec']}")

            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown(f"🎨 **Tło:** {advice['tlo']}")
                st.markdown(f"🌤️ **Światło:** {advice['swiatlo']}")
                st.markdown(f"📐 **Orientacja:** {advice['orientacja']}")
                st.markdown(f"👔 **Styl:** {advice['styl_prezentacji']}")

            st.markdown("---")
            st.subheader("📋 Plan zdjęć")

            for photo in advice["plan_zdjec"]:
                st.markdown(f"""
<div style="background:#f8f9fa;border-left:4px solid #667eea;
            padding:12px 16px;border-radius:4px;margin:8px 0;">
  <strong>📷 Zdjęcie {photo['nr']} — {photo['tytul']}</strong><br>
  <span style="color:#4a5568;">{photo['opis']}</span><br>
  <span style="color:#718096;font-size:13px;">💡 Dlaczego: {photo['dlaczego']}</span>
</div>""", unsafe_allow_html=True)

            if advice["pro_tips"]:
                st.markdown("---")
                st.subheader("⭐ Pro wskazówki")
                for tip in advice["pro_tips"]:
                    st.markdown(f"✅ {tip}")

            if advice["unikaj"]:
                st.markdown("---")
                st.subheader("❌ Czego unikać")
                for avoid in advice["unikaj"]:
                    st.markdown(f"✗ {avoid}")

            if not cfg.get("claude_api_key"):
                st.markdown("---")
                st.info(
                    "💡 Dodaj klucz Claude AI w ustawieniach żeby otrzymać bardziej "
                    "spersonalizowane porady (~0,03 zł za zapytanie)."
                )
