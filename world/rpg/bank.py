"""
Bank system: account management, deposits, withdrawals, and Matrix wire transfers.

Bank storage per character:
  character.db.bank_balance        -- int, stored funds
  character.db.bank_account_opened -- float (unix timestamp)
  character.db.bank_interest_rate  -- float (default 0.0, staff-settable)

Wire transfers require:
  - Sender has a bank account
  - Recipient resolved by Matrix alias (@handle) or Matrix ID (^XXXXXX)
  - Caller is in a room with active Matrix signal coverage
  - A small percentage fee is charged (WIRE_FEE_PERCENT)

Bank terminal rooms must contain an object tagged with category="bank_terminal".
Staff can spawn one via @spawnbank (see economy_cmds.py).

EvMenu entry point: start_bank_menu(caller, terminal)
"""

import time

from evennia.utils.ansi import ANSIString

try:
    import arrow as _arrow
    _ARROW_AVAILABLE = True
except ImportError:
    _ARROW_AVAILABLE = False

from world.rpg.economy import (
    CURRENCY_NAME,
    TRANSACTION_LOG_SIZE,
    format_currency,
    format_transaction_log,
    get_balance,
    _log_transaction,
)
from world.ui_utils import fade_rule

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIRE_FEE_PERCENT = 1          # 1% fee on wire transfers
WIRE_MIN_FEE = 1              # Minimum fee in currency units
WIRE_MAX_AMOUNT = 999_999     # Safety cap per single wire

_W = 68                       # Panel width (visible chars, matches terminal width)
_N = "|n"
_DIM = "|x"
_LABEL = "|w"
_ACCENT = "|c"               # Cyan accent for bank UI
_GOLD = "|y"
_WARN = "|y"
_ERR = "|r"
_OK = "|g"

# ---------------------------------------------------------------------------
# Account helpers
# ---------------------------------------------------------------------------

def has_account(character):
    """Return True if the character has opened a bank account."""
    return getattr(character.db, "bank_account_opened", None) is not None


def open_account(character):
    """
    Open a new bank account for the character.

    Returns (success: bool, message: str).
    """
    if has_account(character):
        return False, "You already have an account."
    character.db.bank_balance = 0
    character.db.bank_account_opened = time.time()
    character.db.bank_interest_rate = 0.0
    return True, "Account opened."


def get_bank_balance(character):
    """Return the character's bank balance (int, never negative)."""
    return max(0, int(getattr(character.db, "bank_balance", 0) or 0))


def bank_deposit(character, amount):
    """
    Deposit cash from wallet into bank.

    Returns (success: bool, message: str).
    """
    if not has_account(character):
        return False, "You don't have a bank account."
    amount = int(amount)
    if amount <= 0:
        return False, "Amount must be positive."
    wallet = get_balance(character)
    if wallet < amount:
        return False, f"You only have {format_currency(wallet)} on hand."

    character.db.currency = wallet - amount
    character.db.bank_balance = get_bank_balance(character) + amount
    _log_transaction(character, "bank_deposit", amount, party="Bank", reason="deposit")
    return True, f"Deposited {format_currency(amount)}."


def bank_withdraw(character, amount):
    """
    Withdraw cash from bank into wallet.

    Returns (success: bool, message: str).
    """
    if not has_account(character):
        return False, "You don't have a bank account."
    amount = int(amount)
    if amount <= 0:
        return False, "Amount must be positive."
    bank_bal = get_bank_balance(character)
    if bank_bal < amount:
        return False, f"Your account only holds {format_currency(bank_bal)}."

    character.db.bank_balance = bank_bal - amount
    wallet = get_balance(character)
    character.db.currency = wallet + amount
    _log_transaction(character, "bank_withdraw", amount, party="Bank", reason="withdrawal")
    return True, f"Withdrew {format_currency(amount)}."


def _compute_wire_fee(amount):
    """Return the fee for a wire transfer of the given amount."""
    fee = max(WIRE_MIN_FEE, int(amount * WIRE_FEE_PERCENT / 100))
    return fee


