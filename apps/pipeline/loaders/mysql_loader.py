import logging
from typing import Optional

from django.db import transaction
from tqdm import tqdm

from apps.data_access.models import (
    Drug,
    DrugAlias,
    Indication,
    DrugIndication,
    AdverseReaction,
    DrugAdverseReaction,
    DrugInteraction,
    Contraindication,
    AdverseEventReport,
    EventReportDrug,
    EventReportReaction,
)
from apps.pipeline.processing import (
    DataUnifier,
    UnifiedDrug,
    UnifiedAdverseReaction,
    UnifiedInteraction,
    UnifiedEventReport,
    get_normalizer,
)

logger = logging.getLogger(__name__)


class MySQLLoader:
    """
    Loads unified data into MySQL via Django ORM.
    """

    def __init__(self, batch_size: int = 1000):
        self.batch_size = batch_size
        self.normalizer = get_normalizer()
        self.unifier = DataUnifier()

        # Caches for fast lookups
        self._drug_cache: dict[str, Drug] = {}
        self._reaction_cache: dict[str, AdverseReaction] = {}

    def clear_caches(self):
        """Clear in-memory caches."""
        self._drug_cache.clear()
        self._reaction_cache.clear()

    def get_or_create_drug(self, canonical_name: str, **defaults) -> tuple[Drug, bool]:
        """Get or create a drug with caching."""
        canonical_name = canonical_name.lower().strip()

        if canonical_name in self._drug_cache:
            return self._drug_cache[canonical_name], False

        drug, created = Drug.objects.get_or_create(
            canonical_name=canonical_name,
            defaults=defaults,
        )
        self._drug_cache[canonical_name] = drug
        return drug, created

    def get_or_create_reaction(self, preferred_term: str, **defaults) -> tuple[AdverseReaction, bool]:
        """Get or create an adverse reaction with caching."""
        preferred_term_normalized = preferred_term.lower().strip()

        if preferred_term_normalized in self._reaction_cache:
            return self._reaction_cache[preferred_term_normalized], False

        reaction, created = AdverseReaction.objects.get_or_create(
            preferred_term_normalized=preferred_term_normalized,
            defaults={
                "preferred_term": preferred_term,
                **defaults,
            },
        )
        self._reaction_cache[preferred_term_normalized] = reaction
        return reaction, created

    def load_drugs_from_labels(self, show_progress: bool = True) -> dict:

        stats = {"drugs_created": 0, "aliases_created": 0, "errors": 0}

        logger.info("Loading drugs from OpenFDA labels...")

        labels = list(self.unifier.iter_openfda_labels())
        iterator = tqdm(labels, desc="Processing labels") if show_progress else labels

        for label in iterator:
            try:
                unified_drugs = self.unifier.extract_drugs_from_label(label)

                for ud in unified_drugs:
                    drug, created = self.get_or_create_drug(
                        ud.canonical_name,
                        rxcui=ud.rxcui,
                        pubchem_cid=ud.pubchem_cid,
                        is_combination=ud.is_combination,
                    )

                    if created:
                        stats["drugs_created"] += 1

                    # Create aliases
                    for alias_info in ud.aliases:
                        alias_name = alias_info.get("name", "")
                        alias_type = alias_info.get("type", "generic")
                        alias_normalized = alias_name.lower().strip()

                        if alias_normalized and alias_normalized != drug.canonical_name:
                            _, alias_created = DrugAlias.objects.get_or_create(
                                drug=drug,
                                alias_normalized=alias_normalized,
                                defaults={
                                    "alias": alias_name,
                                    "alias_type": alias_type,
                                },
                            )
                            if alias_created:
                                stats["aliases_created"] += 1

            except Exception as e:
                logger.error(f"Error processing label: {e}")
                stats["errors"] += 1

        logger.info(f"Drugs loaded: {stats}")
        return stats

    def load_drugs_from_sider(self, show_progress: bool = True) -> dict:
        """Load drugs from SIDER dataset."""
        stats = {"drugs_created": 0, "errors": 0}

        logger.info("Loading drugs from SIDER...")

        records = list(self.unifier.iter_sider_data())
        iterator = tqdm(records, desc="Processing SIDER") if show_progress else records

        seen_drugs = set()
        for record in iterator:
            try:
                drug_name = record.get("drugname", "").lower().strip()
                if not drug_name or drug_name in seen_drugs:
                    continue

                seen_drugs.add(drug_name)

                # Normalize
                result = self.normalizer.normalize(drug_name)
                canonical = result.canonical_name or drug_name

                drug, created = self.get_or_create_drug(
                    canonical,
                    pubchem_cid=record.get("drug_id"),
                )

                if created:
                    stats["drugs_created"] += 1

                # Add original name as alias if different
                if drug_name != canonical:
                    DrugAlias.objects.get_or_create(
                        drug=drug,
                        alias_normalized=drug_name,
                        defaults={
                            "alias": drug_name,
                            "alias_type": "generic",
                        },
                    )

            except Exception as e:
                logger.error(f"Error processing SIDER record: {e}")
                stats["errors"] += 1

        logger.info(f"SIDER drugs loaded: {stats}")
        return stats

    def load_adverse_reactions_from_labels(self, show_progress: bool = True) -> dict:
        """Load adverse reactions from drug labels."""
        stats = {"reactions_created": 0, "links_created": 0, "errors": 0}

        logger.info("Loading adverse reactions from labels...")

        labels = list(self.unifier.iter_openfda_labels())
        iterator = tqdm(labels, desc="Extracting reactions") if show_progress else labels

        for label in iterator:
            try:
                reactions = self.unifier.extract_adverse_reactions_from_label(label)

                for ur in reactions:
                    drug, _ = self.get_or_create_drug(ur.drug_canonical)
                    reaction, created = self.get_or_create_reaction(ur.preferred_term)

                    if created:
                        stats["reactions_created"] += 1

                    # Create link
                    _, link_created = DrugAdverseReaction.objects.get_or_create(
                        drug=drug,
                        reaction=reaction,
                        source="fda_label",
                        defaults={
                            "source_text": ur.source_text,
                        },
                    )
                    if link_created:
                        stats["links_created"] += 1

            except Exception as e:
                logger.error(f"Error processing label reactions: {e}")
                stats["errors"] += 1

        logger.info(f"Adverse reactions loaded: {stats}")
        return stats

    def load_adverse_reactions_from_sider(self, show_progress: bool = True) -> dict:
        """Load adverse reactions from SIDER dataset."""
        stats = {"reactions_created": 0, "links_created": 0, "errors": 0}

        logger.info("Loading adverse reactions from SIDER...")

        records = list(self.unifier.iter_sider_data())
        iterator = tqdm(records, desc="Processing SIDER reactions") if show_progress else records

        for record in iterator:
            try:
                unified = self.unifier.unify_sider_record(record)
                if not unified:
                    continue

                drug, _ = self.get_or_create_drug(unified.drug_canonical)
                reaction, created = self.get_or_create_reaction(unified.preferred_term)

                if created:
                    stats["reactions_created"] += 1

                # Create link
                _, link_created = DrugAdverseReaction.objects.get_or_create(
                    drug=drug,
                    reaction=reaction,
                    source="sider",
                )
                if link_created:
                    stats["links_created"] += 1

            except Exception as e:
                logger.error(f"Error processing SIDER record: {e}")
                stats["errors"] += 1

        logger.info(f"SIDER reactions loaded: {stats}")
        return stats

    def load_interactions_from_labels(self, show_progress: bool = True) -> dict:
        """Load drug interactions from labels."""
        stats = {"interactions_created": 0, "errors": 0}

        logger.info("Loading interactions from labels...")

        labels = list(self.unifier.iter_openfda_labels())
        iterator = tqdm(labels, desc="Extracting interactions") if show_progress else labels

        for label in iterator:
            try:
                interactions = self.unifier.extract_interactions_from_label(label)

                for ui in interactions:
                    drug_a, _ = self.get_or_create_drug(ui.drug_a)
                    drug_b, _ = self.get_or_create_drug(ui.drug_b)

                    # Normalize order (smaller ID first)
                    if drug_a.id > drug_b.id:
                        drug_a, drug_b = drug_b, drug_a

                    _, created = DrugInteraction.objects.get_or_create(
                        drug_a=drug_a,
                        drug_b=drug_b,
                        defaults={
                            "description": ui.description,
                            "severity": ui.severity,
                            "clinical_effect": ui.clinical_effect,
                            "management": ui.management,
                            "source": ui.source,
                            "source_label_id": ui.source_label_id,
                        },
                    )

                    if created:
                        stats["interactions_created"] += 1

            except Exception as e:
                logger.error(f"Error processing label interactions: {e}")
                stats["errors"] += 1

        logger.info(f"Interactions loaded: {stats}")
        return stats

    def load_event_reports(self, source: str = "openfda", show_progress: bool = True) -> dict:

        stats = {"reports_created": 0, "drugs_linked": 0, "reactions_linked": 0, "errors": 0}

        logger.info(f"Loading event reports from {source}...")

        if source == "openfda":
            records = self.unifier.iter_openfda_events()
            unify_func = self.unifier.unify_openfda_event
        else:
            records = self.unifier.iter_fda_csv_events()
            unify_func = self.unifier.unify_fda_csv_event

        records_list = list(records)
        iterator = tqdm(records_list, desc=f"Loading {source} events") if show_progress else records_list

        for record in iterator:
            try:
                unified = unify_func(record)
                if not unified:
                    continue

                # Check for duplicate
                if AdverseEventReport.objects.filter(safety_report_id=unified.safety_report_id).exists():
                    continue

                # Create report
                report = AdverseEventReport.objects.create(
                    safety_report_id=unified.safety_report_id,
                    is_serious=unified.is_serious,
                    seriousness_death=unified.seriousness_death,
                    seriousness_hospitalization=unified.seriousness_hospitalization,
                    patient_age=unified.patient_age,
                    patient_sex=unified.patient_sex,
                    source=unified.source,
                    source_file=unified.source_file,
                )
                stats["reports_created"] += 1

                # Link drugs
                for drug_info in unified.drugs:
                    drug_name = drug_info.get("name", "")
                    if not drug_name:
                        continue

                    # Normalize drug name
                    result = self.normalizer.normalize(drug_name)
                    canonical = result.canonical_name or drug_name.lower().strip()

                    drug, _ = self.get_or_create_drug(canonical)

                    EventReportDrug.objects.create(
                        report=report,
                        drug=drug,
                        characterization=drug_info.get("characterization", "suspect"),
                        dosage=drug_info.get("dosage"),
                        indication=drug_info.get("indication"),
                        drug_name_raw=drug_name,
                    )
                    stats["drugs_linked"] += 1

                # Link reactions
                for reaction_info in unified.reactions:
                    reaction_name = reaction_info.get("name", "")
                    if not reaction_name:
                        continue

                    reaction, _ = self.get_or_create_reaction(reaction_name)

                    EventReportReaction.objects.create(
                        report=report,
                        reaction=reaction,
                        outcome=reaction_info.get("outcome"),
                        reaction_name_raw=reaction_name,
                    )
                    stats["reactions_linked"] += 1

            except Exception as e:
                logger.error(f"Error processing event report: {e}")
                stats["errors"] += 1

        logger.info(f"Event reports loaded: {stats}")
        return stats

    @transaction.atomic
    def load_all(self, show_progress: bool = True) -> dict:

        all_stats = {}

        # 1. Load drugs first 
        all_stats["drugs_from_labels"] = self.load_drugs_from_labels(show_progress)
        all_stats["drugs_from_sider"] = self.load_drugs_from_sider(show_progress)

        # 2. Load adverse reactions
        all_stats["reactions_from_labels"] = self.load_adverse_reactions_from_labels(show_progress)
        all_stats["reactions_from_sider"] = self.load_adverse_reactions_from_sider(show_progress)

        # 3. Load interactions
        all_stats["interactions"] = self.load_interactions_from_labels(show_progress)

        # 4. Load event reports
        all_stats["events_openfda"] = self.load_event_reports("openfda", show_progress)
        all_stats["events_fda_csv"] = self.load_event_reports("fda_csv", show_progress)

        return all_stats
