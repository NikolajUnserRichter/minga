from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from app.models.invoice import Invoice, InvoiceType
from app.models.order import Order
from app.models.documents import OrderConfirmation, DeliveryNote, PackingList

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

    # ==================== BELEGKETTE: AB / Lieferschein / Packliste ====================

    @staticmethod
    def _build_document(title: str, doc_number: str, order: Order, body_elements: list) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        company_style = ParagraphStyle('CompanyHeader', parent=styles['Heading1'], fontSize=16, spaceAfter=20)
        elements.append(Paragraph("Minga Greens", company_style))
        elements.append(Paragraph(f"{title} Nr. {doc_number}", styles['Heading2']))
        elements.append(Spacer(1, 10))

        # Meta
        meta_data = [
            ["Bestellung:", order.order_number],
            ["Datum:", (order.order_date.strftime("%d.%m.%Y") if order.order_date else "-")],
            ["Kunde:", order.customer.name if order.customer else "-"],
        ]
        if order.customer and order.customer.customer_number:
            meta_data.append(["Kundennummer:", order.customer.customer_number])
        if order.delivery_address:
            addr = order.delivery_address
            parts = [addr.get("strasse",""), addr.get("hausnummer","")]
            addr_line = " ".join(p for p in parts if p)
            city = f"{addr.get('plz','')} {addr.get('ort','')}".strip()
            meta_data.append(["Lieferadresse:", f"{addr_line}, {city}".strip(", ")])
        if order.requested_delivery_date:
            meta_data.append(["Lieferdatum:", order.requested_delivery_date.strftime("%d.%m.%Y")])

        meta_table = Table(meta_data, colWidths=[4*cm, 13*cm])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 18))

        elements.extend(body_elements)
        elements.append(Spacer(1, 24))

        footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
        elements.append(Paragraph("Minga Greens - Microgreens Farm München", footer_style))
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    @staticmethod
    def generate_confirmation_pdf(conf: OrderConfirmation) -> bytes:
        order = conf.order
        styles = getSampleStyleSheet()
        body = []
        # Positions-Tabelle
        data = [["Pos", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt (Netto)"]]
        for line in order.lines:
            data.append([
                str(line.position),
                line.beschreibung or "-",
                f"{line.quantity:.2f}",
                line.unit,
                f"{line.unit_price:.2f} €",
                f"{line.line_net:.2f} €",
            ])
        table = Table(data, colWidths=[1.2*cm, 7*cm, 2*cm, 2*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        body.append(table)
        body.append(Spacer(1, 16))

        totals_data = [
            ["Netto:", f"{order.total_net:.2f} €"],
            [f"MwSt:", f"{order.total_vat:.2f} €"],
            ["Gesamt:", f"{order.total_gross:.2f} €"],
        ]
        totals_table = Table(totals_data, colWidths=[13*cm, 3.5*cm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
        ]))
        body.append(totals_table)
        body.append(Spacer(1, 12))
        body.append(Paragraph("Wir bestätigen hiermit Ihren Auftrag wie oben aufgeführt.", styles['Normal']))
        if conf.notes:
            body.append(Spacer(1, 8))
            body.append(Paragraph(f"<i>{conf.notes}</i>", styles['Normal']))

        return PDFService._build_document("Auftragsbestätigung", conf.confirmation_number, order, body)

    @staticmethod
    def generate_delivery_note_pdf(note: DeliveryNote) -> bytes:
        order = note.order
        styles = getSampleStyleSheet()
        body = []

        data = [["Pos", "Beschreibung", "Menge", "Einheit"]]
        for line in order.lines:
            data.append([
                str(line.position),
                line.beschreibung or "-",
                f"{line.quantity:.2f}",
                line.unit,
            ])
        table = Table(data, colWidths=[1.2*cm, 9*cm, 3*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        body.append(table)
        body.append(Spacer(1, 16))

        body.append(Paragraph(
            "Bitte prüfen Sie die Ware bei Annahme und quittieren Sie den Empfang.",
            styles['Normal']
        ))
        body.append(Spacer(1, 30))

        sig_data = [
            ["Datum / Unterschrift Empfänger:", ""],
            ["", "_" * 40],
        ]
        sig_table = Table(sig_data, colWidths=[7*cm, 10*cm])
        sig_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
        body.append(sig_table)
        if note.notes:
            body.append(Spacer(1, 12))
            body.append(Paragraph(f"<i>{note.notes}</i>", styles['Normal']))

        return PDFService._build_document("Lieferschein", note.delivery_note_number, order, body)

    @staticmethod
    def generate_packing_list_pdf(packing: PackingList) -> bytes:
        note = packing.delivery_note
        order = note.order
        styles = getSampleStyleSheet()
        body = []

        # Produkt-Items
        product_items = [i for i in packing.items if not i.is_returnable_container]
        container_items = [i for i in packing.items if i.is_returnable_container]

        body.append(Paragraph("<b>Inhalt</b>", styles['Normal']))
        body.append(Spacer(1, 6))
        if product_items:
            data = [["Pos", "Produkt", "Menge", "Einheit", "Charge"]]
            for item in product_items:
                data.append([
                    str(item.sort_order or "—"),
                    item.product_name,
                    f"{item.quantity:.2f}",
                    item.unit,
                    item.batch_number or "—",
                ])
            t = Table(data, colWidths=[1.2*cm, 8*cm, 2.5*cm, 2*cm, 3*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN', (2,1), (3,-1), 'RIGHT'),
            ]))
            body.append(t)
        else:
            body.append(Paragraph("Keine Produkt-Positionen.", styles['Normal']))
        body.append(Spacer(1, 16))

        if container_items:
            body.append(Paragraph("<b>Pfand-Container (Mehrweg)</b>", styles['Normal']))
            body.append(Spacer(1, 6))
            data = [["Container-Typ", "Anzahl"]]
            for item in container_items:
                data.append([item.container_type or item.product_name, str(item.container_count or int(item.quantity))])
            t = Table(data, colWidths=[10*cm, 4*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN', (1,1), (1,-1), 'RIGHT'),
            ]))
            body.append(t)
            body.append(Spacer(1, 16))

        # Summenblock
        summary = []
        if packing.total_weight_g is not None:
            summary.append(["Gesamtgewicht:", f"{packing.total_weight_g:.0f} g"])
        if packing.total_packages is not None:
            summary.append(["Anzahl Packstücke:", str(packing.total_packages)])
        if summary:
            t = Table(summary, colWidths=[5*cm, 4*cm])
            t.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')]))
            body.append(t)

        if packing.notes:
            body.append(Spacer(1, 10))
            body.append(Paragraph(f"<i>{packing.notes}</i>", styles['Normal']))

        # Verknüpfung zum Lieferschein
        body.append(Spacer(1, 12))
        body.append(Paragraph(
            f"<font size=8 color='grey'>Gehört zu Lieferschein {note.delivery_note_number}</font>",
            styles['Normal']
        ))

        return PDFService._build_document("Verpackungsliste", packing.packing_list_number, order, body)
