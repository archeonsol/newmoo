"""
Central theme palettes: chrome presets, combat, medical, injury, room, comm.

Evennia: |RGB cube (0-5 per digit), |=a-z greyscale, |w bold white, |n reset.
"""

# ═══════════════════════════════════════════════════════════════════════════════
#  CHROME COLORS — chromework customization (limited palette, not freeform)
# ═══════════════════════════════════════════════════════════════════════════════

CHROME_COLORS = {
    "chrome": {"code": "|w", "desc": "standard chrome — bold white"},
    "matte": {"code": "|=l", "desc": "matte dark grey — covert"},
    "black": {"code": "|=c", "desc": "matte black — void-dark"},
    "gunmetal": {"code": "|=i", "desc": "dark metallic grey"},
    "rust": {"code": "|310", "desc": "weathered rust — aged chrome"},
    "brass": {"code": "|431", "desc": "warm brass — old-world metallic"},
    "copper": {"code": "|410", "desc": "reddish copper"},
    "gold": {"code": "|530", "desc": "polished gold — expensive"},
    "silver": {"code": "|=u", "desc": "polished silver"},
    "dark steel": {"code": "|=g", "desc": "dark brushed steel"},
    "bone": {"code": "|553", "desc": "bone white — organic look"},
    "carbon": {"code": "|=e", "desc": "carbon fiber black"},
}

for _name, _data in CHROME_COLORS.items():
    _data["preview"] = f"{_data['code']}{_name}|n"


def chrome_color_code(name: str):
    """
    Resolve a chromework preset name to its |code, or None.
    Normalizes whitespace and case (e.g. 'dark steel').
    """
    if not name or not str(name).strip():
        return None
    key = " ".join(str(name).strip().lower().split())
    entry = CHROME_COLORS.get(key)
    if not entry:
        return None
    return entry.get("code")


# ═══════════════════════════════════════════════════════════════════════════════
#  COMBAT MESSAGE COLORS — hit/miss/parry/dodge/crit, trauma, chrome damage
# ═══════════════════════════════════════════════════════════════════════════════

COMBAT_COLORS = {
    "hit": "|r",
    "crit": "|R",
    "miss": "|r",
    "dodge": "|y",
    "parry": "|c",
    "soak": "|c",
    "trauma_organ": "|r",
    "trauma_bone": "|y",
    "trauma_bleed": "|r",
    "chrome_damage": "|c",
    "chrome_destroy": "|R",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  MEDICAL / BIOSCANNER COLORS
# ═══════════════════════════════════════════════════════════════════════════════

MEDICAL_COLORS = {
    "stable": "|g",
    "compensated": "|y",
    "compromised": "|y",
    "critical": "|r",
    "failing": "|r",
    "arrest": "|R",
    "infection": "|m",
    "treated": "|g",
    "untreated": "|r",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  INJURY DESCRIPTION COLORS — wound lines on look
# ═══════════════════════════════════════════════════════════════════════════════

INJURY_COLORS = {
    "wound": "|r",
    "bandaged": "|=n",
    "splinted": "|y",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  ROOM AND ENVIRONMENT COLORS
# ═══════════════════════════════════════════════════════════════════════════════

ROOM_COLORS = {
    "room_name": "|w",
    "exit": "|c",
    "exit_dim": "|x",
    "ambient": "|x",
    "character_name": "|520",
    "object": "|035",  # teal — objects/corpses in "You see" (legacy ROOM_DESC_OBJECT_NAME_COLOR)
}

# ═══════════════════════════════════════════════════════════════════════════════
#  COMMUNICATION COLORS — handset, groups, Matrix comms
# ═══════════════════════════════════════════════════════════════════════════════

COMM_COLORS = {
    "say": "|w",
    "whisper": "|x",
    "phone_call": "|c",
    "text_msg": "|w",
    "group_prefix": "|c",
    "system_msg": "|x",
    "timestamp": "|x",
}
