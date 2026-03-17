"""
Roleplay mixin: recog, display names, say/whisper (with voice and cameras), move announcements.
"""
from evennia.utils import logger
from evennia.utils.utils import make_iter


def _feed_room_cameras(location, speaker, message, improvise):
    """
    Feed say line to cameras in the room (or held by anyone here) and, if improvising,
    trigger audience echo. Call from at_say after room say loop.
    """
    say_line = '%s says, "%s"' % (speaker.get_display_name(speaker), message)
    if improvise:
        say_line = "|w%s|n" % say_line
    try:
        from typeclasses.broadcast import feed_cameras_in_location
        feed_cameras_in_location(location, say_line)
    except Exception as err:
        logger.log_trace("roleplay_mixin._feed_room_cameras: %s" % err)
    if improvise:
        try:
            from commands.performance_cmds import _audience_echo_improvise
            _audience_echo_improvise(location)
        except Exception as err:
            logger.log_trace("roleplay_mixin._feed_room_cameras improvise echo: %s" % err)


def _at_say_whisper_overhear(location, speaker, message, receivers):
    """Send garbled whisper overhear to other characters in the room."""
    if not location or not receivers:
        return
    try:
        from evennia.contrib.rpg.rpsystem.rplanguage import obfuscate_whisper
        exclude = make_iter(receivers)
        exclude = list(exclude) + [speaker]
        chars_here = location.contents_get(content_type="character")
        for viewer in chars_here:
            if viewer in exclude or viewer == speaker:
                continue
            garbled = obfuscate_whisper(message, level=0.6)
            obj_name = speaker.get_display_name(viewer)
            line = '%s whispers something to someone... "%s"' % (obj_name, garbled)
            viewer.msg(text=(line, {"type": "whisper"}), from_obj=speaker)
    except Exception as err:
        logger.log_trace("roleplay_mixin._at_say_whisper_overhear: %s" % err)


