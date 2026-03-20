from django.db import models
from .drug import Drug


class Indication(models.Model):

    name = models.CharField(max_length=500, unique=True, db_index=True)
    name_normalized = models.CharField(max_length=500, db_index=True)
    meddra_code = models.CharField(
        max_length=20, null=True, blank=True, db_index=True, help_text="MedDRA code if available"
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "indications"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name_normalized"], name="idx_indication_normalized"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.name_normalized:
            self.name_normalized = self.name.lower().strip()
        super().save(*args, **kwargs)


class DrugIndication(models.Model):

    SOURCE_CHOICES = [
        ("fda_label", "FDA Drug Label"),
        ("sider", "SIDER Dataset"),
        ("faers", "FAERS Database"),
        ("synthetic", "Synthetic/ADR Data"),
    ]

    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="indications")
    indication = models.ForeignKey(Indication, on_delete=models.CASCADE, related_name="drugs")
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    confidence = models.FloatField(default=1.0, help_text="Confidence score 0.0-1.0")
    source_text = models.TextField(null=True, blank=True, help_text="Original text from source")

    class Meta:
        db_table = "drug_indications"
        unique_together = ["drug", "indication", "source"]

    def __str__(self):
        return f"{self.drug.canonical_name} treats {self.indication.name}"
