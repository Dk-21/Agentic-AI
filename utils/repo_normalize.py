from urllib.parse import urlparse

def normalize_repo(inp: str) -> str:
    """
    Accepts:
      - owner/name
      - https://github.com/owner/name
      - git@github.com:owner/name.git
    Returns: owner/name
    """
    s = inp.strip().rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    if s.startswith("http"):
        path = urlparse(s).path  # /owner/name
        return "/".join([p for p in path.split("/") if p])[0:2] and path.strip("/").split("/", 2)[:2] and "/".join(path.strip("/").split("/", 2)[:2])
    if s.startswith("git@github.com:"):
        return s.replace("git@github.com:", "").strip()
    return s
