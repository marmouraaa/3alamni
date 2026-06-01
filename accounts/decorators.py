from functools import wraps
from django.core.exceptions import PermissionDenied
from audit.services import log_action

def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.path)
            
            if request.user.role not in roles:
                log_action(
                    user=request.user,
                    action=f"access_{view_func.__name__}",
                    result="blocked",
                    reason=f"Role '{request.user.role}' not allowed. Required: {roles}",
                    request=request
                )
                raise PermissionDenied
            
            log_action(
                user=request.user,
                action=f"access_{view_func.__name__}",
                result="success",
                request=request
            )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator