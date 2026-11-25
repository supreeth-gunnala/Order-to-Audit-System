import csv
from io import BytesIO
from decimal import Decimal
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def export_csv_response(filename: str, headers: list, rows: list) -> HttpResponse:
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([str(cell) if cell is not None else '' for cell in row])
    return response


def export_excel_response(filename: str, sheet_title: str, headers: list, rows: list) -> HttpResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    # Header styling
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='1A365D', end_color='1A365D', fill_type='solid')
    border_thin = Border(
        left=Side(style='thin', color='CBD5E0'),
        right=Side(style='thin', color='CBD5E0'),
        top=Side(style='thin', color='CBD5E0'),
        bottom=Side(style='thin', color='CBD5E0')
    )

    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for row_idx, row in enumerate(rows, start=2):
        ws.append(row)
        for col_num in range(1, len(row) + 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.border = border_thin
            if isinstance(cell.value, (int, float, Decimal)):
                cell.alignment = Alignment(horizontal='right')

    # Auto-adjust column width
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    return response


def export_pdf_table_response(filename: str, title: str, headers: list, rows: list, is_landscape: bool = False) -> HttpResponse:
    buffer = BytesIO()
    pagesize = landscape(A4) if is_landscape else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=20,
        leftMargin=20,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'RepTitle',
        parent=styles['Heading2'],
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#1a365d')
    )
    header_style = ParagraphStyle(
        'RepHeader',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    cell_style = ParagraphStyle(
        'RepCell',
        parent=styles['Normal'],
        fontSize=7,
        leading=9
    )

    story = [
        Paragraph(f"<b>Sri Krishna Food Products - {title}</b>", title_style),
        Paragraph("Confidential Management & Audit Report", styles['Normal']),
        Spacer(1, 12)
    ]

    table_data = [[Paragraph(f"<b>{h}</b>", header_style) for h in headers]]
    for r in rows:
        table_data.append([Paragraph(str(c if c is not None else ''), cell_style) for c in r])

    col_count = len(headers)
    avail_width = 800 if is_landscape else 550
    col_width = avail_width / col_count

    t = Table(table_data, colWidths=[col_width] * col_count)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#a0aec0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response
