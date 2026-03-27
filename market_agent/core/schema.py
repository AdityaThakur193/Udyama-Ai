"""Pydantic models for market intelligence outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# FIX 1: Removed `from typing import Optional` — replaced with str | None style
#         throughout, consistent with PEP 604 and the existing __future__ annotation.

_VALID_DEPTHS: frozenset[str] = frozenset({"Quick", "Deep"})


class Competitor(BaseModel):
    """Represents one competitor in the target market."""

    model_config = ConfigDict(extra="ignore")

    name: str
    # FIX 2: Added default="" — previously required, so missing "description" key in
    #         Gemini JSON output caused a ValidationError and crashed report parsing.
    description: str = ""
    url: str | None = None
    strengths: str | None = None
    weaknesses: str | None = None


class MarketResearchReport(BaseModel):
    """Structured output consumed by the Streamlit dashboard."""

    model_config = ConfigDict(extra="ignore")

    # ── Core inputs ───────────────────────────────────────────────────────────
    idea: str
    region: str
    segment: str

    # FIX 3: Added `depth` field — was passed into crew.py and cache.py but never
    #         stored in the report, making it impossible to know what depth a cached
    #         report was generated at, or to display it correctly in the history panel.
    depth: Literal["Quick", "Deep"] = "Deep"

    # FIX 4: Added `created_at` — required to sort session history newest-first
    #         in the UI. Defaults to current UTC time at report construction.
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ── Research outputs ──────────────────────────────────────────────────────
    # FIX 5: Added default="" for market_overview — previously required, causing
    #         a ValidationError if the ReportWriter omitted it from JSON output.
    market_overview: str = ""
    market_cap: str | None = None

    # FIX 6: Added default_factory=list for all list fields — previously required,
    #         so any key missing from Gemini's JSON output raised a ValidationError
    #         and fell through to the regex fallback unnecessarily.
    competitors: list[Competitor] = Field(default_factory=list)
    pricing_models: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    entry_recommendations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    # Truncated crew output for debug display — max 2000 chars (enforced in crew.py).
    reasoning_log: str | None = None

    # FIX 7: Field validator normalises unexpected depth values to "Deep" instead
    #         of raising a ValidationError — defensive against future UI additions.
    @field_validator("depth", mode="before")
    @classmethod
    def _normalise_depth(cls, v: object) -> str:
        if isinstance(v, str) and v in _VALID_DEPTHS:
            return v
        return "Deep"

    @property
    def display_label(self) -> str:
        """Short human-readable label for use in history panels and tabs."""
        return f"{self.idea[:40]} · {self.region} · {self.segment}"
