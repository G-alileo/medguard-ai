"""
Side Effect Analyzer - Analyze if drug side effects overlap with user symptoms.
"""

import logging
from typing import Optional

from data_access.repositories import DrugRepository

logger = logging.getLogger(__name__)


class SideEffectAnalyzer:
    """
    Analyzes potential side effect issues based on user's current symptoms.
    """

    # Common drug side effects (supplement database data)
    KNOWN_SIDE_EFFECTS = {
        "acetaminophen": [
            "nausea", "vomiting", "loss of appetite", "sweating",
            "liver damage", "rash",
        ],
        "ibuprofen": [
            "stomach pain", "nausea", "vomiting", "diarrhea", "constipation",
            "dizziness", "headache", "drowsiness", "rash", "edema",
            "hypertension", "kidney problems", "gastrointestinal bleeding",
        ],
        "aspirin": [
            "stomach pain", "heartburn", "nausea", "vomiting",
            "gastrointestinal bleeding", "rash", "tinnitus", "dizziness",
        ],
        "naproxen": [
            "stomach pain", "nausea", "diarrhea", "constipation", "headache",
            "dizziness", "drowsiness", "rash", "edema", "hypertension",
        ],
        "diphenhydramine": [
            "drowsiness", "dizziness", "dry mouth", "constipation",
            "blurred vision", "confusion", "urinary retention",
        ],
        "loratadine": [
            "headache", "drowsiness", "dry mouth", "fatigue",
        ],
        "omeprazole": [
            "headache", "diarrhea", "nausea", "abdominal pain",
            "constipation", "flatulence",
        ],
        "metformin": [
            "nausea", "vomiting", "diarrhea", "abdominal pain",
            "loss of appetite", "metallic taste", "lactic acidosis",
        ],
        "lisinopril": [
            "cough", "dizziness", "headache", "fatigue", "nausea",
            "hypotension", "hyperkalemia", "angioedema",
        ],
        "amlodipine": [
            "edema", "dizziness", "flushing", "palpitations",
            "fatigue", "headache", "nausea",
        ],
        "atorvastatin": [
            "muscle pain", "joint pain", "diarrhea", "nausea",
            "headache", "insomnia", "rhabdomyolysis",
        ],
        "gabapentin": [
            "drowsiness", "dizziness", "fatigue", "ataxia",
            "edema", "weight gain", "blurred vision",
        ],
        "prednisone": [
            "increased appetite", "weight gain", "insomnia", "mood changes",
            "hypertension", "hyperglycemia", "osteoporosis", "edema",
        ],
        "fluoxetine": [
            "nausea", "headache", "insomnia", "drowsiness", "anxiety",
            "diarrhea", "dry mouth", "decreased appetite", "sexual dysfunction",
        ],
        "sertraline": [
            "nausea", "diarrhea", "insomnia", "drowsiness", "dizziness",
            "dry mouth", "headache", "sexual dysfunction",
        ],
        "warfarin": [
            "bleeding", "bruising", "nausea", "vomiting",
            "abdominal pain", "hair loss",
        ],
        "albuterol": [
            "tremor", "nervousness", "headache", "dizziness",
            "palpitations", "tachycardia", "insomnia",
        ],
        "amoxicillin": [
            "diarrhea", "nausea", "vomiting", "rash",
            "allergic reaction", "abdominal pain",
        ],
    }

    # Symptom similarity groups (symptoms that are related)
    SYMPTOM_GROUPS = {
        "gi_distress": [
            "nausea", "vomiting", "diarrhea", "constipation",
            "abdominal pain", "stomach pain", "heartburn", "indigestion",
        ],
        "cns_effects": [
            "dizziness", "drowsiness", "headache", "fatigue",
            "confusion", "insomnia", "anxiety",
        ],
        "cardiovascular": [
            "palpitations", "tachycardia", "hypertension", "hypotension",
            "edema", "chest pain",
        ],
        "skin": [
            "rash", "itching", "hives", "flushing",
        ],
    }

    def __init__(self, drug_repo: Optional[DrugRepository] = None):
        self.drug_repo = drug_repo or DrugRepository()
        self._symptom_to_group = self._build_symptom_group_index()

    def _build_symptom_group_index(self) -> dict[str, str]:
        """Build index of symptoms to their group."""
        index = {}
        for group, symptoms in self.SYMPTOM_GROUPS.items():
            for symptom in symptoms:
                index[symptom.lower()] = group
        return index

    def get_drug_side_effects(self, drug_name: str) -> list[str]:
        """
        Get known side effects for a drug.

        Args:
            drug_name: Canonical drug name

        Returns:
            List of side effect names
        """
        drug_lower = drug_name.lower().strip()

        # Check local knowledge base
        if drug_lower in self.KNOWN_SIDE_EFFECTS:
            return self.KNOWN_SIDE_EFFECTS[drug_lower]

        # Check database
        drug = self.drug_repo.get_by_name(drug_name)
        if drug:
            side_effects = self.drug_repo.get_side_effects(drug, limit=20)
            return [se["reaction"] for se in side_effects]

        return []

    def _symptom_matches(self, symptom1: str, symptom2: str) -> bool:
        """Check if two symptoms match (exact or similar)."""
        s1 = symptom1.lower().strip()
        s2 = symptom2.lower().strip()

        # Exact match
        if s1 == s2:
            return True

        # Substring match
        if s1 in s2 or s2 in s1:
            return True

        # Same symptom group
        group1 = self._symptom_to_group.get(s1)
        group2 = self._symptom_to_group.get(s2)
        if group1 and group2 and group1 == group2:
            return True

        return False

    def analyze_side_effect_overlap(
        self,
        drug_name: str,
        symptoms: list[str],
    ) -> dict:
        """
        Check if drug's side effects overlap with user's current symptoms.

        This is important because:
        1. Drug may worsen existing symptoms
        2. User may be more sensitive to certain side effects

        Args:
            drug_name: Canonical drug name
            symptoms: List of user's current symptoms

        Returns:
            Dict with overlap analysis
        """
        if not symptoms:
            return {
                "overlapping_symptoms": [],
                "risk_increase": 0,
                "explanation": "No symptoms provided for analysis",
                "additional_risks": [],
            }

        side_effects = self.get_drug_side_effects(drug_name)

        if not side_effects:
            return {
                "overlapping_symptoms": [],
                "risk_increase": 0,
                "explanation": f"No side effect data available for {drug_name}",
                "additional_risks": [],
            }

        # Find overlapping symptoms
        overlaps = []
        for symptom in symptoms:
            symptom_lower = symptom.lower().strip()
            for side_effect in side_effects:
                if self._symptom_matches(symptom_lower, side_effect):
                    overlaps.append({
                        "user_symptom": symptom,
                        "drug_side_effect": side_effect,
                        "match_type": "exact" if symptom_lower == side_effect.lower() else "related",
                    })

        # Calculate risk increase
        # Base: 5 points per exact match, 3 points per related match
        risk_increase = 0
        for overlap in overlaps:
            if overlap["match_type"] == "exact":
                risk_increase += 5
            else:
                risk_increase += 3

        # Cap at 30
        risk_increase = min(risk_increase, 30)

        # Build explanation
        if overlaps:
            symptom_list = list(set(o["user_symptom"] for o in overlaps))
            explanation = (
                f"{drug_name} may worsen or cause similar symptoms to what you're experiencing: "
                f"{', '.join(symptom_list)}. "
                "Consider monitoring these symptoms closely if you take this medication."
            )
        else:
            explanation = (
                f"No significant overlap between {drug_name}'s common side effects "
                "and your current symptoms."
            )

        # Additional risks (severe side effects not in symptoms)
        severe_side_effects = [
            "gastrointestinal bleeding", "liver damage", "rhabdomyolysis",
            "angioedema", "lactic acidosis", "allergic reaction",
        ]
        additional_risks = [
            se for se in side_effects
            if se.lower() in [s.lower() for s in severe_side_effects]
        ]

        return {
            "overlapping_symptoms": overlaps,
            "overlapping_count": len(overlaps),
            "risk_increase": risk_increase,
            "explanation": explanation,
            "additional_risks": additional_risks,
            "all_side_effects": side_effects[:10],  # Top 10 for reference
        }

    def get_side_effect_warnings(
        self,
        drug_name: str,
    ) -> list[str]:
        """
        Get important warnings about drug side effects.

        Returns list of warning strings.
        """
        drug_lower = drug_name.lower().strip()
        warnings = []

        # Specific warnings based on drug class
        if drug_lower in ["ibuprofen", "aspirin", "naproxen"]:
            warnings.append("NSAIDs can cause stomach bleeding, especially with long-term use")
            warnings.append("Avoid if you have kidney problems or ulcers")

        if drug_lower in ["warfarin"]:
            warnings.append("Increased bleeding risk - watch for unusual bruising or bleeding")
            warnings.append("Many drugs and foods interact with warfarin")

        if drug_lower in ["metformin"]:
            warnings.append("Can cause GI upset initially - take with food")
            warnings.append("Stay hydrated to reduce risk of lactic acidosis")

        if drug_lower in ["gabapentin", "pregabalin"]:
            warnings.append("May cause drowsiness - avoid driving until you know how it affects you")
            warnings.append("Do not stop suddenly - taper off gradually")

        if drug_lower in ["fluoxetine", "sertraline"]:
            warnings.append("May take 2-4 weeks to see full effect")
            warnings.append("Monitor for worsening mood or suicidal thoughts, especially when starting")

        return warnings
