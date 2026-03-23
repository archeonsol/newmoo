"""
Multi-puppet commands: add puppet to set, list puppets, run command as p1/p2/.../p9.

Commands in this module inherit from evennia's BaseCommand (not commands.base_cmds.Command)
on purpose: they run at Account level (e.g. addpuppet, p1, p2). Character flatline/dead
checks are not applied here; character-level commands use base_cmds.Command and at_pre_cmd.

Design invariant
----------------
``account.db.multi_puppets`` stores ONLY the IDs of NPC/secondary puppets (p2, p3, ...).
The main character (p1) is NEVER stored in this list — it is always resolved live as
``session.puppet``.  This prevents the relay system from firing for the main character
and causing duplicate output.
"""

from evennia.commands.command import Command as BaseCommand
from evennia.commands.default.account import CmdIC, CmdOOC
from evennia.utils import logger, search, utils
from commands.media_cmds import _get_object_by_id

MAX_MULTI_PUPPETS = 9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_puppet_viable(obj):
    """
    Return True if obj is a living, puppetable character.
    Returns False for:
      - None / missing objects
      - flatlined characters (death_state == flatlined)
      - permanently dead characters (death_state == permanent)
      - Corpse typeclass objects
    """
    if obj is None or not hasattr(obj, "db"):
        return False
    try:
        from world.death import is_flatlined, is_permanently_dead
        if is_flatlined(obj) or is_permanently_dead(obj):
            return False
    except Exception:
        pass
    try:
        from typeclasses.corpse import Corpse
        if isinstance(obj, Corpse):
            return False
    except Exception:
        pass
    return True


def _clear_relay_cache(char):
    """Clear per-character non-persistent relay account cache."""
    ndb = getattr(char, "ndb", None)
    if ndb and hasattr(ndb, "_relay_account_cache"):
        try:
            delattr(ndb, "_relay_account_cache")
        except Exception:
            pass


def _clear_attr(obj, key):
    """Safely remove an Evennia db attribute."""
    try:
        obj.attributes.remove(key)
    except Exception:
        pass


def _clear_multi_puppet_links_for_account(account):
    """Remove relay markers from all NPC puppets in account's multi_puppets list."""
    ids = list(getattr(account.db, "multi_puppets", None) or [])
    for oid in ids:
        obj = _get_object_by_id(oid)
        if obj and hasattr(obj, "db"):
            _clear_attr(obj, "_multi_puppet_account_id")
            _clear_attr(obj, "_multi_puppet_slot")
            _clear_relay_cache(obj)


def _set_multi_puppet_link(char, account_id, slot_1based):
    """Mark a character as being in an account's multi-puppet set at the given slot (1-based)."""
    if char and hasattr(char, "db"):
        char.db._multi_puppet_account_id = account_id
        char.db._multi_puppet_slot = slot_1based
        _clear_relay_cache(char)


def _multi_puppet_account(caller):
    """Return the Account for multi-puppet commands (caller may be Account or Character)."""
    if hasattr(caller, "account") and caller.account:
        return caller.account
    return caller


def _get_session(account, session=None):
    """Return the first active session for account, or the provided session."""
    if session:
        return session
    handler = getattr(account, "sessions", None)
    if handler and hasattr(handler, "get"):
        sess_list = handler.get() or []
        return sess_list[0] if sess_list else None
    return None


def _main_puppet(account, session=None):
    """Return the main character (current session puppet), or None."""
    sess = _get_session(account, session)
    return getattr(sess, "puppet", None) if sess else None


def _prune_dead_puppets(account):
    """
    Remove IDs from multi_puppets (NPC list) that no longer resolve to viable puppets
    (missing objects, flatlined, permanently dead, or Corpse typeclass).
    Clears relay markers on removed entries.
    """
    ids = list(getattr(account.db, "multi_puppets", None) or [])
    valid = []
    for oid in ids:
        obj = _get_object_by_id(oid)
        if _is_puppet_viable(obj):
            valid.append(oid)
        elif obj and hasattr(obj, "db"):
            # Object exists but is dead/flatlined — clear its relay markers.
            _clear_attr(obj, "_multi_puppet_account_id")
            _clear_attr(obj, "_multi_puppet_slot")
            _clear_relay_cache(obj)
    if len(valid) != len(ids):
        account.db.multi_puppets = valid
    return valid


def _npc_puppet_ids(account):
    """
    Return the clean list of NPC puppet IDs (p2, p3, ...) after pruning dead entries.
    The main character (p1) is NOT included here.
    """
    return _prune_dead_puppets(account)


