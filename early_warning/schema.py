# early_warning/schema.py

import strawberry
from typing import List, Optional
from django.db.models import Count, Q, Avg
from .models import RiskScore, Alert, Intervention, AISuggestion, ThresholdConfig
from .mcp_services import mcp_ew_service
from .graphql_types import (
    RiskScoreType, AISuggestionType, AlertType, InterventionType,
    DashboardStatsType, MCPSuggestionResponse, CorrelationType,
    ClassStatsType
)
from datetime import datetime


@strawberry.type
class Query:
    """Query GraphQL pour Early Warning"""

    @strawberry.field
    def all_risk_scores(self, limit: Optional[int] = 100) -> List[RiskScoreType]:
        """Récupérer tous les scores de risque"""
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
    def risk_score_by_student(self, student_id: str) -> Optional[RiskScoreType]:
        """Récupérer le score de risque d'un étudiant"""
        try:
            r = RiskScore.objects.get(student_id=student_id)
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
    def all_alerts(self, status: Optional[str] = None) -> List[AlertType]:
        """Récupérer toutes les alertes"""
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
    def pending_alerts(self) -> List[AlertType]:
        """Récupérer les alertes en attente"""
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
    def my_interventions(self, status: Optional[str] = None) -> List[InterventionType]:
        """Récupérer les interventions"""
        queryset = Intervention.objects.select_related('alert__risk_score').all()
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
    def dashboard_stats(self) -> DashboardStatsType:
        """Statistiques du dashboard"""
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
    def correlations(self) -> CorrelationType:
        """Calculer les corrélations entre facteurs"""
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
    def class_statistics(self) -> List[ClassStatsType]:
        """Statistiques par classe"""
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


@strawberry.type
class Mutation:
    """Mutation GraphQL pour Early Warning"""

    @strawberry.mutation
    def generate_ai_suggestion(
        self, 
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
        # Créer un objet virtuel pour le service
        class RiskScoreMock:
            def __init__(self, data):
                self.id = 999
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
        })
        
        # Appeler le service MCP (version synchrone)
        result = mcp_ew_service.suggest_intervention(risk_mock)
        
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
    def update_alert_status(self, alert_id: int, status: str) -> Optional[AlertType]:
        """Mettre à jour le statut d'une alerte"""
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.status = status
            alert.save()
            
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
        alert_id: int,
        action_type: str,
        description: str,
        due_date: str
    ) -> Optional[InterventionType]:
        """Créer une nouvelle intervention"""
        try:
            alert = Alert.objects.get(id=alert_id)
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


# Créer le schema
schema = strawberry.Schema(query=Query, mutation=Mutation)