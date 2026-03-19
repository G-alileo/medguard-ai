"""
Drug Name Normalizer - Standardize drug names across all sources.

Maps any drug name input (brand, generic, misspelling) to a canonical form.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from django.conf import settings
from rapidfuzz import fuzz, process


@dataclass
class NormalizationResult:
    """Result of drug name normalization."""

    canonical_name: Optional[str]
    confidence: float  # 0.0-1.0
    match_type: str  # 'exact', 'fuzzy', 'none'
    original_input: str
    suggestions: Optional[list[tuple[str, float]]] = None


class DrugNormalizer:
    """
    Normalizes drug names from any form to canonical names.

    Usage:
        normalizer = DrugNormalizer()
        result = normalizer.normalize("Tylenol 500mg")
        # result.canonical_name == "acetaminophen"
    """

    # Common brand-to-generic mappings (bootstrap data)
    BOOTSTRAP_MAPPINGS = {
        # Pain/Fever
        "tylenol": "acetaminophen",
        "paracetamol": "acetaminophen",
        "apap": "acetaminophen",
        "advil": "ibuprofen",
        "motrin": "ibuprofen",
        "aleve": "naproxen",
        "aspirin": "aspirin",
        "bayer": "aspirin",
        # Statins
        "lipitor": "atorvastatin",
        "crestor": "rosuvastatin",
        "zocor": "simvastatin",
        # Diabetes
        "glucophage": "metformin",
        # Blood pressure
        "norvasc": "amlodipine",
        "prinivil": "lisinopril",
        "zestril": "lisinopril",
        "cozaar": "losartan",
        # Antidepressants
        "prozac": "fluoxetine",
        "zoloft": "sertraline",
        "lexapro": "escitalopram",
        "celexa": "citalopram",
        # Thyroid
        "synthroid": "levothyroxine",
        # Proton pump inhibitors
        "prilosec": "omeprazole",
        "nexium": "esomeprazole",
        # Antibiotics
        "amoxil": "amoxicillin",
        "augmentin": "amoxicillin",
        "zithromax": "azithromycin",
        # Blood thinners
        "coumadin": "warfarin",
        # Respiratory
        "ventolin": "albuterol",
        "proventil": "albuterol",
        "salbutamol": "albuterol",
        # Nerve pain
        "neurontin": "gabapentin",
        "lyrica": "pregabalin",
        # Steroids
        "deltasone": "prednisone",
        # Diuretics
        "microzide": "hydrochlorothiazide",
        "hctz": "hydrochlorothiazide",
        # Antiparasitics
        "albendazole": "albendazole",
        "mebendazole": "mebendazole",
        "vermox": "mebendazole",
        # Allergy medications
        "zyrtec": "cetirizine",
        "allegra": "fexofenadine",
        "claritin": "loratadine",
        "benadryl": "diphenhydramine",
        "chlor-trimeton": "chlorpheniramine",
        # Cough and cold
        "robitussin": "dextromethorphan",
        "mucinex": "guaifenesin",
        "sudafed": "pseudoephedrine",
        "afrin": "oxymetazoline",
        # Stomach medications
        "pepcid": "famotidine",
        "prevacid": "lansoprazole",
        "pepto-bismol": "bismuth_subsalicylate",
        "mylanta": "aluminum_hydroxide",
        "tums": "calcium_carbonate",
        "rolaids": "magnesium_hydroxide",
        "gas-x": "simethicone",
        "immodium": "loperamide",
        "dulcolax": "bisacodyl",
        "colace": "docusate",
        "miralax": "polyethylene_glycol",
        # Pain and fever
        "excedrin": "acetaminophen",
        "midol": "ibuprofen",
        # Topical medications
        "neosporin": "neomycin",
        "bacitracin": "bacitracin",
        "cortaid": "hydrocortisone",
        "monistat": "miconazole",
        "lotrimin": "clotrimazole",
        "lamisil": "terbinafine",
        "nizoral": "ketoconazole",
        "desitin": "zinc_oxide",
        "caladryl": "calamine",
        "orajel": "benzocaine",
        "aspercreme": "trolamine",
        "bengay": "menthol",
        "vicks": "camphor",
        "icy_hot": "menthol",
        # Sleep aids
        "unisom": "doxylamine",
        "simply_sleep": "diphenhydramine",
        "ambien": "zolpidem",
        "lunesta": "eszopiclone",
        # Motion sickness
        "dramamine": "dimenhydrinate",
        "bonine": "meclizine",
        "antivert": "meclizine",
        # Prescription brands
        "diovan": "valsartan",
        "avapro": "irbesartan",
        "micardis": "telmisartan",
        "atacand": "candesartan",
        "pravachol": "pravastatin",
        "livalo": "pitavastatin",
        "tricor": "fenofibrate",
        "zetia": "ezetimibe",
        "plavix": "clopidogrel",
        "effient": "prasugrel",
        "eliquis": "apixaban",
        "xarelto": "rivaroxaban",
        "pradaxa": "dabigatran",
        # Antidepressants
        "wellbutrin": "bupropion",
        "cymbalta": "duloxetine",
        "effexor": "venlafaxine",
        "pristiq": "desvenlafaxine",
        "remeron": "mirtazapine",
        "trazodone": "trazodone",
        # Seizure medications
        "tegretol": "carbamazepine",
        "dilantin": "phenytoin",
        "lamictal": "lamotrigine",
        "topamax": "topiramate",
        "keppra": "levetiracetam",
        # Migraine medications
        "imitrex": "sumatriptan",
        "maxalt": "rizatriptan",
        "zomig": "zolmitriptan",
        "relpax": "eletriptan",
        "treximet": "sumatriptan",
        # Muscle relaxants
        "flexeril": "cyclobenzaprine",
        "zanaflex": "tizanidine",
        "soma": "carisoprodol",
        "robaxin": "methocarbamol",
        "skelaxin": "metaxalone",
        # Anti-inflammatory
        "celebrex": "celecoxib",
        "mobic": "meloxicam",
        "voltaren": "diclofenac",
        "indocin": "indomethacin",
        "toradol": "ketorolac",
    }

    # Common misspellings
    MISSPELLING_CORRECTIONS = {
        "ibuprofin": "ibuprofen",
        "ibuprophen": "ibuprofen",
        "ibrufen": "ibuprofen",  # Very common misspelling
        "ibrufin": "ibuprofen",
        "ibropen": "ibuprofen",
        "acetominophen": "acetaminophen",
        "acetamenophen": "acetaminophen",
        "acetominofen": "acetaminophen",
        "paracetomol": "paracetamol",
        "atorvistatin": "atorvastatin",
        "metforman": "metformin",
        "amoxicilin": "amoxicillin",
        "amoxycillin": "amoxicillin",
        "lisinipril": "lisinopril",
        "gabapenten": "gabapentin",
        "omeprozole": "omeprazole",
        "prednezone": "prednisone",
        "albedazole": "albendazole",  # User typed this correctly, but we need mapping
        "albendazol": "albendazole",
    }

    # Patterns for cleaning drug names
    DOSAGE_PATTERN = re.compile(r"\d+\s*(mg|ml|mcg|g|iu|units?)\b", re.IGNORECASE)
    FORM_PATTERN = re.compile(
        r"\s+(tablets?|capsules?|pills?|solution|syrup|cream|gel|injection|patch)\b",
        re.IGNORECASE,
    )
    PARENTHETICAL_PATTERN = re.compile(r"\([^)]*\)")
    SPECIAL_CHARS_PATTERN = re.compile(r"[^a-z\s]")

    def __init__(self, dictionary_path: Optional[Path] = None):
        """
        Initialize the normalizer.

        Args:
            dictionary_path: Path to drug_dictionary.json. If None, uses bootstrap data.
        """
        self.alias_index: dict[str, str] = {}
        self.drug_info: dict[str, dict] = {}

        # Load bootstrap mappings
        self._load_bootstrap_mappings()

        # Load full dictionary if available
        if dictionary_path and dictionary_path.exists():
            self._load_dictionary(dictionary_path)
        else:
            # Try default location
            default_path = Path(settings.DATA_PROCESSED_PATH) / "drug_dictionary.json"
            if default_path.exists():
                self._load_dictionary(default_path)

    def _load_bootstrap_mappings(self):
        """Load hardcoded brand-generic mappings."""
        # Add misspelling corrections first (they map to generic)
        for misspelling, correct in self.MISSPELLING_CORRECTIONS.items():
            self.alias_index[misspelling] = correct

        # Add brand-to-generic mappings
        for brand, generic in self.BOOTSTRAP_MAPPINGS.items():
            self.alias_index[brand] = generic
            # Also add generic as self-mapping
            self.alias_index[generic] = generic

    def _load_dictionary(self, path: Path):
        """Load drug dictionary from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        # Load drugs and aliases
        for canonical, info in data.get("drugs", {}).items():
            self.drug_info[canonical] = info
            self.alias_index[canonical] = canonical

            for alias_entry in info.get("aliases", []):
                if isinstance(alias_entry, dict):
                    alias_name = alias_entry.get("name", "").lower().strip()
                else:
                    alias_name = str(alias_entry).lower().strip()

                if alias_name:
                    self.alias_index[alias_name] = canonical

        # Load pre-built alias index if available
        if "alias_index" in data:
            for alias, canonical in data["alias_index"].items():
                if alias not in self.alias_index:
                    self.alias_index[alias] = canonical

    def preprocess(self, raw_input: str) -> str:
        """
        Clean and normalize user input for matching.

        Args:
            raw_input: Raw drug name from user

        Returns:
            Cleaned, lowercase drug name
        """
        if not raw_input:
            return ""

        name = raw_input.strip().lower()

        # Remove dosage patterns (e.g., "500mg", "20 mg")
        name = self.DOSAGE_PATTERN.sub("", name)

        # Remove form suffixes (tablets, capsules, etc.)
        name = self.FORM_PATTERN.sub("", name)

        # Remove parenthetical content
        name = self.PARENTHETICAL_PATTERN.sub("", name)

        # Replace separators with space
        name = re.sub(r"[/\\,;]", " ", name)

        # Remove special characters, keep only letters and spaces
        name = self.SPECIAL_CHARS_PATTERN.sub("", name)

        # Normalize whitespace
        name = " ".join(name.split())

        return name.strip()

    def exact_match(self, normalized_name: str) -> Optional[str]:
        """Try exact lookup in alias index."""
        return self.alias_index.get(normalized_name)

    def fuzzy_match(
        self,
        normalized_name: str,
        threshold: float = 85.0,
        max_results: int = 3,
    ) -> list[tuple[str, float]]:
        """
        Fuzzy matching for typos and minor variations.

        Returns list of (canonical_name, confidence_score) tuples.
        """
        if not self.alias_index:
            return []

        all_aliases = list(self.alias_index.keys())

        matches = process.extract(
            normalized_name,
            all_aliases,
            scorer=fuzz.WRatio,
            limit=max_results * 2,
        )

        results = []
        seen_canonical = set()

        for alias, score, _ in matches:
            if score >= threshold:
                canonical = self.alias_index[alias]
                if canonical not in seen_canonical:
                    seen_canonical.add(canonical)
                    results.append((canonical, score))
                    if len(results) >= max_results:
                        break

        return results

    def normalize(
        self,
        user_input: str,
        fuzzy_threshold: float = 85.0,
    ) -> NormalizationResult:
        """
        Main normalization entry point.

        Args:
            user_input: Drug name from user (any form)
            fuzzy_threshold: Minimum score for fuzzy matches (0-100)

        Returns:
            NormalizationResult with canonical name and confidence
        """
        original = user_input
        normalized = self.preprocess(user_input)

        if not normalized:
            return NormalizationResult(
                canonical_name=None,
                confidence=0.0,
                match_type="none",
                original_input=original,
            )

        # Try exact match first
        exact = self.exact_match(normalized)
        if exact:
            return NormalizationResult(
                canonical_name=exact,
                confidence=1.0,
                match_type="exact",
                original_input=original,
            )

        # Try fuzzy match
        fuzzy_results = self.fuzzy_match(normalized, fuzzy_threshold)

        if fuzzy_results:
            best_match, best_score = fuzzy_results[0]
            return NormalizationResult(
                canonical_name=best_match,
                confidence=best_score / 100.0,
                match_type="fuzzy",
                original_input=original,
                suggestions=fuzzy_results[1:] if len(fuzzy_results) > 1 else None,
            )

        # No match found
        return NormalizationResult(
            canonical_name=None,
            confidence=0.0,
            match_type="none",
            original_input=original,
        )

    def normalize_list(self, drug_names: list[str]) -> list[NormalizationResult]:
        """Normalize a list of drug names."""
        return [self.normalize(name) for name in drug_names]

    def add_mapping(self, alias: str, canonical: str):
        """Add a new alias mapping dynamically."""
        normalized_alias = self.preprocess(alias)
        if normalized_alias:
            self.alias_index[normalized_alias] = canonical.lower().strip()

    def get_all_aliases(self, canonical: str) -> list[str]:
        """Get all known aliases for a canonical drug name."""
        canonical = canonical.lower().strip()
        return [alias for alias, canon in self.alias_index.items() if canon == canonical]


# Global singleton instance
_normalizer: Optional[DrugNormalizer] = None


def get_normalizer() -> DrugNormalizer:
    """Get the global DrugNormalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = DrugNormalizer()
    return _normalizer


@lru_cache(maxsize=10000)
def normalize_drug_name(name: str) -> NormalizationResult:
    """
    Convenience function for normalizing a single drug name.

    Results are cached for performance.
    """
    return get_normalizer().normalize(name)
