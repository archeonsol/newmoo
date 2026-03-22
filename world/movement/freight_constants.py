"""Shared constants for freight lifts (avoid import cycles between freight.py and freight_lift)."""

DEFAULT_DOCK_DURATION = 45
DEFAULT_TRANSIT_DURATION = 150

PHASE_ORDER = ["docked_upper", "transit_down", "docked_lower", "transit_up"]

DOOR_WARNINGS = {
    30: "|y[FREIGHT] Doors closing in 30 seconds.|n",
    15: "|y[FREIGHT] Doors closing in 15 seconds. Board now or wait for the return.|n",
    5: "|R[FREIGHT] Doors closing in 5 seconds.|n",
}

TRANSIT_MESSAGES_DOWN = [
    "|xThe lift shudders and begins to descend. The cables groan.|n",
    "|xThe walls vibrate. You can feel the depth increasing — pressure in your ears.|n",
    "|xThe lift sways. Something mechanical adjusts in the shaft above you.|n",
    "|xDarkness through the grate. The shaft is featureless. Only the hum of the motor.|n",
    "|xA distant clang from somewhere in the shaft. Echo, then nothing.|n",
    "|xThe air changes. Cooler. Denser. You are going deeper.|n",
]

TRANSIT_MESSAGES_UP = [
    "|xThe lift lurches upward. The motor engages with a grinding whine.|n",
    "|xAscending. The shaft above is a dim column of grey light.|n",
    "|xThe cables sing. The lift sways. Up, always up.|n",
    "|xThe air thins slightly. You are rising toward the surface levels.|n",
    "|xA rumble. The lift adjusts its speed. The shaft walls blur.|n",
    "|xThe temperature shifts. Warmer. You are approaching the upper station.|n",
]

ARRIVAL_MESSAGES = {
    "docked_upper": "|g[FREIGHT] Arrived at upper station. Doors opening.|n",
    "docked_lower": "|g[FREIGHT] Arrived at lower station. Doors opening.|n",
}

DEPARTURE_MESSAGES = {
    "transit_down": "|y[FREIGHT] Doors sealed. Descending.|n",
    "transit_up": "|y[FREIGHT] Doors sealed. Ascending.|n",
}
