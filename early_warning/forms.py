# early_warning/forms.py

from django import forms
from .models import ThresholdConfig, Intervention


class ImportCSVForm(forms.Form):
    """Formulaire d'import CSV"""
    csv_file = forms.FileField(
        label="Fichier CSV",
        help_text=(
            "Format attendu: "
            "student_name, student_id, class_name, "
            "absences, avg_grade, behavior_score"
        ),
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'form-control',
        })
    )

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']
        if not f.name.lower().endswith('.csv'):
            raise forms.ValidationError(
                "Le fichier doit être au format .csv"
            )
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError(
                "Le fichier ne doit pas dépasser 10 MB"
            )
        return f


class ThresholdConfigForm(forms.ModelForm):
    """
    Formulaire de configuration des seuils.
    """
    class Meta:
        model = ThresholdConfig
        exclude = ['created_at', 'updated_at']
        widgets = {
            'high_risk_threshold': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100
            }),
            'medium_risk_threshold': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100
            }),
            'alert_threshold': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100
            }),
            'absence_weight': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100
            }),
            'grade_weight': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100
            }),
            'behavior_weight': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100
            }),
        }

    def clean(self):
        cleaned = super().clean()
        total = (
            cleaned.get('absence_weight', 0) +
            cleaned.get('grade_weight', 0) +
            cleaned.get('behavior_weight', 0)
        )
        if total != 100:
            raise forms.ValidationError(
                f"La somme des pondérations doit être 100% (actuellement: {total}%)"
            )
        return cleaned


class InterventionForm(forms.ModelForm):
    """Formulaire de création d'une intervention"""
    class Meta:
        model = Intervention
        fields = ['action_type', 'description', 'due_date', 'notes']
        widgets = {
            'action_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Notes de suivi (optionnel)'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.ai_suggestion = kwargs.pop('ai_suggestion', None)
        super().__init__(*args, **kwargs)
        if self.ai_suggestion:
            self.fields['action_type'].initial = self.ai_suggestion.suggested_action
            self.fields['description'].initial = self.ai_suggestion.description
            self.fields['description'].help_text = (
                f"Suggestion IA — confiance: "
                f"{self.ai_suggestion.confidence * 100:.0f}%"
            )