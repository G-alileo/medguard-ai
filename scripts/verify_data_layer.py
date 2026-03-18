#!/usr/bin/env python
"""
Data Layer Verification Script

Validates that data was loaded correctly into MySQL and ChromaDB.

Usage:
    python scripts/verify_data_layer.py
"""

import os
import sys
import time
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medguard.settings")

import django
django.setup()

from django.db.models import Count
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
from apps.data_access.repositories import DrugRepository, InteractionRepository
from apps.data_access.vector_store import get_chroma_client


class DataLayerVerifier:
    """Verifies data layer integrity."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.drug_repo = DrugRepository()
        self.interaction_repo = InteractionRepository()

    def verify_all(self) -> bool:
        """Run all verification checks."""
        print("=" * 60)
        print("MEDGUARD DATA LAYER VERIFICATION")
        print("=" * 60)

        # MySQL checks
        print("\n[1/5] Checking MySQL table counts...")
        self.check_table_counts()

        print("\n[2/5] Testing drug lookups...")
        self.check_drug_lookups()

        print("\n[3/5] Testing interaction checks...")
        self.check_interactions()

        print("\n[4/5] Checking vector store...")
        self.check_vector_store()

        print("\n[5/5] Testing query performance...")
        self.check_performance()

        # Report results
        self.report_results()

        return len(self.errors) == 0

    def check_table_counts(self):
        """Verify record counts in all tables."""
        counts = {
            "Drug": Drug.objects.count(),
            "DrugAlias": DrugAlias.objects.count(),
            "Indication": Indication.objects.count(),
            "DrugIndication": DrugIndication.objects.count(),
            "AdverseReaction": AdverseReaction.objects.count(),
            "DrugAdverseReaction": DrugAdverseReaction.objects.count(),
            "DrugInteraction": DrugInteraction.objects.count(),
            "Contraindication": Contraindication.objects.count(),
            "AdverseEventReport": AdverseEventReport.objects.count(),
            "EventReportDrug": EventReportDrug.objects.count(),
            "EventReportReaction": EventReportReaction.objects.count(),
        }

        print("\n  Table Counts:")
        for table, count in counts.items():
            status = "OK" if count > 0 else "EMPTY"
            print(f"    {table}: {count:,} ({status})")

        # Minimum expected counts
        if counts["Drug"] < 10:
            self.errors.append(f"Too few drugs: {counts['Drug']}")
        if counts["AdverseReaction"] < 10:
            self.errors.append(f"Too few adverse reactions: {counts['AdverseReaction']}")

    def check_drug_lookups(self):
        """Test drug name lookups."""
        test_drugs = [
            "acetaminophen",
            "ibuprofen",
            "metformin",
            "lisinopril",
            "atorvastatin",
        ]

        print("\n  Drug Lookup Tests:")
        for drug_name in test_drugs:
            drug = self.drug_repo.get_by_name(drug_name)
            if drug:
                print(f"    {drug_name}: FOUND (id={drug.id})")
            else:
                print(f"    {drug_name}: NOT FOUND")
                self.warnings.append(f"Drug not found: {drug_name}")

        # Test brand name lookup
        brand_tests = [
            ("tylenol", "acetaminophen"),
            ("advil", "ibuprofen"),
            ("lipitor", "atorvastatin"),
        ]

        print("\n  Brand Name Lookup Tests:")
        for brand, expected_generic in brand_tests:
            drug = self.drug_repo.get_by_name(brand)
            if drug:
                if drug.canonical_name == expected_generic:
                    print(f"    {brand} -> {drug.canonical_name}: CORRECT")
                else:
                    print(f"    {brand} -> {drug.canonical_name}: UNEXPECTED")
                    self.warnings.append(f"Brand {brand} mapped to {drug.canonical_name}, expected {expected_generic}")
            else:
                print(f"    {brand}: NOT FOUND")

    def check_interactions(self):
        """Test interaction lookups."""
        print("\n  Interaction Tests:")

        # Get some drugs with interactions
        drugs_with_interactions = (
            Drug.objects
            .annotate(
                int_count=Count("interactions_as_a") + Count("interactions_as_b")
            )
            .filter(int_count__gt=0)
            .order_by("-int_count")[:5]
        )

        if not drugs_with_interactions:
            self.warnings.append("No drugs with interactions found")
            print("    No drugs with interactions found")
            return

        for drug in drugs_with_interactions:
            interactions = self.interaction_repo.get_all_interactions(drug)
            print(f"    {drug.canonical_name}: {len(interactions)} interactions")

        # Test specific interaction check
        print("\n  Specific Interaction Check:")
        test_pairs = [
            ("warfarin", "aspirin"),
            ("metformin", "ibuprofen"),
        ]

        for drug1, drug2 in test_pairs:
            interaction = self.interaction_repo.check_interaction(drug1, drug2)
            if interaction:
                print(f"    {drug1} + {drug2}: {interaction.severity}")
            else:
                print(f"    {drug1} + {drug2}: No interaction found")

    def check_vector_store(self):
        """Verify vector store collections."""
        print("\n  Vector Store Collections:")

        try:
            chroma = get_chroma_client()
            stats = chroma.get_collection_stats()

            for coll_name, info in stats.items():
                count = info.get("count", 0)
                status = "OK" if count > 0 else "EMPTY"
                print(f"    {coll_name}: {count:,} chunks ({status})")

                if count == 0:
                    self.warnings.append(f"Vector collection {coll_name} is empty")

        except Exception as e:
            self.errors.append(f"Vector store error: {e}")
            print(f"    ERROR: {e}")

        # Test semantic search
        print("\n  Semantic Search Tests:")
        try:
            chroma = get_chroma_client()

            test_queries = [
                ("diabetes treatment", "drug_labels"),
                ("headache side effect", "adverse_reactions"),
            ]

            for query, collection in test_queries:
                results = chroma.search_similar(query, collection, limit=3)
                print(f"    '{query}' in {collection}: {len(results)} results")

        except Exception as e:
            self.errors.append(f"Semantic search error: {e}")
            print(f"    ERROR: {e}")

    def check_performance(self):
        """Test query performance."""
        print("\n  Performance Tests:")

        # Drug lookup
        start = time.time()
        for _ in range(100):
            self.drug_repo.get_by_name("acetaminophen")
        elapsed = (time.time() - start) * 10  # ms per query
        print(f"    Drug lookup (100x): {elapsed:.2f}ms avg")

        if elapsed > 10:
            self.warnings.append(f"Drug lookup slow: {elapsed:.2f}ms")

        # Interaction check
        start = time.time()
        for _ in range(100):
            self.interaction_repo.check_interaction("warfarin", "aspirin")
        elapsed = (time.time() - start) * 10
        print(f"    Interaction check (100x): {elapsed:.2f}ms avg")

        if elapsed > 20:
            self.warnings.append(f"Interaction check slow: {elapsed:.2f}ms")

    def report_results(self):
        """Print final report."""
        print("\n" + "=" * 60)
        print("VERIFICATION RESULTS")
        print("=" * 60)

        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  ❌ {error}")
        else:
            print("\n✅ No errors found")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        if not self.errors and not self.warnings:
            print("\n🎉 All verification checks passed!")


def main():
    verifier = DataLayerVerifier()
    success = verifier.verify_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
