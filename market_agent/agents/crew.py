"""Crew assembly and orchestration for market research workflows."""

from __future__ import annotations

import json
import os
import re

from crewai import Agent, Crew, Process, Task

from market_agent.agents.roles import AGENT_ROLES
from market_agent.agents.tools import serper_tool
from market_agent.core.schema import Competitor, MarketResearchReport
from market_agent.core.settings import GEMINI_API_KEY

# FIX 1: Replaced trivial _get_crewai_llm() function with a module-level constant.
_LLM_MODEL = "gemini/gemini-2.5-flash"

# FIX 2: Moved os.environ setup to module level — was inside run_research_crew(),
#         meaning it only ran after a Streamlit button click. Now runs once at import.
os.environ.setdefault("GOOGLE_API_KEY", GEMINI_API_KEY)

# FIX 3: Added depth configuration table — previously depth was embedded in the
#         profile string only and had zero effect on task complexity or output scope.
_DEPTH_CONFIG: dict[str, dict[str, str]] = {
    "Quick": {
        "competitors": "3",
        "pain_points": "3-5",
        "pricing_models": "3",
        "sources_min": "5",
        "market_overview_words": "100-150",
        "entry_recommendations": "3-5",
    },
    "Deep": {
        "competitors": "5",
        "pain_points": "5-8",
        "pricing_models": "5",
        "sources_min": "10",
        "market_overview_words": "200-300",
        "entry_recommendations": "5-8",
    },
}
_DEFAULT_DEPTH = "Deep"


