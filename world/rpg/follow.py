"""
Follow / Escort / Shadow system.

Follow  — auto-queue a walk step when the target departs a room.
          Fails silently if target is in stealth and follower can't see them,
          or if target moves fast enough that they're gone by the time follower arrives.
Escort  — inverse of follow: when the escorted person issues a move command, the
          escorter departs first, then the escorted follows automatically.
Shadow  — like follow but follower moves in stealth (sneak).

State is stored on ndb (volatile; cleared on reload/disconnect):
  character.ndb._following          = target Character or None
  character.ndb._following_shadow   = True if shadow mode
  character.ndb._escorting          = set of Character objects being escorted
  character.ndb._escorted_by        = Character escorting this character or None

Public API
----------
  set_follow(follower, target, shadow=False)
  clear_follow(follower)
  set_escort(escorter, escorted)
  clear_escort(escorter, escorted)
  get_followers(character) -> list[Character]
  get_escorts(character) -> list[(escorter, shadow)]
  notify_departure(mover, destination, direction_norm)  # called from staggered_movement
  handle_escort_move(escorted, direction_norm) -> bool   # called from Exit.at_traverse
"""

from __future__ import annotations

from evennia.utils.search import search_object

# How long (seconds) after the leader arrives in a room to give up waiting for follower.
# This prevents orphaned follow-callbacks from firing in wrong rooms.
FOLLOW_WINDOW = 15.0


def _safe_id(obj) -> int | None:
    try:
        return int(obj.id)
    except Exception:
        return None


def _resolve(obj_id: int):
    try:
        results = search_object("#%s" % obj_id)
        return results[0] if results else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Follow state helpers
# ---------------------------------------------------------------------------

def set_follow(follower, target, shadow: bool = False) -> None:
    """Register follower as following target (optionally in shadow/stealth mode)."""
    if not follower or not target:
        return
    clear_follow(follower)
    follower.ndb._following = target
    follower.ndb._following_shadow = bool(shadow)

    # Register follower on the target's follower set
    followers = getattr(target.ndb, "_followed_by", None)
    if followers is None:
        followers = set()
        target.ndb._followed_by = followers
    followers.add(follower)


def clear_follow(follower) -> None:
    """Unregister follower. Cleans up target's _followed_by set too."""
    if not follower:
        return
    target = getattr(follower.ndb, "_following", None)
    if target:
        try:
            fs = getattr(target.ndb, "_followed_by", None)
            if fs and follower in fs:
                fs.discard(follower)
        except Exception:
            pass
    follower.ndb._following = None
    follower.ndb._following_shadow = False


def get_followers(character) -> list:
    """Return list of characters currently following this character."""
    fs = getattr(character.ndb, "_followed_by", None)
    if not fs:
        return []
    # Prune dead references
    alive = {f for f in fs if getattr(f, "ndb", None) and getattr(f.ndb, "_following", None) is character}
    character.ndb._followed_by = alive
    return list(alive)


# ---------------------------------------------------------------------------
# Escort state helpers
# ---------------------------------------------------------------------------

def set_escort(escorter, escorted) -> None:
    """
    Register escorter as escorting escorted.
    Trust check (escort category) must already be confirmed by caller.
    """
    if not escorter or not escorted:
        return
    escorts = getattr(escorter.ndb, "_escorting", None)
    if escorts is None:
        escorts = set()
        escorter.ndb._escorting = escorts
    escorts.add(escorted)
    escorted.ndb._escorted_by = escorter


def clear_escort(escorter, escorted) -> None:
    """Remove escort link between escorter and escorted."""
    if escorter:
        try:
            escorts = getattr(escorter.ndb, "_escorting", None)
            if escorts:
                escorts.discard(escorted)
        except Exception:
            pass
    if escorted:
        if getattr(escorted.ndb, "_escorted_by", None) is escorter:
            escorted.ndb._escorted_by = None


def clear_all_escort(character) -> None:
    """Clear all escort relationships for character (both as escorter and escorted)."""
    # If character is being escorted, clear that link
    escorter = getattr(character.ndb, "_escorted_by", None)
    if escorter:
        clear_escort(escorter, character)

    # If character is escorting others, clear each
    escorts = set(getattr(character.ndb, "_escorting", None) or set())
    for escorted in escorts:
        clear_escort(character, escorted)
    character.ndb._escorting = set()


