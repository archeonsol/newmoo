"""
Multi-puppet session relay: when an NPC puppet (p2, p3, ...) is in an account's
multi-puppet set, relay their messages to the account with a "P2 Name: " prefix
so the player sees the NPC feed alongside their own output.

The main character (p1 = current session puppet) is never relayed — their output
goes directly to the player through the normal session channel.
"""
from evennia.utils import logger


def multi_puppet_relay(character, text, session=None, **kwargs):
    """
    If this character is an NPC puppet (p2+) in an account's multi-puppet set, send
    the message to that account's session(s) with "P2 Name: " prefix so the player
    sees the NPC's feed.

    When the NPC is temporarily the session puppet (e.g. during p2 <cmd> execution),
    we relay and return True so the caller passes session=None to the parent — the
    player sees only the prefixed relay, not a duplicate bare message.

    The main character (p1 = current session puppet) is never relayed here.
    """
    account_id = getattr(character.db, "_multi_puppet_account_id", None)
    slot = getattr(character.db, "_multi_puppet_slot", None)
    if not account_id or not slot:
        return False

    try:
        from evennia.accounts.models import AccountDB
        account = AccountDB.objects.get(id=int(account_id))
    except Exception as err:
        # Catches AccountDB.DoesNotExist, ValueError if ID is invalid, etc.
        # Stale link: clear local markers so we don't keep trying.
        logger.log_trace("multipuppet: failed to get account %s: %s" % (account_id, err))
        try:
            if hasattr(character.db, "_multi_puppet_account_id"):
                del character.db["_multi_puppet_account_id"]
            if hasattr(character.db, "_multi_puppet_slot"):
                del character.db["_multi_puppet_slot"]
        except Exception as cleanup_err:
            logger.log_trace("multipuppet: cleanup stale markers: %s" % cleanup_err)
        return False

    # If this character is no longer in the account's multi_puppets list, treat link as stale.
    try:
        mp_ids = list(getattr(account.db, "multi_puppets", None) or [])
        if getattr(character, "id", None) not in mp_ids:
            try:
                if hasattr(character.db, "_multi_puppet_account_id"):
                    del character.db["_multi_puppet_account_id"]
                if hasattr(character.db, "_multi_puppet_slot"):
                    del character.db["_multi_puppet_slot"]
            except Exception as cleanup_err:
                logger.log_trace("multipuppet: cleanup stale multi_puppets link: %s" % cleanup_err)
            return False
    except Exception as err:
        logger.log_trace("multipuppet: check multi_puppets list: %s" % err)
        return False

    # Don't relay for dead/flatlined/corpse characters — they can't act.
    try:
        from world.death import is_flatlined, is_permanently_dead
        if is_flatlined(character) or is_permanently_dead(character):
            return False
    except Exception:
        pass
    try:
        from typeclasses.corpse import Corpse
        if isinstance(character, Corpse):
            return False
    except Exception:
        pass

    if not hasattr(account, "sessions"):
        return False
    sess_list = account.sessions.get()
    if not sess_list:
        return False

    main_sess = sess_list[0]
    # The main character (p1) is never stored in multi_puppets and never has relay markers set,
    # so it will have already returned False above (no account_id/slot). This check is a safety
    # net in case stale markers exist: never relay for whoever is the real current session puppet.
    own_list = (getattr(character, "sessions", None) or [])
    if hasattr(own_list, "get"):
        own_list = own_list.get() or (own_list.all() if hasattr(own_list, "all") else [])
    has_own_sessions = bool(own_list)
    if getattr(main_sess, "puppet", None) == character and has_own_sessions:
        return False

    # Evennia often passes text as a tuple like ("Message", {"type": "say"})
    raw = text[0] if isinstance(text, (tuple, list)) and text else text
    if not raw or not isinstance(raw, str) or not raw.strip():
        return False
    raw = str(raw)

    prefix = "|cP%s %s|n: " % (slot, character.name)
    try:
        account.msg(prefix + raw, session=sess_list)
    except Exception as err:
        logger.log_trace("multipuppet: account.msg relay: %s" % err)
    # When an NPC is temporarily the session puppet for a p2/p3 command, suppress the bare
    # output so the player only sees the prefixed relay line (not a duplicate unprefixed line).
    return getattr(main_sess, "puppet", None) == character and not has_own_sessions
