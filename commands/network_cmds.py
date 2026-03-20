"""
IC global communications network: "The Network" (meatspace-only).

Connectivity rule:
  - A character is "on The Network" if the room containing their physical
    character has active Matrix signal coverage (`room_has_network_coverage`).

Matrix coupling:
  - The only Matrix-related data used is the character's Matrix ID as the
    placeholder alias shown on `who` / `sm`.
"""

from __future__ import annotations

from typing import Iterable

import evennia
import random
from evennia.utils import delay
from evennia.utils.evmore import EvMore

from commands.base_cmds import Command as ICBaseCommand
from world.network.network_decoys import DECOY_COUNT_RANGE, generate_decoy_entries
from world.utils import get_containing_room, room_has_network_coverage

from typeclasses.characters import Character
from world.matrix_accounts import get_alias


MAX_SM_LEN = 400
TABLE_WIDTH = 74
# Visible character widths inside the "terminal box" (ignoring Evennia color codes).
ID_COL_WIDTH = 14
TAG_COL_WIDTH = TABLE_WIDTH - 7 - ID_COL_WIDTH  # see row template: "| {ID:<idw} | {TAG:<tagw} |"


def _resolve_meatspace_character(obj) -> Character | None:
    """
    Resolve the physical `Character` required for meatspace-only networking.
    """
    if obj is None or not isinstance(obj, Character):
        return None
    return obj


def _matrix_alias_for_character(character) -> str:
    """
    Network alias.

    Prefers the Matrix account alias (set via handset `set_alias`), and falls
    back to the character's Matrix ID if no alias is set.
    """
    try:
        account_alias = get_alias(character)
    except Exception:
        account_alias = None

    if account_alias:
        # Display with @ prefix (handle aesthetic).
        return f"@{str(account_alias).lstrip('@')}"

    try:
        alias = character.get_matrix_id()
    except Exception:
        alias = None

    if not alias:
        alias = getattr(character, "key", None) or getattr(character, "name", None) or str(character)
    return str(alias)


def _network_tag_for_character(character) -> str:
    """
    Tag shown next to the character's alias in `who`.
    Stored on `character.db.network_tag` (meant as an IC placeholder).
    """
    raw = getattr(getattr(character, "db", None), "network_tag", "") or ""
    raw = str(raw).replace("\r", " ").replace("\n", " ").strip()
    if not raw:
        return ""
    return raw[:TAG_COL_WIDTH]


def _iter_network_physical_characters() -> Iterable[Character]:
    """
    Yield every physical `Character` currently eligible for The Network:
    their containing room has active Matrix signal coverage.

    Used for `who` listings.  Walks *all* multi-puppet slots per account so
    that every covered puppet appears as its own entry, regardless of which
    one the player is currently controlling.
    """
    from commands.multipuppet_cmds import _multi_puppet_list
    from evennia.utils.search import search_object

    seen_puppet_ids: set[int] = set()
    seen_account_ids: set[int] = set()

    for session in evennia.SESSION_HANDLER.get_sessions():
        if hasattr(session, "logged_in") and not session.logged_in:
            continue

        puppet = getattr(session, "puppet", None)
        if not puppet or not isinstance(puppet, Character):
            continue

        account = getattr(puppet, "account", None) or getattr(session, "account", None)

        if account is not None:
            account_id = getattr(account, "id", None) or id(account)
            if account_id in seen_account_ids:
                continue
            seen_account_ids.add(account_id)

            # Yield every covered puppet in this account's multi-puppet set.
            for oid in _multi_puppet_list(account):
                try:
                    result = search_object("#%s" % int(oid))
                    char = result[0] if result else None
                except (TypeError, ValueError):
                    char = None
                if not char or not isinstance(char, Character):
                    continue
                char_id = getattr(char, "pk", None) or id(char)
                if char_id in seen_puppet_ids:
                    continue
                seen_puppet_ids.add(char_id)
                if room_has_network_coverage(get_containing_room(char)):
                    yield char
        else:
            # No account (e.g. NPC): direct coverage check on the session puppet.
            puppet_id = getattr(puppet, "pk", None) or id(puppet)
            if puppet_id in seen_puppet_ids:
                continue
            seen_puppet_ids.add(puppet_id)
            if room_has_network_coverage(get_containing_room(puppet)):
                yield puppet


