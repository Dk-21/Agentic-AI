from typing import Literal

from langgraph.graph import StateGraph, START, END
from gatekeeper.state import GateState, default_state        
from tools.github_tools import (                
    get_open_pr,
    get_branch_head_sha,
    get_latest_run_for_sha,
    get_check_runs,
    get_blockers,
)
from .state import GateState, default_state
from gatekeeper.judge import llm_decide
from gatekeeper.verifier import verify_evidence
from gatekeeper.summarizer import make_summary_md

# ---------- Nodes ----------

def node_select_target(state: GateState) -> GateState:
    """Pick a release candidate PR (base branch) or fall back to branch head commit."""
    repo = state["repo"]
    base = state["base_branch"]
    # set a label if you want stricter gating
    pr = get_open_pr(repo, base=base, want_label=None)  

    if pr:
        state["pr"] = pr
        state["head_sha"] = pr["head_sha"]
    else:
        head = get_branch_head_sha(repo, branch=base)
        state["pr"] = None
        state["head_sha"] = head["sha"]

    return state

def node_fetch_signals(state: GateState) -> GateState:
    """Fetch Actions run, check runs, and blocker issues for the selected ref."""
    repo = state["repo"]
    sha = state.get("head_sha")
    if not sha:
        state["reasons"] = [*state.get("reasons", []), "No head SHA could be determined."]
        state["decision"] = "PAUSE"
        return state

    latest_run = get_latest_run_for_sha(repo, sha)
    checks_runs = get_check_runs(repo, sha)
    blockers = get_blockers(repo, labels_csv=state["blocker_labels"])

    state["actions"]["latest_run"] = latest_run or {}
    state["checks"]["runs"] = checks_runs or []
    state["blockers"] = blockers or []
    return state

def _is_failed_conclusion(conc: str | None) -> bool:
    """Treat anything not success/neutral/skipped as a failure for redline purposes."""
    if conc is None:
        return True
    return conc.lower() not in {"success", "neutral", "skipped"}

def node_redline_check(state: GateState) -> GateState:
    """Deterministic redlines. If any trip, we return NO_GO and skip LLM."""
    ## False condition
    reasons = list(state.get("reasons", []))

    # 1) Latest workflow must be success
    latest = state.get("actions", {}).get("latest_run", {})
    if not latest or latest.get("conclusion") != "success":
        reasons.append("Latest GitHub Actions workflow run is not 'success'.")

    # 2) Any failed check run → redline (OSS-friendly strict mode)
    failed = [r for r in state.get("checks", {}).get("runs", []) if _is_failed_conclusion(r.get("conclusion"))]
    if failed:
        names = ", ".join(f"{r.get('name')}={r.get('conclusion')}" for r in failed[:5])
        reasons.append(f"One or more check runs failed: {names}")

    # 3) Open blockers by label
    if state.get("blockers"):
        reasons.append(f"Open blocker issues present: {len(state['blockers'])}")

    if reasons:
        state["decision"] = "NO_GO"
        state["reasons"] = reasons
        state["awaiting_llm"] = False
    else:
        # proceed to LLM judge in Part 3
        state["awaiting_llm"] = True  
    return state

def redline_router(state: GateState) -> Literal["NO_GO", "NEEDS_LLM"]:
    """Route based on redline outcome."""
    return "NO_GO" if state.get("decision") == "NO_GO" else "NEEDS_LLM"

# --- Stub nodes for Part 2 (real logic comes in Part 3) ---

def node_llm_judge(state: GateState) -> GateState:
    if not state.get("awaiting_llm"):
        return state

    # Build the signals JSON the judge will see
    signals = {
        "repo": state["repo"],
        "target": {
            "type": "pull_request" if state.get("pr") else "branch_head",
            "number": state.get("pr", {}).get("number") if state.get("pr") else None,
            "head_sha": state.get("head_sha"),
            "base_branch": state["base_branch"],
            "url": state.get("pr", {}).get("url") if state.get("pr") else None,
        },
        "actions": {"latest_run": state.get("actions", {}).get("latest_run", {})},
        "checks": {"runs": state.get("checks", {}).get("runs", [])},
        "blockers": state.get("blockers", []),
    }

    judge = llm_decide(signals)
    verified, violations = verify_evidence(judge, signals)

    if not verified:
        state["decision"] = "PAUSE"
        state["reasons"] = [*state.get("reasons", []), "Evidence verification failed."]
        state["policy_violations"] = [*state.get("policy_violations", []), *violations]
        state["confidence"] = 0.0
        state["awaiting_llm"] = False
        return state

    # Merge judge outcome
    state["decision"] = judge["decision"]
    state["reasons"] = [*state.get("reasons", []), *judge.get("reasons", [])]
    state["evidence"] = judge.get("evidence", [])
    state["policy_violations"] = [*state.get("policy_violations", []), *judge.get("policy_violations", [])]
    state["confidence"] = float(judge.get("confidence", 0.0))
    state["awaiting_llm"] = False
    return state


def node_report(state: GateState) -> GateState:
    
    """Report Generation: No-op here. CLI in Part 4 will render a nice report from the state."""   
    return state

def node_summarize(state: GateState) -> GateState:
    # Use same model as judge or default
    summary = make_summary_md(state, model="gemini-1.5-flash-002")
    state["summary_md"] = summary
    return state

# ---------- Graph builder ----------

def build_graph() -> StateGraph:
    ## Budiling the state Graph for LangGraph
    g = StateGraph(GateState)
    g.add_node("select_target", node_select_target)
    g.add_node("fetch_signals", node_fetch_signals)
    g.add_node("redline_check", node_redline_check)
    g.add_node("llm_judge", node_llm_judge)
    g.add_node("summarize", node_summarize)
    g.add_node("report", node_report)
    g.add_edge(START, "select_target")
    g.add_edge("select_target", "fetch_signals")
    g.add_edge("fetch_signals", "redline_check")

    g.add_conditional_edges(
        "redline_check",
        redline_router,
        {
             # go summarize directly
            "NO_GO": "summarize",    
            # judge first
            "NEEDS_LLM": "llm_judge", 
        },
    )
    # judge -> summarize
    g.add_edge("llm_judge", "summarize")   
    # summarize -> report
    g.add_edge("summarize", "report")      
    g.add_edge("report", END)

    return g


