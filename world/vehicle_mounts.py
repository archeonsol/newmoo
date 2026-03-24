"""Motorcycle mount/dismount helpers for combat, grapple, and movement."""

from typeclasses.vehicles import Motorcycle, vehicle_label


def force_dismount(character, motorcycle, reason=""):
    """Remove rider from motorcycle. Called by combat, damage, grapple, or walking off."""
    if not character or not motorcycle:
        return
    character.db.mounted_on = None
    motorcycle.db.rider = None
    motorcycle.db.driver = None

    if reason == "damage":
        character.msg(
            "|rThe impact throws you from the bike. You hit the ground hard — the wind knocked out of you.|n"
        )
        if character.location:
            character.location.msg_contents(
                "{name} is thrown from their bike and hits the ground!",
                exclude=character,
                mapping={"name": character},
            )
        if hasattr(character, "at_damage"):
            character.at_damage(None, 12, weapon_key="fall")
        # Stagger: skip the next 2 combat rounds while recovering from the fall.
        character.db.combat_skip_turns = 2
    elif reason == "grappled":
        character.msg("|rYou're pulled from the bike.|n")
    elif reason == "move":
        character.msg("You swing off the bike before you walk.")
    elif reason == "destruction":
        pass  # caller sends destruction messages
    else:
        character.msg("You dismount.")
        if character.location:
            blab = vehicle_label(motorcycle)
            character.location.msg_contents(
                f"{{name}} dismounts from {blab}.",
                exclude=character,
                mapping={"name": character},
            )


def check_motorcycle_dismount_on_damage(character, damage):
    """After taking damage while mounted: endurance vs difficulty."""
    bike = getattr(character.db, "mounted_on", None)
    if not bike or not isinstance(bike, Motorcycle):
        return
    try:
        dmg = int(damage or 0)
    except (TypeError, ValueError):
        dmg = 0
    if dmg <= 0:
        return
    tier, _ = character.roll_check(["endurance"], "driving", difficulty=dmg // 2)
    if tier not in ("Critical Success", "Full Success", "Marginal Success"):
        force_dismount(character, bike, reason="damage")


def try_auto_dismount_for_move(character):
    """If mounted, dismount before walking (normal move/traverse). Returns True if dismounted."""
    bike = getattr(character.db, "mounted_on", None)
    if not bike:
        return False
    force_dismount(character, bike, reason="move")
    return True