def bank_wire(sender, network_id, amount):
    """
    Wire funds from sender's bank account to a recipient identified by
    Matrix alias (@handle) or Matrix ID (^XXXXXX).

    Signal coverage must be verified by the caller before calling this.

    Returns (success: bool, message: str, recipient_name: str, fee: int).
    """
    if not has_account(sender):
        return False, "You don't have a bank account.", "", 0

    amount = int(amount)
    if amount <= 0:
        return False, "Amount must be positive.", "", 0
    if amount > WIRE_MAX_AMOUNT:
        return False, f"Maximum single wire is {format_currency(WIRE_MAX_AMOUNT)}.", "", 0

    # Resolve recipient
    recipient = _resolve_wire_recipient(network_id)
    if not recipient:
        return False, f"No account found for '{network_id}'.", "", 0
    if recipient == sender:
        return False, "You cannot wire funds to yourself.", "", 0
    if not has_account(recipient):
        return False, f"{recipient.key} does not have a bank account.", "", 0

    fee = _compute_wire_fee(amount)
    total_cost = amount + fee
    bank_bal = get_bank_balance(sender)

    if bank_bal < total_cost:
        return (
            False,
            f"Insufficient bank funds. Need {format_currency(total_cost)} "
            f"({format_currency(amount)} + {format_currency(fee)} fee), "
            f"have {format_currency(bank_bal)}.",
            recipient.key,
            fee,
        )

    sender_name = getattr(sender, "key", str(sender))
    recipient_name = getattr(recipient, "key", str(recipient))

    # Deduct from sender (amount + fee)
    sender.db.bank_balance = bank_bal - total_cost
    _log_transaction(sender, "wire_out", amount, party=recipient_name,
                     reason=f"wire transfer (fee: {fee})")

    # Credit recipient (amount only; fee is consumed)
    recipient.db.bank_balance = get_bank_balance(recipient) + amount
    _log_transaction(recipient, "wire_in", amount, party=sender_name,
                     reason="wire transfer received")

    return True, f"Wired {format_currency(amount)} to {recipient_name}.", recipient_name, fee


def _resolve_wire_recipient(network_id):
    """
    Resolve a wire recipient from a Matrix alias or Matrix ID.

    Accepts:
      @alias   — Matrix account alias
      ^XXXXXX  — Matrix ID
    """
    if not network_id:
        return None
    nid = network_id.strip()

    if nid.startswith("@") or not nid.startswith("^"):
        # Try alias lookup
        from world.matrix_accounts import get_character_by_alias
        return get_character_by_alias(nid)

    # Matrix ID lookup
    from evennia.utils.search import search_object
    results = search_object(nid, attribute_name="matrix_id")
    if results:
        return results[0]
    # Also try direct db search
    from typeclasses.characters import Character
    for char in Character.objects.all():
        if hasattr(char, "get_matrix_id") and char.get_matrix_id() == nid:
            return char
    return None


# ---------------------------------------------------------------------------
# UI helpers  (open-right-border pattern — no right ║ to avoid ANSI misalign)
# ---------------------------------------------------------------------------

def _rule(ch="─", color=_DIM):
    """Full-width horizontal rule."""
    return f"{color}{ch * _W}{_N}"


def _fade(ch="─", color=_DIM):
    """Left-solid, right-fading rule."""
    return f"{color}{fade_rule(_W, ch)}{_N}"


def _panel_line(content="", indent=2):
    """
    Single panel row: left border + content, no right border.
    Uses ANSIString so visible-length is measured correctly.
    """
    padded = ANSIString(f"{' ' * indent}{content}").ljust(_W - 1)
    return f"{_ACCENT}│{_N}{padded}"


def _panel_header(title, subtitle=None):
    """
    Decorative header block:
      ╔══[ TITLE ]══ fading ──
      ║  subtitle
      ╟── fading ──
    """
    raw_title = f" {title} "
    title_len = len(ANSIString(raw_title))
    left_fill = 3
    right_width = max(4, _W - 1 - left_fill - title_len)

    top = (
        f"{_ACCENT}╔{'═' * left_fill}"
        f"[{_GOLD}{title}{_ACCENT}]"
        f"{_DIM}{fade_rule(right_width, '═')}{_N}"
    )
    lines = [top]

    if subtitle:
        lines.append(_panel_line(f"{_DIM}{subtitle}{_N}"))

    lines.append(f"{_ACCENT}╟{_DIM}{fade_rule(_W - 1, '─')}{_N}")
    return "\n".join(lines)


