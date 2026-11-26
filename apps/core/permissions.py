from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import UserRole


def role_required(allowed_roles, module_name="requested module"):
    """Decorator to enforce that authenticated user has one of the allowed roles."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            allowed_names = [str(dict(UserRole.choices).get(r, r)) for r in allowed_roles]
            user_role_name = request.user.get_role_display() if hasattr(request.user, 'get_role_display') else str(request.user.role)
            raise PermissionDenied(
                f"Access restricted. You are logged in as '{user_role_name}', but access to {module_name} "
                f"requires authorization for: {', '.join(allowed_names)}."
            )
        return _wrapped_view
    return decorator


def salesman_only(view_func):
    """Allowed for Salesmen, Factory Admin, and Owner."""
    return role_required(
        [UserRole.SALESMAN, UserRole.FACTORY_ADMIN, UserRole.OWNER],
        module_name="sales order entry"
    )(view_func)


def admin_only(view_func):
    """Allowed for Factory Admin and Owner only."""
    return role_required(
        [UserRole.FACTORY_ADMIN, UserRole.OWNER],
        module_name="administrative and financial management"
    )(view_func)


def inventory_read_access(view_func):
    """
    Allowed for Production Supervisor, Accountant/Auditor, Factory Admin, and Owner.
    Provides read visibility into stock balances, movement ledger, and goods receipt history.
    """
    return role_required(
        [UserRole.PRODUCTION_SUPERVISOR, UserRole.ACCOUNTANT_AUDITOR, UserRole.FACTORY_ADMIN, UserRole.OWNER],
        module_name="inventory balances, ledger and receipts"
    )(view_func)


def production_execution_only(view_func):
    """
    Allowed for Production Supervisor, Factory Admin, and Owner.
    Restricted from Accountant/Auditor and Salesman to prevent unauthorized manufacturing batches or recipe edits.
    """
    return role_required(
        [UserRole.PRODUCTION_SUPERVISOR, UserRole.FACTORY_ADMIN, UserRole.OWNER],
        module_name="manufacturing recipe creation and batch execution"
    )(view_func)


# Backward-compatible alias
production_only = production_execution_only


def production_view_access(view_func):
    """
    Allowed for Production Supervisor, Accountant/Auditor, Factory Admin, and Owner.
    Provides view visibility into production hub, BOM recipes, runs, and yield variance records.
    """
    return role_required(
        [UserRole.PRODUCTION_SUPERVISOR, UserRole.ACCOUNTANT_AUDITOR, UserRole.FACTORY_ADMIN, UserRole.OWNER],
        module_name="production monitoring and batch records"
    )(view_func)


def audit_or_admin(view_func):
    """Allowed for Accountant/Auditor, Factory Admin, and Owner."""
    return role_required(
        [UserRole.ACCOUNTANT_AUDITOR, UserRole.FACTORY_ADMIN, UserRole.OWNER],
        module_name="financial compliance, audit reports, and billing"
    )(view_func)


def owner_dashboard_access(view_func):
    """Allowed for Owner, Factory Admin, and Accountant/Auditor."""
    return role_required(
        [UserRole.OWNER, UserRole.FACTORY_ADMIN, UserRole.ACCOUNTANT_AUDITOR],
        module_name="executive management dashboard"
    )(view_func)
