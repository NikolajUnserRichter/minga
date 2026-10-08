# Paket 1 — Steuer und Rechnung — Implementation Plan

> **For agentic workers:** Diesen Plan Task für Task in der angegebenen Reihenfolge abarbeiten (Vorbereitung, dann Task 1 bis Task 29). Schritte nutzen Checkbox-Syntax (`- [ ]`). Kein Task wird übersprungen, zusammengefasst oder vorgezogen. Inhaltliche Widersprüche zwischen Plan und Code oder abweichende Rot/Grün-Ergebnisse: stoppen und mit exakter Fehlerausgabe melden. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht (verschobene Zeilennummer, Anker durch einen früheren Task leicht verändert): selbst auflösen und in der Abschlussmeldung vermerken. Das Runbook am Ende und die Manager-Abnahme sind **keine** Worker-Schritte.

**Goal:** Rechnungen von Minga Greens sind steuerlich korrekt und korrigierbar. Pfand trägt den Satz aus dem Produktstamm (19 %), das Rechnungs-PDF weist Entgelt und Steuer je Satz aus, ein Storno hebt auch mehrzeilige Rechnungen exakt auf und landet nicht im Mahnwesen, der DATEV-Export bucht richtig und lässt sich wiederholen, jede Bestellung wird höchstens einmal abgerechnet, Entwürfe lassen sich prüfen und bearbeiten, und das Pfand von IFCO-Clearing-Kunden bleibt von der Rechnung fern. Danach lassen sich RE-2026-00002/3/4 per Storno und Neuausstellung berichtigen (Runbook).

**Architecture:** Jede Regel steht an genau einer Stelle und wird von allen Wegen benutzt:
- **Steuersatz einer Position:** `app/services/steuersatz.py` (`steuersatz_der_position`, `produkt_der_position`, `pfand_vorgaben`) für Bestellung, Rechnung aus Bestellung, Sammelrechnung und Produktstamm; die einmalige Datenkorrektur offener Bestellungen läuft über `tenancy._auto_migrate` mit Marker (`steuersatz_korrektur.py`).
- **Rechenregel:** `app.models.invoice.steuer_je_satz` (Rabatt und Steuer je Satz gerundet) speist Rechnungssummen, PDF-Steuerblock und DATEV. `InvoiceService.recalculate_totals` rechnet nach jedem Anlegen oder Löschen einer Position (`add_line`, Storno, Entwurf).
- **Storno:** Die Stornorechnung ist das Spiegelbild des Originals; beide Belege stehen auf `STORNIERT` und fallen aus Überfälligkeit, Mahnlauf, offenen Posten und Umsatz.
- **DATEV:** `datev_service.erloesgruppen` (eine Zeile je Rechnung und Erlöskonto, Debitor an Erlös, S/H) und die eine Erlöskonto-Regel `erloeskonto_fuer`/`ist_standard_erloeskonto`, die auch der Entwurf beim Satzwechsel nutzt.
- **Doppelabrechnung:** `InvoiceService.aktive_rechnung_zur_bestellung`/`abgerechnete_bestellungen` sperren „Rechnung aus Bestellung", manuelle Rechnungen mit Bestellbezug und den Sammellauf gleichermaßen; je Bestellung vertritt genau ein Lieferschein.
- **Pfandabrechnung je Kunde:** `Customer.pfand_abrechnung` (`JE_LIEFERUNG`/`KEINE`) und `ist_clearing_pfand` gelten für Rechnung aus Bestellung und Sammellauf; die Lieferschein-Anlage rechnet aus den Rechnungspositionen (`netto_je_lieferschein`).
- **GoBD:** Festgeschriebene Rechnungen werden weder neu berechnet noch geändert. Korrekturen nur per Storno und Neuausstellung (Runbook).

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`), SQLite je Mandant (Schema über `tenancy._auto_migrate`), Pydantic v2, ReportLab, React + TypeScript, TanStack Query 5, Playwright (nur `--list`).

**Spec:** `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, Abschnitt „Paketierung → Paket 1" (A3 vollständig, PDF je Satz, Storno, DATEV-Korrektur, B4-Kern, Korrektur RE-00002/3/4, Rechnungsliste ohne 20er-Kürzung, Doppelabrechnung sperren, Stornobeleg ohne Mahnung, `pfand_abrechnung` statt `pfand_via_clearing`, ein Lieferschein je Bestellung) und „Nachtrag 08.10. nachmittags" (Pfand Variante C). Der Plan setzt sechs einzeln geplante, am Code geprüfte und in Kopien durchgespielte Abschnitte S1–S6 zusammen.

**Ausgangsstand:** Branch `feat/paket1-steuer-rechnung` auf `efcea00` (= `c4a1832` + Import-Hotfix A6, der nur `imports.py` berührt). Zeilenangaben gelten für diesen Stand; nach früheren Tasks verschobene Stellen über den zitierten Anker finden.

## Global Constraints

- **Python** ausschließlich über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`; `backend/venv` und `backend/venv311` sind kaputt.
- **Einzeltests:** `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/<datei> -v`.
- **`REDIS_URL=memory://`** ersetzt den Celery-Broker im Prozess (verifiziert in S1 und S6: gleiche Fehlerliste, Minuten statt Viertelstunden). Läuft ein Befehl damit nicht durch: ohne den Zusatz wiederholen und das melden, den Lauf nie weglassen.
- **Vollauf** = Prozedur V (unten); mit `memory://` unter 1 min (auf `efcea00` gemessen: 28 s), ohne ca. 19 min.
- **Baseline:** 15 failed / 2 skipped / 1 error; `passed` ist 501 auf `c4a1832` und 507 auf `efcea00` und wächst mit jedem Task. Nur die Liste der Fehlernamen vergleichen, nie Anzahlen.
- **Einzige erwartete Änderung der Fehlerliste:** `test_services.py::TestInvoiceService::test_invoice_totals_update` wird ab Task 9 grün. Jeder neue Fehlername: stoppen und melden.
- **Schemaänderungen** nur über `backend/app/tenancy.py::_auto_migrate` (`_add_col_if_missing` im ersten `try`), kein Alembic; UUID-Spalten liegen als `CHAR(32)`.
- **Der S1-Korrekturblock (Task 6) bleibt der letzte Block in `_auto_migrate`.**
- **Testdatei:** alle neuen Tests nach `backend/tests/test_gernot_261008.py`. Task 1 legt sie mit dem gemeinsamen Kopf an, jeder spätere Task hängt nur ans Ende an und ergänzt keine Imports.
- **Präfixe in der Testdatei:** `_s1_`/`TestS1`, `_s2_`/`S2_`/`TestS2`, `_s3_`/`_S3_`/`TestS3`, `_datev_`/`DATEV_`/`TestDatev`, `_s5_`/`S5_`/`_d`/`TestS5`, `_s6_`/`S6_`/`TestS6`. Gleichnamige Helfer würden in Python still ersetzt.
- **GoBD:** Versendete bzw. finalisierte Rechnungen (jeder Status außer `ENTWURF`) sind unveränderlich. Korrektur nur per Storno und Neuausstellung.
- **Rechnungszeilen nie direkt in der DB ändern:** Das PDF wird bei jedem Abruf neu aus der DB erzeugt (`api/v1/invoices.py` ~466–500); eine Änderung schriebe das versendete Dokument um. Direkte ORM-Eingriffe stehen nur in Tests, um Altzustände nachzustellen.
- **Festgeschrieben, muss grün bleiben:** `test_pfand_rabatt.py:39-47` und `test_gernot_260821.py:705-708` — ein bewusst auf 7 % gesetzter Pfandartikel behält 7 %; der Fix übernimmt `product.tax_rate`, er erzwingt **nicht** 19 % für `is_deposit`.
- **Festgeschrieben, muss grün bleiben:** `test_pfand_rabatt.py:49-75` — bei manuellen Rechnungszeilen gilt der Satz vom Client.
- **Festgeschrieben, muss grün bleiben:** `test_gernot_260821.py:486-504` — Positionen ohne `product_id` mit ausdrücklichem Satz behalten den Client-Wert.
- **`tests/test_datev_export.py`** prüft heute nur Teilstrings; Task 16 ersetzt die Prüfung durch eine spaltengenaue.
- **Codex-Sandbox ohne Netzwerk:** kein `git pull`, kein `npm install`; `node_modules` liegt vor, `npm run build`, `tsc` und `playwright test --list` laufen offline.
- **Keine Verbindung zum Produktionsserver, kein Deploy:** Runbook und Manager-Abnahme führt nur der Manager mit Freigabe aus.
- **Nichts Fremdes ins Repo:** PDFs, Logs und Hilfsskripte nach `/tmp`; pytest mit `-p no:cacheprovider`, wo der Plan es angibt.
- **UI-Texte auf Deutsch.**
- **Je Task ein Commit** mit der angegebenen Nachricht; kein Push.

### Prozedur V — Vollauf gegen die Baseline

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/paket1-vollauf.log 2>&1
tail -1 /tmp/paket1-vollauf.log
grep -E '^(FAILED|ERROR) ' /tmp/paket1-vollauf.log | sed 's/ - .*//' | sort > /tmp/paket1-fehler-jetzt.txt
comm -13 /tmp/paket1-fehler-baseline.txt /tmp/paket1-fehler-jetzt.txt   # neue Fehlernamen
comm -23 /tmp/paket1-fehler-baseline.txt /tmp/paket1-fehler-jetzt.txt   # behobene Altlasten
```

Erwartet:
- Die letzte Logzeile nennt `passed` (sonst ist der Lauf abgebrochen, z. B. Collection-Fehler: stoppen und melden).
- `comm -13` gibt **nichts** aus.
- `comm -23` gibt vor Task 9 nichts aus, ab Task 9 genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

Weicht etwas ab: stoppen und Testnamen mit Traceback aus `/tmp/paket1-vollauf.log` melden.

### Vorbereitung (vor Task 1): Fehlerliste der Baseline festhalten

- [ ] **Step 1: Baseline erfassen**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q \
  --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/paket1-vollauf.log 2>&1
tail -1 /tmp/paket1-vollauf.log
grep -E '^(FAILED|ERROR) ' /tmp/paket1-vollauf.log | sed 's/ - .*//' | sort > /tmp/paket1-fehler-baseline.txt
cat /tmp/paket1-fehler-baseline.txt
```

Erwartet: letzte Logzeile `15 failed, 507 passed, 2 skipped, 1 error`, dazu 16 Zeilen, genau diese Namen in dieser Reihenfolge (am 08.10.2026 in einer Kopie von `efcea00` mit genau diesen Befehlen gemessen, 28 s):
- `ERROR tests/test_production_automation.py::test_approve_suggestion_creates_grow_batch`
- `FAILED tests/test_api.py::TestHealth::test_root_endpoint`
- `FAILED tests/test_auth_manual.py::test_auth_failure`
- `FAILED tests/test_auth_manual.py::test_auth_success`
- `FAILED tests/test_features.py::TestFeatures::test_subscription_processing`
- `FAILED tests/test_production_readiness.py::test_dunning_level1`
- `FAILED tests/test_production_readiness.py::test_dunning_level2`
- `FAILED tests/test_production_readiness.py::test_dunning_level3`
- `FAILED tests/test_production_readiness.py::test_quality_auto_approved`
- `FAILED tests/test_production_readiness.py::test_quality_rejected_high_loss`
- `FAILED tests/test_production_readiness.py::test_quality_rejected_low_note`
- `FAILED tests/test_refinements.py::test_main_app_imports`
- `FAILED tests/test_services.py::TestInvoiceService::test_finalize_empty_invoice_fails`
- `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`
- `FAILED tests/test_services.py::TestInvoiceService::test_record_full_payment`
- `FAILED tests/test_services.py::TestInvoiceService::test_record_partial_payment`

Weicht die Liste ab: stoppen und melden, nicht mit Task 1 beginnen. Die Datei `/tmp/paket1-fehler-baseline.txt` bleibt bis zum Ende des Plans liegen; jede Prozedur V vergleicht gegen sie.

## Review Focus

Die fünf Eingaben und Zustände, die Gernot und sein Team am ehesten treffen und die **kein automatischer Test** abdeckt. Die Backend-Regeln dahinter sind getestet, die Oberfläche nicht (das Frontend hat keine Unit-Tests). Jeder Punkt ist einem Task zugeordnet und hat eine Prüfung in der Manager-Abnahme (Abschnitt „Abnahme", M1–M5).

1. **Neuer Auftrag mit IFCO-Kiste über das Bestellformular; Position im Bearbeiten-Dialog nachtragen.** Das Formular schickt nach Task 7 keinen Satz mehr, der Server setzt den Produktsatz (Task 1). Getestet ist die API, nicht das Formular. → **Task 7** (Formular), **Task 1** (Server); Prüfung **M1**.
2. **Entwurf öffnen, Pfandzeile löschen, Summe ablesen** — in der Rechnungsliste („Bearbeiten") und im Belege-Dialog der Bestellung. Löschen und Neuberechnung sind getestet (Task 25), das Nachladen der Positionen beim Öffnen nur über einen Node-Nachbau des Abfrage-Caches. Ohne Nachladen sieht der Anwender „Keine Positionen" und keinen Löschknopf. → **Task 29**; Prüfung **M2**.
3. **Storno in der Oberfläche:** Grund „Falscher Steuersatz", Warnung im Dialog bei bereits erfasster Zahlung, Server-Warnungen als Hinweis, danach PDF beider Belege abrufbar. Kein Frontend-Test. → **Task 15**; Prüfung **M3**.
4. **Belege-Dialog im Tagesgeschäft:** „Neuer LS" bei vorhandenem Lieferschein fragt nach (Abbrechen legt nichts an); „Rechnung aus Bestellung" verschwindet nach der ersten Rechnung und kommt nach einem Storno wieder; Planung und Halle sehen einen grauen Hinweis statt eines roten Fehlers. Backend getestet (Tasks 20–24), der Dialog nur per manuellem Playwright-Lauf. → **Tasks 23, 24**; Prüfung **M4**.
5. **Kunde auf „Pfand nicht auf der Rechnung (IFCO-Clearing)" stellen und speichern.** Die API ist getestet (Task 26), das Kundenformular nicht. Schickte das Formular das Feld nicht mit, bliebe der Kunde still auf `JE_LIEFERUNG` und die nächste Rechnung trüge wieder Pfand. → **Task 29** (Step 4); Prüfung **M5**.

Zusätzlich hat jeder Abschnitt einen eigenen Review Focus für die getesteten Regeln (S1: Storno bleibt null, 7-%-Pfand bleibt; S2: kein Abruf schreibt; S3: Spiegelbild und Ausgleich; S4: Summe der Zeilen = Rechnungsbetrag; S6: Ablehnung ohne Spuren; S5: abgelehnte Änderung schreibt nichts).

## Reihenfolge und Abhängigkeiten

| Abschnitt | Inhalt | Tasks | Setzt voraus |
|---|---|---|---|
| S1 | Steuersatz aus dem Produkt (A3), Produktstamm, Shopify, Datenkorrektur offener Bestellungen | 1–7 | — |
| S2 | Eine Rechenregel, `recalculate_totals`, PDF mit Steuer je Satz, Mailen eines Entwurfs | 8–11 | — (Tests ohne `product_id`) |
| S3 | Stornorechnung als Spiegelbild, Stornopaar ausgeglichen, Warnungen, Oberfläche | 12–15 | Task 8, Task 9 (`recalculate_totals`), Task 11 (Block in `send_invoice_email`) |
| S4 | DATEV-Export bucht richtig, Wiederholungsexport | 16–19 | Task 8 hart (`steuer_je_satz`); S3 (Stornostatus) |
| S6 | Doppelte Abrechnung verhindern, ein Lieferschein je Bestellung, `FAKTURIERT` nicht erneut abrechnen | 20–24 | Task 10 (`Decimal`-Import im PDF); S1/S3 an denselben Funktionen |
| S5 | Entwurf prüfen und bearbeiten (B4-Kern), `pfand_abrechnung`, Rechnungsliste | 25–29 | Tasks 1/3, Task 9, Task 16, Tasks 20–24 |
| Runbook | Korrektur RE-2026-00002/3/4, Prüfung Doppelabrechnung, Sammellauf freigeben | — | Paket 1 deployt, Freigaben |

**S6 vor S5:** Tasks 28/29 bauen auf dem Filter `GET /invoices?order_id=` und dem Belege-Dialog aus Task 24 auf. Die Einzelfassung von S6 nannte die umgekehrte Reihenfolge; sie ist hier aufgelöst.

**Zusammengeführte Doppelarbeit:**
1. **Neuberechnung nach Positionsänderungen:** S2 plante ein Nachrechnen nur in `POST /invoices`, S3 die Behebung in `add_line` mit `recalculate_totals`, S5 deren Aufruf beim Löschen. Jetzt: eine Hilfsfunktion `InvoiceService.recalculate_totals` in **Task 9**, aufgerufen von `add_line`, vom Storno (Task 12) und vom Entwurf (Task 25). Der doppelte Test „`POST /invoices` mit zwei Positionen" steht nur noch in Task 9.
2. **Storno-Verknüpfung Lieferschein ↔ Rechnung:** Code nur in Task 21 (Anhängen bei „Rechnung aus Bestellung") und im unveränderten R1.6-Block (Lösen beim Storno). Die Produktionsschritte aus dem Runbook von S3 und dem Produktionsteil von S6 sind ein Runbook: ein Live-Nachweis, Prüfabfrage P1–P6 vor und nach der Korrektur, optionaler Lieferschein-Nachtrag zuletzt.
3. **Erlöskonto-Regel:** S4 (`datev_service.erloeskonto`) und S5 (`erloeskonto_fuer`, `ist_standard_erloeskonto`, eigene Kontentabelle) → eine Stelle in `datev_service` (Task 16); Task 25 importiert sie.
4. **`from decimal import Decimal` in `pdf_service.py`:** nur Task 10; Task 21 setzt nur die Bedingung.
5. **Testdatei-Kopf:** sechs Varianten → ein Kopf in Task 1.
6. **Vollauf und Baseline:** vier Verfahren → Prozedur V.
7. **Spec-Abgleich Pfand:** S5 plante das Ja/Nein-Feld `pfand_via_clearing`; laut Spec-Nachtrag baut Paket 1 `pfand_abrechnung` mit `JE_LIEFERUNG`/`KEINE`. Task 26 ist neu geschrieben, Tasks 27/29 und das Runbook sind umgestellt.
8. **Spec-Abgleich Sammellauf:** Der Spec-Nachtrag ordnet „FAKTURIERT-Bestellungen nicht erneut abrechnen" der Doppelabrechnungssperre in Paket 1 zu; S6 hatte es als Frage an Gernot offen gelassen. Task 22 schließt `FAKTURIERT` jetzt aus (ein Test mehr, Runbook P5 nur noch zur Information).

**Prüfstand der Zusammenführung** (in einer Kopie von `efcea00` außerhalb des Repos, mit dem Code dieses Plans):
- Task 8 + Task 9: beide Task-9-Tests rot (`Decimal('2.50') == Decimal('7.00')`, `AttributeError … 'recalculate_totals'`), nach Step 3 grün.
- Nachbarlauf nach Task 9 (`test_features.py`, `test_storno.py`, `test_pfand_rabatt.py`, `test_services.py`): 4 failed / 29 passed, nur Altlasten; `test_invoice_totals_update` grün.
- Task 12 danach: 2 failed / 2 passed mit den in Task 12 genannten Meldungen; nach Task 12 Step 3: 4 passed.
- Task 16 mit gemeinsamer Erlöskonto-Regel: alle Tests aus Task 16 und `test_datev_export.py` grün (22 passed zusammen mit Tasks 9 und 12). Import von `app.main` ohne Importzyklus, nachdem `invoice_service.py` und `invoices.py` die Regel aus `datev_service` importieren (Task 25).
- Task 26 (neu): 6 rot auf `efcea00`, 6 grün mit dem Code aus Task 26.
- Prozedur V und Vorbereitung: auf unverändertem `efcea00` genau die 16 Baseline-Namen, 28 s.
- **Zusammenspiel:** Auf einer Kopie mit S1 (Tasks 1–7) wurden die Backend-Teile von Task 8, 9, 10 (nur `Decimal`-Import), 12, 16 und 20–28 mit dem Code aus diesem Plan eingespielt, inklusive `FAKTURIERT`-Ausschluss. `test_gernot_261008.py` + `test_sammelrechnung.py` + `test_storno.py`: 140 passed. Prozedur V: 14 failed / 631 passed / 2 skipped / 1 error — keine neuen Fehlernamen, `test_invoice_totals_update` behoben. Der neue `FAKTURIERT`-Test war vor der Änderung rot (`assert [{'anzahl_lieferscheine': 1, …}] == []`).
- Kundenformular aus Task 29 (Step 1 und 4) in einer Frontend-Kopie: `tsc --noEmit` fehlerfrei.

Nicht im Zusammenspiel-Lauf, aber in den Einzelabschnitten durchgespielt: Tasks 10 (PDF-Spalten) und 11, 13–15, 17–19 sowie alle übrigen Frontend-Schritte. Rot-Zustände von Task 25 und 27 nach der Umstellung auf `pfand_abrechnung` wurden nicht erneut gemessen, ihre Grün-Zustände schon.

## File Structure

| Datei | Verantwortung | Abschnitt | Tasks |
|---|---|---|---|
| `backend/app/services/steuersatz.py` | **neu** — Satz der Position, Produkt der Position, Pfandregel des Produktstamms | S1 | 1, 4 |
| `backend/app/services/steuersatz_korrektur.py` | **neu** — einmalige Korrektur offener Bestellpositionen, gezielt aufrufbar | S1 | 6 |
| `backend/app/schemas/order.py` | `OrderLineBase.tax_rate` ohne Default | S1 | 1 |
| `backend/app/api/v1/sales.py` | Bestellung: Anlage, Kreditlimit, Nachtrag (Satz + Variante), PATCH + Audit | S1 | 1 |
| `backend/app/schemas/product.py` | `ProductUpdate.category` + Validator | S1 | 4 |
| `backend/app/api/v1/products.py` | Anlegen und PATCH über `pfand_vorgaben` | S1 | 4 |
| `backend/app/api/v1/imports.py` | `_import_products`: leere Zelle überschreibt nicht | S1 | 4 |
| `backend/app/services/shopify_service.py` | Produktsatz bzw. Shopify-Satz | S1 | 5 |
| `backend/app/tenancy.py` | Korrektur am Ende von `_auto_migrate`; Spalte `customers.pfand_abrechnung` im ersten `try` | S1, S5 | 6, 26 |
| `backend/app/models/invoice.py` | `_cent`, `steuer_je_satz`, `steuerausweis_stimmt`; `calculate_totals`, `get_tax_summary` | S2 | 8 |
| `backend/app/services/invoice_service.py` | `create_invoice_from_order` (Satz, Rabatt, Lieferdatum, Lieferschein, Clearing); `add_line` + `recalculate_totals`; `cancel_invoice` (Spiegelbild, Status, Warnungen, DATEV-Sperre); `check_overdue_invoices`; Kopf-Default 8300 weg; Doppelabrechnungs-Sperre; `waehle_vertreter`, `abgerechnete_bestellungen`; `ist_clearing_pfand`, `netto_je_lieferschein` | S1, S2, S3, S4, S6, S5 | 2, 9, 12, 13, 14, 16, 17, 20, 21, 22, 25, 27 |
| `backend/app/api/v1/invoices.py` | Sammelrechnung (`_aggregiere`, Vorschau, Festschreiben, `_abrechenbare_lieferscheine`); `send_invoice_email`; Storno-Endpoint; DATEV-Routen; 409; `order_id`-Filter; Entwurfsposition ändern/löschen; Lieferschein-Anlage; Sortierung | S1, S2, S3, S4, S6, S5 | 3, 11, 13, 14, 18, 20, 22, 24, 25, 27, 28 |
| `backend/app/services/pdf_service.py` | `Decimal`-Import, Spalte MwSt, Steuer je Satz; Anlage nur ohne Bestellbezug; Anlage aus Rechnungspositionen | S2, S6, S5 | 10, 21, 27 |
| `backend/app/tasks/invoice_tasks.py` | Überfälligkeit und Mahnlauf ohne Gutschriften/negative Beträge | S3 | 13 |
| `backend/app/schemas/invoice.py` | `reason_code` „FALSCHER_STEUERSATZ"; `DatevExportRequest.erneut_exportieren`; `InvoiceLineUpdate`-Grenzen, `InvoiceLineResponse.is_deposit` | S3, S4, S5 | 14, 18, 25 |
| `backend/app/services/datev_service.py` | Kontierung, gemeinsame Erlöskonto-Regel, Belegauswahl, Wiederholungsexport | S4 | 16, 17, 18 |
| `backend/app/api/v1/documents.py` | zweiter Lieferschein nur mit `?zusaetzlich=true` | S6 | 23 |
| `backend/app/models/customer.py` | Enum `PfandAbrechnung`, Spalte `pfand_abrechnung` | S5 | 26 |
| `backend/app/schemas/customer.py` | `pfand_abrechnung` in Create/Update/Response | S5 | 26 |
| `backend/tests/test_gernot_261008.py` | **neu** — alle Tests dieses Plans | alle | 1–6, 8–14, 16–18, 20–28 |
| `backend/tests/test_datev_export.py` | spaltengenaue Prüfung | S4 | 16 |
| `frontend/src/pages/Products.tsx` | Kategorie PFAND schlägt 19 % vor | S1 | 4 |
| `frontend/src/components/domain/CreateOrderModal.tsx` | kein fester Steuersatz | S1 | 7 |
| `frontend/src/types/index.ts` | `Invoice.original_invoice_id`; `PfandAbrechnung`, `Customer.pfand_abrechnung`, `InvoiceLine.is_deposit` | S3, S5 | 15, 29 |
| `frontend/src/services/api.ts` | `invoicesApi.cancel`, `exportDatev`/`downloadDatev`, `documentsApi.createDeliveryNote`, `invoicesApi.list` (`order_id`, `page_size`) | S3, S4, S6, S5 | 15, 19, 23, 24, 28 |
| `frontend/src/pages/Invoices.tsx` | Storno-Dialog, Typ „Stornorechnung", PDF für stornierte Belege; Kopfkonto-Feld weg, DATEV-Wiederholung; Liste 100 + Hinweis; `InvoiceDetail` exportiert, Nachladen, Pfand-Badge | S3, S4, S5 | 15, 19, 28, 29 |
| `frontend/src/pages/Dashboard.tsx` | Kachel „Offene Rechnungen" mit `page_size` | S5 | 28 |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | Rückfrage beim zweiten Lieferschein; Rechnungen per Filter; Knopf nur ohne aktive Rechnung; Positionen aufklappen | S6, S5 | 23, 24, 29 |
| `frontend/src/pages/Customers.tsx` | Auswahl „Pfandabrechnung" | S5 | 29 |
| `frontend/tests/e2e/full-suite.spec.ts` | Belege-Test wiederholbar | S6 | 24 |

---

## Abschnitt S1: Steuersatz kommt aus dem Produkt (A3) — Tasks 1–7

**Einordnung:** S1 läuft zuerst und setzt keinen anderen Abschnitt voraus. Später bauen darauf:
- **Task 1** legt `backend/tests/test_gernot_261008.py` mit dem gemeinsamen Kopf für alle Abschnitte an.
- **`add_line` erzwingt nie den Produktsatz** (Regel 5). Task 9 ändert nur die Summenbildung in `add_line`, Task 12 kopiert die Stornozeilen mit dem Satz der Originalzeile.
- **S6 und S5** setzen an `create_invoice_from_order` (Task 2) und `_aggregiere(db, notes)` (Task 3) an; Task 27 nutzt `produkt_der_position` (Task 1). Eine Sperre gegen Doppelabrechnung gehört in `_abrechenbare_lieferscheine` (Task 22), nicht in `_aggregiere`.
- **`tenancy.py`:** Task 26 trägt seine Spalte im ersten `try` von `_auto_migrate` ein. Der S1-Block aus Task 6 bleibt der letzte Block, denn die Korrektur liest `orders`, `order_lines`, `invoices`, `delivery_notes` und `products` über das ORM; stünde eine Spaltenmigration dahinter, scheiterte die Korrektur beim Deploy-Start mit „no such column" (nur geloggt, Nachlauf erst beim nächsten Neustart).
- **Runbook R4b** ruft `korrigiere_offene_bestellpositionen(db, nur_bestellungen=[…])` nach dem Storno und vor der Neuausstellung auf und prüft **beide** Listen, `uebersprungen_mit_rechnung` und `uebersprungen_status`.

Innerhalb von S1 gilt die Reihenfolge Task 1 → Task 7. Tasks 2, 3 und 6 nutzen das Modul `app/services/steuersatz.py` aus Task 1, Task 4 erweitert es.

### Verifizierter Ausgangsbefund (Code-Stand `efcea00`)

Der Branch `feat/paket1-steuer-rechnung` steht auf `efcea00`. Das ist `c4a1832` plus der Import-Hotfix A6. Von den Dateien, die S1 ändert, berührt der Hotfix nur `imports.py`; dort verschieben sich die Zeilen um 1 bis 7. Alle Zeilenangaben in S1 gelten für `efcea00`.

- `frontend/src/components/domain/CreateOrderModal.tsx:177` sendet bei jeder Position fest `tax_rate: 'REDUZIERT'`. `EditOrderModal.tsx:248-254` (`addOrderLine`) sendet keinen Satz. Dort greift der Schema-Default `REDUZIERT` aus `backend/app/schemas/order.py:35`. Der Fallback `line_data.tax_rate or TaxRate.REDUZIERT` in `sales.py:1028` und `:1337` greift deshalb nie.
- Die Kreditlimit-Schätzung in `sales.py:852` rechnet mit dem Client-Satz. Ein Pfandartikel wird dort mit 7 % geschätzt.
- `PATCH /sales/orders/{id}/lines/{line_id}` (`sales.py:1392-1469`) übernimmt den Client-Satz. Im Audit-Log stehen nur `quantity` und `unit_price` (`:1415-1418`, `:1436-1439`).
- `InvoiceService.create_invoice_from_order` (`invoice_service.py:177-215`):
  - nimmt `line.tax_rate` (`:205`), nicht den Satz des Produkts;
  - übergibt kein `discount_percent` (`:197-208`);
  - nimmt `requested_delivery_date` als Leistungsdatum (`:189`);
  - findet bei Positionen, die nur eine Variante tragen, kein Produkt. Ohne Produkt setzt `add_line` `is_deposit` nicht (`:163`).
- Die Sammelrechnung aggregiert in `invoices.py:563-565` nach `(beschreibung, unit, unit_price, tax_rate)`. `batch_run_commit` (`:615-625`) übergibt weder `product_id` noch `discount_percent`. Pfandzeilen verlieren dadurch `is_deposit`, Positionsrabatte gehen still verloren.
- `InvoiceService.add_line` behält den übergebenen Satz; S1 ändert `add_line` nicht (Task 9 ändert dort später nur die Summenbildung). `cancel_invoice` (`invoice_service.py:335-345`) ruft `add_line` mit `product_id` und dem Satz der Originalzeile auf. Würde `add_line` den Produktsatz erzwingen, bekäme der Storno einer alten 7-%-Pfandrechnung 19 % und ergäbe nicht null.
- `products.py:83-101` (Anlegen) setzt für Pfand 19 %. `update_product` (`:129-145`) tut das nicht. `ProductUpdate` (`schemas/product.py:280-305`) kennt **kein** Feld `category`. Die Produktmaske schickt die Kategorie bei jedem Speichern mit (`Products.tsx:358-372`), der PATCH verwirft sie still. Eine Kategorie ließ sich also nie ändern.
- Produktimport `imports.py:430-437`: Ist die Zelle `tax_rate` leer, setzt der Import `REDUZIERT` und überschreibt einen bestehenden Pfandartikel mit 7 %. Ein neuer Artikel mit `category=PFAND` und leerer `tax_rate` wird mit 7 % und ohne Pfandkennzeichen angelegt.
- **Gegenprobe zur Lückenprüfung „Import ohne Spalte category → MICROGREEN“: trifft nicht zu.** `category` ist Pflichtspalte (`imports.py:92`, `required=True`). `_parse_rows` verwirft eine Zeile ohne Kategorie mit „'category' fehlt“ (`:357-359`), bevor `_import_products` sie sieht. Der Fallback `ProductCategory.MICROGREEN` in `:430` ist toter Code. Er fällt mit der Umstellung in Task 4 weg; ein Absicherungstest hält das Verhalten fest.
- Shopify `shopify_service.py:217` setzt jede Position fest auf `TaxRate.STANDARD`, auch bekannte Microgreens.
- Bestellpositionen ohne Produkt und ohne Variante behalten den Satz vom Client. Abgesichert ist das durch `test_pfand_rabatt.py:49-75` und `test_gernot_260821.py:486-504`. Ein bewusst auf 7 % gesetzter Pfandartikel behält 7 % (`test_pfand_rabatt.py:39-47`, `test_gernot_260821.py:705-708`). S1 übernimmt `product.tax_rate`; es erzwingt **nicht** 19 % für `is_deposit`.

### Regeln, die S1 einführt

1. **Position mit Produkt** (`product_id` oder nur `product_variant_id` → `variant.parent_product`): Der Satz des Produktstamms ist verbindlich. Das gilt bei Anlage, Nachtrag und PATCH der Position, in der Kreditlimit-Schätzung, in der Rechnung aus der Bestellung und in der Sammelrechnung. Ein mitgeschickter Satz zählt nicht.
2. **Freitextposition:** Es gilt der Satz vom Client, ohne Angabe 7 %.
3. **Produktstamm:** Wird ein Artikel zum Pfand (Kategorie PFAND oder Pfandkennzeichen), gilt 19 %. Ausnahme: Der Satz wird ausdrücklich mitgeschickt. Beim Ändern und beim Import zählt nur der Übergang.
4. **Datenkorrektur:** Sie läuft einmal je Mandant. Sie betrifft nur offene, nicht abgerechnete Bestellungen. Rechnungen fasst sie nie an.
5. **Manuelle Rechnungszeile (`POST /invoices/{id}/lines`): bewusst unverändert.** Dort gilt der Satz vom Client, auch wenn `product_id` gesetzt ist. Fehlt der Satz, greift der Schema-Default `REDUZIERT` (`InvoiceLineCreate`, `schemas/invoice.py:30`). Ein API-Aufruf mit Pfand-`product_id` ohne Satz ergibt also 7 %. Das ist eine Entscheidung, keine offene Lücke:
   - Die Vorgabe lautet: Bei manuellen Rechnungszeilen gilt der Satz vom Client (`test_pfand_rabatt.py:49-75`).
   - Die Oberfläche schickt immer einen Satz, vorbelegt aus dem Produkt (`Invoices.tsx:1067`).
   - Die Zeile läuft über `InvoiceService.add_line`. Diese Methode muss den übergebenen Satz behalten, weil der Storno sie mit dem Satz der Originalzeile aufruft (Review Focus 1).

### Review Focus (S1)

1. **Storno bleibt null.** `add_line` erzwingt keinen Produktsatz. Getestet in Task 2 (`test_storno_bucht_mit_dem_satz_der_originalzeile_gegen`).
2. **Bewusst gewählte 7 % beim Pfand bleiben.** Das gilt bei Bestellung, PATCH und Import. Getestet in Task 1 und Task 4.
3. **Keine Rechnung wird verändert.** Bestellungen mit Rechnung (auch Entwurf) und Bestellungen in einer Sammelrechnung überspringt die Korrektur. Getestet in Task 6.
4. **Einmal je Mandant.** Ein Marker in `app_settings` sorgt dafür. Scheitert die Korrektur, blockiert sie keine Schema-Migration, es steht kein Marker, und `_auto_migrate` wirft nicht. Getestet in Task 6: `test_laeuft_je_mandant_nur_einmal` und `test_gescheiterte_korrektur_blockiert_keine_schemamigration`.
5. **Gezielter Aufruf verschluckt nichts.** `nur_bestellungen` meldet Bestellungen außerhalb der offenen Status und unbekannte IDs unter `uebersprungen_status`. Getestet in Task 6 (`test_gezielter_aufruf_meldet_nicht_offene_und_unbekannte_bestellungen`).
6. **Eine leere Importzelle überschreibt nie.** Getestet in Task 4.
7. **Eine Satzregel, eine Stelle.** Bestellung (Task 1), Rechnung aus der Bestellung (Task 2) und Sammelrechnung (Task 3) rufen alle `steuersatz_der_position` auf. Keine dieser Stellen trägt eine eigene `produkt.tax_rate if produkt else …`-Logik.

**Prüfstand:** Geprüft auf einer Kopie von `feat/paket1-steuer-rechnung` @ `efcea00`. Die Codeblöcke dieses Plans wurden per Skript wörtlich übernommen.
- Ausgangsstand: Die 39 neuen Tests ergaben 33 failed und 6 passed. Die 6 grünen sind gewollte Absicherungstests. Die Fehlermeldungen entsprechen den Angaben in den Rot-Schritten.
- Nach jedem Task ergaben sich die Zahlen aus den Grün-Schritten. Mit Tasks 1–6 liefen alle 39 Tests grün.
- Gegenläufe: Task 1 Step 7 ergab 134 passed, Task 2 Step 5 ergab 130 passed, `test_pfand_rabatt.py` und `test_gernot_260821.py` nach Task 4 ergaben 72 passed.
- Vollauf mit `REDIS_URL=memory://`:
  - Ausgangsstand: 15 failed, 507 passed, 2 skipped, 1 error.
  - Mit S1: 15 failed, 546 passed, 2 skipped, 1 error.
  - Die Liste der Fehlernamen ist beide Male die Baseline-Liste (Vorbereitung).
- Gegenprobe zur Lage des Korrektur-Blocks: An den Anfang oder ans Ende des ersten `try` von `_auto_migrate` verschoben, scheitert `test_gescheiterte_korrektur_blockiert_keine_schemamigration`. `test_auto_migrate_fuehrt_die_korrektur_aus` bleibt dabei grün.
- `npm run build` (`tsc` und `vite build`) lief mit beiden Frontend-Änderungen auf `efcea00` ohne Fehler.

---

### Task 1: Bestellpositionen mit Produkt tragen den Produktsatz

**Files:**
- Create: `backend/app/services/steuersatz.py`
- Modify: `backend/app/schemas/order.py:35` (`OrderLineBase.tax_rate`)
- Modify: `backend/app/api/v1/sales.py:33` (Import), `:852` (Kreditlimit), `:1028` (`create_order`), `:1322-1339` (`add_order_line`), `:1414-1440` (`update_order_line`)
- Create: `backend/tests/test_gernot_261008.py` mit dem gemeinsamen Kopf für alle Abschnitte

**Interfaces:**
- Produces:
  - `steuersatz.FREITEXT_STANDARD = TaxRate.REDUZIERT`
  - `steuersatz.produkt_der_position(db: Session, product_id: Optional[UUID], product_variant_id: Optional[UUID]) -> Optional[Product]`
  - `steuersatz.steuersatz_der_position(db: Session, product_id: Optional[UUID], product_variant_id: Optional[UUID], client_satz: Optional[TaxRate]) -> TaxRate`
  - `OrderLineCreate.tax_rate: Optional[TaxRate] = None`
  - `POST /sales/orders/{id}/lines` speichert `product_variant_id` wie `create_order`. Eine unbekannte Variante ergibt 404, eine Variante eines anderen Produkts 400. Bisher verwarf der Endpunkt die Variante. Eine reine Variantenposition wurde dadurch in der Rechnung zur Freitextzeile ohne `product_id` und ohne Pfandkennzeichen.
  - Audit-Log `UPDATE_LINE`: `old_values`/`new_values` enthalten zusätzlich `"tax_rate"` (Enum-Wert als String)
  - Test-Helfer `_s1_einheit`, `_s1_produkt`, `_s1_pfandkiste`, `_s1_variante`, `_s1_kunde`, `_s1_zeile`, `_s1_bestellung`, `_s1_altstand`, `_s1_altbestellung`, `_s1_pfandzeile`, `_s1_rechnung_aus`, `_s1_rechnungszeilen`, `_s1_produktimport`, `_s1_produkt_orm`. Task 2 bis Task 6 nutzen sie.

- [ ] **Step 1: Testdatei mit dem gemeinsamen Kopf, allen S1-Helfern und den Tests dieses Tasks anlegen**

Der Kopf (Docstring und Imports bis `_pdf_text`) gilt für die ganze Datei. Spätere Tasks hängen nur ans Ende an und ergänzen keine Imports.

```python
"""Gernot-Feedback vom 07./08.10.2026 — Paket 1 (Steuer und Rechnung).

Gemeinsame Testdatei der Abschnitte S1–S6. Helfer und Klassen tragen ein
Abschnitts-Präfix (_s1_/TestS1, _s2_/TestS2, _s3_/TestS3, _datev_/TestDatev,
_s5_/TestS5, _s6_/TestS6): ein gleichnamiger Helfer würde still ersetzt.
"""
import csv
import io
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import TestingSessionLocal
from tests.test_documents_preise import _pdf_text


# ============================================================
# S1 — Steuersatz kommt aus dem Produkt (A3)
#
# Pfandkisten liefen mit 7 % statt 19 %: das Bestellformular schickte fest
# REDUZIERT, das Schema setzte REDUZIERT als Default, die Rechnung aus der
# Bestellung übernahm den Satz der Bestellposition.
# ============================================================

_S1_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _s1_einheit():
    """Basiseinheit 'G' — Produktanlage und Produktimport verlangen sie."""
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="G").first()
        if unit is None:
            unit = UnitOfMeasure(code="G", name="Gramm", symbol="g",
                                 category=UnitCategory.WEIGHT, is_base_unit=True)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _s1_produkt(client, sku, name, preis, **extra):
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": name, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": _s1_einheit(), **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_pfandkiste(client, sku="PFAND-IFCO", **extra):
    """Pfandkiste wie in Gernots Stamm: Kategorie PFAND → 19 % + Pfandkennzeichen."""
    return _s1_produkt(client, sku, "IFCO-Kiste", "3.00",
                       category="PFAND", deposit_value="3.00", **extra)


def _s1_variante(client, produkt):
    r = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
        "name_suffix": "6er Stapel", "packaging_unit_id": produkt["base_unit_id"],
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_kunde(client, name="Ökoring Test", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_zeile(produkt=None, menge=2, preis="3.00", **extra):
    zeile = {
        "product_name": produkt["name"] if produkt else "Kresse (Freitext)",
        "quantity": menge, "unit": "STK", "unit_price": preis,
    }
    if produkt:
        zeile["product_id"] = produkt["id"]
    zeile.update(extra)
    return zeile


def _s1_bestellung(client, kunde, zeilen, liefertag="2026-10-09"):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": liefertag, "lines": zeilen,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _s1_altstand(order_id):
    """Stellt den Stand vor dem Fix her: jede Produktposition auf 7 %, Beträge
    und Summen passend dazu — so sehen Gernots offene Bestellungen aus."""
    from app.api.v1.sales import _calculate_line_amounts, _calculate_order_totals
    from app.models.enums import TaxRate
    from app.models.order import Order
    with TestingSessionLocal() as db:
        order = db.get(Order, uuid.UUID(order_id))
        for line in order.lines:
            if line.product_id or line.product_variant_id:
                line.tax_rate = TaxRate.REDUZIERT
                _calculate_line_amounts(line)
        _calculate_order_totals(order)
        db.commit()


def _s1_altbestellung(client, kunde, pfand, liefertag="2026-10-09"):
    """Offene Bestellung wie vor dem Fix: Kresse 7 %, Pfandkiste fälschlich 7 %."""
    order = _s1_bestellung(client, kunde, [
        _s1_zeile(None, menge=10, preis="2.50", tax_rate="REDUZIERT"),
        _s1_zeile(pfand, menge=2, preis="3.00"),
    ], liefertag=liefertag)
    _s1_altstand(order["id"])
    return client.get(f"/api/v1/sales/orders/{order['id']}").json()


def _s1_pfandzeile(client, order_id):
    order = client.get(f"/api/v1/sales/orders/{order_id}").json()
    return next(z for z in order["lines"] if z["product_id"])


def _s1_rechnung_aus(client, order):
    r = client.post(f"/api/v1/invoices/from-order/{order['id']}")
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s1_rechnungszeilen(invoice_id):
    """Rechnungszeilen direkt aus der DB — is_deposit steht nicht in der API-Antwort."""
    from app.models.invoice import InvoiceLine
    with TestingSessionLocal() as db:
        return [{
            "product_id": l.product_id,
            "tax_rate": l.tax_rate.value,
            "is_deposit": l.is_deposit,
            "discount_percent": Decimal(str(l.discount_percent)),
        } for l in db.query(InvoiceLine)
            .filter_by(invoice_id=uuid.UUID(invoice_id))
            .order_by(InvoiceLine.position)]


def _s1_produktimport(client, *zeilen):
    """Produktimport mit der Kopfzeile des echten Templates; je Zeile nur die
    angegebenen Spalten befüllt, alle anderen Zellen leer."""
    from openpyxl import Workbook, load_workbook
    tpl = client.get("/api/v1/imports/template/products").content
    header = [c.value for c in load_workbook(io.BytesIO(tpl))["Daten"][1]]
    spalten = [str(h).rstrip(" *") for h in header]
    wb = Workbook()
    ws = wb.active
    ws.title = "Daten"
    ws.append(header)
    for werte in zeilen:
        zeile = [""] * len(header)
        for spalte, wert in werte.items():
            zeile[spalten.index(spalte)] = wert
        ws.append(zeile)
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/v1/imports/products",
                    files={"file": ("products.xlsx", buf.getvalue(), _S1_XLSX)})
    assert r.status_code == 200, r.text
    return r.json()


def _s1_produkt_orm(db, sku, name, satz):
    """Produkt direkt über das ORM — für Service-Tests mit der db-Fixture ohne Client."""
    from app.models.product import Product, ProductCategory
    from app.models.unit import UnitOfMeasure, UnitCategory
    unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
    if unit is None:
        unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
        db.add(unit)
        db.flush()
    produkt = Product(sku=sku, name=name, category=ProductCategory.MICROGREEN,
                      base_unit_id=unit.id, tax_rate=satz)
    db.add(produkt)
    db.commit()
    return produkt


class TestS1SteuersatzInDerBestellung:
    """Task 1: Bestellpositionen mit Produkt tragen den Produktsatz."""

    def test_pfandkiste_bekommt_19_prozent_obwohl_das_formular_7_schickt(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(pfand, menge=2, preis="3.00", tax_rate="REDUZIERT"),
        ])
        zeile = order["lines"][0]
        assert zeile["tax_rate"] == "STANDARD"
        # 2 × 3,00 € = 6,00 € netto, 19 % = 1,14 €
        assert Decimal(str(zeile["line_vat"])) == Decimal("1.14")
        assert Decimal(str(order["total_gross"])) == Decimal("7.14")

    def test_ohne_satz_gilt_der_produktsatz(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand)])
        assert order["lines"][0]["tax_rate"] == "STANDARD"

    def test_bewusst_auf_7_prozent_gesetztes_pfand_bleibt_bei_7(self, client):
        """Der Fix übernimmt den Produktsatz — er erzwingt nicht 19 % für Pfand."""
        pfand = _s1_pfandkiste(client, sku="PFAND-7", tax_rate="REDUZIERT")
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand, tax_rate="STANDARD")])
        assert order["lines"][0]["tax_rate"] == "REDUZIERT"

    def test_freitext_behaelt_den_satz_vom_client(self, client):
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, tax_rate="STANDARD"),
            {"product_name": "Freitext ohne Satz", "quantity": 1, "unit": "STK", "unit_price": "2.00"},
        ])
        assert sorted(z["tax_rate"] for z in order["lines"]) == ["REDUZIERT", "STANDARD"]

    def test_position_nur_mit_variante_nimmt_den_satz_des_elternprodukts(self, client):
        pfand = _s1_pfandkiste(client)
        variante = _s1_variante(client, pfand)
        order = _s1_bestellung(client, _s1_kunde(client), [{
            "product_variant_id": variante["id"], "product_name": "IFCO-Kiste",
            "quantity": 1, "unit": "STK", "unit_price": "18.00", "tax_rate": "REDUZIERT",
        }])
        assert order["lines"][0]["tax_rate"] == "STANDARD"

    def test_nachgetragene_position_nimmt_den_produktsatz(self, client):
        """EditOrderModal schickt keinen Satz — bisher griff der Schema-Default 7 %."""
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, menge=10, preis="2.50", tax_rate="REDUZIERT"),
        ])
        r = client.post(f"/api/v1/sales/orders/{order['id']}/lines", json={
            "product_id": pfand["id"], "product_name": pfand["name"],
            "quantity": 2, "unit": "STK", "unit_price": "3.00",
        })
        assert r.status_code == 201, r.text
        assert r.json()["tax_rate"] == "STANDARD"
        detail = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        # 25,00 € × 7 % = 1,75 € | 6,00 € × 19 % = 1,14 €
        assert Decimal(str(detail["total_vat"])) == Decimal("2.89")

    def test_nachgetragene_variantenposition_behaelt_die_variante(self, client):
        """add_order_line verwarf product_variant_id — die Rechnung fand dann
        kein Produkt hinter der Position und setzte kein Pfandkennzeichen."""
        pfand = _s1_pfandkiste(client)
        variante = _s1_variante(client, pfand)
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, menge=10, preis="2.50", tax_rate="REDUZIERT"),
        ])
        r = client.post(f"/api/v1/sales/orders/{order['id']}/lines", json={
            "product_variant_id": variante["id"], "product_name": "IFCO-Kiste",
            "quantity": 1, "unit": "STK", "unit_price": "18.00",
        })
        assert r.status_code == 201, r.text
        assert r.json()["product_variant_id"] == variante["id"]

        detail = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        zeile = next(z for z in detail["lines"] if z["product_variant_id"])
        assert zeile["product_variant_id"] == variante["id"]
        assert zeile["tax_rate"] == "STANDARD"

        # Unbekannte Variante: 404 wie in create_order, kein Fremdschlüsselfehler
        r = client.post(f"/api/v1/sales/orders/{order['id']}/lines", json={
            "product_variant_id": str(uuid.uuid4()), "product_name": "?",
            "quantity": 1, "unit": "STK", "unit_price": "1.00",
        })
        assert r.status_code == 404, r.text

    def test_patch_kann_den_produktsatz_nicht_ueberschreiben(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand)])
        zeile = order["lines"][0]
        r = client.patch(f"/api/v1/sales/orders/{order['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "REDUZIERT"})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "STANDARD"

    def test_patch_zieht_den_alten_satz_nach_und_protokolliert_ihn(self, client):
        """Bestätigte Bestellung mit Altposition (7 %): die nächste Änderung
        bringt den Produktsatz und steht mit altem und neuem Satz im Audit-Log."""
        pfand = _s1_pfandkiste(client)
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(pfand)])
        zeile = order["lines"][0]
        _s1_altstand(order["id"])
        r = client.post(f"/api/v1/sales/orders/{order['id']}/confirm")
        assert r.status_code == 200, r.text

        r = client.patch(f"/api/v1/sales/orders/{order['id']}/lines/{zeile['id']}",
                         json={"quantity": 3})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "STANDARD"

        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        eintrag = next(e for e in log if e["action"] == "UPDATE_LINE")
        assert eintrag["old_values"]["tax_rate"] == "REDUZIERT"
        assert eintrag["new_values"]["tax_rate"] == "STANDARD"

    def test_kreditlimit_rechnet_pfand_mit_19_prozent(self, client):
        """100 € Pfand netto: mit 7 % 107 € (unter dem Limit von 110 €), richtig 119 €."""
        pfand = _s1_pfandkiste(client)
        kunde = _s1_kunde(client, credit_limit="110.00")
        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"], "requested_delivery_date": "2026-10-09",
            "lines": [_s1_zeile(pfand, menge=1, preis="100.00", tax_rate="REDUZIERT")],
        })
        assert r.status_code == 400, r.text
        assert "Kreditlimit" in r.json()["detail"]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1SteuersatzInDerBestellung -v`
Erwartet: **9 failed, 1 passed.**
- Grün ist nur `test_freitext_behaelt_den_satz_vom_client`; er sichert das bestehende Verhalten.
- Typische Fehlermeldung: `assert 'REDUZIERT' == 'STANDARD'`.
- `test_bewusst_auf_7_prozent…` scheitert umgekehrt mit `'STANDARD' == 'REDUZIERT'`.
- `test_nachgetragene_variantenposition…` scheitert mit `assert None == '<uuid der Variante>'`.
- `test_kreditlimit…` scheitert mit `assert 201 == 400`; der Response-Text zeigt `"total_gross":"107.00"`.

- [ ] **Step 3: Modul `backend/app/services/steuersatz.py` anlegen**

```python
"""Steuersatzregeln für Bestell- und Rechnungspositionen und den Produktstamm.

Gernot-Feedback 08.10.2026, A3: Pfandkisten liefen mit 7 % statt 19 %. Der
Produktstamm stand korrekt auf 19 %, aber das Bestellformular schickte fest
REDUZIERT, das Schema setzte REDUZIERT als Default, und die Rechnung aus der
Bestellung übernahm den Satz der Bestellposition.

Regeln:
- Position mit Produkt (direkt oder über eine Verpackungsvariante): der Satz
  des Produktstamms ist verbindlich. Ein mitgeschickter Satz zählt nicht.
- Freitextposition (weder Produkt noch Variante): der Satz vom Client; ohne
  Angabe 7 % (Lebensmittel).

Nicht hier: InvoiceService.add_line. Der Storno (cancel_invoice) ruft add_line
mit product_id und dem Satz der Originalzeile auf — würde add_line den
Produktsatz erzwingen, ergäbe der Storno einer alten 7-%-Pfandrechnung nicht
null.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import TaxRate
from app.models.product import Product, ProductVariant

#: Satz für Freitextpositionen ohne Angabe — Lebensmittel.
FREITEXT_STANDARD = TaxRate.REDUZIERT


def produkt_der_position(
    db: Session,
    product_id: Optional[UUID],
    product_variant_id: Optional[UUID],
) -> Optional[Product]:
    """Das Produkt hinter einer Position: direkt oder über die Variante."""
    if product_id:
        return db.get(Product, product_id)
    if product_variant_id:
        variante = db.get(ProductVariant, product_variant_id)
        return variante.parent_product if variante else None
    return None


def steuersatz_der_position(
    db: Session,
    product_id: Optional[UUID],
    product_variant_id: Optional[UUID],
    client_satz: Optional[TaxRate],
) -> TaxRate:
    """Verbindlicher Satz einer Bestellposition (siehe Modul-Docstring)."""
    produkt = produkt_der_position(db, product_id, product_variant_id)
    if produkt is not None and produkt.tax_rate is not None:
        return produkt.tax_rate
    return client_satz or FREITEXT_STANDARD
```

Ein unbekanntes `product_id` liefert `None` → Client-Satz. Den 404 wirft `create_order` danach wie bisher.

- [ ] **Step 4: Schema-Default entfernen**

In `backend/app/schemas/order.py`, Klasse `OrderLineBase`, Zeile 35 ersetzen:

```python
    # Kein Default mehr: der alte Default REDUZIERT überdeckte den Produktsatz
    # (A3, 08.10.2026). Bei Positionen mit Produkt zählt der Produktstamm,
    # siehe app/services/steuersatz.py; hier nur für Freitextpositionen.
    tax_rate: Optional[TaxRate] = Field(
        default=None,
        description="Steuersatz — nur für Freitextpositionen; bei Produkten gilt der Produktsatz",
    )
```

`Optional` ist in der Datei schon importiert. `OrderLineUpdate` und `OrderLineResponse` **nicht** anfassen.

- [ ] **Step 5: `sales.py` umstellen**

(a) Nach Zeile 33 (`from app.services.datev_service import DatevService`):

```python
from app.services.steuersatz import steuersatz_der_position
```

(b) Kreditlimit, Zeile 852 `tax_rate = (ld.tax_rate or TaxRate.REDUZIERT).rate` ersetzen durch:

```python
            # Derselbe Satz wie in der Position selbst — mit dem alten festen
            # 7 % schätzte die Prüfung jede Pfandkiste zu niedrig.
            tax_rate = steuersatz_der_position(
                db, ld.product_id, ld.product_variant_id, ld.tax_rate
            ).rate
```

(c) `create_order`, Zeile 1028 `tax_rate=line_data.tax_rate or TaxRate.REDUZIERT,  # Lebensmittel: 7%` ersetzen durch:

```python
            # Produktsatz verbindlich; nur Freitextpositionen nehmen den
            # Satz vom Client (ohne Angabe 7 %).
            tax_rate=steuersatz_der_position(
                db, line_data.product_id, line_data.product_variant_id, line_data.tax_rate
            ),
```

(d) `add_order_line`: Variante prüfen und speichern, Satz aus dem Produkt.
- Direkt nach dem Block `if line_data.product_id:` … `product_name = product.name` (Zeilen 1322-1326) und vor `line = OrderLine(` einfügen:

```python
    # Variante prüfen wie in create_order. Ohne Prüfung schlüge eine
    # unbekannte ID erst beim Commit am Fremdschlüssel fehl (500).
    if line_data.product_variant_id:
        variante = db.get(ProductVariant, line_data.product_variant_id)
        if not variante:
            raise HTTPException(status_code=404, detail="Verpackungs-Variante nicht gefunden")
        if line_data.product_id and variante.parent_product_id != line_data.product_id:
            raise HTTPException(status_code=400, detail="Variante gehört nicht zum gewählten Produkt")
```

- Im `OrderLine(...)` dieses Endpunkts (Zeilen 1328-1339) direkt nach `product_id=line_data.product_id,` die Zeile `product_variant_id=line_data.product_variant_id,` ergänzen. Bisher fehlte sie; `create_order` (Zeile 1022) speichert die Variante schon.
- Im selben `OrderLine(...)` die Zeile 1337 `tax_rate=line_data.tax_rate or TaxRate.REDUZIERT,` ersetzen durch:

```python
        tax_rate=steuersatz_der_position(
            db, line_data.product_id, line_data.product_variant_id, line_data.tax_rate
        ),
```

`ProductVariant` (Zeile 17) und `HTTPException` (Zeile 9) sind in `sales.py` schon importiert.

(e) `update_order_line`: Die Zeilen 1414-1422 ersetzen, also den Block bis vor `_calculate_line_amounts(line)` (Zeile 1424). Nicht verwechseln: `update_order` trägt in Zeile 1081 den ähnlichen Kommentar `# Alte Werte für Audit-Log speichern`. Dieser Block bleibt unverändert. Eine Textsuche nach `# Alte Werte für Audit` trifft zuerst Zeile 1081; deshalb nach dem ganzen Block suchen. Er lautet wörtlich:

```python
    # Alte Werte für Audit
    old_values = {
        "quantity": str(line.quantity),
        "unit_price": str(line.unit_price)
    }

    update_data = line_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(line, field, value)
```

Neu:

```python
    # Alte Werte für Audit — der Steuersatz gehört dazu, er ändert den Betrag.
    old_values = {
        "quantity": str(line.quantity),
        "unit_price": str(line.unit_price),
        "tax_rate": line.tax_rate.value,
    }

    update_data = line_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(line, field, value)

    # Bei Positionen mit Produkt gilt der Produktsatz — auch wenn der Client
    # einen anderen schickt oder die Position noch den alten festen 7 %
    # trägt (A3, 08.10.2026).
    line.tax_rate = steuersatz_der_position(
        db, line.product_id, line.product_variant_id, line.tax_rate
    )
```

Im selben Endpunkt `new_values` des `UPDATE_LINE`-Eintrags (Zeile ~1436) ergänzen:

```python
            new_values={
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "tax_rate": line.tax_rate.value,
            }
```

Den Import `TaxRate` in Zeile 15 stehen lassen. `subscription_tasks.py` importiert Funktionen aus `sales.py`, nicht `TaxRate`, aber der Import schadet nicht.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1SteuersatzInDerBestellung -v`
Erwartet: 10 passed.

- [ ] **Step 7: Bestehende Tests, die das Verhalten festschreiben**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_pfand_rabatt.py tests/test_gernot_260821.py tests/test_gernot_260917.py tests/test_erp.py tests/test_gernot_260817.py -q`
Erwartet: keine neuen Fehler. Ein Fehler in `test_pfand_rabatt.py:39-75` oder `test_gernot_260821.py:486-504/705-708` ist ein inhaltlicher Befund: stoppen und melden.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/steuersatz.py backend/app/schemas/order.py \
        backend/app/api/v1/sales.py backend/tests/test_gernot_261008.py
git commit -m "fix(steuer): Bestellpositionen mit Produkt tragen den Steuersatz des Produkts"
```

---

### Task 2: Rechnung aus der Bestellung — Produktsatz, Positionsrabatt, Leistungsdatum

**Files:**
- Modify: `backend/app/services/invoice_service.py:21` (Import), `:177-215` (`create_invoice_from_order`)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `produkt_der_position` und `steuersatz_der_position` aus Task 1. Die Helfer `_s1_altbestellung`, `_s1_rechnung_aus` und `_s1_rechnungszeilen` stammen aus Task 1.
- Produces: `create_invoice_from_order` setzt:
  - je Rechnungszeile `tax_rate = steuersatz_der_position(...)`: den Produktsatz (Produkt direkt oder über die Variante), sonst den Satz der Bestellposition, ohne Satz 7 %. Das ist dieselbe Funktion wie bei der Bestellung, keine eigene Regel;
  - `product_id`/`sku` des Produkts hinter der Position, damit `is_deposit` stimmt;
  - `discount_percent` der Position;
  - `Invoice.delivery_date = order.actual_delivery_date or order.requested_delivery_date`.

  Die Signatur bleibt `create_invoice_from_order(self, order_id: UUID) -> Invoice`. **`add_line` bleibt unverändert.**

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS1RechnungAusBestellung:
    """Task 2: Rechnung aus der Bestellung — Satz, Rabatt, Leistungsdatum."""

    def test_altposition_mit_7_prozent_wird_mit_dem_produktsatz_fakturiert(self, client):
        """Der Weg von RE-00002/3/4: Bestellposition 7 %, Produkt 19 %."""
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)

        rechnung = _s1_rechnung_aus(client, order)

        zeilen = _s1_rechnungszeilen(rechnung["id"])
        pfandzeile = next(z for z in zeilen if z["product_id"] is not None)
        assert pfandzeile["tax_rate"] == "STANDARD"
        assert pfandzeile["is_deposit"] is True
        assert next(z for z in zeilen if z["product_id"] is None)["tax_rate"] == "REDUZIERT"
        # 25,00 € × 7 % = 1,75 € | 6,00 € × 19 % = 1,14 €
        assert Decimal(str(rechnung["tax_amount"])) == Decimal("2.89")

    def test_variantenposition_traegt_satz_und_pfandkennzeichen(self, client):
        pfand = _s1_pfandkiste(client)
        variante = _s1_variante(client, pfand)
        order = _s1_bestellung(client, _s1_kunde(client), [{
            "product_variant_id": variante["id"], "product_name": "IFCO-Kiste",
            "quantity": 1, "unit": "STK", "unit_price": "18.00",
        }])
        _s1_altstand(order["id"])

        zeile = _s1_rechnungszeilen(_s1_rechnung_aus(client, order)["id"])[0]

        assert zeile["tax_rate"] == "STANDARD"
        assert zeile["is_deposit"] is True
        assert zeile["product_id"] == uuid.UUID(pfand["id"])

    def test_positionsrabatt_wird_uebernommen(self, client):
        order = _s1_bestellung(client, _s1_kunde(client), [
            _s1_zeile(None, menge=10, preis="10.00", tax_rate="REDUZIERT", discount_percent="10"),
        ])
        assert Decimal(str(order["total_net"])) == Decimal("90.00")

        rechnung = _s1_rechnung_aus(client, order)

        assert _s1_rechnungszeilen(rechnung["id"])[0]["discount_percent"] == Decimal("10")
        assert Decimal(str(rechnung["subtotal"])) == Decimal("90.00")

    def test_leistungsdatum_ist_das_tatsaechliche_lieferdatum(self, client):
        from app.models.order import Order
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(None, tax_rate="REDUZIERT")],
                               liefertag="2026-10-07")
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(order["id"])).actual_delivery_date = date(2026, 10, 8)
            db.commit()

        assert _s1_rechnung_aus(client, order)["delivery_date"] == "2026-10-08"

    def test_ohne_lieferung_bleibt_das_wunschlieferdatum(self, client):
        order = _s1_bestellung(client, _s1_kunde(client), [_s1_zeile(None, tax_rate="REDUZIERT")],
                               liefertag="2026-10-07")
        assert _s1_rechnung_aus(client, order)["delivery_date"] == "2026-10-07"

    def test_storno_bucht_mit_dem_satz_der_originalzeile_gegen(self, client):
        """Absicherung: der Produktsatz wird NICHT in add_line erzwungen. Der
        Storno einer alten 7-%-Pfandrechnung muss mit 7 % gegenbuchen, sonst
        ergibt er nicht null."""
        pfand = _s1_pfandkiste(client)
        kunde = _s1_kunde(client)
        rechnung = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": "2026-10-08",
        }).json()
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "IFCO-Kiste", "quantity": 2, "unit": "STK", "unit_price": "3.00",
            "tax_rate": "REDUZIERT", "product_id": pfand["id"],
        })
        assert r.status_code == 201, r.text
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text

        storno = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                             json={"reason": "Steuersatz falsch"})
        assert storno.status_code == 200, storno.text

        gutschrift = storno.json()["credit_note"]
        assert [z["tax_rate"] for z in _s1_rechnungszeilen(gutschrift["id"])] == ["REDUZIERT"]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1RechnungAusBestellung -v`
Erwartet: **4 failed, 2 passed.**
- Fehlschläge:
  - `…altposition…`: `'REDUZIERT' == 'STANDARD'`
  - `…variantenposition…`: `'REDUZIERT' == 'STANDARD'`
  - `…positionsrabatt…`: `Decimal('0.00') == Decimal('10')`
  - `…tatsaechliche_lieferdatum`: `'2026-10-07' == '2026-10-08'`
- Grün schon jetzt: `…wunschlieferdatum` und der Storno-Absicherungstest.

- [ ] **Step 3: `create_invoice_from_order` umstellen**

In `backend/app/services/invoice_service.py` nach Zeile 21 (`from app.models.product import Product`):

```python
from app.services.steuersatz import produkt_der_position, steuersatz_der_position
```

Die Methode `create_invoice_from_order` bis einschließlich der `for line in order.lines:`-Schleife ersetzen. Der Teil ab `self.db.refresh(invoice, ["lines"])` bleibt unverändert.

```python
    def create_invoice_from_order(self, order_id: UUID) -> Invoice:
        """
        Erstellt eine Rechnung aus einer Bestellung.

        - Steuersatz: bei Positionen mit Produkt (direkt oder über die
          Variante) der Satz des Produktstamms, nicht der gespeicherte Satz
          der Bestellposition — den setzte das Bestellformular bis 08.10.2026
          fest auf 7 % (A3). Freitextpositionen behalten ihren Satz.
        - Positionsrabatt wird übernommen (fehlte bisher still).
        - Leistungsdatum: das tatsächliche Lieferdatum, ersatzweise das
          Wunschlieferdatum — dieselbe Regel wie die Sammelrechnung.
        """
        order = self.db.get(Order, order_id)
        if not order:
            raise ValueError("Bestellung nicht gefunden")

        # Rechnung erstellen
        invoice = self.create_invoice(
            customer_id=order.customer_id,
            order_id=order_id,
            delivery_date=order.actual_delivery_date or order.requested_delivery_date,
        )

        # Positionen aus Bestellung übernehmen
        for line in order.lines:
            # Beschreibung wie bisher aus dem direkt verknüpften Produkt — bei
            # reinen Variantenpositionen bleibt der gespeicherte Name stehen.
            direkt = self.db.get(Product, line.product_id) if line.product_id else None
            # Pfandkennzeichen und SKU aus dem Produkt hinter der Position,
            # auch wenn nur die Variante gesetzt ist.
            produkt = produkt_der_position(self.db, line.product_id, line.product_variant_id)

            self.add_line(
                invoice_id=invoice.id,
                description=direkt.name if direkt else (line.beschreibung or f"Position {line.id}"),
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price or Decimal("0"),
                product_id=produkt.id if produkt else None,
                sku=produkt.sku if produkt else None,
                discount_percent=line.discount_percent or Decimal("0"),
                # Dieselbe Satzregel wie in der Bestellung (Task 1) — nicht hier
                # nachgebaut, damit sie nur an einer Stelle steht.
                tax_rate=steuersatz_der_position(
                    self.db, line.product_id, line.product_variant_id, line.tax_rate
                ),
                order_item_id=line.id,
                harvest_batch_ids=[line.harvest_id] if line.harvest_id else None,
            )
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k "TestS1SteuersatzInDerBestellung or TestS1RechnungAusBestellung" -v`
Erwartet: 16 passed.

- [ ] **Step 5: Bestehende Rechnungstests**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_260821.py tests/test_erp.py tests/test_storno.py tests/test_deposit.py -q`
Erwartet: keine neuen Fehler. `test_storno.py` stellt die Gutschrift über `add_line` aus — bleibt sie grün, ist `add_line` unberührt geblieben.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/invoice_service.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): Rechnung aus Bestellung nimmt Produktsatz, Positionsrabatt und Lieferdatum"
```

---

### Task 3: Sammelrechnung übergibt Produkt, Produktsatz und Positionsrabatt

**Files:**
- Modify: `backend/app/api/v1/invoices.py:511` (Import danach), `:548-570` (`_aggregiere`), `:574-592` (`batch_run_preview`), `:596-626` (`batch_run_commit`)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `produkt_der_position` und `steuersatz_der_position` (Task 1).
- Produces:
  - `_aggregiere(db, notes) -> dict`. Neue Signatur, beide Aufrufer werden angepasst. Der Positionsschlüssel ist `(beschreibung, unit, unit_price, tax_rate, product_id, discount_percent)`; die Indizes 0–3 bleiben gleich.
  - Die Vorschau liefert je Position zusätzlich `discount_percent`. `summe_netto` rechnet den Rabatt ein.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS1Sammelrechnung:
    """Task 3: Sammelrechnung übergibt Produkt, Produktsatz und Rabatt."""

    def _lauf(self, client, kunde, *zeilen):
        order = _s1_bestellung(client, kunde, list(zeilen), liefertag="2026-09-15")
        _s1_altstand(order["id"])
        note = client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={})
        assert note.status_code == 201, note.text
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": "2026-09-01", "period_to": "2026-09-30",
            "customer_ids": [kunde["id"]],
        })
        assert r.status_code == 201, r.text
        return r.json()["rechnungen"][0]

    def test_pfandzeile_traegt_produkt_satz_und_kennzeichen(self, client):
        pfand = _s1_pfandkiste(client)
        rechnung = self._lauf(client, _s1_kunde(client), _s1_zeile(pfand, menge=4, preis="3.00"))

        zeile = _s1_rechnungszeilen(rechnung["id"])[0]
        assert zeile["product_id"] == uuid.UUID(pfand["id"])
        assert zeile["is_deposit"] is True
        assert zeile["tax_rate"] == "STANDARD"
        # 4 × 3,00 € netto + 19 % = 14,28 € Pfand brutto
        assert Decimal(str(rechnung["total_deposit"])) == Decimal("14.28")

    def test_positionsrabatt_bleibt_erhalten(self, client):
        rechnung = self._lauf(client, _s1_kunde(client), _s1_zeile(
            None, menge=10, preis="10.00", tax_rate="REDUZIERT", discount_percent="10"))
        assert Decimal(str(rechnung["subtotal"])) == Decimal("90.00")
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1Sammelrechnung -v`
Erwartet: **2 failed.**
- `…pfandzeile…` scheitert mit `None == UUID(...)`: Die Zeile hat kein Produkt.
- `…positionsrabatt…` scheitert mit `Decimal('100.00') == Decimal('90.00')`.

- [ ] **Step 3: Aggregation und Festschreiben umstellen**

(a) Import: Die Zeilen 508-511 (`from app.models.documents import DeliveryNote` bis `from app.models.order import Order, OrderLine`) bleiben stehen. Direkt nach Zeile 511 eine Zeile einfügen:

```python
from app.services.steuersatz import produkt_der_position, steuersatz_der_position
```

`TaxRate` braucht `invoices.py` dafür nicht. Die Satzregel steckt ganz in `steuersatz_der_position`.

(b) `_aggregiere` ersetzen:

```python
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
    return kunden
```

(c) In `batch_run_preview`:
- `kunden = _aggregiere(_abrechenbare_lieferscheine(db, anfrage))` wird zu `kunden = _aggregiere(db, _abrechenbare_lieferscheine(db, anfrage))`.
- Positions-Dict und Summe:

```python
            "positionen": [{
                "description": key[0], "unit": key[1],
                "unit_price": key[2], "tax_rate": key[3].value,
                "discount_percent": key[5],
                "quantity": pos["menge"],
            } for key, pos in sorted(k["positionen"].items(), key=lambda e: (e[0][0], e[0][2]))],
            "summe_netto": sum((pos["menge"] * key[2] * (1 - key[5] / 100)
                                for key, pos in k["positionen"].items()),
                               Decimal("0")),
```

(d) In `batch_run_commit`:
- Denselben `_aggregiere(db, …)`-Aufruf anpassen.
- Die Zeilenschleife lautet:

```python
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
```

Der Rest von `batch_run_commit` bleibt unverändert. Dazu gehören `InvoiceLineSource`, die Zuordnung der Lieferscheine, `calculate_totals` und Status `OFFEN`. Die Sortierung nutzt nur die Indizes 0 und 2, ein `None` als `product_id` stört sie nicht.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_sammelrechnung.py tests/test_storno.py -v`
Erwartet: alle S1-Tests bis hier (18) und `test_sammelrechnung.py` grün. `test_sammelrechnung.py` nutzt Freitextpositionen ohne Rabatt; ihre Aggregation bleibt gleich.

- [ ] **Step 5: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` ohne Ausgabe.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "fix(sammelrechnung): Pfandkennzeichen, Produktsatz und Positionsrabatt gingen verloren"
```

---

### Task 4: Produktstamm — PATCH und Import mit derselben Pfandregel wie das Anlegen

**Files:**
- Modify: `backend/app/services/steuersatz.py` (+ `pfand_vorgaben`)
- Modify: `backend/app/schemas/product.py:8` (Import `field_validator`), `:280-305` (`ProductUpdate`: Feld `category` und Validator)
- Modify: `backend/app/api/v1/products.py:28` (Import), `:83-101` (`create_product`), `:129-145` (`update_product`)
- Modify: `backend/app/api/v1/imports.py:33` (Import), `:424-443` (`_import_products`)
- Modify: `frontend/src/pages/Products.tsx:455-460` (Kategorie-Auswahl)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces:
  - `steuersatz.pfand_vorgaben(werte: dict, explizit: set[str], bisher: Optional[Product] = None) -> dict` (gibt eine Kopie zurück)
  - `ProductUpdate.category: Optional[ProductCategory] = None`. Die Maske schickt das Feld schon heute; bisher verwarf der PATCH es still. Ein ausdrückliches `"category": null` ergibt 422 (Validator `_kategorie_nicht_leer`), ein weggelassenes Feld bleibt erlaubt.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS1Produktstamm:
    """Task 4: PATCH und Import wenden dieselbe Pfandregel an wie das Anlegen."""

    def test_patch_auf_pfandkennzeichen_setzt_19_prozent(self, client):
        kiste = _s1_produkt(client, "KISTE-1", "Mehrwegkiste", "3.00", category="PACKAGING")
        assert kiste["tax_rate"] == "REDUZIERT"
        r = client.patch(f"/api/v1/products/{kiste['id']}", json={"is_deposit": True})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "STANDARD"

    def test_patch_auf_kategorie_pfand_setzt_kennzeichen_und_19_prozent(self, client):
        kiste = _s1_produkt(client, "KISTE-2", "Mehrwegkiste", "3.00", category="PACKAGING")
        r = client.patch(f"/api/v1/products/{kiste['id']}", json={"category": "PFAND"})
        assert r.status_code == 200, r.text
        assert r.json()["category"] == "PFAND"
        assert r.json()["is_deposit"] is True
        assert r.json()["tax_rate"] == "STANDARD"

    def test_ausdruecklicher_satz_im_patch_gewinnt(self, client):
        kiste = _s1_produkt(client, "KISTE-3", "Mehrwegkiste", "3.00", category="PACKAGING")
        r = client.patch(f"/api/v1/products/{kiste['id']}",
                         json={"is_deposit": True, "tax_rate": "REDUZIERT"})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "REDUZIERT"

    def test_patch_mit_leerer_kategorie_wird_abgewiesen(self, client):
        """products.category ist NOT NULL: ein ausdrückliches null ergibt 422,
        nicht einen Datenbankfehler (500) beim Commit."""
        kiste = _s1_produkt(client, "KISTE-4", "Mehrwegkiste", "3.00", category="PACKAGING")
        r = client.patch(f"/api/v1/products/{kiste['id']}", json={"category": None})
        assert r.status_code == 422, r.text
        assert client.get(f"/api/v1/products/{kiste['id']}").json()["category"] == "PACKAGING"

    def test_speichern_eines_7_prozent_pfands_kippt_den_satz_nicht(self, client):
        """Erneutes is_deposit=true ist kein Übergang — der bewusst gewählte Satz bleibt."""
        pfand = _s1_pfandkiste(client, sku="PFAND-7B", tax_rate="REDUZIERT")
        r = client.patch(f"/api/v1/products/{pfand['id']}",
                         json={"is_deposit": True, "name": "IFCO-Kiste 7 %"})
        assert r.status_code == 200, r.text
        assert r.json()["tax_rate"] == "REDUZIERT"

    def test_reimport_ohne_steuersatz_laesst_pfand_bei_19_prozent(self, client):
        pfand = _s1_pfandkiste(client, sku="PFAND-IMP1")
        assert pfand["tax_rate"] == "STANDARD"

        ergebnis = _s1_produktimport(client, {
            "sku": "PFAND-IMP1", "name": "IFCO-Kiste", "category": "PFAND", "base_price": "3.10",
        })

        assert ergebnis["updated"] == 1, ergebnis
        p = client.get(f"/api/v1/products/{pfand['id']}").json()
        assert p["tax_rate"] == "STANDARD"
        assert Decimal(str(p["base_price"])) == Decimal("3.10")

    def test_neuer_pfandartikel_ohne_steuersatz_bekommt_19_prozent(self, client):
        _s1_einheit()
        ergebnis = _s1_produktimport(client, {"sku": "PFAND-IMP2", "name": "IFCO-Kiste", "category": "PFAND"})
        assert ergebnis["created"] == 1, ergebnis
        p = next(p for p in client.get("/api/v1/products").json() if p["sku"] == "PFAND-IMP2")
        assert p["is_deposit"] is True
        assert p["tax_rate"] == "STANDARD"

    def test_zeile_ohne_kategorie_laesst_den_bestand_unveraendert(self, client):
        """Gegenprobe zur Lückenprüfung: category ist Pflichtspalte, eine Zeile
        ohne sie wird verworfen — der Pfandartikel bleibt PFAND."""
        pfand = _s1_pfandkiste(client, sku="PFAND-IMP3")
        ergebnis = _s1_produktimport(client, {"sku": "PFAND-IMP3", "name": "IFCO-Kiste"})
        assert ergebnis["updated"] == 0
        assert any("category" in f for f in ergebnis["errors"]), ergebnis
        p = client.get(f"/api/v1/products/{pfand['id']}").json()
        assert p["category"] == "PFAND"
        assert p["tax_rate"] == "STANDARD"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1Produktstamm -v`
Erwartet: **5 failed, 3 passed.**
- Fehlschläge:
  - `…pfandkennzeichen…`: `'REDUZIERT' == 'STANDARD'`
  - `…kategorie_pfand…`: `'PACKAGING' == 'PFAND'`, weil der PATCH die Kategorie verwirft
  - `…leerer_kategorie…`: `assert 200 == 422`, weil der PATCH das Feld heute still verwirft. Ohne den Validator aus Step 4 käme nach dem Fix ein Datenbankfehler statt 422.
  - `…reimport…`: `'REDUZIERT' == 'STANDARD'`
  - `…neuer_pfandartikel…`: `assert False is True`. Er scheitert schon an der Zeile `assert p["is_deposit"] is True`, vor der Satzprüfung: Der Import setzt heute für `category=PFAND` kein Pfandkennzeichen.
- Grün schon jetzt: `…ausdruecklicher_satz…`, `…kippt_den_satz_nicht` und `…ohne_kategorie…`. Sie sichern ab, dass die Regel nicht zu weit greift.

- [ ] **Step 3: `pfand_vorgaben` in `steuersatz.py`**

Import ergänzen: `from app.models.product import Product, ProductCategory, ProductVariant`. Im Modul-Docstring unter „Regeln:“ ergänzen:

```
- Produktstamm: wird ein Artikel zum Pfandartikel, gilt 19 % — außer der Satz
  kommt ausdrücklich mit. Ein bewusst auf 7 % gesetzter Pfandartikel bleibt
  bei 7 %.
```

Funktion ans Modulende:

```python
def pfand_vorgaben(
    werte: dict,
    explizit: set[str],
    bisher: Optional[Product] = None,
) -> dict:
    """Pfandregel für Anlegen (bisher=None), Ändern und Import eines Produkts.

    - Kategorie PFAND heißt: das ist ein Pfandgebinde. Ohne ausdrückliche
      Angabe wird das Pfandkennzeichen gesetzt.
    - Wird ein Artikel zum Pfandartikel, gilt der Regelsatz 19 % — Pfand auf
      Mehrweggebinde ist kein Lebensmittelumsatz. Ein ausdrücklich
      mitgeschickter Satz bleibt unangetastet.
    - Beim Ändern zählt nur der Übergang. Ist der Artikel schon Pfand bzw.
      schon PFAND, wird nichts nachgezogen — sonst überschriebe jedes
      Speichern einen bewusst gewählten Satz.

    Gibt eine Kopie von `werte` zurück; `explizit` sind die Felder, die der
    Aufrufer ausdrücklich angegeben hat.
    """
    werte = dict(werte)
    wird_pfandkategorie = werte.get("category") == ProductCategory.PFAND and (
        bisher is None or bisher.category != ProductCategory.PFAND
    )
    if wird_pfandkategorie and "is_deposit" not in explizit:
        werte["is_deposit"] = True
    wird_pfand = bool(werte.get("is_deposit")) and (bisher is None or not bisher.is_deposit)
    if wird_pfand and "tax_rate" not in explizit:
        werte["tax_rate"] = TaxRate.STANDARD
    return werte
```

`ProductCategory` ist ein `str`-Enum; der Import liefert `"PFAND"` als String, auch der Vergleich mit `ProductCategory.PFAND` greift.

- [ ] **Step 4: `ProductUpdate.category`**

In `backend/app/schemas/product.py`:
- Zeile 8 `from pydantic import BaseModel, Field, ConfigDict` wird zu `from pydantic import BaseModel, Field, ConfigDict, field_validator`.
- In der Klasse `ProductUpdate` direkt nach `name` einfügen:

```python
    # Die Maske schickt die Kategorie bei jedem Speichern mit; ohne das Feld
    # verwarf der PATCH sie still.
    category: Optional[ProductCategory] = None
```

- Am Ende der Klasse `ProductUpdate`, nach `is_sellable`, einfügen:

```python

    @field_validator("category")
    @classmethod
    def _kategorie_nicht_leer(cls, v):
        # products.category ist NOT NULL. Ohne die Prüfung schriebe ein PATCH
        # mit "category": null NULL in die Spalte, und der Commit endete in
        # einem 500. Ein weggelassenes Feld erreicht den Validator nicht.
        if v is None:
            raise ValueError("Kategorie darf nicht leer sein")
        return v
```

- [ ] **Step 5: `products.py` — Anlegen und PATCH über dieselbe Funktion**

Nach Zeile 28 (`from app.services.product_service import ProductService`):

```python
from app.services.steuersatz import pfand_vorgaben
```

In `create_product` die Zeilen von `payload = data.model_dump()` bis einschließlich `payload["tax_rate"] = TaxRate.STANDARD` ersetzen durch:

```python
    # Pfandregel (PFAND → Pfandkennzeichen, Pfand → 19 %, ausdrückliche
    # Angaben bleiben) — dieselbe Funktion wie PATCH und Import.
    payload = pfand_vorgaben(data.model_dump(), data.model_fields_set)
```

In `update_product` direkt nach `update_data = data.model_dump(exclude_unset=True)`:

```python
    # Wird der Artikel hier zum Pfand (Kategorie PFAND oder Pfandkennzeichen),
    # gilt dieselbe Regel wie beim Anlegen — bisher blieb er auf 7 %.
    update_data = pfand_vorgaben(update_data, set(update_data), bisher=product)
```

- [ ] **Step 6: `_import_products` — leere Zelle ist keine Angabe**

In `backend/app/api/v1/imports.py` nach Zeile 33 (`from app.models.order import Order, OrderLine, OrderStatus`):

```python
from app.services.steuersatz import pfand_vorgaben
```

Die Schleife in `_import_products` (ab `for r in rows:` bis vor `db.commit()`) ersetzen:

```python
    for r in rows:
        existing = db.execute(select(Product).where(Product.sku == r["sku"])).scalar_one_or_none()
        # Nur eine befüllte Zelle ist eine Angabe. Eine leere Zelle oder
        # fehlende Spalte darf einen bestehenden Wert nie überschreiben — der
        # frühere Default tax_rate=REDUZIERT setzte jeden Pfandartikel bei
        # jedem Re-Import auf 7 % zurück (A3, 08.10.2026). category ist eine
        # Pflichtspalte; Zeilen ohne sie verwirft schon _parse_rows.
        angaben = {k: v for k, v in r.items() if v is not None}
        if "category" in angaben:
            angaben["category"] = ProductCategory(angaben["category"])
        if "tax_rate" in angaben:
            angaben["tax_rate"] = TaxRate(angaben["tax_rate"])
        # Dieselbe Pfandregel wie Anlegen und PATCH in der Produktmaske.
        angaben = pfand_vorgaben(angaben, set(angaben), bisher=existing)
        if existing:
            for k, v in angaben.items():
                setattr(existing, k, v)
            updated += 1
        else:
            angaben.setdefault("tax_rate", TaxRate.REDUZIERT)
            db.add(Product(**{**angaben, "base_unit_id": default_unit.id}))
            created += 1
```

Damit fällt der tote Fallback `ProductCategory.MICROGREEN` weg. `COLUMNS["products"]` und `_parse_rows` bleiben unverändert.

- [ ] **Step 7: Produktmaske — Kategorie PFAND schlägt 19 % vor**

Die Maske schickt bei jedem Speichern `tax_rate` mit. Die Backend-Regel greift dort also nie, die Maske muss den Satz selbst vorschlagen. Sie tut das schon beim Pfand-Häkchen (`Products.tsx` ~577-582). In `frontend/src/pages/Products.tsx` den `onChange` der Kategorie-Auswahl (Zeile 459) ersetzen:

```tsx
          onChange={(e) => {
            const category = e.target.value as ProductCategory;
            // Wie beim Pfand-Häkchen: Kategorie Pfand schlägt Pfandkennzeichen
            // und 19 % vor. Der Satz bleibt danach im Formular änderbar.
            setFormData(category === 'PFAND' && formData.category !== 'PFAND'
              ? { ...formData, category, is_deposit: true, tax_rate: 'STANDARD' }
              : { ...formData, category });
          }}
```

- [ ] **Step 8: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_pfand_rabatt.py tests/test_gernot_260821.py -v`
Erwartet: alle S1-Tests bis hier (26) grün, dazu `test_pfand_rabatt.py` und `test_gernot_260821.py` grün. Das betrifft insbesondere `test_explizite_werte_werden_nicht_ueberschrieben`, `test_expliziter_steuersatz_bleibt_erhalten`, `test_pfandkennzeichen_nachtraeglich_setzen` und `test_import_legt_pfandartikel_an`.

Run: `cd frontend && npm run build`
Erwartet: `tsc` und `vite build` ohne Fehler. Das läuft offline mit dem vorhandenen `node_modules`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/steuersatz.py backend/app/schemas/product.py \
        backend/app/api/v1/products.py backend/app/api/v1/imports.py \
        frontend/src/pages/Products.tsx backend/tests/test_gernot_261008.py
git commit -m "fix(produkte): Pfandregel auch bei Änderung und Import; leere Importzelle überschreibt nicht"
```

---

### Task 5: Shopify-Import nimmt den Produktsatz statt pauschal 19 %

**Files:**
- Modify: `backend/app/services/shopify_service.py:163` (neuer Helfer davor), `:217`
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces: `shopify_service._satz_aus_tax_lines(line_item: dict) -> Optional[TaxRate]`. Die Regel je Shopify-Position:
  1. Ist der Artikel über die SKU bekannt, gilt `product.tax_rate`.
  2. Sonst gilt der Satz aus `line_item["tax_lines"][*]["rate"]` (0.07 → REDUZIERT, 0.19 → STANDARD, 0 → STEUERFREI).
  3. Ohne solche Angabe gilt wie bisher `STANDARD`.

- [ ] **Step 1: Failing Tests anhängen**

Die Tests nutzen die `db`-Fixture aus `conftest.py`, keinen Client.

```python
class TestS1Shopify:
    """Task 5: Shopify-Import nimmt den Produktsatz statt pauschal 19 %."""

    def _bestellung(self, *positionen):
        return {
            "id": 9001, "name": "#9001", "currency": "EUR",
            "customer": {"first_name": "Eva", "last_name": "Shop", "email": "eva@example.com"},
            "line_items": list(positionen),
        }

    def _saetze(self, db):
        from app.models.order import Order
        order = db.query(Order).filter_by(customer_reference="#9001").one()
        return [l.tax_rate.value for l in sorted(order.lines, key=lambda l: l.position)]

    def test_bekannter_artikel_nimmt_den_produktsatz(self, db):
        from app.models.enums import TaxRate
        from app.services.shopify_service import import_shopify_order
        _s1_produkt_orm(db, "MG-ERBSE", "Erbsenkresse", TaxRate.REDUZIERT)

        import_shopify_order(db, self._bestellung(
            {"title": "Erbsenkresse", "sku": "MG-ERBSE", "quantity": 2, "price": "4.00"}))

        assert self._saetze(db) == ["REDUZIERT"]

    def test_unbekannter_artikel_nimmt_den_satz_aus_shopify(self, db):
        from app.services.shopify_service import import_shopify_order
        import_shopify_order(db, self._bestellung(
            {"title": "Kresse lose", "sku": None, "quantity": 1, "price": "3.00",
             "tax_lines": [{"rate": 0.07, "price": "0.21", "title": "MwSt"}]},
            {"title": "Tasse", "sku": None, "quantity": 1, "price": "9.00"}))

        # ohne tax_lines wie bisher 19 %
        assert self._saetze(db) == ["REDUZIERT", "STANDARD"]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1Shopify -v`
Erwartet: **2 failed.** Die Meldungen lauten `['STANDARD'] == ['REDUZIERT']` und `['STANDARD', 'STANDARD'] == ['REDUZIERT', 'STANDARD']`.

- [ ] **Step 3: Satz je Position**

In `backend/app/services/shopify_service.py` direkt vor `def import_shopify_order` einfügen:

```python
def _satz_aus_tax_lines(line_item: dict):
    """Steuersatz aus den tax_lines einer Shopify-Position (rate 0.07 → 7 %).

    None, wenn Shopify keinen oder einen unbekannten Satz liefert.
    """
    from app.models.enums import TaxRate

    for tl in line_item.get("tax_lines") or []:
        try:
            rate = Decimal(str(tl.get("rate")))
        except Exception:
            continue
        for satz in TaxRate:
            if satz.rate == rate:
                return satz
    return None
```

Im `OrderLine(...)` in `import_shopify_order` die Zeile `tax_rate=TaxRate.STANDARD,` ersetzen:

```python
            # Bekannter Artikel: Satz aus dem Produktstamm (Microgreens 7 %,
            # Pfand 19 %). Unbekannter: der Satz, den Shopify berechnet hat;
            # ohne Angabe wie bisher 19 % (A3, 08.10.2026).
            tax_rate=product.tax_rate if product else (_satz_aus_tax_lines(li) or TaxRate.STANDARD),
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_shopify.py -v`
Erwartet: alle grün. `test_import_creates_customer_and_order` prüft nur die Nettosumme, die sich nicht ändert.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/shopify_service.py backend/tests/test_gernot_261008.py
git commit -m "fix(shopify): Steuersatz aus dem Produkt statt pauschal 19 %"
```

---

### Task 6: Einmalige Datenkorrektur offener Bestellpositionen

**Wo die Korrektur läuft: `_auto_migrate` mit Marker, kein Skript.**
- Ein Skript müsste nach dem Deploy je Mandant per `docker exec -i` laufen. Der Containername wechselt bei jedem Coolify-Deploy. Der Codex-Worker kann den Schritt nicht ausführen und nicht prüfen. Ein vergessener Lauf ließe genau die Bestellungen falsch, die als Nächstes fakturiert werden.
- `_auto_migrate` läuft beim Start für jeden Mandanten, bevor Anfragen bedient werden.
- Ein Marker in `app_settings` (Key `DATENKORREKTUR_STEUERSATZ_261008`) macht die Korrektur einmalig. `app_settings` wird über `create_all` angelegt. Die Admin-Oberfläche listet nur `KNOWN_SETTINGS` (`admin.py:36-41`), der Marker taucht dort also nicht auf.
- Die Korrektur bekommt einen eigenen `try`-Block. Scheitert sie, laufen die Schema-Migrationen trotzdem. Ohne Marker wird sie beim nächsten Start erneut versucht.
- Jede geänderte Bestellung bekommt einen Audit-Log-Eintrag. Das Ergebnis (geänderte und übersprungene Bestellnummern) steht als JSON im Marker.
- Es gibt **keine Schemaänderung**; ein `_add_col_if_missing` ist nicht nötig.
- Zusätzlich bleibt `korrigiere_offene_bestellpositionen(db, nur_bestellungen=…)` gezielt aufrufbar. Diesen Weg braucht die Neuausstellung von RE-00002/4.
- **Der S1-Block bleibt der letzte Block in `_auto_migrate`** (siehe Einordnung). Spätere Spaltenmigrationen gehören in den ersten `try`.

**Was „offen“ heißt.** `create_invoice_from_order` setzt weder `orders.invoice_id` noch den Status `FAKTURIERT`; das ist am Code geprüft (`invoice_service.py:177-215`). Die Sammelrechnung hängt nur `delivery_notes.invoice_id` an (`invoices.py:637`). Der Bestellstatus allein reicht deshalb nicht. Eine Bestellung ist offen, wenn alle vier Bedingungen gelten:
- Status ist `ENTWURF`, `BESTAETIGT`, `IN_PRODUKTION` oder `GELIEFERT`;
- es gibt **keine** Rechnung mit `invoices.order_id = orders.id` und Status ≠ `STORNIERT`, auch keinen Entwurf;
- **kein** Lieferschein der Bestellung hat `invoice_id`;
- `orders.invoice_id` ist leer.

Abweichende Bestellungen mit Rechnung werden nur gemeldet (`uebersprungen_mit_rechnung`), nicht geändert.

**Gezielter Aufruf (`nur_bestellungen`).** Dieselben vier Bedingungen gelten. Der Statusfilter wirkt hier aber nicht still:
- Eine genannte Bestellung außerhalb der offenen Status kommt mit Nummer und Status nach `uebersprungen_status`, z. B. `"BE-20261001-0003 (FAKTURIERT)"`. Das betrifft `FAKTURIERT` (Übergang `GELIEFERT → FAKTURIERT`, `sales.py:1202`) und `STORNIERT`.
- Eine unbekannte ID kommt als `"<uuid> (nicht gefunden)"` dorthin.
- Beim automatischen Lauf ohne `nur_bestellungen` bleibt `uebersprungen_status` leer. Dort wäre jede fakturierte Bestellung ein Eintrag ohne Aussage.

**Files:**
- Create: `backend/app/services/steuersatz_korrektur.py`
- Modify: `backend/app/tenancy.py:357-358` (nach dem bestehenden `except` von `_auto_migrate`, vor `def _seed_minimal`)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `produkt_der_position` (Task 1), `app.api.v1.sales._calculate_line_amounts` / `_calculate_order_totals` (dieselben Rechenregeln wie beim Ändern einer Position), `AppSetting`, `OrderAuditLog`, `Invoice`, `DeliveryNote`.
- Produces:
  - `steuersatz_korrektur.MARKER = "DATENKORREKTUR_STEUERSATZ_261008"`
  - `steuersatz_korrektur.korrigiere_offene_bestellpositionen(db: Session, nur_bestellungen: Optional[Iterable[UUID]] = None) -> dict`. Die Funktion committet nicht. Die Schlüssel sind:
    - `bestellungen` (int) und `positionen` (int);
    - `geaendert` (Liste von Bestellnummern);
    - `uebersprungen_mit_rechnung` (Liste von Bestellnummern);
    - `uebersprungen_status` (Liste von Strings `"<Bestellnummer> (<Status>)"` bzw. `"<uuid> (nicht gefunden)"`). Diese Liste ist nur bei `nur_bestellungen` befüllt.
  - `steuersatz_korrektur.korrektur_einmalig_ausfuehren(db: Session) -> Optional[dict]`. Sie liefert `None`, wenn der Marker schon steht, und committet nicht.
  - Audit-Log-Aktion `STEUERSATZ_KORREKTUR` (`user_name="Datenkorrektur"`). `old_values`/`new_values` enthalten `positionen` (Liste mit `position`, `tax_rate`, `line_vat`, `line_gross`), `total_vat` und `total_gross` als Strings.
  - **Für die Neuausstellung von RE-00002/4 (Runbook R4b):** zuerst die Rechnung stornieren, dann `korrigiere_offene_bestellpositionen(db, nur_bestellungen=[order_id])` mit Commit aufrufen. Ist `uebersprungen_mit_rechnung` oder `uebersprungen_status` nicht leer: STOP. Sonst steht die Bestellnummer unter `geaendert`, sofern die Bestellung noch Positionen mit 7 % trug (RE-00004: die Pfandkiste). Erst danach `create_invoice_from_order(order_id)` aufrufen.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS1Datenkorrektur:
    """Task 6: einmalige Korrektur offener Bestellpositionen."""

    def _lauf(self, **kw):
        from app.services.steuersatz_korrektur import korrigiere_offene_bestellpositionen
        with TestingSessionLocal() as db:
            ergebnis = korrigiere_offene_bestellpositionen(db, **kw)
            db.commit()
            return ergebnis

    def test_offene_bestellung_wird_auf_den_produktsatz_korrigiert(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        # 31,00 € × 7 % = 2,17 € — der falsche Stand
        assert Decimal(str(order["total_vat"])) == Decimal("2.17")

        ergebnis = self._lauf()

        assert ergebnis["bestellungen"] == 1 and ergebnis["positionen"] == 1
        nachher = client.get(f"/api/v1/sales/orders/{order['id']}").json()
        assert {bool(z["product_id"]): z["tax_rate"] for z in nachher["lines"]} == {
            True: "STANDARD", False: "REDUZIERT",
        }
        pfandzeile = _s1_pfandzeile(client, order["id"])
        assert Decimal(str(pfandzeile["line_vat"])) == Decimal("1.14")
        assert Decimal(str(pfandzeile["line_gross"])) == Decimal("7.14")
        # 25,00 € × 7 % = 1,75 € | 6,00 € × 19 % = 1,14 €
        assert Decimal(str(nachher["total_vat"])) == Decimal("2.89")
        assert Decimal(str(nachher["total_gross"])) == Decimal("33.89")

    def test_korrektur_steht_im_audit_log(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)

        self._lauf()

        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        eintrag = next(e for e in log if e["action"] == "STEUERSATZ_KORREKTUR")
        assert eintrag["old_values"]["positionen"][0]["tax_rate"] == "REDUZIERT"
        assert eintrag["new_values"]["positionen"][0]["tax_rate"] == "STANDARD"
        assert Decimal(eintrag["old_values"]["total_gross"]) == Decimal("33.17")
        assert Decimal(eintrag["new_values"]["total_gross"]) == Decimal("33.89")

    def test_zweiter_lauf_aendert_nichts(self, client):
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        self._lauf()

        zweiter = self._lauf()

        assert zweiter["bestellungen"] == 0
        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        assert sum(1 for e in log if e["action"] == "STEUERSATZ_KORREKTUR") == 1

    def test_bestellung_mit_rechnung_wird_nicht_angefasst(self, client):
        """Auch ein Rechnungsentwurf (RE-00003) sperrt: Rechnungen fasst die
        Korrektur nie an, und die Bestellung soll nicht von ihr abweichen."""
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        rechnung = _s1_rechnung_aus(client, order)
        rechnungszeilen = _s1_rechnungszeilen(rechnung["id"])

        ergebnis = self._lauf()

        assert ergebnis["bestellungen"] == 0
        assert ergebnis["uebersprungen_mit_rechnung"] == [order["order_number"]]
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"
        assert _s1_rechnungszeilen(rechnung["id"]) == rechnungszeilen

    def test_bestellung_in_sammelrechnung_wird_nicht_angefasst(self, client):
        pfand = _s1_pfandkiste(client)
        kunde = _s1_kunde(client)
        order = _s1_altbestellung(client, kunde, pfand, liefertag="2026-09-15")
        assert client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={}).status_code == 201
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": "2026-09-01", "period_to": "2026-09-30", "customer_ids": [kunde["id"]],
        })
        assert r.status_code == 201, r.text

        ergebnis = self._lauf()

        assert ergebnis["bestellungen"] == 0
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"

    def test_stornierte_bestellung_bleibt(self, client):
        from app.models.enums import OrderStatus
        from app.models.order import Order
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(order["id"])).status = OrderStatus.STORNIERT
            db.commit()

        assert self._lauf()["bestellungen"] == 0
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"

    def test_nach_storno_der_rechnung_gezielt_korrigierbar(self, client):
        """Für die Neuausstellung von RE-00002/4: erst stornieren, dann die
        Bestellung gezielt korrigieren, dann neu fakturieren."""
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        rechnung = _s1_rechnung_aus(client, order)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={"reason": "Steuersatz Pfand"})
        assert r.status_code == 200, r.text

        ergebnis = self._lauf(nur_bestellungen=[uuid.UUID(order["id"])])

        assert ergebnis["bestellungen"] == 1
        assert ergebnis["geaendert"] == [order["order_number"]]
        # Die Stornorechnung sperrt nicht: beide Listen leer, wie das Runbook es verlangt
        assert ergebnis["uebersprungen_mit_rechnung"] == []
        assert ergebnis["uebersprungen_status"] == []
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "STANDARD"

    def test_gezielter_aufruf_meldet_nicht_offene_und_unbekannte_bestellungen(self, client):
        """nur_bestellungen filtert nach Status — eine fakturierte Bestellung
        oder eine unbekannte ID darf nicht still durchrutschen. Sonst hielte
        das Runbook ein leeres Ergebnis für Erfolg."""
        from app.models.enums import OrderStatus
        from app.models.order import Order
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        with TestingSessionLocal() as db:
            db.get(Order, uuid.UUID(order["id"])).status = OrderStatus.FAKTURIERT
            db.commit()
        unbekannt = uuid.uuid4()

        ergebnis = self._lauf(nur_bestellungen=[uuid.UUID(order["id"]), unbekannt])

        assert ergebnis["bestellungen"] == 0
        assert ergebnis["uebersprungen_status"] == [
            f"{order['order_number']} (FAKTURIERT)",
            f"{unbekannt} (nicht gefunden)",
        ]
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"
        # Der automatische Lauf meldet fakturierte Bestellungen nicht.
        assert self._lauf()["uebersprungen_status"] == []

    def test_laeuft_je_mandant_nur_einmal(self, client):
        from app.models.app_setting import AppSetting
        from app.services.steuersatz_korrektur import MARKER, korrektur_einmalig_ausfuehren
        pfand = _s1_pfandkiste(client)
        order = _s1_altbestellung(client, _s1_kunde(client), pfand)
        with TestingSessionLocal() as db:
            erstes = korrektur_einmalig_ausfuehren(db)
            db.commit()
        assert erstes["bestellungen"] == 1

        _s1_altstand(order["id"])  # dieselbe Abweichung taucht wieder auf
        with TestingSessionLocal() as db:
            zweites = korrektur_einmalig_ausfuehren(db)
            db.commit()
            assert db.get(AppSetting, MARKER) is not None

        assert zweites is None
        assert _s1_pfandzeile(client, order["id"])["tax_rate"] == "REDUZIERT"

    def test_auto_migrate_fuehrt_die_korrektur_aus(self):
        """Verdrahtung in tenancy._auto_migrate — auf einer eigenen In-Memory-
        Engine, die geteilte Test-Engine bleibt unberührt."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import StaticPool
        from app.database import Base
        from app.models.app_setting import AppSetting
        from app.services.steuersatz_korrektur import MARKER
        from app.tenancy import _auto_migrate

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        try:
            _auto_migrate(engine)
            with Session(engine) as s:
                assert s.get(AppSetting, MARKER) is not None
        finally:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    def test_gescheiterte_korrektur_blockiert_keine_schemamigration(self, monkeypatch, caplog):
        """Scheitert die Korrektur, laufen die Spaltenmigrationen trotzdem, es
        steht kein Marker, und _auto_migrate wirft nicht — beim nächsten Start
        wird sie erneut versucht. Stünde der Block am Anfang des ersten try,
        fehlte die Spalte; stünde er in dessen except-Zweig, fehlte die
        eigene Fehlermeldung."""
        import logging
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.orm import Session
        from sqlalchemy.pool import StaticPool
        from app.database import Base
        from app.models.app_setting import AppSetting
        from app.services.steuersatz_korrektur import MARKER
        from app.tenancy import _auto_migrate

        def scheitert(db, nur_bestellungen=None):
            raise RuntimeError("Korrektur gescheitert (Test)")

        monkeypatch.setattr(
            "app.services.steuersatz_korrektur.korrigiere_offene_bestellpositionen", scheitert)

        engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                               poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        try:
            # Älteres Schema: eine Spalte fehlt, die _auto_migrate nachträgt.
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE invoices DROP COLUMN service_period_end"))

            with caplog.at_level(logging.ERROR, logger="app.tenancy"):
                _auto_migrate(engine)  # wirft nicht

            spalten = {c["name"] for c in inspect(engine).get_columns("invoices")}
            assert "service_period_end" in spalten
            with Session(engine) as s:
                assert s.get(AppSetting, MARKER) is None
            assert "Steuersatz-Korrektur fehlgeschlagen" in caplog.text
        finally:
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS1Datenkorrektur -v`
Erwartet: **11 failed** mit `ModuleNotFoundError: No module named 'app.services.steuersatz_korrektur'`.

- [ ] **Step 3: Modul `backend/app/services/steuersatz_korrektur.py` anlegen**

```python
"""Einmalige Datenkorrektur: Steuersatz offener Bestellpositionen (A3, 08.10.2026).

Bis zu diesem Release setzte das Bestellformular jede Position fest auf 7 %.
Offene Bestellungen tragen deshalb für Pfandkisten (Produktstamm 19 %) den
falschen Satz — und mit ihm falsche line_vat/line_gross und Bestellsummen.

Korrigiert werden nur Positionen mit Produkt (direkt oder über die Variante),
deren Satz vom Produktstamm abweicht, und nur in Bestellungen, die noch nicht
abgerechnet sind:
- Status ENTWURF, BESTAETIGT, IN_PRODUKTION oder GELIEFERT,
- keine nicht-stornierte Rechnung mit dieser order_id (auch kein Entwurf),
- kein Lieferschein der Bestellung steckt in einer Sammelrechnung,
- orders.invoice_id ist leer.
Rechnungen werden nie angefasst: ihr PDF wird bei jedem Abruf aus der
Datenbank erzeugt, eine Änderung schriebe versendete Belege um (GoBD).

Jede geänderte Bestellung bekommt einen Audit-Log-Eintrag
STEUERSATZ_KORREKTUR mit altem und neuem Stand.

`korrektur_einmalig_ausfuehren` läuft aus tenancy._auto_migrate und setzt
danach einen Marker in app_settings, damit die Korrektur je Mandant genau
einmal läuft. `korrigiere_offene_bestellpositionen` ist zusätzlich gezielt
aufrufbar (nur_bestellungen), z. B. nach dem Storno einer betroffenen
Rechnung, bevor die Bestellung neu fakturiert wird.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.documents import DeliveryNote
from app.models.enums import InvoiceStatus, OrderStatus
from app.models.invoice import Invoice
from app.models.order import Order, OrderAuditLog
from app.services.steuersatz import produkt_der_position

logger = logging.getLogger(__name__)

MARKER = "DATENKORREKTUR_STEUERSATZ_261008"

OFFENE_STATUS = (
    OrderStatus.ENTWURF,
    OrderStatus.BESTAETIGT,
    OrderStatus.IN_PRODUKTION,
    OrderStatus.GELIEFERT,
)

GRUND = (
    "Datenkorrektur 08.10.2026: Steuersatz aus dem Produktstamm übernommen "
    "(Bestellformular hatte fest 7 % gesetzt)"
)


def korrigiere_offene_bestellpositionen(
    db: Session,
    nur_bestellungen: Optional[Iterable[UUID]] = None,
) -> dict:
    """Gleicht den Satz offener Produktpositionen an den Produktstamm an.

    Idempotent: ein zweiter Lauf findet nichts mehr. Committet nicht.

    Mit nur_bestellungen werden genau diese Bestellungen geprüft. Nicht
    offene (z. B. FAKTURIERT) und unbekannte IDs landen in
    uebersprungen_status, statt still herausgefiltert zu werden — der
    Aufrufer muss sehen, dass nichts geändert wurde.
    """
    # Späte Imports: die Rechenregeln der Bestell-API sind die einzige
    # Wahrheit für line_vat/line_gross und die Bestellsummen — dieselben
    # Funktionen wie beim Ändern einer Position über die Oberfläche.
    from app.api.v1.sales import _calculate_line_amounts, _calculate_order_totals

    mit_rechnung = set(db.execute(
        select(Invoice.order_id).where(
            Invoice.order_id.is_not(None),
            Invoice.status != InvoiceStatus.STORNIERT,
        )
    ).scalars())
    in_sammelrechnung = set(db.execute(
        select(DeliveryNote.order_id).where(DeliveryNote.invoice_id.is_not(None))
    ).scalars())

    gesucht = list(nur_bestellungen) if nur_bestellungen is not None else None
    abfrage = select(Order).order_by(Order.order_number)
    if gesucht is None:
        abfrage = abfrage.where(Order.status.in_(OFFENE_STATUS))
    else:
        # Gezielt: auch nicht offene laden, damit sie gemeldet werden können.
        abfrage = abfrage.where(Order.id.in_(gesucht))
    bestellungen = db.execute(abfrage).scalars().all()

    ergebnis = {
        "bestellungen": 0,
        "positionen": 0,
        "geaendert": [],
        "uebersprungen_mit_rechnung": [],
        "uebersprungen_status": [],
    }

    for order in bestellungen:
        if order.status not in OFFENE_STATUS:
            # Nur beim gezielten Aufruf erreichbar.
            ergebnis["uebersprungen_status"].append(f"{order.order_number} ({order.status.value})")
            continue
        abweichend = []
        for line in order.lines:
            produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
            if produkt is not None and produkt.tax_rate is not None and line.tax_rate != produkt.tax_rate:
                abweichend.append((line, produkt.tax_rate))
        if not abweichend:
            continue

        if order.id in mit_rechnung or order.id in in_sammelrechnung or order.invoice_id is not None:
            ergebnis["uebersprungen_mit_rechnung"].append(order.order_number)
            continue

        vorher = {"total_vat": str(order.total_vat), "total_gross": str(order.total_gross), "positionen": []}
        nachher = {"positionen": []}
        for line, satz in abweichend:
            vorher["positionen"].append({
                "position": line.position, "tax_rate": line.tax_rate.value,
                "line_vat": str(line.line_vat), "line_gross": str(line.line_gross),
            })
            line.tax_rate = satz
            _calculate_line_amounts(line)
            nachher["positionen"].append({
                "position": line.position, "tax_rate": line.tax_rate.value,
                "line_vat": str(line.line_vat), "line_gross": str(line.line_gross),
            })
        _calculate_order_totals(order)
        nachher["total_vat"] = str(order.total_vat)
        nachher["total_gross"] = str(order.total_gross)

        db.add(OrderAuditLog(
            order_id=order.id,
            user_id=None,
            user_name="Datenkorrektur",
            action="STEUERSATZ_KORREKTUR",
            old_values=vorher,
            new_values=nachher,
            reason=GRUND,
        ))
        ergebnis["bestellungen"] += 1
        ergebnis["positionen"] += len(abweichend)
        ergebnis["geaendert"].append(order.order_number)
        logger.info(
            "[steuersatz-korrektur] %s: %d Position(en), brutto %s → %s",
            order.order_number, len(abweichend), vorher["total_gross"], nachher["total_gross"],
        )

    if gesucht is not None:
        gefunden = {o.id for o in bestellungen}
        ergebnis["uebersprungen_status"] += [
            f"{oid} (nicht gefunden)" for oid in gesucht if oid not in gefunden
        ]

    db.flush()
    return ergebnis


def korrektur_einmalig_ausfuehren(db: Session) -> Optional[dict]:
    """Führt die Korrektur aus, falls der Marker noch fehlt. Committet nicht.

    Gibt None zurück, wenn sie in diesem Mandanten schon gelaufen ist.
    """
    if db.get(AppSetting, MARKER) is not None:
        return None
    ergebnis = korrigiere_offene_bestellpositionen(db)
    db.add(AppSetting(key=MARKER, value=json.dumps({
        "ausgefuehrt_am": datetime.now(timezone.utc).isoformat(),
        **ergebnis,
    })))
    db.flush()
    logger.info("[steuersatz-korrektur] einmalig ausgeführt: %s", ergebnis)
    return ergebnis
```

- [ ] **Step 4: Aufruf in `_auto_migrate`**

In `backend/app/tenancy.py` direkt **nach** dem bestehenden Block `except Exception as e: logger.error(f"[auto-migrate] failed: {e}")` (Zeile 357-358) und vor `def _seed_minimal` einfügen. Die Einrückung liegt auf Funktionsebene, nicht im bestehenden `try`.

```python

    # Einmalige Datenkorrektur (A3, 08.10.2026): Steuersatz offener
    # Bestellpositionen an den Produktstamm angleichen. Eigener try-Block —
    # scheitert sie, laufen die Schema-Migrationen trotzdem, und ohne Marker
    # wird sie beim nächsten Start erneut versucht.
    try:
        from sqlalchemy.orm import Session as _Session
        from app.services.steuersatz_korrektur import korrektur_einmalig_ausfuehren
        if inspector.has_table("order_lines") and inspector.has_table("app_settings"):
            with _Session(engine) as session:
                korrektur_einmalig_ausfuehren(session)
                session.commit()
    except Exception as e:
        logger.error(f"[auto-migrate] Steuersatz-Korrektur fehlgeschlagen: {e}")
```

`inspector` und `engine` sind die Namen, die `_auto_migrate` schon verwendet (Zeile 268 und Parameter).

**Dieser Block bleibt der letzte in `_auto_migrate`.** Er liest Bestellungen, Rechnungen, Lieferscheine und Produkte über das ORM und braucht deshalb das fertig migrierte Schema. Neue `_add_col_if_missing`-Aufrufe (auch aus anderen Abschnitten, z. B. Task 26) gehören in den ersten `try`, vor `from sqlalchemy.orm import Session`. `test_gescheiterte_korrektur_blockiert_keine_schemamigration` prüft die Lage: Der Block steht hinter den Spaltenmigrationen und hat seinen eigenen `try`.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v`
Erwartet: alle 39 S1-Tests passed, dazu die Tests anderer Abschnitte, falls schon vorhanden.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/steuersatz_korrektur.py backend/app/tenancy.py backend/tests/test_gernot_261008.py
git commit -m "fix(steuer): einmalige Korrektur des Steuersatzes offener Bestellpositionen"
```

---

### Task 7: Bestellformular schickt keinen festen Steuersatz mehr; Abschlussprüfung

**Files:**
- Modify: `frontend/src/components/domain/CreateOrderModal.tsx:177`

**Interfaces:**
- Consumes: Backend aus Task 1. Ohne `tax_rate` setzt der Server den Produktsatz. `salesApi.createOrder` (`services/api.ts:355-371`) typisiert `tax_rate` schon als optional; der Typ bleibt unverändert.

- [ ] **Step 1: Festen Satz entfernen**

In `frontend/src/components/domain/CreateOrderModal.tsx`, in `orderLines` (Zeilen 166-182), die Zeile `tax_rate: 'REDUZIERT' as const, // Food products use reduced tax rate (7%)` ersetzen durch:

```tsx
                // Kein tax_rate: bei Produkten setzt der Server den Satz aus dem
                // Produktstamm (Pfand 19 %, Microgreens 7 %). Der feste Wert
                // 'REDUZIERT' hat Pfandkisten mit 7 % fakturiert (A3, 08.10.2026).
```

Das Formular bietet je Position nur die Produktauswahl (Combobox, `:378-383`); `product_name` wird nur aus der Auswahl gesetzt (`:236`, `:258`). Freitextpositionen ohne Produkt entstehen praktisch nur über die API und behalten dort den Satz vom Client bzw. 7 %.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Erwartet: `tsc` und `vite build` ohne Fehler.

- [ ] **Step 3: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` ohne Ausgabe.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/domain/CreateOrderModal.tsx
git commit -m "fix(bestellung): Formular schickt keinen festen Steuersatz mehr"
```

---

## Abschnitt S2: Rechnungs-PDF weist Entgelt und Steuer je Satz aus, Rundung einheitlich — Tasks 8–11

**Einordnung:** S2 läuft nach S1, hängt technisch aber nicht daran. Die S2-Tests verwenden nur Rechnungspositionen **ohne** `product_id` mit ausdrücklichem Satz; dafür gilt laut `tests/test_gernot_260821.py:486-504` und `tests/test_pfand_rabatt.py:49-75` der Satz vom Client.
- **Task 8** liefert die eine Rechenregel `steuer_je_satz` für Summen, PDF und DATEV. S4 setzt hart darauf (Task 16, Step 0). Nach S2 ergeben `Σ (base + tax)` aller Sätze für jede neu berechnete Rechnung exakt `invoice.total`; Ausnahme sind Altrechnungen mit 1-ct-Abweichung (Runbook L2). Die Schlüssel `rate`, `percent`, `base` und `tax` von `get_tax_summary()` bleiben, neu sind `netto_vor_rabatt` und `rabatt`, und die Liste ist aufsteigend nach Satz sortiert.
- **Task 9** behebt die Ursache „`invoice.lines` ist nach `add_line` veraltet" zentral in `InvoiceService.add_line` über die neue Hilfsfunktion `InvoiceService.recalculate_totals`. In den Einzelabschnitten war das doppelt geplant (S2: Nachrechnen nur in `POST /invoices`; S3: `add_line`). Es repariert `POST /invoices` mit Positionen, den Storno-Pfad, den Abo-Task und die Baseline-Altlast `test_services.py::TestInvoiceService::test_invoice_totals_update`. Task 12 (Stornorechnung) und Task 25 (Entwurfsposition ändern/löschen) rufen die Hilfsfunktion auf.
- **Task 10** importiert `Decimal` in `pdf_service.py` und behebt damit den `NameError` jedes Sammelrechnungs-PDFs; Task 21 setzt darauf auf.
- **Task 11** setzt in `send_invoice_email` den Block `if invoice.status == InvoiceStatus.ENTWURF: invoice.calculate_totals()`. Task 13 ändert dieselbe Funktion an zwei anderen Stellen und lässt diesen Block stehen.
- Die Neuausstellungen von RE-2026-00002/4 (Runbook) tragen bereits das PDF mit Steuer je Satz.

### Verifizierter Ausgangsbefund (S2)

Alle Punkte wurden am 08.10.2026 gegen eine unveränderte Kopie von `c4a1832` geprüft (In-Memory-Test-DB, keine Produktionsdaten).

1. **PDF ohne Steuer je Satz.** `PDFService.generate_invoice_pdf` (`backend/app/services/pdf_service.py:271-298`) hat 7 Spalten, keine davon für den Steuersatz. Der Summenblock (`:300-335`) druckt eine einzige Zeile `["USt:", invoice.tax_amount]`. Bei 7 % Ware und 19 % Pfand fehlen damit die Pflichtangaben nach § 14 Abs. 4 Nr. 8 UStG.
2. **Zwei Rundungen.** `Invoice.calculate_totals` (`backend/app/models/invoice.py:132-172`) rundet die Steuer einmal über alle Sätze, `Invoice.get_tax_summary` (`:193-223`) rundet je Satz. Gemessen für 1 × 2,50 € zu 7 % plus 1 × 4,50 € zu 19 %:
   - `tax_amount` = 1,03 €,
   - `get_tax_summary()` = 0,18 € + 0,86 € = 1,04 €.
3. **`POST /invoices` mit `lines` zählt nur die erste Position.** `create_invoice` (`backend/app/api/v1/invoices.py:106-127`) ruft je Zeile `service.add_line`. Ab der zweiten Zeile sieht `invoice.calculate_totals()` eine veraltete `invoice.lines`-Liste. Gemessen mit 10,00 € zu 7 % plus 5,00 € zu 19 %: `subtotal` 10,00 €, `tax_amount` 0,70 €, `total` 10,70 €, obwohl das PDF beide Positionen zeigt.
   - Die Oberfläche ist nicht betroffen: `invoicesApi.create` in `frontend/src/services/api.ts:710-730` kennt kein `lines`, und `Invoices.tsx:680` legt die Positionen einzeln an.
   - Dieselbe Ursache steckt im Storno und in `tasks/invoice_tasks.py:252-265` (Abo-Rechnung, wird laut Spec ohnehin entfernt). Task 9 behebt sie zentral in `add_line`.
   - Auch die Baseline-Altlast `test_services.py::TestInvoiceService::test_invoice_totals_update` scheitert genau daran: Sie erwartet nach zwei `add_line` in derselben Session 200,00 € und bekommt 100,00 €.
4. **Rabattbetrag bleibt stehen.** `calculate_totals` setzt `discount_amount` nur bei `discount_percent > 0`. Wird der Rabatt per PATCH auf 0 gesetzt, bleibt der alte Betrag stehen (gemessen: 0,70 €). Das PDF druckt dann weiter „Zwischensumme“ und „Rabatt“ (`pdf_service.py:305-314`).
5. **Sammelrechnungs-PDF stürzt ab.** `pdf_service.py:389` nutzt `Decimal("0")`, aber das Modul importiert `Decimal` nicht. Jede Sammelrechnung mit Lieferscheinen endet beim PDF-Abruf mit `NameError: name 'Decimal' is not defined`. S2 braucht den Import ohnehin und behebt das nebenbei; ein Regressionstest sichert es ab.
6. **Wer `calculate_totals` aufruft, ist geprüft.** Die Methode läuft nur für Entwürfe oder neu entstehende Belege:
   - `add_line`, das nur für `ENTWURF` erlaubt ist,
   - `update_invoice`, `update_invoice_line` und `delete_invoice_line`, jeweils nur für `ENTWURF`,
   - `finalize_invoice`, das von `ENTWURF` startet,
   - `create_invoice_from_order`, `batch_run_commit` und der Storno-Beleg, die alle neu sind,
   - nach Task 11 zusätzlich `send_invoice_email` (`POST /invoices/{id}/send`), und zwar **nur** für `ENTWURF`.

   Kein Abruf (`GET /pdf`, `/send` einer bereits ausgestellten Rechnung, DATEV) rechnet die Summen einer versendeten Rechnung neu. Die Änderung der Rechenregel schreibt also **keine** festgeschriebene Rechnung um (GoBD).
7. **„Mailen“ stellt einen Entwurf aus, ohne die Summen neu zu berechnen.** `send_invoice_email` (`backend/app/api/v1/invoices.py:223-275`) erzeugt das PDF aus den gespeicherten Summen und setzt danach `ENTWURF` direkt auf `OFFEN` (`:271-272`). `calculate_totals()` ruft es nicht auf, anders als `InvoiceService.finalize_invoice` (`backend/app/services/invoice_service.py:232-233`). Die Oberfläche bietet „Mailen“ für jeden Status außer `STORNIERT` an, also auch für Entwürfe (`frontend/src/components/domain/OrderDocumentsModal.tsx:317-331`, Aufruf `invoicesApi.sendInvoiceEmail`). Nach Tasks 8–10 allein gilt deshalb (in einer Kopie nachgestellt): Ein Entwurf mit 2,50 € zu 7 % und 4,50 € zu 19 %, dessen Summen noch mit der alten Rundung gespeichert sind (1,03 / 8,03), geht per „Mailen“ mit `USt: 1.03 €` und `8.03 €` hinaus, ohne Zeile je Satz. Danach steht er auf `OFFEN` mit `tax_amount` 1,03. Task 11 behebt das.

### Die eine Rechenregel (gilt für Summen, PDF und DATEV)

Je Steuersatz `r`:
1. `netto_vor_rabatt_r` = Σ `line.line_total`. Die Zeilenbeträge sind bereits auf den Cent gerundet.
2. `rabatt_r` = `round_half_up(netto_vor_rabatt_r × discount_percent / 100, 2)`
3. `base_r` = `netto_vor_rabatt_r − rabatt_r`. Das ist das Entgelt je Satz, wie es auf dem Beleg steht.
4. `tax_r` = `round_half_up(base_r × Satz, 2)`

Rechnungssummen: `discount_amount` = Σ `rabatt_r`, `subtotal` = Σ `base_r`, `tax_amount` = Σ `tax_r`, `total` = `subtotal + tax_amount`.

Abweichung zu heute:
- **Ein Satz ohne Rabatt:** identisch.
- **Ein Satz mit Rabatt:** `discount_amount` und `subtotal` bleiben identisch. Die Steuer wird auf das gerundete statt auf das ungerundete Entgelt gerechnet; das weicht höchstens 1 ct ab, und nur an Rundungsgrenzen.
- **Mehrere Sätze:** Die Steuer wird je Satz gerundet, der Rabatt ebenfalls je Satz.

Entgelt und Steuer je Satz lassen sich aus den gedruckten Positionen nachrechnen. Dazu die Positionsbeträge mit gleichem Eintrag in der Spalte „MwSt“ summieren, den Rabatt je Satz abziehen und den Satz anwenden. Der gedruckte **Gesamtrabatt** ist dagegen die Summe der je Satz gerundeten Rabatte. Er kann daher um 1 ct von „Zwischensumme × Rabattsatz“ abweichen. Beispiel: 0,25 € zu 7 % und 0,25 € zu 19 % mit 10 % Rabatt ergeben 0,03 € + 0,03 € = 0,06 €, gerechnet aus der Zwischensumme wären es 0,05 €. Bei mehr als einem Satz lässt sich die Zeile „Rabatt“ also nur über die Positionssummen je Satz nachrechnen (siehe Offene Punkte, 1).

Zur Kenntnis, nicht in S2 geändert: Die Bestellung (`vat_from_lines`, `backend/app/models/order.py:21-41`) rechnet die Steuer auf `Basis × (1 − Rabatt)` ohne Zwischenrundung. Auftragsbestätigung und Rechnung können deshalb bei Rechnungsrabatt in seltenen Fällen 1 ct auseinanderliegen.

### Review Focus (S2)

1. **Kein Abruf schreibt.** `get_tax_summary()` ruft nicht mehr `line.calculate_line_total()` auf, sondern liest den gespeicherten `line_total`. Getestet in `TestS2KeinAbrufSchreibt::test_get_tax_summary_liest_gespeicherte_zeilenbetraege` (Task 8). Der Test setzt einen gespeicherten Zeilenbetrag abweichend von Menge × Preis und prüft, dass `get_tax_summary()` genau diesen Wert liefert und `db.dirty` leer bleibt. `GET /pdf` committet nie, daher würde ein Test über den PDF-Abruf ein Zurückschreiben nicht bemerken.
2. **Altrechnungen zeigen beim erneuten Abruf ihre festgeschriebenen Beträge.** Ergibt die Aufteilung je Satz nicht exakt `subtotal` und `tax_amount`, druckt das PDF wie bisher eine Zeile „USt:“. Getestet in Task 10 (Abruf) und Task 11 (erneutes Mailen).
3. **Für jede neu berechnete Rechnung gilt Σ Steuer je Satz = `tax_amount` und Σ Entgelt je Satz = `subtotal`.** Getestet in Task 8, auch mit Rechnungsrabatt.
4. **Festgeschriebenes Verhalten bleibt.** S2 ändert nicht, **welcher** Satz eine Position bekommt. Die Tests `test_pfand_rabatt.py:39-47` und `:49-75` sowie `test_gernot_260821.py:486-504` und `:705-708` bleiben unverändert grün.
5. **Mailen stellt aus wie Finalisieren.** `POST /invoices/{id}/send` rechnet einen `ENTWURF` vor dem PDF neu, eine bereits ausgestellte Rechnung nie. Getestet in Task 11.

---

### Task 8: Eine Rechenregel für Summen und Steuer je Satz

**Files:**
- Modify: `backend/app/models/invoice.py`
  - drei neue Modulfunktionen vor `class Invoice(Base):` (Zeile 21): `_cent`, `steuer_je_satz`, `steuerausweis_stimmt`
  - `Invoice.calculate_totals` ersetzen (`:132-172`)
  - `Invoice.get_tax_summary` ersetzen (`:193-223`)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces:
  - `app.models.invoice.steuer_je_satz(lines, discount_percent) -> list[dict]`. Jedes Dict hat die Schlüssel `rate` (`TaxRate`), `percent` (`int`), `netto_vor_rabatt`, `rabatt`, `base` und `tax` (alle `Decimal` mit 2 Stellen). Die Liste ist aufsteigend nach `percent` sortiert. Die Funktion ist rein: Sie liest nur `line.tax_rate` und `line.line_total` und verändert nichts.
  - `app.models.invoice.steuerausweis_stimmt(invoice) -> bool`: True, wenn Σ `base` == `invoice.subtotal` und Σ `tax` == `invoice.tax_amount`. Task 10 nutzt sie.
  - `Invoice.get_tax_summary()` liefert `steuer_je_satz(self.lines, self.discount_percent)`. Die bisherigen Schlüssel bleiben (Vertrag mit DATEV).
  - Testhelfer `S2_ZEILEN`, `_s2_kunde`, `_s2_rechnung_zeilenweise` und `_s2_steuerblock` in `test_gernot_261008.py`. Task 9, Task 10 und Task 11 verwenden sie wieder.

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_gernot_261008.py` anhängen (Kopf aus Task 1):

```python
# ===========================================================================
# S2 — Rechnungs-PDF weist Steuer je Satz aus, Rundung einheitlich
# Helfer und Klassen tragen das Präfix _s2_/TestS2, weil sich mehrere
# Abschnitte diese Datei teilen: ein gleichnamiger Helfer oder eine
# gleichnamige Klasse aus einem anderen Abschnitt würde still ersetzt.
# ===========================================================================

#: Gernots Fall im Kleinen: Ware zu 7 %, Pfandkiste zu 19 %.
#: 2,50 × 7 % = 0,175 → 0,18 | 4,50 × 19 % = 0,855 → 0,86 | zusammen 1,04.
#: Einmal über alle Sätze gerundet ergab das 1,03 — 1 ct neben dem Steuerblock.
S2_ZEILEN = [
    {"description": "Erbsen-Schale", "quantity": 1, "unit": "STK",
     "unit_price": 2.50, "tax_rate": "REDUZIERT"},
    {"description": "Pfandkiste IFCO", "quantity": 1, "unit": "STK",
     "unit_price": 4.50, "tax_rate": "STANDARD"},
]


def _s2_kunde(client):
    r = client.post("/api/v1/sales/customers", json={"name": "Oekoring Test", "typ": "HANDEL"})
    assert r.status_code == 201, r.text
    return r.json()


def _s2_rechnung_zeilenweise(client, zeilen=S2_ZEILEN, **kopf):
    """Anlage wie in der Oberfläche: Kopf, dann jede Position einzeln."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": _s2_kunde(client)["id"],
        "invoice_date": date.today().isoformat(),
        **kopf,
    })
    assert r.status_code == 201, r.text
    rechnung = r.json()
    for zeile in zeilen:
        z = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=zeile)
        assert z.status_code == 201, z.text
    return client.get(f"/api/v1/invoices/{rechnung['id']}").json()


def _s2_steuerblock(invoice_id):
    """(get_tax_summary(), subtotal, tax_amount, total) direkt aus der DB."""
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        return inv.get_tax_summary(), inv.subtotal, inv.tax_amount, inv.total


class TestS2Rechenregel:
    """Die eine Rechenregel, ohne Datenbank geprüft."""

    @staticmethod
    def _zeile(betrag, satz):
        from app.models.enums import TaxRate
        return SimpleNamespace(line_total=Decimal(betrag), tax_rate=TaxRate(satz))

    def test_steuer_wird_je_satz_gerundet(self):
        from app.models.invoice import steuer_je_satz
        saetze = steuer_je_satz(
            [self._zeile("4.50", "STANDARD"), self._zeile("2.50", "REDUZIERT")], Decimal("0"))

        # aufsteigend nach Satz, unabhängig von der Positionsreihenfolge
        assert [(s["percent"], s["base"], s["tax"]) for s in saetze] == [
            (7, Decimal("2.50"), Decimal("0.18")),
            (19, Decimal("4.50"), Decimal("0.86")),
        ]

    def test_rabatt_wird_je_satz_gerundet(self):
        """3,8 % auf 25,00 € (7 %) und 9,00 € (19 %)."""
        from app.models.invoice import steuer_je_satz
        saetze = steuer_je_satz(
            [self._zeile("25.00", "REDUZIERT"), self._zeile("9.00", "STANDARD")], Decimal("3.8"))

        assert [(s["rabatt"], s["base"], s["tax"]) for s in saetze] == [
            (Decimal("0.95"), Decimal("24.05"), Decimal("1.68")),
            (Decimal("0.34"), Decimal("8.66"), Decimal("1.65")),
        ]


class TestS2Rechnungssummen:

    def test_summe_der_satzsteuern_ist_tax_amount(self, client):
        """Bisher: tax_amount 1,03, Steuerblock 0,18 + 0,86 = 1,04."""
        rechnung = _s2_rechnung_zeilenweise(client)

        saetze, netto, steuer, brutto = _s2_steuerblock(rechnung["id"])
        assert sum(s["tax"] for s in saetze) == steuer == Decimal("1.04")
        assert sum(s["base"] for s in saetze) == netto == Decimal("7.00")
        assert brutto == Decimal("8.04")
        assert Decimal(str(rechnung["tax_amount"])) == Decimal("1.04")

    def test_mit_rechnungsrabatt_gehen_alle_summen_auf(self, client):
        rechnung = _s2_rechnung_zeilenweise(client, zeilen=[
            {"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
             "unit_price": 2.50, "tax_rate": "REDUZIERT"},
            {"description": "Pfandkiste IFCO", "quantity": 2, "unit": "STK",
             "unit_price": 4.50, "tax_rate": "STANDARD"},
        ], discount_percent=3.8)

        saetze, netto, steuer, brutto = _s2_steuerblock(rechnung["id"])
        assert Decimal(str(rechnung["discount_amount"])) == sum(s["rabatt"] for s in saetze) == Decimal("1.29")
        assert netto == sum(s["base"] for s in saetze) == Decimal("32.71")
        assert steuer == sum(s["tax"] for s in saetze) == Decimal("3.33")
        assert brutto == netto + steuer == Decimal("36.04")

    def test_rabatt_entfernen_setzt_rabattbetrag_zurueck(self, client):
        """Sonst druckt das PDF 'Zwischensumme' und 'Rabatt' mit dem alten Betrag."""
        rechnung = _s2_rechnung_zeilenweise(client, discount_percent=10)
        assert Decimal(str(rechnung["discount_amount"])) == Decimal("0.70")

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}", json={"discount_percent": 0})

        assert r.status_code == 200, r.text
        assert Decimal(str(r.json()["discount_amount"])) == Decimal("0")
        assert Decimal(str(r.json()["total"])) == Decimal("8.04")


class TestS2KeinAbrufSchreibt:

    def test_get_tax_summary_liest_gespeicherte_zeilenbetraege(self, client):
        """PDF-Abruf und DATEV lesen get_tax_summary() auch für versendete
        Rechnungen. Es darf line_total nicht aus Menge × Preis neu rechnen
        und nichts an der Session verändern."""
        from app.models.invoice import Invoice
        rechnung = _s2_rechnung_zeilenweise(client)
        # Gespeicherten Zeilenbetrag abweichend von Menge × Preis setzen, damit
        # ein Neuberechnen auffällt. Nur im Test — echte Rechnungen nie direkt ändern.
        with TestingSessionLocal() as db:
            inv = db.get(Invoice, uuid.UUID(rechnung["id"]))
            next(l for l in inv.lines if l.description == "Erbsen-Schale").line_total = Decimal("2.40")
            db.commit()

        with TestingSessionLocal() as db:
            inv = db.get(Invoice, uuid.UUID(rechnung["id"]))
            saetze = inv.get_tax_summary()

            assert not db.dirty, f"get_tax_summary() hat verändert: {db.dirty}"
            assert [(s["percent"], s["base"]) for s in saetze] == [
                (7, Decimal("2.40")),
                (19, Decimal("4.50")),
            ]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k "TestS2"`
Erwartet: 6 FAILED. Die Meldungen lauten so (gegen `c4a1832` geprüft):
- beide `TestS2Rechenregel`-Tests: `ImportError: cannot import name 'steuer_je_satz' from 'app.models.invoice'`
- `test_summe_der_satzsteuern_ist_tax_amount`: `assert Decimal('1.04') == Decimal('1.03')`
- `test_mit_rechnungsrabatt_gehen_alle_summen_auf`: `KeyError: 'rabatt'`
- `test_rabatt_entfernen_setzt_rabattbetrag_zurueck`: `assert Decimal('0.70') == Decimal('0')`
- `test_get_tax_summary_liest_gespeicherte_zeilenbetraege`: `AssertionError: get_tax_summary() hat verändert: IdentitySet([<InvoiceLine(pos=1, desc='Erbsen-Schale...')>, <InvoiceLine(pos=2, desc='Pfandkiste IFCO...')>])`

- [ ] **Step 3: Rechenregel als Modulfunktionen**

In `backend/app/models/invoice.py` direkt **vor** `class Invoice(Base):` einfügen. `Decimal`, `ROUND_HALF_UP` und `TaxRate` sind dort bereits importiert (Zeilen 7 und 18).

```python
def _cent(betrag: Decimal) -> Decimal:
    return betrag.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def steuer_je_satz(lines, discount_percent) -> list[dict]:
    """Entgelt und Steuer je Steuersatz — die eine Rechenregel für Rechnungssummen,
    PDF-Steuerblock und DATEV.

    § 14 Abs. 4 Nr. 8 UStG verlangt auf der Rechnung das Entgelt und den
    Steuerbetrag je Steuersatz; § 16 Abs. 1 UStG rechnet die Steuer auf die
    Summe der Entgelte je Satz. Regel:
      1. je Satz die (bereits auf den Cent gerundeten) Zeilenbeträge summieren,
      2. den Rechnungsrabatt je Satz auf den Cent runden und abziehen (= Entgelt),
      3. die Steuer auf dieses Entgelt rechnen und je Satz auf den Cent runden.
    Entgelt und Steuer je Satz folgen so aus den Positionen auf dem Beleg.
    Der Gesamtrabatt ist die Summe der Rabatte je Satz und kann deshalb 1 ct
    von "Zwischensumme × Rabattsatz" abweichen.

    Arbeitet auf allem, was `tax_rate` und `line_total` trägt (auch auf den
    Dummy-Zeilen der Vorlagen-Vorschau). Verändert nichts.
    Reihenfolge: aufsteigend nach Steuersatz (0 %, 7 %, 19 %).
    """
    rabatt_prozent = Decimal(str(discount_percent or 0))
    je_satz: dict = {}
    for line in lines:
        eintrag = je_satz.setdefault(line.tax_rate, {
            "rate": line.tax_rate,
            "percent": line.tax_rate.percent,
            "netto_vor_rabatt": Decimal("0.00"),
            "rabatt": Decimal("0.00"),
            "base": Decimal("0.00"),
            "tax": Decimal("0.00"),
        })
        eintrag["netto_vor_rabatt"] += Decimal(str(line.line_total or 0))

    for eintrag in je_satz.values():
        if rabatt_prozent > 0:
            eintrag["rabatt"] = _cent(eintrag["netto_vor_rabatt"] * rabatt_prozent / 100)
        eintrag["base"] = eintrag["netto_vor_rabatt"] - eintrag["rabatt"]
        eintrag["tax"] = _cent(eintrag["base"] * eintrag["rate"].rate)

    return sorted(je_satz.values(), key=lambda e: e["percent"])


def steuerausweis_stimmt(invoice) -> bool:
    """Ergibt die Aufteilung je Satz exakt die gespeicherten Rechnungssummen?

    Für jede mit calculate_totals() berechnete Rechnung ja. Nein nur bei
    Altrechnungen, deren Summen vor der Vereinheitlichung (Oktober 2026) mit
    einmaliger Rundung über alle Sätze festgeschrieben wurden — bei
    gemischten Sätzen oder Rechnungsrabatt kann das 1 ct abweichen.
    Versendete Rechnungen sind unveränderlich (GoBD); ihr PDF muss dann die
    festgeschriebenen Beträge zeigen, keine davon abweichende Aufteilung.
    """
    saetze = steuer_je_satz(invoice.lines, invoice.discount_percent)
    return (
        sum((s["base"] for s in saetze), Decimal("0")) == Decimal(str(invoice.subtotal or 0))
        and sum((s["tax"] for s in saetze), Decimal("0")) == Decimal(str(invoice.tax_amount or 0))
    )
```

- [ ] **Step 4: `calculate_totals` und `get_tax_summary` auf die Regel umstellen**

In `class Invoice` den kompletten Körper von `calculate_totals` (Zeilen 132-172) ersetzen. Der Pfand-Block am Ende bleibt **wörtlich** erhalten.

```python
    def calculate_totals(self) -> None:
        """Berechnet Zwischensumme, Rabatt, MwSt und Gesamtbetrag.

        Alle Beträge kommen aus steuer_je_satz() — derselben Rechnung, die
        get_tax_summary() und der Steuerblock im PDF verwenden. Dadurch gilt
        für jede hier berechnete Rechnung: Summe der Netto je Satz = subtotal,
        Summe der Steuer je Satz = tax_amount. Früher rundete diese Methode
        die Steuer einmal über alle Sätze, get_tax_summary() je Satz — bei
        gemischten Sätzen lagen beide 1 ct auseinander.
        """
        for line in self.lines:
            line.calculate_line_total()
        saetze = steuer_je_satz(self.lines, self.discount_percent)

        self.discount_amount = sum((s["rabatt"] for s in saetze), Decimal("0.00"))
        self.subtotal = sum((s["base"] for s in saetze), Decimal("0.00"))
        self.tax_amount = sum((s["tax"] for s in saetze), Decimal("0.00"))
        self.total = self.subtotal + self.tax_amount

        # Pfand-Summe berechnen (Brutto)
        deposit_sum = sum((line.gross_total for line in self.lines if line.is_deposit), Decimal("0.00"))
        self.total_deposit = deposit_sum.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

`get_tax_summary` (Zeilen 193-223) komplett ersetzen:

```python
    def get_tax_summary(self) -> list[dict]:
        """MwSt je Satz: Schlüssel rate, percent, base, tax, netto_vor_rabatt, rabatt.

        Gleiche Rechenregel wie calculate_totals(). Liest die gespeicherten
        Zeilenbeträge und verändert nichts — sicher auch für versendete
        Rechnungen (PDF-Abruf, DATEV-Export).
        """
        return steuer_je_satz(self.lines, self.discount_percent)
```

`discount_amount` wird damit **immer** gesetzt, ohne Rabatt also auf 0,00. Das ist beabsichtigt (Befund 4). `InvoiceLine.calculate_line_total`, `InvoiceLine.tax_amount` und `InvoiceLine.gross_total` bleiben unverändert.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k "TestS2"`
Erwartet: 6 passed.

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_pfand_rabatt.py tests/test_documents_preise.py tests/test_storno.py tests/test_sammelrechnung.py tests/test_datev_export.py tests/test_gernot_260821.py -q`
Erwartet: 95 passed. Diese Dateien rechnen Rechnungssummen, Rabatte, Pfand und DATEV. Der Lauf dauert mehrere Minuten, weil `test_gernot_260821.py` langsam ist; im Planungslauf ergab er gegen den Stand nach diesem Task 95 passed.

- [ ] **Step 6: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` ohne Ausgabe.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/invoice.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): Steuer je Satz gerundet — Summen und Steuerblock rechnen gleich"
```

---

### Task 9: `add_line` rechnet über alle Positionen — Hilfsfunktion `recalculate_totals`

Zusammengeführt aus den Einzelabschnitten S2 (Befund 3: `POST /invoices` mit Positionen zählt nur die erste) und S3 (dieselbe Ursache in `add_line`, auch im Storno). Statt eines Nachrechnens nur in `POST /invoices` wird die Ursache einmal in `InvoiceService.add_line` behoben.

**Files:**
- Modify: `backend/app/services/invoice_service.py` — Ende von `add_line` (~166-175) und neue Methode `recalculate_totals` direkt danach, vor `create_invoice_from_order`
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `S2_ZEILEN` und `_s2_kunde` aus Task 8; `Invoice.calculate_totals()` in der Fassung aus Task 8.
- Produces:
  - `InvoiceService.recalculate_totals(self, invoice: Invoice) -> Invoice`. Ablauf: `self.db.flush()`, dann `self.db.refresh(invoice, ["lines"])`, dann `invoice.calculate_totals()`. Pflicht nach jedem Anlegen oder Löschen einer Position. Task 12 (Stornorechnung) und Task 25 (`update_invoice_line`, `delete_invoice_line`) rufen sie auf.
  - `add_line` rechnet ab jetzt über **alle** Positionen. Das wirkt auf `POST /invoices` mit `lines`, `create_invoice_from_order`, den Sammelrechnungslauf, den Storno-Pfad und `generate_recurring_invoices`.
  - Testhelfer `_s2_rechnung_in_einem_aufruf(client, zeilen=S2_ZEILEN, **kopf)`. Tasks 10 und 11 verwenden ihn wieder.

- [ ] **Step 1: Failing Tests anhängen**

```python
# --- S2: POST /invoices mit Positionen, recalculate_totals (Task 9) --------

def _s2_rechnung_in_einem_aufruf(client, zeilen=S2_ZEILEN, **kopf):
    """POST /invoices mit Positionen — der Weg, der bisher nur Zeile 1 zählte."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": _s2_kunde(client)["id"],
        "invoice_date": date.today().isoformat(),
        "lines": zeilen,
        **kopf,
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestS2AnlageMitPositionen:

    def test_anlage_mit_positionen_zaehlt_alle_zeilen(self, client):
        """Bisher 2,50 / 0,18 / 2,68 — nur die erste Position."""
        rechnung = _s2_rechnung_in_einem_aufruf(client)

        assert Decimal(str(rechnung["subtotal"])) == Decimal("7.00")
        assert Decimal(str(rechnung["tax_amount"])) == Decimal("1.04")
        assert Decimal(str(rechnung["total"])) == Decimal("8.04")
        detail = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert len(detail["lines"]) == 2

    def test_hilfsfunktion_rechnet_ohne_geloeschte_position(self, client):
        """recalculate_totals sieht auch eine gelöschte Position nicht mehr —
        Task 25 nutzt das beim Löschen einer Entwurfsposition."""
        from app.models.invoice import Invoice
        from app.services.invoice_service import InvoiceService

        rechnung = _s2_rechnung_in_einem_aufruf(client)
        with TestingSessionLocal() as db:
            inv = db.get(Invoice, uuid.UUID(rechnung["id"]))
            assert len(inv.lines) == 2  # Collection ist jetzt geladen
            db.delete(inv.lines[1])
            InvoiceService(db).recalculate_totals(inv)
            assert len(inv.lines) == 1
            # übrig: 2,50 € zu 7 % = 2,50 netto + 0,18 USt
            assert inv.total == Decimal("2.68")
```

`Invoice.lines` ist nach `InvoiceLine.position` sortiert (`models/invoice.py:124-126`); `lines[1]` ist also die 19-%-Zeile.

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS2AnlageMitPositionen -v`
Erwartet: 2 FAILED (in einer Kopie von `efcea00` + Task 8 geprüft):
- `test_anlage_mit_positionen_zaehlt_alle_zeilen`: `assert Decimal('2.50') == Decimal('7.00')`
- `test_hilfsfunktion_rechnet_ohne_geloeschte_position`: `AttributeError: 'InvoiceService' object has no attribute 'recalculate_totals'`

- [ ] **Step 3: Hilfsfunktion und `add_line`**

In `backend/app/services/invoice_service.py` das Ende von `add_line` ersetzen. Bisher steht dort:

```python
        self.db.add(line)
        self.db.flush()

        # Rechnungssummen neu berechnen
        invoice.calculate_totals()

        return line
```

Neu, einschließlich der neuen Methode direkt dahinter (vor `create_invoice_from_order`):

```python
        self.db.add(line)
        # Summen über ALLE Positionen — invoice.lines trägt nach dem ersten
        # Zugriff sonst den alten Stand (siehe recalculate_totals).
        self.recalculate_totals(invoice)

        return line

    def recalculate_totals(self, invoice: Invoice) -> Invoice:
        """Summen einer Rechnung aus dem aktuellen Stand ihrer Positionen.

        Pflicht nach jedem Anlegen oder Löschen einer Position. Die Session
        läuft mit autoflush=False, und invoice.lines bleibt nach dem ersten
        Zugriff geladen: Positionen, die danach über invoice_id angelegt oder
        per db.delete entfernt werden, sähe calculate_totals sonst nicht.
        Deshalb erst schreiben, dann die Positionen neu laden, dann rechnen.
        """
        self.db.flush()
        self.db.refresh(invoice, ["lines"])
        invoice.calculate_totals()
        return invoice
```

Nur die Zeilen ab `self.db.add(line)` werden ersetzt; der Rest von `add_line` (Satz vom Aufrufer, `is_deposit` aus dem Produkt) bleibt unverändert.

Nicht anfassen:
- `create_invoice_from_order` (~210-214, `refresh(invoice, ["lines"])` + `calculate_totals()`) und `batch_run_commit` (`invoices.py` ~639-643): Sie laden die Positionen schon selbst neu, und Tasks 2/3 arbeiten dort.
- `POST /invoices` (`create_invoice` in `invoices.py`, ~106-127): Es ruft je Zeile `service.add_line` und ist damit repariert. Ein eigenes Nachrechnen dort entfällt.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k "TestS2"`
Erwartet: 8 passed.

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_features.py tests/test_storno.py tests/test_pfand_rabatt.py tests/test_services.py -q -rfE -p no:cacheprovider`
Erwartet: genau vier Fehlschläge, alle Baseline-Altlasten: `test_features.py::TestFeatures::test_subscription_processing`, `test_services.py::TestInvoiceService::test_finalize_empty_invoice_fails`, `::test_record_partial_payment`, `::test_record_full_payment` (in der Kopie: 4 failed, 29 passed). **`test_services.py::TestInvoiceService::test_invoice_totals_update` ist jetzt grün** — gleiche Ursache, gewollt. Die Zahlungstests haben eine andere Ursache (siehe Nebenbefunde).

- [ ] **Step 5: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/invoice_service.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): add_line rechnet über alle Positionen — POST /invoices mit Positionen zählte nur die erste"
```

---

### Task 10: Rechnungs-PDF mit Spalte MwSt und Steuer je Satz

**Files:**
- Modify: `backend/app/services/pdf_service.py`
  - Imports, Zeilen 1-12
  - Positionstabelle, `:271-298`
  - Summenblock, `:300-335`
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes:
  - `steuer_je_satz` und `steuerausweis_stimmt` aus Task 8
  - `_s2_rechnung_in_einem_aufruf` aus Task 9 und `_s2_steuerblock` aus Task 8
  - `tests.test_documents_preise._pdf_text(pdf_bytes) -> bytes`: dekodiert die ASCII85+Flate-Streams von ReportLab, siehe die Nutzung in `test_gernot_260821.py:21-25`
  - `tests.test_sammelrechnung.COMMIT` und `_bestellung_mit_ls(client, customer_id, liefertag, zeilen)`
- Produces: Rechnungs-PDF mit Spalte „MwSt“ (Inhalt z. B. `7 %`) zwischen „Einzelpreis“ und „Gesamt (Netto)“. Im Summenblock steht je Satz eine Zeile `USt {p} % auf {Entgelt} €:` mit dem Steuerbetrag, aufsteigend nach Satz, zwischen „Netto:“ und „Gesamtbetrag:“.

- [ ] **Step 1: Failing Tests anhängen**

```python
# --- S2 Task 3 -------------------------------------------------------------

def _s2_pdf_texte(client, invoice_id) -> list[str]:
    """Alle Textstücke des Rechnungs-PDFs, je Tabellenzelle eins.

    ReportLab schreibt jede Zelle als '(<text>) Tj'; '€' erscheint dabei als
    Oktal-Escape '\\200'. Deshalb prüfen die Tests mit startswith.
    """
    r = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
    assert r.status_code == 200, r.text
    roh = _pdf_text(r.content).decode("latin-1", errors="ignore")
    return re.findall(r"\((.*?)\) Tj", roh)


class TestS2RechnungsPdf:

    def test_pdf_weist_entgelt_und_steuer_je_satz_aus(self, client):
        rechnung = _s2_rechnung_in_einem_aufruf(client)

        texte = _s2_pdf_texte(client, rechnung["id"])

        assert "MwSt" in texte, "Spalte MwSt fehlt in der Positionstabelle"
        assert "7 %" in texte and "19 %" in texte, "Satz je Position fehlt"
        assert any(t.startswith("USt 7 % auf 2.50 ") for t in texte), texte
        assert any(t.startswith("USt 19 % auf 4.50 ") for t in texte), texte
        assert any(t.startswith("0.18 ") for t in texte)
        assert any(t.startswith("0.86 ") for t in texte)
        assert any(t.startswith("8.04 ") for t in texte)
        assert "USt:" not in texte, "Pauschale USt-Zeile statt Ausweis je Satz"

    def test_ein_satz_ergibt_eine_steuerzeile(self, client):
        rechnung = _s2_rechnung_in_einem_aufruf(client, zeilen=[S2_ZEILEN[0]])

        texte = _s2_pdf_texte(client, rechnung["id"])

        assert any(t.startswith("USt 7 % auf 2.50 ") for t in texte), texte
        assert not any(t.startswith("USt 19 %") for t in texte)

    def test_altrechnung_behaelt_festgeschriebene_betraege(self, client):
        """GoBD: eine vor der Umstellung versendete Rechnung mit 1,03 € USt
        darf beim erneuten Abruf nicht plötzlich 1,04 € zeigen."""
        from app.models.invoice import Invoice
        rechnung = _s2_rechnung_in_einem_aufruf(client)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        # Zustand einer Altrechnung nachstellen: Summen mit der alten Rundung.
        # Nur im Test — in echten Daten werden Rechnungen nie direkt geändert.
        with TestingSessionLocal() as db:
            inv = db.get(Invoice, uuid.UUID(rechnung["id"]))
            inv.tax_amount = Decimal("1.03")
            inv.total = Decimal("8.03")
            db.commit()

        texte = _s2_pdf_texte(client, rechnung["id"])

        assert "USt:" in texte
        assert any(t.startswith("1.03 ") for t in texte)
        assert any(t.startswith("8.03 ") for t in texte)
        assert not any(t.startswith("USt 7 % auf") for t in texte)
        # Die DB behält die festgeschriebenen Summen. GET /pdf committet nie;
        # dass get_tax_summary() selbst nichts verändert, prüft
        # TestS2KeinAbrufSchreibt (Task 8).
        _, _, steuer, brutto = _s2_steuerblock(rechnung["id"])
        assert (steuer, brutto) == (Decimal("1.03"), Decimal("8.03"))

    def test_sammelrechnung_pdf_laesst_sich_erzeugen(self, client, sample_customer):
        """Die Lieferschein-Anhangstabelle nutzte Decimal ohne Import → 500."""
        from tests.test_sammelrechnung import COMMIT, _bestellung_mit_ls
        _bestellung_mit_ls(client, sample_customer["id"], "2026-03-05", [
            {"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
             "unit_price": 2.50, "tax_rate": "REDUZIERT"},
        ])
        r = client.post(COMMIT, json={"period_from": "2026-03-01", "period_to": "2026-03-31"})
        assert r.status_code == 201, r.text

        texte = _s2_pdf_texte(client, r.json()["rechnungen"][0]["id"])

        assert "Enthaltene Lieferscheine" in texte
        assert any(t.startswith("USt 7 % auf 25.00 ") for t in texte), texte
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS2RechnungsPdf -v`
Erwartet: 3 FAILED, gegen den Stand nach Task 9 geprüft:
- `test_pdf_weist_entgelt_und_steuer_je_satz_aus`: `AssertionError: Spalte MwSt fehlt in der Positionstabelle`
- `test_ein_satz_ergibt_eine_steuerzeile`: AssertionError mit der Textliste
- `test_sammelrechnung_pdf_laesst_sich_erzeugen`: `NameError: name 'Decimal' is not defined` in `app/services/pdf_service.py:389`

`test_altrechnung_behaelt_festgeschriebene_betraege` ist bereits grün und sichert das GoBD-Verhalten über die Änderung hinweg.

- [ ] **Step 3: Imports**

In `backend/app/services/pdf_service.py` als erste Zeile:

```python
from decimal import Decimal
```

Zeile 9 `from app.models.invoice import Invoice, InvoiceType` ersetzen durch:

```python
from app.models.invoice import Invoice, InvoiceType, steuer_je_satz, steuerausweis_stimmt
```

- [ ] **Step 4: Spalte MwSt in der Positionstabelle**

In `generate_invoice_pdf`, im Block `if _en(tmpl, "lines_table", default=True):` (Zeilen 272-298), nur drei Stellen ändern. Der `TableStyle` bleibt unverändert; `('ALIGN', (2,1), (-1,-1), 'RIGHT')` richtet die neue Spalte schon rechtsbündig aus.

Achtung: Dieselbe Kopfzeile `data = [["Pos", "Art.-Nr.", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "Gesamt (Netto)"]]` steht wörtlich ein zweites Mal in `generate_confirmation_pdf` (Zeile 689). Nur das **erste** Vorkommen (Zeile 273, in `generate_invoice_pdf`) ersetzen. Die Auftragsbestätigung bleibt unverändert. Die beiden anderen Ersetzungsstellen (`f"{line.line_total:.2f} €"` nach `f"{line.unit_price:.2f} €",` und `colWidths=[1.0*cm, 2.0*cm, 5.3*cm, …]`) kommen in der Datei nur einmal vor.

Die Kopfzeile (Zeile 273) ersetzen:

```python
            # MwSt-Spalte: bei gemischten Sätzen (Ware 7 %, Pfand 19 %) muss je
            # Position erkennbar sein, welcher Satz gilt (§ 14 Abs. 4 Nr. 8 UStG).
            data = [["Pos", "Art.-Nr.", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "MwSt", "Gesamt (Netto)"]]
```

In `data.append([...])` zwischen `f"{line.unit_price:.2f} €",` und `f"{line.line_total:.2f} €"` einfügen:

```python
                    f"{line.tax_rate.percent} %",
```

`colWidths` (Zeile 286) ersetzen. Die Summe bleibt 17,0 cm, also A4 minus 2 × 2 cm Rand. „Beschreibung“ ist ein `Paragraph` und bricht um. Die übrigen Spaltenköpfe passen in Helvetica-Bold 10 pt inklusive Zellenabstand; nachgemessen mit `reportlab.pdfbase.pdfmetrics.stringWidth`.

```python
            table = Table(data, colWidths=[1.0*cm, 2.0*cm, 3.9*cm, 1.6*cm, 1.8*cm, 2.3*cm, 1.4*cm, 3.0*cm])
```

- [ ] **Step 5: Steuer je Satz im Summenblock**

Im Block `if _en(tmpl, "totals_block", default=True):` die Liste

```python
            totals_data += [
                ["Netto:", f"{invoice.subtotal:.2f} €"],
                ["USt:", f"{invoice.tax_amount:.2f} €"],
                ["Gesamtbetrag:", f"{invoice.total:.2f} €"]
            ]
```

ersetzen durch:

```python
            totals_data.append(["Netto:", f"{invoice.subtotal:.2f} €"])
            # § 14 Abs. 4 Nr. 8 UStG: Entgelt und Steuerbetrag je Steuersatz.
            # Altrechnungen, deren festgeschriebene Summen noch mit der früheren
            # Rundung entstanden sind, behalten ihre eine USt-Zeile — ein
            # versendeter Beleg darf beim erneuten Abruf keine anderen Beträge
            # zeigen (GoBD). Korrektur nur per Storno und Neuausstellung.
            if steuerausweis_stimmt(invoice):
                for satz in steuer_je_satz(invoice.lines, invoice.discount_percent):
                    totals_data.append([
                        f"USt {satz['percent']} % auf {satz['base']:.2f} €:",
                        f"{satz['tax']:.2f} €",
                    ])
            else:
                totals_data.append(["USt:", f"{invoice.tax_amount:.2f} €"])
            totals_data.append(["Gesamtbetrag:", f"{invoice.total:.2f} €"])
```

Die folgende Zeile `gesamt_row = len(totals_data) - 1` und alles danach bleibt unverändert. `gesamt_row` zeigt weiter auf „Gesamtbetrag:“, auch wenn die Zahl der Steuerzeilen schwankt. Die Rabatt-Zeilen davor (`Zwischensumme`, `Rabatt`) bleiben ebenfalls; durch Task 8 gilt `Zwischensumme` = `subtotal + discount_amount` = Σ `netto_vor_rabatt` exakt.

Nicht anfassen: `generate_delivery_note_pdf` (eigene „USt:“-Zeile bei `:806`, ein Lieferschein ist keine Rechnung), `generate_payment_reminder_pdf` und `generate_confirmation_pdf`.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k "TestS2"`
Erwartet: 12 passed.

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_documents_preise.py tests/test_gernot_260817.py tests/test_gernot_260821.py tests/test_storno.py tests/test_features.py tests/test_print_queue.py -q`
Erwartet: einziger Fehlschlag ist die Baseline-Altlast `test_features.py::TestFeatures::test_subscription_processing`. Diese Dateien rufen Rechnungs-PDFs ab und prüfen u. a. „Zwischensumme“, „Rabatt“, „3.8“, „Pfand“ und „10.71“.

- [ ] **Step 7: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 8: Sichtprüfung des PDFs (manuell, ohne Netzwerk)**

```bash
cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python - <<'EOF'
from datetime import date
from fastapi.testclient import TestClient
from tests.conftest import engine, override_get_db
from app.main import app
from app.database import Base
from app.api.deps import get_current_user, _tenant_db, get_db

async def _auth():
    return {"id": "123e4567-e89b-12d3-a456-426614174000", "username": "t", "email": "t@x.de",
            "roles": ["admin"]}

app.dependency_overrides.update({get_current_user: _auth, _tenant_db: override_get_db, get_db: override_get_db})
Base.metadata.create_all(bind=engine)
c = TestClient(app, base_url="http://localhost")
k = c.post("/api/v1/sales/customers", json={"name": "Sichtprüfung", "typ": "HANDEL"}).json()
r = c.post("/api/v1/invoices", json={"customer_id": k["id"], "invoice_date": date.today().isoformat(),
    "discount_percent": 3.8, "lines": [
    {"description": "Erbsen-Schale", "quantity": 10, "unit": "STK", "unit_price": 2.50, "tax_rate": "REDUZIERT"},
    {"description": "Pfandkiste IFCO", "quantity": 2, "unit": "STK", "unit_price": 4.50, "tax_rate": "STANDARD"}]}).json()
open("/tmp/s2_rechnung.pdf", "wb").write(c.get(f"/api/v1/invoices/{r['id']}/pdf").content)
print("geschrieben: /tmp/s2_rechnung.pdf")
EOF
```

Erwartet: Das PDF zeigt die Spalte „MwSt“ mit 7 % und 19 %. Im Summenblock steht:

| Zeile | Betrag |
|---|---|
| Zwischensumme | 34.00 € |
| Rabatt (3.8 %) | -1.29 € |
| Netto | 32.71 € |
| USt 7 % auf 24.05 € | 1.68 € |
| USt 19 % auf 8.66 € | 1.65 € |
| Gesamtbetrag | 36.04 € |

Keine Spalte läuft über den Rand. Das PDF nur ansehen, nicht ins Repo legen. Im Planungslauf wurde genau dieses PDF erzeugt und gerendert; die Werte stimmen.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/test_gernot_261008.py
git commit -m "feat(rechnung): PDF weist Entgelt und Steuer je Satz aus (§ 14 Abs. 4 Nr. 8 UStG)"
```

---

### Task 11: „Mailen“ eines Entwurfs rechnet die Summen vorher final

**Files:**
- Modify: `backend/app/api/v1/invoices.py`, Funktion `send_invoice_email` (auf `c4a1832` Zeilen 223-275; nach dem Funktionsnamen suchen)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes:
  - `_s2_rechnung_in_einem_aufruf` aus Task 9, `_s2_steuerblock` aus Task 8, `_pdf_text` aus dem Dateikopf
  - `Invoice.calculate_totals()` in der Fassung aus Task 8 und der Steuerblock im PDF aus Task 10
  - `app.api.v1.invoices.send_email`: der Endpoint ruft die Funktion nur mit Schlüsselwortargumenten auf (`db`, `to`, `subject`, `body`, `attachment_bytes`, `attachment_filename`). Der Test ersetzt sie per `monkeypatch` und braucht dadurch weder SMTP noch Netzwerk.
- Produces:
  - `POST /api/v1/invoices/{invoice_id}/send` ruft für `ENTWURF` vor dem PDF `invoice.calculate_totals()` auf, genau wie `InvoiceService.finalize_invoice` (`backend/app/services/invoice_service.py:232-233`). Für jeden anderen Status bleibt alles unverändert.
  - Testhelfer `_s2_texte(pdf_bytes)`, `_s2_alte_summen_setzen(invoice_id)` und `_s2_mailen(client, monkeypatch, invoice_id)`.

- [ ] **Step 1: Failing Tests anhängen**

```python
# --- S2 Task 4 -------------------------------------------------------------

def _s2_texte(pdf_bytes) -> list[str]:
    """Wie _s2_pdf_texte, aber für PDF-Bytes, die nicht über GET /pdf kommen."""
    return re.findall(r"\((.*?)\) Tj", _pdf_text(pdf_bytes).decode("latin-1", errors="ignore"))


def _s2_alte_summen_setzen(invoice_id):
    """Summen mit der früheren Rundung (1,03 / 8,03) nachstellen.
    Nur im Test — in echten Daten werden Rechnungen nie direkt geändert."""
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        inv = db.get(Invoice, uuid.UUID(invoice_id))
        inv.tax_amount = Decimal("1.03")
        inv.total = Decimal("8.03")
        db.commit()


def _s2_mailen(client, monkeypatch, invoice_id) -> dict:
    """POST /invoices/{id}/send mit abgefangenem Versand; liefert die Mail-Argumente."""
    versendet = {}
    monkeypatch.setattr("app.api.v1.invoices.send_email", lambda **kw: versendet.update(kw))
    r = client.post(f"/api/v1/invoices/{invoice_id}/send",
                    params={"to_email": "einkauf@oekoring.example"})
    assert r.status_code == 200, r.text
    return versendet


class TestS2Mailversand:

    def test_mailen_eines_altentwurfs_rechnet_vorher_neu(self, client, monkeypatch):
        """'Mailen' stellt einen Entwurf aus (ENTWURF -> OFFEN), genau wie
        /finalize. Ein Entwurf mit Summen aus der alten Rundung ging bisher mit
        1,03 € und der pauschalen Zeile 'USt:' hinaus."""
        rechnung = _s2_rechnung_in_einem_aufruf(client)
        _s2_alte_summen_setzen(rechnung["id"])

        mail = _s2_mailen(client, monkeypatch, rechnung["id"])

        detail = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert detail["status"] == "OFFEN"
        assert Decimal(str(detail["tax_amount"])) == Decimal("1.04")
        assert Decimal(str(detail["total"])) == Decimal("8.04")
        texte = _s2_texte(mail["attachment_bytes"])
        assert any(t.startswith("USt 7 % auf 2.50 ") for t in texte), texte
        assert any(t.startswith("USt 19 % auf 4.50 ") for t in texte), texte
        assert "USt:" not in texte
        assert "8.04 EUR" in mail["body"]

    def test_mailen_einer_versendeten_rechnung_rechnet_nicht_neu(self, client, monkeypatch):
        """GoBD: erneutes Mailen einer festgeschriebenen Rechnung ändert keine Beträge."""
        rechnung = _s2_rechnung_in_einem_aufruf(client)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        _s2_alte_summen_setzen(rechnung["id"])

        mail = _s2_mailen(client, monkeypatch, rechnung["id"])

        _, _, steuer, brutto = _s2_steuerblock(rechnung["id"])
        assert (steuer, brutto) == (Decimal("1.03"), Decimal("8.03"))
        texte = _s2_texte(mail["attachment_bytes"])
        assert "USt:" in texte
        assert any(t.startswith("1.03 ") for t in texte)
        assert "8.03 EUR" in mail["body"]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS2Mailversand -v`
Erwartet (gegen den Stand nach Task 10 geprüft): 1 FAILED, 1 passed.
- `test_mailen_eines_altentwurfs_rechnet_vorher_neu`: `AssertionError: assert Decimal('1.03') == Decimal('1.04')`
- `test_mailen_einer_versendeten_rechnung_rechnet_nicht_neu` ist bereits grün. Er sichert ab, dass die Korrektur nicht auf ausgestellte Rechnungen übergreift.

- [ ] **Step 3: Entwurf vor dem PDF final berechnen**

In `backend/app/api/v1/invoices.py`, Funktion `send_invoice_email`, zwischen

```python
    if not invoice.lines:
        raise HTTPException(status_code=400, detail="Rechnung hat keine Positionen")
```

und

```python
    try:
        pdf = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
```

einfügen (4 Leerzeichen Einrückung, mit je einer Leerzeile davor und danach). `InvoiceStatus` ist in der Datei bereits importiert (Zeilen 13-16).

```python
    # Mit dem Versand wird ein Entwurf ausgestellt (ENTWURF -> OFFEN, unten),
    # genau wie bei /finalize. Deshalb die Summen vorher final berechnen, wie
    # InvoiceService.finalize_invoice. Sonst ginge ein Entwurf, dessen Summen
    # noch mit der früheren Rundung gespeichert sind, mit der pauschalen
    # Zeile "USt:" statt mit Steuer je Satz hinaus (§ 14 Abs. 4 Nr. 8 UStG).
    # Festgeschriebene Rechnungen (jeder andere Status) werden NIE neu
    # berechnet (GoBD). Scheitert der Versand, wird nicht committet und die
    # Neuberechnung verfällt mit der Session.
    if invoice.status == InvoiceStatus.ENTWURF:
        invoice.calculate_totals()
```

Die Rechnung ist dort mit `joinedload(InvoiceModel.lines)` geladen, `invoice.lines` ist also vollständig. Der Rest der Funktion bleibt unverändert, auch der Statuswechsel `ENTWURF` → `OFFEN` und `db.commit()` am Ende. `get_db` (`backend/app/database.py:32-50`) committet nicht selbst. Endet der Versand mit 502/503, verwirft das Schließen der Session die Neuberechnung, und der Entwurf bleibt unverändert.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k "TestS2"`
Erwartet: 14 passed.

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_erp.py tests/test_dunning.py tests/test_storno.py -q`
Erwartet: keine Fehlschläge (Rechnungs-API inkl. Finalisieren, Mahn-Mail, Storno; im Planungslauf 45 passed).

- [ ] **Step 5: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): Mailen eines Entwurfs berechnet Summen vorher wie Finalisieren"
```

---

## Abschnitt S3: Storno mehrzeiliger Rechnungen reparieren, Stornobeleg ohne Mahnung — Tasks 12–15

**Einordnung:** S3 läuft nach S2.
- **Summen:** Die Behebung in `add_line` und `InvoiceService.recalculate_totals` liefert Task 9. Task 12 ruft die Hilfsfunktion für die Stornorechnung auf; deshalb sind in Task 12 nur noch zwei Tests rot.
- **Satz der Stornozeilen:** `cancel_invoice` kopiert die Positionen **ohne** `add_line`, mit Satz, Konto und Pfandkennzeichen der Originalzeile. Der Storno von RE-00002/4 hebt das Pfand mit denselben 7 % auf, mit denen es berechnet wurde, auch wenn der Produktstamm 19 % sagt. Die 7 % allein unterscheiden Kopieren und `add_line` nicht (Task 2 sichert `add_line` mit `test_storno_bucht_mit_dem_satz_der_originalzeile_gegen`); das Sonderkonto 8338 unterscheidet sie (`test_storno_ist_spiegelbild_je_position`). `is_deposit` prüfen die S3-Tests über das ORM, weil es erst ab Task 25 in der Zeilenantwort steht; die 7-%-Pfandzeile legen die S3-Helfer direkt über das ORM an.
- **Bedingungen von S6:** Der R1.6-Block in `cancel_invoice` (Lieferscheine lösen) bleibt unverändert, und die Stornorechnung bekommt weiterhin **keine** `order_id`. Darauf bauen Tasks 20–22.
- **`send_invoice_email`:** Task 13 Step 5 ändert nur die STORNIERT-Prüfung und den Inhalt des `try:`. Der Block aus Task 11 zwischen `if not invoice.lines: raise …` und `try:` bleibt stehen.
- **DATEV:** Stornopaar = Original + `GUTSCHRIFT` mit `original_invoice_id`, beide `STORNIERT`. Task 17 exportiert genau dieses Paar und setzt seine Sperre direkt vor `# Original stornieren`; die Zeile bleibt nach Task 13 erhalten.
- **Dashboard:** S3 ändert `Dashboard.tsx` nicht. Die Stornorechnung fällt dort allein durch ihren Status aus der Liste `status: 'OFFEN'`.
- **Produktionsrechnungen:** Die Korrektur von RE-2026-00002/3/4 steht im Runbook am Ende (kein Worker-Task).

**Ausgangsbefund:** Am Code mit der echten App nachgestellt (TestClient, In-Memory-DB), nicht geschätzt.

| Befund | Gemessen | Ursache im Code |
|---|---|---|
| Storno einer zweizeiligen Rechnung (10 × 1,00 € zu 7 % + Pfand 6,67 € zu 7 % = 17,84 €) | Stornorechnung −10,70 € statt −17,84 €, `total_deposit` 0 statt −7,14 | `add_line` (`invoice_service.py` ~166-173) ruft `invoice.calculate_totals()` auf. `invoice.lines` ist ab dem ersten Zugriff geladen, und neue Zeilen werden nur über `invoice_id` angehängt, nicht über die Collection. Die Session läuft mit `autoflush=False` (`tenancy.py:83`). Behoben in Task 9. |
| Storno derselben Rechnung mit 6,67 € zu **19 %** statt Pfand | Stornorechnung −10,70 € statt −18,64 € | gleiche Ursache |
| Storno einer Position mit Sonderkonto (8338) | Stornozeile auf 8300 | `cancel_invoice` ruft `add_line` ohne `buchungskonto`. `add_line` setzt dann das Standardkonto zum Satz (`invoice_service.py` ~141-147). |
| `POST /api/v1/invoices` mit zwei `lines` (10,00 € zu 7 % + 6,67 € zu 19 %) | `total` 10,70 statt 18,64 | gleiche Ursache in `add_line` — behoben in Task 9 |
| `DELETE /invoices/{id}/lines/{line_id}` | Summe bleibt 18,64 statt 10,70 | `db.delete(line)` ohne flush, dann `calculate_totals()` (`invoices.py` ~377-378). Wird in Task 25 behoben. |
| Baseline-Test `test_services.py::TestInvoiceService::test_invoice_totals_update` | rot | gleiche Ursache. Nach Task 9 grün (gemessen). |
| Stornorechnung übernimmt den Rechnungsrabatt nicht | Original 10 % Rabatt, Storno 0 % | `create_invoice` setzt bei `discount_percent == 0` den aktuellen Kundenrabatt (`invoice_service.py` ~61-62); `cancel_invoice` übergibt keinen |
| Stornorechnung ohne Liefer-/Leistungsdatum | `delivery_date` null | `cancel_invoice` übergibt `delivery_date` nicht |
| Stornorechnung `OFFEN`, fällig nach Zahlungsziel | `due_date` = heute + 14 Tage | `cancel_invoice` ~348; Folgen siehe Task 13 |


### Review Focus (S3)
1. Die Stornorechnung spiegelt das Original exakt: je Position Satz (7 % auf das Pfand), Konto einschließlich Sonderkonto, Pfandkennzeichen, Artikelnummer und Rabatt, je Satz Entgelt und Steuer. Siehe Task 12, `test_storno_ist_spiegelbild_je_position` und `test_storno_mit_zwei_saetzen_spiegelt_steuer_je_satz`. Die 7 % allein unterscheiden Kopieren und `add_line` nicht (siehe Einordnung). Das Sonderkonto unterscheidet sie.
2. Das Paar ist ausgeglichen. Es taucht nirgends als überfällig, gemahnt, offen oder als Umsatz auf. Das PDF bleibt abrufbar, Versenden geht per API. Siehe Task 13.
3. Eine Stornorechnung aus dem Altbestand mit `OFFEN` wird weder überfällig noch gemahnt, weder über `GET /invoices/overdue` noch über die geplanten Jobs. Siehe Task 13, `test_ueberfaellig_liste_ignoriert_alten_storno_auf_offen` und `test_geplante_jobs_ignorieren_negative_belege`.
4. Ein Entwurf bekommt nie eine Stornorechnung. Siehe Task 13.
5. Bei einer bezahlten Rechnung bleibt das Geld am alten Beleg. Die Warnung erscheint in der API, in der Akte und im Dialog. Siehe Task 14 und Task 15.

---

### Task 12: Die Stornorechnung ist das exakte Spiegelbild des Originals

**Files:**
- Modify: `backend/app/services/invoice_service.py` — in `cancel_invoice` der Block ab `credit_note = None` (~318-351)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `InvoiceService.recalculate_totals(invoice: Invoice) -> Invoice` (Task 9).
- Produces:
  - `cancel_invoice` erzeugt die Stornorechnung als Spiegelbild des Originals:
    - Positionen 1:1 mit negativer Menge, bewusst **nicht** über `add_line`.
    - Übernommen werden je Position `tax_rate`, `buchungskonto` (auch ein Sonderkonto), `is_deposit`, `product_id`, `sku`, `discount_percent` und `position`, dazu `description`, `unit` und `unit_price`.
    - Auf Rechnungsebene übernommen: `discount_percent`, `delivery_date`, `service_period_start/_end` und `buchungskonto`.
  - Testhelfer `_S3_ZEILEN`, `_s3_pfandartikel(client)`, `_s3_altrechnung(client, kunde, *, rabatt=None, lieferdatum=None, konto_ware=None)`, `_s3_storniere(client, rechnung, **extra)`, `_s3_betrag(wert)`. Tasks 13 und 14 verwenden sie weiter.

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_gernot_261008.py` anhängen (der Kopf aus Task 1 enthält alle Imports). Der Test „`POST /invoices` mit mehreren Positionen" und der Test der Hilfsfunktion stehen bereits in Task 9.

```python
# ---------------------------------------------------------------------------
# S3: Storno mehrzeiliger Rechnungen, Ausgleich, Warnungen
# ---------------------------------------------------------------------------

_S3_ZEILEN = [
    {"description": "BIO Erbsen-Schale", "quantity": 10, "unit": "STK",
     "unit_price": 1.00, "tax_rate": "REDUZIERT"},
    {"description": "Versandkarton", "quantity": 1, "unit": "STK",
     "unit_price": 6.67, "tax_rate": "STANDARD"},
]


def _s3_pfandartikel(client):
    """Pfandartikel wie im Produktstamm von Minga: 19 %, als Pfand gekennzeichnet."""
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)
    r = client.post("/api/v1/products", json={
        "sku": f"IFCO-{uuid.uuid4().hex[:6]}", "name": "Pfand IFCO-Kiste",
        "category": "PFAND", "base_price": "6.67", "base_unit_id": unit_id,
        "tax_rate": "STANDARD", "is_deposit": True,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s3_altrechnung(client, kunde, *, rabatt=None, lieferdatum=None, konto_ware=None):
    """Stellt RE-2026-00002/4 nach: Ware zu 7 % plus Pfand-Produktzeile, die
    auf der Rechnung mit 7 % statt 19 % steht — versendet, also OFFEN.

    Die Pfandzeile wird direkt angelegt: so steht sie in Produktion, und die
    API muss einen vom Produktstamm abweichenden Satz nicht mehr annehmen.
    konto_ware: ausdrücklich gesetztes Sonderkonto der Warenzeile
    (InvoiceLineCreate.buchungskonto), sonst das Standardkonto zum Satz.
    Ohne Rabatt: 16,67 netto, 1,17 USt, 17,84 brutto.
    """
    from app.models.invoice import InvoiceLine, TaxRate

    pfand = _s3_pfandartikel(client)
    body = {"customer_id": kunde["id"], "invoice_date": date.today().isoformat()}
    if lieferdatum:
        body["delivery_date"] = lieferdatum
    r = client.post("/api/v1/invoices", json=body)
    assert r.status_code == 201, r.text
    rechnung = r.json()

    ware = dict(_S3_ZEILEN[0])
    if konto_ware:
        ware["buchungskonto"] = konto_ware
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=ware)
    assert r.status_code == 201, r.text
    with TestingSessionLocal() as db:
        db.add(InvoiceLine(
            invoice_id=uuid.UUID(rechnung["id"]), position=2,
            product_id=uuid.UUID(pfand["id"]), sku=pfand["sku"],
            description="Pfand IFCO-Kiste",
            quantity=Decimal("1"), unit="STK", unit_price=Decimal("6.67"),
            tax_rate=TaxRate.REDUZIERT, is_deposit=True, buchungskonto="8300",
        ))
        db.commit()

    if rabatt is not None:
        r = client.patch(f"/api/v1/invoices/{rechnung['id']}", json={"discount_percent": rabatt})
        assert r.status_code == 200, r.text
    # finalize rechnet die Summen in einem frischen Request über alle Zeilen
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


def _s3_storniere(client, rechnung, **extra):
    body = {"reason": "Pfand mit 7 % statt 19 %", "reason_code": "SONSTIGES", **extra}
    return client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json=body)


def _s3_betrag(wert):
    # Beträge kommen als JSON-String ("17.84") — nie über float vergleichen
    return Decimal(str(wert))


class TestS3StornoMehrzeilig:
    """Der Storno summierte bei mehreren Positionen nur die erste (−10,70 statt −17,84)."""

    def test_storno_summiert_alle_positionen(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        assert _s3_betrag(original["total"]) == Decimal("17.84")

        r = _s3_storniere(client, original)
        assert r.status_code == 200, r.text
        storno = r.json()["credit_note"]

        assert _s3_betrag(storno["subtotal"]) == Decimal("-16.67")
        assert _s3_betrag(storno["tax_amount"]) == Decimal("-1.17")
        assert _s3_betrag(storno["total"]) == Decimal("-17.84")

    def test_storno_ist_spiegelbild_je_position(self, client, sample_customer):
        """Satz, Konto, Pfandkennzeichen und Artikelnummer kommen von der
        Originalzeile. Die Warenzeile steht auf einem Sonderkonto (8338): der
        frühere Weg über add_line setzte dort das Standardkonto zum Satz (8300),
        die Gegenbuchung landete auf einem anderen Konto als die Buchung."""
        from app.models.invoice import Invoice

        original = _s3_altrechnung(client, sample_customer, konto_ware="8338")
        storno = _s3_storniere(client, original).json()["credit_note"]

        orig = client.get(f"/api/v1/invoices/{original['id']}").json()
        sto = client.get(f"/api/v1/invoices/{storno['id']}").json()
        assert len(sto["lines"]) == len(orig["lines"]) == 2
        for o, s in zip(orig["lines"], sto["lines"]):
            assert s["position"] == o["position"]
            assert s["tax_rate"] == o["tax_rate"]
            assert s["buchungskonto"] == o["buchungskonto"]
            assert s["product_id"] == o["product_id"]
            assert s["sku"] == o["sku"]
            assert _s3_betrag(s["discount_percent"]) == _s3_betrag(o["discount_percent"])
            assert _s3_betrag(s["quantity"]) == -_s3_betrag(o["quantity"])
            assert _s3_betrag(s["line_total"]) == -_s3_betrag(o["line_total"])
        assert _s3_betrag(sto["total_deposit"]) == -_s3_betrag(orig["total_deposit"])

        # is_deposit steht erst ab S5 in der Zeilenantwort — deshalb über das ORM
        with TestingSessionLocal() as db:
            o_zeilen = db.get(Invoice, uuid.UUID(original["id"])).lines
            s_zeilen = db.get(Invoice, uuid.UUID(storno["id"])).lines
            assert [z.is_deposit for z in s_zeilen] == [z.is_deposit for z in o_zeilen] == [False, True]

        # GoBD: das Original bleibt unverändert
        assert _s3_betrag(orig["total"]) == Decimal("17.84")
        assert [l["tax_rate"] for l in orig["lines"]] == ["REDUZIERT", "REDUZIERT"]
        assert [l["buchungskonto"] for l in orig["lines"]] == ["8338", "8300"]

    def test_storno_mit_zwei_saetzen_spiegelt_steuer_je_satz(self, client, sample_customer):
        """Stornorechnung mit 7 % und 19 %: je Satz heben Entgelt und Steuer
        das Original genau auf, und die Satzsteuern ergeben tax_amount
        (dieselbe Prüfung wie steuerausweis_stimmt aus S2)."""
        from app.models.invoice import Invoice

        r = client.post("/api/v1/invoices", json={
            "customer_id": sample_customer["id"],
            "invoice_date": date.today().isoformat(),
        })
        assert r.status_code == 201, r.text
        rechnung = r.json()
        # Positionen einzeln: jeder Request hat eine frische Session, die
        # Summen des Originals stimmen also auch ohne den Fix in add_line.
        for zeile in _S3_ZEILEN:
            r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=zeile)
            assert r.status_code == 201, r.text
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text
        original = r.json()
        # 10,00 × 7 % + 6,67 × 19 % = 16,67 netto + 0,70 + 1,27 USt
        assert _s3_betrag(original["total"]) == Decimal("18.64")

        storno = _s3_storniere(client, original).json()["credit_note"]

        assert _s3_betrag(storno["subtotal"]) == Decimal("-16.67")
        assert _s3_betrag(storno["tax_amount"]) == Decimal("-1.97")
        assert _s3_betrag(storno["total"]) == Decimal("-18.64")
        with TestingSessionLocal() as db:
            o = db.get(Invoice, uuid.UUID(original["id"]))
            s = db.get(Invoice, uuid.UUID(storno["id"]))
            je_satz_o = {e["rate"]: (e["base"], e["tax"]) for e in o.get_tax_summary()}
            je_satz_s = {e["rate"]: (e["base"], e["tax"]) for e in s.get_tax_summary()}
            assert sum(b for b, _ in je_satz_s.values()) == s.subtotal
            assert sum(t for _, t in je_satz_s.values()) == s.tax_amount
        assert len(je_satz_s) == 2
        assert je_satz_s == {satz: (-b, -t) for satz, (b, t) in je_satz_o.items()}

    def test_storno_uebernimmt_rabatt_und_lieferdatum(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer, rabatt=10, lieferdatum="2026-10-07")
        storno = _s3_storniere(client, original).json()["credit_note"]

        assert _s3_betrag(storno["discount_percent"]) == Decimal("10")
        assert _s3_betrag(storno["total"]) == -_s3_betrag(original["total"])
        assert storno["delivery_date"] == "2026-10-07"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k TestS3StornoMehrzeilig`

Erwartet: 2 FAILED, 2 passed (in einer Kopie von `efcea00` mit Task 8 und Task 9 geprüft):
- `test_storno_ist_spiegelbild_je_position`: `AssertionError: assert '8300' == '8338'` — der Weg über `add_line` setzt das Standardkonto zum Satz.
- `test_storno_uebernimmt_rabatt_und_lieferdatum`: `AssertionError: assert Decimal('0.00') == Decimal('10')`.
- Grün sind bereits `test_storno_summiert_alle_positionen` und `test_storno_mit_zwei_saetzen_spiegelt_steuer_je_satz`: Seit Task 9 summiert `add_line` alle Positionen, damit ergibt auch der alte Storno −17,84 € statt −10,70 €. Beide sichern ab, dass der Kopierweg aus Step 3 nichts verschlechtert.

- [ ] **Step 3: Stornorechnung als Spiegelbild**

In `cancel_invoice` den Block von `credit_note = None` bis einschließlich `return invoice, credit_note` ersetzen durch:

```python
        credit_note = None
        if create_credit_note and invoice.total > 0:
            credit_note = self.create_invoice(
                customer_id=invoice.customer_id,
                invoice_type=InvoiceType.GUTSCHRIFT,
                original_invoice_id=invoice_id,
                delivery_date=invoice.delivery_date,
                buchungskonto=invoice.buchungskonto,
                header_text=(
                    f"Stornorechnung zur Rechnung Nr. {invoice.invoice_number} "
                    f"vom {invoice.invoice_date.strftime('%d.%m.%Y')}"
                ),
            )
            # Der Grund gehört an beide Belege — beim Prüfen liegt oft nur einer vor.
            credit_note.internal_notes = f"Storno zu {invoice.invoice_number}: {reason}"
            # Spiegelbild: create_invoice setzt sonst den heutigen Kundenrabatt.
            credit_note.discount_percent = invoice.discount_percent
            credit_note.service_period_start = invoice.service_period_start
            credit_note.service_period_end = invoice.service_period_end

            # Positionen 1:1 mit negativer Menge kopieren. Bewusst nicht über
            # add_line: die Stornorechnung muss Steuersatz, Konto und
            # Pfandkennzeichen des Originals tragen, nicht den heutigen
            # Produktstamm.
            for line in invoice.lines:
                self.db.add(InvoiceLine(
                    invoice_id=credit_note.id,
                    position=line.position,
                    product_id=line.product_id,
                    description=line.description,
                    sku=line.sku,
                    quantity=-line.quantity,
                    unit=line.unit,
                    unit_price=line.unit_price,
                    discount_percent=line.discount_percent,
                    tax_rate=line.tax_rate,
                    buchungskonto=line.buchungskonto,
                    is_deposit=line.is_deposit,
                ))
            self.recalculate_totals(credit_note)

            # Status regelt Task 13
            credit_note.status = InvoiceStatus.OFFEN
            credit_note.sent_at = datetime.now(timezone.utc)

        return invoice, credit_note
```

`InvoiceLine`, `InvoiceType`, `InvoiceStatus`, `datetime` und `timezone` sind in der Datei bereits importiert (Z. 6, 14-18). `create_invoice` nimmt `delivery_date` und `buchungskonto` als Parameter (`invoice_service.py:30-44`).

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k TestS3StornoMehrzeilig`

Erwartet: 4 passed (in der Prüfkopie bestätigt).

- [ ] **Step 5: Nachbartests**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_storno.py tests/test_sammelrechnung.py tests/test_pfand_rabatt.py tests/test_deposit.py tests/test_services.py -q -rfE -p no:cacheprovider`

Erwartet: genau drei Fehlschläge, alle Baseline-Altlasten: `test_services.py::TestInvoiceService::test_record_full_payment`, `::test_record_partial_payment` und `::test_finalize_empty_invoice_fails`. Ursache der beiden Zahlungstests: siehe Nebenbefunde. Ohne `memory://` dauert der Lauf ca. 5,5 min (`test_services.py` ist langsam).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/invoice_service.py backend/tests/test_gernot_261008.py
git commit -m "fix(storno): Stornorechnung spiegelt das Original — Satz, Konto, Pfand, Rabatt, Lieferdatum"
```

---

### Task 13: Das Stornopaar ist ausgeglichen und fällt aus Überfälligkeit, Mahnlauf, offenen Posten und Umsatz heraus

**Statuswahl, am Code geprüft:** Ein neuer Enum-Wert ist nicht nötig. Er wäre in SQLite technisch harmlos, weil `status` dort als `VARCHAR(13)` ohne CHECK-Constraint liegt (an einer Mandanten-DB gelesen). Er müsste aber in jeder Statusabfrage und im Frontend nachgezogen werden. Bewertet wurden die bestehenden Werte:

| Verbraucher | Fundstelle | `OFFEN` (heute) | `BEZAHLT` | `STORNIERT` |
|---|---|---|---|---|
| Überfällig markieren | `invoice_service.py` ~355-388; `invoice_tasks.py` ~40-52 | wird markiert ✗ | raus | raus |
| Mahnlauf (Mail über negativen Betrag) | `invoice_tasks.py` ~106-175 | nach Markierung gemahnt ✗ | raus | raus |
| Offene Posten | `Dashboard.tsx` ~82/~336 (`status: 'OFFEN'`), `Invoices.tsx` `totalOpen`, `get_revenue_summary.open_amount`, `calculate_revenue_stats` | zählt ✗ | raus | raus |
| Umsatz | `analytics.py:37` (OFFEN, BEZAHLT), `get_revenue_summary` (ohne ENTWURF/STORNIERT), `calculate_revenue_stats` (BEZAHLT) | −Betrag zählt, Original nicht ✗ | −Betrag zählt ✗ | Paar fällt ganz heraus ✓ |
| Zahlung erfassen | `record_payment` sperrt nur STORNIERT; Knopf nur OFFEN/TEILBEZAHLT/UEBERFAELLIG | offen ✗ | API offen | gesperrt ✓ |
| Knopf „→ lexoffice“ | `Invoices.tsx` ~406 (OFFEN/TEILBEZAHLT/UEBERFAELLIG/BEZAHLT) | sichtbar ✗ | sichtbar ✗ | ausgeblendet ✓ |
| Reiter und Kachel „Bezahlt“ | `Invoices.tsx` ~193, ~285 | – | Storno zählt als bezahlt ✗ | – ✓ |
| Versand `/send` | `invoices.py` ~244 | ✓ | ✓ | gesperrt, wird hier geöffnet |
| PDF-Knopf in der Liste | `Invoices.tsx` ~372 | ✓ | ✓ | fehlt, kommt in Task 15 |

**Entscheidung: Beide Belege stehen auf `STORNIERT`.** „Storniert“ bedeutet im System: Der Beleg nimmt an keinem Zahlungs-, Mahn- und Umsatzprozess mehr teil. Das gilt für beide Hälften des Paares. Die Stornorechnung bleibt trotzdem ein gültiger Beleg:
- Das PDF ist abrufbar (`GET /invoices/{id}/pdf`, in der Liste ab Task 15).
- Versenden geht **nur per API** (`POST /invoices/{id}/send`, Runbook R8). In der Oberfläche gibt es dafür keinen Weg: `Invoices.tsx` hat keinen Versandknopf, und `OrderDocumentsModal.tsx` (`:45`, `:106`) listet und versendet nur Rechnungen mit `order_id`. Die Stornorechnung hat keine (siehe S6).

Das Dashboard braucht keine Änderung, weil es nur `status=OFFEN` lädt.

Zusätzlich gibt es eine Absicherung für Altbestand, also eine Stornorechnung, die der alte Code auf `OFFEN` gesetzt hat:
- Beide Überfälligkeitsprüfungen lassen `GUTSCHRIFT` aus.
  - Der Service (`InvoiceService.check_overdue_invoices`) läuft über `GET /invoices/overdue`, das dabei auch `UEBERFAELLIG` schreibt. Das prüft `test_ueberfaellig_liste_ignoriert_alten_storno_auf_offen`.
  - Den geplanten Job (`invoice_tasks.check_overdue_invoices`) prüft `test_geplante_jobs_ignorieren_negative_belege`.
- Der Mahnlauf schickt nur, wenn `total > paid_amount` ist.

Die Überfälligkeit wird bewusst **nicht** über `total > paid_amount` geprüft. `test_gernot_260821.py:202-237` schreibt fest, dass eine 0-€-Rechnung auf `OFFEN` überfällig wird. Mit dieser Bedingung wurde der Test rot (gemessen).

Ein **Entwurf** bekommt keine Stornorechnung, denn er ging nie an den Kunden. Verwerfen bleibt mit `create_credit_note=false` möglich.

**Files:**
- Modify: `backend/app/services/invoice_service.py`: `cancel_invoice` (Prüfreihenfolge, Entwurf, `due_date`, Status) und `check_overdue_invoices` (~373-380)
- Modify: `backend/app/tasks/invoice_tasks.py`: Import Z. 12, `check_overdue_invoices` ~40-46, `send_payment_reminders` ~106-114
- Modify: `backend/app/api/v1/invoices.py`: `send_invoice_email` ~237-275
- Modify: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: Helfer aus Task 12.
- Produces:
  - Nach `POST /invoices/{id}/cancel` haben Original und Stornorechnung `status == "STORNIERT"`. Die Stornorechnung hat `due_date == invoice_date`.
  - Stornopaar = Original + Beleg mit `invoice_type == GUTSCHRIFT` und `original_invoice_id == Original.id`. **Das ist die Grundlage für S4 (DATEV).**
  - `POST /invoices/{id}/send` erlaubt den Versand einer Stornorechnung (Betreff „Stornorechnung …“, nur per API). Ein storniertes Original bleibt mit 400 gesperrt.
  - `POST /invoices/{id}/cancel` auf einen `ENTWURF` mit `create_credit_note=true` liefert 400.

- [ ] **Step 1: Tests anhängen**

```python
class TestS3StornoAusgeglichen:
    """Stornorechnung und Original gleichen sich aus und fallen aus
    Überfälligkeit, Mahnlauf, offenen Posten und Umsatz heraus."""

    def test_beide_belege_stehen_auf_storniert(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        antwort = _s3_storniere(client, original).json()

        assert antwort["invoice"]["status"] == "STORNIERT"
        storno = antwort["credit_note"]
        assert storno["status"] == "STORNIERT"
        assert storno["due_date"] == storno["invoice_date"]

    def _faelligkeit_in_der_vergangenheit(self, *ids):
        from app.models.invoice import Invoice
        with TestingSessionLocal() as db:
            for i in ids:
                db.get(Invoice, uuid.UUID(i)).due_date = date.today() - timedelta(days=30)
            db.commit()

    def _als_altbestand_offen(self, storno_id):
        """Stornorechnung so, wie der alte Code sie hinterließ: OFFEN, fällig."""
        from app.models.invoice import Invoice, InvoiceStatus
        with TestingSessionLocal() as db:
            alt = db.get(Invoice, uuid.UUID(storno_id))
            alt.status = InvoiceStatus.OFFEN
            alt.due_date = date.today() - timedelta(days=30)
            db.commit()

    def test_storno_ist_nie_ueberfaellig(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        storno = _s3_storniere(client, original).json()["credit_note"]
        self._faelligkeit_in_der_vergangenheit(original["id"], storno["id"])

        r = client.get("/api/v1/invoices/overdue")
        assert r.status_code == 200, r.text
        ids = {i["id"] for i in r.json()}
        assert original["id"] not in ids
        assert storno["id"] not in ids
        assert client.get(f"/api/v1/invoices/{storno['id']}").json()["status"] == "STORNIERT"

    def test_ueberfaellig_liste_ignoriert_alten_storno_auf_offen(self, client, sample_customer):
        """Altbestand über die API: GET /invoices/overdue ruft
        InvoiceService.check_overdue_invoices und schreibt UEBERFAELLIG."""
        original = _s3_altrechnung(client, sample_customer)
        storno = _s3_storniere(client, original).json()["credit_note"]
        self._als_altbestand_offen(storno["id"])

        r = client.get("/api/v1/invoices/overdue")
        assert r.status_code == 200, r.text
        assert storno["id"] not in {i["id"] for i in r.json()}
        assert client.get(f"/api/v1/invoices/{storno['id']}").json()["status"] == "OFFEN"

    def test_geplante_jobs_ignorieren_negative_belege(self, client, sample_customer):
        """Altbestand: eine Stornorechnung, die der alte Code auf OFFEN gesetzt hat,
        wird weder überfällig noch gemahnt."""
        from app.models.invoice import Invoice, InvoiceStatus
        from app.tasks.invoice_tasks import check_overdue_invoices, send_payment_reminders

        original = _s3_altrechnung(client, sample_customer)
        storno = _s3_storniere(client, original).json()["credit_note"]
        self._als_altbestand_offen(storno["id"])

        with patch("app.tasks.invoice_tasks.SessionLocal", return_value=TestingSessionLocal()):
            assert check_overdue_invoices()["newly_overdue"] == 0
        assert client.get(f"/api/v1/invoices/{storno['id']}").json()["status"] == "OFFEN"

        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(storno["id"])).status = InvoiceStatus.UEBERFAELLIG
            db.commit()
        mail = MagicMock()
        mail.send_email.return_value = True
        with patch("app.tasks.invoice_tasks.email_service", mail), \
             patch("app.tasks.invoice_tasks.SessionLocal", return_value=TestingSessionLocal()):
            assert send_payment_reminders()["reminders_sent"] == 0
        mail.send_email.assert_not_called()

    def test_weder_offener_posten_noch_umsatz(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        storno = _s3_storniere(client, original).json()["credit_note"]

        offen = {i["id"] for i in client.get("/api/v1/invoices", params={"status": "OFFEN"}).json()}
        assert storno["id"] not in offen and original["id"] not in offen

        heute = date.today().isoformat()
        summe = client.get("/api/v1/invoices/revenue-summary",
                           params={"from_date": heute, "to_date": heute}).json()
        # Paar hebt sich auf: kein Umsatz, nichts offen — vorher −17,84 Umsatz
        assert _s3_betrag(summe["total_revenue"]) == Decimal("0")
        assert _s3_betrag(summe["open_amount"]) == Decimal("0")

    def test_stornorechnung_kann_versendet_werden(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        storno = _s3_storniere(client, original).json()["credit_note"]

        gesendet = {}
        def _fake_send_email(**kwargs):
            gesendet.update(kwargs)
        with patch("app.api.v1.invoices.send_email", _fake_send_email):
            r = client.post(f"/api/v1/invoices/{storno['id']}/send",
                            params={"to_email": "kunde@example.com"})
            assert r.status_code == 200, r.text
            assert "Stornorechnung" in gesendet["subject"]
            assert original["invoice_number"] in gesendet["body"]
            assert "Fällig" not in gesendet["body"]
            assert gesendet["attachment_bytes"].startswith(b"%PDF")

            # das stornierte Original bleibt gesperrt
            r = client.post(f"/api/v1/invoices/{original['id']}/send",
                            params={"to_email": "kunde@example.com"})
            assert r.status_code == 400, r.text

        assert client.get(f"/api/v1/invoices/{storno['id']}").json()["status"] == "STORNIERT"

    def test_entwurf_bekommt_keine_stornorechnung(self, client, sample_customer):
        r = client.post("/api/v1/invoices", json={
            "customer_id": sample_customer["id"],
            "invoice_date": date.today().isoformat(),
            "lines": _S3_ZEILEN,
        })
        entwurf = r.json()

        r = _s3_storniere(client, entwurf)
        assert r.status_code == 400, r.text
        assert "Entwurf" in r.json()["detail"]

        r = _s3_storniere(client, entwurf, create_credit_note=False)
        assert r.status_code == 200, r.text
        assert r.json()["credit_note"] is None
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k TestS3StornoAusgeglichen`

Erwartet: alle sieben FAIL, und zwar so:
- `test_beide_belege_stehen_auf_storniert`: `'OFFEN' == 'STORNIERT'`
- `test_storno_ist_nie_ueberfaellig`: Die Storno-ID steht in der Überfällig-Liste.
- `test_ueberfaellig_liste_ignoriert_alten_storno_auf_offen`: Die Storno-ID steht in der Überfällig-Liste.
- `test_geplante_jobs_ignorieren_negative_belege`: `1 == 0`
- `test_weder_offener_posten_noch_umsatz`: Die Storno-ID steht unter `OFFEN`.
- `test_stornorechnung_kann_versendet_werden`: `'Stornorechnung' in 'Rechnung RE-… — Minga Greens'`
- `test_entwurf_bekommt_keine_stornorechnung`: `200 == 400`

- [ ] **Step 3: `cancel_invoice`: Prüfreihenfolge, Entwurf, Fälligkeit, Status**

In `backend/app/services/invoice_service.py`, `cancel_invoice`:

(a) In `cancel_invoice` alles vom Docstring (die Zeile `"""` direkt unter der Signatur) bis **ausschließlich** der Zeile `# Original stornieren` durch den folgenden Block ersetzen. Der Block enthält `invoice = self.db.get(...)` und `if not invoice: raise …` bereits; diese Zeilen dürfen danach nicht doppelt stehen. Die GUTSCHRIFT-Prüfung muss **vor** die STORNIERT-Prüfung, weil die Stornorechnung jetzt selbst auf STORNIERT steht. Sonst meldet `test_storno.py:83-87` „bereits storniert“ statt „Stornorechnung“.

```python
        """
        Storniert eine Rechnung und erstellt optional eine Stornorechnung.

        Die Stornorechnung ist das exakte Spiegelbild des Originals: gleiche
        Positionen mit negativer Menge, gleiche Steuersätze, Konten,
        Pfandkennzeichen und derselbe Rechnungsrabatt. Original und
        Stornorechnung gleichen sich aus und stehen danach beide auf
        STORNIERT — damit fallen sie aus Überfälligkeit, Mahnlauf, offenen
        Posten und Umsatzauswertungen heraus.
        """
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            raise ValueError("Rechnung nicht gefunden")

        # R1.7 vor der Statusprüfung: auch die Stornorechnung steht auf
        # STORNIERT, die Meldung soll trotzdem den eigentlichen Grund nennen.
        # Der Storno eines Stornos würde die Beträge wieder aufleben lassen —
        # der Weg ist eine neue, korrigierte Rechnung.
        if invoice.invoice_type == InvoiceType.GUTSCHRIFT:
            raise ValueError("Eine Stornorechnung kann nicht storniert werden")

        if invoice.status == InvoiceStatus.STORNIERT:
            raise ValueError("Rechnung ist bereits storniert")

        # Ein Entwurf ging nie an den Kunden — eine Stornorechnung dazu wäre
        # ein Beleg über nichts. Verwerfen geht nur ohne Stornorechnung.
        if invoice.status == InvoiceStatus.ENTWURF and create_credit_note:
            raise ValueError(
                "Ein Entwurf wurde nie ausgestellt und bekommt keine Stornorechnung — "
                "Entwurf korrigieren und finalisieren oder ohne Stornorechnung verwerfen"
            )
```

(b) Im `self.create_invoice(...)`-Aufruf der Stornorechnung nach `delivery_date=invoice.delivery_date,` ergänzen:

```python
                # Nichts zu zahlen: fällig am Ausstellungstag.
                due_date=date.today(),
```

(c) Die beiden Zeilen `# Status regelt Task 13` und `credit_note.status = InvoiceStatus.OFFEN` ersetzen durch:

```python
            # Ausgeglichen: STORNIERT ist der einzige bestehende Status, den
            # Überfälligkeit, Mahnlauf, offene Posten, Umsatzauswertungen,
            # Zahlungserfassung und lexoffice-Übertragung gleichermaßen
            # auslassen. PDF und Versand per API bleiben möglich
            # (invoices.py /pdf und /send).
            credit_note.status = InvoiceStatus.STORNIERT
```

`credit_note.sent_at = datetime.now(timezone.utc)` bleibt stehen. Das ist das bisherige Verhalten: `sent_at` wird ohne Mail gesetzt. Die Spec nennt das unter B2 („`sent_at` unzuverlässig“), es gehört zu Paket 3. Kein S3-Test schreibt `sent_at` fest.

- [ ] **Step 4: Überfälligkeit und Mahnlauf absichern**

`backend/app/services/invoice_service.py`, `check_overdue_invoices`. Das `.where(...)` wird zu:

```python
            .where(
                Invoice.status.in_(self.OVERDUE_STATES),
                Invoice.due_date < today,
                # Eine Gutschrift/Stornorechnung ist nie überfällig — auch
                # kein Altbestand, den der frühere Storno auf OFFEN setzte.
                Invoice.invoice_type != InvoiceType.GUTSCHRIFT,
            )
```

In `backend/app/tasks/invoice_tasks.py` Z. 12 durch die folgende Zeile ersetzen:

```python
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
```

In `check_overdue_invoices` (Task) wird das `.where(...)` zu:

```python
            .where(
                Invoice.status.in_([InvoiceStatus.OFFEN, InvoiceStatus.TEILBEZAHLT]),
                Invoice.due_date < today,
                # Eine Gutschrift/Stornorechnung ist nie überfällig — auch
                # kein Altbestand, den der frühere Storno auf OFFEN setzte.
                Invoice.invoice_type != InvoiceType.GUTSCHRIFT,
            )
```

In `send_payment_reminders` nach `Invoice.reminder_level < 3,` einfügen:

```python
                # Nie eine Mahnung über null oder einen negativen Betrag.
                Invoice.total > Invoice.paid_amount,
```

- [ ] **Step 5: Stornorechnung per API versendbar**

In `backend/app/api/v1/invoices.py`, `send_invoice_email`, genau zwei Stellen ändern. Die Zeilen **zwischen** `if not invoice.lines: raise HTTPException(...)` und `try:` bleiben unberührt. Dort steht seit Task 11 der Block mit dem Kommentar `# Mit dem Versand wird ein Entwurf ausgestellt …` und `if invoice.status == InvoiceStatus.ENTWURF: invoice.calculate_totals()`. Er muss erhalten bleiben.

(a) Die beiden Zeilen

```python
    if invoice.status == InvoiceStatus.STORNIERT:
        raise HTTPException(status_code=400, detail="Stornierte Rechnungen können nicht versendet werden")
```

ersetzen durch:

```python
    # Die Stornorechnung steht als ausgeglichener Beleg auf STORNIERT, muss
    # aber zum Kunden. Gesperrt ist nur das stornierte Original.
    ist_storno = (
        invoice.invoice_type == InvoiceType.GUTSCHRIFT
        and invoice.original_invoice_id is not None
    )
    if invoice.status == InvoiceStatus.STORNIERT and not ist_storno:
        raise HTTPException(status_code=400, detail="Stornierte Rechnungen können nicht versendet werden")
```

(b) In derselben Funktion die Zeilen von `    try:` (die Zeile direkt vor `        pdf = PDFService.generate_invoice_pdf(...)`) bis einschließlich der schließenden Klammer `        )` des `send_email(...)`-Aufrufs ersetzen. Die `except`-Zeilen danach bleiben. Neu:

```python
    try:
        pdf = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
        # Mailtext erst hier: ein Entwurf ist oben bereits neu berechnet (Task 11)
        if ist_storno:
            original = invoice.original_invoice
            betreff = f"Stornorechnung {invoice.invoice_number} — Minga Greens"
            text = (
                f"Sehr geehrte Damen und Herren bei {invoice.customer.name},\n\n"
                f"anbei finden Sie die Stornorechnung {invoice.invoice_number} zur Rechnung "
                f"{original.invoice_number if original else '—'}.\n"
                f"Die Rechnung ist damit vollständig aufgehoben.\n\n"
                f"Mit freundlichen Grüßen\nIhr Minga-Greens-Team"
            )
        else:
            betreff = f"Rechnung {invoice.invoice_number} — Minga Greens"
            text = (
                f"Sehr geehrte Damen und Herren bei {invoice.customer.name},\n\n"
                f"anbei finden Sie die Rechnung {invoice.invoice_number} über\n"
                f"{invoice.total:.2f} {invoice.currency}.\n\n"
                f"Fällig am: {invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else '—'}\n\n"
                f"Mit freundlichen Grüßen\nIhr Minga-Greens-Team"
            )
        send_email(
            db=db,
            to=to_email,
            subject=betreff,
            body=text,
            attachment_bytes=pdf,
            attachment_filename=f"{invoice.invoice_number}.pdf",
        )
```

Der Text der normalen Rechnung ist wortgleich mit heute; er wird nur erst im `try:` gebaut. So liest er `invoice.total` nach der Neuberechnung aus Task 11.

Die `except`-Zweige und der Rest der Funktion bleiben. `sent_at` wird gesetzt, und der Status bleibt `STORNIERT`, weil nur `ENTWURF` nach `OFFEN` wechselt. `InvoiceType` ist in `invoices.py` bereits importiert (Z. 13-16).

Kontrolle: `grep -n "calculate_totals\|ist_storno\|try:" backend/app/api/v1/invoices.py`. Ab der Zeile `ist_storno = (` stehen direkt hintereinander:
1. `ist_storno = (`
2. `if invoice.status == InvoiceStatus.STORNIERT and not ist_storno:`
3. `invoice.calculate_totals()` (Block aus Task 11)
4. `try:`
5. `if ist_storno:`

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k TestS3`

Erwartet: 11 passed.

- [ ] **Step 7: Nachbartests**

Run (dauert ca. 9-10 min; Kommando-Timeout entsprechend hoch setzen): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_storno.py tests/test_sammelrechnung.py tests/test_dunning.py tests/test_gernot_260821.py tests/test_lexoffice.py tests/test_gernot_261008.py -q`

Erwartet: kein FAIL, kein ERROR. Die ganze `test_gernot_261008.py` läuft mit, damit die Tests anderer Abschnitte in derselben Datei mitgeprüft werden. Besonders zu prüfen:
- `test_storno.py::TestStorno::test_storno_eines_stornos_wird_abgelehnt` (braucht die neue Prüfreihenfolge)
- `test_gernot_260821.py::TestUeberfaelligeRechnungen` (0-€-Rechnung bleibt überfällig)
- `test_gernot_261008.py::TestS2Mailversand::test_mailen_eines_altentwurfs_rechnet_vorher_neu`. Er wird rot, wenn Step 5 den Block aus Task 11 entfernt hat (Meldung `Decimal('1.03') == Decimal('1.04')`). Dann den Block wie in Task 11 Step 3 wieder zwischen `if not invoice.lines: raise …` und `try:` einsetzen.

Maßgeblich ist: kein FAIL, kein ERROR. Die Datei enthält hier auch die Tests von S1 und S2.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/invoice_service.py backend/app/tasks/invoice_tasks.py \
        backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "fix(storno): Stornopaar ist ausgeglichen — kein Mahnlauf, kein offener Posten, Stornorechnung versendbar"
```

---

### Task 14: Warnung bei (teil)bezahlter oder an lexoffice übertragener Rechnung; Stornogrund „Falscher Steuersatz“

**Befund zum Stornogrund:**
- Ein Freitext-Grund existiert schon: `InvoiceCancelRequest.reason`, Pflichtfeld mit `min_length=1` (`schemas/invoice.py` ~250).
- `reason_code` ist ein Pydantic-`Literal` und wird **nicht** als Spalte gespeichert. `invoices.py:288` schreibt ihn als `"[CODE] Freitext"` in `internal_notes` (Typ `Text`).
- Deshalb braucht die Erweiterung keine Migration und kein `_auto_migrate`.

**Files:**
- Modify: `backend/app/services/invoice_service.py`: Modulfunktion `_euro` vor `class InvoiceService`, Zahlungsvermerk in `cancel_invoice`, neue `staticmethod storno_warnungen`
- Modify: `backend/app/api/v1/invoices.py`: `cancel_invoice`-Endpoint ~278-300
- Modify: `backend/app/schemas/invoice.py`: `InvoiceCancelRequest.reason_code` ~251-254
- Modify: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces:
  - Die Antwort von `POST /invoices/{id}/cancel` bekommt das neue Feld `warnungen: list[str]` (leer, wenn nichts zu tun ist). Task 15 zeigt es an.
  - `InvoiceService.storno_warnungen(invoice: Invoice) -> list[str]`
  - `reason_code` akzeptiert jetzt auch `"FALSCHER_STEUERSATZ"`.
- Verhalten: Ist bei Storno schon Geld eingegangen, bleibt `paid_amount` am Original stehen. `internal_notes` des Originals erhält dann die Zeile `Bei Storno bereits gezahlt: X,XX € — auf die Neuausstellung umbuchen oder erstatten.` Eine automatische Umbuchung gibt es nicht. Zahlungen müssen > 0 sein (`schemas/invoice.py:82`), ein Ausgleich über eine negative Zahlung ist also unmöglich. Der manuelle Schritt steht im Runbook.

- [ ] **Step 1: Tests anhängen**

```python
class TestS3StornoWarnungenUndGrund:
    def test_storno_einer_teilbezahlten_rechnung_warnt(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        r = client.post(f"/api/v1/invoices/{original['id']}/payments", json={
            "invoice_id": original["id"], "payment_date": date.today().isoformat(),
            "amount": "5.00",
        })
        assert r.status_code == 201, r.text

        antwort = _s3_storniere(client, original).json()

        assert len(antwort["warnungen"]) == 1
        assert "5,00 €" in antwort["warnungen"][0]
        assert original["invoice_number"] in antwort["warnungen"][0]
        detail = client.get(f"/api/v1/invoices/{original['id']}").json()
        assert "bereits gezahlt: 5,00 €" in detail["internal_notes"]
        assert _s3_betrag(detail["paid_amount"]) == Decimal("5.00")

    def test_storno_ohne_zahlung_ohne_warnung(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)
        assert _s3_storniere(client, original).json()["warnungen"] == []

    def test_kopie_in_lexoffice_wird_gemeldet(self, client, sample_customer):
        from app.models.invoice import Invoice
        original = _s3_altrechnung(client, sample_customer)
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(original["id"])).lexoffice_id = "lex-123"
            db.commit()

        warnungen = _s3_storniere(client, original).json()["warnungen"]

        assert any("lexoffice" in w for w in warnungen)

    def test_stornogrund_falscher_steuersatz(self, client, sample_customer):
        original = _s3_altrechnung(client, sample_customer)

        r = _s3_storniere(client, original, reason_code="FALSCHER_STEUERSATZ",
                          reason="Pfand mit 7 % statt 19 % berechnet")
        assert r.status_code == 200, r.text

        orig = client.get(f"/api/v1/invoices/{original['id']}").json()
        sto = client.get(f"/api/v1/invoices/{r.json()['credit_note']['id']}").json()
        assert "[FALSCHER_STEUERSATZ]" in orig["internal_notes"]
        assert "[FALSCHER_STEUERSATZ]" in sto["internal_notes"]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -v -k TestS3StornoWarnungenUndGrund`

Erwartet: 4 FAIL. Drei davon mit `KeyError: 'warnungen'`. `test_stornogrund_falscher_steuersatz` scheitert mit `422 == 200` (`literal_error`).

- [ ] **Step 3: Service**

In `backend/app/services/invoice_service.py` direkt vor `class InvoiceService:` einfügen:

```python
def _euro(betrag: Decimal) -> str:
    """Betrag mit deutschem Dezimalkomma: Decimal("5") -> "5,00 €"."""
    return f"{Decimal(betrag):.2f} €".replace(".", ",")
```

In `cancel_invoice` direkt nach der Zeile `invoice.internal_notes = f"{invoice.internal_notes or ''}\n\nStorniert: {reason}".strip()` einfügen:

```python
        # Bereits eingegangenes Geld bleibt am stornierten Beleg stehen — es
        # gehört auf die Neuausstellung oder zurück an den Kunden. Das muss in
        # die Akte; die API meldet es zusätzlich (storno_warnungen).
        if invoice.paid_amount and invoice.paid_amount > 0:
            invoice.internal_notes += (
                f"\nBei Storno bereits gezahlt: {_euro(invoice.paid_amount)} — "
                "auf die Neuausstellung umbuchen oder erstatten."
            )
```

Direkt nach `cancel_invoice` (vor `OVERDUE_STATES`) einfügen:

```python
    @staticmethod
    def storno_warnungen(invoice: Invoice) -> list[str]:
        """Was der Storno nicht selbst lösen kann — die Oberfläche zeigt es an."""
        warnungen = []
        if invoice.paid_amount and invoice.paid_amount > 0:
            warnungen.append(
                f"Auf {invoice.invoice_number} sind bereits {_euro(invoice.paid_amount)} gezahlt. "
                "Die Zahlung bleibt am stornierten Beleg stehen — bei der Neuausstellung "
                "als Zahlung erfassen oder dem Kunden erstatten."
            )
        if invoice.lexoffice_id:
            warnungen.append(
                f"{invoice.invoice_number} wurde an lexoffice übertragen. Dort von Hand "
                "stornieren bzw. den Entwurf löschen — die Stornorechnung wird nicht übertragen."
            )
        return warnungen
```

Das ist kein Umbau der lexoffice-Anbindung, nur ein Hinweis. `lexoffice_service.py` bleibt unverändert.

- [ ] **Step 4: Endpoint und Schema**

In `backend/app/api/v1/invoices.py`, Endpoint `cancel_invoice`:
- Den Docstring ersetzen durch `"""Storniert eine Rechnung und erstellt optional eine Stornorechnung.\n\n    `warnungen` nennt, was der Storno nicht selbst lösen kann (bereits\n    gezahltes Geld, Kopie in lexoffice) — die Oberfläche zeigt sie an.\n    """`.
- Das Rückgabe-Dict ergänzen:

```python
        return {
            "invoice": InvoiceResponse.model_validate(invoice),
            "credit_note": InvoiceResponse.model_validate(credit_note) if credit_note else None,
            "warnungen": service.storno_warnungen(invoice),
        }
```

In `backend/app/schemas/invoice.py`, `InvoiceCancelRequest`:

```python
    reason_code: Optional[Literal[
        "FALSCHER_EMPFAENGER", "FALSCHE_MENGE", "PREISFEHLER",
        "FALSCHER_STEUERSATZ", "LIEFERUNG_NICHT_ERFOLGT", "SONSTIGES",
    ]] = Field(None, description="Stornogrund aus der Auswahlliste")
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_storno.py tests/test_sammelrechnung.py -v -k "TestS3 or TestStorno or Lieferschein or storno"`

Erwartet: Alle 15 S3-Tests und die Storno-/Sammelrechnungstests sind grün.

- [ ] **Step 6: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/invoice_service.py backend/app/api/v1/invoices.py \
        backend/app/schemas/invoice.py backend/tests/test_gernot_261008.py
git commit -m "feat(storno): Warnung bei bezahlter oder an lexoffice übertragener Rechnung; Grund 'Falscher Steuersatz'"
```

---

### Task 15: Oberfläche: Warnung im Storno-Dialog, neuer Grund, PDF der Storno-Belege, Bezeichnung „Stornorechnung“

**Files:**
- Modify: `frontend/src/types/index.ts`: `interface Invoice` (~594-628)
- Modify: `frontend/src/services/api.ts`: `invoicesApi.cancel` (~741-742)
- Modify: `frontend/src/pages/Invoices.tsx`: UI-Import (~7-18), `stornoMutation` (~133-145), Typ-Spalte (~341), PDF-Knopf (~372), Storno-Modal (~543-573)

**Interfaces:**
- Consumes: `warnungen` aus Task 14, `original_invoice_id` aus `InvoiceResponse` (existiert bereits im Backend).
- Produces:
  - In der Liste heißt eine `GUTSCHRIFT` mit `original_invoice_id` „Stornorechnung“.
  - Der PDF-Knopf erscheint auch bei `STORNIERT`, für die Stornorechnung und das Original (Akte).
  - Der Storno-Dialog warnt vor dem Absenden, wenn bereits gezahlt wurde. Nach dem Storno erscheinen die Server-Warnungen als `toast.warning` (15 s).

- [ ] **Step 1: Typ**

`frontend/src/types/index.ts`, `interface Invoice`, nach `order_id: string | null` einfügen:

```ts
  /** Gesetzt bei einer Stornorechnung: die stornierte Originalrechnung */
  original_invoice_id?: string | null
```

- [ ] **Step 2: API-Typisierung**

`frontend/src/services/api.ts`, in `invoicesApi`:

```ts
  cancel: (id: string, data: { reason: string; reason_code?: string; create_credit_note?: boolean }) =>
    api.post<{ invoice: Invoice; credit_note: Invoice | null; warnungen: string[] }>(
      `/invoices/${id}/cancel`, data,
    ).then(r => r.data),
```

- [ ] **Step 3: `Invoices.tsx`**

(a) In der Import-Liste aus `'../components/ui'` nach `Pagination,` die Zeile `Alert,` ergänzen. `Alert` wird in `components/ui/index.ts:12` exportiert.

(b) In `stornoMutation` das `as any` und das `res: any` entfernen und nach dem Erfolgs-Toast die Warnungen zeigen:

```tsx
    mutationFn: () => invoicesApi.cancel(stornoFuer!.id, {
      reason: stornoGrund,
      reason_code: stornoGrundCode,
    }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      setStornoFuer(null);
      setStornoGrund('');
      toast.success(`Stornorechnung ${res.credit_note?.invoice_number ?? ''} erstellt — Lieferscheine sind wieder abrechenbar`);
      // Was der Storno nicht selbst löst (gezahltes Geld, lexoffice) — lange stehen lassen
      if (res.warnungen?.length) toast.warning(res.warnungen.join(' '), 15000);
    },
```

(c) In der Typ-Spalte ersetzt man `<div className="text-xs text-gray-500 dark:text-gray-400">{TYPE_LABELS[invoice.invoice_type]}</div>` durch:

```tsx
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {invoice.invoice_type === 'GUTSCHRIFT' && invoice.original_invoice_id
                        ? 'Stornorechnung'
                        : TYPE_LABELS[invoice.invoice_type]}
                    </div>
```

(d) Für den PDF-Knopf (der mit `icon={<Download className="w-4 h-4" />}`) die Bedingung auf `['OFFEN', 'TEILBEZAHLT', 'UEBERFAELLIG', 'BEZAHLT', 'STORNIERT'].includes(invoice.status)` erweitern. Die gleichlautenden Bedingungen für „Stornieren“ und „→ lexoffice“ **nicht** ändern.

(e) Im Storno-Modal den Erklärtext ergänzen und die Warnung davor setzen:

```tsx
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Es wird eine <b>Stornorechnung mit eigener Nummer</b> erzeugt; das Original
            bleibt erhalten und wird schreibgeschützt. Zugeordnete Lieferscheine werden
            wieder abrechenbar. Original und Stornorechnung gleichen sich aus und stehen
            danach beide auf „Storniert“.
          </p>
          {stornoFuer && Number(stornoFuer.paid_amount) > 0 && (
            <Alert variant="warning" title="Auf diese Rechnung wurde schon gezahlt">
              {Number(stornoFuer.paid_amount).toFixed(2).replace('.', ',')} € sind bereits verbucht.
              Die Zahlung bleibt am stornierten Beleg stehen — bei der Neuausstellung als
              Zahlung erfassen oder dem Kunden erstatten.
            </Alert>
          )}
```

`Number(...)` ist nötig: Beträge kommen als JSON-String (gemessen: `"total": "10.70"`).

(f) In den Grund-Optionen nach `{ value: 'PREISFEHLER', label: 'Preisfehler' },` einfügen:

```tsx
                    { value: 'FALSCHER_STEUERSATZ', label: 'Falscher Steuersatz' },
```

- [ ] **Step 4: Typprüfung**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p tsconfig.json`

Erwartet: keine Ausgabe, Exit 0. Auf `main` ist der Lauf heute sauber, und mit genau diesen Änderungen wurde er gemessen. Kein `npm install` nötig, `node_modules` liegt vor.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api.ts frontend/src/pages/Invoices.tsx
git commit -m "feat(rechnungen): Storno-Dialog warnt bei Zahlung, Grund 'Falscher Steuersatz', PDF für stornierte Belege"
```

---

## Abschnitt S4: DATEV-Export bucht richtig und lässt sich wiederholen — Tasks 16–19

> **Kennzeichnung:** Die Kontierungslogik dieses Abschnitts (Konto/Gegenkonto, Soll/Haben, Bruttobuchung auf Automatikkonten, Storno-Behandlung) **muss vor der ersten Produktivnutzung vom Steuerberater bestätigt werden.** Bis dahin gilt die Sofortmaßnahme 1 der Spec weiter: kein DATEV-Export. Der **EXTF-Kopf** (Berater-/Mandantennummer, WJ-Beginn, Sachkontenlänge) und PDF-Anhänge sind **nicht** Teil dieses Pakets; die CSV behält den heutigen vereinfachten 12-Spalten-Kopf.

**Einordnung:**
- **Hart: Task 8.** S4 rechnet mit `app.models.invoice.steuer_je_satz(lines, discount_percent)`; auf derselben Funktion bauen `Invoice.calculate_totals` (`total`) und `Invoice.get_tax_summary` (Steuerausweis) auf. Nur so ergibt die Summe der DATEV-Zeilen einer Rechnung genau ihr `total`. `datev_service.py` importiert `steuer_je_satz`; ohne Task 8 lädt schon `tests/conftest.py` nicht. Task 16 Step 0 prüft das. Warum nicht die alte Rundung von `get_tax_summary` nachbauen: Sie zieht den Rabatt ungerundet ab. Bei 1 × 22,15 € zu 7 % mit 10 % Kundenrabatt ergibt das 19,94 + 1,40 = 21,34 €, die Rechnung lautet aber 21,33 € (Rabatt 2,22, Entgelt 19,93, USt 1,40); `test_rundungsgrenze_rabatt_wie_rechnungsbetrag` sichert genau diese Grenze.
- **S3 ist umgesetzt** (Tasks 12–14). Die Stornorechnung steht auf `STORNIERT` und wird trotzdem exportiert, weil sie eine `GUTSCHRIFT` mit `original_invoice_id` ist — dieselbe Definition wie `ist_storno` in Task 13. Gutschriften buchen unabhängig vom Vorzeichen der Mengen auf H. Wird ein S4-Test rot, ist das ein inhaltlicher Befund: stoppen und melden.
- **S1 wirkt nicht auf die S4-Tests:** Sie verwenden nur Freitextpositionen ohne `product_id`, bei denen der Satz vom Client gilt (`tests/test_gernot_260821.py:486-504`).
- **Gemeinsame Erlöskonto-Regel:** Task 16 legt in `datev_service` neben `erloeskonto(line)` die Funktionen `erloeskonto_fuer(tax_rate)` und `ist_standard_erloeskonto(konto)` an. Task 25 importiert sie für `add_line` und den Satzwechsel im Entwurf. Die Regel „Standardkonten 8300/8400/8100 folgen dem Satz, ein Sonderkonto bleibt" steht damit an einer Stelle.
- **Testdatei:** Helfer `_datev_…`, Klassen `TestDatev…`.
- **Zeilennummern** beziehen sich auf `c4a1832`. S1–S3 ändern `models/invoice.py`, `invoice_service.py`, `api/v1/invoices.py`, `api.ts` und `Invoices.tsx` oberhalb der Anker (z. B. `Invoices.tsx` nach Task 15 um etwa +9 bis +16 Zeilen, `api.ts` um etwa +2; in `models/invoice.py` steht `STANDARD_ACCOUNTS` nach Task 8 auf `:398` statt `:381`). **Weicht eine Zeilenangabe ab, nach dem zitierten Inhalt suchen**; jeder Anker ist zusätzlich als Code zitiert und in der Datei eindeutig.

### Ausgangsbefund (am Code geprüft, `main` @ `c4a1832`)

`backend/app/services/datev_service.py::DatevService.export_invoices_csv` heute:

| # | Fehler | Stelle | Wirkung |
|---|---|---|---|
| 1 | Zeile „Gesamtbetrag, S, Konto 1400, Gegenkonto Debitor" | `:79-94` | 1400 im Soll, Debitor im Haben: die Forderung wird gutgeschrieben statt begründet |
| 2 | `invoice.buchungskonto` überschreibt das Erlöskonto je Satz | `:112-115`; Kopf-Default 8300 in `backend/app/services/invoice_service.py:102` | jede Rechnung trägt 8300 im Kopf → 19 % landen auf dem 7-%-Automatikkonto. `InvoiceLine.buchungskonto` (je Satz korrekt aus `add_line`, `invoice_service.py:141-147`) wird ignoriert |
| 3 | Erlöszeile hat 13 statt 12 Felder (`customer_account` zu viel) | `:117-162` | ab Spalte 6 verschoben: Konto = Debitor, Gegenkonto = Erlös, **BU-Schlüssel = Debitorennummer**, Belegdatum leer, Belegfeld 1 = Datum |
| 4 | Stornorechnung mit negativem Umsatz | `:100`, `:118` | DATEV erwartet positiven Umsatz, Richtung über S/H (gemessen: `-26,75;H;…`) |
| 5 | Stornierte Rechnungen ohne Gegenbeleg werden exportiert; ebenso Proforma | Filter `:36-44` nur `status != ENTWURF` | Umsatz ohne Gegenbuchung |
| 6 | Jeder Aufruf setzt `datev_exported = True`, kein Weg zurück | `:167-168`, `:206`; beide Routen committen (`backend/app/api/v1/invoices.py:431`, `:454`) | verlorene oder zurückgewiesene Datei nicht wiederholbar |
| 7 | Eine bereits exportierte Rechnung lässt sich ohne Stornorechnung stornieren | `InvoiceService.cancel_invoice` (`invoice_service.py:285-351`), `POST /invoices/{id}/cancel` mit `create_credit_note=false` | gemessen: 200; ab dann fällt die Rechnung aus jedem Export, ihr Umsatz bleibt in DATEV still stehen |

Gemessen in einer Kopie: gemischte Rechnung (25,00 € zu 7 % + 6,00 € zu 19 %) erzeugt heute
`33,89;S;EUR;;;1400;10008;;0810;RE-2026-00001;;Rechnung Ökoring Testkunde`, danach zwei 13-Felder-Zeilen mit `H` und Konto 8300 für beide Sätze.

### Entscheidungen und Begründung

1. **Eine Zeile je (Rechnung, Steuersatz, Erlöskonto).** Konto = Debitor, Gegenkonto = Erlöskonto, Umsatz = Brutto der Gruppe, BU-Schlüssel leer. 8300/8400 sind in SKR03 Automatikkonten; DATEV rechnet die USt aus dem Brutto heraus. Keine Zeile auf 1400: das Sammelkonto Forderungen führt DATEV aus den Personenkonten selbst. **Beträge nach der einen Rechenregel aus S2** (`steuer_je_satz`), angewandt je Erlöskonto. Teilen sich mehrere Konten einen Satz (Sonderkonto einer Position neben dem Standardkonto), rundet jedes Konto für sich; den Rest-Cent gegenüber dem Steuerausweis des Satzes trägt die betragsgrößte Gruppe des Satzes. Damit ergeben die Zeilen je Satz immer den Steuerausweis und zusammen den Rechnungsbetrag (Beispiel im Test `test_sonderkonto_neben_standardkonto_rest_cent`: 24,08 + 21,33 = 45,41 je Konto gerundet, Steuerausweis 45,40 → 24,07 + 21,33).
2. **Erlöskonto je Position, nicht aus dem Kopf.** `erloeskonto(line)`: die drei Standardkonten (8300/8400/8100) folgen immer dem Steuersatz der Position — ändert ein PATCH (`invoices.py:327-356`, `update_invoice_line`) den Satz eines Entwurfs, bleibt das in `add_line` gesetzte Konto sonst stehen (in der Kopie nachgestellt). Ein ausdrücklich gesetztes Sonderkonto bleibt erhalten. Dieselbe Regel (`erloeskonto_fuer`, `ist_standard_erloeskonto` in `datev_service`) zieht beim Satzwechsel im Entwurf das Konto nach (Task 25). `Invoice.buchungskonto` wird vom Export nicht mehr gelesen; der Default 8300 in `create_invoice` entfällt. **Keine Datenkorrektur nötig:** Bestandsrechnungen behalten 8300 im Kopf, das ist danach wirkungslos; Rechnungszeilen werden nicht angefasst (GoBD). `InvoiceCreate.buchungskonto` und `InvoiceUpdate.buchungskonto` bleiben in der API und sind danach wirkungslos. Ob im Mandanten bewusst gesetzte Kopfkonten ≠ 8300 existieren, prüft die Abfrage unter „Abnahme S4“ vor dem Deploy (Offener Punkt 11).
3. **Spaltenzahl == Kopf.** Kopf unverändert (12 Spalten), jede Zeile genau 12 Felder; Tests prüfen jede Zeile spaltengenau.
4. **Gutschrift → H, Umsatz ohne Vorzeichen.** Eine `GUTSCHRIFT` mindert immer: die Stornorechnung (negative Mengen aus `cancel_invoice`) ebenso wie eine von Hand angelegte Gutschrift (Formular erlaubt Typ GUTSCHRIFT, Positionen sind per Schema immer positiv, `schemas/invoice.py:37`). Eine `RECHNUNG` bucht S. Buchungstext der Stornorechnung nennt die Originalnummer.
5. **Storno: beide Belege exportieren, nie nur einen.** Original und Stornorechnung sind beide Belege mit Nummer aus dem lückenlosen Kreis; zusammen heben sie sich in DATEV auf (S und H). Eine **Stornorechnung** ist eine `GUTSCHRIFT` mit `original_invoice_id`; sie wird unabhängig von ihrem Status exportiert (S3 setzt sie auf `STORNIERT`). Ausgeschlossen werden:
   - eine stornierte `RECHNUNG`, zu der **keine** Stornorechnung existiert — z. B. `cancel_invoice(create_credit_note=False)` oder ein per `PATCH /invoices/{id}` (`InvoiceUpdate.status`) auf STORNIERT gesetzter Entwurf. Ohne Gegenbeleg würde DATEV Umsatz buchen, den es nie gab;
   - eine von Hand angelegte `GUTSCHRIFT` (ohne `original_invoice_id`) auf `STORNIERT`, also ein per PATCH verworfener Entwurf. Den Weg gibt es nur über die API;
   - `PROFORMA` (kein Buchungsbeleg) und `ABSCHLAG` (eigene Kontierung, in der Oberfläche nicht anlegbar).

   Die Variante „Original und Storno gar nicht exportieren" ist verworfen: sie reißt Lücken in die Belegnummern in DATEV und versagt, wenn das Original schon exportiert war. **Nach dem Export** ist ein Storno ohne Stornorechnung gesperrt (`cancel_invoice` meldet einen Fehler): die Rechnung fiele sonst aus jedem weiteren Export, ihr Umsatz bliebe in DATEV stehen. Die Oberfläche sendet `create_credit_note` nie (Default `True`), sie ist nicht betroffen.
6. **Wiederholungsexport per Parameter `erneut_exportieren`.** Der Export markiert weiter, aber genau die Belege, die in der Datei stehen, in derselben Transaktion. `erneut_exportieren=True` nimmt bereits exportierte Rechnungen **und** Zahlungen im Zeitraum wieder auf; `datev_export_date` zeigt danach den letzten Export. Verworfen: „Export markiert nicht, Bestätigung markiert". Der zweite Schritt kann vergessen werden (dann landet derselbe Zeitraum beim nächsten Lauf wieder in der Datei → Doppelimport), und die Bestätigung müsste die exakte Liste der exportierten IDs zurückschicken, sonst markiert sie eine in der Zwischenzeit angelegte Rechnung mit, die nie in einer Datei stand. Der Parameter behält den heutigen Schutz gegen versehentlichen Doppelexport und macht die Wiederholung zur ausdrücklichen Handlung mit Warnhinweis in der Oberfläche.

### Kontierungsregel (vom Steuerberater zu bestätigen)

| Beleg | Umsatz | S/H | Konto | Gegenkonto | BU | Belegdatum | Belegfeld 1 | Buchungstext |
|---|---|---|---|---|---|---|---|---|
| Rechnung, je Satz | Brutto des Satzes, positiv | S | Debitor (`customers.datev_account`, sonst 10000) | 8300 (7 %), 8400 (19 %), 8100 (0 %) bzw. Sonderkonto der Position | leer | `DDMM` | Rechnungsnummer | `Rechnung 7 % <Kunde>` |
| Stornorechnung, je Satz | Brutto des Satzes, ohne Vorzeichen | H | Debitor | wie oben | leer | `DDMM` | Nummer der Stornorechnung | `Storno <Originalnr.> 7 % <Kunde>` |
| Gutschrift von Hand | wie Stornorechnung | H | Debitor | wie oben | leer | `DDMM` | Nummer | `Gutschrift 7 % <Kunde>` |
| Zahlung (unverändert) | Betrag | S | 1200 Bank / 1000 Kasse | Debitor | leer | `DDMM` | Rechnungsnummer | `Zahlung <Kunde>` |

Buchungstext auf 60 Zeichen gekürzt. Brutto je (Konto, Satz) nach der Rechenregel aus S2 (`steuer_je_satz`): Rabatt je Satz auf den Cent runden, Entgelt = Netto − Rabatt, USt auf das gerundete Entgelt je Satz runden; Brutto = Entgelt + USt. Teilen sich mehrere Konten einen Satz, trägt die betragsgrößte Gruppe den Rest-Cent, sodass die Zeilen je Satz genau dem Steuerausweis (`get_tax_summary`) entsprechen.

**Prüfstand:** Der gesamte Plan-Code dieses Abschnitts wurde in zwei Kopien von `backend/` (außerhalb des Repos, `c4a1832` + S2 bzw. `c4a1832` + S2 + S3-Storno-Diff) wörtlich durchgespielt: Rot/Grün je Task wie unten angegeben, mit den dort genannten Zahlen. Vollauf in der Kopie mit S2 + S3 (je ca. 20 min): vor S4 14 failed / 502 passed / 2 skipped / 1 error, nach Tasks 16–18 14 failed / 524 passed / 2 skipped / 1 error; die Fehlerliste ist identisch (verglichen mit dem Befehl aus Task 16 Step 0 und Step 8). Gegenüber der Baseline auf `c4a1832` (15 failed) fehlt dort `test_services.py::TestInvoiceService::test_invoice_totals_update`, den S3 grün macht — deshalb vergleicht dieser Abschnitt gegen die Fehlerliste vor Task 16, nicht gegen die Baseline-Zahl. Die Frontend-Änderungen aus Task 19 sind unverändert gegenüber der geprüften Fassung (`tsc --noEmit` ohne Fehler).

---

### Task 16: Eine Buchungszeile je Rechnung und Erlöskonto, Richtung über S/H

**Files:**
- Modify: `backend/app/services/datev_service.py:1-13` (Imports → Modulkopf mit Helfern) und `:46-168` (Zeilenaufbau in `export_invoices_csv`)
- Modify: `backend/app/services/invoice_service.py:102` (`create_invoice`)
- Modify: `backend/tests/test_datev_export.py:84-95`
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `steuer_je_satz(lines, discount_percent) -> list[dict]` aus `app.models.invoice` (S2; Schlüssel `rate`, `percent`, `netto_vor_rabatt`, `rabatt`, `base`, `tax`), `Invoice.lines`, `InvoiceLine.line_total`, `InvoiceLine.tax_rate`, `InvoiceLine.buchungskonto`, `Invoice.discount_percent`, `Invoice.invoice_type`, `Invoice.original_invoice`, `Customer.datev_account`, `STANDARD_ACCOUNTS` (`backend/app/models/invoice.py:381-388`, nach S2 `:398-405`), `TaxRate.rate`/`.percent` (`backend/app/models/enums.py:4-28`).
- Produces (Modulebene `app.services.datev_service`):
  - `DATEV_KOPF: list[str]` (12 Spalten, Reihenfolge wie heute)
  - `SAMMELDEBITOR = "10000"`, `ERLOESKONTO_JE_SATZ: dict[TaxRate, str]`, `EXPORTIERBARE_TYPEN` (genutzt ab Task 17)
  - `erloeskonto(line: InvoiceLine) -> str`
  - `erloeskonto_fuer(tax_rate: TaxRate) -> str` (Standardkonto zum Satz: 8300 / 8400 / 8100, unbekannt 8300) und `ist_standard_erloeskonto(konto: Optional[str]) -> bool` (leer oder eines der drei Standardkonten) — die gemeinsame Erlöskonto-Regel; `erloeskonto` nutzt beide, Task 25 importiert beide.
  - `erloesgruppen(invoice: Invoice) -> list[dict]` mit Schlüsseln `satz` (TaxRate), `konto`, `netto`, `steuer`, `brutto` (Decimal, mit Vorzeichen), sortiert nach (Konto, Satz). Σ `netto` je Satz == `base` und Σ `steuer` je Satz == `tax` aus `steuer_je_satz(invoice.lines, invoice.discount_percent)`.
  - `_betrag`, `_richtung`, `_debitor` (intern)
  - Test-Helfer `DATEV_KOPF`, `DATEV_GEMISCHT`, `_datev_kunde`, `_datev_rechnung`, `_datev_export`, `_datev_zeile` in `test_gernot_261008.py`, die Task 17 und Task 18 wiederverwenden. `_datev_rechnung` nimmt Positionen als `(Beschreibung, Menge, Preis, Satz)` oder mit fünftem Feld Sonderkonto. `_datev_export(..., erneut=...)` sendet `erneut_exportieren` bereits mit; bis Task 18 ignoriert die API das Feld (Pydantic ignoriert Unbekanntes).

- [ ] **Step 0: Vorbedingung Task 8**

Run: `cd backend && grep -n "^def steuer_je_satz" app/models/invoice.py`
Erwartet: genau ein Treffer. **Kein Treffer → S2 ist nicht umgesetzt: stoppen und melden.** Nicht selbst nachbauen, nicht die Rundung in diesem Abschnitt ändern.

Die Fehlerliste für die Volläufe dieses Abschnitts steht seit der Vorbereitung in `/tmp/paket1-fehler-baseline.txt` (Prozedur V).

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_gernot_261008.py` anhängen (Kopf aus Task 1):

```python
# ---------------------------------------------------------------------------
# S4: DATEV-Export
# ---------------------------------------------------------------------------

DATEV_KOPF = [
    "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
    "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
    "Belegfeld 1", "Belegfeld 2", "Buchungstext",
]

#: Gemischte Rechnung wie RE-00002: Ware zu 7 %, Pfandkiste zu 19 %.
#: 10 × 2,50 = 25,00 netto + 1,75 USt = 26,75 | 2 × 3,00 = 6,00 netto + 1,14 USt = 7,14
DATEV_GEMISCHT = [
    ("Erbsen-Schale", 10, "2.50", "REDUZIERT"),
    ("Pfandkiste 6er", 2, "3.00", "STANDARD"),
]


def _datev_kunde(client, name="Ökoring Testkunde", konto="10008", rabatt=None):
    body = {"name": name, "typ": "HANDEL"}
    if konto is not None:
        body["datev_account"] = konto
    if rabatt is not None:
        body["discount_percent"] = rabatt
    r = client.post("/api/v1/sales/customers", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _datev_rechnung(client, kunde, positionen, typ="RECHNUNG", finalisieren=True, **kopf):
    """positionen: (Beschreibung, Menge, Preis, Satz[, Sonderkonto])."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": date.today().isoformat(),
        "invoice_type": typ, **kopf,
    })
    assert r.status_code == 201, r.text
    rechnung = r.json()
    for beschreibung, menge, preis, satz, *sonderkonto in positionen:
        zeile = {
            "description": beschreibung, "quantity": menge, "unit": "STK",
            "unit_price": preis, "tax_rate": satz,
        }
        if sonderkonto:
            zeile["buchungskonto"] = sonderkonto[0]
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=zeile)
        assert r.status_code == 201, r.text
    if finalisieren:
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text
        rechnung = r.json()
    return rechnung


def _datev_export(client, erneut=None, zahlungen=False):
    body = {
        "from_date": date.today().isoformat(), "to_date": date.today().isoformat(),
        "include_payments": zahlungen,
    }
    if erneut is not None:
        body["erneut_exportieren"] = erneut
    r = client.post("/api/v1/invoices/datev-export", json=body)
    assert r.status_code == 200, r.text
    daten = r.json()
    zeilen = list(csv.reader(io.StringIO(daten["csv_content"]), delimiter=";"))
    return daten, zeilen[0], zeilen[1:]


def _datev_zeile(betrag, sh, konto, gegenkonto, belegnr, text):
    """Eine erwartete Buchungszeile, Spalte für Spalte in Kopf-Reihenfolge."""
    return [betrag, sh, "EUR", "", "", konto, gegenkonto, "",
            date.today().strftime("%d%m"), belegnr, "", text]
```

Dann die beiden Klassen anhängen:

```python
class TestDatevKontierung:
    """Je Rechnung und Erlöskonto eine Zeile: Debitor an Erlös, Richtung über S/H."""

    def test_gemischte_rechnung_spaltengenau(self, client):
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        nr = rechnung["invoice_number"]

        daten, kopf, zeilen = _datev_export(client)

        assert kopf == DATEV_KOPF
        assert zeilen == [
            _datev_zeile("26,75", "S", "10008", "8300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _datev_zeile("7,14", "S", "10008", "8400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert daten["record_count"] == 2
        assert Decimal(str(daten["total_amount"])) == Decimal("33.89")

    def test_jede_zeile_hat_so_viele_felder_wie_der_kopf(self, client):
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        client.post(f"/api/v1/invoices/{rechnung['id']}/payments", json={
            "invoice_id": rechnung["id"], "amount": "33.89",
            "payment_date": date.today().isoformat(),
        })

        _, kopf, zeilen = _datev_export(client, zahlungen=True)

        assert len(zeilen) == 3
        assert all(len(z) == len(kopf) for z in zeilen)

    def test_kopfkonto_ueberschreibt_die_konten_je_satz_nicht(self, client):
        """Altbestand: jede Rechnung trägt im Kopf 8300. Der Export darf es nicht verwenden."""
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT, buchungskonto="8300")
        assert rechnung["buchungskonto"] == "8300"

        _, _, zeilen = _datev_export(client)

        assert [z[6] for z in zeilen] == ["8300", "8400"]

    def test_neue_rechnung_ohne_kopfkonto(self, client):
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT, finalisieren=False)
        assert rechnung["buchungskonto"] is None

    def test_konto_folgt_dem_steuersatz_der_position(self, client):
        """Ein nachträglich geänderter Satz darf nicht auf dem alten Standardkonto landen."""
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                                   finalisieren=False)
        zeile = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["lines"][0]
        assert zeile["buchungskonto"] == "8300"
        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})
        assert r.status_code == 200, r.text
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200

        _, _, zeilen = _datev_export(client)

        assert zeilen == [
            _datev_zeile("11,90", "S", "10008", "8400", rechnung["invoice_number"],
                         "Rechnung 19 % Ökoring Testkunde"),
        ]

    def test_rechnungsrabatt_wie_steuerausweis_der_rechnung(self, client):
        """Brutto je Satz = Entgelt + USt je Satz, so wie die Rechnung sie ausweist."""
        from app.models.invoice import Invoice
        kunde = _datev_kunde(client, rabatt="10")
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        nr = rechnung["invoice_number"]

        _, _, zeilen = _datev_export(client)

        # 25,00 − 2,50 = 22,50 + 1,58 USt = 24,08 | 6,00 − 0,60 = 5,40 + 1,03 USt = 6,43
        assert zeilen == [
            _datev_zeile("24,08", "S", "10008", "8300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _datev_zeile("6,43", "S", "10008", "8400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        with TestingSessionLocal() as db:
            ausweis = db.get(Invoice, uuid.UUID(rechnung["id"])).get_tax_summary()
        brutto_je_satz = sorted(f"{s['base'] + s['tax']:.2f}".replace(".", ",") for s in ausweis)
        assert sorted(z[0] for z in zeilen) == brutto_je_satz

    def test_rundungsgrenze_rabatt_wie_rechnungsbetrag(self, client):
        """Rechenregel aus S2 an einer Rundungsgrenze: 22,15 € zu 7 %, 10 % Rabatt.
        Rabatt 2,215 → 2,22, Entgelt 19,93, USt 1,3951 → 1,40, zusammen 21,33.
        Den Rabatt ungerundet abziehen ergäbe 19,935 → 19,94 + 1,40 = 21,34 —
        beim Debitor bliebe 1 ct offen."""
        kunde = _datev_kunde(client, rabatt="10")
        rechnung = _datev_rechnung(client, kunde, [("Erbsen-Schale", 1, "22.15", "REDUZIERT")])
        assert Decimal(str(rechnung["total"])) == Decimal("21.33")

        daten, _, zeilen = _datev_export(client)

        assert zeilen == [
            _datev_zeile("21,33", "S", "10008", "8300", rechnung["invoice_number"],
                         "Rechnung 7 % Ökoring Testkunde"),
        ]
        assert Decimal(str(daten["total_amount"])) == Decimal(str(rechnung["total"]))

    def test_sonderkonto_neben_standardkonto_rest_cent(self, client):
        """Teilen sich zwei Konten einen Satz, rundet jedes Konto für sich:
        25,00 → 22,50 + 1,58 = 24,08 und 22,15 → 19,93 + 1,40 = 21,33, zusammen 45,41.
        Der Steuerausweis zu 7 % lautet 47,15 − 4,72 = 42,43 + 2,97 = 45,40.
        Den Rest-Cent trägt die betragsgrößte Gruppe (8300): 24,07."""
        kunde = _datev_kunde(client, rabatt="10")
        rechnung = _datev_rechnung(client, kunde, [
            ("Erbsen-Schale", 10, "2.50", "REDUZIERT"),
            ("Kresse Sonderaktion", 1, "22.15", "REDUZIERT", "8301"),
        ])
        nr = rechnung["invoice_number"]
        assert Decimal(str(rechnung["total"])) == Decimal("45.40")

        daten, _, zeilen = _datev_export(client)

        assert zeilen == [
            _datev_zeile("24,07", "S", "10008", "8300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _datev_zeile("21,33", "S", "10008", "8301", nr, "Rechnung 7 % Ökoring Testkunde"),
        ]
        assert Decimal(str(daten["total_amount"])) == Decimal(str(rechnung["total"]))

    def test_summe_der_zeilen_gleich_rechnungsbetrag(self, client):
        """Der Debitor bekommt in DATEV genau den Rechnungsbetrag — sonst bleibt
        nach Zahlung ein Cent offen. Wächter: schon vor Task 16 grün (der alte
        Export summierte invoice.total); nach Task 16 grün, weil Export und
        calculate_totals dieselbe Rechenregel steuer_je_satz (S2) nutzen."""
        kunde = _datev_kunde(client, rabatt="10")
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)

        daten, _, _ = _datev_export(client)

        assert Decimal(str(daten["total_amount"])) == Decimal(str(rechnung["total"]))

    def test_ohne_debitorenkonto_sammeldebitor(self, client):
        kunde = _datev_kunde(client, konto=None)
        _datev_rechnung(client, kunde, [("Kresse", 1, "10.00", "REDUZIERT")])

        _, _, zeilen = _datev_export(client)

        assert [z[5] for z in zeilen] == ["10000"]

    def test_export_aendert_keinen_beleg(self, client):
        """GoBD: der Export liest. Nur die DATEV-Kennzeichen dürfen sich ändern."""
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        vorher = client.get(f"/api/v1/invoices/{rechnung['id']}").json()

        _datev_export(client)

        nachher = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        for feld in ("subtotal", "tax_amount", "total", "status", "invoice_number"):
            assert nachher[feld] == vorher[feld], feld
        assert nachher["lines"] == vorher["lines"]


class TestDatevGutschrift:
    """Gutschriften mindern: H mit positivem Umsatz."""

    def test_storno_spaltengenau(self, client):
        """Original und Stornorechnung sind beide Belege: S und H heben sich auf."""
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                        json={"reason": "Pfand mit 7 % berechnet"})
        assert r.status_code == 200, r.text
        storno = r.json()["credit_note"]
        nr, snr = rechnung["invoice_number"], storno["invoice_number"]

        daten, _, zeilen = _datev_export(client)

        assert zeilen == [
            _datev_zeile("26,75", "S", "10008", "8300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _datev_zeile("7,14", "S", "10008", "8400", nr, "Rechnung 19 % Ökoring Testkunde"),
            _datev_zeile("26,75", "H", "10008", "8300", snr, f"Storno {nr} 7 % Ökoring Testkunde"),
            _datev_zeile("7,14", "H", "10008", "8400", snr, f"Storno {nr} 19 % Ökoring Testkunde"),
        ]
        assert Decimal(str(daten["total_amount"])) == Decimal("0.00")

    def test_storno_spaeter_exportiert_nur_die_stornorechnung(self, client):
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        _datev_export(client)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={"reason": "Preisfehler"})
        snr = r.json()["credit_note"]["invoice_number"]

        _, _, zeilen = _datev_export(client)

        assert [(z[1], z[9]) for z in zeilen] == [("H", snr), ("H", snr)]

    def test_manuelle_gutschrift_mindert(self, client):
        """Gutschrift von Hand (positive Beträge) ist eine Minderung: H."""
        kunde = _datev_kunde(client)
        gs = _datev_rechnung(client, kunde, [("Preisnachlass", 1, "10.00", "REDUZIERT")],
                             typ="GUTSCHRIFT")

        _, _, zeilen = _datev_export(client)

        assert zeilen == [
            _datev_zeile("10,70", "H", "10008", "8300", gs["invoice_number"],
                         "Gutschrift 7 % Ökoring Testkunde"),
        ]
```

- [ ] **Step 2: Bestehenden Service-Test spaltengenau machen**

In `backend/tests/test_datev_export.py`, `test_datev_export_invoices_and_payments`: den Block ab `# Verify` (Zeilen 84-95, `assert count >= 2 …` bis `assert "Zahlung Invoice Customer" in csv_content`) ersetzen durch:

```python
    # Verify — spaltengenau: eine Erlöszeile (Debitor an 8400, S) und eine
    # Zahlungszeile (Bank an Debitor, S). Keine Zeile auf 1400, kein Kopfkonto 8300.
    import csv
    import io
    tag = date.today().strftime("%d%m")
    zeilen = list(csv.reader(io.StringIO(csv_content), delimiter=";"))
    assert zeilen == [
        ["Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz", "Konto", "Gegenkonto",
         "BU-Schlüssel", "Belegdatum", "Belegfeld 1", "Belegfeld 2", "Buchungstext"],
        ["119,00", "S", "EUR", "", "", "10008", "8400", "", tag, "RE-TEST-001", "",
         "Rechnung 19 % Invoice Customer"],
        ["119,00", "S", "EUR", "", "", "1200", "10008", "", tag, "RE-TEST-001", "",
         "Zahlung Invoice Customer"],
    ]
    assert count == 2
    assert total == Decimal("119.00")
```

`test_datev_export_customers` bleibt unverändert.

- [ ] **Step 3: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestDatevKontierung tests/test_gernot_261008.py::TestDatevGutschrift tests/test_datev_export.py -v`

Erwartet: **13 failed, 3 passed.** Bereits grün sind:
- `test_export_aendert_keinen_beleg` und `test_datev_export_customers` — sie sichern Bestandsverhalten;
- `test_summe_der_zeilen_gleich_rechnungsbetrag` — ein **Wächter**: Der alte Export summiert `invoice.total` (`datev_service.py:94`), also gilt heute `total_amount == rechnung['total']`. Der Test soll nach Task 16 grün bleiben; rot würde er nur, wenn der Export anders rechnet als `calculate_totals`.

Typische Meldungen der roten Tests: `At index 0 diff: ['33,89', 'S', 'EUR', '', '', '1400', '10008', …] != ['26,75', 'S', 'EUR', '', '', '10008', '8300', …]`; `test_rundungsgrenze_rabatt_wie_rechnungsbetrag` mit `['21,33', 'S', 'EUR', '', '', '1400', …] != ['21,33', 'S', 'EUR', '', '', '10008', '8300', …]`; `test_sonderkonto_neben_standardkonto_rest_cent` mit `['45,40', 'S', …, '1400', …] != ['24,07', 'S', …]`; `test_neue_rechnung_ohne_kopfkonto` mit `assert '8300' is None`; Storno mit `'-26,75'`. Weicht die Zahl ab: stoppen und melden, keinen Test anpassen.

- [ ] **Step 4: Modulkopf mit Helfern**

In `backend/app/services/datev_service.py` die Zeilen 1-13 (Imports bis `from app.models.customer import Customer`) **ersetzen** durch:

```python
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
import csv
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import (
    Invoice, InvoiceLine, InvoiceStatus, InvoiceType, Payment, PaymentMethod,
    TaxRate, STANDARD_ACCOUNTS, steuer_je_satz,
)
from app.models.customer import Customer

# ---------------------------------------------------------------------------
# Kontierung des Rechnungsexports.
#
# VOR PRODUKTIVNUTZUNG VOM STEUERBERATER ZU BESTÄTIGEN (Spec 08.10.2026,
# Offene Entscheidung 5). Der EXTF-Kopf (Berater-/Mandantennummer, WJ-Beginn,
# Sachkontenlänge) ist NICHT Teil dieser Korrektur.
#
# - Je Rechnung und (Steuersatz, Erlöskonto) genau eine Buchungszeile.
# - Konto = Debitor, Gegenkonto = Erlöskonto, BU-Schlüssel leer:
#   8300/8400 sind in SKR03 Automatikkonten, DATEV rechnet die USt aus dem
#   Bruttobetrag heraus.
# - Umsatz immer positiv; die Richtung steht im Soll/Haben-Kennzeichen und
#   bezieht sich auf das Konto (den Debitor): Rechnung S, Gutschrift H.
# - Keine Zeile auf 1400: das Sammelkonto Forderungen führt DATEV aus den
#   Debitoren selbst. Die frühere Zeile "1400 an Debitor" schrieb die
#   Forderung gut, statt sie zu begründen.
# - Beträge nach der einen Rechenregel steuer_je_satz() (wie Rechnungssummen
#   und Steuerausweis): die Zeilen einer Rechnung ergeben genau ihr total.
# ---------------------------------------------------------------------------

DATEV_KOPF = [
    "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
    "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
    "Belegfeld 1", "Belegfeld 2", "Buchungstext",
]

#: Debitor für Kunden ohne hinterlegtes DATEV-Konto (Bestandsverhalten).
SAMMELDEBITOR = "10000"

ERLOESKONTO_JE_SATZ = {
    TaxRate.REDUZIERT: STANDARD_ACCOUNTS["erloes_7"],
    TaxRate.STANDARD: STANDARD_ACCOUNTS["erloes_19"],
    TaxRate.STEUERFREI: STANDARD_ACCOUNTS["erloes_steuerfrei"],
}

#: Proforma ist kein Buchungsbeleg; Abschlagsrechnungen brauchen eine eigene
#: Kontierung (erhaltene Anzahlungen) und sind in der Oberfläche nicht anlegbar.
EXPORTIERBARE_TYPEN = (InvoiceType.RECHNUNG, InvoiceType.GUTSCHRIFT)

_CENT = Decimal("0.01")


def erloeskonto_fuer(tax_rate: TaxRate) -> str:
    """Standard-Erlöskonto (SKR03) zum Steuersatz: 8300 / 8400 / 8100, unbekannt 8300."""
    return ERLOESKONTO_JE_SATZ.get(tax_rate, STANDARD_ACCOUNTS["erloes_7"])


def ist_standard_erloeskonto(konto: Optional[str]) -> bool:
    """Leer oder eines der drei Standardkonten: dann folgt das Konto dem Satz.

    Jedes andere Konto ist ein Sonderkonto und bleibt stehen — im Export
    (erloeskonto) wie beim Satzwechsel im Entwurf (update_invoice_line,
    Task 25). Bestätigung durch den Steuerberater steht aus.
    """
    return not konto or konto in ERLOESKONTO_JE_SATZ.values()


def erloeskonto(line: InvoiceLine) -> str:
    """Erlöskonto einer Rechnungsposition.

    Die drei Standardkonten folgen immer dem Steuersatz der Position: wird der
    Satz eines Entwurfs nachträglich geändert, bleibt das in add_line gesetzte
    Konto sonst auf dem alten Satz stehen. Ein ausdrücklich gesetztes
    Sonderkonto bleibt erhalten.
    """
    if ist_standard_erloeskonto(line.buchungskonto):
        return erloeskonto_fuer(line.tax_rate)
    return line.buchungskonto


def erloesgruppen(invoice: Invoice) -> list[dict]:
    """Netto, Steuer und Brutto je (Erlöskonto, Steuersatz), mit Vorzeichen.

    Rechenregel steuer_je_satz() aus app.models.invoice — dieselbe wie
    Invoice.calculate_totals() (total) und Invoice.get_tax_summary()
    (Steuerausweis): Rabatt je Satz auf den Cent runden, Entgelt = Netto
    minus Rabatt, Steuer auf das gerundete Entgelt.

    Normalfall: ein Konto je Satz, dann ist jede Gruppe genau der
    Steuerausweis des Satzes. Teilen sich mehrere Konten einen Satz
    (Sonderkonto einer Position neben dem Standardkonto), rundet jedes Konto
    für sich; den Rest-Cent gegenüber dem Steuerausweis des Satzes trägt die
    betragsgrößte Gruppe des Satzes. So ergeben die Zeilen je Satz immer den
    Steuerausweis und zusammen den Rechnungsbetrag.

    Liest nur gespeicherte Werte (line.line_total), ruft also nicht
    calculate_line_total() auf: der Export committet und darf keinen
    versendeten Beleg verändern.
    """
    rabatt = invoice.discount_percent
    zeilen_je_konto: dict[str, list[InvoiceLine]] = {}
    for line in invoice.lines:
        zeilen_je_konto.setdefault(erloeskonto(line), []).append(line)

    gruppen = [
        {"satz": s["rate"], "konto": konto, "netto": s["base"], "steuer": s["tax"]}
        for konto, zeilen in zeilen_je_konto.items()
        for s in steuer_je_satz(zeilen, rabatt)
    ]

    # Rest-Cent-Ausgleich je Satz (bei einem Konto je Satz immer 0).
    for ausweis in steuer_je_satz(invoice.lines, rabatt):
        teile = [g for g in gruppen if g["satz"] == ausweis["rate"]]
        groesste = max(teile, key=lambda g: (abs(g["netto"]), g["konto"]))
        groesste["netto"] += ausweis["base"] - sum(g["netto"] for g in teile)
        groesste["steuer"] += ausweis["tax"] - sum(g["steuer"] for g in teile)

    for g in gruppen:
        g["brutto"] = g["netto"] + g["steuer"]
    return sorted(gruppen, key=lambda g: (g["konto"], g["satz"].value))


def _betrag(wert: Decimal) -> str:
    """DATEV-Betrag: zwei Nachkommastellen, Dezimalkomma, ohne Tausenderpunkt."""
    return f"{Decimal(wert).quantize(_CENT, rounding=ROUND_HALF_UP):.2f}".replace(".", ",")


def _richtung(invoice: Invoice, brutto: Decimal) -> str:
    """Soll/Haben aus Sicht des Debitors.

    Eine Gutschrift mindert immer (H) — die Stornorechnung trägt negative
    Mengen, die von Hand angelegte Gutschrift positive; beide sind Minderungen.
    Eine Rechnung bucht S, ein (heute nicht erzeugbarer) negativer Betrag H.
    """
    if invoice.invoice_type == InvoiceType.GUTSCHRIFT:
        return "H"
    return "S" if brutto >= 0 else "H"


def _debitor(customer: Customer) -> str:
    return customer.datev_account or SAMMELDEBITOR
```

`func` entfällt (in der Datei nicht mehr benutzt; `export_customers_csv` braucht nur `select`). `from typing import Optional` bleibt für `ist_standard_erloeskonto`. Zwischen `_debitor` und `class DatevService:` zwei Leerzeilen.

- [ ] **Step 5: Zeilenaufbau ersetzen**

In `export_invoices_csv` bleiben die Abfrage (`invoices = self.db.execute(…)`, Zeilen 34-44) und der Zahlungsblock ab `# Payments Export` (Zeilen 170-206) in diesem Task **unverändert**. Ersetzt wird alles von `output = StringIO()` (Zeile 46) bis einschließlich `invoice.datev_export_date = datetime.now(timezone.utc)` (Zeile 168) — also der Kopf, die 1400-Zeile, die Erlösschleife mit dem 13-Felder-Bug und die Markierung — durch:

```python
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(DATEV_KOPF)

        record_count = 0
        total_amount = Decimal("0")
        jetzt = datetime.now(timezone.utc)

        for invoice in invoices:
            customer = self.db.get(Customer, invoice.customer_id)
            debitor = _debitor(customer)
            if invoice.invoice_type == InvoiceType.GUTSCHRIFT:
                original = invoice.original_invoice
                art = f"Storno {original.invoice_number}" if original else "Gutschrift"
            else:
                art = "Rechnung"

            for gruppe in erloesgruppen(invoice):
                if gruppe["brutto"] == 0:
                    continue
                sh = _richtung(invoice, gruppe["brutto"])
                betrag = abs(gruppe["brutto"])
                zeile = [
                    _betrag(betrag),                           # Umsatz (immer positiv)
                    sh,                                         # Soll/Haben (bezogen auf Konto)
                    "EUR", "", "",                              # WKZ, Kurs, Basisumsatz
                    debitor,                                    # Konto
                    gruppe["konto"],                            # Gegenkonto (Erlöskonto)
                    "",                                         # BU-Schlüssel (Automatikkonto)
                    invoice.invoice_date.strftime("%d%m"),      # Belegdatum
                    invoice.invoice_number,                     # Belegfeld 1
                    "",                                         # Belegfeld 2
                    f"{art} {gruppe['satz'].percent} % {customer.name}"[:60],
                ]
                writer.writerow(zeile)
                record_count += 1
                total_amount += betrag if sh == "S" else -betrag

            invoice.datev_exported = True
            invoice.datev_export_date = jetzt
```

Den Docstring der Methode im selben Zug korrigieren: die Zeile `Gibt CSV-Content, Anzahl Records und Gesamtbetrag zurück.` ersetzen durch die zwei Zeilen

```python
        Gibt CSV-Content, Anzahl Records und den Saldo der Rechnungszeilen
        (S positiv, H negativ, brutto) zurück.
```

- [ ] **Step 6: Kopf-Default 8300 entfernen**

In `backend/app/services/invoice_service.py`, `create_invoice`, Zeile 102:

```python
            buchungskonto=buchungskonto or STANDARD_ACCOUNTS["erloes_7"],  # Default 7% Erlöse
```

ersetzen durch:

```python
            # Kein Kopf-Default mehr: das Erlöskonto steht je Position
            # (InvoiceLine.buchungskonto, aus dem Steuersatz). Der frühere
            # Default 8300 ließ im DATEV-Export 19 % auf 8300 landen.
            buchungskonto=buchungskonto,
```

`STANDARD_ACCOUNTS` bleibt importiert (`add_line` nutzt es). Kein anderer Code liest `Invoice.buchungskonto` (geprüft: nur der alte Export, `datev_service.py:114-115`).

- [ ] **Step 7: Grün bestätigen**

Run: wie Step 3.
Erwartet: **16 passed**, ohne Ausnahme. Schlägt `test_rundungsgrenze_rabatt_wie_rechnungsbetrag`, `test_sonderkonto_neben_standardkonto_rest_cent` oder `test_summe_der_zeilen_gleich_rechnungsbetrag` fehl, rechnet `erloesgruppen` nicht mit `steuer_je_satz` oder S2 ist unvollständig: stoppen und melden. Den Test nicht anpassen und keine Rundung in diesem Task ändern.

- [ ] **Step 8: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`. Besonders `test_gernot_bugfixes.py::TestBug7DatevExport`, `test_storno.py`, `test_sammelrechnung.py` beachten.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/datev_service.py backend/app/services/invoice_service.py \
        backend/tests/test_datev_export.py backend/tests/test_gernot_261008.py
git commit -m "fix(datev): eine Buchung je Rechnung und Erlöskonto, Debitor an Erlös, Richtung über S/H"
```

---

### Task 17: Nur Buchungsbelege — kein Storno ohne Gegenbeleg, keine Proforma

**Files:**
- Modify: `backend/app/services/datev_service.py` (Imports; neue Methode `DatevService._rechnungen`; Abfrage in `export_invoices_csv`)
- Modify: `backend/app/services/invoice_service.py` (`cancel_invoice`: Sperre direkt vor `# Original stornieren`, auf `main` Zeile 306)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: Helfer und `EXPORTIERBARE_TYPEN` aus Task 16; `Invoice.original_invoice_id`, `Invoice.invoice_type`, `Invoice.status`, `Invoice.datev_exported`.
- Produces:
  - `DatevService._rechnungen(self, from_date: date, to_date: date, erneut_exportieren: bool = False) -> list[Invoice]` — Task 18 reicht den Parameter nur noch durch.
  - `InvoiceService.cancel_invoice(...)` wirft `ValueError` (Route: HTTP 400), wenn `invoice.datev_exported` und `create_credit_note` falsch ist. Signatur unverändert.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestDatevBelegauswahl:
    """Nur Buchungsbelege: kein Entwurf, keine Proforma, kein Storno ohne Gegenbeleg."""

    def test_storniert_ohne_stornorechnung_wird_nicht_exportiert(self, client):
        """Ohne Gegenbeleg würde DATEV Umsatz buchen, den es nie gab."""
        from app.models.invoice import Invoice, InvoiceStatus
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        # Zustand wie nach einem Storno ohne Gegenbeleg (create_credit_note=False
        # oder PATCH status) — direkt gesetzt, damit der Test nicht davon abhängt,
        # ob die API diesen Weg künftig noch erlaubt.
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(rechnung["id"])).status = InvoiceStatus.STORNIERT
            db.commit()

        daten, _, zeilen = _datev_export(client)

        assert zeilen == []
        assert daten["record_count"] == 0

    def test_verworfene_gutschrift_von_hand_wird_nicht_exportiert(self, client):
        """Eine von Hand angelegte Gutschrift, deren Entwurf per PATCH status=STORNIERT
        verworfen wurde, ist kein Beleg. Nur die Stornorechnung (GUTSCHRIFT mit
        original_invoice_id) wird unabhängig vom Status exportiert."""
        from app.models.invoice import Invoice, InvoiceStatus
        kunde = _datev_kunde(client)
        gs = _datev_rechnung(client, kunde, [("Preisnachlass", 1, "10.00", "REDUZIERT")],
                             typ="GUTSCHRIFT", finalisieren=False)
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(gs["id"])).status = InvoiceStatus.STORNIERT
            db.commit()

        _, _, zeilen = _datev_export(client)

        assert zeilen == []

    def test_proforma_und_entwurf_werden_nicht_exportiert(self, client):
        kunde = _datev_kunde(client)
        _datev_rechnung(client, kunde, DATEV_GEMISCHT, typ="PROFORMA")
        _datev_rechnung(client, kunde, DATEV_GEMISCHT, finalisieren=False)

        _, _, zeilen = _datev_export(client)

        assert zeilen == []

    def test_exportierte_rechnung_nur_mit_stornorechnung_stornierbar(self, client):
        """Nach dem Export kann nur ein Gegenbeleg den Umsatz in DATEV aufheben.
        Ein Storno ohne Stornorechnung nähme die Rechnung aus jedem weiteren
        Export, der Umsatz bliebe in DATEV still stehen."""
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        _datev_export(client)

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                        json={"reason": "Doppelt erfasst", "create_credit_note": False})

        assert r.status_code == 400, r.text
        assert "DATEV" in r.json()["detail"]
        assert client.get(f"/api/v1/invoices/{rechnung['id']}").json()["status"] == "OFFEN"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestDatevBelegauswahl -v`
Erwartet: **4 failed.** Drei mit nicht leerer Zeilenliste (`assert [['26,75', 'S', …]] == []` bzw. bei der verworfenen Gutschrift `assert [['10,70', 'H', …]] == []`), `test_exportierte_rechnung_nur_mit_stornorechnung_stornierbar` mit `assert 200 == 400`.

- [ ] **Step 3: Imports**

In `backend/app/services/datev_service.py`:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
```

ersetzen durch:

```python
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session, aliased
```

- [ ] **Step 4: Belegauswahl als eigene Methode**

In `DatevService` direkt vor `def export_invoices_csv(` einfügen:

```python
    def _rechnungen(
        self, from_date: date, to_date: date, erneut_exportieren: bool = False
    ) -> list[Invoice]:
        """Buchungsrelevante Belege im Zeitraum.

        - Entwürfe nie, Proforma/Abschlag nie.
        - Eine Stornorechnung (GUTSCHRIFT mit original_invoice_id) immer,
          gleich mit welchem Status: der Storno-Abschnitt setzt sie auf
          STORNIERT, sie bleibt trotzdem ein Beleg.
        - Eine stornierte RECHNUNG nur, wenn eine Stornorechnung existiert:
          dann sind beide Belege und heben sich in DATEV auf. Ohne Gegenbeleg
          (Storno ohne Stornorechnung, per PATCH stornierter Entwurf) gäbe es
          nur Umsatz, den es nie gab.
        - Eine stornierte Gutschrift von Hand (verworfener Entwurf) nie.
        - Bereits exportierte nur mit erneut_exportieren=True.
        """
        storno = aliased(Invoice)
        hat_stornorechnung = (
            select(storno.id)
            .where(
                storno.original_invoice_id == Invoice.id,
                storno.invoice_type == InvoiceType.GUTSCHRIFT,
                storno.status != InvoiceStatus.ENTWURF,
            )
            .exists()
        )
        ist_stornorechnung = and_(
            Invoice.invoice_type == InvoiceType.GUTSCHRIFT,
            Invoice.original_invoice_id.isnot(None),
        )
        query = select(Invoice).where(
            Invoice.invoice_date.between(from_date, to_date),
            Invoice.status != InvoiceStatus.ENTWURF,
            Invoice.invoice_type.in_(EXPORTIERBARE_TYPEN),
            or_(
                ist_stornorechnung,
                Invoice.status != InvoiceStatus.STORNIERT,
                hat_stornorechnung,
            ),
        )
        if not erneut_exportieren:
            query = query.where(Invoice.datev_exported == False)  # noqa: E712
        return self.db.execute(query.order_by(Invoice.invoice_number)).scalars().all()
```

In `export_invoices_csv` den Kommentar und die Abfrage (heute Zeilen 34-44, `# Exclude drafts and already exported?` bis `).scalars().all()`) ersetzen durch:

```python
        invoices = self._rechnungen(from_date, to_date)
```

Die Abfrage über ORM und `aliased`, nicht über rohes SQL: UUIDs liegen in SQLite als `CHAR(32)`, ein Vergleich in rohem SQL scheitert leicht am Format. `ist_stornorechnung` (GUTSCHRIFT **mit** `original_invoice_id`) im `or_` sorgt dafür, dass eine Stornorechnung auch auf `STORNIERT` exportiert wird (S3 setzt sie dorthin), eine verworfene Gutschrift von Hand aber nicht. Dieselbe Definition nutzt S3 für `ist_storno` in `POST /invoices/{id}/send`.

- [ ] **Step 5: Storno ohne Stornorechnung nach dem Export sperren**

In `backend/app/services/invoice_service.py`, `cancel_invoice`, direkt **vor** der Zeile `        # Original stornieren` (auf `main` Zeile 306; S3 lässt sie stehen) einfügen:

```python
        # DATEV kennt die Rechnung schon. Ohne Stornorechnung fiele sie aus
        # jedem weiteren Export, ihr Umsatz bliebe in DATEV still stehen.
        if invoice.datev_exported and not create_credit_note:
            raise ValueError(
                "Die Rechnung wurde bereits an DATEV exportiert und kann nur mit "
                "Stornorechnung storniert werden"
            )
```

Die Sperre steht vor jeder Änderung am Beleg; die Route (`invoices.py:278-300`, `cancel_invoice`) fängt `ValueError` und antwortet 400 ohne Commit. Die Oberfläche (`Invoices.tsx:134`, `stornoMutation`) sendet `create_credit_note` nie und ist nicht betroffen.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestDatevKontierung tests/test_gernot_261008.py::TestDatevGutschrift tests/test_gernot_261008.py::TestDatevBelegauswahl tests/test_datev_export.py tests/test_storno.py -v`
Erwartet: alle passed (20 S4-/DATEV-Tests plus `test_storno.py`). `TestDatevWiederholungsexport` existiert noch nicht.

- [ ] **Step 7: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/datev_service.py backend/app/services/invoice_service.py \
        backend/tests/test_gernot_261008.py
git commit -m "fix(datev): nur Buchungsbelege exportieren, Storno nach Export nur mit Stornorechnung"
```

---

### Task 18: Wiederholungsexport per `erneut_exportieren`

**Files:**
- Modify: `backend/app/services/datev_service.py` (`export_invoices_csv`: Signatur, Aufruf `_rechnungen`, Zahlungsabfrage und -zeile)
- Modify: `backend/app/schemas/invoice.py:258-262` (`DatevExportRequest`)
- Modify: `backend/app/api/v1/invoices.py:426-430` und `:449-453` (beide Routen)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `DatevService._rechnungen(..., erneut_exportieren)` aus Task 17.
- Produces:
  - `DatevService.export_invoices_csv(self, from_date: date, to_date: date, include_payments: bool = True, erneut_exportieren: bool = False) -> tuple[str, int, Decimal]` — Rückgabe unverändert dreiteilig (der Service-Test entpackt drei Werte).
  - `DatevExportRequest.erneut_exportieren: bool = False` für `POST /api/v1/invoices/datev-export` und `POST /api/v1/invoices/datev-export/download`. `DatevExportResponse` bleibt unverändert.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestDatevWiederholungsexport:

    def _exportiert(self, rechnung_id):
        from app.models.invoice import Invoice
        with TestingSessionLocal() as db:
            inv = db.get(Invoice, uuid.UUID(rechnung_id))
            return inv.datev_exported, inv.datev_export_date

    def test_export_markiert_genau_die_exportierten(self, client):
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        entwurf = _datev_rechnung(client, kunde, DATEV_GEMISCHT, finalisieren=False)

        _datev_export(client)

        markiert, wann = self._exportiert(rechnung["id"])
        assert markiert is True and wann is not None
        assert self._exportiert(entwurf["id"]) == (False, None)

    def test_zweiter_lauf_ohne_wiederholung_ist_leer(self, client):
        kunde = _datev_kunde(client)
        _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        _datev_export(client)

        daten, kopf, zeilen = _datev_export(client)

        assert kopf == DATEV_KOPF
        assert zeilen == []
        assert daten["record_count"] == 0

    def test_wiederholung_liefert_dieselben_zeilen_und_neue_dazu(self, client):
        kunde = _datev_kunde(client)
        _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        _, _, erster_lauf = _datev_export(client)
        neu = _datev_rechnung(client, kunde, [("Kresse", 1, "10.00", "REDUZIERT")])

        _, _, nur_neu = _datev_export(client)
        _, _, alles = _datev_export(client, erneut=True)

        assert [z[9] for z in nur_neu] == [neu["invoice_number"]]
        assert alles == erster_lauf + nur_neu

    def test_zahlungen_werden_mit_wiederholt(self, client):
        kunde = _datev_kunde(client)
        rechnung = _datev_rechnung(client, kunde, DATEV_GEMISCHT)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/payments", json={
            "invoice_id": rechnung["id"], "amount": "33.89",
            "payment_date": date.today().isoformat(),
        })
        assert r.status_code == 201, r.text
        nr = rechnung["invoice_number"]
        zahlung = _datev_zeile("33,89", "S", "1200", "10008", nr, "Zahlung Ökoring Testkunde")

        _, _, erster = _datev_export(client, zahlungen=True)
        _, _, zweiter = _datev_export(client, zahlungen=True)
        _, _, wiederholt = _datev_export(client, zahlungen=True, erneut=True)

        assert erster[-1] == zahlung
        assert zweiter == []
        assert wiederholt == erster
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestDatevWiederholungsexport -v`
Erwartet: **2 failed, 2 passed.** `test_wiederholung_liefert_dieselben_zeilen_und_neue_dazu` und `test_zahlungen_werden_mit_wiederholt` FAIL (das Feld wird ignoriert, der dritte Lauf ist leer). `test_export_markiert_genau_die_exportierten` und `test_zweiter_lauf_ohne_wiederholung_ist_leer` sind bereits grün — sie sichern den Schutz gegen versehentlichen Doppelexport.

- [ ] **Step 3: Service**

In `backend/app/services/datev_service.py` Signatur und Docstring von `export_invoices_csv` (von `    def export_invoices_csv(` bis einschließlich der schließenden `"""` des Docstrings aus Task 16 Step 5) ersetzen durch:

```python
    def export_invoices_csv(
        self,
        from_date: date,
        to_date: date,
        include_payments: bool = True,
        erneut_exportieren: bool = False,
    ) -> tuple[str, int, Decimal]:
        """
        Exportiert Rechnungen und optional Zahlungen im DATEV-Format (CSV Buchungsstapel).
        Gibt CSV-Content, Anzahl Records und den Saldo der Rechnungszeilen
        (S positiv, H negativ, brutto) zurück.

        Markiert genau die exportierten Rechnungen/Zahlungen (datev_exported,
        datev_export_date) in derselben Transaktion. erneut_exportieren=True
        nimmt bereits exportierte im Zeitraum wieder auf — für eine verlorene
        oder vom Steuerberater zurückgewiesene Datei.
        """
```

Den Aufruf aus Task 17 ändern in:

```python
        invoices = self._rechnungen(from_date, to_date, erneut_exportieren)
```

Den Zahlungsblock (ab `# Payments Export` bis vor `return output.getvalue(), record_count, total_amount`) ersetzen durch:

```python
        # Payments Export
        if include_payments:
            query = (
                select(Payment)
                .join(Invoice)
                .where(Payment.payment_date.between(from_date, to_date))
                .order_by(Payment.payment_date, Invoice.invoice_number)
            )
            if not erneut_exportieren:
                query = query.where(Payment.datev_exported == False)  # noqa: E712
            payments = self.db.execute(query).scalars().all()

            for payment in payments:
                invoice = payment.invoice
                customer = self.db.get(Customer, invoice.customer_id)

                bank_account = STANDARD_ACCOUNTS.get("bank", "1200")
                if payment.payment_method == PaymentMethod.BAR:
                    bank_account = STANDARD_ACCOUNTS.get("kasse", "1000")

                # Booking: Bank (1200) S an Debitor H
                row_payment = [
                    _betrag(payment.amount),
                    "S",
                    "EUR", "", "",
                    bank_account,
                    _debitor(customer),
                    "",
                    payment.payment_date.strftime("%d%m"),
                    invoice.invoice_number,
                    payment.reference or "",
                    f"Zahlung {customer.name}"[:60],
                ]
                writer.writerow(row_payment)
                record_count += 1

                payment.datev_exported = True
```

Inhalt der Zahlungszeile unverändert (Bank S an Debitor); neu sind nur der Wiederholungsfilter, eine feste Sortierung und die gemeinsamen Helfer `_betrag`/`_debitor`. Die Zahlungen werden bewusst **nicht** nach Belegart gefiltert (siehe Offener Punkt 10).

- [ ] **Step 4: Schema**

In `backend/app/schemas/invoice.py`, `DatevExportRequest`, nach `include_payments`:

```python
    erneut_exportieren: bool = Field(
        default=False,
        description="Bereits exportierte Rechnungen/Zahlungen im Zeitraum erneut aufnehmen "
                    "(nur wenn die vorige Datei NICHT in DATEV importiert wurde)",
    )
```

- [ ] **Step 5: Beide Routen**

In `backend/app/api/v1/invoices.py`, in `export_datev` **und** `download_datev_export`, den Aufruf `service.export_invoices_csv(...)` um eine Zeile ergänzen:

```python
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
        erneut_exportieren=data.erneut_exportieren,
    )
```

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestDatevKontierung tests/test_gernot_261008.py::TestDatevGutschrift tests/test_gernot_261008.py::TestDatevBelegauswahl tests/test_gernot_261008.py::TestDatevWiederholungsexport tests/test_datev_export.py tests/test_gernot_bugfixes.py::TestBug7DatevExport -v`
Erwartet: **25 passed** (22 Tests in den vier `TestDatev*`-Klassen, 2 in `test_datev_export.py`, 1 `TestBug7DatevExport`). Danach `tests/test_gernot_261008.py` als Ganzes laufen lassen: auch die Tests der anderen Abschnitte (`TestS2…` usw.) bleiben grün.

- [ ] **Step 7: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/datev_service.py backend/app/schemas/invoice.py \
        backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "feat(datev): Export lässt sich für einen Zeitraum ausdrücklich wiederholen"
```

---

### Task 19: Oberfläche — Wiederholung anbieten, wirkungsloses Kopfkonto entfernen

**Files:**
- Modify: `frontend/src/services/api.ts:774-778` (`invoicesApi.exportDatev`, `invoicesApi.downloadDatev`; nach S3 etwa `:776-780`)
- Modify: `frontend/src/pages/Invoices.tsx` — `InvoiceCreateForm` (`:668`, `:684`, `:749-753`) und `DatevExportForm` (`:886-956`) — Zeilen auf `c4a1832`; nach S3 um etwa +9 bis +16 verschoben, bei Abweichung nach dem zitierten Inhalt suchen

**Interfaces:**
- Consumes: `erneut_exportieren` aus Task 18.

- [ ] **Step 1: Parametertyp**

In `frontend/src/services/api.ts` beide Methoden:

```ts
  exportDatev: (data: { from_date: string; to_date: string; include_payments?: boolean; erneut_exportieren?: boolean }) =>
    api.post('/invoices/datev-export', data).then(r => r.data),

  downloadDatev: (data: { from_date: string; to_date: string; include_payments?: boolean; erneut_exportieren?: boolean }) =>
```

(die Folgezeile von `downloadDatev` bleibt unverändert).

- [ ] **Step 2: Feld „Buchungskonto" aus dem Anlageformular entfernen**

Das Kopfkonto hat nach Task 16 keine Wirkung mehr; das Feld lädt nur zu der Fehlbuchung ein, die Task 16 beseitigt. In `InvoiceCreateForm`:
- im `useState` die Zeile `    buchungskonto: '',` (668) entfernen,
- in `handleSubmit` die Zeile `        buchungskonto: formData.buchungskonto || undefined,` (684) entfernen,
- den Block (749-753) entfernen:

```tsx
      <Input
        label="Buchungskonto"
        placeholder="Standard (z.B. 8400)..."
        value={formData.buchungskonto}
        onChange={(e) => setFormData({ ...formData, buchungskonto: e.target.value })}
      />
```

`buchungskonto?: string` im Typ von `invoicesApi.create` (`api.ts:728`) und in `frontend/src/types/index.ts` bleibt (API-Feld existiert weiter).

- [ ] **Step 3: Export-Dialog**

In `DatevExportForm` den State um `erneut_exportieren: false,` nach `include_payments: true,` ergänzen. In `handleExport` direkt nach `const result = await invoicesApi.exportDatev(formData);`:

```tsx
      if (result.record_count === 0) {
        // Bereits exportierte Belege kommen nur mit "erneut exportieren" wieder —
        // eine leere Datei herunterzuladen hilft niemandem.
        toast.info('Keine neuen Buchungen im Zeitraum. Bereits exportierte nur über „Erneut exportieren".');
        return;
      }
```

(`finally` setzt `loading` auch beim `return` zurück; der Dialog bleibt offen.) Nach dem `</label>` des Häkchens „Zahlungen einschließen" (Zeile ~943) einfügen:

```tsx
      <label className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={formData.erneut_exportieren}
          onChange={(e) => setFormData({ ...formData, erneut_exportieren: e.target.checked })}
          className="mt-0.5 w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
        />
        <span className="text-sm text-gray-700 dark:text-gray-300">
          Bereits exportierte erneut exportieren
          {formData.erneut_exportieren && (
            <span className="block text-amber-700 dark:text-amber-300">
              Nur verwenden, wenn die vorige Datei nicht in DATEV importiert wurde — sonst wird doppelt gebucht.
            </span>
          )}
        </span>
      </label>
```

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build` — ohne TypeScript-Fehler. (In der Kopie geprüft: `tsc --noEmit` mit diesen Änderungen fehlerfrei; `toast.info` existiert, s. `Settings.tsx:303`.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/pages/Invoices.tsx
git commit -m "feat(datev): Wiederholungsexport im Dialog, wirkungsloses Kopfkonto entfernt"
```

---

## Abschnitt S6: Doppelte Abrechnung verhindern — Tasks 20–24

**Ziel:** Abgerechnet wird die Bestellung, nicht der Lieferschein — und jede Bestellung genau einmal. Eine Regel (`InvoiceService.aktive_rechnung_zur_bestellung` bzw. `abgerechnete_bestellungen`) sperrt „Rechnung aus Bestellung", manuelle Rechnungen mit Bestellbezug und den Sammellauf gleichermaßen. Nach einem Storno ist die Bestellung wieder frei (Neuausstellung für das Runbook aus S3).

**Befund, am Code geprüft (`main` @ `c4a1832`) und in einer Sandbox nachgestellt:**

| Stelle | Befund |
|---|---|
| `backend/app/services/invoice_service.py:177-216` `create_invoice_from_order` | keine Sperre gegen eine zweite Rechnung; setzt `DeliveryNote.invoice_id` nicht; Bestellstatus bleibt |
| `backend/app/api/v1/invoices.py:521-545` `_abrechenbare_lieferscheine` | nimmt jeden Lieferschein mit `invoice_id IS NULL` (auch `ENTWURF`), prüft nicht `Invoice.order_id` |
| `backend/app/api/v1/invoices.py:548-570` `_aggregiere` | zählt `order.lines` **je Lieferschein** — zwei Lieferscheine = doppelte Menge |
| `backend/app/api/v1/documents.py:185-260` `create_delivery_note` | beliebig viele Lieferscheine je Bestellung; Knopf „Neuer LS" `OrderDocumentsModal.tsx:211-218` |
| `frontend/src/components/domain/OrderDocumentsModal.tsx:43-47` | Rechnungen je Bestellung = `invoicesApi.list({})` (Standard `page_size` 20, `deps.py:161`) clientseitig gefiltert; Knopf „Rechnung aus Bestellung" `:288-295` immer sichtbar |
| `backend/app/api/v1/invoices.py:36-68` `list_invoices` | kein `order_id`-Filter |
| `backend/app/services/pdf_service.py:371-403` | Anlage „Enthaltene Lieferscheine" liest `DeliveryNote.invoice_id`; **`Decimal` ist in `pdf_service.py` nicht importiert** (Zeile 389) → jede Rechnung mit zugeordnetem Lieferschein (= jede Sammelrechnung) antwortet beim PDF-Abruf mit 500 `NameError` (seit `c637d5b`, kein Test deckt es ab) |

**Nachgestellter Ernstfall (lokale SQLite-Datei, kein Produktionszugriff):** Muster wie in Produktion — eine Sammelrechnung, drei Rechnungen „aus Bestellung" mit unverknüpften Lieferscheinen (eine Bestellung mit zwei Lieferscheinen), eine Rechnung ohne Lieferschein, eine von Hand auf `FAKTURIERT` gesetzte Bestellung ohne Rechnung, eine bereits doppelt berechnete Bestellung. Sammellauf-Vorschau mit dem heutigen Code: **6 Lieferscheine, 168,00 € netto erneut berechnet.** Mit S6 blieb nur die `FAKTURIERT`-Bestellung ohne Rechnung (1 Lieferschein, 28,00 €). Seit Task 22 auch `FAKTURIERT` ausschließt (Spec-Nachtrag 08.10.), fällt auch sie heraus (siehe Runbook R2b, P5, und Offener Punkt G10).

**Einordnung:**
- **Hart: keine.** S6 läuft nach S1–S4 und braucht keinen davon. Die Tests nutzen Freitext-Positionen mit ausdrücklichem Steuersatz; die behalten laut `tests/test_gernot_260821.py:486-504` und `tests/test_pfand_rabatt.py:49-75` den Client-Wert.
- **Gemeinsame Funktionen nur an den wörtlich angegebenen Ankern:** Sperre in `create_invoice` hinter der Kundenprüfung, Block vor dem letzten `return invoice` in `create_invoice_from_order` (Fassung aus Task 2), Neufassung von `_abrechenbare_lieferscheine` (**nicht** `_aggregiere` aus Task 3, **nicht** `batch_run_commit`), Filterblock in `list_invoices`, Bedingung am Anlagen-Block im PDF (der `Decimal`-Import steht seit Task 10). Weicht ein Anker ab, weil ein früherer Task ihn geändert hat, und ist die Absicht eindeutig: an der entsprechenden Stelle einfügen und in der Abschlussmeldung vermerken. Für die Komplettersetzung von `_abrechenbare_lieferscheine` vergleicht Task 22 Step 4 die Funktion vorher mit `c4a1832`.
- **R1.6-Block:** Der Block in `cancel_invoice`, der `DeliveryNote.invoice_id = None` setzt, bleibt (Task 12/13 lassen ihn unberührt). `test_storno_loest_und_neuausstellung_verknuepft_neu` prüft ihn.
- **S5 kommt danach:** Tasks 28 und 29 bauen auf dem Filter `GET /invoices?order_id=` und dem Belege-Dialog aus Task 24 auf. Die Einzelfassung von S6 sah S6 nach der Rechnungsliste; das ist hier aufgelöst.
- **Runbook:** setzt S6 deployt voraus. Neuausstellung per „Rechnung aus Bestellung" nach Storno ist erlaubt, ein zweiter Klick wird mit 409 abgelehnt, die Neuausstellung hängt den Lieferschein an, und der Sammellauf überspringt die Bestellung.
- **Sofortmaßnahme 3 („Keinen Sammelrechnungslauf starten") bleibt in Kraft,** bis S6 deployt ist und das Runbook R2b und R12 durchlaufen hat.

### Entscheidungen

**(a) Sperre in `InvoiceService.create_invoice`, nicht nur in `from-order`.** Sie greift, sobald `order_id` gesetzt und `invoice_type == RECHNUNG` ist — damit auch für `POST /invoices` mit `order_id` (`InvoiceCreate.order_id`, `schemas/invoice.py:125`). „Bereits abgerechnet" heißt: eine Rechnung vom Typ `RECHNUNG`, Status ≠ `STORNIERT`, entweder mit `Invoice.order_id` = Bestellung (Rechnung aus Bestellung) oder über einen Lieferschein der Bestellung mit `invoice_id` (Sammelrechnung — Sammelrechnungen haben keine `order_id`, `invoices.py:604-611`). Gutschriften, Proforma und Abschlagsrechnungen (`InvoiceType.ABSCHLAG`, `models/enums.py:45`; nur über die API anlegbar, die Oberfläche kennt den Typ nicht, `frontend/src/types/index.ts:591`) sperren nicht, weil nur `RECHNUNG` sperrt; die Stornorechnung trägt ohnehin keine `order_id` (`invoice_service.py:321-329`). Die Prüfung läuft **vor** `_generate_next_invoice_number` und `self.db.add(invoice)` — danach fände die Abfrage die neue Rechnung selbst. Eine Nummer verbraucht eine Ablehnung ohnehin nicht: Die Nummer ist max+1 der gespeicherten Rechnungen (`invoice_service.py:438-449`), und die API committet im Fehlerfall nicht (`invoices.py:106-140`). Antwort 409 über `BereitsAbgerechnet(ValueError)`: bestehende `except ValueError`-Aufrufer funktionieren unverändert. Restrisiko: zwei gleichzeitige Anfragen können beide die Prüfung passieren (SQLite, `with_for_update` wirkt dort nicht). Abgefangen wird der Doppelklick im Dialog (Knopf gesperrt während der Anfrage, danach ausgeblendet). Einen eindeutigen Teilindex auf `invoices(order_id)` baut S6 bewusst nicht: Bestehende Doppelungen (Runbook P4a) ließen `CREATE UNIQUE INDEX` beim Start scheitern, und `_auto_migrate` bricht dann alle folgenden Migrationen im selben `try` ab (`tenancy.py:283-358`).

**(b) Lieferschein anhängen; beim Storno lösen, nicht umhängen.** „Rechnung aus Bestellung" setzt `invoice_id` an **genau einem** noch nicht zugeordneten Lieferschein der Bestellung (Vertreter: der älteste quittierte, sonst der älteste; Funktion `waehle_vertreter`). Genau einer, weil die PDF-Anlage und `GET /invoices/{id}/delivery-notes` je Lieferschein die volle Bestellsumme ausweisen (`pdf_service.py:387-390`, `invoices.py:668`). Beim Storno **lösen** (bestehender R1.6-Block): Zum Storno-Zeitpunkt gibt es die neue Rechnung noch nicht, Umhängen ginge erst bei der Neuausstellung und bräuchte eine Regel „Zuordnung von stornierter Rechnung übernehmen" — gleiches Ergebnis, mehr Code. Lösen hält beide Wege der Neuausstellung offen (Rechnung aus Bestellung **oder** Sammellauf), und weil Task 22 auf Bestellungsebene prüft, wird nach dem Lösen trotzdem genau einmal neu berechnet. **GoBD-Folge und Gegenmaßnahme:** Die Anlage „Enthaltene Lieferscheine" wird bei jedem PDF-Abruf aus `DeliveryNote.invoice_id` gebaut. Ohne Gegenmaßnahme bekäme jede neue Rechnung aus Bestellung diese Anlage und verlöre sie beim Storno — das PDF einer versendeten Rechnung änderte sich nachträglich. Deshalb erscheint die Anlage nur noch bei Rechnungen **ohne** Bestellbezug (`invoice.order_id is None` = Sammelrechnung). Kein bestehendes PDF ändert sich dadurch: Rechnungen mit Bestellbezug hatten bisher nie einen zugeordneten Lieferschein (from-order setzte nichts), Sammelrechnungen haben keine `order_id`. Dass das PDF einer **stornierten Sammelrechnung** seine Anlage verliert, ist ein bestehender Effekt von R1.6 und bleibt (Offener Punkt B14).

**(c) Sammellauf:** `_abrechenbare_lieferscheine` liefert je noch nicht abgerechneter Bestellung genau einen Vertreter-Lieferschein; Bestellungen aus `abgerechnete_bestellungen()` fallen heraus — auch der Altbestand RE-00002/3/4, an dem kein Lieferschein hängt (Prüfung über `Invoice.order_id`). Vorschau (`batch_run_preview`) und Festschreiben (`batch_run_commit`) rufen beide diese Funktion → eine Regel. `_aggregiere` und `batch_run_commit` bleiben unverändert: Weil jede Bestellung nur einmal hineinkommt, zählt `_aggregiere` ihre Zeilen einmal; das hält S6 auch aus dem A3-Umbau von `_aggregiere` heraus. Weitere Lieferscheine einer berechneten Bestellung behalten `invoice_id = NULL`; die Bestellung gilt über ihren Vertreter als berechnet. Bestellungen auf `FAKTURIERT` fallen ebenfalls heraus: Der Spec-Nachtrag vom 08.10. ordnet „FAKTURIERT-Bestellungen nicht erneut abrechnen" der Doppelabrechnungssperre in Paket 1 zu (Nachtrag T4, Probe P7: bisher rechnete der Lauf eine von Hand auf `FAKTURIERT` gesetzte Bestellung trotzdem ab). Lieferscheine im Status `ENTWURF` werden weiter berechnet — `tests/test_sammelrechnung.py` legt ausschließlich `ENTWURF`-Lieferscheine an, und ob nur quittierte Lieferungen in die Sammelrechnung dürfen, ist eine Kundenentscheidung (Offener Punkt G11).

**(d) Zweiter Lieferschein: warnen mit Pflichtbestätigung, nicht sperren.** Nach (c) ist ein zweiter Lieferschein kein Abrechnungsrisiko mehr. Eine harte Sperre nähme den einzigen Weg zu einer aktuellen Packliste: Die Packliste ist ein Schnappschuss (`PackingListItem`, `documents.py:226-256`), Positionen sind in `BESTAETIGT` noch änderbar (`sales.py:1310`), und es gibt weder Bearbeiten noch Storno eines Lieferscheins. Der Server erzwingt die Bestätigung (409 ohne `?zusaetzlich=true`), damit kein Aufrufer still doppelt; der Dialog fragt per `window.confirm` nach. Der Tagesplan bleibt unberührt — er nimmt `notes[0]` und legt nur ohne Lieferschein einen an (`Tagesplan.tsx:60-61`).

**(e) Dialog:** neuer Filter `GET /invoices?order_id=` mit beiden Wegen aus (a); der Dialog fragt damit statt mit der 20er-Liste. Der Knopf „Rechnung aus Bestellung" erscheint nur, wenn die Liste frisch geladen ist und keine nicht stornierte Rechnung vom Typ `RECHNUNG` enthält; ein Ladefehler wird angezeigt statt als „keine Rechnung". Ausnahme 403: Planung und Halle öffnen den Dialog wegen der Lieferscheine (`documents.router` mit `_deps_belege`, `main.py:129` und `:798`), der Rechnungs-Router hängt aber an `_deps_geld = _rollen(SALES, BUCHHALTUNG)` (`main.py:125` und `:743`). Für sie ist 403 kein Ladefehler: grauer Hinweis „Rechnungen sehen nur Vertrieb und Buchhaltung.", kein Knopf.

**(f) Kein automatisches `FAKTURIERT`.** `FAKTURIERT` ist ein Endzustand (`sales.py:1203`: `OrderStatus.FAKTURIERT: []`). Rechnung vor Lieferung ist möglich (der Dialog bietet den Knopf in jedem Status). Stünde die Bestellung dann auf `FAKTURIERT`, setzte das Quittieren sie nicht mehr auf `GELIEFERT` und buchte den Bestand nicht ab (`documents.py:300-312` greift nur bei `ENTWURF`/`BESTAETIGT`/`IN_PRODUKTION`), und sie verschwände aus Packen und Ausliefern im Tagesplan (`production.py:523` und `:673` filtern auf dieselben drei Status). Ein Storno müsste den Status zurücksetzen, wofür es keinen Übergang gibt. Der Abrechnungsstand kommt deshalb aus der Rechnung selbst (eine Wahrheit); der manuelle Übergang `GELIEFERT → FAKTURIERT` bleibt. Einheitliche Statuswege gehören zu Paket 2 (A1). `test_bestellstatus_bleibt_und_lieferung_ist_weiter_moeglich` schreibt das fest.

### Hinweise für den Worker (S6)

- **Schnellere Testläufe, am 08.10.2026 verifiziert:** Mit vorangestelltem `REDIS_URL=memory://` scheitert das Forecast-Update bei jeder Bestellanlage sofort (abgefangen, nur Warnung, `sales.py:40-46`) statt auf den nicht erreichbaren Redis zu warten. Vollauf `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py` dauerte **ca. 16 s statt ca. 19 min**, Baseline unverändert 15 failed / 501 passed / 2 skipped / 1 error mit **identischer Fehlerliste**. Die S6-Testdatei: mit `memory://` ca. 2 s, ohne ca. 7 min (21 passed in beiden Varianten verifiziert). Beide Varianten sind zulässig; im Zweifel zählt der Vollauf ohne Variable.
- `backend/tests/test_gernot_261008.py` teilen sich mehrere Abschnitte. S6-Helfer heißen `_s6_…`, Konstanten `S6_…`. Die Datei existiert seit Task 1; nur anhängen.
- **Nicht anfassen:** `_aggregiere`, `batch_run_commit`, den R1.6-Block in `cancel_invoice`, `frontend/src/pages/Tagesplan.tsx`.

### Review Focus (S6)

1. **Ablehnung ohne Spuren:** Eine abgelehnte zweite Rechnung wird nicht gespeichert — getestet in Task 20 (`len(alle) == 1`). Eine Nummer verbraucht sie unabhängig von der Position der Prüfung nicht (Nummer = max+1 der gespeicherten, `invoice_service.py:438-449`; die API committet im Fehlerfall nicht); dafür gibt es keinen eigenen Test. Die Prüfung steht vor dem Anlegen, weil die Abfrage sonst die neue Rechnung selbst fände.
2. **Storno → Neuausstellung erlaubt, danach wieder gesperrt** (Runbook). Getestet in Task 20 und Task 21.
3. **GoBD:** Das PDF einer Rechnung mit Bestellbezug ändert sich weder durch das Anhängen noch durch das Lösen eines Lieferscheins. Getestet in Task 21.
4. **Altbestand RE-00002/3/4** (Rechnung aus Bestellung, Lieferschein ohne `invoice_id`) erscheint weder in der Vorschau noch im Festschreiben. Getestet in Task 22.
5. **Vorschau = Festschreiben:** beide über `_abrechenbare_lieferscheine`. Getestet in Task 22 (Vorschau und Lauf im selben Test).
8. **`FAKTURIERT` ohne Rechnung** fällt aus Vorschau und Festschreiben (Spec-Nachtrag). Getestet in Task 22 (`test_fakturierte_bestellung_ohne_rechnung_wird_uebersprungen`).
6. **Rechnung vor Lieferung** lässt Quittieren und Bestandsabbuchung intakt (kein `FAKTURIERT`). Getestet in Task 20.
7. **Planung und Halle im Belege-Dialog:** `GET /invoices` antwortet ihnen mit 403 (`_deps_geld`); der Dialog zeigt dann den grauen Hinweis statt des roten Ladefehlers und keinen Rechnungsknopf. Kein Backend-Test (reines Frontend); am 08.10.2026 in einer Sandbox per Playwright mit abgefangener 403- bzw. 500-Antwort geprüft, Manager-Abnahme nach Task 24.

Keine Schemaänderung, kein `_auto_migrate`.

---

### Task 20: Keine zweite Rechnung zu einer Bestellung

**Files:**
- Modify: `backend/app/services/invoice_service.py` (Importe Zeile 12–21, neue Klasse vor `class InvoiceService:` Zeile 24, `create_invoice` Zeile 30–108, neue Methode vor `finalize_invoice` Zeile 218)
- Modify: `backend/app/api/v1/invoices.py` (Import Zeile 24, `create_invoice` Zeile 106–127, `create_invoice_from_order` Zeile 130–140)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces:
  - `class BereitsAbgerechnet(ValueError)` in `app.services.invoice_service`
  - `InvoiceService.aktive_rechnung_zur_bestellung(self, order_id: UUID) -> Optional[Invoice]`
  - `InvoiceService.create_invoice(...)` wirft `BereitsAbgerechnet`, wenn `order_id` gesetzt, `invoice_type == InvoiceType.RECHNUNG` und eine aktive Rechnung existiert
  - `POST /api/v1/invoices/from-order/{order_id}` und `POST /api/v1/invoices` antworten dann **409**, `detail` nennt Bestellnummer und vorhandene Rechnungsnummer
  - Test-Helfer `_s6_kunde`, `_s6_bestellung`, `_s6_lieferschein`, `_s6_aus_bestellung`, `_s6_finalisieren`, `_s6_storno`, `_s6_lauf`, `_s6_rechnung_ohne_bestellung`, `_s6_pdf_text`, `_s6_ls_an_rechnung` (Tasks 21–24 nutzen sie)

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_gernot_261008.py` anhängen (Kopf aus Task 1; `_s6_lieferschein` reicht `zusaetzlich=true` schon jetzt durch — bis Task 23 ignoriert FastAPI den unbekannten Parameter, danach wird er gebraucht):

```python
# ---------------------------------------------------------------------------
# S6 — Doppelte Abrechnung verhindern
# ---------------------------------------------------------------------------

S6_PREVIEW = "/api/v1/invoices/batch-run/preview"
S6_COMMIT = "/api/v1/invoices/batch-run/commit"


def _s6_kunde(client, name="Ökoring Handels GmbH"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s6_bestellung(client, kunde, liefertag="2026-03-05", menge=10, preis=2.50):
    """Freitext-Position mit ausdrücklichem Satz — bleibt vom A3-Fix unberührt."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": liefertag,
        "lines": [{"product_name": "Erbsen-Schale", "quantity": menge, "unit": "STK",
                   "unit_price": preis, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _s6_lieferschein(client, bestellung, zusaetzlich=False):
    params = {"zusaetzlich": "true"} if zusaetzlich else None
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes",
                    json={}, params=params)
    assert r.status_code == 201, r.text
    return r.json()


def _s6_aus_bestellung(client, bestellung):
    return client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")


def _s6_finalisieren(client, rechnung):
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


def _s6_storno(client, rechnung):
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={
        "reason": "Pfand mit falschem Steuersatz", "reason_code": "PREISFEHLER",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _s6_lauf(client, endpoint):
    r = client.post(endpoint, json={"period_from": "2026-03-01", "period_to": "2026-03-31"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s6_rechnung_ohne_bestellung(client, kunde):
    """Manuelle Rechnung ohne Bestellbezug — schnell, ohne Bestellanlage."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": date.today().isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _s6_pdf_text(client, rechnung):
    from tests.test_documents_preise import _pdf_text
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
    assert r.status_code == 200, r.text
    return _pdf_text(r.content)


def _s6_ls_an_rechnung(client, rechnung):
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return sorted(n["delivery_note_number"] for n in r.json())


class TestS6KeineZweiteRechnungZurBestellung:
    """(a) from-order lehnt ab, solange eine nicht stornierte Rechnung existiert."""

    def test_zweite_rechnung_aus_bestellung_wird_abgelehnt(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        erste = _s6_aus_bestellung(client, bestellung)
        assert erste.status_code == 201, erste.text

        zweite = _s6_aus_bestellung(client, bestellung)

        assert zweite.status_code == 409, zweite.text
        assert erste.json()["invoice_number"] in zweite.json()["detail"]
        alle = client.get("/api/v1/invoices",
                          params={"customer_id": bestellung["customer_id"]}).json()
        assert len(alle) == 1, "Die abgelehnte Rechnung darf nicht gespeichert sein"

    def test_finalisierte_rechnung_sperrt_ebenso(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_finalisieren(client, _s6_aus_bestellung(client, bestellung).json())

        assert _s6_aus_bestellung(client, bestellung).status_code == 409

    def test_nach_storno_ist_neuausstellung_erlaubt(self, client):
        """Runbook S3: RE-00002/4 stornieren und neu ausstellen."""
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        erste = _s6_finalisieren(client, _s6_aus_bestellung(client, bestellung).json())
        _s6_storno(client, erste)

        neu = _s6_aus_bestellung(client, bestellung)

        assert neu.status_code == 201, neu.text
        assert neu.json()["id"] != erste["id"]
        # ... und die Neuausstellung sperrt wieder
        assert _s6_aus_bestellung(client, bestellung).status_code == 409

    def test_sammelrechnung_sperrt_rechnung_aus_bestellung(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        sammel = _s6_lauf(client, S6_COMMIT)["rechnungen"][0]

        r = _s6_aus_bestellung(client, bestellung)

        assert r.status_code == 409, r.text
        assert sammel["invoice_number"] in r.json()["detail"]

    def test_manuelle_rechnung_mit_bestellbezug_wird_abgelehnt(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        assert _s6_aus_bestellung(client, bestellung).status_code == 201

        r = client.post("/api/v1/invoices", json={
            "customer_id": bestellung["customer_id"], "order_id": bestellung["id"],
            "invoice_date": date.today().isoformat(),
        })

        assert r.status_code == 409, r.text

    def test_bestellstatus_bleibt_und_lieferung_ist_weiter_moeglich(self, client):
        """(f) Kein automatisches FAKTURIERT: Rechnung vor Lieferung darf das
        Quittieren (GELIEFERT + Bestandsabbuchung) nicht aushebeln."""
        bestellung = _s6_bestellung(client, _s6_kunde(client),
                                    liefertag=date.today().isoformat())
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
        assert r.status_code == 200, r.text
        ls = _s6_lieferschein(client, bestellung)
        assert _s6_aus_bestellung(client, bestellung).status_code == 201

        assert client.get(f"/api/v1/sales/orders/{bestellung['id']}").json()["status"] == "BESTAETIGT"

        r = client.patch(f"/api/v1/sales/delivery-notes/{ls['id']}/mark-delivered",
                         json={"signed_by": "Fahrer"})
        assert r.status_code == 200, r.text
        assert client.get(f"/api/v1/sales/orders/{bestellung['id']}").json()["status"] == "GELIEFERT"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS6 -v`
Erwartet: 5 FAILED — `test_zweite_rechnung_aus_bestellung_wird_abgelehnt`, `test_finalisierte_rechnung_sperrt_ebenso`, `test_sammelrechnung_sperrt_rechnung_aus_bestellung`, `test_manuelle_rechnung_mit_bestellbezug_wird_abgelehnt` (je Statuscode 201 statt 409) und `test_nach_storno_ist_neuausstellung_erlaubt` (erst die letzte Zeile, `assert 201 == 409`). `test_bestellstatus_bleibt_und_lieferung_ist_weiter_moeglich` ist bereits grün — er schreibt Entscheidung (f) fest.

- [ ] **Step 3: Ausnahme, Abfrage und Sperre im Service**

In `backend/app/services/invoice_service.py`: Import `from sqlalchemy import select, func, and_` → `from sqlalchemy import select, func, and_, or_`.

Modell-Import: direkt nach der Zeile `from app.models.product import Product` einfügen

```python
from app.models.documents import DeliveryNote
```

(Seit Task 2 steht hinter `Product` schon `from app.services.steuersatz import produkt_der_position, steuersatz_der_position`; die neue Zeile kommt trotzdem direkt hinter `Product`. Task 21 nutzt genau diese Zweizeilenfolge als Anker.)

Neue Klasse auf Modulebene: direkt vor `class InvoiceService:` einfügen (zwei Leerzeilen davor und danach)

```python
class BereitsAbgerechnet(ValueError):
    """Zur Bestellung gibt es schon eine nicht stornierte Rechnung.

    Unterklasse von ValueError: bestehende Aufrufer, die ValueError fangen,
    funktionieren weiter. Die API macht daraus 409 statt 400.
    """
```

In `create_invoice`: ersetzen

```python
            raise ValueError("Kunde nicht gefunden")

        # Rechnungsnummer generieren
```

durch

```python
            raise ValueError("Kunde nicht gefunden")

        # Doppelabrechnung: je Bestellung höchstens eine nicht stornierte
        # Rechnung. Gilt für "Rechnung aus Bestellung" und für manuell
        # angelegte Rechnungen mit Bestellbezug. Vor dem Anlegen der neuen
        # Rechnung — danach fände die Abfrage sie selbst.
        if order_id is not None and invoice_type == InvoiceType.RECHNUNG:
            vorhandene = self.aktive_rechnung_zur_bestellung(order_id)
            if vorhandene is not None:
                order = self.db.get(Order, order_id)
                raise BereitsAbgerechnet(
                    f"Zur Bestellung {order.order_number if order else order_id} gibt es "
                    f"bereits die Rechnung {vorhandene.invoice_number} "
                    f"({vorhandene.status.value}). Eine zweite Rechnung ist nicht möglich. "
                    f"Zur Korrektur die Rechnung stornieren und danach neu ausstellen."
                )

        # Rechnungsnummer generieren
```

Neue Methode: direkt vor `def finalize_invoice(self, invoice_id: UUID) -> Invoice:` einfügen

```python
    def aktive_rechnung_zur_bestellung(self, order_id: UUID) -> Optional[Invoice]:
        """Die nicht stornierte Rechnung, in der die Bestellung steckt, sonst None.

        Zwei Wege führen von der Bestellung zur Rechnung:
        - Rechnung aus Bestellung: Invoice.order_id
        - Sammelrechnung: ein Lieferschein der Bestellung trägt invoice_id
        Nur Typ RECHNUNG zählt: Gutschriften (Storno), Proforma und
        Abschlagsrechnungen sperren nicht.
        """
        return self.db.execute(
            select(Invoice)
            .where(
                Invoice.invoice_type == InvoiceType.RECHNUNG,
                Invoice.status != InvoiceStatus.STORNIERT,
                or_(
                    Invoice.order_id == order_id,
                    Invoice.id.in_(
                        select(DeliveryNote.invoice_id).where(
                            DeliveryNote.order_id == order_id,
                            DeliveryNote.invoice_id.is_not(None),
                        )
                    ),
                ),
            )
            .order_by(Invoice.invoice_number)
            .limit(1)
        ).scalars().first()
```

- [ ] **Step 4: 409 in der API**

In `backend/app/api/v1/invoices.py`: Import `from app.services.invoice_service import InvoiceService` → `from app.services.invoice_service import InvoiceService, BereitsAbgerechnet`.

In `create_invoice` **und** `create_invoice_from_order` jeweils vor `except ValueError as e:` einfügen:

```python
    except BereitsAbgerechnet as e:
        raise HTTPException(status_code=409, detail=str(e))
```

`BereitsAbgerechnet` ist eine Unterklasse von `ValueError` — der neue Zweig muss **vor** `except ValueError` stehen, sonst wird 400 daraus.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_sammelrechnung.py tests/test_storno.py -v`
Erwartet: alle passed (davon 6 `TestS6`).

- [ ] **Step 6: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`. Besonders `test_gernot_260817.py`, `test_gernot_260821.py` (rufen `from-order` je Bestellung einmal auf) und `test_documents_preise.py` beachten.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/invoice_service.py backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): keine zweite Rechnung zu einer bereits berechneten Bestellung"
```

---

### Task 21: „Rechnung aus Bestellung" hängt den Lieferschein an — PDF bleibt unverändert

**Files:**
- Modify: `backend/app/services/invoice_service.py` (Importe, neue Funktion `waehle_vertreter` vor `class InvoiceService`, Ende von `create_invoice_from_order` Zeile 210-216)
- Modify: `backend/app/services/pdf_service.py` (Anlagen-Block, auf `c4a1832` Zeile 371-373)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: Helfer aus Task 20; bestehender R1.6-Block in `cancel_invoice` (löst `invoice_id` beim Storno).
- Produces:
  - `waehle_vertreter(lieferscheine) -> Optional[DeliveryNote]` (modulweit in `app.services.invoice_service`; Task 22 nutzt sie)
  - `create_invoice_from_order` setzt `invoice_id` an genau einem bisher nicht zugeordneten Lieferschein der Bestellung
  - `PDFService.generate_invoice_pdf` druckt „Enthaltene Lieferscheine" nur bei `invoice.order_id is None`

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS6LieferscheinHaengtAnDerRechnung:
    """(b) from-order verknüpft den Lieferschein; Storno löst, Neuausstellung verknüpft neu."""

    def test_rechnung_aus_bestellung_verknuepft_den_lieferschein(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        ls = _s6_lieferschein(client, bestellung)

        rechnung = _s6_aus_bestellung(client, bestellung).json()

        assert _s6_ls_an_rechnung(client, rechnung) == [ls["delivery_note_number"]]

    def test_storno_loest_und_neuausstellung_verknuepft_neu(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        ls = _s6_lieferschein(client, bestellung)
        erste = _s6_finalisieren(client, _s6_aus_bestellung(client, bestellung).json())

        _s6_storno(client, erste)
        assert _s6_ls_an_rechnung(client, erste) == []

        neu = _s6_aus_bestellung(client, bestellung).json()
        assert _s6_ls_an_rechnung(client, neu) == [ls["delivery_note_number"]]

    def test_bei_zwei_lieferscheinen_haengt_genau_einer_an(self, client):
        """Die PDF-Tabelle 'Enthaltene Lieferscheine' zeigt je Lieferschein die
        volle Bestellsumme — zwei Einträge würden sie doppelt ausweisen."""
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        ls1 = _s6_lieferschein(client, bestellung)
        _s6_lieferschein(client, bestellung, zusaetzlich=True)

        rechnung = _s6_aus_bestellung(client, bestellung).json()

        assert _s6_ls_an_rechnung(client, rechnung) == [ls1["delivery_note_number"]]

    def test_pdf_mit_bestellbezug_bekommt_keine_lieferscheinanlage(self, client):
        """GoBD: die Anlage liest DeliveryNote.invoice_id, und die löst ein
        Storno wieder. Bei Rechnungen mit Bestellbezug würde sich das PDF
        nachträglich ändern — deshalb dort keine Anlage."""
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        rechnung = _s6_aus_bestellung(client, bestellung).json()

        assert b"Enthaltene Lieferscheine" not in _s6_pdf_text(client, rechnung)

    def test_sammelrechnung_behaelt_die_lieferscheinanlage(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        sammel = _s6_lauf(client, S6_COMMIT)["rechnungen"][0]

        assert b"Enthaltene Lieferscheine" in _s6_pdf_text(client, sammel)
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS6LieferscheinHaengtAnDerRechnung -v`
Erwartet: 3 FAILED — die drei Verknüpfungs-Tests mit `assert [] == ['LS-…-0001']`. Grün sind `test_sammelrechnung_behaelt_die_lieferscheinanlage` (den `NameError` im Sammelrechnungs-PDF hat Task 10 behoben) und `test_pdf_mit_bestellbezug_bekommt_keine_lieferscheinanlage`; dieser **muss grün bleiben** — er fängt den GoBD-Rückschritt, den Step 3 ohne Step 4 erzeugen würde.

- [ ] **Step 3: Vertreter wählen und anhängen**

In `backend/app/services/invoice_service.py`:

Import: ersetzen (Zweizeilen-Anker auf Modulebene; `from app.models.documents import DeliveryNote` allein ist mehrdeutig, weil `cancel_invoice` dieselbe Zeile eingerückt als lokalen Import hat, heute `invoice_service.py:312`)

```python
from app.models.product import Product
from app.models.documents import DeliveryNote
```

durch

```python
from app.models.product import Product
from app.models.documents import DeliveryNote
from app.models.enums import DeliveryNoteStatus
```

Den lokalen Import in `cancel_invoice` nicht anfassen (R1.6-Block).

Neue Funktion auf Modulebene: direkt vor `class InvoiceService:` einfügen, also zwischen `BereitsAbgerechnet` (Task 20) und `class InvoiceService:`

```python
def waehle_vertreter(lieferscheine):
    """Der Lieferschein, der eine Bestellung in der Abrechnung vertritt.

    Der älteste quittierte (Liefernachweis, tatsächliches Lieferdatum), sonst
    der älteste überhaupt. Die Nummer LS-JJJJMMTT-NNNN sortiert chronologisch
    und ist — anders als created_at — nie mal naiv, mal mit Zeitzone.

    Genau EIN Vertreter je Bestellung: die PDF-Tabelle "Enthaltene
    Lieferscheine" (pdf_service) zeigt je Lieferschein die volle
    Bestellsumme; zwei Einträge würden sie doppelt ausweisen.
    """
    if not lieferscheine:
        return None
    return min(
        lieferscheine,
        key=lambda n: (n.status != DeliveryNoteStatus.GELIEFERT, n.delivery_note_number),
    )
```

Ende von `create_invoice_from_order`: ersetzen

```python
        self.db.refresh(invoice, ["lines"])
        invoice.calculate_totals()

        return invoice
```

durch

```python
        self.db.refresh(invoice, ["lines"])
        invoice.calculate_totals()

        # Abrechnungsstatus am Lieferschein (R2.5). Ohne diese Zuordnung sah
        # der Sammellauf die Bestellung als offen. Nur ein noch nicht
        # zugeordneter Lieferschein, genau einer je Bestellung.
        offene = self.db.execute(
            select(DeliveryNote).where(
                DeliveryNote.order_id == order_id,
                DeliveryNote.invoice_id.is_(None),
            )
        ).scalars().all()
        vertreter = waehle_vertreter(offene)
        if vertreter is not None:
            vertreter.invoice_id = invoice.id
            self.db.flush()

        return invoice
```

- [ ] **Step 4: PDF — Anlage nur ohne Bestellbezug**

`from decimal import Decimal` steht seit Task 10 am Kopf von `backend/app/services/pdf_service.py`; nicht erneut einfügen.

Den Anfang des Anlagen-Blocks ersetzen:

```python
        # der Kunde muss nachvollziehen können, welche Lieferungen drinstecken.
        if db is not None:
```

durch

```python
        # der Kunde muss nachvollziehen können, welche Lieferungen drinstecken.
        # Nur ohne Bestellbezug (= Sammelrechnung): die Tabelle liest
        # DeliveryNote.invoice_id, und die setzt "Rechnung aus Bestellung"
        # und löst ein Storno. Bei Rechnungen mit Bestellbezug würde sich das
        # PDF sonst nachträglich ändern (GoBD).
        if db is not None and invoice.order_id is None:
```

Nichts sonst im Block ändern.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_sammelrechnung.py tests/test_storno.py -v`
Erwartet: alle passed (davon 11 `TestS6`).

- [ ] **Step 6: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`. Besonders `test_gernot_260817.py::TestRechnungsadresse` und `test_gernot_260821.py` beachten (lesen Text aus Rechnungs-PDFs mit Bestellbezug).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/invoice_service.py backend/app/services/pdf_service.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): Rechnung aus Bestellung hängt den Lieferschein an; Lieferschein-Anlage nur ohne Bestellbezug"
```

---

### Task 22: Sammellauf berechnet jede Bestellung höchstens einmal

**Files:**
- Modify: `backend/app/services/invoice_service.py` (neue Methode vor `finalize_invoice`)
- Modify: `backend/app/api/v1/invoices.py` (Import Zeile 24, `_abrechenbare_lieferscheine` Zeile 521-545)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `waehle_vertreter` (Task 21), Regel aus `aktive_rechnung_zur_bestellung` (Task 20).
- Produces:
  - `InvoiceService.abgerechnete_bestellungen(self) -> set[UUID]`
  - `_abrechenbare_lieferscheine(db, anfrage)` liefert weiter `list[tuple[DeliveryNote, date]]`, jetzt mit höchstens einem Eintrag je Bestellung, ohne abgerechnete Bestellungen und ohne Bestellungen auf `FAKTURIERT`. Rückgabeform unverändert → `_aggregiere`, `batch_run_preview`, `batch_run_commit` bleiben unberührt.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS6SammellaufRechnetJedeBestellungEinmal:
    """(c) Vorschau und Festschreiben: abgerechnete Bestellungen raus, je Bestellung einmal."""

    def test_bestellung_mit_rechnung_aus_bestellung_wird_uebersprungen(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        assert _s6_aus_bestellung(client, bestellung).status_code == 201

        assert _s6_lauf(client, S6_PREVIEW)["kunden"] == []
        assert _s6_lauf(client, S6_COMMIT)["rechnungen"] == []

    def test_altbestand_ohne_verknuepfung_wird_uebersprungen(self, client):
        """RE-00002/3/4: vor S6 aus Bestellung erzeugt, Lieferschein ohne invoice_id."""
        from uuid import UUID
        from app.models.documents import DeliveryNote
        from tests.conftest import TestingSessionLocal

        bestellung = _s6_bestellung(client, _s6_kunde(client))
        ls = _s6_lieferschein(client, bestellung)
        assert _s6_aus_bestellung(client, bestellung).status_code == 201
        with TestingSessionLocal() as db:
            db.get(DeliveryNote, UUID(ls["id"])).invoice_id = None
            db.commit()

        assert _s6_lauf(client, S6_PREVIEW)["kunden"] == []
        assert _s6_lauf(client, S6_COMMIT)["rechnungen"] == []

    def test_nach_storno_rechnet_der_lauf_die_bestellung_wieder(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        _s6_storno(client, _s6_finalisieren(client, _s6_aus_bestellung(client, bestellung).json()))

        kunden = _s6_lauf(client, S6_PREVIEW)["kunden"]

        assert len(kunden) == 1
        assert kunden[0]["anzahl_lieferscheine"] == 1

    def test_zwei_lieferscheine_einer_bestellung_werden_einmal_berechnet(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client), menge=10, preis=2.50)
        ls1 = _s6_lieferschein(client, bestellung)
        _s6_lieferschein(client, bestellung, zusaetzlich=True)

        k = _s6_lauf(client, S6_PREVIEW)["kunden"][0]
        assert k["anzahl_lieferscheine"] == 1
        assert Decimal(str(k["summe_netto"])) == Decimal("25.00")

        rechnung = _s6_lauf(client, S6_COMMIT)["rechnungen"][0]
        assert Decimal(str(rechnung["subtotal"])) == Decimal("25.00")
        assert _s6_ls_an_rechnung(client, rechnung) == [ls1["delivery_note_number"]]
        assert _s6_lauf(client, S6_COMMIT)["rechnungen"] == []

    def test_quittierter_lieferschein_vertritt_die_bestellung(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        # Manager 08.10. (Paket 2, Entscheidung E5): Quittieren setzt ab Paket 2 eine
        # bestätigte Bestellung voraus — ENTWURF → GELIEFERT ist kein erlaubter Übergang.
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
        assert r.status_code == 200, r.text
        _s6_lieferschein(client, bestellung)
        ls2 = _s6_lieferschein(client, bestellung, zusaetzlich=True)
        r = client.patch(f"/api/v1/sales/delivery-notes/{ls2['id']}/mark-delivered",
                         json={"signed_by": "Fahrer", "actual_delivery_date": "2026-03-06"})
        assert r.status_code == 200, r.text

        rechnung = _s6_lauf(client, S6_COMMIT)["rechnungen"][0]

        assert _s6_ls_an_rechnung(client, rechnung) == [ls2["delivery_note_number"]]

    def test_fakturierte_bestellung_ohne_rechnung_wird_uebersprungen(self, client):
        """Spec-Nachtrag 08.10.2026: FAKTURIERT heißt abgerechnet — auch ohne
        Rechnung im System (z. B. außerhalb von NovaERP berechnet). Bisher
        rechnete der Lauf sie trotzdem ab, sobald sie einen freien Lieferschein
        hatte (Nachtrag T4, Probe P7)."""
        from uuid import UUID
        from app.models.enums import OrderStatus
        from app.models.order import Order

        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        # Zustand wie nach dem manuellen Übergang GELIEFERT → FAKTURIERT
        with TestingSessionLocal() as db:
            db.get(Order, UUID(bestellung["id"])).status = OrderStatus.FAKTURIERT
            db.commit()

        assert _s6_lauf(client, S6_PREVIEW)["kunden"] == []
        assert _s6_lauf(client, S6_COMMIT)["rechnungen"] == []
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS6SammellaufRechnetJedeBestellungEinmal -v`
Erwartet: 4 FAILED — `test_fakturierte_bestellung_ohne_rechnung_wird_uebersprungen` (Vorschau nicht leer: `assert [{'anzahl_lieferscheine': 1, …}] == []`, in einer Prüfkopie nachgestellt), `test_altbestand_ohne_verknuepfung_wird_uebersprungen` (Vorschau nicht leer: genau der Fall RE-00002/3/4), `test_zwei_lieferscheine_einer_bestellung_werden_einmal_berechnet` (`assert 2 == 1`), `test_quittierter_lieferschein_vertritt_die_bestellung` (beide Lieferscheine hängen an der Rechnung). Grün sind `test_bestellung_mit_rechnung_aus_bestellung_wird_uebersprungen` (seit Task 21: die Verknüpfung nimmt den Lieferschein aus dem Lauf) und `test_nach_storno_rechnet_der_lauf_die_bestellung_wieder` (schon auf `c4a1832`: ohne Verknüpfung bleibt der Lieferschein frei). Beide belegen keinen Fix, sie sichern ab, dass die Neufassung in Step 4 diese Fälle nicht verschlechtert — der zweite insbesondere, dass `abgerechnete_bestellungen` stornierte Rechnungen ausnimmt.

- [ ] **Step 3: Menge der abgerechneten Bestellungen**

In `backend/app/services/invoice_service.py`, neue Methode: direkt vor `def finalize_invoice(self, invoice_id: UUID) -> Invoice:` einfügen

```python
    def abgerechnete_bestellungen(self) -> set[UUID]:
        """IDs aller Bestellungen mit nicht stornierter Rechnung.

        Dieselbe Regel wie aktive_rechnung_zur_bestellung, als Menge für den
        Sammellauf (eine Abfrage je Weg statt einer je Bestellung).
        """
        aktiv = (
            Invoice.invoice_type == InvoiceType.RECHNUNG,
            Invoice.status != InvoiceStatus.STORNIERT,
        )
        ueber_bestellung = self.db.execute(
            select(Invoice.order_id).where(Invoice.order_id.is_not(None), *aktiv)
        ).scalars().all()
        ueber_lieferschein = self.db.execute(
            select(DeliveryNote.order_id)
            .join(Invoice, DeliveryNote.invoice_id == Invoice.id)
            .where(*aktiv)
        ).scalars().all()
        return set(ueber_bestellung) | set(ueber_lieferschein)
```

- [ ] **Step 4: Abrechenbare Lieferscheine je Bestellung**

In `backend/app/api/v1/invoices.py`: Import `from app.services.invoice_service import InvoiceService, BereitsAbgerechnet` → `from app.services.invoice_service import InvoiceService, BereitsAbgerechnet, waehle_vertreter`.

**Vor dem Ersetzen vergleichen** (aus dem Repo-Wurzelverzeichnis; schreibt nichts):

```bash
diff <(git show c4a1832:backend/app/api/v1/invoices.py | awk '/^def _abrechenbare_lieferscheine/{f=1} /^def _aggregiere/{f=0} f') \
     <(awk '/^def _abrechenbare_lieferscheine/{f=1} /^def _aggregiere/{f=0} f' backend/app/api/v1/invoices.py) \
  && echo "unverändert seit c4a1832"
```

Erwartet: `unverändert seit c4a1832` (am 08.10.2026 auf `c4a1832` geprüft; S1–S5 ändern die Funktion nach heutigem Stand nicht). Gibt `diff` etwas aus, hat ein früherer Abschnitt die Funktion geändert (z. B. Eager Loading, zusätzliche Filter): jede dieser Änderungen sinngemäß in die neue Fassung unten übernehmen — Abfrage-Optionen in die `select(DeliveryNote)`-Abfrage, Filter in die Schleife über `je_bestellung` — und in der Abschlussmeldung mit der `diff`-Ausgabe nennen. Nichts davon stillschweigend verwerfen; ist die Übernahme nicht eindeutig: stoppen und melden.

Dann die Funktion `_abrechenbare_lieferscheine` (heute Zeile 521-545) vollständig ersetzen. Zeitraum- und Kundenfilter sind wörtlich übernommen, nur gelten sie jetzt für den Vertreter. Neu ist der Ausschluss von `FAKTURIERT` (Spec-Nachtrag 08.10.2026, Sofort-Fix der Doppelabrechnungssperre):

```python
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
    das Wunschlieferdatum der Bestellung. Stornierte und fakturierte
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
        leistungsdatum = note.actual_delivery_date or note.order.requested_delivery_date
        if not (anfrage.period_from <= leistungsdatum <= anfrage.period_to):
            continue
        if anfrage.customer_ids and note.order.customer_id not in anfrage.customer_ids:
            continue
        ergebnis.append((note, leistungsdatum))
    return ergebnis
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_sammelrechnung.py tests/test_storno.py -v`
Erwartet: alle passed (davon 17 `TestS6`; in der Prüfkopie mit S1, Tasks 8–12, 16, 20–28 nachgestellt). `test_sammelrechnung.py` ist der Beleg, dass der normale Lauf (je Bestellung ein Lieferschein) unverändert rechnet.

- [ ] **Step 6: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`. Besonders `test_warenfluss.py` beachten.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/invoice_service.py backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "fix(sammelrechnung): abgerechnete Bestellungen überspringen, je Bestellung nur einmal berechnen"
```

---

### Task 23: Zweiter Lieferschein nur mit Bestätigung

**Files:**
- Modify: `backend/app/api/v1/documents.py:185-198` (`create_delivery_note`)
- Modify: `frontend/src/services/api.ts:1385-1386` (`documentsApi.createDeliveryNote`)
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx:117-121` und `:211-218`
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/sales/orders/{order_id}/delivery-notes?zusaetzlich=true|false` — ohne `zusaetzlich=true` und mit vorhandenem Lieferschein: **409**, `detail` nennt die vorhandenen Lieferscheinnummern
  - `documentsApi.createDeliveryNote(orderId, data, opts?: { zusaetzlich?: boolean })` — dritter Parameter optional; `Tagesplan.tsx:61` ruft weiter mit zwei Argumenten

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS6ZweiterLieferschein:
    """(d) Ein weiterer Lieferschein nur mit ausdrücklicher Bestätigung."""

    def test_zweiter_lieferschein_braucht_bestaetigung(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        ls1 = _s6_lieferschein(client, bestellung)

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})

        assert r.status_code == 409, r.text
        assert ls1["delivery_note_number"] in r.json()["detail"]
        alle = client.get(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes").json()
        assert len(alle) == 1

    def test_mit_bestaetigung_wird_er_angelegt(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        ls1 = _s6_lieferschein(client, bestellung)

        ls2 = _s6_lieferschein(client, bestellung, zusaetzlich=True)

        assert ls2["delivery_note_number"] != ls1["delivery_note_number"]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS6ZweiterLieferschein -v`
Erwartet: `test_zweiter_lieferschein_braucht_bestaetigung` FAILED (201 statt 409); `test_mit_bestaetigung_wird_er_angelegt` grün.

- [ ] **Step 3: Backend**

In `backend/app/api/v1/documents.py`: ersetzen

```python
def create_delivery_note(order_id: UUID, data: DeliveryNoteCreate, db: DBSession):
    """Lieferschein + zugehörige Verpackungsliste anlegen.

    Falls `packing_items` leer ist, werden Items 1:1 aus den Order-Lines
    übernommen (ohne Pfand-Container).
    """
    order = _load_order_with_lines(db, order_id)
    if not order.lines:
        raise HTTPException(status_code=400, detail="Bestellung hat keine Positionen")
```

durch

```python
def create_delivery_note(
    order_id: UUID,
    data: DeliveryNoteCreate,
    db: DBSession,
    zusaetzlich: bool = False,
):
    """Lieferschein + zugehörige Verpackungsliste anlegen.

    Falls `packing_items` leer ist, werden Items 1:1 aus den Order-Lines
    übernommen (ohne Pfand-Container).

    Ein weiterer Lieferschein zu derselben Bestellung nur mit
    `?zusaetzlich=true`. Abgerechnet wird die Bestellung (einmal), nicht der
    Lieferschein — ein zweiter ist also kein Abrechnungsrisiko mehr, aber fast
    immer ein Versehen. Gewollt ist er, wenn die Bestellung nach dem ersten
    Lieferschein geändert wurde und die Packliste (ein Schnappschuss) neu
    gebraucht wird.
    """
    order = _load_order_with_lines(db, order_id)
    if not order.lines:
        raise HTTPException(status_code=400, detail="Bestellung hat keine Positionen")

    vorhandene = db.execute(
        select(DeliveryNote.delivery_note_number)
        .where(DeliveryNote.order_id == order.id)
        .order_by(DeliveryNote.delivery_note_number)
    ).scalars().all()
    if vorhandene and not zusaetzlich:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Zu dieser Bestellung gibt es bereits den Lieferschein "
                f"{', '.join(vorhandene)}. Ein weiterer Lieferschein wird nicht "
                f"zusätzlich berechnet; er ist nur nötig, wenn die Packliste nach "
                f"einer Bestelländerung neu erstellt werden muss."
            ),
        )
```

`zusaetzlich: bool = False` ist ein Query-Parameter (FastAPI behandelt einfache Typen neben einem Body-Modell als Query). `select` und `DeliveryNote` sind in `documents.py` bereits importiert.

- [ ] **Step 4: Frontend**

In `frontend/src/services/api.ts`: ersetzen

```ts
  createDeliveryNote: (orderId: string, data: { notes?: string; total_weight_g?: number; total_packages?: number; packing_items?: Partial<PackingListItem>[] }) =>
    api.post<DeliveryNote>(`/sales/orders/${orderId}/delivery-notes`, data).then(r => r.data),
```

durch

```ts
  // zusaetzlich: weiterer Lieferschein zu einer Bestellung, die schon einen
  // hat — ohne das Flag antwortet das Backend mit 409.
  createDeliveryNote: (orderId: string, data: { notes?: string; total_weight_g?: number; total_packages?: number; packing_items?: Partial<PackingListItem>[] }, opts?: { zusaetzlich?: boolean }) =>
    api.post<DeliveryNote>(`/sales/orders/${orderId}/delivery-notes`, data, {
      params: opts?.zusaetzlich ? { zusaetzlich: true } : undefined,
    }).then(r => r.data),
```

In `frontend/src/components/domain/OrderDocumentsModal.tsx`: ersetzen

```tsx
  const createDeliveryNote = useMutation({
    mutationFn: () => documentsApi.createDeliveryNote(orderId!, {}),
    onSuccess: (n) => { toast.success(`Lieferschein ${n.delivery_note_number} erstellt`); invalidate(); },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Fehler beim Erstellen des Lieferscheins')),
  });
```

durch

```tsx
  const createDeliveryNote = useMutation({
    mutationFn: (zusaetzlich: boolean) => documentsApi.createDeliveryNote(orderId!, {}, { zusaetzlich }),
    onSuccess: (n) => { toast.success(`Lieferschein ${n.delivery_note_number} erstellt`); invalidate(); },
    onError: (e: any) => {
      // 409 = es gibt schon einen Lieferschein; das fragt neuerLieferschein() nach.
      if (e?.response?.status === 409) return;
      toast.error(getErrorMessage(e, 'Fehler beim Erstellen des Lieferscheins'));
    },
  });

  const neuerLieferschein = async () => {
    try {
      await createDeliveryNote.mutateAsync(false);
    } catch (e: any) {
      if (e?.response?.status !== 409) return; // Fehlermeldung kam schon aus onError
      if (!window.confirm(`${getErrorMessage(e)}\n\nTrotzdem einen weiteren Lieferschein anlegen?`)) return;
      await createDeliveryNote.mutateAsync(true).catch(() => undefined);
    }
  };
```

Am Knopf „Neuer LS“: ersetzen

```tsx
              loading={createDeliveryNote.isPending}
              onClick={() => createDeliveryNote.mutate()}
```

durch

```tsx
              loading={createDeliveryNote.isPending}
              onClick={neuerLieferschein}
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_rollen.py tests/test_documents_preise.py -v`
Erwartet: alle passed. `test_rollen.py:200-204` prüft nur `code != 403`: Der Aufruf dort schickt keinen Body und endet schon an der Validierung mit 422; mit Body und fremder ID käme 404 aus `_load_order_with_lines` (`documents.py:60-68`), das vor der neuen Prüfung läuft (beides am 08.10.2026 nachgestellt). Die neue 409 ändert daran nichts.
Run: `cd frontend && npm run build`
Erwartet: ohne TypeScript-Fehler (verifiziert: `tsc` fehlerfrei; Hinweis „Some chunks are larger than 500 kB" ist alt).
Die Playwright-Suite führt der Worker nicht aus (braucht laufendes Backend und Frontend). Ihren Belege-Test passt Task 24 Step 5 an.

- [ ] **Step 6: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`. Besonders `test_gernot_260821.py` und `test_gernot_260824.py` beachten (legen je Bestellung einen Lieferschein an).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/documents.py frontend/src/services/api.ts \
        frontend/src/components/domain/OrderDocumentsModal.tsx backend/tests/test_gernot_261008.py
git commit -m "fix(lieferschein): zweiter Lieferschein zu einer Bestellung nur nach Rückfrage"
```

---

### Task 24: Belege-Dialog fragt Rechnungen je Bestellung serverseitig ab

**Files:**
- Modify: `backend/app/api/v1/invoices.py` (Importe Zeile 10-16, `list_invoices` Zeile 36-68)
- Modify: `frontend/src/services/api.ts:711-712` (`invoicesApi.list`)
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx:43-47`, `:136`, `:288-298`
- Modify: `frontend/tests/e2e/full-suite.spec.ts:162-171` (Test `open belege-modal + generate AB + LS + Rechnung`, Zeile 160)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Produces: `GET /api/v1/invoices?order_id=<uuid>` — Rechnungen mit `Invoice.order_id` = Bestellung **oder** mit einem Lieferschein der Bestellung (Sammelrechnung); kombinierbar mit den übrigen Filtern; Pagination unverändert.
- Consumes (Frontend): `Invoice.invoice_type` und `Invoice.status` aus `InvoiceResponse` (beide vorhanden, `schemas/invoice.py:116`, `:170`).

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS6RechnungenJeBestellung:
    """(e) GET /invoices?order_id= — Grundlage des Belege-Dialogs."""

    def test_filter_findet_die_rechnung_jenseits_der_ersten_seite(self, client):
        """Der Dialog filterte die 20 neuesten Rechnungen — ab Rechnung 21 fehlte sie."""
        kunde = _s6_kunde(client)
        ziel = _s6_bestellung(client, kunde)
        rechnung = _s6_aus_bestellung(client, ziel).json()
        for _ in range(21):
            _s6_rechnung_ohne_bestellung(client, kunde)

        r = client.get("/api/v1/invoices", params={"order_id": ziel["id"]})

        assert r.status_code == 200, r.text
        assert [i["id"] for i in r.json()] == [rechnung["id"]]

    def test_filter_findet_die_sammelrechnung_ueber_den_lieferschein(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
        sammel = _s6_lauf(client, S6_COMMIT)["rechnungen"][0]
        _s6_rechnung_ohne_bestellung(client, _s6_kunde(client, name="Großer Kern"))

        r = client.get("/api/v1/invoices", params={"order_id": bestellung["id"]})

        assert [i["id"] for i in r.json()] == [sammel["id"]]

    def test_stornierte_und_neue_rechnung_erscheinen_beide(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        erste = _s6_finalisieren(client, _s6_aus_bestellung(client, bestellung).json())
        _s6_storno(client, erste)
        neu = _s6_aus_bestellung(client, bestellung).json()
        _s6_rechnung_ohne_bestellung(client, _s6_kunde(client, name="Großer Kern"))

        r = client.get("/api/v1/invoices", params={"order_id": bestellung["id"]})

        rechnungen = {(i["id"], i["status"]) for i in r.json() if i["invoice_type"] == "RECHNUNG"}
        assert rechnungen == {(erste["id"], "STORNIERT"), (neu["id"], "ENTWURF")}
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS6RechnungenJeBestellung -v`
Erwartet: 3 FAILED — FastAPI ignoriert den unbekannten Parameter `order_id`, die Antwort ist die ungefilterte (beim ersten Test auf 20 gekürzte) Liste.

- [ ] **Step 3: Filter im Backend**

In `backend/app/api/v1/invoices.py`: Import `from sqlalchemy import select` → `from sqlalchemy import select, or_`.

Modell-Importe: direkt nach diesem Block

```python
    InvoiceStatus, InvoiceType, PaymentMethod
)
```

einfügen

```python
from app.models.documents import DeliveryNote
```

Die bestehende Zeile `from app.models.documents import DeliveryNote` weiter unten (Zeile 508, Sammelrechnungsblock) bleibt; doppelter Import ist harmlos.

Signatur von `list_invoices`: ersetzen

```python
    to_date: Optional[date] = None,
):
    """Listet alle Rechnungen mit optionaler Filterung."""
```

durch

```python
    to_date: Optional[date] = None,
    order_id: Optional[UUID] = None,
):
    """Listet alle Rechnungen mit optionaler Filterung."""
```

Filter: direkt nach `query = query.where(Invoice.invoice_type == invoice_type)` einfügen

```python
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
```

- [ ] **Step 4: Frontend**

In `frontend/src/services/api.ts` im Parametertyp von `invoicesApi.list` `order_id?: string` ergänzen: `list: (params?: { status?: InvoiceStatus; customer_id?: string; invoice_type?: InvoiceType; from_date?: string; to_date?: string })` → `list: (params?: { status?: InvoiceStatus; customer_id?: string; invoice_type?: InvoiceType; from_date?: string; to_date?: string; order_id?: string })`

In `frontend/src/components/domain/OrderDocumentsModal.tsx`: ersetzen

```tsx
  const invoicesQuery = useQuery({
    queryKey: ['order-invoices', orderId],
    queryFn: () => invoicesApi.list({}).then((rows) => rows.filter((i: Invoice) => i.order_id === orderId)),
    enabled: open && !!orderId,
  });
```

durch

```tsx
  // Serverseitig gefiltert: Rechnung aus Bestellung (order_id) und
  // Sammelrechnung (über den Lieferschein). Früher wurden die 20 neuesten
  // Rechnungen clientseitig gefiltert — ab Rechnung 21 stand hier "keine
  // Rechnung", und der Knopf erzeugte eine Doppelrechnung.
  const invoicesQuery = useQuery({
    queryKey: ['order-invoices', orderId],
    queryFn: () => invoicesApi.list({ order_id: orderId! }),
    enabled: open && !!orderId,
  });
```

Regel für den Knopf: direkt nach `const invoices = invoicesQuery.data || [];` einfügen

```tsx
  // Rechnungen gehören zur Geldseite (main.py: _deps_geld = sales, accounting,
  // admin). Planung und Halle öffnen den Dialog wegen der Lieferscheine auch,
  // GET /invoices antwortet ihnen mit 403 — das ist kein Ladefehler.
  const ohneRechnungsrecht = (invoicesQuery.error as any)?.response?.status === 403;
  // Gleiche Regel wie das Backend (InvoiceService.aktive_rechnung_zur_bestellung):
  // eine nicht stornierte Rechnung vom Typ RECHNUNG sperrt die nächste.
  const aktiveRechnung = invoices.find((i: Invoice) => i.invoice_type === 'RECHNUNG' && i.status !== 'STORNIERT');
  // Ohne frisch geladene Liste kein Knopf: lieber einmal zu wenig anbieten als doppelt berechnen.
  const rechnungMoeglich = invoicesQuery.isSuccess && !invoicesQuery.isFetching && !aktiveRechnung;
```

Knopf und Leerzustand im Abschnitt „Rechnungen“: ersetzen

```tsx
            <Button
              size="sm"
              icon={<Plus className="w-3 h-3" />}
              loading={createInvoice.isPending}
              onClick={() => createInvoice.mutate()}
            >
              Rechnung aus Bestellung
            </Button>
          </div>
          {invoices.length === 0 ? (
```

durch

```tsx
            {rechnungMoeglich && (
              <Button
                size="sm"
                icon={<Plus className="w-3 h-3" />}
                loading={createInvoice.isPending}
                onClick={() => createInvoice.mutate()}
              >
                Rechnung aus Bestellung
              </Button>
            )}
          </div>
          {ohneRechnungsrecht ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              Rechnungen sehen nur Vertrieb und Buchhaltung.
            </p>
          ) : invoicesQuery.isError ? (
            <p className="text-sm text-red-700 dark:text-red-300">
              Rechnungen zu dieser Bestellung konnten nicht geladen werden. Bitte den Dialog neu öffnen.
            </p>
          ) : invoices.length === 0 ? (
```

`createInvoice.onError` zeigt eine 409 aus dem Backend bereits über `getErrorMessage` an — dort nichts ändern.

- [ ] **Step 5: E2E-Test des Belege-Dialogs anpassen**

Der Test `open belege-modal + generate AB + LS + Rechnung` klickt heute `Rechnung aus Bestellung` bedingungslos. Nach Task 24 fehlt der Knopf, sobald die Bestellung eine aktive Rechnung hat — beim zweiten Lauf auf derselben Bestellung liefe der Klick in den Timeout (`actionTimeout: 8_000`, `playwright.config.ts:14`). Nach Task 23 erscheint bei vorhandenem Lieferschein `window.confirm`; Playwright lehnt Dialoge ohne Handler ab, es entsteht kein zweiter Lieferschein — das ist hier gewollt, der vorhandene genügt. Unabhängig von S6 erreicht der Test den Dialog heute gar nicht: Die erste `[class*=card]` der Seite ist der Filterkasten, nicht die Bestellkarte (`Orders.tsx:383` öffnet den Dialog über `OrderCard`). Am 08.10.2026 nachgestellt: Der unveränderte Test scheitert auf `c4a1832` an `getByRole('button', { name: /Neue AB/ })` (Timeout).

In `frontend/tests/e2e/full-suite.spec.ts`: ersetzen

```ts
    // erster Order-Card-Klick → Belege-Modal
    const firstCard = page.locator('[class*=card]').first();
    await firstCard.click();
    await page.getByRole('button', { name: /Neue AB/ }).click();
    await page.getByRole('button', { name: /Neuer LS/ }).click();
    await page.getByRole('button', { name: /Rechnung aus Bestellung/ }).click();
    // Erwarte mindestens je einen Beleg in der Liste
    await expect(page.locator('text=AB-')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=LS-')).toBeVisible();
    await expect(page.locator('text=RE-')).toBeVisible();
```

durch

```ts
    // erster Order-Card-Klick → Belege-Modal. Die erste .card der Seite ist
    // der Filterkasten, deshalb die erste Karte mit Bestellnummer.
    const firstCard = page.locator('[class*=card]').filter({ hasText: /BE-/ }).first();
    await firstCard.click();
    const belege = page.getByRole('dialog');
    // Rechnung zuerst, solange keine andere Abfrage neu lädt. "Rechnung aus
    // Bestellung" erscheint nur bei geladener Liste ohne aktive Rechnung
    // (Task 24); bei wiederholtem Lauf auf derselben Bestellung fehlt der Knopf,
    // die Rechnung steht dann schon in der Liste.
    const rechnungKnopf = belege.getByRole('button', { name: /Rechnung aus Bestellung/ });
    await expect(rechnungKnopf.or(belege.locator('text=RE-')).first()).toBeVisible({ timeout: 5000 });
    if (await rechnungKnopf.isVisible()) {
      await rechnungKnopf.click();
      await expect(rechnungKnopf).toBeHidden({ timeout: 5000 });
    }
    await belege.getByRole('button', { name: /Neue AB/ }).click();
    // Hat die Bestellung schon einen Lieferschein, fragt der Dialog per
    // window.confirm nach (Task 23). Playwright lehnt Dialoge ohne Handler ab:
    // Es entsteht kein zweiter Lieferschein, der vorhandene genügt.
    await belege.getByRole('button', { name: /Neuer LS/ }).click();
    // Erwarte mindestens je einen Beleg in der Liste (.first(): bei
    // wiederholtem Lauf gibt es mehrere ABs)
    await expect(belege.locator('text=AB-').first()).toBeVisible({ timeout: 5000 });
    await expect(belege.locator('text=LS-').first()).toBeVisible();
    await expect(belege.locator('text=RE-').first()).toBeVisible();
```

Warum die Rechnung zuerst: Jede Mutation im Dialog ruft `invalidate()` und lädt `order-invoices` neu; währenddessen ist der Knopf ausgeblendet (`!invoicesQuery.isFetching`). Direkt nach dem Öffnen gibt es nur die erste Abfrage, `isVisible()` ist dann verlässlich. Rechnung vor Lieferung ist erlaubt (Entscheidung f).

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_sammelrechnung.py tests/test_storno.py -v`
Erwartet: alle passed (davon 22 `TestS6`).
Run: `cd frontend && npm run build` — ohne TypeScript-Fehler (`tsconfig.json` schließt nur `src` ein, die E2E-Datei prüft der nächste Befehl).
Run: `cd frontend && npx playwright test --list --reporter=list tests/e2e/full-suite.spec.ts`
Erwartet: letzte Zeile `Total: 14 tests in 1 file`, kein Syntaxfehler. `--list` startet keinen Browser und braucht weder Server noch Netzwerk; `--reporter=list` verhindert, dass der HTML-Reporter `playwright-report/` schreibt.

- [ ] **Step 7: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/invoices.py frontend/src/services/api.ts \
        frontend/src/components/domain/OrderDocumentsModal.tsx \
        frontend/tests/e2e/full-suite.spec.ts backend/tests/test_gernot_261008.py
git commit -m "fix(belege): Rechnungen je Bestellung per Filter statt der 20 neuesten; Knopf nur ohne aktive Rechnung"
```

**Manager-Abnahme nach Task 24 (lokal, Oberfläche; = M4 in der Abnahme, kein Worker-Schritt):**

1. Belege-Dialog einer Bestellung mit Rechnung → kein Knopf „Rechnung aus Bestellung"; nach Storno erscheint er wieder. „Neuer LS" bei vorhandenem Lieferschein → Rückfrage mit der Lieferscheinnummer; „Abbrechen" legt nichts an.
2. Als `production_planner` bzw. `production_staff`: Abschnitt „Rechnungen" zeigt grau „Rechnungen sehen nur Vertrieb und Buchhaltung.", keinen Knopf, keinen roten Fehler; „Neuer LS" funktioniert.
3. E2E zweimal hintereinander: Backend auf `localhost:8000` mit `AUTH_DISABLED=true` (bei leerem `TENANTS_DIR` zusätzlich `DEFAULT_TENANTS=dev`, sonst fehlen die Tabellen), Frontend `VITE_AUTH_DISABLED=true npm run dev` (Port 3000, `vite.config.ts`), mindestens eine Bestellung mit Lieferdatum **heute** (die Seite öffnet auf dem Reiter „Heute"). Dann `cd frontend && BASE_URL=http://localhost:3000 npx playwright test tests/e2e/full-suite.spec.ts -g "belege-modal" --retries=0 --reporter=list`. Erwartet: beide Läufe `1 passed`; danach hat die Bestellung genau eine Rechnung und einen Lieferschein (im zweiten Lauf antwortet der LS-POST mit 409, die Rückfrage wird abgelehnt).

Am 08.10.2026 in einer Sandbox vorab geprüft (S6-Backend aus der Plan-Umsetzung, Frontend mit Step 4 und 5, Vite-Proxy auf das Sandbox-Backend, `VITE_API_URL=` leer): Punkt 3 zweimal grün, Ergebnis 1 Rechnung, 1 Lieferschein, 2 ABs; Punkt 2 per Playwright mit abgefangener Antwort (`page.route`, 403 → grauer Hinweis ohne Knopf; 500 → roter Ladefehler ohne Knopf); `tsc`, `vite build` und `playwright test --list` fehlerfrei.

---

## Abschnitt S5: Rechnungsentwurf prüfen (B4-Kern), Pfandabrechnung je Kunde, Rechnungsliste vollständig — Tasks 25–29

**Einordnung:** S5 läuft zuletzt und setzt voraus:
- **S1:** `app.services.steuersatz.produkt_der_position(db, product_id, product_variant_id) -> Optional[Product]` (Task 1). Damit zählen auch Positionen, die nur über die Verpackungsvariante am Pfandartikel hängen. S5 setzt außerdem auf `_aggregiere(db, notes)` aus Task 3 und darauf, dass die Sammelrechnung `product_id` an `add_line` übergibt; ohne das bekäme die Pfandzeile eines Kunden mit `JE_LIEFERUNG` in der Sammelrechnung kein `is_deposit`.
- **Task 9:** `InvoiceService.recalculate_totals(invoice: Invoice) -> Invoice` — flusht, lädt `invoice.lines` neu und ruft `calculate_totals()`. Ohne sie sähe `calculate_totals()` nach `db.delete(line)` die gelöschte Zeile noch (`autoflush=False`). Task 25 ruft sie in `update_invoice_line` und `delete_invoice_line` auf.
- **Task 16:** `app.services.datev_service.erloeskonto_fuer(tax_rate) -> str` und `ist_standard_erloeskonto(konto) -> bool`. Task 25 importiert sie, statt eine eigene Kontentabelle anzulegen.
- **S6 vollständig (Tasks 20–24):**
  - `GET /api/v1/invoices?order_id=` (Task 24, beide Wege: `Invoice.order_id` und zugeordnete Lieferscheine). Ohne den Filter ignoriert FastAPI den Parameter, und der Dialog zeigte Rechnungen fremder Bestellungen; Task 28 sichert das mit einem Test ab.
  - `BereitsAbgerechnet` und `waehle_vertreter` im Import von `invoices.py` (Tasks 20 und 22); „Rechnung aus Bestellung" hängt genau einen Lieferschein an (Task 21).
  - In `pdf_service.py` die Bedingung `if db is not None and invoice.order_id is None:` am Block „Enthaltene Lieferscheine" (Task 21) und `from decimal import Decimal` (Task 10).
  - Belege-Dialog in der Fassung aus Task 24: `invoicesApi.list({ order_id: orderId! })`, `aktiveRechnung`, `rechnungMoeglich`.
- **Pfandabrechnung laut Spec-Nachtrag 08.10. (Variante C):** Kundenfeld `pfand_abrechnung` mit `JE_LIEFERUNG` (Standard, Pfand auf jeder Rechnung, z. B. Knuspr) und `KEINE` (IFCO-Clearing: Pfand auf Bestellung und Lieferschein, nicht auf der Rechnung, z. B. Ökoring). Das ersetzt das in der Einzelfassung geplante Ja/Nein-Feld `pfand_via_clearing`; `MONATLICH` (Leergutkonto) ergänzt Paket 3. Task 26 ist dafür neu geschrieben und in einer Kopie von `efcea00` geprüft.
- **Runbook:** Ist Ökoring Clearing-Kunde (Offener Punkt G3), muss S5 deployt und `pfand_abrechnung = KEINE` bei Ökoring gesetzt sein, **bevor** RE-00002 neu ausgestellt wird. Sonst trägt die Neuausstellung das Pfand erneut.

Zeilenangaben beziehen sich auf `c4a1832`. Nach S1, S3 und S6 sind sie verschoben; maßgeblich sind die zitierten Ankerzeilen.

### Verifizierter Ausgangsbefund (S5)

Gemessen am 08.10.2026 gegen die App (In-Memory-Testdatenbank, `main` @ `c4a1832`), nicht geschätzt:

| Vorgang | Ergebnis heute |
|---|---|
| Entwurf 10 × 2,50 € (7 %) + 2 × 3,00 € (19 %), zweite Zeile `DELETE` | 204; Summen bleiben 31,00 / 2,89 / 33,89 statt 25,00 / 1,75 / 26,75 (`invoices.py:377-378`) |
| `PATCH` Zeile `{"quantity": 4}` | korrekt neu gerechnet (10,00 / 10,70); der Änderungspfad ist nicht betroffen |
| `PATCH` `{"tax_rate": "STANDARD"}` | 200, Steuer korrekt, `buchungskonto` bleibt **8300** |
| `PATCH` `{"quantity": 0}` / `{"quantity": -1}` / `{"unit": ""}` | **200, gespeichert** |
| `PATCH` `{"unit_price": -5}` / `{"discount_percent": 150}` / `{"description": ""}` | **erst committed, dann 500** (Antwortschema lehnt ab). Der Wert steht danach in der Datenbank |
| `PATCH` `{"quantity": null}` / `{"tax_rate": null}` / `{"description": null}` | 500 (`TypeError` / `AttributeError` / `NOT NULL`) |
| Antwort einer Rechnungszeile | kein Feld `is_deposit`, obwohl die Spalte gesetzt ist (Pfandzeile aus Bestellung: `total_deposit` 6,42, Zeile ohne Kennzeichen) |
| 25 Rechnungen am selben Tag, `GET /invoices` | 20 Einträge, **älteste zuerst** (`RE-2026-00001` vorn): `order_by(invoice_date.desc())` ohne Nebenkriterium |
| `OrderDocumentsModal` | `invoicesApi.list({})` + Filter im Browser: sucht nur unter den 20 neuesten Rechnungen aller Kunden |
| Lieferschein-PDF einer Bestellung mit Pfandartikel | Pfandzeile steht drauf (SKU und Name), der Lieferschein rendert `order.lines` (`pdf_service.py:759`). S5 fasst Bestellpositionen nicht an |
| Entwurf in der Rechnungsliste über „Details" öffnen | **„Keine Positionen", kein Löschknopf.** `InvoiceDetail` (`Invoices.tsx:963-967`) setzt `initialData` auf den Listeneintrag. `GET /invoices` liefert aber `InvoiceResponse` ohne `lines` (`schemas/invoice.py:161-212`, `lines` nur in `InvoiceDetailResponse`). Wegen `staleTime` 60 s (`main.tsx:23-31`) gilt der Eintrag als frisch: React Query 5.90.20 setzt für `initialData` `dataUpdatedAt = Date.now()` (`query-core/build/modern/query.js:418`) und lädt beim Mount nicht nach. Nachgestellt mit `@tanstack/query-core` und den App-Defaults: 0 Abrufe, `lines` undefined. Mit `refetchOnMount: 'always'`: 1 Abruf, die Positionen sind da. Das ist der eigentliche Grund für B4 „Knopf schwer erreichbar". Im Belege-Dialog (Task 29) gälte dasselbe |
| Sammelrechnung eines Clearing-Kunden, nur mit Task 27 Step 3–5 | Rechnung 25,00 € netto, aber Anlage „Enthaltene Lieferscheine" im PDF **31,00 EUR** und `GET /invoices/{id}/delivery-notes` `betrag_netto` 31.0. Beide summieren alle `order.lines` je Lieferschein (`pdf_service.py:386-389`, `invoices.py:668`). Nachgestellt in einer Kopie mit Task 21 |

**Testlaufzeit:** Jede neue Bestellung ruft `_trigger_forecast_update` (`backend/app/api/v1/sales.py:40`) und hängt ohne Redis rund 15 s im Celery-Reconnect. Die S5-Tests mit Bestellungen schalten das per Fixture `_s5_ohne_forecast` ab. Mit Fixture laufen die S5-Tests (36 nach der Zusammenführung) in wenigen Sekunden. Für die Bestands- und Vollläufe ist `REDIS_URL=memory://` vor dem pytest-Aufruf zulässig (in S6 verifiziert, gleiche Fehlerliste); im Zweifel zählt der Lauf ohne Variable.

**Prototyp und Prüfung:**
- **Erstfassung:** in einer Kopie umgesetzt (`main` + S1-Stand + `recalculate_totals` aus S3 + `order_id`-Filter aus S6). Ergebnis 30/30 grün. Dazu liefen `test_pfand_rabatt.py`, `test_gernot_260821.py`, `test_sammelrechnung.py`, `test_storno.py`, `test_datev_export.py`, `test_services.py`, `test_gernot_bugfixes.py`, `test_gernot_260817.py`, `test_lexoffice.py`, `test_documents_preise.py`, `test_rollen.py`, `test_erp.py` und `test_features.py` vorher und nachher mit identischen Fehlernamen (nur Altlasten).
- **Fassung nach dem Review:** wörtlich in einer Kopie durchgespielt. Stand: `main` + S1-Teile + S3 `recalculate_totals` + Tasks 20–22 (`BereitsAbgerechnet`, `waehle_vertreter`, `abgerechnete_bestellungen`, neues `_abrechenbare_lieferscheine`) + Task 21-PDF-Teil + Task 24-Filter.
  - Task 25 rot: 15 failed / 3 passed.
  - Task 27 rot, Stand vor Task 27 nachgestellt: 6 failed / 3 passed.
  - Danach **33/33 grün**.
  - Bestandstests `test_pfand_rabatt.py`, `test_sammelrechnung.py`, `test_storno.py`, `test_gernot_260821.py`, `test_datev_export.py`, `test_documents_preise.py` und `test_gernot_260817.py`: 115 passed.
  - Vollauf mit `REDIS_URL=memory://`: 14 failed / 535 passed / 2 skipped / 1 error. Das sind nur Altlasten der Baseline; `test_services.py::TestInvoiceService::test_invoice_totals_update` behebt S3.
- **Frontend:** in einer Kopie `main` + Task 24 + Task 28 + Task 29 laufen `tsc --noEmit` und `vite build` ohne Fehler.
- **Zusammenführung (dieser Plan):** Task 26 neu (`pfand_abrechnung` statt `pfand_via_clearing`) und in einer Kopie von `efcea00` geprüft (Rot 6, Grün 6); Tasks 25, 27 und 29 mechanisch umgestellt (gemeinsame Erlöskonto-Regel aus Task 16, Kennzeichen `pfand_abrechnung == KEINE`). Die Kundenformular-Änderung aus Task 29 Step 1/4 lief in einer Kopie durch `tsc --noEmit`. Die Zahl der S5-Tests steigt von 33 auf 36.

### Review-Fokus S5

1. **Eine abgelehnte Änderung schreibt nichts.** 422 entsteht im Schema, vor jedem `setattr`. Der Test prüft danach Menge, Preis und Summe in der Datenbank.
2. **Löschen rechnet alles neu**, auch `total_deposit`. Getestet mit einer Pfandzeile.
3. **GoBD:** Alle Änderungen greifen nur bei `ENTWURF` (bestehende Prüfung bleibt). `pfand_abrechnung` wirkt nur auf **neu erzeugte** Rechnungen. Bestehende Rechnungszeilen werden nie angefasst; das PDF wird aus der Datenbank neu erzeugt und bleibt damit unverändert.
4. **Clearing filtert nur Pfandartikel (`is_deposit` am Produkt) und nur bei Kunden mit `pfand_abrechnung = KEINE`.** Bestellung und Lieferschein behalten die Pfandzeile.
5. **Keine leere Rechnung:** Reine Clearing-Pfand-Bestellung → 400. Im Sammellauf fällt ein solcher Kunde heraus (Vorschau und Festschreiben).
6. **Die Anlage passt zur Rechnung, und sie bleibt stabil.** Die Anlage „Enthaltene Lieferscheine" und `GET /invoices/{id}/delivery-notes` rechnen aus den Positionen der Rechnung: bei Sammelrechnungen über `invoice_line_sources`, bei Rechnungen aus Bestellung über `order_item_id`. Sie rechnen weder aus der Bestellung noch aus dem heutigen Kundenfeld. Ein später auf `KEINE` gestelltes Kundenfeld ändert kein bestehendes PDF (eigener Test). Für bestehende Sammelrechnungen ergibt die neue Formel denselben Betrag wie die alte, denn sie hatten weder Clearing noch Positionsrabatt. Sie weicht nur ab, wenn Bestellpositionen nach der Abrechnung geändert wurden. Dann zeigt sie den abgerechneten Betrag, und genau das soll die Anlage zeigen.
7. **Positionen beim ersten Öffnen:** `InvoiceDetail` lädt beim Öffnen immer nach (`refetchOnMount: 'always'`). Ohne das zeigt es „Keine Positionen" und keinen Löschknopf.
8. **Ein Sonderkonto bleibt:** Ein Satzwechsel setzt nur leere Konten und Standardkonten neu. Das ist dieselbe Regel wie im DATEV-Export (S4).

---

### Task 25: Entwurfspositionen — Summen nach Löschen, Prüfung beim Ändern, Standard-Erlöskonto folgt dem Satz, Pfandkennzeichen in der Antwort

**Files:**
- Modify: `backend/app/schemas/invoice.py:9` (Import), `:44-51` (`InvoiceLineUpdate`), `:54-72` (`InvoiceLineResponse`)
- Modify: `backend/app/services/invoice_service.py` (Import der Erlöskonto-Regel aus `datev_service`; `add_line` `:141-147`)
- Modify: `backend/app/api/v1/invoices.py` (Import aus `datev_service`), `:327-356` (`update_invoice_line`), `:359-379` (`delete_invoice_line`)
- Modify: `backend/tests/test_gernot_261008.py` (S5-Block anhängen)

**Interfaces:**
- Consumes:
  - `InvoiceService.recalculate_totals(invoice: Invoice) -> Invoice` (S3).
  - `app.services.datev_service.erloeskonto_fuer(tax_rate: TaxRate) -> str` und `ist_standard_erloeskonto(konto: Optional[str]) -> bool` (Task 16).
- Produces:
  - `InvoiceLineResponse.is_deposit: bool` (Default `False`) in jeder Zeilenantwort, auch in `InvoiceDetailResponse.lines`.
  - `InvoiceLineUpdate`: Grenzen wie `InvoiceLineCreate` (Menge > 0, Preis ≥ 0, Rabatt 0–100, Beschreibung nicht leer). Zusätzlich darf die Einheit nicht leer sein; beim Anlegen prüft `InvoiceLineBase.unit` das nicht (`schemas/invoice.py:27`). Ein ausdrückliches `null` ergibt 422.
  - Test-Helfer `_d`, `_s5_kunde`, `_s5_produkt`, `_s5_ifco_kiste`, `_s5_entwurf`, `_s5_zeile`, `_s5_detail`. Tasks 26–28 nutzen sie weiter.

- [ ] **Step 1: S5-Block mit Helfern und Tests anhängen**

Ans Ende von `backend/tests/test_gernot_261008.py` anhängen (Kopf aus Task 1):

```python
# ---------------------------------------------------------------------------
# S5 — Rechnungsentwurf prüfen, Pfand über IFCO-Clearing, Rechnungsliste
# ---------------------------------------------------------------------------


def _d(wert) -> Decimal:
    return Decimal(str(wert))


def _s5_kunde(client, name="Ökoring Handels GmbH", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s5_produkt(client, name, sku, preis, **extra):
    """Wie _produkt in test_gernot_260917.py: die Produktanlage braucht base_unit_id."""
    from app.models.unit import UnitOfMeasure, UnitCategory

    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)

    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": unit_id, **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _s5_ifco_kiste(client):
    """Pfandartikel wie in Produktion: Kategorie PFAND setzt is_deposit."""
    kiste = _s5_produkt(client, "IFCO-Kiste", "PFAND-IFCO", "3.00", category="PFAND")
    assert kiste["is_deposit"] is True
    return kiste


def _s5_entwurf(client, kunde):
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": date.today().isoformat(),
    })
    assert r.status_code == 201, r.text
    return r.json()


def _s5_zeile(client, rechnung, **daten):
    """Freitextzeile 10 × 2,50 € zu 7 % — mit **daten überschreibbar."""
    body = {"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
            "unit_price": "2.50", "tax_rate": "REDUZIERT"}
    body.update(daten)
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _s5_detail(client, rechnung):
    r = client.get(f"/api/v1/invoices/{rechnung['id']}")
    assert r.status_code == 200, r.text
    return r.json()


class TestS5EntwurfLoeschen:
    """B4: eine Position im Entwurf löschen — die Summen müssen folgen."""

    def test_summen_nach_loeschen(self, client):
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        _s5_zeile(client, rechnung)
        weg = _s5_zeile(client, rechnung, description="Kiste", quantity=2,
                        unit_price="3.00", tax_rate="STANDARD")

        r = client.delete(f"/api/v1/invoices/{rechnung['id']}/lines/{weg['id']}")

        assert r.status_code == 204, r.text
        d = _s5_detail(client, rechnung)
        assert len(d["lines"]) == 1
        # 25,00 netto + 1,75 USt — vorher blieben 31,00 / 2,89 / 33,89 stehen
        assert _d(d["subtotal"]) == Decimal("25.00")
        assert _d(d["tax_amount"]) == Decimal("1.75")
        assert _d(d["total"]) == Decimal("26.75")

    def test_pfandsumme_nach_loeschen_der_pfandzeile(self, client):
        kiste = _s5_ifco_kiste(client)
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        _s5_zeile(client, rechnung)
        pfand = _s5_zeile(client, rechnung, description="IFCO-Kiste", quantity=2,
                          unit_price="3.00", tax_rate="STANDARD", product_id=kiste["id"])
        # 2 × 3,00 € netto + 19 % = 7,14 € brutto (Bestandsverhalten, test_pfand_rabatt)
        assert _d(_s5_detail(client, rechnung)["total_deposit"]) == Decimal("7.14")

        client.delete(f"/api/v1/invoices/{rechnung['id']}/lines/{pfand['id']}")

        assert _d(_s5_detail(client, rechnung)["total_deposit"]) == Decimal("0.00")

    def test_finalisierte_rechnung_bleibt_unveraenderlich(self, client):
        """GoBD: nach dem Finalisieren nur noch Storno und Neuausstellung."""
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        zeile = _s5_zeile(client, rechnung)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        url = f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}"

        assert client.delete(url).status_code == 400
        assert client.patch(url, json={"quantity": 1}).status_code == 400
        assert _d(_s5_detail(client, rechnung)["subtotal"]) == Decimal("25.00")


class TestS5EntwurfAendern:
    """B4: PATCH einer Entwurfsposition prüft die Eingabe und zieht das Konto nach."""

    @pytest.mark.parametrize("aenderung", [
        {"quantity": 0}, {"quantity": -1}, {"quantity": None},
        {"unit_price": -5}, {"unit_price": None},
        {"discount_percent": 150}, {"discount_percent": -1},
        {"description": ""}, {"description": None},
        {"unit": ""}, {"tax_rate": None},
    ])
    def test_ungueltige_aenderung_wird_abgelehnt(self, client, aenderung):
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        zeile = _s5_zeile(client, rechnung)

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}", json=aenderung)

        assert r.status_code == 422, r.text
        d = _s5_detail(client, rechnung)
        assert _d(d["lines"][0]["quantity"]) == Decimal("10")
        assert _d(d["lines"][0]["unit_price"]) == Decimal("2.50")
        assert _d(d["subtotal"]) == Decimal("25.00")

    def test_gueltige_aenderung_rechnet_neu(self, client):
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        zeile = _s5_zeile(client, rechnung)

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"quantity": 4})

        assert r.status_code == 200, r.text
        assert _d(r.json()["line_total"]) == Decimal("10.00")
        d = _s5_detail(client, rechnung)
        assert _d(d["subtotal"]) == Decimal("10.00")
        assert _d(d["total"]) == Decimal("10.70")

    def test_satzwechsel_zieht_erloeskonto_und_steuer_nach(self, client):
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        zeile = _s5_zeile(client, rechnung)
        assert zeile["buchungskonto"] == "8300"
        url = f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}"

        r = client.patch(url, json={"tax_rate": "STANDARD"})

        assert r.status_code == 200, r.text
        assert r.json()["buchungskonto"] == "8400"
        d = _s5_detail(client, rechnung)
        assert _d(d["tax_amount"]) == Decimal("4.75")
        assert _d(d["total"]) == Decimal("29.75")
        assert client.patch(url, json={"tax_rate": "STEUERFREI"}).json()["buchungskonto"] == "8100"
        assert client.patch(url, json={"tax_rate": "REDUZIERT"}).json()["buchungskonto"] == "8300"

    def test_sonderkonto_bleibt(self, client):
        """Nur die Standardkonten folgen dem Satz. Ein Sonderkonto bleibt bei
        Mengen- und bei Satzwechsel — dieselbe Regel wie der DATEV-Export (S4)."""
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        zeile = _s5_zeile(client, rechnung, buchungskonto="8338")
        url = f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}"
        assert client.patch(url, json={"quantity": 3}).json()["buchungskonto"] == "8338"

        r = client.patch(url, json={"tax_rate": "STANDARD"})

        assert r.status_code == 200, r.text
        assert r.json()["buchungskonto"] == "8338"
        assert _d(r.json()["tax_amount"]) == Decimal("1.43")


class TestS5Pfandkennzeichen:
    """Die Oberfläche muss Pfandzeilen erkennen können."""

    def test_zeilen_tragen_is_deposit(self, client):
        kiste = _s5_ifco_kiste(client)
        rechnung = _s5_entwurf(client, _s5_kunde(client))
        ware = _s5_zeile(client, rechnung)
        pfand = _s5_zeile(client, rechnung, description="IFCO-Kiste", quantity=2,
                          unit_price="3.00", tax_rate="STANDARD", product_id=kiste["id"])

        assert ware["is_deposit"] is False
        assert pfand["is_deposit"] is True
        zeilen = {l["id"]: l["is_deposit"] for l in _s5_detail(client, rechnung)["lines"]}
        assert zeilen == {ware["id"]: False, pfand["id"]: True}
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS5 -v`

Erwartet: 18 Tests, 15 FAIL und 3 grün.

- `test_summen_nach_loeschen` FAIL `Decimal('31.00') == Decimal('25.00')`
- `test_pfandsumme_nach_loeschen_der_pfandzeile` FAIL `Decimal('7.14') == Decimal('0.00')`
- `test_ungueltige_aenderung_wird_abgelehnt`, alle 11 Fälle FAIL:
  - Menge 0, Menge −1 und Einheit `""` mit `assert 200 == 422`
  - die übrigen als 500 im TestClient: `TypeError` (Menge/Preis `null`), `ResponseValidationError` (Preis −5, Rabatt 150/−1, Beschreibung `""`), `IntegrityError` (Beschreibung `null`), `AttributeError` (Satz `null`)
- `test_satzwechsel_zieht_erloeskonto_und_steuer_nach` FAIL `'8300' == '8400'`
- `test_zeilen_tragen_is_deposit` FAIL `KeyError: 'is_deposit'`

Grün sind bereits `test_finalisierte_rechnung_bleibt_unveraenderlich`, `test_gueltige_aenderung_rechnet_neu` und `test_sonderkonto_bleibt`. Sie sichern Bestandsverhalten: Heute ändert ein `PATCH` das Konto nie, also bleibt auch das Sonderkonto.

- [ ] **Step 3: Schema**

In `backend/app/schemas/invoice.py` Zeile 9:

```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
```

`InvoiceLineUpdate` (`:44-51`) vollständig ersetzen:

```python
class InvoiceLineUpdate(BaseModel):
    """Schema zum Aktualisieren einer Rechnungsposition (nur Entwürfe).

    Grenzen wie beim Anlegen (InvoiceLineCreate): Menge > 0, Preis >= 0,
    Rabatt 0-100, Beschreibung nicht leer. Zusätzlich darf die Einheit nicht
    leer sein (InvoiceLineBase prüft das beim Anlegen nicht). Ein
    ausdrückliches null heißt nicht "unverändert" — es schrieb die Zeile
    kaputt (Menge None -> 500, Beschreibung None -> NOT NULL). Wer ein Feld
    nicht ändern will, lässt es weg.
    """
    description: Optional[str] = Field(None, min_length=1)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, min_length=1)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    discount_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    tax_rate: Optional[TaxRate] = None

    @field_validator("description", "quantity", "unit", "unit_price", "discount_percent", "tax_rate")
    @classmethod
    def _kein_null(cls, wert):
        if wert is None:
            raise ValueError("darf nicht leer sein — Feld weglassen, um es nicht zu ändern")
        return wert
```

Pydantic v2 ruft den Validator nur für mitgeschickte Felder auf. Weggelassene Felder bleiben `None` und fallen über `exclude_unset=True` heraus; das ist im Prototyp geprüft.

In `InvoiceLineResponse` direkt unter `buchungskonto: Optional[str]`:

```python
    #: Pfandposition (aus dem Produktstamm beim Anlegen) — die Oberfläche
    #: kennzeichnet sie, der Rechnungskopf summiert sie in total_deposit.
    is_deposit: bool = False
```

- [ ] **Step 4: `add_line` nutzt die gemeinsame Erlöskonto-Regel**

In `backend/app/services/invoice_service.py` direkt nach der Zeile `from app.services.steuersatz import produkt_der_position, steuersatz_der_position` (Task 2) einfügen:

```python
from app.services.datev_service import erloeskonto_fuer
```

Ein Importzyklus entsteht nicht: `datev_service.py` importiert nur aus `app.models` (in der Prüfkopie lädt `import app.main` fehlerfrei).

In `add_line` den Block `# Buchungskonto basierend auf Steuersatz` (`:141-147`) ersetzen durch:

```python
        # Buchungskonto basierend auf Steuersatz — dieselbe Regel wie der
        # DATEV-Export (datev_service.erloeskonto_fuer)
        if not buchungskonto:
            buchungskonto = erloeskonto_fuer(tax_rate)
```

- [ ] **Step 5: Endpunkte**

Vorbedingung: In `backend/app/api/v1/invoices.py` lautet die Importzeile aus `app.services.invoice_service` nach S6 `from app.services.invoice_service import InvoiceService, BereitsAbgerechnet, waehle_vertreter`. Lautet sie anders (z. B. ohne `BereitsAbgerechnet` oder `waehle_vertreter`), fehlt S6: stoppen und melden. Diese Zeile bleibt in diesem Task unverändert.

Die Zeile `from app.services.datev_service import DatevService` (direkt darunter) ersetzen durch:

```python
from app.services.datev_service import DatevService, erloeskonto_fuer, ist_standard_erloeskonto
```

**5a: `update_invoice_line`.** Den Teil ab `update_data = data.model_dump(exclude_unset=True)` bis `return line` ersetzen durch:

```python
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
```

**5b: `delete_invoice_line`.** Die beiden Zeilen `db.delete(line)` / `invoice.calculate_totals()` ersetzen durch:

```python
    db.delete(line)
    # Erst löschen, dann die Positionen neu laden, dann rechnen — sonst zählt
    # die gelöschte Zeile in Summe, USt und Pfand weiter mit (B4).
    InvoiceService(db).recalculate_totals(invoice)
```

Das abschließende `db.commit()` bleibt. Die Prüfungen auf `ENTWURF` in beiden Endpunkten bleiben unverändert (GoBD).

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS5 -v`
Erwartet: 18 passed.

- [ ] **Step 7: Bestandstests, die dieses Verhalten festschreiben**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_pfand_rabatt.py tests/test_gernot_260821.py tests/test_storno.py tests/test_sammelrechnung.py tests/test_datev_export.py -q`

Erwartet: dieselben Fehlernamen wie vor Task 25. Im Prototyp waren es keine. `test_pfand_rabatt.py:49-75` muss grün bleiben: Manuelle Zeilen behalten den Satz vom Client, S5 ändert an `add_line` nur die Kontozuordnung. Diese Dateien legen Bestellungen an und brauchen einige Minuten.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/invoice.py backend/app/services/invoice_service.py \
        backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py
git commit -m "fix(rechnung): Entwurf — Summen nach Löschen, Prüfung beim Ändern, Standard-Erlöskonto folgt dem Steuersatz"
```

---

### Task 26: Kundenfeld `pfand_abrechnung` (`JE_LIEFERUNG` / `KEINE`)

Spec, Nachtrag 08.10. nachmittags (Variante C): Paket 1 baut das Kundenfeld `pfand_abrechnung` mit `JE_LIEFERUNG` und `KEINE` statt eines Ja/Nein-Feldes `pfand_via_clearing`; Paket 3 ergänzt `MONATLICH` (Leergutkonto). Bis dahin weist die API `MONATLICH` ab, damit kein Kunde auf einem Wert steht, zu dem es keine Logik gibt.

**Files:**
- Modify: `backend/app/models/customer.py` — neues Enum `PfandAbrechnung` direkt nach `class SubscriptionInterval` (`:55-60`), neue Spalte direkt nach `show_prices_on_delivery_note` (`:182`)
- Modify: `backend/app/schemas/customer.py` — Imports `:9` und `:11`, `CustomerCreate` (`:115`), `CustomerUpdate` (`:163`), `CustomerResponse` (`:194`)
- Modify: `backend/app/tenancy.py` — `_auto_migrate`, erster `try`, direkt unter `_add_col_if_missing("customers", "show_prices_on_delivery_note", "BOOLEAN", "0")` (`:304`)
- Test: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: Helfer `_s5_kunde` (Task 25).
- Produces:
  - `app.models.customer.PfandAbrechnung(str, Enum)` mit `JE_LIEFERUNG = "JE_LIEFERUNG"` und `KEINE = "KEINE"`.
  - `Customer.pfand_abrechnung: Mapped[PfandAbrechnung]` (`SQLEnum(PfandAbrechnung, length=20)`, NOT NULL, Default `JE_LIEFERUNG`).
  - `CustomerCreate.pfand_abrechnung: PfandAbrechnung = JE_LIEFERUNG`, `CustomerUpdate.pfand_abrechnung: Optional[PfandAbrechnung] = None` (ein ausdrückliches `null` ergibt 422), `CustomerResponse.pfand_abrechnung: PfandAbrechnung`. JSON-Wert ist der Enum-Name, z. B. `"KEINE"`.
  - Spalte `customers.pfand_abrechnung VARCHAR(20) DEFAULT 'JE_LIEFERUNG'` auf bestehenden Mandanten-DBs; Bestandskunden stehen danach auf `JE_LIEFERUNG` (Pfand wie heute auf der Rechnung).

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS5KundenfeldPfandAbrechnung:
    """Spec 08.10.2026, Variante C: pfand_abrechnung JE_LIEFERUNG oder KEINE."""

    def test_standard_je_lieferung_und_pflegbar(self, client):
        kunde = _s5_kunde(client)
        assert kunde["pfand_abrechnung"] == "JE_LIEFERUNG"

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"pfand_abrechnung": "KEINE"})

        assert r.status_code == 200, r.text
        assert r.json()["pfand_abrechnung"] == "KEINE"
        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["pfand_abrechnung"] == "KEINE"

    def test_anlage_mit_keine(self, client):
        assert _s5_kunde(client, pfand_abrechnung="KEINE")["pfand_abrechnung"] == "KEINE"

    @pytest.mark.parametrize("wert", ["MONATLICH", "JA", None])
    def test_unbekannter_wert_und_null_werden_abgewiesen(self, client, wert):
        """MONATLICH kommt erst mit Paket 3 — bis dahin gäbe es keine Logik dazu.
        null hieße nicht 'unverändert', sondern schriebe NULL in eine NOT-NULL-Spalte."""
        kunde = _s5_kunde(client)

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"pfand_abrechnung": wert})

        assert r.status_code == 422, r.text
        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["pfand_abrechnung"] == "JE_LIEFERUNG"

    def test_auto_migrate_ergaenzt_spalte(self, tmp_path):
        """Bestehende Mandanten-DBs bekommen die Spalte beim Start; Altkunden stehen auf JE_LIEFERUNG."""
        from sqlalchemy import create_engine, inspect, text
        from app.tenancy import _auto_migrate

        engine = create_engine(f"sqlite:///{tmp_path / 'alt.db'}")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE customers (id CHAR(32) PRIMARY KEY, name VARCHAR(200))"))
            conn.execute(text("INSERT INTO customers (id, name) VALUES ('a', 'Ökoring')"))

        _auto_migrate(engine)

        spalten = {c["name"] for c in inspect(engine).get_columns("customers")}
        assert "pfand_abrechnung" in spalten
        with engine.connect() as conn:
            assert conn.execute(text("SELECT pfand_abrechnung FROM customers")).scalar() == "JE_LIEFERUNG"
        engine.dispose()
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS5KundenfeldPfandAbrechnung -v`

Erwartet: 6 FAILED (auf `efcea00` geprüft):
- `test_standard_je_lieferung_und_pflegbar` und `test_anlage_mit_keine`: `KeyError: 'pfand_abrechnung'` — das unbekannte Feld wird heute still ignoriert.
- `test_unbekannter_wert_und_null_werden_abgewiesen[MONATLICH]`, `[JA]`, `[None]`: `assert 200 == 422`.
- `test_auto_migrate_ergaenzt_spalte`: `assert 'pfand_abrechnung' in {...}`.

- [ ] **Step 3: Modell**

In `backend/app/models/customer.py` direkt nach der Klasse `SubscriptionInterval` (nach der Zeile `    MONATLICH = "MONATLICH"`) einfügen:

```python


class PfandAbrechnung(str, Enum):
    """Wie das Pfand (Produkt mit is_deposit) eines Kunden abgerechnet wird.

    JE_LIEFERUNG: Pfandpositionen stehen auf jeder Rechnung (z. B. Knuspr).
    KEINE: Pfand läuft über das IFCO-Clearing — Pfandpositionen stehen auf
        Bestellung und Lieferschein, aber nicht auf der Rechnung (z. B. Ökoring).
    MONATLICH (Leergutkonto: ausgegeben minus Retouren, einmal im Monat)
    folgt mit Paket 3 (Spec, Nachtrag 08.10.2026).
    """
    JE_LIEFERUNG = "JE_LIEFERUNG"
    KEINE = "KEINE"
```

Direkt unter `show_prices_on_delivery_note: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")`:

```python

    # Pfandabrechnung (Spec 08.10.2026, Variante C): JE_LIEFERUNG oder KEINE
    # (IFCO-Clearing). Wirkt nur auf neu erzeugte Rechnungen.
    pfand_abrechnung: Mapped[PfandAbrechnung] = mapped_column(
        SQLEnum(PfandAbrechnung, length=20), nullable=False,
        default=PfandAbrechnung.JE_LIEFERUNG, server_default=PfandAbrechnung.JE_LIEFERUNG.value,
    )
```

`Enum` und `SQLEnum` importiert die Datei bereits (`:8`, `:10`). `length=20` lässt Platz für `MONATLICH` (Paket 3); SQLite prüft die Länge nicht.

- [ ] **Step 4: Schemas**

In `backend/app/schemas/customer.py`:
- Zeile 9 `from pydantic import BaseModel, Field, ConfigDict, EmailStr` wird zu `from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator`.
- Zeile 11 `from app.models.customer import CustomerType, SubscriptionInterval, PaymentTerms, AddressType` wird zu `from app.models.customer import CustomerType, SubscriptionInterval, PaymentTerms, AddressType, PfandAbrechnung`.

`CustomerCreate` (das Feld `show_prices_on_delivery_note` steht dort, nicht in `CustomerBase`), direkt unter `show_prices_on_delivery_note: bool = Field(default=False, description="Preise auf Lieferschein andrucken")`:

```python

    # Pfandabrechnung: JE_LIEFERUNG (auf jeder Rechnung) oder KEINE (IFCO-Clearing)
    pfand_abrechnung: PfandAbrechnung = Field(
        default=PfandAbrechnung.JE_LIEFERUNG,
        description="JE_LIEFERUNG: Pfand auf jeder Rechnung; KEINE: über IFCO-Clearing, nicht auf der Rechnung",
    )
```

`CustomerUpdate`, direkt unter `show_prices_on_delivery_note: Optional[bool] = None`:

```python

    # Pfandabrechnung (weglassen = unverändert; null wird abgewiesen)
    pfand_abrechnung: Optional[PfandAbrechnung] = None

    @field_validator("pfand_abrechnung")
    @classmethod
    def _pfand_abrechnung_nicht_leer(cls, v):
        # Die Spalte ist NOT NULL. Ein ausdrückliches null ergäbe beim Commit
        # einen Datenbankfehler (500); ein weggelassenes Feld erreicht den
        # Validator nicht.
        if v is None:
            raise ValueError("pfand_abrechnung darf nicht leer sein")
        return v
```

`CustomerResponse`, direkt unter `show_prices_on_delivery_note: bool = False`:

```python
    pfand_abrechnung: PfandAbrechnung = PfandAbrechnung.JE_LIEFERUNG
```

`create_customer` (`model_dump()`) und `update_customer` (`model_dump(exclude_unset=True)`) in `backend/app/api/v1/sales.py:110-145` übernehmen das Feld ohne Änderung.

- [ ] **Step 5: Migration**

In `backend/app/tenancy.py`, `_auto_migrate`, direkt unter `_add_col_if_missing("customers", "show_prices_on_delivery_note", "BOOLEAN", "0")` (erster `try`, **nicht** hinter dem S1-Block aus Task 6):

```python
        # Pfandabrechnung je Kunde (Spec 08.10.2026): Bestandskunden JE_LIEFERUNG
        _add_col_if_missing("customers", "pfand_abrechnung", "VARCHAR(20)", "'JE_LIEFERUNG'")
```

Vorbild für den String-Default: `_add_col_if_missing("inventory_counts", "typ", "VARCHAR(20)", "'STICHPROBE'")` in derselben Funktion.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS5 -v`
Erwartet: 24 passed (18 aus Task 25, 6 aus diesem Task). In der Prüfkopie liefen die 6 Tests dieses Tasks grün.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/customer.py backend/app/schemas/customer.py \
        backend/app/tenancy.py backend/tests/test_gernot_261008.py
git commit -m "feat(kunden): Pfandabrechnung je Kunde (JE_LIEFERUNG / KEINE über IFCO-Clearing)"
```

---

### Task 27: Pfand bei `pfand_abrechnung = KEINE` (IFCO-Clearing) bleibt auf dem Lieferschein, fehlt auf der Rechnung und in ihrer Anlage

**Files:**
- Modify: `backend/app/services/invoice_service.py`:
  - Import-Block `from app.models.invoice import (` (`:14-18`) und Import `from app.models.customer import Customer, AddressType` (`:19`)
  - zwei neue Modulfunktionen direkt vor `class InvoiceService:` (hinter `waehle_vertreter` aus Task 21)
  - `create_invoice_from_order` (`:177-216`)
- Modify: `backend/app/api/v1/invoices.py`:
  - `:24` (Import)
  - `_aggregiere` (`:548-570`, nach S1 mit Signatur `_aggregiere(db, notes)`)
  - `invoice_delivery_notes` (`:654-669`)
- Modify: `backend/app/services/pdf_service.py`, Anlagen-Block „Enthaltene Lieferscheine" (`:379-395`, nach Task 21 mit Bedingung `invoice.order_id is None`)
- Modify: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes:
  - `produkt_der_position` (S1)
  - `Customer.pfand_abrechnung` und `PfandAbrechnung` (Task 26)
  - `InvoiceLineResponse.is_deposit` (Task 25, nur im Test)
  - Task 21: Die Rechnung aus Bestellung hängt einen Lieferschein an, `pdf_service.py` druckt die Anlage nur ohne Bestellbezug; `Decimal` importiert `pdf_service.py` seit Task 10
  - `InvoiceLineSource` (`app.models.invoice`, bestehend: `invoice_line_id`, `delivery_note_id`, `quantity`)
- Produces:
  - `app.services.invoice_service.ist_clearing_pfand(db: Session, kunde: Optional[Customer], line: OrderLine) -> bool`. Diese eine Regel gilt für die Rechnung aus der Bestellung und für den Sammellauf.
  - `app.services.invoice_service.netto_je_lieferschein(db: Session, invoice: Invoice, lieferscheine: list[DeliveryNote]) -> dict[UUID, Decimal]`: abgerechneter Nettobetrag je Lieferschein, auf den Cent gerundet. Grundlage sind die Positionen dieser Rechnung. Die PDF-Anlage und `GET /invoices/{id}/delivery-notes` nutzen beide diese Funktion.
  - `POST /invoices/from-order/{id}` antwortet 400 mit „IFCO-Clearing" im `detail`, wenn nach dem Filter nichts übrig bleibt.
  - `_aggregiere` liefert keine Kunden ohne Positionen.
  - Test-Helfer `_s5_ohne_forecast` (Fixture), `_s5_ware`, `_s5_bestellung`, `_s5_lieferschein` und die Konstanten `S5_PREVIEW`, `S5_COMMIT`, `S5_MAERZ`.

**Regel:**
- Pfand ist eine Bestellposition, deren Produkt (direkt oder über die Variante) `is_deposit` trägt. Beim Kunden mit `pfand_abrechnung = KEINE` fehlt sie auf jeder **neu erzeugten** Rechnung, ob aus Bestellung oder aus dem Sammellauf.
- Bestellung und Lieferschein bleiben unverändert.
- Freitext-Pfandzeilen ohne Produkt erkennt die Regel nicht; sie bleiben auf der Rechnung (siehe Offene Punkte).
- Manuell in einen Entwurf eingefügte Pfandzeilen sind eine bewusste Entscheidung und bleiben stehen.
- Die Anlage „Enthaltene Lieferscheine" rechnet aus den Positionen der Rechnung und nicht aus der Bestellung. Sonst stünde beim Clearing-Kunden in der Anlage 31,00 EUR, auf der Rechnung aber 25,00 € netto.
- Bewusst **nicht** über `ist_clearing_pfand`: Das PDF entsteht bei jedem Abruf neu. Ein später geändertes Kundenfeld `pfand_abrechnung` änderte sonst die Anlage einer versendeten Rechnung (GoBD).

- [ ] **Step 1: Failing Tests anhängen**

```python
S5_PREVIEW = "/api/v1/invoices/batch-run/preview"
S5_COMMIT = "/api/v1/invoices/batch-run/commit"
S5_MAERZ = {"period_from": "2026-03-01", "period_to": "2026-03-31"}


@pytest.fixture
def _s5_ohne_forecast(monkeypatch):
    """Jede neue Bestellung stößt ein Celery-Forecast-Update an. Ohne Redis
    hängt das je Bestellung rund 15 s im Reconnect — für diese Tests egal."""
    monkeypatch.setattr("app.api.v1.sales._trigger_forecast_update", lambda *a, **k: None)


def _s5_ware(client):
    return _s5_produkt(client, "Erbsen-Schale", "MG-ERBSE", "2.50")


def _s5_bestellung(client, kunde, ware=None, kiste=None, liefertag="2026-03-05"):
    zeilen = []
    if ware:
        zeilen.append({"product_id": ware["id"], "product_name": ware["name"],
                       "quantity": 10, "unit": "STK", "unit_price": "2.50"})
    if kiste:
        zeilen.append({"product_id": kiste["id"], "product_name": kiste["name"],
                       "quantity": 2, "unit": "STK", "unit_price": "3.00"})
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": liefertag, "lines": zeilen,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _s5_lieferschein(client, bestellung):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.usefixtures("_s5_ohne_forecast")
class TestS5PfandUeberClearing:
    """Pfand steht auf dem Lieferschein, aber nicht auf der Rechnung des Clearing-Kunden."""

    def test_rechnung_aus_bestellung_ohne_pfand(self, client):
        kunde = _s5_kunde(client, pfand_abrechnung="KEINE")
        bestellung = _s5_bestellung(client, kunde, _s5_ware(client), _s5_ifco_kiste(client))

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 201, r.text
        d = _s5_detail(client, r.json())
        assert [l["description"] for l in d["lines"]] == ["Erbsen-Schale"]
        assert _d(d["subtotal"]) == Decimal("25.00")
        assert _d(d["total_deposit"]) == Decimal("0.00")

    def test_ohne_clearing_bleibt_pfand_auf_der_rechnung(self, client):
        kunde = _s5_kunde(client, name="Großer Kern")
        bestellung = _s5_bestellung(client, kunde, _s5_ware(client), _s5_ifco_kiste(client))

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 201, r.text
        d = _s5_detail(client, r.json())
        assert sorted(l["description"] for l in d["lines"]) == ["Erbsen-Schale", "IFCO-Kiste"]
        assert [l["is_deposit"] for l in d["lines"] if l["description"] == "IFCO-Kiste"] == [True]
        assert _d(d["subtotal"]) == Decimal("31.00")

    def test_nur_pfand_beim_clearing_kunden_gibt_keine_leere_rechnung(self, client):
        kunde = _s5_kunde(client, pfand_abrechnung="KEINE")
        bestellung = _s5_bestellung(client, kunde, kiste=_s5_ifco_kiste(client))

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 400, r.text
        assert "IFCO-Clearing" in r.json()["detail"]
        assert client.get("/api/v1/invoices", params={"customer_id": kunde["id"]}).json() == []

    def test_lieferschein_behaelt_pfand(self, client):
        from tests.test_documents_preise import _pdf_text

        kunde = _s5_kunde(client, pfand_abrechnung="KEINE")
        bestellung = _s5_bestellung(client, kunde, _s5_ware(client), _s5_ifco_kiste(client))
        note = _s5_lieferschein(client, bestellung)

        pdf = client.get(f"/api/v1/sales/delivery-notes/{note['id']}/pdf")

        assert pdf.status_code == 200, pdf.text
        text = _pdf_text(pdf.content).decode("latin-1", errors="ignore")
        assert "PFAND-IFCO" in text
        assert "MG-ERBSE" in text

    def test_sammelrechnung_laesst_pfand_nur_beim_clearing_kunden_weg(self, client):
        clearing = _s5_kunde(client, name="Ökoring", pfand_abrechnung="KEINE")
        normal = _s5_kunde(client, name="Großer Kern")
        ware, kiste = _s5_ware(client), _s5_ifco_kiste(client)
        for kunde in (clearing, normal):
            _s5_lieferschein(client, _s5_bestellung(client, kunde, ware, kiste))

        vorschau = client.post(S5_PREVIEW, json=S5_MAERZ)

        assert vorschau.status_code == 200, vorschau.text
        positionen = {k["customer_name"]: sorted(p["description"] for p in k["positionen"])
                      for k in vorschau.json()["kunden"]}
        assert positionen == {"Ökoring": ["Erbsen-Schale"],
                              "Großer Kern": ["Erbsen-Schale", "IFCO-Kiste"]}

        lauf = client.post(S5_COMMIT, json=S5_MAERZ)

        assert lauf.status_code == 201, lauf.text
        summen = {x["customer_id"]: _d(x["subtotal"]) for x in lauf.json()["rechnungen"]}
        assert summen == {clearing["id"]: Decimal("25.00"), normal["id"]: Decimal("31.00")}

    def test_sammelrechnung_nur_pfand_beim_clearing_kunden_keine_rechnung(self, client):
        kunde = _s5_kunde(client, pfand_abrechnung="KEINE")
        _s5_lieferschein(client, _s5_bestellung(client, kunde, kiste=_s5_ifco_kiste(client)))

        assert client.post(S5_PREVIEW, json=S5_MAERZ).json()["kunden"] == []
        lauf = client.post(S5_COMMIT, json=S5_MAERZ)

        assert lauf.status_code == 201, lauf.text
        assert lauf.json()["rechnungen"] == []


@pytest.mark.usefixtures("_s5_ohne_forecast")
class TestS5LieferscheinAnlage:
    """Die Anlage 'Enthaltene Lieferscheine' muss zur Rechnung passen."""

    def test_sammelrechnung_anlage_ohne_clearing_pfand(self, client):
        from tests.test_documents_preise import _pdf_text

        kunde = _s5_kunde(client, pfand_abrechnung="KEINE")
        note = _s5_lieferschein(client, _s5_bestellung(client, kunde, _s5_ware(client), _s5_ifco_kiste(client)))
        rechnung = client.post(S5_COMMIT, json=S5_MAERZ).json()["rechnungen"][0]
        assert _d(rechnung["subtotal"]) == Decimal("25.00")

        anlage = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")

        assert anlage.status_code == 200, anlage.text
        assert [(x["delivery_note_number"], _d(x["betrag_netto"])) for x in anlage.json()] == [
            (note["delivery_note_number"], Decimal("25.00"))]
        pdf = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
        assert pdf.status_code == 200, pdf.text
        text = _pdf_text(pdf.content).decode("latin-1", errors="ignore")
        assert "Enthaltene Lieferscheine" in text
        assert "25.00 EUR" in text
        assert "31.00 EUR" not in text

    def test_spaeter_gesetztes_kennzeichen_aendert_die_anlage_nicht(self, client):
        """GoBD: Das PDF entsteht bei jedem Abruf neu. Die Anlage rechnet aus
        den Positionen der Rechnung, nicht aus dem heutigen Kundenfeld pfand_abrechnung."""
        kunde = _s5_kunde(client, name="Großer Kern")
        _s5_lieferschein(client, _s5_bestellung(client, kunde, _s5_ware(client), _s5_ifco_kiste(client)))
        rechnung = client.post(S5_COMMIT, json=S5_MAERZ).json()["rechnungen"][0]
        url = f"/api/v1/invoices/{rechnung['id']}/delivery-notes"
        assert [_d(x["betrag_netto"]) for x in client.get(url).json()] == [Decimal("31.00")]

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"pfand_abrechnung": "KEINE"})
        assert r.status_code == 200, r.text

        assert [_d(x["betrag_netto"]) for x in client.get(url).json()] == [Decimal("31.00")]

    def test_rechnung_aus_bestellung_ohne_clearing_pfand(self, client):
        """Task 21 hängt den Lieferschein an die Rechnung aus Bestellung; ihr
        Betrag kommt aus den Positionen mit order_item_id."""
        kunde = _s5_kunde(client, pfand_abrechnung="KEINE")
        bestellung = _s5_bestellung(client, kunde, _s5_ware(client), _s5_ifco_kiste(client))
        _s5_lieferschein(client, bestellung)
        rechnung = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert rechnung.status_code == 201, rechnung.text

        anlage = client.get(f"/api/v1/invoices/{rechnung.json()['id']}/delivery-notes").json()

        assert [_d(x["betrag_netto"]) for x in anlage] == [Decimal("25.00")]
```

`betrag_netto` kommt als JSON-Zahl (`25.0`); `_d` macht daraus `Decimal('25.0')`, und das ist gleich `Decimal('25.00')`.

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS5PfandUeberClearing tests/test_gernot_261008.py::TestS5LieferscheinAnlage -v`

Erwartet: 6 FAIL, 3 grün.

- `test_rechnung_aus_bestellung_ohne_pfand`: `['Erbsen-Schale', 'IFCO-Kiste'] == ['Erbsen-Schale']`
- `test_nur_pfand_…_keine_leere_rechnung`: 201 statt 400
- `test_sammelrechnung_laesst_pfand_…`: Vorschau enthält die IFCO-Kiste bei Ökoring
- `test_sammelrechnung_nur_pfand_…`: Vorschau nicht leer
- `test_sammelrechnung_anlage_ohne_clearing_pfand`: `assert Decimal('31.00') == Decimal('25.00')` (Summe der Rechnung)
- `test_rechnung_aus_bestellung_ohne_clearing_pfand`: `assert [Decimal('31.0')] == [Decimal('25.00')]`

Grün sind bereits:
- `test_ohne_clearing_bleibt_pfand_auf_der_rechnung`: sichert das Bestandsverhalten.
- `test_lieferschein_behaelt_pfand`.
- `test_spaeter_gesetztes_kennzeichen_aendert_die_anlage_nicht`: ein Wächter. Er wird rot, wenn die Anlage über `ist_clearing_pfand` statt aus den Positionen rechnet.

Ist `test_ohne_clearing_bleibt_pfand_auf_der_rechnung` rot, weil `is_deposit` fehlt oder die Pfandzeile ohne Kennzeichen ankommt: S1 oder Task 25 fehlt. Stoppen und melden.

- [ ] **Step 3: Eine Regel für beide Wege**

In `backend/app/services/invoice_service.py` direkt vor `class InvoiceService:` (hinter `waehle_vertreter` aus Task 21):

```python
def ist_clearing_pfand(db: Session, kunde: Optional[Customer], line: OrderLine) -> bool:
    """Gehört diese Bestellposition NICHT auf die Rechnung?

    Kunden mit pfand_abrechnung = KEINE (z. B. Ökoring, Bodan) rechnen das
    Pfand für IFCO-Kisten über das IFCO-Clearing ab, nicht über Minga Greens.
    Die Pfandposition bleibt auf Bestellung und Lieferschein (Nachweis der
    gelieferten Kisten), fehlt aber auf der Rechnung. Erkannt wird Pfand am
    Produktstamm (is_deposit) — Freitext-Pfandzeilen ohne Produkt bleiben
    stehen, weil nichts sie als Pfand ausweist. MONATLICH (Leergutkonto)
    kommt mit Paket 3 und muss hier ergänzt werden.
    """
    if kunde is None or kunde.pfand_abrechnung != PfandAbrechnung.KEINE:
        return False
    produkt = produkt_der_position(db, line.product_id, line.product_variant_id)
    return produkt is not None and bool(produkt.is_deposit)
```

`Session`, `Optional`, `Customer` und `OrderLine` importiert die Datei bereits. `PfandAbrechnung` in den bestehenden Import aufnehmen: `from app.models.customer import Customer, AddressType` wird zu `from app.models.customer import Customer, AddressType, PfandAbrechnung`. `produkt_der_position` importiert sie seit S1 (`from app.services.steuersatz import produkt_der_position`).

- [ ] **Step 4: Rechnung aus Bestellung**

In `InvoiceService.create_invoice_from_order` direkt nach

```python
        if not order:
            raise ValueError("Bestellung nicht gefunden")
```

einfügen:

```python

        # Pfand über IFCO-Clearing bleibt auf dem Lieferschein, nicht auf der
        # Rechnung. Vor dem Anlegen prüfen: eine reine Pfandbestellung ergäbe
        # sonst eine leere Rechnung (und verbrauchte eine Nummer).
        positionen = [l for l in order.lines if not ist_clearing_pfand(self.db, order.customer, l)]
        if order.lines and not positionen:
            raise ValueError(
                "Die Bestellung enthält nur Pfandpositionen. Dieser Kunde rechnet Pfand "
                "über IFCO-Clearing ab — es gibt nichts zu fakturieren."
            )
```

Danach in derselben Funktion die Schleife `for line in order.lines:` (unter `# Positionen aus Bestellung übernehmen`) ändern zu:

```python
        for line in positionen:
```

Was S1 und S6 in dieser Funktion eingebaut haben (Satz aus dem Produkt, Sperre gegen eine zweite Rechnung, Lieferschein-Zuordnung), bleibt unverändert. Der Endpunkt `create_invoice_from_order` in `invoices.py` macht aus dem `ValueError` bereits 400.

- [ ] **Step 5: Sammellauf**

In `backend/app/api/v1/invoices.py` die Importzeile `from app.services.invoice_service import InvoiceService, BereitsAbgerechnet, waehle_vertreter` **vollständig** ersetzen durch:

```python
from app.services.invoice_service import InvoiceService, BereitsAbgerechnet, waehle_vertreter, ist_clearing_pfand
```

In `_aggregiere` als erste Anweisung in der Schleife `for line in order.lines:`, also vor S1s Zeile `produkt = produkt_der_position(...)`:

```python
            # Pfand über IFCO-Clearing steht auf dem Lieferschein, nicht auf
            # der Rechnung — dieselbe Regel wie bei der Rechnung aus Bestellung.
            if ist_clearing_pfand(db, order.customer, line):
                continue
```

Am Ende von `_aggregiere` die Zeile `return kunden` ersetzen durch:

```python
    # Wer im Zeitraum nur Clearing-Pfand geliefert bekam, bekommt keine leere
    # Rechnung — und taucht auch in der Vorschau nicht auf.
    return {kid: k for kid, k in kunden.items() if k["positionen"]}
```

Vorschau und Festschreiben rufen beide `_aggregiere`; damit gilt die Regel für beide. Die Lieferscheine eines so herausgefallenen Kunden bleiben ohne `invoice_id`. Das ist gewollt: Es gibt nichts abzurechnen.

Zwischenstand: `test_sammelrechnung_anlage_ohne_clearing_pfand` und `test_rechnung_aus_bestellung_ohne_clearing_pfand` sind jetzt noch rot (`betrag_netto` 31.0 statt 25.00). Das behebt Step 6.

- [ ] **Step 6: Anlage „Enthaltene Lieferscheine" aus den Positionen der Rechnung**

**6a.** In `backend/app/services/invoice_service.py` im Import-Block `from app.models.invoice import (` die Zeile

```python
    Invoice, InvoiceLine, Payment,
```

ersetzen durch

```python
    Invoice, InvoiceLine, InvoiceLineSource, Payment,
```

**6b.** Direkt unter `ist_clearing_pfand` (Step 3), vor `class InvoiceService:`:

```python
def netto_je_lieferschein(db: Session, invoice: Invoice, lieferscheine: list[DeliveryNote]) -> dict[UUID, Decimal]:
    """Abgerechneter Nettobetrag je Lieferschein dieser Rechnung.

    Für die Anlage "Enthaltene Lieferscheine" im Rechnungs-PDF und für
    GET /invoices/{id}/delivery-notes. Gerechnet wird aus den Positionen
    DIESER Rechnung, nicht aus der Bestellung: Clearing-Pfand steht auf
    Bestellung und Lieferschein, aber nicht auf der Rechnung — die Anlage
    muss zur Rechnung passen. Bewusst nicht über ist_clearing_pfand: Das PDF
    entsteht bei jedem Abruf neu, ein später geändertes Kundenfeld
    änderte sonst die Anlage einer versendeten Rechnung (GoBD).

    - Sammelrechnung: invoice_line_sources (Menge je Lieferschein) mal
      Einzelpreis der Position, nach Positionsrabatt.
    - Rechnung aus Bestellung (S6 hängt genau einen Lieferschein an, ohne
      invoice_line_sources): die Positionen, deren order_item_id zur
      Bestellung des Lieferscheins gehört.
    Der Rabatt auf die ganze Rechnung (Kopfrabatt) bleibt wie bisher außen vor.
    """
    betraege = {n.id: Decimal("0") for n in lieferscheine}
    mit_quelle = set()
    quellen = db.execute(
        select(InvoiceLineSource.delivery_note_id, InvoiceLineSource.quantity,
               InvoiceLine.unit_price, InvoiceLine.discount_percent)
        .join(InvoiceLine, InvoiceLineSource.invoice_line_id == InvoiceLine.id)
        .where(InvoiceLine.invoice_id == invoice.id)
    ).all()
    for note_id, menge, preis, rabatt in quellen:
        if note_id in betraege:
            betraege[note_id] += menge * preis * (1 - (rabatt or Decimal("0")) / 100)
            mit_quelle.add(note_id)
    for note in lieferscheine:
        if note.id in mit_quelle or note.order is None:
            continue
        bestellzeilen = {l.id for l in note.order.lines}
        betraege[note.id] = sum(
            (l.line_total for l in invoice.lines if l.order_item_id in bestellzeilen),
            Decimal("0"),
        )
    return {nid: b.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) for nid, b in betraege.items()}
```

`select`, `Decimal`, `ROUND_HALF_UP`, `UUID`, `Invoice` und `InvoiceLine` importiert die Datei bereits, `DeliveryNote` seit Task 20.

**6c.** In `backend/app/services/pdf_service.py`, im Block „Enthaltene Lieferscheine" (nach Task 21 mit `if db is not None and invoice.order_id is None:`), ersetzen

```python
            if enthaltene:
                elements.append(Paragraph("<b>Enthaltene Lieferscheine</b>", styles['Normal']))
```

durch

```python
            if enthaltene:
                # Beträge aus den Positionen dieser Rechnung, nicht aus der
                # Bestellung — Clearing-Pfand steht nicht auf der Rechnung (S5).
                from app.services.invoice_service import netto_je_lieferschein
                betraege = netto_je_lieferschein(db, invoice, enthaltene)
                elements.append(Paragraph("<b>Enthaltene Lieferscheine</b>", styles['Normal']))
```

Danach in der Schleife `for n in enthaltene:` den Block

```python
                    betrag = sum(
                        (l.quantity * l.unit_price for l in (n.order.lines if n.order else [])),
                        Decimal("0"),
                    )
```

ersatzlos entfernen und in `ls_daten.append([...])` die Zeile `f"{betrag:.2f} EUR",` ersetzen durch

```python
                        f"{betraege[n.id]:.2f} EUR",
```

Der Import steht im Block, wie die übrigen dort (`_select`, `_DN`); `invoice_service` importiert `pdf_service` nicht. `from decimal import Decimal` aus Task 10 bleibt am Dateikopf stehen.

**6d.** In `backend/app/api/v1/invoices.py`, `invoice_delivery_notes`, ersetzen

```python
    return [{
        "id": str(n.id),
        "delivery_note_number": n.delivery_note_number,
        "lieferdatum": (n.actual_delivery_date or n.order.requested_delivery_date).isoformat(),
        "betrag_netto": sum((l.quantity * l.unit_price for l in n.order.lines), Decimal("0")),
    } for n in notes]
```

durch

```python
    # Betrag aus den Positionen dieser Rechnung, nicht aus der Bestellung —
    # sonst zählte Clearing-Pfand mit (dieselbe Regel wie die PDF-Anlage).
    betraege = netto_je_lieferschein(db, invoice, notes)
    return [{
        "id": str(n.id),
        "delivery_note_number": n.delivery_note_number,
        "lieferdatum": (n.actual_delivery_date or n.order.requested_delivery_date).isoformat(),
        "betrag_netto": betraege[n.id],
    } for n in notes]
```

**6e.** Die Importzeile aus Step 5 **vollständig** ersetzen durch:

```python
from app.services.invoice_service import InvoiceService, BereitsAbgerechnet, waehle_vertreter, ist_clearing_pfand, netto_je_lieferschein
```

- [ ] **Step 7: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS5 -v`
Erwartet: 33 passed.

Endet `test_sammelrechnung_anlage_ohne_clearing_pfand` mit 500 und `NameError: name 'Decimal' is not defined` beim PDF-Abruf, fehlt der `Decimal`-Import aus Task 10. Dann stoppen und melden.

- [ ] **Step 8: Bestandstests Sammelrechnung, Storno und Rechnungs-PDF**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_sammelrechnung.py tests/test_storno.py tests/test_pfand_rabatt.py tests/test_documents_preise.py tests/test_gernot_260817.py -q`
Erwartet: dieselben Fehlernamen wie vor Task 25 (in der Prüfkopie: keine). `test_gernot_261008.py` läuft hier ganz, also auch mit den S6-Tests, darunter `test_sammelrechnung_behaelt_die_lieferscheinanlage`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/invoice_service.py backend/app/api/v1/invoices.py \
        backend/app/services/pdf_service.py backend/tests/test_gernot_261008.py
git commit -m "feat(rechnung): Clearing-Pfand bleibt auf dem Lieferschein, nicht auf der Rechnung; Lieferschein-Anlage aus den Rechnungspositionen"
```

---

### Task 28: Rechnungsliste neueste zuerst, bis 100 Einträge, Kürzung sichtbar

**Files:**
- Modify: `backend/app/api/v1/invoices.py:64` (`list_invoices`)
- Modify: `frontend/src/services/api.ts:711-712` (`invoicesApi.list`)
- Modify: `frontend/src/pages/Invoices.tsx:41`, `:75-83`, `:227`, `:304`
- Modify: `frontend/src/pages/Dashboard.tsx:82`, `:336`
- Modify: `backend/tests/test_gernot_261008.py`

**Interfaces:**
- Consumes: `GET /invoices?order_id=` und `invoicesApi.list({ order_id })` (beide Task 24); Helfer `_s5_ohne_forecast`, `_s5_ware`, `_s5_bestellung` (Task 27).
- Produces:
  - `GET /api/v1/invoices` liefert `invoice_date` absteigend, bei gleichem Tag `invoice_number` absteigend. Die Standard-Seitengröße bleibt 20 für andere Aufrufer; `page_size` bis 100 (Obergrenze `PaginationParams` in `backend/app/api/deps.py:156-166`).
  - `invoicesApi.list` nimmt zusätzlich `page_size?: number`; `order_id?: string` steht seit Task 24 drin. Task 29 nutzt beides.

Muster wie beim Saatgut-Fix vom 02.10.2026 (`319f63f`): `page_size: 100` plus sichtbarer Hinweis bei genau 100 Einträgen.

- [ ] **Step 1: Failing Tests anhängen**

```python
class TestS5Rechnungsliste:
    """Die Liste kürzte still auf 20 und sortierte gleiche Tage zufällig."""

    def test_neueste_zuerst_auch_am_selben_tag(self, client):
        kunde = _s5_kunde(client)
        nummern = [_s5_entwurf(client, kunde)["invoice_number"] for _ in range(3)]

        r = client.get("/api/v1/invoices")

        assert r.status_code == 200, r.text
        assert [x["invoice_number"] for x in r.json()] == list(reversed(nummern))

    def test_seitengroesse_100(self, client):
        """Vertrag fürs Frontend: page_size=100 liefert alle (bisher 20 still)."""
        kunde = _s5_kunde(client)
        for _ in range(25):
            _s5_entwurf(client, kunde)

        assert len(client.get("/api/v1/invoices").json()) == 20
        assert len(client.get("/api/v1/invoices", params={"page_size": 100}).json()) == 25

    @pytest.mark.usefixtures("_s5_ohne_forecast")
    def test_filter_nach_bestellung(self, client):
        """Vertrag aus S6 (GET /invoices?order_id=), auf den der Belege-Dialog baut."""
        kunde = _s5_kunde(client)
        ware = _s5_ware(client)
        eins = _s5_bestellung(client, kunde, ware)
        zwei = _s5_bestellung(client, kunde, ware)
        r1 = client.post(f"/api/v1/invoices/from-order/{eins['id']}").json()
        client.post(f"/api/v1/invoices/from-order/{zwei['id']}")

        r = client.get("/api/v1/invoices", params={"order_id": eins["id"]})

        assert r.status_code == 200, r.text
        assert [x["id"] for x in r.json()] == [r1["id"]]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py::TestS5Rechnungsliste -v`

Erwartet: `test_neueste_zuerst_auch_am_selben_tag` FAIL. Die Liste beginnt mit der ältesten Nummer `RE-2026-00001`.

`test_seitengroesse_100` und `test_filter_nach_bestellung` sind grün. Der zweite sichert den S6-Vertrag. **Ist `test_filter_nach_bestellung` rot**, fehlt der `order_id`-Filter aus S6, und der Dialog in Task 29 würde fremde Rechnungen zeigen. In dem Fall stoppen und melden.

- [ ] **Step 3: Stabile Sortierung**

In `list_invoices` die Zeile `query = query.order_by(Invoice.invoice_date.desc())` ersetzen durch:

```python
    # Neueste zuerst, stabil: am selben Tag entscheidet die Nummer. Nur nach
    # Datum sortiert lieferte SQLite gleiche Tage in Einfügereihenfolge, und
    # die neueste Rechnung des Tages stand hinten oder fiel aus der Seite.
    query = query.order_by(Invoice.invoice_date.desc(), Invoice.invoice_number.desc())
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -k TestS5 -v`
Erwartet: 36 passed.

- [ ] **Step 5: Frontend — Parameter**

In `frontend/src/services/api.ts`, `invoicesApi`, die Zeile `list: (params?: { …; to_date?: string; order_id?: string }) =>` (Stand nach Task 24) samt der Folgezeile vollständig ersetzen durch:

```ts
  list: (params?: { status?: InvoiceStatus; customer_id?: string; invoice_type?: InvoiceType; from_date?: string; to_date?: string; order_id?: string; page_size?: number }) =>
    api.get<Invoice[]>('/invoices', { params }).then(r => r.data),
```

- [ ] **Step 6: Frontend — Rechnungsliste**

In `frontend/src/pages/Invoices.tsx` direkt vor `const TYPE_LABELS`:

```tsx
// Die Rechnungsliste lädt bis zu 100 Rechnungen (Obergrenze des Backends).
// Kommen genau 100 zurück, ist sie womöglich gekürzt — das muss sichtbar sein.
const LISTENGRENZE = 100;
```

In der Abfrage `queryKey: ['invoices', { status: filterStatus, invoice_type: filterType }]` den Aufruf um `page_size` ergänzen:

```tsx
      invoicesApi.list({
        status: filterStatus === 'all' ? undefined : filterStatus as InvoiceStatus,
        invoice_type: filterType === 'all' ? undefined : filterType as InvoiceType,
        page_size: LISTENGRENZE,
      }),
```

`PageHeader`-Untertitel:

```tsx
        subtitle={`${invoices.length === LISTENGRENZE ? `${LISTENGRENZE}+` : invoices.length} Rechnungen`}
```

Direkt nach `</FilterBar>`:

```tsx

      {invoices.length === LISTENGRENZE && (
        <p className="mb-2 text-sm text-amber-700 dark:text-amber-300">
          Es werden die neuesten {LISTENGRENZE} Rechnungen angezeigt. Ältere Rechnungen über den Status- oder Typfilter eingrenzen.
        </p>
      )}
```

Status- und Typfilter wirken serverseitig (sie gehen als Parameter an `/invoices`). Der Hinweis ist deshalb ein echter Ausweg.

- [ ] **Step 7: Frontend — Dashboard-Kachel „Offene Rechnungen"**

In `frontend/src/pages/Dashboard.tsx` die Zeile `queryFn: () => invoicesApi.list({ status: 'OFFEN' }),` ersetzen durch:

```tsx
    // page_size: ohne Angabe kürzt das Backend still auf 20
    queryFn: () => invoicesApi.list({ status: 'OFFEN', page_size: 100 }),
```

Die Anzeige `{invoicesData?.length || 0}` ersetzen durch:

```tsx
                    {invoicesData?.length === 100 ? '100+' : invoicesData?.length || 0}
```

- [ ] **Step 8: Build**

Run: `cd frontend && npm run build`. Erwartet: keine TypeScript-Fehler. Die vorhandene Warnung „Some chunks are larger than 500 kB" ist Bestand.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_gernot_261008.py \
        frontend/src/services/api.ts frontend/src/pages/Invoices.tsx frontend/src/pages/Dashboard.tsx
git commit -m "fix(rechnung): Rechnungsliste neueste zuerst, bis 100 Einträge, Kürzung sichtbar"
```

---

### Task 29: Entwurf in der Oberfläche prüfen und bearbeiten

**Files:**
- Modify: `frontend/src/pages/Invoices.tsx`, Zeilen auf `main`:
  - `:474` (Knopf „Details")
  - `:957-958` (`InvoiceDetail`)
  - `:963-967` (Abfrage `['invoice', id]` in `InvoiceDetail`)
  - `:1051-1057` (`deleteLineMutation`)
  - `:1189` (Beschreibungszelle)
  - `:1200` (Löschknopf)
  - `:1212` („Keine Positionen")
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx:3`, `:8`, `:43-47` (nach Task 24 mit Kommentar davor), `:52`, `:130`, `:300-345`
- Modify: `frontend/src/pages/Customers.tsx:7` (Typ-Import), `:245` (Formularzustand), `:258-263` (nach `customerTypeOptions`), `:414` (nach der Checkbox „Preise auf Lieferschein andrucken")
- Modify: `frontend/src/types/index.ts:170` (`Customer`), `:176` (neuer Typ `PfandAbrechnung`), `:644` (`InvoiceLine`)

**Interfaces:**
- Consumes:
  - `InvoiceLineResponse.is_deposit` (Task 25)
  - `Customer.pfand_abrechnung` (Task 26)
  - `invoicesApi.list({ order_id, page_size })` (Task 28, Backend-Filter und `order_id`-Parameter Task 24)
  - Belege-Dialog in der Task 24-Fassung (`invoicesQuery` mit `invoicesApi.list({ order_id: orderId! })`, `aktiveRechnung`, `rechnungMoeglich`)
- Produces:
  - `export function InvoiceDetail` aus `frontend/src/pages/Invoices.tsx`. Die Komponente lädt die Rechnung beim Öffnen immer vom Server nach (`refetchOnMount: 'always'`).
  - Im Belege-Dialog lassen sich die Positionen jeder Rechnung aufklappen und im Entwurf dort bearbeiten (hinzufügen, löschen).

**Entscheidung:** `InvoiceDetail` wird exportiert und im Dialog **inline aufgeklappt**, nicht als zweites Modal. Zwei gestapelte `Modal`s schließen beide auf Escape, und das innere setzt beim Schließen `document.body.style.overflow` zurück (`frontend/src/components/ui/Modal.tsx:43-53`). Ein Umzug von `InvoiceDetail` in eine eigene Datei (~370 Zeilen) gehört nicht in dieses Paket: Er erzeugt Konfliktfläche mit S1–S6, ohne etwas zu beheben. Eine Kreisabhängigkeit entsteht nicht, weil `Invoices.tsx` nichts aus `OrderDocumentsModal` importiert.

**Entscheidung Nachladen:** `InvoiceDetail` bekommt den Listeneintrag als `initialData`, und der hat keine Positionen (siehe Ausgangsbefund). Das trifft die Rechnungsliste und den Belege-Dialog gleichermaßen. Fix: `refetchOnMount: 'always'` an der Abfrage `['invoice', id]`. Verworfen:
- `placeholderData`
- `initialDataUpdatedAt: 0`

Mit beiden bliebe eine bereits geladene Rechnung bis zu 60 s ungeprüft im Cache. Finalisieren im Belege-Dialog invalidiert aber nur `['invoices']`, nicht `['invoice', id]`. Ein erneutes „Bearbeiten" zeigte dann noch den Entwurf mit Löschknöpfen. Solange die Positionen fehlen, steht „Positionen werden geladen …" statt „Keine Positionen", bei einem Ladefehler ein Hinweis.

- [ ] **Step 1: Typen**

In `frontend/src/types/index.ts` direkt nach `export type CustomerType = 'GASTRO' | 'HANDEL' | 'GEWERBE' | 'PRIVAT'` (`:176`):

```ts

/** Pfandabrechnung je Kunde (Backend: PfandAbrechnung). MONATLICH folgt mit Paket 3. */
export type PfandAbrechnung = 'JE_LIEFERUNG' | 'KEINE'
```

In `interface Customer`, unter `show_prices_on_delivery_note?: boolean`:

```ts
  /** Pfandabrechnung: JE_LIEFERUNG = Pfand auf jeder Rechnung, KEINE = IFCO-Clearing (nicht auf der Rechnung) */
  pfand_abrechnung?: PfandAbrechnung
```

In `interface InvoiceLine`, unter `buchungskonto?: string | null`:

```ts
  /** Pfandposition (Produkt mit is_deposit) */
  is_deposit?: boolean
```

- [ ] **Step 2: `InvoiceDetail` exportieren, Löschen mit Rückfrage und Fehlermeldung, Pfand kennzeichnen**

In `frontend/src/pages/Invoices.tsx`:

```tsx
// Invoice Detail — auch im Belege-Dialog der Bestellung (OrderDocumentsModal)
export function InvoiceDetail({ invoice: initial }: { invoice: Invoice }) {
```

(ersetzt `// Invoice Detail` und `function InvoiceDetail(...)`).

Direkt darunter die Abfrage

```tsx
  const { data: refreshed } = useQuery({
    queryKey: ['invoice', initial.id],
    queryFn: () => invoicesApi.get(initial.id),
    initialData: initial,
  });
```

ersetzen durch:

```tsx
  const { data: refreshed, isError: detailFehler } = useQuery({
    queryKey: ['invoice', initial.id],
    queryFn: () => invoicesApi.get(initial.id),
    initialData: initial,
    // initialData ist der Listeneintrag. GET /invoices liefert ihn ohne
    // Positionen (InvoiceResponse, kein lines). Mit staleTime 60 s aus
    // main.tsx gälte er als frisch und würde beim Öffnen nicht nachgeladen —
    // der Dialog zeigte "Keine Positionen" und keinen Löschknopf (B4).
    refetchOnMount: 'always',
  });
```

Den Kommentar `// Refetch invoice details after every mutation …` darüber stehen lassen.

`deleteLineMutation` um `onError` ergänzen:

```tsx
  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => invoicesApi.deleteLine(invoice.id, lineId),
    onSuccess: () => {
      invalidate();
      toast.success('Position entfernt');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Position konnte nicht entfernt werden')),
  });
```

Beschreibungszelle der Positionstabelle (`<td className="py-2">{line.description}</td>`) ersetzen durch:

```tsx
                  <td className="py-2">
                    {line.description}
                    {line.is_deposit && (
                      <Badge variant="info" size="sm" className="ml-2">Pfand</Badge>
                    )}
                  </td>
```

Am Löschknopf (`title="Position entfernen"`) die Zeile `onClick={() => deleteLineMutation.mutate(line.id)}` ersetzen durch:

```tsx
                        disabled={deleteLineMutation.isPending}
                        onClick={() => {
                          if (!confirm(`Position „${line.description}" aus dem Entwurf entfernen?`)) return;
                          deleteLineMutation.mutate(line.id);
                        }}
```

`window.confirm` wie bei der Mahnung in derselben Datei (`:442`). `ConfirmDialog` wäre ein gestapeltes Modal (siehe Entscheidung oben).

Im Leerzustand der Positionstabelle (`:1212`) die Zeile

```tsx
          <p className="text-gray-500 dark:text-gray-400 text-sm">Keine Positionen</p>
```

ersetzen durch:

```tsx
          <p className="text-gray-500 dark:text-gray-400 text-sm">
            {invoice.lines
              ? 'Keine Positionen'
              : detailFehler
                ? 'Positionen konnten nicht geladen werden.'
                : 'Positionen werden geladen …'}
          </p>
```

Ob `lines` fehlt, trennt verlässlich: `GET /invoices/{id}` liefert immer ein Array, auch ein leeres. Ohne das Feld ist es noch der Listeneintrag.

In der Aktionsspalte der Rechnungsliste (Funktion `Invoices`, `:473-475`) den Knopf `Details` beschriften:

```tsx
                    <Button variant="ghost" size="sm" onClick={() => setSelectedInvoice(invoice)}>
                      {invoice.status === 'ENTWURF' ? 'Bearbeiten' : 'Details'}
                    </Button>
```

- [ ] **Step 3: Belege-Dialog**

In `frontend/src/components/domain/OrderDocumentsModal.tsx`:

Zeile 3, Icon ergänzen:

```tsx
import { FileText, Truck, Package, Send, Download, Plus, CheckCheck, Receipt, Mail, Pencil } from 'lucide-react';
```

Unter `import { getErrorMessage } from '../../services/errors';`:

```tsx
import { InvoiceDetail } from '../../pages/Invoices';
```

`invoicesQuery` in der Fassung aus Task 24 Step 4 (vier Kommentarzeilen `// Serverseitig gefiltert: …` und der `useQuery`-Block mit `queryKey: ['order-invoices', orderId]` und `invoicesApi.list({ order_id: orderId! })`) **vollständig** ersetzen durch:

```tsx
  // Serverseitig gefiltert: Rechnung aus Bestellung (order_id) und
  // Sammelrechnung (über den Lieferschein). Früher wurden die 20 neuesten
  // Rechnungen clientseitig gefiltert — ab Rechnung 21 stand hier "keine
  // Rechnung", und der Knopf erzeugte eine Doppelrechnung.
  // page_size 100: ohne Angabe kürzt das Backend still auf 20.
  // Schlüssel unter 'invoices', damit Änderungen im Entwurf (InvoiceDetail
  // invalidiert ['invoices']) auch diese Liste neu laden.
  const invoicesQuery = useQuery({
    queryKey: ['invoices', 'order', orderId],
    queryFn: () => invoicesApi.list({ order_id: orderId!, page_size: 100 }),
    enabled: open && !!orderId,
  });
```

**Vorbedingung:** Steht dort noch `invoicesApi.list({}).then((rows) => rows.filter(…))`, fehlt Task 24. Dann stoppen und melden; den Block nicht selbst auf den Filter umbauen. `aktiveRechnung` und `rechnungMoeglich` aus Task 24 bleiben unverändert. Sie lesen weiter `invoicesQuery`.

In `invalidate` die Zeile `queryClient.invalidateQueries({ queryKey: ['order-invoices', orderId] });` ersatzlos entfernen. Das `['invoices']` darunter trifft den neuen Schlüssel bereits als Präfix. Danach darf `order-invoices` in `frontend/src` nicht mehr vorkommen: `grep -rn "order-invoices" frontend/src` liefert nichts.

Unter `const [signedByInput, setSignedByInput] = useState<Record<string, string>>({});` (vor `if (!order) return null;`, Hook-Reihenfolge):

```tsx
  // Aufgeklappte Rechnung: Positionen prüfen und im Entwurf bearbeiten
  const [offeneRechnung, setOffeneRechnung] = useState<string | null>(null);
```

Im Abschnitt `{/* RECHNUNGEN */}` drei gezielte Änderungen in `invoices.map(...)`. Den übrigen Inhalt nicht anfassen; S3/S6 können dort Knöpfe geändert haben.

(a) Das `<li>` wird zum Block, die bisherige Zeile kommt in einen eigenen Flex-Container:

```tsx
                <li key={inv.id} className="border rounded p-2 dark:border-gray-700">
                  <div className="flex items-center justify-between">
```

(ersetzt `<li key={inv.id} className="flex items-center justify-between border rounded p-2 dark:border-gray-700">`).

(b) Als erstes Kind von `<div className="flex gap-1">` dieser Zeile, vor dem Knopf `PDF`. Gemeint ist das `<div className="flex gap-1">` innerhalb von `invoices.map(...)`; dieselbe Klasse steht auch in den Abschnitten Auftragsbestätigungen und Lieferscheine, dort nichts einfügen:

```tsx
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Pencil className="w-3 h-3" />}
                      onClick={() => setOffeneRechnung(offeneRechnung === inv.id ? null : inv.id)}
                    >
                      {inv.status === 'ENTWURF' ? 'Bearbeiten' : 'Positionen'}
                    </Button>
```

(c) Direkt vor dem schließenden `</li>` dieser Zeile den neuen Flex-Container schließen und die aufgeklappte Ansicht anhängen:

```tsx
                  </div>
                  {offeneRechnung === inv.id && (
                    <div className="mt-3 border-t pt-3 dark:border-gray-700">
                      <InvoiceDetail invoice={inv} />
                    </div>
                  )}
```

`inv` ist ein Listeneintrag ohne Positionen. Die Positionen holt `InvoiceDetail` beim Aufklappen über `GET /invoices/{id}`, weil Step 2 `refetchOnMount: 'always'` setzt. Ohne diese Option zeigte der Dialog hier „Keine Positionen" (siehe Ausgangsbefund). Für Entwürfe zeigt es Kopfdaten, Positionen mit Löschknopf und „Position hinzufügen", sonst eine reine Ansicht.

- [ ] **Step 4: Kundenformular — Auswahl „Pfandabrechnung"**

In `frontend/src/pages/Customers.tsx`:

Zeile 7, Typ-Import ergänzen:

```tsx
import { Customer, CustomerType, Contact, CustomerAddress, AddressType, PfandAbrechnung } from '../types';
```

In `CustomerForm`, im `useState` direkt unter `show_prices_on_delivery_note: customer?.show_prices_on_delivery_note ?? false,`:

```tsx
    pfand_abrechnung: customer?.pfand_abrechnung ?? ('JE_LIEFERUNG' as PfandAbrechnung),
```

Direkt nach der Liste `customerTypeOptions` (endet mit `{ value: 'PRIVAT', label: 'Privat' },` und `];`), vor `const handleSubmit`:

```tsx

  // Pfandabrechnung je Kunde (Spec 08.10.2026). MONATLICH (Leergutkonto) folgt mit Paket 3.
  const pfandAbrechnungOptions: SelectOption[] = [
    { value: 'JE_LIEFERUNG', label: 'Pfand auf jeder Rechnung' },
    { value: 'KEINE', label: 'Pfand nicht auf der Rechnung (IFCO-Clearing)' },
  ];
```

Direkt nach dem `</label>`, das die Checkbox „Preise auf Lieferschein andrucken" schließt (noch im Kasten „Konditionen"):

```tsx
        <div className="mt-4">
          <Select
            label="Pfandabrechnung"
            options={pfandAbrechnungOptions}
            value={formData.pfand_abrechnung}
            onChange={(e) => setFormData({ ...formData, pfand_abrechnung: e.target.value as PfandAbrechnung })}
          />
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Bei „IFCO-Clearing“ stehen Pfandkisten auf Bestellung und Lieferschein, aber nicht auf neu erzeugten Rechnungen.
          </p>
        </div>
```

`handleSubmit` schickt `...formData` mit; `salesApi.createCustomer`/`updateCustomer` nehmen `Partial<Customer>`. Das Feld geht ohne weitere Änderung an `POST`/`PATCH /sales/customers`. Muster wie die Auswahl „Kundentyp" (`e.target.value as CustomerType`). In einer Kopie von `efcea00` mit genau diesen Änderungen an `types/index.ts` und `Customers.tsx` lief `tsc --noEmit -p tsconfig.json` fehlerfrei.

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`. Erwartet: keine TypeScript-Fehler (`noUnusedLocals` ist aktiv: `Pencil` und `InvoiceDetail` werden benutzt, `Invoice` bleibt im Dialog benutzt). Die Warnung „Some chunks are larger than 500 kB" ist Bestand.

- [ ] **Step 6: Nachladen prüfen**

Für das Frontend gibt es keine Unit-Tests (kein vitest/jest im Projekt). Deshalb zwei Prüfungen ohne Browser und ohne Netzwerk.

(a) Die Option steht genau einmal, in `InvoiceDetail`:

Run: `cd frontend && grep -n "refetchOnMount: 'always'" src/pages/Invoices.tsx`
Erwartet: genau ein Treffer, wenige Zeilen unter `export function InvoiceDetail`.

(b) Den Mechanismus mit der installierten React-Query-Version und den App-Defaults aus `main.tsx` nachstellen. Datei `/tmp/s5_nachladen.mjs` anlegen (außerhalb des Repos, nicht committen):

```js
// Stellt InvoiceDetail mit den App-Defaults aus main.tsx nach.
const { QueryClient, QueryObserver } = await import(process.argv[2]);

async function lauf(extra) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: 1000 * 60, retry: 1, refetchOnWindowFocus: false } },
  });
  client.mount();
  let abrufe = 0;
  const listeneintrag = { id: 'x', status: 'ENTWURF' }; // wie GET /invoices: ohne lines
  const obs = new QueryObserver(client, {
    queryKey: ['invoice', 'x'],
    queryFn: async () => { abrufe++; return { ...listeneintrag, lines: [{ id: 'l1' }] }; },
    initialData: listeneintrag,
    ...extra,
  });
  const abmelden = obs.subscribe(() => {});
  await new Promise((r) => setTimeout(r, 50));
  const positionen = obs.getCurrentResult().data?.lines?.length ?? 'keine';
  abmelden();
  client.clear();
  return `${JSON.stringify(extra)} abrufe=${abrufe} positionen=${positionen}`;
}

console.log(await lauf({}));
console.log(await lauf({ refetchOnMount: 'always' }));
```

Run: `cd frontend && node /tmp/s5_nachladen.mjs "$PWD/node_modules/@tanstack/query-core/build/modern/index.js"`
Erwartet, wörtlich:

```
{} abrufe=0 positionen=keine
{"refetchOnMount":"always"} abrufe=1 positionen=1
```

Die erste Zeile ist der Fehler von heute, die zweite der Fix. Weicht die Ausgabe ab, etwa weil eine andere React-Query-Version installiert ist: stoppen und melden.

- [ ] **Step 7: Prozedur V (Vollauf)**

Erwartet: `comm -13` ohne Ausgabe; `comm -23` nennt genau `FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Invoices.tsx frontend/src/components/domain/OrderDocumentsModal.tsx \
        frontend/src/pages/Customers.tsx frontend/src/types/index.ts
git commit -m "feat(rechnung): Entwurf aus dem Belege-Dialog prüfen und bearbeiten, Pfandzeilen gekennzeichnet"
```

---

## Abnahme

Fertig ist der Plan, wenn alle Punkte zutreffen. Punkte 1–13 prüft der Worker, M1–M5 der Manager.

1. `REDIS_URL=memory:// … pytest tests/test_gernot_261008.py -p no:cacheprovider` vollständig grün: 148 Tests (`TestS1` 39, `TestS2` 14, `TestS3` 15, `TestDatev` 22, `TestS6` 22, `TestS5` 36).
2. Prozedur V nach Task 29: `comm -13` ohne Ausgabe; `comm -23` nennt genau `test_services.py::TestInvoiceService::test_invoice_totals_update`.
3. Bestellung mit Pfandkiste, für die das Formular 7 % schickt, trägt 19 % (Produktsatz); ein bewusst auf 7 % gesetzter Pfandartikel bleibt bei 7 %; Freitext behält den Client-Satz; Kreditlimit rechnet mit dem Produktsatz (Task 1).
4. Rechnung aus Bestellung und Sammelrechnung übernehmen Produktsatz, `is_deposit`, `product_id` und Positionsrabatt; Leistungsdatum ist das tatsächliche Lieferdatum (Tasks 2, 3).
5. Produktstamm: PATCH und Import setzen beim Übergang zu Pfand 19 %, eine leere Importzelle überschreibt nichts, `"category": null` → 422; Shopify nimmt den Produktsatz (Tasks 4, 5).
6. Die einmalige Korrektur läuft je Mandant genau einmal (Marker `DATENKORREKTUR_STEUERSATZ_261008`), fasst keine Bestellung mit Rechnung an und blockiert bei einem Fehler keine Schemamigration (Task 6).
7. Rechnung 2,50 € zu 7 % + 4,50 € zu 19 %: `tax_amount` 1,04 = Σ Steuer je Satz; PDF mit Spalte „MwSt" und „USt 7 % auf 2.50 €" / „USt 19 % auf 4.50 €"; eine Altrechnung zeigt ihre festgeschriebenen Beträge; „Mailen" eines Entwurfs rechnet vorher neu, einer ausgestellten Rechnung nie; Sammelrechnungs-PDF ohne `NameError` (Tasks 8–11).
8. `POST /invoices` mit zwei Positionen summiert beide; Storno einer zweizeiligen Rechnung ergibt −17,84 € statt −10,70 €; die Stornorechnung spiegelt Satz, Konto (auch 8338), Pfandkennzeichen, Rabatt und Lieferdatum (Tasks 9, 12).
9. Original und Stornorechnung stehen auf `STORNIERT`, erscheinen weder als überfällig noch gemahnt noch offen noch als Umsatz; ein Entwurf bekommt keine Stornorechnung; Storno-Antwort enthält `warnungen`; Grund `FALSCHER_STEUERSATZ` (Tasks 13, 14).
10. DATEV: gemischte Rechnung → `26,75;S;EUR;;;10008;8300;;DDMM;<Nr>;;Rechnung 7 % …` und `7,14;S;…;8400;…`, keine Zeile auf 1400, jede Zeile 12 Felder; Summe der Zeilen = `total` auch an der Rundungsgrenze; Storno → S und H mit Saldo 0; nach Export nur Storno mit Stornorechnung; zweiter Export leer, mit `erneut_exportieren` identisch (Tasks 16–18).
11. Zweite Rechnung zu einer Bestellung → 409, nach Storno wieder erlaubt; Sammellauf rechnet jede Bestellung höchstens einmal, auch den Altbestand RE-00002/3/4, und überspringt Bestellungen auf `FAKTURIERT`; zweiter Lieferschein nur mit `?zusaetzlich=true`; `GET /invoices?order_id=` findet Rechnung aus Bestellung und Sammelrechnung (Tasks 20–24).
12. Entwurf: Löschen einer Position rechnet neu (25,00 / 1,75 / 26,75 €), ungültiges PATCH → 422 ohne Schreiben, Satzwechsel setzt 8400, Sonderkonto bleibt; `pfand_abrechnung = KEINE` → Rechnung aus Bestellung und Sammelrechnung ohne IFCO-Kiste, Lieferschein mit, Anlage 25,00 statt 31,00; `MONATLICH`/`null` → 422; Rechnungsliste neueste zuerst, `page_size` 100 (Tasks 25–28).
13. `cd frontend && npm run build` ohne TypeScript-Fehler; Nachladeprüfung aus Task 29 Step 6 liefert die beiden erwarteten Zeilen; `npx playwright test --list --reporter=list tests/e2e/full-suite.spec.ts` endet mit `Total: 14 tests in 1 file`.

**Manager-Abnahme (lokal, vor dem Deploy, kein Worker-Schritt).** Start wie in der Manager-Abnahme nach Task 24, Punkt 3: Backend auf `localhost:8000` mit `AUTH_DISABLED=true` (bei leerem `TENANTS_DIR` zusätzlich `DEFAULT_TENANTS=dev`), Frontend mit `VITE_AUTH_DISABLED=true npm run dev` (Port 3000).
- **M1 (Review Focus 1, Tasks 1/7):** Pfandartikel „IFCO-Kiste" (Kategorie Pfand, 19 %) und eine Microgreen-Sorte anlegen. Über „Neue Bestellung" beide bestellen: Bestelldetail zeigt die IFCO-Kiste mit 19 %, die Sorte mit 7 %, Brutto passend. Im Bearbeiten-Dialog eine weitere IFCO-Kiste nachtragen: ebenfalls 19 %.
- **M2 (Review Focus 2, Task 29):** Rechnungen → Entwurf mit Pfandzeile → „Bearbeiten": Die Positionen erscheinen (kurz „Positionen werden geladen …"), die Pfandzeile trägt das Badge „Pfand", „Entfernen" fragt nach, danach stimmt die Summe. Dasselbe im Belege-Dialog der Bestellung („Bearbeiten" klappt die Positionen auf).
- **M3 (Review Focus 3, Task 15):** Rechnung finalisieren, 5,00 € Zahlung erfassen, „Stornieren": Der Dialog warnt „Auf diese Rechnung wurde schon gezahlt", Grund „Falscher Steuersatz" ist wählbar; nach dem Storno erscheint die Warnung als Hinweis. Die Liste zeigt „Stornorechnung", beide Belege haben einen PDF-Knopf.
- **M4 (Review Focus 4, Tasks 23/24):** Manager-Abnahme nach Task 24, Punkte 1–3.
- **M5 (Review Focus 5, Task 29):** Kunde bearbeiten → „Pfandabrechnung" auf „Pfand nicht auf der Rechnung (IFCO-Clearing)" → speichern → erneut öffnen: Die Auswahl steht. Bestellung mit Ware und IFCO-Kiste → „Rechnung aus Bestellung": keine IFCO-Kiste auf der Rechnung; das Lieferschein-PDF zeigt sie.

---

## Runbook Produktion (kein Worker-Task)

**Wer:** Nikolaj bzw. der Manager mit Admin-Rolle. **Nie** der Codex-Worker (keine Netzwerkverbindung, keine Freigabe).
**Regeln für alle Teile:**
- Lesende Schritte sind ausdrücklich als lesend markiert (`sqlite3` mit `mode=ro` oder reine `GET`-Aufrufe).
- Jeder schreibende Schritt läuft nur mit Freigabe (Spec, Entscheidung 5: „Korrekturen an Produktionsdaten … weiterhin einzeln vorlegen").
- Rechnungen und Rechnungszeilen werden in keinem Schritt per SQL geändert.
- Bei jeder Abweichung von „Erwartet": **STOP**, nichts weiter ausführen, Befund melden.

Zugang: Host `49.12.191.103`, Key `sprouddesk_hetzner_ed25519` (Betriebsnotiz „NovaERP Prod-Topologie"). Der Container-Name wechselt je Deploy, deshalb vor jedem `docker exec` neu holen:

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84)
```

Mandanten-DB: `/data/tenants/minga.db`. Backups liegen **außerhalb** von `/data/tenants` und enden nicht auf `.db`, denn `registry.known_slugs()` lädt jede `*.db` in `/data/tenants` als Mandant (`tenancy.py:93-96`).

### Teil 1: Vor dem Deploy (lesend)

**K1: Kopfkonten** (Task 16 ignoriert `Invoice.buchungskonto` künftig).

```bash
docker exec -i "$C" python - <<'PY'
import sqlite3
con = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
print(con.execute("SELECT buchungskonto, count(*) FROM invoices GROUP BY 1").fetchall())
print(con.execute("SELECT invoice_number, buchungskonto, status, datev_exported FROM invoices "
                  "WHERE buchungskonto IS NOT NULL AND buchungskonto <> '8300'").fetchall())
PY
```

Erwartet: nur `8300` (alter Default) und `None`, zweite Liste leer. Jeder andere Wert ist ein bewusst gesetztes Kopfkonto, das der alte Export für alle Sätze der Rechnung verwendet hätte und Task 16 still ignoriert: Liste an Gernot bzw. den Steuerberater (Offener Punkt B5). An den Belegen wird **nichts** geändert.

Danach Deploy nach dem üblichen Ablauf (WAL-sicheres Backup, Deploy, Live-Prüfung; Spec, Entscheidung 5).

### Teil 2: Nach dem Deploy (lesend)

**L1: Ergebnis der einmaligen Steuersatz-Korrektur (Task 6)** — Liste für Gernot.

```bash
docker exec -i "$C" python - <<'PY'
import sqlite3
con = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
print(con.execute("SELECT value FROM app_settings WHERE key = 'DATENKORREKTUR_STEUERSATZ_261008'").fetchone())
PY
```

Erwartet: ein JSON mit `ausgefuehrt_am`, `geaendert` (korrigierte offene Bestellungen) und `uebersprungen_mit_rechnung` (mindestens die Bestellungen hinter RE-00002/3/4). Fehlt der Eintrag, ist die Korrektur gescheitert: Log `[auto-migrate] Steuersatz-Korrektur fehlgeschlagen` lesen, nicht von Hand nachholen. Die Liste `geaendert` geht an Gernot: Er entscheidet, ob bereits versendete Auftragsbestätigungen oder Lieferscheine mit Preisen neu an Kunden gehen; beide PDFs werden bei jedem Abruf aus der aktuellen Bestellung erzeugt (`documents.py:160-180`, `:328-346`) und zeigen nach der Korrektur 19 %.

**L2: Altrechnungen mit 1-ct-Abweichung (Task 8)** — Das Skript schreibt nichts; es läuft im Backend-Container (Arbeitsverzeichnis `/app`). In S2 gegen einen Test-Mandanten unter `TENANTS_DIR=/tmp/...` geprüft.

```bash
docker exec -i "$C" python - <<'PY'
import app.models  # noqa: F401 — alle Mapper laden
from sqlalchemy import select
from app.tenancy import registry
from app.models.invoice import Invoice, steuerausweis_stimmt
for slug in registry.known_slugs():
    with registry.get_sessionmaker(slug)() as db:
        alt = [
            f"{i.invoice_number} ({i.status.value})"
            for i in db.execute(select(Invoice).order_by(Invoice.invoice_number)).scalars()
            if not steuerausweis_stimmt(i)
        ]
        print(f"{slug}: {len(alt)} Altrechnung(en) mit 1-ct-Abweichung", alt)
PY
```

- **Entwürfe in der Liste** (z. B. RE-2026-00003) werden beim Ausstellen nach der neuen Regel neu berechnet („Finalisieren" oder „Mailen", Task 11) und ebenso, sobald eine Änderung am Entwurf gespeichert wird (Kopf per `PATCH /invoices/{id}`, Position anlegen, ändern oder löschen). Nur der reine PDF-Download rechnet nicht; einen solchen Entwurf erst ausstellen, dann das PDF weitergeben.
- **Versendete Rechnungen in der Liste:** an Gernot bzw. den Steuerberater (Offener Punkt B3).

**L3: Summe der DATEV-Zeilen = Rechnungsbetrag (Task 16)** — vor dem ersten Produktivexport. Für jede mit der Rechenregel aus Task 8 berechnete Rechnung gilt das per Konstruktion; abweichen können nur Altrechnungen mit alter Rundung (um 0,01 €). Der Prüfkern wurde in einer Kopie gegen Rechnung, Rechnung mit Sonderkonto und Rabatt, Storno und Entwurf geprüft (keine Abweichung).

```bash
docker exec -i "$C" python - <<'PY'
import app.models  # noqa: F401 — alle Mapper laden
from decimal import Decimal
from sqlalchemy import select
from app.tenancy import registry
from app.models.invoice import Invoice, InvoiceStatus
from app.services.datev_service import erloesgruppen
for slug in registry.known_slugs():
    with registry.get_sessionmaker(slug)() as db:
        abweichend = [
            f"{i.invoice_number} ({i.status.value}): Zeilen {sum((g['brutto'] for g in erloesgruppen(i)), Decimal('0'))} / total {i.total}"
            for i in db.execute(select(Invoice).where(Invoice.status != InvoiceStatus.ENTWURF)
                                .order_by(Invoice.invoice_number)).scalars()
            if sum((g["brutto"] for g in erloesgruppen(i)), Decimal("0")) != i.total
        ]
        print(f"{slug}: {len(abweichend)} Abweichung(en)", abweichend)
PY
```

Die Liste geht an den Steuerberater (Offener Punkt B3). An den Belegen wird **nichts** geändert. Der DATEV-Export bleibt gesperrt, bis der Steuerberater die Kontierung bestätigt hat (Sofortmaßnahme 1).

**L4: Belege-Dialog im Mandanten `minga`** — eine Bestellung mit Entwurf öffnen, „Bearbeiten" klappt die Positionen auf. Keine Testposition in Produktion anlegen; das ist Teil der lokalen Manager-Abnahme (M2). `pfand_abrechnung` erst setzen, wenn Gernot Offenen Punkt G3 beantwortet hat.

### Teil 3: Korrektur RE-2026-00002, -00003, -00004 und Prüfung Doppelabrechnung

**Wann:** nach dem Deploy des gesamten Pakets 1, nur mit Freigabe.

**Wer:** Nikolaj mit Admin-Rolle. Freigaben siehe R0.

**Regeln:**
- Kein direkter Datenbankzugriff.
- Kein `PATCH status`. `InvoiceUpdate` erlaubt das bei Entwürfen, es wird hier nie benutzt.
- Versendete Rechnungen werden nicht verändert. Das PDF entsteht bei jedem Abruf neu aus der DB (`invoices.py` ~466-494); eine Änderung schriebe das versendete Dokument rückwirkend um.
- Bei jeder Abweichung von „Erwartet“: **STOP**, nichts weiter ausführen, Befund melden.

**R0: Freigaben und Vorbedingungen (Checkliste)**
- [ ] Paket 1 ist live. Nachweis ohne Login:
  ```bash
  curl -s https://minga.novaerp.de/openapi.json | grep -o -e FALSCHER_STEUERSATZ -e erneut_exportieren -e pfand_abrechnung | sort -u
  curl -s https://minga.novaerp.de/openapi.json | python3 -c "import json,sys; d=json.load(sys.stdin); print([p['name'] for p in d['paths']['/api/v1/invoices']['get']['parameters']])"
  ```
  Erwartet: die drei Namen `FALSCHER_STEUERSATZ`, `erneut_exportieren`, `pfand_abrechnung`, und die Parameterliste von `GET /api/v1/invoices` enthält `order_id`. Fehlt etwas, ist der Deploy nicht live: abbrechen.
- [ ] Teil 2 (L1–L3) ist gelaufen und ohne Befund bzw. mit Gernot besprochen.
- [ ] Gernot hat schriftlich freigegeben:
  - die Korrektur selbst,
  - das echte Lieferdatum je Rechnung (07. oder 08.10.2026),
  - den Namen des Empfängers für nachträgliches Quittieren,
  - den Versandweg.
- [ ] Pfand IFCO-Kiste zu 19 % ist bestätigt (Spec, offene Entscheidung 4). Ohne diese Bestätigung entfällt R7, RE-00004 bleibt dann unangetastet.
- [ ] Die Variante für RE-00003 ist entschieden: A (empfohlen) oder B, siehe R6 (Offener Punkt B12).
- [ ] Gernot hat beantwortet, ob Ökoring Pfand über das IFCO-Clearing abrechnet (Offene Punkte G3, GB3). Nur dann gilt R6 wie beschrieben (Neuausstellung ohne Pfand). Sonst STOP und R6 mit Nikolaj neu festlegen.
- [ ] Unmittelbar vor R2 wurde ein WAL-sicheres Backup des Mandanten gezogen.
  - Auf dem Hetzner-Host zuerst den Container-Namen neu ermitteln, er wechselt bei jedem Deploy: `docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84`
  - Dann: `docker exec -i "$C" python -c "import sqlite3, pathlib; z=pathlib.Path('/data/tenants-backup'); z.mkdir(exist_ok=True); s=sqlite3.connect('/data/tenants/minga.db'); d=sqlite3.connect(str(z/'minga-vor-s3-korrektur-261008.sqlite')); s.backup(d); d.close(); s.close()"`
  - Das Ziel liegt **außerhalb** von `/data/tenants` und endet nicht auf `.db`. `registry.known_slugs()` lädt jede `*.db` in `/data/tenants` als Mandant (`tenancy.py:93-96`); so verfährt auch R11.
- [ ] Seit der Sofortmaßnahme gab es keinen DATEV-Export. Er bleibt gesperrt, bis der Steuerberater die Kontierung aus S4 bestätigt hat (Offener Punkt B5).

**R1: Arbeitsumgebung (lokal, außerhalb des Repos)**
```bash
K=~/minga-korrektur-261008; mkdir -p "$K"
B=https://minga.novaerp.de/api/v1
read -rs TOKEN   # Access-Token einfügen, nichts wird angezeigt (siehe unten)
api() { curl -sS --fail-with-body -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }
api "$B/invoices?page_size=1" >/dev/null && echo "Zugriff ok"
```
- So kommt man an den Token: In einer angemeldeten Admin-Sitzung die Browser-Entwicklerwerkzeuge öffnen, unter „Netzwerk“ eine beliebige `/api/v1`-Anfrage wählen und aus dem Header `Authorization` den Teil nach `Bearer ` kopieren.
- Der Token wird nie ausgegeben und nie in eine Datei geschrieben.
- Er läuft nach wenigen Minuten ab. Bei `401` den Token neu kopieren und `read -rs TOKEN` wiederholen.
- `$K` enthält Kundendaten und gehört nicht ins Repo.

**R2: Bestandsaufnahme (nur lesend)**
```bash
api "$B/invoices?page_size=100" > "$K/liste-vorher.json"
for NR in RE-2026-00002 RE-2026-00003 RE-2026-00004; do
  ID=$(jq -r --arg n "$NR" '.[] | select(.invoice_number==$n) | .id' "$K/liste-vorher.json")
  api "$B/invoices/$ID" > "$K/$NR-vorher.json"
  jq '{nr: .invoice_number, status, invoice_date, delivery_date, due_date, subtotal, tax_amount, total,
       total_deposit, paid_amount, zahlungen: (.payments|length), order_id, customer_id,
       lexoffice_id, lexoffice_synced_at, datev_exported, sent_at, internal_notes}' "$K/$NR-vorher.json"
done
api "$B/products?page_size=500" | jq '[.[] | select(.is_deposit) | {id, sku, name, tax_rate}]' > "$K/pfandartikel.json"
cat "$K/pfandartikel.json"
for NR in RE-2026-00002 RE-2026-00003 RE-2026-00004; do
  jq --slurpfile p "$K/pfandartikel.json" --arg nr "$NR" \
    '{nr: $nr, pfand: [.lines[] | select(.product_id as $x | [$p[0][].id] | index($x))
                       | {id, description, quantity, unit_price, tax_rate, buchungskonto, is_deposit, line_total}]}' "$K/$NR-vorher.json"
done
for NR in RE-2026-00002 RE-2026-00003; do
  jq -c '[.lines[] | {description, quantity, unit_price, tax_rate}]' "$K/$NR-vorher.json"
done
api "$B/invoices?invoice_type=GUTSCHRIFT&page_size=100" | jq 'length'
api "$B/integrations/lexoffice"
```

Erwartet:
- **RE-00002 und RE-00004:**
  - `status` ist `OFFEN` oder `UEBERFAELLIG`
  - `paid_amount` ist `0.00`, `zahlungen` ist 0
  - `datev_exported` ist `false`
- **RE-00003:** `status` ist `ENTWURF`. Die beiden `jq -c`-Zeilen (Positionen von 00002 und 00003) sind identisch.
- **Pfand:** Je Rechnung gibt es genau eine Pfandzeile mit `tax_rate` `REDUZIERT`. Ihr `line_total` (netto) ist bei RE-00002 und RE-00003 gleich. Die gemessenen Werte als `PFAND2` (RE-00002) und `PFAND4` (RE-00004) notieren, R6 und R7 rechnen damit. Einen Sollwert gibt es nicht: Die Spec nennt keine Pfandbeträge, maßgeblich sind die Daten. Findet der Filter keine Zeile (Position ohne `product_id`), die Pfandzeile über `description` bestimmen und mit Gernot bestätigen.
- **Pfandartikel im Stamm:** `tax_rate` ist `STANDARD`.
- **Gutschriften:** Die Zählung ergibt `0`. Bisher gibt es keine Stornorechnungen, also auch keinen Altbestand mit `OFFEN`.
- **lexoffice:** Steht bei 00002 oder 00004 eine `lexoffice_id`, nach R4 den Schritt R5 ausführen. Sonst entfällt R5.

Sonderfälle:
- **Zahlung vorhanden** (`paid_amount > 0`): STOP. Gernot und der Steuerberater entscheiden, ob umgebucht oder erstattet wird (Offener Punkt B13). Erst dann weiter. Der Storno meldet dann eine Warnung, und in R6/R7 kommt nach dem Finalisieren dieser Schritt hinzu:
  ```bash
  api -X POST "$B/invoices/<NEU_ID>/payments" -d '{"invoice_id":"<NEU_ID>","payment_date":"<Datum der Zahlung>","amount":"<Betrag>","reference":"Umbuchung von RE-2026-0000X"}'
  ```
- **Beleg für die Akte:** Das PDF der Originale erzeugt das System nach dem S2-Deploy im neuen Layout. Für die Akte gilt das **versendete** PDF aus Gernots Postausgang.

**R2b: Prüfabfrage Doppelabrechnung P1–P6 (nur lesend)**

Die Abfragen und das Nachtragsskript sind gegen eine lokal erzeugte SQLite-Datei mit dem Produktionsschema und dem Muster vor S6 geprüft (Python 3.11 wie im Container, `python:3.11-slim`). P4b und die Ergänzung von P5 sind zusätzlich am 08.10.2026 per TestClient auf `c4a1832` nachgestellt: Bestellung über 25,00 € netto mit zwei Lieferscheinen, dann Sammellauf → Sammelrechnung mit `subtotal` 50,00; P4a leer, P4b ein Treffer. Bestellung `FAKTURIERT`, ein Lieferschein in einer Sammelrechnung, ein zweiter frei → alte P5 meldete sie, die neue nicht; `FAKTURIERT` ohne jede Rechnung mit freiem Lieferschein → beide melden sie. Das vollständige Prüfskript aus R2b lief gegen einen Abzug dieses Nachbaus in eine SQLite-Datei: P4a, P4b und P5 je genau der erwartete Treffer, P2 und P6 leer.

Auf dem Host:

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84)
docker exec -i "$C" python - /data/tenants/minga.db <<'PY'
import sqlite3, sys
db = sys.argv[1]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def zeige(titel, sql):
    rows = con.execute(sql).fetchall()
    print(f"\n## {titel} ({len(rows)} Zeilen)")
    if rows:
        print(" | ".join(rows[0].keys()))
        for r in rows:
            print(" | ".join("" if v is None else str(v) for v in r))

zeige("P1 Rechnungen RE-2026-00001..00005", """
SELECT i.invoice_number, i.invoice_type, i.status, i.total, i.sent_at,
       o.order_number, o.status AS bestellstatus,
       (SELECT COUNT(*) FROM delivery_notes d WHERE d.invoice_id = i.id) AS ls_an_rechnung,
       (SELECT COUNT(*) FROM delivery_notes d WHERE d.order_id = i.order_id) AS ls_der_bestellung,
       (SELECT COUNT(*) FROM delivery_notes d WHERE d.order_id = i.order_id AND d.invoice_id IS NULL) AS ls_ohne_rechnung,
       (SELECT COUNT(*) FROM invoice_line_sources s JOIN invoice_lines l ON l.id = s.invoice_line_id
         WHERE l.invoice_id = i.id) AS herkunftszeilen
FROM invoices i LEFT JOIN orders o ON o.id = i.order_id
WHERE i.invoice_number BETWEEN 'RE-2026-00001' AND 'RE-2026-00005'
ORDER BY i.invoice_number
""")

zeige("P2 Rechnungen aus Bestellung, an denen kein Lieferschein haengt (vor S6: Doppelabrechnung im naechsten Sammellauf)", """
SELECT i.invoice_number, i.status AS rechnungsstatus, o.order_number, o.status AS bestellstatus,
       GROUP_CONCAT(d.delivery_note_number || ' (' || d.status || ')', ', ') AS lieferscheine_ohne_rechnung
FROM invoices i
JOIN orders o ON o.id = i.order_id
JOIN delivery_notes d ON d.order_id = i.order_id AND d.invoice_id IS NULL
WHERE i.invoice_type = 'RECHNUNG' AND i.status != 'STORNIERT'
  AND NOT EXISTS (SELECT 1 FROM delivery_notes d2
                   WHERE d2.order_id = i.order_id AND d2.invoice_id IS NOT NULL)
GROUP BY i.id
ORDER BY i.invoice_number
""")

zeige("P3 Bestellungen mit mehr als einem Lieferschein", """
SELECT o.order_number, o.status AS bestellstatus, COUNT(*) AS anzahl_ls,
       GROUP_CONCAT(d.delivery_note_number || ' ' || d.status || ' ' || IFNULL(d.invoice_id, '-'), ', ') AS lieferscheine
FROM delivery_notes d JOIN orders o ON o.id = d.order_id
GROUP BY d.order_id HAVING COUNT(*) > 1
ORDER BY o.order_number
""")

zeige("P4a Bestellungen in mehr als einer nicht stornierten Rechnung (schon jetzt mehrfach berechnet)", """
SELECT o.order_number, GROUP_CONCAT(x.invoice_number, ', ') AS rechnungen, COUNT(DISTINCT x.id) AS anzahl
FROM (
  SELECT i.id, i.invoice_number, i.order_id AS order_id FROM invoices i
   WHERE i.order_id IS NOT NULL AND i.invoice_type = 'RECHNUNG' AND i.status != 'STORNIERT'
  UNION
  SELECT i.id, i.invoice_number, d.order_id FROM delivery_notes d JOIN invoices i ON i.id = d.invoice_id
   WHERE i.invoice_type = 'RECHNUNG' AND i.status != 'STORNIERT'
) x JOIN orders o ON o.id = x.order_id
GROUP BY x.order_id HAVING COUNT(DISTINCT x.id) > 1
ORDER BY o.order_number
""")

zeige("P4b Bestellungen, die innerhalb EINER Rechnung mehrfach berechnet sind (mehrere ihrer Lieferscheine an derselben Rechnung)", """
SELECT o.order_number, i.invoice_number, i.status AS rechnungsstatus, COUNT(*) AS anzahl_ls,
       GROUP_CONCAT(d.delivery_note_number, ', ') AS lieferscheine
FROM delivery_notes d
JOIN invoices i ON i.id = d.invoice_id
JOIN orders o ON o.id = d.order_id
WHERE i.invoice_type = 'RECHNUNG' AND i.status != 'STORNIERT'
GROUP BY d.order_id, d.invoice_id HAVING COUNT(*) > 1
ORDER BY i.invoice_number, o.order_number
""")

zeige("P5 FAKTURIERT ohne Rechnung, aber mit offenem Lieferschein (seit Task 22 nicht mehr im Sammellauf)", """
SELECT o.order_number, GROUP_CONCAT(d.delivery_note_number, ', ') AS lieferscheine
FROM orders o JOIN delivery_notes d ON d.order_id = o.id
WHERE o.status = 'FAKTURIERT' AND d.invoice_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM invoices i WHERE i.order_id = o.id
                   AND i.invoice_type = 'RECHNUNG' AND i.status != 'STORNIERT')
  AND NOT EXISTS (SELECT 1 FROM delivery_notes d3 JOIN invoices i3 ON i3.id = d3.invoice_id
                   WHERE d3.order_id = o.id
                     AND i3.invoice_type = 'RECHNUNG' AND i3.status != 'STORNIERT')
GROUP BY o.id ORDER BY o.order_number
""")

zeige("P6 Lieferscheine an stornierten Rechnungen (sollte es seit R1.6 nicht geben)", """
SELECT d.delivery_note_number, i.invoice_number
FROM delivery_notes d JOIN invoices i ON i.id = d.invoice_id
WHERE i.status = 'STORNIERT'
""")
PY
```

Die Verbindung ist `mode=ro` — die Abfrage kann nichts schreiben. Ausgabe vollständig sichern (Akte zum Paket).

Auswertung:

| Abfrage | Was sie zeigt | Erwartung / Handlung |
|---|---|---|
| P1 | RE-2026-00001..00005: Typ, Status, Betrag, Bestellung, Lieferscheine an der Rechnung bzw. der Bestellung, Herkunftszeilen (`invoice_line_sources`) | Einordnen: `order_number` leer + Herkunftszeilen > 0 = Sammelrechnung; `order_number` gesetzt = Rechnung aus Bestellung. Laut Lückenprüfung sind RE-00002/3/4 aus Bestellung mit `ls_ohne_rechnung` ≥ 1. RE-00001/00005 hier zum ersten Mal belegen. Ist RE-00001 oder RE-00005 eine Sammelrechnung mit Lieferschein, war ihr PDF bis Task 21 nicht abrufbar (`NameError`) — Versand prüfen (Offener Punkt G13). |
| P2 | Rechnungen aus Bestellung, an denen kein Lieferschein hängt | Vor S6 die Kandidaten für Doppelabrechnung; mit S6 überspringt der Sammellauf sie über `Invoice.order_id`. Erwartet: RE-00002/3/4 (sofern noch nicht über R4 storniert). Kein Handlungszwang — Bereinigung optional in R11. |
| P3 | Bestellungen mit mehr als einem Lieferschein | Künftige Läufe berechnen sie mit S6 je einmal (Task 22). Eine **schon geschehene** Doppelabrechnung ist damit nicht erledigt: Stehen zwei ihrer Lieferscheine mit derselben `invoice_id` da, ist sie in dieser Rechnung doppelt berechnet (→ P4b); hängen sie an verschiedenen Rechnungen → P4a. Gegenprobe: Jede P3-Bestellung mit mehr als einem Lieferschein mit `invoice_id` muss in P4a oder P4b stehen. |
| P4a | Bestellungen in mehr als einer nicht stornierten Rechnung (Rechnung aus Bestellung und/oder Sammelrechnung) | **Muss leer sein.** Sonst ist bereits doppelt berechnet: Gernot informieren, die überzählige Rechnung per Storno (Verfahren R4–R8) korrigieren — **nie** per SQL. |
| P4b | Bestellungen, von denen mehrere Lieferscheine an **derselben** nicht stornierten Rechnung hängen | **Muss leer sein.** P4a sieht diesen Fall nicht (nur eine Rechnung), berechnet ist trotzdem doppelt: `_aggregiere` addiert `order.lines` je Lieferschein (`invoices.py:564-569`), nachgestellt 25,00 € netto als 50,00 € berechnet. Jeder Treffer: Gernot informieren, die Rechnung per Storno korrigieren (Verfahren R4–R8, **nie** per SQL). Das Storno löst alle Lieferscheine dieser Rechnung (R1.6), auch die der anderen Bestellungen derselben Sammelrechnung; der nächste Sammellauf über ihren Leistungszeitraum (steht im Kopftext „Sammelrechnung — Leistungszeitraum …“, `invoices.py:604-611`) rechnet dann jede dieser Bestellungen nach Task 22 genau einmal. Nur nach R0 (S6 live) — vorher verdoppelte der neue Lauf wieder. |
| P5 | Bestellungen `FAKTURIERT` ohne Rechnung im System — weder über `Invoice.order_id` noch über einen Lieferschein in einer nicht stornierten Rechnung —, mit offenem Lieferschein | Seit Task 22 überspringt der Sammellauf `FAKTURIERT`-Bestellungen (Spec-Nachtrag). P5 zeigt, welche Bestellungen deshalb **nicht** mehr über den Sammellauf berechnet werden. Liste an Gernot (Offener Punkt G10): Wurden sie außerhalb von NovaERP berechnet? Was nicht berechnet wurde, wird nach seiner Antwort einzeln über „Rechnung aus Bestellung" abgerechnet. |
| P6 | Lieferscheine an stornierten Rechnungen | Muss leer sein (R1.6 löst sie). Sonst melden, nicht ändern. |

**R3: Lieferscheine und echtes Lieferdatum**
```bash
for NR in RE-2026-00002 RE-2026-00004; do
  OID=$(jq -r .order_id "$K/$NR-vorher.json"); echo "== $NR / Bestellung $OID"
  api "$B/sales/orders/$OID" | jq '{order_number, status, requested_delivery_date, actual_delivery_date}'
  api "$B/sales/orders/$OID/delivery-notes" | jq '[.[] | {id, delivery_note_number, status, signed_by, actual_delivery_date}]'
done
```
- **Lieferschein mit `status` ≠ `GELIEFERT`:** nur per API quittieren, mit ausdrücklichem Datum.
  ```bash
  api -X PATCH "$B/sales/delivery-notes/<LS_ID>/mark-delivered" \
    -d '{"signed_by": "<Name laut Gernot>", "actual_delivery_date": "<2026-10-07 oder 2026-10-08 laut Gernot>"}' \
    | jq '{delivery_note_number, status, actual_delivery_date}'
  ```
  - **Nicht** über den Knopf „Quittieren“ in der Oberfläche. Der schickt nur `signed_by`, und das Datum würde heute (`documents.py:294`, `OrderDocumentsModal.tsx:125`).
  - Achtung: Steht die Bestellung noch auf `ENTWURF`, `BESTAETIGT` oder `IN_PRODUKTION`, setzt das Quittieren sie auf `GELIEFERT` und bucht den Lagerbestand ab (`documents.py:298-321`). Das ist die echte Lieferung. Gernot bestätigt vorher, dass der Bestand nicht schon anders abgebucht wurde.
- **Lieferschein schon `GELIEFERT` mit falschem Datum:** Das lässt sich nicht ändern, der Lieferschein ist gesperrt (`documents.py:288-289`). Maßgeblich für die Rechnung ist das `delivery_date`, das R6/R7 ausdrücklich setzen. Die Abweichung kommt in `internal_notes`.
- **Kein Lieferschein:** nichts tun.

**R4: Stornieren (RE-00002 und RE-00004)**

Alternativ geht das in der Oberfläche über „Stornieren“ mit denselben Gründen.

```bash
ID2=$(jq -r .id "$K/RE-2026-00002-vorher.json"); ID4=$(jq -r .id "$K/RE-2026-00004-vorher.json")
api -X POST "$B/invoices/$ID2/cancel" -d '{"reason_code": "SONSTIGES",
  "reason": "Pfand (IFCO) wird über das IFCO-Clearing abgerechnet und gehört nicht auf die Rechnung; zudem mit 7 % statt 19 % ausgewiesen. Neuausstellung ohne Pfand."}' \
  > "$K/RE-2026-00002-storno.json"
api -X POST "$B/invoices/$ID4/cancel" -d '{"reason_code": "FALSCHER_STEUERSATZ",
  "reason": "Pfand mit 7 % statt 19 % berechnet. Neuausstellung mit 19 % auf das Pfand."}' \
  > "$K/RE-2026-00004-storno.json"
for NR in RE-2026-00002 RE-2026-00004; do
  jq -n --slurpfile a "$K/$NR-vorher.json" --slurpfile s "$K/$NR-storno.json" '
    $a[0] as $o | $s[0] as $r |
    {original: $r.invoice.status, storno_nr: $r.credit_note.invoice_number, storno_status: $r.credit_note.status,
     summe_null: ((($o.total|tonumber) + ($r.credit_note.total|tonumber)) == 0
              and (($o.subtotal|tonumber) + ($r.credit_note.subtotal|tonumber)) == 0
              and (($o.tax_amount|tonumber) + ($r.credit_note.tax_amount|tonumber)) == 0),
     warnungen: $r.warnungen}'
  SID=$(jq -r .credit_note.id "$K/$NR-storno.json"); api "$B/invoices/$SID" > "$K/$NR-stornobeleg.json"
  # "* 1" bzw. "0 -" normalisiert die Zahl ("10.000" → 10), sonst meldet diff Scheinunterschiede
  diff <(jq -c '[.lines[] | {position, description, q: ((.quantity|tonumber) * 1), unit_price, tax_rate, buchungskonto}]' "$K/$NR-vorher.json") \
       <(jq -c '[.lines[] | {position, description, q: (0 - (.quantity|tonumber)), unit_price, tax_rate, buchungskonto}]' "$K/$NR-stornobeleg.json") \
    && echo "$NR: Positionen gespiegelt"
done
```
Erwartet je Rechnung:
- `original` und `storno_status` sind `STORNIERT`
- `summe_null` ist `true`
- `warnungen` ist `[]`, oder enthält nur den lexoffice-Hinweis, wenn R2 eine `lexoffice_id` zeigte
- Die Ausgabe enthält „Positionen gespiegelt“. Die Pfandzeile der Stornorechnung trägt also **7 %**, wie das Original.

Die Stornonummern (`storno_nr`) notieren.

**R4b: Bestellpositionen berichtigen (Task 6)**

Die Reihenfolge schreibt S1 vor: erst stornieren, dann die Positionen berichtigen, dann neu ausstellen. Die Rechnung aus der Bestellung nimmt den Produktsatz zwar auch ohne diesen Schritt (Task 2). Die Bestellung selbst (Summen, Auftragsbestätigung) stünde aber weiter auf 7 %.

Die Korrektur ändert nur Bestellungen ohne aktive Rechnung, auch ohne Entwurf.
- Bei **RE-00004** (Großer Kern) greift sie jetzt.
- Bei **Ökoring** greift sie nur in Variante B, nachdem RE-00003 verworfen ist (siehe R6).

Auf dem Host:
```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84)
docker exec -i "$C" python - <<'PY'
import app.models  # noqa: F401 — alle Mapper laden
from uuid import UUID
from app.tenancy import registry
from app.services.steuersatz_korrektur import korrigiere_offene_bestellpositionen
Session = registry.get_sessionmaker("minga")
with Session() as db:
    print(korrigiere_offene_bestellpositionen(db, nur_bestellungen=[UUID("<order_id von RE-00004 aus R2>")]))
    db.commit()
PY
```
Erwartet: `uebersprungen_mit_rechnung` **und** `uebersprungen_status` sind leer, `geaendert` enthält die Bestellnummer (sie trug noch Positionen mit abweichendem Satz). Steht die Bestellung unter `uebersprungen_mit_rechnung`, hängt noch eine aktive Rechnung an ihr; steht sie unter `uebersprungen_status`, ist sie nicht mehr offen (z. B. `FAKTURIERT`) oder die ID ist falsch: in beiden Fällen STOP. Sind beide Listen und `geaendert` leer, trug die Bestellung keine abweichende Position mehr: weiter.

Die Funktion committet nicht selbst, deshalb steht `db.commit()` im Skript. Der Container läuft mit `WORKDIR /app` (`backend/Dockerfile:3`), `app` ist also importierbar.

**R5: lexoffice** (nur wenn R2 bei 00002/00004 eine `lexoffice_id` zeigte)
- Die ERP-Übertragung legt Belege in lexoffice als Entwurf an (`finalize=False`, `lexoffice_service.py:143`). Gernot löscht dort den Entwurf. Hat er ihn in lexoffice inzwischen finalisiert, storniert er ihn dort.
- Die Stornorechnung **nicht** nach lexoffice übertragen. Sie käme dort als normale Rechnung mit negativen Mengen an (`lexoffice_service.py:35-60`, `99-114`).
- Für die Originale **nicht** `POST /integrations/lexoffice/invoices/{id}/pull-status` aufrufen. Die Funktion kennt nur `paid` und würde ein storniertes Original auf `BEZAHLT` setzen (`lexoffice_service.py:151-166`). Ein `voided` holt sie nicht zurück. Die Oberfläche blendet den Knopf bei `STORNIERT` aus.

**R6: Neuausstellung Ökoring**

Zuerst stellt man nach Gernots Bestätigung (R0) bei Ökoring das Kundenfeld `pfand_abrechnung` (Task 26) auf `KEINE`. Es gilt nur für **neu erzeugte** Rechnungen: Variante A berührt es nicht, für Variante B und alle künftigen Rechnungen lässt es das Pfand weg.
```bash
KD=$(jq -r .customer_id "$K/RE-2026-00002-vorher.json")
api -X PATCH "$B/sales/customers/$KD" -d '{"pfand_abrechnung": "KEINE"}' | jq '{name, pfand_abrechnung}'
```
Erwartet: `pfand_abrechnung: "KEINE"`.

**Variante A (empfohlen): RE-00003 wird die korrigierte Rechnung.** So entsteht keine neue Nummer und keine Lücke.
```bash
ID3=$(jq -r .id "$K/RE-2026-00003-vorher.json")
P3=<id der Pfandzeile von RE-00003 aus R2>
api -X DELETE "$B/invoices/$ID3/lines/$P3" -o /dev/null -w '%{http_code}\n'          # 204
api "$B/invoices/$ID3" > "$K/RE-2026-00003-ohne-pfand.json"
jq -n --slurpfile a "$K/RE-2026-00002-vorher.json" --slurpfile n "$K/RE-2026-00003-ohne-pfand.json" '
  {status: $n[0].status, pfand_brutto: $n[0].total_deposit,
   netto_differenz: ((($a[0].subtotal|tonumber) - ($n[0].subtotal|tonumber)) * 100 | round / 100),
   summe_der_zeilen_passt: ((([$n[0].lines[].line_total|tonumber] | add) * 100 | round)
                            == ((($n[0].subtotal|tonumber) + ($n[0].discount_amount|tonumber)) * 100 | round))}'
```
Erwartet:
- `status` ist `ENTWURF`
- `pfand_brutto` ist `0`
- `netto_differenz` ist gleich `PFAND2` aus R2
- `summe_der_zeilen_passt` ist `true` (das hängt von Task 25 ab)

```bash
KD=$(jq -r .customer_id "$K/RE-2026-00003-vorher.json")
PD=$(api "$B/sales/customers/$KD" | jq -r .payment_days)
HEUTE=$(date +%F); FAELLIG=$(date -v+${PD}d +%F)
LIEFER=<echtes Lieferdatum Ökoring laut R0, JJJJ-MM-TT>
S2NR=$(jq -r .credit_note.invoice_number "$K/RE-2026-00002-storno.json")
NOTIZ=$(jq -r '.internal_notes // ""' "$K/RE-2026-00003-vorher.json")
api -X PATCH "$B/invoices/$ID3" -d "$(jq -n --arg d "$HEUTE" --arg f "$FAELLIG" --arg l "$LIEFER" --arg n "$NOTIZ" --arg s "$S2NR" \
  '{invoice_date: $d, due_date: $f, delivery_date: $l,
    internal_notes: ($n + (if $n == "" then "" else "\n\n" end)
      + "Neuausstellung zu RE-2026-00002 (storniert mit " + $s + "). Ohne Pfand: Ökoring rechnet Pfand über das IFCO-Clearing ab.")}')" \
  | jq '{invoice_number, status, invoice_date, delivery_date, due_date, subtotal, tax_amount, total}'
api -X POST "$B/invoices/$ID3/finalize" | jq '{invoice_number, status, total}'
```
Erwartet:
- Rechnungsdatum heute, Lieferdatum wie mit Gernot vereinbart.
- Nach dem Finalisieren steht `status` auf `OFFEN` und `invoice_number` auf `RE-2026-00003`.
- `subtotal` = `subtotal` von RE-00002 minus `PFAND2`. `tax_amount` = `tax_amount` von RE-00002 minus `PFAND2` × 7 %, ±0,01 Rundung.

**Variante B: RE-00003 verwerfen, dann neu aus der Bestellung.**
```bash
api -X POST "$B/invoices/$ID3/cancel" -d '{"reason_code":"SONSTIGES","create_credit_note":false,
  "reason":"Entwurf doppelt angelegt (inhaltsgleich mit RE-2026-00002), nie versendet — verworfen ohne Stornorechnung."}' \
  | jq '{status: .invoice.status, credit_note, warnungen}'
```
- Erwartet: `STORNIERT` und `credit_note: null`. Die Nummer bleibt belegt und dokumentiert. Task 17 exportiert einen so verworfenen Beleg nicht, weil es keinen Gegenbeleg gibt.
- Danach R4b mit der `order_id` von RE-00002 ausführen, also für die Ökoring-Bestellung. Erst jetzt hat sie keine aktive Rechnung mehr.
- Dann `api -X POST "$B/invoices/from-order/<order_id von RE-00002>"` aufrufen. Solange RE-00003 nicht verworfen ist, antwortet S6 mit 409.
- Erwartet: **keine** Pfandzeile, wegen `pfand_abrechnung = KEINE` (Task 27). Steht trotzdem eine da, im Entwurf löschen wie in Variante A.
- Datum, Fälligkeit, Lieferdatum und Notiz setzen und finalisieren wie in Variante A. Die neue Rechnung bekommt die nächste freie Nummer.

**Variante C (Entwurf löschen):** Es gibt keinen Endpunkt dafür. Löschen ginge nur per DB und hinterlässt eine Lücke im Nummernkreis. **Nicht vorgesehen.**

**R7: Neuausstellung Großer Kern mit 19 % auf das Pfand** (nur bei bestätigtem Offenem Punkt GB1, nach R4b)

S6 lässt „Rechnung aus Bestellung“ zu, weil RE-00004 storniert ist, und hängt den Lieferschein an (Task 21). Ein zweiter Aufruf liefert 409. Deshalb nur **einmal** aufrufen. Gibt es Zweifel am Ergebnis, die Rechnung über `GET $B/invoices?order_id=$OID4` wiederfinden, statt erneut aufzurufen.
```bash
OID4=$(jq -r .order_id "$K/RE-2026-00004-vorher.json")
api -X POST "$B/invoices/from-order/$OID4" > "$K/neu-grosser-kern.json"
NID=$(jq -r .id "$K/neu-grosser-kern.json"); api "$B/invoices/$NID" > "$K/neu-grosser-kern-entwurf.json"
jq --slurpfile p "$K/pfandartikel.json" '[.lines[] | select(.product_id as $x | [$p[0][].id] | index($x))
  | {id, description, quantity, unit_price, line_total, tax_rate, buchungskonto}]' "$K/neu-grosser-kern-entwurf.json"
for F in RE-2026-00004-vorher neu-grosser-kern-entwurf; do
  jq -c '[.lines[] | {description, quantity, unit_price}]' "$K/$F.json"
done
jq -n --slurpfile a "$K/RE-2026-00004-vorher.json" --slurpfile n "$K/neu-grosser-kern-entwurf.json" '
  {netto_gleich: (($a[0].subtotal|tonumber) == ($n[0].subtotal|tonumber)),
   mehr_ust: ((($n[0].tax_amount|tonumber) - ($a[0].tax_amount|tonumber)) * 100 | round / 100),
   mehr_brutto: ((($n[0].total|tonumber) - ($a[0].total|tonumber)) * 100 | round / 100)}'
```
Erwartet:
- Genau eine Pfandzeile mit `line_total` gleich `PFAND4` aus R2, `tax_rate` `STANDARD` und `buchungskonto` `8400`.
- Die beiden `jq -c`-Zeilen sind identisch.
- `netto_gleich` ist `true`. `mehr_ust` und `mehr_brutto` sind je `PFAND4` × 12 %, ±0,01 Rundung.

Steht die Pfandzeile auf `REDUZIERT`, wirkt S1 nicht. Dann **nicht finalisieren** und das melden. Den Entwurf erst nach Klärung bearbeiten: im Entwurf die Pfandzeile löschen und neu anlegen. `add_line` setzt dabei bei `STANDARD` das Konto 8400 und übernimmt das Pfandkennzeichen vom Produkt.
```bash
api -X DELETE "$B/invoices/$NID/lines/<Pfandzeile>" -o /dev/null -w '%{http_code}\n'
api -X POST "$B/invoices/$NID/lines" -d '{"description":"<wie Original>","quantity":<Menge>,"unit":"<Einheit wie Original>","unit_price":<Preis>,"tax_rate":"STANDARD","product_id":"<Pfandartikel-ID>"}'
```
Ein `PATCH …/lines/{id}` mit `tax_rate` zieht das Konto erst ab Task 25 mit („Erlöskonto folgt dem Satz“). Im Zweifel löschen und neu anlegen.

Danach Datum, Fälligkeit, Lieferdatum und Notiz setzen wie in R6. Die Notiz lautet `"Neuausstellung zu RE-2026-00004 (storniert mit <Stornonummer>). Pfand mit 19 %."`. Das Lieferdatum (`delivery_date`) ist `<echtes Lieferdatum Großer Kern laut R0>`. Nach Task 2 setzt „Rechnung aus Bestellung“ `order.actual_delivery_date`, ersatzweise das Wunschlieferdatum. Nach R3 sollte das schon stimmen; der PATCH macht es ausdrücklich. Zum Schluss `POST $B/invoices/$NID/finalize`.

**R8: Belege prüfen und versenden**
```bash
for ID in <Storno 00002> <Storno 00004> <RE-00003 neu> <$NID>; do
  NR=$(api "$B/invoices/$ID" | jq -r .invoice_number); api "$B/invoices/$ID/pdf" -o "$K/$NR.pdf"
done
```
Die PDFs öffnen und Folgendes prüfen:
- **Stornorechnung:**
  - Titel „Stornorechnung Nr. …“
  - Zeile „Stornorechnung zur Rechnung Nr. RE-2026-0000X vom …“
  - Beträge negativ
  - Pfand mit 7 %
- **Ökoring neu:**
  - kein Pfand
  - Lieferdatum korrekt
- **Großer Kern neu:**
  - Steuer getrennt nach 7 % und 19 % ausgewiesen (S2)
  - Lieferdatum korrekt

Versand nach Absprache mit Gernot (Offener Punkt G4):
- **Empfohlen:** eine Mail je Kunde mit Stornorechnung, Neuausstellung und zwei Sätzen Erklärung, geschickt aus Gernots Postfach.
- **Alternativ** je Beleg über das System: `api -X POST "$B/invoices/<ID>/send?to_email=<Adresse>"`. Bei Stornorechnungen lautet der Betreff dann „Stornorechnung …“, ohne Fälligkeit.

**R9: Nachkontrolle**
```bash
api "$B/invoices/overdue" | jq '[.[] | select(.invoice_type=="GUTSCHRIFT")] | length'                          # 0
api "$B/invoices?status=OFFEN&page_size=100" | jq '[.[] | {invoice_number, invoice_type, total}]'                # Neuausstellungen ja, keine GUTSCHRIFT
api "$B/invoices?invoice_type=GUTSCHRIFT&page_size=100" | jq '[.[] | {invoice_number, status, total, reminder_level, original_invoice_id}]'
```
- **Am Folgetag nach 09:00** (Jobs `overdue-invoices` um 08:00 und `payment-reminders` um 09:00 Europe/Berlin, `scheduler_service.py:98-99`) die letzte Abfrage wiederholen. Erwartet: beide Stornorechnungen auf `STORNIERT` mit `reminder_level` 0.
- **Dashboard:** „Offene Rechnungen“ zählt die Neuausstellungen, aber keine Stornobelege.
- **Doppelabrechnung:** Die lesende Prüfabfrage P1–P6 aus R2b wiederholen.
  - P4a muss jetzt leer sein. Vorher zeigt sie die Ökoring-Bestellung mit RE-00002 und RE-00003.
  - P6 muss leer sein.
  - Einen Sammelrechnungslauf gibt es erst nach R12 (Sofortmaßnahme 3).
  - Variante A hängt keinen Lieferschein an RE-00003, weil der Entwurf vor S6 entstanden ist. Task 22 schützt trotzdem über `Invoice.order_id`. Ein Nachtrag ist optional über R11.
- **DATEV:** Der Export bleibt gesperrt, bis S4 umgesetzt und die Kontierung vom Steuerberater bestätigt ist. Task 17 exportiert dann jedes Stornopaar als Original (S) und Stornorechnung (H).

**R10: Dokumentation**
In der Akte (Mail an Gernot und den Steuerberater) festhalten:
- je Fall Original, Stornonummer, Neuausstellungsnummer, Datum, ausführende Person und Freigabe
- die gewählte Variante für RE-00003
- etwaige Lieferdatum-Abweichungen aus R3

Die Gründe stehen zusätzlich in `internal_notes` beider Belege. `$K` bleibt außerhalb des Repos.

**R11 (optional, nur mit ausdrücklicher Freigabe): `invoice_id` an Altrechnungen nachtragen**

Für den Schutz vor Doppelabrechnung **nicht nötig** — Task 22 prüft `Invoice.order_id`. Nutzen: einheitlicher Abrechnungsstand am Lieferschein (P2 wird leer, `GET /invoices/{id}/delivery-notes` zeigt ihn, Grundlage für B2 in Paket 3). Das PDF ändert sich dadurch nicht: Task 21 druckt die Lieferschein-Anlage nur bei Rechnungen ohne Bestellbezug, und betroffen sind nur Rechnungen mit Bestellbezug. **Reihenfolge:** erst nach R4–R10. Dann sind RE-00002/4 storniert (Status-Filter schließt sie aus) und ihre Neuausstellungen haben den Lieferschein schon über Task 21.

Regel des Skripts: je nicht stornierter Rechnung aus Bestellung genau ein Lieferschein (der älteste quittierte, sonst der älteste — wie `waehle_vertreter`), nur wenn an der Bestellung noch keiner hängt und sie genau eine aktive Rechnung hat (P4a-Fälle bleiben über die Zählung draußen, P4b-Fälle über „noch keiner hängt"). Idempotent: Ein zweiter Lauf findet nichts mehr.

a) Trockenlauf (schreibt nichts):

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84)
cat > /tmp/s6_nachtrag.py <<'PY'
import sqlite3, sys
DB = sys.argv[1]
SCHREIBEN = "--schreiben" in sys.argv
con = sqlite3.connect(DB, timeout=30)
# Je Rechnung aus Bestellung (nicht storniert, einzige aktive Rechnung der
# Bestellung) genau EIN Lieferschein: der älteste quittierte, sonst der älteste
# — dieselbe Regel wie waehle_vertreter in Task 21. Bestellungen, an denen schon
# ein Lieferschein hängt, bleiben unberührt.
zeilen = con.execute("""
SELECT i.id, i.invoice_number, i.status, d.id, d.delivery_note_number, d.status
FROM invoices i
JOIN delivery_notes d ON d.order_id = i.order_id
WHERE i.invoice_type = 'RECHNUNG' AND i.status != 'STORNIERT'
  AND d.invoice_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM delivery_notes d2
                   WHERE d2.order_id = i.order_id AND d2.invoice_id IS NOT NULL)
  AND (SELECT COUNT(*) FROM invoices i2
        WHERE i2.order_id = i.order_id AND i2.invoice_type = 'RECHNUNG'
          AND i2.status != 'STORNIERT') = 1
ORDER BY i.invoice_number, (d.status != 'GELIEFERT'), d.delivery_note_number
""").fetchall()
vertreter = {}
for inv_id, nr, inv_status, ls_id, ls_nr, ls_status in zeilen:
    vertreter.setdefault(inv_id, (nr, inv_status, ls_id, ls_nr, ls_status))
for nr, inv_status, ls_id, ls_nr, ls_status in vertreter.values():
    print(f"{nr} ({inv_status}) <- {ls_nr} ({ls_status})")
print(f"{len(vertreter)} Zuordnung(en) {'werden geschrieben' if SCHREIBEN else '(Trockenlauf, nichts geschrieben)'}")
if SCHREIBEN:
    with con:
        for inv_id, (nr, _, ls_id, ls_nr, _) in vertreter.items():
            n = con.execute(
                "UPDATE delivery_notes SET invoice_id = ? WHERE id = ? AND invoice_id IS NULL",
                (inv_id, ls_id),
            ).rowcount
            assert n == 1, f"{ls_nr}: {n} Zeilen"
            print(f"RUECKNAHME: UPDATE delivery_notes SET invoice_id = NULL "
                  f"WHERE delivery_note_number = '{ls_nr}';")
PY
docker cp /tmp/s6_nachtrag.py "$C":/tmp/s6_nachtrag.py
docker exec "$C" python /tmp/s6_nachtrag.py /data/tenants/minga.db
```

Ausgabe Gernot bzw. dem Freigebenden vorlegen.

b) Nach Freigabe — WAL-sicheres Backup über die SQLite-Backup-API, außerhalb von `/data/tenants` (dort würde `registry.known_slugs()` jede `*.db` als Mandant laden, `tenancy.py:96`):

```bash
docker exec -i "$C" python - <<'PY'
import sqlite3, pathlib, datetime
ziel = pathlib.Path("/data/tenants-backup"); ziel.mkdir(exist_ok=True)
datei = ziel / f"minga-vor-s6-nachtrag-{datetime.datetime.now():%Y%m%d-%H%M%S}.sqlite"
src = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
dst = sqlite3.connect(datei)
src.backup(dst); dst.close(); src.close()
print("Backup:", datei, datei.stat().st_size, "Bytes")
PY
```

c) Schreiben (eine Transaktion; jede Zeile wird mit `invoice_id IS NULL` abgesichert):

```bash
docker exec "$C" python /tmp/s6_nachtrag.py /data/tenants/minga.db --schreiben
```

Die Ausgabe enthält je geschriebener Zuordnung eine `RUECKNAHME:`-Zeile — sichern. Rücknahme heißt: genau diese Anweisungen ausführen. Das DB-Backup nicht zurückspielen, das verlöre zwischenzeitliche Buchungen.

d) Kontrolle: R2b erneut. Erwartet: P2 leer bis auf Bestellungen aus P4a. (P4b-Bestellungen tauchen in P2 nicht auf: An ihnen hängt schon ein Lieferschein.)

**R12: Trockenlauf des nächsten Sammellaufs, dann Sammellauf freigeben**

Erst wenn P4a, P4b und P6 leer sind und Gernot die P5-Liste kennt (nach einer Korrektur aus P4a/P4b R2b erneut ausführen): In der Oberfläche „Rechnungen → Sammelrechnung", Zeitraum wählen, **nur „Vorschau"** (`POST /invoices/batch-run/preview` schreibt nichts, `invoices.py:573-575`). Prüfen: Keine Bestellung aus P1/P2 erscheint, `anzahl_lieferscheine` je Kunde = Zahl der Bestellungen. Ausnahme: Bestellungen, deren Rechnung wegen P4a/P4b storniert wurde, erscheinen — und zwar je genau einmal (das ist die Neuausstellung). Festschreiben erst nach Gernots Freigabe des Laufs. Danach ist Sofortmaßnahme 3 aufgehoben.

**Abbruch und Rückweg:**
- Ein Storno ist absichtlich endgültig, es gibt kein „Entstornieren“.
- Bricht der Ablauf zwischen R4 und R6/R7 ab, ist das unkritisch: Die Neuausstellung kann später folgen.
- Eine falsch finalisierte Neuausstellung wird selbst wieder storniert und neu ausgestellt, nach demselben Verfahren.
- Das Backup aus R0 einspielen nur als letztes Mittel und nur mit Nikolajs Entscheidung, weil dabei alle zwischenzeitlichen Buchungen des Mandanten verloren gehen.

---

## Nebenbefunde (nicht Teil von Paket 1, nur gemeldet)

- **Gesamtrabatt der Bestellung:** `create_order` übernimmt `OrderCreate.discount_percent` nicht in die Bestellung; `create_invoice_from_order` übergibt keinen Bestellrabatt, es greift der Kundenrabatt (S1).
- **Shopify-Preise:** `price` wird immer als netto behandelt; Shops mit `taxes_included=true` würden zu viel Steuer ausweisen (S1).
- **Abo-Pfade (A5, Paket 2):** `subscription_tasks.py:149-158` legt Abo-Positionen ohne `product_id` an und nimmt den Satz von einem über `seed_id` gesuchten Produkt; `invoice_tasks.py:260-266` setzt fest 7 % und 0,08 €. Task 6 korrigiert diese Positionen nicht (weder `product_id` noch Variante). „A3 vollständig" deckt sie nicht ab; der Fix gehört zu A5 (S1).
- **Altpositionen ohne Variante:** Bis Task 1 verwarf `POST /sales/orders/{id}/lines` die `product_variant_id`; so nachgetragene reine Variantenpositionen erkennt Task 6 nicht. Nur über die API erreichbar, in Gernots Daten nicht zu erwarten (S1).
- **`ProductUpdate.name`** lässt ein ausdrückliches `null` durch; `PATCH {"name": null}` endet in einem 500. Die Maske schickt nie `null` (S1).
- **Vorlagen-Vorschau „Rechnung" ist kaputt:** `GET /api/v1/document-templates/RECHNUNG/preview.pdf` scheitert schon heute (`build_dummy_invoice` in `document_template_service.py:164-190` fehlen `service_period_start`, `service_period_end`, `order`, `total_deposit`, an den Zeilen `sku`). Eine Reparatur muss zusätzlich `subtotal`, `tax_amount` und `total` des Dummys aus `steuer_je_satz(lines, Decimal("0"))` ableiten, sonst zeigt die Vorschau die Rückfallzeile „USt:" (S2).
- **Reverse-Charge-Hinweis bei jeder 0-%-Position** (`pdf_service.py:351-360`), auch wo eine innergemeinschaftliche Lieferung einen anderen Hinweis bräuchte (S2; Offener Punkt GB2).
- **`record_payment`:** Zwei Zahlungen in **derselben** Session ergeben `paid_amount` 30,00 statt 50,00 € (Collection nach dem ersten Zugriff veraltet, `invoice_service.py` ~271-275). Über die API nicht erreichbar. Die Altlasten `test_record_full_payment`/`test_record_partial_payment` haben eine andere Ursache (Test ruft `db.refresh(invoice)` ohne `flush`). Spätere Absicherung: `self.db.refresh(invoice, ["payments"])` nach dem `flush` (S3).
- **Bestellung vs. Rechnung bei Rechnungsrabatt:** `vat_from_lines` (`models/order.py:21-41`) rechnet die Steuer ohne Zwischenrundung; Auftragsbestätigung und Rechnung können in seltenen Fällen 1 ct auseinanderliegen (S2).

## Offene Punkte für Kunde und Steuerberater

**Gernot (G):**
- **G1:** Liste der von Task 6 korrigierten Bestellungen (Runbook L1): Sollen bereits versendete Auftragsbestätigungen oder Lieferscheine mit Preisen neu an Kunden gehen? Beide PDFs zeigen nach der Korrektur 19 %.
- **G2:** Echtes Lieferdatum je Rechnung RE-00002/4 (07. oder 08.10.2026) und Name des Empfängers für das nachträgliche Quittieren der Lieferscheine (Runbook R3).
- **G3:** Welche Kunden rechnen Pfand über das IFCO-Clearing ab (`pfand_abrechnung = KEINE`) — nur Ökoring und Bodan (Spec, offene Entscheidungen von Gernot, Nr. 6)? Ist Ökoring Clearing-Kunde (Voraussetzung für R6, Neuausstellung ohne Pfand)? Bis zur Antwort steht jeder Kunde auf `JE_LIEFERUNG`, Pfand wird wie heute fakturiert.
- **G4:** Versand der Korrekturbelege: eine Mail je Kunde aus Gernots Postfach (empfohlen) oder Versand je Beleg aus dem System (R8)?
- **G5:** lexoffice, falls RE-00002/4 übertragen wurden: dort Entwurf löschen bzw. Beleg stornieren (R5).
- **G6:** Produkt-Importdatei: Steht in `tax_rate` für Pfandartikel ausdrücklich `REDUZIERT`, setzt ein Re-Import weiterhin 7 % (ausdrückliche Angabe, kein Default mehr).
- **G7:** Pfand in Bestellungen immer über den Pfandartikel (Produkt mit Pfandkennzeichen) erfassen; Freitext-Pfandzeilen erkennt das System nicht, sie landen auch bei `KEINE` auf der Rechnung.
- **G8:** Clearing-Kunden mit „Preise auf Lieferschein andrucken": Soll die Pfandzeile auf deren Lieferschein weiter mit Preis erscheinen (heute ja)?
- **G9:** Die Rechnungsliste zeigt die neuesten 100 Rechnungen, ältere über Status- und Typfilter. Reicht das bis Paket 3 (echtes Blättern, Datumsfilter)?
- **G10:** Bestellungen `FAKTURIERT` ohne Rechnung im System (Runbook P5): Der Sammellauf überspringt sie ab Task 22 (Spec-Nachtrag). Wurden sie außerhalb von NovaERP berechnet? Was nicht berechnet wurde, wird einzeln über „Rechnung aus Bestellung" abgerechnet.
- **G11:** Nur quittierte Lieferungen (Lieferschein `GELIEFERT`) in die Sammelrechnung? Heute gehen auch Lieferscheine im Status `ENTWURF` hinein (Dialog-Überarbeitung B5, Paket 3).
- **G12:** Lieferscheinnummer auch auf Rechnungen aus Bestellung? Braucht eine unveränderliche Quelle (z. B. `invoice_line_sources`); Paket 3, mit dem Steuerberater abzustimmen.
- **G13:** Sammelrechnungen, deren PDF bis Task 10 nicht abrufbar war (falls P1 RE-00001 oder RE-00005 als Sammelrechnung mit Lieferschein zeigt): Wie hat die Rechnung den Kunden erreicht?
- **G14:** Die 46 rückdatiert importierten Bestellungen (A6) haben keinen Lieferschein; der Sammellauf erfasst sie nicht. Müssen sie noch abgerechnet werden?

**Steuerberater (B):**
- **B1:** Rundungsregel bestätigen: Rechnungsrabatt je Satz auf den Cent, Steuer je Satz auf das gerundete Entgelt, Rechnungssteuer = Summe der Satzsteuern. Folge: Bei mehreren Sätzen mit Rabatt kann die Zeile „Rabatt" 1 ct von „Zwischensumme × Rabattsatz" abweichen.
- **B2:** Bereits versendete Rechnungen mit 7 % **und** 19 % trugen keinen Ausweis je Satz (§ 14 Abs. 4 Nr. 8 UStG). Genügt das, oder Storno und Neuausstellung?
- **B3:** Altrechnungen mit 1-ct-Abweichung (Runbook L2/L3): Reicht die festgeschriebene USt-Zeile, und wie werden sie in DATEV verbucht?
- **B4:** Das PDF wird bei jedem Abruf neu erzeugt; eine früher versendete Rechnung sieht beim erneuten Abruf anders aus (Spalte „MwSt"), die Beträge bleiben. Muss die versendete Datei selbst archiviert werden (Paket 3, Versandlog)?
- **B5:** DATEV-Kontierung bestätigen: Bruttobuchung auf Automatikkonten ohne BU-Schlüssel, Konto = Debitor / Gegenkonto = Erlöskonto, S für Rechnung, H für Gutschrift, keine Buchung auf 1400 (SKR03 angenommen); Konten 8300/8400/8100, Pfand auf 8400 oder eigenes Konto; Erlöskonto-Regel (Standardkonto folgt dem Satz, Sonderkonto bleibt; Rest-Cent bei mehreren Konten je Satz trägt die betragsgrößte Gruppe); gefundene Kopfkonten ≠ 8300 (Runbook K1).
- **B6:** Stornobehandlung in DATEV: Original (S) und Stornorechnung (H) werden exportiert, eine stornierte Rechnung ohne Stornorechnung (z. B. verworfener Entwurf RE-00003 in Variante B) nicht; nach dem Export ist Storno nur mit Stornorechnung möglich.
- **B7:** Debitorenkonten: Nummernkreis festlegen und pflegen oder Sammeldebitor 10000 bewusst nutzen (der Stammdatenexport fällt heute auf `KD-…` zurück).
- **B8:** Gutschrift von Hand wird als Minderung (H) gebucht, zählt in der App aber als positive Forderung. Soll der Typ GUTSCHRIFT im Anlageformular bleiben?
- **B9:** Zahlungen exportieren (heute Default) oder holt der Steuerberater die Bankumsätze selbst (sonst doppelt)? Zahlungen auf nicht exportierte Belege (Proforma, Entwurf, ohne Stornorechnung storniert) stehen lassen oder ausfiltern; soll `record_payment` sie überhaupt annehmen? Belegfeld 2 (Zahlungsreferenz) ist für DATEV zu lang.
- **B10:** Format EXTF-Buchungsstapel oder DATEV Unternehmen online; Berater-/Mandantennummer, WJ-Beginn, Sachkontenlänge (erst damit ist `Belegdatum` jahresgenau); Kontierung von Abschlagsrechnungen. Nicht Teil von Paket 1 (Spec, Entscheidung 5).
- **B11:** Leistungsdatum: quittiertes Lieferdatum (`orders.actual_delivery_date`), ersatzweise Wunschlieferdatum — für Rechnung aus Bestellung (Task 2) wie Sammelrechnung.
- **B12:** RE-00003: Variante A (Entwurf wird die Neuausstellung, keine Nummernlücke) oder B (verwerfen ohne Stornorechnung, Ökoring bekommt eine neue Nummer)? Variante C (löschen) ist nicht vorgesehen.
- **B13:** Falls auf RE-00002/4 schon gezahlt wurde: auf die Neuausstellung umbuchen oder erstatten? Am stornierten Beleg bleibt ein Zahlungsdatensatz stehen.
- **B14:** Eine stornierte Sammelrechnung verliert beim erneuten PDF-Abruf ihre Anlage „Enthaltene Lieferscheine" (bestehender Effekt von R1.6). Hinnehmbar, oder soll die Anlage künftig aus `invoice_line_sources` kommen?

**Gernot und Steuerberater gemeinsam (GB):**
- **GB1:** Pfand IFCO-Kiste mit 19 % als Transporthilfsmittel bestätigen (Spec, offene Entscheidungen von Gernot, Nr. 4) — Voraussetzung für R7 (RE-00004 neu). Ändert sich die Einordnung, genügt eine Änderung des Satzes am Pfandartikel; danach `korrigiere_offene_bestellpositionen` erneut für offene Bestellungen.
- **GB2:** Welche steuerfreien Umsätze hat Minga Greens (innergemeinschaftliche Lieferung § 4 Nr. 1b UStG mit USt-IdNr. oder Reverse Charge § 13b UStG)? Davon hängen der Pflichthinweis nach § 14 Abs. 4 Nr. 9 UStG (heute pauschal § 13b) und das Konto (heute 8100) ab.
- **GB3:** Durften auf RE-00002/3 (Ökoring) und RE-00004 (Großer Kern) überhaupt Pfandpositionen stehen? Die Antwort entscheidet mit G3, ob RE-00002 ohne Pfand (R6) oder mit 19 % neu ausgestellt wird.

**Für Nikolaj (keine Kundenfrage):**
- **N1 (entschieden, Spec „Von dir — entschieden“ Nr. 6 vom 08.10.):** „Sammelrechnung als Entwurf" kommt in Paket 3 mit „Nummer erst beim Finalisieren"; Paket 1 lässt `batch_run_commit` auf `OFFEN`. Mit `MONATLICH` (Paket 3) wird `ist_clearing_pfand` (Task 27) erweitert und die Rechnungsliste (Task 28) zusätzlich nach `created_at desc` sortiert.
- **N2 (offen):** Feldschutz für `pfand_abrechnung` (Nachtrag T3, Stufe 1): Ändern nur durch Admin, Vertrieb und Buchhaltung, auch bei der Neuanlage, und nur wenn sich der Wert ändert. Kein Abschnitt von Paket 1 baut ihn. Vor der Vergabe von Mitarbeiter-Logins (`production_staff` darf den Kunden-Router benutzen) nachziehen, z. B. mit dem B8-Kern in Paket 3. Bitte entscheiden, ob das noch in Paket 1 gehört.
