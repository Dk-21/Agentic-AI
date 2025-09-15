# tools/github_tools.py
import os, requests
from dotenv import load_dotenv
load_dotenv()

GH = "https://api.github.com"
BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if os.getenv("GITHUB_TOKEN"):
    BASE_HEADERS["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"

def _req(method, url, *, params=None):
    # First try with whatever headers we have
    r = requests.request(method, url, params=params, headers=BASE_HEADERS, timeout=30)
    if r.status_code == 401 and "Authorization" in BASE_HEADERS:
        # Retry once without Authorization header
        hdrs = {k: v for k, v in BASE_HEADERS.items() if k != "Authorization"}
        r2 = requests.request(method, url, params=params, headers=hdrs, timeout=30)
        r2.raise_for_status()
        return r2
    r.raise_for_status()
    return r

def get_open_pr(repo: str, base: str = "main", want_label: str | None = None):
    r = _req("GET", f"{GH}/repos/{repo}/pulls",
             params={"state": "open", "base": base, "sort": "updated", "direction": "desc"})
    for pr in r.json():
        labels = [l["name"] for l in pr.get("labels", [])]
        if (want_label is None) or (want_label in labels):
            return {"number": pr["number"], "head_sha": pr["head"]["sha"],
                    "base": pr["base"]["ref"], "url": pr["html_url"], "labels": labels}
    return None

def get_latest_run_for_sha(repo: str, sha: str):
    r = _req("GET", f"{GH}/repos/{repo}/actions/runs", params={"head_sha": sha, "per_page": 1})
    items = r.json().get("workflow_runs", [])
    if not items: return None
    wr = items[0]
    return {"status": wr["status"], "conclusion": wr["conclusion"], "url": wr["html_url"]}

def get_check_runs(repo: str, ref: str):
    r = _req("GET", f"{GH}/repos/{repo}/commits/{ref}/check-runs")
    return [{"name": cr["name"], "conclusion": cr["conclusion"], "url": cr["html_url"]}
            for cr in r.json().get("check_runs", [])]

def get_blockers(repo: str, labels_csv: str = "release-blocker,P1"):
    r = _req("GET", f"{GH}/repos/{repo}/issues", params={"state": "open", "labels": labels_csv})
    return [{"title": it["title"], "labels": [l["name"] for l in it["labels"]], "url": it["html_url"]}
            for it in r.json()]

def get_branch_head_sha(repo: str, branch: str = "main"):
    r = _req("GET", f"{GH}/repos/{repo}/branches/{branch}")
    data = r.json()
    return {"sha": data["commit"]["sha"], "url": data["commit"]["html_url"]}

def get_default_branch(repo: str) -> str:
    r = _req("GET", f"{GH}/repos/{repo}")
    return r.json().get("default_branch", "main")

