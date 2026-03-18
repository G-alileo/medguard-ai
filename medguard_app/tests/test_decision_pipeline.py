"""
Unit Tests for Decision Pipeline

Tests the complete drug safety evaluation flow with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from medguard_app.orchestrator.decision_pipeline import DecisionPipeline
from medguard_app.utils.normalizers import InputNormalizer
from medguard_app.services.treatment_validator import TreatmentValidator
from medguard_app.services.interaction_checker import InteractionChecker
from medguard_app.services.side_effect_analyzer import SideEffectAnalyzer
from medguard_app.services.risk_engine import RiskEngine


class TestDecisionPipeline:
    """Test suite for DecisionPipeline."""

    @pytest.fixture
    def mock_normalizer(self):
        """Create a mock normalizer."""
        normalizer = Mock(spec=InputNormalizer)
        normalizer.normalize_inputs.return_value = {
            "drug": {
                "original": "tylenol",
                "canonical": "acetaminophen",
                "normalized": True,
            },
            "symptoms_canonical": ["headache", "fever"],
            "symptoms_original": ["head pain", "fever"],
            "existing_drugs_canonical": ["ibuprofen"],
            "existing_drugs_original": ["advil"],
        }
        return normalizer

    @pytest.fixture
    def mock_treatment_validator(self):
        """Create a mock treatment validator."""
        validator = Mock(spec=TreatmentValidator)
        validator.validate_treatment_for_symptoms.return_value = {
            "overall_treats": True,
            "confidence": "high",
            "details": [
                {"symptom": "headache", "treats": True, "confidence": "high"},
                {"symptom": "fever", "treats": True, "confidence": "high"},
            ],
        }
        return validator

    @pytest.fixture
    def mock_interaction_checker(self):
        """Create a mock interaction checker."""
        checker = Mock(spec=InteractionChecker)
        checker.check_all_interactions.return_value = []
        checker.get_interaction_summary.return_value = {
            "total_interactions": 0,
            "risk_level": "none",
        }
        return checker

    @pytest.fixture
    def mock_side_effect_analyzer(self):
        """Create a mock side effect analyzer."""
        analyzer = Mock(spec=SideEffectAnalyzer)
        analyzer.analyze_side_effect_overlap.return_value = {
            "overlapping_count": 0,
            "overlapping_symptoms": [],
            "risk_increase": 0,
        }
        return analyzer

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        service = Mock()
        service.mock_mode = True
        service.generate_explanation.return_value = "This is a test explanation."
        return service

    @pytest.fixture
    def mock_drug_repo(self):
        """Create a mock drug repository."""
        repo = Mock()
        repo.get_by_name.return_value = Mock(id=1, canonical_name="acetaminophen")
        return repo

    @pytest.fixture
    def pipeline_with_mocks(
        self,
        mock_normalizer,
        mock_treatment_validator,
        mock_interaction_checker,
        mock_side_effect_analyzer,
        mock_llm_service,
    ):
        """Create a pipeline with all mocked dependencies."""
        with patch("medguard_app.orchestrator.decision_pipeline.DrugRepository") as MockDrugRepo, \
             patch("medguard_app.orchestrator.decision_pipeline.InteractionRepository") as MockInteractionRepo, \
             patch("medguard_app.orchestrator.decision_pipeline.get_chroma_client") as MockChroma:

            MockDrugRepo.return_value.get_by_name.return_value = Mock(id=1, canonical_name="acetaminophen")
            MockInteractionRepo.return_value = Mock()
            MockChroma.return_value = None

            pipeline = DecisionPipeline(
                normalizer=mock_normalizer,
                treatment_validator=mock_treatment_validator,
                interaction_checker=mock_interaction_checker,
                side_effect_analyzer=mock_side_effect_analyzer,
                risk_engine=RiskEngine(),  # Use real risk engine
                vector_store=None,
                llm_service=mock_llm_service,
            )
            return pipeline

    def test_evaluate_low_risk_scenario(self, pipeline_with_mocks):
        """Test evaluation with no risks identified."""
        result = pipeline_with_mocks.evaluate(
            symptoms=["headache", "fever"],
            proposed_drug="tylenol",
            existing_drugs=["advil"],
        )

        assert result["risk_level"] == "LOW"
        assert result["risk_score"] == 0
        assert result["findings"]["treats_symptom"] is True
        assert result["findings"]["interactions_found"] == 0

    def test_evaluate_with_treatment_mismatch(
        self,
        mock_normalizer,
        mock_interaction_checker,
        mock_side_effect_analyzer,
        mock_llm_service,
    ):
        """Test evaluation when drug doesn't treat symptoms."""
        # Create validator that returns mismatch
        mock_validator = Mock(spec=TreatmentValidator)
        mock_validator.validate_treatment_for_symptoms.return_value = {
            "overall_treats": False,
            "confidence": "high",
            "reason": "Drug not indicated for these symptoms",
            "details": [],
        }

        with patch("medguard_app.orchestrator.decision_pipeline.DrugRepository") as MockDrugRepo, \
             patch("medguard_app.orchestrator.decision_pipeline.InteractionRepository"), \
             patch("medguard_app.orchestrator.decision_pipeline.get_chroma_client"):

            MockDrugRepo.return_value.get_by_name.return_value = Mock(id=1)

            pipeline = DecisionPipeline(
                normalizer=mock_normalizer,
                treatment_validator=mock_validator,
                interaction_checker=mock_interaction_checker,
                side_effect_analyzer=mock_side_effect_analyzer,
                risk_engine=RiskEngine(),
                vector_store=None,
                llm_service=mock_llm_service,
            )

            result = pipeline.evaluate(
                symptoms=["headache"],
                proposed_drug="metformin",  # Diabetes drug for headache
                existing_drugs=[],
            )

            # Treatment mismatch adds 40 points -> MEDIUM risk
            assert result["risk_level"] == "MEDIUM"
            assert result["risk_score"] == 40
            assert result["findings"]["treats_symptom"] is False

    def test_evaluate_with_high_severity_interaction(
        self,
        mock_normalizer,
        mock_treatment_validator,
        mock_side_effect_analyzer,
        mock_llm_service,
    ):
        """Test evaluation with a high severity drug interaction."""
        # Create checker that returns high severity interaction
        mock_checker = Mock(spec=InteractionChecker)
        mock_checker.check_all_interactions.return_value = [
            {
                "proposed_drug": "warfarin",
                "existing_drug": "aspirin",
                "severity": "high",
                "description": "Increased bleeding risk",
                "mechanism": "Both drugs affect coagulation",
            }
        ]
        mock_checker.get_interaction_summary.return_value = {
            "total_interactions": 1,
            "risk_level": "high",
        }

        with patch("medguard_app.orchestrator.decision_pipeline.DrugRepository") as MockDrugRepo, \
             patch("medguard_app.orchestrator.decision_pipeline.InteractionRepository"), \
             patch("medguard_app.orchestrator.decision_pipeline.get_chroma_client"):

            MockDrugRepo.return_value.get_by_name.return_value = Mock(id=1)

            pipeline = DecisionPipeline(
                normalizer=mock_normalizer,
                treatment_validator=mock_treatment_validator,
                interaction_checker=mock_checker,
                side_effect_analyzer=mock_side_effect_analyzer,
                risk_engine=RiskEngine(),
                vector_store=None,
                llm_service=mock_llm_service,
            )

            result = pipeline.evaluate(
                symptoms=["blood clot prevention"],
                proposed_drug="warfarin",
                existing_drugs=["aspirin"],
            )

            # High interaction adds 30 points -> MEDIUM risk
            assert result["risk_level"] == "MEDIUM"
            assert result["risk_score"] == 30
            assert result["findings"]["interactions_found"] == 1

    def test_evaluate_with_critical_interaction(
        self,
        mock_normalizer,
        mock_treatment_validator,
        mock_side_effect_analyzer,
        mock_llm_service,
    ):
        """Test evaluation with a critical drug interaction."""
        # Create checker that returns critical interaction
        mock_checker = Mock(spec=InteractionChecker)
        mock_checker.check_all_interactions.return_value = [
            {
                "proposed_drug": "drug_a",
                "existing_drug": "drug_b",
                "severity": "critical",
                "description": "Life-threatening interaction",
                "mechanism": "Severe toxicity",
            }
        ]
        mock_checker.get_interaction_summary.return_value = {
            "total_interactions": 1,
            "risk_level": "critical",
        }

        with patch("medguard_app.orchestrator.decision_pipeline.DrugRepository") as MockDrugRepo, \
             patch("medguard_app.orchestrator.decision_pipeline.InteractionRepository"), \
             patch("medguard_app.orchestrator.decision_pipeline.get_chroma_client"):

            MockDrugRepo.return_value.get_by_name.return_value = Mock(id=1)

            pipeline = DecisionPipeline(
                normalizer=mock_normalizer,
                treatment_validator=mock_treatment_validator,
                interaction_checker=mock_checker,
                side_effect_analyzer=mock_side_effect_analyzer,
                risk_engine=RiskEngine(),
                vector_store=None,
                llm_service=mock_llm_service,
            )

            result = pipeline.evaluate(
                symptoms=["symptom"],
                proposed_drug="drug_a",
                existing_drugs=["drug_b"],
            )

            # Critical interaction adds 50 points -> MEDIUM risk (just under HIGH)
            assert result["risk_level"] == "MEDIUM"
            assert result["risk_score"] == 50

    def test_evaluate_high_risk_multiple_factors(
        self,
        mock_normalizer,
        mock_side_effect_analyzer,
        mock_llm_service,
    ):
        """Test HIGH risk when multiple factors combine."""
        # Treatment mismatch
        mock_validator = Mock(spec=TreatmentValidator)
        mock_validator.validate_treatment_for_symptoms.return_value = {
            "overall_treats": False,
            "confidence": "high",
            "details": [],
        }

        # High severity interaction
        mock_checker = Mock(spec=InteractionChecker)
        mock_checker.check_all_interactions.return_value = [
            {
                "proposed_drug": "drug_a",
                "existing_drug": "drug_b",
                "severity": "high",
                "description": "Serious interaction",
            }
        ]
        mock_checker.get_interaction_summary.return_value = {
            "total_interactions": 1,
            "risk_level": "high",
        }

        with patch("medguard_app.orchestrator.decision_pipeline.DrugRepository") as MockDrugRepo, \
             patch("medguard_app.orchestrator.decision_pipeline.InteractionRepository"), \
             patch("medguard_app.orchestrator.decision_pipeline.get_chroma_client"):

            MockDrugRepo.return_value.get_by_name.return_value = Mock(id=1)

            pipeline = DecisionPipeline(
                normalizer=mock_normalizer,
                treatment_validator=mock_validator,
                interaction_checker=mock_checker,
                side_effect_analyzer=mock_side_effect_analyzer,
                risk_engine=RiskEngine(),
                vector_store=None,
                llm_service=mock_llm_service,
            )

            result = pipeline.evaluate(
                symptoms=["symptom"],
                proposed_drug="drug_a",
                existing_drugs=["drug_b"],
            )

            # 40 (treatment) + 30 (high interaction) = 70 -> HIGH
            assert result["risk_level"] == "HIGH"
            assert result["risk_score"] == 70
            assert result["recommendation"]["consult_required"] is True

    def test_evaluate_returns_metadata(self, pipeline_with_mocks):
        """Test that evaluation includes proper metadata."""
        result = pipeline_with_mocks.evaluate(
            symptoms=["headache"],
            proposed_drug="tylenol",
            existing_drugs=[],
        )

        assert "metadata" in result
        assert "evaluation_id" in result["metadata"]
        assert "timestamp" in result["metadata"]
        assert "processing_time_seconds" in result["metadata"]
        assert result["metadata"]["evaluation_id"].startswith("eval_")

    def test_evaluate_returns_normalized_inputs(self, pipeline_with_mocks):
        """Test that evaluation returns normalized inputs."""
        result = pipeline_with_mocks.evaluate(
            symptoms=["head pain"],
            proposed_drug="tylenol",
            existing_drugs=["advil"],
        )

        assert "normalized_inputs" in result
        assert result["normalized_inputs"]["drug"] == "acetaminophen"

    def test_evaluate_returns_score_breakdown(self, pipeline_with_mocks):
        """Test that evaluation returns score breakdown."""
        result = pipeline_with_mocks.evaluate(
            symptoms=["headache"],
            proposed_drug="tylenol",
            existing_drugs=[],
        )

        assert "score_breakdown" in result
        assert "treatment_mismatch" in result["score_breakdown"]
        assert "interactions" in result["score_breakdown"]
        assert "side_effect_overlap" in result["score_breakdown"]

    def test_evaluate_error_handling(self, mock_normalizer):
        """Test that errors are caught and return error result."""
        mock_normalizer.normalize_inputs.side_effect = Exception("Test error")

        with patch("medguard_app.orchestrator.decision_pipeline.DrugRepository"), \
             patch("medguard_app.orchestrator.decision_pipeline.InteractionRepository"), \
             patch("medguard_app.orchestrator.decision_pipeline.get_chroma_client"):

            pipeline = DecisionPipeline(normalizer=mock_normalizer)

            result = pipeline.evaluate(
                symptoms=["headache"],
                proposed_drug="tylenol",
                existing_drugs=[],
            )

            assert result["risk_level"] == "UNKNOWN"
            assert result["findings"]["error"] is True
            assert "Test error" in result["findings"]["error_message"]
            assert result["recommendation"]["consult_required"] is True


