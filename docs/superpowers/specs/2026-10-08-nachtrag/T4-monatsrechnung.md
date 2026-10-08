# T4 — Monatliche Sammelrechnung automatisch vorschlagen (B5)

Basis: `main` @ `c4a1832` plus der Spezifikationsstand vom 08.10.2026 (inkl. A6-Nachtrag). Repo nicht verändert.
*Prüfnachtrag:* Während der Prüfung ist `main` auf `efcea00` (A6-Hotfix) gesprungen. Geändert sind nur `backend/app/api/v1/imports.py`, ein neuer Test und `Orders.tsx` (`git diff c4a1832 efcea00 --stat`). Die Import-Belege unten sind auf `efcea00` umgestellt. Alle anderen Datei:Zeile-Angaben gelten auch auf `efcea00`.
Methode: Code gelesen, dazu vier Proben gegen den unveränderten Repo-Code in einer In-Memory-DB
(`/tmp/nachtrag/t4probe/test_t4_probe.py`, eigene Kopie der `conftest.py`, `TENANTS_DIR` nach /tmp umgelenkt).
*Prüfnachtrag:* Die Proben 1–4 habe ich auf `efcea00` wiederholt, die Ergebnisse sind gleich. Dazu kommen die Gegenproben P5, P7 und P8 in `/tmp/nachtrag/t4check/test_t4_check.py` (gleiche Methode, 8 passed). P6 zum Gesamtrabatt der Bestellung sagt nichts aus: Schon die Bestellanlage übernimmt den Rabatt nicht, Bestellung und Rechnung stehen beide auf 25,00 €. P6 wird deshalb nicht verwendet.
**belegt** = im Code gesehen oder per Probe nachgestellt · **Annahme** = nicht im Repo prüfbar.

**Antwort an Gernot:** Ja, das geht. Empfehlung: Der Vorschlag kommt am **1. des Folgemonats um 06:30**, nicht am Monatsletzten,
denn sonst fehlen die Lieferungen vom letzten Tag. Das System legt für jeden Kunden mit „monatlicher Abrechnung“ einen
**Rechnungsentwurf** über den Vormonat an und zeigt im Dashboard einen Hinweis. Der Admin prüft und gibt frei. Erst mit der Freigabe
bekommt die Rechnung ihre Nummer. Automatisch versendet wird nichts.
Voraussetzung: Paket 1 (Doppelabrechnungssperre) und aus Paket 3 die Rechnungsnummer, die erst beim Finalisieren vergeben wird.
*Prüfnachtrag:* Dazu kommen aus Paket 2 der Abo-Fix A5 und der Status-Fix A1, siehe 3.7.

---

## 1 Ist-Zustand (belegt)

### 1.1 Heutiger Sammellauf

| Aspekt | Befund | Beleg |
|---|---|---|
| Endpunkte | `POST /invoices/batch-run/preview` (rechnet nur) und `/batch-run/commit` (schreibt fest) | `invoices.py:573-592`, `:595-651` |
| Anfrage | `period_from`, `period_to` (Pflicht), `customer_ids` optional („leer = alle Kunden“), `invoice_date` optional | `invoices.py:514-518` |
| Auswahl | Lieferscheine mit `invoice_id IS NULL`, deren Bestellung nicht `STORNIERT` ist. **Der LS-Status wird nicht geprüft**: auch LS im Status `ENTWURF` (nie quittiert) werden abgerechnet. Die Bestandstests rechnen genau solche LS ab. *Prüfnachtrag:* Auch Bestellungen auf **`FAKTURIERT`** werden abgerechnet. **Gegenprobe P7:** Bestellung mit LS, per Status-Endpunkt auf `FAKTURIERT` gesetzt, landet trotzdem im Lauf (1 Kunde) | `invoices.py:528-535`, `:533`; `tests/test_sammelrechnung.py:16-25`, `:107-110` |
| Leistungsdatum | `note.actual_delivery_date` oder ersatzweise `order.requested_delivery_date`. Gefiltert wird in Python, inklusive Grenzen | `invoices.py:539-541` |
| Zeitraum | frei wählbar, keine Monatslogik | `invoices.py:515-516` |
| Kundenfilter | `if anfrage.customer_ids and …`: `None` **und** `[]` bedeuten beide „alle Kunden“. Das Frontend schickt nie `customer_ids` | `invoices.py:542`; `Invoices.tsx:148`, `:154`; `api.ts:1589-1593` |
| Aggregation | Je LS werden **alle `order.lines`** genommen (nicht die Packlistenpositionen des LS). Schlüssel ist (Beschreibung, Einheit, Preis, Steuersatz). `OrderLine.discount_percent` wird nicht berücksichtigt. *Prüfnachtrag, nachgestellt:* **Gegenprobe P8:** Position mit 10 % Rabatt, Bestellung netto 22,50 €, Sammelrechnung netto 25,00 € | `invoices.py:548-570`; Rabattfeld `order.py:287` |
| *Prüfnachtrag:* Beträge je LS | Zwei weitere Stellen rechnen den LS-Betrag selbst aus `order.lines` aus, ohne Rabatt: das PDF (Tabelle „Enthaltene Lieferscheine“) und `GET /invoices/{id}/delivery-notes`. Bei mehreren LS je Bestellung zeigen beide den vollen Bestellbetrag je LS | `pdf_service.py:371-395` (Betrag `:387-390`); `invoices.py:654-669` (`:668`) |
| **Mehrere LS je Bestellung** | Die Bestellung wird je LS **vollständig erneut** berechnet. **Probe 1:** eine Bestellung über 10 Stk., zwei LS → Vorschau 20 Stk., 50,00 € statt 25,00 € | `invoices.py:555-569`; LS-Anlage ohne Sperre `documents.py:185-260` |
| Festschreiben | `create_invoice` vergibt sofort eine **echte RE-Nummer**. Die Positionen laufen ohne `product_id`, also bleibt `is_deposit` falsch. Die LS bekommen `invoice_id`. Zum Schluss wird der Status **direkt `OFFEN`**. Alles läuft in **einer** Transaktion für alle Kunden | `invoices.py:604-611`, `:618-625`, `:636-637`, `:645`, `:648`; `invoice_service.py:53`, `:163` |
| Bestellung danach | Status bleibt unverändert, `orders.invoice_id` wird nirgends gesetzt. **Probe 2:** Rechnung `OFFEN` mit `RE-2026-00001`, Bestellung weiter `ENTWURF`, `invoice_id = None` | `grep "\.invoice_id ="` trifft nur LS (`invoices.py:637`, `invoice_service.py:316`) |
| *Prüfnachtrag:* Routenreihenfolge | `GET /invoices/{invoice_id}` steht in Zeile 91. Statische GET-Pfade wie `/overdue` und `/revenue-summary` stehen deshalb davor. **Gegenprobe P5:** Eine nachträglich angehängte Route `GET /invoices/monthly-proposals` liefert 422 `uuid_parsing`, weil `/{invoice_id}` sie abfängt | `invoices.py:71`, `:80`, `:91` |
| Dialog | Titel „Sammelrechnung (Monatsrechnung)“, Ablauf Von/Bis → Vorschau → Festschreiben, keine Kundenauswahl, keine Liste der Ausgeschlossenen | `Invoices.tsx:575-631` |
| **Datumsfehler im Dialog** | Vorbelegung „Von“ über `new Date(y, m, 1).toISOString()`: in Europe/Berlin kommt **der Vormonatsletzte** heraus (nachgestellt: am 08.10. ergibt sich `2026-09-30`). „Bis“ ist das UTC-Datum | `Invoices.tsx:64-68` |

