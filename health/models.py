# health/models.py
from pathlib import Path
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class HealthRequest(models.Model):
    """
    Demande d'aide santé mentale anonyme
    """
    CATEGORY_CHOICES = [
        ('stress', '😰 Stress / Examens'),
        ('family', '👨‍👩‍👧 Problèmes familiaux'),
        ('school', '📚 Problèmes scolaires'),
        ('anxiety', '🌪️ Anxiété / Angoisses'),
        ('other', '💬 Autre'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('in_progress', 'En cours'),
        ('closed', 'Clôturée'),
    ]
    
    URGENCY_CHOICES = [
        ('low', '🟢 Faible'),
        ('medium', '🟠 Modéré'),
        ('high', '🔴 Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='health_requests')
    anonymous_id = models.CharField(max_length=50)
    
    # Catégorisation IA
    ai_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    ai_confidence = models.FloatField(default=0.0)
    ai_explanation = models.TextField(blank=True)
    ai_trace_id = models.CharField(max_length=100, blank=True)
    
    # Override par conseiller (Human in the loop)
    overridden_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, null=True, blank=True)
    overridden_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='overridden_requests')
    overridden_at = models.DateTimeField(null=True, blank=True)
    
    # Gestion
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    urgency_level = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='low')
    counselor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_requests')
    
    # Métadonnées
    student_age_group = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_summary = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.anonymous_id} - {self.get_status_display()}"
    
    def get_effective_category(self):
        return self.overridden_category or self.ai_category
    
    def get_effective_confidence(self):
        if self.overridden_category:
            return 100.0
        return self.ai_confidence
    
    def get_effective_category_display(self):
        category = self.get_effective_category()
        return dict(self.CATEGORY_CHOICES).get(category, category)
    
    def save(self, *args, **kwargs):
        if not self.urgency_level or self.urgency_level == 'low':
            if self.ai_category in ['anxiety', 'stress'] and self.ai_confidence > 80:
                self.urgency_level = 'high'
            elif self.ai_confidence > 70:
                self.urgency_level = 'medium'
        super().save(*args, **kwargs)


class Message(models.Model):
    """
    Message dans le chat (WebSocket)
    """
    ROLE_CHOICES = [
        ('student', 'Étudiant'),
        ('counselor', 'Conseiller'),
        ('system', 'Système'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    health_request = models.ForeignKey(HealthRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=100)
    sender_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"


class ChatSession(models.Model):
    """
    Session de chat active pour WebSocket
    """
    health_request = models.OneToOneField(HealthRequest, on_delete=models.CASCADE, related_name='chat_session')
    is_active = models.BooleanField(default=True)
    counselor_channel = models.CharField(max_length=255, blank=True)
    student_channel = models.CharField(max_length=255, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session {self.health_request.anonymous_id}"


class HealthTimelineEvent(models.Model):
    """
    Timeline des événements pour traçabilité complète
    """
    EVENT_TYPES = [
        ('created', 'Création de la demande'),
        ('ia_categorized', 'Catégorisation IA'),
        ('ia_override', 'Override par conseiller'),
        ('assigned', 'Prise en charge'),
        ('message_sent', 'Message envoyé'),
        ('closed', 'Clôture'),
    ]
    
    health_request = models.ForeignKey(HealthRequest, on_delete=models.CASCADE, related_name='timeline_events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    actor = models.CharField(max_length=100)
    action = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.created_at.strftime('%H:%M')} - {self.action}"


class AuditLog(models.Model):
    """
    Log de sécurité pour traçabilité des actions sensibles
    """
    ACTION_CHOICES = [
        ('view_identity', 'Tentative de voir identité réelle'),
        ('override_category', 'Override catégorie IA'),
        ('access_denied', 'Accès refusé'),
        ('websocket_disconnect', 'Déconnexion WebSocket'),
        ('security_violation', 'Violation de sécurité'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resource = models.CharField(max_length=200)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.created_at} - {self.action} by {self.user}"