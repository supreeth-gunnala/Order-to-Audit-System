from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from apps.core.permissions import salesman_only, admin_only, audit_or_admin
from .models import (
    SalesOrder, SalesOrderItem, OrderStatus,
    Invoice, InvoiceItem, InvoiceStatus,
    Dispatch, DispatchItem,
    Payment, PaymentAllocation, PaymentMode,
    CreditNote
)
from .services import SalesBillingService
from .pdf import generate_tax_invoice_pdf
from apps.master_data.models import Customer, Product, PriceList
from apps.inventory.models import InventoryItem, ItemType
from apps.core.models import AuditLog


@login_required
@salesman_only
def salesman_dashboard(request):
    user = request.user
    if user.is_salesman:
        customers = Customer.objects.filter(assigned_salesman=user, is_active=True)
        orders = SalesOrder.objects.filter(salesman=user).order_by('-order_date')[:10]
    else:
        customers = Customer.objects.filter(is_active=True)
        orders = SalesOrder.objects.order_by('-order_date')[:10]

    return render(request, 'sales/salesman_dashboard.html', {
        'customers': customers,
        'orders': orders,
        'products': Product.objects.filter(is_active=True)
    })


@login_required
@salesman_only
def order_create(request):
    user = request.user
    if user.is_salesman:
        customers = Customer.objects.filter(assigned_salesman=user, is_active=True)
    else:
        customers = Customer.objects.filter(is_active=True)

    products = Product.objects.filter(is_active=True)

    if request.method == 'POST':
        try:
            cust_id = request.POST.get('customer')
            customer = get_object_or_404(Customer, id=cust_id)
            notes = request.POST.get('notes', '')

            prod_id = request.POST.get('product')
            quantity = Decimal(request.POST.get('quantity'))
            product = get_object_or_404(Product, id=prod_id)

            # Price determination (PriceList check then standard product selling price)
            unit_price = product.selling_price
            custom_price = PriceList.objects.filter(product=product, customer=customer).first()
            if custom_price:
                unit_price = custom_price.price

            subtotal = (quantity * unit_price).quantize(Decimal('0.01'))
            tax = (subtotal * (product.gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
            total = subtotal + tax

            count = SalesOrder.objects.count() + 1
            order_number = f"SO-2627-{count:04d}"

            order = SalesOrder.objects.create(
                order_number=order_number,
                salesman=user,
                customer=customer,
                status=OrderStatus.SUBMITTED,
                subtotal=subtotal,
                tax_estimate=tax,
                total_amount=total,
                notes=notes
            )

            SalesOrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
                gst_rate=product.gst_rate,
                tax_amount=tax,
                total_amount=total,
                original_quantity=quantity,
                original_unit_price=unit_price
            )

            AuditLog.objects.create(
                user=user,
                action='ORDER_CREATED',
                entity='SalesOrder',
                entity_id=str(order.id),
                new_value=f"Order: {order.order_number}, Amount: ₹{total}",
                reason=f"Salesman order for {customer.name}"
            )

            messages.success(request, f"Order {order.order_number} submitted successfully for ₹{total:.2f}.")
            return redirect('sales:order_detail', pk=order.id)

        except Exception as e:
            messages.error(request, f"Failed to submit order: {e}")

    return render(request, 'sales/order_create.html', {
        'customers': customers,
        'products': products
    })


@login_required
def order_list(request):
    user = request.user
    if user.is_salesman:
        orders = SalesOrder.objects.filter(salesman=user).select_related('customer', 'salesman')
    else:
        orders = SalesOrder.objects.select_related('customer', 'salesman')

    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(request, 'sales/order_list.html', {
        'orders': orders.order_by('-order_date', '-id'),
        'statuses': OrderStatus.choices,
        'selected_status': status_filter
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related('customer', 'salesman', 'reviewed_by').prefetch_related('items__product'),
        pk=pk
    )

    # Check finished goods inventory availability for each item in order
    stock_info = []
    for item in order.items.all():
        fg = InventoryItem.objects.filter(linked_product=item.product).first()
        avail = fg.current_stock if fg else Decimal('0.00')
        shortage = max(Decimal('0.00'), item.quantity - avail)
        stock_info.append({
            'item': item,
            'available': avail,
            'shortage': shortage,
            'has_shortage': shortage > Decimal('0.00')
        })

    return render(request, 'sales/order_detail.html', {
        'order': order,
        'stock_info': stock_info
    })


@login_required
@admin_only
def order_review_action(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    action = request.POST.get('action')
    admin_notes = request.POST.get('admin_notes', '')

    if action == 'approve':
        order.status = OrderStatus.APPROVED
        order.reviewed_by = request.user
        order.reviewed_at = timezone.now()
        order.admin_notes = admin_notes
        order.save()
        AuditLog.objects.create(
            user=request.user,
            action='ORDER_APPROVED',
            entity='SalesOrder',
            entity_id=str(order.id),
            reason=admin_notes
        )
        messages.success(request, f"Order {order.order_number} has been approved.")

    elif action == 'reject':
        order.status = OrderStatus.REJECTED
        order.reviewed_by = request.user
        order.reviewed_at = timezone.now()
        order.admin_notes = admin_notes
        order.save()
        AuditLog.objects.create(
            user=request.user,
            action='ORDER_REJECTED',
            entity='SalesOrder',
            entity_id=str(order.id),
            reason=admin_notes
        )
        messages.warning(request, f"Order {order.order_number} was rejected.")

    elif action == 'edit_item':
        # Admin modifies order quantity/price before approval
        item_id = request.POST.get('item_id')
        new_qty = Decimal(request.POST.get('quantity'))
        new_price = Decimal(request.POST.get('unit_price'))
        item = get_object_or_404(SalesOrderItem, id=item_id, order=order)

        prev_val = f"Qty: {item.quantity}, Price: {item.unit_price}"
        item.quantity = new_qty
        item.unit_price = new_price
        item.save()

        # Recalculate order totals
        subtotal = sum(i.subtotal for i in order.items.all())
        tax = sum(i.tax_amount for i in order.items.all())
        order.subtotal = subtotal
        order.tax_estimate = tax
        order.total_amount = subtotal + tax
        order.save()

        AuditLog.objects.create(
            user=request.user,
            action='ORDER_ITEM_EDITED',
            entity='SalesOrderItem',
            entity_id=str(item.id),
            previous_value=prev_val,
            new_value=f"Qty: {new_qty}, Price: {new_price}",
            reason=f"Admin modification prior to approval: {admin_notes}"
        )
        messages.info(request, f"Order item updated: {item.product.name} (New total: ₹{order.total_amount:.2f}).")

    return redirect('sales:order_detail', pk=order.id)


@login_required
@admin_only
def order_generate_invoice(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    try:
        invoice = SalesBillingService.generate_invoice(order, user=request.user)
        messages.success(request, f"GST Tax Invoice {invoice.invoice_number} created successfully.")
        return redirect('sales:invoice_detail', pk=invoice.id)
    except Exception as e:
        messages.error(request, f"Invoice generation failed: {e}")
        return redirect('sales:order_detail', pk=order.id)


@login_required
@admin_only
def dispatch_create(request, order_id):
    order = get_object_or_404(SalesOrder, id=order_id)

    if request.method == 'POST':
        try:
            transporter = request.POST.get('transporter_name', '')
            vehicle = request.POST.get('vehicle_number', '')
            notes = request.POST.get('notes', '')

            dispatch_items = {}
            for item in order.items.all():
                qty = Decimal(request.POST.get(f'dispatch_qty_{item.product.id}', item.quantity))
                dispatch_items[item.product.id] = qty

            dispatch = SalesBillingService.process_dispatch(
                order=order,
                items_to_dispatch=dispatch_items,
                user=request.user,
                transporter_name=transporter,
                vehicle_number=vehicle,
                notes=notes
            )
            messages.success(request, f"Dispatch {dispatch.dispatch_number} recorded. Finished goods inventory reduced.")
            return redirect('sales:order_detail', pk=order.id)

        except Exception as e:
            messages.error(request, f"Dispatch Error: {e}")

    # Check FG stock for form display
    items_stock = []
    for item in order.items.all():
        fg = InventoryItem.objects.filter(linked_product=item.product).first()
        avail = fg.current_stock if fg else Decimal('0.00')
        items_stock.append({
            'item': item,
            'available': avail,
            'shortage': max(Decimal('0.00'), item.quantity - avail)
        })

    return render(request, 'sales/dispatch_create.html', {
        'order': order,
        'items_stock': items_stock
    })


@login_required
@audit_or_admin
def invoice_list(request):
    invoices = Invoice.objects.select_related('customer', 'order', 'created_by').order_by('-invoice_date', '-id')
    return render(request, 'sales/invoice_list.html', {'invoices': invoices})


@login_required
@audit_or_admin
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('customer', 'order', 'created_by').prefetch_related('items__product', 'allocations__payment'),
        pk=pk
    )
    return render(request, 'sales/invoice_detail.html', {'invoice': invoice})


@login_required
@audit_or_admin
def invoice_pdf_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    pdf_bytes = generate_tax_invoice_pdf(invoice)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{invoice.invoice_number}.pdf"'
    return response


@login_required
@admin_only
def payment_list(request):
    payments = Payment.objects.select_related('customer', 'created_by').prefetch_related('allocations__invoice').order_by('-payment_date', '-id')
    return render(request, 'sales/payment_list.html', {'payments': payments})


@login_required
@admin_only
def payment_create(request):
    customers = Customer.objects.filter(is_active=True)
    invoices = Invoice.objects.filter(
        outstanding_amount__gt=Decimal('0.00'),
        status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID]
    ).select_related('customer')

    if request.method == 'POST':
        try:
            cust_id = request.POST.get('customer')
            customer = get_object_or_404(Customer, id=cust_id)
            amount = Decimal(request.POST.get('amount'))
            mode = request.POST.get('payment_mode', PaymentMode.BANK_TRANSFER)
            ref_no = request.POST.get('reference_number', '')
            inv_id = request.POST.get('invoice_id') or None
            notes = request.POST.get('notes', '')

            payment = SalesBillingService.record_customer_payment(
                customer=customer,
                amount=amount,
                payment_mode=mode,
                reference_number=ref_no,
                invoice_id=inv_id,
                user=request.user,
                notes=notes
            )
            messages.success(request, f"Payment receipt {payment.receipt_number} recorded for ₹{amount:.2f}.")
            return redirect('sales:payment_list')

        except Exception as e:
            messages.error(request, f"Payment error: {e}")

    return render(request, 'sales/payment_create.html', {
        'customers': customers,
        'invoices': invoices,
        'modes': PaymentMode.choices
    })


@login_required
@admin_only
def invoice_credit_note(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason')
        try:
            cn = SalesBillingService.cancel_invoice_via_credit_note(invoice, reason=reason, user=request.user)
            messages.success(request, f"Credit Note {cn.credit_note_number} issued. Invoice {invoice.invoice_number} cancelled.")
            return redirect('sales:invoice_detail', pk=invoice.id)
        except Exception as e:
            messages.error(request, f"Failed to issue credit note: {e}")

    return render(request, 'sales/credit_note_create.html', {'invoice': invoice})
