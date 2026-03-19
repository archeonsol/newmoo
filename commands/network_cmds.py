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
from world.network_decoys import DECOY_COUNT_RANGE, generate_decoy_entries
from world.utils import get_containing_room, room_has_network_coverage

from typeclasses.characters import Character


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
    Placeholder alias: use the character's Matrix ID.
    """
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
    Yield physical `Character` objects currently eligible for The Network:
    their containing room has active Matrix signal coverage.
    """
    for session in evennia.SESSION_HANDLER.get_sessions():
        if hasattr(session, "logged_in") and not session.logged_in:
            continue

        puppet = getattr(session, "puppet", None)
        if not puppet or not isinstance(puppet, Character) or not hasattr(puppet, "msg"):
            continue

        room = get_containing_room(puppet)
        if not room_has_network_coverage(room):
            continue
        yield puppet


class CmdNetworkWho(ICBaseCommand):
    """
    List characters currently on The Network.
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

        # Staged "terminal" output for aesthetics.
        caller.msg("|gReceiving data stream...|n")
        delay(2, self._who_stage2, caller)

    def _who_stage2(self, caller):
        caller = _resolve_meatspace_character(caller)
        if not caller:
            return
        caller.msg("|gResolving data...|n")
        delay(2, self._who_stage3, caller)

    def _who_stage3(self, caller):
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

        # Inject decoys (staff-editable) to emulate a busier global network.
        decoy_n = random.randint(int(DECOY_COUNT_RANGE[0]), int(DECOY_COUNT_RANGE[1]))
        entries.extend(
            generate_decoy_entries(
                count=decoy_n,
                id_col_width=ID_COL_WIDTH,
                tag_col_width=TAG_COL_WIDTH,
                existing_aliases=[a for a, _t in entries],
            )
        )

        # --- Visual aesthetic ---
        border = "=" * TABLE_WIDTH

        title = "THE NETWORK"
        subtitle = f"On Network - Active Users [{len(entries)}]"

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
        line = f"|g[{sender_alias}] >> {raw}|n"

        sent_anywhere = False
        for puppet in _iter_network_physical_characters():
            # If a session has a puppet with msg, we can show it.
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

