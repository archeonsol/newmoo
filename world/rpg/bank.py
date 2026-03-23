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

from world.rpg.economy import (
    CURRENCY_NAME,
    TRANSACTION_LOG_SIZE,
    format_currency,
    format_transaction_log,
    get_balance,
    _log_transaction,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIRE_FEE_PERCENT = 1          # 1% fee on wire transfers
WIRE_MIN_FEE = 1              # Minimum fee in currency units
WIRE_MAX_AMOUNT = 999_999     # Safety cap per single wire

_W = 54                       # Box width (visible chars)
_N = "|n"
_DIM = "|x"
_LABEL = "|w"
_ACCENT = "|c"               # Cyan accent for bank UI
_WARN = "|y"
_ERR = "|r"

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
# UI helpers
# ---------------------------------------------------------------------------

def _hline(char="═"):
    return f"{_ACCENT}{'═' * _W}{_N}"


def _hline_thin():
    return f"{_DIM}{'─' * _W}{_N}"


def _row(text, fill=" "):
    from evennia.utils.ansi import strip_ansi
    visible = len(strip_ansi(text))
    pad = max(0, _W - 2 - visible)
    return f"{_ACCENT}║{_N} {text}{fill * pad} {_ACCENT}║{_N}"


def _header(title):
    from evennia.utils.ansi import strip_ansi
    visible = len(strip_ansi(title))
    pad_total = max(0, _W - 2 - visible)
    pad_l = pad_total // 2
    pad_r = pad_total - pad_l
    return (
        f"{_hline()}\n"
        f"{_ACCENT}║{_N}{' ' * pad_l}{title}{' ' * pad_r}{_ACCENT}║{_N}\n"
        f"{_hline()}"
    )


def _format_balance_panel(character):
    wallet = get_balance(character)
    bank = get_bank_balance(character) if has_account(character) else None
    opened = getattr(character.db, "bank_account_opened", None)
    opened_str = time.strftime("%Y-%m-%d", time.localtime(opened)) if opened else "—"

    lines = [
        _header(f"{_ACCENT}BANK OF THE FRAME{_N}"),
        _row(""),
        _row(f"{_LABEL}Account Holder:{_N}  {character.key}"),
        _row(f"{_LABEL}Opened:{_N}          {_DIM}{opened_str}{_N}"),
        _row(""),
        _hline_thin(),
        _row(f"{_LABEL}On Hand:{_N}   {format_currency(wallet)}"),
    ]
    if bank is not None:
        lines.append(_row(f"{_LABEL}Bank:{_N}      {format_currency(bank)}"))
        lines.append(_row(f"{_LABEL}Total:{_N}     {format_currency(wallet + bank)}"))
    lines.append(_hline_thin())
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
        text = (
            f"{_header(f'{_ACCENT}BANK OF THE FRAME{_N}')}\n\n"
            f"  {_DIM}No account found for {caller.key}.{_N}\n\n"
            f"  Open a new account to access banking services.\n\n"
            f"{_hline_thin()}"
        )
        options = [
            {"key": "1", "desc": "Open account", "goto": ("node_open_account", {"terminal": terminal})},
            {"key": "q", "desc": "Exit terminal", "goto": "node_bank_exit"},
        ]
        return text, options

    text = (
        f"{_format_balance_panel(caller)}\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "1", "desc": "Check balance",    "goto": ("node_balance",     {"terminal": terminal})},
        {"key": "2", "desc": "Deposit funds",    "goto": ("node_deposit",     {"terminal": terminal})},
        {"key": "3", "desc": "Withdraw funds",   "goto": ("node_withdraw",    {"terminal": terminal})},
        {"key": "4", "desc": "Wire transfer",    "goto": ("node_wire",        {"terminal": terminal})},
        {"key": "5", "desc": "Transaction log",  "goto": ("node_txlog",       {"terminal": terminal})},
        {"key": "q", "desc": "Exit terminal",    "goto": "node_bank_exit"},
    ]
    return text, options


def node_open_account(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)

    if raw_string.strip().lower() in ("yes", "y", "1"):
        ok, msg = open_account(caller)
        if ok:
            text = (
                f"{_header(f'{_ACCENT}ACCOUNT OPENED{_N}')}\n\n"
                f"  {_LABEL}Welcome, {caller.key}.{_N}\n\n"
                f"  Your account has been created and linked to your\n"
                f"  Matrix identity. You may now deposit, withdraw,\n"
                f"  and wire funds securely.\n\n"
                f"{_hline_thin()}"
            )
        else:
            text = (
                f"{_header(f'{_ACCENT}BANK OF THE FRAME{_N}')}\n\n"
                f"  {_ERR}{msg}{_N}\n\n"
                f"{_hline_thin()}"
            )
        return text, [{"key": "1", "desc": "Continue", "goto": ("node_bank_main", {"terminal": terminal})}]

    text = (
        f"{_header(f'{_ACCENT}OPEN NEW ACCOUNT{_N}')}\n\n"
        f"  Opening an account links your identity to the\n"
        f"  Frame banking network. Deposits are secured and\n"
        f"  accessible from any registered terminal.\n\n"
        f"  {_WARN}One account per identity. This cannot be undone.{_N}\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "yes", "desc": "Confirm — open account", "goto": ("node_open_account", {"terminal": terminal})},
        {"key": "q",   "desc": "Cancel",                 "goto": ("node_bank_main",    {"terminal": terminal})},
    ]
    return text, options


def node_balance(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    text = (
        f"{_format_balance_panel(caller)}\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "q", "desc": "Back", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_deposit(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    raw = raw_string.strip()

    if raw and raw.lower() not in ("deposit", "2"):
        try:
            amount = int(raw.replace(",", ""))
        except ValueError:
            text = (
                f"{_header(f'{_ACCENT}DEPOSIT{_N}')}\n\n"
                f"  {_ERR}Invalid amount. Enter a number.{_N}\n\n"
                f"{_hline_thin()}"
            )
            return text, [
                {"key": "q", "desc": "Back", "goto": ("node_bank_main", {"terminal": terminal})},
            ]

        ok, msg = bank_deposit(caller, amount)
        result_color = "|g" if ok else _ERR
        text = (
            f"{_header(f'{_ACCENT}DEPOSIT{_N}')}\n\n"
            f"  {result_color}{msg}{_N}\n\n"
            f"{_format_balance_panel(caller)}\n\n"
            f"{_hline_thin()}"
        )
        options = [
            {"key": "1", "desc": "Deposit more",   "goto": ("node_deposit",  {"terminal": terminal})},
            {"key": "q", "desc": "Back to menu",   "goto": ("node_bank_main",{"terminal": terminal})},
        ]
        return text, options

    wallet = get_balance(caller)
    text = (
        f"{_header(f'{_ACCENT}DEPOSIT{_N}')}\n\n"
        f"  {_LABEL}On hand:{_N}  {format_currency(wallet)}\n"
        f"  {_LABEL}In bank:{_N}  {format_currency(get_bank_balance(caller))}\n\n"
        f"  Enter the amount to deposit, or {_DIM}q{_N} to cancel.\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "_default", "goto": ("node_deposit", {"terminal": terminal})},
        {"key": "q", "desc": "Cancel", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_withdraw(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    raw = raw_string.strip()

    if raw and raw.lower() not in ("withdraw", "3"):
        try:
            amount = int(raw.replace(",", ""))
        except ValueError:
            text = (
                f"{_header(f'{_ACCENT}WITHDRAW{_N}')}\n\n"
                f"  {_ERR}Invalid amount. Enter a number.{_N}\n\n"
                f"{_hline_thin()}"
            )
            return text, [
                {"key": "q", "desc": "Back", "goto": ("node_bank_main", {"terminal": terminal})},
            ]

        ok, msg = bank_withdraw(caller, amount)
        result_color = "|g" if ok else _ERR
        text = (
            f"{_header(f'{_ACCENT}WITHDRAW{_N}')}\n\n"
            f"  {result_color}{msg}{_N}\n\n"
            f"{_format_balance_panel(caller)}\n\n"
            f"{_hline_thin()}"
        )
        options = [
            {"key": "1", "desc": "Withdraw more",  "goto": ("node_withdraw", {"terminal": terminal})},
            {"key": "q", "desc": "Back to menu",   "goto": ("node_bank_main",{"terminal": terminal})},
        ]
        return text, options

    bank_bal = get_bank_balance(caller)
    text = (
        f"{_header(f'{_ACCENT}WITHDRAW{_N}')}\n\n"
        f"  {_LABEL}Available:{_N}  {format_currency(bank_bal)}\n\n"
        f"  Enter the amount to withdraw, or {_DIM}q{_N} to cancel.\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "_default", "goto": ("node_withdraw", {"terminal": terminal})},
        {"key": "q", "desc": "Cancel", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_wire(caller, raw_string, **kwargs):
    """Wire transfer — step 1: enter recipient network ID."""
    terminal = _get_terminal(caller, kwargs)
    raw = raw_string.strip()

    if raw and raw.lower() not in ("wire transfer", "4"):
        # Store recipient and move to amount entry
        return node_wire_amount(caller, "", terminal=terminal, recipient_id=raw)

    text = (
        f"{_header(f'{_ACCENT}WIRE TRANSFER{_N}')}\n\n"
        f"  Send funds directly to another account via the\n"
        f"  Matrix network. A {WIRE_FEE_PERCENT}% fee applies.\n\n"
        f"  {_LABEL}Your bank balance:{_N}  {format_currency(get_bank_balance(caller))}\n\n"
        f"  Enter the recipient's {_LABEL}@alias{_N} or {_LABEL}^MatrixID{_N},\n"
        f"  or {_DIM}q{_N} to cancel.\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "_default", "goto": ("node_wire", {"terminal": terminal})},
        {"key": "q", "desc": "Cancel", "goto": ("node_bank_main", {"terminal": terminal})},
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
            text = (
                f"{_header(f'{_ACCENT}WIRE TRANSFER{_N}')}\n\n"
                f"  {_ERR}Invalid amount.{_N}\n\n"
                f"{_hline_thin()}"
            )
            return text, [
                {"key": "q", "desc": "Back", "goto": ("node_wire", {"terminal": terminal})},
            ]
        return node_wire_confirm(caller, "", terminal=terminal, recipient_id=recipient_id, amount=amount)

    text = (
        f"{_header(f'{_ACCENT}WIRE TRANSFER{_N}')}\n\n"
        f"  {_LABEL}Recipient:{_N}  {recipient_id}\n\n"
        f"  Enter the amount to wire, or {_DIM}q{_N} to cancel.\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "_default", "goto": ("node_wire_amount", {"terminal": terminal, "recipient_id": recipient_id})},
        {"key": "q", "desc": "Cancel", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_wire_confirm(caller, raw_string, **kwargs):
    """Wire transfer — step 3: confirm."""
    terminal = _get_terminal(caller, kwargs)
    recipient_id = kwargs.get("recipient_id", "")
    amount = int(kwargs.get("amount", 0))
    raw = raw_string.strip().lower()

    if raw in ("yes", "y", "confirm", "1"):
        # Check signal coverage
        from world.utils import get_containing_room, room_has_network_coverage
        room = get_containing_room(caller)
        if not room_has_network_coverage(room, include_matrix_nodes=True):
            text = (
                f"{_header(f'{_ACCENT}WIRE TRANSFER{_N}')}\n\n"
                f"  {_ERR}No Matrix signal. Wire transfer requires network coverage.{_N}\n\n"
                f"{_hline_thin()}"
            )
            return text, [
                {"key": "q", "desc": "Back to menu", "goto": ("node_bank_main", {"terminal": terminal})},
            ]

        ok, msg, recip_name, fee = bank_wire(caller, recipient_id, amount)
        if ok:
            text = (
                f"{_header(f'{_ACCENT}TRANSFER COMPLETE{_N}')}\n\n"
                f"  {_LABEL}Sent:{_N}      {format_currency(amount)}\n"
                f"  {_LABEL}Fee:{_N}       {format_currency(fee)}\n"
                f"  {_LABEL}Recipient:{_N} {recip_name}\n\n"
                f"  {_DIM}Transfer logged.{_N}\n\n"
                f"{_hline_thin()}"
            )
        else:
            text = (
                f"{_header(f'{_ACCENT}TRANSFER FAILED{_N}')}\n\n"
                f"  {_ERR}{msg}{_N}\n\n"
                f"{_hline_thin()}"
            )
        return text, [
            {"key": "q", "desc": "Back to menu", "goto": ("node_bank_main", {"terminal": terminal})},
        ]

    if raw and raw not in ("wire transfer", "4", recipient_id, str(amount)):
        # Unrecognized input — re-show confirmation
        pass

    fee = _compute_wire_fee(amount)
    total = amount + fee
    text = (
        f"{_header(f'{_ACCENT}CONFIRM WIRE TRANSFER{_N}')}\n\n"
        f"  {_LABEL}To:{_N}       {recipient_id}\n"
        f"  {_LABEL}Amount:{_N}   {format_currency(amount)}\n"
        f"  {_LABEL}Fee:{_N}      {format_currency(fee)}  ({WIRE_FEE_PERCENT}%)\n"
        f"  {_LABEL}Total:{_N}    {format_currency(total)}\n\n"
        f"  {_WARN}Funds are deducted from your bank account.{_N}\n"
        f"  Requires active Matrix signal to complete.\n\n"
        f"  Type {_LABEL}yes{_N} to confirm.\n\n"
        f"{_hline_thin()}"
    )
    options = [
        {"key": "yes",     "desc": "Confirm transfer",
         "goto": ("node_wire_confirm", {"terminal": terminal, "recipient_id": recipient_id, "amount": amount})},
        {"key": "q",       "desc": "Cancel",
         "goto": ("node_bank_main", {"terminal": terminal})},
        {"key": "_default",
         "goto": ("node_wire_confirm", {"terminal": terminal, "recipient_id": recipient_id, "amount": amount})},
    ]
    return text, options


def node_txlog(caller, raw_string, **kwargs):
    terminal = _get_terminal(caller, kwargs)
    text = format_transaction_log(caller)
    options = [
        {"key": "q", "desc": "Back", "goto": ("node_bank_main", {"terminal": terminal})},
    ]
    return text, options


def node_bank_exit(caller, raw_string, **kwargs):
    caller.msg(f"{_DIM}Terminal session closed.{_N}")
    return None, None
