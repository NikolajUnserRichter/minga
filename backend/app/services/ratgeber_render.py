"""Ratgeber-Beitrag zu HTML.

Reine Funktionen ohne Datenbank- oder Request-Zugriff: derselbe Datensatz
ergibt immer dieselbe Seite. Das macht den Renderer testbar und erlaubt der
Admin-Vorschau, denselben Code zu benutzen wie die öffentliche Seite.

Markdown wird bewusst nur als Teilmenge unterstützt statt über ein weiteres
Paket. Redaktionstext ist keine vertrauenswürdige Quelle — alles wird zuerst
escaped, erst danach werden die erlaubten Auszeichnungen eingesetzt.
"""
from __future__ import annotations

import html
import re

_FETT_RE = re.compile(r"\*\*(.+?)\*\*")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    """Fett und Links innerhalb einer bereits escapten Zeile."""
    text = _FETT_RE.sub(r"<strong>\1</strong>", text)

    def link(treffer: re.Match) -> str:
        beschriftung, ziel = treffer.group(1), treffer.group(2)
        # http, https und seiteninterne Pfade sind die einzigen Ziele, die
        # eine Redaktion braucht. Alles andere (javascript:, data:) fällt
        # auf reinen Text zurück.
        if not (ziel.startswith("https://") or ziel.startswith("http://")
                or ziel.startswith("/")):
            return beschriftung
        return f'<a href="{ziel}">{beschriftung}</a>'

    return _LINK_RE.sub(link, text)


def render_markdown(text: str) -> str:
    """Überschriften, Absätze, Listen, fett und Links — mehr nicht."""
    if not (text or "").strip():
        return ""

    teile: list[str] = []
    liste: list[str] = []

    def liste_schliessen() -> None:
        if liste:
            teile.append("<ul>\n" + "\n".join(liste) + "\n</ul>")
            liste.clear()

    for block in re.split(r"\n\s*\n", text.strip()):
        zeilen = [z.strip() for z in block.splitlines() if z.strip()]
        for zeile in zeilen:
            sicher = _inline(html.escape(zeile))
            if zeile.startswith("### "):
                liste_schliessen()
                teile.append(f"<h3>{sicher[len('### '):]}</h3>")
            elif zeile.startswith("## "):
                liste_schliessen()
                teile.append(f"<h2>{sicher[len('## '):]}</h2>")
            elif zeile.startswith("- "):
                liste.append(f"<li>{sicher[len('- '):]}</li>")
            else:
                liste_schliessen()
                teile.append(f"<p>{sicher}</p>")
        liste_schliessen()

    return "\n".join(teile)
