"""
Corpse typeclass. A character who has permanently died is converted to this.
Keeps the dead character's inventory, body_descriptions, and worn clothing; look shows body + worn + contents.
"""
from evennia.utils import logger
from typeclasses.objects import Object


class Corpse(Object):
    """
    Permanently dead body. Created by converting a flatlined character via world.death.make_permanent_death.
    db.original_name = name of the deceased. Same object keeps db.body_descriptions, db.worn, and contents (inventory).

    Note: swap_typeclass (used by make_permanent_death) does NOT call at_object_creation on the new
    typeclass — it calls at_init instead. original_name is therefore set explicitly in
    death._safe_swap_corpse_typeclass. at_object_creation here only fires for directly-created Corpse
    objects (e.g. builder @create) and acts as a safety net.
    """

    # Class-level constants to avoid redundant allocations
    _PRONOUN_TO_KEY = {"male": "male corpse", "female": "female corpse", "neutral": "neuter corpse"}
    # "a person" reads more naturally than "a neuter" for neutral-pronoun characters.
    _PRONOUN_TO_BODY = {"male": "a man", "female": "a woman", "neutral": "a person"}

    def get_display_name(self, looker, **kwargs):
        """Show as 'male corpse', 'female corpse', or 'neuter corpse' in room and look lists.
        Handles the 'article' kwarg that Evennia's look system may pass (e.g. 'a male corpse')."""
        pronoun = getattr(self.db, "corpse_pronoun", None)
        name = self._PRONOUN_TO_KEY.get(pronoun, "neuter corpse")
        if kwargs.get("article"):
            name = "a " + name
        return name

    def at_object_creation(self):
        if not getattr(self.db, "original_name", None):
            self.db.original_name = self.key

    def get_display_desc(self, looker, **kwargs):
        pronoun = getattr(self.db, "corpse_pronoun", None)
        body_word = self._PRONOUN_TO_BODY.get(pronoun, "a person")
        intro = f"The body of {body_word}. Cold. Still. Nothing left of who they were."
        try:
            from world.appearance import get_effective_body_descriptions, format_body_appearance
            parts = get_effective_body_descriptions(self)
            merged = format_body_appearance(parts, character=self)
            if merged:
                intro = intro + "\n\n" + merged
        except Exception as e:
            logger.log_trace(f"Corpse.get_display_desc error: {e}")
        extra_lines = []
        if getattr(self.db, "skinned", False):
            extra_lines.append("The body has been expertly skinned, raw musculature and slick fat exposed where the flesh was peeled away.")
        if getattr(self.db, "butchered", False):
            extra_lines.append("The torso is split wide and hollowed out, most of the useful organs carved free and taken.")
        if extra_lines:
            intro = intro + "\n\n" + " ".join(extra_lines)
        return intro

    def get_display_things(self, looker, **kwargs):
        """Show worn items on look but not carried (pocket) inventory — use 'loot corpse' for that."""
        try:
            from world.clothing import get_worn_items
            from evennia.utils.utils import list_to_string
            worn = get_worn_items(self)
            if not worn:
                return ""
            names = [obj.get_display_name(looker) for obj in worn]
            return "|wWearing:|n " + list_to_string(names, endsep=" and ")
        except Exception as e:
            logger.log_trace(f"Corpse.get_display_things error: {e}")
            return ""
