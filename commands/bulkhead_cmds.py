"""
IC and staff bulkhead (floodgate) commands.
"""

from __future__ import annotations

import time

from evennia import Command
from evennia.utils.evtable import EvTable
from evennia.utils.search import search_object


def _get_bulkhead_room(location):
    from evennia.utils.utils import inherits_from
    from typeclasses.bulkhead_room import BulkheadRoom

    if location and inherits_from(location, BulkheadRoom):
        return location
    return None


class CmdSeal(Command):
    """
    Seal a bulkhead. Must be standing in a bulkhead room.
    Only Inquisitorate members and staff may use this.

    Usage:
        seal
        seal <reason>
    """

    key = "seal"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = self.caller
        room = _get_bulkhead_room(caller.location)
        if not room:
            caller.msg("You are not in a bulkhead room.")
            return

        reason = (self.args or "").strip()
        from world.maps.bulkheads import seal_bulkhead

        ok, msg = seal_bulkhead(caller, room, reason=reason)
        if ok:
            caller.msg("|gBulkhead sealed.|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdUnseal(Command):
    """
    Unseal a bulkhead. Must be standing in a bulkhead room.

    Usage:
        unseal
    """

    key = "unseal"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = self.caller
        room = _get_bulkhead_room(caller.location)
        if not room:
            caller.msg("You are not in a bulkhead room.")
            return

        from world.maps.bulkheads import unseal_bulkhead

        ok, msg = unseal_bulkhead(caller, room)
        if ok:
            caller.msg("|gBulkhead unsealed.|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdBulkheadStatus(Command):
    """
    Check the status of the bulkhead you're in.

    Usage:
        bulkhead
    """

    key = "bulkhead"
    aliases = ["gate", "bulkhead status"]
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = self.caller
        room = _get_bulkhead_room(caller.location)
        if not room:
            caller.msg("You are not in a bulkhead room.")
            return

        from world.maps.bulkheads import can_operate_bulkhead

        sealed = bool(room.db.sealed)
        name = room.db.bulkhead_id or "bulkhead"
        connects = room.db.connects_districts or ("?", "?")

        lines = [
            f"|x{'=' * 48}|n",
            f"  |w{name.upper().replace('_', ' ')}|n",
            f"  Connects: {connects[0]} |x<>|n {connects[1]}",
            f"  Status: {'|RSEALED|n' if sealed else '|gOPEN|n'}",
        ]

        if sealed:
            reason = room.db.seal_reason or "—"
            sealed_by = room.db.sealed_by or "Unknown"
            elapsed = time.time() - (room.db.sealed_at or time.time())
            hours = int(elapsed / 3600)
            mins = int((elapsed % 3600) / 60)
            lines.append(f"  Sealed by: {sealed_by}")
            lines.append(f"  Reason: {reason}")
            lines.append(f"  Duration: {hours}h {mins}m")
            direction = room.db.seal_direction or "outbound"
            lines.append(f"  Direction: {direction}")

        allowed, _ = can_operate_bulkhead(caller)
        if allowed:
            log = (room.db.seal_log or [])[-5:]
            if log:
                lines.append("")
                lines.append("  |xRecent log:|n")
                for entry in log:
                    ev = entry.get("event", "?")
                    det = (entry.get("details", "") or "")[:50]
                    lines.append(f"  |x— {ev}: {det}|n")

        lines.append(f"|x{'=' * 48}|n")
        caller.msg("\n".join(lines))


class CmdBulkheadAdmin(Command):
    """
    Staff bulkhead management.

    Usage:
        @bulkhead list
        @bulkhead seal <id> = <reason>
        @bulkhead unseal <id>
        @bulkhead setup <room> = <district_exit_dbref> <station_exit_dbref>
    """

    key = "@bulkhead"
    aliases = ["@bulkheads"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        from evennia.utils.utils import inherits_from
        from typeclasses.bulkhead_room import BulkheadRoom
        from world.maps.bulkheads import (
            get_all_bulkheads,
            get_bulkhead_by_id,
            seal_bulkhead,
            setup_bulkhead_exits,
            unseal_bulkhead,
        )

        raw = (self.args or "").strip()
        if not raw:
            self.msg(
                "Usage: @bulkhead list | @bulkhead seal <id> = <reason> | "
                "@bulkhead unseal <id> | @bulkhead setup <room> = <ex1> <ex2>"
            )
            return

        parts = raw.split(None, 1)
        sub = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "list":
            rooms = get_all_bulkheads()
            if not rooms:
                self.msg("No bulkhead-tagged rooms found.")
                return
            table = EvTable("|wID|n", "|wSealed|n", "|wZ|n", border="cells")
            for r in sorted(rooms, key=lambda x: getattr(x.db, "bulkhead_id", "") or ""):
                bid = getattr(r.db, "bulkhead_id", "") or "—"
                sealed = "|rYes|n" if getattr(r.db, "sealed", False) else "|gNo|n"
                z = getattr(r, "z", "?")
                table.add_row(bid, sealed, z)
            self.msg(str(table))
            return

        if sub == "seal":
            if "=" not in rest:
                self.msg("Usage: @bulkhead seal <id> = <reason>")
                return
            left, reason = rest.split("=", 1)
            bid = left.strip()
            room = get_bulkhead_by_id(bid)
            if not room:
                self.msg(f"No bulkhead with id '{bid}'.")
                return
            ok, msg = seal_bulkhead(self.caller, room, reason=reason.strip())
            self.msg(msg if ok else f"|r{msg}|n")
            return

        if sub == "unseal":
            bid = rest.strip()
            if not bid:
                self.msg("Usage: @bulkhead unseal <id>")
                return
            room = get_bulkhead_by_id(bid)
            if not room:
                self.msg(f"No bulkhead with id '{bid}'.")
                return
            ok, msg = unseal_bulkhead(self.caller, room)
            self.msg(msg if ok else f"|r{msg}|n")
            return

        if sub == "setup":
            if "=" not in rest:
                self.msg("Usage: @bulkhead setup <room> = <district_exit#> <station_exit#>")
                return
            left, right = rest.split("=", 1)
            room_key = left.strip()
            bits = right.split()
            if len(bits) < 2:
                self.msg("Provide two exit dbrefs after =.")
                return

            target = None
            if room_key.startswith("#"):
                res = search_object(room_key)
                target = res[0] if res else None
            else:
                res = search_object(room_key, global_search=True)
                for cand in res or []:
                    if inherits_from(cand, BulkheadRoom):
                        target = cand
                        break

            if not target or not inherits_from(target, BulkheadRoom):
                self.msg("Room not found or not a BulkheadRoom.")
                return

            try:
                e1 = int(bits[0].lstrip("#"))
                e2 = int(bits[1].lstrip("#"))
            except ValueError:
                self.msg("Exit dbrefs must be integers (e.g. #1234 or 1234).")
                return

            ex1_res = search_object(f"#{e1}")
            ex2_res = search_object(f"#{e2}")
            if not ex1_res:
                self.msg(f"No object found at #{e1}. Check the district exit dbref.")
                return
            if not ex2_res:
                self.msg(f"No object found at #{e2}. Check the station exit dbref.")
                return

            setup_bulkhead_exits(target, e1, e2)
            self.msg(
                f"Bulkhead {target.key} configured: district exit #{e1}, station exit #{e2}."
            )
            return

        self.msg("Unknown subcommand. See help @bulkhead.")
