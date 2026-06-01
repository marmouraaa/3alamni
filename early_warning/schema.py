# early_warning/schema.py

import strawberry
from typing import List, Optional
from django.db.models import Count, Q, Avg
from django.core.exceptions import PermissionDenied
from .models import RiskScore, Alert, Intervention, AISuggestion, ThresholdConfig
from .mcp_services import mcp_ew_service
from .graphql_types import (
    RiskScoreType, AISuggestionType, AlertType, InterventionType,
    DashboardStatsType, MCPSuggestionResponse, CorrelationType,
    ClassStatsType
)
from datetime import datetime
import hashlib


# ========== GESTION DES PERMISSIONS ==========

def check_role(user, allowed_roles, action_name="operation", request=None):
    """
    Vérifier si l'utilisateur a le bon rôle.
    Lève une exception PermissionDenied si non autorisé.
    """
    if not user or not user.is_authenticated:
        try:
            from audit.services import log_action
            log_action(
                user=None,
                action=f'graphql_{action_name}_unauth',
                result='blocked',
                reason=f"Tentative non authentifiée sur {action_name}"
            )
        except ImportError:
            pass
        raise PermissionDenied("Authentication required")
    
    if not hasattr(user, 'role') or user.role not in allowed_roles:
        try:
            from audit.services import log_action
            log_action(
                user=user,
                action=f'graphql_{action_name}_unauthorized',
                result='blocked',
                reason=f"Rôle '{getattr(user, 'role', 'unknown')}' non autorisé pour {action_name}",
                request=request
            )
        except ImportError:
            pass
        raise PermissionDenied(f"Role '{getattr(user, 'role', 'unknown')}' not allowed. Required: {allowed_roles}")
    
    return True


def generate_trace_id(student_name, absences):
    """Générer un ID de trace cohérent pour le MCP"""
    data = f"{student_name}_{absences}_{datetime.now().timestamp()}"
    return f"ew_{hashlib.md5(data.encode()).hexdigest()[:8]}"


# ========== QUERIES ==========