def _multi_puppet_list(account, session=None):
    """
    Return the full ordered list of puppet IDs for display/indexing:
      index 0 = main character (session.puppet, p1) — NOT stored in db
      index 1+ = NPC puppets from account.db.multi_puppets (p2, p3, ...)

    The main character's ID is prepended live; it is never written to
    account.db.multi_puppets.
    """
    npc_ids = _npc_puppet_ids(account)
    main = _main_puppet(account, session)
    if main and getattr(main, "id", None) is not None:
        pid = main.id
        # Safety: if the main character is in the NPC list, exclude it from the
        # returned list but do NOT write to account.db.multi_puppets here.
        # _multi_puppet_list is called from many read paths (including during
        # temporary session.puppet swaps for p2/p3 relay) and a side-effect write
        # would corrupt the list when session.puppet is temporarily an NPC.
        # Actual DB cleanup happens only in _prune_dead_puppets and explicit
        # prune calls (e.g. StaffOnlyPuppet, CmdAddPuppet).
        if pid in npc_ids:
            npc_ids = [oid for oid in npc_ids if oid != pid]
        return [pid] + npc_ids
    return npc_ids


def _ensure_current_puppet_in_list(account, session=None):
    """
    Return the full ordered puppet ID list (main first, then NPCs).
    Ensures NPC relay links are numbered correctly (slot 2, 3, ...).
    Does NOT add the main character to account.db.multi_puppets.
    """
    ids = _multi_puppet_list(account, session=session)
    # Re-number NPC relay links (slots 2, 3, ...) based on their position in the full list.
    for i, oid in enumerate(ids[1:], start=2):
        obj = _get_object_by_id(oid)
        if obj:
            _set_multi_puppet_link(obj, account.id, i)
    return ids


def _resolve_multi_puppet(account, index, session=None):
    """
    Return (Character or None, 0-based index).
    index 0 = main character (session.puppet, p1)
    index 1+ = NPC puppets from db list

    Uses _multi_puppet_list so the main character is never treated as an NPC
    slot even if it was accidentally stored in account.db.multi_puppets.
    """
    ids = _multi_puppet_list(account, session=session)
    if index < 0 or index >= len(ids):
        return None, index
    if index == 0:
        char = _main_puppet(account, session)
        return char, 0
    from evennia.utils.search import search_object
    try:
        ref = "#%s" % int(ids[index])
        result = search_object(ref)
        return (result[0] if result else None), index
    except (TypeError, ValueError):
        return None, index


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

