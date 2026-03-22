"""
Alchemy: collect, refine, load, brew, tend, claim, check, analyze, dose.
"""
import random
import re

from evennia.utils import delay

from commands.base_cmds import Command, _command_character
from world.alchemy import CHEMICALS, DRUGS
from world.alchemy.ingredients import SPECIMENS
from world.alchemy.recipes import (
    bump_analysis,
    character_knows_recipe,
    drugs_using_chemical,
    get_analysis_state,
    specimens_yielding_chemical,
)
from world.alchemy.stations import (
    claim_brew,
    claim_refine,
    experiment_brew,
    load_chemical_object,
    load_thermos_into_station,
    reconcile_station,
    start_brew,
    start_refine,
    station_status_message,
    tend_batch,
)


def _find_station(caller, args):
    """Find an alchemy station in room or by name."""
    from typeclasses.alchemy_station import AlchemyStationBase

    room = caller.location
    if not room:
        return None
    args_l = (args or "").strip().lower()
    stations = [o for o in room.contents if isinstance(o, AlchemyStationBase)]
    if not stations:
        return None
    if not args_l:
        return stations[0]
    for o in stations:
        if args_l in (o.key or "").lower() or args_l in (getattr(o.db, "station_name", "") or "").lower():
            return o
    return stations[0]


class CmdCollect(Command):
    """
    Collect a specimen into your thermos.

    Usage:
      collect <specimen name>
      collect <specimen> from <corpse>
      collect sample from <organ>  (warns; confirm with collect sample confirm from <organ>)
      collect blood from <character>
    """

    key = "collect"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        raw = (self.args or "").strip()
        if not raw:
            caller.msg("Collect what? See help collect.")
            return
        from world.alchemy.collection import (
            collect_from_character,
            collect_from_corpse,
            collect_from_organ,
            collect_from_room,
        )
        from typeclasses.corpse import Corpse

        low = raw.lower()
        # collect blood from <target>
        m = re.match(r"blood\s+from\s+(.+)", low)
        if m:
            target = caller.search(m.group(1).strip())
            if not target:
                return
            ok, msg = collect_from_character(caller, target, "live_blood")
            caller.msg(msg)
            return
        # collect spinal tap from <target> / spinal tap from
        m = re.match(r"spinal\s+tap\s+from\s+(.+)", low)
        if m:
            target = caller.search(m.group(1).strip())
            if not target:
                return
            ok, msg = collect_from_character(caller, target, "spinal_tap")
            caller.msg(msg)
            return
        # collect ... from <corpse>
        m = re.match(r"(.+?)\s+from\s+(.+)", raw, re.I)
        if m:
            kind = m.group(1).strip().lower()
            tgt = caller.search(m.group(2).strip())
            if not tgt:
                return
            if "corpse" in kind or isinstance(tgt, Corpse):
                ok, msg = collect_from_corpse(caller, tgt)
                caller.msg(msg)
                return
            if getattr(tgt.db, "organ_specimen_key", None):
                caller.msg(
                    "Collecting will |rdestroy|n the organ. To proceed: |wcollect sample confirm from %s|n"
                    % getattr(tgt, "key", "it")
                )
                return
        # collect sample from <object>
        m = re.match(r"sample\s+confirm\s+from\s+(.+)", low)
        if m:
            tgt = caller.search(m.group(1).strip())
            if not tgt:
                return
            if getattr(tgt.db, "organ_specimen_key", None):
                ok, msg = collect_from_organ(caller, tgt)
                caller.msg(msg)
                return
        m = re.match(r"sample\s+from\s+(.+)", low)
        if m:
            tgt = caller.search(m.group(1).strip())
            if not tgt:
                return
            if getattr(tgt.db, "organ_specimen_key", None):
                caller.msg(
                    "Collecting will |rdestroy|n the organ and put the specimen in your thermos. "
                    "To proceed: |wcollect sample confirm from %s|n"
                    % getattr(tgt, "key", "it")
                )
                return
        # room specimen: normalize key from arg
        key = low.replace(" ", "_")
        for sk in SPECIMENS:
            if sk.replace("_", " ") == low or sk == key:
                ok, msg = collect_from_room(caller, sk)
                caller.msg(msg)
                return
        caller.msg("You cannot collect that here.")


