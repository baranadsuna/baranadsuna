#!/usr/bin/env python3
"""
Generates an animated, glowing-green GitHub Contribution Matrix & Velocity Wave SVG
directly from real GitHub GraphQL contribution data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Tuple

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(privacy: PUBLIC, isFork: false) {
      totalCount
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            color
            weekday
          }
        }
      }
    }
  }
}
""".strip()

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_github_data(username: str, token: str) -> Dict[str, Any]:
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": username}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{username}-contrib-pulse-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def theme_palette(mode: str) -> Dict[str, str]:
    if mode == "light":
        return {
            "bg0": "#f8fafc",
            "bg1": "#f1f5f9",
            "bg2": "#ecfdf5",
            "border": "#16a34a",
            "panel": "#ffffff",
            "panel_stroke": "#cbd5e1",
            "title": "#0f172a",
            "muted": "#475569",
            "month": "#15803d",
            "c0": "#ebedf0",
            "c0_stroke": "#e2e8f0",
            "c0_sweep": "#bbf7d0",
            "c1": "#9be9a8",
            "c2": "#40c463",
            "c3": "#30a14e",
            "c4": "#15803d",
            "cell_hi_stroke": "#166534",
            "pill_bg": "#ecfdf5",
            "pill_txt": "#166534",
            "pill2_bg": "#eff6ff",
            "pill2_txt": "#1d4ed8",
            "dot_stroke": "#0f172a",
            "peak_lbl": "#15803d",
            "wave_title": "#15803d",
            "wave_glow": "0.18",
        }
    return {
        "bg0": "#050912",
        "bg1": "#07131a",
        "bg2": "#051c14",
        "border": "#10b981",
        "panel": "#09111d",
        "panel_stroke": "#1e293b",
        "title": "#f8fafc",
        "muted": "#64748b",
        "month": "#6ee7b7",
        "c0": "#111b27",
        "c0_stroke": "#162231",
        "c0_sweep": "#0a3626",
        "c1": "#065f46",
        "c2": "#15803d",
        "c3": "#22c55e",
        "c4": "#4ade80",
        "cell_hi_stroke": "#86efac",
        "pill_bg": "#052e16",
        "pill_txt": "#86efac",
        "pill2_bg": "#0f172a",
        "pill2_txt": "#93c5fd",
        "dot_stroke": "#ffffff",
        "peak_lbl": "#bbf7d0",
        "wave_title": "#4ade80",
        "wave_glow": "0.42",
    }


def level_color(count: int, max_count: int, pal: Dict[str, str]) -> Tuple[str, int]:
    if count <= 0:
        return pal["c0"], 0
    ratio = count / max(1, max_count)
    if ratio <= 0.25:
        return pal["c1"], 1
    if ratio <= 0.50:
        return pal["c2"], 2
    if ratio <= 0.78:
        return pal["c3"], 3
    return pal["c4"], 4


