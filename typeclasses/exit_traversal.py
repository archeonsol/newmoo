"""
Shared exit traversal checks (used by typeclasses.exits.Exit and commands.stealth_cmds.CmdSneak).
Returns (ok, destination_out, err_msg).
"""
import random
from evennia.utils import logger

# Cached VOID_ROOM_ID — loaded once from ServerConfig on first use.
# Set to _VOID_UNSET sentinel so None is a valid "no void room" value.
_VOID_UNSET = object()
_void_room_id_cache = _VOID_UNSET

_VOID_CACHE_KEY = "exit_traversal:void_room_id"


def _get_void_room_id():
    """Return the void room id (int or None), caching after the first DB read.
    Checks diskcache first so the value survives server reloads."""
    global _void_room_id_cache
    if _void_room_id_cache is not _VOID_UNSET:
        return _void_room_id_cache
    # Try diskcache first
    try:
        from world.cache import get as _cache_get
        cached = _cache_get(_VOID_CACHE_KEY, default=_VOID_UNSET)
        if cached is not _VOID_UNSET:
            _void_room_id_cache = cached
            return _void_room_id_cache
    except Exception:
        pass
    # Fall back to DB read
    try:
        from evennia.server.models import ServerConfig
        val = ServerConfig.objects.conf("VOID_ROOM_ID", default=None)
        _void_room_id_cache = int(val) if val is not None else None
    except Exception:
        _void_room_id_cache = None
    # Persist to diskcache for future reloads
    try:
        from world.cache import set as _cache_set
        _cache_set(_VOID_CACHE_KEY, _void_room_id_cache)
    except Exception:
        pass
    return _void_room_id_cache


def invalidate_void_room_id_cache():
    """Call this whenever VOID_ROOM_ID is changed in ServerConfig."""
    global _void_room_id_cache
    _void_room_id_cache = _VOID_UNSET
    try:
        from world.cache import delete as _cache_delete
        _cache_delete(_VOID_CACHE_KEY)
    except Exception:
        pass


def precheck_exit_traversal(exit_obj, traversing_object, destination):
    """
    Validate traversal before staggered move or sneak.
    Returns (True, destination, None) or (False, destination, error_message).
    """
    if not destination:
        return False, destination, None, None

    if getattr(traversing_object.db, "sitting_on", None):
        return False, destination, "You need to stand up first.", None
    if getattr(traversing_object.db, "lying_on", None) or getattr(traversing_object.db, "lying_on_table", None):
        return False, destination, "You need to get up first.", None

    grappled_by = getattr(traversing_object.db, "grappled_by", None)
    if grappled_by:
        grappler_name = (
            grappled_by.get_display_name(traversing_object)
            if hasattr(grappled_by, "get_display_name")
            else getattr(grappled_by, "key", "someone")
        )
        return False, destination, f"You're locked in {grappler_name}'s grasp. Use |wresist|n to break free.", None

    try:
        from world.death import is_flatlined

        if is_flatlined(traversing_object):
            return False, destination, "|rYou are dying. There is nothing you can do.|n", None
    except ImportError:
        pass

    try:
        from world.combat import is_in_combat

        if is_in_combat(traversing_object):
            return False, destination, "You're in combat! Use |wflee|n or |wflee <direction>|n to try to break away.", None
    except ImportError:
        if getattr(traversing_object.db, "combat_target", None) is not None:
            return False, destination, "You're in combat! Use |wflee|n or |wflee <direction>|n to try to break away.", None

    if getattr(traversing_object.db, "voided", False):
        void_id = _get_void_room_id()
        if void_id is not None and getattr(destination, "id", None) != void_id:
            return False, destination, "|rYou cannot leave the void.|n", None

    try:
        from evennia.utils.utils import inherits_from
        from typeclasses.freight_lift import FreightLift

        if destination and inherits_from(destination, FreightLift):
            cap = getattr(destination.db, "lift_capacity", None)
            if cap is not None:
                try:
                    cap_i = int(cap)
                except (TypeError, ValueError):
                    cap_i = None
                if cap_i is not None:
                    n = len(destination.contents_get(content_type="character"))
                    if n >= cap_i:
                        return (
                            False,
                            destination,
                            "The lift is at capacity. Wait for the next cycle.",
                            None,
                        )
    except Exception:
        pass

    try:
        from world.rpg.factions.doors import staff_bypass as _faction_staff

        if _faction_staff(traversing_object):
            pass
        elif getattr(exit_obj.db, "bulkhead_locked", False):
            return (
                False,
                destination,
                "|rThe blast door is sealed. Two feet of steel between you and the other side. "
                "You are not getting through.|n",
                None,
            )
    except Exception:
        logger.log_trace("precheck_exit_traversal: bulkhead_locked check failed")

    try:
        from evennia.utils.utils import inherits_from
        from typeclasses.rooms import GateRoom
        from world.rpg.factions.doors import staff_bypass as _faction_staff

        if _faction_staff(traversing_object):
            pass
        else:
            if getattr(exit_obj.db, "gate_bulkhead", False):
                for room in (getattr(exit_obj, "location", None), destination):
                    if room and inherits_from(room, GateRoom) and getattr(room.db, "sealed", False):
                        return (
                            False,
                            destination,
                            "|rThe bulkhead is sealed. You cannot pass.|n",
                            None,
                        )
    except Exception:
        logger.log_trace("precheck_exit_traversal: gate_bulkhead check failed")

    try:
        from world.rpg.factions import is_faction_member
        from world.rpg.factions.membership import get_member_rank
        from world.rpg.factions.doors import staff_bypass as _faction_staff

        if _faction_staff(traversing_object):
            pass
        else:
            door = getattr(exit_obj.db, "door", None)
            if door and not getattr(exit_obj.db, "door_open", False):
                dname = getattr(exit_obj.db, "door_name", None) or "door"
                if getattr(exit_obj.db, "door_locked", None):
                    return False, destination, f"The {dname} is locked.", None
                if getattr(exit_obj.db, "bioscan", None):
                    dk = (exit_obj.key or "that way").strip()
                    return False, destination, f"The {dname} requires bioscan verification. Use: verify {dk}", None
                return False, destination, f"The {dname} is closed.", None

            fk = getattr(exit_obj.db, "faction_required", None)
            if fk:
                min_r = int(getattr(exit_obj.db, "faction_required_rank", None) or 1)
                if not is_faction_member(traversing_object, fk):
                    return False, destination, "|rAccess denied. Wrong faction clearance.|n", None
                if get_member_rank(traversing_object, fk) < min_r:
                    return False, destination, "|rAccess denied. Insufficient rank.|n", None
    except Exception:
        logger.log_trace("precheck_exit_traversal: door/faction check failed")

    dest_out = destination
    direction_str = (getattr(exit_obj, "key", None) or "away").strip()
    try:
        drunk_level = int(getattr(getattr(traversing_object, "db", None), "drunk_level", 0) or 0)
    except Exception:
        drunk_level = 0
    if drunk_level >= 3:
        if random.random() < 0.25:
            loc = getattr(traversing_object, "location", None)
            exits_here = [
                o
                for o in (getattr(loc, "contents", None) or [])
                if getattr(o, "destination", None)
            ]
            if exits_here:
                stagger_exit = random.choice(exits_here)
                if getattr(stagger_exit, "destination", None):
                    dest_out = stagger_exit.destination
                    direction_str = (stagger_exit.key or "away").strip()

    try:
        from world.rpg.survival import apply_move_hunger_thirst

        apply_move_hunger_thirst(traversing_object, traversing_object.location, dest_out)
    except Exception:
        pass

    return True, dest_out, None, direction_str
