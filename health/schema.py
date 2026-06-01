# health/schema.py
import strawberry
from strawberry.types import Info
from typing import List, Optional
from datetime import datetime
from django.contrib.auth import get_user_model

User = get_user_model()

# ========== TYPES GRAPHQL ==========

@strawberry.type
class HealthRequestType:
    id: str
    anonymous_id: str
    ai_category: str
    ai_confidence: float
    ai_explanation: str
    effective_category: str
    effective_category_display: str
    status: str
    urgency_level: str
    created_at: datetime
    closed_at: Optional[datetime]
    message_preview: str


@strawberry.type
class MessageType:
    id: str
    sender: str
    sender_role: str
    content: str
    created_at: datetime


@strawberry.type
class TimelineEventType:
    event_type: str
    actor: str
    action: str
    detail: str
    created_at: datetime


@strawberry.type
class HealthStatsType:
    pending_count: int
    in_progress_count: int
    closed_count: int
    total_count: int


@strawberry.type
class CategoryStatType:
    category: str
    label: str
    count: int


@strawberry.input
class CloseRequestInput:
    summary: str = ""


@strawberry.type
class HealthMutationResult:
    success: bool
    message: str
    request_id: Optional[str]


# ========== RESOLVERS ==========

def get_health_requests(status: Optional[str] = None, info: Info = None) -> List[HealthRequestType]:
    from .models import HealthRequest
    
    user = info.context.request.user
    
    if not user.is_authenticated:
        raise Exception("Authentification requise")
    
    if user.role not in ['counselor', 'admin']:
        raise Exception("Permission refusée: accès réservé aux conseillers")
    
    if status:
        requests = HealthRequest.objects.filter(status=status).order_by('-created_at')
    else:
        requests = HealthRequest.objects.all().order_by('-created_at')
    
    result = []
    for req in requests[:50]:
        first_message = req.messages.first()
        message_preview = first_message.content[:100] if first_message else ""
        
        result.append(HealthRequestType(
            id=str(req.id),
            anonymous_id=req.anonymous_id,
            ai_category=req.ai_category,
            ai_confidence=req.ai_confidence,
            ai_explanation=req.ai_explanation,
            effective_category=req.get_effective_category(),
            effective_category_display=req.get_effective_category_display(),
            status=req.status,
            urgency_level=req.urgency_level,
            created_at=req.created_at,
            closed_at=req.closed_at,
            message_preview=message_preview
        ))
    
    return result


def get_health_stats(info: Info) -> HealthStatsType:
    from .models import HealthRequest
    
    user = info.context.request.user
    
    if not user.is_authenticated:
        raise Exception("Authentification requise")
    
    if user.role not in ['counselor', 'admin']:
        raise Exception("Permission refusée")
    
    return HealthStatsType(
        pending_count=HealthRequest.objects.filter(status='pending').count(),
        in_progress_count=HealthRequest.objects.filter(status='in_progress').count(),
        closed_count=HealthRequest.objects.filter(status='closed').count(),
        total_count=HealthRequest.objects.count()
    )


def get_category_stats(info: Info) -> List[CategoryStatType]:
    from .models import HealthRequest
    from django.db.models import Q
    
    user = info.context.request.user
    
    if not user.is_authenticated:
        raise Exception("Authentification requise")
    
    if user.role not in ['counselor', 'admin']:
        raise Exception("Permission refusée")
    
    categories = [
        ('stress', '😰 Stress'),
        ('anxiety', '🌪️ Anxiété'),
        ('family', '👨‍👩‍👧 Famille'),
        ('school', '📚 École'),
        ('other', '💬 Autre')
    ]
    
    result = []
    for cat_code, cat_label in categories:
        count = HealthRequest.objects.filter(
            Q(overridden_category=cat_code) | 
            Q(overridden_category__isnull=True, ai_category=cat_code)
        ).count()
        
        result.append(CategoryStatType(
            category=cat_code,
            label=cat_label,
            count=count
        ))
    
    return result


def close_health_request(request_id: str, input_data: CloseRequestInput, info: Info) -> HealthMutationResult:
    from .models import HealthRequest
    from .services import HealthService
    
    user = info.context.request.user
    
    if not user.is_authenticated:
        return HealthMutationResult(success=False, message="Authentification requise", request_id=None)
    
    if user.role not in ['counselor', 'admin']:
        return HealthMutationResult(success=False, message="Permission refusée", request_id=None)
    
    try:
        service = HealthService()
        health_request = service.close_request(request_id, user, input_data.summary)
        return HealthMutationResult(success=True, message="Demande clôturée", request_id=str(health_request.id))
    except Exception as e:
        return HealthMutationResult(success=False, message=str(e), request_id=None)


def override_health_category(request_id: str, new_category: str, info: Info) -> HealthMutationResult:
    from .services import HealthService
    
    user = info.context.request.user
    
    if not user.is_authenticated:
        return HealthMutationResult(success=False, message="Authentification requise", request_id=None)
    
    if user.role not in ['counselor', 'admin']:
        return HealthMutationResult(success=False, message="Permission refusée", request_id=None)
    
    valid_categories = ['stress', 'family', 'school', 'anxiety', 'other']
    if new_category not in valid_categories:
        return HealthMutationResult(success=False, message="Catégorie invalide", request_id=None)
    
    try:
        service = HealthService()
        health_request = service.override_category(request_id, user, new_category)
        return HealthMutationResult(success=True, message="Catégorie modifiée", request_id=str(health_request.id))
    except Exception as e:
        return HealthMutationResult(success=False, message=str(e), request_id=None)


# ========== QUERY ET MUTATION ==========

@strawberry.type
class Query:
    health_requests: List[HealthRequestType] = strawberry.field(resolver=get_health_requests)
    health_stats: HealthStatsType = strawberry.field(resolver=get_health_stats)
    category_stats: List[CategoryStatType] = strawberry.field(resolver=get_category_stats)


@strawberry.type
class Mutation:
    close_health_request: HealthMutationResult = strawberry.mutation(resolver=close_health_request)
    override_health_category: HealthMutationResult = strawberry.mutation(resolver=override_health_category)


# Schéma principal
schema = strawberry.Schema(query=Query, mutation=Mutation)