@strawberry.type
class Query:
    """Query GraphQL pour Early Warning"""

    @strawberry.field
    def all_risk_scores(self, info: strawberry.Info, limit: Optional[int] = 100) -> List[RiskScoreType]:
        """Récupérer tous les scores de risque"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin', 'student'], 'all_risk_scores', info.context.request)
        
        queryset = RiskScore.objects.all().order_by('-risk_score')[:limit]
        return [
            RiskScoreType(
                id=r.id,
                student_name=r.student_name,
                student_id=r.student_id,
                class_name=r.class_name,
                absences=r.absences,
                avg_grade=r.avg_grade,
                behavior_score=r.behavior_score,
                risk_score=r.risk_score,
                risk_level=r.risk_level,
                created_at=r.created_at.isoformat()
            ) for r in queryset
        ]

    @strawberry.field
    def risk_score_by_student(self, info: strawberry.Info, student_id: str) -> Optional[RiskScoreType]:
        """Récupérer le score de risque d'un étudiant"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin', 'student', 'parent'], 'risk_score_by_student', info.context.request)
        
        try:
            r = RiskScore.objects.get(student_id=student_id)
            
            # Les parents ne voient que leurs propres enfants
            if hasattr(user, 'role') and user.role == 'parent':
                if not hasattr(user, 'children') or student_id not in user.children:
                    raise PermissionDenied("Vous ne pouvez voir que les notes de vos enfants")
            
            return RiskScoreType(
                id=r.id,
                student_name=r.student_name,
                student_id=r.student_id,
                class_name=r.class_name,
                absences=r.absences,
                avg_grade=r.avg_grade,
                behavior_score=r.behavior_score,
                risk_score=r.risk_score,
                risk_level=r.risk_level,
                created_at=r.created_at.isoformat()
            )
        except RiskScore.DoesNotExist:
            return None

    @strawberry.field
    def all_alerts(self, info: strawberry.Info, status: Optional[str] = None) -> List[AlertType]:
        """Récupérer toutes les alertes"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'all_alerts', info.context.request)
        
        queryset = Alert.objects.select_related('risk_score').all()
        if status:
            queryset = queryset.filter(status=status)
        
        return [
            AlertType(
                id=a.id,
                student_name=a.risk_score.student_name,
                risk_score=a.risk_score.risk_score,
                risk_level=a.risk_score.risk_level,
                message=a.message,
                status=a.status,
                has_ai_suggestion=a.ai_suggestion is not None,
                created_at=a.created_at.isoformat()
            ) for a in queryset.order_by('-created_at')
        ]

    @strawberry.field
    def pending_alerts(self, info: strawberry.Info) -> List[AlertType]:
        """Récupérer les alertes en attente"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'pending_alerts', info.context.request)
        
        queryset = Alert.objects.filter(status='pending').select_related('risk_score')
        return [
            AlertType(
                id=a.id,
                student_name=a.risk_score.student_name,
                risk_score=a.risk_score.risk_score,
                risk_level=a.risk_score.risk_level,
                message=a.message,
                status=a.status,
                has_ai_suggestion=a.ai_suggestion is not None,
                created_at=a.created_at.isoformat()
            ) for a in queryset.order_by('-created_at')
        ]

    @strawberry.field
    def my_interventions(self, info: strawberry.Info, status: Optional[str] = None) -> List[InterventionType]:
        """Récupérer les interventions"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'my_interventions', info.context.request)
        
        queryset = Intervention.objects.select_related('alert__risk_score', 'ai_suggestion').all()
        if status:
            queryset = queryset.filter(status=status)
        
        return [
            InterventionType(
                id=i.id,
                student_name=i.alert.risk_score.student_name,
                action_type=i.action_type,
                description=i.description,
                due_date=i.due_date.isoformat(),
                status=i.status,
                is_overdue=i.is_overdue(),
                created_at=i.created_at.isoformat()
            ) for i in queryset.order_by('-created_at')
        ]

    @strawberry.field
    def dashboard_stats(self, info: strawberry.Info) -> DashboardStatsType:
        """Statistiques du dashboard"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin', 'student'], 'dashboard_stats', info.context.request)
        
        total_students = RiskScore.objects.count()
        high_risk = RiskScore.objects.filter(risk_level='high').count()
        medium_risk = RiskScore.objects.filter(risk_level='medium').count()
        low_risk = RiskScore.objects.filter(risk_level='low').count()
        active_alerts = Alert.objects.filter(status='pending').count()
        
        interventions = Intervention.objects.all()
        completed = interventions.filter(status='completed').count()
        completion_rate = (completed / interventions.count() * 100) if interventions.count() > 0 else 0
        
        return DashboardStatsType(
            total_students=total_students,
            high_risk_count=high_risk,
            medium_risk_count=medium_risk,
            low_risk_count=low_risk,
            active_alerts=active_alerts,
            completion_rate=round(completion_rate, 1)
        )

    @strawberry.field
    def correlations(self, info: strawberry.Info) -> CorrelationType:
        """Calculer les corrélations entre facteurs"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'correlations', info.context.request)
        
        import pandas as pd
        
        risk_data = list(RiskScore.objects.all().values(
            'absences', 'avg_grade', 'behavior_score', 'risk_score'
        ))
        
        if len(risk_data) > 1:
            df = pd.DataFrame(risk_data)
            return CorrelationType(
                absences=round(df['absences'].corr(df['risk_score']), 2),
                avg_grade=round(df['avg_grade'].corr(df['risk_score']), 2),
                behavior_score=round(df['behavior_score'].corr(df['risk_score']), 2)
            )
        
        return CorrelationType(absences=0, avg_grade=0, behavior_score=0)

    @strawberry.field
    def class_statistics(self, info: strawberry.Info) -> List[ClassStatsType]:
        """Statistiques par classe"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'class_statistics', info.context.request)
        
        stats = []
        classes = RiskScore.objects.values_list('class_name', flat=True).distinct()
        
        for class_name in classes:
            qs = RiskScore.objects.filter(class_name=class_name)
            stats.append(ClassStatsType(
                class_name=class_name,
                total_students=qs.count(),
                avg_risk_score=round(qs.aggregate(Avg('risk_score'))['risk_score__avg'] or 0, 1),
                high_risk_count=qs.filter(risk_level='high').count()
            ))
        
        return sorted(stats, key=lambda x: x.avg_risk_score, reverse=True)


# ========== MUTATIONS ==========

