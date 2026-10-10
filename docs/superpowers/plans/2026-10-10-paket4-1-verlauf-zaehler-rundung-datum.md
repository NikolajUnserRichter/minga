# Paket 4.1 — Bestellverlauf, Reiterzähler, Cent-Rundung, Berliner Datum — Implementation Plan

> **Hinweis für Worker (Codex, ohne Netzwerk):** Diesen Plan Task für Task in der Reihenfolge der Nummern 1–19 abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Lies vor jedem Task seinen Abschnitt frisch aus der Plandatei (sie kann während des Laufs ergänzt werden). Kein Task wird übersprungen, zusammengefasst oder auf eigenes Urteil verkürzt. **Stoppregeln** stehen unter „Global Constraints“. Eigene Patch- oder Ankerfehler sind **kein** Stoppgrund: auf Funktions-/Klassennamen und die zitierten Blöcke ankern (**nie auf Zeilennummern**); jeder Block „diesen Block … ersetzen durch“ bzw. „diesen Block … löschen“ kommt beim Ersetzen genau einmal vor; nach jedem Patch mit `grep -n`/`grep -c` prüfen, dass genau die gemeinte Stelle geändert ist. Die vier Abschnitte tragen Kurzbezeichnungen (R.1 … R.3, D.1 … D.6, V.1 … V.5, Z.1 … Z.4); sie stehen in Texten, Commit-Betreffen (`(P41-R.1)` …) und Code-Kommentaren und meinen die Tasks laut Tabelle „Reihenfolge“ (z. B. „nach D.4“ = nach Task 7). **Abschnitt D ist geteilt:** D.1–D.4 (Backend) sind Tasks 4–7, D.5 (Oberfläche) und D.6 (Abschluss D) sind Tasks 13–14, nach Abschnitt V. „D-E…“, „D-S…“ und „R-D1“ meinen Entscheidungen, Stoppregeln und Runbook von Abschnitt D (Berliner Datum); „P4-D“, „P4-B.2“, „P4-Fix.4“ usw. meinen Paket 4 (schon auf `main`). Die Abschlussmeldungen in Task 3 (R), Task 12 (V), Task 14 (D) und Task 18 (Z) sind Zwischenstände für den Bericht — **nicht anhalten**, der Lauf endet mit Task 19. **Abnahme**, **Manager-Abnahme** und **Offene Punkte** am Ende sind Manager-Arbeit, kein Worker-Task; der Worker verbindet sich nie mit dem Produktionsserver.

**Goal:** Die vier Restpunkte „Offen (niedrig)“ aus der Abnahme von Paket 4 (Spec `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, Eintrag „Paket 4 live“), vom Nutzer alle beauftragt, in einem Arbeitsbaum, einem Branch und einem Deploy:
- **R — Cent-Rundung in der Anlage „Enthaltene Lieferscheine“** (Sammel- und Monatsrechnung; Rechnungs-PDF und `GET /invoices/{id}/delivery-notes`). Jede Position verteilt ihren gedruckten Zeilenbetrag exakt auf ihre Lieferscheine; gerundet wird einmal je Rechnung nach größten Resten (`auf_cent_verteilen`). Die Anlage summiert sich exakt zum Netto der Positionen (vor dem Gesamtrabatt). Keine Datenänderung, keine Layoutänderung.
- **D — Berliner Datum in Belegnummern.** LS, PL, AB, BE (auch Abo-Lauf und Shopify), EK und INV tragen den Berliner Kalendertag statt des UTC-Tags des Containers (Fenster 0–2 Uhr). Das gedruckte „Datum:“ auf AB/LS/PL, „Erstellt am“ in der Bestellansicht und die Stichtag-Vorgabe der Inventur folgen. Wächter halten RE-Jahr und Rechnungsdatum am Jahreswechsel fest. Bestehende Nummern bleiben (GoBD; in `minga` ist keine betroffen).
- **V — Bestellverlauf in der Oberfläche.** Abschnitt „Verlauf“ im Belege-Dialog: wann (Berliner Zeit), wer, was, Status alt → neu, Grund. Der Server speichert ab jetzt den Benutzernamen auch für Änderungen an Kopf und Positionen und nennt bei `UPDATE_LINE` Position und Produkt. Die Halle sieht im Verlauf keine Preise, Rabatte und Beträge.
- **Z — Reiterzähler auf der Rechnungsseite.** Jeder Reiter zeigt, wie viele Rechnungen er bei der aktuellen Suche zeigt (dieselbe Liste wie die Tabelle); an der Listengrenze „N+“. „Überfällig“ lädt nach Zahlung, Storno und Finalisieren mit neu.

**Architecture:** Keine Schemaänderung, keine Migration, keine neue Tabelle, keine neue Route (`tenancy._auto_migrate` unberührt), keine Änderung an Rollen (`main.py`, `core/rollen.py`).
- **Backend:** `invoice_service` (R: `auf_cent_verteilen`, Rumpf von `netto_je_lieferschein`). `order_status_service.heute_berlin` als einzige Quelle für den Tag der Nummern (D: `lieferschein_service.lieferschein_anlegen`, `documents.create_confirmation`, `sales._generate_order_number`, `shopify_service._next_order_number`, `procurement_service._next_po_number`, `inventory_service.create_inventory_count`); `pdf_service.PDFService._build_document` druckt den Berliner Tag des Bestelldatums. `sales.py` (V: `_create_audit_log` mit `user_name`, `UPDATE_LINE` mit `position`/`product`, `get_order_audit_log` mit Positivliste `VERLAUF_WERTE_FUER_ALLE` für Logins ohne `sieht_konditionen`), `schemas/order.py` (`werte_ausgeblendet`).
- **Frontend:** reine Funktionen mit Node-Prüfung: neu `bestellverlauf.ts` (V), `rechnungenJeReiter`/`reiterZaehler` in `rechnungssuche.ts` (Z). Neu `OrderVerlauf.tsx` und `bestellverlaufApi.ts`, eingebaut in `OrderDocumentsModal.tsx` (V). `Tabs.tsx` (`badge?: number | string`) und `Invoices.tsx` (Z). `Sales.tsx` und `Inventur.tsx` mit den vorhandenen `datumKurz`/`heuteBerlin` aus `belegstatus.ts` (D).

**Tech Stack:** FastAPI + SQLAlchemy 2.0, SQLite je Mandant, Pydantic v2, React 18 + TypeScript 5.9, TanStack Query 5; Node ≥ 23.6 für `frontend/tests/unit/*.check.ts` (TypeScript ohne Build); `fractions`/`math` aus der Python-Standardbibliothek (R), keine neue Abhängigkeit.

**Ausgangsstand:** `main` @ `1e2238b` („docs: Paket 4 live (Lücken aus dem Abgleich), Mixe gekennzeichnet, Plan“) = Produktion seit 09.10.2026 23:07. Die Abschnitte sind einzeln geplant, reviewt und auf `1e2238b` nachgespielt (Prüfstände in den Abschnitten); der Gesamtplan ist auf `1e2238b` in einem Stück mechanisch nachgespielt (Prüfstand (Gesamtlauf)). Keine Zeilennummern als Anker.

**Quellen:** Abschnittspläne `/tmp/p41/R.md`, `/tmp/p41/D.md`, `/tmp/p41/V.md`, `/tmp/p41/Z.md` (10.10.2026, in diesen Plan übernommen); Format-Vorbild `docs/superpowers/plans/2026-10-09-paket4-luecken-abgleich.md`.

## Reihenfolge

| Task | Kurz | Inhalt | Art | Neue Tests | Commit |
|---|---|---|---|---|---|
| 1 | R.1 | Reine Funktion `auf_cent_verteilen`; legt `backend/tests/test_paket4_1.py` an | Backend | 5 | ja |
| 2 | R.2 | Anlage „Enthaltene Lieferscheine“ summiert sich exakt zum Netto der Positionen | Backend | 13 | ja |
| 3 | R.3 | Abschluss R (Zwischenstand) | Prüfung | — | — |
| 4 | D.1 | LS, PL und AB nach dem Berliner Tag: Nummer und gedrucktes „Datum:“ | Backend | 6 | ja |
| 5 | D.2 | BE-Nummer nach dem Berliner Tag: Bestellung, Abo-Lauf, Shopify | Backend | 5 | ja |
| 6 | D.3 | EK- und INV-Nummer mit dem Jahr des Berliner Tags | Backend | 3 | ja |
| 7 | D.4 | Wächter: RE-Jahr, Rechnungsdatum, Stornorechnung am Jahreswechsel (kein Code) | Backend (nur Tests) | 4 | ja |
| 8 | V.1 | Änderungen an Bestellungen nennen Benutzer und Position | Backend | 6 | ja |
| 9 | V.2 | Halle sieht im Verlauf keine Preise, Rabatte und Beträge | Backend | 8 | ja |
| 10 | V.3 | Verlauf aufbereiten — reine Funktionen mit Node-Prüfung | Frontend | 1 (Node 45 Fälle) | ja |
| 11 | V.4 | Abschnitt „Verlauf“ im Belege-Dialog | Frontend | — | ja |
| 12 | V.5 | Abschluss V (Zwischenstand) | Prüfung | — | — |
| 13 | D.5 | „Erstellt am“ und Inventur-Stichtag nach dem Berliner Tag | Frontend | — (Node 7 Fälle) | ja |
| 14 | D.6 | Abschluss D (Zwischenstand) | Prüfung | — | — |
| 15 | Z.1 | Zählfunktion der Reiter als reine Funktion mit Node-Prüfung | Frontend | 2 (Node 31 Fälle) | ja |
| 16 | Z.2 | Reiter zeigen ihre Zahl (`badge` statt `count`), „N+“ an der Listengrenze | Frontend | 4 | ja |
| 17 | Z.3 | „Überfällig“ lädt mit den Rechnungen neu | Frontend | 1 | ja |
| 18 | Z.4 | Abschluss Z (Zwischenstand) | Prüfung | — | — |
| 19 | — | Abschluss Paket 4.1: Gesamtprüfung und Gesamtmeldung | Prüfung | — | — |

**Warum R → D.1–D.4 → V → D.5 → Z:**
- **Backend vor Frontend:** Tasks 1–9 ändern nur Backend-Code und die Testdatei, Tasks 10–17 nur das Frontend (dazu angehängte Tests, die `node` aufrufen). V bleibt am Stück: V.4 nutzt `werte_ausgeblendet` aus V.2, V.5 prüft `git log --oneline -4`. D wird geteilt; D.5 (zwei Zeilen Oberfläche, unabhängig von D.1–D.4) läuft nach V. D.6 und die D-Abnahme zählen die D-Commits über `--grep='(P41-D\.'` und sind dafür gebaut.
- **R zuerst:** R legt die gemeinsame Testdatei an, ändert nur `invoice_service.py` und hängt von keinem anderen Abschnitt ab. Danach prüft D.4 (Wächter RE am Jahreswechsel über `festschreiben`/`cancel_invoice`) den von R geänderten `invoice_service` mit. R.3 prüft `git diff --stat <Basis-R>..HEAD` (genau 2 Dateien) — das stimmt, weil R am Stück und als Erstes läuft.
- **D vor V:** Beide ändern `sales.py` an getrennten Stellen (D.2: Importblock aus `order_status_service`, `_generate_order_number`; V.1/V.2: `_create_audit_log`, die vier Aufrufe, `UPDATE_LINE`-Werte, `get_order_audit_log`). Die Hashes aus „Ausgangsstand V“ prüft die Vorbereitung auf der Basis, vor Task 1.
- **Z zuletzt:** nur Frontend; Z.4 prüft `git diff --stat <Basis-Z>..HEAD` (genau 5 Dateien) — das stimmt nur, wenn Z am Stück und zuletzt läuft.
- Innerhalb jedes Abschnitts gilt seine eigene Reihenfolge. Alle Berührungen zwischen den Abschnitten sind getrennte Stellen (File Structure, „Überschneidungen“).

**Commits:** 14 (R 2, D 5, V 4, Z 3); Tasks 3, 12, 14, 18 und 19 committen nichts.

## Prüfstand (Gesamtlauf)

Maßgeblich für den Worker sind allein die Zahlen in den Steps. Die Prüfstände der Abschnitte (einzeln, mit Reviews) stehen in den Abschnitten.

- **Gesamt-Nachspiel dieses Plantexts** (10.10.2026; Kopie `/tmp/p41-kopie-gesamt2` = `git archive 1e2238b` mit eigenem Git-Verlauf — Basis-Commit mit dem Inhalt von `1e2238b`, danach `frontend/node_modules` als Symlink —; Werkzeug `/tmp/p41/merge/nachspiel.py`, Protokoll `/tmp/p41/merge/nachspiel2.log`): Kopf-Vorbereitung und Tasks 1–19 in Dokumentreihenfolge mechanisch angewendet und ausgeführt — 35 Ersetzungen und 1 Löschung (jeder Anker zum Zeitpunkt seines Steps genau einmal, roh und als ganze Zeilen), 6 neue Dateien, Testkopf in Task 1 (in Task 4 und 15 entfällt er, in Task 8 ändert `test -f … ||` nichts), 13 Anhänge; jeder `bash`-Block je Zeile aus dem Wurzelverzeichnis, die Befehle der Steps, alle 14 Commit-Befehle wörtlich (nach jedem Commit `git status --porcelain` nur `?? backend/data/` und `?? frontend/node_modules`). Kein Zählkommentar (`# …`) wich ab.
- **Rot/Grün je Task**, wie in den Steps: Task 1 `5 failed` (`ImportError`) → `5 passed`; Task 2 `8 failed, 5 passed`, die acht Namen und neun Meldungen (Zeilen 5/6 in der Reihenfolge `0001`, `0002`) → `13 passed`, Bestand `229 passed`, F401 `6`; Task 3 `18 passed`, 2 Dateien, 2 Commits; Task 4 die fünf Meldungen, `5 failed, 1 passed` → `6 passed`, `13 passed`, `107 passed`; Task 5 `4 failed, 1 passed` → `5 passed`; Task 6 `2 failed, 1 passed` → `3 passed`, `34 passed`; Task 7 `4 passed`, `18 passed`, Paket-3-Abnahme `5 passed`; Task 8 `5 failed, 1 passed` → `6 passed`, Umfeld `981 passed`; Task 9 `3 failed, 5 passed` → `14 passed`, Umfeld `1001 passed`; Task 10 `ERR_MODULE_NOT_FOUND` und `1 failed` → `bestellverlauf.check: 45 Fälle ok` (auch über `npx --no-install tsx`), `1 passed`; Task 11 `tsc` leer, `✓ built`, Bundle `1`; Task 12 `15 passed`, `git log -4` = V.1–V.4, `<Basis-V>..HEAD` 8 Dateien; Task 13 `0 0 1 1` → `1 1 0 0`, `p41d-berlin.check: 7 Fälle ok`, `✓ built`; Task 14 fünf D-Commits mit genau den Dateien aus „File Structure (D)“ (D.5 nach V; `--grep` trifft nur D); Task 15 `SyntaxError … 'rechnungenJeReiter'`, `1 failed, 1 passed` → `31`/`14 Fälle ok`, `2 passed`; Task 16 die Zeilen aus Step 2 (`4 failed`) → `6 passed`, `0`/`4`, `5 passed, 462 deselected`; Task 17 `1 failed` → `1 passed`; Task 18 `7 passed`, sechs Node-Prüfungen, `<Basis-Z>..HEAD` 5 Dateien, 3 Commits.
- **Prozedur V** zehnmal, Abgleich jedes Mal leer (`14 failed, N passed, 2 skipped, 1 error`, je 1:15–1:49 min in beiden Durchläufen): Basis 2030, nach Task 1 2035, 2 2048, 4 2054, 5 2059, 6 2062, 7 2066, 12 2081, 18 2088, 19 2088.
- **Endstand** (Task 19): `tests/test_paket4_1.py` `58 passed` (R 18, D 18, V 15, Z 7); `test_paket4.py` + `test_gernot_261008_paket3.py` + `test_nachtrag_0910.py` `853 passed` wie auf der Basis (Basis gemessen in `/tmp/p41-kopie-gesamt-basis`: `853 passed`, davon `test_paket4.py` 212); Paket-3-Abnahme `5 passed`; neun Node-Prüfungen wie in Task 19 Step 3; `ruff --select F821,F823` über die 10 geänderten Python-Dateien Exit 0; `tsc` ohne Ausgabe; Build `✓ built`; `22 files changed`, genau die Dateien aus „File Structure“; 14 Commits in der Reihenfolge der Tasks, `Co-Authored-By` 14-mal; im geteilten `node_modules` nichts Neues.
- **Erster Durchlauf** (`/tmp/p41-kopie-gesamt`, Protokoll `/tmp/p41/merge/nachspiel.log`, Plantext vor den drei Korrekturen unten): dieselben Zahlen; daraus die Korrekturen.
- **Zusammenführung, inhaltliche Änderungen gegenüber den Abschnittsplänen:** Tasks durchnummeriert in der Reihenfolge R → D.1–D.4 → V → D.5/D.6 → Z (Backend vor Frontend), Commit-Betreffe unverändert `(P41-…)`; Hinweise, Stoppregeln, Baseline (eine Datei `/tmp/p41-baseline-namen.txt`), Prozedur V (eine Ausgabedatei `/tmp/p41-voll.txt`) und die Ausgangsstände R, D, V wörtlich in den Kopf gezogen, „Ausgangsstand Z“ neu (gemessen); Testkopf vereinheitlicht (R nutzt den Kopf von D/Z); N-Werte auf den Gesamtplan umgestellt; `<Basis-V>` und `<Basis-Z>` als Platzhalter; D.6 prüft `<Basis>..HEAD` statt `1e2238b..HEAD`; Vorbereitung Z erlaubt die sauberen `??`-Einträge (vorher nur `frontend/node_modules`; im Gesamtlauf steht dort auch `backend/data/` — sonst Stopp); Z.4 einheitlich `ruff check` (ohne Unterbefehl lief es auch); Werkzeug V-W (Lese-Skript der Abnahme V, bisher nur unter `/tmp/p41v-tools/`) in den Plan übernommen; Abnahmen und Offene Punkte der Abschnitte ans Ende. **Korrekturen aus dem ersten Gesamt-Nachspiel:** Z.2 Step 2 zeigt die `expected:`-Zeilen statt nur `tail -1` (der Worker konnte die beschriebenen Meldungen sonst nicht prüfen; Ausgabe nachgemessen); R-Überschneidung zu D berichtigt (D ändert `lieferschein_anlegen`, nicht `naechste_belegnummer`); V.1/V.2-Umfeldzahlen als im Gesamtplan gleich bestätigt.
- **Nicht gemessen im Gesamtlauf:** Oberfläche im Browser, Produktion (R-A0, R-D1 „order_date im Fenster“, Abnahme V Schritt 1, Z A1), echte Commits im Worktree (gemessen in der Kopie mit eigenem Git-Verlauf), das Uhrzeit-Fenster in Echtzeit (nur mit eingefrorener Uhr) → Manager-Abnahme.

## Global Constraints

- **Arbeitsort:** Worktree `/Users/nikolajunser-richter/minga-p41`, Branch `feat/paket4-1`, vom Manager vor dem Dispatch aus `main` @ `1e2238b` angelegt: `git worktree add ../minga-p41 -b feat/paket4-1 1e2238b` und `ln -s /Users/nikolajunser-richter/minga-greens-erp/frontend/node_modules frontend/node_modules`. Jeder Befehl beginnt im Worktree-Wurzelverzeichnis (`<Arbeitsbaum>`); das gilt je Zeile eines Befehlsblocks (eine Zeile `cd backend && …` wirkt nicht auf die nächste).
- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` und `backend/venv311` sind kaputt.
- **Node:** `node --version` → v23.6 oder neuer. `TestP41VVerlaufAnzeige`, `TestP41ZZaehlfunktion`, `TestP41ZRechnungsseite`, `TestP41ZUeberfaelligNeuLaden`, `TestP4CBelegstatusAnzeige` und die Paket-3-Abnahmetests rufen `node` aus pytest auf und laufen so auch im Vollauf. Fehlt `node` oder ist es älter: vor Task 1 stoppen, Ausgabe melden. Diese Tests nie überspringen oder ausklammern. Node-Prüfungen laufen mit `node tests/unit/<Name>.check.ts` wie alle Bestandsprüfungen; `tsx` steht nicht in `frontend/package.json`, `npx --no-install tsx …` (nur aus dem npx-Cache) ist ein Zusatz, nie Pflicht und nie ein Stoppgrund.
- **Neue Tests** nur in `backend/tests/test_paket4_1.py`. Task 1 legt die Datei mit dem Kopf an; alle anderen Tasks hängen ihren Block **ans Dateiende**. Die Kopf-Schritte in Task 4, 8 und 15 („nur wenn die Datei fehlt“) entfallen dann — die Datei besteht, kein Stopp. Präfixe je Abschnitt (ein gleichnamiger Helfer würde still ersetzt): **R** — Klassen `TestP41R…`, Helfer `_p41r_…`, Konstanten `_P41R_…`; **D** — `TestP41D…`, `_p41d_…`, `_P41D_…`; **V** — `TestP41V…`, `_p41v_…`, `_P41V_…`; **Z** — `TestP41Z…`, `_p41z_…`, `_P41Z_…`. Keine `autouse`-Fixture. Fixture `client` aus `tests/conftest.py`. Jeder Block bringt seine Importe selbst mit; R und D binden Module unter Präfix-Namen, V bindet `uuid`, `date`, `timedelta`, `Decimal`, `pytest`, `get_current_user`, `app`, `TestingSessionLocal` — kein Name wird von zwei Abschnitten verschieden gebunden (im Gesamt-Nachspiel gesammelt und gelaufen: `58 passed`).
- **Bestehende Tests** ändert kein Task, auch keine `frontend/tests/unit/*.check.ts`. Eine nötige Änderung an einem Bestandstest ist ein Stoppgrund (Stoppregel 4). Die Paket-3-Abnahmetests (`TestAbnahme…`) ändert kein Task.
- **Einzeltests in `test_paket4_1.py` immer über Klassen-IDs, nie `-k`** (in der gemeinsamen Datei zählt `-k` fremde Klassen als `deselected` mit; `-k` in fremden Testdateien bleibt wie in den Steps). Die Befehle stehen in den Steps; zusätzlich:
  - **Paket-3-Abnahme** (Stoppregel 4): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py::TestAbnahmeSepaBerlin tests/test_gernot_261008_paket3.py::TestAbnahmeRechnungsberechtigung -q -p no:cacheprovider 2>&1 | tail -1` → `5 passed` (Z.2 Step 5 nutzt in der Bestandsdatei `-k` → `5 passed, 462 deselected`; gleichwertig).
  - **Alle Paket-4.1-Tests** (Task 19): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py -q -p no:cacheprovider 2>&1 | tail -1` → nach Task 17 `58 passed` (R 18, D 18, V 15, Z 7).
- **Baseline** (Fehlernamen, **nie die Anzahl** vergleichen; 14 failed + 1 error, dieselben 15 Namen wie in Paket 4 und auf `1e2238b` gemessen). Die Datei `/tmp/p41-baseline-namen.txt` legt die Vorbereitung an — Block unverändert, ohne Einrückung, in die Shell geben:

```bash
test -f /tmp/p41-baseline-namen.txt || cat > /tmp/p41-baseline-namen.txt <<'EOF'
ERROR tests/test_production_automation.py::test_approve_suggestion_creates_grow_batch
FAILED tests/test_api.py::TestHealth::test_root_endpoint
FAILED tests/test_auth_manual.py::test_auth_failure
FAILED tests/test_auth_manual.py::test_auth_success
FAILED tests/test_features.py::TestFeatures::test_subscription_processing
FAILED tests/test_production_readiness.py::test_dunning_level1
FAILED tests/test_production_readiness.py::test_dunning_level2
FAILED tests/test_production_readiness.py::test_dunning_level3
FAILED tests/test_production_readiness.py::test_quality_auto_approved
FAILED tests/test_production_readiness.py::test_quality_rejected_high_loss
FAILED tests/test_production_readiness.py::test_quality_rejected_low_note
FAILED tests/test_refinements.py::test_main_app_imports
FAILED tests/test_services.py::TestInvoiceService::test_finalize_empty_invoice_fails
FAILED tests/test_services.py::TestInvoiceService::test_record_full_payment
FAILED tests/test_services.py::TestInvoiceService::test_record_partial_payment
EOF
sort -o /tmp/p41-baseline-namen.txt /tmp/p41-baseline-namen.txt; wc -l < /tmp/p41-baseline-namen.txt
```

  Erwartet: `15`. Eine andere Zahl heißt, die Datei stammt aus einem anderen Lauf: Stoppregel 1. `test_features.py::TestFeatures::test_subscription_processing` scheitert an `async def` ohne Plugin, nicht am Code dieses Plans; er bleibt rot.
- **Kein Netzwerk:** kein `npm install`, kein `git pull`/`push`, kein `curl`. **Kein Deploy, keine Verbindung zum Produktionsserver.**
- **Commits** nur mit den im Task genannten Dateien, nie `git add -A` oder `git add .`. Nachricht nach dem Muster `git commit -m "<Betreff>" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"`; die Betreffe stehen in den Tasks und enden mit `(P41-<Kurz>)`, z. B. `(P41-R.1)`, `(P41-D.3)`, `(P41-V.2)`, `(P41-Z.1)`. Erwartete unversionierte Einträge, die **sauber** sind und nie committet werden: `frontend/node_modules` (Symlink), `backend/data/` (die Testsuite legt `backend/data/tenants/dev.db` samt `-wal`/`-shm` an), falls vorhanden `.claude-flow/` und `.swarm/`, die unversionierte Plandatei; `frontend/dist/` ist per `.gitignore` ausgeblendet.
- **Frontend-Prüfung:** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut; „`tsc`“ in den Steps meint diesen Befehl), Build `cd frontend && npm run build 2>&1 | tail -1` (endet mit `✓ built in …`; die Warnung „Some chunks are larger than 500 kB“ ist Altbestand). `tsconfig.json` hat `noUnusedLocals` und `allowImportingTsExtensions`. Playwright gehört nicht zur Worker-Prüfung. **Node-Prüfungen** (`cd frontend && node tests/unit/<Name>.check.ts`): neu `bestellverlauf` (V.3, `bestellverlauf.check: 45 Fälle ok`), `p41d-berlin` (D.5, `p41d-berlin.check: 7 Fälle ok`), `rechnungsreiter` (Z.1, `rechnungsreiter.check: 31 Fälle ok`); Bestand `rechnungssuche` (`14 Fälle ok`), `positionsaenderung` (`20 Fälle ok`), `belegstatus` (`29 Fälle ok`), `rollen` (`rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`), `dateiname` (`8 Fälle ok`), `belegpfad` (`35 Fälle ok`).
- **Statisch** (`ruff` 0.1.13 unter `/opt/homebrew/bin/ruff` meldet Erfolg stumm; fehlt er dort: „nicht ausführbar“ melden, nicht ersetzen): `ruff check --select F821,F823` mit den Dateien aus den Steps; Task 19 über alle geänderten Python-Dateien.
- **UI-Texte auf Deutsch**, Toast- und Hinweistexte genau wie im Code.
- **Rollen und Rechte:** Kein Task ändert Rollen, Router-Abhängigkeiten (`main.py`) oder `core/rollen.py`. Einzige Rechtewirkung: V.2 filtert die Werte im Verlauf für Logins ohne `sieht_konditionen` (die Halle); Lesezugriff bleibt (kein 403). R, D und Z ändern keine Rechte (je Abschnitt „Rollen und Rechte“ bzw. Entscheidungen).
- **Stoppregeln** (gelten für alle Abschnitte; Verweise auf „Stoppregel 1–5“ meinen diese Liste; Abschnitt D ergänzt D-S1–D-S4):
  1. Ein zitierter Anker fehlt, **weil der Code inhaltlich anders aussieht** (Funktion fehlt, andere Logik, anderer Rückgabewert; z. B. `netto_je_lieferschein` ruft schon `auf_cent_verteilen`, `heute_berlin` fehlt oder `naechste_belegnummer` hat eine andere Signatur (D-S1, D-S2), `_create_audit_log` hat schon `user_name`, `get_order_audit_log` filtert schon, `Tabs.tsx` kennt schon `badge?: number | string`): stoppen, Fundstelle bzw. Fehlerausgabe melden. Eine Abweichung in der **Vorbereitung** ist ebenfalls Stoppregel 1.
  2. Rot oder Grün weicht nach korrekt angewendetem Schritt von der Erwartung ab (andere Anzahl, anderer Testname, andere Fehlermeldung; Datumsangaben in Meldungen sind die des Laufs, in spitzen Klammern wie `<heute>`; die Dauer am Zeilenende ist die des Laufs): stoppen, exakte Ausgabe melden. Nicht „passend machen“. pytest kürzt lange Werte in der `assert`-Zeile (`…`); maßgeblich sind die vollständigen Werte bzw. die Diff-Zeilen darunter. Eine solche Kürzung ist kein Stoppgrund.
  3. Prozedur V zeigt einen Fehlernamen, der nicht in der Baseline steht, oder ein Baseline-Name fehlt: stoppen, `comm`-Ausgabe melden.
  4. Ein Paket-3-Abnahmetest (`TestAbnahmeSepaBerlin`, `TestAbnahmeRechnungsberechtigung`) wird rot, oder ein Umfeld- bzw. Bestandslauf in einem Step (Task 2 Step 5, Task 4 Step 5, Task 6 Step 4, Task 8 und 9 Step 4) zeigt `failed` oder `error`: stoppen, Ausgabe melden. Kein Bestandstest wird angepasst.
  5. **Kein Stopp:** eigene Patch-/Ankerfehler (Leerzeichen, Mehrfachtreffer durch zu kurzen Anker, Tippfehler) — selbst beheben, mit `grep -n` belegen, in der Abschlussmeldung vermerken. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht ebenso.

## Prozedur V (Vollauf mit Namensabgleich)

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/p41-voll.txt 2>&1; tail -1 /tmp/p41-voll.txt; grep -E '^(FAILED|ERROR) ' /tmp/p41-voll.txt | sed 's/ - .*//' | sort > /tmp/p41-namen.txt; comm -3 /tmp/p41-baseline-namen.txt /tmp/p41-namen.txt; echo "--- Ende Abgleich"
```

Erwartet: letzte Zeile `14 failed, N passed, 2 skipped, 1 error in …s`, **keine** Zeile zwischen der Summenzeile und `--- Ende Abgleich`. Dauer 2–3 min. Jede Erwähnung von „Prozedur V“, „Vollauf (Prozedur V)“ oder „Befehl aus dem Kopf“ in den Abschnitten meint diesen Befehl (die Abschnitte hatten einzeln eigene Ausgabe- und Baseline-Dateien; im Gesamtplan gelten nur `/tmp/p41-voll.txt` und `/tmp/p41-baseline-namen.txt`).

N zur Orientierung, maßgeblich sind die Namen. Alle Werte der Tabelle sind im Gesamt-Nachspiel auf `1e2238b` in der Reihenfolge dieses Plans **gemessen** (Prüfstand (Gesamtlauf)); die Zuwächse stimmen mit den Einzelmessungen der Abschnitte überein. Rückt `main` vor dem Dispatch weiter vor, verschiebt sich die Basis, die Zuwächse bleiben:

| nach Task | 0 (Basis) | 1 | 2–3 | 4 | 5 | 6 | 7 | 8 | 9 | 10–14 | 15 | 16 | 17–19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N | 2030 | 2035 | 2048 | 2054 | 2059 | 2062 | 2066 | 2072 | 2080 | 2081 | 2083 | 2087 | 2088 |

Zuwächse: R +5/+13, D +6/+5/+3/+4, V +6/+8/+1, Z +2/+4/+1 (Tasks 11, 13 und die Abschluss-Tasks +0).

## Review Focus

Was **kein automatischer Test** abdeckt (Oberfläche im Browser, Produktion); der Manager prüft es in der Manager-Abnahme. Die Review-Fokus-Absätze der einzelnen Tasks gelten zusätzlich.

**Übergreifend (entsteht erst durch das Zusammenspiel):**
- **Ü1 — Ausliefern nach Mitternacht (D.1 + V.3/V.4).** „Ausgeliefert“ um 00:30 Berliner Zeit: Lieferschein und Packliste heißen `LS-/PL-<Berliner Tag>-…`, `actual_delivery_date` ist derselbe Tag, das LS-PDF druckt „Datum:“ mit dem Berliner Tag des Bestelldatums. Der Verlauf zeigt den Statuswechsel mit Berliner Uhrzeit (`zeitBerlin`, Server speichert UTC) — Nummer, Belegdatum und Verlaufszeit passen zueinander. → A-D2, Abnahme V Schritt 2.
- **Ü2 — Monatsrechnung (R + D.1).** Der Monatslauf am 01.11. legt Entwürfe aus Lieferscheinen an; die Anlage summiert sich exakt zur Zwischensumme der Positionen. Bei gleichem Rest bekommt der Lieferschein mit der kleineren Nummer den Restcent; seit D.1 zählen die Nummern im Kreis des Berliner Tags (die Reihenfolge innerhalb eines Tages bleibt chronologisch). → R-A2, Manager-Abnahme Schritt 8.
- **Ü3 — Belege-Dialog (V.4 + Paket 4 B.4/C.5/O.4).** Unter Lieferscheinen und Rechnungen steht der Verlauf; für die Halle ohne Rechnungsteil, mit Hinweiszeile statt Preisen. „Quittieren“ im Dialog → neuer Eintrag „Lieferschein quittiert“ ohne Neuöffnen; „Belege“ aus der Seite Belegstatus öffnet denselben Dialog. → Abnahme V Schritt 2.
- **Ü4 — `Tabs.tsx` ist gemeinsam (Z.2).** Die Rechnungsseite zeigt Zahlen und „N+“; die Plaketten der Bestellseite („Heute | Morgen | Kommende | Alle“) bleiben gleich; Inventar, Produkte, Produktion und Vertrieb bleiben ohne Zahlen (`count`, Z Offene Punkte 1). → Abnahme Z A3.
- **Ü5 — `sales.py` (D.2 + V.1/V.2).** Eine neue Bestellung um 00:30 heißt `BE-<Berliner Tag>-…`; Änderungen danach erscheinen im Verlauf mit Benutzername und „Pos. n · Produkt“; die Halle sieht dabei keine Preise. → A-D2, Abnahme V Schritt 2.

**R — Cent-Rundung:** Review Focus je Task (Tasks 1–2); R-A0–R-A3. **D — Berliner Datum:** Review Focus je Task (Tasks 4–7, 13); A-D1, A-D2, R-D1. **V — Bestellverlauf:** Review Focus je Task (Tasks 8–11); Abnahme V Schritte 0–3. **Z — Reiterzähler:** Review Focus je Task (Tasks 16–17); Abnahme Z A0–A5.

Getestet (automatisch): R — Cent-Verteilung (Gleichstand, negative Anteile, 1000 Zufallsfälle), Anlage je Lieferschein für 8 Fälle samt PDF, Rechnungsrabatt außerhalb der Anlage, Wächter für Hand-Positionen, Rechnung aus Bestellung und Stornorechnung; D — LS/PL/AB/BE/EK/INV um 00:30, 23:30 und 02:30 sowie am Jahreswechsel, gedrucktes „Datum:“ in AB/LS/PL, Abo-Lauf, Shopify, RE-Wächter, Anzeige- und Vorgabetag (Node); V — Benutzername und Position in den vier Änderungsaktionen, Werte-Filter für die Halle (auch Runbook-Einträge) und Wächter je Rolle mit Konditionssicht, Aufbereitung (Node, im Vollauf); Z — Zählfunktion (Node), Zähler der Rechnungsseite mit Suche und Listengrenze, Reiterleiste mit Zahl und Text, Schlüssel der Abfrage „Überfällig“. Paket-3-Abnahmetests, `tests/test_paket4.py` und `tests/test_nachtrag_0910.py` bleiben unverändert grün.

## File Structure

22 Dateien, davon 7 neu. Spalte „Task“ in der Nummerierung dieses Plans.

| Datei | Task | Verantwortung |
|---|---|---|
| `backend/tests/test_paket4_1.py` | 1, 2, 4–10, 15–17 | **neu** (Task 1 mit Kopf), Blöcke R, D, V, Z angehängt — 58 Tests |
| `backend/app/services/invoice_service.py` | 1, 2 | R.1: Importzeilen (`fractions`, `math`), neu `auf_cent_verteilen` vor `netto_je_lieferschein`; R.2: Rumpf von `netto_je_lieferschein`, Import ohne `ROUND_HALF_UP` |
| `backend/app/services/lieferschein_service.py` | 4 | `naechste_belegnummer` (Docstring), `lieferschein_anlegen` (Nummerndatum `heute_berlin()`, später Import) |
| `backend/app/api/v1/documents.py` | 4 | Importzeile `from datetime import …` (ohne `date`), `create_confirmation` (AB mit `heute_berlin()`) |
| `backend/app/services/pdf_service.py` | 4 | `PDFService._build_document`: „Datum:“ = Berliner Tag von `order.order_date` |
| `backend/app/api/v1/sales.py` | 5, 8, 9 | D.2: Importblock aus `order_status_service` (+ `heute_berlin`), `_generate_order_number`; V.1: `_create_audit_log` (`user_name`), Aufrufe in `update_order`, `add_order_line`, `update_order_line` (+ `position`/`product`), `delete_order_line`; V.2: `VERLAUF_WERTE_FUER_ALLE`, `_verlaufswerte_ohne_konditionen`, `get_order_audit_log` |
| `backend/app/services/shopify_service.py` | 5 | `_next_order_number` mit `heute_berlin()` |
| `backend/app/services/procurement_service.py` | 6 | Importzeile (nur `date`), `ProcurementService._next_po_number` (Jahr aus `heute_berlin()`) |
| `backend/app/services/inventory_service.py` | 6 | `InventoryService.create_inventory_count` (Nummernjahr und Stichtag aus `heute_berlin()`) |
| `backend/app/schemas/order.py` | 9 | `OrderAuditLogResponse.werte_ausgeblendet` |
| `frontend/src/services/bestellverlauf.ts` | 10 | **neu** — Typen, Texte, reine Funktionen (einziger Import: `statusLabels.ts`) |
| `frontend/tests/unit/bestellverlauf.check.ts` | 10 | **neu** — Node-Prüfung, 45 Fälle |
| `frontend/src/services/bestellverlaufApi.ts` | 11 | **neu** — `bestellverlaufApi.liste(orderId)` |
| `frontend/src/components/domain/OrderVerlauf.tsx` | 11 | **neu** — Abschnitt „Verlauf“ |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | 11 | Import hinter `InvoiceDetail`, `<OrderVerlauf …/>` am Ende des Dialoginhalts |
| `frontend/src/pages/Sales.tsx` | 13 | Import `datumKurz`, „Erstellt am“ |
| `frontend/src/pages/Inventur.tsx` | 13 | Import `heuteBerlin`, Stichtag-Vorgabe |
| `frontend/tests/unit/p41d-berlin.check.ts` | 13 | **neu** — Node-Prüfung, 7 Fälle |
| `frontend/src/services/rechnungssuche.ts` | 15 | Anhang: `RechnungsReiter`, `ReiterRechnung`, `rechnungenJeReiter`, `reiterZaehler` |
| `frontend/tests/unit/rechnungsreiter.check.ts` | 15 | **neu** — Node-Prüfung, 31 Fälle |
| `frontend/src/components/ui/Tabs.tsx` | 16 | `interface Tab` (`badge?: number \| string`), Anzeige in `Tabs()` |
| `frontend/src/pages/Invoices.tsx` | 16, 17 | Z.2: Importzeile aus `rechnungssuche`, in `Invoices()` `passtZurSuche` entfällt, `reiter`/`tabs`/`displayInvoices`; Z.3: Schlüssel der Abfrage „Überfällig“ |

**Überschneidungen innerhalb Paket 4.1** (Dateien, die mehr als ein Abschnitt ändert; im Gesamt-Nachspiel R → D.1–D.4 → V → D.5 → Z jeder Anker zum Zeitpunkt seines Steps genau einmal, keine Zeile doppelt ersetzt):
1. **`backend/tests/test_paket4_1.py`** (R, D, V, Z): Task 1 legt an, alle anderen hängen an. Modulweite Namen disjunkt (Präfixe; R und D importieren unter Präfix-Namen); gesamt `58 passed`.
2. **`backend/app/api/v1/sales.py`** (D.2, V.1, V.2): D ankert am Importblock aus `order_status_service` und in `_generate_order_number`; V an `_create_audit_log`, den vier Aufrufen (je eigene `action=`-Zeile), den `UPDATE_LINE`-Werten und `get_order_audit_log`. Getrennte Stellen; die Hashes aus „Ausgangsstand V“ gelten nur vor Task 1.
3. **Fachlich ohne gemeinsame Datei:** R ↔ D.1 (Rang bei gleichem Rest = kleinere LS-Nummer; die R-Tests lesen die Nummern aus der API, D ändert nur den Tag der Nummer); D.4 ↔ R (D.4 prüft `festschreiben`/`cancel_invoice` im von R geänderten `invoice_service`, R ändert dort nur `netto_je_lieferschein`); V.3 ↔ D (der Verlauf zeigt Zeiten in Berlin, D die Nummern nach dem Berliner Tag); V.3 liest `action="…"` aus fünf Backend-Dateien, darunter `sales.py` und `documents.py` — D ändert dort keine Aktion.
4. **Frontend:** keine gemeinsame Datei (V: `OrderDocumentsModal.tsx`, `OrderVerlauf.tsx`, `bestellverlauf*.ts`; D: `Sales.tsx`, `Inventur.tsx`; Z: `Invoices.tsx`, `Tabs.tsx`, `rechnungssuche.ts`). `belegstatus.ts` ändert niemand (D nutzt nur `datumKurz`/`heuteBerlin`). Die Paket-3-Abnahme lädt `Invoices.tsx` mit Ersatzmodulen; Z ändert dort nur Importe aus `../services/rechnungssuche`.

**Nicht geändert (geprüft):** `tenancy.py` (keine Migration), Modelle, `app/main.py`, `app/core/rollen.py`, `order_status_service.py`, `imports.py`, `monatsrechnung_service.py`, `services/api.ts`, `services/orderQueries.ts`, `services/belegstatus.ts`, `components/ui/statusLabels.ts`, `EditOrderModal.tsx`, `Orders.tsx`, `Belegstatus.tsx`, alle Bestandstests und Bestands-Node-Prüfungen, die Paket-3-Abnahmetests.

## Vorbereitung (vor Task 1)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis>` in den Bericht schreiben (erwartet `1e2238b…` oder der neuere `main`-Stand, den der Manager beim Dispatch nennt; eine Shell-Variable reicht nicht, jeder Befehl läuft in einer eigenen Shell). `<Basis-R>` = `<Basis>`.
- [ ] **Arbeitsbaum:** `git status --porcelain` → nur die in „Global Constraints“ als sauber genannten `??`-Einträge. Jede `M`-, `A`- oder `D`-Zeile: stoppen und melden, nichts committen oder zurücksetzen.
- [ ] **Node:** `node --version` → v23.6 oder neuer.
- [ ] **Ausgangsstand R** (Erwartung unter dem Block; Abweichung = Stoppregel 1):

```bash
F=backend/app/services/invoice_service.py
grep -c '^from decimal import Decimal, ROUND_HALF_UP$' $F
grep -c '^def netto_je_lieferschein(db: Session, invoice: Invoice, lieferscheine: list\[DeliveryNote\]) -> dict\[UUID, Decimal\]:$' $F
grep -c 'ROUND_HALF_UP' $F
grep -c 'auf_cent_verteilen\|^from fractions\|^import math' $F
grep -c 'netto_je_lieferschein' backend/app/api/v1/invoices.py backend/app/services/pdf_service.py
grep -rn 'sammelrechnungApi.deliveryNotes\|\.deliveryNotes(' frontend/src | wc -l
```

  Erwartet der Reihe nach: `1`, `1`, `2`, `0`, `backend/app/api/v1/invoices.py:2` und `backend/app/services/pdf_service.py:2`, `0`.
- [ ] **Ausgangsstand D:**

```bash
grep -c "today = date.today()" backend/app/services/lieferschein_service.py backend/app/api/v1/documents.py backend/app/api/v1/sales.py
grep -c "date.today().strftime('%Y%m%d')" backend/app/services/shopify_service.py
grep -c "datetime.now(timezone.utc).year" backend/app/services/procurement_service.py
grep -c "date.today().year" backend/app/services/inventory_service.py
grep -c "^def heute_berlin() -> date:" backend/app/services/order_status_service.py
grep -c "invoice.invoice_date = _heute_berlin()" backend/app/services/invoice_service.py
grep -c 'order.order_date.strftime("%d.%m.%Y")' backend/app/services/pdf_service.py
grep -c "^export function datumKurz\|^export function heuteBerlin" frontend/src/services/belegstatus.ts
grep -c "new Date(selectedOrder.bestell_datum).toLocaleDateString('de-DE')" frontend/src/pages/Sales.tsx
grep -c "useState(new Date().toISOString().split('T')\[0\])" frontend/src/pages/Inventur.tsx
```

  Erwartet: `backend/app/services/lieferschein_service.py:1`, `backend/app/api/v1/documents.py:1`, `backend/app/api/v1/sales.py:1`, danach fünfmal `1`, dann `1`, `2`, `1`, `1`.
- [ ] **Ausgangsstand V** (Kommentar = erwartete Ausgabe):

```bash
grep -c '^) -> OrderAuditLog:$' backend/app/api/v1/sales.py                                              # 1
grep -c '^            user_id=UUID(user\["id"\]) if user else None,$' backend/app/api/v1/sales.py             # 4
for a in UPDATE ADD_LINE UPDATE_LINE DELETE_LINE; do grep -c "^            action=\"$a\",$" backend/app/api/v1/sales.py; done   # 1 1 1 1
grep -c 'user_name' backend/app/api/v1/sales.py                                                          # 0
grep -c '^                "quantity": str(line.quantity),$' backend/app/api/v1/sales.py                     # 2
grep -c '^async def get_order_audit_log(order_id: UUID, db: DBSession):$' backend/app/api/v1/sales.py     # 1
grep -c 'sieht_konditionen' backend/app/api/v1/sales.py                                                  # 3
grep -c '^    reason: Optional\[str\]$' backend/app/schemas/order.py                                       # 1
grep -c "^import { InvoiceDetail } from '../../pages/Invoices';$" frontend/src/components/domain/OrderDocumentsModal.tsx   # 1
grep -c '^export function orderStatusLabel(status: string): string {$' frontend/src/components/ui/statusLabels.ts          # 1
grep -rn 'VERLAUF_WERTE_FUER_ALLE\|werte_ausgeblendet\|bestellverlauf\|OrderVerlauf' backend/app frontend/src | wc -l   # 0
git rev-parse HEAD:backend/app/api/v1/sales.py HEAD:backend/app/schemas/order.py HEAD:frontend/src/components/domain/OrderDocumentsModal.tsx
# 78a5754f9941244fb8b2a59f90483107a2aa5621
# 639ad0e3a631ab0f9749c23d64fde92920bdb13e
# ee7c796b68f82c4dbe5390c50568468fa9e53118
```

  Die drei Hashes gelten nur hier (Task 5 ändert `sales.py`). Weicht nur ein Hash ab, weil `main` seit `1e2238b` vorgerückt ist: kein Stopp, dann die Anker von V beim jeweiligen Step einzeln prüfen (Stoppregel 1, wenn einer inhaltlich fehlt).
- [ ] **Ausgangsstand Z** (die Anker von Z prüft jeder Step selbst; hier nur, dass Z noch nicht da ist):

```bash
grep -c "queryKey: \['invoices-overdue'\]," frontend/src/pages/Invoices.tsx                         # 1
grep -c "count: reiter\." frontend/src/pages/Invoices.tsx                                          # 4
grep -c '^  badge?: number;$' frontend/src/components/ui/Tabs.tsx                                  # 1
grep -c 'rechnungenJeReiter\|reiterZaehler' frontend/src/services/rechnungssuche.ts                # 0
grep -c '^import' frontend/src/services/rechnungssuche.ts                                          # 0
ls backend/tests/test_paket4_1.py frontend/tests/unit/rechnungsreiter.check.ts frontend/tests/unit/bestellverlauf.check.ts frontend/tests/unit/p41d-berlin.check.ts 2>&1 | grep -c 'No such file'   # 4
```

- [ ] **Baseline:** Block aus „Global Constraints“ (Baseline) ausführen → `15`. Dann Prozedur V auf der Basis → `14 failed, 2030 passed, 2 skipped, 1 error` (auf `1e2238b`), Abgleich leer. Die Summenzeile gehört als `<B>` in den Bericht. Abweichung bei den Namen: stoppen und melden.

---

## Abschnitt R — Cent-Rundung in der Anlage „Enthaltene Lieferscheine“ — Tasks 1–3 (R.1–R.3)

> **Rahmen:** Hinweis für Worker, Arbeitsort, Python, Commits, Stoppregeln 1–5, Baseline und Prozedur V stehen im Kopf (Global Constraints). R läuft als Erstes: Task 1 legt die gemeinsame Testdatei an. Die Abschlussmeldung in Task 3 (R.3) ist ein Zwischenstand — **nicht anhalten**. Abnahme R und Offene Punkte R stehen am Ende des Plans (Manager-Arbeit).

**Ziel R:** Die Anlage „Enthaltene Lieferscheine“ einer Sammel- bzw. Monatsrechnung (Rechnungs-PDF und `GET /api/v1/invoices/{id}/delivery-notes`) summiert sich **exakt** zum Netto der Positionen, aus denen sie stammt. Bisher rundete jeder Lieferschein „Menge × Einzelpreis × (1 − Positionsrabatt)“ für sich; immer wenn dieser Betrag kein ganzer Centbetrag ist — Einzelpreis mit 3–4 Nachkommastellen, Positionsrabatt **oder Bruchmenge, auch bei Centpreisen** (Menge `Numeric(10,3)`, z. B. 0,125 × 2,50 €) —, konnte die Summe der Anlage Cent neben dem Rechnungsnetto liegen (Restpunkt „Rundung ±1 Cent in der LS-Anlage“ aus der Paket-4-Abnahme, Spec `2026-10-08-gernot-feedback-abgleich.md`, Eintrag „Paket 4 live“, „Offen (niedrig)“). Danach verteilt jede Position ihren gedruckten Zeilenbetrag exakt auf ihre Lieferscheine, und gerundet wird einmal je Rechnung nach dem Größte-Reste-Verfahren. Festgeschriebene Rechnungen ändern sich in der Datenbank nicht; nur die Anzeige der Anlage wird rechnerisch konsistent.

**Architecture:** Keine Schemaänderung, keine Migration (`tenancy._auto_migrate` unberührt), kein neuer Endpunkt, **kein Frontend**. Nur `backend/app/services/invoice_service.py`: neue reine Funktion `auf_cent_verteilen` (R.1), neuer Rumpf von `netto_je_lieferschein` (R.2). Die beiden Aufrufer bleiben unverändert: `pdf_service.PDFService.generate_invoice_pdf` (Anlage nur bei `invoice.order_id is None`) und `invoices.invoice_delivery_notes` (`GET /invoices/{id}/delivery-notes`). Tests nur in `backend/tests/test_paket4_1.py` (Klassen `TestP41R…`, Helfer `_p41r_…`, Konstanten `_P41R_…`).

**Tech Stack:** FastAPI + SQLAlchemy 2.0, SQLite je Mandant; `fractions.Fraction` und `math` aus der Standardbibliothek (keine neue Abhängigkeit; Hypothesis ist nicht installiert → feste Zufallstabelle mit Startwert).

**Ausgangsstand R:** `main` @ `1e2238b` (= Produktion seit 09.10. 23:07); R läuft im Gesamtplan als Erstes, also auf der Basis. Blob `backend/app/services/invoice_service.py` = `681b0a4a6bf5eab8a0a6247581397a7d4c391d18`. Alle Anker gemessen (Vorbereitung im Kopf, „Ausgangsstand R“).

### Befund (am Code geprüft, in Kopien auf `1e2238b` gemessen; Produktion in dieser Planung **nicht** gemessen)

- **Rechenweg heute** (`invoice_service.netto_je_lieferschein`): Sammelrechnung — je `invoice_line_sources`-Zeile `quantity × unit_price × (1 − discount_percent/100)` der Position, je Lieferschein summiert, **je Lieferschein** auf Cent gerundet (`ROUND_HALF_UP`). Rechnung aus Bestellung (S6, ein Lieferschein, keine Quellen) — Summe der `line_total` der Positionen mit `order_item_id` aus der Bestellung (schon Cent, stimmig). Die Position selbst rundet einmal: `InvoiceLine.calculate_line_total` → `line_total` (Numeric(12,2)), das PDF druckt `line_total` in „Gesamt (Netto)“; `steuer_je_satz` summiert die gerundeten Zeilenbeträge. Einzelpreis `Numeric(10,4)`, Menge `Numeric(10,3)`, Positionsrabatt `Numeric(5,2)`.
- **Gemessen** (Kopie `/tmp/p41-kopie-R`, Zeile „Bruchmenge“ in `/tmp/p41-kopie-rfix-probe`; Sammellauf `POST /invoices/batch-run/commit`, Anlage über `GET /invoices/{id}/delivery-notes` und PDF-Text):

  | Fall | Netto der Positionen | Anlage bisher | Anlage nach R |
  |---|---|---|---|
  | 2 LS × 1 × 1,005 € | 2,01 | 1,01 + 1,01 = **2,02** | 1,01 + 1,00 |
  | 2 LS × 1 × 0,3333 € | 0,67 | 0,33 + 0,33 = **0,66** | 0,34 + 0,33 |
  | 2 LS × 1 × 1,00 €, Positionsrabatt 33,33 % | 1,33 | 0,67 + 0,67 = **1,34** | 0,67 + 0,66 |
  | 2 LS × 0,125 × 2,50 € (Centpreis, Bruchmenge) | 0,63 | 0,31 + 0,31 = **0,62** | 0,32 + 0,31 |
  | 3 LS × 1 × 1,005 € | 3,02 | 3 × 1,01 = **3,03** | 1,01 + 1,01 + 1,00 |
  | 2 LS × 20 Sorten × 1 × 0,3333 € | 13,40 | 6,67 + 6,67 = **13,34** (6 Cent) | 6,70 + 6,70 |
  | 3 und 1 × 0,3333 € | 1,33 | 1,00 + 0,33 (stimmte) | 1,00 + 0,33 |
  | Centpreise, ganze Mengen (10 × 2,50; 5 × 2,50 + 3 × 3,00) | 46,50 | 25,00 + 21,50 (stimmte) | 25,00 + 21,50 |

  Die Abweichung ist nicht auf ±1 Cent begrenzt: sie wächst mit der Zahl der Positionen (Zeile „20 Sorten“: 6 Cent). Ursache ist nicht der Preis allein: Betroffen ist jede Quelle, deren Menge × Einzelpreis × (1 − Positionsrabatt) kein ganzer Centbetrag ist — auch ein Centpreis mit Bruchmenge (Menge `Numeric(10,3)`, Zeile „Bruchmenge“). Unverändert bleiben nur Anlagen, deren Quellbeträge alle ganze Cent sind. Maßgeblich ist der Betrag der Quelle, nicht der der Position: 2 × 1,005 = 2,01 ist ein ganzer Centbetrag, je Lieferschein 1,005 aber nicht.
- **Wo die Anlage erscheint:** PDF nur bei `invoice.order_id is None` (Sammel-/Monatsrechnung; Tabelle „Lieferschein | Lieferdatum | Betrag (netto)“, Format `1.01 EUR`, Zeilen in Abfragereihenfolge); API `GET /invoices/{id}/delivery-notes` (`betrag_netto`). Das Frontend ruft den Endpunkt nicht auf (`sammelrechnungApi.deliveryNotes` ist definiert, `grep` findet keinen Aufruf) → keine Oberfläche betroffen, kein `tsc`/Build nötig.
- **Gesamtrabatt / Bonus:** Der Rabatt auf die ganze Rechnung kommt aus dem Kundenrabatt (`create_invoice` übernimmt `customer.discount_percent`, auch im Sammel- und Monatslauf). Das PDF zeigt dann „Zwischensumme“, „<Bezeichnung aus der Vorlage> (x %)“ — z. B. „Jahresbonus und Verpackungspauschale“ (`document_template.discount_label`) — und „Netto“. Er wird je Steuersatz gerundet und mindert Pfand bei `pfand_rabattfrei` nicht (`steuer_je_satz`). Bonus**zeilen** mit negativem Betrag gibt es nicht: Positionen über die API haben Menge > 0 und Preis ≥ 0 (`_positionsmenge`, `_positionseinzelpreis`), Bestellpositionen ebenso (`gt=0`, `ge=0`). Die Anlage rechnete schon bisher **vor** dem Gesamtrabatt (Docstring „Kopfrabatt bleibt außen vor“).
- **Wege zur Anlage:** Gernots Weg ist der Monatslauf (Rechnungen → „Monatsrechnungen“, `monatsrechnung_service`); der Sammellauf `POST /invoices/batch-run/commit` hat keine Oberfläche. Beide legen über dieselbe Funktion `_sammelrechnung_anlegen` an: je Schlüssel (Text, Einheit, Preis, Satz, Produkt, Positionsrabatt) **eine** Position, je Lieferschein eine `invoice_line_sources`-Zeile. Die Tests nutzen den Sammellauf (kein Kundenmodus, kein Monatsende nötig).
- **Von Hand ergänzte Positionen** (z. B. „Verpackungspauschale“ im Entwurf) haben keine Quelle und stehen in keiner Anlagezeile.
- **Storno:** `cancel_invoice` kopiert die Positionen mit negativer Menge **ohne** `invoice_line_sources` und gibt die Lieferscheine frei (`invoice_id = None`). Die Stornorechnung hat damit keine Anlage; negative Zeilen erreichen `netto_je_lieferschein` nie. Nebenbefund: Auch das stornierte Original zeigt danach keine Anlage mehr (Offener Punkt 2).
- **Leergutbelege** (`leergut_service.belege_anlegen`): Positionen ohne Quellen, keine Lieferscheine zugeordnet → keine Anlage.
- **Mengen der Quellen** sind > 0 (aus Bestellpositionen, `gt=0`). Seit B-E6 (Paket 4) ist die Menge einer Sammelposition nicht mehr änderbar (409); vorher konnte `line_total` von „Summe Quellen × Preis“ abweichen (Probe Paket 4: Menge 20 → 15, Anlage 25 + 25 gegen 37,50).
- **Nebenbefund PDF-Positionstabelle:** Der Einzelpreis wird mit zwei Nachkommastellen gedruckt (`f"{line.unit_price:.2f} €"`): 1,005 € erscheint als „1.00 €“ neben „Gesamt 2.01 €“ (Offener Punkt 1, nicht Teil von R).
- **Nebenbefund Vorschau Monats-/Sammellauf:** `monatsrechnung_service._summe_netto` und `invoices.batch_run_preview` summieren Menge × Preis × (1 − Rabatt) je Position **ohne** Rundung je Position. Gemessen (Kopie `/tmp/p41-kopie-rfix-probe`, 2 LS × 20 Sorten × 1 × 0,3333 €, ohne Kundenrabatt): `summe_netto` = `13.332` in `GET /invoices/monthly-proposals` und `POST /invoices/batch-run/preview`; der Dialog „Monatsrechnungen“ zeigt per `toFixed(2)` „13.33 € netto“ (`MonatsrechnungenDialog.tsx`), der angelegte Entwurf hat `subtotal` 13,40. Gernots Weg, aber außerhalb der Anlage → Offener Punkt 7, nicht Teil von R.
- **Nebenbefund Lieferschein mit Preisspalten** (`Customer.show_prices_on_delivery_note`): `OrderLine.line_net` entsteht mit `quantize(Decimal("0.01"))` **ohne** `rounding` (`sales._calculate_line_amounts`, ebenso `OrderLine.calculate_line_totals`), also `ROUND_HALF_EVEN` (Standardkontext, die App ändert ihn nirgends); die Rechnungsposition rundet `ROUND_HALF_UP`. Gemessen: 1 × 1,005 € → Bestellposition `line_net` 1,00, Lieferschein-PDF „1.00 €“ in Einzelpreis, Gesamt und Zwischensumme; die Sammelrechnung aus zwei solchen Lieferscheinen hat Position 2,01, Anlage nach R 1,01 + 1,00. Altbestand, von R nicht verursacht → Offener Punkt 8.
- **Produktion:** in dieser Planung nicht gelesen (der SSH-Lesezugriff wurde von der Rechteprüfung der Sitzung abgelehnt). Stand laut Plan Paket 4 (09.10.): Rechnungsentwürfe mit Quellen `0`, Lieferscheine 10 `ENTWURF` (2 berechnet, über „Rechnung aus Bestellung“), 1 `GELIEFERT`; der erste Monatsentwurf entsteht am 01.11. Vermutlich gibt es in `minga` noch keine Rechnung mit gedruckter Anlage — **nachmessen in R-A0** (Skript vollständig im Plan, R-W).

### Entscheidungen (Manager, im Plan getroffen)

- **R-E1 — Verfahren: Positionsbetrag mengenanteilig verteilen, einmal je Rechnung nach größten Resten runden (Hare-Niemeyer).**
  1. Jede Position mit Quellen verteilt ihren **gedruckten** Zeilenbetrag `line_total` exakt (Bruchrechnung, `Fraction`) auf ihre Lieferscheine, im Verhältnis der Quellmengen. Alle Quellen einer Position haben denselben Preis und Rabatt — das Mengenverhältnis ist das Betragsverhältnis, ohne Division durch einen Preis von 0.
  2. Die exakten Anteile werden je Lieferschein summiert (dazu bei Rechnung aus Bestellung die `line_total` der Bestellpositionen).
  3. `auf_cent_verteilen`: jeden Lieferscheinbetrag auf den Cent **abrunden**; die Cent, die zur Summe fehlen (immer 0 bis Anzahl Lieferscheine − 1, weil die Summe ein ganzer Centbetrag ist), gehen einzeln an die Lieferscheine mit dem größten abgeschnittenen Rest; bei gleichem Rest zuerst an die kleinere Lieferscheinnummer (`LS-JJJJMMTT-NNNN`, chronologisch, wie `waehle_vertreter`), dann an die kleinere ID.

  Begründung: (a) **Summe exakt** = Summe der Zeilenbeträge, die das PDF druckt, für jede Eingabe (Konstruktion, Zufallstabelle 1000 Fälle). (b) **Jeder Lieferschein liegt weniger als 1 Cent neben seinem Anteil**; der Anteil weicht von „Menge × Preis“ nur um die eigene Rundung der Position ab, mengenanteilig — die Rundung wird dem Lieferschein zugeschrieben, aus dem sie stammt. (c) **Ganze Centbeträge ändern nichts:** Ist Menge × Preis × (1 − Rabatt) jeder Quelle ein ganzer Centbetrag (z. B. Centpreise mit ganzen Mengen), sind alle Anteile ganze Cent, es fehlt kein Cent, die Anlage bleibt wie bisher und das PDF byte-gleich (gemessen: Fall „centpreise“, Bestandstests, PDF-Hash). Centpreise mit Bruchmengen sind dagegen betroffen und werden korrigiert (Fall „bruchmenge_centpreis“: bisher 0,31 + 0,31 = 0,62 gegen 0,63, nach R 0,32 + 0,31). (d) **Deterministisch:** exakte Bruchrechnung, Entscheidung nur nach Rest und Nummer — gleiche Eingabe, gleiche Aufteilung, unabhängig von der Reihenfolge der Datenbankabfrage (Test `umgekehrt == ergebnis`). Das PDF entsteht bei jedem Abruf neu; es darf nicht von der Abfragereihenfolge abhängen. (e) Verständlich: „Restcent an den größten Rest“ ist das übliche Verfahren (Sitzzuteilung Hare-Niemeyer).

  Verworfen (gemessen mit 20 Positionen zu 0,3333 € auf 2 Lieferscheinen, Rechnung 13,40 €, exakt je LS 6,666 €): **Größte Reste je Position** — jede Position hat denselben Gleichstand, der Restcent geht 20-mal an denselben Lieferschein: 6,80 + 6,60 (13 Cent neben dem Anteil). **Kumulative Rundung je Position** — ebenso 6,80 + 6,60 und von der Reihenfolge abhängig. **Rest auf den letzten Lieferschein** — mehrere Cent auf einem Beleg. **Unverändert lassen, Hinweis „Rundungsdifferenz“** — die Anlage gehört zur Rechnung (§ 31 Abs. 1 UStDV, B-E2(b)); eine Summe, die nicht zur Rechnung passt, ist für den Prüfer nicht nachvollziehbar.
- **R-E2 — Ziel ist das Netto der Positionen vor dem Gesamtrabatt.** Die Anlage summiert sich zur Summe der `line_total` der Positionen mit Lieferschein: ohne Gesamtrabatt = „Netto“, mit Gesamtrabatt = „Zwischensumme“ im Summenblock (Test `test_rechnungsrabatt_bleibt_ausserhalb_der_anlage`: 1,01 + 1,00 = 2,01 = 1,95 + 0,06). Begründung: (a) Die Anlage weist Lieferungen aus; ihr Betrag ist der Anteil des Lieferscheins an den Rechnungspositionen — Liefermenge × Preis der Rechnungsposition, nach Positionsrabatt, auf weniger als 1 Cent genau. Er ist nicht in jedem Fall gleich dem „Gesamt (Netto)“ bzw. der „Zwischensumme“ eines Lieferscheins mit Preisspalten: Der rundet je Bestellposition `ROUND_HALF_EVEN` (1 × 1,005 € steht dort als 1,00 €, in der Anlage nach R als 1,01 bzw. 1,00; Altbestand, Offener Punkt 8). Der Gesamtrabatt („Jahresbonus und Verpackungspauschale“) ist eine Entgeltminderung auf die ganze Rechnung (§ 14 Abs. 4 Nr. 7 UStG), je Steuersatz gerundet und für Pfand ggf. nicht anwendbar — ihn auf Lieferscheine umzulegen, schüfe eine dritte Rundungsebene und Beträge, die niemand nachrechnen kann. (b) Wie bisher (Docstring), keine Änderung am Layout. Von Hand ergänzte Positionen bleiben außerhalb der Anlage (Test `test_position_ohne_lieferschein_nicht_in_der_anlage`).
- **R-E3 — Keine Datenänderung, keine Layoutänderung.** Keine neue Spalte, keine Summenzeile, Spaltenkopf und Zahlformat (`1.01 EUR`) bleiben. So bleibt jedes PDF, dessen Anlage nicht betroffen ist, byte-gleich (gemessen mit `pdf_vergleich.py`, Text in R-W). Bei betroffenen **festgeschriebenen** Rechnungen zeigt der erneute Abruf andere Cent in der Anlage — Beträge, Summen und Steuer der Rechnung bleiben unverändert. Deshalb misst R-A0 vor dem Deploy, ob es solche Rechnungen in `minga` gibt; wenn ja, werden ihre PDFs vorher archiviert (wie bei A-R1) und der Nutzer entscheidet (Stoppregel für den Deploy, nicht für den Worker). Eine Summenzeile oder der Hinweis „vor Rabatt“ im Spaltenkopf ist Offener Punkt 3.
- **R-E4 — Randfälle in `netto_je_lieferschein`:** Ein Lieferschein, der eine Quelle hat, aber nicht (mehr) an der Rechnung hängt, bekommt seinen Anteil trotzdem (er wird nur nicht ausgegeben) — sonst rutschte sein Betrag auf die anderen. Hat eine Position die Quellmenge 0 (nur in Altdaten denkbar), teilen sich ihre Quellen den Betrag zu gleichen Teilen. Rechnung aus Bestellung: unverändert (Wächter).
- **R-E5 — Kein Frontend:** Die Oberfläche zeigt die Anlage nirgends (nur PDF); `api.ts` bleibt.

### Überschneidungen mit den anderen Abschnitten von Paket 4.1

| Datei | R (Task: Anker) | andere Abschnitte | Ergebnis |
|---|---|---|---|
| `backend/tests/test_paket4_1.py` | R.1 Kopf, falls die Datei fehlt; R.1 und R.2 hängen ans Dateiende | V, Z, D hängen ebenfalls an | Präfixe `TestP41R…`/`_p41r_`/`_P41R_`; R importiert `auf_cent_verteilen` **im Test**, die Datei bleibt vor R.1 sammelbar |
| `backend/app/services/invoice_service.py` | R.1: Importzeile `from decimal import Decimal, ROUND_HALF_UP`, Zeile `def netto_je_lieferschein(…)`; R.2: Rumpf von `netto_je_lieferschein`, die Importzeilen aus R.1 | — (laut Auftrag berührt kein anderer Restpunkt die Rechnungslogik) | Ändert ein anderer Abschnitt diese Stellen: Stoppregel 1 |
| Lieferscheinnummer (Abschnitt D, LS-Nummer mit Berliner Datum) | R ändert keine Nummernlogik; die Tests lesen die Nummern aus der API-Antwort | D.1 (Task 4) ändert das Nummerndatum in `lieferschein_service.lieferschein_anlegen` (Berliner Tag; `naechste_belegnummer` nur im Docstring) | R setzt nur voraus: ein später angelegter Lieferschein hat am selben Tag die größere Nummer (Rang bei gleichem Rest). D ändert das nicht (Gesamt-Nachspiel: R-Klassen nach D in jedem Vollauf grün); sonst verschöben sich in `_P41R_FAELLE` die Cent zwischen den Lieferscheinen → Stoppregel 2 |

### Prüfstand (alles in Kopien unter `/tmp`, Repo und Produktion unverändert)

- **Entwicklung** in `/tmp/p41-kopie-R` (`git archive 1e2238b`, `frontend/node_modules` als Symlink): Prozedur V Basis `14 failed, 2030 passed, 2 skipped, 1 error`, Namen = Baseline. Probe vor der Änderung: 2 Lieferscheine × 1 × 1,005 € → Position 2,01, Anlage `1.01 EUR` + `1.01 EUR` (API und PDF-Text). Rot/Grün wie in den Steps; Bestand `229 passed`; V nach R `2047`, Namen = Baseline (Stand vor der Revision, ohne Fall „bruchmenge_centpreis“).
- **Nachspiel aus dem Plantext** (Stand dieser Fassung: `/tmp/p41-skripte/rfix/nachspiel2.py` zerlegt diese Datei in ihre 11 Python-Blöcke, wendet sie mechanisch an — jeder Anker genau einmal gefunden — und führt die Prüfbefehle der Steps wörtlich aus, den Rot-/Grün-Befehl aus R.2 Step 2 zeichengleich; Protokoll `/tmp/p41-skripte/rfix/nachspiel2.log`) in `/tmp/p41-kopie-rfix` (frisches `git archive 1e2238b`): Vorbereitung `1`, `1`, `2`, `0`, `…invoices.py:2`/`…pdf_service.py:2`, `0`; V Basis `2030`. R.1 Rot `5 failed` (alle `ImportError`) → Zählungen `1`/`1`/`1`/`1` → `5 passed`, ruff Exit 0, V `2035`. R.2 Rot `8 failed, 5 passed`, die acht Namen und neun Meldungen aus Step 2 (Zeilen 5/6 dort in der Reihenfolge `0001`, `0002`; im Lauf davor `0002`, `0001` — daher der Hinweis in Step 2), Bestand vor R.2 `229 passed`, Zählungen `0`/`2`/`1` → `13 passed`, nach `--- Meldungen` leer, Bestand `229 passed`, ruff F821/F823 Exit 0, F401 `6` (ohne `ROUND_HALF_UP`), V `2048`. Namen in allen drei Vollläufen = Baseline. R.3 `18 passed`. Gegenüber `1e2238b` ist nur `backend/app/services/invoice_service.py` geändert und `backend/tests/test_paket4_1.py` neu, `frontend/src` unverändert (`diff -rq`). Gegenüber der vorigen Fassung (Nachspiel `/tmp/p41-kopie-R-nachspiel`, `/tmp/p41-kopie-rrev`) unterscheiden sich nur der Docstring von `netto_je_lieferschein` und der Fall „bruchmenge_centpreis“ samt Kommentar.
- **Nebenbefunde nachgemessen** (Kopie `/tmp/p41-kopie-rfix-probe`, Basiscode): Bruchmenge 2 × 0,125 × 2,50 € → Position `0.250 × 2.5000 = 0.63`, Anlage `0.31` + `0.31`; Vorschau 20 Sorten `summe_netto` `13.332` (Monats- und Sammellauf), Monatsentwurf `subtotal` `13.40`; Kunde mit Preisspalten, 1 × 1,005 € → Bestellposition `line_net` `1.00`, Lieferschein-PDF „1.00 €“ (Einzelpreis, Gesamt, Zwischensumme), Sammelrechnung aus zwei solchen LS Position `2.01`.
- **Verfahrensvergleich** (gemessen mit `auf_cent_verteilen`): 20 Positionen zu je 0,67 € auf 2 Lieferscheinen — größte Reste je Position 6,80 + 6,60, kumulative Rundung je Position 6,80 + 6,60, größte Reste je Rechnung (R-E1) 6,70 + 6,70.
- **Abnahme-Werkzeuge lokal geprüft:** Die drei Blöcke aus R-W wörtlich in `bash` ausgeführt → Hashes `17f9b26a23e367a5`/`47ac5e2196b7c331`, `ok`. Probe-DB `/tmp/p41-skripte/rfix/probe-minga.db` (`chmod 444`) aus den R-Helfern: 1,005 € zweimal, festgeschrieben als `RE-2026-00001`; 20 Sorten, Centpreise mit ganzen Mengen, Bruchmenge 0,125 × 2,50 € als Entwürfe; Rechnung aus Bestellung. `prod_r0.py` (stdin-Form wie per `ssh`, DB als Argument): Zeile 5 `invoice_lines` „nicht in ganzen Cent“ `21` (die festgeschriebene 1,005-Rechnung fehlt dort: 2 × 1,005 = 2,01), Quellen `47 | 44`, Zeile 6 `0`, Zeile 7 `5 | … 3 [('RE-2026-00001', 'OFFEN'), ('ENTWURF-…', 'ENTWURF'), ('ENTWURF-…', 'ENTWURF')]`. Auf der älteren Probe-DB (`/tmp/p41-skripte/probe-minga-ro.db`, vier Rechnungen ohne Bruchmenge) Zeile 7 wie mit dem vorigen Skript: `4 | … 2 [('RE-2026-00001', 'OFFEN'), ('ENTWURF-…', 'ENTWURF')]`. `pdf_vergleich.py` mit Basis- (`/tmp/p41-kopie-rfix-probe`) und R-Code (`/tmp/p41-kopie-rfix`): 2 PDF-Hashes gleich (Centpreise mit ganzen Mengen, Rechnung aus Bestellung), 3 verschieden — genau die drei aus Zeile 7; mit R-Code „anlage“ = „positionen“ bei allen vier Sammelrechnungen (vorher 0,62 statt 0,63, 13,34 statt 13,40, 2,02 statt 2,01).
- **Nicht gemessen:** Produktion (R-A0; der SSH-Lesezugriff wurde in dieser Planung von der Rechteprüfung abgelehnt), Commits (Kopien ohne Git), Oberfläche im Browser (R-A2), Zusammenspiel mit den Abschnitten V, Z, D (getrennt geplant, Überschneidungen oben), Frontend-Build (nichts im Frontend geändert).

### Prozedur V in R

Befehl aus dem Kopf (Prozedur V). N steigt durch R um **+5** (R.1) und **+13** (R.2); R.3 **+0**. Im Gesamtplan (R als Erstes, auf `1e2238b`): 2030 → 2035 → 2048. Maßgeblich sind die Namen.

### Vorbereitung R

Im Kopf erledigt („Vorbereitung (vor Task 1)“: Basis, Baseline, „Ausgangsstand R“, Prozedur V auf der Basis). `<Basis-R>` = `<Basis>`; `<N-vor-R>` = N der Basis (auf `1e2238b` `2030`).

---

### Task 1 (R.1): Reine Funktion `auf_cent_verteilen` — Cent nach größten Resten, Summe exakt

**Files:**
- Modify: `backend/app/services/invoice_service.py` (Importzeile `from decimal import …`; neue Funktion direkt vor `def netto_je_lieferschein(`)
- Create/Modify: `backend/tests/test_paket4_1.py` (Kopf, falls die Datei fehlt; Block R.1 ans Dateiende)

**Interfaces:**
- Produces (`app.services.invoice_service`): `auf_cent_verteilen(anteile: dict, rang: dict) -> dict` — `anteile`: Schlüssel → exakter Betrag in Euro (`Fraction`, `Decimal` oder `int`), Summe ein ganzer Centbetrag; `rang`: Schlüssel → sortierbarer Wert für Gleichstände. Ergebnis: Schlüssel → `Decimal` mit genau zwei Nachkommastellen; Summe = Summe der Anteile; jedes Ergebnis weniger als 1 Cent neben seinem Anteil; Anteile in ganzen Cent unverändert; unabhängig von der Reihenfolge der Eingabe.
- Consumes: nichts (reine Funktion, keine Datenbank).
- Unverändert: `netto_je_lieferschein` (erst R.2 ruft die Funktion).

**Review Focus (R.1):** Gleichstand geht an den kleineren Rang; negative Anteile (nur Funktionstest, in Rechnungen nicht erreichbar) runden ebenfalls nach unten und behalten die Summe.

- [ ] **Step 1: Testdatei.** Kopf, nur wenn `backend/tests/test_paket4_1.py` noch fehlt (auf der Basis fehlt sie — Task 1 legt sie mit genau diesem Inhalt an; besteht sie schon, kein Stopp, nur vermerken):

```python
"""Paket 4.1 — Restpunkte aus der Paket-4-Abnahme (10.10.2026).

Gemeinsame Testdatei aller Abschnitte. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP41V…/_p41v_, TestP41Z…/_p41z_, TestP41R…/_p41r_,
TestP41D…/_p41d_): ein gleichnamiger Helfer würde still ersetzt. Jeder
Abschnitt bringt seine Importe selbst mit. Keine autouse-Fixture.
"""
```

Dann diesen Block ans Dateiende von `backend/tests/test_paket4_1.py` anhängen:

```python


# ============================================================
# R — Cent-Rundung in der Anlage „Enthaltene Lieferscheine“
# ============================================================

import random as _p41r_random
from decimal import Decimal as _P41R_Decimal
from fractions import Fraction as _P41R_Fraction


def _p41r_euro(text):
    return _P41R_Decimal(text)


def _p41r_verteilen(anteile, rang=None):
    """auf_cent_verteilen mit Rang = Schlüssel. Import im Test: Vor R.1 gibt es
    die Funktion nicht, die gemeinsame Datei bleibt trotzdem sammelbar."""
    from app.services.invoice_service import auf_cent_verteilen
    return auf_cent_verteilen(anteile, rang or {k: k for k in anteile})


class TestP41RCentVerteilung:
    """Größte-Reste-Verfahren: exakte Anteile → Cent, Summe bleibt exakt."""

    def test_exakte_centbetraege_unveraendert(self):
        ergebnis = _p41r_verteilen({"a": _P41R_Fraction("25"), "b": _P41R_Fraction("12.5")})

        assert ergebnis == {"a": _p41r_euro("25.00"), "b": _p41r_euro("12.50")}
        assert str(ergebnis["a"]) == "25.00"

    def test_restcent_an_den_groessten_rest(self):
        # 0,9975 + 0,3325 = 1,33: abgerundet 0,99 + 0,33, der fehlende Cent
        # geht an den größeren Rest (0,75 Cent gegen 0,25 Cent).
        ergebnis = _p41r_verteilen({"a": _P41R_Fraction("0.9975"), "b": _P41R_Fraction("0.3325")})

        assert ergebnis == {"a": _p41r_euro("1.00"), "b": _p41r_euro("0.33")}

    def test_gleicher_rest_kleinerer_rang_zuerst(self):
        anteile = {"x": _P41R_Fraction("1.005"), "y": _P41R_Fraction("1.005")}

        assert _p41r_verteilen(anteile, {"x": 2, "y": 1}) == {"x": _p41r_euro("1.00"), "y": _p41r_euro("1.01")}
        assert _p41r_verteilen(anteile, {"x": 1, "y": 2}) == {"x": _p41r_euro("1.01"), "y": _p41r_euro("1.00")}

    def test_negative_anteile(self):
        ergebnis = _p41r_verteilen({
            "a": _P41R_Fraction("1.005"), "b": _P41R_Fraction("-0.0025"), "c": _P41R_Fraction("0.0075"),
        })

        assert ergebnis == {"a": _p41r_euro("1.00"), "b": _p41r_euro("0.00"), "c": _p41r_euro("0.01")}

    def test_feste_zufallstabelle(self):
        """1000 Fälle aus festem Startwert (Hypothesis ist nicht installiert):
        Summe exakt, jeder Betrag weniger als 1 Cent vom Anteil, Ergebnis
        unabhängig von der Reihenfolge der Eingabe."""
        zufall = _p41r_random.Random(20261010)
        for fall in range(1000):
            n = zufall.randint(1, 7)
            ziel = _P41R_Fraction(zufall.randint(-500, 500_000), 100)
            teile = [_P41R_Fraction(zufall.randint(-10_000, 100_000_000), 10 ** zufall.randint(2, 7))
                     for _ in range(n - 1)]
            anteile = {f"LS-{i:04d}": t for i, t in enumerate(teile, 1)}
            anteile[f"LS-{n:04d}"] = ziel - sum(teile, _P41R_Fraction(0))

            ergebnis = _p41r_verteilen(anteile)
            umgekehrt = _p41r_verteilen(dict(reversed(list(anteile.items()))))

            assert _P41R_Fraction(sum(ergebnis.values(), _P41R_Decimal(0))) == ziel, fall
            assert all(abs(_P41R_Fraction(ergebnis[k]) - anteile[k]) < _P41R_Fraction(1, 100)
                       for k in anteile), fall
            assert all(ergebnis[k].as_tuple().exponent == -2 for k in anteile), fall
            assert umgekehrt == ergebnis, fall
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41RCentVerteilung -q -p no:cacheprovider 2>&1 | tail -8
```

Erwartet: `5 failed`. Alle fünf (`test_exakte_centbetraege_unveraendert`, `test_restcent_an_den_groessten_rest`, `test_gleicher_rest_kleinerer_rang_zuerst`, `test_negative_anteile`, `test_feste_zufallstabelle`) mit `ImportError: cannot import name 'auf_cent_verteilen' from 'app.services.invoice_service'`. Andere Klassen in der Datei (falls vorhanden) sammeln weiter.

- [ ] **Step 3: Implementierung.**

`backend/app/services/invoice_service.py` — Importzeile (Anker genau einmal):

```python
from decimal import Decimal, ROUND_HALF_UP
```

ersetzen durch

```python
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import math
```

`backend/app/services/invoice_service.py` — die Kopfzeile von `netto_je_lieferschein` (Anker genau einmal; die neue Funktion steht direkt davor, die Kopfzeile bleibt):

```python
def netto_je_lieferschein(db: Session, invoice: Invoice, lieferscheine: list[DeliveryNote]) -> dict[UUID, Decimal]:
```

ersetzen durch

```python
def auf_cent_verteilen(anteile: dict, rang: dict) -> dict:
    """Rundet exakte Anteile (in Euro) auf Cent, ohne ihre Summe zu ändern.

    Größte-Reste-Verfahren (Hare-Niemeyer): jeden Anteil auf den Cent
    abrunden; die Cent, die dann zur Summe fehlen, gehen einzeln an die
    Anteile mit dem größten abgeschnittenen Rest, bei gleichem Rest zuerst an
    den kleineren Rang (rang[k], z. B. die Lieferscheinnummer). Damit gilt:
    - Summe der Ergebnisse = Summe der Anteile (die ein ganzer Centbetrag ist),
    - jedes Ergebnis liegt weniger als 1 Cent neben seinem Anteil,
    - Anteile, die schon ganze Cent sind, bleiben unverändert,
    - gleiche Eingabe, gleiches Ergebnis — unabhängig von der Reihenfolge.
    Anteile exakt (Fraction, Decimal oder int; auch Drittel), Ergebnis
    Decimal mit zwei Nachkommastellen. Paket 4.1, R.
    """
    in_cent = {k: Fraction(v) * 100 for k, v in anteile.items()}
    cent = {k: math.floor(v) for k, v in in_cent.items()}
    fehlend = round(sum(in_cent.values(), Fraction(0))) - sum(cent.values())
    nach_rest = sorted(in_cent, key=lambda k: (cent[k] - in_cent[k], rang[k]))
    for k in nach_rest[:fehlend]:
        cent[k] += 1
    return {k: (Decimal(c) / 100).quantize(Decimal("0.01")) for k, c in cent.items()}


def netto_je_lieferschein(db: Session, invoice: Invoice, lieferscheine: list[DeliveryNote]) -> dict[UUID, Decimal]:
```

Prüfen:

```bash
F=backend/app/services/invoice_service.py
grep -c '^def auf_cent_verteilen(anteile: dict, rang: dict) -> dict:$' $F
grep -c '^from fractions import Fraction$' $F
grep -c '^import math$' $F
grep -c '^def netto_je_lieferschein(' $F
```

Erwartet: `1`, `1`, `1`, `1`.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `5 passed`.
- [ ] **Statisch:** `/opt/homebrew/bin/ruff check --select F821,F823 backend/app/services/invoice_service.py backend/tests/test_paket4_1.py` → keine Ausgabe, Exit 0.
- [ ] **Vollauf (Prozedur V):** `14 failed, N passed, 2 skipped, 1 error` mit N = `<N-vor-R>` + 5 (im Gesamtplan `2035`); Abgleich leer.
- [ ] **Commit:**

```bash
git add backend/app/services/invoice_service.py backend/tests/test_paket4_1.py
git commit -m "feat(rechnung): Cent-Verteilung nach größten Resten als reine Funktion (P41-R.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2 (R.2): Anlage „Enthaltene Lieferscheine“ summiert sich exakt zum Netto der Positionen

**Files:**
- Modify: `backend/app/services/invoice_service.py` (Rumpf von `netto_je_lieferschein`; Importzeilen aus R.1)
- Modify: `backend/tests/test_paket4_1.py` (Block R.2 ans Dateiende)

**Interfaces:**
- Produces: `netto_je_lieferschein(db, invoice, lieferscheine) -> dict[UUID, Decimal]` — Signatur und Rückgabetyp unverändert; Beträge mit zwei Nachkommastellen; Summe über alle Lieferscheine der Rechnung = Summe der `line_total` der Positionen mit Quellen (Sammelrechnung) bzw. der Positionen der Bestellung (Rechnung aus Bestellung); Gleichstand → kleinere Lieferscheinnummer.
- Consumes: `auf_cent_verteilen` (R.1); `InvoiceLineSource.invoice_line_id`, `.delivery_note_id`, `.quantity`; `InvoiceLine.line_total`; `DeliveryNote.delivery_note_number`.
- Unverändert: `pdf_service.generate_invoice_pdf` (Anlage, Spalten, Format `1.01 EUR`), `invoices.invoice_delivery_notes` (Felder, `betrag_netto`), `_aggregiere`, `_sammelrechnung_anlegen`, `cancel_invoice`, `leergut_service`, Frontend.

**Review Focus (R.2):** Ein betroffenes PDF zeigt in der Anlage dieselbe Summe wie „Netto“ (ohne Gesamtrabatt) bzw. „Zwischensumme“ (mit Gesamtrabatt); ein PDF, dessen Quellbeträge alle ganze Cent sind (Centpreise, ganze Mengen), bleibt byte-gleich (R-A1).

- [ ] **Step 1: Test.** Diesen Block ans Dateiende von `backend/tests/test_paket4_1.py` anhängen:

```python


import base64 as _p41r_base64
import re as _p41r_re
import zlib as _p41r_zlib

import pytest as _p41r_pytest

_P41R_MAERZ = {"period_from": "2026-03-01", "period_to": "2026-03-31"}


def _p41r_kunde(client, name="Gasthaus Rundung", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p41r_bestellung(client, kunde, tag, zeilen):
    """Bestellung im März 2026; zeilen = [(Text, Menge, Einzelpreis, Positionsrabatt %)], 7 %."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": f"2026-03-{tag:02d}",
        "lines": [{"product_name": text, "quantity": menge, "unit": "STK", "unit_price": preis,
                   "discount_percent": rabatt, "tax_rate": "REDUZIERT"}
                  for text, menge, preis, rabatt in zeilen],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p41r_lieferung(client, kunde, tag, zeilen):
    bestellung = _p41r_bestellung(client, kunde, tag, zeilen)
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
    assert r.status_code == 201, r.text
    return bestellung, r.json()["delivery_note_number"]


def _p41r_sammelrechnung(client, kunde, lieferungen):
    """Je Eintrag eine Bestellung mit Lieferschein (2., 9., 16. … März), dann
    der Sammellauf für den März. Gibt Rechnung (Entwurf) und LS-Nummern in
    Anlagereihenfolge zurück."""
    nummern = [_p41r_lieferung(client, kunde, 2 + 7 * i, zeilen)[1] for i, zeilen in enumerate(lieferungen)]
    r = client.post("/api/v1/invoices/batch-run/commit", json={**_P41R_MAERZ, "customer_ids": [kunde["id"]]})
    assert r.status_code == 201, r.text
    rechnungen = r.json()["rechnungen"]
    assert len(rechnungen) == 1, rechnungen
    return rechnungen[0], nummern


def _p41r_anlage(client, rechnung):
    """Netto je Lieferschein aus GET /invoices/{id}/delivery-notes (dieselbe
    Funktion wie die PDF-Anlage), nach Lieferscheinnummer."""
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return {ls["delivery_note_number"]: _P41R_Decimal(str(ls["betrag_netto"])).quantize(_P41R_Decimal("0.01"))
            for ls in r.json()}


def _p41r_rechnung(client, rechnung):
    r = client.get(f"/api/v1/invoices/{rechnung['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _p41r_dec(wert):
    return _P41R_Decimal(str(wert)).quantize(_P41R_Decimal("0.01"))


def _p41r_pdf_text(pdf_bytes):
    """Text grob aus dem PDF (ReportLab: Flate bzw. ASCII85+Flate), wie
    tests/test_documents_preise.py::_pdf_text."""
    teile, pos = [pdf_bytes], 0
    while True:
        start = pdf_bytes.find(b"stream", pos)
        if start == -1:
            break
        start = pdf_bytes.find(b"\n", start) + 1
        ende = pdf_bytes.find(b"endstream", start)
        if ende == -1:
            break
        stueck = pdf_bytes[start:ende].strip()
        for entpacken in (lambda d: _p41r_zlib.decompress(d),
                          lambda d: _p41r_zlib.decompress(_p41r_base64.a85decode(d, adobe=True))):
            try:
                teile.append(entpacken(stueck))
                break
            except Exception:
                continue
        pos = ende + 1
    return b"\n".join(teile)


def _p41r_pdf_anlage(client, rechnung):
    """Zeilen der PDF-Tabelle „Enthaltene Lieferscheine“: {LS-Nummer: Betrag}."""
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
    assert r.status_code == 200, r.text
    text = _p41r_pdf_text(r.content)
    abschnitt = text[text.index(b"(Enthaltene Lieferscheine) Tj"):]
    nummern = _p41r_re.findall(rb"\((LS-[0-9-]+)\) Tj", abschnitt)
    betraege = _p41r_re.findall(rb"\((-?[0-9]+\.[0-9]{2}) EUR\) Tj", abschnitt)
    assert len(nummern) == len(betraege) > 0, abschnitt
    return {n.decode(): _P41R_Decimal(b.decode()) for n, b in zip(nummern, betraege)}


_P41R_SORTEN = [(f"Sorte {i:02d}", 1, "0.3333", 0) for i in range(1, 21)]

# (Lieferungen, Netto der Positionen, Anlage je Lieferschein in LS-Reihenfolge)
_P41R_FAELLE = {
    # Befund Paket-4-Abnahme: Netto 2,01, Anlage bisher 1,01 + 1,01 = 2,02
    "preis_1_005_zweimal": ([[("Erbsen", 1, "1.005", 0)], [("Erbsen", 1, "1.005", 0)]],
                            "2.01", ["1.01", "1.00"]),
    # Netto 0,67, bisher 0,33 + 0,33 = 0,66
    "preis_0_3333_zweimal": ([[("Erbsen", 1, "0.3333", 0)], [("Erbsen", 1, "0.3333", 0)]],
                             "0.67", ["0.34", "0.33"]),
    # Positionsrabatt 33,33 %: Netto 1,33, bisher 0,67 + 0,67 = 1,34
    "rabatt_33_33_zweimal": ([[("Erbsen", 1, "1.00", "33.33")], [("Erbsen", 1, "1.00", "33.33")]],
                             "1.33", ["0.67", "0.66"]),
    # drei Lieferscheine, Netto 3,02 (3 × 1,005 = 3,015), bisher 3 × 1,01 = 3,03
    "preis_1_005_dreimal": ([[("Erbsen", 1, "1.005", 0)]] * 3, "3.02", ["1.01", "1.01", "1.00"]),
    # 20 Positionen mit je einem Restcent: verteilt je Rechnung, nicht je
    # Position — sonst bekäme der erste Lieferschein alle 20 (6,80 + 6,60).
    # Bisher 6,67 + 6,67 = 13,34 gegen 13,40.
    "zwanzig_sorten_0_3333": ([_P41R_SORTEN, _P41R_SORTEN], "13.40", ["6.70", "6.70"]),
    # Centpreis mit Bruchmenge (Menge Numeric(10,3)): je Lieferschein
    # 0,125 × 2,50 = 0,3125; Position 0,25 × 2,50 = 0,625 → 0,63.
    # Bisher 0,31 + 0,31 = 0,62.
    "bruchmenge_centpreis": ([[("Erbsen", "0.125", "2.50", 0)], [("Erbsen", "0.125", "2.50", 0)]],
                             "0.63", ["0.32", "0.31"]),
    # Wächter: ungleiche Mengen, Rest schon bisher stimmig
    "mengen_3_und_1_zu_0_3333": ([[("Erbsen", 3, "0.3333", 0)], [("Erbsen", 1, "0.3333", 0)]],
                                 "1.33", ["1.00", "0.33"]),
    # Wächter: Centpreise mit ganzen Mengen — Anlage genau wie bisher
    "centpreise": ([[("Erbsen", 10, "2.50", 0)], [("Erbsen", 5, "2.50", 0), ("Erbsen", 3, "3.00", 0)]],
                   "46.50", ["25.00", "21.50"]),
}


class TestP41RAnlageSammelrechnung:
    """Die Anlage „Enthaltene Lieferscheine“ summiert sich exakt zum Netto
    der Positionen; jeder Lieferschein liegt weniger als 1 Cent neben seinem
    Anteil. Feste Tabelle mit den Beispielen der Paket-4-Abnahme."""

    @_p41r_pytest.mark.parametrize("fall", list(_P41R_FAELLE))
    def test_anlage_summiert_zum_positionsnetto(self, client, fall):
        lieferungen, netto, erwartet = _P41R_FAELLE[fall]
        kunde = _p41r_kunde(client)
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, lieferungen)

        detail = _p41r_rechnung(client, rechnung)
        anlage = _p41r_anlage(client, rechnung)

        assert _p41r_dec(detail["subtotal"]) == _p41r_euro(netto)
        assert sum(_p41r_dec(l["line_total"]) for l in detail["lines"]) == _p41r_euro(netto)
        assert anlage == {nr: _p41r_euro(b) for nr, b in zip(nummern, erwartet)}
        assert sum(anlage.values()) == _p41r_euro(netto)


class TestP41RAnlageRandfaelle:
    """PDF, Rechnungsrabatt, Positionen ohne Lieferschein, Rechnung aus
    Bestellung, Stornorechnung."""

    def test_pdf_anlage_summiert_zum_netto(self, client):
        kunde = _p41r_kunde(client)
        lieferungen, netto, erwartet = _P41R_FAELLE["preis_1_005_zweimal"]
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, lieferungen)

        anlage = _p41r_pdf_anlage(client, rechnung)

        assert anlage == {nr: _p41r_euro(b) for nr, b in zip(nummern, erwartet)}
        assert sum(anlage.values()) == _p41r_dec(_p41r_rechnung(client, rechnung)["subtotal"])

    def test_rechnungsrabatt_bleibt_ausserhalb_der_anlage(self, client):
        """Kundenrabatt 3 % (im PDF z. B. „Jahresbonus und Verpackungspauschale“):
        die Anlage zeigt die Lieferungen vor dem Rechnungsrabatt und summiert
        sich zur Zwischensumme = Netto + Rabatt."""
        kunde = _p41r_kunde(client, discount_percent=3)
        lieferungen, _, erwartet = _P41R_FAELLE["preis_1_005_zweimal"]
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, lieferungen)

        detail = _p41r_rechnung(client, rechnung)
        anlage = _p41r_anlage(client, rechnung)

        assert (_p41r_dec(detail["subtotal"]), _p41r_dec(detail["discount_amount"])) == (
            _p41r_euro("1.95"), _p41r_euro("0.06"))
        assert anlage == {nr: _p41r_euro(b) for nr, b in zip(nummern, erwartet)}
        assert sum(anlage.values()) == _p41r_dec(detail["subtotal"]) + _p41r_dec(detail["discount_amount"])

    def test_position_ohne_lieferschein_nicht_in_der_anlage(self, client):
        """Wächter: eine von Hand ergänzte Position gehört zu keinem Lieferschein."""
        kunde = _p41r_kunde(client)
        rechnung, nummern = _p41r_sammelrechnung(client, kunde, [
            [("Erbsen", 10, "2.50", 0)], [("Erbsen", 5, "2.50", 0)]])
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Verpackungspauschale", "quantity": 1, "unit": "STK",
            "unit_price": "5.00", "tax_rate": "REDUZIERT"})
        assert r.status_code in (200, 201), r.text

        assert _p41r_dec(_p41r_rechnung(client, rechnung)["subtotal"]) == _p41r_euro("42.50")
        assert _p41r_anlage(client, rechnung) == {
            nummern[0]: _p41r_euro("25.00"), nummern[1]: _p41r_euro("12.50")}

    def test_rechnung_aus_bestellung_unveraendert(self, client):
        """Wächter: ohne invoice_line_sources zählt die Summe der Positionen."""
        kunde = _p41r_kunde(client)
        bestellung, nummer = _p41r_lieferung(client, kunde, 2, [("Erbsen", 2, "1.005", 0)])
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text

        assert _p41r_anlage(client, r.json()) == {nummer: _p41r_euro("2.01")}

    def test_stornorechnung_ohne_anlage(self, client):
        """Wächter: die Stornorechnung (negative Positionen) hat keine
        Lieferscheine und keine Herkunft je Lieferschein."""
        kunde = _p41r_kunde(client)
        lieferungen, _, _ = _P41R_FAELLE["preis_1_005_zweimal"]
        rechnung, _ = _p41r_sammelrechnung(client, kunde, lieferungen)
        assert client.post(f"/api/v1/invoices/{rechnung['id']}/finalize").status_code == 200
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel", json={
            "reason": "Preisfehler", "reason_code": "PREISFEHLER"})
        assert r.status_code == 200, r.text
        storno_id = r.json()["credit_note"]["id"]

        assert _p41r_anlage(client, {"id": storno_id}) == {}
```

- [ ] **Step 2: Rot.** Ein Lauf, zwei Auszüge: erst Testnamen und Summenzeile, nach `--- Meldungen` die Zeilen der Abweichung (im Pipe kürzt pytest die Kurzzusammenfassung, deshalb über die Datei):

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41RAnlageSammelrechnung tests/test_paket4_1.py::TestP41RAnlageRandfaelle -q -p no:cacheprovider > /tmp/p41-r2-rot.txt 2>&1; grep -E '^(FAILED|ERROR)|passed|failed' /tmp/p41-r2-rot.txt | sed 's/ - .*//'; echo '--- Meldungen'; grep -E '^E +\{' /tmp/p41-r2-rot.txt
```

Erwartet vor `--- Meldungen` genau diese acht Zeilen und die Summenzeile `8 failed, 5 passed in …s`:

```text
FAILED tests/test_paket4_1.py::TestP41RAnlageSammelrechnung::test_anlage_summiert_zum_positionsnetto[preis_1_005_zweimal]
FAILED tests/test_paket4_1.py::TestP41RAnlageSammelrechnung::test_anlage_summiert_zum_positionsnetto[preis_0_3333_zweimal]
FAILED tests/test_paket4_1.py::TestP41RAnlageSammelrechnung::test_anlage_summiert_zum_positionsnetto[rabatt_33_33_zweimal]
FAILED tests/test_paket4_1.py::TestP41RAnlageSammelrechnung::test_anlage_summiert_zum_positionsnetto[preis_1_005_dreimal]
FAILED tests/test_paket4_1.py::TestP41RAnlageSammelrechnung::test_anlage_summiert_zum_positionsnetto[zwanzig_sorten_0_3333]
FAILED tests/test_paket4_1.py::TestP41RAnlageSammelrechnung::test_anlage_summiert_zum_positionsnetto[bruchmenge_centpreis]
FAILED tests/test_paket4_1.py::TestP41RAnlageRandfaelle::test_pdf_anlage_summiert_zum_netto
FAILED tests/test_paket4_1.py::TestP41RAnlageRandfaelle::test_rechnungsrabatt_bleibt_ausserhalb_der_anlage
```

Nach `--- Meldungen` genau diese neun Zeilen (`<heute>` = Datum des Laufs in der Lieferscheinnummer, `JJJJMMTT`; nach `E` fünf Leerzeichen). Die Zeilen 5 und 6 gehören beide zu `[zwanzig_sorten_0_3333]` und können die Plätze tauschen — pytest listet abweichende Schlüssel eines Dicts in Mengenreihenfolge, die von Lauf zu Lauf wechselt:

```text
E     {'LS-<heute>-0002': Decimal('1.01')} != {'LS-<heute>-0002': Decimal('1.00')}
E     {'LS-<heute>-0001': Decimal('0.33')} != {'LS-<heute>-0001': Decimal('0.34')}
E     {'LS-<heute>-0002': Decimal('0.67')} != {'LS-<heute>-0002': Decimal('0.66')}
E     {'LS-<heute>-0003': Decimal('1.01')} != {'LS-<heute>-0003': Decimal('1.00')}
E     {'LS-<heute>-0001': Decimal('6.67')} != {'LS-<heute>-0001': Decimal('6.70')}
E     {'LS-<heute>-0002': Decimal('6.67')} != {'LS-<heute>-0002': Decimal('6.70')}
E     {'LS-<heute>-0001': Decimal('0.31')} != {'LS-<heute>-0001': Decimal('0.32')}
E     {'LS-<heute>-0002': Decimal('1.01')} != {'LS-<heute>-0002': Decimal('1.00')}
E     {'LS-<heute>-0002': Decimal('1.01')} != {'LS-<heute>-0002': Decimal('1.00')}
```

Zuordnung in der Reihenfolge der `FAILED`-Zeilen: 1 `[preis_1_005_zweimal]`, 2 `[preis_0_3333_zweimal]`, 3 `[rabatt_33_33_zweimal]`, 4 `[preis_1_005_dreimal]`, 5–6 `[zwanzig_sorten_0_3333]` (beide Lieferscheine 6,67 statt 6,70), 7 `[bruchmenge_centpreis]`, 8 `test_pdf_anlage_summiert_zum_netto`, 9 `test_rechnungsrabatt_bleibt_ausserhalb_der_anlage` (im Rabatttest ist die Zeile davor — 1,95/0,06 — grün). Alle acht scheitern in der Zeile `assert anlage == …`.

Grün bleiben die Wächter `…[mengen_3_und_1_zu_0_3333]`, `…[centpreise]`, `test_position_ohne_lieferschein_nicht_in_der_anlage`, `test_rechnung_aus_bestellung_unveraendert`, `test_stornorechnung_ohne_anlage`.

- [ ] **Step 3: Implementierung.**

`backend/app/services/invoice_service.py` — in `netto_je_lieferschein`: diesen Block (Docstring bis `return`, Anker genau einmal)

```python
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

ersetzen durch

```python
    """Abgerechneter Nettobetrag je Lieferschein dieser Rechnung.

    Für die Anlage "Enthaltene Lieferscheine" im Rechnungs-PDF und für
    GET /invoices/{id}/delivery-notes. Gerechnet wird aus den Positionen
    DIESER Rechnung, nicht aus der Bestellung: Clearing-Pfand steht auf
    Bestellung und Lieferschein, aber nicht auf der Rechnung — die Anlage
    muss zur Rechnung passen. Bewusst nicht über ist_clearing_pfand: Das PDF
    entsteht bei jedem Abruf neu, ein später geändertes Kundenfeld
    änderte sonst die Anlage einer versendeten Rechnung (GoBD).

    - Sammelrechnung: Jede Position verteilt ihren Zeilenbetrag (line_total,
      so im PDF gedruckt) exakt auf ihre Lieferscheine, im Verhältnis der
      Mengen aus invoice_line_sources.
    - Rechnung aus Bestellung (S6 hängt genau einen Lieferschein an, ohne
      invoice_line_sources): die Positionen, deren order_item_id zur
      Bestellung des Lieferscheins gehört.
    Auf Cent gerundet wird erst der Betrag je Lieferschein, mit
    auf_cent_verteilen über alle Lieferscheine der Rechnung (Paket 4.1, R):
    Die Anlage summiert sich exakt zu den Positionen, aus denen sie stammt;
    jeder Lieferschein liegt weniger als 1 Cent neben seinem Anteil. Bis
    Paket 4.1 rundete jeder Lieferschein Menge × Preis für sich — war das
    kein ganzer Centbetrag (Preise mit 3–4 Nachkommastellen,
    Positionsrabatt, Bruchmengen auch bei Centpreisen), lag die Anlage um
    Cent neben dem Rechnungsnetto. Sind alle Anteile ganze Cent, ändert
    sich nichts.
    Der Rabatt auf die ganze Rechnung (Kopfrabatt, im PDF z. B.
    "Jahresbonus und Verpackungspauschale") bleibt wie bisher außen vor:
    Die Anlage summiert sich zur Zwischensumme vor diesem Rabatt. Von Hand
    ergänzte Positionen (ohne Lieferschein) stehen nicht darin.
    """
    anteile = {n.id: Fraction(0) for n in lieferscheine}
    rang = {n.id: (n.delivery_note_number or "", str(n.id)) for n in lieferscheine}
    je_position: dict = {}
    for line_id, note_id, nummer, menge, zeilenbetrag in db.execute(
        select(InvoiceLineSource.invoice_line_id, InvoiceLineSource.delivery_note_id,
               DeliveryNote.delivery_note_number, InvoiceLineSource.quantity, InvoiceLine.line_total)
        .join(InvoiceLine, InvoiceLineSource.invoice_line_id == InvoiceLine.id)
        .join(DeliveryNote, InvoiceLineSource.delivery_note_id == DeliveryNote.id)
        .where(InvoiceLine.invoice_id == invoice.id)
    ).all():
        je_position.setdefault(line_id, (zeilenbetrag, []))[1].append((note_id, menge))
        # Auch Lieferscheine, die nicht (mehr) an der Rechnung hängen, bekommen
        # ihren Anteil — sonst rutschte er auf die anderen.
        rang.setdefault(note_id, (nummer or "", str(note_id)))
    for zeilenbetrag, quellen in je_position.values():
        gesamtmenge = sum((Fraction(menge) for _, menge in quellen), Fraction(0))
        for note_id, menge in quellen:
            # Anteil nach Menge; ohne Menge (nur in Altdaten denkbar) zu gleichen Teilen
            gewicht = Fraction(menge) / gesamtmenge if gesamtmenge else Fraction(1, len(quellen))
            anteile[note_id] = anteile.get(note_id, Fraction(0)) + Fraction(zeilenbetrag or 0) * gewicht
    mit_quelle = {note_id for _, quellen in je_position.values() for note_id, _ in quellen}
    for note in lieferscheine:
        if note.id in mit_quelle or note.order is None:
            continue
        bestellzeilen = {l.id for l in note.order.lines}
        anteile[note.id] = sum(
            (Fraction(l.line_total or 0) for l in invoice.lines if l.order_item_id in bestellzeilen),
            Fraction(0),
        )
    betraege = auf_cent_verteilen(anteile, rang)
    return {n.id: betraege[n.id] for n in lieferscheine}
```

`backend/app/services/invoice_service.py` — Importzeilen aus R.1 (`ROUND_HALF_UP` wird in dieser Datei nicht mehr gebraucht; kein anderes Modul importiert es von hier — geprüft): diesen Block

```python
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
```

ersetzen durch

```python
from decimal import Decimal
from fractions import Fraction
```

Prüfen:

```bash
F=backend/app/services/invoice_service.py
grep -c 'ROUND_HALF_UP' $F
grep -c 'auf_cent_verteilen(' $F
grep -c 'InvoiceLineSource.quantity, InvoiceLine.line_total)' $F
```

Erwartet: `0`, `2` (Definition und Aufruf), `1`.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → keine `FAILED`-Zeile, Summenzeile `13 passed in …s`, nach `--- Meldungen` keine Zeile.
- [ ] **Step 5: Bestand rund um die Anlage.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_sammelrechnung.py tests/test_paket4.py tests/test_storno.py -q -p no:cacheprovider 2>&1 | tail -1
```

Erwartet: `229 passed` (vor R.2 ebenso `229 passed`; darin `TestP4BSammelpositionMenge` mit 25,00 + 25,00 bzw. 30,00 + 30,00).
- [ ] **Statisch:** `/opt/homebrew/bin/ruff check --select F821,F823 backend/app/services/invoice_service.py backend/tests/test_paket4_1.py` → keine Ausgabe, Exit 0. `/opt/homebrew/bin/ruff check --select F401 backend/app/services/invoice_service.py | grep -c F401` → `6` (Altbestand, auf `1e2238b` ebenfalls `6`; `ROUND_HALF_UP` ist nicht darunter).
- [ ] **Vollauf (Prozedur V):** `14 failed, N passed, 2 skipped, 1 error` mit N = `<N-vor-R>` + 18 (im Gesamtplan `2048`); Abgleich leer.
- [ ] **Commit:**

```bash
git add backend/app/services/invoice_service.py backend/tests/test_paket4_1.py
git commit -m "fix(rechnung): Anlage „Enthaltene Lieferscheine“ summiert sich exakt zum Netto der Positionen (P41-R.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3 (R.3): Abschluss R — Prüfungen und Meldung (ohne Commit)

- [ ] Alle R-Klassen:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41RCentVerteilung tests/test_paket4_1.py::TestP41RAnlageSammelrechnung tests/test_paket4_1.py::TestP41RAnlageRandfaelle -q -p no:cacheprovider 2>&1 | tail -1
```

  Erwartet: `18 passed`.
- [ ] `git diff --stat <Basis-R>..HEAD` → genau `backend/app/services/invoice_service.py` und `backend/tests/test_paket4_1.py`; `git log --oneline <Basis-R>..HEAD` → zwei Commits mit `(P41-R.1)` und `(P41-R.2)`. Kein Frontend, `tsc`/Build entfallen (nichts im Frontend geändert).
- [ ] Meldung (Zwischenstand, **nicht anhalten**, weiter mit Task 4): `<Basis-R>`, N vor/nach, Rot/Grün je Task, Ausgaben der `grep`-Prüfungen, ruff, eigene Patch-Korrekturen (Stoppregel 5).

---

## Abschnitt D — Berliner Datum in Belegnummern — Tasks 4–7 (D.1–D.4); Fortsetzung Tasks 13–14 (D.5, D.6)

> **Rahmen:** Hinweis für Worker, Global Constraints, Stoppregeln 1–5 und Prozedur V stehen im Kopf, ergänzt um die D-Stoppregeln unten. **D ist geteilt:** D.1–D.4 (Backend) sind Tasks 4–7; D.5 (Oberfläche) und D.6 (Abschluss D) folgen als Tasks 13–14 nach Abschnitt V (Backend vor Frontend, siehe „Reihenfolge“). D.6 ist eine Abschlussmeldung und kein Halt. Abnahme D und Offene Punkte D stehen am Ende des Plans (Manager-Arbeit). Der Worker verbindet sich nie mit dem Produktionsserver.

**Ziel:** Jede Belegnummer mit Datum oder Jahr trägt den Berliner Kalendertag. Bisher galt der UTC-Tag des Containers. Betroffen sind Lieferschein (LS), Packliste (PL), Auftragsbestätigung (AB), Bestellung (BE: anlegen, Abo-Lauf, Shopify), Einkaufsbestellung (EK) und Inventur (INV). Das Datum neben der Nummer folgt mit: Das gedruckte „Datum:“ auf AB, LS und PL und „Erstellt am“ in der Bestellansicht zeigen denselben Berliner Tag (D.1, D.5). Die Inventur schlägt als Stichtag den Berliner Tag vor (D.5). RE-Jahr und Rechnungsdatum sind seit P4-B.2 richtig; Wächter-Tests halten sie am Jahreswechsel fest. Bestehende Nummern bleiben unverändert. In minga ist keine betroffen (gemessen, siehe Befund).

**Herkunft:** Spec `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, Eintrag „Paket 4 live“, Offen (niedrig): „LS-Nummer mit UTC-Datum um Mitternacht“.

**Architektur:** Keine Schemaänderung, keine Migration (`tenancy._auto_migrate` unberührt), keine neue Route. Es gibt eine Quelle für den Tag: `app.services.order_status_service.heute_berlin()` (seit Paket 2). Es entsteht keine neue Kopie und kein neues Modul. Das gedruckte Bestelldatum rechnet `PDFService._build_document` aus dem UTC-Zeitstempel in Europe/Berlin um (D.1). Im Frontend nutzen zwei Seiten die vorhandenen reinen Funktionen `datumKurz` und `heuteBerlin` aus `frontend/src/services/belegstatus.ts` (D.5); es entsteht keine neue Funktion.

### Befund (am Code auf `1e2238b`, Produktion am 10.10.2026 nur lesend)

**Zeitfenster.** Der Container läuft in UTC. Gemessen 10.10.2026 06:54 UTC im laufenden App-Container: `TZ` nicht gesetzt, `time.tzname = ('UTC', 'UTC')`. `date.today()` liefert dort den UTC-Tag. Zwischen 00:00 und 01:59 Berliner Sommerzeit bzw. 00:00 und 00:59 Winterzeit ist das noch der Vortag. Am Jahreswechsel liegt das Fenster am **01.01. 00:00–00:59 Berliner Zeit (= 31.12. 23:00–23:59 UTC)**. Zum Auftrag: 31.12. 23:30 Berlin = 22:30 UTC ist derselbe Tag. Dieser Zeitpunkt bleibt als Wächter drin; der kritische Fall ist 01.01. 00:30 Berlin. Automatische Läufe liegen nicht im Fenster (APScheduler mit `timezone="Europe/Berlin"`: Abo-Lauf 05:00, Monatsvorschläge 06:30; Celery Beat in `celery_app.py` ebenfalls mit `timezone="Europe/Berlin"`, Abo-Lauf 05:00). Betroffen sind also nur Handgriffe zwischen 0 und 2 Uhr: Ausliefern, Packliste/„Neuer LS“, AB, Bestellung anlegen, „Heute verarbeiten“, Inventur anlegen.

**Datum neben der Nummer.** `PDFService._build_document` wird von `generate_confirmation_pdf`, `generate_delivery_note_pdf` und `generate_packing_list_pdf` aufgerufen und druckt `["Datum:", order.order_date.strftime("%d.%m.%Y")]`. `Order.order_date` hat den Standard `datetime.now(timezone.utc)` und wird naiv in UTC gespeichert. Auf `1e2238b` tragen Nummer und „Datum:“ im Fenster beide den UTC-Vortag, sie passen also zueinander. Ändert D nur die Nummer, widersprechen sie sich auf dem Kundenbeleg. Gemessen im Review auf dem vorigen Planstand D (`/tmp/p41-kopie-dprf2`, byte-gleich mit `/tmp/p41-kopie-d`), Uhr `_P41D_HALB_EINS`, zusätzlich `app.models.order.datetime` festgesetzt wie im Container: API `BE-20261010-0001` mit `order_date` `2026-10-09T22:30:00`; pdftotext des LS-PDF `Lieferschein Nr. LS-20261010-0001` / `Bestellung: BE-20261010-0001` / `Datum: 09.10.2026` / `Lieferdatum: 10.10.2026`, AB-PDF ebenso `AB-20261010-0001 … Datum: 09.10.2026`. Nachgemessen in dieser Revision (Prüfstand, Gegenprobe PDF). Dieselbe Lücke hat die Oberfläche: `Sales.tsx` zeigt „Erstellt am“ mit `new Date(selectedOrder.bestell_datum).toLocaleDateString('de-DE')` und liest den naiven UTC-Zeitstempel als Ortszeit (09.10.). Andere Datumsfelder auf AB/LS/PL gibt es nicht („Lieferdatum“ ist `requested_delivery_date`, ein Tag; MHD nur bei Chargen). Gespeicherte PDFs gibt es für AB/LS/PL nicht, jeder Abruf erzeugt sie neu. Deshalb D.1 (PDF) und D.5 (Oberfläche).

**Inventur in der Oberfläche.** `frontend/src/pages/Inventur.tsx` setzt `useState(new Date().toISOString().split('T')[0])`, also den UTC-Tag im Browser, und schickt immer `inventurApi.create({ typ, count_date: stichtag })`. Der Server-Zweig `count_date or heute` greift im einzigen UI-Weg nie. Am 01.01. zwischen 00:00 und 00:59 Berliner Zeit entstünde nach D.3 allein `INV-2027-0001` mit Stichtag 31.12.2026; auf `1e2238b` sind es `INV-2026-…` und 31.12., also wenigstens stimmig. Deshalb D.5 (Vorgabe `heuteBerlin()`).

**Alle Nummernerzeuger und das Datum daneben (grep über `backend/app`: Präfixe, `strftime('%Y%m%d')`, `.year`, `*_number`-Zuweisungen, Konstruktoren von `OrderConfirmation`, `DeliveryNote`, `PackingList`, `PurchaseOrder`, `InventoryCount` und `Order(order_number=…)`; `order_date` in `backend/app` und `frontend/src`):**

| Nummer | Erzeuger | Datumsquelle auf `1e2238b` | Wege | in D |
|---|---|---|---|---|
| LS-JJJJMMTT-NNNN, PL-… | `lieferschein_service.lieferschein_anlegen` → `naechste_belegnummer(…, today)` | `date.today()` (UTC) | Ausliefern über `order_status_service.setze_status` → `lieferschein_beim_ausliefern` (Status-Knopf, Tagesplan „Ausgeliefert“, `bulk-status`, Quittieren); „Neuer LS“/Packliste `POST /sales/orders/{id}/delivery-notes` | **D.1** |
| AB-JJJJMMTT-NNNN | `documents.create_confirmation` → `naechste_belegnummer` | `date.today()` | `POST /sales/orders/{id}/confirmations` | **D.1** |
| BE-JJJJMMTT-NNNN | `sales._generate_order_number` | `date.today()` | `POST /sales/orders`; Abo-Lauf `subscription_tasks._create_order_from_subscription` („Heute verarbeiten“, Scheduler) | **D.2** |
| BE-… (Shopify) | `shopify_service._next_order_number` | `date.today()` | Shopify-Import (`integrations.py`); in minga keine Shopify-Tabelle | **D.2** |
| BE-… (Import) | `imports._generate_historic_order_number(order_date)` | Bestelldatum aus der Datei | Altdaten-Import | nein, ohne Uhrzeitbezug |
| RE-JJJJ-NNNNN (auch Stornorechnung, Leergut-, Sammel-, Monatsbeleg) | `invoice_service.festschreiben` → `_naechste_rechnungsnummer(invoice.invoice_date.year)` | `invoice.invoice_date = _heute_berlin()` (Berlin, seit P4-B.2) | `/finalize`, `/send` (Entwurf), `cancel_invoice` (Stornorechnung über `festschreiben`, R1.1) | **D.4** Wächter, kein Code |
| EK-JJJJ-NNNN | `procurement_service._next_po_number` | `datetime.now(timezone.utc).year` | `POST /procurement/purchase-orders`; minga: 0 EK | **D.3** |
| INV-JJJJ-NNNN (+ Stichtag) | `inventory_service.create_inventory_count` | `date.today().year`, `count_date or date.today()` | `POST /inventory/counts`; minga: 0 Inventuren | **D.3** |
| Stichtag-Vorgabe der Inventur | `Inventur.tsx` (`useState`) | UTC-Tag im Browser, immer als `count_date` geschickt | Dialog „Neue Inventur“ | **D.5** |
| „Datum:“ auf AB, LS, PL | `pdf_service.PDFService._build_document` | `order.order_date` (naiv UTC), nicht umgerechnet | alle AB-/LS-/PL-PDFs, auch Nachdruck | **D.1** |
| „Erstellt am“ in der Bestellansicht | `Sales.tsx` | `new Date(bestell_datum)` (naiv UTC als Ortszeit) | Detaildialog einer Bestellung | **D.5** |
| Mahnung | — | keine Nummer (`reminder_level` an der Rechnung) | | nein |
| Leergut | Leergutbelege sind Rechnungen (`beleg_art`); `LeergutBewegung` hat keine Nummer | wie RE | | über D.4 |
| MONAT-JJJJ-MM | `monatsrechnung_service` | Schlüssel, keine Belegnummer; Lauf mit `heute_berlin` | | nein |
| KD-NNNNN | `customer_service`, `shopify_service._next_customer_number` | ohne Datum | | nein |
| MIX-JJJJMMTT-N, BATCH-JJJJMMTT | `seed_mix` (Aussaattag des Aufrufers), `inventory.py` Ernte-Schnellbuchung (`date.today()`) | Chargen, keine Belege | | nein → Offene Punkte |

**Vorhandene Helfer für „heute in Berlin“:** sieben gleichlautende Funktionen. `order_status_service.heute_berlin` ist öffentlich und wird schon von `documents.py`, `belegstatus.py`, `subscription_tasks.py` und `models/order.py` genutzt. Dazu kommen `invoice_service._heute_berlin` (RE), `sepa_service.heute_berlin`, `monatsrechnung_service.heute_berlin`, `leergut_service.heute_berlin`, `imports._today_berlin` und `models/customer._heute_berlin`. In `app/core` gibt es keinen Helfer. Im Frontend gibt es `datumKurz` (Tag wie geschrieben, naiver Zeitstempel als UTC, Anzeige in Berlin) und `heuteBerlin` in `services/belegstatus.ts`; `tests/unit/belegstatus.check.ts` prüft beide schon über Mitternacht (`datumKurz('2026-10-31T23:30:00')` → `01.11.2026`, `heuteBerlin(new Date('2026-10-08T22:30:00Z'))` → `2026-10-09`).

**Gegenprüfung Vollständigkeit (Review 10.10.):** RE läuft nur über `festschreiben` (`invoices.py` und Stornorechnung). SEPA nutzt schon `heute_berlin`. Kein Code liest das Datum aus einer Belegnummer zurück. Die Frontend-Ablage (`belegpfad.belegmonat`) rechnet schon in Berlin.

**Nachgemessen in Produktion (minga, nur `SELECT`/`pragma`, `mode=ro`, Skript R-D1 unten, 10.10.2026 06:54 UTC):**

| Tabelle | Zeilen | mit `<P>-JJJJMMTT` | angelegt 0–2 Uhr Berlin | Nummerndatum ≠ Berliner Anlagetag | davon = UTC-Tag |
|---|---|---|---|---|---|
| `orders` (BE) | 598 | 598 | 0 | 572 | **0** |
| `order_confirmations` (AB) | 6 | 6 | 0 | 0 | **0** |
| `delivery_notes` (LS) | 11 | 11 | 0 | 0 | **0** |
| `packing_lists` (PL) | 11 | 11 | 0 | 0 | **0** |

Weitere Werte: LS mit `actual_delivery_date`: 1, Nummerndatum = Liefertag. `purchase_orders` 0, `inventory_counts` 0, RE-2026: 10. Die 572 BE-Abweichungen tragen kein UTC-Datum. Vermutlich kommen sie aus dem Altdaten-Import (Nummer = Bestelldatum); nicht nachgemessen, siehe Offene Punkte. **Ergebnis: Keine bestehende Nummer trägt den UTC-Vortag. Es gibt nichts zu korrigieren und kein Runbook.**

**Reproduziert (Kopie `1e2238b`, Prozess-Zeitzone `TZ=Etc/GMT+12`, also ein Prozessdatum vor dem Berliner Tag wie UTC um 00:30):** Bestellung mit Liefertag heute angelegt, bestätigt, ausgeliefert. Ergebnis: `BE-20261009-0001`, `LS-20261009-0001`, Liefertag `2026-10-10`. Auf dem Endstand von D mit derselben Uhr: `BE-20261010-0001`, `LS-20261010-0001`, `2026-10-10`.

### Entscheidungen mit Begründung (Manager)

- **D-E1 — Eine Quelle: `order_status_service.heute_berlin`.** Sie ist öffentlich, liegt schon an den Belegwegen (`documents.py` importiert sie, das Ausliefern setzt mit ihr `actual_delivery_date`), und ihre Zeitquelle ist in Bestandstests festsetzbar. Keine dritte Kopie und kein neues `app/core`-Modul. Ein Umzug würde die Bestandstests brechen, die `order_status_service.datetime` festsetzen (`TestNacharbeitPacktagBerlin`, `test_liefertag_ist_der_berliner_kalendertag` in `test_gernot_261008_paket2.py`). `invoice_service._heute_berlin` bleibt für RE. Es ist schon richtig, Tests setzen es fest, und ein Import aus `order_status_service` wäre ein Zyklus (`order_status_service` importiert `invoice_service`). Das Zusammenlegen der sieben Kopien gehört in die Offenen Punkte.
- **D-E2 — Späte Importe, wo der Modulkopf einen Zyklus riskiert.** `lieferschein_service` muss spät importieren, denn `order_status_service` importiert `lieferschein_service` am Modulkopf; ein Kopfimport scheitert mit `ImportError`. `shopify_service` importiert durchgehend in Funktionen. `procurement_service` und `inventory_service` importieren spät, weil `app/services/__init__.py` `inventory_service` beim Paketimport lädt; ein Kopfimport zöge `invoice_service`, `leergut_service` usw. in diesen Moment. Vorbild ist `models/order.py::Order.resolve_packing_date`. `sales.py` und `documents.py` importieren am Kopf (bestehender Importblock aus `order_status_service`).
- **D-E3 — Nummerndatum = Anlagetag in Berlin, nicht der Liefertag.** Ein nachgetragener Liefertag (Tagesplan eines vergangenen Tages) bleibt in `actual_delivery_date`. Die Nummer zählt im Kreis des Anlagetags weiter, wie AB, PL und BE. So nummeriert kein Beleg rückwirkend in einem alten Tageskreis. `TestP4BLieferscheinBeimAusliefern::test_nachgetragener_liefertag` bleibt unverändert grün (gemessen).
- **D-E4 — Code statt Container-Zeitzone (kein `TZ` im Dockerfile).**
  1. *Tests:* Die Regel ist nur im Code mit eingefrorener Uhr prüfbar. Der Entwicklungs-Mac läuft in Europe/Berlin; eine Container-Einstellung wäre in pytest unsichtbar, Rot/Grün nicht messbar und eine Regression unbemerkt.
  2. *Laufzeitumgebungen:* Es gibt zwei Dockerfiles (Wurzel und `backend/`), `docker-compose.yml` und `docker-compose.prod.yml` mit Celery-Worker und -Beat, dazu lokale Entwicklung und Testläufe. Jede bräuchte `TZ`; fehlt es an einer Stelle, kommt der Fehler still zurück.
  3. *Reichweite:* `TZ` ändert die Bedeutung aller übrigen rund 60 `date.today()`-Aufrufe auf einen Schlag, ungetestet (Prognose, Berichte, Überfälligkeit, MHD, Mahnlauf).
  4. *Bestand:* Seit Paket 2 gilt „Berliner Tag im Code“ (sieben Stellen), und D folgt dieser Regel.

  `TZ` als zusätzliche Absicherung bleibt eine eigene Manager-Entscheidung (Offene Punkte) und ist für D nicht nötig.
- **D-E5 — Kollisionsfestigkeit P4-Fix.4 bleibt unverändert.** Die Savepoint-Wiederholung in `lieferschein_anlegen` und die Signatur `naechste_belegnummer(db, model, number_col, prefix, today)` bleiben; `TestP4Fix4Lieferscheinnummer` ersetzt die Funktion mit genau dieser Signatur. Nach D.1 grün (gemessen, siehe D.1 Step 5). AB, BE, EK und INV bekommen keine neue Wiederholung (nicht Teil von D).
- **D-E6 — Bestehende Nummern bleiben (GoBD).** Keine Migration, kein Korrekturskript. In minga ist keine Nummer betroffen (Befund).
- **D-E7 — RE ohne Codeänderung, aber mit Wächter.** D.4 hält RE-Jahr, Rechnungsdatum und Stornorechnung am Jahreswechsel fest. Gegenprobe gemessen: Mit `return date.today()` in `invoice_service._heute_berlin` werden 3 der 4 D.4-Tests rot (`RE-2026-00001 != RE-2027-00001`, `RE-2026-00002 != RE-2027-00001`, Neujahrslieferung). Der Silvester-Wächter bleibt grün, wie gewollt.
- **D-E8 — Testuhr wie im Bestand.** Der Helfer `_p41d_uhr` simuliert den Container. `date.today()` liefert in den nummerngebenden Modulen den UTC-Tag. `datetime.now(tz)` liefert in `order_status_service`, `invoice_service`, `procurement_service` und `models.order` (Standard von `Order.order_date`, seit der Review-Revision) den eingefrorenen Zeitpunkt. Das ist das Muster von `TestNacharbeitPacktagBerlin` (`BerlinerUhr`/`ServerDatum`) und `TestAbnahmeSepaBerlin`. Deshalb ist Rot auf dem Berliner Mac messbar. Der Helfer setzt mit `raising=False`, denn `documents.py` verliert in D.1 den Import `date` und `procurement_service.py` in D.3 `datetime`/`timezone`.
- **D-E9 — Bewusst nicht in D** (kein Nummernbezug und kein Datum neben einer Nummer, Liste in den Offenen Punkten): Entwurfsdatum einer Rechnung (`create_invoice`: `date.today()`, beim Festschreiben ersetzt, Zahlungsziel als Differenz bleibt), Vorgabedatum der Sammelrechnung, Shopify-Liefertag (+3 Tage), Vorgabe in `_create_order_from_subscription` (Aufrufer übergeben immer den Berliner Tag), Überfälligkeits- und Mahnläufe, Berichte, in `pdf_service` „Erstellt am“ (Mahnung) und `days_overdue`. Im Frontend die UTC-Vorgaben ohne Nummernbezug: Liefertag in `CreateOrderModal.tsx`, `heuteIso` in `Abonnements.tsx`, Kennzahl „heute“ in `Sales.tsx`, Anzeige `po.order_date` in `Purchasing.tsx` (EK trägt nur das Jahr) und weitere (Offene Punkte 1).
- **D-E10 — Das gedruckte und angezeigte Bestelldatum folgt der Nummer (Review-Befund, Abhilfe A).** Ohne D.1-PDF stünde nach D genau im Fenster 0–2 Uhr `LS-20261010-0001` neben `Datum: 09.10.2026` auf dem Kundenbeleg. Vorher waren beide falsch, aber stimmig. Eine Einschränkung der Nachricht an Gernot (Abhilfe B) ließe einen neuen Widerspruch auf Kundenbelegen stehen; das ist schlechter als der Ausgangsstand. Umsetzung: `_build_document` liest `order.order_date` als UTC (naiv → `replace(tzinfo=utc)`, mit Zone unverändert, z. B. die Vorschau in `document_template_service`) und formatiert in Europe/Berlin. Die Spalte und ihre Speicherung bleiben (keine Migration, D-E6). Im Frontend `datumKurz(selectedOrder.bestell_datum)`. Nachdruck alter Belege: Das „Datum:“ ändert sich nur bei Bestellungen, deren `order_date` in UTC 22:00–23:59 (Sommer) bzw. 23:00–23:59 (Winter) liegt, und dann vom UTC-Vortag auf den Berliner Tag. Der Altdaten-Import setzt `order_date` auf 00:00 (`imports.py`: `datetime.combine(bestelldatum, datetime.min.time())`), das bleibt derselbe Tag. Für minga hergeleitet 0 (R-D1: 0 Bestellungen mit Anlage 0–2 Uhr Berlin); gemessen wird es vor dem Deploy mit R-D1 Zeile „order_date im Fenster“ (Gate).
- **D-E11 — Inventur-Stichtag im Browser = Berliner Tag (Review-Hinweis).** Die Oberfläche schickt `count_date` immer mit, also wäre D.3s Stichtag-Zweig dort wirkungslos und die INV-Nummer (Berliner Jahr) stünde am 01.01. 00:00–00:59 neben dem Stichtag 31.12. D.5 setzt die Vorgabe auf `heuteBerlin()`. Wählt jemand bewusst einen anderen Stichtag (etwa am 02.01. rückwirkend den 31.12.), gilt D-E3: Die Nummer trägt das Jahr des Anlagetags. Das ist gewollt und bleibt.

### Rollen und Rechte

Unverändert. Keine neue Route, kein neues Feld, keine Rechteprüfung berührt; dieselben Endpunkte mit denselben Rollen. Die beiden Frontend-Stellen (D.5) ändern nur einen angezeigten Wert und einen Vorgabewert auf Seiten, die dieselben Rollen wie bisher sehen.

### Überschneidungen mit V, Z, R (Nachbar-Kopien `/tmp/p41-kopie-vrev`, `-zrev`, `-zfix2`, `-rrev`, Stand 10.10.2026 10:20, `diff -rq` gegen `1e2238b`)

| Datei | D ändert | Andere Abschnitte | Urteil |
|---|---|---|---|
| `backend/app/api/v1/sales.py` | Importblock aus `order_status_service`; `_generate_order_number` | V: `_create_audit_log` und Aufrufer (`user_name`) | getrennte Stellen |
| `backend/app/services/invoice_service.py` | — | R: Importe, neu `auf_cent_verteilen`, Rumpf `netto_je_lieferschein` | D ändert die Datei nicht; D.4 testet nur `festschreiben`/`cancel_invoice` |
| `backend/app/services/pdf_service.py` | `_build_document`, Meta-Block | R liest nur `generate_invoice_pdf` (Lieferscheinanlage), ändert die Datei nicht | getrennte Methode |
| `backend/app/api/v1/documents.py`, `services/lieferschein_service.py`, `shopify_service.py`, `procurement_service.py`, `inventory_service.py` | ja | in keiner Nachbar-Kopie geändert | — |
| Frontend | `pages/Sales.tsx`, `pages/Inventur.tsx` (je ein Import und eine Zeile) | V: `OrderDocumentsModal.tsx`, neu `OrderVerlauf.tsx`, `bestellverlauf.ts`, `bestellverlaufApi.ts`, `tests/unit/bestellverlauf.check.ts`. Z: `Invoices.tsx`, `Tabs.tsx`, `rechnungssuche.ts`, `tests/unit/rechnungsreiter.check.ts` (Z nennt `Sales.tsx` nur in seinen Offenen Punkten) | keine gemeinsame Datei; `belegstatus.ts` ändert niemand |
| `backend/tests/test_paket4_1.py` | Block D (Klassen `TestP41D…`, Helfer `_p41d_…`, Konstanten `_P41D_…`) | V/Z/R eigene Präfixe | Ans Dateiende anhängen. Den Kopf legt der erste Abschnitt an. |

Hat ein anderer Abschnitt den Importblock `from app.services.order_status_service import (…)` in `sales.py` vor D geändert, ist das Stoppregel 1 nur dann, wenn `heute_berlin` dort schon anders gebunden ist. Sonst `heute_berlin` in denselben Block aufnehmen, mit `grep -c "heute_berlin" backend/app/api/v1/sales.py` → `2` belegen und in der Meldung vermerken (Stoppregel 5).

### Prüfstand (gemessen 10.10.2026; Repo und Produktion unverändert)

- **Plantext-Nachspiel nach der Review-Revision:** `/tmp/p41-kopie-drev` = frisches `git archive 1e2238b`, `frontend/node_modules` als Symlink, aus **diesem** Text mechanisch aufgebaut (`/tmp/p41-drev-tools/replay.py`, Treiber `lauf.sh`, Protokoll `lauf1.log`: Kopf, Testblöcke, Node-Prüfung, alle 16 Ersetzungen in Dokumentreihenfolge; jeder Anker kam zum Zeitpunkt seines Steps genau einmal vor). Alle Prüfbefehle der Steps wörtlich ausgeführt:
  - Vorbereitung: alle Zählwerte wie angegeben. Prozedur V Basis `14 failed, 2030 passed, 2 skipped, 1 error`, Abgleich leer.
  - D.1: Rot wörtlich wie in Step 3 (`5 failed, 1 passed`) → Grün `6 passed`; Zählungen `0`/`0`/`0`/`3`/`0`/`1`; `TestP4Fix4…` + `TestP4B…` `13 passed`; PDF-Bestandsdateien `107 passed`; ruff Exit 0; Prozedur V `2036`, Abgleich leer.
  - D.2: Rot wörtlich (`4 failed, 1 passed`) → `5 passed`; `0`/`2`/`0`; ruff Exit 0; Prozedur V `2041`, Abgleich leer.
  - D.3: Rot wörtlich (`2 failed, 1 passed`) → `3 passed`; `0`, `9:from datetime import date`, `0`, `1`; inventur/procurement/shopify `34 passed`; ruff Exit 0; Prozedur V `2044`, Abgleich leer.
  - D.4: `4 passed`; alle D-Klassen `18 passed`; Paket-3-Abnahme über Klassen-IDs `5 passed`; Prozedur V `2048`, Abgleich leer.
  - D.5: Node-Prüfung neu `p41d-berlin.check: 7 Fälle ok` (auch mit `TZ=UTC` und `TZ=Pacific/Kiritimati`); Rot `0`/`0`/`1`/`1` → `1`/`1`/`0`/`0`; `tsc exit 0`; Build `✓ built in 6.39s`; `belegstatus.check: 29 Fälle ok`. `npx --no-install tsx tests/unit/p41d-berlin.check.ts` gibt dieselbe Ausgabe.
  - D.6: ruff F821/F823 über die sieben Python-Dateien Exit 0. F401/F811/F841 über dieselben Dateien: 13 Befunde auf `1e2238b` und auf dem Endstand, keine neuen. `diff -rq` gegen `1e2238b`: unter `backend/app` genau die sieben Dateien, unter `frontend/src` genau `Sales.tsx` und `Inventur.tsx`, neu `frontend/tests/unit/p41d-berlin.check.ts`.
- **Gegenproben auf dem Endstand:**
  - PDF (Review-Befund): `pdf_service.py` auf `1e2238b` zurückgesetzt, Rest D (`/tmp/p41-kopie-drev-pdf`): `1 failed, 5 passed`, `['09.10.2026', '12.10.2026'] != ['10.10.2026', '12.10.2026']`. Das ist der Zustand, den der Review auf dem vorigen Planstand mit pdftotext gemessen hat (`/tmp/p41-kopie-dprf2`: `LS-20261010-0001` / `Datum: 09.10.2026`). Mit D.1 vollständig, Uhr 00:30, Liefertag 10.10., pdftotext: AB, LS und PL je `Nr. …-20261010-0001`, `Bestellung: BE-20261010-0001`, `Datum: 10.10.2026`, `Lieferdatum: 10.10.2026`.
  - RE (Mutation `_heute_berlin` → `date.today()`, `/tmp/p41-kopie-drev-re`): `3 failed, 1 passed` (`RE-2026-00001`/`RE-2026-00002` statt `RE-2027-00001`). Basis + nur Testdatei (`/tmp/p41-kopie-drev-nurtest`): D.4 `1 failed, 3 passed` (`BE-20261231-0001`).
  - Uhr-Probe ohne Monkeypatch, `TZ=Etc/GMT+12` (Prozess 09.10., Berlin 10.10.): Basis `BE/AB/LS/PL-20261009-0001`, Endstand `…-20261010-0001`, Liefertag jeweils `2026-10-10`.
- **Branch-Simulation** (`/tmp/p41-kopie-drev-git3`, `/tmp/p41-drev-tools/gitsim.sh`): Basis-Commit, ein Z-Commit auf `Invoices.tsx`, D.1–D.5 mit den `git add`/`git commit`-Zeilen dieses Plans, danach ein V-Commit auf `OrderDocumentsModal.tsx`. Der V-Commit danach enthält nur `OrderDocumentsModal.tsx`, es blieb also kein D-Rest liegen; `git status --short` am Ende leer. D.6 Step 1 listet genau die fünf D-Commits mit den Dateien aus „File Structure (D)“. Der A-D1-Befehl zeigt nur `(P41-D.5)` mit `Inventur.tsx`, `Sales.tsx`, `p41d-berlin.check.ts`. Der frühere Befehl `git diff 1e2238b --stat -- frontend/` zeigt dagegen auch `Invoices.tsx` und `OrderDocumentsModal.tsx` (Review-Hinweis bestätigt).
- **Vorstand (vor der Review-Revision, weiter gültig für D.2–D.4):** `/tmp/p41-kopie-d`, `-d2`, `-d3`, Review-Nachspiel `/tmp/p41-kopie-dprf` (Rot/Grün D.2–D.4 und Uhr-Probe identisch).
- **Nicht gemessen:** R-D1-Zeile „order_date im Fenster“ in Produktion (Lesezugriff in dieser Revision nicht freigegeben; Skript auf leerem lokalem Schema lauffähig geprüft) → Gate vor dem Deploy. Oberfläche im Browser, echte Commits im Worktree, Produktion nach dem Deploy → Abnahme.

### File Structure (D)

| Datei | Task | Verantwortung |
|---|---|---|
| `backend/app/services/lieferschein_service.py` | D.1 | `lieferschein_anlegen`: LS/PL-Nummer mit `heute_berlin()` (später Import); Docstring `naechste_belegnummer` |
| `backend/app/api/v1/documents.py` | D.1 | `create_confirmation`: AB-Nummer mit `heute_berlin()`; Import `date` entfällt |
| `backend/app/services/pdf_service.py` | D.1 | `PDFService._build_document`: „Datum:“ = Berliner Tag von `order.order_date` |
| `backend/app/api/v1/sales.py` | D.2 | `_generate_order_number` mit `heute_berlin()`; Import im bestehenden Block |
| `backend/app/services/shopify_service.py` | D.2 | `_next_order_number` mit `heute_berlin()` |
| `backend/app/services/procurement_service.py` | D.3 | `_next_po_number`: Jahr aus `heute_berlin()`; Import `datetime, timezone` entfällt |
| `backend/app/services/inventory_service.py` | D.3 | `create_inventory_count`: Nummernjahr und Stichtag aus `heute_berlin()` |
| `backend/tests/test_paket4_1.py` | D.1–D.4 | Block D: 4 Klassen, 18 Tests; Kopf nur, wenn die Datei fehlt |
| `frontend/src/pages/Sales.tsx` | D.5 | „Erstellt am“ mit `datumKurz(selectedOrder.bestell_datum)` |
| `frontend/src/pages/Inventur.tsx` | D.5 | Stichtag-Vorgabe `heuteBerlin()` |
| `frontend/tests/unit/p41d-berlin.check.ts` | D.5 | Node-Prüfung: `datumKurz`/`heuteBerlin` zu den Zeitpunkten der Backend-Tests (neu) |

### D-Stoppregeln (zusätzlich zu Stoppregel 1–5 des Gesamtplans)

- **D-S1:** `order_status_service.heute_berlin` fehlt, ist umbenannt oder liest die Zeit nicht mehr über `datetime.now(ZoneInfo("Europe/Berlin"))`: Stoppregel 1.
- **D-S2:** `naechste_belegnummer` hat eine andere Signatur als `(db, model, number_col, prefix, today)`, oder die Savepoint-Schleife in `lieferschein_anlegen` fehlt: Stoppregel 1 (P4-Fix.4 bleibt unangetastet).
- **D-S3:** Ein Bestandstest wird in D rot (Prozedur V zeigt einen neuen Namen): Stoppregel 3. D passt **keinen** Bestandstest an.
- **D-S4:** `datumKurz` oder `heuteBerlin` fehlt in `frontend/src/services/belegstatus.ts` oder ist dort nicht mehr exportiert: Stoppregel 1. D schreibt keine eigene Datumsfunktion im Frontend.

### Vorbereitung D

Im Kopf erledigt („Vorbereitung (vor Task 1)“: „Ausgangsstand D“ auf der Basis, Baseline). Seitdem hat nur R Dateien geändert (`invoice_service.py`, Testdatei); die D-Anker prüft jeder Step selbst. Prozedur V: Befehl aus dem Kopf. N zur Orientierung im Gesamtplan (vor D steht R mit +18; maßgeblich sind die Namen):

| nach | vor D (= nach Task 2) | D.1 (Task 4) | D.2 (Task 5) | D.3 (Task 6) | D.4 (Task 7) |
|---|---|---|---|---|---|
| N | 2048 | 2054 (+6) | 2059 (+5) | 2062 (+3) | 2066 (+4) |

Einzeln auf `1e2238b` gemessen: 2030 → 2036 → 2041 → 2044 → 2048. D.5 (Task 13) ändert nur das Frontend und hat keinen Vollauf.

---

### Task 4 (D.1): Lieferschein, Packliste und Auftragsbestätigung nach dem Berliner Tag (Nummer und gedrucktes Datum)

**Files:**
- Modify: `backend/app/services/lieferschein_service.py` (`naechste_belegnummer`: Docstring; `lieferschein_anlegen`: Nummerndatum)
- Modify: `backend/app/api/v1/documents.py` (Importzeile `from datetime import …`; `create_confirmation`)
- Modify: `backend/app/services/pdf_service.py` (`PDFService._build_document`: Meta-Block, Zeile „Datum:“)
- Create or Modify: `backend/tests/test_paket4_1.py` (Kopf nur, wenn die Datei fehlt; Block D.1 anhängen)

**Interfaces:**
- Produces: `lieferschein_anlegen` nummeriert LS und PL mit `heute_berlin()`, auf allen Wegen: Ausliefern über `setze_status`, „Neuer LS“, Packliste im Tagesplan. `create_confirmation` nummeriert AB mit `heute_berlin()`. `naechste_belegnummer` ist unverändert, inklusive Signatur. `_build_document` druckt als „Datum:“ den Berliner Tag von `order.order_date` (naiv = UTC; mit Zone wird nur umgerechnet); Signatur unverändert, gilt für AB, LS und PL samt Vorschau.
- Produces (Tests, genutzt von D.2–D.4): `_p41d_uhr(monkeypatch, utc_iso)`, `_p41d_kunde(client, name=…)`, `_p41d_bestellung(client, kunde, liefertag_iso)` (bestätigt), `_p41d_ausliefern(client, bestellung)`, `_p41d_lieferscheine(client, bestellung)` → `[(LS-Nummer, PL-Nummer, actual_delivery_date)]`, `_p41d_pdf_daten(client, url)` → alle `TT.MM.JJJJ` im PDF-Text in Druckreihenfolge, Konstanten `_P41D_HALB_EINS`, `_P41D_HALB_ZWOELF`, `_P41D_HALB_DREI`, `_P41D_DATE_MODULE`, `_P41D_DATETIME_MODULE` (enthält `app.models.order`, damit `Order.order_date` die Testuhr bekommt).
- Consumes: `app.services.order_status_service.heute_berlin`; `tests.test_documents_preise._pdf_text` (Bestand, ReportLab-Streams entpacken).

- [ ] **Step 1: Testdatei-Kopf, nur wenn `backend/tests/test_paket4_1.py` fehlt** (`test -f backend/tests/test_paket4_1.py && echo vorhanden`). Ist sie vorhanden, entfällt dieser Step; das ist kein Stopp. Sonst die Datei mit genau diesem Inhalt anlegen:

```python
"""Paket 4.1 — Restpunkte aus der Paket-4-Abnahme (10.10.2026).

Gemeinsame Testdatei aller Abschnitte. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP41V…/_p41v_, TestP41Z…/_p41z_, TestP41R…/_p41r_,
TestP41D…/_p41d_): ein gleichnamiger Helfer würde still ersetzt. Jeder
Abschnitt bringt seine Importe selbst mit. Keine autouse-Fixture.
"""
```

- [ ] **Step 2: Block ans Dateiende von `backend/tests/test_paket4_1.py` anhängen:**

```python


# ============================================================
# Abschnitt D — Berliner Datum in Belegnummern (Paket 4.1)
# ============================================================
import importlib as _p41d_importlib
from datetime import date as _p41d_date, datetime as _p41d_datetime, timezone as _p41d_timezone

#: Module, deren date.today() eine Nummer oder ihr Datum bestimmte — dort
#: liefert die Testuhr den UTC-Tag wie der Container (python:3.11-slim ohne TZ).
_P41D_DATE_MODULE = (
    "app.services.lieferschein_service", "app.api.v1.documents", "app.api.v1.sales",
    "app.services.shopify_service", "app.services.inventory_service",
    "app.services.invoice_service", "app.tasks.subscription_tasks",
)
#: Module, deren datetime.now(...) einen Berliner Tag, eine Nummer oder das
#: gedruckte Bestelldatum liefert (models.order: Standard von Order.order_date).
_P41D_DATETIME_MODULE = (
    "app.services.order_status_service", "app.services.invoice_service",
    "app.services.procurement_service", "app.models.order",
)


def _p41d_uhr(monkeypatch, utc):
    """Server wie in Produktion (Prozess-Zeitzone UTC) zum Zeitpunkt `utc`:
    date.today() ist der UTC-Tag, datetime.now(tz) der Zeitpunkt in tz,
    datetime.now() naive UTC. Muster: TestNacharbeitPacktagBerlin
    (test_gernot_261008_paket2.py), TestAbnahmeSepaBerlin (paket3).
    raising=False: ein Modul, das `date` oder `datetime` nach Abschnitt D
    nicht mehr importiert (documents.py, procurement_service.py), bekommt
    den Namen nur für die Dauer des Tests."""
    zeitpunkt = _p41d_datetime.fromisoformat(utc)

    class _P41DUhr(_p41d_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return zeitpunkt.astimezone(_p41d_timezone.utc).replace(tzinfo=None)
            return zeitpunkt.astimezone(tz)

    class _P41DServertag(_p41d_date):
        @classmethod
        def today(cls):
            return zeitpunkt.astimezone(_p41d_timezone.utc).date()

    for name in _P41D_DATETIME_MODULE:
        monkeypatch.setattr(_p41d_importlib.import_module(name), "datetime", _P41DUhr, raising=False)
    for name in _P41D_DATE_MODULE:
        monkeypatch.setattr(_p41d_importlib.import_module(name), "date", _P41DServertag, raising=False)


#: 00:30 in München am 10.10.2026 (Sommerzeit, UTC+2) — UTC noch 09.10.
_P41D_HALB_EINS = "2026-10-09T22:30:00+00:00"
#: 23:30 in München am 09.10.2026 — derselbe Tag in UTC und Berlin.
_P41D_HALB_ZWOELF = "2026-10-09T21:30:00+00:00"
#: 02:30 in München am 10.10.2026 — UTC ist auch schon der 10.10.
_P41D_HALB_DREI = "2026-10-10T00:30:00+00:00"


def _p41d_kunde(client, name="Dorint Hotels Betriebs GmbH"):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p41d_bestellung(client, kunde, liefertag):
    """Bestätigte Bestellung mit einer Freitextposition (10 × 2,50 € zu 7 %)."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"], "requested_delivery_date": liefertag,
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _p41d_ausliefern(client, bestellung):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/status", json={"status": "GELIEFERT"})
    assert r.status_code == 200, r.text
    return r.json()


def _p41d_lieferscheine(client, bestellung):
    r = client.get(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return [(ls["delivery_note_number"], ls["packing_list"]["packing_list_number"],
             ls["actual_delivery_date"]) for ls in r.json()]


def _p41d_pdf_daten(client, url):
    """Alle Daten TT.MM.JJJJ im Text eines Beleg-PDFs, in Druckreihenfolge."""
    import re
    from tests.test_documents_preise import _pdf_text
    r = client.get(url)
    assert r.status_code == 200, r.text
    return re.findall(r"\d\d\.\d\d\.\d{4}", _pdf_text(r.content).decode("latin-1", errors="ignore"))


class TestP41DLieferscheinnummerBerlin:
    """Lieferschein, Packliste und Auftragsbestätigung heißen nach dem
    Berliner Anlagetag. Der Container läuft in UTC: zwischen 0 und 2 Uhr
    (Sommerzeit; Winterzeit 0–1 Uhr) hieß der automatische Lieferschein nach
    dem Vortag, während actual_delivery_date schon den Berliner Tag trug."""

    def test_ausliefern_um_halb_eins(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        geliefert = _p41d_ausliefern(client, bestellung)

        assert geliefert["actual_delivery_date"] == "2026-10-10"
        assert _p41d_lieferscheine(client, bestellung) == [
            ("LS-20261010-0001", "PL-20261010-0001", "2026-10-10")]

    def test_neuer_lieferschein_um_halb_eins(self, client, monkeypatch):
        """„Neuer LS“ im Belegdialog und „Packliste“ im Tagesplan."""
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})

        assert r.status_code == 201, r.text
        assert (r.json()["delivery_note_number"], r.json()["packing_list"]["packing_list_number"]) == (
            "LS-20261010-0001", "PL-20261010-0001")

    def test_auftragsbestaetigung_um_halb_eins(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-12")

        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirmations", json={})

        assert r.status_code == 201, r.text
        assert r.json()["confirmation_number"] == "AB-20261010-0001"

    def test_belegdatum_im_pdf_um_halb_eins(self, client, monkeypatch):
        """AB, Lieferschein und Packliste drucken „Datum:“ (Bestelldatum,
        Order.order_date, naiv in UTC gespeichert) und „Lieferdatum:“. Um 00:30
        stand sonst neben AB-/LS-/PL-20261010-… der 09.10.2026."""
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-12")
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirmations", json={})
        assert r.status_code == 201, r.text
        ab = r.json()
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text
        ls = r.json()

        daten = [_p41d_pdf_daten(client, url) for url in (
            f"/api/v1/sales/confirmations/{ab['id']}/pdf",
            f"/api/v1/sales/delivery-notes/{ls['id']}/pdf",
            f"/api/v1/sales/delivery-notes/{ls['id']}/packing-list/pdf")]

        assert daten == [["10.10.2026", "12.10.2026"]] * 3

    def test_neuer_tag_beginnt_um_mitternacht_in_berlin(self, client, monkeypatch):
        """23:30 und 00:30 Berliner Zeit: zwei Tage, zwei Nummernkreise."""
        kunde = _p41d_kunde(client)
        _p41d_uhr(monkeypatch, _P41D_HALB_ZWOELF)
        abend = _p41d_bestellung(client, kunde, "2026-10-09")
        _p41d_ausliefern(client, abend)
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        nacht = _p41d_bestellung(client, kunde, "2026-10-10")
        _p41d_ausliefern(client, nacht)

        assert [_p41d_lieferscheine(client, b)[0][0] for b in (abend, nacht)] == [
            "LS-20261009-0001", "LS-20261010-0001"]

    def test_nach_zwei_uhr_wie_bisher(self, client, monkeypatch):
        """Wächter: ab 2 Uhr sind UTC- und Berliner Tag gleich."""
        _p41d_uhr(monkeypatch, _P41D_HALB_DREI)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        _p41d_ausliefern(client, bestellung)

        assert _p41d_lieferscheine(client, bestellung) == [
            ("LS-20261010-0001", "PL-20261010-0001", "2026-10-10")]
```

- [ ] **Step 3: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin -q -p no:cacheprovider 2>&1 | grep -E "^E     At index|^E   AssertionError: assert '|^FAILED|[0-9]+ (passed|failed)"
```

Erwartet (gemessen):

```
E     At index 0 diff: ('LS-20261009-0001', 'PL-20261009-0001', '2026-10-10') != ('LS-20261010-0001', 'PL-20261010-0001', '2026-10-10')
E     At index 0 diff: 'LS-20261009-0001' != 'LS-20261010-0001'
E   AssertionError: assert 'AB-20261009-0001' == 'AB-20261010-0001'
E     At index 0 diff: ['09.10.2026', '12.10.2026'] != ['10.10.2026', '12.10.2026']
E     At index 1 diff: 'LS-20261009-0002' != 'LS-20261010-0001'
FAILED tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin::test_ausliefern_um_halb_eins
FAILED tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin::test_neuer_lieferschein_um_halb_eins
FAILED tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin::test_auftragsbestaetigung_um_halb_eins
FAILED tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin::test_belegdatum_im_pdf_um_halb_eins
FAILED tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin::test_neuer_tag_beginnt_um_mitternacht_in_berlin
========================= 5 failed, 1 passed in 0.68s ==========================
```

Grün bleibt der Wächter `test_nach_zwei_uhr_wie_bisher`. `test_belegdatum_im_pdf_um_halb_eins` prüft nur das gedruckte Datum: „Datum:“ 09.10. statt 10.10., das „Lieferdatum:“ 12.10. stimmt schon. Die Dauer am Zeilenende ist die des Laufs.

- [ ] **Step 4: Implementierung.**

`backend/app/services/lieferschein_service.py` — in `naechste_belegnummer`, Signatur und Docstring: diesen Block

```python
def naechste_belegnummer(db: Session, model, number_col, prefix: str, today: date) -> str:
    """Generiert {PREFIX}-YYYYMMDD-NNNN sequenziell (AB, LS, PL)."""
```

ersetzen durch

```python
def naechste_belegnummer(db: Session, model, number_col, prefix: str, today: date) -> str:
    """Generiert {PREFIX}-YYYYMMDD-NNNN sequenziell (AB, LS, PL). `today` ist
    der Berliner Kalendertag des Aufrufers (order_status_service.heute_berlin)."""
```

`backend/app/services/lieferschein_service.py` — in `lieferschein_anlegen`, Ende des Docstrings und Nummerndatum (vor `db.flush()`): diesen Block

```python
    Integritätsfehler werden nicht wiederholt. Committet nicht."""
    today = date.today()
```

ersetzen durch

```python
    Integritätsfehler werden nicht wiederholt. Committet nicht."""
    # Nummerndatum = Anlagetag in Europe/Berlin. Der Container läuft in UTC:
    # zwischen 0 und 2 Uhr hieß der Lieferschein sonst nach dem Vortag,
    # während actual_delivery_date schon den Berliner Tag trug (Paket 4.1, D).
    # Später Import: order_status_service importiert dieses Modul.
    from app.services.order_status_service import heute_berlin
    today = heute_berlin()
```

`backend/app/api/v1/documents.py` — Importzeile am Modulkopf: diesen Block

```python
from datetime import date, datetime, timezone
```

ersetzen durch

```python
from datetime import datetime, timezone
```

`backend/app/api/v1/documents.py` — in `create_confirmation`, Nummernvergabe: diesen Block

```python
    today = date.today()
    number = _next_document_number(
        db, OrderConfirmation, OrderConfirmation.confirmation_number, "AB", today
    )
```

ersetzen durch

```python
    # Berliner Kalendertag wie Lieferschein und Packliste (Paket 4.1, D)
    number = _next_document_number(
        db, OrderConfirmation, OrderConfirmation.confirmation_number, "AB", heute_berlin()
    )
```

`backend/app/services/pdf_service.py` — in `PDFService._build_document`, Anfang des Meta-Blocks: diesen Block

```python
        # Meta
        meta_data = [
            ["Bestellung:", order.order_number],
            ["Datum:", (order.order_date.strftime("%d.%m.%Y") if order.order_date else "-")],
```

ersetzen durch

```python
        # Meta. „Datum“ ist das Bestelldatum. Order.order_date ist naiv in UTC
        # gespeichert; gedruckt wird der Berliner Tag wie in Bestell-, AB-, LS-
        # und PL-Nummer. Sonst stünde zwischen 0 und 2 Uhr der Vortag neben der
        # Nummer (Paket 4.1, D).
        from datetime import timezone as _timezone
        from zoneinfo import ZoneInfo as _ZoneInfo
        bestelldatum = "-"
        if order.order_date:
            zeitpunkt = order.order_date
            if zeitpunkt.tzinfo is None:
                zeitpunkt = zeitpunkt.replace(tzinfo=_timezone.utc)
            bestelldatum = zeitpunkt.astimezone(_ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y")
        meta_data = [
            ["Bestellung:", order.order_number],
            ["Datum:", bestelldatum],
```

Prüfen:

```bash
grep -c "date.today()" backend/app/services/lieferschein_service.py backend/app/api/v1/documents.py
grep -cw "date" backend/app/api/v1/documents.py
grep -c "heute_berlin" backend/app/services/lieferschein_service.py
grep -c 'order.order_date.strftime' backend/app/services/pdf_service.py
grep -c '\["Datum:", bestelldatum\],' backend/app/services/pdf_service.py
```

Erwartet: `…/lieferschein_service.py:0`, `…/documents.py:0`, dann `0` (kein `date` mehr in `documents.py`), dann `3` (Docstring, Import, Aufruf), dann `0`, dann `1`.

- [ ] **Step 5: Grün.** Befehl aus Step 3 → `6 passed`. Danach die Wächter für Kollisionsfestigkeit, Ausliefern und die Beleg-PDFs:

```bash
(cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4Fix4Lieferscheinnummer tests/test_paket4.py::TestP4BLieferscheinBeimAusliefern -q -p no:cacheprovider 2>&1 | tail -1)
(cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_documents_preise.py tests/test_gernot_260821.py tests/test_gernot_260824.py tests/test_import_bestellungen_zukunft.py -q -p no:cacheprovider 2>&1 | tail -1)
```

Erwartet: `13 passed`; `107 passed`.

- [ ] **Step 6: Statisch.** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/lieferschein_service.py app/api/v1/documents.py app/services/pdf_service.py` → keine Ausgabe, Exit 0.
- [ ] **Step 7: Vollauf (Prozedur V):** N = vorher + 6 (im Gesamtplan `2054`; D allein auf `1e2238b` `2036`). Abgleich leer.
- [ ] **Step 8: Commit:**

```bash
git add backend/app/services/lieferschein_service.py backend/app/api/v1/documents.py backend/app/services/pdf_service.py backend/tests/test_paket4_1.py
git commit -m "fix(belege): Lieferschein, Packliste und AB nach dem Berliner Tag nummeriert und datiert (P41-D.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

**Review Focus D.1:** Der späte Import in `lieferschein_anlegen` steht vor der Savepoint-Schleife, nicht darin. `naechste_belegnummer` bekommt `today` weiter vom Aufrufer. Das Nummerndatum ist der Anlagetag, nicht `actual_delivery_date` (D-E3). In `_build_document` ändert sich nur der Wert der Zeile „Datum:“; „Lieferdatum:“ (`requested_delivery_date`, ein Tag) bleibt, ebenso Reihenfolge und Layout der Meta-Tabelle. Ein `order_date` mit Zone (Vorschau aus `document_template_service`) wird nur umgerechnet.

---

### Task 5 (D.2): Bestellnummer nach dem Berliner Tag — Bestellung, Abo-Lauf, Shopify

**Files:**
- Modify: `backend/app/api/v1/sales.py` (Importblock aus `order_status_service`; `_generate_order_number`)
- Modify: `backend/app/services/shopify_service.py` (`_next_order_number`)
- Modify: `backend/tests/test_paket4_1.py` (Block D.2 anhängen)

**Interfaces:**
- Produces: `_generate_order_number(db)` → `BE-<Berliner Tag>-NNNN`; gilt auch für `subscription_tasks._create_order_from_subscription`, das diese Funktion importiert. `shopify_service._next_order_number(db)` ebenso. Signaturen unverändert.
- Produces (Tests): `_p41d_einheit()`, `_p41d_bestellnummern()` → sortierte `[(order_number, requested_delivery_date_iso)]`.
- Consumes: `heute_berlin`; Helfer und Konstanten aus D.1.

- [ ] **Step 1: Block ans Dateiende von `backend/tests/test_paket4_1.py` anhängen:**

```python


def _p41d_einheit():
    from app.models.unit import UnitCategory, UnitOfMeasure
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        einheit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if einheit is None:
            einheit = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
            db.add(einheit)
            db.commit()
        return str(einheit.id)


def _p41d_bestellnummern():
    from app.models.order import Order
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        return sorted((o.order_number, o.requested_delivery_date.isoformat()) for o in db.query(Order))


class TestP41DBestellnummerBerlin:
    """BE-Nummern (Bestellung, Abo-Lauf, Shopify-Import) nach dem Berliner Tag."""

    def test_bestellung_um_halb_eins(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)

        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        assert bestellung["order_number"] == "BE-20261010-0001"

    def test_neuer_tag_beginnt_um_mitternacht_in_berlin(self, client, monkeypatch):
        kunde = _p41d_kunde(client)
        _p41d_uhr(monkeypatch, _P41D_HALB_ZWOELF)
        _p41d_bestellung(client, kunde, "2026-10-12")
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        _p41d_bestellung(client, kunde, "2026-10-12")

        assert [nummer for nummer, _ in _p41d_bestellnummern()] == ["BE-20261009-0001", "BE-20261010-0001"]

    def test_abo_lauf_um_halb_eins(self, client, monkeypatch):
        """„Heute verarbeiten“ um 00:30: Liefertag und Nummer tragen denselben Tag."""
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)
        kunde = _p41d_kunde(client, "LfA Förderbank Bayern")
        r = client.post("/api/v1/products", json={
            "name": "Erbse", "sku": "P41D-ABO", "base_price": "3.50",
            "category": "MICROGREEN", "base_unit_id": _p41d_einheit()})
        assert r.status_code in (200, 201), r.text
        r = client.post("/api/v1/sales/subscriptions", json={
            "kunde_id": kunde["id"], "product_id": r.json()["id"], "menge": 2, "einheit": "STUECK",
            "intervall": "TAEGLICH", "liefertage": [], "gueltig_von": "2026-10-10"})
        assert r.status_code == 201, r.text

        r = client.post("/api/v1/sales/subscriptions/process-today")

        assert r.status_code == 200, r.text
        assert r.json()["details"]["erstellt"] == 1
        assert _p41d_bestellnummern() == [("BE-20261010-0001", "2026-10-10")]

    def test_shopify_nummer_um_halb_eins(self, client, monkeypatch):
        from app.services.shopify_service import _next_order_number
        from tests.conftest import TestingSessionLocal
        _p41d_uhr(monkeypatch, _P41D_HALB_EINS)

        with TestingSessionLocal() as db:
            assert _next_order_number(db) == "BE-20261010-0001"

    def test_nach_zwei_uhr_wie_bisher(self, client, monkeypatch):
        """Wächter."""
        _p41d_uhr(monkeypatch, _P41D_HALB_DREI)

        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2026-10-10")

        assert bestellung["order_number"] == "BE-20261010-0001"
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41DBestellnummerBerlin -q -p no:cacheprovider 2>&1 | grep -E "^E     At index|^E   AssertionError: assert '|^FAILED|[0-9]+ (passed|failed)"
```

Erwartet (gemessen):

```
E   AssertionError: assert 'BE-20261009-0001' == 'BE-20261010-0001'
E     At index 1 diff: 'BE-20261009-0002' != 'BE-20261010-0001'
E     At index 0 diff: ('BE-20261009-0001', '2026-10-10') != ('BE-20261010-0001', '2026-10-10')
E   AssertionError: assert 'BE-20261009-0001' == 'BE-20261010-0001'
FAILED tests/test_paket4_1.py::TestP41DBestellnummerBerlin::test_bestellung_um_halb_eins
FAILED tests/test_paket4_1.py::TestP41DBestellnummerBerlin::test_neuer_tag_beginnt_um_mitternacht_in_berlin
FAILED tests/test_paket4_1.py::TestP41DBestellnummerBerlin::test_abo_lauf_um_halb_eins
FAILED tests/test_paket4_1.py::TestP41DBestellnummerBerlin::test_shopify_nummer_um_halb_eins
========================= 4 failed, 1 passed in 0.28s ==========================
```

Grün bleibt der Wächter `test_nach_zwei_uhr_wie_bisher`. `test_abo_lauf_um_halb_eins` zeigt den Befund: Liefertag 10.10., Nummer 09.10.

- [ ] **Step 3: Implementierung.**

`backend/app/api/v1/sales.py` — Importblock am Modulkopf (Import aus `order_status_service`): diesen Block

```python
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, bestaetigen, bezeichnung, pruefe_uebergang,
    setze_status, setze_status_im_tagesplan,
)
```

ersetzen durch

```python
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, bestaetigen, bezeichnung, heute_berlin,
    pruefe_uebergang, setze_status, setze_status_im_tagesplan,
)
```

`backend/app/api/v1/sales.py` — in `_generate_order_number`, Docstring und Nummerndatum: diesen Block

```python
    """Generiert sequenzielle Bestellnummer im Format BE-YYYYMMDD-NNNN.

    Uses SELECT ... FOR UPDATE to prevent duplicate numbers under
    concurrent access.
    """
    today = date.today()
```

ersetzen durch

```python
    """Generiert sequenzielle Bestellnummer im Format BE-YYYYMMDD-NNNN.

    YYYYMMDD ist der Berliner Kalendertag, nicht der UTC-Tag des Containers
    (Paket 4.1, D) — auch für den Abo-Lauf, der diese Funktion nutzt.

    Uses SELECT ... FOR UPDATE to prevent duplicate numbers under
    concurrent access.
    """
    today = heute_berlin()
```

`backend/app/services/shopify_service.py` — in `_next_order_number`, Präfix: diesen Block

```python
    from app.models.order import Order
    prefix = f"BE-{date.today().strftime('%Y%m%d')}"
```

ersetzen durch

```python
    from app.models.order import Order
    from app.services.order_status_service import heute_berlin
    # Berliner Kalendertag wie sales._generate_order_number (Paket 4.1, D)
    prefix = f"BE-{heute_berlin().strftime('%Y%m%d')}"
```

Prüfen:

```bash
grep -c "today = date.today()" backend/app/api/v1/sales.py
grep -c "heute_berlin" backend/app/api/v1/sales.py
grep -c "date.today().strftime" backend/app/services/shopify_service.py
```

Erwartet: `0`, `2` (Import, Aufruf), `0`.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `5 passed`.
- [ ] **Step 5: Statisch.** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/sales.py app/services/shopify_service.py` → keine Ausgabe, Exit 0.
- [ ] **Step 6: Vollauf (Prozedur V):** N = vorher + 5 (im Gesamtplan `2059`; D allein `2041`). Abgleich leer.
- [ ] **Step 7: Commit:**

```bash
git add backend/app/api/v1/sales.py backend/app/services/shopify_service.py backend/tests/test_paket4_1.py
git commit -m "fix(bestellung): Bestellnummer nach dem Berliner Tag, auch im Abo-Lauf und beim Shopify-Import (P41-D.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

**Review Focus D.2:** Die Datumsvorgaben in `sales.py` außerhalb der Nummer bleiben unverändert (`_date.today()` bei Sonderpreisen, DATEV-Dateiname). Ebenso der Shopify-Liefertag `date.today() + 3` (D-E9).

---

### Task 6 (D.3): EK- und Inventurnummer mit dem Jahr des Berliner Tags

**Files:**
- Modify: `backend/app/services/procurement_service.py` (Importzeile `from datetime import …`; `ProcurementService._next_po_number`)
- Modify: `backend/app/services/inventory_service.py` (`InventoryService.create_inventory_count`)
- Modify: `backend/tests/test_paket4_1.py` (Block D.3 anhängen)

**Interfaces:**
- Produces: `_next_po_number()` → `EK-<Jahr des Berliner Tags>-NNNN`. `create_inventory_count(...)` → `INV-<Jahr des Berliner Tags>-NNNN`, Stichtag ohne Vorgabe = Berliner Tag. Ein übergebenes `count_date` bleibt unverändert. Signaturen unverändert.
- Produces (Tests): Konstanten `_P41D_NEUJAHR_HALB_EINS`, `_P41D_SILVESTER_HALB_ZWOELF` (genutzt von D.4).
- Consumes: `heute_berlin`; `_p41d_uhr`.

- [ ] **Step 1: Block ans Dateiende von `backend/tests/test_paket4_1.py` anhängen:**

```python


#: 00:30 in München am 01.01.2027 (Winterzeit, UTC+1) — UTC noch 31.12.2026.
_P41D_NEUJAHR_HALB_EINS = "2026-12-31T23:30:00+00:00"
#: 23:30 in München am 31.12.2026 — UTC 22:30, dasselbe Jahr.
_P41D_SILVESTER_HALB_ZWOELF = "2026-12-31T22:30:00+00:00"


class TestP41DJahreswechselEinkaufInventur:
    """EK- und INV-Nummern tragen das Jahr; maßgeblich ist der Berliner Tag."""

    def test_einkaufsnummer_am_neujahrstag(self, client, monkeypatch):
        from app.services.procurement_service import ProcurementService
        from tests.conftest import TestingSessionLocal
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)

        with TestingSessionLocal() as db:
            assert ProcurementService(db)._next_po_number() == "EK-2027-0001"

    def test_inventur_am_neujahrstag(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)

        r = client.post("/api/v1/inventory/counts")

        assert r.status_code == 201, r.text
        assert (r.json()["count_number"], r.json()["count_date"]) == ("INV-2027-0001", "2027-01-01")

    def test_silvester_halb_zwoelf_im_alten_jahr(self, client, monkeypatch):
        """Wächter: 23:30 Berliner Zeit ist in UTC derselbe Tag."""
        from app.services.procurement_service import ProcurementService
        from tests.conftest import TestingSessionLocal
        _p41d_uhr(monkeypatch, _P41D_SILVESTER_HALB_ZWOELF)

        r = client.post("/api/v1/inventory/counts")

        assert r.status_code == 201, r.text
        assert (r.json()["count_number"], r.json()["count_date"]) == ("INV-2026-0001", "2026-12-31")
        with TestingSessionLocal() as db:
            assert ProcurementService(db)._next_po_number() == "EK-2026-0001"
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41DJahreswechselEinkaufInventur -q -p no:cacheprovider 2>&1 | grep -E "^E     At index|^E   AssertionError: assert '|^FAILED|[0-9]+ (passed|failed)"
```

Erwartet (gemessen):

```
E   AssertionError: assert 'EK-2026-0001' == 'EK-2027-0001'
E     At index 0 diff: 'INV-2026-0001' != 'INV-2027-0001'
FAILED tests/test_paket4_1.py::TestP41DJahreswechselEinkaufInventur::test_einkaufsnummer_am_neujahrstag
FAILED tests/test_paket4_1.py::TestP41DJahreswechselEinkaufInventur::test_inventur_am_neujahrstag
========================= 2 failed, 1 passed in 0.12s ==========================
```

Grün bleibt der Wächter `test_silvester_halb_zwoelf_im_alten_jahr`.

- [ ] **Step 3: Implementierung.**

`backend/app/services/procurement_service.py` — in `ProcurementService._next_po_number`, Docstring und Jahr: diesen Block

```python
        """Fortlaufende EK-Nummer im Format EK-{Jahr}-{4-stellig}."""
        year = datetime.now(timezone.utc).year
```

ersetzen durch

```python
        """Fortlaufende EK-Nummer im Format EK-{Jahr}-{4-stellig}. Jahr des
        Berliner Kalendertags, nicht des UTC-Tags (Paket 4.1, D)."""
        from app.services.order_status_service import heute_berlin
        year = heute_berlin().year
```

`backend/app/services/procurement_service.py` — Importzeile am Modulkopf: diesen Block

```python
from datetime import date, datetime, timezone
```

ersetzen durch

```python
from datetime import date
```

`backend/app/services/inventory_service.py` — in `InventoryService.create_inventory_count`, Nummernjahr: diesen Block

```python
        # Inventurnummer generieren
        year = date.today().year
```

ersetzen durch

```python
        # Inventurnummer und Stichtag nach dem Berliner Kalendertag — der
        # Container läuft in UTC (Paket 4.1, D)
        from app.services.order_status_service import heute_berlin
        heute = heute_berlin()
        year = heute.year
```

`backend/app/services/inventory_service.py` — in `InventoryService.create_inventory_count`, Stichtag im `InventoryCount(...)`: diesen Block

```python
            count_date=count_date or date.today(),
```

ersetzen durch

```python
            count_date=count_date or heute,
```

Prüfen:

```bash
grep -c "datetime.now(timezone.utc).year" backend/app/services/procurement_service.py
grep -n "^from datetime import" backend/app/services/procurement_service.py
grep -c "date.today().year" backend/app/services/inventory_service.py
grep -c "count_date=count_date or heute," backend/app/services/inventory_service.py
```

Erwartet: `0`; `9:from datetime import date` (die Zeilennummer dient nur der Anzeige, kein Anker); `0`; `1`.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `3 passed`. Danach die Bestandsdateien dieser Bereiche:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_inventur.py tests/test_procurement.py tests/test_shopify.py -q -p no:cacheprovider 2>&1 | tail -1
```

Erwartet: `34 passed`.

- [ ] **Step 5: Statisch.** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/procurement_service.py app/services/inventory_service.py` → keine Ausgabe, Exit 0.
- [ ] **Step 6: Vollauf (Prozedur V):** N = vorher + 3 (im Gesamtplan `2062`; D allein `2044`). Abgleich leer.
- [ ] **Step 7: Commit:**

```bash
git add backend/app/services/procurement_service.py backend/app/services/inventory_service.py backend/tests/test_paket4_1.py
git commit -m "fix(einkauf): EK- und Inventurnummer mit dem Jahr des Berliner Tags (P41-D.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7 (D.4): Wächter — RE-Jahr und Rechnungsdatum am Jahreswechsel (keine Codeänderung)

**Files:**
- Modify: `backend/tests/test_paket4_1.py` (Block D.4 anhängen)

**Interfaces:**
- Consumes: `invoice_service.festschreiben` (Rechnungsdatum `_heute_berlin()`, Nummernjahr `invoice_date.year`) und `cancel_invoice` (Stornorechnung über `festschreiben`). Außerdem `_p41d_uhr`, `_p41d_kunde`, `_p41d_bestellung`, `_p41d_ausliefern`, `_p41d_lieferscheine` und die Konstanten aus D.1/D.3.
- Produces (Tests): `_p41d_rechnungsentwurf(client, kunde, datum=…, faellig=…)`, `_p41d_festschreiben(client, rechnung)`.

- [ ] **Step 1: Block ans Dateiende von `backend/tests/test_paket4_1.py` anhängen:**

```python


def _p41d_rechnungsentwurf(client, kunde, datum="2026-12-31", faellig="2027-01-14"):
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": datum, "due_date": faellig,
        "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p41d_festschreiben(client, rechnung):
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


class TestP41DRechnungsjahrBerlin:
    """Wächter (seit P4-B.2 richtig, invoice_service._heute_berlin): RE-Jahr
    und Rechnungsdatum nach dem Berliner Tag des Festschreibens."""

    def test_festschreiben_um_halb_eins_am_neujahrstag(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)
        entwurf = _p41d_rechnungsentwurf(client, _p41d_kunde(client))

        rechnung = _p41d_festschreiben(client, entwurf)

        assert (rechnung["invoice_number"], rechnung["invoice_date"], rechnung["due_date"]) == (
            "RE-2027-00001", "2027-01-01", "2027-01-15")

    def test_festschreiben_um_halb_zwoelf_an_silvester(self, client, monkeypatch):
        _p41d_uhr(monkeypatch, _P41D_SILVESTER_HALB_ZWOELF)
        entwurf = _p41d_rechnungsentwurf(client, _p41d_kunde(client))

        rechnung = _p41d_festschreiben(client, entwurf)

        assert (rechnung["invoice_number"], rechnung["invoice_date"]) == ("RE-2026-00001", "2026-12-31")

    def test_storno_nach_mitternacht_im_neuen_jahr(self, client, monkeypatch):
        """Die Stornorechnung bekommt Nummer und Datum des Neujahrstags; das
        Original behält RE-2026-00001 vom 31.12. (GoBD)."""
        _p41d_uhr(monkeypatch, _P41D_SILVESTER_HALB_ZWOELF)
        original = _p41d_festschreiben(client, _p41d_rechnungsentwurf(client, _p41d_kunde(client)))
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)

        r = client.post(f"/api/v1/invoices/{original['id']}/cancel",
                        json={"reason": "Menge falsch", "create_credit_note": True})

        assert r.status_code == 200, r.text
        storno, gutschrift = r.json()["invoice"], r.json()["credit_note"]
        assert (storno["invoice_number"], storno["invoice_date"]) == ("RE-2026-00001", "2026-12-31")
        assert (gutschrift["invoice_number"], gutschrift["invoice_date"]) == ("RE-2027-00001", "2027-01-01")

    def test_neujahrslieferung_von_der_bestellung_bis_zur_rechnung(self, client, monkeypatch):
        """Alle Nummern einer Lieferung um 00:30 am 01.01.2027 tragen den Neujahrstag."""
        _p41d_uhr(monkeypatch, _P41D_NEUJAHR_HALB_EINS)
        bestellung = _p41d_bestellung(client, _p41d_kunde(client), "2027-01-01")
        _p41d_ausliefern(client, bestellung)
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text

        rechnung = _p41d_festschreiben(client, r.json())

        assert bestellung["order_number"] == "BE-20270101-0001"
        assert _p41d_lieferscheine(client, bestellung) == [
            ("LS-20270101-0001", "PL-20270101-0001", "2027-01-01")]
        assert (rechnung["invoice_number"], rechnung["invoice_date"]) == ("RE-2027-00001", "2027-01-01")
```

- [ ] **Step 2: Sofort grün (Wächter; RE ist seit P4-B.2 richtig, LS/BE seit D.1/D.2).**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41DRechnungsjahrBerlin -q -p no:cacheprovider 2>&1 | tail -1
```

Erwartet: `4 passed`. Ein roter Test hier heißt, dass `festschreiben` oder `cancel_invoice` anders aussieht als im Befund (Stoppregel 2). **Nichts an `invoice_service.py` ändern.** Messwerte zur Einordnung (Manager, nicht nachzuspielen): auf `1e2238b` ohne D.1–D.3 `1 failed, 3 passed` (`BE-20261231-0001`); mit `return date.today()` in `_heute_berlin` `3 failed, 1 passed`.

- [ ] **Step 3: Alle D-Tests und Paket-3-Abnahme.**

```bash
(cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41DLieferscheinnummerBerlin tests/test_paket4_1.py::TestP41DBestellnummerBerlin tests/test_paket4_1.py::TestP41DJahreswechselEinkaufInventur tests/test_paket4_1.py::TestP41DRechnungsjahrBerlin -q -p no:cacheprovider 2>&1 | tail -1)
(cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py::TestAbnahmeSepaBerlin tests/test_gernot_261008_paket3.py::TestAbnahmeRechnungsberechtigung -q -p no:cacheprovider 2>&1 | tail -1)
```

Erwartet: `18 passed`; `5 passed` (Klassen-IDs statt `-k`).

- [ ] **Step 4: Vollauf (Prozedur V):** N = vorher + 4 (im Gesamtplan `2066`; D allein `2048`). Abgleich leer. Danach weiter mit Task 8 (V.1); D.5 folgt als Task 13.
- [ ] **Step 5: Commit:**

```bash
git add backend/tests/test_paket4_1.py
git commit -m "test(rechnung): Wächter für RE-Jahr, Rechnungsdatum und Stornorechnung am Jahreswechsel (P41-D.4)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Abschnitt V — Bestellverlauf in der Oberfläche: wann, wer, was, Status, Grund — Tasks 8–12 (V.1–V.5)

> **Rahmen:** Hinweis für Worker, Global Constraints, Stoppregeln 1–5, Baseline und Prozedur V stehen im Kopf. Neue Tests nur in `backend/tests/test_paket4_1.py` (Klassen `TestP41V…`, Helfer `_p41v_…`, Konstanten `_P41V_…`), Einzeltests über Klassen-IDs, **nie `-k`**. V läuft nach R und D.1–D.4 (Tasks 1–7) und vor D.5 und Z. Die Abschlussmeldung in Task 12 (V.5) ist ein Zwischenstand — **nicht anhalten**. Abnahme V und Offene Punkte V stehen am Ende des Plans (Manager-Arbeit); der Worker verbindet sich nie mit dem Produktionsserver.

**Ziel:** Gernot sieht je Bestellung den Verlauf: **wann** (Berliner Zeit), **wer** (Benutzername, Systemeinträge verständlich), **was** (Aktion auf Deutsch, geänderte Werte als Kurztext), **Status alt → neu** (Wörter wie in der übrigen Oberfläche, „Gepackt“ für `IN_PRODUKTION`) und **Grund**. Der Server liefert den Verlauf seit Paket 2 (`GET /api/v1/sales/orders/{order_id}/audit-log`), aber keine Ansicht ruft ihn auf.

### Befund (am Code auf `1e2238b`, gemessen in der Kopie `/tmp/p41-kopie-v`; Produktion am 10.10. im Review lesend gemessen, siehe „Produktion“ unten)

- **Endpunkt:** `sales.get_order_audit_log` liefert `list[OrderAuditLogResponse]` (`schemas/order.py`: `action`, `field_name`, `line_id`, `old_values`, `new_values`, `user_id`, `user_name`, `created_at`, `reason`), **neueste zuerst** (`order_by(OrderAuditLog.created_at.desc())`). `created_at` ist UTC ohne Zone (`datetime.now(timezone.utc)` in eine naive SQLite-Spalte); die API gibt z. B. `"2026-10-10T07:38:24.548412"` zurück (gemessen).
- **Kein Aufrufer in der Oberfläche:** `git grep -c "audit-log" 1e2238b -- frontend/src` → keine Datei. `OrderDetailResponse` (mit `audit_logs`) nutzt keine Route.
- **Rechte heute:** Der Sales-Router hängt an `_deps_auftraege` (`app/main.py`: Admin, Vertrieb, Buchhaltung, Planung, **Halle**; Lesen und Schreiben). Der Endpunkt hat keine eigene Prüfung und kennt den Aufrufer nicht (`user` fehlt in der Signatur). Die Halle liest also jeden Verlauf vollständig.
- **Wer schreibt welche Einträge** (alle `action=`-Stellen in `backend/app`, 11 Werte):

| Aktion | Schreibstelle | Werte (`old_values` / `new_values`) | `user_name` |
|---|---|---|---|
| `CONFIRM` | `order_status_service.bestaetigen` → `setze_status` | `status` | Token-Benutzername |
| `STATUS_CHANGE` | `setze_status` (Standardwert), Statusknöpfe, Tagesplan | `status`, bei `GELIEFERT` zusätzlich `actual_delivery_date` | ja |
| `BULK_STATUS_CHANGE` | `sales.bulk_update_status` | wie oben | ja |
| `LIEFERSCHEIN_QUITTIERT` | `documents` (Quittieren) → `setze_status` | wie oben, Grund „Lieferschein LS-… quittiert“ | ja |
| `LIEFERDATUM_NACHGETRAGEN` | `order_status_service.trage_lieferdatum_nach` | `actual_delivery_date` | ja |
| `IMPORT` | `imports` | neu: `status`, `bestell_nr_extern`, `datei`; Grund „Bestell-Import“ | ja |
| `STEUERSATZ_KORREKTUR` | `services/steuersatz_korrektur.py` | `total_vat`, `total_gross`, `positionen[{position, tax_rate, line_vat, line_gross}]` | **„Datenkorrektur“**, `user_id` leer |
| `UPDATE` | `sales.update_order` → `_create_audit_log` (nur nach der Bestätigung) | geänderte Kopffelder aus `OrderUpdate`, u. a. `notes`, `requested_delivery_date`, `discount_percent`, Adressen als Python-Text eines dict; Grund = `change_reason` | **fehlt** (nur `user_id`) |
| `ADD_LINE` | `sales.add_order_line` → `_create_audit_log` | neu: `position`, `product`, `quantity`, `unit_price`, `discount_percent` | **fehlt** |
| `UPDATE_LINE` | `sales.update_order_line` → `_create_audit_log` | `quantity`, `unit_price`, `tax_rate`, `discount_percent` — **ohne Position und Produkt** | **fehlt** |
| `DELETE_LINE` | `sales.delete_order_line` → `_create_audit_log` | alt: `position`, `product`, `quantity` | **fehlt** |

  Dazu kommen Einträge aus den Korrektur-Runbooks, direkt per SQL geschrieben: `BULK_STATUS_CHANGE` der Korrektur vom 09.10. mit `user_name` **„systemkorrektur“ (klein)**, ebenso die Vorlage R-B3 im Paket-4-Plan (`'BULK_STATUS_CHANGE', …, 'systemkorrektur'`); `RECHNUNG_ZUGEORDNET` mit „Systemkorrektur“ (groß), `old_values` `NULL`, `new_values` `{"invoice": "RE-…"}`. Die Schreibweise der Systemnamen ist also nicht einheitlich — der Vergleich in der Oberfläche muss Groß-/Kleinschreibung ignorieren (E-V4).
- **Produktion** (`minga`, 10.10., im Review lesend gemessen: `mode=ro`, nur `SELECT`, Skripte `/tmp/p41vrev-tools/prod_namen.py`, `prod_rz.py`, `prod_zeit.py`, `prod_grund.py`; Namen nur ausgegeben, wenn sie einem Systemmuster entsprechen, Werte maskiert; in der Revision nicht selbst nachgemessen — der Lesezugriff war für die Planung nicht freigegeben, Abnahme Schritt 1 misst vor dem Deploy erneut):
  - 603 Einträge. Aktionen: `BULK_STATUS_CHANGE` 574, `STATUS_CHANGE` 16, `CONFIRM` 9, `RECHNUNG_ZUGEORDNET` 2, `STEUERSATZ_KORREKTUR` 1, `LIEFERSCHEIN_QUITTIERT` 1 — alle in `AKTION_TEXT`. Noch kein `UPDATE`/`ADD_LINE`/`UPDATE_LINE`/`DELETE_LINE`: V.1 wirkt nur auf künftige Einträge.
  - **Wer:** die 574 `BULK_STATUS_CHANGE` (GELIEFERT → FAKTURIERT, 09.10. 12:38 UTC) tragen „systemkorrektur“ **klein** und eine `user_id` — 95 % des Bestands; ein Vergleich, der Groß-/Kleinschreibung beachtet, zeigte dort „systemkorrektur“ wie eine Person statt „NovaERP (Datenkorrektur)“. Die 2 `RECHNUNG_ZUGEORDNET` tragen „Systemkorrektur“ mit `user_id`. 23 Einträge ohne Namen (`CONFIRM` 9, `STATUS_CHANGE` 14), alle zwischen 07.10. 09:01 und 08.10. 17:18 UTC (vor Paket 2), mit `user_id` → „Benutzer (Name nicht gespeichert)“. `LIEFERSCHEIN_QUITTIERT` (09.10.) trägt einen Personennamen: Tokens liefern `preferred_username`, die Quelle von V.1 funktioniert in Produktion.
  - **Werte:** `RECHNUNG_ZUGEORDNET` alt `NULL`, neu nur `invoice` (Rechnungsnummer). Beide Gründe enthalten eine Rechnungsnummer (`RE-…`), keine Beträge (V-O5).
  - **Zeit:** `created_at` immer `TEXT` der Länge 26 mit Leerzeichen (ORM-Format, UTC) — auch die Runbook-Zeilen; V-O7 trifft heute nicht zu.
- **Lücke „wer“:** `_create_audit_log` setzt `user_name` nicht. In der Kopie gemessen: `UPDATE`, `ADD_LINE`, `UPDATE_LINE`, `DELETE_LINE` haben `user_name = null`, `CONFIRM` hat `"testuser"`. Die Oberfläche könnte für Änderungen an Kopf und Positionen keinen Namen zeigen.
- **Lücke „was“ bei `UPDATE_LINE`:** Welche Position geändert wurde, steht nirgends (`line_id` setzt `_create_audit_log` nicht, die Werte nennen weder Position noch Produkt).
- **Preise und Konditionen in den Werten:** `ADD_LINE`/`UPDATE_LINE` tragen Einzelpreis und Positionsrabatt, `UPDATE` ggf. den Bestellrabatt, `STEUERSATZ_KORREKTUR` Steuer- und Bruttobeträge, Runbook-Einträge Rechnungsbezug (Prod: `invoice` mit der Rechnungsnummer) und künftig beliebige Schlüssel. Was die Halle heute sieht: `GET /orders/{id}` liefert ihr Einzelpreis, Positionsrabatt und Summen; der Dialog „Bestellung bearbeiten“ (`EditOrderModal.tsx`) zeigt und ändert „Preis pro Einheit“ ohne Rollenprüfung; `update_order_line` erlaubt der Halle Preis- und Rabattänderungen (Paket 3, `TestQ4PositionsrabattImAudit`: „erlaubt, offen: Frage 4“). P4-D blendet nur die **Kunden**-Konditionen (`KUNDENANTWORT_KONDITIONEN`), die Sonderpreisliste und die Beträge der Kreditlimit-Meldung aus; Rechnungen sind für die Halle gesperrt (`_deps_geld`). Der Verlauf ist dagegen die **Preisgeschichte** (wer hat wann welchen Preis/Rabatt gesetzt — Q4.8 hat ihn genau dafür eingeführt) und kann Rechnungsangaben aus Runbooks tragen.
- **Statuswörter:** `frontend/src/components/ui/statusLabels.ts` (`ORDER_STATUS_LABELS`, `orderStatusLabel`; `IN_PRODUKTION` = „Gepackt“, gleichlautend mit `order_status_service.STATUS_BEZEICHNUNG`). Die Datei hat nur einen `import type` und lässt sich mit Node direkt laden (gemessen).
- **Wo der Dialog aufgeht:** `OrderDocumentsModal` („Belege zu Bestellung …“) öffnet ein Klick auf jede Bestellkarte (`Orders.tsx`) und „Belege“ auf der Seite Belegstatus (`Belegstatus.tsx`); alle Rollen des Auftragsrouters erreichen ihn, die Halle ohne Rechnungsteil (`darfRechnungen`). `EditOrderModal` öffnet nur „Bearbeiten“ in `Orders.tsx`.
- **Abfrage-Schlüssel:** `invalidateOrderViews` (`services/orderQueries.ts`) lädt nach jedem Statuswechsel, Quittieren und Bearbeiten alles unter `['orders']` neu (TanStack Query, Präfix).

### Entscheidungen mit Begründung (Manager)

- **E-V1 — Ort: Abschnitt „Verlauf“ am Ende des Belege-Dialogs (`OrderDocumentsModal`), als eigene Komponente `OrderVerlauf`.**
  - Begründung: Der Belege-Dialog ist **die** Bestellansicht — er öffnet beim Klick auf jede Bestellkarte und aus dem Belegstatus, für alle Rollen; dort stehen schon AB, Lieferscheine und Rechnungen, der Verlauf ergänzt sie zur Akte der Bestellung. `EditOrderModal` ist ein Formular (Kopfdaten, Positionen, Stornieren) und nur über „Bearbeiten“ erreichbar; ein eigenes „Bestelldetail“ gibt es nicht. Eine Komponente statt Inline-Code hält `OrderDocumentsModal.tsx` bei zwei Zeilen Änderung und erlaubt später denselben Verlauf im Bearbeiten-Dialog (V-O6).
  - Laden beim Öffnen des Dialogs (eine kleine Anfrage). Schlüssel `['orders', orderId, 'verlauf']`: `invalidateOrderViews` lädt ihn nach jedem Statuswechsel, Quittieren und Bearbeiten mit neu — keine Änderung an `orderQueries.ts`.
- **E-V2 — Chronologisch, älteste zuerst; sortiert wird in der Oberfläche.** Der Verlauf liest sich wie eine Akte (Bestätigt → Gepackt → Geliefert). Die API-Reihenfolge (neueste zuerst) bleibt, weil Bestandstests sie voraussetzen (`test_gernot_261008_paket2.py::_audit`: „neuester Eintrag zuerst“). Gleiche Zeitstempel behalten die Reihenfolge des Servers umgekehrt.
- **E-V3 — „Wer“ wird ab jetzt für alle Einträge gespeichert (V.1).** `_create_audit_log` bekommt `user_name` (Token-Benutzername wie in `setze_status`); `UPDATE_LINE` nennt zusätzlich `position` und `product`. **Keine Migration, keine Datenänderung:** Die Spalte `user_name` gibt es; Alteinträge bleiben, wie sie sind (ein Protokoll wird nicht nachträglich umgeschrieben). Die Oberfläche zeigt sie als „Benutzer (Name nicht gespeichert)“.
- **E-V4 — Systemeinträge verständlich:** `user_name` „Systemkorrektur“ und „Datenkorrektur“ **ohne Rücksicht auf Groß-/Kleinschreibung** (Prod: 574 × „systemkorrektur“, 2 × „Systemkorrektur“; Vorlage R-B3 klein) → „NovaERP (Datenkorrektur)“ (unsere Runbooks bzw. die Steuersatz-Korrektur, nicht Gernots Team), auch wenn eine `user_id` gesetzt ist; weder Name noch ID → „System (automatisch)“ (Statuswechsel ohne Login); Importe zeigen den importierenden Benutzer, Aktion „Importiert“, Datei und externe Bestellnummer.
- **E-V5 — Die Halle sieht im Verlauf keine Preise, Rabatte, Steuersätze, Beträge und keine unbekannten Werte (V.2).** Serverseitig: Logins ohne `sieht_konditionen` (`app.core.rollen`, = alle außer der Halle) bekommen je Eintrag nur die Werte einer **Positivliste** `VERLAUF_WERTE_FUER_ALLE` (Status, Liefer-/Packdaten, Kundenbestellnummer, Notizen, Adressen, Position, Produkt, Menge, Import-Datei und -Nummer); alles andere fällt weg, `werte_ausgeblendet: true` sagt der Oberfläche, dass etwas fehlt („Preise und Beträge nur für Verwaltung, Vertrieb, Buchhaltung und Planung“). Aktion, Zeit, Name, Status und Grund bleiben sichtbar.
  - Begründung: Gernots Satz „Rolle Produktion ohne Rechnungen/Konditionen“ (G60) — der Verlauf ist die Preis- und Rabattgeschichte je Kunde und damit Konditionswissen, das die Halle für Packen und Liefern nicht braucht; Runbook-Einträge können Rechnungsangaben tragen (Rechnungen sind für die Halle gesperrt). Eine **Positivliste** statt einer Sperrliste, weil Runbooks ihre Schlüssel frei wählen (Prod heute: `invoice` in `RECHNUNG_ZUGEORDNET`; künftige Korrekturen schreiben, was ihr Anlass braucht): Ein unbekannter Schlüssel ist für die Halle automatisch ausgeblendet.
  - In Kauf genommen: Die Halle sieht den **aktuellen** Preis einer Position weiter in der Bestellung und im Bearbeiten-Dialog (P4-D E-D4, Q4.8 / Frage 4 offen) — der Filter verhindert nur die Geschichte. Ob die Halle Preise und Rabatte überhaupt ändern darf, ist Gernots offene Frage 4 aus Paket 3 (V-O2). Der Grund-Text bleibt sichtbar, auch wenn jemand dort einen Preis oder eine Rechnungsnummer schreibt (V-O5; Prod: beide `RECHNUNG_ZUGEORDNET`-Gründe nennen eine Rechnungsnummer).
  - Mechanik wie P4-D.2 (`model_copy(update=…)`, unter FastAPI 0.109 / Pydantic 2.5.3 dort gemessen). Ein Login mit Halle **und** einer kaufmännischen Rolle sieht alles (`hat_rolle`: mindestens eine). Kein neues Recht, keine Änderung an `main.py` oder `core/rollen.py`.
- **E-V6 — Aufbereitung als reine Funktionen** in `frontend/src/services/bestellverlauf.ts` (Aktion → Text, Werte → Kurztext, Zeit in Berlin, Wer, Status, Sortierung), geprüft per Node-Check `tests/unit/bestellverlauf.check.ts` (45 Fälle) und im Vollauf über `TestP41VVerlaufAnzeige`. Einziger Import sind die Statuswörter (`../components/ui/statusLabels.ts`, Endung `.ts` nötig für Node; `tsconfig.json` erlaubt sie mit `allowImportingTsExtensions`). Die Prüfung liest die fünf Backend-Dateien und verlangt für **jede** dort geschriebene Aktion einen Text — eine neue Aktion ohne Übersetzung macht sie rot. Unbekannte Aktionen (Runbooks) erscheinen als „Sonstige Änderung (`<AKTION>`)“.
  - Werte: Tage `TT.MM.JJJJ`; Menge ohne Nullen („4.000“ → „4“, „2.500“ → „2,5“); Preise mit 2–4 Nachkommastellen und „€“; Rabatt „10 %“; Steuersatz „7 %“/„19 %“; leer → „leer“; Adressen (Python-Text) nur „Lieferadresse geändert“; Rechnungsbezug aus Runbooks (`invoice`) als „Rechnung: RE-…“; Texte auf 60 Zeichen gekürzt. Unveränderte Werte (gleich formatiert) entfallen; „Rabatt: 0 %“ einer neuen Position entfällt; feste Reihenfolge der Felder.
  - Node-Aufruf wie alle Bestandsprüfungen `node tests/unit/<Name>.check.ts` (Node ≥ 23.6; der Vollauf ruft `node`). `npx tsx` ist nicht im Projekt installiert, nur im npx-Cache dieses Macs: `npx --no-install tsx tests/unit/bestellverlauf.check.ts` liefert dieselbe Zeile (gemessen) — als Zusatz, nicht als Pflicht (ohne Netzwerk nicht garantiert).
- **E-V7 — Lade-, Fehler- und Leer-Zustand:** „Verlauf wird geladen…“ (`role="status"`); Fehlertext vom Server (`getErrorMessage`) mit Knopf „Erneut laden“ (`role="alert"`); leer: „Noch keine Einträge. Protokolliert werden Statuswechsel, Importe und Änderungen ab der Bestätigung.“ (Änderungen an Entwürfen schreibt der Server bewusst nicht, `update_order` nur für `status != ENTWURF`.)
- **E-V8 — Bewusst nicht enthalten:** Eintrag „Angelegt“ (das Anlegen schreibt keinen Eintrag; V-O3); Verlauf im Bearbeiten-Dialog (V-O6); Nachtragen fehlender Namen in Alteinträgen (E-V3); Änderung der API-Reihenfolge (E-V2).

### File Structure (V)

| Datei | Task | Verantwortung |
|---|---|---|
| `backend/tests/test_paket4_1.py` | V.1–V.3 | **neu, falls sie fehlt** (Kopf), sonst Blöcke ans Ende — 15 Tests (`TestP41VVerlaufWer` 6, `TestP41VVerlaufRechte` 8, `TestP41VVerlaufAnzeige` 1) |
| `backend/app/api/v1/sales.py` | V.1, V.2 | V.1: `_create_audit_log` (`user_name`), Aufrufe in `update_order`, `add_order_line`, `update_order_line` (+ `position`/`product`), `delete_order_line`; V.2: `VERLAUF_WERTE_FUER_ALLE`, `_verlaufswerte_ohne_konditionen`, `get_order_audit_log` |
| `backend/app/schemas/order.py` | V.2 | `OrderAuditLogResponse.werte_ausgeblendet` |
| `frontend/src/services/bestellverlauf.ts` | V.3 | **neu** — Typen, Texte, reine Funktionen |
| `frontend/tests/unit/bestellverlauf.check.ts` | V.3 | **neu** — Node-Prüfung, 45 Fälle |
| `frontend/src/services/bestellverlaufApi.ts` | V.4 | **neu** — `bestellverlaufApi.liste(orderId)` |
| `frontend/src/components/domain/OrderVerlauf.tsx` | V.4 | **neu** — Abschnitt „Verlauf“ |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | V.4 | Import hinter `InvoiceDetail`, `<OrderVerlauf …/>` am Ende des Dialoginhalts |

**Nicht geändert (geprüft):** `tenancy.py` (keine Migration), `models/order.py`, `app/main.py`, `app/core/rollen.py`, `order_status_service.py`, `imports.py`, `documents.py`, `services/api.ts`, `services/orderQueries.ts`, `components/ui/statusLabels.ts`, `EditOrderModal.tsx`, `Orders.tsx`, `Belegstatus.tsx`, alle Bestandstests.

**Überschneidungen:** Innerhalb von Paket 4.1 ist nur `backend/tests/test_paket4_1.py` sicher gemeinsam (Blöcke werden angehängt; Präfixe disjunkt; dieser Block bindet `uuid`, `date`, `timedelta`, `Decimal`, `pytest`, `get_current_user`, `app`, `TestingSessionLocal` — gleiche Quelle wie in `test_paket4.py`). Gegen `/tmp/p41/D.md`, `R.md`, `Z.md` (Stand beim Schreiben dieses Abschnitts) per `grep` geprüft: **D** ändert in `sales.py` nur den Importblock aus `order_status_service` und `_generate_order_number` — getrennt von den V-Ankern (`_create_audit_log`, die vier Aufrufe mit je eigener `action=`-Zeile, `UPDATE_LINE`-Werte, `get_order_audit_log`); nach D weicht nur der `sales.py`-Hash der Vorbereitung ab (kein Stopp, s. dort). **R** und **Z** berühren von V nur `test_paket4_1.py`. `schemas/order.py` und `OrderDocumentsModal.tsx` ändert kein anderer Abschnitt. Nicht gemessen: Nachspiel aller vier Abschnitte zusammen (Manager beim Zusammenführen).

### Prüfstand (in Kopien, Repo und Produktion unverändert)

- **Erste Fassung:** Kopie `/tmp/p41-kopie-v` (`git archive 1e2238b`, `frontend/node_modules` als Symlink, eigener Git-Verlauf; Hashes von `sales.py`, `schemas/order.py`, `OrderDocumentsModal.tsx` gleich), alle Blöcke mechanisch angewendet (`/tmp/p41v-tools/ersetze.py`), Nachspiel auf `/tmp/p41-kopie-v2` byte-gleich; das Review hat sie in `/tmp/p41-kopie-vrev` unabhängig mit denselben Zahlen nachgespielt.
- **Revision 10.10. (Review-Befunde eingearbeitet).** Geändert: V.2-Testblock (nur Docstring von `_p41v_datenkorrektur`), V.3-Prüfskript (+2 Fälle: „systemkorrektur“ klein mit `user_id`; `RECHNUNG_ZUGEORDNET` in Prod-Form), V.3-Testblock (`45 Fälle ok`), V.3-Modul (`KORREKTUR_NAMEN` klein + `name.toLowerCase()`, `FELD_TEXT.invoice`). **Nachspiel des ganzen Textes** auf frischer Kopie `/tmp/p41-kopie-vrev2` (`git archive 1e2238b`, eigener Git-Verlauf; `/tmp/p41v-rev2-tools/nachspiel2.py`: 18 Datei-Schritte in Dokumentreihenfolge, jeder Anker zum Zeitpunkt seines Steps genau einmal), Prüfbefehle und die vier Commit-Befehle wörtlich:
  - **Ausgangsstand V:** alle Zählungen und die drei Hashes wie im Kommentar.
  - **Prozedur V auf `1e2238b`:** `14 failed, 2030 passed, 2 skipped, 1 error`, Abgleich leer (erste Fassung, 1:43 min).
  - **V.1:** Rot `5 failed, 1 passed` (4 × `assert None == 'gernot'`, 1 × `assert None == 1`) → Grün `6 passed`; `grep` 4 und 3; ruff Exit 0. Umfeld (5 Dateien) `981 passed` (erste Fassung und Review; in der Revision nicht wiederholt, Block unverändert, Prozedur V am Ende deckt ihn ab).
  - **V.2:** Rot `3 failed, 5 passed` mit genau den drei Meldungen des Steps → Grün mit V.1 `14 passed`; `grep` 3 bzw. 2 und 1; ruff Exit 0. Umfeld (6 Dateien) `1001 passed` (erste Fassung und Review).
  - **V.3:** Rot `ERR_MODULE_NOT_FOUND` bzw. `1 failed` → `bestellverlauf.check: 45 Fälle ok` (auch mit `TZ=America/New_York`, `TZ=Asia/Tokyo`, `TZ=Pacific/Kiritimati` und über `npx --no-install tsx`), `belegstatus.check: 29 Fälle ok`, `rollen.check: … ok`, `tsc` ohne Ausgabe, `1 passed`. **Gegenprobe:** Das Modul der ersten Fassung fällt am Fall „Runbook 09.10.“ (`actual: 'systemkorrektur'`), ein Modul ohne `invoice` am Fall „Runbook-Form wie in Prod“ (`actual: [ 'invoice: RE-2026-00005' ]`).
  - **V.4:** `tsc` ohne Ausgabe, Build `✓ built in 5.64s`; das Bundle enthält „Verlauf wird geladen“, „NovaERP (Datenkorrektur)“ und `invoice:"Rechnung"`.
  - **Endstand (V.5):** `15 passed`; Prozedur V `14 failed, 2045 passed, 2 skipped, 1 error`, Abgleich leer (1:57 min); ruff (3 Dateien) Exit 0; `bestellverlauf.check: 45 Fälle ok`, `tsc` leer; `git status --short` leer, `git diff --stat HEAD~4..HEAD` = die 8 Dateien.
- **Echte Antwortformen** (Kopie, nach V.1/V.2): Verwaltung `UPDATE_LINE` alt `{'quantity': '4.000', 'unit_price': '4.5000', 'tax_rate': 'REDUZIERT', 'discount_percent': '0'}`, neu `{'position': 1, 'product': 'Erbsen-Schale', 'quantity': '6', …}`; `ADD_LINE` `unit_price: '2.80'`; `DELETE_LINE` `quantity: '2.000'`; `UPDATE` `{'notes': None}` → `{'notes': 'Tor 2'}`, Grund „Kunde rief an“. Halle: `UPDATE_LINE` alt `{'quantity': '4.000'}`, neu `{'position': 1, 'product': 'Erbsen-Schale', 'quantity': '6'}`, `werte_ausgeblendet: true`; `CONFIRM`/`STATUS_CHANGE` vollständig, `false`. Diese Formen stehen als Fälle in der Node-Prüfung. **Produktion** (Review 10.10.): `RECHNUNG_ZUGEORDNET` alt `null`, neu `{"invoice": "RE-…"}`, „Systemkorrektur“ mit `user_id`; `BULK_STATUS_CHANGE` `{"status": "GELIEFERT"}` → `{"status": "FAKTURIERT"}`, „systemkorrektur“ mit `user_id`. In der Kopie aufbereitet: „Status geändert (Sammelaktion) — Geliefert → Fakturiert — NovaERP (Datenkorrektur)“ bzw. „Rechnung zugeordnet — NovaERP (Datenkorrektur) — Rechnung: RE-2026-00005“; Zeitstempel im Prod-Format (`2026-10-09 12:38:11.123456`) → `09.10.2026 14:38`.
- **Nicht gemessen:** Produktion in der Revision selbst (Lesezugriff nicht freigegeben; die Zahlen im Befund „Produktion“ stammen aus dem Review, Abnahme Schritt 1 misst vor dem Deploy erneut). Das Abnahme-Skript `/tmp/p41v-tools/prod_audit.py` (nur `SELECT`, `mode=ro`) vergleicht Systemnamen jetzt ohne Groß-/Kleinschreibung und zählt sie je mit/ohne `user_id` (gegen eine synthetische DB in Prod-Form geprüft: die alte Fassung zählte 5 × „systemkorrektur“ als `<Person>`, die neue zeigt sie; Vorfassung `/tmp/p41v-rev2-tools/prod_audit.vorher.py`). Oberfläche im Browser; Zusammenspiel mit den anderen Abschnitten von 4.1. → Abnahme.

### Vorbereitung V (vor Task 8)

- [ ] **Basis V festhalten:** `git rev-parse HEAD` → Hash als `<Basis-V>` in den Bericht (= Commit von Task 7, D.4).
- „Ausgangsstand V“ (Anker und die drei Hashes) ist im Kopf auf der Basis geprüft. Seitdem hat nur D.2 (Task 5) eine Datei von V geändert: `sales.py` am Importblock aus `order_status_service` und in `_generate_order_number` — getrennt von den V-Ankern. Die V-Anker prüft jeder Step selbst (Stoppregel 1 nur, wenn einer inhaltlich fehlt).
- N zur Orientierung (Prozedur V, maßgeblich sind die Namen): vor V `2066`, nach V.1 `2072`, nach V.2 `2080`, nach V.3 und V.4 `2081`. V allein auf `1e2238b`: 2030 → 2036 → 2044 → 2045.

**Stoppregeln:** 1–5 aus Global Constraints. Stoppregel 4 gilt für die Umfeld-Läufe in V.1/V.2 (Task 8/9 Step 4): kein Bestandstest wird in V angepasst.

---

### Task 8 (V.1): Änderungen an Bestellungen nennen den Benutzer und die Position

**Files:**
- Create/Modify: `backend/tests/test_paket4_1.py` (Kopf, falls die Datei fehlt; Block V.1 ans Dateiende)
- Modify: `backend/app/api/v1/sales.py` (`_create_audit_log`; die Aufrufe in `update_order`, `add_order_line`, `update_order_line`, `delete_order_line`)

**Interfaces:**
- Produces:
  - `_create_audit_log(db, order, user_id, action, old_values=None, new_values=None, reason=None, user_name=None)` — neuer letzter Parameter `user_name`, gespeichert in `OrderAuditLog.user_name`.
  - Einträge `UPDATE`, `ADD_LINE`, `UPDATE_LINE`, `DELETE_LINE` tragen `user_name` = `user["username"]` (Token `preferred_username`; ohne Login `None`).
  - `UPDATE_LINE.new_values` zusätzlich `"position": <int>`, `"product": <Bezeichnung der Position>` (vor `quantity`); `old_values` unverändert.
- Consumes: `CurrentUser` (`user` in den vier Endpunkten), `OrderLine.position`, `OrderLine.beschreibung`.
- Unverändert: alle anderen Werte und Aktionen, `setze_status`, Import, Steuersatz-Korrektur; Bestandstests, die `UPDATE_LINE` lesen (`test_gernot_261008.py` `tax_rate`, `TestQ4PositionsrabattImAudit` `discount_percent`), bleiben grün.

**Review Focus (V.1):** `user_name` kommt aus dem Token wie in `setze_status` (`(user or {}).get("username")`), nie aus der Anfrage. Keine Migration (Spalte vorhanden). Alteinträge bleiben ohne Namen (E-V3).

- [ ] **Step 1: Testdatei anlegen (nur falls sie fehlt — im Gesamtplan besteht sie seit Task 1, der Befehl ändert dann nichts) und Block V.1 ans Dateiende hängen.**

```bash
test -f backend/tests/test_paket4_1.py || printf '"""Paket 4.1 — Restpunkte aus der Paket-4-Abnahme. Gemeinsame Testdatei aller\nAbschnitte: Klassen TestP41V…/TestP41Z…/TestP41R…/TestP41D…, Helfer\n_p41v_…/_p41z_…/_p41r_…/_p41d_… (ein gleichnamiger Helfer würde still ersetzt).\nKeine autouse-Fixture; Einzeltests über Klassen-IDs, nie -k."""\n' > backend/tests/test_paket4_1.py
```

Block (unverändert ans Dateiende; die zwei Leerzeilen am Anfang gehören dazu):

```python


# =============================================================================
# Abschnitt V — Bestellverlauf in der Oberfläche (Paket-4-Abnahme, „offen“)
# Präfixe: Klassen TestP41V…, Helfer _p41v_…, Konstanten _P41V_…
# =============================================================================
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.api.deps import get_current_user
from app.main import app
from tests.conftest import TestingSessionLocal

_P41V_USER_ID = "123e4567-e89b-12d3-a456-426614174000"


def _p41v_als(*rollen, name="p41v"):
    """Login mit genau diesen Rollen und diesem Benutzernamen (Muster _p4d_als).
    Das client-Fixture setzt das Login beim nächsten Test neu."""
    async def override():
        return {"id": _P41V_USER_ID, "username": name, "email": "p41v@example.com",
                "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


def _p41v_verwaltung():
    """Standard-Login des client-Fixtures (conftest.py): admin + Planung, testuser."""
    _p41v_als("admin", "production_planner", name="testuser")


def _p41v_bestellung(client):
    """Bestätigte Bestellung mit zwei freien Positionen, angelegt von der Verwaltung."""
    _p41v_verwaltung()
    r = client.post("/api/v1/sales/customers", json={
        "name": f"Verlaufskunde {uuid.uuid4().hex[:6]}", "typ": "GASTRO"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": r.json()["id"],
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [
            {"product_name": "Erbsen-Schale", "quantity": 4, "unit": "STK",
             "unit_price": "4.50", "tax_rate": "REDUZIERT"},
            {"product_name": "Radieschen-Schale", "quantity": 2, "unit": "STK",
             "unit_price": "3.20", "tax_rate": "REDUZIERT"},
        ],
    })
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/sales/orders/{r.json()['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _p41v_verlauf(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
    assert r.status_code == 200, r.text
    return r.json()


def _p41v_eintrag(verlauf, aktion):
    treffer = [e for e in verlauf if e["action"] == aktion]
    assert len(treffer) == 1, treffer
    return treffer[0]


def _p41v_aenderungen(client, order):
    """Je eine Änderung an Kopf und Positionen der bestätigten Bestellung —
    UPDATE, ADD_LINE, UPDATE_LINE, DELETE_LINE (sales.py, _create_audit_log)."""
    basis = f"/api/v1/sales/orders/{order['id']}"
    erste, zweite = order["lines"][0], order["lines"][1]
    r = client.patch(basis, json={"notes": "Tor 2", "change_reason": "Kunde rief an"})
    assert r.status_code == 200, r.text
    r = client.post(f"{basis}/lines", json={
        "product_name": "Senf-Schale", "quantity": 1, "unit": "STK", "unit_price": "2.80"})
    assert r.status_code == 201, r.text
    r = client.patch(f"{basis}/lines/{erste['id']}", json={"quantity": 6})
    assert r.status_code == 200, r.text
    r = client.delete(f"{basis}/lines/{zweite['id']}")
    assert r.status_code == 204, r.text


class TestP41VVerlaufWer:
    """Gernot sieht im Verlauf, wer etwas geändert hat. Statuswechsel und Importe
    speichern den Benutzernamen schon (order_status_service.setze_status,
    imports); Änderungen an Kopf und Positionen (sales._create_audit_log) bisher
    nur die Benutzer-ID — die Oberfläche hätte keinen Namen."""

    @pytest.mark.parametrize("aktion", ["UPDATE", "ADD_LINE", "UPDATE_LINE", "DELETE_LINE"])
    def test_aenderung_nennt_den_benutzer(self, client, aktion):
        order = _p41v_bestellung(client)
        _p41v_als("admin", name="gernot")
        _p41v_aenderungen(client, order)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), aktion)

        assert eintrag["user_name"] == "gernot"
        assert eintrag["user_id"] == _P41V_USER_ID

    def test_statuswechsel_und_grund_wie_bisher(self, client):
        """Wächter: CONFIRM trug den Namen schon, UPDATE den Änderungsgrund."""
        order = _p41v_bestellung(client)
        _p41v_aenderungen(client, order)
        verlauf = _p41v_verlauf(client, order)

        bestaetigt = _p41v_eintrag(verlauf, "CONFIRM")
        assert bestaetigt["user_name"] == "testuser"
        assert (bestaetigt["old_values"], bestaetigt["new_values"]) == (
            {"status": "ENTWURF"}, {"status": "BESTAETIGT"})
        assert _p41v_eintrag(verlauf, "UPDATE")["reason"] == "Kunde rief an"

    def test_geaenderte_position_nennt_nummer_und_produkt(self, client):
        """UPDATE_LINE trug nur Menge, Preis, Steuersatz und Rabatt — welche
        Position, stand nirgends (line_id setzt _create_audit_log nicht)."""
        order = _p41v_bestellung(client)
        _p41v_aenderungen(client, order)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "UPDATE_LINE")

        assert eintrag["new_values"].get("position") == 1
        assert eintrag["new_values"].get("product") == "Erbsen-Schale"
        assert Decimal(eintrag["old_values"]["quantity"]) == 4
        assert Decimal(eintrag["new_values"]["quantity"]) == 6
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufWer -q -p no:cacheprovider 2>&1 | tail -8
```

Erwartet: **`5 failed, 1 passed`**.
- Rot: `test_aenderung_nennt_den_benutzer[UPDATE|ADD_LINE|UPDATE_LINE|DELETE_LINE]` (je `AssertionError: assert None == 'gernot'`), `test_geaenderte_position_nennt_nummer_und_produkt` (`AssertionError: assert None == 1`).
- Grün bleibt der Wächter `test_statuswechsel_und_grund_wie_bisher`.

- [ ] **Step 3: Implementierung.**

`backend/app/api/v1/sales.py`, Signatur und Rumpfanfang von `_create_audit_log`: diesen Block

```python
    new_values: Optional[dict] = None,
    reason: Optional[str] = None
) -> OrderAuditLog:
    """Erstellt Audit-Log-Eintrag für Bestellung."""
    audit_log = OrderAuditLog(
        order_id=order.id,
        user_id=user_id,
        action=action,
```

ersetzen durch

```python
    new_values: Optional[dict] = None,
    reason: Optional[str] = None,
    user_name: Optional[str] = None,
) -> OrderAuditLog:
    """Erstellt Audit-Log-Eintrag für Bestellung.

    user_name: Benutzername aus dem Token wie bei Statuswechseln
    (order_status_service.setze_status) — der Bestellverlauf zeigt ihn als
    „wer“ (Paket 4.1, V.1)."""
    audit_log = OrderAuditLog(
        order_id=order.id,
        user_id=user_id,
        user_name=user_name,
        action=action,
```

`backend/app/api/v1/sales.py`, Aufruf in `update_order`: diesen Block

```python
            user_id=UUID(user["id"]) if user else None,
            action="UPDATE",
```

ersetzen durch

```python
            user_id=UUID(user["id"]) if user else None,
            user_name=(user or {}).get("username"),
            action="UPDATE",
```

`backend/app/api/v1/sales.py`, Aufruf in `add_order_line`: diesen Block

```python
            user_id=UUID(user["id"]) if user else None,
            action="ADD_LINE",
```

ersetzen durch

```python
            user_id=UUID(user["id"]) if user else None,
            user_name=(user or {}).get("username"),
            action="ADD_LINE",
```

`backend/app/api/v1/sales.py`, Aufruf in `update_order_line`: diesen Block

```python
            user_id=UUID(user["id"]) if user else None,
            action="UPDATE_LINE",
```

ersetzen durch

```python
            user_id=UUID(user["id"]) if user else None,
            user_name=(user or {}).get("username"),
            action="UPDATE_LINE",
```

`backend/app/api/v1/sales.py`, Aufruf in `delete_order_line`: diesen Block

```python
            user_id=UUID(user["id"]) if user else None,
            action="DELETE_LINE",
```

ersetzen durch

```python
            user_id=UUID(user["id"]) if user else None,
            user_name=(user or {}).get("username"),
            action="DELETE_LINE",
```

`backend/app/api/v1/sales.py`, Werte von `UPDATE_LINE` in `update_order_line` (nach dem vorigen Ersetzen eindeutig): diesen Block

```python
            action="UPDATE_LINE",
            old_values=old_values,
            new_values={
                "quantity": str(line.quantity),
```

ersetzen durch

```python
            action="UPDATE_LINE",
            old_values=old_values,
            new_values={
                # Welche Position (der Verlauf nennt sie; Paket 4.1, V.1)
                "position": line.position,
                "product": line.beschreibung,
                "quantity": str(line.quantity),
```

- [ ] **Step 4: Grün und Umfeld.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufWer -q -p no:cacheprovider 2>&1 | tail -1
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_gernot_261008_paket2.py tests/test_gernot_261008_paket3.py tests/test_import_bestellungen_zukunft.py tests/test_paket4.py -q -p no:cacheprovider 2>&1 | tail -1
grep -c 'user_name=(user or {}).get("username"),' backend/app/api/v1/sales.py   # 4
grep -c '"position": line.position,' backend/app/api/v1/sales.py               # 3
cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/sales.py tests/test_paket4_1.py
```

Erwartet: `6 passed`, dann `981 passed` (auf `1e2238b` und im Gesamt-Nachspiel nach R und D.1–D.4 gleich; maßgeblich: kein `failed`/`error` — Stoppregel 4), die `grep`-Zählungen wie im Kommentar, `ruff` ohne Ausgabe (Exit 0).

- [ ] **Step 5: Commit.**

```bash
git add backend/app/api/v1/sales.py backend/tests/test_paket4_1.py
git commit -m "fix(verlauf): Änderungen an Bestellungen nennen den Benutzer und die Position (P41-V.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9 (V.2): Die Halle sieht im Verlauf keine Preise, Rabatte und Beträge

**Files:**
- Modify: `backend/tests/test_paket4_1.py` (Block V.2 ans Dateiende)
- Modify: `backend/app/schemas/order.py` (`OrderAuditLogResponse`)
- Modify: `backend/app/api/v1/sales.py` (vor und in `get_order_audit_log`)

**Interfaces:**
- Produces:
  - `OrderAuditLogResponse.werte_ausgeblendet: bool = False`.
  - `GET /api/v1/sales/orders/{order_id}/audit-log`: unverändert für Logins mit `sieht_konditionen` (Admin, Vertrieb, Buchhaltung, Planung; auch Halle + eine dieser Rollen); für alle anderen je Eintrag `old_values`/`new_values` nur mit Schlüsseln aus `VERLAUF_WERTE_FUER_ALLE`, `werte_ausgeblendet = true`, sobald einer wegfiel. `null` bleibt `null`, `{}` bleibt `{}`. Reihenfolge, 404, Aktion, Name, Zeit und Grund unverändert.
  - `app.api.v1.sales.VERLAUF_WERTE_FUER_ALLE` (frozenset, 15 Schlüssel), `_verlaufswerte_ohne_konditionen(werte) -> (dict|None, bool)`.
- Consumes: `sieht_konditionen` (schon importiert aus `app.core.rollen`), `CurrentUser`.

**Review Focus (V.2):** Positivliste, nicht Sperrliste (E-V5). Die Halle behält Lesezugriff (kein 403, sonst bräche der Belege-Dialog für sie). Kein Eingriff in `main.py`/`rollen.py`; der P4-D-Wachhund (`TestP4DHalleOhneGeldUndKonditionen`) bleibt unverändert.

- [ ] **Step 1: Block V.2 ans Dateiende von `backend/tests/test_paket4_1.py` hängen** (unverändert; die zwei Leerzeilen am Anfang gehören dazu; nutzt die Helfer aus V.1):

```python


def _p41v_halle_aendert_preis(client):
    """Bestätigte Bestellung; die Halle ändert Menge, Preis und Rabatt der ersten
    Position (per API erlaubt, Paket 3 Q4.8, Frage 4 offen) und packt sie."""
    order = _p41v_bestellung(client)
    _p41v_als("production_staff", name="halle")
    r = client.patch(f"/api/v1/sales/orders/{order['id']}/lines/{order['lines'][0]['id']}",
                     json={"quantity": 6, "unit_price": "3.80", "discount_percent": 10})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/sales/orders/{order['id']}/status", json={"status": "IN_PRODUKTION"})
    assert r.status_code == 200, r.text
    return order


def _p41v_datenkorrektur(order):
    """Eintrag wie aus einem Korrektur-Runbook. Prod (10.10.): RECHNUNG_ZUGEORDNET,
    Name „Systemkorrektur“ mit user_id, alt NULL, neu {"invoice": "RE-…"}. Hier
    bewusst mit erfundenen Schlüsseln auf beiden Seiten (alt invoice_id, neu
    invoice_id/rechnung/betrag): Der Filter muss jeden Schlüssel außerhalb der
    Positivliste wegnehmen, auch in old_values."""
    from app.models.order import OrderAuditLog
    with TestingSessionLocal() as db:
        db.add(OrderAuditLog(
            order_id=uuid.UUID(order["id"]), user_id=None, user_name="Systemkorrektur",
            action="RECHNUNG_ZUGEORDNET",
            old_values={"invoice_id": None},
            new_values={"invoice_id": str(uuid.uuid4()), "rechnung": "RE-2026-09999",
                        "betrag": "123.45"},
            reason="Rechnung zugeordnet (Datenkorrektur)"))
        db.commit()


class TestP41VVerlaufRechte:
    """Den Verlauf lesen alle Rollen des Auftragsrouters (main.py, _deps_auftraege),
    auch die Halle. Logins ohne Konditionssicht (rollen.sieht_konditionen, P4-D.2)
    bekommen nur die Werte aus sales.VERLAUF_WERTE_FUER_ALLE: Preise, Rabatte,
    Steuersätze, Beträge und unbekannte Schlüssel fallen weg, und
    werte_ausgeblendet sagt der Oberfläche, dass etwas fehlt."""

    def test_halle_sieht_menge_aber_keinen_preis_und_rabatt(self, client):
        order = _p41v_halle_aendert_preis(client)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "UPDATE_LINE")

        assert set(eintrag["old_values"]) == {"quantity"}
        assert set(eintrag["new_values"]) == {"position", "product", "quantity"}
        assert eintrag["werte_ausgeblendet"] is True
        assert eintrag["user_name"] == "halle"

    def test_halle_sieht_statuswechsel_vollstaendig(self, client):
        order = _p41v_halle_aendert_preis(client)

        verlauf = _p41v_verlauf(client, order)

        for aktion, alt, neu in (("CONFIRM", "ENTWURF", "BESTAETIGT"),
                                 ("STATUS_CHANGE", "BESTAETIGT", "IN_PRODUKTION")):
            eintrag = _p41v_eintrag(verlauf, aktion)
            assert (eintrag["old_values"], eintrag["new_values"]) == ({"status": alt}, {"status": neu})
            assert eintrag["werte_ausgeblendet"] is False

    def test_halle_sieht_keine_werte_aus_datenkorrekturen(self, client):
        order = _p41v_bestellung(client)
        _p41v_datenkorrektur(order)
        _p41v_als("production_staff", name="halle")

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "RECHNUNG_ZUGEORDNET")

        assert (eintrag["old_values"], eintrag["new_values"]) == ({}, {})
        assert eintrag["werte_ausgeblendet"] is True
        assert eintrag["user_name"] == "Systemkorrektur"
        assert eintrag["reason"] == "Rechnung zugeordnet (Datenkorrektur)"

    @pytest.mark.parametrize("rollen", [
        ("admin",), ("sales",), ("accounting",), ("production_planner",),
        ("production_staff", "sales"),  # Zusatzrolle: hat_rolle prüft „mindestens eine“
    ])
    def test_rollen_mit_konditionssicht_sehen_preis_und_rabatt(self, client, rollen):
        order = _p41v_halle_aendert_preis(client)
        _p41v_als(*rollen)

        eintrag = _p41v_eintrag(_p41v_verlauf(client, order), "UPDATE_LINE")

        assert Decimal(eintrag["old_values"]["unit_price"]) == Decimal("4.50")
        assert Decimal(eintrag["new_values"]["unit_price"]) == Decimal("3.80")
        assert Decimal(eintrag["new_values"]["discount_percent"]) == 10
        assert eintrag.get("werte_ausgeblendet", False) is False
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufRechte -q -p no:cacheprovider 2>&1 | tail -8
```

Erwartet: **`3 failed, 5 passed`**.
- Rot:
  - `test_halle_sieht_menge_aber_keinen_preis_und_rabatt` (`AssertionError: assert {'discount_pe... 'unit_price'} == {'quantity'}`)
  - `test_halle_sieht_statuswechsel_vollstaendig` (`KeyError: 'werte_ausgeblendet'`)
  - `test_halle_sieht_keine_werte_aus_datenkorrekturen` (`AssertionError: assert ({'invoice_id...-2026-09999'}) == ({}, {})`)
- Grün bleiben die Wächter `test_rollen_mit_konditionssicht_sehen_preis_und_rabatt[rollen0…rollen4]` (admin, sales, accounting, production_planner, Halle + sales).

- [ ] **Step 3: Implementierung.**

`backend/app/schemas/order.py`, Ende von `OrderAuditLogResponse`: diesen Block

```python
    created_at: datetime
    reason: Optional[str]


# ==================== LIST SCHEMAS ====================
```

ersetzen durch

```python
    created_at: datetime
    reason: Optional[str]
    # Paket 4.1, V.2: true, wenn der Server Werte für dieses Login ausgeblendet
    # hat (Logins ohne Konditionssicht, sales.VERLAUF_WERTE_FUER_ALLE)
    werte_ausgeblendet: bool = False


# ==================== LIST SCHEMAS ====================
```

`backend/app/api/v1/sales.py`, `get_order_audit_log` (der ganze Endpunkt, Decorator bis `return`): diesen Block

```python
@router.get("/orders/{order_id}/audit-log", response_model=list[OrderAuditLogResponse])
async def get_order_audit_log(order_id: UUID, db: DBSession):
    """Änderungsprotokoll einer Bestellung abrufen."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    audit_logs = db.execute(
        select(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
        .order_by(OrderAuditLog.created_at.desc())
    ).scalars().all()

    return [OrderAuditLogResponse.model_validate(log) for log in audit_logs]
```

ersetzen durch

```python
# Bestellverlauf für Logins ohne Konditionssicht (die Halle; Paket 4.1, V.2 —
# Gernot 09.10. zu „Rolle Produktion ohne Rechnungen/Konditionen“: „Danke!“).
# Positivliste: nur Werte, die die Halle an der Bestellung selbst sieht und für
# Packen und Liefern braucht. Preise, Rabatte, Steuersätze, Beträge und jeder
# hier nicht genannte Schlüssel (z. B. aus Korrektur-Runbooks) fallen weg.
VERLAUF_WERTE_FUER_ALLE = frozenset({
    "status", "actual_delivery_date", "requested_delivery_date",
    "confirmed_delivery_date", "packing_date", "customer_reference",
    "notes", "internal_notes", "billing_address", "delivery_address",
    "position", "product", "quantity", "bestell_nr_extern", "datei",
})


def _verlaufswerte_ohne_konditionen(werte: Optional[dict]) -> tuple[Optional[dict], bool]:
    """(sichtbare Werte, ob etwas ausgeblendet wurde) — für Logins ohne Konditionssicht."""
    if not werte:
        return werte, False
    sichtbar = {feld: wert for feld, wert in werte.items() if feld in VERLAUF_WERTE_FUER_ALLE}
    return sichtbar, len(sichtbar) != len(werte)


@router.get("/orders/{order_id}/audit-log", response_model=list[OrderAuditLogResponse])
async def get_order_audit_log(order_id: UUID, db: DBSession, user: CurrentUser):
    """Änderungsprotokoll einer Bestellung (Bestellverlauf im Belege-Dialog).

    Logins ohne Konditionssicht (rollen.sieht_konditionen) bekommen je Eintrag
    nur die Werte aus VERLAUF_WERTE_FUER_ALLE; werte_ausgeblendet zeigt an,
    dass etwas fehlt (Paket 4.1, V.2)."""
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    audit_logs = db.execute(
        select(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
        .order_by(OrderAuditLog.created_at.desc())
    ).scalars().all()

    eintraege = [OrderAuditLogResponse.model_validate(log) for log in audit_logs]
    if sieht_konditionen(user):
        return eintraege
    gefiltert = []
    for eintrag in eintraege:
        alt, alt_ausgeblendet = _verlaufswerte_ohne_konditionen(eintrag.old_values)
        neu, neu_ausgeblendet = _verlaufswerte_ohne_konditionen(eintrag.new_values)
        gefiltert.append(eintrag.model_copy(update={
            "old_values": alt, "new_values": neu,
            "werte_ausgeblendet": alt_ausgeblendet or neu_ausgeblendet,
        }))
    return gefiltert
```

- [ ] **Step 4: Grün und Umfeld.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufRechte tests/test_paket4_1.py::TestP41VVerlaufWer -q -p no:cacheprovider 2>&1 | tail -1
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008.py tests/test_gernot_261008_paket2.py tests/test_gernot_261008_paket3.py tests/test_import_bestellungen_zukunft.py tests/test_paket4.py tests/test_rollen.py -q -p no:cacheprovider 2>&1 | tail -1
grep -c 'VERLAUF_WERTE_FUER_ALLE' backend/app/api/v1/sales.py                       # 3
grep -c 'werte_ausgeblendet' backend/app/api/v1/sales.py backend/app/schemas/order.py  # backend/app/api/v1/sales.py:2 und backend/app/schemas/order.py:1
cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/sales.py app/schemas/order.py tests/test_paket4_1.py
```

Erwartet: `14 passed`, dann `1001 passed` (auf `1e2238b` und im Gesamt-Nachspiel gleich; maßgeblich: kein `failed`/`error`), die `grep`-Zählungen wie im Kommentar, `ruff` ohne Ausgabe.

- [ ] **Step 5: Commit.**

```bash
git add backend/app/api/v1/sales.py backend/app/schemas/order.py backend/tests/test_paket4_1.py
git commit -m "feat(verlauf): Halle sieht im Bestellverlauf keine Preise, Rabatte und Beträge (P41-V.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10 (V.3): Verlauf aufbereiten — reine Funktionen mit Node-Prüfung

**Files:**
- Create: `frontend/tests/unit/bestellverlauf.check.ts`
- Create: `frontend/src/services/bestellverlauf.ts`
- Modify: `backend/tests/test_paket4_1.py` (Block V.3 ans Dateiende: Node-Prüfung im Vollauf)

**Interfaces:**
- Produces:
  - **Typen:** `VerlaufEintrag` (Antwortform aus V.2, `werte_ausgeblendet?`), `VerlaufZeile {id, zeit, aktion, status, wer, details, grund}`.
  - **Texte:** `AKTION_TEXT` (13 Aktionen: die 11 aus dem Code + `CREATE`, `RECHNUNG_ZUGEORDNET`), `FELD_TEXT` (mit `invoice` aus Runbooks), `AUSGEBLENDET_TEXT`.
  - **Funktionen:** `zeitBerlin(wert)`, `aktionText(action)`, `werText(e)`, `wertText(feld, wert)`, `statusText(e)`, `detailsText(e)`, `verlaufAufbereiten(eintraege)`.
- Consumes: `orderStatusLabel` aus `../components/ui/statusLabels.ts`; die Antwortform aus V.1/V.2.

**Review Focus (V.3):** Zeit ist UTC ohne Zone und wird in Berlin gezeigt (Sommer-/Winterzeit). Systemnamen ohne Rücksicht auf Groß-/Kleinschreibung (Prod: 574 × „systemkorrektur“). Statuswörter kommen aus `statusLabels.ts`, keine zweite Liste. Die Prüfung liest die Aktionen aus dem Backend (fünf Dateien) — wer eine neue Aktion schreibt, muss sie übersetzen.

- [ ] **Step 1: Prüfskript und Test.**

`frontend/tests/unit/bestellverlauf.check.ts` mit genau diesem Inhalt anlegen:

```ts
// Prüft die Aufbereitung des Bestellverlaufs ohne Browser und ohne Testframework
// (Paket 4.1, Abschnitt V). Lauf: node tests/unit/bestellverlauf.check.ts
// (Node >= 23.6: TypeScript ohne Build) oder npx --no-install tsx tests/unit/bestellverlauf.check.ts
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  AKTION_TEXT, AUSGEBLENDET_TEXT, aktionText, detailsText, statusText, verlaufAufbereiten,
  werText, wertText, zeitBerlin,
} from '../../src/services/bestellverlauf.ts';
import type { VerlaufEintrag } from '../../src/services/bestellverlauf.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

function eintrag(teil: Partial<VerlaufEintrag>): VerlaufEintrag {
  return {
    id: 'e1', order_id: 'o1', action: 'UPDATE', field_name: null, line_id: null,
    old_values: null, new_values: null, user_id: 'u1', user_name: 'testuser',
    created_at: '2026-10-09T21:07:12.123456', reason: null, ...teil,
  };
}

// Jede Aktion, die der Server schreibt, hat einen deutschen Text (Gegenstück:
// action="…" in den fünf Backend-Dateien, auch der Standardwert von setze_status)
const dateien = ['app/api/v1/sales.py', 'app/api/v1/imports.py', 'app/api/v1/documents.py',
  'app/services/steuersatz_korrektur.py', 'app/services/order_status_service.py'];
const imCode = new Set<string>();
for (const datei of dateien) {
  const py = readFileSync(new URL(`../../../backend/${datei}`, import.meta.url), 'utf8');
  for (const treffer of py.matchAll(/\baction(?::\s*str)?\s*=\s*"([A-Z_]+)"/g)) imCode.add(treffer[1]);
}
gleich([...imCode].sort(), ['ADD_LINE', 'BULK_STATUS_CHANGE', 'CONFIRM', 'DELETE_LINE', 'IMPORT',
  'LIEFERDATUM_NACHGETRAGEN', 'LIEFERSCHEIN_QUITTIERT', 'STATUS_CHANGE', 'STEUERSATZ_KORREKTUR',
  'UPDATE', 'UPDATE_LINE'], 'Aktionen im Backend');
gleich([...imCode].filter((a) => !(a in AKTION_TEXT)), [], 'jede Aktion übersetzt');
gleich(aktionText('LIEFERSCHEIN_QUITTIERT'), 'Lieferschein quittiert', 'Aktion');
gleich(aktionText('RECHNUNG_ZUGEORDNET'), 'Rechnung zugeordnet', 'Runbook-Aktion');
gleich(aktionText('STATUS_KORREKTUR'), 'Sonstige Änderung (STATUS_KORREKTUR)', 'unbekannte Aktion');

// Zeit: Server speichert UTC ohne Zone, angezeigt in Berlin (Sommer-/Winterzeit)
gleich(zeitBerlin('2026-10-09T21:07:12.123456'), '09.10.2026 23:07', 'Sommerzeit');
gleich(zeitBerlin('2026-10-31T23:30:00'), '01.11.2026 00:30', 'Winterzeit, Tageswechsel');
gleich(zeitBerlin('2026-10-09T21:07:12Z'), '09.10.2026 23:07', 'mit Zone');
gleich(zeitBerlin('kein Datum'), '', 'unlesbar');

// Wer
gleich(werText({ user_name: 'gernot', user_id: 'u1' }), 'gernot', 'Benutzer');
gleich(werText({ user_name: 'Systemkorrektur', user_id: null }), 'NovaERP (Datenkorrektur)', 'Runbook');
gleich(werText({ user_name: 'systemkorrektur', user_id: 'u1' }), 'NovaERP (Datenkorrektur)', 'Runbook 09.10. (Prod: klein, mit user_id)');
gleich(werText({ user_name: 'Datenkorrektur', user_id: null }), 'NovaERP (Datenkorrektur)', 'Steuersatz-Korrektur');
gleich(werText({ user_name: null, user_id: 'u1' }), 'Benutzer (Name nicht gespeichert)', 'Alteintrag vor V.1');
gleich(werText({ user_name: null, user_id: null }), 'System (automatisch)', 'ohne Login');

// Status mit den Wörtern der übrigen Oberfläche (statusLabels.ts)
gleich(statusText({ old_values: { status: 'ENTWURF' }, new_values: { status: 'BESTAETIGT' } }),
  'Entwurf → Bestätigt', 'Bestätigen');
gleich(statusText({ old_values: { status: 'BESTAETIGT' }, new_values: { status: 'IN_PRODUKTION' } }),
  'Bestätigt → Gepackt', 'IN_PRODUKTION heißt Gepackt');
gleich(statusText({ old_values: null, new_values: { status: 'BESTAETIGT' } }), 'Bestätigt', 'Import');
gleich(statusText({ old_values: { notes: null }, new_values: { notes: 'Tor 2' } }), null, 'kein Status');

// Werte als Kurztext
gleich(wertText('quantity', '4.000'), '4', 'Menge ganz');
gleich(wertText('quantity', '2.500'), '2,5', 'Menge mit Komma');
gleich(wertText('unit_price', '4.5000'), '4,50 €', 'Preis');
gleich(wertText('unit_price', '0.0833'), '0,0833 €', 'Preis mit 4 Stellen');
gleich(wertText('discount_percent', '10.00'), '10 %', 'Rabatt');
gleich(wertText('tax_rate', 'REDUZIERT'), '7 %', 'Steuersatz');
gleich(wertText('requested_delivery_date', '2026-10-12'), '12.10.2026', 'Tag');
gleich(wertText('notes', null), 'leer', 'leer');
gleich(wertText('notes', 'x'.repeat(80)), `${'x'.repeat(59)}…`, 'gekürzt');
gleich(wertText('customer_reference', '4711'), '4711', 'Nummer bleibt Text');

// Details je Aktion (Formen wie vom Server, gemessen auf 1e2238b + V.1/V.2)
gleich(detailsText(eintrag({
  action: 'UPDATE_LINE',
  old_values: { quantity: '4.000', unit_price: '4.5000', tax_rate: 'REDUZIERT', discount_percent: '0' },
  new_values: { position: 1, product: 'Erbsen-Schale', quantity: '6', unit_price: '4.5000', tax_rate: 'REDUZIERT', discount_percent: '0' },
})), ['Pos. 1 · Erbsen-Schale', 'Menge: 4 → 6'], 'Menge geändert');
gleich(detailsText(eintrag({
  action: 'UPDATE_LINE',
  old_values: { discount_percent: '0', quantity: '4.000', tax_rate: 'REDUZIERT', unit_price: '4.5000' },
  new_values: { discount_percent: '10', position: 1, product: 'Erbsen-Schale', quantity: '6', tax_rate: 'REDUZIERT', unit_price: '3.80' },
})), ['Pos. 1 · Erbsen-Schale', 'Menge: 4 → 6', 'Preis: 4,50 € → 3,80 €', 'Rabatt: 0 % → 10 %'], 'Preis und Rabatt, feste Reihenfolge');
gleich(detailsText(eintrag({
  action: 'UPDATE_LINE', werte_ausgeblendet: true,
  old_values: { quantity: '4.000' }, new_values: { position: 1, product: 'Erbsen-Schale', quantity: '6' },
})), ['Pos. 1 · Erbsen-Schale', 'Menge: 4 → 6', AUSGEBLENDET_TEXT], 'Halle');
gleich(detailsText(eintrag({
  action: 'ADD_LINE', new_values: { position: 3, product: 'Senf-Schale', quantity: '1', unit_price: '2.80', discount_percent: '0' },
})), ['Pos. 3 · Senf-Schale', 'Menge: 1', 'Preis: 2,80 €'], 'neue Position ohne Rabatt-Rauschen');
gleich(detailsText(eintrag({
  action: 'DELETE_LINE', old_values: { position: 2, product: 'Radieschen-Schale', quantity: '2.000' },
})), ['Pos. 2 · Radieschen-Schale', 'Menge: 2'], 'Position entfernt');
gleich(detailsText(eintrag({ old_values: { notes: null }, new_values: { notes: 'Tor 2' } })),
  ['Notizen: leer → Tor 2'], 'Kopf geändert');
gleich(detailsText(eintrag({
  old_values: { delivery_address: "{'strasse': 'Hof'}" }, new_values: { delivery_address: "{'strasse': 'Tor 2'}" },
})), ['Lieferadresse geändert'], 'Adresse');
gleich(detailsText(eintrag({
  action: 'STATUS_CHANGE',
  old_values: { status: 'IN_PRODUKTION', actual_delivery_date: null },
  new_values: { status: 'GELIEFERT', actual_delivery_date: '2026-10-09' },
})), ['Geliefert am: leer → 09.10.2026'], 'Ausliefern');
gleich(detailsText(eintrag({
  action: 'IMPORT', new_values: { status: 'BESTAETIGT', bestell_nr_extern: '4711', datei: 'bestellungen.xlsx' },
})), ['Bestellnr. extern: 4711', 'Datei: bestellungen.xlsx'], 'Import');
gleich(detailsText(eintrag({
  action: 'STEUERSATZ_KORREKTUR', user_name: 'Datenkorrektur', user_id: null,
  old_values: { total_vat: '2.17', total_gross: '33.17', positionen: [{ position: 1, tax_rate: 'REDUZIERT', line_vat: '2.17', line_gross: '33.17' }] },
  new_values: { positionen: [{ position: 1, tax_rate: 'STANDARD', line_vat: '5.89', line_gross: '36.89' }], total_vat: '5.89', total_gross: '36.89' },
})), ['Pos. 1: Steuersatz: 7 % → 19 %, MwSt: 2,17 € → 5,89 €, Brutto: 33,17 € → 36,89 €',
  'MwSt gesamt: 2,17 € → 5,89 €', 'Brutto gesamt: 33,17 € → 36,89 €'], 'Steuersatz-Korrektur');
gleich(detailsText(eintrag({
  action: 'RECHNUNG_ZUGEORDNET', user_name: 'Systemkorrektur', old_values: null, new_values: { invoice: 'RE-2026-00005' },
})), ['Rechnung: RE-2026-00005'], 'Runbook-Form wie in Prod (Verwaltung)');
gleich(detailsText(eintrag({ action: 'RECHNUNG_ZUGEORDNET', old_values: {}, new_values: {}, werte_ausgeblendet: true })),
  [AUSGEBLENDET_TEXT], 'Runbook für die Halle');

// Ganze Zeilen: chronologisch (Server liefert neueste zuerst), Grund getrimmt
const roh = [
  eintrag({ id: 'e3', action: 'STATUS_CHANGE', created_at: '2026-10-09T05:10:00.000001',
    old_values: { status: 'BESTAETIGT' }, new_values: { status: 'IN_PRODUKTION' }, reason: 'Im Tagesplan als gepackt markiert' }),
  eintrag({ id: 'e2', action: 'CONFIRM', created_at: '2026-10-09T05:10:00.000001',
    old_values: { status: 'ENTWURF' }, new_values: { status: 'BESTAETIGT' }, reason: 'Beim Packen im Tagesplan bestätigt' }),
  eintrag({ id: 'e1', action: 'UPDATE', created_at: '2026-10-08T16:00:00',
    old_values: { notes: null }, new_values: { notes: 'Tor 2' }, reason: '  ' }),
];
const zeilen = verlaufAufbereiten(roh);
gleich(zeilen.map((z) => z.id), ['e1', 'e2', 'e3'], 'älteste zuerst, gleiche Zeit in Server-Reihenfolge umgekehrt');
gleich(zeilen[1], {
  id: 'e2', zeit: '09.10.2026 07:10', aktion: 'Bestätigt', status: 'Entwurf → Bestätigt', wer: 'testuser',
  details: [], grund: 'Beim Packen im Tagesplan bestätigt',
}, 'Zeile CONFIRM');
gleich(zeilen[0].grund, null, 'leerer Grund');
gleich(verlaufAufbereiten([]), [], 'leer');

console.log(`bestellverlauf.check: ${faelle} Fälle ok`);
```

Diesen Block ans Ende von `backend/tests/test_paket4_1.py` hängen (die zwei Leerzeilen am Anfang gehören dazu):

```python


class TestP41VVerlaufAnzeige:
    """Aufbereitung des Verlaufs (frontend/src/services/bestellverlauf.ts): die
    Node-Prüfung läuft im Vollauf mit (wie TestP4CBelegstatusAnzeige)."""

    def test_node_pruefung(self):
        import os
        import subprocess
        from pathlib import Path
        r = subprocess.run(
            ["node", "tests/unit/bestellverlauf.check.ts"],
            cwd=Path(__file__).resolve().parents[2] / "frontend",
            env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == "bestellverlauf.check: 45 Fälle ok"
```

- [ ] **Step 2: Rot.**

Run: `cd frontend && node tests/unit/bestellverlauf.check.ts`. Erwartet ein Abbruch mit `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '…/frontend/src/services/bestellverlauf.ts' imported from …/frontend/tests/unit/bestellverlauf.check.ts`.
Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufAnzeige -q -p no:cacheprovider 2>&1 | tail -1` → **`1 failed`** (`AssertionError` mit `ERR_MODULE_NOT_FOUND` im Text).

- [ ] **Step 3: Modul anlegen.**

`frontend/src/services/bestellverlauf.ts` mit genau diesem Inhalt anlegen:

```ts
/**
 * Bestellverlauf (Paket 4.1, Abschnitt V): die Einträge von
 * GET /sales/orders/{id}/audit-log für den Belege-Dialog aufbereiten —
 * wann (Berliner Zeit), wer, was (Aktion auf Deutsch), Status alt → neu,
 * geänderte Werte als Kurztext, Grund. Geschrieben werden die Einträge im
 * Server (sales._create_audit_log, order_status_service.setze_status,
 * imports, Datenkorrekturen). Logins ohne Konditionssicht bekommen Preise und
 * Beträge nicht (werte_ausgeblendet, sales.VERLAUF_WERTE_FUER_ALLE).
 *
 * Einziger Import sind die Statuswörter der übrigen Oberfläche; beide Dateien
 * lädt tests/unit/bestellverlauf.check.ts direkt mit Node (Endung .ts nötig).
 */
import { orderStatusLabel } from '../components/ui/statusLabels.ts';

/** Ein Eintrag, wie der Server ihn liefert (schemas/order.py, OrderAuditLogResponse). */
export interface VerlaufEintrag {
  id: string;
  order_id: string;
  action: string;
  field_name: string | null;
  line_id: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  user_id: string | null;
  user_name: string | null;
  created_at: string;
  reason: string | null;
  werte_ausgeblendet?: boolean;
}

/** Eine Zeile der Anzeige. */
export interface VerlaufZeile {
  id: string;
  /** TT.MM.JJJJ HH:MM in Berlin */
  zeit: string;
  aktion: string;
  /** „Bestätigt → Gepackt“, bei einem Import nur der neue Status; sonst null */
  status: string | null;
  wer: string;
  details: string[];
  grund: string | null;
}

/** Alle Aktionen, die Code oder Korrektur-Runbooks schreiben (Stand 1e2238b). */
export const AKTION_TEXT: Record<string, string> = {
  CREATE: 'Angelegt',
  IMPORT: 'Importiert',
  CONFIRM: 'Bestätigt',
  STATUS_CHANGE: 'Status geändert',
  BULK_STATUS_CHANGE: 'Status geändert (Sammelaktion)',
  LIEFERSCHEIN_QUITTIERT: 'Lieferschein quittiert',
  LIEFERDATUM_NACHGETRAGEN: 'Lieferdatum nachgetragen',
  UPDATE: 'Bestellung geändert',
  ADD_LINE: 'Position hinzugefügt',
  UPDATE_LINE: 'Position geändert',
  DELETE_LINE: 'Position entfernt',
  STEUERSATZ_KORREKTUR: 'Steuersatz korrigiert',
  RECHNUNG_ZUGEORDNET: 'Rechnung zugeordnet',
};

export const FELD_TEXT: Record<string, string> = {
  actual_delivery_date: 'Geliefert am',
  requested_delivery_date: 'Liefertag',
  confirmed_delivery_date: 'Bestätigter Liefertag',
  packing_date: 'Packtag',
  customer_reference: 'Kundenbestellnummer',
  notes: 'Notizen',
  internal_notes: 'Interne Notizen',
  billing_address: 'Rechnungsadresse',
  delivery_address: 'Lieferadresse',
  quantity: 'Menge',
  unit_price: 'Preis',
  discount_percent: 'Rabatt',
  tax_rate: 'Steuersatz',
  line_vat: 'MwSt',
  line_gross: 'Brutto',
  positionen: 'Positionen',
  total_vat: 'MwSt gesamt',
  total_gross: 'Brutto gesamt',
  bestell_nr_extern: 'Bestellnr. extern',
  datei: 'Datei',
  // Runbook RECHNUNG_ZUGEORDNET (Prod: neu {"invoice": "RE-…"}); für die Halle ausgeblendet (Server)
  invoice: 'Rechnung',
};

/** Namen, unter denen Korrekturen der NovaERP-Betreuung laufen — klein geschrieben, verglichen
 * ohne Rücksicht auf Groß-/Kleinschreibung (Prod: „systemkorrektur“ und „Systemkorrektur“). */
const KORREKTUR_NAMEN = new Set(['systemkorrektur', 'datenkorrektur']);
export const AUSGEBLENDET_TEXT = 'Preise und Beträge nur für Verwaltung, Vertrieb, Buchhaltung und Planung';

const MIT_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;
const NUR_TAG = /^(\d{4})-(\d{2})-(\d{2})$/;
const STEUERSATZ: Record<string, string> = { STANDARD: '19 %', REDUZIERT: '7 %', STEUERFREI: '0 %' };
const BETRAG = new Set(['unit_price', 'line_vat', 'line_gross', 'total_vat', 'total_gross']);
const MAX_TEXT = 60;

/** Zeitstempel des Servers (UTC ohne Zone, bis zu 6 Nachkommastellen) als Millisekunden. */
function zeitwert(wert: string): number {
  const kurz = wert.replace(/(\.\d{3})\d+/, '$1');
  return new Date(MIT_ZONE.test(kurz) ? kurz : `${kurz}Z`).getTime();
}

/** TT.MM.JJJJ HH:MM in Berliner Zeit; leer bei unlesbarem Wert. */
export function zeitBerlin(wert: string): string {
  const ms = zeitwert(wert);
  if (Number.isNaN(ms)) return '';
  const teile = Object.fromEntries(new Intl.DateTimeFormat('de-DE', {
    timeZone: 'Europe/Berlin', day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(ms)).map((t) => [t.type, t.value]));
  return `${teile.day}.${teile.month}.${teile.year} ${teile.hour}:${teile.minute}`;
}

export function aktionText(action: string): string {
  return AKTION_TEXT[action] ?? `Sonstige Änderung (${action})`;
}

export function werText(e: Pick<VerlaufEintrag, 'user_name' | 'user_id'>): string {
  const name = e.user_name?.trim();
  if (name) return KORREKTUR_NAMEN.has(name.toLowerCase()) ? 'NovaERP (Datenkorrektur)' : name;
  return e.user_id ? 'Benutzer (Name nicht gespeichert)' : 'System (automatisch)';
}

/** Dezimalzahl ohne Tausenderpunkt, Komma, ohne Nullen am Ende („4.000“ → „4“). */
function zahlKurz(n: number, min = 0, max = 3): string {
  let text = n.toFixed(max);
  if (max > min) text = text.replace(new RegExp(`0{1,${max - min}}$`), '');
  return text.replace(/\.$/, '').replace('.', ',');
}

function kuerzen(text: string): string {
  return text.length > MAX_TEXT ? `${text.slice(0, MAX_TEXT - 1)}…` : text;
}

/** Ein Wert als Kurztext, je nach Feld. */
export function wertText(feld: string, wert: unknown): string {
  if (wert === null || wert === undefined || wert === '') return 'leer';
  if (Array.isArray(wert)) return `${wert.length} ${wert.length === 1 ? 'Position' : 'Positionen'}`;
  if (typeof wert === 'object') return 'geändert';
  const text = String(wert);
  // Adressen speichert update_order als Python-Text eines dict
  if (text.startsWith('{')) return 'geändert';
  if (feld === 'status') return orderStatusLabel(text);
  if (feld === 'tax_rate') return STEUERSATZ[text] ?? text;
  const tag = NUR_TAG.exec(text);
  if (tag) return `${tag[3]}.${tag[2]}.${tag[1]}`;
  const zahl = typeof wert === 'number' ? wert : Number(text);
  if (text.trim() !== '' && Number.isFinite(zahl)) {
    if (BETRAG.has(feld)) return `${zahlKurz(zahl, 2, 4)} €`;
    if (feld === 'discount_percent') return `${zahlKurz(zahl, 0, 2)} %`;
    if (feld === 'quantity') return zahlKurz(zahl);
  }
  return kuerzen(text);
}

function feldText(feld: string): string {
  return FELD_TEXT[feld] ?? feld;
}

/** Feste Reihenfolge wie FELD_TEXT, unbekannte Felder zuletzt — unabhängig davon, in welcher
 * Reihenfolge ein Schreibpfad die Schlüssel ablegt. */
const FELD_REIHE = Object.keys(FELD_TEXT);
function rang(feld: string): number {
  const i = FELD_REIHE.indexOf(feld);
  return i < 0 ? FELD_REIHE.length : i;
}

/** Positionsangabe „Pos. 1 · Erbsen-Schale“ aus position/product. */
function positionText(werte: Record<string, unknown>): string | null {
  const teile: string[] = [];
  if (werte.position !== undefined && werte.position !== null) teile.push(`Pos. ${werte.position}`);
  if (werte.product) teile.push(String(werte.product));
  return teile.length ? teile.join(' · ') : null;
}

/** Unterschiede zweier Wertegruppen; gleich formatierte Werte zählen als unverändert. */
function unterschiede(alt: Record<string, unknown>, neu: Record<string, unknown>): string[] {
  const zeilen: string[] = [];
  const felder = [...new Set([...Object.keys(alt), ...Object.keys(neu)])]
    .filter((f) => f !== 'status' && f !== 'position' && f !== 'product')
    .sort((x, y) => rang(x) - rang(y));
  for (const feld of felder) {
    const a = alt[feld];
    const n = neu[feld];
    if (feld in alt && feld in neu) {
      if (Array.isArray(a) && Array.isArray(n)) {
        n.forEach((pos, i) => {
          const altPos = (a[i] ?? {}) as Record<string, unknown>;
          const neuPos = (pos ?? {}) as Record<string, unknown>;
          const was = unterschiede(altPos, neuPos);
          if (was.length) zeilen.push(`${positionText(neuPos) ?? `Pos. ${i + 1}`}: ${was.join(', ')}`);
        });
        continue;
      }
      const vorher = wertText(feld, a);
      const nachher = wertText(feld, n);
      if (vorher !== nachher) zeilen.push(`${feldText(feld)}: ${vorher} → ${nachher}`);
      else if (vorher === 'geändert' && String(a) !== String(n)) zeilen.push(`${feldText(feld)} geändert`);
    } else {
      const wert = feld in neu ? n : a;
      // Neue Position ohne Rabatt: „Rabatt: 0 %“ wäre nur Rauschen
      if (feld === 'discount_percent' && Number(wert) === 0) continue;
      zeilen.push(`${feldText(feld)}: ${wertText(feld, wert)}`);
    }
  }
  return zeilen;
}

/** Status alt → neu; bei einem Eintrag nur mit neuem Status (Import) nur dieser. */
export function statusText(e: Pick<VerlaufEintrag, 'old_values' | 'new_values'>): string | null {
  const alt = e.old_values?.status;
  const neu = e.new_values?.status;
  if (!neu) return null;
  return alt ? `${orderStatusLabel(String(alt))} → ${orderStatusLabel(String(neu))}` : orderStatusLabel(String(neu));
}

export function detailsText(e: VerlaufEintrag): string[] {
  const alt = e.old_values ?? {};
  const neu = e.new_values ?? {};
  const zeilen: string[] = [];
  const position = positionText({ ...alt, ...neu });
  if (position) zeilen.push(position);
  zeilen.push(...unterschiede(alt, neu));
  if (e.werte_ausgeblendet) zeilen.push(AUSGEBLENDET_TEXT);
  return zeilen;
}

/** Chronologisch, älteste zuerst. Der Server liefert die neuesten zuerst; bei
 * gleichem Zeitstempel bleibt dessen Reihenfolge umgekehrt erhalten. */
export function verlaufAufbereiten(eintraege: VerlaufEintrag[]): VerlaufZeile[] {
  return eintraege
    .map((e, i) => ({ e, i, t: zeitwert(e.created_at) }))
    .sort((x, y) => (x.t - y.t) || (y.i - x.i))
    .map(({ e }) => ({
      id: e.id,
      zeit: zeitBerlin(e.created_at),
      aktion: aktionText(e.action),
      status: statusText(e),
      wer: werText(e),
      details: detailsText(e),
      grund: e.reason?.trim() || null,
    }));
}
```

- [ ] **Step 4: Grün.**

```bash
cd frontend && node tests/unit/bestellverlauf.check.ts && node tests/unit/belegstatus.check.ts && node tests/unit/rollen.check.ts && ./node_modules/.bin/tsc --noEmit -p .
cd frontend && npx --no-install tsx tests/unit/bestellverlauf.check.ts || echo "tsx nicht verfügbar (kein Stopp)"
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufAnzeige -q -p no:cacheprovider 2>&1 | tail -1
```

Erwartet: `bestellverlauf.check: 45 Fälle ok`, `belegstatus.check: 29 Fälle ok`, `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`, keine Ausgabe von `tsc`; die zweite Zeile `bestellverlauf.check: 45 Fälle ok` oder der Hinweis (ohne Netzwerk kann `npx` `tsx` nicht laden — kein Stopp, `node` ist maßgeblich); dann **`1 passed`**.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/services/bestellverlauf.ts frontend/tests/unit/bestellverlauf.check.ts backend/tests/test_paket4_1.py
git commit -m "feat(verlauf): Bestellverlauf aufbereiten — Aktion, Status, Werte, Zeit in Berlin (P41-V.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11 (V.4): Abschnitt „Verlauf“ im Belege-Dialog

**Files:**
- Create: `frontend/src/services/bestellverlaufApi.ts`
- Create: `frontend/src/components/domain/OrderVerlauf.tsx`
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx` (Import hinter `InvoiceDetail`; `<OrderVerlauf …/>` am Ende des Dialoginhalts)

**Interfaces:**
- Produces: `bestellverlaufApi.liste(orderId) -> Promise<VerlaufEintrag[]>`; Komponente `OrderVerlauf({ orderId, open })` (Abfrage `['orders', orderId, 'verlauf']`, nur bei `open`); im Belege-Dialog unter den Rechnungen (bzw. unter den Lieferscheinen für Planung und Halle) der Abschnitt „Verlauf“.
- Consumes: `api` (Default-Export aus `services/api.ts`), `verlaufAufbereiten` (V.3), `Button` (`components/ui`), `getErrorMessage` (`services/errors`), lucide-Icon `History` (in lucide-react 0.303 vorhanden).

**Review Focus (V.4):** Lade-, Fehler- und Leer-Zustand (E-V7). Nach „Quittieren“ im Dialog erscheint der Eintrag „Lieferschein quittiert“ ohne Neuöffnen (`invalidate()` → `invalidateOrderViews` → Präfix `['orders']`). Lange Verläufe scrollen im Dialog mit. Halle: Zeile „Preise und Beträge nur für …“.

- [ ] **Step 1: Ausgangsstand.**

```bash
grep -c "^import { InvoiceDetail } from '../../pages/Invoices';$" frontend/src/components/domain/OrderDocumentsModal.tsx   # 1
grep -c 'OrderVerlauf' frontend/src/components/domain/OrderDocumentsModal.tsx                                          # 0
ls frontend/src/services/bestellverlaufApi.ts frontend/src/components/domain/OrderVerlauf.tsx 2>&1 | grep -c 'No such file'   # 2
```

- [ ] **Step 2: Neue Dateien.**

`frontend/src/services/bestellverlaufApi.ts` mit genau diesem Inhalt anlegen:

```ts
/**
 * Bestellverlauf (Paket 4.1, Abschnitt V): GET /sales/orders/{id}/audit-log.
 * Eigene Datei statt api.ts, wie belegstatusApi.ts.
 */
import api from './api';
import type { VerlaufEintrag } from './bestellverlauf';

export const bestellverlaufApi = {
  liste: (orderId: string) =>
    api.get<VerlaufEintrag[]>(`/sales/orders/${orderId}/audit-log`).then((r) => r.data),
};
```

`frontend/src/components/domain/OrderVerlauf.tsx` mit genau diesem Inhalt anlegen:

```tsx
import { useQuery } from '@tanstack/react-query';
import { History } from 'lucide-react';
import { Button } from '../ui';
import { getErrorMessage } from '../../services/errors';
import { bestellverlaufApi } from '../../services/bestellverlaufApi';
import { verlaufAufbereiten } from '../../services/bestellverlauf';

/**
 * Verlauf einer Bestellung im Belege-Dialog (Paket 4.1, Abschnitt V): wann,
 * wer, was, Status alt → neu, Grund — älteste zuerst. Schlüssel unter
 * 'orders', damit invalidateOrderViews (Statuswechsel, Quittieren,
 * Bearbeiten) den Verlauf mit neu lädt.
 */
export function OrderVerlauf({ orderId, open }: { orderId: string; open: boolean }) {
  const verlauf = useQuery({
    queryKey: ['orders', orderId, 'verlauf'],
    queryFn: () => bestellverlaufApi.liste(orderId),
    enabled: open && !!orderId,
  });
  const zeilen = verlauf.data ? verlaufAufbereiten(verlauf.data) : [];

  return (
    <section>
      <h3 className="flex items-center gap-2 font-semibold text-gray-800 dark:text-gray-200 mb-3">
        <History className="w-4 h-4" />
        Verlauf
      </h3>
      {verlauf.isLoading ? (
        <p role="status" className="text-sm text-gray-500 dark:text-gray-400">Verlauf wird geladen…</p>
      ) : verlauf.isError ? (
        <div role="alert" className="flex items-center gap-2 text-sm text-red-700 dark:text-red-300">
          <span>{getErrorMessage(verlauf.error, 'Verlauf konnte nicht geladen werden')}</span>
          <Button size="sm" variant="secondary" onClick={() => verlauf.refetch()}>Erneut laden</Button>
        </div>
      ) : zeilen.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400 italic">
          Noch keine Einträge. Protokolliert werden Statuswechsel, Importe und Änderungen ab der Bestätigung.
        </p>
      ) : (
        <ol className="space-y-2">
          {zeilen.map((z) => (
            <li key={z.id} className="border rounded p-2 text-sm dark:border-gray-700">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-mono text-xs text-gray-500 dark:text-gray-400">{z.zeit}</span>
                <span className="font-medium text-gray-900 dark:text-gray-100">{z.aktion}</span>
                {z.status && <span className="text-gray-700 dark:text-gray-300">{z.status}</span>}
                <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">{z.wer}</span>
              </div>
              {z.details.length > 0 && (
                <ul className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                  {z.details.map((d, i) => <li key={i}>{d}</li>)}
                </ul>
              )}
              {z.grund && <p className="mt-1 text-xs text-gray-600 dark:text-gray-300">Grund: {z.grund}</p>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Einbau in den Belege-Dialog.**

`frontend/src/components/domain/OrderDocumentsModal.tsx`, Importe: diesen Block

```tsx
import { InvoiceDetail } from '../../pages/Invoices';
```

ersetzen durch

```tsx
import { InvoiceDetail } from '../../pages/Invoices';
import { OrderVerlauf } from './OrderVerlauf';
```

`frontend/src/components/domain/OrderDocumentsModal.tsx`, Ende des Dialoginhalts (Schluss des Rechnungsabschnitts): diesen Block

```tsx
        </section>
        )}
      </div>
    </Modal>
```

ersetzen durch

```tsx
        </section>
        )}

        {/* VERLAUF — alle Rollen; die Halle ohne Preise und Beträge (Server, P41-V.2) */}
        <OrderVerlauf orderId={order.id} open={open} />
      </div>
    </Modal>
```

- [ ] **Step 4: Prüfen.**

```bash
grep -c 'OrderVerlauf' frontend/src/components/domain/OrderDocumentsModal.tsx   # 2
cd frontend && ./node_modules/.bin/tsc --noEmit -p .
cd frontend && npm run build 2>&1 | tail -1
cd frontend && grep -l 'Verlauf wird geladen' dist/assets/*.js | wc -l   # 1
```

Erwartet: `2`, keine Ausgabe von `tsc`, `✓ built in …` (die Warnung „Some chunks are larger than 500 kB“ ist Altbestand), `1`.

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/services/bestellverlaufApi.ts frontend/src/components/domain/OrderVerlauf.tsx frontend/src/components/domain/OrderDocumentsModal.tsx
git commit -m "feat(verlauf): Verlauf im Belege-Dialog — wann, wer, was, Status, Grund (P41-V.4)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12 (V.5): Abschluss V — Vollauf, statische Prüfung, Meldung (ohne Commit)

- [ ] **Step 1:** Alle V-Tests: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41VVerlaufWer tests/test_paket4_1.py::TestP41VVerlaufRechte tests/test_paket4_1.py::TestP41VVerlaufAnzeige -q -p no:cacheprovider 2>&1 | tail -1` → `15 passed`.
- [ ] **Step 2:** **Prozedur V** (Kopf) → `14 failed, N passed, 2 skipped, 1 error`, Abgleich leer (im Gesamtplan `N = 2081`; V allein auf `1e2238b` `2045`).
- [ ] **Step 3:** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/sales.py app/schemas/order.py tests/test_paket4_1.py` → keine Ausgabe, Exit 0. `cd frontend && node tests/unit/bestellverlauf.check.ts && ./node_modules/.bin/tsc --noEmit -p .` → `bestellverlauf.check: 45 Fälle ok`, nichts weiter.
- [ ] **Step 4:** `git log --oneline -4` → die vier Betreffe `(P41-V.1)` … `(P41-V.4)` (sofern kein anderer Abschnitt dazwischen committet hat); `git diff --stat <Basis-V>..HEAD -- backend/app frontend/src frontend/tests backend/tests/test_paket4_1.py` nennt genau die 8 Dateien aus „File Structure (V)“ (plus Dateien anderer Abschnitte, falls sie dazwischen liefen); `git status --short` → nur die sauberen `??`-Einträge.
- [ ] **Step 5: Meldung** (Zwischenstand, **nicht anhalten**, weiter mit Task 13; kurz, mit Zeigern): Basis, die Rot/Grün-Zeilen je Task, Summenzeile der Prozedur V, Anker-Korrekturen nach Stoppregel 5, Hinweis zu `npx tsx` (verfügbar oder nicht).

---

## Abschnitt D (Fortsetzung) — Oberfläche und Abschluss D — Tasks 13–14 (D.5, D.6)

> Fortsetzung von Abschnitt D (Befund, Entscheidungen D-E1–D-E11, D-Stoppregeln und File Structure (D) stehen bei Tasks 4–7). D.5 ändert nur das Frontend und nutzt die vorhandenen Funktionen `datumKurz`/`heuteBerlin` aus `frontend/src/services/belegstatus.ts` (D-S4); D.6 prüft die D-Commits über `--grep` und ist deshalb unabhängig davon, dass V dazwischen committet hat.

### Task 13 (D.5): Oberfläche — „Erstellt am“ und Inventur-Stichtag nach dem Berliner Tag

**Files:**
- Modify: `frontend/src/pages/Sales.tsx` (Importe; Detaildialog „Erstellt am“)
- Modify: `frontend/src/pages/Inventur.tsx` (Importe; `useState` für `stichtag`)
- Create: `frontend/tests/unit/p41d-berlin.check.ts` (Node-Prüfung)

**Interfaces:**
- Produces: „Erstellt am“ zeigt `datumKurz(bestell_datum)`, also den Berliner Tag des naiven UTC-Zeitstempels, wie das „Datum:“ auf AB/LS/PL nach D.1. Die Inventur schlägt `heuteBerlin()` als Stichtag vor. Was der Nutzer im Feld wählt, geht unverändert als `count_date` an den Server (D-E11).
- Consumes: `datumKurz`, `heuteBerlin` aus `frontend/src/services/belegstatus.ts` (Paket 4 C, unverändert; D-S4).
- Node-Prüfungen laufen wie in Abschnitt Z mit `node tests/unit/<Name>.check.ts` (Node ≥ 23.6 führt TypeScript ohne Build aus). `tsx` steht nicht in `frontend/node_modules/.bin`; ohne Netz gäbe es `npx tsx` nur aus dem npx-Cache. Gemessen: `npx --no-install tsx tests/unit/p41d-berlin.check.ts` gibt dieselbe Ausgabe wie `node …`.

- [ ] **Step 1: Node-Prüfung anlegen** `frontend/tests/unit/p41d-berlin.check.ts` mit genau diesem Inhalt:

```ts
// Paket 4.1, Abschnitt D: Anzeige- und Vorgabetag im Browser = Berliner Tag,
// zu denselben Zeitpunkten wie backend/tests/test_paket4_1.py (TestP41D…).
// Lauf: node tests/unit/p41d-berlin.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { datumKurz, heuteBerlin } from '../../src/services/belegstatus.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

// „Erstellt am“ (Sales.tsx): bestell_datum kommt naiv in UTC vom Server
gleich(datumKurz('2026-10-09T22:30:00'), '10.10.2026', '00:30 Sommerzeit');
gleich(datumKurz('2026-10-09T21:30:00'), '09.10.2026', '23:30 Sommerzeit');
gleich(datumKurz('2026-12-31T23:30:00'), '01.01.2027', '00:30 am Neujahrstag, Winterzeit');
gleich(datumKurz('2025-03-01T00:00:00'), '01.03.2025', 'Altdaten-Import setzt 00:00');

// Stichtag-Vorgabe (Inventur.tsx)
gleich(heuteBerlin(new Date('2026-12-31T23:30:00Z')), '2027-01-01', '00:30 am Neujahrstag');
gleich(heuteBerlin(new Date('2026-12-31T22:30:00Z')), '2026-12-31', '23:30 an Silvester');
gleich(heuteBerlin(new Date('2026-10-09T22:30:00Z')), '2026-10-10', '00:30 Sommerzeit');

console.log(`p41d-berlin.check: ${faelle} Fälle ok`);
```

Lauf: `cd frontend && node tests/unit/p41d-berlin.check.ts` → `p41d-berlin.check: 7 Fälle ok`. Die Funktionen gibt es schon, die Prüfung ist sofort grün (Wächter für die Zeitpunkte der Backend-Tests). Rot ist hier der Zustand der Seiten, Step 2.

- [ ] **Step 2: Rot (Ausgangsstand der Seiten).**

```bash
(cd frontend && grep -c "datumKurz(selectedOrder.bestell_datum)" src/pages/Sales.tsx; grep -c "useState(() => heuteBerlin())" src/pages/Inventur.tsx; grep -c "new Date(selectedOrder.bestell_datum)" src/pages/Sales.tsx; grep -c "useState(new Date().toISOString()" src/pages/Inventur.tsx)
```

Erwartet (gemessen): `0`, `0`, `1`, `1`.

- [ ] **Step 3: Implementierung.**

`frontend/src/pages/Sales.tsx` — Importe: diesen Block

```tsx
import { invalidateOrderViews } from '../services/orderQueries';
```

ersetzen durch

```tsx
import { invalidateOrderViews } from '../services/orderQueries';
import { datumKurz } from '../services/belegstatus';
```

`frontend/src/pages/Sales.tsx` — im Detaildialog, Feld „Erstellt am“: diesen Block

```tsx
                  {new Date(selectedOrder.bestell_datum).toLocaleDateString('de-DE')}
```

ersetzen durch

```tsx
                  {/* naiver UTC-Zeitstempel → Berliner Tag wie Nummer und Beleg (Paket 4.1, D) */}
                  {datumKurz(selectedOrder.bestell_datum)}
```

`frontend/src/pages/Inventur.tsx` — Importe: diesen Block

```tsx
import { getErrorMessage } from '../services/errors';
```

ersetzen durch

```tsx
import { getErrorMessage } from '../services/errors';
import { heuteBerlin } from '../services/belegstatus';
```

`frontend/src/pages/Inventur.tsx` — Stichtag-Vorgabe: diesen Block

```tsx
  const [stichtag, setStichtag] = useState(new Date().toISOString().split('T')[0]);
```

ersetzen durch

```tsx
  // Berliner Tag, nicht der UTC-Tag des Browsers: zwischen 0 und 2 Uhr wäre es
  // sonst der Vortag, und die Inventurnummer trägt das Berliner Jahr (Paket 4.1, D)
  const [stichtag, setStichtag] = useState(() => heuteBerlin());
```

- [ ] **Step 4: Grün.**

```bash
(cd frontend && grep -c "datumKurz(selectedOrder.bestell_datum)" src/pages/Sales.tsx; grep -c "useState(() => heuteBerlin())" src/pages/Inventur.tsx; grep -c "new Date(selectedOrder.bestell_datum)" src/pages/Sales.tsx; grep -c "useState(new Date().toISOString()" src/pages/Inventur.tsx)
(cd frontend && ./node_modules/.bin/tsc --noEmit -p .; echo "tsc exit $?")
(cd frontend && npm run build 2>&1 | tail -1)
(cd frontend && node tests/unit/p41d-berlin.check.ts && node tests/unit/belegstatus.check.ts)
```

Erwartet: `1`, `1`, `0`, `0`; `tsc exit 0` ohne weitere Ausgabe; `✓ built in …`; `p41d-berlin.check: 7 Fälle ok`, `belegstatus.check: 29 Fälle ok`.

- [ ] **Step 5: Commit:**

```bash
git add frontend/src/pages/Sales.tsx frontend/src/pages/Inventur.tsx frontend/tests/unit/p41d-berlin.check.ts
git commit -m "fix(oberflaeche): Erstellt-am und Inventur-Stichtag nach dem Berliner Tag (P41-D.5)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

**Review Focus D.5:** Nur die beiden Stellen; `liefer_datum` (ein Tag) und die übrigen UTC-Vorgaben bleiben (D-E9, Offene Punkte 1). `belegstatus.ts` bleibt unverändert. `frontend/dist/` wird nicht eingecheckt.

---

### Task 14 (D.6): Abschluss D — Prüfungen und Meldung (ohne Commit)

- [ ] **Step 1:** Die D-Commits und ihre Dateien, unabhängig davon, ob V, Z oder R auf demselben Branch davor oder danach committen:

```bash
git log --reverse --format='%h %s' --name-only --grep='(P41-D\.' <Basis>..HEAD
```

Erwartet: fünf Commits `(P41-D.1)` bis `(P41-D.5)` in dieser Reihenfolge; die genannten Dateien sind genau die aus „File Structure (D)“ (D.1: vier, D.2: drei, D.3: drei, D.4: eine, D.5: drei).
- [ ] **Step 2:** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/lieferschein_service.py app/api/v1/documents.py app/services/pdf_service.py app/api/v1/sales.py app/services/shopify_service.py app/services/procurement_service.py app/services/inventory_service.py` → keine Ausgabe, Exit 0.
- [ ] **Step 3:** `git status --short` zeigt keine geänderte versionierte Datei. Erlaubt unversioniert: `frontend/node_modules`, `backend/data/`, `.claude-flow/`, `.swarm/`, `frontend/dist/`, die Plandatei.
- [ ] **Step 4: Meldung** (Zwischenstand, **nicht anhalten**, weiter mit Task 15): je Task Rot/Grün mit Zahlen, Prozedur-V-Summenzeilen mit leerem Abgleich, ruff, tsc, Build, beide Node-Prüfungen, Commit-Hashes, Abweichungen nach Stoppregel 5.

---

## Abschnitt Z — Reiterzähler auf der Rechnungsseite — Tasks 15–18 (Z.1–Z.4)

> **Rahmen:** Hinweis für Worker, Arbeitsort, Python, Node, Commits, Baseline, Prozedur V und Stoppregeln 1–5 stehen im Kopf (Global Constraints). Z läuft als letzter Abschnitt (Tasks 15–18), nach D.5.
>
> Für diesen Abschnitt gilt zusätzlich:
> - Neue Tests nur in `backend/tests/test_paket4_1.py`, mit den Präfixen **`TestP41Z…`** (Klassen), **`_p41z_…`** (Helfer) und **`_P41Z_…`** (Konstanten). Keine `autouse`-Fixture. Einzeltests nur über Klassen-IDs, nie `-k`.
> - **Kein Z-Task ändert bestehende Tests**, auch keine `frontend/tests/unit/*.check.ts`.
> - Kein Backend-Code, keine Migration, kein neuer Endpunkt.
> - **Nur auf zitierte Blöcke ankern, nie auf Zeilennummern.** Jeder Block „diesen Block … ersetzen durch“ kommt genau einmal vor. Nach jedem Patch mit `grep -n` prüfen, dass genau diese Stelle geändert ist.
> - Die Abschlussmeldung in Z.4 (Task 18) ist ein Zwischenstand — **nicht anhalten**, weiter mit Task 19. Abnahme Z und Offene Punkte Z stehen am Ende des Plans (Manager-Arbeit).
> - Node-Prüfungen laufen mit `node tests/unit/<Name>.check.ts` (Node ≥ 23.6 führt TypeScript ohne Build aus), wie im Vorbild und bei den vorhandenen Prüfungen. Das ist eine bewusste Abweichung vom Aufruf `npx tsx`: `tsx` steht nicht in `frontend/package.json` und nicht in `frontend/node_modules/.bin`. Ohne Netz käme es nur aus dem npx-Cache. Gemessen: `npx --no-install tsx` gibt dieselbe Ausgabe (Prüfstand).

**Ziel:**
- Jeder Reiter der Rechnungsliste („Alle | Offen | Überfällig | Bezahlt“) zeigt, wie viele Rechnungen er bei der aktuellen Suche anzeigt. Die Zahl kommt aus derselben Liste wie die Tabelle.
- Sind genau 100 Rechnungen geladen (die Grenze der Liste), steht „N+“.
- Nach Zahlung, Storno und Finalisieren stimmt auch „Überfällig“ sofort.

**Aufbau:**
- Zwei reine Funktionen kommen neu in `frontend/src/services/rechnungssuche.ts`: `rechnungenJeReiter` und `reiterZaehler`. Die Datei bleibt ohne Importe. Beide nutzen `rechnungPasstZurSuche` aus Paket 4 B.6.
- `Invoices.tsx` liest Tabelle und Zähler aus demselben Ergebnis. Die Zahl geht an `badge`, die Eigenschaft, die `Tabs.tsx` anzeigt.
- `Tabs.tsx` nimmt zusätzlich Text an: `badge?: number | string`.
- Die Abfrage „Überfällig“ läuft unter dem Schlüssel `['invoices', 'overdue']`. Damit lädt jeder vorhandene Aufruf `invalidateQueries({ queryKey: ['invoices'] })` sie mit neu.

### Befund (am Code auf `1e2238b` geprüft; Produktion siehe letzter Punkt)

- **Warum keine Zahl zu sehen ist:**
  - `Invoices.tsx` baut die Reiter in `Invoices()` mit `count: reiter.<id>.length` (Paket 4, B.6 / B-E5).
  - `frontend/src/components/ui/Tabs.tsx` kennt nur `badge?: number`. Sie rendert `<span className="ml-2 badge badge-sm badge-gray">{tab.badge}</span>`, und zwar nur bei `badge > 0`. Den Wert `count` übergibt die Seite also, aber die Reiterleiste liest ihn nie.
  - `tsc` meldet das nicht: `tabs` ist eine Variable und kein Objektliteral im Aufruf, deshalb prüft TypeScript keine überzähligen Eigenschaften.
  - Die Zähllogik selbst ist seit B.6 schon für Tabelle und Zähler dieselbe (`reiter` → `tabs`/`displayInvoices`). Sie war nur unsichtbar.
- **Wie Zähler im Projekt aussehen:**
  - Der einzige sichtbare Reiterzähler steht in `Orders.tsx` („Heute | Morgen | Kommende | Alle“): `badge: <Liste>.length`, eine graue Plakette, bei 0 ausgeblendet.
  - Denselben Fehler wie die Rechnungsseite (`count` statt `badge`, daher unsichtbar) haben `Inventory.tsx` (4 Reiter), `Products.tsx` (3), `Production.tsx` (5) und `Sales.tsx` (2). Siehe Offene Punkte 1.
  - `Tagesplan.tsx` nutzt keine `Tabs`, sondern eigene Abschnitte mit `<Badge>`.
- **Die Listen kommen aus zwei Abfragen:**
  - **„Alle“, „Offen“ und „Bezahlt“** filtern die Liste aus `useQuery(['invoices', { status, invoice_type }])` → `GET /invoices?page_size=100`.
    - Die Grenze ist `LISTENGRENZE = 100`. Das ist auch das Maximum im Backend (`PaginationParams.max_page_size`).
    - Die Liste ist nach Datum sortiert, neueste zuerst.
    - „Offen“ heißt `status === 'OFFEN'`, „Bezahlt“ heißt `status === 'BEZAHLT'`.
    - Die Auswahlfelder Status und Typ in der FilterBar wirken schon auf dem Server.
  - **„Überfällig“** ist `useQuery(['invoices-overdue'])` → `GET /invoices/overdue`.
    - Diese Liste ist ungekürzt und ignoriert die Auswahl von Status und Typ.
    - Sie kommt aus `check_overdue_invoices`: Status OFFEN, TEILBEZAHLT, UEBERFAELLIG oder MAHNVERFAHREN, Fälligkeit vor heute, keine Gutschrift, Leergut nur mit Saldo > 0, `mahnfaehig`.
    - Der Aufruf setzt OFFEN → UEBERFAELLIG und speichert das (`list_overdue_invoices` in `backend/app/api/v1/invoices.py` ruft `db.commit()`). **Schon das Öffnen der Rechnungsseite schreibt also**, auch ohne Z.
    - Täglich um 08:00 (Europe/Berlin) läuft der Job `overdue-invoices` je Mandant (`scheduler_service._safe_wrap` → `invoice_tasks.check_overdue_invoices`). Er stellt dieselben Rechnungen um, dazu auch überfällige TEILBEZAHLT. Nach 08:00 findet der Seitenaufruf deshalb in der Regel nichts mehr umzustellen.
  - **Gemessen:** `matchQuery({ queryKey: ['invoices'] }, …)` aus `@tanstack/query-core` 5.90.20 trifft `['invoices', 'overdue']` (`true`), aber **nicht** `['invoices-overdue']` (`false`).
    - `@tanstack/query-core` steht nicht in `frontend/package.json`. npm zieht es nur hoch, weil `@tanstack/react-query` 5.90.20 davon abhängt. `@tanstack/react-query` re-exportiert query-core (`__reExport(…, require("@tanstack/query-core"))` in `build/modern/index.cjs`). `require('@tanstack/react-query').partialMatchKey === require('@tanstack/query-core').partialMatchKey` ergibt `true`. Der Test in Z.3 bezieht `partialMatchKey` deshalb über `@tanstack/react-query`.
  - **Folge:** Alle Mutationen der Seite (Finalisieren, Verwerfen, Versand, Storno, Zahlung, lexoffice, Mahnung) und alle Dialoge (Monatsrechnungen, Leergut, SEPA, Belegdialog, Einstellungen) rufen nur `invalidateQueries({ queryKey: ['invoices'] })` auf. Nach einer Zahlung bleibt „Überfällig“ (Reiter **und** Karte) deshalb stehen, bis die Seite neu lädt (`staleTime` 60 s, `refetchOnWindowFocus: false` in `main.tsx`). Sobald Zähler sichtbar sind, fällt das auf.
- **Blättern und Grenze:**
  - Das Blättern (20 Zeilen je Seite) läuft im Browser über `displayInvoices`. Es verfälscht die Zahl nicht: Der Zähler ist die Länge der ganzen Reiterliste, also gleich `Pagination.totalItems`.
  - Die **Grenze von 100** verfälscht die Zahl dagegen. Kommen genau 100 zurück, fehlen womöglich ältere Rechnungen. Dann sind „Alle“, „Offen“ und „Bezahlt“ nur Untergrenzen.
  - Für diesen Fall zeigt der Seitenkopf schon „100+ Rechnungen“ und den Hinweis „Es werden die neuesten 100 Rechnungen angezeigt …“.
  - „Überfällig“ ist nie gekürzt.
- **Paket-3-Abnahme:** `test_gernot_261008_paket3.py::TestAbnahmeRechnungsberechtigung` rendert `Invoices()` mit einem Ersatz, der von `react` nur `useState` kennt.
  - Was in `Invoices()` vor `if (isError)` läuft, darf deshalb kein `useMemo` und kein `useEffect` nutzen.
  - Neue Importe aus `../services/…` lädt der Test echt, die müssen also funktionieren.
- **Produktion:** In diesem Lauf **nicht** nachgemessen.
  - Der Auto-Modus hat den lesenden SSH-Zugriff abgelehnt, und lokal liegt keine aktuelle Kopie von `minga.db`.
  - Stand laut Paket-4-Plan (Prod 09.10.: „Suche nur in den 100 neuesten Rechnungen … heute 10“): rund 10 Rechnungen, keine Entwürfe.
  - `minga` erreicht die Grenze von 100 heute also nicht. „N+“ ist Vorsorge.
  - Die echten Zahlen prüft der Manager in der Abnahme (Schritt A2).

### Entscheidungen (Manager, mit Begründung)

- **Z-E1 — Die Zahl geht an `badge`, die vorhandene Anzeige der Reiterleiste.**
  - `Tabs.tsx` bekommt keinen zweiten Weg für `count`. Der würde ungefragt Zähler auf vier weiteren Seiten einschalten (Offene Punkte 1).
  - Format wie bei den Bestellungen: graue Plakette, bei 0 keine Plakette.
  - Findet eine Suche in einem Reiter nichts, zeigt er also keine Zahl. „Heute“ ohne Bestellungen verhält sich genauso, und die Tabelle sagt dann „Keine Rechnungen gefunden“.
- **Z-E2 — Eine einzige Zähllogik.**
  - `rechnungenJeReiter(rechnungen, ueberfaellige, suche)` liefert die Liste je Reiter.
  - Die Tabelle zeigt `reiter[aktiv]`, der Zähler ist `reiter[id].length`.
  - Die Funktion steht in `rechnungssuche.ts` neben `rechnungPasstZurSuche` und ruft sie auf. Die Suche wird also wiederverwendet, nicht nachgebaut. Ohne Importe ist die Datei mit Node prüfbar.
  - Was die Reiter zeigen, bleibt **wie in Paket 4**: „Offen“ heißt nur `OFFEN`, „Überfällig“ ist die Liste des eigenen Endpunkts. Z macht die Zahlen nur sichtbar und ändert keine Bedeutung (Fragen dazu: Offene Punkte 2 und 3).
- **Z-E3 — An der Grenze „N+“, keine Zahlen vom Server.**
  - Gilt `invoices.length === LISTENGRENZE`, zeigen „Alle“, „Offen“ und „Bezahlt“ `N+`, z. B. `100+` oder `60+`.
  - „Überfällig“ zeigt immer die genaue Zahl. 0 bleibt ohne Plakette.
  - Begründung:
    - (a) Der Zähler soll zeigen, was der Reiter zeigt (B-E5). „Offen 130“ vom Server über einer Tabelle mit 60 Zeilen widerspräche dem.
    - (b) Die Suche läuft im Browser (B-E5, Paket-4-Offener-Punkt 4). Ohne Suche auf dem Server könnten Serverzahlen ihr nicht folgen, und es gäbe eine zweite Zähllogik.
    - (c) Gleiche Sprache wie der Seitenkopf („100+ Rechnungen“) und der vorhandene Hinweis.
    - (d) `minga` hat rund 10 Rechnungen, die Grenze ist Wochen entfernt. Zahlen vom Server kommen später zusammen mit Serversuche und echtem Blättern (Offene Punkte 5).
  - Dafür nimmt `Tabs.badge` auch Text an (`number | string`). Für Zahlen ändert sich nichts, die Bestellungen bleiben gleich.
- **Z-E4 — „Überfällig“ unter dem Schlüssel `['invoices', 'overdue']`.**
  - So greift jede vorhandene Invalidierung von `['invoices']`, ohne dass zehn Aufrufstellen angefasst werden.
  - Kein anderer Code nutzt `'invoices-overdue'` (grep: nur `Invoices.tsx`).
  - `['invoices', 'open']` (Dashboard) und `['invoices', { … }]` bleiben davon verschieden.
  - Folge: `GET /invoices/overdue` läuft nach jeder Rechnungsänderung einmal mehr. Er setzt höchstens OFFEN → UEBERFAELLIG, wie der Job um 08:00, bewirkt also nichts Neues.

### Rollen und Rechte

- Z ändert keine Rechte. Es gibt keinen neuen Endpunkt und kein neues Feld, und keine Rechteprüfung wird berührt.
- `invoices.router` hängt in `backend/app/main.py` an `dependencies=_deps_geld`, also `_rollen(SALES, BUCHHALTUNG)`. Admin ist immer dabei, Lesen und Schreiben sind gleich.
  - Das gilt für `GET /invoices` (Tabelle, „Alle“, „Offen“, „Bezahlt“) und für `GET /invoices/overdue` („Überfällig“, Karte). Die Zähler sehen also genau die Rollen, die die Rechnungstabelle sehen.
  - Planung und Halle bekommen 403 und sehen „Keine Berechtigung für Rechnungen“. Der Navigationspunkt „Rechnungen“ steht nur bei `ADMIN`, `SALES` und `ACCOUNTING` (`Layout.tsx`).
- Z.3 ändert nur den Cache-Schlüssel im Browser. `invalidateQueries` lädt standardmäßig nur aktive Abfragen neu. „Überfällig“ lädt also nur bei Nutzern neu, die die Rechnungsseite offen haben und sie ohnehin sehen dürfen.

### Dateien (Z)

| Datei | Task | Änderung |
|---|---|---|
| `backend/tests/test_paket4_1.py` | Z.1–Z.3 | Kopf nur, wenn die Datei fehlt. Blöcke ans Dateiende: `TestP41ZZaehlfunktion` (2 Tests), `TestP41ZRechnungsseite` (4), `TestP41ZUeberfaelligNeuLaden` (1) |
| `frontend/tests/unit/rechnungsreiter.check.ts` | Z.1 | **neu**, Node-Prüfung, 31 Fälle |
| `frontend/src/services/rechnungssuche.ts` | Z.1 | Anhang: `RechnungsReiter`, `ReiterRechnung`, `rechnungenJeReiter`, `reiterZaehler` |
| `frontend/src/components/ui/Tabs.tsx` | Z.2 | `badge?: number \| string`, Anzeige für Text |
| `frontend/src/pages/Invoices.tsx` | Z.2, Z.3 | Import; in `Invoices()` `reiter`, `tabs`, `displayInvoices`; Schlüssel der Abfrage „Überfällig“ |

### Prüfstand (gemessen in Kopien, Repo und Produktion unverändert)

- **Kopien:** jeweils `git archive 1e2238b`, `frontend/node_modules` als Symlink.
  - `/tmp/p41-kopie-z`: Entwicklung.
  - `/tmp/p41-kopie-z3`: **dieser Plantext** mechanisch nachgespielt mit `/tmp/p41-z-skripte/nachspiel.sh`. Die Schritte kommen aus `/tmp/p41-z-skripte/schritte/`, die Anker aus `/tmp/p41-z-skripte/anker/`. Jeder Anker wurde genau einmal gefunden; sonst bricht `ersetze.py` ab.
  - `/tmp/p41-kopie-zrev`: Review, alle Blöcke nachgespielt. Rot und Grün stimmen wörtlich.
  - `/tmp/p41-kopie-zfix2`: **Überarbeitung vom 10.10.** mit eigener Git-Historie. Der Basis-Commit `ebd1e6f` hat den Inhalt von `1e2238b`. Der Symlink kam erst danach, also steht `?? frontend/node_modules` wie im Worktree.
    - Alle 28 Codeblöcke dieses Textes wurden mit `/tmp/p41-zfix-skripte/nachspiel.sh` angewendet bzw. ausgeführt (Protokoll `nachspiel.log`). Jeder Anker kam genau einmal vor.
    - Gemessen wie in den Steps: Vorbereitung Z (`ebd1e6f`, nur `?? frontend/node_modules`), Rot und Grün je Step, drei Commits mit Co-Authored-By-Zeile, Z.4 Step 1, 3 und 5 (5 Dateien, 3 Commits). `git rev-parse --short <Z.1>^` gibt die Basis.
    - Z.3 mit `require('@tanstack/react-query')`: Rot `["invoices-overdue"]` / `false !== true`, Grün `1 passed`.
    - Gegenproben aus A0: Rückbau auf `count` → 3 failed, Rückbau des Schlüssels → 1 failed.
    - Prozedur V `14 failed, 2037 passed, 2 skipped, 1 error`, Abgleich leer. Build `✓ built`.
- **Prozedur V:**
  - Basis `1e2238b`: `14 failed, 2030 passed, 2 skipped, 1 error`, Abgleich leer (15 Baseline-Namen).
  - Nach Z.3: `14 failed, 2037 passed, 2 skipped, 1 error`, Abgleich leer.
  - Zuwachs +7 (Z.1 +2, Z.2 +4, Z.3 +1). Die Zwischenstände 2032 und 2036 sind errechnet.
- **Weitere Prüfungen:**
  - Rot und Grün je Step wie in den Steps angegeben, alle gemessen.
  - `tsc` nach Z.1, Z.2 und Z.3 ohne Ausgabe (4 s).
  - Build `✓ built in 31.78s` (in der ersten Kopie 1 min 28 s).
  - Paket-3-Abnahme `5 passed, 462 deselected`.
  - `ruff --select F821,F823 tests/test_paket4_1.py`: Exit 0.
  - Node-Prüfungen ok: `rechnungsreiter` 31, `rechnungssuche` 14, `positionsaenderung` 20, `belegstatus` 29, `dateiname` 8, `belegpfad` 35 Fälle.
  - `npx --no-install tsx tests/unit/rechnungsreiter.check.ts` gibt dieselbe Ausgabe (tsx 4.23.15 aus dem npx-Cache, ohne Netz). Der Plan nutzt `node`, wie das Vorbild und die vorhandenen Prüfungen.
- **Nicht gemessen:** Commits im echten Worktree (gemessen nur in `/tmp/p41-kopie-zfix2`), Browser und Produktion. Das deckt die Abnahme ab.

### Überschneidungen

- Z ändert nur das Frontend und hängt Tests an `test_paket4_1.py` an.
- In `Invoices.tsx` liegen alle Anker im oberen Teil von `Invoices()`: die Importzeile von `rechnungssuche`, `passtZurSuche`, `reiter`/`tabs`/`displayInvoices` und `queryKey: ['invoices-overdue']`. `InvoiceDetail` und die anderen Komponenten der Datei sind nicht betroffen.
- Ändert ein anderer Abschnitt von Paket 4.1 einen dieser Blöcke, gilt Stoppregel 1. Eine neue Importzeile daneben stört die Anker nicht.
- `Tabs.tsx`: Für Zahlen bleibt alles gleich (Bestellungen). Ein Abschnitt, der neue Reiter mit `badge` baut, ist nicht berührt. Nutzt er `count`, bliebe seine Zahl unsichtbar (Offene Punkte 1).

### Vorbereitung Z (vor Task 15)

- [ ] **Basis festhalten:**

```bash
git rev-parse --short HEAD && git status --porcelain
```

  - Die erste Zeile ist der Hash. Er geht als `<Basis-Z>` in die Abschlussmeldung (Z.4 Step 5 und 6). Im Gesamtplan ist das der Commit von Task 13 (D.5).
  - Danach stehen nur die sauberen `??`-Einträge aus Global Constraints (`frontend/node_modules`, `backend/data/`, ggf. `.claude-flow/`, `.swarm/`, die Plandatei). Bei einer Zeile mit `M`, `A` oder `D` stoppen und melden.
  - Wurde der Hash nicht notiert, gilt als `<Basis-Z>` der Elternteil des Z.1-Commits: `git rev-parse --short <Hash von Z.1>^`.

### Task 15 (Z.1): Zählfunktion der Reiter als reine Funktion mit Node-Prüfung

**Files:**
- Create (nur wenn sie fehlt) bzw. Modify: `backend/tests/test_paket4_1.py` (Kopf; Block ans Dateiende)
- Create: `frontend/tests/unit/rechnungsreiter.check.ts`
- Modify: `frontend/src/services/rechnungssuche.ts` (Anhang ans Dateiende)

**Interfaces:**
- Produces:
  - `type RechnungsReiter = 'all' | 'open' | 'overdue' | 'paid'`
  - `interface ReiterRechnung extends Suchbar { status: string }`
  - `rechnungenJeReiter<T extends ReiterRechnung>(rechnungen: T[], ueberfaellige: T[], suche: string): Record<RechnungsReiter, T[]>`
  - `reiterZaehler(anzahl: number, gekuerzt: boolean): number | string`. Gibt bei `gekuerzt && anzahl > 0` den Text `` `${anzahl}+` `` zurück, sonst `anzahl`.
- Consumes: `rechnungPasstZurSuche` und `Suchbar` (Paket 4 B.6, dieselbe Datei).

- [ ] **Step 1: Tests zuerst.** Nur wenn `backend/tests/test_paket4_1.py` fehlt, die Datei mit diesem Kopf anlegen. Besteht sie schon (im Gesamtplan seit Task 1), entfällt der Kopf; kein Stopp.

```python
"""Paket 4.1 — Restpunkte aus der Paket-4-Abnahme (10.10.2026).

Gemeinsame Testdatei aller Abschnitte. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP41V…/_p41v_ für Abschnitt V, TestP41Z…/_p41z_,
TestP41R…/_p41r_, TestP41D…/_p41d_): ein gleichnamiger Helfer würde still
ersetzt. Jeder Abschnitt bringt seine Importe selbst mit. Keine
autouse-Fixture.
"""
```

Dann diesen Block **ans Dateiende** von `backend/tests/test_paket4_1.py` anhängen:

```python


# ============================================================
# Abschnitt Z — Reiterzähler auf der Rechnungsseite
# Präfixe: Klassen TestP41Z…, Helfer _p41z_…, Konstanten _P41Z_…
# ============================================================


def _p41z_node(befehl):
    """Node im Ordner frontend (wie TestP4CBelegstatusAnzeige)."""
    import os
    import subprocess
    from pathlib import Path
    return subprocess.run(
        befehl,
        cwd=Path(__file__).resolve().parents[2] / "frontend",
        env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
    )


class TestP41ZZaehlfunktion:
    """Zählfunktion der Reiter (frontend/src/services/rechnungssuche.ts):
    die Node-Prüfungen laufen im Vollauf mit."""

    def test_reiter_und_zaehler(self):
        r = _p41z_node(["node", "tests/unit/rechnungsreiter.check.ts"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == "rechnungsreiter.check: 31 Fälle ok"

    def test_suche_unveraendert(self):
        r = _p41z_node(["node", "tests/unit/rechnungssuche.check.ts"])
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == "rechnungssuche.check: 14 Fälle ok"
```

Neue Datei `frontend/tests/unit/rechnungsreiter.check.ts`:

```ts
// Prüft rechnungenJeReiter und reiterZaehler ohne Browser und ohne
// Testframework (Paket 4.1, Z: Reiterzähler der Rechnungsliste).
// Lauf: node tests/unit/rechnungsreiter.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { rechnungenJeReiter, reiterZaehler } from '../../src/services/rechnungssuche.ts';

const r = (nr: number, status: string, kunde: string | null) => ({
  invoice_number: `RE-2026-${String(nr).padStart(5, '0')}`,
  status,
  customer_name: kunde,
  customer_number: `KD-${10000 + nr}`,
});
const oekoringOffen = r(1, 'OFFEN', 'Ökoring Handels GmbH');
const oekoringBezahlt = r(2, 'BEZAHLT', 'Ökoring Handels GmbH');
const kernEntwurf = r(3, 'ENTWURF', 'Großer Kern GmbH');
const kernTeilbezahlt = r(4, 'TEILBEZAHLT', 'Großer Kern GmbH');
const ohneKunde = r(5, 'STORNIERT', null);
const kernUeberfaellig = r(6, 'UEBERFAELLIG', 'Großer Kern GmbH');
const liste = [oekoringOffen, oekoringBezahlt, kernEntwurf, kernTeilbezahlt, ohneKunde, kernUeberfaellig];
// GET /invoices/overdue liefert UEBERFAELLIG und überfällige TEILBEZAHLT
const ueberfaellig = [kernUeberfaellig, kernTeilbezahlt];

let faelle = 0;
// Erwartet je Reiter die letzte Ziffer der Rechnungsnummern, in Listenreihenfolge
const pruefe = (suche: string, erwartet: Record<'all' | 'open' | 'overdue' | 'paid', string[]>) => {
  const reiter = rechnungenJeReiter(liste, ueberfaellig, suche);
  for (const id of ['all', 'open', 'overdue', 'paid'] as const) {
    assert.deepEqual(reiter[id].map((x) => x.invoice_number.slice(-1)), erwartet[id], `${id} / "${suche}"`);
    faelle += 1;
  }
};
pruefe('', { all: ['1', '2', '3', '4', '5', '6'], open: ['1'], overdue: ['6', '4'], paid: ['2'] });
pruefe('kern', { all: ['3', '4', '6'], open: [], overdue: ['6', '4'], paid: [] });
pruefe('ÖKORING', { all: ['1', '2'], open: ['1'], overdue: [], paid: ['2'] });
pruefe('kd-10004', { all: ['4'], open: [], overdue: ['4'], paid: [] });
pruefe('00005', { all: ['5'], open: [], overdue: [], paid: [] });
pruefe('kern 00001', { all: [], open: [], overdue: [], paid: [] });

// Die Tabelle zeigt dieselben Objekte, die der Zähler zählt
const ohneSuche = rechnungenJeReiter(liste, ueberfaellig, '');
assert.equal(ohneSuche.open[0], oekoringOffen);
faelle += 1;
assert.equal(ohneSuche.overdue[1], kernTeilbezahlt);
faelle += 1;

// Zähler: an der Listengrenze ist die Zahl eine Untergrenze
const zaehler: Array<[number, boolean, number | string]> = [
  [0, false, 0],
  [7, false, 7],
  [100, true, '100+'],
  [12, true, '12+'],
  [0, true, 0],
];
for (const [anzahl, gekuerzt, erwartet] of zaehler) {
  assert.equal(reiterZaehler(anzahl, gekuerzt), erwartet, `${anzahl} / ${gekuerzt}`);
  faelle += 1;
}
console.log(`rechnungsreiter.check: ${faelle} Fälle ok`);
```

- [ ] **Step 2: Rot.** `cd frontend && node tests/unit/rechnungsreiter.check.ts` → Exit 1 mit `SyntaxError: The requested module '../../src/services/rechnungssuche.ts' does not provide an export named 'rechnungenJeReiter'`.

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41ZZaehlfunktion -q -p no:cacheprovider 2>&1 | tail -1
```

→ `1 failed, 1 passed`. Rot ist `test_reiter_und_zaehler` mit demselben `SyntaxError`, grün ist `test_suche_unveraendert`.

- [ ] **Step 3: Implementierung.** Diesen Block **ans Dateiende** von `frontend/src/services/rechnungssuche.ts` anhängen. Die Datei endet mit `}` und einem Zeilenumbruch; die erste Zeile des Blocks ist leer.

```ts

/** Reiter der Rechnungsliste (Invoices.tsx). */
export type RechnungsReiter = 'all' | 'open' | 'overdue' | 'paid'

export interface ReiterRechnung extends Suchbar {
  status: string
}

/**
 * Was jeder Reiter bei der aktuellen Suche zeigt (Paket 4.1, Z).
 *
 * Eine Regel für Tabelle und Zähler: die Tabelle zeigt `reiter[aktiv]`,
 * der Zähler eines Reiters ist `reiter[id].length` — eine zweite
 * Zähllogik gibt es nicht. „Offen“ und „Bezahlt“ filtern die geladene
 * Liste nach Status, „Überfällig“ ist die Liste von GET /invoices/overdue
 * (UEBERFAELLIG und überfällige TEILBEZAHLT); in jedem Reiter wirkt die
 * Suche (Paket 4, B; G05).
 */
export function rechnungenJeReiter<T extends ReiterRechnung>(
  rechnungen: T[],
  ueberfaellige: T[],
  suche: string,
): Record<RechnungsReiter, T[]> {
  const passt = (rechnung: T) => rechnungPasstZurSuche(rechnung, suche);
  return {
    all: rechnungen.filter(passt),
    open: rechnungen.filter((r) => r.status === 'OFFEN' && passt(r)),
    overdue: ueberfaellige.filter(passt),
    paid: rechnungen.filter((r) => r.status === 'BEZAHLT' && passt(r)),
  };
}

/**
 * Zähler eines Reiters für die Reiterleiste (`badge` in Tabs.tsx).
 *
 * `gekuerzt`: Die geladene Liste hat die Listengrenze erreicht — ältere
 * Rechnungen fehlen womöglich, die Zahl ist eine Untergrenze („12+“), wie
 * „100+ Rechnungen“ im Seitenkopf. 0 bleibt 0; die Reiterleiste blendet
 * sie aus (wie bei den Bestellungen).
 */
export function reiterZaehler(anzahl: number, gekuerzt: boolean): number | string {
  return gekuerzt && anzahl > 0 ? `${anzahl}+` : anzahl;
}
```

- [ ] **Step 4: Grün.**
  - `cd frontend && node tests/unit/rechnungsreiter.check.ts && node tests/unit/rechnungssuche.check.ts` → `rechnungsreiter.check: 31 Fälle ok`, `rechnungssuche.check: 14 Fälle ok`.
  - Pytest-Befehl aus Step 2 → `2 passed`.
  - `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
  - `grep -c '^import' frontend/src/services/rechnungssuche.ts` → `0` (die Datei bleibt ohne Importe).
- [ ] **Commit:**

```bash
git add backend/tests/test_paket4_1.py frontend/tests/unit/rechnungsreiter.check.ts frontend/src/services/rechnungssuche.ts
git commit -m "feat(rechnung): eine Zählfunktion für Reiter und Tabelle der Rechnungsliste (P41-Z.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16 (Z.2): Reiter zeigen ihre Zahl — `badge` statt `count`, „N+“ an der Listengrenze

**Files:**
- Modify: `backend/tests/test_paket4_1.py` (Block ans Dateiende)
- Modify: `frontend/src/components/ui/Tabs.tsx` (`interface Tab`, Anzeige in `Tabs`)
- Modify: `frontend/src/pages/Invoices.tsx` (Importzeile; in `Invoices()` entfällt `passtZurSuche`, dazu `reiter`, `tabs`, `displayInvoices`)

**Interfaces:**
- Produces:
  - `Tab.badge?: number | string`. Text wird gezeigt, wenn er nicht leer ist. Eine Zahl wird ab 1 gezeigt.
  - Jeder Rechnungsreiter bekommt `badge = reiterZaehler(reiter.<id>.length, listeGekuerzt)`. Für `overdue` ist `gekuerzt` immer `false`.
- Consumes: `rechnungenJeReiter`, `reiterZaehler`, `RechnungsReiter` (Z.1); `LISTENGRENZE`.
- Verhalten:
  - Der Zähler ist gleich der Zahl der Zeilen im Reiter, über alle Seiten hinweg, also gleich `Pagination.totalItems`.
  - Er folgt der Suche und der Auswahl von Status und Typ. Ausnahme: „Überfällig“ folgt der Auswahl nicht.
  - Bei 100 geladenen Rechnungen steht z. B. „100+“, „60+“, „40+“.

**Review Focus (Z.2):**
- Kein `useMemo` und kein `useEffect` in `Invoices()` (sonst scheitert die Paket-3-Abnahme).
- Die Plaketten der Bestellungen bleiben unverändert.
- Leerer Text erscheint nicht als leere Plakette.

- [ ] **Step 1: Tests zuerst.** Diesen Block **ans Dateiende** von `backend/tests/test_paket4_1.py` anhängen:

```python


# Lädt eine .ts/.tsx-Datei des Frontends mit Ersatzmodulen (wie
# _abnahme_frontend in test_gernot_261008_paket3.py) und rendert die
# Rechnungsseite mit festen Listen. Bausteine (Tabs, Pagination, Input …)
# ersetzt ein Platzhalter: geprüft wird, was die Seite ihnen übergibt.
# Welche Abfrage welche Liste bekommt, entscheidet ihre queryFn
# (invoicesApi.list bzw. invoicesApi.getOverdue), nicht der Schlüssel.
_P41Z_BOOTSTRAP = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function laden(datei, ersatz = {}) {
    const code = ts.transpileModule(fs.readFileSync(datei, 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX }
    }).outputText;
    const exports = {};
    const ladenImport = (name) => {
        if (Object.hasOwn(ersatz, name)) return ersatz[name];
        if (name.startsWith('.')) {
            const basis = path.resolve(path.dirname(datei), name);
            const ziel = [basis + '.ts', basis + '.tsx', path.join(basis, 'index.ts')]
                .find(kandidat => fs.existsSync(kandidat));
            assert.ok(ziel, name);
            return laden(ziel, ersatz);
        }
        return require(name);
    };
    vm.runInNewContext(code, { exports, require: ladenImport }, { filename: datei });
    return exports;
}
function elemente(element) {
    if (!element || typeof element !== 'object') return [];
    if (Array.isArray(element)) return element.flatMap(elemente);
    return [element, ...elemente(element.props?.children)];
}
function rechnung(nr, status, kunde) {
    return {
        id: 'r' + nr, invoice_number: 'RE-2026-' + String(nr).padStart(5, '0'),
        invoice_type: 'RECHNUNG', status, customer_name: kunde,
        customer_number: 'KD-' + (10000 + nr), invoice_date: '2026-10-09',
        due_date: '2026-10-23', total: 10, paid_amount: 0,
    };
}
function seite(rechnungen, ueberfaellig, suche = '') {
    const platzhalter = new Map();
    const bausteine = new Proxy({}, {
        get: (_, name) => {
            if (name === 'useToast') return () => ({});
            if (!platzhalter.has(name)) platzhalter.set(name, function Platzhalter() { return null; });
            return platzhalter.get(name);
        },
    });
    const api = new Proxy({}, {
        get: (_, name) => name === 'invoicesApi'
            ? { list: () => 'liste', getOverdue: () => 'ueberfaellig' }
            : new Proxy({}, { get: () => () => null }),
    });
    let ueberfaelligSchluessel = null;
    let sucheGesetzt = false;
    const ersatz = {
        // Der erste useState('') in Invoices() ist das Suchfeld — unten am
        // Wert des Suchfelds nachgeprüft.
        react: { useState: (wert) => {
            if (wert === '' && !sucheGesetzt) { sucheGesetzt = true; return [suche, () => {}]; }
            return [wert, () => {}];
        } },
        '@tanstack/react-query': {
            useQueryClient: () => ({}), useMutation: () => ({}),
            useQuery: ({ queryKey, queryFn }) => {
                const art = queryFn ? queryFn() : null;
                if (art === 'liste') return { data: rechnungen };
                if (art === 'ueberfaellig') { ueberfaelligSchluessel = queryKey; return { data: ueberfaellig }; }
                return {};
            },
        },
        '../services/api': api,
        '../components/ui': bausteine,
        '../components/common/Layout': bausteine,
        '../components/ui/Skeleton': bausteine,
        '../components/domain/BelegVersand': bausteine,
        '../components/domain/MonatsrechnungenDialog': bausteine,
        '../components/domain/Leergut': bausteine,
        '../components/domain/SepaEinzugsliste': bausteine,
        '../context/AuthContext': { useAuth: () => ({ user: { roles: ['admin'] } }) },
    };
    const Invoices = laden('src/pages/Invoices.tsx', ersatz).default;
    const alle = elemente(Invoices());
    const suchfeld = alle.filter(e => e.props?.placeholder === 'Suchen nach Nummer oder Kunde...');
    assert.equal(suchfeld.length, 1);
    assert.equal(suchfeld[0].props.value, suche);
    const leiste = alle.filter(e => Array.isArray(e.props?.tabs));
    assert.equal(leiste.length, 1);
    const blaettern = alle.find(e => e.props?.totalItems !== undefined);
    return {
        zaehler: Object.fromEntries(leiste[0].props.tabs.map(t => [t.label, t.badge])),
        zeilen: alle.filter(e => e.type === 'tr' && e.key != null).length,
        gesamt: blaettern ? blaettern.props.totalItems : null,
        ueberfaelligSchluessel,
    };
}
// Gemischte Liste: 3 offen, 2 bezahlt, 1 Entwurf, 1 überfällig
const _gemischt = [
    rechnung(1, 'OFFEN', 'Ökoring Handels GmbH'),
    rechnung(2, 'OFFEN', 'Ökoring Handels GmbH'),
    rechnung(3, 'OFFEN', 'Großer Kern GmbH'),
    rechnung(4, 'BEZAHLT', 'Großer Kern GmbH'),
    rechnung(5, 'BEZAHLT', 'Dorint Hotel'),
    rechnung(6, 'ENTWURF', 'Dorint Hotel'),
    rechnung(7, 'UEBERFAELLIG', 'Großer Kern GmbH'),
];
const _ueberfaellig = [_gemischt[6]];
"""


def _p41z_frontend(skript):
    r = _p41z_node(["node", "-e", _P41Z_BOOTSTRAP + skript])
    assert r.returncode == 0, r.stdout + r.stderr


class TestP41ZRechnungsseite:
    """Die Reiter der Rechnungsseite zeigen ihre Zahl (Paket 4.1, Z): dieselbe
    Liste wie die Tabelle, mit Suche; an der Listengrenze „N+“."""

    def test_zaehler_ohne_suche(self):
        _p41z_frontend("""
const s = seite(_gemischt, _ueberfaellig);
assert.deepEqual(s.zaehler, { 'Alle': 7, 'Offen': 3, 'Überfällig': 1, 'Bezahlt': 2 });
assert.equal(s.zeilen, 7);
""")

    def test_zaehler_folgen_der_suche(self):
        _p41z_frontend("""
const s = seite(_gemischt, _ueberfaellig, 'kern');
assert.deepEqual(s.zaehler, { 'Alle': 3, 'Offen': 1, 'Überfällig': 1, 'Bezahlt': 1 });
assert.equal(s.zeilen, 3);
const keiner = seite(_gemischt, _ueberfaellig, 'gibt es nicht');
assert.deepEqual(keiner.zaehler, { 'Alle': 0, 'Offen': 0, 'Überfällig': 0, 'Bezahlt': 0 });
assert.equal(keiner.zeilen, 0);
""")

    def test_listengrenze_zeigt_untergrenze(self):
        _p41z_frontend("""
const hundert = Array.from({ length: 100 }, (_, i) => rechnung(i + 1, i < 60 ? 'OFFEN' : 'BEZAHLT', 'Kunde ' + i));
const s = seite(hundert, [rechnung(200, 'UEBERFAELLIG', 'Alt'), rechnung(201, 'TEILBEZAHLT', 'Alt')]);
assert.deepEqual(s.zaehler, { 'Alle': '100+', 'Offen': '60+', 'Überfällig': 2, 'Bezahlt': '40+' });
assert.equal(s.zeilen, 20);
assert.equal(s.gesamt, 100);
const neunundneunzig = seite(hundert.slice(1), []);
assert.deepEqual(neunundneunzig.zaehler, { 'Alle': 99, 'Offen': 59, 'Überfällig': 0, 'Bezahlt': 40 });
""")

    def test_reiterleiste_zeigt_zahl_und_text(self):
        _p41z_frontend("""
const { renderToStaticMarkup } = require('react-dom/server');
const { createElement } = require('react');
const { Tabs } = laden('src/components/ui/Tabs.tsx');
const html = renderToStaticMarkup(createElement(Tabs, { activeTab: 'all', tabs: [
    { id: 'all', label: 'Alle', badge: '100+' },
    { id: 'open', label: 'Offen', badge: 3 },
    { id: 'paid', label: 'Bezahlt', badge: 0 },
    { id: 'ohne', label: 'Ohne' },
] }));
const zahlen = [...html.matchAll(/<span class="ml-2 badge badge-sm badge-gray">([^<]*)<\\/span>/g)].map(m => m[1]);
assert.deepEqual(zahlen, ['100+', '3']);
""")
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41ZRechnungsseite -q -p no:cacheprovider 2>&1 | grep -E "^FAILED|^E +(actual|expected):|[0-9]+ (passed|failed)"
```

→ genau diese Zeilen (gemessen im Gesamt-Nachspiel; die Dauer ist die des Laufs):

```text
E       actual: {
E       expected: { Alle: 7, Offen: 3, 'Überfällig': 1, Bezahlt: 2 },
E       actual: {
E       expected: { Alle: 3, Offen: 1, 'Überfällig': 1, Bezahlt: 1 },
E       actual: {
E       expected: { Alle: '100+', Offen: '60+', 'Überfällig': 2, Bezahlt: '40+' },
E       actual: [ '3' ],
E       expected: [ '100+', '3' ],
FAILED tests/test_paket4_1.py::TestP41ZRechnungsseite::test_zaehler_ohne_suche
FAILED tests/test_paket4_1.py::TestP41ZRechnungsseite::test_zaehler_folgen_der_suche
FAILED tests/test_paket4_1.py::TestP41ZRechnungsseite::test_listengrenze_zeigt_untergrenze
FAILED tests/test_paket4_1.py::TestP41ZRechnungsseite::test_reiterleiste_zeigt_zahl_und_text
============================== 4 failed in 1.24s ===============================
```

Also `4 failed`. Ohne Filter gemessen:
- Die drei Seitentests scheitern mit `Expected values to be strictly deep-equal`. Ist-Wert jeweils `{ 'Überfällig': undefined, Alle: undefined, Bezahlt: undefined, Offen: undefined }`. Erwartet:
  - `test_zaehler_ohne_suche`: `{ Alle: 7, Offen: 3, 'Überfällig': 1, Bezahlt: 2 }`
  - `test_zaehler_folgen_der_suche`: `{ Alle: 3, Offen: 1, 'Überfällig': 1, Bezahlt: 1 }`
  - `test_listengrenze_zeigt_untergrenze`: `{ Alle: '100+', Offen: '60+', 'Überfällig': 2, Bezahlt: '40+' }`
- `test_reiterleiste_zeigt_zahl_und_text`: Ist `['3']`, erwartet `['100+', '3']`.
- Jeder andere Fehler ist Stoppregel 2, z. B. an `assert.equal(suchfeld.length, 1)` oder `leiste.length`.

- [ ] **Step 3: Reiterleiste.** `frontend/src/components/ui/Tabs.tsx`, in `interface Tab`: diesen Block

```tsx
  icon?: ReactNode;
  badge?: number;
}
```

ersetzen durch

```tsx
  icon?: ReactNode;
  // Zahl (ab 1 sichtbar) oder Text wie „100+“ (Rechnungsliste an der
  // Listengrenze, Paket 4.1 Z)
  badge?: number | string;
}
```

`frontend/src/components/ui/Tabs.tsx`, in `Tabs()`: diesen Block

```tsx
              {tab.badge !== undefined && tab.badge > 0 && (
```

ersetzen durch

```tsx
              {(typeof tab.badge === 'string' ? tab.badge !== '' : tab.badge !== undefined && tab.badge > 0) && (
```

- [ ] **Step 4: Rechnungsliste.** `frontend/src/pages/Invoices.tsx`, Importzeile: diesen Block

```tsx
import { rechnungPasstZurSuche } from '../services/rechnungssuche';
```

ersetzen durch

```tsx
import { rechnungenJeReiter, reiterZaehler, type RechnungsReiter } from '../services/rechnungssuche';
```

`frontend/src/pages/Invoices.tsx`, in `Invoices()` nach `stornoMutation`: diesen Block **löschen**, also die zwei Zeilen und die Leerzeile danach. Er wird durch nichts ersetzt.

```tsx
  // Suche „nach Nummer oder Kunde“ — in jedem Reiter (Paket 4, B; G05)
  const passtZurSuche = (invoice: Invoice) => rechnungPasstZurSuche(invoice, search);

```

`frontend/src/pages/Invoices.tsx`, in `Invoices()` nach `typeOptions`: diesen Block

```tsx
  // Je Reiter seine Liste, darauf die Suche. Die Zähler zeigen, was der
  // Reiter mit der aktuellen Suche zeigt (Paket 4, B; G05).
  const reiter: Record<string, Invoice[]> = {
    all: invoices.filter(passtZurSuche),
    open: invoices.filter((i) => i.status === 'OFFEN' && passtZurSuche(i)),
    overdue: overdueInvoices.filter(passtZurSuche),
    paid: invoices.filter((i) => i.status === 'BEZAHLT' && passtZurSuche(i)),
  };

  const tabs = [
    { id: 'all', label: 'Alle', count: reiter.all.length },
    { id: 'open', label: 'Offen', count: reiter.open.length },
    { id: 'overdue', label: 'Überfällig', count: reiter.overdue.length },
    { id: 'paid', label: 'Bezahlt', count: reiter.paid.length },
  ];

  const displayInvoices = reiter[activeTab] ?? reiter.all;
```

ersetzen durch

```tsx
  // Je Reiter seine Liste, darauf die Suche „nach Nummer oder Kunde“
  // (Paket 4, B; G05). Tabelle und Zähler lesen dieselben Listen; der
  // Zähler geht an `badge` — `count` kennt die Reiterleiste nicht
  // (Paket 4.1, Z).
  const reiter = rechnungenJeReiter(invoices, overdueInvoices, search);
  // Volle Liste: ältere Rechnungen fehlen womöglich, die Zahl ist eine
  // Untergrenze („60+“). „Überfällig“ kommt ungekürzt von /invoices/overdue.
  const listeGekuerzt = invoices.length === LISTENGRENZE;

  const tabs = [
    { id: 'all', label: 'Alle', badge: reiterZaehler(reiter.all.length, listeGekuerzt) },
    { id: 'open', label: 'Offen', badge: reiterZaehler(reiter.open.length, listeGekuerzt) },
    { id: 'overdue', label: 'Überfällig', badge: reiterZaehler(reiter.overdue.length, false) },
    { id: 'paid', label: 'Bezahlt', badge: reiterZaehler(reiter.paid.length, listeGekuerzt) },
  ];

  const displayInvoices = reiter[activeTab as RechnungsReiter] ?? reiter.all;
```

- [ ] **Step 5: Grün.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41ZRechnungsseite tests/test_paket4_1.py::TestP41ZZaehlfunktion -q -p no:cacheprovider 2>&1 | tail -1
```

→ `6 passed`. Dann:
- `grep -c 'passtZurSuche\|count: reiter' frontend/src/pages/Invoices.tsx` → `0`
- `grep -c 'badge: reiterZaehler' frontend/src/pages/Invoices.tsx` → `4`
- `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe
- Paket-3-Abnahme:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -q -p no:cacheprovider -k "TestAbnahmeSepaBerlin or TestAbnahmeRechnungsberechtigung" 2>&1 | tail -1
```

→ `5 passed, 462 deselected`. Bei anderem Ergebnis gilt Stoppregel 4.

- [ ] **Commit:**

```bash
git add backend/tests/test_paket4_1.py frontend/src/components/ui/Tabs.tsx frontend/src/pages/Invoices.tsx
git commit -m "fix(rechnung): Reiter der Rechnungsliste zeigen ihre Zahl, an der Listengrenze N+ (P41-Z.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 17 (Z.3): „Überfällig“ lädt mit den Rechnungen neu

**Files:**
- Modify: `backend/tests/test_paket4_1.py` (Block ans Dateiende)
- Modify: `frontend/src/pages/Invoices.tsx` (in `Invoices()`, Abfrage nach `// Fetch overdue`)

**Interfaces:**
- Produces: Query-Schlüssel `['invoices', 'overdue']` (vorher `['invoices-overdue']`).
- Consumes: alle vorhandenen `queryClient.invalidateQueries({ queryKey: ['invoices'] })`. Keiner dieser Aufrufe wird geändert.

- [ ] **Step 1: Test zuerst.** Diesen Block **ans Dateiende** von `backend/tests/test_paket4_1.py` anhängen:

```python


class TestP41ZUeberfaelligNeuLaden:
    """„Überfällig“ lädt mit jeder invalidateQueries({ queryKey: ['invoices'] })
    neu (Zahlung, Storno, Finalisieren, Versand …) — sonst bleiben Liste und
    Zähler bis zum Neuladen der Seite stehen (Paket 4.1, Z)."""

    def test_schluessel_unter_invoices(self):
        _p41z_frontend("""
// Über react-query: es re-exportiert query-core, das selbst nicht in
// frontend/package.json steht (nur transitiv installiert).
const { partialMatchKey } = require('@tanstack/react-query');
const s = seite(_gemischt, _ueberfaellig);
assert.ok(s.ueberfaelligSchluessel, 'keine Abfrage für Überfällig');
assert.equal(partialMatchKey(s.ueberfaelligSchluessel, ['invoices']), true, JSON.stringify(s.ueberfaelligSchluessel));
assert.equal(s.zaehler['Überfällig'], 1);
""")
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41ZUeberfaelligNeuLaden -q -p no:cacheprovider 2>&1 | tail -1
```

→ `1 failed`, Meldung `AssertionError [ERR_ASSERTION]: ["invoices-overdue"]` mit `false !== true`.

- [ ] **Step 3: Implementierung.** `frontend/src/pages/Invoices.tsx`, in `Invoices()`, Abfrage nach dem Kommentar `// Fetch overdue`: diesen Block

```tsx
    queryKey: ['invoices-overdue'],
```

ersetzen durch

```tsx
    // Unter 'invoices': jede invalidateQueries({ queryKey: ['invoices'] })
    // (Zahlung, Storno, Finalisieren, Versand …) lädt auch „Überfällig“
    // neu — sonst blieben Liste und Zähler bis zum Neuladen stehen
    // (Paket 4.1, Z).
    queryKey: ['invoices', 'overdue'],
```

- [ ] **Step 4: Grün.**
  - Befehl aus Step 2 → `1 passed`.
  - `grep -rc "invoices-overdue" frontend/src | grep -v ':0$'` → keine Ausgabe.
  - `tsc` → keine Ausgabe.
- [ ] **Commit:**

```bash
git add backend/tests/test_paket4_1.py frontend/src/pages/Invoices.tsx
git commit -m "fix(rechnung): Überfällig-Liste und -Zähler laden nach Zahlung, Storno und Finalisieren neu (P41-Z.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 18 (Z.4): Abschluss Z — Prüfungen, Vollauf, Build, Meldung (ohne Commit)

**Files:** keine Änderung.

- [ ] **Step 1: Alle Z-Klassen.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4_1.py::TestP41ZZaehlfunktion tests/test_paket4_1.py::TestP41ZRechnungsseite tests/test_paket4_1.py::TestP41ZUeberfaelligNeuLaden -q -p no:cacheprovider 2>&1 | tail -1
```

→ `7 passed`. Dann die Node-Prüfungen:

```bash
cd frontend && for c in rechnungsreiter rechnungssuche positionsaenderung belegstatus dateiname belegpfad; do node tests/unit/$c.check.ts | tail -1; done
```

→ 31, 14, 20, 29, 8 und 35 Fälle ok.

- [ ] **Step 2: Prozedur V** → `14 failed, N passed, 2 skipped, 1 error`, Abgleich leer.
  - N = Stand vor Z.1 + 7 (im Gesamtplan 2081 → 2088; Z allein auf `1e2238b` 2030 → 2037).
  - Laufen andere Abschnitte vorher, verschiebt sich die Basis. Maßgeblich sind die Namen.
- [ ] **Step 3: Statisch.** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 tests/test_paket4_1.py` → keine Ausgabe, Exit 0.
- [ ] **Step 4: Frontend.** `tsc` ohne Ausgabe; `cd frontend && npm run build 2>&1 | tail -1` → `✓ built in …`.
- [ ] **Step 5: Diff.** `<Basis-Z>` ist der Hash aus „Vorbereitung Z“.
  - `git diff --stat <Basis-Z>..HEAD` → genau diese 5 Dateien: `backend/tests/test_paket4_1.py`, `frontend/src/components/ui/Tabs.tsx`, `frontend/src/pages/Invoices.tsx`, `frontend/src/services/rechnungssuche.ts`, `frontend/tests/unit/rechnungsreiter.check.ts`.
  - `git log --oneline <Basis-Z>..HEAD` → drei Commits (Z.1–Z.3).
- [ ] **Step 6: Abschlussmeldung**, kurz und mit Zeigern:
  - `<Basis-Z>` und die drei Commit-Hashes
  - Rot/Grün je Task, erwartet gegen gemessen
  - Summenzeile der Prozedur V
  - Ergebnisse von `ruff`, `tsc`, Build, Node-Prüfungen und Paket-3-Abnahme
  - jeden selbst behobenen Ankerfehler mit Datei und Funktion
  - Browser und Produktion übernimmt der Manager.

---

## Abschluss

### Task 19: Abschluss Paket 4.1 — Gesamtprüfung und Gesamtmeldung

**Files:** keine Änderung.

- [ ] **Step 1: Alle Paket-4.1-Tests** (Befehl „Alle Paket-4.1-Tests“ aus Global Constraints) → `58 passed` (18 R + 18 D + 15 V + 7 Z).
- [ ] **Step 2: Bestands- und Abnahmetests.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py tests/test_gernot_261008_paket3.py tests/test_nachtrag_0910.py -q -p no:cacheprovider 2>&1 | tail -1
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py::TestAbnahmeSepaBerlin tests/test_gernot_261008_paket3.py::TestAbnahmeRechnungsberechtigung -q -p no:cacheprovider 2>&1 | tail -1
```

  Erwartet: `853 passed` (Paket 4, Paket 3 und Nachtrag 09.10. unverändert, Zahl wie auf der Basis); `5 passed` (Stoppregel 4).
- [ ] **Step 3: Node-Prüfungen.**

```bash
cd frontend && for c in bestellverlauf p41d-berlin rechnungsreiter rechnungssuche positionsaenderung belegstatus rollen dateiname belegpfad; do node tests/unit/$c.check.ts | tail -1; done
```

  Erwartet der Reihe nach: `bestellverlauf.check: 45 Fälle ok`, `p41d-berlin.check: 7 Fälle ok`, `rechnungsreiter.check: 31 Fälle ok`, `rechnungssuche.check: 14 Fälle ok`, `positionsaenderung.check: 20 Fälle ok`, `belegstatus.check: 29 Fälle ok`, `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`, `dateiname.check: 8 Fälle ok`, `belegpfad.check: 35 Fälle ok`.
- [ ] **Step 4: Prozedur V** — gilt der Lauf aus Task 18 Step 2, wenn seitdem nichts geändert wurde (`git status --porcelain` nur die sauberen `??`-Einträge); sonst neu → `14 failed, N passed, 2 skipped, 1 error` (auf `1e2238b` N = 2088), Abgleich leer.
- [ ] **Step 5: Statisch über alle geänderten Python-Dateien** (aus dem Wurzelverzeichnis, 10 Dateien):

```bash
git diff --name-only <Basis>..HEAD -- '*.py' | wc -l
git diff --name-only <Basis>..HEAD -- '*.py' | xargs /opt/homebrew/bin/ruff check --select F821,F823; echo "ruff exit $?"
```

  Erwartet: `10`, dann nur `ruff exit 0`.
- [ ] **Step 6: Frontend** — `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` ohne Ausgabe, `cd frontend && npm run build 2>&1 | tail -1` → `✓ built in …`.
- [ ] **Step 7: Diff und Commits.**

```bash
git diff --stat <Basis>..HEAD | tail -1
git diff --name-only <Basis>..HEAD
git log --reverse --format=%s <Basis>..HEAD
git log --format=%B <Basis>..HEAD | grep -c 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>'
git status --porcelain
```

  Erwartet: `22 files changed, …`; genau die 22 Dateien aus „File Structure“; 14 Betreffe in der Reihenfolge P41-R.1, R.2, D.1, D.2, D.3, D.4, V.1, V.2, V.3, V.4, D.5, Z.1, Z.2, Z.3; `14`; nur die sauberen `??`-Einträge.
- [ ] **Step 8: Gesamtmeldung** (kurz, mit Zeigern; die Abschlussmeldungen R, D, V, Z gehen darin auf): `<Basis>`, `<Basis-V>`, `<Basis-Z>`; Commit-Hash je Task; Rot/Grün je Task (erwartet vs. gemessen); Summenzeilen der Prozedur V; Ergebnisse von Step 1–7; jede selbst behobene Anker- oder Redaktionsabweichung mit Datei und Funktion; Hinweis zu `npx tsx` (verfügbar oder nicht). Browser-Prüfungen und Produktionsschritte macht der Manager.

---

## Abnahme (Manager, im Arbeitsbaum nachmessen — nicht dem Bericht glauben)

- **Gesamt:** Task 19 Steps 1–7 selbst ausführen: `tests/test_paket4_1.py` `58 passed`; Bestand `853 passed`, Paket-3-Abnahme `5 passed`; Prozedur V `14 failed, N passed, 2 skipped, 1 error`, Abgleich leer; `ruff` F821/F823 über die 10 Python-Dateien ohne Befund; neun Node-Prüfungen wie in Task 19 Step 3; `tsc` ohne Ausgabe, Build `✓ built`; Diff genau die 22 Dateien aus „File Structure“, 14 Commits mit `Co-Authored-By`-Zeile.
- **R** (Diff `<Basis>..<Commit von Task 2>`): R-Klassen `18 passed` (Task 3); genau `backend/app/services/invoice_service.py` und `backend/tests/test_paket4_1.py`; 2 Commits.
- **D** (über `--grep='(P41-D\.'`, Task 14 Step 1): D-Klassen `18 passed` (Task 7 Step 3); 5 Commits mit genau den Dateien aus „File Structure (D)“; A-D1.
- **V** (Diff `<Basis-V>..<Commit von Task 11>`): V-Klassen `15 passed`; genau die 8 Dateien aus „File Structure (V)“; 4 Commits.
- **Z** (Diff `<Basis-Z>..HEAD`): Z-Klassen `7 passed`; genau die 5 Dateien aus „Dateien (Z)“; 3 Commits; Gegenproben A0.

## Manager-Abnahme (kein Worker-Task; jede Schreibaktion mit Freigabe)

Zugriff wie immer: `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103`, `C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)` (der Containername wechselt je Deploy), Skripte per `docker exec -i "$C" python3 - < skript.py`; lesend immer `mode=ro`, nur `SELECT`/`pragma`, keine personenbezogenen Rohdaten in Plan oder Bericht; Backups WAL-sicher (Memory `novaerp-ssh-wal-backup`). Festgeschriebene Rechnungen und vergebene Belegnummern werden nie geändert (GoBD). Paket 4.1 schreibt keine Daten und braucht kein Runbook.

**Ablauf rund um den gemeinsamen Deploy** (Einzelheiten in den Unterabschnitten R, D, V, Z):
0. **Vor dem Dispatch:**
   - **Nachspiel des Gesamtplans**, nur nötig, wenn `main` seit `1e2238b` vorgerückt ist (auf `1e2238b` ist der Endstand gemessen, Prüfstand (Gesamtlauf)): frische Kopie (`git archive main | tar -x -C /tmp/p41-kopie-<kürzel>`, eigener Git-Verlauf, `frontend/node_modules` als Symlink), dann `python3 -I /tmp/p41/merge/nachspiel.py /tmp/p41/plan.md <Kopie>` und das Protokoll gegen die Erwartungen der Steps lesen.
   - **Worktree anlegen** (Global Constraints) und Codex mit `.git` in `writable_roots` und `mcp_servers={}` starten.
1. **Lokal, vor dem Deploy:** „Abnahme“ oben; A-D1 und A-D2 (Uhr-Probe, Gegenprobe mit `main`); Abnahme V Schritt 0 und 2 (Prod-Kopie im Browser, auch `DEV_ROLES=production_staff`); Abnahme Z A0–A4 (Prod-Kopie, Gegenproben); R-A2 (Browser, Monatsrechnungen mit 1,005 €).
2. **Produktion lesend, vor dem Deploy:**
   - **R-W, R-A0** — **Gate:** Nennt Zeile 7 eine Rechnung mit Status ≠ `ENTWURF`, deren PDFs vorher archivieren (`/root/backups/minga-p41r-belege-*`) und dem Nutzer vorlegen; erwartet nach Stand 09.10. `0 []`. Danach **R-A1** (PDF-Vergleich `main` gegen Branch auf der Prod-Kopie: nur die Rechnungen aus Zeile 7 verschieden).
   - **R-D1** — **Gate:** „order_date im Fenster … davon mit AB / mit LS“ erwartet `0`/`0`; sonst entscheidet der Manager vor dem Deploy, ob der Nachdruck dieser Belege ein anderes „Datum:“ zeigen darf.
   - **V-W, Abnahme V Schritt 1** (Aktionen, Schlüssel, Systemnamen, Zeitformat; eine unbekannte Aktion oder ein unbekannter Systemname → Fix-Runde an denselben Worker, Zählung der Node-Prüfung +1).
   - **Abnahme Z A1** (Zahlen auf der Prod-Kopie, erst nach dem ersten Öffnen der Rechnungsseite zählen).
3. **Deploy** einmal für R, D, V und Z (Backups `*-vor-deploy-<hash>-*.db` für minga, demo, demo.seed). Kein Datenschritt.
4. **Live:** `/health` 200, Startlog ohne Fehler; R-A3 (R-A0 erneut, Zeilen 1–6 unverändert); Abnahme V Schritt 3 (Verlauf in Gernots Arbeitsbereich ansehen); Abnahme Z A5 (Rechnungsseite **erst nach 08:00** öffnen, nichts klicken, was schreibt); R-D1 an den Tagen danach („davon = UTC-Tag“ bleibt `0`).
5. **Gernot informieren** in einer Nachricht: Verlauf im Belege-Dialog, Zähler auf der Rechnungsseite, Anlage der Sammelrechnung cent-genau, Belegnummern nach deutscher Zeit (Text „Nachricht an Gernot“ unter D, nur wenn das R-D1-Gate `0` ergab); dazu die gebündelten Fragen unter „Offene Punkte“.
6. **Später:** R-A2 (3)/Ü2 am 01.11.2026 nach 06:30 (erster Monatslauf mit Anlage, lesend: Anlage = Zwischensumme).

### R — Cent-Rundung: Abnahme R (kein Worker-Task; jede Schreibaktion nur mit Freigabe)

- **R-W — Werkzeuge anlegen (einmal vor R-A0).** Beide Skripte stehen nur hier im Plan, nicht im Repo; `/tmp` wird von macOS aufgeräumt. Die drei Blöcke unverändert, ohne Einrückung, in die Shell geben; ältere Stände unter `/tmp/p41-skripte/` werden überschrieben. `prod_r0.py`: nur `SELECT`, `mode=ro`, gibt nur Zahlen und RE-Nummern aus (keine personenbezogenen Daten), nur ASCII (läuft per `ssh … python3 -` im Container), DB-Pfad als optionales Argument (ohne: `/data/tenants/minga.db`). `pdf_vergleich.py`: öffnet eine DB-Kopie read-only, rendert jede Rechnung mit Lieferscheinen und gibt je Rechnung Anlagensumme, Positionssumme und PDF-Hash aus.

```bash
mkdir -p /tmp/p41-skripte && cat > /tmp/p41-skripte/prod_r0.py <<'P41R_EOF'
# R-A0 (Paket 4.1, R): nur lesend (mode=ro), nur SELECT, gibt nur Zahlen und RE-Nummern aus.
# Aufruf: python3 - [<db>] < prod_r0.py   (ohne <db>: /data/tenants/minga.db)
import math
import sqlite3
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

DB = sys.argv[1] if len(sys.argv) > 1 else "/data/tenants/minga.db"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
q = lambda s, *a: c.execute(s, a).fetchall()
D = lambda v: Decimal(str(v)) if v is not None else Decimal("0")
cent = lambda b: b.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
betrag = lambda m, p, d: D(m) * D(p) * (1 - D(d) / 100)
nicht_cent = lambda b: b != cent(b)


def neu(anteile, rang):
    # wie invoice_service.auf_cent_verteilen (Paket 4.1, R.1)
    in_cent = {k: Fraction(v) * 100 for k, v in anteile.items()}
    ct = {k: math.floor(v) for k, v in in_cent.items()}
    fehlend = round(sum(in_cent.values(), Fraction(0))) - sum(ct.values())
    for k in sorted(in_cent, key=lambda k: (ct[k] - in_cent[k], rang[k]))[:fehlend]:
        ct[k] += 1
    return {k: Decimal(v) / 100 for k, v in ct.items()}


print("1 Rechnungen (typ, status, ohne order_id):", q("select invoice_type, status, order_id is null, count(*) from invoices group by 1,2,3"))
print("2 LS an Rechnungen gesamt / an Rechnungen ohne order_id:",
      q("select count(*) from delivery_notes where invoice_id is not null")[0][0],
      q("select count(*) from delivery_notes d join invoices i on i.id=d.invoice_id where i.order_id is null")[0][0])
print("3 invoice_line_sources:", q("select count(*) from invoice_line_sources")[0][0])
print("4 Rechnungen mit Kopfrabatt > 0:", q("select count(*) from invoices where discount_percent > 0")[0][0],
      "| Kunden mit Rabatt > 0 je invoice_mode:", q("select invoice_mode, count(*) from customers where discount_percent > 0 group by 1"))
for tab in ("invoice_lines", "order_lines"):
    rows = q(f"select quantity, unit_price, discount_percent from {tab}")
    print(f"5 {tab}: {len(rows)} | Preis mit mehr als 2 NK: {sum(1 for m, p, d in rows if nicht_cent(D(p)))}"
          f" | Positionsrabatt > 0: {sum(1 for m, p, d in rows if D(d) > 0)}"
          f" | Menge nicht ganzzahlig: {sum(1 for m, p, d in rows if D(m) != D(m).to_integral_value())}"
          f" | Menge x Preis x (1 - Rabatt) nicht in ganzen Cent: {sum(1 for m, p, d in rows if nicht_cent(betrag(m, p, d)))}")
quellen5 = q("select s.quantity, l.unit_price, l.discount_percent from invoice_line_sources s"
             " join invoice_lines l on l.id = s.invoice_line_id")
print(f"5 invoice_line_sources: {len(quellen5)} | Betrag der Quelle nicht in ganzen Cent:"
      f" {sum(1 for m, p, d in quellen5 if nicht_cent(betrag(m, p, d)))}")
print("6 Positionen mit Quellen, Menge != Summe der Quellen:", q(
    "select count(*) from invoice_lines l where exists(select 1 from invoice_line_sources s where s.invoice_line_id=l.id)"
    " and abs(l.quantity - (select sum(quantity) from invoice_line_sources s where s.invoice_line_id=l.id)) > 0.0005")[0][0])
geaendert = []
n = 0
for inv_id, nr, status, oid in q("select distinct i.id, i.invoice_number, i.status, i.order_id from invoices i join delivery_notes d on d.invoice_id = i.id"):
    n += 1
    notes = q("select id, delivery_note_number, order_id from delivery_notes where invoice_id = ?", inv_id)
    src = q("select s.invoice_line_id, s.delivery_note_id, d.delivery_note_number, s.quantity, l.unit_price, l.discount_percent, l.line_total"
            " from invoice_line_sources s join invoice_lines l on l.id = s.invoice_line_id"
            " join delivery_notes d on d.id = s.delivery_note_id where l.invoice_id = ?", inv_id)
    alt = defaultdict(Decimal)
    anteile = defaultdict(Fraction)
    rang = {}
    je_pos = defaultdict(list)
    for lid, nid, num, m, p, dsc, lt in src:
        alt[nid] += betrag(m, p, dsc)
        je_pos[lid].append((nid, m, lt))
        rang[nid] = (num or "", nid)
    for lid, teile in je_pos.items():
        g = sum((Fraction(D(m)) for _, m, _ in teile), Fraction(0))
        for nid, m, lt in teile:
            anteile[nid] += Fraction(D(lt)) * (Fraction(D(m)) / g if g else Fraction(1, len(teile)))
    for nid, num, ooid in notes:
        rang.setdefault(nid, (num or "", nid))
        if nid in alt or ooid is None:
            continue
        ol = {r[0] for r in q("select id from order_lines where order_id = ?", ooid)}
        s = sum((D(lt) for lt, oi in q("select line_total, order_item_id from invoice_lines where invoice_id = ?", inv_id) if oi in ol), Decimal("0"))
        alt[nid] += s
        anteile[nid] += Fraction(s)
    neu_b = neu(anteile, rang)
    if any(cent(alt[nid]) != neu_b.get(nid, Decimal("0")) for nid, _, _ in notes):
        geaendert.append((nr, status))
print("7 Rechnungen mit Lieferscheinen:", n, "| Anlage aendert sich durch R:", len(geaendert), geaendert)
P41R_EOF
```

```bash
cat > /tmp/p41-skripte/pdf_vergleich.py <<'P41R_EOF'
"""R-A1 (Paket 4.1, R): Rechnungs-PDFs aller Rechnungen mit Lieferscheinen aus
einer DB-KOPIE rendern und je Rechnung Hash und Anlage ausgeben. Schreibt
nichts in die DB (Sitzung wird zurückgerollt, Datei read-only geöffnet).

Aufruf (je Codestand einmal, aus einem beliebigen Verzeichnis):
  REDIS_URL=memory:// <venv-python> -I pdf_vergleich.py <backend-dir> <db-kopie> > <ausgabe>
"""
import hashlib
import sys

sys.path.insert(0, sys.argv[1])
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.main  # noqa: E402,F401  — alle Modelle registrieren
from app.models.documents import DeliveryNote  # noqa: E402
from app.models.invoice import Invoice  # noqa: E402
from app.services.invoice_service import netto_je_lieferschein  # noqa: E402
from app.services.pdf_service import PDFService, load_company_settings  # noqa: E402

engine = create_engine(f"sqlite:///file:{sys.argv[2]}?mode=ro&uri=true")
with Session(engine) as db:
    ids = db.execute(select(DeliveryNote.invoice_id).where(DeliveryNote.invoice_id.is_not(None)).distinct()).scalars().all()
    for invoice in sorted((db.get(Invoice, i) for i in ids), key=lambda r: r.invoice_number):
        notes = db.execute(select(DeliveryNote).where(DeliveryNote.invoice_id == invoice.id)).scalars().all()
        anlage = netto_je_lieferschein(db, invoice, notes)
        pdf = PDFService.generate_invoice_pdf(invoice, settings=load_company_settings(db), db=db)
        zeilen = sum(l.line_total for l in invoice.lines)
        print(invoice.invoice_number, invoice.status.value, "order" if invoice.order_id else "sammel",
              "anlage", sum(anlage.values()), "positionen", zeilen, "pdf", hashlib.sha256(pdf).hexdigest()[:16])
    db.rollback()
P41R_EOF
```

```bash
shasum -a 256 /tmp/p41-skripte/prod_r0.py /tmp/p41-skripte/pdf_vergleich.py | cut -c1-16
python3 -I -c 'import ast, sys; [ast.parse(open(p, encoding="utf-8").read()) for p in sys.argv[1:]]; print("ok")' /tmp/p41-skripte/prod_r0.py /tmp/p41-skripte/pdf_vergleich.py
```

  Erwartet: `17f9b26a23e367a5` und `47ac5e2196b7c331` (Kopierfehler sonst), dann `ok`.
- **R-A0 — Produktion vor dem Deploy, nur lesend.** Skript `/tmp/p41-skripte/prod_r0.py` aus R-W (lokal gegen zwei Probe-DBs geprüft):

```bash
ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103 'C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1); docker exec -i "$C" python3 -' < /tmp/p41-skripte/prod_r0.py
```

  Ausgabe 1–7: Rechnungen je Typ/Status, Lieferscheine an Rechnungen (gesamt / ohne Bestellbezug), Quellen, Gesamtrabatte; **Zeile 5** je Tabelle (`invoice_lines`, `order_lines`) Preise mit mehr als 2 Nachkommastellen, Positionsrabatte, nicht ganzzahlige Mengen und Zeilen, deren Menge × Preis × (1 − Rabatt) kein ganzer Centbetrag ist, dazu als eigene Zeile 5 die Quellen (`invoice_line_sources`) mit solchem Betrag — nur Rechnungen mit solchen Quellen können sich durch R ändern (bei Zeile 6 = 0); die Positionszeile allein unterschätzt (2 × 1,005 = 2,01 ist ein ganzer Centbetrag, je Lieferschein 1,005 nicht). Zeile 6: Positionen mit Menge ≠ Summe der Quellen. **Zeile 7: Rechnungen, deren Anlage sich durch R ändert** (Rechenweg alt gegen neu, unabhängig von Zeile 5). Erwartet nach Stand 09.10.: Zeile 2 zweiter Wert `0`, Zeile 7 `0 []`. **Stopp vor dem Deploy**, wenn Zeile 7 eine Rechnung mit Status ≠ `ENTWURF` nennt: deren PDFs vorher archivieren (`/root/backups/minga-p41r-belege-*`, wie A-R1) und dem Nutzer vorlegen. Zeile 6 > 0: diese Positionen verteilen ihren Betrag künftig mengenanteilig (R-E4) — dem Nutzer melden. Lokale Gegenprobe (`python3 -I /tmp/p41-skripte/prod_r0.py <Probe-DB>`; Probe-DB aus den R-Helfern mit fünf Rechnungen: 1,005 € zweimal, festgeschrieben als `RE-2026-00001`; 20 Sorten, Centpreise mit ganzen Mengen und Bruchmenge 0,125 × 2,50 € als Entwürfe; Rechnung aus Bestellung): Zeile 5 `5 invoice_line_sources: 47 | Betrag der Quelle nicht in ganzen Cent: 44`, Zeile 7 `5 | Anlage aendert sich durch R: 3 [('RE-2026-00001', 'OFFEN'), ('ENTWURF-…', 'ENTWURF'), ('ENTWURF-…', 'ENTWURF')]` — genau die Fälle 1,005 €, 20 Sorten und Bruchmenge, nicht die Centpreise mit ganzen Mengen und nicht die Rechnung aus Bestellung.
- **R-A1 — Prod-Kopie (WAL-sicher, Runbook `novaerp-ssh-wal-backup`), `minga` und `demo`.** Kopie lokal nach `/tmp/p41-r-prod/<mandant>.db`, `chmod 444`. Dann mit `/tmp/p41-skripte/pdf_vergleich.py` aus R-W je einmal mit `main` und mit dem Branch:

```bash
REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -I /tmp/p41-skripte/pdf_vergleich.py <Kopie von main>/backend /tmp/p41-r-prod/minga.db > /tmp/p41-r-prod/minga-main.txt
REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -I /tmp/p41-skripte/pdf_vergleich.py /Users/nikolajunser-richter/minga-p41/backend /tmp/p41-r-prod/minga.db > /tmp/p41-r-prod/minga-r.txt
diff /tmp/p41-r-prod/minga-main.txt /tmp/p41-r-prod/minga-r.txt
```

  Erwartet: Im Branch-Ergebnis ist bei jeder Zeile `sammel` „anlage“ = „positionen“ (ohne von Hand ergänzte Positionen); `diff` zeigt nur die Rechnungen aus R-A0 Zeile 7, alle anderen PDF-Hashes sind gleich. Gemessen auf der Probe-DB (Prüfstand): 5 Rechnungen, 2 Hashes gleich (Centpreise mit ganzen Mengen, Rechnung aus Bestellung), 3 verschieden (0,62 → 0,63 bei 0,63; 13,34 → 13,40 bei 13,40; 2,02 → 2,01 bei 2,01). „Kopie von main“: `git archive main` (heute `1e2238b`) in ein neues, leeres Verzeichnis — nicht das Repo selbst, der Import der App legt sonst `backend/data/` im Repo an.
- **R-A2 — Browser (lokal oder im Testmandanten `abnahme`; Entwürfe danach verwerfen, keine Nummer verbraucht):** (1) Kunde mit Abrechnung „Monatliche Sammelrechnung“, ohne Rabatt; zwei Bestellungen mit Liefertag im Vormonat, je 1 × Freitextartikel zu 1,005 €, je ein Lieferschein (Belegdialog „Neuer LS“); Rechnungen → „Monatsrechnungen“ → Vormonat → „Entwürfe anlegen“; Entwurf öffnen, PDF: Positionstabelle „Gesamt 2.01 €“, „Netto: 2.01 €“, Anlage `1.01 EUR` (ältere LS-Nummer) und `1.00 EUR`. (2) Dasselbe mit einem Kunden mit Rabatt 3 %: „Zwischensumme 2.01 €“, Rabattzeile mit der Bezeichnung der Vorlage „-0.06 €“, „Netto 1.95 €“, Anlage 1.01 + 1.00 = Zwischensumme. (3) Ein Entwurf mit Centpreisen und ganzen Mengen: Anlage wie vor dem Deploy.
- **R-A3 — Live nach dem Deploy:** R-A0 erneut → Zeilen 1–6 unverändert (R schreibt nichts), Startlog ohne Fehler.

### D — Berliner Datum: Abnahme D (im Arbeitsbaum nachmessen, nicht dem Bericht glauben)

**A-D1 — Arbeitsbaum** (`/Users/nikolajunser-richter/minga-p41`): Prüfungen aus D.4 Step 3 (`18 passed`, `5 passed`), D.5 Step 4 (Zählungen, tsc, Build, beide Node-Prüfungen) und D.6 Step 1–2 selbst ausführen und Prozedur V laufen lassen (Abgleich leer). Die Dateiprüfung gilt nur für die D-Commits. V und Z liegen auf demselben Branch `feat/paket4-1` und ändern selbst Frontend-Dateien (V: `OrderDocumentsModal.tsx`, `OrderVerlauf.tsx`, `bestellverlauf.ts`, `bestellverlaufApi.ts`; Z: `Invoices.tsx`, `Tabs.tsx`, `rechnungssuche.ts`), ein `git diff 1e2238b -- frontend/` über den ganzen Branch sagt über D also nichts:

```bash
git log --reverse --format='%h %s' --stat --grep='(P41-D\.' 1e2238b..HEAD -- frontend/
```

Erwartet: genau ein Commit `(P41-D.5)` mit `frontend/src/pages/Inventur.tsx`, `frontend/src/pages/Sales.tsx` und `frontend/tests/unit/p41d-berlin.check.ts`, keine andere Frontend-Datei. Dazu D.6 Step 1 (Dateien aller D-Commits = „File Structure (D)“).

**A-D2 — Uhr-Probe im Browser auf einer Prod-Kopie** (Muster „Aufbau lokal“ aus P4-D des Paket-4-Plans; jede Kopie danach löschen):
1. WAL-sichere Kopie von `minga.db` (Backup-API, Memory „NovaERP SSH + WAL-Backup“) nach `/tmp/p41-d-abnahme/tenants/minga.db` holen.
2. Prozess-Zeitzone so wählen, dass das Prozessdatum vom Berliner Tag abweicht. Das spielt „UTC um 00:30“ ohne Warten auf Mitternacht nach. Vor 12 Uhr Berliner Zeit `Z=Etc/GMT+12` (Vortag), ab 14 Uhr `Z=Pacific/Kiritimati` (Folgetag). Prüfen: `TZ=$Z /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -c "import datetime, zoneinfo; print(datetime.date.today(), datetime.datetime.now(zoneinfo.ZoneInfo('Europe/Berlin')).date())"` → zwei verschiedene Tage. Gemessen 10.10. 09:44 mit `Etc/GMT+12`: `2026-10-09 2026-10-10`.
3. Backend aus dem Arbeitsbaum starten:
   ```bash
   cd backend && TZ=$Z AUTH_DISABLED=true TENANTS_DIR=/tmp/p41-d-abnahme/tenants DEFAULT_TENANT_SLUG=minga REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python /tmp/paket3/q4work/run_backend.py 8104
   ```
   Frontend: `cd frontend && VITE_AUTH_DISABLED=true VITE_API_URL=http://localhost:8104 ./node_modules/.bin/vite --port 5173 --strictPort`.
4. Im Browser: neue Bestellung mit Liefertag heute. Erwartet `BE-<Berliner Tag>-…`, im Kreis des Tages fortlaufend nach den Bestandsnummern. „Bestätigen“, im Belegdialog „AB“ → `AB-<Berliner Tag>-…`. Im Tagesplan „Ausgeliefert“ → Lieferschein `LS-<Berliner Tag>-…`, Packliste `PL-<Berliner Tag>-…`, Liefertag = Berliner Tag. Im Belegdialog „Neuer LS“ bei einer zweiten Bestellung → dasselbe Datum. Rechnung aus der Bestellung festschreiben → `RE-2026-<nächste>` mit Rechnungsdatum = Berliner Tag. AB- und LS-PDF öffnen: „Datum:“ = Berliner Tag, gleich dem Tag in der Nummer. Bestellansicht: „Erstellt am“ = derselbe Tag. Inventur → „Neue Inventur“: Stichtag-Vorgabe = Berliner Tag.
   *Grenze dieser Probe:* Die Prozess-Zeitzone verschiebt nur `date.today()`, nicht `datetime.now(timezone.utc)`. `order_date` ist also echte UTC-Zeit, und tagsüber sind UTC- und Berliner Tag gleich. „Datum:“, „Erstellt am“ und die Stichtag-Vorgabe zeigen hier nur, dass nichts kaputt ist. Das Fenster selbst belegen `test_belegdatum_im_pdf_um_halb_eins` (Backend, eingefrorene Uhr) und `p41d-berlin.check.ts` (Frontend, feste Zeitpunkte).
5. **Gegenprobe:** dasselbe mit einem Backend aus `main` (`1e2238b`). Erwartet: BE/AB/LS/PL mit dem Prozessdatum (Vortag bzw. Folgetag), Liefertag aber Berliner Tag. Gemessen per API in den Kopien: `BE-20261009-0001`/`LS-20261009-0001` gegen `BE-20261010-0001`/`LS-20261010-0001`.
6. Aufräumen: `find /tmp/p41-d-abnahme -type f \( -name "*.db*" -o -name "*.pdf" -o -name "*.png" \)` → löschen und erneut prüfen (leer).

**R-D1 — vor und nach dem Deploy, nur lesend** (gibt nur Zahlen aus, keine personenbezogenen Daten). Zugriff wie immer: `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103`, `C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)`, `docker exec -i "$C" python3 - < /tmp/p41-prod-d.py`:

```python
import sqlite3, time, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
B = ZoneInfo("Europe/Berlin")
print("TZ env:", repr(os.environ.get("TZ")), "tzname:", time.tzname, "localtime:", time.strftime("%Y-%m-%d %H:%M %Z"))
con = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
cur = con.cursor()
def berlin(ts):
    if ts is None: return None
    dt = datetime.fromisoformat(str(ts).replace("Z", ""))
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(B).date()
def utc(ts):
    dt = datetime.fromisoformat(str(ts).replace("Z", ""))
    if dt.tzinfo is not None: dt = dt.astimezone(timezone.utc)
    return dt.date()
for tab, col, pre in [("orders","order_number","BE"),("order_confirmations","confirmation_number","AB"),("delivery_notes","delivery_note_number","LS"),("packing_lists","packing_list_number","PL")]:
    rows = cur.execute(f"select {col}, created_at from {tab}").fetchall()
    n = len(rows); mit_datum = 0; abw = 0; utc_treffer = 0; nachts = 0
    for nr, ca in rows:
        teile = (nr or "").split("-")
        if len(teile) == 3 and teile[0] == pre and len(teile[1]) == 8:
            mit_datum += 1
            d = teile[1]
            bd = berlin(ca).strftime("%Y%m%d"); ud = utc(ca).strftime("%Y%m%d")
            if bd != ud: nachts += 1
            if d != bd:
                abw += 1
                if d == ud: utc_treffer += 1
    print(f"{tab}: {n} Zeilen, {mit_datum} mit {pre}-JJJJMMTT; angelegt 0-2 Uhr Berlin: {nachts}; Nummerndatum != Berliner Anlagetag: {abw} (davon = UTC-Tag: {utc_treffer})")
# LS: Nummerndatum vs actual_delivery_date
rows = cur.execute("select delivery_note_number, actual_delivery_date from delivery_notes where actual_delivery_date is not null").fetchall()
print("delivery_notes mit actual_delivery_date:", len(rows), "davon Nummerndatum != Liefertag:", sum(1 for nr, d in rows if nr.split('-')[1] != str(d).replace('-','')[:8]))
for tab in ["purchase_orders","inventory_counts"]:
    try: print(tab, cur.execute(f"select count(*) from {tab}").fetchone()[0])
    except Exception as e: print(tab, "Fehler", type(e).__name__)
print("invoices RE je Jahr:", cur.execute("select substr(invoice_number,1,7), count(*) from invoices where invoice_number like 'RE-%' group by 1").fetchall())
cols = [r[1] for r in cur.execute("pragma table_info(orders)")]
print("orders Spalten mit shop/source:", [c for c in cols if 'shop' in c or 'source' in c or 'extern' in c])
for c in [c for c in cols if 'shop' in c or 'source' in c]:
    print(c, cur.execute(f"select count(*) from orders where {c} is not null and {c} != ''").fetchone()[0])
print("settings shopify:", cur.execute("select count(*) from sqlite_master where name like '%shopify%'").fetchone()[0])
# order_date im Fenster (Berliner Tag != UTC-Tag): nur bei diesen Bestellungen
# ändert D.1 das gedruckte „Datum:“ im Nachdruck von AB/LS/PL (D-E10).
fenster = {oid for oid, od in cur.execute("select id, order_date from orders where order_date is not null").fetchall() if berlin(od) != utc(od)}
ab_ids = [r[0] for r in cur.execute("select order_id from order_confirmations").fetchall()]
ls_ids = [r[0] for r in cur.execute("select order_id from delivery_notes").fetchall()]
print("orders order_date im Fenster:", len(fenster), "davon mit AB:", sum(1 for o in ab_ids if o in fenster), "mit LS:", sum(1 for o in ls_ids if o in fenster))
```

Erwartet vor dem Deploy (gemessen 10.10.2026 06:54 UTC): `TZ env: None tzname: ('UTC', 'UTC')`; Zeilen 598/6/11/11; „angelegt 0-2 Uhr Berlin“ überall `0`; „davon = UTC-Tag“ überall `0`; `purchase_orders 0`, `inventory_counts 0`, `RE-2026` 10. Die letzte Zeile („order_date im Fenster“) ist neu und **noch nicht gemessen** (der Lesezugriff wurde in der Plan-Revision am 10.10. nicht freigegeben). Erwartet `0`, `0`, `0`, hergeleitet aus „angelegt 0-2 Uhr Berlin: 0“ für `orders` und dem Import-Zeitpunkt 00:00 (D-E10). **Gate vor dem Deploy:** Ist „davon mit AB“ oder „mit LS“ größer als 0, ändert D.1 bei so vielen bereits ausgegebenen Belegen das „Datum:“ im Nachdruck (vom UTC-Vortag auf den Berliner Tag). Dann entscheidet der Manager vor dem Deploy, ob das so bleibt; der Worker ist nicht beteiligt. Nach dem Deploy: an den Tagen danach muss „davon = UTC-Tag“ `0` bleiben, auch wenn „angelegt 0-2 Uhr Berlin“ größer als 0 wird. Das ist der eigentliche Nachweis im Betrieb.

**Nachricht an Gernot (Vorschlag, nur wenn er gefragt hat; nur so, wenn das R-D1-Gate `0` ergab, sonst den letzten Satz anpassen):**
> Belegnummern und das Datum auf Auftragsbestätigung, Lieferschein und Packliste richten sich jetzt immer nach deutscher Zeit. Wer nach Mitternacht ausliefert oder eine Packliste druckt, bekam bisher bis 2 Uhr früh eine Lieferscheinnummer und ein Belegdatum vom Vortag. Das ist behoben, auch bei „Erstellt am“ in der Bestellung und beim vorgeschlagenen Stichtag der Inventur. Bisher ist es bei dir nie vorgekommen; alle vorhandenen Nummern bleiben, wie sie sind.

### V — Bestellverlauf: Abnahme V (kein Worker-Task; jede Schreibaktion mit Freigabe)

- **V-W — Werkzeug anlegen (einmal vor Schritt 1).** Das Lese-Skript lag bisher nur unter `/tmp/p41v-tools/prod_audit.py` (macOS räumt `/tmp` auf); hier wörtlich. Nur `SELECT`, `mode=ro`; Benutzernamen nur als Klassen (Systemnamen wörtlich, Personen als `<Person>`), Werte nur als Schlüsselnamen, Gründe nur von Einträgen ohne Benutzer-ID (System/Runbook). Block unverändert, ohne Einrückung, in die Shell geben:

```bash
mkdir -p /tmp/p41-skripte && cat > /tmp/p41-skripte/prod_audit_v.py <<'P41V_EOF'
"""Paket 4.1, Abschnitt V — Bestellverlauf in minga, nur lesend (mode=ro, nur SELECT).
Gibt keine Personendaten aus: Benutzernamen nur als Klassen, Gründe nur von
Einträgen ohne Benutzer-ID (System/Runbook), Werte nur als Schlüsselnamen."""
import collections
import json
import re
import sqlite3

c = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
q = lambda s, *a: c.execute(s, a).fetchall()  # noqa: E731
print("aktionen", q("SELECT action, count(*) FROM order_audit_logs GROUP BY 1 ORDER BY 2 DESC"))
print("gesamt", q("SELECT count(*), count(DISTINCT order_id), min(created_at), max(created_at) FROM order_audit_logs"))
print("max_je_bestellung", q("SELECT max(n) FROM (SELECT count(*) n FROM order_audit_logs GROUP BY order_id)"))
print("ohne_name_ohne_id_je_aktion", q(
    "SELECT action, sum(user_name IS NULL), sum(user_id IS NULL), count(*) FROM order_audit_logs GROUP BY 1"))
# Systemnamen ohne Rücksicht auf Groß-/Kleinschreibung (Prod 09.10.: „systemkorrektur“ klein,
# RECHNUNG_ZUGEORDNET „Systemkorrektur“); Personennamen erscheinen nur als <Person>.
SYSTEM = {"systemkorrektur", "datenkorrektur", "system", "import", "admin"}
SYSTEM_MUSTER = re.compile(r"korrektur|runbook|system|import|datev|novaerp", re.I)
namen = collections.Counter()
for n, ohne_id in q("SELECT user_name, user_id IS NULL FROM order_audit_logs"):
    if n is None:
        klasse = "<NULL>"
    elif n.strip().lower() in SYSTEM or SYSTEM_MUSTER.search(n):
        klasse = n
    else:
        klasse = "<Person>"
    namen[(klasse, "ohne_id" if ohne_id else "mit_id")] += 1
print("user_name_klassen", sorted(namen.items(), key=lambda x: -x[1]))
schl = collections.defaultdict(lambda: (collections.Counter(), collections.Counter()))
for a, alt, neu in q("SELECT action, old_values, new_values FROM order_audit_logs"):
    for i, v in enumerate((alt, neu)):
        try:
            d = json.loads(v) if v else None
        except ValueError:
            d = "<kein JSON>"
        for k in (d if isinstance(d, dict) else [f"<{type(d).__name__}>"]):
            schl[a][i][k] += 1
for a, (alt, neu) in schl.items():
    print("schluessel", a, "alt", dict(alt), "neu", dict(neu))
st = collections.Counter()
for a, alt, neu in q("SELECT action, old_values, new_values FROM order_audit_logs"):
    try:
        o, n = (json.loads(alt) if alt else {}), (json.loads(neu) if neu else {})
    except ValueError:
        continue
    if isinstance(o, dict) and isinstance(n, dict) and ("status" in o or "status" in n):
        st[(a, o.get("status"), n.get("status"))] += 1
print("statuspaare", st.most_common())
gr = collections.Counter()
for a, r in q("SELECT action, reason FROM order_audit_logs WHERE user_id IS NULL"):
    gr[(a, (r or "<NULL>")[:60])] += 1
print("gruende_system", gr.most_common(30))
print("zeitformat", q("SELECT action, typeof(created_at), length(created_at) FROM order_audit_logs GROUP BY 1"))
P41V_EOF
shasum -a 256 /tmp/p41-skripte/prod_audit_v.py | cut -c1-16
```

  Erwartet: `e8f2f496c87c18a6` (Kopierfehler sonst; gleich `/tmp/p41v-tools/prod_audit.py`, solange es die Datei gibt).

0. **Im Arbeitsbaum nachmessen** (nicht dem Bericht glauben): V.5 Step 1–4 selbst ausführen; `git show --stat` je Commit.
1. **Produktion lesend** (vor dem Deploy, nur `SELECT`): `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103`, `C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)`, `docker exec -i "$C" python3 - < /tmp/p41-skripte/prod_audit_v.py` (Skript aus V-W). Prüfen (Review 10.10. als Vergleich, Befund „Produktion“):
   - **Aktionen:** jede gezählte Aktion steht in `AKTION_TEXT` (10.10.: alle 6 vorhandenen). Fehlt eine (z. B. eine Runbook-Aktion außer `RECHNUNG_ZUGEORDNET`): zeigt sich als „Sonstige Änderung (X)“ — vor dem Deploy Text in `AKTION_TEXT` und einen Fall in der Node-Prüfung ergänzen (Zählung +1 in `TestP41VVerlaufAnzeige`), Fix-Runde an denselben Worker.
   - **Schlüssel:** jeder Schlüssel in Runbook-Einträgen, den Verwaltung sehen soll, hat einen Text in `FELD_TEXT` (sonst erscheint der Rohname; 10.10.: nur `invoice` → „Rechnung“). Für die Halle ist jeder unbekannte Schlüssel ausgeblendet (gewollt).
   - **Wer:** `user_name_klassen` (Name × mit/ohne `user_id`; Systemnamen in jeder Schreibweise ausgegeben, Personen als `<Person>`) — als Systemnamen nur „systemkorrektur“/„datenkorrektur“ in beliebiger Schreibweise erwartet (10.10.: „systemkorrektur“ 574 und „Systemkorrektur“ 2, je mit `user_id`); andere Systemnamen klein in `KORREKTUR_NAMEN` aufnehmen, mit Fall in der Node-Prüfung (Zählung +1).
   - **Zeitformat:** `zeitformat` — Runbook-Zeilen mit anderer Länge prüfen (in UTC geschrieben? Sonst stehen sie 1–2 h verschoben; V-O7; 10.10.: alle Länge 26).
2. **Prod-Kopie im Browser** (WAL-sichere Kopie von `minga.db`, lokal `AUTH_DISABLED`, Frontend aus dem Branch):
   - Eine FAKTURIERT-Altbestellung (Runbook 09.10., Name in der DB klein „systemkorrektur“): Verlauf zeigt „Status geändert (Sammelaktion) — Geliefert → Fakturiert“ mit „NovaERP (Datenkorrektur)“ und dem Runbook-Grund, Zeit in Berliner Zeit (12:38 UTC → 14:38).
   - Die Bestellung zu RE-00005 bzw. RE-00010: „Rechnung zugeordnet“, „NovaERP (Datenkorrektur)“, Detail „Rechnung: RE-2026-000…“ (Verwaltung); als Halle ohne Detail, mit der Hinweiszeile, Grund mit Rechnungsnummer sichtbar (V-O5).
   - Eine im Tagesplan gepackte Entwurfsbestellung (seit Paket 4): „Bestätigt — Entwurf → Bestätigt — Grund: Beim Packen im Tagesplan bestätigt“, danach „Status geändert — Bestätigt → Gepackt“.
   - Eine importierte Bestellung: „Importiert“, Datei, externe Nummer, Benutzer.
   - Eine nach der Bestätigung bearbeitete Bestellung: Altänderungen „Benutzer (Name nicht gespeichert)“, neue Änderung im Branch mit Namen und „Pos. n · Produkt“.
   - `DEV_ROLES=production_staff`: Belege-Dialog ohne Rechnungen, Verlauf da; bei Preisänderungen „Preise und Beträge nur für …“, keine Beträge; Steuersatz-Korrektur ohne Beträge.
   - Belegstatus → „Belege“ → Verlauf da. Im Dialog „Quittieren“ → neuer Eintrag „Lieferschein quittiert“ ohne Neuöffnen.
   - Leer: neue Entwurfsbestellung → Leertext. Fehler: Backend stoppen, Dialog öffnen → Fehlertext + „Erneut laden“.
   - Dunkles Design, schmales Fenster (Zeitspalte und Name brechen um), langer Verlauf scrollt im Dialog.
3. **Nach dem Deploy (live, lesend):** `/health` 200; ein Verlauf in Gernots Arbeitsbereich im Browser; keine Migration, keine Datenänderung (E-V3).

### Z — Reiterzähler: Abnahme Z (Manager)

- **A0 — Branch:** Z.4 Step 1–5 im Worktree selbst ausführen, nicht der Meldung glauben. Erwartet: `7 passed`, Abgleich der Prozedur V leer, `tsc` und Build sauber.
  - Gegenprobe 1: In `Invoices.tsx` einen Reiter auf `count:` zurückdrehen → `test_zaehler_ohne_suche` wird rot.
  - Gegenprobe 2: Den Schlüssel auf `'invoices-overdue'` zurückdrehen → `test_schluessel_unter_invoices` wird rot.
  - Danach `git checkout -- frontend/src/pages/Invoices.tsx`.
- **A1 — Prod-Kopie:**
  - WAL-sichere Kopie von `minga.db` ziehen (Runbook `novaerp-ssh-wal-backup`, nur lesend).
  - Als Mandant eines lokalen Backends auf dem Branch einbinden, Frontend mit `npm run dev`.
  - Zahlen auf der Kopie: `select status, count(*) from invoices group by status;` und `select count(*) from invoices;`.
  - Die Zahlen erst nach dem ersten Öffnen der Rechnungsseite abfragen. `GET /invoices/overdue` stellt beim Laden fällige OFFEN auf UEBERFAELLIG um (Befund). Davor gezählt, könnte „Offen“ zu hoch und UEBERFAELLIG zu niedrig sein.
- **A2 — Browser, Rechnungen:**
  1. Leere Suche: „Alle“ = Gesamtzahl (≤ 100, ohne „+“), „Offen“ = Anzahl `OFFEN`, „Bezahlt“ = Anzahl `BEZAHLT`, „Überfällig“ = Wert der Karte „Überfällig“. Ein Reiter mit 0 hat keine Plakette.
  2. Suche nach „ökoring“, nach einer Kundennummer `KD-…` und nach `00010`: Jede Zahl ist gleich den Zeilen bzw. „x Einträge“ der Paginierung im Reiter. Ein Reiterwechsel ändert die Zahlen nicht.
  3. Status-Auswahl „Bezahlt“: „Alle“ = „Bezahlt“, „Offen“ ohne Plakette, „Überfällig“ unverändert (Offene Punkte 3).
  4. **Nur auf der Kopie:** Für eine überfällige Rechnung die volle Zahlung erfassen. Status-Auswahl „Alle Status“, Suche leer.
     - Gibt es keine überfällige Rechnung, auf der Kopie `due_date` einer offenen Rechnung in die Vergangenheit setzen und die Seite neu laden.
     - **Vorher prüfen:** Die Rechnung steht unter „Überfällig“, und ihre Zeile unter „Alle“ zeigt nicht mehr den Status „Offen“. Sonst die Seite einmal neu laden. Liste und `/invoices/overdue` laden parallel. Liest die Liste vor der Umstellung, steht die Rechnung dort noch als „Offen“ (Offene Punkte 6). Dann die Zahlen der Reiter und Karten notieren.
     - **Ohne Neuladen nach der Zahlung:**
       - „Überfällig“ sinkt um 1, im Reiter und in der Karte.
       - „Bezahlt“ steigt um 1, im Reiter und in der Karte „Bezahlt (Monat)“.
       - „Offene Forderungen“ sinkt um den offenen Betrag der Rechnung.
       - „Offen“ und „Alle“ bleiben **gleich**. Der Seitenaufruf hat die Rechnung schon auf UEBERFAELLIG gesetzt (`check_overdue_invoices`), oder sie ist TEILBEZAHLT bzw. MAHNVERFAHREN. „Offen“ zählt nur `OFFEN` (Z-E2, Offene Punkte 2), und `record_payment` setzt BEZAHLT.
     - Im Netzwerk-Tab folgt auf die Zahlung ein `GET /invoices/overdue`.
  5. Schmales Fenster: Die Reiterleiste bricht mit Plaketten nicht unschön um.
- **A3 — Regression:**
  - Bestellungen: „Heute | Morgen | Kommende | Alle“ zeigen ihre Plaketten wie vorher.
  - Inventar, Produkte, Produktion, Vertrieb: weiter **ohne** Zahlen, unverändert (Offene Punkte 1).
- **A4 — „N+“:** Mit Prod-Daten (≈ 10 Rechnungen) nicht erreichbar, belegt durch `test_listengrenze_zeigt_untergrenze`. Hat `demo` oder `abnahme` mindestens 100 Rechnungen, dort „Alle 100+“ ansehen.
- **A5 — Live nach dem Deploy (ohne Eingaben, erst nach 08:00):** Rechnungsseite in `minga` öffnen. Die Reiterzahlen stimmen mit A2 (1) überein, Stand Deploy.
  - Das Öffnen ist **nicht** rein lesend. `GET /invoices/overdue` stellt fällige OFFEN auf UEBERFAELLIG um und committet (Befund). Das war schon vor Z so und passiert bei jedem Aufruf der Seite durch Gernot.
  - Deshalb erst nach 08:00 (Europe/Berlin) öffnen. Dann hat der Job `overdue-invoices` diese Rechnungen am selben Tag schon umgestellt, und der Aufruf findet in der Regel nichts mehr. Vor 08:00 nicht öffnen.
  - Ob der Job lief, zeigt das Log nicht. INFO aus `app.*` wird verworfen (uvicorn ohne `--log-config`, Kommentar in `backend/app/api/v1/users.py`).
  - Fiel ein Neustart auf 08:00, fehlt der Lauf des Tages, denn der Scheduler hat keinen persistenten Jobstore. Dann schreibt der erste Seitenaufruf, was sonst der Job geschrieben hätte. Inhaltlich ist das dasselbe.
  - Sonst nichts klicken, was schreibt: keine Zahlung, kein Finalisieren, kein Versand.

## Offene Punkte

Nummern je Abschnitt wie in den Abschnittsplänen (R 1–8, D 1–7, V-O1–V-O8, Z 1–7).

### Fragen an Gernot — gebündelt für eine Nachricht (Manager-Abnahme, Schritt 5)

1. **Halle und Preise** (V-O2, Paket 3 Frage 4): Darf die Halle Preise und Rabatte einer Bestellung ändern? Heute ja; der Verlauf blendet ihr nur die Preisgeschichte aus.
2. **„Grund“ im Verlauf** (V-O5): Gründe von Datenkorrekturen nennen teils Rechnungsnummern und sind für die Halle sichtbar — in Ordnung?
3. **Wortwahl im Verlauf** (V-O8): „NovaERP (Datenkorrektur)“ und „System (automatisch)“ — passt das?
4. **Reiter „Offen“** (Z 2): Soll „Offen“ alle unbezahlten Rechnungen zeigen (auch teilbezahlt und überfällig)?
5. **Weitere Zähler** (Z 1): Zahlen auch in den Reitern von Inventar, Produkte, Produktion und Vertrieb?
6. **Anlage der Sammelrechnung** (R 3): Summenzeile „Summe der Lieferscheine“ gewünscht?
7. **Inventurnummer** (D 7): Bei rückwirkendem Stichtag Nummer nach dem Jahr des Anlagetags (heute) oder des Stichtags?

### R — Cent-Rundung

1. **Einzelpreis im PDF mit zwei Nachkommastellen** (`pdf_service`, Positionstabelle): 1,005 € erscheint als „1.00 €“, Menge 2, Gesamt „2.01 €“ — nicht nachrechenbar. Eigener Punkt: Preis mit bis zu 4 Nachkommastellen drucken (ändert PDFs festgeschriebener Rechnungen mit solchen Preisen → R-A0 Zeile 5 zeigt, ob es sie gibt).
2. **Storno einer Sammelrechnung löscht ihre Anlage aus dem PDF:** `cancel_invoice` gibt die Lieferscheine frei (`invoice_id = None`), die Anlage liest `DeliveryNote.invoice_id` — das stornierte Original zeigt beim erneuten Abruf keine Lieferscheine mehr (GoBD; in der Kopie gemessen: Centpreis-Sammelrechnung festgeschrieben, PDF mit Anlage, nach Storno PDF ohne Anlage, API `[]`). Lösung über `invoice_line_sources` (bleiben erhalten) statt `invoice_id` als eigener Punkt; nicht Teil von R (R ändert die Auswahl der Lieferscheine nicht).
3. **Summenzeile oder „vor Rabatt“ in der Anlage** — mit Gernot klären, ob die Anlage eine Summenzeile („Summe der Lieferscheine = Zwischensumme“) zeigen soll; ändert das Layout aller Sammelrechnungen (R-E3).
4. **Reihenfolge der Anlagezeilen** folgt der Datenbankabfrage, nicht Lieferdatum/Nummer (Altbestand; die Beträge hängen seit R nicht mehr davon ab).
5. **Zahlformat der Anlage** `1.01 EUR` (Punkt) statt deutsch — Altbestand wie die Positionstabelle.
6. **Produktion** in dieser Planung nicht gemessen → R-A0 vor dem Deploy.
7. **Vorschau des Monats- und Sammellaufs summiert ungerundet** (`monatsrechnung_service._summe_netto`, `invoices.batch_run_preview`: Menge × Preis × (1 − Rabatt) je Position ohne Rundung je Position). Gemessen in der Kopie (2 LS × 20 Sorten × 0,3333 €, ohne Kundenrabatt): Vorschau `summe_netto` 13.332, Dialog „Monatsrechnungen“ „13.33 € netto“ (`toFixed(2)`), angelegter Entwurf `subtotal` 13,40. Gernots Weg (Rechnungen → „Monatsrechnungen“). Lösung: je Position wie `InvoiceLine.calculate_line_total` runden (`ROUND_HALF_UP`), dann summieren; Kundenrabatt bleibt außen vor oder wird ausgewiesen — eigener Punkt, nicht Teil von R (R ändert nur die Anlage).
8. **Lieferschein mit Preisspalten rundet anders als die Rechnung** (`show_prices_on_delivery_note`): `OrderLine.line_net` per `quantize(Decimal("0.01"))` ohne `rounding` → `ROUND_HALF_EVEN` (`sales._calculate_line_amounts`, `OrderLine.calculate_line_totals`); die Rechnungsposition rundet `ROUND_HALF_UP`. Gemessen: 1 × 1,005 € steht auf jedem Lieferschein als „1.00 €“, in der Anlage nach R als 1,01 bzw. 1,00 (Position 2,01). Altbestand, nicht von R verursacht; schwächt die Nachrechenbarkeit der Anlage gegen den Lieferschein (R-E2(a)). Lösung `ROUND_HALF_UP` in `line_net` ändert Bestellsummen und Lieferschein-PDFs bereits versandter Belege → eigener Punkt mit GoBD-Prüfung (Kandidaten: R-A0 Zeile 5 `order_lines`, Wert „nicht in ganzen Cent“; betroffen sind nur exakte halbe Cent).

### D — Berliner Datum

1. **Weitere `date.today()` in Prozesszeit, ohne Nummernbezug (nicht in D, D-E9).** Wirkung jeweils nur 0–2 Uhr Berliner Zeit:
   - `invoice_service.create_invoice` und `invoices._sammelrechnung_anlegen`: Entwurfsdatum; beim Festschreiben ersetzt.
   - `production.py` und `print_jobs.py`: `tag = datum or date.today()`, Tagesplan und Druckaufträge ohne Datum. Ob das Frontend immer `datum` schickt, ist nicht geprüft.
   - `inventory.py`: Ernte-Schnellbuchung `BATCH-JJJJMMTT` und `harvest_date`.
   - `InvoiceService.check_overdue_invoices` und `invoice_tasks`: Überfälligkeit; Läufe 08:00/09:00, also außerhalb des Fensters.
   - `pdf_service`: „Erstellt am“ (Mahnung) und `days_overdue`.
   - `sales.py`: DATEV-Debitoren-Dateiname.
   - `models/invoice.is_overdue`, `models/customer`, Prognose, Berichte.
   - Frontend, UTC-Tag des Browsers als Vorgabe (`new Date().toISOString().split('T')[0]`): Liefertag und Vergleich „heute“ in `CreateOrderModal.tsx` (um 00:30 wäre der vorgeschlagene Liefertag der Vortag), `heuteIso` in `Abonnements.tsx`, Kennzahl „Lieferungen heute“ in `Sales.tsx`, `SowingForm.tsx`, `HarvestForm.tsx`, `ChargenGridModal.tsx`, `labelDate` in `Production.tsx`, `lieferdatum` in `Inventory.tsx`, `Warenfluss.tsx`. Anzeige `new Date(po.order_date)` in `Purchasing.tsx` (EK trägt nur das Jahr; Widerspruch nur am 01.01. 00:00–00:59). `heuteBerlin`/`datumKurz` liegen in `belegstatus.ts` bereit.

   Vorschlag: eigener Aufräumschritt mit einem Helfer für alle. Dabei die sieben vorhandenen Kopien zusammenlegen; die Tests, die heute `order_status_service.datetime`, `invoice_service._heute_berlin`, `sepa_service.datetime`/`heute_berlin` und `belegstatus.heute_berlin` festsetzen, ziehen mit um. Manager-Entscheidung.
2. **`TZ=Europe/Berlin` im Container als Zusatzschutz** (D-E4). Eigene Entscheidung. Wenn ja: beide Dockerfiles und die Compose-Dateien, vorher prüfen, ob `/usr/share/zoneinfo` bzw. `tzdata` im Image liegt (nicht gemessen; `zoneinfo` funktioniert in Produktion, Quelle unbekannt), und die Prozedur V einmal mit `TZ=UTC` und einmal mit `TZ=Europe/Berlin` laufen lassen.
3. **572 BE-Nummern mit Datum ≠ Berliner Anlagetag** (keine mit UTC-Tag). Vermutlich Altdaten-Import (Nummer = Bestelldatum). Eine zweite Leseabfrage zur Bestätigung ist nicht gelaufen. Nicht Teil von D, nur zur Einordnung.
4. **Nummernkollision ohne Wiederholung** bei AB, BE (Shopify), EK und INV. Nur LS/PL haben P4-Fix.4. Das `with_for_update` in `_generate_order_number` wirkt in SQLite nicht. EK und INV zählen mit `count + 1` statt Höchstwert + 1. Außerhalb von D.
5. **Überschneidungen** wurden gegen Zwischenstände der Nachbar-Kopien geprüft (10:20, `diff -rq` gegen `1e2238b`). Die Zusammenführung prüft die Anker erneut.
6. **R-D1 „order_date im Fenster“ ungemessen** (D-E10). Vor dem Deploy messen; Gate siehe R-D1.
7. **Inventur mit rückwirkendem Stichtag** (etwa am 02.01. auf den 31.12.): Nummer `INV-<Jahr des Anlagetags>` nach D-E3. Falls Gernot die Inventurnummer nach dem Stichtagsjahr erwartet, ist das eine eigene fachliche Entscheidung (D-E11).

### V — Bestellverlauf

- **V-O1 — Produktion im Review am 10.10. lesend gemessen** (Befund „Produktion“; in der Revision nicht selbst nachgemessen): alle 6 vorhandenen Aktionen haben einen Text, der einzige Runbook-Schlüssel `invoice` heißt „Rechnung“, beide Schreibweisen von „systemkorrektur“ werden erkannt, Zeitformat einheitlich. Abnahme Schritt 1 misst vor dem Deploy erneut (Runbooks seit dem 10.10.); unbekannte Aktionen sind bis dahin als „Sonstige Änderung (X)“ sichtbar, unbekannte Werte für die Halle ausgeblendet.
- **V-O2 — Darf die Halle Preise und Rabatte ändern?** (Paket 3, Frage 4, weiter offen). Heute ja (Bearbeiten-Dialog, `update_order_line`, `add_order_line`). V blendet nur die Preisgeschichte aus. Sagt Gernot „nein“, braucht es eine Serverprüfung in den Positionsrouten und eine Anpassung im Bearbeiten-Dialog (eigener Task).
- **V-O3 — Anlegen steht nicht im Verlauf:** Das Anlegen schreibt keinen Eintrag, Änderungen an Entwürfen auch nicht (bewusst seit Paket 2). Ein Eintrag „Angelegt“ (mit Name) wäre eine kleine Ergänzung in `create_order`.
- **V-O4 — Alteinträge ohne Namen** (`UPDATE`, `…_LINE` bis zum Deploy): „Benutzer (Name nicht gespeichert)“. Kein Nachtragen aus Keycloak (Protokoll bleibt unverändert). Alte `UPDATE_LINE`-Einträge nennen keine Position. Prod 10.10. (Review): noch keine solchen Einträge; ohne Namen sind nur 23 `CONFIRM`/`STATUS_CHANGE` vom 07./08.10. (vor Paket 2), mit `user_id`.
- **V-O5 — Freitext „Grund“ sieht auch die Halle** (niedrig). Konkret in Prod (Review 10.10., nur Ja/Nein gezählt): Die Gründe beider `RECHNUNG_ZUGEORDNET`-Einträge nennen eine Rechnungsnummer (`RE-…`, keine Beträge); die Halle sieht sie dort und die Aktion „Rechnung zugeordnet“, obwohl Rechnungen für sie gesperrt sind (`_deps_geld`). **Ausdrücklich in Kauf genommen** (Manager): Eine Nummer ist kein Preis, keine Kondition und kein Betrag, die Rechnung selbst bleibt gesperrt, betroffen sind zwei Bestellungen; den Grund nur für Runbook-Aktionen auszublenden, bräuchte im Filter eine zweite Regel (Aktionsliste) neben der Positivliste. Schreibt jemand Preise in einen Grund, sind sie ebenso sichtbar. Will Gernot das nicht: für Logins ohne Konditionssicht `reason` bei Aktionen außerhalb der 11 Code-Aktionen leeren (Zusatz in `get_order_audit_log`, eigener Task).
- **V-O6 — Verlauf nur im Belege-Dialog**, nicht im Bearbeiten-Dialog; `OrderVerlauf` lässt sich dort mit einer Zeile einbauen, falls Gernot ihn beim Bearbeiten sehen will.
- **V-O7 — Zeitzone von Runbook-Zeilen:** trifft heute nicht zu — Prod 10.10. (Review): alle `created_at` `TEXT` der Länge 26 mit Leerzeichen (ORM-Format, UTC), auch die Runbook-Zeilen (R-B3 schreibt ebenso UTC). Schriebe ein künftiges Runbook Berliner Zeit, zeigte der Verlauf den Eintrag 1–2 h später. Nur Anzeige; Prüfung in Abnahme Schritt 1.
- **V-O8 — Wortwahl für Gernot:** „NovaERP (Datenkorrektur)“ für Systemkorrekturen, „System (automatisch)“ ohne Login — bei Bedarf in `bestellverlauf.ts` anpassen (Node-Prüfung mit).

### Z — Reiterzähler

1. **(Manager/Gernot) Weitere unsichtbare Zähler.**
   - Diese Seiten übergeben `count`, und die Reiterleiste ignoriert es:
     - `Inventory.tsx`: Saatgut, Fertigware, Verpackung, Lagerorte
     - `Products.tsx`: Produkte, Wachstumspläne, Produktgruppen
     - `Production.tsx`: Alle, Keimung, Wachstum, Erntereif, Verpackungsplan (dieser mit festem `count: 0`)
     - `Sales.tsx`
   - Behebung: je Seite `count` → `badge`, jeweils eine Zeile.
   - Nicht in Z, weil nur die Rechnungsseite beauftragt ist. Vorschlag: eigener kleiner Punkt nach Rückfrage.
2. **(Gernot) „Offen“ zeigt nur Status `OFFEN`.**
   - Teilbezahlte Rechnungen stehen nur unter „Alle“ und, wenn fällig, unter „Überfällig“.
   - Überfällige (`UEBERFAELLIG`) stehen nicht unter „Offen“.
   - Die Karte „Offene Forderungen“ rechnet dagegen OFFEN, TEILBEZAHLT und UEBERFAELLIG.
   - Frage an Gernot: Soll „Offen“ alle unbezahlten Rechnungen zeigen? Das wäre eine Änderung in `rechnungenJeReiter`; Zähler und Tabelle folgen dann automatisch.
3. **„Überfällig“ folgt nicht der Auswahl von Status und Typ**, weil die Liste von einem eigenen Endpunkt kommt. Das war schon in Paket 4 so. Tabelle und Zähler sind gleich.
4. **Karte „Bezahlt (Monat)“** zählt alle bezahlten Rechnungen der geladenen Liste, nicht nur den Monat. Beschriftung oder Berechnung korrigieren, nicht in Z.
5. **Serversuche und Blättern** (Paket-4-Offener-Punkt 4). Ab etwa 100 Rechnungen zeigen die Reiter „N+“. Danach braucht es `GET /invoices?suche=` mit Gesamtzahlen je Status; dann kommen die Zähler vom Server.
6. **Gleichzeitige Abfragen.** `GET /invoices/overdue` setzt OFFEN → UEBERFAELLIG und läuft parallel zur Liste.
   - Zwischen 00:00 und dem Job um 08:00 kann eine heute fällig gewordene Rechnung beim ersten Laden unter „Offen“ und „Überfällig“ zugleich zählen, bis die Seite das nächste Mal lädt.
   - Seit Z.3 genügt dafür jede Rechnungsänderung. Priorität niedrig.
7. **Prod-Zahlen nicht nachgemessen.** Der lesende Zugriff war in der Planung gesperrt. Stand aus dem Paket-4-Plan: 10 Rechnungen am 09.10. Abnahme A1/A2 prüft das nach.
