# Alchemy stations, thermos, chemicals, drugs — staff/testing.
# Tags: |walchemy|n (all), plus |wstation|n |wchemical|n |wdrug|n |wrecipe|n |wcontainer|n for |wspawnitem list <tag>|n.
# Drug prototypes set drug_key / quality / doses only; long descriptions come from world.alchemy.drugs_registry
# via DrugItem.at_init when db.desc is empty. Override db.desc on the object if you need a custom blurb.

_ALC = ["alchemy"]
_ALC_STATION = ["alchemy", "station"]
_ALC_CHEM = ["alchemy", "chemical"]
_ALC_DRUG = ["alchemy", "drug"]
_ALC_RECIPE = ["alchemy", "recipe"]
_ALC_CONTAINER = ["alchemy", "container"]

ALCHEMY_STATION = {
    "prototype_key": "ALCHEMY_STATION",
    "prototype_tags": _ALC_STATION,
    "key": "alchemy station",
    "typeclass": "typeclasses.alchemy_station.ApothecaryTable",
}

APOTHECARY_TABLE = {
    "prototype_key": "apothecary_table",
    "prototype_tags": _ALC_STATION,
    "key": "apothecary table",
    "typeclass": "typeclasses.alchemy_station.ApothecaryTable",
    "desc": "A heavy wooden table scarred by years of use. Glass vessels, copper tubing, and ceramic dishes are arranged with the careful precision of someone who learned the hard way what happens when reagents touch the wrong surface. A culture rack holds sealed jars of living specimens. The air smells of earth, fungus, and something faintly sweet that might be decay. Stains on the wood tell stories the alchemist doesn't repeat.",
    "attrs": [
        ("station_type", "apothecary"),
        ("station_name", "apothecary table"),
    ],
    "tags": [("alchemy_station", "object_type")],
}

SYNTHESIS_RIG = {
    "prototype_key": "synthesis_rig",
    "prototype_tags": _ALC_STATION,
    "key": "synthesis rig",
    "typeclass": "typeclasses.alchemy_station.SynthesisRig",
    "desc": "A framework of steel and glass bolted to the wall. Burners, condensation coils, crystallization trays, and an electrolysis bath are connected by a tangle of tubing that only makes sense to the person who built it. The air smells of solvents and ozone. A scorch mark on the ceiling suggests a previous experiment reached an unplanned conclusion. The rig hums faintly when the power is on.",
    "attrs": [
        ("station_type", "synthesis"),
        ("station_name", "synthesis rig"),
    ],
    "tags": [("alchemy_station", "object_type")],
}

SPECIMEN_THERMOS = {
    "prototype_key": "SPECIMEN_THERMOS",
    "prototype_tags": _ALC_CONTAINER,
    "key": "specimen thermos",
    "typeclass": "typeclasses.specimen_thermos.SpecimenThermos",
}

CHEM_NEURO_EXTRACT = {
    "prototype_key": "CHEM_NEURO_EXTRACT",
    "prototype_tags": _ALC_CHEM,
    "key": "vial of anima",
    "typeclass": "typeclasses.drug_items.ChemicalItem",
    "attrs": [
        ("chemical_key", "anima"),
        ("amount", 1.0),
        ("is_chemical", True),
    ],
}

CHEM_DISTILLED_BASE = {
    "prototype_key": "CHEM_DISTILLED_BASE",
    "prototype_tags": _ALC_CHEM,
    "key": "bottle of prima materia",
    "typeclass": "typeclasses.drug_items.ChemicalItem",
    "attrs": [
        ("chemical_key", "prima_materia"),
        ("amount", 1.0),
        ("is_chemical", True),
    ],
}

DRUG_LETHE = {
    "prototype_key": "DRUG_LETHE",
    "prototype_tags": _ALC_DRUG,
    "key": "lethe",
    "typeclass": "typeclasses.drug_items.DrugItem",
    "attrs": [
        ("drug_key", "lethe"),
        ("drug_quality", 75),
        ("doses_remaining", 3),
        ("is_drug_item", True),
    ],
}

DRUG_MERCURIAL = {
    "prototype_key": "DRUG_MERCURIAL",
    "prototype_tags": _ALC_DRUG,
    "key": "mercurial",
    "typeclass": "typeclasses.drug_items.DrugItem",
    "attrs": [
        ("drug_key", "mercurial"),
        ("drug_quality", 60),
        ("doses_remaining", 2),
        ("is_drug_item", True),
    ],
}

RECIPE_LETHE = {
    "prototype_key": "RECIPE_LETHE",
    "prototype_tags": _ALC_RECIPE,
    "key": "data chip: Lethe",
    "typeclass": "typeclasses.items.Item",
    "desc": "A chipped lesson in pink chemistry.",
}
