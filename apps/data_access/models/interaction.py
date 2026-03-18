"""
Drug Interaction models - The CORE table for risk assessment.
"""

from django.db import models

from .drug import Drug


class DrugInteraction(models.Model):
    """
    Drug-drug interactions. This is the CORE table for risk assessment.

    Interaction between drug_a and drug_b. Order is normalized so
    drug_a.id < drug_b.id to avoid duplicates.
    """

    SEVERITY_CHOICES = [
        ("contraindicated", "Contraindicated - Do Not Use Together"),
        ("major", "Major - Serious Consequences Likely"),
        ("moderate", "Moderate - Use With Caution"),
        ("minor", "Minor - Minimal Clinical Significance"),
        ("unknown", "Unknown Severity"),
    ]

    EVIDENCE_CHOICES = [
        ("established", "Established"),
        ("probable", "Probable"),
        ("suspected", "Suspected"),
        ("theoretical", "Theoretical"),
    ]

    SOURCE_CHOICES = [
        ("fda_label", "FDA Drug Label"),
        ("faers", "FAERS Database"),
        ("sider", "SIDER Dataset"),
        ("synthetic", "Synthetic/ADR Data"),
    ]

    drug_a = models.ForeignKey(
        Drug, on_delete=models.CASCADE, related_name="interactions_as_a"
    )
    drug_b = models.ForeignKey(
        Drug, on_delete=models.CASCADE, related_name="interactions_as_b"
    )
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default="unknown", db_index=True
    )
    description = models.TextField(help_text="Description of the interaction")
    clinical_effect = models.TextField(
        null=True, blank=True, help_text="What happens clinically"
    )
    management = models.TextField(
        null=True, blank=True, help_text="How to manage this interaction"
    )
    evidence_level = models.CharField(
        max_length=20, choices=EVIDENCE_CHOICES, null=True, blank=True
    )
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    source_label_id = models.CharField(
        max_length=100, null=True, blank=True, help_text="FDA label ID if from labels"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "drug_interactions"
        unique_together = ["drug_a", "drug_b"]
        indexes = [
            models.Index(fields=["drug_a", "severity"], name="idx_interaction_a_severity"),
            models.Index(fields=["drug_b", "severity"], name="idx_interaction_b_severity"),
            models.Index(fields=["severity"], name="idx_interaction_severity"),
        ]

    def __str__(self):
        return f"{self.drug_a.canonical_name} <-> {self.drug_b.canonical_name} ({self.severity})"

    def save(self, *args, **kwargs):
        # Ensure drug_a.id < drug_b.id to prevent duplicate pairs
        if self.drug_a_id and self.drug_b_id and self.drug_a_id > self.drug_b_id:
            self.drug_a_id, self.drug_b_id = self.drug_b_id, self.drug_a_id
        super().save(*args, **kwargs)

    @property
    def is_dangerous(self) -> bool:
        """Check if this interaction is dangerous (contraindicated or major)."""
        return self.severity in ("contraindicated", "major")
