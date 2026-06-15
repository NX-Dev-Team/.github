import os
import re
import requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

GH_TOKEN = os.environ.get("GH_TOKEN", "")
ORG_NAME = "NX-Dev-Team"          # ← ganti dengan nama org / user GitHub kamu
README_PATH = "profile/README.md"

MEMBERS = [
    {"login": "muhamadsyafii", "role": "Android Engineer"},
    {"login": "kharozim",      "role": "Android Engineer"},
    {"login": "bowoBp",        "role": "BackEnd Engineer"},
    {"login": "totop275",      "role": "Full Stack Engineer"},
    {"login": "alimurtadho",   "role": "Infra & Data Team"},
]

MEDALS = ["🥇", "🥈", "🥉", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅"]

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def gh_get(url: str, params: dict = None) -> dict | list:
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def get_commit_count(login: str) -> int:
    """
    Count commits across ALL repos in the org authored by `login`.
    Uses the Search API (max 1 000 results per query, but good enough for a leaderboard).
    """
    url = "https://api.github.com/search/commits"
    params = {
        "q": f"org:{ORG_NAME} author:{login}",
        "per_page": 1,
    }
    try:
        data = gh_get(url, params)
        return data.get("total_count", 0)
    except Exception as e:
        print(f"  [WARN] commit count for {login}: {e}")
        return 0


def get_pr_count(login: str) -> int:
    """
    Count merged PRs in the org authored by `login`.
    """
    url = "https://api.github.com/search/issues"
    params = {
        "q": f"org:{ORG_NAME} type:pr is:merged author:{login}",
        "per_page": 1,
    }
    try:
        data = gh_get(url, params)
        return data.get("total_count", 0)
    except Exception as e:
        print(f"  [WARN] PR count for {login}: {e}")
        return 0


# ── Core ──────────────────────────────────────────────────────────────────────

def fetch_stats() -> list[dict]:
    stats = []
    for m in MEMBERS:
        login = m["login"]
        print(f"Fetching stats for @{login} …")
        commits = get_commit_count(login)
        prs     = get_pr_count(login)
        stats.append({**m, "commits": commits, "prs": prs})
        print(f"  commits={commits}  prs={prs}")

    # Sort by commits desc, then PRs desc
    stats.sort(key=lambda x: (-x["commits"], -x["prs"]))
    return stats


def build_table(stats: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"<!-- LEADERBOARD-START -->",
        f"",
        f"_Last updated: {now}_",
        f"",
        f"| Rank | Developer | Role | Commits | PRs |",
        f"| :--: | :-------- | :--- | :-----: | :-: |",
    ]
    for i, s in enumerate(stats):
        medal  = MEDALS[i] if i < len(MEDALS) else "🏅"
        handle = f"[@{s['login']}](https://github.com/{s['login']})"
        lines.append(
            f"| {medal} | {handle} | {s['role']} | {s['commits']} | {s['prs']} |"
        )
    lines.append("")
    lines.append("<!-- LEADERBOARD-END -->")
    return "\n".join(lines)


def update_readme(table: str) -> bool:
    """Replace the block between the sentinel comments. Returns True if changed."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!-- LEADERBOARD-START -->.*?<!-- LEADERBOARD-END -->"
    new_content, n = re.subn(pattern, table, content, flags=re.DOTALL)

    if n == 0:
        print("[ERROR] Sentinel comments not found in README. Nothing updated.")
        return False

    if new_content == content:
        print("[INFO] Leaderboard unchanged — skipping write.")
        return False

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[OK] {README_PATH} updated.")
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not GH_TOKEN:
        raise SystemExit("[ERROR] GH_TOKEN env var is not set.")

    stats  = fetch_stats()
    table  = build_table(stats)
    changed = update_readme(table)

    # Signal to the workflow whether there is actually something to commit
    # (write a tiny env file that the YAML step can read)
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as fh:
        fh.write(f"changed={'true' if changed else 'false'}\n")