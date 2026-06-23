import os
import requests
import json
from datetime import datetime, timedelta, timezone

GH_USER    = os.environ.get("GITHUB_USER", "0000007axl")
LC_USER    = os.environ.get("LEETCODE_USER", "AxelSeth")
GH_TOKEN   = os.environ.get("GITHUB_TOKEN", "")

GH_HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ── GitHub ────────────────────────────────────────────────────────────────────

def fetch_github():
    user = requests.get(f"https://api.github.com/users/{GH_USER}", headers=GH_HEADERS).json()
    repos = requests.get(f"https://api.github.com/users/{GH_USER}/repos?per_page=100", headers=GH_HEADERS).json()
    stars = sum(r.get("stargazers_count", 0) for r in repos) if isinstance(repos, list) else 0

    # Contribution graph via GraphQL (needs token with repo scope)
    gql = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    gql_res = requests.post(
        "https://api.github.com/graphql",
        headers={**GH_HEADERS, "Content-Type": "application/json"},
        json={"query": gql, "variables": {"login": GH_USER}}
    ).json()

    weeks = []
    total_contributions = 0
    try:
        cal = gql_res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        weeks = cal["weeks"]
        total_contributions = cal["totalContributions"]
    except Exception:
        pass

    return {
        "repos":      user.get("public_repos", 0),
        "followers":  user.get("followers", 0),
        "stars":      stars,
        "contribs":   total_contributions,
        "weeks":      weeks,
    }

# ── LeetCode ─────────────────────────────────────────────────────────────────

def fetch_leetcode():
    query = """
    query($username: String!) {
      matchedUser(username: $username) {
        submitStatsGlobal {
          acSubmissionNum { difficulty count }
        }
        tagProblemCounts {
          fundamental  { tagName problemsSolved }
          intermediate { tagName problemsSolved }
          advanced     { tagName problemsSolved }
        }
      }
    }
    """
    try:
        res = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": LC_USER}},
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
            timeout=10
        ).json()

        stats = res["data"]["matchedUser"]["submitStatsGlobal"]["acSubmissionNum"]
        tag_data = res["data"]["matchedUser"]["tagProblemCounts"]

        solved = {s["difficulty"]: s["count"] for s in stats}
        all_tags = (
            tag_data.get("fundamental", []) +
            tag_data.get("intermediate", []) +
            tag_data.get("advanced", [])
        )
        top_tags = sorted(
            [t for t in all_tags if t["problemsSolved"] > 0],
            key=lambda t: -t["problemsSolved"]
        )[:5]

        return {
            "total":  solved.get("All", 0),
            "easy":   solved.get("Easy", 0),
            "medium": solved.get("Medium", 0),
            "hard":   solved.get("Hard", 0),
            "tags":   top_tags,
        }
    except Exception as e:
        print(f"LeetCode fetch failed: {e}")
        return {"total": 0, "easy": 0, "medium": 0, "hard": 0, "tags": []}

# ── Contribution grid ─────────────────────────────────────────────────────────

def build_contrib_cells(weeks):
    """Return list of (col, row, level 0-4) tuples for up to 52 weeks."""
    cells = []
    max_weeks = 52
    start_col = max(0, len(weeks) - max_weeks)
    for wi, week in enumerate(weeks[start_col:]):
        for di, day in enumerate(week["contributionDays"]):
            c = day["contributionCount"]
            if   c == 0: lvl = 0
            elif c <= 2: lvl = 1
            elif c <= 5: lvl = 2
            elif c <= 9: lvl = 3
            else:        lvl = 4
            cells.append((wi, di, lvl))
    return cells

FILL = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

def contrib_svg(weeks, x0, y0):
    """Generate SVG <rect> elements for the contribution graph."""
    cells = build_contrib_cells(weeks)
    parts = []
    cell_size = 11
    gap = 2
    step = cell_size + gap

    # Month labels
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    last_month = None
    for wi, week in enumerate(weeks[max(0, len(weeks)-52):]):
        if week["contributionDays"]:
            date_str = week["contributionDays"][0]["date"]
            month = int(date_str[5:7]) - 1
            if month != last_month:
                last_month = month
                mx = x0 + wi * step
                parts.append(
                    f'<text x="{mx}" y="{y0 - 6}" font-family="Cinzel, serif" '
                    f'font-size="7" fill="#8b949e" letter-spacing="0.5">{MONTHS[month]}</text>'
                )

    # Cells
    for col, row, lvl in cells:
        cx = x0 + col * step
        cy = y0 + row * step
        color = FILL[lvl]
        parts.append(
            f'<rect x="{cx}" y="{cy}" width="{cell_size}" height="{cell_size}" '
            f'rx="2" fill="{color}"/>'
        )
    return "\n".join(parts)

# ── Tag bars ──────────────────────────────────────────────────────────────────

