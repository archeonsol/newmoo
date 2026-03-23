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
        divider = f"|x{'=' * 48}|n"

        if phase.startswith("docked"):
            dock_dur = self.db.dock_duration or DEFAULT_DOCK_DURATION
            remaining = max(0, int(dock_dur - elapsed))
            station_name = "upper" if "upper" in phase else "lower"
            status = (
                f"{divider}\n"
                f"  {name.upper()}\n"
                f"{divider}\n"
                f"  The doors are open. The car is docked at the {station_name} station.\n"
                f"  Departure in approximately {remaining} seconds.\n"
                f"{divider}"
            )
        elif phase.startswith("transit"):
            transit_dur = self.db.transit_duration or DEFAULT_TRANSIT_DURATION
            remaining = max(0, int(transit_dur - elapsed))
            direction = "descending" if "down" in phase else "ascending"
            status = (
                f"{divider}\n"
                f"  {name.upper()}\n"
                f"{divider}\n"
                f"  The doors are sealed. The car is {direction}.\n"
                f"  Arrival in approximately {remaining} seconds.\n"
                f"{divider}"
            )
        else:
            status = ""

        # Build the room display manually so the lift status sits between
        # the room description and the characters/objects/exits sections.
        header = self.get_display_header(looker, **kwargs)
        desc = self.get_display_desc(looker, **kwargs)
        things = self.get_display_things(looker, **kwargs)
        furniture = self.get_display_furniture(looker, **kwargs)
        characters = self.get_display_characters(looker, **kwargs)
        footer = self.get_display_footer(looker, **kwargs)
        exits = self.get_display_exits(looker, **kwargs)
        ambient = self.get_display_ambient(looker, **kwargs)

        head = "\n".join([p for p in (header, desc) if p])
        parts = [head]
        if status:
            parts.append(status)
        if ambient:
            parts.append(ambient)
        if things:
            parts.append(things)
        if furniture:
            parts.append(furniture)
        tail = "\n".join([p for p in (characters, exits, footer) if p])
        if tail:
            parts.append(tail)

        appearance = "\n\n".join([p for p in parts if p])
        return self.format_appearance(appearance, looker, **kwargs)
