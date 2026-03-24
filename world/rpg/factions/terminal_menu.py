"""
EvMenu for faction registry terminals. Leadership options require rank permission 3+ for
players; Builder/Admin accounts bypass (full menu, remote target resolve, enlist without
same-room).
"""

from evennia.utils.ansi import strip_ansi
from world.ui_utils import display_ljust, figlet_banner, naturaltime, intword

try:
    from more_itertools import chunked as _chunked
except ImportError:
    def _chunked(iterable, n):
        lst = list(iterable)
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
from evennia.utils.search import search_object

from world.rpg.factions import get_faction, is_faction_member
from world.rpg.factions.membership import (
    enlist,
    discharge,
    promote,
    demote,
    set_rank,
    get_member_rank,
    get_member_permission,
    get_faction_roster,
    ensure_faction_join_timestamp,
)
from world.rpg.factions.ranks import get_rank_name, get_max_rank, get_rank_pay
from world.rpg.factions.pay import can_collect_pay, collect_pay

_W = 52
_N = "|n"
_DIM = "|x"
_LABEL = "|w"

ROSTER_PAGE_SIZE = 30


def _faction_line(fdata, char="="):
    c = fdata.get("color", "|w") if fdata else "|w"
    return f"{c}{char * _W}{_N}"


def _line(fdata=None):
    c = (fdata or {}).get("color", "|x") if fdata else "|x"
    return f"{c}{'-' * _W}{_N}"


def _is_staff(caller):
    try:
        acc = getattr(caller, "account", None)
        if acc and (acc.permissions.check("Builder") or acc.permissions.check("Admin")):
            return True
    except Exception:
        pass
    return False


def _terminal_perm(caller, faction_key):
    """In-character faction permission (rank only); staff account does not elevate."""
    return get_member_permission(caller, faction_key, elevate_staff=False)


def _terminal_leadership_ok(caller, faction_key):
    """Leadership terminal features: rank permission 3+, or staff bypass."""
    if _is_staff(caller):
        return True
    return _terminal_perm(caller, faction_key) >= 3


def _terminal_fdata(terminal):
    key = getattr(getattr(terminal, "db", None), "faction_key", None)
    return get_faction(key) if key else None


def _format_joined_ago(character, faction_key):
    ts = ensure_faction_join_timestamp(character, faction_key)
    if ts is None:
        return "—"
    return naturaltime(ts)


def _pay_status_line(caller, fdata):
    can, reason, amount = can_collect_pay(caller, fdata["key"])
    if can:
        return f"{intword(amount)}/week (available)"
    weekly = get_rank_pay(fdata["ranks"], get_member_rank(caller, fdata["key"]))
    return f"{intword(weekly)}/week ({reason})"


def _get_terminal(caller, kwargs):
    t = kwargs.get("terminal")
    if not t:
        t = getattr(getattr(caller, "ndb", None), "_faction_terminal", None)
    return t


def start_faction_terminal(caller, terminal):
    """Open the registry EvMenu for this terminal."""
    from evennia.utils.evmenu import EvMenu

    for attr in (
        "_faction_terminal",
        "_faction_enlist_line",
        "_faction_promote_line",
        "_faction_demote_line",
        "_faction_discharge_line",
        "_faction_setrank_name_line",
        "_faction_setrank_rank_line",
        "_faction_setrank_target",
    ):
        try:
            delattr(caller.ndb, attr)
        except Exception:
            pass
    try:
        caller.ndb._faction_terminal = terminal
    except Exception:
        pass
    EvMenu(
        caller,
        "world.rpg.factions.terminal_menu",
        startnode="node_terminal_main",
        terminal=terminal,
        persistent=False,
    )


