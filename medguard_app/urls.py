"""
MedGuard App URL Configuration.
"""

from django.urls import path

from . import views

app_name = "medguard_app"

urlpatterns = [
    # Main evaluation endpoint
    path("evaluate/", views.EvaluateDrugView.as_view(), name="evaluate"),

    # Health check
    path("health/", views.HealthCheckView.as_view(), name="health"),
]
