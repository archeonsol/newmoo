"""
Freight lift car (moving room). See world.movement.freight for cycle logic.
"""

import time

from typeclasses.rooms import CityRoom
from world.movement.freight_constants import DEFAULT_DOCK_DURATION, DEFAULT_TRANSIT_DURATION


class FreightLift(CityRoom):
    """
    A moving room that cycles between two stations.

    When docked, dynamic exits link the lift and the station; in transit there are
    no exits from the lift.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.city_level = "lift"
        self.db.lift_id = ""
        self.db.upper_station = None
        self.db.lower_station = None
        self.db.current_phase = "docked_upper"
        self.db.phase_started = None
        self.db.dock_duration = DEFAULT_DOCK_DURATION
        self.db.transit_duration = DEFAULT_TRANSIT_DURATION
        self.db.lift_name = "freight lift"
        self.db.cycle_active = False
        self.db.lift_capacity = None
        self.locks.add("get:false()")

    def return_appearance(self, looker, **kwargs):
        name = self.db.lift_name or "freight lift"
        phase = self.db.current_phase or "docked_upper"
        started = self.db.phase_started or time.time()
        elapsed = time.time() - started

        base = (
            f"|x{'=' * 48}|n\n"
            f"  {name.upper()}\n"
            f"|x{'=' * 48}|n\n\n"
        )

        if phase.startswith("docked"):
            dock_dur = self.db.dock_duration or DEFAULT_DOCK_DURATION
            remaining = max(0, int(dock_dur - elapsed))
            station_name = "upper" if "upper" in phase else "lower"
            base += (
                f"  The doors are open. You are docked at the {station_name} station.\n"
                f"  The lift will depart in approximately {remaining} seconds.\n\n"
                f"  |xUse |wout|x to disembark.|n\n"
            )
        elif phase.startswith("transit"):
            transit_dur = self.db.transit_duration or DEFAULT_TRANSIT_DURATION
            remaining = max(0, int(transit_dur - elapsed))
            direction = "descending" if "down" in phase else "ascending"
            base += (
                f"  The doors are sealed. The lift is {direction}.\n"
                f"  Estimated arrival in {remaining} seconds.\n\n"
                f"  |xThere is nowhere to go. Wait.|n\n"
            )

        chars = [
            c
            for c in self.contents_get(content_type="character")
            if c is not looker
        ]
        if chars:
            char_names = [c.get_display_name(looker) for c in chars]
            base += f"\n  Also here: {', '.join(char_names)}\n"

        return base
