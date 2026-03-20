from django.db import models

class MedDRACode(models.Model):

    code = models.CharField(max_length=20, primary_key=True)
    preferred_term = models.CharField(max_length=500, db_index=True)
    soc_code = models.CharField(
        max_length=20, null=True, blank=True, help_text="System Organ Class code"
    )
    soc_name = models.CharField(
        max_length=200, null=True, blank=True, help_text="System Organ Class name"
    )

    class Meta:
        db_table = "meddra_codes"
        verbose_name = "MedDRA Code"
        verbose_name_plural = "MedDRA Codes"

    def __str__(self):
        return f"{self.code}: {self.preferred_term}"