def node_terminal_main(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        caller.msg(f"{_DIM}Terminal offline.{_N}")
        return None, None

    staff = _is_staff(caller)
    member = is_faction_member(caller, fdata["key"]) or staff
    allow_public = bool(getattr(getattr(terminal, "db", None), "allow_public_info", False))

    if not member and not staff:
        text = (
            f"{_faction_line(fdata)}\n"
            f"  {fdata['color']}{fdata['name'].upper()} — REGISTRY{_N}\n"
            f"{_faction_line(fdata)}\n\n"
        )
        if allow_public:
            text += f"  {_DIM}{fdata['description']}{_N}\n\n"
            text += f"  {_DIM}Public information only. Not a member.{_N}\n"
        else:
            text += "  |rACCESS DENIED.|n\n"
            text += f"  {_DIM}You are not a member of {fdata['name']}.{_N}\n"
        text += f"\n{_line(fdata)}\n"
        options = [{"key": "q", "desc": "Disconnect", "goto": "node_terminal_exit"}]
        return text, options

    rank = get_member_rank(caller, fdata["key"])
    rname = get_rank_name(fdata["ranks"], rank) if rank else "—"
    text = (
        f"{_faction_line(fdata)}\n"
        f"  {fdata['color']}{fdata['name'].upper()} — REGISTRY TERMINAL{_N}\n"
        f"{_faction_line(fdata)}\n\n"
        f"  {_LABEL}Name:{_N}    {caller.key}\n"
        f"  {_LABEL}Rank:{_N}    {rname} ({rank})\n"
        f"  {_LABEL}Joined:{_N}  {_format_joined_ago(caller, fdata['key'])}\n"
        f"  {_LABEL}Pay:{_N}     {_pay_status_line(caller, fdata)}\n\n"
        f"{_line(fdata)}\n"
    )

    options = []
    n = 1

    def add_opt(desc, node, **extra):
        nonlocal n
        opts = {"key": str(n), "desc": desc, "goto": (node, {"terminal": terminal, **extra})}
        options.append(opts)
        n += 1

    lead_ok = _terminal_leadership_ok(caller, fdata["key"])
    add_opt("Collect pay", "node_collect_pay")
    if lead_ok:
        add_opt("View roster", "node_view_roster", roster_page=0)
    add_opt("View own record", "node_own_record")

    if lead_ok:
        add_opt("Enlist new member", "node_enlist")
        add_opt("Promote member", "node_promote_pick")
        add_opt("Demote member", "node_demote_pick")
        add_opt("Discharge member", "node_discharge_pick")
        add_opt("Set rank (leader)", "node_setrank_pick_name")

    options.append({"key": "q", "desc": "Disconnect", "goto": "node_terminal_exit"})

    # numeric keys 1..n map to options - EvMenu uses key from options
    return text, options


def node_terminal_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}Session closed.{_N}")
    return None, None


