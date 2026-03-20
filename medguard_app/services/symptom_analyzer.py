import logging
from typing import Dict, List, Tuple, Optional
from apps.data_access.vector_store import get_chroma_client

logger = logging.getLogger(__name__)


class SymptomAnalyzer:

    SYMPTOM_CONTEXTS = {
        "viral_infection": {
            "patterns": ["fever + sneezing", "fever + runny nose", "fever + cough", "fever + sore throat"],
            "appropriate_treatments": ["acetaminophen", "ibuprofen", "rest", "fluids"],
            "inappropriate_treatments": ["antibiotics", "antihistamines"],
            "confidence_boost": 0.15,
        },
        "allergic_reaction": {
            "patterns": ["hay fever + sneezing", "allergies + runny nose", "seasonal allergies + itchy eyes"],
            "appropriate_treatments": ["antihistamines", "loratadine", "cetirizine"],
            "inappropriate_treatments": ["fever reducers only", "antibiotics"],
            "confidence_boost": 0.20,
        },
        "bacterial_infection": {
            "patterns": ["fever + productive cough", "fever + thick nasal discharge", "fever + ear pain"],
            "appropriate_treatments": ["antibiotics", "fever reducers"],
            "inappropriate_treatments": ["antihistamines only"],
            "confidence_boost": 0.10,
        },
        "headache_cluster": {
            "patterns": ["headache + nausea", "migraine + light sensitivity", "tension headache + stress"],
            "appropriate_treatments": ["acetaminophen", "ibuprofen", "sumatriptan"],
            "inappropriate_treatments": ["antihistamines", "antibiotics"],
            "confidence_boost": 0.15,
        },
        "gi_distress": {
            "patterns": ["nausea + vomiting", "stomach pain + diarrhea", "heartburn + acid reflux"],
            "appropriate_treatments": ["antacids", "anti-diarrheals", "proton pump inhibitors"],
            "inappropriate_treatments": ["fever reducers", "antihistamines"],
            "confidence_boost": 0.18,
        }
    }

    HIGH_RISK_COMBINATIONS = {
        "fever_with_breathing": ["fever + difficulty breathing", "fever + shortness of breath"],
        "chest_pain_combinations": ["chest pain + shortness of breath", "chest pain + arm pain"],
        "severe_headache": ["sudden severe headache", "worst headache ever", "headache + vision changes"],
        "allergic_emergency": ["difficulty breathing + hives", "swelling + difficulty swallowing"],
    }

    def __init__(self, vector_store=None):
        self.vector_store = vector_store or self._get_vector_store()

    def _get_vector_store(self):
        """Get vector store client safely."""
        try:
            return get_chroma_client()
        except Exception as e:
            logger.warning(f"Vector store not available: {e}")
            return None

    def analyze_symptom_combination(self, symptoms: List[str]) -> Dict:

        if not symptoms:
            return {"context": "none", "confidence": 0.0, "suggestions": []}

        combined_symptoms = self._normalize_symptom_combination(symptoms)

        pattern_match = self._match_symptom_patterns(combined_symptoms, symptoms)

        vector_context = self._get_vector_context(combined_symptoms)

        risk_flags = self._check_high_risk_combinations(combined_symptoms)

        return {
            "context": pattern_match.get("context", "unknown"),
            "confidence": pattern_match.get("confidence", 0.5),
            "appropriate_treatments": pattern_match.get("appropriate_treatments", []),
            "inappropriate_treatments": pattern_match.get("inappropriate_treatments", []),
            "vector_context": vector_context,
            "risk_flags": risk_flags,
            "treatment_guidance": self._generate_treatment_guidance(pattern_match, risk_flags),
        }

    def _normalize_symptom_combination(self, symptoms: List[str]) -> str:
        """Create a normalized combination string."""
        normalized = [s.lower().strip() for s in symptoms if s.strip()]
        return " + ".join(sorted(normalized))

    def _match_symptom_patterns(self, combined_symptoms: str, original_symptoms: List[str]) -> Dict:
        """Match against known symptom patterns."""
        best_match = {
            "context": "unknown",
            "confidence": 0.0,
            "appropriate_treatments": [],
            "inappropriate_treatments": [],
        }

        for context, info in self.SYMPTOM_CONTEXTS.items():
            for pattern in info["patterns"]:
                confidence = self._calculate_pattern_similarity(combined_symptoms, pattern)

                if confidence > best_match["confidence"]:
                    best_match = {
                        "context": context,
                        "confidence": confidence + info.get("confidence_boost", 0),
                        "appropriate_treatments": info["appropriate_treatments"],
                        "inappropriate_treatments": info["inappropriate_treatments"],
                    }

        return best_match

    def _calculate_pattern_similarity(self, symptoms: str, pattern: str) -> float:
        """Calculate similarity between symptom combination and known pattern."""
        symptoms_words = set(symptoms.lower().replace(" + ", " ").split())
        pattern_words = set(pattern.lower().replace(" + ", " ").split())

        common_words = {"and", "with", "plus", "or"}
        symptoms_words -= common_words
        pattern_words -= common_words

        if not pattern_words:
            return 0.0

        intersection = symptoms_words.intersection(pattern_words)
        union = symptoms_words.union(pattern_words)

        return len(intersection) / len(union) if union else 0.0

    def _get_vector_context(self, combined_symptoms: str) -> List[Dict]:
        """Get contextual information from vector store."""
        if not self.vector_store:
            return []

        try:
            query = f"symptoms {combined_symptoms} treatment appropriate medication"

            context_results = self.vector_store.search_medical_context(
                query=query,
                limit=3,
                threshold=0.7
            )

            return context_results

        except Exception as e:
            logger.warning(f"Error retrieving vector context: {e}")
            return []

    def _check_high_risk_combinations(self, combined_symptoms: str) -> List[str]:
        """Check for high-risk symptom combinations."""
        risk_flags = []

        for risk_type, patterns in self.HIGH_RISK_COMBINATIONS.items():
            for pattern in patterns:
                if self._calculate_pattern_similarity(combined_symptoms, pattern) > 0.6:
                    risk_flags.append(risk_type)
                    break

        return risk_flags

    def _generate_treatment_guidance(self, pattern_match: Dict, risk_flags: List[str]) -> str:
        """Generate treatment guidance based on analysis."""
        context = pattern_match.get("context", "unknown")

        if risk_flags:
            return "URGENT: These symptoms may indicate a serious condition. Seek immediate medical attention."

        guidance_map = {
            "viral_infection": "Consider fever reducers and rest. Antihistamines are not typically helpful for viral symptoms.",
            "allergic_reaction": "Antihistamines are most appropriate. Fever reducers alone won't address the allergic response.",
            "bacterial_infection": "May require antibiotic treatment. Consult healthcare provider if symptoms worsen.",
            "headache_cluster": "Pain relievers are appropriate. Consider trigger avoidance and stress management.",
            "gi_distress": "Focus on stomach-specific treatments. Avoid NSAIDs if stomach irritation is present.",
        }

        return guidance_map.get(context, "Consider consulting a healthcare provider for appropriate treatment.")

    def improve_treatment_validation(self, drug: str, symptoms: List[str]) -> Dict:

        analysis = self.analyze_symptom_combination(symptoms)

        appropriate_treatments = analysis.get("appropriate_treatments", [])
        inappropriate_treatments = analysis.get("inappropriate_treatments", [])

        drug_lower = drug.lower()

        confidence_modifier = 0.0
        appropriateness_score = 0.5

        for appropriate in appropriate_treatments:
            if appropriate.lower() in drug_lower or drug_lower in appropriate.lower():
                confidence_modifier += 0.2
                appropriateness_score = 0.8
                break

        for inappropriate in inappropriate_treatments:
            if inappropriate.lower() in drug_lower or drug_lower in inappropriate.lower():
                confidence_modifier -= 0.3
                appropriateness_score = 0.2
                break

        return {
            "confidence_modifier": confidence_modifier,
            "appropriateness_score": appropriateness_score,
            "context_explanation": analysis.get("treatment_guidance", ""),
            "symptom_context": analysis.get("context", "unknown"),
        }


_symptom_analyzer = None

def get_symptom_analyzer():
    """Get global SymptomAnalyzer instance."""
    global _symptom_analyzer
    if _symptom_analyzer is None:
        _symptom_analyzer = SymptomAnalyzer()
    return _symptom_analyzer