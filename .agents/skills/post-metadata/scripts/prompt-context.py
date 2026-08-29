#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "PyYAML==6.0.3",
# ]
# ///
"""Render the prompt-ready tag vocabulary and series context for sub-agents."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

from _corpus import CorpusError, Post, load_posts, repository_root


def render_section(
    title: str,
    published: Counter[str],
    drafts: Counter[str],
) -> list[str]:
    lines = [f"## {title}", ""]
    names = sorted(published.keys() | drafts.keys(), key=str.casefold)
    if not names:
        return [*lines, "- (none)"]

    for name in names:
        published_label = "article" if published[name] == 1 else "articles"
        draft_label = "article" if drafts[name] == 1 else "articles"
        lines.append(
            f"- `{name}` — {published[name]} published {published_label}, "
            f"{drafts[name]} draft {draft_label}"
        )
    return lines


def tally(posts: list[Post], field: str) -> tuple[Counter[str], Counter[str]]:
    published: Counter[str] = Counter()
    drafts: Counter[str] = Counter()
    for post in posts:
        (drafts if post.draft else published).update(getattr(post, field))
    return published, drafts


def prompt_context(repository: Path) -> str:
    posts = load_posts(repository)
    published_tags, draft_tags = tally(posts, "tags")
    published_series, draft_series = tally(posts, "series")

    lines = render_section("Canonical vocabulary", published_tags, draft_tags)
    lines.append("")
    lines.extend(render_section("Known series", published_series, draft_series))
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render prompt-ready tag vocabulary and series context.",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        help="Repository root; defaults to the repository containing this script.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = (
            args.repository.resolve()
            if args.repository
            else repository_root(Path(__file__))
        )
        sys.stdout.write(prompt_context(root))
    except (CorpusError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
