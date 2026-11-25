from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.master_data.models import Product, UnitOfMeasure
from apps.inventory.models import InventoryItem


class BillOfMaterials(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='boms')
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=150, help_text="e.g. Standard Murukku 200g Recipe")
    expected_output_packets = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('200.00'),
        help_text="Standard batch yield in finished packets"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['product', '-version']
        unique_together = ('product', 'version')

    def __str__(self):
        return f"{self.product.name} (BOM v{self.version}) - {self.expected_output_packets} pkts"


class BOMComponent(models.Model):
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.CASCADE, related_name='components')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='bom_usages')
    quantity = models.DecimalField(max_digits=12, decimal_places=4, help_text="Quantity required per standard batch")
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT)
    is_packaging = models.BooleanField(default=False)
    standard_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['is_packaging', 'item__name']

    def __str__(self):
        return f"{self.item.name}: {self.quantity} {self.unit.code} ({'Packaging' if self.is_packaging else 'Ingredient'})"


class ProductionRunStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    COMPLETED = 'COMPLETED', 'Completed & Stock Posted'
    CORRECTED = 'CORRECTED', 'Corrected / Reversed'


class ProductionRun(models.Model):
    run_number = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='production_runs')
    bom = models.ForeignKey(BillOfMaterials, on_delete=models.PROTECT, related_name='production_runs')
    batch_size = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1.00'))
    production_date = models.DateField()
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='supervised_runs')

    expected_output = models.DecimalField(max_digits=10, decimal_places=2)
    actual_good_output = models.DecimalField(max_digits=10, decimal_places=2)
    yield_variance_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    yield_variance_flagged = models.BooleanField(default=False)

    damaged_packaging_pouches = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    damaged_packaging_cartons = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    cartons_used = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    packaging_capacity_warning = models.TextField(blank=True)

    # Cost breakdown fields
    direct_material_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    labour_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    gas_power_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_production_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cost_per_good_packet = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'))

    status = models.CharField(max_length=20, choices=ProductionRunStatus.choices, default=ProductionRunStatus.DRAFT)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-production_date', '-id']

    def __str__(self):
        return f"{self.run_number} - {self.product.name} ({self.actual_good_output} pkts) - {self.status}"


class ProductionConsumption(models.Model):
    production_run = models.ForeignKey(ProductionRun, on_delete=models.CASCADE, related_name='consumptions')
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    planned_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    actual_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT)
    variance_percent = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    variance_flagged = models.BooleanField(default=False)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0.0000'))
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    is_packaging = models.BooleanField(default=False)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['is_packaging', 'item__name']

    def __str__(self):
        flag = " [!] ALERT" if self.variance_flagged else ""
        return f"{self.item.name}: Planned {self.planned_quantity}, Actual {self.actual_quantity} ({self.variance_percent}%){flag}"
