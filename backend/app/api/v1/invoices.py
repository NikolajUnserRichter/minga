from typing import Optional
"""
Rechnungs-API - Endpoints für Rechnungen, Zahlungen und DATEV-Export
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_

from app.api.deps import DBSession, Pagination
from app.api.deps import CurrentUser
from app.models.invoice import (
    Invoice, InvoiceLine, Payment,
    InvoiceStatus, InvoiceType, PaymentMethod
)
from app.models.documents import DeliveryNote
from app.schemas.invoice import (
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceDetailResponse,
    InvoiceLineCreate, InvoiceLineUpdate, InvoiceLineResponse,
    PaymentBase, PaymentResponse,
    InvoiceSendRequest, InvoiceCancelRequest,
    DatevExportRequest, DatevExportResponse,
)
from app.services.invoice_service import InvoiceService, BereitsAbgerechnet, BestellungStorniert, waehle_vertreter, ist_clearing_pfand, netto_je_lieferschein
from app.services.datev_service import DatevService, erloeskonto_fuer, ist_standard_erloeskonto
from app.services.email_service import EmailNotConfiguredError
from app.services.belegversand import empfaenger_fuer_versand, firmenzusatz, gruss, versende_beleg
from app.core.email_adressen import pruefe_empfaenger
from app.models.enums import DispatchDocType
from app.schemas.documents import DocumentDispatchResponse
from app.services.email_service import pruefe_smtp_konfiguration
from app.services.pdf_service import load_company_settings
from app.services.sepa_service import LastschriftNichtMoeglich, versand_pruefen, zahlungszeile_fuer_mail
from app.services.beleg_dateiname import beleg_dateiname, content_disposition, rechnung_dateiname

router = APIRouter(prefix="/invoices", tags=["Rechnungen"])


def _benutzername(user: dict) -> Optional[str]:
    """Name für den Ausstellungsvermerk (InvoiceService.festschreiben)."""
    return (user or {}).get("username") or (user or {}).get("email")


# ========================================
# INVOICES
# ========================================

@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    db: DBSession,
    pagination: Pagination,
    status: Optional[InvoiceStatus] = None,
    customer_id: Optional[UUID] = None,
    invoice_type: Optional[InvoiceType] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    order_id: Optional[UUID] = None,
):
    """Listet alle Rechnungen mit optionaler Filterung."""
    # Kunde mitladen: customer_name/customer_number lesen invoice.customer —
    # ohne joinedload eine Kundenabfrage je Zeile.
    query = select(Invoice).options(joinedload(Invoice.lines), joinedload(Invoice.customer))

    if status:
        query = query.where(Invoice.status == status)

    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)

    if invoice_type:
        query = query.where(Invoice.invoice_type == invoice_type)

    if order_id:
        # Beide Wege zur Rechnung einer Bestellung — dieselben wie in
        # InvoiceService.aktive_rechnung_zur_bestellung: Rechnung aus
        # Bestellung (order_id) und Sammelrechnung (über den Lieferschein).
        query = query.where(or_(
            Invoice.order_id == order_id,
            Invoice.id.in_(
                select(DeliveryNote.invoice_id).where(
                    DeliveryNote.order_id == order_id,
                    DeliveryNote.invoice_id.is_not(None),
                )
            ),
        ))

    if from_date:
        query = query.where(Invoice.invoice_date >= from_date)

    if to_date:
        query = query.where(Invoice.invoice_date <= to_date)

    # Neueste zuerst, stabil. Am selben Tag entscheidet der Zeitpunkt der
    # Anlage: Entwürfe tragen einen zufälligen Platzhalter (ENTWURF-…), die
    # Nummer sortiert sie nicht (Spec 08.10.2026, Entscheidung 6). Die
    # Nummer bleibt letzter Schlüssel für gleiche Zeitstempel.
    query = query.order_by(
        Invoice.invoice_date.desc(), Invoice.created_at.desc(), Invoice.invoice_number.desc()
    )
    query = query.offset(pagination.offset).limit(pagination.page_size)

    invoices = db.execute(query).scalars().unique().all()
    return invoices


@router.get("/overdue", response_model=list[InvoiceResponse])
def list_overdue_invoices(db: DBSession):
    """Listet alle überfälligen Rechnungen."""
    service = InvoiceService(db)
    ids = [i.id for i in service.check_overdue_invoices()]
    db.commit()
    if not ids:
        return []
    # Der Commit verfällt alle geladenen Objekte. Ohne Neuladen läse die
    # Serialisierung jede Rechnung und ihren Kunden einzeln nach (N+1).
    return db.execute(
        select(Invoice)
        .options(joinedload(Invoice.customer))
        .where(Invoice.id.in_(ids))
    ).scalars().all()


@router.get("/revenue-summary")
def get_revenue_summary(
    from_date: date,
    to_date: date,
    db: DBSession,
):
    """Gibt Umsatzübersicht für Zeitraum zurück."""
    service = InvoiceService(db)
    return service.get_revenue_summary(from_date, to_date)


@router.get("/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice(invoice_id: UUID, db: DBSession):
    """Gibt eine einzelne Rechnung mit allen Details zurück."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    antwort = InvoiceDetailResponse.model_validate(invoice)
    # Rückverweis auf die Stornorechnung — für die Verlinkung beider Belege
    antwort.cancelled_by_invoice_id = db.execute(
        select(Invoice.id).where(Invoice.original_invoice_id == invoice_id)
    ).scalar_one_or_none()
    return antwort


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(data: InvoiceCreate, db: DBSession):
    """Erstellt eine neue Rechnung."""
    service = InvoiceService(db)
    try:
        invoice = service.create_invoice(
            **data.model_dump(exclude={"billing_address", "shipping_address", "lines"})
        )
        
        # Positionen hinzufügen
        if data.lines:
            for line in data.lines:
                service.add_line(
                    invoice_id=invoice.id,
                    **line.model_dump()
                )
        
        db.commit()
        db.refresh(invoice)
        return invoice
    except BereitsAbgerechnet as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/from-order/{order_id}", response_model=InvoiceResponse, status_code=201)
