"""Shared front-matter loading for the post-metadata scripts.

Imported by `prompt-context.py` and `check.py`; both declare PyYAML in their
inline script metadata, so this module can assume it is importable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CorpusError(Exception):
    """A post, or the repository itself, is not shaped the way we expect."""


@dataclass(frozen=True)
class Post:
    path: Path
    relative: str
    title: str
    description: str
    tags: tuple[str, ...]
    series: tuple[str, ...]
    draft: bool


def repository_root(start: Path) -> Path:
    """Walk up from `start` until we find the checkout containing content/posts."""
    for candidate in start.resolve().parents:
        if (candidate / "content" / "posts").is_dir():
            return candidate
    raise CorpusError("could not find a repository containing content/posts")


def _front_matter(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise CorpusError(f"{path}: missing YAML front matter")

    try:
        closing = lines.index("---", 1)
    except ValueError as error:
        raise CorpusError(f"{path}: unterminated YAML front matter") from error

    try:
        parsed = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as error:
        raise CorpusError(f"{path}: invalid YAML front matter: {error}") from error

    if not isinstance(parsed, dict):
        raise CorpusError(f"{path}: front matter must be a mapping")
    return parsed


def _string_list(metadata: dict[str, Any], field: str, path: Path) -> tuple[str, ...]:
    if field not in metadata:
        return ()

    values = metadata[field]
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        raise CorpusError(f"{path}: '{field}' must be a list of strings")

    stripped = tuple(value.strip() for value in values)
    if len(stripped) != len(set(stripped)):
        raise CorpusError(f"{path}: '{field}' contains duplicate values")
    return stripped


def _string(metadata: dict[str, Any], field: str, path: Path) -> str:
    value = metadata.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CorpusError(f"{path}: '{field}' must be a string")
    return value.strip()


def _draft(metadata: dict[str, Any], path: Path) -> bool:
    value = metadata.get("draft", False)
    if not isinstance(value, bool):
        raise CorpusError(f"{path}: 'draft' must be true or false")
    return value


def load_posts(repository: Path) -> list[Post]:
    """Every post in the checkout, in stable path order."""
    posts = repository / "content" / "posts"
    if not posts.is_dir():
        raise CorpusError(f"{repository}: content/posts does not exist")

    article_paths = sorted(posts.rglob("*.md"))
    if not article_paths:
        raise CorpusError(f"{posts}: no Markdown posts found")

    loaded = []
    for path in article_paths:
        metadata = _front_matter(path)
        loaded.append(
            Post(
                path=path,
                relative=str(path.relative_to(repository)),
                title=_string(metadata, "title", path),
                description=_string(metadata, "description", path),
                tags=_string_list(metadata, "tags", path),
                series=_string_list(metadata, "series", path),
                draft=_draft(metadata, path),
            )
        )
    return loaded