class StaffOnlyPuppet(CmdIC):
    """
    Puppet a character. Staff only (one character per account for players).

    This overrides Evennia's default `CmdIC` search behaviour to be a bit
    more forgiving for NPCs with multi-word names: when run by a Builder+,
    if the normal search does not find a match, we also accept partial
    matches on any word of a character's key in the current room
    (including surnames).
    """

    key = "@puppet"
    aliases = []
    locks = "cmd:perm(Builder)"

    def func(self):
        """
        Staff-only puppet command with relaxed surname/partial matching and
        integration with the multi-puppet system.
        """
        account = self.account
        session = self.session

        new_character = None
        character_candidates = []

        args = (self.args or "").strip()

        if not args:
            # No argument: fall back to last puppet, like default CmdIC.
            character_candidates = [account.db._last_puppet] if account.db._last_puppet else []
            if not character_candidates:
                self.msg("Usage: @puppet <character>")
                return
        else:
            # --- First: use the same logic as Evennia's CmdIC.func ---
            playables = account.characters
            if playables:
                character_candidates.extend(
                    utils.make_iter(
                        account.search(
                            args,
                            candidates=playables,
                            search_object=True,
                            quiet=True,
                        )
                    )
                )

            if account.locks.check_lockstring(account, "perm(Builder)"):
                # Builder+ can puppet beyond their own characters.
                local_matches = []
                if session.puppet:
                    # Local search from current puppet, as in CmdIC.
                    # skip_stealth_filter: stealth-hidden NPCs are still valid @puppet targets for staff.
                    raw = session.puppet.search(args, quiet=True, skip_stealth_filter=True)
                    local_matches = [
                        char
                        for char in utils.make_iter(raw or [])
                        if char and char.access(account, "puppet")
                    ]
                    character_candidates = list(local_matches) or character_candidates

                    # --- Extra: surname/word-part matching in current room ---
                    if not local_matches:
                        loc = getattr(session.puppet, "location", None)
                        if loc and hasattr(loc, "contents_get"):
                            arg_low = args.lower()
                            relaxed = []
                            for obj in loc.contents_get(content_type="character"):
                                if not obj.access(account, "puppet"):
                                    continue
                                key_low = (obj.key or "").lower()
                                words = key_low.split()
                                if any(w.startswith(arg_low) for w in words) or arg_low in key_low:
                                    relaxed.append(obj)
                            if relaxed:
                                character_candidates = list(relaxed)

                # If we still have no candidates at all, fall back to the
                # global object search from CmdIC (keeps default behaviour).
                if not character_candidates:
                    character_candidates.extend(
                        [
                            char
                            for char in search.object_search(args)
                            if char.access(account, "puppet")
                        ]
                    )

        # --- Handle candidates (same semantics as CmdIC) ---
        if not character_candidates:
            self.msg("That is not a valid character choice.")
            return
        if len(character_candidates) > 1:
            self.msg(
                "Multiple targets with the same name:\n %s"
                % ", ".join("%s(#%s)" % (obj.key, obj.id) for obj in character_candidates)
            )
            return

        new_character = character_candidates[0]

        # --- Perform the actual puppeting (same as CmdIC) ---
        try:
            account.puppet_object(session, new_character)
            account.db._last_puppet = new_character
            logger.log_sec(
                f"Puppet Success: (Caller: {account}, Target: {new_character}, IP:"
                f" {self.session.address})."
            )
        except RuntimeError as exc:
            self.msg(f"|rYou cannot become |C{new_character.name}|n: {exc}")
            logger.log_sec(
                f"Puppet Failed: {account} -> {new_character} ({self.session.address}): {exc}"
            )
            return

        # The new main character must never appear in the NPC puppet list.
        # Clear any stale relay markers it may have from a previous life as an NPC puppet.
        puppet = getattr(self.session, "puppet", None)
        if puppet:
            npc_ids = list(getattr(account.db, "multi_puppets", None) or [])
            if getattr(puppet, "id", None) in npc_ids:
                npc_ids = [oid for oid in npc_ids if oid != puppet.id]
                account.db.multi_puppets = npc_ids
            _clear_attr(puppet, "_multi_puppet_account_id")
            _clear_attr(puppet, "_multi_puppet_slot")
            _clear_relay_cache(puppet)
            # Re-number remaining NPC slots.
            for i, oid in enumerate(npc_ids, start=2):
                obj = _get_object_by_id(oid)
                if obj:
                    _set_multi_puppet_link(obj, account.id, i)


