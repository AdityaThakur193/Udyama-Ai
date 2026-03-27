"""Crew assembly and orchestration for market research workflows."""

from __future__ import annotations

import json
import re

from crewai import Agent, Crew, Process, Task

from market_agent.agents.roles import AGENT_ROLES
from market_agent.agents.tools import serper_tool
from market_agent.core.schema import Competitor, MarketResearchReport
from market_agent.core.settings import GEMINI_API_KEY


def _get_crewai_llm() -> str:
    """Return CrewAI-compatible Gemini model identifier."""
    return "gemini/gemini-2.5-flash"


def _build_crew(idea: str, region: str, segment: str, depth: str) -> Crew:
    profile = f"Idea: {idea}\nRegion: {region}\nSegment: {segment}\nDepth: {depth}"

    llm = _get_crewai_llm()

    # Create specialized agents that hand off outputs across a sequential workflow.
    market_researcher = Agent(tools=[serper_tool], llm=llm, verbose=True, **AGENT_ROLES["MarketResearcher"])
    competitor_analyst = Agent(tools=[serper_tool], llm=llm, verbose=True, **AGENT_ROLES["CompetitorAnalyst"])
    pricing_strategist = Agent(tools=[serper_tool], llm=llm, verbose=True, **AGENT_ROLES["PricingStrategist"])
    customer_insights = Agent(tools=[serper_tool], llm=llm, verbose=True, **AGENT_ROLES["CustomerInsights"])
    report_writer = Agent(llm=llm, verbose=True, **AGENT_ROLES["ReportWriter"])

    t1 = Task(
        agent=market_researcher,
        description=(
            f"Perform structured market research with quantitative focus.\n\n"
            f"You MUST include:\n"
            f"- TAM (Total Addressable Market)\n"
            f"- SAM (Serviceable Addressable Market)\n"
            f"- SOM (Serviceable Obtainable Market)\n"
            f"- Market size (USD/INR) with year\n"
            f"- CAGR % (Compound Annual Growth Rate)\n"
            f"- Key market segments\n"
            f"- Demand drivers (e.g., regulatory, economic, tech)\n"
            f"- Current trends and future outlook\n\n"
            f"Avoid vague statements. Every metric needs a source.\n"
            f"If exact data unavailable, provide realistic estimates with clear assumptions.\n\n"
            f"{profile}"
        ),
        expected_output="Structured market analysis with quantified TAM/SAM/SOM, growth metrics, and 5+ credible sources.",
    )
    t2 = Task(
        agent=competitor_analyst,
        description=(
            "Analyze competitor landscape from previous research.\n\n"
            "You MUST include:\n"
            "- Top 3-5 competitors ranked by market share\n"
            "- Business model (B2B, B2C, B2B2C, marketplace, etc.)\n"
            "- Pricing strategy and price points\n"
            "- Product/feature strengths (with 1-2 examples)\n"
            "- Weaknesses and market gaps\n"
            "- Estimated user base or revenue (if available)\n\n"
            "Focus on differentiation opportunities, not just surface features.\n"
            "Include competitor website URLs and sources."
        ),
        context=[t1],
        expected_output="Detailed competitive analysis: 3-5 competitors with business models, pricing, strengths, weaknesses, and market positioning gaps.",
    )
    t3 = Task(
        agent=pricing_strategist,
        description=(
            "Design optimal pricing strategy based on market and competitor analysis.\n\n"
            "You MUST include:\n"
            "- 3-5 pricing models (freemium, tiered, usage-based, subscription, hybrid, etc.)\n"
            "- Price points justified by value delivered\n"
            "- Comparison vs. competitor pricing\n"
            "- Revenue potential estimate (e.g., $X monthly at Y% adoption)\n"
            "- Unit economics (if applicable)\n\n"
            "No arbitrary numbers. Back every pricing decision with market research.\n"
            "Consider segment willingness-to-pay, purchasing power, and payment methods."
        ),
        context=[t1, t2],
        expected_output="3-5 pricing models with justified price points, revenue projections, and competitive positioning.",
    )
    t4 = Task(
        agent=customer_insights,
        description=(
            "Identify real customer pain points and behaviors.\n\n"
            "You MUST include:\n"
            "- 5-8 prioritized pain points (ranked by severity)\n"
            "- Customer segments (e.g., SMEs vs. enterprises, geography, use case)\n"
            "- Purchase barriers (cost, complexity, trust, availability)\n"
            "- Willingness to pay by segment\n"
            "- Current solution gaps (what aren't existing solutions solving?)\n\n"
            "Ground in real data: surveys, reports, user interviews, market research.\n"
            "Avoid generic statements. Be specific with supporting evidence."
        ),
        context=[t1, t2],
        expected_output="5-8 prioritized customer pain points with segment analysis, purchase barriers, and supporting research sources.",
    )
    t5 = Task(
        agent=report_writer,
        description=(
            "Synthesize all findings into final strategic business report.\n\n"
            "You MUST:\n"
            "- Combine insights from all agents into coherent narrative\n"
            "- Ensure consistency across market size, competitors, pricing, pain points\n"
            "- Return ONLY valid JSON (no markdown, no explanations outside JSON)\n"
            "- Include entry_recommendations array with 5-8 actionable strategies\n"
            "- Aggregate ALL sources from other agents (10+ minimum)\n\n"
            "JSON Keys required:\n"
            "  - idea, region, segment (context)\n"
            "  - market_overview (string, 200-300 words)\n"
            "  - market_cap (string, e.g., '$5B by 2028')\n"
            "  - competitors (array of objects: name, description, url, strengths, weaknesses)\n"
            "  - pricing_models (array of strings)\n"
            "  - pain_points (array of strings)\n"
            "  - entry_recommendations (array of strings)\n"
            "  - sources (array of URLs/references, 10-20 items)\n"
            "  - reasoning_log (optional, brief summary of analysis)"
        ),
        context=[t1, t2, t3, t4],
        expected_output="Valid JSON object only (no markdown). Keys: idea, region, segment, market_overview, market_cap, competitors, pricing_models, pain_points, entry_recommendations, sources.",
    )

    return Crew(
        agents=[market_researcher, competitor_analyst, pricing_strategist, customer_insights, report_writer],
        tasks=[t1, t2, t3, t4, t5],
        process=Process.sequential,
        verbose=True,
        tracing=True,
    )


