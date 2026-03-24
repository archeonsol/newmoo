"""
Rentable door commands.

  rent <direction>              -- rent a vacant apartment door (prompts for 7-digit code)
  payrent <direction>           -- pay one week's rent in advance (anyone can do this)
  push <code> <direction>       -- enter code on the door keypad to unlock
  programdoor <direction>       -- open the door programming menu (master code required via push)

Staff:
  @rentset <direction> cost = <amount>   -- set weekly rent cost
  @rentset <direction> name = <name>     -- set door display name
  @rentset <direction> vacate            -- evict tenant and reset door
  @rentset <direction> info              -- show rental status

Flow for opening a rentable door:
  push 1234567 north   -> "Click. The door unlocks."
  open north           -> door opens normally
  n                    -> move through
  close south          -> door auto-locks

Flow for programming:
  programdoor north    -> prompts: "Enter your master code:"   (via _pending_doorcode)
  <type 7 digits>      -> menu appears
"""

from __future__ import annotations

from commands.base_cmds import Command, ADMIN_LOCK
from world.rpg.economy import get_balance, deduct_funds, format_currency, CURRENCY_NAME


# ---------------------------------------------------------------------------
# UI constants
# ---------------------------------------------------------------------------

_N = "|n"
_W = "|w"
_DIM = "|x"
_ACCENT = "|c"
_GOLD = "|y"
_ERR = "|r"
_OK = "|g"
_LABEL = "|w"
_BOX_W = 58


def _line(char="─"):
    return f"{_ACCENT}{'─' * _BOX_W}{_N}"


def _header(title):
    pad = max(0, _BOX_W - len(title) - 4)
    return f"{_ACCENT}╔══[ {_GOLD}{title}{_ACCENT} ]{'═' * pad}{_N}"


def _row(label, value, lw=14):
    dots = "·" * max(1, lw - len(label))
    return f"  {_LABEL}{label}{_N} {_DIM}{dots}{_N} {value}"


def _footer():
    return f"{_ACCENT}╚{'═' * (_BOX_W - 1)}{_N}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_exit_from_id(exit_id):
    from evennia.utils.search import search_object
    results = search_object(f"#{exit_id}")
    return results[0] if results else None


def _rentable_authority(ex):
    """
    Return the rentable exit that holds codes for this exit.
    If ex itself is rentable, returns ex.
    If ex is a plain door paired to a rentable exit, returns the pair.
    Otherwise returns None.
    """
    from world.rpg.rentable_doors import is_rentable, is_paired_with_rentable, _resolve_door_pair
    if is_rentable(ex):
        return ex
    if is_paired_with_rentable(ex):
        return _resolve_door_pair(ex)
    return None


# ---------------------------------------------------------------------------
# CmdRent
# ---------------------------------------------------------------------------

class CmdRent(Command):
    """
    Rent a vacant apartment door for one week, paying cash on hand.

    Usage:
      rent <direction>

    You must have the weekly rent amount as on-hand cash (not in the bank).
    After paying, you will be prompted to set a 7-digit master code.
    The door auto-locks whenever it is closed. Enter the code with:

      push <code> <direction>

    Use |wpayrent <direction>|n to extend the lease by another week.
    Use |wprogramdoor <direction>|n to manage codes.

    Example:
      rent north
    """

    key = "rent"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        from world.rpg.rentable_doors import find_rentable_exit, is_rented, is_expired

        caller = self.caller
        arg = (self.args or "").strip()
        if not arg:
            caller.msg("Rent which door? Usage: |wrent <direction>|n")
            return

        ex = find_rentable_exit(caller, arg)
        if not ex:
            caller.msg("There is no rentable door in that direction.")
            return

        cost = int(getattr(ex.db, "rent_cost", None) or 0)
        if cost <= 0:
            caller.msg("The rent price for this door has not been set. Contact staff.")
            return

        if is_rented(ex) and not is_expired(ex):
            tenant_name = getattr(ex.db, "rent_tenant_name", "someone")
            caller.msg(f"That door is already rented by |w{tenant_name}|n.")
            return

        wallet = get_balance(caller)
        if wallet < cost:
            caller.msg(
                f"{_ERR}You need {format_currency(cost)} on hand to rent this.{_N}\n"
                f"You have {format_currency(wallet)}."
            )
            return

        door_name = getattr(ex.db, "door_name", None) or "door"
        lines = [
            _header("RENTAL AGREEMENT"),
            _row("Door", door_name),
            _row("Weekly rent", format_currency(cost)),
            _row("On hand", format_currency(wallet)),
            _line(),
            f"  You will be charged {_GOLD}{format_currency(cost, color=False)}{_N} now.",
            f"  Rent is due every 7 days. Use |wpayrent {arg}|n to renew.",
            _line(),
            f"  {_DIM}Enter a 7-digit master code to claim this door, or type |wcancel|n.{_N}",
            _footer(),
        ]
        caller.msg("\n".join(lines))
        caller.ndb._pending_rent = {"exit_id": ex.id, "cost": cost, "arg": arg}


