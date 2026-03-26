"""Tool initialization for CrewAI agents."""

from crewai_tools import SerperDevTool

from market_agent.core.settings import SERPER_API_KEY


# Shared search tool instance reused by all agents.
serper_tool = SerperDevTool(api_key=SERPER_API_KEY)

# Add other tools here later, for example website scrapers or database retrievers.
