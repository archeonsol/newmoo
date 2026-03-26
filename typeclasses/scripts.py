"""
Scripts

Global ticking scripts for game-wide periodic systems. Each script owns its
own registration via ensure() — at_server_start calls Script.ensure() for
each, which creates the script if absent and is a no-op if it already exists.

Data storage that previously lived in scripts (StaffPendingScript,
PCNoteStorage, GlobalClimateScript, ProfilingScript) has been moved to its
proper home: Django models (world.models) and ServerConfig.
"""

import time
from evennia.scripts.scripts import DefaultScript


class Script(DefaultScript):
    """Base typeclass for all project scripts."""
    pass


class StaminaRegenScript(Script):
    """
    Global stamina regen: every STAMINA_REGEN_INTERVAL seconds, tick all
    in-world characters.
    """

    @classmethod
    def ensure(cls):
        from evennia.scripts.models import ScriptDB
        if not ScriptDB.objects.filter(db_key="stamina_regen").exists():
            from evennia import create_script
            create_script(cls)

    def at_script_creation(self):
        from world.rpg.stamina import STAMINA_REGEN_INTERVAL
        self.key = "stamina_regen"
        self.interval = STAMINA_REGEN_INTERVAL
        self.repeats = 0
        self.persistent = True

    def at_repeat(self):
        from world.profiling import timed_tick
        from world.rpg.stamina import stamina_regen_all
        with timed_tick("stamina_regen", self.interval):
            stamina_regen_all()


class BleedingTickScript(Script):
    """
    Global bleeding tick: every BLEEDING_TICK_INTERVAL seconds, apply one bleed
    drain to all in-world characters with bleeding_level > 0.
    """

    @classmethod
    def ensure(cls):
        from evennia.scripts.models import ScriptDB
        if not ScriptDB.objects.filter(db_key="bleeding_tick").exists():
            from evennia import create_script
            create_script(cls)

    def at_script_creation(self):
        from world.medical import BLEEDING_TICK_INTERVAL
        self.key = "bleeding_tick"
        self.interval = BLEEDING_TICK_INTERVAL
        self.repeats = 0
        self.persistent = True

    def at_repeat(self):
        from world.profiling import timed_tick
        from world.medical import bleeding_tick_all
        with timed_tick("bleeding_tick", self.interval):
            bleeding_tick_all()


class AddictionWithdrawalScript(Script):
    """Every 30 minutes: addiction withdrawal onset, recovery steps, echoes."""

    @classmethod
    def ensure(cls):
        from evennia.scripts.models import ScriptDB
        if not ScriptDB.objects.filter(db_key="addiction_withdrawal").exists():
            from evennia import create_script
            create_script(cls)

    def at_script_creation(self):
        self.key = "addiction_withdrawal"
        self.interval = 1800
        self.repeats = 0
        self.persistent = True

    def at_repeat(self):
        from world.profiling import timed_tick
        from world.alchemy.addiction import tick_online_characters
        with timed_tick("addiction_withdrawal", self.interval):
            tick_online_characters()


class HandsetMessageCleanupScript(Script):
    """
    Global cleanup: prune handset message buffers to last 24 hours.

    Runs on a timer so simply viewing menus won't delete messages.
    """

    @classmethod
    def ensure(cls):
        from evennia.scripts.models import ScriptDB
        if not ScriptDB.objects.filter(db_key="handset_message_cleanup").exists():
            from evennia import create_script
            create_script(cls)

    def at_script_creation(self):
        self.key = "handset_message_cleanup"
        self.interval = 3600  # hourly
        self.repeats = 0
        self.persistent = True

    def at_repeat(self):
        from world.profiling import timed_tick
        with timed_tick("handset_message_cleanup", self.interval):
            self._run_cleanup()

    def _run_cleanup(self):
        cutoff = time.time() - 86400
        try:
            from evennia.objects.models import ObjectDB
        except Exception:
            return

        qs = ObjectDB.objects.filter(db_typeclass_path="typeclasses.matrix.devices.handsets.Handset")
        for obj in qs:
            try:
                texts = list(getattr(obj.db, "texts", []) or [])
            except Exception:
                continue
            if not texts:
                continue
            kept = []
            for entry in texts:
                if not isinstance(entry, dict):
                    continue
                t = entry.get("t", None)
                if t is None:
                    continue
                try:
                    if float(t) >= cutoff:
                        kept.append(entry)
                except Exception:
                    continue
            if kept != texts:
                obj.db.texts = kept

        from world.profiling import snapshot_object_counts
        snapshot_object_counts({"Handset": len(qs)})


# Matrix scripts
from typeclasses.matrix.scripts import MatrixCleanupScript, MatrixConnectionScript  # noqa: F401, E402
