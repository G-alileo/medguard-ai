from django.db import models
from .drug import Drug


class DrugAlternative(models.Model):

    REASON_CHOICES = [
        ("same_class", "Same Therapeutic Class"),
        ("similar_mechanism", "Similar Mechanism of Action"),
        ("fewer_side_effects", "Fewer Side Effects"),
        ("fewer_interactions", "Fewer Drug Interactions"),
        ("safer_profile", "Safer Overall Profile"),
        ("otc_alternative", "OTC Alternative"),
        ("prescription_alternative", "Prescription Alternative"),
    ]

    original_drug = models.ForeignKey(
        Drug,
        on_delete=models.CASCADE,
        related_name="alternatives_from",
        help_text="The drug being replaced"
    )
    alternative_drug = models.ForeignKey(
        Drug,
        on_delete=models.CASCADE,
        related_name="alternatives_to",
        help_text="The suggested alternative drug"
    )
    reason = models.CharField(
        max_length=50,
        choices=REASON_CHOICES,
        default="same_class"
    )
    advantages = models.TextField(
        null=True,
        blank=True,
        help_text="Benefits of this alternative (JSON list or comma-separated)"
    )
    considerations = models.TextField(
        null=True,
        blank=True,
        help_text="Things to consider with this alternative (JSON list or comma-separated)"
    )
    similarity_score = models.FloatField(
        default=0.8,
        help_text="How similar the therapeutic effect is (0.0-1.0)"
    )
    is_otc = models.BooleanField(
        default=True,
        help_text="Is the alternative available over-the-counter?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "drug_alternatives"
        unique_together = ["original_drug", "alternative_drug"]
        indexes = [
            models.Index(fields=["original_drug"], name="idx_alt_original"),
            models.Index(fields=["alternative_drug"], name="idx_alt_alternative"),
            models.Index(fields=["reason"], name="idx_alt_reason"),
        ]

    def __str__(self):
        return f"{self.original_drug.canonical_name} -> {self.alternative_drug.canonical_name}"

    def get_advantages_list(self) -> list[str]:
        """Return advantages as a list."""
        if not self.advantages:
            return []
        # Handle JSON or comma-separated
        if self.advantages.startswith("["):
            import json
            return json.loads(self.advantages)
        return [x.strip() for x in self.advantages.split(",")]

    def get_considerations_list(self) -> list[str]:
        """Return considerations as a list."""
        if not self.considerations:
            return []
        if self.considerations.startswith("["):
            import json
            return json.loads(self.considerations)
        return [x.strip() for x in self.considerations.split(",")]
