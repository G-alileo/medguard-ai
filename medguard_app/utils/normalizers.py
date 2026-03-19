"""
Input Normalizer - Normalize user inputs (symptoms, drug names) to canonical forms.
"""

import re
from typing import Optional

from apps.pipeline.processing import get_normalizer, NormalizationResult


class InputNormalizer:
    """
    Normalizes user inputs to canonical forms for consistent processing.
    """

    SYMPTOM_MAPPINGS = {
        "head pain": "headache",
        "head ache": "headache",
        "migraine": "headache",
        "tension headache": "headache",
        "throbbing head": "headache",
        "skull pain": "headache",
        "stomach ache": "abdominal pain",
        "stomach pain": "abdominal pain",
        "tummy ache": "abdominal pain",
        "belly pain": "abdominal pain",
        "gut pain": "abdominal pain",
        "stomachache": "abdominal pain",
        "feeling sick": "nausea",
        "queasy": "nausea",
        "sick to stomach": "nausea",
        "want to vomit": "nausea",
        "high temperature": "fever",
        "febrile": "fever",
        "pyrexia": "fever",
        "running a temperature": "fever",
        "ache": "pain",
        "soreness": "pain",
        "hurting": "pain",
        "tired": "fatigue",
        "exhausted": "fatigue",
        "tiredness": "fatigue",
        "exhaustion": "fatigue",
        "lack of energy": "fatigue",
        "lethargy": "fatigue",
        "dizzy": "dizziness",
        "lightheaded": "dizziness",
        "light headed": "dizziness",
        "vertigo": "dizziness",
        "spinning sensation": "dizziness",
        "shortness of breath": "dyspnea",
        "difficulty breathing": "dyspnea",
        "breathlessness": "dyspnea",
        "trouble breathing": "dyspnea",
        "can't breathe": "dyspnea",
        "skin rash": "rash",
        "skin irritation": "rash",
        "hives": "rash",
        "itchy skin": "pruritus",
        "itching": "pruritus",
        "can't sleep": "insomnia",
        "sleeplessness": "insomnia",
        "trouble sleeping": "insomnia",
        "sad": "depression",
        "feeling down": "depression",
        "low mood": "depression",
        "anxious": "anxiety",
        "worried": "anxiety",
        "nervousness": "anxiety",
        "loose stools": "diarrhea",
        "runny stomach": "diarrhea",
        "the runs": "diarrhea",
        "constipated": "constipation",
        "can't poop": "constipation",
        "throwing up": "vomiting",
        "puking": "vomiting",
        "being sick": "vomiting",
        "fast heartbeat": "tachycardia",
        "racing heart": "tachycardia",
        "heart pounding": "palpitations",
        "heart fluttering": "palpitations",
        "high blood pressure": "hypertension",
        "low blood pressure": "hypotension",
        "coughing": "cough",
        "runny nose": "rhinorrhea",
        "stuffy nose": "nasal congestion",
        "blocked nose": "nasal congestion",
        "sore throat": "pharyngitis",
        "throat pain": "pharyngitis",
    }

    def __init__(self):
        self.drug_normalizer = get_normalizer()
        self._symptom_lookup = {k.lower(): v for k, v in self.SYMPTOM_MAPPINGS.items()}

    def normalize_symptom(self, symptom: str) -> str:
        """
        Normalize a symptom description to a canonical form.

        Args:
            symptom: User-provided symptom description

        Returns:
            Normalized symptom name
        """
        if not symptom:
            return ""

        symptom_clean = symptom.strip().lower()
        symptom_clean = re.sub(r"[^\w\s]", "", symptom_clean)
        symptom_clean = " ".join(symptom_clean.split())

        if symptom_clean in self._symptom_lookup:
            return self._symptom_lookup[symptom_clean]

        for key, canonical in self._symptom_lookup.items():
            if key in symptom_clean:
                return canonical

        return symptom_clean

    def normalize_drug_name(self, drug_name: str) -> NormalizationResult:
        """
        Normalize a drug name to canonical form.

        Args:
            drug_name: User-provided drug name (brand, generic, or variation)

        Returns:
            NormalizationResult with canonical name and confidence
        """
        if not drug_name:
            return NormalizationResult(
                canonical_name=None,
                confidence=0.0,
                match_type="none",
                original_input="",
            )

        return self.drug_normalizer.normalize(drug_name)

    def normalize_drug_list(self, drug_names: list[str]) -> list[dict]:
        """
        Normalize a list of drug names.

        Returns list of dicts with original, canonical, and confidence.
        """
        results = []
        for name in drug_names:
            name = name.strip()
            if not name:
                continue

            result = self.normalize_drug_name(name)
            results.append({
                "original": name,
                "canonical": result.canonical_name or name.lower(),
                "confidence": result.confidence,
                "match_type": result.match_type,
            })

        return results

    def normalize_symptoms_list(self, symptoms: list[str]) -> list[dict]:
        """
        Normalize a list of symptoms.

        Returns list of dicts with original and normalized forms.
        """
        results = []
        seen = set()

        for symptom in symptoms:
            symptom = symptom.strip()
            if not symptom:
                continue

            normalized = self.normalize_symptom(symptom)
            if normalized not in seen:
                seen.add(normalized)
                results.append({
                    "original": symptom,
                    "normalized": normalized,
                })

        return results

    def normalize_inputs(
        self,
        symptoms: list[str],
        drug: str,
        existing_drugs: list[str],
    ) -> dict:
        """
        Normalize all inputs for the decision pipeline.

        Args:
            symptoms: List of user-reported symptoms
            drug: Proposed drug name
            existing_drugs: List of currently taken medications

        Returns:
            Dict with normalized versions of all inputs
        """
        normalized_symptoms = self.normalize_symptoms_list(symptoms)

        drug_result = self.normalize_drug_name(drug)

        normalized_existing = self.normalize_drug_list(existing_drugs)

        return {
            "symptoms": normalized_symptoms,
            "symptoms_canonical": [s["normalized"] for s in normalized_symptoms],
            "drug": {
                "original": drug,
                "canonical": drug_result.canonical_name or drug.lower().strip(),
                "confidence": drug_result.confidence,
                "match_type": drug_result.match_type,
            },
            "existing_drugs": normalized_existing,
            "existing_drugs_canonical": [
                d["canonical"] for d in normalized_existing
            ],
        }


_normalizer: Optional[InputNormalizer] = None


def get_input_normalizer() -> InputNormalizer:
    """Get the global InputNormalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = InputNormalizer()
    return _normalizer
