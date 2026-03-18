"""
MedGuard API Views - REST endpoints for drug safety evaluation.

Provides the API bridge between the frontend and the decision pipeline.
"""

import json
import logging
from typing import Any

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .orchestrator import get_decision_pipeline

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class EvaluateDrugView(View):
    """
    Main API endpoint for drug safety evaluation.

    POST /api/evaluate/
    {
        "symptoms": ["headache", "fever"],
        "proposed_drug": "tylenol",
        "existing_drugs": ["aspirin", "lisinopril"]
    }

    Returns:
    {
        "success": true,
        "data": {
            "risk_score": 65,
            "risk_level": "HIGH",
            "explanation": "...",
            "findings": {...},
            "recommendation": {...}
        }
    }
    """

    def post(self, request) -> JsonResponse:
        """Handle POST request for drug evaluation."""
        try:
            # Parse JSON body
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError as e:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Invalid JSON in request body",
                        "details": str(e),
                    },
                    status=400,
                )

            # Validate required fields
            symptoms = data.get("symptoms", [])
            proposed_drug = data.get("proposed_drug", "")
            existing_drugs = data.get("existing_drugs", [])

            if not proposed_drug:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "Missing required field: proposed_drug",
                    },
                    status=400,
                )

            if not isinstance(symptoms, list):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "symptoms must be a list",
                    },
                    status=400,
                )

            if not isinstance(existing_drugs, list):
                return JsonResponse(
                    {
                        "success": False,
                        "error": "existing_drugs must be a list",
                    },
                    status=400,
                )

            # Get pipeline and evaluate
            pipeline = get_decision_pipeline()
            result = pipeline.evaluate(
                symptoms=symptoms,
                proposed_drug=proposed_drug,
                existing_drugs=existing_drugs,
            )

            logger.info(
                f"Evaluation complete: drug={proposed_drug}, "
                f"risk={result['risk_level']}, score={result['risk_score']}"
            )

            return JsonResponse(
                {
                    "success": True,
                    "data": result,
                },
                status=200,
            )

        except Exception as e:
            logger.error(f"Error in drug evaluation: {e}", exc_info=True)
            return JsonResponse(
                {
                    "success": False,
                    "error": "Internal server error during evaluation",
                    "details": str(e) if logger.isEnabledFor(logging.DEBUG) else None,
                },
                status=500,
            )

    def get(self, request) -> JsonResponse:
        """Handle GET request - return API info."""
        return JsonResponse(
            {
                "endpoint": "/api/evaluate/",
                "method": "POST",
                "description": "Evaluate drug safety for a given set of symptoms and medications",
                "required_fields": {
                    "proposed_drug": "string - The drug to evaluate",
                },
                "optional_fields": {
                    "symptoms": "list[string] - Current symptoms",
                    "existing_drugs": "list[string] - Current medications",
                },
                "example_request": {
                    "symptoms": ["headache", "fever"],
                    "proposed_drug": "ibuprofen",
                    "existing_drugs": ["aspirin", "lisinopril"],
                },
            },
            status=200,
        )


@method_decorator(csrf_exempt, name="dispatch")
class HealthCheckView(View):
    """Health check endpoint for monitoring."""

    def get(self, request) -> JsonResponse:
        """Return service health status."""
        return JsonResponse(
            {
                "status": "healthy",
                "service": "medguard-api",
                "version": "1.0.0",
            },
            status=200,
        )


# Function-based view alternatives (for simpler routing)
@csrf_exempt
def evaluate_drug(request) -> JsonResponse:
    """Function-based view for drug evaluation."""
    view = EvaluateDrugView()
    if request.method == "POST":
        return view.post(request)
    elif request.method == "GET":
        return view.get(request)
    else:
        return JsonResponse(
            {"error": "Method not allowed"},
            status=405,
        )


def health_check(request) -> JsonResponse:
    """Function-based health check."""
    return HealthCheckView().get(request)
