"""
Game-specific buffs for stats/skills and status effects.

We build on Evennia's generic buff system in
`evennia.contrib.rpg.buffs.buff` and keep all stat/skill *storage* and
XP caps exactly as they are now. Buffs only ever modify the effective
values returned by helpers like `get_display_stat` / `get_skill_level`.
"""

from evennia.contrib.rpg.buffs.buff import BaseBuff, Mod


class PerfumeBuff(BaseBuff):
    """
    Temporary Charisma bonus from perfume or cologne.

    Mechanics:
      - Adds to effective Charisma display (0–150 scale) only.
      - Does not change stored stats or XP.
    """

    key = "perfume"
    name = "Perfume"
    flavor = "You are wearing an intoxicating perfume."
    duration = 3 * 60 * 60  # ~3 hours
    maxstacks = 1
    stacks = 1
    mods = [
        # Charisma display level (0–150). See RPGCharacterMixin.get_display_stat.
        Mod(stat="charisma_display", modifier="add", value=5),
    ]


class BadSmellBuff(BaseBuff):
    """
    Temporary Charisma penalty from bad-smell tiles or similar effects.

    Mechanics:
      - Subtracts from effective Charisma display (0–150 scale) only.
      - Does not change stored stats or XP.
    """

    key = "bad_smell"
    name = "Reeking Stench"
    flavor = "You reek of gutter runoff and stale garbage."
    duration = 3 * 60 * 60  # default; room scripts may override duration per-application
    maxstacks = 1
    stacks = 1
    mods = [
        Mod(stat="charisma_display", modifier="add", value=-5),
    ]


