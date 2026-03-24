"""
Names for |wspawnitem list <category> [subtag]|n — must match |wprototype_tags|n on dicts.

Single word: prototypes must include that tag. Two words: must include both tags.
Plural forms (e.g. |wdrugs|n → |wdrug|n) are accepted for list filters.
"""

# Shown after a full |wspawnitem list|n
LIST_CATEGORY_HELP = (
    "|wCategories|n (use |wspawnitem list <category>|n or |wspawnitem list <cat> <subtag>|n): "
    "|wcombat|n, |wweapon|n, |warmor|n, |wsurvival|n, |wfood|n, |wdrink|n, |walcohol|n, "
    "|wmedical|n, |wtailoring|n, |wperformance|n, |wconsumable|n, "
    "|walchemy|n, |wdrug|n, |wchemical|n, |wstation|n, |wrecipe|n, |wcontainer|n, |wcyberware|n, "
    "|wvehicle|n (|wground|n, |wmotorcycle|n, |waerial|n)"
)

# User input (lowercase) -> canonical prototype_tag for filtering
SPAWNITEM_TAG_ALIASES = {
    "drugs": "drug",
    "chemicals": "chemical",
    "stations": "station",
    "recipes": "recipe",
    "containers": "container",
    "vehicles": "vehicle",
    "bikes": "motorcycle",
    "bike": "motorcycle",
    "av": "aerial",
    "avs": "aerial",
}

# Valid filter tokens (lowercase). Used for friendlier errors; unknown tags still filter to empty.
KNOWN_LIST_TAGS = frozenset(
    {
        "combat",
        "weapon",
        "armor",
        "survival",
        "food",
        "drink",
        "alcohol",
        "medical",
        "tailoring",
        "performance",
        "consumable",
        "alchemy",
        "drug",
        "chemical",
        "station",
        "recipe",
        "container",
        "cyberware",
        "vehicle",
        "ground",
        "motorcycle",
        "aerial",
        *SPAWNITEM_TAG_ALIASES.keys(),
    }
)
