"""
Full-text help search using Whoosh.

Builds a search index from HELP_ENTRY_DICTS in world/help_entries.py and from
Evennia's database help entries at server start. When the default @help command
finds no exact match, it falls back to search_help() for ranked suggestions.

Public API:
    build_help_index()       Build/rebuild the index. Call from at_server_start().
    search_help(query, limit=5)  Return list of {key, category, score} dicts.
"""

import logging
import os

logger = logging.getLogger("evennia")

try:
    from whoosh import fields as _wfields
    from whoosh import index as _windex
    from whoosh import qparser as _wqparser
    _WHOOSH_AVAILABLE = True
except ImportError:
    _WHOOSH_AVAILABLE = False

_INDEX_DIR = os.environ.get(
    "MOOTEST_HELP_INDEX_DIR",
    os.path.join(os.path.dirname(__file__), "..", ".help_index"),
)

_SCHEMA = None
_INDEX = None


def _get_schema():
    global _SCHEMA
    if _SCHEMA is None and _WHOOSH_AVAILABLE:
        _SCHEMA = _wfields.Schema(
            key=_wfields.ID(stored=True, unique=True),
            aliases=_wfields.TEXT(stored=True),
            category=_wfields.ID(stored=True),
            text=_wfields.TEXT(stored=False),
        )
    return _SCHEMA


def build_help_index():
    """
    Build/rebuild the Whoosh help index from game help entries.
    Called from at_server_start(). Safe to call multiple times.
    """
    if not _WHOOSH_AVAILABLE:
        logger.warning("[help_search] whoosh not available; help search disabled.")
        return
    global _INDEX
    try:
        os.makedirs(_INDEX_DIR, exist_ok=True)
        schema = _get_schema()
        if _windex.exists_in(_INDEX_DIR):
            _INDEX = _windex.open_dir(_INDEX_DIR)
        else:
            _INDEX = _windex.create_in(_INDEX_DIR, schema)

        writer = _INDEX.writer()
        entries = _collect_help_entries()
        for entry in entries:
            key = str(entry.get("key", "")).strip()
            if not key:
                continue
            aliases = " ".join(entry.get("aliases") or [])
            category = str(entry.get("category", "General")).strip()
            text = str(entry.get("text", "")).strip()
            writer.update_document(
                key=key,
                aliases=aliases,
                category=category,
                text=f"{key} {aliases} {text}",
            )
        writer.commit()
        logger.info(f"[help_search] Index built with {len(entries)} entries.")
    except Exception as exc:
        logger.warning(f"[help_search] Failed to build index: {exc}")


def _collect_help_entries() -> list[dict]:
    """Collect help entries from file-based and DB sources."""
    entries = []
    # File-based entries from world/help_entries.py
    try:
        from world.help_entries import HELP_ENTRY_DICTS
        entries.extend(HELP_ENTRY_DICTS or [])
    except Exception:
        pass
    # Evennia DB help entries
    try:
        from evennia.help.models import HelpEntry
        for db_entry in HelpEntry.objects.all():
            entries.append({
                "key": db_entry.key,
                "aliases": list(db_entry.aliases.all()),
                "category": db_entry.help_category or "General",
                "text": db_entry.entrytext or "",
            })
    except Exception:
        pass
    # Command help strings — iterate CharacterCmdSet
    try:
        from commands.default_cmdsets import CharacterCmdSet
        cs = CharacterCmdSet()
        cs.at_cmdset_creation()
        for cmd in cs.commands:
            entries.append({
                "key": getattr(cmd, "key", ""),
                "aliases": list(getattr(cmd, "aliases", []) or []),
                "category": getattr(cmd, "help_category", "Commands") or "Commands",
                "text": (getattr(cmd, "__doc__", "") or "").strip(),
            })
    except Exception:
        pass
    return entries


def search_help(query_string: str, limit: int = 5) -> list[dict]:
    """
    Search the Whoosh index for help entries matching query_string.

    Returns:
        list of {key, category, score} dicts, ordered by relevance.
        Empty list if whoosh is unavailable or no matches.
    """
    global _INDEX
    if not _WHOOSH_AVAILABLE:
        return []
    if _INDEX is None:
        try:
            if _windex.exists_in(_INDEX_DIR):
                _INDEX = _windex.open_dir(_INDEX_DIR)
            else:
                return []
        except Exception:
            return []
    try:
        with _INDEX.searcher() as searcher:
            parser = _wqparser.MultifieldParser(
                ["key", "aliases", "text"],
                schema=_INDEX.schema,
            )
            query = parser.parse(str(query_string))
            results = searcher.search(query, limit=limit)
            return [
                {
                    "key": hit["key"],
                    "category": hit.get("category", "General"),
                    "score": hit.score,
                }
                for hit in results
            ]
    except Exception as exc:
        logger.warning(f"[help_search] Search failed: {exc}")
        return []
