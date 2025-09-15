# Release Gatekeeper (LangGraph + Gemini)

[![python](https://img.shields.io/badge/python-3.10%2B-informational.svg)](https://www.python.org/)
[![framework](https://img.shields.io/badge/agent-LangGraph-5b9bd5.svg)](https://python.langchain.com/docs/langgraph)
[![llm](https://img.shields.io/badge/LLM-Gemini-34d399.svg)](https://ai.google.dev/)


An autonomous **Release Gatekeeper** for developer workflows. It picks the freshest open PR (or the base branch head), fetches **GitHub Actions** status, **check runs**, and labeled **blocker issues**, applies deterministic **redlines**, and—if clean—asks a **Gemini** judge for a structured `GO | PAUSE | NO_GO` decision with **evidence** that’s programmatically **verified**. It then emits a concise developer digest. Built to demonstrate **autonomy**, **reasoning**, and **safe tool usage** on real APIs.

---

## Quickstart

```bash
# 1) Create & activate a virtualenv (Python 3.10+)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt
Create a .env in the project root:

dotenv
# Required for Gemini (Google AI)
GOOGLE_API_KEY=your_gemini_api_key

# Optional: increases GitHub rate limits (public repos work without it)
GITHUB_TOKEN=your_github_pat
```

## Run the gatekeeper:

```bash
export PYTHONPATH=.
python main.py --repo refinedev/refine --base-branch main --format pretty
python main.py --repo refinedev/refine --format md > report.md
python main.py --repo refinedev/refine --format json
# On start, the tool auto-cleans Python caches in this repo (__pycache__, .pyc/.pyo).
# Set GATEKEEPER_SKIP_AUTOCLEAN=1 to skip cleanup.
```

## What & Why
What: A small agent that makes Go/No-Go decisions for releases using GitHub signals + an LLM with guardrails (structured output + evidence verification).

Why: It showcases end-to-end autonomy (one command runs everything), reasoning (judge + verifier), and real tool usage (GitHub APIs) in a developer-tools context. Works on public OSS repos without admin permissions.

## How it Works
### flowchart TD
```

  A([Start]) --> B[Auto Cache Cleanup<br/>(__pycache__, .pyc/.pyo)]
  B --> C[Normalize Repo Input<br/>URL → owner/name]
  C --> D[Select Target<br/>Freshest PR into base, else branch head]
  D --> E[Fetch Signals (GitHub)<br/>Actions latest_run • Check runs • Blockers by label]
  E --> F{Redlines tripped?}
  F -- Yes --> NG[Deterministic NO_GO]
  NG --> S[Summarize → Developer Digest]
  F -- No --> J[LLM Judge (Gemini)<br/>Structured {decision, reasons, evidence, confidence}]
  J --> V{Evidence verified?}
  V -- No --> P[PAUSE<br/>policy_violations logged]
  V -- Yes --> DEC[GO | PAUSE | NO_GO]
  P --> S
  DEC --> S
  S --> R[Render Report & Exit Code<br/>GO=0 • PAUSE=1 • NO_GO=2]
```
Redlines (deterministic): latest workflow run not success, any failing check, or open blocker → NO_GO (LLM skipped).


LLM Judge (Gemini): returns structured JSON; Verifier enforces that each evidence item cites a real path & value from fetched signals (mismatch ⇒ PAUSE).

## Example Commands
```bash
# Use a URL or owner/name (input is normalized)
python main.py --repo https://github.com/refinedev/refine --base-branch main --format pretty
python main.py --repo refinedev/refine --format md > gatekeeper_report.md

Exit codes (for CI):
Decision	Code
GO          0
PAUSE	    1
NO_GO	    2
UNKNOWN	    3
```


## Project Layout
```
release-gatekeeper/
├─ main.py                      # CLI + auto cache cleanup + rendering
├─ tools/
│  └─ github_tools.py           # GitHub REST wrappers
├─ gatekeeper/
│  ├─ state.py                  # Typed state
│  ├─ graph.py                  # LangGraph nodes & routing
│  ├─ judge.py                  # Gemini structured judge (Pydantic v2)
│  ├─ verifier.py               # Evidence path normalization + checks
│  └─ summarizer.py             # Developer digest (Markdown)
└─ utils/
   └─ repo_normalize.py         # URL → owner/name
```
## Assumptions & Limitations
Designed to work on public repos without admin rights; since required-branch-checks aren’t readable, we use strict mode (any failed check = redline).

Uses the latest workflow run for the chosen ref; historical trends and flaky-test analysis are out of scope for this basic version.

Network/API availability and rate limits apply.

LLM output is structured and verified, but ambiguous inputs can still yield PAUSE (fail-safe by design).

## Troubleshooting
401 Unauthorized        → Remove/refresh GITHUB_TOKEN; public reads work unauthenticated.

Evidence path mismatch  → Evidence should cite: actions.latest_run.conclusion, checks.runs.0.conclusion, blockers.

Prose/non-JSON from LLM → Judge uses structured output; if it ever fails, retry or use gemini-1.5-pro-002.

Skip auto-clean         → export GATEKEEPER_SKIP_AUTOCLEAN=1
