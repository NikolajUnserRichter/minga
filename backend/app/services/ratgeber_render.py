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
import json
import re
from typing import Optional

from app.core.ratgeber import Article
from app.core.site import canonical_origin

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


# Gleiche Farbwelt wie die Rechtsseiten im Docroot. Bewusst als eingebettete
# Regel statt als eigene CSS-Datei: eine Anfrage weniger und kein zweiter Ort,
# an dem das Layout auseinanderlaufen kann.
_STYLE = """
:root{--abyss:#0a0a0a;--panel:#121212;--ink-0:#F6F1EA;--ink-1:#CDC5BB;
--ink-2:#9A9288;--ink-3:#6C655C;--bronze:#C0814F;--bronze-glow:#D8A06E;
--line:rgba(246,241,234,.08)}
*{box-sizing:border-box}
body{margin:0;background:var(--abyss);color:var(--ink-1);
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.7}
.wrap{max-width:760px;margin:0 auto;padding:3rem 1.5rem 5rem}
a{color:var(--bronze-glow);text-decoration:none}a:hover{text-decoration:underline}
.logo{display:inline-flex;margin-bottom:2.5rem}.logo img{height:28px;width:auto}
h1{color:var(--ink-0);font-size:2.1rem;font-weight:800;letter-spacing:-.03em;margin:0 0 .75rem}
h2{color:var(--ink-0);font-size:1.35rem;font-weight:700;margin:2.4rem 0 .6rem}
h3{color:var(--ink-0);font-size:1.1rem;font-weight:700;margin:1.8rem 0 .4rem}
p{margin:.7rem 0}li{margin:.35rem 0}
.meta{color:var(--ink-3);font-size:.87rem;margin-bottom:2rem}
.kurz{background:rgba(192,129,79,.12);border:1px solid rgba(192,129,79,.32);
border-radius:.7rem;padding:1.1rem 1.3rem;margin:0 0 2.5rem;color:var(--ink-0)}
.kurz b{display:block;font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;
color:var(--bronze-glow);margin-bottom:.4rem}
.faq{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.5rem}
.faq dt{color:var(--ink-0);font-weight:700;margin-top:1.2rem}
.faq dd{margin:.3rem 0 0}
.quellen{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.5rem;font-size:.9rem}
.quellen li{color:var(--ink-2)}
.teaser{margin-top:3rem;background:var(--panel);border:1px solid var(--line);
border-radius:.8rem;padding:1.25rem 1.4rem}
.teaser .lbl{font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-3)}
.teaser a{display:block;color:var(--ink-0);font-weight:700;font-size:1.05rem;margin-top:.3rem}
.karte{display:block;background:var(--panel);border:1px solid var(--line);
border-radius:.8rem;padding:1.2rem 1.35rem;margin-bottom:.9rem}
.karte:hover{border-color:rgba(192,129,79,.4);text-decoration:none}
.karte .t{color:var(--ink-0);font-weight:700;font-size:1.05rem}
.karte .s{color:var(--ink-2);font-size:.9rem;margin-top:.3rem}
.back{display:inline-block;margin-top:3rem;color:var(--ink-2)}
"""

_KOPF_LOGO = '<a href="/" class="logo"><img src="/logo-dark.png" alt="NovaERP"/></a>'


def _e(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


def article_url(slug: str) -> str:
    return f"{canonical_origin()}/ratgeber/{slug}"


def article_graph(article: Article) -> list[dict]:
    """Schema-Knoten eines Beitrags.

    Nur belegte Angaben: kein Autor, wenn keiner hinterlegt ist, kein
    FAQ-Knoten ohne Fragen. Erfundene Auszeichnung schadet mehr als sie hilft.
    """
    url = article_url(article.slug)
    knoten: list[dict] = [{
        "@type": "Article",
        "@id": f"{url}#article",
        "headline": article.title,
        "description": article.description or article.summary,
        "inLanguage": "de-DE",
        "mainEntityOfPage": url,
        "url": url,
        "isPartOf": {"@id": f"{canonical_origin()}/#website"},
        "publisher": {"@id": f"{canonical_origin()}/#org"},
    }]
    if article.author:
        knoten[0]["author"] = {"@type": "Person", "name": article.author}
    if article.published_at:
        knoten[0]["datePublished"] = article.published_at

    fragen = [f for f in article.faq if f.get("frage") and f.get("antwort")]
    if fragen:
        knoten.append({
            "@type": "FAQPage",
            "@id": f"{url}#faq",
            "mainEntity": [{
                "@type": "Question",
                "name": f["frage"],
                "acceptedAnswer": {"@type": "Answer", "text": f["antwort"]},
            } for f in fragen],
        })

    knoten.append({
        "@type": "BreadcrumbList",
        "@id": f"{url}#breadcrumb",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start",
             "item": f"{canonical_origin()}/"},
            {"@type": "ListItem", "position": 2, "name": "Ratgeber",
             "item": f"{canonical_origin()}/ratgeber"},
            {"@type": "ListItem", "position": 3, "name": article.title, "item": url},
        ],
    })
    return knoten


