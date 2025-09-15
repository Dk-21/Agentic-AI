from utils.repo_normalize import normalize_repo
from gatekeeper.state import default_state
from gatekeeper.graph import build_graph

repo_input = "https://github.com/refinedev/refine"   # <= your URL
repo = normalize_repo(repo_input)                    # -> "refinedev/refine"

STATE = default_state(
    repo=repo,
    base_branch="main",                               # refine uses main
    blocker_labels="release-blocker,P1"               # keep as-is or change
)

graph = build_graph().compile()
final = graph.invoke(STATE)

print("Decision:", final["decision"])
print("Reasons:", final.get("reasons", []))
print("PR:", final.get("pr"))
print("Latest run:", final.get("actions", {}).get("latest_run"))
print("Checks (count):", len(final.get("checks", {}).get("runs", [])))
print("Blockers (count):", len(final.get("blockers", [])))