def node_collect_pay(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    ok, msg, amt = collect_pay(caller, fdata["key"])
    if ok:
        caller.msg(f"|g{msg}|n")
    else:
        caller.msg(f"|r{msg}|n")
    return node_terminal_main(caller, raw_string, terminal=terminal)


def node_view_roster(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    page = int(kwargs.get("roster_page", 0) or 0)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied. Leadership clearance required.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    roster = get_faction_roster(fdata["key"], limit=50)
    total = len(roster)
    pages = list(_chunked(roster, ROSTER_PAGE_SIZE))
    chunk = pages[page] if page < len(pages) else []

    lines = [
        f"{_faction_line(fdata, '-')}",
        f"  ROSTER — {fdata['name'].upper()}",
        f"{_faction_line(fdata, '-')}",
    ]
    for char, rnk in chunk:
        rname = get_rank_name(fdata["ranks"], rnk)
        joined = _format_joined_ago(char, fdata["key"])
        name_col = display_ljust(str(char.key)[:22], 22)
        rank_col = display_ljust(rname[:16], 16)
        lines.append(f"  {name_col} [{rnk}] {rank_col} {joined:>5}")
    lines.append(f"{_faction_line(fdata, '-')}")
    lines.append(f"  {total} member(s). (page {page + 1})")

    text = "\n".join(lines) + "\n"
    options = [{"key": "q", "desc": "Back", "goto": ("node_terminal_main", {"terminal": terminal})}]
    if page > 0:
        options.insert(
            0,
            {
                "key": "p",
                "desc": "Previous page",
                "goto": (
                    "node_view_roster",
                    {"terminal": terminal, "roster_page": page - 1},
                ),
            },
        )
    if (page + 1) * ROSTER_PAGE_SIZE < total:
        options.insert(
            0,
            {
                "key": "n",
                "desc": "Next page",
                "goto": (
                    "node_view_roster",
                    {"terminal": terminal, "roster_page": page + 1},
                ),
            },
        )
    return text, options


def node_own_record(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata or not is_faction_member(caller, fdata["key"]):
        caller.msg("|rNo record for this faction.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    rank = get_member_rank(caller, fdata["key"])
    rname = get_rank_name(fdata["ranks"], rank)
    joined = _format_joined_ago(caller, fdata["key"])
    last_pay = (caller.db.faction_pay_collected or {}).get(fdata["key"])
    pay_s = "Never"
    if last_pay:
        pay_s = naturaltime(last_pay)

    log = caller.db.faction_log or []
    log_lines = [e for e in log if e.get("faction") == fdata["key"]][-10:]

    lines = [
        f"{_faction_line(fdata)}",
        f"  RECORD — {fdata['short_name'].upper()}",
        f"{_faction_line(fdata)}",
        f"  Rank: {rname} ({rank})",
        f"  Joined: {joined}",
        f"  Last pay recorded: {pay_s}",
        "",
        "  Recent log:",
    ]
    for entry in log_lines:
        details = entry.get("details", "")
        ev = entry.get("event", "")
        lines.append(f"  — {ev}: {details[:60]}")

    text = "\n".join(lines) + f"\n\n{_line(fdata)}\n  q — Back\n"
    options = [{"key": "q", "desc": "Back", "goto": ("node_terminal_main", {"terminal": terminal})}]
    return text, options


def _resolve_target_name(caller, name, terminal, remote_ok):
    """Resolve a character by key/name in room, or by dbref if remote_ok (staff)."""
    name = strip_ansi(name or "").strip()
    if not name:
        return None

    try:
        from typeclasses.characters import Character
    except ImportError:
        Character = None

    if name.lower() in ("me", "self") and Character and isinstance(caller, Character):
        return caller

    if name.startswith("#"):
        if not remote_ok:
            return None
        o = search_object(name)
        target = o[0] if o else None
    else:
        room = caller.location
        if not room:
            return None
        results = caller.search(
            name,
            location=room,
            quiet=True,
            use_locks=False,
        )
        if not results:
            target = _scan_room_for_character_name(room, name)
        else:
            target = results[0] if isinstance(results, (list, tuple)) else results

    if not target or not hasattr(target, "tags") or not hasattr(target, "db"):
        return None
    if Character and isinstance(target, Character):
        return target
    try:
        from typeclasses.npc import NPC

        if isinstance(target, NPC):
            return target
    except ImportError:
        pass
    return None


def _scan_room_for_character_name(room, name):
    """Case-insensitive key/alias match; avoids search-lock false negatives."""
    try:
        from typeclasses.characters import Character
    except ImportError:
        return None

    want = name.strip().lower()
    for obj in room.contents:
        if not isinstance(obj, Character):
            continue
        if getattr(obj, "key", "").strip().lower() == want:
            return obj
        try:
            for al in obj.aliases.all():
                if str(al).strip().lower() == want:
                    return obj
        except Exception:
            pass
    return None


def node_enlist(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied. Insufficient clearance.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_enlist_line"
    if not getattr(caller.ndb, wait_key, False):
        setattr(caller.ndb, wait_key, True)
        text = "Enter name of character to enlist (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_enlist", {"terminal": terminal})},
            {"key": "q", "desc": "Cancel", "goto": ("node_enlist_cancel", {"terminal": terminal})},
        ]
        return text, options

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel", ""):
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("|rNo match. Try again or type |wq|n to cancel.|n")
        text = "Enter name of character to enlist (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_enlist", {"terminal": terminal})},
            {"key": "q", "desc": "Cancel", "goto": ("node_enlist_cancel", {"terminal": terminal})},
        ]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    if not hasattr(target, "tags"):
        caller.msg("|rInvalid target.|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_enlist_confirm(
        caller,
        "",
        terminal=terminal,
        enlist_target=target,
    )


