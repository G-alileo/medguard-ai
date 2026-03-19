"""
Management command to migrate hardcoded data to MySQL database.

This command migrates:
1. Treatments (KNOWN_TREATMENTS) -> Drug + Indication + DrugIndication tables
2. Side Effects (KNOWN_SIDE_EFFECTS) -> Drug + AdverseReaction + DrugAdverseReaction tables
3. Alternatives -> Drug + DrugAlternative tables

Usage:
    python manage.py migrate_hardcoded_data
    python manage.py migrate_hardcoded_data --treatments-only
    python manage.py migrate_hardcoded_data --side-effects-only
    python manage.py migrate_hardcoded_data --alternatives-only
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.data_access.models import (
    Drug,
    Indication,
    DrugIndication,
    AdverseReaction,
    DrugAdverseReaction,
    DrugAlternative,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migrate hardcoded drug data to MySQL database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--treatments-only",
            action="store_true",
            help="Only migrate treatments data",
        )
        parser.add_argument(
            "--side-effects-only",
            action="store_true",
            help="Only migrate side effects data",
        )
        parser.add_argument(
            "--alternatives-only",
            action="store_true",
            help="Only migrate alternatives data",
        )

    def handle(self, *args, **options):
        treatments_only = options.get("treatments_only", False)
        side_effects_only = options.get("side_effects_only", False)
        alternatives_only = options.get("alternatives_only", False)

        migrate_all = not (treatments_only or side_effects_only or alternatives_only)

        self.stdout.write("=" * 60)
        self.stdout.write("MIGRATING HARDCODED DATA TO MYSQL")
        self.stdout.write("=" * 60)

        try:
            if migrate_all or treatments_only:
                self._migrate_treatments()

            if migrate_all or side_effects_only:
                self._migrate_side_effects()

            if migrate_all or alternatives_only:
                self._migrate_alternatives()

            self.stdout.write(self.style.SUCCESS("\n Migration completed successfully!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n Migration failed: {e}"))
            logger.exception("Migration failed")
            raise

    @transaction.atomic
    def _migrate_treatments(self):
        """Migrate KNOWN_TREATMENTS to Drug + Indication + DrugIndication."""
        self.stdout.write("\n[1/3] Migrating Treatments...")

        from medguard_app.services.treatment_validator import TreatmentValidator

        validator = TreatmentValidator()
        known_treatments = validator.KNOWN_TREATMENTS

        drugs_created = 0
        indications_created = 0
        links_created = 0

        for drug_name, symptoms in known_treatments.items():
            drug, created = Drug.objects.get_or_create(
                canonical_name=drug_name.lower(),
                defaults={"is_combination": False}
            )
            if created:
                drugs_created += 1

            for symptom in symptoms:
                indication, created = Indication.objects.get_or_create(
                    name=symptom,
                    defaults={
                        "name_normalized": symptom.lower(),
                        "description": f"Symptom/condition: {symptom}"
                    }
                )
                if created:
                    indications_created += 1

                link, created = DrugIndication.objects.get_or_create(
                    drug=drug,
                    indication=indication,
                    source="synthetic",
                    defaults={
                        "confidence": 0.9,
                        "source_text": f"Migrated from hardcoded KNOWN_TREATMENTS"
                    }
                )
                if created:
                    links_created += 1

        self.stdout.write(
            f"   Created {drugs_created} drugs, {indications_created} indications, "
            f"{links_created} drug-indication links"
        )

    @transaction.atomic
    def _migrate_side_effects(self):
        """Migrate KNOWN_SIDE_EFFECTS to Drug + AdverseReaction + DrugAdverseReaction."""
        self.stdout.write("\n[2/3] Migrating Side Effects...")

        from medguard_app.services.side_effect_analyzer import SideEffectAnalyzer

        analyzer = SideEffectAnalyzer()
        known_side_effects = analyzer.KNOWN_SIDE_EFFECTS

        drugs_created = 0
        reactions_created = 0
        links_created = 0

        for drug_name, effects in known_side_effects.items():
            drug, created = Drug.objects.get_or_create(
                canonical_name=drug_name.lower(),
                defaults={"is_combination": False}
            )
            if created:
                drugs_created += 1

            if isinstance(effects, dict):
                for severity, effect_list in effects.items():
                    for effect in effect_list:
                        self._create_side_effect_link(
                            drug, effect, severity,
                            reactions_created, links_created
                        )
                        if isinstance(effect, str):
                            reaction, r_created = AdverseReaction.objects.get_or_create(
                                preferred_term=effect,
                                defaults={
                                    "severity_category": self._map_severity(severity)
                                }
                            )
                            if r_created:
                                reactions_created += 1

                            link, l_created = DrugAdverseReaction.objects.get_or_create(
                                drug=drug,
                                reaction=reaction,
                                defaults={
                                    "frequency": self._map_frequency(severity),
                                    "source": "synthetic",
                                    "source_text": "Migrated from hardcoded KNOWN_SIDE_EFFECTS"
                                }
                            )
                            if l_created:
                                links_created += 1
            else:
                for effect in effects:
                    reaction, r_created = AdverseReaction.objects.get_or_create(
                        preferred_term=effect,
                        defaults={"severity_category": "moderate"}
                    )
                    if r_created:
                        reactions_created += 1

                    link, l_created = DrugAdverseReaction.objects.get_or_create(
                        drug=drug,
                        reaction=reaction,
                        defaults={
                            "frequency": "common",
                            "source": "synthetic",
                            "source_text": "Migrated from hardcoded KNOWN_SIDE_EFFECTS"
                        }
                    )
                    if l_created:
                        links_created += 1

        self.stdout.write(
            f"   Created {drugs_created} drugs, {reactions_created} reactions, "
            f"{links_created} drug-reaction links"
        )

    @transaction.atomic
    def _migrate_alternatives(self):
        """Migrate alternatives_db to DrugAlternative."""
        self.stdout.write("\n[3/3] Migrating Alternatives...")

        from medguard_app.services.drug_alternatives import DrugAlternativesService

        service = DrugAlternativesService()
        alternatives_db = service.alternatives_db

        drugs_created = 0
        alternatives_created = 0

        for drug_name, alternatives in alternatives_db.items():
            original_drug, created = Drug.objects.get_or_create(
                canonical_name=drug_name.lower(),
                defaults={"is_combination": False}
            )
            if created:
                drugs_created += 1

            for alt in alternatives:
                alt_name = alt.get("name", "").lower()
                if not alt_name:
                    continue

                alt_drug, created = Drug.objects.get_or_create(
                    canonical_name=alt_name,
                    defaults={"is_combination": False}
                )
                if created:
                    drugs_created += 1

                import json
                advantages = json.dumps(alt.get("advantages", []))
                considerations = json.dumps(alt.get("considerations", []))

                alternative, created = DrugAlternative.objects.get_or_create(
                    original_drug=original_drug,
                    alternative_drug=alt_drug,
                    defaults={
                        "reason": self._map_reason(alt.get("reason", "same_class")),
                        "advantages": advantages,
                        "considerations": considerations,
                        "similarity_score": 0.85,
                        "is_otc": True,
                    }
                )
                if created:
                    alternatives_created += 1

        self.stdout.write(
            f"   Created {drugs_created} drugs, {alternatives_created} alternatives"
        )

    def _map_severity(self, severity_key: str) -> str:
        """Map severity keys to standard categories."""
        mapping = {
            "common": "mild",
            "less_common": "moderate",
            "rare": "moderate",
            "serious": "severe",
            "very_common": "mild",
        }
        return mapping.get(severity_key.lower(), "moderate")

    def _map_frequency(self, severity_key: str) -> str:
        """Map severity keys to frequency categories."""
        mapping = {
            "common": "common",
            "very_common": "very_common",
            "less_common": "uncommon",
            "rare": "rare",
            "serious": "rare",
        }
        return mapping.get(severity_key.lower(), "unknown")

    def _map_reason(self, reason: str) -> str:
        """Map reason strings to valid choices."""
        reason_lower = reason.lower().replace(" ", "_")
        valid_reasons = [
            "same_class", "similar_mechanism", "fewer_side_effects",
            "fewer_interactions", "safer_profile", "otc_alternative",
            "prescription_alternative"
        ]
        if reason_lower in valid_reasons:
            return reason_lower
        return "same_class"
