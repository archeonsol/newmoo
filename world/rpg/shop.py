"""
Shop / vendor system.

Vendors are objects (or NPCs) that carry a ShopMixin. Their inventory is
stored on db.shop_inventory as a list of item dicts. Staff configure vendors
via @shopset (see economy_cmds.py).

Item dict shape:
  {
    "key":              str,   -- unique key within this vendor's inventory
    "name":             str,   -- display name
    "desc":             str,   -- short one-line description shown in listing
    "price":            int,   -- base price in currency units
    "stock":            int,   -- -1 = unlimited; 0 = sold out; N = finite
    "prototype":        str,   -- Evennia prototype key to spawn on purchase (or None)
    "faction_required": str,   -- faction key required to purchase (or None)
    "rank_required":    int,   -- minimum faction rank required (0 = any member)
    "sale_price":       int,   -- discounted price when on sale (or None)
    "sale_until":       float, -- unix timestamp when sale ends (or None)
    "tags":             list,  -- optional extra tags to add to spawned object
  }

ShopMixin attributes on the vendor object:
  db.shop_inventory   -- list of item dicts (see above)
  db.shop_name        -- display name of the shop (e.g. "Blackwood Surplus")
  db.shop_faction     -- faction key restricting who can browse (or None = public)
  db.shop_desc        -- one-line shop description shown in listing header
  db.shop_open        -- bool (default True); staff can close a shop
"""

import time

