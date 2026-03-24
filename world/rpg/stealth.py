"""
Stealth: hiding, sneaking, passive detection, reveal.

Uses character.roll_check(["intelligence", "agility"], "stealth", ...) for
both hiding quality and detection attempts (numeric compare).
"""
from __future__ import annotations

import random

STAT_LIST = ("intelligence", "agility")
STEALTH_SKILL = "stealth"

# Commands that do not break stealth when already hidden (hide delay uses stricter rules in Command.at_pre_cmd).
STEALTH_SAFE_COMMANDS = frozenset(
    {
        "sneak",
        "look",
        "l",
        "time",
        "score",
        "@sheet",
        "@trusted",
        "@trust",
        "@untrust",
        "help",
        "@quit",
        "ooc",
        "who",
        "inventory",
        "inv",
        "unhide",
        "hide",
        "follow",
        "shadow",
        "stop",
        "cease",
    }
)


def _is_staff(looker) -> bool:
    try:
        acc = getattr(looker, "account", None)
        if acc and getattr(acc, "permissions", None):
            if acc.permissions.check("Builder") or acc.permissions.check("Admin"):
                return True
    except Exception:
        pass
    return False


def roll_stealth(character, modifier: int = 0) -> int:
    """Roll stealth check; return numeric final_result."""
    if not character or not hasattr(character, "roll_check"):
        return 0
    _tier, result = character.roll_check(list(STAT_LIST), STEALTH_SKILL, difficulty=0, modifier=modifier)
    return int(result or 0)


def roll_detection(character, modifier: int = 0) -> int:
    """Passive/active detection uses same skill/stats as stealth per design."""
    return roll_stealth(character, modifier=modifier)


def room_stealth_modifier(room) -> int:
    if not room:
        return 0
    try:
        return int(getattr(room.db, "stealth_modifier", 0) or 0)
    except Exception:
        return 0


def apply_room_stealth_modifier(room, base_result: int) -> int:
    return int(base_result) + room_stealth_modifier(room)


def is_hidden(character) -> bool:
    if not character:
        return False
    return bool(getattr(character.db, "stealth_hidden", False))


def has_spotted(looker, hider) -> bool:
    if not looker or not hider:
        return False
    spotted = getattr(hider.db, "stealth_spotted_by", None) or []
    try:
        return looker.id in spotted
    except Exception:
        return False


def _append_spotted(hider, looker_id: int) -> None:
    cur = list(getattr(hider.db, "stealth_spotted_by", None) or [])
    if looker_id not in cur:
        cur.append(looker_id)
    hider.db.stealth_spotted_by = cur


def add_spotted(hider, looker_id: int) -> None:
    """Public alias for search / external callers."""
    _append_spotted(hider, looker_id)


def reveal(character, reason: str = "action") -> None:
    """Break stealth and reset state."""
    if not character or not getattr(character.db, "stealth_hidden", False):
        return

    character.db.stealth_hidden = False
    character.db.stealth_roll_result = 0
    character.db.stealth_spotted_by = []

    if reason == "action":
        character.msg("|yYou emerge from hiding.|n")
        loc = getattr(character, "location", None)
        if loc:
            loc.msg_contents(
                "{name} emerges from hiding.",
                exclude=character,
                mapping={"name": character},
            )
    elif reason == "combat":
        character.msg("|rYou are forced out of hiding!|n")
        loc = getattr(character, "location", None)
        if loc:
            loc.msg_contents(
                "{name} is revealed!",
                exclude=character,
                mapping={"name": character},
            )
    elif reason == "damage":
        character.msg("|rThe impact gives away your position!|n")
        loc = getattr(character, "location", None)
        if loc:
            loc.msg_contents(
                "{name} is knocked out of hiding!",
                exclude=character,
                mapping={"name": character},
            )


def run_arrival_detection(arriving_char, room) -> None:
    """
    When a character enters a room, roll detection against each hidden character
    they have not already spotted (per that hider's list).
    """
    if not arriving_char or not room or not hasattr(room, "contents_get"):
        return
    try:
        from evennia.objects.objects import DefaultCharacter

        if not isinstance(arriving_char, DefaultCharacter):
            return
    except Exception:
        pass

    for hider in room.contents_get(content_type="character"):
        if hider is arriving_char:
            continue
        if not is_hidden(hider):
            continue
        spotted = getattr(hider.db, "stealth_spotted_by", None) or []
        try:
            if arriving_char.id in spotted:
                continue
        except Exception:
            continue

        hide_result = int(getattr(hider.db, "stealth_roll_result", 0) or 0)
        detect_result = roll_detection(arriving_char)
        if detect_result >= hide_result:
            _append_spotted(hider, arriving_char.id)
            try:
                name = (
                    hider.get_display_name(arriving_char)
                    if hasattr(hider, "get_display_name")
                    else getattr(hider, "key", "someone")
                )
            except Exception:
                name = getattr(hider, "key", "someone")
            arriving_char.msg(f"|yYou spot {name} hiding here.|n")


