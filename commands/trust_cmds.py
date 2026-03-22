"""@trust, @untrust, @trusted — recog-based consent."""

from commands.base_cmds import Command

from world.rpg.trust import (
    TRUST_CATEGORY_KEYS,
    cleanup_stale_trust_entries,
    grant_trust,
    revoke_trust,
    revoke_trust_category,
    _resolve_recog_to_character,
)


class CmdTrust(Command):
    """
    Trust someone to perform actions on you (by the name you recog them as).

    Usage:
        @trust <name>                  — complete trust
        @trust <name> to <category>  — specific trust

    Examples:
        @trust Jake
        @trust Jake to heal
    """

    key = "@trust"
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            caller.msg("Usage: @trust <name> [to <category>]")
            caller.msg("Categories: " + ", ".join(TRUST_CATEGORY_KEYS))
            return

        category = None
        if " to " in args:
            parts = args.split(" to ", 1)
            person_str = parts[0].strip()
            category = parts[1].strip() or None
        else:
            person_str = args

        ok, msg = grant_trust(caller, person_str, category=category)
        if not ok:
            caller.msg(f"|r{msg}|n")
            return

        name_key = person_str.strip().lower()
        if category:
            caller.msg(f"|gYou now trust {person_str} to |w{category.lower()}|g.|n")
        else:
            caller.msg(f"|gYou now trust {person_str} |wcompletely|g.|n")

        trusted = _resolve_recog_to_character(caller, name_key)
        if trusted and trusted != caller:
            cn = (
                caller.get_display_name(trusted)
                if hasattr(caller, "get_display_name")
                else caller.key
            )
            if category:
                trusted.msg(f"|x{cn} now trusts you to: {category.lower()}.|n")
            else:
                trusted.msg(f"|x{cn} now trusts you completely.|n")


class CmdUntrust(Command):
    """
    Revoke trust from someone (by name).

    Usage:
        @untrust <name>                — revoke all trust from this name
        @untrust <name> from <category> — revoke a category
        @untrust all                   — revoke all trust from everyone
    """

    key = "@untrust"
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            caller.msg(
                "Usage: @untrust <name> | @untrust <name> from <category> | @untrust all"
            )
            return

        if args.lower() == "all":
            ok, msg = revoke_trust(caller, revoke_all_people=True)
            caller.msg(f"|y{msg}|n" if ok else f"|r{msg}|n")
            return

        category = None
        if " from " in args:
            parts = args.split(" from ", 1)
            person_str = parts[0].strip()
            category = parts[1].strip().lower()
        else:
            person_str = args

        if category:
            ok, msg = revoke_trust_category(caller, person_str, category)
        else:
            ok, msg = revoke_trust(caller, person_str)

        if ok:
            caller.msg(f"|y{msg}|n")
        else:
            caller.msg(f"|r{msg}|n")


class CmdTrusted(Command):
    """
    Show who you currently trust and for what.

    Usage:
        @trusted
    """

    key = "@trusted"
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        cleanup_stale_trust_entries(caller)
        trust = dict(getattr(caller.db, "trust", None) or {})

        if not trust:
            caller.msg("|xYou trust no one. Smart.|n")
            return

        lines = [
            "|x" + "=" * 48 + "|n",
            "  |wT R U S T   L I S T|n",
            "|x" + "=" * 48 + "|n",
        ]

        for name_key, categories in sorted(trust.items()):
            cats = categories if isinstance(categories, set) else set(categories or [])
            if "all" in cats:
                cat_display = "|wCOMPLETE TRUST|n"
            else:
                cat_display = ", ".join(sorted(cats))
            display_name = (name_key or "").title()
            lines.append(f"  {display_name}: {cat_display}")

        lines.append("|x" + "=" * 48 + "|n")
        lines.append(f"  {len(trust)} trusted. |x@untrust <name> to revoke.|n")
        caller.msg("\n".join(lines))
