"""Follow-up Q&A helper using report context and Gemini integration."""

from __future__ import annotations

import json
import re
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

_STOPWORDS: set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "what",
    "when", "where", "which", "who", "why", "will", "with", "you", "your", "can", "should",
}


def _tokenise(text: str) -> set[str]:
    return {
        tok for tok in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(tok) > 2 and tok not in _STOPWORDS
    }


def _report_context_chunks(report: MarketResearchReport) -> list[str]:
    chunks: list[str] = []

    if report.market_overview:
        chunks.append(f"Market overview: {report.market_overview}")
    if report.market_cap:
        chunks.append(f"Market cap estimate: {report.market_cap}")

    for comp in (report.competitors or [])[:8]:
        parts = [
            f"Competitor: {comp.name or 'Unknown'}",
            f"Description: {comp.description or ''}",
            f"Strengths: {comp.strengths or ''}",
            f"Weaknesses: {comp.weaknesses or ''}",
        ]
        chunks.append(" | ".join(p for p in parts if p.strip()))

    for item in (report.pricing_models or [])[:8]:
        chunks.append(f"Pricing model: {item}")
    for item in (report.pain_points or [])[:8]:
        chunks.append(f"Pain point: {item}")
    for item in (report.entry_recommendations or [])[:8]:
        chunks.append(f"Entry recommendation: {item}")
    for src in (report.sources or [])[:8]:
        chunks.append(f"Source: {src}")

    return [c.strip() for c in chunks if c and c.strip()]


def _keyword_context_answer(question: str, report: MarketResearchReport, top_n: int = 3) -> str | None:
    """Return top matching report snippets for the user question."""
    q_tokens = _tokenise(question)
    if not q_tokens:
        return None

    scored: list[tuple[int, str]] = []
    for chunk in _report_context_chunks(report):
        c_tokens = _tokenise(chunk)
        overlap = q_tokens.intersection(c_tokens)
        if overlap:
            scored.append((len(overlap), chunk))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [text for _, text in scored[:top_n]]
    bullets = "\n".join(f"- {s}" for s in selected)
    return f"From your report, the most relevant points are:\n{bullets}"


def _build_report_fallback_answer(question: str, report: MarketResearchReport) -> str:
    """Return a concise direct answer from report fields without external model calls."""
    q = question.lower()

    if "competitor" in q and report.competitors:
        names = [c.name.strip() for c in report.competitors if c.name and c.name.strip()]
        if names:
            return "From your report, the main competitors are: " + ", ".join(names[:8])

    if ("pricing" in q or "price" in q) and report.pricing_models:
        return "From your report, pricing options are: " + "; ".join(report.pricing_models[:6])

    if any(x in q for x in ("pain", "problem", "challenge")) and report.pain_points:
        return "From your report, top pain points are: " + "; ".join(report.pain_points[:6])

    if any(x in q for x in ("entry", "gtm", "go to market", "recommend")) and report.entry_recommendations:
        return "From your report, recommended entry moves are: " + "; ".join(report.entry_recommendations[:6])

    contextual = _keyword_context_answer(question, report)
    if contextual:
        return contextual

    overview = (report.market_overview or "").strip()
    if overview:
        return (
            "Direct report-based answer (model call skipped): "
            f"{overview[:700]}"
        )

    return (
        "I could not find enough detail in the current report to answer that directly. "
        "Try asking about competitors, pricing, pain points, or entry strategy."
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
    allow_model_call: bool = True,
) -> tuple[str, bool]:
    """Return a concise answer grounded in the generated market report using Gemini Flash."""
    cleaned = question.strip()
    if not cleaned:
        return "Please enter a follow-up question.", False

    try:
        report_obj = _normalise_report(report)
    except Exception:
        return (
            "⚠️ Report context is not available for follow-up right now. "
            "Please regenerate or reload the report and try again."
        ), False
    history_turns = _normalise_history(history)

    local_answer = _local_report_answer(cleaned, report_obj)
    if local_answer:
        return local_answer, False

    if not allow_model_call:
        return _build_report_fallback_answer(cleaned, report_obj), False

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

    model_call_attempted = True

    try:
        response = _MODEL.generate_content(prompt)
        text = getattr(response, "text", None)
        if text and str(text).strip():
            return str(text).strip(), model_call_attempted
        return (
            "I could not generate a clear follow-up answer from the report context. "
            "Please rephrase your question more specifically."
        ), model_call_attempted

    # FIX 3: Distinguish specific failure modes instead of one bare except —
    #         gives the user an actionable message rather than a raw exception dump.
    except genai.types.BlockedPromptException:
        return "⚠️ Your question was blocked by the safety filter. Please rephrase it.", model_call_attempted
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower():
            backup = _build_report_fallback_answer(cleaned, report_obj)
            if backup:
                return (
                    "Gemini quota is currently exceeded, so here is a direct report-based answer:\n"
                    f"{backup}"
                ), model_call_attempted
            return (
                "Gemini API quota exceeded, and I could not find a direct field answer in the report. "
                "Please retry after quota reset."
            ), model_call_attempted
        if "API_KEY" in message or "credentials" in message.lower() or "401" in message:
            return "⚠️ Gemini API key is invalid or missing. Check your GEMINI_API_KEY setting.", model_call_attempted
        return f"⚠️ Could not generate a response: {message}", model_call_attempted
