"""
Exits

Exits are connectors between Rooms. An exit always has a destination property
set and has a single command defined on itself with the same name as its key,
for allowing Characters to traverse the exit to its destination.

Movement is staggered for RP: "You begin walking north" then 3–4 seconds later the move completes.
"""

from evennia.utils import delay
from evennia.objects.objects import DefaultExit

from .objects import ObjectParent

try:
    from world.staggered_movement import WALK_DELAY, _staggered_walk_callback
except ImportError:
    WALK_DELAY = 3.5
    _staggered_walk_callback = None


class Exit(ObjectParent, DefaultExit):
    """
    Exits are connectors between rooms. Movement is staggered: you see "You begin walking X"
    then after a short delay you arrive (for RP).
    """

    def at_traverse(self, traversing_object, destination):
        if not destination:
            super().at_traverse(traversing_object, destination)
            return
        # Voided characters cannot leave the void room
        if getattr(traversing_object.db, "voided", False):
            try:
                from evennia.server.models import ServerConfig
                void_id = ServerConfig.objects.conf("VOID_ROOM_ID", default=None)
                if void_id is not None and getattr(destination, "id", None) != int(void_id):
                    traversing_object.msg("|rYou cannot leave the void.|n")
                    return
            except Exception:
                pass
        direction = (self.key or "away").strip()
        traversing_object.msg(f"You begin walking {direction}.")
        loc = traversing_object.location
        if loc:
            loc.msg_contents(
                f"{traversing_object.get_display_name(traversing_object)} begins walking {direction}.",
                exclude=traversing_object,
            )
        if _staggered_walk_callback:
            delay(WALK_DELAY, _staggered_walk_callback, traversing_object.id, destination.id)
        else:
            traversing_object.move_to(destination)
            victim = getattr(getattr(traversing_object, "db", None), "grappling", None)
            if victim and hasattr(victim, "move_to"):
                victim.move_to(destination)
                destination.msg_contents(
                    "%s is dragged in by %s." % (victim.name, traversing_object.name),
                    exclude=(traversing_object, victim),
                )
        return
