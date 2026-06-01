# early_warning/graphql_types.py

import strawberry
from typing import List, Optional
from datetime import datetime


@strawberry.type
class RiskScoreType:
    """Type GraphQL pour RiskScore"""
    id: int
    student_name: str
    student_id: str
    class_name: str
    absences: int
    avg_grade: float
    behavior_score: int
    risk_score: float
    risk_level: str
    created_at: str


@strawberry.type
class AISuggestionType:
    """Type GraphQL pour AISuggestion"""
    id: int
    suggested_action: str
    description: str
    explanation_primary_factor: str
    explanation_secondary_factor: str
    confidence: float
    fallback_used: bool
    created_at: str


@strawberry.type
class AlertType:
    """Type GraphQL pour Alert"""
    id: int
    student_name: str
    risk_score: float
    risk_level: str
    message: str
    status: str
    has_ai_suggestion: bool
    created_at: str


@strawberry.type
class InterventionType:
    """Type GraphQL pour Intervention"""
    id: int
    student_name: str
    action_type: str
    description: str
    due_date: str
    status: str
    is_overdue: bool
    created_at: str


@strawberry.type
class DashboardStatsType:
    """Type GraphQL pour les statistiques du dashboard"""
    total_students: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    active_alerts: int
    completion_rate: float


@strawberry.type
class MCPSuggestionInput:
    """Input pour la suggestion MCP"""
    student_name: str
    absences: int
    avg_grade: float
    behavior_score: int
    risk_score: float
    risk_level: str


@strawberry.type
class MCPSuggestionResponse:
    """Réponse de la suggestion MCP"""
    action: str
    description: str
    primary_factor: str
    secondary_factor: str
    confidence: float
    explanation: str
    fallback_used: bool
    trace_id: str


@strawberry.type
class CorrelationType:
    """Type pour les corrélations"""
    absences: float
    avg_grade: float
    behavior_score: float


@strawberry.type
class ClassStatsType:
    """Type pour les statistiques par classe"""
    class_name: str
    total_students: int
    avg_risk_score: float
    high_risk_count: int