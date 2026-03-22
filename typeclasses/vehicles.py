"""
Vehicles: drivable objects with an interior room (or open motorcycles). Enter/exit, start/stop engine,
drive / fly <dir>. Uses driving or piloting skill. Interior is a separate room for enclosed types;
when you drive the vehicle moves and exits put you at the vehicle's new location.

Each enclosed vehicle has exactly ONE persistent interior. Items dropped inside stay when you exit.
"""
import re

from typeclasses.objects import Object
from evennia.utils.create import create_object
from evennia.utils.search import search_tag, search_object
from evennia.objects.objects import DefaultExit

# Tag used to find an interior by vehicle id (category = str(vehicle.id)).
VEHICLE_INTERIOR_TAG = "vehicle_interior"
VEHICLE_ACCESS_CAT = "vehicle_access"

from .rooms import Room  # noqa: E402

try:
    from world.vehicle_parts import (
        default_parts,
        default_part_types,
        get_part_condition as _get_part_condition,
        set_part_condition as _set_part_condition,
        damage_part as _damage_part,
        repair_part as _repair_part,
        can_start_engine,
        roll_stall_chance,
        drive_failure_modifier,
        VEHICLE_PART_IDS,
        PART_DISPLAY_NAMES,
        condition_description as _condition_description,
    )
except ImportError:
    default_parts = lambda: {}
    default_part_types = lambda: {}
    _get_part_condition = lambda v, p: 100
    _set_part_condition = lambda v, p, x: None
    _damage_part = lambda v, p, a: 100
    _repair_part = lambda v, p, a: 100
    can_start_engine = lambda v: (True, "")
    roll_stall_chance = lambda v: False
    drive_failure_modifier = lambda v: 0.0
    VEHICLE_PART_IDS = []
    PART_DISPLAY_NAMES = {}
    _condition_description = lambda c: "ok"


# Reuse room's default-welcome check for outside view
_DEFAULT_WELCOME_MARKER = "evennia.com"
_DEFAULT_PLACE_DESC = "A place. Nothing much to note."


def vehicle_label(vehicle):
    """Short display name for messages (vehicle_name attr or object key)."""
    if not vehicle:
        return "vehicle"
    return (getattr(vehicle.db, "vehicle_name", None) or getattr(vehicle, "key", None) or "vehicle").strip()


def _room_allows_vehicle_tags(room) -> bool:
    if not room or not hasattr(room, "tags"):
        return False
    t = room.tags
    return t.has("street", category=VEHICLE_ACCESS_CAT) or t.has(
        "tunnel", category=VEHICLE_ACCESS_CAT
    ) or t.has("aerial", category=VEHICLE_ACCESS_CAT)


def _can_vehicle_enter(vehicle, destination):
    """Check if a vehicle type is allowed in the destination room. Returns (allowed: bool, reason: str).

    Drivable surfaces use tags with category ``vehicle_access`` only (e.g. ``street``, ``tunnel``, ``aerial``).
    """
    if not destination:
        return False, "There is nowhere to go."

    if destination.tags.has("no_vehicle", category=VEHICLE_ACCESS_CAT):
        return False, "You can't drive there."

    vehicle_type = getattr(vehicle.db, "vehicle_type", None) or "ground"

    if vehicle_type in ("ground", "motorcycle"):
        if destination.tags.has("street", category=VEHICLE_ACCESS_CAT) or destination.tags.has(
            "tunnel", category=VEHICLE_ACCESS_CAT
        ):
            return True, ""
        return False, "You can't drive there — no road."

    if vehicle_type == "aerial":
        if destination.tags.has("aerial", category=VEHICLE_ACCESS_CAT) or destination.tags.has(
            "street", category=VEHICLE_ACCESS_CAT
        ):
            return True, ""
        return False, "You can't fly there."

    return False, "Unknown vehicle type."


def _can_vehicle_be_placed_in_room(vehicle, room):
    """Vehicles may only be placed on valid vehicle-access tiles (e.g. drop, spawn)."""
    if not room:
        return False, "Nowhere to place it."
    return _can_vehicle_enter(vehicle, room)


