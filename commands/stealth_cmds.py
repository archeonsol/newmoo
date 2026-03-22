"""
Stealth commands: hide, sneak, search, unhide.
"""

from __future__ import annotations

import time

from evennia.utils import delay
from evennia.utils.search import search_object

from commands.base_cmds import Command, _command_character
from typeclasses.exit_traversal import precheck_exit_traversal

try:
    from world.rpg.staggered_movement import (
        WALK_DELAY,
        CRAWL_DELAY_EXHAUSTED,
        CRAWL_DELAY_LEG_TRAUMA,
        _staggered_walk_callback,
    )
except ImportError:
    WALK_DELAY = 3.5
    CRAWL_DELAY_EXHAUSTED = 8.5
    CRAWL_DELAY_LEG_TRAUMA = 16.0
    _staggered_walk_callback = None


def _resolve_character(oid):
    try:
        objs = search_object("#%s" % int(oid))
        if objs:
            return objs[0]
    except Exception:
        pass
    return None


def _hide_complete(char_id):
    ch = _resolve_character(char_id)
    if not ch or not getattr(ch.ndb, "hide_pending", False):
        return
    ch.ndb.hide_pending = False
    loc = getattr(ch, "location", None)
    if not loc:
        ch.msg("|yThere is nowhere to hide.|n")
        return

    from world.rpg import stealth

    base = stealth.roll_stealth(ch, modifier=0)
    total = stealth.apply_room_stealth_modifier(loc, base)
    ch.db.stealth_roll_result = total
    ch.db.stealth_hidden = True
    ch.db.stealth_spotted_by = []
    ch.msg("|yYou find cover and go still.|n")
    stealth.contest_hide_vs_room(ch, loc)


def _search_complete(char_id, room_id):
    ch = _resolve_character(char_id)
    if not ch:
        return
    loc = getattr(ch, "location", None)
    if not loc or getattr(loc, "id", None) != room_id:
        return

    from world.rpg import stealth

    found_any = False
    for hider in loc.contents_get(content_type="character"):
        if hider is ch:
            continue
        if not stealth.is_hidden(hider):
            continue
        if stealth.has_spotted(ch, hider):
            continue
        det = stealth.roll_detection(ch, modifier=10)
        hide_result = int(getattr(hider.db, "stealth_roll_result", 0) or 0)
        if det >= hide_result:
            found_any = True
            stealth.add_spotted(hider, ch.id)
            try:
                name = (
                    hider.get_display_name(ch)
                    if hasattr(hider, "get_display_name")
                    else getattr(hider, "key", "someone")
                )
            except Exception:
                name = getattr(hider, "key", "someone")
            flavor = stealth.hide_spot_flavor(loc)
            ch.msg(f"|yYou find {name} hiding {flavor}.|n")

    if not found_any:
        ch.msg("|yYou find nothing unusual.|n")


class CmdHide(Command):
    """
    Attempt to hide in your current location.

    Usage:
      hide
    """

    key = "hide"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        from world.rpg import stealth
        from world.combat import is_in_combat

        if stealth.is_hidden(caller):
            caller.msg("You're already hidden.")
            return
        if is_in_combat(caller):
            caller.msg("You can't hide while fighting.")
            return
        if getattr(caller.db, "grappled_by", None):
            caller.msg("You can't hide while restrained.")
            return
        if getattr(caller.ndb, "hide_pending", False):
            caller.msg("You're already trying to hide.")
            return

        now = time.time()
        last = float(getattr(caller.ndb, "_last_hide_attempt", 0) or 0)
        if now - last < 15.0:
            caller.msg("You need to wait before trying to hide again.")
            return
        caller.ndb._last_hide_attempt = now

        loc = getattr(caller, "location", None)
        if not loc:
            caller.msg("You have nowhere to hide.")
            return

        loc.msg_contents(
            "{name} looks for somewhere to hide.",
            exclude=caller,
            mapping={"name": caller},
        )
        caller.ndb.hide_pending = True

        delay(4.0, _hide_complete, caller.id)


