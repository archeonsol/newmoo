"""
Batch build for the city grid skeleton (reference / optional tool).

Builders normally place rooms manually; this is not auto-run. If you use it on a
fresh database (or after removing rooms), you can run from the server:

    # @py from world.maps.build_city import build_city_framework; build_city_framework()

Connect street ↔ gate ↔ freight stations with normal CityExit links; vertical
movement between districts is handled by freight lift scripts through shaft
cells — this script does not create VerticalExit chains for district travel.

Rooms at coordinates that already exist will log errors and skip (see Evennia log).
"""

from __future__ import annotations

from evennia import create_object
from evennia.utils import logger
from evennia.contrib.grid.xyzgrid.xyzroom import (
    MAP_X_TAG_CATEGORY,
    MAP_Y_TAG_CATEGORY,
    MAP_Z_TAG_CATEGORY,
    MAP_XDEST_TAG_CATEGORY,
    MAP_YDEST_TAG_CATEGORY,
    MAP_ZDEST_TAG_CATEGORY,
)

from typeclasses.exits import CityExit
from typeclasses.rooms import (
    AirRoom,
    BourgeoisRoom,
    CityRoom,
    EliteRoom,
    GateRoom,
    GuildRoom,
    SlumRoom,
)
from world.maps.coordinates import CITY_COORDINATES, GATE_GRID_KEYS, get_level_from_z


def _class_for_level(level: str):
    return {
        "slums": SlumRoom,
        "guild": GuildRoom,
        "bourgeois": BourgeoisRoom,
        "elite": EliteRoom,
        "shaft": AirRoom,
    }.get(level, CityRoom)


def _class_for_grid_key(name: str, level: str):
    if name in GATE_GRID_KEYS:
        return GateRoom
    return _class_for_level(level)


def _tag_city_exit(exit_obj, loc, dest):
    lx, ly, lz = loc.xyz
    dx, dy, dz = dest.xyz
    exit_obj.tags.add(str(lx), category=MAP_X_TAG_CATEGORY)
    exit_obj.tags.add(str(ly), category=MAP_Y_TAG_CATEGORY)
    exit_obj.tags.add(str(lz), category=MAP_Z_TAG_CATEGORY)
    exit_obj.tags.add(str(dx), category=MAP_XDEST_TAG_CATEGORY)
    exit_obj.tags.add(str(dy), category=MAP_YDEST_TAG_CATEGORY)
    exit_obj.tags.add(str(dz), category=MAP_ZDEST_TAG_CATEGORY)


def _make_exit(key, loc, dest, excls=CityExit):
    exi = create_object(
        excls,
        key=key,
        location=loc,
        destination=dest,
    )
    _tag_city_exit(exi, loc, dest)
    return exi


def _has_exit_to(room, neighbor):
    for exi in room.contents_get(content_type="exit"):
        if getattr(exi, "destination", None) == neighbor:
            return True
    return False


def _connect_cardinal_exits(rooms: dict):
    directions = {
        "north": (0, 1, 0),
        "south": (0, -1, 0),
        "east": (1, 0, 0),
        "west": (-1, 0, 0),
    }
    for (x, y, z), room in rooms.items():
        for dir_name, (dx, dy, dz) in directions.items():
            neighbor_coord = (x + dx, y + dy, z + dz)
            neighbor = rooms.get(neighbor_coord)
            if not neighbor:
                continue
            if _has_exit_to(room, neighbor):
                continue
            _make_exit(dir_name, room, neighbor)


def build_city_framework():
    """
    Create all registry rooms and cardinal exits between orthogonal neighbors.
    """
    rooms: dict[tuple[int, int, int], object] = {}
    for name, (x, y, z) in CITY_COORDINATES.items():
        level = get_level_from_z(z)
        cls = _class_for_grid_key(name, level)
        title = name.replace("_", " ").title()
        room, errs = cls.create(title, xyz=(x, y, z))
        if errs:
            logger.log_err(f"build_city_framework {name}: {errs}")
            continue
        if room:
            room.db.grid_key = name
            if cls is GateRoom:
                room.db.city_level = level
            rooms[(x, y, z)] = room

    _connect_cardinal_exits(rooms)
    return rooms
