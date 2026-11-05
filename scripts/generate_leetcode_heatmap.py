#!/usr/bin/env python3
"""
Generate an automatically updating LeetCode Activity Heatmap SVG for Sandeep L (@Sandeep_664).
Uses LeetCode's public GraphQL API. Standard library only (no external pip dependencies).
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta, timezone

LEETCODE_USERNAME = "Sandeep_664"
OUTPUT_SVG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "leetcode-heatmap.svg")

GRAPHQL_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    userCalendar {
      activeYears
      streak
      totalActiveDays
      submissionCalendar
    }
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
        submissions
      }
    }
  }
}
"""

def fetch_leetcode_data(username: str, retries: int = 3, timeout: int = 15) -> dict:
    url = "https://leetcode.com/graphql"
    payload = json.dumps({
        "query": GRAPHQL_QUERY,
        "variables": {"username": username}
    }).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://leetcode.com/u/{username}/",
        "Origin": "https://leetcode.com"
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    for attempt in range(1, retries + 1):
        try:
            print(f"[FETCH] Requesting LeetCode data for '{username}' (attempt {attempt}/{retries})...")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(url, response.status, f"HTTP {response.status}", response.headers, None)
                data = json.loads(response.read().decode("utf-8"))
                
                # Validation
                matched = data.get("data", {}).get("matchedUser")
                if not matched or matched.get("username", "").lower() != username.lower():
                    raise ValueError(f"User validation failed. Expected '{username}', got '{matched}'")
                
                calendar_raw = matched.get("userCalendar", {}).get("submissionCalendar")
                if not calendar_raw:
                    raise ValueError(f"Empty submission calendar returned for '{username}'")
                
                print(f"[SUCCESS] Successfully retrieved and validated LeetCode data for '{username}'.")
                return data
        except Exception as e:
            print(f"[WARN] Attempt {attempt} failed: {e}", file=sys.stderr)
            if attempt == retries:
                raise
    raise RuntimeError(f"Failed to fetch data for {username} after {retries} retries.")

def parse_submission_calendar(data: dict) -> tuple[dict, int, int]:
    matched = data["data"]["matchedUser"]
    calendar_raw = matched["userCalendar"]["submissionCalendar"]
    calendar_json = json.loads(calendar_raw)
    
    # Map unix timestamps to YYYY-MM-DD
    # LeetCode unix timestamps are normalized to UTC midnight
    submissions_by_date = {}
    for ts_str, count in calendar_json.items():
        ts = int(ts_str)
        # UTC date
        d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        date_key = d.strftime("%Y-%m-%d")
        submissions_by_date[date_key] = submissions_by_date.get(date_key, 0) + count
        
    streak = matched["userCalendar"].get("streak", 0)
    total_active_days = matched["userCalendar"].get("totalActiveDays", len(submissions_by_date))
    return submissions_by_date, streak, total_active_days

def calculate_streaks(submissions_by_date: dict, end_date: date) -> tuple[int, int]:
    """Calculate current and longest active streaks in days."""
    dates_set = {d_str for d_str, count in submissions_by_date.items() if count > 0}
    
    # Check current streak ending today or yesterday
    cur_streak = 0
    check_date = end_date
    if check_date.strftime("%Y-%m-%d") not in dates_set:
        check_date = end_date - timedelta(days=1)
        
    while check_date.strftime("%Y-%m-%d") in dates_set:
        cur_streak += 1
        check_date -= timedelta(days=1)
        
    # Longest streak across all dates
    sorted_dates = sorted([datetime.strptime(d, "%Y-%m-%d").date() for d in dates_set])
    longest_streak = 0
    current_run = 0
    prev_d = None
    for d in sorted_dates:
        if prev_d is None or d == prev_d + timedelta(days=1):
            current_run += 1
        else:
            current_run = 1
        if current_run > longest_streak:
            longest_streak = current_run
        prev_d = d
        
    return cur_streak, max(longest_streak, cur_streak)

def get_intensity_color(count: int) -> str:
    """Colors matched to Sandeep's signature dark theme (Blue to Purple gradient)."""
    if count == 0:
        return "#161b22"  # GitHub dark empty cell
    elif count <= 2:
        return "#1e3a8a"  # Level 1: Deep Sapphire Blue
    elif count <= 5:
        return "#3b82f6"  # Level 2: Vibrant Electric Blue
    elif count <= 8:
        return "#7c5ff5"  # Level 3: Royal Indigo Purple
    else:
        return "#a855f7"  # Level 4: Vivid Neon Purple

