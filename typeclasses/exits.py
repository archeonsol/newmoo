"""
Exits

Exits are connectors between Rooms. An exit always has a destination property
set and has a single command defined on itself with the same name as its key,
for allowing Characters to traverse the exit to its destination.

Movement is staggered for RP: "You begin walking north" then 3–4 seconds later the move completes.
"""

from evennia.utils import delay
from evennia.objects.objects import DefaultExit
from evennia.contrib.grid.xyzgrid.xyzroom import XYZExit

from .objects import ObjectParent
from typeclasses.exit_traversal import precheck_exit_traversal

try:
    from world.rpg.staggered_movement import (
        WALK_DELAY,
        CRAWL_DELAY_EXHAUSTED,
        CRAWL_DELAY_LEG_TRAUMA,
        _staggered_walk_callback,
        append_walk_queue,
        begin_staggered_walk_segment,
        clear_stagger_walk_pending,
        is_staggered_walk_pending,
        normalize_move_direction,
        set_stagger_walk_pending,
        stagger_walk_direction_conflict,
    )
except ImportError:
    WALK_DELAY = 3.5
    CRAWL_DELAY_EXHAUSTED = 8.5
    CRAWL_DELAY_LEG_TRAUMA = 16.0
    _staggered_walk_callback = None
    append_walk_queue = None
    begin_staggered_walk_segment = None
    clear_stagger_walk_pending = None
    is_staggered_walk_pending = None
    normalize_move_direction = None
    set_stagger_walk_pending = None
    stagger_walk_direction_conflict = None


class Exit(ObjectParent, DefaultExit):
    """
    Exits are connectors between rooms. Movement is staggered: you see "You begin walking X"
    then after a short delay you arrive (for RP). Exhausted characters crawl (slower; stamina cost already 0).

    Street-room look (room_display_mode=street):
      db.exit_narrative — optional prose for this exit in the bottom exit line, e.g.
      "The street continues north". The exit alias is always shown after it as (n) in bold white.
      If unset, that exit uses the default "There are exits to the …" phrasing with the others.

    Optional staggered-move messages (fallback to engine defaults if unset):
      db.move_leave_others — text after the mover's display name for others in the room when
        they start walking/crawling (recog applied automatically). E.g. "crawls into the tunnels to the west."
      db.move_leave_self — line for the mover only; optional {direction} placeholder.
      db.move_arrive_others — same pattern for people already in the destination when you arrive.
      db.move_arrive_self — line for the mover on arrival; optional {direction}.
      db.move_depart_others — optional line for others when the move completes (replaces "goes <dir>").
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.exit_narrative = None
        self.db.move_leave_others = None
        self.db.move_leave_self = None
        self.db.move_arrive_others = None
        self.db.move_arrive_self = None
        self.db.move_depart_others = None

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
        self._after_precheck_ok(traversing_object, destination)
        direction = direction_str or (self.key or "away").strip()
        new_norm = normalize_move_direction(direction) if normalize_move_direction else None

        # Queue further steps while a staggered walk is already counting down.
        if is_staggered_walk_pending and is_staggered_walk_pending(traversing_object) and append_walk_queue:
            append_walk_queue(traversing_object, new_norm)
            traversing_object.msg(f"You add {direction} to your route after your current step.")
            return

        if begin_staggered_walk_segment:
            begin_staggered_walk_segment(traversing_object, destination, direction, new_norm, exit_obj=self)
        return

    def _after_precheck_ok(self, traversing_object, destination):
        """Hook for subclasses (e.g. CityExit stealth)."""
        return


def _clear_shaft_confirm(char_id):
    from evennia.utils.search import search_object

    results = search_object(f"#{char_id}")
    if results:
        ch = results[0]
        ch.ndb._confirmed_shaft_entry = False
        ch.ndb._confirmed_shaft_direction = None


class CityExit(XYZExit, Exit):
    """
    Grid exit with XYZ tags. Staggered movement comes from Exit; coordinate
    queries use XYZExit.
    """

    def _after_precheck_ok(self, traversing_object, destination):
        if not getattr(traversing_object.db, "stealth_hidden", False):
            return
        if getattr(traversing_object.ndb, "_sneaking", False):
            return
        if getattr(traversing_object.ndb, "_stealth_move_sneak", False):
            return
        try:
            from world.rpg.stealth import reveal

            reveal(traversing_object, reason="action")
        except Exception:
            pass


class VerticalExit(CityExit):
    """Up/down between levels (lifts, stairs). Sealed gate bulkheads use `exit.db.gate_bulkhead`."""


class ShaftOpening(CityExit):
    """Exit into an air room; requires confirming the direction twice."""

    def at_traverse(self, traversing_object, destination):
        if not destination:
            super().at_traverse(traversing_object, destination)
            return
        if getattr(traversing_object.ndb, "hide_pending", False):
            traversing_object.ndb.hide_pending = False
            traversing_object.msg("|yYour attempt to hide is interrupted.|n")
            return

        dir_key = (self.key or "").strip().lower()
        if not getattr(traversing_object.ndb, "_confirmed_shaft_entry", False) or getattr(
            traversing_object.ndb, "_confirmed_shaft_direction", None
        ) != dir_key:
            traversing_object.msg(
                "|rThat leads to an open shaft. You will fall. Type the direction again to confirm.|n"
            )
            traversing_object.ndb._confirmed_shaft_entry = True
            traversing_object.ndb._confirmed_shaft_direction = dir_key
            delay(10, _clear_shaft_confirm, traversing_object.id)
            return

        traversing_object.ndb._confirmed_shaft_entry = False
        traversing_object.ndb._confirmed_shaft_direction = None
        super().at_traverse(traversing_object, destination)
