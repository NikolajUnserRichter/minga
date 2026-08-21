# SEO- und GEO-System für novaerp.de

Stand 2026-08-21. Vorbild ist die Pipeline von aixventus.ai, aber an die
Gegebenheiten von NovaERP angepasst — nicht kopiert.

## Ziel

Die Marketing-Seite novaerp.de soll in der klassischen Google-Suche und in
Antworten generativer Engines (ChatGPT, Perplexity, Google AI Overviews)
auffindbar und zitierfähig werden. Gemessen wird laufend, verändert wird
kontrolliert.

## Ausgangslage (geprüft am 2026-08-21, live)

Die Startseite ist handwerklich ordentlich: Title, Description, canonical,
Open Graph, Twitter Cards und JSON-LD (Organization, SoftwareApplication,
Offer, FAQPage) sind vorhanden. Darunter liegen aber vier harte Defekte:

1. `robots.txt`, `sitemap.xml` und `llms.txt` existieren nicht. Alle drei
   liefern HTTP 200 mit der Marketing-HTML, weil der Apex-Catch-All in
   `spa_fallback` jeden unbekannten Pfad auf `index.html` abbildet.
2. Jeder erfundene Pfad antwortet mit 200 statt 404. Die Domain ist damit
   eine unbegrenzte Quelle indexierbarer Dubletten.
3. `www.novaerp.de` gilt laut `_is_apex_request` nicht als Apex und fällt
   auf die React-SPA durch — die ERP-App ist dort öffentlich mit 200
   erreichbar, ohne canonical und ohne noindex.
4. `/impressum/` (mit Schrägstrich) liefert die Startseite statt des
   Impressums.

Dazu kommt ein inhaltliches Problem: die Seite hat genau eine Content-Seite.
Ohne Substanz gibt es für AI-Engines nichts zu zitieren. Das Markup ist
Infrastruktur, kein Schalter — die Ahrefs-Studie über 1.885 Seiten fand für
Schema allein keinen messbaren Citation-Uplift.

Gemessen wird bisher nur über die eigene cookielose First-Party-Zählung
(`/api/track`, Auswertung unter `/stats.html`). Kein Search Console, kein
GEO-Signal.

## Randbedingungen

- `backend/static_marketing/` wird im Dockerfile ins Image gebacken. Alles,
  was zur Laufzeit dorthin geschrieben wird, ist beim nächsten Coolify-Deploy
  verloren. Ein dateibasiertes CMS im Docroot scheidet damit aus.
- Ein persistentes `./data`-Volume existiert und wird bereits genutzt:
  `webstats.py` legt dort `webstats.db` ab, daneben liegen die Tenant-DBs.
  Das ist der vorgesehene Ort für alles, was Deploys überleben muss.
- Geplante Jobs laufen über APScheduler (`scheduler_service.py`), inklusive
  eines nicht-mandantengebundenen Jobs (`demo-reset`) als Präzedenzfall.
- Platform-Aktionen sind über den Header `X-Platform-Admin-Key` geschützt.
- Es gibt aktuell keine GSC-Property, keinen Service-Account und keinen
  Gemini-Key. Alles Messende muss ohne Zugangsdaten sauber aussetzen.

## Entscheidungen

| Frage | Entscheidung | Grund |
|---|---|---|
| Umfang | Fundament + Content-Engine + Messpipeline | vom Auftraggeber so gewählt |
| Ratgeber-Inhalte | Datenbank mit Web-Editor | Redaktion ohne Git-Zugriff möglich |
| Datenbank | SQLite im `./data`-Volume | folgt `webstats.py`, keine Migration nötig |
| Nächtlicher Lauf | APScheduler im Backend | keine Zusatzinfra, ein Deploy |
| Dashboard | Panel in `admin.novaerp.de` | vorhandene Admin-UI und Auth |
| Reichweitenmessung | First-Party bleibt, kein GA4 | datenschutzfreundlicher, reicht aus |

Der Preis der DB-Entscheidung: Inhalte liegen nicht im Git und brauchen ein
eigenes Backup des `./data`-Volumes.

## Aufbau in drei Teilen

Die Reihenfolge ist zwingend. Ohne Fundament misst die Pipeline nichts
Verwertbares, ohne Inhalte hat GEO nichts zu zitieren.

### Teil 1 — Fundament

Neues Modul `backend/app/api/seo_public.py` mit Root-Routen, die in
`main.py` vor dem Catch-All registriert werden (FastAPI matcht in
Deklarationsreihenfolge):

- `GET /robots.txt` — hostabhängig. Apex gibt frei, nennt die Sitemap und
  erlaubt die zitierenden KI-Crawler ausdrücklich. Jeder andere Host
  (admin, Tenant-Subdomains) sperrt vollständig.
- `GET /sitemap.xml` — dynamisch erzeugt, nur auf Apex, sonst 404.
- `GET /llms.txt` — kuratiert nach llmstxt.org, nur auf Apex.

Host-Erkennung und Docroot-Auflösung ziehen in ein eigenes Modul
`backend/app/core/site.py`, damit `main.py` und die SEO-Routen dieselbe
Definition teilen statt sie zu duplizieren.

Dazu kommt eine Freigabeliste erlaubter Dateiendungen für den Apex. Der
Docroot enthält Arbeitsdateien — eine SQLite-Datenbank und HTML-Backups —,
die der Catch-All heute auf Anfrage ausliefert.

Vier Reparaturen in `main.py`:

