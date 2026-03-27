"""Streamlit entrypoint for the Market Intelligence Agent dashboard."""
# This module defines the Streamlit interface for running and exploring market research outputs.
from __future__ import annotations
import json

import hashlib
import re
from html import escape, unescape

import streamlit as st

from market_agent.core.browser_storage import get_indexeddb_script

from market_agent.agents.crew import run_research_crew
from market_agent.agents.followup import answer_followup
from market_agent.core.cache import get_cached_report, save_report

st.set_page_config(layout="wide", page_title="Market Intelligence Agent", page_icon="▪")
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)

# Inject IndexedDB persistence layer
st.markdown(get_indexeddb_script(), unsafe_allow_html=True)

# ============================================================
# SESSION STATE PERSISTENCE
# ============================================================

def init_persistent_state() -> None:
    """Initialize session state with default values if not already set."""
    defaults = {
        "view": "Research",
        "dark_mode": False,
        "report": None,
        "agent_log": "",
        "qa_history": [],
        "idea": "",
        "region": "India",
        "segment": "Consumers",
        "depth": "Quick",
        "db_synced": False,
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


# Initialize all persistent state
init_persistent_state()


def restore_session_from_storage() -> None:
    """Inject script to restore session data from IndexedDB on page load."""
    st.markdown(
        """
        <script>
        // Restore session data from IndexedDB when page loads
        async function restoreSessionData() {
            if (!window.UdyamaStorage) return;
            
            // Wait for DB to be ready
            let attempts = 0;
            while (!window.UdyamaStorage.isReady() && attempts < 20) {
                await new Promise(r => setTimeout(r, 50));
                attempts++;
            }
            
            try {
                const qaHistory = await window.UdyamaStorage.getSession('qa_history');
                if (qaHistory && qaHistory.length > 0) {
                    console.log('Restored QA history:', qaHistory.length, 'messages');
                }
            } catch (err) {
                console.log('Could not restore session data:', err);
            }
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', restoreSessionData);
        } else {
            restoreSessionData();
        }
        </script>
        """,
        unsafe_allow_html=True,
    )


# Restore session data from IndexedDB
restore_session_from_storage()


def save_qa_to_storage() -> None:
    """Save QA history to IndexedDB via JavaScript."""
    if st.session_state.get("qa_history"):
        history_json = json.dumps(st.session_state.qa_history)
        st.markdown(
            f"""
            <script>
            if (window.UdyamaStorage && window.UdyamaStorage.isReady()) {{
                window.UdyamaStorage.saveSession('qa_history', {history_json});
            }}
            </script>
            """,
            unsafe_allow_html=True,
        )

st.markdown(
    """
    <style>
    /* ============ ROOT & GLOBALS ============ */
    :root {
        --primary: #0F172A;
        --accent: #10B981;
        --bg: #F8FAFC;
        --surface: #FFFFFF;
        --text: #1E293B;
        --muted: #64748B;
        --border: #E2E8F0;
    }
    
    :root.dark-mode {
        --primary: #E2E8F0;
        --accent: #34D399;
        --bg: #10172E;
        --surface: #1F2942;
        --text: #F1F5F9;
        --muted: #94A3B8;
        --border: #2D3B52;
    }
    
    .stApp {
        background: linear-gradient(135deg, var(--bg) 0%, var(--bg) 100%);
        color: var(--text);
        font-family: "Inter", sans-serif;
        color-scheme: light !important;
    }
    
    body {
        background: linear-gradient(135deg, #F8FAFC 0%, #E6F0FF 100%) !important;
    }
    
    h1, h2, h3, h4 {
        font-family: "Space Grotesk", sans-serif !important;
        color: var(--primary);
        letter-spacing: -0.01em;
    }
    
    .stMarkdown, p, li, label {
        font-family: "Inter", sans-serif;
        color: var(--text);
    }
    
    .stApp, .stApp *, .stMarkdown *, .stText {
        color: var(--text);
    }
    
    [data-testid="stHeader"] {
        background: transparent;
    }
    
    a {
        color: var(--accent) !important;
    }
    
    /* ============ HIDE DEFAULT SIDEBAR ============ */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* ============ TOP NAVBAR ============ */
    .navbar {
        background: var(--surface);
        border-bottom: 2px solid var(--border);
        padding: 16px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 32px;
        margin-bottom: 24px;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
    }
    
    .navbar-logo {
        font-family: "Space Grotesk", sans-serif;
        font-weight: 700;
        font-size: 1.3rem;
        color: var(--primary);
        display: flex;
        align-items: center;
        gap: 10px;
        flex-shrink: 0;
    }
    
    .navbar-logo span {
        font-size: 1.4rem;
    }
    
    .navbar-center {
        display: flex;
        gap: 0;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--bg);
        padding: 2px;
        flex-grow: 1;
        max-width: 400px;
        justify-content: center;
    }
    
    .navbar-tab {
        flex: 1;
        text-align: center;
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        background: transparent;
        color: var(--muted);
        font-family: "Inter", sans-serif;
        font-weight: 600;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .navbar-tab.active {
        background: var(--accent);
        color: #FFFFFF;
    }
    
    .navbar-tab:hover {
        background: rgba(16, 185, 129, 0.1);
        transition: all 0.15s ease;
    }
    
    .navbar-tab.active:hover {
        background: #059669;
    }
    
    .navbar-right {
        display: flex;
        align-items: center;
        gap: 16px;
        flex-shrink: 0;
    }
    
    .mode-label {
        font-size: 0.85rem;
        color: var(--muted);
        font-weight: 500;
    }
    
    /* ============ MAIN CONTAINER ============ */
    .main-container {
        max-width: 1100px;
        margin: 0 auto;
        padding: 0 24px;
    }
    
    /* ============ HERO CARD ============ */
    .hero {
        border: 1px solid var(--border);
        background: linear-gradient(135deg, var(--surface) 0%, rgba(30, 41, 59, 0.5) 100%);
        padding: 40px 32px;
        margin-bottom: 32px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        text-align: center;
    }
    
    .hero h1 {
        margin: 0;
        font-size: 2.2rem;
        line-height: 1.2;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    .hero p {
        margin: 12px 0 0;
        font-size: 1.05rem;
        color: var(--muted);
        line-height: 1.6;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* ============ FORM CARDS ============ */
    .form-card {
        border: 1px solid var(--border);
        background: var(--surface);
        padding: 28px;
        margin-bottom: 24px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
    }
    
    .form-card-title {
        font-family: "Space Grotesk", sans-serif;
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--primary);
        margin: 0 0 20px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .form-card-title::before {
        content: "";
        width: 3px;
        height: 20px;
        background: var(--accent);
        border-radius: 1.5px;
    }
    
    .input-group {
        margin-bottom: 20px;
    }
    
    .input-group:last-child {
        margin-bottom: 0;
    }
    
    .helper-text {
        margin-top: 4px;
        font-size: 0.85rem;
        color: var(--muted);
        font-weight: 400;
    }
    
    /* ============ INPUTS ============ */
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div,
    .stRadio label,
    .stCheckbox label,
    .stCaption {
        color: var(--text) !important;
    }
    
    .stSelectbox [data-baseweb="select"] span,
    .stSelectbox [data-baseweb="select"] input,
    .stMultiSelect [data-baseweb="select"] span,
    .stMultiSelect [data-baseweb="select"] input,
    .stSelectbox [data-baseweb="select"] [aria-hidden="true"],
    .stMultiSelect [data-baseweb="select"] [aria-hidden="true"] {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        opacity: 1 !important;
    }
    
    .stSelectbox [data-baseweb="select"] input[role="combobox"],
    .stSelectbox [data-baseweb="select"] div[aria-hidden="true"],
    .stMultiSelect [data-baseweb="select"] input[role="combobox"],
    .stMultiSelect [data-baseweb="select"] div[aria-hidden="true"] {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        caret-color: var(--text) !important;
        opacity: 1 !important;
    }
    
    .stSelectbox [data-baseweb="select"] div[value],
    .stMultiSelect [data-baseweb="select"] div[value],
    .stSelectbox [data-baseweb="select"] [class*="singleValue"],
    .stMultiSelect [data-baseweb="select"] [class*="singleValue"] {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        opacity: 1 !important;
        visibility: visible !important;
        text-shadow: none !important;
        height: auto !important;
        min-height: 1.2em !important;
        line-height: 1.4 !important;
    }
    
    .stSelectbox [data-baseweb="select"] > div > div:first-child,
    .stMultiSelect [data-baseweb="select"] > div > div:first-child {
        min-height: 1.2em !important;
        align-items: center !important;
    }
    
    .stSelectbox [data-baseweb="select"] div,
    .stMultiSelect [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] [class*="singleValue"],
    .stMultiSelect [data-baseweb="select"] [class*="singleValue"] {
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
    }
    
    .stSelectbox [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    .stMultiSelect [data-baseweb="select"] [data-testid="stMarkdownContainer"] {
        color: var(--text) !important;
    }
    
    [data-baseweb="popover"],
    [data-baseweb="popover"] * {
        color: var(--text) !important;
    }
    
    [data-baseweb="popover"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
    }
    
    [role="listbox"],
    [role="listbox"] *,
    [role="option"],
    [role="option"] * {
        color: var(--text) !important;
        background: var(--surface) !important;
    }
    
    [role="option"][aria-selected="true"] {
        background: rgba(52, 211, 153, 0.2) !important;
    }
    
    .stRadio [role="radiogroup"] label,
    .stCheckbox label,
    .stCaption,
    [data-testid="stStatusWidget"] * {
        color: var(--text) !important;
    }
    
    [data-testid="stExpander"] summary {
        background: #FFFFFF !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }
    
    [data-testid="stExpander"] summary *,
    [data-testid="stExpander"] summary svg {
        color: var(--text) !important;
        fill: var(--text) !important;
    }
    
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        padding: 10px 12px !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        color: var(--text) !important;
    }
    
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox [data-baseweb="select"] > div:focus,
    .stMultiSelect [data-baseweb="select"] > div:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1) !important;
    }
    
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stMultiSelect label {
        font-family: "Inter", sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        color: var(--primary) !important;
        margin-bottom: 8px !important;
    }
    
    /* ============ BUTTONS ============ */
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--accent) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--accent) !important;
        border-radius: 6px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        height: 44px !important;
    }
    
    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {
        background: #059669 !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important;
    }
    
    .stButton > button:not([kind="primary"]),
    .stFormSubmitButton > button:not([kind="primary"]) {
        background: transparent !important;
        color: var(--accent) !important;
        border: 1px solid var(--accent) !important;
        border-radius: 6px !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:not([kind="primary"]):hover,
    .stFormSubmitButton > button:not([kind="primary"]):hover {
        background: #ECFDF5 !important;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2) !important;
    }
    
    /* ============ TABS ============ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 2px solid var(--border);
        padding-bottom: 0;
    }
    
    .stTabs [data-baseweb="tab"] {
        color: var(--muted);
        font-family: "Inter", sans-serif;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 12px 20px;
        transition: all 0.2s ease;
        margin-right: 8px;
        border-bottom: none;
        position: relative;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text);
    }
    
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: none !important;
    }
    
    .stTabs [aria-selected="true"]::after {
        content: "";
        position: absolute;
        bottom: -2px;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--accent);
        border-radius: 1.5px 1.5px 0 0;
    }
    
    .stTabs [data-baseweb="tab-panel"] {
        padding: 24px 0;
    }
    
    /* ============ CARDS ============ */
    .summary-pill {
        background: linear-gradient(135deg, var(--surface) 0%, rgba(30, 41, 59, 0.5) 100%);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 24px;
        display: flex;
        gap: 16px;
        align-items: center;
        flex-wrap: wrap;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
    }
    
    .summary-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    
    .summary-label {
        font-size: 0.8rem;
        color: var(--muted);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .summary-value {
        font-size: 0.95rem;
        color: var(--primary);
        font-weight: 600;
    }
    
    .metric-card {
        border: 1px solid var(--border);
        background: var(--surface);
        padding: 18px 20px;
        margin-bottom: 12px;
        border-radius: 6px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        line-height: 1.6;
        color: var(--text);
        font-size: 0.95rem;
    }
    
    .comp-card {
        border: 1px solid var(--border);
        background: var(--surface);
        padding: 20px;
        margin-bottom: 14px;
        border-radius: 6px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        transition: all 0.2s ease;
    }
    
    .comp-card:hover {
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.1);
        transform: translateY(-2px);
    }
    
    .comp-top {
        border: 2px solid var(--accent);
        box-shadow: 0 4px 16px rgba(16, 185, 129, 0.15);
        background: linear-gradient(135deg, var(--surface) 0%, rgba(52, 211, 153, 0.1) 100%);
    }
    
    .comp-card h4 {
        margin: 0 0 8px 0;
        color: var(--primary);
        font-size: 1.05rem;
    }
    
    .comp-card p {
        margin: 6px 0;
        color: var(--text);
        font-size: 0.9rem;
        line-height: 1.5;
    }
    
    .comp-card a {
        display: inline-block;
        padding: 6px 12px;
        background: var(--accent);
        color: #FFFFFF !important;
        border-radius: 4px;
        text-decoration: none;
        font-size: 0.85rem;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .comp-card a:hover {
        background: #059669;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
    }
    
    /* ============ REASONING LOG ============ */
    .term {
        background: rgba(15, 23, 42, 0.8);
        color: #E2E8F0;
        border: 1px solid var(--border);
        padding: 16px;
        font-family: "Courier New", monospace;
        white-space: pre-wrap;
        line-height: 1.5;
        border-radius: 6px;
        font-size: 0.85rem;
        overflow-x: auto;
    }
    
    /* ============ CHAT ============ */
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
    }
    
    .chat-row {
        margin: 14px 0;
        display: flex;
        gap: 10px;
    }
    
    .chat-user {
        justify-content: flex-end;
    }
    
    .chat-agent {
        justify-content: flex-start;
    }
    
    .user-bubble {
        background: var(--primary);
        color: #F8FAFC;
        max-width: 70%;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        word-wrap: break-word;
    }
    
    .agent-avatar {
        width: 32px;
        height: 32px;
        border-radius: 999px;
        background: var(--accent);
        color: #FFFFFF;
        font-family: "Space Grotesk", sans-serif;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 4px;
        flex-shrink: 0;
        font-size: 0.95rem;
    }
    
    .agent-bubble {
        background: rgba(52, 211, 153, 0.15);
        color: var(--text);
        border: 1px solid var(--accent);
        max-width: 70%;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        word-wrap: break-word;
    }
    
    .chat-composer {
        display: flex;
        gap: 10px;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--border);
    }
    
    /* ============ WELCOME STATE ============ */
    .welcome {
        border: 1px dashed var(--border);
        background: linear-gradient(135deg, var(--surface) 0%, rgba(30, 41, 59, 0.5) 100%);
        padding: 64px 40px;
        text-align: center;
        border-radius: 8px;
    }
    
    .welcome h3 {
        margin: 0 0 12px;
        font-size: 1.5rem;
        color: var(--primary);
    }
    
    .welcome p {
        margin: 0 0 8px;
        color: var(--muted);
        font-size: 1rem;
        line-height: 1.6;
    }
    
    .welcome-steps {
        margin-top: 24px;
        display: flex;
        gap: 24px;
        justify-content: center;
        flex-wrap: wrap;
    }
    
    .welcome-step {
        font-size: 0.85rem;
        color: var(--muted);
    }
    
    .welcome-step strong {
        color: var(--primary);
    }
    
    /* ============ SPACING & UTILITY ============ */
    .spacer {
        margin-bottom: 12px;
    }
    
    .hint-text {
        font-size: 0.85rem;
        color: var(--muted);
        margin-top: 8px;
        font-weight: 400;
    }
    
    .dark-toggle {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--surface);
        color: var(--text);
        font-family: "Inter", sans-serif;
        font-weight: 500;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .dark-toggle:hover {
        background: var(--bg);
        border-color: var(--accent);
    }
    
    </style>
    """,
    unsafe_allow_html=True,
)

# Apply dark mode CSS conditionally based on session state
if st.session_state.dark_mode:
    st.markdown(
        """
        <style>
        :root {
            --primary: #E2E8F0;
            --accent: #34D399;
            --bg: #10172E;
            --surface: #1F2942;
            --text: #F1F5F9;
            --muted: #94A3B8;
            --border: #2D3B52;
        }
        .stApp {
            background: #10172E !important;
        }
        body {
            background: #10172E !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def bullet_card(items: list[str], empty: str) -> None:
    """Render bullet items as styled metric cards."""
    if not items:
        st.info(empty)
        return
    for item_text in items:
        st.markdown(f"<div class='metric-card'>{escape(item_text)}</div>", unsafe_allow_html=True)


def format_response_text(text: str) -> str:
    """Format response text with proper HTML styling for bullet lists and sections."""
    if not text:
        return ""
    
    # Split by newlines to process line by line
    lines = text.split("\n")
    formatted_html = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            # Empty line
            if in_list:
                formatted_html.append("</div>")
                in_list = False
            formatted_html.append("<div style='margin: 8px 0;'></div>")
            continue
        
        # Check if line is a bullet point (starts with *, -, •, or numbered like "1.")
        is_bullet = stripped.startswith(("*", "-", "•", "–")) or (stripped and stripped[0].isdigit() and "." in stripped[:3])
        
        if is_bullet:
            # Clean the bullet marker
            if stripped.startswith("* "):
                clean_text = stripped[2:].strip()
            elif stripped.startswith("- "):
                clean_text = stripped[2:].strip()
            elif stripped.startswith("• "):
                clean_text = stripped[2:].strip()
            elif stripped.startswith("– "):
                clean_text = stripped[2:].strip()
            else:
                # Numbered item
                clean_text = stripped.split(".", 1)[1].strip() if "." in stripped else stripped
            
            if not in_list:
                formatted_html.append("<div style='margin: 12px 0;'>")
                in_list = True
            
            formatted_html.append(
                f"<div style='margin: 6px 0; padding-left: 16px; border-left: 3px solid var(--accent);'>"
                f"<strong>•</strong> {escape(clean_text)}</div>"
            )
        else:
            # Regular text / section header
            if in_list:
                formatted_html.append("</div>")
                in_list = False
            
            # Check if it looks like a header (ends with colon or contains multiple capitals)
            if stripped.endswith(":") or (len(stripped.split()) <= 5 and stripped.isupper()):
                formatted_html.append(
                    f"<div style='margin: 12px 0 8px 0; font-weight: 600; color: var(--primary); font-size: 0.95rem;'>"
                    f"{escape(stripped)}</div>"
                )
            else:
                formatted_html.append(
                    f"<div style='margin: 8px 0; line-height: 1.6; color: var(--text);'>{escape(stripped)}</div>"
                )
    
    if in_list:
        formatted_html.append("</div>")
    
    return "".join(formatted_html)


def sanitize_competitor_text(text: str | None) -> str:
    """Remove accidental HTML/list wrappers from LLM output for safe display."""
    if not text:
        return ""

    cleaned = unescape(str(text)).strip()
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Normalize list-like string output: ['a', 'b'] -> a; b
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1].strip()
    cleaned = cleaned.replace("', '", "; ").replace('" , "', "; ")
    cleaned = cleaned.strip("'\"")

    return cleaned


def to_points(text: str | None) -> list[str]:
    """Split mixed free text/bullets into readable points."""
    cleaned = sanitize_competitor_text(text)
    if not cleaned:
        return []

    parts = re.split(r"\n+|\s*[•*]\s+|\s*;\s+|\s*\|\s*", cleaned)
    point_items = [p.strip(" -\t") for p in parts if p.strip(" -\t")]
    return point_items if point_items else [cleaned]


# ============================================================
# INITIALIZE APP STATE
# ============================================================

if "report" not in st.session_state:
    st.session_state.report = None
if "agent_log" not in st.session_state:
    st.session_state.agent_log = ""
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "idea" not in st.session_state:
    st.session_state.idea = ""
if "region" not in st.session_state:
    st.session_state.region = "India"
if "segment" not in st.session_state:
    st.session_state.segment = "Consumers"
if "depth" not in st.session_state:
    st.session_state.depth = "Quick"
if "regions_selected" not in st.session_state:
    st.session_state.regions_selected = ["India"]
if "segments_selected" not in st.session_state:
    st.session_state.segments_selected = ["Consumers"]
if "region_other" not in st.session_state:
    st.session_state.region_other = ""
if "segment_other" not in st.session_state:
    st.session_state.segment_other = ""

# ============================================================
# TOP NAVIGATION BAR
# ============================================================

nav_col1, nav_col2, nav_col3 = st.columns([1.2, 3, 0.6], gap="small")

with nav_col1:
    st.markdown(
        "<div class='navbar-logo'><span>▸</span> Udyama-AI</div>",
        unsafe_allow_html=True,
    )

with nav_col2:
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    nav_tabs = st.columns(3, gap="small")
    
    with nav_tabs[0]:
        if st.button("Research", key="nav_research", use_container_width=True):
            st.session_state.view = "Research"
    
    with nav_tabs[1]:
        if st.button("Insights", key="nav_insights", use_container_width=True):
            st.session_state.view = "Insights"
    
    with nav_tabs[2]:
        if st.button("Follow-up", key="nav_followup", use_container_width=True):
            st.session_state.view = "Follow-up"
    
    st.markdown("</div>", unsafe_allow_html=True)

with nav_col3:
    # Dark mode toggle - smaller button
    if st.button(
        f"{'☀' if st.session_state.dark_mode else '●'}",
        key="dark_mode_toggle",
    ):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

st.markdown("<hr style='margin: 0; border: none; height: 1px; background: var(--border);'>", unsafe_allow_html=True)

# ============================================================
# MAIN CONTENT AREA
# ============================================================

st.markdown("<div class='main-container'>", unsafe_allow_html=True)

# Show hero only on Research view or when no report exists
if st.session_state.view == "Research" or st.session_state.report is None:
    st.markdown(
        """
        <div class='hero'>
            <h1>Market Intelligence Agent</h1>
            <p>Founder-grade market research powered by autonomous agents.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# RESEARCH VIEW
# ============================================================

if st.session_state.view == "Research":
    st.markdown("<div class='form-card'>", unsafe_allow_html=True)
    st.markdown("<div class='form-card-title'>Research Input</div>", unsafe_allow_html=True)
    
    with st.form("research_form"):
        # Startup Idea
        st.markdown("<div class='input-group'>", unsafe_allow_html=True)
        st.session_state.idea = st.text_area(
            "Startup Idea",
            value=st.session_state.idea,
            placeholder="e.g., An AI-powered platform for small farmers to optimize crop yield using real-time satellite imagery and ML models.",
            height=110,
        )
        st.markdown(
            "<div class='helper-text'>Describe your core value proposition, target problem, and how you solve it.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Region and Segment in two columns
        col_left, col_right = st.columns(2, gap="medium")
        
        with col_left:
            st.markdown("<div class='input-group'>", unsafe_allow_html=True)
            region_options = ["India", "US", "EU", "Southeast Asia", "Global", "Other"]
            st.session_state.regions_selected = st.multiselect(
                "Region (Multiple)",
                region_options,
                default=[r for r in st.session_state.regions_selected if r in region_options],
            )
            if "Other" in st.session_state.regions_selected:
                st.session_state.region_other = st.text_input(
                    "Other Region",
                    value=st.session_state.region_other,
                    placeholder="Type custom region(s), e.g., Middle East, Africa",
                )
            st.markdown(
                "<div class='helper-text'>Select one or more regions. Choose Other to add your own.</div>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col_right:
            st.markdown("<div class='input-group'>", unsafe_allow_html=True)
            segment_options = [
                "Consumers",
                "SMEs",
                "Enterprises",
                "Students",
                "Healthcare",
                "Farmers",
                "Gig Workers",
                "Other",
            ]
            st.session_state.segments_selected = st.multiselect(
                "Target Segment (Multiple)",
                segment_options,
                default=[s for s in st.session_state.segments_selected if s in segment_options],
            )
            if "Other" in st.session_state.segments_selected:
                st.session_state.segment_other = st.text_input(
                    "Other Target Segment",
                    value=st.session_state.segment_other,
                    placeholder="Type custom segment(s), e.g., NGOs, Government agencies",
                )
            st.markdown(
                "<div class='helper-text'>Select one or more target segments. Choose Other to add your own.</div>",
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Research Depth
        st.markdown("<div class='input-group'>", unsafe_allow_html=True)
        st.markdown("<label style='font-weight: 600; color: var(--primary); font-size: 0.9rem;'>Research Depth</label>", unsafe_allow_html=True)
        col_d1, col_d2 = st.columns(2, gap="small")
        with col_d1:
            if st.checkbox("Quick (2–5 min)", value=st.session_state.depth == "Quick", key="depth_quick"):
                st.session_state.depth = "Quick"
        with col_d2:
            if st.checkbox("Deep (8–15 min)", value=st.session_state.depth == "Deep", key="depth_deep"):
                st.session_state.depth = "Deep"
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Submit button
        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        run_clicked = st.form_submit_button("Run Research", type="primary", use_container_width=True)
        
        st.markdown(
            "<div class='hint-text' style='text-align: center; margin-top: 12px;'>Typical run time: under 30 seconds (Deep mode may take longer)</div>",
            unsafe_allow_html=True,
        )
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Handle research execution
    if run_clicked:
        idea = st.session_state.idea
        regions = [r for r in st.session_state.regions_selected if r != "Other"]
        segments = [s for s in st.session_state.segments_selected if s != "Other"]

        if "Other" in st.session_state.regions_selected and st.session_state.region_other.strip():
            regions.extend([r.strip() for r in st.session_state.region_other.split(",") if r.strip()])
        if "Other" in st.session_state.segments_selected and st.session_state.segment_other.strip():
            segments.extend([s.strip() for s in st.session_state.segment_other.split(",") if s.strip()])

        region = ", ".join(regions)
        segment = ", ".join(segments)
        depth = st.session_state.depth

        if not idea.strip():
            st.warning("Please provide a startup idea before running research.")
        elif not regions:
            st.warning("Please select at least one region (or provide Other Region).")
        elif not segments:
            st.warning("Please select at least one target segment (or provide Other Target Segment).")
        else:
            st.session_state.region = region
            st.session_state.segment = segment
            signature = hashlib.sha256(f"{idea}|{region}|{segment}|{depth}".encode("utf-8")).hexdigest()
            cached = get_cached_report(signature)
            if cached:
                st.session_state.report = cached
                st.session_state.agent_log = "Loaded report from cache."
                st.session_state.qa_history = []
            else:
                with st.status("Running agent pipeline", expanded=True) as status:
                    st.write("Initializing agent roles and research tasks")
                    st.write("Gathering market signals and competitive intelligence")
                    st.write("Synthesizing research into strategic brief")
                    try:
                        report, agent_log = run_research_crew(idea, region, segment, depth)
                        save_report(signature, report)
                        st.session_state.report = report
                        st.session_state.agent_log = agent_log
                        st.session_state.qa_history = []
                        status.update(label="Research complete", state="complete", expanded=False)
                        st.session_state.view = "Insights"
                        st.rerun()
                    except RuntimeError as exc:
                        status.update(label="Research failed", state="error", expanded=True)
                        st.session_state.agent_log = str(exc)
                        st.error(str(exc))
    
    # Show welcome state if no report
    if st.session_state.report is None:
        st.markdown(
            """
            <div class='welcome'>
                <h3>Ready to analyze your market?</h3>
                <p>Fill in your startup idea, choose a region and segment, select research depth, and let our agents uncover strategic insights.</p>
                <div class='welcome-steps'>
                    <div class='welcome-step'><strong>Step 1:</strong> Describe your idea</div>
                    <div class='welcome-step'><strong>Step 2:</strong> Pick region & segment</div>
                    <div class='welcome-step'><strong>Step 3:</strong> Run research</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# INSIGHTS VIEW (Report Output)
# ============================================================

elif st.session_state.view == "Insights":
    if st.session_state.report is None:
        st.info("No research report yet. Start from the Research tab.")
    else:
        report = st.session_state.report
        
        # Summary pill with research parameters
        st.markdown(
            f"""
            <div class='summary-pill'>
                <div class='summary-item'>
                    <span class='summary-label'>Idea</span>
                    <span class='summary-value'>{escape(report.idea[:50])}{'...' if len(report.idea) > 50 else ''}</span>
                </div>
                <div style='width: 1px; background: var(--border);'></div>
                <div class='summary-item'>
                    <span class='summary-label'>Region</span>
                    <span class='summary-value'>{escape(report.region)}</span>
                </div>
                <div style='width: 1px; background: var(--border);'></div>
                <div class='summary-item'>
                    <span class='summary-label'>Segment</span>
                    <span class='summary-value'>{escape(report.segment)}</span>
                </div>
                <div style='width: 1px; background: var(--border);'></div>
                <div class='summary-item'>
                    <span class='summary-label'>Depth</span>
                    <span class='summary-value'>{st.session_state.depth}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Insights tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Market Overview", "Competitors", "Pricing", "Pain Points", "Entry Strategy"]
        )
        
        with tab1:
            market_cap_value = getattr(report, "market_cap", None)
            if market_cap_value:
                st.markdown(
                    f"<div class='metric-card' style='border-left: 3px solid var(--accent);'><strong>Market Cap:</strong> {escape(str(market_cap_value))}</div>",
                    unsafe_allow_html=True,
                )

            overview_text = report.market_overview or ""
            raw_points = re.split(r"\n+|\s*[•*]\s+|\s*-\s+", overview_text)
            overview_items = [p.strip(" -\t") for p in raw_points if p and p.strip(" -\t")]

            # If no bullets were produced, split long prose into sentence bullets.
            if len(overview_items) <= 1 and overview_text.strip():
                sentence_points = re.split(r"(?<=[.!?])\s+", overview_text.strip())
                overview_items = [p.strip() for p in sentence_points if p.strip()]

            if overview_items:
                for point in overview_items:
                    st.markdown(
                        f"<div class='metric-card' style='margin: 8px 0;'><strong>•</strong> {escape(point)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No market overview available.")
        
        with tab2:
            if report.competitors:
                for idx, comp in enumerate(report.competitors):
                    top_class = " comp-top" if idx == 0 else ""
                    name = sanitize_competitor_text(comp.name)
                    description = sanitize_competitor_text(comp.description)
                    strength_points = to_points(comp.strengths)
                    weakness_points = to_points(comp.weaknesses)

                    st.markdown(
                        f"<div class='comp-card{top_class}'>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(f"#### #{idx + 1} {name}")
                    if description:
                        st.write(description)

                    if comp.url and comp.url.strip():
                        st.markdown(f"[Visit Website]({comp.url.strip()})")

                    if strength_points:
                        st.markdown("**Strengths**")
                        for point in strength_points:
                            st.markdown(f"- {point}")

                    if weakness_points:
                        st.markdown("**Weaknesses**")
                        for point in weakness_points:
                            st.markdown(f"- {point}")

                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No competitors listed.")
        
        with tab3:
            if report.pricing_models:
                st.markdown(
                    "<div style='margin-top: 8px;'><h4 style='color: var(--primary); margin-bottom: 16px;'>💰 Pricing Models & Strategies</h4></div>",
                    unsafe_allow_html=True,
                )
                for idx, pricing in enumerate(report.pricing_models):
                    st.markdown(
                        f"<div class='metric-card' style='background: linear-gradient(135deg, var(--surface) 0%, rgba(52, 211, 153, 0.1) 100%); border-left: 3px solid var(--accent); margin: 10px 0;'><strong>#{idx + 1}</strong> {escape(pricing)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("💡 No pricing models available yet. These models will show when the report is generated.")
        
        with tab4:
            if report.pain_points:
                st.markdown(
                    "<div style='margin-top: 8px;'><h4 style='color: var(--primary); margin-bottom: 16px;'>🔴 Customer Pain Points</h4></div>",
                    unsafe_allow_html=True,
                )
                for idx, pain in enumerate(report.pain_points):
                    st.markdown(
                        f"<div class='metric-card' style='background: linear-gradient(135deg, var(--surface) 0%, rgba(239, 68, 68, 0.1) 100%); border-left: 3px solid #EF4444; margin: 10px 0;'><strong>•</strong> {escape(pain)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("💡 No pain points available yet.")
        
        with tab5:
            if report.entry_recommendations:
                st.markdown(
                    "<div style='margin-top: 8px;'><h4 style='color: var(--primary); margin-bottom: 16px;'>🎯 Entry Strategy & Recommendations</h4></div>",
                    unsafe_allow_html=True,
                )
                for idx, entry in enumerate(report.entry_recommendations):
                    st.markdown(
                        f"<div class='metric-card' style='background: linear-gradient(135deg, var(--surface) 0%, rgba(59, 130, 246, 0.1) 100%); border-left: 3px solid #3B82F6; margin: 10px 0;'><strong>#{idx + 1}</strong> {escape(entry)}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("💡 No entry recommendations available yet.")
        
        # Collapsible reasoning log
        with st.expander("Agent Reasoning Log", expanded=False):
            log_text = st.session_state.agent_log or report.reasoning_log or "No reasoning log available."
            st.markdown(f"<div class='term'>{escape(log_text)}</div>", unsafe_allow_html=True)
        
        # Source trail
        if report.sources and len(report.sources) > 0 and report.sources[0].strip():
            st.markdown("---")
            st.markdown("### 📚 Sources & References")
            st.markdown(
                "<div style='background: rgba(52, 211, 153, 0.05); border-left: 3px solid var(--accent); padding: 12px 16px; border-radius: 4px; margin-bottom: 16px;'>"
                "<p style='margin: 0; font-size: 0.9rem; color: var(--muted);'>These sources were consulted during market research and competitive analysis.</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            for i, source in enumerate(report.sources, 1):
                if source and source.strip():
                    # Check if it's a URL
                    if source.startswith("http://") or source.startswith("https://"):
                        # Extract domain for display
                        domain = source.split("://")[1].split("/")[0].replace("www.", "")
                        st.markdown(
                            f"<div style='margin: 10px 0; padding: 8px 12px; background: var(--bg); border-radius: 4px; border-left: 2px solid var(--accent);'>"
                            f"<strong>{i}.</strong> <a href='{escape(source)}' target='_blank' style='color: var(--accent); text-decoration: none; font-weight: 500;'>"
                            f"{escape(domain)}</a>"
                            f"<br><span style='font-size: 0.8rem; color: var(--muted);'>{escape(source[:70])}{'...' if len(source) > 70 else ''}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        # Regular text source
                        st.markdown(
                            f"<div style='margin: 10px 0; padding: 8px 12px; background: var(--bg); border-radius: 4px; border-left: 2px solid var(--accent);'>"
                            f"<strong>{i}.</strong> <span style='color: var(--text);'>{escape(source)}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
        else:
            st.markdown("---")
            st.markdown("### 📚 Sources & References")
            st.info("📋 Sources will be populated when you run a research report.")
        
        # Follow-up button
        st.markdown("<div style='margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--border);'></div>", unsafe_allow_html=True)
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            if st.button("Ask Follow-up Questions", type="primary", use_container_width=True):
                st.session_state.view = "Follow-up"
                st.rerun()

# ============================================================
# FOLLOW-UP VIEW (Chat)
# ============================================================

elif st.session_state.view == "Follow-up":
    if st.session_state.report is None:
        st.info("No research report yet. Start from the Research tab.")
    else:
        report = st.session_state.report
        
        st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
        
        # Display chat history
        for item in st.session_state.qa_history:
            st.markdown(
                f"<div class='chat-row chat-user'><div class='user-bubble'>{escape(item['question'])}</div></div>",
                unsafe_allow_html=True,
            )
            # Format agent response with proper styling for bullet points and lists
            formatted_answer = format_response_text(item['answer'])
            st.markdown(
                f"""
                <div class='chat-row chat-agent'>
                    <div class='agent-avatar'>M</div>
                    <div class='agent-bubble' style='padding: 14px 16px;'>{formatted_answer}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Chat input
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        with st.form("followup_form", clear_on_submit=True):
            question = st.text_input(
                "Ask for deeper strategy, pricing, or competitor context",
                placeholder="e.g., What are the top 3 Go-to-Market channels for this segment?",
            )
            ask_clicked = st.form_submit_button("Ask", type="primary", use_container_width=False)
        
        if ask_clicked and question.strip():
            answer = answer_followup(question=question, report=report)
            st.session_state.qa_history.append({"question": question.strip(), "answer": answer})
            save_qa_to_storage()
            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
