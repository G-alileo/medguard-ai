from typing import Optional
import logging

from apps.data_access.repositories import DrugRepository

logger = logging.getLogger(__name__)


class SideEffectAnalyzer:
    
    def __init__(self, drug_repo: Optional[DrugRepository] = None):
        self.drug_repo = drug_repo or DrugRepository()

    def analyze_side_effects(
        self, drug_name: str, user_symptoms: list[str]
    ) -> dict:
        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            return {
                "has_overlap": False,
                "confidence": "low",
                "overlapping_symptoms": [],
                "reason": f"Drug '{drug_name}' not found in database",
            }

        side_effects = self.drug_repo.get_side_effects_list(drug_name)
        
        if not side_effects:
            return {
                "has_overlap": False,
                "confidence": "low",
                "overlapping_symptoms": [],
                "reason": f"No side effect data available for {drug_name}",
            }

        overlapping = self._find_overlapping_symptoms(user_symptoms, side_effects)

        if overlapping:
            return {
                "has_overlap": True,
                "confidence": "high",
                "overlapping_symptoms": overlapping,
                "side_effects_count": len(side_effects),
                "reason": f"{drug_name} has {len(overlapping)} side effects that overlap with user symptoms",
            }
        else:
            return {
                "has_overlap": False,
                "confidence": "medium",
                "overlapping_symptoms": [],
                "side_effects_count": len(side_effects),
                "reason": f"No direct overlap found between symptoms and {drug_name} side effects",
            }

    def _find_overlapping_symptoms(
        self, user_symptoms: list[str], side_effects: list[str]
    ) -> list[dict]:
        overlapping = []
        side_effects_lower = [s.lower().strip() for s in side_effects]

        for symptom in user_symptoms:
            symptom_lower = symptom.lower().strip()
            
            if symptom_lower in side_effects_lower:
                overlapping.append({
                    "symptom": symptom,
                    "matched_side_effect": symptom,
                    "match_type": "exact",
                })
                continue

            similar = self._find_similar_side_effects(symptom_lower, side_effects)
            if similar:
                overlapping.append({
                    "symptom": symptom,
                    "matched_side_effect": similar[0]["side_effect"],
                    "match_type": "similar",
                    "similarity": similar[0]["similarity"],
                })

        return overlapping

    def _find_similar_side_effects(
        self, symptom: str, side_effects: list[str]
    ) -> list[dict]:
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer('BAAI/bge-base-en-v1.5')
            symptom_embedding = model.encode(symptom, normalize_embeddings=True)

            matches = []
            for side_effect in side_effects:
                effect_embedding = model.encode(side_effect, normalize_embeddings=True)
                similarity = float(symptom_embedding @ effect_embedding)

                if similarity >= 0.6:
                    matches.append({
                        "side_effect": side_effect,
                        "similarity": similarity,
                    })

            matches.sort(key=lambda x: x["similarity"], reverse=True)
            return matches

        except Exception as e:
            logger.warning(f"Vector similarity search for side effects failed: {e}")
            return self._fallback_side_effect_matching(symptom, side_effects)

    def _fallback_side_effect_matching(
        self, symptom: str, side_effects: list[str]
    ) -> list[dict]:
        matches = []
        symptom_lower = symptom.lower().strip()

        for effect in side_effects:
            effect_lower = effect.lower().strip()
            
            if symptom_lower in effect_lower or effect_lower in symptom_lower:
                matches.append({
                    "side_effect": effect,
                    "similarity": 0.7,
                })

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    def get_all_side_effects(self, drug_name: str) -> list[str]:
        return self.drug_repo.get_side_effects_list(drug_name)

    def get_severe_side_effects(self, drug_name: str) -> list[dict]:
        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            return []

        all_effects = self.drug_repo.get_side_effects(drug, limit=100)
        
        severe = [
            effect for effect in all_effects
            if effect.get("frequency") in ["common", "very_common"]
        ]

        return severe

    def calculate_side_effect_risk_score(
        self, drug_name: str, user_symptoms: list[str]
    ) -> int:
        analysis = self.analyze_side_effects(drug_name, user_symptoms)
        
        if not analysis.get("has_overlap"):
            return 0

        overlapping_count = len(analysis.get("overlapping_symptoms", []))
        
        if overlapping_count == 0:
            return 0
        elif overlapping_count == 1:
            return 15
        elif overlapping_count == 2:
            return 25
        else:
            return 30 + min(overlapping_count - 2, 3) * 5

    def analyze_side_effect_overlap(
        self, drug_name: str, symptoms: list[str]
    ) -> dict:
        """Analyze overlap between drug side effects and user symptoms."""
        analysis = self.analyze_side_effects(drug_name, symptoms)

        overlapping_symptoms = analysis.get("overlapping_symptoms", [])
        overlapping_count = len(overlapping_symptoms)

        # Calculate risk increase based on overlap
        risk_increase = 0
        if overlapping_count > 0:
            # Risk increases with more overlapping symptoms
            risk_increase = min(overlapping_count * 10, 40)  # Max 40 points

        return {
            "overlapping_count": overlapping_count,
            "overlapping_symptoms": overlapping_symptoms,
            "risk_increase": risk_increase,
        }
