"""In-memory and optional JSON-backed cache for generated reports."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from market_agent.core.schema import MarketResearchReport

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"

# Primary report cache keyed by signature.
REPORT_CACHE: dict[str, MarketResearchReport] = {}

# FIX 4: Separate lightweight metadata store — keeps display info (idea, created_at)
#         without deserialising the full report for list/history operations.
_REPORT_META: dict[str, dict] = {}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _report_path(signature: str) -> Path:
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
    return _REPORTS_DIR / f"{digest}.json"


def _load_reports_from_disk() -> None:
    """Populate in-memory cache from persisted JSON files at startup."""
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    loaded, skipped = 0, 0
    for file_path in _REPORTS_DIR.glob("*.json"):
        try:
            payload = json.loads(file_path.read_text("utf-8"))
            signature = payload["signature"]
            report = MarketResearchReport.model_validate(payload["report"])
            REPORT_CACHE[signature] = report
            # FIX 4 (cont): Populate metadata from stored payload.
            _REPORT_META[signature] = {
                "created_at": payload.get("created_at", ""),
                "idea": payload.get("idea", report.idea),
                "region": payload.get("region", report.region),
                "segment": payload.get("segment", report.segment),
                "file": str(file_path),
            }
            loaded += 1
        # FIX 1: Log skipped files with a reason instead of silently swallowing errors.
        #         Silent `except: continue` made corrupt cache files impossible to diagnose.
        except KeyError as exc:
            logger.warning("Skipping cache file %s — missing key: %s", file_path.name, exc)
            skipped += 1
        except Exception as exc:
            logger.warning("Skipping cache file %s — %s: %s", file_path.name, type(exc).__name__, exc)
            skipped += 1
    if loaded or skipped:
        logger.info("Cache loaded: %d reports, %d skipped.", loaded, skipped)


# ── Public API ────────────────────────────────────────────────────────────────

def get_cached_report(signature: str) -> MarketResearchReport | None:
    """Return a report from memory cache if present."""
    return REPORT_CACHE.get(signature)


def save_report(signature: str, report: MarketResearchReport) -> None:
    """Persist a report in memory and on disk."""
    REPORT_CACHE[signature] = report
    created_at = datetime.now(timezone.utc).isoformat()
    # FIX 4 (cont): Store metadata in memory for fast list operations.
    _REPORT_META[signature] = {
        "created_at": created_at,
        "idea": report.idea,
        "region": report.region,
        "segment": report.segment,
    }
    # FIX 2: Added error handling for disk write — previously a full disk or
    #         permission error would raise an unhandled exception and crash the app.
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": signature,
        "created_at": created_at,
        "idea": report.idea,
        "region": report.region,
        "segment": report.segment,
        "report": report.model_dump(),
    }
    try:
        _report_path(signature).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to persist report to disk: %s", exc)


# FIX 3: Added list_all_reports() — required by the UI session history panel.
#         Previously there was no way to enumerate stored reports without reading
#         raw files from disk.
def list_all_reports() -> list[dict]:
    """Return all cached report summaries sorted by created_at descending.

    Each entry contains: signature, created_at, idea, region, segment.
    Use get_cached_report(signature) to fetch the full report.
    """
    entries = []
    for sig, meta in _REPORT_META.items():
        entries.append({"signature": sig, **meta})
    return sorted(entries, key=lambda x: x.get("created_at", ""), reverse=True)


# FIX 5: Added delete_report() — required for per-report delete in history UI.
def delete_report(signature: str) -> None:
    """Remove a report from memory cache and delete its file from disk."""
    REPORT_CACHE.pop(signature, None)
    _REPORT_META.pop(signature, None)
    path = _report_path(signature)
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        logger.warning("Could not delete cache file %s: %s", path.name, exc)


# FIX 6: Added clear_all_reports() — required for "Clear History" UI button.
def clear_all_reports() -> None:
    """Wipe all reports from memory and remove all cached files from disk."""
    REPORT_CACHE.clear()
    _REPORT_META.clear()
    for file_path in _REPORTS_DIR.glob("*.json"):
        try:
            file_path.unlink()
        except OSError as exc:
            logger.warning("Could not delete %s: %s", file_path.name, exc)


# Load persisted reports into memory on first import.
_load_reports_from_disk()
