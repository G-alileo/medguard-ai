"""
MedGuard App Configuration.
"""

from django.apps import AppConfig


class MedguardAppConfig(AppConfig):
    """Configuration for the MedGuard application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "medguard_app"
    verbose_name = "MedGuard Drug Safety Assessment"

    def ready(self):
        """Initialize app when Django starts."""
        pass
