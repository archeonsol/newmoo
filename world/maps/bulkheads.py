"""
Bulkhead seal management. Only Inquisitorate members and staff can seal/unseal.

Bulkheads are passthrough rooms between a district and a freight station.
Seal state is stored on the BulkheadRoom; exits use `db.bulkhead_locked` and are
blocked in `precheck_exit_traversal` (custom message, staff bypass).
"""

from __future__ import annotations

import time
from evennia.utils import logger
from evennia.utils.search import search_object, search_tag


def can_operate_bulkhead(character):
    """
    Check if a character has authority to seal/unseal bulkheads.
    Returns (allowed: bool, reason: str).
    """
    try:
        acc = getattr(character, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True, "staff"
    except Exception:
        pass

    try:
        from world.rpg.factions import is_faction_member

        if is_faction_member(character, "INQ"):
            return True, "inquisitorate"
    except Exception:
        pass

    return False, "Only the Inquisitorate may operate bulkheads."


def _log_bulkhead_event(bulkhead_room, event_type: str, character, details: str = ""):
    raw = getattr(bulkhead_room.db, "seal_log", None)
    log = list(raw) if isinstance(raw, (list, tuple)) else []
    log.append(
        {
            "event": event_type,
            "character": getattr(character, "key", "?"),
            "character_id": getattr(character, "id", None),
            "time": time.time(),
            "details": str(details)[:100],
        }
    )
    if len(log) > 30:
        log = log[-30:]
    bulkhead_room.db.seal_log = log


def _lock_exit(exit_id: int | None):
    if not exit_id:
        return
    results = search_object(f"#{exit_id}")
    if not results:
        return
    ex = results[0]
    ex.db.bulkhead_locked = True


def _unlock_exit(exit_id: int | None):
    if not exit_id:
        return
    results = search_object(f"#{exit_id}")
    if not results:
        return
    ex = results[0]
    ex.db.bulkhead_locked = False


def _announce_to_adjacent(bulkhead_room, message: str):
    for attr in ("district_side_exit", "station_side_exit"):
        eid = getattr(bulkhead_room.db, attr, None)
        if not eid:
            continue
        results = search_object(f"#{eid}")
        if not results:
            continue
        exit_obj = results[0]
        dest = getattr(exit_obj, "destination", None)
        if dest and hasattr(dest, "msg_contents"):
            dest.msg_contents(message)


def _notify_freight_of_seal(_bulkhead_room, _sealed: bool):
    """Reserved for future hooks (e.g. station announcements). Lift ignores seals."""
    return


def _apply_seal_locks(bulkhead_room, seal_dir: str):
    """Set bulkhead_locked on the appropriate exit(s) based on seal_direction."""
    if seal_dir in ("outbound", "both"):
        _lock_exit(bulkhead_room.db.station_side_exit)
    if seal_dir in ("inbound", "both"):
        _lock_exit(bulkhead_room.db.district_side_exit)


def _clear_seal_locks(bulkhead_room):
    _unlock_exit(bulkhead_room.db.station_side_exit)
    _unlock_exit(bulkhead_room.db.district_side_exit)


def seal_bulkhead(character, bulkhead_room, reason: str = "", direction: str | None = None):
    """
    Seal a bulkhead. Locks exit(s) per `seal_direction` (default outbound).

    Returns (success: bool, message: str).
    """
    allowed, auth = can_operate_bulkhead(character)
    if not allowed:
        return False, auth

    if bulkhead_room.db.sealed:
        return False, "Already sealed."

    seal_dir = direction or getattr(bulkhead_room.db, "seal_direction", None) or "outbound"
    bulkhead_room.db.seal_direction = seal_dir

    _apply_seal_locks(bulkhead_room, seal_dir)

    bulkhead_room.db.sealed = True
    bulkhead_room.db.seal_reason = reason or "Inquisitorate directive."
    bulkhead_room.db.sealed_by = getattr(character, "key", "?")
    bulkhead_room.db.sealed_at = time.time()
    bulkhead_room.db.seal_warning_sent = False

    _log_bulkhead_event(bulkhead_room, "sealed", character, reason)

    bulkhead_room.msg_contents(
        "|R[BULKHEAD] The blast door slams down. Hydraulic locks engage. The passage is sealed.|n"
    )
    _announce_to_adjacent(
        bulkhead_room,
        "|R[BULKHEAD] A distant boom. The bulkhead has sealed.|n",
    )
    _notify_freight_of_seal(bulkhead_room, True)

    logger.log_info(f"bulkhead sealed {getattr(bulkhead_room.db, 'bulkhead_id', '?')} by {character.key} ({auth})")
    return True, "Bulkhead sealed."


def unseal_bulkhead(character, bulkhead_room):
    """
    Unseal a bulkhead. Unlocks both sides (clears all bulkhead locks on configured exits).

    Returns (success: bool, message: str).
    """
    allowed, auth = can_operate_bulkhead(character)
    if not allowed:
        return False, auth

    if not bulkhead_room.db.sealed:
        return False, "Already open."

    _clear_seal_locks(bulkhead_room)

    sealed_duration = time.time() - (bulkhead_room.db.sealed_at or time.time())
    bulkhead_room.db.sealed = False
    bulkhead_room.db.seal_reason = ""
    bulkhead_room.db.sealed_by = ""
    bulkhead_room.db.sealed_at = 0.0

    _log_bulkhead_event(
        bulkhead_room,
        "unsealed",
        character,
        f"Was sealed for {int(sealed_duration)}s",
    )

    bulkhead_room.msg_contents(
        "|g[BULKHEAD] Hydraulic locks disengage. The blast door retracts into the ceiling. The passage is clear.|n"
    )
    _announce_to_adjacent(
        bulkhead_room,
        "|g[BULKHEAD] The bulkhead opens. Passage restored.|n",
    )
    _notify_freight_of_seal(bulkhead_room, False)

    logger.log_info(f"bulkhead unsealed {getattr(bulkhead_room.db, 'bulkhead_id', '?')} by {character.key} ({auth})")
    return True, "Bulkhead unsealed."


def get_all_bulkheads():
    """Return objects tagged as bulkhead rooms."""
    return list(search_tag("bulkhead", category="room_type"))


def get_bulkhead_by_id(bulkhead_id: str):
    """Find a BulkheadRoom by `db.bulkhead_id`."""
    if not bulkhead_id:
        return None
    for room in get_all_bulkheads():
        if getattr(room.db, "bulkhead_id", "") == bulkhead_id:
            return room
    return None


def setup_bulkhead_exits(bulkhead_room, district_exit_id: int, station_exit_id: int):
    """
    Builder helper: set exit dbrefs on a bulkhead room.
    `district_exit` is the exit *in the bulkhead* leading back toward the district.
    `station_exit` is the exit *in the bulkhead* leading toward the freight station.
    """
    bulkhead_room.db.district_side_exit = int(district_exit_id)
    bulkhead_room.db.station_side_exit = int(station_exit_id)
