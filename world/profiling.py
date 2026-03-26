"""
Performance profiling for the server.

Always-on metrics (no flag needed):
  - Command rate (rolling 1-minute, 10s bucket-based — O(1) write)
  - Script tick durations (one time.monotonic() per tick — negligible)
  - ScriptDB/RSS baselines (set at server start)

Opt-in timing (requires @profiling/timing):
  - Per-command wall-clock time (p50/p95/max)
  - Per-command DB query count (requires settings.DEBUG = True)

Budgets are calibrated for 300 concurrent users (~7 cmds/user/min peak).

All state is module-level (ephemeral — cleared on reload by design).
Baselines are reset in at_server_startstop.at_server_start() each boot.
"""

import time
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# Budget targets — calibrated for 300 concurrent users
# ---------------------------------------------------------------------------
BUDGETS = {
    "cmd_rate_per_min": 2000,   # 300 users × ~7 cmds/min
    "cmd_avg_ms":       15,
    "cmd_p95_ms":       75,
    "cmd_max_ms":       200,
    "cmd_queries_avg":  10,
    "cmd_queries_warn": 25,
    "script_tick_pct":  0.10,   # max fraction of interval consumed by a single tick
}

_SAMPLES_CAP = 100  # ms_samples list is capped at this many entries per command


# ---------------------------------------------------------------------------
# Module-level storage (replaces script.ndb.* — same semantics, no DB overhead)
# ---------------------------------------------------------------------------
_cmd_rate_buckets: dict = {}
_cmd_counts: dict = {}
_script_ticks: dict = {}
_object_counts: dict = {}

_timing_enabled: bool = False
_start_time: float = 0.0
_script_count_baseline: int = 0
_rss_baseline_kb: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_timing_enabled() -> bool:
    return _timing_enabled


def get_cmd_rate_1min() -> int:
    """Rolling 1-minute command count using 10-second buckets."""
    now_bucket = int(time.time() // 10)
    return sum(v for k, v in _cmd_rate_buckets.items() if now_bucket - k <= 6)


def get_p95(samples):
    """95th-percentile value from a list of floats."""
    if not samples:
        return 0.0
    s = sorted(samples)
    idx = min(int(len(s) * 0.95), len(s) - 1)
    return s[idx]


# ---------------------------------------------------------------------------
# Instrumentation — called from commands/base_cmds.py
# ---------------------------------------------------------------------------

def record_command_start(cmd):
    """
    Called from Command.at_pre_cmd.

    Always: increments the rolling rate bucket.
    If timing enabled: stamps _prof_start and _prof_queries on the command instance.
    """
    global _cmd_rate_buckets
    try:
        bucket = int(time.time() // 10)
        _cmd_rate_buckets[bucket] = _cmd_rate_buckets.get(bucket, 0) + 1
        # Trim entries older than 8 buckets (80s) to bound memory
        cutoff = bucket - 7
        _cmd_rate_buckets = {k: v for k, v in _cmd_rate_buckets.items() if k >= cutoff}

        if _timing_enabled:
            cmd._prof_start = time.monotonic()
            try:
                from django.db import connection
                cmd._prof_queries = len(connection.queries)
            except Exception:
                cmd._prof_queries = 0
    except Exception:
        pass


def record_command_end(cmd):
    """
    Called from Command.at_post_cmd.

    Records elapsed ms and query count if timing was stamped by record_command_start.
    No-op if timing is off or command was blocked before func() ran.
    """
    global _cmd_counts
    start = getattr(cmd, '_prof_start', None)
    if start is None:
        return
    try:
        elapsed_ms = (time.monotonic() - start) * 1000

        try:
            from django.db import connection
            queries = max(0, len(connection.queries) - getattr(cmd, '_prof_queries', 0))
        except Exception:
            queries = 0

        key = getattr(cmd, 'key', None) or 'unknown'
        entry = _cmd_counts.get(key)
        if entry is None:
            entry = {
                "calls": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "total_queries": 0,
                "ms_samples": [],
            }
        entry["calls"] += 1
        entry["total_ms"] += elapsed_ms
        if elapsed_ms > entry["max_ms"]:
            entry["max_ms"] = elapsed_ms
        entry["total_queries"] += queries

        samples = entry["ms_samples"]
        samples.append(elapsed_ms)
        if len(samples) > _SAMPLES_CAP:
            entry["ms_samples"] = samples[-_SAMPLES_CAP:]

        _cmd_counts[key] = entry
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Object count snapshots — called from cleanup scripts (zero extra queries)
# ---------------------------------------------------------------------------

def snapshot_object_counts(counts_dict):
    """
    Merge counts_dict into _object_counts.

    Call this at the end of cleanup script runs with counts derived from
    querysets already evaluated during the cleanup — no extra DB queries.

    counts_dict: e.g. {"MatrixNode": 42, "Handset": 17}
    """
    global _object_counts
    try:
        _object_counts.update(counts_dict)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tick timing — context manager for global script at_repeat() bodies
# ---------------------------------------------------------------------------

@contextmanager
def timed_tick(script_key, interval_s):
    """
    Wrap a global script's at_repeat() body to record tick duration.

    Always active (not gated behind timing flag) — overhead is one
    time.monotonic() call per tick (microseconds, for scripts that fire
    every 10–3600 seconds).

    Usage:
        def at_repeat(self):
            from world.profiling import timed_tick
            with timed_tick("stamina_regen", self.interval):
                stamina_regen_all()
    """
    global _script_ticks
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        try:
            entry = _script_ticks.get(script_key)
            if entry is None:
                entry = {
                    "calls": 0,
                    "total_ms": 0.0,
                    "max_ms": 0.0,
                    "last_ms": 0.0,
                    "interval_s": interval_s,
                }
            entry["calls"] += 1
            entry["total_ms"] += elapsed_ms
            if elapsed_ms > entry["max_ms"]:
                entry["max_ms"] = elapsed_ms
            entry["last_ms"] = elapsed_ms
            _script_ticks[script_key] = entry
        except Exception:
            pass
