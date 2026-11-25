from io import BytesIO
from decimal import Decimal
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm


def generate_tax_invoice_pdf(invoice) -> bytes:
    """
    Renders an official GST Tax Invoice as a PDF document.
    Complies with Indian GST Rule 46 requirements.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=18,
        alignment=1,
        textColor=colors.HexColor('#1a365d')
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#4a5568')
    )
    normal_style = ParagraphStyle(
        'NormalSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=11
    )
    bold_style = ParagraphStyle(
        'BoldSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
        fontName='Helvetica-Bold'
    )

    story = []

    # 1. Header
    factory_name = getattr(settings, 'FACTORY_NAME', 'Sri Krishna Food Products')
    factory_addr = getattr(settings, 'FACTORY_ADDRESS', 'Plot 12, SIDCO Industrial Estate, Thuvakudi, Trichy - 620015, Tamil Nadu')
    factory_gstin = getattr(settings, 'FACTORY_GSTIN', '33AAAAA0000A1Z5')
    factory_state = getattr(settings, 'FACTORY_STATE', 'Tamil Nadu')

    story.append(Paragraph(f"<b>{factory_name}</b>", title_style))
    story.append(Paragraph(f"{factory_addr} | GSTIN: <b>{factory_gstin}</b> | State: {factory_state} (State Code: 33)", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>TAX INVOICE</b>", ParagraphStyle('TI', parent=title_style, fontSize=12, leading=14, alignment=1)))
    story.append(Spacer(1, 10))

    # 2. Invoice and Customer Details Grid
    c = invoice.customer
    is_inter = invoice.is_inter_state

    inv_details = [
        [
            Paragraph(f"<b>Invoice No:</b> {invoice.invoice_number}<br/><b>Invoice Date:</b> {invoice.invoice_date.strftime('%d-%b-%Y')}<br/><b>Financial Year:</b> {invoice.financial_year}", normal_style),
            Paragraph(f"<b>Place of Supply:</b> {invoice.place_of_supply}<br/><b>Reverse Charge:</b> No<br/><b>Order Ref:</b> {invoice.order.order_number if invoice.order else 'Direct'}", normal_style)
        ],
        [
            Paragraph(f"<b>Billed To (Customer):</b><br/><b>{c.name}</b><br/>{c.billing_address}<br/>State: {c.state} | GSTIN: {c.gstin or 'URP / Consumer'}<br/>Phone: {c.phone}", normal_style),
            Paragraph(f"<b>Shipped To:</b><br/><b>{c.name}</b><br/>{c.shipping_address or c.billing_address}<br/>State: {c.state}", normal_style)
        ]
    ]

    details_table = Table(inv_details, colWidths=[265, 270])
    details_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 12))

    # 3. Items Table
    if is_inter:
        headers = ['#', 'Product Description', 'HSN', 'Qty', 'Unit', 'Rate (₹)', 'Taxable (₹)', 'IGST 5% (₹)', 'Total (₹)']
        col_widths = [20, 145, 50, 40, 35, 55, 65, 60, 65]
    else:
        headers = ['#', 'Product Description', 'HSN', 'Qty', 'Unit', 'Rate (₹)', 'Taxable (₹)', 'CGST 2.5%', 'SGST 2.5%', 'Total (₹)']
        col_widths = [18, 135, 45, 38, 30, 50, 60, 52, 52, 55]

    table_data = [[Paragraph(f"<b>{h}</b>", bold_style) for h in headers]]

    idx = 1
    for item in invoice.items.select_related('product', 'product__uom').all():
        if is_inter:
            row = [
                str(idx),
                item.product.name,
                item.hsn_code,
                f"{item.quantity:.0f}",
                item.product.uom.code,
                f"{item.unit_price:.2f}",
                f"{item.taxable_value:.2f}",
                f"{item.igst_amount:.2f}",
                f"{item.total_amount:.2f}"
            ]
        else:
            row = [
                str(idx),
                item.product.name,
                item.hsn_code,
                f"{item.quantity:.0f}",
                item.product.uom.code,
                f"{item.unit_price:.2f}",
                f"{item.taxable_value:.2f}",
                f"{item.cgst_amount:.2f}",
                f"{item.sgst_amount:.2f}",
                f"{item.total_amount:.2f}"
            ]
        table_data.append([Paragraph(str(cell), normal_style) for cell in row])
        idx += 1

    # Totals Row
    if is_inter:
        totals_row = [
            Paragraph("<b>Total</b>", bold_style), '', '', '', '', '',
            Paragraph(f"<b>₹{invoice.taxable_value:.2f}</b>", bold_style),
            Paragraph(f"<b>₹{invoice.igst_amount:.2f}</b>", bold_style),
            Paragraph(f"<b>₹{invoice.total_amount:.2f}</b>", bold_style)
        ]
    else:
        totals_row = [
            Paragraph("<b>Total</b>", bold_style), '', '', '', '', '',
            Paragraph(f"<b>₹{invoice.taxable_value:.2f}</b>", bold_style),
            Paragraph(f"<b>₹{invoice.cgst_amount:.2f}</b>", bold_style),
            Paragraph(f"<b>₹{invoice.sgst_amount:.2f}</b>", bold_style),
            Paragraph(f"<b>₹{invoice.total_amount:.2f}</b>", bold_style)
        ]
    table_data.append(totals_row)

    items_table = Table(table_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('SPAN', (0, -1), (5, -1)),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#edf2f7')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # Summary Box
    summary_data = [
        [
            Paragraph("<b>Bank Details for Payment:</b><br/>Bank: State Bank of India<br/>A/c No: 33445566778<br/>IFSC: SBIN0001234<br/>Branch: Thuvakudi, Trichy", normal_style),
            Paragraph(
                f"<b>Taxable Value:</b> ₹{invoice.taxable_value:.2f}<br/>"
                + (f"<b>IGST:</b> ₹{invoice.igst_amount:.2f}<br/>" if is_inter else f"<b>CGST:</b> ₹{invoice.cgst_amount:.2f}<br/><b>SGST:</b> ₹{invoice.sgst_amount:.2f}<br/>")
                + f"<b>Invoice Grand Total: ₹{invoice.total_amount:.2f}</b><br/>"
                f"<b>Amount Paid:</b> ₹{invoice.paid_amount:.2f}<br/>"
                f"<b>Balance Due:</b> ₹{invoice.outstanding_amount:.2f}",
                normal_style
            )
        ]
    ]
    summary_table = Table(summary_data, colWidths=[280, 255])
    summary_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 25))

    # Signatures
    sig_data = [
        [
            Paragraph("Customer Acceptance / Seal", normal_style),
            Paragraph(f"For <b>{factory_name}</b><br/><br/><br/>Authorized Signatory", ParagraphStyle('AS', parent=normal_style, alignment=2))
        ]
    ]
    sig_table = Table(sig_data, colWidths=[265, 270])
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()
