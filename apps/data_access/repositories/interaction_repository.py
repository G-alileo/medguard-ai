from typing import Optional
from django.db.models import Q
from apps.data_access.models import Drug, DrugInteraction
from .drug_repository import DrugRepository


class InteractionRepository:

    def __init__(self):
        self.drug_repo = DrugRepository()

    def check_interaction(
        self,
        drug1: Drug | str | int,
        drug2: Drug | str | int,
    ) -> Optional[DrugInteraction]:

        # Resolve drugs
        d1 = self._resolve_drug(drug1)
        d2 = self._resolve_drug(drug2)

        if not d1 or not d2:
            return None

        # Check both orderings (though save() normalizes order)
        interaction = DrugInteraction.objects.filter(
            Q(drug_a=d1, drug_b=d2) | Q(drug_a=d2, drug_b=d1)
        ).first()

        return interaction

    def get_all_interactions(self, drug: Drug | str | int) -> list[DrugInteraction]:

        d = self._resolve_drug(drug)
        if not d:
            return []

        return list(
            DrugInteraction.objects
            .filter(Q(drug_a=d) | Q(drug_b=d))
            .select_related("drug_a", "drug_b")
            .order_by("-severity")
        )

    def get_dangerous_interactions(self, drug: Drug | str | int) -> list[DrugInteraction]:

        d = self._resolve_drug(drug)
        if not d:
            return []

        return list(
            DrugInteraction.objects
            .filter(
                Q(drug_a=d) | Q(drug_b=d),
                severity__in=["contraindicated", "major"],
            )
            .select_related("drug_a", "drug_b")
        )

    def check_multiple_interactions(
        self,
        drugs: list[Drug | str | int],
    ) -> list[dict]:

        # Resolve all drugs
        resolved = [self._resolve_drug(d) for d in drugs]
        resolved = [d for d in resolved if d is not None]

        if len(resolved) < 2:
            return []

        interactions = []

        # Check all pairs
        for i, drug1 in enumerate(resolved):
            for drug2 in resolved[i + 1:]:
                interaction = self.check_interaction(drug1, drug2)
                if interaction:
                    interactions.append({
                        "drug_a": interaction.drug_a.canonical_name,
                        "drug_b": interaction.drug_b.canonical_name,
                        "severity": interaction.severity,
                        "description": interaction.description,
                        "clinical_effect": interaction.clinical_effect,
                        "management": interaction.management,
                        "is_dangerous": interaction.is_dangerous,
                    })

        # Sort by severity (most dangerous first)
        severity_order = {
            "contraindicated": 0,
            "major": 1,
            "moderate": 2,
            "minor": 3,
            "unknown": 4,
        }
        interactions.sort(key=lambda x: severity_order.get(x["severity"], 5))

        return interactions

    def get_interacting_drugs(self, drug: Drug | str | int) -> list[dict]:

        d = self._resolve_drug(drug)
        if not d:
            return []

        interactions = self.get_all_interactions(d)
        result = []

        for interaction in interactions:
            # Determine which drug is the "other" one
            other = interaction.drug_b if interaction.drug_a == d else interaction.drug_a

            result.append({
                "drug": other.canonical_name,
                "severity": interaction.severity,
                "is_dangerous": interaction.is_dangerous,
            })

        return result

    def get_interactions_by_severity(
        self,
        severity: str,
        limit: int = 100,
    ) -> list[DrugInteraction]:

        return list(
            DrugInteraction.objects
            .filter(severity=severity)
            .select_related("drug_a", "drug_b")[:limit]
        )

    def _resolve_drug(self, drug: Drug | str | int) -> Optional[Drug]:
        """Resolve drug input to Drug object."""
        if isinstance(drug, Drug):
            return drug
        elif isinstance(drug, int):
            return self.drug_repo.get_by_id(drug)
        elif isinstance(drug, str):
            return self.drug_repo.get_by_name(drug)
        return None

    def count_interactions_by_severity(self) -> dict[str, int]:
        """Get count of interactions grouped by severity."""
        from django.db.models import Count

        counts = (
            DrugInteraction.objects
            .values("severity")
            .annotate(count=Count("id"))
        )

        return {item["severity"]: item["count"] for item in counts}
