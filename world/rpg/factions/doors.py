"""
Door pairing, bioscan checks, and auto-close for faction-secured exits.
Used by typeclasses.exits.Exit and commands.door_cmds.

Keys: has_key() expects carried objects to use Evennia tags with category "key"
(the tag key string is the key id, e.g. obj.tags.add("imp_hq_master", category="key")).
"""

import time

from evennia.utils import delay
from evennia.utils.search import search_object

from world.rpg.factions import is_faction_member
from world.rpg.factions.membership import get_member_rank


def _resolve_door_pair_exit(exit_obj):
    """Return the paired exit object from exit.db.door_pair (dbref int or #id)."""
    ndb = getattr(exit_obj, "ndb", None)
    if ndb is not None:
        cached = getattr(ndb, "_door_pair_obj", None)
        if cached is not None:
            try:
                if getattr(cached, "id", None):
                    return cached
            except Exception:
                pass
    ref = getattr(getattr(exit_obj, "db", None), "door_pair", None)
    if ref is None:
        return None
    if isinstance(ref, int):
        rid = ref
    else:
        s = str(ref).strip()
        if s.startswith("#"):
            s = s[1:]
        try:
            rid = int(s)
        except ValueError:
            return None
    res = search_object(f"#{rid}")
    pair = res[0] if res else None
    if pair is not None and ndb is not None:
        ndb._door_pair_obj = pair
    return pair


def exit_direction_word(exit_obj):
    """Compass-style word for messages: exit key/alias (e.g. south, north)."""
    if not exit_obj:
        return "the exit"
    k = (getattr(exit_obj, "key", None) or "").strip().lower()
    if k:
        return k
    try:
        als = exit_obj.aliases.all() if hasattr(exit_obj.aliases, "all") else []
        if als:
            return (als[0] or "").strip().lower() or "the exit"
    except Exception:
        pass
    return "the exit"


def sync_door_pair(exit_obj, open_state):
    """Sync the paired exit to the same open/closed state."""
    pair = _resolve_door_pair_exit(exit_obj)
    if pair and getattr(pair.db, "door", None):
        pair.db.door_open = bool(open_state)
        pair_loc = pair.location
        if pair_loc and hasattr(pair_loc, "msg_contents"):
            direction = exit_direction_word(pair)
            state = "opens" if open_state else "closes"
            pair_loc.msg_contents(
                f"The door to the {direction} {state} from the other side."
            )


def auto_close_door(exit_id):
    """Callback: close door after timer. exit_id is database id."""
    res = search_object(f"#{exit_id}")
    if not res:
        return
    exit_obj = res[0]
    if not getattr(exit_obj.db, "door_open", False):
        return
    exit_obj.db.door_open = False
    sync_door_pair(exit_obj, False)
    door_name = getattr(exit_obj.db, "door_name", None) or "door"
    loc = exit_obj.location
    if loc and hasattr(loc, "msg_contents"):
        loc.msg_contents(f"The {door_name} closes automatically.")


def schedule_door_auto_close(exit_obj, seconds):
    """Schedule auto-close after seconds (0 = no schedule)."""
    sec = int(seconds or 0)
    if sec <= 0:
        return
    delay(sec, auto_close_door, exit_obj.id)


def schedule_bioscan_auto_close(exit_obj):
    sec = int(getattr(exit_obj.db, "bioscan_auto_close", None) or 8)
    schedule_door_auto_close(exit_obj, sec)


# Seconds after submitting biometrics before the door opens (scan / actuator lag).
BIOSCAN_VERIFY_DELAY = 4


def complete_bioscan_verify_pass(caller_id, exit_id, pass_msg, door_name, direction_word):
    """
    Callback after verify: open door and notify room if the caller is still at the exit.
    """
    res_c = search_object(f"#{caller_id}")
    res_e = search_object(f"#{exit_id}")
    if not res_c or not res_e:
        return
    caller = res_c[0]
    ex = res_e[0]
    if not getattr(ex.db, "bioscan", None):
        return
    if getattr(ex.db, "door_open", None):
        return
    if caller.location != ex.location:
        caller.msg("You moved away from the scanner; verification aborts.")
        return
    ex.db.door_open = True
    sync_door_pair(ex, True)
    pm = pass_msg or "Bioscan accepted."
    dn = door_name or "bioscan door"
    dw = (direction_word or "the exit").strip() or "the exit"
    caller.msg(f"|g{pm}|n")
    loc = caller.location
    if loc:
        loc.msg_contents(
            "The {dn} to the {dir} opens for {name}.",
            exclude=caller,
            mapping={"name": caller, "dn": dn, "dir": dw},
            from_obj=caller,
        )
    schedule_bioscan_auto_close(ex)


