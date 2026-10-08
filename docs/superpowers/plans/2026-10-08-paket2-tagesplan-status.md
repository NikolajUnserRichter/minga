# Paket 2 — Tagesplan und Status — Implementation Plan

> **For agentic workers:** Diesen Plan Task für Task in der Reihenfolge der Nummern abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Kein Task wird übersprungen, zusammengefasst oder auf eigenes Urteil verkürzt. Inhaltliche Widersprüche zwischen Plan und Code: stoppen und mit exakter Fehlerausgabe melden. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht (z. B. eine um wenige Zeilen verschobene Fundstelle): selbst auflösen und in der Abschlussmeldung vermerken. **Task 24** hat eine Vorbedingung (Paket 1, Task 1 auf dem Branch); ist sie nicht erfüllt, Task 24 offen lassen und melden. Die **Runbooks** am Ende sind Manager-Arbeit, kein Worker-Task.

**Goal:** Ein Klick auf „Gepackt" bzw. „Ausgeliefert" im Tagesplan ändert den Status sichtbar und richtig. Gepackte Bestellungen fallen aus „Verpacken" und aus dem Sortenbedarf, bleiben aber in „Ausliefern". Alle Wege nach GELIEFERT folgen einer Regel (Übergänge, Lieferdatum, Bestandsabzug, Audit-Log). Die Oberfläche zeigt keine Enum-Werte mehr, Sammelaktionen melden ehrlich. Die Rechnungsliste zeigt den Kunden. Abo-Bestellungen tragen Produkt, Kundenpreis und Produktsatz, kommen an jedem Liefertag genau einmal, und der Knopf „Heute verarbeiten" wirkt im eigenen Mandanten.

**Architecture:** Ein neuer Service `backend/app/services/order_status_service.py` hält die Übergangstabelle `ERLAUBTE_UEBERGAENGE`, die Bezeichnungen `STATUS_BEZEICHNUNG`, `heute_berlin()` und `setze_status(...)` (Übergang prüfen, Lieferdatum, Audit-Log, Bestandsabzug; committet nicht). Status-Endpunkt, Lieferschein-Quittieren und Sammel-Endpunkt rufen nur noch diese Funktion. „Gepackt" ist kein neuer Status: `IN_PRODUKTION` heißt in der Oberfläche „Gepackt"; der Tagesplan trennt in Python (`_NOCH_ZU_PACKEN`, `_SCHON_GEPACKT`), weil „Verpacken" und „Ausliefern" aus derselben Abfrage kommen. Das Backend liefert Status immer als Enum-Wert, übersetzt wird nur in `frontend/src/components/ui/statusLabels.ts`; `invalidateOrderViews` lädt nach jedem Statuswechsel Bestellliste, Tagesplan und beide Packplan-Abfragen neu. A2 sind zwei Properties am Modell `Invoice` plus `joinedload`. A5 baut den Abo-Lauf um: `ist_faellig`, `abo_position` (Preisregel wie `create_order`), `abo_lauf(db, heute)` mit Doppelanlagesperre; der Knopf nimmt die Session der Anfrage. Keine Spalte, keine Migration, keine neuen Status-Werte.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`), SQLite je Mandant, Pydantic v2, APScheduler/Celery (Abo-Lauf), React + TypeScript, TanStack Query 5.

**Spec:** `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, „Paket 2 — Tagesplan und Status" (A1 · A4 · A2 · A5 · Import-Härtung A6-Rest), dazu die geprüften Diagnosen `/tmp/bugpruefung/A1.md`, `A2.md`, `A4.md` und die Lückenprüfung `/tmp/bugpruefung/LUECKEN.md`. Grundlage sind die vier geprüften Abschnitte `/tmp/paket2/P1.md` bis `P4.md`. **Nicht in diesem Plan:** die Import-Härtung (A6-Rest). Für sie gibt es noch keinen geprüften Abschnitt (Entscheidung E2).

## Reihenfolge und Abhängigkeiten

| Abschnitt | Inhalt | Tasks | Setzt voraus |
|---|---|---|---|
| P1 | A1 — eine Statusregel für alle Wege nach GELIEFERT, „Ausgeliefert" im Tagesplan, Bezeichnungen statt Enum-Werten, ehrliche Sammelaktionen | 1–9 | — |
| P2 | A4 — Knopf „Gepackt" im Tagesplan, Sortenbedarf und Packliste ohne Gepackte, Dashboard | 10–15 | Task 1 (IN_PRODUKTION → STORNIERT), Task 4 (`_AUSGELIEFERT`, Enum-Wert), Task 6 (Bezeichnungen), Task 7 (`invalidateOrderViews`, Selbstaktualisierung), Task 8 (Storno bei Gepackt im Dialog) |
| P3 | A2 — Kunde in Rechnungsliste, Detail und „Überfällig" | 16–18 | — (nur die gemeinsame Testdatei) |
| P4 | A5 — Abo-Bestellungen mit Produkt, Preis, Satz; mehrere Liefertage; Knopf im richtigen Mandanten | 19–22 | Task 1 (`heute_berlin`, nur Task 22) |
| Abschluss | Testdatei komplett, Schluss-Vollauf, Frontend-Build, Abschlussmeldung | 23 | 1–22 |
| Nach Merge Paket 1 | Abo-Satz über `steuersatz_der_position` | 24 | Paket-1-Task 1 auf dem Branch |
| Runbooks A–C | Prüfung vor dem Deploy, LfA-Entwürfe, Nachquittieren und Live-Prüfung | — | Deploy, Freigaben |

P3 und P4 hängen fachlich nicht an P1/P2. Sie laufen trotzdem danach auf demselben Branch, nicht parallel: Alle vier Abschnitte schreiben in dieselbe Testdatei, P1 und P3 in `frontend/src/pages/Invoices.tsx` und `frontend/src/types/index.ts`, P1 und P4 in `backend/app/api/v1/sales.py`.

**Zusammengeführte Doppelarbeit:**
1. **Statusfunktion:** eine Stelle, `order_status_service.setze_status` (Task 1), für Status-Endpunkt, Quittieren (Task 2) und Sammel-Endpunkt (Task 3). P2 nutzt den bestehenden Status-Endpunkt unverändert und fasst `sales.py` nicht an.
2. **Bezeichnungen:** Backend `STATUS_BEZEICHNUNG` (Task 1), Frontend `statusLabels.ts` und `OrderStatusBadge` (Task 6). P2 übernimmt `OrderStatusBadge`; die im Einzelabschnitt P2 vorbereiteten Ersatzzeilen für einen Stand ohne P1 entfallen.
3. **Neuladen:** nur `invalidateOrderViews` (Task 7). Auch die Mutation „Gepackt" im Tagesplan (Task 13) ruft ihn, statt die vier Abfragen selbst zu invalidieren.
4. **Selbstaktualisierung des Tagesplans** (`refetchInterval`, `refetchOnWindowFocus`): nur in Task 7, Task 13 prüft sie nur.
5. **Bestellseiten** (`Orders.tsx`, `OrderCard.tsx`, `Sales.tsx`, `EditOrderModal.tsx`): nur P1 (Tasks 6 und 8). Die Aufteilung auf zwei Tasks ist Absicht: `tsconfig.json` hat `noUnusedLocals`, `orderStatusLabel` kommt in `Orders.tsx` erst mit seinem ersten Aufrufer in Task 8. P2 prüft sie in Task 10 Step 0.
6. **Berliner Kalendertag:** `order_status_service.heute_berlin()` (Task 1) ist die eine Rechnung; der Abo-Lauf ruft sie über `liefertag_heute()` (Task 22). Der Einzelabschnitt P4 brachte eine eigene Rechnung mit und empfahl selbst die Zusammenführung. `imports._today_berlin()` bleibt unberührt (Hotfix `efcea00`, Folgepunkt F3).
7. **Testdatei:** Kopf und `autouse`-Fixture nur in Task 1; P2–P4 hängen ihre Blöcke an. Die Fixture `_a4_ohne_celery` aus P2 ist neben der `autouse`-Fixture überflüssig, aber harmlos; sie bleibt, weil P2 mit ihr gemessen wurde.
8. **Vorbereitung, Vollauf, Abschluss:** Basis-Commit einmal vor Task 1; Vollauf als Prozedur V; Schluss-Vollauf, Frontend-Build, Diff-Prüfung und Abschlussmeldung einmal in Task 23 (in den Einzelabschnitten verteilt auf P1, P2, P3 und P4).

**Prüfstand (alles in Kopien außerhalb des Repos, Repo unverändert):**
- P1 auf einer Kopie von `efcea00` mit allen Code-Blöcken: 39 passed; Vollauf mit `REDIS_URL=memory://` 15 failed / 546 passed / 2 skipped / 1 error in 22 s, Fehlernamen identisch mit der Baseline; `tsc --noEmit` ohne Ausgabe, `vite build` endet mit `✓ built`. Gegen den Paket-1-Stand mit S6 plus P1-Backend: genau ein Paket-1-Test rot (Überschneidung 1).
- P2 auf einem P1-Probestand mit damals 37 P1-Tests: 55 passed, Vollauf 19:40 min mit Baseline-Fehlernamen. Seitdem kamen in P1 zwei Tests hinzu (`test_storno_nach_gepackt_bucht_keinen_bestand`, `test_bestandsfehler_laesst_lieferschein_offen`), keiner liest `verpacken`. Die erwarteten Zahlen in Tasks 10–12 sind auf 39 P1-Tests umgerechnet.
- P3 auf `efcea00`: 8 passed; 18 rechnungsnahe Testdateien 222 passed / 11 failed, alle 11 Baseline.
- P4 auf einer frischen `git archive efcea00`-Kopie: 21 passed, Vollauf 15 failed / 528 passed / 2 skipped / 1 error, Baseline-Namen. Task 24 gegen das `steuersatz.py` aus Paket 1: 21 passed.
- **Nicht gemessen:** die vollständige Testdatei mit allen vier Abschnitten zusammen (Task 23 Step 1), die Zusammenführung in Task 13 (`invalidateOrderViews` statt vier Aufrufen) und in Task 22 (`liefertag_heute()` über `heute_berlin()`, Test patcht `order_status_service.datetime`).

## Global Constraints

- **Arbeitsort:** Worktree `/Users/nikolajunser-richter/minga-paket2`, Branch `feat/paket2-tagesplan-status`, Basis `efcea00` (enthält den Import-Hotfix A6). Jeder Run beginnt im Worktree-Wurzelverzeichnis.
- **Zeilenangaben** beziehen sich auf `efcea00`; nach früheren Tasks verschieben sie sich — maßgeblich ist der zitierte Inhalt.
- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` und `backend/venv311` sind kaputt.
- **Einzeltest:** `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/<datei> -v`.
- **Prozedur V (Vollauf):** `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE 2>&1 | tail -30` — ca. 19 min.
- **Zwischenläufe** dürfen `REDIS_URL=memory://` voranstellen (`cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ …`, am 08.10.2026 verifiziert, ca. 22 s, gleiche Fehlerliste). Der Schluss-Vollauf in Task 23 läuft ohne die Variable; im Zweifel zählt er.
- **Baseline `main`:** 15 failed + 1 error. **Nur die Fehlernamen vergleichen, nie die Anzahl.** Die Altlasten: `test_api.py::TestHealth::test_root_endpoint`, `test_refinements.py::test_main_app_imports`, `test_auth_manual.py::test_auth_failure`, `test_auth_manual.py::test_auth_success`, `test_features.py::TestFeatures::test_subscription_processing`, `test_production_readiness.py::test_dunning_level1/2/3`, `test_production_readiness.py::test_quality_auto_approved`, `…::test_quality_rejected_high_loss`, `…::test_quality_rejected_low_note`, `test_services.py::TestInvoiceService` ×4, plus ERROR `test_production_automation.py::test_approve_suggestion_creates_grow_batch`.
- **Neue Tests** nur in `backend/tests/test_gernot_261008_paket2.py`. Helfer: P1 ohne Präfix, P2 `_a4_`, P3 `_a2_`, P4 `_p4_`/`_P4_`. Fixture `client` aus `tests/conftest.py`. Der Helfer `_produkt` der Aufgabenstellung liegt in `tests/test_gernot_260917.py:21`, nicht in `test_gernot_261002.py`; die Abschnitte bringen eigene Helfer mit (`_produkt` in Task 1, `_p4_produkt` in Task 19).
- **Bestehende Erwartungen** nur dort ändern, wo ein Task es begründet: `test_gernot_bugfixes.py:140` (Task 4), `_FakeSub` in `test_gernot_260817.py` (Task 21), `test_gernot_261008.py` (nur Task 2 Step 5, nur wenn Paket 1 auf dem Branch liegt). `test_gernot_260817.py:187-206` bleibt unverändert: Die Same-Day-Bestellung steht weiter in „Verpacken" und „Ausliefern".
- **Keine neuen Status-Werte.** `IN_PRODUKTION` heißt in der Oberfläche „Gepackt", `GELIEFERT` „Geliefert" wie bisher in `OrderStatusBadge`; „Ausgeliefert" ist nur die Beschriftung des Knopfs im Tagesplan. `OrderStatusBadge` liegt in `frontend/src/components/ui/Badge.tsx` (Z. 57-75), nicht in `components/common/`.
- **Übergänge** (eine Tabelle, Task 1): ENTWURF → BESTAETIGT, STORNIERT · BESTAETIGT → IN_PRODUKTION, GELIEFERT, STORNIERT · IN_PRODUKTION → GELIEFERT, STORNIERT · GELIEFERT → FAKTURIERT · FAKTURIERT, STORNIERT → nichts. ENTWURF → GELIEFERT ist auf keinem Weg erlaubt.
- **Ein Weg nach GELIEFERT:** `POST /sales/orders/{id}/status`, `PATCH /sales/delivery-notes/{id}/mark-delivered` (`documents.py`) und `POST /sales/orders/bulk-status` (`sales.py` ~1544) rufen `order_status_service.setze_status` — Übergangsregel, Bestandsabzug, `actual_delivery_date`, Audit-Log in einer Transaktion. Am Code geprüft: andere Stellen setzen keinen Bestellstatus nach GELIEFERT (der Import legt Bestellungen an, wechselt aber keinen Status).
- **Bestand** wird nur beim Übergang nach GELIEFERT gebucht (`deduct_inventory_for_order`, am Code geprüft; `reserve_for_order` hat keinen Aufrufer). Packen und Stornieren nach „Gepackt" buchen nichts.
- **Keine neue Spalte, keine Migration, kein `_auto_migrate`.** Das vermeidet das Demo-Reset-Problem (LUECKEN.md Punkt 5).
- **Paket 1** läuft parallel auf `feat/paket1-steuer-rechnung` (Worktree `/Users/nikolajunser-richter/minga-paket1`, Plan `/tmp/paket1/plan-final.md`, Tasks 1–29; am 08.10. sind Tasks 1–7 committet). Dateien mit Überschneidung nur an den genannten Stellen ändern. Nicht anfassen: `_create_audit_log` in `sales.py`, `backend/app/services/invoice_service.py`, `list_invoices` außer der Ladezeile.
- **Kein Netzwerk** in der Codex-Sandbox: kein `npm install`, kein `git pull`. **Kein Deploy, keine Verbindung zum Produktionsserver.**
- **Commits** nur mit den genannten Dateilisten, nie `git add -A` oder `git add .`: `frontend/node_modules` ist im Worktree ein Symlink auf das Hauptrepo und erscheint als untracked.
- **Frontend-Prüfung:** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut). `tsconfig.json` hat `noUnusedLocals`: keine Importe vorziehen. Die Playwright-Suite gehört nicht zur Worker-Prüfung (braucht Browser und laufende Server).
- **Knopf-Test aus Task 22** nie ohne den Patch auf `SessionLocal` laufen lassen: `backend/data/tenants/dev.db` ist im Hauptrepo eine echte lokale Dev-DB.
- UI-Texte auf Deutsch.

## Review Focus

Die fünf Eingaben bzw. Zustände, die ein Anwender am ehesten trifft und die **kein automatischer Test** abdeckt (es gibt keine Frontend-Tests; der Manager prüft sie im Browser, Abnahme Prüfungen 1–11):

1. **Doppelklick in der Bestellkarte.** Am 07.10. liefen fünf Bestellungen in derselben Sekunde BESTAETIGT → IN_PRODUKTION → GELIEFERT, weil „Geliefert" nach dem ersten Klick an die Stelle von „In Produktion" rückte. Jetzt stehen „Gepackt" und „Geliefert" nebeneinander, die Karte sperrt bis zur Antwort. → **Task 8** (Step 1); Prüfung 3.
2. **Hallen-Tablet mit altem Stand.** Ein zweites Gerät hat die Bestellung schon gepackt oder geliefert. Ein Klick auf „Gepackt" muss einen verständlichen Fehler-Toast zeigen („Statuswechsel nicht möglich: Gepackt → Gepackt"), neu laden und darf nichts doppelt auslösen; ohne Klick ist der Plan nach spätestens 60 s aktuell. → **Task 13** (Step 4), mit Task 7; Prüfung 7.
3. **Absage nach dem Packen.** Eine gepackte Bestellung wird im Bearbeiten-Dialog storniert; „Position hinzufügen" darf dabei nicht erscheinen. Der API-Übergang ist getestet (Task 1), der Dialog nicht. → **Task 8** (Step 4); Prüfung 5.
4. **Nachquittieren im Belege-Dialog** (Gernots Bestellungen vom 07./08.10.). Das Feld „Liefertag" schlägt das Lieferdatum der schon gelieferten Bestellung bzw. den vergangenen Liefertag vor, höchstens heute; bei Entwurf oder Storniert steht ein Hinweis statt des Knopfs. Server getestet (Task 2), Dialog nicht. → **Task 9**; Prüfung 6.
5. **„Ausgeliefert" für einen vergangenen Tag und kurz nach Mitternacht.** Der Tagesplan eines früheren Tages schickt dessen Datum als Liefertag; „heute" ist der lokale Kalendertag, nicht UTC (zwischen 0 und 2 Uhr lag `toISOString()` einen Tag zurück). → **Task 7** (Step 2); Prüfung 1.

Jeder Abschnitt hat zusätzlich einen eigenen Review Focus für die getesteten Regeln.

## File Structure

„Paket 1" nennt die Tasks aus `/tmp/paket1/plan-final.md`, die dieselbe Datei ändern. Details im folgenden Abschnitt.

| Datei | Verantwortung | Abschnitt | Tasks | Paket 1 |
|---|---|---|---|---|
| `backend/app/services/order_status_service.py` | **neu** — Übergangstabelle, Bezeichnungen, `heute_berlin`, `setze_status`, `trage_lieferdatum_nach` | P1 | 1, 2 (22 nutzt `heute_berlin`) | — |
| `backend/app/api/v1/sales.py` | Status-Endpunkt, Sammel-Endpunkt, Fehlertexte; Knopf „Heute verarbeiten" | P1, P4 | 1, 3, 5, 22 | **ja** — Task 1 (Importzeile nach Z. 33: sicherer Textkonflikt) |
| `backend/app/schemas/order.py` | `OrderStatusUpdate.actual_delivery_date`, `BulkStatusUpdate`, `BulkStatusResult` | P1 | 1, 3 | **ja** — Task 1 (Z. 35) |
| `backend/app/api/v1/documents.py` | Quittieren über die Statusregel | P1 | 2 | **ja** — Task 23 |
| `backend/app/api/v1/production.py` | day-plan: Gelieferte in „Ausliefern", Enum-Wert, `packbar`, `verpacken_erledigt`; packaging-plan ohne Gepackte, `gepackt` | P1, P2 | 4, 11, 12 | — |
| `backend/app/api/v1/forecasting.py` | Fehlertexte Produktionsvorschlag | P1 | 5 | — |
| `backend/app/models/invoice.py` | Properties `customer_name`, `customer_number` | P3 | 16 | **ja** — Task 8 (Nachbarschaft `get_tax_summary`) |
| `backend/app/api/v1/invoices.py` | `list_invoices` lädt den Kunden (nur Z. 47), `list_overdue_invoices` | P3 | 17 | **ja** — Tasks 24, 28 u. a. |
| `backend/app/tasks/subscription_tasks.py` | Fälligkeit, Position, `abo_lauf`, Doppelanlagesperre, Liefertag | P4 | 19, 21, 22, 24 | — (Task 24 nutzt `steuersatz.py` aus Paket-1-Task 1) |
| `backend/app/tasks/invoice_tasks.py` | toten Abo-Rechnungstask entfernen | P4 | 20 | **ja** — Task 13 |
| `backend/tests/test_gernot_261008_paket2.py` | **neu** — alle Tests dieses Plans | alle | 1–5, 10–12, 16, 17, 19–22 | — |
| `backend/tests/test_gernot_bugfixes.py` | Z. 140: `"Entwurf"` → `"ENTWURF"` | P1 | 4 | — |
| `backend/tests/test_gernot_260817.py` | `_FakeSub` um Produktfelder ergänzen | P4 | 21 | — |
| `backend/tests/test_gernot_261008.py` | **nur falls Paket 1 auf dem Branch:** S6-Test bestätigt vor dem Quittieren | P1 | 2 | **ja** — Paket-1-Datei (Task 22) |
| `frontend/src/components/ui/statusLabels.ts` | **neu** — alle Bezeichnungen | P1 | 6 | — |
| `frontend/src/components/ui/Badge.tsx`, `frontend/src/components/ui/index.ts` | `OrderStatusBadge` über die Bezeichnungen, Export | P1 | 6 | — |
| `frontend/src/services/orderQueries.ts` | **neu** — `invalidateOrderViews` | P1 | 7 | — |
| `frontend/src/services/api.ts` | `DayPlanOrder.status`, `updateOrderStatus` mit Lieferdatum, `bulkUpdateStatus`; Typen `packbar`, `verpacken_erledigt`, `gepackt` | P1, P2 | 6, 13 | **ja** — Tasks 15, 19, 23, 24, 28 |
| `frontend/src/types/index.ts` | `Order.actual_delivery_date`; `Invoice.customer_name`/`customer_number` nullable | P1, P3 | 9, 18 | **ja** — Tasks 15, 29 |
| `frontend/src/pages/Tagesplan.tsx` | Badges, „Ausgeliefert", „Gepackt", „Bereits gepackt", Neuladen | P1, P2 | 6, 7, 13 | — |
| `frontend/src/pages/Orders.tsx` | Filter, Einzel- und Sammelaktionen | P1 | 6, 8 | — |
| `frontend/src/components/domain/OrderCard.tsx` | „Gepackt" und „Geliefert" getrennt, Sperre | P1 | 8 | — |
| `frontend/src/pages/Sales.tsx` | Badge, Filter, Mutationen | P1 | 6, 8 | — |
| `frontend/src/components/domain/EditOrderModal.tsx` | Storno bei Gepackt, Neuladen | P1 | 8 | — |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | Belegstatus, Liefertag beim Quittieren, Hinweis statt Knopf | P1 | 6, 9 | **ja — stärkste Überschneidung** (Tasks 23, 24, 29) |
| `frontend/src/pages/Production.tsx` | Bezeichnungen; Verpackungsplan nennt Gepackte | P1, P2 | 6, 14 | — |
| `frontend/src/pages/Forecasting.tsx` | `SuggestionStatusBadge`, Warnungstypen | P1 | 6 | — |
| `frontend/src/pages/Invoices.tsx` | lexoffice-Status; Fallback im Detail | P1, P3 | 6, 18 | **ja** — Tasks 15, 19, 28, 29 |
| `frontend/src/pages/Dashboard.tsx` | „Offene Bestellungen" zählt Gepackte mit | P2 | 15 | **ja** — Task 28 (Z. 82, 336) |

## Überschneidungen mit Paket 1

Geprüft gegen `/tmp/paket1/plan-final.md` und den Branch `feat/paket1-steuer-rechnung` (`3cf51b1`, Tasks 1–7 committet). Aufgabennummern „Paket-1-Task n" beziehen sich auf `plan-final.md`; die Einzelabschnitte nannten sie S1–S6 (S1 = Tasks 1–7, S2 = 8–11, S3 = 12–15, S4 = 16–19, S6 = 20–24, S5 = 25–29).

1. **Test `test_quittierter_lieferschein_vertritt_die_bestellung` (wichtigster Punkt, ohne gemeinsame Zeile).** Paket-1-Task 22 legt ihn in `backend/tests/test_gernot_261008.py` an (`plan-final.md` Z. 5679-5689). Er quittiert eine ENTWURF-Bestellung und erwartet 200; nach Task 2 antwortet der Endpunkt 400 „Lieferschein nicht quittiert — Statuswechsel nicht möglich: Entwurf → Geliefert" (gewollt). Korrektur: Bestellung vorher bestätigen (Wortlaut in Task 2 Step 5); damit im Nachbau 21 passed. **Paket-1-Task 22 ist noch nicht ausgeführt:** Der Manager gibt dem Paket-1-Worker die Bestätigung jetzt mit (Entscheidung E5). Sonst zieht Task 2 Step 5 bzw. Task 23 Step 3 sie beim Merge nach. `test_bestellstatus_bleibt_und_lieferung_ist_weiter_moeglich` (Paket-1-Task 20) bestätigt schon vorher und bleibt grün.
2. **Paket-1-Runbook, Teil 3, R3** (`plan-final.md` ~Z. 8207-8218) gilt nach Paket 2 nicht mehr wörtlich: (a) Quittieren einer ENTWURF- oder STORNIERT-Bestellung gibt 400 — erst `POST /sales/orders/{id}/confirm`; (b) der Knopf „Quittieren" schickt nach Task 9 das Datum aus dem Feld „Liefertag" mit; (c) steht die Bestellung schon auf GELIEFERT ohne Lieferdatum, trägt das Quittieren es nach (`LIEFERDATUM_NACHGETRAGEN`), ohne zweiten Bestandsabzug; ein vorhandenes Lieferdatum wird nie überschrieben.
3. **`backend/app/api/v1/sales.py`.** Paket 2 ändert den Import aus `app.schemas.order` (Z. 25-30, Task 3), fügt nach Z. 33 den Import aus `app.services.order_status_service` ein (Task 1), ändert die Fehlertexte in `confirm_order` (Z. 1143), `delete_order` (Z. 1277), `add_order_line` (Z. 1313) (Task 5), ersetzt `update_order_status` (Z. 1174-1255, Task 1), `bulk_update_status` (Z. 1544-1585, Task 3) und `process_today_subscriptions` (Z. 582-588, Task 22). Paket-1-Task 1 (schon committet) ändert Z. 33 (Import `steuersatz_der_position`), Z. 852, Z. 1028, Z. 1322-1339 und Z. 1414-1440. **Sicherer Textkonflikt:** die Einfügung nach Z. 33 — beide Importzeilen behalten. Z. 1313 liegt vor dem Paket-1-Einschub nach Z. 1326 (eigener Hunk). `_create_audit_log` (Z. 647-666) bleibt unverändert.
4. **`backend/app/schemas/order.py`:** Paket 2 `OrderStatusUpdate` (Z. 167-170), `BulkStatusUpdate` (Z. 303-307), neue Klasse `BulkStatusResult`; Paket-1-Task 1 `OrderLineBase.tax_rate` (Z. 35). Getrennte Stellen.
5. **`backend/app/api/v1/documents.py`:** Paket 2 Z. 27 (Import `CurrentUser`), Service-Import nach Z. 39, `mark_delivered` (Z. 274-325); Paket-1-Task 23 nur `create_delivery_note` (Z. 185-226, Parameter `zusaetzlich`). Getrennte Hunks, im Nachbau konfliktfrei.
6. **`frontend/src/components/domain/OrderDocumentsModal.tsx` — stärkste Überschneidung:**

   | Stelle (Stand `efcea00`) | Paket 2 | Paket 1 | Merge |
   |---|---|---|---|
   | Z. 3 Icon-Import | — | Task 29: `Pencil` | kein Konflikt |
   | nach Z. 8 (`getErrorMessage`) | Task 6 `belegStatusLabel`, Task 9 `invalidateOrderViews` | Task 29: `import { InvoiceDetail } from '../../pages/Invoices'` | **Konflikt sicher** — alle drei Importzeilen behalten |
   | Z. 43-47 `invoicesQuery` | — | Task 24 (Filter `order_id`), Tasks 28/29 | kein Konflikt mit Paket 2 |
   | Z. 52/54 in `invalidate()` | Task 9 ersetzt Z. 54 (`['orders']` → `invalidateOrderViews`) | Task 29 entfernt Z. 52 (`order-invoices`) | Konflikt wahrscheinlich — Z. 52 entfällt, Z. 54 wird `void invalidateOrderViews(queryClient);` |
   | Z. 117-121 / Z. 123-128 | Task 9 ändert `markDeliveredMutation` (Z. 123-125) | Task 23 ersetzt `createDeliveryNote` (Z. 117-121), fügt `neuerLieferschein` an | Konflikt wahrscheinlich — beide Blöcke behalten |
   | nach Z. 130 (`signedByInput`) | Task 9 `lieferdatumInput` | Task 29 `offeneRechnung` | **Konflikt sicher** — beide `useState` behalten, beide vor `if (!order) return null;` |
   | Z. 132-136 | Task 9 ersetzt Z. 132, ergänzt `heute`, `vorschlagLieferdatum`, `quittierbar` | Task 24 ergänzt nach Z. 136 `ohneRechnungsrecht`, `aktiveRechnung`, `rechnungMoeglich` | Konflikt möglich — alles behalten |
   | Z. 171, 229 Belegstatus | Task 6 | — | kein Konflikt |
   | Z. 211-218 Knopf „Neuer LS" | — | Task 23 | kein Konflikt |
   | Z. 253-274 Quittieren-Zeile | Task 9 | — | kein Konflikt |
   | Z. 288-298 „Rechnung aus Bestellung" | — | Task 24 | kein Konflikt |
   | Z. 300-345 Rechnungs-`<li>`, darin Z. 305 | Task 6 nur Z. 305 (`{inv.status}` → `{belegStatusLabel(inv.status)}`) | Task 29 baut das `<li>` um | Konflikt möglich — danach `belegStatusLabel(inv.status)` wieder einsetzen |
7. **`frontend/src/pages/Invoices.tsx`:** Paket 2 Importzeile nach Z. 21 und Z. 128 (Task 6), Z. 1156 (Task 18). Paket 1: Tasks 15 (Z. 7-18, `stornoMutation` Z. 133-145), 19, 28 (Z. 41, 75-83, 227, 304), 29 (`InvoiceDetail` exportiert, Detail umgebaut). Zwischen den Hunks liegen unveränderte Zeilen; Z. 1156 kann mit Task 29 kollidieren — dann die eine Zeile `{invoice.customer_name || '–'}` neu setzen.
8. **`frontend/src/services/api.ts`:** Paket 2 Importzeile nach Z. 14, `DayPlanOrder` (Z. 137-147), `getPackagingPlan`/`getDayPlan` (Z. 228-246), `updateOrderStatus` (Z. 384-385) plus `bulkUpdateStatus`. Paket 1: `invoicesApi.list` (Z. 711-712, Tasks 24, 28), `invoicesApi.cancel` (~Z. 741, Task 15), `exportDatev`/`downloadDatev` (Z. 774-778, Task 19), `documentsApi.createDeliveryNote` (Z. 1385-1386, Task 23). Kein Konflikt erwartet; Task 9 nutzt `documentsApi.markDelivered` (Z. 1388) unverändert.
9. **`frontend/src/types/index.ts`:** Paket 2 `interface Order` (nach Z. 188, Task 9), `interface Invoice` Z. 621-622 (Task 18); Paket 1 `Invoice.original_invoice_id` (Task 15), `Customer.pfand_abrechnung`, `InvoiceLine.is_deposit` (Task 29). Task 18 und Paket-1-Task 15 ändern beide `interface Invoice` — bei Konflikt alle Felder behalten.
10. **`backend/app/api/v1/invoices.py`:** Paket 2 nur Z. 47 (Ladeoptionen) und `list_overdue_invoices` (Z. 71-77, Task 17). Paket-1-Task 24 ergänzt Signatur und `order_id`-Filter in `list_invoices`, Task 28 die Sortierung (Z. 64); Z. 47 schreibt Paket 1 nicht um. Schreibt Paket 1 sie doch um: dessen Optionen behalten, `joinedload(Invoice.customer)` ergänzen. Task 17 setzt voraus, dass `InvoiceService.check_overdue_invoices()` weiter eine Liste von `Invoice` liefert (Paket-1-Task 13 ändert dort nur das `.where`).
11. **`backend/app/models/invoice.py`:** Task 16 fügt zwei Properties zwischen `is_overdue` und `get_tax_summary` ein; Paket-1-Task 8 ändert `calculate_totals`/`get_tax_summary` und ergänzt `_cent`, `steuer_je_satz`, `steuerausweis_stimmt`. Nachbarschaft, Konflikt möglich — beides behalten.
12. **`backend/app/tasks/invoice_tasks.py`:** Task 20 löscht `generate_recurring_invoices` (Z. 191-289); Paket-1-Task 13 ändert Import Z. 12, `check_overdue_invoices` (~Z. 40-46) und `send_payment_reminders` (~Z. 106-114). Getrennte Hunks.
13. **`frontend/src/pages/Dashboard.tsx`:** Task 15 nur Z. 60-64 (Bestellabfrage); Paket-1-Task 28 Z. 82 und Z. 336 (Rechnungen). Getrennte Hunks.
14. **`backend/app/services/steuersatz.py`:** von Paket-1-Task 1 angelegt (Signatur am 08.10. auf dem Paket-1-Branch geprüft: `steuersatz_der_position(db, product_id, product_variant_id, client_satz) -> TaxRate`); Task 24 nutzt die Funktion erst nach dem Merge.
15. **Test `TestRechnungZeigtKunde::test_schreibende_endpunkte` (Task 16)** setzt die Storno-Antwort `{"invoice": …, "credit_note": …}` voraus und dass eine finalisierte Rechnung eine Stornorechnung bekommt. Paket 1 behält die Form (seine Tests lesen `["credit_note"]`) und verweigert die Stornorechnung nur für Entwürfe. Ändert sich das doch, nur die zwei Storno-Prüfungen am Testende anpassen.
16. **Semantisch, ohne gemeinsame Zeile:** Nach Paket 2 hat jede gelieferte Bestellung ein `actual_delivery_date`. Empfehlung an Paket 1: Leistungsdatum `note.actual_delivery_date or order.actual_delivery_date or order.requested_delivery_date` (heute `invoices.py:539`, `:667`, `invoice_service.py:189`). Setzt Paket 1 je FAKTURIERT, dann über `order_status_service.setze_status(db, order, OrderStatus.FAKTURIERT, user=..., action="INVOICE")`. Paket-1-Entscheidung (f) („kein automatisches FAKTURIERT") passt zu Paket 2: Quittieren einer FAKTURIERT-Bestellung trägt nach Task 2 nur das Lieferdatum nach.

Nicht von Paket 1 geändert: `production.py`, `forecasting.py`, `subscription_tasks.py`, `Tagesplan.tsx`, `Orders.tsx`, `OrderCard.tsx`, `Sales.tsx`, `EditOrderModal.tsx`, `Badge.tsx`, `components/ui/index.ts`, `Production.tsx`, `Forecasting.tsx`.

## Vorbereitung (vor Task 1)

- [ ] **Basis-Commit festhalten**

Run: `git rev-parse HEAD`
Erwartet: `efcea00f67dc93bb448c751b16d980a8fcaffc5e`. Den Hash im Bericht als `<Basis>` notieren und in Task 23 wörtlich einsetzen. Eine Shell-Variable reicht nicht, weil jeder Befehl in einer eigenen Shell läuft.

- [ ] **Ausgangszustand prüfen**

Run: `git status --porcelain`
Erwartet: genau `?? frontend/node_modules` (Symlink). Jede andere Zeile: stoppen und melden, nichts committen oder zurücksetzen.

Run: `test -e backend/tests/test_gernot_261008_paket2.py && echo vorhanden || echo fehlt`
Erwartet: `fehlt`.

---

## Abschnitt P1: A1 — Ausliefern im Tagesplan, eine Statusregel für alle Wege, Bezeichnungen statt Enum-Werten — Tasks 1–9

**Ziel:** Ein Klick auf „Ausgeliefert" im Tagesplan setzt die Bestellung auf GELIEFERT, die Zeile bleibt am Tag mit Badge „Geliefert" stehen, und alle drei Wege nach GELIEFERT (Status-Endpunkt, Lieferschein quittieren, Sammel-Endpunkt) folgen derselben Regel. Die Oberfläche zeigt nirgends mehr Enum-Werte, IN_PRODUKTION heißt „Gepackt", Sammelaktionen melden ehrlich, was sie getan haben.

**Verifizierter Ausgangsbefund (gemessen am 08.10.2026 an `efcea00`, In-Memory-Testdatenbank):**

| Vorgang | Ergebnis heute |
|---|---|
| `POST /sales/orders/{id}/status` BESTAETIGT → GELIEFERT | 400 „Ungültiger Statusübergang: BESTAETIGT → GELIEFERT" |
| IN_PRODUKTION → STORNIERT | 400 |
| IN_PRODUKTION → GELIEFERT | 200, aber `actual_delivery_date` bleibt `null` |
| Tagesplan nach GELIEFERT | Bestellung fehlt in `ausliefern` (Filter `production.py:523`) |
| `POST /sales/orders/bulk-status` | Exception `ValidationError for OrderSummary` (6 Pflichtfelder fehlen), nichts gespeichert — der Endpunkt ist mit jedem Aufruf kaputt |
| `PATCH /sales/delivery-notes/{id}/mark-delivered` bei ENTWURF-Bestellung | 200, Bestellung springt auf GELIEFERT, **kein** Audit-Log-Eintrag |
| `day-plan`/`packaging-plan` Feld `status` | „Entwurf" übersetzt, alles andere roh (`BESTAETIGT`, `IN_PRODUKTION`) |

Dazu (A1.md): Die Sammelaktion „Geliefert" (`Orders.tsx:142-155`) filterte still auf IN_PRODUKTION und meldete trotzdem Erfolg; `handleBulkReady` ebenso. Keine Statusänderung invalidierte `['day-plan']`, global gilt `staleTime` 60 s und `refetchOnWindowFocus: false` (`main.tsx:26-28`).

**Review Focus (P1, getestet):**
1. **Atomar:** Scheitert der Bestandsabzug, bleiben Status, Lieferdatum und Audit-Log unverändert, beim Quittieren auch der Lieferschein (Tasks 1, 2, 3).
2. **Kein doppelter Abzug:** Quittieren einer schon gelieferten Bestellung trägt nur das Datum nach (Task 2).
3. **ENTWURF → GELIEFERT** ist auf allen drei Wegen gesperrt (Tasks 1, 2, 3).
4. **Same-Day-Bestellungen** stehen weiter in „Verpacken" und „Ausliefern" (`tests/test_gernot_260817.py:187-206` bleibt unverändert grün, Task 4).
5. **Bestand erst bei Geliefert:** Packen und Stornieren nach „Gepackt" buchen nichts (Task 1, `test_storno_nach_gepackt_bucht_keinen_bestand`).

---

### Task 1: Eine Statusregel — Service und Status-Endpunkt

**Files:**
- Create: `backend/app/services/order_status_service.py`
- Modify: `backend/app/api/v1/sales.py:25-33` (Importe), `:1174-1255` (`update_order_status`)
- Modify: `backend/app/schemas/order.py:167-170` (`OrderStatusUpdate`)
- Create: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Produces:
  - `ERLAUBTE_UEBERGAENGE: dict[OrderStatus, tuple[OrderStatus, ...]]`
  - `STATUS_BEZEICHNUNG: dict[OrderStatus, str]`, `bezeichnung(status: OrderStatus) -> str`
  - `class StatuswechselFehler(Exception)` (→ 400), `class BestandsbuchungFehler(Exception)` (→ 500 + Rollback)
  - `heute_berlin() -> date`, `user_uuid(user: Optional[dict]) -> Optional[UUID]`. Hinweis: `backend/app/api/v1/imports.py:42-43` hat bereits `_today_berlin()` mit demselben Inhalt, privat im API-Modul. Der Service bekommt bewusst eine eigene öffentliche Funktion (ein Service importiert nicht aus `api/`), `imports.py` bleibt unverändert (Hotfix `efcea00`). Zusammenlegen ist ein späterer Aufräumschritt.
  - `pruefe_uebergang(alt: OrderStatus, neu: OrderStatus) -> None`
  - `setze_status(db, order, neu, *, user, action="STATUS_CHANGE", reason=None, lieferdatum=None) -> None` — committet nicht
  - `OrderStatusUpdate.actual_delivery_date: Optional[date]`
  - Test-Helfer in `test_gernot_261008_paket2.py`: `_heute`, `_kunde`, `_bestellung`, `_bestaetigt`, `_gepackt`, `_status`, `_lesen`, `_audit`, `_plan`, `_lieferschein`, `_quittieren`, `_produkt`, `_fertigware`, `_bestand`, `_grammzeile`. P2-P4 dürfen sie wiederverwenden.

- [ ] **Step 1: Testdatei mit Helfern und den Tests dieser Task anlegen**

Task 1 legt `backend/tests/test_gernot_261008_paket2.py` an; alle späteren Tasks hängen ihre Blöcke ans Dateiende. Existiert die Datei schon (Vorbereitung erwartet `fehlt`), stoppen und melden.

```python
"""Gernot-Feedback vom 07./08.10.2026 — Paket 2: Tagesplan und Status.

A1: "Ausgeliefert" wurde nicht angezeigt. Drei Wege nach GELIEFERT mit drei
    verschiedenen Regeln (Status-Endpunkt ohne Lieferdatum, Lieferschein-
    Quittieren ohne Übergangsregel und Audit-Log, Sammel-Endpunkt ohne
    alles); der Tagesplan zeigte rohe Enum-Werte und GELIEFERT gar nicht.
A4: Gepackte Bestellungen zählten weiter in "Verpacken" und im Sortenbedarf
    (Block "P2 / A4", Helfer _a4_).
A2: Die Spalte "Kunde" der Rechnungsliste blieb leer (Block "P3 / A2",
    Helfer _a2_).
A5: Abo-Bestellungen ohne Produkt, Preis und Satz; mehrere Liefertage
    wirkten nicht (Block "P4", Helfer _p4_).
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal

TEST_USER_ID = "123e4567-e89b-12d3-a456-426614174000"  # aus conftest.client


@pytest.fixture(autouse=True)
def _ohne_prognose_anstoss(monkeypatch):
    """Bestätigen und Stornieren stoßen per Celery eine Prognose an. Ohne Redis
    hängt jeder Aufruf in Verbindungsversuchen — für diese Tests ohne Belang."""
    monkeypatch.setattr("app.api.v1.sales._trigger_forecast_update", lambda *a, **k: None)


# ---------------------------------------------------------------- Helfer

def _heute():
    """Liefertag laut Server (Europe/Berlin). date.today() wäre auf einem
    UTC-Rechner zwischen 22 und 24 Uhr UTC noch der Vortag."""
    from app.services.order_status_service import heute_berlin
    return heute_berlin()


def _kunde(client, name="Ökoring"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL"})
    assert r.status_code == 201, r.text
    return r.json()


def _bestellung(client, kunde, liefertag=None, lines=None):
    """Bestellung im Status ENTWURF."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (liefertag or date.today()).isoformat(),
        "lines": lines or [{"product_name": "Erbsen-Schale", "quantity": 2, "unit": "STK",
                            "unit_price": 3.0, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _bestaetigt(client, kunde, liefertag=None, lines=None):
    o = _bestellung(client, kunde, liefertag, lines)
    r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _gepackt(client, kunde, liefertag=None, lines=None):
    o = _bestaetigt(client, kunde, liefertag, lines)
    r = _status(client, o, "IN_PRODUKTION")
    assert r.status_code == 200, r.text
    return r.json()


def _status(client, order, status, **extra):
    return client.post(f"/api/v1/sales/orders/{order['id']}/status",
                       json={"status": status, **extra})


def _lesen(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _audit(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
    assert r.status_code == 200, r.text
    return r.json()  # neuester Eintrag zuerst


def _plan(client, tag=None):
    r = client.get("/api/v1/production/day-plan",
                   params={"target_date": (tag or date.today()).isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _lieferschein(client, order):
    r = client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return r.json()


def _quittieren(client, note, **body):
    return client.patch(f"/api/v1/sales/delivery-notes/{note['id']}/mark-delivered", json=body)


def _produkt(client, name="Erbse", sku="MG-ERB-261008"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": "3.00",
        "category": "MICROGREEN", "base_unit_id": unit_id,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _fertigware(produkt, gramm):
    """Fertigwarenbestand direkt über das ORM — es gibt keinen schlanken API-Weg."""
    from app.models.inventory import FinishedGoodsInventory
    with TestingSessionLocal() as db:
        inv = FinishedGoodsInventory(
            product_id=uuid.UUID(produkt["id"]), batch_number="FW-261008",
            initial_quantity_g=Decimal(gramm), current_quantity_g=Decimal(gramm),
            harvest_date=date.today(), best_before_date=date.today() + timedelta(days=7),
        )
        db.add(inv)
        db.commit()
        return str(inv.id)


def _bestand(inventory_id):
    from app.models.inventory import FinishedGoodsInventory
    with TestingSessionLocal() as db:
        return db.get(FinishedGoodsInventory, uuid.UUID(inventory_id)).current_quantity_g


def _grammzeile(produkt, gramm=100):
    return [{"product_id": produkt["id"], "product_name": produkt["name"], "quantity": gramm,
             "unit": "g", "unit_price": 0.05, "tax_rate": "REDUZIERT"}]


# ------------------------------------------- Task 1: eine Statusregel

class TestStatusregel:
    """A1: BESTAETIGT → GELIEFERT fehlte, gepackt ließ sich nicht stornieren."""

    def test_uebergangstabelle(self):
        from app.models.order import OrderStatus as S
        from app.services.order_status_service import ERLAUBTE_UEBERGAENGE
        assert ERLAUBTE_UEBERGAENGE == {
            S.ENTWURF: (S.BESTAETIGT, S.STORNIERT),
            S.BESTAETIGT: (S.IN_PRODUKTION, S.GELIEFERT, S.STORNIERT),
            S.IN_PRODUKTION: (S.GELIEFERT, S.STORNIERT),
            S.GELIEFERT: (S.FAKTURIERT,),
            S.FAKTURIERT: (),
            S.STORNIERT: (),
        }

    def test_bestaetigt_direkt_ausgeliefert(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "GELIEFERT")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "GELIEFERT"
        assert r.json()["actual_delivery_date"] == _heute().isoformat()

    def test_gepackt_darf_storniert_werden(self, client):
        o = _gepackt(client, _kunde(client))
        r = _status(client, o, "STORNIERT", reason="Kunde hat abgesagt")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "STORNIERT"

    def test_entwurf_nicht_direkt_geliefert(self, client):
        o = _bestellung(client, _kunde(client))
        r = _status(client, o, "GELIEFERT")
        assert r.status_code == 400
        assert r.json()["detail"] == "Statuswechsel nicht möglich: Entwurf → Geliefert"
        assert _lesen(client, o)["status"] == "ENTWURF"

    def test_fehlertext_ohne_enum_wert(self, client):
        o = _gepackt(client, _kunde(client))
        r = _status(client, o, "FAKTURIERT")
        assert r.status_code == 400
        assert r.json()["detail"] == "Statuswechsel nicht möglich: Gepackt → Fakturiert"

    def test_geliefert_bucht_bestand(self, client):
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        o = _bestaetigt(client, _kunde(client), lines=_grammzeile(produkt, 100))
        assert _status(client, o, "GELIEFERT").status_code == 200
        assert _bestand(lager) == Decimal("900")

    def test_audit_log_mit_lieferdatum_und_nutzer(self, client):
        o = _bestaetigt(client, _kunde(client))
        _status(client, o, "GELIEFERT")
        eintrag = _audit(client, o)[0]
        assert eintrag["action"] == "STATUS_CHANGE"
        assert eintrag["old_values"]["status"] == "BESTAETIGT"
        assert eintrag["new_values"] == {"status": "GELIEFERT",
                                         "actual_delivery_date": _heute().isoformat()}
        assert eintrag["user_id"] == TEST_USER_ID
        assert eintrag["user_name"] == "testuser"

    def test_lieferdatum_nachtragen(self, client):
        gestern = date.today() - timedelta(days=1)
        o = _bestaetigt(client, _kunde(client), liefertag=gestern)
        r = _status(client, o, "GELIEFERT", actual_delivery_date=gestern.isoformat())
        assert r.status_code == 200, r.text
        assert r.json()["actual_delivery_date"] == gestern.isoformat()

    def test_lieferdatum_in_der_zukunft_abgelehnt(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "GELIEFERT",
                    actual_delivery_date=(date.today() + timedelta(days=2)).isoformat())
        assert r.status_code == 400
        assert "Zukunft" in r.json()["detail"]
        assert _lesen(client, o)["status"] == "BESTAETIGT"

    def test_lieferdatum_nur_beim_liefern(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "IN_PRODUKTION", actual_delivery_date=_heute().isoformat())
        assert r.status_code == 400

    def test_bestandsfehler_rollt_alles_zurueck(self, client, monkeypatch):
        """Status, Lieferdatum und Audit-Log nur zusammen mit dem Bestandsabzug."""
        def kaputt(*a, **k):
            raise RuntimeError("Lager gesperrt")
        monkeypatch.setattr("app.services.order_status_service.deduct_inventory_for_order", kaputt)
        o = _bestaetigt(client, _kunde(client))
        r = _status(client, o, "GELIEFERT")
        assert r.status_code == 500
        assert "Lager gesperrt" in r.json()["detail"]
        bestellung = _lesen(client, o)
        assert bestellung["status"] == "BESTAETIGT"
        assert bestellung["actual_delivery_date"] is None
        assert _audit(client, o)[0]["action"] == "CONFIRM"

    def test_geliefert_nicht_stornierbar(self, client):
        """Charakterisierung — schon vorher so, bleibt so (Bestand ist gebucht)."""
        o = _gepackt(client, _kunde(client))
        assert _status(client, o, "GELIEFERT").status_code == 200
        assert _status(client, o, "STORNIERT").status_code == 400

    def test_storno_nach_gepackt_bucht_keinen_bestand(self, client):
        """Bestand wird erst bei GELIEFERT gebucht: Packen und Stornieren
        lassen ihn unverändert (Entscheidung 08.10.2026)."""
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        o = _gepackt(client, _kunde(client), lines=_grammzeile(produkt, 100))
        assert _bestand(lager) == Decimal("1000")
        assert _status(client, o, "STORNIERT", reason="Kunde hat abgesagt").status_code == 200
        assert _bestand(lager) == Decimal("1000")
```

Am Code geprüft: Bestellungen buchen Fertigware nur über `deduct_inventory_for_order` (`order_fulfillment_service.py:122`, heute aufgerufen in `sales.py:1238` und `documents.py:312`, beide nur beim Wechsel nach GELIEFERT). `reserve_for_order` (`inventory_service.py:229`) ruft niemand auf, `ship_goods` nur der manuelle Endpunkt `POST /inventory/finished-goods/ship` (`api/v1/inventory.py:423`). Der neue Test schreibt das für „Gepackt → Storniert" fest.

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v`
Erwartet: **12 failed, 1 passed.** Grün ist nur `test_geliefert_nicht_stornierbar` (Charakterisierung, war schon so). `test_uebergangstabelle` scheitert mit `ModuleNotFoundError: app.services.order_status_service`, `test_bestandsfehler_rollt_alles_zurueck` am `monkeypatch` auf dasselbe Modul, `test_storno_nach_gepackt_bucht_keinen_bestand` und die übrigen an 400 „Ungültiger Statusübergang: …" bzw. am fehlenden Lieferdatum.

- [ ] **Step 3: Service anlegen**

Neue Datei `backend/app/services/order_status_service.py`:

```python
"""Statuswechsel einer Bestellung — eine Regel für alle Wege.

Bis Oktober 2026 führten drei Wege nach GELIEFERT, jeder mit eigenen Regeln:
- POST /sales/orders/{id}/status prüfte die Übergänge, setzte aber kein
  Lieferdatum,
- PATCH /sales/delivery-notes/{id}/mark-delivered setzte das Lieferdatum,
  umging aber die Übergangsregel (sogar aus ENTWURF) und schrieb kein
  Audit-Log,
- POST /sales/orders/bulk-status prüfte gar nichts, buchte keinen Bestand und
  scheiterte am Ende an seinem eigenen Antwortschema.

Alle drei rufen jetzt `setze_status`. Die Funktion committet nicht — der
Aufrufer committet Status, Lieferdatum, Audit-Log und Bestandsbuchung in
einer Transaktion oder rollt alles zurück.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.order import Order, OrderAuditLog, OrderStatus
from app.services.order_fulfillment_service import deduct_inventory_for_order


# IN_PRODUKTION heißt in der Oberfläche "Gepackt" (Entscheidung 08.10.2026).
# Gepackt, aber nicht geliefert, darf storniert werden: Bestand wird erst
# beim Übergang nach GELIEFERT gebucht. Direkt aus ENTWURF nach GELIEFERT
# geht nicht — erst bestätigen.
ERLAUBTE_UEBERGAENGE: dict[OrderStatus, tuple[OrderStatus, ...]] = {
    OrderStatus.ENTWURF: (OrderStatus.BESTAETIGT, OrderStatus.STORNIERT),
    OrderStatus.BESTAETIGT: (OrderStatus.IN_PRODUKTION, OrderStatus.GELIEFERT, OrderStatus.STORNIERT),
    OrderStatus.IN_PRODUKTION: (OrderStatus.GELIEFERT, OrderStatus.STORNIERT),
    OrderStatus.GELIEFERT: (OrderStatus.FAKTURIERT,),
    OrderStatus.FAKTURIERT: (),
    OrderStatus.STORNIERT: (),
}

# Gleiche Wörter wie frontend/src/components/ui/statusLabels.ts — Fehlertexte
# landen als Toast beim Anwender und dürfen keine Enum-Werte zeigen.
STATUS_BEZEICHNUNG: dict[OrderStatus, str] = {
    OrderStatus.ENTWURF: "Entwurf",
    OrderStatus.BESTAETIGT: "Bestätigt",
    OrderStatus.IN_PRODUKTION: "Gepackt",
    OrderStatus.GELIEFERT: "Geliefert",
    OrderStatus.FAKTURIERT: "Fakturiert",
    OrderStatus.STORNIERT: "Storniert",
}


class StatuswechselFehler(Exception):
    """Fachlich unzulässig — der Aufrufer antwortet mit 400."""


class BestandsbuchungFehler(Exception):
    """Bestandsabzug beim Übergang nach GELIEFERT gescheitert — Rollback, 500."""


def heute_berlin() -> date:
    """Kalendertag in München. Der Server läuft in UTC; zwischen 0 und 2 Uhr
    wäre date.today() noch der Vortag."""
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def bezeichnung(status: OrderStatus) -> str:
    return STATUS_BEZEICHNUNG.get(status, status.value)


def pruefe_uebergang(alt: OrderStatus, neu: OrderStatus) -> None:
    if neu not in ERLAUBTE_UEBERGAENGE.get(alt, ()):
        raise StatuswechselFehler(
            f"Statuswechsel nicht möglich: {bezeichnung(alt)} → {bezeichnung(neu)}"
        )


def user_uuid(user: Optional[dict]) -> Optional[UUID]:
    """Keycloak liefert eine UUID; Basic-Auth-Nutzer heißen 'basic-auth:<name>'."""
    try:
        return UUID(str(user["id"])) if user and user.get("id") else None
    except ValueError:
        return None


def setze_status(
    db: Session,
    order: Order,
    neu: OrderStatus,
    *,
    user: Optional[dict],
    action: str = "STATUS_CHANGE",
    reason: Optional[str] = None,
    lieferdatum: Optional[date] = None,
) -> None:
    """Prüft den Übergang und setzt den Status — committet NICHT.

    Beim Übergang nach GELIEFERT zusätzlich: tatsächliches Lieferdatum
    (Standard heute, nie in der Zukunft) und Bestandsabzug in derselben
    Transaktion. Jeder Wechsel schreibt genau einen Audit-Log-Eintrag.
    """
    alt = order.status
    pruefe_uebergang(alt, neu)

    if lieferdatum is not None and neu != OrderStatus.GELIEFERT:
        raise StatuswechselFehler("Ein Lieferdatum gibt es nur beim Wechsel auf Geliefert")

    alte_werte: dict = {"status": alt.value}
    neue_werte: dict = {"status": neu.value}

    if neu == OrderStatus.GELIEFERT:
        tag = lieferdatum or heute_berlin()
        if tag > heute_berlin():
            raise StatuswechselFehler(f"Lieferdatum {tag:%d.%m.%Y} liegt in der Zukunft")
        alte_werte["actual_delivery_date"] = (
            order.actual_delivery_date.isoformat() if order.actual_delivery_date else None
        )
        neue_werte["actual_delivery_date"] = tag.isoformat()
        order.actual_delivery_date = tag

    user_id = user_uuid(user)
    order.status = neu
    order.updated_by = user_id
    order.updated_at = datetime.now(timezone.utc)
    db.add(OrderAuditLog(
        order_id=order.id,
        user_id=user_id,
        user_name=(user or {}).get("username"),
        action=action,
        old_values=alte_werte,
        new_values=neue_werte,
        reason=reason,
    ))

    if neu == OrderStatus.GELIEFERT:
        try:
            deduct_inventory_for_order(db, order, commit=False)
        except Exception as e:  # noqa: BLE001 — jeder Fehler muss zum Rollback führen
            raise BestandsbuchungFehler(str(e)) from e
```

- [ ] **Step 4: Schema erweitern**

In `backend/app/schemas/order.py`, Klasse `OrderStatusUpdate` (Z. 167-170), ersetzen durch:

```python
class OrderStatusUpdate(BaseModel):
    """Schema für Statusänderung"""
    status: OrderStatus
    reason: Optional[str] = Field(None, description="Grund für Statusänderung")
    actual_delivery_date: Optional[date] = Field(
        None, description="Nur bei GELIEFERT: tatsächlicher Liefertag (Standard heute, nie in der Zukunft)"
    )
```

`date` ist in der Datei bereits importiert (Z. 5).

- [ ] **Step 5: Status-Endpunkt anbinden**

In `backend/app/api/v1/sales.py` nach der Zeile `from app.services.datev_service import DatevService` (Z. 33) einfügen:

```python
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, bezeichnung, pruefe_uebergang, setze_status,
)
```

(`bezeichnung` und `pruefe_uebergang` werden erst in Tasks 3 und 5 benutzt; der Import steht trotzdem jetzt, damit der Block nur einmal angefasst wird.)

Die komplette Funktion `update_order_status` — vom Dekorator `@router.post("/orders/{order_id}/status", response_model=OrderResponse)` (Z. 1174) bis einschließlich `return await get_order(order_id, db)` vor `@router.delete("/orders/{order_id}", …)` (Z. 1255) — ersetzen durch:

```python
@router.post("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    status_update: OrderStatusUpdate,
    db: DBSession,
    user: CurrentUser
):
    """
    Bestellstatus aktualisieren.

    Regeln: app.services.order_status_service.ERLAUBTE_UEBERGAENGE.
    Beim Wechsel auf GELIEFERT: Lieferdatum (Standard heute) + Bestandsabzug.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    neu = status_update.status
    try:
        setze_status(
            db, order, neu,
            user=user,
            reason=status_update.reason,
            lieferdatum=status_update.actual_delivery_date,
        )
    except StatuswechselFehler as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except BestandsbuchungFehler as e:
        db.rollback()
        logger.exception("Bestandsabzug beim Statuswechsel fehlgeschlagen: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Statuswechsel abgebrochen — Bestandsabzug fehlgeschlagen: {e}",
        )

    db.commit()

    # Forecast bei Stornierung triggern
    if neu == OrderStatus.STORNIERT:
        _trigger_forecast_update(str(order.id), "CANCEL")

    return await get_order(order_id, db)
```

Die frühere lokale Tabelle `valid_transitions` und der Inline-Import von `deduct_inventory_for_order` entfallen; beides steckt jetzt im Service.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v`
Erwartet: 13 passed.

Zusätzlich die bestehenden Status-Tests: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_bugfixes.py tests/test_gernot_260817.py tests/test_features.py -q`
Erwartet: keine neuen Fehlschläge gegenüber der Baseline (in `test_features.py` ist `TestFeatures::test_subscription_processing` Altlast).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/order_status_service.py backend/app/api/v1/sales.py backend/app/schemas/order.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(status): eine Übergangsregel für Bestellungen — Bestätigt→Geliefert, Gepackt stornierbar, Lieferdatum und Audit"
```

---

### Task 2: Lieferschein quittieren über dieselbe Regel, Lieferdatum nachtragen

**Files:**
- Modify: `backend/app/services/order_status_service.py` (neue Funktion `trage_lieferdatum_nach`)
- Modify: `backend/app/api/v1/documents.py:27` (Import), `:39` (Service-Import), `:274-325` (`mark_delivered`)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: `setze_status`, `heute_berlin`, `StatuswechselFehler`, `BestandsbuchungFehler`, `user_uuid` aus Task 1; Helfer aus Task 1.
- Produces: `trage_lieferdatum_nach(db, order, tag, *, user, reason=None) -> bool` (überschreibt nie ein vorhandenes Datum, committet nicht). Audit-Aktionen `LIEFERSCHEIN_QUITTIERT` und `LIEFERDATUM_NACHGETRAGEN`.

Verhalten nach dieser Task:

| Bestellstatus beim Quittieren | Ergebnis |
|---|---|
| BESTAETIGT, IN_PRODUKTION | Lieferschein quittiert, Bestellung → GELIEFERT über `setze_status` (Lieferdatum = gewähltes Datum, Bestandsabzug, Audit `LIEFERSCHEIN_QUITTIERT`) |
| ENTWURF, STORNIERT | 400, nichts geändert (Lieferschein bleibt offen) |
| GELIEFERT, FAKTURIERT | Lieferschein quittiert; fehlt der Bestellung das Lieferdatum, wird es nachgetragen (Audit `LIEFERDATUM_NACHGETRAGEN`), kein zweiter Bestandsabzug |
| Lieferdatum in der Zukunft | 400, nichts geändert |

- [ ] **Step 1: Failing Tests anhängen**

```python
# ------------------------- Task 2: Lieferschein quittieren, gleiche Regel

class TestLieferscheinQuittieren:
    """A1/LÜCKEN 4: Quittieren umging Übergangsregel und Audit-Log; das
    Lieferdatum war immer 'heute', auch beim Nachtragen."""

    def test_quittieren_liefert_mit_audit_log(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, signed_by="Fr. Huber")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "GELIEFERT"

        bestellung = _lesen(client, o)
        assert bestellung["status"] == "GELIEFERT"
        assert bestellung["actual_delivery_date"] == _heute().isoformat()
        eintrag = _audit(client, o)[0]
        assert eintrag["action"] == "LIEFERSCHEIN_QUITTIERT"
        assert eintrag["new_values"]["status"] == "GELIEFERT"
        assert ls["delivery_note_number"] in eintrag["reason"]
        assert eintrag["user_id"] == TEST_USER_ID

    def test_entwurf_kann_nicht_quittiert_werden(self, client):
        o = _bestellung(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, signed_by="X")
        assert r.status_code == 400
        assert "Entwurf → Geliefert" in r.json()["detail"]
        assert _lesen(client, o)["status"] == "ENTWURF"
        noten = client.get(f"/api/v1/sales/orders/{o['id']}/delivery-notes").json()
        assert noten[0]["status"] == "ENTWURF"

    def test_stornierte_bestellung_kann_nicht_quittiert_werden(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        assert _status(client, o, "STORNIERT").status_code == 200
        assert _quittieren(client, ls).status_code == 400

    def test_lieferdatum_waehlbar(self, client):
        gestern = date.today() - timedelta(days=1)
        o = _bestaetigt(client, _kunde(client), liefertag=gestern)
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, actual_delivery_date=gestern.isoformat())
        assert r.status_code == 200, r.text
        assert r.json()["actual_delivery_date"] == gestern.isoformat()
        assert _lesen(client, o)["actual_delivery_date"] == gestern.isoformat()

    def test_lieferdatum_in_der_zukunft_abgelehnt(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, actual_delivery_date=(date.today() + timedelta(days=2)).isoformat())
        assert r.status_code == 400
        assert _lesen(client, o)["status"] == "BESTAETIGT"

    def test_quittieren_bucht_bestand(self, client):
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        o = _bestaetigt(client, _kunde(client), lines=_grammzeile(produkt, 100))
        assert _quittieren(client, _lieferschein(client, o)).status_code == 200
        assert _bestand(lager) == Decimal("900")

    def test_altfall_lieferdatum_nachtragen_ohne_zweite_buchung(self, client):
        """Gernots fünf Bestellungen: per Status-Endpunkt geliefert, ohne Lieferdatum,
        Lieferschein noch offen. Nachträgliches Quittieren trägt das echte Datum nach."""
        from app.models.order import Order
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        gestern = date.today() - timedelta(days=1)
        o = _bestaetigt(client, _kunde(client), liefertag=gestern, lines=_grammzeile(produkt, 100))
        ls = _lieferschein(client, o)
        assert _status(client, o, "GELIEFERT").status_code == 200
        with TestingSessionLocal() as db:  # Zustand vor dem Fix nachstellen
            db.get(Order, uuid.UUID(o["id"])).actual_delivery_date = None
            db.commit()

        r = _quittieren(client, ls, signed_by="Fahrer", actual_delivery_date=gestern.isoformat())
        assert r.status_code == 200, r.text
        bestellung = _lesen(client, o)
        assert bestellung["status"] == "GELIEFERT"
        assert bestellung["actual_delivery_date"] == gestern.isoformat()
        assert _bestand(lager) == Decimal("900"), "Bestand darf nicht zweimal gebucht werden"
        assert _audit(client, o)[0]["action"] == "LIEFERDATUM_NACHGETRAGEN"

    def test_vorhandenes_lieferdatum_wird_nicht_ueberschrieben(self, client):
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        assert _status(client, o, "GELIEFERT").status_code == 200
        gestern = date.today() - timedelta(days=1)
        assert _quittieren(client, ls, actual_delivery_date=gestern.isoformat()).status_code == 200
        assert _lesen(client, o)["actual_delivery_date"] == _heute().isoformat()

    def test_bestandsfehler_laesst_lieferschein_offen(self, client, monkeypatch):
        """Gegenstück zu test_bestandsfehler_rollt_alles_zurueck: scheitert der
        Bestandsabzug, bleiben Lieferschein und Bestellung unverändert."""
        def kaputt(*a, **k):
            raise RuntimeError("Lager gesperrt")
        monkeypatch.setattr("app.services.order_status_service.deduct_inventory_for_order", kaputt)
        o = _bestaetigt(client, _kunde(client))
        ls = _lieferschein(client, o)
        r = _quittieren(client, ls, signed_by="Fahrer")
        assert r.status_code == 500
        assert "Lager gesperrt" in r.json()["detail"]
        assert _lesen(client, o)["status"] == "BESTAETIGT"
        assert _lesen(client, o)["actual_delivery_date"] is None
        noten = client.get(f"/api/v1/sales/orders/{o['id']}/delivery-notes").json()
        assert (noten[0]["status"], noten[0]["signed_by"]) == ("ENTWURF", None)
        assert _audit(client, o)[0]["action"] == "CONFIRM"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestLieferscheinQuittieren -v`
Erwartet: **6 failed, 3 passed.** Grün sind die Charakterisierungen `test_lieferdatum_waehlbar` und `test_quittieren_bucht_bestand` (konnte der Endpunkt schon) sowie `test_vorhandenes_lieferdatum_wird_nicht_ueberschrieben` (seit Task 1 grün, sichert die Regel „nie überschreiben" ab). `test_bestandsfehler_laesst_lieferschein_offen` scheitert an `assert 200 == 500`: Der alte `mark_delivered` bucht über seinen eigenen Import, der `monkeypatch` auf den Service greift dort noch nicht.

- [ ] **Step 3: Nachtrag-Funktion im Service**

An `backend/app/services/order_status_service.py` anhängen:

```python


def trage_lieferdatum_nach(
    db: Session,
    order: Order,
    tag: date,
    *,
    user: Optional[dict],
    reason: Optional[str] = None,
) -> bool:
    """Lieferdatum einer schon gelieferten Bestellung nachtragen — nur wenn es
    fehlt (Altfälle: Status-Endpunkt setzte es vor Oktober 2026 nicht).
    Ein vorhandenes Datum wird nie überschrieben. Committet NICHT."""
    if order.actual_delivery_date:
        return False
    order.actual_delivery_date = tag
    db.add(OrderAuditLog(
        order_id=order.id,
        user_id=user_uuid(user),
        user_name=(user or {}).get("username"),
        action="LIEFERDATUM_NACHGETRAGEN",
        old_values={"actual_delivery_date": None},
        new_values={"actual_delivery_date": tag.isoformat()},
        reason=reason,
    ))
    return True
```

- [ ] **Step 4: `mark_delivered` umbauen**

In `backend/app/api/v1/documents.py` Z. 27-28:

```python
from app.api.deps import DBSession, CurrentUser
from app.models.order import Order, OrderStatus
```

Nach `from app.services.email_service import send_email, EmailNotConfiguredError` (Z. 39) einfügen:

```python
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, heute_berlin, setze_status, trage_lieferdatum_nach,
)
```

Die komplette Funktion `mark_delivered` — vom Dekorator `@router.patch(\n    "/delivery-notes/{note_id}/mark-delivered",` (Z. 274) bis einschließlich `return note` vor `@router.get("/delivery-notes/{note_id}/pdf")` (Z. 325) — ersetzen durch:

```python
@router.patch(
    "/delivery-notes/{note_id}/mark-delivered",
    response_model=DeliveryNoteResponse,
)
def mark_delivered(note_id: UUID, data: DeliveryNoteMarkDelivered, db: DBSession, user: CurrentUser):
    """Lieferschein quittieren.

    Steht die Bestellung noch vor GELIEFERT, wechselt sie über dieselbe Regel
    wie der Status-Endpunkt (order_status_service.setze_status): Übergang
    geprüft, Lieferdatum, Bestandsabzug, Audit-Log. Ist sie schon geliefert
    und fehlt ihr das Lieferdatum (Altfälle vor Oktober 2026), wird es aus
    dem Lieferschein nachgetragen.
    """
    note = db.execute(
        select(DeliveryNote)
        .options(joinedload(DeliveryNote.order))
        .where(DeliveryNote.id == note_id)
    ).unique().scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Lieferschein nicht gefunden")
    if note.is_locked():
        raise HTTPException(status_code=400, detail="Lieferschein ist bereits quittiert")

    lieferdatum = data.actual_delivery_date or heute_berlin()
    if lieferdatum > heute_berlin():
        raise HTTPException(
            status_code=400,
            detail=f"Lieferdatum {lieferdatum:%d.%m.%Y} liegt in der Zukunft",
        )

    note.status = DeliveryNoteStatus.GELIEFERT
    note.delivered_at = datetime.now(timezone.utc)
    note.signed_by = data.signed_by
    note.actual_delivery_date = lieferdatum

    order = note.order
    grund = f"Lieferschein {note.delivery_note_number} quittiert"
    if order and order.status in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT):
        trage_lieferdatum_nach(db, order, lieferdatum, user=user, reason=grund)
    elif order:
        try:
            setze_status(
                db, order, OrderStatus.GELIEFERT,
                user=user,
                action="LIEFERSCHEIN_QUITTIERT",
                reason=grund,
                lieferdatum=lieferdatum,
            )
        except StatuswechselFehler as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Lieferschein nicht quittiert — {e}")
        except BestandsbuchungFehler as e:
            db.rollback()
            import logging; logging.getLogger(__name__).exception(
                "Bestandsabzug nach LS-Quittierung fehlgeschlagen: %s", e
            )
            raise HTTPException(
                status_code=500,
                detail=f"Quittierung abgebrochen — Bestandsabzug fehlgeschlagen: {e}",
            )

    db.commit()
    db.refresh(note)
    return note
```

`_load_order_with_lines` und der Import von `date` bleiben (werden anderswo in der Datei benutzt).

- [ ] **Step 5: Paket-1-Test angleichen (nur falls Paket 1 schon auf dem Branch ist)**

Run: `grep -n "def test_quittierter_lieferschein_vertritt_die_bestellung" backend/tests/test_gernot_261008.py`

Kein Treffer (oder Datei fehlt): nichts tun, weiter mit Step 6. Das ist der Normalfall: Am 08.10. liegt Paket 1 nicht auf dem Paket-2-Branch, und Paket-1-Task 22 ist noch nicht ausgeführt. Paket 1 legt den Test dann gleich so an (Abschnitt „Überschneidungen mit Paket 1", Punkt 1; Entscheidung E5), oder Task 23 Step 3 zieht die Korrektur beim Merge nach.

Ein Treffer: In diesem Test die Zeilen

```python
    def test_quittierter_lieferschein_vertritt_die_bestellung(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        _s6_lieferschein(client, bestellung)
```

ersetzen durch

```python
    def test_quittierter_lieferschein_vertritt_die_bestellung(self, client):
        bestellung = _s6_bestellung(client, _s6_kunde(client))
        # Quittieren setzt nur bestätigte Bestellungen auf GELIEFERT (Paket 2, Task 2)
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
        assert r.status_code == 200, r.text
        _s6_lieferschein(client, bestellung)
```

Begründung: `_s6_bestellung` legt eine Bestellung im Status ENTWURF an; Quittieren aus ENTWURF ist ab jetzt gesperrt (`test_entwurf_kann_nicht_quittiert_werden`), der Test bekäme 400 statt 200. Was er prüft (der quittierte Lieferschein vertritt die Bestellung im Sammellauf), ändert sich nicht. Weicht der Testtext vom zitierten Wortlaut ab: stoppen und melden.

Run (nur bei Treffer): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py -q`
Erwartet: keine Fehlschläge (im Nachbau mit S6: 21 passed).

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v`
Erwartet: 22 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/order_status_service.py backend/app/api/v1/documents.py backend/tests/test_gernot_261008_paket2.py
# nur wenn Step 5 den Paket-1-Test geändert hat:
git add backend/tests/test_gernot_261008.py
git commit -m "fix(lieferschein): Quittieren nutzt die Statusregel, schreibt Audit-Log, trägt Lieferdatum nach"
```

---

### Task 3: Sammel-Endpunkt an die Regel binden — alle oder keine

**Files:**
- Modify: `backend/app/api/v1/sales.py:25-30` (Schema-Import), `:1544-1585` (`bulk_update_status`)
- Modify: `backend/app/schemas/order.py:303-307` (`BulkStatusUpdate`, neue Klasse `BulkStatusResult`)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: `setze_status`, `pruefe_uebergang`, `bezeichnung` aus Task 1.
- Produces: `POST /api/v1/sales/orders/bulk-status` mit Antwort `list[BulkStatusResult]` (`id`, `order_number`, `status`, `total_gross`). Ist ein Übergang unzulässig: 400, Text nennt Bestellnummer und Bezeichnung, nichts geändert. `order_ids` muss mindestens einen Eintrag haben (sonst 422). Task 8 nutzt den Endpunkt aus der Bestellliste.

Warum alle oder keine: Die Bestellliste wählt vorher nur passende Bestellungen aus (Task 8). Lehnt der Server trotzdem ab, hat sich zwischendurch etwas geändert (anderes Gerät); dann ist „nichts geändert, Liste neu laden" ehrlicher als ein Teilerfolg.

- [ ] **Step 1: Failing Tests anhängen**

```python
# --------------------- Task 3: Sammel-Endpunkt, gleiche Regel, alle oder keine

class TestSammelStatus:
    """LÜCKEN 3: POST /orders/bulk-status prüfte nichts, buchte keinen Bestand
    und scheiterte an seinem Antwortschema (500 bei jedem Aufruf)."""

    def _sammel(self, client, orders, status):
        return client.post("/api/v1/sales/orders/bulk-status", json={
            "order_ids": [o["id"] for o in orders], "status": status,
        })

    def test_bestaetigt_und_gepackt_auf_geliefert(self, client):
        kunde = _kunde(client)
        a, b = _bestaetigt(client, kunde), _gepackt(client, kunde)
        r = self._sammel(client, [a, b], "GELIEFERT")
        assert r.status_code == 200, r.text
        assert sorted(x["order_number"] for x in r.json()) == sorted([a["order_number"], b["order_number"]])
        for o in (a, b):
            bestellung = _lesen(client, o)
            assert bestellung["status"] == "GELIEFERT"
            assert bestellung["actual_delivery_date"] == _heute().isoformat()
            assert _audit(client, o)[0]["action"] == "BULK_STATUS_CHANGE"

    def test_ein_unzulaessiger_aendert_nichts(self, client):
        kunde = _kunde(client)
        ok, entwurf = _bestaetigt(client, kunde), _bestellung(client, kunde)
        r = self._sammel(client, [ok, entwurf], "GELIEFERT")
        assert r.status_code == 400
        assert entwurf["order_number"] in r.json()["detail"]
        assert "Entwurf" in r.json()["detail"]
        assert _lesen(client, ok)["status"] == "BESTAETIGT"

    def test_bucht_bestand_fuer_jede_bestellung(self, client):
        produkt = _produkt(client)
        lager = _fertigware(produkt, 1000)
        kunde = _kunde(client)
        a = _bestaetigt(client, kunde, lines=_grammzeile(produkt, 100))
        b = _gepackt(client, kunde, lines=_grammzeile(produkt, 100))
        assert self._sammel(client, [a, b], "GELIEFERT").status_code == 200
        assert _bestand(lager) == Decimal("800")

    def test_bestandsfehler_aendert_keine(self, client, monkeypatch):
        def kaputt(*a, **k):
            raise RuntimeError("Lager gesperrt")
        monkeypatch.setattr("app.services.order_status_service.deduct_inventory_for_order", kaputt)
        kunde = _kunde(client)
        a, b = _bestaetigt(client, kunde), _bestaetigt(client, kunde)
        assert self._sammel(client, [a, b], "GELIEFERT").status_code == 500
        assert {_lesen(client, a)["status"], _lesen(client, b)["status"]} == {"BESTAETIGT"}

    def test_gepackt_per_sammelaktion(self, client):
        kunde = _kunde(client)
        a, b = _bestaetigt(client, kunde), _bestaetigt(client, kunde)
        r = self._sammel(client, [a, b], "IN_PRODUKTION")
        assert r.status_code == 200, r.text
        assert {x["status"] for x in r.json()} == {"IN_PRODUKTION"}

    def test_leere_auswahl_abgelehnt(self, client):
        r = client.post("/api/v1/sales/orders/bulk-status", json={"order_ids": [], "status": "GELIEFERT"})
        assert r.status_code == 422

    def test_unbekannte_bestellung_404(self, client):
        """Charakterisierung — war schon so."""
        r = client.post("/api/v1/sales/orders/bulk-status", json={
            "order_ids": [str(uuid.uuid4())], "status": "GELIEFERT",
        })
        assert r.status_code == 404
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestSammelStatus -v`
Erwartet: **6 failed, 1 passed.** Fünf scheitern an `pydantic_core.ValidationError: 6 validation errors for OrderSummary` (der TestClient reicht die Server-Exception durch), `test_leere_auswahl_abgelehnt` an 200 statt 422. Grün ist nur die Charakterisierung `test_unbekannte_bestellung_404`.

- [ ] **Step 3: Schemas**

In `backend/app/schemas/order.py` die Klasse `BulkStatusUpdate` (Z. 303-307) ersetzen durch:

```python
class BulkStatusUpdate(BaseModel):
    """Schema für Massen-Statusänderung"""
    order_ids: list[UUID] = Field(..., min_length=1)
    status: OrderStatus
    reason: Optional[str] = None


class BulkStatusResult(BaseModel):
    """Eine Bestellung nach der Sammel-Statusänderung"""
    id: UUID
    order_number: str
    status: OrderStatus
    total_gross: Decimal
```

`OrderSummary` (Z. 291-298) bleibt stehen; es wird danach nirgends mehr benutzt, ist aber nicht Gegenstand dieser Task.

- [ ] **Step 4: Endpunkt ersetzen**

In `backend/app/api/v1/sales.py` im Import aus `app.schemas.order` (Z. 25-30):

```python
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse, OrderListResponse,
    OrderLineCreate, OrderLineUpdate, OrderLineResponse,
    OrderStatusUpdate, OrderAuditLogResponse,
    BulkStatusUpdate, BulkStatusResult
)
```

Die komplette Funktion `bulk_update_status` (vom Dekorator `@router.post("/orders/bulk-status", …)` Z. 1544 bis Dateiende Z. 1585) ersetzen durch:

```python
@router.post("/orders/bulk-status", response_model=list[BulkStatusResult])
async def bulk_update_status(
    bulk_update: BulkStatusUpdate,
    db: DBSession,
    user: CurrentUser
):
    """Mehrere Bestellungen auf einen Status setzen — alle oder keine.

    Jeder Übergang wird vorab geprüft. Ist einer unzulässig, ändert sich
    nichts und die Antwort nennt die betroffenen Bestellnummern.
    """
    ids = list(dict.fromkeys(bulk_update.order_ids))
    orders = db.execute(
        select(Order).where(Order.id.in_(ids))
    ).scalars().all()

    if len(orders) != len(ids):
        raise HTTPException(
            status_code=404,
            detail="Eine oder mehrere Bestellungen nicht gefunden"
        )

    abgelehnt = []
    for order in orders:
        try:
            pruefe_uebergang(order.status, bulk_update.status)
        except StatuswechselFehler:
            abgelehnt.append(f"{order.order_number} ({bezeichnung(order.status)})")
    if abgelehnt:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nichts geändert — {bezeichnung(bulk_update.status)} ist nicht möglich für: "
                + ", ".join(sorted(abgelehnt))
            ),
        )

    try:
        for order in orders:
            setze_status(
                db, order, bulk_update.status,
                user=user,
                action="BULK_STATUS_CHANGE",
                reason=bulk_update.reason,
            )
            # Nächste Bestellung soll den bereits reduzierten Bestand sehen
            db.flush()
    except StatuswechselFehler as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except BestandsbuchungFehler as e:
        db.rollback()
        logger.exception("Bestandsabzug bei Sammel-Statuswechsel fehlgeschlagen: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Nichts geändert — Bestandsabzug fehlgeschlagen: {e}",
        )

    db.commit()

    if bulk_update.status == OrderStatus.STORNIERT:
        for order in orders:
            _trigger_forecast_update(str(order.id), "CANCEL")

    return [
        BulkStatusResult(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            total_gross=order.total_gross,
        )
        for order in orders
    ]
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v`
Erwartet: 29 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/sales.py backend/app/schemas/order.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(bestellungen): Sammel-Statuswechsel prüft Übergänge, bucht Bestand, alle oder keine"
```

---

### Task 4: Tagesplan — Gelieferte bleiben in „Ausliefern", Status als Enum-Wert

**Files:**
- Modify: `backend/app/api/v1/production.py:19` (Konstante), `:513-526` (Abfrage), `:537`, `:548`, `:737`
- Modify: `backend/tests/test_gernot_bugfixes.py:140`
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Produces: `production._AUSGELIEFERT = (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)`. `GET /production/day-plan`: `ausliefern` enthält zusätzlich GELIEFERT und FAKTURIERT des Tages, `verpacken` nie. Feld `status` in `day-plan` (`verpacken`, `ausliefern`) und `packaging-plan` (`items[].orders[]`) ist immer der Enum-Wert. Task 11 ersetzt den `verpacken`-Filter (Gepackte nach `verpacken_erledigt`).

**Bewusst geänderte Erwartung:** `tests/test_gernot_bugfixes.py:140` erwartet heute `order_ref["status"] == "Entwurf"`. Das Backend übersetzte nur ENTWURF und lieferte alles andere roh; das Frontend bekam deshalb gemischte Werte („Entwurf", „BESTAETIGT", „IN_PRODUKTION") und konnte sie nicht einheitlich übersetzen. Ab jetzt liefert das Backend durchgängig den Enum-Wert, die Übersetzung liegt in `statusLabels.ts` (Task 6). Der Test prüft weiter, dass der Entwurf sichtbar ist — nur in der neuen Schreibweise `"ENTWURF"`.

**Bewusst unveränderte Erwartung:** `tests/test_gernot_260817.py:187-206` (`TestPacktag`) zählt `verpacken` und `ausliefern` mit ENTWURF-Bestellungen; die Same-Day-Bestellung steht weiter in beiden Listen. Keine Änderung nötig. Ebenso `tests/test_import_bestellungen_zukunft.py` (prüft nur, dass die Bestellung in `verpacken` steht).

FAKTURIERT wird mitgeladen, damit eine Bestellung, die am Liefertag schon fakturiert wurde, nicht genauso aus „Ausliefern" verschwindet wie bisher GELIEFERT.

- [ ] **Step 1: Failing Tests anhängen und bestehende Erwartung umstellen**

An `test_gernot_261008_paket2.py` anhängen:

```python
# ------------------ Task 4: Tagesplan zeigt Gelieferte, Status als Enum-Wert

class TestTagesplanAusliefern:
    """A1: GELIEFERT verschwand aus 'Ausliefern'; Status kam gemischt
    ('Entwurf' übersetzt, alles andere roh)."""

    def test_gelieferte_bleibt_in_ausliefern(self, client):
        o = _bestaetigt(client, _kunde(client))  # Same-Day: verpacken + ausliefern
        assert _status(client, o, "GELIEFERT").status_code == 200
        plan = _plan(client)
        assert [(x["order_id"], x["status"]) for x in plan["ausliefern"]] == [(o["id"], "GELIEFERT")]
        assert plan["verpacken"] == []

    def test_fakturierte_bleibt_in_ausliefern(self, client):
        o = _bestaetigt(client, _kunde(client))
        _status(client, o, "GELIEFERT")
        assert _status(client, o, "FAKTURIERT").status_code == 200
        assert [x["status"] for x in _plan(client)["ausliefern"]] == ["FAKTURIERT"]

    def test_status_kommt_als_enum_wert(self, client):
        kunde = _kunde(client)
        _bestellung(client, kunde)
        _gepackt(client, kunde)
        stati = sorted(x["status"] for x in _plan(client)["ausliefern"])
        assert stati == ["ENTWURF", "IN_PRODUKTION"]

    def test_packaging_plan_status_als_enum_wert(self, client):
        _bestellung(client, _kunde(client), liefertag=date.today() + timedelta(days=1))
        r = client.get("/api/v1/production/packaging-plan",
                       params={"target_date": date.today().isoformat()})
        assert r.json()["items"][0]["orders"][0]["status"] == "ENTWURF"

    def test_stornierte_nicht_im_tagesplan(self, client):
        """Charakterisierung — war schon so."""
        o = _bestaetigt(client, _kunde(client))
        _status(client, o, "STORNIERT")
        plan = _plan(client)
        assert plan["ausliefern"] == [] and plan["verpacken"] == []
```

In `backend/tests/test_gernot_bugfixes.py` Z. 140:

```python
        assert order_ref["status"] == "ENTWURF"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestTagesplanAusliefern -v`
Erwartet: **4 failed, 1 passed** (grün: Charakterisierung `test_stornierte_nicht_im_tagesplan`).

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_bugfixes.py -v`
Erwartet: genau `TestBug8Verpackungsplan::test_lieferung_morgen_erscheint_heute` scheitert (`assert 'Entwurf' == 'ENTWURF'`).

- [ ] **Step 3: production.py**

Nach `router = APIRouter(tags=["Produktion"])` (Z. 19) einfügen:

```python

# Schon beim Kunden: erscheint im Tagesplan nur noch unter "Ausliefern".
_AUSGELIEFERT = (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)
```

In `get_day_plan` den Statusfilter der Abfrage für Verpacken/Ausliefern (Z. 523) ersetzen:

```python
            # GELIEFERT/FAKTURIERT nur für "Ausliefern": die Zeile bleibt am
            # Liefertag sichtbar und zeigt "Geliefert", statt zu verschwinden.
            Order.status.in_([OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION,
                              *_AUSGELIEFERT]),
```

In `_order_ref` (Z. 537):

```python
            # Enum-Wert; die Oberfläche übersetzt (statusLabels.ts)
            "status": o.status.value,
```

Die Zeile `verpacken = [...]` (Z. 548) ersetzen durch:

```python
    verpacken = [
        _order_ref(o) for o in orders
        if o.effective_packing_date == target_date and o.status not in _AUSGELIEFERT
    ]
```

Z. 549 (`ausliefern = …`) bleibt unverändert.

In `get_packaging_plan` (Z. 737):

```python
                "status": order.status.value,  # Enum-Wert; die Oberfläche übersetzt
```

Die Abfrage in `get_packaging_plan` (Z. 673) bleibt unverändert — GELIEFERT war dort schon ausgeschlossen.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py tests/test_gernot_bugfixes.py tests/test_gernot_260817.py tests/test_import_bestellungen_zukunft.py -v`
Erwartet: alle grün.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/production.py backend/tests/test_gernot_bugfixes.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(tagesplan): Gelieferte bleiben in Ausliefern; Status kommt als Enum-Wert"
```

---

### Task 5: Fehlertexte nennen Bezeichnungen statt Enum-Werten

**Files:**
- Modify: `backend/app/api/v1/sales.py:1143` (`confirm_order`), `:1277` (`delete_order`), `:1313` (`add_order_line`)
- Modify: `backend/app/api/v1/forecasting.py:935`, `:1021`
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: `bezeichnung` aus Task 1 (in sales.py bereits importiert).

Diese Texte kommen als Toast beim Anwender an (über `EditOrderModal`, Bestellliste, Prognose-Seite). Der 422-Text bei ungültigem Listenfilter (sales.py ~Z. 697-700) bleibt, er ist aus der Oberfläche kaum erreichbar.

- [ ] **Step 1: Failing Tests anhängen**

```python
# --------------------------- Task 5: Fehlertexte mit Bezeichnung

class TestFehlertexte:
    """Fehlertexte landen als Toast beim Anwender — keine Enum-Werte."""

    def test_bestaetigen(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung hat Status Bestätigt, kann nicht bestätigt werden"

    def test_loeschen(self, client):
        o = _bestaetigt(client, _kunde(client))
        r = client.delete(f"/api/v1/sales/orders/{o['id']}")
        assert r.status_code == 400
        assert r.json()["detail"].endswith("Diese Bestellung hat Status Bestätigt")

    def test_position_bei_gepackt(self, client):
        o = _gepackt(client, _kunde(client))
        r = client.post(f"/api/v1/sales/orders/{o['id']}/lines", json={
            "product_name": "Kresse", "quantity": 1, "unit": "STK",
            "unit_price": 2.0, "tax_rate": "REDUZIERT",
        })
        assert r.status_code == 400
        assert r.json()["detail"] == "Positionen können nicht hinzugefügt werden bei Status Gepackt"

    def _vorschlag(self, client, status):
        """Produktionsvorschlag direkt über das ORM (Vorbild test_import_chargen.py)."""
        from app.models.forecast import Forecast, ProductionSuggestion, SuggestionStatus
        r = client.post("/api/v1/seeds", json={
            "name": "Rettich", "keimdauer_tage": 2, "wachstumsdauer_tage": 8,
            "erntefenster_min_tage": 9, "erntefenster_optimal_tage": 11,
            "erntefenster_max_tage": 14, "ertrag_gramm_pro_tray": 350,
        })
        assert r.status_code == 201, r.text
        seed_id = uuid.UUID(r.json()["id"])
        with TestingSessionLocal() as db:
            forecast = Forecast(seed_id=seed_id, datum=date.today(), horizont_tage=7,
                                prognostizierte_menge=100, effektive_menge=100, modell_typ="MANUAL")
            db.add(forecast)
            db.flush()
            vorschlag = ProductionSuggestion(
                forecast_id=forecast.id, seed_id=seed_id, empfohlene_trays=2,
                aussaat_datum=date.today(), erwartete_ernte_datum=date.today() + timedelta(days=10),
                status=SuggestionStatus(status),
            )
            db.add(vorschlag)
            db.commit()
            return str(vorschlag.id)

    def test_vorschlag_genehmigen(self, client):
        vid = self._vorschlag(client, "GENEHMIGT")
        r = client.post(f"/api/v1/forecasting/production-suggestions/{vid}/approve", json={})
        assert r.status_code == 400
        assert r.json()["detail"] == "Vorschlag hat Status Genehmigt, kann nicht genehmigt werden"

    def test_vorschlag_ablehnen(self, client):
        vid = self._vorschlag(client, "UMGESETZT")
        r = client.post(f"/api/v1/forecasting/production-suggestions/{vid}/reject",
                        json={"grund": "Zu viel Ware im Lager"})
        assert r.status_code == 400
        assert r.json()["detail"] == "Vorschlag hat Status Umgesetzt, kann nicht abgelehnt werden"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestFehlertexte -v`
Erwartet: **5 failed** (Texte enthalten `BESTAETIGT`, `IN_PRODUKTION`, `GENEHMIGT`, `UMGESETZT`).

- [ ] **Step 3: Texte umstellen**

`backend/app/api/v1/sales.py`:

Z. 1143:
```python
            detail=f"Bestellung hat Status {bezeichnung(order.status)}, kann nicht bestätigt werden"
```
Z. 1277:
```python
            detail=f"Nur Entwürfe können gelöscht werden. Diese Bestellung hat Status {bezeichnung(order.status)}"
```
Z. 1313:
```python
            detail=f"Positionen können nicht hinzugefügt werden bei Status {bezeichnung(order.status)}"
```

`backend/app/api/v1/forecasting.py`:

Z. 935:
```python
            # capitalize(): GENEHMIGT → "Genehmigt", wie SuggestionStatusBadge
            detail=f"Vorschlag hat Status {suggestion.status.value.capitalize()}, kann nicht genehmigt werden"
```
Z. 1021:
```python
            detail=f"Vorschlag hat Status {suggestion.status.value.capitalize()}, kann nicht abgelehnt werden"
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v`
Erwartet: 39 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/sales.py backend/app/api/v1/forecasting.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(status): Fehlertexte nennen Bezeichnungen statt Enum-Werten"
```

---

### Task 6: Frontend — Bezeichnungen zentral, IN_PRODUKTION heißt „Gepackt"

**Files:**
- Create: `frontend/src/components/ui/statusLabels.ts`
- Modify: `frontend/src/components/ui/Badge.tsx:1-2`, `:57-75`; `frontend/src/components/ui/index.ts:11`
- Modify: `frontend/src/services/api.ts:14`, `:144`, `:384-385`
- Modify: `frontend/src/pages/Tagesplan.tsx:7`, `:102`, `:149`, `:190`
- Modify: `frontend/src/pages/Production.tsx:12-21`, `:465`, `:603`
- Modify: `frontend/src/pages/Forecasting.tsx:7-16`, `:362-372`, `:378`
- Modify: `frontend/src/pages/Invoices.tsx:21`, `:128`
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx:8`, `:171`, `:229`, `:305`
- Modify: `frontend/src/pages/Sales.tsx:9-18`, `:28`, `:96-104`, `:305-308`
- Modify: `frontend/src/pages/Orders.tsx:15-37`

**Interfaces:**
- Produces: `ORDER_STATUS_LABELS: Record<OrderStatus, string>`, `orderStatusLabel(status: string): string`, `belegStatusLabel`, `aussaatStatusLabel`, `lexofficeStatusLabel`, `warnungTypLabel` (alle aus `components/ui` exportiert). `OrderStatusBadge` zeigt „Gepackt" für IN_PRODUKTION. `DayPlanOrder.status: OrderStatus`. `salesApi.updateOrderStatus(id, status: OrderStatus, reason?, actualDeliveryDate?)` und `salesApi.bulkUpdateStatus(orderIds, status, reason?)`.

**Einheitliche Wörter:** Entwurf · Bestätigt · Gepackt · Geliefert · Fakturiert · Storniert. GELIEFERT heißt überall „Geliefert" wie bisher in `OrderStatusBadge`; „Ausgeliefert" ist nur die Beschriftung des Knopfs im Tagesplan (Task 7). **Farben bleiben, wie sie in `OrderStatusBadge` heute sind** (Badge.tsx:60-65): Entwurf grau, Bestätigt blau, Gepackt (IN_PRODUKTION) gelb, Geliefert grün, Fakturiert grau, Storniert rot. Entschieden ist nur der Name; eine neue Farbwahl würde in der Bestellliste „Entwurf" so aussehen lassen wie bisher „In Produktion". Der Tagesplan übernimmt damit die Farben der Bestellliste: sein Entwurf-Badge wird grau statt gelb (bisher `variant={o.status === 'Entwurf' ? 'warning' : 'info'}`). Andere Farben → Offener Punkt O6. Hinweis: `OrderStatusBadge` liegt in `components/ui/Badge.tsx`, nicht in `components/common/`.

- [ ] **Step 1: Bezeichnungen anlegen**

Neue Datei `frontend/src/components/ui/statusLabels.ts`:

```ts
import type { OrderStatus } from '../../types';

/**
 * Anzeigenamen für Status-Werte. Das Backend liefert immer den Enum-Wert
 * (z. B. IN_PRODUKTION); übersetzt wird ausschließlich hier. Die Wörter
 * für Bestellungen stehen gleichlautend in
 * backend/app/services/order_status_service.py (STATUS_BEZEICHNUNG).
 *
 * IN_PRODUKTION heißt in der Oberfläche „Gepackt" (Entscheidung 08.10.2026).
 */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  ENTWURF: 'Entwurf',
  BESTAETIGT: 'Bestätigt',
  IN_PRODUKTION: 'Gepackt',
  GELIEFERT: 'Geliefert',
  FAKTURIERT: 'Fakturiert',
  STORNIERT: 'Storniert',
};

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status as OrderStatus] ?? status;
}

// Auftragsbestätigung (ENTWURF/VERSENDET), Lieferschein (ENTWURF/AUSGESTELLT/
// GELIEFERT) und Rechnung (InvoiceStatus) teilen sich die Wörter.
const BELEG_STATUS_LABELS: Record<string, string> = {
  ENTWURF: 'Entwurf',
  VERSENDET: 'Versendet',
  AUSGESTELLT: 'Ausgestellt',
  GELIEFERT: 'Geliefert',
  OFFEN: 'Offen',
  TEILBEZAHLT: 'Teilbezahlt',
  BEZAHLT: 'Bezahlt',
  UEBERFAELLIG: 'Überfällig',
  STORNIERT: 'Storniert',
  MAHNVERFAHREN: 'Im Mahnverfahren',
};

export function belegStatusLabel(status: string): string {
  return BELEG_STATUS_LABELS[status] ?? status;
}

// Tagesplan „Aussaat": Vorschlagsstatus oder eine bereits angelegte Charge
// (backend/app/api/v1/production.py get_day_plan, "status": "ANGELEGT").
const AUSSAAT_STATUS_LABELS: Record<string, string> = {
  VORGESCHLAGEN: 'Vorgeschlagen',
  GENEHMIGT: 'Genehmigt',
  ANGELEGT: 'Angelegt',
};

export function aussaatStatusLabel(status: string): string {
  return AUSSAAT_STATUS_LABELS[status] ?? status;
}

// lexoffice meldet eigene, englische Belegstatus.
const LEXOFFICE_STATUS_LABELS: Record<string, string> = {
  draft: 'Entwurf',
  open: 'Offen',
  overdue: 'Überfällig',
  paid: 'Bezahlt',
  paidoff: 'Bezahlt',
  voided: 'Storniert',
};

export function lexofficeStatusLabel(status: string): string {
  return LEXOFFICE_STATUS_LABELS[status] ?? status;
}

// Warnungen an Produktionsvorschlägen (backend/app/models/forecast.py
// WarningType). "UNBEKANNT" setzt forecasting.py, wenn der Typ fehlt.
const WARNUNG_TYP_LABELS: Record<string, string> = {
  UNTERDECKUNG: 'Unterdeckung',
  UEBERPRODUKTION: 'Überproduktion',
  KAPAZITAET: 'Kapazität',
  SAATGUT_NIEDRIG: 'Saatgut knapp',
  UNBEKANNT: 'Warnung',
};

export function warnungTypLabel(typ: string): string {
  return WARNUNG_TYP_LABELS[typ] ?? typ;
}
```

- [ ] **Step 2: Badge und Export**

`frontend/src/components/ui/Badge.tsx`, nach Z. 2 (`import { GrowBatchStatus, … } from '../../types';`):

```ts
import { orderStatusLabel } from './statusLabels';
```

Den Block `// Order Status Badge` bis einschließlich `export function OrderStatusBadge … }` (Z. 57-75) ersetzen durch:

```tsx
// Order Status Badge — Bezeichnungen in statusLabels.ts. Farben wie bisher
// in der Bestellliste; der Tagesplan übernimmt sie.
const orderStatusVariant: Record<OrderStatus, BadgeVariant> = {
  ENTWURF: 'gray',
  BESTAETIGT: 'info',
  IN_PRODUKTION: 'warning',
  GELIEFERT: 'success',
  FAKTURIERT: 'gray',
  STORNIERT: 'danger',
};

interface OrderStatusBadgeProps {
  status: OrderStatus | string;
}

export function OrderStatusBadge({ status }: OrderStatusBadgeProps) {
  const variant = orderStatusVariant[status as OrderStatus] ?? 'gray';
  return <Badge variant={variant}>{orderStatusLabel(status)}</Badge>;
}
```

`frontend/src/components/ui/index.ts`, nach Z. 11 (Export aus `./Badge`):

```ts
export {
  ORDER_STATUS_LABELS,
  orderStatusLabel,
  belegStatusLabel,
  aussaatStatusLabel,
  lexofficeStatusLabel,
  warnungTypLabel,
} from './statusLabels';
```

- [ ] **Step 3: api.ts**

Nach dem Typ-Import `} from '../types'` (Z. 14) als eigene Zeile (damit der lange Importblock, den Paket 1 eventuell erweitert, unberührt bleibt):

```ts
import type { OrderStatus } from '../types'
```

`DayPlanOrder`, Z. 144:

```ts
  status: OrderStatus  // Enum-Wert; Anzeige über orderStatusLabel / OrderStatusBadge
```

`salesApi.updateOrderStatus` (Z. 384-385) ersetzen durch:

```ts
  // actualDeliveryDate nur bei GELIEFERT: tatsächlicher Liefertag (Standard heute)
  updateOrderStatus: (id: string, status: OrderStatus, reason?: string, actualDeliveryDate?: string) =>
    api.post<Order>(`/sales/orders/${id}/status`, {
      status, reason, actual_delivery_date: actualDeliveryDate,
    }).then(r => r.data),

  // Sammelaktion: alle oder keine — der Server prüft jeden Übergang vorab
  bulkUpdateStatus: (orderIds: string[], status: OrderStatus, reason?: string) =>
    api.post<Array<{ id: string; order_number: string; status: OrderStatus; total_gross: string }>>(
      '/sales/orders/bulk-status', { order_ids: orderIds, status, reason },
    ).then(r => r.data),
```

- [ ] **Step 4: Tagesplan.tsx — Badges**

Z. 7:

```ts
import { Input, EmptyState, Badge, OrderStatusBadge, PageLoader, Button, useToast, aussaatStatusLabel } from '../components/ui';
```

Z. 102 (Aussaat; ANGELEGT ist kein `SuggestionStatus`, daher nicht `SuggestionStatusBadge`):

```tsx
          <Badge variant={a.status === 'GENEHMIGT' ? 'success' : 'warning'}>{aussaatStatusLabel(a.status)}</Badge>
```

Z. 149 (Verpacken) und Z. 190 (Ausliefern) — beide Zeilen `<Badge variant={o.status === 'Entwurf' ? 'warning' : 'info'}>{o.status}</Badge>` ersetzen durch:

```tsx
<OrderStatusBadge status={o.status} />
```

(Einrückung der jeweiligen Zeile beibehalten. Der Ausliefern-Block wird in Task 7 ohnehin neu geschrieben.)

- [ ] **Step 5: Production.tsx, Forecasting.tsx, Invoices.tsx**

`Production.tsx`, Import aus `'../components/ui'` (Z. 12-21) um zwei Namen ergänzen:

```ts
  Input,
  getRelativeDate,
  GrowBatchStatusBadge,
  orderStatusLabel,
} from '../components/ui';
```

Z. 465: `({o.status}{o.same_day ? …` → `({orderStatusLabel(o.status)}{o.same_day ? …` (Rest der Zeile unverändert).

Z. 603:

```tsx
                        <GrowBatchStatusBadge status={batch.status} />
```

`Forecasting.tsx`, Import aus `'../components/ui'` (Z. 7-16): nach `Badge,` ergänzen `SuggestionStatusBadge,` und `warnungTypLabel,`. Den Block Z. 362-372 (`<Badge variant={suggestion.status === 'GENEHMIGT' ? … }>{suggestion.status}</Badge>`) ersetzen durch:

```tsx
                        <SuggestionStatusBadge status={suggestion.status} />
```

In der Spalte „Warnungen" Z. 378 (`{w.typ}`, zeigte `UNTERDECKUNG` usw. roh) ersetzen durch:

```tsx
                              <span title={w.nachricht}>{warnungTypLabel(w.typ)}</span>
```

(`Badge` bleibt importiert, die Warnungen nutzen es. Den vollen Text `w.nachricht` zeigt das Dashboard schon, hier steht er im Tooltip.)

`Invoices.tsx`, nach Z. 21 eigene Zeile:

```ts
import { lexofficeStatusLabel } from '../components/ui/statusLabels';
```

Z. 128:

```ts
      toast.success(res.updated ? 'Als bezahlt übernommen' : `lexoffice-Status: ${lexofficeStatusLabel(res.lexoffice_status)}`);
```

- [ ] **Step 6: OrderDocumentsModal.tsx — Belegstatus**

Nach Z. 8 (`import { getErrorMessage } …`) eigene Zeile:

```ts
import { belegStatusLabel } from '../ui/statusLabels';
```

In Z. 171, 229 und 305 jeweils nur den Inhalt des `<span>` tauschen: `{c.status}` → `{belegStatusLabel(c.status)}`, `{n.status}` → `{belegStatusLabel(n.status)}`, `{inv.status}` → `{belegStatusLabel(inv.status)}`. Die Funktion `statusBadge` (Farben, Z. 16-24) bleibt.

- [ ] **Step 7: Sales.tsx und Orders.tsx — Status-Anzeige und Filter**

`Sales.tsx`, Import aus `'../components/ui'` (Z. 9-18) um `OrderStatusBadge,` und `ORDER_STATUS_LABELS,` ergänzen. Z. 28:

```ts
import type { Order, OrderStatus, Customer, OrderWithCustomer } from '../types';
```

`orderStatusOptions` (Z. 96-104) ersetzen durch:

```ts
  const orderStatusOptions: SelectOption[] = [
    { value: '', label: 'Alle Status' },
    ...(Object.keys(ORDER_STATUS_LABELS) as OrderStatus[]).map((s) => ({
      value: s,
      label: ORDER_STATUS_LABELS[s],
    })),
  ];
```

Detail-Modal, Z. 306-308 (`<span className={`badge badge-${selectedOrder.status.toLowerCase()}`}>{selectedOrder.status}</span>`) ersetzen durch:

```tsx
                <OrderStatusBadge status={selectedOrder.status} />
```

`Orders.tsx`, Import aus `'../components/ui'` (Z. 15-26): nach `getRelativeDate,` ergänzen `ORDER_STATUS_LABELS,`. `statusOptions` (Z. 29-37) ersetzen durch:

```ts
const statusOptions: SelectOption[] = [
  { value: 'all', label: 'Alle Status' },
  ...(Object.keys(ORDER_STATUS_LABELS) as OrderStatus[]).map((s) => ({
    value: s,
    label: ORDER_STATUS_LABELS[s],
  })),
];
```

(`orderStatusLabel` kommt erst in Task 8 dazu: `tsconfig.json` hat `noUnusedLocals`, ein unbenutzter Import bricht `tsc`.)

- [ ] **Step 8: Prüfen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe.

Run: `cd frontend && grep -rn '\.status}' src/pages src/components | grep -v 'status={' | grep -v KanbanBoard.tsx`
Erwartet: keine Ausgabe (die zwei Treffer in `KanbanBoard.tsx` sind Schlüssel, keine Anzeige).

Run: `cd frontend && grep -rn '{w\.typ}' src/pages src/components`
Erwartet: keine Ausgabe.

Run: `cd frontend && grep -rn "In Produktion" src/pages src/components | grep -v "In Produktion ab"`
Erwartet: nur noch `OrderCard.tsx`, `Orders.tsx` (Sammelleiste) und `Sales.tsx` (Knopf) — die stellt Task 8 um. („In Produktion ab" in `Inventory.tsx` betrifft Saatgut, nicht Bestellungen.)

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ui/statusLabels.ts frontend/src/components/ui/Badge.tsx frontend/src/components/ui/index.ts frontend/src/services/api.ts frontend/src/pages/Tagesplan.tsx frontend/src/pages/Production.tsx frontend/src/pages/Forecasting.tsx frontend/src/pages/Invoices.tsx frontend/src/components/domain/OrderDocumentsModal.tsx frontend/src/pages/Sales.tsx frontend/src/pages/Orders.tsx
git commit -m "fix(ui): Statusbezeichnungen zentral, IN_PRODUKTION heißt Gepackt, keine Enum-Werte mehr"
```

---

### Task 7: Tagesplan — Knopf „Ausgeliefert", Neuladen nach jedem Statuswechsel

**Files:**
- Create: `frontend/src/services/orderQueries.ts`
- Modify: `frontend/src/pages/Tagesplan.tsx:4-5`, `:14`, `:20-23`, `:47-50`, `:65-67`, `:184-192`

**Interfaces:**
- Consumes: `salesApi.updateOrderStatus(..., actualDeliveryDate)`, `OrderStatusBadge` aus Task 6; Backend Tasks 1 und 4.
- Produces: `invalidateOrderViews(queryClient: QueryClient): Promise<void>` — invalidiert `['orders']`, `['day-plan']`, `['packaging-plan']` (Tagesplan.tsx) und `['packagingPlan']` (Production.tsx; zwei Schlüssel für denselben Endpunkt). Tasks 8, 9 und 13 benutzen ihn.

Verhalten: In der Karte „Ausliefern" bekommen BESTAETIGT und IN_PRODUKTION einen Knopf „Ausgeliefert", gesperrt während einer laufenden Anfrage. Nach dem Klick lädt der Tagesplan neu; die Zeile bleibt mit Badge „Geliefert" stehen (Backend Task 4). Ein Entwurf bekommt keinen Knopf (erst bestätigen). Wer einen vergangenen Tag ansieht und dort „Ausgeliefert" klickt, schickt dessen Datum als Liefertag mit. Tagesplan und Packplan laden zusätzlich alle 60 s und bei Fensterfokus neu, damit das Hallen-Tablet Änderungen anderer Geräte sieht (`main.tsx:26-28` schaltet `refetchOnWindowFocus` global ab — global bleibt das so).

- [ ] **Step 1: Helfer anlegen**

Neue Datei `frontend/src/services/orderQueries.ts`:

```ts
import type { QueryClient } from '@tanstack/react-query';

/**
 * Alle Ansichten, die den Bestellstatus zeigen. Nach jedem Statuswechsel neu
 * laden — sonst zeigt ein offener Tagesplan (Hallen-Tablet) den alten Stand,
 * weil main.tsx refetchOnWindowFocus abschaltet.
 * 'packagingPlan' (Production.tsx) und 'packaging-plan' (Tagesplan.tsx) sind
 * zwei Schlüssel für denselben Endpunkt.
 */
const BESTELL_ANSICHTEN = [['orders'], ['day-plan'], ['packaging-plan'], ['packagingPlan']];

export async function invalidateOrderViews(queryClient: QueryClient): Promise<void> {
  await Promise.all(
    BESTELL_ANSICHTEN.map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  );
}
```

- [ ] **Step 2: Tagesplan.tsx**

Z. 4-5 ersetzen durch (Icon `CheckCircle`, `salesApi`) und die zwei neuen Importe nach Z. 7 anfügen:

```ts
import { Sprout, Scissors, Package, Truck, Users, Boxes, ListTodo, Plus, FileText, ChevronDown, ChevronRight, CheckCircle } from 'lucide-react';
import { productionApi, staffApi, documentsApi, salesApi } from '../services/api';
```
```ts
import { getErrorMessage } from '../services/errors';
import { invalidateOrderViews } from '../services/orderQueries';
```

Z. 14 (`const today = new Date().toISOString().split('T')[0];`) ersetzen durch:

```ts
  // Lokaler Kalendertag (sv-SE = JJJJ-MM-TT). toISOString() wäre UTC und
  // zeigte zwischen 0 und 2 Uhr noch den Vortag.
  const today = new Date().toLocaleDateString('sv-SE');
```

Die Abfrage `day-plan` (Z. 20-23) ersetzen durch:

```ts
  const { data: plan, isLoading } = useQuery({
    queryKey: ['day-plan', date],
    queryFn: () => productionApi.getDayPlan(date),
    // Hallen-Tablet: Änderungen anderer Geräte ohne Neuladen sehen
    refetchInterval: 60_000,
    refetchOnWindowFocus: 'always',
  });
```

Die Abfrage `packaging-plan` (Z. 47-50) ersetzen durch:

```ts
  const { data: packaging } = useQuery({
    queryKey: ['packaging-plan', date],
    queryFn: () => productionApi.getPackagingPlan(date),
    refetchInterval: 60_000,
    refetchOnWindowFocus: 'always',
  });
```

Direkt nach `packlisteMutation` (vor `if (isLoading) return <PageLoader />;`, Z. 67) einfügen:

```ts
  // "Ausgeliefert" in der Karte Ausliefern. Wer einen vergangenen Tag
  // nachträgt, liefert dessen Datum mit — sonst setzt der Server heute.
  const ausgeliefertMutation = useMutation({
    mutationFn: (orderId: string) =>
      salesApi.updateOrderStatus(orderId, 'GELIEFERT', undefined, date < today ? date : undefined),
    onSuccess: async (order) => {
      await invalidateOrderViews(queryClient);
      toast.success(`${order.order_number ?? 'Bestellung'} ausgeliefert`);
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden')),
  });
```

Im Abschnitt `key: 'ausliefern'` die `rows` (Z. 184-192) ersetzen durch (`key={i}` wird zu `key={o.order_id}`):

```tsx
      // Bestätigt und Gepackt bekommen den Knopf; Geliefert bleibt am Tag
      // sichtbar (Badge), ein Entwurf muss erst bestätigt werden.
      rows: (plan?.ausliefern ?? []).map((o) => (
        <div key={o.order_id} className="flex items-center justify-between p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
          <div>
            <p className="font-medium text-gray-900 dark:text-white">{o.customer_name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">{o.order_number} · {o.positionen} Positionen</p>
          </div>
          <div className="flex items-center gap-2">
            <OrderStatusBadge status={o.status} />
            {(o.status === 'BESTAETIGT' || o.status === 'IN_PRODUKTION') && (
              <Button
                size="sm"
                variant="success"
                icon={<CheckCircle className="w-4 h-4" />}
                loading={ausgeliefertMutation.isPending && ausgeliefertMutation.variables === o.order_id}
                disabled={ausgeliefertMutation.isPending}
                onClick={() => ausgeliefertMutation.mutate(o.order_id)}
              >
                Ausgeliefert
              </Button>
            )}
          </div>
        </div>
      )),
```

- [ ] **Step 3: Prüfen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe.

Run: `cd frontend && grep -n "Ausgeliefert\|invalidateOrderViews\|refetchInterval" src/pages/Tagesplan.tsx`
Erwartet: je mindestens ein Treffer.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/orderQueries.ts frontend/src/pages/Tagesplan.tsx
git commit -m "feat(tagesplan): Knopf Ausgeliefert, Tagesplan lädt nach Statuswechsel neu"
```

---

### Task 8: Bestellliste — ehrliche Sammelaktionen, „Gepackt" und „Geliefert" getrennt

**Files:**
- Modify: `frontend/src/components/domain/OrderCard.tsx:1-27`, `:89-129`
- Modify: `frontend/src/pages/Orders.tsx:5`, `:29-37` (nach Task 6), `:47`, `:63-64`, `:78-155`, `:279-300`, `:326-328`, `:387-394`
- Modify: `frontend/src/pages/Sales.tsx:9-27`, `:54-74`, `:244-245`, `:368-378`
- Modify: `frontend/src/components/domain/EditOrderModal.tsx:7`, `:150-152`, `:156`, `:161`, `:241`, `:267`, `:315`, `:359-361`

**Interfaces:**
- Consumes: `salesApi.bulkUpdateStatus` (Task 6, Backend Task 3), `invalidateOrderViews` (Task 7), `orderStatusLabel`, `ORDER_STATUS_LABELS` (Task 6).
- Produces: `OrderCard`-Props `onConfirm/onMarkReady/onMarkDelivered: () => unknown` (dürfen ein Promise liefern; die Karte sperrt ihre Knöpfe, bis es erledigt ist). Die Karte entscheidet selbst anhand des Status, welche Knöpfe sie zeigt.

Warum so: Laut Audit-Log gingen Gernots fünf Bestellungen am 07.10. in derselben Sekunde von BESTAETIGT über IN_PRODUKTION nach GELIEFERT. In `OrderCard` lag „Geliefert" nach dem ersten Klick genau dort, wo vorher „In Produktion" war. Jetzt stehen ab Bestätigt beide Knöpfe nebeneinander und behalten ihren Platz; nach „Gepackt" bleibt dieser Knopf ausgegraut stehen. Die Sammelaktionen filterten still (`Orders.tsx:142-155` nur IN_PRODUKTION) und meldeten trotzdem Erfolg. Jetzt nennen sie die Anzahl, melden „keine passende" als Fehler und zählen Übersprungene mit Nummer auf.

- [ ] **Step 1: OrderCard.tsx**

Z. 1-13 (Importe, Props, Funktionskopf) ersetzen durch:

```tsx
import { useState, type MouseEvent } from 'react';
import { OrderWithCustomer } from '../../types';
import { OrderStatusBadge, formatDate, getRelativeDate } from '../ui';
import { Calendar, Check, ClipboardCheck, Truck } from 'lucide-react';

// Darf ein Promise liefern (z. B. mutateAsync); Fehler meldet der Aufrufer selbst.
type Aktion = () => unknown;

interface OrderCardProps {
  order: OrderWithCustomer;
  onConfirm?: Aktion;
  onMarkReady?: Aktion;
  onMarkDelivered?: Aktion;
  onClick?: () => void;
}

export function OrderCard({ order, onConfirm, onMarkReady, onMarkDelivered, onClick }: OrderCardProps) {
  // Solange ein Statuswechsel läuft, sind alle Knöpfe der Karte gesperrt.
  const [busy, setBusy] = useState(false);
  const run = (aktion: Aktion) => async (e: MouseEvent) => {
    e.stopPropagation();
    if (busy) return;
    setBusy(true);
    try {
      await aktion();
    } catch {
      // Der Aufrufer zeigt den Fehler als Toast; hier nur die Sperre lösen.
    } finally {
      setBusy(false);
    }
  };
```

Z. 22-27 (Kommentar und `canConfirm/canMarkReady/canMarkDelivered`) ersetzen durch:

```tsx
  // Eine neu erfasste Bestellung steht auf ENTWURF. Ohne diesen Schritt
  // ist die Statuskette aus der Oberfläche nicht begehbar, weil
  // "Gepackt" erst ab BESTAETIGT erscheint.
  const canConfirm = order.status === 'ENTWURF';
  // "Gepackt" und "Geliefert" stehen ab Bestätigt nebeneinander und behalten
  // ihren Platz: nach "Gepackt" bleibt der Knopf ausgegraut stehen. Vorher
  // rückte "Geliefert" an dieselbe Stelle, ein Doppelklick löste beide
  // Wechsel aus (Audit-Log 07.10.: BESTAETIGT → IN_PRODUKTION → GELIEFERT
  // in derselben Sekunde).
  const showPackDeliver = order.status === 'BESTAETIGT' || order.status === 'IN_PRODUKTION';
  const isPacked = order.status === 'IN_PRODUKTION';
```

Den Block `{/* Actions */}` bis zu seinem schließenden `)}` (Z. 89-129) ersetzen durch:

```tsx
        {/* Actions */}
        {((canConfirm && onConfirm) || (showPackDeliver && onMarkReady && onMarkDelivered)) && (
          <div className="mt-4 flex gap-2">
            {canConfirm && onConfirm && (
              <button
                className="btn btn-primary btn-sm flex-1"
                disabled={busy}
                onClick={run(onConfirm)}
              >
                <ClipboardCheck className="w-4 h-4" />
                Bestätigen
              </button>
            )}
            {showPackDeliver && onMarkReady && onMarkDelivered && (
              <>
                <button
                  className="btn btn-success btn-sm flex-1"
                  disabled={busy || isPacked}
                  title={isPacked ? 'Bereits gepackt' : undefined}
                  onClick={run(onMarkReady)}
                >
                  <Check className="w-4 h-4" />
                  Gepackt
                </button>
                <button
                  className="btn btn-primary btn-sm flex-1"
                  disabled={busy}
                  onClick={run(onMarkDelivered)}
                >
                  <Truck className="w-4 h-4" />
                  Geliefert
                </button>
              </>
            )}
          </div>
        )}
```

`OrderRow` (ab Z. 135) bleibt unverändert.

- [ ] **Step 2: Orders.tsx — Einzel- und Sammelaktionen**

Nach Z. 5 (`import { Order, OrderStatus } from '../types';`):

```ts
import { invalidateOrderViews } from '../services/orderQueries';
```

Im Import aus `'../components/ui'` nach `ORDER_STATUS_LABELS,` (Task 6) ergänzen: `orderStatusLabel,`.

Direkt nach `statusOptions` (aus Task 6) einfügen:

```ts

// Spiegel der Serverregel (order_status_service.ERLAUBTE_UEBERGAENGE) — nur
// für die Vorauswahl und die Meldung; der Server prüft trotzdem jede Bestellung.
const SAMMEL_ERLAUBT_AB: Record<'IN_PRODUKTION' | 'GELIEFERT', OrderStatus[]> = {
  IN_PRODUKTION: ['BESTAETIGT'],
  GELIEFERT: ['BESTAETIGT', 'IN_PRODUKTION'],
};

const nummer = (o: Order) => o.order_number ?? o.id.slice(0, 8);
```

Nach `const [editOrder, setEditOrder] = useState<Order | null>(null);` (Z. 47):

```ts
  const [bulkBusy, setBulkBusy] = useState(false);
```

Die Reiter „Heute"/„Morgen" (Z. 63-64, `const today = new Date().toISOString().split('T')[0];` und `const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0];`) ersetzen durch — derselbe UTC-Fehler, den Task 7 im Tagesplan behebt:

```ts
  // Lokaler Kalendertag wie im Tagesplan (sv-SE = JJJJ-MM-TT). toISOString()
  // wäre UTC und ordnete zwischen 0 und 2 Uhr die Bestellungen von gestern
  // unter "Heute" ein.
  const today = new Date().toLocaleDateString('sv-SE');
  const morgen = new Date();
  morgen.setDate(morgen.getDate() + 1);
  const tomorrow = morgen.toLocaleDateString('sv-SE');
```

Die Funktionen `handleConfirm`, `handleMarkReady`, `handleMarkDelivered`, die Zeile `const bulk = useBulkSelection(orders);` und `handleBulkConfirm`, `handleBulkReady`, `handleBulkDelivered` (Z. 78-155) ersetzen durch:

```tsx
  const handleConfirm = async (order: Order) => {
    try {
      await salesApi.confirmOrder(order.id);
      await invalidateOrderViews(queryClient);
      toast.success('Bestellung bestätigt');
    } catch (e) {
      toast.error(getErrorMessage(e, 'Bestellung konnte nicht bestätigt werden'));
    }
  };

  const handleMarkReady = async (order: Order) => {
    try {
      await salesApi.updateOrderStatus(order.id, 'IN_PRODUKTION');
      await invalidateOrderViews(queryClient);
      toast.success(`${nummer(order)} gepackt`);
    } catch (e) {
      toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden'));
    }
  };

  const handleMarkDelivered = async (order: Order) => {
    try {
      await salesApi.updateOrderStatus(order.id, 'GELIEFERT');
      await invalidateOrderViews(queryClient);
      toast.success(`${nummer(order)} geliefert`);
    } catch (e) {
      toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden'));
    }
  };

  // Bulk selection
  const bulk = useBulkSelection(orders);

  const handleBulkConfirm = async () => {
    const auswahl = bulk.selectedItems;
    const entwuerfe = auswahl.filter((o) => o.status === 'ENTWURF');
    if (entwuerfe.length === 0) {
      toast.error('Keine der markierten Bestellungen ist ein Entwurf');
      return;
    }
    setBulkBusy(true);
    try {
      // Einzeln bestätigen (der Endpunkt prüft Positionen und setzt das
      // bestätigte Lieferdatum) — Fehlschläge werden gezählt, nicht verschluckt.
      const ergebnisse = await Promise.allSettled(entwuerfe.map((o) => salesApi.confirmOrder(o.id)));
      const fehler = ergebnisse.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      await invalidateOrderViews(queryClient);
      bulk.clearSelection();
      const ok = entwuerfe.length - fehler.length;
      if (ok > 0) toast.success(`${ok} von ${auswahl.length} Bestellung(en) bestätigt`);
      if (fehler.length > 0) {
        toast.error(`${fehler.length} nicht bestätigt: ${getErrorMessage(fehler[0].reason, 'Fehler')}`);
      }
    } finally {
      setBulkBusy(false);
    }
  };

  // Sammelaktion ehrlich: gesendet werden nur Bestellungen, für die der
  // Wechsel erlaubt ist; die übrigen werden mit Nummer gemeldet. Der Server
  // ändert alle oder keine.
  const runBulkStatus = async (ziel: 'IN_PRODUKTION' | 'GELIEFERT') => {
    const auswahl = bulk.selectedItems;
    const passend = auswahl.filter((o) => SAMMEL_ERLAUBT_AB[ziel].includes(o.status));
    const rest = auswahl.filter((o) => !SAMMEL_ERLAUBT_AB[ziel].includes(o.status));
    const zielText = orderStatusLabel(ziel);
    if (passend.length === 0) {
      toast.error(`Keine der ${auswahl.length} markierten Bestellungen kann auf „${zielText}" gesetzt werden`);
      return;
    }
    setBulkBusy(true);
    try {
      await salesApi.bulkUpdateStatus(passend.map((o) => o.id), ziel);
      await invalidateOrderViews(queryClient);
      bulk.clearSelection();
      toast.success(`${passend.length} von ${auswahl.length} Bestellung(en) auf „${zielText}" gesetzt`);
      if (rest.length > 0) {
        toast.warning(
          `Nicht geändert: ${rest.map((o) => `${nummer(o)} (${orderStatusLabel(o.status)})`).join(', ')}`,
        );
      }
    } catch (e) {
      // Server hat abgelehnt (alle oder keine): nichts geändert, aber die
      // Liste ist offenbar veraltet — neu laden, damit der Status stimmt.
      await invalidateOrderViews(queryClient);
      toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden'));
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkReady = () => runBulkStatus('IN_PRODUKTION');
  const handleBulkDelivered = () => runBulkStatus('GELIEFERT');
```

In der Sammelleiste (`<BulkActionBar …>`, Z. 279-300): jedem der drei `<button>` die Zeile `disabled={bulkBusy}` direkt nach `onClick={…}` hinzufügen und beim mittleren Knopf den Text `In Produktion` durch `Gepackt` ersetzen.

`OrderListProps` (Z. 326-328):

```ts
  onConfirm: (order: Order) => Promise<void>;
  onMarkReady: (order: Order) => Promise<void>;
  onMarkDelivered: (order: Order) => Promise<void>;
```

In `OrderList` die Props an `OrderCard` (Z. 387-394) ersetzen — die Karte entscheidet jetzt selbst nach Status:

```tsx
                onMarkReady={() => onMarkReady(order)}
                onMarkDelivered={() => onMarkDelivered(order)}
```

`onConfirm` (Z. 384-386) bleibt unverändert. Den `ExcelImport`-Block im Seitenkopf (`onImported=…`, seit `efcea00` mit „Bestellungen importieren") nicht anfassen.

- [ ] **Step 3: Sales.tsx**

Nach dem Import aus `'../components/ui'` (nach Task 6) zwei Zeilen:

```ts
import { getErrorMessage } from '../services/errors';
import { invalidateOrderViews } from '../services/orderQueries';
```

`markReadyMutation` und `markDeliveredMutation` (Z. 54-74) ersetzen durch:

```ts
  const markReadyMutation = useMutation({
    mutationFn: (id: string) => salesApi.updateOrderStatus(id, 'IN_PRODUKTION'),
    onSuccess: async () => {
      await invalidateOrderViews(queryClient);
      toast.success('Bestellung gepackt');
    },
    onError: (e) => {
      toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden'));
    },
  });

  const markDeliveredMutation = useMutation({
    mutationFn: (id: string) => salesApi.updateOrderStatus(id, 'GELIEFERT'),
    onSuccess: async () => {
      await invalidateOrderViews(queryClient);
      toast.success('Bestellung als geliefert markiert');
    },
    onError: (e) => {
      toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden'));
    },
  });
```

`OrderCard`-Props (Z. 244-245) auf `mutateAsync`, damit die Karte bis zur Antwort sperrt:

```tsx
                onMarkReady={() => markReadyMutation.mutateAsync(order.id)}
                onMarkDelivered={() => markDeliveredMutation.mutateAsync(order.id)}
```

Detail-Modal: Knopftext `In Produktion setzen` (Z. 376) → `Gepackt`; die Bedingung des Liefern-Knopfs (Z. 379) `{selectedOrder.status === 'IN_PRODUKTION' && (` ersetzen durch:

```tsx
              {(selectedOrder.status === 'BESTAETIGT' || selectedOrder.status === 'IN_PRODUKTION') && (
```

- [ ] **Step 4: EditOrderModal.tsx — Storno bei Gepackt**

Backend erlaubt seit Task 1 IN_PRODUKTION → STORNIERT; Positionen hinzufügen bleibt auf Entwurf und Bestätigt beschränkt (`sales.py` `add_order_line`). Deshalb zwei Flags statt einem.

Nach Z. 7 (`import { getErrorMessage } …`):

```ts
import { invalidateOrderViews } from '../../services/orderQueries';
```

Z. 151 (`const stornierbar = …`) ersetzen durch:

```ts
    // Positionen ergänzen: nur Entwurf und Bestätigt (sales.py add_order_line).
    const positionenErweiterbar = currentOrder?.status === 'ENTWURF' || currentOrder?.status === 'BESTAETIGT';
    // Stornieren zusätzlich bei Gepackt — Bestand wird erst bei Geliefert gebucht.
    const stornierbar = positionenErweiterbar || currentOrder?.status === 'IN_PRODUKTION';
```

`stornierbar` → `positionenErweiterbar` an genau drei Stellen: `enabled: open && stornierbar,` (Z. 156), `if (!currentOrder || !stornierbar || priceLoading || priceError) return;` (Z. 241, in `addLine`), `{stornierbar ? <div className="rounded-lg bg-gray-50 …` (Z. 315, Block „Position hinzufügen"). `cancelOrder` (Z. 262) und der Storno-Abschnitt (Z. 354) behalten `stornierbar`.

In `refreshOrder` (Z. 161) und in `cancelOrder` (Z. 267) jeweils `await queryClient.invalidateQueries({ queryKey: ['orders'] });` ersetzen durch `await invalidateOrderViews(queryClient);` (in `refreshOrder` mit Kommentar `// Lieferdatum und Positionen stehen auch im Tagesplan`).

Den Hinweistext (Z. 359-361) ersetzen durch:

```tsx
                        {istStorniert ? 'Diese Bestellung ist bereits storniert.'
                            : 'Eine gelieferte oder fakturierte Bestellung kann nicht mehr storniert werden.'}
```

- [ ] **Step 5: Prüfen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe.

Run: `cd frontend && grep -rn "In Produktion" src/pages src/components | grep -v "In Produktion ab"`
Erwartet: keine Ausgabe.

Run: `cd frontend && grep -n "toISOString()\.split" src/pages/Orders.tsx src/pages/Tagesplan.tsx`
Erwartet: keine Ausgabe (die neuen Kommentare erwähnen `toISOString()` ohne `.split`).

Run: `cd frontend && grep -rn "queryKey: \['orders'\] })" src/pages/Orders.tsx src/pages/Sales.tsx src/components/domain/EditOrderModal.tsx`
Erwartet: genau ein Treffer, `Orders.tsx` in der Zeile `onImported={() => queryClient.invalidateQueries({ queryKey: ['orders'] })}` (Import legt Bestellungen an, wechselt keinen Status; bewusst unverändert, um die Zeile aus `efcea00` nicht zu berühren).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/domain/OrderCard.tsx frontend/src/pages/Orders.tsx frontend/src/pages/Sales.tsx frontend/src/components/domain/EditOrderModal.tsx
git commit -m "fix(bestellungen): Sammelaktionen melden ehrlich, Gepackt und Geliefert getrennt, Storno bei Gepackt"
```

---

### Task 9: Belege — Liefertag beim Quittieren wählbar, Tagesplan lädt mit

**Files:**
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx:8-9` (Import), `:53-54`, `:123-128`, `:130-132`, `:253-274`
- Modify: `frontend/src/types/index.ts:188` (`interface Order`)

**Interfaces:**
- Consumes: `documentsApi.markDelivered(noteId, { signed_by, actual_delivery_date })` (gibt es schon, `api.ts:1388`), Backend Task 2, `invalidateOrderViews` (Task 7). `actual_delivery_date` liefert die API schon (`OrderResponse`, `schemas/order.py:191`), nur dem Typ `Order` (`types/index.ts:178-197`) fehlte es.

Verhalten: Neben „Unterzeichnet von…" steht ein Datumsfeld „Liefertag" (höchstens heute). Vorschlag: Ist die Bestellung schon geliefert, ihr `actual_delivery_date` — der Server überschreibt es nie (`trage_lieferdatum_nach`), und der Sammellauf nimmt `note.actual_delivery_date` als Leistungsdatum (`invoices.py:539`, `:667`); ein abweichender Vorschlag hätte Lieferschein und Bestellung mit zwei Daten hinterlassen. Sonst der geplante Liefertag, wenn er in der Vergangenheit liegt, sonst heute. Das deckt Gernots Altfälle (LÜCKEN 4: Bestellungen vom 07./08.10. nachträglich quittieren) ohne Tipparbeit ab. Steht die Bestellung auf Entwurf oder Storniert, zeigt die Zeile statt Feldern und Knopf einen Hinweis — der Server lehnt das Quittieren dort seit Task 2 ab, der Knopf führte nur noch zu einem 400-Toast. (`order` ist der Stand beim Öffnen des Dialogs, wie bisher.)

- [ ] **Step 1: Typ `Order`**

In `frontend/src/types/index.ts`, `interface Order`, den Zwei-Zeilen-Block (kommt in der Datei genau einmal vor)

```ts
  liefer_datum: string
  status: OrderStatus
```

ersetzen durch

```ts
  liefer_datum: string
  // Tatsächlicher Liefertag (gesetzt beim Wechsel auf GELIEFERT)
  actual_delivery_date?: string | null
  status: OrderStatus
```

- [ ] **Step 2: Änderungen im Dialog**

Nach der in Task 6 eingefügten Importzeile (`belegStatusLabel`):

```ts
import { invalidateOrderViews } from '../../services/orderQueries';
```

In `invalidate()` die Zeile `queryClient.invalidateQueries({ queryKey: ['orders'] });` (Z. 54) ersetzen durch:

```ts
    // Quittieren setzt die Bestellung auf Geliefert — Tagesplan mit neu laden
    void invalidateOrderViews(queryClient);
```

`markDeliveredMutation` (Z. 123-125, `mutationFn`) ersetzen durch:

```ts
  const markDeliveredMutation = useMutation({
    mutationFn: ({ noteId, signed_by, actual_delivery_date }: { noteId: string; signed_by: string; actual_delivery_date: string }) =>
      documentsApi.markDelivered(noteId, { signed_by, actual_delivery_date }),
```

(`onSuccess`/`onError` Z. 126-127 bleiben.)

Die Zeile `if (!order) return null;` (Z. 132, direkt unter `const [signedByInput, setSignedByInput] = …`) ersetzen durch:

```tsx
  // Tatsächlicher Liefertag je Lieferschein (Eingabe des Anwenders).
  const [lieferdatumInput, setLieferdatumInput] = useState<Record<string, string>>({});

  if (!order) return null;

  const heute = new Date().toLocaleDateString('sv-SE');
  // Vorschlag: Ist die Bestellung schon geliefert, ihr Lieferdatum — der Server
  // überschreibt es nie, Lieferschein und Bestellung sollen gleich lauten.
  // Sonst der geplante Liefertag, höchstens heute (Nachtragen, LÜCKEN 4).
  const vorschlagLieferdatum =
    order.actual_delivery_date
    ?? (order.liefer_datum && order.liefer_datum < heute ? order.liefer_datum : heute);
  // Quittieren setzt die Bestellung auf Geliefert; aus Entwurf und Storniert
  // lehnt der Server das ab (order_status_service.setze_status).
  const quittierbar = order.status !== 'ENTWURF' && order.status !== 'STORNIERT';
```

(Der `useState` muss vor dem frühen `return` stehen — Hook-Regel.)

Die Bedingung der Quittieren-Zeile (Z. 253, `{n.status !== 'GELIEFERT' && (` direkt vor `<div className="mt-2 flex items-center gap-2">`) ersetzen durch einen Hinweis für nicht quittierbare Bestellungen und die bisherige Zeile nur für quittierbare:

```tsx
                  {n.status !== 'GELIEFERT' && !quittierbar && (
                    <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                      {order.status === 'STORNIERT'
                        ? 'Bestellung ist storniert, der Lieferschein kann nicht quittiert werden.'
                        : 'Erst die Bestellung bestätigen, dann den Lieferschein quittieren.'}
                    </p>
                  )}
                  {n.status !== 'GELIEFERT' && quittierbar && (
                    <div className="mt-2 flex items-center gap-2">
```

(Rest der Zeile bis zum schließenden `)}` Z. 274 bleibt; nur `{n.status !== 'GELIEFERT' && (` kommt in der Datei genau einmal vor.)

In der Quittieren-Zeile (Z. 255-269) zwischen dem `Input` „Unterzeichnet von…" und dem `Button` „Quittieren" ein Datumsfeld einfügen und den `mutate`-Aufruf erweitern:

```tsx
                      <Input
                        type="date"
                        aria-label="Liefertag"
                        title="Tatsächlicher Liefertag"
                        max={heute}
                        value={lieferdatumInput[n.id] ?? vorschlagLieferdatum}
                        onChange={(e) => setLieferdatumInput((p) => ({ ...p, [n.id]: e.target.value }))}
                      />
                      <Button
                        size="sm"
                        icon={<CheckCheck className="w-3 h-3" />}
                        loading={markDeliveredMutation.isPending}
                        onClick={() =>
                          markDeliveredMutation.mutate({
                            noteId: n.id,
                            signed_by: signedByInput[n.id] || '',
                            actual_delivery_date: lieferdatumInput[n.id] || vorschlagLieferdatum,
                          })
                        }
                      >
```

- [ ] **Step 3: Prüfen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe.

Run: `cd frontend && grep -n "actual_delivery_date" src/types/index.ts && grep -c "quittierbar" src/components/domain/OrderDocumentsModal.tsx`
Erwartet: ein Treffer in `types/index.ts` (im `interface Order`), Zählwert 3.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/domain/OrderDocumentsModal.tsx
git commit -m "feat(belege): Liefertag beim Quittieren wählbar, Hinweis statt Knopf bei Entwurf/Storniert, Tagesplan lädt nach Quittieren neu"
```

---


## Abschnitt P2: A4 — Knopf „Gepackt" im Tagesplan, Sortenbedarf ohne gepackte Bestellungen — Tasks 10–15

**Ziel:** In der Karte „Verpacken" setzt ein Knopf „Gepackt" die Bestellung von BESTAETIGT auf IN_PRODUKTION (Oberfläche „Gepackt"). Gepackte fallen aus „Verpacken", aus dem Sortenbedarf und aus der Packliste der Produktionsseite, bleiben aber in „Ausliefern" und werden unter „Bereits gepackt" benannt. Kein neuer Status, keine neue Spalte. Der ursprüngliche Fix „nur umbenennen" ist widerlegt (A4.md): Beim Packen standen die Bestellungen auf BESTAETIGT, IN_PRODUKTION war ein Durchgangszustand von unter einer Sekunde.

**Voraussetzung:** Tasks 1–9 vollständig. Task 10 Step 0 prüft das, bevor P2 eine Datei ändert. P2 ändert `sales.py`, `documents.py`, `Badge.tsx`, `statusLabels.ts`, `Orders.tsx`, `OrderCard.tsx`, `EditOrderModal.tsx` und `OrderDocumentsModal.tsx` nicht.

**Befund (A4.md, am Code bestätigt):**
- Eine Aktion „gepackt" gibt es nirgends. Beim Packen stehen Bestellungen auf `BESTAETIGT` und zählen deshalb im Sortenbedarf (`GET /production/packaging-plan`, `production.py:643-771`).
- day-plan (`production.py:515-526`) lädt mit **einer** Abfrage beide Karten, `verpacken` (Z. 548) und `ausliefern` (Z. 549). Ein Statusfilter im SQL nähme gepackte Bestellungen auch aus „Ausliefern". Deshalb wird in Python gefiltert.
- `packaging-plan` speist zwei Oberflächen: den Sortenbedarf im Tagesplan (`komponenten`, Tagesplan.tsx:46-50, 312-339) und den Tab „Verpackungsplan" der Produktionsseite (`items`, Production.tsx:96-100, 425-470).
- **Bestand wird erst bei `GELIEFERT` gebucht** (geprüft): `deduct_inventory_for_order` wird nur in `sales.py:1229-1246` (Zweig `new_status == GELIEFERT`) und in `documents.py:308-321` (Quittieren, nur bei Übergang nach `GELIEFERT`) aufgerufen, nach Task 1 nur noch in `setze_status` beim Übergang nach `GELIEFERT`. `reserve_for_order` (`inventory_service.py:229`) hat keinen Aufrufer. „Gepackt" bucht also nichts, und ein Storno aus „Gepackt" muss nichts zurückbuchen. Task 10 hält das fest. Die Prüfung dort ist aussagekräftig, weil `deduct_inventory_for_order` `inventory_deducted_at` auch ohne Produktzeilen setzt (`order_fulfillment_service.py:213-214`).
- `production_staff` erreicht den Status-Endpunkt: Der Sales-Router hängt an `_deps_auftraege = _rollen(SALES, BUCHHALTUNG, PLANER, PRODUKTION)` (`main.py:122`), Lesen und Schreiben. Task 10 hält das fest.
- Die Anzeige veraltet: `main.tsx:26-28` setzt `staleTime` 60 s und `refetchOnWindowFocus: false`. Ein offenes Hallen-Tablet sieht deshalb nie, was ein anderes Gerät gepackt hat.

**Weitere Stellen, die mit `IN_PRODUKTION` rechnen.** Nach der Umdeutung ist `IN_PRODUKTION` „gepackt": geerntet, im Karton, nicht geliefert.

| Stelle | Was sie mit `IN_PRODUKTION` tut | Nach der Umdeutung |
|---|---|---|
| `services/forecast_engine.py:28-41` `_fetch_historical_data` | Verkaufshistorie: alle Status außer `STORNIERT`, Liefertag ≤ heute | richtig, gepackte Ware ist verkauft |
| `api/v1/forecasting.py:793ff` `generate_production_suggestions`, `:1125` `_calculate_subscription_demand` | lesen keine Bestellungen (Forecast-Tabelle bzw. Abos) | nicht betroffen |
| `tasks/forecast_tasks.py:192-202` `calculate_forecast_accuracy` | filtert `!= STORNIERT` | nicht betroffen. **Nebenbefund außerhalb A4:** Der Job nutzt `Order.liefer_datum` (gibt es nicht) und `OrderLine.menge` (Python-Property, keine Spalte). Er scheitert, sobald es Forecasts von gestern gibt; geplant in `scheduler_service.py:96` |
| `tasks/report_tasks.py:208-226` | Umsatzbericht über `Order.liefer_datum`, ohne Statusfilter | nicht betroffen, gleicher Altcode-Befund |
| `api/v1/sales.py:691` Sammelfilter `OFFEN`, `:840-842` Kreditlimit | zählen `ENTWURF`, `BESTAETIGT`, `IN_PRODUKTION` als offen | richtig, gepackt ist nicht geliefert und nicht berechnet. Task 10 hält den Sammelfilter fest. Das Kreditlimit nutzt dieselbe Statusliste, nur am Code geprüft |
| **`frontend/src/pages/Dashboard.tsx:60-64`** Kennzahl „Offene Bestellungen" (angezeigt `:165-166` und `:345`) | `salesApi.listOrders({ status: 'BESTAETIGT' })`, zählt `total` | **betroffen.** Jede gepackte Bestellung fiele über Nacht aus der Kennzahl, obwohl sie weder geliefert noch berechnet ist. **Task 15** zählt `BESTAETIGT` + `IN_PRODUKTION` |
| **`api/v1/imports.py:122`, `:555-575`** Bestellimport | Status-Spalte erlaubt `IN_PRODUKTION`, auch mit Lieferdatum in der Zukunft. Abgelehnt wird nur `GELIEFERT`/`FAKTURIERT` mit Zukunftsdatum | **betroffen, nicht in P2.** So importierte Bestellungen fielen still aus Sortenbedarf und „Verpacken". Das ist dasselbe Unterpack-Risiko wie A4.md Punkt 8. Siehe Runbook A und Entscheidung E2 (Import-Härtung, A6-Rest) |
| `api/v1/production.py:594ff` Dashboard-Zusammenfassung, day-plan „Ernte" (`:492-510`) | lesen keine Bestellungen (Wachstumschargen) | nicht betroffen. Einen Erntebedarf aus Bestellungen gibt es im Code nicht |
| `models/order.py:218-220` `can_be_cancelled` | erlaubt Storno aus `IN_PRODUKTION` | passt zur Entscheidung. Die Property hat keinen Aufrufer, maßgeblich ist die Übergangsregel aus Task 1 |
| `components/domain/EditOrderModal.tsx:151` `stornierbar` | sperrt Storno bei `IN_PRODUKTION` | **betroffen**, behoben durch Task 8 (Step 4) |
| `api/v1/invoices.py:533` Sammellauf | `!= STORNIERT` | Paket 1 (Task 22), nicht P2 |

**Review Focus (P2, getestet):**
1. **Ausliefern behält Gepackte.** Der naheliegende SQL-Fix würde sie dem Fahrer wegnehmen. Getestet in Task 11 (`test_gepackte_bleibt_in_ausliefern`, von Anfang an grün).
2. **Same-Day:** Pack- und Liefertag fallen zusammen. Vor dem Packen steht die Bestellung in beiden Listen (`test_gernot_260817.py:200-206`, unverändert), danach nur noch in „Ausliefern". Getestet in Task 11.
3. **Ein Entwurf ist nicht packbar** (`ENTWURF → IN_PRODUKTION` bleibt verboten). Der Knopf erscheint nur bei `packbar`. Getestet in Task 10 und Task 11.
4. **Sortenbedarf und Packliste rechnen mit denselben Bestellungen** wie die Verpacken-Karte, sonst widersprechen sie sich auf derselben Seite (A4.md, Nebenwirkung 1). Getestet in Task 12. Der Hinweis „ohne N bereits gepackte" im Sortenbedarf zählt aus derselben Liste wie „Bereits gepackt" (Task 13 Step 8).
5. **Kein Bestand beim Packen.** Getestet in Task 10.
6. **Gepackt bleibt „offen"**: Filter OFFEN (Task 10), Dashboard-Kennzahl (Task 15), Storno im Bestelldialog (Task 8; geprüft in Task 10 Step 0 und Browser-Prüfung 5).
7. **Kein Doppelklick-Fehler:** Der Knopf bleibt gesperrt, bis der Tagesplan neu geladen ist (Task 13 Step 4).

**Bestehende Tests:** P2 ändert **keine** bestehende Erwartung.
- `test_gernot_bugfixes.py:140` erwartet `order_ref["status"] == "Entwurf"` (nach Task 4 `"ENTWURF"`) im packaging-plan. P2 lässt `status` unverändert, das Format gehört P1.
- `test_gernot_260817.py:187-206` zählt `verpacken`/`ausliefern`. Dort entstehen nur Entwürfe, die nie gepackt werden. Sie stehen weiter in `verpacken`, und die Same-Day-Bestellung steht weiter in beiden Listen. Den gepackten Fall deckt der neue Test `test_same_day_gepackt` ab.
- `test_gernot_260824.py:104-116` (`verpacken[0]` trägt Positionen) und `test_phase4_verbesserungen.py:120-126` arbeiten mit ungepackten Bestellungen. Neue Schlüssel stören dort nicht, gemessen grün.
- `test_import_bestellungen_zukunft.py:109-111` erwartet die importierte `BESTAETIGT`-Bestellung in `verpacken`. Sie bleibt dort, gemessen grün.
- `test_features.py:170-175` (bestätigte Bestellung im packaging-plan): bleibt grün, weil `BESTAETIGT` in `_NOCH_ZU_PACKEN` steht.
- **P1-Tests in derselben Datei** (`TestStatusregel`, `TestLieferscheinQuittieren`, `TestSammelStatus`, `TestTagesplanAusliefern`, `TestFehlertexte`): Keiner erwartet IN_PRODUKTION in `verpacken`. Gemessen auf dem P1-Probestand (37 P1-Tests): alle grün mit P2. Die zwei seither ergänzten P1-Tests (`test_storno_nach_gepackt_bucht_keinen_bestand`, `test_bestandsfehler_laesst_lieferschein_offen`) lesen `verpacken` nicht. Abgesichert durch den Lauf über die ganze Datei in Task 10 Step 0, Task 11 Step 7 und Task 12 Step 6.

---

### Task 10: Charakterisierung — was „Gepackt" heute schon bedeutet

**Files:**
- Modify: `backend/tests/test_gernot_261008_paket2.py` (Task 1 hat sie angelegt)

**Interfaces:**
- Consumes: Fixture `client` (`tests/conftest.py:58-82`), `TestingSessionLocal` (`tests/conftest.py:23`), `_als` und `ALLE_ROLLEN` aus `tests/test_rollen.py:18-29`.
- Produces: Fixture `_a4_ohne_celery` und die Helfer `_a4_bestellung(client, liefertag, *, bestaetigen=True, produkt="Erbsen-Schale", menge=5, **extra) -> dict`, `_a4_status(client, order, status, reason=None) -> Response`, `_a4_packen(client, order) -> dict`, `_a4_tagesplan(client, tag) -> dict`, `_a4_packplan(client, tag) -> dict` und `_a4_nummern(zeilen) -> list[str]`. Tasks 11 und 12 nutzen sie weiter.
- Unverändert: kein Produktivcode.

Alle Tests dieses Tasks sind **Charakterisierungstests und von Anfang an grün** — der Vertragstest `test_gepackte_bestellung_laesst_sich_stornieren` seit Task 1. Sie halten fest, worauf sich der Knopf verlässt: bestehender Endpunkt, Übergangsregel, keine Bestandsbuchung, Audit-Log mit Grund, Zugriff der Halle.

- [ ] **Step 0: Voraussetzungen prüfen (vor jeder Änderung)**

Jeder Run beginnt im Worktree-Wurzelverzeichnis (`cd backend` aus einem vorigen Run gilt nicht weiter). Nacheinander:

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -q`
Erwartet: **0 failed, 39 passed** (Tasks 1–5). Fehlt die Datei, fehlt Task 1. Ist ein Test rot: **stoppen und die Ausgabe melden.** Dann ist der Stand nach Task 9 nicht sauber, und das ist nicht Sache von P2.

Run: `grep -n "const stornierbar" frontend/src/components/domain/EditOrderModal.tsx`
Erwartet: genau eine Zeile, die `IN_PRODUKTION` enthält (Task 8: `const stornierbar = positionenErweiterbar || currentOrder?.status === 'IN_PRODUKTION';`). Sonst **stoppen und melden**: „Task 8 Step 4 fehlt. Gepackte Bestellungen wären nach P2 in der Oberfläche nicht stornierbar."

Run: `grep -rn "IN_PRODUKTION: 'Gepackt'" frontend/src/components/ui/`
Erwartet: mindestens ein Treffer (Task 6, `statusLabels.ts`). Sonst stoppen und melden.

Run: `grep -ln "invalidateOrderViews" frontend/src/pages/Orders.tsx frontend/src/pages/Sales.tsx frontend/src/components/domain/EditOrderModal.tsx frontend/src/components/domain/OrderDocumentsModal.tsx`
Erwartet: alle vier Pfade, Reihenfolge egal. Sonst stoppen und melden.

Run: `grep -c "_AUSGELIEFERT" backend/app/api/v1/production.py`
Erwartet: mindestens `2` (Task 4: Definition und Abfrage). Sonst stoppen und melden.

- [ ] **Step 1: Tests schreiben**

Existiert `backend/tests/test_gernot_261008_paket2.py` wider Erwarten noch nicht, stoppen (siehe Step 0). Den folgenden Block **ans Dateiende** anhängen. Doppelte Imports aus anderen Abschnitten schaden nicht.

```python
# ===========================================================================
# P2 / A4 — Knopf "Gepackt" im Tagesplan
#
# IN_PRODUKTION heißt in der Oberfläche "Gepackt". Gepackte Bestellungen
# fallen aus "Verpacken" und aus dem Sortenbedarf, bleiben aber in
# "Ausliefern". Kein neuer Status, keine neue Spalte.
# ===========================================================================
import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import TestingSessionLocal


@pytest.fixture()
def _a4_ohne_celery():
    """Anlegen, Bestätigen und Stornieren stoßen über Celery ein Forecast-Update an.

    Ohne Redis wartet jeder dieser Aufrufe rund 20 s auf Wiederholungen. Für
    diese Tests ist das Forecast-Update ohne Belang, deshalb abgeklemmt.
    """
    from unittest.mock import patch
    with patch("app.tasks.forecast_tasks.update_forecast_from_order.delay"):
        yield


def _a4_bestellung(client, liefertag, *, bestaetigen=True, produkt="Erbsen-Schale", menge=5, **extra):
    """Bestellung mit einer Position ohne Produktstamm (Sortenbedarf-Schlüssel = Name)."""
    kunde = client.post("/api/v1/sales/customers", json={
        "name": f"Packkunde {uuid.uuid4().hex[:6]}", "typ": "GASTRO",
    })
    assert kunde.status_code == 201, kunde.text
    payload = {
        "customer_id": kunde.json()["id"],
        "requested_delivery_date": liefertag.isoformat(),
        "lines": [{"product_name": produkt, "quantity": menge, "unit": "STK",
                   "unit_price": 2.5, "tax_rate": "REDUZIERT"}],
    }
    payload.update(extra)
    r = client.post("/api/v1/sales/orders", json=payload)
    assert r.status_code == 201, r.text
    order = r.json()
    if bestaetigen:
        r = client.post(f"/api/v1/sales/orders/{order['id']}/confirm")
        assert r.status_code == 200, r.text
        order = r.json()
    return order


def _a4_status(client, order, status, reason=None):
    """Derselbe Aufruf wie der Knopf im Tagesplan (salesApi.updateOrderStatus)."""
    return client.post(f"/api/v1/sales/orders/{order['id']}/status",
                       json={"status": status, "reason": reason})


def _a4_packen(client, order):
    r = _a4_status(client, order, "IN_PRODUKTION", "Im Tagesplan als gepackt markiert")
    assert r.status_code == 200, r.text
    return r.json()


def _a4_tagesplan(client, tag):
    r = client.get("/api/v1/production/day-plan", params={"target_date": tag.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _a4_packplan(client, tag):
    r = client.get("/api/v1/production/packaging-plan", params={"target_date": tag.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _a4_nummern(zeilen):
    return sorted(z["order_number"] for z in zeilen)


@pytest.mark.usefixtures("_a4_ohne_celery")
class TestGepacktBedeutung:
    """Charakterisierung: was der Statuswechsel nach IN_PRODUKTION heute schon tut.

    Diese Tests sind von Anfang an grün. Sie halten fest, worauf der Knopf
    "Gepackt" im Tagesplan sich verlässt.
    """

    def test_bestaetigte_bestellung_laesst_sich_packen(self, client):
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        assert _a4_packen(client, order)["status"] == "IN_PRODUKTION"

    def test_entwurf_laesst_sich_nicht_packen(self, client):
        """ENTWURF → IN_PRODUKTION bleibt verboten; der Knopf erscheint nur bei BESTAETIGT."""
        order = _a4_bestellung(client, date.today() + timedelta(days=1), bestaetigen=False)
        r = _a4_status(client, order, "IN_PRODUKTION")
        assert r.status_code == 400, r.text

    def test_packen_bucht_keinen_bestand(self, client):
        """Bestand wird erst bei GELIEFERT gebucht, nicht beim Packen."""
        from app.models.order import Order
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _a4_packen(client, order)
        with TestingSessionLocal() as db:
            o = db.get(Order, uuid.UUID(order["id"]))
            assert o.inventory_deducted_at is None
            assert o.actual_delivery_date is None

    def test_packen_steht_im_audit_log(self, client):
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _a4_packen(client, order)
        log = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        eintrag = [e for e in log if e["action"] == "STATUS_CHANGE"]
        assert eintrag and eintrag[0]["new_values"] == {"status": "IN_PRODUKTION"}
        assert eintrag[0]["reason"] == "Im Tagesplan als gepackt markiert"

    def test_gepackte_bestellung_bleibt_offen(self, client):
        """Der Sammelfilter OFFEN zählt IN_PRODUKTION weiter mit — richtig, gepackt
        ist nicht geliefert. (Das Kreditlimit, sales.py:840-842, nutzt dieselbe
        Statusliste; am Code geprüft, hier nicht getestet.)"""
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _a4_packen(client, order)
        r = client.get("/api/v1/sales/orders", params={"status": "OFFEN"})
        assert r.status_code == 200, r.text
        assert [o["order_number"] for o in r.json()["items"]] == [order["order_number"]]

    def test_halle_darf_packen(self, client):
        """Der Knopf sitzt auf dem Hallen-Tablet: production_staff muss durchkommen."""
        from tests.test_rollen import _als, ALLE_ROLLEN
        order = _a4_bestellung(client, date.today() + timedelta(days=1))
        _als(["production_staff"])
        try:
            r = _a4_status(client, order, "IN_PRODUKTION")
        finally:
            _als(ALLE_ROLLEN)
        assert r.status_code == 200, r.text

    def test_gepackte_bestellung_laesst_sich_stornieren(self, client):
        """Vertragstest zu P1 (Übergangstabelle): gepackt, aber nicht geliefert → stornierbar.

        Grün, sobald P1 IN_PRODUKTION → STORNIERT erlaubt. Rot heißt: P1 fehlt.
        Die Oberfläche (EditOrderModal) prüft Step 0 und die Abnahme, nicht dieser Test.
        """
        morgen = date.today() + timedelta(days=1)
        order = _a4_bestellung(client, morgen)
        _a4_packen(client, order)
        r = _a4_status(client, order, "STORNIERT", "Kunde hat abgesagt")
        assert r.status_code == 200, r.text
        assert _a4_tagesplan(client, morgen)["ausliefern"] == []
```

- [ ] **Step 2: Grün bestätigen (Charakterisierung)**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k TestGepacktBedeutung`
Erwartet: 7 passed in wenigen Sekunden.
- Ist **nur** `test_gepackte_bestellung_laesst_sich_stornieren` rot (`assert 400 == 200`, Text „Ungültiger Statusübergang: IN_PRODUKTION → STORNIERT"), dann fehlt Task 1. **Stoppen und melden.** Den Übergang nicht hier ergänzen, er gehört in die gemeinsame Regel aus Task 1.
- Ist ein anderer Test rot, weicht der Code vom Stand nach Task 9 ab. Stoppen und die exakte Ausgabe melden.

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -q`
Erwartet: 0 failed, 46 passed (39 + 7).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_gernot_261008_paket2.py
git commit -m "test(tagesplan): Bedeutung von 'Gepackt' (IN_PRODUKTION) festgehalten"
```

---

### Task 11: Tagesplan — Gepackte raus aus „Verpacken", drin in „Ausliefern"

**Files:**
- Modify: `backend/app/api/v1/production.py:19-22` (Modulkonstanten nach `_AUSGELIEFERT` aus Task 4)
- Modify: `backend/app/api/v1/production.py` `get_day_plan`: `_order_ref` (nach `"positionen"`, `efcea00` Z. 538) und die Aufteilung `verpacken` (`efcea00` Z. 548; P1-Stand Z. 555–558)
- Modify: `backend/app/api/v1/production.py` `get_day_plan`: Rückgabe-Dict (`"verpacken": verpacken,`)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: Helfer aus Task 10.
- Produces:
  - `production._NOCH_ZU_PACKEN = (OrderStatus.ENTWURF, OrderStatus.BESTAETIGT)` und `production._SCHON_GEPACKT = (OrderStatus.IN_PRODUKTION, OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)`. Task 12 nutzt beide.
  - `GET /api/v1/production/day-plan`: Jede Zeile in `verpacken`, `verpacken_erledigt` und `ausliefern` trägt zusätzlich `packbar: bool` (= Status `BESTAETIGT`). Neuer Schlüssel `verpacken_erledigt: list` mit den Bestellungen des Packtags, die gepackt, geliefert oder fakturiert sind. Gleiche Zeilenform wie `verpacken`.
- Unverändert: die SQL-Abfrage (P1-Stand mit `*_AUSGELIEFERT`), `ausliefern = …` und der Schlüssel `status` in `_order_ref` (gehört P1).

- [ ] **Step 1: Failing Tests schreiben**

Ans Dateiende von `backend/tests/test_gernot_261008_paket2.py`:

```python
@pytest.mark.usefixtures("_a4_ohne_celery")
class TestTagesplanGepackt:
    """A4: gepackte Bestellungen raus aus "Verpacken", drin in "Ausliefern"."""

    def test_gepackte_faellt_aus_verpacken(self, client):
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        offen = _a4_bestellung(client, morgen)
        gepackt = _a4_bestellung(client, morgen)
        _a4_packen(client, gepackt)

        plan = _a4_tagesplan(client, heute)
        assert _a4_nummern(plan["verpacken"]) == [offen["order_number"]]
        assert _a4_nummern(plan["verpacken_erledigt"]) == [gepackt["order_number"]]

    def test_gepackte_bleibt_in_ausliefern(self, client):
        morgen = date.today() + timedelta(days=1)
        offen = _a4_bestellung(client, morgen)
        gepackt = _a4_bestellung(client, morgen)
        _a4_packen(client, gepackt)

        plan = _a4_tagesplan(client, morgen)
        assert _a4_nummern(plan["ausliefern"]) == sorted([offen["order_number"], gepackt["order_number"]])

    def test_same_day_gepackt(self, client):
        """Same-Day: Pack- und Liefertag sind derselbe Tag. Nach dem Packen nur noch
        unter Ausliefern (vgl. test_gernot_260817.py::test_same_day_bestellung_wird_heute_verpackt)."""
        heute = date.today()
        order = _a4_bestellung(client, heute)
        _a4_packen(client, order)

        plan = _a4_tagesplan(client, heute)
        assert plan["verpacken"] == []
        assert _a4_nummern(plan["verpacken_erledigt"]) == [order["order_number"]]
        assert _a4_nummern(plan["ausliefern"]) == [order["order_number"]]

    def test_packbar_nur_wenn_bestaetigt(self, client):
        """Der Knopf "Gepackt" braucht BESTAETIGT; ein Entwurf muss erst bestätigt werden."""
        morgen = date.today() + timedelta(days=1)
        entwurf = _a4_bestellung(client, morgen, bestaetigen=False)
        bestaetigt = _a4_bestellung(client, morgen)

        zeilen = {z["order_number"]: z for z in _a4_tagesplan(client, date.today())["verpacken"]}
        assert zeilen[entwurf["order_number"]]["packbar"] is False
        assert zeilen[bestaetigt["order_number"]]["packbar"] is True

    def test_expliziter_packtag_gepackt(self, client):
        """Abweichender Packtag: gepackt fällt auch dort aus Verpacken."""
        heute = date.today()
        order = _a4_bestellung(client, heute + timedelta(days=3), packing_date=heute.isoformat())
        _a4_packen(client, order)

        plan = _a4_tagesplan(client, heute)
        assert plan["verpacken"] == []
        assert _a4_nummern(plan["verpacken_erledigt"]) == [order["order_number"]]

    def test_gelieferte_und_fakturierte_gelten_als_erledigt(self, client):
        """P1 (Task 4) lädt GELIEFERT und FAKTURIERT für "Ausliefern" mit. Am
        Packtag stehen sie unter "Bereits gepackt", nie unter "Verpacken"."""
        heute = date.today()
        geliefert = _a4_bestellung(client, heute)
        fakturiert = _a4_bestellung(client, heute)
        for order in (geliefert, fakturiert):
            _a4_packen(client, order)
            r = _a4_status(client, order, "GELIEFERT")
            assert r.status_code == 200, r.text
        r = _a4_status(client, fakturiert, "FAKTURIERT")
        assert r.status_code == 200, r.text

        plan = _a4_tagesplan(client, heute)
        assert plan["verpacken"] == []
        assert _a4_nummern(plan["verpacken_erledigt"]) == sorted(
            [geliefert["order_number"], fakturiert["order_number"]])
```

`test_gepackte_bleibt_in_ausliefern` ist eine **Charakterisierung und von Anfang an grün**. Er schützt vor dem naheliegenden, falschen Fix im SQL.

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k TestTagesplanGepackt`
Erwartet: 5 failed, 1 passed (`test_gepackte_bleibt_in_ausliefern`). Gemessen auf dem P1-Stand:
- `test_gepackte_faellt_aus_verpacken`: `assert ['BE-…-0001', 'BE-…-0002'] == ['BE-…-0001']`. Die gepackte Bestellung steht noch in `verpacken`.
- `test_same_day_gepackt`, `test_expliziter_packtag_gepackt`: `assert [{…}] == []`.
- `test_packbar_nur_wenn_bestaetigt`: `KeyError: 'packbar'`.
- `test_gelieferte_und_fakturierte_gelten_als_erledigt`: `KeyError: 'verpacken_erledigt'`.

- [ ] **Step 3: Modulkonstanten anlegen**

In `backend/app/api/v1/production.py` direkt **nach** der Zeile `_AUSGELIEFERT = (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)` (Task 4, P1-Stand Z. 22) einfügen. `OrderStatus` ist in Z. 11 bereits importiert.

```python

# Packen (Gernot, 08.10.2026): IN_PRODUKTION heißt in der Oberfläche "Gepackt".
# Noch zu packen sind nur Entwürfe und bestätigte Bestellungen. Gepackte,
# gelieferte und fakturierte gelten für den Packtag als erledigt — sie stehen
# nicht mehr in "Verpacken" und zählen nicht im Sortenbedarf, bleiben aber in
# "Ausliefern".
_NOCH_ZU_PACKEN = (OrderStatus.ENTWURF, OrderStatus.BESTAETIGT)
_SCHON_GEPACKT = (OrderStatus.IN_PRODUKTION, OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)
```

`GELIEFERT` und `FAKTURIERT` stehen in `_SCHON_GEPACKT`, weil Task 4 beide für „Ausliefern" in die day-plan-Abfrage lädt (`_AUSGELIEFERT`). So erscheint eine am Packtag schon gelieferte oder fakturierte Bestellung unter „Bereits gepackt", statt aus der Verpacken-Karte zu verschwinden.

- [ ] **Step 4: `packbar` in `_order_ref`**

In `get_day_plan`, Funktion `_order_ref`, direkt **nach** der Zeile `"positionen": len(o.lines),` einfügen:

```python
            # Der Knopf "Gepackt" setzt BESTAETIGT → IN_PRODUKTION. Ein Entwurf
            # muss erst bestätigt werden; ENTWURF → IN_PRODUKTION ist verboten.
            "packbar": o.status == OrderStatus.BESTAETIGT,
```

Die Zeile `"status": …` direkt darüber **nicht** anfassen (P1).

- [ ] **Step 5: `verpacken` in Python trennen**

Die Belegung von `verpacken` ersetzen. P1-Stand (Task 4, Z. 555–558):

```python
    verpacken = [
        _order_ref(o) for o in orders
        if o.effective_packing_date == target_date and o.status not in _AUSGELIEFERT
    ]
```

Neu:

```python
    # Verpacken und Ausliefern kommen aus derselben Abfrage. Gepackte gehören
    # weiter zu "Ausliefern" — deshalb hier in Python trennen, nicht im SQL.
    packtag = [o for o in orders if o.effective_packing_date == target_date]
    verpacken = [_order_ref(o) for o in packtag if o.status in _NOCH_ZU_PACKEN]
    verpacken_erledigt = [_order_ref(o) for o in packtag if o.status in _SCHON_GEPACKT]
```

`_AUSGELIEFERT` bleibt danach in der Abfrage in Gebrauch. Die Zeile `ausliefern = …` direkt darunter **nicht** anfassen.

- [ ] **Step 6: Rückgabe ergänzen**

Im Rückgabe-Dict von `get_day_plan` direkt **nach** `"verpacken": verpacken,` einfügen:

```python
        "verpacken_erledigt": verpacken_erledigt,
```

- [ ] **Step 7: Grün bestätigen, P2 und ganze Datei**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k "TestGepacktBedeutung or TestTagesplanGepackt"`
Erwartet: 13 passed.
- Ist **nur** `test_gelieferte_und_fakturierte_gelten_als_erledigt` rot, mit `assert [] == ['BE-…', 'BE-…']`, dann lädt day-plan `GELIEFERT`/`FAKTURIERT` nicht (Task 4 fehlt). Stoppen und melden.

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -q` (**ohne** `-k`)
Erwartet: 0 failed, 52 passed (39 + 13). **Ist irgendein Test rot, auch aus P1: stoppen, nicht committen, die Ausgabe melden.** Ein roter P1-Test (z. B. aus `TestTagesplanAusliefern`) heißt: P1 und P2 widersprechen sich in der Regel für „Verpacken". Das entscheidet der Manager, nicht der Worker.

- [ ] **Step 8: Nachbartests**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_bugfixes.py tests/test_gernot_260824.py tests/test_phase4_verbesserungen.py tests/test_rollen.py tests/test_import_bestellungen_zukunft.py -q`
Erwartet: alle grün. Gemessen auf dem P1-Stand mit P2: 65 passed in ca. 4,5 min (Redis-Wartezeiten in diesen Dateien). Ist etwas rot: stoppen, nicht committen, melden. Den Vollauf macht Task 12.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/v1/production.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(tagesplan): gepackte Bestellungen fallen aus 'Verpacken', bleiben in 'Ausliefern'"
```

---

### Task 12: Sortenbedarf und Packliste ohne gepackte Bestellungen

**Files:**
- Modify: `backend/app/api/v1/production.py` `get_packaging_plan` (`efcea00` Z. 643–771: Docstring, Filter nach der Zeile `orders = [o for o in orders if o.effective_packing_date == target_date]`, Rückgabe)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: `_NOCH_ZU_PACKEN`, `_SCHON_GEPACKT` aus Task 11, Helfer aus Task 10.
- Produces: `GET /api/v1/production/packaging-plan`. `items` und `komponenten` enthalten nur noch Bestellungen in `_NOCH_ZU_PACKEN`. Neuer Schlüssel `gepackt: list[{"order_id": str, "order_number": str, "customer_name": str, "delivery_date": str}]` mit den Gepackten des Packtags. Die Abfrage lädt `GELIEFERT`/`FAKTURIERT` nicht (`efcea00` Z. 673, auch nach P1). `gepackt` enthält deshalb nur `IN_PRODUKTION`.
- Unverändert: die SQL-Abfrage (`efcea00` Z. 662–676) und der Schlüssel `status` in `items[].orders[]` (gehört P1).

- [ ] **Step 1: Failing Tests schreiben**

Ans Dateiende von `backend/tests/test_gernot_261008_paket2.py`:

```python
@pytest.mark.usefixtures("_a4_ohne_celery")
class TestSortenbedarfGepackt:
    """A4: Sortenbedarf und Packliste zählen nur, was noch zu packen ist."""

    def test_gepackte_zaehlt_nicht_im_sortenbedarf(self, client):
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        _a4_bestellung(client, morgen, menge=3)
        gepackt = _a4_bestellung(client, morgen, menge=5)
        _a4_packen(client, gepackt)

        plan = _a4_packplan(client, heute)
        bedarf = {k["product_name"]: k["total_quantity"] for k in plan["komponenten"]}
        assert bedarf == {"Erbsen-Schale": 3}

    def test_gepackte_zaehlt_nicht_in_der_packliste(self, client):
        """`items` speist den Tab Verpackungsplan auf der Produktionsseite."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        offen = _a4_bestellung(client, morgen, menge=3)
        gepackt = _a4_bestellung(client, morgen, menge=5)
        _a4_packen(client, gepackt)

        items = _a4_packplan(client, heute)["items"]
        assert len(items) == 1
        assert items[0]["total_quantity"] == 3
        assert [o["order_number"] for o in items[0]["orders"]] == [offen["order_number"]]

    def test_gepackte_werden_benannt(self, client):
        """Niemand soll eine Bestellung suchen müssen, die schon im Karton liegt."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        gepackt = _a4_bestellung(client, morgen)
        _a4_packen(client, gepackt)

        plan = _a4_packplan(client, heute)
        assert plan["komponenten"] == []
        assert plan["items"] == []
        assert [g["order_number"] for g in plan["gepackt"]] == [gepackt["order_number"]]
        assert plan["gepackt"][0]["order_id"] == gepackt["id"]
        assert plan["gepackt"][0]["delivery_date"] == morgen.isoformat()

    def test_bestaetigte_und_entwuerfe_zaehlen_weiter(self, client):
        """Charakterisierung: ohne Packmarke bleibt alles im Bedarf, auch Entwürfe."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        _a4_bestellung(client, morgen, menge=3)
        _a4_bestellung(client, morgen, menge=4, bestaetigen=False)

        bedarf = {k["product_name"]: k["total_quantity"] for k in _a4_packplan(client, heute)["komponenten"]}
        assert bedarf == {"Erbsen-Schale": 7}

    def test_gelieferte_zaehlt_nicht(self, client):
        """Charakterisierung: GELIEFERT war schon vorher ausgeschlossen und bleibt es."""
        heute, morgen = date.today(), date.today() + timedelta(days=1)
        order = _a4_bestellung(client, morgen)
        _a4_packen(client, order)
        r = _a4_status(client, order, "GELIEFERT")
        assert r.status_code == 200, r.text

        plan = _a4_packplan(client, heute)
        assert plan["komponenten"] == []
        assert plan["items"] == []
```

`test_bestaetigte_und_entwuerfe_zaehlen_weiter` und `test_gelieferte_zaehlt_nicht` sind **Charakterisierungen und von Anfang an grün**.

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k TestSortenbedarfGepackt`
Erwartet: 3 failed, 2 passed.
- `test_gepackte_zaehlt_nicht_im_sortenbedarf`: `assert {'Erbsen-Schale': 8.0} == {'Erbsen-Schale': 3}`
- `test_gepackte_zaehlt_nicht_in_der_packliste`: `assert 8.0 == 3`
- `test_gepackte_werden_benannt`: `assert [{'aus_bundles': [], …, 'total_quantity': 5.0}] == []`

- [ ] **Step 3: Docstring ergänzen**

Im Docstring von `get_packaging_plan` nach der Zeile `nicht bestätigte Bestellungen nicht unsichtbar bleiben.` (`efcea00` Z. 655) einfügen:

```python
    Gepackte Bestellungen (IN_PRODUKTION, Oberfläche "Gepackt") zählen weder
    in `items` noch in `komponenten`; sie stehen nur namentlich unter `gepackt`.
```

- [ ] **Step 4: Filter in Python**

Direkt **nach** der Zeile (`efcea00` Z. 677, nach P1 unverändert)

```python
    orders = [o for o in orders if o.effective_packing_date == target_date]
```

einfügen:

```python
    # Was schon im Karton liegt, braucht keine Sorten mehr (A4, 08.10.2026).
    gepackt = [o for o in orders if o.status in _SCHON_GEPACKT]
    orders = [o for o in orders if o.status in _NOCH_ZU_PACKEN]
```

Die Bundle-Vorladung (`bundle_ids`) und die Schleife `for order in orders:` arbeiten danach automatisch nur auf offenen Bestellungen.

- [ ] **Step 5: Rückgabe ergänzen**

Im Rückgabe-Dict am Ende von `get_packaging_plan` direkt **nach** `"komponenten": sorted(komponenten.values(), key=lambda k: k["product_name"]),` einfügen:

```python
        "gepackt": [{
            "order_id": str(o.id),
            "order_number": o.order_number,
            "customer_name": o.customer.name if o.customer else "—",
            "delivery_date": o.requested_delivery_date.isoformat(),
        } for o in gepackt],
```

`Order.customer` ist über `joinedload(Order.customer)` in der Abfrage bereits geladen.

- [ ] **Step 6: Grün bestätigen, P2 und ganze Datei**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k "TestGepacktBedeutung or TestTagesplanGepackt or TestSortenbedarfGepackt"`
Erwartet: 18 passed.

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -q` (**ohne** `-k`)
Erwartet: 0 failed, 57 passed (39 + 18). Ist irgendein Test rot: **stoppen, nicht committen, melden** (wie Task 11 Step 7).

- [ ] **Step 7: Vollauf**

Prozedur V als Zwischenlauf (`REDIS_URL=memory://` zulässig, siehe Global Constraints). Erwartet: Fehlernamen **identisch** mit der Baseline. **Jeder Name, der nicht in der Baseline steht, egal aus welcher Datei, heißt: stoppen, nicht committen, die Ausgabe melden.** Fremde Tests nicht reparieren; ein neuer roter Test nach diesem Task blockiert den Commit, denn er kann ihn verursacht haben.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/production.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(packplan): Sortenbedarf und Packliste zählen gepackte Bestellungen nicht mehr"
```

---

### Task 13: Tagesplan — Knopf „Gepackt", „Bereits gepackt", Selbstaktualisierung

**Files:**
- Modify: `frontend/src/services/api.ts:137-147` (`DayPlanOrder`), `:228-246` (`productionApi.getPackagingPlan`, `productionApi.getDayPlan`)
- Modify: `frontend/src/pages/Tagesplan.tsx` (Imports, die zwei Plan-Abfragen, Mutation vor `if (isLoading)`, Eintrag `key: 'verpacken'`, Kartenrumpf in `sections.map`, Kopf der Sortenbedarf-Karte)

**Interfaces:**
- Consumes: `packbar`, `verpacken_erledigt` (Task 11), `gepackt` (Task 12). Außerdem bestehend:
  - `salesApi.updateOrderStatus(id, status, reason?)` (`api.ts:384-385`; Task 6 ergänzt einen vierten Parameter `actualDeliveryDate?`)
  - `getErrorMessage(error, fallback)` (`services/errors.ts:10`)
  - `invalidateOrderViews(queryClient): Promise<void>` (`services/orderQueries.ts`, Task 7; in `Tagesplan.tsx` seit Task 7 importiert)
  - `OrderStatusBadge` (`components/ui/Badge.tsx`, exportiert in `components/ui/index.ts:11`)
  - `Button` mit `loading`, `icon`, `variant="success"`, `size="sm"` (`components/ui/Button.tsx`)
  - das Icon `PackageCheck` aus `lucide-react` 0.303
  - TanStack Query 5.90: `onSettled` wird abgewartet, bevor die Mutation `isPending` verlässt (`query-core/build/modern/mutation.js:137`).
- Produces: `gepacktMutation` in `Tagesplan`. Sie lädt über `invalidateOrderViews(queryClient)` neu, also `['orders']`, `['day-plan']`, `['packaging-plan']` und `['packagingPlan']`. (Zusammengeführt: Der Einzelabschnitt rief die vier Invalidierungen selbst auf.)
- Unverändert: Eintrag `key: 'ausliefern'` (P1) samt Badge-Zeile, Packlisten-Knopf und `packlisteMutation`, `ausgeliefertMutation` (Task 7).

- [ ] **Step 1: Typen in `api.ts`**

In `interface DayPlanOrder` direkt **nach** `lines: Array<{ product_name: string; quantity: number; unit: string }>` (Z. 146, P1-Stand Z. 147) einfügen:

```ts
  // Knopf "Gepackt" möglich (BESTAETIGT → IN_PRODUKTION); ein Entwurf muss erst bestätigt werden
  packbar: boolean
```

In `getPackagingPlan` direkt **nach** der Zeile `komponenten: Array<{ product_id: string | null; product_name: string; total_quantity: number; aus_bundles: string[] }>` (Z. 233) einfügen:

```ts
      // Schon gepackt (IN_PRODUKTION): zählt weder in items noch in komponenten
      gepackt: Array<{ order_id: string; order_number: string; customer_name: string; delivery_date: string }>
```

In `getDayPlan` direkt **nach** `verpacken: Array<DayPlanOrder>` (Z. 243) einfügen:

```ts
      // Packtag erledigt: gepackt, geliefert oder fakturiert — fehlt in verpacken
      verpacken_erledigt: Array<DayPlanOrder>
```

- [ ] **Step 2: Imports in `Tagesplan.tsx`**

`PackageCheck` in die lucide-Liste aufnehmen. `salesApi`, `OrderStatusBadge`, `getErrorMessage` und `invalidateOrderViews` sind seit Tasks 6 und 7 importiert — **nicht doppeln**, sonst meldet tsc `Duplicate identifier`. Nur die lucide-Zeile ändert sich. Ergebnis:

```tsx
import { Sprout, Scissors, Package, Truck, Users, Boxes, ListTodo, Plus, FileText, ChevronDown, ChevronRight, CheckCircle, PackageCheck } from 'lucide-react';
```

- [ ] **Step 3: Selbstaktualisierung der beiden Plan-Abfragen**

Task 7 hat beide Abfragen (`day-plan`, `packaging-plan`) schon mit `refetchInterval: 60_000` und `refetchOnWindowFocus: 'always'` versehen. **Nichts ändern.** Optionen nicht doppeln, sonst meldet tsc `An object literal cannot have multiple properties with the same name`.

Run: `cd frontend && grep -c "refetchInterval: 60_000" src/pages/Tagesplan.tsx`
Erwartet: `2`. Sonst stoppen und melden (Task 7 unvollständig).

Zum Verhalten: Global gilt `staleTime` 60 s (`main.tsx:26`). `refetchOnWindowFocus: true` lädt beim Fokus deshalb nur, wenn die Daten älter als 60 s sind. Im Hintergrund pausiert `refetchInterval` (`refetchIntervalInBackground` ist aus). Ein Tablet, das länger als 60 s geschlafen hat, lädt also beim Aufwecken sofort. Eines, das kürzer geschlafen hat, lädt spätestens nach 60 s. Das erfüllt die Abnahme („spätestens 60 s"). Sofortiges Laden bei jedem Fokus bräuchte `'always'`. Das ist Entscheidung E3, nicht Teil dieses Tasks, weil es die Zeilen aus Task 7 ändern würde.

- [ ] **Step 4: Mutation „Gepackt"**

Direkt **vor** der Zeile `if (isLoading) return <PageLoader />;` einfügen, also hinter `ausgeliefertMutation` (Task 7). Dort steht sie vor dem frühen Return (Hook-Regel).

```tsx
  // "Gepackt" = BESTAETIGT → IN_PRODUKTION. Die Bestellung fällt danach aus
  // Verpacken und Sortenbedarf, bleibt aber unter Ausliefern (A4, 08.10.2026).
  const gepacktMutation = useMutation({
    mutationFn: (orderId: string) =>
      salesApi.updateOrderStatus(orderId, 'IN_PRODUKTION', 'Im Tagesplan als gepackt markiert'),
    onSuccess: (order) => toast.success(`${order.order_number ?? 'Bestellung'} als gepackt markiert`),
    onError: (error) => toast.error(getErrorMessage(error, 'Konnte nicht als gepackt markiert werden')),
    // Auch nach einem Fehler neu laden — meist hat ein anderes Gerät schon
    // gepackt. Das Promise zurückgeben: isPending bleibt dann true, bis der
    // Tagesplan neu geladen ist, und ein zweiter Klick trifft keine schon
    // gepackte Bestellung (400 "Statuswechsel nicht möglich: Gepackt → Gepackt").
    onSettled: () => invalidateOrderViews(queryClient),
  });

```

Ohne das zurückgegebene Promise würde `isPending` schon vor dem Neuladen `false`. Der Knopf wäre dann kurz wieder aktiv, und ein zweiter Klick endete mit 400 „Statuswechsel nicht möglich: Gepackt → Gepackt" als Fehler-Toast. `invalidateOrderViews` liefert genau dieses Promise (`Promise<void>`, wartet auf alle vier Invalidierungen); TanStack Query 5.90 wartet auf das Promise aus `onSettled`, bevor die Mutation `isPending` verlässt.

- [ ] **Step 5: Verpacken-Eintrag — Leertext und Status-Badge**

Im Eintrag `key: 'verpacken'` die Zeile `empty: 'Nichts zu verpacken (Bestellungen werden am Tag vor der Lieferung gepackt).',` ersetzen durch:

```tsx
      empty: (plan?.verpacken_erledigt ?? []).length > 0
        ? 'Alles gepackt.'
        : 'Nichts zu verpacken (Bestellungen werden am Tag vor der Lieferung gepackt).',
```

Status-Badge: Dort steht seit Task 6 `<OrderStatusBadge status={o.status} />`. **Nicht ändern.** Unter „Verpacken" kommen ab Task 11 nur noch `ENTWURF` (grau) und `BESTAETIGT` (blau) an (Farben aus Task 6). Den Eintrag `key: 'ausliefern'` nicht anfassen.

- [ ] **Step 6: Verpacken-Eintrag — Knopf „Gepackt"**

Direkt **nach** dem schließenden `</button>` des Packlisten-Knopfs (die Zeilen `<FileText className="w-4 h-4" />`, `Packliste`, `</button>`) einfügen:

```tsx
              {o.packbar ? (
                <Button
                  size="sm"
                  variant="success"
                  icon={<PackageCheck className="w-4 h-4" />}
                  loading={gepacktMutation.isPending && gepacktMutation.variables === o.order_id}
                  disabled={gepacktMutation.isPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    gepacktMutation.mutate(o.order_id);
                  }}
                >
                  Gepackt
                </Button>
              ) : (
                <span className="text-xs text-gray-500 dark:text-gray-400">erst bestätigen</span>
              )}
```

`e.stopPropagation()` ist nötig, weil ein Klick auf die Zeile sie sonst auf- oder zuklappt (`onClick` am Zeilen-`div`). Ein Knopf je Bestellung, ein Übergang je Klick. Bis der Tagesplan neu geladen ist, bleibt der Knopf gesperrt (Step 4). Die Kette BESTAETIGT → IN_PRODUKTION → GELIEFERT durch Doppelklick (A1.md, Punkt 5) ist hier nicht möglich, „Ausgeliefert" sitzt in einer anderen Karte.

- [ ] **Step 7: Verpacken-Eintrag — Liste „Bereits gepackt"**

Im Eintrag `key: 'verpacken'` den Schlüssel `footer` **innerhalb des Objekts** einfügen: zwischen der Zeile `      )),`, die `rows: (plan?.verpacken ?? []).map(…)` abschließt, und der Zeile `    },`, die den Eintrag `verpacken` schließt (nach Task 7 etwa zwischen Z. 197 und Z. 198). Nicht hinter `},`, dort beginnt schon das Objekt `{ key: 'ausliefern', …`.

```tsx
      // Erledigt am Packtag: sichtbar, damit niemand eine gepackte Bestellung sucht
      footer: (plan?.verpacken_erledigt ?? []).length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 space-y-1">
          <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Bereits gepackt</p>
          {(plan?.verpacken_erledigt ?? []).map((o) => (
            <div key={o.order_id} className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <PackageCheck className="w-4 h-4 text-green-600 dark:text-green-400 shrink-0" />
              <span>{o.customer_name}</span>
              <span className="text-gray-400">
                · {o.order_number} · Lieferung {new Date(o.delivery_date).toLocaleDateString('de-DE')}
              </span>
              {/* Gepackt, Geliefert oder Fakturiert — alles erledigt am Packtag */}
              <OrderStatusBadge status={o.status} />
            </div>
          ))}
        </div>
      ),
```

Im Kartenrumpf der `sections.map` direkt **nach** dem Ausdruck `{s.count === 0 ? (…) : (<div className="space-y-2">{s.rows}</div>)}` einfügen, also nach der Zeile `)}` hinter `<div className="space-y-2">{s.rows}</div>`:

```tsx
              {s.footer}
```

Die anderen Einträge brauchen kein `footer`. TypeScript normalisiert das Array-Literal, `s.footer` ist dort `undefined` (gemessen: tsc sauber).

- [ ] **Step 8: Sortenbedarf-Kopf**

In der Karte „Sortenbedarf zum Packen" die Zeile `<Badge variant="info">{packaging?.komponenten.length}</Badge>` ersetzen durch:

```tsx
            <div className="flex items-center gap-2">
              {/* Gleiche Quelle wie die Liste "Bereits gepackt" in der Verpacken-Karte */}
              {(plan?.verpacken_erledigt ?? []).length > 0 && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ohne {plan?.verpacken_erledigt.length} bereits gepackte
                </span>
              )}
              <Badge variant="info">{packaging?.komponenten.length}</Badge>
            </div>
```

Die Zahl stammt bewusst aus `plan.verpacken_erledigt`, nicht aus `packaging.gepackt`. Nach P1 enthält die day-plan-Liste auch gelieferte und fakturierte Bestellungen des Packtags. packaging-plan lädt die nicht (`production.py:673`), dort steht nur `IN_PRODUKTION`. Mit `packaging.gepackt` zeigte der Hinweis eine andere Zahl als die Liste „Bereits gepackt" darunter. Auch Gelieferte fehlen im Sortenbedarf, der Satz „ohne N bereits gepackte" stimmt also.

Die Bedingung, unter der die Karte überhaupt erscheint (`(packaging?.komponenten ?? []).length > 0`), bleibt. Ist alles gepackt, verschwindet die Karte, und die Verpacken-Karte zeigt „Alles gepackt." samt Liste.

- [ ] **Step 9: Typprüfung und Platzprüfung**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe, Exit-Code 0.

Run: `cd frontend && sed -n "/key: 'ausliefern'/,/^  \];/p" src/pages/Tagesplan.tsx | grep -c packbar`
Erwartet: `0`. Der Ausliefern-Eintrag ist unberührt. Ein Wert > 0 heißt: Step 5 hat die falsche Zeile ersetzt, also zurücknehmen.

Run: `cd frontend && grep -c "{s.footer}" src/pages/Tagesplan.tsx`
Erwartet: `1`.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/pages/Tagesplan.tsx
git commit -m "feat(tagesplan): Knopf 'Gepackt' in der Verpacken-Karte, Sortenbedarf ohne Gepackte"
```

---

### Task 14: Produktionsseite, Tab Verpackungsplan — Gepackte benennen

**Files:**
- Modify: `frontend/src/pages/Production.tsx:428-441` (Kopf und Leerzustand des Tabs `PACKAGING`)

**Interfaces:**
- Consumes: `packagingPlan.gepackt` (Task 12, Typ aus Task 13). Enthält nur `IN_PRODUKTION`. Gelieferte zeigt dieser Tab ohnehin nicht.
- Unverändert: Tabelle und Zeile 465 (seit Task 6 `({orderStatusLabel(o.status)}…`), Abfrage `['packagingPlan', packagingDate]` (Z. 96–100). Die Invalidierung dieser Abfrage kommt aus der Tagesplan-Mutation (Task 13) und von den Bestellseiten (P1).

- [ ] **Step 1: Kopf und Leerzustand**

Stand `efcea00` und P1-Stand (Task 6 ändert diese Zeilen nicht), Z. 431–440:

```tsx
              <span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">
                (Lieferungen von morgen + Same-Day-Bestellungen)
              </span>
            </h3>
          </div>
          {!packagingPlan?.items || packagingPlan.items.length === 0 ? (
            <EmptyState
              title="Keine Lieferungen geplant"
              description="Für dieses Datum gibt es keine offenen Bestellungen."
            />
```

ersetzen durch:

```tsx
              <span className="ml-2 text-xs font-normal text-gray-500 dark:text-gray-400">
                (Lieferungen von morgen + Same-Day-Bestellungen)
              </span>
            </h3>
            {/* Gepackte zählen nicht mehr mit — hier benannt, damit niemand sie sucht */}
            {(packagingPlan?.gepackt ?? []).length > 0 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Bereits gepackt: {(packagingPlan?.gepackt ?? []).map((g) => `${g.customer_name} (${g.order_number})`).join(', ')}
              </span>
            )}
          </div>
          {!packagingPlan?.items || packagingPlan.items.length === 0 ? (
            <EmptyState
              title={(packagingPlan?.gepackt ?? []).length > 0 ? 'Alles gepackt' : 'Keine Lieferungen geplant'}
              description={(packagingPlan?.gepackt ?? []).length > 0
                ? 'Alle Bestellungen dieses Packtags sind als gepackt markiert.'
                : 'Für dieses Datum gibt es keine offenen Bestellungen.'}
            />
```

Der Kopf-Container (`<div className="p-4 border-b … flex justify-between items-center">`, Z. 428) setzt den neuen Text rechts neben die Überschrift.

- [ ] **Step 2: Typprüfung**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe, Exit-Code 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Production.tsx
git commit -m "feat(produktion): Verpackungsplan nennt bereits gepackte Bestellungen"
```

---

### Task 15: Dashboard — gepackte Bestellungen bleiben „offen"

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx:60-64` (Abfrage `['orders', 'open']`)

**Interfaces:**
- Consumes: `salesApi.listOrders(params?: { status?: string; kunde_id?: string }) => Promise<ListResponse<Order>>` (`api.ts:349-350`; `ListResponse.total: number`, `types/index.ts:326-329`). Der Endpunkt nimmt genau einen Status oder den Sammelfilter `OFFEN` (`sales.py:688-700`). Deshalb zwei Abfragen.
- Produces: `ordersData.total` = Anzahl `BESTAETIGT` + `IN_PRODUKTION`. Verwendet wird nur `.total` (`:166`, `:345`).
- Unverändert: Schlüssel `['orders', 'open']`. Er wird über das Präfix `['orders']` von `invalidateOrderViews` (Task 7; auch aus `gepacktMutation`, Task 13) mit invalidiert. Unverändert bleibt auch die Rechnungsabfrage Z. 82/336 (Paket-1-Task 28).

Warum: Bisher war `IN_PRODUKTION` ein Durchgang von unter einer Sekunde (A4.md). Mit dem Knopf fällt jede gepackte Bestellung über Nacht aus der Kennzahl „Offene Bestellungen", obwohl sie weder geliefert noch berechnet ist. Das widerspricht der Begründung zu `sales.py:691`/`:840` („gepackt ist nicht geliefert"). Entwürfe zählen wie bisher nicht mit. Ob sie mitzählen sollen (Filter `OFFEN`), ist Entscheidung E1.

- [ ] **Step 1: Abfrage ersetzen**

In `frontend/src/pages/Dashboard.tsx` den Block (Z. 60–64)

```tsx
  const { data: ordersData } = useQuery({
    queryKey: ['orders', 'open'],
    queryFn: () => salesApi.listOrders({ status: 'BESTAETIGT' }),
    retry: 0,
  });
```

ersetzen durch:

```tsx
  // Offen = bestätigt oder gepackt. Seit dem Knopf "Gepackt" im Tagesplan
  // stehen Bestellungen über Nacht auf IN_PRODUKTION ("Gepackt") — sie sind
  // weder geliefert noch berechnet und zählen weiter (A4, 08.10.2026).
  // Entwürfe zählen wie bisher nicht mit (dafür gäbe es den Filter OFFEN).
  const { data: ordersData } = useQuery({
    queryKey: ['orders', 'open'],
    queryFn: async () => {
      const [bestaetigt, gepackt] = await Promise.all([
        salesApi.listOrders({ status: 'BESTAETIGT' }),
        salesApi.listOrders({ status: 'IN_PRODUKTION' }),
      ]);
      return { total: bestaetigt.total + gepackt.total };
    },
    retry: 0,
  });
```

Die Anzeigen `{ordersData?.total || 0}` (Z. 166 und Z. 345) bleiben unverändert.

- [ ] **Step 2: Typprüfung**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe, Exit-Code 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "fix(dashboard): gepackte Bestellungen zählen weiter als offen"
```

---


## Abschnitt P3: A2 — Kunde in Rechnungsliste, Detail und „Überfällig" — Tasks 16–18

**Ziel:** Die Spalte „Kunde" der Rechnungsliste, das Detail-Modal und der Reiter „Überfällig" zeigen Kundenname und Kundennummer; die Kundensuche greift wieder. Keine Schemaänderung, kein `_auto_migrate`.

**Befund (aus A2.md, am Code bestätigt):** `InvoiceResponse` (`backend/app/schemas/invoice.py:213-214`) hat `customer_name` und `customer_number` mit Default `None` und `from_attributes=True`. Das Modell `Invoice` (`backend/app/models/invoice.py:21-226`) hat keins von beiden. Deshalb ist der Wert bei jedem Endpunkt, der ein `Invoice` serialisiert, `null`: Liste, Detail, Überfällig, Anlegen, from-order, PATCH, Finalisieren, Storno und Sammellauf-Festschreiben. Der Fix gehört deshalb ins Modell und nicht in einzelne Endpunkte. Als Quelle dient derselbe Stammdatenstand, den auch das PDF druckt (`pdf_service.py:239`: `invoice.customer.name`). Kein Regressionsfehler: Das Schemafeld steht seit dem Initial Commit `5737cbe` und wurde nie befüllt.

**Bewusst nicht angefasst:** `backend/app/services/invoice_service.py` (Paket 1 ändert dort `check_overdue_invoices`; ein `joinedload` dort hätte nichts gebracht, Messung in Task 17 Step 4), die Sammellauf-Vorschau (`invoices.py:559`, `:582`, befüllt `customer_name` schon selbst), die Kürzung der Rechnungsliste auf 20 (Paket-1-Task 28).

**Review Focus (P3, getestet):**
1. Alle schreibenden Endpunkte liefern den Kunden mit, PATCH mit neuem `customer_id` den neuen Namen (Task 16, `test_schreibende_endpunkte`).
2. Liste und „Überfällig" brauchen gleich viele SELECTs bei 1 und bei 4 Rechnungen (Task 17).
3. „Überfällig" liefert dieselbe JSON-Form wie heute (kein zeitzonenbehaftetes `updated_at`, Task 17 Step 4).

---

### Task 16: Die Rechnung kennt ihren Kunden

**Files:**
- Modify: `backend/app/models/invoice.py:186-191` (Klasse `Invoice`, direkt nach der Property `is_overdue`)
- Modify: `backend/tests/test_gernot_261008_paket2.py` (Block ans Dateiende)

**Interfaces:**
- Produces:
  - `Invoice.customer_name -> Optional[str]` und `Invoice.customer_number -> Optional[str]`: reine `@property`, kein Setter, keine Spalte.
  - Test-Helfer `_a2_kunde`, `_a2_entwurf`, `_a2_rechnung`, `_a2_liste`, `_a2_zeile`. Task 17 nutzt sie weiter.
- Unverändert: `InvoiceResponse` und `InvoiceDetailResponse`. Beide kennen die Felder schon.

- [ ] **Step 1: Failing Tests schreiben**

Den folgenden Block **ans Dateiende** von `backend/tests/test_gernot_261008_paket2.py` anhängen (Task 1 hat die Datei angelegt). Steht `from datetime import date, timedelta` schon im Dateikopf, darf die Zeile aus dem Block dorthin wandern. Ein doppelter Import schadet nicht.

```python
# ===========================================================================
# P3 / A2 — Kunde in Rechnungsliste, Detail und "Überfällig"
#
# InvoiceResponse kannte customer_name/customer_number seit dem Initial
# Commit, das Invoice-Modell nicht — die Felder kamen immer als null.
# ===========================================================================
from datetime import date, timedelta


def _a2_kunde(client, name="Gasthof Zur Post", nummer="K-A2-001"):
    r = client.post("/api/v1/sales/customers", json={
        "name": name, "typ": "GASTRO", "customer_number": nummer,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _a2_entwurf(client, kunde, *, rechnungsdatum=None, faellig=None):
    """Rechnungsentwurf mit einer Position, Satz ausdrücklich gesetzt."""
    body = {
        "customer_id": kunde["id"],
        "invoice_date": (rechnungsdatum or date.today()).isoformat(),
        "lines": [{
            "description": "Erbse 100 g", "quantity": "2", "unit": "STUECK",
            "unit_price": "3.50", "tax_rate": "REDUZIERT",
        }],
    }
    if faellig is not None:
        body["due_date"] = faellig.isoformat()
    r = client.post("/api/v1/invoices", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _a2_rechnung(client, kunde, *, ueberfaellig=False):
    """Finalisierte (OFFEN) Rechnung; ueberfaellig=True → Zahlungsziel gestern."""
    heute = date.today()
    if ueberfaellig:
        entwurf = _a2_entwurf(client, kunde, rechnungsdatum=heute - timedelta(days=30),
                              faellig=heute - timedelta(days=1))
    else:
        entwurf = _a2_entwurf(client, kunde, faellig=heute + timedelta(days=14))
    r = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


def _a2_liste(r):
    """Zeilen aus GET /invoices bzw. /invoices/overdue.

    Heute eine nackte Liste (api.ts: api.get<Invoice[]>). Stellt Paket 1 die
    Rechnungsliste auf {"items": [...], ...} um, greift der zweite Zweig.
    """
    assert r.status_code == 200, r.text
    daten = r.json()
    return daten["items"] if isinstance(daten, dict) else daten


def _a2_zeile(rows, invoice_id):
    treffer = [r for r in rows if r["id"] == invoice_id]
    assert len(treffer) == 1, f"Rechnung {invoice_id} nicht in der Antwort"
    return treffer[0]


class TestRechnungZeigtKunde:
    """A2: Spalte "Kunde" war in Liste, Detail und "Überfällig" leer."""

    def test_liste(self, client):
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde)

        zeile = _a2_zeile(_a2_liste(client.get("/api/v1/invoices")), rechnung["id"])
        assert zeile["customer_name"] == "Gasthof Zur Post"
        assert zeile["customer_number"] == "K-A2-001"

    def test_liste_mit_statusfilter_wie_dashboard(self, client):
        """Dashboard.tsx fragt GET /invoices?status=OFFEN ab."""
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde)

        rows = _a2_liste(client.get("/api/v1/invoices", params={"status": "OFFEN"}))
        assert _a2_zeile(rows, rechnung["id"])["customer_name"] == "Gasthof Zur Post"

    def test_detail(self, client):
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde)

        r = client.get(f"/api/v1/invoices/{rechnung['id']}")
        assert r.status_code == 200, r.text
        assert r.json()["customer_name"] == "Gasthof Zur Post"
        assert r.json()["customer_number"] == "K-A2-001"

    def test_ueberfaellig(self, client):
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde, ueberfaellig=True)

        zeile = _a2_zeile(_a2_liste(client.get("/api/v1/invoices/overdue")), rechnung["id"])
        assert zeile["status"] == "UEBERFAELLIG"
        assert zeile["customer_name"] == "Gasthof Zur Post"
        assert zeile["customer_number"] == "K-A2-001"

    def test_ueberfaellig_zweiter_aufruf(self, client):
        """Beim zweiten Aufruf steht die Rechnung schon auf UEBERFAELLIG — Kunde bleibt."""
        kunde = _a2_kunde(client)
        rechnung = _a2_rechnung(client, kunde, ueberfaellig=True)
        client.get("/api/v1/invoices/overdue")

        rows = _a2_liste(client.get("/api/v1/invoices/overdue"))
        assert _a2_zeile(rows, rechnung["id"])["customer_name"] == "Gasthof Zur Post"

    def test_schreibende_endpunkte(self, client):
        """Anlegen, Kopfdaten ändern, Finalisieren und Storno liefern den Kunden mit."""
        alt = _a2_kunde(client)
        neu = _a2_kunde(client, name="Fruchthof Nagel", nummer="K-A2-002")

        entwurf = _a2_entwurf(client, alt, faellig=date.today() + timedelta(days=14))
        assert entwurf["customer_name"] == "Gasthof Zur Post"

        r = client.patch(f"/api/v1/invoices/{entwurf['id']}", json={"customer_id": neu["id"]})
        assert r.status_code == 200, r.text
        assert r.json()["customer_name"] == "Fruchthof Nagel"
        assert r.json()["customer_number"] == "K-A2-002"

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")
        assert r.status_code == 200, r.text
        assert r.json()["customer_name"] == "Fruchthof Nagel"

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/cancel", json={
            "reason": "Test", "reason_code": "SONSTIGES", "create_credit_note": True,
        })
        assert r.status_code == 200, r.text
        assert r.json()["invoice"]["customer_name"] == "Fruchthof Nagel"
        assert r.json()["credit_note"]["customer_name"] == "Fruchthof Nagel"
```

Hinweise zu den Tests:
- Der Steuersatz der Position ist ausdrücklich gesetzt (`REDUZIERT`). Nach dem A3-Fix aus Paket 1 gilt bei manuellen Zeilen ohne `product_id` weiterhin der Satz des Clients (LUECKEN.md Punkt 6). Deshalb hängen die Tests nicht an Paket 1.
- Die Prüfung `zeile["status"] == "UEBERFAELLIG"` in `test_ueberfaellig` beschreibt bestehendes Verhalten und war schon vorher erfüllt (Charakterisierung). Rot wird der Test nur wegen `customer_name`.

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k "TestRechnungZeigtKunde"`
Erwartet: **6 failed**, jeder mit `AssertionError: assert None == 'Gasthof Zur Post'`. Bei `test_schreibende_endpunkte` kommt der Fehler schon an der ersten Prüfung nach dem Anlegen. Scheitert ein Test vorher an einem Statuscode (Helfer-Assert), dann stoppen und die Ausgabe melden.

- [ ] **Step 3: Properties am Modell**

In `backend/app/models/invoice.py`, Klasse `Invoice`, direkt **nach** der Property `is_overdue` (endet Z. 191) und **vor** `def get_tax_summary` einfügen:

```python
    # Kunde für Listen und Detail. InvoiceResponse kennt beide Felder seit
    # jeher (from_attributes), das Modell hatte sie nicht — die Spalte "Kunde"
    # blieb deshalb überall leer. Stammdaten-Stand wie im PDF
    # (pdf_service: invoice.customer.name). Listen laden den Kunden per
    # joinedload, sonst kostet jede Zeile eine eigene Abfrage.
    @property
    def customer_name(self) -> Optional[str]:
        """Name des Kunden (aktueller Stammdatenstand)."""
        return self.customer.name if self.customer else None

    @property
    def customer_number(self) -> Optional[str]:
        """Kundennummer (aktueller Stammdatenstand)."""
        return self.customer.customer_number if self.customer else None
```

`Optional` ist in der Datei schon importiert (Z. 9). Ein Setter ist unnötig. `InvoiceUpdate` (`schemas/invoice.py:147-158`) kennt `customer_name` nicht, also schreibt die `setattr`-Schleife in `update_invoice` (`invoices.py:157-159`) das Feld nie. Weder `app/` noch `tests/` enthält `Invoice(customer_name=…)`.

**Nicht anfassen:** `schemas/invoice.py` (Felder vorhanden) und die Sammellauf-Vorschau `invoices.py:559` und `:582`. Die Vorschau befüllt `customer_name` korrekt über ein eigenes Dict.

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k "TestRechnungZeigtKunde"`
Erwartet: 6 passed.

- [ ] **Step 5: Vollauf**

Prozedur V als Zwischenlauf (`REDIS_URL=memory://` zulässig, siehe Global Constraints). Erwartet: dieselben Fehlernamen wie die Baseline. Nur Namen vergleichen. Ein neuer Name aus Tests früherer Tasks: gesondert ausweisen und stoppen.

- [ ] **Step 6: Commit**

Vorher `git diff backend/tests/test_gernot_261008_paket2.py` ansehen: Der Diff darf nur den P3-Block aus Step 1 enthalten. Steht dort etwas anderes, stoppen und melden.

```bash
git add backend/app/models/invoice.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(rechnungen): Spalte 'Kunde' war in Liste, Detail und Überfällig leer"
```

---

### Task 17: Rechnungslisten laden den Kunden mit (kein N+1)

**Files:**
- Modify: `backend/app/api/v1/invoices.py:47` (`list_invoices`, **nur** die Ladeoptionen)
- Modify: `backend/app/api/v1/invoices.py:71-77` (`list_overdue_invoices`)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: Helfer aus Task 16. Dazu `InvoiceService.check_overdue_invoices() -> list[Invoice]` (`invoice_service.py:362`), unverändert.
- Produces: `_a2_selects()`, ein Kontextmanager, der die SELECTs auf `tests.conftest.engine` zählt. `GET /invoices` und `GET /invoices/overdue` brauchen danach eine feste Zahl an Abfragen, egal wie viele Zeilen sie liefern.

- [ ] **Step 1: Failing Tests anhängen**

Ans Dateiende von `backend/tests/test_gernot_261008_paket2.py`:

```python
# --- P3 / A2: keine Kundenabfrage je Zeile (N+1) ---
from contextlib import contextmanager

from sqlalchemy import event

from tests.conftest import engine as _a2_engine


@contextmanager
def _a2_selects():
    """Zählt SELECT-Anweisungen auf der Test-Engine während des Blocks."""
    zaehler = {"n": 0}

    def _mitzaehlen(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            zaehler["n"] += 1

    event.listen(_a2_engine, "before_cursor_execute", _mitzaehlen)
    try:
        yield zaehler
    finally:
        event.remove(_a2_engine, "before_cursor_execute", _mitzaehlen)


class TestRechnungslistenOhneNPlusEins:
    """Der Kundenname darf nicht pro Zeile eine eigene Abfrage kosten."""

    def _selects(self, client, url):
        with _a2_selects() as z:
            r = client.get(url)
        return z["n"], _a2_liste(r)

    def test_liste(self, client):
        _a2_rechnung(client, _a2_kunde(client, "Kunde 0", "K-A2-100"))
        einer, rows = self._selects(client, "/api/v1/invoices")
        assert len(rows) == 1

        for i in range(1, 4):
            _a2_rechnung(client, _a2_kunde(client, f"Kunde {i}", f"K-A2-10{i}"))
        vier, rows = self._selects(client, "/api/v1/invoices")
        assert len(rows) == 4
        assert {r["customer_name"] for r in rows} == {f"Kunde {i}" for i in range(4)}

        assert vier == einer, f"{einer} SELECTs bei 1 Rechnung, {vier} bei 4 — N+1"

    def test_ueberfaellig(self, client):
        _a2_rechnung(client, _a2_kunde(client, "Kunde 0", "K-A2-100"), ueberfaellig=True)
        einer, rows = self._selects(client, "/api/v1/invoices/overdue")
        assert len(rows) == 1

        for i in range(1, 4):
            _a2_rechnung(client, _a2_kunde(client, f"Kunde {i}", f"K-A2-10{i}"), ueberfaellig=True)
        vier, rows = self._selects(client, "/api/v1/invoices/overdue")
        assert len(rows) == 4
        assert {r["customer_name"] for r in rows} == {f"Kunde {i}" for i in range(4)}

        assert vier == einer, f"{einer} SELECTs bei 1 Rechnung, {vier} bei 4 — N+1"
```

`tests.conftest.engine` ist die `StaticPool`-Engine, an die `TestingSessionLocal` und die `client`-Fixture gebunden sind (`tests/conftest.py:18-23`).

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k "TestRechnungslistenOhneNPlusEins"`
Erwartet: **2 failed**, gemessen auf HEAD + Task 16:
- `test_liste`: `AssertionError: 2 SELECTs bei 1 Rechnung, 5 bei 4 — N+1`
- `test_ueberfaellig`: `AssertionError: 3 SELECTs bei 1 Rechnung, 9 bei 4 — N+1`

Ist Paket 1 schon gemergt, können die absoluten Zahlen abweichen, etwa durch eine zusätzliche Zählabfrage. Maßgeblich ist, dass `vier > einer` gilt.

- [ ] **Step 3: `list_invoices` lädt den Kunden mit**

In `backend/app/api/v1/invoices.py`, Funktion `list_invoices`, Z. 47:

```python
    query = select(Invoice).options(joinedload(Invoice.lines))
```

ersetzen durch:

```python
    # Kunde mitladen: customer_name/customer_number lesen invoice.customer —
    # ohne joinedload eine Kundenabfrage je Zeile.
    query = select(Invoice).options(joinedload(Invoice.lines), joinedload(Invoice.customer))
```

`joinedload` und `select` sind schon importiert (Z. 9 und Z. 10). Den Rest von `list_invoices` (Filter, `order_by`, `offset`/`limit`, `.unique()`) **nicht anfassen**, das ist Paket-1-Gebiet.

- [ ] **Step 4: `list_overdue_invoices` lädt nach dem Commit einmal gesammelt nach**

In `backend/app/api/v1/invoices.py` den Rumpf von `list_overdue_invoices` (Z. 71–77):

```python
@router.get("/overdue", response_model=list[InvoiceResponse])
def list_overdue_invoices(db: DBSession):
    """Listet alle überfälligen Rechnungen."""
    service = InvoiceService(db)
    overdue = service.check_overdue_invoices()
    db.commit()
    return overdue
```

ersetzen durch:

```python
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
```

Warum der Fix im Endpunkt sitzt und nicht in `InvoiceService.check_overdue_invoices`:
- **Gemessen:** `joinedload(Invoice.customer)` nur in `check_overdue_invoices` ergibt 2 statt 5 SELECTs, der Test bleibt rot. `db.commit()` verfällt alle Objekte (`expire_on_commit` ist Standard, `tenancy.py:83`), und die Serialisierung lädt danach jede Rechnung einzeln nach. Deshalb wird `invoice_service.py` **nicht** geändert, das ist Paket-1-Gebiet (Überschneidung 10).
- **Verworfen:** `db.flush()` und dann vor dem Commit serialisieren. Gemessen ergibt das für eben auf UEBERFAELLIG gesetzte Rechnungen ein zeitzonenbehaftetes `updated_at` (`…713382Z`), für alle anderen das naive aus SQLite (`…713382`). Das JSON wäre uneinheitlich. Das Nachladen per `IN` liefert dieselbe Form wie heute.
- Bei einem many-to-one-`joinedload` ist kein `.unique()` nötig. Die Reihenfolge bleibt wie heute ungeordnet, beide Abfragen haben kein `ORDER BY`.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -v -k "TestRechnungZeigtKunde or TestRechnungslistenOhneNPlusEins"`
Erwartet: 8 passed.

- [ ] **Step 6: Vollauf**

Prozedur V als Zwischenlauf (`REDIS_URL=memory://` zulässig, siehe Global Constraints). Erwartet: Baseline-Fehlernamen, keine neuen. Vorab gemessen: Die 18 rechnungsnahen Testdateien laufen mit P3 bei 222 passed und 11 failed, alle 11 aus der Baseline. Bestehende Erwartungen ändert P3 nicht. `test_gernot_bugfixes.py:140` und `test_gernot_260817.py:187-206` (LUECKEN.md Punkt 6) betreffen P3 nicht.

- [ ] **Step 7: Commit**

Vorher `git diff backend/tests/test_gernot_261008_paket2.py` ansehen: Der Diff darf nur den Block aus Step 1 dieses Tasks enthalten. Steht dort etwas anderes, stoppen und melden.

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_gernot_261008_paket2.py
git commit -m "perf(rechnungen): Liste und Überfällig laden den Kunden gesammelt statt je Zeile"
```

---

### Task 18: Frontend — Typ passt zum Backend, Detail mit Fallback

**Files:**
- Modify: `frontend/src/types/index.ts:621-622` (`interface Invoice`, `reminder_level` nur als Anker)
- Modify: `frontend/src/pages/Invoices.tsx:1156` (`InvoiceDetail`, Feld „Kunde")

**Interfaces:**
- Produces: `Invoice.customer_name?: string | null`, `Invoice.customer_number?: string | null`.
- Unverändert: Die Listenspalte (`Invoices.tsx:344`, hat schon `|| '-'`) und die Suche (`Invoices.tsx:166-170`, `customer_name?.toLowerCase()`) funktionieren, sobald das Backend liefert. `OrderDocumentsModal.tsx` und `Dashboard.tsx` zeigen den Kunden nicht an.

Für diesen Task gibt es keinen Frontend-Test im Repo, der das Feld prüft. Die Wirkung belegen Tasks 16 und 17 im Backend, hier geht es um Typtreue.

- [ ] **Step 1: Typ an die Antwort angleichen**

In `frontend/src/types/index.ts`, `interface Invoice` (beginnt Z. 594), Z. 621–622. **Achtung:** `  customer_name?: string` allein ist nicht eindeutig. Es ist auch Präfix von Z. 182 im `interface Order` (`  customer_name?: string | null`). Ein Edit nur mit dieser Zeile schlägt fehl, ein ungeankertes `sed` veränderte zusätzlich das Order-Interface (`customer_number?: string | null | null`), und `tsc` meldete das **nicht**. Deshalb die Folgezeile als Anker mitnehmen. Der folgende Zwei-Zeilen-Block kommt in der Datei genau einmal vor:

```ts
  customer_name?: string
  reminder_level?: number
```

ersetzen durch:

```ts
  // Aus den Kundenstammdaten; null, falls der Kunde fehlt
  customer_name?: string | null
  customer_number?: string | null
  reminder_level?: number
```

Danach prüfen: `grep -n "customer_name?: string" frontend/src/types/index.ts` zeigt Z. 182 unverändert (`customer_name?: string | null` im `interface Order`) und die neue Zeile im `interface Invoice`. `grep -c "| null | null" frontend/src/types/index.ts` ergibt 0.

- [ ] **Step 2: Fallback im Detail**

In `frontend/src/pages/Invoices.tsx`, Z. 1156:

```tsx
            <p className="font-medium">{invoice.customer_name}</p>
```

ersetzen durch:

```tsx
            <p className="font-medium">{invoice.customer_name || '–'}</p>
```

Zeichen festgelegt: Halbgeviertstrich `–` (U+2013). Das Detail-Modal nutzt ihn schon als Fallback beim Fälligkeitsdatum (`Invoices.tsx:1168`, `… : '–'`), das Feld „Kunde" passt sich daran an. Die Listenspalte (`Invoices.tsx:344`) behält ihren Bindestrich `'-'`. Liste und Detail weichen also weiter voneinander ab, wie heute schon zwischen Liste und Fälligkeitsfeld. Z. 344 wird bewusst nicht angeglichen, weil `Invoices.tsx` Paket-1-Gebiet ist (Entscheidung E4).

Sonst nichts in `Invoices.tsx` ändern, die Datei ist Paket-1-Gebiet.

- [ ] **Step 3: Typprüfung**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe, Exit 0. Auf `HEAD efcea00` und mit genau dieser Änderung (Zwei-Zeilen-Anker aus Step 1) in einer Kopie gemessen.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/pages/Invoices.tsx
git commit -m "fix(rechnungen): Kundenfelder im Typ nullable, Detail zeigt '–' statt leer"
```

---


## Abschnitt P4: A5 — Abo-Bestellungen mit Produkt, Preis und Steuersatz; mehrere Liefertage; Knopf im richtigen Mandanten — Tasks 19–22 (und 24)

**Ziel:** Der Abo-Lauf legt je fälligem Abo und Liefertag genau eine Entwurfs-Bestellung an, mit dem Abo-Produkt (bzw. der Variante), dem Kundenpreis zum Liefertag und dem Satz des Produktstamms; ein Abo ohne eindeutiges, lieferbares Produkt wird übersprungen und gemeldet, statt „irgendein Produkt" zu nehmen. Mehrere Liefertage wirken, auch bei Start an einem Nicht-Liefertag. „Heute verarbeiten" läuft im Mandanten der Anfrage. Der nie eingeplante Abo-Rechnungstask verschwindet. Keine Frontend- und keine Schemaänderung. Die Korrektur der vier LfA-Entwürfe ist Runbook B (Manager).

**Verifizierter Ausgangsbefund (Code-Stand `c4a1832`; `efcea00` ändert keine P4-Datei):**

- **Produktsuche nur über die Sorte.** `subscription_tasks.py:129`: `select(Product).where(Product.seed_id == sub.seed_id)`. Das Abo-Formular setzt `product_id` und leert `seed_id` (`Abonnements.tsx:437-438`), `create_subscription` übernimmt beides (`sales.py:518-538`). Mit `seed_id = None` wird daraus `WHERE products.seed_id IS NULL`; `.first()` ohne `ORDER BY` liefert das erste Produkt ohne Sorte. Dessen `base_price` wird der Preis (Z. 145-146), dessen `tax_rate` der Satz (Z. 156). Die Position bekommt kein `product_id` (Z. 149-158 setzt nur `seed_id`), der Text wird `Abo-Lieferung: Unknown` (Z. 152, weil `sub.seed` leer ist). Der Preislisten-Zweig (Z. 133-142) greift nur mit `customer.price_list_id`; für Preislisten gibt es keinen API-Endpunkt, und `create_order` nutzt sie nicht.
- **Sonderpreise kennt der Lauf nicht.** `create_order` (`sales.py:947-988`) rechnet so: `pricing_service.resolve_unit_price(db, customer_id, product_id, default=product.base_price, on_date=heute)` liefert `(preis, ist_sonderpreis)`. Bei einer Variante gilt `variant.price_override` (sonst der Basispreis), aber nur ohne Sonderpreis. Der Name lautet `"{Produkt} — {name_suffix}"`, die Einheit ist `UnitOfMeasure.code` der `packaging_unit_id`.
- **Fälligkeit** `_is_subscription_due_today` (Z. 12-44): Die Liefertage filtern (Z. 22-24), **und zusätzlich** zählt der Abstand zu `gueltig_von` (Z. 29-42: `delta % 7 == 0`, `delta % 14 == 0`, `today.day == gueltig_von.day`). Folgen:
  - (a) wöchentlich Mo + Do, Start an einem Montag: nur montags;
  - (b) Start an einem Nicht-Liefertag: nie. Das Formular setzt `gueltig_von` auf heute (`Abonnements.tsx:48`, `:138`), ein mittwochs angelegtes Montags-Abo liefert also nie;
  - (c) zweiwöchentlich wie (a)/(b);
  - (d) monatlich mit Liefertagen: nur wenn der Monatstag zufällig auf einen Liefertag fällt;
  - (e) monatlich ab dem 29.–31.: fällt in kürzeren Monaten aus.

  Die vier LfA-Entwürfe (14.09., 21.09., 28.09., 05.10.2026) fallen alle auf einen Montag: Das LfA-Abo startet an einem Montag. Ob es weitere Liefertage hat, die (a) unterdrückt, zeigt R1 in Runbook B. Abos, die nie eine Bestellung erzeugt haben, sind wahrscheinlich Fall (b). Sie **starten nach dem Fix** (Runbook B, R6).
- **Der Knopf „Heute verarbeiten“ läuft im falschen Mandanten.** `POST /sales/subscriptions/process-today` (`Abonnements.tsx:119-127` → `sales.py:582-588`) ruft `process_daily_subscriptions()`, und das öffnet `SessionLocal()` (`subscription_tasks.py:49`). `SessionLocal` ist der Legacy-Proxy aus `database.py:93-96`; er löst über `_active_slug()` (`database.py:74-76`) nach `get_current_tenant()` oder `DEFAULT_TENANT_SLUG` auf (`tenancy.py:53`, Standard `dev`). Die ContextVar setzt nur der Scheduler (`scheduler_service.py:46`). `tenant_middleware` (`main.py:316-354`) schreibt den Mandanten nur in `request.state` (`set_request_tenant`, `tenancy.py:399-400`), und das liest nur `get_db(request)` bzw. `DBSession`. Folgen in Produktion:
  - Der Knopf auf `minga.novaerp.de` verarbeitet die Abos der Default-DB, nicht die von Minga.
  - Ist `DEFAULT_TENANT_SLUG=minga` gesetzt, löst jeder Nutzer eines anderen Mandanten (z. B. der Demo) Mingas Lauf aus. Mit der neuen Rückmeldung aus Task 22 sähe er Minga-Kundennamen, also ein Datenleck zwischen Mandanten.
  - Ist nichts gesetzt, legt der erste Klick `/data/tenants/dev.db` an (`_build_engine`, `tenancy.py:104-108`). `registry.known_slugs()` (`tenancy.py:93-96`) führt sie danach als Mandanten, der Scheduler läuft auch für sie.
  - Nachgemessen (Prüfer, Kopie mit Plan-Endstand): Der Knopf-Test ohne Patch endet mit `sqlite3.OperationalError: no such table: subscriptions`, weil eine neue, leere `TENANTS_DIR/dev.db` entsteht. Im Repo steht `TENANTS_DIR` auf `./data/tenants`, und `backend/data/tenants/dev.db` ist eine echte lokale Dev-DB: Den Knopf-Test **nie** ohne den Patch auf `SessionLocal` laufen lassen.
- **Doppelanlage:** Der Scheduler läuft um 05:00 (`scheduler_service.py:102`, je Mandant mit gesetzter ContextVar). Eine Prüfung „gibt es die Abo-Bestellung schon?“ fehlt. Dass der Knopf bei Minga Doppelungen erzeugt hat, ist **nicht belegt**, weil er bisher gar nicht in Mingas DB lief (Ausnahme: `DEFAULT_TENANT_SLUG=minga`, Runbook B, Schritt 4). Sobald Task 22 den Knopf in den Mandanten der Anfrage legt, treffen 05:00-Lauf und Knopf dieselbe DB und denselben Tag. Ohne Sperre entstünde dann jede Abo-Bestellung doppelt.
- **Abo-Rechnungstask** `invoice_tasks.py:191-287` (`generate_recurring_invoices`) steht nicht in `celery_app.py:36-99` (beat_schedule) und nicht in `scheduler_service.py:87-105`; im Repo ruft ihn niemand auf (`git grep` über `backend/app`, `frontend/src`: nur die Definition selbst, `invoice_tasks.py:192` und `:200`). Er rechnet fest 0,08 € (Z. 265), ohne `product_id`, und mit dem Satz-Default von `InvoiceService.add_line` (`REDUZIERT`, `invoice_service.py:120`). Toter Code. Er wird entfernt, nicht repariert: Abos erzeugen Bestellungen, abgerechnet wird über die Bestellung.
- **Variable Bundles und deaktivierte Produkte im Abo.** Das Abo-Formular bietet alle Produkte an, auch `is_variable_bundle` (`Abonnements.tsx:435-444`, Kennzeichen 📦 in Z. 442). `create_order` weist eine Position auf ein variables Bundle ohne `variable_bundle_selections` mit 400 ab (`sales.py:990-997`, „variables Bundle — bitte Sorten auswählen“); laut Spec (Features, B1) fallen variable Bundles ohne Auswahl aus dem Packplan. Ein Abo hat keine Sortenauswahl. `Product.is_active` (`product.py:249`, Soft-Delete über `DELETE /products/{id}`, `products.py:149-157`) prüft weder der alte Lauf noch `create_order`.
- **Liefertag:** `date.today()` ist im Container die UTC-Zeit (kein `TZ` in `Dockerfile`, `backend/Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`; P1 geht ebenfalls von UTC aus; die Coolify-Umgebung ist ungeprüft). Der Scheduler feuert um 05:00 Europe/Berlin (`scheduler_service.py:84`), dann ist UTC derselbe Kalendertag. Ein Klick auf den Knopf zwischen 00:00 und 02:00 Uhr Berliner Zeit träfe den Vortag. Der A6-Hotfix rechnet deshalb mit `_today_berlin()` (`imports.py:17`, `:42-43`), Task 1 führt `order_status_service.heute_berlin()` ein; der Abo-Lauf nutzt sie (Task 22).

**Regeln, die P4 einführt:**

1. **Produkt eines Abos:** `product_id`, sonst die Variante (über ihr Elternprodukt), sonst die Legacy-Sorte. Bei der Sorte nur, wenn genau **ein** aktives Produkt an ihr hängt. Übersprungen wird außerdem ein Abo auf ein **deaktiviertes** Produkt (`is_active` ist `False`) und auf ein **variables Bundle** (es braucht eine Sortenauswahl, die ein Abo nicht hat; `create_order` lehnt so eine Position ab). Übersprungen heißt: Warnung im Log und in der Rückmeldung des Knopfs, keine Bestellung, auch kein leerer Kopf. Nie wieder „irgendein Produkt“.
2. **Position wie `create_order`:** Sonderpreis zum Liefertag vor Variantenpreis vor Basispreis. Name aus Produkt (und Variante). Einheit der Variante, sonst die des Abos. Satz aus dem Produktstamm. Die Menge kommt aus dem Abo. Wie in `create_order` gibt es keine Umrechnung zwischen Einheiten: Ein Abo mit Einheit `KISTE_6` und ohne Variante kostet Produktpreis × Menge, als wäre der Produktpreis ein Kistenpreis.
3. **Fälligkeit:** Liefertage sind Wochentage, das Intervall wählt Wochen bzw. Monate (Docstring `ist_faellig`). Ohne Liefertage bleibt das bisherige Verhalten.
4. **Je Abo und Liefertag höchstens eine Bestellung**, gleich in welchem Status. Eine stornierte Abo-Bestellung kommt nicht zurück. Erkannt wird sie ohne neue Spalte an `Order.notes` („Automatisch erstellt aus Abo <id>“), Kunde und Liefertag. Alle drei sind änderbar: Wer die Notiz einer Abo-Bestellung ändert, ihren Liefertag verschiebt oder den Entwurf löscht, bekommt sie beim nächsten Lauf desselben Tages zurück. Bewusst hingenommen (keine Schemaänderung), Hinweis an Gernot.
5. **Der Knopf verarbeitet den Mandanten der Anfrage** (Session aus `DBSession`), der 05:00-Lauf weiter jeden Mandanten mit `SessionLocal()` unter der vom Scheduler gesetzten ContextVar. Beide rufen dieselbe Funktion `abo_lauf(db, heute)`. **Liefertag** ist der Kalendertag in Europe/Berlin (`liefertag_heute()` → `order_status_service.heute_berlin()`), nicht die Container-Zeit.

**Review Focus (P4, getestet):**

1. **Kein beliebiges Produkt.** Getestet mit einem „Köder“-Produkt ohne Sorte zu 2,00 €, genau wie in Produktion (`test_produkt_abo_bekommt_produkt_preis_satz_und_einheit`, `test_abo_ohne_produkt_und_sorte_legt_nichts_an`).
2. **Übersprungen heißt: nichts angelegt.** Die Position entsteht vor dem Bestellkopf (`_create_order_from_subscription`). **Beleg dafür ist allein `test_lauf_ueberspringt_meldet_und_beliefert_die_anderen`:** Dort committet der Lauf nach dem abgefangenen Überspringen, ein vorher geflushter Kopf des kaputten Abos bliebe also stehen und `_p4_bestellungen(kaputt_id) == []` schlüge fehl. Die Einzeltests (`test_abo_ohne_produkt_und_sorte_legt_nichts_an`, `test_mehrdeutige_sorte_legt_nichts_an`, `test_variables_bundle_wird_uebersprungen`, `test_deaktiviertes_produkt_wird_uebersprungen`) belegen nur die Ausnahme: `_p4_anlegen` committet bei einer Ausnahme nicht, die Session rollt beim Schließen zurück. Derselbe Test zeigt, dass ein übersprungenes Abo den Lauf für die anderen nicht abbricht.
3. **Mehrere Liefertage und Start an einem Nicht-Liefertag** (`TestP4Faelligkeit`).
4. **05:00-Lauf + Knopf** am selben Tag ergeben eine Bestellung (`TestP4AboLauf`).
5. **Runbook B schreibt nur Entwürfe ohne Beleg.** Auftragsbestätigung, Lieferschein, Rechnung oder Lagerbewegung → Abbruch ohne Schreiben (im Planungslauf geprüft, kein Repo-Test).
6. **Mandant des Knopfs.** `process_today_subscriptions` darf `SessionLocal()` nicht mehr erreichen. `test_knopf_nutzt_den_mandanten_der_anfrage` patcht `SessionLocal` mit `side_effect=AssertionError(…)`: Er ist vor Task 22 rot aus genau diesem Grund und schreibt nie in `backend/data/tenants/dev.db`.

---

### Task 19: Fälligkeit — mehrere Liefertage, Start an einem Nicht-Liefertag

**Files:**
- Modify: `backend/app/tasks/subscription_tasks.py` Z. 1-2 (Imports), Z. 12-44 (`_is_subscription_due_today`), Z. 46-67 (`process_daily_subscriptions`), Z. 69-71, 112, 116, 157 (`_create_order_from_subscription`)
- Modify: `backend/tests/test_gernot_261008_paket2.py` (P4-Block ans Dateiende; doppelte Imports sind unschädlich)

**Interfaces:**
- Produces:
  - `subscription_tasks.ist_faellig(sub, heute: date) -> bool`. Liest nur `aktiv`, `intervall`, `liefertage`, `gueltig_von`, `gueltig_bis`, kein `date.today()`.
  - `subscription_tasks._is_subscription_due_today(sub) -> bool` bleibt als Name (`tests/test_features.py:125` importiert ihn) und ruft `ist_faellig(sub, date.today())`.
  - `subscription_tasks.process_daily_subscriptions(heute: Optional[date] = None)`. Der Scheduler und (bis Task 22) der Knopf rufen weiter ohne Argument.
  - `subscription_tasks._create_order_from_subscription(db, sub, heute: Optional[date] = None)`: Liefertag, Packtag und Positionsdatum = `heute`.
  - Test-Helfer `_p4_einheit`, `_p4_produkt`, `_p4_kunde`, `_p4_abo`, `_p4_bestellungen`, `_p4_anlegen`, `_p4_lauf`, `_p4_sub`, `_p4_faellige_tage`, Konstanten `_P4_MO`, `_P4_MI`, `_P4_DO`. Tasks 20–22 nutzen sie.

- [ ] **Step 1: P4-Block mit allen P4-Helfern und den Fälligkeitstests ans Dateiende anhängen**

```python
# ============================================================
# P4 — Abo-Bestellungen (A5)
#
# Der Abo-Lauf suchte das Produkt nur über seed_id. Produkt-Abos haben
# seed_id = None, daraus wurde WHERE products.seed_id IS NULL: Preis und
# Steuersatz irgendeines Produkts ohne Sorte, Text "Abo-Lieferung: Unknown"
# (LfA Förderbank Bayern, vier Entwürfe ab 14.09.2026, je 2,00 EUR).
# Die Fälligkeit prüfte zusätzlich den Abstand zu gueltig_von in ganzen
# Wochen: mehrere Liefertage wirkten nicht. Alle P4-Helfer tragen das
# Präfix _p4_, damit andere Abschnitte in dieselbe Datei schreiben können.
# ============================================================
import uuid
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal

_P4_MO = date(2026, 10, 5)   # Montag
_P4_MI = date(2026, 10, 7)   # Mittwoch
_P4_DO = date(2026, 10, 8)   # Donnerstag


def _p4_einheit(code="STK", name="Stück"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code=code).first()
        if unit is None:
            unit = UnitOfMeasure(code=code, name=name, category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _p4_produkt(client, name, sku, preis, **extra):
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": _p4_einheit(), **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p4_kunde(client, name="LfA Förderbank Bayern"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GEWERBE"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p4_abo(client, kunde, gueltig_von=_P4_MO, **felder):
    body = {
        "kunde_id": kunde["id"], "menge": 2, "einheit": "STUECK",
        "intervall": "WOECHENTLICH", "liefertage": [0],
        "gueltig_von": gueltig_von.isoformat(), **felder,
    }
    r = client.post("/api/v1/sales/subscriptions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _p4_bestellungen(abo_id=None):
    """Alle Bestellungen (optional nur die eines Abos) mit ihren Positionen."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.order import Order
    with TestingSessionLocal() as db:
        q = select(Order).options(selectinload(Order.lines)).order_by(Order.order_number)
        if abo_id:
            q = q.where(Order.notes.contains(f"Abo {abo_id}"))
        return [
            {
                "order_number": o.order_number,
                "status": o.status.value,
                "requested_delivery_date": o.requested_delivery_date,
                "total_net": o.total_net, "total_vat": o.total_vat, "total_gross": o.total_gross,
                "lines": [
                    {
                        "product_id": str(l.product_id) if l.product_id else None,
                        "product_variant_id": str(l.product_variant_id) if l.product_variant_id else None,
                        "beschreibung": l.beschreibung, "unit": l.unit,
                        "quantity": l.quantity, "unit_price": l.unit_price,
                        "tax_rate": l.tax_rate.value, "line_net": l.line_net,
                    }
                    for l in o.lines
                ],
            }
            for o in db.execute(q).scalars().all()
        ]


def _p4_anlegen(abo_id, heute=_P4_DO):
    """Legt die Abo-Bestellung an wie der Lauf, ohne Fälligkeitsprüfung."""
    from app.models.customer import Subscription
    from app.tasks.subscription_tasks import _create_order_from_subscription
    with TestingSessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(abo_id))
        _create_order_from_subscription(db, sub, heute)
        db.commit()


def _p4_lauf(heute):
    """Der echte Lauf (Scheduler bzw. "Heute verarbeiten") gegen die Test-DB."""
    from app.tasks.subscription_tasks import process_daily_subscriptions
    with patch("app.tasks.subscription_tasks.SessionLocal", TestingSessionLocal):
        return process_daily_subscriptions(heute=heute)


def _p4_sub(intervall, liefertage, gueltig_von, gueltig_bis=None, aktiv=True):
    """Abo nur mit den Feldern, die die Fälligkeit liest."""
    from app.models.customer import SubscriptionInterval
    return SimpleNamespace(
        aktiv=aktiv, intervall=SubscriptionInterval(intervall), liefertage=liefertage,
        gueltig_von=gueltig_von, gueltig_bis=gueltig_bis,
    )


def _p4_faellige_tage(sub, von, bis):
    from app.tasks.subscription_tasks import ist_faellig
    tage, tag = [], von
    while tag <= bis:
        if ist_faellig(sub, tag):
            tage.append(tag)
        tag += timedelta(days=1)
    return tage

class TestP4Faelligkeit:
    """A5: Mehrere Liefertage wirkten nicht; ein gueltig_von an einem
    Nicht-Liefertag hieß: nie liefern."""

    def test_woechentlich_mo_und_do_liefert_an_beiden_tagen(self):
        sub = _p4_sub("WOECHENTLICH", [0, 3], _P4_MO)
        assert _p4_faellige_tage(sub, _P4_MO, date(2026, 10, 18)) == [
            date(2026, 10, 5), date(2026, 10, 8), date(2026, 10, 12), date(2026, 10, 15),
        ]

    def test_woechentlich_start_an_einem_nicht_liefertag(self):
        """Das Formular setzt gueltig_von = heute. Am Mittwoch angelegt, montags geliefert."""
        sub = _p4_sub("WOECHENTLICH", [0], _P4_MI)
        assert _p4_faellige_tage(sub, _P4_MI, date(2026, 10, 25)) == [
            date(2026, 10, 12), date(2026, 10, 19),
        ]

    def test_zweiwoechentlich_zaehlt_kalenderwochen_ab_erster_lieferung(self):
        sub = _p4_sub("ZWEIWOECHENTLICH", [0, 3], _P4_MI)
        assert _p4_faellige_tage(sub, _P4_MI, date(2026, 10, 25)) == [
            date(2026, 10, 8), date(2026, 10, 19), date(2026, 10, 22),
        ]

    def test_monatlich_mit_liefertag_erster_montag_ab_stichtag(self):
        sub = _p4_sub("MONATLICH", [0], date(2026, 10, 15))
        assert _p4_faellige_tage(sub, date(2026, 10, 15), date(2026, 12, 31)) == [
            date(2026, 10, 19), date(2026, 11, 16), date(2026, 12, 21),
        ]

    def test_monatlich_ohne_liefertag_kappt_auf_monatsende(self):
        sub = _p4_sub("MONATLICH", None, date(2026, 8, 31))
        assert _p4_faellige_tage(sub, date(2026, 8, 31), date(2026, 11, 30)) == [
            date(2026, 8, 31), date(2026, 9, 30), date(2026, 10, 31), date(2026, 11, 30),
        ]

    def test_bisheriges_verhalten_bleibt(self):
        """Absicherung: Fälle, die schon vorher stimmten."""
        taeglich = _p4_sub("TAEGLICH", [0, 1, 2, 3, 4], _P4_MO)
        assert len(_p4_faellige_tage(taeglich, _P4_MO, date(2026, 10, 18))) == 10
        ohne_tage = _p4_sub("WOECHENTLICH", None, _P4_MI)
        assert _p4_faellige_tage(ohne_tage, _P4_MI, date(2026, 10, 21)) == [
            date(2026, 10, 7), date(2026, 10, 14), date(2026, 10, 21),
        ]
        beendet = _p4_sub("WOECHENTLICH", [0], _P4_MO, gueltig_bis=date(2026, 10, 11))
        assert _p4_faellige_tage(beendet, _P4_MO, date(2026, 10, 25)) == [date(2026, 10, 5)]
        pausiert = _p4_sub("WOECHENTLICH", [0], _P4_MO, aktiv=False)
        assert _p4_faellige_tage(pausiert, _P4_MO, date(2026, 10, 25)) == []

    def test_lauf_am_donnerstag_beliefert_mo_do_abo(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[0, 3])

        _p4_lauf(_P4_DO)

        bestellungen = _p4_bestellungen(abo["id"])
        assert len(bestellungen) == 1
        assert bestellungen[0]["requested_delivery_date"] == _P4_DO
        assert bestellungen[0]["status"] == "ENTWURF"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestP4 -v`
Erwartet: **7 failed.** Sechs mit `ImportError: cannot import name 'ist_faellig' from 'app.tasks.subscription_tasks'`, `test_lauf_am_donnerstag_beliefert_mo_do_abo` mit `TypeError: process_daily_subscriptions() got an unexpected keyword argument 'heute'`. `test_bisheriges_verhalten_bleibt` ist eine Absicherung bestehenden Verhaltens; sie scheitert hier nur am fehlenden Namen.

- [ ] **Step 3: Imports**

In `backend/app/tasks/subscription_tasks.py` die Zeilen 1-2

```python
from datetime import date
from decimal import Decimal
```

ersetzen durch:

```python
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
```

- [ ] **Step 4: `_is_subscription_due_today` (Z. 12-44) vollständig ersetzen**

Die ganze Funktion bis vor `@shared_task` ersetzen durch:

```python
def _montag(tag: date) -> date:
    return tag - timedelta(days=tag.weekday())


def _stichtag(jahr: int, monat: int, tag: int) -> date:
    """Tag `tag` im Monat, auf das Monatsende gekappt (31. -> 30.09.)."""
    return date(jahr, monat, min(tag, monthrange(jahr, monat)[1]))


def ist_faellig(sub, heute: date) -> bool:
    """Ist das Abo an `heute` zu liefern?

    Liefertage (0 = Montag ... 6 = Sonntag) sind die Wochentage, an denen
    geliefert wird. Das Intervall sagt, in welchen Wochen bzw. Monaten:

    - TAEGLICH: jeden Tag; mit Liefertagen nur an diesen.
    - WOECHENTLICH: jede Woche an jedem Liefertag. Ohne Liefertage am
      Wochentag von gueltig_von.
    - ZWEIWOECHENTLICH: jede zweite Kalenderwoche an jedem Liefertag. Woche 0
      ist die Woche der ersten Lieferung ab gueltig_von. Ohne Liefertage alle
      14 Tage ab gueltig_von.
    - MONATLICH: Stichtag ist der Tag des Monats von gueltig_von, auf das
      Monatsende gekappt. Ohne Liefertage wird am Stichtag geliefert, mit
      Liefertagen am ersten Liefertag ab dem Stichtag (je Liefertag einmal
      in den sieben Tagen ab Stichtag).

    Bis Oktober 2026 galt zusätzlich (heute - gueltig_von) % 7 == 0 bzw. % 14.
    Ein Abo lieferte damit nur am Wochentag von gueltig_von: bei Mo + Do nur
    montags, und nie, wenn gueltig_von auf keinen Liefertag fiel.
    """
    if not sub.aktiv:
        return False
    if heute < sub.gueltig_von:
        return False
    if sub.gueltig_bis and heute > sub.gueltig_bis:
        return False

    liefertage = {int(t) for t in (sub.liefertage or [])}
    if liefertage and heute.weekday() not in liefertage:
        return False

    if sub.intervall == SubscriptionInterval.TAEGLICH:
        return True
    if sub.intervall == SubscriptionInterval.WOECHENTLICH:
        return bool(liefertage) or heute.weekday() == sub.gueltig_von.weekday()
    if sub.intervall == SubscriptionInterval.ZWEIWOECHENTLICH:
        if not liefertage:
            return (heute - sub.gueltig_von).days % 14 == 0
        erste_lieferung = min(
            sub.gueltig_von + timedelta(days=(t - sub.gueltig_von.weekday()) % 7)
            for t in liefertage
        )
        wochen = (_montag(heute) - _montag(erste_lieferung)).days // 7
        return wochen % 2 == 0
    if sub.intervall == SubscriptionInterval.MONATLICH:
        if not liefertage:
            return heute == _stichtag(heute.year, heute.month, sub.gueltig_von.day)
        vormonat = heute.replace(day=1) - timedelta(days=1)
        return any(
            0 <= (heute - _stichtag(jahr, monat, sub.gueltig_von.day)).days < 7
            for jahr, monat in ((heute.year, heute.month), (vormonat.year, vormonat.month))
        )
    return False


def _is_subscription_due_today(sub: Subscription) -> bool:
    """Prüft ob Abo heute fällig ist (alter Name, ruft ist_faellig)."""
    return ist_faellig(sub, date.today())
```

- [ ] **Step 5: `process_daily_subscriptions` (Z. 46-67) vollständig ersetzen**

Von `@shared_task` bis vor `def _create_order_from_subscription` ersetzen durch:

```python
@shared_task
def process_daily_subscriptions(heute: Optional[date] = None):
    """Täglicher Task: Erstellt Entwurfs-Bestellungen aus aktiven Abos."""
    heute = heute or date.today()
    db = SessionLocal()
    try:
        # Aktive Abos laden
        subs = db.execute(
            select(Subscription).where(Subscription.aktiv == True)
        ).scalars().all()

        created_count = 0

        for sub in subs:
            if ist_faellig(sub, heute):
                _create_order_from_subscription(db, sub, heute)
                created_count += 1

        db.commit()
        return f"{created_count} orders created from subscriptions"
    finally:
        db.close()
```

- [ ] **Step 6: `_create_order_from_subscription` bekommt den Liefertag**

(a) Kopf (Z. 69-71)

```python
def _create_order_from_subscription(db, sub: Subscription):
    """Erstellt eine Order aus einem Abo."""
    customer = sub.kunde
```

ersetzen durch:

```python
def _create_order_from_subscription(db, sub: Subscription, heute: Optional[date] = None):
    """Erstellt eine Order aus einem Abo für den Liefertag `heute`."""
    heute = heute or date.today()
    customer = sub.kunde
```

(b) In derselben Funktion genau drei Stellen `date.today()` durch `heute` ersetzen: `requested_delivery_date=date.today(),` im `Order(...)` (Z. 112), `packing_date=Order.resolve_packing_date(date.today(), None),` (Z. 116) und `requested_delivery_date=date.today()` im `OrderLine(...)` (Z. 157). Danach steht `date.today()` in der Funktion nur noch in `heute = heute or date.today()`. `_generate_order_number` (sales.py) behält sein eigenes `date.today()` — die Nummer zeigt den Anlagetag.

- [ ] **Step 7: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestP4 -v`
Erwartet: **7 passed.**

- [ ] **Step 8: Umfeld**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_features.py -q`
Erwartet: einziger Fehlschlag `test_features.py::TestFeatures::test_subscription_processing` (Baseline; scheitert an `async def` ohne Plugin, nicht an der Fälligkeit).

- [ ] **Step 9: Commit**

```bash
git add backend/app/tasks/subscription_tasks.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(abo): mehrere Liefertage wirkten nicht, Start an einem Nicht-Liefertag lieferte nie"
```

---

### Task 20: Toten Abo-Rechnungstask entfernen

**Files:**
- Modify: `backend/app/tasks/invoice_tasks.py` Z. 191-289 (Decorator `@celery_app.task(name="app.tasks.invoice_tasks.generate_recurring_invoices", …)` bis einschließlich der zwei Leerzeilen vor `@celery_app.task(name="app.tasks.invoice_tasks.calculate_revenue_stats")`)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Removes: `invoice_tasks.generate_recurring_invoices`. Kein Aufrufer, kein Eintrag in `celery_app.conf.beat_schedule` oder `scheduler_service.start_scheduler`.

- [ ] **Step 1: Test anhängen**

```python
class TestP4AboRechnungstask:
    """A5: Der nie eingeplante Abo-Rechnungstask rechnete fest 0,08 EUR und 7 %."""

    def test_abo_rechnungstask_ist_entfernt(self):
        import app.tasks.invoice_tasks as invoice_tasks
        assert not hasattr(invoice_tasks, "generate_recurring_invoices")
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k Rechnungstask -v`
Erwartet: 1 failed, `AssertionError: assert not True`.

- [ ] **Step 3: Funktion löschen**

In `backend/app/tasks/invoice_tasks.py` den Block ab `@celery_app.task(` (Z. 191, die Zeile direkt über `name="app.tasks.invoice_tasks.generate_recurring_invoices",`) bis einschließlich `        db.close()` (Z. 287) und die zwei folgenden Leerzeilen löschen. Danach folgt auf `send_payment_reminders` (endet mit `        db.close()`) nach zwei Leerzeilen direkt `@celery_app.task(name="app.tasks.invoice_tasks.calculate_revenue_stats")`. Die Imports bleiben: `Decimal`, `timedelta` und `func` werden weiter genutzt (Z. 58-60, 132-145, 308-334).

Prüfen (aus dem Repo-Wurzelverzeichnis): `git grep -n -e generate_recurring_invoices -e recurring_invoices -- backend/app frontend/src` → keine Treffer. Nicht `grep -r` über `backend`: Das träfe den eigenen Test aus Step 1 (`backend/tests/test_gernot_261008_paket2.py`, `hasattr(invoice_tasks, "generate_recurring_invoices")`), die veralteten, nicht versionierten Bytecode-Dateien `backend/app/tasks/__pycache__/invoice_tasks.cpython-311.pyc` und `-314.pyc` (`__pycache__/` steht in `.gitignore`; die `.venv` ist Python 3.14, die `-311.pyc` wird nie neu erzeugt) und durchsuchte `backend/venv` und `backend/venv311` (zusammen rund 860 MB).

- [ ] **Step 4: Grün bestätigen**

Run: wie Step 2. Erwartet: 1 passed. Dann `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_dunning.py tests/test_production_readiness.py -q`. Erwartet nur die Baseline-Namen `test_production_readiness.py::test_dunning_level1/2/3`, `::test_quality_auto_approved`, `::test_quality_rejected_low_note`, `::test_quality_rejected_high_loss`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/invoice_tasks.py backend/tests/test_gernot_261008_paket2.py
git commit -m "chore(rechnung): nie eingeplanten Abo-Rechnungstask mit festem Preis 0,08 EUR entfernt"
```

---

### Task 21: Abo-Position aus Produkt bzw. Variante, mit Kundenpreis und Produktsatz

**Files:**
- Modify: `backend/app/tasks/subscription_tasks.py` (Kopf, zwei neue Funktionen, `process_daily_subscriptions`, `_create_order_from_subscription`)
- Modify: `backend/tests/test_gernot_260817.py` Z. 215, 227-240, 288-290
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: `app.services.pricing_service.resolve_unit_price(db, customer_id, product_id, default, on_date) -> tuple[Decimal, bool]` (wie `create_order`, `sales.py:956-962`); `app.api.v1.sales._calculate_line_amounts(line)`, `_calculate_order_totals(order)`, `_generate_order_number(db)`.
- Produces:
  - `subscription_tasks.AboUebersprungen(Exception)`: die Meldung nennt den Grund.
  - `subscription_tasks._abo_produkt(db, sub) -> tuple[Product, Optional[ProductVariant]]`, wirft `AboUebersprungen` (kein oder mehrdeutiges Produkt, fremde Variante, Produkt deaktiviert, variables Bundle).
  - `subscription_tasks.abo_position(db, sub, heute: date) -> OrderLine`: transient, nicht in der Session. Wirft `AboUebersprungen`. Das Runbook Runbook B nutzt sie.
  - `_create_order_from_subscription(db, sub, heute=None) -> Order` wirft `AboUebersprungen`, **bevor** etwas angelegt ist.
  - `process_daily_subscriptions` gibt `{"status": "ok", "erstellt": int, "uebersprungen": [{"abo_id": str, "kunde": str, "grund": str}]}` zurück statt eines Texts. `_safe_wrap` (`scheduler_service.py:49`) liest `status`. Der Knopf reicht das Dict bis Task 22 unverändert als `details` durch.

- [ ] **Step 1: Tests anhängen**

```python
class TestP4AboPosition:
    """A5: Position aus Produkt bzw. Variante, mit Kundenpreis und Produktsatz."""

    def _koeder(self, client):
        """Wie in Produktion: ein Produkt ohne Sorte, das der alte Lauf griff."""
        return _p4_produkt(client, "Mehrwegkiste leer", "P4-KOEDER", "2.00")

    def test_produkt_abo_bekommt_produkt_preis_satz_und_einheit(self, client):
        kunde = _p4_kunde(client)
        self._koeder(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50",
                              tax_rate="STANDARD")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], einheit="KISTE_6")

        _p4_anlegen(abo["id"])

        [bestellung] = _p4_bestellungen(abo["id"])
        [zeile] = bestellung["lines"]
        # Vorher: ("Abo-Lieferung: Unknown", 2,00, REDUZIERT) vom Köder-Produkt
        assert (zeile["beschreibung"], zeile["unit_price"], zeile["tax_rate"]) == (
            "BIO Snackbox | Amaranth", Decimal("4.50"), "STANDARD")
        assert zeile["product_id"] == produkt["id"]
        assert zeile["unit"] == "KISTE_6"
        assert zeile["line_net"] == Decimal("9.00")
        assert bestellung["total_vat"] == Decimal("1.71")
        assert bestellung["total_gross"] == Decimal("10.71")

    def test_sonderpreis_des_kunden_gilt(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices", json={
            "product_id": produkt["id"], "unit_price": "4.20", "valid_from": "2026-09-01",
        })
        assert r.status_code in (200, 201), r.text
        abo = _p4_abo(client, kunde, product_id=produkt["id"])

        _p4_anlegen(abo["id"])

        [bestellung] = _p4_bestellungen(abo["id"])
        assert bestellung["lines"][0]["unit_price"] == Decimal("4.20")

    def test_variante_liefert_name_einheit_und_preis(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        r = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
            "packaging_unit_id": _p4_einheit("KISTE_12", "Mehrwegkiste 12"),
            "name_suffix": "12er Mehrwegkiste", "price_override": "48.00", "items_per_pack": 12,
        })
        assert r.status_code in (200, 201), r.text
        variante = r.json()
        abo = _p4_abo(client, kunde, product_id=produkt["id"],
                      product_variant_id=variante["id"], menge=1)

        _p4_anlegen(abo["id"])

        [zeile] = _p4_bestellungen(abo["id"])[0]["lines"]
        assert zeile["product_variant_id"] == variante["id"]
        assert zeile["beschreibung"] == "BIO Snackbox | Amaranth — 12er Mehrwegkiste"
        assert zeile["unit"] == "KISTE_12"
        assert zeile["unit_price"] == Decimal("48.00")

    def test_abo_ohne_produkt_und_sorte_legt_nichts_an(self, client):
        from app.models.customer import Subscription, SubscriptionInterval
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        self._koeder(client)
        with TestingSessionLocal() as db:
            sub = Subscription(
                kunde_id=uuid.UUID(kunde["id"]), menge=Decimal("2"), einheit="STUECK",
                intervall=SubscriptionInterval.WOECHENTLICH, liefertage=[3], gueltig_von=_P4_MO,
            )
            db.add(sub)
            db.commit()
            abo_id = str(sub.id)

        with pytest.raises(AboUebersprungen):
            _p4_anlegen(abo_id)
        assert _p4_bestellungen() == []

    def test_mehrdeutige_sorte_legt_nichts_an(self, client):
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        sorte = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7,
            "erntefenster_max_tage": 8, "ertrag_gramm_pro_tray": 350,
        }).json()
        _p4_produkt(client, "Kresse Schale", "P4-KR-S", "3.00", seed_id=sorte["id"])
        _p4_produkt(client, "Kresse Kiste", "P4-KR-K", "30.00", seed_id=sorte["id"])
        abo = _p4_abo(client, kunde, seed_id=sorte["id"])

        with pytest.raises(AboUebersprungen):
            _p4_anlegen(abo["id"])
        assert _p4_bestellungen() == []

    def test_lauf_ueberspringt_meldet_und_beliefert_die_anderen(self, client):
        from app.models.customer import Subscription, SubscriptionInterval
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        gut = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[3])
        with TestingSessionLocal() as db:
            kaputt = Subscription(
                kunde_id=uuid.UUID(kunde["id"]), menge=Decimal("2"), einheit="STUECK",
                intervall=SubscriptionInterval.WOECHENTLICH, liefertage=[3], gueltig_von=_P4_MO,
            )
            db.add(kaputt)
            db.commit()
            kaputt_id = str(kaputt.id)

        ergebnis = _p4_lauf(_P4_DO)

        assert ergebnis["erstellt"] == 1
        assert [u["abo_id"] for u in ergebnis["uebersprungen"]] == [kaputt_id]
        assert len(_p4_bestellungen(gut["id"])) == 1
        assert _p4_bestellungen(kaputt_id) == []

    def test_sorten_abo_mit_eindeutigem_produkt(self, client):
        """Absicherung: Legacy-Abos über die Sorte liefern weiter das Produkt der Sorte."""
        kunde = _p4_kunde(client)
        sorte = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7,
            "erntefenster_max_tage": 8, "ertrag_gramm_pro_tray": 350,
        }).json()
        self._koeder(client)
        _p4_produkt(client, "Kresse Schale", "P4-KR-S", "3.00", seed_id=sorte["id"])
        abo = _p4_abo(client, kunde, seed_id=sorte["id"])

        _p4_anlegen(abo["id"])

        [zeile] = _p4_bestellungen(abo["id"])[0]["lines"]
        assert zeile["unit_price"] == Decimal("3.00")
        assert zeile["tax_rate"] == "REDUZIERT"

    def test_variables_bundle_wird_uebersprungen(self, client):
        """create_order lehnt ein variables Bundle ohne Sortenauswahl ab
        (sales.py, 'bitte Sorten auswählen'); ein Abo hat keine Auswahl."""
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        tray = _p4_produkt(client, "Gastrotray 4 Sorten", "P4-TRAY", "18.00",
                           is_variable_bundle=True, variable_bundle_min_slots=4,
                           variable_bundle_max_slots=4)
        abo = _p4_abo(client, kunde, product_id=tray["id"])

        with pytest.raises(AboUebersprungen, match="variables Bundle"):
            _p4_anlegen(abo["id"])
        assert _p4_bestellungen() == []

    def test_deaktiviertes_produkt_wird_uebersprungen(self, client):
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"])
        r = client.delete(f"/api/v1/products/{produkt['id']}")  # Soft-Delete: is_active = False
        assert r.status_code == 204, r.text

        with pytest.raises(AboUebersprungen, match="deaktiviert"):
            _p4_anlegen(abo["id"])
        assert _p4_bestellungen() == []
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k AboPosition -v`
Erwartet: **8 failed, 1 passed.**
- `test_produkt_abo_bekommt_produkt_preis_satz_und_einheit`: `At index 0 diff: 'Abo-Lieferung: Unknown' != 'BIO Snackbox | Amaranth'`. Das ist das Produktionsbild: Der Lauf griff das Köder-Produkt zu 2,00 € und dessen 7 %.
- `test_sonderpreis_des_kunden_gilt`: `assert Decimal('4.5000') == Decimal('4.20')`.
- `test_variante_liefert_name_einheit_und_preis`: `assert None == '<uuid der Variante>'`.
- `test_abo_ohne_produkt_und_sorte_legt_nichts_an`, `test_mehrdeutige_sorte_legt_nichts_an`, `test_variables_bundle_wird_uebersprungen`, `test_deaktiviertes_produkt_wird_uebersprungen`: `ImportError: cannot import name 'AboUebersprungen'`.
- `test_lauf_ueberspringt_meldet_und_beliefert_die_anderen`: `TypeError: string indices must be integers, not 'str'`. Heute kommt ein Text zurück, und das kaputte Abo hätte eine Bestellung bekommen.
- Grün ist `test_sorten_abo_mit_eindeutigem_produkt`. Er sichert das Legacy-Verhalten über die Sorte ab.

- [ ] **Step 3: Kopf der Datei ersetzen**

Alles von Zeile 1 bis einschließlich `from typing import List` ersetzen durch den folgenden Block. `PriceList` und `PriceListItem` fallen weg: Preislisten haben keinen Endpunkt, und `create_order` nutzt sie nicht.

```python
import logging
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from celery import shared_task
from sqlalchemy import select
from app.database import SessionLocal
from app.models.customer import Subscription, SubscriptionInterval
from app.models.order import Order, OrderLine, OrderStatus, TaxRate
from app.models.product import Product, ProductVariant
from app.models.unit import UnitOfMeasure
from app.services.pricing_service import resolve_unit_price
from app.api.v1.sales import router
from typing import List

logger = logging.getLogger(__name__)


class AboUebersprungen(Exception):
    """Das Abo wird nicht beliefert; die Meldung nennt den Grund."""
```

- [ ] **Step 4: Produkt und Position — direkt vor `@shared_task` einfügen**

Hinter `_is_subscription_due_today` (aus Task 19) und vor `@shared_task`:

```python
def _abo_produkt(db, sub) -> tuple[Product, Optional[ProductVariant]]:
    """Produkt und Verpackungsvariante, die das Abo liefert.

    Vorrang: product_id, dann die Variante (über ihr Elternprodukt), dann das
    Legacy-Feld seed_id, dort nur, wenn genau ein aktives Produkt an der
    Sorte hängt. Ein deaktiviertes Produkt und ein variables Bundle werden
    nicht geliefert. Bis Oktober 2026 suchte der Lauf nur über seed_id. Bei
    Produkt-Abos (seed_id leer) entstand daraus WHERE products.seed_id IS NULL,
    also Preis und Steuersatz irgendeines Produkts ohne Sorte
    ("Abo-Lieferung: Unknown", LfA Förderbank Bayern ab 14.09.2026).
    """
    variante = None
    if sub.product_variant_id:
        variante = db.get(ProductVariant, sub.product_variant_id)
        if variante is None:
            raise AboUebersprungen(f"Verpackungsvariante {sub.product_variant_id} existiert nicht")

    if sub.product_id:
        produkt = db.get(Product, sub.product_id)
        if produkt is None:
            raise AboUebersprungen(f"Produkt {sub.product_id} existiert nicht")
    elif variante is not None:
        produkt = variante.parent_product
    elif sub.seed_id:
        treffer = db.execute(
            select(Product).where(Product.seed_id == sub.seed_id, Product.is_active == True)
        ).scalars().all()
        if len(treffer) != 1:
            raise AboUebersprungen(
                f"Sorte {sub.seed_id}: {len(treffer)} aktive Produkte, das Abo braucht genau eines"
            )
        produkt = treffer[0]
    else:
        raise AboUebersprungen("Abo hat weder Produkt noch Sorte")

    if variante is not None and variante.parent_product_id != produkt.id:
        raise AboUebersprungen("Verpackungsvariante gehört nicht zum Abo-Produkt")
    # "is False": nur ein ausdrücklich deaktiviertes Produkt (DELETE /products/{id}).
    if produkt.is_active is False:
        raise AboUebersprungen(f"Produkt {produkt.name} ist deaktiviert")
    if produkt.is_variable_bundle:
        # create_order verlangt dafür eine Sortenauswahl (variable_bundle_selections),
        # ohne sie fällt die Position aus dem Packplan. Ein Abo hat keine.
        raise AboUebersprungen(
            f"{produkt.name} ist ein variables Bundle und braucht eine Sortenauswahl"
        )
    return produkt, variante


def abo_position(db, sub, heute: date) -> OrderLine:
    """Bestellposition einer Abo-Lieferung an `heute`.

    Preis wie in create_order (sales.py, Positionsschleife): Sonderpreis des
    Kunden (resolve_unit_price, Stichtag = Liefertag) vor Variantenpreis vor
    Basispreis. Steuersatz aus dem Produktstamm. Einheit der Variante, sonst
    die des Abos. Wirft AboUebersprungen, bevor etwas angelegt ist.
    """
    from app.api.v1.sales import _calculate_line_amounts

    produkt, variante = _abo_produkt(db, sub)

    preis, ist_sonderpreis = resolve_unit_price(
        db, customer_id=sub.kunde_id, product_id=produkt.id,
        default=produkt.base_price, on_date=heute,
    )
    name = produkt.name
    einheit = sub.einheit
    if variante is not None:
        name = f"{produkt.name} — {variante.name_suffix or ''}".strip(" —")
        verpackung = db.get(UnitOfMeasure, variante.packaging_unit_id)
        if verpackung is not None:
            einheit = verpackung.code
        if not ist_sonderpreis:
            if variante.price_override is not None:
                preis = variante.price_override
            elif produkt.base_price is not None:
                preis = produkt.base_price

    if not preis:
        logger.warning("[abo] Abo %s: %s hat keinen Preis, Position mit 0,00 EUR", sub.id, produkt.name)

    line = OrderLine(
        position=1,
        product_id=produkt.id,
        product_variant_id=variante.id if variante is not None else None,
        seed_id=sub.seed_id,
        beschreibung=name,
        # Durchgehend Decimal: Decimal * float wirft.
        quantity=Decimal(str(sub.menge)),
        unit=einheit,
        unit_price=Decimal(str(preis or 0)),
        tax_rate=produkt.tax_rate or TaxRate.REDUZIERT,
        requested_delivery_date=heute,
    )
    _calculate_line_amounts(line)
    return line
```

Abweichung zu `create_order`, mit Absicht: Der Sonderpreis gilt zum **Liefertag** (`on_date=heute`), nicht zum Anlagetag. Beim täglichen Lauf ist das derselbe Tag. Bei der Korrektur alter Entwürfe (Runbook B) zählt so der Preis, der am Liefertag galt.

- [ ] **Step 5: `process_daily_subscriptions` (Stand Task 19) vollständig ersetzen**

```python
@shared_task
def process_daily_subscriptions(heute: Optional[date] = None):
    """Täglicher Task: Erstellt Entwurfs-Bestellungen aus aktiven Abos."""
    heute = heute or date.today()
    db = SessionLocal()
    try:
        # Aktive Abos laden
        subs = db.execute(
            select(Subscription).where(Subscription.aktiv == True)
        ).scalars().all()

        erstellt = 0
        uebersprungen = []
        for sub in subs:
            if not ist_faellig(sub, heute):
                continue
            try:
                _create_order_from_subscription(db, sub, heute)
                erstellt += 1
            except AboUebersprungen as grund:
                kunde = sub.kunde.name if sub.kunde else str(sub.kunde_id)
                logger.warning("[abo] Abo %s (%s) übersprungen: %s", sub.id, kunde, grund)
                uebersprungen.append({"abo_id": str(sub.id), "kunde": kunde, "grund": str(grund)})

        db.commit()
        # Dict statt Text: _safe_wrap (scheduler_service.py) liest "status",
        # der Knopf "Heute verarbeiten" die Zahlen.
        return {"status": "ok", "erstellt": erstellt, "uebersprungen": uebersprungen}
    finally:
        db.close()
```

- [ ] **Step 6: `_create_order_from_subscription` bis Dateiende ersetzen**

Ab `def _create_order_from_subscription(` bis zum Dateiende ersetzen durch den folgenden Block. Adressblock und Kopf sind unverändert. Neu: Die Position entsteht zuerst, die Preisfindung (Z. 125-158) fällt weg.

```python
def _create_order_from_subscription(db, sub: Subscription, heute: Optional[date] = None) -> Order:
    """Erstellt eine Order aus einem Abo für den Liefertag `heute`.

    Wirft AboUebersprungen, ohne etwas anzulegen, wenn kein eindeutiges
    Produkt feststeht.
    """
    from app.api.v1.sales import _generate_order_number, _calculate_order_totals

    heute = heute or date.today()
    # Zuerst die Position: steht kein Produkt fest, entsteht auch kein Kopf.
    line = abo_position(db, sub, heute)

    customer = sub.kunde
    order_number = _generate_order_number(db)

    # Adressen
    billing_addr = None
    if customer.billing_address:
         billing_addr = {
            "name": customer.billing_address.name or customer.name,
            "strasse": customer.billing_address.strasse,
            "hausnummer": customer.billing_address.hausnummer,
            # ohne adresszusatz fehlt die Zustellinfo auf allen Abo-Belegen
            "adresszusatz": customer.billing_address.adresszusatz,
            "plz": customer.billing_address.plz,
            "ort": customer.billing_address.ort,
            "land": customer.billing_address.land
        }
    else:
        # Fallback minimal
        billing_addr = {"name": customer.name, "strasse": "TBD", "plz": "00000", "ort": "TBD"}

    delivery_addr = None
    if customer.shipping_address:
        delivery_addr = {
            "name": customer.shipping_address.name or customer.name,
            "strasse": customer.shipping_address.strasse,
            "hausnummer": customer.shipping_address.hausnummer,
            "adresszusatz": customer.shipping_address.adresszusatz,
            "plz": customer.shipping_address.plz,
            "ort": customer.shipping_address.ort,
            "land": customer.shipping_address.land
        }

    order = Order(
        order_number=order_number,
        customer_id=sub.kunde_id,
        billing_address=billing_addr,
        delivery_address=delivery_addr,
        requested_delivery_date=heute,
        # Abos liefern am Lauftag — ohne festgeschriebenen Packtag läge der
        # Standard-Packtag (Vortag) in der Vergangenheit und die Ware stünde
        # in keinem Tagesplan mehr.
        packing_date=Order.resolve_packing_date(heute, None),
        status=OrderStatus.ENTWURF,
        currency="EUR",
        notes=f"Automatisch erstellt aus Abo {sub.id}",
        internal_notes="Subscription Run"
    )
    db.add(order)
    db.flush()

    # Über die Beziehung anhängen: order.lines ist bei einer frisch erzeugten
    # Order eine leere Liste, die kein Lazy-Load mehr nachlädt — mit db.add()
    # allein summierte _calculate_order_totals über nichts und die Abo-
    # Bestellung blieb bei 0,00 €.
    order.lines.append(line)

    _calculate_order_totals(order)
    return order
```

Reihenfolge der Datei danach: Kopf, `AboUebersprungen`, `_montag`, `_stichtag`, `ist_faellig`, `_is_subscription_due_today`, `_abo_produkt`, `abo_position`, `process_daily_subscriptions`, `_create_order_from_subscription`.

- [ ] **Step 7: Neue Tests grün, bestehende Abo-Tests rot**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestP4 -q`, dann `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py -q`
Erwartet: P4-Tests 17 passed. Zwei Fehlschläge in `test_gernot_260817.py`, beide mit `AttributeError: '_FakeSub' object has no attribute 'product_variant_id'`: `TestPacktag::test_abo_bestellung_faellt_nicht_aus_dem_tagesplan` und `TestPacktag::test_abo_lauf_rechnet_mit_produktpreis`.

- [ ] **Step 8: `_FakeSub` in `tests/test_gernot_260817.py` anpassen (bewusste Änderung bestehender Erwartungen)**

Begründung: Der Lauf liest jetzt `product_id` und `product_variant_id`. Der erste Test baut ein Abo ohne Produkt und ohne Sorte. Genau das legt seit A5 **keine** Bestellung mehr an, sondern wird übersprungen (Regel 1). Der Test prüft aber den Packtag, nicht die Produktwahl. Deshalb bekommt er ein Produkt; Packtag und Tagesplan-Erwartung bleiben unverändert. Der zweite Test bleibt ein Legacy-Sorten-Abo und bekommt nur die neuen Felder mit `None`.

(a) Z. 215 ersetzen:

```python
    def test_abo_bestellung_faellt_nicht_aus_dem_tagesplan(self, client):
```

durch

```python
    def test_abo_bestellung_faellt_nicht_aus_dem_tagesplan(self, client, base_unit):
```

(b) Z. 227-240 ersetzen:

```python
        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Abo-Kunde", "typ": "GASTRO",
        }).json()

        db = TestingSessionLocal()
        try:
            class _FakeSub:
                """Minimal-Abo — der Task liest nur diese Felder."""
                id = "abo-1"
                kunde_id = UUID(kunde["id"])
                seed_id = None
                seed = None
                menge = 2
                einheit = "STUECK"
```

durch

```python
        kunde = client.post("/api/v1/sales/customers", json={
            "name": "Abo-Kunde", "typ": "GASTRO",
        }).json()
        # Seit A5 (08.10.2026) überspringt der Lauf Abos ohne Produkt und
        # ohne Sorte, statt irgendein Produkt zu nehmen — das Abo braucht eins.
        produkt = client.post("/api/v1/products", json={
            "sku": "ABO-TP", "name": "Kresse Schale", "category": "MICROGREEN",
            "base_price": 4.5,
        })
        assert produkt.status_code == 201, produkt.text

        db = TestingSessionLocal()
        try:
            class _FakeSub:
                """Minimal-Abo — der Task liest nur diese Felder."""
                id = "abo-1"
                kunde_id = UUID(kunde["id"])
                seed_id = None
                seed = None
                product_id = UUID(produkt.json()["id"])
                product_variant_id = None
                menge = 2
                einheit = "STUECK"
```

(c) Im zweiten `_FakeSub` (Z. 288-290)

```python
                seed_id = sorten_id
                seed = None
                menge = Decimal("2.00")
```

ersetzen durch

```python
                seed_id = sorten_id
                seed = None
                product_id = None  # Legacy-Abo über die Sorte
                product_variant_id = None
                menge = Decimal("2.00")
```

- [ ] **Step 9: Grün und Umfeld**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestP4 -q`, dann `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_260821.py tests/test_gernot_260917.py tests/test_features.py -q`
Erwartet: einziger Fehlschlag `test_features.py::TestFeatures::test_subscription_processing` (Baseline). P4-Datei 17 passed (Tasks 19–21), `test_gernot_260817.py` 20 passed.

- [ ] **Step 10: Commit**

```bash
git add backend/app/tasks/subscription_tasks.py backend/tests/test_gernot_261008_paket2.py backend/tests/test_gernot_260817.py
git commit -m "fix(abo): Abo-Bestellung mit Abo-Produkt, Kundenpreis und Produktsatz statt 'Abo-Lieferung: Unknown'"
```

---

### Task 22: Knopf im Mandanten der Anfrage, Berliner Kalendertag, je Abo und Liefertag eine Bestellung

**Files:**
- Modify: `backend/app/tasks/subscription_tasks.py` (Imports, `liefertag_heute`, `_abo_bestellung_vorhanden`, `abo_lauf`, `process_daily_subscriptions`)
- Modify: `backend/app/api/v1/sales.py` Z. 582-588 (`process_today_subscriptions`)
- Test: `backend/tests/test_gernot_261008_paket2.py`

**Interfaces:**
- Consumes: `order_status_service.heute_berlin() -> date` (Task 1).
- Produces:
  - `subscription_tasks.liefertag_heute() -> date`: Kalendertag in Europe/Berlin; ruft `order_status_service.heute_berlin()` (Task 1). **Zusammengeführt:** Der Einzelabschnitt brachte eine eigene Rechnung mit `datetime`/`ZoneInfo` mit, um von P1 unabhängig zu bleiben; hier steht Task 1 vorher, also gibt es nur eine Stelle. `imports._today_berlin()` bleibt (Hotfix `efcea00`, Folgepunkt F3). Diese Fassung ist nicht gemessen: Scheitert `test_liefertag_ist_der_berliner_kalendertag` nach Step 4, stoppen und melden.
  - `subscription_tasks._abo_bestellung_vorhanden(db, sub, heute: date) -> bool`. Erkennt Abo-Bestellungen am Text `Automatisch erstellt aus Abo {sub.id}` in `Order.notes`, dazu Kunde und Liefertag, in jedem Status.
  - `subscription_tasks.abo_lauf(db, heute: date) -> dict`: der Rumpf des bisherigen Laufs auf einer **übergebenen** Session; committet. Ergebnis `{"status": "ok", "erstellt": int, "bereits_vorhanden": int, "uebersprungen": [{"abo_id": str, "kunde": str, "grund": str}]}`.
  - `subscription_tasks.process_daily_subscriptions(heute: Optional[date] = None)`: bleibt `@shared_task` und Einstieg des Schedulers (`scheduler_service.py:81`, `:102`) und von Celery Beat (`celery_app.py:70`). Öffnet `SessionLocal()` (Mandant aus der ContextVar, die `_safe_wrap` setzt) und ruft `abo_lauf(db, heute or liefertag_heute())`. Wird aus keiner Anfrage mehr aufgerufen.
  - `POST /api/v1/sales/subscriptions/process-today`: `process_today_subscriptions(db: DBSession)` ruft `abo_lauf(db, liefertag_heute())` und antwortet `{"message": "<deutscher Satz>", "details": <Ergebnis-Dict>}`. Die Oberfläche zeigt `message` unverändert im Toast (`Abonnements.tsx:119-127`), daher keine Frontend-Änderung.

- [ ] **Step 1: Tests anhängen**

```python
class TestP4AboLauf:
    """A5: Der Knopf "Heute verarbeiten" lief im Default-Mandanten statt im
    Mandanten der Anfrage. Läuft er richtig, treffen er und der 05:00-Lauf
    dieselbe DB: je Abo und Liefertag darf es nur eine Bestellung geben."""

    def test_zweiter_lauf_am_selben_tag_legt_nichts_doppelt_an(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[3])

        _p4_lauf(_P4_DO)
        zweiter = _p4_lauf(_P4_DO)

        assert len(_p4_bestellungen(abo["id"])) == 1
        assert zweiter["erstellt"] == 0
        assert zweiter["bereits_vorhanden"] == 1

    def test_stornierte_abo_bestellung_kommt_nicht_wieder(self, client):
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        abo = _p4_abo(client, kunde, product_id=produkt["id"], liefertage=[3])
        _p4_lauf(_P4_DO)
        from app.models.order import Order, OrderStatus
        from sqlalchemy import select
        with TestingSessionLocal() as db:
            order = db.execute(select(Order)).scalars().one()
            order.status = OrderStatus.STORNIERT
            db.commit()

        _p4_lauf(_P4_DO)

        assert [b["status"] for b in _p4_bestellungen(abo["id"])] == ["STORNIERT"]

    def test_knopf_nutzt_den_mandanten_der_anfrage(self, client):
        """Der Knopf muss die Session der Anfrage nehmen und meldet auf Deutsch.

        SessionLocal() fiele ohne Scheduler-Kontext auf DEFAULT_TENANT_SLUG
        zurück (database.py, _active_slug). Der Patch lässt jeden Zugriff
        scheitern, statt in TENANTS_DIR/dev.db zu schreiben. Diesen Test nie
        ohne ihn laufen lassen: backend/data/tenants/dev.db ist eine echte
        lokale Dev-DB.
        """
        from app.models.customer import Subscription, SubscriptionInterval
        kunde = _p4_kunde(client)
        produkt = _p4_produkt(client, "BIO Snackbox | Amaranth", "P4-SNACK", "4.50")
        # Täglich ab gestern: fällig, auch wenn der Berliner Kalendertag dem
        # des Testrechners schon voraus ist.
        gestern = date.today() - timedelta(days=1)
        abo = _p4_abo(client, kunde, product_id=produkt["id"], intervall="TAEGLICH",
                      liefertage=None, gueltig_von=gestern)
        with TestingSessionLocal() as db:
            db.add(Subscription(
                kunde_id=uuid.UUID(kunde["id"]), menge=Decimal("2"), einheit="STUECK",
                intervall=SubscriptionInterval.TAEGLICH, gueltig_von=gestern,
            ))
            db.commit()

        with patch("app.tasks.subscription_tasks.SessionLocal",
                   side_effect=AssertionError("Knopf nutzt SessionLocal (Default-Mandant)")):
            r = client.post("/api/v1/sales/subscriptions/process-today")

        assert r.status_code == 200, r.text
        assert len(_p4_bestellungen(abo["id"])) == 1
        assert r.json()["message"] == (
            "1 Abo-Bestellung angelegt. 1 Abo übersprungen: "
            "LfA Förderbank Bayern (Abo hat weder Produkt noch Sorte)"
        )

    def test_liefertag_ist_der_berliner_kalendertag(self):
        """Der Container läuft in UTC: 22:30 UTC am 07.10. ist in München schon der 08.10."""
        from datetime import datetime, timezone
        from app.services import order_status_service
        from app.tasks.subscription_tasks import liefertag_heute

        class _Uhr(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 7, 22, 30, tzinfo=timezone.utc).astimezone(tz)

        # liefertag_heute ruft order_status_service.heute_berlin (eine Regel)
        with patch.object(order_status_service, "datetime", _Uhr):
            assert liefertag_heute() == date(2026, 10, 8)
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k AboLauf -v`
Erwartet: **4 failed:**
- `test_zweiter_lauf_am_selben_tag_legt_nichts_doppelt_an`: `assert 2 == 1` (doppelt angelegt);
- `test_stornierte_abo_bestellung_kommt_nicht_wieder`: `assert ['STORNIERT', 'ENTWURF'] == ['STORNIERT']`;
- `test_knopf_nutzt_den_mandanten_der_anfrage`: `AssertionError: Knopf nutzt SessionLocal (Default-Mandant)`. Das ist der Produktionsfehler: Der Endpunkt öffnet `SessionLocal()`;
- `test_liefertag_ist_der_berliner_kalendertag`: `ImportError: cannot import name 'liefertag_heute'`.

Der rote Knopf-Test darf nichts außerhalb der Test-DB anfassen: `ls -la backend/data/tenants` vor und nach diesem Lauf vergleichen, keine neue Datei, gleiche Zeitstempel (`backend/data/` ist nicht versioniert, `git status` hilft hier nicht).

- [ ] **Step 3: Imports**

Im Kopf von `backend/app/tasks/subscription_tasks.py` (Stand Task 21) direkt **unter** der Zeile `from app.services.pricing_service import resolve_unit_price` einfügen:

```python
from app.services.order_status_service import heute_berlin
```

Kein Importzyklus: `order_status_service` importiert nur Modelle und `order_fulfillment_service`, und dieser nur Modelle (am Code geprüft, `order_fulfillment_service.py:20-33`); `sales.py` lädt das Modul seit Task 1 ohnehin. `datetime` und `ZoneInfo` braucht `subscription_tasks.py` nicht.

- [ ] **Step 4: Liefertag und Prüfung einfügen**

In `subscription_tasks.py` direkt vor `@shared_task` (hinter `abo_position`):

```python
def liefertag_heute() -> date:
    """Heutiger Kalendertag in München.

    Der Container läuft in UTC. Zwischen 00:00 und 02:00 Uhr Berliner Zeit
    wäre date.today() noch der Vortag, und ein Klick auf "Heute verarbeiten"
    legte die Bestellungen des Vortags an. Dieselbe Rechnung wie das
    Lieferdatum beim Statuswechsel: order_status_service.heute_berlin().
    """
    return heute_berlin()


def _abo_bestellung_vorhanden(db, sub, heute: date) -> bool:
    """Gibt es zu diesem Abo und Liefertag schon eine Bestellung?

    Zählt in jedem Status, auch STORNIERT: Wer die Abo-Bestellung eines Tages
    storniert, will sie nicht beim nächsten Klick auf "Heute verarbeiten"
    zurückhaben. Erkennungsmerkmal ist der Text, den
    _create_order_from_subscription in Order.notes schreibt, dazu Kunde und
    Liefertag. Ohne eigene Spalte ist das nicht fest: Notiz und Liefertag
    sind in der Oberfläche änderbar (EditOrderModal, OrderUpdate), Entwürfe
    lassen sich löschen (DELETE /sales/orders/{id}). Wer eins davon tut,
    bekommt die Abo-Bestellung beim nächsten Lauf desselben Tages zurück.
    """
    return db.execute(
        select(Order.id).where(
            Order.customer_id == sub.kunde_id,
            Order.requested_delivery_date == heute,
            Order.notes.contains(f"Abo {sub.id}"),
        ).limit(1)
    ).first() is not None
```

- [ ] **Step 5: Lauf als `abo_lauf` herausziehen**

`process_daily_subscriptions` (Stand Task 21, von `@shared_task` bis vor `def _create_order_from_subscription`) vollständig ersetzen durch:

```python
def abo_lauf(db, heute: date) -> dict:
    """Legt in der Mandanten-DB von `db` die an `heute` fälligen Abo-Bestellungen an.

    Zwei Aufrufer, jeder mit der Session des richtigen Mandanten:
    process_daily_subscriptions (Scheduler 05:00, SessionLocal unter der
    ContextVar des Mandanten) und der Knopf "Heute verarbeiten"
    (sales.process_today_subscriptions, Session der Anfrage). Committet.
    """
    # Aktive Abos laden
    subs = db.execute(
        select(Subscription).where(Subscription.aktiv == True)
    ).scalars().all()

    erstellt = 0
    bereits_vorhanden = 0
    uebersprungen = []
    for sub in subs:
        if not ist_faellig(sub, heute):
            continue
        # 05:00-Lauf und Knopf "Heute verarbeiten" treffen denselben Tag.
        if _abo_bestellung_vorhanden(db, sub, heute):
            bereits_vorhanden += 1
            continue
        try:
            _create_order_from_subscription(db, sub, heute)
            erstellt += 1
        except AboUebersprungen as grund:
            kunde = sub.kunde.name if sub.kunde else str(sub.kunde_id)
            logger.warning("[abo] Abo %s (%s) übersprungen: %s", sub.id, kunde, grund)
            uebersprungen.append({"abo_id": str(sub.id), "kunde": kunde, "grund": str(grund)})

    db.commit()
    # Dict statt Text: _safe_wrap (scheduler_service.py) liest "status",
    # der Knopf "Heute verarbeiten" die Zahlen.
    return {
        "status": "ok",
        "erstellt": erstellt,
        "bereits_vorhanden": bereits_vorhanden,
        "uebersprungen": uebersprungen,
    }


@shared_task
def process_daily_subscriptions(heute: Optional[date] = None):
    """Täglicher Task (Scheduler 05:00): Entwurfs-Bestellungen aus aktiven Abos.

    SessionLocal() löst über die ContextVar auf, die scheduler_service._safe_wrap
    je Mandant setzt. Ohne sie, etwa aus einer Anfrage heraus, fiele es auf
    DEFAULT_TENANT_SLUG zurück. Darum ruft der Knopf "Heute verarbeiten"
    abo_lauf mit der Session der Anfrage und nicht diesen Task.
    """
    db = SessionLocal()
    try:
        return abo_lauf(db, heute or liefertag_heute())
    finally:
        db.close()
```

Reihenfolge der Datei danach: Kopf, `AboUebersprungen`, `_montag`, `_stichtag`, `ist_faellig`, `_is_subscription_due_today`, `_abo_produkt`, `abo_position`, `liefertag_heute`, `_abo_bestellung_vorhanden`, `abo_lauf`, `process_daily_subscriptions`, `_create_order_from_subscription`. `_is_subscription_due_today` behält `date.today()` (nur `tests/test_features.py` ruft ihn).

- [ ] **Step 6: Endpunkt nimmt die Session der Anfrage und meldet auf Deutsch**

In `backend/app/api/v1/sales.py` die Funktion `process_today_subscriptions` (Z. 582-588)

```python
@router.post("/subscriptions/process-today", status_code=status.HTTP_200_OK)
async def process_today_subscriptions():
    """Löst manuell den Subscription-Run für heute aus."""
    from app.tasks.subscription_tasks import process_daily_subscriptions
    # Synchron ausführen um Ergebnis zu sehen
    result = process_daily_subscriptions()
    return {"message": "Subscription run completed", "details": result}
```

vollständig ersetzen durch:

```python
@router.post("/subscriptions/process-today", status_code=status.HTTP_200_OK)
async def process_today_subscriptions(db: DBSession):
    """Löst manuell den Subscription-Run für heute aus."""
    # Session der Anfrage = Mandant der Subdomain. Der Scheduler-Task öffnet
    # SessionLocal(), und das fällt ohne Scheduler-Kontext auf
    # DEFAULT_TENANT_SLUG zurück: Bis Oktober 2026 lief der Knopf im
    # Default-Mandanten statt im Mandanten der Anfrage.
    from app.tasks.subscription_tasks import abo_lauf, liefertag_heute
    result = abo_lauf(db, liefertag_heute())
    # Die Oberfläche zeigt `message` im Toast (Abonnements.tsx, processMutation).
    erstellt = result["erstellt"]
    teile = [f"{erstellt} Abo-Bestellung{'en' if erstellt != 1 else ''} angelegt."]
    if result["bereits_vorhanden"]:
        teile.append(f"{result['bereits_vorhanden']} schon vorhanden.")
    if result["uebersprungen"]:
        anzahl = len(result["uebersprungen"])
        gruende = ", ".join(f"{u['kunde']} ({u['grund']})" for u in result["uebersprungen"])
        teile.append(f"{anzahl} Abo{'s' if anzahl != 1 else ''} übersprungen: {gruende}")
    return {"message": " ".join(teile), "details": result}
```

`DBSession` ist in `sales.py:13` schon importiert; es kommt **kein** Modul-Import dazu. Sonst nichts in `sales.py` anfassen (Paket 1 ändert dort andere Stellen).

- [ ] **Step 7: Grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestP4 -q`, dann `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py -q`
Erwartet: **21 passed** (alle P4-Tests); `test_gernot_260817.py` 20 passed.

Dann aus dem Repo-Wurzelverzeichnis: `git grep -n "process_daily_subscriptions" -- backend/app` → Treffer nur in `backend/app/celery_app.py:70`, `backend/app/services/scheduler_service.py:81` und `:102` sowie in `backend/app/tasks/subscription_tasks.py` (Docstring von `abo_lauf` und die Definition); **kein** Treffer in `backend/app/api/`.

- [ ] **Step 8: Vollauf gegen die Baseline**

Prozedur V als Zwischenlauf (`REDIS_URL=memory://` zulässig, siehe Global Constraints). Erwartet: dieselben Fehlernamen wie die Baseline, nur Namen vergleichen. Besonders `test_gernot_260821.py` (Abo bearbeiten), `test_features.py` (bleibt mit derselben Altlast rot), `test_dunning.py` prüfen.

- [ ] **Step 9: Commit**

```bash
git add backend/app/tasks/subscription_tasks.py backend/app/api/v1/sales.py backend/tests/test_gernot_261008_paket2.py
git commit -m "fix(abo): 'Heute verarbeiten' lief im Default-Mandanten; jetzt Mandant der Anfrage, Berliner Kalendertag, je Abo und Tag eine Bestellung"
```

---


## Abschnitt P5: Bestell-Import härten (A6-Rest) — Tasks P5.1–P5.6 (Manager-Nachtrag 08.10.)

> **Für den ausführenden Worker:** Task für Task abarbeiten, Schritte als Checkboxen. Kein Task wird übersprungen oder zusammengefasst. Inhaltliche Widersprüche zwischen Plan und Code: stoppen und mit exakter Fehlerausgabe melden. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht (z. B. eine um wenige Zeilen verschobene Fundstelle): selbst auflösen und in der Abschlussmeldung vermerken. Jeder „Suchen"-Block muss in der Datei **genau einmal** vorkommen. Findet er sich nicht oder mehrfach: stoppen und melden, nicht frei nachbauen.

**Ziel:** Der Bestell-Import (`POST /api/v1/imports/order_history`) legt keine unvollständigen Bestellungen mehr an, meldet ungültige Status-Werte, unplausible Bestelldaten und fehlerhafte Positionen als Fehler statt sie still umzudeuten, und legt Bestellungen so an wie das Bestellformular: mit Adress-Schnappschuss, Packtag bei Lieferung heute, `created_by` und einem Audit-Eintrag. Die Halle sieht den Import-Knopf nicht mehr, den sie ohnehin nicht benutzen darf.

**Umfang:** Genau „Stufe A" aus `docs/superpowers/specs/2026-10-08-nachtrag/T1-import.md` (Abschnitt 3.3), soweit am Code belegt und klein. Was T1 dort zusätzlich nennt und hier nicht umgesetzt wird, steht unter „Nicht in P5". **Nicht in P5:** Doppel-Lieferschein-Sperre (Paket 1, Task 23), Abrechnung der 47 rückdatierten Bestellungen (wartet auf Gernot), Stufe B (Vorschau, Importläufe, Rückgängig), Stufe C (`bulk-status`, macht P1).

**Architektur:** `_import_order_history` wird zweiphasig. Phase 1 prüft jede neue Bestellung der Datei mit `_pruefe_bestellung` und sammelt **alle** Fehler, auch die Lesefehler aus `_parse_rows`. Gibt es einen einzigen Fehler, bricht der Lauf mit 400 ab und legt nichts an. Phase 2 legt die geprüften Bestellungen mit `_lege_bestellung_an` an. Die Adressregel aus `create_order` wandert in ein neues Modul `app/services/bestell_adressen.py`, `sales.py` bleibt unberührt. Keine Schemaänderung, kein `_auto_migrate`, keine neue Spalte.

**Abhängigkeiten:**
- **Keine Code-Abhängigkeit zu P1–P4 oder Paket 1.** P5 läuft auf `main` @ `efcea00` und vor oder nach den anderen Abschnitten. Alle Fundstellen unten gelten für `efcea00`. Nach früheren P5-Tasks oder anderen Abschnitten verschieben sich Zeilen, maßgeblich ist der zitierte Inhalt.
- **Ausführungsbasis ist der Branch `feat/paket2-tagesplan-status`** (Worktree `/Users/nikolajunser-richter/minga-paket2`), nicht `efcea00`. Er trägt P1–P4 bereits (Stand der Prüfung: `a28104c`, am 08.10. weiter bei `db76f06`, P4 committet noch). P5 startet erst, wenn P4 vollständig committet ist (Vorbereitung, Schritt „Ausgangszustand prüfen"). Auf dem Branch sind `imports.py`, `ExcelImport.tsx`, `test_import_bestellungen_zukunft.py` und `test_gernot_260821.py` unverändert gegenüber `efcea00`, ihre Zeilenangaben gelten. **Verschoben ist nur `Orders.tsx`:** `ExcelImport`-Import Z. 14 (statt 13), `const queryClient = useQueryClient();` Z. 51 (statt 41), `<ExcelImport …/>`-Block Z. 229–234 (statt 198–203). Die Inhaltsanker treffen dort weiter genau einmal.
- **P2, Entscheidung M2** („Import mit `IN_PRODUKTION`", `/tmp/paket2/P2.md`) wird hier gelöst: Task P5.2 lehnt `IN_PRODUKTION` für eine ausstehende Lieferung (Lieferdatum ab heute) ab. Die lesende Prüfung „Vor dem Deploy" in P2 bleibt für den Altbestand nötig.
- **Bezeichnung „Gepackt"** für `IN_PRODUKTION` (A4-Entscheidung, P1.6/P2): P5 nimmt sie im Import als Eingabe an und nennt sie in der Rückmeldung. P5 braucht dafür keinen P1-Code.
- **Testdatei:** P5 schreibt nur in `backend/tests/test_import_bestellungen_zukunft.py` (aus `efcea00`), P1–P4 schreiben in `backend/tests/test_gernot_261008_paket2.py`. Alle P5-Helfer tragen das Präfix `_p5_`, alle P5-Klassen heißen `TestP5…`.

**Ueberschneidung mit Paket 1 und P1-P4:**

| Datei | P5 ändert | Andere ändern | Merge |
|---|---|---|---|
| `backend/app/api/v1/imports.py` | Z. 25 (`from app.api.deps import …`), Z. 122 (Status-Spalte in `COLUMNS["order_history"]`), Z. 256–261 (`HINWEISE["order_history"]`), Z. 490–665 (`_import_order_history`, neu geschrieben, neue Helfer direkt darüber), Z. 774 (Kommentar in `IMPORTERS`), Z. 780–786 (`import_entity`) | **Paket 1, S1/Task 4 Step 6:** fügt nach Z. 33 `from app.services.steuersatz import pfand_vorgaben` ein und schreibt die Schleife in `_import_products` (Z. 424–443) neu | Getrennte Hunks. **P5 fasst `_import_products` und Z. 30–36 nicht an**, `OrderAuditLog` wird deshalb im Funktionsrumpf importiert statt in Z. 33. Nachgemessen: `git merge-file` aus P5-Endstand, `efcea00` und dem Paket-1-Stand von `imports.py` ergibt **0 Konflikte**. Vom Prüfer gegen den echten Paket-1-Worktree (`/Users/nikolajunser-richter/minga-paket1`, Commit `16d6ae7`, einziger Paket-1-Commit an `imports.py`) wiederholt: 0 Konflikte, Ergebnis bytegleich mit P5 nachgespielt auf dem Paket-1-Stand. P5 auf Paket-1-HEAD inkl. Task 23 (409 beim zweiten Lieferschein): 34 passed |
| `backend/app/api/v1/imports.py`, Positionen | Steuersatz der Importposition bleibt `product.tax_rate or TaxRate.REDUZIERT` (unverändert aus `efcea00`) | Paket 1 S1.1 führt `steuersatz.steuersatz_der_position` ein, ändert die Importzeile aber nicht | Folgepunkt nach dem Paket-1-Merge, siehe „Nicht in P5" |
| `backend/app/api/v1/sales.py` | **nicht geändert** | Paket 1 (`create_order` ~968–976, `add_order_line`, `update_order_line`), P1 (Importblock, `update_order_status`, `bulk_update_status`), P4 (`process_today_subscriptions`) | Deshalb liegt die Adressregel in einem neuen Modul. `create_order` behält seinen eigenen Block. Der Test `test_adressen_wie_bei_create_order` hält beide Wege gleich |
| `frontend/src/pages/Orders.tsx` | eine Importzeile nach Z. 13, ein Block nach Z. 41 (`const queryClient = useQueryClient();`), Z. 198–203 (`<ExcelImport …/>` in eine Bedingung gefasst). Auf dem Branch (P1 schon drin): nach Z. 14, nach Z. 51, Z. 229–234 | **P1.6/P1.8** (Zeilen für `efcea00`, auf dem Branch bereits umgesetzt): Z. 5, 15–37, 47, 63–64, 78–155, 279–300, 326–328, 387–394. P1 lässt den `ExcelImport`-Block ausdrücklich unverändert (`P1.md`, P1.8: „Den `ExcelImport`-Block im Seitenkopf … nicht anfassen") | Getrennte Hunks, zwischen den Einfügestellen liegen jeweils unveränderte Zeilen. Die Zeile `onImported={() => queryClient.invalidateQueries({ queryKey: ['orders'] })}` bleibt wörtlich erhalten (nur eingerückt). P1.8, Schritt „Prüfen", erwartet per grep genau diesen einen Treffer |
| `frontend/src/components/common/ExcelImport.tsx` | Toast-Darstellung in `handleUpload` | niemand (grep über `/tmp/paket1/*.md`, `/tmp/paket2/P1–P4.md`) | — |
| `backend/app/services/bestell_adressen.py` | **neu** | — | — |
| `backend/app/models/order.py` | **nicht geändert** (`resolve_packing_date` nutzt `date.today()`; P5 rechnet den Packtag im Import selbst mit dem Berliner Datum) | P4 nutzt `resolve_packing_date` unverändert | — |
| `backend/app/services/pdf_service.py`, `documents.py` | nicht geändert | Paket 1 (Lieferschein-Sperre Task 23, PDF je Satz) | P5-Test `test_lieferschein_zeigt_die_lieferadresse` legt genau **einen** Lieferschein an, verträgt also die Sperre |

**Aufwand:** S–M. Fünf Backend-Tasks, ein Frontend-Task, keine Migration. Worker ca. 3–4 h. Ein Vollauf dauert mit `REDIS_URL=memory://` etwa 20 s.

**Vorab nachgemessen am 08.10.2026** (Kopie von `main` @ `efcea00` per `git archive` unter `/tmp/paket2/p5work`, Repo unverändert):
- Jeder Task wurde in genau dieser Reihenfolge mit den Test- und Code-Blöcken dieses Abschnitts durchgespielt. Rot- und Grün-Ausgaben unten sind gemessen.
- Vollauf `main` @ `efcea00`: **15 failed / 507 passed / 2 skipped / 1 error**. Nach P5.1 / P5.2 / P5.3 / P5.4 / P5.5: 510 / 520 / 526 / 531 / **535 passed**, jeweils 15 failed / 2 skipped / 1 error. Die 15 Fehlernamen und der eine Error sind exakt die der Baseline (Liste in `docs/superpowers/plans/2026-10-02-saatgut-lagerbuecher.md`, „Global Constraints"). Die 28 zusätzlichen Erfolge sind die neuen P5-Tests.
- Zusätzlich wurde dieser Abschnitt selbst maschinell nachgespielt: Alle Test-, Such- und Ersetzungsblöcke aus genau diesem Text auf einen frischen `efcea00`-Export angewendet. Jeder „Suchen"-Block traf genau einmal, Rot/Grün wie unten, die fünf Enddateien sind bytegleich mit dem Probestand (Ausnahme seit der Prüfung: eine Docstring-Zeile in `_benutzer_id`, P5.5 Step 4, nur Kommentartext).
- Frontend nach P5.6: `./node_modules/.bin/tsc --noEmit -p .` Exit 0, `vite build` ohne Fehler.
- **Unabhängige Prüfung (08.10.2026):** Alle Blöcke wörtlich aus diesem Text auf einen frischen `efcea00`-Export nachgespielt (`/tmp/p5review/w1`): jeder Suchblock genau einmal, Rot 3/8/3/3/3 mit den zitierten Meldungen, Grün 74/84/90/95/154, Testdatei am Ende 34 passed, Vollauf 507 → 535 passed mit identischen Fehlernamen, `tsc` Exit 0, `vite build` OK, P1.8-grep genau ein Treffer, `imports.py`-Hunks bei 25, 122, 260, 490ff, 773, 780, 785.
- **Auf der Ausführungsbasis** `feat/paket2-tagesplan-status` @ `a28104c` (P1–P3, P4 teilweise) wiederholt: alle Suchblöcke eindeutig, Testdatei 34 passed, P5.5 Step 8 154 passed, Vollauf **580 → 608 passed** mit denselben 15 Fehlernamen + 1 Error, `tsc` Exit 0. Die Vollauf-Anzahlen oben (507 …535) gelten für `efcea00`; auf dem Branch zählen nur die Namen.

**Verifizierter Ausgangsbefund (Code `efcea00`, Lauf gegen die Kopie):**

| Fall | Heute |
|---|---|
| Bestellung mit zwei Zeilen, zweite ohne Preis | HTTP 200, `{"created":2,"updated":0,"errors":["Zeile 5: 'einzelpreis' fehlt"]}`, Bestellung mit **einer** Position. Erneuter Upload der korrigierten Datei überspringt sie (`imports.py:538-544`, Idempotenz über `customer_reference`) |
| Lesefehler in einer Bestellung, unbekannte SKU in einer anderen | 400 nur mit der SKU-Meldung, der Lesefehler fehlt in der Antwort |
| Status „Bestätigt", „in produktion", „offen" | `_coerce` macht daraus `None` (`imports.py:180-183`), dann greift still die Datumsregel. Der `except ValueError`-Zweig (`:564-566`) ist toter Code |
| Status `IN_PRODUKTION`, Lieferdatum in drei Tagen | 200. Nach P2 heißt das „gepackt" und fällt aus Sortenbedarf und „Verpacken" (P2, M2) |
| Bestelldatum nach dem Lieferdatum bzw. in der Zukunft | 200, die Bestellnummer trägt das Bestelldatum (`_generate_historic_order_number`, `:464-487`). Produktionsfall BE-20261011-0001 |
| Deaktivierter Kunde | 200. `create_order` lehnt ab (`sales.py:830-831`) |
| Menge 0, Preis −1,00 | 200. Das Bestellschema verlangt `quantity > 0`, `unit_price >= 0` (`schemas/order.py:32`, `:34`) |
| Einheit leer | `"g"` (`:651`). Das Formular nimmt `STK` (`CreateOrderModal.tsx:80-82`, „es wird aktuell nichts abgewogen verkauft") |
| Variables Bundle ohne Sortenauswahl, offene Bestellung | 200. `create_order` verlangt Auswahl und Slot-Grenzen (`sales.py:990-1016`) |
| Kunde mit Standardadresse | `billing_address`/`delivery_address` bleiben `None`. `create_order` übernimmt sie (`sales.py:875-901`). Ohne Schnappschuss fehlt die Lieferadresse auf Lieferschein und AB (`pdf_service.py:489-497`) |
| Lieferdatum heute, Status leer | `BESTAETIGT`, `packing_date = None`, Tagesplan heute: `verpacken = []`, nur `ausliefern` (T1, Repro 2) |
| `created_by`, Audit | `None`, kein Eintrag in `order_audit_logs` |
| Halle (`production_staff`) | Sieht den Knopf (`Orders.tsx:198-203`, `Layout.tsx:187-189`), Upload → 403 (`main.py:788-792`, `_deps_vertrieb`) |

### Entscheidungen

1. **Fehlerhafte Zeile: der ganze Lauf wird abgelehnt (alles oder nichts), nicht nur die betroffene Bestellgruppe.** Begründung:
   - Ein Lesefehler lässt sich nicht immer einer Bestellung zuordnen. `_parse_rows` (`imports.py:324-365`) bricht bei der ersten fehlenden Pflichtspalte ab und verwirft die Zeile samt ihrer `bestell_nr_extern`; fehlt gerade diese Spalte, gibt es keine Gruppe. Eine Zuordnung bräuchte Änderungen am gemeinsamen Parser, den auch Kunden-, Produkt- und Saatgut-Import nutzen (Paket 1 arbeitet dort in `_import_products`).
   - Gleiche Regel wie heute schon: Unbekannter Kunde, unbekannte SKU und GELIEFERT mit Zukunftsdatum lehnen bereits den ganzen Lauf ab. Der Test `test_geliefert_mit_zukunftsdatum_lehnt_ganzen_lauf_ab` (`efcea00`) schreibt fest, dass auch die fehlerfreie Nachbarbestellung nicht entsteht. Gruppenweise Ablehnung hieße zwei verschiedene Regeln in einem Import.
   - Der Re-Upload funktioniert ohne Aufräumen: Es ist nichts angelegt, die Idempotenz über `customer_reference` greift nicht.
   - Ein Teilerfolg ist in der Oberfläche leicht zu übersehen (Toast „x angelegt", höchstens drei Fehlerzeilen, 5 s sichtbar). Ein 400 mit „keine Bestellung angelegt" ist eindeutig.
   - Kosten: Eine einzige falsche Zeile blockiert die ganze Datei. Deshalb sammelt der Import **alle** Fehler der Datei und nennt sie in einer Antwort (bis zu 10 Zeilen, dann „… und N weitere").
   - Bereits importierte Bestellungen (gleiche `bestell_nr_extern`) werden wie bisher übersprungen und **nicht** geprüft, Lesefehler blockieren dagegen immer, weil ihre Gruppe unbekannt sein kann. Folge für den Altbestand: Ein Lesefehler in einer Zeile einer schon importierten Bestellung blockiert den Upload, nach der Korrektur bleibt diese Bestellung trotzdem unvollständig (siehe „Nach dem Deploy", Gernot informieren).
2. **Einheit leer → `STK`, kein Fehler.** Das Produkt trägt keine verlässliche Verkaufseinheit: `Product.base_unit_id` ist die Lager-/Basiseinheit. Der Excel-Produktimport setzt sie nur im Anlagezweig auf `G` (`imports.py:440`, `default_unit` aus `:425-427`); vorhandene und im Formular angelegte Produkte behalten ihre Basiseinheit. Ein Default daraus hinge also davon ab, wie das Produkt entstanden ist, und wiederholt für jeden per Excel angelegten Artikel genau den heutigen „g"-Fehler. `Product.sales_units` (`models/product.py:209-210`) hat keinen Schreiber und keinen Leser (grep über `backend/app` und `frontend/src`). Das Formular setzt für jedes Produkt `STK`. Ein Fehler statt Default würde Dateien blockieren, in denen die Spalte leer ist (T1, Frage 6). Die Vorlage nennt die Regel.
3. **Audit-Aktion `IMPORT`.** Vorhandene Aktionen: `UPDATE`, `CONFIRM`, `STATUS_CHANGE`, `ADD_LINE`, `UPDATE_LINE`, `DELETE_LINE`, `BULK_STATUS_CHANGE` (`sales.py:1104-1571`). `CREATE` steht nur im Spaltenkommentar (`models/order.py:369`) und wird nirgends geschrieben, auch `create_order` schreibt keinen Eintrag. `IMPORT` hält Importe von Handanlagen unterscheidbar, und T1 Stufe B baut darauf („Rollback blockiert bei Audit-Eintrag ≠ IMPORT"). `action` ist `String(50)` ohne Enum, das Frontend liest das Audit-Log nicht (grep), also keine Migration und keine Anzeigeänderung.
4. **`IN_PRODUKTION` für ausstehende Lieferungen wird abgelehnt** (P2, M2), nicht auf `BESTAETIGT` umgebogen. Eine stille Umdeutung wäre genau das Verhalten, das P5 abschafft.
5. **Bestelldatum in der Zukunft ist ein Fehler** (T1 Stufe A: „Bestelldatum ≤ heute und ≤ Lieferdatum"). Bestelldatum ist der Tag der Kundenbestellung; ein künftiges Datum steht sonst in der Bestellnummer und als „Datum" auf AB und Lieferschein (`pdf_service.py:480`). Frage an Gernot, ob der Fall Fruchthof Nagel gewollt war, siehe Offene Punkte.
6. **Antwort rückwärtskompatibel erweitert:** `{created, updated, errors, status_counts, hinweis}`. `status_counts` zählt die angelegten Bestellungen je Status, `hinweis` ist ein fertiger deutscher Satz für den Toast („Angelegt: 46 Geliefert, 2 Bestätigt. Geliefert heißt: ohne Lieferschein und ohne Lagerabzug, der Sammellauf rechnet diese Bestellungen nicht ab."). Warnungen im Sinn von T1 (Kreditlimit, GELIEFERT heute, offen in der Vergangenheit, unbekannte Einheit) kommen nicht, siehe „Nicht in P5".

### Rahmen (gilt für alle Tasks)

- Python ausschließlich über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`.
- Einzeltest: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/<datei> -v -p no:cacheprovider`
- Vollauf (ca. 20 s): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -p no:cacheprovider`
- Baseline: 15 bekannte Fehlschläge + 1 Error. Nur die Namen vergleichen, nie die Anzahl. Liste: `test_api.py::TestHealth::test_root_endpoint`, `test_refinements.py::test_main_app_imports`, `test_auth_manual.py::test_auth_failure`, `test_auth_manual.py::test_auth_success`, `test_features.py::TestFeatures::test_subscription_processing`, `test_production_readiness.py::test_dunning_level1/2/3`, `…::test_quality_auto_approved`, `…::test_quality_rejected_high_loss`, `…::test_quality_rejected_low_note`, `test_services.py::TestInvoiceService` ×4 (`test_invoice_totals_update`, `test_record_full_payment`, `test_record_partial_payment`, `test_finalize_empty_invoice_fails`), ERROR `test_production_automation.py::test_approve_suggestion_creates_grow_batch`. Ein weiterer Name: stoppen, nicht committen.
- Ohne `REDIS_URL=memory://` hängt jeder `POST /sales/orders` im Test in Celery-Verbindungsversuchen (Task P5.4 nutzt ihn).
- Frontend: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut) und `./node_modules/.bin/vite build`. Kein Frontend-Testframework im Repo.
- Kein Netzwerk: kein `npm install`, kein `git pull`. Kein Deploy. Keine Schemaänderung.
- UI- und Fehlertexte auf Deutsch.

### Review-Fokus

1. **Alles oder nichts:** Bei einem einzigen Fehler entsteht keine Bestellung, auch keine fehlerfreie aus derselben Datei; der Re-Upload der korrigierten Datei legt alle Positionen an (P5.1).
2. **Idempotenz unverändert:** Vorhandene `customer_reference` werden übersprungen und nicht geprüft (P5.1, bestehender Ablauf).
3. **Leer bleibt leer:** Eine leere Status-Zelle folgt weiter der Datumsregel aus `efcea00`, nur ungültige Werte werden Fehler (P5.2; die sechs `efcea00`-Tests bleiben grün).
4. **Gleiche Adresse wie im Formular:** Import- und Formularweg ergeben denselben Schnappschuss (P5.4).
5. **Basic-Auth-Login bricht den Import nicht** (`id = "basic-auth:<name>"`, P5.5).
6. **Kein Eingriff in `_import_products`, Z. 30–36 von `imports.py` und `sales.py`** (Abnahme Punkt 4).

### Vorbereitung (vor Task P5.1)

- [ ] **Basis-Commit festhalten**

Run: `git rev-parse HEAD`
Den Hash im Bericht als `<Basis>` notieren und in der Abnahme wörtlich einsetzen (jeder Befehl läuft in einer eigenen Shell, eine Variable überlebt nicht).

- [ ] **Ausgangszustand prüfen**

Run: `git branch --show-current`
Erwartet: `feat/paket2-tagesplan-status` (Ausführungsbasis, siehe „Abhängigkeiten"). Ein anderer Name: stoppen und melden.

Run: `git status --porcelain --untracked-files=no`
Erwartet: keine Ausgabe (P1–P4 vollständig committet; ungetrackte Dateien zählen nicht). Sonst stoppen und melden, nichts zurücksetzen, nichts committen.

Run: `git status --porcelain -- backend/app/api/v1/imports.py backend/app/services/bestell_adressen.py backend/tests/test_import_bestellungen_zukunft.py frontend/src/components/common/ExcelImport.tsx frontend/src/pages/Orders.tsx`
Erwartet: keine Ausgabe. Sonst stoppen und melden, nichts zurücksetzen.

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_import_bestellungen_zukunft.py -v -p no:cacheprovider`
Erwartet: 6 passed. Wenn `_import_order_history` nicht mehr mit `def _import_order_history(db, rows: list[dict]) -> tuple[int, int]:` beginnt, hat jemand die Funktion schon geändert: stoppen und melden.

---

### Task P5.1: Alles oder nichts — eine fehlerhafte Zeile verhindert den ganzen Lauf

**Files:**
- Modify: `backend/app/api/v1/imports.py:490-665` (`_import_order_history` neu, Helfer direkt darüber), `:774` (`IMPORTERS`, Kommentar), `:785-786` (`import_entity`)
- Test: `backend/tests/test_import_bestellungen_zukunft.py` (anhängen)

**Interfaces:**
- Produces (alle in `imports.py`, direkt unter `_generate_historic_order_number`):
  - `_import_abbruch(fehler: list[str]) -> HTTPException` — 400, `detail` = „Import abgebrochen, keine Bestellung angelegt. N Fehler:" + höchstens 10 Fehlerzeilen, getrennt durch `\n`.
  - `_bundle_auswahl(ext_nr, roh, get_product) -> tuple[Optional[list], list[str]]`
  - `_pruefe_bestellung(ext_nr, zeilen, kunde, get_product, heute) -> tuple[Optional[dict], list[str]]`. Der Plan hat die Schlüssel `ext_nr`, `kunde`, `status`, `bestelldatum`, `lieferdatum`, `positionen` (Liste aus `{"produkt", "zeile", "auswahl"}`). P5.2 und P5.3 ergänzen nur Prüfungen.
  - `_lege_bestellung_an(db, plan, used_numbers) -> Order` (ohne Commit). P5.4 und P5.5 erweitern die Signatur.
  - `_import_order_history(db, rows, *, parse_errors=()) -> dict` mit `created`, `updated` (= übersprungen), `errors` (immer `[]`, Fehler kommen als 400). Wird **nicht** mehr über `IMPORTERS` aufgerufen; der Eintrag bleibt nur für die 404-Prüfung.
  - Test-Helfer `_p5_zeile`, `_p5_referenzen`.

- [ ] **Step 1: Failing Tests anhängen**

Ans Ende von `backend/tests/test_import_bestellungen_zukunft.py` anhängen:

```python
# ===========================================================================
# P5 — Bestell-Import härten (A6-Rest, Gernot 08.10.2026). Helfer: _p5_.
# ===========================================================================


def _p5_zeile(externe_nummer, kunde, produkt, bestelldatum, lieferdatum, *,
              menge=2, einheit="STK", preis="3.90", status=None, bundle=None):
    """Eine Importzeile mit frei wählbaren Spalten (Reihenfolge wie COLUMNS)."""
    return [externe_nummer, kunde["name"], bestelldatum, lieferdatum, produkt["sku"],
            menge, einheit, preis, status, bundle]


def _p5_referenzen(client):
    response = client.get("/api/v1/sales/orders")
    assert response.status_code == 200, response.text
    return {item["customer_reference"] for item in response.json()["items"]}


class TestP5AllesOderNichts:
    """Lücke 10 aus T1: Eine Zeile mit Lesefehler fiel still heraus, die
    Bestellung entstand ohne sie, und ein erneuter Upload übersprang sie."""

    def _datei(self, kunde, produkt, preis_zweite_position):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        return [
            _p5_zeile("P5-NACHBAR", kunde, produkt, heute, lieferdatum),
            _p5_zeile("P5-ZWEI", kunde, produkt, heute, lieferdatum),
            _p5_zeile("P5-ZWEI", kunde, produkt, heute, lieferdatum, preis=preis_zweite_position),
        ]

    def test_zeile_ohne_preis_legt_keine_bestellung_an(self, client):
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, self._datei(kunde, produkt, None))

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "keine Bestellung angelegt" in detail
        # Datenzeilen beginnen in Zeile 3 (Kopf + Typzeile davor)
        assert "Zeile 5: 'einzelpreis' fehlt" in detail
        referenzen = _p5_referenzen(client)
        assert "P5-ZWEI" not in referenzen
        assert "P5-NACHBAR" not in referenzen, "alles oder nichts: auch die fehlerfreie Bestellung nicht"

    def test_korrigierte_datei_bringt_beide_positionen(self, client):
        kunde = _kunde(client)
        produkt = _produkt()
        assert _import_bestellungen(client, self._datei(kunde, produkt, None)).status_code == 400

        response = _import_bestellungen(client, self._datei(kunde, produkt, "4.50"))

        assert response.status_code == 200, response.text
        assert response.json()["created"] == 2
        assert len(_bestellung(client, "P5-ZWEI")["lines"]) == 2

    def test_alle_fehler_in_einer_antwort(self, client):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-OHNE-MENGE", kunde, produkt, heute, lieferdatum, menge=None),
            _p5_zeile("P5-FALSCHE-SKU", kunde, {"sku": "GIBT-ES-NICHT"}, heute, lieferdatum),
            _p5_zeile("P5-FREMDER-KUNDE", {"name": "Unbekannte GmbH"}, produkt, heute, lieferdatum),
        ])

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "Zeile 3: 'menge' fehlt" in detail
        assert "GIBT-ES-NICHT" in detail
        assert "Unbekannte GmbH" in detail
        assert _p5_referenzen(client) == set()
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_import_bestellungen_zukunft.py -v -p no:cacheprovider`
Erwartet: **3 failed, 6 passed.**
- `test_zeile_ohne_preis_legt_keine_bestellung_an`: `AssertionError: {"created":2,"updated":0,"errors":["Zeile 5: 'einzelpreis' fehlt"]}` / `assert 200 == 400`
- `test_korrigierte_datei_bringt_beide_positionen`: `assert 200 == 400` beim ersten Upload
- `test_alle_fehler_in_einer_antwort`: `assert "Zeile 3: 'menge' fehlt" in "Bestellung 'P5-FALSCHE-SKU': SKU 'GIBT-ES-NICHT' nicht gefunden"`

- [ ] **Step 3: `_import_order_history` zweiphasig neu schreiben**

In `backend/app/api/v1/imports.py` alles ab der Zeile `def _import_order_history(db, rows: list[dict]) -> tuple[int, int]:` (Z. 490) **bis ausschließlich** `def _import_grow_batches(db, rows: list[dict]) -> tuple[int, int]:` (Z. 668) ersetzen durch den folgenden Block. `_generate_historic_order_number` darüber bleibt unverändert. Der Block endet mit zwei Leerzeilen vor `def _import_grow_batches`.

```python
# ---- Bestell-Import (order_history) ---------------------------------------
#
# Alles oder nichts (A6-Rest, 08.10.2026): Zuerst werden alle neuen
# Bestellungen der Datei geprüft, angelegt wird erst, wenn keine einzige Zeile
# einen Fehler hat. Bis dahin fiel eine Zeile mit Lesefehler still heraus, die
# Bestellung entstand ohne sie, und ein erneuter Upload übersprang sie wegen
# customer_reference für immer.

_MAX_FEHLER_IM_TEXT = 10


def _import_abbruch(fehler: list[str]) -> HTTPException:
    """400 mit allen Fehlern der Datei — Gernot korrigiert sie in einem Rutsch."""
    zeilen = fehler[:_MAX_FEHLER_IM_TEXT]
    if len(fehler) > _MAX_FEHLER_IM_TEXT:
        zeilen.append(f"… und {len(fehler) - _MAX_FEHLER_IM_TEXT} weitere")
    return HTTPException(
        status_code=400,
        detail=(
            f"Import abgebrochen, keine Bestellung angelegt. {len(fehler)} Fehler:\n"
            + "\n".join(zeilen)
        ),
    )


def _bundle_auswahl(ext_nr: str, roh: Any, get_product) -> tuple[Optional[list], list[str]]:
    """Spalte bundle_selections (JSON) → [{product_id, quantity}], dazu Fehler."""
    import json

    if not roh:
        return None, []
    try:
        parsed = json.loads(roh) if isinstance(roh, str) else roh
    except json.JSONDecodeError as e:
        return None, [f"Bestellung '{ext_nr}': bundle_selections ist kein gültiges JSON: {e}"]
    if not isinstance(parsed, list):
        return None, [f"Bestellung '{ext_nr}': bundle_selections muss eine Liste sein"]
    auswahl: list[dict] = []
    fehler: list[str] = []
    for sel in parsed:
        if not isinstance(sel, dict):
            fehler.append(f"Bestellung '{ext_nr}': bundle_selections-Eintrag {sel!r} ist kein Objekt")
            continue
        sku = sel.get("sku") or sel.get("product_sku")
        if not sku:
            continue
        sorte = get_product(sku)
        if not sorte:
            fehler.append(f"Bestellung '{ext_nr}': Bundle-Sorte '{sku}' nicht in Produkten gefunden")
            continue
        auswahl.append({"product_id": str(sorte.id), "quantity": int(sel.get("quantity", 1) or 1)})
    return (auswahl or None), fehler


def _pruefe_bestellung(
    ext_nr: str, zeilen: list[dict], kunde: Optional[Customer], get_product, heute: date
) -> tuple[Optional[dict], list[str]]:
    """Prüft eine Bestellung der Datei, ohne etwas anzulegen.

    Liefert (Plan, Fehler). Den Plan legt _lege_bestellung_an an; bei Fehlern
    ist er None.
    """
    fehler: list[str] = []
    head = zeilen[0]
    if not kunde:
        fehler.append(
            f"Bestellung '{ext_nr}': Kunde '{head['kunde']}' nicht gefunden — bitte zuerst Stammdaten importieren"
        )

    lieferdatum = head["lieferdatum"]
    status_str = head.get("status")
    if not status_str:
        status = OrderStatus.GELIEFERT if lieferdatum < heute else OrderStatus.BESTAETIGT
    else:
        try:
            status = OrderStatus(status_str)
        except ValueError:
            status = OrderStatus.GELIEFERT

    if status in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT) and lieferdatum > heute:
        fehler.append(
            f"Bestellung '{ext_nr}': Status {status.value}, aber Lieferdatum "
            f"{lieferdatum.strftime('%d.%m.%Y')} liegt in der Zukunft — "
            "Status-Spalte leer lassen oder BESTAETIGT eintragen"
        )

    positionen: list[dict] = []
    for zeile in zeilen:
        product = get_product(zeile["produkt_sku"])
        if not product:
            fehler.append(f"Bestellung '{ext_nr}': SKU '{zeile['produkt_sku']}' nicht gefunden")
            continue
        auswahl, auswahl_fehler = _bundle_auswahl(ext_nr, zeile.get("bundle_selections"), get_product)
        fehler.extend(auswahl_fehler)
        positionen.append({"produkt": product, "zeile": zeile, "auswahl": auswahl})

    if fehler:
        return None, fehler
    return {
        "ext_nr": ext_nr,
        "kunde": kunde,
        "status": status,
        "bestelldatum": head["bestelldatum"],
        "lieferdatum": lieferdatum,
        "positionen": positionen,
    }, []


def _lege_bestellung_an(db, plan: dict, used_numbers: set[str]) -> Order:
    """Legt eine geprüfte Bestellung samt Positionen an (ohne Commit)."""
    status = plan["status"]
    lieferdatum = plan["lieferdatum"]
    order = Order(
        order_number=_generate_historic_order_number(db, plan["bestelldatum"], used_numbers),
        customer_id=plan["kunde"].id,
        customer_reference=plan["ext_nr"],
        order_date=datetime.combine(plan["bestelldatum"], datetime.min.time()),
        requested_delivery_date=lieferdatum,
        confirmed_delivery_date=(
            lieferdatum
            if status in (OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION)
            else None
        ),
        actual_delivery_date=(
            lieferdatum
            if status in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)
            else None
        ),
        status=status,
        currency="EUR",
        total_net=Decimal("0"),
        total_vat=Decimal("0"),
        total_gross=Decimal("0"),
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0"),
    )
    db.add(order)
    db.flush()  # order.id verfügbar machen

    for position, pos in enumerate(plan["positionen"], start=1):
        product = pos["produkt"]
        zeile = pos["zeile"]
        line = OrderLine(
            order_id=order.id,
            position=position,
            product_id=product.id,
            product_sku=product.sku,
            beschreibung=product.name,  # Snapshot des Produktnamens
            quantity=zeile["menge"],
            unit=zeile.get("einheit") or "g",
            unit_price=zeile["einzelpreis"],
            discount_percent=Decimal("0"),
            tax_rate=product.tax_rate or TaxRate.REDUZIERT,
            variable_bundle_selections=pos["auswahl"],
        )
        line.calculate_line_totals()
        db.add(line)
        order.lines.append(line)

    order.calculate_totals()
    return order


def _import_order_history(db, rows: list[dict], *, parse_errors: Sequence[str] = ()) -> dict:
    """Importiert Bestellungen aus der Vorlage order_history (Altsystem, Go-Live).

    Mehrere Zeilen mit derselben `bestell_nr_extern` ergeben eine Bestellung.
    Idempotent über customer_reference: vorhandene werden übersprungen.
    Alles oder nichts: Hat eine Zeile einen Fehler — auch einen Lesefehler aus
    _parse_rows —, wird keine Bestellung angelegt (400 mit allen Fehlern).
    """
    import unicodedata

    def _normalize_name(s: str) -> str:
        # SQLite's func.lower() macht kein Unicode-Casefolding ("Ö" bleibt "Ö"),
        # daher Python-seitig vergleichen.
        return unicodedata.normalize("NFC", s.strip()).casefold()

    fehler: list[str] = list(parse_errors)

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["bestell_nr_extern"]].append(r)

    customer_index = {_normalize_name(c.name): c for c in db.execute(select(Customer)).scalars().all()}
    products_by_sku: dict[str, Optional[Product]] = {}

    def _get_product(sku: str) -> Optional[Product]:
        if sku not in products_by_sku:
            products_by_sku[sku] = db.execute(
                select(Product).where(Product.sku == sku)
            ).scalar_one_or_none()
        return products_by_sku[sku]

    heute = _today_berlin()
    geplant: list[dict] = []
    skipped = 0
    for ext_nr, group_rows in groups.items():
        # Idempotenz: gleicher customer_reference schon importiert → skip
        if db.execute(select(Order.id).where(Order.customer_reference == ext_nr).limit(1)).first():
            skipped += 1
            continue
        kunde = customer_index.get(_normalize_name(group_rows[0]["kunde"]))
        plan, plan_fehler = _pruefe_bestellung(ext_nr, group_rows, kunde, _get_product, heute)
        fehler.extend(plan_fehler)
        if plan:
            geplant.append(plan)

    if fehler:
        raise _import_abbruch(fehler)

    used_numbers: set[str] = set()
    for plan in geplant:
        _lege_bestellung_an(db, plan, used_numbers)
    db.commit()
    return {"created": len(geplant), "updated": skipped, "errors": []}
```

Gegenüber `efcea00` unverändert: Statusregel samt totem `except ValueError` (räumt P5.2 auf), Einheit `"g"` (ändert P5.3), Steuersatz aus dem Produktstamm, Bestellnummer aus dem Bestelldatum, Idempotenz über `customer_reference`.

- [ ] **Step 4: `import_entity` ruft den Bestell-Import mit den Lesefehlern auf**

In `backend/app/api/v1/imports.py` suchen:

```python
    rows, parse_errors = _parse_rows(file, entity)
    if not rows and parse_errors:
```

Ersetzen durch:

```python
    rows, parse_errors = _parse_rows(file, entity)
    if entity == "order_history":
        # Bestellungen: alles oder nichts. Lesefehler gehen in die Prüfung ein,
        # statt die Zeile still wegzulassen (A6-Rest).
        try:
            return _import_order_history(db, rows, parse_errors=parse_errors)
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Import fehlgeschlagen: {e}")
    if not rows and parse_errors:
```

- [ ] **Step 5: Kommentar in `IMPORTERS`**

In `backend/app/api/v1/imports.py` suchen:

```python
    "order_history": _import_order_history,
```

Ersetzen durch:

```python
    # Nur für die Prüfung auf bekannte Entitäten: import_entity ruft den
    # Bestell-Import mit eigener Signatur auf (alles oder nichts).
    "order_history": _import_order_history,
```

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_import_bestellungen_zukunft.py tests/test_gernot_260821.py -v -p no:cacheprovider`
Erwartet: 74 passed (9 + 65). In `test_gernot_260821.py` liegt `test_unveraendertes_template_importiert_nichts[order_history]`: leere Vorlage → 200, `created == 0`, `errors == []`.

- [ ] **Step 7: Vollauf**

Run: Vollauf aus dem Rahmen. Erwartet: dieselben 15 Fehlernamen + 1 Error wie die Baseline.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/imports.py backend/tests/test_import_bestellungen_zukunft.py
git commit -m "fix(import): Bestellimport nur noch ganz oder gar nicht, alle Fehler in einer Antwort"
```

---

### Task P5.2: Kopfdaten prüfen — Status, Bestelldatum, Kunde

**Files:**
- Modify: `backend/app/api/v1/imports.py:122` (Status-Spalte), `:256-261` (`HINWEISE["order_history"]`), neue Konstanten vor `_bundle_auswahl`, `_pruefe_bestellung`
- Test: `backend/tests/test_import_bestellungen_zukunft.py` (Dateikopf + anhängen)

**Interfaces:**
- Produces: `_STATUS_AUS_DATEI: dict[str, OrderStatus]`, `_GUELTIGE_STATUS: str`, `_status_schluessel(roh) -> str` (NFC, `_` → Leerzeichen, Großbuchstaben).
- Status-Spalte in `COLUMNS["order_history"]` hat den Typ `"str"`. Die Typzeile der Vorlage zeigt deshalb `[str]` statt der Werteliste; die Werte stehen im Hinweis. `test_gernot_260821.py::…test_unveraendertes_template_importiert_nichts` bleibt grün, weil die Typzeile mit „[" beginnt (`_parse_rows`, `imports.py:347`). Alte Vorlagen mit `[enum:…]` in der Typzeile bleiben lesbar (gleicher Grund).
- Regeln (Fehler, nicht Warnung):
  - Status leer → Datumsregel aus `efcea00`, unverändert.
  - Status gesetzt → Enum-Wert oder Oberflächenbezeichnung (`Bestätigt`, `In Produktion`, `Gepackt`, Groß-/Kleinschreibung egal), sonst Fehler mit der Liste der gültigen Werte.
  - `IN_PRODUKTION` mit Lieferdatum ab heute → Fehler (P2, M2). Mit Lieferdatum in der Vergangenheit erlaubt, wie ausdrücklich `BESTAETIGT` in der Vergangenheit (`test_ausdruecklich_bestaetigt_in_vergangenheit_bleibt_bestaetigt`).
  - Bestelldatum nach dem Lieferdatum → Fehler. Bestelldatum nach heute (Europe/Berlin) → Fehler.
  - Kunde deaktiviert → Fehler (wie `create_order`, `sales.py:830-831`).

- [ ] **Step 1: `import pytest` im Dateikopf**

In `backend/tests/test_import_bestellungen_zukunft.py` suchen:

```python
from openpyxl import load_workbook
```

Ersetzen durch:

```python
import pytest
from openpyxl import load_workbook
```

- [ ] **Step 2: Failing Tests anhängen**

Ans Dateiende:

```python
class TestP5Kopfdaten:
    """Status, Bestelldatum und Kunde werden geprüft statt still übernommen."""

    @pytest.mark.parametrize("eingabe, erwartet", [
        ("Bestätigt", "BESTAETIGT"),        # heute: still GELIEFERT
        ("in produktion", "IN_PRODUKTION"),  # heute: still GELIEFERT
        ("Geliefert", "GELIEFERT"),          # Charakterisierung, schon grün
        ("STORNIERT", "STORNIERT"),          # Charakterisierung, schon grün
    ])
    def test_bezeichnungen_der_oberflaeche_werden_erkannt(self, client, eingabe, erwartet):
        vergangen = _heute_berlin() - timedelta(days=3)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-STATUS", kunde, produkt, vergangen, vergangen, status=eingabe),
        ])

        assert response.status_code == 200, response.text
        assert _bestellung(client, "P5-STATUS")["status"] == erwartet

    def test_unbekannter_status_ist_ein_fehler(self, client):
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-OFFEN", kunde, produkt, heute, heute + timedelta(days=2), status="offen"),
        ])

        assert response.status_code == 400, response.text
        assert "Status 'offen'" in response.json()["detail"]
        assert _p5_referenzen(client) == set()

    def test_gepackt_fuer_ausstehende_lieferung_wird_abgelehnt(self, client):
        """IN_PRODUKTION heißt nach P2 „gepackt“ — das passiert im Tagesplan,
        nicht im Import (P2, Entscheidung M2)."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-GEPACKT", kunde, produkt, heute, heute + timedelta(days=2), status="IN_PRODUKTION"),
        ])

        assert response.status_code == 400, response.text
        assert "P5-GEPACKT" in response.json()["detail"]
        assert "IN_PRODUKTION" in response.json()["detail"]

    def test_bestelldatum_nach_lieferdatum(self, client):
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()
        bestelldatum = heute - timedelta(days=1)
        lieferdatum = heute - timedelta(days=3)

        response = _import_bestellungen(client, [
            _p5_zeile("P5-SPAET-BESTELLT", kunde, produkt, bestelldatum, lieferdatum),
        ])

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "P5-SPAET-BESTELLT" in detail
        assert f"Bestelldatum {bestelldatum.strftime('%d.%m.%Y')} liegt nach dem Lieferdatum" in detail

    def test_bestelldatum_in_der_zukunft(self, client):
        """Produktionsfall BE-20261011-0001: Bestelldatum 11.10., importiert am 08.10."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()
        bestelldatum = heute + timedelta(days=1)

        response = _import_bestellungen(client, [
            _p5_zeile("P5-ZUKUNFT-BESTELLT", kunde, produkt, bestelldatum, heute + timedelta(days=3)),
        ])

        assert response.status_code == 400, response.text
        assert f"Bestelldatum {bestelldatum.strftime('%d.%m.%Y')} liegt in der Zukunft" in response.json()["detail"]

    def test_deaktivierter_kunde(self, client):
        """Wie create_order (sales.py: 'Kunde ist deaktiviert')."""
        import uuid
        from app.models.customer import Customer

        heute = _heute_berlin()
        kunde = _kunde(client, name="Ehemals GmbH")
        produkt = _produkt()
        with TestingSessionLocal() as db:
            db.get(Customer, uuid.UUID(kunde["id"])).aktiv = False
            db.commit()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-INAKTIV", kunde, produkt, heute, heute + timedelta(days=2)),
        ])

        assert response.status_code == 400, response.text
        assert "Ehemals GmbH" in response.json()["detail"]
        assert "deaktiviert" in response.json()["detail"]

    def test_vorlage_nennt_die_gueltigen_status(self, client):
        response = client.get("/api/v1/imports/template/order_history")
        workbook = load_workbook(io.BytesIO(response.content), data_only=True)
        texte = " ".join(
            str(zelle) for zeile in workbook["Beispiel"].iter_rows(values_only=True) for zelle in zeile if zelle
        )
        assert "ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT" in texte
```

Die Parameter `Geliefert` und `STORNIERT` sind Charakterisierungstests und schon vor dem Fix grün.

- [ ] **Step 3: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_import_bestellungen_zukunft.py -v -p no:cacheprovider`
Erwartet: **8 failed, 11 passed.** Rot: `test_bezeichnungen_der_oberflaeche_werden_erkannt[Bestätigt-BESTAETIGT]` und `[in produktion-IN_PRODUKTION]` (beide `'GELIEFERT' == …`), `test_unbekannter_status_ist_ein_fehler`, `test_gepackt_fuer_ausstehende_lieferung_wird_abgelehnt`, `test_bestelldatum_nach_lieferdatum`, `test_bestelldatum_in_der_zukunft`, `test_deaktivierter_kunde` (alle `assert 200 == 400`), `test_vorlage_nennt_die_gueltigen_status`.

- [ ] **Step 4: Status-Spalte roh lesen**

In `backend/app/api/v1/imports.py` suchen:

```python
        ("status", "status", False, "enum:ENTWURF|BESTAETIGT|IN_PRODUKTION|GELIEFERT|FAKTURIERT|STORNIERT"),
```

Ersetzen durch:

```python
        # Roh lesen ("str" statt "enum:"): Ein ungültiger Wert wird sonst still
        # zu None und damit wie eine leere Zelle behandelt. Gültige Werte prüft
        # _import_order_history, sie stehen im Hinweis der Vorlage.
        ("status", "status", False, "str"),
```

- [ ] **Step 5: Hinweis der Vorlage**

In `backend/app/api/v1/imports.py` suchen:

```python
        "Status leer lassen: Lieferdatum in der Vergangenheit = GELIEFERT, heute oder "
        "später = BESTAETIGT (erscheint im Tagesplan)."
    ),
```

Ersetzen durch:

```python
        "Status leer lassen: Lieferdatum in der Vergangenheit = GELIEFERT, heute oder "
        "später = BESTAETIGT (erscheint im Tagesplan). Gültige Status-Werte: "
        "ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT "
        "(auch 'Bestätigt', 'In Produktion', 'Gepackt'). GELIEFERT heißt: ohne "
        "Lieferschein und ohne Lagerabzug, der Sammellauf erfasst die Bestellung nicht. "
        "Bestelldatum: nicht in der Zukunft und nicht nach dem Lieferdatum. "
        "Hat eine Zeile einen Fehler, wird keine Bestellung der Datei angelegt."
    ),
```

- [ ] **Step 6: Status-Abbildung**

In `backend/app/api/v1/imports.py` suchen (Kopfzeile von `_bundle_auswahl` aus P5.1):

```python
def _bundle_auswahl(
```

Ersetzen durch:

```python
# Status-Spalte: Enum-Werte und die Bezeichnungen der Oberfläche (auch mit
# Umlaut). Schlüssel nach _status_schluessel normalisiert.
_STATUS_AUS_DATEI = {
    "ENTWURF": OrderStatus.ENTWURF,
    "BESTAETIGT": OrderStatus.BESTAETIGT,
    "BESTÄTIGT": OrderStatus.BESTAETIGT,
    "IN PRODUKTION": OrderStatus.IN_PRODUKTION,
    "GEPACKT": OrderStatus.IN_PRODUKTION,
    "GELIEFERT": OrderStatus.GELIEFERT,
    "FAKTURIERT": OrderStatus.FAKTURIERT,
    "STORNIERT": OrderStatus.STORNIERT,
}
_GUELTIGE_STATUS = "ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT"


def _status_schluessel(roh: Any) -> str:
    """'in_produktion ' → 'IN PRODUKTION'; NFC, weil Excel am Mac 'ä' zerlegt speichern kann."""
    import unicodedata

    text = unicodedata.normalize("NFC", str(roh))
    return " ".join(text.replace("_", " ").split()).upper()


def _bundle_auswahl(
```

- [ ] **Step 7: Kopfprüfungen in `_pruefe_bestellung`**

In `backend/app/api/v1/imports.py` suchen (direkt unter der Kundenprüfung `if not kunde: …`):

```python
    lieferdatum = head["lieferdatum"]
    status_str = head.get("status")
    if not status_str:
        status = OrderStatus.GELIEFERT if lieferdatum < heute else OrderStatus.BESTAETIGT
    else:
        try:
            status = OrderStatus(status_str)
        except ValueError:
            status = OrderStatus.GELIEFERT

    if status in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT) and lieferdatum > heute:
```

Ersetzen durch:

```python
    elif not kunde.aktiv:
        fehler.append(f"Bestellung '{ext_nr}': Kunde '{kunde.name}' ist deaktiviert")

    lieferdatum = head["lieferdatum"]
    bestelldatum = head["bestelldatum"]
    roh_status = head.get("status")
    if roh_status is None:
        status = OrderStatus.GELIEFERT if lieferdatum < heute else OrderStatus.BESTAETIGT
    else:
        status = _STATUS_AUS_DATEI.get(_status_schluessel(roh_status))
        if status is None:
            fehler.append(
                f"Bestellung '{ext_nr}': Status '{roh_status}' ist unbekannt — "
                f"erlaubt sind {_GUELTIGE_STATUS} oder eine leere Zelle"
            )

    if status == OrderStatus.IN_PRODUKTION and lieferdatum >= heute:
        fehler.append(
            f"Bestellung '{ext_nr}': Status IN_PRODUKTION (gepackt) für eine ausstehende Lieferung — "
            "gepackt wird im Tagesplan; Status-Spalte leer lassen oder BESTAETIGT eintragen"
        )
    if bestelldatum > lieferdatum:
        fehler.append(
            f"Bestellung '{ext_nr}': Bestelldatum {bestelldatum.strftime('%d.%m.%Y')} liegt nach "
            f"dem Lieferdatum {lieferdatum.strftime('%d.%m.%Y')}"
        )
    if bestelldatum > heute:
        fehler.append(
            f"Bestellung '{ext_nr}': Bestelldatum {bestelldatum.strftime('%d.%m.%Y')} liegt in der Zukunft"
        )

    if status in (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT) and lieferdatum > heute:
```

Das `elif` hängt an `if not kunde:` direkt darüber. Danach im Rückgabe-Dict suchen:

```python
        "bestelldatum": head["bestelldatum"],
        "lieferdatum": lieferdatum,
```

Ersetzen durch:

```python
        "bestelldatum": bestelldatum,
        "lieferdatum": lieferdatum,
```

- [ ] **Step 8: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_import_bestellungen_zukunft.py tests/test_gernot_260821.py -v -p no:cacheprovider`
Erwartet: 84 passed (19 + 65).

- [ ] **Step 9: Vollauf** — wie P5.1 Step 7.

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/v1/imports.py backend/tests/test_import_bestellungen_zukunft.py
git commit -m "fix(import): ungültiger Status, Bestelldatum und inaktiver Kunde werden gemeldet statt still übernommen"
```

---

### Task P5.3: Positionen prüfen — Menge, Preis, Einheit, variables Bundle

**Files:**
- Modify: `backend/app/api/v1/imports.py` (`HINWEISE["order_history"]`, Konstante `_OFFEN`, Positionsschleife in `_pruefe_bestellung`, `unit=` in `_lege_bestellung_an`)
- Test: `backend/tests/test_import_bestellungen_zukunft.py` (anhängen)

**Interfaces:**
- Produces: `_OFFEN = (ENTWURF, BESTAETIGT, IN_PRODUKTION)` (dieselben Status wie die Tagesplan-Abfrage, `production.py:523`). P5.4 nutzt sie für den Packtag.
- Regeln:
  - Menge ≤ 0 → Fehler, Einzelpreis < 0 → Fehler (wie `schemas/order.py:32`, `:34`).
  - Einheit leer → `STK` (Entscheidung 2). Eine befüllte Einheit wird unverändert übernommen.
  - Variables Bundle (`Product.is_variable_bundle`) in einer Bestellung, die noch gepackt wird (Status in `_OFFEN` **und** Lieferdatum ab heute): Sortenauswahl Pflicht, Anzahl zwischen `variable_bundle_min_slots or 1` und `variable_bundle_max_slots or 99` (wie `sales.py:990-1007`). Gelieferte Historie bleibt ohne Auswahl importierbar.

- [ ] **Step 1: Failing Tests anhängen**

```python
def _p5_variables_bundle(sku="MG-GASTROTRAY", min_slots=2, max_slots=3):
    """Variables Bundle (Gastrotray): der Kunde wählt min..max Sorten."""
    import uuid
    from app.models.product import Product

    bundle = _produkt(sku)
    with TestingSessionLocal() as db:
        produkt = db.get(Product, uuid.UUID(bundle["id"]))
        produkt.is_variable_bundle = True
        produkt.variable_bundle_min_slots = min_slots
        produkt.variable_bundle_max_slots = max_slots
        db.commit()
    return bundle


class TestP5Positionen:
    """Menge, Preis, Einheit und Sortenauswahl wie im Bestellformular."""

    def test_leere_einheit_wird_stueck(self, client):
        """Formular-Standard ist STK (CreateOrderModal.tsx: 'es wird aktuell
        nichts abgewogen verkauft'). Bisher wurde daraus 'g'."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-EINHEIT", kunde, produkt, heute, heute + timedelta(days=2), einheit=None),
        ])

        assert response.status_code == 200, response.text
        assert [line["unit"] for line in _bestellung(client, "P5-EINHEIT")["lines"]] == ["STK"]

    def test_angegebene_einheit_bleibt(self, client):
        """Charakterisierung, schon grün: eine befüllte Einheit wird übernommen."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-KISTE", kunde, produkt, heute, heute + timedelta(days=2), einheit="KISTE_12"),
        ])

        assert response.status_code == 200, response.text
        assert [line["unit"] for line in _bestellung(client, "P5-KISTE")["lines"]] == ["KISTE_12"]

    def test_menge_null_und_negativer_preis(self, client):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-NULL", kunde, produkt, heute, lieferdatum, menge=0),
            _p5_zeile("P5-MINUS", kunde, produkt, heute, lieferdatum, preis="-1.00"),
        ])

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "Bestellung 'P5-NULL'" in detail and "Menge 0" in detail
        assert "Bestellung 'P5-MINUS'" in detail and "Einzelpreis -1" in detail
        assert _p5_referenzen(client) == set()

    def test_offenes_variables_bundle_braucht_sorten_in_den_grenzen(self, client):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        kunde = _kunde(client)
        bundle = _p5_variables_bundle()
        _produkt("MG-SONNE")  # Sorte existiert — der Fehler liegt an der Anzahl

        response = _import_bestellungen(client, [
            _p5_zeile("P5-OHNE-SORTEN", kunde, bundle, heute, lieferdatum),
            _p5_zeile("P5-EINE-SORTE", kunde, bundle, heute, lieferdatum,
                      bundle='[{"sku": "MG-SONNE", "quantity": 1}]'),
        ])

        assert response.status_code == 400, response.text
        detail = response.json()["detail"]
        assert "Bestellung 'P5-OHNE-SORTEN'" in detail and "variables Bundle" in detail
        assert "Bestellung 'P5-EINE-SORTE'" in detail and "2–3 Sorten, erhalten: 1" in detail

    def test_variables_bundle_mit_gueltiger_auswahl(self, client):
        """Charakterisierung, schon grün: Auswahl wird aufgelöst und gespeichert."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        bundle = _p5_variables_bundle()
        sonne = _produkt("MG-SONNE")
        erbse = _produkt("MG-ERBSE")

        response = _import_bestellungen(client, [
            _p5_zeile("P5-TRAY", kunde, bundle, heute, heute + timedelta(days=2),
                      bundle='[{"sku": "MG-SONNE", "quantity": 1}, {"sku": "MG-ERBSE", "quantity": 1}]'),
        ])

        assert response.status_code == 200, response.text
        auswahl = _bestellung(client, "P5-TRAY")["lines"][0]["variable_bundle_selections"]
        assert sorted(s["product_id"] for s in auswahl) == sorted([sonne["id"], erbse["id"]])

    def test_geliefertes_variables_bundle_ohne_auswahl_bleibt_erlaubt(self, client):
        """Charakterisierung, schon grün: Historie wird nicht mehr gepackt —
        die Altdaten kennen die Sortenauswahl oft nicht."""
        vergangen = _heute_berlin() - timedelta(days=5)
        kunde = _kunde(client)
        bundle = _p5_variables_bundle()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-TRAY-ALT", kunde, bundle, vergangen, vergangen),
        ])

        assert response.status_code == 200, response.text
        assert _bestellung(client, "P5-TRAY-ALT")["status"] == "GELIEFERT"
```

`test_angegebene_einheit_bleibt`, `test_variables_bundle_mit_gueltiger_auswahl` und `test_geliefertes_variables_bundle_ohne_auswahl_bleibt_erlaubt` sind Charakterisierungstests und schon grün.

- [ ] **Step 2: Rot bestätigen**

Run: wie P5.2 Step 3.
Erwartet: **3 failed, 22 passed.** Rot: `test_leere_einheit_wird_stueck` (`['g'] == ['STK']`), `test_menge_null_und_negativer_preis` und `test_offenes_variables_bundle_braucht_sorten_in_den_grenzen` (beide `assert 200 == 400`).

- [ ] **Step 3: Hinweis der Vorlage ergänzen**

In `backend/app/api/v1/imports.py` suchen:

```python
        "Bestelldatum: nicht in der Zukunft und nicht nach dem Lieferdatum. "
```

Ersetzen durch:

```python
        "Bestelldatum: nicht in der Zukunft und nicht nach dem Lieferdatum. "
        "Einheit leer = STK. Variable Bundles brauchen für offene Bestellungen ab heute "
        "die Sortenauswahl in bundle_selections. "
```

- [ ] **Step 4: Konstante `_OFFEN`**

In `backend/app/api/v1/imports.py` suchen:

```python
_GUELTIGE_STATUS = "ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT"
```

Ersetzen durch:

```python
_GUELTIGE_STATUS = "ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT"
# Status, die noch gepackt und geliefert werden (wie day-plan, production.py)
_OFFEN = (OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION)
```

- [ ] **Step 5: Positionsschleife in `_pruefe_bestellung`**

In `backend/app/api/v1/imports.py` suchen:

```python
    positionen: list[dict] = []
    for zeile in zeilen:
        product = get_product(zeile["produkt_sku"])
        if not product:
            fehler.append(f"Bestellung '{ext_nr}': SKU '{zeile['produkt_sku']}' nicht gefunden")
            continue
        auswahl, auswahl_fehler = _bundle_auswahl(ext_nr, zeile.get("bundle_selections"), get_product)
        fehler.extend(auswahl_fehler)
        positionen.append({"produkt": product, "zeile": zeile, "auswahl": auswahl})
```

Ersetzen durch:

```python
    # Sortenauswahl nur dort Pflicht, wo noch gepackt wird — Altdaten
    # gelieferter Bestellungen kennen sie oft nicht.
    wird_noch_gepackt = status in _OFFEN and lieferdatum >= heute
    positionen: list[dict] = []
    for zeile in zeilen:
        sku = zeile["produkt_sku"]
        product = get_product(sku)
        if not product:
            fehler.append(f"Bestellung '{ext_nr}': SKU '{sku}' nicht gefunden")
            continue
        # Wie das Bestellschema (schemas/order.py: quantity > 0, unit_price >= 0)
        if zeile["menge"] <= 0:
            fehler.append(f"Bestellung '{ext_nr}', SKU '{sku}': Menge {zeile['menge']} — muss größer als 0 sein")
        if zeile["einzelpreis"] < 0:
            fehler.append(f"Bestellung '{ext_nr}', SKU '{sku}': Einzelpreis {zeile['einzelpreis']} ist negativ")
        auswahl, auswahl_fehler = _bundle_auswahl(ext_nr, zeile.get("bundle_selections"), get_product)
        fehler.extend(auswahl_fehler)
        # Wie create_order (sales.py, Abschnitt „Variable Bundle")
        if product.is_variable_bundle and wird_noch_gepackt and not auswahl_fehler:
            if not auswahl:
                fehler.append(
                    f"Bestellung '{ext_nr}': '{product.name}' ist ein variables Bundle — "
                    "bitte Sorten in bundle_selections angeben"
                )
            else:
                slots = sum(s["quantity"] for s in auswahl)
                min_slots = product.variable_bundle_min_slots or 1
                max_slots = product.variable_bundle_max_slots or 99
                if not min_slots <= slots <= max_slots:
                    fehler.append(
                        f"Bestellung '{ext_nr}': '{product.name}' braucht {min_slots}–{max_slots} "
                        f"Sorten, erhalten: {slots}"
                    )
        positionen.append({"produkt": product, "zeile": zeile, "auswahl": auswahl})
```

- [ ] **Step 6: Einheit in `_lege_bestellung_an`**

In `backend/app/api/v1/imports.py` suchen:

```python
            unit=zeile.get("einheit") or "g",
```

Ersetzen durch:

```python
            # Leer = Stück wie im Bestellformular (CreateOrderModal.tsx). Das
            # Produkt trägt keine verlässliche Verkaufseinheit: base_unit ist
            # beim Excel-Produktimport immer G, sales_units wird nirgends gepflegt.
            unit=zeile.get("einheit") or "STK",
```

- [ ] **Step 7: Grün bestätigen**

Run: wie P5.2 Step 8. Erwartet: 90 passed (25 + 65).

- [ ] **Step 8: Vollauf** — wie P5.1 Step 7.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/v1/imports.py backend/tests/test_import_bestellungen_zukunft.py
git commit -m "fix(import): Menge, Preis und Bundle-Sorten geprüft, leere Einheit wird Stück statt Gramm"
```

---

### Task P5.4: Anlage wie im Formular — Adress-Schnappschuss und Packtag

**Files:**
- Create: `backend/app/services/bestell_adressen.py`
- Modify: `backend/app/api/v1/imports.py` (`_lege_bestellung_an`, Aufruf in `_import_order_history`)
- Test: `backend/tests/test_import_bestellungen_zukunft.py` (anhängen)

**Interfaces:**
- Produces: `bestell_adressen.adressen_vom_kunden(customer) -> tuple[Optional[dict], Optional[dict]]` = (Rechnungsadresse, Lieferadresse), Inhalt wie `sales.py:879-901` (Name, Straße, Hausnummer, Adresszusatz, PLZ, Ort, Land). `create_order` wird **nicht** umgestellt (Überschneidung `sales.py`), siehe „Nicht in P5".
- `_lege_bestellung_an(db, plan, used_numbers, heute) -> Order`. Packtag = Lieferdatum, wenn der Status in `_OFFEN` ist und das Lieferdatum heute oder früher liegt (Europe/Berlin), sonst leer (= Vortag, `Order.effective_packing_date`). Gleiche Regel wie `Order.resolve_packing_date` (`models/order.py:176-189`), aber mit dem Berliner Datum der Statusregel statt `date.today()` (Serverzeit, T1 Risiko 7).

- [ ] **Step 1: Failing Tests anhängen**

```python
def _p5_kunde_mit_adresse(client, name="RATIONAL AG"):
    """Kunde mit Standardadresse samt Adresszusatz (Muster test_gernot_260821.py)."""
    kunde = _kunde(client, name=name)
    response = client.post(f"/api/v1/sales/customers/{kunde['id']}/addresses", json={
        "address_type": "BOTH",
        "strasse": "Siegfried-Meister-Strasse", "hausnummer": "1",
        "adresszusatz": "Werk 2 - Tor 210",
        "plz": "86899", "ort": "Landsberg", "is_default": True,
    })
    assert response.status_code == 201, response.text
    return kunde


class TestP5AnlageWieImFormular:
    """Adress-Schnappschuss und Packtag wie create_order."""

    def test_adressen_wie_bei_create_order(self, client):
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=2)
        kunde = _p5_kunde_mit_adresse(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-ADRESSE", kunde, produkt, heute, lieferdatum),
        ])
        assert response.status_code == 200, response.text
        importiert = _bestellung(client, "P5-ADRESSE")

        formular = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": lieferdatum.isoformat(),
            "lines": [{"product_id": produkt["id"], "product_name": produkt["name"],
                       "quantity": 1, "unit": "STK", "unit_price": "3.90"}],
        })
        assert formular.status_code == 201, formular.text

        assert importiert["delivery_address"]["adresszusatz"] == "Werk 2 - Tor 210"
        assert importiert["delivery_address"] == formular.json()["delivery_address"]
        assert importiert["billing_address"] == formular.json()["billing_address"]

    def test_lieferschein_zeigt_die_lieferadresse(self, client):
        from tests.test_documents_preise import _pdf_text

        heute = _heute_berlin()
        kunde = _p5_kunde_mit_adresse(client)
        produkt = _produkt()
        response = _import_bestellungen(client, [
            _p5_zeile("P5-LS", kunde, produkt, heute, heute + timedelta(days=2)),
        ])
        assert response.status_code == 200, response.text
        order = _bestellung(client, "P5-LS")

        note = client.post(f"/api/v1/sales/orders/{order['id']}/delivery-notes", json={})
        assert note.status_code == 201, note.text
        pdf = client.get(f"/api/v1/sales/delivery-notes/{note.json()['id']}/pdf")
        assert pdf.status_code == 200, pdf.text
        assert b"Tor 210" in _pdf_text(pdf.content)

    def test_kunde_ohne_adresse_bleibt_ohne_schnappschuss(self, client):
        """Charakterisierung, schon grün: wie create_order kein Schnappschuss ohne Kundenadresse."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-OHNE-ADRESSE", kunde, produkt, heute, heute + timedelta(days=2)),
        ])

        assert response.status_code == 200, response.text
        order = _bestellung(client, "P5-OHNE-ADRESSE")
        assert order["delivery_address"] is None
        assert order["billing_address"] is None

    def test_lieferdatum_heute_steht_unter_verpacken(self, client):
        """T1 Repro 2: Same-Day-Import stand nur unter „Ausliefern“."""
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-HEUTE", kunde, produkt, heute, heute),
        ])
        assert response.status_code == 200, response.text
        order = _bestellung(client, "P5-HEUTE")
        assert order["packing_date"] == heute.isoformat()

        plan = client.get("/api/v1/production/day-plan", params={"target_date": heute.isoformat()})
        assert plan.status_code == 200, plan.text
        assert order["id"] in [o["order_id"] for o in plan.json()["verpacken"]]
        assert order["id"] in [o["order_id"] for o in plan.json()["ausliefern"]]

    def test_kuenftige_lieferung_behaelt_den_standard_packtag(self, client):
        """Charakterisierung, schon grün: Packtag bleibt leer = Vortag der Lieferung."""
        heute = _heute_berlin()
        lieferdatum = heute + timedelta(days=3)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-SPAETER", kunde, produkt, heute, lieferdatum),
        ])

        assert response.status_code == 200, response.text
        order = _bestellung(client, "P5-SPAETER")
        assert order["packing_date"] is None
        assert order["effective_packing_date"] == (lieferdatum - timedelta(days=1)).isoformat()
```

`test_kunde_ohne_adresse_bleibt_ohne_schnappschuss` und `test_kuenftige_lieferung_behaelt_den_standard_packtag` sind Charakterisierungstests und schon grün.

- [ ] **Step 2: Rot bestätigen**

Run: wie P5.2 Step 3.
Erwartet: **3 failed, 27 passed.** Rot: `test_adressen_wie_bei_create_order` (`TypeError: 'NoneType' object is not subscriptable`), `test_lieferschein_zeigt_die_lieferadresse` (`assert b'Tor 210' in …`), `test_lieferdatum_heute_steht_unter_verpacken` (`assert None == '<heute>'`).

- [ ] **Step 3: Neues Modul `backend/app/services/bestell_adressen.py`**

```python
"""Adress-Schnappschuss einer Bestellung aus den Kundenadressen.

Dieselbe Regel wie `create_order` (sales.py, Abschnitt „Adressen vom Kunden
übernehmen"): Standard-Rechnungs- und -Lieferadresse des Kunden, inklusive
Adresszusatz. Der trägt die Zustellinfo („Werk 2 - Tor 210") und wäre ohne
Schnappschuss auf jedem später erzeugten Beleg weg.

Heute nutzt nur der Bestell-Import diese Funktion. `create_order` behält
vorerst seinen eigenen Block, weil Paket 1 und P1 parallel in sales.py
arbeiten; der Test `test_adressen_wie_bei_create_order` hält beide Wege
gleich.
"""
from typing import Optional

from app.models.customer import Customer, CustomerAddress


def _schnappschuss(customer: Customer, adresse: Optional[CustomerAddress]) -> Optional[dict]:
    if adresse is None:
        return None
    return {
        "name": adresse.name or customer.name,
        "strasse": adresse.strasse,
        "hausnummer": adresse.hausnummer,
        "adresszusatz": adresse.adresszusatz,
        "plz": adresse.plz,
        "ort": adresse.ort,
        "land": adresse.land,
    }


def adressen_vom_kunden(customer: Customer) -> tuple[Optional[dict], Optional[dict]]:
    """(Rechnungsadresse, Lieferadresse) als JSON-Schnappschuss; None ohne passende Adresse."""
    return (
        _schnappschuss(customer, customer.billing_address),
        _schnappschuss(customer, customer.shipping_address),
    )
```

- [ ] **Step 4: `_lege_bestellung_an` setzt Adressen und Packtag**

In `backend/app/api/v1/imports.py` suchen:

```python
def _lege_bestellung_an(db, plan: dict, used_numbers: set[str]) -> Order:
    """Legt eine geprüfte Bestellung samt Positionen an (ohne Commit)."""
    status = plan["status"]
    lieferdatum = plan["lieferdatum"]
    order = Order(
        order_number=_generate_historic_order_number(db, plan["bestelldatum"], used_numbers),
        customer_id=plan["kunde"].id,
        customer_reference=plan["ext_nr"],
        order_date=datetime.combine(plan["bestelldatum"], datetime.min.time()),
        requested_delivery_date=lieferdatum,
```

Ersetzen durch:

```python
def _lege_bestellung_an(db, plan: dict, used_numbers: set[str], heute: date) -> Order:
    """Legt eine geprüfte Bestellung samt Positionen an (ohne Commit)."""
    from app.services.bestell_adressen import adressen_vom_kunden

    status = plan["status"]
    lieferdatum = plan["lieferdatum"]
    rechnungsadresse, lieferadresse = adressen_vom_kunden(plan["kunde"])
    order = Order(
        order_number=_generate_historic_order_number(db, plan["bestelldatum"], used_numbers),
        customer_id=plan["kunde"].id,
        customer_reference=plan["ext_nr"],
        # Schnappschuss wie create_order — ohne ihn fehlt die Lieferadresse
        # auf Lieferschein und Auftragsbestätigung (pdf_service.py).
        billing_address=rechnungsadresse,
        delivery_address=lieferadresse,
        order_date=datetime.combine(plan["bestelldatum"], datetime.min.time()),
        requested_delivery_date=lieferdatum,
        # Wie Order.resolve_packing_date, aber mit dem Berliner Datum der
        # Statusregel: Liegt der Vortag schon zurück (Lieferung heute), wird
        # am Liefertag gepackt — sonst fehlte die Bestellung unter „Verpacken".
        packing_date=lieferdatum if status in _OFFEN and lieferdatum <= heute else None,
```

Dann in `_import_order_history` suchen:

```python
    for plan in geplant:
        _lege_bestellung_an(db, plan, used_numbers)
```

Ersetzen durch:

```python
    for plan in geplant:
        _lege_bestellung_an(db, plan, used_numbers, heute)
```

- [ ] **Step 5: Grün bestätigen**

Run: wie P5.2 Step 8. Erwartet: 95 passed (30 + 65).

- [ ] **Step 6: Vollauf** — wie P5.1 Step 7.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/bestell_adressen.py backend/app/api/v1/imports.py backend/tests/test_import_bestellungen_zukunft.py
git commit -m "fix(import): Bestellungen bekommen Kundenadressen und bei Lieferung heute den Packtag"
```

---

### Task P5.5: Nachvollziehbar — `created_by`, Audit `IMPORT`, Aufteilung nach Status

**Files:**
- Modify: `backend/app/api/v1/imports.py:25` (Import `CurrentUser`), Konstanten/Helfer nach `_OFFEN`, `_lege_bestellung_an`, `_import_order_history`, `import_entity`
- Test: `backend/tests/test_import_bestellungen_zukunft.py` (anhängen)

**Interfaces:**
- `import_entity(entity, db, user: CurrentUser, file)`. Der Router hängt schon an `Depends(get_current_user)` (`main.py:788-792`); FastAPI löst die Abhängigkeit je Request einmal auf.
- `_benutzer_id(user) -> Optional[UUID]` wie `print_jobs._benutzer_id` (`print_jobs.py:63-68`). Basic-Auth-Logins haben die ID `basic-auth:<name>` (`deps.py:49-56`); `UUID(user["id"])` wie in `sales.py:921` würde den Import mit 400 „Import fehlgeschlagen: badly formed hexadecimal UUID string" abbrechen.
- `_lege_bestellung_an(db, plan, used_numbers, heute, *, user=None, dateiname=None)` setzt `created_by` und schreibt je Bestellung `OrderAuditLog(action="IMPORT", user_id, user_name=user["username"], new_values={"status", "bestell_nr_extern", "datei"}, reason="Bestell-Import")`.
- `_import_order_history(db, rows, *, parse_errors=(), user=None, dateiname=None) -> dict` liefert zusätzlich `status_counts: dict[str, int]` (Enum-Wert → Anzahl angelegter Bestellungen) und `hinweis: Optional[str]` (`None`, wenn nichts angelegt wurde). `_import_hinweis(status_counts)` baut den Satz in Enum-Reihenfolge, `IN_PRODUKTION` heißt „Gepackt".

- [ ] **Step 1: Failing Tests anhängen**

```python
TEST_USER_ID = "123e4567-e89b-12d3-a456-426614174000"  # conftest.client


class TestP5Nachvollziehbar:
    """Wer hat importiert, was ist dabei entstanden?"""

    def test_created_by_und_audit_eintrag(self, client):
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-AUDIT", kunde, produkt, heute, heute + timedelta(days=2)),
        ])
        assert response.status_code == 200, response.text
        order = _bestellung(client, "P5-AUDIT")

        assert order["created_by"] == TEST_USER_ID
        audit = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
        assert audit.status_code == 200, audit.text
        assert [(e["action"], e["user_id"]) for e in audit.json()] == [("IMPORT", TEST_USER_ID)]
        eintrag = audit.json()[0]
        assert eintrag["user_name"] == "testuser"
        assert eintrag["new_values"] == {
            "status": "BESTAETIGT", "bestell_nr_extern": "P5-AUDIT", "datei": "bestellungen.xlsx",
        }

    def test_antwort_nennt_die_aufteilung_nach_status(self, client):
        heute = _heute_berlin()
        vergangen = heute - timedelta(days=4)
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-ALT-1", kunde, produkt, vergangen, vergangen),
            _p5_zeile("P5-ALT-2", kunde, produkt, vergangen, vergangen),
            _p5_zeile("P5-NEU", kunde, produkt, heute, heute + timedelta(days=2)),
        ])

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["created"] == 3
        assert body["errors"] == []
        assert body["status_counts"] == {"GELIEFERT": 2, "BESTAETIGT": 1}
        assert "2 Geliefert" in body["hinweis"]
        assert "1 Bestätigt" in body["hinweis"]
        assert "Sammellauf" in body["hinweis"]

    def test_basic_auth_kennung_bricht_den_import_nicht(self, client):
        """Basic-Auth-Logins haben keine UUID als ID (deps.py: 'basic-auth:<name>')."""
        from app.api.deps import get_current_user
        from app.main import app

        async def basic_auth_user():
            return {"id": "basic-auth:gernot", "username": "gernot", "roles": ["admin"]}

        app.dependency_overrides[get_current_user] = basic_auth_user
        heute = _heute_berlin()
        kunde = _kunde(client)
        produkt = _produkt()

        response = _import_bestellungen(client, [
            _p5_zeile("P5-BASIC", kunde, produkt, heute, heute + timedelta(days=2)),
        ])

        assert response.status_code == 200, response.text
        order = _bestellung(client, "P5-BASIC")
        assert order["created_by"] is None
        audit = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log").json()
        assert [(e["action"], e["user_name"]) for e in audit] == [("IMPORT", "gernot")]

    def test_halle_darf_nicht_importieren(self, client):
        """Charakterisierung, schon grün: Import-Router = _deps_vertrieb (main.py).
        Grundlage dafür, den Knopf für die Halle auszublenden (Task P5.6)."""
        from app.api.deps import get_current_user
        from app.main import app

        async def halle():
            return {"id": TEST_USER_ID, "username": "halle", "roles": ["production_staff"]}

        app.dependency_overrides[get_current_user] = halle
        response = client.post(
            "/api/v1/imports/order_history",
            files={"file": ("bestellungen.xlsx", b"egal", XLSX_MIME)},
        )
        assert response.status_code == 403, response.text
```

`test_halle_darf_nicht_importieren` ist ein Charakterisierungstest (schon grün) und sichert die Grundlage für P5.6.

- [ ] **Step 2: Rot bestätigen**

Run: wie P5.2 Step 3.
Erwartet: **3 failed, 31 passed.** Rot: `test_created_by_und_audit_eintrag` (`assert None == '123e4567-…'`), `test_antwort_nennt_die_aufteilung_nach_status` (`KeyError: 'status_counts'`), `test_basic_auth_kennung_bricht_den_import_nicht` (`assert [] == [('IMPORT', 'gernot')]`).

- [ ] **Step 3: Import `CurrentUser`**

In `backend/app/api/v1/imports.py` suchen:

```python
from app.api.deps import DBSession
```

Ersetzen durch:

```python
from app.api.deps import CurrentUser, DBSession
```

Z. 33 (`from app.models.order import …`) **nicht** ändern, dort fügt Paket 1 eine Zeile ein. `OrderAuditLog` wird in Step 5 im Funktionsrumpf importiert.

- [ ] **Step 4: Bezeichnungen, `_benutzer_id`, `_import_hinweis`**

In `backend/app/api/v1/imports.py` suchen:

```python
# Status, die noch gepackt und geliefert werden (wie day-plan, production.py)
_OFFEN = (OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION)
```

Ersetzen durch:

```python
# Status, die noch gepackt und geliefert werden (wie day-plan, production.py)
_OFFEN = (OrderStatus.ENTWURF, OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION)
# Bezeichnungen für die Rückmeldung an die Oberfläche (IN_PRODUKTION = „Gepackt", A4)
_STATUS_TEXT = {
    OrderStatus.ENTWURF: "Entwurf",
    OrderStatus.BESTAETIGT: "Bestätigt",
    OrderStatus.IN_PRODUKTION: "Gepackt",
    OrderStatus.GELIEFERT: "Geliefert",
    OrderStatus.FAKTURIERT: "Fakturiert",
    OrderStatus.STORNIERT: "Storniert",
}


def _benutzer_id(user: Optional[dict]) -> Optional[UUID]:
    """User-ID als UUID — Basic-Auth-Kennungen ('basic-auth:<name>') sind keine,
    dann None (wie print_jobs._benutzer_id). UUID(user["id"]) wie in sales.py
    bräche den Import mit 400 "Import fehlgeschlagen: …" ab (import_entity)."""
    try:
        return UUID(user["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _import_hinweis(status_counts: dict[str, int]) -> Optional[str]:
    """Kurztext für den Toast: was ist als was angelegt worden."""
    if not status_counts:
        return None
    teile = [
        f"{status_counts[s.value]} {_STATUS_TEXT[s]}" for s in OrderStatus if s.value in status_counts
    ]
    text = "Angelegt: " + ", ".join(teile) + "."
    if status_counts.get(OrderStatus.GELIEFERT.value):
        text += (
            " Geliefert heißt: ohne Lieferschein und ohne Lagerabzug,"
            " der Sammellauf rechnet diese Bestellungen nicht ab."
        )
    return text
```

- [ ] **Step 5: `_lege_bestellung_an` mit Benutzer, Datei und Audit**

Kopf suchen:

```python
def _lege_bestellung_an(db, plan: dict, used_numbers: set[str], heute: date) -> Order:
    """Legt eine geprüfte Bestellung samt Positionen an (ohne Commit)."""
    from app.services.bestell_adressen import adressen_vom_kunden

    status = plan["status"]
```

Ersetzen durch:

```python
def _lege_bestellung_an(
    db, plan: dict, used_numbers: set[str], heute: date, *,
    user: Optional[dict] = None, dateiname: Optional[str] = None,
) -> Order:
    """Legt eine geprüfte Bestellung samt Positionen und Audit-Eintrag an (ohne Commit)."""
    from app.models.order import OrderAuditLog
    from app.services.bestell_adressen import adressen_vom_kunden

    benutzer_id = _benutzer_id(user)
    status = plan["status"]
```

Im `Order(...)`-Aufruf suchen:

```python
        status=status,
        currency="EUR",
        total_net=Decimal("0"),
```

Ersetzen durch:

```python
        status=status,
        created_by=benutzer_id,
        currency="EUR",
        total_net=Decimal("0"),
```

Ende der Funktion suchen:

```python
    order.calculate_totals()
    return order
```

Ersetzen durch:

```python
    order.calculate_totals()

    # Ein Eintrag je Bestellung: wer, aus welcher Datei, mit welchem Status.
    # Eigene Aktion IMPORT (bisher: UPDATE, CONFIRM, STATUS_CHANGE, …_LINE),
    # damit Importe von Hand angelegten Bestellungen unterscheidbar bleiben.
    db.add(OrderAuditLog(
        order_id=order.id,
        user_id=benutzer_id,
        user_name=(user or {}).get("username"),
        action="IMPORT",
        new_values={"status": status.value, "bestell_nr_extern": plan["ext_nr"], "datei": dateiname},
        reason="Bestell-Import",
    ))
    return order
```

- [ ] **Step 6: `_import_order_history` reicht Benutzer und Datei durch und zählt je Status**

Signatur suchen:

```python
def _import_order_history(db, rows: list[dict], *, parse_errors: Sequence[str] = ()) -> dict:
```

Ersetzen durch:

```python
def _import_order_history(
    db, rows: list[dict], *, parse_errors: Sequence[str] = (),
    user: Optional[dict] = None, dateiname: Optional[str] = None,
) -> dict:
```

Ende der Funktion suchen:

```python
    used_numbers: set[str] = set()
    for plan in geplant:
        _lege_bestellung_an(db, plan, used_numbers, heute)
    db.commit()
    return {"created": len(geplant), "updated": skipped, "errors": []}
```

Ersetzen durch:

```python
    used_numbers: set[str] = set()
    status_counts: dict[str, int] = {}
    for plan in geplant:
        _lege_bestellung_an(db, plan, used_numbers, heute, user=user, dateiname=dateiname)
        status_counts[plan["status"].value] = status_counts.get(plan["status"].value, 0) + 1
    db.commit()
    return {
        "created": len(geplant),
        "updated": skipped,
        "errors": [],
        "status_counts": status_counts,
        "hinweis": _import_hinweis(status_counts),
    }
```

- [ ] **Step 7: `import_entity` mit Benutzer**

In `backend/app/api/v1/imports.py` suchen:

```python
async def import_entity(entity: str, db: DBSession, file: UploadFile = File(...)):
```

Ersetzen durch:

```python
async def import_entity(entity: str, db: DBSession, user: CurrentUser, file: UploadFile = File(...)):
```

Dann suchen:

```python
            return _import_order_history(db, rows, parse_errors=parse_errors)
```

Ersetzen durch:

```python
            return _import_order_history(
                db, rows, parse_errors=parse_errors, user=user, dateiname=file.filename
            )
```

- [ ] **Step 8: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_import_bestellungen_zukunft.py tests/test_gernot_260821.py tests/test_import_chargen.py tests/test_warenfluss.py tests/test_phase4_verbesserungen.py tests/test_rollen.py -v -p no:cacheprovider`
Erwartet: 154 passed. Das sind alle Testdateien, die `/imports/` aufrufen, plus die Rollentests.

- [ ] **Step 9: Vollauf**

Run: Vollauf aus dem Rahmen. Erwartet (gemessen): 15 failed / 535 passed / 2 skipped / 1 error, Fehlernamen exakt wie die Baseline. Abweichende Anzahl „passed" ist kein Fehler, wenn andere Abschnitte vorher gemergt wurden, nur die Namen zählen.

- [ ] **Step 10: Commit**

```bash
git add backend/app/api/v1/imports.py backend/tests/test_import_bestellungen_zukunft.py
git commit -m "feat(import): Bestellimport mit created_by, Audit-Eintrag IMPORT und Aufteilung nach Status"
```

---

### Task P5.6: Oberfläche — Fehlerliste lesbar, Aufteilung im Toast, kein Import-Knopf für die Halle

**Files:**
- Modify: `frontend/src/components/common/ExcelImport.tsx:52-65` (`handleUpload`)
- Modify: `frontend/src/pages/Orders.tsx:13`, `:41`, `:198-203` (Stand `efcea00`; auf `feat/paket2-tagesplan-status` mit P1: `:14`, `:51`, `:229-234`)

**Interfaces:**
- Consumes: `hinweis` aus P5.5; `useAuth().user.roles` (`context/AuthContext.tsx:102`, Rollen klein wie im Token).
- Die Rollenliste `['admin', 'sales', 'production_planner', 'accounting']` entspricht `_deps_vertrieb` + Admin (`main.py:124`, `:788-792`). Gleiches Muster wie `App.tsx:34-37`.
- Der Toast nimmt `ReactNode` (`components/ui/Toast.tsx:10`, `:58`). Ohne `whitespace-pre-line` fallen die `\n` der Fehlerliste zu Leerzeichen zusammen (`.toast` in `index.css:527-529` setzt kein `white-space`). Standarddauer ist 5 s; Fehlerlisten bleiben 20 s, der Hinweis 15 s, Schließen per X bleibt.
- E2E `frontend/tests/e2e/import-upload.spec.ts` meldet sich als `anna@demo.novaerp.de` (admin) an und sieht den Knopf weiter. Im Dev-Modus (`VITE_AUTH_DISABLED=true`) hat `DEV_USER` alle Rollen (`context/AuthContext.tsx:24-30`).

- [ ] **Step 1: `ExcelImport.tsx` — Fehlerliste und Hinweis**

In `frontend/src/components/common/ExcelImport.tsx` suchen:

```tsx
      } catch (err: any) {
        toast.error(getErrorMessage(err, 'Import fehlgeschlagen'));
        return;
      }
      const created = data.created || 0;
      const updated = data.updated || 0;
      const errors: string[] = data.errors || [];
      const summary = `${created} angelegt · ${updated} ${secondaryLabel}${errors.length ? ` · ${errors.length} Fehler` : ''}`;
      if (errors.length) {
        toast.error(`${summary}\n${errors.slice(0, 3).join('\n')}${errors.length > 3 ? '\n…' : ''}`);
      } else {
        toast.success(summary);
      }
```

Ersetzen durch:

```tsx
      } catch (err: any) {
        // Der Bestell-Import lehnt eine fehlerhafte Datei als Ganzes ab und nennt
        // alle Fehler zeilenweise — die Liste muss lesbar und lange genug stehen.
        toast.error(
          <span className="whitespace-pre-line">{getErrorMessage(err, 'Import fehlgeschlagen')}</span>,
          20000
        );
        return;
      }
      const created = data.created || 0;
      const updated = data.updated || 0;
      const errors: string[] = data.errors || [];
      // Bestell-Import: was als Geliefert, was als Bestätigt angelegt wurde
      const hinweis: string | undefined = data.hinweis || undefined;
      const summary = `${created} angelegt · ${updated} ${secondaryLabel}${errors.length ? ` · ${errors.length} Fehler` : ''}`;
      if (errors.length) {
        toast.error(
          <span className="whitespace-pre-line">
            {`${summary}\n${errors.slice(0, 3).join('\n')}${errors.length > 3 ? '\n…' : ''}`}
          </span>,
          20000
        );
      } else if (hinweis) {
        toast.success(<span className="whitespace-pre-line">{`${summary}\n${hinweis}`}</span>, 15000);
      } else {
        toast.success(summary);
      }
```

- [ ] **Step 2: `Orders.tsx` — Import**

In `frontend/src/pages/Orders.tsx` suchen:

```tsx
import { ExcelImport } from '../components/common/ExcelImport';
```

Ersetzen durch:

```tsx
import { ExcelImport } from '../components/common/ExcelImport';
import { useAuth } from '../context/AuthContext';
```

- [ ] **Step 3: `Orders.tsx` — Rolle prüfen**

In `frontend/src/pages/Orders.tsx` suchen (erste Zeilen von `Orders()`, vor jedem frühen `return`):

```tsx
  const queryClient = useQueryClient();
```

Ersetzen durch:

```tsx
  const queryClient = useQueryClient();
  // Import nur für Rollen, die /imports schreiben dürfen (main.py: _deps_vertrieb).
  // Die Halle sieht die Bestellseite auch, bekäme beim Import aber 403.
  const { user } = useAuth();
  const darfImportieren = ['admin', 'sales', 'production_planner', 'accounting'].some((rolle) =>
    user?.roles?.includes(rolle)
  );
```

- [ ] **Step 4: `Orders.tsx` — Knopf nur mit Recht**

In `frontend/src/pages/Orders.tsx` suchen:

```tsx
            <ExcelImport
              entity="order_history"
              label="Bestellungen importieren"
              secondaryLabel="übersprungen"
              onImported={() => queryClient.invalidateQueries({ queryKey: ['orders'] })}
            />
```

Ersetzen durch:

```tsx
            {darfImportieren && (
              <ExcelImport
                entity="order_history"
                label="Bestellungen importieren"
                secondaryLabel="übersprungen"
                onImported={() => queryClient.invalidateQueries({ queryKey: ['orders'] })}
              />
            )}
```

- [ ] **Step 5: Typprüfung und Build**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe, Exit 0.

Run: `cd frontend && ./node_modules/.bin/vite build`
Erwartet: „✓ built in …", nur die bekannte Chunk-Größen-Warnung.

Run: `cd frontend && grep -n "onImported={() => queryClient.invalidateQueries({ queryKey: \['orders'\] })}" src/pages/Orders.tsx`
Erwartet: genau ein Treffer (die Zeile, auf die P1.8 im Schritt „Prüfen" per grep prüft).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/common/ExcelImport.tsx frontend/src/pages/Orders.tsx
git commit -m "fix(import): Fehlerliste lesbar, Aufteilung nach Status im Toast, kein Import-Knopf für die Halle"
```

---

### Abnahme

Fertig ist P5, wenn alle zutreffen:

1. `tests/test_import_bestellungen_zukunft.py`: 34 passed. Vollauf: dieselben 15 Fehlernamen + 1 Error wie die Baseline.
2. `tsc --noEmit` Exit 0, `vite build` ohne Fehler.
3. `git diff <Basis>..HEAD --stat` nennt genau: `backend/app/api/v1/imports.py`, `backend/app/services/bestell_adressen.py` (neu), `backend/tests/test_import_bestellungen_zukunft.py`, `frontend/src/components/common/ExcelImport.tsx`, `frontend/src/pages/Orders.tsx`.
4. `git diff <Basis>..HEAD -U0 -- backend/app/api/v1/imports.py | grep '^@@'`: Kein Hunk beginnt (alte Seite, Zahl nach `-`) zwischen 26 und 121 oder zwischen 262 und 489. Gemessen: Hunks bei 25, 122, 260, 490–665, 773–785. `git diff <Basis>..HEAD -- backend/app/api/v1/sales.py backend/app/models/order.py` ist leer.
5. Ein Upload mit einer fehlerhaften Zeile legt keine Bestellung an und nennt alle Fehler; derselbe Upload nach Korrektur legt alle Bestellungen mit allen Positionen an (P5.1).

**Abschlussmeldung des Workers:** Basis-Hash, die sechs Commit-Hashes, Rot/Grün je Task (Anzahlen), Vollauf-Fehlernamen, Ausgabe von Abnahme 3 und 4, jede selbst aufgelöste redaktionelle Unstimmigkeit.

**Nach dem Deploy (Manager, nicht der Worker):**
- Vorher WAL-sicheres Backup des Mandanten `minga` (Freigabe 5 der Spezifikation).
- Auf der Demo (`anna@demo.novaerp.de`, admin): Vorlage herunterladen, Hinweis im Blatt „Beispiel" lesen. Eine Datei mit einer Zeile ohne Preis hochladen → roter Toast mit „Import abgebrochen, keine Bestellung angelegt" und der Zeilennummer, keine neue Bestellung. Korrigiert hochladen → grüner Toast mit „Angelegt: …". Die Demo setzt sich um 03:30 zurück.
- Mit einem reinen `production_staff`-Login (sobald es einen gibt, B8): Bestellseite zeigt „Neue Bestellung", aber keinen Import-Knopf.
- Gernot vor dem nächsten Upload informieren: alles oder nichts, Bestelldatum nicht in der Zukunft, Einheit leer = Stück, „Gepackt" nicht importierbar, gültige Status-Werte stehen in der Vorlage.
- **Und ausdrücklich zum Altbestand:** Bereits importierte Bestellungen (gleiche `bestell_nr_extern`) überspringt der Import weiter, auch wenn sie unvollständig sind. Lädt Gernot die Originaldatei vom 08.10. erneut hoch und hat eine Zeile darin einen Lesefehler (z. B. fehlender Preis), lehnt P5 die ganze Datei mit 400 ab, obwohl alle übrigen Bestellungen schon existieren (`fehler = list(parse_errors)` steht vor dem Idempotenz-Sprung, P5.1). Korrigiert er die Zeile, läuft der Upload durch, die betroffene Bestellung wird aber übersprungen und bleibt ohne diese Position. Die 400-Meldung sagt das nicht. Solche Positionen von Hand in der Bestellung ergänzen, nicht per Re-Upload (T1, Risiko 4 und Lücke 10).

### Nicht in P5 (T1 Stufe A, bewusst offen gelassen oder für später)

- **Kreditlimit als Warnung** (T1: „nur Warnung"). Bräuchte die Summenrechnung aus `sales.py:833-863` und einen Warnungskanal; die Rechnung ändert sich mit Paket 1 (Steuersatz). Nach Paket 1 als eigener kleiner Task.
- **Warnungen** für GELIEFERT mit Lieferdatum heute, offene Bestellungen in der Vergangenheit und unbekannte Einheiten (T1 3.1, 3.3). P5 liefert stattdessen `status_counts` und `hinweis`. Eine Einheitenliste müsste Formularwerte (`CreateOrderModal.tsx:412-424`) und `units_of_measure` zusammenführen.
- **Leere Preisspalte → Kundenpreis/Basispreis** (T1 1.3, „optional"): Der Preis bleibt Pflichtspalte.
- **Kopfdaten innerhalb einer Bestellung:** Kunde, Bestell-, Lieferdatum und Status liest der Import nur aus der ersten Zeile einer `bestell_nr_extern` (`_pruefe_bestellung`, `head = zeilen[0]`, wie `imports.py:546-555` in `efcea00`). Abweichende Werte in Folgezeilen werden weiter still ignoriert. Nicht in T1, am Code belegt; Vorschlag: als Fehler melden.
- **`create_order` auf `adressen_vom_kunden` umstellen**, sobald Paket 1 und P1 gemergt sind (beide ändern `sales.py`).
- **Ein „heute" für alle:** `imports._today_berlin()`, P1 `order_status_service.heute_berlin()`, P4 `subscription_tasks.liefertag_heute()` zusammenführen.
- **Weitere Doppelungen mit P1-Code** (auf dem Branch vorhanden, P5 bleibt bewusst unabhängig davon): `imports._benutzer_id` ↔ `order_status_service.user_uuid` (Z. 79–84), `imports._STATUS_TEXT` ↔ `order_status_service.STATUS_BEZEICHNUNG` (Z. 44–51, gleiche Texte, `IN_PRODUKTION` = „Gepackt"). Nach dem Merge auf die P1-Helfer umstellen, zusammen mit „heute".
- **Gleiche 403-Falle auf der Saatgut-Seite:** Die Halle (`production_staff`) sieht „Saatgut" (`Layout.tsx:89-92`, Rollen inkl. `PRODUCTION_STAFF`) mit Import-Knopf (`Seeds.tsx:78`), der ganze Import-Router hängt aber an `_deps_vertrieb` (`main.py:788-792`) → 403. P5 blendet auftragsgemäß nur den Bestell-Import aus. Gehört in den B8-Kern von Paket 3 oder einen kleinen Folgetask.
- **Steuersatz der Importposition** über `steuersatz.steuersatz_der_position` (Paket 1 S1.1), analog P4.5.
- **Modul-Docstring** `imports.py:1-8` nennt `order_history` und `grow_batches` nicht (T1 3.2); außerhalb der für P5 freigegebenen Stellen.
- **Stufe B** (Vorschau, `ImportRun`, Rückgängig, `external_order_number`) und **Stufe C** (`bulk-status`, macht P1.3). Ob Stufe B nötig ist, hängt an Offenem Punkt 5.
- **Altbestand:** P5 korrigiert keine bereits importierten Bestellungen (Einheit `g`, fehlende Adressen, fehlendes Audit, durch Teilimport fehlende Positionen). Ein Re-Upload repariert sie nicht (siehe „Nach dem Deploy", Altbestand). Nachkorrekturen nur einzeln vorgelegt und per API (T1 3.4).

**Offene Punkte:** fuer Gernot.

1. **Einheit:** Wo die Spalte „einheit" leer ist, legt der Import künftig „Stück" an, wie das Bestellformular. War in Ihrer Datei Stück/Schale gemeint oder Gramm? Sollen die schon importierten Positionen mit „g" auf Stück umgestellt werden (Prüfabfrage T1 3.4 Nr. 4)?
2. **Bestelldatum in der Zukunft** wird künftig abgelehnt. Für Fruchthof Nagel ist der 11.10. als Bestelldatum eingespielt und steht so auf AB und Lieferschein. War das gewollt oder ein Versehen in der Datei?
3. **„Gepackt" im Import:** Eine noch nicht gelieferte Bestellung mit Status `IN_PRODUKTION`/„Gepackt" wird abgelehnt, gepackt wird im Tagesplan. Brauchen Sie den Fall trotzdem?
4. **Variable Bundles (Gastrotray):** Offene Bestellungen ab heute brauchen in der Spalte `bundle_selections` die gewählten Sorten, sonst wird die Datei abgelehnt. Kann Ihr Altsystem die Sortenauswahl mitliefern?
5. **Einmalig oder regelmäßig:** War der Import eine Übernahme zum Go-Live, oder kommen regelmäßig Bestellungen per Datei? Davon hängt ab, ob Vorschau und „Rückgängig" (Stufe B) sich lohnen. Sollen Mitarbeiter-Logins importieren dürfen? Heute bleibt das bei Vertrieb, Buchhaltung, Planung und Admin, der Knopf ist für die Halle ausgeblendet.
6. **Alles oder nichts:** Eine fehlerhafte Zeile verhindert jetzt den ganzen Upload, dafür nennt die Meldung alle Fehler auf einmal. Passt das für Ihre Arbeitsweise, oder sollen fehlerfreie Bestellungen trotzdem angelegt werden? Wichtig: Schon importierte Bestellungen werden beim erneuten Hochladen übersprungen, auch wenn ihnen eine Position fehlt. Fehlende Positionen bitte direkt in der Bestellung ergänzen, nicht über einen neuen Upload.
7. **`bestell_nr_extern`:** Ist das Ihre alte Auftragsnummer oder die Bestellnummer des Kunden? Sie steht als „Auftragsnummer" auf AB und Lieferschein und dient zugleich als Schutz gegen doppelten Import.

## Abschluss — Task 23 (Worker) und Task 24 (nach dem Merge von Paket 1)

### Task 23: Testdatei komplett, Schluss-Vollauf, Frontend-Build, Abschlussmeldung

> **Manager-Nachtrag 08.10.2026 — zuerst ausführen:** Vor Step 1 dieses Tasks die Tasks P5.1 bis P5.6 aus dem Abschnitt P5 (direkt über „Abschluss“) vollständig in dieser Reihenfolge ausführen, je Task ein Commit wie dort angegeben. P5-Tests gehören nach `backend/tests/test_import_bestellungen_zukunft.py` (am Dateiende anhängen). Erst danach Task 23; der Schluss-Vollauf deckt P5 mit ab, verglichen werden nur Fehlernamen. Die Testzahl für `test_gernot_261008_paket2.py` in Step 1 bleibt unverändert.


**Files:** keine Änderungen (außer Korrekturen, falls ein Schritt scheitert — dann stoppen und melden, nicht still reparieren).

Die Testdatei mit allen vier Abschnitten zusammen ist **vor diesem Plan nie gelaufen** (Prüfstand). Step 1 ist deshalb die erste echte Probe des Zusammenspiels.

- [ ] **Step 1: Ganze Paket-2-Testdatei**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -q`
Erwartet: **0 failed, 86 passed** (Tasks 1–5: 39, Tasks 10–12: 18, Tasks 16–17: 8, Tasks 19–22: 21). Jeder rote Test: stoppen und mit Ausgabe melden.

- [ ] **Step 2: Nachbardateien**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_bugfixes.py tests/test_gernot_260824.py tests/test_gernot_260821.py tests/test_gernot_260917.py tests/test_phase4_verbesserungen.py tests/test_rollen.py tests/test_import_bestellungen_zukunft.py tests/test_features.py tests/test_dunning.py tests/test_production_readiness.py -q -rfE 2>&1 | tail -15`
Erwartet: nur Baseline-Namen — `test_features.py::TestFeatures::test_subscription_processing` und aus `test_production_readiness.py` `test_dunning_level1/2/3`, `test_quality_auto_approved`, `test_quality_rejected_high_loss`, `test_quality_rejected_low_note`.

- [ ] **Step 3: Schluss-Vollauf (Prozedur V, ohne `REDIS_URL`)**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE 2>&1 | tail -30` (ca. 19 min)
Erwartet: Fehlschläge exakt die 15 Altlasten plus ERROR `test_production_automation.py::test_approve_suggestion_creates_grow_batch`. Jeder andere Name ist eine Regression: stoppen und mit Ausgabe melden. Ausnahme mit bekannter Ursache: Liegt Paket 1 schon auf dem Branch und scheitert `test_gernot_261008.py::TestS6SammellaufRechnetJedeBestellungEinmal::test_quittierter_lieferschein_vertritt_die_bestellung` mit 400 „Entwurf → Geliefert", Task 2 Step 5 nachholen — nicht den Status-Code des Tests ändern.

- [ ] **Step 4: Frontend**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
Run: `cd frontend && ./node_modules/.bin/vite build --outDir /tmp/novaerp-paket2-build --emptyOutDir` → endet mit `✓ built in …` (Ausgabe außerhalb des Repos; die Chunk-Größen-Warnung ist bekannt).

- [ ] **Step 5: Rückstände**

Run: `cd frontend && grep -rn "In Produktion" src/pages src/components | grep -v "In Produktion ab"` → keine Ausgabe.
Run: `cd frontend && grep -rn '\.status}' src/pages src/components | grep -v 'status={' | grep -v KanbanBoard.tsx` → keine Ausgabe.
Run: `git grep -n "process_daily_subscriptions" -- backend/app/api` → keine Ausgabe.
Run: `git grep -n -e generate_recurring_invoices -e recurring_invoices -- backend/app frontend/src` → keine Ausgabe.

- [ ] **Step 6: Umfang**

Run: `git diff --stat <Basis>..HEAD` (`<Basis>` aus der Vorbereitung wörtlich einsetzen)
Erwartet: genau die Dateien der File Structure — `backend/app/services/order_status_service.py`, `backend/app/api/v1/sales.py`, `backend/app/schemas/order.py`, `backend/app/api/v1/documents.py`, `backend/app/api/v1/production.py`, `backend/app/api/v1/forecasting.py`, `backend/app/models/invoice.py`, `backend/app/api/v1/invoices.py`, `backend/app/tasks/subscription_tasks.py`, `backend/app/tasks/invoice_tasks.py`, `backend/tests/test_gernot_261008_paket2.py`, `backend/tests/test_gernot_bugfixes.py`, `backend/tests/test_gernot_260817.py`, `frontend/src/components/ui/statusLabels.ts`, `frontend/src/components/ui/Badge.tsx`, `frontend/src/components/ui/index.ts`, `frontend/src/services/orderQueries.ts`, `frontend/src/services/api.ts`, `frontend/src/types/index.ts`, `frontend/src/pages/Tagesplan.tsx`, `frontend/src/pages/Orders.tsx`, `frontend/src/components/domain/OrderCard.tsx`, `frontend/src/pages/Sales.tsx`, `frontend/src/components/domain/EditOrderModal.tsx`, `frontend/src/components/domain/OrderDocumentsModal.tsx`, `frontend/src/pages/Production.tsx`, `frontend/src/pages/Forecasting.tsx`, `frontend/src/pages/Invoices.tsx`, `frontend/src/pages/Dashboard.tsx` (29 Dateien); `backend/tests/test_gernot_261008.py` nur, wenn Task 2 Step 5 einen Treffer hatte. **Nicht** darunter: `backend/app/tenancy.py`, `backend/app/models/order.py`, `backend/app/services/invoice_service.py`, `backend/app/api/v1/imports.py`, `frontend/src/main.tsx`, `frontend/node_modules`.
Run: `git log --oneline <Basis>..HEAD` → je Task ein Commit (Tasks 1–22), Task 23 ohne Commit.

- [ ] **Step 7: Abschlussmeldung (Worker → Manager)**

Kurz: Commits (`git log --oneline <Basis>..HEAD`), Testergebnis (Step 1, Fehlerliste aus Step 3), Ergebnis von Task 2 Step 5 (Treffer ja/nein), Status von Task 24 (ausgeführt oder offen mit Grund), jede selbst aufgelöste redaktionelle Abweichung vom Plan. Keine Rohdumps.

---

### Task 24: Steuersatz der Abo-Position über die Regel aus Paket 1 (erst nach dem Merge von Paket-1-Task 1)

**Vorbedingung:** Paket-1-Task 1 (`backend/app/services/steuersatz.py`) liegt auf dem Branch. Stand 08.10.: auf `feat/paket1-steuer-rechnung` als `7fd1ef8` committet, auf dem Paket-2-Branch noch nicht — im Normalfall bleibt dieser Task bis zum Merge offen. Prüfen:

```bash
grep -n "def steuersatz_der_position" backend/app/services/steuersatz.py
```

Kein Treffer: Task **nicht** ausführen, als offen melden. Nichts selbst nachbauen.

**Files:**
- Modify: `backend/app/tasks/subscription_tasks.py` (Import, `abo_position`)

**Interfaces:**
- Consumes: `app.services.steuersatz.steuersatz_der_position(db, product_id, product_variant_id, client_satz) -> TaxRate` (Paket-1-Task 1; Signatur am 08.10. auf dem Paket-1-Branch geprüft).
- Produces: keine neue Schnittstelle. Verhalten unverändert, solange Paket 1 für Positionen mit Produkt den Produktstamm liefert.

- [ ] **Step 1: Absicherung vorher grün**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -k TestP4 -q`. Erwartet: alle P4-Tests grün (21 passed). Kein neuer Test: `test_produkt_abo_bekommt_produkt_preis_satz_und_einheit` (Produkt auf `STANDARD`, Köder auf `REDUZIERT`) sichert den Satz bereits ab.

- [ ] **Step 2: Import**

Unter `from app.services.pricing_service import resolve_unit_price` einfügen:

```python
from app.services.steuersatz import steuersatz_der_position
```

- [ ] **Step 3: Satz in `abo_position`**

```python
        tax_rate=produkt.tax_rate or TaxRate.REDUZIERT,
```

ersetzen durch

```python
        # Dieselbe Regel wie jede Bestellposition mit Produkt (steuersatz.py).
        tax_rate=steuersatz_der_position(
            db, produkt.id, variante.id if variante is not None else None, None
        ),
```

Der Import `TaxRate` in der Kopfzeile `from app.models.order import …` darf bleiben.

- [ ] **Step 4: Grün und Vollauf**

Run: P4-Datei und `tests/test_gernot_261008.py` (Paket 1) → grün bzw. wie in Paket 1 beschrieben. Danach Vollauf; als Vergleich dient die Fehlerliste von `main` **nach** dem Paket-1-Merge (Paket 1 entfernt Altlasten: laut Paket-1-Plan wird `test_services.py::TestInvoiceService::test_invoice_totals_update` mit Paket-1-Task 9 grün).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/subscription_tasks.py
git commit -m "refactor(abo): Steuersatz der Abo-Position über die gemeinsame Regel aus steuersatz.py"
```

---

## Abnahme

Fertig ist der Plan, wenn alle zutreffen:

1. `tests/test_gernot_261008_paket2.py`: 0 failed, 86 passed (Task 23 Step 1). Schluss-Vollauf ohne `REDIS_URL`: dieselben 15 Fehlernamen plus 1 Error wie die Baseline, kein neuer Name (Task 23 Step 3).
2. `tsc --noEmit -p .` ohne Ausgabe, `vite build` endet mit `✓ built` (Task 23 Step 4); die Rückstandsprüfungen aus Task 23 Step 5 liefern nichts.
3. `git diff --stat <Basis>..HEAD` umfasst genau die 29 Dateien aus Task 23 Step 6 (plus `test_gernot_261008.py` nur bei Treffer in Task 2 Step 5).
4. **Statusregel (API):** BESTAETIGT → GELIEFERT gibt 200 mit `actual_delivery_date` = Berliner Kalendertag; ENTWURF → GELIEFERT gibt auf allen drei Wegen 400, der Text nennt „Entwurf", nichts wird geändert; IN_PRODUKTION → STORNIERT gibt 200 und lässt den Fertigwarenbestand unverändert; jeder Wechsel schreibt genau einen Audit-Eintrag mit `user_id`; scheitert der Bestandsabzug, bleibt alles unverändert (500).
5. **Quittieren:** setzt eine bestätigte oder gepackte Bestellung über `setze_status` auf GELIEFERT (Audit `LIEFERSCHEIN_QUITTIERT`); bei einer schon gelieferten Bestellung ohne Lieferdatum nur `LIEFERDATUM_NACHGETRAGEN`, kein zweiter Bestandsabzug; ein Lieferdatum in der Zukunft gibt 400.
6. **Sammel-Endpunkt:** `POST /sales/orders/bulk-status` ändert alle oder keine; leere Auswahl 422; Antwort `list[BulkStatusResult]`.
7. **Tagesplan:** GELIEFERT und FAKTURIERT bleiben am Liefertag in `ausliefern`; gepackte, gelieferte und fakturierte Bestellungen des Packtags stehen in `verpacken_erledigt`, nie in `verpacken`; `packbar` ist nur bei BESTAETIGT `true`; `status` ist überall der Enum-Wert. `test_gernot_260817.py:187-206` unverändert grün.
8. **Packplan:** `komponenten` und `items` zählen nur ENTWURF und BESTAETIGT; `gepackt` nennt die gepackten Bestellungen des Packtags.
9. **Rechnungen:** `customer_name` und `customer_number` sind in Liste, Detail und „Überfällig" gefüllt; beide Listen brauchen bei 1 und 4 Rechnungen gleich viele SELECTs.
10. **Abos:** Ein Produkt-Abo ergibt eine Position mit `product_id`, Produktname, Kundenpreis und Produktsatz; ein Abo ohne eindeutiges Produkt, auf ein deaktiviertes Produkt oder ein variables Bundle erzeugt nichts und steht in der Rückmeldung; Mo + Do liefert an beiden Tagen, auch bei Start an einem Mittwoch; zweimal „Heute verarbeiten" am selben Tag ergibt eine Bestellung je Abo; `process_today_subscriptions` nimmt `DBSession`; `generate_recurring_invoices` existiert nicht mehr.
11. Task 24 ist ausgeführt oder ausdrücklich als offen gemeldet (Vorbedingung nicht erfüllt).

**Abnahme im Browser (Manager, Revision Gate, nicht Teil des Workers).** Backend und Frontend lokal aus dem Worktree starten, Testdaten über die Oberfläche anlegen:

1. Tagesplan heute, bestätigte Same-Day-Bestellung → „Ausgeliefert" → Toast, die Zeile bleibt in „Ausliefern" mit grünem „Geliefert" und ohne Knopf; in „Verpacken" fehlt sie und steht unter „Bereits gepackt". Tagesplan von gestern mit einer bestätigten Bestellung von gestern → „Ausgeliefert" → im Audit-Log das Datum von gestern (Review Focus 5).
2. Tagesplan heute, Bestellung für morgen bestätigt, zweite als Entwurf: bestätigte zeigt „Bestätigt" (blau) und „Gepackt", der Entwurf „Entwurf" (grau) und „erst bestätigen". Klick auf „Gepackt" → Toast „BE-… als gepackt markiert", Zeile wandert unter „Bereits gepackt", Sortenbedarf zeigt „ohne 1 bereits gepackte" mit der kleineren Menge; im Tagesplan für morgen steht sie unter „Ausliefern" als „Gepackt" (gelb).
3. Schneller Doppelklick auf „Gepackt" im Tagesplan und auf „Gepackt" in der Bestellkarte → kein Fehler-Toast, je Bestellung genau ein Audit-Eintrag `IN_PRODUKTION`; „Geliefert" rückt nicht an die Stelle von „Gepackt" (Review Focus 1).
4. Bestellliste: zwei Bestätigte und ein Entwurf markieren → Sammelleiste „Geliefert" → „2 von 3 Bestellung(en) auf „Geliefert" gesetzt" und eine Warnung mit der Entwurfsnummer.
5. Gepackte Bestellung → „Bearbeiten" → Abschnitt „Stornieren" vorhanden und wirksam; „Position hinzufügen" fehlt; danach fehlt die Bestellung im Tagesplan unter „Ausliefern" und „Bereits gepackt" (Review Focus 3).
6. Belege: Lieferschein einer offenen Bestellung mit Liefertag gestern → Feld „Liefertag" zeigt gestern; Lieferschein einer schon gelieferten Bestellung → Feld zeigt deren Lieferdatum; Lieferschein einer Entwurfs-Bestellung → Hinweis „Erst die Bestellung bestätigen …", kein Knopf (Review Focus 4).
7. Zwei Browserfenster mit dem Tagesplan: im ersten „Gepackt" → das zweite zeigt den neuen Stand nach spätestens 60 s ohne Neuladen; im zweiten vorher noch „Gepackt" auf dieselbe Bestellung → Fehler-Toast „Statuswechsel nicht möglich: Gepackt → Gepackt", danach neuer Stand (Review Focus 2).
8. Dashboard „Offene Bestellungen" vor und nach „Gepackt" gleich; Produktion → Verpackungsplan (heute) zeigt „Bereits gepackt: …".
9. Prognose-Seite: Warnungen zeigen „Kapazität"/„Unterdeckung", Tooltip mit dem vollen Text; nirgends ein Enum-Wert in Bestell-, Beleg- oder Aussaat-Badges.
10. Rechnungen: Spalte „Kunde" gefüllt, Detail-Modal zeigt den Kunden, Suche nach einem Kundennamen findet dessen Rechnung (im Reiter „Alle").
11. Abonnements → „Heute verarbeiten" zweimal → zweite Meldung „0 Abo-Bestellungen angelegt. N schon vorhanden." (bei übersprungenen Abos mit Grund).

---

## Runbooks (Manager, kein Worker-Task)

Grundsätze (Spec, Entscheidung 5 vom 08.10.): Geprüfte Pakete werden direkt deployt — vorher WAL-sicheres Backup des Mandanten, danach Live-Prüfung. **Korrekturen an Produktionsdaten (LfA-Entwürfe, Nachquittieren) einzeln vorlegen und freigeben lassen.** Zugang laut Betriebsnotiz: `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 root@49.12.191.103`; Container-Name vor **jedem** `docker exec` neu holen: `C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)`. Im Container gibt es kein `sqlite3`-Binary; Mandanten-DB `/data/tenants/minga.db`, Arbeitsverzeichnis `/app`.

### Runbook A: Vor dem Deploy (lesend)

**A1 — Altbestand auf IN_PRODUKTION.** A4.md, Punkt 8: Wer `IN_PRODUKTION` bisher als „in Arbeit/wächst" gesetzt hat, verliert diese Bestellungen nach dem Deploy aus dem Sortenbedarf; dann würde zu wenig gepackt. Dasselbe gilt für Bestellungen, die mit Status-Spalte `IN_PRODUKTION` importiert wurden (`imports.py:122`, `:555-575`, auch mit Lieferdatum in der Zukunft). Lesend prüfen:

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)
docker exec -i "$C" python3 -c "
import sqlite3
con = sqlite3.connect('file:/data/tenants/minga.db?mode=ro', uri=True)
for r in con.execute('''SELECT order_number, requested_delivery_date, packing_date, customer_reference, updated_at
                        FROM orders WHERE status = 'IN_PRODUKTION' ORDER BY requested_delivery_date'''):
    print(r)
"
```

Erwartet: keine Zeile mit `requested_delivery_date` ab heute. Laut A4.md gingen die fünf gemeldeten Bestellungen in derselben Sekunde über `IN_PRODUKTION` nach `GELIEFERT`. Gibt es solche Zeilen doch, vor dem Deploy Gernot fragen (Offener Punkt O9). Eine Korrektur nach `BESTAETIGT` gibt es als Übergang nicht. `customer_reference` gesetzt heißt: Die Bestellung kam aus dem Import. Bis die Import-Härtung steht (Entscheidung E2), Gernot bitten, in der Importvorlage kein `IN_PRODUKTION` zu verwenden.

**A2 — LfA-Prüfabfrage R1–R6** aus Runbook B, Schritt 1, ist rein lesend und kann sofort laufen.

**A3 — Backup** wie Runbook B, Schritt 6 (SQLite-Backup-API, Ziel `/root/backups/minga-vor-deploy-paket2-<Zeitstempel>.db`), unmittelbar vor dem Deploy.

### Runbook B: LfA-Entwürfe und Abo-Lauf (A5)

**Ausführung: Manager, nicht der Codex-Worker** (die Sandbox hat kein Netzwerk). **Kein Code im Repo.** Die Skripte liegen nur im Runbook und werden per `docker exec -i` eingespeist. Schritt 1 ist rein lesend und kann **sofort** laufen, vor jedem Deploy. Geschrieben wird nur in Schritt 7, und nur mit Gernots Antwort und ausdrücklicher Freigabe.

**Warum die Korrektur GoBD-unkritisch ist:** Eine Bestellung im Status `ENTWURF` ist kein Buchungsbeleg (§ 147 Abs. 1 Nr. 4 AO) und, solange nichts an den Kunden ging, kein Handelsbrief (§ 257 Abs. 1 Nr. 2, 3 HGB; § 147 Abs. 1 Nr. 2, 3 AO). Die vier Entwürfe sind systemintern entstanden. Für Entwürfe ist zu erwarten, dass keine Auftragsbestätigung, kein Lieferschein, keine Rechnung und keine Lagerbewegung existiert; Schritt 1 (R3) belegt das je Bestellung, bevor korrigiert wird. Trotzdem bleibt der Ursprungsinhalt feststellbar (Gedanke des § 146 Abs. 4 AO): Je Bestellung schreibt das Skript einen `order_audit_logs`-Eintrag (`UPDATE_LINE`) mit allen alten und neuen Werten. **Kritisch wäre** eine Änderung, sobald ein Beleg existiert: eine versandte Auftragsbestätigung, ein Lieferschein oder eine Rechnung. Ihr Inhalt muss so bleiben, wie er rausging; Rechnungs-PDFs werden bei jedem Abruf neu aus der DB erzeugt (`invoices.py:466-500`). Das Korrekturskript bricht in diesen Fällen ab, ohne zu schreiben. Solche Fälle laufen über Storno und Neuanlage.

- [ ] **Schritt 1: Lesende Prüfabfrage R1–R6 (sofort möglich)**

Auf dem Host das Skript als `/root/p4_pruefung.py` ablegen und ausführen:

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)
cat > /root/p4_pruefung.py <<'PY'
import sqlite3, sys
db = sys.argv[1]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

def zeige(titel, sql, *args):
    rows = con.execute(sql, args).fetchall()
    print(f"\n## {titel} ({len(rows)} Zeilen)")
    if rows:
        print(" | ".join(rows[0].keys()))
        for r in rows:
            print(" | ".join("" if v is None else str(v) for v in r))

# Abo-Bestellungen: _create_order_from_subscription schreibt
# notes = 'Automatisch erstellt aus Abo <uuid mit Bindestrichen>' und
# internal_notes = 'Subscription Run'. IDs liegen als 32 Hex-Zeichen ohne Bindestriche.
ABO_ID = "REPLACE(SUBSTR(o.notes, INSTR(o.notes, 'Abo ') + 4, 36), '-', '')"

zeige("R1 Alle Abos", """
SELECT s.id AS abo_id, c.name AS kunde, s.aktiv, s.intervall, s.liefertage,
       s.gueltig_von, s.gueltig_bis, s.menge, s.einheit,
       p.sku, p.name AS produkt, p.base_price, p.tax_rate, p.is_active AS produkt_aktiv,
       p.is_bundle, p.is_variable_bundle,
       s.product_variant_id, s.seed_id, c.price_list_id
FROM subscriptions s
JOIN customers c ON c.id = s.kunde_id
LEFT JOIN products p ON p.id = s.product_id
ORDER BY c.name, s.gueltig_von
""")

zeige("R2 Alle Bestellungen aus dem Abo-Lauf mit Positionen", f"""
SELECT o.order_number, o.requested_delivery_date, o.created_at, o.status, c.name AS kunde,
       o.total_net, o.total_vat, o.total_gross, {ABO_ID} AS abo_id,
       l.position, l.beschreibung, l.product_id, l.quantity, l.unit, l.unit_price,
       l.tax_rate, l.line_net
FROM orders o
JOIN customers c ON c.id = o.customer_id
LEFT JOIN order_lines l ON l.order_id = o.id
WHERE o.internal_notes = 'Subscription Run' OR o.notes LIKE 'Automatisch erstellt aus Abo %'
ORDER BY o.requested_delivery_date, o.order_number, l.position
""")

zeige("R3 Belege, Lagerbewegungen und Protokoll zu diesen Bestellungen", f"""
SELECT o.order_number, o.status,
       (SELECT COUNT(*) FROM order_confirmations x WHERE x.order_id = o.id) AS auftragsbestaetigungen,
       (SELECT COUNT(*) FROM order_confirmations x WHERE x.order_id = o.id AND x.sent_at IS NOT NULL) AS ab_versendet,
       (SELECT COUNT(*) FROM delivery_notes d WHERE d.order_id = o.id) AS lieferscheine,
       (SELECT COUNT(*) FROM invoices i WHERE i.order_id = o.id) AS rechnungen,
       (SELECT COUNT(*) FROM inventory_movements m WHERE m.order_id = o.id) AS lagerbewegungen,
       (SELECT COUNT(*) FROM order_audit_logs a WHERE a.order_id = o.id) AS protokolleintraege,
       o.inventory_deducted_at, o.actual_delivery_date, o.invoice_id
FROM orders o
WHERE o.internal_notes = 'Subscription Run' OR o.notes LIKE 'Automatisch erstellt aus Abo %'
ORDER BY o.requested_delivery_date
""")

zeige("R4 Woher die 2,00 EUR kamen: erste Produkte ohne Sorte (so griff der alte Lauf)", """
SELECT rowid, sku, name, base_price, tax_rate, category, is_active
FROM products WHERE seed_id IS NULL ORDER BY rowid LIMIT 3
""")

zeige("R5 Sonderpreise der Abo-Kunden auf ihre Abo-Produkte", """
SELECT c.name AS kunde, p.sku, p.name AS produkt, cp.unit_price, cp.valid_from, cp.valid_until
FROM subscriptions s
JOIN customers c ON c.id = s.kunde_id
JOIN customer_prices cp ON cp.customer_id = s.kunde_id AND cp.product_id = s.product_id
JOIN products p ON p.id = s.product_id
ORDER BY c.name, cp.valid_from
""")

zeige("R6 Aktive Abos, aus denen nie eine Bestellung entstand (starten nach dem Fix)", f"""
SELECT c.name AS kunde, s.intervall, s.liefertage, s.gueltig_von, s.gueltig_bis,
       s.menge, s.einheit, p.name AS produkt
FROM subscriptions s
JOIN customers c ON c.id = s.kunde_id
LEFT JOIN products p ON p.id = s.product_id
WHERE s.aktiv = 1
  AND NOT EXISTS (SELECT 1 FROM orders o
                   WHERE o.notes LIKE 'Automatisch erstellt aus Abo %'
                     AND {ABO_ID} = s.id)
ORDER BY c.name
""")
PY
docker exec -i "$C" python - /data/tenants/minga.db < /root/p4_pruefung.py
```

Die Verbindung ist `mode=ro` und kann nichts schreiben. Die Ausgabe vollständig zur Akte nehmen.

| Abfrage | Zeigt | Erwartung / Handlung |
|---|---|---|
| R1 | alle Abos mit Kunde, Intervall, Liefertagen, Gültigkeit, Menge, Einheit, Produkt (mit `produkt_aktiv`, `is_bundle`, `is_variable_bundle`), Variante, Sorte | LfA-Abo identifizieren: `product_id` gesetzt, `seed_id` leer (Spec). Liefertage notieren. Bei mehreren Liefertagen (z. B. `[0, 3]`) hat der alte Lauf nur die Montage angelegt; die übrigen Liefertage fehlen als Bestellung (Offener Punkt O16). **Einheit notieren:** Steht dort `KISTE_6` oder `KISTE_12` und keine Variante, rechnet der reparierte Lauf Produktpreis × Menge (keine Umrechnung, wie `create_order`). Ist `base_price` ein Stückpreis, liegt der Preis um den Faktor 6 bzw. 12 daneben (O16). Abos mit `produkt_aktiv = 0` oder `is_variable_bundle = 1` überspringt der reparierte Lauf. |
| R2 | alle Bestellungen aus dem Abo-Lauf mit Positionen und Anlagezeitpunkt (`created_at`, UTC) | Die vier LfA-Entwürfe 14.09./21.09./28.09./05.10., je eine Position `Abo-Lieferung: Unknown`, `product_id` leer, Preis 2,00. Weitere Treffer melden. Der 05:00-Lauf legt um 03:00 bzw. 04:00 UTC an; eine Abo-Bestellung zu anderer Uhrzeit stammt vom Knopf, und das ging nur bei `DEFAULT_TENANT_SLUG=minga` (Schritt 4). Läuft P4 erst nach Montag, 12.10., 05:00 live, kommt ein fünfter Entwurf `BE-20261012-…` dazu. Ihn behandeln die Schritte unten genauso, sie suchen nach Muster und nicht nach Datum. |
| R3 | Belege, Lagerbewegungen, Protokoll je Abo-Bestellung | Alle Zähler 0, `inventory_deducted_at`/`actual_delivery_date`/`invoice_id` leer. Sonst ist die Bestellung kein reiner Entwurf mehr: **nicht** korrigieren, melden, Weg „Storno + Neuanlage“. |
| R4 | die ersten Produkte ohne Sorte in Tabellenreihenfolge | Erklärt die 2,00 € und den Satz: das erste Produkt entspricht vermutlich dem, das der alte Lauf griff (`.first()` ohne `ORDER BY`). Nur zur Erklärung, die Korrektur hängt nicht davon ab. |
| R5 | Sonderpreise der Abo-Kunden auf ihre Abo-Produkte | Daraus ergibt sich der richtige Preis je Liefertag (Gültigkeit beachten). |
| R6 | aktive Abos, aus denen nie eine Bestellung entstand | Diese Abos **starten nach dem Deploy**, Fälligkeitsfall (b). Liste an Gernot (O17). |

- [ ] **Schritt 2: Mit Gernot klären (vor jeder Korrektur)**

Ihm R1, R2, R5, R6 vorlegen und je LfA-Entwurf eine von drei Antworten einholen:

- **A — geliefert, nicht berechnet:** Korrektur in Schritt 7. Die Bestellung bleibt mit ihrer Nummer (`BE-20260914-…` usw.) bestehen. Danach läuft sie durch den normalen Ablauf (bestätigen, liefern, Rechnung), Rechnung erst mit Paket 1 live.
- **B — nicht geliefert:** in der Oberfläche stornieren (Schritt 8).
- **C — geliefert und außerhalb des Systems berechnet:** stornieren (Schritt 8), im Grund die externe Rechnungsnummer nennen. Sonst würde später doppelt berechnet.

Außerdem: Menge, Produkt und **Einheit** aus R1 bestätigen lassen. Das Skript übernimmt die **Menge des Entwurfs**, deren **Einheit** (außer bei einer Variante) und das **aktuelle Abo-Produkt** mit dessen Preis je Einheit. Ausdrücklich fragen: Ist der Preis des Abo-Produkts (bzw. sein Sonderpreis aus R5) der Preis für **eine** Einheit des Abos (z. B. eine Kiste)? Wenn nein, vor Schritt 7 das Abo neu anlegen (mit Variante oder passender Einheit) bzw. den Preis klären; sonst stimmt die Korrektur um den Faktor 6 bzw. 12 nicht.

- [ ] **Schritt 3: Montag, 12.10.2026, 05:00**

Ist P4 bis Sonntagabend nicht live, legt der Lauf einen weiteren falschen Entwurf an. **Nichts tun:** nicht deaktivieren, denn ein deaktiviertes Abo erzeugt auch nach dem Fix nichts, bis jemand es wieder einschaltet. Der Entwurf läuft in R2 und Schritt 7 mit.

- [ ] **Schritt 4: Nach dem Deploy von Tasks 19–22 — ist der Code live?**

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)
docker exec "$C" python -c "import app.tasks.subscription_tasks as t; print(hasattr(t, 'ist_faellig'), hasattr(t, 'abo_position'), hasattr(t, '_abo_bestellung_vorhanden'), hasattr(t, 'abo_lauf'))"
docker exec "$C" sh -c 'echo "DEFAULT_TENANT_SLUG=$(printenv DEFAULT_TENANT_SLUG)"; ls -la /data/tenants'
```

Erwartet: `True True True True`. Sonst ist der Deploy nicht live: abbrechen. P4 hat keine `openapi.json`-Änderung, darum die Prüfung im Container.

Die zweite Zeile ist rein lesend und klärt, wohin der Knopf **vor** Task 22 geschrieben hat:
- `DEFAULT_TENANT_SLUG` leer → Default `dev`. Liegt in `/data/tenants` eine `dev.db` (samt `-wal`/`-shm`), hat sie vermutlich ein Klick auf „Heute verarbeiten“ angelegt; der Scheduler führt sie seitdem als Mandanten. **Nicht löschen**, dem Manager melden (Folgepunkt F4).
- `DEFAULT_TENANT_SLUG=minga` → Klicks aus jedem Mandanten (auch der Demo) haben Mingas Lauf ausgelöst. In R2 nach Abo-Bestellungen mit `created_at` außerhalb von 03:00–04:00 UTC suchen und melden.
- Ein anderer Wert → dessen DB hat die Klicks abbekommen; melden.

- [ ] **Schritt 5: Vorschau der nächsten 14 Tage (lesend, vor dem nächsten 05:00-Lauf)**

```bash
cat > /root/p4_vorschau.py <<'PY'
"""Vorschau: welche Abos der reparierte Lauf in den nächsten 14 Tagen beliefert.

Nur lesend. Läuft im App-Container mit dem Code von P4 (cwd /app):
  python - < p4_vorschau.py          Mandant minga
  python - demo < p4_vorschau.py     anderer Mandant
"""
import sys
from datetime import date, timedelta

from sqlalchemy import select

from app.database import get_tenant_session
from app.tenancy import registry
from app.models.customer import Subscription
from app.tasks.subscription_tasks import ist_faellig, liefertag_heute, _abo_produkt, AboUebersprungen

TAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
SLUG = sys.argv[1] if len(sys.argv) > 1 else "minga"
if not registry.exists(SLUG):  # sonst legte create_engine eine leere DB an
    sys.exit(f"Mandanten-DB fehlt: {registry.path_for(SLUG)} (TENANTS_DIR prüfen)")
print(f"Mandanten-DB: {registry.path_for(SLUG)}")
heute = liefertag_heute()
with get_tenant_session(SLUG) as db, db.no_autoflush:
    for sub in db.execute(select(Subscription).where(Subscription.aktiv == True)).scalars():
        try:
            produkt, variante = _abo_produkt(db, sub)
            was = produkt.name + (f" — {variante.name_suffix}" if variante else "")
        except AboUebersprungen as e:
            was = f"ÜBERSPRUNGEN: {e}"
        termine = [heute + timedelta(days=i) for i in range(14)
                   if ist_faellig(sub, heute + timedelta(days=i))]
        print(f"{sub.kunde.name} | {sub.intervall.value} {[TAGE[t] for t in (sub.liefertage or [])]} "
              f"ab {sub.gueltig_von} | {sub.menge} {sub.einheit} {was}")
        print("    " + (", ".join(f"{TAGE[t.weekday()]} {t:%d.%m.}" for t in termine) or "keine Lieferung in 14 Tagen"))
    db.rollback()
PY
docker exec -i "$C" python - < /root/p4_vorschau.py
docker exec -i "$C" python - demo < /root/p4_vorschau.py
```

Die Ausgabe zeigt je aktivem Abo das gelieferte Produkt oder `ÜBERSPRUNGEN: <Grund>` und die Liefertermine der nächsten 14 Tage. An Gernot geben, zusammen mit R6. **Die Vorschau ist die einzige verlässliche Stelle, an der übersprungene Abos sichtbar werden:** Beim 05:00-Lauf stehen sie nur im Log, beim Knopf nur im grünen Erfolgs-Toast (`Abonnements.tsx:121-123`). Nach jeder Abo-Änderung deshalb erneut laufen lassen (Folgepunkt F2). Abos, die nicht starten sollen, deaktiviert er unter *Abonnements → Deaktivieren* **vor** dem nächsten 05:00-Lauf. Übersprungene Abos (z. B. Sorte mit mehreren Produkten) braucht er neu, mit Produkt. `PATCH /subscriptions` kann das Produkt nicht ändern (`SubscriptionUpdate`, `schemas/customer.py:279-286`).

Die zweite Zeile prüft die Demo (`demo.novaerp.de`): Ihre Abos laufen ab dem Deploy an **jedem** Liefertag statt nur am Wochentag von `gueltig_von`, Sorten-Abos mit mehr als einem aktiven Produkt werden übersprungen. Der 05:00-Lauf nach dem Reset um 03:30 legt dort also mehr Entwürfe an oder meldet Überspringen. Gewollt, aber vorher bekannt; welche Abos `demo.seed.db` enthält, zeigt erst diese Ausgabe (das Dev-Skript `backend/seed_data.py`, `create_subscriptions` Z. 362-419, legt acht wöchentliche Sorten-Abos mit Liefertagen `[1, 3, 5]`, `[1, 5]`, `[0, 2, 4]` und `[1, 4]` an; ob die Demo daraus stammt, ist nicht belegt). Fehlt `demo.db`, endet das Skript mit `Mandanten-DB fehlt`.

- [ ] **Schritt 6: WAL-sicheres Backup (vor jedem Schreiben)**

Über die SQLite-Backup-API, außerhalb von `/data/tenants`. Dort würde `registry.known_slugs()` jede `*.db` als Mandant laden (`tenancy.py:93-96`).

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)
docker exec -i "$C" python3 -c "import sqlite3; s=sqlite3.connect('file:/data/tenants/minga.db?mode=ro', uri=True); d=sqlite3.connect('/tmp/minga-backup.db'); s.backup(d); d.close(); print(sqlite3.connect('/tmp/minga-backup.db').execute('pragma integrity_check').fetchone())"
docker cp "$C":/tmp/minga-backup.db /root/backups/minga-vor-abo-korrektur-$(date +%Y%m%d-%H%M%S).db
docker exec "$C" rm -f /tmp/minga-backup.db
```

Erwartet: `('ok',)` und die Datei unter `/root/backups/`.

- [ ] **Schritt 7: Korrektur der Entwürfe aus Antwort A (Trockenlauf, dann mit Freigabe)**

Das Skript nutzt `abo_position()` und `_calculate_order_totals()` aus dem deployten Code, also dieselbe Rechnung wie der reparierte Lauf und jede Bestellung.

Vorbedingungen je Bestellung (sonst wird nichts geschrieben):
- Status `ENTWURF`, genau eine Position;
- keine Auftragsbestätigung, kein Lieferschein, keine Rechnung, keine Lagerbewegung;
- das Abo ist aus `notes` auffindbar und gehört demselben Kunden;
- `abo_position` findet ein eindeutiges, aktives Produkt, das kein variables Bundle ist;
- die Einheit ist mit Gernot geklärt (Schritt 2): Der Trockenlauf zeigt je Bestellung `Menge … Einheit`; vor `APPLY` mit Gernots Antwort abgleichen.

Die Position wird **an Ort und Stelle** geändert, Positions-ID und Bestellnummer bleiben. Neu gesetzt werden `product_id`, `product_variant_id`, Text, Preis zum Liefertag und Produktsatz. Die Einheit ändert sich nur bei einer Variante. Danach rechnet das Skript Zeilenbeträge und Summen neu und schreibt je Bestellung einen Audit-Eintrag.

```bash
cat > /root/p4_korrektur.py <<'PY'
"""A5: Abo-Entwürfe mit "Abo-Lieferung: Unknown" auf das Abo-Produkt umstellen.

Läuft im App-Container mit dem Code von Paket 2 / P4 (cwd /app):
  python - < p4_korrektur.py                         Trockenlauf, alle Kandidaten
  python - APPLY BE-20260914-0001 ... < p4_korrektur.py   schreibt genau diese
Position und Summen kommen aus abo_position() und _calculate_order_totals(),
also aus demselben Code wie der reparierte Abo-Lauf und jede Bestellung.
"""
import re
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.database import get_tenant_session
from app.tenancy import registry
from app.models.order import Order, OrderStatus, OrderAuditLog
from app.models.customer import Subscription
from app.models.documents import OrderConfirmation, DeliveryNote
from app.models.invoice import Invoice
from app.models.inventory import InventoryMovement
from app.tasks.subscription_tasks import abo_position, AboUebersprungen
from app.api.v1.sales import _calculate_line_amounts, _calculate_order_totals

SLUG = "minga"
if not registry.exists(SLUG):  # sonst legte create_engine eine leere DB an
    sys.exit(f"Mandanten-DB fehlt: {registry.path_for(SLUG)} (TENANTS_DIR prüfen)")
print(f"Mandanten-DB: {registry.path_for(SLUG)}")
SCHREIBEN = len(sys.argv) > 1 and sys.argv[1] == "APPLY"
AUSWAHL = set(sys.argv[2:]) if SCHREIBEN else None
if SCHREIBEN and not AUSWAHL:
    sys.exit("APPLY braucht die Bestellnummern, z. B. APPLY BE-20260914-0001")
ABO_RE = re.compile(r"Abo ([0-9a-fA-F-]{36})")
GRUND = ("A5 (Gernot-Feedback 08.10.2026): Abo-Position ohne Produkt "
         "('Abo-Lieferung: Unknown') auf das Abo-Produkt umgestellt; "
         "Preis, Steuersatz und Summen neu berechnet")


def werte(o, zeile):
    return {
        "beschreibung": zeile.beschreibung,
        "product_id": str(zeile.product_id) if zeile.product_id else None,
        "unit": zeile.unit, "quantity": str(zeile.quantity),
        "unit_price": str(zeile.unit_price), "tax_rate": zeile.tax_rate.value,
        "line_net": str(zeile.line_net), "total_net": str(o.total_net),
        "total_vat": str(o.total_vat), "total_gross": str(o.total_gross),
    }


with get_tenant_session(SLUG) as db, db.no_autoflush:
    bestellungen = db.execute(
        select(Order).where(Order.internal_notes == "Subscription Run")
        .order_by(Order.requested_delivery_date, Order.order_number)
    ).scalars().all()
    kandidaten = [
        o for o in bestellungen
        if any(z.product_id is None and (z.beschreibung or "").startswith("Abo-Lieferung:")
               for z in o.lines)
    ]
    if AUSWAHL is not None:
        kandidaten = [o for o in kandidaten if o.order_number in AUSWAHL]

    fehler, plan = [], []
    for o in kandidaten:
        gruende = []
        if o.status != OrderStatus.ENTWURF:
            gruende.append(f"Status {o.status.value}")
        if len(o.lines) != 1:
            gruende.append(f"{len(o.lines)} Positionen")
        for modell, name in ((OrderConfirmation, "Auftragsbestätigung"), (DeliveryNote, "Lieferschein"),
                             (Invoice, "Rechnung"), (InventoryMovement, "Lagerbewegung")):
            n = db.execute(select(func.count()).select_from(modell)
                           .where(modell.order_id == o.id)).scalar()
            if n:
                gruende.append(f"{n} {name}")
        treffer = ABO_RE.search(o.notes or "")
        sub = db.get(Subscription, uuid.UUID(treffer.group(1))) if treffer else None
        if sub is None:
            gruende.append("Abo nicht gefunden")
        elif sub.kunde_id != o.customer_id:
            gruende.append("Abo gehört zu einem anderen Kunden")
        neu = None
        if not gruende:
            try:
                # Preis zum Liefertag, wie der Lauf ihn an diesem Tag gerechnet hätte.
                neu = abo_position(db, sub, o.requested_delivery_date)
            except AboUebersprungen as e:
                gruende.append(f"Abo: {e}")
        if gruende:
            fehler.append((o.order_number, gruende))
        else:
            plan.append((o, neu))

    if AUSWAHL is not None:
        gefunden = {o.order_number for o in kandidaten}
        fehler += [(nr, ["kein Kandidat (Nummer, Status oder Position prüfen)"])
                   for nr in sorted(AUSWAHL - gefunden)]

    for o, neu in plan:
        zeile = o.lines[0]
        vorher = werte(o, zeile)
        zeile.product_id = neu.product_id
        zeile.product_variant_id = neu.product_variant_id
        zeile.beschreibung = neu.beschreibung
        zeile.unit_price = neu.unit_price
        zeile.tax_rate = neu.tax_rate
        if neu.product_variant_id:
            zeile.unit = neu.unit  # Variantenpreis gilt je Verpackungseinheit
        # Menge bleibt die des Entwurfs (so war das Abo an diesem Tag).
        _calculate_line_amounts(zeile)
        _calculate_order_totals(o)
        nachher = werte(o, zeile)
        print(f"{o.order_number} {o.requested_delivery_date} {o.customer.name} | Menge {zeile.quantity} {zeile.unit}")
        for k in vorher:
            if vorher[k] != nachher[k]:
                print(f"    {k}: {vorher[k]} -> {nachher[k]}")
        if SCHREIBEN:
            o.updated_at = datetime.now(timezone.utc)
            db.add(OrderAuditLog(
                order_id=o.id, action="UPDATE_LINE", line_id=zeile.id,
                old_values=vorher, new_values=nachher,
                user_name="Runbook P4 (A5)", reason=GRUND,
            ))

    for nr, gruende in fehler:
        print(f"NICHT KORRIGIERBAR {nr}: {', '.join(gruende)}")
    print(f"{len(plan)} Bestellung(en) korrigierbar, {len(fehler)} nicht.")

    if not SCHREIBEN:
        db.rollback()
        print("Trockenlauf — nichts geschrieben.")
    elif fehler:
        db.rollback()
        sys.exit("Vorbedingung verletzt — nichts geschrieben.")
    else:
        db.commit()
        print("Geschrieben. Alte Werte: order_audit_logs.old_values; Rückfallebene: Backup aus Runbook-Schritt 6.")
PY
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)
docker exec -i "$C" python - < /root/p4_korrektur.py
```

Der Trockenlauf zeigt je Kandidat alt → neu (Text, `product_id`, Preis, Satz, Zeilen- und Bestellsummen) und `NICHT KORRIGIERBAR <Nr>: <Grund>`. Ausgabe Gernot bzw. dem Freigebenden vorlegen. Nach Freigabe nur die Nummern mit Antwort **A**:

```bash
docker exec -i "$C" python - APPLY BE-20260914-0001 BE-20260921-0001 < /root/p4_korrektur.py
```

(Nummern aus R2 übernehmen, die hier sind Beispiele.) Ohne Nummern verweigert `APPLY`. Eine unbekannte Nummer oder eine verletzte Vorbedingung: `Vorbedingung verletzt — nichts geschrieben.` Ein zweiter Lauf findet die korrigierten Bestellungen nicht mehr (idempotent). **Rücknahme:** Die alten Werte stehen je Bestellung in `order_audit_logs.old_values`. Das Backup aus Schritt 6 ist die Rückfallebene, falls unmittelbar danach etwas schiefgeht.

Im Planungslauf gegen das nachgestellte Fehlerbild (Abo-Produkt 12,50 € zu 7 %, Sonderpreis 11,90 €, Köder „Mehrwegkiste Pfand“ 2,00 € zu 19 %, Menge 2): je Entwurf `unit_price: 2.0000 -> 11.9000`, `tax_rate: STANDARD -> REDUZIERT`, `total_gross: 4.76 -> 25.47`. Ein Entwurf mit Auftragsbestätigung wurde abgewiesen.

- [ ] **Schritt 8: Entwürfe aus Antwort B und C stornieren (Oberfläche)**

*Bestellungen → Bestellung öffnen → Abschnitt „Stornieren“ → Grund → „Bestellung stornieren“* (`EditOrderModal.tsx:262-268`, `POST /sales/orders/{id}/status` mit `STORNIERT`, `ENTWURF → STORNIERT` ist erlaubt, `sales.py:1199`). Der Audit-Eintrag `STATUS_CHANGE` mit Grund entsteht automatisch. Gründe:
- B: „A5: Abo-Lauf-Fehler, nicht geliefert“;
- C: „A5: Abo-Lauf-Fehler, außerhalb berechnet mit <Rechnungsnr.>“.

Keine Bestandswirkung. Löschen statt Stornieren ginge auch (`DELETE /sales/orders/{id}` nur für Entwürfe), hinterlässt aber keine Spur. Darum stornieren.

**Alternative zu Schritt 7, falls Gernot kein Skript will:** Entwurf stornieren (wie B), dann in der Oberfläche neu anlegen, mit Liefertermin = ursprünglicher Liefertag und dem Abo-Produkt. Nachteile:
- neue Nummer mit Anlagedatum statt Liefertag;
- vier Handeingaben;
- Preis aus der Formular-Vorbelegung zum Anlagetag statt zum Liefertag.

Erst **nach** Paket 1 (Tasks 1 und 7) live. Vorher schickt das Bestellformular fest 7 % (`CreateOrderModal.tsx:177`).

- [ ] **Schritt 9: Kontrolle**

Schritt 1 erneut ausführen. Erwartet:
- R2: keine Position `Abo-Lieferung: Unknown` mehr im Status `ENTWURF`;
- A-Fälle mit Abo-Produkt, Sonderpreis und Satz;
- B/C-Fälle `STORNIERT`;
- R3: je A-Fall ein Protokolleintrag mehr.

Am nächsten Liefertag nach dem Deploy (bei Montags-Abo 12.10. bzw. 19.10.) prüfen: Der 05:00-Lauf hat für LfA genau einen Entwurf mit Produktname, Kundenpreis und Produktsatz angelegt (R2), und ein Klick auf „Heute verarbeiten“ **auf `minga.novaerp.de`** meldet `0 Abo-Bestellungen angelegt. N schon vorhanden.` (N = Zahl der heute in Minga fälligen Abos laut Vorschau; übersprungene Abos hängt die Meldung an). Seit Task 22 läuft der Klick im Mandanten der Anfrage, die Meldung betrifft also Minga. Danach `docker exec "$C" ls -la /data/tenants`: keine neue Datei gegenüber Schritt 4.


### Runbook C: Nach dem Deploy

**C1 — Live-Prüfung (lesend).**

```bash
C=$(docker ps --format '{{.Names}}' | grep n8ml32w2vs6b190ue2ianc84 | head -1)
docker exec "$C" python -c "import app.services.order_status_service as s; print([x.value for x in s.ERLAUBTE_UEBERGAENGE[s.OrderStatus.IN_PRODUKTION]])"
docker exec "$C" python -c "import app.tasks.subscription_tasks as t; print(hasattr(t, 'abo_lauf'), hasattr(t, 'liefertag_heute'))"
curl -s -o /dev/null -w '%{http_code}\n' https://minga.novaerp.de/health
```

Erwartet: `['GELIEFERT', 'STORNIERT']`, `True True`, `200`. Danach im Browser auf `minga.novaerp.de` (Tagesplan heute): Badges zeigen „Bestätigt"/„Gepackt", keine Enum-Werte; Knopf „Gepackt" in „Verpacken", „Ausgeliefert" in „Ausliefern". Rechnungen: Spalte „Kunde" bei RE-2026-00001 bis -00005 gefüllt, die Suche „Ökoring" findet RE-00002 und RE-00003, das Detail-Modal zeigt den Kunden. Keine Statusänderung an echten Bestellungen ohne Gernots Wissen.

**C2 — Gernots Bestellungen vom 07./08.10. nachquittieren (nur mit Antwort auf O2 und Freigabe).** Sie stehen auf GELIEFERT ohne `actual_delivery_date`, ihre Lieferscheine auf `ENTWURF` (A1.md, LUECKEN.md Punkt 4). Je Bestellung in der Oberfläche: *Bestellungen → Karte → Belege → Lieferschein → „Liefertag" auf das von Gernot genannte Datum (07. oder 08.10.) → „Unterzeichnet von…" → „Quittieren"*. Erwartet: Lieferschein `GELIEFERT`, Bestellung bleibt `GELIEFERT` mit dem gewählten `actual_delivery_date`, Audit-Eintrag `LIEFERDATUM_NACHGETRAGEN`, kein zweiter Bestandsabzug (Task 2). Ein vorhandenes Lieferdatum überschreibt das Quittieren nie. Bestellungen ohne Lieferschein: nichts tun und melden — der Status-Endpunkt kann einer gelieferten Bestellung kein Datum nachtragen.

**C3 — Paket-1-Runbook R3 angleichen,** bevor es läuft (Überschneidung 2): ENTWURF/STORNIERT → erst bestätigen bzw. nicht quittieren; der Knopf „Quittieren" schickt nach Task 9 das Datum mit.

**C4 — Abo-Lauf am nächsten Liefertag** wie Runbook B, Schritt 9.

---

## Offene Punkte für Gernot

Nur Gernot (bzw. der Steuerberater) kann entscheiden. Nummern O1–O20; im Plan so referenziert.

**Tagesplan und Status (P1, P2)**
- **O1 — Soll „Ausgeliefert" im Tagesplan auch den Lieferschein quittieren?** Heute und nach diesem Plan bleibt ein angelegter Lieferschein auf „Entwurf", wenn der Fahrer im Tagesplan klickt. Quittieren heißt laut Datenmodell „vom Empfänger unterschrieben" und sperrt den Lieferschein; das automatisch zu tun, behauptete etwas, das der Klick nicht belegt. Wenn gewünscht: Empfängername abfragen oder bewusst leer lassen.
- **O2 — Die fünf Bestellungen vom 07./08.10.:** Wer quittiert sie, mit welchem Datum (07. oder 08.10.)? Ablauf Runbook C2.
- **O3 — Wortwahl:** Der Status heißt überall „Geliefert", der Knopf im Tagesplan „Ausgeliefert". Soll der Status selbst „Ausgeliefert" heißen? (Eine Zeile in `statusLabels.ts`, eine in `STATUS_BEZEICHNUNG`.)
- **O4 — Nachträglich liefern ohne Lieferschein:** Der Tagesplan schickt das angezeigte Datum mit, die Bestellliste setzt immer heute. Braucht auch die Bestellliste ein Datumsfeld?
- **O5 — Stornieren gepackter Ware:** jetzt erlaubt. Die Ware bleibt dabei im Bestand gebucht wie vor dem Packen; es gibt keinen Abgang „verworfen". Soll es dafür eine Buchung geben?
- **O6 — Farben der Status-Badges:** Der Plan ändert nur Namen. Entwurf grau, Bestätigt blau, Gepackt gelb, Geliefert grün, Fakturiert grau, Storniert rot; im Tagesplan wird „Entwurf" dadurch grau statt bisher gelb. Andere Farben wären drei Zeilen in `orderStatusVariant` (`Badge.tsx`), dann in Bestellliste und Tagesplan zugleich.
- **O7 — „Gepackt" zurücknehmen?** Die beschlossenen Übergänge kennen kein IN_PRODUKTION → BESTAETIGT. Ein Fehlklick auf dem Tablet nimmt die Bestellung aus dem Sortenbedarf; sie bleibt unter „Bereits gepackt" und in „Ausliefern", liefern und stornieren geht weiter. Braucht die Halle „Gepackt zurücknehmen"? Wenn ja: neuer Übergang in `ERLAUBTE_UEBERGAENGE`.
- **O8 — Entwürfe am Packtag:** Unter „Verpacken" stehen auch Entwürfe, packbar erst nach Bestätigung. Reicht „erst bestätigen", oder soll die Halle im Tagesplan selbst bestätigen dürfen (`POST /sales/orders/{id}/confirm`; laut Gernot dürfen Mitarbeiter Bestellungen anlegen und AB versenden)?
- **O9 — Altbestand auf IN_PRODUKTION:** Liefert Runbook A1 Bestellungen ab heute, entscheidet Gernot je Bestellung: wirklich gepackt (bleibt) oder nicht (Datenkorrektur mit Audit-Eintrag, Weg nicht Teil dieses Plans).
- **O10 — Packliste auf der Produktionsseite:** Gepackte stehen dort nicht mehr in der Tabelle, nur in der Kopfzeile. Lieber alle mit Häkchen?
- **O11 — Teilweise gepackt:** Der Knopf gilt für die ganze Bestellung. Eine Packmarke je Position bräuchte eine neue Spalte (für Paket 2 ausgeschlossen).

**Rechnungen (P3)**
- **O12 — Mahnstufe:** `InvoiceResponse` liefert `reminder_level` nicht, obwohl das Frontend es liest (`Invoices.tsx:439`). Der Knopf „Mahnung" bietet deshalb immer Stufe 1 (0 €) an und eskaliert nie zu „1. Mahnung" (5 €) bzw. „2. Mahnung" (10 €). Ist die Eskalation mit diesen Gebühren gewollt? (Fix: zwei Schemafelder; passt zu „Stornobeleg ohne Mahnung" in Paket 1.)
- **O13 — Kundensuche:** wirkt nur im Reiter „Alle" (`Invoices.tsx:196-203`) und nur auf den Namen. Auch in „Offen", „Überfällig", „Bezahlt" und mit Kundennummer? (Kleine Änderung in `Invoices.tsx`, nach Paket 1.)
- **O14 — Stammdatenstand statt Beleg-Snapshot (Steuerberater):** Liste und PDF zeigen den aktuellen Kundennamen; nach einer Umbenennung tragen auch alte Rechnungen den neuen Namen. Müssen versendete Belege den Namen zum Rechnungszeitpunkt behalten? Falls ja: Paket 3 (Belegarchiv).

**Abos (P4, Runbook B)**
- **O15 — LfA-Lieferungen 14.09., 21.09., 28.09., 05.10.:** tatsächlich geliefert? Außerhalb des Systems berechnet, mit welcher Rechnung? Davon hängt je Entwurf Korrektur (A) oder Storno (B/C) ab.
- **O16 — Ist das LfA-Abo richtig gepflegt** (Produkt, Menge, Einheit, Liefertage)? Fehlen Lieferungen an weiteren Liefertagen, die der Fälligkeitsfehler unterdrückt hat — nachträglich erfassen? **Einheit:** Läuft das Abo in `KISTE_6`/`KISTE_12` ohne Variante, ist der Preis Produktpreis × Menge; ist der Produktpreis ein Stückpreis, liegt der korrigierte Preis um den Faktor 6 bzw. 12 daneben. Vor `APPLY` klären.
- **O17 — Sollen alle Abos aus R6 nach dem Deploy starten?** Sie haben wegen des Fehlers nie eine Bestellung erzeugt. Nicht gewünschte vor dem nächsten 05:00-Lauf deaktivieren.
- **O18 — Bedeutung von „monatlich" und „zweiwöchentlich" mit Liefertagen:** monatlich = erster Liefertag ab dem Monatstag von „Gültig ab" (ab dem 29. aufs Monatsende gekappt); zweiwöchentlich = jede zweite Kalenderwoche ab der Woche der ersten Lieferung. Bestätigen.
- **O19 — Preis der korrigierten Entwürfe:** der am jeweiligen Liefertag gültige Sonderpreis bzw. Basispreis. Bestätigen.
- **O20 — Bestand bei nachträglich „Geliefert":** Wird eine korrigierte September-Bestellung jetzt auf „Geliefert" gesetzt, bucht `setze_status` den Fertigwarenbestand **von heute** ab (FIFO, bei Unterdeckung nur eine Warnung). So gewollt, oder gehen diese Bestellungen ohne Bestandsbuchung in die Abrechnung? (Hängt mit O4 und O5 zusammen.)

**Hinweise an Gernot (zur Kenntnis):**
- Abo-Bestellungen erkennt das System an der Notiz „Automatisch erstellt aus Abo …", am Kunden und am Liefertag. Wer die Notiz ändert, den Liefertag verschiebt oder den Entwurf löscht, bekommt sie beim nächsten Lauf desselben Tages neu. Nicht gewünschte Abo-Bestellungen **stornieren**, nicht löschen oder umschreiben.
- Abos ohne eindeutiges Produkt, auf deaktivierte Produkte oder auf variable Bundles (Gastrotray) werden nicht beliefert. Beim 05:00-Lauf steht das nur im Protokoll, beim Knopf in der grünen Meldung. Solche Abos mit einem lieferbaren Produkt neu anlegen; das Produkt eines Abos lässt sich nicht ändern.
- „Heute verarbeiten" wirkte bisher nicht auf Mingas Abos (Mandantenfehler). Nach dem Deploy wirkt der Knopf auf Mingas Abos und legt nichts doppelt an, wenn der 05:00-Lauf schon gelaufen ist.
- Preis eines Abos = Produktpreis (bzw. Sonderpreis) × Menge in der Einheit des Abos, ohne Umrechnung. Für Kisten-Abos eine Verpackungsvariante oder einen Kistenpreis pflegen.
- „Gepackt" bucht keinen Bestand; erst „Geliefert" bucht ab. Eine gepackte Bestellung lässt sich stornieren.

## Entscheidungen für den Manager

- **E1 — entschieden (Manager 08.10.: Plan-Default gilt) — Dashboard „Offene Bestellungen"** (Task 15): zählt BESTAETIGT + IN_PRODUKTION, die bisherige Bedeutung ohne Verlust der Gepackten. Alternative in einer Zeile: `salesApi.listOrders({ status: 'OFFEN' })` zählt zusätzlich Entwürfe (`sales.py:691`) und deckt sich mit dem Filter „Offen". Vor dem Worker-Lauf festlegen; ohne Festlegung gilt der Plan.
- **E2 — Import-Härtung (A6-Rest) fehlt in diesem Plan.** Die Spec ordnet sie Paket 2 zu (unvollständige Bestellungen bei fehlerhaften Zeilen verhindern, Bestelldatum/Status/Einheit prüfen, Adresse und Audit-Eintrag setzen; Nachtrag T1). Es gibt dafür keinen geprüften Abschnitt. Dazu gehört: `imports.py:122` erlaubt `IN_PRODUKTION`, `:568-576` lehnt Zukunftsdaten nur für GELIEFERT/FAKTURIERT ab — Vorschlag: `IN_PRODUKTION` mit Lieferdatum ab heute ablehnen oder auf `BESTAETIGT` abbilden. Eigenen Abschnitt planen lassen (ändert `imports.py`, das dieser Plan bewusst nicht anfasst).
- **E3 — entschieden (Manager 08.10.):** Tasks 7/13 setzen `refetchOnWindowFocus: 'always'` an beiden Plan-Abfragen; das Hallen-Tablet lädt beim Aufwecken sofort.
- **E4 — Platzhalter:** Nach Task 18 zeigt die Rechnungsliste bei fehlendem Kunden `-` (`Invoices.tsx:344`), das Detail `–`. Wer `Invoices.tsx` nach dem Merge von Paket 1 anfasst, kann Z. 344 angleichen.
- **E5 — Hinweis an den Paket-1-Worker, bevor Paket-1-Task 22 läuft:** in `test_quittierter_lieferschein_vertritt_die_bestellung` direkt nach `bestellung = _s6_bestellung(client, _s6_kunde(client))` die Bestellung per `POST /api/v1/sales/orders/{id}/confirm` bestätigen (Wortlaut Task 2 Step 5). Zusätzlich an Paket 1 weitergeben: Leistungsdatum `note.actual_delivery_date or order.actual_delivery_date or order.requested_delivery_date`; ein künftiges FAKTURIERT nur über `setze_status` (Überschneidung 16); Paket-1-Runbook R3 angleichen (Überschneidung 2).
- **E6 — Bewusst nicht in diesem Plan:** `i18n/de.json:48` (`inProduktion`, ungenutzt); Fehlertext bei ungültigem Listenfilter (`sales.py` ~Z. 697); Kundentyp roh im Kunden-Modal (`Sales.tsx:407-409`, kein Status); Bestellimport (`imports.py`, siehe E2); `invoice_service.py` (Paket 1); globales `refetchOnWindowFocus` in `main.tsx` bleibt `false`.

## Folgepunkte (Manager trägt sie in die Spec ein)

- **F1 — Absatzprognose ohne Produkt-Abos** (gleiche Ursache wie A5): `_calculate_subscription_demand` (`backend/app/api/v1/forecasting.py:1125`, Abfrage Z. 1133-1142) zählt Abo-Bedarf nur über `Subscription.seed_id`; Produkt-Abos wie LfA fehlen in der Prognose.
- **F2 — Übersprungene Abos sichtbar machen:** beim 05:00-Lauf nur im Log, beim Knopf im grünen Erfolgs-Toast (`Abonnements.tsx:121-123`). Bis dahin ist Runbook B, Schritt 5 die einzige verlässliche Stelle. Vorschlag: Warnhinweis je Abo in *Abonnements* bzw. Warn-Toast.
- **F3 — Berliner Kalendertag:** `order_status_service.heute_berlin()` (Task 1) und `subscription_tasks.liefertag_heute()` (Task 22, ruft `heute_berlin`) sind zusammengeführt; `imports._today_berlin()` (`imports.py:42-43`, Hotfix `efcea00`) rechnet noch selbst — beim nächsten Eingriff in `imports.py` (E2) umstellen.
- **F4 — Fremde Mandanten-DB aus Knopf-Klicks:** Zeigt Runbook B, Schritt 4 eine `dev.db` (oder andere unerwartete DB) in `/data/tenants`, entscheidet der Manager über Sicherung und Entfernung; solange sie dort liegt, läuft jeder Scheduler-Job auch für sie (`known_slugs`).
- **F5 — Forecast-Genauigkeit und Umsatzbericht:** `tasks/forecast_tasks.py:192-202` und `tasks/report_tasks.py:208-226` nutzen `Order.liefer_datum` (keine Spalte) und `OrderLine.menge` (Property); `calculate_forecast_accuracy` scheitert, sobald es Forecasts von gestern gibt (geplant `scheduler_service.py:96`).

## Nebenbefunde (nicht Teil dieses Plans, nicht geändert)

- `SubscriptionUpdate` (`schemas/customer.py:279-286`) kann Produkt und Variante nicht ändern; `create_subscription` prüft nicht, ob die Variante zum Produkt gehört (der Lauf überspringt so ein Abo jetzt mit Grund).
- `ProductVariant.is_active` (`product.py:358`) prüft der Abo-Lauf nicht; ein Abo auf eine deaktivierte Variante liefert weiter (wie `create_order`).
- `_generate_order_number` (`sales.py`) nimmt `date.today()` (Container-Zeit UTC): Eine Abo-Bestellung, die zwischen 00:00 und 02:00 Uhr Berliner Zeit per Knopf entsteht, trägt in der Nummer das Vortagsdatum; der Liefertag stimmt.
- Das Abo-Formular setzt `gueltig_von` mit `new Date().toISOString()` (UTC); kurz nach Mitternacht steht dort das Vortagsdatum.
- Im Vollauf legt ein Test außerhalb dieses Plans `TENANTS_DIR/dev.db` an bzw. öffnet sie (auf der Prüfkopie bei etwa 70 % des Laufs). Im Hauptrepo ist das `backend/data/tenants/dev.db`, die echte lokale Dev-DB. Ursache nicht untersucht.
- Celery Beat (`celery_app.py:68-72`) ruft `process_daily_subscriptions` ohne Mandanten-Kontext, also im Default-Mandanten. In Produktion plant der APScheduler mit Kontext; relevant nur, falls Celery Beat je läuft.
- `confirm_order` (`sales.py:1153`) setzt BESTAETIGT weiter selbst (eigener Audit-Eintrag `CONFIRM`), nicht über `setze_status`; die Spec-Entscheidung betrifft nur die Wege nach GELIEFERT.
- `batch_run_commit` (`invoices.py:650`) serialisiert nach dem Commit und lädt dabei je Kunde nach; seltener Schreibvorgang, der Name kommt über die Property korrekt.
- Weitere rohe Enum-Werte aus LUECKEN.md Punkt 3 sind mit Task 5 und 6 erledigt (`Tagesplan.tsx:102`, `Forecasting.tsx:371`, `Production.tsx:603`, `Invoices.tsx:128`, `forecasting.py:935`/`:1021`, `OrderDocumentsModal.tsx:171`/`:229`/`:305`).