def smooth_curve_path(pts: List[Tuple[float, float]]) -> str:
    if not pts:
        return ""
    if len(pts) == 1:
        return f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"
    d = [f"M {pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        cx = (x0 + x1) / 2.0
        d.append(f"C {cx:.1f} {y0:.1f}, {cx:.1f} {y1:.1f}, {x1:.1f} {y1:.1f}")
    return " ".join(d)


def compute_current_streak(days: List[Dict[str, Any]]) -> int:
    if not days:
        return 0
    streak = 0
    idx = len(days) - 1
    if idx >= 0 and days[idx]["contributionCount"] == 0:
        idx -= 1
    while idx >= 0 and days[idx]["contributionCount"] > 0:
        streak += 1
        idx -= 1
    return streak


def build_svg(data: Dict[str, Any], username: str, mode: str = "dark") -> str:
    pal = theme_palette(mode)
    user = data["data"]["user"]
    cal = user["contributionsCollection"]["contributionCalendar"]
    total_contribs = int(cal["totalContributions"])
    weeks = cal["weeks"]
    repo_count = int(user.get("repositories", {}).get("totalCount", 0))

    all_days = [d for w in weeks for d in w["contributionDays"]]
    active_days = [d for d in all_days if d["contributionCount"] > 0]
    max_day = max((d["contributionCount"] for d in all_days), default=0)
    peak_day_obj = max(all_days, key=lambda d: d["contributionCount"], default={"date": "", "contributionCount": 0})
    streak = compute_current_streak(all_days)

    # Grid geometry (53 weeks centered cleanly inside 960px frame)
    n_weeks = len(weeks)
    step_x = 15.2
    step_y = 13.6
    cell = 10.6
    grid_x0 = 96.0
    grid_y0 = 78.0

    # Month labels
    month_labels: List[str] = []
    seen_month = None
    last_label_x = -999.0
    for wi, w in enumerate(weeks):
        days = w["contributionDays"]
        if not days:
            continue
        dt = datetime.strptime(days[0]["date"], "%Y-%m-%d")
        ym = (dt.year, dt.month)
        if ym != seen_month:
            seen_month = ym
            x = grid_x0 + wi * step_x
            if x - last_label_x >= 36.0:
                month_labels.append(
                    f'<text x="{x:.1f}" y="{grid_y0 - 7:.1f}" fill="{pal["month"]}" font-size="10.2" font-weight="600" class="mono">{MONTH_NAMES[dt.month - 1]}</text>'
                )
                last_label_x = x

    # Grid cells + radar column sweep keyframes
    cells_svg: List[str] = []
    beacon_svg: List[str] = []
    for wi, w in enumerate(weeks):
        col_delay = (wi / max(1, n_weeks - 1)) * 4.5
        for day in w["contributionDays"]:
            wd = int(day["weekday"])
            cnt = int(day["contributionCount"])
            x = grid_x0 + wi * step_x
            y = grid_y0 + wd * step_y
            col, lvl = level_color(cnt, max(4, max_day), pal)
            if lvl == 0:
                cells_svg.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2.4" '
                    f'fill="{col}" stroke="{pal["c0_stroke"]}" stroke-width="0.8" '
                    f'style="animation: cellSweep 5.5s {col_delay:.2f}s infinite ease-in-out;"/>'
                )
            else:
                glow_attr = ' filter="url(#glowSoft)"' if lvl >= 3 else ""
                pulse_dur = 2.0 if lvl >= 4 else 2.8
                cells_svg.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2.4" '
                    f'fill="{col}" stroke="{pal["cell_hi_stroke"]}" stroke-opacity="0.7" stroke-width="0.9"{glow_attr}>'
                    f'<animate attributeName="opacity" values="0.8;1;0.8" dur="{pulse_dur}s" begin="{(wd * 0.2):.2f}s" repeatCount="indefinite"/>'
                    f'</rect>'
                )
                if lvl >= 3:
                    cx = x + cell / 2.0
                    cy = y + cell / 2.0
                    beacon_svg.append(
                        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="none" stroke="{pal["c4"]}" stroke-width="1.2">'
                        f'<animate attributeName="r" values="4;12" dur="2.6s" begin="{(wd * 0.25):.2f}s" repeatCount="indefinite"/>'
                        f'<animate attributeName="opacity" values="0.75;0" dur="2.6s" begin="{(wd * 0.25):.2f}s" repeatCount="indefinite"/>'
                        f'</circle>'
                    )

    # Bottom Wave: Last 28 days real commit velocity
    recent_days = all_days[-28:] if len(all_days) >= 28 else all_days
    wave_x0 = 56.0
    wave_x1 = 904.0
    wave_y_base = 286.0
    wave_y_top = 240.0
    y_max = max(4, max((d["contributionCount"] for d in recent_days), default=4))

    pts: List[Tuple[float, float]] = []
    n_rec = max(2, len(recent_days))
    for idx, d in enumerate(recent_days):
        px = wave_x0 + (idx / (n_rec - 1)) * (wave_x1 - wave_x0)
        py = wave_y_base - (d["contributionCount"] / float(y_max)) * (wave_y_base - wave_y_top)
        pts.append((px, py))

    curve_d = smooth_curve_path(pts)
    area_d = f"{curve_d} L {pts[-1][0]:.1f} {wave_y_base:.1f} L {pts[0][0]:.1f} {wave_y_base:.1f} Z"

    peak_markers: List[str] = []
    for idx, (px, py) in enumerate(pts):
        cnt = int(recent_days[idx]["contributionCount"])
        date_short = recent_days[idx]["date"][5:]
        if cnt > 0:
            peak_markers.append(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#22c55e" stroke="{pal["dot_stroke"]}" stroke-width="1.4" filter="url(#glowSoft)"/>'
            )
            peak_markers.append(
                f'<text x="{px:.1f}" y="{py - 8:.1f}" text-anchor="middle" fill="{pal["peak_lbl"]}" font-size="9.5" font-weight="700" class="mono">{cnt}</text>'
            )
        if idx in (0, len(pts) // 2, len(pts) - 1) or (cnt == max_day and cnt > 0):
            peak_markers.append(
                f'<text x="{px:.1f}" y="{wave_y_base + 14:.1f}" text-anchor="middle" fill="{pal["muted"]}" font-size="9" class="mono">{date_short}</text>'
            )

    repo_pill = f"REPOS: {repo_count}" if repo_count > 0 else "ACTIVE NOW"
    peak_txt = f"PEAK: {peak_day_obj['contributionCount']}/DAY" if peak_day_obj["contributionCount"] > 0 else "PEAK: LIVE"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 322" width="100%" height="100%">
  <defs>
    <linearGradient id="bgCard" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{pal["bg0"]}"/>
      <stop offset="55%" stop-color="{pal["bg1"]}"/>
      <stop offset="100%" stop-color="{pal["bg2"]}"/>
    </linearGradient>
    <linearGradient id="waveAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#22c55e" stop-opacity="{pal["wave_glow"]}"/>
      <stop offset="85%" stop-color="#16a34a" stop-opacity="0.06"/>
      <stop offset="100%" stop-color="#16a34a" stop-opacity="0.0"/>
    </linearGradient>
    <linearGradient id="waveStrokeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10b981"/>
      <stop offset="65%" stop-color="#22c55e"/>
      <stop offset="100%" stop-color="#4ade80"/>
    </linearGradient>
    <filter id="glowSoft" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="2.8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <style>
      .ui {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; }}
      .mono {{ font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace; }}
      @keyframes cellSweep {{
        0%, 100% {{ fill: {pal["c0"]}; stroke: {pal["c0_stroke"]}; }}
        12% {{ fill: {pal["c0_sweep"]}; stroke: #15803d; }}
        24% {{ fill: {pal["c0"]}; stroke: {pal["c0_stroke"]}; }}
      }}
      .wave-line {{
        stroke: url(#waveStrokeGrad);
        stroke-width: 3;
        stroke-linecap: round;
        fill: none;
        filter: url(#glowSoft);
        stroke-dasharray: 1200;
        stroke-dashoffset: 1200;
        animation: drawWave 4.2s infinite ease-in-out;
      }}
      @keyframes drawWave {{
        0% {{ stroke-dashoffset: 1200; opacity: 0.35; }}
        45%, 88% {{ stroke-dashoffset: 0; opacity: 1; }}
        100% {{ stroke-dashoffset: 0; opacity: 0.45; }}
      }}
    </style>
  </defs>

  <!-- Main Card Container -->
  <rect width="960" height="322" rx="14" fill="url(#bgCard)" stroke="{pal["border"]}" stroke-opacity="0.45" stroke-width="1.6"/>

  <!-- Top Telemetry Header -->
  <circle cx="28" cy="29" r="5" fill="#22c55e" filter="url(#glowSoft)">
    <animate attributeName="opacity" values="1;0.3;1" dur="1.4s" repeatCount="indefinite"/>
  </circle>
  <text x="41" y="34" fill="{pal["title"]}" font-size="12.5" font-weight="800" letter-spacing="0.3" class="ui">
    LIVE CONTRIBUTION MATRIX &amp; VELOCITY &#8226; @{username.upper()}
  </text>

  <!-- Real Telemetry Pills -->
  <g transform="translate(492, 17)" class="mono" font-size="9.8" font-weight="700">
    <rect x="0" y="0" width="134" height="24" rx="6" fill="{pal["pill_bg"]}" stroke="#22c55e" stroke-width="1"/>
    <text x="67" y="16" text-anchor="middle" fill="{pal["pill_txt"]}">{total_contribs} PUBLIC COMMITS</text>

    <rect x="142" y="0" width="90" height="24" rx="6" fill="{pal["pill2_bg"]}" stroke="#10b981" stroke-width="1"/>
    <text x="187" y="16" text-anchor="middle" fill="{pal["month"]}">STREAK: {streak}d</text>

    <rect x="240" y="0" width="98" height="24" rx="6" fill="{pal["pill2_bg"]}" stroke="#3b82f6" stroke-width="1"/>
    <text x="289" y="16" text-anchor="middle" fill="{pal["pill2_txt"]}">{peak_txt}</text>

    <rect x="346" y="0" width="94" height="24" rx="6" fill="{pal["pill2_bg"]}" stroke="#22c55e" stroke-width="1"/>
    <text x="393" y="16" text-anchor="middle" fill="{pal["pill_txt"]}">{repo_pill}</text>
  </g>

  <!-- Matrix Box Frame -->
  <rect x="24" y="54" width="912" height="142" rx="10" fill="{pal["panel"]}" fill-opacity="0.88" stroke="{pal["panel_stroke"]}" stroke-width="1.2"/>

  <!-- Weekday Labels -->
  <text x="44" y="{grid_y0 + 1 * step_y + 9:.1f}" fill="{pal["muted"]}" font-size="10" class="mono">Mon</text>
  <text x="44" y="{grid_y0 + 3 * step_y + 9:.1f}" fill="{pal["muted"]}" font-size="10" class="mono">Wed</text>
  <text x="44" y="{grid_y0 + 5 * step_y + 9:.1f}" fill="{pal["muted"]}" font-size="10" class="mono">Fri</text>

  <!-- Month Headers -->
  {''.join(month_labels)}

  <!-- Animated 53x7 Contribution Cells -->
  {''.join(cells_svg)}
  {''.join(beacon_svg)}

  <!-- Matrix Legend -->
  <g transform="translate(696, 179)" class="mono" font-size="9.5">
    <text x="0" y="9" fill="{pal["muted"]}">Less</text>
    <rect x="30" y="0" width="10" height="10" rx="2" fill="{pal["c0"]}" stroke="{pal["c0_stroke"]}"/>
    <rect x="44" y="0" width="10" height="10" rx="2" fill="{pal["c1"]}"/>
    <rect x="58" y="0" width="10" height="10" rx="2" fill="{pal["c2"]}"/>
    <rect x="72" y="0" width="10" height="10" rx="2" fill="{pal["c3"]}"/>
    <rect x="86" y="0" width="10" height="10" rx="2" fill="{pal["c4"]}"/>
    <text x="102" y="9" fill="{pal["wave_title"]}">More ({len(active_days)} active days)</text>
  </g>

  <!-- Bottom Live 28-Day Commit Velocity Wave -->
  <rect x="24" y="204" width="912" height="104" rx="10" fill="{pal["panel"]}" fill-opacity="0.88" stroke="{pal["panel_stroke"]}" stroke-width="1.2"/>
  <text x="40" y="222" fill="{pal["wave_title"]}" font-size="10.5" font-weight="700" class="mono">28-DAY LIVE COMMIT VELOCITY WAVE</text>
  <line x1="{wave_x0}" y1="{wave_y_base}" x2="{wave_x1}" y2="{wave_y_base}" stroke="{pal["panel_stroke"]}" stroke-width="1"/>
  <path d="{area_d}" fill="url(#waveAreaGrad)"/>
  <path d="{curve_d}" class="wave-line"/>
  {''.join(peak_markers)}
  <circle r="4.5" fill="#ffffff" stroke="#22c55e" stroke-width="2" filter="url(#glowSoft)">
    <animateMotion dur="4.2s" repeatCount="indefinite" path="{curve_d}"/>
  </circle>
</svg>
"""
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate animated green GitHub contribution SVG")
    parser.add_argument("--username", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "baranadsuna"))
    parser.add_argument("--out", default="dist/contrib-pulse-dark.svg")
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    parser.add_argument("--input-json", help="Optional local GraphQL JSON file for testing")
    args = parser.parse_args()

    if args.input_json:
        with open(args.input_json, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    else:
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("ERROR: GITHUB_TOKEN environment variable is required", file=sys.stderr)
            return 1
        data = fetch_github_data(args.username, token)

    svg = build_svg(data, args.username, mode=args.theme)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Generated {args.out} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
