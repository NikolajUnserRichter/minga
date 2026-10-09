"""Sentry ohne Bankdaten (B10, Paket 3 Q5).

Bei einem Fehler schickt sentry-sdk (FastAPI-Integration) den JSON-Body und
die Variablen der Stack-Frames mit — trotz send_default_pii=False, und der
Standard-Filter kennt kein "iban". Für /api/v1/sepa fallen Body und
Frame-Variablen deshalb ganz weg; überall sonst wird alles, was wie eine
IBAN aussieht, ersetzt.
"""
import re

_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b")


def _maskiere(wert):
    if isinstance(wert, str):
        return _IBAN.sub("[IBAN entfernt]", wert)
    if isinstance(wert, dict):
        return {k: _maskiere(v) for k, v in wert.items()}
    if isinstance(wert, (list, tuple)):
        return [_maskiere(v) for v in wert]
    return wert


def ohne_bankdaten(event, hint):
    """before_send für sentry_sdk.init."""
    request = event.get("request") or {}
    if "/api/v1/sepa" in str(request.get("url", "")):
        request.pop("data", None)
        for ausnahme in (event.get("exception") or {}).get("values", []):
            for frame in (ausnahme.get("stacktrace") or {}).get("frames", []):
                frame.pop("vars", None)
    return _maskiere(event)
