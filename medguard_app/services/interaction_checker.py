from typing import Optional
import logging

from apps.data_access.repositories import DrugRepository, InteractionRepository

logger = logging.getLogger(__name__)


class InteractionChecker:
    
    SEVERITY_DISPLAY = {
        "contraindicated": "critical",
        "major": "high",
        "moderate": "medium",
        "minor": "low",
        "unknown": "unknown",
    }

    def __init__(
        self,
        drug_repo: Optional[DrugRepository] = None,
        interaction_repo: Optional[InteractionRepository] = None,
    ):
        self.drug_repo = drug_repo or DrugRepository()
        self.interaction_repo = interaction_repo or InteractionRepository()

    def check_interaction(
        self, drug1_name: str, drug2_name: str
    ) -> Optional[dict]:
        drug1 = self.drug_repo.get_by_name(drug1_name)
        drug2 = self.drug_repo.get_by_name(drug2_name)

        if not drug1 or not drug2:
            return None

        interaction = self.interaction_repo.check_interaction(drug1, drug2)
        
        if not interaction:
            return None

        return {
            "drug_a": interaction.drug_a.canonical_name,
            "drug_b": interaction.drug_b.canonical_name,
            "severity": interaction.severity,
            "severity_display": self.SEVERITY_DISPLAY.get(interaction.severity, "unknown"),
            "description": interaction.description,
            "clinical_effect": interaction.clinical_effect,
            "mechanism": getattr(interaction, 'mechanism', None),
            "management": interaction.management,
            "is_dangerous": interaction.is_dangerous,
            "source": interaction.source,
        }

    def check_multiple_interactions(
        self, proposed_drug: str, existing_drugs: list[str]
    ) -> list[dict]:
        if not existing_drugs:
            return []

        all_drugs = [proposed_drug] + existing_drugs
        interactions = self.interaction_repo.check_multiple_interactions(all_drugs)

        # Map database severity to display severity for RiskEngine
        for interaction in interactions:
            raw_severity = interaction.get("severity", "unknown")
            interaction["severity"] = self.SEVERITY_DISPLAY.get(raw_severity, "unknown")
            interaction["severity_raw"] = raw_severity  # Keep original for reference

        return interactions

    def get_all_interactions_for_drug(self, drug_name: str) -> list[dict]:
        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            return []

        interactions = self.interaction_repo.get_all_interactions(drug)
        
        return [
            {
                "drug": interaction.drug_b.canonical_name if interaction.drug_a.canonical_name == drug_name.lower() else interaction.drug_a.canonical_name,
                "severity": interaction.severity,
                "severity_display": self.SEVERITY_DISPLAY.get(interaction.severity, "unknown"),
                "description": interaction.description,
                "is_dangerous": interaction.is_dangerous,
            }
            for interaction in interactions
        ]

    def get_dangerous_interactions(self, drug_name: str) -> list[dict]:
        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            return []

        interactions = self.interaction_repo.get_dangerous_interactions(drug)
        
        return [
            {
                "drug": interaction.drug_b.canonical_name if interaction.drug_a.canonical_name == drug_name.lower() else interaction.drug_a.canonical_name,
                "severity": interaction.severity,
                "description": interaction.description,
                "clinical_effect": interaction.clinical_effect,
                "management": interaction.management,
            }
            for interaction in interactions
        ]

    def has_dangerous_interaction(
        self, proposed_drug: str, existing_drugs: list[str]
    ) -> bool:
        interactions = self.check_multiple_interactions(proposed_drug, existing_drugs)
        return any(
            i["severity"] in ["contraindicated", "major"]
            for i in interactions
        )

    def get_highest_severity(self, interactions: list[dict]) -> str:
        if not interactions:
            return "none"

        severity_order = {
            "contraindicated": 0,
            "major": 1,
            "moderate": 2,
            "minor": 3,
            "unknown": 4,
        }

        severities = [i.get("severity", "unknown") for i in interactions]
        highest = min(severities, key=lambda s: severity_order.get(s, 5))
        
        return highest

    def get_interaction_summary(self, proposed_drug: str, existing_drugs: list[str]) -> dict:
        """Get a summary of interactions between proposed drug and existing drugs."""
        interactions = self.check_multiple_interactions(proposed_drug, existing_drugs)

        return {
            "total_interactions": len(interactions),
            "risk_level": self.get_highest_severity(interactions),
        }
