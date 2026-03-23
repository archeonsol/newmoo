"""
Structured game event logging via structlog.

Configures structlog once with a JSON renderer backed by Evennia's stdlib
logger. All game systems should use get_logger(__name__) from this module
for structured event logging.

Usage:
    from world.gamelog import get_logger
    log = get_logger(__name__)
    log.info("combat.hit", attacker="Alice", target="Bob", damage=12, weapon="knife")

Falls back to a plain stdlib logger if structlog is unavailable.
"""

import logging

try:
    import orjson as _orjson

    def _orjson_renderer(logger, method, event_dict):
        """structlog processor: serialise event_dict to JSON using orjson."""
        return _orjson.dumps(
            event_dict,
            option=_orjson.OPT_NON_STR_KEYS | _orjson.OPT_SERIALIZE_NUMPY,
        ).decode("utf-8")

    _json_renderer = _orjson_renderer
except ImportError:
    _json_renderer = None  # resolved below after structlog import


try:
    import structlog

    if _json_renderer is None:
        _json_renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _json_renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _STRUCTLOG_AVAILABLE = True

    def get_logger(name: str):
        """Return a structlog bound logger for the given module name."""
        return structlog.get_logger(name)

except ImportError:
    _STRUCTLOG_AVAILABLE = False

    def get_logger(name: str):  # type: ignore[misc]
        """Fallback: return a plain stdlib logger."""
        return logging.getLogger(name)
