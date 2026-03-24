"""
Refined chemicals and finished drug items for the alchemy system.
"""
from typeclasses.items import Item


def sync_drug_item_desc_from_registry(obj):
    """
    If db.desc is empty, set it from world.alchemy.drugs_registry (single source of truth).
    Skips when desc is already set so builders can override on the object.
    """
    dk = getattr(obj.db, "drug_key", None)
    if not dk:
        return
    if (getattr(obj.db, "desc", None) or "").strip():
        return
    try:
        from world.alchemy import DRUGS

        drug = DRUGS.get(dk)
        if drug and drug.get("desc"):
            obj.db.desc = drug["desc"]
    except Exception:
        pass


class ChemicalItem(Item):
    """Refined chemical container. db.chemical_key, db.amount (0.0-1.0)."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.chemical_key = None
        self.db.amount = 1.0
        self.db.is_chemical = True
        self.db.desc = "A labeled chemical container."


class DrugItem(Item):
    """Crafted drug. db.drug_key, quality, doses_remaining, suspicious flag."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.drug_key = None
        self.db.drug_quality = 50
        self.db.drug_potency_mult = 1.0
        self.db.doses_remaining = 1
        self.db.crafted_by = None
        self.db.batch_id = None
        self.db.suspicious = False
        self.db.is_drug_item = True

    def at_init(self):
        super().at_init()
        sync_drug_item_desc_from_registry(self)

    def return_appearance(self, looker, **kwargs):
        # Covers spawn order where drug_key is set after create_object / at_init
        sync_drug_item_desc_from_registry(self)
        return super().return_appearance(looker, **kwargs)

    def get_display_name(self, looker, **kwargs):
        base = super().get_display_name(looker, **kwargs)
        if getattr(self.db, "suspicious", False):
            return "a suspicious liquid"
        q = int(getattr(self.db, "drug_quality", 50) or 50)
        if q < 40:
            qual = "murky"
        elif q <= 70:
            qual = "clear"
        else:
            qual = "pristine"
        from world.alchemy import DRUGS

        dk = self.db.drug_key
        drug = DRUGS.get(dk) if dk else None
        if drug:
            form = drug.get("form", "dose")
            return f"a {qual} {form} of {drug.get('name', dk)}"
        return base
