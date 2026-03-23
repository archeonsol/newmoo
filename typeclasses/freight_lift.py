"""
Freight lift car (moving room). See world.movement.freight for cycle logic.

The FreightLift exposes a phase_machine property that returns a LiftStateMachine
for validated phase transitions. The machine is non-persistent (ndb) and inferred
from db.current_phase on every reload.

States:    docked_upper → transit_down → docked_lower → transit_up → docked_upper
Triggers:  depart_down, arrive_lower, depart_up, arrive_upper
"""

import logging
import time

from transitions import Machine

from typeclasses.rooms import CityRoom
from world.movement.freight_constants import DEFAULT_DOCK_DURATION, DEFAULT_TRANSIT_DURATION

logger = logging.getLogger("evennia")

# ---------------------------------------------------------------------------
# Lift FSM
# ---------------------------------------------------------------------------

LIFT_STATES = ["docked_upper", "transit_down", "docked_lower", "transit_up"]

LIFT_TRANSITIONS = [
    {"trigger": "depart_down",  "source": "docked_upper",  "dest": "transit_down"},
    {"trigger": "arrive_lower", "source": "transit_down",  "dest": "docked_lower"},
    {"trigger": "depart_up",    "source": "docked_lower",  "dest": "transit_up"},
    {"trigger": "arrive_upper", "source": "transit_up",    "dest": "docked_upper"},
]

_VALID_LIFT_STATES = set(LIFT_STATES)


class LiftStateMachine:
    """
    Non-persistent FSM helper for a FreightLift instance.

    Attach to lift.ndb._phase_machine via get_lift_fsm().
    After each transition, db.current_phase is updated automatically.

    Usage:
        fsm = lift.phase_machine
        fsm.depart_down()    # docked_upper → transit_down
        fsm.arrive_lower()   # transit_down → docked_lower
        print(fsm.state)     # "docked_lower"
    """

    def __init__(self, lift):
        self.lift = lift
        initial = self._infer_initial()
        self.machine = Machine(
            model=self,
            states=LIFT_STATES,
            transitions=LIFT_TRANSITIONS,
            initial=initial,
            ignore_invalid_triggers=True,
            after_state_change="_sync_db_phase",
        )

    def _infer_initial(self) -> str:
        phase = getattr(self.lift.db, "current_phase", None) or "docked_upper"
        return phase if phase in _VALID_LIFT_STATES else "docked_upper"

    def _sync_db_phase(self):
        """Write the current FSM state back to db.current_phase."""
        try:
            self.lift.db.current_phase = self.state
        except Exception as exc:
            logger.warning(f"[LiftStateMachine] db sync failed for {self.lift}: {exc}")


def get_lift_fsm(lift) -> LiftStateMachine:
    """
    Return the LiftStateMachine for a FreightLift, creating it if needed.
    Stored in lift.ndb._phase_machine (non-persistent; recreated on reload).
    """
    fsm = getattr(lift.ndb, "_phase_machine", None)
    if fsm is None or not isinstance(fsm, LiftStateMachine):
        fsm = LiftStateMachine(lift)
        lift.ndb._phase_machine = fsm
    return fsm


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

        # Default look-details for the freight lift
        self.add_detail(
            "control panel",
            "A battered steel panel set into the wall beside the doors. Buttons for "
            "upper and lower stations, a stop lever, and an emergency release handle. "
            "Most of the labels have been worn off. The panel hums faintly.",
        )
        self.add_detail(
            "capacity plate",
            "A stamped metal plate riveted near the door frame. It reads a maximum "
            "load in kilograms — the number is partially obscured by rust, but the "
            "warning beneath it is clear: OVERLOADING WILL VOID SAFETY CERTIFICATION.",
        )

    @property
    def phase_machine(self) -> LiftStateMachine:
        """
        Return the LiftStateMachine for this lift (created on first access).
        Stored in ndb._phase_machine (non-persistent; recreated on reload).
        Use this to trigger validated phase transitions:
            self.phase_machine.depart_down()
            self.phase_machine.arrive_lower()
        """
        return get_lift_fsm(self)

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
