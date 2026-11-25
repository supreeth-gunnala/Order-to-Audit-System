from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from apps.master_data.models import UnitOfMeasure, Product, Supplier


class ItemType(models.TextChoices):
    RAW_MATERIAL = 'RAW_MATERIAL', 'Raw Material'
    PACKAGING = 'PACKAGING', 'Packaging Material'
    FINISHED_GOOD = 'FINISHED_GOOD', 'Finished Good'


class InventoryItem(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='inventory_items')
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    current_stock = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0.000'))
    weighted_avg_cost = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal('0.0000'),
        help_text="Weighted Average Cost per unit in Indian Rupees"
    )
    linked_product = models.OneToOneField(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_item',
        help_text="Mapped finished product if this item represents finished goods."
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_type', 'name']

    def __str__(self):
        return f"{self.name} [{self.get_item_type_display()}] - {self.current_stock} {self.uom.code}"

    @property
    def total_stock_value(self) -> Decimal:
        return (self.current_stock * self.weighted_avg_cost).quantize(Decimal('0.01'))

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.reorder_level


class StockMovementType(models.TextChoices):
    OPENING_BALANCE = 'OPENING_BALANCE', 'Opening Balance'
    PURCHASE_RECEIPT = 'PURCHASE_RECEIPT', 'Purchase Receipt'
    PRODUCTION_ISSUE = 'PRODUCTION_ISSUE', 'Production Material Issue'
    PRODUCTION_OUTPUT = 'PRODUCTION_OUTPUT', 'Production Finished Goods Output'
    DISPATCH = 'DISPATCH', 'Sales Dispatch'
    RETURN = 'RETURN', 'Sales/Purchase Return'
    ADJUSTMENT = 'ADJUSTMENT', 'Inventory Adjustment'
    DAMAGE_SCRAP = 'DAMAGE_SCRAP', 'Damaged Packaging / Scrap'


class StockLedger(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='ledger_entries')
    movement_type = models.CharField(max_length=30, choices=StockMovementType.choices)
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3,
        help_text="Signed quantity moved: positive for additions/receipts, negative for deductions/issues."
    )
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    source_document = models.CharField(max_length=60, help_text="e.g. Purchase, ProductionRun, Dispatch, Adjustment")
    reference_id = models.CharField(max_length=60, help_text="Transaction code or document ID")
    balance_before = models.DecimalField(max_digits=14, decimal_places=3)
    balance_after = models.DecimalField(max_digits=14, decimal_places=3)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp', '-id']

    def __str__(self):
        sign = '+' if self.quantity > 0 else ''
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.item.name} | {sign}{self.quantity} {self.unit.code} -> Bal: {self.balance_after}"


class Purchase(models.Model):
    purchase_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases')
    purchase_date = models.DateField()
    supplier_invoice_no = models.CharField(max_length=100, blank=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-purchase_date', '-id']

    def __str__(self):
        return f"{self.purchase_number} - {self.supplier.name} - ₹{self.total_amount}"


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='purchase_lines')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Purchase rate per unit before tax")
    total_price = models.DecimalField(max_digits=14, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item.name}: {self.quantity} {self.unit.code} @ ₹{self.unit_price}"
