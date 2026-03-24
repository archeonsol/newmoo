"""
Bulkhead / floodgate room — sealable passthrough between district and freight station.
"""

from typeclasses.rooms import CityRoom


class BulkheadRoom(CityRoom):
    """
    A sealable passthrough room between a district and a freight station.

    When unsealed: passage through (subject to normal exits).
    When sealed: configured exit(s) get `db.bulkhead_locked` (see `world.maps.bulkheads`).

    Builders tag: @tag here = bulkhead (category room_type is set in at_object_creation).
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.tags.add("bulkhead", category="room_type")
        self.db.bulkhead_id = ""
        self.db.sealed = False
        self.db.seal_reason = ""
        self.db.sealed_by = ""
        self.db.sealed_at = 0.0
        self.db.district_side_exit = None
        self.db.station_side_exit = None
        self.db.connects_districts = ("", "")
        self.db.seal_direction = "outbound"
        self.db.seal_warning_sent = False
        self.db.seal_log = []

        # Default look-details for the bulkhead room
        self.add_detail(
            "blast door",
            "A reinforced steel blast door, floor to ceiling. Three locking bolts run "
            "through the frame. When sealed, the door is rated to withstand explosive "
            "decompression. Scorch marks and dents suggest it has been tested before.",
        )
        self.add_detail(
            "hydraulic rams",
            "Heavy hydraulic rams are mounted on either side of the blast door frame. "
            "When active, they drive the door bolts home with several tonnes of force. "
            "The rams hiss faintly even at rest — always under pressure.",
        )
        self.add_detail(
            "warning lights",
            "Red warning lights are recessed into the frame at intervals. They pulse "
            "slowly when the door is unsealed, and strobe rapidly during a seal sequence. "
            "The bulbs are behind thick glass — they have never needed replacing.",
        )

    def return_appearance(self, looker, **kwargs):
        name = self.db.bulkhead_id or "bulkhead"
        sealed = bool(self.db.sealed)
        divider = f"|x{'=' * 52}|n"

        if sealed:
            reason = self.db.seal_reason or "No reason given."
            sealed_by = self.db.sealed_by or "Unknown"
            status = (
                f"{divider}\n"
                f"  |w{name.upper().replace('_', ' ')}|n  |R[SEALED]|n\n"
                f"{divider}\n"
                "  The blast door is down. Floor to ceiling, wall to wall. Solid\n"
                "  steel, three bolts deep. The hydraulic rams are locked in the\n"
                "  closed position. Red warning lights pulse along the frame.\n\n"
                f"  Sealed by {sealed_by}. Reason: {reason}\n"
                f"{divider}"
            )
        else:
            status = (
                f"{divider}\n"
                f"  |w{name.upper().replace('_', ' ')}|n\n"
                f"{divider}\n"
                "  The blast door is retracted into the ceiling. The passage is\n"
                "  clear. The hydraulic rams idle in the open position. Green\n"
                "  status lights run along the frame.\n"
                f"{divider}"
            )

        # Build the room display manually so the bulkhead status sits between
        # the room description and the characters/objects/exits sections.
        header = self.get_display_header(looker, **kwargs)
        desc = self.get_display_desc(looker, **kwargs)
        things = self.get_display_things(looker, **kwargs)
        furniture = self.get_display_furniture(looker, **kwargs)
        characters = self.get_display_characters(looker, **kwargs)
        footer = self.get_display_footer(looker, **kwargs)
        exits = self.get_display_exits(looker, **kwargs)
        ambient = self.get_display_ambient(looker, **kwargs)

        head = "\n".join([p for p in (header, desc) if p])
        parts = [head, status]
        if ambient:
            parts.append(ambient)
        if things:
            parts.append(things)
        if furniture:
            parts.append(furniture)
        tail = "\n".join([p for p in (characters, exits, footer) if p])
        if tail:
            parts.append(tail)

        appearance = "\n\n".join([p for p in parts if p])
        return self.format_appearance(appearance, looker, **kwargs)