def _build_crew(idea: str, region: str, segment: str, depth: str) -> Crew:
    profile = f"Idea: {idea}\nRegion: {region}\nSegment: {segment}\nDepth: {depth}"

    # FIX 3 (cont): Resolve depth config once — falls back to Deep for unknown values.
    cfg = _DEPTH_CONFIG.get(depth, _DEPTH_CONFIG[_DEFAULT_DEPTH])

    # FIX 4: Added max_iter=10 to all agents — previously uncapped, risking infinite
    #         tool-call loops that would exhaust API quota silently.
    market_researcher = Agent(
        tools=[serper_tool], llm=_LLM_MODEL, verbose=True,
        max_iter=10, **AGENT_ROLES["MarketResearcher"]
    )
    competitor_analyst = Agent(
        tools=[serper_tool], llm=_LLM_MODEL, verbose=True,
        max_iter=10, **AGENT_ROLES["CompetitorAnalyst"]
    )
    pricing_strategist = Agent(
        tools=[serper_tool], llm=_LLM_MODEL, verbose=True,
        max_iter=10, **AGENT_ROLES["PricingStrategist"]
    )
    customer_insights = Agent(
        tools=[serper_tool], llm=_LLM_MODEL, verbose=True,
        max_iter=10, **AGENT_ROLES["CustomerInsights"]
    )
    report_writer = Agent(
        llm=_LLM_MODEL, verbose=True,
        max_iter=5, **AGENT_ROLES["ReportWriter"]
    )

    # FIX 3 (cont): Task descriptions now use cfg values so Quick runs fewer
    #               data points and Deep runs comprehensive analysis.
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
            f"If exact data unavailable, provide realistic estimates with clear assumptions.\n"
            f"Provide at least {cfg['sources_min']} credible sources.\n\n"
            f"{profile}"
        ),
        expected_output=(
            f"Structured market analysis with quantified TAM/SAM/SOM, growth metrics, "
            f"and {cfg['sources_min']}+ credible sources."
        ),
    )
    t2 = Task(
        agent=competitor_analyst,
        description=(
            f"Analyze competitor landscape from previous research.\n\n"
            f"You MUST include:\n"
            f"- Top {cfg['competitors']} competitors ranked by market share\n"
            f"- Business model (B2B, B2C, B2B2C, marketplace, etc.)\n"
            f"- Pricing strategy and price points\n"
            f"- Product/feature strengths (with 1-2 examples)\n"
            f"- Weaknesses and market gaps\n"
            f"- Estimated user base or revenue (if available)\n\n"
            f"Focus on differentiation opportunities, not just surface features.\n"
            f"Include competitor website URLs and sources.\n\n"
            f"{profile}"
        ),
        context=[t1],
        expected_output=(
            f"Detailed competitive analysis: {cfg['competitors']} competitors with "
            f"business models, pricing, strengths, weaknesses, and market positioning gaps."
        ),
    )
    t3 = Task(
        agent=pricing_strategist,
        description=(
            f"Design optimal pricing strategy based on market and competitor analysis.\n\n"
            f"You MUST include:\n"
            f"- {cfg['pricing_models']} pricing models (freemium, tiered, usage-based, subscription, hybrid, etc.)\n"
            f"- Price points justified by value delivered\n"
            f"- Comparison vs. competitor pricing\n"
            f"- Revenue potential estimate (e.g., $X monthly at Y% adoption)\n"
            f"- Unit economics (if applicable)\n\n"
            f"No arbitrary numbers. Back every pricing decision with market research.\n"
            f"Consider segment willingness-to-pay, purchasing power, and payment methods.\n\n"
            f"{profile}"
        ),
        context=[t1, t2],
        expected_output=(
            f"{cfg['pricing_models']} pricing models with justified price points, "
            f"revenue projections, and competitive positioning."
        ),
    )
    t4 = Task(
        agent=customer_insights,
        description=(
            f"Identify real customer pain points and behaviors.\n\n"
            f"You MUST include:\n"
            f"- {cfg['pain_points']} prioritized pain points (ranked by severity)\n"
            f"- Customer segments (e.g., SMEs vs. enterprises, geography, use case)\n"
            f"- Purchase barriers (cost, complexity, trust, availability)\n"
            f"- Willingness to pay by segment\n"
            f"- Current solution gaps (what aren't existing solutions solving?)\n\n"
            f"Ground in real data: surveys, reports, user interviews, market research.\n"
            f"Avoid generic statements. Be specific with supporting evidence.\n\n"
            f"{profile}"
        ),
        context=[t1, t2],
        expected_output=(
            f"{cfg['pain_points']} prioritized customer pain points with segment analysis, "
            f"purchase barriers, and supporting research sources."
        ),
    )
    t5 = Task(
        agent=report_writer,
        description=(
            f"Synthesize all findings into final strategic business report.\n\n"
            f"You MUST:\n"
            f"- Combine insights from all agents into coherent narrative\n"
            f"- Ensure consistency across market size, competitors, pricing, pain points\n"
            f"- Return ONLY valid JSON (no markdown, no explanations outside JSON)\n"
            f"- Include entry_recommendations array with {cfg['entry_recommendations']} actionable strategies\n"
            f"- Aggregate ALL sources from other agents ({cfg['sources_min']}+ minimum)\n\n"
            f"JSON Keys required:\n"
            f"  - idea, region, segment (context)\n"
            f"  - market_overview (string, {cfg['market_overview_words']} words)\n"
            f"  - market_cap (string, e.g., '$5B by 2028')\n"
            f"  - competitors (array of objects: name, description, url, strengths, weaknesses)\n"
            f"  - pricing_models (array of strings)\n"
            f"  - pain_points (array of strings)\n"
            f"  - entry_recommendations (array of strings)\n"
            f"  - sources (array of URLs/references, {cfg['sources_min']}-20 items)\n"
            f"  - reasoning_log (optional, brief summary of analysis)\n\n"
            f"{profile}"
        ),
        context=[t1, t2, t3, t4],
        expected_output=(
            "Valid JSON object only (no markdown). Keys: idea, region, segment, "
            "market_overview, market_cap, competitors, pricing_models, pain_points, "
            "entry_recommendations, sources."
        ),
    )

    return Crew(
        agents=[market_researcher, competitor_analyst, pricing_strategist, customer_insights, report_writer],
        tasks=[t1, t2, t3, t4, t5],
        process=Process.sequential,
        verbose=True,
    )