def generate_svg(submissions_by_date: dict, current_streak: int, longest_streak: int, end_date: date) -> str:
    """
    Build a clean, responsive, GitHub-style 53-week contribution calendar SVG.
    """
    # Grid dimensions
    cell_size = 11
    cell_gap = 3
    col_width = cell_size + cell_gap  # 14px
    row_height = cell_size + cell_gap # 14px
    
    # Calculate starting date (align to Sunday 52 weeks ago)
    # end_date weekday: Monday=0, Sunday=6
    days_since_sunday = (end_date.weekday() + 1) % 7
    total_days = 52 * 7 + days_since_sunday + 1  # 53 columns total
    start_date = end_date - timedelta(days=total_days - 1)
    
    # Offsets inside SVG
    grid_x = 42
    grid_y = 68
    
    # Calculate total submissions in this window
    window_submissions = 0
    window_active_days = 0
    
    calendar_cells = []
    month_labels = {}
    
    cur_d = start_date
    col = 0
    while cur_d <= end_date:
        row = (cur_d.weekday() + 1) % 7  # 0 = Sunday, 1 = Monday ... 6 = Saturday
        d_str = cur_d.strftime("%Y-%m-%d")
        count = submissions_by_date.get(d_str, 0)
        
        if count > 0:
            window_submissions += count
            window_active_days += 1
            
        color = get_intensity_color(count)
        
        # Track first week of each month for labels
        if cur_d.day <= 7 and cur_d.strftime("%b") not in month_labels.values():
            month_labels[col] = cur_d.strftime("%b")
            
        x = grid_x + col * col_width
        y = grid_y + row * row_height
        
        formatted_date = cur_d.strftime("%B %d, %Y")
        sub_text = f"{count} submission{'s' if count != 1 else ''}" if count > 0 else "No submissions"
        title_text = f"{sub_text} on {formatted_date}"
        
        calendar_cells.append(
            f'<rect class="day" x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2.5" fill="{color}">'
            f'<title>{title_text}</title></rect>'
        )
        
        if row == 6:
            col += 1
        cur_d += timedelta(days=1)
        
    total_cols = col + 1 if row != 6 else col
    
    # Month label XML
    month_svg_labels = []
    for c, m_name in month_labels.items():
        mx = grid_x + c * col_width
        month_svg_labels.append(f'<text class="legend-text" x="{mx}" y="{grid_y - 8}">{m_name}</text>')
        
    # Day labels (Mon, Wed, Fri)
    day_labels = [
        (1, "Mon"),
        (3, "Wed"),
        (5, "Fri")
    ]
    day_svg_labels = []
    for r_idx, d_name in day_labels:
        dy = grid_y + r_idx * row_height + 9
        day_svg_labels.append(f'<text class="legend-text" x="12" y="{dy}">{d_name}</text>')

    # Total width & height
    total_width = grid_x + (total_cols * col_width) + 32
    total_height = 200

    # Build entire SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_width} {total_height}" width="{total_width}" height="{total_height}" role="img" aria-label="LeetCode Contribution Heatmap for Sandeep L">',
        '  <defs>',
        '    <style>',
        '      .bg { fill: #0d1117; stroke: #21262d; stroke-width: 1px; rx: 8px; }',
        '      .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; fill: #4f8ef7; }',
        '      .stat-pill { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 11px; fill: #8b949e; }',
        '      .stat-val { font-weight: 600; fill: #c9d1d9; }',
        '      .legend-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 10px; fill: #6e7681; }',
        '      .day { stroke: rgba(255,255,255,0.04); stroke-width: 0.5px; transition: all 0.2s ease; }',
        '      .day:hover { stroke: #4f8ef7; stroke-width: 1.5px; }',
        '    </style>',
        '  </defs>',
        f'  <rect width="{total_width}" height="{total_height}" class="bg"/>',
        '',
        '  <!-- Header Row: LeetCode Brand Icon & Title -->',
        '  <g transform="translate(18, 18)">',
        '    <!-- LeetCode Official Hexagon Logo -->',
        '    <path d="M13.483 0a1.374 1.374 0 0 0-.961.438L7.116 6.26c-1.077 1.134-1.285 2.846-.505 4.19l-4.52 4.417a1.374 1.374 0 0 0 0 1.942l3.208 3.136a1.374 1.374 0 0 0 1.942 0l4.52-4.417a4.015 4.015 0 0 0 4.19-.505l5.822-5.406a1.374 1.374 0 0 0 0-1.942l-7.829-7.237A1.374 1.374 0 0 0 13.483 0zm-.066 3.107 5.753 5.319-4.28 3.974a2.227 2.227 0 0 1-2.946.126l-.21-.19-.209-.19a2.227 2.227 0 0 1-.127-2.945l2.019-2.093z" fill="#FFA116"/>',
        '    <text x="30" y="15" class="title">LeetCode Activity Calendar · @Sandeep_664</text>',
        '  </g>',
        '',
        '  <!-- Stat Badges in Header -->',
        '  <g transform="translate(420, 18)">',
        f'    <text x="0" y="15" class="stat-pill">Submissions: <tspan class="stat-val">{window_submissions}</tspan></text>',
        f'    <text x="130" y="15" class="stat-pill">Active Days: <tspan class="stat-val">{window_active_days}</tspan></text>',
        f'    <text x="250" y="15" class="stat-pill">Current Streak: <tspan class="stat-val">{current_streak} days</tspan></text>',
        f'    <text x="390" y="15" class="stat-pill">Max Streak: <tspan class="stat-val">{longest_streak} days</tspan></text>',
        '  </g>',
        '',
        '  <!-- Month Labels -->',
        '  <g>' + "".join(month_svg_labels) + '</g>',
        '',
        '  <!-- Day of Week Labels -->',
        '  <g>' + "".join(day_svg_labels) + '</g>',
        '',
        '  <!-- 53-Week Calendar Cells -->',
        '  <g>' + "".join(calendar_cells) + '</g>',
        '',
        '  <!-- Footer Legend -->',
        f'  <g transform="translate({total_width - 170}, {grid_y + 7 * row_height + 15})">',
        '    <text x="0" y="9" class="legend-text">Less</text>',
        f'    <rect x="28" y="0" width="10" height="10" rx="2" fill="{get_intensity_color(0)}"/>',
        f'    <rect x="42" y="0" width="10" height="10" rx="2" fill="{get_intensity_color(1)}"/>',
        f'    <rect x="56" y="0" width="10" height="10" rx="2" fill="{get_intensity_color(4)}"/>',
        f'    <rect x="70" y="0" width="10" height="10" rx="2" fill="{get_intensity_color(7)}"/>',
        f'    <rect x="84" y="0" width="10" height="10" rx="2" fill="{get_intensity_color(11)}"/>',
        '    <text x="100" y="9" class="legend-text">More</text>',
        '  </g>',
        '</svg>'
    ]
    return "\n".join(svg_parts)