### 1.2 Kundenmerkmal Abrechnungsart
**Gibt es nicht.** Im ganzen Backend findet sich weder `invoice_mode` noch etwas Gleichwertiges. Die Felder des `Customer` stehen in `customer.py:128-191`.
Als Vorlage für ein neues Kundenmerkmal eignet sich `show_prices_on_delivery_note`: Modell `customer.py:182`, Migration `tenancy.py:304`,
Schemas `schemas/customer.py:115/163/194`, Formular `Customers.tsx:406-413`.
*Prüfnachtrag:* Zur Vorlage gehören noch die Formularvorbelegung `Customers.tsx:245` und der TS-Typ `frontend/src/types/index.ts:170`.
Wichtig für die Rollen: Kunden liegen im Router `sales` mit `_deps_auftraege`. Dort dürfen auch `production_staff` schreiben (`main.py:122`, `:700-705`).
Ein neues Feld `invoice_mode` könnte also jeder Mitarbeiter umstellen. Das widerspricht Gernots B8-Antwort „Rechnungen bleiben beim Admin“. Nötig ist ein Schutz auf Feldebene, wie ihn T3 für `pfand_abrechnung` vorschlägt.

### 1.3 Entwurf, Nummer, Finalisieren, Verwerfen
- `invoice_number` ist `String(20)`, `unique`, `NOT NULL` (`invoice.py:32-34`). Die Nummer entsteht beim Anlegen (`invoice_service.py:53`), das Jahr kommt aus `date.today()` (`:431`).
- `finalize_invoice` setzt nur `ENTWURF → OFFEN` und `sent_at` und rechnet die Summen nach (`invoice_service.py:218-239`). **`invoice_date` und `due_date` bleiben auf dem Stand der Anlage**; `due_date = invoice_date + payment_days` (`:56-58`).
- **Einen Entwurf löschen kann man nicht.** Der Router hat nur `DELETE …/lines/{line_id}` (`invoices.py:359`).
- **Storno eines Entwurfs:** Erlaubt ist er (`invoice_service.py:298-349` prüft nicht auf `ENTWURF`), und es entsteht eine Gutschrift mit **neuer RE-Nummer im Status `OFFEN`**.
  **Probe 3:** Entwurf `RE-2026-00001` storniert → Gutschrift `RE-2026-00002`, `OFFEN`, −26,75 €. Ein verworfener Vorschlag kostet heute also zwei Nummern und einen Stornobeleg.
  *Prüfnachtrag:* Das geht nur über die API. In der Oberfläche gibt es den Knopf „Stornieren“ nur für `OFFEN/TEILBEZAHLT/UEBERFAELLIG/BEZAHLT` (`Invoices.tsx:395-405`). Ein Entwurf lässt sich dort weder löschen noch stornieren. Ein verworfener Vorschlag bliebe also für immer als `ENTWURF` mit Nummer stehen, und seine LS blieben reserviert.
- *Prüfnachtrag:* **Es gibt einen zweiten Freigabeweg.** `POST /invoices/{id}/send` macht aus einem `ENTWURF` ohne `/finalize` direkt `OFFEN` (`invoices.py:229-232`, `:270-272`). Betreff und Dateiname der Mail nehmen dabei die Nummer, die gerade gilt (`:254`, `:263`).
  In der Oberfläche bietet `OrderDocumentsModal.tsx:317-330` „Mailen“ auch für Entwürfe an. Monatsrechnungen tauchen dort nicht auf, weil das Modal nach `order_id` filtert (`:45`). Die API bleibt aber offen.
  Folge: Die Nummernvergabe aus Paket 3 und die Admin-Freigabe müssen `finalize` **und** `send` abdecken. Sonst geht ein Entwurf mit Platzhalternummer `ENTWURF-…` an den Kunden.
- Gut so: Entwürfe fehlen im DATEV-Export (`datev_service.py:40`), im Umsatz (`invoice_service.py:405`) und in der Überfälligkeitsprüfung (`:355-360`).
  *Prüfnachtrag:* DATEV-Export und Umsatz wählen nach `invoice_date` aus (`datev_service.py:39`, `invoice_service.py:404`), nicht nach dem Leistungszeitraum. Siehe Risiko 9.
- Das PDF druckt den Leistungszeitraum (`pdf_service.py:246-251`) und die Liste der enthaltenen LS (*korrigiert:* `:371-395`, vorher `:382-391`).

### 1.4 Woher Lieferscheine kommen und woher nicht
- Ein LS entsteht nur über `POST /orders/{id}/delivery-notes` (`documents.py:185-260`). Eine Sperre „ein LS je Bestellung“ gibt es nicht; `order_id` ist nicht unique (`models/documents.py:71-73`).
  In der Oberfläche passiert das implizit beim Packlistendruck im Tagesplan, falls noch kein LS existiert (`Tagesplan.tsx:58-63`), oder jederzeit über den Knopf „Neuer LS“ (`OrderDocumentsModal.tsx:117-118`, `:211-217`).
- Setzt man den Status auf `GELIEFERT` (`sales.py:1174-1245`), entsteht **kein** LS. **Probe 4:** Bestellung per Status-Endpunkt auf `GELIEFERT` → 0 LS, der Sammellauf findet 0 Kunden.
- Der Import legt `GELIEFERT`-Bestellungen ohne LS an. *Korrigiert auf `efcea00`:* Ist die Statusspalte leer und liegt das Lieferdatum vor heute (Berlin), wird es `GELIEFERT`, sonst `BESTAETIGT`. Ein LS entsteht weiterhin nicht (`imports.py:554-566`, `:591-595`; vorher `:547-562`). Laut Spezifikation (Zeilen 61, 64, aus Produktionsdaten gelesen) sind das **46 rückdatierte Bestellungen vom 16.09. bis 07.10.**, ohne LS und ohne Rechnung.
  *Prüfnachtrag:* Dazu kommt **eine Bestellung vom 08.10. (Klara Düran)**. Sie steht ebenfalls auf `GELIEFERT` und wurde nicht korrigiert, korrigiert wurden nur die beiden Zukunftsbestellungen (Spezifikation Zeilen 61–62). Für Oktober fehlen also LS vom 01. bis 08.10.
- *Prüfnachtrag:* `delivery_notes.invoice_id` kam auf bestehenden Mandanten-DBs per `ALTER TABLE … ADD COLUMN invoice_id CHAR(32)` dazu, **ohne Fremdschlüssel** (`tenancy.py:337`). Im Modell steht dagegen `ForeignKey("invoices.id", ondelete="SET NULL")` (`models/documents.py:91-93`), und das legt nur `create_all` an, also Tests und neue Mandanten.
  Wird eine Rechnung gelöscht, setzt deshalb nur die Test-DB die LS zurück. Ob Mingas Tabelle älter ist als die Spalte, ist eine **Annahme** (wahrscheinlich, weil die Belegkette vor dem Warenfluss-Release kam).
- Eine „Rechnung aus Bestellung“ verknüpft ihre LS nicht (`invoice_service.py:177-216`). Deshalb würde der Sammellauf die Bestellungen hinter RE-00002/3/4 noch einmal berechnen (Spezifikation, Sofortmaßnahme 3). Die Sperre dagegen gehört zu Paket 1.

### 1.5 Scheduler-Infrastruktur
- APScheduler `3.10.4` (`requirements.txt:28`) als `BackgroundScheduler(timezone="Europe/Berlin")` (`scheduler_service.py:84`). Er startet im FastAPI-Lifespan (`main.py:204-209`) und lässt sich über `SCHEDULER_ENABLED` abschalten (`scheduler_service.py:66`).
- Es gibt 12 mandantenbezogene Jobs (`scheduler_service.py:87-105`), darunter einen einzigen monatlichen: `monthly-revenue-stats`, `CronTrigger(day=1, hour=2)` (`:100`).
  Der rechnet am 1. den **gerade begonnenen** Monat aus (`invoice_tasks.py:297-299`: `monat = today.month`). Dieselbe Falle an der Monatsgrenze droht dem neuen Job.
  *Präzisiert:* Dazu kommen zwei globale Jobs ohne Mandantenschleife, `demo-reset` um 03:30 und `seo-geo-nightly` um 04:15 (`:118-145`).
