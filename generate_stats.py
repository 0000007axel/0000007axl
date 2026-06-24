import os, requests, datetime, random

GH_USER  = os.environ.get("GITHUB_USER",   "0000007axl")
LC_USER  = os.environ.get("LEETCODE_USER", "AxelSeth")
GH_TOKEN = os.environ.get("GITHUB_TOKEN",  "")
GH_HEADERS = {"Accept": "application/vnd.github+json"}
if GH_TOKEN:
    GH_HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_github():
    try:
        user  = requests.get(f"https://api.github.com/users/{GH_USER}", headers=GH_HEADERS, timeout=10).json()
        repos = requests.get(f"https://api.github.com/users/{GH_USER}/repos?per_page=100", headers=GH_HEADERS, timeout=10).json()
    except:
        user, repos = {}, []
    stars = sum(r.get("stargazers_count",0) for r in repos) if isinstance(repos,list) else 0
    weeks, total = [], 0
    if GH_TOKEN:
        gql = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
          totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
        try:
            gql_res = requests.post("https://api.github.com/graphql",
                headers={**GH_HEADERS,"Content-Type":"application/json"},
                json={"query":gql,"variables":{"login":GH_USER}}, timeout=10).json()
            cal = gql_res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            weeks = cal["weeks"]; total = cal["totalContributions"]
        except: pass
    if not weeks:
        try:
            cal = requests.get(f"https://github-contributions-api.jogruber.de/v4/{GH_USER}?y=2026", timeout=10).json()
            contribs = cal.get("contributions", [])
            total = sum(d.get("count",0) for d in contribs)
            from collections import OrderedDict
            groups = OrderedDict()
            for d in contribs:
                dt = datetime.datetime.strptime(d["date"], "%Y-%m-%d").date()
                monday = dt - datetime.timedelta(days=dt.weekday())
                groups.setdefault(monday, []).append(d)
            weeks = []
            for monday in sorted(groups):
                days = sorted(groups[monday], key=lambda x: x["date"])
                weeks.append({"contributionDays": [{"date": d["date"], "contributionCount": d["count"]} for d in days]})
        except: pass
    return {"repos":user.get("public_repos",0),"followers":user.get("followers",0),
            "stars":stars,"contribs":total,"weeks":weeks}

def fetch_leetcode():
    q = """query($u:String!){matchedUser(username:$u){
      submitStatsGlobal{acSubmissionNum{difficulty count}}
      tagProblemCounts{fundamental{tagName problemsSolved}
        intermediate{tagName problemsSolved}advanced{tagName problemsSolved}}}}"""
    try:
        res = requests.post("https://leetcode.com/graphql",
            json={"query":q,"variables":{"u":LC_USER}},
            headers={"Content-Type":"application/json","Referer":"https://leetcode.com"},
            timeout=10).json()
        stats    = res["data"]["matchedUser"]["submitStatsGlobal"]["acSubmissionNum"]
        tag_data = res["data"]["matchedUser"]["tagProblemCounts"]
        solved   = {s["difficulty"]:s["count"] for s in stats}
        all_tags = (tag_data.get("fundamental",[])+tag_data.get("intermediate",[])+tag_data.get("advanced",[]))
        top_tags = sorted([t for t in all_tags if t["problemsSolved"]>0],key=lambda t:-t["problemsSolved"])[:5]
        return {"total":solved.get("All",0),"easy":solved.get("Easy",0),"medium":solved.get("Medium",0),"hard":solved.get("Hard",0),"tags":top_tags}
    except Exception as e:
        print(f"LeetCode failed: {e}")
        return {"total":0,"easy":0,"medium":0,"hard":0,"tags":[]}

# ── SVG helpers ───────────────────────────────────────────────────────────────

FONTS = "@import url('https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&amp;family=IM+Fell+English:ital@0;1&amp;family=Cinzel:wght@400;700&amp;display=swap');"

# ── Cal-Heatmap inspired options ──────────────────────────────────────────────

CAL = {
    "scale": {
        "type": "quantize",
        "range": ["#21262d","#0e4429","#006d32","#26a641","#39d353"],
        "domain": [0, 1, 3, 6, 10],
    },
    "subDomain": {
        "width": 11,
        "height": 11,
        "gutter": 2,
        "radius": 2,
    },
    "domain": {
        "label": {"font": "Cinzel,serif", "size": 7, "color": "#8b949e"},
    },
    "theme": "dark",
}