class CmdLoad(Command):
    """
    Load chemicals or a thermos into an alchemy station.

    Usage:
      load <object> in <station>
      load thermos in <station>
    """

    key = "load"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        raw = (self.args or "").strip()
        m = re.match(r"(.+?)\s+in\s+(.+)", raw, re.I)
        if not m:
            caller.msg("Usage: load <object> in <station>")
            return
        obj_name, st_name = m.group(1).strip(), m.group(2).strip()
        station = _find_station(caller, st_name)
        if not station:
            caller.msg("No alchemy station like that here.")
            return
        obj = caller.search(obj_name)
        if not obj or obj.location != caller:
            caller.msg("You are not carrying that.")
            return
        if getattr(obj.db, "is_thermos", False):
            ok, msg = load_thermos_into_station(station, obj)
            caller.msg(msg)
            return
        ok, msg = load_chemical_object(station, obj)
        caller.msg(msg)


class CmdBrew(Command):
    """
    Start a brewing batch on a station.

    Usage:
      brew <recipe> on <station>
      brew experiment on <station>   (then: brew experiment confirm on <station>)
    """

    key = "brew"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        raw = (self.args or "").strip()
        m = re.match(r"(.+?)\s+on\s+(.+)", raw, re.I)
        if not m:
            caller.msg("Usage: brew <recipe> on <station> | brew experiment confirm on <station>")
            return
        recipe, st_name = m.group(1).strip().lower(), m.group(2).strip()
        station = _find_station(caller, st_name)
        if not station:
            caller.msg("No alchemy station like that here.")
            return
        if recipe == "experiment":
            caller.msg(
                "Experimenting will consume |rall|n chemicals in the hopper with no guarantee of success. "
                "To proceed: |wbrew experiment confirm on %s|n" % (getattr(station, "key", "station"))
            )
            return
        if recipe == "experiment confirm":
            ok, msg = experiment_brew(caller, station)
            caller.msg(msg)
            return
        ok, msg = start_brew(caller, station, recipe, experiment=False)
        caller.msg(msg)


class CmdTend(Command):
    """Tend the current stage of a batch."""

    key = "tend"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        station = _find_station(caller, self.args or "")
        if not station:
            caller.msg("Tend which station?")
            return
        ok, msg = tend_batch(caller, station)
        caller.msg(msg)


class CmdRefine(Command):
    """Begin refining a loaded specimen."""

    key = "refine"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        station = _find_station(caller, self.args or "")
        if not station:
            caller.msg("Refine at which station?")
            return
        ok, msg = start_refine(caller, station)
        caller.msg(msg)