def _iter_network_sessions_for_broadcast() -> Iterable[Character]:
    """
    Yield one Character per logged-in player that should receive a Network
    broadcast.  A player qualifies if *any* of their multi-puppet characters
    is in a room with active Matrix signal coverage.

    Deduplicates by account so a player with multiple puppets only receives
    the message once, delivered through their currently-active session puppet.
    For characters without an account (e.g. NPCs), falls back to a direct
    coverage check on the session puppet.
    """
    from commands.multipuppet_cmds import _multi_puppet_list
    from evennia.utils.search import search_object

    seen_account_ids: set[int] = set()

    for session in evennia.SESSION_HANDLER.get_sessions():
        if hasattr(session, "logged_in") and not session.logged_in:
            continue

        puppet = getattr(session, "puppet", None)
        if not puppet or not isinstance(puppet, Character) or not hasattr(puppet, "msg"):
            continue

        account = getattr(puppet, "account", None) or getattr(session, "account", None)

        if account is not None:
            account_id = getattr(account, "id", None) or id(account)
            if account_id in seen_account_ids:
                continue
            seen_account_ids.add(account_id)

            # Check every puppet in this account's multi-puppet set for coverage.
            has_coverage = False
            for oid in _multi_puppet_list(account):
                try:
                    result = search_object("#%s" % int(oid))
                    char = result[0] if result else None
                except (TypeError, ValueError):
                    char = None
                if char and isinstance(char, Character):
                    if room_has_network_coverage(get_containing_room(char)):
                        has_coverage = True
                        break

            if has_coverage:
                yield puppet
        else:
            # No account (e.g. NPC): direct coverage check on the session puppet.
            if room_has_network_coverage(get_containing_room(puppet)):
                yield puppet


class CmdNetworkWho(ICBaseCommand):
    """
    List characters currently on The Network.

    Usage:
      who           - list all users on The Network
      who <filter>  - filter results by alias (e.g. `who ja` matches @jazzy)
    """

    key = "who"
    locks = "cmd:all()"
    help_category = "Network"

    def func(self):
        caller = _resolve_meatspace_character(self.caller)  # resolve for alias + coverage
        if not caller:
            self.msg("|rThe Network accepts only meatspace presence right now.|n")
            return

        # Caller must have signal to query the network.
        room = get_containing_room(caller)
        if not room_has_network_coverage(room):
            self.msg("|rYour signal is lost. The Network cannot reach you.|n")
            return

        filter_str = (self.args or "").strip().lower()

        # Staged "terminal" output for aesthetics.
        caller.msg("|gReceiving data stream...|n")
        delay(2, self._who_stage2, caller, filter_str)

    def _who_stage2(self, caller, filter_str=""):
        caller = _resolve_meatspace_character(caller)
        if not caller:
            return
        caller.msg("|gResolving data...|n")
        delay(2, self._who_stage3, caller, filter_str)

    def _who_stage3(self, caller, filter_str=""):
        caller = _resolve_meatspace_character(caller)
        if not caller:
            return

        # Re-check signal at time of display.
        room = get_containing_room(caller)
        if not room_has_network_coverage(room):
            caller.msg("|rYour signal is lost. The Network cannot reach you.|n")
            return

        entries: list[tuple[str, str]] = []  # (alias, tag)
        seen_controller_ids: set[int] = set()

        for controller in _iter_network_physical_characters():
            controller_id = getattr(controller, "pk", None) or id(controller)
            if controller_id in seen_controller_ids:
                continue
            seen_controller_ids.add(controller_id)

            alias = _matrix_alias_for_character(controller)[:ID_COL_WIDTH]
            tag = _network_tag_for_character(controller)
            entries.append((alias, tag))

        if not filter_str:
            decoy_n = random.randint(int(DECOY_COUNT_RANGE[0]), int(DECOY_COUNT_RANGE[1]))
            entries.extend(
                generate_decoy_entries(
                    count=decoy_n,
                    id_col_width=ID_COL_WIDTH,
                    tag_col_width=TAG_COL_WIDTH,
                    existing_aliases=[a for a, _t in entries],
                )
            )

        # Apply filter if provided (case-insensitive substring match on alias).
        if filter_str:
            entries = [(a, t) for a, t in entries if filter_str in a.lower()]

        # --- Visual aesthetic ---
        border = "=" * TABLE_WIDTH

        title = "THE NETWORK"
        subtitle = f"On Network - Active Users [{len(entries)}]" if not filter_str else f"On Network - Filter: {filter_str} [{len(entries)}]"

        # Randomize the order each time.
        random.shuffle(entries)

        # Render as: banner + subtitle + a fixed-width two-column table.
        out_lines = []
        out_lines.append(f"|r{border}|n")
        out_lines.append(f"|y{title.center(TABLE_WIDTH)}|n")
        out_lines.append(f"|r{border}|n")
        out_lines.append(f"|g{subtitle.center(TABLE_WIDTH)}|n")
        out_lines.append(f"|r{border}|n")

        # Header row with vertical separators (ID | TAG).
        out_lines.append(f"|w| {'ID'.ljust(ID_COL_WIDTH)} | {'TAG'.ljust(TAG_COL_WIDTH)} |n")
        # Divider row: separates headers from the actual data rows.
        out_lines.append(f"|r{'-' * TABLE_WIDTH}|n")

        for alias, tag in entries:
            out_lines.append(f"|w| {alias:<{ID_COL_WIDTH}} | {tag:<{TAG_COL_WIDTH}} |n")

        out_lines.append(f"|r{border}|n")

        output = "\n".join(out_lines)
        # Pagination: if many entries, use EvMore.
        if len(entries) > 22:
            EvMore(caller, output)
        else:
            caller.msg(output)