# ---------------------------------------------------------------------------
# Departure notification — called from staggered_movement after mover arrives
# ---------------------------------------------------------------------------

def notify_departure(mover, destination, direction_norm: str) -> None:
    """
    Called just after `mover` has moved to `destination` via `direction_norm`.
    Triggers any characters following this mover (follow/shadow).

    Escort handoff (escorted follows after escorter departs) is handled by
    `after_escort_departure`, called separately from staggered_movement.

    This must be called AFTER the mover has been placed in the new room.
    """
    _trigger_followers(mover, destination, direction_norm)


def _trigger_followers(leader, destination, direction_norm: str) -> None:
    """Schedule each follower to walk to leader's new room."""
    from evennia.utils import delay

    followers = get_followers(leader)
    for follower in followers:
        if not getattr(follower, "ndb", None):
            continue
        shadow = bool(getattr(follower.ndb, "_following_shadow", False))

        # Check: leader must still be visible (not hidden) unless follower spotted them
        from world.rpg import stealth
        if stealth.is_hidden(leader):
            spotted = getattr(leader.db, "stealth_spotted_by", None) or []
            try:
                if follower.id not in spotted:
                    follower.msg("|yYou lose track of your target — they vanish from sight.|n")
                    clear_follow(follower)
                    continue
            except Exception:
                clear_follow(follower)
                continue

        follower.msg(f"|xYou follow along {direction_norm}.|n")
        leader_id = _safe_id(leader)
        follower_id = _safe_id(follower)
        dest_id = _safe_id(destination)
        if follower_id and dest_id and leader_id:
            delay(0.5, _follow_step, follower_id, dest_id, direction_norm, leader_id, shadow)


def _follow_step(follower_id: int, dest_id: int, direction_norm: str, leader_id: int, shadow: bool) -> None:
    """
    Delayed callback: attempt to walk follower toward destination.
    Checks that:
    - Follower is still following the same leader
    - Follower is still in a room that has an exit toward destination
      (they might not be — leader may have outrun them already)
    """
    follower = _resolve(follower_id)
    leader = _resolve(leader_id)
    if not follower or not leader:
        return
    # Still following same person?
    if getattr(follower.ndb, "_following", None) is not leader:
        return
    # Don't follow if follower is in combat, grappled, unconscious, etc.
    if _follower_blocked(follower):
        return

    if shadow:
        _sneak_step(follower, direction_norm)
    else:
        _walk_step(follower, direction_norm)


def _follower_blocked(follower) -> bool:
    """True if the follower can't move right now."""
    try:
        from world.combat import is_in_combat
        if is_in_combat(follower):
            return True
    except Exception:
        pass
    if getattr(getattr(follower, "db", None), "grappled_by", None):
        return True
    try:
        from world.death import is_flatlined
        if is_flatlined(follower):
            return True
    except Exception:
        pass
    try:
        from world.medical import is_unconscious
        if is_unconscious(follower):
            return True
    except Exception:
        pass
    return False


def _walk_step(follower, direction_norm: str) -> None:
    """Queue a normal staggered walk for the follower."""
    from world.rpg.staggered_movement import (
        begin_staggered_walk_in_direction,
        append_walk_queue,
        is_staggered_walk_pending,
    )
    if is_staggered_walk_pending(follower):
        append_walk_queue(follower, direction_norm)
    else:
        ok, err = begin_staggered_walk_in_direction(follower, direction_norm)
        if not ok and err:
            follower.msg(err)


