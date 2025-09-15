# gatekeeper/verifier.py
from typing import Any, Dict, List, Tuple
import re

def _get_by_path(obj: Any, path: str) -> Any:
    """
    Dot-path lookup into nested dict/list structures.
    Examples:
      path="actions.latest_run.conclusion"
      path="checks.runs.0.conclusion"
      path="blockers"  # returns list
    """
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                idx = int(part)
            except ValueError:
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur

def _normalize_path(raw_path: str | None, source: str | None) -> str | None:
    """
    Make model-provided paths match our signals structure:
      - Convert bracket indexing to dot indexing: runs[0].conclusion -> runs.0.conclusion
      - Prefix with top-level section based on 'source' if missing:
          actions.latest_run.conclusion
          checks.runs.0.conclusion
          blockers   (for empty/non-indexed blockers)
    """
    if raw_path is None:
        # Allow empty path for blockers (meaning "the blockers list")
        return "blockers" if source == "blockers" else None

    path = raw_path.strip()
    if source == "blockers" and path in {"", "[]", "blockers[]"}:
        return "blockers"

    # runs[0] -> runs.0, checks.runs[1] -> checks.runs.1
    path = re.sub(r"\[(\d+)\]", r".\1", path)

    # If the model omitted the top-level prefix, add it from 'source'
    if source in {"actions", "checks", "blockers", "target"}:
        if not (path == source or path.startswith(source + ".")):
            # Special-case blockers: keep just "blockers" if they tried to use indexes oddly
            if source == "blockers" and not path.startswith("blockers"):
                path = "blockers"
            else:
                path = f"{source}.{path}"

    return path

def verify_evidence(judge: Dict[str, Any], signals: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Ensure every evidence item maps to an actual value in signals and matches."""
    violations: List[str] = []
    ev: List[Dict[str, Any]] = judge.get("evidence", [])

    for i, item in enumerate(ev):
        src = item.get("source")
        raw_path = item.get("path")
        npath = _normalize_path(raw_path, src)
        if npath is None:
            violations.append(f"evidence[{i}]: missing/invalid path")
            continue

        actual = _get_by_path(signals, npath)
        if actual is None:
            violations.append(f"evidence[{i}]: path '{raw_path}' -> '{npath}' not found")
            continue

        claimed = item.get("value", None)
        # Loose equality across JSON types
        if str(actual) != str(claimed):
            violations.append(
                f"evidence[{i}]: value mismatch at '{npath}': actual={actual!r} claimed={claimed!r}"
            )

    ok = len(violations) == 0
    return ok, violations
