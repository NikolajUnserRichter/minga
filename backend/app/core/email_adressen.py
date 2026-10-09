"""Prüfung von E-Mail-Empfängern für den Belegversand (Paket 3, Q2).

Eine Stelle für den Kundenstamm (Empfängerlisten je Belegart) und die
Versand-Endpunkte: Format prüfen, klein schreiben, Dubletten entfernen,
Obergrenze. Bewusst ohne Abhängigkeit zu Modellen oder Services, damit die
Pydantic-Schemas sie importieren können.

Umlaute VOR dem @ werden abgelehnt: smtplib bricht ohne SMTPUTF8-Unterstützung
des Mailservers mit SMTPNotSupportedError ab (ob der SMTP von IONOS SMTPUTF8
kann, ist nicht geprüft). Domains mit Umlaut gehen in ASCII-Form (xn--…) raus.
"""
from __future__ import annotations

from typing import Iterable, Optional, Union

from email_validator import EmailNotValidError, validate_email

#: Höchstzahl Adressen je Liste bzw. je Mail (An + Cc zusammen)
MAX_EMPFAENGER = 10


def pruefe_empfaenger(
    adressen: Optional[Union[str, Iterable[str]]],
    *,
    feld: str = "Empfänger",
) -> list[str]:
    """Prüft und normalisiert Adressen; Reihenfolge bleibt, Dubletten fallen weg.

    Leere Einträge werden übersprungen, None ergibt []. Ungültige Adressen,
    Umlaute vor dem @ und mehr als MAX_EMPFAENGER Adressen ergeben ValueError
    mit deutscher Meldung (in Pydantic-Validatoren wird daraus eine 422).
    """
    if adressen is None:
        return []
    if isinstance(adressen, str):
        adressen = [adressen]
    ergebnis: list[str] = []
    for roh in adressen:
        if roh is None:
            continue
        text = str(roh).strip()
        if not text:
            continue
        lokal = text.rsplit("@", 1)[0]
        if not lokal.isascii():
            raise ValueError(
                f"{feld}: „{text}“ enthält Umlaute oder Sonderzeichen vor dem @. "
                f"Der Mailserver stellt solche Adressen nicht sicher zu — bitte die "
                f"Schreibweise ohne Umlaut verwenden (z. B. ae statt ä)."
            )
        try:
            geprueft = validate_email(text, allow_smtputf8=False, check_deliverability=False)
        except EmailNotValidError as e:
            raise ValueError(f"{feld}: „{text}“ ist keine gültige E-Mail-Adresse ({e})") from None
        adresse = (geprueft.ascii_email or geprueft.normalized).lower()
        if adresse not in ergebnis:
            ergebnis.append(adresse)
    if len(ergebnis) > MAX_EMPFAENGER:
        raise ValueError(
            f"{feld}: höchstens {MAX_EMPFAENGER} Adressen erlaubt (angegeben: {len(ergebnis)})"
        )
    return ergebnis
