"""
Lark grammar parsers for complex command argument syntax.

Each parser provides a `parse_*(args)` function that returns a dict of
extracted fields on success, or None on failure. Callers fall back to their
existing manual split logic when None is returned, so behaviour is unchanged
if lark is unavailable or the input doesn't match the grammar.

Parsers defined here:
    parse_npc_summon(args)   — "@npc/summon name=template[/location]"
    parse_autopilot(args)    — "autopilot <sector> [via <waypoint>]"
"""

try:
    from lark import Lark, ParseError, UnexpectedInput
    _LARK_AVAILABLE = True
except ImportError:
    Lark = None
    ParseError = Exception
    UnexpectedInput = Exception
    _LARK_AVAILABLE = False

# ---------------------------------------------------------------------------
# @npc/summon grammar
# ---------------------------------------------------------------------------
# Syntax: name=template[/location]
# Examples:
#   Guard=guard_template
#   Guard=guard_template/slums
# ---------------------------------------------------------------------------

_NPC_SUMMON_GRAMMAR = r"""
    start: name "=" template ("/" location)?
    name:     FREETEXT
    template: FREETEXT
    location: FREETEXT
    FREETEXT: /[^=\/\n]+/
    %ignore /[ \t]+/
"""

_npc_summon_parser = Lark(_NPC_SUMMON_GRAMMAR, parser="earley") if _LARK_AVAILABLE else None


def parse_npc_summon(args: str) -> dict | None:
    """
    Parse "@npc/summon name=template[/location]" arguments.

    Returns:
        {"name": str, "template": str, "location": str | None}
        or None if parsing fails (caller should use manual split fallback).
    """
    if not _LARK_AVAILABLE or _npc_summon_parser is None:
        return None
    try:
        tree = _npc_summon_parser.parse(args.strip())
        result = {}
        for subtree in tree.children:
            key = subtree.data
            value = "".join(str(t) for t in subtree.children).strip()
            result[key] = value
        return {
            "name": result.get("name", ""),
            "template": result.get("template", ""),
            "location": result.get("location") or None,
        }
    except (ParseError, UnexpectedInput, Exception):
        return None


# ---------------------------------------------------------------------------
# autopilot grammar
# ---------------------------------------------------------------------------
# Syntax: <sector> [via <waypoint>]
# Examples:
#   slums
#   guild via market
# ---------------------------------------------------------------------------

_AUTOPILOT_GRAMMAR = r"""
    start: sector ("via" waypoint)?
    sector:   WORD
    waypoint: WORD
    WORD: /[a-zA-Z0-9_\-]+/
    %ignore /[ \t]+/
"""

_autopilot_parser = Lark(_AUTOPILOT_GRAMMAR, parser="earley") if _LARK_AVAILABLE else None


def parse_autopilot(args: str) -> dict | None:
    """
    Parse "autopilot <sector> [via <waypoint>]" arguments.

    Returns:
        {"sector": str, "waypoint": str | None}
        or None if parsing fails.
    """
    if not _LARK_AVAILABLE or _autopilot_parser is None:
        return None
    try:
        tree = _autopilot_parser.parse(args.strip())
        result = {}
        for subtree in tree.children:
            key = subtree.data
            value = "".join(str(t) for t in subtree.children).strip()
            result[key] = value
        return {
            "sector": result.get("sector", ""),
            "waypoint": result.get("waypoint") or None,
        }
    except (ParseError, UnexpectedInput, Exception):
        return None
