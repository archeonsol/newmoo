"""
Oral medication schedule: potency depends on taking doses ~every 8h (ideal window).
Too soon = refuse dose; missed/late = reduced effectiveness.
Timing is tracked per drug profile on the character (systemic), not per wound.
"""
import time

# Target interval between doses (clinical "every 8 hours")
IDEAL_DOSE_INTERVAL_SECS = 8 * 3600
# Minimum time before another dose (prevents stacking / toxicity)
MIN_DOSE_INTERVAL_SECS = 5 * 3600
# Below this gap from ideal, dose is "early"
EARLY_DOSE_MAX_SECS = 7 * 3600
# Ideal window end (still full potency)
LATE_IDEAL_MAX_SECS = 9 * 3600
# After this, clearly off schedule but not a full miss
SOFT_LATE_MAX_SECS = 14 * 3600


def check_dose_timing(last_dose_ts, now=None):
    """
    Return (multiplier: float or None, note: str).
    None multiplier => too soon; do not consume pill.
    First dose (no prior timestamp): multiplier ~0.88 building serum levels.
    """
    now = now or time.time()
    if last_dose_ts is None or float(last_dose_ts) <= 0:
        return 0.88, "loading dose"

    dt = now - float(last_dose_ts)
    if dt < MIN_DOSE_INTERVAL_SECS:
        return None, "too_soon"

    if dt < EARLY_DOSE_MAX_SECS:
        return 0.78, "early (suboptimal spacing)"
    if dt <= LATE_IDEAL_MAX_SECS:
        return 1.0, "on schedule"
    if dt <= SOFT_LATE_MAX_SECS:
        return 0.82, "late"
    return 0.55, "missed window"


def get_character_last_dose(character, profile_key):
    pl = getattr(character.db, "pill_last_dose", None) or {}
    if not isinstance(pl, dict):
        return None
    return pl.get(profile_key)


def record_character_dose(character, profile_key, now=None):
    """Store last oral dose time for this drug profile (systemic schedule)."""
    now = now or time.time()
    pl = getattr(character.db, "pill_last_dose", None) or {}
    if not isinstance(pl, dict):
        pl = {}
    pl[profile_key] = float(now)
    character.db.pill_last_dose = pl


def record_profile_dose(injury, profile_key, now=None):
    """Legacy: per-wound dose log (unused for systemic pills). Kept for old data."""
    now = now or time.time()
    pl = injury.get("pill_last_dose")
    if not isinstance(pl, dict):
        pl = {}
    pl[profile_key] = float(now)
    injury["pill_last_dose"] = pl
