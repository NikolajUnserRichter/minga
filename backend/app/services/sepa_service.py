"""SEPA-Lastschrift (B10): Prüfungen, Einzugsdatum, Vorabankündigung, Einzug.

Nur Standardbibliothek plus python-dateutil (requirements.txt). Kein
SEPA-XML in diesem Schritt.

Regeln:
- Die Gläubiger-ID steht einmal in den Firmeneinstellungen und wird OHNE
  Umgebungs-Rückfall gelesen: eine Umgebungsvariable gälte für alle
  Mandanten im Container.
- Zahlungsart, Mandat und Hinweis bestimmt erst das Festschreiben
  (ENTWURF → OFFEN), nie das Anlegen: ein Entwurf kann noch den Kunden
  wechseln. Der Hinweis wird an der Rechnung eingefroren (GoBD).
- Die volle IBAN steht nie in Mail, PDF oder Rechnungsantwort.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from dateutil.easter import easter
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.sepa_mandate import LastschriftStatus, SepaMandat, Zahlungsart

GLAEUBIGER_ID_KEY = "COMPANY_SEPA_GLAEUBIGER_ID"
FRIST_KEY = "SEPA_VORABANKUENDIGUNG_TAGE"
#: Vorabankündigungsfrist ohne abweichende Vereinbarung im Mandat.
STANDARD_FRIST_TAGE = 14


class LastschriftNichtMoeglich(ValueError):
    """Lastschriftkunde, aber Festschreiben als Lastschrift unmöglich (kein
    aktives Mandat, keine Gläubiger-ID). Kein stiller Rückfall auf
    Überweisung: die Rechnung bleibt Entwurf. ValueError, damit die
    vorhandenen Endpunkte (finalize: except ValueError → 400) greifen."""


# --------------------------------------------------------------------------
# Prüfungen (ISO 13616 Modulo 97)
# --------------------------------------------------------------------------

def _als_zahl(zeichen: str) -> int:
    """Buchstaben → Zahlen (A=10 … Z=35), Ziffern bleiben."""
    return int("".join(str(int(c, 36)) for c in zeichen))


def iban_normalisieren(wert: str) -> str:
    return re.sub(r"\s+", "", wert or "").upper()


#: IBAN-Länge je Land im SEPA-Raum (EPC-Länderliste, Stand 2024). Nur diese
#: Länder kennen die SEPA-Lastschrift; ein neues SEPA-Land hier ergänzen.
SEPA_IBAN_LAENGEN = {
    "AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22,
    "DK": 18, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GI": 23, "GR": 27,
    "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27, "LI": 21, "LT": 20, "LU": 20,
    "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "RO": 24,
    "SE": 24, "SI": 19, "SK": 24, "SM": 27, "VA": 22,
}


def iban_pruefen(wert: str) -> str:
    """Normalisierte IBAN oder ValueError mit Klartext: Format, SEPA-Land,
    Länge des Landes, Prüfziffer (Modulo 97)."""
    iban = iban_normalisieren(wert)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        raise ValueError("IBAN hat kein gültiges Format")
    land = iban[:2]
    if land not in SEPA_IBAN_LAENGEN:
        raise ValueError(f"{land} ist kein SEPA-Land — von dort gibt es keine SEPA-Lastschrift")
    if len(iban) != SEPA_IBAN_LAENGEN[land]:
        raise ValueError(f"IBAN aus {land} hat {SEPA_IBAN_LAENGEN[land]} Zeichen, nicht {len(iban)}")
    if _als_zahl(iban[4:] + iban[:4]) % 97 != 1:
        raise ValueError("IBAN-Prüfziffer stimmt nicht")
    return iban


def iban_maskiert(wert: str) -> str:
    """Land, Prüfziffer und die letzten zwei Stellen, Rest 'x', in Vierergruppen:
    DE89370400440532013000 → 'DE89 xxxx xxxx xxxx xxxx 00' (Gernots Schreibweise)."""
    iban = iban_normalisieren(wert)
    if len(iban) < 8:
        return "x" * len(iban)
    maskiert = iban[:4] + "x" * (len(iban) - 6) + iban[-2:]
    return " ".join(maskiert[i:i + 4] for i in range(0, len(maskiert), 4))


def bic_pruefen(wert: Optional[str]) -> Optional[str]:
    if wert is None or not wert.strip():
        return None
    bic = re.sub(r"\s+", "", wert).upper()
    if not re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", bic):
        raise ValueError("BIC hat kein gültiges Format (8 oder 11 Zeichen)")
    return bic


def glaeubiger_id_pruefen(wert: str) -> str:
    """Normalisierte Gläubiger-ID oder ValueError.

    Deutschland: DE + 2 Prüfziffern + 3 Zeichen Geschäftsbereich + 11 Ziffern
    = 18 Zeichen. Die Prüfziffer läuft über nationale Kennung + Land +
    Prüfziffer, OHNE den Geschäftsbereich (Modulo 97 wie bei der IBAN).
    """
    gid = re.sub(r"\s+", "", wert or "").upper()
    if not gid.startswith("DE"):
        raise ValueError("Gläubiger-ID muss mit DE beginnen")
    if len(gid) != 18:
        raise ValueError(f"Gläubiger-ID hat 18 Zeichen, nicht {len(gid)}")
    if not re.fullmatch(r"DE\d{2}[A-Z0-9]{3}\d{11}", gid):
        raise ValueError("Gläubiger-ID hat kein gültiges Format (DE, 2 Prüfziffern, 3 Zeichen, 11 Ziffern)")
    if _als_zahl(gid[7:] + gid[:4]) % 97 != 1:
        raise ValueError("Gläubiger-ID-Prüfziffer stimmt nicht")
    return gid


def mandatsreferenz_pruefen(wert: str) -> str:
    """1–35 Zeichen aus A-Z a-z 0-9 + ? / - : ( ) . , ' — ohne Leerzeichen,
    nicht mit '/' beginnend oder endend, kein '//'. Zusätzlich nicht mit '+'
    oder '-' beginnend: Excel läse die Zelle der Einreichungs-CSV als Formel,
    und ein entschärfendes ' würde mit der Referenz ins Online-Banking kopiert."""
    ref = (wert or "").strip()
    if not 1 <= len(ref) <= 35:
        raise ValueError("Mandatsreferenz hat 1 bis 35 Zeichen")
    if not re.fullmatch(r"[A-Za-z0-9+?/\-:().,']+", ref):
        raise ValueError("Mandatsreferenz enthält unzulässige Zeichen (erlaubt: A-Z a-z 0-9 + ? / - : ( ) . , ')")
    if ref.startswith("/") or ref.endswith("/") or "//" in ref:
        raise ValueError("Mandatsreferenz darf nicht mit / beginnen oder enden und kein // enthalten")
    if ref.startswith(("+", "-")):
        raise ValueError("Mandatsreferenz darf nicht mit + oder - beginnen")
    return ref