@strawberry.type
class Mutation:
    """Mutation GraphQL pour Early Warning"""

    @strawberry.mutation
    def generate_ai_suggestion(
        self, 
        info: strawberry.Info,
        student_name: str,
        absences: int,
        avg_grade: float,
        behavior_score: int,
        risk_score: float,
        risk_level: str
    ) -> MCPSuggestionResponse:
        """
        Générer une suggestion IA via MCP (Groq)
        Utilise le service MCP pour appeler l'API Groq
        """
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'generate_ai_suggestion', info.context.request)
        
        # Générer un trace_id cohérent
        trace_id = generate_trace_id(student_name, absences)
        
        # Chercher un RiskScore existant pour un vrai ID
        existing_risk = RiskScore.objects.filter(student_name=student_name).first()
        
        # Créer un objet virtuel pour le service
        class RiskScoreMock:
            def __init__(self, data, existing=None):
                self.id = existing.id if existing else hash(f"{data['student_name']}_{data['absences']}") % 10000
                self.student_name = data['student_name']
                self.absences = data['absences']
                self.avg_grade = data['avg_grade']
                self.behavior_score = data['behavior_score']
                self.risk_score = data['risk_score']
                self.risk_level = data['risk_level']
        
        risk_mock = RiskScoreMock({
            'student_name': student_name,
            'absences': absences,
            'avg_grade': avg_grade,
            'behavior_score': behavior_score,
            'risk_score': risk_score,
            'risk_level': risk_level
        }, existing_risk)
        
        # Appeler le service MCP
        result = mcp_ew_service.suggest_intervention(risk_mock)
        
        # Remplacer le trace_id par celui qu'on a généré si c'est un fallback
        if result.get('fallback_used'):
            result['trace_id'] = trace_id
        
        # Log l'appel GraphQL
        try:
            from audit.services import log_action
            log_action(
                user=user,
                action='graphql_generate_suggestion',
                result='success' if not result['fallback_used'] else 'fallback',
                reason=f"Étudiant: {student_name}, score: {risk_score}, action: {result['action']}",
                case_id=result['trace_id'],
                request=info.context.request
            )
        except ImportError:
            pass
        
        return MCPSuggestionResponse(
            action=result['action'],
            description=result['description'],
            primary_factor=result['primary_factor'],
            secondary_factor=result['secondary_factor'],
            confidence=result['confidence'],
            explanation=result['explanation'],
            fallback_used=result['fallback_used'],
            trace_id=result['trace_id']
        )

    @strawberry.mutation
    def update_alert_status(self, info: strawberry.Info, alert_id: int, status: str) -> Optional[AlertType]:
        """Mettre à jour le statut d'une alerte"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'update_alert_status', info.context.request)
        
        # Valider le statut
        valid_statuses = ['pending', 'in_progress', 'resolved', 'ignored']
        if status not in valid_statuses:
            raise ValueError(f"Statut invalide. Choisir parmi: {valid_statuses}")
        
        try:
            alert = Alert.objects.select_related('risk_score').get(id=alert_id)
            old_status = alert.status
            alert.status = status
            alert.save()
            
            # Log la mise à jour
            try:
                from audit.services import log_action
                log_action(
                    user=user,
                    action='graphql_update_alert',
                    result='success',
                    reason=f"Alerte #{alert_id}: {old_status} → {status}",
                    case_id=str(alert_id),
                    request=info.context.request
                )
            except ImportError:
                pass
            
            return AlertType(
                id=alert.id,
                student_name=alert.risk_score.student_name,
                risk_score=alert.risk_score.risk_score,
                risk_level=alert.risk_score.risk_level,
                message=alert.message,
                status=alert.status,
                has_ai_suggestion=alert.ai_suggestion is not None,
                created_at=alert.created_at.isoformat()
            )
        except Alert.DoesNotExist:
            return None

    @strawberry.mutation
    def create_intervention(
        self,
        info: strawberry.Info,
        alert_id: int,
        action_type: str,
        description: str,
        due_date: str
    ) -> Optional[InterventionType]:
        """Créer une nouvelle intervention"""
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'create_intervention', info.context.request)
        
        # Valider le type d'action
        valid_actions = ['quiz', 'meeting', 'followup', 'counseling', 'custom']
        if action_type not in valid_actions:
            raise ValueError(f"Type d'action invalide. Choisir parmi: {valid_actions}")
        
        try:
            alert = Alert.objects.select_related('risk_score', 'ai_suggestion').get(id=alert_id)
            
            intervention = Intervention.objects.create(
                alert=alert,
                action_type=action_type,
                description=description,
                due_date=due_date,
                ai_suggestion=alert.ai_suggestion
            )
            
            # Mettre à jour le statut de l'alerte
            alert.status = 'in_progress'
            alert.save()
            
            # Log la création
            try:
                from audit.services import log_action
                log_action(
                    user=user,
                    action='graphql_create_intervention',
                    result='success',
                    reason=f"Intervention #{intervention.id} créée pour alerte #{alert_id}",
                    case_id=str(intervention.id),
                    request=info.context.request
                )
            except ImportError:
                pass
            
            return InterventionType(
                id=intervention.id,
                student_name=intervention.alert.risk_score.student_name,
                action_type=intervention.action_type,
                description=intervention.description,
                due_date=intervention.due_date.isoformat(),
                status=intervention.status,
                is_overdue=intervention.is_overdue(),
                created_at=intervention.created_at.isoformat()
            )
        except Alert.DoesNotExist:
            return None

    @strawberry.mutation
    def bulk_update_alerts(
        self,
        info: strawberry.Info,
        alert_ids: List[int],
        status: str
    ) -> int:
        """
        Mettre à jour plusieurs alertes en une seule mutation
        Retourne le nombre d'alertes mises à jour
        """
        user = info.context.request.user
        check_role(user, ['teacher', 'admin'], 'bulk_update_alerts', info.context.request)
        
        valid_statuses = ['pending', 'in_progress', 'resolved', 'ignored']
        if status not in valid_statuses:
            raise ValueError(f"Statut invalide. Choisir parmi: {valid_statuses}")
        
        updated = Alert.objects.filter(id__in=alert_ids).update(status=status)
        
        # Log la mise à jour groupée
        try:
            from audit.services import log_action
            log_action(
                user=user,
                action='graphql_bulk_update_alerts',
                result='success',
                reason=f"{updated} alertes mises à jour vers '{status}'",
                case_id=f"bulk_{status}_{len(alert_ids)}",
                request=info.context.request
            )
        except ImportError:
            pass
        
        return updated


# Créer le schema
schema = strawberry.Schema(query=Query, mutation=Mutation)