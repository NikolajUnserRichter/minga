from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from app.models.invoice import Invoice, InvoiceType

class PDFService:
    @staticmethod
    def generate_invoice_pdf(invoice: Invoice) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        styles = getSampleStyleSheet()
        elements = []
        
        # Header
        # Assuming we have company info, putting placeholder for now
        company_style = ParagraphStyle(
            'CompanyHeader',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30
        )
        elements.append(Paragraph("Minga Greens", company_style))
        
        # Invoice Title
        title = "Rechnung" if invoice.invoice_type == InvoiceType.RECHNUNG else "Gutschrift"
        elements.append(Paragraph(f"{title} Nr. {invoice.invoice_number}", styles['Heading2']))
        elements.append(Spacer(1, 12))
        
        # Meta Info (Date, Customer)
        meta_data = [
            ["Datum:", invoice.invoice_date.strftime("%d.%m.%Y")],
            ["Kunde:", invoice.customer.name],
            ["Kundennummer:", invoice.customer.customer_number or "-"],
        ]
        
        if invoice.customer.billing_address:
             addr = invoice.customer.billing_address
             addr_str = f"{addr.strasse} {addr.hausnummer or ''}, {addr.plz} {addr.ort}"
             meta_data.append(["Anschrift:", addr_str])
             
        meta_table = Table(meta_data, colWidths=[4*cm, 10*cm])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 24))
        
        # Line Items
        data = [["Pos", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt (Netto)"]]
        
        for idx, line in enumerate(invoice.lines, 1):
            data.append([
                str(idx),
                line.description,
                f"{line.quantity:.2f}",
                line.unit,
                f"{line.unit_price:.2f} €",
                f"{line.line_total:.2f} €"
            ])
            
        table = Table(data, colWidths=[1.5*cm, 6*cm, 2*cm, 2*cm, 2.5*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'), # Numbers right aligned
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.white),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 24))
        
        # Totals
        totals_data = [
            ["Netto:", f"{invoice.subtotal:.2f} €"],
            ["USt:", f"{invoice.tax_amount:.2f} €"],
            ["Gesamtbetrag:", f"{invoice.total:.2f} €"]
        ]
        
        totals_table = Table(totals_data, colWidths=[13.5*cm, 3.5*cm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (-1,-1), (-1,-1), 'Helvetica-Bold'), # Total bold
            ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
        ]))
        elements.append(totals_table)
        elements.append(Spacer(1, 24))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey
        )
        elements.append(Paragraph("Vielen Dank für Ihren Auftrag!", styles['Normal']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Minga Greens - Microgreens Farm München", footer_style))
        
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
