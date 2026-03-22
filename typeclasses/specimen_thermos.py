"""
Specimen collection container — one raw specimen at a time.
"""
from evennia.objects.objects import DefaultObject


class SpecimenThermos(DefaultObject):
    def at_object_creation(self):
        super().at_object_creation()
        self.db.specimen = None
        self.db.specimen_amount = 0.0
        self.db.is_thermos = True
        self.locks.add("get:all()")
