from decimal import Decimal
import os
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    SalesOrder, SalesOrderItem, OrderStatus,
    Invoice, InvoiceItem, InvoiceStatus,
    Dispatch, DispatchItem,
    Payment, PaymentAllocation, PaymentMode,
    CreditNote
)
from apps.inventory.models import InventoryItem, StockMovementType
from apps.inventory.services import InventoryService
from apps.core.models import AuditLog


class SalesBillingService:
    @classmethod
    @transaction.atomic
    def generate_invoice(cls, order: SalesOrder, user=None) -> Invoice:
        """
        Creates a sequential GST Invoice for an approved SalesOrder.
        Accurately separates CGST/SGST (Intra-state) vs IGST (Inter-state).
        """
        if order.status not in [OrderStatus.APPROVED, OrderStatus.DISPATCHED]:
            raise ValidationError(f"Order {order.order_number} must be Approved before invoicing. Current status: {order.status}")

        if hasattr(order, 'invoice') and order.invoice:
            return order.invoice

        customer = order.customer
        factory_state = getattr(settings, 'FACTORY_STATE', 'Tamil Nadu').strip()
        is_inter_state = customer.is_interstate

        fy_year = "2026-27"
        count = Invoice.objects.filter(financial_year=fy_year).count() + 1
        invoice_number = f"INV-2627-{count:04d}"

        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            financial_year=fy_year,
            order=order,
            customer=customer,
            invoice_date=timezone.now().date(),
            place_of_supply=customer.state,
            customer_gstin=customer.gstin or '',
            is_inter_state=is_inter_state,
            created_by=user or order.salesman
        )

        taxable_value = Decimal('0.00')
        cgst_total = Decimal('0.00')
        sgst_total = Decimal('0.00')
        igst_total = Decimal('0.00')

        for item in order.items.select_related('product').all():
            prod = item.product
            qty = item.quantity
            rate = item.unit_price
            line_taxable = (qty * rate).quantize(Decimal('0.01'))
            taxable_value += line_taxable

            gst_rate = item.gst_rate  # e.g. 5.00
            line_cgst = Decimal('0.00')
            line_sgst = Decimal('0.00')
            line_igst = Decimal('0.00')

            if is_inter_state:
                # Inter-state: Full rate as IGST
                line_igst = (line_taxable * (gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
                igst_total += line_igst
            else:
                # Intra-state: Split equally into CGST and SGST
                half_rate = gst_rate / Decimal('2.0')
                line_cgst = (line_taxable * (half_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
                line_sgst = (line_taxable * (half_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
                cgst_total += line_cgst
                sgst_total += line_sgst

            line_total = line_taxable + line_cgst + line_sgst + line_igst

            InvoiceItem.objects.create(
                invoice=invoice,
                product=prod,
                hsn_code=prod.hsn_code,
                quantity=qty,
                unit_price=rate,
                taxable_value=line_taxable,
                cgst_amount=line_cgst,
                sgst_amount=line_sgst,
                igst_amount=line_igst,
                total_amount=line_total
            )

        invoice.taxable_value = taxable_value
        if is_inter_state:
            invoice.igst_rate = Decimal('5.00')
            invoice.igst_amount = igst_total
        else:
            invoice.cgst_rate = Decimal('2.50')
            invoice.cgst_amount = cgst_total
            invoice.sgst_rate = Decimal('2.50')
            invoice.sgst_amount = sgst_total

        total_invoice_amount = taxable_value + cgst_total + sgst_total + igst_total
        invoice.total_amount = total_invoice_amount
        invoice.outstanding_amount = total_invoice_amount
        invoice.save()

        order.status = OrderStatus.INVOICED
        order.save(update_fields=['status'])

        AuditLog.objects.create(
            user=user,
            action='INVOICE_GENERATED',
            entity='Invoice',
            entity_id=str(invoice.id),
            new_value=f"Number: {invoice.invoice_number}, Total: ₹{invoice.total_amount}",
            reason=f"Generated for Order {order.order_number}"
        )

        return invoice

    @classmethod
    @transaction.atomic
    def process_dispatch(
        cls,
        order: SalesOrder,
        items_to_dispatch: dict,  # {product_id: quantity}
        user=None,
        transporter_name: str = '',
        vehicle_number: str = '',
        notes: str = ''
    ) -> Dispatch:
        """
        Dispatches finished goods against an approved order.
        Strictly verifies that sufficient finished goods stock exists.
        Prevents dispatch and raises clear shortage error if stock is insufficient.
        """
        if order.status not in [OrderStatus.APPROVED, OrderStatus.INVOICED]:
            raise ValidationError(f"Order must be Approved or Invoiced prior to dispatch. Status: {order.status}")

        count = Dispatch.objects.count() + 1
        dispatch_number = f"DSP-2627-{count:04d}"

        invoice = getattr(order, 'invoice', None)

        dispatch = Dispatch.objects.create(
            dispatch_number=dispatch_number,
            order=order,
            invoice=invoice,
            dispatch_date=timezone.now().date(),
            transporter_name=transporter_name,
            vehicle_number=vehicle_number,
            notes=notes,
            created_by=user or order.salesman
        )

        for line in order.items.select_related('product').all():
            prod = line.product
            requested_qty = items_to_dispatch.get(prod.id, line.quantity)
            if not isinstance(requested_qty, Decimal):
                requested_qty = Decimal(str(requested_qty))

            if requested_qty <= Decimal('0.00'):
                continue

            # Find matching finished goods inventory item
            fg_item = InventoryItem.objects.select_for_update().filter(linked_product=prod).first()
            if not fg_item:
                fg_item = InventoryItem.objects.select_for_update().filter(
                    name__icontains=prod.name, item_type='FINISHED_GOOD'
                ).first()

            if not fg_item:
                raise ValidationError(f"Finished Goods inventory record not found for {prod.name}.")

            available_stock = fg_item.current_stock
            if available_stock < requested_qty:
                shortage = requested_qty - available_stock
                raise ValidationError(
                    f"Insufficient finished goods stock for {prod.name}! "
                    f"Order Requested: {requested_qty} pkts, Available in Stock: {available_stock} pkts. "
                    f"Shortage: {shortage} pkts. Invalid dispatch blocked to prevent negative inventory."
                )

            # Record dispatch item
            DispatchItem.objects.create(
                dispatch=dispatch,
                product=prod,
                quantity=requested_qty
            )

            # Deduct stock from finished goods
            InventoryService.record_movement(
                item=fg_item,
                movement_type=StockMovementType.DISPATCH,
                quantity=-requested_qty,
                unit=fg_item.uom,
                unit_cost=fg_item.weighted_avg_cost,
                source_document='Dispatch',
                reference_id=dispatch.dispatch_number,
                user=user,
                notes=f"Dispatched for Order {order.order_number} to {order.customer.name}"
            )

        order.status = OrderStatus.DISPATCHED
        order.save(update_fields=['status'])

        AuditLog.objects.create(
            user=user,
            action='ORDER_DISPATCHED',
            entity='Dispatch',
            entity_id=str(dispatch.id),
            new_value=f"Dispatch No: {dispatch.dispatch_number}",
            reason=f"Dispatched for Order {order.order_number}"
        )

        return dispatch

    @classmethod
    @transaction.atomic
    def record_customer_payment(
        cls,
        customer,
        amount: Decimal,
        payment_mode: str,
        reference_number: str = '',
        invoice_id: int = None,
        user=None,
        notes: str = ''
    ) -> Payment:
        """
        Records a customer payment receipt and updates invoice outstanding balance.
        Prevents over-allocation.
        """
        if amount <= Decimal('0.00'):
            raise ValidationError("Payment amount must be greater than zero.")

        count = Payment.objects.count() + 1
        receipt_number = f"REC-2627-{count:04d}"

        payment = Payment.objects.create(
            receipt_number=receipt_number,
            customer=customer,
            payment_date=timezone.now().date(),
            amount=amount,
            payment_mode=payment_mode,
            reference_number=reference_number,
            notes=notes,
            created_by=user or customer.assigned_salesman
        )

        remaining_to_allocate = amount

        if invoice_id:
            invoices = [Invoice.objects.select_for_update().get(id=invoice_id, customer=customer)]
        else:
            # Auto-allocate to unpaid invoices chronologically
            invoices = Invoice.objects.select_for_update().filter(
                customer=customer,
                status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID]
            ).order_by('invoice_date', 'id')

        for inv in invoices:
            if remaining_to_allocate <= Decimal('0.00'):
                break

            due = inv.outstanding_amount
            if due <= Decimal('0.00'):
                continue

            alloc_amt = min(remaining_to_allocate, due)

            PaymentAllocation.objects.create(
                payment=payment,
                invoice=inv,
                allocated_amount=alloc_amt
            )

            inv.paid_amount += alloc_amt
            inv.outstanding_amount = inv.total_amount - inv.paid_amount

            if inv.outstanding_amount == Decimal('0.00'):
                inv.status = InvoiceStatus.PAID
            else:
                inv.status = InvoiceStatus.PARTIALLY_PAID

            inv.save(update_fields=['paid_amount', 'outstanding_amount', 'status'])
            remaining_to_allocate -= alloc_amt

        AuditLog.objects.create(
            user=user,
            action='PAYMENT_RECORDED',
            entity='Payment',
            entity_id=str(payment.id),
            new_value=f"Receipt: {payment.receipt_number}, Amount: ₹{amount}",
            reason=f"Received from {customer.name}"
        )

        return payment

    @classmethod
    @transaction.atomic
    def cancel_invoice_via_credit_note(cls, invoice: Invoice, reason: str, user=None) -> CreditNote:
        """
        Cancels an invoice lawfully by issuing a Credit Note, retaining the original invoice intact.
        """
        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValidationError("Invoice is already cancelled.")

        count = CreditNote.objects.count() + 1
        cn_number = f"CN-2627-{count:04d}"

        cn = CreditNote.objects.create(
            credit_note_number=cn_number,
            invoice=invoice,
            reason=reason,
            taxable_amount=invoice.taxable_value,
            cgst_amount=invoice.cgst_amount,
            sgst_amount=invoice.sgst_amount,
            igst_amount=invoice.igst_amount,
            total_amount=invoice.total_amount,
            date=timezone.now().date(),
            created_by=user
        )

        invoice.status = InvoiceStatus.CANCELLED
        invoice.outstanding_amount = Decimal('0.00')
        invoice.save(update_fields=['status', 'outstanding_amount'])

        AuditLog.objects.create(
            user=user,
            action='INVOICE_CANCELLED_CREDIT_NOTE',
            entity='Invoice',
            entity_id=str(invoice.id),
            new_value=f"Credit Note: {cn.credit_note_number}",
            reason=reason
        )

        return cn
