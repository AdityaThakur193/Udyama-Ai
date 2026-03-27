"""Pydantic models for market intelligence outputs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class Competitor(BaseModel):
    """Represents one competitor in the target market."""

    # Ignore unknown keys so partial/extra model outputs do not fail validation.
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str
    url: Optional[str] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None


class MarketResearchReport(BaseModel):
    """Structured output consumed by the Streamlit dashboard."""

    model_config = ConfigDict(extra="ignore")

    idea: str
    region: str
    segment: str
    market_overview: str
    market_cap: Optional[str] = None
    competitors: list[Competitor]
    pricing_models: list[str]
    pain_points: list[str]
    entry_recommendations: list[str]
    sources: list[str]
    reasoning_log: Optional[str] = None