- Mandantenschleife `_safe_wrap` (`scheduler_service.py:30-57`): Die Slugs kommen aus dem Dateisystem (`tenancy.py:93-96`), je Mandant wird die ContextVar gesetzt, Fehler werden je Mandant geloggt. Es gibt weder Wiederholung noch Protokoll in der DB.
  *Prüfnachtrag:* `known_slugs()` nimmt **jede** `*.db`-Datei im Mandantenordner. Der Golden-Seed der Demo heißt `demo.seed.db` (`demo_reset_service.py:22-23`), sein Stem ist `demo.seed`. `get_engine` prüft den Slug nicht (`tenancy.py:76-85`).
  Jeder Mandantenjob läuft deshalb auch gegen die Seed-Datei. Dass sie in Produktion neben `demo.db` liegt, ist eine **Annahme** aus der Betriebsnotiz.
  Der neue Job darf deshalb nichts schreiben, bevor er den Mandantenschalter geprüft hat.
- *Prüfnachtrag:* Laufzeit-Schalter: `get_setting` fällt standardmäßig auf eine Umgebungsvariable zurück (`settings_service.py:55-62`). Ein Schalter `MONATSRECHNUNG_AUTO` als Container-Variable würde also **alle** Mandanten einschalten, die Seed-Datei eingeschlossen.
  Pflegbar über die Oberfläche ist ein Schlüssel nur, wenn er in `KNOWN_SETTINGS` steht (`settings_service.py:20-52`). Andere Schlüssel lehnt `PATCH /admin/settings` mit 400 ab (`admin.py:71-72`).
- `add_job(coalesce=True, max_instances=1)` ohne Jobstore (`scheduler_service.py:107-116`). Damit gilt der **MemoryJobStore**, und es wird nichts gespeichert.
  **Annahme (Bibliotheksverhalten 3.x):** `misfire_grace_time` steht standardmäßig auf 1 s. Ein Lauf, der in einen Neustart oder Deploy fällt, wird **nicht nachgeholt**.
  *Präzisiert:* Ausschlaggebend ist der MemoryJobStore. Nach dem Start berechnet der Scheduler den nächsten Termin neu, den verpassten gibt es danach nicht mehr. Die Gnadenfrist greift nur, solange der Prozess läuft.
- Zeitzone: Das Dockerfile setzt kein `TZ` (`Dockerfile:19-44`). Die Tasks verwenden `date.today()`. **Annahme:** Der Container läuft auf UTC.
  Ein Trigger am 1. um 00:30 Berliner Zeit läge dann in UTC noch am Vormonatsletzten. ~~Im Code gibt es keinen Helfer für „heute in Berlin“ (`grep ZoneInfo` liefert nichts).~~
  *Korrigiert:* Seit `efcea00` gibt es den Helfer `_today_berlin()` (`imports.py:42-43`, `datetime.now(ZoneInfo("Europe/Berlin")).date()`). Er ist privat im Import-Modul und sollte für T4 nach `app/core` o. ä. wandern.
  `zoneinfo` braucht im `python:3.11-slim`-Image das PyPI-Paket `tzdata`. Das kommt transitiv über `pandas==2.2.0` bzw. `celery==5.3.6` (`requirements.txt:23`, `:49`). Das ist eine **Annahme**, im Image nicht geprüft.
- Mehrere Prozesse: Das Root-`Dockerfile:44` startet **einen** uvicorn-Prozess. `docker-compose.prod.yml:25-29` startet `gunicorn --workers 4`, und dann liefe der Scheduler viermal.
  **Annahme:** Coolify baut das Root-Dockerfile (dafür sprechen SQLite und `/data/tenants`).
  *Prüfnachtrag:* Gestützt wird das dadurch, dass `docker-compose.prod.yml` auf PostgreSQL zeigt (`:33`) und einen eigenen `celery-beat` startet (`:66-69`). Das passt nicht zu SQLite je Mandant, und das Root-`Dockerfile:37` setzt SQLite.
  Würde dieser Stack doch genutzt, müsste der neue Job zusätzlich in `celery_app.py` (`beat_schedule` ab `:36`) eingetragen werden. `scheduler_service.py:86` spiegelt diesen Plan nur.
- `POST /admin/scheduler/run/{job_id}` ruft `job.func()` auf, also die Schleife über **alle Mandanten** (`admin.py:121-134`). Ein Mandanten-Admin würde damit Rechnungsentwürfe in allen Mandanten auslösen.
- Benachrichtigungen: Ein Modell dafür gibt es nicht (keine Notification-Tabelle). Das Dashboard steuert Rechnungsdaten über die Rolle: `showSalesSection` (`Dashboard.tsx:78-84`, `:325`).
  Rechnungen sind für ADMIN/SALES/ACCOUNTING freigegeben, in der Navigation (`Layout.tsx:204-207`) wie in der API (`_deps_geld`, `main.py:125`, `:740-744`).
  *Prüfnachtrag:* Endpunkte, die nur der Admin aufrufen darf, brauchen deshalb im Rechnungsrouter eine eigene Abhängigkeit, z. B. `dependencies=[Depends(require_role(["admin"]))]` (`deps.py:104-119`). Auf Router-Ebene kommen Vertrieb und Buchhaltung durch.
  Heute dürfen beide auch `/finalize` und `/send` aufrufen.
- Migration: `_auto_migrate` kennt nur `ADD COLUMN` (`tenancy.py:265-290`). `CREATE INDEX IF NOT EXISTS` wird schon benutzt (`tenancy.py:354`). Neue Tabellen entstehen beim Boot über `create_all` (`tenancy.py:252-256`).
  *Prüfnachtrag:* Alle Schritte stehen in **einem** `try/except` (`tenancy.py:283-358`). Scheitert ein Schritt, fallen alle folgenden still aus, nur ein Logeintrag bleibt.
  Die Tests bauen das Schema nur über `create_all` (`tests/conftest.py:47`, `:75`). Was allein in `_auto_migrate` steht, etwa ein Index, existiert im Test nicht.

---

## 2 Lücken

| # | Lücke | Folge für den Automatismus |
|---|---|---|
| L1 | Kein Merkmal `invoice_mode` | Der Job wüsste nicht, für wen er vorschlagen soll. „Leere Liste = alle“ würde auch Einzelrechnungskunden erfassen |
| L2 | Der Lauf erzeugt `OFFEN` mit echter Nummer | Ein „Vorschlag“ wäre in Wahrheit schon eine ausgestellte Rechnung |
| L3 | Kein Verwerfen ohne Nummernverbrauch (Probe 3) | Jeder verworfene Vorschlag reißt eine Lücke in den Nummernkreis bzw. erzeugt eine Gutschrift |
| L4 | Doppelabrechnung: (a) Rechnung aus Bestellung (Paket 1), (b) **neu:** mehrere LS je Bestellung (Probe 1) | Der Job rechnet doppelt ab, ohne dass es jemand merkt |
| L5 | `GELIEFERT` ohne LS ist unsichtbar (Status-Weg, Import mit 46 Bestellungen, *Prüfnachtrag:* plus eine vom 08.10.). *Prüfnachtrag:* Genauso unsichtbar sind gelieferte Bestellungen, die wegen A1 auf `BESTAETIGT`/`IN_PRODUKTION` stehen geblieben sind und keine Packliste gedruckt bekamen (Spezifikation Zeile 38) | Die Monatsrechnung ist zu niedrig, und niemand bekommt einen Hinweis |
| L6 | LS-Status, gelieferte Menge (Packliste) und Positionsrabatt bleiben unberücksichtigt (*Prüfnachtrag:* Rabatt per Gegenprobe P8 nachgestellt) | Nicht quittierte, geänderte oder rabattierte Lieferungen werden mit Bestellmenge und vollem Preis berechnet |
| L7 | Kein Job, kein Laufprotokoll. Die einzige Sperre ist `LS.invoice_id`, und die ist zwischen zwei Prozessen nicht atomar (SQLite kennt kein `FOR UPDATE`; **Annahme**, Dialektverhalten) | Bei einem Doppelstart entstehen doppelte Entwürfe |
| L8 | Verpasste Läufe werden nicht nachgeholt, die Zeitzone ist UTC (**Annahme**) | Nach einem Deploy am 1. fehlt der Monat, oder es wird der falsche Monat abgerechnet |
| L9 | Kein Hinweis und keine Benachrichtigung | Die Entwürfe bleiben liegen |
| L10 | Finalisieren setzt `invoice_date`/`due_date` nicht neu | Ein am 1. angelegter Entwurf, der am 6. freigegeben wird, trägt Datum und Fälligkeit vom 1. |
| L11 | Datums-Vorbelegung im Dialog liegt um einen Tag daneben | Ein manueller Monatslauf nimmt den Vormonatsletzten mit |
| L12 | Der Admin-Trigger wirkt mandantenübergreifend | Ein Mandant kann Entwürfe bei anderen erzeugen |
| L13 | Die Bestellung wird nie `FAKTURIERT` (*präzisiert:* nie automatisch; von Hand geht es über `GELIEFERT → FAKTURIERT`, `sales.py:1202`) | Ob eine Bestellung abgerechnet ist, sieht man in der Bestellliste nicht (Abstimmung mit Paket 1). *Prüfnachtrag:* Selbst ein von Hand gesetztes `FAKTURIERT` schützt nicht. Der Lauf rechnet die Bestellung trotzdem ab, sobald sie einen freien LS hat (P7). Das betrifft T1s Vorschlag, die 46 Altbestellungen auf `FAKTURIERT` zu setzen |
| *L14* | *Prüfnachtrag:* zweiter Freigabeweg `/send` (1.3) und Nummer im Mailbetreff | Ein Entwurf geht ohne Admin-Freigabe und mit Platzhalternummer raus |
| *L15* | *Prüfnachtrag:* `delivery_notes.invoice_id` ohne Fremdschlüssel auf bestehenden DBs (1.4) | Ein gelöschter Entwurf hält seine LS für immer fest, wenn das Löschen sie nicht ausdrücklich freigibt |
| *L16* | *Prüfnachtrag:* `invoice_mode` wäre für `production_staff` schreibbar (1.2) | Ein Mitarbeiter kann die Abrechnungsart eines Kunden ändern |

