"""Follow-up Q&A helper using report context and Gemini integration."""

from __future__ import annotations

import json

import google.generativeai as genai

from market_agent.core.schema import MarketResearchReport
from market_agent.core.settings import GEMINI_API_KEY


def answer_followup(question: str, report: MarketResearchReport) -> str:
    """Return a concise answer grounded in the generated market report using Gemini Flash."""
    cleaned = question.strip()
    if not cleaned:
        return "Please enter a follow-up question."

    # Serialize the report so the model answers only from known research context.
    context_json = json.dumps(report.model_dump(), indent=2)

    prompt = (
        "You are a market intelligence assistant. "
        "Answer the user's question using ONLY the provided report context. "
        "Be concise and practical.\n\n"
        f"Report Data:\n{context_json}\n\n"
        f"User Question: {cleaned}"
    )

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {str(e)}"