def node_enlist_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_enlist_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_enlist_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("enlist_target")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        staff = _is_staff(caller)
        if not staff:
            if not caller.location or target.location != caller.location:
                caller.msg("Target must be present at this terminal.")
                return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = enlist(target, fdata["key"], enlisted_by=caller.key)
        caller.msg(msg if ok else f"|r{msg}|n")
        if target != caller:
            target.msg(f"|yYou have been enlisted in {fdata['name']}.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    tname = target.key
    text = (
        f"Enlist |w{tname}|n at default rank in {fdata['name']}?\n"
        f"  y — Confirm\n  n — Cancel\n"
    )
    options = [
        {"key": ("y", "yes", "1"), "desc": "Confirm", "goto": ("node_enlist_confirm", kwargs)},
        {"key": ("n", "no", "2"), "desc": "Cancel", "goto": ("node_terminal_main", {"terminal": terminal})},
    ]
    return text, options


def _can_promote_to(caller, fdata, target, new_rank):
    """Return (ok, err_msg)."""
    if _is_staff(caller):
        return True, None
    perm_ic = _terminal_perm(caller, fdata["key"])
    if perm_ic < 3:
        return False, "Insufficient clearance. Leadership only."
    op_rank = get_member_rank(caller, fdata["key"])
    if new_rank >= op_rank:
        return False, "You cannot promote anyone to your rank or above."
    return True, None


def _can_affect_rank(caller, fdata, target_rank, discharge=False):
    """Whether caller may change/discharge someone at target_rank."""
    if _is_staff(caller):
        return True, None
    perm_ic = _terminal_perm(caller, fdata["key"])
    if perm_ic < 3:
        return False, "Insufficient clearance. Leadership only."
    op_rank = get_member_rank(caller, fdata["key"])
    if target_rank >= op_rank:
        return False, "Target's rank is not below yours."
    return True, None


def node_promote_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_promote_line"
    if not getattr(caller.ndb, wait_key, False):
        setattr(caller.ndb, wait_key, True)
        text = "Name of member to promote (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_promote_pick", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_promote_cancel", {"terminal": terminal})},
        ]
        return text, options

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel", ""):
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("|rNo match. Try again or type |wq|n to cancel.|n")
        text = "Name of member to promote (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_promote_pick", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_promote_cancel", {"terminal": terminal})},
        ]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    if target == caller:
        caller.msg("You cannot promote yourself.")
        return node_terminal_main(caller, "", terminal=terminal)

    if not is_faction_member(target, fdata["key"]):
        caller.msg("They are not a member of this faction.")
        return node_terminal_main(caller, "", terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    max_r = get_max_rank(fdata["ranks"])
    if cur >= max_r:
        caller.msg("They are already at maximum rank.")
        return node_terminal_main(caller, "", terminal=terminal)

    new_rank = cur + 1
    ok, err = _can_promote_to(caller, fdata, target, new_rank)
    if not ok:
        caller.msg(f"|r{err}|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_promote_confirm(
        caller,
        "",
        terminal=terminal,
        promote_target=target,
        new_rank=new_rank,
    )


def node_promote_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_promote_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_promote_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("promote_target")
    new_rank = kwargs.get("new_rank")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = promote(
            target,
            fdata["key"],
            promoted_by=caller.key,
            operator=caller,
        )
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|yYour rank in {fdata['name']} has changed.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    text = (
        f"Promote |w{target.key}|n from rank {cur} to {new_rank}?\n"
        f"  y / n\n"
    )
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": ("node_promote_confirm", kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": ("node_terminal_main", {"terminal": terminal})},
    ]
    return text, options


