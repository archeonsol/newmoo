"""
Specimen and chemical registries for alchemy. Specimens are collected raw;
chemicals are refined outputs used in drug recipes.

Organ harvest: butcher code must set ``db.organ_specimen_key`` on harvested organ items
to the specimen key (e.g. ``"adrenal_fluid"``) that matches ``SPECIMENS`` entries whose
``organ_tag`` field matches the organ (e.g. ``"adrenal"``). Collection matches
``organ_specimen_key`` to ``SPECIMENS`` keys, not ``organ_tag`` on the item.
"""
import time

SPECIMENS = {
    "sewer_water": {
        "key": "sewer_water",
        "name": "Sewer Water",
        "desc": "Murky fluid collected from the drainage system. Smells exactly how you'd expect.",
        "source_type": "room",
        "rarity": "common",
        "yield_chemical": "ferment",
        "refine_difficulty": 8,
        "refine_yield_base": 0.6,
        "refine_station": "apothecary",
    },
    "fungal_bloom": {
        "key": "fungal_bloom",
        "name": "Fungal Bloom",
        "desc": "Bioluminescent spores scraped from the Sink's grow-walls. They pulse faintly in the dark.",
        "source_type": "room",
        "rarity": "common",
        "yield_chemical": "mycelium_essence",
        "refine_difficulty": 10,
        "refine_yield_base": 0.5,
        "refine_station": "apothecary",
    },
    "coolant_runoff": {
        "key": "coolant_runoff",
        "name": "Coolant Runoff",
        "desc": "Blue-green fluid leaking from industrial cooling systems. Slightly viscous. Do not taste.",
        "source_type": "room",
        "rarity": "common",
        "yield_chemical": "aqua_fortis",
        "refine_difficulty": 6,
        "refine_yield_base": 0.7,
        "refine_station": "synthesis",
    },
    "rust_scrapings": {
        "key": "rust_scrapings",
        "name": "Rust Scrapings",
        "desc": "Iron oxide collected from corroded infrastructure. Powdery, reddish-brown.",
        "source_type": "room",
        "rarity": "common",
        "yield_chemical": "iron_salt",
        "refine_difficulty": 5,
        "refine_yield_base": 0.8,
        "refine_station": "synthesis",
    },
    "vent_condensation": {
        "key": "vent_condensation",
        "name": "Vent Condensation",
        "desc": "Moisture collected from deep ventilation shafts. Pure by undercity standards. Faintly acidic.",
        "source_type": "room",
        "rarity": "common",
        "yield_chemical": "prima_materia",
        "refine_difficulty": 4,
        "refine_yield_base": 0.9,
        "refine_station": "synthesis",
    },
    "tunnel_lichen": {
        "key": "tunnel_lichen",
        "name": "Tunnel Lichen",
        "desc": "Photosynthetic growth found in deep, damp tunnels. Emits a faint green luminescence. Samples degrade quickly once removed from substrate.",
        "source_type": "room",
        "rarity": "uncommon",
        "yield_chemical": "phosphor",
        "refine_difficulty": 14,
        "refine_yield_base": 0.4,
        "refine_station": "apothecary",
    },
    "chrome_residue": {
        "key": "chrome_residue",
        "name": "Chrome Residue",
        "desc": "Metallic film scraped from a cybersurgery site. Contains trace amounts of biocompatible alloy.",
        "source_type": "room",
        "rarity": "uncommon",
        "yield_chemical": "quicksilver",
        "refine_difficulty": 18,
        "refine_yield_base": 0.3,
        "refine_station": "synthesis",
    },
    "corpse_bile": {
        "key": "corpse_bile",
        "name": "Corpse Bile",
        "desc": "Extracted from a cadaver's digestive tract. Yellow-green, viscous, biologically active.",
        "source_type": "corpse",
        "rarity": "uncommon",
        "yield_chemical": "vitriol_salt",
        "refine_difficulty": 12,
        "refine_yield_base": 0.5,
        "refine_station": "apothecary",
    },
    "adrenal_fluid": {
        "key": "adrenal_fluid",
        "name": "Adrenal Fluid",
        "desc": "Harvested from the adrenal glands of a corpse. Yellowish, slightly warm. The body's own combat drug.",
        "source_type": "organ",
        "organ_tag": "adrenal",
        "rarity": "rare",
        "yield_chemical": "ichor",
        "refine_difficulty": 16,
        "refine_yield_base": 0.35,
        "refine_station": "apothecary",
    },
    "cerebrospinal_fluid": {
        "key": "cerebrospinal_fluid",
        "name": "Cerebrospinal Fluid",
        "desc": "Drawn from the spinal column. Clear, faintly iridescent. Carries neural chemistry.",
        "source_type": "organ",
        "organ_tag": "spinal",
        "rarity": "rare",
        "yield_chemical": "anima",
        "refine_difficulty": 20,
        "refine_yield_base": 0.25,
        "refine_station": "apothecary",
    },
    "clone_nutrient": {
        "key": "clone_nutrient",
        "name": "Clone Nutrient",
        "desc": "Growth medium drained from a cloning vat. Contains stem cell residue and synthetic growth factors. Controlled substance — Sepulchre property.",
        "source_type": "room",
        "rarity": "rare",
        "yield_chemical": "alkahest",
        "refine_difficulty": 22,
        "refine_yield_base": 0.2,
        "refine_station": "apothecary",
    },
    "anomalous_deposit": {
        "key": "anomalous_deposit",
        "name": "Anomalous Deposit",
        "desc": "Unclassified material collected from sites of structural decay. Absorbs light at the edges. Spectral analysis inconclusive. Handle with extreme caution.",
        "source_type": "room",
        "rarity": "exotic",
        "yield_chemical": "nigredo_salt",
        "refine_difficulty": 28,
        "refine_yield_base": 0.15,
        "refine_station": "synthesis",
    },
    "live_blood": {
        "key": "live_blood",
        "name": "Live Blood Sample",
        "desc": "Fresh blood from a living subject. Still warm. Still carrying whatever they had in their system.",
        "source_type": "character",
        "rarity": "uncommon",
        "yield_chemical": "sanguine",
        "refine_difficulty": 10,
        "refine_yield_base": 0.6,
        "refine_station": "apothecary",
    },
    "spinal_tap": {
        "key": "spinal_tap",
        "name": "Spinal Tap Sample",
        "desc": "Cerebrospinal fluid drawn from a living subject. The extraction is not pleasant for them.",
        "source_type": "character",
        "rarity": "rare",
        "yield_chemical": "anima_viva",
        "refine_difficulty": 24,
        "refine_yield_base": 0.3,
        "refine_station": "apothecary",
    },
    "arc_crystal": {
        "key": "arc_crystal",
        "name": "Arc Crystal",
        "desc": "Crystallized residue from a sustained electrical discharge. Formed naturally in the power plant's waste chambers.",
        "source_type": "room",
        "rarity": "rare",
        "yield_chemical": "galvanic_salt",
        "refine_difficulty": 18,
        "refine_yield_base": 0.3,
        "refine_station": "synthesis",
    },
    "render_fat": {
        "key": "render_fat",
        "name": "Rendered Fat",
        "desc": "Animal or human fat processed by the Renderers' Covenant. Greasy, foul-smelling, chemically versatile.",
        "source_type": "organ",
        "organ_tag": "fat",
        "rarity": "common",
        "yield_chemical": "tallow",
        "refine_difficulty": 6,
        "refine_yield_base": 0.7,
        "refine_station": "apothecary",
    },
}

