"""
Staff / builder commands for the underground city XYZ grid.
"""

from commands.base_cmds import Command


class CmdCityMap(Command):
    """
    ASCII map of one Z level (rooms that exist in the DB).
    Usage:
        @citymap           — map of your current Z
        @citymap <z>       — map at integer Z (e.g. 65)
    """

    key = "citymap"
    aliases = ["@citymap"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom

        loc = caller.location
        z = None
        args = (self.args or "").strip()
        if args:
            try:
                z = int(args.split()[0])
            except (ValueError, IndexError):
                caller.msg("Usage: @citymap or @citymap <integer Z>")
                return
        else:
            if not loc or not hasattr(loc, "xyz"):
                caller.msg("Your current location has no XYZ coordinates. Use |w@citymap <z>|n.")
                return
            z = loc.xyz[2]
            try:
                z = int(z)
            except (TypeError, ValueError):
                caller.msg("Could not parse Z from your room.")
                return

        allr = list(XYZRoom.objects.filter_xyz(xyz=("*", "*", z)))
        if not allr:
            caller.msg(f"No XYZ rooms found at Z={z}.")
            return

        xs = [int(r.xyz[0]) for r in allr]
        ys = [int(r.xyz[1]) for r in allr]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        occupied = {(int(r.xyz[0]), int(r.xyz[1])) for r in allr}

        cx = cy = None
        if loc and hasattr(loc, "xyz"):
            try:
                if int(loc.xyz[2]) == z:
                    cx, cy = int(loc.xyz[0]), int(loc.xyz[1])
            except (TypeError, ValueError):
                pass

        header = "    " + "".join(f"{x % 10}" for x in range(minx, maxx + 1))
        lines = [header]
        for y in range(maxy, miny - 1, -1):
            row = f"{y:3d} "
            for x in range(minx, maxx + 1):
                if cx is not None and x == cx and y == cy:
                    ch = "@"
                elif (x, y) in occupied:
                    ch = "#"
                else:
                    ch = "."
                row += ch
            lines.append(row)

        label = _level_label(z)
        caller.msg("\n".join(lines) + f"\n\n  Z={z} ({label})")


def _level_label(z: int) -> str:
    from world.maps.coordinates import get_level_from_z

    return get_level_from_z(z).replace("_", " ").title()


class CmdCityLevel(Command):
    """
    List rooms at a Z level (from the database).
    Usage:
        @citylevel       — rooms on your current Z
        @citylevel <z>   — rooms at Z
    """

    key = "citylevel"
    aliases = ["@citylevel"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom

        args = (self.args or "").strip()
        loc = caller.location
        z = None
        if args:
            try:
                z = int(args.split()[0])
            except (ValueError, IndexError):
                caller.msg("Usage: @citylevel or @citylevel <z>")
                return
        else:
            if not loc or not hasattr(loc, "xyz"):
                caller.msg("No XYZ on current room. Use |w@citylevel <z>|n.")
                return
            try:
                z = int(loc.xyz[2])
            except (TypeError, ValueError):
                caller.msg("Could not read Z from your room.")
                return

        rooms = list(XYZRoom.objects.filter_xyz(xyz=("*", "*", z)))
        rooms.sort(key=lambda r: (int(r.xyz[1]), int(r.xyz[0])))
        if not rooms:
            caller.msg(f"No rooms at Z={z}.")
            return
        lines = [f"Rooms at Z={z} ({_level_label(z)}), count={len(rooms)}:"]
        for r in rooms:
            gk = getattr(r.db, "grid_key", None) or ""
            x, y, zz = r.xyz
            lines.append(f"  ({x},{y},{zz}) #{r.id} {r.key}  |c{gk}|n")
        caller.msg("\n".join(lines))


class CmdCityCoord(Command):
    """
    Show XYZ for a room.
    Usage:
        @citycoord              — your current room
        @citycoord <room>      — search globally
    """

    key = "citycoord"
    aliases = ["@citycoord"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if args:
            target = caller.search(args, global_search=True)
            if not target:
                return
            room = target
        else:
            room = caller.location
        if not room:
            caller.msg("No location.")
            return
        if not hasattr(room, "xyz"):
            caller.msg(f"{room.key} has no XYZ tags (not a city / XYZ room).")
            return
        x, y, z = room.xyz
        gk = getattr(room.db, "grid_key", None) or ""
        caller.msg(f"{room.key} (#{room.id})  XYZ=({x},{y},{z})  grid_key=|c{gk}|n")


class CmdAirRoom(Command):
    """
    Create an AirRoom at integer coordinates if empty.
    Usage: @airroom <x> <y> <z>
    """

    key = "airroom"
    aliases = ["@airroom"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        parts = (self.args or "").split()
        if len(parts) != 3:
            caller.msg("Usage: @airroom <x> <y> <z>")
            return
        try:
            x, y, z = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            caller.msg("x, y, z must be integers.")
            return

        from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
        from typeclasses.rooms import AirRoom

        if XYZRoom.objects.filter_xyz(xyz=(x, y, z)).exists():
            caller.msg(f"There is already a room at ({x},{y},{z}).")
            return

        room, errs = AirRoom.create(f"Open shaft ({x},{y},{z})", xyz=(x, y, z))
        if errs:
            caller.msg(f"Could not create: {errs}")
            return
        caller.msg(f"Created {room.key} (#{room.id}) at ({x},{y},{z}).")


class CmdShaftConnect(Command):
    """
    Create a vertical shaft of AirRooms between two rooms (same X,Y), wiring
    |wdown|n / |wup|n exits. Rooms must share X,Y; upper Z > lower Z.
    Usage: @shaftconnect <upper #dbref> <lower #dbref>
    """

    key = "shaftconnect"
    aliases = ["@shaftconnect"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        from evennia.utils.search import search_object

        parts = (self.args or "").split()
        if len(parts) != 2:
            caller.msg("Usage: @shaftconnect <upper #id> <lower #id>")
            return

        up_res = search_object(parts[0])
        lo_res = search_object(parts[1])
        if not up_res or not lo_res:
            caller.msg("Could not resolve one or both objects.")
            return
        upper, lower = up_res[0], lo_res[0]
        if not hasattr(upper, "xyz") or not hasattr(lower, "xyz"):
            caller.msg("Both ends must be XYZ rooms.")
            return

        ux, uy, uz = (int(upper.xyz[0]), int(upper.xyz[1]), int(upper.xyz[2]))
        lx, ly, lz = (int(lower.xyz[0]), int(lower.xyz[1]), int(lower.xyz[2]))
        if (ux, uy) != (lx, ly):
            caller.msg("Shaft requires the same X and Y for upper and lower rooms.")
            return
        if uz <= lz:
            caller.msg("Upper room must be above lower (higher Z).")
            return

        from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
        from typeclasses.exits import VerticalExit
        from world.maps.build_city import _has_exit_to, _make_exit

        created = 0
        chain = [upper]

        for z in range(uz - 1, lz, -1):
            if XYZRoom.objects.filter_xyz(xyz=(ux, uy, z)).exists():
                r = XYZRoom.objects.get_xyz(xyz=(ux, uy, z))
            else:
                from typeclasses.rooms import AirRoom

                r, errs = AirRoom.create(f"Shaft ({ux},{uy},{z})", xyz=(ux, uy, z))
                if errs:
                    caller.msg(f"Failed at z={z}: {errs}")
                    return
                created += 1
            chain.append(r)
        chain.append(lower)

        for a, b in zip(chain, chain[1:]):
            if not _has_exit_to(a, b):
                _make_exit("down", a, b, VerticalExit)
            if not _has_exit_to(b, a):
                _make_exit("up", b, a, VerticalExit)

        caller.msg(
            f"Shaft wired from {upper.key} (#{upper.id}) to {lower.key} (#{lower.id}). "
            f"New air rooms: {created}."
        )
