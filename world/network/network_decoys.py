import random
import string
import os
import markovify
from typing import Iterable
from django.conf import settings

# --- NEW: Markovify Setup ---

def _get_markov_model():
    """Builds the combined brain from your two corpus files."""
    try:
        path_a = os.path.join(settings.GAME_DIR, "world", "network", "corpusa.txt")
        path_b = os.path.join(settings.GAME_DIR, "world", "network", "corpusb.txt")
        path_c = os.path.join(settings.GAME_DIR, "world", "network", "corpusc.txt")

        with open(path_a, "r", encoding="utf-8", errors="ignore") as f:
                model_a = markovify.Text(f.read(), state_size=2)
        with open(path_a, "r", encoding="utf-8", errors="ignore") as f:
            model_b = markovify.Text(f.read(), state_size=2)
        with open(path_c, "r", encoding="utf-8", errors="ignore") as f:
            model_c = markovify.Text(f.read(), state_size=2)

        # Mix: 1.0 weight for A, 0.7 for B (tweak as you like!)
        combined = markovify.combine([model_a, model_b, model_c], [0.4, 0.7, 1.0])
        combined.compile(inplace=True)
        return combined
    except Exception:
        return None

# Load the brain once so it stays in memory
_MARKOV_BRAIN = _get_markov_model()

# --- Your Existing Config ---

DECOY_COUNT_RANGE = (8, 10)

TAG_POOL: list[str] = [
    "just vibing", "afk 2m", "anyone got wheels?", "need a doc. asap.",
    "looking for work", "coffee run?", "don't @ me", "where's the party?",
]

def _fallback_alias(*, max_len: int) -> str:
    if max_len <= 1: return "x"
    first = random.choice(string.ascii_lowercase)
    rest = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(max_len - 1))
    return first + rest

def _fallback_tag(*, max_len: int) -> str:
    raw = random.choice(TAG_POOL) if TAG_POOL else "..."
    return raw[:max_len]

# --- The Main Function ---

def generate_decoy_entries(
    *,
    count: int,
    id_col_width: int,
    tag_col_width: int,
    existing_aliases: Iterable[str] = (),
) -> list[tuple[str, str]]:
    existing = {str(a).strip().lower() for a in existing_aliases if a}
    rows: list[tuple[str, str]] = []

    # Try to get Faker for names
    fake = None
    try:
        from faker import Faker
        fake = Faker()
    except Exception:
        fake = None

    attempts = 0
    while len(rows) < max(0, int(count)) and attempts < 200:
        attempts += 1

        # 1. Generate Alias (Using Faker or Fallback)
        if fake:
            alias = str(fake.user_name() or "").strip()
        else:
            alias = _fallback_alias(max_len=max(3, min(id_col_width, 14)))

        # 2. Generate Tag (Using Markovify, Faker Sentence, or Pool)
        tag = ""
        if _MARKOV_BRAIN:
            # Try to make a short sentence that fits the column width
            tag = _MARKOV_BRAIN.make_short_sentence(tag_col_width, tries=20)
        
        if not tag: # If Markov fails or isn't loaded, try Faker
            if fake:
                tag = str(fake.sentence() or "").strip()
            else: # Total fallback
                tag = _fallback_tag(max_len=tag_col_width)

        # Clean up strings
        alias = alias.replace("\r", "").replace("\n", "").strip()
        # Ensure decoy aliases are displayed as handles.
        # Keep within the fixed ID column width.
        if alias:
            alias = "@" + alias.lstrip("@")
        else:
            alias = "@x"
        alias = alias[:id_col_width]
        tag = tag.replace("\r", " ").replace("\n", " ").strip()[:tag_col_width]

        if not alias:
            continue

        key = alias.lower()
        if key in existing:
            continue

        existing.add(key)
        rows.append((alias, tag))

    return rows