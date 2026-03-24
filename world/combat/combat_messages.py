"""
Combat messaging and flavor text.

Canonical location: `world.combat.combat_messages`

Moved from `world/combat_messages.py` so combat text lives with the combat system.
"""

from __future__ import annotations

import random

from world.theme_colors import COMBAT_COLORS as CC

try:
    from num2words import num2words as _n2w
    _NUM2WORDS_AVAILABLE = True
except ImportError:
    _NUM2WORDS_AVAILABLE = False

try:
    from slugify import slugify as _slugify_lib
    _SLUGIFY_AVAILABLE = True
except ImportError:
    _SLUGIFY_AVAILABLE = False


def damage_word(n: int) -> str:
    """
    Return a narrative word for small damage numbers (1-20); raw int for larger.
    e.g. damage_word(3) -> "three", damage_word(25) -> "25"
    """
    n = int(n)
    if _NUM2WORDS_AVAILABLE and 1 <= n <= 20:
        try:
            return _n2w(n)
        except Exception:
            pass
    return str(n)


def _slugify_template(name: str) -> str:
    """
    Turn a weapon template display name into a safe, lowercase key.
    Example: "Executioner's Blade" -> "executioners_blade".
    Uses python-slugify for Unicode/diacritic/smart-quote handling when available.
    """
    if not name:
        return ""
    if _SLUGIFY_AVAILABLE:
        return _slugify_lib(name, separator="_")
    out = name.strip().lower()
    for ch in ("'", '"'):
        out = out.replace(ch, "")
    return out.replace(" ", "_")


def get_message_profile_id(weapon_key: str, weapon_obj=None) -> str:
    """
    Determine which message profile to use for this strike.

    If the weapon object has a db.weapon_template set (matching entries in
    world.combat.weapon_tiers), we use a profile id of
        "<weapon_key>::<slugified_template_name>"
    so that individual weapon items can override all combat text.

    Otherwise we fall back to a per-weapon-key profile like "knife" or
    "long_blade". Callers can also always define a "default" profile.
    """
    template = None
    if weapon_obj is not None and getattr(weapon_obj, "db", None):
        template = getattr(weapon_obj.db, "weapon_template", None)

    # If the stored template doesn't resolve in weapon_tiers for this weapon_key,
    # fall back to matching against the object's key. This helps legacy/spawned
    # items that were renamed but never had weapon_template set correctly.
    if template:
        try:
            from world.combat.weapon_tiers import find_weapon_template

            entry, _tier = find_weapon_template(str(weapon_key or ""), str(template))
            if not entry and weapon_obj is not None:
                entry2, _tier2 = find_weapon_template(
                    str(weapon_key or ""), str(getattr(weapon_obj, "key", "") or "")
                )
                if entry2:
                    template = entry2.get("name") or template
        except Exception:
            pass
    if template:
        slug = _slugify_template(str(template))
        if slug:
            return f"{weapon_key}::{slug}"
    return str(weapon_key or "fists")


