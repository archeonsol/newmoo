"""
Core membership operations: enlist, discharge, promote, demote, query.
All functions operate on Evennia tags and db attributes.

Membership data stored on character:
    tags: faction_imp (category="faction")     — one tag per faction
    db.faction_ranks: {"IMP": 3, "MYTHOS": 1}  — rank number per faction
    db.faction_joined: {"IMP": timestamp, ...}  — when they joined (see ensure_faction_join_timestamp)
    db.faction_pay_collected: {"IMP": timestamp} — last pay collection time
    db.faction_notes: {"IMP": "Transferred from..."}  — admin notes per faction

Vendors can restrict sales with db.faction_required and db.faction_required_rank — use
is_faction_member() and get_member_rank() from this module.
"""

import logging
import time

from world.rpg.factions import get_faction, get_character_factions
from world.rpg.factions.ranks import get_rank_info, get_max_rank, get_rank_name, get_rank_permission

try:
    from world.gamelog import get_logger as _get_gamelog
    _log = _get_gamelog(__name__)
except Exception:
    _log = logging.getLogger("evennia")

# Wall-clock enlist uses time.time(). Below this, values are almost always epoch bugs or bad imports.
FACTION_JOIN_MIN_PLAUSIBLE_TS = 946684800  # 2000-01-01 UTC


def _is_plausible_faction_join_ts(ts):
    if ts is None or ts == "":
        return False
    if not isinstance(ts, (int, float)):
        return False
    if isinstance(ts, bool):
        return False
    now = time.time()
    if ts <= 0 or ts < FACTION_JOIN_MIN_PLAUSIBLE_TS or ts > now + 86400:
        return False
    return True


def _faction_enlist_time_from_log(character, faction_key):
    """Most recent 'enlisted' log entry for this faction, or None."""
    log = character.db.faction_log or []
    for entry in reversed(log):
        if entry.get("faction") != faction_key or entry.get("event") != "enlisted":
            continue
        raw = entry.get("time")
        if raw is None:
            raw = entry.get("timestamp")
        if raw is not None and _is_plausible_faction_join_ts(raw):
            return float(raw)
    return None


def _faction_join_time_from_first_pay_cooldown(character, faction_key):
    """
    While the first-pay delay cooldown is active, its expiry minus the standard
    delay recovers the enlist wall-clock time.
    """
    from world.rpg.factions.pay import FIRST_PAY_DELAY_SECONDS

    try:
        raw_cd = getattr(character.db, "cooldowns", None) or {}
        exp = raw_cd.get(f"pay_first_{faction_key}")
    except Exception:
        return None
    if exp is None:
        return None
    now = time.time()
    inferred = float(exp) - float(FIRST_PAY_DELAY_SECONDS)
    if inferred > now + 60:
        return None
    if not _is_plausible_faction_join_ts(inferred):
        return None
    return inferred


def ensure_faction_join_timestamp(character, faction_key):
    """
    Return db.faction_joined[faction_key] if valid; otherwise infer from faction_log
    or the active first-pay cooldown, persist it, and return it. Returns None if unknown.
    """
    fdata = get_faction(faction_key)
    if not fdata or not hasattr(character, "db"):
        return None
    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return None

    joined_map = dict(character.db.faction_joined or {})
    current = joined_map.get(faction_key)
    if _is_plausible_faction_join_ts(current):
        return float(current)

    inferred = _faction_enlist_time_from_log(character, faction_key)
    if inferred is None:
        inferred = _faction_join_time_from_first_pay_cooldown(character, faction_key)

    if inferred is not None:
        joined_map[faction_key] = inferred
        character.db.faction_joined = joined_map
        return inferred
    return None


def _is_roster_eligible(obj):
    """True if object should appear on faction roster (living character types only)."""
    if not obj or not hasattr(obj, "db"):
        return False
    try:
        from typeclasses.corpse import Corpse

        if isinstance(obj, Corpse):
            return False
    except ImportError:
        pass
    try:
        from typeclasses.characters import Character

        if isinstance(obj, Character):
            return True
    except ImportError:
        pass
    try:
        from typeclasses.npc import NPC

        if isinstance(obj, NPC):
            return True
    except ImportError:
        pass
    return False


