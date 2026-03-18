"""
MedGuard App - Drug safety assessment application.

This is the main Django app containing:
- utils: Input normalization
- services: Business logic (treatment validation, interaction checking, etc.)
- orchestrator: Decision pipeline that ties everything together
"""

default_app_config = "medguard_app.apps.MedguardAppConfig"
