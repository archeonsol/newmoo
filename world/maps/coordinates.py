"""
Master coordinate registry. ALL NAMES AND POSITIONS ARE PROVISIONAL.
Builders will rename rooms and may adjust grid layout. This file defines
the mechanical skeleton only. Do not hardcode room names from this file
in game systems — use city_level tags and coordinate queries instead.

`CITY_COORDINATES` maps a canonical location name to (x, y, z). Names that share
the same cell (e.g. street + junction + transit hub) are merged: the first
occurrence in the raw registry wins; others are listed in `CITY_COORD_ALIASES`.

Z bands (reference):
  Z=65 — Slums (streets, gates, slum freight)
  Z=64–49 — Air / shafts
  Z=48 — Guild (streets, gates, guild freight)
  Z=47–32 — Air / shafts
  Z=31 — Bourgeois (streets, gates, bourgeois freight)
  Z=30–15 — Air / shafts
  Z=14 — Elite (streets, gate, elite freight)

Gates and freight live on the same Z as their district; vertical travel between
districts is via freight lifts through shafts, not dedicated gate Z levels.

A few names needed distinct cells; see `MANUAL_COORD_OVERRIDES`.
"""

from __future__ import annotations

from typing import Dict, Tuple

from world.maps._raw_city_coordinates import RAW_CITY_COORDINATES

Coord = Tuple[int, int, int]

# Grid keys that should be built as `GateRoom` (district Z, same as surrounding tier).
GATE_GRID_KEYS: frozenset[str] = frozenset(
    {
        "slum_gate_central",
        "warren_gate_north",
        "warren_gate_south",
        "guild_gate",
        "bourgeois_gate",
        "elite_gate",
    }
)

# Second name -> coordinate when two different places collided in the design doc.
MANUAL_COORD_OVERRIDES: Dict[str, Coord] = {
    # Apex: garden vs corridor node (apex_transit_up is set in raw registry)
    "the_garden": (13, 10, 14),
    # Works: back room vs commerce cell
    "the_grindstone_back": (10, 14, 48),
}


def _build_registry() -> tuple[Dict[str, Coord], Dict[str, str]]:
    raw: Dict[str, Coord] = dict(RAW_CITY_COORDINATES)
    raw.update(MANUAL_COORD_OVERRIDES)

    coord_to_canonical: Dict[Coord, str] = {}
    coords: Dict[str, Coord] = {}
    aliases: Dict[str, str] = {}

    for name, coord in raw.items():
        if coord in coord_to_canonical:
            aliases[name] = coord_to_canonical[coord]
        else:
            coord_to_canonical[coord] = name
            coords[name] = coord

    return coords, aliases


CITY_COORDINATES, CITY_COORD_ALIASES = _build_registry()


def resolve_city_key(name: str) -> str:
    """Return canonical grid key for a location name (may be an alias)."""
    n = (name or "").strip().lower().replace(" ", "_")
    if n in CITY_COORDINATES:
        return n
    canon = CITY_COORD_ALIASES.get(n)
    if canon:
        return canon
    return n


def get_coord(name: str) -> Coord | None:
    """Return (x, y, z) for a canonical or alias name."""
    key = resolve_city_key(name)
    return CITY_COORDINATES.get(key)


def get_level_from_z(z: int) -> str:
    if z == 65:
        return "slums"
    if z == 48:
        return "guild"
    if z == 31:
        return "bourgeois"
    if z == 14:
        return "elite"
    return "shaft"
