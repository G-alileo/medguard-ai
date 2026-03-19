from django import forms


class DrugEvaluationForm(forms.Form):
    """Form for collecting drug evaluation input from users."""

    symptoms = forms.CharField(
        label="Your Symptoms",
        widget=forms.Textarea(attrs={
            'placeholder': 'e.g., headache, nausea, fever',
            'rows': 3,
            'class': 'form-textarea',
        }),
        help_text="Describe your current symptoms, one per line or comma-separated"
    )

    drug = forms.CharField(
        label="Medication Given by Chemist",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g., ibuprofen',
            'class': 'form-input',
        }),
        help_text="Enter the medication name prescribed by your chemist"
    )

    existing_medications = forms.CharField(
        label="Existing Medications (if any)",
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'e.g., aspirin, lisinopril, metformin',
            'rows': 3,
            'class': 'form-textarea',
        }),
        help_text="List any medications you are currently taking"
    )
