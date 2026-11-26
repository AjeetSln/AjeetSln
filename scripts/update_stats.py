#!/usr/bin/env python3
"""
Fetches real public + private contribution metrics from AjeetSln's GitHub
contributions calendar and generates assets/contribution-activity.svg.
"""
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = "AjeetSln"
BASE_URL = f"https://github.com/users/{USERNAME}/contributions"


def fetch_calendar(query=""):
    req = urllib.request.Request(
        BASE_URL + query,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ProfileStatsBot/1.0)"},
    )
    html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    tags = re.findall(r'<td[^>]*class="ContributionCalendar-day"[^>]*>', html)
    cells = []
    for t in tags:
        cid = re.search(r'id="contribution-day-component-([^"]+)"', t)
        dt = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', t)
        if cid and dt:
            cells.append((cid.group(1), dt.group(1)))

    tips = dict(
        re.findall(r'for="contribution-day-component-([^"]+)"[^>]*>([^<]+)<', html)
    )
    out = {}
    for cid, dt in cells:
        tip = tips.get(cid, "")
        m = re.match(r"(\d+)\s+contribution", tip)
        out[dt] = int(m.group(1)) if m else 0
    return out


def fmt_short_date(ds):
    d = datetime.strptime(ds, "%Y-%m-%d")
    return d.strftime("%b %-d, %Y")


