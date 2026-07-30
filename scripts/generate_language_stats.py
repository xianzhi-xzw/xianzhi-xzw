#!/usr/bin/env python3
"""Generate contribution-based language and activity SVGs."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo


TIME_ZONE = ZoneInfo("Asia/Shanghai")
LANGUAGE_DAYS = 365
ACTIVITY_DAYS = 30
COLORS = {
    "Python": "#3572A5",
    "C++": "#f34b7d",
    "C": "#555555",
    "CUDA": "#3A4E3A",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Vue": "#41b883",
    "TeX": "#3D6117",
    "Shell": "#89e051",
    "CMake": "#DA3434",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "Rust": "#dea584",
    "Java": "#b07219",
    "Go": "#00ADD8",
}
EXTENSION_LANGUAGES = {
    ".asm": "Assembly",
    ".bash": "Shell",
    ".bib": "BibTeX",
    ".bst": "BibTeX",
    ".c": "C",
    ".cc": "C++",
    ".cmake": "CMake",
    ".cpp": "C++",
    ".css": "CSS",
    ".cu": "CUDA",
    ".cuh": "CUDA",
    ".cxx": "C++",
    ".go": "Go",
    ".h": "C++",
    ".hh": "C++",
    ".hpp": "C++",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".php": "PHP",
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Python",
    ".r": "R",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sql": "SQL",
    ".swift": "Swift",
    ".tex": "TeX",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
    ".zsh": "Shell",
}
FILENAME_LANGUAGES = {
    "CMakeLists.txt": "CMake",
    "Dockerfile": "Dockerfile",
    "Makefile": "Makefile",
}
EXCLUDED_PATH_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "vendor",
    "third_party",
    "dist",
    "build",
    "datasets",
    "data",
    "outputs",
    "checkpoints",
}


def github_request(token: str, url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "xianzhi-contribution-stats",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def contributed_commits(token: str, username: str, since: date) -> list[dict]:
    query = quote(f"author:{username} author-date:>={since.isoformat()}")
    commits: list[dict] = []
    page = 1
    while True:
        result = github_request(
            token,
            f"https://api.github.com/search/commits?q={query}&per_page=100&page={page}",
        )
        batch = result["items"]
        commits.extend(batch)
        # GitHub's commit search endpoint exposes at most 1,000 results.
        if len(batch) < 100 or page >= 10:
            break
        page += 1
    return commits


def commit_detail(token: str, item: dict) -> dict | None:
    full_name = quote(item["repository"]["full_name"], safe="/")
    sha = item["sha"]
    try:
        return github_request(
            token,
            f"https://api.github.com/repos/{full_name}/commits/{sha}?per_page=100",
        )
    except HTTPError:
        return None


def language_for_file(filename: str) -> str | None:
    path = Path(filename)
    if EXCLUDED_PATH_PARTS.intersection(path.parts):
        return None
    return FILENAME_LANGUAGES.get(path.name) or EXTENSION_LANGUAGES.get(
        path.suffix.casefold()
    )


def contribution_statistics(
    token: str, username: str
) -> tuple[dict[str, int], dict[str, dict[str, int]], int]:
    today = datetime.now(TIME_ZONE).date()
    contribution_start = today - timedelta(days=LANGUAGE_DAYS - 1)
    activity_start = today - timedelta(days=ACTIVITY_DAYS - 1)
    commits = contributed_commits(token, username, contribution_start)
    language_additions: dict[str, int] = {}
    activity = {
        (activity_start + timedelta(days=offset)).isoformat(): {
            "additions": 0,
            "deletions": 0,
        }
        for offset in range(ACTIVITY_DAYS)
    }

    with ThreadPoolExecutor(max_workers=8) as executor:
        details = executor.map(lambda item: commit_detail(token, item), commits)
        for detail in details:
            if not detail or len(detail.get("parents", [])) > 1:
                continue
            authored_at = detail["commit"]["author"]["date"]
            local_day = (
                datetime.fromisoformat(authored_at.replace("Z", "+00:00"))
                .astimezone(TIME_ZONE)
                .date()
                .isoformat()
            )
            for changed_file in detail.get("files", []):
                language = language_for_file(changed_file["filename"])
                if language is None:
                    continue
                additions = changed_file.get("additions", 0)
                deletions = changed_file.get("deletions", 0)
                language_additions[language] = (
                    language_additions.get(language, 0) + additions
                )
                if local_day in activity:
                    activity[local_day]["additions"] += additions
                    activity[local_day]["deletions"] += deletions

    return language_additions, activity, len(commits)


def compact_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def render_language_svg(counts: dict[str, int], output: Path) -> None:
    languages = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]
    total = sum(counts.values())
    width = 850
    row_height = 34
    height = 74 + row_height * len(languages)
    rows: list[str] = []
    for index, (language, count) in enumerate(languages):
        y = 68 + index * row_height
        percent = count / total * 100 if total else 0
        bar_width = max(2, round(percent / 100 * 535))
        color = COLORS.get(language, "#8b949e")
        rows.append(
            f"""
  <g transform="translate(24 {y})">
    <circle cx="5" cy="5" r="5" fill="{color}"/>
    <text class="language" x="20" y="10">{escape(language)}</text>
    <rect class="track" x="160" y="0" width="535" height="10" rx="5"/>
    <rect x="160" y="0" width="{bar_width}" height="10" rx="5" fill="{color}"/>
    <text class="value" x="805" y="10" text-anchor="end">{count:,} added · {percent:.1f}%</text>
  </g>"""
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Languages by Contributed Lines</title>
  <desc id="desc">Programming languages aggregated from the user's commits across accessible repositories</desc>
  <style>
    .title {{ font: 600 18px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; fill: #1f2328; }}
    .subtitle {{ font: 400 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; fill: #656d76; }}
    .language, .value {{ font: 400 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; fill: #1f2328; }}
    .track {{ fill: #eaeef2; }}
    @media (prefers-color-scheme: dark) {{
      .title, .language, .value {{ fill: #f0f6fc; }}
      .subtitle {{ fill: #8b949e; }}
      .track {{ fill: #21262d; }}
    }}
  </style>
  <text class="title" x="24" y="28">Languages by Contributed Lines</text>
  <text class="subtitle" x="24" y="48">{compact_number(total)} added lines · last 12 months · owned + collaborative repositories</text>
{''.join(rows)}
</svg>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")


def render_activity_svg(activity: dict[str, dict[str, int]], output: Path) -> None:
    entries = list(activity.items())
    total_additions = sum(values["additions"] for _, values in entries)
    total_deletions = sum(values["deletions"] for _, values in entries)
    max_additions = max((values["additions"] for _, values in entries), default=1) or 1
    max_deletions = max((values["deletions"] for _, values in entries), default=1) or 1

    width = 850
    height = 260
    baseline = 170
    chart_left = 58
    chart_width = 760
    slot = chart_width / len(entries)
    bar_width = max(4, slot - 7)
    bars: list[str] = []

    for index, (day, values) in enumerate(entries):
        x = chart_left + index * slot + (slot - bar_width) / 2
        addition_height = round(values["additions"] / max_additions * 88, 2)
        deletion_height = round(values["deletions"] / max_deletions * 34, 2)
        bars.append(
            f"""
  <g>
    <title>{day}: +{values["additions"]:,} / −{values["deletions"]:,} lines</title>
    <rect x="{x:.2f}" y="{baseline - addition_height:.2f}" width="{bar_width:.2f}" height="{addition_height:.2f}" rx="2" fill="#2da44e"/>
    <rect x="{x:.2f}" y="{baseline + 3}" width="{bar_width:.2f}" height="{deletion_height:.2f}" rx="2" fill="#cf222e"/>
  </g>"""
        )

    first_date = datetime.fromisoformat(entries[0][0]).strftime("%b %d")
    middle_date = datetime.fromisoformat(entries[len(entries) // 2][0]).strftime("%b %d")
    last_date = datetime.fromisoformat(entries[-1][0]).strftime("%b %d")
    half_max = round(max_additions / 2)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Daily Code Activity</title>
  <desc id="desc">Daily added and deleted source lines over the last 30 days</desc>
  <style>
    .title {{ font: 600 18px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; fill: #1f2328; }}
    .subtitle, .axis {{ font: 400 12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; fill: #656d76; }}
    .grid {{ stroke: #d8dee4; stroke-width: 1; }}
    @media (prefers-color-scheme: dark) {{
      .title {{ fill: #f0f6fc; }}
      .subtitle, .axis {{ fill: #8b949e; }}
      .grid {{ stroke: #30363d; }}
    }}
  </style>
  <text class="title" x="24" y="28">Daily Code Activity · Last 30 Days</text>
  <text class="subtitle" x="24" y="49">+{total_additions:,} added · −{total_deletions:,} deleted · merge commits excluded</text>
  <line class="grid" x1="{chart_left}" y1="82" x2="{chart_left + chart_width}" y2="82"/>
  <line class="grid" x1="{chart_left}" y1="126" x2="{chart_left + chart_width}" y2="126"/>
  <line class="grid" x1="{chart_left}" y1="{baseline}" x2="{chart_left + chart_width}" y2="{baseline}"/>
  <text class="axis" x="{chart_left - 9}" y="86" text-anchor="end">{max_additions:,}</text>
  <text class="axis" x="{chart_left - 9}" y="130" text-anchor="end">{half_max:,}</text>
  <text class="axis" x="{chart_left - 9}" y="{baseline + 4}" text-anchor="end">0</text>
{''.join(bars)}
  <text class="axis" x="{chart_left}" y="232">{first_date}</text>
  <text class="axis" x="{chart_left + chart_width / 2}" y="232" text-anchor="middle">{middle_date}</text>
  <text class="axis" x="{chart_left + chart_width}" y="232" text-anchor="end">{last_date}</text>
  <circle cx="655" cy="26" r="5" fill="#2da44e"/><text class="subtitle" x="665" y="30">added</text>
  <circle cx="740" cy="26" r="5" fill="#cf222e"/><text class="subtitle" x="750" y="30">deleted</text>
</svg>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")


def refresh_readme_images(readme: Path, version: str) -> None:
    content = readme.read_text(encoding="utf-8")
    updated = re.sub(
        r"(\./assets/(?:language-stats|code-activity)\.svg)(?:\?v=[^)]+)?",
        rf"\1?v={version}",
        content,
    )
    readme.write_text(updated, encoding="utf-8")


def main() -> None:
    token = os.environ["GH_TOKEN"]
    user = github_request(token, "https://api.github.com/user")
    counts, activity, commit_count = contribution_statistics(token, user["login"])
    render_language_svg(counts, Path("assets/language-stats.svg"))
    render_activity_svg(activity, Path("assets/code-activity.svg"))
    refresh_readme_images(
        Path("README.md"), datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    )
    print(
        f"Analysed {commit_count} authored commits and "
        f"{sum(counts.values()):,} contributed source lines."
    )


if __name__ == "__main__":
    main()