def enlist(character, faction_key, rank=None, enlisted_by=None):
    """
    Enlist a character in a faction at the given rank (default: faction's default_rank).

    Returns (success: bool, message: str).
    """
    fdata = get_faction(faction_key)
    if not fdata:
        return False, f"Unknown faction: {faction_key}"

    if character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return False, f"Already a member of {fdata['name']}."

    conflict = _check_faction_conflict(character, fdata["key"])
    if conflict:
        return False, conflict

    if rank is None:
        rank = fdata.get("default_rank", 1)
    rank_info = get_rank_info(fdata["ranks"], rank)
    if not rank_info:
        return False, f"Invalid rank {rank} for {fdata['name']}."

    character.tags.add(fdata["tag"], category=fdata["tag_category"])

    ranks = character.db.faction_ranks or {}
    ranks[fdata["key"]] = rank
    character.db.faction_ranks = ranks

    joined = character.db.faction_joined or {}
    joined[fdata["key"]] = time.time()
    character.db.faction_joined = joined

    # Set first-pay delay cooldown so new members can't immediately collect pay.
    from world.rpg.factions.pay import FIRST_PAY_DELAY_SECONDS
    character.cooldowns.add(f"pay_first_{fdata['key']}", FIRST_PAY_DELAY_SECONDS)

    _log_faction_event(
        character,
        fdata["key"],
        "enlisted",
        f"Rank {rank} ({rank_info['name']}), by {enlisted_by or 'system'}",
    )

    return True, f"Enlisted in {fdata['name']} as {rank_info['name']}."


def discharge(character, faction_key, discharged_by=None, reason="discharged"):
    """
    Remove a character from a faction. Clears tag and rank.
    Does NOT clear faction_pay_collected — cooldown persists across discharge/re-enlist.

    Returns (success: bool, message: str).
    """
    fdata = get_faction(faction_key)
    if not fdata:
        return False, f"Unknown faction: {faction_key}"

    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return False, f"Not a member of {fdata['name']}."

    character.tags.remove(fdata["tag"], category=fdata["tag_category"])

    ranks = character.db.faction_ranks or {}
    old_rank = ranks.pop(fdata["key"], None)
    character.db.faction_ranks = ranks

    _log_faction_event(
        character,
        fdata["key"],
        reason,
        f"Was rank {old_rank}, by {discharged_by or 'system'}",
    )

    return True, f"Discharged from {fdata['name']}. Reason: {reason}."


def promote(character, faction_key, promoted_by=None, operator=None):
    """Increase a character's rank by 1 in the given faction. Returns (success, message).

    If operator is set, enforces leadership permission (3+) and rank rules; staff (perm 99) bypass rank limits.
    """
    fdata = get_faction(faction_key)
    if not fdata:
        return False, f"Unknown faction: {faction_key}"

    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return False, f"Not a member of {fdata['name']}."

    ranks = character.db.faction_ranks or {}
    current = ranks.get(fdata["key"], fdata.get("default_rank", 1))
    new_rank = current + 1

    if operator is not None:
        op_perm = get_member_permission(operator, faction_key)
        if op_perm < 3:
            return False, "Only faction leadership can promote members."
        if op_perm != 99:
            op_rank = get_member_rank(operator, faction_key)
            if new_rank >= op_rank:
                return False, "Cannot promote someone to your rank or above."

    max_r = get_max_rank(fdata["ranks"])

    if new_rank > max_r:
        return False, f"Already at maximum rank ({get_rank_name(fdata['ranks'], current)})."

    rank_info = get_rank_info(fdata["ranks"], new_rank)
    if not rank_info:
        return False, f"Invalid rank {new_rank}."

    ranks[fdata["key"]] = new_rank
    character.db.faction_ranks = ranks

    _log_faction_event(
        character,
        fdata["key"],
        "promoted",
        f"{current} -> {new_rank} ({rank_info['name']}), by {promoted_by or 'system'}",
    )

    return True, f"Promoted to {rank_info['name']} in {fdata['name']}."


def demote(character, faction_key, demoted_by=None, operator=None):
    """Decrease a character's rank by 1. Cannot go below rank 1. Returns (success, message).

    If operator is set, enforces leadership permission (3+) and rank rules; staff (perm 99) bypass rank limits.
    """
    fdata = get_faction(faction_key)
    if not fdata:
        return False, f"Unknown faction: {faction_key}"

    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return False, f"Not a member of {fdata['name']}."

    ranks = character.db.faction_ranks or {}
    current = ranks.get(fdata["key"], fdata.get("default_rank", 1))
    new_rank = current - 1

    if new_rank < 1:
        return False, "Already at minimum rank."

    if operator is not None:
        op_perm = get_member_permission(operator, faction_key)
        if op_perm < 3:
            return False, "Only faction leadership can demote members."
        if op_perm != 99:
            op_rank = get_member_rank(operator, faction_key)
            if current >= op_rank:
                return False, "Cannot demote someone at or above your rank."

    rank_info = get_rank_info(fdata["ranks"], new_rank)
    ranks[fdata["key"]] = new_rank
    character.db.faction_ranks = ranks

    _log_faction_event(
        character,
        fdata["key"],
        "demoted",
        f"{current} -> {new_rank}, by {demoted_by or 'system'}",
    )

    return True, f"Demoted to {rank_info['name']} in {fdata['name']}."


