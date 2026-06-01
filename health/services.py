# health/services.py
import logging
import uuid
from typing import Dict, Any
from django.utils import timezone
from groq import Groq
from django.conf import settings

logger = logging.getLogger(__name__)


class HealthService:
    """Service pour la gestion des demandes santé mentale"""
    
    def create_request(self, student, message: str, category: str, age_group: str = ""):
        from .models import HealthRequest, HealthTimelineEvent, Message as ChatMessage
        
        # Récupérer l'ID anonyme
        anonymous_id = f"Étudiant #{student.id}"
        if hasattr(student, 'student_profile') and student.student_profile.anonymous_id:
            anonymous_id = student.student_profile.anonymous_id
        
        now = timezone.now()
        
        # Créer la demande SANS IA (pour tester)
        health_request = HealthRequest.objects.create(
            id=uuid.uuid4(),
            student=student,
            anonymous_id=anonymous_id,
            ai_category=category,
            ai_confidence=85.0,
            ai_explanation="Message en attente d'analyse",
            ai_trace_id="",  # Vide pour l'instant
            status='pending',
            urgency_level='low',
            student_age_group=age_group,
            created_at=now,
            updated_at=now,
            closure_summary=''
        )
        
        # Créer le message
        ChatMessage.objects.create(
            health_request=health_request,
            sender=anonymous_id,
            sender_role='student',
            content=message,
            created_at=now
        )
        
        # Timeline
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='created',
            actor=anonymous_id,
            action=f"Ouverture de la demande par {anonymous_id}",
            created_at=now
        )
        
        return health_request
    
    def assign_counselor(self, request_id, counselor):
        from .models import HealthRequest, HealthTimelineEvent
        
        health_request = HealthRequest.objects.get(id=request_id)
        
        if health_request.status == 'pending':
            health_request.counselor = counselor
            health_request.status = 'in_progress'
            health_request.save()
            
            HealthTimelineEvent.objects.create(
                health_request=health_request,
                event_type='assigned',
                actor=f"Conseiller {counselor.username}",
                action=f"Prise en charge par {counselor.username}",
                created_at=timezone.now()
            )
        
        return health_request
    
    def close_request(self, request_id, counselor, summary: str = ""):
        from .models import HealthRequest, HealthTimelineEvent
        
        health_request = HealthRequest.objects.get(id=request_id)
        health_request.status = 'closed'
        health_request.closed_at = timezone.now()
        health_request.closure_summary = summary
        health_request.save()
        
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='closed',
            actor=f"Conseiller {counselor.username}",
            action="Demande clôturée",
            detail=summary,
            created_at=timezone.now()
        )
        
        return health_request
    
    def override_category(self, request_id, counselor, new_category: str):
        from .models import HealthRequest, HealthTimelineEvent, AuditLog
        
        health_request = HealthRequest.objects.get(id=request_id)
        old_category = health_request.get_effective_category()
        
        health_request.overridden_category = new_category
        health_request.overridden_by = counselor
        health_request.overridden_at = timezone.now()
        health_request.save()
        
        HealthTimelineEvent.objects.create(
            health_request=health_request,
            event_type='ia_override',
            actor=f"Conseiller {counselor.username}",
            action=f"Override catégorie: {old_category} → {new_category}",
            created_at=timezone.now()
        )
        
        AuditLog.objects.create(
            user=counselor,
            action='override_category',
            resource=str(health_request.id),
            details={'old_category': old_category, 'new_category': new_category},
            created_at=timezone.now()
        )
        
        return health_request
    
    def log_security_violation(self, user, request_id, ip_address, user_agent):
        from .models import AuditLog
        
        return AuditLog.objects.create(
            user=user,
            action='view_identity',
            resource=str(request_id),
            ip_address=ip_address,
            user_agent=user_agent,
            details={'attempt': 'view_real_identity', 'blocked': True},
            created_at=timezone.now()
        )