def node_demote_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_demote_line"
    if not getattr(caller.ndb, wait_key, False):
        setattr(caller.ndb, wait_key, True)
        text = "Name of member to demote (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_demote_pick", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_demote_cancel", {"terminal": terminal})},
        ]
        return text, options

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel", ""):
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("|rNo match. Try again or type |wq|n to cancel.|n")
        text = "Name of member to demote (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_demote_pick", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_demote_cancel", {"terminal": terminal})},
        ]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    if target == caller:
        caller.msg("You cannot demote yourself.")
        return node_terminal_main(caller, "", terminal=terminal)

    if not is_faction_member(target, fdata["key"]):
        caller.msg("They are not a member.")
        return node_terminal_main(caller, "", terminal=terminal)

    tr = get_member_rank(target, fdata["key"])
    ok, err = _can_affect_rank(caller, fdata, tr)
    if not ok:
        caller.msg(f"|r{err}|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_demote_confirm(caller, "", terminal=terminal, demote_target=target)


def node_demote_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_demote_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_demote_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("demote_target")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = demote(
            target,
            fdata["key"],
            demoted_by=caller.key,
            operator=caller,
        )
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|yYour rank in {fdata['name']} has changed.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    text = f"Demote |w{target.key}|n from rank {cur} by one step?\n  y / n\n"
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": ("node_demote_confirm", kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": ("node_terminal_main", {"terminal": terminal})},
    ]
    return text, options


def node_discharge_pick(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_discharge_line"
    if not getattr(caller.ndb, wait_key, False):
        setattr(caller.ndb, wait_key, True)
        text = "Name of member to discharge (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_discharge_pick", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_discharge_cancel", {"terminal": terminal})},
        ]
        return text, options

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel", ""):
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("|rNo match. Try again or type |wq|n to cancel.|n")
        text = "Name of member to discharge (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_discharge_pick", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_discharge_cancel", {"terminal": terminal})},
        ]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    if target == caller:
        caller.msg("You cannot discharge yourself from this terminal.")
        return node_terminal_main(caller, "", terminal=terminal)

    if not is_faction_member(target, fdata["key"]):
        caller.msg("They are not a member.")
        return node_terminal_main(caller, "", terminal=terminal)

    tr = get_member_rank(target, fdata["key"])
    ok, err = _can_affect_rank(caller, fdata, tr, discharge=True)
    if not ok:
        caller.msg(f"|r{err}|n")
        return node_terminal_main(caller, "", terminal=terminal)

    return node_discharge_confirm(caller, "", terminal=terminal, discharge_target=target)


def node_discharge_cancel(caller, raw_string, **kwargs):
    try:
        delattr(caller.ndb, "_faction_discharge_line")
    except Exception:
        pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_discharge_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("discharge_target")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = discharge(target, fdata["key"], discharged_by=caller.key, reason="discharged")
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|rYou have been discharged from {fdata['name']}.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    text = (
        f"Discharge |w{target.key}|n from {fdata['name']}? They lose rank and clearance.\n"
        f"  y / n\n"
    )
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": ("node_discharge_confirm", kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": ("node_terminal_main", {"terminal": terminal})},
    ]
    return text, options


