import math
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from apps.core.permissions import production_execution_only, production_view_access
from .models import BillOfMaterials, BOMComponent, ProductionRun, ProductionConsumption, ProductionRunStatus
from .services import ProductionService
from apps.inventory.models import InventoryItem, ItemType
from apps.master_data.models import Product, UnitOfMeasure
from apps.sales.models import SalesOrderItem, OrderStatus


@login_required
@production_view_access
def production_dashboard(request):
    raw_materials = InventoryItem.objects.filter(item_type=ItemType.RAW_MATERIAL)
    packaging = InventoryItem.objects.filter(item_type=ItemType.PACKAGING)
    finished_goods = InventoryItem.objects.filter(item_type=ItemType.FINISHED_GOOD)

    boms = BillOfMaterials.objects.filter(is_active=True).select_related('product')
    recent_runs = ProductionRun.objects.select_related('product', 'bom', 'supervisor').order_by('-production_date', '-id')[:8]

    # Alerts
    variance_alerts = ProductionRun.objects.filter(yield_variance_flagged=True).order_by('-production_date')[:5]

    # Stretch Goal: Production Planning from Pending Sales Orders
    pending_items = SalesOrderItem.objects.filter(
        order__status__in=[OrderStatus.SUBMITTED, OrderStatus.APPROVED]
    ).values('product__id', 'product__name').annotate(
        total_ordered=Sum('quantity')
    )

    production_plan = []
    for pi in pending_items:
        prod_id = pi['product__id']
        prod_name = pi['product__name']
        ordered_qty = pi['total_ordered'] or Decimal('0.00')

        fg = InventoryItem.objects.filter(linked_product_id=prod_id).first()
        avail_stock = fg.current_stock if fg else Decimal('0.00')
        net_shortage = max(Decimal('0.00'), ordered_qty - avail_stock)

        active_bom = BillOfMaterials.objects.filter(product_id=prod_id, is_active=True).first()
        batch_yield = active_bom.expected_output_packets if active_bom else Decimal('200.00')

        if net_shortage > Decimal('0.00'):
            batches_needed = math.ceil(float(net_shortage) / float(batch_yield))
        else:
            batches_needed = 0

        production_plan.append({
            'product_name': prod_name,
            'ordered_qty': ordered_qty,
            'avail_stock': avail_stock,
            'net_shortage': net_shortage,
            'batch_yield': batch_yield,
            'batches_needed': batches_needed,
            'bom_id': active_bom.id if active_bom else None,
            'advice': f"To fulfil pending orders ({ordered_qty:.0f} pkts needed, {avail_stock:.0f} in stock), produce {batches_needed} batch(es)." if batches_needed > 0 else "Sufficient finished goods available in inventory."
        })

    return render(request, 'production/dashboard.html', {
        'raw_materials': raw_materials,
        'packaging': packaging,
        'finished_goods': finished_goods,
        'boms': boms,
        'recent_runs': recent_runs,
        'variance_alerts': variance_alerts,
        'production_plan': production_plan,
    })


@login_required
@production_view_access
def bom_list(request):
    boms = BillOfMaterials.objects.select_related('product').prefetch_related('components__item', 'components__unit').all()
    return render(request, 'production/bom_list.html', {'boms': boms})


@login_required
@production_execution_only
def bom_create(request):
    products = Product.objects.filter(is_active=True)
    items = InventoryItem.objects.filter(is_active=True).select_related('uom')
    uoms = UnitOfMeasure.objects.all()

    if request.method == 'POST':
        try:
            product_id = request.POST.get('product')
            product = get_object_or_404(Product, id=product_id)
            name = request.POST.get('name', f"{product.name} Standard Formulation")
            expected_output = Decimal(request.POST.get('expected_output', '200.00'))
            notes = request.POST.get('notes', '')

            existing_count = BillOfMaterials.objects.filter(product=product).count()
            version = existing_count + 1

            bom = BillOfMaterials.objects.create(
                product=product,
                version=version,
                name=name,
                expected_output_packets=expected_output,
                notes=notes,
                is_active=True
            )

            item_ids = request.POST.getlist('component_item')
            quantities = request.POST.getlist('component_qty')

            for itm_id, qty_str in zip(item_ids, quantities):
                if itm_id and qty_str:
                    qty = Decimal(qty_str)
                    if qty > Decimal('0'):
                        inv_item = get_object_or_404(InventoryItem, id=itm_id)
                        BOMComponent.objects.create(
                            bom=bom,
                            item=inv_item,
                            quantity=qty,
                            unit=inv_item.uom,
                            is_packaging=(inv_item.item_type == ItemType.PACKAGING),
                            standard_rate=inv_item.weighted_avg_cost
                        )

            messages.success(request, f"BOM '{name}' (v{version}) created successfully with recipe components.")
            return redirect('production:bom_detail', pk=bom.id)
        except Exception as e:
            messages.error(request, f"Failed to create BOM: {e}")

    return render(request, 'production/bom_create.html', {
        'products': products,
        'items': items,
        'uoms': uoms
    })


@login_required
@production_view_access
def bom_detail(request, pk):
    bom = get_object_or_404(BillOfMaterials.objects.prefetch_related('components__item', 'components__unit'), pk=pk)
    return render(request, 'production/bom_detail.html', {'bom': bom})


@login_required
@production_view_access
def production_run_list(request):
    runs = ProductionRun.objects.select_related('product', 'bom', 'supervisor').order_by('-production_date', '-id')
    return render(request, 'production/run_list.html', {'runs': runs})


@login_required
@production_execution_only
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
@production_view_access
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