THEMES = {
    "dark":  {"bg": "#0d1117", "muted": "#8b949e", "border": "#30363d"},
    "light": {"bg": "#ffffff", "muted": "#656d76", "border": "#d0d7de"},
}

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(rgb):
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def lerp_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex((int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t)))

def scale_color(value, cfg):
    st = cfg["type"]
    dom = cfg["domain"]
    rng = cfg["range"]
    if st == "quantize":
        for i in range(len(dom) - 1, 0, -1):
            if value >= dom[i]:
                return rng[i] if i < len(rng) else rng[-1]
        return rng[0]
    elif st == "ordinal":
        return rng[value % len(rng)]
    elif st == "threshold":
        for i, t in enumerate(dom):
            if value <= t:
                return rng[i] if i < len(rng) else rng[-1]
        return rng[-1]
    else:
        dmin, dmax = dom[0], dom[-1]
        if dmax == dmin:
            return rng[-1]
        t = max(0, min(1, (value - dmin) / (dmax - dmin)))
        seg = len(rng) - 1
        idx = t * seg
        lo = int(idx)
        hi = min(lo + 1, len(rng) - 1)
        return lerp_color(rng[lo], rng[hi], idx - lo)

def stat_card(x, y, w, h, num, label):
    cx = x + w//2
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="none" stroke="#30363d" stroke-width="0.8"/>'
        f'<text x="{cx}" y="{y+h//2-2}" text-anchor="middle" '
        f'font-family="UnifrakturMaguntia,serif" font-size="24" fill="#e6edf3">{num}</text>'
        f'<text x="{cx}" y="{y+h//2+18}" text-anchor="middle" '
        f'font-family="Cinzel,serif" font-size="8" fill="#8b949e" letter-spacing="2">{label}</text>'
    )

def empty_cell(cfg):
    return scale_color(0, cfg["scale"])

# ── Title SVG ─────────────────────────────────────────────────────────────────

