# Nachtrag 09.10. — SKR04, Firmendaten, Belegordner — Implementation Plan

> **Hinweis für Worker (Codex, ohne Netzwerk):** Diesen Plan Task für Task in der Reihenfolge der Nummern 1–17 abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Lies vor jedem Task seinen Abschnitt frisch aus der Plandatei (sie kann während des Laufs ergänzt werden). Kein Task wird übersprungen, zusammengefasst oder auf eigenes Urteil verkürzt. **Stoppregeln** stehen unter „Global Constraints“. Eigene Patch- oder Ankerfehler sind **kein** Stoppgrund: auf Funktions-/Klassennamen und die zitierten Zeilen bzw. Blöcke ankern (**nie auf Zeilennummern**), nach jedem Patch mit `grep -n` prüfen, dass genau die gemeinte Stelle geändert ist. Die drei Abschnitte D, F und O tragen eigene Kurzbezeichnungen (D.1 … O.6); sie stehen in Texten, Commit-Betreffen und Code-Kommentaren und meinen die Tasks laut Tabelle „Reihenfolge“ (z. B. „Stand nach Task D.3“ = nach Task 3). Die Abschlussmeldungen in Task 5 (D), Task 10 (F) und Task 16 (O) sind Zwischenstände für den Bericht — **nicht anhalten**, der Lauf endet mit Task 17. **Abnahme**, **Manager-Abnahme** und **Offene Punkte** am Ende sind Manager-Arbeit, kein Worker-Task.

**Goal:** Drei Punkte aus Gernots Rückmeldung vom 09.10.2026 (Antworten im Word-Dokument `261009_Kommentare.docx`) und aus der Spec („Offen (niedrig, 09.10.)“), in einem Arbeitsbaum, einem Branch und einem Deploy:
- **D — DATEV-Export im Kontenrahmen des Mandanten.** Gernot: „Wir arbeiten selber mit DATEV Mittelstand Faktura mit Rechnungswesen und haben auch DATEV Unternehmen online. Kontenrahmen SKR04“. Der Export kennt nur SKR03. Danach gilt je Mandant `DATEV_KONTENRAHMEN` (`SKR03` | `SKR04`, ohne Eintrag `SKR03`), festgeschriebene Rechnungen werden beim Export abgebildet statt umgeschrieben (GoBD), und der Export bleibt für `minga` gesperrt (`DATEV_EXPORT_SPERRE`), bis der neue Steuerberater die Kontierung bestätigt.
- **F — Karte „Firmendaten“ speichert auf dem Server.** Gernot auf die Bitte, den Firmennamen einzutragen: „Das steht doch schon drinnen? Wo sollte ich das noch eintragen?“ — die Karte speicherte nur im Browser (`localStorage`). Danach liest und schreibt sie `COMPANY_*` über `/admin/settings`, übernimmt Browser-Werte einmalig als Vorschlag, maskiert die Werte im PDF und grüßt in Beleg-Mails ohne Firmennamen mit dem Absendernamen. **Briefkopf und Fuß** der Belege kommen weiter aus den Belegvorlagen (Admin → Belegvorlagen) und erscheinen nicht doppelt (Abschnitt F, „Befund“, Entscheidung F-E1).
- **O — Belegordner.** Gernot: „Ist es möglich einen Speicherort für die Belege zu definieren?“ In Chrome/Edge legt jede Beleg-Schaltfläche die Datei unter `<Ordner>/<Belegart>/<JJJJ-MM>/<Belegnummer>.pdf` ab; sonst Download wie heute.

**Architecture:** Keine Schemaänderung, keine Migration, keine neue Tabelle (`tenancy._auto_migrate` unberührt). D: neues Modul `app.services.kontenrahmen` (eine Kontentabelle je Rahmen), `datev_service` und `InvoiceService.add_line`/`update_invoice_line` lesen den Rahmen, Rahmenprüfung in `PATCH /admin/settings`, neuer Endpunkt `GET /invoices/datev-export/einstellungen`, Dialog und Einstellungskarte „DATEV-Export“. F: `settings_service.firmendaten_pruefen`, Maskierung in `pdf_service`, `belegversand.absendername`, neue Komponente `FirmendatenKarte`; kein neuer Endpunkt. O: reines Frontend — `belegpfad.ts`, `belegordner.ts` (die eine Download-Funktion `belegHerunterladen`), `BelegordnerKarte`; alle Beleg-Downloads (auch der von D geänderte DATEV-Dialog) laufen darüber.

**Tech Stack:** FastAPI + SQLAlchemy 2.0, SQLite je Mandant, Pydantic v2, React 18 + TypeScript 5.9, TanStack Query 5; Node ≥ 23.6 für die Node-Prüfungen von O.

**Ausgangsstand:** `main` @ `df84f7b` („docs: B6 live, Plan B6“; live: Pakete 1, 2, 2.1, 3, B6, Benutzerverwaltung, Sicherheitsfixes). Alle drei Abschnitte sind auf `df84f7b` geplant, einzeln durchgespielt und zusammen in der Reihenfolge dieses Plans nachgespielt (Prüfstand). Keine Zeilennummern als Anker.

**Spec:** `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md` — Abschnitt „Umsetzungsstand …“, Punkt „Offen (niedrig, 09.10.)“ (1) Firmendaten-Karte und (2) Mail-Grußformel (→ F); „Offene Entscheidungen“ 5 (DATEV: Kontenrahmen, EXTF) und Sofortmaßnahme 1 (kein DATEV-Export) (→ D). O ist neu (Gernot, 09.10.).

## Reihenfolge

| Task | Kurz | Inhalt | Art | Neue Tests |
|---|---|---|---|---|
| 1 | D.1 | Kontentabelle je Rahmen, Einstellung `DATEV_KONTENRAHMEN`; legt `backend/tests/test_nachtrag_0910.py` an | Backend | 14 |
| 2 | D.2 | Kontierung beim Anlegen und beim Satzwechsel nach Rahmen | Backend | 8 |
| 3 | D.3 | Export bucht im Kontenrahmen des Mandanten | Backend | 9 |
| 4 | D.4 | Exportsperre, Einstellungen für den Dialog | Backend | 6 |
| 5 | D.5 | Export-Dialog mit Rahmen und Sperre, Karte „DATEV-Export“ | Frontend | — |
| 6 | F.1 | PDF: Firmendaten maskieren, Vorrang der Belegvorlage festhalten | Backend | 4 |
| 7 | F.2 | Firmendaten beim Speichern prüfen | Backend | 11 |
| 8 | F.3 | Beleg-Mails: Grußformel mit dem Absendernamen | Backend | 5 |
| 9 | F.4 | Karte „Firmendaten“ liest und schreibt den Server | Frontend | — |
| 10 | F.5 | Abschluss F (ohne Commit) | Prüfung | — |
| 11 | O.1 | Ablagepfad als reine Funktion (Node-Prüfung, 35 Fälle) | Frontend | — |
| 12 | O.2 | Die eine Download-Funktion für Belege | Frontend | 8 |
| 13 | O.3 | Einstellungen: Belegordner wählen, Zugriff erlauben, zurücksetzen | Frontend | — |
| 14 | O.4 | Belegdialog und Tagesplan | Frontend | — |
| 15 | O.5 | Rechnungsseite und Lastschriften | Frontend | — |
| 16 | O.6 | Abschluss O (ohne Commit) | Prüfung | — |
| 17 | — | Abschluss Nachtrag: Gesamtprüfung und Gesamtmeldung (ohne Commit) | Prüfung | — |

**Warum D → F → O:** D ist steuerlich relevant und braucht vor dem Deploy einen Datenschritt (Sperre und Rahmen für `minga`, Manager-Abnahme); D.1 legt die gemeinsame Testdatei mit dem Kopf für alle Abschnitte an. F ist klein und unabhängig. O kommt zuletzt, weil es den von D geänderten DATEV-Dialog und alle übrigen Beleg-Downloads über `belegHerunterladen` führt; mit allen drei Karten ist das Einstellungsraster lückenlos (Review Focus, Punkt Ü1). Innerhalb jedes Abschnitts gilt seine eigene Reihenfolge. Fachliche Abhängigkeiten zwischen den Abschnitten gibt es nicht; alle Berührungen sind Text-Anker in gemeinsamen Dateien (File Structure, „Überschneidungen“).

**Commits:** 14 (D 5, F 4, O 5); Tasks 10, 16 und 17 committen nichts.

## Prüfstand (Gesamtlauf)

Maßgeblich für den Worker sind allein die Zahlen in den Steps. Die Prüfstände der Abschnitte (einzeln auf `df84f7b`, mit Reviews) stehen in den Abschnitten.

- **Gesamtlauf D → F → O** in `/tmp/n0910-kopie-plan` (frisches `git archive df84f7b`, `frontend/node_modules` als Symlink; Treiber `/tmp/n0910-plan-tools/lauf.sh`, Protokoll `lauf.log`): die Code-Blöcke aus den Abschnittstexten mechanisch mit ihren Ankern angewendet (D: aus dem Plantext geparst, `d-apply.py`; F: `f-replay.py` mit den `F-BLOCK`-Markern; O: `o-anwenden.py`), jeder Anker genau einmal gefunden.
  - **D** (Tasks 1–5): Rot/Grün `14 failed` → `14 passed`; `6 failed, 2 passed` → `8 passed`; `6 failed, 3 passed` → `9 passed` (Bestandstests DATEV `149 passed`); `5 failed, 1 passed` → `6 passed`; `tsc` 4 Fehler → sauber. Prozedur V nach Task 5: `14 failed, 1681 passed, 2 skipped, 1 error`, Baseline-Namen.
  - **F** (Tasks 6–9, nach D): Vorbereitung F wie angegeben bis auf den Hash von `Settings.tsx` (nach Task 5 `041a51f…` statt `9dc4b96…` — erwartet, darum steht die Hash-Prüfung nur in der Vorbereitung vor Task 1); `1 failed, 3 passed` → `4 passed` mit der Meldung aus Task 6 Step 2, Umfeld `195 passed`; `6 failed, 5 passed` (die sechs genannten Tests) → `11 passed`, `admin.py` genau drei Treffer, Umfeld `467 passed`; `2 failed, 3 passed` → `5 passed`; F-Klassen `20 passed`; `tsc` genau 1 × TS2307 → sauber, Build `✓ built`, alle Prüf-`grep`s wie in den Steps. Prozedur V: `14 failed, 1701 passed, 2 skipped, 1 error`, Baseline-Namen.
  - **O** (Tasks 11–15, nach D und F): `ERR_MODULE_NOT_FOUND` → `35 Fälle ok`/`8 Fälle ok`; `8 failed` → `8 passed`; `tsc` sauber; 4 × TS2339 (`OrderDocumentsModal.tsx` × 3, `Tagesplan.tsx` × 1) → sauber; Ausgangszählung Task 15 Step 1 nach Task 5 unverändert `6`/`1`; End-`grep`s aus Tasks 14/15 wie angegeben; Paket-3-Abnahmetests `5 passed`; `createObjectURL` genau in den 7 Dateien aus Task 16 Step 4; Build `✓ built`.
  - **Schluss:** Prozedur V `14 failed, 1709 passed, 2 skipped, 1 error`, `comm`-Abgleich leer; `tests/test_nachtrag_0910.py` gesamt `65 passed`; `ruff --select F821,F823` über alle 10 geänderten Python-Dateien Exit 0; genau die 21 Dateien aus „File Structure“ geändert bzw. neu.
- **Nicht gemessen im Gesamtlauf:** die Commits (die Kopie hat nur einen Basis-Commit), Oberfläche im Browser, Produktionsdaten (Manager-Abnahme).

## Global Constraints

- **Arbeitsort:** Worktree `/Users/nikolajunser-richter/minga-n0910`, Branch `feat/nachtrag-0910`, vom Manager vor dem Dispatch aus `main` @ `df84f7b` angelegt: `git worktree add ../minga-n0910 -b feat/nachtrag-0910 main` und `ln -s /Users/nikolajunser-richter/minga-greens-erp/frontend/node_modules frontend/node_modules`. Jeder Befehl beginnt im Worktree-Wurzelverzeichnis (`<Arbeitsbaum>` in den Abschnitten).
- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` und `backend/venv311` sind kaputt.
- **Neue Tests** nur in `backend/tests/test_nachtrag_0910.py`. Task 1 legt die Datei mit dem gemeinsamen Kopf an, alle anderen Tasks hängen ihren Block **ans Dateiende**. Präfixe je Abschnitt (ein gleichnamiger Helfer würde still ersetzt): D — Klassen `TestD…`, Helfer `_d_…`, Konstanten `_D_…`; F — Klassen `TestF1…`/`TestF2…`/`TestF3…`, Helfer und Fixtures `_f_…`, Konstanten `_F_…`; O — Klasse `TestOBelegordner`, Helfer `_o_…`. Keine `autouse`-Fixture. Fixture `client` aus `tests/conftest.py`. **Bestehende Tests ändert kein Task.**
- **Einzeltests in `test_nachtrag_0910.py` immer über Klassen-IDs, nie `-k`** (in der gemeinsamen Datei zählt `-k` fremde Klassen als `deselected` mit; `-k` in fremden Testdateien, z. B. für die Paket-3-Abnahmetests, bleibt wie in den Steps). Die Befehle stehen in den Steps; zusätzlich:
  - **„Lauf F“** (Abschnitt F, je Task die eigene Klasse `TestF1PdfBriefkopf`, `TestF2FirmendatenSpeichern`, `TestF3MailGruss`):
    ```bash
    cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestF1PdfBriefkopf -q -p no:cacheprovider 2>&1 | tail -3
    ```
  - **„Tests O“** (Abschnitt O):
    ```bash
    cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestOBelegordner -q -p no:cacheprovider
    ```
  - **Alle Nachtrag-Tests** (Task 17): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py -q -p no:cacheprovider` → nach Task 12 `65 passed`.
- **Baseline nach B6** (Fehlernamen, **nie die Anzahl** vergleichen; 14 failed + 1 error). Die Datei `/tmp/n0910-baseline-namen.txt` legt die Vorbereitung an — Block unverändert, ohne Einrückung, in die Shell geben:

```bash
test -f /tmp/n0910-baseline-namen.txt || cat > /tmp/n0910-baseline-namen.txt <<'EOF'
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
sort -o /tmp/n0910-baseline-namen.txt /tmp/n0910-baseline-namen.txt; wc -l < /tmp/n0910-baseline-namen.txt
```

  Erwartet: `15`. `test_features.py::TestFeatures::test_subscription_processing` scheitert an `async def` ohne Plugin, nicht am Code dieses Plans; er bleibt rot.
- **Kein Netzwerk:** kein `npm install`, kein `git pull`/`push`, kein `curl`. **Kein Deploy, keine Verbindung zum Produktionsserver.**
- **Commits** nur mit den im Task genannten Dateien, nie `git add -A` oder `git add .`. Nachricht nach dem Muster `git commit -m "<Betreff>" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"` (Betreffe stehen in den Tasks). Erwartete unversionierte Einträge, die **sauber** sind und nie committet werden: `frontend/node_modules` (Symlink), `backend/data/` (die Testsuite legt `backend/data/tenants/dev.db` samt `-wal`/`-shm` an), falls vorhanden `.claude-flow/` und `.swarm/`, die unversionierte Plandatei, `frontend/dist/`.
- **Frontend-Prüfung:** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut), Build `cd frontend && npm run build` (endet mit `✓ built in …`; die Warnung „Some chunks are larger than 500 kB“ ist Altbestand). `tsconfig.json` hat `noUnusedLocals`. Playwright gehört nicht zur Worker-Prüfung. **Node-Prüfung (O):** `cd frontend && node tests/unit/belegpfad.check.ts` (Node ≥ 23.6, TypeScript ohne Build).
- **Statisch** (`ruff` 0.1.13 unter `/opt/homebrew/bin/ruff` meldet Erfolg stumm; fehlt er dort: „nicht ausführbar“ melden, nicht ersetzen):
  - **für D** (Tasks 3 und 4): `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/kontenrahmen.py app/services/datev_service.py app/services/invoice_service.py app/api/v1/invoices.py app/api/v1/admin.py app/schemas/invoice.py` → keine Ausgabe, Exit-Code 0.
  - **für F** (Task 10) und **gesamt** (Task 17): Befehle in den Tasks.
- **UI-Texte auf Deutsch**, Toast-Texte genau wie im Code.
- **Stoppregeln** (in Abschnitt D heißen 1–3 „D1“–„D3“, in F und O „Stoppregel 1–5“):
  1. Ein zitierter Anker fehlt, **weil der Code inhaltlich anders aussieht** (Funktion fehlt, andere Logik, anderer Rückgabewert; z. B. `erloeskonto_fuer` hat schon zwei Parameter, ein anderer Abschnitt hat die PDF-Schaltfläche umgebaut): stoppen, Fundstelle bzw. Fehlerausgabe melden.
  2. Rot oder Grün weicht nach korrekt angewendetem Schritt von der Erwartung ab (andere Anzahl, anderer Testname, andere Fehlermeldung): stoppen, exakte Ausgabe melden. Nicht „passend machen“. Die erwarteten Meldungen sind inhaltlich gemeint: pytest kürzt lange Werte in der `assert`-Zeile, maßgeblich sind die vollständigen Werte bzw. die Diff-Zeilen darunter. Eine solche Kürzung ist kein Stoppgrund.
  3. Prozedur V zeigt einen Fehlernamen, der nicht in der Baseline steht, oder ein Baseline-Name fehlt: stoppen, `comm`-Ausgabe melden.
  4. Ein Paket-3-Abnahmetest (`TestAbnahmeSepaBerlin`, `TestAbnahmeRechnungsberechtigung`) wird rot: stoppen, Ausgabe melden. Der Test wird **nicht** angepasst.
  5. **Kein Stopp:** eigene Patch-/Ankerfehler (Leerzeichen, Mehrfachtreffer durch zu kurzen Anker, Tippfehler) — selbst beheben, mit `grep -n` belegen, in der Abschlussmeldung vermerken. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht ebenso.
  
  Eine Abweichung in der **Vorbereitung** ist Stoppregel 1 — außer dem Hash von `Settings.tsx` (siehe dort).

## Prozedur V (Vollauf mit Namensabgleich)

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/n0910-voll.txt 2>&1; tail -1 /tmp/n0910-voll.txt; grep -E '^(FAILED|ERROR) ' /tmp/n0910-voll.txt | sed 's/ - .*//' | sort > /tmp/n0910-namen.txt; comm -3 /tmp/n0910-baseline-namen.txt /tmp/n0910-namen.txt; echo "--- Ende Abgleich"
```

Erwartet: letzte Zeile `14 failed, N passed, 2 skipped, 1 error in …s`, **keine** Zeile zwischen der Summenzeile und `--- Ende Abgleich`. Dauer 1–3 min. N im Gesamtlauf gemessen (nur zur Orientierung; maßgeblich sind die Namen):

| nach Task | 0 (Basis) | 1 | 2 | 3 | 4–5 | 6 | 7 | 8–11 | 12–17 |
|---|---|---|---|---|---|---|---|---|---|
| N | 1644 | 1658 | 1666 | 1675 | 1681 | 1685 | 1696 | 1701 | 1709 |

Jede Erwähnung von „Prozedur V“ in den Abschnitten meint diesen Befehl (die Abschnitte hatten einzeln eigene Ausgabedateien; im Gesamtplan gilt nur `/tmp/n0910-voll.txt`).

## Review Focus

Was **kein automatischer Test** abdeckt (keine Frontend-Tests im Repo); der Manager prüft es in der Manager-Abnahme. Die Review-Fokus-Absätze der einzelnen Tasks gelten zusätzlich.

**Übergreifend (entsteht erst durch das Zusammenspiel):**
- **Ü1 — Einstellungsraster.** Nach allen drei Abschnitten stehen die Karten ab `lg` so (am Code gelesen, zweispaltiges Raster): Saisonzyklus | Monatsrechnungen · DATEV-Export (volle Breite, D) · SMTP (volle Breite) · SEPA-Lastschrift | Belegordner (O) · Lexware Office | Shopify · Firmendaten (volle Breite, F) · Systeminfo | Kapazitäten · Benachrichtigungen | Forecasting. Keine leere Zelle (auf `df84f7b` stand Shopify allein in seiner Zeile). → DB6, FB-Prüfungen, C1.
- **Ü2 — DATEV-Dialog.** D (Rahmen, Kontenzeile, Sperre, Servertext bei 409) und O (Ablage `DATEV-Exporte/<JJJJ-MM>/…`, immer neu daneben) im selben Dialog: Mit Sperre ist der Knopf gesperrt, es entsteht weder Datei noch Ordnerfrage; ohne Sperre landet der Export im Belegordner; ein 409 (Sonderkonto) kommt über `belegHerunterladen` an D's `catch` und zeigt den Servertext. → DB1, DB2, C7.
- **Ü3 — Speichern der SMTP-Karte.** Nach F schickt die SMTP-Karte nur ihre acht Schlüssel (F-E7); D's Regel „`DATEV_KONTENRAHMEN = null` ohne gespeicherten Rahmen ist ein No-op“ (D-E2) bleibt für offene alte Browser-Tabs und Fremd-Clients nötig. → FB5, DB3.

**D — DATEV-Export:** DB1–DB6 (Task 5, Review Focus); Kontierung der Echtdaten erst nach dem Deploy lesend (Manager-Abnahme D, Schritt 1).

**F — Firmendaten:** FB1–FB7 (Task 9); Vorrang der Belegvorlage am echten Beleg (R2); Belegvorlagen und Umgebung in Produktion (R1).

**O — Belegordner:**

1. **Freigabe-Prompt vor dem Abruf:** Mit gewähltem Ordner in einer neuen Sitzung fragt Chrome beim ersten Beleg nach dem Zugriff, **bevor** das PDF kommt. Bei der Mahnung kommt die Frage vor „… mit Gebühr erzeugen?“. → C9
2. **Toast-Text** genau „Gespeichert in Belege/<Belegart>/<JJJJ-MM>/<Datei>“. Ohne Ordner kein Toast. → C2, C12
3. **Ersetzen-Rückfrage** mit Ordnerpfad und Ausweichnamen. Exporte ohne Rückfrage. → C3, C7
4. **Karte „Belegordner“:** vier Zustände plus der Hinweis in Safari/Firefox. Die Zustände: kein Ordner, Zugriff erlaubt, Frage offen (mit Knopf „Zugriff erlauben“) und verweigert (mit dem Weg „alle Tabs schließen … Website-Einstellungen“, ohne Knopf). → C1, C9, C11, C11b, C13
5. **Safari/Firefox unverändert:** Download mit Belegnummer wie seit B7. → C13
6. **Rollen:** Nur Admin sieht die Einstellungen (O-E6, Offener Punkt 1). → C15
7. **Rückfall am Hallen-Tablet:** Die Packliste aus dem Tagesplan kommt dort an wie bisher. → C16

Getestet (automatisch): D — Kontentabelle, Rahmenprüfung inkl. Wechselsperre nach Export und SMTP-Rückschreiben, Kontierung beim Anlegen/Satzwechsel, Export spaltengenau in SKR03 und SKR04 (Bestand, Storno, Zahlungen, Rücklastschrift, Leergut), Abbruch bei fremdem Sonderkonto, Sperre und Einstellungs-Endpunkt mit Rechten; F — PDF bytegleich mit Vorlage, je Block einmal ohne Vorlage, Maskierung, Prüfung beim Speichern (IBAN/BIC/Zeilen/Länge), Grußformel; O — Ablagepfad (35 Fälle), Download-Funktion gegen Attrappen (8 Tests), Paket-3-Abnahmetests unverändert grün.

## File Structure

21 Dateien, davon 8 neu. Spalte „Task“ in der Nummerierung dieses Plans.

| Datei | Task | Verantwortung |
|---|---|---|
| `backend/app/services/kontenrahmen.py` | 1 | **neu** — `SACHKONTEN` je Rahmen, `kontenrahmen(db)`, `erloeskonto_fuer(satz, rahmen)`, `ist_standard_erloeskonto`, `sonderkonto_pruefen`, `export_sperre`, `schon_exportiert`, `wechsel_pruefen`, `BEBUCHTE_KONTEN` |
| `backend/app/services/settings_service.py` | 1, 7 | D: `DATEV_KONTENRAHMEN`, `DATEV_EXPORT_SPERRE` in `KNOWN_SETTINGS` hinter `MONATSRECHNUNG_AUTO`; F: neu `FIRMENDATEN_KEYS`, `FIRMENDATEN_MAX_LAENGE`, `firmendaten_pruefen` vor `get_setting`, fünf Labels |
| `backend/app/api/v1/admin.py` | 1, 7 | D: Import `kontenrahmen` unter der Importzeile aus `email_service`, Rahmenprüfung in `update_settings` vor dem Löschzweig; F: Importzeile aus `settings_service`, Aufruf `einstellung_pruefen(key, firmendaten_pruefen(key, raw_value))` und Kommentar darüber |
| `backend/app/services/invoice_service.py` | 2 | Import, `InvoiceService.add_line` (Konto des Rahmens) |
| `backend/app/schemas/invoice.py` | 2, 4 | `InvoiceLineCreate.buchungskonto` (Beschreibung); neu `DatevKonto`, `DatevEinstellungenResponse` |
| `backend/app/api/v1/invoices.py` | 2, 3, 4 | Importe, `update_invoice_line`, `export_datev`, `download_datev_export` (409), neu `GET /invoices/datev-export/einstellungen` |
| `backend/app/services/datev_service.py` | 3, 4 | eigene SKR03-Tabelle raus, `erloeskonto(line, rahmen)`, `erloesgruppen(invoice, rahmen)`, `DatevExportAbgelehnt`, `_rahmen`, `_sonderkonten_pruefen`, Sperre in `export_invoices_csv` |
| `backend/app/services/pdf_service.py` | 6 | neu `_auszeichnung_maskieren`; `render_company_header_block`, `render_company_footer_block` |
| `backend/app/services/belegversand.py` | 8 | neu `absendername`; `gruss` |
| `backend/tests/test_nachtrag_0910.py` | 1–4, 6–8, 12 | **neu** (Task 1 mit Kopf), Blöcke D, F, O angehängt — 65 Tests |
| `frontend/src/services/api.ts` | 5, 14 | D: `DatevEinstellungen` vor `AppSettingResponse`, `invoicesApi.datevEinstellungen`; O: `documentsApi` — drei Lader statt `download…Pdf` |
| `frontend/src/pages/Invoices.tsx` | 5, 15 | D: `DatevExportForm` (Anfang, Bereich ab `} catch (error) {` bis Feld „Von“, Knopf „Exportieren“); O: Importe, PDF-Knopf, Mahnung, `try`-Block in `handleExport` |
| `frontend/src/pages/Settings.tsx` | 5, 9, 13 | D: Import `invoicesApi`, `<DatevSettingsCard />`, neue Karte vor „Monatsrechnungen (B5)“; F: lucide-Import, Import `FirmendatenKarte`, alte Karte samt Zustand raus, `SMTP_KEYS`; O: Import `BelegordnerKarte`, `<BelegordnerKarte />` |
| `frontend/src/components/domain/FirmendatenKarte.tsx` | 9 | **neu** — Karte „Firmendaten“ (Server, Vorschlag aus dem Browser, Hinweis auf Belegvorlagen) |
| `frontend/src/services/belegpfad.ts` | 11 | **neu**, ohne Importe — Belegart, Monat, Ablagepfad |
| `frontend/tests/unit/belegpfad.check.ts` | 11 | **neu** — Node-Prüfung, 35 Fälle |
| `frontend/src/services/belegordner.ts` | 12 | **neu** — `belegHerunterladen` und Ordnerverwaltung, ohne React |
| `frontend/src/components/domain/BelegordnerKarte.tsx` | 13 | **neu** — Karte „Belegordner“ |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | 14 | `belegPdf`, `downloadInvoicePdf`, Knöpfe AB/LS-PDF/Packliste |
| `frontend/src/pages/Tagesplan.tsx` | 14 | `packlisteMutation` |
| `frontend/src/components/domain/SepaEinzugsliste.tsx` | 15 | `einreichen` |

**Überschneidungen** (Dateien, die mehr als ein Abschnitt ändert; im Gesamtlauf D → F → O jeder Anker genau einmal gefunden):
1. **`backend/tests/test_nachtrag_0910.py`** (D, F, O): Task 1 legt an, alle anderen hängen an. Modulweite Namen sind disjunkt (Präfixe `_d_`/`_D_`, `_f_`/`_F_`, `_o_`; Importe je Block, mehrfache Importe sind harmlos); gesamt `65 passed`.
2. **`frontend/src/pages/Settings.tsx`** (D, F, O): D ändert die Importzeile aus `../services/api`, die Kartenliste hinter `<MonatsrechnungSettingsCard />` und fügt eine Karte vor dem Kommentar „Monatsrechnungen (B5)“ ein; F ersetzt die lucide-Importzeile, fügt unter der `SepaEinstellungenKarte`-Importzeile ein, entfernt Zustand, Speicherfunktion und Karte „Company Profile“ und ändert `SmtpSettingsCard`; O ersetzt die `SepaEinstellungenKarte`-Importzeile durch sich plus Belegordner-Import und die Zeile `<SepaEinstellungenKarte />` durch sich plus Karte. Danach Importe in der Folge SEPA, Belegordner, Firmendaten. Der Hash von `Settings.tsx` gilt nur in der Vorbereitung (nach Task 5 weicht er ab — erwartet).
3. **`backend/app/api/v1/admin.py`** (D, F): D ankert an der Importzeile aus `email_service` und am Kommentar `# Empty/None löscht (lässt env-Fallback durchscheinen)`; F an der Importzeile aus `settings_service`, an `raw_value = einstellung_pruefen(key, raw_value)` und am Kommentar darüber. Die Zeile `from app.services.sepa_service import einstellung_pruefen` ändert keiner.
4. **`backend/app/services/settings_service.py`** (D, F): D ersetzt den letzten Eintrag `MONATSRECHNUNG_AUTO` samt schließender Klammer; F fügt vor `def get_setting` ein und ändert die Labels von fünf Firmendaten-Schlüsseln — verschiedene Zeilen.
5. **`frontend/src/pages/Invoices.tsx`** (D, O): Beide Anker in `DatevExportForm` enthalten die Zeile `    } catch (error) {` — D's Block beginnt dort, O's `try`-Block endet dort. D lässt die Zeile stehen, deshalb findet O seinen Anker nach D genau einmal (gemessen). Die übrigen Anker (D: Funktionsanfang, Knopf „Exportieren“; O: Importe, PDF-Knopf, Mahnung) liegen getrennt.
6. **`frontend/src/services/api.ts`** (D, O): D in `invoicesApi` (`// DATEV`) und vor `export interface AppSettingResponse`; O nur in `documentsApi`.

**Nicht geändert (geprüft):** `tenancy.py` (keine Migration), Modelle, `main.py` (Router und Rechte), `Layout.tsx` (Navigation; „Einstellungen“ nur `ADMIN`), `types/index.ts`, alle bestehenden Tests (`tests/test_datev_export.py`, `tests/test_gernot_261008.py`, `tests/test_gernot_261008_paket3.py` bleiben unverändert grün), `cancel_invoice` (Storno-Spiegel), `Invoice.buchungskonto` (Kopf), `belegversand.firmenname`/`firmenzusatz`, `document_templates`.
**Von O nicht geändert (geprüft):** das Backend außer der Testdatei; `frontend/src/services/dateiname.ts` (B7); `print.ts` (Druck, Etiketten); `_openPdfFromResponse` (Warenfluss, Inventur); `attachmentsApi.download`; `ExcelImport.tsx`, `ChargenGridModal.tsx`, `Dienstplan.tsx`, `DocumentTemplates.tsx`, `Production.tsx`; `backend/tests/test_gernot_261008_paket3.py` (seine Abnahmetests laden `belegordner.ts` mit und bleiben grün).

## Vorbereitung (vor Task 1)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis>` in den Bericht schreiben (erwartet `df84f7b…`; eine Shell-Variable reicht nicht, jeder Befehl läuft in einer eigenen Shell).
- [ ] **Arbeitsbaum:** `git status --porcelain` → nur die in „Global Constraints“ als sauber genannten `??`-Einträge. Jede `M`-, `A`- oder `D`-Zeile: stoppen und melden, nichts committen oder zurücksetzen.
- [ ] **Ausgangsstand D** (Kommentar = erwartete Ausgabe):

```bash
grep -c '^def erloeskonto_fuer(tax_rate: TaxRate) -> str:' backend/app/services/datev_service.py          # 1
grep -c '^def erloesgruppen(invoice: Invoice) -> list\[dict\]:' backend/app/services/datev_service.py     # 1
grep -c '^from app.services.datev_service import erloeskonto_fuer$' backend/app/services/invoice_service.py   # 1
grep -c '^from app.services.datev_service import DatevService, erloeskonto_fuer, ist_standard_erloeskonto$' backend/app/api/v1/invoices.py   # 1
grep -c '^from app.services.email_service import send_email, EmailNotConfiguredError$' backend/app/api/v1/admin.py   # 1
grep -c '        # Empty/None löscht (lässt env-Fallback durchscheinen)' backend/app/api/v1/admin.py   # 1
grep -c '"MONATSRECHNUNG_AUTO":' backend/app/services/settings_service.py   # 1
grep -c '^function DatevExportForm' frontend/src/pages/Invoices.tsx   # 1
test -e backend/app/services/kontenrahmen.py && echo vorhanden || echo fehlt   # fehlt
grep -rn 'DATEV_KONTENRAHMEN\|DATEV_EXPORT_SPERRE\|datevEinstellungen' backend/app frontend/src | wc -l   # 0
cat backend/tests/test_nachtrag_0910.py 2>/dev/null | grep -c '^class TestD[A-Z]'   # 0 (Datei fehlt oder noch ohne D-Klassen)
```

- [ ] **Ausgangsstand F:**

```bash
grep -c '^def render_company_header_block(' backend/app/services/pdf_service.py                           # 1
grep -c '^    name = settings.get("COMPANY_NAME") or "Minga Greens"$' backend/app/services/pdf_service.py   # 1
grep -c '^    parts: list\[str\] = \[\]$' backend/app/services/pdf_service.py                               # 1
grep -c '^def get_setting(db: Session, key: str, env_fallback: bool = True) -> Optional\[str\]:$' backend/app/services/settings_service.py   # 1
grep -c '"label": "Firmenname (Briefkopf)"' backend/app/services/settings_service.py                       # 1
grep -c '^from app.services.settings_service import KNOWN_SETTINGS, get_setting, set_setting$' backend/app/api/v1/admin.py   # 1
grep -c '^            raw_value = einstellung_pruefen(key, raw_value)$' backend/app/api/v1/admin.py          # 1
grep -c '^def gruss(db: Session) -> str:$' backend/app/services/belegversand.py                            # 1
grep -c "localStorage.getItem('minga_settings_company')" frontend/src/pages/Settings.tsx                   # 1
test -e frontend/src/components/domain/FirmendatenKarte.tsx && echo vorhanden || echo fehlt              # fehlt
grep -sc '^class TestF[0-9]' backend/tests/test_nachtrag_0910.py; true                                    # 0 oder keine Ausgabe
git hash-object frontend/src/pages/Settings.tsx    # 9dc4b96a097f0192a4a6b89bc6fff74a1149b257 (df84f7b)
```

Weicht nur der Hash ab: kein Stopp; dann die `Settings.tsx`-Anker von Task 5 (D.5), Task 9 (F.4) und Task 13 (O.3) beim jeweiligen Task einzeln prüfen, fehlt einer: Stoppregel 1. Nach Task 5 weicht der Hash ohnehin ab — erwartet, er wird danach nicht mehr geprüft.

- [ ] **Ausgangsstand O:**

```bash
grep -c "export function dateinameAusHeader" frontend/src/services/dateiname.ts                        # 1 (B7)
grep -cF 'expose_headers=["Content-Disposition"]' backend/app/main.py                                 # 1 (B7)
grep -cF 'downloadConfirmationPdf: (conf: OrderConfirmation) =>' frontend/src/services/api.ts         # 1
grep -rn "downloadConfirmationPdf\|downloadDeliveryNotePdf\|downloadPackingListPdf" frontend/src | wc -l  # 7
grep -c "ladePdfHerunter" frontend/src/pages/Invoices.tsx                                             # 2
grep -cF 'a.download = `Lastschrift-Einreichung_${heute}.csv`;' frontend/src/components/domain/SepaEinzugsliste.tsx  # 1
grep -cF '<SepaEinstellungenKarte />' frontend/src/pages/Settings.tsx                                 # 1
grep -rn "belegordner\|belegpfad\|showDirectoryPicker" frontend/src | wc -l                           # 0
if [ -f backend/tests/test_nachtrag_0910.py ]; then grep -c "^class TestO" backend/tests/test_nachtrag_0910.py; else echo fehlt; fi   # 0 oder „fehlt“
node --version                                                                                         # v23.6 oder neuer
```

- [ ] **Baseline:** Block aus „Global Constraints“ (Baseline-Namen) ausführen → `15`. Dann Prozedur V auf der Basis → `14 failed, 1644 passed, 2 skipped, 1 error`, Abgleich leer. Die Summenzeile gehört als `<B>` in den Bericht. Abweichung bei den Namen: stoppen und melden.

---

## Abschnitt D — DATEV-Export im Kontenrahmen des Mandanten (SKR03 | SKR04; MingaGreens SKR04) — Tasks 1–5

**Goal:** Gernot (09.10.2026): MingaGreens arbeitet mit DATEV Mittelstand Faktura mit Rechnungswesen und DATEV Unternehmen online im **SKR04**. Der DATEV-Export kennt nur SKR03. Danach gilt je Mandant die Einstellung `DATEV_KONTENRAHMEN` (`SKR03` | `SKR04`, ohne Eintrag `SKR03` = Bestand) über die Admin-Einstellungen mit Prüfung, und **eine** Kontentabelle je Rahmen enthält jedes Sachkonto, das der Export bebucht (`backend/app/services/kontenrahmen.py`). Festgeschriebene Rechnungen werden **nicht** umgeschrieben (GoBD): der Export bildet die Standard-Erlöskonten beim Export aus Steuersatz und Rahmen ab, ein Sonderkonto bleibt. Bis der (neue) Steuerberater die Kontierung bestätigt, bleibt der Export für `minga` gesperrt (`DATEV_EXPORT_SPERRE`, Hinweis im Dialog).

**Architecture:** Neues Modul `app.services.kontenrahmen` (Tabelle `SACHKONTEN`, `kontenrahmen(db)`, `erloeskonto_fuer(satz, rahmen)`, `ist_standard_erloeskonto`, `sonderkonto_pruefen`, `export_sperre`, `wechsel_pruefen`). `datev_service` verliert seine eigene SKR03-Tabelle und importiert alles von dort (die Namen bleiben über `datev_service` importierbar). `InvoiceService.add_line` und `update_invoice_line` setzen das Konto des Rahmens; `cancel_invoice` (Storno-Spiegel) bleibt unverändert. `PATCH /admin/settings` prüft den Rahmen vor dem Löschzweig. Neuer Endpunkt `GET /invoices/datev-export/einstellungen` für Dialog und Einstellungskarte. Keine neue Spalte, keine Migration (`app_settings` besteht).

**Tech Stack:** FastAPI + SQLAlchemy 2.0, SQLite je Mandant, Pydantic v2, React 18 + TypeScript, TanStack Query 5.

**Ausgangsstand:** `main` @ `df84f7b` (live: Pakete 1, 2, 2.1, 3, B6, Benutzerverwaltung, Sicherheitsfixes). Wenn andere Abschnitte des Nachtrags vorher laufen, gelten die Anker unverändert, solange sie die zitierten Blöcke nicht anfassen (siehe Abhängigkeiten).

### Abhängigkeiten

- **Fachlich:** keine zu anderen Abschnitten. Setzt nur `main` voraus: Paket 1 S4/S5 (Export je Satz und Erlöskonto, `erloeskonto_fuer`/`ist_standard_erloeskonto`, Satzwechsel im Entwurf), Paket 3 Q6 (Leergutbelege) und B10 (Rücklastschrift als negative Lastschriftzahlung).
- **Gemeinsame Dateien** (berührt ein früherer Abschnitt einen der zitierten Blöcke, gilt Stoppregel D1): `backend/tests/test_nachtrag_0910.py` (im Gesamtplan legt Task 1 sie an; sonst hängt D nur an), `backend/app/api/v1/invoices.py` (`update_invoice_line`, DATEV-Endpunkte, Importe), `backend/app/services/invoice_service.py` (`add_line`, Import), `backend/app/schemas/invoice.py` (`InvoiceLineCreate.buchungskonto`, `DatevExportResponse`), `backend/app/services/settings_service.py` (`KNOWN_SETTINGS`), `backend/app/api/v1/admin.py` (`update_settings`), `frontend/src/pages/Invoices.tsx` (`DatevExportForm`), `frontend/src/pages/Settings.tsx` (Kartenliste), `frontend/src/services/api.ts` (`invoicesApi`, vor `AppSettingResponse`).
- **Gegen F und O geprüft** (Arbeitsstände beim Schreiben, lesend): jeder Anker von D auf dem Ausgangsstand kommt in `/tmp/n0910-kopie-fr` (F.1–F.3, F.4 im Arbeitsbaum) und `/tmp/n0910-kopie-o2` (O.1–O.5) genau einmal vor. D ändert keinen Anker von F oder O: F ändert in `admin.py` die Importzeile aus `settings_service` und den Aufruf `einstellung_pruefen` in `update_settings`, die Importzeilen aus `email_service` und `sepa_service` bleiben (D importiert unter der Zeile aus `email_service`, die weder F noch O ändern, und prüft vor dem Löschzweig), F fügt vor `def get_setting` ein (D innerhalb von `KNOWN_SETTINGS`), F baut Firmendaten- und SMTP-Karte um (D fügt eine eigene Karte vor „Monatsrechnungen“ ein); O ersetzt den `try`-Block in `handleExport` bis einschließlich `} catch (error) {` (D ändert die Zeile danach und den Anfang von `DatevExportForm`). Reihenfolge D, F, O beliebig; dieser Plan nimmt D → F → O (gemessen, „Prüfstand (Gesamtlauf)“ oben).
- **Betrieb:** Bestätigung der Kontierung durch den Steuerberater (Offene Punkte D 1–5). Der EXTF-Kopf bleibt B9-Rest (Paket 4) und ist nicht Teil von D.
- **Kein Deploy-Risiko für Bestand:** ohne Eintrag gilt SKR03, alle Konten wie heute (Regressionstests `TestDExportSkr03`, Paket-1-Tests `TestDatev*`, `tests/test_datev_export.py` unverändert grün).

### Ist-Stand (am Code geprüft, `main` @ `df84f7b`)

Was der Export heute bucht (`DatevService.export_invoices_csv`, Kontierungskommentar in `datev_service.py`):

| Fall | Konto | Gegenkonto | S/H | Quelle |
|---|---|---|---|---|
| Rechnung, je (Satz, Erlöskonto) eine Zeile | Debitor (`customer.datev_account`, sonst `10000`) | 8300 (7 %), 8400 (19 %), 8100 (steuerfrei) oder Sonderkonto der Position | S (negativer Saldo H) | `erloesgruppen`, `erloeskonto`, `_richtung` |
| Stornorechnung / Gutschrift | Debitor | Konten wie Original (Spiegel) | H (Storno zu Leergut-Minderung S) | `cancel_invoice`, `_richtung` |
| Leergutbeleg (Paket 3, Q6) | Debitor | Erlöskonto zum Satz des Pfandprodukts (19 % → 8400); **kein eigenes Pfand-/Leergutkonto** | nach Saldo | `leergut_service` → `add_line(tax_rate=produkt.tax_rate)` |
| Zahlung | Bank 1200, **nur** `BAR` → Kasse 1000; Überweisung, EC, Kreditkarte, PayPal, Lastschrift → Bank | Debitor | S | Zahlungsteil in `export_invoices_csv` |
| Rücklastschrift (B10) | Bank 1200 | Debitor | H (negative `LASTSCHRIFT`-Zahlung) | `sepa_service.ruecklastschrift` |
| Forderungen 1400 | **nicht bebucht** — DATEV führt das Sammelkonto aus den Debitoren | | | Kommentar „Keine Zeile auf 1400“ |

Steuerfälle: `TaxRate` kennt genau drei Werte — `STANDARD` 19 %, `REDUZIERT` 7 %, `STEUERFREI` 0 %. Es gibt **keinen** eigenen Fall für innergemeinschaftliche Lieferung, Ausfuhr oder Reverse Charge; das PDF druckt bei `STEUERFREI` den Vermerk „Steuerschuldnerschaft des Leistungsempfängers (§ 13b UStG)“ (`pdf_service`, Schalter `reverse_charge`), DATEV bekäme 8100 („Steuerfreie Umsätze § 4 Nr. 8 ff.“). → Offener Punkt 2, keine Logikänderung in D.

Wo `buchungskonto` heute gesetzt wird:

1. **Anlage einer Rechnungsposition** — `InvoiceService.add_line`: leer → `erloeskonto_fuer(tax_rate)` (SKR03), ausdrücklich gesetzt (`InvoiceLineCreate.buchungskonto`) → bleibt. Alle Wege laufen hierüber: Rechnung von Hand (`POST /invoices`, `POST /invoices/{id}/lines`), `create_invoice_from_order`, Sammelrechnung und Monatsentwürfe (`invoices.py`, Kandidatenzeilen), Leergutabrechnung.
2. **Satzwechsel im Entwurf** — `invoices.update_invoice_line`: Standardkonto zieht mit dem Satz mit, Sonderkonto bleibt. `InvoiceLineUpdate` hat kein Feld `buchungskonto`.
3. **Storno-Spiegel** — `InvoiceService.cancel_invoice` kopiert `buchungskonto` jeder Position 1:1 (bewusst nicht über `add_line`).
4. **Kopf** `Invoice.buchungskonto` — wird gespeichert und beim Storno kopiert, der Export liest ihn seit Paket 1 nicht (Test `test_kopfkonto_ueberschreibt_die_konten_je_satz_nicht`).
5. **Export** — `erloeskonto(line)`: Standardkonto → aus dem Satz neu abgeleitet, Sonderkonto → unverändert. Bestand in Produktion nicht gemessen (Abfrage unter „Nach dem Deploy“, Schritt 1): erwartet nur Standardkonten 8300/8400, weil alle Wege über `add_line` ohne Sonderkonto laufen; Sonderkonten kommen nur in Tests vor (8338, 8301).

### Entscheidungen (Manager, im Plan getroffen)

- **D-E1 — Abbilden beim Export, nicht Umschreiben.** Der Export leitet das Erlöskonto jeder Position mit Standardkonto (8300/8400/8100 **oder** 4300/4400/4100) beim Export aus Steuersatz und aktuellem Rahmen ab; ein Sonderkonto bleibt. Begründung: (a) Die festgeschriebenen Rechnungen in `minga` tragen über `add_line` die SKR03-Standardkonten 8300/8400. Würde das Konto nur beim Anlegen nach Rahmen gesetzt, müssten diese Positionen nachträglich geändert werden (Unveränderbarkeit nach GoBD / § 146 Abs. 4 AO) oder sie gingen mit SKR03-Konten in einen SKR04-Bestand. (b) Der Storno-Spiegel kopiert die Konten des Originals; mit der Abbildung beim Export landen Original und Stornorechnung immer auf demselben Konto, auch wenn das Original aus der SKR03-Zeit stammt und nach dem Wechsel storniert wird. (c) So arbeitet der Export schon seit Paket 1 für den Satzwechsel. **Zusätzlich** (D.2) setzen `add_line` und der Satzwechsel das Konto des aktuellen Rahmens, damit neue Positionen anzeigen, was exportiert wird; gespeichert bleibt es ein Vorschlag, maßgeblich ist der Export.
- **D-E2 — Rahmenwechsel nur vor dem ersten Export.** Weil der Export beim Export ableitet, würde ein Wechsel einen Wiederholungsexport (`erneut_exportieren`) schon exportierter Belege umkontieren. `PATCH /admin/settings` lehnt einen Wechsel ab, sobald eine Rechnung oder Zahlung `datev_exported` trägt (422). Einen gespeicherten Rahmen leeren wäre ein stiller Wechsel auf SKR03 und wird ebenfalls abgelehnt; **ohne** gespeicherten Rahmen ist `null`/`""` ein No-op — die SMTP-Karte schickt beim Speichern jede bekannte Einstellung zurück, ungesetzte als `null` (Befund aus Abschnitt F, Nebenbefund 2; Test `test_smtp_karte_speichert_weiter`). Für `minga` ist noch nichts exportiert (Spec, Sofortmaßnahme 1) — SKR04 lässt sich setzen.
- **D-E3 — Sonderkonto aus dem anderen Rahmen wird nie still exportiert.** Regel: Klasse 8 ist im SKR04 nicht belegt, Klasse 4 im SKR03 sind Aufwendungen — ein vierstelliges Sonderkonto dieser Klasse ist im jeweiligen Rahmen nie ein Erlöskonto. Beim Anlegen 400, im Export 409 **vor** der ersten Zeile (nichts markiert), mit Rechnungsnummer, Position und Konto. Keine weitere Plausibilisierung (Sache des Steuerberaters).
- **D-E4 — Ein mitgeschicktes Standardkonto folgt Satz und Rahmen** (z. B. `8400` bei 7 % → 8300 bzw. 4300). Betrifft nur Fremd-Clients; der Export rechnete schon bisher so.
- **D-E5 — Sperre als Einstellung `DATEV_EXPORT_SPERRE` (Text = Grund), nicht als Default.** Gesetzt: Export 409 „DATEV-Export gesperrt: <Grund>“, nichts markiert; Dialog und Einstellungskarte zeigen den Grund, der Knopf „Exportieren“ ist gesperrt. Kein Default-„gesperrt“, weil dann Demo, Testmandant und die Bestandstests (Paket 1 S4, `test_datev_export.py`) brechen; für `minga` setzt der Manager die Sperre **vor** dem Deploy (siehe „Nach dem Deploy“). Keine Oberfläche zum Aufheben: Freigabe nach Bestätigung des Steuerberaters über den Betreuer.
- **D-E6 — Beide Schlüssel ohne Rückfall auf Umgebungsvariablen** (eine Container-Variable gälte für alle Mandanten; Muster Gläubiger-ID, Paket 3).
- **D-E7 — SKR04-Gegenstück zu 8100 ist 4100**, 1:1 übertragen. Ob `STEUERFREI` überhaupt dorthin gehört (igL 4125, Ausfuhr 4120, § 13b 4337), entscheidet der Steuerberater (Offener Punkt 2).
- **D-E8 — Zahlungswege wie bisher:** nur bar → Kasse (SKR04 1600), alles andere → Bank (SKR04 1800). Forderungen (SKR04 1200) stehen der Vollständigkeit halber in der Tabelle und werden nicht bebucht. Debitoren (10000 ff.) hängen nicht am Rahmen.
- **D-E9 — Einstellungs-Endpunkt unter `/invoices`:** den Export bedient auch die Buchhaltung (`accounting`), `/admin/settings` ist nur für `admin`.

### Prüfstand (alles in Kopien unter `/tmp`, Repo unverändert)

- **Baseline** `main` @ `df84f7b`, Kopie `/tmp/n0910-kopie-d` (`git archive`): Prozedur V → `14 failed, 1644 passed, 2 skipped, 1 error`, Fehlernamen = Liste in „Global Constraints“.
- **Entwicklung** in `/tmp/n0910-kopie-d`, Task für Task (Rot vor jeder Implementierung, Vollauf nach jedem Task, Baseline-Namen). `ruff --select F401,F811,F821,F823` über die geänderten Dateien: dieselben 13 Altbefunde wie auf `df84f7b` (alle in `invoices.py`/`invoice_service.py`), keiner neu. Build `✓ built`, danach nichts Neueres im über den Symlink geteilten `node_modules`.
- **Revision nach Abgleich mit Abschnitt F:** Die SMTP-Karte schickt beim Speichern jede bekannte Einstellung zurück, ungesetzte als `null` (F, Nebenbefund 2). Die erste Fassung von D lehnte `null` für `DATEV_KONTENRAHMEN` immer ab — „Speichern“ der SMTP-Karte wäre in jedem Mandanten ohne Rahmen mit 422 gescheitert. Jetzt: ohne gespeicherten Rahmen No-op, mit gespeichertem 422 (D-E2), Test `test_smtp_karte_speichert_weiter`. Der Import in `admin.py` ankert an der Importzeile aus `email_service`, die weder F noch O ändern (die Zeile aus `sepa_service` lässt F stehen; die frühere Begründung „F entfernt sie“ war überholt).
- **Nachspiel aus dem Plantext** auf einer frischen Kopie (`/tmp/n0910-kopie-d-nachspiel2`, `git archive df84f7b`): ein Skript hat genau die Test- und Code-Blöcke dieses Abschnitts mechanisch mit ihren Ankern angewendet (jeder zitierte Block genau einmal gefunden). D.1 `14 failed` → `14 passed`, Vollauf `1658`; D.2 `6 failed, 2 passed` → `8 passed`, Vollauf `1666`; D.3 `6 failed, 3 passed` → `9 passed`, Vollauf `1675`; D.4 `5 failed, 1 passed` → `6 passed`, Vollauf `1681`; alle Vollläufe `14 failed, … 2 skipped, 1 error` mit Baseline-Namen. D.5 `tsc` 4 Fehler → sauber, Build `✓ built`. `ruff --select F821,F823` (Befehl unten): keine Ausgabe. Diff genau die 11 Dateien aus den Files-Listen.
- **Bestandstests** des Exports unverändert grün: `tests/test_datev_export.py` und `tests/test_gernot_261008.py` zusammen `149 passed` (darin `TestDatevKontierung`, `TestDatevGutschrift`, `TestDatevBelegauswahl`, `TestDatevWiederholungsexport`, `TestS3Storno…`, `TestS5…` mit Satzwechsel und Sonderkonto 8338).
- **Gegenprobe der Anker** gegen die Arbeitsstände von F und O (siehe Abhängigkeiten): alle Anker auf dem Ausgangsstand genau einmal vorhanden. **Reihenfolge ausgeführt** (Review 09.10.): D auf Kopien der Nachspiel-Stände von F (`/tmp/n0910-kopie-fu` → `/tmp/n0910-kopie-drev-f`) und O (`/tmp/n0910-kopie-o4` → `/tmp/n0910-kopie-drev-o`) angewendet, jeder D-Anker genau einmal; Prozedur V D+F `1701 passed`, D+O `1689 passed`, beide nur Baseline-Namen; `tsc` sauber, Build `✓ built`. Mit O reicht `belegHerunterladen` Fehler aus `laden()` an den Aufrufer weiter, der 409-Servertext erreicht also D's `catch` mit `getErrorMessage`.
- **Review 09.10. (Nachspiel `/tmp/n0910-kopie-drev`, eigenes Skript, alle 41 zitierten Blöcke genau einmal):** Rot/Grün, Vollläufe (1658/1666/1675/1681, auch nach D.5 `1681`), `ruff`, `tsc`, Build, Diff (11 Dateien) wie oben bestätigt. Eingearbeitet: (1) **D.1 Step 2** nannte `test_skr04_setzen_schreibweise_egal` als `AssertionError` — der Test importiert das Modul in der ersten Zeile und scheitert mit `ModuleNotFoundError`; der dritte `AssertionError` kommt von `test_unbekannter_rahmen_422` (PATCH `SKR05` → 400). Nachgespielt in `/tmp/n0910-kopie-dred` (nur Testblock D.1 auf `df84f7b`): genau diese Zuordnung. (2) Karte „DATEV-Export“ volle Breite (`lg:col-span-2`, Knöpfe `max-w-md`), sonst leere Zelle neben ihr im Raster. (3) Anker-Begründung in `admin.py` vereinheitlicht (Zeile aus `email_service`; F lässt die Zeile aus `sepa_service` stehen). (4) „Nach dem Deploy“: `SKR04` exakt schreiben und im Skript nachprüfen (Schritt 2); Probeexport in `abnahme` mit Backup davor und Rückspielen danach (Schritt 4).
- **Nicht gemessen:** Oberfläche im Browser (keine Frontend-Tests; Review Focus D.5), Produktionsdaten (lesende Abfragen unter „Nach dem Deploy“), Import der Datei in DATEV (Offener Punkt 5).

### Task 1 (D.1): Kontentabelle je Rahmen und Einstellung `DATEV_KONTENRAHMEN`

**Files:**
- Create: `backend/app/services/kontenrahmen.py`
- Modify: `backend/app/services/settings_service.py` (`KNOWN_SETTINGS`)
- Modify: `backend/app/api/v1/admin.py` (Import, `update_settings`)
- Create/Modify: `backend/tests/test_nachtrag_0910.py` (Kopf falls neu, Block D.1 anhängen)

**Interfaces:**
- Produces (`app.services.kontenrahmen`):
  - Konstanten `EINSTELLUNG = "DATEV_KONTENRAHMEN"`, `SPERRE = "DATEV_EXPORT_SPERRE"`, `STANDARD_RAHMEN = "SKR03"`; `SACHKONTEN: dict[str, dict[str, str]]` mit den Schlüsseln `erloes_7`, `erloes_19`, `erloes_steuerfrei`, `forderungen`, `bank`, `kasse` je Rahmen (`SKR03` = `STANDARD_ACCOUNTS` unverändert; `SKR04` = 4300/4400/4100/1200/1800/1600); `STANDARD_ERLOESKONTEN: frozenset[str]` (die sechs Standard-Erlöskonten beider Rahmen); `BEBUCHTE_KONTEN: tuple[tuple[str, str], ...]` (Schlüssel, Bezeichnung) für die Anzeige.
  - `rahmen_pruefen(wert) -> str` (normalisiert, sonst `ValueError("SKR03 oder SKR04 erwartet")`), `kontenrahmen(db) -> str` (ohne Eintrag `SKR03`, ohne Umgebungs-Rückfall), `sachkonto(rahmen, schluessel) -> str`, `erloeskonto_fuer(tax_rate, rahmen) -> str` (**`rahmen` ist Pflicht**), `ist_standard_erloeskonto(konto) -> bool` (leer oder Standardkonto **irgendeines** Rahmens), `sonderkonto_pruefen(konto, rahmen) -> None` (`ValueError("Erlöskonto 8338 passt nicht zum Kontenrahmen SKR04 (Kontenklasse 8 ist dort kein Erlöskonto)")`), `export_sperre(db) -> Optional[str]`, `schon_exportiert(db) -> bool`, `wechsel_pruefen(db, wert) -> Optional[str]` (None = leer ohne gespeicherten Rahmen, nichts zu tun).
  - `PATCH /admin/settings` mit `DATEV_KONTENRAHMEN`: 200 und gespeichert `SKR03`/`SKR04` (Schreibweise egal); 422 `"DATEV-Kontenrahmen (SKR03 | SKR04): SKR03 oder SKR04 erwartet"` für Unbekanntes; `""`/`null` ohne gespeicherten Rahmen 200 ohne Wirkung, mit gespeichertem Rahmen 422 `"DATEV-Kontenrahmen (SKR03 | SKR04): leeren nicht möglich — SKR03 oder SKR04 angeben"`; 422 `"DATEV-Kontenrahmen (SKR03 | SKR04): nach dem ersten DATEV-Export nicht mehr änderbar — Wechsel des Kontenrahmens mit dem Steuerberater klären"` für einen Wechsel nach dem ersten Export (derselbe Wert bleibt 200). `DATEV_EXPORT_SPERRE`: freier Text, leer löscht.
  - Test-Helfer `_d_rahmen`, `_d_setze_rahmen`, `_d_einstellung`, `_d_kunde`, `_d_rechnung`, `_d_positionen`, `_d_als_exportiert`, Konstanten `_D_KOPF`, `_D_GEMISCHT` (Tasks D.2–D.4 nutzen sie).
- Consumes: `settings_service.get_setting(db, key, env_fallback=False)`, `models.invoice.STANDARD_ACCOUNTS`, `Invoice.datev_exported`, `Payment.datev_exported`.

**Review Focus (D.1):** Prüfung vor dem Löschzweig in `update_settings` (sonst wäre `""` ein stiller Wechsel); die SMTP-Karte (schickt alle Schlüssel zurück) speichert weiter; Wechselsperre zählt Rechnungen **und** Zahlungen; kein Umgebungs-Rückfall.

- [ ] **Step 1: Testblock anhängen.** `backend/tests/test_nachtrag_0910.py` fehlt auf dem Ausgangsstand (Vorbereitung) — Task 1 legt die gemeinsame Datei aller Abschnitte an. Falls sie fehlt, zuerst mit genau diesem Kopf anlegen:

```python
"""Nachtrag 09.10.2026 — Gernots Feedback vom 09.10. (Word-Kommentare und
Excel-Sammelrechnung).

Gemeinsame Testdatei aller Abschnitte. Helfer und Klassen tragen ein
Abschnitts-Präfix (_d_/TestD für Abschnitt D usw.): ein gleichnamiger Helfer
würde still ersetzt. Jeder Abschnitt bringt seine Importe selbst mit.
"""
```

Dann diesen Block **ans Dateiende** anhängen (beginnt mit einer Leerzeile):

```python


# ============================================================
# D — DATEV-Export im Kontenrahmen des Mandanten (SKR03 | SKR04)
#
# Gernot (09.10.2026): MingaGreens bucht mit DATEV Mittelstand Faktura mit
# Rechnungswesen und DATEV Unternehmen online im SKR04. Der Export kannte nur
# SKR03. Einstellung DATEV_KONTENRAHMEN (ohne Eintrag SKR03), eine
# Kontentabelle je Rahmen (app.services.kontenrahmen). Festgeschriebene
# Rechnungen werden nie umgeschrieben: der Export bildet die Standard-
# Erlöskonten aus Steuersatz und Rahmen ab, ein Sonderkonto bleibt.
# Kontierung vom Steuerberater zu bestätigen.
# ============================================================
import csv
import io
import uuid
from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal

_D_KOPF = [
    "Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz",
    "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum",
    "Belegfeld 1", "Belegfeld 2", "Buchungstext",
]

#: Ware zu 7 %, Pfandkiste zu 19 % (wie RE-00002):
#: 10 × 2,50 = 25,00 + 1,75 USt = 26,75 | 2 × 3,00 = 6,00 + 1,14 USt = 7,14
_D_GEMISCHT = [
    ("Erbsen-Schale", 10, "2.50", "REDUZIERT"),
    ("Pfandkiste 6er", 2, "3.00", "STANDARD"),
]


def _d_rahmen(client, wert):
    return client.patch("/api/v1/admin/settings", json={"DATEV_KONTENRAHMEN": wert})


def _d_setze_rahmen(client, wert):
    r = _d_rahmen(client, wert)
    assert r.status_code == 200, r.text


def _d_einstellung(client, key):
    r = client.get("/api/v1/admin/settings")
    assert r.status_code == 200, r.text
    return next(s for s in r.json() if s["key"] == key)


def _d_kunde(client, name="Ökoring Testkunde", konto="10008"):
    r = client.post("/api/v1/sales/customers",
                    json={"name": name, "typ": "HANDEL", "datev_account": konto})
    assert r.status_code == 201, r.text
    return r.json()


def _d_rechnung(client, kunde, positionen, finalisieren=True):
    """positionen: (Beschreibung, Menge, Preis, Satz[, Sonderkonto])."""
    r = client.post("/api/v1/invoices", json={
        "customer_id": kunde["id"], "invoice_date": date.today().isoformat(),
    })
    assert r.status_code == 201, r.text
    rechnung = r.json()
    for beschreibung, menge, preis, satz, *sonderkonto in positionen:
        zeile = {"description": beschreibung, "quantity": menge, "unit": "STK",
                 "unit_price": preis, "tax_rate": satz}
        if sonderkonto:
            zeile["buchungskonto"] = sonderkonto[0]
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json=zeile)
        assert r.status_code == 201, r.text
    if finalisieren:
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text
        rechnung = r.json()
    return rechnung


def _d_positionen(client, rechnung):
    r = client.get(f"/api/v1/invoices/{rechnung['id']}")
    assert r.status_code == 200, r.text
    return sorted(r.json()["lines"], key=lambda l: l["position"])


def _d_als_exportiert(rechnung_id):
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        db.get(Invoice, uuid.UUID(rechnung_id)).datev_exported = True
        db.commit()


class TestDKontentabelle:
    """Eine Tabelle je Rahmen, SKR03 = Bestand."""

    def test_skr03_ist_der_bisherige_bestand(self):
        from app.models.invoice import STANDARD_ACCOUNTS
        from app.services.kontenrahmen import SACHKONTEN
        assert SACHKONTEN["SKR03"] == STANDARD_ACCOUNTS == {
            "erloes_7": "8300", "erloes_19": "8400", "erloes_steuerfrei": "8100",
            "forderungen": "1400", "bank": "1200", "kasse": "1000",
        }

    def test_skr04_konten(self):
        from app.services.kontenrahmen import SACHKONTEN
        assert SACHKONTEN["SKR04"] == {
            "erloes_7": "4300", "erloes_19": "4400", "erloes_steuerfrei": "4100",
            "forderungen": "1200", "bank": "1800", "kasse": "1600",
        }

    def test_erloeskonto_je_satz_und_rahmen(self):
        from app.models.enums import TaxRate
        from app.services.kontenrahmen import erloeskonto_fuer
        saetze = (TaxRate.REDUZIERT, TaxRate.STANDARD, TaxRate.STEUERFREI)
        assert [erloeskonto_fuer(s, "SKR03") for s in saetze] == ["8300", "8400", "8100"]
        assert [erloeskonto_fuer(s, "SKR04") for s in saetze] == ["4300", "4400", "4100"]

    def test_standardkonten_beider_rahmen_folgen_dem_satz(self):
        from app.services.kontenrahmen import ist_standard_erloeskonto
        for konto in (None, "", "8300", "8400", "8100", "4300", "4400", "4100"):
            assert ist_standard_erloeskonto(konto), konto
        for konto in ("8338", "8301", "4337", "1200"):
            assert not ist_standard_erloeskonto(konto), konto

    def test_sonderkonto_aus_dem_anderen_rahmen(self):
        from app.services.kontenrahmen import sonderkonto_pruefen
        sonderkonto_pruefen("8338", "SKR03")
        sonderkonto_pruefen("4337", "SKR04")
        sonderkonto_pruefen("8300", "SKR04")   # Standardkonto: folgt dem Satz
        sonderkonto_pruefen(None, "SKR04")
        with pytest.raises(ValueError, match="8338 passt nicht zum Kontenrahmen SKR04"):
            sonderkonto_pruefen("8338", "SKR04")
        with pytest.raises(ValueError, match="4337 passt nicht zum Kontenrahmen SKR03"):
            sonderkonto_pruefen("4337", "SKR03")


class TestDEinstellung:
    """DATEV_KONTENRAHMEN über die Admin-Einstellungen, mit Prüfung."""

    def test_ohne_eintrag_gilt_skr03(self, client):
        from app.services.kontenrahmen import kontenrahmen
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"
        with TestingSessionLocal() as db:
            assert kontenrahmen(db) == "SKR03"

    def test_umgebungsvariablen_wirken_nicht(self, client, monkeypatch):
        """Eine Container-Variable gälte für alle Mandanten."""
        from app.services.kontenrahmen import export_sperre, kontenrahmen
        monkeypatch.setenv("DATEV_KONTENRAHMEN", "SKR04")
        monkeypatch.setenv("DATEV_EXPORT_SPERRE", "aus der Umgebung")
        with TestingSessionLocal() as db:
            assert kontenrahmen(db) == "SKR03"
            assert export_sperre(db) is None

    def test_skr04_setzen_schreibweise_egal(self, client):
        from app.services.kontenrahmen import kontenrahmen
        r = _d_rahmen(client, " skr04 ")
        assert r.status_code == 200, r.text
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["value"] == "SKR04"
        with TestingSessionLocal() as db:
            assert kontenrahmen(db) == "SKR04"

    def test_unbekannter_rahmen_422(self, client):
        r = _d_rahmen(client, "SKR05")
        assert r.status_code == 422, r.text
        assert "SKR03 oder SKR04 erwartet" in r.json()["detail"]
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"

    def test_leeren_ist_kein_stiller_wechsel(self, client):
        _d_setze_rahmen(client, "SKR04")
        for leer in ("", None):
            r = _d_rahmen(client, leer)
            assert r.status_code == 422, r.text
            assert "leeren nicht möglich — SKR03 oder SKR04 angeben" in r.json()["detail"]
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["value"] == "SKR04"

    def test_smtp_karte_speichert_weiter(self, client):
        """Die SMTP-Karte (Settings.tsx) schickt beim Speichern JEDE bekannte
        Einstellung mit dem geladenen Wert zurück, ungesetzte als null. Das darf
        weder scheitern noch den Rahmen umstellen — ohne und mit Eintrag."""
        def wie_die_karte():
            daten = client.get("/api/v1/admin/settings").json()
            return {s["key"]: (s["value"] or None) for s in daten
                    if not (s["is_secret"] and s["value"] == "***")}

        r = client.patch("/api/v1/admin/settings", json=wie_die_karte())
        assert r.status_code == 200, r.text
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"

        _d_setze_rahmen(client, "SKR04")
        r = client.patch("/api/v1/admin/settings", json=wie_die_karte())
        assert r.status_code == 200, r.text
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["value"] == "SKR04"

    def test_wechsel_nach_exportierter_rechnung_gesperrt(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_als_exportiert(rechnung["id"])

        r = _d_rahmen(client, "SKR04")

        assert r.status_code == 422, r.text
        assert "nach dem ersten DATEV-Export nicht mehr änderbar" in r.json()["detail"]
        assert _d_einstellung(client, "DATEV_KONTENRAHMEN")["source"] == "none"
        # Den geltenden Rahmen ausdrücklich speichern ist kein Wechsel
        assert _d_rahmen(client, "SKR03").status_code == 200

    def test_wechsel_nach_exportierter_zahlung_gesperrt(self, client):
        from app.models.invoice import Payment
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/payments", json={
            "amount": "33.89", "payment_date": date.today().isoformat()})
        assert r.status_code == 201, r.text
        with TestingSessionLocal() as db:
            db.get(Payment, uuid.UUID(r.json()["id"])).datev_exported = True
            db.commit()

        assert _d_rahmen(client, "SKR04").status_code == 422

    def test_sperrgrund_setzen_und_aufheben(self, client):
        from app.services.kontenrahmen import export_sperre
        grund = "Kontierung SKR04 vom Steuerberater noch nicht bestätigt"
        r = client.patch("/api/v1/admin/settings", json={"DATEV_EXPORT_SPERRE": grund})
        assert r.status_code == 200, r.text
        with TestingSessionLocal() as db:
            assert export_sperre(db) == grund

        r = client.patch("/api/v1/admin/settings", json={"DATEV_EXPORT_SPERRE": ""})
        assert r.status_code == 200, r.text
        with TestingSessionLocal() as db:
            assert export_sperre(db) is None
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestDKontentabelle tests/test_nachtrag_0910.py::TestDEinstellung -q -p no:cacheprovider
```

Erwartet: `14 failed` — 9 × `ModuleNotFoundError: No module named 'app.services.kontenrahmen'` (alle Tests, die das Modul importieren — auch `test_skr04_setzen_schreibweise_egal`, Import in der ersten Zeile), 3 × `AssertionError: {"detail":"Unbekannter Setting-Key: DATEV_KONTENRAHMEN"}` (`test_unbekannter_rahmen_422`, `test_leeren_ist_kein_stiller_wechsel`, `test_wechsel_nach_exportierter_rechnung_gesperrt`), 1 × `assert 400 == 422` (`test_wechsel_nach_exportierter_zahlung_gesperrt`), 1 × `StopIteration` (`test_smtp_karte_speichert_weiter`: der Schlüssel fehlt in `GET /admin/settings`).

- [ ] **Step 3: Implementierung.**

`backend/app/services/kontenrahmen.py` **neu anlegen**, genau dieser Inhalt:

```python
"""Kontenrahmen des DATEV-Exports je Mandant: SKR03 oder SKR04.

Nachtrag 09.10.2026, Abschnitt D: MingaGreens bucht mit DATEV Mittelstand
Faktura mit Rechnungswesen und DATEV Unternehmen online im SKR04; der Export
kannte nur SKR03. Einstellung DATEV_KONTENRAHMEN (Admin-Einstellungen), ohne
Eintrag SKR03 wie bisher.

VOR PRODUKTIVNUTZUNG VOM STEUERBERATER ZU BESTÄTIGEN: die Konten beider
Rahmen, insbesondere "steuerfrei" (der Code kennt nur einen steuerfreien Fall)
und dass Karte/PayPal/Lastschrift wie bisher über die Bank laufen.

Hier steht jedes Sachkonto, das der Export bebucht, für beide Rahmen — an
keiner anderen Stelle ein Kontoliteral. Debitoren (10000 ff.) hängen nicht am
Rahmen.

Grundsatz (GoBD): Eine festgeschriebene Rechnung wird nie umgeschrieben. Die
Standard-Erlöskonten beider Rahmen gelten als "Konto folgt dem Steuersatz":
der Export bildet sie beim Export aus Steuersatz und aktuellem Rahmen ab. Ein
Sonderkonto an der Position bleibt, wie es ist. Damit ein Rahmenwechsel keine
schon exportierten Belege umkontiert, ist er nach dem ersten Export gesperrt.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaxRate
from app.models.invoice import STANDARD_ACCOUNTS, Invoice, Payment
from app.services.settings_service import get_setting

#: Einstellung (app_settings) — gelesen ohne Rückfall auf Umgebungsvariablen:
#: eine Container-Variable gälte für alle Mandanten (wie die Gläubiger-ID).
EINSTELLUNG = "DATEV_KONTENRAHMEN"
#: Sperrgrund für den DATEV-Export; leer = Export frei.
SPERRE = "DATEV_EXPORT_SPERRE"
#: Ohne Eintrag: Bestand (alle Mandanten exportierten bisher SKR03).
STANDARD_RAHMEN = "SKR03"

SACHKONTEN: dict[str, dict[str, str]] = {
    # SKR03 = die bisherigen STANDARD_ACCOUNTS, unverändert.
    "SKR03": dict(STANDARD_ACCOUNTS),
    "SKR04": {
        "erloes_7": "4300",           # Erlöse 7 % USt
        "erloes_19": "4400",          # Erlöse 19 % USt
        "erloes_steuerfrei": "4100",  # Steuerfreie Umsätze (Gegenstück zu SKR03 8100)
        "forderungen": "1200",        # Forderungen aus L+L — vom Export nicht bebucht
        "bank": "1800",               # Bank
        "kasse": "1600",              # Kasse
    },
}

_SCHLUESSEL_JE_SATZ = {
    TaxRate.REDUZIERT: "erloes_7",
    TaxRate.STANDARD: "erloes_19",
    TaxRate.STEUERFREI: "erloes_steuerfrei",
}

#: Die Standard-Erlöskonten ALLER Rahmen: ein solches Konto an einer Position
#: heißt "folgt dem Steuersatz" — auch eine 8300 aus der SKR03-Zeit.
STANDARD_ERLOESKONTEN = frozenset(
    konten[schluessel]
    for konten in SACHKONTEN.values()
    for schluessel in _SCHLUESSEL_JE_SATZ.values()
)

#: Kontenklasse der Erlöse im jeweils ANDEREN Rahmen. Ein Sonderkonto daraus
#: ist im eigenen Rahmen nie ein Erlöskonto: SKR03-Klasse 4 sind betriebliche
#: Aufwendungen, SKR04-Klasse 8 ist nicht belegt.
_FREMDE_ERLOESKLASSE = {"SKR03": "4", "SKR04": "8"}

#: Was der Export bebucht, in Anzeigereihenfolge (Dialog, Einstellungen).
BEBUCHTE_KONTEN = (
    ("erloes_7", "Erlöse 7 %"),
    ("erloes_19", "Erlöse 19 %"),
    ("erloes_steuerfrei", "Erlöse steuerfrei"),
    ("bank", "Bank (Zahlungen außer bar)"),
    ("kasse", "Kasse (Barzahlungen)"),
)


def rahmen_pruefen(wert: Optional[str]) -> str:
    """'skr04 ' -> 'SKR04'; alles andere als SKR03/SKR04 ist ein ValueError."""
    rahmen = (wert or "").strip().upper()
    if rahmen not in SACHKONTEN:
        raise ValueError("SKR03 oder SKR04 erwartet")
    return rahmen


def kontenrahmen(db: Session) -> str:
    """Rahmen des Mandanten; ohne Eintrag SKR03."""
    wert = get_setting(db, EINSTELLUNG, env_fallback=False)
    return rahmen_pruefen(wert) if wert else STANDARD_RAHMEN


def sachkonto(rahmen: str, schluessel: str) -> str:
    return SACHKONTEN[rahmen][schluessel]


def erloeskonto_fuer(tax_rate: TaxRate, rahmen: str) -> str:
    """Standard-Erlöskonto zum Steuersatz im Rahmen; unbekannter Satz wie 7 %."""
    return SACHKONTEN[rahmen][_SCHLUESSEL_JE_SATZ.get(tax_rate, "erloes_7")]


def ist_standard_erloeskonto(konto: Optional[str]) -> bool:
    """Leer oder ein Standard-Erlöskonto irgendeines Rahmens: dann folgt das
    Konto dem Steuersatz. Jedes andere Konto ist ein Sonderkonto und bleibt."""
    return not konto or konto in STANDARD_ERLOESKONTEN


def sonderkonto_pruefen(konto: Optional[str], rahmen: str) -> None:
    """ValueError, wenn ein Sonderkonto zur Erlösklasse des anderen Rahmens
    gehört (z. B. 8338 aus SKR03 in einem SKR04-Mandanten) — DATEV würde es
    nicht als Erlöskonto kennen. Standardkonten folgen dem Satz und passen immer."""
    if ist_standard_erloeskonto(konto):
        return
    if len(konto) == 4 and konto.isdigit() and konto[0] == _FREMDE_ERLOESKLASSE[rahmen]:
        raise ValueError(
            f"Erlöskonto {konto} passt nicht zum Kontenrahmen {rahmen} "
            f"(Kontenklasse {konto[0]} ist dort kein Erlöskonto)"
        )


def export_sperre(db: Session) -> Optional[str]:
    """Sperrgrund für den DATEV-Export oder None (frei)."""
    wert = get_setting(db, SPERRE, env_fallback=False)
    return (wert or "").strip() or None


def schon_exportiert(db: Session) -> bool:
    """Gibt es eine an DATEV exportierte Rechnung oder Zahlung?"""
    rechnung = db.execute(
        select(Invoice.id).where(Invoice.datev_exported == True).limit(1)  # noqa: E712
    ).first()
    if rechnung is not None:
        return True
    zahlung = db.execute(
        select(Payment.id).where(Payment.datev_exported == True).limit(1)  # noqa: E712
    ).first()
    return zahlung is not None


def wechsel_pruefen(db: Session, wert: Optional[str]) -> Optional[str]:
    """Prüfer für PATCH /admin/settings, Schlüssel DATEV_KONTENRAHMEN.

    Leer/None: ohne gespeicherten Rahmen ein No-op (None, nichts zu löschen,
    es bleibt SKR03) — die SMTP-Karte schickt beim Speichern jede bekannte
    Einstellung zurück, ungesetzte als null. Einen gespeicherten Rahmen leeren
    wäre ein stiller Wechsel auf SKR03 und wird abgelehnt.
    Nach dem ersten Export ist nur der bisherige Rahmen zulässig: der Export
    leitet die Standardkonten beim Export ab, ein Wechsel würde einen
    Wiederholungsexport alter Belege umkontieren.
    """
    if not (wert or "").strip():
        if get_setting(db, EINSTELLUNG, env_fallback=False):
            raise ValueError("leeren nicht möglich — SKR03 oder SKR04 angeben")
        return None
    neu = rahmen_pruefen(wert)
    if neu != kontenrahmen(db) and schon_exportiert(db):
        raise ValueError(
            "nach dem ersten DATEV-Export nicht mehr änderbar — "
            "Wechsel des Kontenrahmens mit dem Steuerberater klären"
        )
    return neu
```

`backend/app/services/settings_service.py` — in `KNOWN_SETTINGS`, letzter Eintrag `MONATSRECHNUNG_AUTO` samt schließender Klammer: diesen Block

```python
    "MONATSRECHNUNG_AUTO":   {"is_secret": False, "label": "Monatsrechnungen automatisch als Entwurf (true | false)"},
}
```

ersetzen durch

```python
    "MONATSRECHNUNG_AUTO":   {"is_secret": False, "label": "Monatsrechnungen automatisch als Entwurf (true | false)"},
    # DATEV-Export (Nachtrag 09.10., D): Kontenrahmen je Mandant, ohne Eintrag
    # SKR03. Gelesen OHNE Umgebungs-Rückfall (app.services.kontenrahmen).
    "DATEV_KONTENRAHMEN":    {"is_secret": False, "label": "DATEV-Kontenrahmen (SKR03 | SKR04)"},
    "DATEV_EXPORT_SPERRE":   {"is_secret": False, "label": "DATEV-Export gesperrt — Grund (leer = Export frei)"},
}
```

`backend/app/api/v1/admin.py` — Importzeile aus `email_service` (darunter einfügen; diese Zeile ändern weder F noch O): diesen Block

```python
from app.services.email_service import send_email, EmailNotConfiguredError
```

ersetzen durch

```python
from app.services.email_service import send_email, EmailNotConfiguredError
from app.services import kontenrahmen
```

`backend/app/api/v1/admin.py` — in `update_settings`, vor dem Löschzweig: diesen Block

```python
        # Empty/None löscht (lässt env-Fallback durchscheinen)
        if raw_value is None or raw_value == "":
```

ersetzen durch

```python
        # Kontenrahmen (Nachtrag 09.10., D): vor dem Löschzweig prüfen — einen
        # gespeicherten Rahmen leeren wäre ein stiller Wechsel auf SKR03; nach
        # dem ersten Export gesperrt. Ohne Eintrag ist null ein No-op.
        if key == kontenrahmen.EINSTELLUNG:
            try:
                raw_value = kontenrahmen.wechsel_pruefen(db, raw_value)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"{KNOWN_SETTINGS[key]['label']}: {e}")
        # Empty/None löscht (lässt env-Fallback durchscheinen)
        if raw_value is None or raw_value == "":
```

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `14 passed`.
- [ ] **Vollauf (Prozedur V):** Befehl unter „Prozedur V“. Erwartet: `14 failed, N passed, 2 skipped, 1 error`, keine Zeile vor `--- Ende Abgleich`. Gemessen (D als erster Abschnitt, auch im Gesamtlauf): `14 failed, 1658 passed, 2 skipped, 1 error`.
- [ ] **Commit:**

```bash
git add backend/app/services/kontenrahmen.py backend/app/services/settings_service.py backend/app/api/v1/admin.py backend/tests/test_nachtrag_0910.py
git commit -m "feat(datev): Kontenrahmen SKR03/SKR04 je Mandant als Einstellung, eine Kontentabelle für beide Rahmen (D)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```


### Task 2 (D.2): Kontierung beim Anlegen und beim Satzwechsel nach Rahmen

**Files:**
- Modify: `backend/app/services/invoice_service.py` (Import, `InvoiceService.add_line`)
- Modify: `backend/app/api/v1/invoices.py` (Import, `update_invoice_line`)
- Modify: `backend/app/schemas/invoice.py` (`InvoiceLineCreate.buchungskonto`, nur Beschreibung)
- Modify: `backend/tests/test_nachtrag_0910.py` (Block D.2 anhängen)

**Interfaces:**
- Produces: `add_line` speichert bei leerem **oder Standard-**Konto `erloeskonto_fuer(tax_rate, kontenrahmen(db))`; ein Sonderkonto bleibt, aus dem anderen Rahmen → `ValueError` → `POST /invoices/{id}/lines` und `POST /invoices` antworten 400 mit dem Text aus `sonderkonto_pruefen`. `update_invoice_line` zieht bei Satzwechsel ein Standardkonto (beider Rahmen) auf das Konto des aktuellen Rahmens nach.
- Consumes: `kontenrahmen`, `erloeskonto_fuer`, `ist_standard_erloeskonto`, `sonderkonto_pruefen` (D.1).
- Unverändert: `cancel_invoice` (Storno kopiert die Konten des Originals), `Invoice.buchungskonto` (Kopf), alle Aufrufer von `add_line`.

**Review Focus (D.2):** Rechnung aus Bestellung, Sammel-/Monatsrechnung und Leergutabrechnung laufen über `add_line` und bekommen dasselbe Konto wie eine Position von Hand; kein Weg schreibt eine festgeschriebene Position um.

- [ ] **Step 1: Testblock ans Dateiende anhängen:**

```python


class TestDKontierungBeimAnlegen:
    """Neue Positionen und der Satzwechsel im Entwurf nehmen das Konto des
    Rahmens. Gespeichert ist es nur ein Vorschlag — maßgeblich bildet der
    Export ab (TestDExport)."""

    def test_skr03_wie_bisher(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT, finalisieren=False)
        assert [p["buchungskonto"] for p in _d_positionen(client, rechnung)] == ["8300", "8400"]

    def test_skr04_neue_positionen(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT + [
            ("Kresse Export", 1, "5.00", "STEUERFREI"),
        ], finalisieren=False)
        assert [p["buchungskonto"] for p in _d_positionen(client, rechnung)] == ["4300", "4400", "4100"]

    def test_satzwechsel_im_entwurf_skr04(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "4300"
        url = f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}"

        r = client.patch(url, json={"tax_rate": "STANDARD"})

        assert r.status_code == 200, r.text
        assert r.json()["buchungskonto"] == "4400"
        assert client.patch(url, json={"tax_rate": "STEUERFREI"}).json()["buchungskonto"] == "4100"

    def test_entwurf_aus_der_skr03_zeit_folgt_dem_neuen_rahmen(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "8300"
        _d_setze_rahmen(client, "SKR04")

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})

        assert r.status_code == 200, r.text
        assert r.json()["buchungskonto"] == "4400"

    def test_entwurf_aus_der_skr04_zeit_folgt_skr03(self, client):
        """Auch 4300 gilt als Standardkonto (vor dem ersten Export ist der
        Rahmen noch wählbar)."""
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [("Pfandkiste", 1, "10.00", "REDUZIERT")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "4300"
        _d_setze_rahmen(client, "SKR03")

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})

        assert r.json()["buchungskonto"] == "8400"

    def test_ausdrueckliches_standardkonto_folgt_dem_satz(self, client):
        """Ein mitgeschicktes Standardkonto (z. B. 8400 aus einem alten Client)
        ist kein Sonderkonto: es folgt Satz und Rahmen."""
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client),
                               [("Erbsen-Schale", 1, "2.50", "REDUZIERT", "8400")], finalisieren=False)
        assert [p["buchungskonto"] for p in _d_positionen(client, rechnung)] == ["4300"]

    def test_sonderkonto_des_rahmens_bleibt(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client),
                               [("Kresse Sonderaktion", 1, "10.00", "REDUZIERT", "4337")],
                               finalisieren=False)
        zeile = _d_positionen(client, rechnung)[0]
        assert zeile["buchungskonto"] == "4337"
        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"tax_rate": "STANDARD"})
        assert r.json()["buchungskonto"] == "4337"

    def test_sonderkonto_aus_dem_anderen_rahmen_400(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [], finalisieren=False)

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/lines", json={
            "description": "Kresse", "quantity": 1, "unit": "STK", "unit_price": "10.00",
            "tax_rate": "REDUZIERT", "buchungskonto": "8338"})

        assert r.status_code == 400, r.text
        assert r.json()["detail"] == (
            "Erlöskonto 8338 passt nicht zum Kontenrahmen SKR04 "
            "(Kontenklasse 8 ist dort kein Erlöskonto)")
        assert _d_positionen(client, rechnung) == []
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestDKontierungBeimAnlegen -q -p no:cacheprovider
```

Erwartet: `6 failed, 2 passed`. Grün bleiben die Wächter `test_skr03_wie_bisher` und `test_sonderkonto_des_rahmens_bleibt` (4337 bleibt schon heute). Rot: `test_skr04_neue_positionen` (`['8300', '8400', '8100'] == ['4300', '4400', '4100']`), `test_satzwechsel_im_entwurf_skr04` (`'8300' == '4300'`), `test_entwurf_aus_der_skr03_zeit_folgt_dem_neuen_rahmen` (`'8400' == '4400'`), `test_entwurf_aus_der_skr04_zeit_folgt_skr03` (`'8300' == '4300'`), `test_ausdrueckliches_standardkonto_folgt_dem_satz` (`['8400'] == ['4300']`), `test_sonderkonto_aus_dem_anderen_rahmen_400` (`assert 201 == 400`).

- [ ] **Step 3: Implementierung.**

`backend/app/services/invoice_service.py` — Importzeile aus `datev_service`: diesen Block

```python
from app.services.datev_service import erloeskonto_fuer
```

ersetzen durch

```python
from app.services.kontenrahmen import (
    erloeskonto_fuer, ist_standard_erloeskonto, kontenrahmen, sonderkonto_pruefen,
)
```

`backend/app/services/invoice_service.py` — in `InvoiceService.add_line`, nach der Positionsermittlung (`max_pos`): diesen Block

```python
        # Buchungskonto basierend auf Steuersatz — dieselbe Regel wie der
        # DATEV-Export (datev_service.erloeskonto_fuer)
        if not buchungskonto:
            buchungskonto = erloeskonto_fuer(tax_rate)
```

ersetzen durch

```python
        # Erlöskonto: ein Standardkonto (oder keins) folgt Steuersatz und
        # Kontenrahmen des Mandanten — dieselbe Regel wie der DATEV-Export.
        # Ein Sonderkonto bleibt, muss aber zum Rahmen passen (Nachtrag 09.10., D).
        rahmen = kontenrahmen(self.db)
        if ist_standard_erloeskonto(buchungskonto):
            buchungskonto = erloeskonto_fuer(tax_rate, rahmen)
        else:
            sonderkonto_pruefen(buchungskonto, rahmen)
```

`backend/app/api/v1/invoices.py` — Importzeile aus `datev_service`: diesen Block

```python
from app.services.datev_service import DatevService, erloeskonto_fuer, ist_standard_erloeskonto
```

ersetzen durch

```python
from app.services.datev_service import DatevService
from app.services.kontenrahmen import erloeskonto_fuer, ist_standard_erloeskonto, kontenrahmen
```

`backend/app/api/v1/invoices.py` — in `update_invoice_line`, nach der Feldschleife: diesen Block

```python
    # Das Erlöskonto hängt am Steuersatz (8300/8400/8100). Ohne Nachziehen
    # buchte der DATEV-Export eine auf 19 % korrigierte Zeile weiter auf 8300.
    # Ein Sonderkonto bleibt — dieselbe Regel wie der DATEV-Export (S4).
    if line.tax_rate != satz_vorher and ist_standard_erloeskonto(line.buchungskonto):
        line.buchungskonto = erloeskonto_fuer(line.tax_rate)
```

ersetzen durch

```python
    # Das Erlöskonto hängt am Steuersatz und am Kontenrahmen des Mandanten
    # (SKR03 8300/8400/8100, SKR04 4300/4400/4100). Ohne Nachziehen buchte der
    # DATEV-Export eine auf 19 % korrigierte Zeile weiter auf 7 %.
    # Ein Sonderkonto bleibt — dieselbe Regel wie der DATEV-Export (S4, D).
    if line.tax_rate != satz_vorher and ist_standard_erloeskonto(line.buchungskonto):
        line.buchungskonto = erloeskonto_fuer(line.tax_rate, kontenrahmen(db))
```

`backend/app/schemas/invoice.py` — in `InvoiceLineCreate`, Feld `buchungskonto`: diesen Block

```python
    buchungskonto: Optional[str] = Field(None, max_length=10, description="Erlöskonto (SKR03)")
```

ersetzen durch

```python
    buchungskonto: Optional[str] = Field(
        None, max_length=10,
        description="Erlöskonto: leer = Standardkonto zu Steuersatz und Kontenrahmen; "
                    "sonst Sonderkonto, das zum Kontenrahmen passen muss",
    )
```

Prüfen: `grep -rn 'erloeskonto_fuer(' backend/app | grep -v '\.pyc'` zeigt in `invoice_service.py` und `invoices.py` nur Aufrufe mit zwei Argumenten; die eigene Definition in `datev_service.py` und ihr Aufruf in `erloeskonto` (ein Argument) bleiben bis D.3 stehen.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `8 passed`.
- [ ] **Vollauf (Prozedur V):** Befehl unter „Prozedur V“. Erwartet: `14 failed, N passed, 2 skipped, 1 error`, keine Zeile vor `--- Ende Abgleich`. Gemessen (D als erster Abschnitt, auch im Gesamtlauf): `1666 passed`. Insbesondere bleiben `TestS5…` (Satzwechsel, Sonderkonto 8338) und `TestDatev…` aus Paket 1 grün.
- [ ] **Commit:**

```bash
git add backend/app/services/invoice_service.py backend/app/api/v1/invoices.py backend/app/schemas/invoice.py backend/tests/test_nachtrag_0910.py
git commit -m "feat(datev): neue Rechnungspositionen und Satzwechsel nehmen das Erlöskonto des Kontenrahmens, fremdes Sonderkonto abgelehnt (D)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```


### Task 3 (D.3): Export bucht im Kontenrahmen des Mandanten

**Files:**
- Modify: `backend/app/services/datev_service.py` (Importe, Kommentarkopf, `ERLOESKONTO_JE_SATZ`/`erloeskonto_fuer`/`ist_standard_erloeskonto` entfernen, `erloeskonto`, `erloesgruppen`, neue Klasse `DatevExportAbgelehnt`, `DatevService._rahmen`, `DatevService._sonderkonten_pruefen`, `export_invoices_csv`)
- Modify: `backend/app/api/v1/invoices.py` (Import, `export_datev`, `download_datev_export`)
- Modify: `backend/tests/test_nachtrag_0910.py` (Block D.3 anhängen)

**Interfaces:**
- Produces: `class DatevExportAbgelehnt(ValueError)`; `erloeskonto(line, rahmen) -> str`; `erloesgruppen(invoice, rahmen) -> list[dict]` (beide: `rahmen` Pflicht); `export_invoices_csv` liest den Rahmen einmal, prüft alle Positionen der ausgewählten Belege vor der ersten Zeile und bucht Erlöse, Bank und Kasse aus `SACHKONTEN`. `POST /invoices/datev-export` und `/datev-export/download` antworten bei `DatevExportAbgelehnt` 409 mit dem Text, ohne zu committen. `erloeskonto_fuer` und `ist_standard_erloeskonto` bleiben über `app.services.datev_service` importierbar (aus `kontenrahmen`).
- Consumes: D.1 (`kontenrahmen`, `sachkonto`, `sonderkonto_pruefen`, …).
- Unverändert: Belegauswahl `_rechnungen`, `_richtung`, Rest-Cent-Regel, Spaltenkopf, Buchungstext, Debitoren-Export.

**Review Focus (D.3):** Spalte 7 (Gegenkonto) bei Bestandsrechnungen und Stornos aus der SKR03-Zeit; Zahlungen und Rücklastschrift auf 1800/1600; der Abbruch markiert nichts.

- [ ] **Step 1: Testblock ans Dateiende anhängen:**

```python


def _d_export_roh(client, zahlungen=False, download=False):
    pfad = "/api/v1/invoices/datev-export" + ("/download" if download else "")
    return client.post(pfad, json={
        "from_date": date.today().isoformat(), "to_date": date.today().isoformat(),
        "include_payments": zahlungen,
    })


def _d_export(client, zahlungen=False):
    r = _d_export_roh(client, zahlungen)
    assert r.status_code == 200, r.text
    daten = r.json()
    zeilen = list(csv.reader(io.StringIO(daten["csv_content"]), delimiter=";"))
    return daten, zeilen[0], zeilen[1:]


def _d_zeile(betrag, sh, konto, gegenkonto, belegnr, text, belegfeld2=""):
    """Eine erwartete Buchungszeile, Spalte für Spalte in Kopf-Reihenfolge."""
    return [betrag, sh, "EUR", "", "", konto, gegenkonto, "",
            date.today().strftime("%d%m"), belegnr, belegfeld2, text]


def _d_exportiert(rechnung_id):
    from app.models.invoice import Invoice
    with TestingSessionLocal() as db:
        return db.get(Invoice, uuid.UUID(rechnung_id)).datev_exported


def _d_zahlung(client, rechnung, betrag, methode="UEBERWEISUNG", referenz=None):
    body = {"amount": betrag, "payment_date": date.today().isoformat(), "payment_method": methode}
    if referenz:
        body["reference"] = referenz
    r = client.post(f"/api/v1/invoices/{rechnung['id']}/payments", json=body)
    assert r.status_code == 201, r.text


class TestDExportSkr04:
    """Spaltengenau im SKR04: Erlöse 4300/4400, Bank 1800, Kasse 1600."""

    def test_gemischte_rechnung_spaltengenau(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]

        daten, kopf, zeilen = _d_export(client)

        assert kopf == _D_KOPF
        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert daten["record_count"] == 2
        assert Decimal(str(daten["total_amount"])) == Decimal("33.89")

    def test_bestandsrechnung_wird_abgebildet_nicht_umgeschrieben(self, client):
        """GoBD: die Rechnung aus der SKR03-Zeit behält 8300/8400 an ihren
        Positionen; erst der Export bildet sie auf SKR04 ab."""
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        vorher = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert [l["buchungskonto"] for l in vorher["lines"]] == ["8300", "8400"]
        _d_setze_rahmen(client, "SKR04")

        _, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        nachher = client.get(f"/api/v1/invoices/{rechnung['id']}").json()
        assert nachher["lines"] == vorher["lines"]
        for feld in ("subtotal", "tax_amount", "total", "status", "invoice_number"):
            assert nachher[feld] == vorher[feld], feld

    def test_storno_spaltengenau(self, client):
        """Storno einer Bestandsrechnung nach dem Wechsel: die Stornorechnung
        spiegelt die Konten des Originals (8300/8400), beide landen auf
        4300/4400 und heben sich auf."""
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_setze_rahmen(client, "SKR04")
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/cancel",
                        json={"reason": "Pfand mit 7 % berechnet"})
        assert r.status_code == 200, r.text
        storno = r.json()["credit_note"]
        nr, snr = rechnung["invoice_number"], storno["invoice_number"]
        assert [p["buchungskonto"] for p in _d_positionen(client, storno)] == ["8300", "8400"]

        daten, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
            _d_zeile("26,75", "H", "10008", "4300", snr, f"Storno {nr} 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "H", "10008", "4400", snr, f"Storno {nr} 19 % Ökoring Testkunde"),
        ]
        assert Decimal(str(daten["total_amount"])) == Decimal("0.00")

    def test_zahlungen_spaltengenau(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        _d_zahlung(client, rechnung, "20.00", referenz="Überweisung 1")
        _d_zahlung(client, rechnung, "13.89", methode="BAR")

        daten, _, zeilen = _d_export(client, zahlungen=True)

        assert zeilen[:2] == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "4400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert sorted(zeilen[2:]) == sorted([
            _d_zeile("20,00", "S", "1800", "10008", nr, "Zahlung Ökoring Testkunde", "Überweisung 1"),
            _d_zeile("13,89", "S", "1600", "10008", nr, "Zahlung Ökoring Testkunde"),
        ])
        assert daten["record_count"] == 4

    def test_ruecklastschrift_auf_die_bank_des_rahmens(self, client):
        """SEPA (B10): Einzug S, Rücklastschrift als Gegenbuchung H — beide 1800."""
        from app.models.invoice import Payment, PaymentMethod
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        with TestingSessionLocal() as db:
            for betrag, referenz in (("33.89", "MANDAT-1"), ("-33.89", "Rücklastschrift MANDAT-1")):
                db.add(Payment(invoice_id=uuid.UUID(rechnung["id"]), payment_date=date.today(),
                               amount=Decimal(betrag), payment_method=PaymentMethod.LASTSCHRIFT,
                               reference=referenz))
            db.commit()

        _, _, zeilen = _d_export(client, zahlungen=True)

        assert sorted(zeilen[2:]) == [
            _d_zeile("33,89", "H", "1800", "10008", nr, "Zahlung Ökoring Testkunde",
                     "Rücklastschrift MANDAT-1"),
            _d_zeile("33,89", "S", "1800", "10008", nr, "Zahlung Ökoring Testkunde", "MANDAT-1"),
        ]

    def test_leergutbeleg_mit_minderung(self, client):
        """Paket 3, Q6: Leergutbeleg (Pfand 19 %) mit negativem Saldo bucht H
        auf das 19-%-Konto des Rahmens — auch mit 8400 aus der SKR03-Zeit."""
        from app.models.invoice import Invoice, InvoiceLine, TaxRate
        rechnung = _d_rechnung(client, _d_kunde(client), [], finalisieren=False)
        with TestingSessionLocal() as db:
            beleg = db.get(Invoice, uuid.UUID(rechnung["id"]))
            beleg.beleg_art = "LEERGUT"
            for nr_pos, (text, menge) in enumerate(
                (("Leergut ausgegeben: IFCO", "1"), ("Leergut zurückgenommen: IFCO", "-4")), start=1
            ):
                zeile = InvoiceLine(
                    invoice_id=beleg.id, position=nr_pos, description=text,
                    quantity=Decimal(menge), unit="STK", unit_price=Decimal("3.00"),
                    discount_percent=Decimal("0"),
                    tax_rate=TaxRate.STANDARD, is_deposit=True, buchungskonto="8400",
                )
                zeile.calculate_line_total()
                db.add(zeile)
            db.commit()
        _d_setze_rahmen(client, "SKR04")
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/finalize")
        assert r.status_code == 200, r.text
        beleg = r.json()
        assert Decimal(str(beleg["total"])) == Decimal("-10.71")

        _, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("10,71", "H", "10008", "4400", beleg["invoice_number"],
                     "Rechnung 19 % Ökoring Testkunde"),
        ]

    def test_sonderkonto_des_rahmens_bleibt(self, client):
        _d_setze_rahmen(client, "SKR04")
        rechnung = _d_rechnung(client, _d_kunde(client), [
            ("Erbsen-Schale", 10, "2.50", "REDUZIERT"),
            ("Kresse Sonderaktion", 1, "10.00", "REDUZIERT", "4337"),
        ])
        nr = rechnung["invoice_number"]

        _, _, zeilen = _d_export(client)

        assert zeilen == [
            _d_zeile("26,75", "S", "10008", "4300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("10,70", "S", "10008", "4337", nr, "Rechnung 7 % Ökoring Testkunde"),
        ]

    def test_sonderkonto_aus_skr03_bricht_den_export_ab(self, client):
        """Ein SKR03-Sonderkonto lässt sich nicht abbilden. Statt es still in
        den SKR04-Bestand zu schreiben, bricht der Export ab und markiert nichts."""
        kunde = _d_kunde(client)
        sonder = _d_rechnung(client, kunde, [("Kresse Sonderaktion", 1, "10.00", "REDUZIERT", "8338")])
        normal = _d_rechnung(client, kunde, _D_GEMISCHT)
        _d_setze_rahmen(client, "SKR04")

        r = _d_export_roh(client)

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == (
            "DATEV-Export abgebrochen, nichts exportiert: Sonderkonten passen nicht "
            f"zum Kontenrahmen SKR04 — {sonder['invoice_number']} Pos. 1 (8338). "
            "Kontierung mit dem Steuerberater klären.")
        assert _d_export_roh(client, download=True).status_code == 409
        assert _d_exportiert(sonder["id"]) is False
        assert _d_exportiert(normal["id"]) is False


class TestDExportSkr03:
    """Regression: ausdrücklich SKR03 = Bestand (8300/8400, Bank 1200, Kasse 1000)."""

    def test_spaltengenau_mit_zahlungen(self, client):
        _d_setze_rahmen(client, "SKR03")
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        nr = rechnung["invoice_number"]
        _d_zahlung(client, rechnung, "20.00", referenz="Überweisung 1")
        _d_zahlung(client, rechnung, "13.89", methode="BAR")

        _, _, zeilen = _d_export(client, zahlungen=True)

        assert zeilen[:2] == [
            _d_zeile("26,75", "S", "10008", "8300", nr, "Rechnung 7 % Ökoring Testkunde"),
            _d_zeile("7,14", "S", "10008", "8400", nr, "Rechnung 19 % Ökoring Testkunde"),
        ]
        assert sorted(zeilen[2:]) == sorted([
            _d_zeile("20,00", "S", "1200", "10008", nr, "Zahlung Ökoring Testkunde", "Überweisung 1"),
            _d_zeile("13,89", "S", "1000", "10008", nr, "Zahlung Ökoring Testkunde"),
        ])
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestDExportSkr04 tests/test_nachtrag_0910.py::TestDExportSkr03 -q -p no:cacheprovider
```

Erwartet: `6 failed, 3 passed`. Schon grün: `TestDExportSkr03::test_spaltengenau_mit_zahlungen` (Regression) sowie `test_gemischte_rechnung_spaltengenau` und `test_sonderkonto_des_rahmens_bleibt` — nach D.2 tragen neue Positionen 4300/4400/4337, und der alte Export reicht ein ihm unbekanntes Konto als „Sonderkonto“ unverändert durch. Rot (Gegenkonto bzw. Bank/Kasse noch SKR03): `test_bestandsrechnung_wird_abgebildet_nicht_umgeschrieben` und `test_storno_spaltengenau` (`'8300' != '4300'` in der Diff-Zeile), `test_zahlungen_spaltengenau` (`'1000' … != '1600'`), `test_ruecklastschrift_auf_die_bank_des_rahmens` (`'1200' … != '1800'`), `test_leergutbeleg_mit_minderung` (`'8400' … != '4400'`), `test_sonderkonto_aus_skr03_bricht_den_export_ab` (`assert 200 == 409`).

- [ ] **Step 3: Implementierung.**

`backend/app/services/datev_service.py` — Importzeile `typing` am Dateianfang (danach unbenutzt): diesen Block **ersatzlos entfernen**:

```python
from typing import Optional
```

`backend/app/services/datev_service.py` — Importblock `app.models.invoice` und `Customer`: diesen Block

```python
from app.models.invoice import (
    Invoice, InvoiceLine, InvoiceStatus, InvoiceType, Payment, PaymentMethod,
    TaxRate, STANDARD_ACCOUNTS, steuer_je_satz, ENTWURF_PRAEFIX,
)
from app.models.customer import Customer
```

ersetzen durch

```python
from app.models.invoice import (
    Invoice, InvoiceLine, InvoiceStatus, InvoiceType, Payment, PaymentMethod,
    steuer_je_satz, ENTWURF_PRAEFIX,
)
from app.models.customer import Customer
# Kontentabelle je Rahmen (Nachtrag 09.10., D). erloeskonto_fuer und
# ist_standard_erloeskonto bleiben auch über dieses Modul importierbar.
from app.services.kontenrahmen import (  # noqa: F401
    erloeskonto_fuer, ist_standard_erloeskonto, kontenrahmen, sachkonto,
    sonderkonto_pruefen,
)
```

`backend/app/services/datev_service.py` — Kommentarkopf „Kontierung des Rechnungsexports“, Punkt BU-Schlüssel: diesen Block

```python
# - Konto = Debitor, Gegenkonto = Erlöskonto, BU-Schlüssel leer:
#   8300/8400 sind in SKR03 Automatikkonten, DATEV rechnet die USt aus dem
#   Bruttobetrag heraus.
```

ersetzen durch

```python
# - Konto = Debitor, Gegenkonto = Erlöskonto, BU-Schlüssel leer:
#   8300/8400 (SKR03) bzw. 4300/4400 (SKR04) sind Automatikkonten, DATEV
#   rechnet die USt aus dem Bruttobetrag heraus.
# - Kontenrahmen je Mandant (Einstellung DATEV_KONTENRAHMEN, ohne Eintrag
#   SKR03; Nachtrag 09.10., D). Alle Sachkonten aus app.services.kontenrahmen.
#   Standard-Erlöskonten bildet der Export beim Export aus Steuersatz und
#   Rahmen ab; festgeschriebene Positionen werden nie umgeschrieben (GoBD).
```

`backend/app/services/datev_service.py` — Konstante `ERLOESKONTO_JE_SATZ` (ersatzlos entfernen; die Tabelle steht jetzt in `kontenrahmen.py`): diesen Block **ersatzlos entfernen**:

```python
ERLOESKONTO_JE_SATZ = {
    TaxRate.REDUZIERT: STANDARD_ACCOUNTS["erloes_7"],
    TaxRate.STANDARD: STANDARD_ACCOUNTS["erloes_19"],
    TaxRate.STEUERFREI: STANDARD_ACCOUNTS["erloes_steuerfrei"],
}

```

`backend/app/services/datev_service.py` — von `def erloeskonto_fuer(` bis einschließlich der Kopfzeile `def erloesgruppen(`: diesen Block

```python
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
```

ersetzen durch

```python
class DatevExportAbgelehnt(ValueError):
    """Export nicht möglich (Sperre, Kontierung) — die API antwortet 409.
    Ausgelöst, bevor eine Zeile geschrieben oder ein Beleg markiert ist."""


def erloeskonto(line: InvoiceLine, rahmen: str) -> str:
    """Erlöskonto einer Rechnungsposition im Kontenrahmen ``rahmen``.

    Die Standardkonten beider Rahmen (SKR03 8300/8400/8100, SKR04
    4300/4400/4100) folgen immer dem Steuersatz der Position und dem Rahmen
    des Mandanten — so wird eine Rechnung aus der SKR03-Zeit im SKR04
    exportiert, ohne dass ihre Positionen geändert werden (GoBD). Ein
    ausdrücklich gesetztes Sonderkonto bleibt erhalten.
    """
    if ist_standard_erloeskonto(line.buchungskonto):
        return erloeskonto_fuer(line.tax_rate, rahmen)
    return line.buchungskonto


def erloesgruppen(invoice: Invoice, rahmen: str) -> list[dict]:
```

`backend/app/services/datev_service.py` — in `erloesgruppen`, Schleife über `invoice.lines`: diesen Block

```python
    for line in invoice.lines:
        zeilen_je_konto.setdefault(erloeskonto(line), []).append(line)
```

ersetzen durch

```python
    for line in invoice.lines:
        zeilen_je_konto.setdefault(erloeskonto(line, rahmen), []).append(line)
```

`backend/app/services/datev_service.py` — in `DatevService`, Kopfzeile von `_rechnungen` (davor zwei Methoden einfügen): diesen Block

```python
    def _rechnungen(
        self, from_date: date, to_date: date, erneut_exportieren: bool = False
    ) -> list[Invoice]:
```

ersetzen durch

```python
    def _rahmen(self) -> str:
        """Kontenrahmen des Mandanten; ein unlesbarer Eintrag bricht ab."""
        try:
            return kontenrahmen(self.db)
        except ValueError as e:
            raise DatevExportAbgelehnt(f"DATEV-Kontenrahmen: {e}") from e

    @staticmethod
    def _sonderkonten_pruefen(invoices: list[Invoice], rahmen: str) -> None:
        """Ein Sonderkonto aus dem anderen Rahmen (z. B. 8338 aus der
        SKR03-Zeit im SKR04) lässt sich nicht abbilden. Statt es still zu
        exportieren, bricht der Export ab — vor der ersten Zeile."""
        konflikte = []
        for invoice in invoices:
            for line in sorted(invoice.lines, key=lambda l: l.position):
                try:
                    sonderkonto_pruefen(line.buchungskonto, rahmen)
                except ValueError:
                    konflikte.append(f"{invoice.invoice_number} Pos. {line.position} ({line.buchungskonto})")
        if konflikte:
            raise DatevExportAbgelehnt(
                "DATEV-Export abgebrochen, nichts exportiert: Sonderkonten passen nicht "
                f"zum Kontenrahmen {rahmen} — {', '.join(konflikte)}. "
                "Kontierung mit dem Steuerberater klären."
            )

    def _rechnungen(
        self, from_date: date, to_date: date, erneut_exportieren: bool = False
    ) -> list[Invoice]:
```

`backend/app/services/datev_service.py` — in `export_invoices_csv`, Belegauswahl: diesen Block

```python
        invoices = self._rechnungen(from_date, to_date, erneut_exportieren)

        output = StringIO()
```

ersetzen durch

```python
        rahmen = self._rahmen()
        invoices = self._rechnungen(from_date, to_date, erneut_exportieren)
        self._sonderkonten_pruefen(invoices, rahmen)

        output = StringIO()
```

`backend/app/services/datev_service.py` — in `export_invoices_csv`, Schleife über die Erlösgruppen: diesen Block

```python
            for gruppe in erloesgruppen(invoice):
```

ersetzen durch

```python
            for gruppe in erloesgruppen(invoice, rahmen):
```

`backend/app/services/datev_service.py` — in `export_invoices_csv`, Zahlungsteil (Bank/Kasse): diesen Block

```python
                bank_account = STANDARD_ACCOUNTS.get("bank", "1200")
                if payment.payment_method == PaymentMethod.BAR:
                    bank_account = STANDARD_ACCOUNTS.get("kasse", "1000")

                # Booking: Bank (1200) S an Debitor H
```

ersetzen durch

```python
                # Bar auf die Kasse, alles andere (Überweisung, EC, Karte,
                # PayPal, Lastschrift) wie bisher auf die Bank — je Rahmen.
                bank_account = sachkonto(rahmen, "bank")
                if payment.payment_method == PaymentMethod.BAR:
                    bank_account = sachkonto(rahmen, "kasse")

                # Booking: Bank (SKR03 1200 / SKR04 1800) S an Debitor H
```

`backend/app/api/v1/invoices.py` — Importzeile aus `datev_service` (Stand nach Task D.2): diesen Block

```python
from app.services.datev_service import DatevService
```

ersetzen durch

```python
from app.services.datev_service import DatevExportAbgelehnt, DatevService
```

`backend/app/api/v1/invoices.py` — in `export_datev` (POST `/datev-export`): diesen Block

```python
    """Exportiert Rechnungen im DATEV-Format."""
    service = DatevService(db)
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
        erneut_exportieren=data.erneut_exportieren,
    )
    db.commit()
```

ersetzen durch

```python
    """Exportiert Rechnungen im DATEV-Format."""
    service = DatevService(db)
    try:
        csv_content, record_count, total_amount = service.export_invoices_csv(
            from_date=data.from_date,
            to_date=data.to_date,
            include_payments=data.include_payments,
            erneut_exportieren=data.erneut_exportieren,
        )
    except DatevExportAbgelehnt as e:
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()
```

`backend/app/api/v1/invoices.py` — in `download_datev_export` (POST `/datev-export/download`): diesen Block

```python
    """Exportiert Rechnungen als DATEV CSV-Datei zum Download."""
    service = DatevService(db)
    csv_content, record_count, total_amount = service.export_invoices_csv(
        from_date=data.from_date,
        to_date=data.to_date,
        include_payments=data.include_payments,
        erneut_exportieren=data.erneut_exportieren,
    )
    db.commit()
```

ersetzen durch

```python
    """Exportiert Rechnungen als DATEV CSV-Datei zum Download."""
    service = DatevService(db)
    try:
        csv_content, record_count, total_amount = service.export_invoices_csv(
            from_date=data.from_date,
            to_date=data.to_date,
            include_payments=data.include_payments,
            erneut_exportieren=data.erneut_exportieren,
        )
    except DatevExportAbgelehnt as e:
        raise HTTPException(status_code=409, detail=str(e))
    db.commit()
```

Prüfen: `grep -n 'STANDARD_ACCOUNTS\|ERLOESKONTO_JE_SATZ\|TaxRate\|Optional' backend/app/services/datev_service.py` → keine Ausgabe; `grep -n 'rahmen: str) ->\|erloesgruppen(invoice, rahmen)\|erloeskonto(line, rahmen)' backend/app/services/datev_service.py` → 5 Treffer (Kopfzeilen von `erloeskonto`, `erloesgruppen` und `_sonderkonten_pruefen`, Aufruf in `erloesgruppen`, Aufruf in `export_invoices_csv`).

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `9 passed`. Zusätzlich die Bestandstests des Exports:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_datev_export.py tests/test_gernot_261008.py -q -p no:cacheprovider
```

Erwartet: `149 passed` (gemessen auf `df84f7b` + D.1–D.3; unverändert gegenüber vorher, D ändert dort keinen Test).
- [ ] **Vollauf (Prozedur V):** Befehl unter „Prozedur V“. Erwartet: `14 failed, N passed, 2 skipped, 1 error`, keine Zeile vor `--- Ende Abgleich`. Gemessen (D als erster Abschnitt, auch im Gesamtlauf): `1675 passed`.
- [ ] **Statisch:** `ruff`-Befehl für D (Global Constraints) → keine Ausgabe.
- [ ] **Commit:**

```bash
git add backend/app/services/datev_service.py backend/app/api/v1/invoices.py backend/tests/test_nachtrag_0910.py
git commit -m "feat(datev): Export bucht im Kontenrahmen des Mandanten, Bestandsrechnungen werden abgebildet statt umgeschrieben (D)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```


### Task 4 (D.4): Exportsperre bis zur Bestätigung und Einstellungen für den Dialog

**Files:**
- Modify: `backend/app/schemas/invoice.py` (neu `DatevKonto`, `DatevEinstellungenResponse` hinter `DatevExportResponse`)
- Modify: `backend/app/services/datev_service.py` (Import `export_sperre`, Sperre am Anfang von `export_invoices_csv`)
- Modify: `backend/app/api/v1/invoices.py` (Importe, neuer Endpunkt `GET /invoices/datev-export/einstellungen` vor `POST /datev-export`)
- Modify: `backend/tests/test_nachtrag_0910.py` (Block D.4 anhängen)

**Interfaces:**
- Produces: `GET /api/v1/invoices/datev-export/einstellungen` → `{"kontenrahmen": "SKR04", "konten": [{"bezeichnung": "Erlöse 7 %", "konto": "4300"}, …5 Einträge in der Reihenfolge von BEBUCHTE_KONTEN], "sperrgrund": "<Text>" | null}`; Rechte wie der Rechnungsrouter (`admin`, `sales`, `accounting`; Halle 403). Mit gesetzter Sperre: `export_invoices_csv` wirft `DatevExportAbgelehnt("DATEV-Export gesperrt: <Grund>")` vor allem anderen → beide Export-Endpunkte 409, nichts markiert.
- Consumes: `export_sperre`, `BEBUCHTE_KONTEN`, `sachkonto`, `kontenrahmen` (D.1); `DatevExportAbgelehnt` und die 409-Behandlung (D.3).

**Review Focus (D.4):** Die Sperre greift im Service (auch für künftige Aufrufer), nicht nur in der API; der GET-Endpunkt steht vor `/{invoice_id}`-Routen nicht im Weg (zwei Pfadsegmente).

- [ ] **Step 1: Testblock ans Dateiende anhängen:**

```python


_D_GRUND = "Kontierung SKR04 vom Steuerberater noch nicht bestätigt"


def _d_sperren(client, grund):
    r = client.patch("/api/v1/admin/settings", json={"DATEV_EXPORT_SPERRE": grund})
    assert r.status_code == 200, r.text


def _d_als(*rollen):
    """Login mit genau diesen Rollen; das client-Fixture räumt auf."""
    from app.api.deps import get_current_user
    from app.main import app

    async def override():
        return {"id": "123e4567-e89b-12d3-a456-426614174000", "username": "d",
                "email": "d@example.com", "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


class TestDSperre:
    """Bis der Steuerberater die Kontierung bestätigt, bleibt der Export zu."""

    def test_gesperrt_409_und_nichts_markiert(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_sperren(client, _D_GRUND)

        for download in (False, True):
            r = _d_export_roh(client, download=download)
            assert r.status_code == 409, r.text
            assert r.json()["detail"] == f"DATEV-Export gesperrt: {_D_GRUND}"
        assert _d_exportiert(rechnung["id"]) is False

    def test_nach_freigabe_wieder_frei(self, client):
        rechnung = _d_rechnung(client, _d_kunde(client), _D_GEMISCHT)
        _d_sperren(client, _D_GRUND)
        _d_sperren(client, "")

        _, _, zeilen = _d_export(client)

        assert len(zeilen) == 2
        assert _d_exportiert(rechnung["id"]) is True

    def test_sperre_gilt_auch_im_service(self, client):
        from app.services.datev_service import DatevExportAbgelehnt, DatevService
        _d_sperren(client, _D_GRUND)
        with TestingSessionLocal() as db:
            with pytest.raises(DatevExportAbgelehnt, match="DATEV-Export gesperrt"):
                DatevService(db).export_invoices_csv(date.today(), date.today())


class TestDEinstellungenFuerDenDialog:
    """GET /invoices/datev-export/einstellungen — Rahmen, Konten, Sperre."""

    _URL = "/api/v1/invoices/datev-export/einstellungen"

    def test_ohne_eintrag_skr03_und_frei(self, client):
        r = client.get(self._URL)
        assert r.status_code == 200, r.text
        assert r.json() == {
            "kontenrahmen": "SKR03",
            "konten": [
                {"bezeichnung": "Erlöse 7 %", "konto": "8300"},
                {"bezeichnung": "Erlöse 19 %", "konto": "8400"},
                {"bezeichnung": "Erlöse steuerfrei", "konto": "8100"},
                {"bezeichnung": "Bank (Zahlungen außer bar)", "konto": "1200"},
                {"bezeichnung": "Kasse (Barzahlungen)", "konto": "1000"},
            ],
            "sperrgrund": None,
        }

    def test_skr04_gesperrt(self, client):
        _d_setze_rahmen(client, "SKR04")
        _d_sperren(client, _D_GRUND)

        daten = client.get(self._URL).json()

        assert daten["kontenrahmen"] == "SKR04"
        assert [k["konto"] for k in daten["konten"]] == ["4300", "4400", "4100", "1800", "1600"]
        assert daten["sperrgrund"] == _D_GRUND

    def test_buchhaltung_liest_den_dialog_nicht_die_admin_einstellungen(self, client):
        """Darum ein eigener Endpunkt unter /invoices: /admin/settings ist nur
        für admin. Die Halle sieht weder Rechnungen noch DATEV."""
        _d_als("accounting")
        assert client.get(self._URL).status_code == 200
        assert client.get("/api/v1/admin/settings").status_code == 403
        _d_als("production_staff")
        assert client.get(self._URL).status_code == 403
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestDSperre tests/test_nachtrag_0910.py::TestDEinstellungenFuerDenDialog -q -p no:cacheprovider
```

Erwartet: `5 failed, 1 passed` (Wächter `test_nach_freigabe_wieder_frei`). Rot: `test_gesperrt_409_und_nichts_markiert` (`assert 200 == 409`), `test_sperre_gilt_auch_im_service` (`DID NOT RAISE … DatevExportAbgelehnt`), `test_ohne_eintrag_skr03_und_frei` (`assert 404 == 200`), `test_skr04_gesperrt` (`KeyError: 'kontenrahmen'`), `test_buchhaltung_liest_den_dialog_nicht_die_admin_einstellungen` (`assert 404 == 200`).

- [ ] **Step 3: Implementierung.**

`backend/app/schemas/invoice.py` — Klasse `DatevExportResponse` (zwei Klassen dahinter anfügen): diesen Block

```python
class DatevExportResponse(BaseModel):
    """Response für DATEV-Export"""
    filename: str
    record_count: int
    total_amount: Decimal
    export_date: datetime
    csv_content: Optional[str] = None  # Optional, für direkten Download
```

ersetzen durch

```python
class DatevExportResponse(BaseModel):
    """Response für DATEV-Export"""
    filename: str
    record_count: int
    total_amount: Decimal
    export_date: datetime
    csv_content: Optional[str] = None  # Optional, für direkten Download


class DatevKonto(BaseModel):
    bezeichnung: str
    konto: str


class DatevEinstellungenResponse(BaseModel):
    """Für den Export-Dialog (Nachtrag 09.10., D): Kontenrahmen des Mandanten,
    die Konten, die der Export bebucht, und ein Sperrgrund (None = frei)."""
    kontenrahmen: str
    konten: list[DatevKonto]
    sperrgrund: Optional[str] = None
```

`backend/app/services/datev_service.py` — Importblock aus `kontenrahmen` (Stand nach Task D.3): diesen Block

```python
from app.services.kontenrahmen import (  # noqa: F401
    erloeskonto_fuer, ist_standard_erloeskonto, kontenrahmen, sachkonto,
    sonderkonto_pruefen,
)
```

ersetzen durch

```python
from app.services.kontenrahmen import (  # noqa: F401
    erloeskonto_fuer, export_sperre, ist_standard_erloeskonto, kontenrahmen,
    sachkonto, sonderkonto_pruefen,
)
```

`backend/app/services/datev_service.py` — in `export_invoices_csv`, Anfang (Stand nach Task D.3): diesen Block

```python
        rahmen = self._rahmen()
        invoices = self._rechnungen(from_date, to_date, erneut_exportieren)
```

ersetzen durch

```python
        # Sperre (z. B. "Kontierung vom Steuerberater noch nicht bestätigt")
        # vor allem anderen: nichts wird gelesen, geschrieben oder markiert.
        grund = export_sperre(self.db)
        if grund:
            raise DatevExportAbgelehnt(f"DATEV-Export gesperrt: {grund}")
        rahmen = self._rahmen()
        invoices = self._rechnungen(from_date, to_date, erneut_exportieren)
```

`backend/app/api/v1/invoices.py` — Schema-Import (`from app.schemas.invoice import (`), Zeile mit `DatevExportRequest`: diesen Block

```python
    DatevExportRequest, DatevExportResponse,
```

ersetzen durch

```python
    DatevExportRequest, DatevExportResponse, DatevEinstellungenResponse, DatevKonto,
```

`backend/app/api/v1/invoices.py` — Importzeile aus `kontenrahmen` (Stand nach Task D.2): diesen Block

```python
from app.services.kontenrahmen import erloeskonto_fuer, ist_standard_erloeskonto, kontenrahmen
```

ersetzen durch

```python
from app.services.kontenrahmen import (
    BEBUCHTE_KONTEN, erloeskonto_fuer, export_sperre, ist_standard_erloeskonto, kontenrahmen, sachkonto,
)
```

`backend/app/api/v1/invoices.py` — vor `@router.post("/datev-export")` (neuer GET-Endpunkt): diesen Block

```python
@router.post("/datev-export")
def export_datev(
```

ersetzen durch

```python
@router.get("/datev-export/einstellungen", response_model=DatevEinstellungenResponse)
def datev_einstellungen(db: DBSession):
    """Kontenrahmen, bebuchte Konten und Sperre für den Export-Dialog.

    Unter /invoices statt /admin/settings: den Export bedient auch die
    Buchhaltung, /admin/settings ist nur für admin (Nachtrag 09.10., D).
    """
    rahmen = kontenrahmen(db)
    return DatevEinstellungenResponse(
        kontenrahmen=rahmen,
        konten=[DatevKonto(bezeichnung=text, konto=sachkonto(rahmen, schluessel))
                for schluessel, text in BEBUCHTE_KONTEN],
        sperrgrund=export_sperre(db),
    )


@router.post("/datev-export")
def export_datev(
```

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `6 passed`. Danach alle D-Tests:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestDKontentabelle tests/test_nachtrag_0910.py::TestDEinstellung tests/test_nachtrag_0910.py::TestDKontierungBeimAnlegen tests/test_nachtrag_0910.py::TestDExportSkr04 tests/test_nachtrag_0910.py::TestDExportSkr03 tests/test_nachtrag_0910.py::TestDSperre tests/test_nachtrag_0910.py::TestDEinstellungenFuerDenDialog -q -p no:cacheprovider
```

Erwartet: `37 passed`.
- [ ] **Vollauf (Prozedur V):** Befehl unter „Prozedur V“. Erwartet: `14 failed, N passed, 2 skipped, 1 error`, keine Zeile vor `--- Ende Abgleich`. Gemessen (D als erster Abschnitt, auch im Gesamtlauf): `1681 passed`.
- [ ] **Statisch:** `ruff`-Befehl für D (Global Constraints) → keine Ausgabe.
- [ ] **Commit:**

```bash
git add backend/app/schemas/invoice.py backend/app/services/datev_service.py backend/app/api/v1/invoices.py backend/tests/test_nachtrag_0910.py
git commit -m "feat(datev): Exportsperre bis zur Bestätigung durch den Steuerberater, Einstellungen für den Export-Dialog (D)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```


### Task 5 (D.5): Oberfläche — Export-Dialog mit Kontenrahmen und Sperre, Einstellungskarte „DATEV-Export“

**Files:**
- Modify: `frontend/src/pages/Invoices.tsx` (`DatevExportForm`)
- Modify: `frontend/src/pages/Settings.tsx` (Import, Kartenliste, neue Karte `DatevSettingsCard` vor `MonatsrechnungSettingsCard`)
- Modify: `frontend/src/services/api.ts` (`DatevEinstellungen`, `invoicesApi.datevEinstellungen`)

**Interfaces:**
- Produces: `interface DatevEinstellungen { kontenrahmen: 'SKR03' | 'SKR04'; konten: { bezeichnung: string; konto: string }[]; sperrgrund: string | null }`; `invoicesApi.datevEinstellungen(): Promise<DatevEinstellungen>`; Query-Key `['datev-einstellungen']` (Dialog und Karte teilen ihn); `export function DatevSettingsCard()`.
- Consumes: `GET /invoices/datev-export/einstellungen` (D.4), `PATCH /admin/settings` mit `DATEV_KONTENRAHMEN` (D.1), `getErrorMessage` (beide Seiten importieren es schon).
- Texte: Dialog „Kontenrahmen SKR04“ + Kontenzeile („Erlöse 7 % 4300 · Erlöse 19 % 4400 · …“), bei Sperre Kasten „DATEV-Export gesperrt“ mit Grund und gesperrtem Knopf; Fehler-Toast mit Servertext (409). Karte: „DATEV-Export“ (volle Breite, `lg:col-span-2`), Knöpfe SKR03/SKR04, Hinweis „Nach dem ersten Export nicht mehr änderbar.“, Kontenzeile, ggf. „Export gesperrt: <Grund>“; Fehler-Toast mit Servertext (422).

**Review Focus (D.5, Browser — kein automatischer Test):** DB1 Dialog im Mandanten mit SKR04 und Sperre: Kasten, Knopf gesperrt, Kontenzeile 4300/4400/4100/1800/1600. DB2 Ohne Sperre: Export lädt die Datei; 409 (Sonderkonto) zeigt den Servertext. DB3 Einstellungen → „DATEV-Export“: Wechsel SKR03 ↔ SKR04 vor dem ersten Export, Dialog zeigt danach den neuen Rahmen (gemeinsamer Query-Key). DB4 Nach einem Export: Wechsel zeigt den 422-Text, Auswahl bleibt. DB5 Rolle `accounting`: Dialog lädt die Einstellungen (Karte ist auf der admin-Seite). DB6 Einstellungen ab `lg`: Karte „DATEV-Export“ über die volle Breite unter „Saisonzyklus“/„Monatsrechnungen“, keine leere Zelle neben ihr.

- [ ] **Step 1: Seiten anpassen (zuerst — `tsc` wird rot, weil `api.ts` noch fehlt).**

`frontend/src/pages/Invoices.tsx` — Anfang von `function DatevExportForm`: diesen Block

```tsx
function DatevExportForm({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
```

ersetzen durch

```tsx
function DatevExportForm({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  // Kontenrahmen und Sperre des Mandanten (Nachtrag 09.10., D). Das Backend
  // lehnt einen gesperrten Export ohnehin mit 409 ab; der Dialog sagt es vorher.
  const { data: einstellungen } = useQuery({
    queryKey: ['datev-einstellungen'],
    queryFn: () => invoicesApi.datevEinstellungen(),
  });
  const sperrgrund = einstellungen?.sperrgrund ?? null;
```

`frontend/src/pages/Invoices.tsx` — in `DatevExportForm`, Ende von `handleExport` bis zum Feld „Von“: diesen Block

```tsx
    } catch (error) {
      toast.error('Fehler beim Export');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Von"
```

ersetzen durch

```tsx
    } catch (error) {
      // 409 mit Klartext: Sperre oder Sonderkonto, das nicht zum Kontenrahmen passt
      toast.error(getErrorMessage(error, 'Fehler beim Export'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {einstellungen && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-sm text-gray-600 dark:text-gray-300">
          <div className="font-medium text-gray-800 dark:text-gray-100">
            Kontenrahmen {einstellungen.kontenrahmen}
          </div>
          <div className="text-xs mt-1">
            {einstellungen.konten.map((k) => `${k.bezeichnung} ${k.konto}`).join(' · ')}
          </div>
        </div>
      )}
      {sperrgrund && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-900/30 dark:border-amber-700 p-3 text-sm text-amber-800 dark:text-amber-200">
          <div className="font-medium">DATEV-Export gesperrt</div>
          <div>{sperrgrund}</div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        <Input
          label="Von"
```

`frontend/src/pages/Invoices.tsx` — in `DatevExportForm`, Knopf „Exportieren“: diesen Block

```tsx
        <Button onClick={handleExport} loading={loading} fullWidth icon={<Download className="w-4 h-4" />}>
          Exportieren
        </Button>
```

ersetzen durch

```tsx
        <Button onClick={handleExport} loading={loading} disabled={!!sperrgrund} fullWidth icon={<Download className="w-4 h-4" />}>
          Exportieren
        </Button>
```

`frontend/src/pages/Settings.tsx` — Importzeile aus `../services/api`: diesen Block

```tsx
import { capacityApi, adminApi, integrationsApi } from '../services/api';
```

ersetzen durch

```tsx
import { capacityApi, adminApi, integrationsApi, invoicesApi } from '../services/api';
```

`frontend/src/pages/Settings.tsx` — in `Settings()`, Kartenliste: diesen Block

```tsx
        <MonatsrechnungSettingsCard />
        <SmtpSettingsCard />
```

ersetzen durch

```tsx
        <MonatsrechnungSettingsCard />
        <DatevSettingsCard />
        <SmtpSettingsCard />
```

`frontend/src/pages/Settings.tsx` — Abschnittskommentar vor `MonatsrechnungSettingsCard` (neue Karte davor einfügen): diesen Block

```tsx
// ==================== Monatsrechnungen (B5) ====================
```

ersetzen durch

```tsx
// ==================== DATEV-Export (Nachtrag 09.10., D) ====================

export function DatevSettingsCard() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ['datev-einstellungen'],
    queryFn: () => invoicesApi.datevEinstellungen(),
  });

  const saveMutation = useMutation({
    mutationFn: (rahmen: string) => adminApi.updateSettings({ DATEV_KONTENRAHMEN: rahmen }),
    onSuccess: (_r, rahmen) => {
      toast.success(`DATEV-Kontenrahmen: ${rahmen}`);
      queryClient.invalidateQueries({ queryKey: ['datev-einstellungen'] });
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] });
    },
    // 422 mit Klartext, z. B. nach dem ersten Export nicht mehr änderbar
    onError: (e) => toast.error(getErrorMessage(e, 'Speichern fehlgeschlagen')),
  });

  // Volle Breite: im Raster (lg:grid-cols-2) steht die Karte zwischen
  // Monatsrechnungen (halb) und SMTP (volle Breite) — halb breit bliebe
  // rechts eine leere Zelle. Die Knöpfe bleiben schmal (max-w-md).
  return (
    <div className="card lg:col-span-2">
      <div className="card-header">
        <h3 className="card-title">DATEV-Export</h3>
      </div>
      <div className="card-body space-y-3">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Kontenrahmen der Buchhaltung in DATEV. Nach dem ersten Export nicht mehr änderbar.
        </p>
        <div className="flex gap-2 max-w-md">
          {(['SKR03', 'SKR04'] as const).map((rahmen) => (
            <button
              key={rahmen}
              type="button"
              disabled={!data || saveMutation.isPending}
              onClick={() => rahmen !== data?.kontenrahmen && saveMutation.mutate(rahmen)}
              className={`flex-1 p-2 rounded-lg border-2 text-sm transition-colors ${data?.kontenrahmen === rahmen
                ? 'border-minga-500 bg-minga-50 dark:bg-minga-900/30 font-medium'
                : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                }`}
            >
              {rahmen}
            </button>
          ))}
        </div>
        {data && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {data.konten.map((k) => `${k.bezeichnung} ${k.konto}`).join(' · ')}
          </p>
        )}
        {data?.sperrgrund && (
          <p className="text-xs text-amber-700 dark:text-amber-300">
            Export gesperrt: {data.sperrgrund}
          </p>
        )}
      </div>
    </div>
  );
}


// ==================== Monatsrechnungen (B5) ====================
```

- [ ] **Step 2: Rot.** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → genau 4 Fehler:

```
src/pages/Invoices.tsx(…): error TS2339: Property 'datevEinstellungen' does not exist on type '{ list: … }'.
src/pages/Invoices.tsx(…): error TS7006: Parameter 'k' implicitly has an 'any' type.
src/pages/Settings.tsx(…): error TS2339: Property 'datevEinstellungen' does not exist on type '{ list: … }'.
src/pages/Settings.tsx(…): error TS7006: Parameter 'k' implicitly has an 'any' type.
```
Zeilennummern sind ohne Belang; maßgeblich sind Datei, Fehlercode und Name.

- [ ] **Step 3: Schnittstelle.**

`frontend/src/services/api.ts` — vor `export interface AppSettingResponse {`: diesen Block

```ts
export interface AppSettingResponse {
```

ersetzen durch

```ts
/** GET /invoices/datev-export/einstellungen — sperrgrund null = Export frei */
export interface DatevEinstellungen {
  kontenrahmen: 'SKR03' | 'SKR04'
  konten: { bezeichnung: string; konto: string }[]
  sperrgrund: string | null
}

export interface AppSettingResponse {
```

`frontend/src/services/api.ts` — in `invoicesApi`, Abschnitt `// DATEV`: diesen Block

```ts
  // DATEV
  exportDatev: (data: { from_date: string; to_date: string; include_payments?: boolean; erneut_exportieren?: boolean }) =>
```

ersetzen durch

```ts
  // DATEV
  /** Kontenrahmen, bebuchte Konten und Sperre für den Export-Dialog (Nachtrag 09.10., D) */
  datevEinstellungen: () =>
    api.get<DatevEinstellungen>('/invoices/datev-export/einstellungen').then(r => r.data),

  exportDatev: (data: { from_date: string; to_date: string; include_payments?: boolean; erneut_exportieren?: boolean }) =>
```

- [ ] **Step 4: Grün.** `tsc` → keine Ausgabe. Build: `cd frontend && npm run build` → `✓ built in …`.
- [ ] **Commit:**

```bash
git add frontend/src/pages/Invoices.tsx frontend/src/pages/Settings.tsx frontend/src/services/api.ts
git commit -m "feat(datev): Export-Dialog zeigt Kontenrahmen und Sperre, Einstellungskarte DATEV-Export (D)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Abschlussmeldung D** (Zwischenstand für die Gesamtmeldung in Task 17; weiter mit Task 6): `<Basis>`, fünf Commit-Hashes, Rot/Grün je Task, letzte Prozedur-V-Zeile, `ruff`, `tsc`, Build; jede Abweichung und jeder selbst behobene Ankerfehler.

---

## Abschnitt F — Firmendaten-Karte in den Einstellungen speichert auf dem Server — Tasks 6–10

**Ziel:** Die Karte „Firmendaten“ (Einstellungen) liest und schreibt die Firmendaten des Mandanten über `GET/PATCH /api/v1/admin/settings` (`COMPANY_*`, nur Admin) statt im Browser (`localStorage['minga_settings_company']`). Was Gernot dort im Browser eingetragen hat, erscheint einmalig als Vorschlag mit Hinweis. Briefkopf und Fuß der PDFs erscheinen nicht doppelt. Beleg-Mails grüßen ohne Firmennamen mit dem Absendernamen (`EMAILS_FROM_NAME`) statt „Ihr Team“.

**Spec:** `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, „Umsetzungsstand …“, Punkt „Offen (niedrig, 09.10.)“ (1) Firmendaten-Karte, (2) Mail-Grußformel.

### Befund: Woher Briefkopf und Fuß kommen (geklärt vor der Planung)

- **Quelle sind die Belegvorlagen** (Admin → Belegvorlagen, Tabelle `document_templates`, je Belegart `texts.header_text` und `texts.footer_text`, dazu ein Logo). Es gibt kein Briefpapier-PDF und kein Hintergrundbild: `pdf_service` zeichnet auf der Seite nur das Entwurfs-Wasserzeichen (`_wasserzeichen_entwurf`), Branding wirkt nur in der Oberfläche.
- **Regel im Code, je Block entweder–oder:** `render_company_header_block(settings, logo_path, custom_header_text)` druckt einen nicht leeren `header_text` **statt** `<b>COMPANY_NAME</b>` + Adresszeilen (ohne beides: „Minga Greens“). Der Fuß druckt einen nicht leeren `footer_text` **statt** `render_company_footer_block(settings)` (ohne beides: „Minga Greens - Microgreens Farm München“). Gleich in `generate_invoice_pdf`, `_build_document` (AB, Lieferschein, Verpackungsliste) und `generate_payment_reminder_pdf`. Der Vorlagen-Editor sagt es schon: „Briefkopf (überschreibt Firmenname + Adresse)“, „Fußzeile (überschreibt Firmen-Footer)“ (`DocumentTemplates.tsx`).
- **Beleg Minga:** RE-2026-00001 zeigt „MingaGreens GmbH · Wittenberger Straße 17 · 80993 München“ und einen Fuß mit Bank, Geschäftsführung, USt-ID, Steuer-Nr., HRB, Öko-Kontrollnummer, obwohl alle `COMPANY_*` leer sind. Ohne Vorlagentext stünde dort „Minga Greens“ bzw. „Minga Greens - Microgreens Farm München“, und Geschäftsführung/HRB/Öko-Nr. kennt kein `COMPANY_*`-Feld — also hat die RECHNUNG-Vorlage beide Texte. Das lokale Backup `backend/data/minga-preReset-20260812-walsafe.db` (August, vor dem Neustart) hat genau diese Texte in **allen fünf** Vorlagen, `COMPANY_*` leer, `EMAILS_FROM_NAME = 'MingaGreens GmbH'` (Runbook-Skript unten, an einer Kopie; die echte USt-ID im Fuß ist DE340540498). Den heutigen Stand der übrigen vier Vorlagen prüft der Manager vor dem Deploy (Abnahme R1).
- **Was passiert, wenn `COMPANY_NAME`/Adresse gesetzt werden:** Bei Vorlagen mit eigenem Text **nichts** — das PDF bleibt bytegleich (gemessen, Test `test_mit_vorlage_bleibt_das_pdf_bytegleich`); kein doppelter Name, kein doppelter Fuß. Bei einer Vorlage ohne eigenen Text erscheinen die Firmendaten statt der Code-Standards, **je Block einmal** (Kopf: Name, Straße, Ort; Fuß: Name, „Straße · Ort“, Kontakt, Steuer, Bank). Außerhalb der PDFs: Betreff der Beleg-Mails bekommt „ — Firmenname“ (`belegversand.firmenzusatz`), die Grußformel den Firmennamen, der Dienstplan-PDF-Titel den Firmennamen statt „Minga Greens“.
- **Nebenbefund 1 (in F behoben):** `render_company_header_block`/`render_company_footer_block` setzen die Werte unmaskiert in ReportLab-Auszeichnung. „Huber & Soehne <Bio> GmbH“ wird still zu „Huber & Soehne GmbH“, „Servus <servus@…>“ zu „Servus“, „AT&T“ zu „AT&T;“ (gemessen); ein Wert mit `<B>` bricht das PDF ab (`ValueError … Parse error`). Mit der Karte werden die Felder frei editierbar. Maskiert werden nur `&` und `<`: ein unmaskiertes `>` druckt ReportLab richtig, maskiert (`&gt;`) entstünden bei Werten wie „x>y“ andere PDF-Bytes (gemessen) — so bleibt jedes bisher richtig gedruckte PDF bytegleich.
- **Nebenbefund 2 (in F behoben):** Die SMTP-Karte (`SmtpSettingsCard`) schickt beim Speichern **jede** bekannte Einstellung mit dem zuletzt geladenen Wert zurück, auch Werte aus Umgebungsvariablen (`source: 'env'`) — sie schriebe damit Firmendaten, Gläubiger-ID und `MONATSRECHNUNG_AUTO` aus der Container-Umgebung still in die Mandanten-DB, genau das, wovor SEPA- und Monatsrechnungs-Karte warnen.
- **Nebenbefund 3 (nicht in F, Offene Punkte; in der Zweitprüfung bestätigt):** Die Vorschau der Belegvorlagen (`GET /document-templates/{typ}/preview.pdf`) antwortet für RECHNUNG, AUFTRAGSBESTAETIGUNG, LIEFERSCHEIN und VERPACKUNGSLISTE mit 500 (`AttributeError` an den Ersatzobjekten aus `document_template_service.build_dummy_*`); nur MAHNUNG geht.

### Entscheidungen (Manager)

- **F-E1 — Belegvorlage hat Vorrang (bestehende Regel bleibt, wird mit Tests festgehalten).** Begründung: (a) Die Vorlagen sind vollständiger als `COMPANY_*` (Geschäftsführung und Registereintrag sind Pflichtangaben auf Geschäftsbriefen, § 35a GmbHG; dazu die Öko-Kontrollnummer) — dafür gibt es kein Feld. (b) Ausgestellte Belege werden bei jedem Abruf neu gerendert; bleibt das PDF bytegleich, bleiben GoBD-Stand und Versandnachweis intakt (AB/Lieferschein erneut senden vergleicht die SHA-256 des ersten Versands und antwortet sonst 409, `documents.py`). (c) Die Oberfläche der Belegvorlagen verspricht genau diese Regel. Verworfen: „Firmendaten vor Vorlage“ (verlöre Pflichtangaben, änderte ausgestellte PDFs, sperrte erneutes Senden), „beide drucken“ (= Doppelung).
- **F-E2 — Bank, IBAN, BIC in der Karte „Firmendaten“; die Gläubiger-ID bleibt allein in der Karte „SEPA-Lastschrift“** (Paket 3). Keine Doppelung; die Firmendaten-Karte verweist darauf.
- **F-E3 — Vorbelegt wird nur der in der Mandanten-DB gespeicherte Wert** (`source: 'db'`), wie in `SepaEinstellungenKarte`. Ein Wert aus der Container-Umgebung gilt für alle Mandanten und erscheint nur als Hinweis „Vorgabe des Servers: …“ unter dem Feld.
- **F-E4 — Browser-Werte einmalig als Vorschlag:** nur in Felder, die auf dem Server leer sind; ohne die alten Beispielwerte der Karte („Minga Greens GmbH“, „Breisacher Str. 12, 81667 München“, „DE328451962“, „info@minga-greens.de“, „+49 89 123 456 0“, „www.minga-greens.de“ — die Karte zeigte sie, wenn nichts gespeichert war); die alte Adresse „Straße, PLZ Ort“ wird am letzten Komma in zwei Zeilen geteilt. Nichts geht automatisch an den Server: ein gelber Hinweis nennt die übernommenen Felder, „Speichern“ schreibt sie, „Vorschlag verwerfen“ lädt den Serverstand. Beides löscht den Browser-Eintrag.
- **F-E5 — Prüfung beim Speichern** (`settings_service.firmendaten_pruefen`, für die elf Firmendaten-Schlüssel; `update_settings` ruft sie vor `sepa_service.einstellung_pruefen` auf, beide lassen fremde Schlüssel unverändert): Rand-Leerzeichen weg, nicht nur Leerzeichen, eine Zeile (der Firmenname steht im Mail-Betreff; ein Zeilenumbruch dort bricht den Versand ab), höchstens 200 Zeichen; IBAN und BIC mit den Prüfern aus dem SEPA-Mandat (`iban_pruefen` Modulo 97, `bic_pruefen`), normalisiert. Keine Formatprüfung für USt-IdNr., Steuernummer, E-Mail, Website (reine Anzeige). Fehler: 422 „<Label>: <Grund>“, nichts gespeichert (bestehendes Verhalten des Endpunkts). Leer (`""`/`null`) löscht wie bisher. Die Labels in `KNOWN_SETTINGS` werden die der Karte („Firmenname“, „Straße und Hausnummer“, „PLZ und Ort“, „USt-IdNr.“, „Steuernummer“) — bisher hießen sie u. a. „Firmenname (Briefkopf)“, was F-E1 widerspricht und in den 422-Meldungen der Karte stünde.
- **F-E6 — Grußformel:** `COMPANY_NAME`, sonst `EMAILS_FROM_NAME` (derselbe Wert wie im Von-Feld der Mail, mit Rückfall auf die Umgebung wie in `email_service.send_email`), sonst „Ihr Team“. **Der Betreff-Zusatz bleibt am Firmennamen** (`firmenzusatz` unverändert): der Absendername steht schon im Von-Feld. Für Minga heißt der Gruß ab F „MingaGreens GmbH“, ab dem Speichern der Karte der dort eingetragene Firmenname. Folge des Rückfalls: Steht `EMAILS_FROM_NAME` in der Container-Umgebung (Coolify), grüßen ab F alle Mandanten ohne eigenen Firmen- und Absendernamen in der DB mit diesem Wert statt „Ihr Team“ (im Von-Feld steht er schon heute) — Abnahme R1 prüft das.
- **F-E7 — Die SMTP-Karte speichert nur ihre acht Schlüssel** (Nebenbefund 2). Sonst liefe ihr Speichern ab F zusätzlich durch die Firmendaten-Prüfung und könnte an einem fremden Feld mit 422 scheitern.

### Prüfstand (Kopien von `main` @ `df84f7b` per `git archive`, Repo unverändert)

- Basis-Vollauf: `14 failed, 1644 passed, 2 skipped, 1 error`, Fehlernamen = Baseline.
- **Stand dieses Textes, Nachspiel aus dem Plantext** (`/tmp/n0910-kopie-fu`, frische Kopie; Skript `/tmp/n0910-fu-skripte/replay.py` wendet die Blöcke mechanisch mit den hier genannten Ankern an, die Vorbereitung mit genau den Befehlen oben): Vorbereitung alle Ausgaben wie angegeben (9 × `1`, `fehlt`, leer, Hash `9dc4b96…`). F.1 `1 failed, 3 passed` → `4 passed` (Fehlermeldung wie in Step 2); F.2 `6 failed, 5 passed` → `11 passed` (die sechs genannten Tests); F.3 `2 failed, 3 passed` → `5 passed`; alle F-Klassen `20 passed`; F.4 `tsc` genau 1 Fehler (TS2307) → sauber, `npm run build` `✓ built`, geteiltes `node_modules` danach ohne neuere Datei. Alle Prüf-`grep`s wie in den Steps. Umfeld F.1 (`test_documents_preise`, `test_gernot_261008`, `test_storno`, `test_erp`): `195 passed`; Umfeld F.2/F.3 (`test_gernot_261008_paket3`): `467 passed`. Prozedur V: `14 failed, 1664 passed, 2 skipped, 1 error`, Fehlernamen = Baseline (`comm` leer). `ruff --select F821,F823` über die vier geänderten Python-Dateien und die Testdatei: Exit 0. Gegenprobe: mit `escape(wert)` statt `_auszeichnung_maskieren` scheitert `test_sonderzeichen_in_den_firmendaten_erscheinen_im_pdf` an `feld>wald.example` — der Test hält die Wahl fest. Nach F unverändert vorhanden: die Anker von Abschnitt D in `admin.py` (Importzeilen aus `email_service` und `sepa_service`, Kommentar `# Empty/None löscht …`) und `settings_service.py` (`MONATSRECHNUNG_AUTO`) sowie der von Abschnitt O (`<SepaEinstellungenKarte />`).
- **Zweitprüfung (Review) am vorigen Stand dieses Textes** (`/tmp/n0910-kopie-fr`, eigenes Skript): dieselben Zahlen, Namen und Signaturen am Code bestätigt (`iban_pruefen`/`bic_pruefen`/`einstellung_pruefen`, `get_setting`/`set_setting`/`KNOWN_SETTINGS`, `belegversand.firmenname`/`gruss`, `VersandErgebnis(message_id=…)`, `adminApi.listSettings`/`updateSettings`, `AppSettingResponse`, `getErrorMessage(error, fallback)`, `Input` mit `hint`, `Button` mit `icon`/`loading`, Route `/admin/templates`, `_deps_admin`). Die echten Minga-Werte aus der Vorlage bestehen die Prüfung (IBAN DE16701696050003781275, BIC GENODEF1ISE, Steuer-Nr. 143/163/41625). Ihre Hinweise sind eingearbeitet: Maskierung nur `&`/`<` (Nebenbefund 1), Labels wie in der Karte (F-E5), Ladefehler und Nachladen der Karte (F.4), `EMAILS_FROM_NAME` der Umgebung in R1, Runbook-Skript für WAL-Kopien (`immutable=1`).
- Nicht gemessen: Oberfläche im Browser (Abnahme FB1–FB7), Produktionsdaten (Abnahme R1).

### Abhängigkeiten

- **Ausgangsstand:** `main` mit Paket 3 (Belegversand `belegversand.py`, SEPA-Karte, Versandnachweis mit SHA-256) — live seit 09.10.2026. Keine Schemaänderung, keine Migration, kein neuer Endpunkt.
- **Mit anderen Abschnitten:** gemeinsame Testdatei `backend/tests/test_nachtrag_0910.py` (Abschnitt F hängt an; Klassen `TestF1…TestF3`, Helfer `_f_`, keine `autouse`-Fixture). Berührt nur `pdf_service` (neu `_auszeichnung_maskieren` vor `render_company_header_block`, dazu `render_company_header_block`/`render_company_footer_block`), `settings_service` (neu `firmendaten_pruefen` vor `get_setting`; fünf Firmendaten-Labels in `KNOWN_SETTINGS`), `admin.py` (Importzeile aus `settings_service`, ein Aufruf und sein Kommentar in `update_settings`), `belegversand.gruss`, `Settings.tsx` (Firmendaten-Karte, SMTP-Speichern) und eine neue Komponente. **Abschnitt D** fügt in `admin.py` unter der Importzeile aus `email_service` den Import `kontenrahmen` ein (die Zeile aus `sepa_service` bleibt), in `update_settings` einen Block vor dem Löschzweig und hängt in `KNOWN_SETTINGS` hinter `MONATSRECHNUNG_AUTO` an: F lässt genau diese Stellen unverändert, deshalb gehen beide Reihenfolgen. **Abschnitt O** setzt seine Importzeile ebenfalls unter die `SepaEinstellungenKarte`-Importzeile bzw. hinter `<SepaEinstellungenKarte />`; beide Reihenfolgen gehen. Ändert ein anderer Abschnitt dieselben Stellen, gelten die zitierten Anker; Zahlen der Umfeld-Läufe sind auf `df84f7b` gemessen und wachsen mit vorher eingespielten Abschnitten (dann nur „0 failed“ prüfen). Im Gesamtlauf (D vorher) unverändert `195 passed` bzw. `467 passed`.
- **Reihenfolge in F:** F.1 → F.2 → F.3 → F.4 → F.5. F.1 legt die Helfer an, die F.2 und F.3 nutzen. F.4 braucht F.2 nur für die Fehlertexte (Abnahme FB3).
- **Basis F:** vor Task 6 `git rev-parse HEAD` → als `<Basis F>` in den Bericht (Stand nach Task 5; Task 10 vergleicht dagegen).
- **Prozedur V, „Lauf F“, Vorbereitung F:** stehen im Kopf des Plans (Global Constraints, Prozedur V, Vorbereitung vor Task 1).

---

### Task 6 (F.1): PDF — Firmendaten maskieren, Vorrang der Belegvorlage festhalten

**Files:**
- Create oder Append: `backend/tests/test_nachtrag_0910.py` (Block „Abschnitt F“, Teil 1)
- Modify: `backend/app/services/pdf_service.py` (neu `_auszeichnung_maskieren`; `render_company_header_block`, `render_company_footer_block`)

**Interfaces:**
- Produces (Tests): Konstanten `_F_FIRMA` (elf `COMPANY_*`-Werte), `_F_VORLAGE` (`header_text`/`footer_text` wie bei Minga); Fixtures `_f_ohne_umgebung` (löscht `COMPANY_*`/`EMAILS_FROM_NAME` aus der Umgebung), `_f_mails` (fängt `belegversand.send_email` ab, SMTP per Umgebung „konfiguriert“, Liste der Mail-Argumente); Helfer `_f_setze_db(**werte)`, `_f_vorlage(client, belegart, texte=_F_VORLAGE)`, `_f_bestellung`, `_f_rechnung`, `_f_ab`, `_f_rechnungs_pdf`, `_f_text(pdf) -> str`, `_f_ab_senden(client, ab)`. F.2 und F.3 nutzen sie.
- Produces: `pdf_service._auszeichnung_maskieren(wert: str) -> str` — maskiert `&` und `<` (nicht `>`, siehe Nebenbefund 1).
- Verhalten: Werte aus `settings` werden in Kopf- und Fußblock mit `_auszeichnung_maskieren` maskiert. Vorlagentexte (`header_text`, `footer_text`) bleiben unmaskiert (dürfen `<b>`/`<br/>` enthalten). Signaturen unverändert.

**Review Focus (F.1):** Die drei Charakterisierungstests sind schon vor der Änderung grün — sie halten F-E1 fest (bytegleich mit Vorlage, je Block einmal ohne Vorlage, erneutes AB-Senden ohne 409). Rot ist nur der Maskierungstest; er hält auch fest, dass `>` unmaskiert bleibt (ein Textstück wie vor F). PDF-Bytes ändern sich nur bei Werten mit `<` oder mit `&` direkt vor Buchstaben — die wurden bisher falsch gedruckt; ein schon versendeter AB/Lieferschein eines Mandanten **ohne** Vorlagentext mit solchem Wert ließe sich danach nicht erneut senden (409). Für Minga ohne Wirkung (Vorlagentexte, `COMPANY_*` leer).

- [ ] **Step 1: Testblock anhängen**

Genau diesen Block an das Dateiende von `backend/tests/test_nachtrag_0910.py` anhängen (die Datei besteht seit Task 1; eine Leerzeile davor genügt):

<!-- F-BLOCK: f1-tests -->
```python
# ============================================================================
# Abschnitt F — Firmendaten in den Einstellungen speichern auf dem Server
# (Spec 2026-10-08, „Offen (niedrig, 09.10.)" Punkte 1 und 2)
#
# Briefkopf und Fuß der Minga-Belege kommen aus den Belegvorlagen
# (document_templates.texts: header_text, footer_text). pdf_service nimmt je
# Block ENTWEDER den Vorlagentext ODER die Firmendaten (COMPANY_*), nie beide.
# F hält das mit Tests fest, maskiert die Firmendaten im PDF, prüft sie beim
# Speichern und grüßt in Beleg-Mails ohne Firmennamen mit dem Absendernamen.
# Helfer tragen das Präfix _f_, Klassen TestF1…TestF3.
# ============================================================================
import re as _f_re

import pytest

from tests.conftest import TestingSessionLocal
from tests.test_documents_preise import _pdf_text as _f_pdf_roh

_F_FIRMA = {
    "COMPANY_NAME": "Testfarm GmbH",
    "COMPANY_ADDRESS_LINE1": "Feldweg 1",
    "COMPANY_ADDRESS_LINE2": "80000 Muenchen",
    "COMPANY_USTID": "DE123456789",
    "COMPANY_STEUERNR": "143/163/41625",
    "COMPANY_PHONE": "+49 89 1234",
    "COMPANY_EMAIL": "info@testfarm.example",
    "COMPANY_WEBSITE": "www.testfarm.example",
    "COMPANY_BANK_NAME": "Volksbank Test",
    "COMPANY_IBAN": "DE89370400440532013000",
    "COMPANY_BIC": "COBADEFFXXX",
}
# Wie die Minga-Vorlagen: Briefkopf eine Zeile, Fuß mit Bank, Geschäftsführung,
# HRB und Öko-Kontrollnummer (Felder, die COMPANY_* gar nicht kennt).
_F_VORLAGE = {
    "header_text": "Testfarm GmbH · Feldweg 1 · 80000 Muenchen",
    "footer_text": (
        "Volksbank Test - IBAN DE89370400440532013000 - BIC COBADEFFXXX\n"
        "Geschaeftsfuehrung: Erika Muster | HRB 123456 | DE-OEKO-001"
    ),
}


@pytest.fixture
def _f_ohne_umgebung(monkeypatch):
    """Firmendaten und Absendername nur aus der Test-DB, nie vom Rechner."""
    for schluessel in (*_F_FIRMA, "EMAILS_FROM_NAME"):
        monkeypatch.delenv(schluessel, raising=False)


def _f_setze_db(**werte):
    """Setzt Einstellungen direkt in der DB (ohne die Prüfung von PATCH)."""
    from app.services.settings_service import set_setting
    with TestingSessionLocal() as db:
        for schluessel, wert in werte.items():
            set_setting(db, schluessel, wert)
        db.commit()


def _f_vorlage(client, belegart, texte=_F_VORLAGE):
    r = client.patch(f"/api/v1/document-templates/{belegart}", json={"texts": dict(texte)})
    assert r.status_code == 200, r.text


def _f_bestellung(client):
    r = client.post("/api/v1/sales/customers", json={"name": "Oekoring Handels GmbH", "typ": "HANDEL"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": r.json()["id"],
        "requested_delivery_date": "2026-03-05",
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return bestellung


def _f_rechnung(client):
    r = client.post(f"/api/v1/invoices/from-order/{_f_bestellung(client)['id']}")
    assert r.status_code == 201, r.text
    return r.json()


def _f_ab(client):
    r = client.post(f"/api/v1/sales/orders/{_f_bestellung(client)['id']}/confirmations", json={})
    assert r.status_code == 201, r.text
    return r.json()


def _f_rechnungs_pdf(client, rechnung) -> bytes:
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
    assert r.status_code == 200, r.text
    return r.content


def _f_text(pdf: bytes) -> str:
    """Alle Textstücke eines ReportLab-PDFs, mit Leerzeichen verbunden."""
    roh = _f_pdf_roh(pdf).decode("latin-1", errors="ignore")
    return " ".join(_f_re.findall(r"\((.*?)\) Tj", roh))


@pytest.fixture
def _f_mails(monkeypatch):
    """Beleg-Mails abfangen (belegversand.send_email), SMTP 'konfiguriert'."""
    from app.services.email_service import VersandErgebnis
    monkeypatch.setenv("SMTP_HOST", "smtp.farm.example")
    monkeypatch.setenv("SMTP_USER", "versand@farm.example")
    gesendet = []

    def senden(**kw):
        gesendet.append(kw)
        return VersandErgebnis(message_id=f"<f{len(gesendet)}@test.example>")

    monkeypatch.setattr("app.services.belegversand.send_email", senden)
    return gesendet


def _f_ab_senden(client, ab):
    return client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send",
                        json={"to": ["einkauf@oekoring.example"]})


@pytest.mark.usefixtures("_f_ohne_umgebung")
class TestF1PdfBriefkopf:
    """Belegvorlage hat Vorrang; ohne Vorlagentext Firmendaten je Block einmal."""

    def test_mit_vorlage_bleibt_das_pdf_bytegleich(self, client):
        _f_vorlage(client, "RECHNUNG")
        rechnung = _f_rechnung(client)
        vorher = _f_rechnungs_pdf(client, rechnung)

        r = client.patch("/api/v1/admin/settings", json=_F_FIRMA)
        assert r.status_code == 200, r.text
        nachher = _f_rechnungs_pdf(client, rechnung)

        assert nachher == vorher
        text = _f_text(nachher)
        assert text.count("Testfarm GmbH") == 1, text
        assert text.count("DE89370400440532013000") == 1, text
        assert "Erika Muster" in text and "DE-OEKO-001" in text
        assert "DE123456789" not in text and "Minga Greens" not in text

    def test_ohne_vorlagentext_kopf_und_fuss_aus_den_firmendaten(self, client):
        rechnung = _f_rechnung(client)
        r = client.patch("/api/v1/admin/settings", json=_F_FIRMA)
        assert r.status_code == 200, r.text

        text = _f_text(_f_rechnungs_pdf(client, rechnung))

        # Kopf: Name, Straße, Ort. Fuß: Name, „Straße · Ort", Kontakt, Steuer, Bank.
        assert text.count("Testfarm GmbH") == 2, text
        assert text.count("Feldweg 1") == 2, text
        assert text.count("80000 Muenchen") == 2, text
        assert text.count("DE123456789") == 1, text
        assert text.count("DE89370400440532013000") == 1, text
        assert "Minga Greens" not in text

    def test_ab_nach_dem_setzen_der_firmendaten_erneut_sendbar(self, client, _f_mails):
        """Der Versandnachweis vergleicht die PDF-Prüfsumme (Paket 3, Q2): mit
        Vorlagentext ändern die Firmendaten das PDF nicht, also kein 409."""
        _f_vorlage(client, "AUFTRAGSBESTAETIGUNG")
        ab = _f_ab(client)
        assert _f_ab_senden(client, ab).status_code == 200

        assert client.patch("/api/v1/admin/settings", json=_F_FIRMA).status_code == 200
        r = _f_ab_senden(client, ab)

        assert r.status_code == 200, r.text
        erste, zweite = r.json()["dispatches"][:2]
        assert erste["attachment_sha256"] == zweite["attachment_sha256"]
        assert len(_f_mails) == 2

    def test_sonderzeichen_in_den_firmendaten_erscheinen_im_pdf(self, client):
        rechnung = _f_rechnung(client)
        _f_setze_db(COMPANY_NAME="Huber & Soehne <Bio> GmbH",
                    COMPANY_EMAIL="Servus <servus@farm.example>",
                    COMPANY_WEBSITE="feld>wald.example")

        text = _f_text(_f_rechnungs_pdf(client, rechnung))

        # ReportLab schreibt maskierte Zeichen als eigene Textstücke; _f_text
        # verbindet sie mit Leerzeichen — deshalb ohne Leerzeichen vergleichen.
        ohne_leer = text.replace(" ", "")
        assert "Huber&Soehne<Bio>GmbH" in ohne_leer, text
        assert "E-Mail:Servus<servus@farm.example>" in ohne_leer, text
        # ">" bleibt unmaskiert: ReportLab druckt es richtig, und als ein
        # Textstück wie vor F bleiben die PDF-Bytes solcher Werte gleich.
        assert "feld>wald.example" in text, text
```

Prüfen: `grep -c '^class TestF1PdfBriefkopf' backend/tests/test_nachtrag_0910.py` → `1`.

- [ ] **Step 2: Rot bestätigen**

Run: Lauf F mit `TestF1PdfBriefkopf`.
Erwartet: **`1 failed, 3 passed`**; der Fehlschlag ist `test_sonderzeichen_in_den_firmendaten_erscheinen_im_pdf` mit `assert 'Huber&Soehne<Bio>GmbH' in '…Huber&SoehneGmbH…'` (ReportLab verschluckt `<Bio>` und `<servus@farm.example>` still; im Fuß steht `E-Mail: Servus \267 feld>wald.example`).

- [ ] **Step 3: Maskier-Helfer**

In `backend/app/services/pdf_service.py` direkt **vor** der Zeile, die mit

<!-- F-BLOCK: f1-anker-helfer -->
```python
def render_company_header_block(
```

beginnt (in der Datei genau einmal), diesen Block einfügen (die Zeile selbst bleibt):

<!-- F-BLOCK: f1-neu-helfer -->
```python
def _auszeichnung_maskieren(wert: str) -> str:
    """Freitext (Firmendaten, Abschnitt F) für ReportLabs Paragraph-Auszeichnung.

    Maskiert "&" und "<" — sonst verschluckt ReportLab "<...>" still, bricht an
    "<B>" ab oder druckt "AT&T" als "AT&T;". ">" bleibt: ReportLab druckt es
    unmaskiert richtig, maskiert ergäbe es andere PDF-Bytes. So bleiben PDFs mit
    bisher richtig gedruckten Werten bytegleich (Versandnachweis, SHA-256).
    """
    return wert.replace("&", "&amp;").replace("<", "&lt;")


```

- [ ] **Step 4: Briefkopf maskieren**

In derselben Datei, Funktion `render_company_header_block`, die drei Zeilen

<!-- F-BLOCK: f1-alt-kopf -->
```python
    name = settings.get("COMPANY_NAME") or "Minga Greens"
    addr1 = settings.get("COMPANY_ADDRESS_LINE1") or ""
    addr2 = settings.get("COMPANY_ADDRESS_LINE2") or ""
```

ersetzen durch:

<!-- F-BLOCK: f1-neu-kopf -->
```python
    # Firmendaten sind Freitext aus den Einstellungen (Karte "Firmendaten",
    # Abschnitt F): maskieren (_auszeichnung_maskieren). Der Vorlagentext
    # (header_text) bleibt unmaskiert, er darf <b> und <br/> enthalten.
    name = _auszeichnung_maskieren(settings.get("COMPANY_NAME") or "Minga Greens")
    addr1 = _auszeichnung_maskieren(settings.get("COMPANY_ADDRESS_LINE1") or "")
    addr2 = _auszeichnung_maskieren(settings.get("COMPANY_ADDRESS_LINE2") or "")
```

- [ ] **Step 5: Fuß maskieren**

In derselben Datei, Funktion `render_company_footer_block`, die Zeile (in der Datei genau einmal)

<!-- F-BLOCK: f1-alt-fuss -->
```python
    parts: list[str] = []
```

ersetzen durch:

<!-- F-BLOCK: f1-neu-fuss -->
```python
    # Maskiert wie im Briefkopf (_auszeichnung_maskieren, Abschnitt F).
    settings = {k: _auszeichnung_maskieren(v) for k, v in settings.items() if isinstance(v, str)}
    parts: list[str] = []
```

Prüfen: `grep -c '^def _auszeichnung_maskieren(wert: str) -> str:$' backend/app/services/pdf_service.py` → `1`; `grep -c '_auszeichnung_maskieren(settings.get("COMPANY_' backend/app/services/pdf_service.py` → `3`; `grep -c 'settings = {k: _auszeichnung_maskieren(v) for k, v in settings.items() if isinstance(v, str)}' backend/app/services/pdf_service.py` → `1`. Den Aufruf von `render_company_footer_block`, den Import von `escape` und die Vorlagentext-Zweige in `generate_invoice_pdf`, `_build_document` und `generate_payment_reminder_pdf` **nicht** ändern.

- [ ] **Step 6: Grün bestätigen**

Run: wie Step 2. Erwartet: **`4 passed`**.

- [ ] **Step 7: Umfeld**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_documents_preise.py tests/test_gernot_261008.py tests/test_storno.py tests/test_erp.py -q -p no:cacheprovider 2>&1 | tail -1`
Erwartet: kein Fehlschlag. Gemessen auf `df84f7b` und im Gesamtlauf nach D: `195 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/test_nachtrag_0910.py
git commit -m "fix(pdf): Firmendaten im Briefkopf und Fuss maskiert; Vorrang der Belegvorlage mit Tests festgehalten (F)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7 (F.2): Schnittstelle — Firmendaten beim Speichern prüfen

**Files:**
- Modify: `backend/app/services/settings_service.py` (neu `FIRMENDATEN_KEYS`, `FIRMENDATEN_MAX_LAENGE`, `firmendaten_pruefen` vor `get_setting`; fünf Labels in `KNOWN_SETTINGS`)
- Modify: `backend/app/api/v1/admin.py` (Importzeile aus `settings_service`, Aufruf in `update_settings`)
- Append: `backend/tests/test_nachtrag_0910.py` (Teil 2)

**Interfaces:**
- Produces: `settings_service.FIRMENDATEN_KEYS: tuple[str, ...]` (die elf Schlüssel der Karte, ohne `COMPANY_SEPA_GLAEUBIGER_ID`), `settings_service.FIRMENDATEN_MAX_LAENGE = 200`, `settings_service.firmendaten_pruefen(key: str, wert: str) -> str` (zu speichernder Wert oder `ValueError` mit Klartext; andere Schlüssel unverändert, wie `sepa_service.einstellung_pruefen`). `update_settings` ruft `einstellung_pruefen(key, firmendaten_pruefen(key, raw_value))`; die Importzeile `from app.services.sepa_service import einstellung_pruefen` bleibt (Anker von Abschnitt D).
- `KNOWN_SETTINGS`: Labels von `COMPANY_NAME`, `COMPANY_ADDRESS_LINE1`, `COMPANY_ADDRESS_LINE2`, `COMPANY_USTID`, `COMPANY_STEUERNR` wie in der Karte (F-E5). Nur Anzeige: kein Code und kein Test liest diese Texte außer `list_settings` und der 422-Meldung.
- `PATCH /api/v1/admin/settings`: unverändert bis auf die Prüfung — 422 `"<Label>: <Grund>"` (z. B. `"IBAN: IBAN-Prüfziffer stimmt nicht"`, `"Firmenname: nur eine Zeile erlaubt"`), dann wird **kein** Schlüssel des Aufrufs gespeichert. `""`/`null` löscht wie bisher. Rechte unverändert: Router `admin` mit `_deps_admin` (nur `admin`, lesen und schreiben).
- Test-Helfer `_f_als(rollen)` (setzt das Login bis zum Testende auf genau diese Rollen; der `client`-Teardown entfernt es).

- [ ] **Step 1: Testblock anhängen**

Genau diesen Block an das Dateiende von `backend/tests/test_nachtrag_0910.py` anhängen:

<!-- F-BLOCK: f2-tests -->
```python
def _f_als(rollen):
    from app.api.deps import get_current_user
    from app.main import app

    async def override():
        return {"id": "123e4567-e89b-12d3-a456-426614174077", "username": "f",
                "email": "f@farm.example", "roles": rollen}
    app.dependency_overrides[get_current_user] = override


@pytest.mark.usefixtures("_f_ohne_umgebung")
class TestF2FirmendatenSpeichern:
    """PATCH /admin/settings prüft die Firmendaten (Karte „Firmendaten")."""

    def _werte(self, client):
        r = client.get("/api/v1/admin/settings")
        assert r.status_code == 200, r.text
        return {s["key"]: s for s in r.json()}

    def test_alle_felder_speichern_normalisiert(self, client):
        r = client.patch("/api/v1/admin/settings", json={
            **_F_FIRMA,
            "COMPANY_NAME": "  Testfarm GmbH ",
            "COMPANY_IBAN": "de89 3704 0044 0532 0130 00",
            "COMPANY_BIC": "cobadeffxxx",
        })

        assert r.status_code == 200, r.text
        werte = self._werte(client)
        assert {k: werte[k]["value"] for k in _F_FIRMA} == _F_FIRMA
        assert {werte[k]["source"] for k in _F_FIRMA} == {"db"}
        # Labels wie in der Karte — sie stehen in den 422-Meldungen.
        assert [werte[k]["label"] for k in list(_F_FIRMA)[:5]] == [
            "Firmenname", "Straße und Hausnummer", "PLZ und Ort", "USt-IdNr.", "Steuernummer"]

    def test_falsche_iban_422_und_nichts_gespeichert(self, client):
        r = client.patch("/api/v1/admin/settings", json={
            "COMPANY_NAME": "Testfarm GmbH", "COMPANY_IBAN": "DE89370400440532013001"})

        assert r.status_code == 422, r.text
        assert r.json()["detail"] == "IBAN: IBAN-Prüfziffer stimmt nicht"
        assert self._werte(client)["COMPANY_NAME"]["source"] != "db"

    def test_falsche_bic_422(self, client):
        r = client.patch("/api/v1/admin/settings", json={"COMPANY_BIC": "COBA"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"].startswith("BIC: BIC hat kein gültiges Format")

    @pytest.mark.parametrize("wert,meldung", [
        ("Testfarm\nGmbH", "nur eine Zeile"),
        ("x" * 201, "höchstens 200 Zeichen"),
        ("   ", "nur Leerzeichen"),
    ], ids=["zeilenumbruch", "zu_lang", "nur_leerzeichen"])
    def test_unbrauchbarer_firmenname_422(self, client, wert, meldung):
        r = client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": wert})
        assert r.status_code == 422, r.text
        assert r.json()["detail"].startswith(f"Firmenname: {meldung}"), r.text

    def test_leerer_wert_loescht_wie_bisher(self, client):
        assert client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": "Testfarm GmbH"}).status_code == 200
        assert client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": ""}).status_code == 200
        assert self._werte(client)["COMPANY_NAME"]["has_value"] is False

    @pytest.mark.parametrize("rolle", ["sales", "accounting", "production_planner", "production_staff"])
    def test_nur_admin(self, client, rolle):
        _f_als([rolle])
        assert client.get("/api/v1/admin/settings").status_code == 403
        r = client.patch("/api/v1/admin/settings", json={"COMPANY_NAME": "Testfarm GmbH"})
        assert r.status_code == 403, r.text
```

- [ ] **Step 2: Rot bestätigen**

Run: Lauf F mit `TestF2FirmendatenSpeichern`.
Erwartet: **`6 failed, 5 passed`**. Fehlschläge: `test_alle_felder_speichern_normalisiert` (Dict-Vergleich: `COMPANY_IBAN` `'de89 3704 0044 0532 0130 00'`, `COMPANY_BIC` `'cobadeffxxx'`, `COMPANY_NAME` `'  Testfarm GmbH '`), `test_falsche_iban_422_und_nichts_gespeichert` und `test_falsche_bic_422` sowie `test_unbrauchbarer_firmenname_422[zeilenumbruch|zu_lang|nur_leerzeichen]` (je `assert 200 == 422`, Text `{"changed":…}`). Grün schon jetzt: `test_leerer_wert_loescht_wie_bisher`, `test_nur_admin[sales|accounting|production_planner|production_staff]`.

- [ ] **Step 3: Prüfer in `settings_service`**

In `backend/app/services/settings_service.py` direkt **vor** der Zeile

<!-- F-BLOCK: f2-anker-settings -->
```python
def get_setting(db: Session, key: str, env_fallback: bool = True) -> Optional[str]:
```

diesen Block einfügen (die Zeile selbst bleibt):

<!-- F-BLOCK: f2-neu-settings -->
```python
#: Felder der Karte "Firmendaten" in den Einstellungen (Abschnitt F). Die
#: Gläubiger-ID gehört zur Karte "SEPA-Lastschrift" und hat ihre eigene
#: Prüfung (sepa_service.einstellung_pruefen).
FIRMENDATEN_KEYS = (
    "COMPANY_NAME", "COMPANY_ADDRESS_LINE1", "COMPANY_ADDRESS_LINE2",
    "COMPANY_USTID", "COMPANY_STEUERNR", "COMPANY_PHONE", "COMPANY_EMAIL",
    "COMPANY_WEBSITE", "COMPANY_BANK_NAME", "COMPANY_IBAN", "COMPANY_BIC",
)
FIRMENDATEN_MAX_LAENGE = 200


def firmendaten_pruefen(key: str, wert: str) -> str:
    """Prüfer für PATCH /admin/settings (nicht leerer Wert), läuft vor
    sepa_service.einstellung_pruefen: gibt den zu speichernden Wert zurück
    oder wirft ValueError mit Klartext. Andere Schlüssel unverändert.

    Firmendaten: eine Zeile (der Firmenname steht im Betreff der Beleg-Mails;
    ein Zeilenumbruch im Betreff bricht den Versand ab), ohne Rand-Leerzeichen,
    höchstens FIRMENDATEN_MAX_LAENGE Zeichen; IBAN und BIC wie im SEPA-Mandat
    geprüft und normalisiert.
    """
    if key not in FIRMENDATEN_KEYS:
        return wert
    from app.services.sepa_service import bic_pruefen, iban_pruefen

    wert = wert.strip()
    if not wert:
        raise ValueError("nur Leerzeichen — zum Löschen das Feld leer lassen")
    if "\n" in wert or "\r" in wert:
        raise ValueError("nur eine Zeile erlaubt")
    if len(wert) > FIRMENDATEN_MAX_LAENGE:
        raise ValueError(f"höchstens {FIRMENDATEN_MAX_LAENGE} Zeichen")
    if key == "COMPANY_IBAN":
        return iban_pruefen(wert)
    if key == "COMPANY_BIC":
        return bic_pruefen(wert)
    return wert


```

(Import von `sepa_service` in der Funktion: `sepa_service` importiert `settings_service` selbst lokal; so bleibt es ohne Zirkel.)

- [ ] **Step 4: Labels der Firmendaten**

In derselben Datei, in `KNOWN_SETTINGS`, die sechs Zeilen

<!-- F-BLOCK: f2-alt-labels -->
```python
    # Firmendaten — landen auf allen Belegen (§ 14 UStG)
    "COMPANY_NAME":         {"is_secret": False, "label": "Firmenname (Briefkopf)"},
    "COMPANY_ADDRESS_LINE1": {"is_secret": False, "label": "Adresse Zeile 1 (Straße)"},
    "COMPANY_ADDRESS_LINE2": {"is_secret": False, "label": "Adresse Zeile 2 (PLZ Ort)"},
    "COMPANY_USTID":        {"is_secret": False, "label": "USt-IdNr. (DEXXXXXXXX)"},
    "COMPANY_STEUERNR":     {"is_secret": False, "label": "Steuernummer (alternativ zur USt-IdNr.)"},
```

ersetzen durch:

<!-- F-BLOCK: f2-neu-labels -->
```python
    # Firmendaten (Karte "Firmendaten", Abschnitt F). Auf Belegen (§ 14 UStG)
    # nur, wo die Belegvorlage keinen eigenen Briefkopf bzw. keine eigene
    # Fußzeile hat. Labels wie in der Karte: sie stehen in den 422-Meldungen.
    "COMPANY_NAME":         {"is_secret": False, "label": "Firmenname"},
    "COMPANY_ADDRESS_LINE1": {"is_secret": False, "label": "Straße und Hausnummer"},
    "COMPANY_ADDRESS_LINE2": {"is_secret": False, "label": "PLZ und Ort"},
    "COMPANY_USTID":        {"is_secret": False, "label": "USt-IdNr."},
    "COMPANY_STEUERNR":     {"is_secret": False, "label": "Steuernummer"},
```

Die übrigen Einträge (auch Telefon, E-Mail, Website, Bank, IBAN, BIC und `MONATSRECHNUNG_AUTO` samt schließender Klammer) bleiben.

- [ ] **Step 5: Endpunkt nutzt den Prüfer**

In `backend/app/api/v1/admin.py` drei Stellen (je genau einmal vorhanden):

1. `from app.services.settings_service import KNOWN_SETTINGS, get_setting, set_setting` → `from app.services.settings_service import KNOWN_SETTINGS, firmendaten_pruefen, get_setting, set_setting`
2. In `update_settings`: `            raw_value = einstellung_pruefen(key, raw_value)` → `            raw_value = einstellung_pruefen(key, firmendaten_pruefen(key, raw_value))`
3. Kommentar darüber: `        # Inhaltsprüfung je Schlüssel (z. B. Gläubiger-ID). Bei Fehler wird` → `        # Inhaltsprüfung je Schlüssel (Firmendaten, Gläubiger-ID). Bei Fehler wird`

Die Zeile `from app.services.sepa_service import einstellung_pruefen` bleibt unverändert (sie wird weiter gebraucht; Abschnitt D ankert an der Zeile aus `email_service` darüber).

Prüfen: `grep -n 'einstellung_pruefen\|firmendaten_pruefen' backend/app/api/v1/admin.py` → genau drei Treffer: die unveränderte Importzeile aus `sepa_service`, die Importzeile aus `settings_service`, der Aufruf `einstellung_pruefen(key, firmendaten_pruefen(key, raw_value))`.

- [ ] **Step 6: Grün bestätigen**

Run: wie Step 2. Erwartet: **`11 passed`**. Zusätzlich Lauf F mit `TestF1PdfBriefkopf` → `4 passed`.

- [ ] **Step 7: Umfeld und Prozedur V**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -q -p no:cacheprovider 2>&1 | tail -1` → kein Fehlschlag (gemessen `467 passed`; enthält `TestQ5Einstellungen`, Gläubiger-ID über denselben Endpunkt).
Prozedur V → kein Abgleich-Eintrag.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/settings_service.py backend/app/api/v1/admin.py backend/tests/test_nachtrag_0910.py
git commit -m "feat(einstellungen): Firmendaten beim Speichern geprueft, IBAN und BIC normalisiert, Labels wie in der Karte (F)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8 (F.3): Beleg-Mails — Grußformel mit dem Absendernamen

**Files:**
- Modify: `backend/app/services/belegversand.py` (neu `absendername`, `gruss`)
- Append: `backend/tests/test_nachtrag_0910.py` (Teil 3)

**Interfaces:**
- Produces: `belegversand.absendername(db) -> str` — `firmenname(db)`, sonst `get_setting(db, "EMAILS_FROM_NAME")` (mit Umgebungs-Rückfall wie `send_email`), getrimmt, sonst `""`.
- `gruss(db) -> str` gleiche Signatur; nutzt `absendername`. Aufrufer unverändert: `documents.py` (AB, Lieferschein), `invoices.py` (Rechnung, Stornorechnung, Leergutabrechnung).
- Unverändert: `firmenname`, `firmenzusatz` (Betreff nur mit `COMPANY_NAME`, F-E6).

- [ ] **Step 1: Testblock anhängen**

Genau diesen Block an das Dateiende anhängen:

<!-- F-BLOCK: f3-tests -->
```python
@pytest.mark.usefixtures("_f_ohne_umgebung")
class TestF3MailGruss:
    """Grußformel: Firmenname, sonst Absendername (EMAILS_FROM_NAME), sonst „Ihr Team"."""

    def test_ohne_firmenname_gruesst_der_absendername(self, client, _f_mails):
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand")
        assert _f_ab_senden(client, _f_ab(client)).status_code == 200
        assert _f_mails[0]["body"].endswith("Mit freundlichen Grüßen\nTestfarm Versand")

    def test_rechnungsmail_gruesst_den_absendernamen(self, client, _f_mails):
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand")
        rechnung = _f_rechnung(client)
        r = client.post(f"/api/v1/invoices/{rechnung['id']}/send",
                        json={"to": ["rechnung@oekoring.example"]})
        assert r.status_code == 200, r.text
        assert _f_mails[0]["body"].rstrip().endswith("Mit freundlichen Grüßen\nTestfarm Versand")

    def test_firmenname_vor_dem_absendernamen(self, client, _f_mails):
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand", COMPANY_NAME="Testfarm GmbH")
        assert _f_ab_senden(client, _f_ab(client)).status_code == 200
        assert _f_mails[0]["body"].endswith("Mit freundlichen Grüßen\nTestfarm GmbH")

    def test_ohne_beides_ihr_team(self, client, _f_mails):
        assert _f_ab_senden(client, _f_ab(client)).status_code == 200
        assert _f_mails[0]["body"].endswith("Mit freundlichen Grüßen\nIhr Team")

    def test_betreff_ohne_firmenname_ohne_zusatz(self, client, _f_mails):
        """Der Absendername steht schon im Von-Feld — der Betreff bekommt
        seinen Zusatz weiter nur vom Firmennamen."""
        _f_setze_db(EMAILS_FROM_NAME="Testfarm Versand")
        ab = _f_ab(client)
        assert _f_ab_senden(client, ab).status_code == 200
        assert _f_mails[0]["subject"] == f"Auftragsbestätigung {ab['confirmation_number']}"
```

- [ ] **Step 2: Rot bestätigen**

Run: Lauf F mit `TestF3MailGruss`.
Erwartet: **`2 failed, 3 passed`**: `test_ohne_firmenname_gruesst_der_absendername` und `test_rechnungsmail_gruesst_den_absendernamen`, je `assert False` aus `endswith('Mit freundlichen Grüßen\nTestfarm Versand')` (die Mail endet mit `…Ihr Team`).

- [ ] **Step 3: `absendername` und `gruss`**

In `backend/app/services/belegversand.py` die Funktion

<!-- F-BLOCK: f3-alt -->
```python
def gruss(db: Session) -> str:
    name = firmenname(db)
    return f"Mit freundlichen Grüßen\n{name}" if name else "Mit freundlichen Grüßen\nIhr Team"
```

ersetzen durch:

<!-- F-BLOCK: f3-neu -->
```python
def absendername(db: Session) -> str:
    """Name unter der Grußformel: der Firmenname, sonst der Absender-Name
    der Mails (EMAILS_FROM_NAME — derselbe Wert wie im Von-Feld, auch aus der
    Umgebung), sonst leer (Abschnitt F)."""
    from app.services.settings_service import get_setting
    return firmenname(db) or (get_setting(db, "EMAILS_FROM_NAME") or "").strip()


def gruss(db: Session) -> str:
    name = absendername(db)
    return f"Mit freundlichen Grüßen\n{name}" if name else "Mit freundlichen Grüßen\nIhr Team"
```

- [ ] **Step 4: Grün bestätigen**

Run: wie Step 2. Erwartet: **`5 passed`**. Alle drei Klassen zusammen: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py::TestF1PdfBriefkopf tests/test_nachtrag_0910.py::TestF2FirmendatenSpeichern tests/test_nachtrag_0910.py::TestF3MailGruss -q -p no:cacheprovider 2>&1 | tail -1` → `20 passed`.

- [ ] **Step 5: Umfeld und Prozedur V**

Umfeld wie F.2 Step 7 (`test_gernot_261008_paket3.py`, u. a. `test_firmenname_aus_den_einstellungen` für AB und Rechnung) → kein Fehlschlag. Prozedur V → kein Abgleich-Eintrag; gemessen im Gesamtlauf (nach D) `14 failed, 1701 passed, 2 skipped, 1 error` (F allein auf `df84f7b`: `1664 passed`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/belegversand.py backend/tests/test_nachtrag_0910.py
git commit -m "feat(versand): Grussformel ohne Firmennamen mit dem Absendernamen statt Ihr Team (F)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9 (F.4): Oberfläche — Karte „Firmendaten“ liest und schreibt den Server

**Files:**
- Create: `frontend/src/components/domain/FirmendatenKarte.tsx`
- Modify: `frontend/src/pages/Settings.tsx` (Importe; Zustand `company`, `handleSaveCompany` und Karte entfernen; `SmtpSettingsCard` speichert nur ihre Schlüssel)

**Interfaces:**
- Produces: `export function FirmendatenKarte()` — nutzt `adminApi.listSettings()`/`adminApi.updateSettings()` (unverändert) und den Query-Key `['admin-settings']` (geteilt mit Saison-, Monatsrechnungs-, SMTP- und SEPA-Karte). Sendet genau die elf Firmendaten-Schlüssel (`wert.trim() || null`). Erst nach erfolgreichem PATCH: Browser-Eintrag löschen, Toast „Firmendaten gespeichert“, Liste neu laden (`setQueryData`, Felder zeigen den normalisierten Stand); scheitert nur dieses Nachladen, bleibt es bei „gespeichert“ plus Hinweis „Seite neu laden“ (kein „Speichern fehlgeschlagen“). Ladefehler ohne Daten: „Firmendaten ließen sich nicht laden: <Meldung>“.
- `Settings.tsx`: neue Konstante `SMTP_KEYS` (acht Schlüssel) vor `SmtpSettingsCard`; „Speichern“ der SMTP-Karte schickt nur diese.
- Keine Änderung an `services/api.ts`, `types/index.ts`, Routen oder Navigation (Einstellungen bleiben `roles: ['ADMIN']`).

**Review Focus (F.4):** Kein automatischer Test (keine Frontend-Tests im Repo) — Abnahme FB1–FB7.

- [ ] **Step 1: `Settings.tsx` umstellen**

In `frontend/src/pages/Settings.tsx` (alle Anker je genau einmal vorhanden):

1. Importzeile ersetzen:

<!-- F-BLOCK: f4-alt-icons -->
```tsx
import { Database, Server, Key, Bell, Pencil, Building2, Save, Globe, Hash, Mail, Send, Plug, CheckCircle2, XCircle, ShoppingBag } from 'lucide-react';
```

durch:

<!-- F-BLOCK: f4-neu-icons -->
```tsx
import { Database, Server, Key, Bell, Pencil, Save, Mail, Send, Plug, CheckCircle2, XCircle, ShoppingBag } from 'lucide-react';
```

2. Direkt unter der Zeile `import { SepaEinstellungenKarte } from '../components/domain/SepaEinstellungenKarte';` diese Zeile einfügen:

<!-- F-BLOCK: f4-neu-import -->
```tsx
import { FirmendatenKarte } from '../components/domain/FirmendatenKarte';
```

3. Den Bereich von der Zeile `  const [company, setCompany] = useState(() => {` bis **vor** die Zeile `  const [notifications, setNotifications] = useState(() => {` löschen (Zustand der alten Karte samt Beispielwerten und der Leerzeile danach).
4. Den Bereich von der Zeile `  const handleSaveCompany = () => {` bis **vor** die Zeile `  const handleSaveNotifications = () => {` löschen.
5. Den Bereich von der Zeile `        {/* Company Profile */}` bis **vor** die Zeile `        {/* System Info */}` ersetzen durch:

<!-- F-BLOCK: f4-neu-karte -->
```tsx
        {/* Firmendaten — auf dem Server (Abschnitt F) */}
        <FirmendatenKarte />

```

6. Die Zeile `export function SmtpSettingsCard() {` ersetzen durch:

<!-- F-BLOCK: f4-neu-smtp-keys -->
```tsx
// Schlüssel der SMTP-Karte. „Speichern“ schickt nur sie — vorher schickte die
// Karte jede bekannte Einstellung mit dem zuletzt geladenen Wert zurück, auch
// Werte aus Umgebungsvariablen (Firmendaten, Gläubiger-ID, Monatsrechnungen).
const SMTP_KEYS = [
  'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD', 'SMTP_USE_TLS',
  'SMTP_USE_SSL', 'EMAILS_FROM_EMAIL', 'EMAILS_FROM_NAME',
];

export function SmtpSettingsCard() {
```

7. Im `onClick` des Speichern-Knopfs der SMTP-Karte die Zeile `              data.forEach((s) => {` (14 Leerzeichen; die Zeile darunter ist `                const current = edit[s.key] ?? '';`) ersetzen durch:

<!-- F-BLOCK: f4-neu-smtp-filter -->
```tsx
              data.filter((s) => SMTP_KEYS.includes(s.key)).forEach((s) => {
```

(Das `data.forEach((s) => {` mit 4 Leerzeichen im `useEffect` derselben Karte bleibt.)

Prüfen: `grep -n "minga_settings_company\|handleSaveCompany\|Company Profile\|Building2\|Globe\|Hash" frontend/src/pages/Settings.tsx` → keine Ausgabe; `grep -c "FirmendatenKarte\|SMTP_KEYS" frontend/src/pages/Settings.tsx` → `4`.

- [ ] **Step 2: Rot bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: genau **1** Fehler: `src/pages/Settings.tsx(…): error TS2307: Cannot find module '../components/domain/FirmendatenKarte' or its corresponding type declarations.`

- [ ] **Step 3: Komponente anlegen**

`frontend/src/components/domain/FirmendatenKarte.tsx` mit genau diesem Inhalt anlegen:

<!-- F-BLOCK: f4-karte -->
```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, Save } from 'lucide-react';
import { adminApi } from '../../services/api';
import type { AppSettingResponse } from '../../services/api';
import { getErrorMessage } from '../../services/errors';
import { Button, Input, useToast } from '../ui';

/**
 * Karte „Firmendaten“ in den Einstellungen (Abschnitt F, Spec 08.10.2026).
 *
 * Liest und schreibt die Firmendaten des Mandanten über GET/PATCH
 * /admin/settings (COMPANY_*; der Router lässt nur Admins zu). Bis Oktober
 * 2026 speicherte die Karte nur im Browser (localStorage
 * 'minga_settings_company'). Was dort steht, wird einmalig als Vorschlag in
 * leere Felder übernommen und erst mit „Speichern“ auf den Server geschrieben;
 * danach ist der Browser-Eintrag gelöscht.
 *
 * Vorrang: Hat eine Belegvorlage einen eigenen Briefkopf bzw. eine eigene
 * Fußzeile, druckt das PDF nur diesen Text (pdf_service) — die Firmendaten
 * erscheinen dort dann gar nicht, also auch nicht doppelt. Die Gläubiger-ID
 * pflegt die Karte „SEPA-Lastschrift“.
 */

const FELDER = [
  { key: 'COMPANY_NAME', label: 'Firmenname' },
  { key: 'COMPANY_ADDRESS_LINE1', label: 'Straße und Hausnummer' },
  { key: 'COMPANY_ADDRESS_LINE2', label: 'PLZ und Ort' },
  { key: 'COMPANY_USTID', label: 'USt-IdNr.' },
  { key: 'COMPANY_STEUERNR', label: 'Steuernummer' },
  { key: 'COMPANY_EMAIL', label: 'E-Mail' },
  { key: 'COMPANY_PHONE', label: 'Telefon' },
  { key: 'COMPANY_WEBSITE', label: 'Website' },
  { key: 'COMPANY_BANK_NAME', label: 'Bank' },
  { key: 'COMPANY_IBAN', label: 'IBAN' },
  { key: 'COMPANY_BIC', label: 'BIC' },
] as const;

type FeldKey = (typeof FELDER)[number]['key'];
type Werte = Record<FeldKey, string>;

const ALT_SCHLUESSEL = 'minga_settings_company';
// Vorbelegung der alten Browser-Karte: Beispielwerte, nie echte Firmendaten.
const ALT_BEISPIELE = new Set([
  'Minga Greens GmbH', 'Breisacher Str. 12, 81667 München', 'DE328451962',
  'info@minga-greens.de', '+49 89 123 456 0', 'www.minga-greens.de',
]);

function leer(): Werte {
  return Object.fromEntries(FELDER.map((f) => [f.key, ''])) as Werte;
}

/** Werte der alten Browser-Karte, ohne leere Felder und ohne ihre Beispielwerte. */
function altVorschlag(): Partial<Werte> {
  let alt: Record<string, unknown>;
  try {
    alt = JSON.parse(localStorage.getItem(ALT_SCHLUESSEL) || '{}') || {};
  } catch {
    return {};
  }
  const wert = (k: string): string => {
    const v = alt[k];
    return typeof v === 'string' && v.trim() && !ALT_BEISPIELE.has(v.trim()) ? v.trim() : '';
  };
  const vorschlag: Partial<Werte> = {};
  if (wert('name')) vorschlag.COMPANY_NAME = wert('name');
  const adresse = wert('address');
  if (adresse) {
    // Die alte Karte hatte ein Feld „Straße 1, 12345 Ort“ — hier zwei Zeilen.
    const komma = adresse.lastIndexOf(',');
    if (komma > 0) {
      vorschlag.COMPANY_ADDRESS_LINE1 = adresse.slice(0, komma).trim();
      vorschlag.COMPANY_ADDRESS_LINE2 = adresse.slice(komma + 1).trim();
    } else {
      vorschlag.COMPANY_ADDRESS_LINE1 = adresse;
    }
  }
  if (wert('taxId')) vorschlag.COMPANY_USTID = wert('taxId');
  if (wert('email')) vorschlag.COMPANY_EMAIL = wert('email');
  if (wert('phone')) vorschlag.COMPANY_PHONE = wert('phone');
  if (wert('website')) vorschlag.COMPANY_WEBSITE = wert('website');
  return vorschlag;
}

/** Gespeicherte Werte des Mandanten. Nur source 'db': eine Umgebungsvariable
 *  gilt für alle Mandanten im Container und erscheint nur als Hinweis — ein
 *  Speichern übernähme sie sonst still in diesen Mandanten. */
function ausServer(data: AppSettingResponse[]): Werte {
  const werte = leer();
  for (const f of FELDER) {
    const s = data.find((x) => x.key === f.key);
    if (s && s.source === 'db') werte[f.key] = s.value || '';
  }
  return werte;
}

export function FirmendatenKarte() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, error } = useQuery({ queryKey: ['admin-settings'], queryFn: () => adminApi.listSettings() });
  const [werte, setWerte] = useState<Werte | null>(null);
  const [vorschlag, setVorschlag] = useState<FeldKey[]>([]);

  useEffect(() => {
    // Nur beim ersten Laden befüllen: andere Karten speichern ebenfalls über
    // /admin/settings und laden die Liste neu — ungespeicherte Eingaben hier
    // gehen dabei nicht verloren.
    if (!data || werte !== null) return;
    const start = ausServer(data);
    const alt = altVorschlag();
    const uebernommen = FELDER.map((f) => f.key).filter((k) => !start[k] && alt[k]);
    for (const k of uebernommen) start[k] = alt[k] as string;
    setWerte(start);
    setVorschlag(uebernommen);
  }, [data, werte]);

  const speichern = useMutation({
    mutationFn: (w: Werte) =>
      adminApi.updateSettings(Object.fromEntries(FELDER.map((f) => [f.key, w[f.key].trim() || null]))),
    onSuccess: async () => {
      localStorage.removeItem(ALT_SCHLUESSEL);
      setVorschlag([]);
      toast.success('Firmendaten gespeichert');
      // Der Server normalisiert (IBAN, BIC, Rand-Leerzeichen): gespeicherten Stand
      // zeigen. Scheitert nur dieses Nachladen, ist trotzdem gespeichert.
      try {
        const frisch = await adminApi.listSettings();
        queryClient.setQueryData(['admin-settings'], frisch);
        setWerte(ausServer(frisch));
      } catch {
        toast.error('Gespeichert, aber der neue Stand ließ sich nicht laden — bitte die Seite neu laden.');
      }
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Speichern fehlgeschlagen')),
  });

  const verwerfen = () => {
    localStorage.removeItem(ALT_SCHLUESSEL);
    setVorschlag([]);
    if (data) setWerte(ausServer(data));
  };

  if (!data || werte === null) {
    // Ein Ladefehler zählt nur ohne Daten: scheitert ein Nachladen im
    // Hintergrund, bleiben Karte und ungespeicherte Eingaben stehen.
    return (
      <div className="card lg:col-span-2">
        <div className={`card-body text-sm ${!data && error ? 'text-red-600 dark:text-red-400' : 'text-gray-500'}`}>
          {!data && error
            ? `Firmendaten ließen sich nicht laden: ${getErrorMessage(error, 'unbekannter Fehler')}`
            : 'Lädt Firmendaten…'}
        </div>
      </div>
    );
  }

  const umgebung = (key: FeldKey): string | undefined => {
    const s = data.find((x) => x.key === key);
    return s && s.source === 'env' && s.value ? `Vorgabe des Servers: ${s.value}` : undefined;
  };

  return (
    <div className="card lg:col-span-2">
      <div className="card-header">
        <h3 className="card-title flex items-center gap-2">
          <Building2 className="w-5 h-5 text-minga-600 dark:text-minga-400" />
          Firmendaten
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Gespeichert für alle Benutzer dieses Arbeitsbereichs. Verwendet für Grußformel und Betreff
          der Beleg-Mails und für Belege, deren Belegvorlage keinen eigenen Briefkopf bzw. keine
          eigene Fußzeile hat. Steht dort ein eigener Text, druckt der Beleg nur diesen — nichts
          erscheint doppelt. Briefkopf und Fußzeile pflegen Sie unter{' '}
          <Link to="/admin/templates" className="underline">Belegvorlagen</Link>, die
          Gläubiger-ID unter „SEPA-Lastschrift“.
        </p>
      </div>
      <div className="card-body space-y-4">
        {vorschlag.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
            <p>
              Diese Angaben waren bisher nur in diesem Browser gespeichert, noch nicht auf dem
              Server: {vorschlag.map((k) => FELDER.find((f) => f.key === k)?.label).join(', ')}.
              Bitte prüfen und mit „Speichern“ übernehmen.
            </p>
            <button type="button" className="mt-2 underline" onClick={verwerfen}>
              Vorschlag verwerfen
            </button>
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {FELDER.map((f) => (
            <Input
              key={f.key}
              label={f.label}
              type={f.key === 'COMPANY_EMAIL' ? 'email' : 'text'}
              value={werte[f.key]}
              hint={umgebung(f.key)}
              onChange={(e) => setWerte({ ...werte, [f.key]: e.target.value })}
            />
          ))}
        </div>
        <div className="flex justify-end">
          <Button
            icon={<Save className="w-4 h-4" />}
            loading={speichern.isPending}
            onClick={() => speichern.mutate(werte)}
          >
            Speichern
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe. `cd frontend && npm run build` → endet mit `✓ built in …` (Warnung „Some chunks are larger than 500 kB“ ist Altbestand).
Prüfen: `grep -rn "minga_settings_company" frontend/src` → nur `frontend/src/components/domain/FirmendatenKarte.tsx` (Konstante `ALT_SCHLUESSEL` und Kommentar).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/domain/FirmendatenKarte.tsx frontend/src/pages/Settings.tsx
git commit -m "feat(einstellungen): Karte Firmendaten speichert auf dem Server; Browser-Werte einmalig als Vorschlag; SMTP-Karte speichert nur ihre Schluessel (F)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10 (F.5): Abschluss F — Vollauf, statische Prüfung, Build, Meldung

**Files:** keine Änderung (nur bei einem Befund aus Step 3, dann mit Meldung).

- [ ] **Step 1:** Alle F-Klassen (Befehl aus F.3 Step 4) → `20 passed`.
- [ ] **Step 2:** Prozedur V → kein Abgleich-Eintrag.
- [ ] **Step 3:** `git diff --name-only <Basis F>..HEAD -- '*.py' | xargs /opt/homebrew/bin/ruff check --select F821,F823` → ohne Befund (fehlt `ruff` dort: „nicht ausführbar“ melden, nicht ersetzen).
- [ ] **Step 4:** `tsc` ohne Ausgabe, `npm run build` mit `✓ built`.
- [ ] **Step 5:** `git diff --stat <Basis F>..HEAD` → genau diese 7 Dateien: `backend/app/api/v1/admin.py`, `backend/app/services/belegversand.py`, `backend/app/services/pdf_service.py`, `backend/app/services/settings_service.py`, `backend/tests/test_nachtrag_0910.py`, `frontend/src/components/domain/FirmendatenKarte.tsx`, `frontend/src/pages/Settings.tsx`. `git log --oneline <Basis F>..HEAD` → vier Commits (F.1–F.4). `<Basis F>` = `git rev-parse HEAD` vor F.1, im Bericht festhalten.
- [ ] **Step 6: Abschlussmeldung** (kurz, mit Zeigern): Basis-Hash, Commit je Task, Rot/Grün je Task (erwartet/gemessen), Summenzeile Prozedur V, `ruff`/`tsc`/Build, jede selbst behobene Anker- oder Redaktionsabweichung mit Datei und Funktion.

---

## Abschnitt O — Belegordner: PDFs direkt in einen gewählten Ordner, sortiert nach Belegart und Monat (Chrome/Edge) — Tasks 11–16

**Ziel:** Gernot (09.10.): „Ist es möglich einen Speicherort für die Belege zu definieren? Damit nicht alles im Download-Ordner landet und ich es dann noch sortieren muss.“ Er nutzt Chrome oder Edge. In den Einstellungen wählt man je Browser und Gerät einen **Belegordner**. Danach legt jede Beleg-Schaltfläche der App die Datei direkt dort ab, als `<Ordner>/<Belegart>/<JJJJ-MM>/<Belegnummer>.pdf`, z. B. `Belege/Rechnungen/2026-10/RE-2026-00006.pdf`, und meldet das als Toast „Gespeichert in Belege/Rechnungen/2026-10/RE-2026-00006.pdf“. Ohne Ordner, in Safari/Firefox, ohne Freigabe oder bei einem Schreibfehler läuft der Download wie heute. Die Freigabe fragt der Browser je Sitzung neu ab. Der Ordner lässt sich zurücksetzen.

**Architektur:** Reines Frontend, keine Backend- und Schemaänderung. Die File System Access API (`showDirectoryPicker`, `FileSystemDirectoryHandle`, `queryPermission`/`requestPermission`, `createWritable`) gibt es nur in Chromium-Browsern am Computer. Das Ordner-Handle liegt in IndexedDB (`novaerp-belegordner`). Jeder Mandant hat seine eigene Subdomain, also auch seinen eigenen Speicher. Neu sind drei Bausteine:
- `frontend/src/services/belegpfad.ts` (rein, ohne Importe, Node-Prüfung): Belegart der Rechnung, Monat des Belegdatums in Berlin, sichere Namen, Zusatz „(1)“, Ablagepfad, Anzeige.
- `frontend/src/services/belegordner.ts`: die **eine** Download-Funktion `belegHerunterladen(angaben, laden, toast)` und die Ordnerverwaltung für die Einstellungen. Die Datei ist bewusst ohne React-Import, damit die Node-Tests sie direkt laden können.
- `frontend/src/components/domain/BelegordnerKarte.tsx`: die Karte „Belegordner“ in den Einstellungen.

Alle Beleg-Downloads laufen über `belegHerunterladen`. Das sind Rechnung, Stornorechnung, Gutschrift, Leergutbeleg, Proforma und Entwurf (Rechnungsliste und Belegdialog der Bestellung), Monatsrechnung (ist eine Rechnung), Auftragsbestätigung, Lieferschein, Packliste (Belegdialog und Tagesplan), Mahnung, DATEV-Export und Lastschrift-CSV. Die drei `documentsApi.download…Pdf` werden zu reinen Ladern.

**Tech Stack:** React 18 + TypeScript 5.9 (`lib.dom` kennt `getDirectoryHandle`/`getFileHandle`/`createWritable`. `showDirectoryPicker`, `queryPermission` und `requestPermission` deklariert `belegordner.ts` lokal). Node ≥ 23.6 für `tests/unit/*.check.ts`. Pytest mit Node-Harness wie die Paket-3-Abnahme (`_abnahme_frontend`).

**Ausgangsstand:** `main` mit Paket 1, 2, 2.1, 3, B6, Benutzerverwaltung und Sicherheitsfixes. Geplant und durchgespielt auf `df84f7b` („docs: B6 live, Plan B6“). Keine Zeilennummern als Anker: maßgeblich sind die zitierten Zeilen und Funktionsnamen.

### Abhängigkeiten

- **Braucht B7 (Paket 3, Q3), live:** `frontend/src/services/dateiname.ts::dateinameAusHeader`. Der Server benennt Belege nach ihrer Nummer (`backend/app/services/beleg_dateiname.py`), und CORS gibt `Content-Disposition` frei (`backend/app/main.py`, `expose_headers=["Content-Disposition"]`). Der Dateiname im Belegordner ist derselbe wie heute im Download-Ordner.
- **Kein Backend, keine Migration, kein Server-Runbook.** Ausgeliefert wird wie jeder Frontend-Stand. Nur die Testdatei `backend/tests/test_nachtrag_0910.py` bekommt einen Block (Node-Tests des Frontends).
- **Gemeinsame Dateien mit anderen Abschnitten des Nachtrags:** `frontend/src/pages/Invoices.tsx`, `frontend/src/components/domain/OrderDocumentsModal.tsx`, `frontend/src/pages/Tagesplan.tsx`, `frontend/src/services/api.ts` (nur `documentsApi`), `frontend/src/pages/Settings.tsx`, `frontend/src/components/domain/SepaEinzugsliste.tsx`, `backend/tests/test_nachtrag_0910.py` (O hängt nur an; die Datei legt Task 1 an). Die Reihenfolge zu anderen Abschnitten ist egal, solange die zitierten Zeilen unverändert sind. Sonst gilt Stoppregel 1.
- **Mit D und F geprüft (Review 09.10.):** F fügt in `Settings.tsx` unter der Importzeile von `SepaEinstellungenKarte` ein. O ersetzt diese Zeile durch sich selbst plus den Belegordner-Import. Das geht in beiden Reihenfolgen. D ändert in `DatevExportForm` nur den Funktionsanfang und den Bereich ab `catch (error) {` samt `toast.error`. Der O-Anker in `handleExport` endet genau auf der unveränderten Zeile `catch (error) {`. Im Gesamtlauf D → F → O gemessen: jeder O-Anker genau einmal, alle Rot/Grün-Zahlen wie in den Steps. Der D-Block in `api.ts` liegt in `invoicesApi`, O ändert nur `documentsApi`.
- **Für andere Abschnitte:** Ein **neuer** Beleg-Download, etwa ein weiterer Beleg oder Export, gehört über `belegHerunterladen`. Fehlt seine Belegart, wird sie in `belegpfad.ts` (`Belegart`) ergänzt, sonst landet er im Download-Ordner. Ein solcher Download braucht keinen eigenen Rückfall.
- **Paket-3-Abnahmetests, die Frontend-Dateien in Node laden:** `tests/test_gernot_261008_paket3.py::TestAbnahmeSepaBerlin::test_frontend_vorgabe_maximum_und_csv_um_halb_eins_berlin` lädt `SepaEinzugsliste.tsx` samt allen nicht ersetzten Importen, nach O also `belegordner.ts`, `dateiname.ts` und `belegpfad.ts`. `TestAbnahmeRechnungsberechtigung` lädt `Invoices.tsx` auf dieselbe Weise. Beide bleiben **unverändert** grün, wenn `belegordner.ts` ohne React auskommt, für den Download `window.URL` und `document.createElement` nutzt und `document.body` und `setTimeout` nur unter Schutz anfasst (Entscheidung O-E8). Der `vm`-Kontext kennt beides nicht, gemessen. Gemessen: Ein erster Entwurf mit React-Hook brach den SEPA-Test (`TypeError: (0 , react_1.forwardRef) is not a function`).
- **Basis O:** vor Task 11 `git rev-parse HEAD` → als `<Basis-O>` in den Bericht (Stand nach Task 10; Task 16 vergleicht dagegen).
- **Rahmen, Prozedur V, File Structure, Vorbereitung:** stehen im Kopf des Plans (Global Constraints, Prozedur V, File Structure, Vorbereitung vor Task 1).

### Prüfstand (alles in Kopien unter `/tmp`, Repo unverändert)

- **Baseline** `df84f7b` (`git archive`, `frontend/node_modules` als Symlink): Prozedur V → `14 failed, 1644 passed, 2 skipped, 1 error`, Fehlernamen = die 15 Baseline-Namen.
- **Rot/Grün je Task, nachgespielt aus diesem Plantext (Stand nach Review 09.10.)** in `/tmp/n0910-kopie-o5` (frisches `git archive df84f7b`). Das Skript `/tmp/n0910-o5-skripte/anwenden.py` setzt die Code-Blöcke mechanisch ein: 5 neue Dateien, 1 Anhang, 17 Ersetzungen, jeder Anker genau einmal. Die Ergebnisdateien sind byte-gleich mit den Blöcken.
  - **Vorbereitung:** greps `1/1/1/7/2/1/1/0/fehlt`, `node v25.3.0`.
  - **O.1:** Node-Prüfung `ERR_MODULE_NOT_FOUND`, danach `belegpfad.check: 35 Fälle ok`, `dateiname.check: 8 Fälle ok`, `tsc` sauber.
  - **O.2:** `8 failed`, je `ENOENT … 'src/services/belegordner.ts'`, danach `8 passed`, `tsc` sauber.
  - **O.3:** `tsc` sauber.
  - **O.4:** `_openPdfFromResponse` 4, `tsc` meldet genau 4 × `TS2339` (`OrderDocumentsModal.tsx` × 3, `Tagesplan.tsx` × 1), danach sauber.
  - **O.5:** `grep` 6 + 1 Altstellen → 0 + 0. `belegHerunterladen(` 3/1/1/1. Paket-3-Abnahmetests `5 passed, 462 deselected`. `tsc` sauber. Build `✓ built`.
  - **Schluss:** Prozedur V `14 failed, 1652 passed, 2 skipped, 1 error` (+8), `comm`-Abgleich leer (Ausgabe `/tmp/n0910-o5-voll.txt`). Schritt O.6/4 genau die 7 Dateien. Diff genau 11 Dateien, 5 Commits.
- **Fassung vor dem Review** (`/tmp/n0910-kopie-o2`, `-o3`, unabhängig nachgespielt in `/tmp/n0910-kopie-orev`): dieselben Zahlen, nur `34` statt `35 Fälle`.
- **Gegenproben (Mutationen an `belegordner.ts`, Skript `/tmp/n0910-o5-skripte/mutation.py`):**
  - „immer ersetzen“ → 2 Tests rot (Rückfrage, Exporte).
  - „Freigabe erst nach dem Laden“ → 1 rot.
  - „kein Rückfall bei Schreibfehler“ → 1 rot.
  - „Belegdatum ignoriert“ → 1 rot.
  - „abgelehnt wie offen behandeln“ (ein Hinweis für beide) → 1 rot.
  - „SecurityError als abgelehnt“ → 1 rot.
  - Danach wieder `8 passed`.
- **Browser-Probe** (headless Chromium aus Playwright 1.62.1, OPFS-Ordner statt Ordnerdialog, Skript unter „Abnahme“, gemessen in `/tmp/n0910-o5-probe`): `Browser-Probe O: ok`. Geprüft und bestanden:
  - Ablage, Ersetzen nach OK, „(1)“ nach Abbrechen, die Exporte ohne Rückfrage.
  - Der Monat aus einem UTC-Zeitstempel (`2026-10-31T23:30:00.123456` → `2026-11`) und der Ordnername mit Umlaut (`Auftragsbestätigungen`).
  - Bei `TypeMismatchError` und nach dem Zurücksetzen kam der Rückfall auf den Download. Der Rückfall-Link (eingehängt, URL nach 5 s freigegeben) kommt in Chromium an, als `download`-Ereignis mit der Belegnummer, und ist danach wieder aus dem DOM entfernt.
  - Ohne `showDirectoryPicker` und in einem unsicheren Kontext liefert `belegordnerMoeglich()` `false`.
  - Nicht prüfbar: die Ablehnung. Ein OPFS-Ordner ist immer freigegeben.
- **Aus der Chromium-Quelle (nicht gemessen):** Freigabe-Zustände nach „Nicht zulassen“ bzw. Wegklicken (O-E5a). Das deckt die Abnahme C11 und C11b ab.
- **Backend-Fakten (lesend geprüft):**
  - Stornorechnung, Leergutbeleg und Monatsrechnung laufen im Nummernkreis `RE-JJJJ-NNNNN` (`invoice_service._naechste_rechnungsnummer`: „Auch die Stornorechnung läuft in diesem Kreis“). Der Dateiname allein unterscheidet sie also nicht.
  - `issued_at` (AB, LS) und `created_at` (Packliste) speichert der Server als `datetime.now(timezone.utc)`. SQLite gibt sie ohne Zone zurück, die API liefert dann z. B. `"2026-10-31T23:30:00"` (in der Kopie per SQLite-Rundreise und Pydantic gemessen).
  - Die Mahnung heißt `Zahlungserinnerung_<Nr>_Stufe<n>.pdf` (Server und Client gleich). Die SEPA-CSV heißt `Lastschrift-Einreichung_<heute Berlin>.csv`. DATEV kommt als JSON (`csv_content`) ohne Kopf.
  - Proforma ist ein eigener Rechnungstyp (`InvoiceType.PROFORMA`, `backend/app/models/enums.py`), in der Rechnungsliste anlegbar und in der Typ-Spalte als „Proforma“ ausgewiesen. Leergutbelege sind `RECHNUNG` mit `beleg_art = 'LEERGUT'` (`leergut_service`).
- **Vollständigkeit (Review 09.10., grep nach `downloadPdf`, `documentsApi.download*`, `a.download`, `ladePdfHerunter`, `createObjectURL`):** Beleg-Downloads gibt es nur an den 9 Stellen dieses Abschnitts:
  - Rechnungsliste: PDF, Mahnung, DATEV
  - Belegdialog: RE, AB, LS, PL
  - Tagesplan: PL
  - SEPA-CSV

  `InvoiceDetail`, `MonatsrechnungenDialog` und `Leergut` haben keinen eigenen Download. `print_jobs` dient nur dem Druck-Agenten.
- **Nicht gemessen:**
  - echter Ordnerdialog und Freigabe-Prompt samt „Nicht zulassen“ in Chrome/Edge (C1–C11b, C14)
  - Rückfall-Download in Safari, Firefox und am Hallen-Tablet (C13, C16)
  - echte Belege aus dem Server

### Entscheidungen (Manager — Gernot kann widersprechen, siehe „Offene Punkte“)

- **O-E1 — Kein Backend.** Die Belegart lässt sich nicht aus dem Präfix ableiten (Rechnung, Storno, Leergut und Monatsrechnung heißen alle `RE-…`). Aber jeder Aufrufer hält das Objekt in der Hand: `Invoice` (`invoice_type`, `original_invoice_id`, `beleg_art`, `status`, `invoice_date`), `OrderConfirmation.issued_at`, `DeliveryNote.issued_at` und `packing_list.created_at`. Ein Kopf wie `X-Beleg-Art` wäre ein zweiter Weg zu denselben Daten.
- **O-E2 — Eine zentrale Funktion, feste Reihenfolge.** `belegHerunterladen(angaben, laden, toast)` liest zuerst den Ordner und holt die **Freigabe**, danach erst ruft sie `laden()` (Server) auf und legt ab bzw. lädt herunter. Der Grund: `requestPermission` verlangt eine frische Nutzeraktion, also den Klick von höchstens einigen Sekunden zuvor. Nach einer PDF-Erzeugung oder einer offenen Rückfrage wäre sie oft verfallen. Rückfragen, die heute vor dem Abruf stehen (Mahnung „… mit Gebühr erzeugen?“, SEPA „Vorabankündigung …?“), wandern deshalb **in** `laden`. Liefert `laden` `null` (abgebrochen, DATEV ohne neue Buchungen), passiert nichts. Fehler aus `laden` gehen wie bisher an den Aufrufer und dessen Fehler-Toast.
- **O-E3 — Ordnerstruktur `<Belegart>/<JJJJ-MM>/<Datei>`.** Belegarten (Ordnernamen mit Umlaut, die API und Windows/macOS können das): `Rechnungen`, `Stornorechnungen`, `Gutschriften` (Gutschrift ohne Original), `Leergut`, `Proformarechnungen`, `Entwürfe` (jeder Rechnungsentwurf, Datei `Entwurf-….pdf`), `Auftragsbestätigungen`, `Lieferscheine`, `Packlisten`, `Mahnungen`, `DATEV-Exporte`, `Lastschriften`. Für die Rechnung gilt: Entwurf zuerst, danach genau die Typ-Spalte der Rechnungsliste (`Invoices.tsx`, `TYPE_LABELS`): Stornorechnung (Gutschrift mit Original), Leergutabrechnung, sonst der Rechnungstyp, also Gutschrift, Proforma oder Rechnung (auch Monatsrechnung). Proforma bekommt einen eigenen Ordner, denn sie ist keine Steuerrechnung und gehört nicht in den Ordner, den die Buchhaltung abarbeitet (Offener Punkt 3). Der Monat kommt aus dem Belegdatum in Berliner Zeit. Ein Datum `JJJJ-MM-TT` gilt wie geschrieben, ein Zeitstempel ohne Zone ist UTC. Ohne Datum gilt heute in Berlin. Je Aufruf:

  | Aufruf | Belegart | Datum für den Monat |
  |---|---|---|
  | Rechnungsliste „PDF“, Belegdialog Rechnung | `belegartDerRechnung(invoice)` | `invoice.invoice_date` |
  | Belegdialog AB | Auftragsbestätigungen | `conf.issued_at` |
  | Belegdialog LS | Lieferscheine | `note.issued_at` |
  | Belegdialog „Packliste“, Tagesplan „Packliste“ | Packlisten | `note.packing_list.created_at`, sonst `note.issued_at` |
  | Rechnungsliste „Mahnung“ | Mahnungen | keins (heute = Mahndatum) |
  | DATEV-Export | DATEV-Exporte | `to_date` (Ende des Zeitraums) |
  | „Bei der Bank einreichen (CSV)“ | Lastschriften | keins (heute = Einreichung) |
- **O-E4 — Vorhandene Datei.**
  - **Belege:** Ersetzt wird nur nach Rückfrage. Beispieltext: „„RE-2026-00006.pdf“ liegt schon in Belege/Rechnungen/2026-10. OK: ersetzen, Abbrechen: daneben als „RE-2026-00006 (1).pdf“ speichern“. Begründung: Gleicher Name heißt gleiche Belegnummer, also meist derselbe Beleg (ausgestellte Rechnungen sind festgeschrieben) oder ein neuerer Stand (Entwurf, unterschriebener Lieferschein). Ersetzen ist darum der Normalfall, ein stiller Zusatz „(1)“ würde den Ordner mit Doppeln füllen, die Gernot wieder aufräumen müsste. Still ersetzen geht aber auch nicht: Die App erzeugt PDFs bei jedem Abruf neu. Nach einer Änderung an Briefpapier oder Vorlage sieht das neue PDF anders aus als das verschickte, und die alte Datei kann genau die verschickte sein. Abbrechen verliert daher nichts, die neue Datei kommt mit Zusatz daneben.
  - **Exporte** (`DATEV-Exporte`, `Lastschriften`) bekommen nie eine Rückfrage, sondern immer den nächsten freien Zusatz „(1)“, „(2)“ …. Der Name trägt ein Datum, keine Nummer, also hat derselbe Name einen anderen Inhalt: Eine zweite SEPA-Einreichung am selben Tag enthält andere Rechnungen, ein DATEV-Lauf ohne „Erneut exportieren“ nur die neuen Buchungen. Ersetzen hieße Daten verlieren.
- **O-E5 — Rückfall statt Verlust.** Ohne Ordner, ohne API (Safari, Firefox, Mobilgeräte), außerhalb von https/localhost, ohne Freigabe und bei jedem Schreibfehler (Ordner gelöscht, Datei statt Ordner, Platte voll) läuft ein normaler Download mit dem Servernamen. Ist ein Ordner gewählt, erscheint ein Warn-Toast mit Grund. Grund: Die SEPA-Einreichung (zweites Mal 409) und die Mahnstufe sind beim Abruf schon vermerkt, ein zweiter Abruf ist nicht immer möglich.
- **O-E5a — „Ohne Freigabe“ hat zwei Fälle mit verschiedenem Ausweg.** Belegt aus der Chromium-Quelle (`chrome_file_system_access_permission_context.cc`), nicht im Browser gemessen:
  - **Noch offen** (`'prompt'`): Die Frage wurde weggeklickt (Esc, Kreuz; `DISMISSED` setzt keinen Status) oder kam gar nicht, weil die Nutzeraktion verfallen war (`SecurityError`). Der Stand bleibt „fragen“. Der Knopf „Zugriff erlauben“ in den Einstellungen fragt erneut. Der Hinweis nennt deshalb diesen Knopf.
  - **Abgelehnt** (`'denied'`): „Nicht zulassen“ setzt den Status `DENIED`. Danach endet jedes `requestPermission` dieser Sitzung sofort ohne Frage (`RequestPermission`: Status ≠ `ASK` → `kRequestAborted`), auch über den Knopf. Erst `CleanupPermissions` setzt wieder auf „fragen“, ausgelöst von `OnLastPageFromOriginClosed`, also wenn der letzte Tab dieser Adresse geschlossen ist. Der zweite Weg ist `RevokeGrants`. Ein Block in den Website-Einstellungen ergibt ebenfalls `'denied'`. Der Hinweis und die Karte nennen darum „alle Tabs dieser Seite schließen und neu öffnen oder Symbol links in der Adresszeile → Website-Einstellungen“. Die Karte zeigt dann keinen Knopf „Zugriff erlauben“, denn er bliebe wirkungslos.
- **O-E6 — Je Browser und Gerät, gewählt in den Einstellungen.** Die Wahl liegt in IndexedDB, der Server weiß nichts davon. Wer denselben Ordner auf mehreren Rechnern will (z. B. OneDrive), wählt ihn auf jedem Rechner. Die Seite „Einstellungen“ sieht heute nur `ADMIN` (`Layout.tsx`). Buchhaltung und Vertrieb können also keinen Ordner wählen, ihre Downloads bleiben wie heute (Offener Punkt 1).
- **O-E7 — Exporte gehören dazu, andere Downloads nicht.** DATEV-Export und Lastschrift-CSV sind Buchhaltungsunterlagen, die Gernot sonst ebenfalls sortiert. Inventur, Warenfluss, Etiketten, Dienstplan, Import-Vorlagen, Zertifikate und die Vorlagen-Vorschau bleiben normale Downloads. Bewusst ausgenommen ist auch das Inventur-Abschluss-PDF bzw. -XLSX (`Inventur.tsx` → `inventurApi.export` über `_openPdfFromResponse`), obwohl es eine Unterlage für den Jahresabschluss ist (Offener Punkt 7).
- **O-E8 — Rückfall-Download wie bisher die robusteste Stelle.** Bisher gab es drei Muster: AB, LS, PL und die Rechnung im Belegdialog hängten den Link ein und gaben die Blob-URL erst nach 5 s frei (`_openPdfFromResponse`). Die Rechnungsliste hängte ein und gab sofort frei (`print.ts::ladePdfHerunter`). SEPA, DATEV und Mahnung nutzten einen losgelösten Link und gaben sofort frei. Der Rückfall in `belegordner.ts::herunterladen` hängt den Link in `document.body` ein, klickt, nimmt ihn wieder heraus und gibt die URL nach 5 s frei, ohne `target=_blank`. Das ist wichtig für Safari, Firefox und Tablets. Die Halle sieht die Einstellungen nicht, also landet die Tagesplan-Packliste am Hallen-Tablet immer im Rückfall (Abnahme C16). Ohne `document.body` bzw. ohne `setTimeout` gilt das bisherige SEPA-Muster: losgelöst und sofort freigeben. Das betrifft nur den `vm`-Kontext der Node-Prüfungen, denn die Paket-3-Abnahme (`TestAbnahmeSepaBerlin`) kennt weder das eine noch das andere. Deshalb steht beides unter `typeof`- bzw. `if`-Schutz. Die Paket-3-Abnahmetests laufen damit unverändert.
- **O-E9 — Toast als Parameter, nicht als Hook.** `belegordner.ts` importiert kein React (siehe Abhängigkeiten). Jeder Aufrufer reicht sein `toast` aus `useToast()` durch. Ohne Belegordner gibt es keinen Toast, wie heute.

---

### Task 11 (O.1): Ablagepfad als reine Funktion

**Files:**
- Create: `frontend/tests/unit/belegpfad.check.ts`
- Create: `frontend/src/services/belegpfad.ts`

**Interfaces:**
- Produces:
  - `type Belegart`: die 12 Ordnernamen aus O-E3.
  - `istExport(art) -> boolean`.
  - `belegartDerRechnung({ invoice_type, status, original_invoice_id?, beleg_art? }) -> Belegart`.
  - `belegmonat(datum?: string | null, jetzt?: Date) -> 'JJJJ-MM'`.
  - `sichererName(name) -> string`.
  - `nameMitZaehler(dateiname, n) -> string`.
  - `belegablage(art, datum, dateiname, jetzt?) -> { ordner: [Belegart, string], datei }`.
  - `ablageAnzeige(wurzel, ablage, datei?) -> string`.

**Review Focus (O.1):** Der Vorrang der Rechnungsarten entspricht der Typ-Spalte der Rechnungsliste (Stornorechnung, Leergutabrechnung, dann der Typ). Proforma hat einen eigenen Ordner. Die Monatsgrenze wird in Berlin gerechnet: UTC 31.10. 23:30 ist November, UTC 30.09. 22:30 (Sommerzeit) ist Oktober. Namen, die Windows ablehnt, werden ersetzt.

- [ ] **Step 1: Prüfskript anlegen**

`frontend/tests/unit/belegpfad.check.ts` mit genau diesem Inhalt anlegen:

```ts
// Prüft die Ablage im Belegordner ohne Browser und ohne Testframework (Abschnitt O).
// Lauf: node tests/unit/belegpfad.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import {
  ablageAnzeige, belegablage, belegartDerRechnung, belegmonat, istExport, nameMitZaehler, sichererName,
} from '../../src/services/belegpfad.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

// Belegart aus der Rechnung, Vorrang wie die Typ-Spalte der Rechnungsliste
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'OFFEN' }), 'Rechnungen', 'Rechnung');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'BEZAHLT', beleg_art: null }), 'Rechnungen', 'Monatsrechnung ist eine Rechnung');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'STORNIERT' }), 'Rechnungen', 'stornierte Rechnung bleibt Rechnung');
gleich(belegartDerRechnung({ invoice_type: 'GUTSCHRIFT', status: 'OFFEN', original_invoice_id: 'a1' }), 'Stornorechnungen', 'Stornorechnung');
gleich(belegartDerRechnung({ invoice_type: 'GUTSCHRIFT', status: 'OFFEN', original_invoice_id: 'a1', beleg_art: 'LEERGUT' }), 'Stornorechnungen', 'Storno eines Leergutbelegs');
gleich(belegartDerRechnung({ invoice_type: 'GUTSCHRIFT', status: 'OFFEN', original_invoice_id: null }), 'Gutschriften', 'Gutschrift ohne Original');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'OFFEN', beleg_art: 'LEERGUT' }), 'Leergut', 'Leergutbeleg');
gleich(belegartDerRechnung({ invoice_type: 'PROFORMA', status: 'OFFEN' }), 'Proformarechnungen', 'Proforma ist keine Steuerrechnung');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'ENTWURF' }), 'Entwürfe', 'Entwurf');
gleich(belegartDerRechnung({ invoice_type: 'RECHNUNG', status: 'ENTWURF', beleg_art: 'LEERGUT' }), 'Entwürfe', 'Leergut-Entwurf');

// Monat nach Belegdatum (Berlin); ohne Datum der heutige Monat in Berlin
const jetzt = new Date('2026-12-31T23:30:00Z'); // in Berlin schon 01.01.2027
gleich(belegmonat('2026-10-31', jetzt), '2026-10', 'Datum ohne Uhrzeit');
gleich(belegmonat('2026-10-31T21:59:00', jetzt), '2026-10', 'Zeitstempel ohne Zone = UTC');
gleich(belegmonat('2026-10-31T23:30:00', jetzt), '2026-11', 'UTC 23:30 = Berlin 00:30 am 1.11.');
gleich(belegmonat('2026-10-31T23:30:00.123456', jetzt), '2026-11', 'Mikrosekunden wie vom Server');
gleich(belegmonat('2026-09-30T22:30:00Z', jetzt), '2026-10', 'Sommerzeit: UTC+2');
gleich(belegmonat('2026-10-31T23:30:00+01:00', jetzt), '2026-10', 'Zeitstempel mit Zone');
gleich(belegmonat(null, jetzt), '2027-01', 'ohne Datum: heute in Berlin');
gleich(belegmonat(undefined, jetzt), '2027-01', 'ohne Datum (undefined)');
gleich(belegmonat('', jetzt), '2027-01', 'leeres Datum');
gleich(belegmonat('kein Datum', jetzt), '2027-01', 'unlesbares Datum');

// Ablage und Anzeige im Toast
const ablage = belegablage('Rechnungen', '2026-10-09', 'RE-2026-00006.pdf', jetzt);
gleich(ablage, { ordner: ['Rechnungen', '2026-10'], datei: 'RE-2026-00006.pdf' }, 'Ablage einer Rechnung');
gleich(ablageAnzeige('Belege', ablage), 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf', 'Anzeige');
gleich(ablageAnzeige('Belege', ablage, 'RE-2026-00006 (1).pdf'), 'Belege/Rechnungen/2026-10/RE-2026-00006 (1).pdf', 'Anzeige mit Zusatz');
gleich(belegablage('Mahnungen', null, 'Zahlungserinnerung_RE-2026-00006_Stufe1.pdf', jetzt).ordner, ['Mahnungen', '2027-01'], 'Mahnung: heute');

// Zusatz (n) für eine vorhandene Datei
gleich(nameMitZaehler('RE-2026-00006.pdf', 1), 'RE-2026-00006 (1).pdf', 'Zusatz vor der Endung');
gleich(nameMitZaehler('DATEV_Export_2026-10-01_2026-10-31.csv', 2), 'DATEV_Export_2026-10-01_2026-10-31 (2).csv', 'Zusatz CSV');
gleich(nameMitZaehler('Beleg', 1), 'Beleg (1)', 'ohne Endung');

// Namen, die Windows oder der Browser ablehnen
gleich(sichererName('Zahlungserinnerung_RE:1?.pdf'), 'Zahlungserinnerung_RE_1_.pdf', 'verbotene Zeichen');
gleich(sichererName('a/b\\c.pdf'), 'a_b_c.pdf', 'Pfadtrenner');
gleich(sichererName('RE-1.pdf. '), 'RE-1.pdf', 'Punkt und Leerzeichen am Ende');
gleich(sichererName('..'), 'Beleg', 'nur Punkte');
gleich(belegablage('Entwürfe', '2026-10-09', 'Entwurf-B<>.pdf', jetzt).datei, 'Entwurf-B__.pdf', 'Ablage nimmt sicheren Namen');

// Exporte bekommen nie einen Ersetzen-Dialog
gleich(istExport('Lastschriften'), true, 'SEPA-CSV ist Export');
gleich(istExport('DATEV-Exporte'), true, 'DATEV ist Export');
gleich(istExport('Rechnungen'), false, 'Rechnung ist Beleg');

console.log(`belegpfad.check: ${faelle} Fälle ok`);
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd frontend && node tests/unit/belegpfad.check.ts`
Erwartet: Abbruch mit `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '…/frontend/src/services/belegpfad.ts' imported from …/frontend/tests/unit/belegpfad.check.ts`.

- [ ] **Step 3: Modul anlegen**

`frontend/src/services/belegpfad.ts` mit genau diesem Inhalt anlegen:

```ts
/**
 * Ablage im Belegordner (Abschnitt O, Gernot 09.10.2026):
 * <Belegordner>/<Belegart>/<JJJJ-MM>/<Dateiname>, z. B.
 * Belege/Rechnungen/2026-10/RE-2026-00006.pdf.
 *
 * Die Belegart kommt vom Aufrufer, nicht aus dem Dateinamen: Rechnung,
 * Stornorechnung, Leergutbeleg und Monatsrechnung heißen alle RE-….pdf
 * (ein Nummernkreis). Der Monat kommt aus dem Belegdatum in Berliner Zeit,
 * ohne Datum aus dem heutigen Tag in Berlin.
 *
 * Bewusst ohne Importe: tests/unit/belegpfad.check.ts lädt die Datei direkt
 * mit Node (wie dateiname.ts).
 */

export type Belegart =
  | 'Rechnungen'
  | 'Stornorechnungen'
  | 'Gutschriften'
  | 'Leergut'
  | 'Proformarechnungen'
  | 'Entwürfe'
  | 'Auftragsbestätigungen'
  | 'Lieferscheine'
  | 'Packlisten'
  | 'Mahnungen'
  | 'DATEV-Exporte'
  | 'Lastschriften';

/**
 * Exporte heißen nach einem Datum, nicht nach einer Belegnummer: derselbe Name
 * hat einen anderen Inhalt (zweite SEPA-Einreichung am selben Tag, DATEV nur
 * mit den neuen Buchungen). Sie werden nie ersetzt, sondern bekommen (1), (2) ….
 */
export function istExport(art: Belegart): boolean {
  return art === 'DATEV-Exporte' || art === 'Lastschriften';
}

export interface RechnungFuerAblage {
  invoice_type: string;
  status: string;
  original_invoice_id?: string | null;
  beleg_art?: string | null;
}

/**
 * Belegart einer Rechnung. Entwürfe getrennt, sonst genau die Typ-Spalte der
 * Rechnungsliste (Invoices.tsx): Stornorechnung, Leergutabrechnung, dann der
 * Typ — Gutschrift, Proforma, Rechnung (auch Monatsrechnung). Proforma ist
 * keine Steuerrechnung und bekommt deshalb einen eigenen Ordner.
 */
export function belegartDerRechnung(r: RechnungFuerAblage): Belegart {
  if (r.status === 'ENTWURF') return 'Entwürfe';
  if (r.invoice_type === 'GUTSCHRIFT' && r.original_invoice_id) return 'Stornorechnungen';
  if (r.beleg_art === 'LEERGUT') return 'Leergut';
  if (r.invoice_type === 'GUTSCHRIFT') return 'Gutschriften';
  if (r.invoice_type === 'PROFORMA') return 'Proformarechnungen';
  return 'Rechnungen';
}

const NUR_DATUM = /^(\d{4})-(\d{2})-\d{2}$/;
const MIT_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * JJJJ-MM des Belegdatums in Berliner Zeit. "2026-10-31" gilt wie geschrieben;
 * ein Zeitstempel ohne Zone ist UTC (der Server speichert
 * datetime.now(timezone.utc), SQLite gibt ihn ohne Zone zurück). Ohne oder mit
 * unlesbarem Datum: der heutige Monat in Berlin.
 */
export function belegmonat(datum: string | null | undefined, jetzt: Date = new Date()): string {
  if (datum) {
    const tag = NUR_DATUM.exec(datum);
    if (tag) return `${tag[1]}-${tag[2]}`;
    const zeit = new Date(MIT_ZONE.test(datum) ? datum : `${datum}Z`);
    if (!Number.isNaN(zeit.getTime())) return monatInBerlin(zeit);
  }
  return monatInBerlin(jetzt);
}

function monatInBerlin(zeit: Date): string {
  const teile = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit',
  }).formatToParts(zeit);
  const jahr = teile.find((t) => t.type === 'year')?.value;
  const monat = teile.find((t) => t.type === 'month')?.value;
  return `${jahr}-${monat}`;
}

/** Datei- bzw. Ordnername ohne Zeichen, die Windows oder der Browser ablehnen. */
export function sichererName(name: string): string {
  // eslint-disable-next-line no-control-regex
  const sauber = name.replace(/[\x00-\x1f<>:"/\\|?*]/g, '_').replace(/[. ]+$/, '').trim();
  return sauber || 'Beleg';
}

/** Name für eine schon vorhandene Datei: ("RE-1.pdf", 1) → "RE-1 (1).pdf". */
export function nameMitZaehler(dateiname: string, n: number): string {
  const punkt = dateiname.lastIndexOf('.');
  if (punkt <= 0) return `${dateiname} (${n})`;
  return `${dateiname.slice(0, punkt)} (${n})${dateiname.slice(punkt)}`;
}

export interface Ablage {
  /** Unterordner unter dem Belegordner: [Belegart, JJJJ-MM] */
  ordner: [Belegart, string];
  datei: string;
}

export function belegablage(
  art: Belegart, datum: string | null | undefined, dateiname: string, jetzt: Date = new Date(),
): Ablage {
  return { ordner: [art, belegmonat(datum, jetzt)], datei: sichererName(dateiname) };
}

/** Anzeige im Toast: "Belege/Rechnungen/2026-10/RE-2026-00006.pdf". */
export function ablageAnzeige(wurzel: string, ablage: Ablage, datei: string = ablage.datei): string {
  return [wurzel, ...ablage.ordner, datei].join('/');
}
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd frontend && node tests/unit/belegpfad.check.ts && node tests/unit/dateiname.check.ts && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: `belegpfad.check: 35 Fälle ok`, `dateiname.check: 8 Fälle ok`, danach keine Ausgabe von `tsc`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/belegpfad.ts frontend/tests/unit/belegpfad.check.ts
git commit -m "feat(belegordner): Ablagepfad je Belegart und Monat als reine Funktion mit Node-Prüfung (O)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12 (O.2): Die eine Download-Funktion für Belege

**Files:**
- Modify: `backend/tests/test_nachtrag_0910.py` (Block O anhängen; die Datei besteht seit Task 1)
- Create: `frontend/src/services/belegordner.ts`

**Interfaces:**
- Consumes: `dateinameAusHeader` (B7), alles aus `belegpfad.ts` (O.1).
- Produces:
  - `belegordnerMoeglich() -> boolean` (sicherer Kontext, `showDirectoryPicker` vorhanden, IndexedDB vorhanden).
  - `belegordnerName() -> Promise<string | null>`.
  - `belegordnerErlaubnis() -> Promise<'granted' | 'denied' | 'prompt' | null>`.
  - `belegordnerWaehlen() -> Promise<string | null>` (`null` = Dialog abgebrochen).
  - `belegordnerFreigeben() -> Promise<boolean>` (fragt nur im Stand `'prompt'`; nach „Nicht zulassen“ fragt Chrome in dieser Sitzung nicht mehr, siehe O-E5a).
  - `belegordnerZuruecksetzen() -> Promise<void>`.
  - `ZUGRIFF_WIEDER_ERLAUBEN: string`: der Weg nach „Nicht zulassen“, gleich in Warn-Toast und Karte.
  - **`belegHerunterladen(angaben: BelegAngaben, laden: () => Promise<Geladen | null>, toast?: BelegToast) -> Promise<BelegErgebnis | null>`**.
  - `BelegAngaben = { art, datum?, ersatzname, mime? }`.
  - `Geladen = { data: BlobPart; headers?: unknown }` (eine Axios-Antwort passt).
  - `BelegErgebnis = { ort: 'ordner'; pfad } | { ort: 'download'; dateiname; hinweis? }`.
  - `BelegToast = { success, warning }` (passt auf `useToast()`).

**Review Focus (O.2):** Reihenfolge Freigabe → `laden` → ablegen (O-E2). Belege werden nur nach Rückfrage ersetzt, Exporte nie (O-E4). Jeder Fehler beim Ablegen endet im Download (O-E5). Der Hinweis unterscheidet „noch offen“ (Knopf in den Einstellungen hilft) und „abgelehnt“ (Tabs schließen bzw. Website-Einstellungen) (O-E5a). Der Rückfall hängt den Link ein und gibt die URL verzögert frei, beides mit Schutz für den `vm`-Kontext (O-E8). Kein React-Import (O-E9). Die Tests laufen ohne Browser gegen Attrappen. Deren `requestPermission` bildet Chromium nach: Eine Frage kommt nur im Stand `'prompt'`. Die echte API prüfen Browser-Probe und Abnahme.

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_nachtrag_0910.py` (seit Task 1 vorhanden) zwei Leerzeilen und diesen Block anhängen:

```python
# ---------------------------------------- Abschnitt O: Belegordner (Frontend)

def _o_node(script):
    """Führt `script` mit Node im Ordner frontend aus, mit Attrappen für den
    gewählten Ordner (File System Access API), IndexedDB, window und document.

    Wie die Paket-3-Abnahme (_abnahme_frontend): TypeScript übersetzt das
    typescript-Paket des Frontends, relative Importe kommen aus den echten
    Dateien (belegordner.ts → dateiname.ts, belegpfad.ts). Ein Browser ist
    nicht nötig; die echte API prüft die Abnahme in Chrome.
    """
    import os
    import subprocess
    from pathlib import Path
    vorspann = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
function laden(datei, globals) {
    const code = ts.transpileModule(fs.readFileSync(datei, 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText;
    const exports = {};
    const ladenImport = (name) => {
        if (!name.startsWith('.')) return require(name);
        const basis = path.resolve(path.dirname(datei), name);
        const ziel = [basis + '.ts', basis + '.tsx'].find((k) => fs.existsSync(k));
        assert.ok(ziel, name);
        return laden(ziel, globals);
    };
    vm.runInNewContext(code, { exports, require: ladenImport, ...globals }, { filename: datei });
    return exports;
}
// Objekte aus dem vm-Kontext haben andere Prototypen: über JSON vergleichen
const gleich = (ist, soll) => assert.deepEqual(JSON.parse(JSON.stringify(ist ?? null)), soll);
const fehler = (name) => Object.assign(new Error(name), { name });
class Datei {
    constructor(name) { this.kind = 'file'; this.name = name; this.inhalt = null; }
    async createWritable() {
        const datei = this;
        let puffer = null;
        return {
            async write(b) { puffer = typeof b === 'string' ? b : await b.text(); },
            async close() { datei.inhalt = puffer; },
            async abort() {},
        };
    }
}
class Ordner {
    constructor(name) {
        this.kind = 'directory'; this.name = name; this.eintraege = new Map();
        this.erlaubnis = 'granted'; this.protokoll = [];
    }
    async getDirectoryHandle(name, o = {}) {
        let e = this.eintraege.get(name);
        if (!e) { if (!o.create) throw fehler('NotFoundError'); e = new Ordner(name); this.eintraege.set(name, e); }
        if (e.kind !== 'directory') throw fehler('TypeMismatchError');
        return e;
    }
    async getFileHandle(name, o = {}) {
        let e = this.eintraege.get(name);
        if (!e) { if (!o.create) throw fehler('NotFoundError'); e = new Datei(name); this.eintraege.set(name, e); }
        if (e.kind !== 'file') throw fehler('TypeMismatchError');
        return e;
    }
    async queryPermission() { return this.erlaubnis; }
    async requestPermission() {
        // wie Chromium: nur im Stand „fragen“ kommt eine Frage, sonst sofort der Stand
        if (this.erlaubnis !== 'prompt') return this.erlaubnis;
        this.protokoll.push('Freigabe angefragt');
        if (this.ohneKlick) throw fehler('SecurityError');
        this.erlaubnis = this.antwort || 'granted';
        return this.erlaubnis;
    }
    inhalt(pfad) {
        let h = this;
        for (const teil of pfad.split('/')) h = h && h.eintraege.get(teil);
        return h ? h.inhalt : undefined;
    }
}
function attrappeIndexedDB() {
    const daten = new Map();
    const spaeter = (r, tun) => { setTimeout(() => { r.result = tun(); if (r.onsuccess) r.onsuccess(); }, 0); return r; };
    const speicher = {
        get: (k) => spaeter({}, () => daten.get(k)),
        put: (v, k) => spaeter({}, () => { daten.set(k, v); return k; }),
        delete: (k) => spaeter({}, () => { daten.delete(k); }),
    };
    const db = { createObjectStore() {}, transaction: () => ({ objectStore: () => speicher }), close() {} };
    return {
        open() {
            const r = {};
            setTimeout(() => { r.result = db; if (r.onupgradeneeded) r.onupgradeneeded(); if (r.onsuccess) r.onsuccess(); }, 0);
            return r;
        },
    };
}
function umgebung(o = {}) {
    const w = { wurzel: new Ordner('Belege'), rueckfragen: [], antworten: [], downloads: [], meldungen: [] };
    const window = {
        isSecureContext: true,
        confirm: (text) => { w.rueckfragen.push(text); return w.antworten.length ? w.antworten.shift() : true; },
        URL: { createObjectURL: () => 'blob:o', revokeObjectURL() {} },
    };
    if (!o.ohneApi) window.showDirectoryPicker = async () => w.wurzel;
    const document = { createElement: () => { const a = { click() { w.downloads.push(a.download); } }; return a; } };
    w.bo = laden('src/services/belegordner.ts', { window, document, indexedDB: attrappeIndexedDB(), Blob });
    w.toast = {
        success: (m) => w.meldungen.push(['success', m]),
        warning: (m) => w.meldungen.push(['warning', m]),
    };
    w.kopf = (n) => ({ 'content-disposition': `attachment; filename="${n}"; filename*=UTF-8''${encodeURIComponent(n)}` });
    w.re = (inhalt, nummer = 'RE-2026-00006') => w.bo.belegHerunterladen(
        { art: 'Rechnungen', datum: '2026-10-09', ersatzname: 'Ersatz.pdf' },
        async () => ({ data: inhalt, headers: w.kopf(nummer + '.pdf') }), w.toast);
    return w;
}
"""
    ergebnis = subprocess.run(
        ["node", "-e", vorspann + "(async () => {\n" + script
         + "\n})().catch((e) => { console.error(e); process.exitCode = 1; });"],
        cwd=Path(__file__).resolve().parents[2] / "frontend",
        env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
    )
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr


class TestOBelegordner:
    """Gernot 09.10.: Belege direkt in einen gewählten Ordner, sortiert nach
    <Belegart>/<JJJJ-MM>/<Belegnummer>, statt im Download-Ordner. Ohne Ordner,
    ohne Freigabe, ohne API oder bei Schreibfehlern: normaler Download."""

    def test_ohne_ordner_normaler_download_ohne_meldung(self):
        _o_node("""
const w = umgebung();
gleich(await w.bo.belegordnerName(), null);
gleich(await w.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
gleich(w.downloads, ['RE-2026-00006.pdf']);
gleich(w.meldungen, []);
""")

    def test_ablage_nach_belegart_und_monat_mit_meldung(self):
        _o_node("""
const w = umgebung();
gleich(await w.bo.belegordnerWaehlen(), 'Belege');
gleich(await w.bo.belegordnerName(), 'Belege');
gleich(await w.re('PDF-1'), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf' });
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006.pdf'), 'PDF-1');
// Zeitstempel ohne Zone = UTC: 31.10. 23:30 UTC ist in Berlin schon November
gleich(await w.bo.belegHerunterladen(
    { art: 'Auftragsbestätigungen', datum: '2026-10-31T23:30:00.123456', ersatzname: 'AB-20261101-0001.pdf' },
    async () => ({ data: 'AB' }), w.toast),
  { ort: 'ordner', pfad: 'Belege/Auftragsbestätigungen/2026-11/AB-20261101-0001.pdf' });
gleich(w.downloads, []);
gleich(w.meldungen, [
    ['success', 'Gespeichert in Belege/Rechnungen/2026-10/RE-2026-00006.pdf'],
    ['success', 'Gespeichert in Belege/Auftragsbestätigungen/2026-11/AB-20261101-0001.pdf'],
]);
""")

    def test_vorhandener_beleg_nur_nach_rueckfrage_ersetzen_sonst_daneben(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
await w.re('PDF-1');
gleich(w.rueckfragen, []);
w.antworten.push(true);   // OK = ersetzen
gleich(await w.re('PDF-2'), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf' });
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006.pdf'), 'PDF-2');
w.antworten.push(false);  // Abbrechen = daneben speichern
gleich(await w.re('PDF-3'), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006 (1).pdf' });
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006.pdf'), 'PDF-2');
gleich(w.wurzel.inhalt('Rechnungen/2026-10/RE-2026-00006 (1).pdf'), 'PDF-3');
gleich(w.rueckfragen.length, 2);
gleich(w.rueckfragen[1], '„RE-2026-00006.pdf" liegt schon in Belege/Rechnungen/2026-10.\\n\\n'
    + 'OK: ersetzen\\nAbbrechen: daneben als „RE-2026-00006 (1).pdf" speichern');
""")

    def test_exporte_bekommen_ohne_rueckfrage_einen_zusatz(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
const sepa = (inhalt) => w.bo.belegHerunterladen(
    { art: 'Lastschriften', datum: '2026-10-09', ersatzname: 'Lastschrift-Einreichung_2026-10-09.csv', mime: 'text/csv' },
    async () => ({ data: inhalt }), w.toast);
gleich(await sepa('a;b'), { ort: 'ordner', pfad: 'Belege/Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09.csv' });
gleich(await sepa('c;d'), { ort: 'ordner', pfad: 'Belege/Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09 (1).csv' });
gleich(w.wurzel.inhalt('Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09.csv'), 'a;b');
gleich(w.rueckfragen, []);
""")

    def test_freigabe_vor_dem_laden_sonst_download_mit_hinweis(self):
        _o_node("""
// Freigabe je Sitzung: erst fragen (frischer Klick), dann beim Server laden
const w = umgebung();
await w.bo.belegordnerWaehlen();
w.wurzel.erlaubnis = 'prompt';
gleich(await w.bo.belegordnerErlaubnis(), 'prompt');
const e = await w.bo.belegHerunterladen({ art: 'Mahnungen', datum: '2026-10-09', ersatzname: 'M.pdf' },
    async () => { w.wurzel.protokoll.push('geladen'); return { data: 'M' }; }, w.toast);
gleich(w.wurzel.protokoll, ['Freigabe angefragt', 'geladen']);
gleich(e, { ort: 'ordner', pfad: 'Belege/Mahnungen/2026-10/M.pdf' });

// Ohne Freigabe: Download mit Hinweis. Zwei Fälle mit verschiedenem Ausweg (O-E5a):
// ohneKlick (SecurityError) bzw. weggeklickt: Stand bleibt „fragen“, der Knopf
// in den Einstellungen hilft. abgelehnt: Chrome fragt in dieser Sitzung nicht
// mehr, auch nicht über den Knopf.
const hinweise = {
    ohneKlick: 'Kein Zugriff auf den Belegordner „Belege" — RE-2026-00006.pdf liegt im Download-Ordner. '
        + 'Zugriff erlauben: Einstellungen → Belegordner.',
    weggeklickt: 'Kein Zugriff auf den Belegordner „Belege" — RE-2026-00006.pdf liegt im Download-Ordner. '
        + 'Zugriff erlauben: Einstellungen → Belegordner.',
    abgelehnt: 'Zugriff auf den Belegordner „Belege" abgelehnt — RE-2026-00006.pdf liegt im Download-Ordner. '
        + 'Wieder erlauben: alle Tabs dieser Seite schließen und neu öffnen '
        + 'oder Symbol links in der Adresszeile → Website-Einstellungen.',
};
for (const fall of ['ohneKlick', 'weggeklickt', 'abgelehnt']) {
    const v = umgebung();
    await v.bo.belegordnerWaehlen();
    v.wurzel.erlaubnis = 'prompt';
    if (fall === 'ohneKlick') v.wurzel.ohneKlick = true;
    else v.wurzel.antwort = fall === 'abgelehnt' ? 'denied' : 'prompt';
    gleich(await v.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf', hinweis: hinweise[fall] });
    gleich(v.downloads, ['RE-2026-00006.pdf']);
    gleich(v.meldungen.map((m) => m[0]), ['warning']);
    // Der Knopf „Zugriff erlauben“ (Einstellungen, frischer Klick)
    v.wurzel.ohneKlick = false; v.wurzel.antwort = 'granted';
    if (fall === 'abgelehnt') {
        gleich(await v.bo.belegordnerErlaubnis(), 'denied');
        gleich(await v.bo.belegordnerFreigeben(), false);
        gleich(v.wurzel.protokoll, ['Freigabe angefragt']);   // keine zweite Frage
        gleich(v.bo.ZUGRIFF_WIEDER_ERLAUBEN, hinweise.abgelehnt.split('Download-Ordner. ')[1]);
    } else {
        gleich(await v.bo.belegordnerErlaubnis(), 'prompt');
        gleich(await v.bo.belegordnerFreigeben(), true);
        gleich(v.wurzel.protokoll, ['Freigabe angefragt', 'Freigabe angefragt']);
    }
}
""")

    def test_schreibfehler_faellt_auf_download_zurueck(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
await w.wurzel.getFileHandle('Packlisten', { create: true });   // Datei statt Ordner
const e = await w.bo.belegHerunterladen(
    { art: 'Packlisten', datum: '2026-10-09T08:00:00', ersatzname: 'PL-20261009-0001.pdf' },
    async () => ({ data: 'PL' }), w.toast);
gleich(e, {
    ort: 'download', dateiname: 'PL-20261009-0001.pdf',
    hinweis: 'Belegordner „Belege" nicht beschreibbar (TypeMismatchError) — PL-20261009-0001.pdf liegt im Download-Ordner.',
});
gleich(w.downloads, ['PL-20261009-0001.pdf']);
""")

    def test_laden_ohne_ergebnis_oder_mit_fehler(self):
        _o_node("""
const w = umgebung();
await w.bo.belegordnerWaehlen();
gleich(await w.bo.belegHerunterladen({ art: 'Mahnungen', ersatzname: 'M.pdf' }, async () => null, w.toast), null);
gleich([w.downloads, w.meldungen, [...w.wurzel.eintraege.keys()]], [[], [], []]);
await assert.rejects(
    w.bo.belegHerunterladen({ art: 'Rechnungen', ersatzname: 'x.pdf' }, async () => { throw new Error('500 vom Server'); }, w.toast),
    /500 vom Server/);
""")

    def test_ohne_api_und_nach_zuruecksetzen_normaler_download(self):
        _o_node("""
// Safari/Firefox: keine API — nichts zu wählen, Download wie bisher
const ohne = umgebung({ ohneApi: true });
gleich(ohne.bo.belegordnerMoeglich(), false);
gleich(await ohne.bo.belegordnerWaehlen(), null);
gleich(await ohne.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
gleich(ohne.meldungen, []);

const w = umgebung();
gleich(w.bo.belegordnerMoeglich(), true);
await w.bo.belegordnerWaehlen();
await w.bo.belegordnerZuruecksetzen();
gleich(await w.bo.belegordnerName(), null);
gleich(await w.re('PDF'), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
gleich(w.wurzel.eintraege.size, 0);
""")
```

Prüfen: `grep -c "^class TestOBelegordner\|^def _o_node" backend/tests/test_nachtrag_0910.py` → `2`.

- [ ] **Step 2: Rot bestätigen**

Run: Tests O (Global Constraints).
Erwartet: **8 failed**, jeder mit `AssertionError: Error: ENOENT: no such file or directory, open 'src/services/belegordner.ts'`.

- [ ] **Step 3: Modul anlegen**

`frontend/src/services/belegordner.ts` mit genau diesem Inhalt anlegen:

```ts
/**
 * Belegordner (Abschnitt O, Gernot 09.10.2026): Belege landen direkt in einem
 * gewählten Ordner, sortiert nach <Belegart>/<JJJJ-MM>/ (belegpfad.ts), statt
 * im Download-Ordner. File System Access API — nur Chrome und Edge am
 * Computer, nur über https bzw. localhost.
 *
 * Die Wahl gilt je Browser und Gerät: Das Ordner-Handle liegt in IndexedDB
 * dieser Adresse (jeder Mandant hat seine eigene Subdomain), der Server weiß
 * nichts davon. Die Schreibfreigabe fragt der Browser je Sitzung neu ab
 * (Chrome/Edge bieten „Bei jedem Besuch zulassen" an). Nach „Nicht zulassen"
 * fragt Chrome in dieser Sitzung nicht mehr (siehe freigabe).
 *
 * Rückfall auf den normalen Download — wie vor Abschnitt O — ohne Ordner, in
 * Browsern ohne die API, ohne Freigabe und bei jedem Schreibfehler. Eine Datei
 * geht nie verloren: Die SEPA-Einreichung und die Mahnstufe sind beim Abruf
 * schon vermerkt, ein zweiter Abruf ist nicht immer möglich.
 *
 * Bewusst ohne React-Import (Toast kommt als Parameter): Die Node-Prüfungen in
 * backend/tests (test_nachtrag_0910.py, Paket-3-Abnahme der SEPA-Liste) laden
 * diese Datei samt ihren Importen direkt.
 */
import { dateinameAusHeader } from './dateiname';
import { ablageAnzeige, belegablage, istExport, nameMitZaehler, type Belegart } from './belegpfad';

type Erlaubnis = 'granted' | 'denied' | 'prompt';

// Nicht in lib.dom (nur Chromium): Freigabe am Handle und der Ordnerdialog.
interface Ordner extends FileSystemDirectoryHandle {
  queryPermission(d: { mode: 'readwrite' }): Promise<Erlaubnis>;
  requestPermission(d: { mode: 'readwrite' }): Promise<Erlaubnis>;
}
type OrdnerDialog = (o: { id?: string; mode?: 'readwrite'; startIn?: string }) => Promise<FileSystemDirectoryHandle>;

const DB_NAME = 'novaerp-belegordner';
const STORE = 'ordner';
const SCHLUESSEL = 'belege';

function ordnerDialog(): OrdnerDialog | undefined {
  return (window as unknown as { showDirectoryPicker?: OrdnerDialog }).showDirectoryPicker;
}

/** Kann dieser Browser Belege in einen Ordner schreiben? */
export function belegordnerMoeglich(): boolean {
  return typeof window !== 'undefined'
    && window.isSecureContext
    && typeof ordnerDialog() === 'function'
    && typeof indexedDB !== 'undefined';
}

function datenbank(): Promise<IDBDatabase> {
  return new Promise((ok, fehler) => {
    const anfrage = indexedDB.open(DB_NAME, 1);
    anfrage.onupgradeneeded = () => anfrage.result.createObjectStore(STORE);
    anfrage.onsuccess = () => ok(anfrage.result);
    anfrage.onerror = () => fehler(anfrage.error);
  });
}

async function speicher<T>(modus: IDBTransactionMode, tun: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await datenbank();
  try {
    return await new Promise<T>((ok, fehler) => {
      const anfrage = tun(db.transaction(STORE, modus).objectStore(STORE));
      anfrage.onsuccess = () => ok(anfrage.result);
      anfrage.onerror = () => fehler(anfrage.error);
    });
  } finally {
    db.close(); // wartet auf laufende Transaktionen
  }
}

async function gespeicherterOrdner(): Promise<Ordner | null> {
  if (!belegordnerMoeglich()) return null;
  try {
    return ((await speicher('readonly', (s) => s.get(SCHLUESSEL))) as Ordner | undefined) ?? null;
  } catch {
    return null;
  }
}

/** Name des gewählten Ordners, sonst null. */
export async function belegordnerName(): Promise<string | null> {
  return (await gespeicherterOrdner())?.name ?? null;
}

/** Freigabe-Stand für die Einstellungen; null = kein Ordner gewählt. */
export async function belegordnerErlaubnis(): Promise<Erlaubnis | null> {
  const ordner = await gespeicherterOrdner();
  if (!ordner) return null;
  try {
    return await ordner.queryPermission({ mode: 'readwrite' });
  } catch {
    return 'denied';
  }
}

/** Ordner wählen (Einstellungen, direkt aus dem Klick). null = Dialog abgebrochen. */
export async function belegordnerWaehlen(): Promise<string | null> {
  const dialog = ordnerDialog();
  if (!dialog || !belegordnerMoeglich()) return null;
  try {
    const ordner = await dialog({ id: 'novaerp-belege', mode: 'readwrite', startIn: 'documents' });
    await speicher('readwrite', (s) => s.put(ordner, SCHLUESSEL));
    return ordner.name;
  } catch (e) {
    if ((e as { name?: string })?.name === 'AbortError') return null;
    throw e;
  }
}

/** Ordner vergessen: Belege landen wieder im Download-Ordner. */
export async function belegordnerZuruecksetzen(): Promise<void> {
  if (!belegordnerMoeglich()) return;
  await speicher('readwrite', (s) => s.delete(SCHLUESSEL));
}

/**
 * Schreibfreigabe sichern. requestPermission verlangt eine frische
 * Nutzeraktion (Klick, wenige Sekunden): deshalb ruft belegHerunterladen das
 * VOR dem Abruf beim Server auf. Ergebnis (Chromium,
 * chrome_file_system_access_permission_context.cc):
 * - 'granted': frei.
 * - 'prompt': noch offen — Frage weggeklickt, oder ohne Nutzeraktion
 *   (SecurityError). Der Knopf „Zugriff erlauben" in den Einstellungen fragt neu.
 * - 'denied': „Nicht zulassen" bzw. in den Website-Einstellungen gesperrt.
 *   Chrome fragt in dieser Sitzung nicht mehr, auch nicht über den Knopf
 *   (requestPermission endet ohne Frage), erst nachdem alle Tabs dieser Seite
 *   geschlossen waren: ZUGRIFF_WIEDER_ERLAUBEN.
 */
async function freigabe(ordner: Ordner): Promise<Erlaubnis> {
  try {
    if ((await ordner.queryPermission({ mode: 'readwrite' })) === 'granted') return 'granted';
    return await ordner.requestPermission({ mode: 'readwrite' });
  } catch {
    return 'prompt';
  }
}

/** Der Weg nach „Nicht zulassen" (Warn-Toast und Karte in den Einstellungen). */
export const ZUGRIFF_WIEDER_ERLAUBEN = 'Wieder erlauben: alle Tabs dieser Seite schließen und neu öffnen '
  + 'oder Symbol links in der Adresszeile → Website-Einstellungen.';

/** Freigabe aus den Einstellungen anfragen (Knopf „Zugriff erlauben"). */
export async function belegordnerFreigeben(): Promise<boolean> {
  const ordner = await gespeicherterOrdner();
  return ordner ? (await freigabe(ordner)) === 'granted' : false;
}

export interface BelegAngaben {
  art: Belegart;
  /** Belegdatum (JJJJ-MM-TT oder Zeitstempel); fehlt es, gilt heute in Berlin. */
  datum?: string | null;
  /** Dateiname, falls der Server keinen Content-Disposition-Kopf schickt. */
  ersatzname: string;
  /** Standard application/pdf */
  mime?: string;
}

/** Was `laden` liefert: eine Axios-Antwort oder nur die Daten (DATEV). */
export interface Geladen {
  data: BlobPart;
  headers?: unknown;
}

export type BelegErgebnis =
  | { ort: 'ordner'; pfad: string }
  | { ort: 'download'; dateiname: string; hinweis?: string };

/** Das Nötige aus useToast(). */
export interface BelegToast {
  success: (meldung: string) => void;
  warning: (meldung: string, dauer?: number) => void;
}

/**
 * DIE Download-Funktion für Belege und Exporte. Reihenfolge: Ordner und
 * Freigabe (braucht die frische Nutzeraktion), dann `laden` (Server), dann
 * ablegen bzw. herunterladen. `laden` darf null liefern (Rückfrage
 * abgebrochen, nichts zu exportieren): dann geschieht nichts, Ergebnis null.
 * Fehler aus `laden` gehen an den Aufrufer; Fehler beim Ablegen enden im
 * normalen Download mit Hinweis. Mit `toast`: „Gespeichert in …" bzw. der
 * Hinweis; ohne Belegordner keine Meldung (Download wie bisher).
 */
export async function belegHerunterladen(
  angaben: BelegAngaben,
  laden: () => Promise<Geladen | null>,
  toast?: BelegToast,
): Promise<BelegErgebnis | null> {
  const ergebnis = await ablegenOderHerunterladen(angaben, laden);
  if (toast && ergebnis) {
    if (ergebnis.ort === 'ordner') toast.success(`Gespeichert in ${ergebnis.pfad}`);
    else if (ergebnis.hinweis) toast.warning(ergebnis.hinweis, 10000);
  }
  return ergebnis;
}

async function ablegenOderHerunterladen(
  angaben: BelegAngaben,
  laden: () => Promise<Geladen | null>,
): Promise<BelegErgebnis | null> {
  const ordner = await gespeicherterOrdner();
  const frei = ordner ? await freigabe(ordner) : null;

  const geladen = await laden();
  if (!geladen) return null;

  // B7: Der Server benennt die Datei (Belegnummer); ersatzname nur ohne Kopf
  const kopf = (geladen.headers as Record<string, unknown> | undefined)?.['content-disposition'];
  const dateiname = dateinameAusHeader(kopf, angaben.ersatzname);
  const blob = new Blob([geladen.data], { type: angaben.mime ?? 'application/pdf' });

  if (ordner && frei === 'granted') {
    try {
      return { ort: 'ordner', pfad: await ablegen(ordner, angaben, dateiname, blob) };
    } catch (e) {
      herunterladen(blob, dateiname);
      const grund = (e as { name?: string })?.name || 'Fehler';
      return {
        ort: 'download', dateiname,
        hinweis: `Belegordner „${ordner.name}" nicht beschreibbar (${grund}) — ${dateiname} liegt im Download-Ordner.`,
      };
    }
  }
  herunterladen(blob, dateiname);
  if (!ordner) return { ort: 'download', dateiname };
  if (frei === 'denied') {
    // Der Knopf in den Einstellungen hilft hier nicht (siehe freigabe)
    return {
      ort: 'download', dateiname,
      hinweis: `Zugriff auf den Belegordner „${ordner.name}" abgelehnt — ${dateiname} liegt im Download-Ordner. `
        + ZUGRIFF_WIEDER_ERLAUBEN,
    };
  }
  return {
    ort: 'download', dateiname,
    hinweis: `Kein Zugriff auf den Belegordner „${ordner.name}" — ${dateiname} liegt im Download-Ordner. `
      + 'Zugriff erlauben: Einstellungen → Belegordner.',
  };
}

/**
 * Schreibt nach <Ordner>/<Belegart>/<JJJJ-MM>/<Datei>. Liegt dort schon eine
 * Datei gleichen Namens: Belege nur nach Rückfrage ersetzen, sonst daneben als
 * „… (1).pdf"; Exporte immer daneben. Liefert den Pfad für den Toast.
 */
async function ablegen(wurzel: Ordner, angaben: BelegAngaben, dateiname: string, blob: Blob): Promise<string> {
  const ablage = belegablage(angaben.art, angaben.datum, dateiname);
  let ordner: FileSystemDirectoryHandle = wurzel;
  for (const teil of ablage.ordner) {
    ordner = await ordner.getDirectoryHandle(teil, { create: true });
  }

  let datei = ablage.datei;
  if (await vorhanden(ordner, datei)) {
    let n = 1;
    while (n < 1000 && (await vorhanden(ordner, nameMitZaehler(ablage.datei, n)))) n += 1;
    const daneben = nameMitZaehler(ablage.datei, n);
    const ersetzen = !istExport(angaben.art) && window.confirm(
      `„${ablage.datei}" liegt schon in ${[wurzel.name, ...ablage.ordner].join('/')}.\n\n`
      + `OK: ersetzen\nAbbrechen: daneben als „${daneben}" speichern`,
    );
    if (!ersetzen) datei = daneben;
  }

  const handle = await ordner.getFileHandle(datei, { create: true });
  const strom = await handle.createWritable();
  try {
    await strom.write(blob);
    await strom.close();
  } catch (e) {
    await strom.abort().catch(() => undefined);
    throw e;
  }
  return ablageAnzeige(wurzel.name, ablage, datei);
}

async function vorhanden(ordner: FileSystemDirectoryHandle, name: string): Promise<boolean> {
  try {
    await ordner.getFileHandle(name);
    return true;
  } catch (e) {
    const art = (e as { name?: string })?.name;
    if (art === 'NotFoundError') return false;
    if (art === 'TypeMismatchError') return true; // ein Ordner dieses Namens
    throw e;
  }
}

/**
 * Normaler Download wie bisher die Belege im Belegdialog
 * (_openPdfFromResponse): Link einhängen, klicken, wieder herausnehmen, die
 * URL erst nach 5 s freigeben (Safari, Firefox, Hallen-Tablet). Ohne
 * document.body bzw. setTimeout — nur im vm-Kontext der Node-Prüfungen — wie
 * bisher SEPA, DATEV und Mahnung: losgelöst, sofort freigeben.
 */
function herunterladen(blob: Blob, dateiname: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = dateiname;
  const seite = document.body;
  if (seite) seite.appendChild(a);
  a.click();
  if (seite) a.remove();
  if (typeof setTimeout === 'function') setTimeout(() => window.URL.revokeObjectURL(url), 5000);
  else window.URL.revokeObjectURL(url);
}
```

- [ ] **Step 4: Grün bestätigen**

Run: Tests O → **8 passed**. Dann `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/belegordner.ts backend/tests/test_nachtrag_0910.py
git commit -m "feat(belegordner): eine Download-Funktion für Belege — Ordner, Freigabe, Rückfrage, Rückfall auf den Download (O)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13 (O.3): Einstellungen — Belegordner wählen, Zugriff erlauben, zurücksetzen

**Files:**
- Create: `frontend/src/components/domain/BelegordnerKarte.tsx`
- Modify: `frontend/src/pages/Settings.tsx` (Import, Karte im Raster)

**Interfaces:**
- Consumes: die Ordnerfunktionen aus O.2, `Button`/`useToast` (`../ui`), `getErrorMessage`.
- Produces: `BelegordnerKarte`. Ohne API zeigt sie nur einen Hinweis. Ohne Ordner zeigt sie „Belegordner wählen“. Mit Ordner zeigt sie Name und Zugriffsstand mit den Knöpfen „Anderen Ordner wählen“, „Zugriff erlauben“ (nur im Stand `'prompt'`) und „Zurücksetzen“. Im Stand `'denied'` steht statt des Knopfes der Weg `ZUGRIFF_WIEDER_ERLAUBEN` (O-E5a).

**Review Focus (O.3):** Der Ordnerdialog öffnet direkt aus dem Klick. Abbrechen im Dialog ergibt keinen Toast. Ein vom Browser abgelehnter Ordner (Systemordner) ergibt einen Fehler-Toast. Den Knopf „Zugriff erlauben“ gibt es nur dort, wo er wirkt.

- [ ] **Step 1: Karte anlegen**

`frontend/src/components/domain/BelegordnerKarte.tsx` mit genau diesem Inhalt anlegen:

```tsx
import { useEffect, useState } from 'react';
import { FolderOpen } from 'lucide-react';
import { Button, useToast } from '../ui';
import { getErrorMessage } from '../../services/errors';
import {
  belegordnerErlaubnis, belegordnerFreigeben, belegordnerMoeglich, belegordnerName,
  belegordnerWaehlen, belegordnerZuruecksetzen, ZUGRIFF_WIEDER_ERLAUBEN,
} from '../../services/belegordner';

/**
 * Einstellungen → Belegordner (Abschnitt O, Gernot 09.10.2026). Gilt nur für
 * diesen Browser auf diesem Gerät; nichts davon liegt auf dem Server.
 */
export function BelegordnerKarte() {
  const toast = useToast();
  const moeglich = belegordnerMoeglich();
  const [name, setName] = useState<string | null>(null);
  const [erlaubnis, setErlaubnis] = useState<string | null>(null);

  const neuLesen = async () => {
    setName(await belegordnerName());
    setErlaubnis(await belegordnerErlaubnis());
  };

  useEffect(() => {
    if (moeglich) void neuLesen();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moeglich]);

  const waehlen = async () => {
    try {
      const gewaehlt = await belegordnerWaehlen();
      if (gewaehlt) toast.success(`Belegordner: ${gewaehlt}`);
    } catch (e) {
      // z. B. ein Systemordner, den der Browser nicht freigibt
      toast.error(getErrorMessage(e, 'Ordner konnte nicht gewählt werden'));
    }
    await neuLesen();
  };

  const freigeben = async () => {
    if (await belegordnerFreigeben()) toast.success('Zugriff auf den Belegordner erlaubt');
    else toast.warning('Kein Zugriff — Belege landen im Download-Ordner');
    await neuLesen();
  };

  const zuruecksetzen = async () => {
    await belegordnerZuruecksetzen();
    toast.info('Belegordner zurückgesetzt — Belege landen wieder im Download-Ordner');
    await neuLesen();
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title flex items-center gap-2">
          <FolderOpen className="w-5 h-5" />
          Belegordner
        </h3>
      </div>
      <div className="card-body space-y-3">
        {!moeglich ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Dieser Browser kann Belege nicht direkt in einen Ordner speichern — das können Chrome
            und Edge am Computer. Belege landen im Download-Ordner.
          </p>
        ) : (
          <>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              PDFs und Exporte landen direkt im gewählten Ordner, sortiert nach Belegart und Monat,
              z. B. <span className="font-mono">Belege/Rechnungen/2026-10/RE-2026-00006.pdf</span>.
              Gilt nur für diesen Browser auf diesem Gerät.
            </p>
            {name ? (
              <div className="text-sm space-y-1">
                <div>
                  Ordner: <span className="font-medium">{name}</span>
                </div>
                {erlaubnis === 'granted' && (
                  <div className="text-emerald-700 dark:text-emerald-300">Zugriff erlaubt</div>
                )}
                {erlaubnis === 'prompt' && (
                  <div className="text-amber-700 dark:text-amber-300">
                    Der Browser fragt beim nächsten Beleg einmal nach dem Zugriff (je Sitzung;
                    „Bei jedem Besuch zulassen" erspart die Frage).
                  </div>
                )}
                {erlaubnis === 'denied' && (
                  // Kein Knopf: Chrome fragt nach „Nicht zulassen" in dieser Sitzung nicht mehr
                  <div className="text-red-700 dark:text-red-300">
                    Zugriff verweigert — Belege landen im Download-Ordner. {ZUGRIFF_WIEDER_ERLAUBEN}
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm">Kein Ordner gewählt — Belege landen im Download-Ordner.</p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={waehlen}>
                {name ? 'Anderen Ordner wählen' : 'Belegordner wählen'}
              </Button>
              {name && erlaubnis === 'prompt' && (
                <Button size="sm" variant="secondary" onClick={freigeben}>
                  Zugriff erlauben
                </Button>
              )}
              {name && (
                <Button size="sm" variant="ghost" onClick={zuruecksetzen}>
                  Zurücksetzen
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: In die Einstellungen**

In `frontend/src/pages/Settings.tsx` die Zeile

```tsx
import { SepaEinstellungenKarte } from '../components/domain/SepaEinstellungenKarte';
```

ersetzen durch:

```tsx
import { SepaEinstellungenKarte } from '../components/domain/SepaEinstellungenKarte';
import { BelegordnerKarte } from '../components/domain/BelegordnerKarte';
```

und in derselben Datei die Zeile

```tsx
        <SepaEinstellungenKarte />
```

ersetzen durch:

```tsx
        <SepaEinstellungenKarte />
        <BelegordnerKarte />
```

Prüfen: `grep -n "BelegordnerKarte" frontend/src/pages/Settings.tsx` → 2 Treffer.

- [ ] **Step 3: Prüfen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/domain/BelegordnerKarte.tsx frontend/src/pages/Settings.tsx
git commit -m "feat(belegordner): Einstellungen — Belegordner wählen, Zugriff erlauben, zurücksetzen (O)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14 (O.4): Belegdialog und Tagesplan — AB, Lieferschein, Packliste, Rechnung

**Files:**
- Modify: `frontend/src/services/api.ts` (`documentsApi`)
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx` (Importe, `downloadInvoicePdf`, drei Knöpfe)
- Modify: `frontend/src/pages/Tagesplan.tsx` (Import, `packlisteMutation`)

**Interfaces:**
- Produces: Die Lader `documentsApi.confirmationPdf(conf)`, `documentsApi.deliveryNotePdf(note)` und `documentsApi.packingListPdf(note)` (Axios-Antwort mit Blob) ersetzen die drei `download…Pdf`. Im Belegdialog gibt es `belegPdf(angaben, laden)` mit Fehler-Toast „PDF-Download fehlgeschlagen“. Bisher hatten AB, LS und PL keinen.
- Consumes: `belegHerunterladen`, `BelegAngaben`, `Geladen` (O.2), `belegartDerRechnung` (O.1).

**Review Focus (O.4):** Die Packliste im Tagesplan holt die Freigabe erst nach zwei Serveraufrufen (Lieferschein suchen bzw. anlegen). Dauert das länger als die Nutzeraktion gilt, kommt der Download mit Hinweis (O-E5). Die Halle sieht die Einstellungen nicht und hat deshalb keinen Ordner. Am Hallen-Tablet läuft die Packliste also immer über den Rückfall `herunterladen`: eingehängter Link, URL nach 5 s freigegeben wie bisher (O-E8, Abnahme C16).

- [ ] **Step 1: Lader statt Download in `api.ts`**

In `frontend/src/services/api.ts`, Objekt `documentsApi`, den Block

```ts
  downloadConfirmationPdf: (conf: OrderConfirmation) =>
    _openPdfFromResponse(`/sales/confirmations/${conf.id}/pdf`, `${conf.confirmation_number}.pdf`),
```

ersetzen durch:

```ts
  // Abschnitt O: nur laden — ablegen bzw. herunterladen macht belegHerunterladen
  confirmationPdf: (conf: OrderConfirmation) =>
    api.get(`/sales/confirmations/${conf.id}/pdf`, { responseType: 'blob' }),
```

und den Block

```ts
  downloadDeliveryNotePdf: (note: DeliveryNote) =>
    _openPdfFromResponse(`/sales/delivery-notes/${note.id}/pdf`, `${note.delivery_note_number}.pdf`),

  downloadPackingListPdf: (note: DeliveryNote) =>
    _openPdfFromResponse(`/sales/delivery-notes/${note.id}/packing-list/pdf`, `${note.packing_list?.packing_list_number || note.delivery_note_number}.pdf`),
```

ersetzen durch:

```ts
  // Abschnitt O: nur laden — ablegen bzw. herunterladen macht belegHerunterladen
  deliveryNotePdf: (note: DeliveryNote) =>
    api.get(`/sales/delivery-notes/${note.id}/pdf`, { responseType: 'blob' }),

  packingListPdf: (note: DeliveryNote) =>
    api.get(`/sales/delivery-notes/${note.id}/packing-list/pdf`, { responseType: 'blob' }),
```

Prüfen: `grep -c "_openPdfFromResponse" frontend/src/services/api.ts` → `4` (Definition, Warenfluss, zwei Inventur-Aufrufe).

- [ ] **Step 2: Rot bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: genau 4 Fehler `TS2339` (Property … does not exist), und zwar `OrderDocumentsModal.tsx` mit `downloadConfirmationPdf`, `downloadDeliveryNotePdf` und `downloadPackingListPdf` sowie `Tagesplan.tsx` mit `downloadPackingListPdf`.

- [ ] **Step 3: Belegdialog**

In `frontend/src/components/domain/OrderDocumentsModal.tsx` die Zeile

```tsx
import { dateinameAusHeader } from '../../services/dateiname';
```

ersetzen durch:

```tsx
import { belegHerunterladen, type BelegAngaben, type Geladen } from '../../services/belegordner';
import { belegartDerRechnung } from '../../services/belegpfad';
```

In derselben Datei die Funktion `downloadInvoicePdf`, also den Block

```tsx
  const downloadInvoicePdf = async (inv: Invoice) => {
    try {
      const res = await invoicesApi.downloadPdf(inv.id);
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener';
      // B7: Name vom Server (RE-….pdf bzw. Entwurf-….pdf)
      a.download = dateinameAusHeader(res.headers['content-disposition'], `${inv.invoice_number}.pdf`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e: any) {
      toast.error(getErrorMessage(e, 'PDF-Download fehlgeschlagen'));
    }
  };
```

ersetzen durch:

```tsx
  // Abschnitt O: alle PDFs dieses Dialogs über die eine Download-Funktion
  // (Belegordner, sonst Download-Ordner; Name vom Server, B7)
  const belegPdf = (angaben: BelegAngaben, laden: () => Promise<Geladen | null>) =>
    belegHerunterladen(angaben, laden, toast).catch((e) => {
      toast.error(getErrorMessage(e, 'PDF-Download fehlgeschlagen'));
      return null;
    });

  const downloadInvoicePdf = (inv: Invoice) =>
    belegPdf(
      { art: belegartDerRechnung(inv), datum: inv.invoice_date, ersatzname: `${inv.invoice_number}.pdf` },
      () => invoicesApi.downloadPdf(inv.id),
    );
```

In derselben Datei die Zeile (Knopf „PDF“ der Auftragsbestätigung)

```tsx
                      onClick={() => documentsApi.downloadConfirmationPdf(c)}
```

ersetzen durch:

```tsx
                      onClick={() => belegPdf(
                        { art: 'Auftragsbestätigungen', datum: c.issued_at, ersatzname: `${c.confirmation_number}.pdf` },
                        () => documentsApi.confirmationPdf(c),
                      )}
```

In derselben Datei die Zeile (Knopf „LS-PDF“)

```tsx
                        onClick={() => documentsApi.downloadDeliveryNotePdf(n)}
```

ersetzen durch:

```tsx
                        onClick={() => belegPdf(
                          { art: 'Lieferscheine', datum: n.issued_at, ersatzname: `${n.delivery_note_number}.pdf` },
                          () => documentsApi.deliveryNotePdf(n),
                        )}
```

In derselben Datei die Zeile (Knopf „Packliste“)

```tsx
                          onClick={() => documentsApi.downloadPackingListPdf(n)}
```

ersetzen durch:

```tsx
                          onClick={() => belegPdf(
                            {
                              art: 'Packlisten',
                              datum: n.packing_list?.created_at ?? n.issued_at,
                              ersatzname: `${n.packing_list?.packing_list_number || n.delivery_note_number}.pdf`,
                            },
                            () => documentsApi.packingListPdf(n),
                          )}
```

Prüfen: `grep -c "belegPdf(" frontend/src/components/domain/OrderDocumentsModal.tsx` → `4`, `grep -c "dateinameAusHeader" frontend/src/components/domain/OrderDocumentsModal.tsx` → `0`.

- [ ] **Step 4: Tagesplan**

In `frontend/src/pages/Tagesplan.tsx` die Zeile

```tsx
import { invalidateOrderViews } from '../services/orderQueries';
```

ersetzen durch:

```tsx
import { invalidateOrderViews } from '../services/orderQueries';
import { belegHerunterladen } from '../services/belegordner';
```

und in `packlisteMutation` die Zeile

```tsx
      await documentsApi.downloadPackingListPdf(note);
```

ersetzen durch:

```tsx
      // Abschnitt O: Belegordner, sonst Download-Ordner
      await belegHerunterladen(
        {
          art: 'Packlisten',
          datum: note.packing_list?.created_at ?? note.issued_at,
          ersatzname: `${note.packing_list?.packing_list_number || note.delivery_note_number}.pdf`,
        },
        () => documentsApi.packingListPdf(note),
        toast,
      );
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe. `grep -rn "downloadConfirmationPdf\|downloadDeliveryNotePdf\|downloadPackingListPdf" frontend/src | wc -l` → `0`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/components/domain/OrderDocumentsModal.tsx frontend/src/pages/Tagesplan.tsx
git commit -m "feat(belegordner): Auftragsbestätigung, Lieferschein, Packliste und Rechnung im Belegdialog über den Belegordner (O)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 15 (O.5): Rechnungsseite und Lastschriften — Rechnung, Mahnung, DATEV, SEPA-CSV

**Files:**
- Modify: `frontend/src/pages/Invoices.tsx` (Importe, PDF-Knopf, Mahnung, `DatevExportForm.handleExport`)
- Modify: `frontend/src/components/domain/SepaEinzugsliste.tsx` (Import, `einreichen`)

**Interfaces:**
- Consumes: `belegHerunterladen` (O.2), `belegartDerRechnung` (O.1). Weggefallen sind die Importe `dateinameAusHeader` und `ladePdfHerunter` in `Invoices.tsx`.

**Review Focus (O.5):**
- **Mahnung und SEPA:** Die bisherige Rückfrage steht jetzt in `laden`. Ohne Belegordner ändert sich nichts. Mit Belegordner erscheint beim ersten Beleg der Sitzung zuerst die Browser-Freigabe, dann die Rückfrage. Abbrechen erzeugt nichts. Die Mahnstufe bleibt, ebenso der SEPA-Vermerk.
- **DATEV:** „Keine neuen Buchungen“ ergibt wie bisher nur den Info-Toast, kein Ablegen und kein Schließen des Dialogs.
- **SEPA:** Die Paket-3-Abnahme lädt diese Datei in Node und muss unverändert grün bleiben (Stoppregel 4).

- [ ] **Step 1: Ausgangszählung**

Run: `grep -c "a\.download\|ladePdfHerunter\|dateinameAusHeader" frontend/src/pages/Invoices.tsx frontend/src/components/domain/SepaEinzugsliste.tsx`
Erwartet: `…/Invoices.tsx:6` und `…/SepaEinzugsliste.tsx:1` (nach Task 5 unverändert, gemessen: D ändert in `Invoices.tsx` keinen Download).

- [ ] **Step 2: Rechnungsseite**

In `frontend/src/pages/Invoices.tsx` die beiden Zeilen

```tsx
import { dateinameAusHeader } from '../services/dateiname';
import { ladePdfHerunter } from '../services/print';
```

ersetzen durch:

```tsx
import { belegHerunterladen } from '../services/belegordner';
import { belegartDerRechnung } from '../services/belegpfad';
```

In derselben Datei im Knopf „PDF“ der Rechnungstabelle den Block

```tsx
                          try {
                            const response = await invoicesApi.downloadPdf(invoice.id);
                            // B7: Name vom Server (RE-….pdf bzw. Entwurf-….pdf)
                            ladePdfHerunter(
                              response.data,
                              dateinameAusHeader(response.headers['content-disposition'], `${invoice.invoice_number}.pdf`),
                            );
                          } catch (err) {
```

ersetzen durch:

```tsx
                          try {
                            // Abschnitt O: Belegordner nach Belegart und Monat, sonst
                            // Download-Ordner; Name vom Server (B7: RE-….pdf bzw. Entwurf-….pdf)
                            await belegHerunterladen(
                              {
                                art: belegartDerRechnung(invoice),
                                datum: invoice.invoice_date,
                                ersatzname: `${invoice.invoice_number}.pdf`,
                              },
                              () => invoicesApi.downloadPdf(invoice.id),
                              toast,
                            );
                          } catch (err) {
```

In derselben Datei im Knopf „Mahnung“ den Block (die Zeilen `const nextLevel …`, `const stageLabel …` und `const fee …` darüber bleiben)

```tsx
                          if (!confirm(`${stageLabel} mit Gebühr €${fee.toFixed(2)} erzeugen?`)) return;
                          try {
                            const response = await invoicesApi.generatePaymentReminder(invoice.id, nextLevel, fee);
                            const url = window.URL.createObjectURL(new Blob([response.data]));
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `Zahlungserinnerung_${invoice.invoice_number}_Stufe${nextLevel}.pdf`;
                            a.click();
                            window.URL.revokeObjectURL(url);
                            queryClient.invalidateQueries({ queryKey: ['invoices'] });
```

ersetzen durch:

```tsx
                          try {
                            // Abschnitt O: erst die Ordner-Freigabe (braucht den frischen
                            // Klick), dann die Rückfrage, dann erzeugen. Abbrechen → null.
                            const ergebnis = await belegHerunterladen(
                              {
                                art: 'Mahnungen',
                                ersatzname: `Zahlungserinnerung_${invoice.invoice_number}_Stufe${nextLevel}.pdf`,
                              },
                              async () => {
                                if (!confirm(`${stageLabel} mit Gebühr €${fee.toFixed(2)} erzeugen?`)) return null;
                                return invoicesApi.generatePaymentReminder(invoice.id, nextLevel, fee);
                              },
                              toast,
                            );
                            if (!ergebnis) return;
                            queryClient.invalidateQueries({ queryKey: ['invoices'] });
```

In derselben Datei in `DatevExportForm`, Funktion `handleExport`, den Block

```tsx
    try {
      const result = await invoicesApi.exportDatev(formData);
      if (result.record_count === 0) {
        // Bereits exportierte Belege kommen nur mit "erneut exportieren" wieder —
        // eine leere Datei herunterzuladen hilft niemandem.
        toast.info('Keine neuen Buchungen im Zeitraum. Bereits exportierte nur über „Erneut exportieren".');
        return;
      }
      toast.success(`Export erfolgreich: ${result.record_count} Datensätze`);

      // Download CSV
      const blob = new Blob([result.csv_content], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `DATEV_Export_${formData.from_date}_${formData.to_date}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);

      onClose();
    } catch (error) {
```

ersetzen durch:

```tsx
    try {
      // Abschnitt O: Belegordner DATEV-Exporte/<Monat des Zeitraumendes>, sonst Download-Ordner
      const ergebnis = await belegHerunterladen(
        {
          art: 'DATEV-Exporte',
          datum: formData.to_date,
          ersatzname: `DATEV_Export_${formData.from_date}_${formData.to_date}.csv`,
          mime: 'text/csv',
        },
        async () => {
          const result = await invoicesApi.exportDatev(formData);
          if (result.record_count === 0) {
            // Bereits exportierte Belege kommen nur mit "erneut exportieren" wieder —
            // eine leere Datei herunterzuladen hilft niemandem.
            toast.info('Keine neuen Buchungen im Zeitraum. Bereits exportierte nur über „Erneut exportieren".');
            return null;
          }
          toast.success(`Export erfolgreich: ${result.record_count} Datensätze`);
          return { data: result.csv_content };
        },
        toast,
      );
      if (ergebnis) onClose();
    } catch (error) {
```

- [ ] **Step 3: Lastschrift-CSV**

In `frontend/src/components/domain/SepaEinzugsliste.tsx` die Zeile

```tsx
import { Button, Input, useToast } from '../ui';
```

ersetzen durch:

```tsx
import { Button, Input, useToast } from '../ui';
import { belegHerunterladen } from '../../services/belegordner';
```

und in derselben Datei den Anfang von `einreichen`

```tsx
  const einreichen = async () => {
    const ohneMail = einreichbar.filter((z) => z.ankuendigung !== 'RECHTZEITIG');
    let bestaetigt = false;
    if (ohneMail.length > 0) {
      bestaetigt = confirm(
        `Für ${ohneMail.map((z) => z.invoice_number).join(', ')} ist keine rechtzeitige Vorabankündigung per Mail belegt. `
        + 'Wurde sie auf anderem Weg rechtzeitig zugestellt? (Wird an der Rechnung vermerkt.)',
      );
      if (!bestaetigt) return;
    }
    setReicheEin(true);
    try {
      const response = await sepaApi.einreichen(einreichbar.map((z) => z.invoice_id), bestaetigt);
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `Lastschrift-Einreichung_${heute}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success(`${einreichbar.length} Lastschrift(en) als eingereicht vermerkt`);
```

ersetzen durch:

```tsx
  const einreichen = async () => {
    const ohneMail = einreichbar.filter((z) => z.ankuendigung !== 'RECHTZEITIG');
    try {
      // Abschnitt O: erst die Ordner-Freigabe (braucht den frischen Klick), dann
      // die Rückfrage, dann einreichen. Die CSV gibt es nur einmal (zweites
      // Mal 409): Kann der Ordner nicht schreiben, kommt sie als Download.
      const ergebnis = await belegHerunterladen(
        { art: 'Lastschriften', ersatzname: `Lastschrift-Einreichung_${heute}.csv`, mime: 'text/csv' },
        async () => {
          let bestaetigt = false;
          if (ohneMail.length > 0) {
            bestaetigt = confirm(
              `Für ${ohneMail.map((z) => z.invoice_number).join(', ')} ist keine rechtzeitige Vorabankündigung per Mail belegt. `
              + 'Wurde sie auf anderem Weg rechtzeitig zugestellt? (Wird an der Rechnung vermerkt.)',
            );
            if (!bestaetigt) return null;
          }
          setReicheEin(true);
          return sepaApi.einreichen(einreichbar.map((z) => z.invoice_id), bestaetigt);
        },
        toast,
      );
      if (!ergebnis) return;
      toast.success(`${einreichbar.length} Lastschrift(en) als eingereicht vermerkt`);
```

Der Rest von `einreichen` (`neuLaden();`, `catch` mit `fehlertext`, `finally` mit `setReicheEin(false)`) bleibt unverändert.

- [ ] **Step 4: Prüfen**

Run: `grep -c "a\.download\|ladePdfHerunter\|dateinameAusHeader" frontend/src/pages/Invoices.tsx frontend/src/components/domain/SepaEinzugsliste.tsx` → beide `0`.
Run: `grep -c "belegHerunterladen(" frontend/src/pages/Invoices.tsx frontend/src/components/domain/SepaEinzugsliste.tsx frontend/src/components/domain/OrderDocumentsModal.tsx frontend/src/pages/Tagesplan.tsx` → `3`, `1`, `1`, `1`.
Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -q -p no:cacheprovider -k "TestAbnahmeSepaBerlin or TestAbnahmeRechnungsberechtigung" 2>&1 | tail -1` → `5 passed, … deselected` (Stoppregel 4).
Run: `cd frontend && npm run build 2>&1 | tail -1` → `✓ built in …`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Invoices.tsx frontend/src/components/domain/SepaEinzugsliste.tsx
git commit -m "feat(belegordner): Rechnung, Mahnung, DATEV-Export und Lastschrift-CSV über den Belegordner (O)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16 (O.6): Abschluss — Prüfungen, Vollauf, Build, Abschlussmeldung

**Files:** keine Änderung.

- [ ] **Step 1: Node-Prüfungen und Tests O**

Run: `cd frontend && node tests/unit/belegpfad.check.ts && node tests/unit/dateiname.check.ts` → `35 Fälle ok`, `8 Fälle ok`. Dann Tests O → **8 passed**.

- [ ] **Step 2: Prozedur V** → Summenzeile `14 failed, 1709 passed, 2 skipped, 1 error` (= `<B>` 1644 aus der Vorbereitung + 37 D + 20 F + 8 O; im Gesamtlauf gemessen), Abgleich leer.

- [ ] **Step 3: Frontend** — `tsc` ohne Ausgabe, `npm run build` mit `✓ built`.

- [ ] **Step 4: Kein Beleg-Download am Belegordner vorbei**

Run: `grep -rln "createObjectURL" frontend/src | sort`
Erwartet genau diese 7 Dateien (alles andere als Belege, bzw. die zentrale Funktion): `frontend/src/components/common/ExcelImport.tsx`, `frontend/src/components/domain/ChargenGridModal.tsx`, `frontend/src/pages/Dienstplan.tsx`, `frontend/src/pages/DocumentTemplates.tsx`, `frontend/src/services/api.ts`, `frontend/src/services/belegordner.ts`, `frontend/src/services/print.ts`. Eine weitere Datei mit Beleg-Download (etwa aus einem anderen Abschnitt): melden, nicht selbst umbauen. Im Gesamtlauf nach D und F gemessen: genau diese 7.

- [ ] **Step 5: Diff-Prüfung**

Run: `git diff --stat <Basis-O>..HEAD` → genau 11 Dateien: `backend/tests/test_nachtrag_0910.py`, `frontend/src/components/domain/BelegordnerKarte.tsx`, `frontend/src/components/domain/OrderDocumentsModal.tsx`, `frontend/src/components/domain/SepaEinzugsliste.tsx`, `frontend/src/pages/Invoices.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/pages/Tagesplan.tsx`, `frontend/src/services/api.ts`, `frontend/src/services/belegordner.ts`, `frontend/src/services/belegpfad.ts`, `frontend/tests/unit/belegpfad.check.ts`.
Run: `git log --oneline <Basis-O>..HEAD` → fünf Commits (O.1–O.5). `git status --porcelain` → nur die in „Global Constraints“ als sauber genannten `??`-Einträge.

- [ ] **Step 6: Abschlussmeldung** (kurz, mit Zeigern):
  - `<Basis-O>`, Commit-Hashes je Task.
  - Rot/Grün je Task (erwartet vs. gemessen).
  - Prozedur-V-Summenzeile und „Abgleich leer“.
  - Ergebnis der Paket-3-Abnahmetests, `tsc`, Build und Schritt 4.
  - Jede selbst behobene Anker- oder Redaktionsabweichung mit Datei und Funktion.
  - Hinweis: Browser-Probe und Abnahme in Chrome macht der Manager.

---

## Abschluss

### Task 17: Abschluss Nachtrag — Gesamtprüfung und Gesamtmeldung

**Files:** keine Änderung.

- [ ] **Step 1: Alle Nachtrag-Tests** (Befehl „Alle Nachtrag-Tests“ aus Global Constraints) → `65 passed` (37 D + 20 F + 8 O).
- [ ] **Step 2: Bestandstests von D und Abnahmetests von O** — `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_datev_export.py tests/test_gernot_261008.py -q -p no:cacheprovider 2>&1 | tail -1` → `149 passed`; Paket-3-Abnahmetests (Befehl aus Task 15 Step 4) → `5 passed, … deselected` (Stoppregel 4).
- [ ] **Step 3: Prozedur V** — gilt der Lauf aus Task 16 Step 2, wenn seitdem nichts geändert wurde (`git status --porcelain` sauber); sonst neu → `14 failed, 1709 passed, 2 skipped, 1 error`, Abgleich leer.
- [ ] **Step 4: Statisch über alle geänderten Python-Dateien** — `git diff --name-only <Basis>..HEAD -- '*.py' | xargs /opt/homebrew/bin/ruff check --select F821,F823` (aus dem Wurzelverzeichnis, 10 Dateien) → keine Ausgabe, Exit-Code 0.
- [ ] **Step 5: Frontend** — `tsc` ohne Ausgabe, `npm run build` mit `✓ built` (gilt aus Task 16 Step 3, wenn seitdem nichts geändert wurde).
- [ ] **Step 6: Diff und Commits** — `git diff --stat <Basis>..HEAD` → genau die 21 Dateien aus „File Structure“; `git log --oneline <Basis>..HEAD` → 14 Commits in der Reihenfolge D.1–D.5, F.1–F.4, O.1–O.5; `git status --porcelain` → nur die sauberen `??`-Einträge.
- [ ] **Step 7: Gesamtmeldung** (kurz, mit Zeigern; die Abschlussmeldungen D, F, O gehen darin auf): `<Basis>`, `<Basis F>`, `<Basis-O>`; Commit-Hash je Task; Rot/Grün je Task (erwartet vs. gemessen); Summenzeilen der Prozedur V nach Task 4, Task 10 und Task 16; Ergebnisse von Step 1–6; jede selbst behobene Anker- oder Redaktionsabweichung mit Datei und Funktion; Hinweis: Browser-Prüfungen, Browser-Probe O und Produktionsschritte macht der Manager.

---

## Abnahme (Manager, im Arbeitsbaum nachmessen — nicht dem Bericht glauben)

- **Gesamt:** `tests/test_nachtrag_0910.py` `65 passed`; Prozedur V `14 failed, 1709 passed, 2 skipped, 1 error`, Abgleich leer; `ruff` F821/F823 über die 10 Python-Dateien ohne Befund; `tsc` ohne Ausgabe, Build `✓ built`; Diff genau die 21 Dateien aus „File Structure“, 14 Commits mit `Co-Authored-By`-Zeile.
- **D:** Klassen `TestD…` `37 passed`; `tests/test_datev_export.py` + `tests/test_gernot_261008.py` `149 passed`.
- **F** (Diff gegen `<Basis F>`): F-Klassen `20 passed`; Prozedur V ohne Abweichung; `tsc`/Build; Diff genau die 7 Dateien.
- **O** (Diff gegen `<Basis-O>`): Tests O `8 passed`, `belegpfad.check: 35 Fälle ok`, Prozedur V ohne Abweichung, Paket-3-Abnahmetests `5 passed`, `tsc` und Build, Diff genau 11 Dateien, Schritt O.6/4 genau 7 Dateien.

**Browser-Probe (automatisch, echtes Chromium, kein Netz):** Prüft `belegordner.ts` gegen die echte File System Access API. Ein OPFS-Ordner „Belege“ steht dabei für den gewählten Ordner, denn der Ordnerdialog lässt sich nicht automatisieren. Gemessen auf der Kopie: `Browser-Probe O: ok`.

```bash
WURZEL=<Arbeitsbaum>/frontend
mkdir -p /tmp/n0910-o-probe && cd /tmp/n0910-o-probe
printf "import * as bo from '%s/src/services/belegordner';\n(window as unknown as { bo: typeof bo }).bo = bo;\n" "$WURZEL" > entry.ts
"$WURZEL/node_modules/.bin/esbuild" entry.ts --bundle --format=iife --outfile=/tmp/n0910-o-probe/bo.js --log-level=warning
WURZEL="$WURZEL" node probe.mjs     # → Browser-Probe O: ok
```

`/tmp/n0910-o-probe/probe.mjs`:

```js
// Abschnitt O, Manager-Probe: belegordner.ts im echten Chromium (Playwright, headless).
// Der gewählte Ordner ist ein OPFS-Ordner "Belege" (gleiche Schnittstelle wie
// ein Ordner aus showDirectoryPicker). Aufruf: WURZEL=<…>/frontend node probe.mjs
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const WURZEL = process.env.WURZEL;
const { chromium } = createRequire(`${WURZEL}/package.json`)('playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ acceptDownloads: true });
const rueckfragen = []; const antworten = [];
page.on('dialog', async (d) => { rueckfragen.push(d.message()); (antworten.length ? antworten.shift() : true) ? await d.accept() : await d.dismiss(); });
const downloads = [];
page.on('download', (d) => downloads.push(d.suggestedFilename()));
await page.route('http://localhost:4321/**', (r) => r.fulfill({ contentType: 'text/html', body: '<html></html>' }));
await page.goto('http://localhost:4321/');   // localhost = sicherer Kontext
await page.addScriptTag({ content: readFileSync('/tmp/n0910-o-probe/bo.js', 'utf8') });
await page.evaluate(async () => {
  const belege = await (await navigator.storage.getDirectory()).getDirectoryHandle('Belege', { create: true });
  window.showDirectoryPicker = async () => belege;
  window.lies = async (pfad) => {
    let h = await navigator.storage.getDirectory();
    const teile = pfad.split('/');
    for (const t of teile.slice(0, -1)) h = await h.getDirectoryHandle(t);
    return (await (await h.getFileHandle(teile.at(-1))).getFile()).text();
  };
  window.re = (inhalt) => window.bo.belegHerunterladen(
    { art: 'Rechnungen', datum: '2026-10-09', ersatzname: 'Ersatz.pdf' },
    async () => ({ data: inhalt, headers: { 'content-disposition': `attachment; filename="RE-2026-00006.pdf"; filename*=UTF-8''RE-2026-00006.pdf` } }));
});
const ev = (fn, arg) => page.evaluate(fn, arg);
assert.equal(await ev(() => window.bo.belegordnerWaehlen()), 'Belege');
assert.equal(await ev(() => window.bo.belegordnerErlaubnis()), 'granted');
assert.deepEqual(await ev(() => window.re('PDF-1')), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006.pdf' });
antworten.push(true);
await ev(() => window.re('PDF-2'));
assert.equal(await ev(() => window.lies('Belege/Rechnungen/2026-10/RE-2026-00006.pdf')), 'PDF-2');
antworten.push(false);
assert.deepEqual(await ev(() => window.re('PDF-3')), { ort: 'ordner', pfad: 'Belege/Rechnungen/2026-10/RE-2026-00006 (1).pdf' });
assert.equal(rueckfragen.length, 2);
const sepa = () => ev(() => window.bo.belegHerunterladen(
  { art: 'Lastschriften', datum: '2026-10-09', ersatzname: 'Lastschrift-Einreichung_2026-10-09.csv', mime: 'text/csv' },
  async () => ({ data: 'a;b' })));
await sepa();
assert.deepEqual(await sepa(), { ort: 'ordner', pfad: 'Belege/Lastschriften/2026-10/Lastschrift-Einreichung_2026-10-09 (1).csv' });
assert.equal(rueckfragen.length, 2, 'Exporte ohne Rückfrage');
assert.deepEqual(await ev(() => window.bo.belegHerunterladen(
  { art: 'Auftragsbestätigungen', datum: '2026-10-31T23:30:00.123456', ersatzname: 'AB-20261101-0001.pdf' },
  async () => ({ data: 'AB' }))), { ort: 'ordner', pfad: 'Belege/Auftragsbestätigungen/2026-11/AB-20261101-0001.pdf' });
await ev(async () => {   // Datei "Packlisten" blockiert den Unterordner
  const belege = await (await navigator.storage.getDirectory()).getDirectoryHandle('Belege');
  const w = await (await belege.getFileHandle('Packlisten', { create: true })).createWritable(); await w.write('x'); await w.close();
});
const pl = await ev(() => window.bo.belegHerunterladen({ art: 'Packlisten', ersatzname: 'PL-20261009-0001.pdf' }, async () => ({ data: 'PL' })));
assert.equal(pl.ort, 'download'); assert.match(pl.hinweis, /nicht beschreibbar \(TypeMismatchError\)/);
await ev(() => window.bo.belegordnerZuruecksetzen());
assert.deepEqual(await ev(() => window.re('PDF-4')), { ort: 'download', dateiname: 'RE-2026-00006.pdf' });
await page.waitForTimeout(500);
assert.deepEqual(downloads, ['PL-20261009-0001.pdf', 'RE-2026-00006.pdf']);
assert.equal(await ev(() => document.querySelectorAll('a').length), 0, 'Rückfall-Link wieder entfernt');
await browser.close();
console.log('Browser-Probe O: ok');
```

## Manager-Abnahme (kein Worker-Task; jede Schreibaktion mit Freigabe)

**Ablauf rund um den gemeinsamen Deploy** (Einzelheiten in den Unterabschnitten „D — Nach dem Deploy“, „F — Firmendaten: Runbook und Oberfläche“, „O — Belegordner: Oberfläche in Chrome“; Backups WAL-sicher, Memory `novaerp-ssh-wal-backup`):
1. **Lokal, vor dem Deploy:** Browser-Prüfungen DB1–DB6 (Task 5), FB1–FB7 (F, unten), C1–C16 (O, unten) gegen ein Backend auf einer Kopie der Demo- bzw. `minga`-Datenbank; F R2 (Echtdaten-Probe, bytegleiche PDFs); Review Focus Ü1–Ü3.
2. **Produktion lesend:** D Schritt 1 (SQL: nichts exportiert, nur Standardkonten, `DATEV_%` leer) und F R1 (Belegvorlagen, `COMPANY_*`, `EMAILS_FROM_NAME` in DB und Umgebung) für `minga` und `demo`.
3. **Produktion schreibend vor dem Deploy:** D Schritt 2 (`DATEV_EXPORT_SPERRE` und `DATEV_KONTENRAHMEN = SKR04` für `minga`, Skript mit Trockenlauf und Nachprüfung). F braucht keinen Datenschritt; ein gesetztes `EMAILS_FROM_NAME` in der Container-Umgebung vorher entscheiden (F R1). O braucht nichts.
4. **Deploy** einmal für D, F und O (Backups `*-vor-deploy-<hash>-*.db` für minga, demo, demo.seed).
5. **Live:** D Schritt 4 (als Erstes `kontenrahmen(db) == "SKR04"` und Sperre in `minga`; Probeexport nur in `abnahme` mit Backup und Rückspielen); O: C1–C3 kurz auf `demo.novaerp.de` (nie Mahnung oder SEPA in `minga`); F: Karte „Firmendaten“ in `demo` laden (Werte vom Server, kein Fehler); `/health` 200, Startlog ohne Fehler.
6. **Gernot informieren** in einer Nachricht: SKR04 eingestellt, Export gesperrt bis zur Bestätigung (Offene Punkte D 1–7 als Fragenliste); Firmendaten-Karte speichert jetzt auf dem Server, Vorschlag prüfen und speichern, Briefkopf bleibt in den Belegvorlagen (Offene Punkte F 1); Belegordner einrichten (Einstellungen → „Belegordner“) und Offene Punkte O 1–10.
7. **Später:** Freigabe des DATEV-Exports nach schriftlicher Bestätigung des Steuerberaters (D Schritt 6).

### D — Nach dem Deploy (DATEV-Export; Schritte 1–2 laufen vor dem Deploy)

1. **Vor dem Deploy, lesend auf `minga`** (Muster WAL-sicheres Backup und `mode=ro`, Memory `novaerp-ssh-wal-backup`):
   ```sql
   SELECT COUNT(*) FROM invoices WHERE datev_exported = 1;          -- erwartet 0 (sonst ist SKR04 nicht mehr setzbar, D-E2)
   SELECT COUNT(*) FROM payments WHERE datev_exported = 1;          -- erwartet 0
   SELECT buchungskonto, tax_rate, COUNT(*) FROM invoice_lines GROUP BY 1, 2;   -- nur 8300/8400 (ggf. 8100); jedes andere Konto ist ein Sonderkonto → melden, der SKR04-Export bricht sonst mit 409 ab
   SELECT COUNT(*) FROM invoice_lines WHERE tax_rate = 'STEUERFREI'; -- Offener Punkt 2
   SELECT key, value FROM app_settings WHERE key LIKE 'DATEV_%';    -- erwartet leer
   ```
2. **Vor dem Deploy, schreibend** (WAL-sicheres Backup `minga-vor-datev-skr04-<Zeit>.db`, Skript mit Trockenlauf und `APPLY`): zwei Zeilen in `app_settings` (`key`, `value`, `is_secret=0`, `updated_at=jetzt`): `DATEV_EXPORT_SPERRE` = „Kontierung SKR04 vom Steuerberater noch nicht bestätigt — Freigabe über NovaERP“ und `DATEV_KONTENRAHMEN` = **genau** `SKR04` (Literal im Skript, fünf Zeichen, Großbuchstaben, ohne Leerzeichen). Der alte Code ignoriert unbekannte Schlüssel (`list_settings` iteriert nur `KNOWN_SETTINGS`), es gibt also kein Fenster ohne Sperre.
   **Warum genau:** Der direkte DB-Schreibweg umgeht `rahmen_pruefen`. Nach dem Deploy ruft `add_line` `kontenrahmen(db)` bei jeder neuen Position auf; ein unlesbarer Wert (z. B. `SKR 04`) wirft dort `ValueError` → jede neue Rechnungsposition in `minga` scheitert mit 400 (auch Monatsrechnungs-Lauf, Sammelrechnung, Leergut), `GET /invoices/datev-export/einstellungen` antwortet 500, und die Karte kann es nicht reparieren (`wechsel_pruefen` liest den alten Wert und lehnt mit 422 ab). Darum prüft das Skript **nach** `APPLY` im selben Lauf lesend nach und bricht laut ab, wenn eine Bedingung nicht stimmt:
   ```sql
   SELECT value, length(value) FROM app_settings WHERE key = 'DATEV_KONTENRAHMEN';   -- genau eine Zeile: SKR04 | 5
   SELECT COUNT(*) FROM app_settings WHERE key = 'DATEV_EXPORT_SPERRE' AND trim(value) <> '';   -- 1
   ```
   Weicht etwas ab: vor dem Deploy aus `minga-vor-datev-skr04-<Zeit>.db` zurückspielen bzw. den Wert per Skript auf `SKR04` korrigieren, nicht deployen. Reparatur nach dem Deploy ebenfalls nur per Skript (Backup + `APPLY`), nicht über die Oberfläche.
3. **Deploy** wie bei den Paketen (Backups `*-vor-deploy-<hash>-*.db` für minga, demo, demo.seed).
4. **Live-Prüfung:** `/health` 200; openapi enthält `/api/v1/invoices/datev-export/einstellungen`; im Container lesend für `minga`, **als Erstes** (ein falscher Wert sperrt sonst jede neue Rechnungsposition, Schritt 2): `kontenrahmen(db) == "SKR04"`, `export_sperre(db)` = Grund. Im Testmandanten `abnahme` (Admin-Login lokal): **vorher** WAL-sicheres Backup `abnahme-vor-datev-probe-<Zeit>.db` (Freigabe); Einstellungen → „DATEV-Export“ zeigt SKR03, Wechsel auf SKR04, Dialog zeigt 4300/4400/4100/1800/1600, Export einer Proberechnung liefert Gegenkonto 4300/4400, danach Wechsel auf SKR03 → 422. Der Probeexport setzt `datev_exported` — ohne Rückspielen bliebe `abnahme` dauerhaft auf SKR04 (D-E2) und spätere Abnahmen liefen nicht mehr über SKR03. Darum **danach** `abnahme` aus diesem Backup zurückspielen (Freigabe; Backup-API in umgekehrter Richtung, Sicherung → `/data/tenants/abnahme.db`, `pragma integrity_check` = `ok`, kein `cp`; zwischen Backup und Rückspielen keine anderen Abnahmen in `abnahme`) und nachprüfen: Karte zeigt wieder SKR03, `SELECT COUNT(*) FROM invoices WHERE datev_exported = 1` wie vor dem Backup. Bundle enthält „DATEV-Export gesperrt“; Startlog ohne Fehler.
5. **Gernot informieren:** SKR04 eingestellt, Export bleibt gesperrt, bis der Steuerberater die Kontierung bestätigt (Offene Punkte 1–7 als Fragenliste).
6. **Freigabe später:** nach schriftlicher Bestätigung des Steuerberaters `DATEV_EXPORT_SPERRE` löschen (Backup + Skript, oder `PATCH /admin/settings` mit `""`); erster Export gemeinsam mit dem Steuerberater als Probeimport.

### F — Firmendaten: Runbook und Oberfläche

**R1 — vor dem Deploy, Produktion nur lesend:** Skript `/tmp/n0910/f-runbook/firmendaten_pruefung.py` (unten) nach `/root/` kopieren, dann `docker exec -i "$C" python3 - minga < /root/firmendaten_pruefung.py` (und `demo`). Erwartet für `minga`: alle fünf Belegarten `header_text=ja footer_text=ja`, keine `COMPANY_*`-Zeile in der Datenbank, `EMAILS_FROM_NAME = 'MingaGreens GmbH'`. Steht bei einer Belegart `NEIN` oder `KEINE VORLAGE`: kein Abbruchgrund — dort druckt der Beleg nach dem Speichern der Karte die Firmendaten statt „Minga Greens“ (je Block einmal); ein schon versendeter Beleg dieser Art ließe sich danach nicht erneut senden (409 „… Belegvorlage wurden seit dem ersten Versand … geändert“). Gernot dann vor dem Speichern darauf hinweisen oder den Vorlagentext dort ergänzen (mit Freigabe). Lokal an einer Kopie des August-Backups nachgespielt: alle fünf `ja`, `EMAILS_FROM_NAME = 'MingaGreens GmbH'`.
Das Skript zeigt im Container zusätzlich die **Umgebung** (`COMPANY_*` und `EMAILS_FROM_NAME`; gilt für alle Mandanten, dieselben Werte wie in den Coolify-Variablen). Erwartet: `(keine)`. Steht dort `EMAILS_FROM_NAME`, grüßen ab F alle Mandanten ohne eigenen Firmen- und Absendernamen in der DB (Ausgabe für `demo`; künftige Mandanten) mit diesem Wert statt „Ihr Team“ — im Von-Feld ihrer Mails steht er schon heute. Minga ist nicht betroffen (eigener DB-Wert). Vor dem Deploy entscheiden (Freigabe): Wert passt für alle → nichts tun; sonst den Wert je betroffenem Mandanten in der SMTP-Karte setzen oder die Variable in Coolify entfernen. Steht dort ein `COMPANY_*`-Wert: zeigt die Karte als „Vorgabe des Servers“, druckt ihn bei Belegen ohne Vorlagentext — ebenso vor dem Deploy klären.

**R2 — Echtdaten-Probe (lokal, Kopie des Deploy-Backups):** RE-2026-00001 als PDF vor und nach `PATCH /admin/settings` mit Gernots Firmendaten über den Branch-Code (TestClient wie in der Testumgebungs-Notiz, `TENANTS_DIR` auf die Kopie) → bytegleich; ebenso eine versendete AB (`GET /confirmations/{id}/pdf`, SHA-256 = `attachment_sha256` im Versandprotokoll). Kopie danach löschen.

**Oberfläche** (lokal, Rolle admin, Browser):
- **FB1** Im Browser `localStorage.minga_settings_company` auf `{"name":"MingaGreens GmbH","address":"Wittenberger Straße 17, 80993 München","taxId":"DE328451962","email":"info@minga-greens.de","phone":"+49 89 123 456 0","website":"www.minga-greens.de"}` setzen, Einstellungen öffnen → gelber Hinweis nennt nur „Firmenname, Straße und Hausnummer, PLZ und Ort“; Felder vorbelegt („Wittenberger Straße 17“ / „80993 München“); USt-IdNr., E-Mail, Telefon, Website leer (Beispielwerte nicht übernommen).
- **FB2** „Speichern“ → Toast „Firmendaten gespeichert“, Hinweis weg, `localStorage.minga_settings_company` gelöscht; Seite neu laden → Werte vom Server, kein Hinweis.
- **FB3** IBAN `DE89 3704 0044 0532 0130 01` → Toast „IBAN: IBAN-Prüfziffer stimmt nicht“, nichts gespeichert; mit `…00` gespeichert und als `DE89370400440532013000` angezeigt.
- **FB4** „Vorschlag verwerfen“ (mit neu gesetztem `localStorage` und leeren Serverfeldern) → Felder leer, Hinweis weg, Eintrag gelöscht.
- **FB5** SMTP-Karte „Speichern“ → im Netzwerk-Tab enthält der PATCH-Body nur die acht SMTP-Schlüssel; Firmendaten-Karte unverändert, ungespeicherte Eingaben dort bleiben stehen.
- **FB6** Beleg-Mail an eine eigene Adresse (AB eines Testkunden) → Gruß „Mit freundlichen Grüßen / <Firmenname>“; ohne Firmennamen der Absendername.
- **FB7** Firmenname mit `Huber & Soehne` speichern → Toast „Firmendaten gespeichert“; Backend während der geöffneten Seite stoppen und Seite neu laden → Karte zeigt „Firmendaten ließen sich nicht laden: …“ (nicht „nur Administratoren“).

**`/tmp/n0910/f-runbook/firmendaten_pruefung.py`** (nur lesend: im Container `mode=ro`, lokal `immutable=1` und nur an einer WAL-sicheren Kopie; gibt keine Geheimnisse aus):

<!-- F-BLOCK: f-runbook -->
```python
"""Abschnitt F, Runbook: Belegvorlagen und Firmendaten eines Mandanten lesen.
Nur lesend. Gibt keine Werte von Geheimnissen aus (nur Firmendaten und
Absendername).

Aufruf im Container:  docker exec -i "$C" python3 - minga < firmendaten_pruefung.py
Lokal (Kopie):        python3 firmendaten_pruefung.py minga /pfad/zur/kopie.db

Im Container: laufende DB mit mode=ro (liest den WAL mit). Lokal nur gegen
eine WAL-sichere Kopie (Backup-API), nie gegen backend/data/ direkt — auch
mode=ro legt im WAL-Modus -shm/-wal neben der Datei an bzw. ändert sie.
Lokal deshalb immutable=1: keine Nebendateien, geht auch in schreibgeschützten
Verzeichnissen; Inhalte einer -wal-Datei sähe es nicht, daher Abbruch, wenn
eine nicht leere -wal-Datei daneben liegt.
"""
import json
import os
import sqlite3
import sys

FIRMENDATEN = (
    "COMPANY_NAME", "COMPANY_ADDRESS_LINE1", "COMPANY_ADDRESS_LINE2",
    "COMPANY_USTID", "COMPANY_STEUERNR", "COMPANY_PHONE", "COMPANY_EMAIL",
    "COMPANY_WEBSITE", "COMPANY_BANK_NAME", "COMPANY_IBAN", "COMPANY_BIC",
    "COMPANY_SEPA_GLAEUBIGER_ID", "EMAILS_FROM_NAME",
)

slug = sys.argv[1] if len(sys.argv) > 1 else "minga"
lokal = len(sys.argv) > 2
pfad = sys.argv[2] if lokal else f"/data/tenants/{slug}.db"
if lokal:
    wal = pfad + "-wal"
    if os.path.exists(wal) and os.path.getsize(wal) > 0:
        sys.exit(f"{wal} ist nicht leer: erst WAL-sicher kopieren (Backup-API), dann die Kopie prüfen.")
    con = sqlite3.connect(f"file:{pfad}?mode=ro&immutable=1", uri=True)
else:
    con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)

print(f"Mandant {slug}")
print("Belegvorlagen (Briefkopf / Fusszeile eigener Text, Abschnitte aktiv):")
gefunden = set()
for typ, texte, abschnitte in con.execute(
        "SELECT document_type, texts, sections FROM document_templates ORDER BY document_type"):
    gefunden.add(typ)
    t = json.loads(texte) if texte else {}
    s = {x.get("key"): x.get("enabled", True) for x in (json.loads(abschnitte) if abschnitte else [])}
    print(f"  {typ:22} header_text={'ja' if (t.get('header_text') or '').strip() else 'NEIN'}"
          f"  footer_text={'ja' if (t.get('footer_text') or '').strip() else 'NEIN'}"
          f"  header_logo={s.get('header_logo', True)}  footer={s.get('footer', True)}")
for typ in sorted({"RECHNUNG", "AUFTRAGSBESTAETIGUNG", "LIEFERSCHEIN", "VERPACKUNGSLISTE", "MAHNUNG"} - gefunden):
    print(f"  {typ:22} KEINE VORLAGE (Code-Standard: Firmendaten bzw. 'Minga Greens')")
print("Einstellungen (Datenbank):")
for key, wert in con.execute(
        "SELECT key, value FROM app_settings WHERE key LIKE 'COMPANY_%' OR key = 'EMAILS_FROM_NAME' ORDER BY key"):
    print(f"  {key} = {wert!r}")
con.close()
if not lokal:
    print("Umgebung des Containers (gilt fuer alle Mandanten):")
    umgebung = [k for k in FIRMENDATEN if os.environ.get(k)]
    for key in umgebung:
        print(f"  {key} = {os.environ[key]!r}")
    if not umgebung:
        print("  (keine)")
```

**Rücknahme:** reiner Code, keine Daten- oder Schemaänderung. Ein Code-Rollback lässt gespeicherte `COMPANY_*` stehen; der alte Code nutzt sie wie heute (Belegvorlage hat dort ebenfalls Vorrang).

### O — Belegordner: Oberfläche in Chrome

**Oberfläche in Chrome** (lokal: Vite `:5173` gegen ein Backend auf einer Kopie der Demo- bzw. `minga`-Datenbank, Rolle admin; `localhost` gilt als sicherer Kontext. Nach dem Deploy kurz C1–C3 auf `demo.novaerp.de` wiederholen, nie Mahnung oder SEPA im Mandanten `minga`):
- **C1 Ordner wählen.** Einstellungen → Karte „Belegordner“ zeigt „Kein Ordner gewählt — Belege landen im Download-Ordner.“ Auf „Belegordner wählen“ klicken, im Dialog unter Dokumente einen neuen Ordner „Belege“ anlegen und wählen. Chrome fragt nach dem Bearbeiten: zulassen. Danach zeigt die Karte „Ordner: Belege“ und „Zugriff erlaubt“, als Toast kommt „Belegordner: Belege“. Den Ordner direkt selbst, den Benutzerordner oder Systemordner lehnt Chrome mit eigener Meldung ab: einen Unterordner wählen.
- **C2 Rechnung.** Rechnungen → „PDF“ einer festgeschriebenen Rechnung. Toast „Gespeichert in Belege/Rechnungen/<Monat des Rechnungsdatums>/RE-….pdf“. Die Datei liegt im Explorer bzw. Finder dort. Download-Leiste und Download-Ordner bleiben leer.
- **C3 Noch einmal.** Dieselbe Rechnung erneut: Rückfrage „„RE-….pdf“ liegt schon in Belege/Rechnungen/<Monat> … OK: ersetzen / Abbrechen: daneben als „RE-… (1).pdf“ speichern“. OK ersetzt (Änderungszeit neu), Abbrechen legt `RE-… (1).pdf` daneben.
- **C4 Andere Rechnungsarten.** Eine Stornorechnung landet in `Stornorechnungen/`, ein Leergutbeleg in `Leergut/`, eine Proforma in `Proformarechnungen/`, ein Entwurf in `Entwürfe/` (Datei `Entwurf-….pdf`). Eine Monatsrechnung landet in `Rechnungen/`.
- **C5 Belegdialog einer Bestellung.** AB-PDF → `Auftragsbestätigungen/<Monat>/AB-….pdf`. LS-PDF → `Lieferscheine/`. Packliste → `Packlisten/`. Rechnung → wie C2. Den Monat bestimmt das Ausstellungsdatum.
- **C6 Mahnung** (nur lokal oder Demo). Auf „Mahnung“ klicken, die Rückfrage „Zahlungserinnerung mit Gebühr €0.00 erzeugen?“ mit Abbrechen beantworten. Dann wird nichts gespeichert und die Mahnstufe bleibt (Liste neu laden). Mit OK landet `Mahnungen/<heutiger Monat>/Zahlungserinnerung_RE-…_Stufe1.pdf` im Ordner.
- **C7 DATEV.** Zeitraum 01.09.–30.09. ergibt `DATEV-Exporte/2026-09/DATEV_Export_2026-09-01_2026-09-30.csv`. Derselbe Zeitraum mit „Erneut exportieren“ ergibt ohne Rückfrage `… (1).csv`. Ohne neue Buchungen kommt nur der Info-Toast, und der Dialog bleibt offen.
- **C8 SEPA-CSV** (nur lokal oder Demo). „Bei der Bank einreichen (CSV)“ legt `Lastschriften/<heutiger Monat>/Lastschrift-Einreichung_<heute>.csv` ab. Eine zweite Einreichung am selben Tag ergibt ohne Rückfrage `… (1).csv`.
- **C9 Neue Sitzung.** Chrome ganz schließen und neu öffnen. Die Karte zeigt jetzt „Der Browser fragt beim nächsten Beleg einmal nach dem Zugriff …“. Beim nächsten „PDF“ kommt Chromes Frage, und zwar vor dem PDF. „Bei jedem Besuch zulassen“ wählen, dann fragt Chrome nach einem weiteren Neustart nicht mehr.
- **C10 Ordner weg.** Den Ordner `Belege` im Explorer umbenennen und „PDF“ klicken. Es kommt der Warn-Toast „Belegordner „Belege“ nicht beschreibbar (<Grund>, erwartet NotFoundError) — RE-….pdf liegt im Download-Ordner.“, und die Datei liegt im Download-Ordner. Den Ordner danach zurück umbenennen.
- **C11 Frage weggeklickt.** In einer neuen Sitzung Chromes Frage beim „PDF“ mit Esc bzw. dem Kreuz schließen, also **nicht** „Nicht zulassen“ wählen. Es kommen der Warn-Toast „Kein Zugriff auf den Belegordner „Belege“ — RE-….pdf liegt im Download-Ordner. Zugriff erlauben: Einstellungen → Belegordner.“ und ein normaler Download. Die Karte zeigt „Der Browser fragt beim nächsten Beleg …“ und den Knopf „Zugriff erlauben“. Klick → Frage → zulassen → „Zugriff erlaubt“.
- **C11b Zugriff verweigert** (O-E5a, aus der Chromium-Quelle abgeleitet, hier erstmals im Browser). In einer neuen Sitzung Chromes Frage mit „Nicht zulassen“ beantworten. Es kommen der Warn-Toast „Zugriff auf den Belegordner „Belege“ abgelehnt — RE-….pdf liegt im Download-Ordner. Wieder erlauben: alle Tabs dieser Seite schließen und neu öffnen oder Symbol links in der Adresszeile → Website-Einstellungen.“ und ein normaler Download. Ein zweites „PDF“ zeigt keine Frage, nur denselben Hinweis. Die Karte zeigt „Zugriff verweigert — …“ mit diesem Weg und **keinen** Knopf „Zugriff erlauben“. Dann alle Tabs dieser Adresse schließen, andere Seiten dürfen offen bleiben, und die Seite neu öffnen. Die Karte zeigt wieder „Der Browser fragt …“ mit Knopf. Klick → Frage → zulassen → „Zugriff erlaubt“. Danach noch einmal „Nicht zulassen“ provozieren und den zweiten Weg prüfen: Symbol links in der Adresszeile → Website-Einstellungen, dort „Dateien bearbeiten“ bzw. „Berechtigungen zurücksetzen“, dann die Seite neu laden. Hilft dieser Weg ohne Schließen der Tabs nicht, wird der Teil „oder Symbol links in der Adresszeile → Website-Einstellungen“ aus `ZUGRIFF_WIEDER_ERLAUBEN` gestrichen. Das ist eine reine Textänderung samt Testerwartung in `test_freigabe_vor_dem_laden_sonst_download_mit_hinweis`.
- **C12 Zurücksetzen.** Nach „Zurücksetzen“ zeigt die Karte „Kein Ordner gewählt …“. Das nächste PDF landet im Download-Ordner, ohne Toast.
- **C13 Safari oder Firefox.** Die Karte zeigt „Dieser Browser kann Belege nicht direkt in einen Ordner speichern — das können Chrome und Edge am Computer …“ und keinen Knopf. PDFs aus Rechnungsliste und Belegdialog (RE, AB, LS, PL) sowie der DATEV-Export kommen wie seit B7 mit der Belegnummer bzw. dem Zeitraum im Download-Ordner an. Das prüft den Rückfall `herunterladen` (O-E8) außerhalb von Chromium.
- **C14 Edge.** C1 bis C3 kurz wiederholen.
- **C15 Rolle Buchhaltung.** Ohne „Einstellungen“ in der Navigation laufen die Downloads wie heute.
- **C16 Packliste am Hallen-Tablet** (das echte Gerät der Halle, Rolle Produktion, nicht gemessen). Tagesplan → „Packliste“ bei einer Bestellung mit und einer ohne Lieferschein. Das PDF kommt wie vor O an, mit der Packlistennummer als Name, und lässt sich öffnen und drucken. Kein Toast, die Halle hat keinen Belegordner. Dasselbe am Tablet einmal mit „PDF“ in der Rechnungsliste, falls dort jemand mit Rechnungsrecht arbeitet. Kommt nichts an oder öffnet sich eine leere Seite: Befund mit Gerät, Betriebssystem und Browser melden. Dann ist `herunterladen` (O-E8) nachzubessern, etwa mit längerer Frist oder mit `target=_blank` wie früher `_openPdfFromResponse`.

## Offene Punkte

Die Nummern gelten je Abschnitt: „Offener Punkt n“ im Text eines Abschnitts meint dessen Liste hier.

**Woher kommt der Briefkopf?** (Gernots Rückfrage „Das steht doch schon drinnen? Wo sollte ich das noch eintragen?“) Briefkopf und Fuß aller Belege kommen aus den **Belegvorlagen** (Admin → Belegvorlagen, `document_templates.texts.header_text`/`footer_text` je Belegart, dazu das Logo); `pdf_service` druckt je Block **entweder** den Vorlagentext **oder** die Firmendaten `COMPANY_*`, nie beide. Belegt an RE-2026-00001 (Name, Anschrift, Bank, Geschäftsführung, USt-ID, Steuer-Nr., HRB, Öko-Kontrollnummer bei leeren `COMPANY_*`) und am August-Backup (alle fünf Vorlagen mit Text). Gernots Eintrag in der Karte „Firmendaten“ lag nur im Browser; nach F erscheint er dort als Vorschlag und wirkt nach dem Speichern auf Gruß und Betreff der Beleg-Mails, auf Belege ohne eigenen Vorlagentext und auf den Dienstplan — nicht auf den Briefkopf. **Offen:** der heutige Stand der übrigen vier Vorlagen in Produktion (F R1, vor dem Deploy).

### D — DATEV-Export (Steuerberater, Gernot, intern)

Für den (neuen) Steuerberater — **Kontierung vor dem ersten Export zu bestätigen**, bis dahin bleibt der Export für `minga` gesperrt:

1. **Kontenzuordnung SKR04:** Erlöse 7 % → 4300, Erlöse 19 % → 4400, steuerfrei → 4100, Bank → 1800, Kasse → 1600, Debitoren 10000 ff. (bzw. `customer.datev_account`), BU-Schlüssel leer (4300/4400 als Automatikkonten). Gibt es mehrere Bankkonten (z. B. 1800/1810), auf die Zahlungen getrennt gehören?
2. **Steuerfreie Umsätze:** Der Code kennt nur einen Fall `STEUERFREI` (0 %) und druckt dafür den § 13b-Vermerk; DATEV bekäme 4100 (§ 4 Nr. 8 ff.). Gibt es bei MingaGreens steuerfreie Umsätze überhaupt? Wenn ja, welche (innergemeinschaftliche Lieferung → 4125 und anderer Rechnungsvermerk, Ausfuhr → 4120, § 13b → 4337)? Das wäre ein eigener Steuerfall im Code, nicht Teil von D.
3. **Pfand und Leergut:** heute auf Erlöse 19 % (4400), Leergut-Minderungen als H auf 4400. Gewünscht ein eigenes Konto (Erlöse Leergut, Pfandverbindlichkeit)? Dafür bräuchte das Pfandprodukt ein eigenes Erlöskonto (Erweiterung, nicht D).
4. **Zahlungswege:** EC, Kreditkarte, PayPal und SEPA-Lastschrift laufen wie bisher auf die Bank (1800); Geldtransit (SKR04 1460) oder ein eigenes PayPal-Konto? Rücklastschrift-Gebühren erfasst das System nicht.
5. **Dateiformat:** Der Export ist ein vereinfachter Buchungsstapel **ohne EXTF-Kopf** (B9-Rest, Spec Offene Entscheidung 5). Für den Import in DATEV Rechnungswesen bzw. Unternehmen online braucht es voraussichtlich den EXTF-Kopf mit Berater- und Mandantennummer, WJ-Beginn und Sachkontenlänge — die Sperre bleibt mindestens bis dahin. Alternativ nur Belegbilder über Unternehmen online?

Für Gernot:

6. **DATEV Mittelstand Faktura:** Werden Rechnungen nur noch in NovaERP geschrieben? Fakturiert MingaGreens parallel in Faktura, stehen die Erlöse in DATEV doppelt.
7. **Neuer Steuerberater:** Name und Kontakt, Berater-/Mandantennummer, Wirtschaftsjahr, ab wann SKR04 gilt. Bisher ist nichts exportiert; RE-2026-00001 ff. gehen beim ersten Export mit SKR04-Konten raus (abgebildet, nicht umgeschrieben).

Intern (niedrig):

8. Der Kopf `Invoice.buchungskonto` wird weiter gespeichert und beim Storno kopiert, aber nirgends gelesen — unverändert gelassen.
9. Gernot kann die Sperre in der Oberfläche nicht selbst aufheben (D-E5, gewollt). Wünscht er das, wäre es ein Schalter in der Karte „DATEV-Export“.

### F — Firmendaten

1. **Gernot (Hinweis, keine Rückfrage):** Die Karte „Firmendaten“ speichert jetzt auf dem Server. Was er dort bisher im Browser eingetragen hatte, steht als Vorschlag in der Karte — bitte prüfen und speichern. Briefkopf und Fußzeile der Belege kommen weiter aus Admin → Belegvorlagen; die Firmendaten ändern daran nichts (keine Doppelung). Sie wirken auf Gruß und Betreff der Beleg-Mails, auf Belege ohne eigenen Vorlagentext und auf den Dienstplan.
2. **Belegvorlagen-Vorschau 500 (Nebenbefund 3, nicht in F):** `preview.pdf` scheitert für RECHNUNG an `beleg_art`, `service_period_start`/`_end` und `sku` je Zeile, für AUFTRAGSBESTAETIGUNG/LIEFERSCHEIN an `product_sku` je Zeile und `customer_reference`, für VERPACKUNGSLISTE an `customer_reference` (Ersatzobjekte in `document_template_service.build_dummy_*`, seit den Feldern aus Paket 1–3 unvollständig; gemessen auf `df84f7b`). Gernot sieht beim Pflegen von Briefkopf/Fuß einen Fehler statt der Vorschau. Empfehlung: eigener kleiner Fix (S) mit Test „Vorschau je Belegart 200“.
3. **Mahnungen** (nicht in F): Das Mahnungs-PDF grüßt fest „Ihr Minga-Greens-Team“ (`generate_payment_reminder_pdf`, Abschnitt `regards`), die Mahn-Mails aus `app/core/email.py` fest „Ihr Team“ — für andere Mandanten falsch. Später auf `belegversand.absendername` umstellen.
4. **Weitere Browser-Attrappen auf der Einstellungsseite** (nicht in F): „Benachrichtigungen“ und „Forecasting“ speichern nur in `localStorage`; „Systeminfo“ zeigt fest „PostgreSQL 15“ und „Minga-Greens ERP v1.0.0“; „API-Schlüssel – Regenerieren“ ist ein Toast. Gleiche Fehlerklasse wie die Firmendaten-Karte — anbinden oder entfernen.
5. **Fuß ohne Vorlagentext** druckt die Adresse nur, wenn „PLZ und Ort“ gesetzt ist (`render_company_footer_block`, unverändert). Für Minga ohne Wirkung (Vorlagentext).
6. **Umgebungs-Rückfall:** `load_company_settings` und der neue Gruß lesen `COMPANY_*` bzw. `EMAILS_FROM_NAME` weiter mit Rückfall auf Container-Variablen (gelten für alle Mandanten). Die Karte zeigt solche Werte nur als Hinweis und übernimmt sie nicht. Vor dem Deploy prüfen, ob `COMPANY_*` oder `EMAILS_FROM_NAME` in der Umgebung gesetzt sind — das Runbook-Skript zeigt beides im Container (Abnahme R1); ein gesetztes `EMAILS_FROM_NAME` (Beispiel im Docstring von `email_service.py`: „Minga Greens“) stünde ab F im Gruß aller Mandanten ohne eigenen Wert.

### O — Belegordner (für Gernot)

1. **Wer wählt den Ordner?** Die Wahl steckt in den Einstellungen, und die sieht nur der Admin. Sollen auch Buchhaltung und Vertrieb einen Belegordner wählen können? Dann käme ein Knopf auf die Rechnungsseite.
2. **Ordnerstruktur:** `Belege/<Belegart>/<JJJJ-MM>/<Belegnummer>.pdf` mit den Ordnern Rechnungen, Stornorechnungen, Gutschriften, Leergut, Proformarechnungen, Entwürfe, Auftragsbestätigungen, Lieferscheine, Packlisten, Mahnungen, DATEV-Exporte und Lastschriften. Passt das? Oder lieber Jahr und Monat getrennt (`2026/10`) bzw. der Monat zuerst (`2026-10/Rechnungen`)?
3. **Proforma:** Proformarechnungen bekommen einen eigenen Ordner `Proformarechnungen/`. Sie sind keine Steuerrechnung und sollen in `Rechnungen/` nicht mitgebucht werden. Lieber doch zu den Rechnungen?
4. **Entwürfe:** Rechnungsentwürfe zum Prüfen landen in `Entwürfe/`. Sollen sie stattdessen gar nicht in den Belegordner, also wie bisher in den Download-Ordner?
5. **Gleicher Beleg zweimal:** Heute fragt die App „ersetzen oder daneben speichern (1)“. Soll sie lieber immer ersetzen oder immer daneben speichern?
6. **Exporte:** DATEV-Export und Lastschrift-Datei landen auch im Belegordner, und zwar immer neu daneben, nie ersetzt. Gewollt?
7. **Inventur:** Das Abschluss-PDF bzw. -XLSX der Inventur ist eine Unterlage für den Jahresabschluss, landet aber weiter im Download-Ordner (O-E7). Soll es auch in den Belegordner, etwa nach `Inventur/<JJJJ-MM>/`?
8. **Freigabe:** Chrome und Edge fragen nach jedem Browser-Neustart einmal nach dem Zugriff, außer man wählt „Bei jedem Besuch zulassen“. Das ist eine Schutzregel des Browsers und lässt sich nicht abschalten. Nach „Nicht zulassen“ fragt der Browser so lange nicht mehr, bis alle Tabs von NovaERP geschlossen waren. Den Weg dahin nennt die App im Hinweis.
9. **Mehrere Rechner:** Jeder Rechner wählt seinen Ordner selbst. Für einen gemeinsamen Ordner auf jedem Rechner denselben OneDrive- oder Netzwerkordner wählen.
10. **Kein Archiv:** Der Belegordner ist eine Ablage für deine Downloads, kein revisionssicheres Archiv (GoBD). Die Belege selbst bleiben unverändert in NovaERP.

### O — bewusst nicht enthalten

- **Andere Downloads** (Inventur, Zählliste, Warenfluss, Etiketten, Dienstplan, Import-Vorlagen, Zertifikate und Anhänge, Vorlagen-Vorschau) laufen weiter in den Download-Ordner (O-E7; Inventur: Offener Punkt 7).
- **Kein automatisches Ablegen ohne Klick**, auch nicht beim Mailversand. Eine Datei entsteht nur durch einen Klick auf eine Beleg-Schaltfläche.
- **Mobilgeräte** (Chrome auf Android, Safari auf iOS) haben die API nicht und nutzen den Download.
- **Nummer und Monatsordner am Monatswechsel:** AB-, LS- und PL-Nummern tragen das Serverdatum (`date.today()` in `documents.py`), der Monatsordner das Berliner Ausstellungsdatum. Zwischen 0 und 1 bzw. 2 Uhr am Monatsersten können sie um einen Monat auseinanderliegen. Nicht geändert.
- **Befund am Rand (Altbestand, nicht in O):** `DatevExportForm` belegt „von“ mit `new Date(Jahr, Monat, 1).toISOString()` vor. In Berlin ergibt das den Vortag (z. B. `2026-09-30` statt `2026-10-01`), der Standardzeitraum beginnt also einen Tag zu früh. Deshalb nimmt O für den Monatsordner das Zeitraumende (`to_date`). Eigener kleiner Fix, wenn gewünscht.

### Nicht in diesem Plan (aus Gernots Antworten vom 09.10.; Zuordnung durch den Manager)

- **Monatliche Sammelrechnung je Kunde** und Pfand-Abrechnungsart (z. B. Knuspr): laut `261009_Kunden-Sammelrechnung.xlsx` — Kundeneinstellungen (Daten), kein Code.
- **SEPA:** Basislastschrift (CORE), Gläubiger-ID und vier Kunden mit Mandat laut Gernots Antwort — Einstellungen und Kundenstamm (Daten). **Naturkostinsel:** zwei Filialen mit je eigenem Mandat, Einzug je Filiale getrennt — fachlich neu (Mandat je Filiale bzw. Lieferadresse), nicht geplant.
- **RE-2026-00002 und RE-2026-00004:** weder bezahlt noch verschickt, Lieferdatum 08.10.2026 → Korrektur nach Runbook Teil 3 (Paket 1), eigene Freigabe.
- **46 importierte Bestellungen bis 07.10.:** über DATEV abgerechnet → in NovaERP nicht abrechnen (Spec A6 „Offen“).
- **RE-2026-00005 (Klara Düran):** Verknüpfung mit BE-20261007-0008 freigegeben („Passt für mich“) → Datenkorrektur mit Freigabe.
- **IFCO-Clearing:** nur Ökoring und Bodan (Kundeneinstellung `pfand_abrechnung = KEINE`).
- **B1-Rezepturen:** Gernot: „Müsste jetzt soweit alles definiert sein“ → Stücklisten der 26 Mixe prüfen.
- **E-Rechnungspflicht 2027/2028:** Gernot fragt beim Steuerberater nach.
