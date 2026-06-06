# early_warning/models.py

from django.db import models
from django.core.exceptions import ValidationError


class ThresholdConfig(models.Model):
    """Configuration des seuils d'alerte — singleton"""
    high_risk_threshold = models.IntegerField(
        default=70,
        help_text="Score à partir duquel le risque est élevé (0-100)"
    )
    medium_risk_threshold = models.IntegerField(
        default=40,
        help_text="Score à partir duquel le risque est moyen (0-100)"
    )
    alert_threshold = models.IntegerField(
        default=50,
        help_text="Score à partir duquel une alerte est générée (0-100)"
    )
    absence_weight = models.IntegerField(default=40, help_text="Pondération absences (%)")
    grade_weight = models.IntegerField(default=40, help_text="Pondération notes (%)")
    behavior_weight = models.IntegerField(default=20, help_text="Pondération comportement (%)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration des seuils"
        verbose_name_plural = "Configurations des seuils"

    def __str__(self):
        return f"Seuils (High:{self.high_risk_threshold} Med:{self.medium_risk_threshold})"

    def clean(self):
        total = self.absence_weight + self.grade_weight + self.behavior_weight
        if total != 100:
            raise ValidationError(
                f"Les pondérations doivent totaliser 100% (actuellement: {total}%)"
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create()
        return config


class RiskScore(models.Model):
    """Score de risque calculé pour un étudiant"""
    RISK_LEVEL_CHOICES = [
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Elevé'),
    ]

    student_name = models.CharField(max_length=100)
    student_id = models.IntegerField(db_index=True)
    class_name = models.CharField(max_length=100)
    absences = models.IntegerField()
    avg_grade = models.FloatField()
    behavior_score = models.IntegerField(help_text="Score comportement (0-10)")
    risk_score = models.FloatField()
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-risk_score']
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['class_name']),
            models.Index(fields=['risk_level']),
        ]

    def __str__(self):
        return f"{self.student_name} — Score: {self.risk_score:.1f} ({self.get_risk_level_display()})"

    def risk_level_emoji(self):
        return {'high': '🔴', 'medium': '🟠', 'low': '🟢'}.get(self.risk_level, '')


class AISuggestion(models.Model):
    """Suggestion générée par l'IA (ou fallback) pour une alerte"""
    ACTION_CHOICES = [
        ('quiz', 'Quiz personnalisé'),
        ('meeting', 'Réunion parents-professeurs'),
        ('followup', 'Séances de suivi'),
        ('counseling', 'Orientation psychologue scolaire'),
    ]

    suggested_action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    explanation_primary_factor = models.TextField()
    explanation_secondary_factor = models.TextField(blank=True)
    explanation_basis = models.TextField()
    confidence = models.FloatField()
    trace_id = models.CharField(max_length=100, blank=True)
    fallback_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_suggested_action_display()} — {self.confidence:.0%}"

    def confidence_percent(self):
        return f"{self.confidence * 100:.0f}%"


class Alert(models.Model):
    """Alerte générée pour un étudiant à risque"""
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('in_progress', 'En cours'),
        ('resolved', 'Résolu'),
        ('ignored', 'Ignoré'),
    ]

    risk_score = models.ForeignKey(RiskScore, on_delete=models.CASCADE, related_name='alerts')
    ai_suggestion = models.ForeignKey(
        AISuggestion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='alerts'
    )
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"Alerte #{self.id} — {self.risk_score.student_name} — {self.get_status_display()}"

    def status_color(self):
        return {
            'pending': '#E24B4A',
            'in_progress': '#EF9F27',
            'resolved': '#639922',
            'ignored': '#888780',
        }.get(self.status, '#888780')


class Intervention(models.Model):
    """Plan d'action créé par le professeur"""
    ACTION_TYPE_CHOICES = [
        ('quiz', 'Quiz personnalisé'),
        ('meeting', 'Réunion parents-professeurs'),
        ('followup', 'Séances de suivi'),
        ('counseling', 'Orientation psychologue scolaire'),
        ('custom', 'Action personnalisée'),
    ]
    STATUS_CHOICES = [
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    ]

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='interventions')
    ai_suggestion = models.ForeignKey(
        AISuggestion, on_delete=models.SET_NULL, null=True, blank=True
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPE_CHOICES)
    description = models.TextField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f"{self.get_action_type_display()} — {self.alert.risk_score.student_name}"

    def is_overdue(self):
        from django.utils import timezone
        return (
            self.due_date < timezone.now().date()
            and self.status not in ['completed', 'cancelled']
        )