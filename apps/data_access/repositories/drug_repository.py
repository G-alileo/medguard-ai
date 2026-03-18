"""
Drug Repository - Data access layer for drug entities.
"""

from typing import Optional

from django.db.models import Q, Count

from apps.data_access.models import (
    Drug,
    DrugAlias,
    DrugIndication,
    DrugAdverseReaction,
    Contraindication,
)
from apps.pipeline.processing import normalize_drug_name


class DrugRepository:
    """
    Repository for accessing drug data.
    Provides clean interface for business logic layer.
    """

    def get_by_id(self, drug_id: int) -> Optional[Drug]:
        """Get a drug by its primary key."""
        try:
            return Drug.objects.get(id=drug_id)
        except Drug.DoesNotExist:
            return None

    def get_by_name(self, name: str) -> Optional[Drug]:
        """
        Get a drug by any name (brand, generic, alias).

        Performs normalization to find the canonical drug.
        """
        # First, try exact match on canonical name
        name_lower = name.lower().strip()

        drug = Drug.objects.filter(canonical_name=name_lower).first()
        if drug:
            return drug

        # Try alias lookup
        alias = DrugAlias.objects.filter(alias_normalized=name_lower).select_related("drug").first()
        if alias:
            return alias.drug

        # Try normalization
        result = normalize_drug_name(name)
        if result.canonical_name:
            return Drug.objects.filter(canonical_name=result.canonical_name).first()

        return None

    def search(self, query: str, limit: int = 10) -> list[Drug]:
        """
        Search for drugs by name (partial match).

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching drugs
        """
        query_lower = query.lower().strip()

        # Search in canonical names
        drugs = Drug.objects.filter(
            canonical_name__icontains=query_lower
        ).order_by("canonical_name")[:limit]

        if drugs.exists():
            return list(drugs)

        # Search in aliases
        alias_matches = (
            DrugAlias.objects
            .filter(alias_normalized__icontains=query_lower)
            .select_related("drug")
            .values_list("drug", flat=True)
            .distinct()[:limit]
        )

        return list(Drug.objects.filter(id__in=alias_matches))

    def get_all_names(self, drug: Drug) -> list[str]:
        """Get all known names for a drug."""
        names = [drug.canonical_name]
        names.extend(
            drug.aliases.values_list("alias", flat=True)
        )
        return list(set(names))

    def get_indications(self, drug: Drug) -> list[str]:
        """Get conditions this drug treats."""
        return list(
            DrugIndication.objects
            .filter(drug=drug)
            .select_related("indication")
            .values_list("indication__name", flat=True)
            .distinct()
        )

    def get_side_effects(self, drug: Drug, limit: int = 20) -> list[dict]:
        """
        Get known side effects for a drug.

        Returns:
            List of dicts with reaction info and report counts
        """
        reactions = (
            DrugAdverseReaction.objects
            .filter(drug=drug)
            .select_related("reaction")
            .order_by("-report_count")[:limit]
        )

        return [
            {
                "reaction": r.reaction.preferred_term,
                "frequency": r.frequency,
                "report_count": r.report_count,
                "source": r.source,
            }
            for r in reactions
        ]

    def get_contraindications(self, drug: Drug) -> list[dict]:
        """Get contraindications for a drug."""
        return list(
            Contraindication.objects
            .filter(drug=drug)
            .values("condition", "severity")
        )

    def get_drugs_with_most_interactions(self, limit: int = 10) -> list[dict]:
        """Get drugs with the most known interactions."""
        from data_access.models import DrugInteraction

        # Count interactions for each drug
        drug_counts = (
            Drug.objects
            .annotate(
                interaction_count=Count("interactions_as_a") + Count("interactions_as_b")
            )
            .filter(interaction_count__gt=0)
            .order_by("-interaction_count")[:limit]
        )

        return [
            {
                "drug": d.canonical_name,
                "interaction_count": d.interaction_count,
            }
            for d in drug_counts
        ]

    def get_drugs_by_rxcui(self, rxcui: str) -> Optional[Drug]:
        """Get a drug by its RxNorm CUI."""
        return Drug.objects.filter(rxcui=rxcui).first()