def _panel_section(label):
    """A dim in-panel section divider with a label."""
    raw = f"── {label} "
    raw_len = len(raw)
    rest = max(0, _W - 1 - raw_len)
    return f"{_DIM}{raw}{fade_rule(rest, '─')}{_N}"


def _panel_kv(key, value, key_w=14):
    """Key-value row inside a panel."""
    key_str = f"{_LABEL}{key}{_N}"
    return _panel_line(f"{key_str}{'.' * max(1, key_w - len(key))} {value}")


def _panel_close():
    return f"{_ACCENT}╚{_DIM}{fade_rule(_W - 1, '─')}{_N}"


def _format_balance_panel(character):
    wallet = get_balance(character)
    bank = get_bank_balance(character) if has_account(character) else None
    opened = getattr(character.db, "bank_account_opened", None)
    if opened:
        if _ARROW_AVAILABLE:
            opened_str = _arrow.get(opened).format("YYYY-MM-DD")
        else:
            opened_str = time.strftime("%Y-%m-%d", time.localtime(opened))
    else:
        opened_str = "—"

    lines = [
        _panel_header("BANK OF THE FRAME", subtitle="Frame Financial Network  //  Secure Terminal"),
        _panel_line(),
        _panel_kv("Holder", character.key),
        _panel_kv("Opened", f"{_DIM}{opened_str}{_N}"),
        _panel_line(),
        _panel_section("BALANCE"),
        _panel_kv("On Hand", format_currency(wallet)),
    ]
    if bank is not None:
        lines.append(_panel_kv("In Bank", format_currency(bank)))
        lines.append(_panel_kv("Total", f"{_GOLD}{format_currency(wallet + bank, color=False)}{_N}"))
    lines.append(_panel_line())
    lines.append(_panel_close())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EvMenu nodes
# ---------------------------------------------------------------------------

def _get_terminal(caller, kwargs):
    t = kwargs.get("terminal")
    if not t:
        t = getattr(getattr(caller, "ndb", None), "_bank_terminal", None)
    return t


def start_bank_menu(caller, terminal):
    """Open the bank EvMenu for the given terminal object."""
    from evennia.utils.evmenu import EvMenu

    try:
        caller.ndb._bank_terminal = terminal
    except Exception:
        pass

    EvMenu(
        caller,
        "world.rpg.bank",
        startnode="node_bank_main",
        terminal=terminal,
        persistent=False,
    )


def node_bank_main(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)

    if not has_account(caller):
        text = "\n".join([
            _panel_header("BANK OF THE FRAME", subtitle="No account on file for this identity."),
            _panel_line(),
            _panel_line(f"Identity {_LABEL}{caller.key}{_N} is not registered with the"),
            _panel_line("Frame Financial Network."),
            _panel_line(),
            _panel_line(f"{_GOLD}Open an account to access deposits, withdrawals,{_N}"),
            _panel_line(f"{_GOLD}and secure wire transfers.{_N}"),
            _panel_line(),
            _panel_close(),
        ])
        options = [
            {"key": "1", "desc": f"{_GOLD}Open account{_N}", "goto": ("node_open_account", {"terminal": terminal})},
            {"key": "q", "desc": f"{_DIM}Disconnect{_N}",    "goto": "node_bank_exit"},
        ]
        return text, options

    text = "\n".join([
        _format_balance_panel(caller),
    ])
    options = [
        {"key": "1", "desc": "Check balance",           "goto": ("node_balance",  {"terminal": terminal})},
        {"key": "2", "desc": f"{_OK}Deposit funds{_N}", "goto": ("node_deposit",  {"terminal": terminal})},
        {"key": "3", "desc": f"{_GOLD}Withdraw funds{_N}", "goto": ("node_withdraw", {"terminal": terminal})},
        {"key": "4", "desc": f"{_ACCENT}Wire transfer{_N}", "goto": ("node_wire",    {"terminal": terminal})},
        {"key": "5", "desc": "Transaction log",          "goto": ("node_txlog",    {"terminal": terminal})},
        {"key": "q", "desc": f"{_DIM}Disconnect{_N}",   "goto": "node_bank_exit"},
    ]
    return text, options


