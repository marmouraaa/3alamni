from django.db import models
from accounts.models import User

class AuditLog(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )
    role = models.CharField(max_length=20)
    action = models.CharField(max_length=100)
    case_id = models.CharField(max_length=100, null=True, blank=True)
    result = models.CharField(max_length=20)   # success / blocked
    reason = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=50, null=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['action', 'result', 'timestamp'])]

    def __str__(self):
        return f"{self.timestamp} | {self.role} | {self.action} | {self.result}"