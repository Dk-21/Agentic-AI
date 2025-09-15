# gatekeeper/summarizer.py
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

SYSTEM = (
    "You are a senior release engineer. Write a concise, factual, developer-facing summary "
    "based ONLY on the provided inputs. Do not speculate. Keep it under 160 words. "
    "Output Markdown with these sections: "
    "1) Overview (one sentence), 2) Signals (bulleted), 3) Decision & Rationale (short), 4) Links, 5) Next Steps."
)

USER_TMPL = (
    "Repo: {repo}\n"
    "Target: {target}\n"
    "Decision: {decision}\n"
    "Confidence: {confidence}\n"
    "Reasons:\n{reasons}\n"
    "Checks Summary:\n{checks_lines}\n"
    "Blockers Count: {blockers_count}\n"
    "PR URL: {pr_url}\n"
    "Workflow URL: {run_url}\n"
    "Notes: Only use the facts above. If anything is missing, omit it.\n"
)

def _checks_lines(checks: List[Dict[str, Any]]) -> str:
    if not checks:
        return "- (no check runs found)"
    out = []
    for r in checks[:12]:
        name = r.get("name", "unknown")
        concl = r.get("conclusion", "unknown")
        out.append(f"- {name}: {concl}")
    if len(checks) > 12:
        out.append(f"- ... and {len(checks) - 12} more")
    return "\n".join(out)

def make_summary_md(state: Dict[str, Any], model: str = "gemini-1.5-flash-002") -> str:
    repo = state["repo"]
    decision = state.get("decision", "UNKNOWN")
    confidence = state.get("confidence", 0.0)
    reasons = state.get("reasons", [])
    pr = state.get("pr") or {}
    pr_url = pr.get("url", "")
    run_url = (state.get("actions", {}) or {}).get("latest_run", {}).get("url", "")
    checks = (state.get("checks", {}) or {}).get("runs", []) or []
    blockers_count = len(state.get("blockers", []) or [])

    # Build plain-text inputs (no JSON/braces to avoid formatting issues)
    reasons_lines = "\n".join([f"- {r}" for r in reasons]) or "- (none)"
    checks_lines = _checks_lines(checks)
    target = f"PR #{pr.get('number')}" if pr else f"branch head ({state.get('base_branch')})"

    user = USER_TMPL.format(
        repo=repo,
        target=target,
        decision=decision,
        confidence=confidence,
        reasons=reasons_lines,
        checks_lines=checks_lines,
        blockers_count=blockers_count,
        pr_url=pr_url,
        run_url=run_url,
    )

    try:
        llm = ChatGoogleGenerativeAI(model=model, temperature=0.2)
        resp = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=user)])
        return (resp.content or "").strip()
    except Exception:
        # Fallback: deterministic summary
        lines = []
        lines.append("Overview")
        lines.append(f"{repo}: decision **{decision}** (confidence {confidence}).")
        lines.append("\nSignals")
        lines.append(checks_lines)
        lines.append("\nDecision & Rationale")
        lines.append(reasons_lines)
        links = []
        if pr_url: links.append(f"- PR: {pr_url}")
        if run_url: links.append(f"- Workflow: {run_url}")
        if links:
            lines.append("\nLinks")
            lines.extend(links)
        lines.append("\nNext Steps")
        if decision == "GO":
            lines.append("- Proceed with release per checklist.")
        elif decision == "NO_GO":
            lines.append("- Triage failures, re-run CI, clear blockers, re-evaluate.")
        else:
            lines.append("- Clarify missing signals or address flagged risks, then re-run.")
        return "\n".join(lines)
