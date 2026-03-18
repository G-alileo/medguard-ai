import logging
from datetime import datetime
from typing import Optional

from django.conf import settings

from apps.data_access.repositories import DrugRepository, InteractionRepository
from apps.data_access.vector_store import get_chroma_client, ChromaClient

from ..utils.normalizers import InputNormalizer, get_input_normalizer
from ..services.treatment_validator import TreatmentValidator
from ..services.interaction_checker import InteractionChecker
from ..services.side_effect_analyzer import SideEffectAnalyzer
from ..services.risk_engine import RiskEngine
from ..services.llm_service import DeepSeekService, get_llm_service

logger = logging.getLogger(__name__)


class DecisionPipeline:
    """
    Main orchestrator for all drug safety evaluations.

    Usage:
        pipeline = DecisionPipeline()
        result = pipeline.evaluate(
            symptoms=["headache", "fever"],
            proposed_drug="ibuprofen",
            existing_drugs=["aspirin", "lisinopril"]
        )
        print(result["risk_level"])  # "HIGH"
        print(result["explanation"])  # "There are serious interactions..."
    """

    def __init__(
        self,
        normalizer: Optional[InputNormalizer] = None,
        treatment_validator: Optional[TreatmentValidator] = None,
        interaction_checker: Optional[InteractionChecker] = None,
        side_effect_analyzer: Optional[SideEffectAnalyzer] = None,
        risk_engine: Optional[RiskEngine] = None,
        vector_store: Optional[ChromaClient] = None,
        llm_service: Optional[DeepSeekService] = None,
    ):
        """
        Initialize the pipeline with all services.

        All services can be injected for testing.
        """
        self.normalizer = normalizer or get_input_normalizer()

        # Initialize repositories
        self.drug_repo = DrugRepository()
        self.interaction_repo = InteractionRepository()

        # Initialize services
        self.treatment_validator = treatment_validator or TreatmentValidator(self.drug_repo)
        self.interaction_checker = interaction_checker or InteractionChecker(
            self.interaction_repo, self.drug_repo
        )
        self.side_effect_analyzer = side_effect_analyzer or SideEffectAnalyzer(self.drug_repo)
        self.risk_engine = risk_engine or RiskEngine()

        # Vector store (may not be available)
        try:
            self.vector_store = vector_store or get_chroma_client()
        except Exception as e:
            logger.warning(f"Vector store not available: {e}")
            self.vector_store = None

        # LLM service (may use mock mode)
        self.llm_service = llm_service or get_llm_service()

    def evaluate(
        self,
        symptoms: list[str],
        proposed_drug: str,
        existing_drugs: list[str],
    ) -> dict:
        """
        Main entry point for ALL drug safety evaluations.

        Args:
            symptoms: List of user-reported symptoms
            proposed_drug: The drug given at the chemist or being considered
            existing_drugs: List of medications user is currently taking

        Returns:
            Complete assessment dict ready for presentation:
            {
                "risk_score": int,
                "risk_level": "LOW" | "MEDIUM" | "HIGH",
                "explanation": str,
                "findings": {...},
                "recommendation": {...},
                "metadata": {...}
            }
        """
        start_time = datetime.now()
        evaluation_id = f"eval_{start_time.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting evaluation {evaluation_id}")
        logger.debug(f"Inputs: symptoms={symptoms}, drug={proposed_drug}, existing={existing_drugs}")

        try:
            # Step 1: Normalize all inputs
            normalized = self._normalize_inputs(symptoms, proposed_drug, existing_drugs)
            logger.debug(f"Normalized inputs: {normalized}")

            # Step 2: Check if drug exists
            drug_exists = self._validate_drug_exists(normalized["drug"]["canonical"])

            # Step 3: Validate treatment
            treatment_result = self._validate_treatment(
                normalized["drug"]["canonical"],
                normalized["symptoms_canonical"],
            )
            logger.debug(f"Treatment result: {treatment_result}")

            # Step 4: Check interactions
            interactions = self._check_interactions(
                normalized["drug"]["canonical"],
                normalized["existing_drugs_canonical"],
            )
            interaction_summary = self.interaction_checker.get_interaction_summary(
                normalized["drug"]["canonical"],
                normalized["existing_drugs_canonical"],
            )
            logger.debug(f"Interactions found: {len(interactions)}")

            # Step 5: Analyze side effects
            side_effect_analysis = self._analyze_side_effects(
                normalized["drug"]["canonical"],
                normalized["symptoms_canonical"],
            )
            logger.debug(f"Side effect overlap: {side_effect_analysis.get('overlapping_count', 0)}")

            # Step 6: Calculate risk score (DETERMINISTIC)
            risk_result = self.risk_engine.calculate_risk_score(
                treatment_result=treatment_result,
                interactions=interactions,
                side_effect_analysis=side_effect_analysis,
                contraindications=[],  # Future enhancement
            )
            logger.info(f"Risk score: {risk_result['score']} ({risk_result['level']})")

            # Step 7: Retrieve context (if vector store available)
            context = self._retrieve_context(
                normalized["drug"]["canonical"],
                normalized["symptoms_canonical"],
                normalized["existing_drugs_canonical"],
            )

            # Step 8: Build findings dict for LLM
            findings = {
                "treatment": treatment_result,
                "interactions": interactions,
                "interaction_summary": interaction_summary,
                "side_effects": side_effect_analysis,
            }

            # Step 9: Generate explanation (LLM or mock)
            explanation = ""
            if risk_result["score"] > 0:
                explanation = self.llm_service.generate_explanation(
                    findings=findings,
                    context=context,
                    risk_score=risk_result["score"],
                    risk_level=risk_result["level"],
                )

            # Step 10: Build recommendation
            recommendation = self.risk_engine.get_recommendation(risk_result["level"])

            # Step 11: Build final result
            elapsed = (datetime.now() - start_time).total_seconds()

            result = {
                # Core assessment
                "risk_score": risk_result["score"],
                "risk_level": risk_result["level"],
                "explanation": explanation,

                # Detailed findings
                "findings": {
                    "drug_found": drug_exists,
                    "treats_symptom": treatment_result.get("overall_treats", False),
                    "treatment_confidence": treatment_result.get("confidence", "unknown"),
                    "interactions_found": len(interactions),
                    "interaction_risk_level": interaction_summary.get("risk_level", "none"),
                    "side_effect_warnings": side_effect_analysis.get("overlapping_symptoms", []),
                    "side_effect_risk": side_effect_analysis.get("risk_increase", 0),
                },

                # Score breakdown
                "score_breakdown": risk_result.get("breakdown", {}),
                "risk_factors": risk_result.get("factors", []),

                # Recommendation
                "recommendation": recommendation,

                # Normalized inputs (for reference)
                "normalized_inputs": {
                    "drug": normalized["drug"]["canonical"],
                    "symptoms": normalized["symptoms_canonical"],
                    "existing_drugs": normalized["existing_drugs_canonical"],
                },

                # Metadata
                "metadata": {
                    "evaluation_id": evaluation_id,
                    "timestamp": start_time.isoformat(),
                    "processing_time_seconds": elapsed,
                    "llm_used": not self.llm_service.mock_mode,
                    "vector_store_used": self.vector_store is not None and len(context) > 0,
                },
            }

            logger.info(f"Evaluation {evaluation_id} completed in {elapsed:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Error in evaluation {evaluation_id}: {e}", exc_info=True)
            return self._build_error_result(str(e), evaluation_id, start_time)

    def _normalize_inputs(
        self,
        symptoms: list[str],
        proposed_drug: str,
        existing_drugs: list[str],
    ) -> dict:
        """Normalize all inputs."""
        return self.normalizer.normalize_inputs(symptoms, proposed_drug, existing_drugs)

    def _validate_drug_exists(self, drug_name: str) -> bool:
        """Check if drug exists in database."""
        drug = self.drug_repo.get_by_name(drug_name)
        return drug is not None

    def _validate_treatment(self, drug_name: str, symptoms: list[str]) -> dict:
        """Validate if drug is appropriate for symptoms."""
        return self.treatment_validator.validate_treatment_for_symptoms(drug_name, symptoms)

    def _check_interactions(self, proposed_drug: str, existing_drugs: list[str]) -> list[dict]:
        """Check for drug interactions."""
        return self.interaction_checker.check_all_interactions(proposed_drug, existing_drugs)

    def _analyze_side_effects(self, drug_name: str, symptoms: list[str]) -> dict:
        """Analyze side effect overlap with symptoms."""
        return self.side_effect_analyzer.analyze_side_effect_overlap(drug_name, symptoms)

    def _retrieve_context(
        self,
        drug: str,
        symptoms: list[str],
        existing_drugs: list[str],
    ) -> list[dict]:
        """Retrieve relevant context from vector store."""
        if not self.vector_store:
            return []

        try:
            # Get context for the drug
            context = self.vector_store.get_context_for_drug(
                drug=drug,
                query_type="interactions" if existing_drugs else "usage",
                limit=3,
            )

            # Also search for interaction context if there are existing drugs
            if existing_drugs:
                for existing in existing_drugs[:2]:  # Limit to 2 drugs
                    interaction_context = self.vector_store.search_interactions(
                        drug1=drug,
                        drug2=existing,
                        limit=2,
                    )
                    context.extend(interaction_context)

            # Deduplicate and return
            seen = set()
            unique_context = []
            for item in context:
                text_hash = hash(item.get("text", "")[:100])
                if text_hash not in seen:
                    seen.add(text_hash)
                    unique_context.append(item)

            return unique_context[:5]  # Max 5 context items

        except Exception as e:
            logger.warning(f"Error retrieving context: {e}")
            return []

    def _build_error_result(
        self,
        error_message: str,
        evaluation_id: str,
        start_time: datetime,
    ) -> dict:
        """Build an error result when evaluation fails."""
        elapsed = (datetime.now() - start_time).total_seconds()

        return {
            "risk_score": 0,
            "risk_level": "UNKNOWN",
            "explanation": (
                "We were unable to complete the safety evaluation due to a technical error. "
                "Please consult a healthcare professional for advice."
            ),
            "findings": {
                "error": True,
                "error_message": error_message,
            },
            "recommendation": {
                "action": "error",
                "message": "Unable to evaluate. Please consult a healthcare professional.",
                "consult_required": True,
            },
            "metadata": {
                "evaluation_id": evaluation_id,
                "timestamp": start_time.isoformat(),
                "processing_time_seconds": elapsed,
                "error": True,
            },
        }


# Singleton instance
_pipeline: Optional[DecisionPipeline] = None


def get_decision_pipeline() -> DecisionPipeline:
    """Get the global DecisionPipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = DecisionPipeline()
    return _pipeline
