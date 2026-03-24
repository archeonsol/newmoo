"""
Pydantic schemas for faction data validation.

These schemas validate faction definitions, rank table entries, and rank tables
at import time. A typo in a faction key, missing required field, or invalid
permission level will raise a ValidationError immediately rather than causing
a silent runtime failure deep in membership checks.

All schemas use model_dump() to return plain dicts, so all existing call sites
that access fdata["key"], fdata["tag"], etc. are unchanged.
"""

from pydantic import BaseModel, field_validator, model_validator


class RankEntrySchema(BaseModel):
    """A single rank row: name, permission level, and weekly pay."""
    name: str
    permission: int
    pay: int

    @field_validator("permission")
    @classmethod
    def permission_in_range(cls, v: int) -> int:
        if v < 0 or v > 3:
            raise ValueError(f"permission must be 0–3, got {v}")
        return v

    @field_validator("pay")
    @classmethod
    def pay_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"pay must be >= 0, got {v}")
        return v


class RankTableSchema(BaseModel):
    """
    A complete rank table: a dict of {rank_number: RankEntrySchema}.
    Rank numbers must be positive integers.
    """
    ranks: dict[int, RankEntrySchema]

    @model_validator(mode="before")
    @classmethod
    def coerce_from_dict(cls, data):
        """Accept a plain {int: dict} rank table directly."""
        if isinstance(data, dict) and "ranks" not in data:
            return {"ranks": data}
        return data

    @field_validator("ranks")
    @classmethod
    def ranks_non_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("Rank table must have at least one rank.")
        for k in v:
            if not isinstance(k, int) or k < 1:
                raise ValueError(f"Rank numbers must be positive integers, got {k!r}")
        return v


class FactionSchema(BaseModel):
    """
    Schema for a single faction definition.
    All fields are required except tag_category (defaults to 'faction')
    and default_rank (defaults to 1).
    """
    key: str
    name: str
    short_name: str
    description: str
    color: str
    tag: str
    tag_category: str = "faction"
    ranks: str
    default_rank: int = 1
    hq_room_tag: str
    terminal_prototype: str

    @field_validator("key")
    @classmethod
    def key_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("tag")
    @classmethod
    def tag_lowercase(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("default_rank")
    @classmethod
    def default_rank_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError(f"default_rank must be >= 1, got {v}")
        return v


def validate_factions(raw_factions: dict) -> dict:
    """
    Validate a raw FACTIONS dict and return a plain-dict version.

    Each value is validated through FactionSchema. Returns a new dict with
    the same keys and model_dump() plain-dict values. Raises ValidationError
    on the first invalid entry.

    Args:
        raw_factions: The raw FACTIONS dict from factions/__init__.py.

    Returns:
        dict: Validated factions dict (plain dicts, all existing call sites unchanged).
    """
    validated = {}
    for k, v in raw_factions.items():
        schema = FactionSchema(**v)
        validated[schema.key] = schema.model_dump()
    return validated


def validate_rank_tables(raw_tables: dict) -> dict:
    """
    Validate a raw RANK_TABLES dict and return a plain-dict version.

    Args:
        raw_tables: The raw RANK_TABLES dict from factions/ranks.py.

    Returns:
        dict: Validated rank tables dict (plain dicts).
    """
    validated = {}
    for table_key, table_data in raw_tables.items():
        schema = RankTableSchema.model_validate(table_data)
        validated[table_key] = {
            rank_num: entry.model_dump()
            for rank_num, entry in schema.ranks.items()
        }
    return validated
