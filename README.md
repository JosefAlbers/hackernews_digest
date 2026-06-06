# hackernews digest

A static Hacker News digest generated from discussion threads and hosted on [GitHub Pages](https://josefalbers.github.io/hackernews_digest).

## What it does

For each day:

1. Fetches Show HN stories from Hacker News.
2. Downloads the full comment thread for each story.
3. Uses an LLM to generate a concise summary of the discussion.
4. Translates each summary into German, Japanese, and Korean.
5. Saves everything as JSON files.
6. Publishes a static website via GitHub Pages.

The site auto-detects your browser language and falls back to English if a translation is unavailable. You can also switch languages manually from any page.

## Example

For a story like:

> Show HN: VimLM – A Local, Offline Coding Assistant for Vim

the digest will fetch the submission and all comments, summarize the discussion, translate it, and make it available through the website.

## Repository Structure

```text
.
├── data/
│   ├── dates.json
│   ├── posts_2025-05-30.json
│   ├── posts_2025-05-30_de.json
│   ├── posts_2025-05-30_ja.json
│   ├── posts_2025-05-30_ko.json
│   └── ...
├── index.html
├── main.py
├── translate.py
└── .github/
    └── workflows/
        └── update.yml
```

## Running Locally

Install dependencies:

```bash
pip install requests beautifulsoup4 mlx-code
```

Set your Gemini API key:

```bash
export GEMINI_API_KEY=your_key_here
```

Generate summaries and translations for a specific date:

```bash
python main.py 2025-02-15
```

Or for two days ago (the default):

```bash
python main.py
```

To run only the translation pass on already-generated data:

```bash
python translate.py 2025-02-15           # all languages
python translate.py 2025-02-15 ja        # one language
```

Serve the website locally:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000`.

## Data Format

Each generated file contains a list of posts:

```json
{
  "item_id": 43054244,
  "date": "2025-02-15",
  "title": "Show HN: VimLM – A Local, Offline Coding Assistant for Vim",
  "project_url": "https://github.com/JosefAlbers/VimLM",
  "hn_url": "https://news.ycombinator.com/item?id=43054244",
  "content": "Summary of the discussion..."
}
```

Translated files (`posts_<date>_<lang>.json`) have the same structure with `title` and `content` replaced by the translated versions.

## Automation

A GitHub Actions workflow runs daily at 03:00 UTC and:

1. Generates a new digest for the previous day.
2. Translates it into all configured languages.
3. Commits the updated data files back to the repository.

The website is automatically served through GitHub Pages.

## Why?

Reading Hacker News comments is often more valuable than reading the article itself, but following every discussion is impossible. This turns long comment threads into concise daily digests you can browse later, in your own language.

## License

MIT
