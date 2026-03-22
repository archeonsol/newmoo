"""
Builder commands for freight lifts.
"""

from commands.base_cmds import Command


class CmdFreight(Command):
    """
    Manage freight lift cycles.
    Usage:
        freight start <lift>     — start cycle (opens doors if docked)
        freight stop <lift>      — pause cycle
        freight status <lift>    — phase, timing, passengers
        freight reset <lift> <phase> — force phase: docked_upper|transit_down|docked_lower|transit_up
        freight setup <lift> = <upper #ref> <lower #ref> — set station dbrefs
    """

    key = "freight"
    aliases = ["@freight"]
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        raw = (self.args or "").strip()
        if not raw:
            caller.msg(
                "Usage: freight start|stop|status|reset|setup ... (|whelp freight|n)"
            )
            return
        parts = raw.split()
        sub = parts[0].lower()
        rest = raw[len(parts[0]) :].strip() if parts else ""

        if sub == "start":
            self._do_start(caller, rest)
        elif sub == "stop":
            self._do_stop(caller, rest)
        elif sub == "status":
            self._do_status(caller, rest)
        elif sub == "reset":
            self._do_reset(caller, rest)
        elif sub == "setup":
            self._do_setup(caller, rest)
        else:
            caller.msg("Unknown subcommand. Use: start, stop, status, reset, setup.")

    def _resolve_lift(self, caller, argstr):
        if not argstr.strip():
            caller.msg("Specify a lift (object name or #dbref).")
            return None
        return caller.search(argstr.strip(), global_search=True)

    def _do_start(self, caller, rest):
        lift = self._resolve_lift(caller, rest)
        if not lift:
            return
        from typeclasses.freight_lift import FreightLift
        from evennia.utils.utils import inherits_from
        from world.movement.freight import start_freight_cycle

        if not inherits_from(lift, FreightLift):
            caller.msg("That is not a FreightLift room.")
            return
        start_freight_cycle(lift)
        caller.msg(f"|gFreight cycle started on {lift.key} (#{lift.id}).|n")

    def _do_stop(self, caller, rest):
        lift = self._resolve_lift(caller, rest)
        if not lift:
            return
        from typeclasses.freight_lift import FreightLift
        from evennia.utils.utils import inherits_from
        from world.movement.freight import stop_freight_cycle

        if not inherits_from(lift, FreightLift):
            caller.msg("That is not a FreightLift room.")
            return
        stop_freight_cycle(lift)
        caller.msg(f"|yFreight cycle stopped on {lift.key} (#{lift.id}).|n")

    def _do_status(self, caller, rest):
        import time

        lift = self._resolve_lift(caller, rest)
        if not lift:
            return
        from typeclasses.freight_lift import FreightLift
        from evennia.utils.utils import inherits_from

        if not inherits_from(lift, FreightLift):
            caller.msg("That is not a FreightLift room.")
            return

        phase = getattr(lift.db, "current_phase", "?")
        started = getattr(lift.db, "phase_started", None) or time.time()
        elapsed = time.time() - started
        active = getattr(lift.db, "cycle_active", False)
        pax = len(lift.contents_get(content_type="character"))
        caller.msg(
            f"{lift.key} (#{lift.id})\n"
            f"  phase: {phase}\n"
            f"  cycle_active: {active}\n"
            f"  elapsed in phase: {elapsed:.1f}s\n"
            f"  passengers: {pax}\n"
            f"  lift_id: {getattr(lift.db, 'lift_id', '')}\n"
        )

    def _do_reset(self, caller, rest):
        parts = rest.split()
        if len(parts) < 2:
            caller.msg("Usage: freight reset <lift> <phase>")
            return
        phase = parts[-1].lower()
        lift_arg = " ".join(parts[:-1])
        lift = self._resolve_lift(caller, lift_arg)
        if not lift:
            return
        from typeclasses.freight_lift import FreightLift
        from evennia.utils.utils import inherits_from
        from world.movement.freight import reset_freight_phase

        if not inherits_from(lift, FreightLift):
            caller.msg("That is not a FreightLift room.")
            return
        valid = ("docked_upper", "transit_down", "docked_lower", "transit_up")
        if phase not in valid:
            caller.msg(f"Phase must be one of: {', '.join(valid)}")
            return
        reset_freight_phase(lift, phase)
        caller.msg(f"|gLift forced to phase {phase}.|n")

    def _do_setup(self, caller, rest):
        if "=" not in rest:
            caller.msg("Usage: freight setup <lift> = <upper #ref> <lower #ref>")
            return
        left, right = rest.split("=", 1)
        lift = self._resolve_lift(caller, left.strip())
        if not lift:
            return
        from typeclasses.freight_lift import FreightLift
        from evennia.utils.utils import inherits_from
        from world.movement.freight import setup_freight_stations

        if not inherits_from(lift, FreightLift):
            caller.msg("That is not a FreightLift room.")
            return
        bits = right.split()
        if len(bits) != 2:
            caller.msg("Provide exactly two station dbrefs after =.")
            return
        setup_freight_stations(lift, bits[0].strip(), bits[1].strip())
        caller.msg(f"|gSet upper_station={bits[0]} lower_station={bits[1]} on {lift.key}.|n")
