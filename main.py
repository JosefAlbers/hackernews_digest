import asyncio
import html
import json
import re
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from mlx_code.mcb import KB
from mlx_code.repl import Agent

def extract_show_hn_from_soup(soup, show_hn):
    show_hn_ids = []
    show_hn_titles = []
    post_rows = soup.find_all("tr", class_="athing")
    for row in post_rows:
        post_id = row.get("id")
        if not post_id:
            continue
        title_span = row.find("span", class_="titleline")
        if title_span:
            title_link = title_span.find("a")
            if title_link:
                title_text = title_link.get_text().strip()
                if title_text.lower().startswith("show hn:") or not show_hn:
                    show_hn_ids.append(int(post_id))
                    show_hn_titles.append(title_text)
    return (show_hn_ids, show_hn_titles)


def get_hn_post_ids_for_date(date_str, max_pages=2, show_hn=True):
    base_url = "https://news.ycombinator.com/"
    current_url = f"{base_url}front?day={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    all_show_hn_ids = []
    all_show_hn_titles = []
    pages_crawled = 0
    while current_url and pages_crawled < max_pages:
        print(f"Fetching: {current_url}")
        try:
            response = requests.get(current_url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            page_ids, page_titles = extract_show_hn_from_soup(soup, show_hn=show_hn)
            all_show_hn_ids.extend(page_ids)
            all_show_hn_titles.extend(page_titles)
            pages_crawled += 1
            more_link_element = soup.find("a", class_="morelink")
            if more_link_element and max_pages > pages_crawled:
                href = more_link_element.get("href")
                current_url = urljoin(base_url, href)
            else:
                current_url = None
        except requests.exceptions.RequestException as e:
            print(f"An error occurred on page {pages_crawled + 1}: {e}")
            break
    return all_show_hn_ids


def clean_text(text: str) -> str:
    if not text:
        return text
    text = re.sub("</?p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub("<br\\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = html.unescape(text)
    text = re.sub("\\n\\s*\\n", "\n\n", text)
    text = text.strip()
    return text


def fetch_item(item_id: int, session: requests.Session) -> dict:
    base_url = "https://hacker-news.firebaseio.com/v0/item/{}.json"
    resp = session.get(base_url.format(item_id))
    resp.raise_for_status()
    return resp.json()


def get_hackernews_comments(url: str | int) -> List[Dict]:
    print(f"url={url!r}")
    if isinstance(url, str):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "id" not in query:
            raise ValueError("URL does not contain an 'id' parameter")
        root_id = int(query["id"][0])
    elif isinstance(url, int):
        root_id = url
    session = requests.Session()
    session.headers.update({"User-Agent": "hn-comment-fetcher/1.0"})
    visited = set()
    stack = [root_id]
    items_by_id = {}
    while stack:
        item_id = stack.pop()
        if item_id in visited:
            continue
        visited.add(item_id)
        item = fetch_item(item_id, session)
        items_by_id[item_id] = item
        for kid_id in item.get("kids", []):
            if kid_id not in visited:
                stack.append(kid_id)
    result = {}
    title = ""
    url_str = ""
    for item_id, item in items_by_id.items():
        if item.get("type") == "story":
            title = item.get("title", "")
            url_str = item.get("url")
            titleline = f"[{title}]({url_str})" if url_str else title
            content = (
                f"# {titleline}\n\n{item.get('text')}"
                if item.get("text")
                else titleline
            )
        else:
            content = (
                item.get("text", "[deleted]")
                if not item.get("deleted")
                else f"[deleted]"
            )
        parent = item.get("parent", None)
        children = item.get("kids", [])
        result[item_id] = {
            "id": item_id,
            "parent": parent,
            "children": children,
            "content": clean_text(content),
        }
    return (result, title, url_str)




async def summarize(pp):
    agent = Agent(
        system='Summarize the following thread.',
        tool_names=[], 
        api = 'gemini', 
        api_key = os.environ.get("GEMINI_API_KEY"), 
        base_url = "https://generativelanguage.googleapis.com", 
        model = "gemini-3.1-flash-lite",
    )
    result = await agent.run(pp)
    result = "\n".join(
        [i.get("text", "") for i in result["content"] if i.get("type") == "text"]
    )
    return result


def update_dates_json(date_str):
    path = Path("data/dates.json")
    if path.exists():
        dates = json.loads(path.read_text(encoding="utf-8"))
    else:
        dates = []
    if date_str not in dates:
        dates.append(date_str)
    dates.sort(reverse=True)
    path.write_text(json.dumps(dates, indent=2), encoding="utf-8")


def main(target_date):
    outdir = Path("data")
    outdir.mkdir(exist_ok=True)
    outfile = outdir / f"posts_{target_date}.json"
    if outfile.exists():
        print(f"{outfile} already exists")
        return
    kb = KB(db_path=f"{target_date}.json")
    lod = []
    for item_id in get_hn_post_ids_for_date(target_date):
        thread, title, project_url = get_hackernews_comments(item_id)
        kb.db |= thread
        summary = asyncio.run(summarize(kb.get_branch(item_id)))
        lod.append(
            {
                "item_id": item_id,
                "date": target_date,
                "title": title,
                "project_url": project_url,
                "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
                "content": summary.strip(),
            }
        )
    outfile.write_text(json.dumps(lod, indent=2), encoding="utf-8")
    update_dates_json(target_date)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = (date.today() - timedelta(days=2)).isoformat()
    main(target_date)
