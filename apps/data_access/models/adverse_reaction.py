"""
Adverse Reaction models - Side effects and their frequencies.
"""

from django.db import models

from .drug import Drug


class AdverseReaction(models.Model):
    """
    Known adverse reactions / side effects.
    Uses MedDRA Preferred Terms when available.
    """

    SEVERITY_CHOICES = [
        ("mild", "Mild"),
        ("moderate", "Moderate"),
        ("severe", "Severe"),
        ("life_threatening", "Life-Threatening"),
    ]

    preferred_term = models.CharField(
        max_length=500, unique=True, db_index=True, help_text="MedDRA Preferred Term or reaction name"
    )
    preferred_term_normalized = models.CharField(max_length=500, db_index=True)
    meddra_code = models.CharField(
        max_length=20, null=True, blank=True, db_index=True, help_text="MedDRA code"
    )
    severity_category = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, null=True, blank=True
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "adverse_reactions"
        ordering = ["preferred_term"]
        indexes = [
            models.Index(fields=["preferred_term_normalized"], name="idx_reaction_normalized"),
            models.Index(fields=["meddra_code"], name="idx_reaction_meddra"),
        ]

    def __str__(self):
        return self.preferred_term

    def save(self, *args, **kwargs):
        if not self.preferred_term_normalized:
            self.preferred_term_normalized = self.preferred_term.lower().strip()
        super().save(*args, **kwargs)


class DrugAdverseReaction(models.Model):
    """
    Links drugs to their known adverse reactions with frequency data.
    """

    FREQUENCY_CHOICES = [
        ("very_common", ">10%"),
        ("common", "1-10%"),
        ("uncommon", "0.1-1%"),
        ("rare", "0.01-0.1%"),
        ("very_rare", "<0.01%"),
        ("unknown", "Unknown"),
    ]

    SOURCE_CHOICES = [
        ("fda_label", "FDA Drug Label"),
        ("sider", "SIDER Dataset"),
        ("faers", "FAERS Database"),
        ("synthetic", "Synthetic/ADR Data"),
    ]

    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="adverse_reactions")
    reaction = models.ForeignKey(
        AdverseReaction, on_delete=models.CASCADE, related_name="drugs"
    )
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, null=True, blank=True
    )
    report_count = models.IntegerField(
        default=0, help_text="Number of reports linking this drug-reaction pair"
    )
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    source_text = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "drug_adverse_reactions"
        unique_together = ["drug", "reaction", "source"]
        indexes = [
            models.Index(fields=["drug", "report_count"], name="idx_drug_reaction_count"),
        ]

    def __str__(self):
        return f"{self.drug.canonical_name} -> {self.reaction.preferred_term}"