class StaffOnlyUnpuppet(CmdOOC):
    """
    Unpuppet / leave character. Staff only.

    Usage:
      @unpuppet              - drop all NPC puppets (p2+), keep p1 puppeted
      @unpuppet all          - same as above
      @unpuppet p2 p3 ...    - drop specific NPC puppet slots while keeping p1
      @unpuppet p1           - fully unpuppet (go OOC)
    """

    key = "@unpuppet"
    aliases = []
    locks = "cmd:perm(Builder)"

    def func(self):
        args = (self.args or "").strip()
        # No arguments or "all": drop all NPC puppets, keep p1 puppeted.
        if not args or args.lower() == "all":
            npc_ids = _npc_puppet_ids(self.account)
            if not npc_ids:
                self.caller.msg("You have no NPC puppets in your set.")
                return
            removed_names = []
            for oid in npc_ids:
                obj = _get_object_by_id(oid)
                if obj and hasattr(obj, "db"):
                    removed_names.append(obj.get_display_name(self.caller))
                    _clear_attr(obj, "_multi_puppet_account_id")
                    _clear_attr(obj, "_multi_puppet_slot")
                    _clear_relay_cache(obj)
            self.account.db.multi_puppets = []
            if removed_names:
                self.caller.msg("Unpuppeted: %s. You remain puppeting your main character." % ", ".join(removed_names))
            else:
                self.caller.msg("Multi-puppet set cleared; you remain puppeting your main character.")
            return

        # With arguments: interpret as one or more p-slots (p2, p3, ...). Only drop those NPC slots.
        tokens = args.split()
        indices_to_remove = set()
        wants_full_unpuppet = False
        for tok in tokens:
            tok = tok.lower()
            if tok.startswith("p") and tok[1:].isdigit():
                idx = int(tok[1:]) - 1  # p1 -> 0, p2 -> 1, ...
                if idx == 0:
                    # Asking to unpuppet p1 too – treat as full unpuppet.
                    wants_full_unpuppet = True
                elif idx > 0:
                    indices_to_remove.add(idx)

        if wants_full_unpuppet or not indices_to_remove:
            # Fall back to full unpuppet if p1 requested or nothing valid parsed.
            _clear_multi_puppet_links_for_account(self.account)
            super().func()
            if hasattr(self.account, "db"):
                self.account.db.multi_puppets = []
            return

        # Remove selected NPC puppet slots.
        # The full list is [main, npc0, npc1, ...] so p2 = npc index 0, p3 = npc index 1, etc.
        npc_ids = _npc_puppet_ids(self.account)
        if not npc_ids:
            self.caller.msg("You have no NPC puppets in your set.")
            return

        removed_names = []
        # Convert p-slot indices to npc_ids indices (subtract 1 since p1 is not in the list).
        npc_indices_to_remove = {idx - 1 for idx in indices_to_remove}
        # Work from highest index down so list pops don't shift earlier indices.
        for npc_idx in sorted(npc_indices_to_remove, reverse=True):
            if 0 <= npc_idx < len(npc_ids):
                oid = npc_ids[npc_idx]
                obj = _get_object_by_id(oid)
                if obj and hasattr(obj, "db"):
                    removed_names.append(obj.get_display_name(self.caller))
                    _clear_attr(obj, "_multi_puppet_account_id")
                    _clear_attr(obj, "_multi_puppet_slot")
                    _clear_relay_cache(obj)
                npc_ids.pop(npc_idx)

        # Re-number remaining NPC slots (slot 2, 3, ...) and persist.
        self.account.db.multi_puppets = npc_ids
        for i, oid in enumerate(npc_ids, start=2):
            obj = _get_object_by_id(oid)
            if obj:
                _set_multi_puppet_link(obj, self.account.id, i)
        if removed_names:
            self.caller.msg("Unpuppeted: %s" % ", ".join(removed_names))


class CmdAddPuppet(BaseCommand):
    """
    Add an NPC to your multi-puppet set without unpuppeting your main character.
    Use p2, p3, ... to run commands as the added NPCs.
    Usage: @addpuppet <character>
    """
    key = "@addpuppet"
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "db"):
            self.msg("No account.")
            return
        session = getattr(self, "session", None)
        if not session:
            self.msg("No session.")
            return
        if not self.args or not self.args.strip():
            self.msg("Usage: @addpuppet <character>")
            return
        # Resolve character: search from current puppet's location or globally.
        raw = self.args.strip()
        searcher = getattr(session, "puppet", None) or self.caller
        # Use quiet=True so we don't emit "Could not find" before our relaxed search succeeds.
        char = (
            searcher.search(raw, global_search=True, quiet=True)
            if hasattr(searcher, "search")
            else None
        )

        # If normal search failed, try a relaxed, room-local surname/partial match.
        if not char and hasattr(searcher, "location"):
            loc = getattr(searcher, "location", None)
            if loc and hasattr(loc, "contents_get"):
                arg_low = raw.lower()
                relaxed = []
                for obj in loc.contents_get(content_type="character"):
                    if not obj.access(account, "puppet"):
                        continue
                    key_low = (getattr(obj, "key", "") or "").lower()
                    words = key_low.split()
                    if any(w.startswith(arg_low) for w in words) or arg_low in key_low:
                        relaxed.append(obj)
                if len(relaxed) == 1:
                    char = relaxed[0]
                elif len(relaxed) > 1:
                    names = [f"{o.name}(#{getattr(o, 'id', '?')})" for o in relaxed]
                    self.msg("Multiple matches for that name here: %s" % ", ".join(names))
                    return

        if not char:
            from evennia.utils.search import search_object
            matches = search_object(raw)
            if isinstance(matches, list) and len(matches) == 1:
                char = matches[0]
            elif isinstance(matches, list) and len(matches) > 1:
                names = [f"{o.name}(#{getattr(o, 'id', '?')})" for o in matches]
                self.msg("Multiple global matches: %s" % ", ".join(names))
                return

        if not char:
            return
        from evennia.utils import make_iter
        char = make_iter(char)[0] if make_iter(char) else char
        if not hasattr(char, "location"):
            self.msg("That's not a character you can puppet.")
            return

        # Prevent adding the main character as an NPC puppet.
        main = _main_puppet(account, session)
        if main and char.id == getattr(main, "id", None):
            self.msg("That's your main character — they're already p1.")
            return

        if not _is_puppet_viable(char):
            self.msg("|r%s|n is dead, flatlined, or otherwise not puppetable." % char.get_display_name(self.caller))
            return

        npc_ids = _npc_puppet_ids(account)
        if char.id in npc_ids:
            self.msg("You already have that character in your puppet set.")
            return
        # p1 slot is the main character; NPC puppets start at p2.
        if len(npc_ids) >= MAX_MULTI_PUPPETS - 1:
            self.msg(f"You can only have {MAX_MULTI_PUPPETS - 1} NPC puppets in your set.")
            return

        npc_ids.append(char.id)
        account.db.multi_puppets = npc_ids
        slot = len(npc_ids) + 1  # p2, p3, ...
        _set_multi_puppet_link(char, account.id, slot)
        self.msg(
            "You add |w%s|n to your puppet set as p%s. Use |wp%s|n to act as them."
            % (char.get_display_name(self.caller), slot, slot)
        )


