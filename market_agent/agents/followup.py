"""Follow-up Q&A helper using report context and Gemini integration."""

from __future__ import annotations

import json

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


def answer_followup(question: str, report: MarketResearchReport) -> str:
    """Return a concise answer grounded in the generated market report using Gemini Flash."""
    cleaned = question.strip()
    if not cleaned:
        return "Please enter a follow-up question."

    # FIX 2 (cont): Exclude reasoning_log (and any other noisy fields) before
    #               serialising — keeps prompt lean without losing useful context.
    context_data = report.model_dump(exclude=_EXCLUDED_FROM_CONTEXT)
    context_json = json.dumps(context_data, indent=2)

    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Report Data:\n{context_json}\n\n"
        f"User Question: {cleaned}"
    )

    try:
        response = _MODEL.generate_content(prompt)
        return response.text

    # FIX 3: Distinguish specific failure modes instead of one bare except —
    #         gives the user an actionable message rather than a raw exception dump.
    except genai.types.BlockedPromptException:
        return "⚠️ Your question was blocked by the safety filter. Please rephrase it."
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower():
            return (
                "⚠️ Gemini API quota exceeded. "
                "Please wait a moment and try again, or check your billing settings."
            )
        if "API_KEY" in message or "credentials" in message.lower() or "401" in message:
            return "⚠️ Gemini API key is invalid or missing. Check your GEMINI_API_KEY setting."
        return f"⚠️ Could not generate a response: {message}"
