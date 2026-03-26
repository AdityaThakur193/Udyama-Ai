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
        description=f"Research market overview and growth signals.\\n{profile}",
        expected_output="A concise market overview with key trends and opportunities.",
    )
    t2 = Task(
        agent=competitor_analyst,
        description="Analyze competitor landscape using findings from previous task.",
        context=[t1],
        expected_output="A list of competitors with strengths and weaknesses.",
    )
    t3 = Task(
        agent=pricing_strategist,
        description="Propose pricing models for the selected segment and region.",
        context=[t1, t2],
        expected_output="3-5 pricing models with rationale.",
    )
    t4 = Task(
        agent=customer_insights,
        description="Identify customer pain points, unmet needs, and purchase barriers.",
        context=[t1, t2],
        expected_output="A prioritized list of customer pain points.",
    )
    t5 = Task(
        agent=report_writer,
        description=(
            "Synthesize all findings into a final strategic report. "
            "Return ONLY valid JSON with keys: "
            "market_overview (string), competitors (array of objects with name, description, url, strengths, weaknesses), "
            "pricing_models (array of strings), pain_points (array of strings), "
            "entry_recommendations (array of strings), sources (array of URLs/strings)."
        ),
        context=[t1, t2, t3, t4],
        expected_output="A valid JSON object only, without markdown formatting.",
    )

    return Crew(
        agents=[market_researcher, competitor_analyst, pricing_strategist, customer_insights, report_writer],
        tasks=[t1, t2, t3, t4, t5],
        process=Process.sequential,
        verbose=True,
        tracing=True,
    )


def get_dummy_report() -> MarketResearchReport:
    """Return static data for UI development and testing."""
    return MarketResearchReport(
        idea="AI-based crop advisory assistant",
        region="India",
        segment="Farmers",
        market_overview="Digital agri-advisory is growing rapidly due to smartphone penetration and weather volatility.",
        competitors=[
            Competitor(
                name="AgriSense",
                description="Mobile-first advisory platform for crop planning.",
                url="https://example.com/agrisense",
                strengths="Strong on-ground channel partnerships.",
                weaknesses="Limited personalization by micro-climate.",
            )
        ],
        pricing_models=["Freemium with premium advisory packs", "B2B2C via agri-input distributors"],
        pain_points=["Low trust in generic recommendations", "Language and literacy barriers"],
        entry_recommendations=["Start with one crop and one state", "Partner with cooperatives for pilot adoption"],
        sources=["https://example.com/market-trends", "https://example.com/competitor-analysis"],
        reasoning_log="Dummy run: no external API calls were executed.",
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
        competitors=competitors,
        pricing_models=_as_string_list(parsed.get("pricing_models")),
        pain_points=_as_string_list(parsed.get("pain_points")),
        entry_recommendations=_as_string_list(parsed.get("entry_recommendations")),
        sources=_as_string_list(parsed.get("sources")),
        reasoning_log=raw_output,
    )


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
