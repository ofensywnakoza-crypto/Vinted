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

tab1, tab2, tab3 = st.tabs(["📦 Moje ogłoszenia", "🛒 Co kupić — trendy i okazje", "🎯 Cel miesięczny"])


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
# TAB 3 — Monthly goal
# ================================================================== #
with tab3:
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
