# Udyama-Ai: Market Intelligence Agent

Streamlit app that helps founders generate a market research brief using multi-agent workflows (CrewAI + Gemini + Serper).

## Current Status

- Working UI with research input, insights tabs, and follow-up view.
- Live research pipeline is connected through CrewAI.
- Gemini model configured as `gemini-2.5-flash`.
- Tracing is enabled for CrewAI runs.
- Report parsing supports structured JSON output and fallback extraction.
- Caching is implemented for generated reports by input signature.

## Features

### 1. Research Input

- Startup idea input
- Region selection (`India`, `US`, `EU`, `Southeast Asia`, `Global`)
- Segment selection (`Consumers`, `SMEs`, `Enterprises`, `Students`, `Healthcare`, `Farmers`, `Gig Workers`)
- Depth selection (`Quick`, `Deep`)
- Dummy mode toggle for UI testing

### 2. Multi-Agent Research Crew

Agents used:

- Market Research Specialist
- Competitive Intelligence Analyst
- Pricing and Monetization Strategist
- Customer Insights Researcher
- Market Intelligence Report Writer

Tools/LLM:

- Serper search tool
- Gemini (`gemini-2.5-flash`)
- CrewAI sequential execution

### 3. Insights Rendering

- Market overview
- Competitor cards (with strengths/weaknesses and links)
- Pricing models
- Pain points
- Entry recommendations
- Reasoning log
- Source trail

### 4. Caching

- Report cache by hashed signature of `idea|region|segment|depth`
- In-memory + JSON-backed persistence

### 5. Tracing

- Crew tracing is enabled in code and at runtime env defaults.

## Known Limitations

### Follow-up is currently hardcoded

The follow-up Q&A is **not connected to Gemini yet**.

- File: `market_agent/agents/followup.py`
- Function: `answer_followup(...)`
- It currently returns a static template response.

### Live run dependency

- Live research requires valid `GEMINI_API_KEY` and `SERPER_API_KEY`.
- If Gemini quota is exhausted, research run will fail with a clear runtime message.

## Project Structure

```
Udyama-Ai/
	app.py
	requirements.txt
	.streamlit/
		secrets.toml
	market_agent/
		__init__.py
		agents/
			__init__.py
			crew.py
			roles.py
			tools.py
			followup.py
		core/
			__init__.py
			cache.py
			schema.py
			settings.py
```

## Setup

1. Create virtual environment

```powershell
python -m venv .venv
```

2. Install dependencies

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Configure API keys in `.streamlit/secrets.toml`

```toml
GEMINI_API_KEY = "your-gemini-key"
SERPER_API_KEY = "your-serper-key"
```

4. Run app

```powershell
.venv\Scripts\streamlit.exe run app.py
```

## Notes

- `.streamlit/secrets.toml` is ignored via `.gitignore`.
- `.venv/` should remain local and not be committed.
