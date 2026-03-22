"""
Resolve specimen collection from rooms, corpses, organs, and characters.
"""
import time

from world.alchemy.ingredients import SPECIMENS, can_collect_from_character

_ROOM_COLLECT_COOLDOWN_SEC = 300


def _find_thermos(caller):
    for o in caller.contents:
        if getattr(o.db, "is_thermos", False):
            return o
    return None


def collect_from_room(caller, specimen_key):
    """Tag category specimen on room must match specimen_key."""
    room = caller.location
    if not room:
        return False, "You are nowhere."
    tags = room.tags.get(category="specimen", return_list=True) or []
    if specimen_key not in tags and specimen_key not in SPECIMENS:
        return False, "You find nothing like that here to sample."
    if specimen_key not in tags:
        return False, "You find nothing like that here to sample."
    spec = SPECIMENS.get(specimen_key)
    if not spec or spec.get("source_type") != "room":
        return False, "That cannot be collected here."
    thermos = _find_thermos(caller)
    if not thermos:
        return False, "You need a specimen thermos."
    if getattr(thermos.db, "specimen", None):
        return False, "Your thermos is already full. Empty it first."
    rid = getattr(room, "id", None)
    if rid is not None:
        cooldown_key = "_collect_cd_%s_%s" % (rid, specimen_key)
        last = float(getattr(caller.ndb, cooldown_key, 0) or 0)
        if time.time() - last < _ROOM_COLLECT_COOLDOWN_SEC:
            return False, "You've already collected from here recently. Give the source time to replenish."
    thermos.db.specimen = specimen_key
    thermos.db.specimen_amount = 1.0
    if rid is not None:
        setattr(caller.ndb, "_collect_cd_%s_%s" % (rid, specimen_key), time.time())
    return True, "You fill the thermos with %s." % spec.get("name", specimen_key)


def collect_from_corpse(caller, corpse):
    from typeclasses.corpse import Corpse

    if not isinstance(corpse, Corpse):
        return False, "That is not a corpse."
    if getattr(corpse.db, "bile_collected", False):
        return False, "This corpse has already been drained."
    thermos = _find_thermos(caller)
    if not thermos:
        return False, "You need a specimen thermos."
    if getattr(thermos.db, "specimen", None):
        return False, "Your thermos is already full."
    thermos.db.specimen = "corpse_bile"
    thermos.db.specimen_amount = 1.0
    corpse.db.bile_collected = True
    return True, "You draw off bile from the corpse into your thermos. It will need refining."


def collect_from_organ(caller, organ_obj):
    thermos = _find_thermos(caller)
    if not thermos:
        return False, "You need a specimen thermos."
    if getattr(thermos.db, "specimen", None):
        return False, "Your thermos is already full."
    okey = getattr(organ_obj.db, "organ_specimen_key", None)
    if not okey:
        return False, "That organ does not yield a useful specimen."
    if okey not in SPECIMENS:
        return False, "Unknown specimen type."
    thermos.db.specimen = okey
    thermos.db.specimen_amount = 1.0
    try:
        organ_obj.delete()
    except Exception:
        pass
    return True, "You extract a specimen into your thermos."


def collect_from_character(caller, target, specimen_key):
    ok, msg = can_collect_from_character(caller, target, specimen_key)
    if not ok:
        return False, msg
    thermos = _find_thermos(caller)
    if not thermos:
        return False, "You need a specimen thermos."
    if getattr(thermos.db, "specimen", None):
        return False, "Your thermos is already full."
    if specimen_key == "spinal_tap":
        if hasattr(target, "at_damage"):
            target.at_damage(None, 10, weapon_key="surgery")
        if hasattr(target, "msg"):
            target.msg("|rSomeone drives a needle into your spine. The pain is extraordinary.|n")
    elif specimen_key == "live_blood":
        if hasattr(target, "at_damage"):
            target.at_damage(None, 3, weapon_key="surgery")
        if hasattr(target, "msg"):
            target.msg("|rA needle pierces your arm. Blood drawn.|n")
    thermos.db.specimen = specimen_key
    thermos.db.specimen_amount = 1.0
    sp = SPECIMENS.get(specimen_key, {})
    return True, "You obtain: %s." % sp.get("name", specimen_key)
