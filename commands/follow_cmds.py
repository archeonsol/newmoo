"""
Follow / Escort / Shadow commands.

follow <target>   — Follow a character: auto-walk when they depart a room.
shadow <target>   — Shadow a character: like follow but you move in stealth.
escort <target>   — Lead someone: when they input a movement command, you go first,
                    then they follow. Requires the target to have granted you escort trust.

Stopping follow/escort: use |wstop following|n / |wstop escorting|n (see |wstop|n).
"""

from commands.base_cmds import Command, _command_character


def stop_following_activity(caller) -> bool:
    """
    End follow/shadow only. Returns True if the caller was following someone.
    """
    from world.rpg import follow as follow_mod

    target = getattr(caller.ndb, "_following", None)
    if not target:
        caller.msg("|xYou are not following anyone.|n")
        return False
    follow_mod.clear_follow(caller)
    try:
        tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
    except Exception:
        tname = getattr(target, "key", "someone")
    caller.msg(f"|xYou stop following {tname}.|n")
    try:
        cname = caller.get_display_name(target) if hasattr(target, "get_display_name") else caller.key
    except Exception:
        cname = getattr(caller, "key", "someone")
    target.msg(f"|x{cname} stops following you.|n")
    return True


def stop_escorting_activity(caller) -> bool:
    """
    End escort relationships only (being escorted and/or escorting others).
    Returns True if any escort state was cleared.
    """
    from world.rpg import follow as follow_mod

    did_something = False

    escorter = getattr(caller.ndb, "_escorted_by", None)
    if escorter:
        follow_mod.clear_escort(escorter, caller)
        try:
            ename = escorter.get_display_name(caller) if hasattr(escorter, "get_display_name") else escorter.key
        except Exception:
            ename = getattr(escorter, "key", "someone")
        caller.msg(f"|xYou are no longer being escorted by {ename}.|n")
        try:
            cname = caller.get_display_name(escorter) if hasattr(escorter, "get_display_name") else caller.key
        except Exception:
            cname = getattr(caller, "key", "someone")
        escorter.msg(f"|x{cname} has ended the escort.|n")
        did_something = True

    escorts = set(getattr(caller.ndb, "_escorting", None) or set())
    for escorted in escorts:
        follow_mod.clear_escort(caller, escorted)
        try:
            ename = escorted.get_display_name(caller) if hasattr(escorted, "get_display_name") else escorted.key
        except Exception:
            ename = getattr(escorted, "key", "someone")
        caller.msg(f"|xYou stop escorting {ename}.|n")
        try:
            cname = caller.get_display_name(escorted) if hasattr(escorted, "get_display_name") else caller.key
        except Exception:
            cname = getattr(caller, "key", "someone")
        escorted.msg(f"|x{cname} stops escorting you.|n")
        did_something = True

    if not did_something:
        caller.msg("|xYou are not in an escort arrangement.|n")
    return did_something


class CmdFollow(Command):
    """
    Follow a character in the same room.

    When they walk to a new room you will automatically walk in the same
    direction. You can lose them if they go into stealth or move fast enough
    that they are already gone when you arrive.

    Usage:
      follow <name>
      follow           (show who you are following)
    """

    key = "follow"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        from world.rpg import follow as follow_mod
        from world.rpg import stealth

        arg = (self.args or "").strip()

        if not arg:
            target = getattr(caller.ndb, "_following", None)
            if target:
                mode = "shadow" if getattr(caller.ndb, "_following_shadow", False) else "follow"
                try:
                    name = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
                except Exception:
                    name = getattr(target, "key", "someone")
                caller.msg(f"|xYou are {mode}ing {name}.|n")
            else:
                caller.msg("|xYou are not following anyone.|n")
            return

        # Find target in current room
        loc = getattr(caller, "location", None)
        if not loc:
            caller.msg("You have no location.")
            return

        target = caller.search(arg, location=loc)
        if not target:
            return
        if target is caller:
            caller.msg("You can't follow yourself.")
            return

        # Can't follow someone who is hidden and you haven't spotted
        if stealth.is_hidden(target):
            spotted = getattr(target.db, "stealth_spotted_by", None) or []
            try:
                if caller.id not in spotted:
                    caller.msg("You can't follow someone you can't see.")
                    return
            except Exception:
                caller.msg("You can't follow someone you can't see.")
                return

        follow_mod.set_follow(caller, target, shadow=False)

        try:
            tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
        except Exception:
            tname = getattr(target, "key", "someone")
        caller.msg(f"|xYou begin following {tname}.|n")
        try:
            cname = caller.get_display_name(target) if hasattr(target, "get_display_name") else caller.key
        except Exception:
            cname = getattr(caller, "key", "someone")
        target.msg(f"|x{cname} begins following you.|n")


