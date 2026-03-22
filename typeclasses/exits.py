"""
Exits

Exits are connectors between Rooms. An exit always has a destination property
set and has a single command defined on itself with the same name as its key,
for allowing Characters to traverse the exit to its destination.

Movement is staggered for RP: "You begin walking north" then 3–4 seconds later the move completes.
"""

from evennia.utils import delay
from evennia.objects.objects import DefaultExit

from .objects import ObjectParent
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


class Exit(ObjectParent, DefaultExit):
    """
    Exits are connectors between rooms. Movement is staggered: you see "You begin walking X"
    then after a short delay you arrive (for RP). Exhausted characters crawl (slower; stamina cost already 0).
    """

    def at_traverse(self, traversing_object, destination):
        if not destination:
            super().at_traverse(traversing_object, destination)
            return
        if getattr(traversing_object.ndb, "hide_pending", False):
            traversing_object.ndb.hide_pending = False
            traversing_object.msg("|yYour attempt to hide is interrupted.|n")
            return

        ok, destination, err, direction_str = precheck_exit_traversal(self, traversing_object, destination)
        if not ok:
            if err:
                traversing_object.msg(err)
            return
        direction = direction_str or (self.key or "away").strip()

        try:
            from world.rpg.stamina import is_exhausted, spend_stamina, STAMINA_COST_WALK, STAMINA_COST_CRAWL
        except ImportError:
            is_exhausted = lambda _: False
            spend_stamina = lambda _, __: True
            STAMINA_COST_WALK = 1
            STAMINA_COST_CRAWL = 0
        exhausted = is_exhausted(traversing_object)
        # Characters missing a leg/foot, or with an unsalvageable leg, must crawl (drag).
        try:
            missing = set(getattr(getattr(traversing_object, "db", None), "missing_body_parts", []) or [])
        except Exception:
            missing = set()
        leg_lost = bool(missing.intersection({"left thigh", "right thigh", "left foot", "right foot"}))
        try:
            from world.medical.limb_trauma import is_limb_destroyed
            if is_limb_destroyed(traversing_object, "left_leg") or is_limb_destroyed(traversing_object, "right_leg"):
                leg_lost = True
        except Exception:
            pass
        force_crawl = exhausted or leg_lost

        # Starting a new move clears any previous "stop walking" request so
        # that fresh walks work normally.
        db = getattr(traversing_object, "db", None)
        if db is not None and hasattr(db, "cancel_walking"):
            try:
                del db.cancel_walking
            except Exception:
                db.cancel_walking = False

        if force_crawl:
            spend_stamina(traversing_object, STAMINA_COST_CRAWL)
            delay_secs = CRAWL_DELAY_LEG_TRAUMA if leg_lost else CRAWL_DELAY_EXHAUSTED
            if leg_lost:
                traversing_object.msg(f"You drag yourself {direction}, barely moving.")
            else:
                traversing_object.msg(f"You crawl slowly {direction}.")
        else:
            spend_stamina(traversing_object, STAMINA_COST_WALK)
            delay_secs = WALK_DELAY
            traversing_object.msg(f"You begin walking {direction}.")

        # Announce staggered move to others in the room with recog-aware names.
        loc = traversing_object.location
        if loc:
            from world.rp_features import get_move_display_for_viewer
            viewers = [c for c in loc.contents_get(content_type="character") if c is not traversing_object]
            for viewer in viewers:
                display = get_move_display_for_viewer(traversing_object, viewer)
                if force_crawl:
                    viewer.msg(
                        f"{display} drags along the ground {direction}."
                        if leg_lost
                        else f"{display} crawls slowly {direction}."
                    )
                else:
                    viewer.msg(f"{display} begins walking {direction}.")
        cb = _staggered_walk_callback
        if cb:
            delay(delay_secs, cb, traversing_object.id, destination.id)
        else:
            # Never move instantly — same delay as normal stagger (fixes missing callback = teleport bug).
            def _fallback_move():
                o, d = traversing_object, destination
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
                victim = getattr(getattr(o, "db", None), "grappling", None)
                if victim and hasattr(victim, "move_to"):
                    victim.move_to(d, quiet=True)
                    if d and hasattr(d, "contents_get"):
                        for v in d.contents_get(content_type="character"):
                            if v in (o, victim):
                                continue
                            vname = victim.get_display_name(v) if hasattr(victim, "get_display_name") else victim.name
                            oname = o.get_display_name(v) if hasattr(o, "get_display_name") else o.name
                            v.msg("%s is dragged in by %s." % (vname, oname))

            delay(delay_secs, _fallback_move)
        return
