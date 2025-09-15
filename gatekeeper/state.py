from typing import Any, Dict, List, Literal, Optional, TypedDict

Decision = Literal["UNKNOWN", "GO", "NO_GO", "PAUSE"]

class PR(TypedDict, total=False):
    number: int
    head_sha: str
    base: str
    url: str
    labels: List[str]

class ActionsInfo(TypedDict, total=False):
    latest_run: Dict[str, Any]  # {status, conclusion, url}

class ChecksInfo(TypedDict, total=False):
    required: List[str]         # empty for OSS; may be filled if you own the repo
    runs: List[Dict[str, Any]]  # [{name, conclusion, url}]

class Issue(TypedDict, total=False):
    title: str
    labels: List[str]
    url: str

class GateState(TypedDict, total=False):
    # Inputs / config
    repo: str
    base_branch: str
    # e.g., "release-blocker,P1"
    blocker_labels: str  

    # Selected target
    pr: Optional[PR]
    head_sha: Optional[str]

    # Signals
    actions: ActionsInfo
    checks: ChecksInfo
    blockers: List[Issue]

    # Decision artifacts
    decision: Decision
    reasons: List[str]
    evidence: List[Dict[str, Any]]
    policy_violations: List[str]
    confidence: float

    # Flow control
    awaiting_llm: bool
    # Summary State - Human-readable summary for developers
    summary_md: str  


def default_state(repo: str, base_branch: str = "main", blocker_labels: str = "release-blocker,P1") -> GateState:
    return GateState(
        repo=repo,
        base_branch=base_branch,
        blocker_labels=blocker_labels,
        pr=None,
        head_sha=None,
        actions=ActionsInfo(),
        checks=ChecksInfo(required=[], runs=[]),
        blockers=[],
        decision="UNKNOWN",
        reasons=[],
        evidence=[],
        policy_violations=[],
        confidence=0.0,
        awaiting_llm=False,
        summary_md=""
    )
