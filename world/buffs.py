"""
Game-specific buffs for stats/skills and status effects.

We build on Evennia's generic buff system in
`evennia.contrib.rpg.buffs.buff` and keep all stat/skill *storage* and
XP caps exactly as they are now. Buffs only ever modify the effective
values returned by helpers like `get_display_stat` / `get_skill_level`.
"""

import sys

from evennia.contrib.rpg.buffs.buff import BaseBuff, Mod

_THIS_MODULE = sys.modules[__name__]


class GameBuffBase(BaseBuff):
    """
    Evennia merges the persisted buff cache into the instance with
    ``self.__dict__.update(cache)``. Stale saves sometimes contained
    ``mods: []`` or ``stat_mods: {}`` / ``skill_mods: {}``, which then
    shadowed the real lists/dicts defined on the buff *class*.

    Those keys are not meaningful runtime state here (mods live on the
    class); empty containers only break lookups. Strip them after load so
    class definitions win again.

    Mechanical stat/skill changes must use ``Mod`` objects on ``mods``.
    ``BuffHandler.check()`` resolves modifiers via ``traits``, which only
    includes buffs with a non-empty ``mods`` list, then ``get_by_stat()`` matches
    ``Mod.stat`` to the string passed to ``check()`` (e.g. ``strength_display``,
    ``skill:unarmed``).
    """

    def at_init(self, *args, **kwargs):
        super().at_init(*args, **kwargs)
        # Instance dict (merged from cache) and the live buffcache row must both
        # drop empty placeholders or the next save re-persists the bad keys.
        # Only strip when the class defines a non-empty default so we do not
        # strip valid empty class-level containers.
        for name, empty in (("mods", []), ("stat_mods", {}), ("skill_mods", {})):
            inst_val = self.__dict__.get(name)
            class_val = getattr(type(self), name, empty)
            if inst_val == empty and class_val != empty:
                self.__dict__.pop(name, None)
        try:
            row = self.handler.buffcache.get(self.buffkey)
        except Exception:
            row = None
        if isinstance(row, dict):
            dirty = False
            for name, empty in (("mods", []), ("stat_mods", {}), ("skill_mods", {})):
                class_val = getattr(type(self), name, empty)
                if row.get(name) == empty and class_val != empty:
                    row.pop(name, None)
                    dirty = True
            # row is a plain dict; mutating it does not trigger _BuffCacheDict._persist.
            # Write it back explicitly so the clean version reaches the database.
            if dirty:
                try:
                    self.handler.buffcache[self.buffkey] = row
                except Exception:
                    pass


class PerfumeBuff(GameBuffBase):
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


class BadSmellBuff(GameBuffBase):
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


def build_drug_buff_class(drug_key, suffix, display_name, duration_seconds, stat_buffs, stat_debuffs):
    """
    Factory for temporary drug effect buffs (stat_display modifiers).
    suffix: "" for main effect, "comedown" / "withdrawal" / "overdose" for other keys.
    """
    mods = []
    for k, v in (stat_buffs or {}).items():
        mods.append(Mod(stat="%s_display" % k, modifier="add", value=int(v)))
    for k, v in (stat_debuffs or {}).items():
        mods.append(Mod(stat="%s_display" % k, modifier="add", value=-int(abs(v))))
    key_part = "%s%s" % (drug_key, ("_%s" % suffix) if suffix else "")
    cls_name = "DrugBuff_%s" % key_part.replace("/", "_")
    cls = type(
        cls_name,
        (GameBuffBase,),
        {
            "key": "drug_%s" % key_part,
            "name": display_name or drug_key,
            "flavor": "",
            "duration": int(duration_seconds),
            "maxstacks": 1,
            "stacks": 1,
            "mods": mods,
        },
    )
    # BuffHandler persists buffcache; pickle must resolve the class on this module.
    # KNOWN LIMITATION: if apply_drug calls this factory with potency-scaled values at
    # runtime, the module-level name is overwritten with the scaled class. After a server
    # restart, _register_all_drug_buff_classes() reinstalls the baseline class under the
    # same name before db.buffs is unpickled. Any character who had an active drug buff
    # during the restart will silently revert to the unscaled effect.
    # Fixing this properly requires storing potency in the buff row rather than baking
    # it into the class. Until then, the regression is bounded to rare restart windows
    # and the effect expires naturally within the buff's duration anyway.
    setattr(_THIS_MODULE, cls_name, cls)
    return cls


def _register_all_drug_buff_classes():
    """
    Create every ``DrugBuff_*`` class on this module at import time.

    Buff rows persist ``ref`` as a class object; pickle stores it as
    ``world.buffs.DrugBuff_<name>``. Those types were previously created only
    when a dose/comedown/withdrawal first ran. After a server restart the
    class attribute did not exist yet, so unpickling ``db.buffs`` could fail
    and drop the whole cache (including cyberware buffs).

    Canonical stats come from ``DRUGS``; at runtime ``apply_drug`` may replace
    the same class name with potency-scaled types — same pickle name, so loads
    still resolve.
    """
    try:
        from world.alchemy import DRUGS
    except ImportError:
        return

    for drug_key, drug in DRUGS.items():
        eff = drug.get("effects") or {}
        dur = int(eff.get("duration_seconds", 60) or 60)
        stat_buffs = eff.get("stat_buffs") or {}
        stat_debuffs = eff.get("stat_debuffs") or {}
        name = drug.get("name", drug_key)
        build_drug_buff_class(drug_key, "", name, dur, stat_buffs, stat_debuffs)

        cd = drug.get("comedown") or {}
        cd_dur = int(cd.get("duration_seconds", 0) or 0)
        cd_debuffs = cd.get("stat_debuffs") or {}
        if cd or cd_dur or cd_debuffs:
            # If cd_dur is unspecified (0) but debuffs exist, default to 1 hour so the
            # comedown is actually felt rather than expiring in 1 second.
            effective_cd_dur = cd_dur if cd_dur else (3600 if cd_debuffs else 1)
            build_drug_buff_class(
                drug_key,
                "comedown",
                "%s comedown" % name,
                max(1, effective_cd_dur),
                {},
                cd_debuffs,
            )

        add = drug.get("addiction") or {}
        wdeb = add.get("withdrawal_debuffs") or {}
        if wdeb:
            build_drug_buff_class(
                drug_key,
                "withdrawal",
                "%s withdrawal" % name,
                48 * 3600,
                {},
                wdeb,
            )


def build_overdose_severe_buff(duration_seconds=900):
    """All stats -20 for severe overdose aftermath."""
    mods = []
    for k in ("strength", "perception", "endurance", "charisma", "intelligence", "agility"):
        mods.append(Mod(stat="%s_display" % k, modifier="add", value=-20))
    cls_name = "OverdoseSevereBuff"
    cls = type(
        cls_name,
        (GameBuffBase,),
        {
            "key": "overdose_severe",
            "name": "Toxic shock",
            "flavor": "Your chemistry has turned on you.",
            "duration": int(duration_seconds),
            "maxstacks": 1,
            "stacks": 1,
            "mods": mods,
        },
    )
    setattr(_THIS_MODULE, cls_name, cls)
    return cls


_register_all_drug_buff_classes()
# Severe OD buff is added dynamically elsewhere; ensure the class exists for unpickle.
build_overdose_severe_buff(900)
