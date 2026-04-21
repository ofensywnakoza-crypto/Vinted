"""Vinted Manager - glowna aplikacja Streamlit."""
import streamlit as st

from config import VINTED_PRIMARY, VINTED_DARK, VINTED_LIGHT, VINTED_ACCENT
from core import database

database.init_db()

st.set_page_config(
    page_title="Vinted Manager",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    .stApp {{ background-color: #FAFAFA; }}
    .main .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }}
    h1, h2, h3 {{ color: {VINTED_DARK}; font-weight: 700; }}
    .vinted-logo {{
        font-size: 2rem; font-weight: 800; color: {VINTED_PRIMARY};
        letter-spacing: -1px; margin-bottom: 0;
    }}
    .vinted-subtitle {{ color: #6B7280; font-size: 0.95rem; margin-top: 0; }}
    .metric-card {{
        background: white; border-radius: 12px; padding: 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #E5E7EB;
    }}
    .metric-label {{ color: #6B7280; font-size: 0.85rem; margin-bottom: 0.3rem; }}
    .metric-value {{ color: {VINTED_DARK}; font-size: 1.8rem; font-weight: 700; }}
    .action-card {{
        background: white; border-left: 4px solid {VINTED_PRIMARY};
        border-radius: 8px; padding: 1rem; margin-bottom: 0.6rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}
    .action-card.urgent {{ border-left-color: {VINTED_ACCENT}; }}
    .stButton > button {{
        background-color: {VINTED_PRIMARY}; color: white; border: none;
        border-radius: 8px; padding: 0.5rem 1.2rem; font-weight: 600;
    }}
    .stButton > button:hover {{ background-color: {VINTED_DARK}; }}
    [data-testid="stSidebar"] {{ background-color: white; }}
    .status-badge {{
        display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px;
        font-size: 0.75rem; font-weight: 600;
    }}
    .status-active {{ background: {VINTED_LIGHT}; color: {VINTED_DARK}; }}
    .status-sold {{ background: #D1FAE5; color: #065F46; }}
    .status-trash {{ background: #FEE2E2; color: #991B1B; }}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<p class="vinted-logo">Vinted Manager</p>', unsafe_allow_html=True)
    st.markdown('<p class="vinted-subtitle">Twoj asystent sprzedazy</p>', unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio(
        "Menu",
        [
            "🏠 Dashboard",
            "📦 Moje ogloszenia",
            "🎯 Akcje do wykonania",
            "📸 Strefa fotografii",
            "📈 Trendy rynkowe",
            "💎 Okazje do kupienia",
            "⚙️ Ustawienia",
        ],
        label_visibility="collapsed",
    )

if page.startswith("🏠"):
    from ui import dashboard
    dashboard.render()
elif page.startswith("📦"):
    from ui import listings
    listings.render()
elif page.startswith("🎯"):
    from ui import actions
    actions.render()
elif page.startswith("📸"):
    from ui import photos
    photos.render()
elif page.startswith("📈"):
    from ui import trends_page
    trends_page.render()
elif page.startswith("💎"):
    from ui import deals
    deals.render()
elif page.startswith("⚙️"):
    from ui import settings
    settings.render()