def main():
    ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    today_str = ist_now.strftime("%Y-%m-%d")
    current_year = ist_now.year

    all_days = {}
    for yr in range(2023, current_year + 1):
        all_days.update(fetch_calendar(f"?from={yr}-01-01&to={yr}-12-31"))

    rolling_days = fetch_calendar("")
    all_days.update(rolling_days)

    valid_days = {k: v for k, v in all_days.items() if k <= today_str}
    sorted_dates = sorted(valid_days.keys())

    total_all_time = sum(valid_days.values())
    last_year_total = sum(
        v for k, v in rolling_days.items() if k <= today_str
    )

    first_active = next((d for d in sorted_dates if valid_days[d] > 0), "2023-06-30")

    # Longest streak
    best_streak = 0
    best_start = best_end = today_str
    run = 0
    run_start = None
    prev_d = None
    for ds in sorted_dates:
        c = valid_days[ds]
        d = datetime.strptime(ds, "%Y-%m-%d").date()
        if c > 0:
            if run == 0 or (prev_d and (d - prev_d).days == 1):
                if run == 0:
                    run_start = ds
                run += 1
            else:
                run = 1
                run_start = ds
            if run > best_streak:
                best_streak = run
                best_start = run_start
                best_end = ds
        else:
            run = 0
            run_start = None
        prev_d = d

    # Monthly rollup over the rolling 12-month calendar
    monthly = defaultdict(int)
    for ds, cnt in rolling_days.items():
        if ds <= today_str:
            monthly[ds[:7]] += cnt

    months_sorted = sorted(monthly.keys())[-12:]
    month_labels = [
        datetime.strptime(m + "-01", "%Y-%m-%d").strftime("%b '%y")
        for m in months_sorted
    ]
    month_vals = [monthly[m] for m in months_sorted]
    max_val = max(month_vals) if month_vals and max(month_vals) > 0 else 10

    # Chart geometry: x from 72 to 1140, y from 250 (bottom) to 145 (top)
    x_start, x_end = 78.0, 1138.0
    y_bottom, y_top = 268.0, 152.0
    n = max(1, len(month_vals))
    step = (x_end - x_start) / max(1, n - 1)

    pts = []
    for i, val in enumerate(month_vals):
        x = x_start + i * step
        y = y_bottom - (val / max_val) * (y_bottom - y_top)
        pts.append((round(x, 1), round(y, 1), val, month_labels[i]))

    # Smooth path
    line_d = f"M {pts[0][0]} {pts[0][1]}"
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1][0], pts[i - 1][1]
        x1, y1 = pts[i][0], pts[i][1]
        cx = round((x0 + x1) / 2, 1)
        line_d += f" C {cx} {y0}, {cx} {y1}, {x1} {y1}"

    area_d = f"{line_d} L {pts[-1][0]} {y_bottom} L {pts[0][0]} {y_bottom} Z"

    # Grid lines
    grid_svg = ""
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = round(y_bottom - frac * (y_bottom - y_top), 1)
        gval = int(round(frac * max_val))
        grid_svg += f'<line x1="64" y1="{gy}" x2="1152" y2="{gy}" stroke="#1E293B" stroke-width="1" stroke-dasharray="4 4" />\n'
        grid_svg += f'<text x="54" y="{gy + 4}" text-anchor="end" fill="#64748B" font-family="\'SFMono-Regular\', Consolas, monospace" font-size="11">{gval}</text>\n'

    # Data nodes & x-labels
    nodes_svg = ""
    for x, y, val, lbl in pts:
        label_y = y - 12 if y > y_top + 14 else y + 18
        nodes_svg += f'<circle cx="{x}" cy="{y}" r="5" fill="#0D1117" stroke="#22D3EE" stroke-width="2.5" />\n'
        if val > 0:
            nodes_svg += f'<text x="{x}" y="{label_y}" text-anchor="middle" fill="#E2E8F0" font-family="\'SFMono-Regular\', Consolas, monospace" font-size="11.5" font-weight="700">{val}</text>\n'
        nodes_svg += f'<text x="{x}" y="{y_bottom + 24}" text-anchor="middle" fill="#94A3B8" font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif" font-size="11.5" font-weight="600">{lbl}</text>\n'

    first_fmt = fmt_short_date(first_active)
    best_range = f"{fmt_short_date(best_start)} - {fmt_short_date(best_end)}"

    svg = f"""<svg width="1200" height="335" viewBox="0 0 1200 335" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bgMain" x1="0" y1="0" x2="1200" y2="335" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#090D16" />
      <stop offset="100%" stop-color="#0F172A" />
    </linearGradient>
    <linearGradient id="areaGrad" x1="0" y1="152" x2="0" y2="268" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#6366F1" stop-opacity="0.45" />
      <stop offset="100%" stop-color="#6366F1" stop-opacity="0.02" />
    </linearGradient>
    <linearGradient id="lineGrad" x1="78" y1="0" x2="1138" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#22D3EE" />
      <stop offset="50%" stop-color="#818CF8" />
      <stop offset="100%" stop-color="#C084FC" />
    </linearGradient>
    <linearGradient id="borderGrad" x1="0" y1="0" x2="1200" y2="335" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#4F46E5" stop-opacity="0.7" />
      <stop offset="100%" stop-color="#06B6D4" stop-opacity="0.6" />
    </linearGradient>
  </defs>

  <rect x="2" y="2" width="1196" height="331" rx="16" fill="url(#bgMain)" stroke="url(#borderGrad)" stroke-width="1.5" />

  <!-- Top Streak & Contribution Summary Bar -->
  <!-- Card 1: All-Time -->
  <rect x="24" y="20" width="368" height="84" rx="12" fill="#0D1117" stroke="#1E293B" stroke-width="1" />
  <text x="208" y="54" text-anchor="middle" fill="#34D399" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="800">{total_all_time}</text>
  <text x="208" y="74" text-anchor="middle" fill="#E2E8F0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600">Total Contributions (Public + Private)</text>
  <text x="208" y="92" text-anchor="middle" fill="#64748B" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">{first_fmt} - Present</text>

  <!-- Card 2: Rolling 12 Months -->
  <rect x="416" y="20" width="368" height="84" rx="12" fill="#0D1117" stroke="#4F46E5" stroke-opacity="0.8" stroke-width="1.5" />
  <text x="600" y="54" text-anchor="middle" fill="#38BDF8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="800">{last_year_total}</text>
  <text x="600" y="74" text-anchor="middle" fill="#E2E8F0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600">Contributions in the Last Year</text>
  <text x="600" y="92" text-anchor="middle" fill="#A78BFA" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">Verified GitHub Profile Graph (Incl. Private)</text>

  <!-- Card 3: Longest Streak -->
  <rect x="808" y="20" width="368" height="84" rx="12" fill="#0D1117" stroke="#1E293B" stroke-width="1" />
  <text x="992" y="54" text-anchor="middle" fill="#FBBF24" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="800">{best_streak} Days</text>
  <text x="992" y="74" text-anchor="middle" fill="#E2E8F0" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="13" font-weight="600">Longest Coding Streak</text>
  <text x="992" y="92" text-anchor="middle" fill="#64748B" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="11">{best_range}</text>

  <!-- Chart Title -->
  <text x="32" y="132" fill="#A78BFA" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="15" font-weight="700">
    Ajeet Prajapati's 12-Month Contribution Velocity (Public + Private)
  </text>

  <!-- Chart Grid & Curve -->
  {grid_svg}
  <path d="{area_d}" fill="url(#areaGrad)" />
  <path d="{line_d}" fill="none" stroke="url(#lineGrad)" stroke-width="3" stroke-linecap="round" />
  {nodes_svg}
</svg>
"""

    out_path = Path(__file__).resolve().parent.parent / "assets" / "contribution-activity.svg"
    out_path.write_text(svg, encoding="utf-8")
    print(f"Generated {out_path}: all_time={total_all_time}, last_year={last_year_total}, best={best_streak}")


if __name__ == "__main__":
    main()