def create_invoice_from_order(order_id: UUID, db: DBSession):
    """Erstellt eine Rechnung aus einer Bestellung."""
    service = InvoiceService(db)
    try:
        invoice = service.create_invoice_from_order(order_id)
        db.commit()
        db.refresh(invoice)
        return invoice
    except (BereitsAbgerechnet, BestellungStorniert) as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    db: DBSession,
):
    """Aktualisiert eine Rechnung (nur Entwürfe)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.status != InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Nur Entwürfe können bearbeitet werden")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(invoice, field, value)

    # Ein geänderter Einmalrabatt muss sofort in den Summen landen — sonst
    # zeigt die Rechnung den alten Betrag, bis irgendwann eine Zeile angefasst wird.
    invoice.calculate_totals()

    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/finalize", response_model=InvoiceResponse)
def finalize_invoice(invoice_id: UUID, db: DBSession, user: CurrentUser):
    """Finalisiert eine Rechnung (Entwurf -> Offen)."""
    service = InvoiceService(db)
    try:
        invoice = service.finalize_invoice(invoice_id, von=_benutzername(user))
        db.commit()
        db.refresh(invoice)
        return invoice
    except BereitsAbgerechnet as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{invoice_id}/payment-reminder")
def generate_payment_reminder(
    invoice_id: UUID,
    db: DBSession,
    level: int = Query(default=1, ge=1, le=3, description="1=Erinnerung, 2=1.Mahnung, 3=2.Mahnung"),
    dunning_fee: float = Query(default=0.0, ge=0.0),
):
    """Generiert eine Zahlungserinnerung / Mahnung als PDF + erhöht reminder_level."""
    from app.models.invoice import Invoice as InvoiceModel
    from app.services.pdf_service import PDFService
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    invoice = db.execute(
        select(InvoiceModel)
        .options(joinedload(InvoiceModel.customer), joinedload(InvoiceModel.lines))
        .where(InvoiceModel.id == invoice_id)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    if invoice.status in (InvoiceStatus.BEZAHLT, InvoiceStatus.STORNIERT):
        raise HTTPException(status_code=400, detail="Bezahlte/stornierte Rechnungen können nicht gemahnt werden")
    if not invoice.mahnfaehig:
        raise HTTPException(
            status_code=400,
            detail="Lastschriftrechnung: der Einzug steht aus oder ist gebucht — Mahnung erst nach einer Rücklastschrift",
        )
    # Ein Entwurf ist nicht ausgestellt — eine Mahnung trüge den Platzhalter.
    if invoice.status == InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Ein Entwurf kann nicht gemahnt werden — die Rechnung zuerst finalisieren")

    pdf = PDFService.generate_payment_reminder_pdf(invoice, reminder_level=level, dunning_fee=dunning_fee, settings=load_company_settings(db), db=db)

    # Mahnstufe persistieren wenn höher
    if level > (invoice.reminder_level or 0):
        invoice.reminder_level = level
        from datetime import datetime as _dt, timezone as _tz
        invoice.last_reminder_sent_at = _dt.now(_tz.utc)
        db.commit()

    filename = f"Zahlungserinnerung_{invoice.invoice_number}_Stufe{level}.pdf"
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{invoice_id}/send", response_model=DocumentDispatchResponse)
def send_invoice_email(
    invoice_id: UUID,
    db: DBSession,
    user: CurrentUser,
    data: Optional[InvoiceSendRequest] = None,
    to_email: Optional[str] = Query(None, description="Veraltet: ein Empfänger; neu ist der JSON-Body"),
):
    """Sendet die Rechnung als PDF-Anhang per E-Mail.

    Ein Entwurf wird vorher über InvoiceService.festschreiben ausgestellt
    (wie /finalize) und committet — aber nur, wenn SMTP konfiguriert ist.
    sent_at setzt nur ein erfolgreicher Versand."""
    from app.models.invoice import Invoice as InvoiceModel  # local import to avoid cycle
    from app.services.pdf_service import PDFService
    from datetime import datetime as _dt, timezone as _tz

    invoice = db.execute(
        select(InvoiceModel)
        .options(joinedload(InvoiceModel.customer), joinedload(InvoiceModel.lines))
        .where(InvoiceModel.id == invoice_id)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    # Die Stornorechnung steht als ausgeglichener Beleg auf STORNIERT, muss
    # aber zum Kunden. Gesperrt ist nur das stornierte Original.
    ist_storno = (
        invoice.invoice_type == InvoiceType.GUTSCHRIFT
        and invoice.original_invoice_id is not None
    )
    if invoice.status == InvoiceStatus.STORNIERT and not ist_storno:
        raise HTTPException(status_code=400, detail="Stornierte Rechnungen können nicht versendet werden")
    if not invoice.lines:
        raise HTTPException(status_code=400, detail="Rechnung hat keine Positionen")
    # SEPA-Lastschrift (B10, Q5) — vor Empfängern, Festschreiben und Versand:
    # Entwurf eines Lastschriftkunden ohne Mandat/Gläubiger-ID → 400, bleibt
    # Entwurf; festgeschriebene Lastschriftrechnung mit widerrufenem Mandat
    # oder zu spätem Erstversand (Vorabankündigungsfrist) → 409.
    try:
        versand_pruefen(db, invoice)
    except LastschriftNichtMoeglich as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Empfänger VOR dem Festschreiben klären (Paket 3, Q2): ohne gültige
    # Empfänger bleibt ein Entwurf Entwurf und verbraucht keine Nummer.
    # Body `to`/`cc` oder `use_customer_recipients`; der Query-Parameter
    # `to_email` bleibt für ältere Aufrufer. Die Antwort ist die neue
    # Zeile im Versandprotokoll.
    try:
        to = data.to if data and data.to else None
        if not to and to_email:
            to = pruefe_empfaenger([to_email], feld="to_email")
        an, cc = empfaenger_fuer_versand(
            invoice.customer, DispatchDocType.RE,
            to=to, cc=data.cc if data else [],
            use_customer_recipients=bool(data and data.use_customer_recipients),
        )
    except ValueError as e:  # auch KeinEmpfaenger und die Obergrenze An + Cc
        raise HTTPException(status_code=400, detail=str(e))
    if not an:
        raise HTTPException(status_code=400, detail="Kein Empfänger angegeben")

    # Mailen eines Entwurfs stellt ihn aus — mit derselben Funktion wie
    # /finalize (Summen, Datum, Nummer, Status). Festgeschrieben und
    # committet wird VOR dem Versand: Betreff, Dateiname und PDF tragen die
    # echte Rechnungsnummer, und die Schreibsperre der Mandanten-DB ist
    # während des SMTP-Versands wieder frei. Scheitert der Versand, bleibt
    # die Rechnung festgeschrieben und unversendet (sent_at leer); eine
    # vergebene Nummer wird nie zurückgenommen (lückenlos, GoBD).
    # Ohne SMTP-Einstellungen scheiterte der Versand sicher: dann wird gar
    # nicht erst festgeschrieben, der Entwurf bleibt Entwurf.
    vorher_entwurf = invoice.status == InvoiceStatus.ENTWURF
    if vorher_entwurf:
        # Paket 2.1: Gibt es zur Bestellung schon eine festgeschriebene
        # Rechnung, antwortet /send mit 409 — vor der SMTP-Prüfung, damit
        # die Meldung auch ohne SMTP die richtige ist. festschreiben prüft
        # dasselbe noch einmal unter der Schreibsperre.
        try:
            InvoiceService(db).pruefe_festschreibung(invoice)
        except BereitsAbgerechnet as e:
            raise HTTPException(status_code=409, detail=str(e))
        try:
            pruefe_smtp_konfiguration(db)
        except EmailNotConfiguredError as e:
            raise HTTPException(status_code=503, detail=f"{e} Der Entwurf bleibt Entwurf.")
        try:
            InvoiceService(db).festschreiben(invoice, von=_benutzername(user))
        except BereitsAbgerechnet as e:
            raise HTTPException(status_code=409, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        db.commit()
        db.refresh(invoice)
    nicht_versendet = (
        f"Rechnung {invoice.invoice_number} ist finalisiert, aber nicht versendet. "
        if vorher_entwurf else ""
    )

    try:
        pdf = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
        # Mailtext erst hier: ein Entwurf ist oben bereits neu berechnet (Task 11)
        if ist_storno:
            original = invoice.original_invoice
            betreff = f"Stornorechnung {invoice.invoice_number}{firmenzusatz(db)}"
            text = (
                f"Sehr geehrte Damen und Herren bei {invoice.customer.name},\n\n"
                f"anbei finden Sie die Stornorechnung {invoice.invoice_number} zur Rechnung "
                f"{original.invoice_number if original else '—'}.\n"
                f"Die Rechnung ist damit vollständig aufgehoben.\n\n"
                f"{gruss(db)}"
            )
        else:
            betreff = f"Rechnung {invoice.invoice_number}{firmenzusatz(db)}"
            text = (
                f"Sehr geehrte Damen und Herren bei {invoice.customer.name},\n\n"
                f"anbei finden Sie die Rechnung {invoice.invoice_number} über\n"
                f"{invoice.total:.2f} {invoice.currency}.\n\n"
                # Lastschrift: eingefrorener Hinweis statt "Fällig am" (B10)
                f"{zahlungszeile_fuer_mail(invoice)}\n\n"
                f"{gruss(db)}"
            )
        eintrag = versende_beleg(
            db,
            doc_type=DispatchDocType.RE,
            document_number=invoice.invoice_number,
            an=an,
            cc=cc,
            betreff=betreff,
            text=text,
            pdf=pdf,
            user=user,
            customer_id=invoice.customer_id,
            order_id=invoice.order_id,
            invoice_id=invoice.id,
        )
    except EmailNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=f"{nicht_versendet}{e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{nicht_versendet}E-Mail-Versand fehlgeschlagen: {e}")

    # sent_at: erster erfolgreicher Mailversand (B2); maßgeblich ist das Protokoll
    if invoice.sent_at is None:
        invoice.sent_at = _dt.now(_tz.utc)
    db.commit()
    db.refresh(eintrag)
    return eintrag


@router.post("/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: UUID,
    data: InvoiceCancelRequest,
    db: DBSession,
    user: CurrentUser,
):
    """Storniert eine Rechnung und erstellt optional eine Stornorechnung.

    `warnungen` nennt, was der Storno nicht selbst lösen kann (bereits
    gezahltes Geld, Kopie in lexoffice) — die Oberfläche zeigt sie an.
    """
    service = InvoiceService(db)
    try:
        # Auswahlgrund + Freitext zusammen — beides gehört in die Akte (R1.4)
        grund = f"[{data.reason_code}] {data.reason}" if data.reason_code else data.reason
        invoice, credit_note = service.cancel_invoice(
            invoice_id=invoice_id,
            reason=grund,
            create_credit_note=data.create_credit_note,
            von=_benutzername(user),
        )
        db.commit()
        return {
            "invoice": InvoiceResponse.model_validate(invoice),
            "credit_note": InvoiceResponse.model_validate(credit_note) if credit_note else None,
            "warnungen": service.storno_warnungen(invoice),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{invoice_id}", status_code=204)
def discard_invoice_draft(invoice_id: UUID, db: DBSession):
    """Verwirft einen Entwurf ohne Rechnungsnummer (Platzhalter ENTWURF-…).

    Keine Nummer, also keine Lücke; zugeordnete Lieferscheine werden wieder
    abrechenbar. Finalisierte Rechnungen und Altentwürfe mit RE-Nummer: 409.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    try:
        InvoiceService(db).entwurf_verwerfen(invoice)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()


