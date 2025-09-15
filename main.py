# main.py
import argparse
import json
import os
import sys
import time
from typing import Any, Dict
import shutil
from dotenv import load_dotenv

from utils.repo_normalize import normalize_repo
from gatekeeper.state import default_state
from gatekeeper.graph import build_graph


# ---------- rendering ----------

def render_pretty(state: Dict[str, Any]) -> str:
    lines = []
    lines.append("=== Release Gatekeeper ===")
    lines.append(f"Repo: {state['repo']}")
    lines.append(f"Decision: {state.get('decision')}")
    conf = state.get("confidence")
    if conf is not None:
        lines.append(f"Confidence: {conf}")
    lines.append("Reasons:")
    for r in state.get("reasons", []):
        lines.append(f" - {r}")
    ev = state.get("evidence", [])
    if ev:
        lines.append("Evidence:")
        for e in ev:
            lines.append(f" - {e}")
    pv = state.get("policy_violations", [])
    if pv:
        lines.append("Policy violations:")
        for p in pv:
            lines.append(f" - {p}")
    pr = state.get("pr")
    if pr:
        lines.append(f"PR: {pr}")
    lr = state.get("actions", {}).get("latest_run")
    if lr:
        lines.append(f"Latest run: {lr}")
    lines.append(f"Checks (count): {len(state.get('checks', {}).get('runs', []))}")
    lines.append(f"Blockers (count): {len(state.get('blockers', []))}")
    if state.get("summary_md"):
        lines.append("\n---\nDeveloper Digest:\n")
        lines.append(state["summary_md"])
    return "\n".join(lines)


def render_md(state: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Release Gatekeeper\n")
    lines.append(f"- **Repo:** `{state['repo']}`")
    lines.append(f"- **Decision:** **{state.get('decision')}**")
    if state.get("confidence") is not None:
        lines.append(f"- **Confidence:** {state['confidence']}")
    lines.append("\n## Reasons")
    for r in state.get("reasons", []):
        lines.append(f"- {r}")
    ev = state.get("evidence", [])
    if ev:
        lines.append("\n## Evidence")
        for e in ev:
            lines.append(f"- `{e}`")
    pv = state.get("policy_violations", [])
    if pv:
        lines.append("\n## Policy violations")
        for p in pv:
            lines.append(f"- {p}")
    pr = state.get("pr")
    if pr:
        lines.append("\n## PR")
        lines.append(f"- `{pr}`")
    lr = state.get("actions", {}).get("latest_run")
    if lr:
        lines.append("\n## Latest run")
        lines.append(f"- `{lr}`")
    lines.append("\n## Counts")
    lines.append(f"- Checks: {len(state.get('checks', {}).get('runs', []))}")
    lines.append(f"- Blockers: {len(state.get('blockers', []))}")
    if state.get("summary_md"):
        lines.append("\n## Developer Digest\n")
        lines.append(state["summary_md"])
    return "\n".join(lines)


# ---------- exit code mapping ----------
def decision_exit_code(decision: str) -> int:
    if decision == "GO":
        return 0
    if decision == "PAUSE":
        return 1
    if decision == "NO_GO":
        return 2
    # unknown
    return 3  
DEFAULT_CLEAN_SKIP = {
    ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", "dist", "build"
}

def clean_caches(root: str = ".", skip: set[str] = DEFAULT_CLEAN_SKIP, verbose: bool = False) -> int:
    """Delete __pycache__ dirs and .pyc/.pyo files recursively, skipping heavy folders."""
    deleted = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # prune walk for speed
        dirnames[:] = [d for d in dirnames if d not in skip]

        # __pycache__ dirs
        if "__pycache__" in dirnames:
            cache_dir = os.path.join(dirpath, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                deleted += 1
                if verbose: print(f"Deleted dir: {cache_dir}")
            except Exception as e:
                if verbose: print(f"Failed dir: {cache_dir} ({e})")

        # .pyc / .pyo files
        for fname in filenames:
            if fname.endswith((".pyc", ".pyo")):
                fpath = os.path.join(dirpath, fname)
                try:
                    os.remove(fpath)
                    deleted += 1
                    if verbose: print(f"Deleted file: {fpath}")
                except Exception as e:
                    if verbose: print(f"Failed file: {fpath} ({e})")
    if verbose:
        print(f"\n Cache cleanup complete. {deleted} items deleted.")
    return deleted


def main():
    load_dotenv()  # GEMINI_API_KEY, GITHUB_TOKEN, etc.
    ap = argparse.ArgumentParser(description="Release Gatekeeper (LangGraph + Gemini)")
    ap.add_argument("--repo", required=True, help="GitHub repo as URL or owner/name")
    ap.add_argument("--base-branch", default="main", help="Target branch (default: main)")
    ap.add_argument(
        "--blocker-labels", default="release-blocker,P1",
        help="Comma-separated labels treated as release blockers"
    )
    ap.add_argument(
        "--format", choices=["pretty", "md", "json"], default="pretty",
        help="Output format"
    )
    ap.add_argument(
        "--model", default="gemini-1.5-flash-002",
        help="Gemini model for judge (e.g., gemini-1.5-pro-002)"
    )
    args = ap.parse_args()

    repo = normalize_repo(args.repo)

    # build graph & run
    state = default_state(repo=repo, base_branch=args.base_branch, blocker_labels=args.blocker_labels)
    graph = build_graph().compile()

    t0 = time.time()
    ## Runable Program
    final = graph.invoke(state, config={"configurable": {"model": args.model}})
    dt = time.time() - t0

    # render
    if args.format == "pretty":
        out = render_pretty(final)
    elif args.format == "md":
        out = render_md(final)
    else:
        # minimal stable JSON subset
        subset = {
            "repo": final.get("repo"),
            "decision": final.get("decision"),
            "confidence": final.get("confidence"),
            "reasons": final.get("reasons", []),
            "evidence": final.get("evidence", []),
            "policy_violations": final.get("policy_violations", []),
            "pr": final.get("pr"),
            "latest_run": final.get("actions", {}).get("latest_run"),
            "checks_count": len(final.get("checks", {}).get("runs", [])),
            "blockers_count": len(final.get("blockers", [])),
            "elapsed_sec": round(dt, 2),
        }
        out = json.dumps(subset, ensure_ascii=False, indent=2)

    print(out)
    print(f"\n(Elapsed: {dt:.2f}s)")

    # --- Auto cleanup of the cache Files (no CLI flags) ---
    # Set GATEKEEPER_SKIP_AUTOCLEAN=1 to skip if needed
    if os.getenv("GATEKEEPER_SKIP_AUTOCLEAN", "0") != "1":
        try:
            clean_caches(".", verbose=False)
        except Exception as e:
            print(f"[gatekeeper] autoclean skipped due to error: {e}")
    sys.exit(decision_exit_code(final.get("decision", "UNKNOWN")))



if __name__ == "__main__":
    main()