CHEMICALS = {
    "ferment": {"name": "Ferment", "type": "biological", "desc": "Living culture in suspension. The base of all biological reactions."},
    "mycelium_essence": {"name": "Mycelium Essence", "type": "psychoactive", "desc": "Concentrated fungal compound. Opens doors in the mind that have no hinges."},
    "aqua_fortis": {"name": "Aqua Fortis", "type": "chemical", "desc": "Strong water. Dissolves what shouldn't dissolve."},
    "iron_salt": {"name": "Iron Salt", "type": "mineral", "desc": "Crystallized iron. Binds, strengthens, endures."},
    "prima_materia": {"name": "Prima Materia", "type": "neutral", "desc": "The first matter. Clean, empty, waiting to become something."},
    "phosphor": {"name": "Phosphor", "type": "biological", "desc": "The light-bearer. Bioluminescent compound that reacts to neural chemistry."},
    "quicksilver": {"name": "Quicksilver", "type": "tech", "desc": "Liquid metal in biocompatible suspension. The bridge between chrome and meat."},
    "vitriol_salt": {"name": "Vitriol Salt", "type": "biological", "desc": "Concentrated digestive fury. Breaks down what the body built."},
    "ichor": {"name": "Ichor", "type": "hormonal", "desc": "The blood that isn't blood. Raw adrenal extract. What the body saves for emergencies."},
    "anima": {"name": "Anima", "type": "neural", "desc": "Soul in solution. Neural chemistry stripped from the source and suspended."},
    "alkahest": {"name": "Alkahest", "type": "biological", "desc": "The universal solvent. Growth factors that rebuild what was broken."},
    "nigredo_salt": {"name": "Nigredo Salt", "type": "exotic", "desc": "Crystallized void. It shouldn't be solid. It shouldn't be anything."},
    "sanguine": {"name": "Sanguine", "type": "biological", "desc": "Concentrated blood. The oxygen-carrier. The life-medium."},
    "anima_viva": {"name": "Anima Viva", "type": "neural", "desc": "Living soul. Fresh neural chemistry. More potent because it was taken, not found."},
    "galvanic_salt": {"name": "Galvanic Salt", "type": "mineral", "desc": "Charged mineral. Conducts, catalyzes, and wakes the dead — or close enough."},
    "tallow": {"name": "Tallow", "type": "biological", "desc": "Rendered fat. The oldest delivery medium. Carries what needs carrying."},
}


def can_collect_from_character(collector, target, specimen_key):
    """
    Check if collector can take a specimen from target.
    Requires: target is restrained (grappled by collector), sedated, consenting, or flatlined.
    Spinal tap requires medicine skill.
    """
    from world.death import is_flatlined

    spec = SPECIMENS.get(specimen_key)
    if not spec or spec.get("source_type") != "character":
        return False, "This specimen isn't collected from people."
    from world.rpg.trust import check_trust

    consenting = check_trust(target, collector, "collect")
    sedated = float(getattr(target.db, "sedated_until", 0.0) or 0.0) > time.time()
    grappled = getattr(target.db, "grappled_by", None) == collector
    flatlined = is_flatlined(target)
    if not any([consenting, sedated, grappled, flatlined]):
        return False, "The subject must be restrained, sedated, or willing."
    if specimen_key == "spinal_tap":
        skill = collector.get_skill_level("medicine") if hasattr(collector, "get_skill_level") else 0
        if (skill or 0) < 40:
            return False, "You lack the medical knowledge for a spinal extraction."
    return True, "Collection possible."
