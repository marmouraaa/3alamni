from django.db import models
from accounts.models import StudentProfile

class StudySession(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # secondes
    is_complete = models.BooleanField(default=False)
    
class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10)
    condition_type = models.CharField(max_length=20)  # study_time, quiz_count, etc.
    condition_value = models.IntegerField()
    
class StudentBadge(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)