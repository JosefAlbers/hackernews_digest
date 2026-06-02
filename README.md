# hn2mc

A static Hacker News digest generated from discussion threads and hosted on [GitHub Pages](https://josefalbers.github.io/hn2mc).

## What it does

For each day:

1. Fetches front-page Hacker News stories.
2. Downloads the full comment thread for each story.
3. Uses an LLM to generate a concise summary of the discussion.
4. Saves the results as JSON files.
5. Publishes everything as a static website via GitHub Pages.

The site can be browsed by date and each summary links to both the original article and the Hacker News discussion.

## Example

For a story like:

> Show HN: VimLM – A Local, Offline Coding Assistant for Vim

hn2mc will:

* fetch the submission
* fetch all comments
* summarize the discussion
* store the result as structured JSON

and make it available through the website.

## Repository Structure

```text
.
├── data/
│   ├── dates.json
│   ├── posts_2025-05-30.json
│   └── posts_2025-05-31.json
├── index.html
├── main.py
└── .github/
    └── workflows/
        └── update.yml
```

## Running Locally

Install dependencies:

```bash
pip install requests beautifulsoup4 mlx-code
```

Generate summaries for a specific date:

```bash
python main.py 2025-02-15
```

Generate summaries for two days ago:

```bash
python main.py
```

Serve the website locally:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

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

## Automation

A GitHub Actions workflow runs daily and:

1. Generates a new digest.
2. Updates the data files.
3. Commits the changes back to the repository.

The website is automatically served through GitHub Pages.

## Why?

Reading Hacker News comments is often more valuable than reading the article itself, but following every discussion is impossible.

hn2mc turns long comment threads into concise daily digests that can be browsed later.
