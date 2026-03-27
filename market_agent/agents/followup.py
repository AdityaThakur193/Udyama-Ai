"""Follow-up Q&A helper using report context and Gemini integration."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from market_agent.core.schema import MarketResearchReport
from market_agent.core.settings import GEMINI_API_KEY

# FIX 1: Module-level singleton — genai.configure() and GenerativeModel() were being
#         called on every single question, re-initialising the SDK needlessly each time.
genai.configure(api_key=GEMINI_API_KEY)
_MODEL = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    # FIX 4: Added generation config — no token ceiling meant follow-up answers
    #         could balloon in length and cost. Capped at 512 tokens for concise replies.
    generation_config=GenerationConfig(
        temperature=0.3,
        max_output_tokens=512,
    ),
)

# FIX 2: Fields excluded from the report context sent to Gemini.
#         reasoning_log alone can be thousands of tokens — including it in every
#         follow-up prompt was massively inflating token usage and cost.
_EXCLUDED_FROM_CONTEXT: set[str] = {"reasoning_log"}

_SYSTEM_PROMPT = (
    "You are a market intelligence assistant. "
    "Answer the user's question using ONLY the provided report context. "
    "If the answer is not in the report, say so clearly. "
    "Be concise, direct, and practical."
)


def _normalise_report(report: MarketResearchReport | dict[str, Any]) -> MarketResearchReport:
    """Convert report payloads to the expected Pydantic model for follow-up prompts."""
    if isinstance(report, MarketResearchReport):
        return report
    if hasattr(report, "model_dump"):
        return MarketResearchReport.model_validate(report.model_dump())
    if isinstance(report, dict) and "report" in report and isinstance(report["report"], dict):
        return MarketResearchReport.model_validate(report["report"])
    return MarketResearchReport.model_validate(report)


def _local_report_answer(question: str, report: MarketResearchReport) -> str | None:
    """Answer common follow-up questions directly from report fields without calling Gemini."""
    q = question.lower()

    if "idea" in q and any(x in q for x in ("what", "startup", "business", "product")):
        return f"Your report is about: {report.idea}"

    if any(x in q for x in ("region", "market", "where")) and "segment" not in q:
        return f"Target region in this report: {report.region}"

    if "segment" in q or "customer" in q or "audience" in q:
        return f"Target segment in this report: {report.segment}"

    if "competitor" in q:
        if not report.competitors:
            return "No competitors were captured in this report."
        names = [c.name.strip() for c in report.competitors if c.name and c.name.strip()]
        if not names:
            return "Competitor names are not clearly available in this report."
        return "Competitors in your report: " + ", ".join(names[:8])

    if "pricing" in q or "price" in q:
        if not report.pricing_models:
            return "No pricing models were listed in this report."
        return "Pricing models in your report: " + "; ".join(report.pricing_models[:6])

    if "pain" in q or "problem" in q or "challenge" in q:
        if not report.pain_points:
            return "No pain points were listed in this report."
        return "Pain points in your report: " + "; ".join(report.pain_points[:6])

    if "entry" in q or "go to market" in q or "gtm" in q or "recommend" in q:
        if not report.entry_recommendations:
            return "No entry recommendations were listed in this report."
        return "Entry recommendations in your report: " + "; ".join(report.entry_recommendations[:6])

    return None


def _normalise_history(
    history: Sequence[dict[str, str]] | None,
    limit: int = 4,
) -> list[dict[str, str]]:
    """Return the last N valid chat turns as clean question/answer pairs."""
    if not history:
        return []

    cleaned: list[dict[str, str]] = []
    for item in history[-limit:]:
        q = str(item.get("question", "")).strip() if isinstance(item, dict) else ""
        a = str(item.get("answer", "")).strip() if isinstance(item, dict) else ""
        if q:
            cleaned.append({"question": q, "answer": a})
    return cleaned


def answer_followup(
    question: str,
    report: MarketResearchReport | dict[str, Any],
    history: Sequence[dict[str, str]] | None = None,
) -> str:
    """Return a concise answer grounded in the generated market report using Gemini Flash."""
    cleaned = question.strip()
    if not cleaned:
        return "Please enter a follow-up question."

    try:
        report_obj = _normalise_report(report)
    except Exception:
        return (
            "⚠️ Report context is not available for follow-up right now. "
            "Please regenerate or reload the report and try again."
        )
    history_turns = _normalise_history(history)

    local_answer = _local_report_answer(cleaned, report_obj)
    if local_answer:
        return local_answer

    # FIX 2 (cont): Exclude reasoning_log (and any other noisy fields) before
    #               serialising — keeps prompt lean without losing useful context.
    context_data = report_obj.model_dump(exclude=_EXCLUDED_FROM_CONTEXT)
    context_json = json.dumps(context_data, indent=2)

    history_block = ""
    if history_turns:
        history_lines = []
        for idx, turn in enumerate(history_turns, start=1):
            history_lines.append(
                f"Turn {idx} Question: {turn['question']}\n"
                f"Turn {idx} Answer: {turn['answer'] or '(no answer)'}"
            )
        history_block = (
            "Conversation History (for continuity only; report remains source of truth):\n"
            + "\n".join(history_lines)
            + "\n\n"
        )

    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Report Data:\n{context_json}\n\n"
        f"{history_block}"
        f"User Question: {cleaned}"
    )

    try:
        response = _MODEL.generate_content(prompt)
        text = getattr(response, "text", None)
        if text and str(text).strip():
            return str(text).strip()
        return (
            "I could not generate a clear follow-up answer from the report context. "
            "Please rephrase your question more specifically."
        )

    # FIX 3: Distinguish specific failure modes instead of one bare except —
    #         gives the user an actionable message rather than a raw exception dump.
    except genai.types.BlockedPromptException:
        return "⚠️ Your question was blocked by the safety filter. Please rephrase it."
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower():
            backup = (
                report_obj.market_overview.strip()
                if isinstance(report_obj.market_overview, str)
                else ""
            )
            if backup:
                return (
                    "Gemini quota is currently exceeded, so here is a direct report-based answer: "
                    f"{backup[:700]}"
                )
            return (
                "Gemini API quota exceeded, and I could not find a direct field answer in the report. "
                "Please retry after quota reset."
            )
        if "API_KEY" in message or "credentials" in message.lower() or "401" in message:
            return "⚠️ Gemini API key is invalid or missing. Check your GEMINI_API_KEY setting."
        return f"⚠️ Could not generate a response: {message}"
