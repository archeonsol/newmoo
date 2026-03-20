"""chromework — customize cyberware color and per-part descriptions before install."""

from evennia.commands.command import Command

from typeclasses.cyberware import CyberwareBase


CHROMOWORK_SKILL = "mechanical_engineering"
CHROMOWORK_MIN_SKILL = 75
CHROMOWORK_DESC_DIFFICULTY = 10
CHROMOWORK_DESC_MIN = 20
CHROMOWORK_DESC_MAX = 500


class CmdChromework(Command):
    """
    Customize a cyberware object's description and color before installation.

    Requires Mechanical Engineering 75+. Inventory only (not installed).

    Usage:
      chromework <item> view
      chromework <item> color <preset_name>
      chromework <item> color <skin_tone_name>   (same names as @skintone)
      chromework <item> desc <body part> = <text>
    """

    key = "chromework"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Usage: chromework <cyberware> view | color ... | desc ...")
            return
        if not hasattr(caller, "get_skill_level"):
            caller.msg("You cannot use chromework.")
            return
        if caller.get_skill_level(CHROMOWORK_SKILL) < CHROMOWORK_MIN_SKILL:
            caller.msg(
                f"Chromework requires {CHROMOWORK_SKILL.replace('_', ' ')} at {CHROMOWORK_MIN_SKILL} or higher."
            )
            return

        parts = self.args.strip().split(None, 1)
        item_name = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        obj = caller.search(item_name, location=caller, quiet=True)
        if not obj:
            caller.msg("You are not carrying that.")
            return
        obj = obj[0]
        if not isinstance(obj, CyberwareBase):
            caller.msg("That is not cyberware.")
            return
        if getattr(obj.db, "installed", False):
            caller.msg("Chromework must be done before installation. Uninstall it first.")
            return

        if not rest:
            caller.msg("Usage: chromework <item> view | color ... | desc ...")
            return

        sub = rest.split(None, 1)
        cmd = sub[0].lower()
        tail = sub[1].strip() if len(sub) > 1 else ""

        if cmd == "view":
            self._cmd_view(caller, obj)
            return
        if cmd == "color":
            self._cmd_color(caller, obj, tail)
            return
        if cmd == "desc":
            self._cmd_desc(caller, obj, tail)
            return
        caller.msg("Unknown subcommand. Use: view, color, desc.")

    def _cmd_view(self, caller, obj):
        from world.skin_tones import CHROME_COLORS, get_chrome_desc_color, get_chrome_desc_text

        caller.msg(f"|w{obj.key}|n — chromework preview")
        color = get_chrome_desc_color(obj)
        caller.msg(f"  Color code: {color or '(default |w)'}")
        mods = getattr(obj, "body_mods", {}) or {}
        for part, (mode, _t) in mods.items():
            txt = get_chrome_desc_text(obj, part)
            if not txt:
                continue
            frag = f"{color or '|w'}{txt}|n"
            caller.msg(f"  [{mode}] {part}: {frag}")

    def _cmd_color(self, caller, obj, tail):
        from world.skin_tones import SKIN_TONES, resolve_skin_tone_key, get_skin_tone_code_for_key
        from world.theme_colors import CHROME_COLORS

        if not tail:
            caller.msg("Usage: chromework <item> color <preset|skin tone name>")
            caller.msg("Presets: " + ", ".join(sorted(CHROME_COLORS.keys())))
            return
        preset_key = " ".join(tail.strip().lower().split())
        if preset_key in CHROME_COLORS:
            entry = CHROME_COLORS[preset_key]
            obj.db.custom_color = entry["code"]
            caller.msg(
                f"Chrome color set to {entry['preview']} — {entry['desc']}"
            )
            return
        sk = resolve_skin_tone_key(tail)
        if sk:
            code = get_skin_tone_code_for_key(sk)
            obj.db.custom_color = code
            meta = SKIN_TONES.get(sk, {})
            preview = meta.get("preview", sk)
            caller.msg(f"Chrome color set to {preview} ({code}).")
            return
        caller.msg("Unknown color. Use a CHROME preset or a skin tone name from @skintone.")

    def _cmd_desc(self, caller, obj, tail):
        from world.medical import BODY_PARTS
        from world.skin_tones import strip_color_codes

        if "=" not in tail:
            caller.msg("Usage: chromework <item> desc <body part> = <text>")
            return
        left, _, right = tail.partition("=")
        part = left.strip().lower()
        text = right.strip()
        if part not in BODY_PARTS:
            caller.msg("Unknown body part. Use a canonical part name (e.g. left arm, torso, head).")
            return
        mods = getattr(obj, "body_mods", {}) or {}
        if part not in mods:
            caller.msg("That cyberware does not modify that body part.")
            return
        if len(text) < CHROMOWORK_DESC_MIN or len(text) > CHROMOWORK_DESC_MAX:
            caller.msg(
                f"Description must be {CHROMOWORK_DESC_MIN}-{CHROMOWORK_DESC_MAX} characters."
            )
            return
        clean = strip_color_codes(text)
        if clean != text:
            caller.msg("Color codes were stripped from the description; color comes from chromework color.")
        tier, total = caller.roll_check(
            ["intelligence", "strength"],
            CHROMOWORK_SKILL,
            difficulty=CHROMOWORK_DESC_DIFFICULTY,
        )
        if tier == "Failure":
            caller.msg(
                f"You botch the fine adjustment. (Mechanical Engineering vs {CHROMOWORK_DESC_DIFFICULTY}, got {total})"
            )
            return
        custom = dict(getattr(obj.db, "custom_descriptions", None) or {})
        custom[part] = clean
        obj.db.custom_descriptions = custom
        obj.db.customized_by = caller.dbref
        caller.msg(f"Updated description for |w{part}|n on {obj.key}.")