# ---------------------------------------------------------------------------
# CmdPayRent
# ---------------------------------------------------------------------------

class CmdPayRent(Command):
    """
    Pay one week's rent in advance for an apartment door.

    Usage:
      payrent <direction>

    Anyone can pay the rent — you do not have to be the tenant.
    This extends the rental period by exactly one week.

    Example:
      payrent north
    """

    key = "payrent"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        from world.rpg.rentable_doors import find_rentable_exit, is_rented, do_pay_rent, format_time_remaining

        caller = self.caller
        arg = (self.args or "").strip()
        if not arg:
            caller.msg("Pay rent for which door? Usage: |wpayrent <direction>|n")
            return

        ex = find_rentable_exit(caller, arg)
        if not ex:
            caller.msg("There is no rentable door in that direction.")
            return

        if not is_rented(ex):
            caller.msg("That door is not currently rented.")
            return

        cost = int(getattr(ex.db, "rent_cost", None) or 0)
        if cost <= 0:
            caller.msg("The rent price for this door has not been set. Contact staff.")
            return

        wallet = get_balance(caller)
        if wallet < cost:
            caller.msg(
                f"{_ERR}You need {format_currency(cost)} on hand.{_N} "
                f"You have {format_currency(wallet)}."
            )
            return

        door_name = getattr(ex.db, "door_name", None) or "door"
        tenant_name = getattr(ex.db, "rent_tenant_name", "the tenant")

        ok = deduct_funds(caller, cost, party=door_name, reason="weekly rent payment")
        if not ok:
            caller.msg(f"{_ERR}Payment failed.{_N}")
            return

        ok2, msg2 = do_pay_rent(caller, ex)
        if not ok2:
            from world.rpg.economy import add_funds
            add_funds(caller, cost, party=door_name, reason="rent payment refund")
            caller.msg(f"{_ERR}{msg2}{_N}")
            return

        time_left = format_time_remaining(ex)
        lines = [
            _header("RENT PAID"),
            _row("Door", door_name),
            _row("Tenant", tenant_name),
            _row("Paid", format_currency(cost)),
            _row("Remaining", time_left),
            _row("On hand", format_currency(get_balance(caller))),
            _footer(),
        ]
        caller.msg("\n".join(lines))

        tenant_id = getattr(ex.db, "rent_tenant_id", None)
        if tenant_id and tenant_id != caller.id:
            from evennia.utils.search import search_object
            results = search_object(f"#{tenant_id}")
            if results:
                tenant = results[0]
                if hasattr(tenant, "msg"):
                    tenant.msg(
                        f"\n{_ACCENT}[RENT]{_N} {_LABEL}{caller.key}{_N} paid "
                        f"{format_currency(cost)} for |w{door_name}|n. "
                        f"Time remaining: {time_left}."
                    )


# ---------------------------------------------------------------------------
# CmdPush  — keypad code entry
# ---------------------------------------------------------------------------

