"""Follow-up Q&A helper using report context and Gemini integration placeholder."""

from __future__ import annotations

import json

from market_agent.core.schema import MarketResearchReport


def answer_followup(question: str, report: MarketResearchReport) -> str:
    """Return a concise answer grounded in the generated market report."""
    cleaned = question.strip()
    if not cleaned:
        return "Please enter a follow-up question."

    context_json = json.dumps(report.model_dump(), indent=2)

    # TODO: Integrate Gemini Flash here using google-generativeai with GEMINI_API_KEY.
    # Prompt design should include context_json and cleaned, then return model text.
    _prompt = (
        "You are a market intelligence assistant. "
        "Answer using only the report context.\n"
        f"Report JSON:\n{context_json}\n\n"
        f"Question: {cleaned}"
    )

    return (
        f"Based on the current report for {report.idea} in {report.region}, "
        "the most practical next step is to validate one entry recommendation with a small pilot, "
        "then refine pricing and positioning from user feedback."
    )
