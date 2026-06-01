from django.db import models
from django.conf import settings

class StudySession(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # secondes
    is_complete = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.student.username} - {self.duration}s"

class Badge(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10, default='🏆')
    condition_type = models.CharField(max_length=20)  # study_time, quiz_count, etc.
    condition_value = models.IntegerField()
    
    def __str__(self):
        return self.name

class StudentBadge(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'badge']
    
    def __str__(self):
        return f"{self.student.username} - {self.badge.name}"