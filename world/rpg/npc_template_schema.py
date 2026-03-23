"""
Pydantic schema for NPC template validation.

Validates that every NPC template returned by get_npc_template() has the
correct structure: a name string, a stats dict with valid stat keys and
int values, and a skills dict with valid skill keys and int values.

A bad template (missing key, wrong type, unknown stat/skill) raises a
ValidationError at the point of use rather than causing a silent failure
when the template is applied to an NPC.

Usage:
    from world.rpg.npc_template_schema import validate_npc_template
    validated = validate_npc_template(raw_template)
    # validated is a plain dict — all existing call sites unchanged.
"""

from pydantic import BaseModel, field_validator, model_validator


class NPCTemplateSchema(BaseModel):
    """
    Schema for a single NPC template.

    Fields:
        name (str): Display name for the NPC.
        stats (dict[str, int]): Stat key → value. All keys must be in STAT_KEYS.
        skills (dict[str, int]): Skill key → value. All keys must be in SKILL_KEYS.
    """
    name: str
    stats: dict[str, int]
    skills: dict[str, int]

    @field_validator("stats")
    @classmethod
    def validate_stats(cls, v: dict) -> dict:
        from world.rpg.npc_templates import STAT_KEYS
        unknown = [k for k in v if k not in STAT_KEYS]
        if unknown:
            raise ValueError(f"Unknown stat key(s) in template: {unknown}")
        return v

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: dict) -> dict:
        from world.skills import SKILL_KEYS
        unknown = [k for k in v if k not in SKILL_KEYS]
        if unknown:
            raise ValueError(f"Unknown skill key(s) in template: {unknown}")
        return v

    @model_validator(mode="after")
    def stats_values_in_range(self) -> "NPCTemplateSchema":
        from world.levels import MAX_STAT_LEVEL, MAX_LEVEL
        for k, v in self.stats.items():
            if v < 0 or v > MAX_STAT_LEVEL:
                raise ValueError(f"Stat '{k}' value {v} out of range 0–{MAX_STAT_LEVEL}")
        for k, v in self.skills.items():
            if v < 0 or v > MAX_LEVEL:
                raise ValueError(f"Skill '{k}' value {v} out of range 0–{MAX_LEVEL}")
        return self


def validate_npc_template(raw: dict) -> dict:
    """
    Validate a raw NPC template dict and return a plain-dict version.

    Args:
        raw: Template dict with 'name', 'stats', 'skills' keys.

    Returns:
        dict: Validated template (plain dict, all existing call sites unchanged).

    Raises:
        pydantic.ValidationError: If the template is malformed.
    """
    return NPCTemplateSchema(**raw).model_dump()