def einstellung_pruefen(key: str, wert: str) -> str:
    """Prüfer für PATCH /admin/settings. Andere Schlüssel unverändert."""
    if key == GLAEUBIGER_ID_KEY:
        return glaeubiger_id_pruefen(wert)
    if key == FRIST_KEY:
        if not wert.strip().isdigit() or not 1 <= int(wert) <= 30:
            raise ValueError("ganze Zahl von 1 bis 30 erwartet")
        return str(int(wert))
    return wert


# --------------------------------------------------------------------------
# Einzugsdatum
# --------------------------------------------------------------------------

def heute_berlin() -> date:
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def _target2_feiertage(jahr: int) -> set[date]:
    ostern = easter(jahr)
    return {
        date(jahr, 1, 1),
        ostern - timedelta(days=2),   # Karfreitag
        ostern + timedelta(days=1),   # Ostermontag
        date(jahr, 5, 1),
        date(jahr, 12, 25),
        date(jahr, 12, 26),
    }


def naechster_bankarbeitstag(tag: date) -> date:
    """tag selbst, wenn Bankarbeitstag (TARGET2), sonst der nächste."""
    while tag.weekday() >= 5 or tag in _target2_feiertage(tag.year):
        tag += timedelta(days=1)
    return tag


def einzugsdatum(rechnungsdatum: date, zahlungsziel_tage: int, frist_tage: int, heute: date) -> date:
    """Nächster Bankarbeitstag ab dem späteren von Fälligkeit nach
    Zahlungsziel und heute + Vorabankündigungsfrist."""
    return naechster_bankarbeitstag(max(
        rechnungsdatum + timedelta(days=zahlungsziel_tage),
        heute + timedelta(days=frist_tage),
    ))


# --------------------------------------------------------------------------
# Datenbank
# --------------------------------------------------------------------------

def glaeubiger_id(db: Session) -> Optional[str]:
    from app.services.settings_service import get_setting
    return get_setting(db, GLAEUBIGER_ID_KEY, env_fallback=False)


def vorabankuendigung_tage(db: Session) -> int:
    from app.services.settings_service import get_setting
    wert = get_setting(db, FRIST_KEY, env_fallback=False)
    return int(wert) if wert and wert.isdigit() else STANDARD_FRIST_TAGE


