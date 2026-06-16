from io import BytesIO
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from app.models.invoice import Invoice, InvoiceType
from app.models.order import Order
from app.models.documents import OrderConfirmation, DeliveryNote, PackingList
from app.models.document_template import DocumentType, DEFAULT_SECTIONS, DEFAULT_COLUMNS


COMPANY_KEYS = (
    "COMPANY_NAME", "COMPANY_ADDRESS_LINE1", "COMPANY_ADDRESS_LINE2",
    "COMPANY_USTID", "COMPANY_STEUERNR", "COMPANY_PHONE", "COMPANY_EMAIL",
    "COMPANY_WEBSITE", "COMPANY_BANK_NAME", "COMPANY_IBAN", "COMPANY_BIC",
)


def load_company_settings(db) -> dict[str, str]:
    """Lädt alle COMPANY_*-Settings für PDF-Rendering. Robust gegen None."""
    if db is None:
        return {}
    from app.services.settings_service import get_setting
    return {k: (get_setting(db, k) or "") for k in COMPANY_KEYS}


def render_company_header_block(settings: dict[str, str], logo_path: Optional[str] = None, custom_header_text: Optional[str] = None):
    """Rendert den Briefkopf-Block — Logo (falls vorhanden) + Firmenname + Adresse
    oder Custom-Header-Text aus Template."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Image, Table, TableStyle
    from reportlab.lib import colors

    name = settings.get("COMPANY_NAME") or "Minga Greens"
    addr1 = settings.get("COMPANY_ADDRESS_LINE1") or ""
    addr2 = settings.get("COMPANY_ADDRESS_LINE2") or ""

    if custom_header_text and custom_header_text.strip():
        text_html = custom_header_text.replace("\n", "<br/>")
    else:
        lines = [f"<b>{name}</b>"]
        if addr1: lines.append(addr1)
        if addr2: lines.append(addr2)
        text_html = "<br/>".join(lines)

    style = ParagraphStyle('CompanyHeader', fontSize=10, leading=12, spaceAfter=6)
    text_para = Paragraph(text_html, style)

    if logo_path:
        try:
            logo = Image(logo_path, width=3*cm, height=3*cm, kind="proportional")
            tbl = Table([[logo, text_para]], colWidths=[3.5*cm, 13.5*cm])
            tbl.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            return tbl
        except Exception:
            pass  # bei kaputter Bilddatei → nur Text
    return text_para


def render_company_footer_block(settings: dict[str, str]):
    """Rendert den Fußzeilen-Block mit Bankverbindung + USt-IdNr."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    parts: list[str] = []
    if settings.get("COMPANY_NAME"):
        parts.append(f"<b>{settings['COMPANY_NAME']}</b>")
    if settings.get("COMPANY_ADDRESS_LINE2"):
        parts.append(f"{settings.get('COMPANY_ADDRESS_LINE1', '')} · {settings['COMPANY_ADDRESS_LINE2']}")
    contact_bits = []
    if settings.get("COMPANY_PHONE"):   contact_bits.append(f"Tel.: {settings['COMPANY_PHONE']}")
    if settings.get("COMPANY_EMAIL"):   contact_bits.append(f"E-Mail: {settings['COMPANY_EMAIL']}")
    if settings.get("COMPANY_WEBSITE"): contact_bits.append(settings["COMPANY_WEBSITE"])
    if contact_bits:
        parts.append(" · ".join(contact_bits))
    tax_bits = []
    if settings.get("COMPANY_USTID"):    tax_bits.append(f"USt-IdNr.: {settings['COMPANY_USTID']}")
    if settings.get("COMPANY_STEUERNR"): tax_bits.append(f"Steuernr.: {settings['COMPANY_STEUERNR']}")
    if tax_bits:
        parts.append(" · ".join(tax_bits))
    bank_bits = []
    if settings.get("COMPANY_BANK_NAME"): bank_bits.append(f"Bank: {settings['COMPANY_BANK_NAME']}")
    if settings.get("COMPANY_IBAN"):      bank_bits.append(f"IBAN: {settings['COMPANY_IBAN']}")
    if settings.get("COMPANY_BIC"):       bank_bits.append(f"BIC: {settings['COMPANY_BIC']}")
    if bank_bits:
        parts.append(" · ".join(bank_bits))
    if not parts:
        return None
    style = ParagraphStyle('CompanyFooter', fontSize=7, leading=9, textColor=colors.grey, spaceBefore=8)
    return Paragraph("<br/>".join(parts), style)