# ========================================
# INVOICE LINES
# ========================================

@router.post("/{invoice_id}/lines", response_model=InvoiceLineResponse, status_code=201)
def add_invoice_line(
    invoice_id: UUID,
    data: InvoiceLineCreate,
    db: DBSession,
):
    """Fügt eine Position zur Rechnung hinzu."""
    service = InvoiceService(db)
    try:
        line = service.add_line(
            invoice_id=invoice_id,
            **data.model_dump(),
        )
        db.commit()
        db.refresh(line)
        return line
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{invoice_id}/lines/{line_id}", response_model=InvoiceLineResponse)
def update_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    data: InvoiceLineUpdate,
    db: DBSession,
):
    """Aktualisiert eine Rechnungsposition."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.status != InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Nur Entwürfe können bearbeitet werden")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    satz_vorher = line.tax_rate
    for field, value in update_data.items():
        setattr(line, field, value)

    # Das Erlöskonto hängt am Steuersatz (8300/8400/8100). Ohne Nachziehen
    # buchte der DATEV-Export eine auf 19 % korrigierte Zeile weiter auf 8300.
    # Ein Sonderkonto bleibt — dieselbe Regel wie der DATEV-Export (S4).
    if line.tax_rate != satz_vorher and ist_standard_erloeskonto(line.buchungskonto):
        line.buchungskonto = erloeskonto_fuer(line.tax_rate)

    # Zeile und Rechnung neu berechnen
    line.calculate_line_total()
    InvoiceService(db).recalculate_totals(invoice)

    db.commit()
    db.refresh(line)
    return line


@router.delete("/{invoice_id}/lines/{line_id}", status_code=204)
def delete_invoice_line(
    invoice_id: UUID,
    line_id: UUID,
    db: DBSession,
):
    """Löscht eine Rechnungsposition."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    if invoice.status != InvoiceStatus.ENTWURF:
        raise HTTPException(status_code=400, detail="Nur Entwürfe können bearbeitet werden")

    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    db.delete(line)
    # Erst löschen, dann die Positionen neu laden, dann rechnen — sonst zählt
    # die gelöschte Zeile in Summe, USt und Pfand weiter mit (B4).
    InvoiceService(db).recalculate_totals(invoice)
    db.commit()