def main():
    print(f"=== Generating LeetCode Heatmap for @{LEETCODE_USERNAME} ===")
    try:
        data = fetch_leetcode_data(LEETCODE_USERNAME)
        submissions_by_date, live_streak, total_active_days = parse_submission_calendar(data)
        
        today = datetime.now(timezone.utc).date()
        calc_cur_streak, longest_streak = calculate_streaks(submissions_by_date, today)
        effective_streak = max(live_streak, calc_cur_streak)
        
        print(f"[METRICS] Submissions recorded: {len(submissions_by_date)} days")
        print(f"[METRICS] Streak: {effective_streak} days (longest: {longest_streak} days)")
        
        new_svg = generate_svg(submissions_by_date, effective_streak, longest_streak, today)
        
        os.makedirs(os.path.dirname(OUTPUT_SVG_PATH), exist_ok=True)
        
        # Check if existing file is identical to prevent unnecessary timestamp bumps
        if os.path.exists(OUTPUT_SVG_PATH):
            with open(OUTPUT_SVG_PATH, "r", encoding="utf-8") as f:
                existing_svg = f.read()
            if existing_svg == new_svg:
                print(f"[UNCHANGED] LeetCode heatmap at {OUTPUT_SVG_PATH} is already up to date. Skipping write.")
                return 0
                
        with open(OUTPUT_SVG_PATH, "w", encoding="utf-8") as f:
            f.write(new_svg)
        print(f"[SAVED] Generated new LeetCode heatmap SVG successfully -> {OUTPUT_SVG_PATH}")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to generate LeetCode heatmap: {e}", file=sys.stderr)
        # If output SVG already exists, do NOT delete it or overwrite with broken content
        if os.path.exists(OUTPUT_SVG_PATH):
            print(f"[PRESERVED] Preserving previously generated valid SVG at {OUTPUT_SVG_PATH}")
            return 0  # Fail safely without breaking the profile
        return 1

if __name__ == "__main__":
    sys.exit(main())