class RoleplayMixin:
    """Recog, get_display_name, get_search_result, announce_move_*, at_say (say/whisper/voice/cameras)."""

    @property
    def recog(self):
        """Per-viewer recognition: who you've been introduced to (see world.rp_features)."""
        from world.rp_features import RecogHandler
        if not hasattr(self, "_recog_handler"):
            self._recog_handler = RecogHandler(self)
        return self._recog_handler

    def get_display_name(self, looker=None, **kwargs):
        """
        Viewer-aware name: sdesc until introduced, then recog or key.
        When they wear a mask/helmet, others see sdesc only (recog hidden until they remove it).
        """
        from world.rp_features import get_display_name_for_viewer
        return get_display_name_for_viewer(self, looker, **kwargs)

    def get_search_result(self, searchdata, attribute_name=None, typeclass=None, candidates=None, exact=False, use_dbref=None, tags=None, **kwargs):
        """
        Allow search/look by sdesc or recog (e.g. 'look average naked person', 'look Bob').
        When candidates are in the same location, try matching by display name (sdesc/recog) first.
        You cannot find a character by their actual key/name unless you have them recog'd.
        """
        if candidates is not None and searchdata and isinstance(searchdata, str):
            try:
                from evennia.utils.utils import inherits_from
                from world.emote import resolve_sdesc_to_characters
                cand_list = list(candidates)
                char_candidates = [c for c in cand_list if inherits_from(c, "typeclasses.characters.Character")]
                if char_candidates:
                    matches = resolve_sdesc_to_characters(self, char_candidates, searchdata.strip())
                    if matches:
                        return list(matches)
            except Exception as err:
                logger.log_trace("roleplay_mixin.get_search_result resolve_sdesc: %s" % err)
        results = super().get_search_result(
            searchdata,
            attribute_name=attribute_name,
            typeclass=typeclass,
            candidates=candidates,
            exact=exact,
            use_dbref=use_dbref,
            tags=tags,
            **kwargs,
        )
        # Don't allow finding a character by key/alias unless the caller has recog'd them (dbref search still works)
        if candidates is not None and searchdata and isinstance(searchdata, str) and not (searchdata.strip().startswith("#")):
            try:
                result_list = list(results)
                filtered = []
                for obj in result_list:
                    if hasattr(obj, "recog") and getattr(obj, "recog", None) is not None:
                        if self.recog.get(obj):
                            filtered.append(obj)
                    else:
                        filtered.append(obj)
                return filtered
            except Exception as err:
                logger.log_trace("roleplay_mixin.get_search_result filter recog: %s" % err)
        return results

    def announce_move_from(self, destination, msg=None, mapping=None, move_type="move", **kwargs):
        """Announce departure: each viewer sees recog name or sdesc only (no 'sdesc (key)' — respects recog)."""
        if not self.location:
            return
        if move_type not in ("move", "traverse") or not destination:
            super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        location = self.location
        viewers = [c for c in location.contents_get(content_type="character") if c != self]
        if getattr(destination, "db", None) and getattr(destination.db, "pod", None):
            for viewer in viewers:
                display = self.get_display_name(viewer)
                if display:
                    display = display[0].upper() + display[1:]
                else:
                    display = getattr(self, "key", "Someone")
                viewer.msg("%s enters the splinter pod." % display)
            return
        exits = [
            o for o in (getattr(location, "contents", None) or [])
            if getattr(o, "destination", None) is destination
        ]
        if not exits:
            super().announce_move_from(destination, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        direction = exits[0].key.strip()
        for viewer in viewers:
            display = self.get_display_name(viewer)
            if display:
                display = display[0].upper() + display[1:]
            else:
                display = getattr(self, "key", "Someone")
            viewer.msg(f"{display} goes {direction}.")

    def announce_move_to(self, source_location, msg=None, mapping=None, move_type="move", **kwargs):
        """Announce arrival: each viewer sees recog name or sdesc only (no 'sdesc (key)' — respects recog)."""
        if not self.location:
            return
        if move_type not in ("move", "traverse") or not source_location:
            super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        exits = [
            o for o in (getattr(source_location, "contents", None) or [])
            if getattr(o, "destination", None) is self.location
        ]
        if not exits:
            super().announce_move_to(source_location, msg=msg, mapping=mapping, move_type=move_type, **kwargs)
            return
        direction = exits[0].key.strip()
        viewers = [c for c in self.location.contents_get(content_type="character") if c != self]
        for viewer in viewers:
            display = self.get_display_name(viewer)
            if display:
                display = display[0].upper() + display[1:]
            else:
                display = getattr(self, "key", "Someone")
            viewer.msg(f"{display} arrives from the {direction}.")

    def at_say(self, message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs):
        """
        Say (and whisper) hook. For room say, optionally show voice to listeners who pass perception check.
        """
        from world.voice import get_voice_phrase, get_speaking_tag, voice_perception_check

        # Whisper or explicit receivers: use default behavior, then add overhear obfuscation for whisper
        if kwargs.get("whisper", False) or receivers:
            super().at_say(
                message, msg_self=msg_self, msg_location=msg_location,
                receivers=receivers, msg_receivers=msg_receivers, **kwargs
            )
            if kwargs.get("whisper", False) and receivers:
                location = self.location
                if location:
                    _at_say_whisper_overhear(location, self, message, receivers)
            return

        custom_mapping = kwargs.get("mapping", {})
        location = self.location
        msg_type = "say"
        voice_phrase = get_voice_phrase(self)
        improvise = getattr(self.ndb, "performance_improvising", False)

        if msg_self:
            self_mapping = {
                "self": "You",
                "object": self.get_display_name(self),
                "location": location.get_display_name(self) if location else None,
                "receiver": None,
                "all_receivers": None,
                "speech": message,
            }
            self_mapping.update(custom_mapping)
            template = msg_self if isinstance(msg_self, str) else 'You say, "|n{speech}|n"'
            line_self = template.format_map(self_mapping)
            if improvise:
                line_self = "|w%s|n" % line_self
            self.msg(text=(line_self, {"type": msg_type}), from_obj=self)

        if not location:
            return

        # Room say: send to each character in location (except self) with optional voice
        chars_here = location.contents_get(content_type="character")
        for viewer in make_iter(chars_here):
            if viewer == self:
                continue
            obj_name = self.get_display_name(viewer)
            if voice_phrase and voice_perception_check(viewer, self):
                line = '%s says in a %s, "*speaking in a %s* %s"' % (obj_name, voice_phrase, voice_phrase, message)
            else:
                line = '%s says, "%s"' % (obj_name, message)
            if improvise:
                line = "|w%s|n" % line
            viewer.msg(text=(line, {"type": msg_type}), from_obj=self)

        _feed_room_cameras(location, self, message, improvise)