def glyph_paths(font_path, text="seth axel", font_size=62.0):
    from fontTools.ttLib import TTFont
    from fontTools.pens.svgPathPen import SVGPathPen
    import re
    font = TTFont(font_path)
    cmap = font.getBestCmap()
    gset = font.getGlyphSet()
    hmtx = font['hmtx']
    upem = font['head'].unitsPerEm
    s = font_size / upem
    glyphs = []
    for char in text:
        if char == ' ':
            adv = hmtx.metrics.get('.notdef', (500,0))[0] * s * 0.5
            glyphs.append((' ', None, adv))
            continue
        gn = cmap.get(ord(char))
        if gn is None: continue
        pen = SVGPathPen(gset)
        gset[gn].draw(pen)
        p = re.sub(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?', lambda m: f"{float(m.group(0))*s:.1f}", pen.getCommands())
        glyphs.append((char, p, hmtx.metrics[gn][0]*s))
    font.close()
    return glyphs

def build_title_svg():
    import os, re
    from xml.etree import ElementTree as ET
    W=680
    g4_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "g4.svg")
    with open(g4_path) as f:
        g4 = f.read()
    inner = g4.split("<svg", 1)[1]
    inner = inner.split(">", 1)[1]
    inner = inner.rsplit("</svg>", 1)[0]
    sc = W / 204.37494 / 2
    g4_xoff = -3.3807975 + -2.9924433
    g4_center = (204.37494 / 2 + g4_xoff) * sc
    g4_adjust = -round(g4_center) - 7

    # Compute g4 content bounding box for y
    def tokenize(d):
        tokens = []
        i = 0
        while i < len(d):
            if d[i] in 'MmLlCcVvHhSsQqTtAaZz':
                tokens.append(d[i]); i += 1
            elif d[i] in '-0123456789.':
                j = i
                while j < len(d) and d[j] in '-0123456789.eE': j += 1
                tokens.append(d[i:j]); i = j
            else: i += 1
        return tokens
    def parse_y(d):
        tokens = tokenize(d)
        y = 0.0; cmd = None; i = 0; ys = []
        while i < len(tokens):
            t = tokens[i]
            if t in 'MmLlCcVvHhSsQqTtAaZz':
                cmd = t; i += 1
                if cmd in 'Zz': continue
                continue
            if cmd is None: break
            if cmd in ('m','M'):
                y = float(tokens[i+1]) if cmd == 'M' else y + float(tokens[i+1])
                ys.append(y); i += 2
                cmd = 'l' if cmd == 'm' else 'L'
            elif cmd in ('l','L'):
                y = float(tokens[i+1]) if cmd == 'L' else y + float(tokens[i+1])
                ys.append(y); i += 2
            elif cmd in ('c','C'):
                # skip control points, only track endpoint (3rd pair)
                dy = float(tokens[i+5])
                y = dy if cmd == 'C' else y + dy
                ys.append(y); i += 6
            elif cmd in ('v','V'):
                y = float(tokens[i]) if cmd == 'V' else y + float(tokens[i])
                ys.append(y); i += 1
            elif cmd in ('h','H'):
                i += 1
            elif cmd in ('s','S'):
                # skip control point, only track endpoint (2nd pair)
                dy = float(tokens[i+3])
                y = dy if cmd == 'S' else y + dy
                ys.append(y); i += 4
            elif cmd in ('q','Q'):
                # skip control point, only track endpoint (2nd pair)
                dy = float(tokens[i+3])
                y = dy if cmd == 'Q' else y + dy
                ys.append(y); i += 4
            elif cmd in ('t','T'):
                dy = float(tokens[i+1])
                y = dy if cmd == 'T' else y + dy
                ys.append(y); i += 2
            elif cmd in ('a','A'):
                y = float(tokens[i+5]) if cmd == 'A' else y + float(tokens[i+5])
                ys.append(y); i += 7
            else: break
        return ys
    tree = ET.fromstring(g4)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    paths = tree.findall(".//{http://www.w3.org/2000/svg}path") or tree.findall(".//path")
    total_yoff = -217.75742 + (-1.4962217)
    all_y = []
    for path in paths:
        d = path.get('d', '')
        if not d or len(d) < 20: continue
        all_y.extend([y + total_yoff for y in parse_y(d)])
    content_min_y = min(all_y)
    content_max_y = max(all_y)
    content_h_in_title = (content_max_y - content_min_y) * sc
    pad = 10
    H = int(content_h_in_title) + pad * 2
    g4_cy = (content_min_y + content_max_y) / 2
    g4_yoff = -(g4_cy * sc)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <g transform="translate({W//2}, {H//2})">
    <g transform="translate({g4_adjust}, {g4_yoff:.1f}) scale({sc:.4f})">
{inner}
    </g>
  </g>
</svg>"""

def build_subtitle_svg():
    W=680
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="40" viewBox="0 0 {W} 40">
  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&amp;display=swap');
    </style>
  </defs>
  <text x="{W//2}" y="18" text-anchor="middle"
    font-family="IM Fell English,serif" font-style="italic" font-size="15" fill="#8b949e">[sɛθ ˈæk.səl]</text>
  <text x="{W//2}" y="35" text-anchor="middle"
    font-family="IM Fell English,serif" font-style="italic" font-size="13" fill="#8b949e" opacity="0.8">he/him · Junior C &amp; Python Dev</text>
</svg>"""


# ── GitHub stats SVG ──────────────────────────────────────────────────────────

