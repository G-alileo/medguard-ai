from typing import Optional
import logging
from dataclasses import dataclass

from apps.data_access.repositories import DrugRepository

logger = logging.getLogger(__name__)


@dataclass
class DrugAlternative:
    name: str
    generic_name: str
    similarity_score: float
    advantages: list[str]
    considerations: list[str]
    reason: str


class DrugAlternativesService:
    
    def __init__(self, drug_repo: Optional[DrugRepository] = None):
        self.drug_repo = drug_repo or DrugRepository()

    def get_alternatives(
        self, drug_name: str, limit: int = 5
    ) -> list[DrugAlternative]:
        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            logger.warning(f"Drug '{drug_name}' not found in database")
            return []

        alternatives_data = self.drug_repo.get_alternatives(drug, limit=limit)

        alternatives = []
        for alt in alternatives_data:
            alternatives.append(
                DrugAlternative(
                    name=alt["name"],
                    generic_name=alt["name"],
                    similarity_score=alt.get("similarity_score", 0.0),
                    advantages=alt.get("advantages", []),
                    considerations=alt.get("considerations", []),
                    reason=alt.get("reason", ""),
                )
            )

        return alternatives

    def find_safer_alternative(
        self,
        drug_name: str,
        reason: str = "fewer_side_effects",
        limit: int = 3,
    ) -> list[DrugAlternative]:
        alternatives = self.get_alternatives(drug_name, limit=limit * 2)

        if reason == "fewer_side_effects":
            filtered = [
                alt for alt in alternatives
                if "fewer side effects" in str(alt.reason).lower() or
                   "safer" in str(alt.reason).lower()
            ]
        elif reason == "fewer_interactions":
            filtered = [
                alt for alt in alternatives
                if "fewer interactions" in str(alt.reason).lower()
            ]
        else:
            filtered = alternatives

        return filtered[:limit] if filtered else alternatives[:limit]

    def get_otc_alternatives(
        self, drug_name: str, limit: int = 3
    ) -> list[DrugAlternative]:
        alternatives = self.get_alternatives(drug_name, limit=limit * 2)

        otc_alternatives = []
        for alt_data in self.drug_repo.get_alternatives(
            self.drug_repo.get_by_name(drug_name), limit=limit * 2
        ):
            if alt_data.get("is_otc"):
                otc_alternatives.append(
                    DrugAlternative(
                        name=alt_data["name"],
                        generic_name=alt_data["name"],
                        similarity_score=alt_data.get("similarity_score", 0.0),
                        advantages=alt_data.get("advantages", []),
                        considerations=alt_data.get("considerations", []),
                        reason=alt_data.get("reason", ""),
                    )
                )

        return otc_alternatives[:limit]

    def get_alternatives_for_interaction(
        self,
        drug_name: str,
        interacting_drug: str,
        limit: int = 3,
    ) -> list[DrugAlternative]:
        alternatives = self.get_alternatives(drug_name, limit=limit * 2)

        from apps.data_access.repositories import InteractionRepository
        interaction_repo = InteractionRepository()

        safe_alternatives = []
        for alt in alternatives:
            interaction = interaction_repo.check_interaction(alt.generic_name, interacting_drug)
            
            if not interaction or interaction.severity in ["minor", "unknown"]:
                safe_alternatives.append(alt)

        return safe_alternatives[:limit] if safe_alternatives else alternatives[:limit]

    def format_alternatives_for_display(
        self, alternatives: list[DrugAlternative]
    ) -> list[dict]:
        return [
            {
                "name": alt.name,
                "reason": alt.reason,
                "advantages": alt.advantages,
                "considerations": alt.considerations,
                "similarity_score": alt.similarity_score,
            }
            for alt in alternatives
        ]

    def find_alternatives(
        self,
        drug_name: str,
        symptoms: list[str],
        existing_medications: list[str],
        limit: int = 3
    ) -> list[DrugAlternative]:
        """
        Find alternative drugs considering symptoms and existing medications.
        This is the main method called by the DecisionPipeline.
        """
        try:
            # Start with basic alternatives
            base_alternatives = self.get_alternatives(drug_name, limit=limit * 2)

            if not base_alternatives:
                return []

            # If there are existing medications, filter for ones with fewer interactions
            if existing_medications:
                safe_alternatives = []
                from apps.data_access.repositories import InteractionRepository
                interaction_repo = InteractionRepository()

                for alt in base_alternatives:
                    has_major_interaction = False

                    for existing_med in existing_medications:
                        interaction = interaction_repo.check_interaction(
                            alt.generic_name, existing_med
                        )

                        if interaction and interaction.severity in ["contraindicated", "major"]:
                            has_major_interaction = True
                            break

                    if not has_major_interaction:
                        # Add interaction safety to advantages
                        advantages = list(alt.advantages) if alt.advantages else []
                        if existing_medications:
                            advantages.append("No major interactions with your current medications")

                        safe_alternatives.append(DrugAlternative(
                            name=alt.name,
                            generic_name=alt.generic_name,
                            similarity_score=alt.similarity_score,
                            advantages=advantages,
                            considerations=alt.considerations,
                            reason=alt.reason
                        ))

                if safe_alternatives:
                    return safe_alternatives[:limit]

            # Return the best alternatives we found
            return base_alternatives[:limit]

        except Exception as e:
            logger.error(f"Error finding alternatives for {drug_name}: {e}")
            return []