def aktives_mandat(db: Session, customer_id) -> Optional[SepaMandat]:
    return db.execute(
        select(SepaMandat).where(SepaMandat.customer_id == customer_id, SepaMandat.aktiv.is_(True))
    ).scalar_one_or_none()


# --------------------------------------------------------------------------
# Festschreiben: Vorabankündigung als Snapshot
# --------------------------------------------------------------------------

#: Vorabankündigung nach Gernots Wortlaut vom 08.10.2026 — „zum frühest
#: möglichen Zeitpunkt" ist durch das konkrete Einzugsdatum ersetzt (eine
#: Vorabankündigung braucht Betrag und Datum). „Bitte überweisen Sie den
#: Betrag nicht": die Firmen-IBAN steht in jeder Fußzeile.
HINWEIS_VORLAGE = (
    "Den Rechnungsbetrag von {betrag} buchen wir am {einzugsdatum} per "
    "SEPA-Lastschrift zum Mandat {mandatsreferenz} zu der Gläubiger-ID "
    "{glaeubiger_id} von Ihrem Konto {iban_maskiert}{bank_teil} ab. Bitte "
    "überweisen Sie den Betrag nicht und sorgen Sie für ausreichende Deckung."
)


def _euro(betrag: Decimal, waehrung: str) -> str:
    """1234.5 → '1.234,50 EUR'."""
    text = f"{Decimal(betrag):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {waehrung}"


def hinweistext(*, betrag: Decimal, waehrung: str, einzug: date, mandat: SepaMandat, glaeubiger: str) -> str:
    bank = (mandat.bank_name or "").strip()
    return HINWEIS_VORLAGE.format(
        betrag=_euro(betrag, waehrung),
        einzugsdatum=einzug.strftime("%d.%m.%Y"),
        mandatsreferenz=mandat.mandatsreferenz,
        glaeubiger_id=glaeubiger,
        iban_maskiert=iban_maskiert(mandat.iban),
        # Ohne Bank entfällt "bei der …" ganz, statt "bei der  ab" zu drucken.
        bank_teil=f" bei der {bank}" if bank else "",
    )


def lastschrift_voraussetzungen(db: Session, invoice):
    """Ist die Rechnung beim Festschreiben eine Lastschrift — und geht das?

    None: keine Lastschrift (Überweisungskunde, Gutschrift, Stornorechnung,
    Betrag ≤ 0). Sonst (Kunde, aktives Mandat, Gläubiger-ID). Lastschriftkunde
    ohne aktives Mandat oder ohne Gläubiger-ID: LastschriftNichtMoeglich.
    Der Kunde zählt über die ID, nicht über die Relationship: PATCH /invoices
    kann im Entwurf customer_id umgestellt haben. Betrag: im Entwurf der
    zuletzt berechnete; festschreiben rechnet vorher neu (recalculate_totals).
    """
    from app.models.customer import Customer
    from app.models.invoice import InvoiceType

    if invoice.invoice_type != InvoiceType.RECHNUNG or (invoice.total or 0) <= 0:
        return None
    kunde = db.get(Customer, invoice.customer_id)
    if kunde is None or kunde.zahlungsart != Zahlungsart.LASTSCHRIFT:
        return None
    mandat = aktives_mandat(db, kunde.id)
    if mandat is None:
        raise LastschriftNichtMoeglich(
            f"{kunde.name} zahlt per Lastschrift, hat aber kein aktives SEPA-Mandat — "
            "Mandat anlegen oder Zahlungsart auf Überweisung stellen"
        )
    glaeubiger = glaeubiger_id(db)
    if not glaeubiger:
        raise LastschriftNichtMoeglich(
            "Gläubiger-ID fehlt in den Firmeneinstellungen — ohne sie keine Lastschrift"
        )
    return kunde, mandat, glaeubiger