---

## 3 Vorschlag

### 3.0 Grundentscheidungen (Empfehlung)
1. **Zeitpunkt:** Täglich um 06:30 Europe/Berlin prüft der Job „Ist der Vormonat schon vorgeschlagen?“. Praktisch läuft er damit am 1. um 06:30.
   Fällt der Termin in einen Neustart, holt er den Lauf am nächsten Morgen nach. Nicht am Monatsletzten laufen lassen, weil dann die Lieferungen dieses Tages fehlen.
   *Prüfnachtrag (optional):* Dazu kommt ein einmaliger Lauf etwa 10 min nach jedem Start, etwa per `DateTrigger` in `start_scheduler`. Ein Deploy am Vormittag des 1. verschiebt den Vorschlag dann nicht auf den 2. Wegen der Idempotenz kostet das nichts.
2. **Ergebnis:** Es entstehen nur Entwürfe. Weder finalisiert noch versendet der Job etwas automatisch. Freigabe und Versand bleiben beim Admin (Gernot zu B8: „Rechnungen sollen beim Admin bleiben“).
3. **Wer:** nur Kunden mit `invoice_mode = MONATLICH` und `aktiv`.
   *Prüfnachtrag:* Wer mitten im Monat inaktiv gesetzt wurde und noch freie LS im Monat hat, wird nicht still übergangen. Er erscheint als Hinweis, sonst bleibt seine letzte Lieferung unberechnet.
4. **Quelle:** weiterhin Lieferscheine, denn an ihnen hängt der Doppelabrechnungsschutz. Bestellungen ohne LS rechnet der Job **nicht still ab**, sondern listet sie als Hinweis mit dem Knopf „Lieferscheine nachziehen“.
5. **Zeitraum:** fest der Kalendermonat. `service_period_start/end` = 1. bis Letzter. ~~Der manuelle Dialog bleibt für Sonderfälle frei wählbar.~~
   *Korrigiert:* Gernot hat sich bei B5 ausdrücklich für „monatlich fix“ und gegen einen frei wählbaren Zeitraum wie heute entschieden. Der manuelle Dialog bekommt deshalb eine **Monatsauswahl** (Standard Vormonat).
   Die Monatsgrenzen rechnet das Backend aus `month=YYYY-MM`. Damit entfällt auch der Datumsfehler L11. Ein freier Zeitraum bleibt höchstens als Admin-Sonderfall hinter einem Klappschalter, falls Gernot ihn ausdrücklich will.
6. **Rechnungsdatum** = Tag der Freigabe, Fälligkeit wird dabei neu berechnet (L10).
   *Prüfnachtrag:* Das Rechnungsdatum ist das Ausstellungsdatum. Auf den Monatsletzten zurückdatieren scheidet aus (**Annahme**, § 14 Abs. 4 Nr. 3 UStG, siehe Frage 9). Dem Leistungsmonat zugeordnet wird die Rechnung dann über den Leistungszeitraum, siehe Risiko 9.
7. **Schalter je Mandant** `MONATSRECHNUNG_AUTO` in `app_settings`, standardmäßig **aus**, bis Paket 1 und die Nummernvergabe aus Paket 3 live sind.
   *Prüfnachtrag:* Lesen mit `get_setting(db, "MONATSRECHNUNG_AUTO", env_fallback=False)`, damit keine Container-Variable alle Mandanten einschaltet. Eintragen in `KNOWN_SETTINGS` (`settings_service.py:20-52`), sonst lässt `PATCH /admin/settings` ihn nicht zu (`admin.py:71-72`).
   Der Schalter wird als Erstes geprüft, vor jedem Schreibzugriff (Seed-Datei, 1.5).

### 3.1 Datenmodell — **S**

| Änderung | Umsetzung | Migration |
|---|---|---|
| `customers.invoice_mode` | `VARCHAR(20)`, Werte `EINZEL` / `MONATLICH`, Standard `EINZEL` | `_add_col_if_missing("customers","invoice_mode","VARCHAR(20)","'EINZEL'")` |
| `invoices.batch_key` | `VARCHAR(20)`, z. B. `MONAT-2026-10`; NULL bei normalen Rechnungen | `ADD COLUMN` plus `CREATE UNIQUE INDEX IF NOT EXISTS ux_invoices_batch ON invoices(customer_id, batch_key) WHERE batch_key IS NOT NULL AND status <> 'STORNIERT'`. Je Kunde und Monat ist damit höchstens eine aktive Monatsrechnung möglich; nach einem Storno ist eine neue erlaubt. *Prüfnachtrag:* SQLite kann Teilindizes. Der Status steht als Klartext `STORNIERT` in der DB (`enums.py:30-38`, Name = Wert). Den Index **zusätzlich im Modell** deklarieren (`Index(..., unique=True, sqlite_where=text(...))` in `Invoice.__table_args__`), sonst fehlt er in Tests und bei neuen Mandanten (`create_all`). In `_auto_migrate` als letzten Schritt oder in einem eigenen `try` anlegen (1.5) |
| Neue Tabelle `billing_runs` | `id`, `kind` (`MONAT_AUTO`/`MONAT_MANUELL`), `period_start`, `period_end`, `status` (`LAEUFT`/`FERTIG`/`FEHLER`), `started_at`, `finished_at`, `triggered_by` (NULL = Scheduler), `result` JSON (angelegte Entwürfe, übersprungene Kunden mit Grund, Hinweise), `error`. ~~`UniqueConstraint(kind, period_start)`~~ *Korrigiert:* Mit `UniqueConstraint(kind, period_start)` sperren sich der automatische und der manuelle Lauf **nicht** gegenseitig. Außerdem ließe sich ein manueller Lauf nach `FERTIG` nie wiederholen. Ein Kunde, dessen LS erst nach dem Lauf nachgezogen wurden, hat dann keinen Entwurf, den man neu aufbauen könnte, und bekommt keinen. Besser: Teilindex `UNIQUE (period_start) WHERE status = 'LAEUFT'`, also höchstens ein laufender Lauf je Monat, gleich welcher Art. Der Job überspringt, wenn es schon einen `MONAT_AUTO`-Lauf mit `FERTIG` für den Monat gibt. Ein manueller „Nachlauf“ bleibt jederzeit möglich und legt nur Entwürfe für Kunden ohne aktive Monatsrechnung an (`batch_key`-Index) | `create_all` beim Boot (neue Tabelle, `tenancy.py:252-256`); Modell in `app/models/__init__.py` registrieren (Muster `ImportRun`, `:104`, `:209`) |
| Platzhalternummer | `ENTWURF-` + 12 Zeichen = 20 Zeichen, passt in `String(20)` | aus Paket 3, hier nur genutzt |
| (optional) `pfand_via_clearing` | aus Paket 1, filtert Pfandpositionen im Monatsentwurf. *Prüfnachtrag:* T3 empfiehlt, statt des Booleans gleich `pfand_abrechnung` (`JE_LIEFERUNG`/`KEINE`, später `MONATLICH`) zu bauen. Name und Werte mit T3 und Paket 1 abstimmen | Paket 1 |

