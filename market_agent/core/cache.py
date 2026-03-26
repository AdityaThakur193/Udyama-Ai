"""In-memory and optional JSON-backed cache for generated reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from market_agent.core.schema import MarketResearchReport


REPORT_CACHE: dict[str, MarketResearchReport] = {}
_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _report_path(signature: str) -> Path:
    # Hashing keeps filenames short and filesystem-safe.
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    return _REPORTS_DIR / f"{digest}.json"


def _load_reports_from_disk() -> None:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for file_path in _REPORTS_DIR.glob("*.json"):
        try:
            payload = json.loads(file_path.read_text("utf-8"))
            signature = payload["signature"]
            report = MarketResearchReport.model_validate(payload["report"])
            REPORT_CACHE[signature] = report
        except Exception:
            continue


def get_cached_report(signature: str) -> Optional[MarketResearchReport]:
    """Return a report from memory cache if present."""
    return REPORT_CACHE.get(signature)


def save_report(signature: str, report: MarketResearchReport) -> None:
    """Persist a report in memory and optionally on disk."""
    REPORT_CACHE[signature] = report
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"signature": signature, "report": report.model_dump()}
    _report_path(signature).write_text(json.dumps(payload, indent=2), encoding="utf-8")


_load_reports_from_disk()
