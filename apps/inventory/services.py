from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import InventoryItem, StockLedger, StockMovementType, Purchase
from apps.core.models import AuditLog


class InventoryService:
    @staticmethod
    @transaction.atomic
    def record_movement(
        item: InventoryItem,
        movement_type: str,
        quantity: Decimal,
        unit,
        unit_cost: Decimal,
        source_document: str,
        reference_id: str,
        user=None,
        notes: str = '',
        allow_negative: bool = False
    ) -> StockLedger:
        """
        Atomically records a stock movement into the StockLedger and updates item balance.
        quantity is signed: positive for additions/receipts, negative for deductions/dispatches.
        """
        # Lock item row to prevent concurrent race conditions
        locked_item = InventoryItem.objects.select_for_update().get(id=item.id)

        balance_before = locked_item.current_stock
        balance_after = balance_before + quantity

        if not allow_negative and balance_after < Decimal('0.000'):
            raise ValidationError(
                f"Insufficient stock for {locked_item.name}. Available: {balance_before} {locked_item.uom.code}, Requested reduction: {-quantity} {unit.code}."
            )

        locked_item.current_stock = balance_after
        locked_item.save(update_fields=['current_stock', 'updated_at'])

        total_cost = (abs(quantity) * unit_cost).quantize(Decimal('0.01'))

        ledger_entry = StockLedger.objects.create(
            item=locked_item,
            movement_type=movement_type,
            quantity=quantity,
            unit=unit,
            unit_cost=unit_cost,
            total_cost=total_cost,
            source_document=source_document,
            reference_id=reference_id,
            balance_before=balance_before,
            balance_after=balance_after,
            created_by=user,
            notes=notes
        )

        AuditLog.objects.create(
            user=user,
            action=f"STOCK_{movement_type}",
            entity='StockLedger',
            entity_id=str(ledger_entry.id),
            previous_value=f"Balance: {balance_before}",
            new_value=f"Balance: {balance_after} (Delta: {quantity})",
            reason=f"{source_document} - {reference_id}"
        )

        return ledger_entry

    @classmethod
    @transaction.atomic
    def post_purchase_receipt(cls, purchase: Purchase, user=None):
        """
        Processes a supplier purchase receipt:
        - Updates Weighted Average Cost (WAC) for raw materials / packaging.
        - Records StockLedger entry for each purchase line item.
        """
        for line in purchase.items.select_related('item', 'unit').all():
            item = line.item
            qty = line.quantity
            rate = line.unit_price

            locked_item = InventoryItem.objects.select_for_update().get(id=item.id)
            current_qty = locked_item.current_stock
            current_wac = locked_item.weighted_avg_cost

            # Weighted Average Valuation calculation:
            # WAC = (Existing Stock Value + Purchase Stock Value) / Total Quantity
            if current_qty > Decimal('0.000'):
                total_qty = current_qty + qty
                existing_val = current_qty * current_wac
                new_val = qty * rate
                new_wac = (existing_val + new_val) / total_qty
            else:
                new_wac = rate

            locked_item.weighted_avg_cost = new_wac.quantize(Decimal('0.0001'))
            locked_item.save(update_fields=['weighted_avg_cost', 'updated_at'])

            cls.record_movement(
                item=locked_item,
                movement_type=StockMovementType.PURCHASE_RECEIPT,
                quantity=qty,
                unit=line.unit,
                unit_cost=rate,
                source_document='Purchase',
                reference_id=purchase.purchase_number,
                user=user,
                notes=f"Purchase from {purchase.supplier.name} (Bill: {purchase.supplier_invoice_no})"
            )

        AuditLog.objects.create(
            user=user,
            action='PURCHASE_POSTED',
            entity='Purchase',
            entity_id=str(purchase.id),
            new_value=f"Total: ₹{purchase.total_amount}",
            reason=f"Posted receipt {purchase.purchase_number}"
        )
