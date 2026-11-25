from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from apps.core.permissions import production_only, audit_or_admin
from .models import BillOfMaterials, BOMComponent, ProductionRun, ProductionConsumption, ProductionRunStatus
from .services import ProductionService
from apps.inventory.models import InventoryItem, ItemType
from apps.master_data.models import Product


@login_required
@production_only
def production_dashboard(request):
    raw_materials = InventoryItem.objects.filter(item_type=ItemType.RAW_MATERIAL)
    packaging = InventoryItem.objects.filter(item_type=ItemType.PACKAGING)
    finished_goods = InventoryItem.objects.filter(item_type=ItemType.FINISHED_GOOD)

    boms = BillOfMaterials.objects.filter(is_active=True).select_related('product')
    recent_runs = ProductionRun.objects.select_related('product', 'bom', 'supervisor').order_by('-production_date', '-id')[:8]

    # Alerts
    variance_alerts = ProductionRun.objects.filter(yield_variance_flagged=True).order_by('-production_date')[:5]

    return render(request, 'production/dashboard.html', {
        'raw_materials': raw_materials,
        'packaging': packaging,
        'finished_goods': finished_goods,
        'boms': boms,
        'recent_runs': recent_runs,
        'variance_alerts': variance_alerts,
    })


@login_required
@production_only
def bom_list(request):
    boms = BillOfMaterials.objects.select_related('product').prefetch_related('components__item', 'components__unit').all()
    return render(request, 'production/bom_list.html', {'boms': boms})


@login_required
@production_only
def bom_detail(request, pk):
    bom = get_object_or_404(BillOfMaterials.objects.prefetch_related('components__item', 'components__unit'), pk=pk)
    return render(request, 'production/bom_detail.html', {'bom': bom})


@login_required
@production_only
def production_run_list(request):
    runs = ProductionRun.objects.select_related('product', 'bom', 'supervisor').order_by('-production_date', '-id')
    return render(request, 'production/run_list.html', {'runs': runs})


@login_required
@production_only
def production_run_create(request):
    boms = BillOfMaterials.objects.filter(is_active=True).select_related('product')
    selected_bom = boms.first()

    bom_id = request.GET.get('bom_id')
    if bom_id:
        selected_bom = get_object_or_404(BillOfMaterials, id=bom_id)

    if request.method == 'POST':
        try:
            bom = get_object_or_404(BillOfMaterials, id=request.POST.get('bom'))
            product = bom.product
            batch_size = Decimal(request.POST.get('batch_size', '1.0'))
            p_date = request.POST.get('production_date', timezone.now().date())

            actual_good_output = Decimal(request.POST.get('actual_good_output'))
            damaged_pouches = Decimal(request.POST.get('damaged_pouches', '0'))
            cartons_used = Decimal(request.POST.get('cartons_used', '0'))
            labour_cost = Decimal(request.POST.get('labour_cost', '0'))
            gas_power_cost = Decimal(request.POST.get('gas_power_cost', '0'))
            notes = request.POST.get('notes', '')

            # Extract actual quantities for components
            consumptions_data = {}
            for comp in bom.components.filter(is_packaging=False):
                field_name = f"actual_qty_{comp.item.id}"
                if field_name in request.POST:
                    consumptions_data[comp.item.id] = Decimal(request.POST.get(field_name))

            count = ProductionRun.objects.count() + 1
            run_number = f"PR-2627-{count:04d}"

            run = ProductionRun.objects.create(
                run_number=run_number,
                product=product,
                bom=bom,
                batch_size=batch_size,
                production_date=p_date,
                supervisor=request.user,
                expected_output=bom.expected_output_packets * batch_size,
                actual_good_output=actual_good_output,
                notes=notes
            )

            ProductionService.complete_run(
                production_run=run,
                raw_materials_consumed=consumptions_data,
                actual_good_output=actual_good_output,
                damaged_pouches=damaged_pouches,
                cartons_used=cartons_used,
                labour_cost=labour_cost,
                gas_power_cost=gas_power_cost,
                user=request.user
            )

            messages.success(
                request,
                f"Production Run {run.run_number} completed successfully! "
                f"Produced: {run.actual_good_output} packets @ ₹{run.cost_per_good_packet:.2f}/pkt."
            )
            return redirect('production:run_detail', pk=run.id)

        except Exception as e:
            messages.error(request, f"Production Run Failed: {e}")

    return render(request, 'production/run_create.html', {
        'boms': boms,
        'selected_bom': selected_bom
    })


@login_required
@audit_or_admin
def production_run_detail(request, pk):
    run = get_object_or_404(
        ProductionRun.objects.select_related('product', 'bom', 'supervisor').prefetch_related('consumptions__item', 'consumptions__unit'),
        pk=pk
    )
    raw_consumptions = run.consumptions.filter(is_packaging=False)
    pkg_consumptions = run.consumptions.filter(is_packaging=True)

    return render(request, 'production/run_detail.html', {
        'run': run,
        'raw_consumptions': raw_consumptions,
        'pkg_consumptions': pkg_consumptions
    })
