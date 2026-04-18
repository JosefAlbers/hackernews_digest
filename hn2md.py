#!/usr/bin/env python3
"""
Hacker News front page scraper.
Fetches posts from https://news.ycombinator.com/news and exports each as a .md file,
including the full comment thread.

Usage:
    python hn2md.py                    # scrape page 1
    python hn2md.py --pages 3          # scrape pages 1–3
    python hn2md.py --out ./hn_posts   # custom output directory
"""

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run:\n  pip install requests beautifulsoup4")
    sys.exit(1)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; hn2md/1.0)"
}


def slugify(text: str) -> str:
    """Convert a title to a safe filename slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text[:80]


def html_to_text(element) -> str:
    """Convert comment HTML to plain text, preserving paragraphs and code blocks."""
    if element is None:
        return ""

    parts = []
    for node in element.children:
        if isinstance(node, str):
            parts.append(node)
        elif node.name == "p":
            parts.append("\n\n" + node.get_text())
        elif node.name in ("pre", "code"):
            code = node.get_text()
            indented = "\n".join("    " + line for line in code.splitlines())
            parts.append("\n\n" + indented)
        elif node.name == "a":
            href = node.get("href", "")
            text = node.get_text(strip=True)
            parts.append(f"[{text}]({href})" if href else text)
        elif node.name == "i":
            parts.append(f"*{node.get_text()}*")
        else:
            parts.append(node.get_text())

    return "".join(parts).strip()


def fetch_comments(item_id: str) -> list[dict]:
    """
    Fetch the comment thread for a post and return a flat list of comment dicts,
    each with a 'depth' level indicating nesting.
    """
    url = f"https://news.ycombinator.com/item?id={item_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    comments = []

    for row in soup.select("tr.athing.comtr"):
        # Depth is encoded as the width of the indent image (40px per level)
        indent_img = row.select_one("td.ind img")
        depth = 0
        if indent_img and indent_img.get("width"):
            try:
                depth = int(indent_img["width"]) // 40
            except ValueError:
                pass

        author_a = row.select_one("a.hnuser")
        author = author_a.get_text(strip=True) if author_a else "[deleted]"

        age_span = row.select_one("span.age")
        age = age_span.get("title", age_span.get_text(strip=True)) if age_span else ""

        # HN renders comment text in a div with class "commtext" (may also have c00/cF etc.)
        comment_div = row.select_one("div.commtext")
        if comment_div is None:
            text = "*[comment deleted or collapsed]*"
        else:
            text = html_to_text(comment_div)

        comments.append({
            "author": author,
            "age": age,
            "depth": depth,
            "text": text,
        })

    return comments


def fetch_page(page: int) -> list[dict]:
    """Scrape a single HN news page and return a list of post dicts."""
    url = f"https://news.ycombinator.com/news?p={page}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = []

    for row in soup.select("tr.athing"):
        post_id = row.get("id", "")

        title_cell = row.select_one("span.titleline")
        if not title_cell:
            continue
        anchor = title_cell.find("a")
        if not anchor:
            continue
        title = anchor.get_text(strip=True)
        link = anchor.get("href", "")
        if link.startswith("item?id="):
            link = "https://news.ycombinator.com/" + link

        sitebit = title_cell.select_one("span.sitestr")
        domain = sitebit.get_text(strip=True) if sitebit else ""

        subtext = row.find_next_sibling("tr")
        points, author, age, comment_count, comments_url = "", "", "", "", ""
        if subtext:
            score_span = subtext.select_one("span.score")
            if score_span:
                points = score_span.get_text(strip=True)

            user_a = subtext.select_one("a.hnuser")
            if user_a:
                author = user_a.get_text(strip=True)

            age_span = subtext.select_one("span.age")
            if age_span:
                age = age_span.get("title", age_span.get_text(strip=True))

            subtext_links = subtext.select("a")
            if subtext_links:
                last_a = subtext_links[-1]
                text = last_a.get_text(strip=True)
                if "comment" in text or text == "discuss":
                    comment_count = text
                    href = last_a.get("href", "")
                    if href:
                        comments_url = "https://news.ycombinator.com/" + href

        posts.append({
            "id": post_id,
            "title": title,
            "link": link,
            "domain": domain,
            "points": points,
            "author": author,
            "age": age,
            "comment_count": comment_count,
            "comments_url": comments_url,
        })

    return posts


def comments_to_markdown(comments: list[dict]) -> str:
    """Render a flat comment list as indented markdown, using > blockquotes for depth."""
    lines = []
    for c in comments:
        prefix = "  " * c["depth"]
        header = f"{prefix}**{c['author']}**"
        if c["age"]:
            header += f" · *{c['age']}*"
        lines.append(header)
        lines.append("")
        for body_line in c["text"].splitlines():
            lines.append(prefix + body_line if body_line.strip() else "")
        lines.append("")
    return "\n".join(lines)


def post_to_markdown(post: dict, comments: list[dict], scraped_at: str) -> str:
    """Render a post and its comments as a markdown string."""
    lines = [
        f"# {post['title']}",
        "",
        f"**URL:** <{post['link']}>  ",
    ]
    if post["domain"]:
        lines.append(f"**Domain:** {post['domain']}  ")
    if post["points"]:
        lines.append(f"**Points:** {post['points']}  ")
    if post["author"]:
        lines.append(f"**Author:** [{post['author']}](https://news.ycombinator.com/user?id={post['author']})  ")
    if post["age"]:
        lines.append(f"**Posted:** {post['age']}  ")
    if post["comment_count"] and post["comments_url"]:
        lines.append(f"**Discussion:** [{post['comment_count']}]({post['comments_url']})  ")

    lines += ["", "---", ""]

    if comments:
        lines.append(f"## Comments ({len(comments)})")
        lines.append("")
        lines.append(comments_to_markdown(comments))
    else:
        lines.append("*No comments yet.*")

    lines += [
        "",
        "---",
        "",
        f"*Scraped from [Hacker News](https://news.ycombinator.com) on {scraped_at}*",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Scrape HN front page posts + comments to markdown files.")
    parser.add_argument("--pages", type=int, default=1, help="Number of listing pages to scrape (default: 1)")
    parser.add_argument("--out", type=str, default="hn_posts", help="Output directory (default: hn_posts)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = 0

    for page in range(1, args.pages + 1):
        print(f"Fetching page {page}...")
        try:
            posts = fetch_page(page)
        except requests.RequestException as e:
            print(f"  Error fetching page {page}: {e}")
            continue

        for i, post in enumerate(posts, start=1):
            comments = []
            if post["id"]:
                try:
                    comments = fetch_comments(post["id"])
                except requests.RequestException as e:
                    print(f"    Warning: could not fetch comments for '{post['title']}': {e}")
                time.sleep(0.5)  # be polite between comment page requests

            md = post_to_markdown(post, comments, scraped_at)
            slug = slugify(post["title"]) or post["id"]
            filename = out_dir / f"{slug}.md"
            if filename.exists():
                filename = out_dir / f"{slug}-{post['id']}.md"

            filename.write_text(md, encoding="utf-8")
            print(f"  [{i:2d}] {filename.name}  ({len(comments)} comments)")
            total += 1

        if page < args.pages:
            time.sleep(1)

    print(f"\nDone — {total} posts saved to '{out_dir}/'")


if __name__ == "__main__":
    main()
