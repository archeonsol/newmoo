"""
Freight lift cycle management. Each lift has a persistent script on the lift room
that drives dock / transit / dock / transit.

NOTE: Freight lifts run independently of bulkhead seal state (`world.maps.bulkheads`).
A sealed bulkhead blocks walking through the bulkhead room, not the lift itself.
The lift shaft is separate from the pedestrian corridor. If you ride the lift to a
sealed district, you exit at the station and find the bulkhead closed; you can ride
back. This is intentional.
"""

from __future__ import annotations

import random
import time

from evennia import create_object
from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger
from evennia.utils.search import search_object

from evennia.contrib.grid.xyzgrid.xyzroom import (
    MAP_X_TAG_CATEGORY,
    MAP_Y_TAG_CATEGORY,
    MAP_Z_TAG_CATEGORY,
    MAP_XDEST_TAG_CATEGORY,
    MAP_YDEST_TAG_CATEGORY,
    MAP_ZDEST_TAG_CATEGORY,
)

from typeclasses.exits import CityExit
from world.movement.freight_constants import (
    ARRIVAL_MESSAGES,
    DEFAULT_DOCK_DURATION,
    DEFAULT_TRANSIT_DURATION,
    DEPARTURE_MESSAGES,
    DOOR_WARNINGS,
    TRANSIT_MESSAGES_DOWN,
    TRANSIT_MESSAGES_UP,
)


def _tag_city_exit(exit_obj, loc, dest):
    lx, ly, lz = loc.xyz
    dx, dy, dz = dest.xyz
    exit_obj.tags.add(str(lx), category=MAP_X_TAG_CATEGORY)
    exit_obj.tags.add(str(ly), category=MAP_Y_TAG_CATEGORY)
    exit_obj.tags.add(str(lz), category=MAP_Z_TAG_CATEGORY)
    exit_obj.tags.add(str(dx), category=MAP_XDEST_TAG_CATEGORY)
    exit_obj.tags.add(str(dy), category=MAP_YDEST_TAG_CATEGORY)
    exit_obj.tags.add(str(dz), category=MAP_ZDEST_TAG_CATEGORY)


def open_doors(lift, station):
    """Create exits between lift and station; tag exits for CityExit / grid."""
    close_doors(lift)
    if not lift or not station:
        return

    if not hasattr(lift, "xyz") or not hasattr(station, "xyz"):
        logger.log_err("open_doors: lift or station missing xyz tags")
        return

    dest = station
    loc = lift
    ex_out = create_object(
        CityExit,
        key="out",
        aliases=["exit", "leave", "disembark"],
        location=lift,
        destination=dest,
    )
    ex_out.db.is_lift_exit = True
    _tag_city_exit(ex_out, lift, dest)

    ex_in = create_object(
        CityExit,
        key="board",
        aliases=["lift", "enter lift", "freight"],
        location=station,
        destination=lift,
    )
    ex_in.db.is_lift_exit = True
    _tag_city_exit(ex_in, station, lift)

    lift.db._current_exit_out = ex_out.id
    lift.db._current_exit_in = ex_in.id


def close_doors(lift):
    """Remove lift/station exits created by open_doors."""
    for attr in ("_current_exit_out", "_current_exit_in"):
        eid = getattr(lift.db, attr, None)
        if eid:
            results = search_object(f"#{eid}")
            if results:
                try:
                    results[0].delete()
                except Exception as err:
                    logger.log_err(f"close_doors delete exit {eid}: {err}")
        setattr(lift.db, attr, None)


def _get_station(lift, phase):
    if phase == "docked_upper":
        sid = lift.db.upper_station
    else:
        sid = lift.db.lower_station
    if sid:
        results = search_object(f"#{sid}")
        return results[0] if results else None
    return None


def ensure_freight_cycle_script(lift):
    """Attach or return the FreightCycleScript on the lift room."""
    from evennia import create_script

    for scr in lift.scripts.all():
        if scr.key == "freight_cycle":
            return scr
    scr = create_script(
        typeclass="world.movement.freight.FreightCycleScript",
        key="freight_cycle",
        obj=lift,
        interval=5,
        persistent=True,
        autostart=True,
    )
    return scr


def start_freight_cycle(lift):
    """Turn on cycle and ensure doors if docked."""
    lift.db.cycle_active = True
    if lift.db.phase_started is None:
        lift.db.phase_started = time.time()
    scr = ensure_freight_cycle_script(lift)
    try:
        scr.start(interval=5, repeats=0)
    except Exception:
        pass
    phase = lift.db.current_phase or "docked_upper"
    if phase.startswith("docked"):
        if not getattr(lift.db, "_current_exit_out", None):
            st = _get_station(lift, phase)
            if st:
                open_doors(lift, st)


