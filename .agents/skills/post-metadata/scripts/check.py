#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "PyYAML==6.0.3",
# ]
# ///
"""Verify post `description` and `tags` metadata against the rules in this skill.

Run it after every batch, before showing the batch to the user. Errors are
objective rule violations; warnings are heuristics that need a human to read
the value and decide. Exits non-zero when any error is found (or any warning,
with --strict).
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import sys

from _corpus import CorpusError, Post, load_posts, repository_root

MIN_LENGTH = 120
MAX_LENGTH = 155
MAX_TAGS = 3

NEAR_DUPLICATE_RATIO = 0.85

# Phrasing the descriptions reference rules out. Warnings, not errors: an
# occasional one is defensible, a batch full of them is drift.
BANNED_PHRASING = [
    r"\bdive[sd]? into\b",
    r"\bexplor(e|es|ing)\b",
    r"\bunpack(s|ing)?\b",
    r"\bdelv(e|es|ing)\b",
    r"\bcomprehensive guide\b",
    r"\beverything you need to know\b",
    r"\bin this post,? we'?ll\b",
    r"\bsecret sauce\b",
    r"\bliving, breathing\b",
    r"\bcrucial\b",
    r"\bessence\b",
    r"\bseamless(ly)?\b",
    r"\bleverag(e|es|ing)\b",
    r"\butili[sz](e|es|ing)\b",
]

MARKDOWN = [
    (r"`", "backtick"),
    (r"\*\*", "bold markers"),
    (r"\[[^\]]*\]\([^)]*\)", "markdown link"),
]

EMOJI = re.compile(
    "[\U0001f000-\U0001faff☀-➿⬀-⯿️]"
)

TITLE_STOPWORDS = {
    "a", "an", "and", "are", "for", "from", "how", "into", "isnt", "its",
    "not", "our", "own", "that", "the", "them", "then", "this", "to", "was",
    "what", "when", "why", "with", "you", "your",
}


@dataclass(frozen=True)
class Finding:
    level: str
    where: str
    message: str


def word_set(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return {word for word in words if len(word) > 3 and word not in TITLE_STOPWORDS}


def canonical_key(tag: str) -> str:
    """Fold spelling variants that would split one archive into two."""
    key = re.sub(r"[^a-z0-9]+", "", tag.casefold())
    return key[:-1] if key.endswith("s") and len(key) > 3 else key


def check_description(post: Post, *, selected: bool) -> list[Finding]:
    findings: list[Finding] = []
    description = post.description
    if not description:
        # Backfilling the whole archive is its own job. Only nag about a missing
        # description when this post was named on the command line.
        if not selected:
            return []
        return [Finding("warn", post.relative, "no description; falls back to .Summary")]

    length = len(description)
    if length > MAX_LENGTH:
        findings.append(
            Finding(
                "error",
                post.relative,
                f"description is {length} characters; Google cuts at ~{MAX_LENGTH}",
            )
        )
    elif length < MIN_LENGTH:
        findings.append(
            Finding(
                "warn",
                post.relative,
                f"description is {length} characters; target is {MIN_LENGTH}-{MAX_LENGTH}",
            )
        )

    if description.endswith(("...", "…")):
        findings.append(Finding("error", post.relative, "description trails off"))
    elif not description.endswith((".", "!", "?")):
        findings.append(
            Finding("error", post.relative, "description is a fragment; end the sentence")
        )

    if description[0] in "\"'“":
        findings.append(Finding("error", post.relative, "description is quoted"))

    for pattern, label in MARKDOWN:
        if re.search(pattern, description):
            findings.append(
                Finding("error", post.relative, f"description contains {label}; use plain text")
            )

    if EMOJI.search(description):
        findings.append(Finding("error", post.relative, "description contains emoji"))

    for pattern in BANNED_PHRASING:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            findings.append(
                Finding("warn", post.relative, f"banned phrasing: {match.group(0)!r}")
            )

    shared = word_set(post.title) & word_set(description)
    if len(shared) >= 3:
        findings.append(
            Finding(
                "warn",
                post.relative,
                f"description repeats the title: {', '.join(sorted(shared))}",
            )
        )

    return findings


def check_tags(post: Post, series_keys: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    if not post.tags:
        findings.append(Finding("error", post.relative, "no tags"))
    elif len(post.tags) > MAX_TAGS:
        findings.append(
            Finding(
                "error",
                post.relative,
                f"{len(post.tags)} tags; the limit is {MAX_TAGS}",
            )
        )

    for tag in post.tags:
        series = series_keys.get(canonical_key(tag))
        if series:
            findings.append(
                Finding(
                    "error",
                    post.relative,
                    f"tag {tag!r} names the {series!r} series; use the series taxonomy",
                )
            )

    return findings


def check_corpus(posts: list[Post]) -> list[Finding]:
    """Checks that only make sense across the whole archive."""
    findings: list[Finding] = []

    spellings: defaultdict[str, set[str]] = defaultdict(set)
    for post in posts:
        for tag in post.tags:
            spellings[canonical_key(tag)].add(tag)
    for variants in spellings.values():
        if len(variants) > 1:
            findings.append(
                Finding(
                    "error",
                    "corpus",
                    "tag spelling collision splits one archive: "
                    + ", ".join(sorted(repr(v) for v in variants)),
                )
            )

    described = [post for post in posts if post.description]
    by_description: defaultdict[str, list[str]] = defaultdict(list)
    for post in described:
        by_description[post.description.casefold()].append(post.relative)
    for paths in by_description.values():
        if len(paths) > 1:
            findings.append(
                Finding("error", "corpus", "identical descriptions: " + ", ".join(paths))
            )

    for index, post in enumerate(described):
        for other in described[index + 1 :]:
            ratio = SequenceMatcher(
                None, post.description.casefold(), other.description.casefold()
            ).ratio()
            if NEAR_DUPLICATE_RATIO <= ratio < 1.0:
                findings.append(
                    Finding(
                        "warn",
                        "corpus",
                        f"descriptions {ratio:.0%} similar: {post.relative}, {other.relative}",
                    )
                )

    return findings


def summary(posts: list[Post]) -> list[str]:
    tags: Counter[str] = Counter()
    for post in posts:
        tags.update(post.tags)
    described = sum(1 for post in posts if post.description)
    return [
        f"posts: {len(posts)} ({described} with a description, "
        f"{len(posts) - described} falling back to .Summary)",
        f"tag assignments: {sum(tags.values())}",
        f"unique tags: {len(tags)}",
        f"one-article tags: {sum(1 for count in tags.values() if count == 1)}",
        f"most tags on one article: {max((len(p.tags) for p in posts), default=0)}",
    ]


def select(posts: list[Post], repository: Path, paths: list[Path]) -> list[Post]:
    if not paths:
        return posts

    wanted = {path.resolve() for path in paths}
    unknown = wanted - {post.path.resolve() for post in posts}
    if unknown:
        raise CorpusError(
            "not posts in this repository: "
            + ", ".join(sorted(str(path) for path in unknown))
        )
    return [post for post in posts if post.path.resolve() in wanted]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check post descriptions and tags against the post-metadata rules.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Posts to check; defaults to every post. Corpus-wide checks always "
        "run over the whole archive.",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        help="Repository root; defaults to the repository containing this script.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as errors.",
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
        posts = load_posts(root)
        batch = select(posts, root, args.paths)
    except (CorpusError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    series_keys = {
        canonical_key(name): name for post in posts for name in post.series
    }

    findings: list[Finding] = []
    for post in batch:
        findings.extend(check_description(post, selected=bool(args.paths)))
        findings.extend(check_tags(post, series_keys))
    findings.extend(check_corpus(posts))

    for line in summary(posts):
        print(line)
    print()

    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warn"]
    for finding in errors + warnings:
        print(f"{finding.level:>5}: {finding.where}: {finding.message}")
    if not findings:
        print("no findings")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    print("Metrics diagnose drift; they do not decide relevance. Read the outliers.")

    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
