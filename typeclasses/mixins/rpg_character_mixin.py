"""
RPG character mixin: stats, skills, grades, and the roll-check (dice) system.
"""
import random


class RPGCharacterMixin:
    """Stats 0-300, skills 0-150; letter tiers; roll_check (the simulation engine)."""

    def get_grade_adjective(self, grade_letter):
        """Legacy: use get_stat_grade_adjective or get_skill_grade_adjective. Falls back to skill adjective."""
        from world.grades import get_skill_grade_adjective
        return get_skill_grade_adjective(grade_letter)

    def get_stat_level(self, stat_key):
        """Return stored stat level 0-300 (used for XP spending and letter lookup)."""
        from world.xp import _stat_level
        return _stat_level(self, stat_key)

    def get_display_stat(self, stat_name):
        """
        Return display level 0-150 for a stat (stored_level // 2). Use for all RPG mechanics and HP.
        No external code should perform // 2 on stored stats; use this method instead.
        """
        stored = self.get_stat_level(stat_name) or 0
        return min(int(stored) // 2, 150)

    def get_skill_level(self, skill_key):
        """Return skill level as int 0-150 (normalizes legacy letter to mid-tier)."""
        from world.xp import _skill_level
        return _skill_level(self, skill_key)

    def get_stat_grade_adjective(self, grade_letter, stat_key):
        """Adjective for this stat at this grade (letter-matched, per-stat)."""
        from world.grades import get_stat_grade_adjective as _get
        return _get(grade_letter, stat_key)

    def get_skill_grade_adjective(self, grade_letter):
        """Adjective for skills at this grade (letter-matched, shared set)."""
        from world.grades import get_skill_grade_adjective as _get
        return _get(grade_letter)

    def get_stat_cap(self, stat_key):
        """Return stored stat cap 0-300 (display as //2 for 0-150 scale)."""
        from world.xp import _stat_cap_level
        return _stat_cap_level(self, stat_key)

    def get_skill_cap(self, skill_key):
        """Return cap level for this skill (int 0-150)."""
        from world.xp import _skill_cap_level
        return _skill_cap_level(self, skill_key)

    def roll_check(self, stat_list, skill_name, difficulty=0, modifier=0):
        """
        modifier: A hidden raw number added to the final result
                  (from stances, gear, or temporary states).
        Uses display level for stats (get_display_stat); skill level as-is. Both scaled to 1-21 (U–A).
        """
        if isinstance(stat_list, str):
            stat_list = [stat_list]

        from world.levels import level_to_effective_grade, MAX_LEVEL
        total_display = sum(self.get_display_stat(s) for s in stat_list)
        stat_val = level_to_effective_grade(int(total_display / len(stat_list)), MAX_LEVEL)

        skill_level = self.get_skill_level(skill_name)
        skill_val = level_to_effective_grade(skill_level, MAX_LEVEL)

        # 1. THE CEILING (Skill-based technical cap)
        ceiling = (skill_val * 6) + 10
        ceiling = min(100, ceiling)

        # 2. THE STRENGTH (Stat-based bonus)
        strength_bonus = stat_val * 2

        # 3. THE ROLL
        raw_roll = random.randint(1, 100)
        effective_roll = min(raw_roll, ceiling)
        final_result = effective_roll + strength_bonus + modifier - difficulty

        if final_result > 90:
            return "Critical Success", final_result
        if final_result > 60:
            return "Full Success", final_result
        if final_result > 35:
            return "Marginal Success", final_result
        return "Failure", final_result