def complete_bioscan_verify_fail(
    caller_id, exit_id, fail_msg, door_name, direction_word, sound_fail
):
    """
    Callback after verify (failed scan): notify caller and optionally the room.
    """
    res_c = search_object(f"#{caller_id}")
    res_e = search_object(f"#{exit_id}")
    if not res_c or not res_e:
        return
    caller = res_c[0]
    ex = res_e[0]
    if not getattr(ex.db, "bioscan", None):
        return
    if caller.location != ex.location:
        caller.msg("You moved away from the scanner; verification aborts.")
        return
    fm = fail_msg or "Bioscan rejected."
    dn = door_name or "bioscan door"
    dw = (direction_word or "the exit").strip() or "the exit"
    caller.msg(f"|r{fm}|n")
    if sound_fail:
        loc = caller.location
        if loc:
            loc.msg_contents(
                "The {dn} to the {dir} buzzes — access denied for {name}.",
                exclude=caller,
                mapping={"name": caller, "dn": dn, "dir": dw},
                from_obj=caller,
            )


def has_key(character, key_tag):
    """True if character carries a key item with tag key_tag (category key)."""
    if not key_tag or not character:
        return False
    for obj in character.contents:
        if obj.tags.has(key_tag, category="key"):
            return True
    return False


def staff_bypass(character):
    try:
        acc = getattr(character, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True
    except Exception:
        pass
    return False


def _log_bioscan_attempt(character, exit_obj, passed=False):
    """Store bioscan attempts on the exit for security review (capped)."""
    log = exit_obj.db.bioscan_log or []
    log.append(
        {
            "character_id": getattr(character, "id", None),
            "character_name": getattr(character, "key", "?"),
            "time": time.time(),
            "passed": passed,
        }
    )
    if len(log) > 30:
        log = log[-30:]
    exit_obj.db.bioscan_log = log


def run_bioscan(character, exit_obj):
    """
    Run bioscan verification. Returns (passed: bool, message: str).
    """
    if staff_bypass(character):
        return True, "Staff override accepted."

    if not character.cooldowns.ready("bioscan"):
        return False, "Scanner cycling. Wait."
    character.cooldowns.add("bioscan", 3)

    scan_type = getattr(exit_obj.db, "bioscan_type", None) or "faction"

    if scan_type == "faction":
        faction_key = getattr(exit_obj.db, "bioscan_faction", None)
        if not faction_key:
            return False, "Bioscan misconfigured. No faction set."
        if is_faction_member(character, faction_key):
            return True, "Faction membership confirmed."
        _log_bioscan_attempt(character, exit_obj, passed=False)
        return False, "Faction membership not detected."

    if scan_type == "rank":
        faction_key = getattr(exit_obj.db, "bioscan_faction", None)
        min_rank = int(getattr(exit_obj.db, "bioscan_rank", None) or 1)
        if not faction_key:
            return False, "Bioscan misconfigured."
        rank = get_member_rank(character, faction_key)
        if rank >= min_rank:
            return True, "Rank clearance confirmed."
        if rank > 0:
            _log_bioscan_attempt(character, exit_obj, passed=False)
            return False, "Insufficient rank clearance."
        _log_bioscan_attempt(character, exit_obj, passed=False)
        return False, "Faction membership not detected."

    if scan_type == "whitelist":
        whitelist = getattr(exit_obj.db, "bioscan_whitelist", None) or []
        cid = getattr(character, "id", None)
        dbref = getattr(character, "dbref", None)
        if cid in whitelist or dbref in whitelist:
            return True, "Identity confirmed."
        _log_bioscan_attempt(character, exit_obj, passed=False)
        return False, "Identity not on access list."

    if scan_type == "custom":
        _log_bioscan_attempt(character, exit_obj, passed=False)
        return False, "Custom bioscan not implemented."

    _log_bioscan_attempt(character, exit_obj, passed=False)
    return False, "Unknown bioscan type."
