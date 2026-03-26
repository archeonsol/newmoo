"""
Custom Django models for the game.

These replace Script-based data stores that were using Evennia's attribute system
as a makeshift database:
  - PendingJob: replaces StaffPendingScript (was a pickled list in db.pending)
  - PCNote: replaces PCNoteStorage (was a pickled list in db.notes)

After adding or changing models here, run:
    evennia makemigrations world
    evennia migrate
"""

from django.db import models
from django.utils import timezone


class PendingJob(models.Model):
    """Staff approval queue entry (custom sdesc terms, future: name changes, etc.)."""

    job_id = models.CharField(max_length=32, unique=True)
    job_type = models.CharField(max_length=64, db_index=True)
    requester_id = models.IntegerField(db_index=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"PendingJob({self.job_type}, {self.job_id[:8]})"


class PCNote(models.Model):
    """A staff/player note attached to a character."""

    category = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=255)
    body = models.TextField()
    char_id = models.IntegerField(db_index=True)
    char_key = models.CharField(max_length=255)
    account_id = models.IntegerField(null=True, blank=True, db_index=True)
    account_key = models.CharField(max_length=255, blank=True)
    # Not auto_now_add so that data migration can set historical timestamps.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"PCNote({self.char_key}, {self.category}, #{self.pk})"
