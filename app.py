"""Streamlit entrypoint for the Market Intelligence Agent dashboard."""
# This module defines the Streamlit interface for running and exploring market research outputs.
from __future__ import annotations

import hashlib
from html import escape

import streamlit as st

from market_agent.agents.crew import get_dummy_report, run_research_crew
from market_agent.agents.followup import answer_followup
from market_agent.core.cache import get_cached_report, save_report


st.set_page_config(layout="wide", page_title="Market Intelligence Agent", page_icon="🔍")
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">',
    unsafe_allow_html=True,
)
st.markdown(
    """
    <style>
    :root {
        --primary: #0F172A;
        --accent: #10B981;
        --bg: #F8FAFC;
        --surface: #FFFFFF;
        --text: #1E293B;
        --muted: #64748B;
        --border: #E2E8F0;
    }
    .stApp {
        background: var(--bg);
        color: var(--text);
        font-family: "Inter", sans-serif;
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
    [data-testid="stSidebar"] {
        background: var(--surface);
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] * {
        color: var(--text);
    }
    [data-testid="stSidebar"] h3 {
        font-size: 1.15rem;
        margin-bottom: 8px;
        letter-spacing: -0.01em;
    }
    [data-testid="stSidebar"] .stRadio > label {
        font-weight: 600;
        color: var(--primary);
        margin-bottom: 4px;
    }
    [data-testid="stSidebar"] hr {
        border-color: var(--border);
        margin: 16px 0;
    }
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
        background: #FFFFFF !important;
        border: 1px solid var(--border) !important;
    }
    [role="listbox"],
    [role="listbox"] *,
    [role="option"],
    [role="option"] * {
        color: var(--text) !important;
        background: #FFFFFF !important;
    }
    [role="option"][aria-selected="true"] {
        background: #ECFDF5 !important;
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
        background: #FFFFFF !important;
        border: 1px solid var(--border) !important;
        border-radius: 5px !important;
        padding: 10px 12px !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
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
        margin-bottom: 6px !important;
    }
    .shell {
        max-width: 900px;
        margin: 0 auto;
        padding: 0 16px;
    }
    .hero {
        border: 1px solid var(--border);
        background: var(--surface);
        padding: 28px 24px;
        margin-bottom: 28px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
    }
    .hero h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.2;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .hero p {
        margin: 12px 0 0;
        font-size: 1.05rem;
        color: var(--muted);
        line-height: 1.5;
    }
    .section-title {
        border-left: 2px solid var(--accent);
        padding-left: 10px;
        padding-top: 2px;
        padding-bottom: 2px;
        margin: 24px 0 16px;
        font-family: "Space Grotesk", sans-serif;
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--accent) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--accent) !important;
        border-radius: 6px !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 16px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--muted);
        font-family: "Space Grotesk", sans-serif;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 8px 0;
        transition: color 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        color: var(--accent) !important;
        border-bottom: 3px solid var(--accent) !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding: 20px 4px;
    }
    .metric-card {
        border: 1px solid var(--border);
        background: var(--surface);
        padding: 16px 18px;
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
        padding: 18px 20px;
        margin-bottom: 14px;
        border-radius: 6px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        transition: all 0.2s ease;
    }
    .comp-card:hover {
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
        transform: translateY(-2px);
    }
    .comp-top {
        border: 2px solid var(--accent);
        box-shadow: 0 4px 16px rgba(16, 185, 129, 0.15);
        background: linear-gradient(135deg, #FFFFFF 0%, #F0FDF4 100%);
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
    .term {
        background: #0F172A;
        color: #E2E8F0;
        border: 1px solid #1F2937;
        padding: 16px;
        font-family: "Courier New", monospace;
        white-space: pre-wrap;
        line-height: 1.5;
        border-radius: 6px;
        font-size: 0.85rem;
        overflow-x: auto;
    }
    .chat-row {
        margin: 14px 0;
        display: flex;
        gap: 8px;
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
        max-width: 72%;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        word-wrap: break-word;
    }
    .agent-avatar {
        width: 28px;
        height: 28px;
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
        font-size: 0.9rem;
    }
    .agent-bubble {
        background: #ECFDF5;
        color: var(--text);
        border: 1px solid #86EFAC;
        max-width: 72%;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        word-wrap: break-word;
    }
    .welcome {
        border: 1px dashed #9AA4B2;
        background: var(--surface);
        padding: 48px 32px;
        text-align: center;
        border-radius: 8px;
        background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
    }
    .welcome h3 {
        margin: 0 0 12px;
        font-size: 1.4rem;
        color: var(--primary);
    }
    .welcome p {
        margin: 0;
        color: var(--muted);
        font-size: 1rem;
        line-height: 1.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def section_title(title: str) -> None:
    st.markdown(f"<div class='section-title'>{escape(title)}</div>", unsafe_allow_html=True)


def bullet_card(items: list[str], empty: str) -> None:
    if not items:
        st.info(empty)
        return
    for bullet in items:
        st.markdown(f"<div class='metric-card'>{escape(bullet)}</div>", unsafe_allow_html=True)


# Initialize app state once so navigation does not reset current results.
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
if "use_dummy" not in st.session_state:
    st.session_state.use_dummy = True

with st.sidebar:
    st.markdown("### Market Intelligence Agent")
    st.caption("Navigation only")
    active_view = st.radio(
        "Go to",
        ["Research Input", "Insights", "Follow-up"],
        index=0,
    )
    st.markdown("---")
    st.caption("Set filters in the center panel and run research.")

outer_left, outer_mid, outer_right = st.columns([1, 8, 1])

with outer_mid:
    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='hero'>
            <h1>Market Intelligence Agent</h1>
            <p>Founder-grade market research with autonomous agents and concise strategic outputs.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if active_view == "Research Input" or st.session_state.report is None:
        section_title("Research Input")
        with st.form("research_form"):
            st.session_state.idea = st.text_area(
                "Startup Idea",
                value=st.session_state.idea,
                placeholder="Describe your startup idea and core value proposition",
                height=120,
            )
            col_a, col_b = st.columns(2)
            with col_a:
                st.session_state.region = st.selectbox(
                    "Region",
                    ["India", "US", "EU", "Southeast Asia", "Global"],
                    index=["India", "US", "EU", "Southeast Asia", "Global"].index(st.session_state.region),
                )
                st.session_state.depth = st.radio("Research Depth", ["Quick", "Deep"], horizontal=True)
            with col_b:
                st.session_state.segment = st.selectbox(
                    "Segment",
                    [
                        "Consumers",
                        "SMEs",
                        "Enterprises",
                        "Students",
                        "Healthcare",
                        "Farmers",
                        "Gig Workers",
                    ],
                    index=[
                        "Consumers",
                        "SMEs",
                        "Enterprises",
                        "Students",
                        "Healthcare",
                        "Farmers",
                        "Gig Workers",
                    ].index(st.session_state.segment),
                )
                st.session_state.use_dummy = st.checkbox("Use dummy data", value=st.session_state.use_dummy)

            run_clicked = st.form_submit_button("Run Research", type="primary", use_container_width=True)
    else:
        run_clicked = False

    if run_clicked:
        idea = st.session_state.idea
        region = st.session_state.region
        segment = st.session_state.segment
        depth = st.session_state.depth
        use_dummy = st.session_state.use_dummy

        if not idea.strip():
            st.warning("Please provide a startup idea before running research.")
        else:
            signature = hashlib.sha256(f"{idea}|{region}|{segment}|{depth}".encode("utf-8")).hexdigest()
            cached = get_cached_report(signature)
            if cached:
                st.session_state.report = cached
                st.session_state.agent_log = "Loaded report from cache."
                st.session_state.qa_history = []
            else:
                with st.status("Running agent pipeline", expanded=True) as status:
                    st.write("Initializing agent roles and research tasks")
                    if use_dummy:
                        report = get_dummy_report().model_copy(
                            update={"idea": idea, "region": region, "segment": segment}
                        )
                        agent_log = "Dummy mode: generated static report for UI testing."
                        st.write("Dummy mode enabled: skipping external API calls")
                        save_report(signature, report)
                        st.session_state.report = report
                        st.session_state.agent_log = agent_log
                        st.session_state.qa_history = []
                        status.update(label="Research complete", state="complete", expanded=False)
                    else:
                        st.write("Executing research crew with sequential tasks")
                        try:
                            report, agent_log = run_research_crew(idea, region, segment, depth)
                            save_report(signature, report)
                            st.session_state.report = report
                            st.session_state.agent_log = agent_log
                            st.session_state.qa_history = []
                            status.update(label="Research complete", state="complete", expanded=False)
                        except RuntimeError as exc:
                            status.update(label="Research failed", state="error", expanded=True)
                            st.session_state.agent_log = str(exc)
                            st.error(str(exc))

    report = st.session_state.report
    if report is None:
        st.markdown(
            """
            <div class='welcome'>
                <h3>Start With Your Startup Hypothesis</h3>
                <p>Define your idea, choose region and segment, then run autonomous market analysis.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        if active_view == "Insights":
            section_title("Research Brief")
            st.markdown(
                f"<div class='metric-card'><strong>{escape(report.idea)}</strong><br/>{escape(report.region)} · {escape(report.segment)}</div>",
                unsafe_allow_html=True,
            )

            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["Market Overview", "Competitors", "Pricing", "Pain Points", "Entry Strategy"]
            )

            with tab1:
                section_title("Demand and Market Motion")
                st.markdown(f"<div class='metric-card'>{escape(report.market_overview)}</div>", unsafe_allow_html=True)

            with tab2:
                section_title("Competitive Field")
                if report.competitors:
                    for idx, comp in enumerate(report.competitors):
                        top_class = " comp-top" if idx == 0 else ""
                        website = (
                            f"<a href='{escape(comp.url)}' target='_blank'>Visit Website</a>" if comp.url else ""
                        )
                        strengths = (
                            f"<p><strong>Strengths:</strong> {escape(comp.strengths)}</p>" if comp.strengths else ""
                        )
                        weaknesses = (
                            f"<p><strong>Weaknesses:</strong> {escape(comp.weaknesses)}</p>" if comp.weaknesses else ""
                        )
                        st.markdown(
                            f"""
                            <div class='comp-card{top_class}'>
                                <h4>{escape(comp.name)}</h4>
                                <p>{escape(comp.description)}</p>
                                <p>{website}</p>
                                {strengths}
                                {weaknesses}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.info("No competitors listed.")

            with tab3:
                section_title("Monetization Paths")
                bullet_card(report.pricing_models, "No pricing models available.")

            with tab4:
                section_title("Customer Friction")
                bullet_card(report.pain_points, "No pain points available.")

            with tab5:
                section_title("Go-to-Market Entry")
                bullet_card(report.entry_recommendations, "No entry recommendations available.")

            with st.expander("Agent Reasoning Log", expanded=False):
                log_text = st.session_state.agent_log or report.reasoning_log or "No reasoning log available."
                st.markdown(f"<div class='term'>{escape(log_text)}</div>", unsafe_allow_html=True)

            if report.sources:
                section_title("Source Trail")
                for source in report.sources:
                    st.markdown(f"- [{source}]({source})")

        if active_view == "Follow-up":
            section_title("Follow-up Questions")

            with st.form("followup_form", clear_on_submit=True):
                question = st.text_input("Ask for deeper strategy, pricing, or competitor context")
                ask_clicked = st.form_submit_button("Ask", type="secondary")

            if ask_clicked and question.strip():
                answer = answer_followup(question=question, report=report)
                st.session_state.qa_history.append({"question": question.strip(), "answer": answer})

            for item in st.session_state.qa_history:
                st.markdown(
                    f"<div class='chat-row chat-user'><div class='user-bubble'>{escape(item['question'])}</div></div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div class='chat-row chat-agent'>
                        <div class='agent-avatar'>M</div>
                        <div class='agent-bubble'>{escape(item['answer'])}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("</div>", unsafe_allow_html=True)
