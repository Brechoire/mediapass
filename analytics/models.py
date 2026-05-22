"""Models for tracking website analytics."""

import uuid

from django.contrib.auth import get_user_model
from django.db import models


class PageVisit(models.Model):
    """Model for tracking page visits."""

    DEVICE_CHOICES = [
        ("desktop", "Desktop"),
        ("mobile", "Mobile"),
        ("tablet", "Tablet"),
    ]

    url = models.CharField(max_length=2000)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        get_user_model(), null=True, blank=True, on_delete=models.SET_NULL,
        related_name="page_visits"
    )
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.CharField(max_length=1000)
    referrer = models.CharField(max_length=2000, null=True, blank=True)
    device_type = models.CharField(
        max_length=20, choices=DEVICE_CHOICES, default="desktop"
    )
    session_id = models.CharField(max_length=100, default=uuid.uuid4)
    time_spent = models.IntegerField(default=0)  # temps en secondes
    is_bounce = models.BooleanField(default=True, db_index=True)

    class Meta:
        """Meta options for PageVisit model."""

        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["url"]),
            models.Index(fields=["user"]),
            models.Index(fields=["device_type"]),
            models.Index(fields=["session_id"]),
            models.Index(fields=["ip_address", "url", "-timestamp"]),
        ]

    def __str__(self):
        """Return string representation of PageVisit."""
        return f"{self.url} - {self.timestamp}"
