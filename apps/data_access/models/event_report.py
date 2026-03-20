from django.db import models
from .drug import Drug
from .adverse_reaction import AdverseReaction


class AdverseEventReport(models.Model):

    SOURCE_CHOICES = [
        ("openfda_events", "OpenFDA Drug Events"),
        ("fda_csv", "FDA Adverse Events CSV"),
        ("synthetic", "Synthetic/ADR Data"),
    ]

    safety_report_id = models.CharField(
        max_length=50, unique=True, db_index=True, help_text="External report ID"
    )
    report_date = models.DateField(null=True, blank=True)
    is_serious = models.BooleanField(default=False)
    seriousness_death = models.BooleanField(default=False)
    seriousness_hospitalization = models.BooleanField(default=False)
    seriousness_disability = models.BooleanField(default=False)
    seriousness_lifethreatening = models.BooleanField(default=False)

    # Patient demographics
    patient_age = models.IntegerField(null=True, blank=True)
    patient_sex = models.CharField(
        max_length=1, null=True, blank=True, help_text="M=Male, F=Female, U=Unknown"
    )

    # Source tracking
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    source_file = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "adverse_event_reports"
        indexes = [
            models.Index(fields=["report_date"], name="idx_report_date"),
            models.Index(fields=["is_serious"], name="idx_report_serious"),
            models.Index(fields=["source"], name="idx_report_source"),
        ]

    def __str__(self):
        return f"Report {self.safety_report_id}"


class EventReportDrug(models.Model):

    CHARACTERIZATION_CHOICES = [
        ("suspect", "Primary Suspect"),
        ("concomitant", "Concomitant"),
        ("interacting", "Interacting"),
    ]

    report = models.ForeignKey(
        AdverseEventReport, on_delete=models.CASCADE, related_name="drugs"
    )
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="event_reports")
    characterization = models.CharField(
        max_length=20, choices=CHARACTERIZATION_CHOICES, default="suspect"
    )
    dosage = models.CharField(max_length=100, null=True, blank=True)
    indication = models.CharField(
        max_length=500, null=True, blank=True, help_text="Why the drug was taken"
    )
    drug_name_raw = models.CharField(
        max_length=500, null=True, blank=True, help_text="Original drug name from report"
    )

    class Meta:
        db_table = "event_report_drugs"
        indexes = [
            models.Index(fields=["drug", "characterization"], name="idx_event_drug_char"),
        ]

    def __str__(self):
        return f"{self.report.safety_report_id}: {self.drug.canonical_name}"


class EventReportReaction(models.Model):
    """
    Reactions reported in an adverse event.
    """

    OUTCOME_CHOICES = [
        ("recovered", "Recovered"),
        ("recovering", "Recovering"),
        ("not_recovered", "Not Recovered"),
        ("fatal", "Fatal"),
        ("unknown", "Unknown"),
    ]

    report = models.ForeignKey(
        AdverseEventReport, on_delete=models.CASCADE, related_name="reactions"
    )
    reaction = models.ForeignKey(
        AdverseReaction, on_delete=models.CASCADE, related_name="event_reports"
    )
    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, null=True, blank=True
    )
    reaction_name_raw = models.CharField(
        max_length=500, null=True, blank=True, help_text="Original reaction name from report"
    )

    class Meta:
        db_table = "event_report_reactions"
        indexes = [
            models.Index(fields=["reaction"], name="idx_event_reaction"),
        ]

    def __str__(self):
        return f"{self.report.safety_report_id}: {self.reaction.preferred_term}"
