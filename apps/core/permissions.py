from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from .models import UserRole


def role_required(allowed_roles):
    """Decorator to enforce that authenticated user has one of the allowed roles."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have authorization to access this manufacturing module.")
        return _wrapped_view
    return decorator


def salesman_only(view_func):
    return role_required([UserRole.SALESMAN, UserRole.FACTORY_ADMIN])(view_func)

def admin_only(view_func):
    return role_required([UserRole.FACTORY_ADMIN, UserRole.OWNER])(view_func)

def production_only(view_func):
    return role_required([UserRole.PRODUCTION_SUPERVISOR, UserRole.FACTORY_ADMIN, UserRole.OWNER])(view_func)

def audit_or_admin(view_func):
    return role_required([UserRole.ACCOUNTANT_AUDITOR, UserRole.FACTORY_ADMIN, UserRole.OWNER])(view_func)

def owner_dashboard_access(view_func):
    return role_required([UserRole.OWNER, UserRole.FACTORY_ADMIN, UserRole.ACCOUNTANT_AUDITOR])(view_func)