class CmdPuppetList(BaseCommand):
    """
    List your current multi-puppet set (p1 = you, p2, p3, ... = NPC puppets).
    Usage: @puppet/list
    """
    key = "@puppet/list"
    aliases = ["@puppetlist", "puppet list"]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = getattr(self.caller, "account", self.caller)
        if not hasattr(account, "db"):
            self.msg("No account.")
            return
        session = getattr(self, "session", None)
        main = _main_puppet(account, session)
        npc_ids = _npc_puppet_ids(account)
        if not npc_ids:
            self.msg("You have no NPC puppets in your set. Use |w@addpuppet <name>|n to add NPCs.")
            return

        lines = []
        # p2+: NPC puppets only. p1 (main character) is not shown here.
        for i, oid in enumerate(npc_ids, start=2):
            obj = _get_object_by_id(oid)
            if not obj:
                lines.append("  p%s: |r#%s (gone)|n" % (i, oid))
                continue
            name = obj.get_display_name(self.caller)
            loc_name = obj.location.name if obj.location else "nowhere"
            status = " |r(dead/flatlined)|n" if not _is_puppet_viable(obj) else ""
            lines.append("  p%s: %s (%s)%s" % (i, name, loc_name, status))

        self.msg("|wYour NPC puppet set:|n\n%s" % "\n".join(lines))


class CmdPuppetSlot(BaseCommand):
    """
    Run a command as one of your multi-puppeted characters.
    Usage: p1 <command>   p2 <command>   ...   p9 <command>
    Example: p1 say Hello world   p2 go north
    """
    key = "p1"
    aliases = [f"p{i}" for i in range(2, MAX_MULTI_PUPPETS + 1)]
    locks = "cmd:perm(Builder)"
    help_category = "Admin"

    def func(self):
        account = _multi_puppet_account(self.caller)
        session = getattr(self, "session", None)
        if not session:
            if hasattr(account, "sessions") and account.sessions.get():
                session = account.sessions.get()[0]
        if not session:
            self.msg("No session.")
            return
        # Renumber NPC relay slots so _multi_puppet_slot values are always current.
        _ensure_current_puppet_in_list(account, session=session)
        # Parse slot from cmdstring: p1 -> 0, p2 -> 1, ...
        raw = (self.cmdstring or "").strip().lower()
        if raw.startswith("p") and len(raw) >= 2 and raw[1:].isdigit():
            index = int(raw[1:]) - 1
        else:
            index = 0
        char, _ = _resolve_multi_puppet(account, index, session=session)
        if not char:
            self.msg("You don't have a puppet in slot %s. Use |w@puppet|n and |w@addpuppet|n to build your set." % (index + 1))
            return
        # p1 is always the main character — no liveness gate needed (they act normally).
        if index > 0 and not _is_puppet_viable(char):
            self.msg("|rp%s (%s) is dead or flatlined and cannot act.|n" % (index + 1, char.name))
            return
        sub_cmd = (self.args or "").strip()
        if not sub_cmd:
            self.msg("Usage: %s <command>   (e.g. %s say Hello)" % (self.cmdstring, self.cmdstring))
            return

        old_puppet = getattr(session, "puppet", None)
        session.puppet = char

        try:
            d = char.execute_cmd(sub_cmd, session=session)
            if d is not None and hasattr(d, "addBoth"):
                def _restore(_):
                    session.puppet = old_puppet
                d.addBoth(_restore)
            else:
                session.puppet = old_puppet
        except Exception as e:
            session.puppet = old_puppet
            self.msg("|rError running command: %s|n" % e)