class CmdPush(Command):
    """
    Enter a code on a door keypad to unlock it.

    Usage:
      push <code> <direction>

    Enters a 7-digit code on the keypad of a rentable door. If the code
    is correct the door unlocks; you can then open it normally.
    The door re-locks automatically when closed.

    Works from both sides of the door.

    Example:
      push 1234567 north
      push 1234567 south
    """

    key = "push"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        from world.rpg.rentable_doors import (
            is_rentable, is_paired_with_rentable, _resolve_door_pair,
            is_rented, is_expired, check_code,
        )
        from world.rpg.factions.doors import staff_bypass, sync_door_pair
        from commands.door_cmds import find_exit_by_direction

        caller = self.caller
        raw = (self.args or "").strip()
        if not raw:
            caller.msg("Usage: |wpush <code> <direction>|n")
            return

        tokens = raw.split()
        if len(tokens) < 2:
            caller.msg("Usage: |wpush <code> <direction>|n")
            return

        code = tokens[0]
        direction = " ".join(tokens[1:])

        ex = find_exit_by_direction(caller, direction)
        if not ex:
            caller.msg("There is no exit in that direction.")
            return
        if not getattr(ex.db, "door", None):
            caller.msg("There is no door there.")
            return

        # Resolve which exit holds the codes
        auth_ex = _rentable_authority(ex)
        if auth_ex is None:
            caller.msg("That door doesn't have a keypad.")
            return

        door_name = getattr(auth_ex.db, "door_name", None) or "door"

        if not is_rented(auth_ex):
            caller.msg(f"The {door_name} is vacant and locked.")
            return

        if is_expired(auth_ex):
            caller.msg(f"|rThe rental has expired. The keypad is inactive.|n")
            return

        if getattr(ex.db, "door_open", None):
            caller.msg(f"The {door_name} is already open.")
            return

        if not getattr(ex.db, "door_locked", None):
            caller.msg(f"The {door_name} is already unlocked.")
            return

        if not check_code(auth_ex, code):
            caller.msg(f"|rIncorrect code.|n")
            loc = caller.location
            if loc:
                loc.msg_contents(
                    f"The {door_name} keypad beeps — incorrect code.",
                    exclude=[caller],
                )
            return

        # Correct — unlock both sides
        ex.db.door_locked = False
        auth_ex.db.door_locked = False

        caller.msg(f"|gClick.|n The {door_name} unlocks.")
        loc = caller.location
        if loc:
            loc.msg_contents(
                f"The {door_name} keypad beeps — {caller.key} enters a code.",
                exclude=[caller],
            )


# ---------------------------------------------------------------------------
# CmdDoorCode  — door programming menu (programdoor)
# ---------------------------------------------------------------------------

class CmdDoorCode(Command):
    """
    Access the programming menu for your rented apartment door.

    Usage:
      programdoor <direction>

    You will be prompted to enter your master code. If correct, you can:
      - Change the master code
      - Add a secondary code (can unlock the door but cannot reprogram it)
      - Remove a secondary code
      - List registered codes

    Example:
      programdoor north
    """

    key = "programdoor"
    aliases = ["pdoor"]
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        from world.rpg.rentable_doors import (
            find_rentable_exit, is_rented, is_expired, is_tenant,
        )
        from world.rpg.factions.doors import staff_bypass

        caller = self.caller
        arg = (self.args or "").strip()
        if not arg:
            caller.msg("Usage: |wprogramdoor <direction>|n")
            return

        ex = find_rentable_exit(caller, arg)
        if not ex:
            caller.msg("There is no rentable door in that direction.")
            return

        if not is_rented(ex):
            caller.msg("That door is not currently rented.")
            return

        if is_expired(ex):
            caller.msg(f"{_ERR}The rental has expired.{_N}")
            return

        if staff_bypass(caller):
            _show_door_menu(caller, ex)
            return

        if not is_tenant(caller, ex):
            caller.msg("Only the tenant can access the door programming menu.")
            return

        door_name = getattr(ex.db, "door_name", None) or "door"
        caller.msg(
            f"{_ACCENT}[ DOOR TERMINAL — {door_name.upper()} ]{_N}\n"
            f"  {_DIM}Enter your master code:{_N}"
        )
        caller.ndb._pending_doorcode = {"exit_id": ex.id}