class TestRiskEngine:
    """Test suite for RiskEngine in isolation."""

    def test_low_risk_threshold(self):
        """Test LOW risk for score 0-25."""
        engine = RiskEngine()

        result = engine.calculate_risk_score(
            treatment_result={"overall_treats": True},
            interactions=[],
            side_effect_analysis={"risk_increase": 0},
        )

        assert result["level"] == "LOW"
        assert result["score"] == 0

    def test_medium_risk_threshold(self):
        """Test MEDIUM risk for score 26-60."""
        engine = RiskEngine()

        result = engine.calculate_risk_score(
            treatment_result={"overall_treats": False},  # +40 points
            interactions=[],
            side_effect_analysis={"risk_increase": 0},
        )

        assert result["level"] == "MEDIUM"
        assert result["score"] == 40

    def test_high_risk_threshold(self):
        """Test HIGH risk for score 61+."""
        engine = RiskEngine()

        result = engine.calculate_risk_score(
            treatment_result={"overall_treats": False},  # +40
            interactions=[{"severity": "high"}],  # +30
            side_effect_analysis={"risk_increase": 0},
        )

        assert result["level"] == "HIGH"
        assert result["score"] == 70

    def test_critical_interaction_weight(self):
        """Test critical interaction adds 50 points."""
        engine = RiskEngine()

        result = engine.calculate_risk_score(
            treatment_result={"overall_treats": True},
            interactions=[{"severity": "critical"}],
            side_effect_analysis={"risk_increase": 0},
        )

        assert result["score"] == 50
        assert result["breakdown"]["interaction_details"]["critical"] == 50

    def test_multiple_interactions(self):
        """Test multiple interactions are summed."""
        engine = RiskEngine()

        result = engine.calculate_risk_score(
            treatment_result={"overall_treats": True},
            interactions=[
                {"severity": "high"},   # +30
                {"severity": "medium"}, # +15
            ],
            side_effect_analysis={"risk_increase": 0},
        )

        assert result["score"] == 45
        assert result["level"] == "MEDIUM"

    def test_side_effect_overlap_capped(self):
        """Test side effect risk is capped at 30."""
        engine = RiskEngine()

        result = engine.calculate_risk_score(
            treatment_result={"overall_treats": True},
            interactions=[],
            side_effect_analysis={"risk_increase": 100},  # Should cap at 30
        )

        assert result["score"] == 30
        assert result["breakdown"]["side_effect_overlap"] == 30

    def test_recommendation_low(self):
        """Test LOW risk recommendation."""
        engine = RiskEngine()
        rec = engine.get_recommendation("LOW")

        assert rec["action"] == "likely_safe"
        assert rec["consult_required"] is False

    def test_recommendation_high(self):
        """Test HIGH risk recommendation."""
        engine = RiskEngine()
        rec = engine.get_recommendation("HIGH")

        assert rec["action"] == "not_recommended"
        assert rec["consult_required"] is True


class TestInputNormalizer:
    """Test suite for InputNormalizer."""

    def test_normalize_drug_name(self):
        """Test drug name normalization."""
        normalizer = InputNormalizer()
        result = normalizer.normalize_drug("TYLENOL")

        assert result["normalized"] == "tylenol"

    def test_normalize_symptom(self):
        """Test symptom normalization."""
        normalizer = InputNormalizer()
        result = normalizer.normalize_symptom("HEAD PAIN")

        # Should map to "headache"
        assert result["canonical"] == "headache"

    def test_normalize_inputs_complete(self):
        """Test complete input normalization."""
        normalizer = InputNormalizer()
        result = normalizer.normalize_inputs(
            symptoms=["HEAD PAIN", "Fever"],
            drug="Tylenol",
            existing_drugs=["ADVIL"],
        )

        assert "drug" in result
        assert "symptoms_canonical" in result
        assert "existing_drugs_canonical" in result