class CmdNetworkSend(ICBaseCommand):
    """
    Send an IC broadcast over The Network.

    Usage:
      sm <message>
    """

    key = "sm"
    aliases: list[str] = []
    locks = "cmd:all()"
    help_category = "Network"

    def func(self):
        raw = (self.args or "").strip()
        if not raw:
            self.msg("Usage: sm <message>")
            return

        if len(raw) > MAX_SM_LEN:
            raw = raw[:MAX_SM_LEN]
            self.msg(f"|yMessage truncated to {MAX_SM_LEN} characters.|n")

        sender_controller = _resolve_meatspace_character(self.caller)
        if not sender_controller:
            self.msg("|rThe Network accepts only meatspace presence right now.|n")
            return

        room = get_containing_room(sender_controller)
        if not room_has_network_coverage(room):
            self.msg("|rYour signal is lost. You cannot send over The Network.|n")
            return

        sender_alias = _matrix_alias_for_character(sender_controller)
        line = f"|g{sender_alias}|n |x>>|n {raw}"

        sent_anywhere = False
        for puppet in _iter_network_sessions_for_broadcast():
            puppet.msg(line)
            sent_anywhere = True

        # Meatspace-only rule: the sender should always see their own
        # broadcast even if nobody else has signal coverage right now.
        if not sent_anywhere and hasattr(self.caller, "msg"):
            self.caller.msg(line)


class CmdNetworkNtag(ICBaseCommand):
    """
    Set your IC Network tag (shown next to your alias in `who`).

    Usage:
      ntag <tag text>
      ntag/clear
    """

    key = "ntag"
    aliases: list[str] = []
    locks = "cmd:all()"
    help_category = "Network"
    switch_options = ("clear",)

    def func(self):
        caller = _resolve_meatspace_character(self.caller)
        if not caller:
            self.msg("|rThe Network accepts only meatspace presence right now.|n")
            return

        clear = "clear" in getattr(self, "switches", [])
        raw = (self.args or "").strip()

        if clear:
            try:
                if hasattr(caller.db, "network_tag"):
                    del caller.db.network_tag
            except Exception:
                caller.db.network_tag = ""
            self.msg("|gNetwork tag cleared.|n")
            return

        if not raw:
            current = _network_tag_for_character(caller)
            self.msg(f"Your current Network tag: |c{current if current else '(none)'}|n")
            self.msg("Usage: ntag <tag text>   or   ntag/clear")
            return

        cleaned = raw.replace("\r", " ").replace("\n", " ").strip()
        if len(cleaned) > TAG_COL_WIDTH:
            cleaned = cleaned[:TAG_COL_WIDTH]
            self.msg(f"|yTag truncated to {TAG_COL_WIDTH} characters to fit the table.|n")

        caller.db.network_tag = cleaned
        self.msg("|gNetwork tag updated.|n")