def stop_freight_cycle(lift):
    lift.db.cycle_active = False
    for scr in lift.scripts.all():
        if scr.key == "freight_cycle":
            try:
                scr.stop()
            except Exception:
                pass


class FreightCycleScript(DefaultScript):
    """
    Persistent script driving one freight lift's cycle.
    Attached to the FreightLift room (self.obj).
    """

    def at_script_creation(self):
        self.key = "freight_cycle"
        self.desc = "Drives the freight lift dock/transit cycle."
        self.db_interval = 5
        self.db_persistent = True
        self.db.warnings_sent = []

    def at_repeat(self, **kwargs):
        lift = self.obj
        if not lift or not getattr(lift.db, "cycle_active", False):
            return

        phase = lift.db.current_phase or "docked_upper"
        started = lift.db.phase_started
        if started is None:
            lift.db.phase_started = time.time()
            started = lift.db.phase_started
        elapsed = time.time() - started

        if phase.startswith("docked"):
            dock_dur = lift.db.dock_duration or DEFAULT_DOCK_DURATION
            remaining = dock_dur - elapsed
            sent = list(self.db.warnings_sent or [])
            for threshold in sorted(DOOR_WARNINGS.keys(), reverse=True):
                if remaining <= threshold and threshold not in sent:
                    msg = DOOR_WARNINGS[threshold]
                    lift.msg_contents(msg)
                    station = _get_station(lift, phase)
                    if station:
                        station.msg_contents(msg)
                    sent.append(threshold)
            self.db.warnings_sent = sent

            if elapsed >= dock_dur:
                self._transition_to_transit(lift, phase)

        elif phase.startswith("transit"):
            transit_dur = lift.db.transit_duration or DEFAULT_TRANSIT_DURATION
            last_atmo = getattr(lift.ndb, "_last_freight_atmo", None) or 0
            gap = getattr(lift.ndb, "_freight_atmo_gap", None) or random.randint(20, 40)
            if time.time() - last_atmo > gap:
                pool = TRANSIT_MESSAGES_DOWN if "down" in phase else TRANSIT_MESSAGES_UP
                lift.msg_contents(random.choice(pool))
                lift.ndb._last_freight_atmo = time.time()
                lift.ndb._freight_atmo_gap = random.randint(20, 40)

            if elapsed >= transit_dur:
                self._transition_to_docked(lift, phase)

    def _transition_to_transit(self, lift, current_phase):
        close_doors(lift)

        if current_phase == "docked_upper":
            next_phase = "transit_down"
        else:
            next_phase = "transit_up"

        lift.db.current_phase = next_phase
        lift.db.phase_started = time.time()
        self.db.warnings_sent = []
        lift.ndb._last_freight_atmo = time.time()

        msg = DEPARTURE_MESSAGES.get(next_phase, "|y[FREIGHT] Doors sealed. In transit.|n")
        lift.msg_contents(msg)

        station = _get_station(lift, current_phase)
        if station:
            station.msg_contents("|y[FREIGHT] The lift doors close. The lift departs.|n")

    def _transition_to_docked(self, lift, current_phase):
        if current_phase == "transit_down":
            next_phase = "docked_lower"
            sid = lift.db.lower_station
        else:
            next_phase = "docked_upper"
            sid = lift.db.upper_station

        station = None
        if sid:
            results = search_object(f"#{sid}")
            station = results[0] if results else None

        if not station:
            logger.log_err(f"FreightCycleScript: lift {lift.id} has no station for phase {next_phase}")
            return

        lift.db.current_phase = next_phase
        lift.db.phase_started = time.time()
        self.db.warnings_sent = []

        open_doors(lift, station)

        msg = ARRIVAL_MESSAGES.get(next_phase, "|g[FREIGHT] Arrived. Doors opening.|n")
        lift.msg_contents(msg)
        station.msg_contents("|g[FREIGHT] The lift arrives. Doors opening.|n")


def reset_freight_phase(lift, phase: str):
    """Force a phase (for debugging). Does not open doors automatically unless docked."""
    close_doors(lift)
    lift.db.current_phase = phase
    lift.db.phase_started = time.time()
    scr = ensure_freight_cycle_script(lift)
    scr.db.warnings_sent = []
    if phase.startswith("docked"):
        st = _get_station(lift, phase)
        if st and getattr(lift.db, "cycle_active", False):
            open_doors(lift, st)


def setup_freight_stations(lift, upper_id, lower_id):
    """Set upper/lower station dbrefs (ints or #id strings)."""
    lift.db.upper_station = upper_id
    lift.db.lower_station = lower_id
