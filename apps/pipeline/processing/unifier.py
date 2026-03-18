"""
Data Unifier - Merge data from multiple source files into unified format.
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from django.conf import settings

from .cleaner import DataCleaner, get_cleaner
from .normalizer import DrugNormalizer, get_normalizer

logger = logging.getLogger(__name__)


@dataclass
class UnifiedDrug:
    """Unified drug record from all sources."""

    canonical_name: str
    aliases: list[dict] = field(default_factory=list)  # [{"name": ..., "type": ...}]
    rxcui: Optional[str] = None
    pubchem_cid: Optional[str] = None
    is_combination: bool = False
    sources: list[str] = field(default_factory=list)


@dataclass
class UnifiedIndication:
    """Unified indication record."""

    name: str
    drug_canonical: str
    source: str
    source_text: Optional[str] = None


@dataclass
class UnifiedAdverseReaction:
    """Unified adverse reaction record."""

    preferred_term: str
    drug_canonical: str
    source: str
    meddra_code: Optional[str] = None
    frequency: Optional[str] = None
    source_text: Optional[str] = None


@dataclass
class UnifiedInteraction:
    """Unified drug interaction record."""

    drug_a: str
    drug_b: str
    description: str
    severity: str = "unknown"
    clinical_effect: Optional[str] = None
    management: Optional[str] = None
    source: str = "fda_label"
    source_label_id: Optional[str] = None


@dataclass
class UnifiedEventReport:
    """Unified adverse event report."""

    safety_report_id: str
    drugs: list[dict] = field(default_factory=list)  # [{"name": ..., "characterization": ...}]
    reactions: list[dict] = field(default_factory=list)  # [{"name": ..., "outcome": ...}]
    is_serious: bool = False
    seriousness_death: bool = False
    seriousness_hospitalization: bool = False
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    report_date: Optional[str] = None
    source: str = "openfda_events"
    source_file: Optional[str] = None


class DataUnifier:
    """
    Unifies data from multiple sources into a consistent format.
    """

    def __init__(
        self,
        normalizer: Optional[DrugNormalizer] = None,
        cleaner: Optional[DataCleaner] = None,
    ):
        self.normalizer = normalizer or get_normalizer()
        self.cleaner = cleaner or get_cleaner()
        self.data_path = Path(settings.DATA_RAW_PATH)

    def iter_openfda_labels(self) -> Iterator[dict]:
        """Iterate over OpenFDA drug label records."""
        label_path = self.data_path / "drug-label"

        if not label_path.exists():
            logger.warning(f"Drug label path not found: {label_path}")
            return

        for json_file in sorted(label_path.glob("*.json")):
            logger.info(f"Processing label file: {json_file.name}")
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                for result in data.get("results", []):
                    yield result
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error reading {json_file}: {e}")

    def iter_openfda_events(self) -> Iterator[dict]:
        """Iterate over OpenFDA drug event records."""
        event_path = self.data_path / "drug-events"

        if not event_path.exists():
            logger.warning(f"Drug events path not found: {event_path}")
            return

        for json_file in sorted(event_path.glob("*.json")):
            logger.info(f"Processing event file: {json_file.name}")
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                for result in data.get("results", []):
                    result["_source_file"] = json_file.name
                    yield result
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error reading {json_file}: {e}")

    def iter_sider_data(self) -> Iterator[dict]:
        """Iterate over SIDER dataset records."""
        sider_path = self.data_path / "SIDER_DATASET_KAGGLE" / "drug_df.csv"

        if not sider_path.exists():
            logger.warning(f"SIDER file not found: {sider_path}")
            return

        try:
            with open(sider_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row
        except OSError as e:
            logger.error(f"Error reading SIDER data: {e}")

    def iter_fda_csv_events(self) -> Iterator[dict]:
        """Iterate over FDA CSV adverse event records."""
        csv_path = self.data_path / "FDA Drug Adverse Event Reports" / "FDA_Drug_Adverse_Events.csv"

        if not csv_path.exists():
            logger.warning(f"FDA CSV not found: {csv_path}")
            return

        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row
        except OSError as e:
            logger.error(f"Error reading FDA CSV: {e}")

    def iter_adr_synthetic_data(self, limit: Optional[int] = None) -> Iterator[dict]:
        """Iterate over ADR synthetic data records."""
        adr_path = self.data_path / "Adverse Drug Reaction (ADR) Reporting" / "synthetic_drug_data.csv"

        if not adr_path.exists():
            logger.warning(f"ADR synthetic data not found: {adr_path}")
            return

        try:
            with open(adr_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if limit and i >= limit:
                        break
                    yield row
        except OSError as e:
            logger.error(f"Error reading ADR synthetic data: {e}")

    def extract_drugs_from_label(self, label: dict) -> list[UnifiedDrug]:
        """Extract drug information from a drug label."""
        drugs = []
        openfda = label.get("openfda", {})

        brand_names = openfda.get("brand_name", [])
        generic_names = openfda.get("generic_name", [])
        substance_names = openfda.get("substance_name", [])
        rxcui_list = openfda.get("rxcui", [])

        if not generic_names and not brand_names:
            return []

        # Use first generic as canonical, fallback to brand
        canonical = None
        if generic_names:
            canonical = self.cleaner.clean_string(generic_names[0])
        elif brand_names:
            # Try to normalize brand to generic
            result = self.normalizer.normalize(brand_names[0])
            canonical = result.canonical_name or self.cleaner.clean_string(brand_names[0])

        if not canonical:
            return []

        # Build aliases list
        aliases = []
        for name in brand_names:
            clean_name = self.cleaner.clean_string(name, lowercase=False)
            if clean_name:
                aliases.append({"name": clean_name, "type": "brand"})

        for name in generic_names:
            clean_name = self.cleaner.clean_string(name, lowercase=False)
            if clean_name and clean_name.lower() != canonical:
                aliases.append({"name": clean_name, "type": "generic"})

        for name in substance_names:
            clean_name = self.cleaner.clean_string(name, lowercase=False)
            if clean_name:
                aliases.append({"name": clean_name, "type": "substance"})

        # Check if combination
        is_combination = " and " in canonical or "/" in canonical

        drugs.append(
            UnifiedDrug(
                canonical_name=canonical,
                aliases=aliases,
                rxcui=rxcui_list[0] if rxcui_list else None,
                is_combination=is_combination,
                sources=["fda_label"],
            )
        )

        return drugs

    def extract_interactions_from_label(self, label: dict) -> list[UnifiedInteraction]:
        """Extract drug interactions from a drug label."""
        interactions = []

        interaction_text = label.get("drug_interactions", [""])[0]
        if not interaction_text:
            return []

        # Get primary drug
        openfda = label.get("openfda", {})
        generic_names = openfda.get("generic_name", [])
        brand_names = openfda.get("brand_name", [])

        primary_drug = None
        if generic_names:
            primary_drug = self.cleaner.clean_string(generic_names[0])
        elif brand_names:
            result = self.normalizer.normalize(brand_names[0])
            primary_drug = result.canonical_name

        if not primary_drug:
            return []

        # Extract mentioned drugs from interaction text
        # This is a simplified extraction - would need NLP for full accuracy
        text_lower = interaction_text.lower()

        # Look for common drug classes and specific drugs
        drug_patterns = [
            ("warfarin", "warfarin"),
            ("aspirin", "aspirin"),
            ("nsaid", "ibuprofen"),  # Represents NSAID class
            ("ace inhibitor", "lisinopril"),  # Represents ACE inhibitor class
            ("lithium", "lithium"),
            ("digoxin", "digoxin"),
            ("methotrexate", "methotrexate"),
            ("cyclosporin", "cyclosporine"),
        ]

        # Severity keywords
        severity_keywords = {
            "contraindicated": "contraindicated",
            "do not use": "contraindicated",
            "avoid": "major",
            "serious": "major",
            "significant": "moderate",
            "caution": "moderate",
            "minor": "minor",
        }

        for pattern, drug_name in drug_patterns:
            if pattern in text_lower and drug_name != primary_drug:
                # Determine severity
                severity = "unknown"
                for keyword, sev in severity_keywords.items():
                    if keyword in text_lower:
                        severity = sev
                        break

                interactions.append(
                    UnifiedInteraction(
                        drug_a=primary_drug,
                        drug_b=drug_name,
                        description=interaction_text[:2000],  # Limit length
                        severity=severity,
                        source="fda_label",
                        source_label_id=label.get("id"),
                    )
                )

        return interactions

    def extract_adverse_reactions_from_label(self, label: dict) -> list[UnifiedAdverseReaction]:
        """Extract adverse reactions from a drug label."""
        reactions = []

        reaction_text = label.get("adverse_reactions", [""])[0]
        if not reaction_text:
            return []

        # Get primary drug
        openfda = label.get("openfda", {})
        generic_names = openfda.get("generic_name", [])
        brand_names = openfda.get("brand_name", [])

        primary_drug = None
        if generic_names:
            primary_drug = self.cleaner.clean_string(generic_names[0])
        elif brand_names:
            result = self.normalizer.normalize(brand_names[0])
            primary_drug = result.canonical_name

        if not primary_drug:
            return []

        # Common adverse reactions to look for
        common_reactions = [
            "headache", "nausea", "dizziness", "fatigue", "diarrhea",
            "vomiting", "rash", "constipation", "insomnia", "drowsiness",
            "abdominal pain", "back pain", "cough", "dyspnea", "edema",
            "hypertension", "hypotension", "anxiety", "depression",
        ]

        text_lower = reaction_text.lower()

        for reaction in common_reactions:
            if reaction in text_lower:
                reactions.append(
                    UnifiedAdverseReaction(
                        preferred_term=reaction,
                        drug_canonical=primary_drug,
                        source="fda_label",
                        source_text=reaction_text[:500],
                    )
                )

        return reactions

    def unify_sider_record(self, record: dict) -> Optional[UnifiedAdverseReaction]:
        """Convert SIDER record to unified format."""
        drug_name = self.cleaner.clean_string(record.get("drugname"))
        reaction = self.cleaner.clean_reaction_name(record.get("pt"))

        if not drug_name or not reaction:
            return None

        # Normalize drug name
        result = self.normalizer.normalize(drug_name)
        canonical = result.canonical_name or drug_name

        return UnifiedAdverseReaction(
            preferred_term=reaction,
            drug_canonical=canonical,
            source="sider",
            meddra_code=None,  # SIDER has different ID format
        )

    def unify_openfda_event(self, record: dict) -> Optional[UnifiedEventReport]:
        """Convert OpenFDA event record to unified format."""
        safety_id = record.get("safetyreportid")
        if not safety_id:
            return None

        patient = record.get("patient", {})

        # Extract drugs
        drugs = []
        for drug_entry in patient.get("drug", []):
            drug_name = drug_entry.get("medicinalproduct")
            if drug_name:
                char = drug_entry.get("drugcharacterization", "1")
                char_map = {"1": "suspect", "2": "concomitant", "3": "interacting"}
                drugs.append({
                    "name": drug_name,
                    "characterization": char_map.get(char, "suspect"),
                    "dosage": drug_entry.get("drugdosagetext"),
                    "indication": drug_entry.get("drugindication"),
                })

        # Extract reactions
        reactions = []
        for reaction_entry in patient.get("reaction", []):
            reaction_name = reaction_entry.get("reactionmeddrapt")
            if reaction_name:
                outcome = reaction_entry.get("reactionoutcome")
                outcome_map = {"1": "recovered", "2": "recovering", "3": "not_recovered", "4": "fatal", "5": "unknown"}
                reactions.append({
                    "name": reaction_name,
                    "outcome": outcome_map.get(outcome, "unknown"),
                })

        if not drugs and not reactions:
            return None

        return UnifiedEventReport(
            safety_report_id=safety_id,
            drugs=drugs,
            reactions=reactions,
            is_serious=record.get("serious") == "1",
            seriousness_death=record.get("seriousnessdeath") == "1",
            seriousness_hospitalization=record.get("seriousnesshospitalization") == "1",
            patient_age=self.cleaner.clean_integer(patient.get("patientonsetage")),
            patient_sex={"1": "M", "2": "F"}.get(patient.get("patientsex")),
            report_date=record.get("receiptdate"),
            source="openfda_events",
            source_file=record.get("_source_file"),
        )

    def unify_fda_csv_event(self, record: dict) -> Optional[UnifiedEventReport]:
        """Convert FDA CSV event record to unified format."""
        # Generate a unique ID from the record
        report_date = record.get("report_date", "")
        drugs_str = record.get("drugs", "")
        reactions_str = record.get("reactions", "")

        safety_id = f"FDA_CSV_{report_date}_{hash(drugs_str + reactions_str)}"

        # Parse drugs (semicolon separated)
        drugs = []
        for drug_name in self.cleaner.clean_list_string(drugs_str, ";"):
            drugs.append({"name": drug_name, "characterization": "suspect"})

        # Parse reactions (semicolon separated)
        reactions = []
        for reaction_name in self.cleaner.clean_list_string(reactions_str, ";"):
            reactions.append({"name": reaction_name, "outcome": "unknown"})

        if not drugs and not reactions:
            return None

        # Parse sex (1=Male, 2=Female)
        sex_val = record.get("sex")
        sex = {"1": "M", "2": "F"}.get(sex_val)

        return UnifiedEventReport(
            safety_report_id=safety_id,
            drugs=drugs,
            reactions=reactions,
            is_serious=record.get("serious") == "1",
            patient_age=self.cleaner.clean_integer(record.get("age")),
            patient_sex=sex,
            report_date=report_date,
            source="fda_csv",
        )
