"""
Vehicle and Weapon Components — Evennia base_systems.components integration.

Extracts fuel, wear, and drive state from the Vehicle monolith into
isolated Component classes. Each component stores its data under a
prefixed DB attribute key (e.g. "fuel::level") so it never collides
with legacy db.fuel_level etc.

Compatibility shims on Vehicle (see typeclasses/vehicles.py) expose the
old db.* attribute names as properties that delegate here, so all
existing call sites continue to work without modification.

Usage (on Vehicle typeclass):
    from evennia.contrib.base_systems.components import ComponentHolderMixin, ComponentProperty
    from world.vehicle_components import FuelComponent, WearComponent, DriveComponent

    class Vehicle(Object, ComponentHolderMixin):
        fuel  = ComponentProperty("fuel")
        wear  = ComponentProperty("wear")
        drive = ComponentProperty("drive")
"""

from evennia.contrib.base_systems.components import Component, DBField


# ---------------------------------------------------------------------------
# FuelComponent
# ---------------------------------------------------------------------------

class FuelComponent(Component):
    """
    Tracks fuel state: current level, capacity, and fuel type.

    DB keys (prefixed "fuel::"):
        fuel::level     — current fuel (float, 0 – capacity)
        fuel::capacity  — max fuel (float)
        fuel::type      — fuel type string (e.g. "standard", "electric")
        fuel::heat      — engine heat level (float, 0 – overheat_threshold)
        fuel::overheat  — overheat threshold (float)
    """

    name = "fuel"

    level     = DBField(default=100.0)
    capacity  = DBField(default=100.0)
    type      = DBField(default="standard")
    heat      = DBField(default=0.0)
    overheat  = DBField(default=100.0)

    def consume(self, amount):
        """Consume fuel. Returns True if there was enough fuel, False if empty."""
        current = float(self.level or 0)
        if current <= 0:
            return False
        self.level = max(0.0, current - float(amount))
        return True

    def refuel(self, amount, cap=None):
        """Add fuel up to capacity (or optional cap override)."""
        capacity = float(cap or self.capacity or 100)
        self.level = min(capacity, float(self.level or 0) + float(amount))

    @property
    def is_empty(self):
        return float(self.level or 0) <= 0

    @property
    def percent(self):
        cap = float(self.capacity or 100)
        return (float(self.level or 0) / cap * 100) if cap > 0 else 0


# ---------------------------------------------------------------------------
# WearComponent
# ---------------------------------------------------------------------------

class WearComponent(Component):
    """
    Tracks vehicle wear/damage state separate from combat HP.

    DB keys (prefixed "wear::"):
        wear::level     — current wear accumulation (float, 0 = pristine)
        wear::max       — wear threshold before breakdown (float)
    """

    name = "wear"

    level = DBField(default=0.0)
    max   = DBField(default=100.0)

    def accumulate(self, amount):
        """Add wear. Returns True if vehicle is now at or past breakdown threshold."""
        self.level = float(self.level or 0) + float(amount)
        return self.is_broken

    def repair(self, amount):
        """Reduce wear by amount (minimum 0)."""
        self.level = max(0.0, float(self.level or 0) - float(amount))

    @property
    def is_broken(self):
        return float(self.level or 0) >= float(self.max or 100)

    @property
    def percent(self):
        """Wear as a percentage of max (0 = pristine, 100 = broken)."""
        max_w = float(self.max or 100)
        return (float(self.level or 0) / max_w * 100) if max_w > 0 else 0


# ---------------------------------------------------------------------------
# DriveComponent
# ---------------------------------------------------------------------------

class DriveComponent(Component):
    """
    Tracks drive/pilot state: who is driving, passengers, running state.

    DB keys (prefixed "drive::"):
        drive::driver       — Character object or None
        drive::passengers   — list of Character objects
        drive::running      — bool (engine on/off)
        drive::speed_class  — "slow" | "normal" | "fast" | "racing"
        drive::skill        — driving skill key string
    """

    name = "drive"

    driver      = DBField(default=None)
    passengers  = DBField(default=None)   # None → treated as []
    running     = DBField(default=False)
    speed_class = DBField(default="normal")
    skill       = DBField(default="driving")

    def get_passengers(self):
        """Return passengers list, always a list (never None)."""
        return list(self.passengers or [])

    def add_passenger(self, char):
        pax = self.get_passengers()
        if char not in pax:
            pax.append(char)
            self.passengers = pax

    def remove_passenger(self, char):
        pax = self.get_passengers()
        if char in pax:
            pax.remove(char)
            self.passengers = pax

    def set_driver(self, char):
        self.driver = char

    def clear_driver(self):
        self.driver = None

    @property
    def is_occupied(self):
        return self.driver is not None or bool(self.get_passengers())


# ---------------------------------------------------------------------------
# AmmoComponent  (used by CombatWeapon ranged subclasses)
# ---------------------------------------------------------------------------

class AmmoComponent(Component):
    """
    Tracks ammunition state for ranged weapons.

    DB keys (prefixed "ammo::"):
        ammo::current   — rounds currently loaded (int)
        ammo::capacity  — magazine capacity (int)
        ammo::type      — ammo type string (e.g. "sidearm", "longarm", "automatic")
    """

    name = "ammo"

    current  = DBField(default=0)
    capacity = DBField(default=0)
    type     = DBField(default="sidearm")

    def load_rounds(self, rounds):
        """Load rounds into the weapon up to capacity. Returns actual rounds loaded."""
        cap = int(self.capacity or 0)
        cur = int(self.current or 0)
        can_load = max(0, cap - cur)
        loaded = min(int(rounds), can_load)
        self.current = cur + loaded
        return loaded

    def consume(self, count=1):
        """Consume count rounds. Returns True if there were enough rounds."""
        cur = int(self.current or 0)
        if cur < count:
            return False
        self.current = cur - count
        return True

    def unload_rounds(self):
        """Remove all rounds. Returns the count that was unloaded."""
        cur = int(self.current or 0)
        self.current = 0
        return cur

    @property
    def is_empty(self):
        return int(self.current or 0) <= 0

    @property
    def is_full(self):
        return int(self.current or 0) >= int(self.capacity or 0)