# Central registry of combat text. Each profile key maps to per-result templates
# that use {attacker} and {defender} placeholders. Room lines see names from the
# perspective of an arbitrary third-party viewer.
#
# You can add new entries here for individual weapon templates, for example:
#   "long_blade::executioners_blade": { ... custom text ... }
#
# Any missing profile/result falls back to the base weapon_key profile, then
# finally to the "fists" profile.
#
# Unified structure:
# - Defensive outcomes (MISS/PARRIED/DODGED) live under result keys.
# - Hit outcomes (HIT pools for normal/critical) live under "HIT":
#     "HIT": { "normal": [(atk, def), ...], "critical": [(atk, def), ...] }
# - Optional per-move overrides live under "moves" and can include both result
#   dicts and "HIT" pools:
#     "moves": { "move_slug": { "MISS": {...}, "HIT": {...} } }
WEAPON_MESSAGE_PROFILES = {
    "fists": {
        "MISS": {
            "attacker": "Your punch finds air. " + CC["miss"] + "{defender}|n slipped it. You're off balance.",
            "defender": "{attacker} throws. You move. They " + CC["miss"] + "miss.|n",
            "room": "{attacker} attacks {defender} but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "Your punch goes in. " + CC["parry"] + "{defender}|n blocks. No contact. " + CC["parry"] + "Parried.|n",
            "defender": "{attacker} throws. Your guard is up. The punch is turned. " + CC["parry"] + "Parried.|n",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["parry"] + "parries the blow.|n",
        },
        "DODGED": {
            "attacker": "You commit. " + CC["dodge"] + "{defender} slips the punch.|n You're open.",
            "defender": "The punch comes. You " + CC["dodge"] + "roll.|n {attacker}'s fist misses.",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
        "SOAK": {
            "attacker": CC["soak"] + "Your blow lands on {defender}'s {loc}, but their armor absorbs it.|n",
            "defender": CC["soak"] + "{attacker}'s strike hits your {loc}; your armor takes it.|n",
            "room": "{attacker}'s blow lands on {defender}'s {loc}, but their armor " + CC["soak"] + "absorbs the hit.|n",
        },
        "SOAK_SHIELD": {
            "attacker": CC["soak"] + "Your blow lands on {effective_defender}'s {loc} — {defender} pulled them in the way — but their armor absorbs it.|n",
            "defender": CC["soak"] + "You pull {effective_defender} in the way. {attacker}'s strike hits them but armor takes it.|n",
            "effective_defender": CC["soak"] + "{defender} uses you as a shield. {attacker}'s blow hits your {loc}; your armor takes it.|n",
            "room": "{defender} pulls {effective_defender} into the line of fire. {attacker}'s blow hits {effective_defender}'s {loc}, but their armor " + CC["soak"] + "soaks the impact.|n",
        },
    },
    "claws": {
        "MISS": {
            "attacker": "You rake forward, but " + CC["miss"] + "{defender}|n slips outside your talons. Empty air.",
            "defender": "{attacker}'s claws flash for you. You shift off-line and they " + CC["miss"] + "miss.|n",
            "room": "{attacker} slashes at {defender} with chrome claws, but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "Your claws carve in. " + CC["parry"] + "{defender}|n catches your line and turns it. " + CC["parry"] + "Parried.|n",
            "defender": "{attacker}'s talons come in fast. You redirect the strike. " + CC["parry"] + "Parried.|n",
            "room": "{attacker}'s claws streak toward {defender}, but {defender} " + CC["parry"] + "parries the slash.|n",
        },
        "DODGED": {
            "attacker": "You commit to the slash. " + CC["dodge"] + "{defender} evades cleanly.|n Your claws cut nothing.",
            "defender": "Chrome talons dart for you. You " + CC["dodge"] + "dodge|n and the slash skims past.",
            "room": "{attacker} snaps a claw strike at {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
        "HIT": {
            "normal": [
                (
                    "Your claws rake across {defender}'s {loc}, opening bright lines of blood.",
                    "" + CC["crit"] + "{attacker}|n's claws tear across your {loc}. Fire follows the cut.",
                ),
                (
                    "You hook in with your talons and rip through {defender}'s {loc}.",
                    "" + CC["crit"] + "{attacker}|n's talons catch your {loc} and yank free. You stagger.",
                ),
            ],
            "critical": [
                (
                    "" + CC["dodge"] + "CRITICAL.|n You drive your claws deep into {defender}'s {loc} and rip outward.",
                    "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n buries chrome talons in your {loc} and tears them free.",
                ),
                (
                    "" + CC["dodge"] + "CRITICAL.|n Your talons find {defender}'s {loc} and shred through in one savage pull.",
                    "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's claws rake through your {loc}. You nearly fold.",
                ),
            ],
        },
        "moves": {
            "rake": {
                "MISS": {
                    "attacker": "You whip a rake at " + CC["miss"] + "{defender}|n, but they slip back and your talons comb empty air.",
                    "defender": "{attacker} snaps a quick rake toward your face. You lean away and they " + CC["miss"] + "miss.|n",
                    "room": "{attacker} lashes out with a rake at {defender}, but " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "Your rake flashes in, but " + CC["parry"] + "{defender}|n catches your wrist line and turns it aside. " + CC["parry"] + "Parried.|n",
                    "defender": "{attacker}'s rake comes fast. You intercept and redirect the claw line. " + CC["parry"] + "Parried.|n",
                    "room": "{attacker}'s rake streaks for {defender}, but {defender} " + CC["parry"] + "parries the strike.|n",
                },
                "DODGED": {
                    "attacker": "You commit to the rake and " + CC["dodge"] + "{defender} slips outside the angle.|n Nothing but air.",
                    "defender": "{attacker} rakes in at you. You " + CC["dodge"] + "dodge off-line|n and the claws skim past.",
                    "room": "{attacker} throws a rake at {defender}, but {defender} " + CC["dodge"] + "dodges clear.|n",
                },
                "HIT": {
                    "normal": [
                        (
                            "You rake your talons across {defender}'s {loc} in a fast, tearing line.",
                            "" + CC["crit"] + "{attacker}|n rakes claws across your {loc}, opening thin, vicious cuts.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your rake catches {defender}'s {loc} deep and peels through on the follow-through.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's rake tears deep into your {loc} and rips free.",
                        ),
                    ],
                },
            },
            "talon_slash": {
                "MISS": {
                    "attacker": "You carve a talon slash at " + CC["miss"] + "{defender}|n, but they pull out of range. " + CC["miss"] + "Miss.|n",
                    "defender": "{attacker}'s talon slash whistles past your chest. You moved first. They " + CC["miss"] + "miss.|n",
                    "room": "{attacker} carves a talon slash at {defender}, but " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "Your talon slash bites in, but " + CC["parry"] + "{defender}|n meets your forearm and knocks it wide. " + CC["parry"] + "Parried.|n",
                    "defender": "{attacker} slashes with chrome talons. You catch the motion and shove it off-line. " + CC["parry"] + "Parried.|n",
                    "room": "{attacker}'s talon slash streaks in, but {defender} " + CC["parry"] + "parries it aside.|n",
                },
                "DODGED": {
                    "attacker": "You throw the talon slash hard and " + CC["dodge"] + "{defender} slips past the arc.|n",
                    "defender": "The talon slash comes fast; you " + CC["dodge"] + "dodge|n and it cuts only air.",
                    "room": "{attacker} snaps a talon slash at {defender}, but {defender} " + CC["dodge"] + "dodges away.|n",
                },
                "HIT": {
                    "normal": [
                        (
                            "You whip a talon slash into {defender}'s {loc}, the chrome edge biting hard.",
                            "" + CC["crit"] + "{attacker}|n's talon slash bites into your {loc} with a hot, sharp sting.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your talon slash carves through {defender}'s {loc} in one savage stroke.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's talon slash carves through your {loc}, nearly dropping you.",
                        ),
                    ],
                },
            },
            "hooked_rip": {
                "MISS": {
                    "attacker": "You reach for a hooked rip, but " + CC["miss"] + "{defender}|n twists free before your claws can set.",
                    "defender": "{attacker} tries to set a hooked rip on you. You turn with it and they " + CC["miss"] + "miss.|n",
                    "room": "{attacker} reaches in for a hooked rip on {defender}, but " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "You hook in, but " + CC["parry"] + "{defender}|n jams your arm at the elbow and kills the rip. " + CC["parry"] + "Parried.|n",
                    "defender": "{attacker} hooks claws in for a rip. You smother the arm and stop the pull. " + CC["parry"] + "Parried.|n",
                    "room": "{attacker} tries to hook and rip into {defender}, but {defender} " + CC["parry"] + "parries in close.|n",
                },
                "DODGED": {
                    "attacker": "You shoot for the hooked rip; " + CC["dodge"] + "{defender} pivots out|n before you can latch on.",
                    "defender": "{attacker}'s hooked rip comes in tight. You " + CC["dodge"] + "dodge by rotating out|n at the last beat.",
                    "room": "{attacker} commits to a hooked rip at {defender}, but {defender} " + CC["dodge"] + "dodges out of the bind.|n",
                },
                "HIT": {
                    "normal": [
                        (
                            "You sink hooked talons into {defender}'s {loc} and rip backward.",
                            "" + CC["crit"] + "{attacker}|n hooks claws into your {loc} and rips out, staggering you.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your hooked rip buries into {defender}'s {loc} and tears a brutal channel free.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's hooked rip tears through your {loc} with brutal force.",
                        ),
                    ],
                },
            },
            "eviscerating_arc": {
                "MISS": {
                    "attacker": "You swing a wide eviscerating arc, but " + CC["miss"] + "{defender}|n drops under it. " + CC["miss"] + "Miss.|n",
                    "defender": "{attacker}'s eviscerating arc scythes across where your torso was. You duck and they " + CC["miss"] + "miss.|n",
                    "room": "{attacker} whips an eviscerating arc at {defender}, but the broad slash " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "Your eviscerating arc surges in, but " + CC["parry"] + "{defender}|n catches your arm line and deadens the sweep. " + CC["parry"] + "Parried.|n",
                    "defender": "{attacker} throws a huge eviscerating arc. You meet the limb and blunt the stroke. " + CC["parry"] + "Parried.|n",
                    "room": "{attacker}'s eviscerating arc tears in, but {defender} " + CC["parry"] + "parries and spoils the swing.|n",
                },
                "DODGED": {
                    "attacker": "You commit fully to the arc and " + CC["dodge"] + "{defender} slips outside it.|n Your claws cut nothing.",
                    "defender": "The eviscerating arc comes in broad and fast. You " + CC["dodge"] + "dodge clear|n before it can catch you.",
                    "room": "{attacker} unleashes an eviscerating arc at {defender}, but {defender} " + CC["dodge"] + "dodges outside the sweep.|n",
                },
                "HIT": {
                    "normal": [
                        (
                            "You draw a wide eviscerating arc through {defender}'s {loc}, talons hissing through cloth and skin.",
                            "" + CC["crit"] + "{attacker}|n's eviscerating arc rips across your {loc} in a broad, savage cut.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your eviscerating arc catches {defender}'s {loc} full-on and shreds through.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's eviscerating arc shreds your {loc} in a brutal sweep.",
                        ),
                    ],
                },
            },
            "fingertip_feint": {
                "MISS": {
                    "attacker": "You sell the feint, then stab in - but " + CC["miss"] + "{defender}|n doesn't bite and your follow-up misses.",
                    "defender": "{attacker} feints and flicks claws in, but you read it and they " + CC["miss"] + "miss.|n",
                    "room": "{attacker} tries a fingertip feint on {defender}, but the follow-up " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "The feint works, but " + CC["parry"] + "{defender}|n still catches your real line and turns it. " + CC["parry"] + "Parried.|n",
                    "defender": "{attacker}'s feint sells hard, but you recover in time to redirect the true strike. " + CC["parry"] + "Parried.|n",
                    "room": "{attacker}'s fingertip feint almost lands, but {defender} " + CC["parry"] + "parries the real attack.|n",
                },
                "DODGED": {
                    "attacker": "You bite on the opening and flick in, but " + CC["dodge"] + "{defender} slips out|n before the claws arrive.",
                    "defender": "{attacker} feints high and snaps low; you " + CC["dodge"] + "dodge off-line|n and avoid the claws.",
                    "room": "{attacker} feints and strikes at {defender}, but {defender} " + CC["dodge"] + "dodges the setup.|n",
                },
                "HIT": {
                    "normal": [
                        (
                            "You feint high, then flick your claws into {defender}'s {loc} before they can reset.",
                            "" + CC["crit"] + "{attacker}|n feints, then flicks claws into your {loc} with surgical precision.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your fingertip feint sells the fake perfectly, then rips into {defender}'s {loc}.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n feints and then drives claws deep into your {loc}.",
                        ),
                    ],
                },
            },
            "tendon_shear": {
                "MISS": {
                    "attacker": "You angle for tendon and slice at " + CC["miss"] + "{defender}|n, but they retract the limb in time.",
                    "defender": "{attacker} goes for a tendon shear. You pull back and they " + CC["miss"] + "miss.|n",
                    "room": "{attacker} darts in for a tendon shear on {defender}, but " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "You cut for tendon, but " + CC["parry"] + "{defender}|n knocks your forearm away before the edge can bite. " + CC["parry"] + "Parried.|n",
                    "defender": "{attacker} slices for your tendons. You jam their arm and redirect it. " + CC["parry"] + "Parried.|n",
                    "room": "{attacker}'s tendon shear streaks toward {defender}, but {defender} " + CC["parry"] + "parries the cut.|n",
                },
                "DODGED": {
                    "attacker": "You line up the tendon shear and " + CC["dodge"] + "{defender} hops out of range.|n No purchase.",
                    "defender": "{attacker} aims for your tendons; you " + CC["dodge"] + "dodge back|n and the claws miss by inches.",
                    "room": "{attacker} commits to a tendon shear, but {defender} " + CC["dodge"] + "dodges clear.|n",
                },
                "HIT": {
                    "normal": [
                        (
                            "You angle your claws for a tendon shear and slash through {defender}'s {loc}.",
                            "" + CC["crit"] + "{attacker}|n's tendon shear slices into your {loc}, threatening your balance.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your tendon shear lands clean on {defender}'s {loc}, tearing through critical tissue.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's tendon shear tears through your {loc}; your limb almost gives out.",
                        ),
                    ],
                },
            },
        },
    },
    "knife": {
        "MISS": {
            "attacker": "You lunge. " + CC["miss"] + "{defender}|n is gone. The blade cuts air. You're open.",
            "defender": "{attacker} thrusts. You're already moving. The knife misses. They " + CC["miss"] + "miss.|n",
            "room": "{attacker} attacks {defender} but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "You thrust. " + CC["parry"] + "{defender}|n meets it. Steel on steel. Your blade is turned. " + CC["parry"] + "Parried.|n",
            "defender": "The knife comes in. You block. The blade goes wide. " + CC["parry"] + "Parried.|n",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["parry"] + "parries the blow.|n",
        },
        "DODGED": {
            "attacker": "You go for the gut. " + CC["dodge"] + "{defender} rolls.|n The blade misses. You're exposed.",
            "defender": "You see the lunge. You " + CC["dodge"] + "roll.|n The knife passes. You're still up.",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
    },
    "long_blade": {
        "MISS": {
            "attacker": "You swing. " + CC["miss"] + "{defender}|n steps clear. Your edge finds nothing. You're exposed.",
            "defender": "The blade comes. You're not there. It passes. {attacker} " + CC["miss"] + "miss.|n",
            "room": "{attacker} attacks {defender} but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "Your blade comes down. " + CC["parry"] + "{defender}|n catches it. Impact. They shove it aside. " + CC["parry"] + "Parried.|n",
            "defender": "The edge falls. You meet it. You turn the blow. " + CC["parry"] + "Parried.|n",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["parry"] + "parries the blow.|n",
        },
        "DODGED": {
            "attacker": "Downstroke. " + CC["dodge"] + "{defender} slips it.|n Your edge hits nothing. You're open.",
            "defender": "The blade drops. You " + CC["dodge"] + "roll clear.|n It misses. You're still standing.",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
    },
    "long_blade::executioners_blade": {
        "MISS": {
            "attacker": "You hurl the headsman's weight in a killing arc. " + CC["miss"] + "{defender}|n wrenches clear and the slab of steel hammers sparks off stone.",
            "defender": "{attacker} swings the executioner's blade — a blur of black iron that displaces the air where your throat was. The edge " + CC["miss"] + "misses|n by a finger's width and you taste the draft of your own near-death.",
            "room": "{attacker} heaves an executioner's blade at {defender} in a stroke meant to end it. The massive edge " + CC["miss"] + "misses,|n gouging stone where flesh should have been.",
        },
        "PARRIED": {
            "attacker": "You bring the full sentence down on {defender}. Their guard catches the headsman's edge with a shriek of tortured metal; the impact jars your teeth loose. " + CC["parry"] + "Parried.|n",
            "defender": "The executioner's blade falls on you like a dropped guillotine. You get steel under it — barely — and " + CC["parry"] + "deflect the blow|n with a shock that numbs both arms to the elbows.",
            "room": "{attacker}'s executioner's blade crashes into {defender}'s guard with a sound like a church bell breaking. {defender} " + CC["parry"] + "parries,|n staggering under the sheer mass of the stroke.",
        },
        "DODGED": {
            "attacker": "You give the blade everything — shoulders, hips, murder. " + CC["dodge"] + "{defender} is already gone,|n and the momentum nearly takes you off your feet.",
            "defender": "You read the headsman's intent and move before the steel commits. The executioner's blade carves a trench where you stood. You " + CC["dodge"] + "dodge,|n heart slamming.",
            "room": "{attacker} buries the full weight of an executioner's blade into empty ground as {defender} " + CC["dodge"] + "dodges clear,|n the impact sending up a shower of grit.",
        },
        "moves": {
            "executioners_slash": {
                "MISS": {
                    "attacker": "You rip an executioner's slash at neck height. " + CC["miss"] + "{defender}|n drops under the killing line and the blade shears air, trailing a whistle like a last breath.",
                    "defender": "{attacker} uncorks a flat executioner's slash aimed to open your throat from ear to ear. You duck and feel steel part your hair. They " + CC["miss"] + "miss.|n",
                    "room": "{attacker}'s executioner's slash screams at throat-height toward {defender}, but the killing stroke " + CC["miss"] + "misses,|n the massive blade burying its momentum into a wall.",
                },
                "PARRIED": {
                    "attacker": "You drive an executioner's slash into {defender}'s guard. Metal screams. Their weapon bows but holds, bleeding the force sideways. " + CC["parry"] + "Parried.|n",
                    "defender": "You brace for the executioner's slash and catch it — God help you, you catch it — and " + CC["parry"] + "turn the edge|n aside with a wrench that nearly dislocates your shoulder.",
                    "room": "{attacker}'s executioner's slash slams into {defender}'s guard hard enough to throw sparks. {defender} " + CC["parry"] + "parries|n with a grunt of raw effort.",
                },
                "DODGED": {
                    "attacker": "You put your whole body behind the executioner's slash. " + CC["dodge"] + "{defender} reads it and vanishes outside the arc|n before the blade reaches the kill zone.",
                    "defender": "The executioner's slash is already in motion when you move, " + CC["dodge"] + "slipping off-line|n and feeling the displaced air yank at your clothes.",
                    "room": "{attacker} unleashes an executioner's slash at {defender}, but {defender} " + CC["dodge"] + "dodges|n under the singing arc of black steel.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You drag an executioner's slash through {defender}'s {loc}. The heavy edge splits cloth, then skin, then the wet layers underneath — the blade so massive it barely slows down.",
                            "" + CC["crit"] + "{attacker}|n's executioner's slash cleaves into your {loc}. You don't feel pain yet — just the weight, the impossible weight of the blade settling into you like it belongs there.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n The executioner's slash catches {defender}'s {loc} dead-on and keeps going. Meat parts. Something underneath gives with a sound you'll hear in your sleep.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's executioner's slash buries itself in your {loc}. There's a moment of nothing — then heat, then wet, then the understanding that you are coming apart.",
                        ),
                    ],
                },
            },
            "forward-weight_cleave": {
                "MISS": {
                    "attacker": "You drop a forward-weight cleave straight from the sky. " + CC["miss"] + "{defender}|n shifts and the blade hammers the ground hard enough to numb your palms.",
                    "defender": "{attacker}'s forward-weight cleave falls like a meat-cutter's chop — all mass, no mercy. You jerk sideways and the edge " + CC["miss"] + "misses,|n cracking the floor where you stood.",
                    "room": "{attacker} drops a forward-weight cleave at {defender} that could split a man crown to crotch. The blow " + CC["miss"] + "misses,|n cratering the ground.",
                },
                "PARRIED": {
                    "attacker": "You feed the blade's weight into a forward cleave. {defender}'s guard buckles under it but holds, and the force bleeds off in a screech of metal. " + CC["parry"] + "Parried.|n",
                    "defender": "The forward-weight cleave comes down on you like a felled tree. You jam steel overhead and " + CC["parry"] + "deflect the blow|n — but the shock drives you to one knee.",
                    "room": "{attacker}'s forward-weight cleave smashes into {defender}'s guard with bone-rattling force. {defender} " + CC["parry"] + "parries,|n knees buckling under the impact.",
                },
                "DODGED": {
                    "attacker": "You let gravity pull the blade through. " + CC["dodge"] + "{defender} steps off the line|n and the cleave buries itself in nothing, dragging you forward.",
                    "defender": "You feel the air compress as the forward-weight cleave falls and " + CC["dodge"] + "throw yourself clear.|n The edge hits where your collarbone was.",
                    "room": "{attacker} commits fully to a forward-weight cleave, but {defender} " + CC["dodge"] + "dodges|n and the massive blade hammers empty ground.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You drop the forward-weight cleave into {defender}'s {loc} and let gravity finish the argument. The blade sinks in with a butcher-shop thud and sticks.",
                            "The forward-weight cleave from " + CC["crit"] + "{attacker}|n hammers into your {loc}. Something cracks under the mass — not a clean sound, a splintering one. Your vision whites at the edges.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n The forward-weight cleave hits {defender}'s {loc} with the finality of a dropped anvil. The blade doesn't bounce — it sinks, and what's underneath deforms around it.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's forward-weight cleave demolishes your {loc}. You feel your body rearrange itself around the impact — bones bending, tissue compressing, something deep rupturing with a wet pop.",
                        ),
                    ],
                },
            },
            "spine_strike": {
                "MISS": {
                    "attacker": "You angle the headsman's edge for the spine. " + CC["miss"] + "{defender}|n rotates at the last instant and the blade skims past, taking a strip of cloth with it.",
                    "defender": "{attacker} hunts for your spine with the executioner's blade. You wrench sideways and the edge " + CC["miss"] + "misses,|n so close you feel the flat drag across your ribs.",
                    "room": "{attacker} lunges at {defender}'s back with a vicious spine strike. The blade " + CC["miss"] + "misses,|n but only just.",
                },
                "PARRIED": {
                    "attacker": "You thread the blade toward their spine. {defender} gets steel behind their back at the last second and jams the edge off course. " + CC["parry"] + "Parried.|n",
                    "defender": "You feel death reaching for your spine and whip your guard behind you. Steel meets steel and you " + CC["parry"] + "parry the spine strike|n blind, by feel alone.",
                    "room": "{attacker} drives the executioner's blade at {defender}'s spine, but {defender} somehow gets a guard up behind them and " + CC["parry"] + "parries the attempt.|n",
                },
                "DODGED": {
                    "attacker": "You aim for the spine — one clean stroke to sever the cord. " + CC["dodge"] + "{defender} torques away|n and the edge draws a line through empty air.",
                    "defender": "You feel the intent on your back like a cold hand and " + CC["dodge"] + "twist off the line|n as the spine strike cuts where your vertebrae were.",
                    "room": "{attacker} drives for {defender}'s spine, but {defender} " + CC["dodge"] + "dodges,|n rotating out of the blade's path at the last breath.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You thread the blade in for a spine strike at {defender}'s {loc}. The edge finds the channel between muscle and bone and digs in — their whole frame shudders and lists.",
                            "" + CC["crit"] + "{attacker}|n drives a spine strike into your {loc}. Something structural shifts. Your legs feel like they belong to someone else and your balance goes sideways.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n Your spine strike bites into {defender}'s {loc} and you feel the blade grate against something fundamental. Their body locks rigid for a heartbeat, then goes loose in all the wrong places.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's spine strike connects with your {loc} and the world goes electric. Everything below the cut turns to static — signals misfiring, muscles clenching on their own, your body no longer fully yours.",
                        ),
                    ],
                },
            },
            "half-blade_rend": {
                "MISS": {
                    "attacker": "You choke up on the blade and drive it forward in a close-range rend. " + CC["miss"] + "{defender}|n jerks back and the edge chews air where their belly was.",
                    "defender": "{attacker} crowds in and tries to gut you with a half-blade rend. You suck your stomach in and stagger back. They " + CC["miss"] + "miss|n — barely.",
                    "room": "{attacker} closes to grappling distance and drives a half-blade rend at {defender}'s midsection. The ugly stroke " + CC["miss"] + "misses.|n",
                },
                "PARRIED": {
                    "attacker": "You wrench the half-blade in close, going for the rend. {defender} jams their weapon against yours at bad-breath distance and shoves you off. " + CC["parry"] + "Parried.|n",
                    "defender": "The half-blade rend comes in close and filthy. You clamp steel against the executioner's edge and " + CC["parry"] + "force it aside|n with an ugly, grinding shove.",
                    "room": "{attacker} tries to rip into {defender} at close range with a half-blade rend. {defender} " + CC["parry"] + "parries in the clinch,|n metal grinding against metal.",
                },
                "DODGED": {
                    "attacker": "You step into the clinch, half-blade leading. " + CC["dodge"] + "{defender} peels out of grappling range|n before you can put the edge to work.",
                    "defender": "You refuse the close range and " + CC["dodge"] + "back out of the clinch|n as the half-blade rend chews through the space you just occupied.",
                    "room": "{attacker} crowds in for a half-blade rend, but {defender} " + CC["dodge"] + "slips out of the clinch|n before the edge can bite.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You choke up on the steel and drive a half-blade rend through {defender}'s {loc} at bad-breath distance. The edge catches and tears — not a clean cut but a ragged one, all leverage and malice.",
                            "The half-blade rend from " + CC["crit"] + "{attacker}|n gouges into your {loc}. They're close enough that you can smell them — sweat, steel, intent — and the blade tears through you like a jagged promise.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n You wrench the half-blade rend across {defender}'s {loc} and something gives — not just skin but the stuff underneath, peeling apart in layers. The wound is ugly, ragged, deep.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's half-blade rend rips through your {loc} at close range. You feel it catch on something inside and pull — a tearing, unzipping wrongness that sends your vision dark around the edges.",
                        ),
                    ],
                },
            },
            "sweeping_behead": {
                "MISS": {
                    "attacker": "You throw the sweeping behead — a flat, screaming arc at neck height. " + CC["miss"] + "{defender}|n drops under it and you feel the blade's hunger go unsatisfied.",
                    "defender": "{attacker}'s sweeping behead hisses over your head as you flatten yourself. The edge " + CC["miss"] + "misses|n your scalp by an inch and takes a chunk out of the wall behind you.",
                    "room": "{attacker} uncorks a sweeping behead at {defender} — a full-rotation killing stroke. The massive blade " + CC["miss"] + "misses,|n carving a groove in the scenery.",
                },
                "PARRIED": {
                    "attacker": "You hurl the sweeping behead at their neck. {defender}'s guard smashes up into the blade's path and the impact kicks through both your arms. " + CC["parry"] + "Parried.|n",
                    "defender": "You drive your weapon up into the sweeping behead's path and " + CC["parry"] + "meet the edge|n with a crash that drops your vision to a white flash.",
                    "room": "{attacker}'s sweeping behead smashes into {defender}'s raised guard with a sound like a forge hammer. {defender} " + CC["parry"] + "parries,|n visibly shaken by the blow.",
                },
                "DODGED": {
                    "attacker": "You loose the sweeping behead — all hip, all shoulder, all intent. " + CC["dodge"] + "{defender} throws themselves under the arc|n and the blade decapitates nothing.",
                    "defender": "You see the beheading arc begin and " + CC["dodge"] + "hurl yourself flat.|n The executioner's blade passes where your head was, singing.",
                    "room": "{attacker} whips a sweeping behead at {defender}'s neck in a killing arc. {defender} " + CC["dodge"] + "dodges,|n barely clearing the headsman's edge.",
                },
                "HIT": {
                    "normal": [
                        (
                            "Your sweeping behead catches {defender} across the {loc} — not the clean decapitation it promised but something worse: a deep, ragged bite that leaves the blade stuck in meat and sinew.",
                            "" + CC["crit"] + "{attacker}|n's sweeping behead slams into your {loc}. You feel how close that was to taking everything. The blade bites deep enough that you feel cold air inside the wound.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n The sweeping behead connects with {defender}'s {loc} with the full arc's momentum. The blade goes through whatever's in the way — cloth, skin, muscle — with a sound like wet canvas tearing.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's sweeping behead crunches through your {loc}. The rotation carries the blade so deep you feel it scrape bone. Something inside you lets go — quietly, finally, like it was waiting for permission.",
                        ),
                    ],
                },
            },
            "final_verdict": {
                "MISS": {
                    "attacker": "You bring the Final Verdict down with everything — this is the killing stroke, the last word. " + CC["miss"] + "{defender}|n cheats it by inches and the blade splits stone, throwing fragments.",
                    "defender": "{attacker} swings the Final Verdict and for a frozen instant you see your own death in the arc. Then you " + CC["miss"] + "move|n and the world's heaviest blade smashes the ground where you stood, hard enough to crack foundations.",
                    "room": "{attacker} swings the Final Verdict at {defender} — the headsman's masterwork, meant to end everything. The execution stroke " + CC["miss"] + "misses|n and hammers a crater into the ground.",
                },
                "PARRIED": {
                    "attacker": "You swing the Final Verdict with killing weight. {defender}'s guard catches it and for a moment holds — metal screaming, arms shaking. The judgment doesn't land. " + CC["parry"] + "Parried.|n",
                    "defender": "The Final Verdict falls on you like the world ending. You get steel under it and " + CC["parry"] + "hold|n — barely, screaming through your teeth, arms threatening to buckle — and somehow turn the blade aside.",
                    "room": "{attacker}'s Final Verdict crashes into {defender}'s guard with catastrophic force. {defender} " + CC["parry"] + "parries|n through what looks like sheer refusal to die, staggering under the impact.",
                },
                "DODGED": {
                    "attacker": "You bring the Final Verdict — the headsman's last word. " + CC["dodge"] + "{defender} is already gone.|n The blade buries itself in the ground and you're left staring at nothing.",
                    "defender": "The Final Verdict begins its descent and you " + CC["dodge"] + "move before it can finish.|n Behind you, the blade hits the ground hard enough to send cracks through stone. You don't look back.",
                    "room": "{attacker} brings the Final Verdict down on {defender} with absolute, terminal commitment. {defender} " + CC["dodge"] + "dodges|n and the execution stroke obliterates the ground, sending up a spray of broken stone.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You deliver the Final Verdict to {defender}'s {loc}. The blade lands with the weight of a pronouncement — heavy, deliberate, absolute. The wound opens and stays open, too deep and too wide to close on its own.",
                            "The Final Verdict from " + CC["crit"] + "{attacker}|n crashes into your {loc}. It doesn't feel like being cut. It feels like being divided — the blade so heavy and the stroke so committed that your body just accepts the separation.",
                        ),
                    ],
                    "critical": [
                        (
                            "" + CC["dodge"] + "CRITICAL.|n The Final Verdict finds {defender}'s {loc} and the headsman's steel delivers everything it promised. The wound is catastrophic — deep, structural, the kind that changes what a body is.",
                            "" + CC["dodge"] + "CRITICAL.|n " + CC["crit"] + "{attacker}|n's Final Verdict connects with your {loc} and the world reduces to a single fact: you have been opened. The blade goes deeper than muscle, deeper than bone — it hits something foundational and breaks it.",
                        ),
                    ],
                },
            },
        },
        "HIT": {"normal": [], "critical": []},
    },
    "blunt": {
        "MISS": {
            "attacker": "You swing. " + CC["miss"] + "{defender}|n reads it and moves. Your weapon hits empty. You're open.",
            "defender": "{attacker} winds up. You're gone before it lands. They " + CC["miss"] + "miss.|n",
            "room": "{attacker} attacks {defender} but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "You swing. " + CC["parry"] + "{defender}|n blocks. Your strike slides off. " + CC["parry"] + "Parried.|n",
            "defender": "{attacker} swings. You block. The blow goes wide. " + CC["parry"] + "Parried.|n",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["parry"] + "parries the blow.|n",
        },
        "DODGED": {
            "attacker": "You put your weight into it. " + CC["dodge"] + "{defender} is gone.|n The blow finds air. You're exposed.",
            "defender": "You see it coming. You " + CC["dodge"] + "roll.|n The weapon misses. That would have broken you.",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
    },
    "sidearm": {
        "MISS": {
            "attacker": "You fire. " + CC["miss"] + "{defender}|n isn't there. The round goes wide. Miss.",
            "defender": "The shot cracks past. You moved. They " + CC["miss"] + "miss.|n",
            "room": "{attacker} attacks {defender} but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "You fire, but " + CC["parry"] + "{defender}'s cover eats the rounds.|n",
            "defender": "Shots spark off your cover. {attacker} doesn't connect. " + CC["parry"] + "Parried.|n",
            "room": "{attacker}'s shots spark off {defender}'s cover. " + CC["parry"] + "No clean hit.|n",
        },
        "DODGED": {
            "attacker": "You squeeze. " + CC["dodge"] + "{defender} is already moving.|n The round goes where they were. Miss.",
            "defender": "Muzzle flash. You " + CC["dodge"] + "dive.|n The shot goes past. You're still breathing.",
            "room": "{attacker} attacks {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
    },
    "longarm": {
        "MISS": {
            "attacker": "You fire. " + CC["miss"] + "{defender}|n isn't there. The round goes wide. Miss.",
            "defender": "The shot cracks past. You moved. They " + CC["miss"] + "miss.|n",
            "room": "{attacker} attacks {defender} but " + CC["miss"] + "misses.|n",
        },
        "PARRIED": {
            "attacker": "You send a round in, but " + CC["parry"] + "{defender}'s cover drinks it.|n",
            "defender": "You feel the impact through cover. {attacker} doesn't get through. " + CC["parry"] + "Parried.|n",
            "room": "{attacker}'s shot punches {defender}'s cover but " + CC["parry"] + "doesn't get through.|n",
        },
        "DODGED": {
            "attacker": "You line it up. " + CC["dodge"] + "{defender} is already moving.|n The round takes stone instead.",
            "defender": "You break line-of-fire as the shot comes. You " + CC["dodge"] + "duck behind cover.|n",
            "room": "{attacker} fires at {defender}, but {defender} " + CC["dodge"] + "slips out of the firing line.|n",
        },
    },
    "automatic": {
        "MISS": {
            "attacker": "You rake the space where " + CC["miss"] + "{defender}|n was. Rounds chew stone. They're not there.",
            "defender": "Automatic fire rips past. You moved before it walked onto you. They " + CC["miss"] + "miss.|n",
            "room": "{attacker}'s burst tears up the air around {defender} but " + CC["miss"] + "doesn't connect.|n",
        },
        "PARRIED": {
            "attacker": "Your burst chews into " + CC["parry"] + "{defender}'s cover.|n No clean shot.",
            "defender": "Automatic fire hammers your cover. {attacker} can't quite walk it onto you. " + CC["parry"] + "Parried.|n",
            "room": "{attacker}'s burst hammers {defender}'s cover, " + CC["parry"] + "throwing up chips instead of blood.|n",
        },
        "DODGED": {
            "attacker": "You walk a burst through the space. " + CC["dodge"] + "{defender} dives clear.|n",
            "defender": "You see the burst coming and " + CC["dodge"] + "dive out of its path.|n Rounds tear where you were.",
            "room": "{attacker} sweeps a burst at {defender}, but {defender} " + CC["dodge"] + "dodges aside.|n",
        },
    },
}


def get_result_messages(result: str, weapon_key: str, weapon_obj=None, move_name: str | None = None):
    """
    Return the appropriate message templates for a MISS/PARRIED/DODGED result.
    """
    result = str(result or "").upper()
    base_key = str(weapon_key or "fists")
    profile_id = get_message_profile_id(base_key, weapon_obj)

    profile = WEAPON_MESSAGE_PROFILES.get(profile_id)
    if not profile:
        profile = WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

    if move_name:
        move_slug = _slugify_template(str(move_name))
        moves = profile.get("moves") or {}
        move_profile = moves.get(move_slug)
        if move_profile:
            messages = move_profile.get(result)
            if messages:
                return messages

    messages = profile.get(result)
    if not messages:
        messages = WEAPON_MESSAGE_PROFILES["fists"].get(result, {})
    return messages or {}


def get_soak_messages(
    weapon_key: str,
    weapon_obj=None,
    move_name: str | None = None,
    *,
    shielded: bool = False,
):
    """
    Return armor soak message templates when armor absorbs the hit.

    Returns a dict of templates using placeholders:
    - Always: {attacker}, {defender}, {loc}
    - If shielded=True: also {effective_defender}; and may include an "effective_defender" key.
    """
    key = "SOAK_SHIELD" if shielded else "SOAK"
    base_key = str(weapon_key or "fists")
    profile_id = get_message_profile_id(base_key, weapon_obj)

    profile = WEAPON_MESSAGE_PROFILES.get(profile_id)
    if not profile:
        profile = WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

    if move_name:
        move_slug = _slugify_template(str(move_name))
        move_profile = (profile.get("moves") or {}).get(move_slug) or {}
        msgs = move_profile.get(key)
        if msgs:
            return msgs

    msgs = profile.get(key)
    if not msgs:
        msgs = WEAPON_MESSAGE_PROFILES["fists"].get(key, {})
    return msgs or {}


def hit_message(
    weapon_key,
    body_part,
    defender_name,
    attacker_name,
    is_critical,
    weapon_obj=None,
    move_name: str | None = None,
):
    """
    Flavorful hit messages with hit location.
    Returns (attacker_line, defender_line).
    """
    loc = body_part or "them"
    profile_id = get_message_profile_id(weapon_key, weapon_obj)
    want = "critical" if is_critical else "normal"

    base_key = str(weapon_key or "fists")
    profile = WEAPON_MESSAGE_PROFILES.get(profile_id) or WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

    def _get_hit_pool(p):
        if not p:
            return None
        hit = p.get("HIT") or {}
        pool = hit.get(want)
        return pool if pool else None

    if move_name and profile:
        move_slug = _slugify_template(str(move_name))
        move_profile = (profile.get("moves") or {}).get(move_slug) or {}
        pool = _get_hit_pool(move_profile)
        if pool:
            atk, def_ = random.choice(pool)
            return atk.format(defender=defender_name, attacker=attacker_name, loc=loc), def_.format(
                defender=defender_name, attacker=attacker_name, loc=loc
            )

    pool = _get_hit_pool(profile)
    if pool:
        atk, def_ = random.choice(pool)
        return atk.format(defender=defender_name, attacker=attacker_name, loc=loc), def_.format(
            defender=defender_name, attacker=attacker_name, loc=loc
        )

    # Fallback to weapon_key-based text.
    if weapon_key == "knife":
        if is_critical:
            pool = [
                (
                    "" + CC["dodge"] + "CRITICAL.|n You drive the blade into {defender}'s {loc}. Steel goes deep; they buckle.",
                    "" + CC["crit"] + "{attacker}|n sinks the knife into your {loc}. You double over, still standing.",
                ),
                (
                    "" + CC["dodge"] + "CRITICAL.|n One vicious thrust into {defender}'s {loc}. The blade comes back red.",
                    "" + CC["crit"] + "{attacker}|n opens you at the {loc}. You reel but stay up.",
                ),
            ]
        else:
            pool = [
                (
                    "You slash at {defender}'s {loc}. The edge bites; they hiss and stagger.",
                    "The blade cuts your {loc}. It burns. You're still in the fight.",
                ),
                (
                    "Steel finds flesh at {defender}'s {loc}. A cut opens; red runs.",
                    "" + CC["crit"] + "{attacker}|n opens a cut on your {loc}. You press a hand to it and hold your ground.",
                ),
            ]
    elif weapon_key == "long_blade":
        if is_critical:
            pool = [
                (
                    "" + CC["dodge"] + "CRITICAL.|n You slice through {defender}'s {loc} in one long stroke. "
                    "The edge is red; they crumple to one knee.",
                    "" + CC["crit"] + "{attacker}|n's blade shears across your {loc}. You drop to a knee, gasping.",
                ),
                (
                    "" + CC["dodge"] + "CRITICAL.|n A sweeping cut catches {defender}'s {loc}. Flesh parts; they stagger hard.",
                    "" + CC["crit"] + "{attacker}|n cuts you deep across the {loc}. You're still standing — barely.",
                ),
            ]
        else:
            pool = [
                (
                    "You bring the edge down on {defender}'s {loc}. A clean cut; they reel back.",
                    "The blade finds your {loc}. You stagger but keep your feet.",
                ),
                (
                    "Your sword lashes across {defender}'s {loc}. Blood on the steel; they're still up.",
                    "" + CC["crit"] + "{attacker}|n opens a gash on your {loc}. You taste blood and hold your stance.",
                ),
            ]
    elif weapon_key == "blunt":
        if is_critical:
            pool = [
                (
                    "" + CC["dodge"] + "CRITICAL.|n You put everything into a blow to {defender}'s {loc}. "
                    "You feel the impact; they fold and catch themselves.",
                    "" + CC["crit"] + "{attacker}|n crushes your {loc}. Something gives. You stay up through sheer will.",
                ),
                (
                    "" + CC["dodge"] + "CRITICAL.|n One heavy strike to {defender}'s {loc}. The crack is ugly. They stagger but don't fall.",
                    "" + CC["crit"] + "{attacker}|n lands it on your {loc}. Your vision blurs. You're still standing.",
                ),
            ]
        else:
            pool = [
                (
                    "Your strike lands on {defender}'s {loc}. Solid impact; they grunt and reel.",
                    "The blow catches your {loc}. Your head rings. You stay in the fight.",
                ),
                (
                    "You hammer {defender}'s {loc}. They stagger, still up.",
                    "Something heavy finds your {loc}. You blink, taste blood, and hold your ground.",
                ),
            ]
    elif weapon_key in ("sidearm", "longarm", "automatic"):
        if is_critical:
            pool = [
                (
                    "" + CC["dodge"] + "CRITICAL.|n Your round punches through {defender}'s {loc}. "
                    "They jerk and stagger, hand to the wound.",
                    "" + CC["crit"] + "{attacker}|n shoots you. The bullet hits your {loc}. You're still on your feet.",
                ),
                (
                    "" + CC["dodge"] + "CRITICAL.|n The shot finds {defender}'s {loc}. They double over but don't drop.",
                    "" + CC["crit"] + "{attacker}|n's round tears into your {loc}. You reel and stay standing.",
                ),
            ]
        else:
            pool = [
                (
                    "Your shot hits {defender}'s {loc}. They jerk; blood blooms. Still up.",
                    "You're hit in the {loc}. Shot. The pain is coming. You're still fighting.",
                ),
                (
                    "The round finds flesh at {defender}'s {loc}. They flinch and keep their feet.",
                    "" + CC["crit"] + "{attacker}|n's bullet grazes your {loc}. Shock holds the worst at bay. You hold your ground.",
                ),
            ]
    else:
        if is_critical:
            pool = [
                (
                    "" + CC["dodge"] + "CRITICAL.|n Your fist connects with {defender}'s {loc}. "
                    "You feel bone. They stagger badly but stay up.",
                    "" + CC["crit"] + "{attacker}|n lands a brutal shot on your {loc}. Lights flash. You're still standing.",
                ),
                (
                    "" + CC["dodge"] + "CRITICAL.|n You put everything into a strike to {defender}'s {loc}. "
                    "They reel and catch themselves.",
                    "" + CC["crit"] + "{attacker}|n hits your {loc} hard. You taste blood. You don't go down.",
                ),
            ]
        else:
            pool = [
                (
                    "Your fist connects with {defender}'s {loc}. Solid. They stagger.",
                    "The punch catches your {loc}. You taste blood. Still up.",
                ),
                (
                    "You hit {defender} in the {loc}. They reel but keep their feet.",
                    "" + CC["crit"] + "{attacker}|n's blow finds your {loc}. You blink and stay in it.",
                ),
            ]

    atk_tpl, def_tpl = random.choice(pool)
    return atk_tpl.format(defender=defender_name, attacker=attacker_name, loc=loc), def_tpl.format(
        defender=defender_name, attacker=attacker_name, loc=loc
    )


# Legacy: kept for any external imports.
HIT_POOLS: dict = {}

