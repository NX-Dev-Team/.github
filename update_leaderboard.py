import os
import re
import requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

GH_TOKEN     = os.environ.get("GH_TOKEN", "")
ORG_NAME     = "NX-Dev-Team"        # ← ganti nama org GitHub kamu
README_PATH  = "profile/README.md"

MEMBERS = [
    {"login": "muhamadsyafii", "role": "Android Engineer"},
    {"login": "kharozim",      "role": "Android Engineer"},
    {"login": "bowoBp",        "role": "BackEnd Engineer"},
    {"login": "totop275",      "role": "Full Stack Engineer"},
    {"login": "alimurtadho",   "role": "Infra & Data Team"},
]

MEDALS = ["🥇", "🥈", "🥉", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅"]

# PR size tier thresholds (lines changed per PR)
PR_SMALL_MAX  = 100   # < 100 lines  → 1 poin
PR_MEDIUM_MAX = 500   # 100–500 lines → 3 poin
                      # > 500 lines  → 6 poin

WEIGHT = {
    "pr_small":      1,
    "pr_medium":     3,
    "pr_large":      6,
    "reviews_given": 2,
    "issues_closed": 3,
}

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── GitHub helpers ────────────────────────────────────────────────────────────

def gh_get(url: str, params: dict = None) -> dict | list:
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def search_count(query: str) -> int:
    try:
        data = gh_get(
            "https://api.github.com/search/issues",
            params={"q": query, "per_page": 1},
        )
        return data.get("total_count", 0)
    except Exception as e:
        print(f"  [WARN] search '{query}': {e}")
        return 0


def get_reviews_given(login: str) -> int:
    return search_count(f"org:{ORG_NAME} type:pr reviewed-by:{login} -author:{login}")


def get_issues_closed(login: str) -> int:
    return search_count(f"org:{ORG_NAME} type:issue is:closed author:{login}")


def get_org_repos() -> list[str]:
    repos = []
    page  = 1
    while True:
        data = gh_get(
            f"https://api.github.com/orgs/{ORG_NAME}/repos",
            params={"per_page": 100, "page": page, "type": "all"},
        )
        if not data:
            break
        repos.extend(r["name"] for r in data)
        if len(data) < 100:
            break
        page += 1
    return repos


def get_pr_tiers(login: str, repos: list[str]) -> dict:
    """
    Iterasi semua merged PR per repo, klasifikasikan ke tier
    berdasarkan total lines changed (additions + deletions).
    """
    small = medium = large = 0
    total_lines = 0

    for repo in repos:
        page = 1
        while True:
            try:
                prs = gh_get(
                    f"https://api.github.com/repos/{ORG_NAME}/{repo}/pulls",
                    params={"state": "closed", "per_page": 100, "page": page},
                )
            except Exception as e:
                print(f"  [WARN] pulls {repo} p{page}: {e}")
                break

            if not prs:
                break

            for pr in prs:
                if pr.get("merged_at") and pr.get("user", {}).get("login") == login:
                    lines = pr.get("additions", 0) + pr.get("deletions", 0)
                    total_lines += lines
                    if lines < PR_SMALL_MAX:
                        small += 1
                    elif lines <= PR_MEDIUM_MAX:
                        medium += 1
                    else:
                        large += 1

            if len(prs) < 100:
                break
            page += 1

    return {
        "pr_small":    small,
        "pr_medium":   medium,
        "pr_large":    large,
        "total_prs":   small + medium + large,
        "total_lines": total_lines,
    }


# ── Fetch all stats ───────────────────────────────────────────────────────────

def fetch_stats() -> list[dict]:
    print(f"Fetching repos for org: {ORG_NAME} …")
    repos = get_org_repos()
    print(f"  Found {len(repos)} repos: {repos}")

    stats = []
    for m in MEMBERS:
        login = m["login"]
        print(f"\nFetching stats for @{login} …")

        tiers         = get_pr_tiers(login, repos)
        reviews_given = get_reviews_given(login)
        issues_closed = get_issues_closed(login)

        score = round(
            tiers["pr_small"]  * WEIGHT["pr_small"]      +
            tiers["pr_medium"] * WEIGHT["pr_medium"]      +
            tiers["pr_large"]  * WEIGHT["pr_large"]       +
            reviews_given      * WEIGHT["reviews_given"]  +
            issues_closed      * WEIGHT["issues_closed"]
        )

        print(
            f"  pr_small={tiers['pr_small']}  pr_medium={tiers['pr_medium']}"
            f"  pr_large={tiers['pr_large']}  reviews={reviews_given}"
            f"  issues={issues_closed}  lines={tiers['total_lines']:,}  score={score}"
        )

        stats.append({
            **m,
            **tiers,
            "reviews_given": reviews_given,
            "issues_closed": issues_closed,
            "score":         score,
        })

    stats.sort(key=lambda x: (-x["score"], -x["total_prs"]))
    return stats


# ── Build markdown table ──────────────────────────────────────────────────────

def build_table(stats: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "<!-- LEADERBOARD-START -->",
        "",
        f"_Last updated: {now}_",
        "",
        "| Rank | Developer | Role | 🟢 PR Kecil | 🟡 PR Sedang | 🔴 PR Besar | 👀 Reviews | 🎯 Issues | ⭐ Score |",
        "| :--: | :-------- | :--- | :---------: | :----------: | :---------: | :--------: | :-------: | :------: |",
    ]
    for i, s in enumerate(stats):
        medal  = MEDALS[i] if i < len(MEDALS) else "🏅"
        handle = f"[@{s['login']}](https://github.com/{s['login']})"
        lines.append(
            f"| {medal} | {handle} | {s['role']}"
            f" | {s['pr_small']} | {s['pr_medium']} | {s['pr_large']}"
            f" | {s['reviews_given']} | {s['issues_closed']}"
            f" | **{s['score']}** |"
        )
    lines += [
        "",
        "> **Scoring:** 🟢 PR Kecil (<100 lines) ×1 &nbsp;·&nbsp; 🟡 PR Sedang (100–500 lines) ×3 &nbsp;·&nbsp; 🔴 PR Besar (>500 lines) ×6 &nbsp;·&nbsp; 👀 Review ×2 &nbsp;·&nbsp; 🎯 Issue Closed ×3",
        "",
        "<!-- LEADERBOARD-END -->",
    ]
    return "\n".join(lines)


# ── Update README ─────────────────────────────────────────────────────────────

def update_readme(table: str) -> bool:
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!-- LEADERBOARD-START -->.*?<!-- LEADERBOARD-END -->"
    new_content, n = re.subn(pattern, table, content, flags=re.DOTALL)

    if n == 0:
        print("[ERROR] Sentinel comments not found in README.")
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

    stats   = fetch_stats()
    table   = build_table(stats)
    changed = update_readme(table)

    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as fh:
        fh.write(f"changed={'true' if changed else 'false'}\n")