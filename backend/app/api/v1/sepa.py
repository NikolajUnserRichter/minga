"""SEPA-Lastschrift (B10): Mandate, Zahlungsart, Einzugsliste.

Nur Admin und Buchhaltung (Rechtegruppe _deps_bank in main.py) — hier und
nur hier stehen volle IBANs in Antworten. Kein SEPA-XML in diesem Schritt.
"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DBSession
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.sepa_mandate import LastschriftStatus, SepaMandat, Zahlungsart
from app.schemas.sepa import (
    MandatCreate, MandatResponse, MandateUebersicht, MandatUpdate,
    WiderrufRequest, WiderrufResponse, ZahlungsartUpdate,
)
from app.services import sepa_service
from app.services.demo_reset_service import DEFAULT_DEMO_SLUG
from app.services.sepa_service import aktives_mandat, glaeubiger_id, heute_berlin, iban_maskiert
from app.tenancy import get_request_tenant

router = APIRouter(prefix="/sepa", tags=["SEPA-Lastschrift"])

#: Demo-Mandant: Die Zugänge (anna/admin, clara/accounting) gehen an
#: Interessenten, und jeder liest dort alles bis zum Reset um 03:30. Deshalb
#: nur diese Beispiel-IBANs (öffentliche Musterkonten), keine echten Bankdaten.
DEMO_BEISPIEL_IBANS = frozenset({"DE89370400440532013000", "DE02120300000000202051"})


def _kunde(db, customer_id: UUID) -> Customer:
    kunde = db.get(Customer, customer_id)
    if kunde is None:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")
    return kunde


def _mandat(db, mandat_id: UUID) -> SepaMandat:
    mandat = db.get(SepaMandat, mandat_id)
    if mandat is None:
        raise HTTPException(status_code=404, detail="Mandat nicht gefunden")
    return mandat


def _referenz_frei(db, referenz: str, ausser: Optional[UUID] = None) -> None:
    abfrage = select(SepaMandat.id).where(SepaMandat.mandatsreferenz == referenz)
    if ausser is not None:
        abfrage = abfrage.where(SepaMandat.id != ausser)
    if db.execute(abfrage).first():
        raise HTTPException(status_code=409, detail=f"Mandatsreferenz {referenz} ist bereits vergeben")


def _anzeige(feld: str, wert):
    """Wert fürs Änderungsprotokoll: IBAN maskiert, Enum/Datum als Text."""
    if feld == "iban" and wert:
        return iban_maskiert(wert)
    if hasattr(wert, "value"):
        return wert.value
    if isinstance(wert, date):
        return wert.isoformat()
    return wert


def _protokolliere(mandat: SepaMandat, user: dict, feld: str, alt, neu) -> None:
    """Eintrag im Änderungsprotokoll des Mandats: {am, von, feld, alt, neu},
    IBAN maskiert. JSON-Spalte ohne Mutationserkennung: neue Liste zuweisen."""
    mandat.aenderungen = list(mandat.aenderungen or []) + [{
        "am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "von": user.get("username"), "feld": feld,
        "alt": _anzeige(feld, alt), "neu": _anzeige(feld, neu),
    }]


def _demo_pruefen(request: Request, iban: Optional[str]) -> None:
    if iban and get_request_tenant(request) == DEFAULT_DEMO_SLUG and iban not in DEMO_BEISPIEL_IBANS:
        raise HTTPException(
            status_code=422,
            detail="Demo: bitte nur Beispiel-IBANs eintragen "
                   "(DE89 3704 0044 0532 0130 00 oder DE02 1203 0000 0000 2020 51)",
        )


def _hat_festgeschriebene_rechnungen(db, mandat: SepaMandat) -> bool:
    """sepa_mandat_id setzt nur das Festschreiben (Q5.5)."""
    return db.execute(
        select(Invoice.id).where(Invoice.sepa_mandat_id == mandat.id).limit(1)
    ).first() is not None


@router.get("/kunden/{customer_id}/mandate", response_model=MandateUebersicht)
def list_mandate(customer_id: UUID, db: DBSession):
    """Alle Mandate des Kunden (aktives zuerst), Zahlungsart und Gläubiger-ID."""
    kunde = _kunde(db, customer_id)
    mandate = db.execute(
        select(SepaMandat).where(SepaMandat.customer_id == customer_id)
        .order_by(SepaMandat.aktiv.desc(), SepaMandat.created_at.desc())
    ).scalars().all()
    return MandateUebersicht(
        customer_id=kunde.id,
        zahlungsart=kunde.zahlungsart,
        glaeubiger_id=glaeubiger_id(db),
        mandate=[MandatResponse.model_validate(m) for m in mandate],
    )


@router.post("/kunden/{customer_id}/mandate", response_model=MandatResponse, status_code=201)
def create_mandat(customer_id: UUID, data: MandatCreate, request: Request, db: DBSession, user: CurrentUser):
    """Mandat anlegen. 409 bei schon aktivem Mandat oder vergebener Referenz."""
    _kunde(db, customer_id)
    _demo_pruefen(request, data.iban)
    if aktives_mandat(db, customer_id) is not None:
        raise HTTPException(status_code=409, detail="Kunde hat bereits ein aktives Mandat — erst widerrufen")
    _referenz_frei(db, data.mandatsreferenz)
    mandat = SepaMandat(customer_id=customer_id, created_by=user.get("username"), **data.model_dump())
    db.add(mandat)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Aktives Mandat oder Mandatsreferenz bereits vorhanden")
    db.refresh(mandat)
    return mandat


@router.patch("/mandate/{mandat_id}", response_model=MandatResponse)
def update_mandat(mandat_id: UUID, data: MandatUpdate, request: Request, db: DBSession, user: CurrentUser):
    """Aktives Mandat ändern; jede Änderung steht im Änderungsprotokoll (IBAN
    maskiert). IBAN, BIC, Bank und Kontoinhaber bleiben änderbar (Kontowechsel
    unter demselben Mandat). Referenz, Datum und Art sind fest, sobald eine
    Rechnung mit diesem Mandat festgeschrieben ist: deren Vorabankündigung
    nennt die Referenz, und Einzugsliste, Einreichung und Zahlung müssen dazu
    passen. Festgeschriebene Rechnungen behalten ihren Hinweis (Snapshot)."""
    mandat = _mandat(db, mandat_id)
    if not mandat.aktiv:
        raise HTTPException(status_code=409, detail="Widerrufene Mandate sind nicht änderbar")
    neu = data.model_dump(exclude_unset=True)
    for feld in ("kontoinhaber", "mandatsart", "mandatsreferenz", "unterschrieben_am", "iban"):
        if feld in neu and neu[feld] is None:
            raise HTTPException(status_code=422, detail=f"{feld} darf nicht leer sein")
    _demo_pruefen(request, neu.get("iban"))
    fest = [f for f in ("mandatsreferenz", "unterschrieben_am", "mandatsart")
            if f in neu and neu[f] != getattr(mandat, f)]
    if fest and (mandat.letzter_einzug_am is not None or _hat_festgeschriebene_rechnungen(db, mandat)):
        raise HTTPException(
            status_code=409,
            detail="Referenz, Datum und Art sind fest, sobald eine Rechnung mit diesem Mandat "
                   "festgeschrieben ist — für eine Änderung das Mandat widerrufen und ein neues anlegen",
        )
    if "mandatsreferenz" in neu:
        _referenz_frei(db, neu["mandatsreferenz"], ausser=mandat.id)

    for feld, wert in neu.items():
        alt = getattr(mandat, feld)
        if alt == wert:
            continue
        _protokolliere(mandat, user, feld, alt, wert)
        setattr(mandat, feld, wert)
    try:
        db.commit()
    except IntegrityError:
        # Zwischen Prüfung und Speichern hat ein anderer Vorgang die Referenz
        # vergeben. Ohne Abfangen: 500, und die SQL-Meldung samt neuer IBAN
        # stünde im Log.
        db.rollback()
        raise HTTPException(status_code=409, detail="Mandatsreferenz bereits vergeben")
    db.refresh(mandat)
    return mandat


@router.post("/mandate/{mandat_id}/widerruf", response_model=WiderrufResponse)
def widerrufe_mandat(mandat_id: UUID, data: WiderrufRequest, db: DBSession, user: CurrentUser):
    """Mandat widerrufen; der Kunde zahlt danach per Überweisung. Offene
    Lastschriftrechnungen werden gemeldet, nicht umgeschrieben (GoBD).
    Widerruf und Zahlungsartwechsel stehen im Protokoll (wer, wann)."""
    mandat = _mandat(db, mandat_id)
    if not mandat.aktiv:
        raise HTTPException(status_code=409, detail="Mandat ist bereits widerrufen")
    widerrufen_am = data.widerrufen_am or heute_berlin()
    if widerrufen_am < mandat.unterschrieben_am:
        raise HTTPException(status_code=422, detail="Datum des Widerrufs liegt vor der Unterschrift des Mandats")
    mandat.aktiv = False
    mandat.widerrufen_am = widerrufen_am
    _protokolliere(mandat, user, "widerrufen_am", None, widerrufen_am)
    kunde = db.get(Customer, mandat.customer_id)
    if kunde.zahlungsart == Zahlungsart.LASTSCHRIFT:
        _protokolliere(mandat, user, "zahlungsart", kunde.zahlungsart, Zahlungsart.UEBERWEISUNG)
        kunde.zahlungsart = Zahlungsart.UEBERWEISUNG
    offene = db.execute(
        select(Invoice.invoice_number).where(
            Invoice.sepa_mandat_id == mandat.id,
            Invoice.lastschrift_status == LastschriftStatus.AUSSTEHEND,
            # Stornierte Rechnungen sind erledigt, auch wenn ihr Einzug "ausstehend" blieb
            Invoice.status.in_((InvoiceStatus.OFFEN, InvoiceStatus.TEILBEZAHLT, InvoiceStatus.UEBERFAELLIG)),
            Invoice.total > Invoice.paid_amount,
        ).order_by(Invoice.invoice_number)
    ).scalars().all()
    db.commit()
    db.refresh(mandat)
    return WiderrufResponse(
        mandat=MandatResponse.model_validate(mandat),
        zahlungsart=kunde.zahlungsart,
        offene_lastschriften=list(offene),
    )


@router.put("/kunden/{customer_id}/zahlungsart")
def set_zahlungsart(customer_id: UUID, data: ZahlungsartUpdate, db: DBSession, user: CurrentUser):
    """Überweisung ↔ Lastschrift. Lastschrift verlangt aktives Mandat und
    Gläubiger-ID. Der Wechsel steht im Protokoll des aktiven Mandats (wer, wann)."""
    kunde = _kunde(db, customer_id)
    mandat = aktives_mandat(db, customer_id)
    if data.zahlungsart == Zahlungsart.LASTSCHRIFT:
        if mandat is None:
            raise HTTPException(status_code=422, detail="Für Lastschrift zuerst ein aktives SEPA-Mandat anlegen")
        if not glaeubiger_id(db):
            raise HTTPException(status_code=422, detail="Gläubiger-ID fehlt in den Firmeneinstellungen")
    if mandat is not None and kunde.zahlungsart != data.zahlungsart:
        _protokolliere(mandat, user, "zahlungsart", kunde.zahlungsart, data.zahlungsart)
    kunde.zahlungsart = data.zahlungsart
    db.commit()
    return {"customer_id": str(kunde.id), "zahlungsart": kunde.zahlungsart}