def set_rank(character, faction_key, rank_number, set_by=None):
    """Set a character's rank to a specific value. Returns (success, message)."""
    fdata = get_faction(faction_key)
    if not fdata:
        return False, f"Unknown faction: {faction_key}"

    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return False, f"Not a member of {fdata['name']}."

    rank_info = get_rank_info(fdata["ranks"], rank_number)
    if not rank_info:
        return False, f"Invalid rank {rank_number} for {fdata['name']}."

    ranks = character.db.faction_ranks or {}
    old_rank = ranks.get(fdata["key"], 1)
    ranks[fdata["key"]] = rank_number
    character.db.faction_ranks = ranks

    _log_faction_event(
        character,
        fdata["key"],
        "rank_set",
        f"{old_rank} -> {rank_number} ({rank_info['name']}), by {set_by or 'system'}",
    )

    return True, f"Rank set to {rank_info['name']} in {fdata['name']}."


def get_member_rank(character, faction_key):
    """Return the character's rank number in a faction. Returns 0 if not a member."""
    fdata = get_faction(faction_key)
    if not fdata:
        return 0
    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return 0
    ranks = character.db.faction_ranks or {}
    return ranks.get(fdata["key"], 0)


def get_member_permission(character, faction_key, *, elevate_staff=True):
    """
    Return the character's permission level in a faction. Returns -1 if not a member.

    When elevate_staff is True (default), Builder/Admin accounts return 99 (OOC bypass for
    code paths that should treat staff as fully authorized). When False, only rank-derived
    permission is used (e.g. registry terminals that should stay IC).
    """
    if elevate_staff:
        try:
            if getattr(character, "account", None):
                if character.account.permissions.check("Builder") or character.account.permissions.check("Admin"):
                    return 99
        except Exception:
            pass

    fdata = get_faction(faction_key)
    if not fdata:
        return -1
    if not character.tags.has(fdata["tag"], category=fdata["tag_category"]):
        return -1

    rank = get_member_rank(character, faction_key)
    return get_rank_permission(fdata["ranks"], rank)


def get_faction_roster(faction_key, limit=None):
    """
    Return a list of (character, rank_number) tuples, sorted by rank descending.
    Queries the database — call once per session when opening roster, not every tick.
    If limit is an int, return at most that many entries after sorting.
    """
    from evennia.utils.search import search_tag

    fdata = get_faction(faction_key)
    if not fdata:
        return []

    members = search_tag(key=fdata["tag"], category=fdata["tag_category"])
    result = []
    for char in members:
        if not _is_roster_eligible(char):
            continue
        if not hasattr(char, "db"):
            continue
        ranks = getattr(char.db, "faction_ranks", None) or {}
        rank = ranks.get(fdata["key"], fdata.get("default_rank", 1))
        result.append((char, rank))

    result.sort(key=lambda x: x[1], reverse=True)
    if limit is not None:
        return result[: int(limit)]
    return result


# A character cannot be in both factions in a conflict pair.
FACTION_CONFLICTS = frozenset(
    {
        frozenset({"BURN", "SINK", "RACK", "PIT"}),
        frozenset({"BURN", "IMP"}),
        frozenset({"SINK", "IMP"}),
        frozenset({"RACK", "IMP"}),
        frozenset({"PIT", "IMP"}),
        frozenset({"BURN", "INQ"}),
        frozenset({"SINK", "INQ"}),
        frozenset({"RACK", "INQ"}),
        frozenset({"PIT", "INQ"}),
    }
)


def _check_faction_conflict(character, new_faction_key):
    """
    Check if enlisting in new_faction_key would conflict with existing memberships.
    Returns an error message string if conflict found, None if clear.
    """
    current_factions = {f["key"] for f in get_character_factions(character)}
    new_fdata = get_faction(new_faction_key)

    for conflict_group in FACTION_CONFLICTS:
        if new_faction_key not in conflict_group:
            continue
        overlaps = current_factions & conflict_group
        if overlaps:
            conflicting = next(iter(overlaps))
            conflict_fdata = get_faction(conflicting)
            return (
                f"Cannot join {new_fdata['name']} while a member of "
                f"{conflict_fdata['name']}. Discharge first."
            )
    return None


def _log_faction_event(character, faction_key, event_type, details=""):
    """Append a faction event to db.faction_log; capped at 50 entries."""
    try:
        _log.info(
            "faction.event",
            char=getattr(character, "key", "?"),
            faction=faction_key,
            event=event_type,
            details=details,
        )
    except Exception:
        pass
    log = character.db.faction_log or []
    log.append(
        {
            "faction": faction_key,
            "event": event_type,
            "details": details,
            "time": time.time(),
            "character_name": character.key,
        }
    )
    if len(log) > 50:
        log = log[-50:]
    character.db.faction_log = log
