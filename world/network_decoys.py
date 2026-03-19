"""
Decoy entries for The Network `who` output.

This module exists so staff can easily edit/add/remove the canned tags and
influence how decoys are generated, without touching command code.
"""

from __future__ import annotations

import random
import string
from typing import Iterable


# How many decoys to inject per `who`.
DECOY_COUNT_RANGE = (8, 10)

# Staff-editable canned tags (short, casual, IC-ish).
TAG_POOL: list[str] = [
    "just vibing",
    "afk 2m",
    "anyone got wheels?",
    "need a doc. asap.",
    "looking for work",
    "coffee run?",
    "don't @ me",
    "where's the party?",
    "ping me later",
    "new to town",
]


def _fallback_alias(*, max_len: int) -> str:
    # Simple username-ish fallback: letters+digits with a letter start.
    if max_len <= 1:
        return "x"
    first = random.choice(string.ascii_lowercase)
    rest = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(max_len - 1))
    return first + rest


def _fallback_tag(*, max_len: int) -> str:
    raw = random.choice(TAG_POOL) if TAG_POOL else "..."
    return raw[:max_len]


def generate_decoy_entries(
    *,
    count: int,
    id_col_width: int,
    tag_col_width: int,
    existing_aliases: Iterable[str] = (),
) -> list[tuple[str, str]]:
    """
    Generate (alias, tag) rows for `who`.

    Prefers Faker if available, otherwise uses simple fallbacks + TAG_POOL.
    """
    existing = {str(a).strip().lower() for a in existing_aliases if a}
    rows: list[tuple[str, str]] = []

    fake = None
    try:
        from faker import Faker  # type: ignore

        fake = Faker()
    except Exception:
        fake = None

    attempts = 0
    while len(rows) < max(0, int(count)) and attempts < 200:
        attempts += 1

        if fake:
            alias = str(fake.user_name() or "").strip()
            tag = str(fake.sentence() or "").strip()
        else:
            alias = _fallback_alias(max_len=max(3, min(id_col_width, 14)))
            tag = _fallback_tag(max_len=tag_col_width)

        alias = alias.replace("\r", "").replace("\n", "").strip()
        tag = tag.replace("\r", " ").replace("\n", " ").strip()

        if not alias:
            continue

        alias = alias[:id_col_width]
        tag = tag[:tag_col_width]

        key = alias.lower()
        if key in existing:
            continue

        existing.add(key)
        rows.append((alias, tag))

    # If we couldn't generate enough distinct ones, pad with fallbacks.
    while len(rows) < max(0, int(count)):
        alias = _fallback_alias(max_len=max(3, min(id_col_width, 14)))[:id_col_width]
        key = alias.lower()
        if key in existing:
            continue
        existing.add(key)
        rows.append((alias, _fallback_tag(max_len=tag_col_width)))

    return rows