def _sneak_step(follower, direction_norm: str) -> None:
    """Queue a stealthy walk step for the follower (shadow mode)."""
    from world.rpg.staggered_movement import (
        find_exit_in_room,
        is_staggered_walk_pending,
        set_stagger_walk_pending,
        NDB_STAGGER_WALK_EXIT_ID,
        WALK_DELAY,
        _staggered_walk_callback,
    )
    from typeclasses.exit_traversal import precheck_exit_traversal
    from evennia.utils import delay
    from world.rpg import stealth

    loc = getattr(follower, "location", None)
    if not loc:
        return
    exit_obj, dest = find_exit_in_room(loc, direction_norm)
    if not exit_obj or not dest:
        follower.msg(f"|xYou can't follow that way ({direction_norm}).|n")
        return
    ok, dest2, err, direction_str = precheck_exit_traversal(exit_obj, follower, dest)
    if not ok:
        if err:
            follower.msg(err)
        return

    if is_staggered_walk_pending(follower):
        follower.msg("|xYou are already moving.|n")
        return

    direction = direction_str or (exit_obj.key or "away").strip()
    from world.rpg.staggered_movement import normalize_move_direction
    new_norm = normalize_move_direction(direction)

    # Show sneak departure message
    was_hidden = stealth.is_hidden(follower)
    if not was_hidden:
        follower.msg(f"|xYou slip {direction}, keeping to the shadows.|n")
    loc_viewers = [c for c in loc.contents_get(content_type="character") if c is not follower]
    from world.rp_features import get_move_display_for_viewer
    for viewer in loc_viewers:
        display = get_move_display_for_viewer(follower, viewer)
        if was_hidden:
            spotted = getattr(follower.db, "stealth_spotted_by", None) or []
            try:
                if viewer.id in spotted:
                    viewer.msg(f"|yYou notice {display} slip away {direction}.|n")
            except Exception:
                pass
        else:
            viewer.msg(f"{display} slips quietly {direction}.")

    follower.ndb._stealth_move_sneak = True
    set_stagger_walk_pending(follower, new_norm, direction)
    if exit_obj.id:
        setattr(follower.ndb, NDB_STAGGER_WALK_EXIT_ID, exit_obj.id)
    delay(WALK_DELAY, _staggered_walk_callback, follower.id, (dest2 or dest).id)


# ---------------------------------------------------------------------------
# Escort: escorted person's move command triggers escorter first
# ---------------------------------------------------------------------------

def handle_escort_move(escorted, direction_norm: str) -> bool:
    """
    Called from Exit.at_traverse (or equivalent) when `escorted` attempts to move.
    If an escorter is registered, they move first and then escorted auto-follows.
    Returns True if the escorted's move was intercepted (they should NOT move now).
    Returns False if there is no active escorter or escorter is blocked.
    """
    escorter = getattr(getattr(escorted, "ndb", None), "_escorted_by", None)
    if not escorter:
        return False
    if not getattr(escorter, "ndb", None):
        escorted.ndb._escorted_by = None
        return False

    # Escorter must be in same room
    if getattr(escorter, "location", None) is not getattr(escorted, "location", None):
        return False

    if _follower_blocked(escorter):
        escorted.msg("|xYour escort can't move right now.|n")
        return True  # Block escorted's move since escort mode is active

    from world.rpg.staggered_movement import (
        begin_staggered_walk_in_direction,
        is_staggered_walk_pending,
    )
    if is_staggered_walk_pending(escorter):
        return True  # Escorter already moving, wait

    escorted.msg(f"|xYour escort moves ahead of you {direction_norm}.|n")
    escorter.msg(f"|xYou lead the way {direction_norm}.|n")

    # Flag so that when escorter's walk completes, escorted auto-follows
    escorter.ndb._escort_pending_direction = direction_norm
    escorter.ndb._escort_pending_escorted_id = _safe_id(escorted)

    ok, err = begin_staggered_walk_in_direction(escorter, direction_norm)
    if not ok:
        escorter.ndb._escort_pending_direction = None
        escorter.ndb._escort_pending_escorted_id = None
        if err:
            escorted.msg(err)
        return False
    return True  # Escorted move is intercepted; they'll follow after escorter departs


def after_escort_departure(escorter, destination, direction_norm: str) -> None:
    """
    Called after escorter completes their staggered walk step.
    Triggers the escorted person to follow.
    """
    from evennia.utils import delay

    escorted_id = getattr(escorter.ndb, "_escort_pending_escorted_id", None)
    pending_dir = getattr(escorter.ndb, "_escort_pending_direction", None)
    escorter.ndb._escort_pending_direction = None
    escorter.ndb._escort_pending_escorted_id = None

    if not escorted_id or not pending_dir:
        return
    delay(0.3, _escort_follow_step, int(escorted_id), _safe_id(destination), pending_dir, _safe_id(escorter))


def _escort_follow_step(escorted_id: int, dest_id: int, direction_norm: str, escorter_id: int) -> None:
    """Delayed: have escorted person walk after escorter."""
    escorted = _resolve(escorted_id)
    escorter = _resolve(escorter_id)
    if not escorted or not escorter:
        return
    if getattr(escorted.ndb, "_escorted_by", None) is not escorter:
        return
    if _follower_blocked(escorted):
        return
    _walk_step(escorted, direction_norm)