# ---------------------------------------------------------------------------
# Pending input handler — called by CmdNoMatch
# ---------------------------------------------------------------------------

def handle_pending_input(caller, raw: str) -> bool:
    """
    Check if caller has a pending rent or programdoor input. If so, handle it.
    Returns True if the input was consumed, False otherwise.
    """
    raw = (raw or "").strip()

    # Rent: waiting for initial master code
    pending_rent = getattr(caller.ndb, "_pending_rent", None)
    if pending_rent:
        _handle_rent_code(caller, raw, pending_rent)
        return True

    # Programdoor: waiting for master code authentication
    pending_dc = getattr(caller.ndb, "_pending_doorcode", None)
    if pending_dc and "menu_stage" not in pending_dc:
        _handle_doorcode_auth(caller, raw, pending_dc)
        return True

    # Programdoor: inside a menu stage
    if pending_dc and "menu_stage" in pending_dc:
        _handle_doorcode_menu_input(caller, raw, pending_dc)
        return True

    return False


def _handle_rent_code(caller, raw, pending):
    """Process the 7-digit code entry during the initial rent transaction."""
    from world.rpg.rentable_doors import is_valid_code, do_rent, set_master_code, is_rented, is_expired

    try:
        del caller.ndb._pending_rent
    except Exception:
        pass

    if raw.lower() == "cancel":
        caller.msg("Rental cancelled.")
        return

    if not is_valid_code(raw):
        caller.msg(f"{_ERR}Invalid code.{_N} Codes must be exactly 7 digits. Rental cancelled.")
        return

    exit_id = pending["exit_id"]
    cost = pending["cost"]
    arg = pending.get("arg", "the door")

    ex = _get_exit_from_id(exit_id)
    if not ex:
        caller.msg("The exit no longer exists. Rental cancelled.")
        return

    if is_rented(ex) and not is_expired(ex):
        caller.msg("Someone just rented that door. Rental cancelled.")
        return

    wallet = get_balance(caller)
    if wallet < cost:
        caller.msg(f"{_ERR}Insufficient funds. Rental cancelled.{_N}")
        return

    ok = deduct_funds(caller, cost, party=getattr(ex.db, "door_name", "door"), reason="weekly rent")
    if not ok:
        caller.msg(f"{_ERR}Payment failed. Rental cancelled.{_N}")
        return

    ok2, msg2 = do_rent(caller, ex)
    if not ok2:
        from world.rpg.economy import add_funds
        add_funds(caller, cost, party=getattr(ex.db, "door_name", "door"), reason="rent refund")
        caller.msg(f"{_ERR}{msg2}{_N}")
        return

    set_master_code(ex, raw)

    door_name = getattr(ex.db, "door_name", None) or "door"
    from world.rpg.rentable_doors import format_time_remaining
    lines = [
        _header("RENTAL CONFIRMED"),
        _row("Door", door_name),
        _row("Paid", format_currency(cost)),
        _row("On hand", format_currency(get_balance(caller))),
        _row("Expires in", format_time_remaining(ex)),
        _line(),
        f"  {_DIM}Master code set. Unlock with |wpush {raw} {arg}|n then |wopen {arg}|n.{_N}",
        f"  {_DIM}Use |wprogramdoor {arg}|n to manage codes.{_N}",
        _footer(),
    ]
    caller.msg("\n".join(lines))

    loc = caller.location
    if loc:
        loc.msg_contents(f"|w{caller.key}|n rents the {door_name}.", exclude=[caller])


def _handle_doorcode_auth(caller, raw, pending):
    """Process master code authentication for the programdoor menu."""
    from world.rpg.rentable_doors import is_master_code, is_expired

    exit_id = pending["exit_id"]
    ex = _get_exit_from_id(exit_id)

    def _clear():
        try:
            del caller.ndb._pending_doorcode
        except Exception:
            pass

    if not ex:
        _clear()
        caller.msg("The door is gone.")
        return

    if raw.lower() == "cancel":
        _clear()
        caller.msg("Cancelled.")
        return

    if is_expired(ex):
        _clear()
        caller.msg(f"{_ERR}The rental has expired.{_N}")
        return

    if not is_master_code(ex, raw):
        _clear()
        caller.msg(f"{_ERR}Incorrect master code.{_N}")
        return

    pending["menu_stage"] = "main"
    caller.ndb._pending_doorcode = pending
    _show_door_menu(caller, ex)


