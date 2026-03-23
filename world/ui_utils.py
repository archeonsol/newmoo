"""
Shared UI rendering helpers for text menus/panels.
"""
import random

# ---------------------------------------------------------------------------
# wcwidth — display-accurate column alignment for double-width characters
# ---------------------------------------------------------------------------
try:
    from wcwidth import wcswidth as _wcswidth
    _WCWIDTH_AVAILABLE = True
except ImportError:
    _WCWIDTH_AVAILABLE = False


def display_ljust(text: str, width: int) -> str:
    """Left-justify text to display width, accounting for double-width characters."""
    if _WCWIDTH_AVAILABLE:
        try:
            dw = _wcswidth(text)
            if dw >= 0:
                pad = max(0, width - dw)
                return text + " " * pad
        except Exception:
            pass
    return text.ljust(width)


# ---------------------------------------------------------------------------
# pyfiglet — ASCII art title headers
# ---------------------------------------------------------------------------
try:
    import pyfiglet as _pyfiglet
    _PYFIGLET_AVAILABLE = True
except ImportError:
    _PYFIGLET_AVAILABLE = False


def figlet_banner(text: str, font: str = "small", width: int = 52, color: str = "|w", center: bool = False) -> str:
    """
    Render text as FIGlet ASCII art, cropped to width.
    Returns a colored multi-line string. Falls back to plain text if pyfiglet unavailable.

    If center=True, each line is padded with leading spaces to center it within `width`.

    Color is applied as a single prefix on each line so Evennia parses it correctly
    without double-processing from ANSIString wrappers in panel renderers.
    """
    if not _PYFIGLET_AVAILABLE:
        return f"{color}{text}|n"
    try:
        rendered = _pyfiglet.figlet_format(text, font=font, width=width)
        lines = rendered.rstrip("\n").split("\n")

        # Measure the natural art width before any escaping (plain ASCII, so len() is accurate).
        art_width = max((len(line) for line in lines if line.strip()), default=0)

        colored = []
        for line in lines:
            if line.strip():
                # FIGlet art contains raw | and \ characters. Evennia uses |
                # as its color-code prefix (|r, |n, etc.) and treats \| as an
                # escaped literal pipe. We must escape all pipes in the art as
                # || (Evennia's literal-pipe escape) before wrapping with color
                # tags, otherwise art characters get misread as color codes.
                safe = line.replace("|", "||")
                if center:
                    pad = max(0, (width - art_width) // 2)
                    safe = " " * pad + safe
                colored.append(f"{color}{safe}|n")
            else:
                colored.append("")
        return "\n".join(colored)
    except Exception:
        return f"{color}{text}|n"


# ---------------------------------------------------------------------------
# humanize — natural-language number and timestamp formatting
# ---------------------------------------------------------------------------
try:
    import humanize as _humanize
    _HUMANIZE_AVAILABLE = True
except ImportError:
    _HUMANIZE_AVAILABLE = False


def naturaltime(dt) -> str:
    """Return a human-readable relative time string, e.g. '3 minutes ago'."""
    if _HUMANIZE_AVAILABLE:
        try:
            return _humanize.naturaltime(dt)
        except Exception:
            pass
    import datetime as _datetime
    if isinstance(dt, (int, float)):
        dt = _datetime.datetime.fromtimestamp(dt)
    try:
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(dt)


def intword(n: int) -> str:
    """Return a formatted number string, e.g. '1.2 million' or '3,400'."""
    if _HUMANIZE_AVAILABLE:
        try:
            return _humanize.intword(n) if n >= 1_000_000 else _humanize.intcomma(n)
        except Exception:
            pass
    return f"{n:,}"


def fade_rule(
    width: int,
    ch: str = "─",
    start_ratio: float = 0.38,
    decay: float = 0.62,
    initial_gap: int = 1,
    gap_growth_every: int = 2,
    jitter: float = 0.2,
) -> str:
    """
    Build a left-to-right fading horizontal rule at a specific width.

    Args:
        width: Total number of characters to generate.
        ch: The glyph used for each visible segment.
        start_ratio: Initial solid-run size as a ratio of width.
        decay: Multiplier applied to each subsequent run length.
        initial_gap: Spaces inserted after the first run.
        gap_growth_every: Increase gap size every N segments.
        jitter: Random variation applied to each displayed run length, in [0, 1).
            0.0 is fully deterministic. 0.2 is a reasonable default for variation.
    """
    remaining = max(0, int(width))
    if remaining <= 0:
        return ""

    parts = []
    run = max(1, int(remaining * start_ratio))
    gap = max(1, int(initial_gap))
    step = 0

    while remaining > 0:
        if jitter > 0:
            display_run = max(1, int(run * random.uniform(1 - jitter, 1 + jitter)))
        else:
            display_run = run
        seg = min(display_run, remaining)
        parts.append(ch * seg)
        remaining -= seg
        if remaining <= 0:
            break

        space = min(gap, remaining)
        parts.append(" " * space)
        remaining -= space

        run = max(1, int(run * decay))
        if gap_growth_every > 0 and step % gap_growth_every == gap_growth_every - 1:
            gap += 1
        step += 1

    return "".join(parts)
