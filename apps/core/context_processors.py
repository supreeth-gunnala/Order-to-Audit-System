from django.conf import settings
from .models import UserRole

def global_context(request):
    """Provides application-wide constants and user role flags to templates."""
    context = {
        'APP_NAME': 'Sri Krishna Food Products - Order to Audit ERP',
        'FACTORY_NAME': getattr(settings, 'FACTORY_NAME', 'Sri Krishna Food Products'),
        'FACTORY_STATE': getattr(settings, 'FACTORY_STATE', 'Tamil Nadu'),
        'FACTORY_GSTIN': getattr(settings, 'FACTORY_GSTIN', '33AAAAA0000A1Z5'),
        'VARIANCE_TOLERANCE_PERCENT': getattr(settings, 'VARIANCE_TOLERANCE_PERCENT', 3.0),
        'UserRole': UserRole,
    }
    if request.user.is_authenticated:
        context['user_role'] = request.user.role
        context['is_salesman'] = request.user.is_salesman
        context['is_admin'] = request.user.is_admin
        context['is_production_supervisor'] = request.user.is_production_supervisor
        context['is_auditor'] = request.user.is_auditor
        context['is_owner'] = request.user.is_owner
    return context
