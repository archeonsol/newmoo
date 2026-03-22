"""Tunnel autopilot command."""

from commands.base_cmds import Command


class CmdAutopilot(Command):
    """
    Engage autopilot to drive through a tunnel.
    Works from any position inside a tunnel — entrance or mid-tunnel.
    You can change direction mid-tunnel by re-running autopilot with a different destination.

    Usage:
        autopilot <sector>       — e.g. autopilot guild, autopilot slums
        autopilot stop           — cancel autopilot, coast to a stop

    Examples:
        autopilot guild          — drive toward the guild district end
        autopilot slums          — reverse, head back toward slums
        autopilot stop           — stop where you are
    """

    key = "autopilot"
    aliases = ["auto", "ap"]
    locks = "cmd:all()"
    help_category = "Vehicles"

    def func(self):
        from commands.vehicle_cmds import _get_vehicle_from_caller
        from typeclasses.vehicles import Vehicle
        from world.movement import tunnels as tun

        caller = self.caller

        if getattr(caller.db, "mounted_on", None):
            vehicle = caller.db.mounted_on
        else:
            vehicle = _get_vehicle_from_caller(caller)

        if not vehicle or not isinstance(vehicle, Vehicle):
            caller.msg("You're not in a vehicle.")
            return

        if getattr(vehicle.db, "vehicle_type", None) == "aerial":
            caller.msg("AVs don't use tunnels. Fly through the shaft.")
            return

        args = (self.args or "").strip().lower()

        if args in ("stop", "off", "cancel"):
            if getattr(vehicle.db, "autopilot_active", False):
                tun.cancel_autopilot(vehicle, reason="Pilot disengaged.")
            else:
                caller.msg("Autopilot isn't active.")
            return

        if not args:
            loc = vehicle.location
            valid = tun.get_valid_destinations(loc) if loc else []
            if valid:
                valid_str = ", ".join(f"|w{v}|n" for v in valid)
                caller.msg(f"Valid destinations from here: {valid_str}")
                caller.msg("Usage: |wautopilot <sector>|n or |wautopilot stop|n")
            else:
                if loc and tun.get_tunnel_network(loc):
                    caller.msg(
                        "You're at an endpoint. Drive out of the tunnel, or autopilot back the other way."
                    )
                else:
                    caller.msg("You're not in a tunnel.")
            return

        if not getattr(vehicle.db, "engine_running", False):
            caller.msg("Engine must be running.")
            return

        if getattr(vehicle.db, "driver", None) and vehicle.db.driver != caller:
            caller.msg("You're not driving.")
            return

        ok, msg = tun.start_autopilot(vehicle, caller, args)
        if not ok and msg:
            caller.msg(f"|r{msg}|n")