class CmdAlchemyCheck(Command):
    """Check station status."""

    key = "batchcheck"
    aliases = ["abatch", "checkstation"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        station = _find_station(caller, self.args or "")
        if not station:
            caller.msg("Check which station?")
            return
        caller.msg(station_status_message(station))


class CmdClaim(Command):
    """Claim refined chemicals or finished drugs from a station."""

    key = "claim"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        raw = (self.args or "").strip().lower()
        station = _find_station(caller, self.args or "")
        if not station:
            caller.msg("Claim from which station?")
            return
        reconcile_station(station)
        if getattr(station.db, "refining", False) and getattr(station.db, "refine_ready", False):
            ok, msg = claim_refine(caller, station)
            caller.msg(msg)
            return
        ok, msg = claim_brew(caller, station)
        caller.msg(msg)


class CmdAnalyze(Command):
    """
    Research a chemical at a station (requires it in the hopper).

    Usage:
      analyze <chemical> on <station>
    """

    key = "analyze"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        raw = (self.args or "").strip()
        m = re.match(r"(.+?)\s+on\s+(.+)", raw, re.I)
        if not m:
            caller.msg("Usage: analyze <chemical> on <station>")
            return
        chem_raw, st_name = m.group(1).strip().lower(), m.group(2).strip()
        station = _find_station(caller, st_name)
        if not station:
            caller.msg("No station like that here.")
            return
        chem_key = None
        for ck, data in CHEMICALS.items():
            if ck == chem_raw.replace(" ", "_") or data.get("name", "").lower() == chem_raw:
                chem_key = ck
                break
        if not chem_key:
            chem_key = chem_raw.replace(" ", "_")
        loaded = dict(getattr(station.db, "batch_ingredients", None) or {})
        if chem_key not in loaded or loaded.get(chem_key, 0) <= 0:
            caller.msg("You need that chemical loaded into the station hopper first.")
            return
        secs = random.randint(120, 300)
        caller.msg("You begin analysis. This will take about %s seconds." % secs)

        def _done(cid, ck, station_id):
            from evennia.utils.search import search_object

            ch = search_object("#%s" % cid)
            if not ch:
                return
            ch = ch[0]
            stats = ["intelligence", "perception"]
            tier, _ = ch.roll_check(stats, "alchemy", difficulty=12)
            success = tier != "Failure"
            reveals = bump_analysis(ch, ck, success=success)
            info = CHEMICALS.get(ck, {})
            lines = [
                "Analysis complete.",
                "Name: %s" % info.get("name", ck),
                "Type: %s" % info.get("type", "unknown"),
            ]
            if reveals >= 2:
                lines.append("Description: %s" % info.get("desc", ""))
                specs = specimens_yielding_chemical(ck)
                if specs:
                    from world.alchemy.ingredients import SPECIMENS as SP

                    bits = []
                    for sk in specs:
                        s = SP.get(sk, {})
                        src = s.get("source_type", "?")
                        bits.append("%s (%s)" % (s.get("name", sk), src))
                    lines.append("Sources: " + "; ".join(bits))
                else:
                    lines.append("Sources: no specimen route recorded for this compound.")
            if reveals >= 3:
                uses = drugs_using_chemical(ck)
                if uses:
                    parts = []
                    for dk, cat in uses:
                        parts.append("%s [%s]" % (dk.replace("_", " "), cat or "?"))
                    lines.append("Recipes / street names: " + ", ".join(parts))
                else:
                    lines.append("Recipes: none in your reference data.")
            ch.msg("\n".join(lines))

        delay(secs, _done, caller.id, chem_key, station.id)


class CmdDose(Command):
    """
    Use a drug item from your inventory on yourself or another willing/restrained subject.

    Usage:
      dose <item name>           — use on yourself (matches item in your inventory)
      dose <item> to <character>

    Examples: |wdose lethe|n, |wdose mercurial|n. Drug items do not use |wget|n/|wuse|n; they use |wdose|n.
    """

    key = "dose"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = _command_character(self)
        if not caller:
            self.caller.msg("You must be in character.")
            return
        raw = (self.args or "").strip()
        m = re.match(r"(.+?)\s+to\s+(.+)", raw, re.I)
        target = caller
        item_query = raw
        if m:
            item_query = m.group(1).strip()
            target = caller.search(m.group(2).strip())
            if not target:
                return
        obj = caller.search(item_query)
        if not obj or obj.location != caller:
            caller.msg("You are not carrying that.")
            return
        if not getattr(obj.db, "is_drug_item", False):
            caller.msg("That is not a drug you can dose.")
            return
        dk = getattr(obj.db, "drug_key", None)
        if not dk:
            caller.msg("Unknown substance.")
            return
        doses = int(getattr(obj.db, "doses_remaining", 1) or 1)
        if doses <= 0:
            caller.msg("That is empty.")
            return
        q = int(getattr(obj.db, "drug_quality", 50) or 50)
        susp = bool(getattr(obj.db, "suspicious", False))
        from world.alchemy.effects import apply_drug

        if target != caller:
            from world.rpg.trust import check_trust_or_incapacitated

            ok, _reason = check_trust_or_incapacitated(target, caller, "feed")
            if not ok:
                caller.msg("They don't trust you to administer substances. They need to @trust you to feed.")
                return
        apply_drug(
            target,
            dk,
            quality=q,
            suspicious=susp,
            administrator=caller if target != caller else None,
        )
        doses -= 1
        obj.db.doses_remaining = doses
        if doses <= 0:
            try:
                obj.delete()
            except Exception:
                pass
