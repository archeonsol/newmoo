"""
Economy system: wallet helpers, currency formatting, and transaction logging.

The in-game currency name is defined by CURRENCY_NAME. Change it here and
every display string updates automatically. Code always uses 'money' /
'currency' / character.db.currency.

Wallet storage:
  character.db.currency       -- int, on-hand cash
  character.db.transaction_log -- list of dicts (rolling, max TRANSACTION_LOG_SIZE)

Transaction log entry shape:
  {
    "time":   float (unix timestamp),
    "type":   str   ("credit" | "debit" | "transfer_out" | "transfer_in"),
    "amount": int,
    "party":  str   (name/alias of other party, or "" for system),
    "reason": str,
  }
"""

import time

# ---------------------------------------------------------------------------
# IC currency name — change this single constant to rename the currency.
# ---------------------------------------------------------------------------
CURRENCY_NAME = "script"

# Rolling transaction log length per character.
TRANSACTION_LOG_SIZE = 20

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_currency(amount, color=True):
    """
    Return a display string for an amount of money.

    Examples:
      format_currency(1240)        -> "|w1,240 script|n"
      format_currency(1240, False) -> "1,240 script"
    """
    formatted = f"{int(amount):,} {CURRENCY_NAME}"
    if color:
        return f"|w{formatted}|n"
    return formatted


def format_currency_plain(amount):
    """Return uncolored currency string."""
    return format_currency(amount, color=False)


# ---------------------------------------------------------------------------
# Transaction log
# ---------------------------------------------------------------------------

def _append_transaction(character, entry):
    """Append a transaction entry to the character's rolling log."""
    log = list(character.db.transaction_log or [])
    log.append(entry)
    if len(log) > TRANSACTION_LOG_SIZE:
        log = log[-TRANSACTION_LOG_SIZE:]
    character.db.transaction_log = log


def _log_transaction(character, tx_type, amount, party="", reason=""):
    _append_transaction(character, {
        "time": time.time(),
        "type": tx_type,
        "amount": int(amount),
        "party": str(party),
        "reason": str(reason),
    })


# ---------------------------------------------------------------------------
# Wallet helpers
# ---------------------------------------------------------------------------

def get_balance(character):
    """Return the character's on-hand cash balance (int, never negative)."""
    return max(0, int(getattr(character.db, "currency", 0) or 0))


def add_funds(character, amount, party="", reason=""):
    """
    Add funds to a character's wallet.

    Returns the new balance.
    """
    amount = int(amount)
    if amount <= 0:
        return get_balance(character)
    current = get_balance(character)
    character.db.currency = current + amount
    _log_transaction(character, "credit", amount, party=party, reason=reason)
    return current + amount


def deduct_funds(character, amount, party="", reason=""):
    """
    Deduct funds from a character's wallet.

    Returns True on success, False if insufficient funds.
    Does not modify balance on failure.
    """
    amount = int(amount)
    if amount <= 0:
        return True
    current = get_balance(character)
    if current < amount:
        return False
    character.db.currency = current - amount
    _log_transaction(character, "debit", amount, party=party, reason=reason)
    return True


def transfer_funds(sender, recipient, amount, reason=""):
    """
    Transfer funds from sender to recipient atomically.

    Returns (success: bool, message: str).
    """
    amount = int(amount)
    if amount <= 0:
        return False, "Amount must be positive."

    current = get_balance(sender)
    if current < amount:
        return False, f"Insufficient funds. You have {format_currency(current)}."

    sender_name = getattr(sender, "key", str(sender))
    recipient_name = getattr(recipient, "key", str(recipient))

    # Atomic: deduct first, then credit.
    sender.db.currency = current - amount
    _log_transaction(sender, "transfer_out", amount, party=recipient_name, reason=reason)

    rec_current = get_balance(recipient)
    recipient.db.currency = rec_current + amount
    _log_transaction(recipient, "transfer_in", amount, party=sender_name, reason=reason)

    return True, f"Transferred {format_currency(amount)} to {recipient_name}."


# ---------------------------------------------------------------------------
# Transaction log display
# ---------------------------------------------------------------------------

_TX_TYPE_LABELS = {
    "credit":       "|g+ credit|n",
    "debit":        "|r- debit |n",
    "transfer_out": "|r- sent  |n",
    "transfer_in":  "|g+ recv  |n",
    "bank_deposit": "|y  deposit|n",
    "bank_withdraw":"|y  withdraw|n",
    "wire_out":     "|r- wire  |n",
    "wire_in":      "|g+ wire  |n",
}

_BOX_W = 60


def _box_line(char="═"):
    return f"|x{'═' * _BOX_W}|n"


def _box_row(text, pad_char=" "):
    from evennia.utils.ansi import strip_ansi
    visible = len(strip_ansi(text))
    padding = max(0, _BOX_W - 2 - visible)
    return f"|x║|n {text}{pad_char * padding} |x║|n"


def format_transaction_log(character, limit=TRANSACTION_LOG_SIZE):
    """
    Return a formatted string of the character's recent transactions.
    """
    log = list(character.db.transaction_log or [])
    if not log:
        return (
            f"\n{_box_line()}\n"
            f"{_box_row('|xNo transactions recorded.|n')}\n"
            f"{_box_line()}\n"
        )

    lines = [
        f"\n{_box_line()}",
        _box_row(f"|wRECENT TRANSACTIONS|n"),
        _box_line("─"),
    ]
    for entry in reversed(log[-limit:]):
        t = time.strftime("%m/%d %H:%M", time.localtime(entry.get("time", 0)))
        label = _TX_TYPE_LABELS.get(entry.get("type", ""), f"  {entry.get('type','?'):<8}")
        amt = format_currency(entry.get("amount", 0))
        party = entry.get("party", "")
        reason = entry.get("reason", "")
        detail = f"{party}" if party else ""
        if reason and reason != detail:
            detail = f"{detail} — {reason}" if detail else reason
        row = f"|x{t}|n  {label}  {amt}"
        lines.append(_box_row(row))
        if detail:
            lines.append(_box_row(f"  |x{detail[:_BOX_W - 6]}|n"))
    lines.append(_box_line())
    return "\n".join(lines)
