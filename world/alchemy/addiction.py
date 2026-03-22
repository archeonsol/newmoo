"""
Addiction levels, withdrawal, and long-term recovery ticks.
"""
import random
import time

from evennia.utils import logger

from world.alchemy import ADDICTION_RECOVERY_DAYS, DRUGS, WITHDRAWAL_ONSET_HOURS
from world.buffs import build_drug_buff_class


def _character_has_buff_key(character, buff_key):
    if not character or not hasattr(character, "buffs"):
        return False
    try:
        all_attr = getattr(character.buffs, "all", None)
        if not callable(all_attr):
            return False
        for buff in all_attr():
            if getattr(buff, "key", "") == buff_key:
                return True
    except Exception:
        return False
    return False


def tick_online_characters():
    """
    Called every 30 minutes from global script. Process online player characters only.
    """
    try:
        from typeclasses.characters import Character

        qs = Character.objects.filter(db_location__isnull=False)
        for char in qs.iterator():
            try:
                if not char or not char.sessions.count():
                    continue
                _tick_character_addiction(char)
            except Exception as err:
                logger.log_trace(f"addiction.tick: {err}")
    except Exception as err:
        logger.log_trace(f"addiction.tick_online_characters: {err}")


def _tick_character_addiction(character):
    now = time.time()
    ad = getattr(character.db, "addictions", None) or {}
    if not ad:
        return
    recovery_seconds = int(ADDICTION_RECOVERY_DAYS) * 86400
    for drug_key, entry in list(ad.items()):
        drug = DRUGS.get(drug_key)
        if not drug:
            continue
        level = int(entry.get("level", 0) or 0)
        if level <= 0:
            continue
        last_dose = float(entry.get("last_dose", 0) or 0)
        if last_dose <= 0:
            continue
        hours = WITHDRAWAL_ONSET_HOURS.get(level)
        if hours is None:
            continue
        abst = (now - last_dose) / 3600.0
        # Recovery: each abstinence window can reduce level by 1
        if level > 0 and (now - last_dose) >= recovery_seconds:
            lr = float(entry.get("last_recovery_reduction_at", 0) or 0)
            if lr == 0 or (now - lr) >= recovery_seconds:
                new_level = max(0, level - 1)
                entry["level"] = new_level
                entry["last_recovery_reduction_at"] = now
                entry["withdrawal_active"] = False
                ad[drug_key] = entry
                character.msg(
                    "|ySomething in your wiring loosens. The need is still there, but one notch weaker.|n"
                )
                continue
        # Withdrawal onset
        if abst >= float(hours):
            if not entry.get("withdrawal_active"):
                entry["withdrawal_active"] = True
                entry["withdrawal_started"] = now
                ad[drug_key] = entry
                _apply_withdrawal(character, drug_key, drug)
                echoes = (drug.get("addiction", {}) or {}).get("withdrawal_echoes") or []
                if echoes:
                    character.msg(random.choice(echoes))
        # Re-apply withdrawal buff if it expired while withdrawal is still active
        if entry.get("withdrawal_active"):
            buff_key = "drug_%s_withdrawal" % drug_key
            if not _character_has_buff_key(character, buff_key):
                _apply_withdrawal(character, drug_key, drug)
        # Periodic withdrawal echo while active
        if entry.get("withdrawal_active") and random.random() < 0.15:
            echoes = (drug.get("addiction", {}) or {}).get("withdrawal_echoes") or []
            if echoes:
                character.msg(random.choice(echoes))
    character.db.addictions = ad


def _apply_withdrawal(character, drug_key, drug):
    add = drug.get("addiction", {}) or {}
    debuffs = add.get("withdrawal_debuffs") or {}
    if not debuffs:
        return
    name = drug.get("name", drug_key)
    cls = build_drug_buff_class(drug_key, "withdrawal", "%s withdrawal" % name, 48 * 3600, {}, debuffs)
    try:
        character.buffs.add(cls, duration=48 * 3600)
    except Exception as err:
        logger.log_trace(f"_apply_withdrawal: {err}")


def clear_withdrawal_on_dose(character, drug_key):
    """
    Taking the drug clears withdrawal for that substance.
    """
    ad = dict(getattr(character.db, "addictions", None) or {})
    if drug_key not in ad:
        return
    entry = dict(ad[drug_key])
    entry["withdrawal_active"] = False
    entry["last_recovery_reduction_at"] = 0
    ad[drug_key] = entry
    character.db.addictions = ad
    try:
        character.buffs.remove("drug_%s_withdrawal" % drug_key)
    except Exception:
        pass
