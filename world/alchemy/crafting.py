"""
Refining timers, yield, quality impacts, and tend resolution.
"""
from world.rpg.skills import SKILL_STATS
from world.alchemy.ingredients import SPECIMENS


def calculate_refine_duration(character, specimen_key):
    """Seconds until refine is ready to claim; skill reduces wait."""
    spec = SPECIMENS.get(specimen_key)
    if not spec:
        return 120
    base_time = 120 + (spec["refine_difficulty"] * 30)
    skill = character.get_skill_level("alchemy") if hasattr(character, "get_skill_level") else 0
    reduction = (skill or 0) * 0.8
    return max(60, int(base_time - reduction))


def calculate_refine_yield(character, specimen_key):
    """Multiplier 0-1 for how much chemical amount the refine produces."""
    spec = SPECIMENS.get(specimen_key)
    if not spec:
        return 0.5
    base = spec["refine_yield_base"]
    skill = character.get_skill_level("alchemy") if hasattr(character, "get_skill_level") else 0
    bonus = (skill or 0) * 0.003
    return min(1.0, base + bonus)


def final_dose_yield(base_yield, quality):
    """
    Doses from batch. Ruined at quality <= 0.
    Any non-ruined batch produces at least one dose; poor quality yields fewer doses.
    """
    if quality <= 0:
        return 0
    y = base_yield * (quality / 100.0)
    doses = int(round(y))
    return max(1, doses)


def resolve_tend_skill(character, stage):
    """
    Apply stage skill check to running quality. Returns (delta_quality, tier_name).
    """
    stats = SKILL_STATS.get("alchemy", ["intelligence", "perception"])
    diff = int(stage.get("skill_check_difficulty", 10))
    tier, _final = character.roll_check(stats, "alchemy", difficulty=diff)
    if tier == "Critical Success":
        delta = int(stage.get("quality_impact_crit", 0))
    elif tier == "Failure":
        delta = int(stage.get("quality_impact_fail", -10))
    else:
        delta = int(stage.get("quality_impact_success", 0))
    return delta, tier


def potency_multiplier(quality, drug_def=None):
    """
    Scale drug effects: base 0.5 at quality 0 to 1.5 at 100.
    """
    return 0.5 + (quality / 100.0)


def tolerance_multiplier(addiction_level, tolerance_rate):
    """Reduce effectiveness by tolerance_rate per addiction level."""
    return max(0.1, 1.0 - (addiction_level * tolerance_rate))
