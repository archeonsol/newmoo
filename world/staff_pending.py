"""
Staff pending approvals: a reusable foundation for player requests that require
staff approval (custom sdesc gender terms, future: name changes, etc.).

- Pending jobs are stored in the PendingJob Django model.
- When a job is added, a message is sent to the staff_pending channel so staff see it.
- Staff use the @pending command to list, approve, or deny.
- Each job type has a resolver that applies the change (or not) and notifies the player.
"""

import uuid
from datetime import datetime, timezone

# Channel alias used by this system
STAFF_PENDING_CHANNEL_ALIAS = "staff_pending"


def _notify_staff_channel(job):
    """Send a notification to the staff pending channel so staff see new requests."""
    from evennia import create_channel, search_channel
    channels = search_channel(STAFF_PENDING_CHANNEL_ALIAS)
    if not channels:
        channel = create_channel(
            key=STAFF_PENDING_CHANNEL_ALIAS,
            aliases=["pending", "staffpending"],
            desc="Staff queue for pending approval requests (sdesc custom terms, etc.).",
            locks="listen:perm(Builder);send:perm(Builder);control:perm(Admin)",
        )
    else:
        channel = list(channels)[0] if hasattr(channels, "__iter__") else channels
    summary = _format_job_summary(job)
    if summary:
        try:
            channel.msg(summary, senders=None)
        except Exception:
            pass


def _format_job_summary(job):
    """One-line human-readable summary for channel and list. job is a dict."""
    job_type = job.get("type") or "unknown"
    full_id = job.get("id", "")
    short_id = full_id[:8] if len(full_id) >= 8 else full_id
    req_id = job.get("requester_id")
    requester_name = "#%s" % req_id if req_id else "?"
    if req_id is not None:
        from evennia import search_object
        objs = search_object("#%s" % req_id)
        try:
            obj = objs[0] if objs else None
        except (TypeError, IndexError):
            obj = None
        if obj is not None:
            requester_name = obj.get_display_name(None) if hasattr(obj, "get_display_name") else getattr(obj, "key", str(obj))
    payload = job.get("payload") or {}
    if job_type == "sdesc_gender_term":
        term = payload.get("term", "?")
        return "[Pending %s] %s requested custom sdesc gender term: |w%s|n (|wsdesc custom|n). Use |w@pending approve %s|n or |w@pending deny %s|n." % (short_id, requester_name, term, short_id, short_id)
    return "[Pending %s] %s: type=%s (use |w@pending approve %s|n or |w@pending deny %s|n)." % (short_id, requester_name, job_type, short_id, short_id)


def _job_to_dict(job):
    """Convert a PendingJob instance to the legacy dict format used by resolvers."""
    return {
        "id": job.job_id,
        "type": job.job_type,
        "requester_id": job.requester_id,
        "payload": job.payload,
        "created": job.created_at.isoformat() if job.created_at else "",
        "meta": job.meta,
    }


def add_pending(job_type, requester, payload, **meta):
    """
    Add a pending job. requester is the Character (or Object) requesting.

    Returns (job_id, True) on success, or (None, False) on error.
    """
    from world.models import PendingJob
    requester_id = getattr(requester, "id", None)
    if not requester_id:
        return None, False
    job_id = uuid.uuid4().hex
    try:
        PendingJob.objects.create(
            job_id=job_id,
            job_type=job_type,
            requester_id=requester_id,
            payload=dict(payload),
            meta=dict(meta),
        )
    except Exception:
        return None, False
    _notify_staff_channel({
        "id": job_id,
        "type": job_type,
        "requester_id": requester_id,
        "payload": dict(payload),
    })
    return job_id, True


def get_pending(job_type=None):
    """Return list of pending job dicts, optionally filtered by job_type."""
    from world.models import PendingJob
    qs = PendingJob.objects.all()
    if job_type:
        qs = qs.filter(job_type=job_type)
    return [_job_to_dict(j) for j in qs]


def get_by_id(job_id):
    """Return the job dict with the given id (full hex or 8-char prefix), or None."""
    if not job_id:
        return None
    from world.models import PendingJob
    job_id = job_id.strip().lower()
    try:
        job = PendingJob.objects.filter(job_id__startswith=job_id).first()
        return _job_to_dict(job) if job else None
    except Exception:
        return None


def resolve(job_id, approved, staff_member):
    """
    Resolve a pending job: approve or deny. Runs the type-specific handler,
    removes the job from the DB, and returns (success, message).
    """
    from world.models import PendingJob
    job_id = (job_id or "").strip().lower()
    try:
        job_obj = PendingJob.objects.filter(job_id__startswith=job_id).first()
    except Exception:
        job_obj = None
    if not job_obj:
        return False, "No pending job with that id."
    job = _job_to_dict(job_obj)
    handler = _RESOLVERS.get(job_obj.job_type)
    if not handler:
        return False, "Unknown job type: %s." % job_obj.job_type
    job_obj.delete()
    return handler(job, approved, staff_member)


def _resolve_sdesc_gender_term(job, approved, staff_member):
    """On approve: set character's sdesc_gender_term and sdesc_gender_term_custom. Notify requester."""
    from evennia import search_object
    req_id = job.get("requester_id")
    payload = job.get("payload") or {}
    term = (payload.get("term") or "").strip().lower()
    objs = search_object("#%s" % req_id) if req_id else []
    try:
        character = objs[0] if objs else None
    except (TypeError, IndexError):
        character = None
    if approved:
        if not term:
            return False, "Payload missing 'term'."
        if not character:
            return False, "Requester character no longer found."
        character.db.sdesc_gender_term = term
        character.db.sdesc_gender_term_custom = True
        try:
            character.msg("|gStaff approved your custom sdesc gender term. You will now appear as \"%s\" (e.g. a rangy %s).|n" % (term, term))
        except Exception:
            pass
        return True, "Approved: %s now has custom sdesc term |w%s|n." % (character.get_display_name(staff_member), term)
    else:
        if character:
            try:
                character.msg("|yYour request for a custom sdesc gender term was declined by staff.|n")
            except Exception:
                pass
        return True, "Denied."


# Register type-specific resolvers (approve/deny logic and notifications)
_RESOLVERS = {
    "sdesc_gender_term": _resolve_sdesc_gender_term,
}


def register_resolver(job_type, handler):
    """
    Register a resolver for a job type. Handler signature: (job, approved, staff_member) -> (success, message).
    Use this for future approval types (e.g. name changes, custom titles).
    """
    _RESOLVERS[job_type] = handler