class CmdSneak(Command):
    """
    Move quietly to an adjacent room.

    Usage:
      sneak <direction>
    """

    key = "sneak"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        arg = (self.args or "").strip().lower()
        if not arg:
            caller.msg("Sneak which way?")
            return

        dir_map = {
            "n": "north",
            "s": "south",
            "e": "east",
            "w": "west",
            "ne": "northeast",
            "nw": "northwest",
            "se": "southeast",
            "sw": "southwest",
            "u": "up",
            "d": "down",
        }
        direction = dir_map.get(arg, arg)

        loc = getattr(caller, "location", None)
        if not loc:
            caller.msg("You have nowhere to go.")
            return

        target_exit = None
        for ex in getattr(loc, "contents", None) or []:
            if not getattr(ex, "destination", None):
                continue
            key = (getattr(ex, "key", "") or "").lower()
            aliases = []
            if hasattr(ex, "aliases"):
                try:
                    aliases = [a.lower() for a in ex.aliases.all()]
                except Exception:
                    aliases = []
            if direction == key or direction in aliases:
                target_exit = ex
                break

        if not target_exit or not target_exit.destination:
            caller.msg("You can't sneak that way.")
            return

        destination = target_exit.destination

        ok, destination, err, direction_str = precheck_exit_traversal(target_exit, caller, destination)
        if not ok:
            if err:
                caller.msg(err)
            return

        direction = direction_str or (target_exit.key or "away").strip()

        try:
            from world.rpg.stamina import is_exhausted, spend_stamina, STAMINA_COST_WALK, STAMINA_COST_CRAWL
        except ImportError:
            is_exhausted = lambda _: False
            spend_stamina = lambda _, __: True
            STAMINA_COST_WALK = 1
            STAMINA_COST_CRAWL = 0

        exhausted = is_exhausted(caller)
        try:
            missing = set(getattr(caller.db, "missing_body_parts", []) or [])
        except Exception:
            missing = set()
        leg_lost = bool(missing.intersection({"left thigh", "right thigh", "left foot", "right foot"}))
        try:
            from world.medical.limb_trauma import is_limb_destroyed

            if is_limb_destroyed(caller, "left_leg") or is_limb_destroyed(caller, "right_leg"):
                leg_lost = True
        except Exception:
            pass
        force_crawl = exhausted or leg_lost

        db = getattr(caller, "db", None)
        if db is not None and hasattr(db, "cancel_walking"):
            try:
                del db.cancel_walking
            except Exception:
                db.cancel_walking = False

        from world.rpg import stealth

        was_hidden = stealth.is_hidden(caller)

        if force_crawl:
            spend_stamina(caller, STAMINA_COST_CRAWL)
            delay_secs = CRAWL_DELAY_LEG_TRAUMA if leg_lost else CRAWL_DELAY_EXHAUSTED
            if leg_lost:
                caller.msg(f"You drag yourself {direction}, barely moving.")
            else:
                caller.msg(f"You crawl slowly {direction}.")
        else:
            spend_stamina(caller, STAMINA_COST_WALK)
            delay_secs = WALK_DELAY
            caller.msg(f"You begin moving quietly {direction}.")

        # Origin room messages (sneak-specific)
        if loc:
            from world.rp_features import get_move_display_for_viewer

            viewers = [c for c in loc.contents_get(content_type="character") if c is not caller]
            for viewer in viewers:
                display = get_move_display_for_viewer(caller, viewer)
                if was_hidden:
                    spotted = getattr(caller.db, "stealth_spotted_by", None) or []
                    try:
                        if viewer.id in spotted:
                            viewer.msg(f"|yYou notice {display} slip away towards {direction}.|n")
                    except Exception:
                        pass
                elif force_crawl:
                    if leg_lost:
                        viewer.msg(
                            f"{display} drags along the ground {direction}."
                        )
                    else:
                        viewer.msg(f"{display} crawls slowly {direction}.")
                else:
                    viewer.msg(f"{display} sneaks {direction}.")

        caller.ndb._stealth_move_sneak = True

        cb = _staggered_walk_callback
        if cb:
            delay(delay_secs, cb, caller.id, destination.id)
        else:

            def _fallback_sneak():
                o, d = caller, destination
                if not o or not d:
                    return
                db = getattr(o, "db", None)
                if db is not None and getattr(db, "cancel_walking", False):
                    try:
                        del db.cancel_walking
                    except Exception:
                        db.cancel_walking = False
                    try:
                        if hasattr(o.ndb, "_stealth_move_sneak"):
                            del o.ndb._stealth_move_sneak
                    except Exception:
                        pass
                    return
                sneak = bool(getattr(o.ndb, "_stealth_move_sneak", False))
                o.move_to(d, quiet=sneak)

            delay(delay_secs, _fallback_sneak)


class CmdSearch(Command):
    """
    Search the area carefully for hidden characters.

    Usage:
      search
    """

    key = "search"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        loc = getattr(caller, "location", None)
        if not loc:
            caller.msg("There is nothing to search.")
            return

        now = time.time()
        last = float(getattr(caller.ndb, "_last_search", 0) or 0)
        if now - last < 10.0:
            caller.msg("You need to wait before searching again.")
            return
        caller.ndb._last_search = now

        loc.msg_contents(
            "{name} searches the area carefully.",
            exclude=caller,
            mapping={"name": caller},
        )

        try:
            rid = int(getattr(loc, "id", 0) or 0)
        except Exception:
            rid = 0
        delay(3.0, _search_complete, caller.id, rid)


class CmdUnhide(Command):
    """
    Step out of hiding.

    Usage:
      unhide
    """

    key = "unhide"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        from world.rpg import stealth

        if not stealth.is_hidden(caller):
            caller.msg("You aren't hiding.")
            return
        stealth.reveal(caller, reason="action")
