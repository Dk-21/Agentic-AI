import os
from utils.repo_normalize import normalize_repo
from gatekeeper.state import default_state
from gatekeeper.graph import build_graph

# Choose your OSS repo (URL or owner/name)
repo_input = "https://github.com/refinedev/refine"  # your choice
repo = normalize_repo(repo_input)

STATE = default_state(repo=repo, base_branch="main")

graph = build_graph().compile()
final = graph.invoke(STATE)

print("\n=== Release Gatekeeper ===")
print("Repo:", repo)
print("Decision:", final["decision"])
print("Confidence:", final.get("confidence"))
print("Reasons:")
for r in final.get("reasons", []):
    print(" -", r)
print("Evidence:")
for e in final.get("evidence", []):
    print(" -", e)
print("Policy violations:", final.get("policy_violations", []))
print("PR:", final.get("pr"))
print("Latest run:", final.get("actions", {}).get("latest_run"))
print("Checks (count):", len(final.get("checks", {}).get("runs", [])))
print("Blockers (count):", len(final.get("blockers", [])))