from world.rpg.economy import (
    CURRENCY_NAME,
    format_currency,
    get_balance,
    deduct_funds,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STOCK_UNLIMITED = -1
LISTING_WIDTH = 62    # visible width of the shop listing box

# ---------------------------------------------------------------------------
# ShopMixin
# ---------------------------------------------------------------------------

class ShopMixin:
    """
    Mixin for vendor NPCs and shop objects.

    Provides helpers to read/write inventory and check access.
    Add this mixin to a typeclass alongside DefaultObject or DefaultCharacter.
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.shop_inventory = []
        self.db.shop_name = self.key
        self.db.shop_faction = None
        self.db.shop_desc = ""
        self.db.shop_open = True

    def is_vendor(self):
        return True

    def get_shop_items(self, character=None):
        """Return the list of item dicts, optionally filtered for a character."""
        items = list(self.db.shop_inventory or [])
        if character is None:
            return items
        return [it for it in items if _item_visible(it, character)]

    def get_item_by_key(self, item_key):
        for it in (self.db.shop_inventory or []):
            if it.get("key") == item_key:
                return it
        return None

    def get_item_by_number(self, number):
        """Return the item at 1-based index in the visible list."""
        items = list(self.db.shop_inventory or [])
        try:
            idx = int(number) - 1
            return items[idx] if 0 <= idx < len(items) else None
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _effective_price(item):
    """Return the current price for an item (sale price if active)."""
    sale_price = item.get("sale_price")
    sale_until = item.get("sale_until")
    if sale_price is not None and sale_until and time.time() < sale_until:
        return int(sale_price)
    return int(item.get("price", 0))


def _is_on_sale(item):
    sale_price = item.get("sale_price")
    sale_until = item.get("sale_until")
    return bool(sale_price is not None and sale_until and time.time() < sale_until)


def _item_visible(item, character):
    """
    Return True if the item should appear in the listing for this character.
    Restricted items still appear but are marked as restricted.
    """
    return True  # All items visible; access checked at buy time


def _item_accessible(item, character):
    """
    Return (accessible: bool, reason: str).
    Checks faction membership and rank requirements.
    """
    faction_req = item.get("faction_required")
    rank_req = item.get("rank_required", 0)

    if faction_req:
        from world.rpg.factions import is_faction_member
        from world.rpg.factions.membership import get_member_rank
        if not is_faction_member(character, faction_req):
            from world.rpg.factions import get_faction
            fd = get_faction(faction_req)
            name = fd["name"] if fd else faction_req
            return False, f"Requires {name} membership."
        if rank_req:
            rank = get_member_rank(character, faction_req)
            if rank < rank_req:
                return False, f"Requires rank {rank_req} in {faction_req}."

    return True, ""


def get_shop_items(vendor, character=None):
    """Return items from a vendor, optionally filtered."""
    if hasattr(vendor, "get_shop_items"):
        return vendor.get_shop_items(character)
    return list(getattr(vendor.db, "shop_inventory", None) or [])


def buy_item(character, vendor, item_ref, qty=1):
    """
    Purchase an item from a vendor.

    item_ref: item key (str) or 1-based number (int or str).
    qty: quantity to purchase (default 1).

    Returns (success: bool, message: str, items_spawned: list).
    """
    qty = max(1, int(qty))

    # Resolve item
    if hasattr(vendor, "get_item_by_key"):
        item = vendor.get_item_by_key(str(item_ref))
        if not item:
            item = vendor.get_item_by_number(item_ref)
    else:
        item = None
        inventory = list(getattr(vendor.db, "shop_inventory", None) or [])
        for it in inventory:
            if it.get("key") == str(item_ref):
                item = it
                break
        if not item:
            try:
                idx = int(item_ref) - 1
                item = inventory[idx] if 0 <= idx < len(inventory) else None
            except (ValueError, TypeError):
                pass

    if not item:
        return False, "That item isn't available here.", []

    # Shop open check
    if not getattr(vendor.db, "shop_open", True):
        return False, f"{vendor.key} is not open for business right now.", []

    # Stock check
    stock = item.get("stock", STOCK_UNLIMITED)
    if stock == 0:
        return False, f"{item['name']} is sold out.", []
    if stock != STOCK_UNLIMITED and stock < qty:
        return False, f"Only {stock} in stock.", []

    # Access check
    accessible, reason = _item_accessible(item, character)
    if not accessible:
        return False, reason, []

    price = _effective_price(item)
    total = price * qty

    # Funds check
    wallet = get_balance(character)
    if wallet < total:
        short = total - wallet
        return (
            False,
            f"You need {format_currency(total)} but only have {format_currency(wallet)}. "
            f"({format_currency(short)} short.)",
            [],
        )

    # Deduct funds
    ok = deduct_funds(character, total, party=getattr(vendor, "key", "vendor"),
                      reason=f"purchase: {item['name']} x{qty}")
    if not ok:
        return False, "Transaction failed.", []

    # Decrement stock
    if stock != STOCK_UNLIMITED:
        item["stock"] = stock - qty
        # Write back
        inv = list(vendor.db.shop_inventory or [])
        for i, it in enumerate(inv):
            if it.get("key") == item.get("key"):
                inv[i] = item
                break
        vendor.db.shop_inventory = inv

    # Spawn items
    spawned = []
    prototype_key = item.get("prototype")
    if prototype_key:
        from evennia.prototypes.spawner import spawn
        extra_tags = item.get("tags") or []
        for _ in range(qty):
            try:
                objs = spawn(prototype_key)
                if objs:
                    obj = objs[0]
                    obj.location = character
                    for tag in extra_tags:
                        obj.tags.add(tag)
                    spawned.append(obj)
            except Exception as e:
                from evennia.utils import logger
                logger.log_err(f"shop.buy_item: spawn error for prototype '{prototype_key}': {e}")

    return True, f"Purchased {item['name']} x{qty} for {format_currency(total)}.", spawned


# ---------------------------------------------------------------------------
# Visual shop listing
# ---------------------------------------------------------------------------

_BOX_W = LISTING_WIDTH


def _lbox_top():
    return f"|x╔{'═' * (_BOX_W - 2)}╗|n"


def _lbox_bot():
    return f"|x╚{'═' * (_BOX_W - 2)}╝|n"


def _lbox_div():
    return f"|x╠{'═' * (_BOX_W - 2)}╣|n"


def _lbox_row(text, fill=" "):
    from evennia.utils.ansi import strip_ansi
    visible = len(strip_ansi(text))
    pad = max(0, _BOX_W - 4 - visible)
    return f"|x║|n  {text}{fill * pad}  |x║|n"


def _lbox_header(shop_name, shop_desc=""):
    from evennia.utils.ansi import strip_ansi
    title = f"|w{shop_name.upper()}|n"
    if shop_desc:
        title += f"  |x—|n  {shop_desc}"
    visible = len(strip_ansi(title))
    pad = max(0, _BOX_W - 4 - visible)
    return (
        f"{_lbox_top()}\n"
        f"|x║|n  {title}{' ' * pad}  |x║|n\n"
        f"{_lbox_div()}"
    )


def _lbox_col_header():
    num_w = 3
    name_w = 28
    price_w = 14
    stock_w = _BOX_W - 4 - num_w - name_w - price_w - 2
    header = (
        f"|x{'#':<{num_w}}|n  "
        f"|x{'Item':<{name_w}}|n"
        f"|x{'Price':>{price_w}}|n"
        f"|x{'Stock':>{stock_w}}|n"
    )
    return _lbox_row(header)


def format_shop_listing(vendor, character=None):
    """
    Return a rich visual shop listing string for the given vendor.

    Restricted items are shown with a [RESTRICTED] tag.
    Sale items show the discounted price in yellow with the original struck.
    """
    shop_name = getattr(vendor.db, "shop_name", None) or getattr(vendor, "key", "Shop")
    shop_desc = getattr(vendor.db, "shop_desc", "") or ""
    shop_open = getattr(vendor.db, "shop_open", True)
    items = get_shop_items(vendor, character)

    lines = [_lbox_header(shop_name, shop_desc)]

    if not shop_open:
        lines.append(_lbox_row("|rCLOSED — not currently trading.|n"))
        lines.append(_lbox_bot())
        return "\n".join(lines)

    if not items:
        lines.append(_lbox_row("|xNo items available.|n"))
        lines.append(_lbox_bot())
        return "\n".join(lines)

    lines.append(_lbox_col_header())
    lines.append(f"|x╠{'─' * (_BOX_W - 2)}╣|n")

    for idx, item in enumerate(items, start=1):
        name = item.get("name", "Unknown")
        desc = item.get("desc", "")
        price = int(item.get("price", 0))
        stock = item.get("stock", STOCK_UNLIMITED)
        on_sale = _is_on_sale(item)
        effective = _effective_price(item)

        # Access
        if character:
            accessible, restrict_reason = _item_accessible(item, character)
        else:
            accessible, restrict_reason = True, ""

        # Price display
        if on_sale:
            price_str = f"|y{format_currency(effective, color=False)}|n |x({format_currency(price, color=False)})|n"
        else:
            price_str = format_currency(effective)

        if not accessible:
            price_str = f"|x[RESTRICTED]|n"

        # Stock display
        if stock == STOCK_UNLIMITED:
            stock_str = "|x×∞|n"
        elif stock == 0:
            stock_str = "|rSOLD OUT|n"
        else:
            stock_str = f"|x×{stock}|n"

        # Row
        from evennia.utils.ansi import strip_ansi
        num_w = 3
        name_w = 28
        price_w = 14
        stock_w = _BOX_W - 4 - num_w - name_w - price_w - 2

        name_display = name[:name_w] if len(name) <= name_w else name[:name_w - 1] + "…"
        price_visible = len(strip_ansi(price_str))
        stock_visible = len(strip_ansi(stock_str))

        price_pad = max(0, price_w - price_visible)
        stock_pad = max(0, stock_w - stock_visible)

        row = (
            f"|w{idx:<{num_w}}|n  "
            f"{name_display:<{name_w}}"
            f"{' ' * price_pad}{price_str}"
            f"{' ' * stock_pad}{stock_str}"
        )
        lines.append(_lbox_row(row))

        if desc:
            desc_display = desc[:_BOX_W - 8]
            lines.append(_lbox_row(f"  |x{desc_display}|n"))

        if on_sale:
            sale_until = item.get("sale_until", 0)
            remaining = max(0, int(sale_until - time.time()))
            if remaining > 3600:
                sale_str = f"  |ySALE — {remaining // 3600}h remaining|n"
            else:
                sale_str = f"  |ySALE — {remaining // 60}m remaining|n"
            lines.append(_lbox_row(sale_str))

        if not accessible and restrict_reason:
            lines.append(_lbox_row(f"  |x{restrict_reason}|n"))

        # Separator between items (not after last)
        if idx < len(items):
            lines.append(f"|x║{'·' * (_BOX_W - 2)}║|n")

    lines.append(_lbox_bot())

    if character:
        wallet = get_balance(character)
        lines.append(f"  Your wallet: {format_currency(wallet)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Staff helpers
# ---------------------------------------------------------------------------

def add_shop_item(vendor, item_dict):
    """
    Add or replace an item in a vendor's inventory.

    item_dict must have at least 'key', 'name', and 'price'.
    Returns (success: bool, message: str).
    """
    key = item_dict.get("key")
    if not key:
        return False, "Item must have a 'key'."

    inv = list(vendor.db.shop_inventory or [])
    for i, it in enumerate(inv):
        if it.get("key") == key:
            inv[i] = item_dict
            vendor.db.shop_inventory = inv
            return True, f"Updated item '{key}'."

    inv.append(item_dict)
    vendor.db.shop_inventory = inv
    return True, f"Added item '{key}'."


def remove_shop_item(vendor, item_key):
    """Remove an item from a vendor's inventory by key."""
    inv = list(vendor.db.shop_inventory or [])
    new_inv = [it for it in inv if it.get("key") != item_key]
    if len(new_inv) == len(inv):
        return False, f"Item '{item_key}' not found."
    vendor.db.shop_inventory = new_inv
    return True, f"Removed item '{item_key}'."


def restock_item(vendor, item_key, amount):
    """Set or add stock for an item."""
    inv = list(vendor.db.shop_inventory or [])
    for i, it in enumerate(inv):
        if it.get("key") == item_key:
            current = it.get("stock", STOCK_UNLIMITED)
            if current == STOCK_UNLIMITED:
                return True, "Item has unlimited stock."
            inv[i]["stock"] = current + int(amount)
            vendor.db.shop_inventory = inv
            return True, f"Restocked '{item_key}' to {inv[i]['stock']}."
    return False, f"Item '{item_key}' not found."


def set_sale(vendor, item_key, sale_price, duration_hours):
    """Put an item on sale for a given number of hours."""
    inv = list(vendor.db.shop_inventory or [])
    for i, it in enumerate(inv):
        if it.get("key") == item_key:
            inv[i]["sale_price"] = int(sale_price)
            inv[i]["sale_until"] = time.time() + duration_hours * 3600
            vendor.db.shop_inventory = inv
            return True, f"Sale set on '{item_key}' for {duration_hours}h."
    return False, f"Item '{item_key}' not found."


def find_vendor_in_room(room):
    """
    Return the first vendor object found in the room, or None.

    Checks for objects with db.shop_inventory or tagged 'vendor'.
    """
    for obj in room.contents:
        if getattr(obj.db, "shop_inventory", None) is not None:
            return obj
        if obj.tags.get("vendor"):
            return obj
    return None
