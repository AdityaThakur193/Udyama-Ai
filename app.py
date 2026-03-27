"""Streamlit entrypoint for the Market Intelligence Agent dashboard."""
from __future__ import annotations

import hashlib
import json
import re
from html import escape, unescape

import streamlit as st

from market_agent.core.browser_storage import get_indexeddb_script
from market_agent.agents.crew import run_research_crew
from market_agent.agents.followup import answer_followup
from market_agent.core.cache import get_cached_report, save_report

try:
    from market_agent.core.settings import GEMINI_API_KEY  # noqa: F401
except RuntimeError as _cfg_err:
    st.error(f"⚙️ Configuration error: {_cfg_err}")
    st.stop()

st.set_page_config(
    layout="wide",
    page_title="Udyama-AI · Market Intelligence",
    page_icon="◆",
    initial_sidebar_state="expanded",
)

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700;800'
    '&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap"'
    ' rel="stylesheet">',
    unsafe_allow_html=True,
)

st.markdown(get_indexeddb_script(), unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================

def init_persistent_state() -> None:
    defaults = {
        "view": "Research",
        "report": None,
        "agent_log": "",
        "qa_history": [],
        "idea": "",
        "region": "India",
        "segment": "Consumers",
        "depth": "Quick",
        "db_synced": False,
        "regions_selected": ["India"],
        "segments_selected": ["Consumers"],
        "region_other": "",
        "segment_other": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_persistent_state()


def restore_session_from_storage() -> None:
    st.markdown(
        """<script>
        async function restoreSessionData() {
            if (!window.UdyamaStorage) return;
            let attempts = 0;
            while (!window.UdyamaStorage.isReady() && attempts < 20) {
                await new Promise(r => setTimeout(r, 50)); attempts++;
            }
            try {
                const qa = await window.UdyamaStorage.getSession('qa_history');
                if (qa && qa.length > 0) console.log('Restored QA:', qa.length, 'msgs');
            } catch(e) { console.log('Could not restore session:', e); }
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', restoreSessionData);
        } else { restoreSessionData(); }
        </script>""",
        unsafe_allow_html=True,
    )


restore_session_from_storage()


def save_qa_to_storage() -> None:
    if st.session_state.get("qa_history"):
        history_json = json.dumps(st.session_state.qa_history)
        st.markdown(
            f"""<script>
            if (window.UdyamaStorage && window.UdyamaStorage.isReady()) {{
                window.UdyamaStorage.saveSession('qa_history', {history_json});
            }}
            </script>""",
            unsafe_allow_html=True,
        )


# ============================================================
# DESIGN SYSTEM — Earthy Warmth Palette
# Tea Green · Beige · Cornsilk · Papaya Whip · Light Bronze
# ============================================================

st.markdown(
    """
    <style>
    /* ── TOKENS ── */
    :root {
        /* Palette */
        --tea-green:    #CCD5AE;
        --beige:        #E9EDC9;
        --cornsilk:     #FEFAE0;
        --papaya-whip:  #FAEDCD;
        --light-bronze: #D4A373;
        --bronze-dark:  #BF8C5A;
        --bronze-darker:#A0733D;

        /* Semantic roles */
        --bg:           #FEFAE0;          /* cornsilk — lightest, page bg */
        --surface:      #FAEDCD;          /* papaya-whip — cards */
        --surface-2:    #E9EDC9;          /* beige — secondary surfaces */
        --border:       #CCD5AE;          /* tea-green — borders */
        --border-soft:  rgba(204,213,174,0.5);
        --accent:       #D4A373;          /* light-bronze — primary CTA */
        --accent-dark:  #BF8C5A;
        --accent-darker:#A0733D;
        --accent-soft:  rgba(212,163,115,0.12);
        --accent-glow:  rgba(212,163,115,0.25);

        /* Typography */
        --primary:      #3B2A1A;          /* warm dark brown — headings */
        --text:         #4A3728;          /* body text */
        --muted:        #8B7355;          /* muted text */
        --text-light:   #6B5742;

        /* Sidebar */
        --sidebar-bg:   #3B2A1A;          /* warm dark espresso */
        --sidebar-text: #E9EDC9;
        --sidebar-muted:#8B7355;

        /* States */
        --danger:       #C0392B;
        --danger-soft:  rgba(192,57,43,0.08);
        --info:         #4A7C8E;
        --info-soft:    rgba(74,124,142,0.08);
        --success:      #5A7A3A;
        --success-soft: rgba(90,122,58,0.1);

        /* Layout */
        --radius:       10px;
        --radius-sm:    6px;
        --radius-lg:    16px;
        --shadow-sm:    0 1px 4px rgba(59,42,26,0.07), 0 1px 2px rgba(59,42,26,0.04);
        --shadow:       0 4px 18px rgba(59,42,26,0.1), 0 1px 4px rgba(59,42,26,0.05);
        --shadow-lg:    0 8px 36px rgba(59,42,26,0.14);
    }

    /* ── BASE ── */
    html, body, .stApp {
        font-family: 'DM Sans', system-ui, sans-serif !important;
        background: var(--bg) !important;
        color: var(--text) !important;
    }
    h1, h2, h3, h4, h5 {
        font-family: 'Playfair Display', Georgia, serif !important;
        color: var(--primary) !important;
        letter-spacing: -0.01em;
    }
    a { color: var(--accent-darker) !important; }
    a:hover { color: var(--accent-dark) !important; text-decoration: underline; }

    /* ── STREAMLIT CHROME ── */
    [data-testid="stHeader"]     { background: transparent !important; }
    [data-testid="stToolbar"]    { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    footer                       { display: none !important; }
    #MainMenu                    { display: none !important; }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {
        background: var(--sidebar-bg) !important;
        border-right: 1px solid rgba(212,163,115,0.2) !important;
    }
    [data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stCaption {
        color: var(--sidebar-text) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #FEFAE0 !important;
        font-family: 'Playfair Display', serif !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(212,163,115,0.2) !important;
        margin: 14px 0 !important;
    }

    /* sidebar nav buttons */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(212,163,115,0.1) !important;
        color: #E9EDC9 !important;
        border: 1px solid rgba(212,163,115,0.2) !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.93rem !important;
        padding: 10px 14px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
        text-align: left !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(212,163,115,0.22) !important;
        border-color: var(--light-bronze) !important;
        color: #FEFAE0 !important;
    }
    .nav-active > div > button {
        background: var(--light-bronze) !important;
        color: #3B2A1A !important;
        border-color: var(--light-bronze) !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 10px rgba(212,163,115,0.4) !important;
    }

    /* sidebar inputs */
    [data-testid="stSidebar"] .stTextArea textarea,
    [data-testid="stSidebar"] .stTextInput input {
        background: rgba(254,250,224,0.07) !important;
        border: 1px solid rgba(212,163,115,0.3) !important;
        color: #E9EDC9 !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.9rem !important;
    }
    [data-testid="stSidebar"] .stTextArea textarea:focus,
    [data-testid="stSidebar"] .stTextInput input:focus {
        border-color: var(--light-bronze) !important;
        box-shadow: 0 0 0 3px rgba(212,163,115,0.2) !important;
    }
    [data-testid="stSidebar"] .stTextArea textarea::placeholder,
    [data-testid="stSidebar"] .stTextInput input::placeholder {
        color: rgba(233,237,201,0.4) !important;
    }
    [data-testid="stSidebar"] .stTextArea label,
    [data-testid="stSidebar"] .stTextInput label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stSelectbox label {
        color: #CCD5AE !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background: rgba(254,250,224,0.07) !important;
        border: 1px solid rgba(212,163,115,0.3) !important;
        color: #E9EDC9 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div {
        color: #E9EDC9 !important;
        -webkit-text-fill-color: #E9EDC9 !important;
    }
    [data-testid="stSidebar"] [data-baseweb="popover"],
    [data-testid="stSidebar"] [data-baseweb="popover"] * {
        background: #4A3728 !important;
        color: #E9EDC9 !important;
        border-color: rgba(212,163,115,0.3) !important;
    }
    [data-testid="stSidebar"] .stCheckbox label {
        color: #CCD5AE !important;
        font-size: 0.88rem !important;
    }
    [data-testid="stSidebar"] .stFormSubmitButton > button {
        background: var(--light-bronze) !important;
        color: #3B2A1A !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.94rem !important;
        padding: 11px 24px !important;
        box-shadow: 0 2px 10px rgba(212,163,115,0.35) !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.01em !important;
    }
    [data-testid="stSidebar"] .stFormSubmitButton > button:hover {
        background: var(--bronze-dark) !important;
        box-shadow: 0 4px 16px rgba(212,163,115,0.5) !important;
        transform: translateY(-1px) !important;
    }

    /* ── MAIN CONTENT ── */
    .block-container {
        padding-top: 2rem !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        max-width: 1200px !important;
    }

    /* ── HERO ── */
    .hero {
        background: linear-gradient(135deg, #3B2A1A 0%, #4A3728 55%, #5C4A32 100%);
        border-radius: var(--radius-lg);
        padding: 52px 44px;
        margin-bottom: 32px;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(212,163,115,0.2);
    }
    .hero::before {
        content: '';
        position: absolute; top: -40%; right: -8%;
        width: 420px; height: 420px;
        background: radial-gradient(circle, rgba(212,163,115,0.2) 0%, transparent 68%);
        border-radius: 50%;
    }
    .hero::after {
        content: '';
        position: absolute; bottom: -30%; left: 5%;
        width: 280px; height: 280px;
        background: radial-gradient(circle, rgba(204,213,174,0.1) 0%, transparent 65%);
        border-radius: 50%;
    }
    .hero h1 {
        font-family: 'Playfair Display', serif !important;
        font-size: 2.5rem;
        font-weight: 800;
        color: #FEFAE0 !important;
        margin: 0 0 14px;
        line-height: 1.18;
        letter-spacing: -0.02em;
        position: relative;
    }
    .hero h1 span { color: #D4A373; }
    .hero p {
        font-size: 1.02rem;
        color: #CCD5AE !important;
        margin: 0;
        line-height: 1.7;
        max-width: 560px;
        position: relative;
        font-family: 'DM Sans', sans-serif;
    }
    .hero-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(212,163,115,0.18); border: 1px solid rgba(212,163,115,0.35);
        color: #D4A373; font-size: 0.75rem; font-weight: 700;
        padding: 4px 12px; border-radius: 999px; margin-bottom: 18px;
        letter-spacing: 0.07em; text-transform: uppercase;
        font-family: 'DM Sans', sans-serif; position: relative;
    }

    /* ── PAGE HEADER ── */
    .page-header {
        margin-bottom: 28px; padding-bottom: 18px;
        border-bottom: 2px solid var(--border);
    }
    .page-header h2 { font-size: 1.65rem; font-weight: 700; margin: 0 0 4px; }
    .page-header p  { color: var(--muted); font-size: 0.94rem; margin: 0; font-family: 'DM Sans', sans-serif; }

    /* ── CARDS ── */
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 16px 20px;
        margin-bottom: 10px;
        box-shadow: var(--shadow-sm);
        line-height: 1.65;
        color: var(--text);
        font-size: 0.93rem;
        font-family: 'DM Sans', sans-serif;
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }
    .metric-card:hover {
        box-shadow: var(--shadow);
        transform: translateY(-1px);
    }

    .comp-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 22px 24px;
        margin-bottom: 14px;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    .comp-card:hover {
        box-shadow: var(--shadow);
        transform: translateY(-2px);
    }
    .comp-top {
        border: 1.5px solid var(--light-bronze);
        box-shadow: 0 4px 20px rgba(212,163,115,0.15);
        background: linear-gradient(135deg, var(--surface) 0%, rgba(212,163,115,0.06) 100%);
    }
    .comp-card h4  {
        margin: 0 0 8px; font-size: 1.05rem;
        font-family: 'Playfair Display', serif !important;
        color: var(--primary) !important;
    }
    .comp-card p  { margin: 6px 0; color: var(--muted); font-size: 0.9rem; line-height: 1.55; }
    .comp-card a {
        display: inline-block; padding: 5px 14px;
        background: var(--accent-soft); color: var(--accent-darker) !important;
        border: 1px solid var(--border); border-radius: 6px;
        font-size: 0.83rem; font-weight: 600;
        transition: all 0.2s ease; text-decoration: none !important;
        font-family: 'DM Sans', sans-serif;
    }
    .comp-card a:hover {
        background: var(--light-bronze); color: #3B2A1A !important;
        border-color: var(--light-bronze);
        box-shadow: 0 2px 8px rgba(212,163,115,0.3);
    }

    /* ── SUMMARY PILL ── */
    .summary-pill {
        background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 18px 22px;
        margin-bottom: 24px;
        display: flex; gap: 20px; align-items: center; flex-wrap: wrap;
        box-shadow: var(--shadow-sm);
    }
    .summary-item    { display: flex; flex-direction: column; gap: 3px; }
    .summary-label   {
        font-size: 0.7rem; color: var(--muted); font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.08em; font-family: 'DM Sans', sans-serif;
    }
    .summary-value   {
        font-size: 0.92rem; color: var(--primary); font-weight: 600;
        font-family: 'Playfair Display', serif;
    }
    .summary-divider { width: 1px; height: 36px; background: var(--border); flex-shrink: 0; }

    /* ── INPUTS (main area) ── */
    .stTextInput input, .stTextArea textarea,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1.5px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.93rem !important;
        color: var(--text) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--light-bronze) !important;
        box-shadow: 0 0 0 3px rgba(212,163,115,0.15) !important;
    }
    .stTextInput label, .stTextArea label, .stSelectbox label, .stMultiSelect label {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 700 !important; font-size: 0.83rem !important;
        color: var(--text-light) !important;
        text-transform: uppercase !important; letter-spacing: 0.05em !important;
    }
    [data-baseweb="popover"] {
        background: var(--cornsilk) !important;
        border: 1px solid var(--border) !important;
        box-shadow: var(--shadow-lg) !important;
        border-radius: var(--radius) !important;
    }
    [data-baseweb="popover"] * { color: var(--text) !important; }
    [role="option"][aria-selected="true"] { background: var(--accent-soft) !important; }
    [role="option"]:hover { background: var(--surface-2) !important; }

    /* ── BUTTONS (main area) ── */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--light-bronze) !important;
        color: #3B2A1A !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        padding: 11px 24px !important;
        font-weight: 700 !important; font-size: 0.93rem !important;
        font-family: 'DM Sans', sans-serif !important;
        box-shadow: 0 2px 10px rgba(212,163,115,0.3) !important;
        transition: all 0.2s ease !important;
        height: 42px !important;
        letter-spacing: 0.01em !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {
        background: var(--bronze-dark) !important;
        box-shadow: 0 4px 16px rgba(212,163,115,0.45) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:not([kind="primary"]),
    .stFormSubmitButton > button:not([kind="primary"]) {
        background: var(--surface) !important;
        color: var(--accent-darker) !important;
        border: 1.5px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        padding: 10px 20px !important;
        font-weight: 600 !important; font-size: 0.93rem !important;
        font-family: 'DM Sans', sans-serif !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:not([kind="primary"]):hover,
    .stFormSubmitButton > button:not([kind="primary"]):hover {
        background: var(--surface-2) !important;
        border-color: var(--light-bronze) !important;
    }

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--surface) !important;
        border-radius: var(--radius) !important;
        padding: 4px !important;
        border: 1px solid var(--border) !important;
        box-shadow: var(--shadow-sm);
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--muted) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important; font-size: 0.88rem !important;
        padding: 8px 18px !important; border-radius: 7px !important;
        border: none !important; transition: all 0.2s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text) !important; background: var(--surface-2) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--primary) !important;
        background: var(--beige) !important;
        box-shadow: var(--shadow-sm) !important;
        border-bottom: 2px solid var(--light-bronze) !important;
    }
    .stTabs [data-baseweb="tab-panel"] { padding: 20px 0 !important; }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ── EXPANDER ── */
    [data-testid="stExpander"] summary {
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: var(--surface-2) !important;
        border-color: var(--light-bronze) !important;
    }
    [data-testid="stExpander"] summary * { color: var(--text) !important; }

    /* ── REASONING LOG ── */
    .term {
        background: #3B2A1A;
        color: #CCD5AE;
        border: 1px solid rgba(212,163,115,0.2);
        padding: 20px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        white-space: pre-wrap; line-height: 1.65;
        border-radius: var(--radius); font-size: 0.83rem; overflow-x: auto;
    }

    /* ── CHAT ── */
    .chat-container { max-width: 820px; margin: 0 auto; }
    .chat-row       { margin: 16px 0; display: flex; gap: 10px; align-items: flex-end; }
    .chat-user      { justify-content: flex-end; }
    .chat-agent     { justify-content: flex-start; }

    .user-bubble {
        background: linear-gradient(135deg, #4A3728 0%, #3B2A1A 100%);
        color: #FEFAE0; max-width: 72%;
        padding: 12px 18px; border-radius: 16px 16px 4px 16px;
        font-size: 0.93rem; line-height: 1.6; word-wrap: break-word;
        box-shadow: 0 2px 10px rgba(59,42,26,0.2);
        font-family: 'DM Sans', sans-serif;
    }
    .agent-avatar {
        width: 34px; height: 34px; border-radius: 10px;
        background: linear-gradient(135deg, var(--light-bronze) 0%, var(--bronze-dark) 100%);
        color: #3B2A1A; font-family: 'Playfair Display', serif; font-weight: 700;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0; font-size: 1rem;
        box-shadow: 0 2px 8px rgba(212,163,115,0.35);
    }
    .agent-bubble {
        background: var(--surface); color: var(--text);
        border: 1px solid var(--border); max-width: 72%;
        padding: 14px 18px; border-radius: 16px 16px 16px 4px;
        font-size: 0.93rem; line-height: 1.65; word-wrap: break-word;
        box-shadow: var(--shadow-sm); font-family: 'DM Sans', sans-serif;
    }
    .chat-empty {
        text-align: center; padding: 52px 24px;
        color: var(--muted); font-size: 0.95rem; font-family: 'DM Sans', sans-serif;
    }
    .chat-empty span { font-size: 2.8rem; display: block; margin-bottom: 14px; }

    /* ── WELCOME ── */
    .welcome {
        border: 1.5px dashed var(--border);
        background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
        padding: 60px 40px; text-align: center; border-radius: var(--radius-lg);
        margin-top: 16px;
    }
    .welcome h3 {
        font-size: 1.5rem; font-weight: 700; margin: 0 0 10px;
        color: var(--primary) !important;
        font-family: 'Playfair Display', serif !important;
    }
    .welcome p { color: var(--muted) !important; font-size: 0.96rem; margin: 0; line-height: 1.7; }

    /* ── MISC ── */
    .stMarkdown, p, li { font-family: 'DM Sans', sans-serif !important; color: var(--text); }
    [data-testid="stAlert"]     { border-radius: var(--radius) !important; font-family: 'DM Sans', sans-serif !important; }
    [data-testid="stStatusWidget"] * { color: var(--text) !important; }
    .hint-text { font-size: 0.83rem; color: var(--muted); font-family: 'DM Sans', sans-serif; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_response_text(text: str) -> str:
    if not text:
        return ""
    lines = text.split("\n")
    html: list[str] = []
    in_list = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_list:
                html.append("</div>"); in_list = False
            html.append("<div style='margin:8px 0'></div>")
            continue
        is_bullet = s.startswith(("*", "-", "•", "–")) or (s and s[0].isdigit() and "." in s[:3])
        if is_bullet:
            clean = s[2:].strip() if s.startswith(("* ", "- ", "• ", "– ")) else (s.split(".", 1)[1].strip() if "." in s else s)
            if not in_list:
                html.append("<div style='margin:12px 0'>"); in_list = True
            html.append(
                f"<div style='margin:5px 0;padding-left:16px;border-left:3px solid #D4A373;'>"
                f"<span style='color:#D4A373;font-weight:700;margin-right:6px;'>›</span>{escape(clean)}</div>"
            )
        else:
            if in_list:
                html.append("</div>"); in_list = False
            if s.endswith(":") or (len(s.split()) <= 5 and s.isupper()):
                html.append(
                    f"<div style='margin:12px 0 6px;font-weight:700;color:#3B2A1A;"
                    f"font-size:0.9rem;font-family:Playfair Display,serif;'>{escape(s)}</div>"
                )
            else:
                html.append(f"<div style='margin:7px 0;line-height:1.65;color:#4A3728;'>{escape(s)}</div>")
    if in_list:
        html.append("</div>")
    return "".join(html)


def sanitize_competitor_text(text: str | None) -> str:
    if not text:
        return ""
    cleaned = unescape(str(text)).strip()
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace("', '", "; ").replace('" , "', "; ").strip("'\"")
    return cleaned


def to_points(text: str | None) -> list[str]:
    cleaned = sanitize_competitor_text(text)
    if not cleaned:
        return []
    parts = re.split(r"\n+|\s*[•*]\s+|\s*;\s+|\s*\|\s*", cleaned)
    items = [p.strip(" -\t") for p in parts if p.strip(" -\t")]
    return items if items else [cleaned]


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div style='padding:28px 8px 20px;border-bottom:1px solid rgba(212,163,115,0.2);margin-bottom:8px;'>
            <div style='font-family:Playfair Display,serif;font-weight:800;font-size:1.3rem;
                        color:#FEFAE0;display:flex;align-items:center;gap:10px;letter-spacing:-0.01em;'>
                <span style='background:#D4A373;color:#3B2A1A;border-radius:8px;
                             padding:4px 8px;font-size:1rem;font-family:DM Sans,sans-serif;
                             font-weight:700;'>◆</span>
                Udyama-AI
            </div>
            <div style='font-family:DM Sans,sans-serif;font-size:0.72rem;color:#6B5742;
                        margin-top:6px;letter-spacing:0.07em;text-transform:uppercase;font-weight:700;'>
                Market Intelligence
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='padding:4px 0 8px;font-size:0.7rem;color:#6B5742;font-weight:700;"
        "letter-spacing:0.09em;text-transform:uppercase;font-family:DM Sans,sans-serif;'>Navigation</div>",
        unsafe_allow_html=True,
    )

    view = st.session_state.view
    for label, key, v in [
        ("🔍  Research",  "nav_research",  "Research"),
        ("📊  Insights",  "nav_insights",  "Insights"),
        ("💬  Follow-up", "nav_followup",  "Follow-up"),
    ]:
        cls = "nav-active" if view == v else ""
        st.markdown(f"<div class='{cls}'>", unsafe_allow_html=True)
        if st.button(label, key=key, use_container_width=True):
            st.session_state.view = v
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown(
        "<div style='font-size:0.7rem;color:#6B5742;font-weight:700;letter-spacing:0.09em;"
        "text-transform:uppercase;font-family:DM Sans,sans-serif;margin-bottom:12px;'>Research Setup</div>",
        unsafe_allow_html=True,
    )

    with st.form("research_form"):
        st.session_state.idea = st.text_area(
            "Startup Idea",
            value=st.session_state.idea,
            placeholder="Describe your value proposition and target problem…",
            height=100,
        )

        region_options = ["India", "US", "EU", "Southeast Asia", "Global", "Other"]
        st.session_state.regions_selected = st.multiselect(
            "Region",
            region_options,
            default=[r for r in st.session_state.regions_selected if r in region_options],
        )
        if "Other" in st.session_state.regions_selected:
            st.session_state.region_other = st.text_input(
                "Custom Region(s)",
                value=st.session_state.region_other,
                placeholder="e.g., Middle East, Africa",
            )

        segment_options = ["Consumers", "SMEs", "Enterprises", "Students", "Healthcare", "Farmers", "Gig Workers", "Other"]
        st.session_state.segments_selected = st.multiselect(
            "Target Segment",
            segment_options,
            default=[s for s in st.session_state.segments_selected if s in segment_options],
        )
        if "Other" in st.session_state.segments_selected:
            st.session_state.segment_other = st.text_input(
                "Custom Segment(s)",
                value=st.session_state.segment_other,
                placeholder="e.g., NGOs, Governments",
            )

        st.markdown(
            "<div style='font-size:0.78rem;color:#CCD5AE;font-weight:700;margin:8px 0 4px;"
            "letter-spacing:0.05em;text-transform:uppercase;'>Depth</div>",
            unsafe_allow_html=True,
        )
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.checkbox("Quick", value=st.session_state.depth == "Quick", key="depth_quick"):
                st.session_state.depth = "Quick"
        with col_d2:
            if st.checkbox("Deep", value=st.session_state.depth == "Deep", key="depth_deep"):
                st.session_state.depth = "Deep"

        run_clicked = st.form_submit_button("▶  Run Research", use_container_width=True)

    st.markdown(
        "<div style='font-size:0.74rem;color:#6B5742;text-align:center;margin-top:6px;"
        "font-family:DM Sans,sans-serif;'>~30s Quick · ~10m Deep</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.report is not None:
        r = st.session_state.report
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            f"""<div style='font-size:0.7rem;color:#6B5742;font-weight:700;letter-spacing:0.09em;
                text-transform:uppercase;font-family:DM Sans,sans-serif;margin-bottom:10px;'>
                Active Report</div>
                <div style='background:rgba(212,163,115,0.12);border:1px solid rgba(212,163,115,0.25);
                border-radius:8px;padding:12px;'>
                <div style='color:#CCD5AE;font-size:0.76rem;font-weight:700;font-family:DM Sans,sans-serif;
                letter-spacing:0.05em;text-transform:uppercase;margin-bottom:4px;'>Idea</div>
                <div style='color:#E9EDC9;font-size:0.83rem;line-height:1.55;font-family:DM Sans,sans-serif;'>
                {escape(r.idea[:80])}{'…' if len(r.idea)>80 else ''}</div>
                <div style='margin-top:8px;display:flex;gap:5px;flex-wrap:wrap;'>
                <span style='background:rgba(212,163,115,0.18);color:#D4A373;font-size:0.72rem;
                padding:2px 8px;border-radius:4px;font-family:DM Sans,sans-serif;font-weight:600;'>
                {escape(r.region)}</span>
                <span style='background:rgba(212,163,115,0.18);color:#D4A373;font-size:0.72rem;
                padding:2px 8px;border-radius:4px;font-family:DM Sans,sans-serif;font-weight:600;'>
                {escape(r.segment)}</span>
                <span style='background:rgba(212,163,115,0.18);color:#D4A373;font-size:0.72rem;
                padding:2px 8px;border-radius:4px;font-family:DM Sans,sans-serif;font-weight:600;'>
                {st.session_state.depth}</span>
                </div></div>""",
            unsafe_allow_html=True,
        )


# ============================================================
# HANDLE FORM SUBMISSION
# ============================================================

if run_clicked:
    idea    = st.session_state.idea
    regions = [r for r in st.session_state.regions_selected if r != "Other"]
    segments = [s for s in st.session_state.segments_selected if s != "Other"]

    if "Other" in st.session_state.regions_selected and st.session_state.region_other.strip():
        regions.extend([r.strip() for r in st.session_state.region_other.split(",") if r.strip()])
    if "Other" in st.session_state.segments_selected and st.session_state.segment_other.strip():
        segments.extend([s.strip() for s in st.session_state.segment_other.split(",") if s.strip()])

    region  = ", ".join(regions)
    segment = ", ".join(segments)
    depth   = st.session_state.depth

    if not idea.strip():
        st.warning("⚠️ Please describe your startup idea.")
    elif not regions:
        st.warning("⚠️ Please select at least one region.")
    elif not segments:
        st.warning("⚠️ Please select at least one target segment.")
    else:
        st.session_state.region  = region
        st.session_state.segment = segment
        signature = hashlib.sha256(f"{idea}|{region}|{segment}|{depth}".encode()).hexdigest()
        cached = get_cached_report(signature)
        if cached:
            st.session_state.report    = cached
            st.session_state.agent_log = "Loaded from cache."
            st.session_state.qa_history = []
            st.session_state.view      = "Insights"
            st.rerun()
        else:
            with st.status("Running agent pipeline…", expanded=True) as status:
                st.write("🧠 Initializing agent roles and research tasks")
                st.write("🌐 Gathering market signals and competitive intelligence")
                st.write("✍️ Synthesizing research into strategic brief")
                try:
                    report, agent_log = run_research_crew(idea, region, segment, depth)
                    save_report(signature, report)
                    st.session_state.report    = report
                    st.session_state.agent_log = agent_log
                    st.session_state.qa_history = []
                    status.update(label="✅ Research complete!", state="complete", expanded=False)
                    st.session_state.view = "Insights"
                    st.rerun()
                except RuntimeError as exc:
                    status.update(label="❌ Research failed", state="error", expanded=True)
                    st.session_state.agent_log = str(exc)
                    st.error(str(exc))


# ============================================================
# RESEARCH VIEW
# ============================================================

if st.session_state.view == "Research":
    st.markdown(
        """
        <div class='hero'>
            <div class='hero-badge'>◆ AI-Powered Research Agent</div>
            <h1>Market <span>Intelligence</span><br>at Founder Speed</h1>
            <p>Describe your startup on the left panel, pick your market, and get deep competitive
            analysis, pricing insights, and a go-to-market strategy — in minutes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.report is None:
        st.markdown(
            """<div class='welcome'>
                <h3>Ready when you are</h3>
                <p>Fill in the Research Setup panel on the left and click
                <strong>Run Research</strong> to begin your market analysis.</p>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.info("✅ A report is ready — head to **Insights** to explore your results.")


# ============================================================
# INSIGHTS VIEW
# ============================================================

elif st.session_state.view == "Insights":
    if st.session_state.report is None:
        st.markdown("<div class='page-header'><h2>📊 Insights</h2><p>Run a research report to see your market analysis.</p></div>", unsafe_allow_html=True)
        st.markdown("<div class='welcome'><h3>No report yet</h3><p>Head to Research and run your first analysis.</p></div>", unsafe_allow_html=True)
    else:
        report = st.session_state.report

        st.markdown(
            "<div class='page-header'><h2>📊 Market Insights</h2>"
            "<p>Your AI-generated market intelligence report</p></div>",
            unsafe_allow_html=True,
        )

        market_cap_value = getattr(report, "market_cap", None)
        cap_html = (
            f"<div class='summary-divider'></div>"
            f"<div class='summary-item'>"
            f"<span class='summary-label'>Market Cap</span>"
            f"<span class='summary-value'>{escape(str(market_cap_value))}</span></div>"
        ) if market_cap_value else ""

        st.markdown(
            f"""<div class='summary-pill'>
                <div class='summary-item'>
                    <span class='summary-label'>Idea</span>
                    <span class='summary-value'>{escape(report.idea[:48])}{'…' if len(report.idea)>48 else ''}</span>
                </div>
                <div class='summary-divider'></div>
                <div class='summary-item'>
                    <span class='summary-label'>Region</span>
                    <span class='summary-value'>{escape(report.region)}</span>
                </div>
                <div class='summary-divider'></div>
                <div class='summary-item'>
                    <span class='summary-label'>Segment</span>
                    <span class='summary-value'>{escape(report.segment)}</span>
                </div>
                <div class='summary-divider'></div>
                <div class='summary-item'>
                    <span class='summary-label'>Depth</span>
                    <span class='summary-value'>{st.session_state.depth}</span>
                </div>
                {cap_html}
            </div>""",
            unsafe_allow_html=True,
        )

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["🌐 Overview", "🏢 Competitors", "💰 Pricing", "🔴 Pain Points", "🎯 Entry Strategy"]
        )

        with tab1:
            overview_text = report.market_overview or ""
            raw = re.split(r"\n+|\s*[•*]\s+|\s*-\s+", overview_text)
            items = [p.strip(" -\t") for p in raw if p and p.strip(" -\t")]
            if len(items) <= 1 and overview_text.strip():
                items = [p.strip() for p in re.split(r"(?<=[.!?])\s+", overview_text.strip()) if p.strip()]
            if items:
                for pt in items:
                    st.markdown(
                        f"<div class='metric-card' style='border-left:3px solid #D4A373;'>"
                        f"<span style='color:#D4A373;font-weight:700;margin-right:8px;'>›</span>{escape(pt)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No market overview available.")

        with tab2:
            if report.competitors:
                for idx, comp in enumerate(report.competitors):
                    top_class = " comp-top" if idx == 0 else ""
                    name  = sanitize_competitor_text(comp.name)
                    desc  = sanitize_competitor_text(comp.description)
                    sp    = to_points(comp.strengths)
                    wp    = to_points(comp.weaknesses)
                    badge = ("<span style='background:#D4A373;color:#3B2A1A;font-size:0.7rem;"
                             "padding:2px 8px;border-radius:4px;margin-left:8px;"
                             "font-family:DM Sans,sans-serif;font-weight:700;'>Top Pick</span>") if idx == 0 else ""
                    st.markdown(f"<div class='comp-card{top_class}'>", unsafe_allow_html=True)
                    st.markdown(f"#### #{idx+1} {name}", unsafe_allow_html=False)
                    if idx == 0:
                        st.markdown(badge, unsafe_allow_html=True)
                    if desc:
                        st.write(desc)
                    if comp.url and comp.url.strip():
                        st.markdown(f"[↗ Visit Website]({comp.url.strip()})")
                    if sp:
                        st.markdown("**Strengths**")
                        for p in sp: st.markdown(f"- {p}")
                    if wp:
                        st.markdown("**Weaknesses**")
                        for p in wp: st.markdown(f"- {p}")
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No competitors listed.")

        with tab3:
            if report.pricing_models:
                for idx, pricing in enumerate(report.pricing_models):
                    st.markdown(
                        f"<div class='metric-card' style='border-left:3px solid #D4A373;"
                        f"background:linear-gradient(135deg,#FAEDCD 0%,rgba(212,163,115,0.06) 100%);'>"
                        f"<span style='color:#D4A373;font-weight:700;margin-right:8px;"
                        f"font-family:Playfair Display,serif;'>#{idx+1}</span>{escape(pricing)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("💡 No pricing models available yet.")

        with tab4:
            if report.pain_points:
                for pain in report.pain_points:
                    st.markdown(
                        f"<div class='metric-card' style='border-left:3px solid #C0392B;"
                        f"background:linear-gradient(135deg,#FAEDCD 0%,rgba(192,57,43,0.06) 100%);'>"
                        f"<span style='color:#C0392B;font-weight:700;margin-right:8px;'>●</span>"
                        f"{escape(pain)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("💡 No pain points available yet.")

        with tab5:
            if report.entry_recommendations:
                for idx, entry in enumerate(report.entry_recommendations):
                    st.markdown(
                        f"<div class='metric-card' style='border-left:3px solid #4A7C8E;"
                        f"background:linear-gradient(135deg,#FAEDCD 0%,rgba(74,124,142,0.07) 100%);'>"
                        f"<span style='color:#4A7C8E;font-weight:700;margin-right:8px;"
                        f"font-family:Playfair Display,serif;'>#{idx+1}</span>{escape(entry)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("💡 No entry recommendations available yet.")

        with st.expander("🔍 Agent Reasoning Log", expanded=False):
            log_text = st.session_state.agent_log or getattr(report, "reasoning_log", None) or "No reasoning log available."
            st.markdown(f"<div class='term'>{escape(log_text)}</div>", unsafe_allow_html=True)

        if report.sources and len(report.sources) > 0 and report.sources[0].strip():
            st.markdown("---")
            st.markdown("### 📚 Sources & References")
            st.markdown(
                "<div style='background:rgba(212,163,115,0.08);border-left:3px solid #D4A373;"
                "padding:12px 16px;border-radius:8px;margin-bottom:16px;'>"
                "<p style='margin:0;font-size:0.87rem;color:#8B7355;font-family:DM Sans,sans-serif;'>"
                "These sources were consulted during market research and competitive analysis.</p></div>",
                unsafe_allow_html=True,
            )
            for i, source in enumerate(report.sources, 1):
                if source and source.strip():
                    if source.startswith("http://") or source.startswith("https://"):
                        domain = source.split("://")[1].split("/")[0].replace("www.", "")
                        st.markdown(
                            f"<div style='margin:10px 0;padding:10px 14px;background:#FAEDCD;"
                            f"border-radius:8px;border:1px solid #CCD5AE;border-left:3px solid #D4A373;'>"
                            f"<strong style='color:#A0733D;'>{i}.</strong> "
                            f"<a href='{escape(source)}' target='_blank' style='color:#A0733D;"
                            f"font-weight:600;text-decoration:none;'>{escape(domain)} ↗</a>"
                            f"<br><span style='font-size:0.77rem;color:#8B7355;'>"
                            f"{escape(source[:72])}{'…' if len(source)>72 else ''}</span></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div style='margin:10px 0;padding:10px 14px;background:#FAEDCD;"
                            f"border-radius:8px;border:1px solid #CCD5AE;border-left:3px solid #D4A373;'>"
                            f"<strong style='color:#A0733D;'>{i}.</strong> "
                            f"<span style='color:#4A3728;'>{escape(source)}</span></div>",
                            unsafe_allow_html=True,
                        )
        else:
            st.markdown("---")
            st.markdown("### 📚 Sources & References")
            st.info("📋 Sources will appear here after running a report.")

        st.markdown(
            "<div style='margin-top:32px;padding-top:24px;border-top:1.5px solid #CCD5AE;'></div>",
            unsafe_allow_html=True,
        )
        _, col_btn, _ = st.columns([1, 1, 1])
        with col_btn:
            if st.button("💬 Ask Follow-up Questions", type="primary", use_container_width=True):
                st.session_state.view = "Follow-up"
                st.rerun()


# ============================================================
# FOLLOW-UP VIEW
# ============================================================

elif st.session_state.view == "Follow-up":
    st.markdown(
        "<div class='page-header'><h2>💬 Follow-up Chat</h2>"
        "<p>Ask deeper questions about your market research report</p></div>",
        unsafe_allow_html=True,
    )

    if st.session_state.report is None:
        st.markdown(
            "<div class='welcome'><h3>No report yet</h3>"
            "<p>Run a market analysis first, then come here to ask questions.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        report = st.session_state.report
        st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

        if not st.session_state.qa_history:
            st.markdown(
                "<div class='chat-empty'><span>💬</span>"
                "Ask anything about your market — strategy, competitors, pricing, channels…</div>",
                unsafe_allow_html=True,
            )

        for item in st.session_state.qa_history:
            st.markdown(
                f"<div class='chat-row chat-user'>"
                f"<div class='user-bubble'>{escape(item['question'])}</div></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""<div class='chat-row chat-agent'>
                    <div class='agent-avatar'>M</div>
                    <div class='agent-bubble'>{format_response_text(item['answer'])}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

        with st.form("followup_form", clear_on_submit=True):
            col_q, col_btn = st.columns([5, 1])
            with col_q:
                question = st.text_input(
                    "question",
                    placeholder="e.g., What are the top 3 GTM channels for this segment?",
                    label_visibility="collapsed",
                )
            with col_btn:
                ask_clicked = st.form_submit_button("Ask →", type="primary", use_container_width=True)

        if ask_clicked and question.strip():
            answer = answer_followup(question=question, report=report)
            st.session_state.qa_history.append({"question": question.strip(), "answer": answer})
            save_qa_to_storage()
            st.rerun()
