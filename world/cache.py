"""
Persistent disk cache singleton using diskcache.

Provides a module-level Cache instance that survives server reloads (unlike
module-level dicts which are cleared). Used for:
  - Tunnel graph serialisation (world/movement/tunnel_graph.py)
  - VOID_ROOM_ID persistence (typeclasses/exit_traversal.py)

Public API:
    get(key, default=None)  -> value or default
    set(key, value, expire=None)  -> None
    delete(key)  -> None
    clear()  -> None   (wipe entire cache — use sparingly)
"""

import os
import logging

logger = logging.getLogger("evennia")

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    _TENACITY_AVAILABLE = True
except ImportError:
    _TENACITY_AVAILABLE = False

# Cache directory: prefer a configurable env var, fall back to /tmp.
_CACHE_DIR = os.environ.get("MOOTEST_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", ".diskcache"))
_CACHE_SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB

_CACHE = None


def _init_diskcache():
    """Attempt to open the diskcache. Retried by tenacity if available."""
    import diskcache
    return diskcache.Cache(_CACHE_DIR, size_limit=_CACHE_SIZE_LIMIT)


def _get_cache():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        if _TENACITY_AVAILABLE:
            _init_with_retry = retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.1, max=2),
                reraise=True,
            )(_init_diskcache)
            _CACHE = _init_with_retry()
        else:
            _CACHE = _init_diskcache()
    except Exception as exc:
        logger.warning(f"[cache] diskcache unavailable after retries, using in-memory fallback: {exc}")
        _CACHE = _InMemoryFallback()
    return _CACHE


class _InMemoryFallback:
    """Minimal dict-backed fallback when diskcache is unavailable."""
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, expire=None):
        self._data[key] = value

    def delete(self, key):
        self._data.pop(key, None)

    def clear(self):
        self._data.clear()


def get(key: str, default=None):
    """Retrieve a value from the cache."""
    try:
        return _get_cache().get(key, default)
    except Exception:
        return default


def set(key: str, value, expire: int | None = None):
    """Store a value in the cache, optionally with an expiry in seconds."""
    try:
        if _TENACITY_AVAILABLE:
            _set_with_retry = retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=0.1, max=2),
                reraise=False,
            )(lambda: _get_cache().set(key, value, expire=expire))
            _set_with_retry()
        else:
            _get_cache().set(key, value, expire=expire)
    except Exception:
        pass


def delete(key: str):
    """Remove a key from the cache."""
    try:
        _get_cache().delete(key)
    except Exception:
        pass


def clear():
    """Wipe the entire cache. Use sparingly."""
    try:
        _get_cache().clear()
    except Exception:
        pass
