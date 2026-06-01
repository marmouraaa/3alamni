# audit/services.py
import logging
import json
from django.utils import timezone
from .models import AuditLog

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Récupérer l'adresse IP du client"""
    if not request:
        return None
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_action(user, action, result, reason=None, case_id=None, trace_id=None, request=None, extra_data=None):
    """
    Enregistrer une action dans les logs d'audit
    
    Args:
        user: Utilisateur Django (ou None)
        action: Action (une des constantes ACTION_CHOICES)
        result: Résultat (success, error, blocked, fallback, warning)
        reason: Raison/description
        case_id: Identifiant du cas (alerte_id, intervention_id, etc.)
        trace_id: Identifiant de traçabilité MCP
        request: Requête HTTP (pour IP et User-Agent)
        extra_data: Données additionnelles (dict)
    
    Returns:
        AuditLog instance or None
    """
    try:
        # Récupérer les informations de la requête
        ip_address = None
        user_agent = ''
        request_path = ''
        request_method = ''
        
        if request:
            ip_address = get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            request_path = request.path[:500]
            request_method = request.method
        
        # Créer le log
        audit_log = AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            result=result,
            reason=reason or '',
            case_id=case_id or '',
            trace_id=trace_id or '',
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            extra_data=extra_data or {},
        )
        
        # Log dans le fichier aussi
        log_level = logging.INFO if result == 'success' else logging.WARNING
        logger.log(
            log_level,
            f"[AUDIT] user={user.username if user else 'anonymous'} action={action} result={result} reason={reason} case_id={case_id}"
        )
        
        return audit_log
        
    except Exception as e:
        logger.error(f"[AUDIT] Erreur lors de l'enregistrement: {e}")
        return None


def log_error(user, action, error, request=None, case_id=None):
    """Raccourci pour logger une erreur"""
    return log_action(
        user=user,
        action=action,
        result='error',
        reason=str(error)[:500],
        case_id=case_id,
        request=request
    )


def log_success(user, action, reason=None, case_id=None, request=None):
    """Raccourci pour logger un succès"""
    return log_action(
        user=user,
        action=action,
        result='success',
        reason=reason,
        case_id=case_id,
        request=request
    )


def log_blocked(user, action, reason=None, case_id=None, request=None):
    """Raccourci pour logger un accès bloqué"""
    return log_action(
        user=user,
        action=action,
        result='blocked',
        reason=reason,
        case_id=case_id,
        request=request
    )


def log_fallback(user, action, reason=None, case_id=None, trace_id=None, request=None):
    """Raccourci pour logger un fallback MCP"""
    return log_action(
        user=user,
        action=action,
        result='fallback',
        reason=reason,
        case_id=case_id,
        trace_id=trace_id,
        request=request
    )