### 3.2 Service und Job — **M**
Neuer Service `app/services/sammelrechnung_service.py`. Dorthin wandern `_abrechenbare_lieferscheine`, `_aggregiere` und der Kern des Festschreibens aus `invoices.py:521-651`. Danach nutzen Endpunkt und Job denselben Code. Die Funktionen bekommen `db` und `jetzt` übergeben und lassen sich so ohne Scheduler testen.

```
schlage_monatsrechnungen_vor(db, jetzt_berlin, kind="MONAT_AUTO", ausgeloest_von=None):
  monat = Vormonat(jetzt_berlin.date())          # nie date.today()
  0. (Prüfnachtrag) nur kind = MONAT_AUTO: Schalter lesen (env_fallback=False);
     aus → return, ohne zu schreiben; FERTIG-Lauf MONAT_AUTO für monat vorhanden → return "schon erledigt"
     (ein manueller Lauf des Admins hängt nicht am Schalter)
  1. Sperre: INSERT billing_runs(kind, period_start, status='LAEUFT') → commit
       IntegrityError (Teilindex: schon ein LAEUFT-Lauf für monat, gleich welcher Art):
         LAEUFT älter als 60 min → bedingtes UPDATE … SET status='FEHLER'
             WHERE id=? AND status='LAEUFT'; rowcount 1 → INSERT erneut versuchen,
             rowcount 0 → anderer Prozess war schneller → return
         sonst → return "läuft gerade"
  2. kunden = aktive Kunden mit invoice_mode = MONATLICH
  3. ls = freie LS (invoice_id NULL) mit Leistungsdatum im Monat, Bestellung nicht STORNIERT
          (Prüfnachtrag: und nicht FAKTURIERT, P7),
          ohne Bestellungen, die schon in einer aktiven Rechnung stecken (Sperre aus Paket 1),
          [gestrichen: je Bestellung nur EIN LS (weitere → Hinweis "mehrere LS", nicht berechnen)]
          Prüfnachtrag: je BESTELLUNG einmal aggregieren und ALLE ihre freien LS an den
          Entwurf hängen (Hinweis "mehrere LS"). Bliebe der zweite LS frei, käme er jeden
          Monat als "freier LS aus früherem Monat" wieder, und ein manueller Lauf mit
          weitem Zeitraum würde die ganze Bestellung erneut berechnen
  4. je Kunde (eigene Transaktion, damit ein Fehler nicht alle Kunden blockiert):
       aktive Rechnung mit batch_key vorhanden → überspringen, neue freie LS als Hinweis "nachgekommen"
       keine LS → Hinweis "keine Lieferungen", kein Entwurf
       sonst → Entwurf: Status ENTWURF, Platzhalternummer, batch_key, Leistungszeitraum,
               Positionen mit product_id + Positionsrabatt, invoice_line_sources,
               LS.invoice_id = Entwurf (Reservierung), Summen
  5. Hinweise je Monat: GELIEFERT-Bestellungen von Monatskunden im Zeitraum ohne LS (Bestellnummern),
     freie LS aus früheren Monaten, LS für Kunden mit EINZEL, LS nicht als geliefert quittiert
     Prüfnachtrag: "ohne LS" für ALLE nicht stornierten Bestellungen der Monatskunden mit
     Liefertermin im Monat, nicht nur GELIEFERT. Wegen A1 bleiben gelieferte Bestellungen
     oft auf BESTAETIGT/IN_PRODUKTION stehen (Spezifikation Zeile 38)
  6. billing_runs.status = FERTIG, result speichern (bei Ausnahme: FEHLER + error)
```

*Prüfnachtrag zum Service:*
- Der Aggregationsschlüssel muss `product_id` enthalten. Heute fehlt sie (`invoices.py:565-566`). Ohne sie kann `add_line` weder `is_deposit` setzen (`invoice_service.py:163`) noch der Pfandfilter aus Paket 1/T3 greifen. Der Positionsrabatt geht an `add_line(discount_percent=…)` (P8).
- LS-Beträge im PDF und in `GET /invoices/{id}/delivery-notes` aus `invoice_line_sources` bilden statt aus `order.lines` (`pdf_service.py:387-390`, `invoices.py:668`). Sonst zeigen beide nach der Korrektur andere Zahlen als die Rechnung.
- Berlin-Datum über einen gemeinsamen Helfer. Den gibt es seit `efcea00` als `_today_berlin()` in `imports.py:42-43`, er gehört nach `app/core`.

Für den Scheduler kommt in `app/tasks/invoice_tasks.py` eine Funktion `propose_monthly_invoices()` dazu. Sie öffnet `SessionLocal()` (der Mandant kommt über die ContextVar), prüft den Schalter `MONATSRECHNUNG_AUTO` und ruft den Service mit `datetime.now(ZoneInfo("Europe/Berlin"))` auf.
Registriert wird sie in `scheduler_service.py:87-105` als `("monthly-invoice-proposals", propose_monthly_invoices, CronTrigger(hour=6, minute=30))`, also **täglich** und nicht nur am 1. Das Nachholen nach einem Neustart läuft damit über die Idempotenz und braucht keinen persistenten Jobstore.
*Prüfnachtrag:* Nicht das Muster von `generate_recurring_invoices` übernehmen (`invoice_tasks.py:200-287`). Es ist nicht eingeplant, prüft die Idempotenz nur über `invoice_date == today` und `scalar_one_or_none()` (`:239-245`) und soll laut A5 entfernt werden.

### 3.3 Endpunkte — **M**

| Endpunkt | Zweck | Rolle |
|---|---|---|
| `GET /invoices/monthly-proposals?month=YYYY-MM` (Standard: Vormonat) | Laufstatus, Entwürfe mit `batch_key`, Summen und Hinweise. Speist Dashboard und Rechnungsseite | Admin (je nach Antwort zu B8 auch Buchhaltung) |
| `POST /invoices/monthly-proposals/run?month=YYYY-MM` | Manueller Lauf **nur für den eigenen Mandanten** (`kind=MONAT_MANUELL`), ebenfalls idempotent. Ersatz für `/admin/scheduler/run` (L12) | Admin |
| `POST /invoices/{id}/rebuild` | Monatsentwurf neu aufbauen: LS freigeben, Positionen und Quellen löschen, für denselben Kunden und Monat neu aggregieren. Nur im Status `ENTWURF` mit `batch_key` | Admin |
| `DELETE /invoices/{id}` | Entwurf verwerfen und LS freigeben. Erst möglich, wenn Platzhalternummern da sind (B4/Paket 3). *Prüfnachtrag:* Die LS **ausdrücklich** freigeben (`UPDATE delivery_notes SET invoice_id = NULL WHERE invoice_id = ?`, Muster `invoice_service.py:313-316`). Auf bestehenden DBs fehlt der Fremdschlüssel mit `ON DELETE SET NULL` (1.4) | Admin |
| `POST /invoices/{id}/finalize` (Erweiterung, Paket 3) | Nummer vergeben, `invoice_date` = heute (Berlin), `due_date` neu berechnen; mit Paket 1 abstimmen, ob die Bestellungen auf `FAKTURIERT` gehen | Admin |
| *Prüfnachtrag:* `POST /invoices/{id}/send` (Erweiterung, Paket 3) | Bei `ENTWURF` entweder ablehnen („erst freigeben“) oder dieselbe Freigabelogik wie `/finalize` durchlaufen, **bevor** Betreff und PDF entstehen (`invoices.py:249-272`). Sonst gibt es einen zweiten Freigabeweg mit Platzhalternummer | Admin (B8) |
| `POST /invoices/batch-run/preview|commit` (Erweiterung) | Standardmäßig nur `MONATLICH`-Kunden, Ausgeschlossene zurückgeben, `commit` erzeugt Entwürfe (B4). *Prüfnachtrag:* Zeitraum als `month=YYYY-MM` statt `period_from/to` (3.0 Nr. 5). Bestandstests anpassen, siehe 3.5 | wie heute |
| `POST /invoices/monthly-proposals/backfill-delivery-notes` | Für die gemeldeten `GELIEFERT`-Bestellungen ohne LS je einen LS anlegen (Status `GELIEFERT`, `actual_delivery_date` aus der Bestellung). Nur nach Bestätigung. *Prüfnachtrag:* `FAKTURIERT` ausschließen, weil die Ware dann schon anderswo berechnet ist (T1, P7). Keinen Lagerabzug auslösen, also nicht über `mark-delivered` gehen und `deduct_inventory_for_order` nicht aufrufen (`documents.py:298-312`). Die importierten Bestellungen haben bewusst keine Lagerbewegungen (Spezifikation Zeile 61) | Admin |

