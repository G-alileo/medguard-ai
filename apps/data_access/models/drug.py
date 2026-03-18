"""
Drug models - Core drug entity and aliases.
"""

from django.db import models


class Drug(models.Model):
    """
    Central drug entity - the normalized reference for all drug names.
    Links brand names, generics, and identifiers to a single canonical drug.
    """

    canonical_name = models.CharField(
        max_length=500, unique=True, db_index=True, help_text="Normalized lowercase drug name"
    )
    rxcui = models.CharField(
        max_length=20, null=True, blank=True, db_index=True, help_text="RxNorm Concept Unique Identifier"
    )
    pubchem_cid = models.CharField(
        max_length=50, null=True, blank=True, help_text="PubChem Compound ID"
    )
    is_combination = models.BooleanField(
        default=False, help_text="True if this is a multi-drug combination product"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drugs"
        ordering = ["canonical_name"]
        indexes = [
            models.Index(fields=["canonical_name"], name="idx_drug_canonical"),
            models.Index(fields=["rxcui"], name="idx_drug_rxcui"),
        ]

    def __str__(self):
        return self.canonical_name

    @property
    def all_names(self) -> list[str]:
        """Return all known names for this drug."""
        names = [self.canonical_name]
        names.extend(alias.alias for alias in self.aliases.all())
        return names


class DrugAlias(models.Model):
    """
    All known names for a drug (brand names, generic variations, spelling variants).
    Enables search: input any alias -> find canonical drug.
    """

    ALIAS_TYPE_CHOICES = [
        ("brand", "Brand Name"),
        ("generic", "Generic Name"),
        ("variant", "Spelling Variant"),
        ("substance", "Active Substance"),
        ("combination", "Combination Product"),
    ]

    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=500, help_text="The alias name as-is")
    alias_normalized = models.CharField(
        max_length=500, db_index=True, help_text="Lowercase normalized for matching"
    )
    alias_type = models.CharField(max_length=20, choices=ALIAS_TYPE_CHOICES, default="generic")

    class Meta:
        db_table = "drug_aliases"
        unique_together = ["drug", "alias_normalized"]
        indexes = [
            models.Index(fields=["alias_normalized"], name="idx_alias_normalized"),
            models.Index(fields=["alias_type"], name="idx_alias_type"),
        ]

    def __str__(self):
        return f"{self.alias} -> {self.drug.canonical_name}"

    def save(self, *args, **kwargs):
        if not self.alias_normalized:
            self.alias_normalized = self.alias.lower().strip()
        super().save(*args, **kwargs)