def _show_door_menu(caller, ex):
    """Display the door programming menu."""
    from world.rpg.rentable_doors import format_time_remaining

    door_name = getattr(ex.db, "door_name", None) or "door"
    tenant_name = getattr(ex.db, "rent_tenant_name", "—")
    n_secondary = len(list(getattr(ex.db, "rent_secondary_codes", None) or []))

    lines = [
        _header(f"DOOR TERMINAL — {door_name.upper()}"),
        _row("Tenant", tenant_name),
        _row("Expires", format_time_remaining(ex)),
        _row("Secondary codes", str(n_secondary)),
        _line(),
        f"  {_W}1{_N}  Change master code",
        f"  {_W}2{_N}  Add a secondary code",
        f"  {_W}3{_N}  Remove a secondary code",
        f"  {_W}4{_N}  List secondary codes",
        f"  {_W}X{_N}  Exit menu",
        _line(),
        f"  {_DIM}Enter option:{_N}",
        _footer(),
    ]
    caller.msg("\n".join(lines))
    pending = getattr(caller.ndb, "_pending_doorcode", None)
    if not isinstance(pending, dict):
        pending = {}
    pending.setdefault("exit_id", ex.id)
    pending["menu_stage"] = "main"
    caller.ndb._pending_doorcode = pending


def _handle_doorcode_menu_input(caller, raw, pending):
    """Handle menu option selection and sub-prompts."""
    from world.rpg.rentable_doors import (
        is_valid_code, set_master_code, add_secondary_code, remove_secondary_code,
    )

    exit_id = pending["exit_id"]
    ex = _get_exit_from_id(exit_id)

    def _clear():
        try:
            del caller.ndb._pending_doorcode
        except Exception:
            pass

    if not ex:
        _clear()
        caller.msg("The door is gone.")
        return

    stage = pending.get("menu_stage", "main")
    choice = raw.strip().lower()

    if stage == "main":
        if choice in ("x", "exit", "cancel", "quit"):
            _clear()
            caller.msg(f"{_DIM}Door terminal closed.{_N}")
            return

        if choice == "1":
            pending["menu_stage"] = "new_master"
            caller.ndb._pending_doorcode = pending
            caller.msg(f"  {_DIM}Enter new 7-digit master code (or |wcancel|n):{_N}")
            return

        if choice == "2":
            pending["menu_stage"] = "add_secondary"
            caller.ndb._pending_doorcode = pending
            caller.msg(f"  {_DIM}Enter 7-digit secondary code to add (or |wcancel|n):{_N}")
            return

        if choice == "3":
            codes = list(getattr(ex.db, "rent_secondary_codes", None) or [])
            if not codes:
                caller.msg(f"  {_DIM}No secondary codes registered.{_N}")
                _show_door_menu(caller, ex)
                return
            pending["menu_stage"] = "remove_secondary"
            caller.ndb._pending_doorcode = pending
            lines = [f"  {_DIM}Registered secondary codes:{_N}"]
            for i, c in enumerate(codes, 1):
                lines.append(f"    {_W}{i}.{_N} {c}")
            lines.append(f"  {_DIM}Enter code or number to remove (or |wcancel|n):{_N}")
            caller.msg("\n".join(lines))
            return

        if choice == "4":
            codes = list(getattr(ex.db, "rent_secondary_codes", None) or [])
            if not codes:
                caller.msg(f"  {_DIM}No secondary codes registered.{_N}")
            else:
                lines = [f"  {_DIM}Secondary codes ({len(codes)}):{_N}"]
                for i, c in enumerate(codes, 1):
                    lines.append(f"    {_W}{i}.{_N} {c}")
                caller.msg("\n".join(lines))
            _show_door_menu(caller, ex)
            return

        caller.msg(f"{_ERR}Unknown option.{_N}")
        _show_door_menu(caller, ex)
        return

    # Sub-stages: "cancel" returns to main
    if choice == "cancel":
        pending["menu_stage"] = "main"
        caller.ndb._pending_doorcode = pending
        _show_door_menu(caller, ex)
        return

    if stage == "new_master":
        code = raw.strip()
        if not is_valid_code(code):
            caller.msg(f"{_ERR}Must be exactly 7 digits.{_N}")
            caller.msg(f"  {_DIM}Enter new master code (or |wcancel|n):{_N}")
            return
        ok, msg = set_master_code(ex, code)
        caller.msg(f"{_OK}Master code updated.{_N}" if ok else f"{_ERR}{msg}{_N}")
        pending["menu_stage"] = "main"
        caller.ndb._pending_doorcode = pending
        _show_door_menu(caller, ex)
        return

    if stage == "add_secondary":
        code = raw.strip()
        if not is_valid_code(code):
            caller.msg(f"{_ERR}Must be exactly 7 digits.{_N}")
            caller.msg(f"  {_DIM}Enter secondary code to add (or |wcancel|n):{_N}")
            return
        ok, msg = add_secondary_code(ex, code)
        caller.msg(f"{_OK}Secondary code added.{_N}" if ok else f"{_ERR}{msg}{_N}")
        pending["menu_stage"] = "main"
        caller.ndb._pending_doorcode = pending
        _show_door_menu(caller, ex)
        return

    if stage == "remove_secondary":
        code = raw.strip()
        codes = list(getattr(ex.db, "rent_secondary_codes", None) or [])
        if code.isdigit():
            idx = int(code) - 1
            if 0 <= idx < len(codes):
                code = codes[idx]
        ok, msg = remove_secondary_code(ex, code)
        caller.msg(f"{_OK}Secondary code removed.{_N}" if ok else f"{_ERR}{msg}{_N}")
        pending["menu_stage"] = "main"
        caller.ndb._pending_doorcode = pending
        _show_door_menu(caller, ex)
        return