class PDFService:
    @staticmethod
    def generate_invoice_pdf(invoice: Invoice, settings: Optional[dict] = None, *, db=None) -> bytes:
        settings = settings or {}
        # Template-Lookup + Section-Toggle-Helper
        tmpl = None
        logo_path = None
        from app.services.document_template_service import section_enabled as _en
        if db is not None:
            from app.services.document_template_service import load_template, get_logo_path
            tmpl = load_template(db, DocumentType.RECHNUNG)
            logo_path = get_logo_path(db, tmpl)

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

        # Briefkopf — Logo + Custom-Header oder Settings-Fallback
        custom_header = (tmpl.texts.get("header_text") if (tmpl and tmpl.texts) else None)
        elements.append(render_company_header_block(settings, logo_path=logo_path, custom_header_text=custom_header))
        elements.append(Spacer(1, 8))
        
        # Invoice Title
        if _en(tmpl, "title", default=True):
            title = "Rechnung" if invoice.invoice_type == InvoiceType.RECHNUNG else "Gutschrift"
            elements.append(Paragraph(f"{title} Nr. {invoice.invoice_number}", styles['Heading2']))
            elements.append(Spacer(1, 12))

        # Meta Info (Date, Customer)
        if _en(tmpl, "meta_block", default=True):
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
        if _en(tmpl, "lines_table", default=True):
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
                ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.white),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 24))

        # Totals
        if _en(tmpl, "totals_block", default=True):
            totals_data = [
                ["Netto:", f"{invoice.subtotal:.2f} €"],
                ["USt:", f"{invoice.tax_amount:.2f} €"],
                ["Gesamtbetrag:", f"{invoice.total:.2f} €"]
            ]
            totals_table = Table(totals_data, colWidths=[13.5*cm, 3.5*cm])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
                ('FONTNAME', (-1,-1), (-1,-1), 'Helvetica-Bold'),
                ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
            ]))
            elements.append(totals_table)
            elements.append(Spacer(1, 16))

        # Skonto-Hinweis wenn Customer Skonto hat
        if _en(tmpl, "skonto_hint", default=True):
            skonto_pct = getattr(invoice.customer, 'skonto_percent', 0) or 0
            skonto_days = getattr(invoice.customer, 'skonto_days', 0) or 0
            if skonto_pct and skonto_days:
                skonto_amount = float(invoice.total) * float(skonto_pct) / 100
                skonto_text = (
                    f"<b>Skonto:</b> Bei Zahlung innerhalb von {skonto_days} Tagen "
                    f"gewähren wir {float(skonto_pct):.1f}% Skonto (entspricht "
                    f"{skonto_amount:.2f} {invoice.currency} Abzug)."
                )
                elements.append(Paragraph(skonto_text, styles['Normal']))
                elements.append(Spacer(1, 8))

        # Reverse-Charge-Vermerk bei steuerfreien Positionen
        if _en(tmpl, "reverse_charge", default=True):
            from app.models.enums import TaxRate
            has_steuerfrei = any(line.tax_rate == TaxRate.STEUERFREI for line in (invoice.lines or []))
            if has_steuerfrei:
                elements.append(Paragraph(
                    "<b>Hinweis:</b> Steuerschuldnerschaft des Leistungsempfängers (Reverse Charge / § 13b UStG).",
                    styles['Normal']
                ))
                elements.append(Spacer(1, 8))

        # Eigentumsvorbehalt — custom text aus Template wenn gesetzt
        if _en(tmpl, "ownership", default=True):
            ownership_text = (
                (tmpl.texts.get("ownership_text") if (tmpl and tmpl.texts) else None)
                or "Ware bleibt bis zur vollständigen Bezahlung unser Eigentum (Eigentumsvorbehalt)."
            )
            elements.append(Paragraph(f"<i>{ownership_text}</i>", styles['Normal']))
            elements.append(Spacer(1, 14))

        # Danke-Text — custom text aus Template wenn gesetzt
        if _en(tmpl, "thanks", default=True):
            thanks_text = (
                (tmpl.texts.get("thanks_text") if (tmpl and tmpl.texts) else None)
                or "Vielen Dank für Ihren Auftrag!"
            )
            elements.append(Paragraph(thanks_text, styles['Normal']))

        # Footer: Custom-Text oder Firmendaten + Bankverbindung
        if _en(tmpl, "footer", default=True):
            elements.append(Spacer(1, 20))
            custom_footer = tmpl.texts.get("footer_text") if (tmpl and tmpl.texts) else None
            if custom_footer and custom_footer.strip():
                footer_style = ParagraphStyle('CustomFooter', fontSize=8, leading=10, textColor=colors.grey)
                elements.append(Paragraph(custom_footer.replace("\n", "<br/>"), footer_style))
            else:
                footer_block = render_company_footer_block(settings)
                if footer_block:
                    elements.append(footer_block)
                else:
                    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
                    elements.append(Paragraph("Minga Greens - Microgreens Farm München", footer_style))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    # ==================== BELEGKETTE: AB / Lieferschein / Packliste ====================

    @staticmethod
    def _build_document(
        title: str,
        doc_number: str,
        order: Order,
        body_elements: list,
        settings: Optional[dict] = None,
        *,
        document_type: Optional[DocumentType] = None,
        db=None,
    ) -> bytes:
        settings = settings or {}
        # Template laden (optional — Code-Defaults greifen wenn keines existiert)
        tmpl = None
        logo_path = None
        if document_type is not None and db is not None:
            from app.services.document_template_service import load_template, get_logo_path, get_text, section_enabled
            tmpl = load_template(db, document_type)
            logo_path = get_logo_path(db, tmpl)

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        # Header-Sektion (Logo + Briefkopf-Text aus Template oder Settings)
        custom_header = None
        if tmpl and tmpl.texts:
            custom_header = tmpl.texts.get("header_text") or None
        # Skip ganze Header-Sektion wenn explizit ausgeschaltet
        from app.services.document_template_service import section_enabled as _en
        if _en(tmpl, "header_logo", default=True):
            elements.append(render_company_header_block(settings, logo_path=logo_path, custom_header_text=custom_header))

        if _en(tmpl, "title", default=True):
            elements.append(Paragraph(f"<b>{title}</b> Nr. {doc_number}", styles['Heading2']))
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

        if _en(tmpl, "meta_block", default=True):
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

        # Footer-Sektion
        if _en(tmpl, "footer", default=True):
            custom_footer = tmpl.texts.get("footer_text") if (tmpl and tmpl.texts) else None
            if custom_footer and custom_footer.strip():
                footer_style = ParagraphStyle('CustomFooter', fontSize=8, leading=10, textColor=colors.grey)
                elements.append(Paragraph(custom_footer.replace("\n", "<br/>"), footer_style))
            else:
                footer_block = render_company_footer_block(settings)
                if footer_block:
                    elements.append(footer_block)
                else:
                    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
                    elements.append(Paragraph("Minga Greens - Microgreens Farm München", footer_style))
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    @staticmethod
    def generate_payment_reminder_pdf(invoice: Invoice, reminder_level: int = 1, dunning_fee: float = 0.0, settings: Optional[dict] = None, *, db=None) -> bytes:
        """Generiert eine Zahlungserinnerung/Mahnung als PDF.

        reminder_level=1 → freundliche Zahlungserinnerung
        reminder_level=2 → erste Mahnung (mit Mahngebühr)
        reminder_level=3 → letzte Mahnung
        """
        settings = settings or {}
        # Template-Lookup
        tmpl = None
        logo_path = None
        if db is not None:
            from app.services.document_template_service import load_template, get_logo_path
            tmpl = load_template(db, DocumentType.MAHNUNG)
            logo_path = get_logo_path(db, tmpl)

        from datetime import date as _date
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        title_map = {
            1: "Zahlungserinnerung",
            2: "1. Mahnung",
            3: "2. Mahnung",
        }
        title = title_map.get(reminder_level, "Zahlungserinnerung")

        from app.services.document_template_service import section_enabled as _en

        # Briefkopf — Logo + Custom-Header
        if _en(tmpl, "header_logo", default=True):
            custom_header = (tmpl.texts.get("header_text") if (tmpl and tmpl.texts) else None)
            elements.append(render_company_header_block(settings, logo_path=logo_path, custom_header_text=custom_header))
            elements.append(Spacer(1, 8))
        if _en(tmpl, "title", default=True):
            elements.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
            elements.append(Spacer(1, 12))

        days_overdue = 0
        if invoice.due_date:
            days_overdue = max(0, (_date.today() - invoice.due_date).days)

        if _en(tmpl, "meta_block", default=True):
            meta = [
                ["Rechnung:", invoice.invoice_number],
                ["Rechnungsdatum:", invoice.invoice_date.strftime("%d.%m.%Y")],
                ["Fällig am:", invoice.due_date.strftime("%d.%m.%Y") if invoice.due_date else "—"],
                ["Tage überfällig:", str(days_overdue)],
                ["Kunde:", invoice.customer.name if invoice.customer else "—"],
            ]
            if invoice.customer and invoice.customer.customer_number:
                meta.append(["Kundennummer:", invoice.customer.customer_number])
            meta_table = Table(meta, colWidths=[4*cm, 13*cm])
            meta_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(meta_table)
            elements.append(Spacer(1, 20))

        # Begründungs-Text je nach Stufe
        if reminder_level == 1:
            body_text = (
                "Sehr geehrte Damen und Herren,<br/><br/>"
                f"wir möchten Sie freundlich daran erinnern, dass die o.g. Rechnung "
                f"über <b>{invoice.total:.2f} {invoice.currency}</b> am "
                f"<b>{invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '—'}</b> "
                "zur Zahlung fällig war.<br/><br/>"
                "Möglicherweise ist Ihre Zahlung mit dieser Erinnerung gekreuzt — "
                "in diesem Fall betrachten Sie dieses Schreiben bitte als gegenstandslos."
            )
        elif reminder_level == 2:
            body_text = (
                "Sehr geehrte Damen und Herren,<br/><br/>"
                f"trotz unserer Zahlungserinnerung ist der offene Betrag der "
                f"Rechnung {invoice.invoice_number} bislang nicht ausgeglichen worden. "
                f"Wir bitten Sie nochmals dringend, den fälligen Betrag inkl. "
                f"Mahngebühr <b>innerhalb von 7 Tagen</b> zu überweisen."
            )
        else:
            body_text = (
                "Sehr geehrte Damen und Herren,<br/><br/>"
                "trotz mehrfacher Mahnung ist unsere Forderung weiterhin offen. "
                "Wir setzen Ihnen hiermit eine letzte Frist von 7 Tagen zur "
                "Zahlung. Anderenfalls werden wir die Forderung kostenpflichtig "
                "an unseren Anwalt zur gerichtlichen Geltendmachung übergeben."
            )

        if _en(tmpl, "body_text", default=True):
            elements.append(Paragraph(body_text, styles['Normal']))
            elements.append(Spacer(1, 18))

        # Betrags-Übersicht
        if _en(tmpl, "amount_block", default=True):
            open_amount = float(invoice.total) - float(invoice.paid_amount or 0)
            totals = [
                ["Rechnungsbetrag:", f"{invoice.total:.2f} {invoice.currency}"],
                ["Bereits gezahlt:", f"{float(invoice.paid_amount or 0):.2f} {invoice.currency}"],
                ["Offener Betrag:", f"{open_amount:.2f} {invoice.currency}"],
            ]
            if dunning_fee > 0:
                totals.append(["Mahngebühr:", f"{dunning_fee:.2f} {invoice.currency}"])
                totals.append(["<b>Zu zahlen gesamt:</b>", f"<b>{open_amount + dunning_fee:.2f} {invoice.currency}</b>"])
            tt = Table(totals, colWidths=[12*cm, 5*cm])
            tt.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
                ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
            ]))
            elements.append(tt)
            elements.append(Spacer(1, 24))

        if _en(tmpl, "regards", default=True):
            elements.append(Paragraph("Mit freundlichen Grüßen", styles['Normal']))
            elements.append(Paragraph("Ihr Minga-Greens-Team", styles['Normal']))
            elements.append(Spacer(1, 20))
        # Footer mit Bankverbindung — bei Mahnung kritisch (Empfänger braucht IBAN)
        if _en(tmpl, "footer", default=True):
            custom_footer = tmpl.texts.get("footer_text") if (tmpl and tmpl.texts) else None
            if custom_footer and custom_footer.strip():
                footer_style = ParagraphStyle('CustomFooter', fontSize=8, leading=10, textColor=colors.grey)
                elements.append(Paragraph(custom_footer.replace("\n", "<br/>"), footer_style))
            else:
                footer_block = render_company_footer_block(settings)
                if footer_block:
                    elements.append(footer_block)
                else:
                    footer = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
                    elements.append(Paragraph(
                        "Minga Greens · Microgreens Farm München · "
                        f"Erstellt am {_date.today().strftime('%d.%m.%Y')}",
                        footer
                    ))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    @staticmethod
    def generate_confirmation_pdf(conf: OrderConfirmation, settings: Optional[dict] = None, *, db=None) -> bytes:
        order = conf.order
        styles = getSampleStyleSheet()
        body = []
        # Template + Section-Toggles für Body
        from app.services.document_template_service import load_template, section_enabled as _en
        tmpl = load_template(db, DocumentType.AUFTRAGSBESTAETIGUNG) if db is not None else None

        # Positions-Tabelle
        if _en(tmpl, "lines_table", default=True):
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

        if _en(tmpl, "totals_block", default=True):
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

        if _en(tmpl, "confirm_text", default=True):
            confirm_text = (tmpl.texts.get("confirm_text") if (tmpl and tmpl.texts) else None) \
                or "Wir bestätigen hiermit Ihren Auftrag wie oben aufgeführt."
            body.append(Paragraph(confirm_text, styles['Normal']))
        if conf.notes:
            body.append(Spacer(1, 8))
            body.append(Paragraph(f"<i>{conf.notes}</i>", styles['Normal']))

        return PDFService._build_document("Auftragsbestätigung", conf.confirmation_number, order, body, settings, document_type=DocumentType.AUFTRAGSBESTAETIGUNG, db=db)

    @staticmethod
    def generate_delivery_note_pdf(note: DeliveryNote, settings: Optional[dict] = None, *, db=None) -> bytes:
        order = note.order
        styles = getSampleStyleSheet()
        body = []
        from app.services.document_template_service import load_template, section_enabled as _en
        tmpl = load_template(db, DocumentType.LIEFERSCHEIN) if db is not None else None

        # Spalten inkl. Charge + MHD (Rückverfolgbarkeit LMHV § 11)
        if _en(tmpl, "lines_table", default=True):
            data = [["Pos", "Beschreibung", "Menge", "Einheit", "Charge", "MHD"]]
            for line in order.lines:
                charge = getattr(line, "batch_number", None) or "—"
                mhd = "—"
                harvest = getattr(line, "harvest", None)
                if harvest:
                    seed_batch = getattr(harvest, "seed_batch", None)
                    if seed_batch and getattr(seed_batch, "mhd", None):
                        mhd = seed_batch.mhd.strftime("%d.%m.%Y")
                data.append([
                    str(line.position),
                    line.beschreibung or "-",
                    f"{line.quantity:.2f}",
                    line.unit,
                    charge,
                    mhd,
                ])
            table = Table(data, colWidths=[1.0*cm, 6.5*cm, 2.2*cm, 1.8*cm, 2.5*cm, 2.5*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (2,1), (3,-1), 'RIGHT'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            body.append(table)
            body.append(Spacer(1, 16))

        if _en(tmpl, "signature", default=True):
            sig_hint = (tmpl.texts.get("signature_hint") if (tmpl and tmpl.texts) else None) \
                or "Bitte prüfen Sie die Ware bei Annahme und quittieren Sie den Empfang."
            body.append(Paragraph(sig_hint, styles['Normal']))
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

        return PDFService._build_document("Lieferschein", note.delivery_note_number, order, body, settings, document_type=DocumentType.LIEFERSCHEIN, db=db)

    @staticmethod
    def generate_packing_list_pdf(packing: PackingList, settings: Optional[dict] = None, *, db=None) -> bytes:
        note = packing.delivery_note
        order = note.order
        styles = getSampleStyleSheet()
        body = []
        from app.services.document_template_service import load_template, section_enabled as _en
        tmpl = load_template(db, DocumentType.VERPACKUNGSLISTE) if db is not None else None

        # Produkt-Items
        product_items = [i for i in packing.items if not i.is_returnable_container]
        container_items = [i for i in packing.items if i.is_returnable_container]

        if _en(tmpl, "products_table", default=True):
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

        if _en(tmpl, "containers", default=True) and container_items:
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
        if _en(tmpl, "summary", default=True):
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

        return PDFService._build_document("Verpackungsliste", packing.packing_list_number, order, body, settings, document_type=DocumentType.VERPACKUNGSLISTE, db=db)
