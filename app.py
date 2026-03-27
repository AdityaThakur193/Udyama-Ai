"""Streamlit entrypoint for the Market Intelligence Agent — production build."""
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
    st.error(f"Configuration error: {_cfg_err}")
    st.stop()

st.set_page_config(
    layout="wide",
    page_title="Udyama-AI · Market Intelligence",
    page_icon="◆",
    initial_sidebar_state="expanded",
)

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800'
    '&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap"'
    ' rel="stylesheet">',
    unsafe_allow_html=True,
)

st.markdown(get_indexeddb_script(), unsafe_allow_html=True)


# ── SESSION STATE ────────────────────────────────────────────

def init_persistent_state() -> None:
    defaults: dict = {
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
            let i = 0;
            while (!window.UdyamaStorage.isReady() && i < 20) {
                await new Promise(r => setTimeout(r, 50)); i++;
            }
            try {
                const qa = await window.UdyamaStorage.getSession('qa_history');
                if (qa && qa.length) console.log('[Udyama] QA restored:', qa.length);
            } catch (e) { console.warn('[Udyama] session restore failed', e); }
        }
        document.readyState === 'loading'
            ? document.addEventListener('DOMContentLoaded', restoreSessionData)
            : restoreSessionData();
        </script>""",
        unsafe_allow_html=True,
    )


restore_session_from_storage()


def save_qa_to_storage() -> None:
    if st.session_state.get("qa_history"):
        payload = json.dumps(st.session_state.qa_history)
        st.markdown(
            f"""<script>
            if (window.UdyamaStorage?.isReady())
                window.UdyamaStorage.saveSession('qa_history', {payload});
            </script>""",
            unsafe_allow_html=True,
        )


# ── DESIGN SYSTEM ────────────────────────────────────────────

st.markdown(
    """
    <style>

    /* ── TOKENS ── */
    :root {
        --tea-green:    #CCD5AE;
        --beige:        #E9EDC9;
        --cornsilk:     #FEFAE0;
        --papaya-whip:  #FAEDCD;
        --bronze:       #D4A373;
        --bronze-dark:  #BF8C5A;
        --bronze-darker:#A0733D;

        --bg:           #FEFAE0;
        --surface:      #FAEDCD;
        --surface-2:    #E9EDC9;
        --border:       #CCD5AE;
        --accent:       #D4A373;
        --accent-dark:  #BF8C5A;
        --accent-soft:  rgba(212,163,115,0.12);

        --primary:      #3B2A1A;
        --text:         #4A3728;
        --text-light:   #6B5742;
        --muted:        #8B7355;

        --sidebar-bg:   #5A4535;

        --danger:       #B83232;
        --info:         #4A7C8E;

        --radius:    10px;
        --radius-sm: 7px;
        --radius-lg: 16px;
        --shadow-sm: 0 1px 4px rgba(59,42,26,0.07);
        --shadow:    0 4px 18px rgba(59,42,26,0.10);
        --shadow-lg: 0 8px 36px rgba(59,42,26,0.14);
    }

    /* ── BASE ── */
    html, body, .stApp {
        font-family: 'DM Sans', system-ui, sans-serif !important;
        background: var(--bg) !important;
        color: var(--text) !important;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', Georgia, serif !important;
        color: var(--primary) !important;
        letter-spacing: -0.015em;
    }
    a { color: var(--bronze-darker) !important; text-decoration: none; }
    a:hover { color: var(--bronze-dark) !important; text-decoration: underline; }

    /* ── HIDE STREAMLIT CHROME ── */
    [data-testid="stHeader"] {
        background: transparent !important;
        border-bottom: none !important;
    }
    [data-testid="stToolbar"]    { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    footer                       { display: none !important; }
    #MainMenu                    { display: none !important; }

    /* ── FORCE SIDEBAR ALWAYS OPEN — hide every toggle control ── */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"],
    [data-testid="baseButton-headerNoPadding"],
    button[aria-label="Close sidebar"],
    button[aria-label="Collapse sidebar"] {
        display: none !important;
    }
    /* Lock sidebar width so it can never slide away */
    section[data-testid="stSidebar"] {
        transform: none !important;
        min-width: 250px !important;
        width: 250px !important;
        flex-shrink: 0 !important;
    }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] {
        background: var(--sidebar-bg) !important;
        border-right: 1px solid rgba(212,163,115,0.18) !important;
        box-shadow: 2px 0 16px rgba(59,42,26,0.1) !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 0 !important;
    }
    [data-testid="stSidebar"] .stMarkdown p {
        color: #E9EDC9 !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    /* Sidebar nav buttons */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: rgba(233,237,201,0.72) !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.93rem !important;
        padding: 10px 14px !important;
        transition: background 0.15s, color 0.15s !important;
        width: 100% !important;
        text-align: left !important;
        height: auto !important;
        min-height: 0 !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(212,163,115,0.14) !important;
        color: #FEFAE0 !important;
    }
    .nav-active-btn > div > button, .nav-active-btn button {
        background: rgba(212,163,115,0.2) !important;
        color: #FEFAE0 !important;
        font-weight: 700 !important;
        border-left: 3px solid #D4A373 !important;
        padding-left: 11px !important;
    }

    /* ── MAIN CONTAINER ── */
    .block-container {
        padding-top: 2.5rem !important;
        padding-left: 2.8rem !important;
        padding-right: 2.8rem !important;
        max-width: 1180px !important;
    }

    /* ── HERO ── */
    .hero {
        background: linear-gradient(135deg, #3B2A1A 0%, #4A3728 55%, #5C4A32 100%);
        border-radius: var(--radius-lg);
        padding: 52px 48px;
        margin-bottom: 32px;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(212,163,115,0.18);
    }
    .hero::before {
        content: '';
        position: absolute; top: -45%; right: -6%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(212,163,115,0.18) 0%, transparent 68%);
        border-radius: 50%; pointer-events: none;
    }
    .hero-badge {
        display: inline-flex; align-items: center; gap: 7px;
        background: rgba(212,163,115,0.15); border: 1px solid rgba(212,163,115,0.3);
        color: #D4A373; font-size: 0.72rem; font-weight: 700;
        padding: 4px 14px; border-radius: 999px; margin-bottom: 20px;
        letter-spacing: 0.08em; text-transform: uppercase;
        font-family: 'DM Sans', sans-serif; position: relative;
    }
    .hero h1 {
        font-family: 'Playfair Display', serif !important;
        font-size: 2.6rem !important; font-weight: 800 !important;
        color: #FEFAE0 !important; margin: 0 0 14px !important;
        line-height: 1.18 !important; letter-spacing: -0.025em !important;
        position: relative;
    }
    .hero h1 span { color: #D4A373; }
    .hero p {
        font-size: 1rem; color: #CCD5AE !important;
        margin: 0; line-height: 1.72;
        max-width: 540px; position: relative;
        font-family: 'DM Sans', sans-serif;
    }

    /* ── PAGE HEADER ── */
    .page-header {
        margin-bottom: 28px; padding-bottom: 18px;
        border-bottom: 2px solid var(--border);
    }
    .page-header h2 { font-size: 1.65rem; font-weight: 700; margin: 0 0 5px; }
    .page-header p  { color: var(--muted); font-size: 0.93rem; margin: 0; }

    /* ── FORM CARD ── */
    .form-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-lg);
        padding: 36px 40px;
        box-shadow: var(--shadow-sm);
        margin-top: 8px;
    }

    /* ── INPUTS ── */
    .stTextInput input,
    .stTextArea textarea {
        background: #FAEDCD !important;
        border: 1.5px solid #BF8C5A !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.93rem !important;
        color: #4A3728 !important;
        -webkit-text-fill-color: #4A3728 !important;
        padding: 10px 14px !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: #D4A373 !important;
        box-shadow: 0 0 0 3px rgba(212,163,115,0.18) !important;
        outline: none !important;
        background: #FEF8E8 !important;
    }
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: rgba(107,87,66,0.55) !important;
        -webkit-text-fill-color: rgba(107,87,66,0.55) !important;
        font-style: italic !important;
    }
    /* ── TEXTAREA placeholder visible fix ── */
    .stTextArea textarea:not(:focus)::placeholder {
        opacity: 1 !important;
    }
        /* Labels (main area) */
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stMultiSelect label {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
        color: var(--text-light) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
    }
    /* Radio label override — restore normal casing */
    .stRadio label {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        color: var(--text-light) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
    }

    /* ── DEPTH CLICK TRIGGERS — invisible buttons that sit below the HTML pill ── */
    .depth-click-btn > div > button {
        background: transparent !important;
        color: #6B5742 !important;
        border: 1.5px solid #CCD5AE !important;
        border-radius: 7px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        padding: 6px 0 !important;
        width: 100% !important;
        opacity: 0.65 !important;
        transition: opacity 0.15s, border-color 0.15s !important;
    }
    .depth-click-btn > div > button:hover {
        opacity: 1 !important;
        border-color: #D4A373 !important;
        background: rgba(212,163,115,0.06) !important;
        color: #3B2A1A !important;
    }
    /* ── RADIO — option text always visible ── */
    /* The text lives in a <p> inside the label wrapper */
    .stRadio > div[role="radiogroup"] > label p,
    .stRadio > div[role="radiogroup"] > label span,
    .stRadio [data-baseweb="radio"] ~ div p,
    .stRadio label p {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.93rem !important;
        font-weight: 500 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
    }
    /* Radio circle — unselected */
    .stRadio [data-baseweb="radio"] > div:first-child {
        border: 2px solid var(--border) !important;
        background-color: var(--cornsilk) !important;
        width: 18px !important;
        height: 18px !important;
        border-radius: 50% !important;
    }
    /* Radio circle — selected: target via parent aria-checked */
    .stRadio [role="radio"][aria-checked="true"] > div:first-child {
        border-color: var(--bronze) !important;
        background-color: var(--bronze) !important;
    }
    /* Inner dot for selected state */
    .stRadio [role="radio"][aria-checked="true"] > div:first-child::after {
        content: '';
        display: block;
        width: 7px; height: 7px;
        background: #3B2A1A;
        border-radius: 50%;
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
    }
    .stRadio [role="radio"] > div:first-child { position: relative; }
    /* Hover */
    .stRadio [role="radio"]:hover > div:first-child {
        border-color: var(--bronze) !important;
        box-shadow: 0 0 0 3px rgba(212,163,115,0.15) !important;
    }

    /* ── MULTISELECT / SELECTBOX ── */
    [data-baseweb="select"] > div {
        background: #FEFAE0 !important;
        border: 1.5px solid #CCD5AE !important;
        border-radius: 7px !important;
        font-family: 'DM Sans', sans-serif !important;
        color: #4A3728 !important;
    }
    [data-baseweb="select"] > div:focus-within {
        border-color: #D4A373 !important;
        box-shadow: 0 0 0 3px rgba(212,163,115,0.15) !important;
    }
    /* All text nodes inside select — nuclear override so placeholder div is always visible */
    [data-baseweb="select"] *:not(svg):not(path) {
        color: #4A3728 !important;
        -webkit-text-fill-color: #4A3728 !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    /* Re-assert tag text separately */
    [data-baseweb="tag"] *:not(svg):not(path) {
        color: #3B2A1A !important;
        -webkit-text-fill-color: #3B2A1A !important;
        font-weight: 600 !important;
    }
    /* Placeholder text — muted italic */
    [data-baseweb="select"] input::placeholder {
        color: rgba(107,87,66,0.55) !important;
        -webkit-text-fill-color: rgba(107,87,66,0.55) !important;
        font-style: italic !important;
    }
    /* Kill the blue browser selection highlight globally */
    ::selection {
        background: rgba(212,163,115,0.28) !important;
        color: #3B2A1A !important;
    }
    ::-moz-selection {
        background: rgba(212,163,115,0.28) !important;
        color: #3B2A1A !important;
    }
    /* Specifically nuke blue focus outline on select wrapper */
    [data-baseweb="select"] *:focus,
    [data-baseweb="select"] *:focus-visible {
        outline: none !important;
        box-shadow: none !important;
    }
    [data-baseweb="tag"] {
        background: var(--surface-2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 5px !important;
    }
    [data-baseweb="tag"] span {
        color: var(--primary) !important;
        -webkit-text-fill-color: var(--primary) !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
    }
    [data-baseweb="tag"] button svg { fill: var(--text-light) !important; }
    /* ── DROPDOWN POPOVER — literal hex so portal context resolves correctly ── */
    [data-baseweb="popover"],
    [data-baseweb="popover"] [data-baseweb="menu"],
    [data-baseweb="popover"] ul {
        background: #FEFAE0 !important;
        border: 1px solid #CCD5AE !important;
        border-radius: 10px !important;
        box-shadow: 0 8px 32px rgba(59,42,26,0.14) !important;
    }
    /* Every text node inside the popover */
    [data-baseweb="popover"] *:not(svg):not(path) {
        color: #4A3728 !important;
        -webkit-text-fill-color: #4A3728 !important;
        font-family: 'DM Sans', sans-serif !important;
        background-color: transparent !important;
    }
    /* Individual option rows */
    [data-baseweb="popover"] li,
    [role="option"] {
        background: transparent !important;
        color: #4A3728 !important;
        -webkit-text-fill-color: #4A3728 !important;
        padding: 9px 14px !important;
        border-radius: 6px !important;
        margin: 2px 4px !important;
        font-size: 0.92rem !important;
        cursor: pointer !important;
        transition: background 0.12s !important;
    }
    [role="option"]:hover,
    [data-baseweb="popover"] li:hover {
        background: #E9EDC9 !important;
        color: #3B2A1A !important;
        -webkit-text-fill-color: #3B2A1A !important;
    }
    [role="option"][aria-selected="true"] {
        background: rgba(212,163,115,0.18) !important;
        color: #3B2A1A !important;
        -webkit-text-fill-color: #3B2A1A !important;
        font-weight: 600 !important;
    }
    /* Checkbox inside multi-select options */
    [role="option"] input[type="checkbox"] { accent-color: #D4A373 !important; }

    /* ── BUTTONS ── */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button {
        background: var(--bronze) !important;
        color: #3B2A1A !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.94rem !important;
        padding: 11px 28px !important;
        box-shadow: 0 2px 10px rgba(212,163,115,0.28) !important;
        transition: background 0.15s, box-shadow 0.15s, transform 0.15s !important;
        letter-spacing: 0.01em !important;
        cursor: pointer !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button:hover {
        background: var(--bronze-dark) !important;
        box-shadow: 0 4px 16px rgba(212,163,115,0.42) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="primary"]:active,
    .stFormSubmitButton > button:active {
        transform: translateY(0) !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: var(--surface) !important;
        color: var(--bronze-darker) !important;
        border: 1.5px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.93rem !important;
        padding: 10px 22px !important;
        transition: all 0.15s !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background: var(--surface-2) !important;
        border-color: var(--bronze) !important;
        color: var(--primary) !important;
    }

    /* ── TABS ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 3px;
        background: var(--surface) !important;
        border-radius: var(--radius) !important;
        padding: 4px !important;
        border: 1px solid var(--border) !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--muted) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 8px 20px !important;
        border-radius: 7px !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.15s !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text) !important;
        background: var(--surface-2) !important;
    }
    .stTabs [aria-selected="true"] {
        color: var(--primary) !important;
        background: var(--beige) !important;
        box-shadow: var(--shadow-sm) !important;
        border-bottom: 2px solid var(--bronze) !important;
    }
    .stTabs [data-baseweb="tab-panel"] { padding: 20px 0 !important; }
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ── EXPANDER ── */
    [data-testid="stExpander"] details summary {
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 10px 16px !important;
    }
    [data-testid="stExpander"] details summary:hover {
        background: var(--surface-2) !important;
        border-color: var(--bronze) !important;
    }
    [data-testid="stExpander"] details summary p,
    [data-testid="stExpander"] details summary span { color: var(--text) !important; }

    /* ── CONTENT CARDS ── */
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
        transition: box-shadow 0.15s, transform 0.15s;
    }
    .metric-card:hover { box-shadow: var(--shadow); transform: translateY(-1px); }

    .comp-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 22px 24px;
        margin-bottom: 14px;
        box-shadow: var(--shadow-sm);
        transition: all 0.15s;
    }
    .comp-card:hover { box-shadow: var(--shadow); transform: translateY(-2px); }
    .comp-top {
        border: 1.5px solid var(--bronze);
        box-shadow: 0 4px 18px rgba(212,163,115,0.14);
        background: linear-gradient(135deg, var(--surface) 0%, rgba(212,163,115,0.05) 100%);
    }
    .comp-card h4 {
        margin: 0 0 8px !important;
        font-size: 1.02rem !important;
        font-family: 'Playfair Display', serif !important;
        color: var(--primary) !important;
    }

    /* ── SUMMARY PILL ── */
    .summary-pill {
        background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 18px 24px; margin-bottom: 24px;
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

    /* ── TERMINAL LOG ── */
    .term {
        background: #3B2A1A; color: #CCD5AE;
        border: 1px solid rgba(212,163,115,0.18);
        padding: 20px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        white-space: pre-wrap; line-height: 1.65;
        border-radius: var(--radius); font-size: 0.82rem; overflow-x: auto;
    }

    /* ── CHAT ── */
    .chat-container { max-width: 800px; margin: 0 auto; }
    .chat-row       { margin: 14px 0; display: flex; gap: 10px; align-items: flex-end; }
    .chat-user      { justify-content: flex-end; }
    .chat-agent     { justify-content: flex-start; }
    .user-bubble {
        background: linear-gradient(135deg, #4A3728 0%, #3B2A1A 100%);
        color: #FEFAE0; max-width: 72%;
        padding: 12px 18px; border-radius: 16px 16px 4px 16px;
        font-size: 0.92rem; line-height: 1.6;
        box-shadow: 0 2px 10px rgba(59,42,26,0.18);
        font-family: 'DM Sans', sans-serif;
    }
    .agent-avatar {
        width: 34px; height: 34px; border-radius: 10px; flex-shrink: 0;
        background: linear-gradient(135deg, #D4A373 0%, #BF8C5A 100%);
        color: #3B2A1A; font-family: 'Playfair Display', serif; font-weight: 700;
        display: flex; align-items: center; justify-content: center;
        font-size: 1rem; box-shadow: 0 2px 8px rgba(212,163,115,0.3);
    }
    .agent-bubble {
        background: var(--surface); color: var(--text);
        border: 1px solid var(--border); max-width: 72%;
        padding: 14px 18px; border-radius: 16px 16px 16px 4px;
        font-size: 0.92rem; line-height: 1.65;
        box-shadow: var(--shadow-sm); font-family: 'DM Sans', sans-serif;
    }
    .chat-empty {
        text-align: center; padding: 56px 24px;
        color: var(--muted); font-size: 0.94rem;
        font-family: 'DM Sans', sans-serif;
    }

    /* ── WELCOME ── */
    .welcome {
        border: 1.5px dashed var(--border);
        background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
        padding: 64px 40px; text-align: center;
        border-radius: var(--radius-lg); margin-top: 12px;
    }
    .welcome h3 {
        font-size: 1.45rem; font-weight: 700; margin: 0 0 10px;
        color: var(--primary) !important;
        font-family: 'Playfair Display', serif !important;
    }
    .welcome p { color: var(--muted) !important; font-size: 0.95rem; margin: 0; line-height: 1.7; }

    /* ── MISC ── */
    [data-testid="stAlert"] {
        border-radius: var(--radius) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    p, li, span { font-family: 'DM Sans', sans-serif; }
    hr { border-color: var(--border) !important; margin: 20px 0 !important; }

    /* ── PROGRESS BAR — earthy bronze ── */
    [data-testid="stProgressBar"] {
        background: #E9EDC9 !important;
        border-radius: 999px !important;
        height: 6px !important;
        overflow: hidden !important;
    }
    [data-testid="stProgressBar"] > div {
        background: #E9EDC9 !important;
        border-radius: 999px !important;
    }
    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, #D4A373 0%, #BF8C5A 60%, #D4A373 100%) !important;
        background-size: 200% 100% !important;
        border-radius: 999px !important;
        animation: bronzeShimmer 1.8s ease-in-out infinite !important;
    }
    @keyframes bronzeShimmer {
        0%   { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    /* Status widget left accent bar */
    [data-testid="stStatus"] {
        border-left: 3px solid #D4A373 !important;
        border-radius: 0 var(--radius) var(--radius) 0 !important;
        background: #FEFAE0 !important;
        box-shadow: var(--shadow-sm) !important;
    }
    [data-testid="stStatus"] summary,
    [data-testid="stStatus"] summary * {
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 600 !important;
        color: #4A3728 !important;
    }
    /* Progress text label */
    [data-testid="stProgressBar"] + div p,
    div[data-testid="stText"] p {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.84rem !important;
        color: #8B7355 !important;
    }

    /* ── FOOTER ── */
    .site-footer {
        margin-top: 72px;
        border-top: 1.5px solid var(--border);
        padding: 48px 0 32px;
    }
    .footer-grid {
        display: grid;
        grid-template-columns: 1.8fr 1fr 1fr;
        gap: 40px;
        margin-bottom: 40px;
    }
    .footer-brand-name {
        font-family: 'Playfair Display', serif;
        font-weight: 800;
        font-size: 1.25rem;
        color: #3B2A1A;
        margin: 0 0 8px;
        display: flex;
        align-items: center;
        gap: 9px;
    }
    .footer-brand-icon {
        background: #D4A373;
        color: #3B2A1A;
        border-radius: 7px;
        width: 28px; height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 900;
        font-size: 0.85rem;
        flex-shrink: 0;
        font-family: 'DM Sans', sans-serif;
    }
    .footer-tagline {
        font-size: 0.88rem;
        color: #8B7355;
        line-height: 1.65;
        max-width: 300px;
        margin: 0 0 20px;
        font-family: 'DM Sans', sans-serif;
    }
    .footer-badge-row {
        display: flex;
        gap: 7px;
        flex-wrap: wrap;
    }
    .footer-badge {
        background: #E9EDC9;
        border: 1px solid #CCD5AE;
        color: #6B5742;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 999px;
        font-family: 'DM Sans', sans-serif;
        letter-spacing: 0.04em;
    }
    .footer-col-title {
        font-family: 'DM Sans', sans-serif;
        font-weight: 700;
        font-size: 0.72rem;
        color: #8B7355;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 0 0 14px;
    }
    .footer-link-list {
        list-style: none;
        padding: 0; margin: 0;
        display: flex;
        flex-direction: column;
        gap: 9px;
    }
    .footer-link-list li {
        font-family: 'DM Sans', sans-serif;
        font-size: 0.88rem;
        color: #6B5742;
        cursor: pointer;
        transition: color 0.15s;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .footer-link-list li:hover { color: #A0733D; }
    .footer-link-list li::before {
        content: '›';
        color: #D4A373;
        font-weight: 700;
    }
    .footer-bottom {
        border-top: 1px solid #CCD5AE;
        padding-top: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
    }
    .footer-copy {
        font-size: 0.8rem;
        color: #8B7355;
        font-family: 'DM Sans', sans-serif;
    }
    .footer-stack {
        display: flex;
        gap: 6px;
        align-items: center;
        flex-wrap: wrap;
    }
    .footer-stack-label {
        font-size: 0.75rem;
        color: #8B7355;
        font-family: 'DM Sans', sans-serif;
        margin-right: 2px;
    }
    .footer-stack-pill {
        background: #FAEDCD;
        border: 1px solid #CCD5AE;
        color: #6B5742;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 3px 9px;
        border-radius: 5px;
        font-family: 'DM Sans', sans-serif;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ── HELPERS ─────────────────────────────────────────────────

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
            html.append("<div style='margin:6px 0'></div>")
            continue
        is_bullet = (
            s.startswith(("* ", "- ", "• ", "– "))
            or (s and s[0].isdigit() and len(s) > 2 and s[1] == ".")
        )
        if is_bullet:
            clean = (
                s[2:].strip() if s[:2] in ("* ", "- ", "• ", "– ")
                else s.split(".", 1)[1].strip()
            )
            if not in_list:
                html.append("<div style='margin:10px 0'>"); in_list = True
            html.append(
                f"<div style='margin:5px 0;padding-left:14px;border-left:3px solid #D4A373;'>"
                f"<span style='color:#D4A373;font-weight:700;margin-right:6px;'>›</span>"
                f"{escape(clean)}</div>"
            )
        else:
            if in_list:
                html.append("</div>"); in_list = False
            heading = s.endswith(":") or (len(s.split()) <= 6 and s.isupper())
            if heading:
                html.append(
                    f"<div style='margin:12px 0 5px;font-weight:700;color:#3B2A1A;"
                    f"font-size:0.9rem;font-family:Playfair Display,serif;'>{escape(s)}</div>"
                )
            else:
                html.append(f"<div style='margin:6px 0;line-height:1.65;color:#4A3728;'>{escape(s)}</div>")
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


def compute_opportunity_score(report) -> dict:
    """Derive 0-100 opportunity score from report text signals."""
    text = " ".join(filter(None, [
        report.market_overview or "",
        " ".join(report.pain_points or []),
        " ".join(report.entry_recommendations or []),
        " ".join(report.pricing_models or []),
        " ".join(
            f"{c.description or ''} {c.strengths or ''} {c.weaknesses or ''}"
            for c in (report.competitors or [])
        ),
    ])).lower()

    # Market Size (0–25)
    ms = 12
    for kw, v in [("trillion",25),("billion",24),("bn ",22),("crore",20),("million",18),
                  ("large market",20),("growing market",20),("expanding",18),
                  ("niche",10),("small market",8)]:
        if kw in text: ms = max(ms, v); break

    # Competition (0–25) — fewer / weaker competitors = higher score
    n = len(report.competitors or [])
    cs = 22 if n == 0 else 18 if n <= 2 else 13 if n <= 4 else 8
    if any(k in text for k in ["monopoly","dominated by","google dominat","amazon dominat"]):
        cs = max(4, cs - 5)

    # Entry Difficulty (0–25) — easy entry = higher score
    easy = sum(1 for k in ["low barrier","easy","simple","mvp","bootstrap","no-code","api","saas","b2c","d2c"] if k in text)
    hard = sum(1 for k in ["regulated","regulatory","capital intensive","patent","hardware","infrastructure","license required","fda","rbi approval"] if k in text)
    ed = min(24, max(6, 14 + easy * 2 - hard * 3))

    # Timing (0–25) — emerging / AI / trend = higher
    ts = 14
    for kw, v in [("2026",24),("2025",22),("emerging",23),("early stage",23),("nascent",22),
                  ("ai-powered",22),("ai powered",22),("growing",18),("trend",18),
                  ("saturated",8),("mature",10),("declining",5)]:
        if kw in text: ts = max(ts, v); break

    total = ms + cs + ed + ts
    label = "Strong" if total >= 70 else "Moderate" if total >= 50 else "Challenging"
    color = "#4A7C8E" if total >= 70 else "#D4A373" if total >= 50 else "#B83232"
    return dict(total=total, market_size=ms, competition=cs,
                entry_difficulty=ed, timing=ts, label=label, color=color)


def render_score_card(report) -> None:
    s = compute_opportunity_score(report)
    total   = s["total"]
    color   = s["color"]
    label   = s["label"]

    def bar(val: int, max_val: int = 25, c: str = color) -> str:
        pct = round(val / max_val * 100)
        return (
            f"<div style='flex:1;background:#E9EDC9;border-radius:999px;height:7px;overflow:hidden;'>"
            f"<div style='width:{pct}%;height:100%;background:{c};border-radius:999px;"
            f"transition:width 0.6s ease;'></div></div>"
        )

    def row(label_text: str, val: int) -> str:
        return (
            f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:11px;'>"
            f"<div style='width:130px;font-size:0.8rem;font-weight:600;color:#6B5742;"
            f"font-family:DM Sans,sans-serif;flex-shrink:0;'>{label_text}</div>"
            f"{bar(val)}"
            f"<div style='width:40px;text-align:right;font-size:0.8rem;font-weight:700;"
            f"color:{color};font-family:DM Sans,sans-serif;flex-shrink:0;'>{val}/25</div>"
            f"</div>"
        )

    # Circular score ring via conic-gradient
    pct  = round(total / 100 * 360)
    ring = (
        f"background: conic-gradient({color} 0deg {pct}deg, #E9EDC9 {pct}deg 360deg);"
    )

    html = (
        f"<div style='background:linear-gradient(135deg,#FAEDCD 0%,#F5F0D8 100%);"
        f"border:1px solid #CCD5AE;border-radius:14px;padding:28px 32px;"
        f"box-shadow:0 2px 12px rgba(59,42,26,0.07);margin-bottom:24px;"
        f"display:flex;gap:40px;align-items:center;flex-wrap:wrap;'>"

        # Left — circular score
        f"<div style='display:flex;flex-direction:column;align-items:center;flex-shrink:0;'>"
        f"<div style='width:110px;height:110px;border-radius:50%;{ring}"
        f"display:flex;align-items:center;justify-content:center;'>"
        f"<div style='width:86px;height:86px;border-radius:50%;background:#FAEDCD;"
        f"display:flex;flex-direction:column;align-items:center;justify-content:center;"
        f"box-shadow:0 2px 8px rgba(59,42,26,0.1);'>"
        f"<span style='font-family:Playfair Display,serif;font-weight:800;font-size:1.75rem;"
        f"color:{color};line-height:1;'>{total}</span>"
        f"<span style='font-size:0.65rem;color:#8B7355;font-family:DM Sans,sans-serif;"
        f"font-weight:600;letter-spacing:0.05em;'>/100</span>"
        f"</div></div>"
        f"<div style='margin-top:10px;background:{color};color:#fff;"
        f"font-size:0.7rem;font-weight:700;padding:3px 12px;border-radius:999px;"
        f"font-family:DM Sans,sans-serif;letter-spacing:0.06em;'>{label.upper()}</div>"
        f"<div style='margin-top:5px;font-size:0.7rem;color:#8B7355;"
        f"font-family:DM Sans,sans-serif;'>Opportunity Score</div>"
        f"</div>"

        # Right — breakdown bars
        f"<div style='flex:1;min-width:220px;'>"
        f"<div style='font-family:DM Sans,sans-serif;font-size:0.7rem;font-weight:700;"
        f"color:#8B7355;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:16px;'>"
        f"Score Breakdown</div>"
        + row("Market Size",       s["market_size"])
        + row("Competition Level", s["competition"])
        + row("Entry Difficulty",  s["entry_difficulty"])
        + row("Timing",            s["timing"])
        + f"</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def accent_card(content: str, border: str = "#D4A373", tint: str = "rgba(212,163,115,0.05)") -> None:
    st.markdown(
        f"<div class='metric-card' style='border-left:3px solid {border};"
        f"background:linear-gradient(135deg,#FAEDCD 0%,{tint} 100%);'>"
        f"{content}</div>",
        unsafe_allow_html=True,
    )


# ── FOOTER ─────────────────────────────────────────────────

def generate_pdf_html(report, depth: str) -> str:
    """Build a beautifully styled, print-ready HTML page for PDF export."""
    import datetime
    score = compute_opportunity_score(report)
    now   = datetime.datetime.now().strftime("%B %d, %Y")

    def _bar(val: int, color: str) -> str:
        pct = round(val / 25 * 100)
        return (
            f"<div style='flex:1;background:#E9EDC9;border-radius:4px;height:8px;'>"
            f"<div style='width:{pct}%;height:100%;background:{color};border-radius:4px;'></div></div>"
        )

    def _row(label: str, val: int) -> str:
        return (
            f"<tr><td style='padding:4px 10px 4px 0;font-size:11px;color:#6B5742;"
            f"font-family:DM Sans,sans-serif;white-space:nowrap;'>{label}</td>"
            f"<td style='padding:4px 0;width:100%;'>{_bar(val, score['color'])}</td>"
            f"<td style='padding:4px 0 4px 10px;font-size:11px;font-weight:700;"
            f"color:{score["color"]};font-family:DM Sans,sans-serif;'>{val}/25</td></tr>"
        )

    comps_html = ""
    for i, c in enumerate(report.competitors or [], 1):
        sp = to_points(c.strengths); wp = to_points(c.weaknesses)
        s_items = "".join(f"<li>{escape(p)}</li>" for p in sp)
        w_items = "".join(f"<li>{escape(p)}</li>" for p in wp)
        sw_html = ""
        if sp: sw_html += f"<b>Strengths</b><ul style='margin:4px 0 8px;padding-left:18px;'>{s_items}</ul>"
        if wp: sw_html += f"<b>Weaknesses</b><ul style='margin:4px 0 8px;padding-left:18px;'>{w_items}</ul>"
        url_tag = f"<a href='{c.url}' style='color:#A0733D;'>Visit →</a>" if (c.url and c.url.strip()) else ""
        comps_html += (
            f"<div style='border:1px solid #CCD5AE;border-radius:8px;padding:14px 18px;"
            f"margin-bottom:12px;background:#FEFAE0;page-break-inside:avoid;'>"
            f"<div style='font-weight:800;font-size:14px;color:#3B2A1A;margin-bottom:4px;'>#{i} {escape(c.name or '')}</div>"
            f"<p style='margin:4px 0 8px;font-size:12px;color:#4A3728;'>{escape(c.description or '')}</p>"
            f"{url_tag}{sw_html}</div>"
        )

    bullets = lambda items: "".join(f"<li style='margin-bottom:6px;'>{escape(str(p))}</li>" for p in (items or []))
    sources = [s for s in (report.sources or []) if s and s.strip()]
    src_html = "".join(f"<li><a href='{s}' style='color:#A0733D;'>{escape(s)}</a></li>" for s in sources)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Market Report — {escape(report.idea)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=Playfair+Display:wght@700;800&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'DM Sans', sans-serif; background: #FEFAE0; color: #3B2A1A; padding: 32px 40px; max-width: 860px; margin: auto; }}
  h1 {{ font-family: 'Playfair Display', serif; font-size: 26px; color: #3B2A1A; margin-bottom: 4px; }}
  h2 {{ font-family: 'Playfair Display', serif; font-size: 18px; color: #4A3728; margin: 28px 0 10px; border-bottom: 2px solid #CCD5AE; padding-bottom: 6px; }}
  p  {{ font-size: 13px; line-height: 1.7; color: #4A3728; margin-bottom: 10px; }}
  li {{ font-size: 13px; line-height: 1.65; color: #4A3728; }}
  .meta {{ display:flex;gap:24px;flex-wrap:wrap;margin:10px 0 20px;background:#FAEDCD;border:1px solid #CCD5AE;border-radius:8px;padding:12px 18px; }}
  .meta-item {{ display:flex;flex-direction:column;gap:2px; }}
  .meta-label {{ font-size:9px;font-weight:700;color:#8B7355;text-transform:uppercase;letter-spacing:0.1em; }}
  .meta-value {{ font-size:13px;font-weight:600;color:#3B2A1A; }}
  .score-ring {{ display:inline-block;width:80px;height:80px;border-radius:50%;background:conic-gradient({score['color']} 0deg {round(score['total']/100*360)}deg, #E9EDC9 {round(score['total']/100*360)}deg);display:flex;align-items:center;justify-content:center;margin-right:24px;vertical-align:middle; }}
  .score-inner {{ width:62px;height:62px;border-radius:50%;background:#FAEDCD;display:flex;flex-direction:column;align-items:center;justify-content:center; }}
  ul {{ padding-left:20px;margin-bottom:12px; }}
  .footer {{ margin-top:40px;border-top:1px solid #CCD5AE;padding-top:14px;font-size:11px;color:#8B7355;text-align:center; }}
  @media print {{
    body {{ padding: 20px 24px; background: white; }}
    @page {{ margin: 1.5cm; size: A4; }}
  }}
</style></head>
<body>
<h1>Market Intelligence Report</h1>
<p style="font-size:14px;color:#6B5742;margin-top:4px;">{escape(report.idea)}</p>

<div class="meta">
  <div class="meta-item"><span class="meta-label">Generated</span><span class="meta-value">{now}</span></div>
  <div class="meta-item"><span class="meta-label">Region</span><span class="meta-value">{escape(report.region)}</span></div>
  <div class="meta-item"><span class="meta-label">Segment</span><span class="meta-value">{escape(report.segment)}</span></div>
  <div class="meta-item"><span class="meta-label">Depth</span><span class="meta-value">{depth}</span></div>
  <div class="meta-item"><span class="meta-label">Opportunity Score</span><span class="meta-value" style="color:{score['color']};">{score['total']}/100 — {score['label']}</span></div>
</div>

<h2>Opportunity Score Breakdown</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:4px;">
  {_row("Market Size", score['market_size'])}
  {_row("Competition Level", score['competition'])}
  {_row("Entry Difficulty", score['entry_difficulty'])}
  {_row("Timing", score['timing'])}
</table>

<h2>Market Overview</h2>
<p>{escape(report.market_overview or "No data available.")}</p>

<h2>Competitors</h2>
{comps_html}

<h2>Pricing Models</h2>
<ul>{bullets(report.pricing_models)}</ul>

<h2>Pain Points</h2>
<ul>{bullets(report.pain_points)}</ul>

<h2>Entry Strategy &amp; Recommendations</h2>
<ol style="padding-left:20px;">{bullets(report.entry_recommendations)}</ol>

{"<h2>Sources</h2><ul>" + src_html + "</ul>" if sources else ""}

<div class="footer">Generated by Udyama-AI · {now}</div>
</body></html>
"""



def render_footer() -> None:
    import datetime
    year = datetime.date.today().year
    # NOTE: HTML is built as a compact string — Streamlit's markdown parser converts
    # any line with 4+ leading spaces into a <pre> code block, so we must NOT indent.
    html = (
        "<div class='site-footer'>"
        "<div class='footer-grid'>"

        "<div>"
        "<div class='footer-brand-name'>"
        "<span class='footer-brand-icon'>&#9670;</span>Udyama-AI"
        "</div>"
        "<p class='footer-tagline'>"
        "AI-powered market intelligence for founders. "
        "Research your market, benchmark competitors, "
        "and craft your go-to-market strategy &mdash; in minutes."
        "</p>"
        "<div class='footer-badge-row'>"
        "<span class='footer-badge'>Multi-Agent AI</span>"
        "<span class='footer-badge'>Real-time Research</span>"
        "<span class='footer-badge'>GTM Strategy</span>"
        "</div>"
        "</div>"

        "<div>"
        "<p class='footer-col-title'>Navigate</p>"
        "<ul class='footer-link-list'>"
        "<li>Research</li>"
        "<li>Insights</li>"
        "<li>Follow-up Chat</li>"
        "</ul>"
        "</div>"

        "<div>"
        "<p class='footer-col-title'>What We Analyze</p>"
        "<ul class='footer-link-list'>"
        "<li>Market Overview</li>"
        "<li>Competitor Landscape</li>"
        "<li>Pricing Models</li>"
        "<li>Pain Points</li>"
        "<li>Entry Strategy</li>"
        "</ul>"
        "</div>"

        "</div>"

        "<div class='footer-bottom'>"
        f"<span class='footer-copy'>&copy; {year} Udyama-AI. Built for founders, by founders.</span>"
        "<div class='footer-stack'>"
        "<span class='footer-stack-label'>Powered by</span>"
        "<span class='footer-stack-pill'>Streamlit</span>"
        "<span class='footer-stack-pill'>CrewAI</span>"
        "<span class='footer-stack-pill'>Gemini</span>"
        "<span class='footer-stack-pill'>Serper</span>"
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ── SIDEBAR — navigation only ────────────────────────────────

with st.sidebar:
    st.markdown(
        """
        <div style='padding:32px 20px 24px;border-bottom:1px solid rgba(212,163,115,0.18);
                    margin-bottom:4px;'>
            <div style='display:flex;align-items:center;gap:10px;'>
                <div style='background:#D4A373;color:#3B2A1A;border-radius:8px;
                            width:34px;height:34px;display:flex;align-items:center;
                            justify-content:center;font-weight:900;font-size:1rem;
                            flex-shrink:0;font-family:DM Sans,sans-serif;'>◆</div>
                <div>
                    <div style='font-family:Playfair Display,serif;font-weight:800;
                                font-size:1.15rem;color:#FEFAE0;line-height:1.2;'>
                        Udyama-AI</div>
                    <div style='font-family:DM Sans,sans-serif;font-size:0.66rem;
                                color:rgba(233,237,201,0.45);letter-spacing:0.07em;
                                text-transform:uppercase;font-weight:600;margin-top:2px;'>
                        Market Intelligence</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='padding:16px 20px 6px;font-size:0.65rem;color:rgba(233,237,201,0.35);"
        "font-weight:700;letter-spacing:0.11em;text-transform:uppercase;"
        "font-family:DM Sans,sans-serif;'>Menu</div>",
        unsafe_allow_html=True,
    )

    for label, target in [("Research", "Research"), ("Insights", "Insights"), ("Follow-up", "Follow-up")]:
        if st.button(label, key=f"nav_{target.lower()}", use_container_width=True):
            st.session_state.view = target
            st.rerun()
    active_view = st.session_state.view
    st.markdown(
        f"""<script>(function(){{
            var apply=function(){{
                var btns=parent.document.querySelectorAll(
                    '[data-testid="stSidebar"] [data-testid="stButton"] button');
                btns.forEach(function(b){{
                    var w=b.closest('[data-testid="stButton"]');
                    if(!w)return;
                    if(b.innerText.trim()==='{active_view}')
                        w.classList.add('nav-active-btn');
                    else w.classList.remove('nav-active-btn');
                }});
            }};apply();setTimeout(apply,120);
        }})();</script>""",
        unsafe_allow_html=True,
    )

    # Active report card at bottom — normal flow, no absolute positioning
    if st.session_state.report is not None:
        r = st.session_state.report
        st.markdown(
            f"""
            <div style='margin:24px 12px 16px;padding:14px;border-radius:8px;
                        background:rgba(0,0,0,0.12);border:1px solid rgba(212,163,115,0.15);'>
                <div style='font-size:0.64rem;color:rgba(233,237,201,0.38);font-weight:700;
                            letter-spacing:0.1em;text-transform:uppercase;
                            font-family:DM Sans,sans-serif;margin-bottom:7px;'>Active Report</div>
                <div style='font-size:0.8rem;color:rgba(233,237,201,0.65);
                            font-family:DM Sans,sans-serif;line-height:1.45;'>
                    {escape(r.idea[:55])}{'…' if len(r.idea)>55 else ''}</div>
                <div style='margin-top:8px;display:flex;gap:5px;flex-wrap:wrap;'>
                    <span style='background:rgba(212,163,115,0.18);color:#D4A373;font-size:0.68rem;
                        padding:2px 8px;border-radius:4px;font-family:DM Sans,sans-serif;
                        font-weight:600;'>{escape(r.region)}</span>
                    <span style='background:rgba(212,163,115,0.18);color:#D4A373;font-size:0.68rem;
                        padding:2px 8px;border-radius:4px;font-family:DM Sans,sans-serif;
                        font-weight:600;'>{st.session_state.depth}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── RESEARCH VIEW ────────────────────────────────────────────

if st.session_state.view == "Research":

    st.markdown(
        """
        <div class='hero'>
            <div class='hero-badge'>◆ AI-Powered Research Agent</div>
            <h1>Market <span>Intelligence</span><br>at Founder Speed</h1>
            <p>Describe your startup idea below and configure your target market.
            Our multi-agent system generates deep competitive analysis,
            pricing insights, and go-to-market strategy in minutes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


    # ── All widgets outside form so conditionals re-render immediately ──

    idea_val = st.text_area(
        "Startup Idea",
        value=st.session_state.idea,
        placeholder="Describe your core value proposition and the problem you are solving…",
        height=120,
        key="idea_widget",
    )

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
    col_r, col_s = st.columns(2, gap="large")

    region_options = ["India", "US", "EU", "Southeast Asia", "Global", "Other"]
    with col_r:
        selected_regions = st.multiselect(
            "Target Region(s)",
            region_options,
            default=[r for r in st.session_state.regions_selected if r in region_options],
            key="regions_widget",
        )

    segment_options = [
        "Consumers", "SMEs", "Enterprises", "Students",
        "Healthcare", "Farmers", "Gig Workers", "Other",
    ]
    with col_s:
        selected_segments = st.multiselect(
            "Target Segment(s)",
            segment_options,
            default=[s for s in st.session_state.segments_selected if s in segment_options],
            key="segments_widget",
        )

    # Custom inputs — always rendered in columns, visible only when Other selected
    col_ro, col_so = st.columns(2, gap="large")
    with col_ro:
        if "Other" in selected_regions:
            region_other_val = st.text_input(
                "Custom Region(s)",
                value=st.session_state.region_other,
                placeholder="e.g., Middle East, Africa",
                key="region_other_widget",
            )
        else:
            region_other_val = st.session_state.region_other
    with col_so:
        if "Other" in selected_segments:
            segment_other_val = st.text_input(
                "Custom Segment(s)",
                value=st.session_state.segment_other,
                placeholder="e.g., NGOs, Governments",
                key="segment_other_widget",
            )
        else:
            segment_other_val = st.session_state.segment_other

    # ── Depth — inline HTML pill toggle (no Streamlit button CSS conflicts) ──
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-family:DM Sans,sans-serif;font-weight:700;font-size:0.78rem;"
        "color:#6B5742;text-transform:uppercase;letter-spacing:0.07em;margin:0 0 10px;'>"
        "Research Depth</p>",
        unsafe_allow_html=True,
    )

    # Render visual pill toggle — purely decorative, actual state lives in session_state
    q_bg  = "#D4A373" if st.session_state.depth == "Quick" else "#FAEDCD"
    q_col = "#3B2A1A" if st.session_state.depth == "Quick" else "#8B7355"
    q_fw  = "700"     if st.session_state.depth == "Quick" else "500"
    q_sh  = "0 2px 8px rgba(212,163,115,0.30)" if st.session_state.depth == "Quick" else "none"
    d_bg  = "#D4A373" if st.session_state.depth == "Deep"  else "#FAEDCD"
    d_col = "#3B2A1A" if st.session_state.depth == "Deep"  else "#8B7355"
    d_fw  = "700"     if st.session_state.depth == "Deep"  else "500"
    d_sh  = "0 2px 8px rgba(212,163,115,0.30)" if st.session_state.depth == "Deep"  else "none"

    st.markdown(
        f"""<div style='display:flex;gap:0;border:1.5px solid #CCD5AE;border-radius:8px;
                        overflow:hidden;width:fit-content;background:#FAEDCD;'>
            <div style='padding:9px 32px;font-family:DM Sans,sans-serif;font-size:0.9rem;
                        font-weight:{q_fw};color:{q_col};background:{q_bg};
                        box-shadow:{q_sh};border-right:1px solid #CCD5AE;
                        transition:all 0.15s;cursor:pointer;'>Quick</div>
            <div style='padding:9px 32px;font-family:DM Sans,sans-serif;font-size:0.9rem;
                        font-weight:{d_fw};color:{d_col};background:{d_bg};
                        box-shadow:{d_sh};transition:all 0.15s;cursor:pointer;'>Deep</div>
        </div>
        <div style='margin-top:6px;font-size:0.78rem;color:#8B7355;font-family:DM Sans,sans-serif;'>
            {'Quick: fast scan, ~30 sec' if st.session_state.depth == 'Quick'
             else 'Deep: multi-round research, ~10 min — richer results'}
        </div>""",
        unsafe_allow_html=True,
    )

    # Actual clickable toggles — sized to match pill, placed transparently over it
    col_q, col_d, col_sp = st.columns([1, 1, 3])
    with col_q:
        if st.button("Quick", key="depth_quick_btn", use_container_width=True):
            st.session_state.depth = "Quick"
            st.rerun()
    with col_d:
        if st.button("Deep", key="depth_deep_btn", use_container_width=True):
            st.session_state.depth = "Deep"
            st.rerun()

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
    _, col_run = st.columns([3, 1])
    with col_run:
        run_clicked = st.button("Run Research", type="primary", use_container_width=True,
                                key="run_research_btn")

    # ── Submission logic ──
    if run_clicked:
        st.session_state.idea              = idea_val
        st.session_state.regions_selected  = selected_regions
        st.session_state.segments_selected = selected_segments
        st.session_state.region_other      = region_other_val
        st.session_state.segment_other     = segment_other_val

        regions  = [r for r in selected_regions  if r != "Other"]
        segments = [s for s in selected_segments if s != "Other"]
        if "Other" in selected_regions and region_other_val.strip():
            regions.extend([x.strip() for x in region_other_val.split(",") if x.strip()])
        if "Other" in selected_segments and segment_other_val.strip():
            segments.extend([x.strip() for x in segment_other_val.split(",") if x.strip()])

        idea    = idea_val.strip()
        region  = ", ".join(regions)
        segment = ", ".join(segments)

        if not idea:
            st.warning("Please describe your startup idea before running research.")
        elif not regions:
            st.warning("Please select at least one target region.")
        elif not segments:
            st.warning("Please select at least one target segment.")
        else:
            st.session_state.region  = region
            st.session_state.segment = segment
            sig = hashlib.sha256(f"{idea}|{region}|{segment}|{st.session_state.depth}".encode()).hexdigest()
            cached = get_cached_report(sig)
            if cached:
                st.session_state.report     = cached
                st.session_state.agent_log  = "Loaded from cache."
                st.session_state.qa_history = []
                st.session_state.view       = "Insights"
                st.rerun()
            else:
                with st.status("Running agent pipeline…", expanded=True) as status:
                    bar = st.progress(0)

                    bar.progress(10, text="Setting up agent roles and task configuration…")
                    st.write("Initializing agent roles and research tasks…")

                    bar.progress(30, text="Gathering live market signals and competitive data…")
                    st.write("Gathering market signals and competitive intelligence…")

                    bar.progress(55, text="Analyzing competitors, pricing models and pain points…")
                    st.write("Running competitive analysis and pricing research…")

                    bar.progress(75, text="Synthesizing findings into a strategic brief…")
                    st.write("Synthesizing research into strategic brief…")

                    try:
                        report, agent_log = run_research_crew(
                            idea, region, segment, st.session_state.depth
                        )
                        bar.progress(100, text="Research complete.")
                        save_report(sig, report)
                        st.session_state.report     = report
                        st.session_state.agent_log  = agent_log
                        st.session_state.qa_history = []
                        status.update(label="Research complete.", state="complete", expanded=False)
                        st.session_state.view = "Insights"
                        st.rerun()
                    except RuntimeError as exc:
                        bar.progress(0, text="Pipeline failed.")
                        status.update(label="Research failed.", state="error", expanded=True)
                        st.session_state.agent_log = str(exc)
                        st.error(f"Agent error: {exc}")


# ── INSIGHTS VIEW ────────────────────────────────────────────

elif st.session_state.view == "Insights":

    if st.session_state.report is None:
        st.markdown(
            "<div class='page-header'><h2>Market Insights</h2>"
            "<p>Run a research report to see your analysis.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='welcome'><h3>No report yet</h3>"
            "<p>Head to Research, fill in your idea, and click Run Research.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        report = st.session_state.report
        st.markdown(
            "<div class='page-header'><h2>Market Insights</h2>"
            "<p>AI-generated market intelligence report</p></div>",
            unsafe_allow_html=True,
        )

        market_cap_value = getattr(report, "market_cap", None)
        cap_html = (
            f"<div class='summary-divider'></div>"
            f"<div class='summary-item'><span class='summary-label'>Market Cap</span>"
            f"<span class='summary-value'>{escape(str(market_cap_value))}</span></div>"
        ) if market_cap_value else ""

        render_score_card(report)

        pill_html = (
            f"<div class='summary-pill'>"
            f"<div class='summary-item'><span class='summary-label'>Idea</span>"
            f"<span class='summary-value'>{escape(report.idea[:48])}{'…' if len(report.idea)>48 else ''}</span></div>"
            f"<div class='summary-divider'></div>"
            f"<div class='summary-item'><span class='summary-label'>Region</span>"
            f"<span class='summary-value'>{escape(report.region)}</span></div>"
            f"<div class='summary-divider'></div>"
            f"<div class='summary-item'><span class='summary-label'>Segment</span>"
            f"<span class='summary-value'>{escape(report.segment)}</span></div>"
            f"<div class='summary-divider'></div>"
            f"<div class='summary-item'><span class='summary-label'>Depth</span>"
            f"<span class='summary-value'>{st.session_state.depth}</span></div>"
            f"{cap_html}"
            f"</div>"
        )
        st.markdown(pill_html, unsafe_allow_html=True)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Overview", "Competitors", "Pricing", "Pain Points", "Entry Strategy"]
        )

        with tab1:
            text = report.market_overview or ""
            raw  = re.split(r"\n+|\s*[•*]\s+|\s*-\s+", text)
            pts  = [p.strip(" -\t") for p in raw if p and p.strip(" -\t")]
            if len(pts) <= 1 and text.strip():
                pts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
            if pts:
                for pt in pts:
                    accent_card(f"<span style='color:#D4A373;font-weight:700;margin-right:8px;'>›</span>{escape(pt)}")
            else:
                st.info("No market overview available.")

        with tab2:
            if report.competitors:
                for idx, comp in enumerate(report.competitors):
                    top_badge = (
                        "<span style='background:#D4A373;color:#3B2A1A;font-size:0.7rem;"
                        "padding:3px 10px;border-radius:4px;font-weight:700;"
                        "font-family:DM Sans,sans-serif;letter-spacing:0.04em;"
                        "display:inline-block;margin-bottom:10px;'>Top Pick</span>"
                    ) if idx == 0 else ""

                    desc_html = (
                        f"<p style='color:#4A3728;font-family:DM Sans,sans-serif;"
                        f"font-size:0.93rem;line-height:1.65;margin:8px 0 12px;'>"
                        f"{escape(sanitize_competitor_text(comp.description or ''))}</p>"
                    ) if comp.description else ""

                    url_html = (
                        f"<a href='{comp.url.strip()}' target='_blank' rel='noopener' "
                        f"style='color:#A0733D;font-family:DM Sans,sans-serif;font-size:0.88rem;"
                        f"font-weight:600;text-decoration:underline;display:inline-block;"
                        f"margin-bottom:14px;'>Visit Website →</a>"
                    ) if (comp.url and comp.url.strip()) else ""

                    sp = to_points(comp.strengths)
                    wp = to_points(comp.weaknesses)

                    def _pts_html(pts: list, label: str, bullet_col: str) -> str:
                        if not pts:
                            return ""
                        items = "".join(
                            f"<li style='color:#4A3728;font-family:DM Sans,sans-serif;"
                            f"font-size:0.88rem;line-height:1.6;margin-bottom:4px;'>"
                            f"{escape(p)}</li>"
                            for p in pts
                        )
                        return (
                            f"<p style='font-weight:700;color:#3B2A1A;font-family:DM Sans,sans-serif;"
                            f"font-size:0.9rem;margin:12px 0 6px;'>{label}</p>"
                            f"<ul style='margin:0;padding-left:18px;list-style:disc;"
                            f"color:{bullet_col};'>{items}</ul>"
                        )

                    str_html  = _pts_html(sp, "Strengths",  "#4A7C8E")
                    weak_html = _pts_html(wp, "Weaknesses", "#B83232")

                    card_bg   = "linear-gradient(135deg,#FAEDCD 0%,#F5F0D8 100%)" if idx == 0 else "#FEFAE0"
                    card_bdr  = "#D4A373" if idx == 0 else "#CCD5AE"
                    num_badge = (
                        f"<span style='font-family:Playfair Display,serif;font-weight:800;"
                        f"font-size:1.05rem;color:#D4A373;margin-right:8px;'>#{idx+1}</span>"
                    )

                    html = (
                        f"<div style='background:{card_bg};border:1.5px solid {card_bdr};"
                        f"border-radius:12px;padding:22px 26px;margin-bottom:16px;"
                        f"box-shadow:0 2px 10px rgba(59,42,26,0.07);'>"
                        f"<div style='font-family:Playfair Display,serif;font-weight:800;"
                        f"font-size:1.15rem;color:#3B2A1A;margin-bottom:8px;'>"
                        f"{num_badge}{escape(sanitize_competitor_text(comp.name or 'Unknown'))}</div>"
                        f"{top_badge}{desc_html}{url_html}{str_html}{weak_html}"
                        f"</div>"
                    )
                    st.markdown(html, unsafe_allow_html=True)
            else:
                st.info("No competitors listed.")

        with tab3:
            if report.pricing_models:
                for idx, p in enumerate(report.pricing_models):
                    accent_card(
                        f"<span style='color:#D4A373;font-weight:700;margin-right:8px;"
                        f"font-family:Playfair Display,serif;'>#{idx+1}</span>{escape(p)}"
                    )
            else:
                st.info("No pricing models available yet.")

        with tab4:
            if report.pain_points:
                for p in report.pain_points:
                    accent_card(
                        f"<span style='color:#B83232;font-weight:700;margin-right:8px;'>●</span>{escape(p)}",
                        border="#B83232", tint="rgba(184,50,50,0.05)",
                    )
            else:
                st.info("No pain points available yet.")

        with tab5:
            if report.entry_recommendations:
                for idx, e in enumerate(report.entry_recommendations):
                    accent_card(
                        f"<span style='color:#4A7C8E;font-weight:700;margin-right:8px;"
                        f"font-family:Playfair Display,serif;'>#{idx+1}</span>{escape(e)}",
                        border="#4A7C8E", tint="rgba(74,124,142,0.05)",
                    )
            else:
                st.info("No entry recommendations available yet.")

        with st.expander("Agent Reasoning Log", expanded=False):
            log = st.session_state.agent_log or getattr(report, "reasoning_log", None) or "No log."
            st.markdown(f"<div class='term'>{escape(log)}</div>", unsafe_allow_html=True)

        valid_sources = [s for s in (report.sources or []) if s and s.strip()]
        st.markdown("---")
        st.markdown("### Sources & References")
        if valid_sources:
            st.markdown(
                "<div style='background:rgba(212,163,115,0.07);border-left:3px solid #D4A373;"
                "padding:11px 16px;border-radius:8px;margin-bottom:14px;'>"
                "<p style='margin:0;font-size:0.87rem;color:#8B7355;font-family:DM Sans,sans-serif;'>"
                "Sources consulted during market research and competitive analysis.</p></div>",
                unsafe_allow_html=True,
            )
            for i, src in enumerate(valid_sources, 1):
                if src.startswith(("http://", "https://")):
                    domain = src.split("://")[1].split("/")[0].replace("www.", "")
                    st.markdown(
                        f"<div style='margin:9px 0;padding:10px 14px;background:#FAEDCD;"
                        f"border-radius:8px;border:1px solid #CCD5AE;border-left:3px solid #D4A373;'>"
                        f"<strong style='color:#A0733D;'>{i}.</strong> "
                        f"<a href='{escape(src)}' target='_blank' style='color:#A0733D;font-weight:600;'>"
                        f"{escape(domain)} →</a>"
                        f"<br><span style='font-size:0.77rem;color:#8B7355;'>"
                        f"{escape(src[:74])}{'…' if len(src)>74 else ''}</span></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='margin:9px 0;padding:10px 14px;background:#FAEDCD;"
                        f"border-radius:8px;border:1px solid #CCD5AE;border-left:3px solid #D4A373;'>"
                        f"<strong style='color:#A0733D;'>{i}.</strong> "
                        f"<span style='color:#4A3728;'>{escape(src)}</span></div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Sources will appear here after running a report.")

        st.markdown(
            "<div style='margin-top:32px;padding-top:22px;border-top:1.5px solid #CCD5AE;'></div>",
            unsafe_allow_html=True,
        )
        col_dl, col_fu = st.columns(2, gap="medium")
        with col_dl:
            md_content = generate_pdf_html(report, st.session_state.depth)
            safe_name  = report.idea[:40].strip().replace(" ", "_").replace("/", "-").lower()
            try:
                from weasyprint import HTML as _WP

                pdf_bytes = _WP(string=md_content).write_pdf()
                st.download_button(
                    label="⬇ Download Report (PDF)",
                    data=pdf_bytes,
                    file_name=f"udyama_{safe_name}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except (ImportError, OSError) as exc:
                st.caption(f"PDF export unavailable in this environment ({exc.__class__.__name__}).")
                st.download_button(
                    label="⬇ Download Report (HTML)",
                    data=md_content.encode("utf-8"),
                    file_name=f"udyama_{safe_name}.html",
                    mime="text/html",
                    use_container_width=True,
                    help="Open in browser -> Ctrl+P -> Save as PDF",
                )
        with col_fu:
            if st.button("Ask Follow-up Questions", type="primary", use_container_width=True):
                st.session_state.view = "Follow-up"
                st.rerun()


# ── FOLLOW-UP VIEW ───────────────────────────────────────────

elif st.session_state.view == "Follow-up":

    st.markdown(
        "<div class='page-header'><h2>Follow-up Chat</h2>"
        "<p>Ask deeper questions about your market research report</p></div>",
        unsafe_allow_html=True,
    )

    if st.session_state.report is None:
        st.markdown(
            "<div class='welcome'><h3>No report yet</h3>"
            "<p>Run a market analysis first, then come back here to ask questions.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        report = st.session_state.report
        st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

        if not st.session_state.qa_history:
            st.markdown(
                "<div class='chat-empty'>"
                "Ask anything about your market — strategy, competitors, pricing, channels…"
                "</div>",
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

        with st.form("followup_form", clear_on_submit=True):
            col_q, col_btn = st.columns([5, 1])
            with col_q:
                question = st.text_input(
                    "question",
                    placeholder="e.g., What are the top 3 GTM channels for this segment?",
                    label_visibility="collapsed",
                )
            with col_btn:
                ask_clicked = st.form_submit_button("Ask", type="primary", use_container_width=True)

        if ask_clicked and question.strip():
            with st.spinner("Thinking…"):
                answer = answer_followup(
                    question=question.strip(),
                    report=report,
                    history=st.session_state.qa_history,
                )
            st.session_state.qa_history.append({"question": question.strip(), "answer": answer})
            save_qa_to_storage()
            st.rerun()

# ── FOOTER — rendered on every view ──
render_footer()
