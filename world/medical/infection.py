"""
Infection subsystem for wound-driven medical state.
Split out from world.medical.__init__ to keep core module maintainable.
"""
import random
import time

from world.theme_colors import MEDICAL_COLORS as MC

_MI = MC["infection"]
_CR = MC["critical"]
_AR = MC["arrest"]

INFECTION_CATALOG = {
    "surface_cellulitis": {"label": "Surface cellulitis", "base_severity": 1},
    "stitch_abscess": {"label": "Stitch abscess", "base_severity": 1},
    "anaerobic_wound_rot": {"label": "Anaerobic wound rot", "base_severity": 2},
    "bone_deep_osteitis": {"label": "Bone-deep osteitis", "base_severity": 2},
    "pleural_empyema": {"label": "Pleural empyema", "base_severity": 2},
    "sewer_fever": {"label": "Sewer fever", "base_severity": 2},
    "chrome_interface_necrosis": {"label": "Chrome-interface necrosis", "base_severity": 3},
    "bloodfire_sepsis": {"label": "Bloodfire sepsis", "base_severity": 3},
    "chrome_rejection_syndrome": {"label": "Chrome rejection syndrome", "base_severity": 2},
    "neural_rejection_cascade": {"label": "Neural rejection cascade", "base_severity": 3},
}

INFECTION_STAGE_LABELS = {
    1: "localized inflammation",
    2: "spreading infection",
    3: "systemic fever",
    4: "septic collapse",
}

INFECTION_DISEASE_MESSAGES = {
    "surface_cellulitis": {
        "onset": [f"{_MI}Red streaks creep out from the cut. The skin is hot and tender.|n"],
        "worsen": [f"{_MI}The redness spreads in a map under your skin. It burns to the touch.|n"],
        "critical": [f"{_CR}Your whole limb throbs and shakes. The infection has gone systemic.|n"],
    },
    "stitch_abscess": {
        "onset": [f"{_MI}Pressure builds around the sutures. The wound edge looks angry and swollen.|n"],
        "worsen": [f"{_MI}A pocket of heat and fluid forms under the stitches. The closure is failing.|n"],
        "critical": [f"{_CR}The wound is tense, foul, and close to bursting. You feel fever taking hold.|n"],
    },
    "anaerobic_wound_rot": {
        "onset": [f"{_MI}A sweet-rotten smell rises from deep tissue. This is not superficial.|n"],
        "worsen": [f"{_CR}The tissue around the wound darkens and crackles under pressure.|n"],
        "critical": [f"{_AR}Rot runs ahead of pain. This can kill you fast without debridement.|n"],
    },
    "bone_deep_osteitis": {
        "onset": [f"{_MI}A deep ache drills into the bone. Movement sends lightning through it.|n"],
        "worsen": [f"{_MI}The pain turns constant and heavy, like the bone itself is burning.|n"],
        "critical": [f"{_CR}You feel weak and feverish. The infection is chewing through marrow.|n"],
    },
    "pleural_empyema": {
        "onset": [f"{_MI}Your chest feels wet and tight. Breathing becomes shallow and sharp.|n"],
        "worsen": [f"{_CR}Each breath rasps; pressure builds behind the ribs.|n"],
        "critical": [f"{_AR}You can barely draw air. The pleural infection is becoming fatal.|n"],
    },
    "sewer_fever": {
        "onset": [f"{_MI}Chills hit you in waves. Your gut knots and your head swims.|n"],
        "worsen": [f"{_MI}Your temperature spikes and your thoughts slow. Sewer fever is spreading.|n"],
        "critical": [f"{_CR}You shake uncontrollably, drenched in sweat. Organ failure is close.|n"],
    },
    "chrome_interface_necrosis": {
        "onset": [f"{_MI}Pain needles through the chrome-meat seam. The interface is inflamed.|n"],
        "worsen": [f"{_CR}The implant margin blackens and leaks; rejection is turning necrotic.|n"],
        "critical": [f"{_AR}The interface is breaking down rapidly. You need surgical revision now.|n"],
    },
    "bloodfire_sepsis": {
        "onset": [f"{_MI}Heat floods your veins. Your pulse hammers out of rhythm.|n"],
        "worsen": [f"{_CR}You drift between chills and burning fever. Sepsis is advancing.|n"],
        "critical": [f"{_AR}Your vision tunnels and your pressure crashes. Bloodfire sepsis is terminal without immediate care.|n"],
    },
    "chrome_rejection_syndrome": {
        "onset": [f"{_MI}The tissue around the implant is hot and swollen. The body is fighting the chrome.|n"],
        "worsen": [f"{_CR}Inflammation spreads from the interface. The implant site weeps fluid. Rejection is escalating.|n"],
        "critical": [f"{_AR}The body is winning against the chrome. The implant is being pushed out. Without intervention, it will fail.|n"],
    },
    "neural_rejection_cascade": {
        "onset": [f"{_MI}A static ache blooms along neural interface lines. Signal quality drops.|n"],
        "worsen": [f"{_CR}Neural backlash spikes through the implant. Motor control stutters and pain sharpens.|n"],
        "critical": [f"{_AR}Neural rejection cascade is catastrophic. The interface is failing in real time.|n"],
    },
}

