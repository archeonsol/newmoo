"""Replace Evennia color codes with MEDICAL_COLORS references (f-string safe order)."""
import sys
from pathlib import Path


def _insert_theme_import(text: str) -> str:
    if "from world.theme_colors import MEDICAL_COLORS as MC" in text:
        return text
    lines = text.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            insert_at = i + 1
    lines.insert(insert_at, "\nfrom world.theme_colors import MEDICAL_COLORS as MC\n")
    return "".join(lines)


def migrate(s: str) -> str:
    # f-strings first (longer prefixes)
    s = s.replace('f"|R', 'f"{MC[\'arrest\']}')
    s = s.replace('f"|r', 'f"{MC[\'critical\']}')
    s = s.replace('f"|y', 'f"{MC[\'compensated\']}')
    s = s.replace('f"|m', 'f"{MC[\'infection\']}')
    s = s.replace('f"|g', 'f"{MC[\'stable\']}')
    s = s.replace("|R", '" + MC["arrest"] + "')
    s = s.replace("|r", '" + MC["critical"] + "')
    s = s.replace("|y", '" + MC["compensated"] + "')
    s = s.replace("|m", '" + MC["infection"] + "')
    s = s.replace("|g", '" + MC["stable"] + "')
    return s


def main():
    path = Path(sys.argv[1])
    text = _insert_theme_import(path.read_text(encoding="utf-8"))
    path.write_text(migrate(text), encoding="utf-8")
    print("ok", path)


if __name__ == "__main__":
    main()
