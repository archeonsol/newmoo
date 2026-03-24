"""
Open, close, lock, unlock, and verify — doors and bioscan exits.

Rentable doors (ex.db.rentable = True):
  - Must be unlocked first with: push <code> <direction>
  - Then opened normally with: open <direction>
  - Auto-lock when closed from either side.
  - Staff bypass skips the unlock requirement.
"""

from commands.base_cmds import Command


def _dir_map():
    return {
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
        "o": "out",
    }


def find_exit_by_direction_in_room(room, arg):
    """Find exit in *room* matching direction string (key or alias)."""
    if not room or not arg:
        return None
    raw = arg.strip().lower()
    direction = _dir_map().get(raw, raw)
    exits = [o for o in (room.contents or []) if getattr(o, "destination", None)]
    for ex in exits:
        key = (ex.key or "").lower().strip()
        try:
            aliases = [a.lower() for a in (ex.aliases.all() if hasattr(ex.aliases, "all") else [])]
        except Exception:
            aliases = []
        if direction == key or direction in aliases:
            return ex
    return None


def find_exit_by_direction(caller, arg):
    """Find exit in caller's location matching direction string (key or alias)."""
    return find_exit_by_direction_in_room(getattr(caller, "location", None), arg)


class CmdOpenDoor(Command):
    """
    Open a door on an exit.

    Usage:
        open <direction>
    """

    key = "open"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.rpg.factions.doors import staff_bypass, sync_door_pair, schedule_door_auto_close
        from world.rpg.rentable_doors import is_rentable, is_paired_with_rentable, _resolve_door_pair

        if not self.args:
            self.caller.msg("Open which way? Usage: open <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if getattr(ex.db, "door_open", None):
            self.caller.msg("It's already open.")
            return

        # ── Rentable door handling ──────────────────────────────────────────
        # Covers both the outside (rentable) exit and the inside (plain) exit.
        is_rent_side = is_rentable(ex) or is_paired_with_rentable(ex)
        if is_rent_side:
            auth_ex = ex if is_rentable(ex) else _resolve_door_pair(ex)
            door_name = getattr(auth_ex.db, "door_name", None) if auth_ex else None
            door_name = door_name or "door"

            if getattr(ex.db, "door_locked", None):
                if staff_bypass(self.caller):
                    ex.db.door_locked = False
                    if auth_ex:
                        auth_ex.db.door_locked = False
                    ex.db.door_open = True
                    sync_door_pair(ex, True)
                    self.caller.msg(f"You open the {door_name} (staff override).")
                    loc = self.caller.location
                    if loc:
                        loc.msg_contents(f"The {door_name} opens.", exclude=self.caller)
                    return
                self.caller.msg(
                    f"The {door_name} is locked. "
                    f"Use |wpush <code> {(self.args or '').strip()}|n to enter the keypad code."
                )
                return
        # ── End rentable handling ───────────────────────────────────────────

        if getattr(ex.db, "door_locked", None) and not staff_bypass(self.caller):
            self.caller.msg("It's locked.")
            return
        if getattr(ex.db, "door_locked", None) and staff_bypass(self.caller):
            ex.db.door_locked = False
        if getattr(ex.db, "bioscan", None):
            self.caller.msg("This door requires bioscan verification. Use: verify <direction>")
            return
        ex.db.door_open = True
        sync_door_pair(ex, True)
        door_name = getattr(ex.db, "door_name", None) or "door"
        self.caller.msg(f"You open the {door_name}.")
        loc = self.caller.location
        if loc:
            loc.msg_contents(
                "{name} opens the {dn}.",
                exclude=self.caller,
                mapping={"name": self.caller, "dn": door_name},
                from_obj=self.caller,
            )
        auto_close = int(getattr(ex.db, "door_auto_close", None) or 0)
        if auto_close > 0:
            from world.rpg.factions.doors import auto_close_door

            delay(auto_close, auto_close_door, ex.id)


class CmdCloseDoor(Command):
    """
    Close an open door.

    Usage:
        close <direction>
    """

    key = "close"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.factions.doors import staff_bypass, sync_door_pair
        from world.rpg.rentable_doors import is_rentable, is_paired_with_rentable, rentable_auto_lock_on_close

        if not self.args:
            self.caller.msg("Close which way? Usage: close <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if not getattr(ex.db, "door_open", None):
            self.caller.msg("It's already closed.")
            return
        ex.db.door_open = False
        sync_door_pair(ex, False)
        door_name = getattr(ex.db, "door_name", None) or "door"

        # Auto-lock: rentable exit OR the plain inside exit paired to a rentable door
        if is_rentable(ex) or is_paired_with_rentable(ex):
            rentable_auto_lock_on_close(ex)
            self.caller.msg(f"You close the {door_name}. It locks automatically.")
            loc = self.caller.location
            if loc:
                loc.msg_contents(
                    f"{{name}} closes the {door_name}. It locks with a click.",
                    exclude=self.caller,
                    mapping={"name": self.caller},
                    from_obj=self.caller,
                )
            return

        self.caller.msg(f"You close the {door_name}.")
        loc = self.caller.location
        if loc:
            loc.msg_contents(
                "{name} closes the {dn}.",
                exclude=self.caller,
                mapping={"name": self.caller, "dn": door_name},
                from_obj=self.caller,
            )


class CmdUnlockDoor(Command):
    """Unlock a locked door (requires key in inventory). Staff bypass."""

    key = "unlockdoor"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.factions.doors import staff_bypass, has_key

        if not self.args:
            self.caller.msg("Unlock which way? Usage: unlockdoor <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if not getattr(ex.db, "door_locked", None):
            self.caller.msg("It's not locked.")
            return
        if staff_bypass(self.caller):
            ex.db.door_locked = False
            self.caller.msg("You unlock it (staff).")
            return
        tag = getattr(ex.db, "door_key_tag", None)
        if not has_key(self.caller, tag):
            self.caller.msg("You lack the right key.")
            return
        ex.db.door_locked = False
        self.caller.msg("You unlock it.")


class CmdLockDoor(Command):
    """Lock a door (requires key). Staff bypass."""

    key = "lock"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.factions.doors import staff_bypass, has_key

        if not self.args:
            self.caller.msg("Lock which way? Usage: lockdoor <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args)
        if not ex:
            self.caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            self.caller.msg("There is no door there.")
            return
        if getattr(ex.db, "door_locked", None):
            self.caller.msg("It's already locked.")
            return
        if not getattr(ex.db, "door_open", None):
            self.caller.msg("Close it first.")
            return
        if staff_bypass(self.caller):
            ex.db.door_locked = True
            self.caller.msg("You lock it (staff).")
            return
        tag = getattr(ex.db, "door_key_tag", None)
        if not has_key(self.caller, tag):
            self.caller.msg("You lack the right key.")
            return
        ex.db.door_locked = True
        self.caller.msg("You lock it.")


class CmdVerify(Command):
    """
    Submit to bioscan at a secured door.

    Usage:
        verify <direction>
    """

    key = "verify"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from evennia.utils import delay
        from world.rpg.factions.doors import (
            BIOSCAN_VERIFY_DELAY,
            complete_bioscan_verify_fail,
            complete_bioscan_verify_pass,
            exit_direction_word,
            run_bioscan,
        )

        if not self.args:
            self.caller.msg("Verify at which door? Usage: verify <direction>")
            return
        ex = find_exit_by_direction(self.caller, self.args.strip())
        if not ex:
            self.caller.msg("No exit in that direction.")
            return
        if not getattr(ex.db, "bioscan", None):
            self.caller.msg("That door doesn't have a bioscan.")
            return
        if getattr(ex.db, "door_open", None):
            self.caller.msg("The door is already open.")
            return

        passed, message = run_bioscan(self.caller, ex)
        door_name = getattr(ex.db, "door_name", None) or "bioscan door"
        dir_word = exit_direction_word(ex)

        self.caller.msg(
            f"You submit your biometric credentials for verification at {dir_word}."
        )
        loc = self.caller.location
        if loc:
            loc.msg_contents(
                "{name} submits their biometric credentials for verification at {dir}.",
                exclude=self.caller,
                mapping={"name": self.caller, "dir": dir_word},
                from_obj=self.caller,
            )

        if passed:
            pass_msg = getattr(ex.db, "bioscan_message_pass", None) or "Bioscan accepted."
            delay(
                BIOSCAN_VERIFY_DELAY,
                complete_bioscan_verify_pass,
                self.caller.id,
                ex.id,
                pass_msg,
                door_name,
                dir_word,
            )
        else:
            fail_msg = getattr(ex.db, "bioscan_message_fail", None) or "Bioscan rejected."
            sound_fail = bool(getattr(ex.db, "bioscan_sound_fail", None))
            delay(
                BIOSCAN_VERIFY_DELAY,
                complete_bioscan_verify_fail,
                self.caller.id,
                ex.id,
                fail_msg,
                door_name,
                dir_word,
                sound_fail,
            )
