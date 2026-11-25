from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError


class UnitCategory(models.TextChoices):
    MASS = 'MASS', 'Mass / Weight (kg, g)'
    VOLUME = 'VOLUME', 'Volume (L, ml)'
    COUNT = 'COUNT', 'Discrete Count (pieces, packets)'
    CONTAINER = 'CONTAINER', 'Container / Bulk (cartons, boxes)'


class UnitOfMeasure(models.Model):
    code = models.CharField(max_length=15, unique=True, help_text="Short unit symbol, e.g., 'kg', 'L', 'g', 'pcs', 'pkt', 'ctn'")
    name = models.CharField(max_length=50, help_text="Descriptive unit name, e.g., 'Kilogram', 'Litre'")
    category = models.CharField(max_length=20, choices=UnitCategory.choices, default=UnitCategory.COUNT)
    base_unit = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='derived_units')
    conversion_factor = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal('1.000000'),
        help_text="Multiplier to convert this unit into its base unit. For example, for 'g' where base is 'kg', factor is 0.001."
    )

    class Meta:
        verbose_name = 'Unit of Measure'
        verbose_name_plural = 'Units of Measure'
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"

    def convert_to(self, target_unit, quantity: Decimal) -> Decimal:
        """Converts quantity from this unit to target_unit within the same physical category."""
        if self.code == target_unit.code:
            return quantity
        if self.category != target_unit.category:
            raise ValidationError(f"Cannot convert incompatible unit categories: {self.category} to {target_unit.category}")
        # Convert to common base unit, then to target unit
        qty_in_base = quantity * self.conversion_factor
        return qty_in_base / target_unit.conversion_factor


class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'Product Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=150, unique=True)
    sku = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.PROTECT, related_name='products')
    pack_size = models.DecimalField(max_digits=10, decimal_places=2, help_text="Pack size quantity (e.g. 200)")
    pack_unit = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='pack_products')
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Default selling price per unit before GST")
    hsn_code = models.CharField(max_length=20, default='19059040', help_text="HSN code for GST reporting")
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'), help_text="GST percentage rate, e.g., 5.00 for 5%")
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name='products', help_text="Base billing UOM (e.g. pkt)")
    pieces_per_carton = models.PositiveIntegerField(default=20, help_text="Capacity per standard outer carton (e.g. 20 packets/carton)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - ₹{self.selling_price}"


class CustomerType(models.TextChoices):
    RETAILER = 'RETAILER', 'Retailer'
    DISTRIBUTOR = 'DISTRIBUTOR', 'Distributor'


class Customer(models.Model):
    name = models.CharField(max_length=150)
    customer_type = models.CharField(max_length=20, choices=CustomerType.choices, default=CustomerType.RETAILER)
    gstin = models.CharField(max_length=25, blank=True, null=True, help_text="15-character GSTIN if registered")
    state = models.CharField(max_length=60, default='Tamil Nadu')
    billing_address = models.TextField()
    shipping_address = models.TextField(blank=True)
    assigned_salesman = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_customers',
        limit_choices_to={'role': 'SALESMAN'}
    )
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_customer_type_display()} - {self.state})"

    @property
    def is_interstate(self):
        factory_state = getattr(settings, 'FACTORY_STATE', 'Tamil Nadu').strip().lower()
        return self.state.strip().lower() != factory_state


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    gstin = models.CharField(max_length=25, blank=True, null=True)
    state = models.CharField(max_length=60, default='Tamil Nadu')
    address = models.TextField()
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PriceList(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_rules')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name='custom_prices')
    customer_type = models.CharField(max_length=20, choices=CustomerType.choices, blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    effective_from = models.DateField()

    class Meta:
        ordering = ['-effective_from']

    def __str__(self):
        target = self.customer.name if self.customer else self.customer_type or 'All'
        return f"{self.product.name} @ ₹{self.price} for {target}"