def contest_hide_vs_room(hider, room, exclude=None) -> None:
    """
    After a successful hide, each other character in the room rolls detection vs hider's cached result.
    """
    if not hider or not room:
        return
    exclude = exclude or set()
    hide_result = int(getattr(hider.db, "stealth_roll_result", 0) or 0)
    for other in room.contents_get(content_type="character"):
        if other is hider or other in exclude:
            continue
        det = roll_detection(other)
        if det >= hide_result:
            _append_spotted(hider, other.id)
            try:
                name = (
                    hider.get_display_name(other)
                    if hasattr(hider, "get_display_name")
                    else getattr(hider, "key", "someone")
                )
            except Exception:
                name = getattr(hider, "key", "someone")
            other.msg(f"|yYou watch {name} settle into a hiding spot. You know where they are.|n")


def sneak_arrival(sneaker, room) -> None:
    """
    After sneak move_to into room: fresh stealth roll (+ room mod), clear spotted list,
    contest vs everyone present in destination.
    """
    if not sneaker or not room:
        return
    base = roll_stealth(sneaker)
    total = apply_room_stealth_modifier(room, base)
    sneaker.db.stealth_roll_result = total
    sneaker.db.stealth_spotted_by = []
    sneaker.db.stealth_hidden = True

    hide_result = total
    for other in room.contents_get(content_type="character"):
        if other is sneaker:
            continue
        det = roll_detection(other)
        if det >= hide_result:
            _append_spotted(sneaker, other.id)
            try:
                name = (
                    sneaker.get_display_name(other)
                    if hasattr(sneaker, "get_display_name")
                    else getattr(sneaker, "key", "someone")
                )
            except Exception:
                name = getattr(sneaker, "key", "someone")
            other.msg(f"|yYou notice {name} slipping into the room.|n")


def hide_spot_flavor(room) -> str:
    """Flavor line for search success; generic if room has no list."""
    if not room:
        return "nearby"
    spots = getattr(room.db, "stealth_hide_spots", None)
    if isinstance(spots, (list, tuple)) and spots:
        choices = [str(s) for s in spots if s]
        if choices:
            return random.choice(choices)
    return "nearby"


def cancel_hide_pending(character, msg: str | None = None) -> None:
    if not character:
        return
    if getattr(character.ndb, "hide_pending", False):
        character.ndb.hide_pending = False
        if msg:
            character.msg(msg)
        else:
            character.msg("|yYour attempt to hide is interrupted.|n")


def command_key_interrupts_hide(cmd_self) -> str:
    """Normalized command key for hide-pending interrupt (any command cancels)."""
    key = (getattr(cmd_self, "key", None) or "").strip().lower()
    if key:
        return key
    raw = getattr(cmd_self, "raw_string", "") or ""
    part = raw.strip().split(None, 1)
    return (part[0] if part else "").lower()


def command_breaks_stealth(cmd_self) -> bool:
    """True if this command should break stealth (caller already hidden)."""
    key = (getattr(cmd_self, "key", None) or "").strip().lower()
    if not key:
        raw = getattr(cmd_self, "raw_string", "") or ""
        part = raw.strip().split(None, 1)
        key = (part[0] if part else "").lower()
    if key in STEALTH_SAFE_COMMANDS:
        return False
    # Strip common prefixes
    if key.startswith("@") and key.lstrip("@") in STEALTH_SAFE_COMMANDS:
        return False
    return True


def sneak_breaks_stealth_combat(sneaker) -> bool:
    """True if sneaker should lose stealth due to combat state in current room."""
    try:
        from world.combat import is_in_combat
        from world.combat.utils import get_combat_target

        if not is_in_combat(sneaker):
            return False
        loc = getattr(sneaker, "location", None)
        tgt = get_combat_target(sneaker)
        if tgt and getattr(tgt, "location", None) == loc:
            return True
        for other in loc.contents_get(content_type="character") if loc and hasattr(loc, "contents_get") else []:
            if other is sneaker:
                continue
            if get_combat_target(other) == sneaker:
                return True
    except Exception:
        pass
    return False
