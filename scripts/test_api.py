#!/usr/bin/env python
import os
import sys
import json
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medguard.settings")

import django
django.setup()

from django.test import RequestFactory
from medguard_app.views import EvaluateDrugView, HealthCheckView


def test_health_check():
    """Test the health check endpoint."""
    print("\n[TEST 1] Health Check Endpoint")
    print("-" * 50)

    factory = RequestFactory()
    request = factory.get("/api/health/")

    view = HealthCheckView()
    response = view.get(request)

    print(f"Status Code: {response.status_code}")
    data = json.loads(response.content)
    print(f"Response: {json.dumps(data, indent=2)}")

    assert response.status_code == 200
    assert data["status"] == "healthy"
    print("[OK] Health check passed")


def test_evaluate_get_info():
    """Test GET request to evaluation endpoint (should return API info)."""
    print("\n[TEST 2] Evaluate Endpoint - GET (API Info)")
    print("-" * 50)

    factory = RequestFactory()
    request = factory.get("/api/evaluate/")

    view = EvaluateDrugView()
    response = view.get(request)

    print(f"Status Code: {response.status_code}")
    data = json.loads(response.content)
    print(f"Response: {json.dumps(data, indent=2)}")

    assert response.status_code == 200
    assert "endpoint" in data
    print("[OK] GET info passed")


def test_evaluate_low_risk():
    """Test low risk scenario."""
    print("\n[TEST 3] Evaluate - LOW RISK Scenario")
    print("-" * 50)

    factory = RequestFactory()
    payload = {
        "symptoms": ["headache", "fever"],
        "proposed_drug": "acetaminophen",
        "existing_drugs": [],
    }

    request = factory.post(
        "/api/evaluate/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    view = EvaluateDrugView()
    response = view.post(request)

    print(f"Status Code: {response.status_code}")
    data = json.loads(response.content)

    if response.status_code == 200:
        result = data.get("data", data)
        print(f"\nRisk Level: {result.get('risk_level')}")
        print(f"Risk Score: {result.get('risk_score')}")
        print(f"Treats Symptom: {result.get('findings', {}).get('treats_symptom')}")
        print(f"Interactions: {result.get('findings', {}).get('interactions_found')}")
        print(f"\nExplanation Preview:")
        explanation = result.get("explanation", "")[:200]
        print(f"{explanation}...")

        assert result["risk_level"] in ["LOW", "MEDIUM"]
        print("\n[OK] Low risk evaluation passed")
    else:
        print(f"Error: {data}")
        raise AssertionError("Request failed")


def test_evaluate_interaction_risk():
    """Test interaction risk scenario."""
    print("\n[TEST 4] Evaluate - INTERACTION RISK Scenario")
    print("-" * 50)

    factory = RequestFactory()
    payload = {
        "symptoms": ["blood clot prevention"],
        "proposed_drug": "warfarin",
        "existing_drugs": ["aspirin"],
    }

    request = factory.post(
        "/api/evaluate/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    view = EvaluateDrugView()
    response = view.post(request)

    print(f"Status Code: {response.status_code}")
    data = json.loads(response.content)

    if response.status_code == 200:
        result = data.get("data", data)
        print(f"\nRisk Level: {result.get('risk_level')}")
        print(f"Risk Score: {result.get('risk_score')}")
        print(f"Interactions Found: {result.get('findings', {}).get('interactions_found')}")

        interactions = result.get("findings", {}).get("interactions", [])
        if interactions:
            print(f"\nInteraction Details:")
            for interaction in interactions:
                print(f"  - {interaction.get('drug_pair')}: {interaction.get('severity')}")
                print(f"    {interaction.get('description', '')}")

        assert result.get("findings", {}).get("interactions_found", 0) > 0
        print("\n[OK] Interaction risk evaluation passed")
    else:
        print(f"Error: {data}")
        raise AssertionError("Request failed")


def test_evaluate_treatment_mismatch():
    """Test treatment mismatch scenario."""
    print("\n[TEST 5] Evaluate - TREATMENT MISMATCH Scenario")
    print("-" * 50)

    factory = RequestFactory()
    payload = {
        "symptoms": ["headache"],
        "proposed_drug": "metformin",  # Diabetes drug for headache
        "existing_drugs": [],
    }

    request = factory.post(
        "/api/evaluate/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    view = EvaluateDrugView()
    response = view.post(request)

    print(f"Status Code: {response.status_code}")
    data = json.loads(response.content)

    if response.status_code == 200:
        result = data.get("data", data)
        print(f"\nRisk Level: {result.get('risk_level')}")
        print(f"Risk Score: {result.get('risk_score')}")
        print(f"Treats Symptom: {result.get('findings', {}).get('treats_symptom')}")

        assert result.get("findings", {}).get("treats_symptom") == False
        assert result.get("risk_score", 0) >= 40  # Treatment mismatch adds 40 points
        print("\n[OK] Treatment mismatch evaluation passed")
    else:
        print(f"Error: {data}")
        raise AssertionError("Request failed")


def test_invalid_input():
    """Test error handling for invalid input."""
    print("\n[TEST 6] Evaluate - INVALID INPUT")
    print("-" * 50)

    factory = RequestFactory()
    payload = {
        "symptoms": "not a list",  # Should be a list
        "proposed_drug": "",  # Empty
        "existing_drugs": [],
    }

    request = factory.post(
        "/api/evaluate/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    view = EvaluateDrugView()
    response = view.post(request)

    print(f"Status Code: {response.status_code}")
    data = json.loads(response.content)
    print(f"Response: {json.dumps(data, indent=2)}")

    assert response.status_code == 400
    print("[OK] Invalid input handling passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("MEDGUARD API END-TO-END TESTS")
    print("=" * 60)

    tests = [
        test_health_check,
        test_evaluate_get_info,
        test_evaluate_low_risk,
        test_evaluate_interaction_risk,
        test_evaluate_treatment_mismatch,
        test_invalid_input,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n[FAIL] Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n*** ALL TESTS PASSED! ***")
        return 0
    else:
        print(f"\n*** {failed} test(s) failed ***")
        return 1


if __name__ == "__main__":
    sys.exit(main())
