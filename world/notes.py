"""
PC Note system.

Storage: PCNote Django model (world.models.PCNote).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

STAFF_READ_ATTR = "pc_notes_read_ids_v1"
DEFAULT_CATEGORIES = ("IC", "OOC", "JOB", "PLOT", "PVP")


def _note_to_dict(note) -> Dict[str, Any]:
    """Convert a PCNote instance to the dict format used throughout the codebase."""
    return {
        "id": note.pk,
        "created_at": note.created_at.isoformat() if note.created_at else "",
        "category": note.category,
        "title": note.title,
        "body": note.body,
        "char_id": note.char_id,
        "char_key": note.char_key,
        "account_id": note.account_id,
        "account_key": note.account_key,
    }


def add_note(
    *,
    character,
    account,
    category: str,
    title: str,
    body: str,
) -> Dict[str, Any]:
    """Add a new note and persist it."""
    from world.models import PCNote
    cat = (category or "").strip().upper() or "UNCATEGORIZED"
    ttl = (title or "").strip() or "(untitled)"
    txt = (body or "").rstrip()
    note = PCNote.objects.create(
        category=cat,
        title=ttl,
        body=txt,
        char_id=getattr(character, "id", None),
        char_key=getattr(character, "key", None) or getattr(character, "name", None) or "",
        account_id=getattr(account, "id", None),
        account_key=getattr(account, "key", None) or getattr(account, "username", None) or "",
    )
    return _note_to_dict(note)


def notes_for_character(character, *, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """All notes for a given character, optionally filtered by category. Most-recent first."""
    from world.models import PCNote
    cid = getattr(character, "id", None)
    if not cid:
        return []
    qs = PCNote.objects.filter(char_id=cid)
    if category:
        qs = qs.filter(category__iexact=category.strip())
    return [_note_to_dict(n) for n in qs]


def notes_for_character_name(char_name: str, *, account=None, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Staff: find notes for a character by case-insensitive name."""
    from world.models import PCNote
    if not char_name:
        return []
    qs = PCNote.objects.filter(char_key__iexact=char_name.strip())
    if account is not None:
        acc_id = getattr(account, "id", None)
        if acc_id is not None:
            qs = qs.filter(account_id=acc_id)
    if category:
        qs = qs.filter(category__iexact=category.strip())
    return [_note_to_dict(n) for n in qs]


def get_note_by_id(note_id: int) -> Optional[Dict[str, Any]]:
    from world.models import PCNote
    try:
        nid = int(note_id)
        note = PCNote.objects.get(pk=nid)
        return _note_to_dict(note)
    except Exception:
        return None


def staff_read_ids(account) -> set:
    raw = getattr(getattr(account, "db", None), STAFF_READ_ATTR, None) or []
    try:
        return set(int(x) for x in raw)
    except Exception:
        return set()


def staff_mark_read(account, note_id: int) -> None:
    if not getattr(account, "db", None):
        return
    ids = staff_read_ids(account)
    try:
        ids.add(int(note_id))
    except Exception:
        return
    setattr(account.db, STAFF_READ_ATTR, sorted(ids))


def staff_unread_notes(account) -> List[Dict[str, Any]]:
    from world.models import PCNote
    read = staff_read_ids(account)
    qs = PCNote.objects.filter(account_id__isnull=False)
    return [_note_to_dict(n) for n in qs if n.pk not in read]