INFECTION_STAGE_PENALTIES = {
    1: {"atk": -1, "def": -1, "stamina_recovery": -1, "hp_drain": 0},
    2: {"atk": -2, "def": -2, "stamina_recovery": -1, "hp_drain": 1},
    3: {"atk": -4, "def": -3, "stamina_recovery": -2, "hp_drain": 2},
    4: {"atk": -6, "def": -5, "stamina_recovery": -3, "hp_drain": 4},
}
INFECTION_RISK_THRESHOLD = 0.55
INFECTION_STAGE_ADVANCE_SECS = 1800

# Must match world.medical.medical_treatment.IMMUNE_MEDIATED_INFECTIONS (avoid import cycle).
_IMMUNE_MEDIATED = frozenset({"chrome_rejection_syndrome", "neural_rejection_cascade"})


def _infection_message(infection_key, phase):
    pool = (INFECTION_DISEASE_MESSAGES.get(infection_key) or {}).get(phase) or []
    return random.choice(pool) if pool else None


def _environment_infection_modifier(character):
    loc = getattr(character, "location", None)
    if not loc:
        return 1.0
    key = (getattr(loc, "key", "") or "").lower()
    tags = set()
    try:
        for t in (loc.tags.all() if hasattr(loc, "tags") else []):
            tags.add(str(getattr(t, "db_key", t)).lower())
    except Exception:
        tags = set()
    bad_words = ("sewer", "sludge", "waste", "industrial", "toxic", "foundry", "underhive")
    mod = 1.0
    if any(w in key for w in bad_words):
        mod += 0.35
    if any(t in tags for t in ("dirty", "sewer", "industrial", "contaminated")):
        mod += 0.35
    if any(t in tags for t in ("clinic", "hospital", "sterile")):
        mod -= 0.25
    return max(0.6, min(1.8, mod))


def _pick_infection_type(injury):
    part = (injury.get("body_part") or "").lower()
    if "chronic_augmented_interface" in (injury.get("flags") or []):
        return "chrome_interface_necrosis"
    if injury.get("fracture"):
        return random.choice(["bone_deep_osteitis", "anaerobic_wound_rot"])
    od = injury.get("organ_damage") or {}
    if "lungs" in od:
        return "pleural_empyema"
    if "heart" in od or "carotid" in od:
        return "bloodfire_sepsis"
    if part in ("abdomen", "groin", "back"):
        return random.choice(["anaerobic_wound_rot", "sewer_fever"])
    return random.choice(["surface_cellulitis", "stitch_abscess", "sewer_fever"])


def get_infection_penalties(character):
    from world.medical.injuries import _normalize_injuries
    injuries = _normalize_injuries(character)
    out = {"atk": 0, "def": 0, "stamina_recovery": 0, "hp_drain": 0}
    for injury in injuries:
        stage = int(injury.get("infection_stage", 0) or 0)
        if stage <= 0:
            continue
        p = INFECTION_STAGE_PENALTIES.get(stage, {})
        for key in out:
            out[key] += int(p.get(key, 0))
    return out


def get_infection_readout(character):
    from world.medical.injuries import _normalize_injuries
    injuries = _normalize_injuries(character)
    rows = []
    for injury in injuries:
        stage = int(injury.get("infection_stage", 0) or 0)
        if stage <= 0:
            continue
        key = injury.get("infection_type") or "surface_cellulitis"
        label = INFECTION_CATALOG.get(key, {}).get("label", key.replace("_", " "))
        part = (injury.get("body_part") or "wound").strip()
        risk = float(injury.get("infection_risk", 0.0) or 0.0)
        rows.append({
            "body_part": part,
            "infection_key": key,
            "label": label,
            "stage": stage,
            "stage_label": INFECTION_STAGE_LABELS.get(stage, "progressing"),
            "risk": risk,
        })
    rows.sort(key=lambda r: (r["stage"], r["risk"]), reverse=True)
    return rows