def lastschrift_festschreiben(db: Session, invoice, zahlungsziel_tage: int) -> None:
    """Teil des Festschreibens (ENTWURF → OFFEN) — für JEDEN Weg dorthin.

    Läuft in InvoiceService._zahlungsbedingungen_festschreiben (Q1): nach
    recalculate_totals und dem Rechnungsdatum, vor Status und Nummer. Eine
    Ausnahme verbraucht also keine Nummer. zahlungsziel_tage ist das
    Zahlungsziel des Entwurfs (Q1: due_date − invoice_date, auch von Hand
    gesetzt) — eingezogen wird nie vor der vereinbarten Fälligkeit, und nie
    früher als heute + Vorabankündigungsfrist. Rechnungen von
    Überweisungskunden, Gutschriften, Stornorechnungen und Beträge ≤ 0
    bleiben unberührt (zahlungsart NULL).
    """
    lastschrift = lastschrift_voraussetzungen(db, invoice)
    if lastschrift is None:
        return
    _kunde, mandat, glaeubiger = lastschrift

    einzug = einzugsdatum(invoice.invoice_date, zahlungsziel_tage, vorabankuendigung_tage(db), heute_berlin())
    invoice.due_date = einzug
    invoice.zahlungsart = Zahlungsart.LASTSCHRIFT
    invoice.sepa_mandat_id = mandat.id
    invoice.lastschrift_status = LastschriftStatus.AUSSTEHEND
    invoice.sepa_hinweis = hinweistext(
        betrag=invoice.total, waehrung=invoice.currency or "EUR",
        einzug=einzug, mandat=mandat, glaeubiger=glaeubiger,
    )


def zahlungszeile_fuer_mail(invoice) -> str:
    """Zeile unter dem Betrag in der Rechnungsmail. Solange der Einzug aussteht:
    der eingefrorene Lastschrifthinweis. Sonst (Überweisung, Einzug gebucht,
    Rücklastschrift) wie bisher die Fälligkeit — nach einer Rücklastschrift
    soll der Kunde überweisen, die Mail darf ihm das nicht ausreden. Der
    Mailtext ist kein Beleg; Beleg ist das PDF mit dem eingefrorenen Hinweis."""
    if invoice.sepa_hinweis and invoice.lastschrift_status == LastschriftStatus.AUSSTEHEND:
        return invoice.sepa_hinweis
    return f"Fällig am: {invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '—'}"


def versand_pruefen(db: Session, invoice) -> None:
    """Vor dem Mailversand einer Rechnung (POST /invoices/{id}/send).

    Entwurf: Lastschrift-Voraussetzungen des aktuellen Kunden prüfen, bevor
    der Versand ihn festschreibt (LastschriftNichtMoeglich → 400).
    Festgeschriebene Lastschriftrechnung mit ausstehendem Einzug (ValueError → 409):
    - Mandat widerrufen: die Rechnung kündigt einen Einzug an, der nicht kommt.
    - noch nie per Mail versendet (sent_at leer) und der Einzug liegt näher
      als die Vorabankündigungsfrist (T2 Regel 2, Risiko 12). Ein erneuter
      Versand ist frei: angekündigt hat der erste.
    Das Einzugsdatum wird nicht verschoben: es steht im eingefrorenen Hinweis
    der festgeschriebenen Rechnung (GoBD). Korrektur: Storno und Neuausstellung.
    """
    from app.models.invoice import InvoiceStatus

    if invoice.status == InvoiceStatus.ENTWURF:
        lastschrift_voraussetzungen(db, invoice)
        return
    if invoice.zahlungsart != Zahlungsart.LASTSCHRIFT or invoice.lastschrift_status != LastschriftStatus.AUSSTEHEND:
        return
    mandat = db.get(SepaMandat, invoice.sepa_mandat_id)
    if mandat is None or not mandat.aktiv:
        raise ValueError(
            "Das SEPA-Mandat dieser Rechnung ist widerrufen — sie kündigt einen Einzug an, "
            "der nicht stattfindet. Rechnung stornieren und als Überweisung neu ausstellen."
        )
    frist = vorabankuendigung_tage(db)
    heute = heute_berlin()
    if invoice.sent_at is None and (invoice.due_date - heute).days < frist:
        raise ValueError(
            f"Vorabankündigungsfrist nicht einhaltbar: Einzug am {invoice.due_date.strftime('%d.%m.%Y')}, "
            f"angekündigt werden muss er {frist} Tage vorher. Die Rechnung ist festgeschrieben — "
            "stornieren und neu ausstellen, dann gilt ein neues Einzugsdatum."
        )


# --------------------------------------------------------------------------
# Einzugsliste, Einreichung bei der Bank, Einzug buchen
# --------------------------------------------------------------------------

def _einzug_offen_bedingungen():
    """Festgeschriebene Lastschriftrechnung mit offenem Betrag, Einzug steht aus.
    Kein Entwurf (sepa_hinweis entsteht erst beim Festschreiben), nichts
    Bezahltes, nichts Storniertes."""
    from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
    return (
        Invoice.zahlungsart == Zahlungsart.LASTSCHRIFT,
        Invoice.lastschrift_status == LastschriftStatus.AUSSTEHEND,
        Invoice.invoice_type == InvoiceType.RECHNUNG,
        Invoice.status.in_((InvoiceStatus.OFFEN, InvoiceStatus.TEILBEZAHLT, InvoiceStatus.UEBERFAELLIG)),
        Invoice.sepa_hinweis.is_not(None),
        Invoice.total > Invoice.paid_amount,
    )


