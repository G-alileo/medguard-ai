from django.db import models
from .drug import Drug

class Contraindication(models.Model):

    SEVERITY_CHOICES = [
        ("absolute", "Absolute - Never Use"),
        ("relative", "Relative - Use With Extreme Caution"),
    ]

    SOURCE_CHOICES = [
        ("fda_label", "FDA Drug Label"),
        ("sider", "SIDER Dataset"),
    ]

    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="contraindications")
    condition = models.TextField(help_text="The contraindication condition")
    condition_normalized = models.CharField(
        max_length=500, db_index=True, help_text="Normalized for matching"
    )
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, default="absolute"
    )
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    source_label_id = models.CharField(
        max_length=100, null=True, blank=True, help_text="FDA label ID if from labels"
    )

    class Meta:
        db_table = "contraindications"
        indexes = [
            models.Index(fields=["condition_normalized"], name="idx_contraindication_norm"),
            models.Index(fields=["drug", "severity"], name="idx_contraindication_drug"),
        ]

    def __str__(self):
        return f"{self.drug.canonical_name}: {self.condition[:50]}..."

    def save(self, *args, **kwargs):
        if not self.condition_normalized:
            # Take first 500 chars, lowercase
            self.condition_normalized = self.condition[:500].lower().strip()
        super().save(*args, **kwargs)
