"""
Alchemy and drug crafting: registries, stations, and consumption effects.

Alchemy is chemistry under another name — specimens, stations, staged brews.
"""

from world.alchemy.drugs_registry import DRUGS
from world.alchemy.ingredients import CHEMICALS, SPECIMENS

# Category pairs -> probability of OD check when mixing (see overdose.check_overdose)
DANGEROUS_COMBINATIONS = {
    frozenset({"opioid", "depressant"}): 0.5,
    frozenset({"combat_stim", "stimulant"}): 0.3,
    frozenset({"opioid", "combat_stim"}): 0.4,
    frozenset({"exotic", "psychedelic"}): 0.6,
}

WITHDRAWAL_ONSET_HOURS = {
    0: None,
    1: 24,
    2: 12,
    3: 6,
    4: 3,
}

ADDICTION_RECOVERY_DAYS = 7

__all__ = [
    "DRUGS",
    "SPECIMENS",
    "CHEMICALS",
    "DANGEROUS_COMBINATIONS",
    "WITHDRAWAL_ONSET_HOURS",
    "ADDICTION_RECOVERY_DAYS",
]