def run_research_crew(
    idea: str, region: str, segment: str, depth: str
) -> tuple[MarketResearchReport, str]:
    """Build the crew and execute live research, returning a report plus a reasoning log string."""
    # CrewAI Gemini provider reads GOOGLE_API_KEY in environment.
    import os

    os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "true")
    crew = _build_crew(idea=idea, region=region, segment=segment, depth=depth)

    # Execute the crew with the given inputs
    inputs = {
        "idea": idea,
        "region": region,
        "segment": segment,
        "depth": depth,
    }
    try:
        result = crew.kickoff(inputs=inputs)
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower():
            raise RuntimeError(
                "Gemini API quota exceeded (429 RESOURCE_EXHAUSTED). "
                "Please enable billing or wait for quota reset, then retry."
            ) from exc
        raise RuntimeError(f"Crew execution failed: {message}") from exc

    # Extract output from crew execution
    raw_output = result.raw if hasattr(result, "raw") else str(result)

    report = _build_report_from_output(raw_output=raw_output, idea=idea, region=region, segment=segment)

    log = f"✅ Crew executed successfully. Output:\n{raw_output[:500]}..."
    return report, log


def _build_report_from_output(raw_output: str, idea: str, region: str, segment: str) -> MarketResearchReport:
    """Parse crew output into structured report fields with JSON-first fallback."""
    # Prefer strict JSON output, then gracefully fall back to text extraction.
    parsed = _extract_json_payload(raw_output)

    if parsed is None:
        return MarketResearchReport(
            idea=idea,
            region=region,
            segment=segment,
            market_overview=(raw_output[:700] if raw_output else f"Research conducted on {idea} for {segment} in {region}."),
            market_cap=_extract_market_cap(raw_output),
            competitors=[],
            pricing_models=_extract_bullets(raw_output, "pricing"),
            pain_points=_extract_bullets(raw_output, "pain"),
            entry_recommendations=_extract_bullets(raw_output, "entry"),
            sources=_extract_sources(raw_output),
            reasoning_log=raw_output,
        )

    competitors_data = parsed.get("competitors", []) if isinstance(parsed, dict) else []
    competitors = []
    if isinstance(competitors_data, list):
        for item in competitors_data:
            if isinstance(item, dict):
                competitors.append(
                    Competitor(
                        name=str(item.get("name", "Unknown")),
                        description=str(item.get("description", "")),
                        url=_safe_str(item.get("url")),
                        strengths=_safe_str(item.get("strengths")),
                        weaknesses=_safe_str(item.get("weaknesses")),
                    )
                )
            elif isinstance(item, str):
                competitors.append(Competitor(name=item, description=""))

    return MarketResearchReport(
        idea=idea,
        region=region,
        segment=segment,
        market_overview=str(parsed.get("market_overview", "")).strip() or f"Research conducted on {idea} for {segment} in {region}.",
        market_cap=_safe_str(parsed.get("market_cap")) or _extract_market_cap(raw_output),
        competitors=competitors,
        pricing_models=_as_string_list(parsed.get("pricing_models")),
        pain_points=_as_string_list(parsed.get("pain_points")),
        entry_recommendations=_as_string_list(parsed.get("entry_recommendations")),
        sources=_as_string_list(parsed.get("sources")),
        reasoning_log=raw_output,
    )


