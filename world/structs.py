"""
Typed data structures for frequently-read dict schemas.

Uses msgspec.Struct for fast, typed conversion to/from the plain dicts
stored in character.db. The storage format is unchanged — still plain dicts.

Public API:
    structure_injury(raw_dict)     -> InjuryEntry or None
    unstructure_injury(entry)      -> dict
    structure_transaction(raw)     -> TransactionEntry or None
    unstructure_transaction(entry) -> dict
"""

import time
import uuid

try:
    import msgspec
    _MSGSPEC_AVAILABLE = True
except ImportError:
    _MSGSPEC_AVAILABLE = False


if _MSGSPEC_AVAILABLE:
    class InjuryEntry(msgspec.Struct, kw_only=True):
        injury_id: str = ""
        hp_occupied: int = 0
        severity: int = 1
        body_part: str = ""
        type: str = "trauma"
        treated: bool = False
        created_at: float = 0.0
        organ_damage: dict = {}
        limb_damage: dict = {}
        fracture: object = None
        bleed_rate: float = 0.0
        vessel_type: str = "none"
        bleed_treated: bool = False
        infection_risk: float = 0.0
        treatment_quality: int = 0
        cleaned_at: float = 0.0
        infection_type: object = None
        infection_stage: int = 0
        infection_since: float = 0.0
        last_infection_tick: float = 0.0
        last_infection_reminder: float = 0.0
        antibiotic_until: float = 0.0
        antibiotic_potency: float = 0.0
        antibiotic_profile: object = None
        immunosuppressant_until: float = 0.0
        immunosuppressant_potency: float = 0.0
        immunosuppressant_profile: object = None
        pill_last_dose: dict = {}
        cyberware_dbref: object = None
        rejection_risk: float = 0.0

    class TransactionEntry(msgspec.Struct, kw_only=True):
        time: float = 0.0
        type: str = "credit"
        amount: int = 0
        party: str = ""
        reason: str = ""

else:
    # Fallback plain classes when msgspec is unavailable.
    class InjuryEntry:  # type: ignore[no-redef]
        pass

    class TransactionEntry:  # type: ignore[no-redef]
        pass


def structure_injury(raw: dict) -> "InjuryEntry | None":
    """
    Convert a raw injury dict to an InjuryEntry.
    Returns None if msgspec is unavailable or raw is not a dict.
    """
    if not _MSGSPEC_AVAILABLE or not isinstance(raw, dict):
        return None
    try:
        return msgspec.convert(raw, InjuryEntry)
    except Exception:
        return None


def unstructure_injury(entry: "InjuryEntry") -> dict:
    """Convert an InjuryEntry back to a plain dict."""
    if not _MSGSPEC_AVAILABLE:
        return {}
    try:
        return msgspec.to_builtins(entry)
    except Exception:
        return {}


def structure_transaction(raw: dict) -> "TransactionEntry | None":
    """Convert a raw transaction dict to a TransactionEntry."""
    if not _MSGSPEC_AVAILABLE or not isinstance(raw, dict):
        return None
    try:
        return msgspec.convert(raw, TransactionEntry)
    except Exception:
        return None


def unstructure_transaction(entry: "TransactionEntry") -> dict:
    """Convert a TransactionEntry back to a plain dict."""
    if not _MSGSPEC_AVAILABLE:
        return {}
    try:
        return msgspec.to_builtins(entry)
    except Exception:
        return {}
