from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from .models import User, UserRole, AuditLog
from .permissions import role_required, owner_dashboard_access, admin_only
from apps.sales.models import SalesOrder, Invoice, InvoiceStatus, OrderStatus
from apps.inventory.models import InventoryItem, ItemType
from apps.production.models import ProductionRun


def user_login(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard_router')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username} ({user.get_role_display()})!")
            return redirect('core:dashboard_router')
        else:
            messages.error(request, "Invalid username or password. Please use the seeded demo credentials.")

    return render(request, 'core/login.html')


@login_required
def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out securely.")
    return redirect('core:login')


@login_required
def dashboard_router(request):
    """Directs user to their role-specific dashboard."""
    role = request.user.role
    if role == UserRole.SALESMAN:
        return redirect('sales:salesman_dashboard')
    elif role == UserRole.PRODUCTION_SUPERVISOR:
        return redirect('production:dashboard')
    elif role == UserRole.ACCOUNTANT_AUDITOR:
        return redirect('reports:auditor_dashboard')
    elif role in [UserRole.FACTORY_ADMIN, UserRole.OWNER] or request.user.is_superuser:
        return redirect('core:owner_dashboard')
    return redirect('core:owner_dashboard')


@login_required
@owner_dashboard_access
def owner_dashboard(request):
    today = timezone.now().date()
    
    # 1. Sales & Orders KPIs
    today_orders = SalesOrder.objects.filter(order_date__date=today)
    today_orders_count = today_orders.count()
    today_orders_value = today_orders.aggregate(s=Sum('total_amount'))['s'] or 0

    pending_orders = SalesOrder.objects.filter(status=OrderStatus.SUBMITTED)
    pending_orders_count = pending_orders.count()

    approved_orders_count = SalesOrder.objects.filter(status=OrderStatus.APPROVED).count()
    dispatched_orders_count = SalesOrder.objects.filter(status=OrderStatus.DISPATCHED).count()

    # 2. Inventory Balances
    rm_items = InventoryItem.objects.filter(item_type=ItemType.RAW_MATERIAL)
    pkg_items = InventoryItem.objects.filter(item_type=ItemType.PACKAGING)
    fg_items = InventoryItem.objects.filter(item_type=ItemType.FINISHED_GOOD)

    rm_value = sum(i.total_stock_value for i in rm_items)
    pkg_value = sum(i.total_stock_value for i in pkg_items)
    fg_value = sum(i.total_stock_value for i in fg_items)

    # 3. Production & Variances
    total_runs = ProductionRun.objects.count()
    variance_alert_runs = ProductionRun.objects.filter(
        Q(yield_variance_flagged=True) | Q(consumptions__variance_flagged=True)
    ).distinct()
    variance_alerts_count = variance_alert_runs.count()

    latest_run = ProductionRun.objects.order_by('-production_date', '-id').first()
    latest_cost_per_pkt = latest_run.cost_per_good_packet if latest_run else 0

    # 4. Receivables & Payments
    unpaid_invoices = Invoice.objects.filter(~Q(status=InvoiceStatus.CANCELLED))
    total_receivables = unpaid_invoices.aggregate(s=Sum('outstanding_amount'))['s'] or 0
    total_sales_invoiced = unpaid_invoices.aggregate(s=Sum('total_amount'))['s'] or 0
    total_collected = unpaid_invoices.aggregate(s=Sum('paid_amount'))['s'] or 0

    # 5. Recent Transactions & Audits
    recent_orders = SalesOrder.objects.select_related('customer', 'salesman').order_by('-order_date')[:6]
    recent_runs = ProductionRun.objects.select_related('product', 'supervisor').order_by('-production_date', '-id')[:5]
    recent_audits = AuditLog.objects.select_related('user').order_by('-timestamp')[:8]

    context = {
        'today_orders_count': today_orders_count,
        'today_orders_value': today_orders_value,
        'pending_orders_count': pending_orders_count,
        'approved_orders_count': approved_orders_count,
        'dispatched_orders_count': dispatched_orders_count,
        'rm_items': rm_items,
        'pkg_items': pkg_items,
        'fg_items': fg_items,
        'rm_value': rm_value,
        'pkg_value': pkg_value,
        'fg_value': fg_value,
        'total_inventory_value': rm_value + pkg_value + fg_value,
        'total_runs': total_runs,
        'variance_alerts_count': variance_alerts_count,
        'latest_cost_per_pkt': latest_cost_per_pkt,
        'total_receivables': total_receivables,
        'total_sales_invoiced': total_sales_invoiced,
        'total_collected': total_collected,
        'recent_orders': recent_orders,
        'recent_runs': recent_runs,
        'recent_audits': recent_audits,
    }
    return render(request, 'core/owner_dashboard.html', context)


@login_required
@admin_only
def audit_trail(request):
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')
    action = request.GET.get('action')
    entity = request.GET.get('entity')
    if action:
        logs = logs.filter(action__icontains=action)
    if entity:
        logs = logs.filter(entity__icontains=entity)

    return render(request, 'core/audit_trail.html', {'logs': logs[:200], 'action': action, 'entity': entity})


def permission_denied_view(request, exception=None):
    """Custom HTTP 403 Forbidden handler providing clear business context."""
    return render(request, '403.html', {'exception': str(exception) if exception else None}, status=403)

