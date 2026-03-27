"""Tool initialization for CrewAI agents."""

from __future__ import annotations

from crewai_tools import SerperDevTool

from market_agent.core.settings import SERPER_API_KEY

# FIX 1: Added depth-configured tool instances — previously a single shared tool
#         with no n_results setting meant Quick and Deep searches returned the same
#         number of results, giving depth parameter no effect at the search layer.
_SERPER_QUICK = SerperDevTool(api_key=SERPER_API_KEY, n_results=5)
_SERPER_DEEP = SerperDevTool(api_key=SERPER_API_KEY, n_results=10)

# Kept for backward compatibility — used as fallback when depth is unrecognised.
serper_tool = _SERPER_DEEP


def get_serper_tool(depth: str) -> SerperDevTool:
    """Return a Serper search tool configured for the given research depth.

    Quick: 5 results per query — faster, lower quota usage.
    Deep:  10 results per query — broader coverage, more sources surfaced.
    """
    # FIX 1 (cont): Returns a pre-built singleton, not a new instance per call,
    #               so there is no per-request construction overhead.
    return _SERPER_QUICK if depth == "Quick" else _SERPER_DEEP

# Add other tools here later, for example website scrapers or database retrievers.
