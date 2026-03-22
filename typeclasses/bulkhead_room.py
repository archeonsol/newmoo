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

    def return_appearance(self, looker, **kwargs):
        name = self.db.bulkhead_id or "bulkhead"
        sealed = bool(self.db.sealed)

        header = (
            f"|x{'=' * 52}|n\n"
            f"  |w{name.upper().replace('_', ' ')}|n\n"
            f"|x{'=' * 52}|n\n\n"
            "  A reinforced corridor cut through structural steel. The walls are\n"
            "  two feet thick on either side — you can see the cross-section where\n"
            "  the bulkhead frame meets the rock. Hydraulic rams line the ceiling,\n"
            "  connected to a blast door that can seal the passage in seconds.\n\n"
        )

        if sealed:
            reason = self.db.seal_reason or "No reason given."
            sealed_by = self.db.sealed_by or "Unknown"
            text = header + (
                "  |R[SEALED]|n\n\n"
                "  The blast door is down. Floor to ceiling, wall to wall. Solid\n"
                "  steel, three bolts deep. The hydraulic rams are locked in the\n"
                "  closed position. Red warning lights pulse along the frame.\n\n"
                f"  |wSeal authority:|n {sealed_by}\n"
                f"  |wReason:|n {reason}\n\n"
                "  |xYou can go back the way you came. You are not going through this.|n\n"
            )
        else:
            text = header + (
                "  The blast door is retracted into the ceiling. The passage is\n"
                "  clear. The hydraulic rams idle in the open position. Green\n"
                "  status lights run along the frame.\n\n"
                "  |xThe way through is open.|n\n"
            )

        text += f"|x{'=' * 52}|n"
        return text