*Prüfnachtrag zu den Endpunkten:*
- `GET /invoices/monthly-proposals` muss im Router **vor** `GET /{invoice_id}` stehen (`invoices.py:91`), wie `/overdue` und `/revenue-summary` (`:71`, `:80`). Sonst antwortet er mit 422 (Gegenprobe P5). Die neuen POST- und DELETE-Pfade kollidieren nicht.
- „Admin“ heißt hier: eine eigene Abhängigkeit am Endpunkt, `require_role(["admin"])` (`deps.py:104-119`). Der Router selbst lässt Vertrieb und Buchhaltung durch (`main.py:125`, `:740-744`).
- Die Dashboard-Karte führt zur „gefilterten Rechnungsliste“. `GET /invoices` kennt aber keinen Filter nach `batch_key` oder Leistungszeitraum, und die Seitengröße steht standardmäßig auf 20 (`invoices.py:36-68`, `deps.py:156-166`). Nötig ist ein Filterparameter. Die Aufhebung der 20er-Kürzung steht in Paket 1.

### 3.4 Oberfläche — **M**
- **Kunde** (`Customers.tsx` neben `:406-413`): Auswahl „Abrechnung: je Lieferung / monatliche Sammelrechnung“.
  *Prüfnachtrag:* Das Feld sehen und ändern nur Admin, Vertrieb und Buchhaltung, im Backend am Feld geprüft (L16). Dazu Vorbelegung `:245` und Typ `types/index.ts:170`.
- **Dashboard** (`Dashboard.tsx`, gesteuert wie `showSalesSection` `:78-84`, aber nur für ADMIN): eine Karte „Monatsrechnungen Oktober zur Prüfung: 5 Entwürfe · 1.234,56 € netto · 3 Hinweise“, die zur gefilterten Rechnungsliste führt.
  Die Karte verschwindet, wenn alle Entwürfe des Monats freigegeben oder verworfen sind. Zusätzlich ein Badge am Menüpunkt „Rechnungen“.
- **Rechnungen** (`Invoices.tsx`): ein Banner für den Vormonat mit Liste je Kunde und den Aktionen „Prüfen“ (Detail plus LS-Liste über `/{id}/delivery-notes`), „Aktualisieren“ (nur bei nachgekommenen LS, mit Warnung, dass manuelle Änderungen verloren gehen), „Freigeben“ und „Verwerfen“.
  Die Hinweise erscheinen als aufklappbare Liste: Bestellungen ohne LS (mit Knopf „Lieferscheine nachziehen“), mehrere LS je Bestellung, Kunden ohne Lieferungen. Dazu „Ausgewählte freigeben“ mit Bestätigung.
- **Dialog Sammelrechnung**: Vorbelegung auf den Vormonat und lokal berechnet (L11), Kundenauswahl, Liste „nicht enthalten, weil Einzelabrechnung“.
  *Korrigiert:* Statt Von/Bis gibt es eine Monatsauswahl, und die Grenzen rechnet das Backend (3.0 Nr. 5, Gernot „monatlich fix“). Dann rechnet der Client kein Datum mehr, und L11 verschwindet.
  Der Knopf „Festschreiben“ heißt künftig „Entwürfe anlegen“ (B4). Der Hinweistext „Erst Festschreiben vergibt Nummern“ (`Invoices.tsx:579-582`) muss dann mitgeändert werden.
- Optional eine Mail an den Admin am 1. „5 Monatsrechnungen warten auf Freigabe“, über den vorhandenen `send_email` (siehe Frage 5).

### 3.5 Tests — **M**
Backend, neue Datei `tests/test_monatsrechnung_vorschlag.py`. Der Service wird direkt mit der Test-Session und einem festen `jetzt` aufgerufen:
1. Monatskunde mit 2 LS im Oktober → 1 Entwurf, `ENTWURF`, Platzhalternummer, Zeitraum 01.–31.10., LS reserviert.
2. Einzelkunde mit LS → kein Entwurf, erscheint unter „ausgeschlossen“.
3. Zweiter Aufruf für denselben Monat → keine neue Rechnung, Lauf „schon erledigt“.
4. Lauf in `LAEUFT` (frisch) → zweiter Aufruf bricht ab. Lauf in `FEHLER` → nächster Aufruf übernimmt.
5. Monatsgrenze und Zeitzone: `jetzt` = 01.11.2026 00:30 Europe/Berlin → Zeitraum Oktober. `jetzt` = 31.10. 23:59 → Zeitraum September, dessen Lauf schon erledigt ist.
6. Kunde ohne Lieferungen → kein Entwurf, Hinweis.
7. `GELIEFERT` über den Status-Endpunkt, ohne LS → keine Position, Hinweis mit Bestellnummer. Nach `backfill-delivery-notes` und `rebuild` ist die Position da.
8. Zwei LS für eine Bestellung → nur einmal berechnet, Hinweis (Gegenprobe zu Probe 1).
9. Bestellung schon „aus Bestellung“ abgerechnet → nicht im Entwurf (Sperre aus Paket 1).
10. Nachgekommener LS → Hinweis „nachgekommen“. `rebuild` nimmt ihn auf, die Summen stimmen.
11. Verwerfen → LS wieder frei, **keine RE-Nummer verbraucht**.
12. Freigeben → nächste lückenlose RE-Nummer, `invoice_date` = Freigabetag, `due_date` neu.
13. Storno der freigegebenen Monatsrechnung → der Unique-Index lässt einen neuen Entwurf für denselben Kunden und Monat zu.
14. Rollen: `production_staff` und `sales` bekommen 403 auf `monthly-proposals` (sofern nur der Admin zugelassen wird).
15. Scheduler: Die Jobliste enthält `monthly-invoice-proposals` (dafür die Jobdefinition aus `start_scheduler` in eine testbare Funktion ziehen). Schalter aus → der Job erzeugt nichts.
16. *Prüfnachtrag:* Routenreihenfolge: `GET /invoices/monthly-proposals` liefert 200 und nicht 422 (Gegenstück zu P5).
17. *Prüfnachtrag:* Teilindex `ux_invoices_batch`: Ein zweiter aktiver Entwurf für denselben Kunden und Monat scheitert mit `IntegrityError`. Das klappt im Test nur, wenn der Index im Modell steht (3.1).
18. *Prüfnachtrag:* Verwerfen auf einem Schema **ohne** Fremdschlüssel an `delivery_notes.invoice_id`: Die Tabelle per `ALTER TABLE ADD COLUMN` nachbauen wie in Produktion, dann prüfen, dass die LS trotzdem frei werden. Im Standard-Testschema verdeckt `ON DELETE SET NULL` den Fehler.
19. *Prüfnachtrag:* `FAKTURIERT`-Bestellung mit freiem LS → nicht im Entwurf (P7). Positionsrabatt 10 % → Entwurf netto 22,50 € (P8).
20. *Prüfnachtrag:* `/send` auf einen Monatsentwurf → abgelehnt, oder freigegeben mit echter Nummer im Mailbetreff, nie `ENTWURF-…`.
21. *Prüfnachtrag:* Schalter nur als Umgebungsvariable gesetzt, ohne DB-Wert → der Job erzeugt nichts (`env_fallback=False`).
~~Frontend: ein Unit-Test für den Datumshelfer „Vormonat“ in Europe/Berlin.~~
*Korrigiert:* Das Frontend hat keinen Unit-Test-Runner. In `package.json:6-11` gibt es kein `test`-Skript, als Testwerkzeug ist nur Playwright da (`:27`, `tests/e2e/`). Weil die Monatsgrenzen ins Backend wandern (3.0 Nr. 5), gehört der Test dorthin: `month=2026-10` → 01.10.–31.10., auch für Dezember/Januar und Februar im Schaltjahr. Optional ein Playwright-Fall mit `timezoneId: 'Europe/Berlin'`.
~~Hinweis: Die Bestandstests in `test_sammelrechnung.py` erwarten heute `OFFEN` bzw. eine sofortige Nummer und müssen mit B4/Paket 3 angepasst werden.~~
*Korrigiert:* Keiner der acht Bestandstests prüft Status oder Nummer (`tests/test_sammelrechnung.py:51-128`). Brechen würden sie aus anderen Gründen:
(a) Nimmt der Lauf standardmäßig nur `MONATLICH`-Kunden, schlagen **5 von 8** fehl. Das sind `:52`, `:71`, `:85`, `:99` und `:112`, weil `sample_customer` (`tests/conftest.py:143-155`) kein `invoice_mode` setzt.
Drei bestehen nur noch scheinbar: `:77` und `:126` erwarten ohnehin eine leere Liste, `:107` vergleicht zwei leere Läufe. Die Fixture muss also `invoice_mode: "MONATLICH"` bekommen.
(b) Wird der Storno von Entwürfen zugunsten von `DELETE` gesperrt, bricht `:112-124` (storniert die frisch festgeschriebene Rechnung, die dann ein Entwurf ist).
(c) Mit dem Wechsel auf `month=` statt `period_from/to` müssen alle Aufrufe in `_lauf` (`:45-48`) und `:78-80` umgestellt werden.