def node_setrank_pick_name(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    if not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)
    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied. Leader clearance required.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_setrank_name_line"
    if not getattr(caller.ndb, wait_key, False):
        setattr(caller.ndb, wait_key, True)
        text = "Name of member (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_setrank_pick_name", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})},
        ]
        return text, options

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel", ""):
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    target = _resolve_target_name(caller, line, terminal, remote_ok=_is_staff(caller))
    if not target:
        caller.msg("|rNo match. Try again or type |wq|n to cancel.|n")
        text = "Name of member (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_setrank_pick_name", {"terminal": terminal})},
            {"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})},
        ]
        return text, options

    if not is_faction_member(target, fdata["key"]):
        caller.msg("|rNot a member.|n")
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    return node_setrank_pick_rank(
        caller,
        "",
        terminal=terminal,
        setrank_target=target,
    )


def node_setrank_pick_rank(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal") or _get_terminal(caller, kwargs)
    fdata = _terminal_fdata(terminal)
    target = kwargs.get("setrank_target")

    if not fdata or not target:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not _terminal_leadership_ok(caller, fdata["key"]):
        caller.msg("|rAccess denied. Leader clearance required.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    wait_key = "_faction_setrank_rank_line"
    if not getattr(caller.ndb, wait_key, False):
        setattr(caller.ndb, wait_key, True)
        text = "Enter new rank number (or |wq|n to cancel):\n"
        rank_kw = {"terminal": terminal, "setrank_target": target}
        options = [
            {"key": "_default", "goto": ("node_setrank_pick_rank", rank_kw)},
            {"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})},
        ]
        return text, options

    line = (raw_string or "").strip()
    if line.lower() in ("q", "quit", "cancel", ""):
        try:
            delattr(caller.ndb, wait_key)
        except Exception:
            pass
        return node_terminal_main(caller, "", terminal=terminal)

    rank_kw = {"terminal": terminal, "setrank_target": target}
    try:
        new_r = int(line)
    except ValueError:
        caller.msg("|rEnter a number.|n")
        text = "Enter new rank number (or |wq|n to cancel):\n"
        options = [
            {"key": "_default", "goto": ("node_setrank_pick_rank", rank_kw)},
            {"key": "q", "desc": "Back", "goto": ("node_setrank_cancel", {"terminal": terminal})},
        ]
        return text, options

    try:
        delattr(caller.ndb, wait_key)
    except Exception:
        pass

    return node_setrank_confirm(
        caller,
        "",
        terminal=terminal,
        setrank_target=target,
        setrank_new=new_r,
    )


def node_setrank_cancel(caller, raw_string, **kwargs):
    for attr in (
        "_faction_setrank_name_line",
        "_faction_setrank_rank_line",
        "_faction_setrank_target",
    ):
        try:
            delattr(caller.ndb, attr)
        except Exception:
            pass
    return node_terminal_main(caller, raw_string, **kwargs)


def node_setrank_confirm(caller, raw_string, **kwargs):
    terminal = kwargs.get("terminal")
    target = kwargs.get("setrank_target")
    new_r = kwargs.get("setrank_new")
    fdata = _terminal_fdata(terminal)

    if raw_string and raw_string.strip().lower() in ("y", "yes", "1"):
        if not target or not fdata:
            return node_terminal_main(caller, raw_string, terminal=terminal)
        ok, msg = set_rank(target, fdata["key"], new_r, set_by=caller.key)
        caller.msg(msg if ok else f"|r{msg}|n")
        if ok and target != caller:
            target.msg(f"|yYour rank in {fdata['name']} has been set.|n")
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if raw_string and raw_string.strip().lower() in ("n", "no", "2", "q"):
        return node_terminal_main(caller, raw_string, terminal=terminal)

    if not target or not fdata:
        return node_terminal_main(caller, raw_string, terminal=terminal)

    cur = get_member_rank(target, fdata["key"])
    text = f"Set |w{target.key}|n from rank {cur} to {new_r}? y/n\n"
    options = [
        {"key": ("y", "yes"), "desc": "Confirm", "goto": ("node_setrank_confirm", kwargs)},
        {"key": ("n", "no", "q"), "desc": "Cancel", "goto": ("node_terminal_main", {"terminal": terminal})},
    ]
    return text, options