class VehicleInterior(Room):
    """
    Room representing the inside of a vehicle. db.vehicle points to the Vehicle object.
    No location (rooms don't have one). Movement is via the drive command.
    """

    default_description = (
        "Worn upholstery, a faint smell of oil and old vinyl. The steering column and dash sit in front of you; "
    )

    def _exterior_room(self):
        """The room where the vehicle is (the outside world)."""
        vehicle = self.db.vehicle
        return getattr(vehicle, "location", None) if vehicle else None

    def _exterior_exits(self):
        """List of exit names (e.g. ['south', 'east']) from the vehicle's current location."""
        room = self._exterior_room()
        if not room:
            return []
        return [
            (obj.key or "").strip() or "out"
            for obj in (room.contents or [])
            if isinstance(obj, DefaultExit) and getattr(obj, "destination", None)
        ]

    def _exterior_display_desc(self, room, looker, **kwargs):
        """Get the exterior room's description, with default substitution for stock welcome text."""
        if hasattr(room, "get_display_desc"):
            return room.get_display_desc(looker, **kwargs)
        raw = (room.db.desc or getattr(room, "default_description", "") or "").strip()
        if not raw or _DEFAULT_WELCOME_MARKER.lower() in raw.lower():
            return getattr(room, "default_description", _DEFAULT_PLACE_DESC) or _DEFAULT_PLACE_DESC
        return raw

    def _exterior_appearance_as_look(self, room, looker, **kwargs):
        """
        Full room readout as if `look` were used while standing in that room
        (header, desc, things, furniture, people, exits, footer).

        You are not in that room, so omit your own @lp line (no bogus 'You are standing here').
        """
        if not room:
            return ""
        kw = dict(kwargs)
        kw["include_looker"] = False
        try:
            if hasattr(room, "return_appearance"):
                snap = room.return_appearance(looker, **kw) or ""
            else:
                snap = self._exterior_display_desc(room, looker, **kwargs)
        except Exception:
            snap = self._exterior_display_desc(room, looker, **kwargs)
        return self._sanitize_exterior_snapshot(snap)

    @staticmethod
    def _sanitize_exterior_snapshot(text):
        """Remove bogus self-lines and OOC exit aliases (|w(n)|n) from the outside-room snapshot."""
        if not text:
            return ""
        out_lines = []
        for line in text.split("\n"):
            s = line.strip()
            if s in ("You are standing here.", "You are standing here"):
                continue
            if "here are exits to the" in line.lower():
                line = re.sub(r"\s*\|w\([^)]*\)\|n", "", line)
                line = re.sub(r"  +", " ", line)
            out_lines.append(line)
        return "\n".join(out_lines).strip()

    def _windows_intro_line(self, vehicle):
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        if vt == "aerial":
            return "|wYou see this through the closed windows:|n"
        return "|wYou see this through the windscreen:|n"

    @staticmethod
    def _hud_bar(pct, width=6):
        """Block bar 0–100; color by band (green / amber / red)."""
        pct = max(0, min(100, int(pct)))
        filled = max(0, min(width, round(width * pct / 100.0)))
        empty = width - filled
        if pct < 25:
            col = "|550"
        elif pct < 50:
            col = "|530"
        else:
            col = "|050"
        return f"{col}{'█' * filled}{'░' * empty}|n"

    def _vehicle_status_panel(self, vehicle):
        """
        Shared compact HUD for all vehicle types: power, class, mode, fuel/cool gauges, fault lamps.
        Three lines when healthy; adds one line for active fault codes only.
        """
        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        running = getattr(vehicle.db, "engine_running", False)
        airborne = bool(getattr(vehicle.db, "airborne", False))
        parts = getattr(vehicle.db, "vehicle_parts", None) or {}

        part_abbrev = {
            "engine": "ENG",
            "transmission": "TRN",
            "brakes": "BRK",
            "suspension": "SUS",
            "tires": "TIR",
            "battery": "BAT",
            "fuel_system": "FUEL",
            "cooling_system": "COOL",
            "electrical": "ELC",
        }

        bad = []
        try:
            from world.vehicle_parts import VEHICLE_PART_IDS

            bad = [p for p in VEHICLE_PART_IDS if (parts.get(p, 100) or 100) < 50]
        except ImportError:
            pass

        fuel_v = parts.get("fuel_system", 100) or 100
        cool_v = parts.get("cooling_system", 100) or 100
        fuel_bar = self._hud_bar(fuel_v)
        cool_bar = self._hud_bar(cool_v)

        pwr = "|050●RUN|n" if running else "|x○STB|n"
        if vt == "aerial":
            mode = "|050SKY|n" if airborne else "|025GND|n"
            kind = "|025AV|n"
        elif vt == "motorcycle":
            mode = "|025RIDE|n"
            kind = "|0252W|n"
        else:
            mode = "|025ROAD|n"
            kind = "|0254W|n"

        fault_bits = []
        for pid in bad[:6]:
            fault_bits.append(f"|550●{part_abbrev.get(pid, pid[:3].upper())}|n")

        top = "|025╭── |530◇|n |025 LINK ────────────────────────────────╮|n"
        row1 = (
            f"|025│|n {pwr} {kind} {mode}  "
            f"|xF|n{fuel_bar} |xC|n{cool_bar}"
        )
        bot = "|025╰──────────────────────────────────────────────╯|n"
        lines = [top]
        if fault_bits:
            lines.append(row1 + " |025│|n")
            lines.append(f"|025│|n |550⚠|n {' '.join(fault_bits)} |025│|n")
        else:
            lines.append(row1 + "  |025◇|n|xOK|n |025│|n")
        lines.append(bot)
        return "\n".join(lines)

    def _dashboard_block(self, vehicle):
        return self._vehicle_status_panel(vehicle)

    def get_display_desc(self, looker, **kwargs):
        """
        Interior prose, then transition line, then full outside-room look (desc, things, people, exits).
        Dashboard and cabin contents are assembled in return_appearance so order matches: outside view,
        then LINK panel, then items inside the vehicle, then seating lines.
        """
        vehicle = self.db.vehicle
        if vehicle:
            base = self.db.desc or self.default_description
            room = self._exterior_room()
            parts = [base]
            if room:
                parts.append(self._windows_intro_line(vehicle))
                parts.append(self._exterior_appearance_as_look(room, looker, **kwargs))
            return "\n\n".join(p for p in parts if p)
        return self.db.desc or self.default_description

    def return_appearance(self, looker, **kwargs):
        """
        Same as Room, but after the main desc block (interior + windscreen view): LINK panel, then
        objects *inside* the cabin, then characters. No separate OOC drive exit line at the bottom —
        exits already appear in the outside snapshot.
        """
        header = self.get_display_header(looker, **kwargs)
        desc = self.get_display_desc(looker, **kwargs)
        things = self.get_display_things(looker, **kwargs)
        furniture = self.get_display_furniture(looker, **kwargs)
        characters = self.get_display_characters(looker, **kwargs)
        footer = self.get_display_footer(looker, **kwargs)
        vehicle = self.db.vehicle
        dashboard = self._dashboard_block(vehicle) if vehicle else ""

        if self._is_street_mode():
            ambient = ""
        else:
            ambient = self.get_display_ambient(looker, **kwargs)

        if self._is_street_mode():
            narrative = self.get_display_narrative_exits(looker, **kwargs)
            head = "\n".join([p for p in (header, desc) if p])
            parts = [head]
            if dashboard:
                parts.append(dashboard)
            if things:
                parts.append(things)
            if furniture:
                parts.append(furniture)
            tail = "\n".join([p for p in (characters, footer) if p])
            if tail:
                parts.append(tail)
            if narrative:
                parts.append(narrative)
            appearance = "\n\n".join([p for p in parts if p])
            return self.format_appearance(appearance, looker, **kwargs)

        exits = self.get_display_exits(looker, **kwargs)
        head = "\n".join([p for p in (header, desc) if p])
        parts = [head]
        if ambient:
            parts.append(ambient)
        if dashboard:
            parts.append(dashboard)
        if things:
            parts.append(things)

        if furniture:
            parts.append(furniture)

        tail = "\n".join([p for p in (characters, exits, footer) if p])
        if tail:
            if furniture:
                parts.append(tail)
            else:
                parts[-1] = "\n".join([parts[-1], tail]) if parts[-1] else tail

        appearance = "\n\n".join([p for p in parts if p])
        return self.format_appearance(appearance, looker, **kwargs)

    def get_outside_block(self, looker, **kwargs):
        """Windscreen section after a move: full outside room look (same as a normal `look` there)."""
        vehicle = self.db.vehicle
        if not vehicle:
            return ""
        room = self._exterior_room()
        if not room:
            return ""
        block = self._windows_intro_line(vehicle) + "\n\n"
        block += self._exterior_appearance_as_look(room, looker, **kwargs)
        return block

    def get_display_exits(self, looker, **kwargs):
        """Exits are shown inside the windscreen snapshot; no duplicate line here."""
        return ""

    def get_vehicle_interior_seat_line(self, char, looker, **kwargs):
        """
        One line for cab occupants: driver's seat vs passenger / back.
        Used by Room.get_display_characters when present.
        """
        vehicle = self.db.vehicle
        if not vehicle:
            return None
        from typeclasses.rooms import _ic_room_char_name

        chars = self.filter_visible(self.contents_get(content_type="character"), looker, **kwargs)
        try:
            from evennia.utils.utils import inherits_from

            chars = [c for c in chars if inherits_from(c, "evennia.objects.objects.DefaultCharacter")]
        except Exception:
            pass

        driver = getattr(vehicle.db, "driver", None)
        if driver is not None and driver not in chars:
            driver = None
        passengers = [c for c in chars if driver is None or c is not driver]
        try:
            passengers.sort(key=lambda x: getattr(x, "id", 0) or 0)
        except Exception:
            pass

        vt = getattr(vehicle.db, "vehicle_type", None) or "ground"
        pilot_word = "pilot" if vt == "aerial" else "driver"
        front_passenger = "the co-pilot seat" if vt == "aerial" else "the passenger seat"

        if driver:
            if char is driver:
                if char is looker:
                    return f"You are sitting in the {pilot_word}'s seat."
                return f"{_ic_room_char_name(char, looker, **kwargs)} is sitting in the {pilot_word}'s seat."
            if char not in passengers:
                return None
            idx = passengers.index(char)
            place = front_passenger if idx == 0 else "the back"
            if char is looker:
                return f"You are sitting in {place}."
            return f"{_ic_room_char_name(char, looker, **kwargs)} is sitting in {place}."

        if char not in passengers:
            return None
        idx = passengers.index(char)
        place = front_passenger if idx == 0 else "the back"
        if char is looker:
            return f"You are sitting in {place}."
        return f"{_ic_room_char_name(char, looker, **kwargs)} is sitting in {place}."


