"""Apply COMBAT_COLORS concat migration to a single combat module (no f-strings starting with |code)."""
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if "from world.theme_colors import COMBAT_COLORS as CC" not in text:
    # insert after first import block - after "from __future__" or first line
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i + 1
    lines.insert(insert_at, "\nfrom world.theme_colors import COMBAT_COLORS as CC\n")
    text = "".join(lines)


def migrate_colors(s: str) -> str:
    s = s.replace("|R", '" + CC["crit"] + "')
    s = s.replace("|r", '" + CC["miss"] + "')
    s = s.replace("|c", '" + CC["parry"] + "')
    s = s.replace("|y", '" + CC["dodge"] + "')
    return s


path.write_text(migrate_colors(text), encoding="utf-8")
print("ok", path)
