"""Role definitions and prompts for each research agent."""

from __future__ import annotations

import copy
from typing import TypedDict

# FIX 1: Added TypedDict for AgentRole — previously the dict shape was implicit,
#         meaning typos in "role"/"goal"/"backstory" keys would fail silently at runtime.
class AgentRole(TypedDict):
    role: str
    goal: str
    backstory: str


# Base roles — depth-neutral, used as defaults and overridden by get_roles_for_depth().
AGENT_ROLES: dict[str, AgentRole] = {
    "MarketResearcher": {
        "role": "Market Research Specialist",
        "goal": (
            "Map market size, trends, and demand signals for the startup idea. "
            "Document all sources used."
        ),
        "backstory": (
            "A data-driven analyst focused on market structure and growth drivers. "
            "Always tracks and cites sources for every claim."
        ),
    },
    "CompetitorAnalyst": {
        "role": "Competitive Intelligence Analyst",
        "goal": (
            "Identify direct and adjacent competitors with clear positioning insights. "
            "Include source URLs for each competitor."
        ),
        "backstory": (
            "A strategy consultant with deep experience in benchmarking startups. "
            "Maintains a detailed source log for verification."
        ),
    },
    "PricingStrategist": {
        "role": "Pricing and Monetization Strategist",
        "goal": (
            "Recommend viable pricing models based on value proposition and segment. "
            "Track all pricing benchmarks and their sources."
        ),
        "backstory": (
            "A monetization expert who designs pricing experiments for early products. "
            "Documents where each pricing reference came from."
        ),
    },
    "CustomerInsights": {
        "role": "Customer Insights Researcher",
        "goal": (
            "Surface customer pain points, objections, and adoption blockers. "
            "Cite research sources and studies."
        ),
        "backstory": (
            "A customer researcher skilled at synthesizing qualitative and market signals. "
            "Maintains source attribution for all insights."
        ),
    },
    "ReportWriter": {
        "role": "Market Intelligence Report Writer",
        "goal": (
            "Synthesize all findings into a structured and actionable final report "
            "with comprehensive source citations."
        ),
        "backstory": (
            "An executive writer who turns complex analysis into strategic narratives. "
            "Compiles all sources from research agents."
        ),
    },
}

# FIX 2: Depth-specific goal overrides — previously all agents had identical goals
#         regardless of whether the user selected Quick or Deep research mode.
#         Quick: narrow focus, prioritise speed and top-level signals.
#         Deep:  exhaustive, cross-validate claims, multiple search passes.
_DEPTH_GOAL_OVERRIDES: dict[str, dict[str, str]] = {
    "Quick": {
        "MarketResearcher": (
            "Provide a fast, high-level market snapshot — top-line TAM/SAM/SOM, "
            "the single strongest growth driver, and 3+ sources. Speed over exhaustiveness."
        ),
        "CompetitorAnalyst": (
            "Identify the 3 most prominent competitors quickly. "
            "One key strength and one weakness each. Include URLs."
        ),
        "PricingStrategist": (
            "Recommend 3 pricing models with rough price ranges. "
            "Prioritise speed — directional estimates are acceptable."
        ),
        "CustomerInsights": (
            "Surface the 3-5 most critical pain points with brief supporting evidence. "
            "Focus on the highest-severity blockers only."
        ),
        "ReportWriter": (
            "Produce a compact but complete JSON report. "
            "Prioritise clarity and valid JSON structure over exhaustive detail. "
            "Return ONLY valid JSON, no markdown, no prose outside the JSON object."
        ),
    },
    "Deep": {
        "MarketResearcher": (
            "Conduct exhaustive market research — quantify TAM/SAM/SOM, CAGR, "
            "demand drivers, regulatory factors, and future outlook. "
            "Cross-validate every metric across at least 2 sources. Document all 10+ sources."
        ),
        "CompetitorAnalyst": (
            "Map the full competitive landscape — top 5 competitors with detailed "
            "business models, pricing, strengths, weaknesses, and estimated revenue or user base. "
            "Identify whitespace and differentiation angles. Include all source URLs."
        ),
        "PricingStrategist": (
            "Design a comprehensive 5-model pricing strategy grounded in competitor benchmarks, "
            "willingness-to-pay data, and unit economics. Justify every price point with evidence."
        ),
        "CustomerInsights": (
            "Conduct thorough customer pain point analysis — 5-8 prioritised pain points "
            "ranked by severity, backed by surveys, reports, or user interviews. "
            "Segment insights by customer type and geography."
        ),
        "ReportWriter": (
            "Synthesize all agent findings into a comprehensive, consistent strategic report. "
            "Aggregate all 10+ sources. Ensure no contradictions across sections. "
            "Return ONLY valid JSON, no markdown, no prose outside the JSON object."
        ),
    },
}


def get_roles_for_depth(depth: str) -> dict[str, AgentRole]:
    """Return agent roles with goals tuned for the given research depth.

    Falls back to base AGENT_ROLES if depth is unrecognised.
    Used by crew.py instead of importing AGENT_ROLES directly.
    """
    # FIX 2 (cont): Deep-copy so mutations in crew construction never affect the base dict.
    roles: dict[str, AgentRole] = copy.deepcopy(AGENT_ROLES)
    overrides = _DEPTH_GOAL_OVERRIDES.get(depth, {})
    for agent_name, goal in overrides.items():
        if agent_name in roles:
            roles[agent_name]["goal"] = goal
    return roles
