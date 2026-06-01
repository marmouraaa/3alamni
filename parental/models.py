from django.db import models
from accounts.models import User, StudentProfile

class ParentalControl(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE)
    child = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    education_enabled = models.BooleanField(default=True)
    health_enabled = models.BooleanField(default=True)
    study_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Contrôle {self.parent} → {self.child}"

class WeeklyReport(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE)
    child = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    week_start = models.DateField()
    total_study_hours = models.FloatField()
    quiz_completed = models.IntegerField()
    average_score = models.FloatField()
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rapport {self.child} - semaine {self.week_start}"