- `www.<root>` zählt als Apex und wird per 301 auf den Apex umgeleitet.
- Unbekannte Apex-Pfade liefern eine neue `404.html` mit Status 404 und
  `noindex`. Der Subdomain-Zweig behält den SPA-Fallback, weil Client-Routing
  ihn braucht.
- `/pfad/` wird per 301 auf `/pfad` normalisiert.
- `/pfad.html` wird per 301 auf `/pfad` normalisiert, damit jede Seite genau
  eine kanonische URL hat.

Markup: canonical, Open Graph und `WebPage`-JSON-LD auf den Rechtsseiten;
`noindex` auf `stats.html` und `404.html`; auf der Startseite ein
`WebSite`-Knoten sowie `logo`, `contactPoint` und `foundingDate` an der
Organization. `sameAs` bleibt leer, solange es keine echten Profile gibt —
erfundene Verweise schaden der Entity-Erkennung mehr als sie nützen.

Sitemap und llms.txt lesen die Artikelliste über eine schmale Funktion, die
in Teil 1 eine leere Liste liefert. Teil 2 füllt sie, ohne Teil 1 anzufassen.

### Teil 2 — Content-Engine

Ratgeber-Bereich als eigener Content-Cluster, gerendert aus der Datenbank.

- `backend/app/core/ratgeber.py` — SQLite-Datenschicht im `./data`-Volume,
  Schema wird beim ersten Zugriff angelegt. Ein Beitrag hat Slug, Titel,
  Cluster, Beschreibung, Autor, Lesezeit, Kurzfassung, Markdown-Body,
  FAQ-Einträge, Quellen, Teaser auf den Folgebeitrag und einen Status
  (Entwurf, Warteschlange, live).
- `backend/app/services/ratgeber_render.py` — reine Funktion von Datensatz
  zu HTML. Markdown-Teilmenge (Überschriften, Listen, fett, Links),
  Kurzfassungs-Box, FAQ-Block, Quellenangabe. Erzeugt Article-, FAQPage- und
  BreadcrumbList-Schema automatisch.
- Öffentliche Routen `/ratgeber` (Übersicht nach Cluster) und
  `/ratgeber/<slug>` (Beitrag), nur auf Apex, nur für veröffentlichte
  Beiträge. Serverseitig gerendertes HTML, damit Crawler es ohne
  JavaScript lesen.
- Admin-API `backend/app/api/v1/ratgeber.py` hinter `X-Platform-Admin-Key`:
  auflisten, lesen, speichern, Vorschau, veröffentlichen, zurückziehen,
  löschen, Warteschlange sortieren.
- Editor als eigener Bereich in `backend/static_admin/index.html`.
- Das Veröffentlichungsdatum wird beim ersten Live-Gang einmal gestempelt
  und danach nie wieder verschoben — sonst springt das Datum bei jeder
  Bearbeitung und entwertet die Signalwirkung.

### Teil 3 — Mess- und Optimierpipeline

- `backend/app/core/seo_store.py` — SQLite `seo.db` im `./data`-Volume mit
  Tagesdaten aus der Search Console, GEO-Messungen, Grounding-Verbrauch und
  einem Änderungsprotokoll.
- `backend/app/services/seo_geo.py` — drei Sammler, jeder einzeln
  abschaltbar und ohne Zugangsdaten inaktiv: Search Console über
  Service-Account, GEO-Messung über Gemini mit Google-Search-Grounding, und
  die vorhandene First-Party-Zählung als Nutzensignal.
- Harter lokaler Kostenriegel für das Grounding (monatlich und täglich),
  bevor ein Request rausgeht. Verbrauch ist im Dashboard sichtbar.
- GEO-Prompts werden getrennt nach Discovery und Marke ausgewertet.
  Marken-Prompts nennen die Domain zwangsläufig; sie in eine Gesamtquote zu
  mischen erzeugt eine Zahl, die Fortschritt vortäuscht.
- APScheduler-Job `seo-geo-nightly`, nicht mandantengebunden, analog
  `demo-reset`.
- Auswertung und Vorschläge landen im Admin-Dashboard. Automatisch
  ausgerollt wird in diesem Teil nichts — die Marketing-Seite liegt im
  Image, ein Schreibpfad dorthin überlebt keinen Deploy. Vorschläge
  betreffen Ratgeber-Inhalte, die in der DB liegen und deshalb gefahrlos
  änderbar sind.

## Was bewusst nicht gebaut wird

- Kein Google Analytics. Die vorhandene cookielose Messung genügt und ist
  rechtlich unkomplizierter.
- Kein automatisches Umschreiben der statischen Marketing-Seiten.
- Keine Mehr-Engine-Messung (Perplexity, OpenAI) in der ersten Fassung.
  Sinnvoll erst, wenn eine Gemini-Baseline steht.

## Offene Punkte außerhalb des Codes

- GSC-Property `novaerp.de` per DNS-TXT verifizieren, Sitemap einreichen.
- Google-Service-Account anlegen und in der GSC freigeben.
- Google-Cloud-Projekt mit Billing plus Gemini-Key, sonst kein Grounding.
- Markenlage klären: `craftdesk.de` führt eine fremde Seite, `tradesk.de`
  steht bei Sedo zum Verkauf, `novaerp.com` ist geparkt. Für die
  Entity-Erkennung generativer Engines ist das ein Störfaktor.
- Backup des `./data`-Volumes, seit dort Redaktionsinhalte liegen.
