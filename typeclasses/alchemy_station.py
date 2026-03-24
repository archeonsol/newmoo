"""
Alchemy workstations: apothecary (organic) and synthesis rig (chemical/tech).
State lives on db.* — see world.alchemy.stations.
"""
from evennia.objects.objects import DefaultObject


class AlchemyStationBase(DefaultObject):
    """
    Base class for alchemy stations. Subclasses set ``station_type`` (apothecary | synthesis).
    """

    station_type = "apothecary"

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:false()")
        self.db.station_type = self.station_type
        self.db.batch_active = False
        self.db.batch_owner = None
        self.db.batch_recipe = None
        self.db.batch_quality = 100
        self.db.batch_stage = 0
        self.db.batch_stage_ready = False
        self.db.batch_stage_started = None
        self.db.batch_ingredients = {}
        self.db.batch_yield = 0
        self.db.refining = False
        self.db.refine_specimen = None
        self.db.refine_started = None
        self.db.refine_duration = 0
        self.db.refine_ready = False
        self.db.station_name = "alchemy station"
        self.db.is_alchemy_station = True

    def at_server_start(self):
        try:
            from world.alchemy.stations import reconcile_station

            reconcile_station(self)
        except Exception:
            pass


class ApothecaryTable(AlchemyStationBase):
    """
    Organic alchemy station. Biological specimens, fermentation, culturing, extraction.
    """

    station_type = "apothecary"


class SynthesisRig(AlchemyStationBase):
    """
    Synthetic alchemy station. Chemical processing, crystallization, electrolysis.
    """

    station_type = "synthesis"


class AlchemyStation(ApothecaryTable):
    """Legacy alias: same behavior as Apothecary Table (existing objects may use this typeclass)."""

    pass
