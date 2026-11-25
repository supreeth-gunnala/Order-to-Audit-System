from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.master_data.models import Product, Customer


class OrderStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', 'Submitted'
    APPROVED = 'APPROVED', 'Approved by Admin'
    REJECTED = 'REJECTED', 'Rejected'
    INVOICED = 'INVOICED', 'GST Invoiced'
    DISPATCHED = 'DISPATCHED', 'Dispatched'


class SalesOrder(models.Model):
    order_number = models.CharField(max_length=50, unique=True)
    salesman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sales_orders')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.SUBMITTED)
    order_date = models.DateTimeField(auto_now_add=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_estimate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_orders'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-order_date', '-id']

    def __str__(self):
        return f"{self.order_number} - {self.customer.name} - ₹{self.total_amount} ({self.get_status_display()})"


class SalesOrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    original_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    original_unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.original_quantity:
            self.original_quantity = self.quantity
        if not self.original_unit_price:
            self.original_unit_price = self.unit_price

        self.subtotal = (self.quantity * self.unit_price).quantize(Decimal('0.01'))
        self.tax_amount = (self.subtotal * (self.gst_rate / Decimal('100.0'))).quantize(Decimal('0.01'))
        self.total_amount = self.subtotal + self.tax_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity} pkts @ ₹{self.unit_price}"


class InvoiceStatus(models.TextChoices):
    POSTED = 'POSTED', 'Posted'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Fully Paid'
    CANCELLED = 'CANCELLED', 'Cancelled via Credit Note'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    financial_year = models.CharField(max_length=10, default='2026-27')
    order = models.OneToOneField(SalesOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    invoice_date = models.DateField()
    place_of_supply = models.CharField(max_length=100)
    customer_gstin = models.CharField(max_length=25, blank=True)
    is_inter_state = models.BooleanField(default=False)

    taxable_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.POSTED)
    pdf_file = models.FileField(upload_to='invoices/', blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='generated_invoices')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-invoice_date', '-id']

    def __str__(self):
        return f"{self.invoice_number} | {self.customer.name} | ₹{self.total_amount} | Due: ₹{self.outstanding_amount}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    hsn_code = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=12, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} ({self.quantity} pkts)"


class CreditNote(models.Model):
    credit_note_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='credit_notes')
    reason = models.TextField()
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    sgst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    igst_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.credit_note_number} against {self.invoice.invoice_number} - ₹{self.total_amount}"


class Dispatch(models.Model):
    dispatch_number = models.CharField(max_length=50, unique=True)
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name='dispatches')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, null=True, blank=True, related_name='dispatches')
    dispatch_date = models.DateField()
    transporter_name = models.CharField(max_length=150, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dispatch_date', '-id']

    def __str__(self):
        return f"{self.dispatch_number} for Order {self.order.order_number}"


class DispatchItem(models.Model):
    dispatch = models.ForeignKey(Dispatch, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity} pkts"


class PaymentMode(models.TextChoices):
    CASH = 'CASH', 'Cash'
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer / NEFT / RTGS'
    UPI = 'UPI', 'UPI Payment'
    CHEQUE = 'CHEQUE', 'Cheque'


class Payment(models.Model):
    receipt_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='payments')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.choices, default=PaymentMode.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True, help_text="Transaction reference / UTR / Cheque number")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-id']

    def __str__(self):
        return f"{self.receipt_number} | {self.customer.name} | ₹{self.amount} via {self.get_payment_mode_display()}"


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='allocations')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='allocations')
    allocated_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Allocated ₹{self.allocated_amount} from {self.payment.receipt_number} to {self.invoice.invoice_number}"