def _mandat_aktiv_bedingung():
    """Das Mandat der Rechnung ist (noch) aktiv — als SQL fürs bedingte UPDATE."""
    from app.models.invoice import Invoice
    return Invoice.sepa_mandat_id.in_(select(SepaMandat.id).where(SepaMandat.aktiv.is_(True)))


def _versandtag(invoice) -> Optional[date]:
    """Tag des ersten erfolgreichen Mailversands in Europe/Berlin (sent_at;
    seit Q2 setzt es nur der Versand)."""
    if invoice.sent_at is None:
        return None
    zeit = invoice.sent_at if invoice.sent_at.tzinfo else invoice.sent_at.replace(tzinfo=timezone.utc)
    return zeit.astimezone(ZoneInfo("Europe/Berlin")).date()


def ankuendigung(invoice, frist_tage: int) -> str:
    """Wie die Vorabankündigung belegt ist: RECHTZEITIG (per Mail, mindestens
    frist_tage vor dem Einzug), ZU_SPAET, NICHT_PER_MAIL (nie über das System
    versendet — etwa ausgedruckt mitgegeben oder gar nicht)."""
    tag = _versandtag(invoice)
    if tag is None:
        return "NICHT_PER_MAIL"
    return "RECHTZEITIG" if (invoice.due_date - tag).days >= frist_tage else "ZU_SPAET"


def einzugsliste(db: Session, bis: Optional[date] = None, invoice_ids: Optional[list] = None) -> list[dict]:
    """Arbeitsliste „Einzug fällig": je Rechnung Restbetrag, Einzugsdatum,
    Versand der Vorabankündigung, Einreichung, Mandat und IBAN."""
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    abfrage = (
        select(Invoice, SepaMandat, Customer)
        .join(SepaMandat, Invoice.sepa_mandat_id == SepaMandat.id)
        .join(Customer, Invoice.customer_id == Customer.id)
        .where(*_einzug_offen_bedingungen())
        .order_by(Invoice.due_date, Invoice.invoice_number)
    )
    if bis is not None:
        abfrage = abfrage.where(Invoice.due_date <= bis)
    if invoice_ids is not None:
        abfrage = abfrage.where(Invoice.id.in_(invoice_ids))

    heute = heute_berlin()
    frist = vorabankuendigung_tage(db)
    return [{
        "invoice_id": inv.id,
        "invoice_number": inv.invoice_number,
        "customer_id": kunde.id,
        "customer_name": kunde.name,
        "rechnungsdatum": inv.invoice_date,
        "betrag": inv.remaining_amount,
        "waehrung": inv.currency or "EUR",
        "einzugsdatum": inv.due_date,
        "ueberfaellig_seit_tagen": max(0, (heute - inv.due_date).days),
        "versendet_am": inv.sent_at,
        "ankuendigung": ankuendigung(inv, frist),
        "eingereicht_am": inv.lastschrift_eingereicht_am,
        "mandat_id": mandat.id,
        "mandatsreferenz": mandat.mandatsreferenz,
        "mandatsart": mandat.mandatsart,
        "unterschrieben_am": mandat.unterschrieben_am,
        "kontoinhaber": mandat.kontoinhaber,
        "iban": mandat.iban,
        "bic": mandat.bic,
        "bank_name": mandat.bank_name,
        "mandat_aktiv": mandat.aktiv,
    } for inv, mandat, kunde in db.execute(abfrage).all()]


EINZUG_CSV_SPALTEN = (
    "Rechnungsnummer", "Kunde", "Kontoinhaber", "IBAN", "BIC", "Bank",
    "Mandatsreferenz", "Mandatsart", "Mandatsdatum", "Betrag", "Waehrung",
    "Einzugsdatum", "Verwendungszweck",
)

#: Zellanfänge, die Excel und LibreOffice als Formel lesen (CSV-Injection).
_FORMEL_ANFANG = ("=", "+", "-", "@", "\t", "\r")


def _csv_zelle(wert) -> str:
    """Text für die CSV, Formelanfänge mit ' entschärft. Kundennamen ändern
    auch Vertrieb und Halle; eine Zelle =HYPERLINK(…D2…) schickte sonst beim
    Öffnen in Excel die IBAN einer anderen Zeile nach außen."""
    text = "" if wert is None else str(wert)
    return "'" + text if text.startswith(_FORMEL_ANFANG) else text


