"""
Oral medications: pill bottles (not MedicalTools). Patients take systemic doses with |wuse <bottle>|n (wield bottle first).
Doctors hand out bottles; dosing schedule (~8h) on the character affects potency (see world.medical.pill_dosing).
"""
from typeclasses.items import Item


def announce_pill_taken(taker, drug_display_name):
    """Room-visible swallow + self line (call after a successful dose)."""
    taker.msg(f"You take out a pill from your bottle of {drug_display_name} and swallow it.|n")
    loc = getattr(taker, "location", None)
    if not loc:
        return
    for ob in loc.contents:
        if ob is taker or not hasattr(ob, "msg"):
            continue
        name = taker.get_display_name(ob) if hasattr(taker, "get_display_name") else taker.name
        ob.msg(f"{name} takes out a pill from a bottle and swallows it.|n")


class PillBottle(Item):
    """
    db.pill_kind: 'antibiotic' | 'immunosuppressant'
    db.drug_display_name: human-readable name for messages
    db.antibiotic_profile / db.immunosuppressant_profile: string key
    db.antibiotic_targets / db.immunosuppressant_targets: list of infection_type keys
    db.uses_remaining: int or None
    """

    def at_object_creation(self):
        super().at_object_creation()
        if self.db.uses_remaining is None:
            self.db.uses_remaining = 20

    def get_drug_display_name(self, looker=None):
        return (getattr(self.db, "drug_display_name", None) or self.key or "medication").strip()

    def take_dose(self, taker, target, body_part=None):
        from world.medical.medical_treatment import attempt_pill_dose

        return attempt_pill_dose(taker, target, self, body_part=body_part)


class CoAmoxiclavBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "co-amoxiclav"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "co-amoxiclav"
        self.db.antibiotic_profile = "co_amoxiclav"
        self.db.antibiotic_targets = ["surface_cellulitis", "stitch_abscess", "sewer_fever"]


class CephalexinBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "cephalexin"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "cephalexin"
        self.db.antibiotic_profile = "cephalexin"
        self.db.antibiotic_targets = ["surface_cellulitis", "stitch_abscess"]


class DoxycyclineBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "doxycycline"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "doxycycline"
        self.db.antibiotic_profile = "doxycycline"
        self.db.antibiotic_targets = ["sewer_fever", "pleural_empyema"]


class MetronidazoleBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "metronidazole"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "metronidazole"
        self.db.antibiotic_profile = "metronidazole"
        self.db.antibiotic_targets = ["anaerobic_wound_rot"]


class ClindamycinBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "clindamycin"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "clindamycin"
        self.db.antibiotic_profile = "clindamycin"
        self.db.antibiotic_targets = ["anaerobic_wound_rot", "bone_deep_osteitis"]


class PiperacillinTazobactamBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "piperacillin-tazobactam"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "piperacillin/tazobactam"
        self.db.antibiotic_profile = "pip_tazo"
        self.db.antibiotic_targets = [
            "anaerobic_wound_rot",
            "bone_deep_osteitis",
            "pleural_empyema",
            "sewer_fever",
            "bloodfire_sepsis",
        ]


class VancomycinBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "vancomycin"
        self.db.pill_kind = "antibiotic"
        self.db.drug_display_name = "vancomycin"
        self.db.antibiotic_profile = "vancomycin"
        self.db.antibiotic_targets = ["bloodfire_sepsis", "chrome_interface_necrosis"]


class TacrolimusBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "tacrolimus"
        self.db.pill_kind = "immunosuppressant"
        self.db.drug_display_name = "tacrolimus"
        self.db.immunosuppressant_profile = "tacrolimus"
        self.db.immunosuppressant_targets = ["chrome_rejection_syndrome", "neural_rejection_cascade"]


class MycophenolateBottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "mycophenolate"
        self.db.pill_kind = "immunosuppressant"
        self.db.drug_display_name = "mycophenolate"
        self.db.immunosuppressant_profile = "mycophenolate"
        self.db.immunosuppressant_targets = ["chrome_rejection_syndrome", "neural_rejection_cascade"]


class Cyclochrome7Bottle(PillBottle):
    def at_object_creation(self):
        super().at_object_creation()
        self.key = "cyclochrome-7"
        self.db.pill_kind = "immunosuppressant"
        self.db.drug_display_name = "Cyclochrome-7"
        self.db.immunosuppressant_profile = "cyclochrome_7"
        self.db.immunosuppressant_targets = ["chrome_rejection_syndrome", "neural_rejection_cascade"]


# Backward-compatible class names (older scripts / prototypes)
class Antibiotics(CoAmoxiclavBottle):
    """Alias -> co-amoxiclav bottle."""

    pass


class AntiAnaerobeKit(MetronidazoleBottle):
    """Alias -> metronidazole bottle."""

    pass


class InterfacePhageCocktail(VancomycinBottle):
    """Alias -> vancomycin bottle."""

    pass
