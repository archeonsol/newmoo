"""Inject COMBAT_COLORS into combat_messages.py — replace |R/|r/|c/|y with CC[...] concat."""
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "world" / "combat" / "combat_messages.py"
text = path.read_text(encoding="utf-8")
if "from world.theme_colors import COMBAT_COLORS as CC" not in text:
    text = text.replace(
        "import random\n\n",
        "import random\n\nfrom world.theme_colors import COMBAT_COLORS as CC\n\n",
        1,
    )


def migrate_colors(s: str) -> str:
    # Order: uppercase R before lowercase r
    s = s.replace("|R", '" + CC["crit"] + "')
    s = s.replace("|r", '" + CC["miss"] + "')
    s = s.replace("|c", '" + CC["parry"] + "')
    s = s.replace("|y", '" + CC["dodge"] + "')
    return s


text = migrate_colors(text)
path.write_text(text, encoding="utf-8")
print("done", path)
