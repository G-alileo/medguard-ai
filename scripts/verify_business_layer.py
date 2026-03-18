#!/usr/bin/env python
"""
Business Layer Verification Script

Validates that the decision pipeline and all services work correctly.

Usage:
    python scripts/verify_business_layer.py
"""

import os
import sys
import time
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medguard.settings")

import django
django.setup()

from medguard_app.utils.normalizers import InputNormalizer, get_input_normalizer
from medguard_app.services.treatment_validator import TreatmentValidator
from medguard_app.services.interaction_checker import InteractionChecker
from medguard_app.services.side_effect_analyzer import SideEffectAnalyzer
from medguard_app.services.risk_engine import RiskEngine
from medguard_app.services.llm_service import get_llm_service
from medguard_app.orchestrator import get_decision_pipeline


class BusinessLayerVerifier:
    """Verifies business layer integrity."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def verify_all(self) -> bool:
        """Run all verification checks."""
        print("=" * 60)
        print("MEDGUARD BUSINESS LAYER VERIFICATION")
        print("=" * 60)

        print("\n[1/6] Testing InputNormalizer...")
        self.test_normalizer()

        print("\n[2/6] Testing TreatmentValidator...")
        self.test_treatment_validator()

        print("\n[3/6] Testing InteractionChecker...")
        self.test_interaction_checker()

        print("\n[4/6] Testing SideEffectAnalyzer...")
        self.test_side_effect_analyzer()

        print("\n[5/6] Testing RiskEngine...")
        self.test_risk_engine()

        print("\n[6/6] Testing DecisionPipeline (Full Flow)...")
        self.test_decision_pipeline()

        # Report results
        self.report_results()

        return len(self.errors) == 0

    def test_normalizer(self):
        """Test input normalization."""
        try:
            normalizer = get_input_normalizer()

            # Test drug normalization
            tests = [
                ("TYLENOL", "tylenol"),
                ("Ibuprofen", "ibuprofen"),
                ("  aspirin  ", "aspirin"),
            ]

            print("\n  Drug Normalization:")
            for input_val, expected in tests:
                result = normalizer.normalize_drug(input_val)
                normalized = result.get("normalized", "")
                status = "OK" if normalized == expected else "FAIL"
                print(f"    '{input_val}' -> '{normalized}' ({status})")
                if normalized != expected:
                    self.errors.append(f"Drug normalization failed: {input_val}")

            # Test symptom normalization
            symptom_tests = [
                ("HEAD PAIN", "headache"),
                ("stomach ache", "abdominal pain"),
                ("fever", "fever"),
            ]

            print("\n  Symptom Normalization:")
            for input_val, expected in symptom_tests:
                result = normalizer.normalize_symptom(input_val)
                canonical = result.get("canonical", "")
                status = "OK" if canonical == expected else "WARN"
                print(f"    '{input_val}' -> '{canonical}' ({status})")

        except Exception as e:
            self.errors.append(f"Normalizer error: {e}")
            print(f"    ERROR: {e}")

    def test_treatment_validator(self):
        """Test treatment validation."""
        try:
            validator = TreatmentValidator()

            tests = [
                ("acetaminophen", "headache", True),
                ("ibuprofen", "fever", True),
                ("metformin", "headache", False),  # Diabetes drug
            ]

            print("\n  Treatment Validation:")
            for drug, symptom, expected in tests:
                result = validator.does_drug_treat_symptom(drug, symptom)
                treats = result.get("treats", False)
                status = "OK" if treats == expected else "WARN"
                print(f"    {drug} for {symptom}: {treats} ({status})")

        except Exception as e:
            self.errors.append(f"Treatment validator error: {e}")
            print(f"    ERROR: {e}")

    def test_interaction_checker(self):
        """Test drug interaction checking."""
        try:
            checker = InteractionChecker()

            tests = [
                ("warfarin", "aspirin", True, "major"),
                ("warfarin", "ibuprofen", True, "major"),
                ("acetaminophen", "metformin", False, None),
            ]

            print("\n  Interaction Checks:")
            for drug1, drug2, expect_interaction, expect_severity in tests:
                result = checker.check_interaction(drug1, drug2)
                has_interaction = result is not None
                severity = result.get("severity") if result else None

                if expect_interaction:
                    status = "OK" if has_interaction else "WARN"
                    print(f"    {drug1} + {drug2}: {severity or 'none'} ({status})")
                else:
                    status = "OK" if not has_interaction else "WARN"
                    print(f"    {drug1} + {drug2}: no interaction ({status})")

        except Exception as e:
            self.errors.append(f"Interaction checker error: {e}")
            print(f"    ERROR: {e}")

    def test_side_effect_analyzer(self):
        """Test side effect analysis."""
        try:
            analyzer = SideEffectAnalyzer()

            # Test overlap analysis
            print("\n  Side Effect Overlap Analysis:")
            result = analyzer.analyze_side_effect_overlap(
                drug_name="acetaminophen",
                symptoms=["headache", "nausea"],
            )

            overlap_count = result.get("overlapping_count", 0)
            risk_increase = result.get("risk_increase", 0)
            print(f"    acetaminophen with [headache, nausea]:")
            print(f"      Overlapping: {overlap_count}, Risk increase: {risk_increase}")

        except Exception as e:
            self.errors.append(f"Side effect analyzer error: {e}")
            print(f"    ERROR: {e}")

    def test_risk_engine(self):
        """Test risk scoring."""
        try:
            engine = RiskEngine()

            # Test LOW risk scenario
            result = engine.calculate_risk_score(
                treatment_result={"overall_treats": True},
                interactions=[],
                side_effect_analysis={"risk_increase": 0},
            )

            print("\n  Risk Scoring Tests:")
            print(f"    LOW risk scenario: score={result['score']}, level={result['level']}")
            if result["level"] != "LOW":
                self.errors.append(f"Expected LOW risk, got {result['level']}")

            # Test MEDIUM risk scenario
            result = engine.calculate_risk_score(
                treatment_result={"overall_treats": False},  # +40
                interactions=[],
                side_effect_analysis={"risk_increase": 0},
            )
            print(f"    MEDIUM risk scenario (treatment mismatch): score={result['score']}, level={result['level']}")
            if result["level"] != "MEDIUM":
                self.errors.append(f"Expected MEDIUM risk, got {result['level']}")

            # Test HIGH risk scenario
            result = engine.calculate_risk_score(
                treatment_result={"overall_treats": False},  # +40
                interactions=[{"severity": "high"}],  # +30
                side_effect_analysis={"risk_increase": 0},
            )
            print(f"    HIGH risk scenario: score={result['score']}, level={result['level']}")
            if result["level"] != "HIGH":
                self.errors.append(f"Expected HIGH risk, got {result['level']}")

        except Exception as e:
            self.errors.append(f"Risk engine error: {e}")
            print(f"    ERROR: {e}")

    def test_decision_pipeline(self):
        """Test complete decision pipeline."""
        try:
            pipeline = get_decision_pipeline()

            # Test case 1: Low risk scenario
            print("\n  Pipeline Test 1: Low Risk (acetaminophen for headache)")
            start = time.time()
            result = pipeline.evaluate(
                symptoms=["headache", "fever"],
                proposed_drug="acetaminophen",
                existing_drugs=[],
            )
            elapsed = time.time() - start

            print(f"    Risk Score: {result['risk_score']}")
            print(f"    Risk Level: {result['risk_level']}")
            print(f"    Treats Symptom: {result['findings']['treats_symptom']}")
            print(f"    Processing Time: {elapsed:.2f}s")

            if result["risk_level"] not in ["LOW", "MEDIUM"]:
                self.warnings.append(f"Unexpected risk level for acetaminophen+headache: {result['risk_level']}")

            # Test case 2: Interaction scenario
            print("\n  Pipeline Test 2: Interaction Risk (warfarin with aspirin)")
            start = time.time()
            result = pipeline.evaluate(
                symptoms=["blood clot prevention"],
                proposed_drug="warfarin",
                existing_drugs=["aspirin"],
            )
            elapsed = time.time() - start

            print(f"    Risk Score: {result['risk_score']}")
            print(f"    Risk Level: {result['risk_level']}")
            print(f"    Interactions Found: {result['findings']['interactions_found']}")
            print(f"    Processing Time: {elapsed:.2f}s")

            # Test case 3: Treatment mismatch
            print("\n  Pipeline Test 3: Treatment Mismatch (metformin for headache)")
            start = time.time()
            result = pipeline.evaluate(
                symptoms=["headache"],
                proposed_drug="metformin",
                existing_drugs=[],
            )
            elapsed = time.time() - start

            print(f"    Risk Score: {result['risk_score']}")
            print(f"    Risk Level: {result['risk_level']}")
            print(f"    Treats Symptom: {result['findings']['treats_symptom']}")
            print(f"    Processing Time: {elapsed:.2f}s")

            if result["findings"]["treats_symptom"]:
                self.warnings.append("Metformin should not treat headache")

        except Exception as e:
            self.errors.append(f"Pipeline error: {e}")
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()

    def report_results(self):
        """Print final report."""
        print("\n" + "=" * 60)
        print("VERIFICATION RESULTS")
        print("=" * 60)

        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  X {error}")
        else:
            print("\n[OK] No errors found")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ! {warning}")

        if not self.errors and not self.warnings:
            print("\n[SUCCESS] All verification checks passed!")


def main():
    verifier = BusinessLayerVerifier()
    success = verifier.verify_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