class CmdShadow(Command):
    """
    Shadow a character in stealth.

    Like follow, but you automatically sneak in the direction they move.
    You must not already be in open view when they depart.

    Usage:
      shadow <name>
    """

    key = "shadow"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        from world.rpg import follow as follow_mod
        from world.rpg import stealth

        arg = (self.args or "").strip()
        if not arg:
            caller.msg("Shadow whom?")
            return

        loc = getattr(caller, "location", None)
        if not loc:
            caller.msg("You have no location.")
            return

        target = caller.search(arg, location=loc)
        if not target:
            return
        if target is caller:
            caller.msg("You can't shadow yourself.")
            return

        if stealth.is_hidden(target):
            spotted = getattr(target.db, "stealth_spotted_by", None) or []
            try:
                if caller.id not in spotted:
                    caller.msg("You can't shadow someone you can't see.")
                    return
            except Exception:
                caller.msg("You can't shadow someone you can't see.")
                return

        follow_mod.set_follow(caller, target, shadow=True)

        try:
            tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
        except Exception:
            tname = getattr(target, "key", "someone")
        caller.msg(f"|xYou begin shadowing {tname}, keeping to cover as they move.|n")


class CmdEscort(Command):
    """
    Escort someone: lead them ahead when they move.

    When the escorted person issues a movement command, you depart first,
    then they follow automatically once you are gone. The target must have
    granted you escort trust first (@trust <you> to escort).

    Usage:
      escort <name>       — start escorting this person
      escort              — show who you are currently escorting
    """

    key = "escort"
    locks = "cmd:all()"
    help_category = "Movement"

    def func(self):
        caller = _command_character(self)
        if not getattr(caller, "db", None):
            self.caller.msg("You must be in character to do that.")
            return

        from world.rpg import follow as follow_mod
        from world.rpg.trust import check_trust

        arg = (self.args or "").strip()

        if not arg:
            escorts = getattr(caller.ndb, "_escorting", None) or set()
            if escorts:
                names = []
                for e in escorts:
                    try:
                        n = e.get_display_name(caller) if hasattr(e, "get_display_name") else e.key
                    except Exception:
                        n = getattr(e, "key", "someone")
                    names.append(n)
                caller.msg("|xYou are escorting: " + ", ".join(names) + ".|n")
            else:
                caller.msg("|xYou are not escorting anyone.|n")
            return

        loc = getattr(caller, "location", None)
        if not loc:
            caller.msg("You have no location.")
            return

        target = caller.search(arg, location=loc)
        if not target:
            return
        if target is caller:
            caller.msg("You can't escort yourself.")
            return

        # Check escort trust (target must trust caller for escort)
        if not check_trust(target, caller, "escort"):
            try:
                tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
            except Exception:
                tname = getattr(target, "key", "someone")
            caller.msg(f"|r{tname} has not granted you escort trust. They need to: @trust <you> to escort|n")
            return

        # Remove any existing escort they may have
        existing = getattr(target.ndb, "_escorted_by", None)
        if existing and existing is not caller:
            follow_mod.clear_escort(existing, target)

        follow_mod.set_escort(caller, target)

        try:
            tname = target.get_display_name(caller) if hasattr(target, "get_display_name") else target.key
        except Exception:
            tname = getattr(target, "key", "someone")
        try:
            cname = caller.get_display_name(target) if hasattr(caller, "get_display_name") else caller.key
        except Exception:
            cname = getattr(caller, "key", "someone")
        caller.msg(f"|xYou are now escorting {tname}. You will lead the way when they move.|n")
        target.msg(f"|x{cname} is now escorting you. They will move ahead when you issue movement commands.|n")
