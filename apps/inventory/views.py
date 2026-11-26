from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.permissions import inventory_read_access, admin_only
from apps.reports.exporters import export_csv_response, export_excel_response
from .models import InventoryItem, ItemType, StockLedger, Purchase, PurchaseItem
from .services import InventoryService
from apps.master_data.models import Supplier, UnitOfMeasure


@login_required
@inventory_read_access
def stock_summary(request):
    raw_materials = InventoryItem.objects.filter(item_type=ItemType.RAW_MATERIAL).select_related('uom')
    packaging = InventoryItem.objects.filter(item_type=ItemType.PACKAGING).select_related('uom')
    finished_goods = InventoryItem.objects.filter(item_type=ItemType.FINISHED_GOOD).select_related('uom', 'linked_product')

    rm_total_val = sum(i.total_stock_value for i in raw_materials)
    pkg_total_val = sum(i.total_stock_value for i in packaging)
    fg_total_val = sum(i.total_stock_value for i in finished_goods)

    fmt = request.GET.get('export')
    if fmt:
        headers = ['SKU', 'Item Name', 'Category', 'Current Stock', 'UOM', 'WAC Unit Rate (₹)', 'Total Stock Value (₹)']
        all_items = list(raw_materials) + list(packaging) + list(finished_goods)
        rows = [
            [
                i.sku, i.name, i.get_item_type_display(), f"{i.current_stock:.3f}",
                i.uom.code, f"{i.weighted_avg_cost:.4f}", f"{i.total_stock_value:.2f}"
            ]
            for i in all_items
        ]
        if fmt == 'csv':
            return export_csv_response('Inventory_Stock_Balances', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('Inventory_Stock_Balances', 'Stock Balances', headers, rows)

    return render(request, 'inventory/stock_summary.html', {
        'raw_materials': raw_materials,
        'packaging': packaging,
        'finished_goods': finished_goods,
        'rm_total_val': rm_total_val,
        'pkg_total_val': pkg_total_val,
        'fg_total_val': fg_total_val,
        'grand_total_val': rm_total_val + pkg_total_val + fg_total_val
    })


@login_required
@inventory_read_access
def stock_ledger_view(request):
    items = InventoryItem.objects.all()
    entries = StockLedger.objects.select_related('item', 'unit', 'created_by').order_by('-timestamp')

    item_id = request.GET.get('item')
    mov_type = request.GET.get('movement_type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if item_id:
        entries = entries.filter(item_id=item_id)
    if mov_type:
        entries = entries.filter(movement_type=mov_type)
    if start_date:
        entries = entries.filter(timestamp__date__gte=start_date)
    if end_date:
        entries = entries.filter(timestamp__date__lte=end_date)

    fmt = request.GET.get('export')
    if fmt:
        headers = ['Timestamp', 'Movement Type', 'Item SKU', 'Item Name', 'Quantity', 'UOM', 'Bal Before', 'Bal After', 'Rate (₹)', 'Total (₹)', 'Source Doc', 'Ref ID', 'User']
        rows = [
            [
                e.timestamp.strftime('%Y-%m-%d %H:%M'), e.get_movement_type_display(), e.item.sku, e.item.name,
                f"{e.quantity:.3f}", e.unit.code, f"{e.balance_before:.3f}", f"{e.balance_after:.3f}",
                f"{e.unit_cost:.4f}", f"{e.total_cost:.2f}", e.source_document, e.reference_id,
                e.created_by.username if e.created_by else 'System'
            ]
            for e in entries
        ]
        if fmt == 'csv':
            return export_csv_response('Stock_Movement_Ledger', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('Stock_Movement_Ledger', 'Stock Ledger', headers, rows)

    return render(request, 'inventory/stock_ledger.html', {
        'entries': entries[:200],
        'items': items,
        'selected_item': int(item_id) if item_id else None,
        'selected_mov': mov_type,
        'start_date': start_date,
        'end_date': end_date
    })


@login_required
@inventory_read_access
def purchase_list(request):
    purchases = Purchase.objects.select_related('supplier', 'created_by').prefetch_related('items').order_by('-purchase_date', '-id')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        purchases = purchases.filter(purchase_date__gte=start_date)
    if end_date:
        purchases = purchases.filter(purchase_date__lte=end_date)

    fmt = request.GET.get('export')
    if fmt:
        headers = ['PO Number', 'Receipt Date', 'Supplier', 'Vendor Bill No', 'Items & Qty', 'Total Amount (₹)', 'Received By']
        rows = []
        for p in purchases:
            items_summary = "; ".join([f"{item.item.name}: {item.quantity} {item.unit.code} @ ₹{item.unit_price}" for item in p.items.all()])
            rows.append([
                p.purchase_number, p.purchase_date.strftime('%Y-%m-%d'), p.supplier.name,
                p.supplier_invoice_no or '-', items_summary, f"{p.total_amount:.2f}",
                p.created_by.username if p.created_by else 'Admin'
            ])
        if fmt == 'csv':
            return export_csv_response('Purchase_Register', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('Purchase_Register', 'Purchase Register', headers, rows)

    return render(request, 'inventory/purchase_list.html', {
        'purchases': purchases,
        'start_date': start_date,
        'end_date': end_date
    })


@login_required
@admin_only
def purchase_create(request):
    suppliers = Supplier.objects.all()
    items = InventoryItem.objects.filter(item_type__in=[ItemType.RAW_MATERIAL, ItemType.PACKAGING])

    if request.method == 'POST':
        try:
            supp_id = request.POST.get('supplier')
            p_date = request.POST.get('purchase_date')
            bill_no = request.POST.get('supplier_invoice_no', '')
            notes = request.POST.get('notes', '')

            item_id = request.POST.get('item')
            qty = Decimal(request.POST.get('quantity'))
            price = Decimal(request.POST.get('unit_price'))

            inv_item = InventoryItem.objects.get(id=item_id)
            total = (qty * price).quantize(Decimal('0.01'))

            count = Purchase.objects.count() + 1
            po_num = f"PO-2627-{count:04d}"

            purchase = Purchase.objects.create(
                purchase_number=po_num,
                supplier_id=supp_id,
                purchase_date=p_date,
                supplier_invoice_no=bill_no,
                total_amount=total,
                notes=notes,
                created_by=request.user
            )

            PurchaseItem.objects.create(
                purchase=purchase,
                item=inv_item,
                quantity=qty,
                unit=inv_item.uom,
                unit_price=price,
                total_price=total
            )

            InventoryService.post_purchase_receipt(purchase, user=request.user)

            messages.success(
                request,
                f"Purchase {po_num} recorded successfully. Weighted-average cost for {inv_item.name} updated."
            )
            return redirect('inventory:purchase_list')

        except Exception as e:
            messages.error(request, f"Error creating purchase: {e}")

    return render(request, 'inventory/purchase_create.html', {
        'suppliers': suppliers,
        'items': items
    })


@login_required
@admin_only
def item_create(request):
    uoms = UnitOfMeasure.objects.all()
    if request.method == 'POST':
        try:
            sku = request.POST.get('sku', '').strip()
            name = request.POST.get('name', '').strip()
            item_type = request.POST.get('item_type')
            uom_id = request.POST.get('uom')
            reorder_level = Decimal(request.POST.get('reorder_level', '0.000') or '0')
            opening_stock = Decimal(request.POST.get('opening_stock', '0.000') or '0')
            initial_cost = Decimal(request.POST.get('initial_cost', '0.0000') or '0')

            uom = get_object_or_404(UnitOfMeasure, id=uom_id)
            item = InventoryItem.objects.create(
                sku=sku,
                name=name,
                item_type=item_type,
                uom=uom,
                reorder_level=reorder_level,
                current_stock=Decimal('0.000'),
                weighted_avg_cost=initial_cost
            )

            if opening_stock > Decimal('0.000'):
                from .models import StockMovementType
                InventoryService.record_movement(
                    item=item,
                    movement_type=StockMovementType.OPENING_BALANCE,
                    quantity=opening_stock,
                    unit=uom,
                    unit_cost=initial_cost,
                    source_document='OpeningBalance',
                    reference_id=f"OPN-{item.sku}",
                    user=request.user,
                    notes="Initial opening inventory balance"
                )

            messages.success(request, f"Inventory item '{name}' ({sku}) created successfully.")
            return redirect('inventory:stock_summary')
        except Exception as e:
            messages.error(request, f"Error creating inventory item: {e}")

    return render(request, 'inventory/item_create.html', {
        'uoms': uoms,
        'item_types': [
            (ItemType.RAW_MATERIAL, 'Raw Material / Ingredient'),
            (ItemType.PACKAGING, 'Packaging Material')
        ]
    })


@login_required
@admin_only
def opening_stock_create(request):
    from django.db import transaction
    from .models import StockMovementType

    items = InventoryItem.objects.filter(
        item_type__in=[ItemType.RAW_MATERIAL, ItemType.PACKAGING],
        is_active=True
    ).order_by('name')

    if request.method == 'POST':
        try:
            item_id = request.POST.get('item')
            quantity = Decimal(request.POST.get('quantity', '0'))
            unit_cost = Decimal(request.POST.get('unit_cost', '0'))
            notes = request.POST.get('notes', '').strip()

            if quantity <= 0:
                raise ValueError("Opening quantity must be greater than zero.")

            if unit_cost <= 0:
                raise ValueError("Opening cost must be greater than zero.")

            with transaction.atomic():
                item = InventoryItem.objects.select_for_update().get(
                    id=item_id,
                    item_type__in=[ItemType.RAW_MATERIAL, ItemType.PACKAGING],
                    is_active=True
                )

                if item.current_stock != Decimal('0.000'):
                    raise ValueError(
                        "Opening stock can only be recorded when current stock is zero."
                    )

                if StockLedger.objects.filter(
                    item=item,
                    movement_type=StockMovementType.OPENING_BALANCE,
                    quantity__gt=0
                ).exists():
                    raise ValueError("Opening stock has already been recorded for this item.")

                item.weighted_avg_cost = unit_cost.quantize(Decimal('0.0001'))
                item.save(update_fields=['weighted_avg_cost', 'updated_at'])

                InventoryService.record_movement(
                    item=item,
                    movement_type=StockMovementType.OPENING_BALANCE,
                    quantity=quantity,
                    unit=item.uom,
                    unit_cost=unit_cost,
                    source_document='OpeningBalance',
                    reference_id=f'OPN-{item.sku}',
                    user=request.user,
                    notes=notes or 'Initial opening inventory balance'
                )

            messages.success(
                request,
                f'Opening stock recorded: {quantity} {item.uom.code} of {item.name}.'
            )
            return redirect('inventory:stock_summary')

        except Exception as e:
            messages.error(request, f'Unable to record opening stock: {e}')

    return render(request, 'inventory/opening_stock_create.html', {
        'items': items
    })