def einzugsliste_csv(zeilen: list[dict]) -> str:
    """CSV für die Eingabe im Online-Banking: Semikolon, Dezimalkomma,
    UTF-8 mit BOM (Excel erkennt sonst die Umlaute nicht)."""
    import csv
    import io
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", lineterminator="\r\n")
    schreiber.writerow(EINZUG_CSV_SPALTEN)
    for z in zeilen:
        schreiber.writerow([_csv_zelle(w) for w in (
            z["invoice_number"], z["customer_name"], z["kontoinhaber"], z["iban"],
            z["bic"], z["bank_name"], z["mandatsreferenz"],
            z["mandatsart"].value, z["unterschrieben_am"].strftime("%d.%m.%Y"),
            f"{z['betrag']:.2f}".replace(".", ","), z["waehrung"],
            z["einzugsdatum"].strftime("%d.%m.%Y"), f"Rechnung {z['invoice_number']}",
        )])
    return "\ufeff" + puffer.getvalue()


def _zeitpunkt() -> str:
    return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y %H:%M")


def einreichen(db: Session, invoice_ids: list, *, ankuendigung_bestaetigt: bool,
               benutzer: Optional[str]) -> list[dict]:
    """Markiert die Rechnungen als bei der Bank eingereicht und liefert genau
    ihre Zeilen für die CSV. Jede Rechnung nur EINMAL: ein zweiter Export
    (anderer Tag, zweite Person, zweiter Klick) lehnt sie ab, statt sie noch
    einmal in eine Datei zu schreiben. Ohne rechtzeitig per Mail versendete
    Vorabankündigung nur mit ausdrücklicher Bestätigung (an der Rechnung
    vermerkt). Alles oder nichts (ValueError)."""
    from app.models.invoice import Invoice

    ids = list(dict.fromkeys(invoice_ids))
    zeilen = {z["invoice_id"]: z for z in einzugsliste(db, invoice_ids=ids)}
    fehlend = [str(i) for i in ids if i not in zeilen]
    if fehlend:
        raise ValueError(
            "Nicht in der Einzugsliste (Entwurf, bezahlt, storniert, kein Lastschrifteinzug "
            f"ausstehend oder unbekannt): {', '.join(fehlend)}"
        )
    probleme, ohne_mail = [], []
    for z in zeilen.values():
        if z["eingereicht_am"] is not None:
            probleme.append(f"{z['invoice_number']} bereits am {z['eingereicht_am'].strftime('%d.%m.%Y')} eingereicht")
        elif not z["mandat_aktiv"]:
            probleme.append(f"{z['invoice_number']}: Mandat widerrufen — nicht einziehen")
        elif z["ankuendigung"] != "RECHTZEITIG":
            ohne_mail.append(z["invoice_id"])
            if not ankuendigung_bestaetigt:
                probleme.append(f"{z['invoice_number']}: Vorabankündigung nicht rechtzeitig per Mail versendet")
    if probleme:
        raise ValueError("Nichts eingereicht — " + "; ".join(probleme))

    heute = heute_berlin()
    # Zuerst schreiben, dann lesen (Muster festschreiben, Q1): das bedingte
    # UPDATE holt die Schreibsperre der Mandanten-DB. Ein gleichzeitiger
    # zweiter Export wartet und findet die Rechnungen danach eingereicht.
    getroffen = db.execute(
        update(Invoice)
        .where(Invoice.id.in_(ids), Invoice.lastschrift_eingereicht_am.is_(None),
               _mandat_aktiv_bedingung(), *_einzug_offen_bedingungen())
        .values(lastschrift_eingereicht_am=heute)
        .execution_options(synchronize_session=False)
    ).rowcount
    if getroffen != len(ids):
        raise ValueError("Gleichzeitig eingereicht oder geändert — Einzugsliste neu laden; nichts eingereicht")
    db.expire_all()  # ab hier frisch gelesen: wir halten die Schreibsperre

    vermerk = f"SEPA-Einreichung am {_zeitpunkt()} von {benutzer or 'unbekannt'}"
    for inv in db.execute(select(Invoice).where(Invoice.id.in_(ids))).scalars():
        zusatz = " — Vorabankündigung außerhalb des Systems bestätigt" if inv.id in ohne_mail else ""
        inv.internal_notes = f"{inv.internal_notes or ''}\n\n{vermerk}{zusatz}".strip()
    frisch = {z["invoice_id"]: z for z in einzugsliste(db, invoice_ids=ids)}
    return [frisch[i] for i in ids]


