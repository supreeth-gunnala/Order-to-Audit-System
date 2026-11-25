from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.core.permissions import audit_or_admin
from .services import ReportService
from .exporters import export_csv_response, export_excel_response, export_pdf_table_response
from apps.inventory.models import InventoryItem, ItemType


@login_required
@audit_or_admin
def auditor_dashboard(request):
    gst = ReportService.get_gst_outward_summary()
    gstr3b = ReportService.get_gstr3b_summary()
    receivables = ReportService.get_receivables_ageing()
    total_due = sum(r['total_due'] for r in receivables)

    rm_items = InventoryItem.objects.filter(item_type=ItemType.RAW_MATERIAL)
    pkg_items = InventoryItem.objects.filter(item_type=ItemType.PACKAGING)
    fg_items = InventoryItem.objects.filter(item_type=ItemType.FINISHED_GOOD)

    context = {
        'gst': gst,
        'gstr3b': gstr3b,
        'receivables': receivables,
        'total_due': total_due,
        'rm_val': sum(i.total_stock_value for i in rm_items),
        'pkg_val': sum(i.total_stock_value for i in pkg_items),
        'fg_val': sum(i.total_stock_value for i in fg_items),
    }
    return render(request, 'reports/auditor_dashboard.html', context)


@login_required
@audit_or_admin
def sales_register(request):
    start = request.GET.get('start_date') or None
    end = request.GET.get('end_date') or None
    invoices = ReportService.get_sales_register(start_date=start, end_date=end)

    fmt = request.GET.get('export')
    if fmt:
        headers = ['Invoice No', 'Date', 'Customer', 'State', 'GSTIN', 'Taxable (₹)', 'CGST (₹)', 'SGST (₹)', 'IGST (₹)', 'Total (₹)', 'Balance Due (₹)', 'Status']
        rows = [
            [
                inv.invoice_number, inv.invoice_date.strftime('%Y-%m-%d'), inv.customer.name, inv.customer.state,
                inv.customer_gstin or 'URP', f"{inv.taxable_value:.2f}", f"{inv.cgst_amount:.2f}", f"{inv.sgst_amount:.2f}",
                f"{inv.igst_amount:.2f}", f"{inv.total_amount:.2f}", f"{inv.outstanding_amount:.2f}", inv.get_status_display()
            ]
            for inv in invoices
        ]
        if fmt == 'csv':
            return export_csv_response('Sales_Register', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('Sales_Register', 'Sales Register', headers, rows)
        elif fmt == 'pdf':
            return export_pdf_table_response('Sales_Register', 'Sales Register Report', headers, rows, is_landscape=True)

    return render(request, 'reports/sales_register.html', {
        'invoices': invoices,
        'start_date': start,
        'end_date': end
    })


@login_required
@audit_or_admin
def gst_outward_report(request):
    start = request.GET.get('start_date') or None
    end = request.GET.get('end_date') or None
    data = ReportService.get_gst_outward_summary(start_date=start, end_date=end)

    fmt = request.GET.get('export')
    if fmt:
        headers = ['HSN Code', 'Product', 'Total Qty', 'Taxable Value (₹)', 'CGST (₹)', 'SGST (₹)', 'IGST (₹)', 'Total (₹)']
        rows = [
            [h['hsn_code'], h['product__name'], str(h['total_qty']), f"{h['taxable']:.2f}", f"{h['cgst']:.2f}", f"{h['sgst']:.2f}", f"{h['igst']:.2f}", f"{h['total']:.2f}"]
            for h in data['hsn_summary']
        ]
        if fmt == 'csv':
            return export_csv_response('GSTR1_Outward_Summary', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('GSTR1_Outward_Summary', 'GSTR-1 Summary', headers, rows)
        elif fmt == 'pdf':
            return export_pdf_table_response('GSTR1_Outward_Summary', 'GSTR-1 Outward Supplies Summary', headers, rows)

    return render(request, 'reports/gst_outward.html', {
        'data': data,
        'start_date': start,
        'end_date': end
    })


@login_required
@audit_or_admin
def gstr3b_report(request):
    start = request.GET.get('start_date') or None
    end = request.GET.get('end_date') or None
    data = ReportService.get_gstr3b_summary(start_date=start, end_date=end)
    return render(request, 'reports/gstr3b_summary.html', {
        'data': data,
        'start_date': start,
        'end_date': end
    })


@login_required
@audit_or_admin
def production_costing_report(request):
    runs = ReportService.get_production_costing_summary()

    fmt = request.GET.get('export')
    if fmt:
        headers = ['Run No', 'Date', 'Product', 'Actual Output', 'Yield Var %', 'Direct Mat (₹)', 'Labour (₹)', 'Overhead (₹)', 'Total Cost (₹)', 'Cost/Pkt (₹)']
        rows = [
            [
                r.run_number, r.production_date.strftime('%Y-%m-%d'), r.product.name, f"{r.actual_good_output:.0f}",
                f"{r.yield_variance_percent}%", f"{r.direct_material_cost:.2f}", f"{r.labour_cost:.2f}",
                f"{r.gas_power_cost:.2f}", f"{r.total_production_cost:.2f}", f"{r.cost_per_good_packet:.2f}"
            ]
            for r in runs
        ]
        if fmt == 'csv':
            return export_csv_response('Production_Costing', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('Production_Costing', 'Costing Report', headers, rows)
        elif fmt == 'pdf':
            return export_pdf_table_response('Production_Costing', 'Production Costing & Variance Report', headers, rows, is_landscape=True)

    return render(request, 'reports/production_costing.html', {'runs': runs})


@login_required
@audit_or_admin
def receivables_ageing_report(request):
    buckets = ReportService.get_receivables_ageing()
    total_due = sum(b['total_due'] for b in buckets)

    fmt = request.GET.get('export')
    if fmt:
        headers = ['Customer', 'Type', 'State', '0-30 Days (₹)', '31-60 Days (₹)', '61-90 Days (₹)', '>90 Days (₹)', 'Total Due (₹)']
        rows = [
            [
                b['customer'].name, b['customer'].get_customer_type_display(), b['customer'].state,
                f"{b['current']:.2f}", f"{b['days_30']:.2f}", f"{b['days_60']:.2f}", f"{b['days_90_plus']:.2f}", f"{b['total_due']:.2f}"
            ]
            for b in buckets
        ]
        if fmt == 'csv':
            return export_csv_response('Receivables_Ageing', headers, rows)
        elif fmt == 'excel':
            return export_excel_response('Receivables_Ageing', 'Receivables Ageing', headers, rows)
        elif fmt == 'pdf':
            return export_pdf_table_response('Receivables_Ageing', 'Receivables Ageing Analysis Report', headers, rows)

    return render(request, 'reports/receivables_ageing.html', {
        'buckets': buckets,
        'total_due': total_due
    })
