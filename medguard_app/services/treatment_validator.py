"""
Treatment Validator - Check if a drug is indicated for specific symptoms.
"""

import logging
from typing import Optional

from data_access.repositories import DrugRepository

logger = logging.getLogger(__name__)


class TreatmentValidator:
    """
    Validates whether a drug is indicated for treating specific symptoms/conditions.
    """

    # Common drug-indication mappings (supplement database data)
    # These are well-established OTC drug uses
    KNOWN_TREATMENTS = {
        "acetaminophen": [
            "headache", "fever", "pain", "mild pain", "muscle pain",
            "toothache", "backache", "arthritis", "menstrual pain",
        ],
        "ibuprofen": [
            "headache", "fever", "pain", "inflammation", "muscle pain",
            "toothache", "backache", "arthritis", "menstrual pain",
            "swelling", "joint pain",
        ],
        "aspirin": [
            "headache", "fever", "pain", "inflammation", "heart attack prevention",
            "blood clot prevention", "arthritis",
        ],
        "naproxen": [
            "headache", "pain", "inflammation", "arthritis", "muscle pain",
            "menstrual pain", "gout",
        ],
        "diphenhydramine": [
            "allergy", "allergic reaction", "insomnia", "sleep",
            "itching", "hives", "rash", "pruritus", "cold symptoms",
        ],
        "loratadine": [
            "allergy", "hay fever", "allergic rhinitis", "hives",
            "itching", "sneezing", "runny nose",
        ],
        "omeprazole": [
            "heartburn", "acid reflux", "gerd", "stomach ulcer",
            "gastric ulcer", "indigestion",
        ],
        "ranitidine": [
            "heartburn", "acid reflux", "stomach ulcer", "indigestion",
        ],
        "loperamide": [
            "diarrhea", "loose stools", "traveler's diarrhea",
        ],
        "bisacodyl": [
            "constipation",
        ],
        "guaifenesin": [
            "cough", "chest congestion", "mucus",
        ],
        "dextromethorphan": [
            "cough", "dry cough",
        ],
        "pseudoephedrine": [
            "nasal congestion", "sinus congestion", "stuffy nose",
        ],
        "phenylephrine": [
            "nasal congestion", "sinus congestion",
        ],
        "metformin": [
            "diabetes", "type 2 diabetes", "high blood sugar",
        ],
        "lisinopril": [
            "hypertension", "high blood pressure", "heart failure",
        ],
        "amlodipine": [
            "hypertension", "high blood pressure", "angina", "chest pain",
        ],
        "atorvastatin": [
            "high cholesterol", "hyperlipidemia", "cardiovascular prevention",
        ],
        "levothyroxine": [
            "hypothyroidism", "low thyroid", "thyroid deficiency",
        ],
        "albuterol": [
            "asthma", "bronchospasm", "wheezing", "shortness of breath",
            "dyspnea", "breathing difficulty",
        ],
        "fluoxetine": [
            "depression", "anxiety", "ocd", "panic disorder",
        ],
        "sertraline": [
            "depression", "anxiety", "ptsd", "panic disorder", "ocd",
        ],
        "gabapentin": [
            "nerve pain", "neuropathy", "seizures", "postherpetic neuralgia",
        ],
        "prednisone": [
            "inflammation", "allergic reaction", "asthma", "arthritis",
            "autoimmune conditions", "swelling",
        ],
        "amoxicillin": [
            "bacterial infection", "ear infection", "sinus infection",
            "respiratory infection", "urinary tract infection",
        ],
        "azithromycin": [
            "bacterial infection", "respiratory infection", "bronchitis",
            "pneumonia", "skin infection",
        ],
        "warfarin": [
            "blood clot prevention", "atrial fibrillation", "dvt prevention",
            "pulmonary embolism prevention",
        ],
    }

    def __init__(self, drug_repo: Optional[DrugRepository] = None):
        self.drug_repo = drug_repo or DrugRepository()
        # Build reverse lookup (symptom → drugs)
        self._symptom_to_drugs = self._build_symptom_index()

    def _build_symptom_index(self) -> dict[str, list[str]]:
        """Build index of symptoms to drugs that treat them."""
        index = {}
        for drug, symptoms in self.KNOWN_TREATMENTS.items():
            for symptom in symptoms:
                symptom_lower = symptom.lower()
                if symptom_lower not in index:
                    index[symptom_lower] = []
                index[symptom_lower].append(drug)
        return index

    def does_drug_treat_symptom(
        self,
        drug_name: str,
        symptom: str,
    ) -> dict:
        """
        Check if a drug is indicated for treating a specific symptom.

        Args:
            drug_name: Canonical drug name
            symptom: Normalized symptom name

        Returns:
            Dict with:
                - treats: bool
                - confidence: "high" | "medium" | "low"
                - matched_symptom: str (what symptom was matched)
                - reason: str (explanation)
        """
        drug_lower = drug_name.lower().strip()
        symptom_lower = symptom.lower().strip()

        # Check known treatments first
        if drug_lower in self.KNOWN_TREATMENTS:
            known_symptoms = [s.lower() for s in self.KNOWN_TREATMENTS[drug_lower]]

            # Direct match
            if symptom_lower in known_symptoms:
                return {
                    "treats": True,
                    "confidence": "high",
                    "matched_symptom": symptom_lower,
                    "reason": f"{drug_name} is commonly used to treat {symptom}",
                }

            # Partial match
            for known in known_symptoms:
                if symptom_lower in known or known in symptom_lower:
                    return {
                        "treats": True,
                        "confidence": "medium",
                        "matched_symptom": known,
                        "reason": f"{drug_name} treats {known}, which is related to {symptom}",
                    }

        # Check database indications
        drug = self.drug_repo.get_by_name(drug_name)
        if drug:
            indications = self.drug_repo.get_indications(drug)
            for indication in indications:
                indication_lower = indication.lower()
                if symptom_lower in indication_lower or indication_lower in symptom_lower:
                    return {
                        "treats": True,
                        "confidence": "medium",
                        "matched_symptom": indication,
                        "reason": f"{drug_name} is indicated for {indication}",
                    }

        # No match found - check if symptom is treated by other drugs
        alternative_drugs = self._symptom_to_drugs.get(symptom_lower, [])

        return {
            "treats": False,
            "confidence": "low",
            "matched_symptom": None,
            "reason": f"No indication found for {drug_name} treating {symptom}",
            "alternatives": alternative_drugs[:3] if alternative_drugs else None,
        }

    def validate_treatment_for_symptoms(
        self,
        drug_name: str,
        symptoms: list[str],
    ) -> dict:
        """
        Check if a drug is indicated for ANY of the given symptoms.

        Args:
            drug_name: Canonical drug name
            symptoms: List of normalized symptoms

        Returns:
            Dict with overall assessment and per-symptom results
        """
        if not symptoms:
            return {
                "overall_treats": False,
                "confidence": "low",
                "reason": "No symptoms provided",
                "symptom_results": [],
            }

        results = []
        any_treats = False
        best_confidence = "low"
        confidence_order = {"high": 3, "medium": 2, "low": 1}

        for symptom in symptoms:
            result = self.does_drug_treat_symptom(drug_name, symptom)
            results.append({
                "symptom": symptom,
                **result,
            })

            if result["treats"]:
                any_treats = True
                if confidence_order.get(result["confidence"], 0) > confidence_order.get(best_confidence, 0):
                    best_confidence = result["confidence"]

        # Build reason
        if any_treats:
            treated = [r["symptom"] for r in results if r["treats"]]
            reason = f"{drug_name} is indicated for: {', '.join(treated)}"
        else:
            reason = f"{drug_name} is not indicated for any of the reported symptoms"

        return {
            "overall_treats": any_treats,
            "confidence": best_confidence,
            "reason": reason,
            "symptom_results": results,
            "treated_symptoms": [r["symptom"] for r in results if r["treats"]],
            "untreated_symptoms": [r["symptom"] for r in results if not r["treats"]],
        }
