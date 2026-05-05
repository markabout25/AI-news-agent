import os
import feedparser
import anthropic
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sources import SOURCES


def fetch_recent_articles(sources, hours=48):
    """Fetch articles published in the last N hours from all sources."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source in sources:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if published and published >= cutoff:
                    articles.append({
                        "source": source["name"],
                        "title": entry.get("title", "Untitled"),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", entry.get("description", "")),
                        "published": published.strftime("%Y-%m-%d"),
                    })
        except Exception as e:
            print(f"Error fetching {source['name']}: {e}")

    return articles


def summarize_with_claude(articles):
    """Use Claude to generate a structured digest from the articles."""
    if not articles:
        return "No new articles found in the last 48 hours."

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    articles_text = "\n\n".join([
        f"**{a['source']}** — {a['published']}\n"
        f"Title: {a['title']}\n"
        f"URL: {a['link']}\n"
        f"Summary: {a['summary'][:600]}"
        for a in articles
    ])

    prompt = f"""You are an AI research analyst. Below are recent articles from top AI newsletters \
and blogs published in the last 48 hours.

{articles_text}

Create a structured digest with these exact sections:

## Key Themes
2-3 sentences on what the AI world is focused on right now.

## Top Stories
The 5 most important articles. For each: title as a markdown link, source, date, and a 2-3 sentence summary.

## Quick Hits
Brief bullet points for remaining notable articles (title as link + one sentence).

## Takeaway
1-2 sentence editorial on the single most significant development this cycle.

Be concise, insightful, and prioritize signal over noise."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def save_digest(content):
    """Save the digest as a markdown file in summaries/."""
    summaries_dir = Path("summaries")
    summaries_dir.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = summaries_dir / f"{date_str}.md"

    header = f"# AI News Digest — {date_str}\n\n"
    filepath.write_text(header + content, encoding="utf-8")
    print(f"Digest saved to {filepath}")
    return str(filepath)


if __name__ == "__main__":
    print("Fetching recent AI articles...")
    articles = fetch_recent_articles(SOURCES)
    print(f"Found {len(articles)} articles from the last 48 hours.")

    print("Generating summary with Claude...")
    digest = summarize_with_claude(articles)

    save_digest(digest)
    print("Done.")
