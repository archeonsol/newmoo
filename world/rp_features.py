"""
RP features adapted from Evennia contrib rpsystem: recog (sdesc until introduced),
and helpers for display names. When a character wears a mask or helmet, recog is
hidden and others see only their sdesc until they remove it.
"""

# Attribute keys
RECOG_REF2RECOG = "_recog_ref2recog"
RECOG_OBJ2RECOG = "_recog_obj2recog"
# Temporary recog while the target is masked/helmeted (overlays normal recog for as long as
# their face is hidden, without overwriting the underlying "true" recog).
HELMET_RECOG_REF2RECOG = "_helmet_recog_ref2recog"


class RecogHandler:
    """
    Per-character handler: who this character "recognizes" (has been introduced to).
    Maps other character id -> personal nickname string. When set, that string is
    shown instead of sdesc for get_display_name(looker=this_character).
    """

    def __init__(self, character):
        self.obj = character
        self._cache = {}
        self._load()

    def _load(self):
        self._cache = dict(self.obj.attributes.get(RECOG_REF2RECOG, default={}) or {})
        # Build _obj2recog from ref2recog by resolving #id to object (persistent storage uses refs only)
        self._obj2recog = {}
        try:
            from evennia.utils.utils import dbref_to_obj
            from evennia.objects.models import ObjectDB
            for ref_key, recog_str in self._cache.items():
                if not ref_key.startswith("#"):
                    continue
                obj = dbref_to_obj(ref_key, ObjectDB, raise_errors=False)
                if obj:
                    self._obj2recog[obj] = recog_str
        except Exception:
            pass

    def get(self, other_char):
        """Return this character's recog string for other_char, or None."""
        if other_char is None or other_char == self.obj:
            return None
        oid = getattr(other_char, "id", None)
        if oid is None:
            return None
        key = "#%s" % oid
        return self._cache.get(key)

    def add(self, other_char, recog_string, max_length=60):
        """Set this character's recog for other_char. Returns the string stored."""
        if other_char is None or other_char == self.obj:
            return recog_string
        recog_string = (recog_string or "").strip()
        if not recog_string:
            return ""
        if len(recog_string) > max_length:
            recog_string = recog_string[:max_length]
        key = "#%s" % other_char.id
        self._cache[key] = recog_string
        ref2 = self.obj.attributes.get(RECOG_REF2RECOG, default={}) or {}
        ref2[key] = recog_string
        self.obj.attributes.add(RECOG_REF2RECOG, ref2)
        self._obj2recog[other_char] = recog_string
        return recog_string

    def remove(self, other_char):
        """Clear recog for other_char."""
        if other_char is None:
            return
        key = "#%s" % getattr(other_char, "id", None)
        if key not in self._cache:
            return
        del self._cache[key]
        ref2 = self.obj.attributes.get(RECOG_REF2RECOG, default={}) or {}
        ref2.pop(key, None)
        self.obj.attributes.add(RECOG_REF2RECOG, ref2)
        self._obj2recog.pop(other_char, None)

    def all(self):
        """Return dict {recog_string: other_char} for listing."""
        return {v: k for k, v in self._obj2recog.items()}


def get_character_sdesc_for_viewer(character, viewer):
    """
    Return the sdesc string for character as seen by viewer.
    Used for display and for matching in emotes. Does not apply recog; that
    is applied in get_display_name.
    """
    if character is None:
        return ""
    try:
        from world.rpg.sdesc import get_short_desc
        return get_short_desc(character, viewer) or (getattr(character, "key", None) or "")
    except Exception:
        return getattr(character, "key", None) or ""


def get_helmet_recog_for_viewer(viewer, character):
    """
    Return temporary recog string viewer uses for character while they are masked/helmeted,
    or None if none is set. Stored per-viewer so it never overwrites the underlying recog.
    """
    if viewer is None or character is None or viewer == character:
        return None
    try:
        ref2 = viewer.attributes.get(HELMET_RECOG_REF2RECOG, default={}) or {}
        key = "#%s" % getattr(character, "id", None)
        if not key or key not in ref2:
            return None
        val = (ref2.get(key) or "").strip()
        return val or None
    except Exception:
        return None


