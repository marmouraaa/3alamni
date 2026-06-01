from .models import AuditLog

def log_action(user, action, result, case_id=None, reason=None, request=None):
    ip = None
    if request:
        ip = request.META.get('REMOTE_ADDR')
    
    AuditLog.objects.create(
        user=user,
        role=user.role if user and not user.is_anonymous else 'anonymous',
        action=action,
        case_id=case_id,
        result=result,
        reason=reason,
        ip_address=ip
    )