# ---------------------------------------------------------------------------
# CmdCheckDoor  — check <direction>
# ---------------------------------------------------------------------------

class CmdCheckDoor(Command):
    """
    Check the status of a door or rentable apartment in a direction.

    Usage:
      check <direction>

    For rentable doors:
      - If vacant: shows the weekly rent price.
      - If rented: shows only how long the lease has remaining.

    Example:
      check north
    """

    key = "check"
    locks = "cmd:all()"
    help_category = "Housing"

    def func(self):
        from world.rpg.rentable_doors import (
            is_rentable, is_paired_with_rentable, _resolve_door_pair,
            is_rented, is_expired, format_time_remaining,
        )
        from commands.door_cmds import find_exit_by_direction

        caller = self.caller
        arg = (self.args or "").strip()
        if not arg:
            caller.msg("Check what? Usage: |wcheck <direction>|n")
            return

        ex = find_exit_by_direction(caller, arg)
        if not ex:
            caller.msg("There is no exit in that direction.")
            return

        if not getattr(ex.db, "door", None):
            caller.msg("There is no door there.")
            return

        # Resolve rentable authority (works from outside or inside)
        auth_ex = None
        if is_rentable(ex):
            auth_ex = ex
        elif is_paired_with_rentable(ex):
            auth_ex = _resolve_door_pair(ex)

        if auth_ex is None:
            caller.msg("That door is not a rentable apartment.")
            return

        door_name = getattr(auth_ex.db, "door_name", None) or "door"

        # Use the door_name (e.g. "W101") as the label, falling back to "Door"
        label = door_name.upper()

        if is_rented(auth_ex) and not is_expired(auth_ex):
            remaining = format_time_remaining(auth_ex).upper()
            caller.msg(f"|c{label}:|n |yRENTED|n — |w{remaining} REMAINING|n")
            return

        cost = int(getattr(auth_ex.db, "rent_cost", None) or 0)
        if cost <= 0:
            caller.msg(f"|c{label}:|n |gAVAILABLE|n — Contact staff for pricing.")
            return

        caller.msg(
            f"|c{label}:|n |gAVAILABLE|n — "
            f"|w{format_currency(cost, color=False).upper()} PER WEEK|n  "
            f"(|wrent {arg}|n to claim)"
        )


