# early_warning/services.py

import hashlib
import logging
from datetime import datetime

from .models import RiskScore, AISuggestion, ThresholdConfig

logger = logging.getLogger(__name__)


class RiskScoringService:
    """
    Calcule le score de risque d'un étudiant selon la formule pondérée.
    """

    def calculate_risk_score(
        self, student_name, student_id, class_name,
        absences, avg_grade, behavior_score
    ):
        config = ThresholdConfig.get_config()

        # Sous-scores (max 40 pour absence, 40 pour note, 20 pour comportement)
        absence_s = min(absences * 2, 40)
        grade_s = max((20 - avg_grade) * 2, 0)
        behavior_s = max((10 - behavior_score) * 2, 0)

        # Pondération
        w_abs = (absence_s * config.absence_weight) / 40
        w_grd = (grade_s * config.grade_weight) / 40
        w_beh = (behavior_s * config.behavior_weight) / 20

        score = w_abs + w_grd + w_beh

        # Niveau
        if score >= config.high_risk_threshold:
            level = 'high'
        elif score >= config.medium_risk_threshold:
            level = 'medium'
        else:
            level = 'low'

        obj, created = RiskScore.objects.update_or_create(
            student_id=str(student_id),
            defaults={
                'student_name': student_name,
                'class_name': class_name,
                'absences': absences,
                'avg_grade': avg_grade,
                'behavior_score': behavior_score,
                'risk_score': round(score, 2),
                'risk_level': level,
            }
        )

        action = "Créé" if created else "Mis à jour"
        logger.debug(
            f"[RiskScoring] {action}: {student_name} "
            f"score={score:.1f} level={level}"
        )
        return obj


class TransformersAIService:
    """
    Service IA pour générer les suggestions d'intervention.
    Utilise Groq via MCPEarlyWarningService.
    Fallback déterministe automatique.
    """

    def get_ai_suggestion(self, risk_score_obj):
        from .mcp_services import mcp_ew_service

        result = mcp_ew_service.suggest_intervention(risk_score_obj)
        fallback = result.get('fallback_used', True)
        trace_id = result.get('trace_id', '')

        ai_suggestion = AISuggestion.objects.create(
            suggested_action=result['action'],
            description=result['description'],
            explanation_primary_factor=result['primary_factor'],
            explanation_secondary_factor=result.get('secondary_factor', ''),
            explanation_basis=result['basis'],
            confidence=result['confidence'],
            trace_id=trace_id,
            fallback_used=fallback,
        )

        logger.info(
            f"[AIService] Suggestion créée: #{ai_suggestion.id} "
            f"action={ai_suggestion.suggested_action} "
            f"fallback={fallback}"
        )
        return ai_suggestion

    def _generate_trace_id(self, risk_score_obj):
        data = f"{risk_score_obj.id}{risk_score_obj.student_id}{datetime.now()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]


class NotificationService:
    """Service de notifications email (à implémenter)"""

    def send_alert_email(self, recipient_email, alert):
        logger.info(
            f"[EMAIL] Alerte #{alert.id} pour "
            f"{alert.risk_score.student_name} → {recipient_email}"
        )
        return True