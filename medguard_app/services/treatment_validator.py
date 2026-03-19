from typing import Optional
import logging

from apps.data_access.repositories import DrugRepository

logger = logging.getLogger(__name__)


class TreatmentValidator:
    
    def __init__(self, drug_repo: Optional[DrugRepository] = None):
        self.drug_repo = drug_repo or DrugRepository()

    def does_drug_treat_symptom(self, drug_name: str, symptom: str) -> dict:
        drug_lower = drug_name.lower().strip()
        symptom_lower = symptom.lower().strip()

        db_result = self.drug_repo.does_drug_treat_symptom(drug_name, symptom)
        if db_result.get("treats"):
            return db_result

        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            return {
                "treats": False,
                "confidence": "low",
                "matched_symptom": None,
                "reason": f"Drug '{drug_name}' not found in database",
                "source": "not_found",
            }

        db_indications = self.drug_repo.get_indications(drug)
        
        if db_indications:
            similar_symptoms = self._find_similar_symptoms_vector(
                symptom_lower, list(db_indications)
            )
            if similar_symptoms:
                best_match = similar_symptoms[0]
                return {
                    "treats": True,
                    "confidence": best_match["confidence"],
                    "matched_symptom": best_match["matched_symptom"],
                    "reason": f"{drug_name} treats {best_match['matched_symptom']}, similar to '{symptom}' (similarity: {best_match['similarity']:.0%})",
                    "source": "vector_similarity",
                }

        return {
            "treats": False,
            "confidence": "low",
            "matched_symptom": None,
            "reason": f"No indication found for {drug_name} treating {symptom}",
            "source": "no_match",
        }

    def _find_similar_symptoms_vector(
        self, user_symptom: str, known_symptoms: list[str]
    ) -> list[dict]:
        if not known_symptoms:
            return []

        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer('BAAI/bge-base-en-v1.5')
            user_embedding = model.encode(user_symptom, normalize_embeddings=True)

            matches = []
            for known_symptom in known_symptoms:
                known_embedding = model.encode(known_symptom, normalize_embeddings=True)
                similarity = float(user_embedding @ known_embedding)

                if similarity >= 0.5:
                    confidence = "high" if similarity >= 0.75 else "medium"
                    matches.append({
                        "matched_symptom": known_symptom,
                        "similarity": similarity,
                        "confidence": confidence,
                    })

            matches.sort(key=lambda x: x["similarity"], reverse=True)
            return matches

        except Exception as e:
            logger.warning(f"Vector similarity search failed: {e}")
            return self._fallback_symptom_matching(user_symptom, known_symptoms)

    def _fallback_symptom_matching(
        self, user_symptom: str, known_symptoms: list[str]
    ) -> list[dict]:
        user_lower = user_symptom.lower().strip()
        matches = []

        for known in known_symptoms:
            known_lower = known.lower().strip()
            
            if user_lower == known_lower:
                matches.append({
                    "matched_symptom": known,
                    "similarity": 1.0,
                    "confidence": "high",
                })
            elif user_lower in known_lower or known_lower in user_lower:
                matches.append({
                    "matched_symptom": known,
                    "similarity": 0.7,
                    "confidence": "medium",
                })

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    def validate_treatment_for_symptoms(
        self, drug_name: str, symptoms: list[str]
    ) -> dict:
        if not symptoms:
            return {
                "overall_treats": False,
                "confidence": "low",
                "reason": "No symptoms provided to validate against",
            }

        drug = self.drug_repo.get_by_name(drug_name)
        if not drug:
            return {
                "overall_treats": False,
                "confidence": "low",
                "reason": f"Drug '{drug_name}' not found in database",
            }

        matched_symptoms = []
        unmatched_symptoms = []

        for symptom in symptoms:
            result = self.does_drug_treat_symptom(drug_name, symptom)
            if result.get("treats"):
                matched_symptoms.append({
                    "symptom": symptom,
                    "matched": result.get("matched_symptom"),
                    "confidence": result.get("confidence"),
                })
            else:
                unmatched_symptoms.append(symptom)

        if matched_symptoms:
            confidence_level = "high" if len(matched_symptoms) >= len(symptoms) * 0.8 else "medium"
            return {
                "overall_treats": True,
                "confidence": confidence_level,
                "matched_symptoms": matched_symptoms,
                "unmatched_symptoms": unmatched_symptoms,
                "reason": f"{drug_name} treats {len(matched_symptoms)} of {len(symptoms)} symptoms",
            }
        else:
            return {
                "overall_treats": False,
                "confidence": "low",
                "unmatched_symptoms": unmatched_symptoms,
                "reason": f"{drug_name} does not treat any of the provided symptoms",
            }

    def get_alternative_drugs_for_symptom(self, symptom: str, limit: int = 5) -> list[dict]:
        return self.drug_repo.get_drugs_for_symptom(symptom, limit=limit)
