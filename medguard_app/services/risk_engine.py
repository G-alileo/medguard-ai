"""
Risk Engine - Calculate risk scores based on all assessment factors.

This is the CORE module that produces deterministic risk scores.
The LLM only EXPLAINS this score - it never changes it.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level categories."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class RiskBreakdown:
    """Breakdown of how risk score was calculated."""

    treatment_mismatch: int = 0
    interaction_total: int = 0
    interaction_critical: int = 0
    interaction_high: int = 0
    interaction_medium: int = 0
    side_effect_overlap: int = 0
    contraindication: int = 0

    @property
    def total(self) -> int:
        return (
            self.treatment_mismatch
            + self.interaction_total
            + self.side_effect_overlap
            + self.contraindication
        )


class RiskEngine:
    """
    Calculates risk scores for drug evaluations.

    Risk scoring is DETERMINISTIC:
    - Same inputs ALWAYS produce same score
    - LLM only explains the score, never changes it

    Scoring weights (total can exceed 100 for extreme cases):
    - No treatment indication: 40 points
    - Critical/Contraindicated interaction: 50 points each
    - Major/High interaction: 30 points each
    - Moderate interaction: 15 points each
    - Minor interaction: 5 points each
    - Side effect overlap: 1-30 points (based on severity)
    - Contraindication match: 40 points

    Risk levels:
    - LOW: 0-25
    - MEDIUM: 26-60
    - HIGH: 61+
    """

    # Scoring weights
    WEIGHTS = {
        "no_treatment_indication": 40,
        "interaction_critical": 50,
        "interaction_high": 30,
        "interaction_medium": 15,
        "interaction_low": 5,
        "side_effect_overlap_max": 30,
        "contraindication": 40,
    }

    # Risk level thresholds
    THRESHOLDS = {
        "low_max": 25,
        "medium_max": 60,
    }

    def __init__(self):
        # Configurable weights (can be overridden)
        self.weights = self.WEIGHTS.copy()
        self.thresholds = self.THRESHOLDS.copy()

    def calculate_risk_score(
        self,
        treatment_result: dict,
        interactions: list[dict],
        side_effect_analysis: dict,
        contraindications: Optional[list[dict]] = None,
    ) -> dict:
        """
        Calculate the overall risk score.

        Args:
            treatment_result: From TreatmentValidator.validate_treatment_for_symptoms()
            interactions: From InteractionChecker.check_all_interactions()
            side_effect_analysis: From SideEffectAnalyzer.analyze_side_effect_overlap()
            contraindications: List of matched contraindications (future)

        Returns:
            Dict with score, level, and breakdown
        """
        breakdown = RiskBreakdown()
        contraindications = contraindications or []

        # 1. Treatment mismatch scoring
        if not treatment_result.get("overall_treats", True):
            breakdown.treatment_mismatch = self.weights["no_treatment_indication"]
            logger.debug(f"Treatment mismatch: +{breakdown.treatment_mismatch}")

        # 2. Interaction scoring
        for interaction in interactions:
            severity = interaction.get("severity", "unknown")
            if severity == "critical":
                breakdown.interaction_critical += self.weights["interaction_critical"]
            elif severity == "high":
                breakdown.interaction_high += self.weights["interaction_high"]
            elif severity == "medium":
                breakdown.interaction_medium += self.weights["interaction_medium"]
            elif severity == "low":
                breakdown.interaction_total += self.weights["interaction_low"]

        breakdown.interaction_total = (
            breakdown.interaction_critical
            + breakdown.interaction_high
            + breakdown.interaction_medium
        )
        logger.debug(f"Interaction total: {breakdown.interaction_total}")

        # 3. Side effect overlap scoring
        side_effect_risk = side_effect_analysis.get("risk_increase", 0)
        breakdown.side_effect_overlap = min(
            side_effect_risk, self.weights["side_effect_overlap_max"]
        )
        logger.debug(f"Side effect overlap: +{breakdown.side_effect_overlap}")

        # 4. Contraindication scoring
        if contraindications:
            breakdown.contraindication = (
                len(contraindications) * self.weights["contraindication"]
            )
            logger.debug(f"Contraindications: +{breakdown.contraindication}")

        # Calculate total score
        total_score = breakdown.total

        # Determine risk level
        if total_score <= self.thresholds["low_max"]:
            risk_level = RiskLevel.LOW
        elif total_score <= self.thresholds["medium_max"]:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.HIGH

        # Build factors list for explanation
        factors = self._build_factor_list(
            breakdown, treatment_result, interactions, side_effect_analysis
        )

        return {
            "score": total_score,
            "level": risk_level.value,
            "breakdown": {
                "treatment_mismatch": breakdown.treatment_mismatch,
                "interactions": breakdown.interaction_total,
                "interaction_details": {
                    "critical": breakdown.interaction_critical,
                    "high": breakdown.interaction_high,
                    "medium": breakdown.interaction_medium,
                },
                "side_effect_overlap": breakdown.side_effect_overlap,
                "contraindications": breakdown.contraindication,
            },
            "factors": factors,
            "threshold_info": {
                "low_max": self.thresholds["low_max"],
                "medium_max": self.thresholds["medium_max"],
            },
        }

    def _build_factor_list(
        self,
        breakdown: RiskBreakdown,
        treatment_result: dict,
        interactions: list[dict],
        side_effect_analysis: dict,
    ) -> list[dict]:
        """Build a list of factors contributing to the score."""
        factors = []

        # Treatment factor
        if breakdown.treatment_mismatch > 0:
            factors.append({
                "category": "treatment",
                "severity": "warning",
                "points": breakdown.treatment_mismatch,
                "description": "Drug may not be indicated for reported symptoms",
                "details": treatment_result.get("reason", ""),
            })

        # Interaction factors
        for interaction in interactions:
            severity = interaction.get("severity", "unknown")
            factor_severity = "critical" if severity in ["critical", "high"] else "warning"

            factors.append({
                "category": "interaction",
                "severity": factor_severity,
                "points": self._get_interaction_points(severity),
                "description": f"Interaction with {interaction.get('existing_drug', 'unknown')}",
                "details": interaction.get("description", ""),
                "mechanism": interaction.get("mechanism", ""),
            })

        # Side effect factor
        if breakdown.side_effect_overlap > 0:
            overlaps = side_effect_analysis.get("overlapping_symptoms", [])
            factors.append({
                "category": "side_effects",
                "severity": "warning",
                "points": breakdown.side_effect_overlap,
                "description": "Drug side effects may worsen current symptoms",
                "details": side_effect_analysis.get("explanation", ""),
                "overlapping_symptoms": [o.get("user_symptom") for o in overlaps],
            })

        # Sort by points (highest first)
        factors.sort(key=lambda x: x.get("points", 0), reverse=True)

        return factors

    def _get_interaction_points(self, severity: str) -> int:
        """Get points for an interaction severity level."""
        mapping = {
            "critical": self.weights["interaction_critical"],
            "high": self.weights["interaction_high"],
            "medium": self.weights["interaction_medium"],
            "low": self.weights["interaction_low"],
        }
        return mapping.get(severity, 0)

    def get_risk_summary(self, risk_result: dict) -> str:
        """
        Generate a human-readable summary of the risk assessment.

        This is a DETERMINISTIC summary, not LLM-generated.
        """
        score = risk_result["score"]
        level = risk_result["level"]
        breakdown = risk_result["breakdown"]

        parts = []

        if level == "LOW":
            parts.append("This drug appears to be low risk for your situation.")
        elif level == "MEDIUM":
            parts.append("This drug has moderate risks that should be considered.")
        else:
            parts.append("This drug has significant risks in your situation.")

        # Add breakdown details
        if breakdown["interactions"] > 0:
            parts.append(f"Drug interactions contribute {breakdown['interactions']} points to risk.")
        if breakdown["treatment_mismatch"] > 0:
            parts.append(f"Treatment mismatch adds {breakdown['treatment_mismatch']} points.")
        if breakdown["side_effect_overlap"] > 0:
            parts.append(f"Side effect concerns add {breakdown['side_effect_overlap']} points.")

        return " ".join(parts)

    def get_recommendation(self, level: str) -> dict:
        """
        Get a recommendation based on risk level.

        Returns DETERMINISTIC recommendations, not LLM-generated.
        """
        recommendations = {
            "LOW": {
                "action": "likely_safe",
                "message": "Safe to use based on available data. Monitor for any adverse effects.",
                "consult_required": False,
            },
            "MEDIUM": {
                "action": "use_caution",
                "message": (
                    "Use with caution. Some risks identified. "
                    "Consider consulting a pharmacist or healthcare provider."
                ),
                "consult_required": False,
            },
            "HIGH": {
                "action": "not_recommended",
                "message": (
                    "NOT RECOMMENDED. Serious risks identified. "
                    "Consult a healthcare professional before using this medication."
                ),
                "consult_required": True,
            },
        }

        return recommendations.get(level, recommendations["MEDIUM"])
