"""
Recipe matching, known-recipe checks, and analysis bookkeeping.
"""

from world.alchemy import DRUGS
from world.alchemy.ingredients import SPECIMENS


def character_knows_recipe(character, recipe_key):
    known = list(getattr(character.db, "known_recipes", None) or [])
    return recipe_key in known


def chemicals_sufficient(loaded, recipe_chemicals, eps=0.001):
    """True if loaded dict has at least recipe amounts for each key."""
    for ck, amt in recipe_chemicals.items():
        have = float(loaded.get(ck, 0.0) or 0.0)
        if have + eps < float(amt):
            return False
    return True


def consume_recipe_chemicals(loaded, recipe_chemicals):
    """Subtract recipe amounts from loaded dict (mutates)."""
    for ck, amt in recipe_chemicals.items():
        loaded[ck] = max(0.0, float(loaded.get(ck, 0.0) or 0.0) - float(amt))


def find_experiment_match(loaded):
    """
    If loaded chemicals exactly match one recipe's needs (each loaded >= required,
    and no extra unused chemicals), return drug_key. Otherwise first full match by
    minimal excess. For 'experiment', accept any drug whose recipe is subset-satisfied
    and total loaded mass is close to sum of recipe (within tolerance).
    """
    best = None
    best_score = None
    for drug_key, drug in DRUGS.items():
        req = drug.get("recipe", {}).get("chemicals") or {}
        if not req:
            continue
        if not chemicals_sufficient(loaded, req):
            continue
        # Penalize leftover chemicals
        leftover = dict(loaded)
        consume_recipe_chemicals(leftover, req)
        extra = sum(max(0.0, v) for v in leftover.values())
        score = extra
        if best_score is None or score < best_score:
            best_score = score
            best = drug_key
    return best


def get_analysis_state(character):
    """Per-chemical analysis progress for research."""
    return dict(getattr(character.db, "alchemy_analysis", None) or {})


def specimens_yielding_chemical(chemical_key):
    """Specimen keys whose refine output is this chemical."""
    return [sk for sk, sp in SPECIMENS.items() if sp.get("yield_chemical") == chemical_key]


def drugs_using_chemical(chemical_key):
    """List of (drug_key, drug_category) for recipes that require this chemical."""
    out = []
    for dk, drug in DRUGS.items():
        req = drug.get("recipe", {}).get("chemicals") or {}
        if chemical_key in req:
            out.append((dk, drug.get("drug_category")))
    return out


def bump_analysis(character, chemical_key, success=True):
    data = get_analysis_state(character)
    entry = data.get(chemical_key, {"reveals": 0, "attempts": 0})
    entry["attempts"] = entry.get("attempts", 0) + 1
    if success:
        entry["reveals"] = min(3, entry.get("reveals", 0) + 1)
    data[chemical_key] = entry
    character.db.alchemy_analysis = data
    return entry["reveals"]
