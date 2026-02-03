#!/usr/bin/env python3
"""Fetch 2018+ publications from Google Scholar and update papers/index.html."""
from __future__ import annotations

import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import requests
from bs4 import BeautifulSoup

SCHOLAR_BASE = (
    "https://scholar.google.com/citations?hl=en&user=O8wbTncAAAAJ"
    "&view_op=list_works&sortby=pubdate"
)
START_YEAR = 2018
PAPERS_INDEX = Path(__file__).resolve().parents[1] / "papers" / "index.html"
MARKER_START = "<!-- AUTO-GENERATED PUBLICATIONS START -->"
MARKER_END = "<!-- AUTO-GENERATED PUBLICATIONS END -->"


@dataclass
class Publication:
    year: int
    title: str
    link: str
    venue: str


def fetch_page(cstart: int) -> BeautifulSoup:
    url = f"{SCHOLAR_BASE}&cstart={cstart}&pagesize=20"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_rows(soup: BeautifulSoup) -> List[Publication]:
    publications: List[Publication] = []
    for row in soup.select("tr.gsc_a_tr"):
        year_span = row.select_one("td.gsc_a_y span")
        if not year_span:
            continue
        year_text = year_span.text.strip()
        if not year_text.isdigit():
            continue
        year = int(year_text)
        if year < START_YEAR:
            break
        link_tag = row.select_one("a.gsc_a_at")
        if not link_tag:
            continue
        title = link_tag.text.strip()
        link = "https://scholar.google.com" + link_tag.get("href", "")
        detail_lines = row.select("div.gs_gray")
        venue = detail_lines[1].text.strip() if len(detail_lines) > 1 else ""
        publications.append(Publication(year=year, title=title, link=link, venue=venue))
    return publications


def fetch_publications() -> List[Publication]:
    all_pubs: List[Publication] = []
    cstart = 0
    while True:
        soup = fetch_page(cstart)
        pubs = parse_rows(soup)
        if not pubs:
            break
        all_pubs.extend(pubs)
        last_year = pubs[-1].year
        if last_year < START_YEAR:
            break
        cstart += 20
    return all_pubs


def chunk(items: List[Publication], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_html(pubs: List[Publication]) -> str:
    by_year: Dict[int, List[Publication]] = {}
    for pub in pubs:
        by_year.setdefault(pub.year, []).append(pub)
    parts: List[str] = [MARKER_START]
    for year in sorted(by_year.keys(), reverse=True):
        parts.append(f"  <div class=\"bigtitle\">{year}</div>")
        parts.append("  <div class=\"spacer\"></div>")
        for group in chunk(by_year[year], 3):
            parts.append("  <div class=\"row\">")
            for pub in group:
                title = html.escape(pub.title)
                venue = html.escape(pub.venue or "")
                link = html.escape(pub.link)
                parts.append(
                    "      <div class=\"col-md-4 paperbox\">\n"
                    "        <div class=\"media\">\n"
                    "          <div class=\"media-body\">\n"
                    "            <div class=\"smallhead media-heading\">\n"
                    f"              <a href=\"{link}\" class=\"off\">{title}</a>\n"
                    "            </div>\n"
                    f"            <p class=\"note\"><i>{venue}</i></p>\n"
                    "          </div>\n"
                    "        </div>\n"
                    "      <div class=\"bigspacer\"></div><div class=\"spacer\"></div>\n"
                    "      </div>"
                )
            parts.append("  </div>")
            parts.append("")
    parts.append(MARKER_END)
    parts.append("")
    return "\n".join(parts)


def inject_html(existing: str, new_block: str) -> str:
    if MARKER_START in existing and MARKER_END in existing:
        start = existing.index(MARKER_START)
        end = existing.index(MARKER_END) + len(MARKER_END)
        return existing[:start] + new_block + existing[end:]
    anchor = '  <div class="bigtitle">2017</div>'
    if anchor not in existing:
        raise SystemExit("Could not find insertion anchor in papers/index.html")
    idx = existing.index(anchor)
    return existing[:idx] + new_block + "\n" + existing[idx:]


def main() -> int:
    pubs = fetch_publications()
    if not pubs:
        print("No publications fetched.")
        return 1
    html_block = build_html(pubs)
    current = PAPERS_INDEX.read_text()
    updated = inject_html(current, html_block)
    PAPERS_INDEX.write_text(updated)
    print(f"Inserted {len(pubs)} publications (>= {START_YEAR}) into {PAPERS_INDEX}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
