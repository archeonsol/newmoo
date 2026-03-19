"""
Custom online listing commands:
  - @who: show account names + each account's set message
  - @whomsg <message>: set your message shown by @who
"""

from __future__ import annotations

from evennia.commands.command import Command as BaseCommand
from evennia.utils.evmore import EvMore
from evennia.utils.utils import crop
import time


MAX_WHOMSG_LEN = 120
DEFAULT_WHOMSG = "hello world!"
ANON_KEY = "who_anonymous"


def _get_account(caller):
    """
    Return the Account object for either:
      - Account caller (logged in, but unpuppeted), or
      - Character caller (puppeted; has `.account`).
    """
    acct = getattr(caller, "account", None)
    return acct or caller


def _get_whomsg(account) -> str:
    raw = getattr(getattr(account, "db", None), "whomsg", None)
    msg = str(raw or "").replace("\r", " ").replace("\n", " ").strip()
    if not msg:
        return DEFAULT_WHOMSG
    return msg[:MAX_WHOMSG_LEN]


def _format_idle_seconds(seconds: float) -> str:
    """
    Render idle duration in a compact way:
      - under 60 minutes: show minutes specifically (e.g. 5m)
      - 60+ minutes: show whole hours only (e.g. 1h, 2h, 3h)
    """
    if seconds < 0:
        seconds = 0
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = int(minutes // 60)
    return f"{hours}h"


def _is_anonymous(account) -> bool:
    """
    Whether this account should be shown as Anonymous on @who.
    """
    if not hasattr(account, "db"):
        return False
    return bool(getattr(account.db, ANON_KEY, False))


class CmdWho(BaseCommand):
    """
    List who is currently online.

    Display format is strictly:
      account_name: whomsg
    """

    key = "@who"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        # Evennia may match @-prefixed commands even if the user types without
        # the prefix (due to CMD_IGNORE_PREFIXES). Guard so `who` behaves as
        # "not available" rather than acting like `@who`.
        raw = (self.raw_string or "").strip()
        if not raw.lower().startswith("@who"):
            self.msg(f"Command '{raw}' is not available. Type \"help\" for help.")
            return

        import evennia

        rows = []
        seen = set()

        for session in evennia.SESSION_HANDLER.get_sessions():
            if hasattr(session, "logged_in") and not session.logged_in:
                continue

            account = getattr(session, "account", None)
            if not account and hasattr(session, "get_account"):
                try:
                    account = session.get_account()
                except Exception:
                    account = None
            if not account:
                continue

            # Deduplicate sessions per account.
            acct_id = getattr(account, "id", None) or id(account)
            if acct_id in seen:
                continue
            seen.add(acct_id)

            username = getattr(account, "username", None) or getattr(account, "key", None) or getattr(account, "name", None)
            if not username:
                username = str(account)

            if _is_anonymous(account):
                username = "Anonymous"
            else:
                username = crop(str(username), 30) or str(username)
            idle_seconds = time.time() - getattr(session, "cmd_last_visible", time.time())
            rows.append((username, _get_whomsg(account), _format_idle_seconds(idle_seconds)))

        if not rows:
            self.msg("No one is currently online.")
            return

        # Stable order for readability.
        rows.sort(key=lambda r: r[0].lower())

        # If we have a lot of people, use EvMore to paginate.
        table = self.styled_table("|wAccount|n", "|wMessage|n", "|wIdle|n")
        for username, msg, idle in rows:
            table.add_row(username, msg, idle)
        header = self.styled_header("Online (@who)")
        output = f"{header}\n{table}"

        if len(rows) > 30:
            EvMore(self.caller, output)
        else:
            self.msg(output)


class CmdWhoMsg(BaseCommand):
    """
    Set the message shown next to your account in @who.

    Usage:
      @whomsg <message>

    Defaults to:
      hello world!
    """

    key = "@whomsg"
    aliases = ["@whomessage", "@whoMsg"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        raw = (self.raw_string or "").strip().lower()
        if not (raw.startswith("@whomsg") or raw.startswith("@whomessage")):
            # If someone types without the prefix (e.g. "whomsg"), behave like a normal nomatch.
            # This keeps `whomsg` from acting like `@whomsg`.
            self.msg(f"Command '{self.raw_string.strip()}' is not available. Type \"help\" for help.")
            return

        caller = self.caller
        account = _get_account(caller)
        raw = (self.args or "").strip()

        if not raw:
            current = _get_whomsg(account)
            self.msg(f"Your @who message is: {current}")
            self.msg("Usage: @whomsg <message>")
            return

        lowered = raw.lower()
        if lowered in ("clear", "reset", "default", "off", "none"):
            if hasattr(account, "db"):
                try:
                    # db access pattern varies a bit by Evennia version.
                    del account.db.whomsg
                except Exception:
                    account.db.whomsg = ""
            self.msg("Your @who message has been reset to the default.")
            return

        if len(raw) > MAX_WHOMSG_LEN:
            raw = raw[:MAX_WHOMSG_LEN]
            self.msg(f"Message truncated to {MAX_WHOMSG_LEN} characters.")

        if not hasattr(account, "db"):
            self.msg("No account database available; cannot set @whomsg.")
            return

        account.db.whomsg = raw
        self.msg("Your @who message has been set.")


class CmdWhoAnon(BaseCommand):
    """
    Toggle anonymous mode for @who.

    When enabled, your account name is shown as "Anonymous" in @who.

    Usage:
      @whoanon            - toggle anonymous mode on/off
    """

    key = "@whoanon"
    aliases = ["@whomodeanon", "@whomanon"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        account = _get_account(caller)
        raw = (self.args or "").strip().lower()

        if raw:
            self.msg('Usage: @whoanon (toggles anonymous mode on/off).')
            return

        if not hasattr(account, "db"):
            self.msg("No account database available; cannot change anonymous mode.")
            return

        current = _is_anonymous(account)
        setattr(account.db, ANON_KEY, not current)
        new_state = "enabled" if not current else "disabled"
        self.msg(f"Anonymous mode {new_state} for @who.")