### 3.6 Randfälle aus der Aufgabe

| Fall | Verhalten im Vorschlag |
|---|---|
| Bestellungen ohne LS, darunter die 46 aus dem Import | Kein stilles Abrechnen. Die Liste erscheint im Laufergebnis und im Dashboard, danach entscheidet der Admin über „Lieferscheine nachziehen“ und „Aktualisieren“. Die Bestellungen vom 16.–30.09. betreffen den ersten Automatiklauf (01.11., Oktober) nicht, die vom 01.–07.10. schon (Frage 3). *Prüfnachtrag:* Auch die Bestellung vom 08.10. (Klara Düran) steht auf `GELIEFERT` ohne LS (Spezifikation Zeile 61). Hat der Monatskunde zum Laufzeitpunkt **gar keinen** LS, entsteht kein Entwurf, den „Aktualisieren“ neu aufbauen könnte. Dann hilft nur ein manueller Nachlauf, der nach der Korrektur in 3.1 möglich ist |
| Job läuft zweimal (zweiter Prozess, manueller Klick, Folgetag) | ~~Die `billing_runs`-Zeile ist die Sperre. Pro Kunde schützen zusätzlich `batch_key` mit Unique-Index und `LS.invoice_id`, also drei Ebenen~~ *Korrigiert:* Mit `UniqueConstraint(kind, period_start)` sperrte die Zeile nur Läufe **derselben Art**, ein manueller Klick lief also neben dem Job. Nach 3.1 gilt höchstens ein `LAEUFT` je Monat, gleich welcher Art. Folgetag: der `FERTIG`-Lauf (`MONAT_AUTO`) wird übersprungen. Pro Kunde schützen zusätzlich der `batch_key`-Teilindex und `LS.invoice_id`. Der Index muss dafür auch im Testschema existieren (3.1) |
| Container-Neustart am Monatsersten | Der tägliche Trigger holt am nächsten Morgen nach. Fällt der Neustart mitten in den Lauf, gilt `LAEUFT` nach 60 min als verwaist. Die schon angelegten Kunden bleiben dank `batch_key` bestehen, der Rest wird ergänzt |
| Kunde ohne Lieferungen | Kein Entwurf, nur ein Info-Hinweis „keine Lieferungen im Oktober“ |
| LS kommt nach dem Lauf dazu | Hinweis „nachgekommen“ und „Aktualisieren“. Der Job ändert keinen Entwurf eigenmächtig, weil der Admin ihn schon bearbeitet haben könnte |
| Vergessener LS aus einem früheren Monat | Hinweis. Ob er in die nächste Monatsrechnung darf, klärt Frage 8 |
| Demo-Mandant | Läuft mit, alle Kunden stehen standardmäßig auf `EINZEL`, und der Schalter ist aus, also passiert nichts. *Prüfnachtrag:* Die Schleife erfasst auch den Pseudo-Mandanten `demo.seed`, also den Golden-Seed (1.5). Das bleibt folgenlos, solange der Schalter ohne Rückgriff auf Umgebungsvariablen gelesen wird und vor jedem Schreibzugriff steht |
| *Prüfnachtrag:* Abo-Bestellungen | Die vier LfA-Abo-Entwürfe tragen „Unknown“ und 2,00 € (A5, Spezifikation Zeilen 54-57). Bekommen sie im Tagesplan eine Packliste, also einen LS, landen sie mit falschem Preis im Monatsentwurf. Erst A5 beheben (Paket 2) |

### 3.7 Reihenfolge, Abhängigkeiten, Aufwand

| Schritt | Abhängig von | Aufwand |
|---|---|---|
| Doppelabrechnungssperre „aus Bestellung“, Sammellauf mit `product_id` und Steuersatz des Produkts, `pfand_via_clearing` (*Prüfnachtrag:* bzw. `pfand_abrechnung` nach T3; die Sperre muss auch `FAKTURIERT` ausschließen, P7) | **Paket 1** | (Paket 1) |
| Sammellauf erzeugt Entwürfe, Entwurf verwerfen, Nummer erst beim Finalisieren, Datum und Fälligkeit beim Finalisieren (*Prüfnachtrag:* auch im Weg `/send`, `invoices.py:270-272`) | **B4 / Paket 3** | (Paket 3) |
| *Prüfnachtrag:* Abo-Bestellungen mit richtigem Produkt und Preis (A5), ehrliche Statusaktionen (A1) | **Paket 2** | (Paket 2) |
| Ein LS je Bestellung im Lauf (*korrigiert:* je Bestellung einmal aggregieren, alle LS anhängen), Positionsrabatt übernehmen, LS-Beträge aus `invoice_line_sources` | – | S |
| `invoice_mode` (Modell, Schema, Kundenformular, *Prüfnachtrag:* Feldschutz gegen `production_staff`) | – | S |
| `billing_runs`, `batch_key`, Unique-Index (*Prüfnachtrag:* beide Teilindizes auch im Modell; Schalter in `KNOWN_SETTINGS`) | – | S |
| Service plus täglicher Job mit Nachholen, Berlin-Datum, Schalter | die beiden Zeilen davor | M |
| Endpunkte `monthly-proposals`, `run`, `rebuild`, `backfill-delivery-notes` | Service | M |
| Dashboard-Karte, Banner, Dialogkorrektur | Endpunkte | M |
| Tests | alles | M |
| **T4 gesamt** (bei fertigem Paket 1 und Nummernvergabe aus Paket 3) | | **M** (ohne diese Voraussetzungen **L**) |