def node_open_account(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)

    if raw_string.strip().lower() in ("yes", "y", "1"):
        ok, msg = open_account(caller)
        if ok:
            text = "\n".join([
                _panel_header("ACCOUNT OPENED", subtitle="Registration successful."),
                _panel_line(),
                _panel_line(f"{_OK}Welcome, {caller.key}.{_N}"),
                _panel_line(),
                _panel_line("Your account has been created and linked to your"),
                _panel_line("Matrix identity. You may now deposit, withdraw,"),
                _panel_line("and wire funds securely."),
                _panel_line(),
                _panel_close(),
            ])
        else:
            text = "\n".join([
                _panel_header("BANK OF THE FRAME", subtitle="Registration failed."),
                _panel_line(),
                _panel_line(f"{_ERR}{msg}{_N}"),
                _panel_line(),
                _panel_close(),
            ])
        return text, [{"key": "1", "desc": "Continue", "goto": ("node_bank_main", {"terminal": terminal})}]

    text = "\n".join([
        _panel_header("OPEN NEW ACCOUNT", subtitle="Frame Financial Network registration."),
        _panel_line(),
        _panel_line("Opening an account links your identity to the"),
        _panel_line("Frame banking network. Deposits are secured and"),
        _panel_line("accessible from any registered terminal."),
        _panel_line(),
        _panel_line(f"{_WARN}One account per identity. This cannot be undone.{_N}"),
        _panel_line(),
        _panel_close(),
    ])
    options = [
        {"key": "yes", "desc": f"{_OK}Confirm — open account{_N}", "goto": ("node_open_account", {"terminal": terminal})},
        {"key": "q",   "desc": f"{_DIM}Cancel{_N}",                "goto": ("node_bank_main",    {"terminal": terminal})},
    ]
    return text, options