def tag_bars_svg(tags, x0, y0, bar_w=320):
    parts = []
    if not tags:
        return ""
    max_val = tags[0]["problemsSolved"]
    row_h = 22
    for i, tag in enumerate(tags):
        y = y0 + i * row_h
        fill_w = int((tag["problemsSolved"] / max_val) * bar_w) if max_val else 0
        name = tag["tagName"][:18]
        count = tag["problemsSolved"]
        parts.append(
            f'<text x="{x0}" y="{y + 11}" font-family="Cinzel, serif" font-size="8" '
            f'fill="#8b949e" letter-spacing="1">{name.upper()}</text>'
            f'<rect x="{x0 + 100}" y="{y + 3}" width="{bar_w}" height="3" rx="1" fill="#21262d"/>'
            f'<rect x="{x0 + 100}" y="{y + 3}" width="{fill_w}" height="3" rx="1" fill="#8b949e" opacity="0.6"/>'
            f'<text x="{x0 + 100 + bar_w + 8}" y="{y + 11}" font-family="Cinzel, serif" '
            f'font-size="8" fill="#8b949e">{count}</text>'
        )
    return "\n".join(parts)

# ── SVG assembly ──────────────────────────────────────────────────────────────

def build_svg(gh, lc):
    W = 680
    contrib_h = 110   # month label + 7 rows of cells
    tag_rows  = len(lc["tags"])
    H = 680 + tag_rows * 22

    # Divider helper
    def divider(y):
        return (
            f'<line x1="40" y1="{y}" x2="{W-40}" y2="{y}" stroke="#30363d" stroke-width="0.5"/>'
            f'<text x="{W//2}" y="{y + 4}" text-anchor="middle" font-family="serif" '
            f'font-size="10" fill="#8b949e" letter-spacing="4">✦  ✦  ✦</text>'
            f'<line x1="40" y1="{y+8}" x2="{W-40}" y2="{y+8}" stroke="#30363d" stroke-width="0.5"/>'
        )

    def section(label, y):
        return (
            f'<text x="40" y="{y}" font-family="Cinzel, serif" font-size="9" '
            f'fill="#8b949e" letter-spacing="3">{label.upper()}</text>'
            f'<line x1="{40 + len(label)*8 + 16}" y1="{y - 3}" x2="{W - 40}" y2="{y - 3}" '
            f'stroke="#30363d" stroke-width="0.5"/>'
        )

    def stat_card(x, y, w, h, num, label):
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="none" stroke="#30363d" stroke-width="0.5"/>'
            f'<text x="{x + w//2}" y="{y + h//2 - 4}" text-anchor="middle" '
            f'font-family="UnifrakturMaguntia, serif" font-size="22" fill="#e6edf3">{num}</text>'
            f'<text x="{x + w//2}" y="{y + h//2 + 14}" text-anchor="middle" '
            f'font-family="Cinzel, serif" font-size="7" fill="#8b949e" letter-spacing="1.5">{label.upper()}</text>'
        )

    # Crows
    crow1 = (
        '<path d="M310 52 C314 46 320 45 323 47 C324 45 327 44 330 45 '
        'C333 43 336 44 335 47 C333 48 331 47 330 48 C328 50 325 52 321 51 '
        'C319 52 316 52 310 52Z" fill="#c9d1d9" opacity="0.65"/>'
        '<path d="M309 51 C308 50 309 49 311 50" stroke="#c9d1d9" stroke-width="0.8" opacity="0.5"/>'
    )
    crow2 = (
        '<path d="M350 50 C354 45 359 44 362 46 C363 44 365 43 368 44 '
        'C370 42 373 43 372 46 C370 47 368 46 367 47 C365 49 362 51 359 50 '
        'C357 51 354 51 350 50Z" fill="#c9d1d9" opacity="0.5"/>'
    )

    # Corner brackets
    corners = (
        '<polyline points="20,20 20,34" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        '<polyline points="20,20 34,20" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        f'<polyline points="{W-20},20 {W-20},34" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        f'<polyline points="{W-20},20 {W-34},20" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        f'<polyline points="20,{H-20} 20,{H-34}" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        f'<polyline points="20,{H-20} 34,{H-20}" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        f'<polyline points="{W-20},{H-20} {W-20},{H-34}" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
        f'<polyline points="{W-20},{H-20} {W-34},{H-20}" stroke="#c9d1d9" stroke-width="1.5" opacity="0.5" fill="none"/>'
    )

    # Shields
    shields = ["LINUX", "NEOVIM", "C", "PYTHON", "GIT", "ÉCOLE 42"]
    shield_svg = []
    sx = 78
    for s in shields:
        sw = len(s) * 7 + 24
        shield_svg.append(
            f'<rect x="{sx}" y="178" width="{sw}" height="20" rx="2" fill="none" stroke="#30363d" stroke-width="0.5"/>'
            f'<text x="{sx + 8}" y="192" font-family="Cinzel, serif" font-size="7.5" fill="#8b949e" letter-spacing="1.5">⚔ {s}</text>'
        )
        sx += sw + 10

    # GitHub stat cards (4 across)
    card_w = 130
    card_h = 52
    card_y = 280
    card_gap = 12
    card_x0 = 40
    gh_cards = (
        stat_card(card_x0,                    card_y, card_w, card_h, gh["repos"],     "Repos")    +
        stat_card(card_x0 + (card_w+card_gap),  card_y, card_w, card_h, gh["followers"], "Followers") +
        stat_card(card_x0 + (card_w+card_gap)*2, card_y, card_w, card_h, gh["stars"],    "Stars")    +
        stat_card(card_x0 + (card_w+card_gap)*3, card_y, card_w, card_h, gh["contribs"], "Contributions")
    )

    # Contribution graph
    contrib_y0 = 380
    contrib_cells = contrib_svg(gh["weeks"], 40, contrib_y0 + 14)

    # LeetCode cards (3 across)
    lc_card_w = 180
    lc_card_h = 52
    lc_card_y = 510
    lc_card_gap = 15
    lc_card_x0 = 40
    lc_cards = (
        stat_card(lc_card_x0,                       lc_card_y, lc_card_w, lc_card_h, lc["total"],  "Solved") +
        stat_card(lc_card_x0 + lc_card_w+lc_card_gap, lc_card_y, lc_card_w, lc_card_h, lc["easy"],   "Easy")   +
        stat_card(lc_card_x0 + (lc_card_w+lc_card_gap)*2, lc_card_y, lc_card_w, lc_card_h, lc["medium"], "Medium")
    )

    tag_y0 = 580
    tags_svg = tag_bars_svg(lc["tags"], 40, tag_y0)

    quest_y = tag_y0 + tag_rows * 22 + 30
    quests = (
        f'<text x="52" y="{quest_y + 16}" font-family="IM Fell English, serif" font-size="13" fill="#c9d1d9">🛠  I\'m working on: —</text>'
        f'<text x="52" y="{quest_y + 38}" font-family="IM Fell English, serif" font-size="13" fill="#c9d1d9">🌱  I\'m learning: Algorithms, Data Structures, System and Network Administration</text>'
    )

    footer_y = H - 28
    footer = (
        f'<text x="{W//2}" y="{footer_y}" text-anchor="middle" font-family="UnifrakturMaguntia, serif" '
        f'font-size="13" fill="#8b949e" opacity="0.55" letter-spacing="2">~ I use NeoVim btw ~</text>'
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&amp;family=IM+Fell+English:ital@0;1&amp;family=Cinzel:wght@400;700&amp;display=swap');
    </style>
  </defs>

  <!-- Background -->
  <rect width="{W}" height="{H}" fill="#0d1117"/>

  <!-- Outer border -->
  <rect x="16" y="16" width="{W-32}" height="{H-32}" fill="none" stroke="#30363d" stroke-width="1"/>

  <!-- Corner brackets -->
  {corners}

  <!-- Crows -->
  {crow1}
  {crow2}

  <!-- Title -->
  <text x="{W//2}" y="100" text-anchor="middle" font-family="UnifrakturMaguntia, serif" font-size="52" fill="#e6edf3" letter-spacing="2">Axel</text>
  <text x="{W//2}" y="126" text-anchor="middle" font-family="IM Fell English, serif" font-style="italic" font-size="14" fill="#8b949e" letter-spacing="2">[æk.səl]</text>
  <text x="{W//2}" y="146" text-anchor="middle" font-family="IM Fell English, serif" font-style="italic" font-size="12" fill="#8b949e" opacity="0.75">he/him · Junior C &amp; Python Dev</text>

  <!-- Shields -->
  {"".join(shield_svg)}

  <!-- Divider 1 -->
  {divider(212)}

  <!-- About -->
  {section("About", 244)}
  <text x="40" y="264" font-family="IM Fell English, serif" font-size="13" fill="#c9d1d9">Student at <tspan font-weight="bold" fill="#e6edf3">École 42</tspan> — learning through projects, ego, and pain.</text>
  <text x="40" y="282" font-family="IM Fell English, serif" font-size="13" fill="#c9d1d9">Building things in C from scratch. Occasionally writing Python when I want to feel productive.</text>
  <text x="40" y="300" font-family="IM Fell English, serif" font-size="13" fill="#c9d1d9">Algorithms enthusiast. Linux native. Living in the terminal. I use NeoVim btw.</text>

  <!-- GitHub -->
  {section("GitHub", 340)}
  {gh_cards}

  <!-- Contributions -->
  {section("Contributions", 374)}
  {contrib_cells}

  <!-- LeetCode -->
  {section("LeetCode", 500)}
  {lc_cards}

  <!-- Tags -->
  {tags_svg}

  <!-- Quests -->
  {section("Quests", quest_y)}
  {quests}

  <!-- Divider 2 -->
  {divider(H - 56)}

  <!-- Footer -->
  {footer}
</svg>"""

    return svg

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching GitHub stats...")
    gh = fetch_github()
    print(f"  repos={gh['repos']} followers={gh['followers']} stars={gh['stars']} contribs={gh['contribs']}")

    print("Fetching LeetCode stats...")
    lc = fetch_leetcode()
    print(f"  total={lc['total']} easy={lc['easy']} medium={lc['medium']} tags={[t['tagName'] for t in lc['tags']]}")

    svg = build_svg(gh, lc)
    with open("stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("stats.svg written.")