def einzug_buchen(db: Session, invoice_ids: list, datum: date, *, benutzer: Optional[str]) -> tuple[list[str], list[str]]:
    """Bucht den Einzug als Zahlung (LASTSCHRIFT, Restbetrag, Mandatsreferenz).
    Alles oder nichts: eine ungeeignete Rechnung → ValueError, nichts gebucht.
    Liefert (gebuchte Rechnungsnummern, Hinweise)."""
    from app.models.invoice import Invoice, PaymentMethod
    from app.services.invoice_service import InvoiceService

    ids = list(dict.fromkeys(invoice_ids))
    if datum > heute_berlin():
        raise ValueError("Einzugsdatum liegt in der Zukunft — gebucht wird, was auf dem Konto ist")
    zeilen = {z["invoice_id"]: z for z in einzugsliste(db, invoice_ids=ids)}
    fehlend = [str(i) for i in ids if i not in zeilen]
    if fehlend:
        raise ValueError(
            "Nicht in der Einzugsliste (Entwurf, bezahlt, storniert, kein Lastschrifteinzug "
            f"ausstehend oder unbekannt): {', '.join(fehlend)}"
        )
    widerrufen = [z["invoice_number"] for z in zeilen.values() if not z["mandat_aktiv"]]
    if widerrufen:
        raise ValueError(f"Mandat widerrufen — nicht einziehen: {', '.join(widerrufen)}")
    zu_frueh = [z["invoice_number"] for z in zeilen.values() if datum < z["rechnungsdatum"]]
    if zu_frueh:
        raise ValueError(f"Einzugsdatum liegt vor dem Rechnungsdatum: {', '.join(zu_frueh)}")

    # Zuerst schreiben, dann lesen (Muster festschreiben, Q1): pysqlite beginnt
    # die Transaktion erst mit dem ersten Schreibzugriff. Das bedingte UPDATE
    # holt die Schreibsperre; ein gleichzeitiger zweiter Aufruf wartet und
    # findet die Rechnungen danach nicht mehr AUSSTEHEND → nichts doppelt.
    getroffen = db.execute(
        update(Invoice)
        .where(Invoice.id.in_(ids), _mandat_aktiv_bedingung(), *_einzug_offen_bedingungen())
        .values(lastschrift_status=LastschriftStatus.EINGEZOGEN)
        .execution_options(synchronize_session=False)
    ).rowcount
    if getroffen != len(ids):
        raise ValueError("Gleichzeitig gebucht oder geändert — Einzugsliste neu laden; nichts gebucht")
    db.expire_all()  # ab hier frisch gelesen: wir halten die Schreibsperre

    service = InvoiceService(db)
    vermerk = f"SEPA-Einzug, gebucht am {_zeitpunkt()} von {benutzer or 'unbekannt'}"
    gebucht, hinweise = [], []
    for invoice_id in ids:
        inv = db.get(Invoice, invoice_id)
        mandat = db.get(SepaMandat, inv.sepa_mandat_id)
        if datum < inv.due_date:
            hinweise.append(
                f"{inv.invoice_number}: eingezogen am {datum.strftime('%d.%m.%Y')}, "
                f"angekündigt war der {inv.due_date.strftime('%d.%m.%Y')}"
            )
        service.record_payment(
            invoice_id=inv.id,
            amount=inv.remaining_amount,
            payment_date=datum,
            payment_method=PaymentMethod.LASTSCHRIFT,
            reference=mandat.mandatsreferenz,
            notes=vermerk,
        )
        if mandat.letzter_einzug_am is None or mandat.letzter_einzug_am < datum:
            mandat.letzter_einzug_am = datum
        gebucht.append(inv.invoice_number)
    return gebucht, hinweise


# --------------------------------------------------------------------------
# Rücklastschrift
# --------------------------------------------------------------------------

#: Neue Zahlungsfrist nach einer Rücklastschrift (T2 Regel 6: "OFFEN mit
#: neuer Frist"); ab dann überweist der Kunde. Offener Punkt 10 an Gernot.
RUECKLASTSCHRIFT_FRIST_TAGE = 14


def _lastschrift_summe(db: Session, invoice_id) -> Decimal:
    """Summe der Lastschriftzahlungen der Rechnung, frisch aus der DB (nicht aus
    einer geladenen Collection)."""
    from app.models.invoice import Payment, PaymentMethod
    wert = db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.invoice_id == invoice_id, Payment.payment_method == PaymentMethod.LASTSCHRIFT)
    ).scalar()
    return Decimal(str(wert)).quantize(Decimal("0.01"))