def set_helmet_recog_for_viewer(viewer, character, recog_string, max_length=60):
    """
    Set or update the temporary recog string viewer uses for character while they are
    masked/helmeted. Returns the stored string (or "" if cleared/empty).
    """
    if viewer is None or character is None or viewer == character:
        return recog_string
    recog_string = (recog_string or "").strip()
    if not recog_string:
        return ""
    if len(recog_string) > max_length:
        recog_string = recog_string[:max_length]
    key = "#%s" % getattr(character, "id", None)
    if not key:
        return recog_string
    ref2 = viewer.attributes.get(HELMET_RECOG_REF2RECOG, default={}) or {}
    ref2[key] = recog_string
    viewer.attributes.add(HELMET_RECOG_REF2RECOG, ref2)
    return recog_string


def clear_helmet_recog_for_viewer(viewer, character):
    """Clear any temporary helmet/mask recog viewer has for character."""
    if viewer is None or character is None:
        return
    key = "#%s" % getattr(character, "id", None)
    if not key:
        return
    ref2 = viewer.attributes.get(HELMET_RECOG_REF2RECOG, default={}) or {}
    if key not in ref2:
        return
    ref2.pop(key, None)
    viewer.attributes.add(HELMET_RECOG_REF2RECOG, ref2)


def get_display_name_for_viewer(character, viewer, **kwargs):
    """
    Single place for viewer-aware name: sdesc until introduced, else recog or key.
    When character wears a mask or helmet, recog is hidden and viewers see sdesc only.
    """
    if character is None:
        return ""
    if viewer == character:
        return getattr(character, "key", None) or "Someone"
    # Face hidden (mask/helmet): prefer temporary helmet-recog overlay if set; otherwise show sdesc.
    try:
        from world.rpg.sdesc import character_has_mask_or_helmet
        if character_has_mask_or_helmet(character):
            temp = get_helmet_recog_for_viewer(viewer, character)
            if temp:
                return temp
            return get_character_sdesc_for_viewer(character, viewer)
    except Exception:
        pass
    # Check viewer's normal recog for this character
    if hasattr(viewer, "recog") and callable(getattr(viewer.recog, "get", None)):
        recog = viewer.recog.get(character)
        if recog:
            return recog
    return get_character_sdesc_for_viewer(character, viewer)


def get_move_display_for_viewer(character, viewer):
    """
    Movement-line display: always show sdesc; if viewer has recog for this character
    (and they are not masked/helmeted), append recog in parentheses.

    Examples:
      - No recog: "A short ugly baka wearing a mustard banana suit who smells intoxicating"
      - With recog: "A short ugly baka wearing a mustard banana suit who smells intoxicating (Bobby)"
    """
    if character is None:
        return ""
    # Base sdesc as seen by viewer
    sdesc = get_character_sdesc_for_viewer(character, viewer)
    sdesc = (sdesc or "").strip() or getattr(character, "key", "Someone")
    # Capitalize first character ("a short..." -> "A short...")
    if sdesc:
        sdesc = sdesc[0].upper() + sdesc[1:]
    # Append movement-only smell suffix if any active effect is present.
    try:
        from world.smell import get_move_sdesc_suffix

        move_suffix = get_move_sdesc_suffix(character)
    except Exception:
        move_suffix = ""
    if move_suffix:
        sdesc = f"{sdesc} {move_suffix}"
    # Don't reveal recog when face is hidden by mask/helmet.
    try:
        from world.rpg.sdesc import character_has_mask_or_helmet
        if character_has_mask_or_helmet(character):
            return sdesc
    except Exception:
        pass
    # Append recog in parentheses if viewer has one.
    recog = None
    if hasattr(viewer, "recog") and callable(getattr(viewer.recog, "get", None)):
        recog = (viewer.recog.get(character) or "").strip()
    if recog:
        return f"{sdesc} ({recog})"
    return sdesc
