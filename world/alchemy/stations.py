"""
Alchemy station state: refine pipeline, batch brew stages, reconcile timers after reload.
"""
import time

from evennia.utils import logger

from world.alchemy import DRUGS
from world.alchemy.crafting import (
    calculate_refine_duration,
    calculate_refine_yield,
    final_dose_yield,
    resolve_tend_skill,
)
from world.alchemy.recipes import (
    chemicals_sufficient,
    consume_recipe_chemicals,
    character_knows_recipe,
    find_experiment_match,
)


def reconcile_station(station):
    """Update *_ready flags from persisted timestamps (call on load and periodically)."""
    now = time.time()
    db = station.db
    # Refining
    if getattr(db, "refining", False) and getattr(db, "refine_started", None):
        spec_key = db.refine_specimen
        dur = int(getattr(db, "refine_duration", 0) or 0)
        if dur <= 0 and spec_key:
            dur = 120
        started = float(db.refine_started)
        db.refine_ready = (now - started) >= dur
    # Batch stage timer
    if getattr(db, "batch_active", False):
        recipe_key = db.batch_recipe
        drug = DRUGS.get(recipe_key) if recipe_key else None
        stages = drug.get("stages", []) if drug else []
        idx = int(getattr(db, "batch_stage", 0) or 0)
        started = getattr(db, "batch_stage_started", None)
        if started is not None and idx < len(stages):
            dur = int(stages[idx].get("duration_seconds", 0) or 0)
            db.batch_stage_ready = (now - float(started)) >= dur
        elif idx >= len(stages) and len(stages) > 0:
            db.batch_stage_ready = True


def _station_type(station):
    return getattr(station.db, "station_type", None) or getattr(type(station), "station_type", None) or "apothecary"


def start_refine(character, station):
    """Begin refining loaded specimen thermos contents."""
    reconcile_station(station)
    db = station.db
    if getattr(db, "batch_active", False):
        return False, "A batch is already running."
    if getattr(db, "refining", False) and not getattr(db, "refine_ready", False):
        return False, "Something is already refining."
    spec = getattr(db, "refine_specimen", None)
    if not spec:
        return False, "There is no specimen loaded to refine."
    from world.alchemy.ingredients import SPECIMENS

    if spec not in SPECIMENS:
        return False, "Invalid specimen state."
    sp_def = SPECIMENS[spec]
    required_station = sp_def.get("refine_station", "apothecary")
    actual_station = _station_type(station)
    if required_station != actual_station:
        station_names = {"apothecary": "Apothecary Table", "synthesis": "Synthesis Rig"}
        return False, "This specimen must be refined at a %s." % station_names.get(
            required_station, required_station
        )
    dur = calculate_refine_duration(character, spec)
    db.refining = True
    db.refine_started = time.time()
    db.refine_duration = dur
    db.refine_ready = False
    return True, f"Refining started. It will be ready in about {dur} seconds."


def claim_refine(character, station):
    """Produce chemical item from completed refine."""
    reconcile_station(station)
    db = station.db
    if not getattr(db, "refining", False):
        return False, "Nothing is refining."
    if not getattr(db, "refine_ready", False):
        return False, "The refine is not ready yet."
    spec_key = db.refine_specimen
    from world.alchemy.ingredients import SPECIMENS

    spec = SPECIMENS.get(spec_key)
    if not spec:
        _clear_refine(station)
        return False, "Bad specimen data. Refine cleared."
    chem_key = spec["yield_chemical"]
    amt = calculate_refine_yield(character, spec_key)
    try:
        from evennia import create_object

        obj = create_object(
            "typeclasses.drug_items.ChemicalItem",
            key=SPECIMENS.get(spec_key, {}).get("name", "chemical"),
            location=station,
        )
        obj.db.chemical_key = chem_key
        obj.db.amount = float(amt)
        obj.db.is_chemical = True
        obj.db.desc = f"A container of refined {chem_key.replace('_', ' ')}."
    except Exception as err:
        logger.log_trace(f"alchemy claim_refine create: {err}")
        return False, "Could not create chemical output."
    _clear_refine(station)
    return True, f"You collect the refined product into a container."


def _clear_refine(station):
    station.db.refining = False
    station.db.refine_specimen = None
    station.db.refine_started = None
    station.db.refine_duration = 0
    station.db.refine_ready = False