def ruecklastschrift(db: Session, invoice_id, datum: date, grund: str, *,
                     benutzer: Optional[str] = None, zahlbar_bis: Optional[date] = None):
    """Gegenbuchung der Lastschriftzahlungen; die Rechnung ist wieder offen,
    bekommt eine neue Frist und ist ab jetzt mahnfähig. Nach einem Storno (die
    Bank gibt einen schon gebuchten Einzug zurück) nur die Gegenbuchung, der
    Status bleibt STORNIERT. Gibt (Rechnung, Betrag der Gegenbuchung) zurück."""
    from app.models.invoice import Invoice, InvoiceStatus, Payment, PaymentMethod

    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise LookupError("Rechnung nicht gefunden")
    heute = heute_berlin()
    if datum > heute:
        raise ValueError("Datum der Rücklastschrift liegt in der Zukunft")
    if datum < inv.invoice_date:
        raise ValueError("Datum der Rücklastschrift liegt vor dem Rechnungsdatum")
    if zahlbar_bis is not None and zahlbar_bis < heute:
        raise ValueError("Neue Zahlungsfrist liegt in der Vergangenheit")

    # Zuerst schreiben, dann lesen (Muster festschreiben, Q1): das bedingte
    # UPDATE holt die Schreibsperre. Ein gleichzeitiger zweiter Aufruf wartet
    # und findet danach RUECKLASTSCHRIFT vor → abgelehnt, statt doppelt
    # gegenzubuchen.
    erlaubt = or_(
        and_(Invoice.status.not_in((InvoiceStatus.ENTWURF, InvoiceStatus.STORNIERT)),
             Invoice.lastschrift_status.in_((LastschriftStatus.AUSSTEHEND, LastschriftStatus.EINGEZOGEN))),
        and_(Invoice.status == InvoiceStatus.STORNIERT,
             Invoice.lastschrift_status == LastschriftStatus.EINGEZOGEN),
    )
    getroffen = db.execute(
        update(Invoice)
        .where(Invoice.id == invoice_id, Invoice.zahlungsart == Zahlungsart.LASTSCHRIFT, erlaubt)
        .values(lastschrift_status=LastschriftStatus.RUECKLASTSCHRIFT)
        .execution_options(synchronize_session=False)
    ).rowcount
    if getroffen != 1:
        raise ValueError(
            "Keine Lastschriftrechnung mit ausstehendem oder gebuchtem Einzug "
            "(Überweisung, Entwurf, storniert ohne Einzug oder schon zurückgegeben)"
        )
    db.expire_all()  # ab hier frisch gelesen: wir halten die Schreibsperre
    inv = db.get(Invoice, invoice_id)

    eingezogen = _lastschrift_summe(db, inv.id)
    vermerk = f"gebucht am {_zeitpunkt()} von {benutzer or 'unbekannt'}"
    if eingezogen > 0:
        # Gegenbuchung statt Löschen: Zahlungen bleiben nachvollziehbar (GoBD).
        mandat = db.get(SepaMandat, inv.sepa_mandat_id)
        db.add(Payment(
            invoice_id=inv.id,
            payment_date=datum,
            amount=-eingezogen,
            payment_method=PaymentMethod.LASTSCHRIFT,
            reference=f"Rücklastschrift {mandat.mandatsreferenz}"[:100],
            notes=f"{grund} ({vermerk})",
        ))
        db.flush()
    inv.paid_amount = Decimal(str(db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == inv.id)
    ).scalar())).quantize(Decimal("0.01"))
    if inv.status != InvoiceStatus.STORNIERT:
        # record_payment setzt den Status nur nach oben — hier ausdrücklich zurück.
        if inv.paid_amount >= inv.total:
            inv.status = InvoiceStatus.BEZAHLT
        elif inv.paid_amount > 0:
            inv.status = InvoiceStatus.TEILBEZAHLT
        else:
            inv.status = InvoiceStatus.OFFEN
        # Neue Frist: sonst wäre die Rechnung am nächsten Morgen überfällig und
        # gemahnt (Fälligkeit = altes Einzugsdatum). due_date steht nicht im
        # Rechnungs-PDF (dort der eingefrorene Hinweis), nur in Mail und Mahnung.
        inv.due_date = zahlbar_bis or heute + timedelta(days=RUECKLASTSCHRIFT_FRIST_TAGE)
    inv.internal_notes = (
        f"{inv.internal_notes or ''}\n\nRücklastschrift am {datum.strftime('%d.%m.%Y')}: {grund} ({vermerk})"
    ).strip()
    return inv, eingezogen
