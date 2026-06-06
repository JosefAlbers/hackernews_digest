import asyncio
import json
import os
import sys
from pathlib import Path

from mlx_code.repl import Agent

LANGUAGES = {
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
}

MODEL = "gemini-3.1-flash-lite"


def make_agent():
    return Agent(
        system=(
            "You are a translation engine. "
            "You will receive a JSON object with 'title' and 'content' fields. "
            "Translate both values into the requested language. "
            "Preserve all markdown formatting in 'content' exactly. "
            "Return ONLY the translated JSON object with the same two keys. "
            "No explanation, no markdown fences, no preamble."
        ),
        tool_names=[],
        api="gemini",
        api_key=os.environ["GEMINI_API_KEY"],
        base_url="https://generativelanguage.googleapis.com",
        model=MODEL,
    )


def extract_raw(result) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        return "\n".join(
            i.get("text", "") for i in result.get("content", []) if i.get("type") == "text"
        ).strip()
    return str(result).strip()


def strip_fences(raw: str) -> str:
    if raw.startswith("```"):
        lines = raw.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[1:end])
    return raw.strip()


async def translate_post(post: dict, lang_name: str) -> dict:
    payload = {"title": post["title"], "content": post["content"]}
    agent = make_agent()
    result = await agent.run(
        f"Translate the following JSON object to {lang_name}.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    raw = strip_fences(extract_raw(result))
    try:
        translated = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  Parse failed for item {post['item_id']}: {e} — keeping original")
        return post 
    return {**post, "title": translated["title"], "content": translated["content"]}


async def translate_posts(posts: list[dict], lang_name: str) -> list[dict]:
    results = []
    for i, post in enumerate(posts, 1):
        print(f"  [{i}/{len(posts)}] {post['title'][:60]}")
        results.append(await translate_post(post, lang_name))
    return results


def translate_date(date_str: str, lang_code: str) -> bool:
    src = Path(f"data/posts_{date_str}.json")
    dst = Path(f"data/posts_{date_str}_{lang_code}.json")

    if not src.exists():
        print(f"Source not found: {src}")
        return False

    if dst.exists():
        print(f"Already exists, skipping: {dst}")
        return True

    posts = json.loads(src.read_text(encoding="utf-8"))
    lang_name = LANGUAGES[lang_code]

    print(f"Translating {len(posts)} posts to {lang_name} ...")
    translated = asyncio.run(translate_posts(posts, lang_name))

    dst.write_text(json.dumps(translated, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {dst}")
    return True


def translate_all_languages(date_str: str):
    for lang_code in LANGUAGES:
        try:
            translate_date(date_str, lang_code)
        except Exception as e:
            print(f"Failed to translate {date_str} to {lang_code}: {e}")


if __name__ == "__main__":
    from datetime import date, timedelta

    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = (date.today() - timedelta(days=2)).isoformat()

    if len(sys.argv) > 2:
        lang = sys.argv[2]
        if lang not in LANGUAGES:
            print(f"Unknown language: {lang}. Choose from: {list(LANGUAGES)}")
            sys.exit(1)
        translate_date(target_date, lang)
    else:
        translate_all_languages(target_date)