def node_balance(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    text = _format_balance_panel(caller)
    options = [
        {"key": "q", "desc": f"{_DIM}Back{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_deposit(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    raw = raw_string.strip()

    if raw and raw.lower() not in ("deposit", "2"):
        try:
            amount = int(raw.replace(",", ""))
        except ValueError:
            text = "\n".join([
                _panel_header("DEPOSIT", subtitle="Invalid input."),
                _panel_line(),
                _panel_line(f"{_ERR}Enter a numeric amount.{_N}"),
                _panel_line(),
                _panel_close(),
            ])
            return text, [
                {"key": "q", "desc": f"{_DIM}Back{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
            ]

        ok, msg = bank_deposit(caller, amount)
        status = f"{_OK}{msg}{_N}" if ok else f"{_ERR}{msg}{_N}"
        text = "\n".join([
            _panel_header("DEPOSIT", subtitle="Transaction processed." if ok else "Transaction failed."),
            _panel_line(),
            _panel_line(status),
            _panel_line(),
            _panel_section("UPDATED BALANCE"),
            _panel_kv("On Hand", format_currency(get_balance(caller))),
            _panel_kv("In Bank", format_currency(get_bank_balance(caller))),
            _panel_line(),
            _panel_close(),
        ])
        options = [
            {"key": "1", "desc": f"{_OK}Deposit more{_N}",  "goto": ("node_deposit",   {"terminal": terminal})},
            {"key": "q", "desc": f"{_DIM}Back to menu{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
        ]
        return text, options

    wallet = get_balance(caller)
    text = "\n".join([
        _panel_header("DEPOSIT", subtitle="Transfer on-hand cash into your account."),
        _panel_line(),
        _panel_kv("On Hand", format_currency(wallet)),
        _panel_kv("In Bank", format_currency(get_bank_balance(caller))),
        _panel_line(),
        _panel_line(f"Enter the amount to deposit, or {_DIM}q{_N} to cancel."),
        _panel_line(),
        _panel_close(),
    ])
    options = [
        {"key": "_default", "goto": ("node_deposit", {"terminal": terminal})},
        {"key": "q", "desc": f"{_DIM}Cancel{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_withdraw(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    raw = raw_string.strip()

    if raw and raw.lower() not in ("withdraw", "3"):
        try:
            amount = int(raw.replace(",", ""))
        except ValueError:
            text = "\n".join([
                _panel_header("WITHDRAW", subtitle="Invalid input."),
                _panel_line(),
                _panel_line(f"{_ERR}Enter a numeric amount.{_N}"),
                _panel_line(),
                _panel_close(),
            ])
            return text, [
                {"key": "q", "desc": f"{_DIM}Back{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
            ]

        ok, msg = bank_withdraw(caller, amount)
        status = f"{_OK}{msg}{_N}" if ok else f"{_ERR}{msg}{_N}"
        text = "\n".join([
            _panel_header("WITHDRAW", subtitle="Transaction processed." if ok else "Transaction failed."),
            _panel_line(),
            _panel_line(status),
            _panel_line(),
            _panel_section("UPDATED BALANCE"),
            _panel_kv("On Hand", format_currency(get_balance(caller))),
            _panel_kv("In Bank", format_currency(get_bank_balance(caller))),
            _panel_line(),
            _panel_close(),
        ])
        options = [
            {"key": "1", "desc": f"{_GOLD}Withdraw more{_N}", "goto": ("node_withdraw",  {"terminal": terminal})},
            {"key": "q", "desc": f"{_DIM}Back to menu{_N}",   "goto": ("node_bank_main", {"terminal": terminal})},
        ]
        return text, options

    bank_bal = get_bank_balance(caller)
    text = "\n".join([
        _panel_header("WITHDRAW", subtitle="Transfer funds from account to on-hand cash."),
        _panel_line(),
        _panel_kv("Available", format_currency(bank_bal)),
        _panel_line(),
        _panel_line(f"Enter the amount to withdraw, or {_DIM}q{_N} to cancel."),
        _panel_line(),
        _panel_close(),
    ])
    options = [
        {"key": "_default", "goto": ("node_withdraw", {"terminal": terminal})},
        {"key": "q", "desc": f"{_DIM}Cancel{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_wire(caller, raw_string, **kwargs):
    """Wire transfer — step 1: enter recipient network ID."""
    terminal = _get_terminal(caller, kwargs)
    raw = raw_string.strip()

    if raw and raw.lower() not in ("wire transfer", "4"):
        return node_wire_amount(caller, "", terminal=terminal, recipient_id=raw)

    text = "\n".join([
        _panel_header("WIRE TRANSFER", subtitle="Matrix-routed bank-to-bank transfer."),
        _panel_line(),
        _panel_kv("Your Bank", format_currency(get_bank_balance(caller))),
        _panel_kv("Fee", f"{WIRE_FEE_PERCENT}% of amount"),
        _panel_line(),
        _panel_line(f"Enter recipient {_LABEL}@alias{_N} or {_LABEL}^MatrixID{_N}."),
        _panel_line(f"{_WARN}Requires active Matrix signal to complete.{_N}"),
        _panel_line(),
        _panel_close(),
    ])
    options = [
        {"key": "_default", "goto": ("node_wire", {"terminal": terminal})},
        {"key": "q", "desc": f"{_DIM}Cancel{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_wire_amount(caller, raw_string, **kwargs):
    """Wire transfer — step 2: enter amount."""
    terminal = _get_terminal(caller, kwargs)
    recipient_id = kwargs.get("recipient_id", "")
    raw = raw_string.strip()

    if raw and raw != recipient_id:
        try:
            amount = int(raw.replace(",", ""))
        except ValueError:
            text = "\n".join([
                _panel_header("WIRE TRANSFER", subtitle="Invalid amount."),
                _panel_line(),
                _panel_line(f"{_ERR}Enter a numeric amount.{_N}"),
                _panel_line(),
                _panel_close(),
            ])
            return text, [
                {"key": "q", "desc": f"{_DIM}Back{_N}", "goto": ("node_wire", {"terminal": terminal})},
            ]
        return node_wire_confirm(caller, "", terminal=terminal, recipient_id=recipient_id, amount=amount)

    text = "\n".join([
        _panel_header("WIRE TRANSFER", subtitle="Step 2 of 3 — enter amount."),
        _panel_line(),
        _panel_kv("Recipient", f"{_ACCENT}{recipient_id}{_N}"),
        _panel_kv("Your Bank", format_currency(get_bank_balance(caller))),
        _panel_line(),
        _panel_line(f"Enter the amount to wire, or {_DIM}q{_N} to cancel."),
        _panel_line(),
        _panel_close(),
    ])
    options = [
        {"key": "_default", "goto": ("node_wire_amount", {"terminal": terminal, "recipient_id": recipient_id})},
        {"key": "q", "desc": f"{_DIM}Cancel{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_wire_confirm(caller, raw_string, **kwargs):
    """Wire transfer — step 3: confirm."""
    terminal = _get_terminal(caller, kwargs)
    recipient_id = kwargs.get("recipient_id", "")
    amount = int(kwargs.get("amount", 0))
    raw = raw_string.strip().lower()

    if raw in ("yes", "y", "confirm", "1"):
        from world.utils import get_containing_room
        from world.network_utils import room_has_network_coverage
        room = get_containing_room(caller)
        if not room_has_network_coverage(room, include_matrix_nodes=True):
            text = "\n".join([
                _panel_header("WIRE TRANSFER", subtitle="Signal lost."),
                _panel_line(),
                _panel_line(f"{_ERR}No Matrix signal detected.{_N}"),
                _panel_line("Wire transfers require active network coverage."),
                _panel_line(),
                _panel_close(),
            ])
            return text, [
                {"key": "q", "desc": f"{_DIM}Back to menu{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
            ]

        ok, msg, recip_name, fee = bank_wire(caller, recipient_id, amount)
        if ok:
            text = "\n".join([
                _panel_header("TRANSFER COMPLETE", subtitle="Funds dispatched via Matrix routing."),
                _panel_line(),
                _panel_kv("Sent",      f"{_OK}{format_currency(amount, color=False)}{_N}"),
                _panel_kv("Fee",       format_currency(fee)),
                _panel_kv("Recipient", f"{_ACCENT}{recip_name}{_N}"),
                _panel_line(),
                _panel_section("UPDATED BALANCE"),
                _panel_kv("In Bank", format_currency(get_bank_balance(caller))),
                _panel_line(),
                _panel_line(f"{_DIM}Transfer logged to your transaction history.{_N}"),
                _panel_line(),
                _panel_close(),
            ])
        else:
            text = "\n".join([
                _panel_header("TRANSFER FAILED", subtitle="Transaction could not be completed."),
                _panel_line(),
                _panel_line(f"{_ERR}{msg}{_N}"),
                _panel_line(),
                _panel_close(),
            ])
        return text, [
            {"key": "q", "desc": f"{_DIM}Back to menu{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
        ]

    fee = _compute_wire_fee(amount)
    total = amount + fee
    text = "\n".join([
        _panel_header("CONFIRM WIRE TRANSFER", subtitle="Step 3 of 3 — review and confirm."),
        _panel_line(),
        _panel_kv("To",     f"{_ACCENT}{recipient_id}{_N}"),
        _panel_kv("Amount", format_currency(amount)),
        _panel_kv("Fee",    f"{format_currency(fee)}  {_DIM}({WIRE_FEE_PERCENT}%){_N}"),
        _panel_kv("Total",  f"{_GOLD}{format_currency(total, color=False)}{_N}"),
        _panel_line(),
        _panel_line(f"{_WARN}Deducted from your bank account.{_N}"),
        _panel_line(f"{_WARN}Requires active Matrix signal.{_N}"),
        _panel_line(),
        _panel_line(f"Type {_LABEL}yes{_N} to confirm."),
        _panel_line(),
        _panel_close(),
    ])
    options = [
        {"key": "yes", "desc": f"{_OK}Confirm transfer{_N}",
         "goto": ("node_wire_confirm", {"terminal": terminal, "recipient_id": recipient_id, "amount": amount})},
        {"key": "q",   "desc": f"{_DIM}Cancel{_N}",
         "goto": ("node_bank_main", {"terminal": terminal})},
        {"key": "_default",
         "goto": ("node_wire_confirm", {"terminal": terminal, "recipient_id": recipient_id, "amount": amount})},
    ]
    return text, options


def node_txlog(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    text = format_transaction_log(caller)
    options = [
        {"key": "q", "desc": f"{_DIM}Back{_N}", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_bank_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}Terminal session closed.{_N}")
    return None, None