# ---------------------------------------------------------------------------
# Staff: @rentset
# ---------------------------------------------------------------------------

class CmdRentSet(Command):
    """
    Configure a rentable door exit.

    Usage:
      @rentset <direction> cost = <amount>   -- set weekly rent price
      @rentset <direction> name = <doorname> -- set the door's display name
      @rentset <direction> vacate            -- evict tenant and reset door
      @rentset <direction> info              -- show full rental status

    The exit must already be configured as a rentable door via:
      |w@door <direction> = rentable|n

    Example:
      @rentset north cost = 500
      @rentset north name = apartment door
      @rentset north vacate
    """

    key = "@rentset"
    aliases = ["rentset"]
    locks = ADMIN_LOCK
    help_category = "Admin"

    def func(self):
        from world.rpg.rentable_doors import (
            is_rentable, do_vacate, format_time_remaining, is_rented,
        )
        from commands.door_cmds import find_exit_by_direction

        caller = self.caller
        raw = (self.args or "").strip()
        if not raw:
            caller.msg("Usage: |w@rentset <direction> <sub> [= <value>]|n")
            return

        parts = raw.split(None, 1)
        dir_str = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        ex = find_exit_by_direction(caller, dir_str)
        if not ex:
            caller.msg("No exit in that direction.")
            return
        if not is_rentable(ex):
            caller.msg(
                f"That exit is not a rentable door. "
                f"Use |w@door {dir_str} = rentable|n to set it up first."
            )
            return

        if not rest:
            caller.msg("Specify a sub-command: |wcost|n, |wname|n, |wvacate|n, or |winfo|n.")
            return

        if rest.lower() == "vacate":
            tenant = getattr(ex.db, "rent_tenant_name", "nobody")
            do_vacate(ex)
            caller.msg(f"Vacated '{ex.key}'. Previous tenant: {tenant}.")
            return

        if rest.lower() == "info":
            cost = int(getattr(ex.db, "rent_cost", None) or 0)
            rented = is_rented(ex)
            tenant_name = getattr(ex.db, "rent_tenant_name", "—") if rented else "vacant"
            expires_str = format_time_remaining(ex) if rented else "—"
            n_sec = len(list(getattr(ex.db, "rent_secondary_codes", None) or []))
            lines = [
                _header(f"RENTABLE DOOR — {(getattr(ex.db, 'door_name', None) or ex.key).upper()}"),
                _row("Exit key", ex.key),
                _row("DB ref", f"#{ex.id}"),
                _row("Weekly cost", format_currency(cost) if cost else "NOT SET"),
                _row("Status", f"{_OK}Rented{_N}" if rented else f"{_DIM}Vacant{_N}"),
                _row("Tenant", tenant_name),
                _row("Expires in", expires_str),
                _row("Secondary codes", str(n_sec)),
                _footer(),
            ]
            caller.msg("\n".join(lines))
            return

        if "=" in rest:
            sub, val = rest.split("=", 1)
            sub = sub.strip().lower()
            val = val.strip()

            if sub == "cost":
                try:
                    cost = int(val.replace(",", ""))
                except ValueError:
                    caller.msg("Cost must be a number.")
                    return
                if cost <= 0:
                    caller.msg("Cost must be positive.")
                    return
                ex.db.rent_cost = cost
                caller.msg(f"Weekly rent for '{ex.key}' set to {format_currency(cost)}.")
                return

            if sub == "name":
                if not val:
                    caller.msg("Provide a door name.")
                    return
                ex.db.door_name = val
                caller.msg(f"Door name set to '{val}'.")
                return

        caller.msg("Usage: |w@rentset <dir> cost = N|n | |wname = <name>|n | |wvacate|n | |winfo|n")
