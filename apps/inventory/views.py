from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.core.permissions import production_only, audit_or_admin
from .models import InventoryItem, ItemType, StockLedger, Purchase, PurchaseItem
from .services import InventoryService
from apps.master_data.models import Supplier, UnitOfMeasure


@login_required
@audit_or_admin
def stock_summary(request):
    raw_materials = InventoryItem.objects.filter(item_type=ItemType.RAW_MATERIAL).select_related('uom')
    packaging = InventoryItem.objects.filter(item_type=ItemType.PACKAGING).select_related('uom')
    finished_goods = InventoryItem.objects.filter(item_type=ItemType.FINISHED_GOOD).select_related('uom', 'linked_product')

    rm_total_val = sum(i.total_stock_value for i in raw_materials)
    pkg_total_val = sum(i.total_stock_value for i in packaging)
    fg_total_val = sum(i.total_stock_value for i in finished_goods)

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
@audit_or_admin
def stock_ledger_view(request):
    items = InventoryItem.objects.all()
    entries = StockLedger.objects.select_related('item', 'unit', 'created_by').order_by('-timestamp')

    item_id = request.GET.get('item')
    mov_type = request.GET.get('movement_type')
    if item_id:
        entries = entries.filter(item_id=item_id)
    if mov_type:
        entries = entries.filter(movement_type=mov_type)

    return render(request, 'inventory/stock_ledger.html', {
        'entries': entries[:200],
        'items': items,
        'selected_item': int(item_id) if item_id else None,
        'selected_mov': mov_type
    })


@login_required
@production_only
def purchase_list(request):
    purchases = Purchase.objects.select_related('supplier', 'created_by').prefetch_related('items').order_by('-purchase_date', '-id')
    return render(request, 'inventory/purchase_list.html', {'purchases': purchases})


@login_required
@production_only
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