def experiment_brew(character, station):
    """
    Try to match loaded chemicals to a recipe; learn recipe if new; start batch.
    """
    reconcile_station(station)
    loaded = dict(getattr(station.db, "batch_ingredients", None) or {})
    m = find_experiment_match(loaded)
    if not m:
        station.db.batch_ingredients = {}
        return False, "Nothing viable forms. The reagents are wasted."
    known = list(getattr(character.db, "known_recipes", None) or [])
    learned = False
    if m not in known:
        known.append(m)
        character.db.known_recipes = known
        learned = True
    ok, msg = start_brew(character, station, m, experiment=False)
    if learned and ok:
        msg = "You stumble onto a viable reaction. " + msg
    return ok, msg


def start_brew(character, station, recipe_key, experiment=False):
    """Lock recipe and consume loaded chemicals; start stage 0 timer."""
    reconcile_station(station)
    db = station.db
    if getattr(db, "refining", False):
        return False, "Finish or claim the refine first."
    if getattr(db, "batch_active", False):
        return False, "A batch is already active."
    drug = DRUGS.get(recipe_key)
    if not drug:
        return False, "Unknown recipe."
    required_station = drug.get("recipe", {}).get("brew_station", "apothecary")
    actual_station = _station_type(station)
    if required_station != actual_station:
        station_names = {"apothecary": "Apothecary Table", "synthesis": "Synthesis Rig"}
        return False, "This recipe requires a %s." % station_names.get(required_station, required_station)
    if not experiment and not character_knows_recipe(character, recipe_key):
        return False, "You do not know that recipe."
    req = drug.get("recipe", {}).get("chemicals") or {}
    loaded = dict(getattr(db, "batch_ingredients", None) or {})
    if not chemicals_sufficient(loaded, req):
        return False, "You do not have the required chemicals loaded."
    consume_recipe_chemicals(loaded, req)
    db.batch_ingredients = loaded
    db.batch_active = True
    db.batch_owner = character.id
    db.batch_recipe = recipe_key
    db.batch_quality = 100
    db.batch_stage = 0
    db.batch_stage_started = time.time()
    db.batch_stage_ready = False
    db.batch_yield = 0
    stages = drug.get("stages", [])
    if not stages:
        return False, "Invalid recipe stages."
    # First stage must elapse before tend
    return True, f"Batch started: {drug.get('name', recipe_key)}. Wait for the first stage to finish, then tend the station."


def tend_batch(character, station):
    """If stage ready, resolve skill and advance or complete."""
    reconcile_station(station)
    db = station.db
    if not getattr(db, "batch_active", False):
        return False, "No active batch."
    if not getattr(db, "batch_stage_ready", False):
        recipe_key = db.batch_recipe
        drug = DRUGS.get(recipe_key) or {}
        idx = int(db.batch_stage or 0)
        stages = drug.get("stages", [])
        started = db.batch_stage_started
        if idx < len(stages) and started:
            elapsed = time.time() - float(started)
            need = int(stages[idx].get("duration_seconds", 0) or 0)
            left = max(0, need - elapsed)
            return False, f"This stage is not ready. About {int(left)} seconds left."
        return False, "This stage is not ready yet."
    recipe_key = db.batch_recipe
    drug = DRUGS.get(recipe_key)
    if not drug:
        _reset_batch(station)
        return False, "Invalid batch. Cleared."
    stages = drug.get("stages", [])
    idx = int(db.batch_stage or 0)
    if idx >= len(stages):
        return False, "Batch already finished tending."
    stage = stages[idx]
    delta, tier = resolve_tend_skill(character, stage)
    q = int(db.batch_quality or 100) + delta
    db.batch_quality = max(0, min(100, q))
    desc = stage.get("tend_desc", "You work the batch.")
    character.msg(desc)
    # Advance
    if idx + 1 < len(stages):
        db.batch_stage = idx + 1
        db.batch_stage_started = time.time()
        db.batch_stage_ready = False
        reconcile_station(station)
        return True, f"The batch moves to the next stage ({tier}). Quality is now {db.batch_quality}."
    # Complete
    quality = int(db.batch_quality or 0)
    base_yield = int(drug.get("recipe", {}).get("base_yield", 1))
    doses = final_dose_yield(base_yield, quality)
    db.batch_yield = doses
    if quality <= 0:
        _reset_batch(station)
        return True, "The batch is ruined. Whatever this is, it's not what you were making. It's nothing."
    _spawn_drug_items(station, character, recipe_key, quality, doses)
    _reset_batch(station)
    return True, f"Batch complete ({tier}). You have {doses} dose(s) ready to claim from the station."