Empfohlen ist, T4 als letzten Schritt von Paket 3 zu liefern. Die Korrektur des Datumsfehlers im Dialog (L11) und die LS-Doppelzählung (Probe 1) sind kleine Fehlerbehebungen, die schon vorher gehen. Bis dahin bleibt Sofortmaßnahme 3 bestehen: keinen Sammellauf starten.
*Prüfnachtrag:* Ebenso früh gehen der Ausschluss von `FAKTURIERT` im Lauf (P7) und der Positionsrabatt (P8). Ändert sich die Aggregation, laufen PDF und `GET /invoices/{id}/delivery-notes` mit, sonst passen die Beträge nicht mehr zur Rechnung (1.1).

---

## 4 Risiken
1. **Start vor Paket 1:** Die Entwürfe würden die Bestellungen hinter RE-00002/3/4 noch einmal enthalten. Gegenmittel: Der Schalter steht standardmäßig auf aus, und T4 kommt erst nach Paket 1.
2. **Start vor der Platzhalternummer:** Jeder verworfene Entwurf verbraucht Nummern bzw. erzeugt Gutschriften (Probe 3). Gegenmittel: dieselbe harte Abhängigkeit.
3. **Doppelzählung bei mehreren LS** (Probe 1): Das betrifft schon den heutigen manuellen Lauf. Der Job würde das Problem monatlich und unbemerkt wiederholen.
4. **Unvollständige Monatsrechnung:** Bestellungen, die ohne LS auf `GELIEFERT` stehen (Status-Weg, Import), fehlen. Gegenmittel: Hinweisliste; endgültig behebt das erst A1 (Paket 2), wenn beide Wege nach `GELIEFERT` einen LS sicherstellen.
5. **Bestellmenge statt Liefermenge:** Abgerechnet werden `order.lines`, nicht die Packliste. Teil- oder Minderlieferungen müssen vor der Freigabe in der Bestellung korrigiert sein (Frage 7).
6. **Zeitzone:** Mit `date.today()` in einem UTC-Container wird um Mitternacht der falsche Monat gerechnet. Gegenmittel: das Datum ausdrücklich in Europe/Berlin bilden und den Job um 06:30 laufen lassen.
7. **Mehrere Prozesse** (falls Prod doch gunicorn mit 4 Workern fährt, `docker-compose.prod.yml:25-29`): Ohne Laufsperre entstünden vier Läufe gleichzeitig. Gegenmittel: die Sperre über `billing_runs`.
8. **„Aktualisieren“ überschreibt Handänderungen am Entwurf.** Gegenmittel: Warnung im Dialog; keine automatische Aktualisierung.
9. **Freigabefrist:** Bleibt ein Entwurf liegen, verschiebt sich die Rechnungsstellung. Steuerlich entsteht die Umsatzsteuer bei Soll-Versteuerung trotzdem mit dem Leistungsmonat (**Annahme**, Frage 9). Die Dashboard-Karte sollte die Frist anzeigen.
   *Prüfnachtrag:* DATEV-Export und Umsatzübersicht wählen nach `invoice_date` (`datev_service.py:39`, `invoice_service.py:404`). Wird die Oktober-Rechnung am 06.11. freigegeben, landet sie im **November-Export**, obwohl die Leistung im Oktober liegt. Das muss die DATEV-Korrektur (B9) über den Leistungszeitraum lösen (Frage 9).
10. **Mandantentrennung:** Der bestehende `/admin/scheduler/run` wirkt mandantenübergreifend und sollte den neuen Job nicht auslösen können, sonst entstehen Entwürfe in fremden Mandanten.
    *Prüfnachtrag:* Dazu gehört der Schalter: Liest man ihn mit dem Standard-Rückgriff auf Umgebungsvariablen, schaltet eine Container-Variable alle Mandanten und den Golden-Seed `demo.seed` gleichzeitig ein (1.5).
11. *Prüfnachtrag:* **Zweiter Freigabeweg `/send`:** Er macht aus einem Entwurf `OFFEN`, ohne Finalisieren und heute auch für Vertrieb und Buchhaltung. Ohne Anpassung in Paket 3 geht ein Monatsentwurf mit Platzhalternummer an den Kunden (`invoices.py:254`, `:263`, `:270-272`).
12. *Prüfnachtrag:* **Verwerfen ohne Freigabe der LS:** Auf bestehenden DBs fehlt der Fremdschlüssel an `delivery_notes.invoice_id` (`tenancy.py:337`). Ein `DELETE`, das sich auf `ON DELETE SET NULL` verlässt, hält die LS dort dauerhaft fest, und die Lieferungen werden nie berechnet. Die Tests mit `create_all` zeigen das nicht.
13. *Prüfnachtrag:* **Abrechnungsart durch Mitarbeiter änderbar:** Der Kundenrouter lässt `production_staff` schreiben (`main.py:122`, `:700-705`). Ohne Feldschutz kann ein Mitarbeiter einen Kunden aus der Monatsrechnung nehmen oder hineinschieben.
14. *Prüfnachtrag:* **Migration still übersprungen:** Ein fehlerhafter `CREATE UNIQUE INDEX` in `_auto_migrate` bricht alle folgenden Migrationsschritte still ab (`tenancy.py:283-358`).

---

## 5 Fragen an Gernot / Steuerberater
1. (Gernot) Reicht es, wenn die Monatsrechnungen am **1. des Folgemonats** morgens als Entwurf bereitliegen? Am Monatsletzten selbst würden die Lieferungen dieses Tages fehlen.
2. (Gernot) Welche Kunden sollen monatlich abgerechnet werden? Alle übrigen bekommen dann weiter je Lieferung eine Rechnung.
3. (Gernot) Wurden die 46 importierten, rückdatierten Bestellungen (16.09.–07.10.) schon außerhalb des Systems abgerechnet? Falls nicht: Sollen die Lieferungen vom 01.–07.10. in die Oktober-Monatsrechnung und die vom September in eine eigene Rechnung? *Prüfnachtrag:* Dasselbe gilt für die Bestellung vom 08.10. (Klara Düran), die ebenfalls ohne LS auf `GELIEFERT` steht.
4. (Gernot) Ist es in Ordnung, dass die Monatsrechnung das **Datum der Freigabe** trägt und das Zahlungsziel ab dann läuft (statt Monatsletztem)?
5. (Gernot) Genügt der Hinweis im Dashboard, oder soll das System am 1. zusätzlich eine Mail schicken, und wenn ja, an wen?
6. (Gernot) Wird für jede Lieferung ein Lieferschein bzw. eine Packliste erzeugt, oder gibt es Lieferungen ganz ohne Lieferschein?
7. (Gernot) Werden Minder- oder Teillieferungen vor Monatsende in der Bestellung korrigiert? Die Monatsrechnung nimmt die Bestellmenge.
8. (Steuerberater) Darf eine vergessene Lieferung aus einem früheren Monat in die nächste Monatsrechnung (mit entsprechend angegebenem Liefer- bzw. Leistungszeitraum), oder braucht sie eine eigene Rechnung?
9. (Steuerberater) Soll- oder Ist-Versteuerung, und gibt es eine Dauerfristverlängerung? Bis zu welchem Tag müssen die Monatsrechnungen freigegeben sein? *Prüfnachtrag:* Und: Reicht es, wenn der DATEV-Export die im Folgemonat datierte Monatsrechnung über das Leistungsdatum (Leistungszeitraum) dem Leistungsmonat zuordnet? Oder bucht die Kanzlei nach Belegdatum?
10. (Gernot) Soll derselbe Monatslauf auch die Pfand-Sammelrechnung bzw. Pfand-Gutschrift aus seiner B4-Alternative vorschlagen?
11. (Gernot) Darf außer dem Admin noch jemand (z. B. ein Buchhaltungs-Login) Monatsrechnungen freigeben? Heute dürfen Vertrieb und Buchhaltung Rechnungen finalisieren.
12. *Prüfnachtrag:* (Gernot) „Monatlich fix“: Brauchen Sie in Ausnahmefällen trotzdem noch eine Sammelrechnung über einen freien Zeitraum, etwa beim Kundenwechsel mitten im Monat? Sonst entfällt die Von/Bis-Auswahl ganz.