class Vehicle(Object):
    """
    Base class for all vehicles. Subclassed by enclosed ground vehicles, motorcycles, and aerial vehicles.

    db.vehicle_type: ground | motorcycle | aerial
    db.has_interior: enclosed types True; motorcycles False
    """

    has_interior_default = True

    def at_object_creation(self):
        super().at_object_creation()
        self.db.vehicle_type = getattr(self.db, "vehicle_type", None) or "ground"
        self.db.engine_running = False
        self.db.interior = None
        self.db.has_interior = self.has_interior_default
        self.db.driver = None
        self.db.max_passengers = 4
        self.db.driving_skill = getattr(self.db, "driving_skill", None) or "driving"
        self.db.vehicle_name = getattr(self.db, "vehicle_name", None) or "vehicle"
        self.db.vehicle_parts = default_parts()
        self.db.vehicle_part_types = default_part_types()
        self.db.speed_class = getattr(self.db, "speed_class", None) or "normal"
        self.db.locked = bool(getattr(self.db, "locked", False))
        self.db.lock_key_tag = getattr(self.db, "lock_key_tag", None) or ""
        self.db.autopilot_active = False
        self.db.autopilot_route = []
        self.db.autopilot_step = 0
        self.db.autopilot_destination = ""
        try:
            self.locks.add("get:false()")
        except Exception:
            pass
        if self.has_interior_default:
            self._ensure_interior()

    def _recover_interior_from_id(self):
        rid = getattr(self.db, "interior_room_id", None)
        if not rid:
            return None
        try:
            res = search_object(f"#{rid}")
            if res:
                interior = res[0]
                if getattr(interior.db, "vehicle", None) in (self, None):
                    interior.db.vehicle = self
                    self.db.interior = interior
                    return interior
        except Exception:
            pass
        return None

    def _ensure_interior(self):
        """Return this vehicle's single persistent interior. Creates once per vehicle; never duplicates."""
        if not getattr(self.db, "has_interior", True):
            return None

        interior = self.db.interior
        if interior:
            try:
                if not interior.tags.has(VEHICLE_INTERIOR_TAG, category=str(self.id)):
                    interior.tags.add(VEHICLE_INTERIOR_TAG, category=str(self.id))
            except Exception:
                pass
            return interior

        recovered = self._recover_interior_from_id()
        if recovered:
            return recovered

        if getattr(self.ndb, "_interior_tag_search_done", False):
            pass
        else:
            try:
                found = search_tag(VEHICLE_INTERIOR_TAG, category=str(self.id))
                self.ndb._interior_tag_search_done = True
                if found:
                    candidate = found[0]
                    if getattr(candidate.db, "vehicle", None) is self or getattr(candidate.db, "vehicle", None) == self:
                        self.db.interior = candidate
                        self.db.interior_room_id = candidate.id
                        return candidate
                    if getattr(candidate.db, "vehicle", None) is None:
                        candidate.db.vehicle = self
                        self.db.interior = candidate
                        self.db.interior_room_id = candidate.id
                        return candidate
            except Exception:
                self.ndb._interior_tag_search_done = True

        key = f"Inside the {self.key}"
        interior = create_object(
            "typeclasses.vehicles.VehicleInterior",
            key=key,
            location=None,
        )
        if interior:
            interior.db.vehicle = self
            interior.db.desc = None
            interior.tags.add(VEHICLE_INTERIOR_TAG, category=str(self.id))
            self.db.interior = interior
            self.db.interior_room_id = interior.id
        return self.db.interior

    @property
    def interior(self):
        if not getattr(self.db, "has_interior", True):
            return None
        return self._ensure_interior()

    def at_pre_get(self, getter, **kwargs):
        if getter and getter.check_permstring("Builder"):
            return super().at_pre_get(getter, **kwargs)
        interior = None
        if getattr(self.db, "has_interior", True):
            interior = self.db.interior or self._ensure_interior()
        if interior and hasattr(interior, "contents_get"):
            try:
                if interior.contents_get(content_type="character"):
                    getter.msg("Someone is inside. You can't pick this up.")
                    return False
            except Exception:
                pass
        return super().at_pre_get(getter, **kwargs)

    def at_pre_drop(self, dropper, **kwargs):
        loc = dropper.location if dropper else None
        if not loc:
            return super().at_pre_drop(dropper, **kwargs)
        ok, reason = _can_vehicle_be_placed_in_room(self, loc)
        if not ok:
            if dropper:
                dropper.msg(f"|r{reason}|n")
            return False
        return super().at_pre_drop(dropper, **kwargs)

    def at_after_move(self, source_location, **kwargs):
        try:
            super().at_after_move(source_location, **kwargs)
        except Exception:
            pass
        dest = self.location
        if not dest:
            return
        ok, _reason = _can_vehicle_be_placed_in_room(self, dest)
        if ok:
            return
        if source_location:
            self.move_to(source_location, quiet=True)

    def return_appearance(self, looker, **kwargs):
        name = self.get_display_name(looker)
        desc = self.db.desc or "A vehicle."
        parts = [desc]
        if getattr(self.db, "engine_running", False):
            parts.append("\n|yEngine running.|n")
        return "\n".join(parts)

    def damage_part(self, part_id, amount):
        try:
            from world.movement import tunnels as _tunnels

            if getattr(self.db, "autopilot_active", False):
                _tunnels.cancel_autopilot(self, reason="Vehicle took damage.")
        except Exception:
            pass
        return _damage_part(self, part_id, amount)

    def start_engine(self):
        ok, msg = can_start_engine(self)
        if not ok:
            return False, msg
        self.db.engine_running = True
        return True, None

    def stop_engine(self):
        self.db.engine_running = False
        try:
            from world.movement import tunnels as _tunnels

            if getattr(self.db, "autopilot_active", False):
                _tunnels.cancel_autopilot(self, reason="Engine stopped.")
        except Exception:
            pass

    @property
    def engine_running(self):
        return bool(self.db.engine_running)

    def get_part_condition(self, part_id):
        return _get_part_condition(self, part_id)

    def set_part_condition(self, part_id, value):
        _set_part_condition(self, part_id, value)

    def repair_part(self, part_id, amount):
        return _repair_part(self, part_id, amount)

    def drive_failure_modifier(self):
        return drive_failure_modifier(self)

    def roll_stall_chance(self):
        return roll_stall_chance(self)

    def get_exit(self, direction):
        """Find an exit from the vehicle's current room in the given direction (e.g. 'east', 'e')."""
        room = self.location
        if not room or not direction:
            return None
        d = direction.strip().lower()
        dir_aliases = {
            "n": "north",
            "s": "south",
            "e": "east",
            "w": "west",
            "ne": "northeast",
            "nw": "northwest",
            "se": "southeast",
            "sw": "southwest",
            "u": "up",
            "d": "down",
        }
        d = dir_aliases.get(d, d)
        d_names = {d}
        for short, long in dir_aliases.items():
            if long == d:
                d_names.add(short)
        for obj in (room.contents or []):
            if not isinstance(obj, DefaultExit) or not getattr(obj, "destination", None):
                continue
            key = (obj.key or "").strip().lower()
            raw_aliases = getattr(obj, "aliases", None)
            if isinstance(raw_aliases, str):
                exit_aliases = [a.strip().lower() for a in raw_aliases.split(",") if a.strip()]
            elif hasattr(raw_aliases, "all"):
                exit_aliases = [str(a).strip().lower() for a in raw_aliases.all() if str(a).strip()]
            else:
                exit_aliases = [str(a).strip().lower() for a in (raw_aliases or []) if str(a).strip()]
            if key in d_names or d in exit_aliases or any(a in d_names for a in exit_aliases):
                return obj
        return None


class Motorcycle(Vehicle):
    """
    Open vehicle — no interior. The rider remains in the room, mounted.
    """

    has_interior_default = False

    def at_object_creation(self):
        super().at_object_creation()
        self.db.vehicle_type = "motorcycle"
        self.db.has_interior = False
        self.db.interior = None
        self.db.max_passengers = getattr(self.db, "max_passengers", None) or 1
        self.db.rider = None
        self.db.speed_class = getattr(self.db, "speed_class", None) or "fast"
        if not hasattr(self.db, "has_pillion"):
            self.db.has_pillion = False

    @property
    def interior(self):
        return None


class AerialVehicle(Vehicle):
    """Flying vehicle; uses piloting; can use aerial corridors and shafts."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.vehicle_type = "aerial"
        self.db.has_interior = True
        self.db.driving_skill = "piloting"
        self.db.speed_class = getattr(self.db, "speed_class", None) or "fast"
        self.db.airborne = False
        self.db.altitude_z = None

    def stop_engine(self):
        super().stop_engine()
        if getattr(self.db, "airborne", False):
            self.db.airborne = False