def run_research_crew(
    idea: str, region: str, segment: str, depth: str
) -> tuple[MarketResearchReport, str]:
    """Build the crew and execute live research, returning a report plus a reasoning log string."""
    crew = _build_crew(idea=idea, region=region, segment=segment, depth=depth)

    try:
        # FIX 5: Removed redundant inputs={...} from kickoff — profile is already
        #         embedded as f-strings in task descriptions at Task creation time.
        #         Passing inputs only matters when task descriptions use {variable} placeholders.
        result = crew.kickoff()
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower():
            raise RuntimeError(
                "Gemini API quota exceeded (429 RESOURCE_EXHAUSTED). "
                "Please enable billing or wait for quota reset, then retry."
            ) from exc
        raise RuntimeError(f"Crew execution failed: {message}") from exc

    raw_output = result.raw if hasattr(result, "raw") else str(result)

    # FIX 6: Added JSON retry — if first parse fails, re-prompt Gemini to repair the
    #         output before falling back to regex extraction.
    report = _build_report_from_output(
        raw_output=raw_output, idea=idea, region=region, segment=segment, depth=depth
    )

    log = f"✅ Crew executed successfully. Output preview:\n{raw_output[:500]}..."
    return report, log


def _build_report_from_output(
    raw_output: str, idea: str, region: str, segment: str, depth: str = _DEFAULT_DEPTH
) -> MarketResearchReport:
    """Parse crew output into structured report fields with JSON-first fallback."""
    parsed = _extract_json_payload(raw_output)

    # FIX 6 (cont): Attempt a Gemini-assisted JSON repair before falling back to regex.
    if parsed is None:
        parsed = _retry_json_extraction(raw_output)

    if parsed is None:
        return MarketResearchReport(
            idea=idea,
            region=region,
            segment=segment,
            depth=depth,
            market_overview=(
                raw_output[:700] if raw_output
                else f"Research conducted on {idea} for {segment} in {region}."
            ),
            market_cap=_extract_market_cap(raw_output),
            competitors=[],
            pricing_models=_extract_bullets(raw_output, "pricing"),
            pain_points=_extract_bullets(raw_output, "pain"),
            entry_recommendations=_extract_bullets(raw_output, "entry"),
            sources=_extract_sources(raw_output),
            # FIX 7: Truncate reasoning_log to 2000 chars — storing full raw output
            #         inflated cache files and caused massive token usage in follow-up prompts.
            reasoning_log=raw_output[:2000] if raw_output else None,
        )

    # FIX 8: Extracted competitor parsing into _parse_competitors() —
    #         _build_report_from_output was doing too much in one function.
    competitors = _parse_competitors(parsed.get("competitors", []))

    return MarketResearchReport(
        idea=idea,
        region=region,
        segment=segment,
        depth=depth,
        market_overview=(
            str(parsed.get("market_overview", "")).strip()
            or f"Research conducted on {idea} for {segment} in {region}."
        ),
        market_cap=_safe_str(parsed.get("market_cap")) or _extract_market_cap(raw_output),
        competitors=competitors,
        pricing_models=_as_string_list(parsed.get("pricing_models")),
        pain_points=_as_string_list(parsed.get("pain_points")),
        entry_recommendations=_as_string_list(parsed.get("entry_recommendations")),
        sources=_as_string_list(parsed.get("sources")),
        reasoning_log=raw_output[:2000] if raw_output else None,
    )


# FIX 8 (cont): New dedicated function for competitor parsing — clean and testable.
def _parse_competitors(competitors_data: object) -> list[Competitor]:
    """Normalize raw competitor data from parsed JSON into Competitor models."""
    if not isinstance(competitors_data, list):
        return []
    competitors: list[Competitor] = []
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
    return competitors


# FIX 6 (cont): New retry helper — calls Gemini directly to repair malformed JSON
#               before the regex fallback is used.
def _retry_json_extraction(raw_output: str) -> dict | None:
    """Ask Gemini to repair malformed JSON output from the crew."""
    if not raw_output:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            "The following text should be a JSON object but may have formatting issues "
            "(e.g. wrapped in markdown, trailing text). "
            "Extract and return ONLY the valid JSON object. No markdown. No explanation.\n\n"
            f"{raw_output[:4000]}"
        )
        response = model.generate_content(prompt)
        return _extract_json_payload(response.text)
    except Exception:
        return None


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
    candidates: list[str] = []
    fenced = re.findall(r"```json\s*(\{.*?\})\s*```", raw_output, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(fenced)
    stripped = raw_output.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
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
    return [line for line in lines if any(term in line.lower() for term in terms)][:6]


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
