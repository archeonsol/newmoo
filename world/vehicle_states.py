"""
Vehicle finite state machine via transitions.

Provides VehicleStateMachine — a non-persistent helper that wraps a Vehicle
instance and enforces valid state transitions. The machine is attached as
vehicle.ndb._state_machine on first access via get_vehicle_fsm().

State storage: db.engine_running, db.autopilot_active, db.vehicle_destroyed
remain authoritative. The FSM reads these flags to infer its initial state
and fires after-callbacks to keep them in sync when transitions are triggered.

States:
    parked      — engine off, not moving
    running     — engine on, driver in control
    autopilot   — engine on, autopilot routing
    destroyed   — vehicle destroyed (terminal)

Transitions:
    start_engine        parked → running
    stop_engine         running/autopilot → parked
    engage_autopilot    running → autopilot
    disengage_autopilot autopilot → running
    destroy             * → destroyed

Non-breaking guarantees:
    - ignore_invalid_triggers=True: invalid trigger calls are silent no-ops.
    - The FSM does NOT replace any existing db.* flag writes. Existing code
      that sets db.engine_running directly still works; the FSM is advisory.
    - get_vehicle_fsm(vehicle) always returns a valid machine even if the
      vehicle is in an unexpected state (defaults to 'parked').

Usage:
    from world.vehicle_states import get_vehicle_fsm
    fsm = get_vehicle_fsm(vehicle)
    fsm.start_engine()       # parked → running
    fsm.engage_autopilot()   # running → autopilot
    print(fsm.state)         # "autopilot"
"""

import logging

from transitions import Machine

logger = logging.getLogger("evennia")

VEHICLE_STATES = ["parked", "running", "autopilot", "destroyed"]

VEHICLE_TRANSITIONS = [
    {
        "trigger": "start_engine",
        "source": "parked",
        "dest": "running",
    },
    {
        "trigger": "stop_engine",
        "source": ["running", "autopilot"],
        "dest": "parked",
    },
    {
        "trigger": "engage_autopilot",
        "source": "running",
        "dest": "autopilot",
    },
    {
        "trigger": "disengage_autopilot",
        "source": "autopilot",
        "dest": "running",
    },
    {
        "trigger": "destroy",
        "source": "*",
        "dest": "destroyed",
    },
]


def _infer_initial_state(vehicle) -> str:
    """
    Infer the initial FSM state from the vehicle's current db flags.
    Falls back to 'parked' for any unexpected combination.
    """
    if getattr(vehicle.db, "vehicle_destroyed", False):
        return "destroyed"
    if getattr(vehicle.db, "autopilot_active", False):
        return "autopilot"
    if getattr(vehicle.db, "engine_running", False):
        return "running"
    return "parked"


class VehicleStateMachine:
    """
    Non-persistent FSM helper for a Vehicle instance.

    Attach to vehicle.ndb._state_machine via get_vehicle_fsm().
    Do not instantiate directly.
    """

    def __init__(self, vehicle):
        self.vehicle = vehicle
        initial = _infer_initial_state(vehicle)
        self.machine = Machine(
            model=self,
            states=VEHICLE_STATES,
            transitions=VEHICLE_TRANSITIONS,
            initial=initial,
            ignore_invalid_triggers=True,
            after_state_change="_sync_db_flags",
        )

    def _sync_db_flags(self):
        """
        Sync db.* flags to match the current FSM state.
        Called automatically after every successful state transition.
        """
        state = self.state
        try:
            self.vehicle.db.engine_running = state in ("running", "autopilot")
            self.vehicle.db.autopilot_active = state == "autopilot"
            self.vehicle.db.vehicle_destroyed = state == "destroyed"
        except Exception as exc:
            logger.warning(f"[VehicleStateMachine] db sync failed for {self.vehicle}: {exc}")

    def on_enter_destroyed(self):
        """Log vehicle destruction for debugging."""
        logger.debug(f"[VehicleStateMachine] {self.vehicle} entered destroyed state.")


def get_vehicle_fsm(vehicle) -> VehicleStateMachine:
    """
    Return the VehicleStateMachine for a vehicle, creating it if needed.

    The machine is stored in vehicle.ndb._state_machine (non-persistent).
    It is recreated on every server reload, inferring state from db.* flags.

    Args:
        vehicle: A Vehicle typeclass instance.

    Returns:
        VehicleStateMachine: The FSM helper for this vehicle.
    """
    fsm = getattr(vehicle.ndb, "_state_machine", None)
    if fsm is None or not isinstance(fsm, VehicleStateMachine):
        fsm = VehicleStateMachine(vehicle)
        vehicle.ndb._state_machine = fsm
    return fsm
