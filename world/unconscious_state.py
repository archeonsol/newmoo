"""
Global unconsciousness (KO): grapple strikes, overdoses, OR anesthesia, and similar.

Single source of truth: character.db.unconscious and character.db.unconscious_until.
"""
import re
import time

from evennia.utils import delay
from evennia.utils.search import search_object

from world.combat.utils import combat_display_name as _combat_display_name

UNCONSCIOUS_WAKE_MIN = 10
UNCONSCIOUS_WAKE_MAX = 30

# Room @lp while KO / OR sedation (must match medical unconscious assignments in grapple).
UNCONSCIOUS_ROOM_POSE_TEXT = "lying here, unconscious"


def _normalize_room_pose_for_compare(text):
    """Lowercase, strip optional leading 'is ', collapse whitespace, trim trailing punctuation."""
    if not text:
        return ""
    p = str(text).strip().lower()
    if p.startswith("is "):
        p = p[3:].strip()
    p = re.sub(r"\s+", " ", p)
    return p.rstrip(".,;:")


def _room_pose_is_unconscious_placeholder(text):
    """
    True if room_pose matches the KO/OR sedation line (with or without a leading 'is ').
    """
    return _normalize_room_pose_for_compare(text) == _normalize_room_pose_for_compare(
        UNCONSCIOUS_ROOM_POSE_TEXT
    )


def clear_sedation_markers(character):
    """Clear OR sevoflurane markers (sedated_until / sedated_by). Safe anytime."""
    if not character or not getattr(character, "db", None):
        return
    character.db.sedated_until = 0.0
    character.db.sedated_by = None


def _snapshot_room_pose_before_unconscious(character):
    raw = getattr(character.db, "room_pose", None) or "standing here"
    if _room_pose_is_unconscious_placeholder(raw):
        return "standing here"
    return raw


def _restore_prev_room_pose_after_unconscious(character):
    """
    After trauma and/or medical KO ends, restore @lp (room_pose) from the snapshot taken
    when KO started. If there is no snapshot (legacy / manual db edits) but room_pose is
    still the unconscious placeholder, clear it so the room falls back to the default
    look line (same as |w@lp|n with no args).
    """
    if not character or not getattr(character, "db", None):
        return
    try:
        from world.medical import is_unconscious

        if is_unconscious(character):
            return
    except Exception:
        pass

    prev_pose = getattr(character.db, "_unconscious_prev_room_pose", None)
    current = getattr(character.db, "room_pose", None)

    if prev_pose is not None:
        if _room_pose_is_unconscious_placeholder(prev_pose):
            character.db.room_pose = "standing here"
        else:
            character.db.room_pose = prev_pose
        try:
            character.attributes.remove("_unconscious_prev_room_pose")
        except Exception:
            pass
    elif _room_pose_is_unconscious_placeholder(current):
        try:
            del character.db.room_pose
        except Exception:
            character.db.room_pose = None


def get_unconscious_wake_seconds(character):
    end = 0
    if hasattr(character, "get_stat_level"):
        end = character.get_stat_level("endurance") or 0
    ratio = min(1.0, max(0.0, (end or 0) / 300.0))
    return max(
        UNCONSCIOUS_WAKE_MIN,
        min(UNCONSCIOUS_WAKE_MAX, UNCONSCIOUS_WAKE_MAX - ratio * (UNCONSCIOUS_WAKE_MAX - UNCONSCIOUS_WAKE_MIN)),
    )


def _wake_unconscious_callback(character_id):
    try:
        result = search_object("#%s" % character_id)
        if not result:
            return
        character = result[0]
    except Exception:
        return
    if not getattr(character.db, "unconscious", False):
        # Another path already woke us (force-wake, reconcile, duplicate timer). That path
        # should have restored @lp, but stale timers used to return here without any
        # restore — clear the KO line if it is still stuck.
        _restore_prev_room_pose_after_unconscious(character)
        return
    wake_at = float(getattr(character.db, "unconscious_until", 0.0) or 0.0)
    now = time.time()
    if wake_at > now:
        delay(max(1.0, wake_at - now), _wake_unconscious_callback, character.id)
        return
    character.db.unconscious = False
    character.db.unconscious_until = 0.0
    clear_sedation_markers(character)
    _restore_prev_room_pose_after_unconscious(character)
    try:
        character.cmdset.remove("UnconsciousCmdSet")
    except Exception:
        pass
    character.msg("|gYou groggily come to.|n")
    if character.location and hasattr(character.location, "contents_get"):
        for v in character.location.contents_get(content_type="character"):
            if v == character:
                continue
            v.msg("%s groggily comes to." % _combat_display_name(character, v))


def set_unconscious_for_seconds(character, seconds):
    if not character or not getattr(character, "db", None):
        return
    now = time.time()
    secs = max(1.0, float(seconds or 0.0))
    character.db.unconscious = True
    until = now + secs
    old_until = float(getattr(character.db, "unconscious_until", 0.0) or 0.0)
    character.db.unconscious_until = max(old_until, until)
    if not hasattr(character.db, "_unconscious_prev_room_pose"):
        character.db._unconscious_prev_room_pose = _snapshot_room_pose_before_unconscious(character)
    character.db.room_pose = UNCONSCIOUS_ROOM_POSE_TEXT
    try:
        character.cmdset.add("commands.default_cmdsets.UnconsciousCmdSet")
    except Exception:
        pass
    delay(secs, _wake_unconscious_callback, character.id)


def set_unconscious(character):
    secs = get_unconscious_wake_seconds(character)
    set_unconscious_for_seconds(character, secs)


def force_wake_unconscious(character, silent=False):
    if not character or not getattr(character, "db", None):
        return
    was_uncon = bool(getattr(character.db, "unconscious", False))
    character.db.unconscious = False
    character.db.unconscious_until = 0.0
    clear_sedation_markers(character)
    _restore_prev_room_pose_after_unconscious(character)
    try:
        character.cmdset.remove("UnconsciousCmdSet")
    except Exception:
        pass
    if (not silent) and was_uncon:
        character.msg("|gYou groggily come to.|n")
        if character.location and hasattr(character.location, "contents_get"):
            for v in character.location.contents_get(content_type="character"):
                if v == character:
                    continue
                v.msg("%s groggily comes to." % _combat_display_name(character, v))