def apply_infection_tick(character):
    from world.medical.core import _ensure_medical_db
    from world.medical.injuries import _normalize_injuries
    from world.body import is_part_augmented, is_part_chrome
    _ensure_medical_db(character)
    injuries = _normalize_injuries(character)
    if not injuries:
        return
    now = time.time()
    env_mod = _environment_infection_modifier(character)
    for injury in injuries:
        if (injury.get("hp_occupied", 0) or 0) <= 0:
            continue
        last_tick = float(injury.get("last_infection_tick", 0.0) or 0.0)
        if last_tick and (now - last_tick) < INFECTION_STAGE_ADVANCE_SECS:
            continue
        injury["last_infection_tick"] = now
        if injury.get("cyberware_dbref") and injury.get("type") == "surgery":
            rejection_base = float(injury.get("rejection_risk", 0.05) or 0.05)
            age_hours = (now - float(injury.get("created_at", now) or now)) / 3600.0
            age_decay = max(0.0, 1.0 - (age_hours / 48.0))
            effective_risk = rejection_base * age_decay
            imm_until_r = float(injury.get("immunosuppressant_until", 0.0) or 0.0)
            imm_pot_r = float(injury.get("immunosuppressant_potency", 0.0) or 0.0)
            rejection_dampen = min(0.82, imm_pot_r * 2.6) if imm_until_r > now else 0.0
            if random.random() < (effective_risk * 0.1 * (1.0 - rejection_dampen)):
                if not injury.get("infection_type"):
                    injury["infection_type"] = "chrome_rejection_syndrome"
                    injury["infection_stage"] = max(1, int(injury.get("infection_stage", 0) or 0))
                    msg = _infection_message("chrome_rejection_syndrome", "onset")
                    if msg and hasattr(character, "msg"):
                        character.msg(msg)
        quality = int(injury.get("treatment_quality", 0) or 0)
        cleaned_recently = (now - float(injury.get("cleaned_at", 0.0) or 0.0)) < 3600
        risk_gain = 0.04 * env_mod
        if quality <= 0:
            risk_gain += 0.06
        elif quality == 1:
            risk_gain += 0.03
        if cleaned_recently:
            risk_gain -= 0.04
        if injury.get("bleed_treated") is False and float(injury.get("bleed_rate", 0.0) or 0.0) > 0:
            risk_gain += 0.04
        part = (injury.get("body_part") or "").lower()
        if part and hasattr(character, "db"):
            try:
                if is_part_chrome(character, part):
                    risk_gain = min(risk_gain, 0.01)
                elif is_part_augmented(character, part):
                    risk_gain += 0.03
            except Exception:
                pass
        injury["infection_risk"] = min(1.0, float(injury.get("infection_risk", 0.0) or 0.0) + max(0.0, risk_gain))
        stage = int(injury.get("infection_stage", 0) or 0)
        if stage <= 0:
            abx_until0 = float(injury.get("antibiotic_until", 0.0) or 0.0)
            abx_pot0 = float(injury.get("antibiotic_potency", 0.0) or 0.0)
            if abx_until0 > now and abx_pot0 > 0.0:
                injury["infection_risk"] = max(0.0, float(injury.get("infection_risk", 0.0) or 0.0) - abx_pot0 * 0.55)
            imm_until0 = float(injury.get("immunosuppressant_until", 0.0) or 0.0)
            imm_pot0 = float(injury.get("immunosuppressant_potency", 0.0) or 0.0)
            if imm_until0 > now and imm_pot0 > 0.0:
                injury["infection_risk"] = max(0.0, float(injury.get("infection_risk", 0.0) or 0.0) - imm_pot0 * 0.35)
                if injury.get("cyberware_dbref") and injury.get("type") == "surgery":
                    rr0 = float(injury.get("rejection_risk", 0.05) or 0.05)
                    injury["rejection_risk"] = max(0.0, rr0 - imm_pot0 * 0.025)
            if abx_until0 and abx_until0 <= now:
                injury["antibiotic_until"] = 0.0
                injury["antibiotic_potency"] = 0.0
                injury["antibiotic_profile"] = None
            if imm_until0 and imm_until0 <= now:
                injury["immunosuppressant_until"] = 0.0
                injury["immunosuppressant_potency"] = 0.0
                injury["immunosuppressant_profile"] = None
        if stage <= 0 and injury["infection_risk"] >= INFECTION_RISK_THRESHOLD:
            injury["infection_type"] = injury.get("infection_type") or _pick_infection_type(injury)
            injury["infection_stage"] = 1
            injury["infection_since"] = now
            msg = _infection_message(injury["infection_type"], "onset")
            if msg and hasattr(character, "msg"):
                character.msg(msg)
        elif stage > 0:
            itype = injury.get("infection_type") or ""
            imm_until = float(injury.get("immunosuppressant_until", 0.0) or 0.0)
            imm_potency = float(injury.get("immunosuppressant_potency", 0.0) or 0.0)
            if itype in _IMMUNE_MEDIATED and imm_until > now and imm_potency > 0.0:
                injury["infection_risk"] = max(0.0, float(injury.get("infection_risk", 0.0) or 0.0) - imm_potency)
                cure_roll = 0.2 + (0.65 * imm_potency) + (0.04 * quality) + (0.06 if cleaned_recently else 0.0)
                if random.random() < min(0.85, cure_roll):
                    injury["infection_stage"] = max(0, stage - 1)
                    stage = int(injury.get("infection_stage", 0) or 0)
                if stage <= 0:
                    injury["infection_type"] = None
                    injury["infection_since"] = 0.0
                    injury["immunosuppressant_until"] = 0.0
                    injury["immunosuppressant_potency"] = 0.0
                    injury["immunosuppressant_profile"] = None
                    continue
            elif itype in _IMMUNE_MEDIATED and imm_until and imm_until <= now:
                injury["immunosuppressant_until"] = 0.0
                injury["immunosuppressant_potency"] = 0.0
                injury["immunosuppressant_profile"] = None
            abx_until = float(injury.get("antibiotic_until", 0.0) or 0.0)
            abx_potency = float(injury.get("antibiotic_potency", 0.0) or 0.0)
            if itype not in _IMMUNE_MEDIATED and abx_until > now and abx_potency > 0.0:
                # Timed antibiotic effect: each infection tick during an active course
                # pushes risk and stage down before natural progression resolves.
                injury["infection_risk"] = max(0.0, float(injury.get("infection_risk", 0.0) or 0.0) - abx_potency)
                cure_roll = 0.18 + (0.7 * abx_potency) + (0.04 * quality) + (0.06 if cleaned_recently else 0.0)
                if random.random() < min(0.85, cure_roll):
                    injury["infection_stage"] = max(0, stage - 1)
                    stage = int(injury.get("infection_stage", 0) or 0)
                if stage <= 0:
                    injury["infection_type"] = None
                    injury["infection_since"] = 0.0
                    injury["antibiotic_until"] = 0.0
                    injury["antibiotic_potency"] = 0.0
                    injury["antibiotic_profile"] = None
                    continue
            elif abx_until and abx_until <= now:
                injury["antibiotic_until"] = 0.0
                injury["antibiotic_potency"] = 0.0
                injury["antibiotic_profile"] = None
            stage = int(injury.get("infection_stage", 0) or 0)
            prog = 0.10 + (0.08 * env_mod) - (0.07 * quality) - (0.08 if cleaned_recently else 0.0)
            if prog > 0.03 and random.random() < min(0.55, prog):
                injury["infection_stage"] = min(4, stage + 1)
                phase = "critical" if injury["infection_stage"] >= 4 else "worsen"
                msg = _infection_message(injury.get("infection_type"), phase)
                if msg and hasattr(character, "msg"):
                    character.msg(msg)
            # Repeating reminder ticker for care seeking.
            if stage >= 2 and hasattr(character, "msg"):
                last_rem = float(injury.get("last_infection_reminder", 0.0) or 0.0)
                if (now - last_rem) >= 1800:
                    injury["last_infection_reminder"] = now
                    character.msg(f"{_MI}You feel infection worsening. Find proper medical care soon.|n")
            elif prog < 0.05 and random.random() < 0.3:
                injury["infection_stage"] = max(1, stage - 1)
            if injury.get("infection_stage", 0) <= 0:
                injury["infection_type"] = None
                injury["infection_since"] = 0.0
    penalties = get_infection_penalties(character)
    hp_drain = int(penalties.get("hp_drain", 0) or 0)
    if hp_drain > 0:
        cur = character.db.current_hp
        if cur is None and hasattr(character, "max_hp"):
            character.db.current_hp = character.max_hp
            cur = character.db.current_hp
        character.db.current_hp = max(0, int(cur or 0) - hp_drain)