# ========================================
# PAYMENTS
# ========================================

@router.get("/{invoice_id}/payments", response_model=list[PaymentResponse])
def list_invoice_payments(invoice_id: UUID, db: DBSession):
    """Listet alle Zahlungen einer Rechnung."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return invoice.payments


@router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=201)
def record_payment(
    invoice_id: UUID,
    data: PaymentBase,
    db: DBSession,
):
    """Erfasst eine Zahlung für eine Rechnung."""
    service = InvoiceService(db)
    try:
        payment = service.record_payment(
            invoice_id=invoice_id,
            **data.model_dump(),
        )
        db.commit()
        db.refresh(payment)
        return payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========================================
# DATEV EXPORT
# ========================================

@router.post("/datev-export")
def export_datev(
    data: DatevExportRequest,
    db: DBSession,
):
    """Exportiert Rechnungen im DATEV-Format."""
    service = DatevService(db)
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
        erneut_exportieren=data.erneut_exportieren,
    )
    db.commit()

    return DatevExportResponse(
        csv_content=csv_content,
        record_count=record_count,
        total_amount=total_amount,
        filename=f"DATEV_Export_{data.from_date}_{data.to_date}.csv",
        export_date=datetime.now(timezone.utc),
    )


@router.post("/datev-export/download")
def download_datev_export(
    data: DatevExportRequest,
    db: DBSession,
):
    """Exportiert Rechnungen als DATEV CSV-Datei zum Download."""
    service = DatevService(db)
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
        erneut_exportieren=data.erneut_exportieren,
    )
    db.commit()

    filename = f"DATEV_Export_{data.from_date}_{data.to_date}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        }
    )

@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    db: DBSession,
):
    """Generiert ein PDF für die Rechnung."""
    # Lines + Customer eager laden — PDF-Service iteriert über invoice.lines
    # (Reverse-Charge-Check) und liest customer.billing_address; bei lazy
    # load würde das in strikten Async-Contexts crashen.
    invoice = db.execute(
        select(Invoice)
        .options(joinedload(Invoice.lines), joinedload(Invoice.customer))
        .where(Invoice.id == invoice_id)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    from app.services.pdf_service import PDFService
    pdf_content = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        # B7: Dateiname = Rechnungsnummer, Entwurf → "Entwurf-….pdf"
        headers={"Content-Disposition": content_disposition(rechnung_dateiname(invoice))},
    )


# =====================================================================
# Sammelrechnung (Warenfluss-Release, AP2)
#
# Ein Lauf je Zeitraum: alle nicht abgerechneten Lieferscheine der Kunden
# werden je Artikel + Einheit + Einzelpreis + Steuersatz aggregiert.
# Vorschau rechnet nur. Der Lauf legt je Kunde einen Rechnungsentwurf an
# und setzt delivery_notes.invoice_id — der Doppelabrechnungsschutz (R2.5).
# Die Rechnungsnummer vergibt erst InvoiceService.festschreiben (Spec
# 08.10.2026, Entscheidung 6).
# =====================================================================

from pydantic import BaseModel as _BaseModel, Field as _Field

from app.models.documents import DeliveryNote
from app.models.enums import OrderStatus
from app.models.invoice import InvoiceLineSource
from app.models.order import Order, OrderLine
from app.services.steuersatz import produkt_der_position, steuersatz_der_position


class BatchRunRequest(_BaseModel):
    period_from: date
    period_to: date
    customer_ids: Optional[list[UUID]] = _Field(None, description="leer = alle Kunden")
    invoice_date: Optional[date] = None


def _abrechenbare_lieferscheine(db, anfrage: BatchRunRequest):
    """Je noch nicht abgerechneter Bestellung genau EIN Lieferschein des Zeitraums.

    Abgerechnet wird die Bestellung, nicht der Lieferschein: _aggregiere
    zählt order.lines je zurückgegebenem Lieferschein. Deshalb
    - fällt jede Bestellung heraus, die schon in einer nicht stornierten
      Rechnung steckt — über Invoice.order_id (Rechnung aus Bestellung, auch
      Altbestand ohne Lieferschein-Zuordnung) oder über einen bereits
      zugeordneten Lieferschein (Sammelrechnung);
    - steht jede Bestellung höchstens einmal in der Liste, auch wenn sie
      mehrere Lieferscheine hat (Vertreter: waehle_vertreter).
    Vorschau und Festschreiben rufen beide diese Funktion — eine Regel.

    Leistungsdatum: das tatsächliche Lieferdatum des Vertreters, ersatzweise
    das tatsächliche oder das Wunschlieferdatum der Bestellung. Stornierte und fakturierte
    Bestellungen bleiben draußen — FAKTURIERT gilt als abgerechnet, auch ohne
    Rechnung im System (Spec-Nachtrag 08.10.2026).
    """
    abgerechnet = InvoiceService(db).abgerechnete_bestellungen()
    notes = db.execute(
        select(DeliveryNote)
        .join(Order, DeliveryNote.order_id == Order.id)
        .where(
            DeliveryNote.invoice_id.is_(None),
            # STORNIERT nie. FAKTURIERT heißt: schon abgerechnet, auch wenn die
            # Rechnung nicht im System steht (Spec-Nachtrag 08.10.2026,
            # Sofort-Fix der Doppelabrechnungssperre).
            Order.status.notin_([OrderStatus.STORNIERT, OrderStatus.FAKTURIERT]),
        )
    ).scalars().all()

    je_bestellung: dict = {}
    for note in notes:
        if note.order_id in abgerechnet:
            continue
        je_bestellung.setdefault(note.order_id, []).append(note)

    ergebnis = []
    for kandidaten in je_bestellung.values():
        note = waehle_vertreter(kandidaten)
        leistungsdatum = (
            note.actual_delivery_date or note.order.actual_delivery_date
            or note.order.requested_delivery_date
        )
        if not (anfrage.period_from <= leistungsdatum <= anfrage.period_to):
            continue
        if anfrage.customer_ids and note.order.customer_id not in anfrage.customer_ids:
            continue
        ergebnis.append((note, leistungsdatum))
    return ergebnis


def _aggregiere(db, notes) -> dict:
    """Je Kunde: Positionen aggregiert nach (Artikel, Einheit, Preis,
    Steuersatz, Produkt, Positionsrabatt).

    Merkt sich je Position, welcher Lieferschein wie viel beigetragen hat —
    daraus entstehen beim Festschreiben die invoice_line_sources (R2.3).

    Produkt und Rabatt gehören in den Schlüssel (A3, 08.10.2026): ohne
    product_id fehlte der Rechnungszeile das Pfandkennzeichen, ohne Rabatt
    fiel der Positionsrabatt still weg. Der Steuersatz kommt aus
    steuersatz_der_position — dieselbe Funktion wie bei der Bestellung und
    der Rechnung aus der Bestellung (InvoiceService.create_invoice_from_order).
    """
    kunden: dict = {}
    for note, leistungsdatum in notes:
        order = note.order
        k = kunden.setdefault(order.customer_id, {
            "customer_id": order.customer_id,
            "customer_name": order.customer.name if order.customer else "—",
            "lieferscheine": [],
            "positionen": {},
        })
        k["lieferscheine"].append(note)
        for line in order.lines:
            # Pfand über IFCO-Clearing steht auf dem Lieferschein, nicht auf
            # der Rechnung — dieselbe Regel wie bei der Rechnung aus Bestellung.
            if ist_clearing_pfand(db, order.customer, line):
                continue
            produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
            satz = steuersatz_der_position(
                db, line.product_id, line.product_variant_id, line.tax_rate
            )
            key = (line.beschreibung or "Position", line.unit,
                   line.unit_price,
                   satz,
                   produkt.id if produkt else None,
                   line.discount_percent or Decimal("0"))
            pos = k["positionen"].setdefault(key, {"menge": Decimal("0"), "quellen": []})
            pos["menge"] += line.quantity
            pos["quellen"].append((note.id, line.quantity))
    # Wer im Zeitraum nur Clearing-Pfand geliefert bekam, bekommt keine leere
    # Rechnung — und taucht auch in der Vorschau nicht auf.
    return {kid: k for kid, k in kunden.items() if k["positionen"]}


@router.post("/batch-run/preview")
def batch_run_preview(anfrage: BatchRunRequest, db: DBSession):
    """Vorschau des Sammelrechnungslaufs — rechnet, schreibt nichts (R2.6)."""
    kunden = _aggregiere(db, _abrechenbare_lieferscheine(db, anfrage))
    return {
        "period_from": anfrage.period_from.isoformat(),
        "period_to": anfrage.period_to.isoformat(),
        "kunden": [{
            "customer_id": str(k["customer_id"]),
            "customer_name": k["customer_name"],
            "anzahl_lieferscheine": len(k["lieferscheine"]),
            "positionen": [{
                "description": key[0], "unit": key[1],
                "unit_price": key[2], "tax_rate": key[3].value,
                "discount_percent": key[5],
                "quantity": pos["menge"],
            } for key, pos in sorted(k["positionen"].items(), key=lambda e: (e[0][0], e[0][2]))],
            "summe_netto": sum((pos["menge"] * key[2] * (1 - key[5] / 100)
                                for key, pos in k["positionen"].items()),
                               Decimal("0")),
        } for k in kunden.values()],
    }


@router.post("/batch-run/commit", status_code=201)
def batch_run_commit(anfrage: BatchRunRequest, db: DBSession):
    """Legt je Kunde einen Rechnungsentwurf an (Platzhalter, keine Nummer)
    und ordnet die Lieferscheine zu (R2.1–R2.5). Freigabe einzeln über
    /finalize; ein verworfener Entwurf (DELETE) gibt die Lieferscheine frei.
    Hat ein gleichzeitiger zweiter Lauf Lieferscheine schon belegt: 409,
    nichts angelegt."""
    kunden = _aggregiere(db, _abrechenbare_lieferscheine(db, anfrage))
    service = InvoiceService(db)
    rechnungen = []

    for k in kunden.values():
        invoice = service.create_invoice(
            customer_id=k["customer_id"],
            invoice_date=anfrage.invoice_date or date.today(),
            header_text=(
                f"Sammelrechnung — Leistungszeitraum "
                f"{anfrage.period_from.strftime('%d.%m.%Y')}–{anfrage.period_to.strftime('%d.%m.%Y')}"
            ),
        )
        invoice.service_period_start = anfrage.period_from
        invoice.service_period_end = anfrage.period_to

        for (beschreibung, unit, preis, steuersatz, produkt_id, rabatt), pos in sorted(
            k["positionen"].items(), key=lambda e: (e[0][0], e[0][2])
        ):
            line = service.add_line(
                invoice_id=invoice.id,
                description=beschreibung,
                quantity=pos["menge"],
                unit=unit,
                unit_price=preis,
                product_id=produkt_id,
                discount_percent=rabatt,
                tax_rate=steuersatz,
            )
            db.flush()
            for note_id, menge in pos["quellen"]:
                db.add(InvoiceLineSource(
                    invoice_line_id=line.id,
                    delivery_note_id=note_id,
                    quantity=menge,
                ))

        # Doppelabrechnungsschutz: ab jetzt hängt der Lieferschein an dieser
        # Rechnung — der nächste Lauf sieht ihn nicht mehr (R2.5). Nur wenn
        # er noch frei ist: ein gleichzeitiger zweiter Lauf bekommt 409.
        try:
            service.lieferscheine_belegen(invoice, k["lieferscheine"])
        except BereitsAbgerechnet as e:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(e))

        # Summen über ALLE Zeilen: die lines-Relationship kann nach dem
        # zeilenweisen add_line noch den alten Stand tragen.
        db.flush()
        db.refresh(invoice)
        invoice.calculate_totals()

        # Bleibt ENTWURF: Nummer, Rechnungsdatum und Fälligkeit setzt erst
        # das Festschreiben (Spec 08.10.2026, Entscheidung 6).
        rechnungen.append(invoice)

    db.commit()
    return {
        "rechnungen": [InvoiceResponse.model_validate(r) for r in rechnungen],
    }


@router.get("/{invoice_id}/delivery-notes")
def invoice_delivery_notes(invoice_id: UUID, db: DBSession):
    """Die in einer (Sammel-)Rechnung enthaltenen Lieferscheine (R2.3)."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")

    notes = db.execute(
        select(DeliveryNote).where(DeliveryNote.invoice_id == invoice_id)
    ).scalars().all()
    # Betrag aus den Positionen dieser Rechnung, nicht aus der Bestellung —
    # sonst zählte Clearing-Pfand mit (dieselbe Regel wie die PDF-Anlage).
    betraege = netto_je_lieferschein(db, invoice, notes)
    return [{
        "id": str(n.id),
        "delivery_note_number": n.delivery_note_number,
        "lieferdatum": (
            n.actual_delivery_date or n.order.actual_delivery_date or n.order.requested_delivery_date
        ).isoformat(),
        "betrag_netto": betraege[n.id],
    } for n in notes]
