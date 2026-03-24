"""
Rank tables per faction type. Each rank has a number (1 = lowest),
a display name, a permission level, and a weekly pay amount.

Permission levels on rank rows are used for flavor and future systems.
At the registry terminal today:
    0 = member (view own info, collect pay)
    1 = officer (reserved for future use)
    2 = commander (reserved for future use; not used for enlist/promote/demote/discharge)
    3 = leadership — enlist, promote, demote, discharge, and set rank require this level
        (or staff) at the terminal.

Staff/Builders bypass permission levels entirely — they can do everything
at any terminal regardless of faction membership.
"""

RANK_TABLES = {
    "imperium_ranks": {
        1: {"name": "Recruit", "permission": 0, "pay": 150},
        2: {"name": "Patrol Officer", "permission": 0, "pay": 250},
        3: {"name": "Sergeant", "permission": 1, "pay": 400},
        4: {"name": "Lieutenant", "permission": 2, "pay": 600},
        5: {"name": "Captain", "permission": 2, "pay": 850},
        6: {"name": "Commander", "permission": 3, "pay": 1200},
        7: {"name": "Marshal", "permission": 3, "pay": 1800},
    },
    "inquisitorate_ranks": {
        1: {"name": "Acolyte", "permission": 0, "pay": 200},
        2: {"name": "Interrogator", "permission": 0, "pay": 350},
        3: {"name": "Inquisitor", "permission": 1, "pay": 600},
        4: {"name": "Senior Inquisitor", "permission": 2, "pay": 900},
        5: {"name": "High Inquisitor", "permission": 3, "pay": 1500},
    },
    "guild_ranks": {
        1: {"name": "Apprentice", "permission": 0, "pay": 100},
        2: {"name": "Journeyman", "permission": 0, "pay": 200},
        3: {"name": "Artisan", "permission": 0, "pay": 350},
        4: {"name": "Senior Artisan", "permission": 1, "pay": 500},
        5: {"name": "Foreman", "permission": 2, "pay": 700},
        6: {"name": "Guild Officer", "permission": 2, "pay": 950},
        7: {"name": "Guild Master", "permission": 3, "pay": 1500},
    },
    "gang_ranks": {
        1: {"name": "Runner", "permission": 0, "pay": 50},
        2: {"name": "Soldier", "permission": 0, "pay": 100},
        3: {"name": "Enforcer", "permission": 1, "pay": 200},
        4: {"name": "Lieutenant", "permission": 2, "pay": 350},
        5: {"name": "Boss", "permission": 3, "pay": 600},
    },
}

# Validate all rank tables at import time via pydantic.
try:
    from world.rpg.factions.schemas import validate_rank_tables as _validate_rank_tables
    RANK_TABLES = _validate_rank_tables(RANK_TABLES)
except Exception as _rank_schema_exc:
    import logging as _logging
    _logging.getLogger("evennia").warning(
        f"[factions] Rank table schema validation failed, using raw RANK_TABLES: {_rank_schema_exc}"
    )


def get_rank_table(table_key):
    """Return the rank table dict for a faction type."""
    return RANK_TABLES.get(table_key, {})


def get_ranks_at_permission(table_key, min_permission):
    """Return list of (rank_number, info) tuples at or above min_permission, sorted by rank."""
    table = get_rank_table(table_key)
    return [(num, info) for num, info in sorted(table.items()) if info.get("permission", 0) >= min_permission]


def get_rank_info(table_key, rank_number):
    """Return rank info dict for a specific rank in a table. Returns None if invalid."""
    table = get_rank_table(table_key)
    return table.get(rank_number)


def get_max_rank(table_key):
    """Return the highest rank number in a table."""
    table = get_rank_table(table_key)
    return max(table.keys()) if table else 1


try:
    from num2words import num2words as _n2w
    _NUM2WORDS_AVAILABLE = True
except ImportError:
    _NUM2WORDS_AVAILABLE = False


def get_rank_ordinal(rank_number: int) -> str:
    """Return an ordinal word for a rank number, e.g. 3 -> 'third rank'."""
    if _NUM2WORDS_AVAILABLE:
        try:
            return f"{_n2w(int(rank_number), to='ordinal')} rank"
        except Exception:
            pass
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    suffix = suffixes.get(rank_number % 10, "th")
    if 11 <= (rank_number % 100) <= 13:
        suffix = "th"
    return f"{rank_number}{suffix} rank"


def get_rank_name(table_key, rank_number):
    """Return display name for a rank. Returns 'Unknown' if not found."""
    info = get_rank_info(table_key, rank_number)
    return info["name"] if info else "Unknown"


def get_rank_permission(table_key, rank_number):
    """Return permission level for a rank. Returns 0 if not found."""
    info = get_rank_info(table_key, rank_number)
    return info.get("permission", 0) if info else 0


def get_rank_pay(table_key, rank_number):
    """Return weekly pay amount for a rank. Returns 0 if not found."""
    info = get_rank_info(table_key, rank_number)
    return info.get("pay", 0) if info else 0
