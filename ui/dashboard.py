"""Dashboard - ekran glowny."""
from datetime import date

import plotly.graph_objects as go
import streamlit as st

from config import MONTHLY_GOAL_PLN, VINTED_PRIMARY, VINTED_ACCENT, VINTED_DARK
from core import database, rules


def render():
    st.markdown("## 🏠 Dashboard")
    st.caption("Szybki podglad Twojej sprzedazy")

    active = database.get_active_listings()
    today = date.today()
    sales_month = database.get_sales_in_month(today.year, today.month)
    sales_today = database.get_sales_on_date(today.isoformat())

    total_month = sum((s.get("net_profit") or 0) for s in sales_month)
    total_today = sum((s.get("net_profit") or 0) for s in sales_today)
    pct = min(total_month / MONTHLY_GOAL_PLN * 100, 100) if MONTHLY_GOAL_PLN else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _metric_card("Aktywne ogloszenia", f"{len(active)}", VINTED_PRIMARY)
    with col2:
        _metric_card("Dzis sprzedane", f"{len(sales_today)}", "#10B981")
    with col3:
        _metric_card("Miesiac (netto)", f"{total_month:.0f} zl", VINTED_DARK)
    with col4:
        _metric_card("Do celu", f"{max(MONTHLY_GOAL_PLN - total_month, 0):.0f} zl", VINTED_ACCENT)

    st.markdown("### 🎯 Cel miesieczny")
    st.caption(f"Limit podatkowy: {MONTHLY_GOAL_PLN:.0f} PLN")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=total_month,
        number={"suffix": " zl", "font": {"size": 40, "color": VINTED_DARK}},
        delta={"reference": MONTHLY_GOAL_PLN, "decreasing": {"color": "#10B981"}},
        gauge={
            "axis": {"range": [0, MONTHLY_GOAL_PLN * 1.1], "tickcolor": "#9CA3AF"},
            "bar": {"color": VINTED_PRIMARY},
            "bgcolor": "#F3F4F6",
            "borderwidth": 0,
            "steps": [
                {"range": [0, MONTHLY_GOAL_PLN * 0.5], "color": "#E0F7FA"},
                {"range": [MONTHLY_GOAL_PLN * 0.5, MONTHLY_GOAL_PLN * 0.85], "color": "#B2EBF2"},
                {"range": [MONTHLY_GOAL_PLN * 0.85, MONTHLY_GOAL_PLN], "color": "#FED7AA"},
                {"range": [MONTHLY_GOAL_PLN, MONTHLY_GOAL_PLN * 1.1], "color": "#FECACA"},
            ],
            "threshold": {
                "line": {"color": VINTED_ACCENT, "width": 3},
                "thickness": 0.85,
                "value": MONTHLY_GOAL_PLN,
            },
        },
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=10, b=10), paper_bgcolor="#FAFAFA")
    st.plotly_chart(fig, use_container_width=True)

    if pct >= 100:
        st.error("⚠️ Przekroczono limit 3 499 zl - uwazaj na obowiazek podatkowy.")
    elif pct >= 85:
        st.warning(f"⚠️ Zblizasz sie do limitu ({pct:.1f}%). Planuj sprzedaz rozwaznie.")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown("### 🎯 Pilne akcje")
        recs = rules.get_recommendations(only_actionable=True)
        if not recs:
            st.success("Brak pilnych akcji - wszystko pod kontrola.")
        else:
            for r in recs[:5]:
                urgent = r.action in ("RELIST", "LOWER_PRICE")
                css_class = "action-card urgent" if urgent else "action-card"
                emoji = rules.EMOJIS.get(r.action, "•")
                label = rules.LABELS.get(r.action, r.action)
                price_str = f"{r.current_price:.0f} zl" if r.current_price else "?"
                st.markdown(
                    f'<div class="{css_class}"><b>{emoji} {label}</b><br>'
                    f'<span style="color:#6B7280;font-size:0.9rem">{r.title[:50]} - {price_str} - {r.days_on_market}d</span></div>',
                    unsafe_allow_html=True,
                )
            if len(recs) > 5:
                st.caption(f"+ {len(recs) - 5} wiecej akcji - zobacz zakladke 'Akcje do wykonania'")

    with col_b:
        st.markdown("### 💰 Ostatnia sprzedaz")
        if not sales_month:
            st.info("Brak sprzedazy w tym miesiacu.")
        else:
            recent = sorted(
                sales_month,
                key=lambda s: s.get("sold_date") or "",
                reverse=True,
            )[:5]
            for s in recent:
                price = s.get("sold_price") or 0
                profit = s.get("net_profit") or 0
                st.markdown(
                    f'<div class="action-card"><b>✅ {s["title"][:40]}</b><br>'
                    f'<span style="color:#6B7280;font-size:0.9rem">'
                    f'{price:.0f} zl (zysk {profit:.0f} zl) - {s.get("sold_date", "")}</span></div>',
                    unsafe_allow_html=True,
                )


def _metric_card(label: str, value: str, color: str):
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value" style="color:{color}">{value}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