def _seitenrahmen(titel: str, beschreibung: str, url: str,
                  graph: list[dict], inhalt: str) -> str:
    # `<` wird zu <: ein Redaktionstitel mit "</script>" würde sonst aus
    # dem Script-Block ausbrechen. Bleibt gültiges JSON.
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph},
                    ensure_ascii=False, indent=2).replace("<", "\\u003c")
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{_e(titel)}</title>
<meta name="description" content="{_e(beschreibung)}"/>
<link rel="canonical" href="{_e(url)}" />
<meta property="og:type" content="article" />
<meta property="og:url" content="{_e(url)}" />
<meta property="og:title" content="{_e(titel)}" />
<meta property="og:description" content="{_e(beschreibung)}" />
<meta property="og:locale" content="de_DE" />
<meta property="og:site_name" content="NovaERP" />
<meta property="og:image" content="{canonical_origin()}/og.png" />
<script type="application/ld+json">
{ld}
</script>
<style>{_STYLE}</style></head><body><div class="wrap">
{_KOPF_LOGO}
{inhalt}
</div></body></html>
"""


def render_article_page(article: Article,
                        nachfolger: Optional[Article] = None) -> str:
    """Vollständige Beitragsseite als HTML."""
    url = article_url(article.slug)
    zeilen = [f"<h1>{_e(article.title)}</h1>"]

    meta = []
    if article.cluster:
        meta.append(_e(article.cluster))
    if article.author:
        meta.append(_e(article.author))
    if article.published_at:
        meta.append(_e(article.published_at))
    if article.reading_minutes:
        meta.append(f"{int(article.reading_minutes)} Min. Lesezeit")
    if meta:
        zeilen.append('<div class="meta">' + " · ".join(meta) + "</div>")

    if article.summary:
        zeilen.append('<div class="kurz"><b>Kurz gefasst</b>'
                      f"{_e(article.summary)}</div>")

    zeilen.append(render_markdown(article.body))

    fragen = [f for f in article.faq if f.get("frage") and f.get("antwort")]
    if fragen:
        zeilen.append('<div class="faq"><h2>Häufige Fragen</h2><dl>')
        for f in fragen:
            zeilen.append(f"<dt>{_e(f['frage'])}</dt><dd>{_e(f['antwort'])}</dd>")
        zeilen.append("</dl></div>")

    quellen = []
    for q in article.sources:
        ziel = str(q.get("url") or "")
        if ziel.startswith("https://") or ziel.startswith("http://"):
            quellen.append((ziel, q.get("title") or ziel))
    if quellen:
        zeilen.append('<div class="quellen"><h2>Quellen</h2><ul>')
        for ziel, beschriftung in quellen:
            zeilen.append(
                f'<li><a href="{_e(ziel)}" rel="noopener" target="_blank">'
                f"{_e(beschriftung)}</a></li>"
            )
        zeilen.append("</ul></div>")

    if nachfolger is not None:
        zeilen.append(
            '<div class="teaser"><span class="lbl">Weiterlesen</span>'
            f'<a href="/ratgeber/{_e(nachfolger.slug)}">{_e(nachfolger.title)}</a>'
            + (f"<div>{_e(nachfolger.summary)}</div>" if nachfolger.summary else "")
            + "</div>"
        )

    zeilen.append('<a href="/ratgeber" class="back">← Alle Ratgeber-Beiträge</a>')

    return _seitenrahmen(
        titel=f"{article.title} — NovaERP",
        beschreibung=article.description or article.summary,
        url=url,
        graph=article_graph(article),
        inhalt="\n".join(zeilen),
    )