def _extract_market_cap(raw_output: str) -> str | None:
    """Extract a market cap/size expression from model output."""
    if not raw_output:
        return None

    patterns = [
        r"\$\s?\d+(?:[\.,]\d+)?\s?(?:billion|million|trillion|bn|mn|tn|B|M|T)",
        r"₹\s?\d+(?:[\.,]\d+)?\s?(?:crore|lakh|thousand|million|billion|cr|L|K)",
        r"\d+(?:[\.,]\d+)?\s?(?:billion|million|trillion|bn|mn|tn)\s?(?:USD|INR|dollars)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_output, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def _extract_json_payload(raw_output: str) -> dict | None:
    """Try to extract a JSON object from raw model output."""
    if not raw_output:
        return None

    candidates = []
    fenced = re.findall(r"```json\s*(\{.*?\})\s*```", raw_output, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(fenced)

    if raw_output.strip().startswith("{") and raw_output.strip().endswith("}"):
        candidates.append(raw_output.strip())

    brace_match = re.search(r"(\{[\s\S]*\})", raw_output)
    if brace_match:
        candidates.append(brace_match.group(1))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _as_string_list(value: object) -> list[str]:
    """Normalize a mixed value to a list of non-empty strings."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _extract_bullets(raw_output: str, keyword: str) -> list[str]:
    """Extract bullet-like lines from prose based on a section keyword."""
    if not raw_output:
        return []
    lines = [line.strip(" -*\t") for line in raw_output.splitlines() if line.strip()]
    if keyword == "pricing":
        terms = ("pricing", "monetization", "subscription", "freemium", "model")
    elif keyword == "pain":
        terms = ("pain", "friction", "barrier", "challenge", "objection")
    else:
        terms = ("entry", "go-to-market", "gtm", "launch", "recommend")
    out = [line for line in lines if any(term in line.lower() for term in terms)]
    return out[:6]


def _extract_sources(raw_output: str) -> list[str]:
    """Extract URLs from output as source hints."""
    if not raw_output:
        return []
    urls = re.findall(r"https?://[^\s)\]]+", raw_output)
    return list(dict.fromkeys(urls))[:12]


def _safe_str(value: object) -> str | None:
    """Return stripped string value or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
