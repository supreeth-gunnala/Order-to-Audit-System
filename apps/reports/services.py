from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, F, Q, Avg
from django.utils import timezone
from apps.sales.models import Invoice, InvoiceItem, InvoiceStatus, SalesOrder, Payment, Dispatch
from apps.inventory.models import InventoryItem, StockLedger, Purchase, PurchaseItem
from apps.production.models import ProductionRun, ProductionConsumption
from apps.master_data.models import Customer, Product


class ReportService:
    @staticmethod
    def get_sales_register(start_date=None, end_date=None, customer_id=None):
        qs = Invoice.objects.select_related('customer', 'order', 'created_by').prefetch_related('items')
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.order_by('-invoice_date', '-id')

    @staticmethod
    def get_customer_wise_sales(start_date=None, end_date=None):
        qs = Invoice.objects.filter(~Q(status=InvoiceStatus.CANCELLED))
        if start_date:
            qs = qs.filter(invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice_date__lte=end_date)
        
        return qs.values('customer__id', 'customer__name', 'customer__state', 'customer__customer_type').annotate(
            total_invoices=Count('id'),
            total_taxable=Sum('taxable_value'),
            total_tax=Sum(F('cgst_amount') + F('sgst_amount') + F('igst_amount')),
            total_amount=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
            total_outstanding=Sum('outstanding_amount')
        ).order_by('-total_amount')

    @staticmethod
    def get_product_wise_sales(start_date=None, end_date=None):
        qs = InvoiceItem.objects.filter(~Q(invoice__status=InvoiceStatus.CANCELLED))
        if start_date:
            qs = qs.filter(invoice__invoice_date__gte=start_date)
        if end_date:
            qs = qs.filter(invoice__invoice_date__lte=end_date)

        return qs.values('product__id', 'product__name', 'product__sku', 'product__hsn_code').annotate(
            total_quantity=Sum('quantity'),
            total_taxable=Sum('taxable_value'),
            total_tax=Sum(F('cgst_amount') + F('sgst_amount') + F('igst_amount')),
            total_amount=Sum('total_amount'),
            avg_rate=Avg('unit_price')
        ).order_by('-total_amount')

    @staticmethod
    def get_gst_outward_summary(start_date=None, end_date=None):
        """
        GSTR-1 style outward supply breakdown:
        - B2B Registered vs B2C Unregistered
        - Intra-state (CGST + SGST) vs Inter-state (IGST)
        - HSN Summary
        """
        invoices = Invoice.objects.filter(~Q(status=InvoiceStatus.CANCELLED))
        if start_date:
            invoices = invoices.filter(invoice_date__gte=start_date)
        if end_date:
            invoices = invoices.filter(invoice_date__lte=end_date)

        intra_invoices = invoices.filter(is_inter_state=False)
        inter_invoices = invoices.filter(is_inter_state=True)

        totals = invoices.aggregate(
            taxable=Sum('taxable_value'),
            cgst=Sum('cgst_amount'),
            sgst=Sum('sgst_amount'),
            igst=Sum('igst_amount'),
            grand_total=Sum('total_amount')
        )

        hsn_items = InvoiceItem.objects.filter(invoice__in=invoices).values(
            'hsn_code', 'product__name'
        ).annotate(
            total_qty=Sum('quantity'),
            taxable=Sum('taxable_value'),
            cgst=Sum('cgst_amount'),
            sgst=Sum('sgst_amount'),
            igst=Sum('igst_amount'),
            total=Sum('total_amount')
        ).order_by('hsn_code')

        return {
            'invoices': invoices,
            'totals': {
                'taxable': totals['taxable'] or Decimal('0.00'),
                'cgst': totals['cgst'] or Decimal('0.00'),
                'sgst': totals['sgst'] or Decimal('0.00'),
                'igst': totals['igst'] or Decimal('0.00'),
                'grand_total': totals['grand_total'] or Decimal('0.00'),
            },
            'intra_summary': intra_invoices.aggregate(
                taxable=Sum('taxable_value'), cgst=Sum('cgst_amount'), sgst=Sum('sgst_amount')
            ),
            'inter_summary': inter_invoices.aggregate(
                taxable=Sum('taxable_value'), igst=Sum('igst_amount')
            ),
            'hsn_summary': hsn_items
        }

    @staticmethod
    def get_gstr3b_summary(start_date=None, end_date=None):
        """
        GSTR-3B style management summary for outward supplies:
        Section 3.1: Details of Outward Supplies and inward supplies liable to reverse charge.
        """
        invoices = Invoice.objects.filter(~Q(status=InvoiceStatus.CANCELLED))
        if start_date:
            invoices = invoices.filter(invoice_date__gte=start_date)
        if end_date:
            invoices = invoices.filter(invoice_date__lte=end_date)

        agg = invoices.aggregate(
            taxable=Sum('taxable_value'),
            igst=Sum('igst_amount'),
            cgst=Sum('cgst_amount'),
            sgst=Sum('sgst_amount'),
            total=Sum('total_amount')
        )
        return {
            'outward_taxable_supplies': {
                'taxable_value': agg['taxable'] or Decimal('0.00'),
                'integrated_tax': agg['igst'] or Decimal('0.00'),
                'central_tax': agg['cgst'] or Decimal('0.00'),
                'state_tax': agg['sgst'] or Decimal('0.00'),
                'total_tax': (agg['igst'] or Decimal('0.00')) + (agg['cgst'] or Decimal('0.00')) + (agg['sgst'] or Decimal('0.00')),
                'total_value': agg['total'] or Decimal('0.00'),
            }
        }

    @staticmethod
    def get_receivables_ageing():
        """
        Receivables Ageing analysis:
        Bins: 0-30 days, 31-60 days, 61-90 days, > 90 days.
        """
        today = timezone.now().date()
        unpaid_invoices = Invoice.objects.filter(
            outstanding_amount__gt=Decimal('0.00'),
            status__in=[InvoiceStatus.POSTED, InvoiceStatus.PARTIALLY_PAID]
        ).select_related('customer')

        customer_buckets = {}
        for inv in unpaid_invoices:
            c = inv.customer
            cid = c.id
            if cid not in customer_buckets:
                customer_buckets[cid] = {
                    'customer': c,
                    'current': Decimal('0.00'),
                    'days_30': Decimal('0.00'),
                    'days_60': Decimal('0.00'),
                    'days_90_plus': Decimal('0.00'),
                    'total_due': Decimal('0.00')
                }

            days = (today - inv.invoice_date).days
            due = inv.outstanding_amount

            customer_buckets[cid]['total_due'] += due
            if days <= 30:
                customer_buckets[cid]['current'] += due
            elif days <= 60:
                customer_buckets[cid]['days_30'] += due
            elif days <= 90:
                customer_buckets[cid]['days_60'] += due
            else:
                customer_buckets[cid]['days_90_plus'] += due

        return list(customer_buckets.values())

    @staticmethod
    def get_stock_ledger_report(item_id=None, movement_type=None, start_date=None, end_date=None):
        qs = StockLedger.objects.select_related('item', 'unit', 'created_by')
        if item_id:
            qs = qs.filter(item_id=item_id)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)
        return qs.order_by('-timestamp', '-id')

    @staticmethod
    def get_production_costing_summary(start_date=None, end_date=None):
        qs = ProductionRun.objects.select_related('product', 'bom', 'supervisor')
        if start_date:
            qs = qs.filter(production_date__gte=start_date)
        if end_date:
            qs = qs.filter(production_date__lte=end_date)
        return qs.order_by('-production_date', '-id')
