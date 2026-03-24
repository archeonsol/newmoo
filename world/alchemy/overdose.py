"""
Overdose detection and severe/fatal outcomes.
"""
import random
import time

from evennia.utils import logger

from world.alchemy import DRUGS, DANGEROUS_COMBINATIONS


def check_overdose(character, drug_key, lowered_threshold=0, suspicious_product=False):
    """
    Returns None (safe), "severe", or "fatal".
    lowered_threshold: subtract from effective threshold (chasing the high).
    """
    drug = DRUGS.get(drug_key)
    if not drug:
        return None
    active = getattr(character.db, "active_drugs", None) or {}
    threshold = int(drug.get("overdose_threshold", 99)) - int(lowered_threshold)
    threshold = max(1, threshold)

    if suspicious_product and random.random() < 0.3:
        return "severe" if random.random() < 0.7 else "fatal"

    if drug_key in active:
        dose_count = int(active[drug_key].get("dose_count", 0)) + 1
        if dose_count >= threshold + 1:
            return "fatal"
        if dose_count >= threshold:
            if random.random() < 0.6:
                return "severe"
            return "fatal"

    active_categories = set()
    for dk, _dstate in active.items():
        d = DRUGS.get(dk)
        if d:
            active_categories.add(d.get("drug_category"))
    new_cat = drug.get("drug_category")
    for combo, od_chance in DANGEROUS_COMBINATIONS.items():
        if new_cat in combo:
            overlap = active_categories & combo
            if overlap and new_cat not in overlap:
                if random.random() < od_chance:
                    return "severe" if random.random() < 0.7 else "fatal"
    return None


def _clear_drug_buffs(character):
    if not hasattr(character, "buffs"):
        return
    try:
        all_attr = getattr(character.buffs, "all", None)
        if callable(all_attr):
            buff_iter = list(all_attr())
        else:
            buff_iter = []
        for buff in buff_iter:
            k = getattr(buff, "key", "") or ""
            if k.startswith("drug_") or k == "overdose_severe":
                try:
                    character.buffs.remove(k)
                except Exception:
                    pass
    except Exception as err:
        logger.log_trace(f"_clear_drug_buffs: {err}")


def _reset_drug_db_flags(character):
    """Clear mechanical drug flags on character.db."""
    for attr in (
        "drug_pain_suppression",
        "drug_bleed_resistance",
        "drug_consciousness_sustain",
        "drug_stamina_regen_bonus",
        "drug_regen_multiplier",
        "drug_infection_resistance",
        "drug_hunger_multiplier",
        "drug_color_shift",
        "drug_void_sight",
        "drug_hallucination_severity",
    ):
        try:
            character.attributes.remove(attr)
        except Exception:
            try:
                setattr(character.db, attr, 0 if "bonus" in attr or "resistance" in attr else False)
            except Exception:
                pass


def clear_all_drug_effects(character):
    """Remove drug buffs and flags; used by overdose."""
    _clear_drug_buffs(character)
    _reset_drug_db_flags(character)
    character.db.active_drugs = {}


def trigger_severe_overdose(character, drug_key):
    drug = DRUGS.get(drug_key, {})
    character.msg("|R|[rOVERDOSE|n")
    character.msg(
        "|rYour body revolts. Every chemical in your blood turns hostile at once. You hit the floor. Vomit. Convulsions. The world goes black, then red, then black again. You are alive. You should not be.|n"
    )
    if character.location:
        character.location.msg_contents(
            "{name} collapses. Convulsions. Foam. Overdose.",
            exclude=character,
            mapping={"name": character},
        )
    clear_all_drug_effects(character)
    from world.buffs import build_overdose_severe_buff

    try:
        character.buffs.add(build_overdose_severe_buff(900))
    except Exception as err:
        logger.log_trace(f"trigger_severe_overdose buff: {err}")
    try:
        mx = character.max_hp
        damage = int(mx * 0.3)
        if damage > 0 and hasattr(character, "at_damage"):
            character.at_damage(None, damage, weapon_key="fists")
    except Exception as err:
        logger.log_trace(f"trigger_severe_overdose damage: {err}")
    try:
        from world.unconscious_state import set_unconscious_for_seconds

        set_unconscious_for_seconds(character, 60)
    except Exception as err:
        logger.log_trace(f"trigger_severe_overdose KO: {err}")
    try:
        character.db.last_overdose = {"drug": drug_key, "severity": "severe", "time": time.time()}
        logger.log_info("Overdose severe: %s on #%s" % (drug_key, character.id))
    except Exception:
        pass


def trigger_fatal_overdose(character, drug_key):
    try:
        character.db.last_overdose = {"drug": drug_key, "severity": "fatal", "time": time.time()}
        logger.log_info("Overdose fatal: %s on #%s" % (drug_key, character.id))
    except Exception:
        pass
    character.msg("|R|[rFATAL OVERDOSE|n")
    character.msg(
        "|rYour heart stops. Or it doesn't stop — it fibrillates, which is the same thing. The chemistry in your blood has achieved a lethal consensus. You can't breathe. You can't see. The last thing you register is the sound of your own pulse failing.|n"
    )
    if character.location:
        character.location.msg_contents(
            "{name} drops. No convulsions this time. Just — drops. Not breathing.",
            exclude=character,
            mapping={"name": character},
        )
    clear_all_drug_effects(character)
    character.db.current_hp = 0
    try:
        from world.death import make_flatlined

        make_flatlined(character, attacker=None)
    except Exception as err:
        logger.log_trace(f"trigger_fatal_overdose: {err}")