def _spawn_drug_items(station, character, drug_key, quality, doses):
    """Create drug items on station for claim."""
    if doses <= 0:
        return
    try:
        from evennia import create_object

        drug = DRUGS.get(drug_key, {})
        name = drug.get("name", drug_key)
        obj = create_object(
            "typeclasses.drug_items.DrugItem",
            key=name.lower(),
            location=station,
        )
        obj.db.drug_key = drug_key
        obj.db.drug_quality = quality
        obj.db.doses_remaining = doses
        obj.db.crafted_by = character.id
        obj.db.suspicious = quality < 20
        obj.db.is_drug_item = True
        from typeclasses.drug_items import sync_drug_item_desc_from_registry

        sync_drug_item_desc_from_registry(obj)
    except Exception as err:
        logger.log_trace(f"_spawn_drug_items: {err}")


def claim_brew(character, station):
    """Move finished drug items from station to character (anyone can claim)."""
    reconcile_station(station)
    try:
        from typeclasses.drug_items import DrugItem
    except Exception:
        DrugItem = None
    found = [
        o
        for o in station.contents
        if getattr(o.db, "is_drug_item", False) or (DrugItem and isinstance(o, DrugItem))
    ]
    if not found:
        return False, "There is nothing to claim here."
    n = 0
    for o in found:
        try:
            o.location = character
            n += 1
        except Exception as err:
            logger.log_trace(f"claim_brew move: {err}")
    return True, f"You claim {n} item(s) from the station."


def _reset_batch(station):
    station.db.batch_active = False
    station.db.batch_owner = None
    station.db.batch_recipe = None
    station.db.batch_quality = 100
    station.db.batch_stage = 0
    station.db.batch_stage_ready = False
    station.db.batch_stage_started = None
    station.db.batch_yield = 0


def load_thermos_into_station(station, thermos):
    """Drain thermos into station for refining."""
    reconcile_station(station)
    if getattr(station.db, "batch_active", False) or getattr(station.db, "refining", False):
        return False, "The station is busy."
    if getattr(station.db, "refine_specimen", None):
        return False, "There is already a specimen in the refining chamber. Refine or clear it first."
    spec = getattr(thermos.db, "specimen", None)
    if not spec:
        return False, "The thermos is empty."
    station.db.refine_specimen = spec
    thermos.db.specimen = None
    thermos.db.specimen_amount = 0.0
    return True, "Specimen decanted into the refining chamber."


def load_chemical_object(station, obj):
    """Merge a ChemicalItem into batch_ingredients and destroy the object."""
    if not getattr(obj.db, "is_chemical", False):
        return False, "That is not a refined chemical container."
    key = getattr(obj.db, "chemical_key", None)
    if not key:
        return False, "Invalid chemical."
    amt = float(getattr(obj.db, "amount", 1.0) or 1.0)
    ing = dict(getattr(station.db, "batch_ingredients", None) or {})
    ing[key] = float(ing.get(key, 0.0) or 0.0) + amt
    station.db.batch_ingredients = ing
    try:
        obj.delete()
    except Exception:
        pass
    return True, "Chemical transferred to the station hopper."


def station_status_message(station):
    """Human-readable status for check command."""
    reconcile_station(station)
    lines = []
    db = station.db
    name = getattr(db, "station_name", "alchemy station")
    lines.append(f"{name}:")
    if getattr(db, "refining", False):
        left = 0
        if db.refine_started and db.refine_duration:
            elapsed = time.time() - float(db.refine_started)
            left = max(0, int(db.refine_duration) - int(elapsed))
        lines.append(f"  Refining: specimen {db.refine_specimen}. Ready: {bool(db.refine_ready)} (~{left}s left).")
    if getattr(db, "batch_active", False):
        drug = DRUGS.get(db.batch_recipe or "")
        stg = int(db.batch_stage or 0)
        stages = drug.get("stages", []) if drug else []
        lines.append(f"  Batch: {db.batch_recipe} stage {stg + 1}/{len(stages)} quality {db.batch_quality}. Stage ready: {bool(db.batch_stage_ready)}.")
        loaded = getattr(db, "batch_ingredients", {}) or {}
        if loaded:
            chem_lines = ["%s: %.2f" % (k.replace("_", " "), v) for k, v in loaded.items() if float(v or 0) > 0]
            if chem_lines:
                lines.append("  Hopper: " + ", ".join(chem_lines))
    if not getattr(db, "refining", False) and not getattr(db, "batch_active", False):
        lines.append("  Idle.")
    return "\n".join(lines)