def build_github_svg(gh):
    W=680; H=90
    cw = (W - 100 - 3*12) // 4
    x0 = 50
    cards = (
        stat_card(x0,              0, cw, H, gh["repos"],     "REPOS")        +
        stat_card(x0+cw+12,        0, cw, H, gh["followers"], "FOLLOWERS")    +
        stat_card(x0+(cw+12)*2,    0, cw, H, gh["stars"],     "STARS")        +
        stat_card(x0+(cw+12)*3,    0, cw, H, gh["contribs"],  "CONTRIBUTIONS")
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs><style>{FONTS}</style></defs>
  {cards}
</svg>"""

# ── Contribution graph SVG ────────────────────────────────────────────────────

def build_contrib_svg(weeks, cfg=None):
    if cfg is None:
        cfg = CAL
    th = THEMES[cfg["theme"]]
    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    MAX = 46
    CELL = cfg["subDomain"]["width"]
    GAP = cfg["subDomain"]["gutter"]
    RAD = cfg["subDomain"]["radius"]
    STEP = CELL + GAP
    graph_w = MAX * STEP - GAP
    MARGIN = 40
    W = graph_w + MARGIN * 2
    x0 = (W - graph_w) // 2
    LABEL_H = 18
    H = LABEL_H + 7 * STEP + 6
    use_weeks = weeks[-MAX:] if len(weeks) > MAX else weeks
    parts = []
    last_month = None
    for wi, week in enumerate(use_weeks):
        days = week.get("contributionDays", [])
        if days:
            m = int(days[0]["date"][5:7]) - 1
            if m != last_month:
                last_month = m
                parts.append(
                    f'<text x="{x0 + wi * STEP}" y="{LABEL_H - 4}" '
                    f'font-family="{cfg["domain"]["label"]["font"]}" '
                    f'font-size="{cfg["domain"]["label"]["size"]}" '
                    f'fill="{th["muted"]}">{MONTHS[m]}</text>'
                )
        for di, day in enumerate(days):
            color = scale_color(day["contributionCount"], cfg["scale"])
            x = x0 + wi * STEP
            y = LABEL_H + di * STEP
            parts.append(
                f'<rect x="{x}" y="{y}" '
                f'width="{CELL}" height="{CELL}" '
                f'rx="{RAD}" fill="{color}"/>'
            )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs><style>{FONTS}</style></defs>
  {"".join(parts)}
</svg>"""

# ── LeetCode stats SVG ────────────────────────────────────────────────────────

def build_leetcode_svg(lc):
    W=680; H=90
    cw = (W - 100 - 3*16) // 4
    x0 = 50
    cards = (
        stat_card(x0,           0, cw, H, lc["total"],  "SOLVED") +
        stat_card(x0+(cw+16),   0, cw, H, lc["easy"],   "EASY")   +
        stat_card(x0+(cw+16)*2, 0, cw, H, lc["medium"], "MEDIUM") +
        stat_card(x0+(cw+16)*3, 0, cw, H, lc["hard"],   "HARD")
    )
    # Tag bars
    tags = lc["tags"]
    BAR_Y = H + 20
    bar_parts = []
    if tags:
        total_val = lc["total"]
        BAR_W = 290; ROW_H = 28
        for i, tag in enumerate(tags):
            y  = BAR_Y + i*ROW_H
            fw = int((tag["problemsSolved"]/total_val)*BAR_W) if total_val else 0
            bar_parts.append(
                f'<text x="50" y="{y+13}" font-family="Cinzel,serif" font-size="8" fill="#8b949e" letter-spacing="1">'
                f'{tag["tagName"][:16].upper()}</text>'
                f'<rect x="170" y="{y+7}" width="{BAR_W}" height="3" rx="1" fill="#21262d"/>'
                f'<rect x="170" y="{y+7}" width="{fw}" height="3" rx="1" fill="#8b949e" opacity="0.6"/>'
                f'<text x="{170+BAR_W+10}" y="{y+13}" font-family="Cinzel,serif" font-size="8" fill="#8b949e">'
                f'{tag["problemsSolved"]}</text>'
            )
    total_h = BAR_Y + len(tags)*28 + 10 if tags else H
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{total_h}" viewBox="0 0 {W} {total_h}">
  <defs><style>{FONTS}</style></defs>
  {cards}
  {"".join(bar_parts)}
</svg>"""

# ── Write all SVGs ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Fetching GitHub...")
    gh = fetch_github()
    print(f"  repos={gh['repos']} followers={gh['followers']} stars={gh['stars']} contribs={gh['contribs']}")
    print("Fetching LeetCode...")
    lc = fetch_leetcode()
    print(f"  total={lc['total']} easy={lc['easy']} medium={lc['medium']}")

    with open("title.svg",    "w") as f: f.write(build_title_svg())
    with open("subtitle.svg", "w") as f: f.write(build_subtitle_svg())
    with open("github.svg",  "w") as f: f.write(build_github_svg(gh))
    with open("contrib.svg", "w") as f: f.write(build_contrib_svg(gh["weeks"]))
    with open("leetcode.svg","w") as f: f.write(build_leetcode_svg(lc))
    print("All SVGs written.")
