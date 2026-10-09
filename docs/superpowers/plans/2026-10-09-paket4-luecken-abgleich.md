# Paket 4 — Lücken aus dem Abgleich mit Gernot — Implementation Plan

> **Hinweis für Worker (Codex, ohne Netzwerk):** Diesen Plan Task für Task in der Reihenfolge der Nummern 1–24 abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Lies vor jedem Task seinen Abschnitt frisch aus der Plandatei (sie kann während des Laufs ergänzt werden). Kein Task wird übersprungen, zusammengefasst oder auf eigenes Urteil verkürzt. **Stoppregeln** stehen unter „Global Constraints“. Eigene Patch- oder Ankerfehler sind **kein** Stoppgrund: auf Funktions-/Klassennamen und die zitierten Blöcke ankern (**nie auf Zeilennummern**); jeder Block „Anker (genau einmal) … ersetzen durch“ bzw. „diesen Block … ersetzen durch“ kommt beim Ersetzen genau einmal vor; nach jedem Patch mit `grep -n` prüfen, dass genau die gemeinte Stelle geändert ist. Die vier Abschnitte tragen Kurzbezeichnungen (A.1 … A.6, B.1 … B.7, C.1 … C.6, P4-D.1 … P4-D.4); sie stehen in Texten, Commit-Betreffen und Code-Kommentaren und meinen die Tasks laut Tabelle „Reihenfolge“ (z. B. „nach B.3“ = nach Task 9). **„D/F/O“, „D.1“–„D.5“, „F.n“, „O.n“ und „Nachtrag-Task n“ in den Abschnitten A–C und in allen Überschneidungs-Tabellen meinen den Nachtrag 09.10. (schon auf `main`); im Abschnitt P4-D meinen „D.1“–„D.4“ dessen eigene Tasks.** Die Abschlussmeldungen in Task 6 (A), Task 13 (B), Task 19 (C) und Task 23 (P4-D) sind Zwischenstände für den Bericht — **nicht anhalten**, der Lauf endet mit Task 24. **Abnahme**, **Manager-Abnahme** und **Offene Punkte** am Ende sind Manager-Arbeit, kein Worker-Task; der Worker verbindet sich nie mit dem Produktionsserver.

**Goal:** Die Wünsche Gernots, die der Abgleich (`/tmp/p4/abgleich.json`: 92 Wünsche, Urteile, Kritik, X01–X07) als offen oder nur teilweise umgesetzt ausweist und die Code brauchen, in einem Arbeitsbaum, einem Branch und einem Deploy:
- **A — Tagesplan und Produktion** (G10, G11, G12, G13, G74). Gernots Mixe erscheinen im Sortenbedarf als Einzelsorten: der Server leitet `is_bundle` beim Speichern aus der Stückliste ab, das Produktformular schickt es nicht mehr; die 24 Bestandsmixe korrigiert Runbook A-R1. „Gepackt“ und „Ausgeliefert“ im Tagesplan bestätigen einen Entwurf im selben Schritt, aber nur bis zu seinem Liefertag. Umschalter „Sorten | Artikel“ im Sortenbedarf.
- **B — Abrechnung** (G66, G31/X07, G64, G21, G05). `FAKTURIERT` sperrt jede Rechnung zur Bestellung (409, Belegdialog ohne Knopf). Jeder Wechsel auf `GELIEFERT` legt den fehlenden Lieferschein an, damit Monats- und Sammellauf jede Lieferung sehen. Rechnungsdatum = Tag des Festschreibens. Menge und Einzelpreis einer Entwurfsposition direkt in der Tabelle ändern (Menge einer Sammelposition nur über die Bestellung). Suche nach Nummer, Kunde oder Kundennummer in jedem Reiter.
- **C — Belegstatus und Dateinamen** (G14, G15, X07, G19; G37, G38). Neue Seite „Belegstatus“ je Bestellung (Lieferschein, Rechnung, versendet, bezahlt; Filter Zeitraum, Kunde, „nur unvollständige“), Endpunkt `GET /api/v1/belegstatus` mit den Rechten der Rechnungen; FAKTURIERT-Altbestand als „extern (DATEV)“. Download, Mailanhang und Versandprotokoll heißen `<Belegnummer>_<Kunde>.pdf`.
- **P4-D — Rechte der Rolle Produktion bei Kunden-Stammdaten** (G41, G60; Umfeld G40, G42–G44). Die Halle löscht keine Adressen und Ansprechpartner, ändert den Aktiv-Schalter nicht, sieht keine Konditionen und keine Sonderpreisliste; Kundenseite je Rolle; Wachhund über alle Geld- und Konditionsrouten.

**Architecture:** Keine Schemaänderung, keine Migration, keine neue Tabelle (`tenancy._auto_migrate` unberührt).
- **Backend:** neue Module `app.services.lieferschein_service` (B), `app.services.belegstatus`, `app.schemas.belegstatus`, `app.api.v1.belegstatus` (C; Router in `main.py` mit `_deps_geld`). Regeln an je einer Stelle: `order_status_service` (A: `bestaetigen`, `im_tagesplan_moeglich`, `setze_status_im_tagesplan`; B: Lieferschein in `setze_status` beim Wechsel auf `GELIEFERT`), `invoice_service` (B: `BestellungFakturiert`, Datum in `festschreiben`), `beleg_dateiname` (C: `kundenteil`, Kunde im Dateinamen), `core.rollen` (P4-D: `KUNDENFELD_AKTIV`, `KUNDENANTWORT_KONDITIONEN`, `sieht_konditionen`). `products.update_product` (A), `production.get_day_plan` (A), `sales.py` (A: Bestätigen; P4-D: Kundenrechte), `invoices.py`/`documents.py` (B, C), `belegversand.py` (C).
- **Frontend:** `Products.tsx`, `Tagesplan.tsx`, `api.ts` (A); `OrderDocumentsModal.tsx`, `Invoices.tsx` (B); Seite `Belegstatus.tsx` mit Route, Navigation, Schnellsuche, Rollentexten (C); `Customers.tsx`, `rollen.ts` (P4-D). Reine Funktionen ohne Importe mit Node-Prüfung: `positionsaenderung.ts`, `rechnungssuche.ts` (B), `belegstatus.ts` (C), Rollenlisten in `rollen.ts` (P4-D).

**Tech Stack:** FastAPI + SQLAlchemy 2.0, SQLite je Mandant, Pydantic v2, React 18 + TypeScript 5.9, TanStack Query 5; Node ≥ 23.6 für `frontend/tests/unit/*.check.ts`.

**Ausgangsstand:** `main` nach dem Merge von D/F/O (Nachtrag 09.10.) — heute `main` @ `521ed6d` („docs: Nachtrag 09.10. live (SKR04, Firmendaten, Belegordner) …“, darin D/F/O samt der Nachbesserungen `fcbb50e`, `60710b1`, `1bfa032`, `857c65a`; live). Die Abschnitte sind einzeln geplant und nachgespielt (A auf `df84f7b` und `bd56901`; B auf `df84f7b`, `bd56901`, `1bfa032` und zusammen mit A; C auf `df84f7b` und `521ed6d`; P4-D auf `df84f7b` und `bd56901`). **Kein Step setzt D/F/O voraus**; alle Anker sind auf `df84f7b` und auf dem gemergten Stand gleich (Prüfstand). Keine Zeilennummern als Anker.

**Quellen:** Abgleich `/tmp/p4/abgleich.json`; Abschnittspläne `/tmp/p4/A.md`, `/tmp/p4/B.md`, `/tmp/p4/C.md`, `/tmp/p4/D.md` (09.10.2026, in diesen Plan übernommen); Nachtrag `/tmp/n0910/plan.md` (im Repo: `docs/superpowers/plans/2026-10-09-nachtrag-skr04-firmendaten-belegordner.md`).

## Reihenfolge

| Task | Kurz | Inhalt | Art | Neue Tests | Commit |
|---|---|---|---|---|---|
| 1 | A.1 | Artikel mit Stückliste bleibt beim Speichern festes Bundle; legt `backend/tests/test_paket4.py` an | Backend | 6 | ja |
| 2 | A.2 | Produktformular schickt `is_bundle` nicht mehr | Frontend | — | ja |
| 3 | A.3 | Entwurf beim Packen/Ausliefern bestätigen (eine Statusregel, nur bis zum Liefertag); `POST /confirm` über dieselbe Funktion | Backend | 9 | ja |
| 4 | A.4 | Tagesplan meldet je Bestellung `gepackt_moeglich`/`ausgeliefert_moeglich` | Backend | 3 | ja |
| 5 | A.5 | Tagesplan: Knöpfe für Entwürfe, Umschalter „Sorten \| Artikel“ | Frontend | — | ja |
| 6 | A.6 | Abschluss A (Zwischenstand) | Prüfung | — | — |
| 7 | B.1 | `FAKTURIERT` sperrt jede Rechnung zur Bestellung | Backend | 6 | ja |
| 8 | B.2 | Rechnungsdatum beim Festschreiben = Ausstellungstag; **passt 2 Bestandstests an** | Backend | 3 | ja |
| 9 | B.3 | Ausliefern legt den fehlenden Lieferschein an (`lieferschein_service`) | Backend | 8 | ja |
| 10 | B.4 | Belegdialog: keine Rechnung für fakturierte Bestellungen | Frontend | — | ja |
| 11 | B.5 | Menge und Einzelpreis einer Entwurfsposition ändern; Mengensperre für Sammelpositionen | Backend + Frontend | 4 (+ Node 20 Fälle) | ja |
| 12 | B.6 | Suche nach Nummer, Kunde, Kundennummer in jedem Reiter | Frontend | — (Node 14 Fälle) | ja |
| 13 | B.7 | Abschluss B (Zwischenstand) | Prüfung | — | — |
| 14 | C.1 | Dateiname-Regel: Nummer und bereinigter Kundenname | Backend | 24 | ja |
| 15 | C.2 | Download, Mailanhang, Versandprotokoll mit Kundennamen; **stellt 11 Bestandserwartungen um** | Backend | 7 | ja |
| 16 | C.3 | Belegstatus: Regeln und `GET /api/v1/belegstatus` | Backend | 15 | ja |
| 17 | C.4 | Anzeige des Belegstatus als reine Funktionen | Frontend | 1 (Node 29 Fälle) | ja |
| 18 | C.5 | Seite „Belegstatus“, Route, Navigation, Schnellsuche, Rollentexte | Frontend | — | ja |
| 19 | C.6 | Abschluss C (Zwischenstand) | Prüfung | — | — |
| 20 | P4-D.1 | Halle löscht keine Kundenstammdaten (Adressen, Ansprechpartner, Aktiv-Schalter) | Backend | 14 | ja |
| 21 | P4-D.2 | Konditionen für die Halle ausgeblendet; Wachhund Geld/DATEV/Konditionen; **passt 2 Bestandstests an** | Backend | 19 | ja |
| 22 | P4-D.3 | Kundenseite je Rolle; Rollenlisten mit Node-Prüfung | Frontend | — (Node `rollen.check`) | ja |
| 23 | P4-D.4 | Abschluss P4-D (Zwischenstand) | Prüfung | — | — |
| 24 | — | Abschluss Paket 4: Gesamtprüfung und Gesamtmeldung | Prüfung | — | — |

**Warum A → B → C → P4-D:**
- **A zuerst:** A.1 legt die gemeinsame Testdatei an. B ist mit A zusammen gemessen (A- und B-Klassen `39 passed`): „Ausgeliefert“ im Tagesplan bestätigt einen Abo-Entwurf (A.3) und B.3 legt dabei den Lieferschein an — erst damit erreicht der Monatslauf die Abo-Lieferungen (G31).
- **B vor C:** Der FAKTURIERT-Test von C.3 legt seine Rechnungen an, bevor er FAKTURIERT setzt, und bleibt so nach B.1 grün (gemessen mit B.1 in einer Kopie). Der Belegstatus zeigt die Lieferscheine, die B.3 beim Ausliefern anlegt.
- **P4-D zuletzt:** Sein Wachhund (`TestP4DHalleOhneGeldUndKonditionen`) prüft dann auch die neue Geldroute `GET /api/v1/belegstatus` aus C.3 (in der Zusammenführung ergänzt). P4-D.3 ändert `rollen.ts` nach C.5 an anderen Zeilen. P4-D.4 prüft seine drei Commits über `HEAD~3` — das stimmt nur, wenn sie die letzten sind.
- Innerhalb jedes Abschnitts gilt seine eigene Reihenfolge. Alle Berührungen zwischen den Abschnitten sind getrennte Stellen in gemeinsamen Dateien (File Structure, „Überschneidungen“).

**Commits:** 19 (A 5, B 6, C 5, P4-D 3); Tasks 6, 13, 19, 23 und 24 committen nichts.

## Prüfstand (Gesamtlauf)

Maßgeblich für den Worker sind allein die Zahlen in den Steps. Die Prüfstände der Abschnitte (einzeln, mit Reviews) stehen in den Abschnitten.

- **Zusammenführung, Anker-Nachspiel** (09.10.2026, Kopie `/tmp/p4-kopie-plan` = `git archive 521ed6d`, Werkzeug `/tmp/p4-merge-tools/replay_anchors.py`, Blöcke aus `/tmp/p4/A.md`–`D.md` zerlegt mit `/tmp/p4-merge-tools/blocks.py` und `files.py`): alle **143 Ersetzungen** (A 25, B 30, C 39, P4-D 49) in der Reihenfolge dieses Plans mechanisch angewendet, **jeder Anker zum Zeitpunkt seines Steps genau einmal**. Keine Zeile wird von zwei Abschnitten ersetzt, kein Abschnitt erzeugt einen Anker eines anderen ein zweites Mal (`/tmp/p4-merge-tools/cross.py`: nur triviale gemeinsame Zeilen wie `raise HTTPException(` in verschiedenen Blöcken, keine entfernt). Die `grep`-Zählungen der Steps auf dem Endstand: A.2 `0`; A.5 `1`/`3`/`2`, `belegHerunterladen` `2`; B.1 `5`/`6`; B.3 `2`/`0`; B.4 `3`; B.5 `4`/`1`; B.6 `0`; C.2 `documents.py:7`, `invoices.py:1`, `belegversand.py:2`; C.5 `1`/`1`/`1`, `rollen.ts` `2`; P4-D.3 `8`/`4`/`4`/`1`/`2`/`2` — alle wie in den Steps.
- **Endstand des Gesamtplans, gemessen** (`/tmp/p4-kopie-plan3` = `git archive 521ed6d`, `frontend/node_modules` als Symlink; **dieser Plantext** mechanisch in Dokumentreihenfolge angewendet mit `/tmp/p4-merge-tools/apply_all.py`: 143 Ersetzungen, 13 neue Dateien und der Testkopf, 13 Testblöcke, kein Fehler): `tests/test_paket4.py` `119 passed` (17 Klassen); `tests/test_gernot_261008_paket3.py` `467 passed`; Paket-3-Abnahme `5 passed, 462 deselected`; `tests/test_nachtrag_0910.py` `174 passed`; Prozedur V `14 failed, 1937 passed, 2 skipped, 1 error`, Abgleich leer; `tsc` ohne Ausgabe, Build `✓ built`; die sechs Node-Prüfungen wie in Task 24 Step 3; `ruff --select F821,F823` über die 20 Python-Dateien Exit 0; der Wachhund aus P4-D.2 zählt 55 Routen×Methoden; im geteilten `node_modules` nichts Neues.
- **Vorbereitung auf `521ed6d`** (`/tmp/p4-kopie-planbasis`): alle `grep`-Zählungen der Ausgangsstände A, B und P4-D wie angegeben; die fünf Hashes von P4-D gleich (`git rev-parse 521ed6d:<Datei>`).
- **Prozedur V auf `521ed6d`** (Basis, gemessen im Prüfstand von C): `14 failed, 1818 passed, 2 skipped, 1 error`, Namen = Baseline.
- **Zusammenführung, inhaltliche Änderungen gegenüber den Abschnittsplänen:** Tasks durchnummeriert; Commit-Betreffe einheitlich `(P4-<Kurz>)` (vorher A „P4 A.n“, B „(B)“, C „(C)“); Hinweise, Stoppregeln, Baseline, Prozedur V und Ausgangsstände in den Kopf gezogen (eine Baseline-Datei `/tmp/p4-baseline-namen.txt`; B und P4-D nutzten `/tmp/n0910-baseline-namen.txt`, C `/tmp/p4c-baseline-namen.txt` — gleicher Inhalt); Vorbedingung V-C1 erfüllt (Global Constraints, „Bestehende Tests“); Verweise auf Tasks des Nachtrags als „Nachtrag-Task n“; im Wachhund von P4-D.2 `"/api/v1/belegstatus"` in `_PRAEFIXE` ergänzt (Rot/Grün unverändert, C.3 sperrt die Halle schon mit 403; Routenzahl 55 statt 54); Abnahme, Runbooks und Offene Punkte der Abschnitte am Ende.
- **Nicht gemessen im Gesamtlauf:** Rot/Grün je Task in der Reihenfolge A → B → C → P4-D und die Zwischenstände der Prozedur V (die N-Werte vor Task 21 sind aus den gemessenen Zuwächsen errechnet; der Endstand 1937 ist gemessen), die Commits (die Kopie hat keine Git-Historie), Oberfläche, Produktion. → Manager-Abnahme, Schritt 0.

## Global Constraints

- **Arbeitsort:** Worktree `/Users/nikolajunser-richter/minga-p4`, Branch `feat/paket4`, vom Manager vor dem Dispatch aus `main` nach dem Merge von D/F/O angelegt (heute `521ed6d`): `git worktree add ../minga-p4 -b feat/paket4 main` und `ln -s /Users/nikolajunser-richter/minga-greens-erp/frontend/node_modules frontend/node_modules`. Jeder Befehl beginnt im Worktree-Wurzelverzeichnis (`<Arbeitsbaum>`).
- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` und `backend/venv311` sind kaputt.
- **Node:** `node --version` → v23.6 oder neuer. `TestP4CBelegstatusAnzeige` und die Paket-3-Abnahmetests rufen `node` aus pytest auf und laufen so auch im Vollauf. Fehlt `node` oder ist es älter: vor Task 1 stoppen, Ausgabe melden. Diese Tests nie überspringen oder ausklammern.
- **Neue Tests** nur in `backend/tests/test_paket4.py`. Task 1 legt die Datei mit dem Kopf aus Task 1 an; alle anderen Tasks hängen ihren Block **ans Dateiende**. Die Kopf-Schritte in Task 7, 14 und 20 („nur wenn die Datei fehlt“) entfallen dann — die Datei besteht, kein Stopp. Präfixe je Abschnitt (ein gleichnamiger Helfer würde still ersetzt): **A** — Klassen `TestP4A…`, Helfer und Fixtures `_p4a_…`; **B** — `TestP4B…`, `_p4b_…`, Konstanten `_P4B_…`; **C** — `TestP4C…`, `_p4c_…`, `_P4C_…`; **P4-D** — `TestP4D…`, `_p4d_…`, `_P4D_…`. Keine `autouse`-Fixture. Fixture `client` aus `tests/conftest.py`. Jeder Block bringt seine Importe selbst mit; doppelte Importe sind harmlos (geprüft: kein Name wird von zwei Abschnitten verschieden gebunden).
- **Bestehende Tests** ändert kein Task, mit genau diesen Ausnahmen: Task 8 (B.2) Step 5 (B-E3: `test_gernot_261008_paket3.py::TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum`, `test_dunning.py::test_dunning_email_sending`), Task 15 (C.2) Step 6 (C-E12: 11 erwartete Dateinamen in `test_gernot_261008_paket3.py`, je mit `# Paket 4, C`), Task 21 (P4-D.2) Step 5 (E-D6: zwei Tests in `test_gernot_261008_paket3.py`, `TestQ4SonderpreiseDatevKatalogpreis` und `TestQ7Feldschutz`). Weitere Änderungen an Bestandstests sind ein Stoppgrund. Die Paket-3-Abnahmetests (`TestAbnahme…`) ändert kein Task.
- **Einzeltests in `test_paket4.py` immer über Klassen-IDs, nie `-k`** (in der gemeinsamen Datei zählt `-k` fremde Klassen als `deselected` mit; `-k` in fremden Testdateien bleibt wie in den Steps). Die Befehle stehen in den Steps; zusätzlich:
  - **„Lauf C“** (Abschnitt C; `<Ziele>` = die Klassen-IDs aus dem Step):
    ```bash
    cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest <Ziele> -q -p no:cacheprovider 2>&1 | tail -1
    ```
  - **Paket-3-Abnahme** (Stoppregel 4): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -q -p no:cacheprovider -k "TestAbnahmeSepaBerlin or TestAbnahmeRechnungsberechtigung" 2>&1 | tail -1` → `5 passed, 462 deselected`.
  - **Alle Paket-4-Tests** (Task 24): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py -q -p no:cacheprovider 2>&1 | tail -1` → nach Task 21 `119 passed` (A 18, B 21, C 47, P4-D 33).
- **Baseline** (Fehlernamen, **nie die Anzahl** vergleichen; 14 failed + 1 error, dieselben 15 Namen wie nach B6 und nach D/F/O). Die Datei `/tmp/p4-baseline-namen.txt` legt die Vorbereitung an — Block unverändert, ohne Einrückung, in die Shell geben:

```bash
test -f /tmp/p4-baseline-namen.txt || cat > /tmp/p4-baseline-namen.txt <<'EOF'
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
sort -o /tmp/p4-baseline-namen.txt /tmp/p4-baseline-namen.txt; wc -l < /tmp/p4-baseline-namen.txt
```

  Erwartet: `15`. Eine andere Zahl heißt, die Datei stammt aus einem anderen Lauf: Stoppregel 1. `test_features.py::TestFeatures::test_subscription_processing` scheitert an `async def` ohne Plugin, nicht am Code dieses Plans; er bleibt rot.
- **Kein Netzwerk:** kein `npm install`, kein `git pull`/`push`, kein `curl`. **Kein Deploy, keine Verbindung zum Produktionsserver.**
- **Commits** nur mit den im Task genannten Dateien, nie `git add -A` oder `git add .`. Nachricht nach dem Muster `git commit -m "<Betreff>" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"`; die Betreffe stehen in den Tasks und enden mit `(P4-<Kurz>)`, z. B. `(P4-A.1)`, `(P4-B.3)`, `(P4-C.2)`, `(P4-D.1)`. Erwartete unversionierte Einträge, die **sauber** sind und nie committet werden: `frontend/node_modules` (Symlink), `backend/data/` (die Testsuite legt `backend/data/tenants/dev.db` samt `-wal`/`-shm` an), falls vorhanden `.claude-flow/` und `.swarm/`, die unversionierte Plandatei, `frontend/dist/`.
- **Frontend-Prüfung:** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut), Build `cd frontend && npm run build` (endet mit `✓ built in …`; die Warnung „Some chunks are larger than 500 kB“ ist Altbestand). `tsconfig.json` hat `noUnusedLocals`. Playwright gehört nicht zur Worker-Prüfung. **Node-Prüfungen** (`cd frontend && node tests/unit/<Name>.check.ts`, TypeScript ohne Build): neu `positionsaenderung` (B.5, `20 Fälle ok`), `rechnungssuche` (B.6, `14 Fälle ok`), `belegstatus` (C.4, `belegstatus.check: 29 Fälle ok`), `rollen` (P4-D.3, `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`); Bestand `dateiname` (`8 Fälle ok`), `belegpfad` (`35 Fälle ok`).
- **Statisch** (`ruff` 0.1.13 unter `/opt/homebrew/bin/ruff` meldet Erfolg stumm; fehlt er dort: „nicht ausführbar“ melden, nicht ersetzen): `--select F821,F823` mit den Dateien aus den Steps; Task 24 über alle geänderten Python-Dateien.
- **UI-Texte auf Deutsch**, Toast-Texte genau wie im Code.
- **Stoppregeln** (gelten für alle Abschnitte; Verweise im Text auf „Stoppregel 1–5“ meinen diese Liste — A und P4-D zählten „Kein Stopp“ als 4, hier ist es 5):
  1. Ein zitierter Anker fehlt, **weil der Code inhaltlich anders aussieht** (Funktion fehlt, andere Logik, anderer Rückgabewert; z. B. `beleg_dateiname` hat schon einen Parameter `kunde`, ein anderer Abschnitt hat `versende_beleg`, `delete_address` oder `kundenfeldschutz` umgebaut): stoppen, Fundstelle bzw. Fehlerausgabe melden. Eine Abweichung in der **Vorbereitung** ist ebenfalls Stoppregel 1.
  2. Rot oder Grün weicht nach korrekt angewendetem Schritt von der Erwartung ab (andere Anzahl, anderer Testname, andere Fehlermeldung; Datumsangaben in Meldungen sind die des Laufs, in spitzen Klammern wie `<heute>`): stoppen, exakte Ausgabe melden. Nicht „passend machen“. pytest kürzt lange Werte in der `assert`-Zeile (`…`); maßgeblich sind die vollständigen Werte bzw. die Diff-Zeilen darunter. Eine solche Kürzung ist kein Stoppgrund.
  3. Prozedur V zeigt einen Fehlernamen, der nicht in der Baseline steht, oder ein Baseline-Name fehlt: stoppen, `comm`-Ausgabe melden.
  4. Ein Paket-3-Abnahmetest (`TestAbnahmeSepaBerlin`, `TestAbnahmeRechnungsberechtigung`) wird rot, oder ein Step, der Bestandstests anpasst (Task 8 Step 5, Task 15 Step 5/6, Task 21 Step 5), zeigt **andere** rote Bestandstests als die genannten: stoppen, Ausgabe melden. Kein Test wird darüber hinaus angepasst.
  5. **Kein Stopp:** eigene Patch-/Ankerfehler (Leerzeichen, Mehrfachtreffer durch zu kurzen Anker, Tippfehler) — selbst beheben, mit `grep -n` belegen, in der Abschlussmeldung vermerken. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht ebenso.

## Prozedur V (Vollauf mit Namensabgleich)

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/p4-voll.txt 2>&1; tail -1 /tmp/p4-voll.txt; grep -E '^(FAILED|ERROR) ' /tmp/p4-voll.txt | sed 's/ - .*//' | sort > /tmp/p4-namen.txt; comm -3 /tmp/p4-baseline-namen.txt /tmp/p4-namen.txt; echo "--- Ende Abgleich"
```

Erwartet: letzte Zeile `14 failed, N passed, 2 skipped, 1 error in …s`, **keine** Zeile zwischen der Summenzeile und `--- Ende Abgleich`. Dauer 1–3 min. Jede Erwähnung von „Prozedur V“, „Prozedur V (Paket 4)“, „Vollauf (Prozedur V)“ in den Abschnitten meint diesen Befehl (die Abschnitte hatten einzeln eigene Ausgabe- und Baseline-Dateien; im Gesamtplan gelten nur `/tmp/p4-voll.txt` und `/tmp/p4-baseline-namen.txt`).

N zur Orientierung — Basis `1818` und Endstand `1937` auf `521ed6d` **gemessen**, die Zwischenstände **errechnet** aus den gemessenen Zuwächsen der Abschnitte (A +18, B +21, C +47, P4-D +33); maßgeblich sind die Namen. Rückt `main` vor dem Dispatch weiter vor, verschiebt sich die Basis, die Zuwächse bleiben:

| nach Task | 0 (Basis) | 1–2 | 3 | 4–6 | 7 | 8 | 9–10 | 11–13 | 14 | 15 | 16 | 17–19 | 20 | 21–24 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N | 1818 | 1824 | 1833 | 1836 | 1842 | 1845 | 1853 | 1857 | 1881 | 1888 | 1903 | 1904 | 1918 | 1937 |

## Review Focus

Was **kein automatischer Test** abdeckt (keine Frontend-Tests im Repo); der Manager prüft es in der Manager-Abnahme. Die Review-Fokus-Absätze der einzelnen Tasks gelten zusätzlich.

**Übergreifend (entsteht erst durch das Zusammenspiel):**
- **Ü1 — Entwurf ausliefern (A.3–A.5 + B.3 + C.2 + O.4).** „Ausgeliefert“ im Tagesplan auf einem Entwurf mit Liefertag heute: Toast „… bestätigt und ausgeliefert“, im Verlauf CONFIRM und Statuswechsel, genau **ein** Lieferschein `ENTWURF` mit Liefertag (B.3), Bestand gebucht. „Packliste“ danach öffnet diesen Lieferschein (O.4 nimmt `notes[0]`), der Download heißt `LS-…_<Kunde>.pdf` (C.2). Ein Entwurf mit vergangenem Liefertag bekommt keinen Knopf und keinen Lieferschein. → RA4, RA9, R-B2 (1), R-C2 Punkt 7.
- **Ü2 — FAKTURIERT überall gleich (B.1/B.4 + C.3).** Belegstatus zeigt FAKTURIERT ohne Rechnung als „extern (DATEV)“; „Belege“ öffnet den Belegdialog, der für fakturierte Bestellungen keine Rechnung anbietet; `POST /invoices/from-order/{id}` antwortet 409 mit dem Text aus B-E1. Sonderfall „FAKTURIERT mit storniertem NovaERP-Beleg“: Lücke ohne Weg für Gernot (C, Offener Punkt 15; heute 0 Fälle). → R-C2 Punkt 3, Review Focus B.4.
- **Ü3 — Dateinamen und Belegordner (C.2 + O).** Der Belegordner speichert den neuen Servernamen `<Nummer>_<Kunde>.pdf` unter `Belege/<Belegart>/<JJJJ-MM>/`; ein früher unter `<Nummer>.pdf` abgelegter Beleg bleibt daneben liegen, ohne Ersetzen-Rückfrage (einmal je Beleg). → R-C2 Punkt 7, Nachricht R-C3.
- **Ü4 — Rollen und Navigation (C.5 + P4-D.3).** `rollen.ts` trägt nach beiden die Texte „Vertrieb“/„Buchhaltung“ mit Belegstatus und „Produktion“ mit „Kunden anlegen und ändern, ohne Konditionen und ohne Löschen“; „Belegstatus“ steht nur bei Admin, Vertrieb, Buchhaltung; die Halle erreicht „Kunden“ über Strg+K ohne Konditionen; der Wachhund prüft `/api/v1/belegstatus` mit. → R-C2 Punkt 8, RF-D1, RF-D5.
- **Ü5 — Monatsentwurf (B.3 + B.5 + C.3).** Nach dem Monatslauf zeigt der Belegstatus `RECHNUNG_ENTWURF`; im Entwurf ist die Menge einer Sammelposition gesperrt (409-Text als Toast, Zeile bleibt in Arbeit), Preis und Löschen gehen. → R-B2 (2), Review Focus B.5.
- **Ü6 — Halle im Tagesplan (A.3–A.5 + P4-D).** Die Rolle Produktion packt und liefert Entwürfe (kein neues Recht, Review Focus A.3) und sieht beim Bestellen den gültigen Preis, aber keine Konditionen und keine Sonderpreisliste. → RA3/RA4 lokal mit Rolle Produktion, RF-D2.

**A — Tagesplan und Produktion:** Review Focus je Task (Tasks 1–5); RA1–RA9 in `abnahme`, RA2m/RA8m/RA9m in `minga` nur ansehen (Manager-Abnahme A).
**B — Abrechnung:** Review Focus je Task (Tasks 7–12), u. a. Escape im Positionsfeld schließt nur die Zeile, nicht den Dialog (nur im Nachbau gemessen), Tausenderpunkte; R-B2.
**C — Belegstatus und Dateinamen:** Review Focus je Task (Tasks 14–18); R-C2 Punkte 1–8.
**P4-D — Rechte:** Review Focus je Task (Tasks 20–22); RF-D1–RF-D5 lokal, R-D2 live.

Getestet (automatisch): A — Bundle-Ableitung beim Speichern (auch altes Formular), Mix-Auflösung im Sortenbedarf inkl. Abo, Bestätigen beim Packen/Ausliefern mit Audit und Transaktion, Liefertag-Regel, Knöpfe je Status; B — 409 auf allen Wegen zur Rechnung einer FAKTURIERT-Bestellung, Rechnungsdatum beim Festschreiben, Lieferschein beim Ausliefern auf allen Wegen nach `GELIEFERT` samt Monats-/Sammellauf, Mengensperre für Sammelpositionen, Eingabe- und Suchregeln (Node); C — Kundenteil des Dateinamens (Umlaute, Länge, Sonderzeichen), Download/Mail/Protokoll je Belegart, kein 409 nach der Umstellung, Belegstatus-Regeln, Filter, Seiten, Rechte, Anzeige (Node); P4-D — Löschrechte, Aktiv-Schalter, Maskierung der Konditionen, Sonderpreisliste, Kreditlimit-Meldung, Wachhund über alle Geld- und Konditionsrouten, Rollenlisten gegen das Backend (Node). Paket-3-Abnahmetests und `tests/test_nachtrag_0910.py` bleiben unverändert grün.

## File Structure

39 Dateien, davon 14 neu. Spalte „Task“ in der Nummerierung dieses Plans.

| Datei | Task | Verantwortung |
|---|---|---|
| `backend/tests/test_paket4.py` | 1, 3, 4, 7, 8, 9, 11, 14–17, 20, 21 | **neu** (Task 1 mit Kopf), Blöcke A, B, C, P4-D angehängt — 119 Tests |
| `backend/app/api/v1/products.py` | 1 | neu `_bundle_art_ableiten` vor `update_product`, Aufruf in `update_product` |
| `frontend/src/pages/Products.tsx` | 2 | `ProductForm`: Zustand `formData` ohne `is_bundle`, Optionsfelder „Bundle-Typ“ |
| `backend/app/services/order_status_service.py` | 3, 9 | A: neu vor `trage_lieferdatum_nach` `MIT_BESTAETIGUNG`, `bestaetigen`, `_im_tagesplan_bestaetigbar`, `im_tagesplan_moeglich`, `setze_status_im_tagesplan`; B: Importzeile aus `order_fulfillment_service`, `GELIEFERT`-Block in `setze_status` (`lieferschein_beim_ausliefern`) |
| `backend/app/schemas/order.py` | 3 | `OrderStatusUpdate.entwurf_bestaetigen` |
| `backend/app/api/v1/sales.py` | 3, 20, 21 | A: Import aus `order_status_service`, `confirm_order`, `update_order_status`; P4-D: Decorators `reactivate_customer`, `delete_address`, `delete_contact`, Import aus `app.core.rollen`, Rechte-Listen, `_kundenantwort`, `list_customers`, `get_customer`, `create_customer`, `update_customer`, Sonderpreisliste, `create_order` (Kreditlimit) |
| `backend/app/api/v1/production.py` | 4 | Import `im_tagesplan_moeglich`, `get_day_plan._order_ref` |
| `frontend/src/pages/Tagesplan.tsx` | 5 | Importzeile aus `../services/api`, `Statusklick`, `bedarfAnsicht`, `ausgeliefertMutation`, `gepacktMutation`, `statusWechsel`, Knöpfe Verpacken/Ausliefern, Karte Sortenbedarf |
| `frontend/src/services/api.ts` | 5 | `DayPlanOrder` (zwei Felder), `salesApi.updateOrderStatus` (fünfter Parameter) |
| `backend/app/services/invoice_service.py` | 7, 8 | B.1: `BestellungFakturiert`, `fakturiert_meldung`, `create_invoice`, `create_invoice_from_order`, `add_line`, `pruefe_festschreibung`; B.2: `festschreiben` |
| `backend/app/api/v1/invoices.py` | 7, 11, 15 | B.1: `add_invoice_line` (`except`); B.5: `update_invoice_line` vor der Feldschleife (Mengensperre); C.2: Import aus `beleg_dateiname`, `send_invoice_email` |
| `backend/tests/test_gernot_261008_paket3.py` | 8, 15, 21 | Bestandstests: B.2 `TestQ1Festschreiben` (1 Test), C.2 11 Dateinamen-Erwartungen, P4-D.2 je ein Test in `TestQ4SonderpreiseDatevKatalogpreis` und `TestQ7Feldschutz` |
| `backend/tests/test_dunning.py` | 8 | `test_dunning_email_sending` (B-E3) |
| `backend/app/services/lieferschein_service.py` | 9 | **neu** — `naechste_belegnummer`, `lieferschein_anlegen`, `lieferschein_beim_ausliefern` |
| `backend/app/api/v1/documents.py` | 9, 15 | B.3: Importe, `_next_document_number` (Alias), `create_delivery_note`; C.2: Import `bestellkunde`, `send_confirmation`, `download_confirmation_pdf`, `send_delivery_note`, `download_delivery_note_pdf`, `download_packing_list_pdf` |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | 10 | `rechnungMoeglich`, Text „Noch keine Rechnung …“ |
| `frontend/src/pages/Invoices.tsx` | 11, 12 | B.5: Import nach `getErrorMessage`, `InvoiceDetail` (Positionstabelle, Rechnungsdatum-Hinweis); B.6: `filteredInvoices`, `tabs`/`displayInvoices`, `<Tabs …/>`, Suchfeld |
| `frontend/src/services/positionsaenderung.ts` | 11 | **neu**, ohne Importe — Eingabe von Menge und Preis |
| `frontend/tests/unit/positionsaenderung.check.ts` | 11 | **neu** — Node-Prüfung, 20 Fälle |
| `frontend/src/services/rechnungssuche.ts` | 12 | **neu**, ohne Importe — `rechnungPasstZurSuche` |
| `frontend/tests/unit/rechnungssuche.check.ts` | 12 | **neu** — Node-Prüfung, 14 Fälle |
| `backend/app/services/beleg_dateiname.py` | 14, 15 | `KUNDE_MAX_ZEICHEN`, `kundenteil`, `beleg_dateiname(…, kunde=)`, `bestellkunde`, `rechnung_kunde`, `rechnung_dateiname` |
| `backend/app/services/belegversand.py` | 15 | Docstring, `versende_beleg(…, kunde=)`, `markiere_ohne_mail(…, kunde=)` |
| `backend/app/schemas/belegstatus.py` | 16 | **neu** — `BelegstatusLieferschein`, `BelegstatusRechnung`, `BelegstatusZeile`, `BelegstatusListe` |
| `backend/app/services/belegstatus.py` | 16 | **neu** — `belegstatus(db, …)`, `rechnung_faellig_ab`, Codes `OHNE_RECHNUNG`/`RECHNUNG_ENTWURF`/`NICHT_VERSENDET` |
| `backend/app/api/v1/belegstatus.py` | 16 | **neu** — `GET /belegstatus` |
| `backend/app/main.py` | 16 | Import, `include_router` hinter `invoices.router` mit `_deps_geld` |
| `frontend/src/services/belegstatus.ts` | 17 | **neu**, ohne Importe — Typen, Datumshilfen, vier Zellen, `LUECKEN_TEXT` |
| `frontend/tests/unit/belegstatus.check.ts` | 17 | **neu** — Node-Prüfung, 29 Fälle |
| `frontend/src/services/belegstatusApi.ts` | 18 | **neu** — `belegstatusApi.liste(filter)` |
| `frontend/src/pages/Belegstatus.tsx` | 18 | **neu** — Seite |
| `frontend/src/App.tsx` | 18 | Import, Route `belegstatus` |
| `frontend/src/components/common/Layout.tsx` | 18 | Icon `ListChecks`, Navigationspunkt hinter „Rechnungen“ |
| `frontend/src/components/common/CommandPalette.tsx` | 18 | Icon `ListChecks`, Eintrag `nav-belegstatus` hinter `nav-invoices` |
| `frontend/src/services/rollen.ts` | 18, 22 | C.5: Rollentexte Vertrieb, Buchhaltung; P4-D.3: Rollentext Produktion, `ROLLEN_OHNE_HALLE`, `KAUFMAENNISCHE_ROLLEN`, `KUNDEN_KONDITIONSFELDER`, `hatEineRolle`, `ohneKonditionen` vor `rollenInfo` |
| `backend/app/core/rollen.py` | 20, 21 | `KUNDENFELD_AKTIV`, `kundenfeldschutz`; `KUNDENANTWORT_KONDITIONEN`, `sieht_konditionen` |
| `backend/app/schemas/customer.py` | 21 | `CustomerResponse`: Konditionsfelder `Optional` |
| `frontend/src/pages/Customers.tsx` | 22 | Kundenseite je Rolle (Konditionen, Sonderpreis-Knopf, Excel-Import, Papierkorb, Aktiv, Payload ohne Konditionen, `onError`) |
| `frontend/tests/unit/rollen.check.ts` | 22 | **neu** — Node-Prüfung gegen `backend/app/core/rollen.py` |

**Überschneidungen innerhalb Paket 4** (Dateien, die mehr als ein Abschnitt ändert; im Anker-Nachspiel A → B → C → P4-D jeder Anker genau einmal, keine Zeile doppelt ersetzt):
1. **`backend/tests/test_paket4.py`** (A, B, C, P4-D): Task 1 legt an, alle anderen hängen an. Modulweite Namen disjunkt (Präfixe), gemeinsam gebunden nur `pytest` und `Decimal` mit gleicher Quelle; gesamt `119 passed`.
2. **`backend/app/services/order_status_service.py`** (A.3, B.3): A fügt vor `def trage_lieferdatum_nach(` ein (die `def`-Zeile bleibt); B ändert die Importzeile aus `order_fulfillment_service` und den `GELIEFERT`-Block in `setze_status`. Fachlich gewollt: `setze_status_im_tagesplan` → `bestaetigen` + `setze_status` → `lieferschein_beim_ausliefern` (gemessen mit A + B: `39 passed`, Probe Abo-Entwurf → genau ein Lieferschein).
3. **`backend/app/api/v1/sales.py`** (A.3, P4-D.1, P4-D.2): A ankert an der Importzeile aus `order_status_service`, in `confirm_order` und `update_order_status`; P4-D an der Importzeile aus `app.core.rollen`, an Decorators und Kundenfunktionen sowie am Kreditlimit-Block in `create_order`. Gemeinsame Zeilen nur trivial (`raise HTTPException(` in verschiedenen Blöcken). Die fünf Hashes der Vorbereitung gelten nur vor Task 1.
4. **`backend/app/api/v1/invoices.py`** (B.1, B.5, C.2): `add_invoice_line`, `update_invoice_line` (vor der Feldschleife) bzw. Import aus `beleg_dateiname` und `send_invoice_email` — getrennte Funktionen.
5. **`backend/app/api/v1/documents.py`** (B.3, C.2): B zieht `create_delivery_note` und die Nummernregel nach `lieferschein_service` (Importe, `_next_document_number` als Alias); C ändert Import `bestellkunde`, Versand und Downloads von AB/LS/PL. Nach beiden `kunde=` in `documents.py` `7` (gemessen im Anker-Nachspiel).
6. **`backend/tests/test_gernot_261008_paket3.py`** (B.2, C.2, P4-D.2): verschiedene Klassen (`TestQ1Festschreiben`; `TestQ3Downloads`, `TestQ3Mailanhang`, `TestQ1AndereWege`, `TestQ2AbVersand`, `TestQ2LsVersand`, `TestQ2Rechnungsversand`; `TestQ4SonderpreiseDatevKatalogpreis`, `TestQ7Feldschutz`). Testzahl bleibt `467`. Die Paket-3-Abnahmetests berührt keiner.
7. **`frontend/src/services/rollen.ts`** (C.5, P4-D.3): C ändert die Texte „Vertrieb“ und „Buchhaltung“, P4-D den Text „Produktion“ und fügt vor `rollenInfo` ein. `grep -c 'Belegstatus'` bleibt nach P4-D `2`.
8. **Fachlich ohne gemeinsame Datei:** B.1 (409 für FAKTURIERT) ↔ C.3 (Test legt Rechnungen vor FAKTURIERT an; Storno-Sonderfall, C Offener Punkt 15); B.4 ↔ C.5 (der Belegstatus öffnet den Belegdialog aus B.4); C.3 ↔ P4-D.2 (Wachhund prüft `/api/v1/belegstatus`); A.5 ↔ B.3 (Packliste nach „Ausgeliefert“ findet den neuen Lieferschein).

**Überschneidungen mit D/F/O** (Nachtrag 09.10., schon auf `main`; Einzelheiten in den Abschnitten). **Kein Step setzt D/F/O voraus**; alle Anker sind auf `df84f7b` und `521ed6d` gleich:

| Datei | Paket 4 (Task: Stelle) | D/F/O (Nachtrag-Task: Stelle) | Ergebnis |
|---|---|---|---|
| `frontend/src/pages/Tagesplan.tsx` | A.5: zehn Stellen (Importzeile aus `../services/api`, Kommentar vor `Tagesplan`, State, Mutationen, Knöpfe, Sortenbedarf) | O.4 (14): Importzeile aus `orderQueries` + `belegordner`, `packlisteMutation` | getrennt; A-Anker vor und nach O.4 je einmal |
| `frontend/src/services/api.ts` | A.5: `DayPlanOrder`, `salesApi.updateOrderStatus` | D.5 (5): `DatevEinstellungen`, `invoicesApi.datevEinstellungen`; O.4 (14): `documentsApi` | getrennt |
| `backend/app/services/invoice_service.py` | B.1, B.2 (s. File Structure; `add_line` bis `# Position ermitteln`) | D.2 (2): Import `kontenrahmen`, `add_line` ab `# Buchungskonto basierend auf Steuersatz`; Fix `1bfa032` | getrennt |
| `backend/app/api/v1/invoices.py` | B.1 `add_invoice_line`; B.5 `update_invoice_line` bis `satz_vorher = line.tax_rate`; C.2 Import aus `beleg_dateiname`, `send_invoice_email` | D.2–D.4 (2–4): Importe, `update_invoice_line` nach der Feldschleife, `export_datev`, `download_datev_export`, `GET /invoices/datev-export/einstellungen`; Fix `1bfa032`: `buchungskonto`-Block hinter `satz_vorher` | getrennt; B.5's Anker endet vor dem Fix-Block |
| `frontend/src/pages/Invoices.tsx` | B.5: nach Importzeile `getErrorMessage`, `InvoiceDetail`; B.6: Suche, Reiter | D.5 (5) und Fix `857c65a`: `DatevExportForm`; O.5 (15): Importe `dateinameAusHeader`/`ladePdfHerunter`, PDF-Knopf, Mahnung, `handleExport` | getrennt; B fügt **nach** `getErrorMessage` ein, die O stehen lässt |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | B.4: `rechnungMoeglich`, Text; C.5 importiert nur | O.4 (14): Import, `belegPdf`, `downloadInvoicePdf`, Knöpfe | getrennt |
| `backend/app/services/belegversand.py` | C.2: Docstring, `versende_beleg`, `markiere_ohne_mail` | F.3 (8): `absendername`, `gruss` | getrennt; F-Tests prüfen Text und Betreff, nicht `attachment_filename` |
| `backend/app/api/v1/documents.py` | B.3, C.2 | O „bewusst nicht enthalten“: Nummern mit `date.today()` in `documents.py` | B verschiebt die Regel unverändert nach `lieferschein_service.naechste_belegnummer`; O's Aussage bleibt inhaltlich richtig |
| `backend/tests/test_gernot_261008_paket3.py` | B.2, C.2, P4-D.2 (Bestandstests, s. o.) | O: Stoppregel 4 (Abnahmetests, unverändert) | Abnahmetests nach jedem Abschnitt `5 passed` |
| Dateinamen (fachlich) | C.2: `<Nummer>_<Kunde>.pdf` | O (11–15): Belegordner speichert `dateinameAusHeader(…)` unter `<Belegart>/<JJJJ-MM>/` | O unverändert funktionsfähig; alte Dateien bleiben einmalig daneben (Ü3); O-Texte nennen künftig `<Belegnummer>_<Kunde>.pdf` (C, Offener Punkt 10) |
| Rechte (fachlich) | P4-D.2: Wachhund über `/api/v1/invoices` u. a. | D.4 (4): `GET /invoices/datev-export/einstellungen` | automatisch mitgeprüft (Halle 403) |

**Nicht geändert (geprüft):** `tenancy.py` (keine Migration), Modelle, `datev_service.py`, `kontenrahmen.py`, `settings_service.py`, `admin.py`, `pdf_service.py` (nur gelesen: `rechnungsempfaenger`, `line_desc_cell`), `email_service.py`, `schemas/invoice.py`, `types/index.ts`, `Orders.tsx`, `Settings.tsx`, `SepaEinzugsliste.tsx`, `dateiname.ts`, `belegordner.ts`, `belegpfad.ts`, `backend/tests/test_nachtrag_0910.py` (bleibt `174 passed`), die Paket-3-Abnahmetests.

## Vorbereitung (vor Task 1)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis>` in den Bericht schreiben (erwartet `521ed6d…` oder der neuere `main`-Stand, den der Manager beim Dispatch nennt; eine Shell-Variable reicht nicht, jeder Befehl läuft in einer eigenen Shell). `<Basis-A>` = `<Basis>`.
- [ ] **Arbeitsbaum:** `git status --porcelain` → nur die in „Global Constraints“ als sauber genannten `??`-Einträge. Jede `M`-, `A`- oder `D`-Zeile: stoppen und melden, nichts committen oder zurücksetzen.
- [ ] **Node:** `node --version` → v23.6 oder neuer.
- [ ] **Ausgangsstand A** (Kommentar = erwartete Ausgabe; Abweichung = Stoppregel 1):

```bash
grep -c '^def update_product(' backend/app/api/v1/products.py                                                     # 1
grep -c '^    update_data = pfand_vorgaben(update_data, set(update_data), bisher=product)$' backend/app/api/v1/products.py   # 1
grep -c '^def trage_lieferdatum_nach(' backend/app/services/order_status_service.py                               # 1
grep -c '^    BestandsbuchungFehler, StatuswechselFehler, bezeichnung, pruefe_uebergang, setze_status,$' backend/app/api/v1/sales.py   # 1
grep -c '^    old_status = order.status.value$' backend/app/api/v1/sales.py                                         # 1
grep -c '^    actual_delivery_date: Optional\[date\] = Field($' backend/app/schemas/order.py                         # 1
grep -c '^from app.services.label_service import LabelService$' backend/app/api/v1/production.py                    # 1
grep -c '^            "packbar": o.status == OrderStatus.BESTAETIGT,$' backend/app/api/v1/production.py              # 1
grep -c 'is_bundle:' frontend/src/pages/Products.tsx                                                                # 3
grep -c "^import { productionApi, staffApi, documentsApi, salesApi } from '../services/api';$" frontend/src/pages/Tagesplan.tsx   # 1
grep -c 'erst bestätigen' frontend/src/pages/Tagesplan.tsx                                                          # 1
grep -c '^  updateOrderStatus: (id: string, status: OrderStatus, reason?: string, actualDeliveryDate?: string) =>$' frontend/src/services/api.ts   # 1
cat backend/app/api/v1/*.py backend/app/services/order_status_service.py backend/app/schemas/order.py frontend/src/pages/Tagesplan.tsx frontend/src/services/api.ts | grep -c '_bundle_art_ableiten\|im_tagesplan_moeglich\|setze_status_im_tagesplan\|entwurf_bestaetigen\|gepackt_moeglich\|bedarfAnsicht\|entwurfBestaetigen'   # 0
if [ -f backend/tests/test_paket4.py ]; then grep -c '^class TestP4A' backend/tests/test_paket4.py; else echo fehlt; fi   # fehlt
```

- [ ] **Ausgangsstand B:**

```bash
grep -cF 'class BereitsAbgerechnet(ValueError):' backend/app/services/invoice_service.py                               # 1
grep -cF '        if order_id is not None and invoice_type == InvoiceType.RECHNUNG:' backend/app/services/invoice_service.py   # 1
grep -cF '            raise BestellungStorniert("Bestellung ist storniert")' backend/app/services/invoice_service.py       # 1
grep -cF '        # Position ermitteln' backend/app/services/invoice_service.py                                          # 1
grep -cF '                select(Order).where(Order.id == order_id).with_for_update()' backend/app/services/invoice_service.py  # 1
grep -cF '            invoice.invoice_date = _heute_berlin()' backend/app/services/invoice_service.py                     # 1
grep -cF 'def add_invoice_line(' backend/app/api/v1/invoices.py                                                          # 1
grep -cF '    satz_vorher = line.tax_rate' backend/app/api/v1/invoices.py                                              # 1
grep -c 'InvoiceLineSource' backend/app/api/v1/invoices.py                                                         # 2
grep -cF 'def _next_document_number(db, model, number_col, prefix: str, today: date) -> str:' backend/app/api/v1/documents.py  # 1
grep -cF '            deduct_inventory_for_order(db, order, commit=False)' backend/app/services/order_status_service.py   # 1
grep -cF '    def test_altentwurf_behaelt_re_nummer_und_datum(self, client):' backend/tests/test_gernot_261008_paket3.py  # 1
grep -cF '    # Manually set to OVERDUE conform to logic' backend/tests/test_dunning.py                                   # 1
grep -cF "  const rechnungMoeglich = order.status !== 'STORNIERT' && invoicesQuery.isSuccess" frontend/src/components/domain/OrderDocumentsModal.tsx  # 1
grep -cF "import { getErrorMessage } from '../services/errors';" frontend/src/pages/Invoices.tsx                         # 1
grep -cF '  const filteredInvoices = invoices.filter(' frontend/src/pages/Invoices.tsx                                   # 1
grep -rn 'invoicesApi.updateLine\|lieferschein_service\|BestellungFakturiert\|rechnungPasstZurSuche' backend/app frontend/src | wc -l   # 0
ls backend/app/services/lieferschein_service.py frontend/src/services/positionsaenderung.ts frontend/src/services/rechnungssuche.ts 2>&1 | grep -c 'No such file'   # 3
```

- [ ] **Ausgangsstand C** (die Anker von C prüft jeder Step selbst; hier nur, dass C noch nicht da ist):

```bash
grep -c 'def kundenteil\|KUNDE_MAX_ZEICHEN' backend/app/services/beleg_dateiname.py              # 0
ls backend/app/services/belegstatus.py backend/app/api/v1/belegstatus.py backend/app/schemas/belegstatus.py frontend/src/pages/Belegstatus.tsx 2>&1 | grep -c 'No such file'   # 4
grep -c 'belegstatus' backend/app/main.py frontend/src/App.tsx                                  # backend/app/main.py:0 und frontend/src/App.tsx:0
```

- [ ] **Ausgangsstand P4-D:**

```bash
grep -c '^@router.delete("/customers/{customer_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)$' backend/app/api/v1/sales.py   # 1
grep -c '^@router.delete("/customers/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)$' backend/app/api/v1/sales.py   # 1
grep -c '^@router.post("/customers/{customer_id}/reactivate", response_model=CustomerResponse)$' backend/app/api/v1/sales.py   # 1
grep -c '^@router.get("/customers/{customer_id}/prices", response_model=list\[CustomerPriceResponse\])$' backend/app/api/v1/sales.py   # 1
grep -c '^from app.core.rollen import KAUFMAENNISCHE_ROLLEN, ROLLEN_OHNE_HALLE, kundenfeldschutz, standardwerte$' backend/app/api/v1/sales.py   # 1
grep -c 'CustomerResponse.model_validate(' backend/app/api/v1/sales.py   # 5
grep -c '^        if open_order_total + estimated_total > customer.credit_limit:$' backend/app/api/v1/sales.py   # 1
grep -c '^ROLLEN_OHNE_HALLE = \[ADMIN, SALES, BUCHHALTUNG, PLANER\]$' backend/app/core/rollen.py   # 1
grep -c '^KAUFMAENNISCHE_ROLLEN = \[ADMIN, SALES, BUCHHALTUNG\]$' backend/app/core/rollen.py   # 1
grep -c '^def kundenfeldschutz(' backend/app/core/rollen.py   # 1
grep -c '^    payment_terms: PaymentTerms$' backend/app/schemas/customer.py   # 1
grep -c "id: 'nav-customers'\|id: 'action-new-customer'" frontend/src/components/common/CommandPalette.tsx   # 2
grep -c 'icon={<Trash className="w-4 h-4" />}' frontend/src/pages/Customers.tsx   # 2
grep -c '<ExcelImport entity="customers"' frontend/src/pages/Customers.tsx   # 1
grep -c 'title="Sonderpreise verwalten"' frontend/src/pages/Customers.tsx   # 1
grep -c '^export function rollenInfo(' frontend/src/services/rollen.ts   # 1
grep -rn "KUNDENANTWORT_KONDITIONEN\|KUNDENFELD_AKTIV\|sieht_konditionen\|hatEineRolle\|ohneKonditionen\|KUNDEN_KONDITIONSFELDER" backend/app frontend/src | wc -l   # 0
grep -c 'assert liste.status_code == 200, liste.text' backend/tests/test_gernot_261008_paket3.py   # 2
git rev-parse HEAD:backend/app/api/v1/sales.py HEAD:backend/app/core/rollen.py HEAD:backend/app/schemas/customer.py HEAD:frontend/src/pages/Customers.tsx HEAD:frontend/src/services/rollen.ts
# 7a754cd62a37c4383525b47a59c76bba0ac0c292
# b9cbf95f847c3722b4bba487cc6e7913cdb11e71
# 1a3065213e943fb9773afa79f30b0112849aad16
# 8e0f1272e6bcda3db2f89a043313eead4a000324
# 572b30bc3076c07eb2f7cdf396c9cc5b4fca8e29
```

  Die fünf Hashes gelten nur hier (Task 3 ändert `sales.py`, Task 18 `rollen.ts` — danach weichen sie ab, erwartet). Weicht hier nur ein Hash ab, weil `main` seit `521ed6d` vorgerückt ist: kein Stopp, dann die Anker von P4-D beim jeweiligen Step einzeln prüfen (Stoppregel 1, wenn einer inhaltlich fehlt).

- [ ] **Baseline:** Block aus „Global Constraints“ (Baseline) ausführen → `15`. Dann Prozedur V auf der Basis → `14 failed, 1818 passed, 2 skipped, 1 error` (auf `521ed6d`), Abgleich leer. Die Summenzeile gehört als `<B>` in den Bericht. Abweichung bei den Namen: stoppen und melden.

---

## Abschnitt A — Tagesplan und Produktion: Mix-Auflösung wirkt, „Gepackt“ auch für Entwürfe — Tasks 1–6 (A.1–A.6)

> **Rahmen:** Arbeitsort, Tests, Commits, Stoppregeln, Baseline und Prozedur V stehen im Kopf des Plans (Global Constraints). A.1–A.6 = Tasks 1–6. Task 1 legt `backend/tests/test_paket4.py` an. Die Abschlussmeldung in Task 6 ist ein Zwischenstand — nicht anhalten. Manager-Abnahme A, die Runbooks A-R1/A-R2 und die Offenen Punkte von A stehen am Ende des Plans.

**Goal:** Gernots Mixe erscheinen im Sortenbedarf als Einzelsorten, und eine Bestellung, die er im Formular als Entwurf erfasst hat, lässt sich im Tagesplan mit einem Klick als gepackt bzw. ausgeliefert markieren. Danach verschwindet sie sofort aus dem Sortenbedarf.
- **G11/G74:** Speichern im Produktformular setzt das Bundle-Kennzeichen nicht mehr zurück. Der Server leitet es beim Speichern aus der Stückliste ab. Die 24 Bestandsmixe korrigiert ein Manager-Runbook (A-R1).
- **G13:** Eine Abo-Lieferung mit einem Mix wird im Sortenbedarf aufgelöst (der Test hält das fest). Für den Gastrotray braucht es Gernots Antwort.
- **G12:** Umschalter „Sorten | Artikel“ in der Karte Sortenbedarf.
- **G10:** „Gepackt“ und „Ausgeliefert“ im Tagesplan bestätigen einen Entwurf im selben Schritt. Das läuft über die eine Statusregel in `order_status_service`, mit eigenem Audit-Eintrag, und nur bis zum Liefertag des Entwurfs: Entwürfe mit vergangenem Liefertag (Prod: 7) bekommen keinen Knopf, der Server lehnt sie ab.

**Architecture:** Keine Schemaänderung, keine Migration, `tenancy._auto_migrate` bleibt unberührt.
- `products.update_product` ruft den neuen Helfer `_bundle_art_ableiten`.
- `order_status_service` bekommt `MIT_BESTAETIGUNG`, `bestaetigen`, `_im_tagesplan_bestaetigbar` (Liefertag nicht vor heute), `im_tagesplan_moeglich(order, ziel)` und `setze_status_im_tagesplan`. `sales.confirm_order` nutzt `bestaetigen`, `sales.update_order_status` nutzt das neue Kennzeichen `OrderStatusUpdate.entwurf_bestaetigen`.
- `production.get_day_plan` liefert je Bestellung `gepackt_moeglich` und `ausgeliefert_moeglich`.
- Frontend: `Products.tsx` schickt `is_bundle` nicht mehr mit. `Tagesplan.tsx` und `api.ts` bekommen die Knöpfe für Entwürfe und den Umschalter.

### Ist-Stand (am Code auf `df84f7b`, in Produktion nur lesend geprüft am 09.10.2026)

1. **Mix-Auflösung (G11, G74).** `production.get_packaging_plan` löst Bundles nur über `product.is_bundle` auf: Vorladen `bundle_ids …if line.product_id and line.product and line.product.is_bundle` und Zweig `elif product and product.is_bundle and components_by_parent.get(product.id)`. Variable Bundles laufen über `is_variable_bundle` und `variable_bundle_selections`.
   - **Prod:** 25 Artikel haben eine Stückliste, alle in der Kategorie BUNDLE. 24 davon tragen `is_bundle=0`, nur MG-11037 trägt 1. Variable Bundles gibt es nicht. Die 24 SKUs stehen in A-R1.
   - **Ursache:** Das Zusammenspiel von Formular und Server. `products.add_bundle_component` setzt `parent.is_bundle = True`. `ProductForm` in `Products.tsx` übernimmt beim Öffnen `is_bundle: product?.is_bundle ?? false`. Das Optionsfeld „Fest (Mischkiste)“ erscheint über `checked={!formData.is_variable_bundle}` als gewählt, setzt `is_bundle` aber nur bei einem Klick. „Speichern“ (`handleSubmit` → `productsApi.update`) schickt dann `is_bundle: false`, und `update_product` übernimmt jedes gesendete Feld per `setattr`.
   - **Beleg:** Bei 21 der 22 am 09.10. gespeicherten Mixe liegt `updated_at` 1–10 s nach der letzten Komponente, z. B. MG-11001 mit Komponente um 11:36:02 und Produkt um 11:36:12.
   - **Weitere Leser des Kennzeichens:**
     - `order_fulfillment_service.deduct_inventory_for_order` bucht bei einem festen Bundle die Komponenten aus.
     - `pdf_service.line_desc_cell` und `product_sorte` drucken auf Belegen eine graue Inhaltszeile und lassen die „Sorte:“-Zeile weg.
     - Im Frontend markiert 📦 Bundles in den Auswahllisten, und `CreateOrderModal.pickableSorten` schließt sie aus.
   - **Ohne Stückliste:** die 39 Artikel „BIO Kiste | X (VPE 6/12)“ (Kategorie MICROGREEN; zu jedem gibt es namensgleich eine „BIO Snackbox | X“), die Gastrokisten Erbse, Radieschen und Rettich (MG-14002–14004), der Gastrotray MG-14001 sowie MG-10005 „BIO Snackbox | Brotzeitmix“ und MG-10020 „BIO Snackbox | Salatmix“ (MICROGREEN; Saatgut „Brotzeitmix“/„Salatmix“ ist je als eine Sorte angelegt).
2. **Abo-Lieferungen (G13).** Seit Paket 2 und B6 trägt die Abo-Bestellung das Abo-Produkt (`subscription_tasks.abo_position`) und kommt als ENTWURF mit Packtag = Liefertag. Die Auflösung hängt am selben Kennzeichen wie bei normalen Bestellungen.
   - **Prod:** 3 aktive Abos, alle auf MG-14001: Staatsministerium (5 Stück, Montag), Dorint (4, Donnerstag), LfA (4, Montag).
   - MG-14001 hat keine Stückliste und ist nicht variabel. Im Sortenbedarf bleibt es deshalb „BIO Gastrotray (1-8 Sorten)“.
   - Die 4 LfA-Entwürfe „Abo-Lieferung: Unknown“ (BE-20260914-0001, BE-20260921-0001, BE-20260928-0001, BE-20261005-0001) sind unverändert. Schritt 7 aus Runbook B von Paket 2 steht noch aus.
3. **Gepackt bei Entwürfen (G10).**
   - `get_day_plan._order_ref` setzt `"packbar": o.status == OrderStatus.BESTAETIGT`. `Tagesplan.tsx` zeigt sonst „erst bestätigen“, und „Ausgeliefert“ erscheint nur bei BESTAETIGT bzw. IN_PRODUKTION.
   - Der Sortenbedarf zählt ENTWURF und BESTAETIGT (`_NOCH_ZU_PACKEN`).
   - **Prod 09.10.:** 4 von 6 Lieferungen waren ENTWURF: BE-20261008-0003, -0007, -0008 und -0009, alle am 08.10. im Formular erfasst (Packtag 08.10., Liefertag 09.10.).
   - **Entwürfe an vergangenen Tagen (Prod 09.10., `mode=ro`): 7** mit Liefertag vor heute: BE-20260914-0001, BE-20260921-0001, BE-20260928-0001, BE-20261005-0001 (LfA, Abo, „Abo-Lieferung: Unknown“), BE-20260917-0002 (Klara Düran, 2 Pos.), BE-20260917-0003 (Bierbichler, die falsch erfasste Bestellung aus G80, soll storniert werden), BE-20261007-0001 (Gemüsebau Kiening, Lieferung 07.10., fällt unter G66). `get_day_plan` listet Entwürfe an **jedem** Tag unter Ausliefern (Abfrage mit ENTWURF, `ausliefern` = Liefertag gleich Tag). `ERLAUBTE_UEBERGAENGE` erlaubt aus GELIEFERT nur FAKTURIERT, ein Storno ist danach nicht mehr möglich; der Übergang bucht Bestand und Leergut (`deduct_inventory_for_order` → `buche_ausgaben`).
   - **Statusregel:** `order_status_service.ERLAUBTE_UEBERGAENGE` (ENTWURF → BESTAETIGT | STORNIERT) zusammen mit `setze_status`. **Daneben** bestätigt `sales.confirm_order` mit eigenem Code: eigene Prüfungen, eigener Audit-Eintrag, `UUID(user["id"])`.
   - **Test aus Paket 2:** `test_gernot_261008_paket2.py::TestTagesplanGepackt::test_packbar_nur_wenn_bestaetigt` legt `packbar is False` für Entwürfe fest.
4. **Bundle-Sicht (G12).** Die Artikelsicht gibt es als Tab „Verpackungsplan“ (`Production.tsx`, `packaging-plan.items`). Im Tagesplan gibt es keinen Umschalter.

### Entscheidungen (Manager, im Plan getroffen; Gernot kann bei den markierten widersprechen)

- **A-E1: Der Server leitet die Bundle-Art beim Speichern ab, das Formular schickt `is_bundle` nicht mehr.** Regel in `products._bundle_art_ableiten`: *Variabel ⇒ kein festes Bundle. Sonst: Stückliste vorhanden ⇒ festes Bundle. Sonst bleibt das Kennzeichen, wie es ist.*
  - **Warum nicht nur das Formular reparieren:** Offene alte Browser-Tabs, das Hallen-Tablet mit altem Bundle und andere Clients würden das Kennzeichen weiter zurücksetzen.
  - **Warum nicht „immer auflösen, wenn eine Stückliste existiert“ nur im Packplan:** Dann wären sich Packplan, Bestandsabzug (`order_fulfillment_service`) und Belege (`pdf_service.line_desc_cell`) uneinig. Das Kennzeichen bleibt die eine Wahrheit für alle drei Leser.
  - **Ohne Stückliste bleibt das Kennzeichen unverändert:** Sonst würde aus einem sortenreinen Artikel der Kategorie BUNDLE (z. B. Gastrokiste Erbse) beim Speichern ein „Bundle“ ohne Inhalt. Der Beleg verlöre dann die „Sorte:“-Zeile, und der Bestandsabzug meldete „Bundle … hat keine Komponenten“.
  - **Variabel setzt `is_bundle` auf false:** Das neue Formular schickt `is_bundle` nicht mehr. Ohne diese Regel bliebe nach dem Umschalten auf „Variabel“ eine alte Stückliste als festes Bundle wirksam.
- **A-E2: Den Bestand korrigiert ein Manager-Runbook, keine Startmigration.** Datenkorrekturen in Produktion sind Manager-Sache, mit Trockenlauf, Freigabe, Backup und Protokoll (A-R1).
  - Alternative ohne Runbook: Gernot öffnet jeden der 24 Mixe einmal und speichert (A.1 heilt beim Speichern). Das sind 24 Klicks und Fehler sind möglich.
  - Reihenfolge: **Deploy zuerst, dann A-R1.** Vor dem Deploy würde das nächste Speichern im alten Formular das Kennzeichen wieder zurücksetzen.
- **A-E3 (G10): „Gepackt“ und „Ausgeliefert“ bestätigen einen Entwurf im selben Schritt, aber nur bis zu seinem Liefertag. Es gibt keinen eigenen Knopf „Bestätigen“ im Tagesplan.**
  - **Warum:**
    - Gernots Ablauf ist Formular → Entwurf, am 09.10. waren 4 von 6 Lieferungen Entwürfe.
    - In der Halle soll es ein Klick sein. Packen heißt bei ihm „angenommen“.
    - Ein zusätzlicher Knopf wäre der Zusatzschritt, den die Kritik bemängelt.
  - **Eine Regel für alle Bestätigungen der Oberfläche:**
    - Neue Funktion `order_status_service.bestaetigen`: ENTWURF → BESTAETIGT mit den Prüfungen aus `confirm_order`, bestätigtem Lieferdatum und Audit-Eintrag CONFIRM.
    - `POST /confirm` ruft sie ebenfalls auf. Damit entfällt die bisherige zweite Bestätigungslogik in `sales.confirm_order`.
    - Danach läuft der Wechsel wie immer über `setze_status`. `ERLAUBTE_UEBERGAENGE` bleibt unverändert.
    - Der Ablauf ist atomar: eine Transaktion mit zwei Audit-Einträgen. Scheitert der zweite Schritt, z. B. weil das Lieferdatum in der Zukunft liegt, bleibt der Entwurf ein Entwurf.
    - **Nicht erfasst (keine Regression, Offener Punkt 9):** `POST /sales/orders/{id}/status` mit `status=BESTAETIGT` und `POST /sales/orders/bulk-status` bestätigen einen Entwurf weiter über das bloße `setze_status`: Aktion STATUS_CHANGE bzw. BULK_STATUS_CHANGE, ohne Prüfung „ohne Positionen“, ohne `confirmed_delivery_date`. Die Oberfläche nutzt diese Wege für Entwürfe nicht: Bestellliste und Sammel-„Bestätigen“ rufen `/confirm` (`Orders.tsx`, `salesApi.confirmOrder`), die Sammelaktion bietet nur „Gepackt“ und „Geliefert“. Sie auf `bestaetigen` umzustellen, ändert Antworten und Audit bestehender API-Wege und gehört nicht zu G10.
  - **Nur bis zum Liefertag (`_im_tagesplan_bestaetigbar`):**
    - Ein Entwurf, dessen Liefertag vor heute (Europe/Berlin) liegt, wird im Tagesplan weder gepackt noch ausgeliefert. Der Server lehnt mit 400 ab („Entwurf mit Liefertag TT.MM.JJJJ liegt in der Vergangenheit — erst in der Bestellliste bestätigen oder stornieren“), `gepackt_moeglich` und `ausgeliefert_moeglich` sind false. Verpacken zeigt dann wie bisher „erst bestätigen“.
    - **Warum:** In Prod stehen 7 solche Entwürfe (Ist-Stand 3), darunter die falsch erfasste Bierbichler-Bestellung. Ein Klick auf „Ausgeliefert“ im Tagesplan ihres Tages würde sie bestätigen und unumkehrbar liefern (Bestand, Leergut, kein Storno mehr).
    - **Auch für „Gepackt“:** Sonst führten zwei Klicks (Gepackt am Packtag, Ausgeliefert am Liefertag; aus Gepackt ist Geliefert erlaubt) zum selben Ergebnis.
    - **Folge:** „Ausgeliefert“ gibt es für einen Entwurf nur am Liefertag heute, weil der Knopf ohnehin nur bis heute erscheint. „Gepackt“ geht bis zum Liefertag, also auch am Morgen des Liefertags im Tagesplan des Packtags (Gernots Ablauf: Formular am Abend des Packtags). Bestätigte Bestellungen bleiben wie in Paket 2 an vergangenen Tagen nachtragbar.
    - Die Regel steht nur im Server. Der Tagesplan liest die Felder und braucht keine eigene Datumsprüfung.
  - **Opt-in:** Nur der Tagesplan schickt `entwurf_bestaetigen: true`. Bestellliste, Sammelaktion und Fremd-Clients behalten die Regel aus Paket 2 (ENTWURF → Gepackt gibt 400).
  - **Server bestimmt die Knöpfe:** `gepackt_moeglich` und `ausgeliefert_moeglich` aus `im_tagesplan_moeglich`, damit es keinen Client-Spiegel der Regel gibt. `packbar` bleibt für alte Tabs und den Paket-2-Test.
  - Gernot kann widersprechen (Offene Punkte, Frage 1). Dann schickt der Tagesplan das Kennzeichen nicht, und der Knopf verschwindet für Entwürfe wieder (`im_tagesplan_moeglich` ohne `MIT_BESTAETIGUNG`).
- **A-E4 (G12): Umschalter „Sorten | Artikel“ in der Karte „Sortenbedarf zum Packen“.** Die Daten liefert `packaging-plan.items` bereits. Der Tab „Verpackungsplan“ in der Produktion bleibt. Voreinstellung ist „Sorten“ (Gernot: „Einzelsorten-Grid (primär)“).
- **A-E5 (G13): Kein eigener Code.** Mit A.1 wird ein Mix im Abo aufgelöst, das hält ein Test fest. Ob der Gastrotray (MG-14001) aufgelöst werden kann, hängt von Gernots Antwort ab (Frage 3). Die LfA-Entwürfe hängen an Runbook B Schritt 7 aus Paket 2 und an R-B3 aus Abschnitt B (A-R2) und werden hier nicht neu geplant.
- **A-E6: Keine Einheit im Sortenbedarf.**
  - Die Einheiten in den Bestellungen sind uneinheitlich (`STK`, `Stück`, `Kisten` für dasselbe Produkt).
  - Eine Einheit je Kachel würde dieselbe Sorte auf mehrere Kacheln verteilen.
  - Nach A-R1 und Frage 2 bestehen fast alle Kacheln aus Snackboxen in Stück.
  - Die Artikelsicht (A-E4) zeigt die Bestelleinheit nur, wenn alle Positionen des Artikels dieselbe tragen. Sonst steht unter der Zahl „Einheiten gemischt: Kisten, STK“. Gezählt werden Bestellungen, nicht Positionen (anders als der Tab „Verpackungsplan“ in `Production.tsx`, der bleibt unverändert).

### Was A je ID liefert

| ID | Status laut Kritik | Nach A (Code + A-R1) | Bleibt offen |
|---|---|---|---|
| G11 | OFFEN (in Prod wirkungslos) | Die 24 Mixe lösen sich im Sortenbedarf in Snackbox-Sorten auf | 39 Kisten „BIO Kiste \| X (VPE n)“, Snackbox Brotzeitmix/Salatmix und die Gastrokisten 14002–14004 ohne Stückliste (Fragen 2, 3) |
| G74 | OFFEN | Gernots Stücklisten wirken, Speichern setzt sie nicht mehr außer Kraft | MG-10005/MG-10020 Snackbox Brotzeitmix/Salatmix: Saatgutmischung in einer Schale oder zusammengestellt? (Frage 2) |
| G13 | LIVE_TEILWEISE | Ein Abo mit Mix wird aufgelöst (Test), der Abo-Entwurf ist im Tagesplan bis zum Liefertag packbar | Inhalt des Gastrotrays (Frage 3), die 4 LfA-Entwürfe (A-R2 → R-B3 aus Abschnitt B bzw. Runbook B Schritt 7 aus Paket 2) |
| G12 | LIVE (ohne Umschalter) | Umschalter „Sorten \| Artikel“ im Tagesplan | — |
| G10 | LIVE_TEILWEISE | „Gepackt“ und „Ausgeliefert“ für Entwürfe mit einem Klick bis zum Liefertag, Audit mit Bestätigung; Entwürfe vergangener Tage bleiben gesperrt | Gernots Zustimmung (Frage 1), die 7 Alt-Entwürfe (A-R2, Frage 4) |

### Überschneidungen mit D/F/O (gegen `/tmp/n0910/plan.md` und den Branch `feat/nachtrag-0910` @ `bd56901` geprüft)

1. **`frontend/src/pages/Tagesplan.tsx`, O.4 (Nachtrag-Task 14).**
   - O.4 ersetzt die Importzeile `import { invalidateOrderViews } from '../services/orderQueries';` durch sich selbst plus `import { belegHerunterladen } from '../services/belegordner';`.
   - Außerdem ersetzt O.4 in `packlisteMutation` die Zeile `await documentsApi.downloadPackingListPdf(note);` durch den `belegHerunterladen`-Block.
   - A.5 ändert andere Stellen: die Importzeile aus `../services/api` (nach O.4 weiter `documentsApi` in `packlisteMutation`), den Kommentar vor `export default function Tagesplan`, den State nach `offeneBestellung`, `ausgeliefertMutation`, `gepacktMutation`, `statusWechsel`, die Knöpfe in Verpacken und Ausliefern und die Karte Sortenbedarf.
   - Keine Zeile wird von beiden geändert. Gemessen: alle 10 A-Anker vor und nach O.4 genau einmal, `tsc` sauber, Build ✓.
2. **`frontend/src/services/api.ts`, D.5 (Nachtrag-Task 5) und O.4 (Nachtrag-Task 14).**
   - D fügt `DatevEinstellungen` vor `export interface AppSettingResponse` ein und `invoicesApi.datevEinstellungen`. O ändert `documentsApi`.
   - A.5 ändert `DayPlanOrder` (Feld `packbar` und zwei neue Felder) und `salesApi.updateOrderStatus`. Die Stellen sind getrennt. Gemessen: beide A-Anker vor und nach D/O genau einmal.
3. **Keine Überschneidung (geprüft mit `git diff df84f7b bd56901`):**
   - **Backend:** `backend/app/api/v1/products.py`, `production.py` und `sales.py`, `backend/app/services/order_status_service.py`, `backend/app/schemas/order.py`.
   - **Frontend:** `frontend/src/pages/Products.tsx`.
   - **Testdateien:** D/F/O nutzen `test_nachtrag_0910.py`, A legt `test_paket4.py` an bzw. hängt dort an.
   - `pdf_service.line_desc_cell` (Nebenwirkung von A-R1) ist nach F unverändert. F ändert nur `render_company_header_block` und `render_company_footer_block`.
4. **„Setzt D/F/O voraus“:** kein Schritt. Alle A-Anker sind auf `df84f7b` und auf dem D/F/O-Stand identisch. Gemessen auf beiden Ständen, siehe Prüfstand.
5. **Nur als Hinweis fürs Nachspiel, nicht D/F/O:** Innerhalb von Paket 4 ändert Abschnitt B (B.3) in `order_status_service.py` den Import und `setze_status`, der Paket-4-Abschnitt D in `sales.py` Kundenfunktionen und `create_order`. A ankert dort auf `def trage_lieferdatum_nach(`, den Import aus `order_status_service`, `confirm_order` und `update_order_status`, also auf andere Stellen. Mit B.3 legt „Ausgeliefert“ zusätzlich einen Lieferschein an; das ändert nichts an A, verstärkt aber den Grund für die Liefertag-Regel (A-E3).

### Prüfstand (alles in Kopien unter `/tmp`, Repo unverändert, Produktion nur lesend)

- **Diese Fassung, auf zwei Ständen nachgespielt:** `/tmp/p4-kopie-arev3` (`git archive df84f7b`) und `/tmp/p4-kopie-arev3-dfo` (`git archive bd56901` = `feat/nachtrag-0910` mit D.1–O.5), `node_modules` jeweils als Symlink. Die Blöcke aus **diesem Dokument** wurden je Task mechanisch mit ihren Ankern angewendet (`/tmp/p4a-rev3-tools/replay.py`), jeder Anker genau einmal.
  - Vorbereitung A: auf beiden Ständen genau die angegebenen Ausgaben.
  - Rot/Grün auf beiden Ständen gleich: A.1 `5 failed, 1 passed` → `6 passed` (Umfeld `222 passed`). A.2 `3` → `0`, `tsc` sauber. A.3 `6 failed, 3 passed` mit den Meldungen aus Step 2 → `15 passed` (Umfeld `804 passed`). A.4 `3 failed` (`KeyError`) → `18 passed` (Umfeld `141 passed`). A.5 `tsc` genau die 4 Fehler → sauber, Build `✓ built`, `grep`-Prüfungen `1`/`3`/`2`, `belegHerunterladen` `0` auf `df84f7b` bzw. `2` auf dem D/F/O-Stand.
  - **Gegenprobe Liefertag-Regel:** `_im_tagesplan_bestaetigbar` testweise auf `return True` → genau die zwei neuen Tests rot (`test_vergangener_entwurf_wird_im_tagesplan_nicht_bestaetigt`, `test_vergangener_entwurf_bekommt_keinen_knopf`), die übrigen 16 grün.
  - Prozedur V: `df84f7b` nach A `14 failed, 1662 passed, 2 skipped, 1 error`. D/F/O-Stand Basis `14 failed, 1709 passed, 2 skipped, 1 error`, nach A `14 failed, 1727 passed, 2 skipped, 1 error`. Abgleich jeweils leer. `ruff --select F821,F823` über die 6 Python-Dateien: Exit 0.
  - Geänderte Dateien gegen den jeweiligen Ausgangsstand: genau die 9 aus A.6 Step 3.
  - Baseline-Block (Kopf, Global Constraints) in `zsh` und `bash`: `15`, Inhalt gleich den Fehlernamen der D/F/O-Basis.
- **Vorfassungen** (`/tmp/p4-kopie-a*`, `/tmp/p4-kopie-arev*`, ohne Liefertag-Regel): A.1 und A.2 sind seither unverändert.
- **Produktion, nur lesend (`mode=ro`, 09.10.2026):**
  - 7 Entwürfe mit Liefertag vor heute (Liste in Ist-Stand 3), 4 Entwürfe mit Liefertag 09.10. (Packtag 08.10.).
  - RE-2026-00001 (OFFEN, versendet 08.10. 06:19:56) und RE-2026-00005 (OFFEN, versendet 08.10. 06:18:43).
  - MG-12025: `is_bundle=0`, Stückliste seit 08.10. 02:43:55, `updated_at` 09.10. 11:32:25.
  - Mix-Artikel ohne Stückliste: MG-10005 „BIO Snackbox | Brotzeitmix“, MG-10020 „BIO Snackbox | Salatmix“ und die Kisten Brotzeitmix/Salatmix MG-11019, MG-11034, MG-12004, MG-12019. Saatgut „Brotzeitmix“ und „Salatmix“ ist je als eine Sorte angelegt (`is_mix=0`).
  - **A-R1-Trockenlauf** mit genau dem Skript und dem Aufruf aus dem Runbook (`ssh … 'C=…; docker exec -i "$C" python3 -' < /tmp/p4a-r1.py`): Ausgabe wie in Schritt 1 beschrieben. Er ist vor APPLY zu wiederholen.
- **A-R1 APPLY** gegen eine synthetische lokale DB (Vorfassung, Skript seither unverändert): `geschrieben 24`, ein zweiter Lauf bricht mit „Kandidaten weichen … ab“ ab.
- **Nicht gemessen:** die Oberfläche im Browser, die Commits (Kopien ohne Git-Historie) und die schreibenden Runbook-Schritte (Backup, APPLY, `scp`). Das ist Manager-Arbeit.

### Vorbereitung A

Ausgangsstand A, Baseline-Namen und Prozedur V auf der Basis stehen in „Vorbereitung (vor Task 1)“ im Kopf und sind dort vor Task 1 geprüft. `<Basis-A>` = `<Basis>` (A läuft zuerst).

---

### Task 1 (A.1): Ein Artikel mit Stückliste bleibt beim Speichern ein festes Bundle (G11, G74, G13)

**Files:**
- Modify: `backend/app/api/v1/products.py` (neu `_bundle_art_ableiten` vor `update_product`, Aufruf in `update_product`)
- Create/Modify: `backend/tests/test_paket4.py` (Kopf, falls neu; Block A.1 anhängen)

**Interfaces:**
- Produces: `products._bundle_art_ableiten(db, product) -> None` (setzt `product.is_bundle`, committet nicht). `PATCH /api/v1/products/{id}` antwortet mit `is_bundle` gemäß der Regel aus A-E1, egal welches `is_bundle` der Client schickt.
- Produces (Test-Helfer, A.3 und A.4 nutzen sie): `_p4a_ohne_celery` (Fixture), `_p4a_heute`, `_p4a_basiseinheit`, `_p4a_produkt`, `_p4a_mix`, `_p4a_speichern`, `_p4a_kennzeichen_wie_in_prod`, `_p4a_kunde`, `_p4a_bestellung`, `_p4a_sortenbedarf`, `_p4a_abo_lieferung`.
- Consumes: `BundleComponent`, `select` (in `products.py` schon importiert), `subscription_tasks._create_order_from_subscription` (B6), `order_status_service.heute_berlin`.

**Review Focus (A.1):**
- Die Regel gilt bei **jedem** PATCH, auch wenn der Client `is_bundle` gar nicht schickt.
- Ohne Stückliste ändert sich nichts.
- Ein Artikel mit Stückliste, dessen Kategorie jemand von BUNDLE weg ändert, bleibt Bundle. Das Formular zeigt die Stückliste dann nicht mehr an (Grenzfall, in Prod nicht vorhanden).
- `remove_bundle_component` bleibt unverändert. Ein Mix ohne Komponenten zählt im Packplan als Einzelartikel (Bestand).

- [ ] **Step 1: Testblock anhängen.** Fehlt `backend/tests/test_paket4.py`, zuerst mit genau diesem Kopf anlegen (gilt für alle Abschnitte von Paket 4; existiert die Datei schon, Kopf weglassen):

```python
"""Paket 4 — Gernots Rückmeldungen vom 08. und 09.10.2026 (Abgleich aller Wünsche).

Gemeinsame Testdatei aller Abschnitte. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP4A…/_p4a_ für Abschnitt A, TestP4B…/_p4b_ usw.):
ein gleichnamiger Helfer würde still ersetzt. Jeder Abschnitt bringt seine
Importe selbst mit. Keine autouse-Fixture.
"""
```

Dann diesen Block **ans Dateiende** anhängen (beginnt mit zwei Leerzeilen):

```python


# ============================================================
# Abschnitt A — Tagesplan: Mix-Auflösung (G11, G74, G13) und
# „Gepackt“/„Ausgeliefert“ auch für Entwürfe (G10)
# ============================================================
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal


@pytest.fixture()
def _p4a_ohne_celery():
    """Anlegen und Bestätigen stoßen per Celery ein Forecast-Update an; ohne
    Redis wartet jeder Aufruf auf Wiederholungen. Für Abschnitt A ohne Belang
    (wie _a4_ohne_celery in test_gernot_261008_paket2.py)."""
    with patch("app.tasks.forecast_tasks.update_forecast_from_order.delay"):
        yield


def _p4a_heute():
    """Kalendertag des Servers (Europe/Berlin), wie Packtag und Lieferdatum."""
    from app.services.order_status_service import heute_berlin
    return heute_berlin()


def _p4a_basiseinheit():
    """Basiseinheit 'G' — die Produktanlage verlangt sie, es gibt keinen
    API-Weg dorthin (wie base_unit in test_gernot_260817.py)."""
    from app.models.unit import UnitCategory, UnitOfMeasure
    with TestingSessionLocal() as db:
        if not db.query(UnitOfMeasure).filter_by(code="G").first():
            db.add(UnitOfMeasure(code="G", name="Gramm", symbol="g",
                                 category=UnitCategory.WEIGHT, is_base_unit=True))
            db.commit()


def _p4a_produkt(client, name, sku, kategorie="MICROGREEN"):
    _p4a_basiseinheit()
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": name, "category": kategorie, "base_price": 3.0,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p4a_mix(client, sorten, name="BIO Genussmix (VPE 6)", sku="P4A-MIX"):
    """Mix wie Gernot ihn am 09.10. angelegt hat: Kategorie BUNDLE, Formular
    offen, Komponenten über die Stückliste. sorten: [(Produkt, Anteil)].
    Zurück kommt der Stand beim Öffnen des Formulars (is_bundle false)."""
    mix = _p4a_produkt(client, name, sku, kategorie="BUNDLE")
    for sorte, anteil in sorten:
        r = client.post(f"/api/v1/products/{mix['id']}/bundle-components", json={
            "child_product_id": sorte["id"], "quantity": anteil,
        })
        assert r.status_code == 201, r.text
    return mix


def _p4a_speichern(client, offen, *, altes_formular=False, **aenderung):
    """PATCH wie „Speichern“ im Produktformular (Products.tsx, handleSubmit).

    `offen` ist der Stand beim Öffnen. Das alte Formular (bis Paket 4) schickte
    is_bundle aus diesem Stand mit, das neue schickt es nicht mehr."""
    daten = {
        "name": offen["name"], "category": offen["category"],
        "base_price": offen["base_price"], "tax_rate": offen["tax_rate"],
        "is_variable_bundle": offen["is_variable_bundle"],
        "variable_bundle_min_slots": 1, "variable_bundle_max_slots": 8,
        "is_active": True, "is_sellable": True,
    }
    if altes_formular:
        daten["is_bundle"] = offen["is_bundle"]
    daten.update(aenderung)
    r = client.patch(f"/api/v1/products/{offen['id']}", json=daten)
    assert r.status_code == 200, r.text
    return r.json()


def _p4a_kennzeichen_wie_in_prod(produkt):
    """Stand der 24 Mixe in Produktion (09.10.2026): Stückliste da, is_bundle 0."""
    from app.models.product import Product
    with TestingSessionLocal() as db:
        db.get(Product, uuid.UUID(produkt["id"])).is_bundle = False
        db.commit()


def _p4a_kunde(client, name=None):
    r = client.post("/api/v1/sales/customers", json={
        "name": name or f"Packkunde {uuid.uuid4().hex[:6]}", "typ": "GASTRO",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _p4a_bestellung(client, liefertag, positionen=(("Erbsen-Schale", 5),), *, bestaetigen=False):
    """Bestellung wie aus Gernots Formular: ENTWURF.

    positionen: (Produkt-JSON oder freier Name, Menge); leer = ohne Position."""
    lines = []
    for ware, menge in positionen:
        zeile = {"quantity": menge, "unit": "STK", "unit_price": 3.0, "tax_rate": "REDUZIERT"}
        if isinstance(ware, dict):
            zeile.update(product_id=ware["id"], product_name=ware["name"])
        else:
            zeile.update(product_name=ware)
        lines.append(zeile)
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": _p4a_kunde(client)["id"],
        "requested_delivery_date": liefertag.isoformat(),
        "lines": lines,
    })
    assert r.status_code == 201, r.text
    order = r.json()
    if bestaetigen:
        r = client.post(f"/api/v1/sales/orders/{order['id']}/confirm")
        assert r.status_code == 200, r.text
        order = r.json()
    return order


def _p4a_sortenbedarf(client, packtag):
    """Sortenbedarf im Tagesplan: {Sorte: Menge} (packaging-plan, komponenten)."""
    r = client.get("/api/v1/production/packaging-plan",
                   params={"target_date": packtag.isoformat()})
    assert r.status_code == 200, r.text
    return {k["product_name"]: k["total_quantity"] for k in r.json()["komponenten"]}


def _p4a_abo_lieferung(kunde, produkt, menge, liefertag):
    """Abo mit einer Position anlegen und die Lieferung erzeugen wie der
    Abo-Lauf (subscription_tasks._create_order_from_subscription, B6)."""
    from app.models.customer import Subscription, SubscriptionInterval, SubscriptionItem
    from app.tasks.subscription_tasks import _create_order_from_subscription
    with TestingSessionLocal() as db:
        sub = Subscription(
            kunde_id=uuid.UUID(kunde["id"]), product_id=uuid.UUID(produkt["id"]),
            menge=Decimal(str(menge)), einheit="STUECK",
            intervall=SubscriptionInterval.WOECHENTLICH,
            liefertage=[liefertag.weekday()], gueltig_von=liefertag,
        )
        sub.positionen.append(SubscriptionItem(
            position=1, product_id=uuid.UUID(produkt["id"]),
            menge=Decimal(str(menge)), einheit="STUECK",
        ))
        db.add(sub)
        db.flush()
        order = _create_order_from_subscription(db, sub, liefertag)
        db.commit()
        return order.order_number


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4AStueckliste:
    """A.1 (G11, G74, G13): Ein Artikel mit Stückliste ist ein festes Bundle.

    Prod 09.10.2026: 25 Artikel mit Stückliste, 24 davon is_bundle=0. Das
    Formular schickte beim Speichern is_bundle=false aus dem Stand vom Öffnen
    und setzte das Kennzeichen zurück, das add_bundle_component gesetzt hatte.
    Der Tagesplan löst nur Bundles auf und zeigte den Mix ungeteilt."""

    def test_altes_formular_setzt_kennzeichen_nicht_zurueck(self, client):
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 1)])

        gespeichert = _p4a_speichern(client, offen, altes_formular=True)
        assert gespeichert["is_bundle"] is True

    def test_speichern_heilt_den_prod_zustand(self, client):
        """Einer der 24 Mixe nach dem Deploy: einmal speichern genügt."""
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 1)])
        _p4a_kennzeichen_wie_in_prod(offen)

        gespeichert = _p4a_speichern(client, offen)
        assert gespeichert["is_bundle"] is True

    def test_sortenbedarf_loest_gespeicherten_mix_auf(self, client):
        """Gernot (B1): „BIO Genussmix (VPE 6): 10“ → Einzelsorten in Stück."""
        heute = _p4a_heute()
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        radieschen = _p4a_produkt(client, "BIO Snackbox | Radieschen", "P4A-RAD")
        offen = _p4a_mix(client, [(erbse, 1), (radieschen, 1)])
        _p4a_speichern(client, offen, altes_formular=True)
        _p4a_bestellung(client, heute + timedelta(days=1), [(offen, 10)])

        assert _p4a_sortenbedarf(client, heute) == {
            "BIO Snackbox | Erbse": 10, "BIO Snackbox | Radieschen": 10,
        }

    def test_abo_lieferung_eines_mixes_wird_aufgeloest(self, client):
        """G13: Die Abo-Lieferung trägt das Abo-Produkt; ist es ein Mix, stehen
        im Sortenbedarf seine Sorten."""
        heute = _p4a_heute()
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 3)], name="BIO Microgreens Mix KKER (VPE 12)", sku="P4A-KKER")
        _p4a_speichern(client, offen, altes_formular=True)
        _p4a_abo_lieferung(_p4a_kunde(client, "Dorint Testhotel"), offen, 4, heute)

        assert _p4a_sortenbedarf(client, heute) == {"BIO Snackbox | Erbse": 12}

    def test_variabel_ist_kein_festes_bundle(self, client):
        """Umschalten auf „Variabel (Gastrotray)“: die Bestellung wählt die
        Sorten, eine alte Stückliste gilt nicht mehr."""
        erbse = _p4a_produkt(client, "BIO Snackbox | Erbse", "P4A-ERB")
        offen = _p4a_mix(client, [(erbse, 1)], name="BIO Gastrotray (1-8 Sorten)", sku="P4A-TRAY")

        gespeichert = _p4a_speichern(client, offen, is_variable_bundle=True)
        assert (gespeichert["is_variable_bundle"], gespeichert["is_bundle"]) == (True, False)

    def test_ohne_stueckliste_bleibt_einzelartikel(self, client):
        """Charakterisierung: „BIO Kiste | Erbse (VPE 6)“ ohne Stückliste bleibt,
        was er ist, und steht als Artikel im Sortenbedarf."""
        heute = _p4a_heute()
        offen = _p4a_produkt(client, "BIO Kiste | Erbse (VPE 6)", "P4A-KISTE", kategorie="BUNDLE")

        gespeichert = _p4a_speichern(client, offen, altes_formular=True)
        assert gespeichert["is_bundle"] is False
        _p4a_bestellung(client, heute + timedelta(days=1), [(offen, 2)])
        assert _p4a_sortenbedarf(client, heute) == {"BIO Kiste | Erbse (VPE 6)": 2}
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4AStueckliste -q -p no:cacheprovider 2>&1 | tail -15`

Erwartet: `5 failed, 1 passed`.
- **Grün** ist nur `test_ohne_stueckliste_bleibt_einzelartikel`.
- **Rot** mit diesen Meldungen:
  - `test_altes_formular_setzt_kennzeichen_nicht_zurueck` und `test_speichern_heilt_den_prod_zustand`: `assert False is True`.
  - `test_sortenbedarf_loest_gespeicherten_mix_auf`: Links steht `{'BIO Genussmix (VPE 6)': 10.0}`, rechts `{'BIO Snackbox | Erbse': 10, 'BIO Snackbox | Radieschen': 10}`.
  - `test_abo_lieferung_eines_mixes_wird_aufgeloest`: Links steht `{'BIO Microgreens Mix KKER (VPE 12)': 4.0}`, rechts `{'BIO Snackbox | Erbse': 12}`.
  - `test_variabel_ist_kein_festes_bundle`: `assert (True, True) == (True, False)`.

- [ ] **Step 3: Implementierung.** In `backend/app/api/v1/products.py` den Helfer vor `update_product` einfügen:

Anker (genau einmal):

```python
@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
```

ersetzen durch:

```python
def _bundle_art_ableiten(db: Session, product: Product) -> None:
    """Bundle-Art beim Speichern aus der Stückliste ableiten (Paket 4, G11/G74).

    - Variabel (Gastrotray): die Bestellung wählt die Sorten, also kein festes
      Bundle, auch wenn noch eine alte Stückliste anhängt.
    - Sonst: wer eine Stückliste hat, ist ein festes Bundle (Mischkiste).
    - Ohne Stückliste bleibt das Kennzeichen, wie es ist.

    add_bundle_component setzt is_bundle seit 19.08.2026. Das Produktformular
    schickte beim Speichern aber is_bundle aus dem Stand vom Öffnen mit (false)
    und setzte das Kennzeichen zurück. Packplan, Bestandsabzug und Belege lesen
    is_bundle; der Tagesplan zeigte den Mix deshalb ungeteilt (Prod 09.10.2026:
    24 von 25 Artikeln mit Stückliste auf 0). Ein mitgeschicktes is_bundle
    entscheidet hier nicht.
    """
    if product.is_variable_bundle:
        product.is_bundle = False
        return
    if product.is_bundle:
        return
    hat_stueckliste = db.execute(
        select(BundleComponent.id)
        .where(BundleComponent.parent_product_id == product.id)
        .limit(1)
    ).first() is not None
    if hat_stueckliste:
        product.is_bundle = True


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
```

und in `update_product` den Aufruf nach der `setattr`-Schleife ergänzen:

Anker (genau einmal):

```python
    update_data = pfand_vorgaben(update_data, set(update_data), bisher=product)
    for field, value in update_data.items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product
```

ersetzen durch:

```python
    update_data = pfand_vorgaben(update_data, set(update_data), bisher=product)
    for field, value in update_data.items():
        setattr(product, field, value)
    _bundle_art_ableiten(db, product)

    db.commit()
    db.refresh(product)
    return product
```

Prüfen: `grep -n "_bundle_art_ableiten" backend/app/api/v1/products.py` → genau 2 Treffer (`def` und Aufruf in `update_product`).

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4AStueckliste -q -p no:cacheprovider 2>&1 | tail -3` → `6 passed`.

Umfeld: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_261008_paket2.py tests/test_b6_abo_positionen.py tests/test_import_bestellungen_zukunft.py tests/test_warenfluss.py -q -p no:cacheprovider 2>&1 | tail -1` → `222 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/products.py backend/tests/test_paket4.py
git commit -m "fix(produkte): Artikel mit Stückliste bleibt beim Speichern festes Bundle, variabel heißt kein festes Bundle (P4-A.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2 (A.2): Produktformular schickt `is_bundle` nicht mehr (G74)

**Files:**
- Modify: `frontend/src/pages/Products.tsx` (`ProductForm`: Zustand `formData`, die zwei Optionsfelder „Bundle-Typ“)

**Interfaces:**
- Consumes: A.1 (der Server leitet `is_bundle` ab). Produces: `productsApi.create`/`update` aus `ProductForm` ohne `is_bundle`.

**Review Focus (A.2):** Das Optionsfeld „Fest (Mischkiste)“ bleibt über `checked={!formData.is_variable_bundle}` gewählt. Der Wechsel „Variabel“ ↔ „Fest“ setzt nur noch `is_variable_bundle`. Die Stückliste erscheint wie bisher nur bei Kategorie BUNDLE und „Fest“.

- [ ] **Step 1: Ausgangszählung**

Run: `grep -c "is_bundle:" frontend/src/pages/Products.tsx` → `3`.

- [ ] **Step 2: Implementierung.** In `frontend/src/pages/Products.tsx`, Funktion `ProductForm`, im Zustand `formData`:

Anker (genau einmal):

```tsx
    is_bundle: product?.is_bundle ?? false,
    is_variable_bundle: product?.is_variable_bundle ?? false,
```

ersetzen durch:

```tsx
    // is_bundle schickt das Formular nicht: der Server leitet es aus der
    // Stückliste ab (Paket 4, products._bundle_art_ableiten). Bis Paket 4 ging
    // hier der Stand vom Öffnen mit und setzte das Kennzeichen zurück.
    is_variable_bundle: product?.is_variable_bundle ?? false,
```

Im `fieldset` „Bundle-Typ“, Optionsfeld „Fest (Mischkiste)“:

Anker (genau einmal):

```tsx
              onChange={() => setFormData({ ...formData, is_variable_bundle: false, is_bundle: true })}
```

ersetzen durch:

```tsx
              onChange={() => setFormData({ ...formData, is_variable_bundle: false })}
```

Optionsfeld „Variabel (Gastrotray)“:

Anker (genau einmal):

```tsx
              onChange={() => setFormData({ ...formData, is_variable_bundle: true, is_bundle: false })}
```

ersetzen durch:

```tsx
              onChange={() => setFormData({ ...formData, is_variable_bundle: true })}
```

- [ ] **Step 3: Prüfen**

Run: `grep -c "is_bundle:" frontend/src/pages/Products.tsx` → `0`. Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Products.tsx
git commit -m "fix(produkte): Produktformular schickt is_bundle nicht mehr mit, der Server leitet es aus der Stückliste ab (P4-A.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3 (A.3): Entwurf beim Packen bzw. Ausliefern bestätigen — über die eine Statusregel, nur bis zum Liefertag (G10)

**Files:**
- Modify: `backend/app/services/order_status_service.py` (neu vor `trage_lieferdatum_nach`: `MIT_BESTAETIGUNG`, `bestaetigen`, `_im_tagesplan_bestaetigbar`, `im_tagesplan_moeglich`, `setze_status_im_tagesplan`)
- Modify: `backend/app/schemas/order.py` (`OrderStatusUpdate.entwurf_bestaetigen`)
- Modify: `backend/app/api/v1/sales.py` (Import aus `order_status_service`, `confirm_order`, `update_order_status`)
- Modify: `backend/tests/test_paket4.py` (Block A.3 anhängen)

**Interfaces:**
- Produces (`app.services.order_status_service`):
  - **`MIT_BESTAETIGUNG: dict[OrderStatus, str]`:** `IN_PRODUKTION` → „Beim Packen im Tagesplan bestätigt“, `GELIEFERT` → „Beim Ausliefern im Tagesplan bestätigt“.
  - **`bestaetigen(db, order, *, user, reason=None, bestaetigtes_lieferdatum=None) -> None`:** wirft `StatuswechselFehler` mit „Bestellung hat Status <X>, kann nicht bestätigt werden“ bzw. „Bestellung ohne Positionen kann nicht bestätigt werden“. Committet nicht.
  - **`_im_tagesplan_bestaetigbar(order) -> bool`:** `order.requested_delivery_date >= heute_berlin()`.
  - **`im_tagesplan_moeglich(order, ziel) -> bool`:** nimmt die Bestellung, nicht nur den Status (Liefertag-Regel).
  - **`setze_status_im_tagesplan(db, order, neu, *, user, reason=None, lieferdatum=None) -> bool`:** `True`, wenn bestätigt wurde. Ein Entwurf mit Liefertag vor heute: `StatuswechselFehler` „Entwurf mit Liefertag TT.MM.JJJJ liegt in der Vergangenheit — erst in der Bestellliste bestätigen oder stornieren“, nichts geändert. Committet nicht.
- Produces (API):
  - **`POST /sales/orders/{id}/status`** mit `{"entwurf_bestaetigen": true}`: Ein Entwurf mit Liefertag heute oder später wird vor IN_PRODUKTION bzw. GELIEFERT bestätigt. Das ergibt zwei Audit-Einträge (CONFIRM mit dem Grund aus `MIT_BESTAETIGUNG`, dann STATUS_CHANGE), `confirmed_delivery_date` = Liefertag und einen Forecast-Anstoß „CONFIRM“. Liefertag vor heute: 400 mit der Meldung oben.
  - **Ohne das Kennzeichen** gilt alles wie in Paket 2.
  - **`POST /confirm`** antwortet unverändert (Status, Texte, `confirmed_delivery_date`).
- Consumes: `setze_status`, `ERLAUBTE_UEBERGAENGE`, `bezeichnung` (alle in `order_status_service`).

**Review Focus (A.3):**
- Bestätigung und Statuswechsel laufen in einer Transaktion. `update_order_status` rollt bei `StatuswechselFehler`/`BestandsbuchungFehler` beides zurück.
- Ein Entwurf mit Liefertag vor heute wird im Tagesplan weder bestätigt noch gepackt noch geliefert (A-E3). Die Prüfung steht vor `bestaetigen`, es entsteht kein Audit-Eintrag.
- `confirm_order` und der Tagesplan nutzen dieselbe Funktion `bestaetigen`. `_create_audit_log` wird von `confirm_order` nicht mehr genutzt, bleibt aber für andere Aufrufer.
- Der Audit-Eintrag CONFIRM trägt jetzt `user_name`. Basic-Auth-Nutzer brechen beim Bestätigen nicht mehr an `UUID(user["id"])` ab, sondern `user_uuid` liefert `None`.
- Der Sammel-Endpunkt `bulk-status` bleibt unverändert.
- **Rechte:** Es entsteht kein neues Recht. Der Router `sales` hängt an `_deps_auftraege` (`main.py`: Vertrieb, Buchhaltung, Planer, Produktion); die Rolle Produktion konnte `POST /confirm` schon bisher aufrufen, `entwurf_bestaetigen` gibt es nur auf demselben Router.

- [ ] **Step 1: Testblock ans Dateiende anhängen** (`backend/tests/test_paket4.py`, beginnt mit zwei Leerzeilen):

```python


def _p4a_status(client, order, status, **extra):
    """Derselbe Aufruf wie die Knöpfe im Tagesplan (salesApi.updateOrderStatus)."""
    return client.post(f"/api/v1/sales/orders/{order['id']}/status",
                       json={"status": status, **extra})


def _p4a_lesen(client, order):
    r = client.get(f"/api/v1/sales/orders/{order['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def _p4a_positionen_loeschen(order):
    """Entwurf ohne Positionen. Die Schnittstelle legt keinen an (400), Altbestand
    und Importe kennen ihn — darum direkt in der DB."""
    from sqlalchemy import delete
    from app.models.order import OrderLine
    with TestingSessionLocal() as db:
        db.execute(delete(OrderLine).where(OrderLine.order_id == uuid.UUID(order["id"])))
        db.commit()


def _p4a_audit(client, order):
    """(Aktion, alter Status, neuer Status, Grund) je Statuseintrag, sortiert."""
    r = client.get(f"/api/v1/sales/orders/{order['id']}/audit-log")
    assert r.status_code == 200, r.text
    return sorted(
        (e["action"], (e["old_values"] or {}).get("status"),
         (e["new_values"] or {}).get("status"), e["reason"])
        for e in r.json() if (e["new_values"] or {}).get("status")
    )


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4AEntwurfPacken:
    """A.3 (G10): „Gepackt“ und „Ausgeliefert“ im Tagesplan bestätigen einen
    Entwurf im selben Schritt — über die eine Statusregel (order_status_service),
    mit eigenem Audit-Eintrag CONFIRM, nur bis zum Liefertag. Ohne das
    Kennzeichen bleibt alles wie in Paket 2."""

    def test_gepackt_bestaetigt_den_entwurf(self, client):
        morgen = _p4a_heute() + timedelta(days=1)
        o = _p4a_bestellung(client, morgen)

        r = _p4a_status(client, o, "IN_PRODUKTION", reason="Im Tagesplan als gepackt markiert",
                        entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "IN_PRODUKTION"
        assert r.json()["confirmed_delivery_date"] == morgen.isoformat()
        assert _p4a_audit(client, o) == [
            ("CONFIRM", "ENTWURF", "BESTAETIGT", "Beim Packen im Tagesplan bestätigt"),
            ("STATUS_CHANGE", "BESTAETIGT", "IN_PRODUKTION", "Im Tagesplan als gepackt markiert"),
        ]

    def test_ausgeliefert_bestaetigt_den_entwurf(self, client):
        heute = _p4a_heute()
        o = _p4a_bestellung(client, heute)

        r = _p4a_status(client, o, "GELIEFERT", entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert (r.json()["status"], r.json()["actual_delivery_date"]) == ("GELIEFERT", heute.isoformat())
        assert _p4a_audit(client, o) == [
            ("CONFIRM", "ENTWURF", "BESTAETIGT", "Beim Ausliefern im Tagesplan bestätigt"),
            ("STATUS_CHANGE", "BESTAETIGT", "GELIEFERT", None),
        ]

    def test_gepackter_entwurf_verlaesst_den_sortenbedarf(self, client):
        """Gernot (A4): gepackt → sofort raus aus dem Sortenbedarf, auch als Entwurf."""
        heute = _p4a_heute()
        morgen = heute + timedelta(days=1)
        _p4a_bestellung(client, morgen, [("Erbsen-Schale", 3)])
        gepackt = _p4a_bestellung(client, morgen, [("Erbsen-Schale", 5)])
        assert _p4a_sortenbedarf(client, heute) == {"Erbsen-Schale": 8}

        r = _p4a_status(client, gepackt, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert _p4a_sortenbedarf(client, heute) == {"Erbsen-Schale": 3}

    def test_entwurf_ohne_positionen_wird_nicht_gepackt(self, client):
        morgen = _p4a_heute() + timedelta(days=1)
        o = _p4a_bestellung(client, morgen)
        _p4a_positionen_loeschen(o)

        r = _p4a_status(client, o, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung ohne Positionen kann nicht bestätigt werden"
        assert _p4a_lesen(client, o)["status"] == "ENTWURF"

    def test_scheitert_das_liefern_bleibt_der_entwurf(self, client):
        """Bestätigung und Statuswechsel in einer Transaktion: alles oder nichts."""
        heute = _p4a_heute()
        morgen = heute + timedelta(days=1)
        o = _p4a_bestellung(client, heute)

        r = _p4a_status(client, o, "GELIEFERT", entwurf_bestaetigen=True,
                        actual_delivery_date=morgen.isoformat())
        assert r.status_code == 400
        assert r.json()["detail"] == f"Lieferdatum {morgen:%d.%m.%Y} liegt in der Zukunft"
        best = _p4a_lesen(client, o)
        assert (best["status"], best["confirmed_delivery_date"]) == ("ENTWURF", None)
        assert _p4a_audit(client, o) == []

    def test_vergangener_entwurf_wird_im_tagesplan_nicht_bestaetigt(self, client):
        """Prod 09.10.2026: 7 Entwürfe mit Liefertag vor heute, u. a. die falsch
        erfasste Bierbichler-Bestellung (G80) und vier LfA-Abo-Lieferungen. Ein
        Klick im Tagesplan eines vergangenen Tages darf sie weder bestätigen
        noch liefern: aus Geliefert führt kein Weg zurück."""
        gestern = _p4a_heute() - timedelta(days=1)
        o = _p4a_bestellung(client, gestern)
        meldung = (f"Entwurf mit Liefertag {gestern:%d.%m.%Y} liegt in der Vergangenheit "
                   "— erst in der Bestellliste bestätigen oder stornieren")

        # Wie der Tagesplan an einem vergangenen Tag: Lieferdatum = dieser Tag
        r = _p4a_status(client, o, "GELIEFERT", entwurf_bestaetigen=True,
                        actual_delivery_date=gestern.isoformat())
        assert (r.status_code, r.json()["detail"]) == (400, meldung)
        r = _p4a_status(client, o, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert (r.status_code, r.json()["detail"]) == (400, meldung)
        best = _p4a_lesen(client, o)
        assert (best["status"], best["confirmed_delivery_date"]) == ("ENTWURF", None)
        assert _p4a_audit(client, o) == []

    def test_ohne_kennzeichen_gilt_die_regel_aus_paket_2(self, client):
        """Charakterisierung: Bestellliste, Sammelaktion und Fremd-Clients
        schicken das Kennzeichen nicht — ENTWURF → Gepackt bleibt verboten."""
        o = _p4a_bestellung(client, _p4a_heute() + timedelta(days=1))

        r = _p4a_status(client, o, "IN_PRODUKTION")
        assert r.status_code == 400
        assert r.json()["detail"] == "Statuswechsel nicht möglich: Entwurf → Gepackt"
        assert _p4a_lesen(client, o)["status"] == "ENTWURF"

    def test_bestaetigte_bestellung_wird_nicht_nochmal_bestaetigt(self, client):
        """Charakterisierung: das Kennzeichen wirkt nur auf Entwürfe."""
        o = _p4a_bestellung(client, _p4a_heute() + timedelta(days=1), bestaetigen=True)

        r = _p4a_status(client, o, "IN_PRODUKTION", entwurf_bestaetigen=True)
        assert r.status_code == 200, r.text
        assert [a for a, *_ in _p4a_audit(client, o)] == ["CONFIRM", "STATUS_CHANGE"]

    def test_bestaetigen_ueber_confirm_unveraendert(self, client):
        """Charakterisierung: POST /confirm läuft jetzt über dieselbe Funktion
        (order_status_service.bestaetigen) — Antworten wie bisher."""
        morgen = _p4a_heute() + timedelta(days=1)
        o = _p4a_bestellung(client, morgen)

        r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
        assert r.status_code == 200, r.text
        assert (r.json()["status"], r.json()["confirmed_delivery_date"]) == ("BESTAETIGT", morgen.isoformat())
        assert _p4a_audit(client, o) == [("CONFIRM", "ENTWURF", "BESTAETIGT", None)]

        r = client.post(f"/api/v1/sales/orders/{o['id']}/confirm")
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung hat Status Bestätigt, kann nicht bestätigt werden"

        leer = _p4a_bestellung(client, morgen)
        _p4a_positionen_loeschen(leer)
        r = client.post(f"/api/v1/sales/orders/{leer['id']}/confirm")
        assert r.status_code == 400
        assert r.json()["detail"] == "Bestellung ohne Positionen kann nicht bestätigt werden"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4AEntwurfPacken -q -p no:cacheprovider 2>&1 | tail -15`

Erwartet: `6 failed, 3 passed`.
- **Grün:** `test_ohne_kennzeichen_gilt_die_regel_aus_paket_2`, `test_bestaetigte_bestellung_wird_nicht_nochmal_bestaetigt`, `test_bestaetigen_ueber_confirm_unveraendert`.
- **Rot:**
  - `test_gepackt_bestaetigt_den_entwurf` und `test_gepackter_entwurf_verlaesst_den_sortenbedarf`: `{"detail":"Statuswechsel nicht möglich: Entwurf → Gepackt"}` / `assert 400 == 200`.
  - `test_ausgeliefert_bestaetigt_den_entwurf`: `{"detail":"Statuswechsel nicht möglich: Entwurf → Geliefert"}` / `assert 400 == 200`.
  - `test_entwurf_ohne_positionen_wird_nicht_gepackt`: Diff `- Bestellung ohne Positionen kann nicht bestätigt werden` / `+ Statuswechsel nicht möglich: Entwurf → Gepackt`.
  - `test_scheitert_das_liefern_bleibt_der_entwurf`: Diff `- Lieferdatum <morgen TT.MM.JJJJ> liegt in der Zukunft` / `+ Statuswechsel nicht möglich: Entwurf → Geliefert`.
  - `test_vergangener_entwurf_wird_im_tagesplan_nicht_bestaetigt`: `At index 1 diff: 'Statuswechsel nicht möglich: Entwurf → Geliefert' != 'Entwurf mit Liefertag <gestern TT.MM.JJJJ> liegt in der Vergangenheit — erst in der Bestellliste bestätigen oder stornieren'`.

- [ ] **Step 3: Statusregel.** In `backend/app/services/order_status_service.py` **vor** `def trage_lieferdatum_nach(` einfügen (Anker ist die `def`-Zeile, sie bleibt stehen):

Anker (genau einmal):

```python
def trage_lieferdatum_nach(
```

ersetzen durch:

```python
# Paket 4 (G10, Gernot 08.10.2026): „Gepackt“ und „Ausgeliefert“ im Tagesplan
# bestätigen einen Entwurf im selben Schritt. Gernot erfasst Bestellungen im
# Formular als Entwurf (Prod 09.10.: 4 von 6 Lieferungen); bis Paket 4 standen
# sie im Sortenbedarf, bis jemand sie in der Bestellliste bestätigte.
# ERLAUBTE_UEBERGAENGE bleibt unverändert: der Entwurf geht über `bestaetigen`
# (ENTWURF → BESTAETIGT, eigener Audit-Eintrag CONFIRM), danach gilt
# `setze_status` wie immer. Nur der Tagesplan schickt das Kennzeichen.
MIT_BESTAETIGUNG: dict[OrderStatus, str] = {
    OrderStatus.IN_PRODUKTION: "Beim Packen im Tagesplan bestätigt",
    OrderStatus.GELIEFERT: "Beim Ausliefern im Tagesplan bestätigt",
}


def bestaetigen(
    db: Session,
    order: Order,
    *,
    user: Optional[dict],
    reason: Optional[str] = None,
    bestaetigtes_lieferdatum: Optional[date] = None,
) -> None:
    """ENTWURF → BESTAETIGT — der eine Weg zum Bestätigen (POST /confirm und
    der Tagesplan). Committet NICHT.

    Bestätigt wird nur ein Entwurf mit mindestens einer Position. Das
    bestätigte Lieferdatum ist ohne Angabe das gewünschte."""
    if order.status != OrderStatus.ENTWURF:
        raise StatuswechselFehler(
            f"Bestellung hat Status {bezeichnung(order.status)}, kann nicht bestätigt werden"
        )
    if len(order.lines) == 0:
        raise StatuswechselFehler("Bestellung ohne Positionen kann nicht bestätigt werden")
    setze_status(db, order, OrderStatus.BESTAETIGT, user=user, action="CONFIRM", reason=reason)
    order.confirmed_delivery_date = bestaetigtes_lieferdatum or order.requested_delivery_date


def _im_tagesplan_bestaetigbar(order: Order) -> bool:
    """Ein Entwurf wird im Tagesplan nur bis zu seinem Liefertag bestätigt.

    An vergangenen Tagen stehen Entwürfe, die nie bestätigt wurden (Prod
    09.10.2026: 7, darunter die falsch erfasste Bierbichler-Bestellung und
    vier LfA-Abo-Lieferungen). Ein Klick dort würde sie bestätigen und bei
    „Ausgeliefert“ unumkehrbar liefern: aus GELIEFERT führt nur FAKTURIERT
    weiter, Bestand und Leergut wären gebucht. Gilt auch für „Gepackt“, sonst
    führten zwei Klicks (Gepackt, dann Ausgeliefert) zum selben Ergebnis.
    Solche Entwürfe klärt das Büro in der Bestellliste."""
    return order.requested_delivery_date >= heute_berlin()


def im_tagesplan_moeglich(order: Order, ziel: OrderStatus) -> bool:
    """Zeigt der Tagesplan den Knopf für `ziel` (Gepackt, Ausgeliefert)?
    Dieselbe Regel wie setze_status_im_tagesplan."""
    if order.status == OrderStatus.ENTWURF and ziel in MIT_BESTAETIGUNG:
        return _im_tagesplan_bestaetigbar(order)
    return ziel in ERLAUBTE_UEBERGAENGE.get(order.status, ())


def setze_status_im_tagesplan(
    db: Session,
    order: Order,
    neu: OrderStatus,
    *,
    user: Optional[dict],
    reason: Optional[str] = None,
    lieferdatum: Optional[date] = None,
) -> bool:
    """Statuswechsel aus dem Tagesplan. Ein Entwurf wird vor „Gepackt“ bzw.
    „Ausgeliefert“ bestätigt, aber nur bis zu seinem Liefertag; sonst genau
    setze_status. Gibt zurück, ob bestätigt wurde. Committet NICHT —
    scheitert der Wechsel, rollt der Aufrufer die Bestätigung mit zurück."""
    bestaetigt = False
    if order.status == OrderStatus.ENTWURF and neu in MIT_BESTAETIGUNG:
        if not _im_tagesplan_bestaetigbar(order):
            raise StatuswechselFehler(
                f"Entwurf mit Liefertag {order.requested_delivery_date:%d.%m.%Y} liegt in der "
                "Vergangenheit — erst in der Bestellliste bestätigen oder stornieren"
            )
        bestaetigen(db, order, user=user, reason=MIT_BESTAETIGUNG[neu])
        bestaetigt = True
    setze_status(db, order, neu, user=user, reason=reason, lieferdatum=lieferdatum)
    return bestaetigt


def trage_lieferdatum_nach(
```

- [ ] **Step 4: Schema.** In `backend/app/schemas/order.py`, Klasse `OrderStatusUpdate`:

Anker (genau einmal):

```python
    actual_delivery_date: Optional[date] = Field(
        None, description="Nur bei GELIEFERT: tatsächlicher Liefertag (Standard heute, nie in der Zukunft)"
    )
```

ersetzen durch:

```python
    actual_delivery_date: Optional[date] = Field(
        None, description="Nur bei GELIEFERT: tatsächlicher Liefertag (Standard heute, nie in der Zukunft)"
    )
    entwurf_bestaetigen: bool = Field(
        False,
        description="Tagesplan (Paket 4): ein Entwurf wird vor IN_PRODUKTION bzw. GELIEFERT "
                    "im selben Schritt bestätigt (eigener Audit-Eintrag CONFIRM)",
    )
```

- [ ] **Step 5: Schnittstelle.** In `backend/app/api/v1/sales.py` den Import aus `order_status_service`:

Anker (genau einmal):

```python
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, bezeichnung, pruefe_uebergang, setze_status,
)
```

ersetzen durch:

```python
from app.services.order_status_service import (
    BestandsbuchungFehler, StatuswechselFehler, bestaetigen, bezeichnung, pruefe_uebergang,
    setze_status, setze_status_im_tagesplan,
)
```

In `confirm_order` den Block ab der 404-Prüfung bis einschließlich `db.commit()`. Danach bleiben `_trigger_forecast_update(str(order.id), "CONFIRM")` und `return await get_order(order_id, db)` unverändert stehen:

Anker (genau einmal):

```python
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    if order.status != OrderStatus.ENTWURF:
        raise HTTPException(
            status_code=400,
            detail=f"Bestellung hat Status {bezeichnung(order.status)}, kann nicht bestätigt werden"
        )

    if len(order.lines) == 0:
        raise HTTPException(
            status_code=400,
            detail="Bestellung ohne Positionen kann nicht bestätigt werden"
        )

    old_status = order.status.value
    order.status = OrderStatus.BESTAETIGT
    order.confirmed_delivery_date = confirmed_delivery_date or order.requested_delivery_date
    order.updated_by = UUID(user["id"]) if user else None
    order.updated_at = datetime.now(timezone.utc)

    _create_audit_log(
        db, order,
        user_id=UUID(user["id"]) if user else None,
        action="CONFIRM",
        old_values={"status": old_status},
        new_values={"status": order.status.value}
    )

    db.commit()
```

ersetzen durch:

```python
    if not order:
        raise HTTPException(status_code=404, detail="Bestellung nicht gefunden")

    # Dieselbe Funktion wie der Tagesplan (Paket 4, G10): Prüfungen, Status,
    # bestätigtes Lieferdatum und Audit-Eintrag CONFIRM an einer Stelle.
    try:
        bestaetigen(db, order, user=user, bestaetigtes_lieferdatum=confirmed_delivery_date)
    except StatuswechselFehler as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
```

In `update_order_status` den `try`-Anfang:

Anker (genau einmal):

```python
    neu = status_update.status
    try:
        setze_status(
            db, order, neu,
            user=user,
            reason=status_update.reason,
            lieferdatum=status_update.actual_delivery_date,
        )
    except StatuswechselFehler as e:
```

ersetzen durch:

```python
    neu = status_update.status
    bestaetigt = False
    try:
        if status_update.entwurf_bestaetigen:
            # Tagesplan (Paket 4, G10): ein Entwurf wird im selben Schritt bestätigt
            bestaetigt = setze_status_im_tagesplan(
                db, order, neu,
                user=user,
                reason=status_update.reason,
                lieferdatum=status_update.actual_delivery_date,
            )
        else:
            setze_status(
                db, order, neu,
                user=user,
                reason=status_update.reason,
                lieferdatum=status_update.actual_delivery_date,
            )
    except StatuswechselFehler as e:
```

und nach dem Commit in `update_order_status` (Anker genau einmal in der Datei):

Anker (genau einmal):

```python
    db.commit()

    # Forecast bei Stornierung triggern
    if neu == OrderStatus.STORNIERT:
        _trigger_forecast_update(str(order.id), "CANCEL")
```

ersetzen durch:

```python
    db.commit()

    # Wie POST /confirm: eine Bestätigung stößt die Prognose an
    if bestaetigt:
        _trigger_forecast_update(str(order.id), "CONFIRM")
    # Forecast bei Stornierung triggern
    if neu == OrderStatus.STORNIERT:
        _trigger_forecast_update(str(order.id), "CANCEL")
```

Prüfen:
- `grep -n "def bestaetigen\|def setze_status_im_tagesplan\|def im_tagesplan_moeglich\|^MIT_BESTAETIGUNG" backend/app/services/order_status_service.py` → 4 Treffer.
- `grep -c "^def _im_tagesplan_bestaetigbar(order: Order) -> bool:$" backend/app/services/order_status_service.py` → `1`.
- `grep -c "bestaetigen(db, order, user=user, bestaetigtes_lieferdatum=confirmed_delivery_date)" backend/app/api/v1/sales.py` → `1`.
- `grep -c "old_status = order.status.value" backend/app/api/v1/sales.py` → `0`.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4AEntwurfPacken tests/test_paket4.py::TestP4AStueckliste -q -p no:cacheprovider 2>&1 | tail -1` → `15 passed`.

Umfeld (Statusregel, Bestätigen, Paket-2/3-Abnahme): `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py tests/test_gernot_261008.py tests/test_gernot_261008_paket3.py tests/test_erp.py tests/test_import_bestellungen_zukunft.py -q -p no:cacheprovider 2>&1 | tail -1` → `804 passed`.

Statisch: `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/order_status_service.py app/api/v1/sales.py app/schemas/order.py` → keine Ausgabe, Exit 0.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/order_status_service.py backend/app/schemas/order.py backend/app/api/v1/sales.py backend/tests/test_paket4.py
git commit -m "feat(status): Gepackt und Ausgeliefert im Tagesplan bestätigen einen Entwurf bis zu seinem Liefertag im selben Schritt; POST /confirm über dieselbe Funktion (P4-A.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4 (A.4): Tagesplan meldet je Bestellung die möglichen Knöpfe (G10)

**Files:**
- Modify: `backend/app/api/v1/production.py` (Import, `get_day_plan._order_ref`)
- Modify: `backend/tests/test_paket4.py` (Block A.4 anhängen)

**Interfaces:**
- Produces: In `GET /production/day-plan` trägt jede Bestellung in `verpacken`, `verpacken_erledigt` und `ausliefern` zusätzlich `gepackt_moeglich: bool` und `ausgeliefert_moeglich: bool`. Für einen Entwurf mit Liefertag vor heute sind beide false. `packbar` bleibt unverändert.
- Consumes: `order_status_service.im_tagesplan_moeglich(order, ziel)` (A.3).

**Review Focus (A.4):** Der Import steht modulweit. Gemessen gibt es keinen Importzyklus: `production` → `order_status_service` → `order_fulfillment_service`/`invoice_service`. `packbar` bleibt für alte Tabs und für `test_packbar_nur_wenn_bestaetigt`.

- [ ] **Step 1: Testblock ans Dateiende anhängen** (beginnt mit zwei Leerzeilen):

```python


def _p4a_tagesplan(client, tag):
    r = client.get("/api/v1/production/day-plan", params={"target_date": tag.isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.usefixtures("_p4a_ohne_celery")
class TestP4ATagesplanKnoepfe:
    """A.4 (G10): Der Tagesplan erfährt vom Server, welche Knöpfe eine Zeile
    bekommt (gepackt_moeglich, ausgeliefert_moeglich) — dieselbe Regel wie
    setze_status_im_tagesplan. `packbar` bleibt wie in Paket 2."""

    def test_knoepfe_je_status(self, client):
        heute = _p4a_heute()
        # Same-Day: Pack- und Liefertag heute, die Zeile steht in beiden Karten
        entwurf = _p4a_bestellung(client, heute)
        bestaetigt = _p4a_bestellung(client, heute, bestaetigen=True)
        gepackt = _p4a_bestellung(client, heute, bestaetigen=True)
        geliefert = _p4a_bestellung(client, heute, bestaetigen=True)
        assert _p4a_status(client, gepackt, "IN_PRODUKTION").status_code == 200
        assert _p4a_status(client, geliefert, "GELIEFERT").status_code == 200

        plan = _p4a_tagesplan(client, heute)
        verpacken = {z["order_number"]: z for z in plan["verpacken"]}
        ausliefern = {z["order_number"]: z for z in plan["ausliefern"]}

        assert sorted(verpacken) == sorted([entwurf["order_number"], bestaetigt["order_number"]])
        for o in (entwurf, bestaetigt):
            assert verpacken[o["order_number"]]["gepackt_moeglich"] is True
        assert verpacken[entwurf["order_number"]]["packbar"] is False

        knoepfe = {
            nr: (z["gepackt_moeglich"], z["ausgeliefert_moeglich"]) for nr, z in ausliefern.items()
        }
        assert knoepfe == {
            entwurf["order_number"]: (True, True),
            bestaetigt["order_number"]: (True, True),
            gepackt["order_number"]: (False, True),
            geliefert["order_number"]: (False, False),
        }

    def test_erledigte_bekommen_keinen_knopf(self, client):
        heute = _p4a_heute()
        gepackt = _p4a_bestellung(client, heute + timedelta(days=1))
        assert _p4a_status(client, gepackt, "IN_PRODUKTION", entwurf_bestaetigen=True).status_code == 200

        zeile = _p4a_tagesplan(client, heute)["verpacken_erledigt"][0]
        assert (zeile["order_number"], zeile["gepackt_moeglich"]) == (gepackt["order_number"], False)

    def test_vergangener_entwurf_bekommt_keinen_knopf(self, client):
        """Tagesplan eines vergangenen Tages (Prod 09.10.2026: 7 Entwürfe mit
        Liefertag vor heute): ein Entwurf bekommt weder „Gepackt“ noch
        „Ausgeliefert“. Eine bestätigte Bestellung desselben Tages behält
        beide Knöpfe, ihre Lieferung lässt sich nachtragen (Paket 2)."""
        gestern = _p4a_heute() - timedelta(days=1)
        # Packtag = Liefertag (Same-Day-Regel beim Anlegen): beide stehen in
        # Verpacken und Ausliefern von gestern
        entwurf = _p4a_bestellung(client, gestern)
        bestaetigt = _p4a_bestellung(client, gestern, bestaetigen=True)

        plan = _p4a_tagesplan(client, gestern)
        knoepfe = {
            karte: {z["order_number"]: (z["gepackt_moeglich"], z["ausgeliefert_moeglich"]) for z in plan[karte]}
            for karte in ("verpacken", "ausliefern")
        }
        erwartet = {entwurf["order_number"]: (False, False), bestaetigt["order_number"]: (True, True)}
        assert knoepfe == {"verpacken": erwartet, "ausliefern": erwartet}
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4ATagesplanKnoepfe -q -p no:cacheprovider 2>&1 | tail -6` → `3 failed`, alle drei `KeyError: 'gepackt_moeglich'`.

- [ ] **Step 3: Implementierung.** In `backend/app/api/v1/production.py` den Import:

Anker (genau einmal):

```python
from app.services import growroom_capacity_service
from app.services.label_service import LabelService
```

ersetzen durch:

```python
from app.services import growroom_capacity_service
from app.services.label_service import LabelService
from app.services.order_status_service import im_tagesplan_moeglich
```

und in `get_day_plan`, Funktion `_order_ref`:

Anker (genau einmal):

```python
            "packbar": o.status == OrderStatus.BESTAETIGT,
```

ersetzen durch:

```python
            "packbar": o.status == OrderStatus.BESTAETIGT,
            # Paket 4 (G10): welche Knöpfe die Zeile bekommt. Ein Entwurf wird
            # beim Packen bzw. Ausliefern im selben Schritt bestätigt, aber nur
            # bis zu seinem Liefertag (order_status_service.setze_status_im_tagesplan).
            "gepackt_moeglich": im_tagesplan_moeglich(o, OrderStatus.IN_PRODUKTION),
            "ausgeliefert_moeglich": im_tagesplan_moeglich(o, OrderStatus.GELIEFERT),
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py -q -p no:cacheprovider 2>&1 | tail -1` → `18 passed`, falls die Datei nur Abschnitt A enthält. Enthält sie schon andere Abschnitte, gilt: `tests/test_paket4.py::TestP4AStueckliste tests/test_paket4.py::TestP4AEntwurfPacken tests/test_paket4.py::TestP4ATagesplanKnoepfe` → `18 passed`.

Umfeld: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_261008_paket2.py -q -p no:cacheprovider 2>&1 | tail -1` → `141 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/production.py backend/tests/test_paket4.py
git commit -m "feat(tagesplan): Server meldet je Bestellung, ob Gepackt und Ausgeliefert möglich sind, für Entwürfe bis zum Liefertag (P4-A.4)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5 (A.5): Tagesplan — „Gepackt“/„Ausgeliefert“ für Entwürfe, Umschalter „Sorten | Artikel“ (G10, G12)

**Files:**
- Modify: `frontend/src/pages/Tagesplan.tsx` (Importzeile aus `../services/api`, Typ `Statusklick`, Zustand `bedarfAnsicht`, `ausgeliefertMutation`, `gepacktMutation`, `statusWechsel`, Knöpfe Verpacken/Ausliefern, Karte Sortenbedarf)
- Modify: `frontend/src/services/api.ts` (`DayPlanOrder`, `salesApi.updateOrderStatus`)

**Interfaces:**
- Produces:
  - **`salesApi.updateOrderStatus(id, status, reason?, actualDeliveryDate?, entwurfBestaetigen?)`:** neuer optionaler fünfter Parameter. Die übrigen Aufrufer (Bestellliste, `Sales.tsx`, `EditOrderModal`) bleiben unverändert.
  - **`DayPlanOrder`:** neue Felder `gepackt_moeglich` und `ausgeliefert_moeglich`.
- Consumes: A.3 (`entwurf_bestaetigen`), A.4 (Felder).
- **Nicht angefasst (O.4):** die Importzeile aus `../services/orderQueries` bzw. `belegordner` und `packlisteMutation`.

**Review Focus (A.5):**
- Ein Entwurf zeigt „Gepackt“ (Tooltip „Entwurf — wird beim Packen bestätigt“). Der Toast lautet „BE-… bestätigt und als gepackt markiert“.
- Der Knopf bleibt gesperrt, bis der Tagesplan neu geladen ist (`onSettled` wie in Paket 2).
- „Ausgeliefert“ erscheint nur bis heute (`date <= today`), für Entwürfe nur am Liefertag heute. Die Regel liefert der Server über `ausgeliefert_moeglich`, der Tagesplan prüft kein Datum selbst.
- Ein Entwurf mit vergangenem Liefertag zeigt in Verpacken weiter „erst bestätigen“ (Tooltip „Liefertag vorbei — in der Bestellliste bestätigen oder stornieren“) und in Ausliefern nur das Badge.
- Der Umschalter zeigt in „Artikel“ je Verkaufsartikel die Menge, die Bestelleinheit nur bei einheitlicher Einheit (sonst „Einheiten gemischt: …“) und die Zahl der Bestellungen (verschiedene Bestellnummern, nicht Positionen). Die Zahl im Kartenkopf folgt der Ansicht.

- [ ] **Step 1: Tagesplan ändern** (`frontend/src/pages/Tagesplan.tsx`, zehn Ersetzungen, jede mit genau einem Treffer).

1) Importzeile aus `../services/api`:

Anker (genau einmal):

```tsx
import { productionApi, staffApi, documentsApi, salesApi } from '../services/api';
```

ersetzen durch:

```tsx
import { productionApi, staffApi, documentsApi, salesApi, type DayPlanOrder } from '../services/api';
```

2) Vor dem Kommentar über `export default function Tagesplan()`:

Anker (genau einmal):

```tsx
/**
 * Tagesplan für Mitarbeiter: was ist heute zu tun?
```

ersetzen durch:

```tsx
// Klick auf „Gepackt“ bzw. „Ausgeliefert“: welche Bestellung, und ob sie ein
// Entwurf war — der Server bestätigt ihn im selben Schritt (Paket 4, G10).
type Statusklick = { orderId: string; entwurf: boolean };

/**
 * Tagesplan für Mitarbeiter: was ist heute zu tun?
```

3) Zustand nach `offeneBestellung`:

Anker (genau einmal):

```tsx
  const [offeneBestellung, setOffeneBestellung] = useState<string | null>(null);
```

ersetzen durch:

```tsx
  const [offeneBestellung, setOffeneBestellung] = useState<string | null>(null);

  // Sortenbedarf: Sorten (Bundles aufgelöst, Hauptansicht) oder Artikel wie
  // bestellt (Bundle-Sicht, Gernot B1 / G12)
  const [bedarfAnsicht, setBedarfAnsicht] = useState<'sorten' | 'artikel'>('sorten');
```

4) `ausgeliefertMutation` (Anfang bis `onSuccess`):

Anker (genau einmal):

```tsx
  const ausgeliefertMutation = useMutation({
    mutationFn: (orderId: string) =>
      salesApi.updateOrderStatus(orderId, 'GELIEFERT', undefined, date < today ? date : undefined),
    onSuccess: async (order) => {
      await invalidateOrderViews(queryClient);
      toast.success(`${order.order_number ?? 'Bestellung'} ausgeliefert`);
    },
```

ersetzen durch:

```tsx
  const ausgeliefertMutation = useMutation({
    mutationFn: ({ orderId }: Statusklick) =>
      salesApi.updateOrderStatus(orderId, 'GELIEFERT', undefined, date < today ? date : undefined, true),
    onSuccess: async (order, { entwurf }) => {
      await invalidateOrderViews(queryClient);
      toast.success(`${order.order_number ?? 'Bestellung'} ${entwurf ? 'bestätigt und ' : ''}ausgeliefert`);
    },
```

5) `gepacktMutation` (Kommentar bis `onSuccess`):

Anker (genau einmal):

```tsx
  // "Gepackt" = BESTAETIGT → IN_PRODUKTION. Die Bestellung fällt danach aus
  // Verpacken und Sortenbedarf, bleibt aber unter Ausliefern (A4, 08.10.2026).
  const gepacktMutation = useMutation({
    mutationFn: (orderId: string) =>
      salesApi.updateOrderStatus(orderId, 'IN_PRODUKTION', 'Im Tagesplan als gepackt markiert'),
    onSuccess: (order) => toast.success(`${order.order_number ?? 'Bestellung'} als gepackt markiert`),
```

ersetzen durch:

```tsx
  // "Gepackt" = IN_PRODUKTION, ein Entwurf wird dabei bestätigt (Paket 4, G10).
  // Die Bestellung fällt danach aus Verpacken und Sortenbedarf, bleibt aber
  // unter Ausliefern (A4, 08.10.2026).
  const gepacktMutation = useMutation({
    mutationFn: ({ orderId }: Statusklick) =>
      salesApi.updateOrderStatus(orderId, 'IN_PRODUKTION', 'Im Tagesplan als gepackt markiert', undefined, true),
    onSuccess: (order, { entwurf }) =>
      toast.success(`${order.order_number ?? 'Bestellung'} ${entwurf ? 'bestätigt und ' : ''}als gepackt markiert`),
```

6) `statusWechsel`:

Anker (genau einmal):

```tsx
  const statusWechsel = (orderId: string, ziel: 'IN_PRODUKTION' | 'GELIEFERT') => {
    if (statuswechselLaeuft.current || (ziel === 'GELIEFERT' && date > today)) return;
    statuswechselLaeuft.current = true;
    const mutation = ziel === 'GELIEFERT' ? ausgeliefertMutation : gepacktMutation;
    mutation.mutate(orderId, {
```

ersetzen durch:

```tsx
  const statusWechsel = (o: DayPlanOrder, ziel: 'IN_PRODUKTION' | 'GELIEFERT') => {
    if (statuswechselLaeuft.current || (ziel === 'GELIEFERT' && date > today)) return;
    statuswechselLaeuft.current = true;
    const mutation = ziel === 'GELIEFERT' ? ausgeliefertMutation : gepacktMutation;
    mutation.mutate({ orderId: o.order_id, entwurf: o.status === 'ENTWURF' }, {
```

7) Knopf „Gepackt“ in der Karte Verpacken:

Anker (genau einmal):

```tsx
              {o.packbar ? (
                <Button
                  size="sm"
                  variant="success"
                  icon={<PackageCheck className="w-4 h-4" />}
                  loading={gepacktMutation.isPending && gepacktMutation.variables === o.order_id}
                  disabled={statuswechselPending}
                  onClick={(e) => {
                    e.stopPropagation();
                    statusWechsel(o.order_id, 'IN_PRODUKTION');
                  }}
                >
                  Gepackt
                </Button>
              ) : (
                <span className="text-xs text-gray-500 dark:text-gray-400">erst bestätigen</span>
              )}
```

ersetzen durch:

```tsx
              {/* Auch für Entwürfe: der Server bestätigt beim Packen (Paket 4, G10).
                  Einen Entwurf mit vergangenem Liefertag klärt das Büro. */}
              {o.gepackt_moeglich ? (
                <Button
                  size="sm"
                  variant="success"
                  icon={<PackageCheck className="w-4 h-4" />}
                  loading={gepacktMutation.isPending && gepacktMutation.variables?.orderId === o.order_id}
                  disabled={statuswechselPending}
                  title={o.status === 'ENTWURF' ? 'Entwurf — wird beim Packen bestätigt' : undefined}
                  onClick={(e) => {
                    e.stopPropagation();
                    statusWechsel(o, 'IN_PRODUKTION');
                  }}
                >
                  Gepackt
                </Button>
              ) : (
                <span
                  className="text-xs text-gray-500 dark:text-gray-400"
                  title="Liefertag vorbei — in der Bestellliste bestätigen oder stornieren"
                >
                  erst bestätigen
                </span>
              )}
```

8) Kommentar über den Zeilen der Karte Ausliefern:

Anker (genau einmal):

```tsx
      // Bestätigt und Gepackt bekommen den Knopf; Geliefert bleibt am Tag
      // sichtbar (Badge), ein Entwurf muss erst bestätigt werden.
```

ersetzen durch:

```tsx
      // Bestätigt und Gepackt bekommen den Knopf, ein Entwurf nur am Liefertag
      // heute (der Server bestätigt ihn dabei, Paket 4 / G10; Feld
      // ausgeliefert_moeglich). Geliefert bleibt am Tag sichtbar (Badge).
```

9) Knopf „Ausgeliefert“:

Anker (genau einmal):

```tsx
            {date <= today && (o.status === 'BESTAETIGT' || o.status === 'IN_PRODUKTION') && (
              <Button
                size="sm"
                variant="success"
                icon={<CheckCircle className="w-4 h-4" />}
                loading={ausgeliefertMutation.isPending && ausgeliefertMutation.variables === o.order_id}
                disabled={statuswechselPending}
                onClick={() => statusWechsel(o.order_id, 'GELIEFERT')}
              >
```

ersetzen durch:

```tsx
            {date <= today && o.ausgeliefert_moeglich && (
              <Button
                size="sm"
                variant="success"
                icon={<CheckCircle className="w-4 h-4" />}
                loading={ausgeliefertMutation.isPending && ausgeliefertMutation.variables?.orderId === o.order_id}
                disabled={statuswechselPending}
                title={o.status === 'ENTWURF' ? 'Entwurf — wird beim Ausliefern bestätigt' : undefined}
                onClick={() => statusWechsel(o, 'GELIEFERT')}
              >
```

10) Karte „Sortenbedarf zum Packen“ (Kopfbereich rechts und Inhalt):

Anker (genau einmal):

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
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {(packaging?.komponenten ?? []).map((k, i) => (
                <div key={i} className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <p className="font-medium text-gray-900 dark:text-white">{k.product_name}</p>
                  <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">
                    {Number(k.total_quantity).toLocaleString('de-DE')}
                  </p>
                  {k.aus_bundles.length > 0 && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">inkl. {k.aus_bundles.join(', ')}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
```

ersetzen durch:

```tsx
            <div className="flex items-center gap-2">
              {/* Gleiche Quelle wie die Liste "Bereits gepackt" in der Verpacken-Karte */}
              {(plan?.verpacken_erledigt ?? []).length > 0 && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ohne {plan?.verpacken_erledigt.length} bereits gepackte
                </span>
              )}
              {/* G12: Sorten (aufgelöst) oder Artikel wie bestellt (Bundles ganz) */}
              <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-xs">
                {(['sorten', 'artikel'] as const).map((ansicht) => (
                  <button
                    key={ansicht}
                    type="button"
                    className={`px-2 py-1 ${bedarfAnsicht === ansicht
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
                    aria-pressed={bedarfAnsicht === ansicht}
                    onClick={() => setBedarfAnsicht(ansicht)}
                  >
                    {ansicht === 'sorten' ? 'Sorten' : 'Artikel'}
                  </button>
                ))}
              </div>
              <Badge variant="info">
                {bedarfAnsicht === 'sorten' ? packaging?.komponenten.length : packaging?.items.length}
              </Badge>
            </div>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {bedarfAnsicht === 'sorten'
                ? (packaging?.komponenten ?? []).map((k, i) => (
                    <div key={i} className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                      <p className="font-medium text-gray-900 dark:text-white">{k.product_name}</p>
                      <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">
                        {Number(k.total_quantity).toLocaleString('de-DE')}
                      </p>
                      {k.aus_bundles.length > 0 && (
                        <p className="text-xs text-gray-500 dark:text-gray-400">inkl. {k.aus_bundles.join(', ')}</p>
                      )}
                    </div>
                  ))
                : (packaging?.items ?? []).map((a, i) => {
                    // Einheit nur, wenn alle Positionen dieselbe tragen (Prod:
                    // Kisten/STK/Stück für denselben Mix, A-E6). Gezählt werden
                    // Bestellungen, nicht Positionen.
                    const einheiten = Array.from(new Set<string>(a.orders.map((z: { unit: string }) => z.unit)));
                    const bestellungen = new Set<string>(a.orders.map((z: { order_number: string }) => z.order_number)).size;
                    return (
                      <div key={i} className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                        <p className="font-medium text-gray-900 dark:text-white">{a.product_name}</p>
                        <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">
                          {Number(a.total_quantity).toLocaleString('de-DE')}
                          {einheiten.length === 1 && (
                            <span className="text-sm font-normal text-gray-500 dark:text-gray-400"> {einheiten[0]}</span>
                          )}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {bestellungen} {bestellungen === 1 ? 'Bestellung' : 'Bestellungen'}
                          {einheiten.length > 1 && ` · Einheiten gemischt: ${einheiten.join(', ')}`}
                        </p>
                      </div>
                    );
                  })}
            </div>
          </div>
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`

Erwartet sind genau 4 Fehler, alle in `src/pages/Tagesplan.tsx`:
- 2 × `TS2554: Expected 2-4 arguments, but got 5.` (Aufrufe in `ausgeliefertMutation` und `gepacktMutation`)
- `TS2339: Property 'gepackt_moeglich' does not exist on type 'DayPlanOrder'.`
- `TS2339: Property 'ausgeliefert_moeglich' does not exist on type 'DayPlanOrder'.`

- [ ] **Step 3: Schnittstelle im Frontend.** In `frontend/src/services/api.ts`, `interface DayPlanOrder`:

Anker (genau einmal):

```ts
  // Knopf "Gepackt" möglich (BESTAETIGT → IN_PRODUKTION); ein Entwurf muss erst bestätigt werden
  packbar: boolean
}
```

ersetzen durch:

```ts
  // Direkter Übergang BESTAETIGT → IN_PRODUKTION möglich (Paket 2; die Oberfläche nutzt gepackt_moeglich)
  packbar: boolean
  // Knöpfe im Tagesplan (Paket 4, G10) — der Server entscheidet; ein Entwurf
  // wird beim Packen bzw. Ausliefern im selben Schritt bestätigt
  gepackt_moeglich: boolean
  ausgeliefert_moeglich: boolean
}
```

in `salesApi`:

Anker (genau einmal):

```ts
  // actualDeliveryDate nur bei GELIEFERT: tatsächlicher Liefertag (Standard heute)
  updateOrderStatus: (id: string, status: OrderStatus, reason?: string, actualDeliveryDate?: string) =>
    api.post<Order>(`/sales/orders/${id}/status`, {
      status, reason, actual_delivery_date: actualDeliveryDate,
    }).then(r => r.data),
```

ersetzen durch:

```ts
  // actualDeliveryDate nur bei GELIEFERT: tatsächlicher Liefertag (Standard heute).
  // entwurfBestaetigen nur aus dem Tagesplan: ein Entwurf wird vor Gepackt bzw.
  // Geliefert im selben Schritt bestätigt (Paket 4, G10).
  updateOrderStatus: (id: string, status: OrderStatus, reason?: string, actualDeliveryDate?: string,
    entwurfBestaetigen?: boolean) =>
    api.post<Order>(`/sales/orders/${id}/status`, {
      status, reason, actual_delivery_date: actualDeliveryDate, entwurf_bestaetigen: entwurfBestaetigen,
    }).then(r => r.data),
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe. Run: `cd frontend && npm run build` → endet mit `✓ built in …`. Die Warnung „Some chunks are larger than 500 kB“ ist Altbestand.

Prüfen:
- `grep -c "erst bestätigen" frontend/src/pages/Tagesplan.tsx` → `1` (der Hinweis bleibt für Entwürfe mit vergangenem Liefertag)
- `grep -c "gepackt_moeglich\|ausgeliefert_moeglich" frontend/src/pages/Tagesplan.tsx` → `3` (Bedingung „Gepackt“, Kommentar über Ausliefern, Bedingung „Ausgeliefert“)
- `grep -c "updateOrderStatus(" frontend/src/pages/Tagesplan.tsx` → `2`
- `grep -c "belegHerunterladen" frontend/src/pages/Tagesplan.tsx` → wie vor A.5. Nach O ist das `2`, Import und Aufruf bleiben unberührt.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Tagesplan.tsx frontend/src/services/api.ts
git commit -m "feat(tagesplan): Gepackt und Ausgeliefert auch für Entwürfe bis zum Liefertag, Umschalter Sorten/Artikel im Sortenbedarf (P4-A.5)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6 (A.6): Abschluss A — Prüfungen und Meldung (ohne Commit)

- [ ] **Step 1:** Prozedur V → `14 failed, N passed, 2 skipped, 1 error`, Abgleich leer. N im Gesamtplan errechnet 1836 (Basis 1818 + 18; einzeln gemessen auf dem D/F/O-Stand `bd56901`: 1709 → 1727).
- [ ] **Step 2:** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/products.py app/api/v1/sales.py app/api/v1/production.py app/services/order_status_service.py app/schemas/order.py tests/test_paket4.py` → keine Ausgabe, Exit 0.
- [ ] **Step 3:** `git diff --stat <Basis-A>..HEAD` → genau 9 Dateien: `backend/app/api/v1/production.py`, `backend/app/api/v1/products.py`, `backend/app/api/v1/sales.py`, `backend/app/schemas/order.py`, `backend/app/services/order_status_service.py`, `backend/tests/test_paket4.py`, `frontend/src/pages/Products.tsx`, `frontend/src/pages/Tagesplan.tsx`, `frontend/src/services/api.ts`. `git log --oneline <Basis-A>..HEAD` → 5 Commits (A.1–A.5).
- [ ] **Step 4: Abschlussmeldung A**: `<Basis-A>`, die 5 Commit-Hashes, die Summenzeile aus Prozedur V, ggf. selbst behobene Ankerfehler.

---

## Abschnitt B — Abrechnung: Schutz vor Doppelabrechnung, Lieferschein beim Ausliefern, Rechnungsdatum, Positionen bearbeiten, Suche — Tasks 7–13 (B.1–B.7)

> **Rahmen:** Arbeitsort, Tests, Commits, Stoppregeln, Baseline und Prozedur V stehen im Kopf des Plans (Global Constraints). B.1–B.7 = Tasks 7–13. Ausnahme von „Bestehende Tests ändert kein Task“: B.2 Step 5 (= Task 8, Step 5; B-E3). Die Abschlussmeldung in Task 13 ist ein Zwischenstand — nicht anhalten. Runbooks R-B1–R-B3 und die Offenen Punkte von B stehen am Ende des Plans.

**Goal:** Sechs Punkte aus Gernots Rückmeldungen (Feedback 08.10., Nachtrag 08.10. B5, Kommentare 09.10.; Abgleich `/tmp/p4/abgleich.json`):
- **G66 — Doppelabrechnung.** Gernot: „Die Rechnungen bis 07.10.2026 sind über DATEV ausgestellt und bereits abgerechnet.“ 574 Bestellungen stehen seit 09.10. auf `FAKTURIERT`. Sammel- und Monatslauf schließen sie aus, „Rechnung aus Bestellung“ (`InvoiceService.create_invoice_from_order`) prüft nur `STORNIERT` — jede der 574 ließ sich einzeln noch einmal berechnen. Danach sperrt `FAKTURIERT` jeden Weg zur Rechnung mit klarer Meldung (409).
- **G31 / X07 — Monatslauf ohne Lieferschein.** Gernot: „Wird die dann automatisch erstellt und vorgeschlagen am Monatsende?“ Der Monatslauf rechnet nur Lieferscheine ab; der Tagesplan-Knopf „Ausgeliefert“ legt keinen an. Prod: `BE-20261008-0002` (Abo Dorint) ist `GELIEFERT` ohne Lieferschein; die Monatskunden `KD-10012` und `KD-10022` haben Wochen-Abos. Danach legt jeder Wechsel auf `GELIEFERT` den fehlenden Lieferschein an (Entscheidung B-E2).
  - **Grenze von B, Abo-Entwürfe (G31 mit Paket-4-Abschnitt A, G10):** Der Abo-Lauf legt Bestellungen als `ENTWURF` an (`subscription_tasks`). Für einen Entwurf zeigt der Tagesplan keinen Knopf „Ausgeliefert“ (`Tagesplan.tsx`, Karte „Ausliefern“: nur `BESTAETIGT`/`IN_PRODUKTION`), und `setze_status` erlaubt `ENTWURF → GELIEFERT` nicht. Prod 09.10.: `KD-10022` hat 4 Bestellungen seit 14.09., alle `ENTWURF`, ohne Lieferschein; `KD-10012` hat seit 01.09. keine Bestellung. Diesen Weg schließt **Abschnitt A (A.3–A.5, G10)**: „Ausgeliefert“ bestätigt den Entwurf im selben Schritt (`setze_status_im_tagesplan` → `bestaetigen` + `setze_status`), und B.3 legt dort den Lieferschein mit an (gemessen, siehe Prüfstand). Die Anker kollidieren nicht: A fügt vor `def trage_lieferdatum_nach(` ein, B ändert die Importzeile aus `order_fulfillment_service` und den `GELIEFERT`-Block in `setze_status`. Ohne A muss jede Abo-Bestellung erst in der Bestellliste bestätigt werden; geschieht das nicht, bleibt die Monatsrechnung am 01.11. für diese Kunden leer (nur Hinweis `OHNE_LIEFERSCHEIN`).
  - **Grenze von B, Altfall X07:** `BE-20261008-0002` (Dorint, Einzelkunde, `GELIEFERT` seit 08.10., ohne Lieferschein, unberechnet) bleibt nach B unsichtbar: B.3 wirkt nur auf künftige Wechsel nach `GELIEFERT`, `EINZELABRECHNUNG` im Monatsdialog braucht einen Lieferschein, `OHNE_LIEFERSCHEIN` gilt nur für Monatskunden. Sichtbar wird er erst auf der Seite „Belegstatus“ aus **Abschnitt C** (C.3, Lücke `OHNE_RECHNUNG`, Anzeige „Rechnung fehlt“). Gernot berechnet ihn per „Rechnung aus Bestellung“ im Belegdialog (geht ohne Lieferschein); der Manager sagt es ihm (R-B2, Offener Punkt 7).
- **G64 (Datumsbefund) — Rechnungsdatum beim Festschreiben.** `InvoiceService.festschreiben` setzte das Datum nur bei Entwürfen mit Platzhalter; `RE-2026-00003` (Altentwurf mit echter Nummer) wurde am 09.10. mit Datum 07.10. festgeschrieben — vor der Lieferung vom 08.10. Danach ist das Rechnungsdatum immer der Tag des Festschreibens (Europe/Berlin), das Zahlungsziel in Tagen bleibt.
- **G21 — Positionen im Entwurf bearbeiten.** Gernot: „Entwurf prüfen – Positionen editierbar (Menge, Preis, Position löschen, z. B. Pfandkisten entfernen).“ Löschen und Hinzufügen gibt es, Menge und Preis nicht (`invoicesApi.updateLine` wird nirgends aufgerufen). Danach: „Ändern“ je Position im Entwurf, Menge und Einzelpreis direkt in der Tabelle. In Sammel- und Monatsrechnungen ist die Menge einer Position an ihre Lieferscheine gebunden: Der Server lehnt eine Mengenänderung dort mit 409 und dem Korrekturweg ab, der Preis bleibt änderbar (Entscheidung B-E6).
- **G05 — Suche.** Gernot: „Suche ‚nach Nummer oder Kunde‘ funktioniert.“ Sie wirkte nur im Reiter „Alle“. Danach in jedem Reiter, Wörter beliebig kombiniert, auch über die Kundennummer.

**Architecture:** Keine Schemaänderung, keine Migration (`tenancy._auto_migrate` unberührt), kein neuer Endpunkt. Backend: `BestellungFakturiert` (Unterklasse von `BereitsAbgerechnet`, also überall 409) an vier Stellen in `invoice_service` plus ein `except` in `POST /invoices/{id}/lines`; ein Datumsblock in `festschreiben`; eine Mengensperre für Positionen mit Herkunft je Lieferschein (`invoice_line_sources`) in `PATCH /invoices/{id}/lines/{line_id}` (409); neues Modul `app.services.lieferschein_service` (die Lieferschein-Anlage aus `documents.create_delivery_note`, unverändert herausgezogen, plus `lieferschein_beim_ausliefern`), aufgerufen in `order_status_service.setze_status` beim Wechsel auf `GELIEFERT`. Frontend: Belegdialog (`OrderDocumentsModal`), `InvoiceDetail` und Rechnungsliste in `Invoices.tsx`; zwei reine Funktionen ohne Importe mit Node-Prüfung (`positionsaenderung.ts`, `rechnungssuche.ts`).

**Ausgangsstand:** `main` @ `df84f7b`. Ausgeführt wird B **nach** dem Merge von D/F/O (Branch `feat/nachtrag-0910`). Jeder Anker von B ist auf `df84f7b` und auf dem D/F/O-Stand (`feat/nachtrag-0910` @ `bd56901`, alle 14 Commits, und @ `1bfa032`, dazu drei Nachbesserungen D/F) identisch vorhanden — gemessen, siehe „Prüfstand“. Kein Schritt von B setzt D/F/O voraus.

### Befunde (am Code geprüft, Produktion am 09.10.2026 nur lesend)

- **G66:** Prod: 574 `FAKTURIERT` (keine davon mit NovaERP-Rechnung, keine mit Lieferschein), 8 `GELIEFERT`, 3 `BESTAETIGT`, 11 `ENTWURF`, 2 `STORNIERT`. Wege zur Rechnung mit Bestellbezug: (1) `POST /invoices/from-order/{id}` → `create_invoice_from_order` → `create_invoice(order_id=…)`; (2) `POST /invoices` mit `order_id` → `create_invoice`; (3) `POST /invoices` bzw. `POST /invoices/{id}/lines` mit `order_item_id` → `add_line` (keine Oberfläche, nur API); (4) Sammellauf und Monatslauf über `_abrechenbare_lieferscheine` — schließen `FAKTURIERT` schon aus; (5) Festschreiben eines Entwurfs, der älter ist als die Kennzeichnung (`pruefe_festschreibung`). (1)–(3) und (5) waren offen. NovaERP setzt `FAKTURIERT` nie selbst: keine Rechnung ändert den Bestellstatus, die Oberfläche bietet den Status nicht an (`Orders.tsx` kennt nur Gepackt/Geliefert); er kommt aus dem Excel-Import oder der Sammelaktion per API und ist endgültig (`ERLAUBTE_UEBERGAENGE[FAKTURIERT] = ()`).
- **G31 / X07:** Wege nach `GELIEFERT` laufen alle über `order_status_service.setze_status`: Tagesplan „Ausgeliefert“ und Bestellliste „Geliefert“ (`POST /sales/orders/{id}/status`), Sammelaktion (`POST /sales/orders/bulk-status`), Lieferschein quittieren (`PATCH /sales/delivery-notes/{id}/mark-delivered`). Einen Lieferschein legen nur „Neuer LS“ im Belegdialog und die Packliste im Tagesplan an. Prod: `GELIEFERT` ohne Lieferschein: `BE-20261007-0008` (KD-10033, Einzelkunde, schon berechnet mit RE-2026-00005) und `BE-20261008-0002` (KD-10010 Dorint, Einzelkunde, unberechnet). Aktive Abos: KD-10010 (EINZELN), KD-10012 und KD-10022 (beide MONATLICH, wöchentlich montags). Der Abo-Lauf legt Bestellungen als `ENTWURF` an (`subscription_tasks`); die vier LfA-Bestellungen (KD-10022, 14.09.–05.10.) stehen bis heute auf `ENTWURF`, KD-10012 hat seit 01.09. keine Bestellung. Für Entwürfe zeigt der Tagesplan kein „Ausgeliefert“ (nur `BESTAETIGT`/`IN_PRODUKTION`), `ERLAUBTE_UEBERGAENGE[ENTWURF]` ist `(BESTAETIGT, STORNIERT)` — B.3 erreicht Abo-Lieferungen also erst mit Abschnitt A (G10) oder nach „Bestätigen“ in der Bestellliste. Lieferscheine in Prod: 10 `ENTWURF` (2 berechnet), 1 `GELIEFERT` — der übliche Lieferschein ist ein Entwurf aus der Packliste.
- **G64:** Prod: `RE-2026-00003` ist inzwischen storniert (Stornorechnung `RE-2026-00009`) und als `RE-2026-00010` mit Rechnungsdatum 09.10. neu ausgestellt (Vermerk „systemkorrektur“, 09.10. 17:01). Rechnungsentwürfe in Prod: 0, Entwürfe mit echter Nummer: 0. Der Fix ist vorbeugend (Altentwürfe aus Sicherungen, Demo, anderen Mandanten).
- **G21:** `PATCH /invoices/{id}/lines/{line_id}` (`InvoiceLineUpdate`: Menge > 0, Preis ≥ 0, rechnet Zeile und Summen neu, nur Entwurf, sonst 400; Leergutbeleg 409) ist live; `InvoiceDetail` (auch im Belegdialog eingebettet) zeigt Menge und Preis nur an. Spalten: Menge `Numeric(10, 3)`, Einzelpreis `Numeric(10, 4)`. **Sammel- und Monatsrechnung:** `_aggregiere` fasst je (Artikel, Einheit, Preis, Satz, Produkt, Rabatt) die Lieferungen zu **einer** Position zusammen und schreibt je Lieferschein `invoice_line_sources.quantity`; `netto_je_lieferschein` rechnet für die Anlage „Enthaltene Lieferscheine“ (PDF, nur bei `invoice.order_id is None`) und `GET /invoices/{id}/delivery-notes` Quellmenge × Einzelpreis der Position. `PATCH …/lines/{id}` schreibt heute nur `InvoiceLine.quantity` um — gemessen (Monatskunde, 2 Lieferungen à 10 × 2,50 €, Monatslauf, Menge 20 → 15): Rechnung netto 37,50 €, Anlage 25,00 + 25,00 = 50,00 €. Die Bestellung lässt sich ändern, sobald der Entwurf verworfen ist (`_pruefe_bestellung_nicht_berechnet` antwortet sonst 409 „erst … den Entwurf verwerfen“). Prod 09.10.: kein Rechnungsentwurf mit Quellen; der erste Monatsentwurf entsteht am 01.11.
- **G05:** `displayInvoices` nahm für „Offen“, „Überfällig“, „Bezahlt“ ungefilterte Listen. Kundenname-Suche funktioniert (`customer_name` gefüllt); `customer_number` liefert die API mit, die Suche nutzte sie nicht. Gesucht wird nur in den geladenen 100 neuesten Rechnungen (Hinweis auf der Seite vorhanden).

### Entscheidungen (Manager, im Plan getroffen)

- **B-E1 — `FAKTURIERT` sperrt jede Rechnung zur Bestellung, auch das Festschreiben eines älteren Entwurfs.** Neue Ausnahme `BestellungFakturiert(BereitsAbgerechnet)`: Alle Handler, die `BereitsAbgerechnet` schon mit 409 beantworten (`POST /invoices`, `/from-order`, `/finalize`, `/send`), tun es ohne Änderung; nur `POST /invoices/{id}/lines` bekommt ein `except`. Geprüft wird in `create_invoice` (deckt Wege 1 und 2), zusätzlich vorn in `create_invoice_from_order` (sonst käme bei einer reinen Pfandbestellung die irreführende Meldung „nichts zu fakturieren“), in `add_line` für `order_item_id` (Weg 3) und in `pruefe_festschreibung` (Weg 5, Meldung mit „Diesen Entwurf verwerfen.“). Keine Falle für Korrekturen: Storno und Neuausstellung einer NovaERP-Rechnung berühren den Bestellstatus nicht, und `FAKTURIERT` ist in der Oberfläche nicht wählbar. Meldung: „Bestellung <Nr> ist als „Fakturiert“ gekennzeichnet: Sie ist außerhalb von NovaERP abgerechnet (z. B. über DATEV). Eine Rechnung hier würde sie doppelt berechnen.“ Der Belegdialog bietet den Knopf gar nicht erst an (B.4).
- **B-E2 — Lieferschein beim Ausliefern, nicht „Monatslauf ohne Lieferschein“.** Jeder Wechsel auf `GELIEFERT` legt einen Lieferschein an, wenn die Bestellung keinen hat (`setze_status` → `lieferschein_beim_ausliefern`). Begründung:
  (a) **Eine Regel statt zwei (Paket-3-Logik).** Sammel- und Monatslauf, Doppelabrechnungsschutz (`delivery_notes.invoice_id`, `abgerechnete_bestellungen`), Freigabe bei Storno und Verwerfen, Herkunft je Position (`invoice_line_sources.delivery_note_id`), die PDF-Tabelle „Enthaltene Lieferscheine“ und `netto_je_lieferschein` hängen am Lieferschein. Ein Monatslauf, der Bestellungen ohne Lieferschein direkt aufnimmt, bräuchte für Sammelrechnungen über mehrere Bestellungen eine zweite Verknüpfung Rechnung↔Bestellung (neue Spalte oder Wiederbelebung des ungenutzten `orders.invoice_id`) und an allen genannten Stellen einen zweiten Zweig — verworfen.
  (b) **GoBD / UStG.** Die Sammelrechnung weist heute je Lieferung Lieferschein und Lieferdatum aus („Enthaltene Lieferscheine“). Der Leistungszeitpunkt (§ 14 Abs. 4 Nr. 6 UStG; der Kalendermonat genügt nach § 31 Abs. 4 UStDV) wäre auch ohne Lieferschein angebbar — aber verweist eine Rechnung auf Lieferscheine, gehören diese zur Rechnung (§ 31 Abs. 1 UStDV) und sind aufzubewahren. Mit B.3 hat jede abgerechnete Lieferung denselben Beleg in NovaERP (PDF reproduzierbar); eine Monatsrechnung, in der ein Teil der Lieferungen mit und ein Teil ohne Lieferschein stünde, wäre für den Prüfer nicht einheitlich nachvollziehbar (GoBD: Nachvollziehbarkeit, Belegfunktion).
  (c) **Gernot liefert nicht in Teilen.** Der Lieferschein 1:1 aus der Bestellung (dieselbe Anlage wie „Neuer LS“) ist richtig; ein vorhandener Lieferschein (Packliste) bleibt der einzige.
  (d) **Status `ENTWURF`, nicht `GELIEFERT`.** `GELIEFERT` heißt beim Lieferschein „vom Empfänger quittiert“ (gesperrt, Unterschrift). Der Klick „Ausgeliefert“ ist keine Quittung; der Lieferschein gleicht dem aus der Packliste (in Prod der Normalfall) und kann später quittiert werden. Der Monatsdialog meldet ihn wahrheitsgemäß unter `NICHT_QUITTIERT`. Er trägt den Liefertag der Bestellung (`actual_delivery_date`), **keinen** Vermerk — `notes` druckt das Lieferschein-PDF.
  (e) **An einer Stelle für alle Wege** (Tagesplan, Bestellliste, Sammelaktion, Quittieren), in derselben Transaktion wie Status und Bestandsabzug. Ein Import mit Status `GELIEFERT` (Altbestand, heute `FAKTURIERT`) läuft nicht über `setze_status` und bleibt ohne Lieferschein.
  (f) Die Anlage wird aus `documents.create_delivery_note` **unverändert** in `lieferschein_service.lieferschein_anlegen` verschoben (dieselben Nummern `LS-`/`PL-` mit `date.today()`, dieselben Packlistenzeilen); der Endpunkt prüft weiter Positionen und vorhandene Lieferscheine (409) selbst.
- **B-E3 — Rechnungsdatum = Tag des Festschreibens, immer.** Ein Altentwurf behält nur seine Nummer. Das Zahlungsziel in Tagen (Fälligkeit − Entwurfsdatum) bleibt wie bisher. Folge: Zwei Bestandstests hielten das alte Verhalten fest und werden angepasst — `test_gernot_261008_paket3.py::TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum` (prüfte „behält Datum“; neu `test_altentwurf_behaelt_re_nummer`, prüft Nummer und heutiges Datum) und `test_dunning.py::test_dunning_email_sending` (nutzte die vorab gesetzte Nummer, damit das Datum von vor 18 Tagen stehen bleibt; setzt die Daten jetzt nach dem Festschreiben, wie schon den Status). Das ist die einzige Änderung an Bestandstests in B. Hinweis im Entwurf unter „Rechnungsdatum“: „Beim Finalisieren gilt der Tag der Ausstellung; das Zahlungsziel in Tagen bleibt.“ Ein Altentwurf `RE-2026-…`, der erst 2027 festgeschrieben würde, trüge Datum 2027 mit Nummer 2026 — in Prod gibt es keinen (Befund), daher keine Sonderregel.
- **B-E4 — Positionen bearbeiten: Menge und Einzelpreis, in der Zeile.** „Ändern“ öffnet zwei Textfelder (Komma oder Punkt, `inputMode="decimal"`), „Speichern“/Enter schickt nur geänderte Felder, „Abbrechen“/Escape verwirft nur die Zeile — Escape stoppt im Feld die Weitergabe (`e.stopPropagation()`), sonst schlösse der `keydown`-Listener von `Modal.tsx` auf `document` (`closeOnEscape` standardmäßig an) den ganzen Rechnungs- bzw. Belegdialog; immer eine Zeile zugleich. Prüfung vor dem Senden nach Spaltengenauigkeit (Menge > 0, höchstens 3 Nachkommastellen; Preis ≥ 0, höchstens 4); Tausenderpunkte werden abgelehnt statt geraten: `1.000,00` und das mehrdeutige Muster `1.000`/`12.500` (1–3 Ziffern ohne führende 0, Punkt, genau 3 Ziffern) gelten als ungültig (auch `10.000`; das Feld füllt `eingabeAusZahl` mit `10`); `0,125`, `0.125`, `3.10`, `1,000`, `999.5` und als Preis `1.2345` bleiben gültig (gemessen). Prod 09.10.: Bestellpositionen Menge höchstens 324, Einzelpreis höchstens 28,56 €; Rechnungspositionen 156 bzw. 23,76 €. Steuersatz und Rabatt bleiben ohne Oberfläche (Gernot fragte nach Menge, Preis, Löschen; die API kann beides). Festgeschriebene Rechnungen: keine Knöpfe (`isDraft`), der Server lehnt weiter mit 400 ab; Leergutbelege bleiben nur lesbar (409).
- **B-E5 — Suche in jedem Reiter, im Browser.** Jedes Wort muss in Rechnungsnummer, Kundenname oder Kundennummer vorkommen; Groß-/Kleinschreibung egal. Die Zähler der Reiter folgen der Suche, Suche und Reiterwechsel springen auf Seite 1 (ohne `useEffect` — die Paket-3-Abnahme rendert `Invoices.tsx` mit einem Ersatz, der nur `useState` kennt). Keine Serversuche (Offener Punkt 4).
- **B-E6 — In Sammel- und Monatsrechnungen bleibt die Menge an die Lieferscheine gebunden.** `PATCH /invoices/{id}/lines/{line_id}` lehnt eine **Mengenänderung** an einer Position mit `invoice_line_sources` mit 409 ab: „Die Menge stammt aus den Lieferscheinen dieser Sammel- bzw. Monatsrechnung. Entwurf verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten.“ Begründung: (a) B-E2(b) — die Anlage „Enthaltene Lieferscheine“ gehört zur Rechnung (§ 31 Abs. 1 UStDV) und muss zu ihr passen; (b) eine Sammelposition fasst mehrere Lieferscheine zusammen, welcher davon weniger hatte, weiß nur die Bestellung — eine Verteilung wäre geraten; (c) der Monatsdialog sagt schon heute unter `NICHT_QUITTIERT` „Minder- oder Teillieferungen vor dem Freigeben in der Bestellung korrigieren“. Reihenfolge der Meldung wie gemessen: Solange der Entwurf besteht, lehnt die Bestellung Änderungen mit 409 ab. Unverändert änderbar: Einzelpreis, Rabatt, Steuersatz, Text (die Anlage rechnet mit Preis und Rabatt der Position), Löschen der Position (`netto_je_lieferschein` liest Quellen nur über vorhandene Positionen der Rechnung), und jede Position einer Rechnung aus Bestellung (ohne Quellen; ihre Anlage rechnet aus den Positionen). Eine unverändert mitgeschickte Menge ist keine Änderung. Verworfen: genau eine Quelle mitführen — bei mehreren Quellen (der Normalfall im Monat) nicht eindeutig. Die Oberfläche zeigt den Servertext als Toast; die Zeile bleibt in Arbeit.

### Überschneidungen mit D/F/O

Gemessen: alle Anker von B auf `df84f7b` und auf `feat/nachtrag-0910` @ `bd56901` (D.1–D.5, F.1–F.4, O.1–O.5) und @ `1bfa032` (dazu `fcbb50e`, `60710b1`, `1bfa032`: Nachbesserungen F und D) je genau einmal; B auf den Ständen aus dem Plantext nachgespielt (Prüfstand). Kein B-Schritt ändert eine Zeile, die D/F/O ändern. Auf `1bfa032` steht in `update_invoice_line` zwischen `satz_vorher = line.tax_rate` und der Feldschleife ein neuer `buchungskonto`-Block (D, nicht in `/tmp/n0910/plan.md`); B.5's Anker endet mit `satz_vorher = line.tax_rate` und bleibt davon unberührt.

| Datei | B (Task: Anker) | D/F/O (Task: Stelle) | Ergebnis |
|---|---|---|---|
| `backend/app/services/invoice_service.py` | B.1: Klasse `BereitsAbgerechnet`; `create_invoice` (Block `if order_id is not None and invoice_type == InvoiceType.RECHNUNG:`); `create_invoice_from_order` (`STORNIERT`-Prüfung); `add_line` (Entwurfsprüfung bis `# Position ermitteln`); `pruefe_festschreibung` (`with_for_update`). B.2: `festschreiben` (Docstring Punkt 2, Block `braucht_nummer`) | D.2: Importzeile `from app.services.datev_service import erloeskonto_fuer` → `kontenrahmen`; `add_line` Block ab `# Buchungskonto basierend auf Steuersatz` | getrennt; B's `add_line`-Anker endet vor D's Block |
| `backend/app/api/v1/invoices.py` | B.1: `add_invoice_line` (`try`-Block bis `except ValueError as e:`). B.5: `update_invoice_line`, **vor** der Feldschleife (Block von `line = db.get(InvoiceLine, line_id)` bis `satz_vorher = line.tax_rate`) | D.2: Importzeilen, `update_invoice_line` **nach** der Feldschleife (Block ab „# Das Erlöskonto hängt am Steuersatz“); D.3: `export_datev`, `download_datev_export`; D.4: neuer Endpunkt | getrennt; B.5's Anker endet vor der Feldschleife, D.2's beginnt danach |
| `frontend/src/pages/Invoices.tsx` | B.5: Importzeile `getErrorMessage` (danach einfügen), `InvoiceDetail` (`deleteLineMutation`, Eingabe Rechnungsdatum, Positionstabelle). B.6: Importzeile `getErrorMessage`, `filteredInvoices`, `tabs`/`displayInvoices`, `<Tabs …/>`, Suchfeld | D.5: `DatevExportForm`. O.5: Importzeilen `dateinameAusHeader`/`ladePdfHerunter` (direkt über `getErrorMessage`), PDF-Knopf und Mahnung der Tabelle, `handleExport` | getrennt; B fügt **nach** der `getErrorMessage`-Zeile ein, die O stehen lässt |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | B.4: `rechnungMoeglich`, Text „Noch keine Rechnung …“ | O.4: Importzeile `dateinameAusHeader`, `downloadInvoicePdf`, Knöpfe AB/LS-PDF/Packliste | getrennt |
| `backend/tests/test_gernot_261008_paket3.py` | B.2: `TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum` | O, Stoppregel 4: führt `TestAbnahmeSepaBerlin`, `TestAbnahmeRechnungsberechtigung` aus (unverändert) | getrennt; beide Abnahmen nach B grün (`5 passed`, beide Stände) |
| `backend/tests/test_paket4.py` | B.1–B.3 und B.5 hängen an | — (D/F/O nutzen `test_nachtrag_0910.py`) | — |
| `backend/app/api/v1/documents.py` | B.3: Importe, `_next_document_number`, `create_delivery_note` | O-Plan, „Bewusst nicht enthalten“: „AB-, LS- und PL-Nummern tragen das Serverdatum (`date.today()` in `documents.py`)“ | B verschiebt die Nummernregel unverändert nach `lieferschein_service.naechste_belegnummer` (weiter `date.today()`); O's Aussage bleibt inhaltlich richtig, nur der Ort ist neu |
| `frontend/src/pages/Tagesplan.tsx` | — (B ändert ihn nicht) | O.4: `packlisteMutation` (`belegHerunterladen`) | Packliste nach „Ausgeliefert“ findet den neuen Lieferschein (`notes[0]`); nichts zu ändern |

Nicht von B berührt (geprüft): `api.ts` (`invoicesApi.updateLine` existiert), `Settings.tsx`, `SepaEinzugsliste.tsx`, `datev_service.py`, `kontenrahmen.py`, `schemas/*`, `tenancy.py`, `main.py`, `types/index.ts`, `test_nachtrag_0910.py`. Mit D.2 zieht `PATCH …/lines/{id}` bei Satzwechsel das Konto des Rahmens nach — B.5 schickt nie `tax_rate`, und B.5's Mengensperre (409) steht vor der Feldschleife; ein Satzwechsel ohne Mengenänderung läuft unverändert in D.2's Block, also keine Wechselwirkung.

**Zusammenspiel mit Paket-4-Abschnitt A (nicht D/F/O):** A.3 fügt in `order_status_service.py` vor `def trage_lieferdatum_nach(` ein (`MIT_BESTAETIGUNG`, `bestaetigen`, `im_tagesplan_moeglich`, `setze_status_im_tagesplan`); B.3 ändert dort nur die Importzeile aus `order_fulfillment_service` und den `GELIEFERT`-Block in `setze_status`. `setze_status_im_tagesplan` ruft `setze_status` — „Ausgeliefert“ für einen Abo-Entwurf legt nach A + B den Lieferschein an (gemessen, Prüfstand). Reihenfolge A/B beliebig.

### Prüfstand (alles in Kopien unter `/tmp`, Repo und Produktion unverändert)

- **Entwicklung** (Stand vor der Review-Überarbeitung: B.5 ohne Mengensperre, Node-Prüfung 18 Fälle) in `/tmp/p4-kopie-B` (`git archive df84f7b`), Task für Task: Baseline Prozedur V `14 failed, 1644 passed, 2 skipped, 1 error`, Namen = Baseline. B.1 Rot `4 failed, 2 passed` → `6 passed`, V `1650`; B.2 Rot `2 failed, 1 passed` → `3 passed`, Bestandstests `2 failed, 9 passed` → `11 passed`, V `1653` (ohne die Anpassung: `16 failed, 1651 passed` mit genau den zwei Namen); B.3 Rot `6 failed, 2 passed` → `8 passed`, V `1661`; Node-Prüfungen `ERR_MODULE_NOT_FOUND` → `18 Fälle ok` / `14 Fälle ok`; `tsc` sauber, Build `✓ built`; Paket-3-Abnahme `5 passed`; im geteilten `node_modules` danach nichts Neueres.
- **Nachspiel aus dem Plantext, Stand vor der Review-Überarbeitung** (Skript `/tmp/p4b-skripte/nachspiel.py` zerlegt diese Datei, wendet die 38 Blöcke — 29 Ersetzungen, Kopf, 3 Testblöcke, 5 neue Dateien — mechanisch mit ihren Ankern an, jeder Anker genau einmal gefunden, und führt die Prüfbefehle der Steps aus; Protokolle `/tmp/p4b-nachspiel-df84.log`, `/tmp/p4b-nachspiel-dfo.log`):
  - **auf `df84f7b`** (`/tmp/p4-kopie-B-nachspiel`, frisches `git archive`): Vorbereitung alle Ausgaben wie angegeben. B.1 `4 failed, 2 passed` (3 × `assert 201 == 409`, 1 × `assert 200 == 409`) → `6 passed`, Zählungen `5`/`6`, V `1650`; B.2 `2 failed, 1 passed` → `3 passed`, `if braucht_nummer:` `1`, Bestand `2 failed, 9 passed` (genau die zwei Namen) → `11 passed`, V `1653`; B.3 `6 failed, 2 passed` → `8 passed`, B-Klassen `17 passed`, Zählungen `2`/`0`, `ruff` F821/F823 Exit 0, F401 nur der Altbefund, V `1661`; B.4 `0` → `3`, `tsc` sauber; B.5 `ERR_MODULE_NOT_FOUND` → `18 Fälle ok`, `tsc` sauber, `updateLine` `1`, Paket-3-Abnahme `5 passed, 462 deselected`; B.6 `ERR_MODULE_NOT_FOUND` → `14 Fälle ok`, `filteredInvoices` `0`, `tsc` sauber, Abnahme `5 passed`, Build `✓ built`. Ergebnis dateigleich mit der Entwicklungskopie (`diff -rq` leer).
  - **auf dem D/F/O-Stand** (`/tmp/p4-kopie-B-dfo`, `git archive bd56901` aus dem Arbeitsbaum `minga-n0910`, Branch `feat/nachtrag-0910`, alle 14 Commits D/F/O): Basis V `14 failed, 1709 passed, 2 skipped, 1 error`; Vorbereitung und alle Rot/Grün-Ausgaben wie auf `df84f7b`; V `1715` → `1718` → `1726`, Namen = Baseline. Nach B unverändert: `tests/test_nachtrag_0910.py` `65 passed`, `belegpfad.check` `35 Fälle ok`, `dateiname.check` `8 Fälle ok`, O.6 Step 4 (`createObjectURL` genau in den 7 Dateien), O.5 Step 4 (`belegHerunterladen(` in `Invoices.tsx` `3`, in `OrderDocumentsModal.tsx` `1`), D.5 (`invoicesApi.datevEinstellungen` in `Invoices.tsx` `1`).
- **Überarbeitung nach Review (09.10., B-E6, Tausenderpunkt, Escape, A/X07-Grenzen, R-B1):** Nachspiel des ganzen Plans aus dem Plantext (Blöcke zerlegt mit `/tmp/p4b-rev2/blocks.py`, angewandt mit `/tmp/p4b-rev2/apply2.py`, Ablauf `/tmp/p4b-rev2/lauf.sh`; jeder Anker genau einmal), Protokolle `/tmp/p4b-rev2/lauf-df84.log`, `/tmp/p4b-rev2/lauf-dfo.log`:
  - **auf `df84f7b`** (`/tmp/p4-kopie-Brev2`, frisches `git archive`): Vorbereitung alle 19 Ausgaben wie angegeben. V Basis `14 failed, 1644 passed, 2 skipped, 1 error`. B.1 `4 failed, 2 passed` → `6 passed`, B.2 `2 failed, 1 passed` → `3 passed`, Bestand `2 failed, 9 passed` → `11 passed`, B.3 `6 failed, 2 passed` → `8 passed` (Namen und Meldungen wie in den Steps); B.4 `3`; B.5 Backend Rot `1 failed, 3 passed` (`assert 200 == 409`) → `4 passed`, Zählungen `4`/`1`, `ruff` F821/F823 Exit 0, V `1665` (= 1644 + 6 + 3 + 8 + 4), Namen = Baseline; Node `ERR_MODULE_NOT_FOUND` → `20 Fälle ok`; `tsc` sauber; `updateLine` `1`, Escape-Zeile `2`; Paket-3-Abnahme `5 passed, 462 deselected`; B.6 `ERR_MODULE_NOT_FOUND` → `14 Fälle ok`, `filteredInvoices` `0`, `tsc` sauber; B.7 alle B-Klassen `21 passed`, `ruff` F821/F823 Exit 0, F401 nur der Altbefund, Build `✓ built`.
  - **auf dem D/F/O-Stand `1bfa032`** (`/tmp/p4-kopie-Brev2-dfo`): Vorbereitung wie angegeben; V Basis `14 failed, 1806 passed, 2 skipped, 1 error`; alle Rot/Grün-Ausgaben wie auf `df84f7b`; V nach B.5 `1827` (+21), Namen = Baseline; danach `tests/test_nachtrag_0910.py` `162 passed`, `belegpfad.check` `35 Fälle ok`, `dateiname.check` `8 Fälle ok`, `belegHerunterladen(` in `Invoices.tsx` `3`, in `OrderDocumentsModal.tsx` `1`, `invoicesApi.datevEinstellungen` `1`; im geteilten `node_modules` nichts Neueres.
  - **mit Paket-4-Abschnitt A** (`/tmp/p4-kopie-Brev2-mitA`: Abzug der A-Prüfkopie `/tmp/p4-kopie-arev3` vom 09.10., darauf B.1–B.3 und B.5 Backend aus dem Plantext, jeder Anker genau einmal): A- und B-Klassen `39 passed`; Probe `tests/test_zz_probe_mita.py` (nicht Teil des Plans) `2 passed`: Abo-Entwurf mit Liefertag heute, `POST /sales/orders/{id}/status` mit `entwurf_bestaetigen` → `GELIEFERT`, genau ein Lieferschein `ENTWURF` mit Liefertag, der Sammellauf sieht ihn; ohne Kennzeichen bleibt `ENTWURF → GELIEFERT` abgelehnt, kein Lieferschein. (Dieser A-Stand bestätigt im Tagesplan nur Entwürfe bis zu ihrem Liefertag; maßgeblich ist A.)
  - **Escape im Dialog** (Chromium über Playwright, React 18.3.1 wie im Projekt, `Modal`-Nachbau mit `keydown` auf `document` und `createPortal` nach `document.body`, `/tmp/p4b-rev2/esc/esc.cjs`): ohne `e.stopPropagation()` → Zeile verworfen **und** Dialog zu; mit → nur Zeile verworfen, Dialog offen.
  - **Probe Mengenänderung** (vor B-E6, Kopie des Reviews): Monatskunde, 2 × 10 × 2,50 €, Monatslauf, Menge 20 → 15 → Rechnung netto 37,50 €, Anlage 25,00 + 25,00 €.
- **Produktion** nur lesend (`mode=ro`, nur `SELECT`/`pragma`, Skripte `/tmp/p4b-skripte/prod1.py`–`prod3.py`, Überarbeitung `/tmp/p4b-rev2/prod_rb1_neu.py`): Zahlen unter „Befunde“. R-B1 mit sortierter Liste gemessen 09.10.: `0`, `0`, `['BE-20261007-0008', 'BE-20261008-0002']`; KD-10022 4 × `ENTWURF` (14.09.–05.10.), KD-10012 0 Bestellungen seit 01.09., `BE-20261008-0002` `GELIEFERT`/`EINZELN`, 0 Lieferscheine, 0 Rechnungen; Rechnungsentwürfe mit Quellen `0`.
- **Nicht gemessen:** Oberfläche im Browser (Review Focus je Task; Escape nur im Nachbau oben), Commits (Kopien ohne Git), der erste automatische Monatslauf am 01.11. (Runbook R-B2), B.5 auf `bd56901` einzeln (enthalten in `1bfa032`).

### Prozedur V in B

Befehl aus dem Kopf (Prozedur V). N steigt durch B um **+6** (B.1), **+3** (B.2), **+8** (B.3), **+4** (B.5); B.4, B.6 und B.7 **+0**. Gemessen: auf `df84f7b` 1644 → 1650 → 1653 → 1661 → 1665; auf dem D/F/O-Stand `bd56901` 1709 → 1715 → 1718 → 1726 (B.1–B.3), auf `1bfa032` 1806 → 1827 nach B.5. Im Gesamtplan (nach A) errechnet: 1836 → 1842 → 1845 → 1853 → 1857. Maßgeblich sind die Namen.

### Vorbereitung B (vor Task 7)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis-B>` in den Bericht (eine Shell-Variable reicht nicht). `git status --porcelain` → keine `M`/`A`/`D`-Zeile; sonst stoppen und melden.
- Ausgangsstand B: in „Vorbereitung (vor Task 1)“ geprüft. Tasks 1–6 berühren keinen Anker von B (Anker-Nachspiel, Prüfstand im Kopf).

---

### Task 7 (B.1): `FAKTURIERT` sperrt jede Rechnung zur Bestellung (G66)

**Files:**
- Modify: `backend/app/services/invoice_service.py` (neue Klasse und Funktion hinter `BereitsAbgerechnet`; `create_invoice`; `create_invoice_from_order`; `add_line`; `pruefe_festschreibung`)
- Modify: `backend/app/api/v1/invoices.py` (`add_invoice_line`)
- Create/Modify: `backend/tests/test_paket4.py` (Kopf falls neu, Block B.1 anhängen)

**Interfaces:**
- Produces (`app.services.invoice_service`): `class BestellungFakturiert(BereitsAbgerechnet)`; `fakturiert_meldung(order: Order) -> str`. API: 409 mit `fakturiert_meldung` auf `POST /invoices/from-order/{id}`, `POST /invoices` (mit `order_id` oder Position mit `order_item_id`), `POST /invoices/{id}/lines` (mit `order_item_id`); 409 mit `fakturiert_meldung(…) + " Diesen Entwurf verwerfen."` auf `POST /invoices/{id}/finalize` und `POST /invoices/{id}/send` (Entwurf).
- Consumes: `OrderStatus.FAKTURIERT`; die vorhandenen `except BereitsAbgerechnet`-Zweige (409).
- Unverändert: `_abrechenbare_lieferscheine` (Sammel-/Monatslauf), `aktive_rechnung_zur_bestellung`, `cancel_invoice` (Gutschrift ist kein Typ `RECHNUNG`).

**Review Focus (B.1):** Meldung im Toast des Belegdialogs (für einen Entwurf, der vor der Kennzeichnung entstand: Finalisieren → 409 mit „Diesen Entwurf verwerfen.“); keine Rechnung, keine Nummer verbraucht.

- [ ] **Step 1: Testdatei.** Kopf, nur wenn `backend/tests/test_paket4.py` noch fehlt (sonst überspringen; ein anderer Paket-4-Abschnitt hat ihn angelegt):

```python
"""Paket 4 — Gernots Rückmeldungen vom 08./09.10.2026.

Gemeinsame Testdatei der Abschnitte A–D. Klassen und Helfer tragen ein
Abschnitts-Präfix (TestP4A…/_p4a_, TestP4B…/_p4b_, …): ein gleichnamiger
Helfer würde still ersetzt. Jeder Abschnitt bringt seine Imports selbst mit.
Keine autouse-Fixture.
"""
```

Dann den Block ans Dateiende von `backend/tests/test_paket4.py` anhängen:

```python


# ============================================================
# B — Abrechnung: Doppelabrechnung, Lieferschein beim Ausliefern,
#     Rechnungsdatum beim Festschreiben
# ============================================================

import uuid as _p4b_uuid
from datetime import date as _p4b_date, timedelta as _p4b_timedelta

from tests.conftest import TestingSessionLocal as _P4B_Session


def _p4b_kunde(client, name="Dorint Hotels Betriebs GmbH", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _p4b_bestellung(client, kunde, liefertag=None, menge=10, preis="2.50"):
    """Bestätigte Bestellung mit einer Freitextposition (10 × 2,50 € zu 7 %)."""
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (liefertag or _p4b_date.today()).isoformat(),
        "lines": [{"product_name": "Erbsen-Schale", "quantity": menge, "unit": "STK",
                   "unit_price": preis, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    bestellung = r.json()
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def _p4b_status(client, bestellung, status, **extra):
    r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/status", json={"status": status, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _p4b_fakturiert(client, kunde):
    """Bestellung, die außerhalb von NovaERP abgerechnet ist (wie die 574
    DATEV-Bestellungen in minga): geliefert, dann FAKTURIERT."""
    bestellung = _p4b_bestellung(client, kunde)
    _p4b_status(client, bestellung, "GELIEFERT")
    return _p4b_status(client, bestellung, "FAKTURIERT")


def _p4b_rechnungen(kunde):
    from app.models.invoice import Invoice
    with _P4B_Session() as db:
        return db.query(Invoice).filter(Invoice.customer_id == _p4b_uuid.UUID(kunde["id"])).count()


def _p4b_meldung(bestellung):
    return (
        f"Bestellung {bestellung['order_number']} ist als „Fakturiert“ gekennzeichnet: "
        "Sie ist außerhalb von NovaERP abgerechnet (z. B. über DATEV). "
        "Eine Rechnung hier würde sie doppelt berechnen."
    )


class TestP4BFakturiert:
    """G66: FAKTURIERT heißt abgerechnet — auch ohne Rechnung in NovaERP.
    Kein Weg legt dafür eine Rechnung an oder schreibt sie fest."""

    def test_rechnung_aus_bestellung_gesperrt(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_fakturiert(client, kunde)

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung)
        assert _p4b_rechnungen(kunde) == 0

    def test_rechnung_von_hand_mit_bestellbezug_gesperrt(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_fakturiert(client, kunde)

        r = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "order_id": bestellung["id"],
            "invoice_date": _p4b_date.today().isoformat(),
            "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                       "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
        })

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung)
        assert _p4b_rechnungen(kunde) == 0

    def test_position_aus_fakturierter_bestellung_gesperrt(self, client):
        """Eine Bestellposition (order_item_id) holt die Bestellung über einen
        anderen Entwurf herein — derselbe Schutz."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_fakturiert(client, kunde)
        zeile_id = client.get(f"/api/v1/sales/orders/{bestellung['id']}").json()["lines"][0]["id"]
        r = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": _p4b_date.today().isoformat()})
        assert r.status_code == 201, r.text
        entwurf = r.json()

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/lines", json={
            "description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
            "unit_price": "2.50", "tax_rate": "REDUZIERT", "order_item_id": zeile_id})

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung)
        assert client.get(f"/api/v1/invoices/{entwurf['id']}").json()["lines"] == []

    def test_entwurf_einer_spaeter_fakturierten_bestellung_nicht_festschreibbar(self, client):
        """Altfall: Der Entwurf entstand, bevor die Bestellung als abgerechnet
        gekennzeichnet wurde. Er bekommt keine Nummer."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        entwurf = r.json()
        _p4b_status(client, bestellung, "FAKTURIERT")

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/finalize")

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _p4b_meldung(bestellung) + " Diesen Entwurf verwerfen."
        nachher = client.get(f"/api/v1/invoices/{entwurf['id']}").json()
        assert nachher["status"] == "ENTWURF"
        assert nachher["invoice_number"].startswith("ENTWURF-")

    def test_gelieferte_bestellung_bleibt_abrechenbar(self, client):
        """Wächter: nur FAKTURIERT sperrt."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 201, r.text

    def test_sammellauf_laesst_fakturierte_aus(self, client):
        """Wächter (Spec-Nachtrag 08.10.): Sammel- und Monatslauf schlossen
        FAKTURIERT schon vorher aus."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date.today())
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text
        _p4b_status(client, bestellung, "GELIEFERT")
        _p4b_status(client, bestellung, "FAKTURIERT")
        heute = _p4b_date.today()

        r = client.post("/api/v1/invoices/batch-run/preview", json={
            "period_from": (heute - _p4b_timedelta(days=31)).isoformat(),
            "period_to": heute.isoformat()})

        assert r.status_code == 200, r.text
        assert r.json()["kunden"] == []
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4BFakturiert -q -p no:cacheprovider 2>&1 | tail -8
```

Erwartet: `4 failed, 2 passed`. Rot: `test_rechnung_aus_bestellung_gesperrt`, `test_rechnung_von_hand_mit_bestellbezug_gesperrt`, `test_position_aus_fakturierter_bestellung_gesperrt` (je `assert 201 == 409`), `test_entwurf_einer_spaeter_fakturierten_bestellung_nicht_festschreibbar` (`assert 200 == 409`). Grün bleiben die Wächter `test_gelieferte_bestellung_bleibt_abrechenbar` und `test_sammellauf_laesst_fakturierte_aus`.

- [ ] **Step 3: Implementierung.**

`backend/app/services/invoice_service.py` — Klasse `BereitsAbgerechnet` (neue Klasse und Meldung dahinter): diesen Block

```python
class BereitsAbgerechnet(ValueError):
    """Zur Bestellung gibt es schon eine nicht stornierte Rechnung.

    Unterklasse von ValueError: bestehende Aufrufer, die ValueError fangen,
    funktionieren weiter. Die API macht daraus 409 statt 400.
    """
```

ersetzen durch

```python
class BereitsAbgerechnet(ValueError):
    """Zur Bestellung gibt es schon eine nicht stornierte Rechnung.

    Unterklasse von ValueError: bestehende Aufrufer, die ValueError fangen,
    funktionieren weiter. Die API macht daraus 409 statt 400.
    """


class BestellungFakturiert(BereitsAbgerechnet):
    """Die Bestellung steht auf FAKTURIERT: außerhalb von NovaERP abgerechnet,
    z. B. die über DATEV abgerechneten Bestellungen bis 07.10.2026 in minga
    (Paket 4, B; G66). Unterklasse von BereitsAbgerechnet — die API
    antwortet 409. NovaERP setzt FAKTURIERT nie selbst (keine Rechnung
    ändert den Bestellstatus); der Status kommt aus dem Import oder der
    Sammelaktion und ist endgültig (order_status_service).
    """


def fakturiert_meldung(order: Order) -> str:
    """Meldung, wenn eine fakturierte Bestellung (noch einmal) berechnet würde."""
    return (
        f"Bestellung {order.order_number} ist als „Fakturiert“ gekennzeichnet: "
        "Sie ist außerhalb von NovaERP abgerechnet (z. B. über DATEV). "
        "Eine Rechnung hier würde sie doppelt berechnen."
    )
```

`backend/app/services/invoice_service.py` — in `InvoiceService.create_invoice`, Doppelabrechnungsprüfung: diesen Block

```python
        if order_id is not None and invoice_type == InvoiceType.RECHNUNG:
            vorhandene = self.aktive_rechnung_zur_bestellung(order_id)
```

ersetzen durch

```python
        if order_id is not None and invoice_type == InvoiceType.RECHNUNG:
            # FAKTURIERT = außerhalb abgerechnet, auch ohne Rechnung hier (Paket 4, B)
            bestellung = self.db.get(Order, order_id)
            if bestellung is not None and bestellung.status == OrderStatus.FAKTURIERT:
                raise BestellungFakturiert(fakturiert_meldung(bestellung))
            vorhandene = self.aktive_rechnung_zur_bestellung(order_id)
```

`backend/app/services/invoice_service.py` — in `InvoiceService.create_invoice_from_order`, Statusprüfung: diesen Block

```python
        if order.status == OrderStatus.STORNIERT:
            raise BestellungStorniert("Bestellung ist storniert")
```

ersetzen durch

```python
        if order.status == OrderStatus.STORNIERT:
            raise BestellungStorniert("Bestellung ist storniert")
        # Vor der Pfandprüfung: deren Meldung („nichts zu fakturieren“) führte
        # bei einer fakturierten Bestellung in die Irre (Paket 4, B).
        if order.status == OrderStatus.FAKTURIERT:
            raise BestellungFakturiert(fakturiert_meldung(order))
```

`backend/app/services/invoice_service.py` — in `InvoiceService.add_line`, nach der Entwurfsprüfung (D.2 ändert erst den Block ab `# Buchungskonto basierend auf Steuersatz`): diesen Block

```python
        if invoice.status != InvoiceStatus.ENTWURF:
            raise ValueError("Nur Entwürfe können bearbeitet werden")

        # Position ermitteln
```

ersetzen durch

```python
        if invoice.status != InvoiceStatus.ENTWURF:
            raise ValueError("Nur Entwürfe können bearbeitet werden")

        # Eine Bestellposition holt ihre Bestellung in diesen Entwurf — auch in
        # einen ohne Bestellbezug (Paket 4, B).
        if order_item_id is not None:
            bestellzeile = self.db.get(OrderLine, order_item_id)
            if bestellzeile is not None and bestellzeile.order.status == OrderStatus.FAKTURIERT:
                raise BestellungFakturiert(fakturiert_meldung(bestellzeile.order))

        # Position ermitteln
```

`backend/app/services/invoice_service.py` — in `InvoiceService.pruefe_festschreibung`, Schleife über die Bestellungen: diesen Block

```python
            order = self.db.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()
            andere = self.aktive_rechnung_zur_bestellung(
```

ersetzen durch

```python
            order = self.db.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()
            # Entwurf älter als die Kennzeichnung FAKTURIERT (Paket 4, B)
            if order is not None and order.status == OrderStatus.FAKTURIERT:
                raise BestellungFakturiert(fakturiert_meldung(order) + " Diesen Entwurf verwerfen.")
            andere = self.aktive_rechnung_zur_bestellung(
```

`backend/app/api/v1/invoices.py` — in `add_invoice_line`, Ende des `try`-Blocks: diesen Block

```python
        line = service.add_line(
            invoice_id=invoice_id,
            **data.model_dump(),
        )
        db.commit()
        db.refresh(line)
        return line
    except ValueError as e:
```

ersetzen durch

```python
        line = service.add_line(
            invoice_id=invoice_id,
            **data.model_dump(),
        )
        db.commit()
        db.refresh(line)
        return line
    except BereitsAbgerechnet as e:
        # Position aus einer fakturierten Bestellung (Paket 4, B)
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
```

Prüfen: `grep -c 'BestellungFakturiert' backend/app/services/invoice_service.py` → `5` (Klasse und vier `raise`); `grep -c 'except BereitsAbgerechnet' backend/app/api/v1/invoices.py` → `6` (vorher `5`, auf `df84f7b` wie nach D).

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `6 passed`.
- [ ] **Vollauf (Prozedur V):** `14 failed, N passed, 2 skipped, 1 error` mit N = vorher + 6; Abgleich leer.
- [ ] **Commit:**

```bash
git add backend/app/services/invoice_service.py backend/app/api/v1/invoices.py backend/tests/test_paket4.py
git commit -m "fix(rechnung): fakturierte Bestellungen sperren jede Rechnung — aus Bestellung, von Hand, per Position und beim Festschreiben (P4-B.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8 (B.2): Rechnungsdatum beim Festschreiben immer der Ausstellungstag (G64)

**Files:**
- Modify: `backend/app/services/invoice_service.py` (`InvoiceService.festschreiben`: Docstring Punkt 2, Datumsblock)
- Modify: `backend/tests/test_paket4.py` (Block B.2 anhängen)
- Modify: `backend/tests/test_gernot_261008_paket3.py` (`TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum`) und `backend/tests/test_dunning.py` (`test_dunning_email_sending`) — Entscheidung B-E3

**Interfaces:**
- Produces: `festschreiben` setzt `invoice.invoice_date = _heute_berlin()` für jeden Entwurf; `due_date = invoice_date + Zahlungsziel des Entwurfs in Tagen` (unverändert). Nummernvergabe unverändert (nur Platzhalter bekommen eine).
- Consumes: `_heute_berlin` (Modulfunktion, in Tests festsetzbar).

- [ ] **Step 1: Block ans Dateiende von `backend/tests/test_paket4.py` anhängen:**

```python


from decimal import Decimal as _P4B_Decimal


def _p4b_altentwurf(kunde, nummer, datum, ziel_tage):
    """Entwurf, wie ihn der Code vor Paket 3 anlegte: echte RE-Nummer schon
    beim Anlegen (Bestand wie RE-2026-00003). Direkt per ORM — über die API
    entsteht so ein Entwurf nicht mehr."""
    from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, TaxRate
    with _P4B_Session() as db:
        rechnung = Invoice(
            invoice_number=nummer, customer_id=_p4b_uuid.UUID(kunde["id"]),
            invoice_date=datum, due_date=datum + _p4b_timedelta(days=ziel_tage),
            status=InvoiceStatus.ENTWURF,
        )
        db.add(rechnung)
        db.flush()
        db.add(InvoiceLine(
            invoice_id=rechnung.id, position=1, description="Erbsen-Schale",
            quantity=_P4B_Decimal("10"), unit="STK", unit_price=_P4B_Decimal("2.50"),
            tax_rate=TaxRate.REDUZIERT, line_total=_P4B_Decimal("25.00"),
        ))
        db.commit()
        return str(rechnung.id)


def _p4b_heute_festsetzen(monkeypatch, tag):
    monkeypatch.setattr("app.services.invoice_service._heute_berlin", lambda: tag)


def _p4b_festschreiben(client, rechnung_id):
    r = client.post(f"/api/v1/invoices/{rechnung_id}/finalize")
    assert r.status_code == 200, r.text
    return r.json()


class TestP4BAusstellungsdatum:
    """G64: Rechnungsdatum ist der Tag des Festschreibens (Europe/Berlin),
    auch bei einem Altentwurf mit RE-Nummer. Das Zahlungsziel in Tagen bleibt."""

    def test_altentwurf_mit_nummer_bekommt_den_tag_der_ausstellung(self, client, monkeypatch):
        """Wie RE-2026-00003: angelegt 07.10., festgeschrieben 09.10."""
        kunde = _p4b_kunde(client, "Ökoring Handels GmbH")
        alt_id = _p4b_altentwurf(kunde, "RE-2026-00003", _p4b_date(2026, 10, 7), 14)
        _p4b_heute_festsetzen(monkeypatch, _p4b_date(2026, 10, 9))

        rechnung = _p4b_festschreiben(client, alt_id)

        assert rechnung["invoice_number"] == "RE-2026-00003"
        assert rechnung["invoice_date"] == "2026-10-09"
        assert rechnung["due_date"] == "2026-10-23"

    def test_zahlungsziel_in_tagen_bleibt(self, client, monkeypatch):
        kunde = _p4b_kunde(client, "Ökoring Handels GmbH")
        alt_id = _p4b_altentwurf(kunde, "RE-2026-00004", _p4b_date(2026, 9, 1), 30)
        _p4b_heute_festsetzen(monkeypatch, _p4b_date(2026, 10, 9))

        rechnung = _p4b_festschreiben(client, alt_id)

        assert (rechnung["invoice_date"], rechnung["due_date"]) == ("2026-10-09", "2026-11-08")

    def test_neuer_entwurf_wie_bisher(self, client, monkeypatch):
        """Wächter: Entwurf mit Platzhalter — Nummer und Datum beim Festschreiben."""
        kunde = _p4b_kunde(client, "Ökoring Handels GmbH")
        r = client.post("/api/v1/invoices", json={
            "customer_id": kunde["id"], "invoice_date": "2026-10-01", "due_date": "2026-10-15",
            "lines": [{"description": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                       "unit_price": "2.50", "tax_rate": "REDUZIERT"}],
        })
        assert r.status_code == 201, r.text
        _p4b_heute_festsetzen(monkeypatch, _p4b_date(2026, 10, 9))

        rechnung = _p4b_festschreiben(client, r.json()["id"])

        assert rechnung["invoice_number"] == "RE-2026-00001"
        assert (rechnung["invoice_date"], rechnung["due_date"]) == ("2026-10-09", "2026-10-23")
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4BAusstellungsdatum -q -p no:cacheprovider 2>&1 | tail -6
```

Erwartet: `2 failed, 1 passed`. Rot: `test_altentwurf_mit_nummer_bekommt_den_tag_der_ausstellung` (`assert '2026-10-07' == '2026-10-09'`), `test_zahlungsziel_in_tagen_bleibt` (`assert ('2026-09-01', '2026-10-01') == ('2026-10-09', '2026-11-08')`). Grün: Wächter `test_neuer_entwurf_wie_bisher`.

- [ ] **Step 3: Implementierung.**

`backend/app/services/invoice_service.py` — Docstring von `InvoiceService.festschreiben`, Punkt 2: diesen Block

```python
        2. Trägt der Entwurf den Platzhalter: Rechnungsdatum = heute
           (Europe/Berlin). Nummer und Ausstellungsdatum entstehen zusammen.
           Ein Altentwurf mit RE-Nummer behält Nummer und Datum.
```

ersetzen durch

```python
        2. Rechnungsdatum = heute (Europe/Berlin), immer — auch für einen
           Altentwurf, der seine RE-Nummer schon vor Paket 3 bekam; er
           behält nur die Nummer (Paket 4, B). Trägt der Entwurf den
           Platzhalter, entstehen Nummer und Ausstellungsdatum zusammen.
```

`backend/app/services/invoice_service.py` — in `InvoiceService.festschreiben`, nach dem Zahlungsziel: diesen Block

```python
        braucht_nummer = ist_entwurfsnummer(invoice.invoice_number)
        if braucht_nummer:
            invoice.invoice_date = _heute_berlin()
```

ersetzen durch

```python
        braucht_nummer = ist_entwurfsnummer(invoice.invoice_number)
        # Ausstellungsdatum ist der Tag des Festschreibens — auch für einen
        # Altentwurf mit RE-Nummer. RE-2026-00003 trug sonst das Anlagedatum
        # 07.10. statt 09.10. und lag vor der Lieferung vom 08.10. (Paket 4, B).
        invoice.invoice_date = _heute_berlin()
```

Prüfen: `grep -c 'if braucht_nummer:' backend/app/services/invoice_service.py` → `1` (nur noch die Nummernvergabe).

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `3 passed`.

- [ ] **Step 5: Bestandstests, die das alte Verhalten festhielten (B-E3).** Erst Rot bestätigen:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py::TestQ1Festschreiben tests/test_dunning.py -q -p no:cacheprovider 2>&1 | tail -4
```

Erwartet: `2 failed, 9 passed`: `TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum` (`assert ('<heute>', '<heute+14>') == ('<heute−10>', '<heute+4>')`) und `test_dunning.py::test_dunning_email_sending` (`assert 0 == 1`, `reminders_sent`). Andere Namen: Stoppregel 2.

`backend/tests/test_gernot_261008_paket3.py` — in `TestQ1Festschreiben`: diesen Block

```python
    def test_altentwurf_behaelt_re_nummer_und_datum(self, client):
        """Entscheidung 2: bestehende Entwürfe behalten ihre RE-Nummer."""
        kunde = _q1_kunde(client)
        alt_id = _q1_altentwurf(kunde, _q1_nr(3))
        vorher = client.get(f"/api/v1/invoices/{alt_id}").json()

        alt = _q1_finalisieren(client, {"id": alt_id})
        neu = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        assert alt["invoice_number"] == _q1_nr(3)
        assert (alt["invoice_date"], alt["due_date"]) == (vorher["invoice_date"], vorher["due_date"])
        assert neu["invoice_number"] == _q1_nr(4)
```

ersetzen durch

```python
    def test_altentwurf_behaelt_re_nummer(self, client):
        """Entscheidung 2: bestehende Entwürfe behalten ihre RE-Nummer. Das
        Rechnungsdatum ist seit Paket 4 (B) auch bei ihnen der Tag des
        Festschreibens (tests/test_paket4.py::TestP4BAusstellungsdatum)."""
        kunde = _q1_kunde(client)
        alt_id = _q1_altentwurf(kunde, _q1_nr(3))

        alt = _q1_finalisieren(client, {"id": alt_id})
        neu = _q1_finalisieren(client, _q1_entwurf(client, kunde))

        assert alt["invoice_number"] == _q1_nr(3)
        assert alt["invoice_date"] == _q1_heute().isoformat()
        assert neu["invoice_number"] == _q1_nr(4)
```

`backend/tests/test_dunning.py` — in `test_dunning_email_sending`: diesen Block

```python
    # Manually set to OVERDUE conform to logic
    invoice.status = InvoiceStatus.UEBERFAELLIG
```

ersetzen durch

```python
    # Manually set to OVERDUE conform to logic. Festschreiben setzt das
    # Rechnungsdatum seit Paket 4 (B) immer auf heute, auch bei der hier
    # vorab gesetzten Nummer — das Mahnbeispiel braucht die alten Daten.
    invoice.invoice_date = overdue_date - timedelta(days=14)
    invoice.due_date = overdue_date
    invoice.status = InvoiceStatus.UEBERFAELLIG
```

Dann derselbe Befehl → `11 passed`.

- [ ] **Vollauf (Prozedur V):** N = vorher + 3; Abgleich leer.
- [ ] **Commit:**

```bash
git add backend/app/services/invoice_service.py backend/tests/test_paket4.py backend/tests/test_gernot_261008_paket3.py backend/tests/test_dunning.py
git commit -m "fix(rechnung): Rechnungsdatum beim Festschreiben immer der Ausstellungstag, auch für Altentwürfe mit Nummer (P4-B.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9 (B.3): Ausliefern legt den fehlenden Lieferschein an (G31, X07)

**Files:**
- Create: `backend/app/services/lieferschein_service.py`
- Modify: `backend/app/api/v1/documents.py` (Importe, `_next_document_number`, `create_delivery_note`)
- Modify: `backend/app/services/order_status_service.py` (Import, `setze_status`)
- Modify: `backend/tests/test_paket4.py` (Block B.3 anhängen)

**Interfaces:**
- Produces (`app.services.lieferschein_service`): `naechste_belegnummer(db, model, number_col, prefix, today) -> str` (bisher `documents._next_document_number`, dort jetzt ein Alias); `lieferschein_anlegen(db, order, *, notes=None, packing_items=None, total_weight_g=None, total_packages=None, actual_delivery_date=None) -> DeliveryNote` (ENTWURF + Packliste, ohne `packing_items` 1:1 aus den Bestellpositionen; flusht, committet nicht); `lieferschein_beim_ausliefern(db, order) -> Optional[DeliveryNote]` (nur ohne vorhandenen Lieferschein und mit Positionen; trägt `order.actual_delivery_date`).
- `setze_status(…, GELIEFERT)` legt vor dem Bestandsabzug den Lieferschein an (gleiche Transaktion; Rollback bei Fehler wie bisher). Ein Audit-Eintrag je Wechsel wie bisher.
- Unverändert: `POST /sales/orders/{id}/delivery-notes` (400 ohne Positionen, 409 bei vorhandenem Lieferschein ohne `?zusaetzlich=true`, Antwort), Nummernformat `LS-JJJJMMTT-NNNN`/`PL-…` mit `date.today()`, `_abrechenbare_lieferscheine`, `waehle_vertreter`, Monatsdialog-Hinweise.

**Review Focus (B.3):** Tagesplan „Ausgeliefert“ für eine Bestellung ohne Packliste (bestätigt; nach Abschnitt A auch ein Abo-Entwurf) → Belegdialog zeigt einen Lieferschein (Entwurf) mit den Positionen der Bestellung; „Packliste“ danach öffnet dessen Packliste (kein zweiter Lieferschein). Monatsdialog: Lieferung erscheint unter „vorgeschlagen“ (Monatskunde) bzw. als `EINZELABRECHNUNG` (Einzelkunde), nicht mehr als `OHNE_LIEFERSCHEIN`. Lieferschein-PDF ohne internen Vermerk.

- [ ] **Step 1: Block ans Dateiende von `backend/tests/test_paket4.py` anhängen:**

```python


def _p4b_lieferscheine(client, bestellung):
    r = client.get(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return r.json()


def _p4b_monat(client, monat):
    r = client.get("/api/v1/invoices/monthly-proposals", params={"month": monat})
    assert r.status_code == 200, r.text
    return r.json()


class TestP4BLieferscheinBeimAusliefern:
    """G31/X07: Jede gelieferte Bestellung hat einen Lieferschein. Monats- und
    Sammellauf rechnen über Lieferscheine ab (Paket 3); ohne Lieferschein
    fehlte eine im Tagesplan ausgelieferte Bestellung still."""

    def test_ausliefern_legt_den_lieferschein_an(self, client):
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)

        geliefert = _p4b_status(client, bestellung, "GELIEFERT")

        scheine = _p4b_lieferscheine(client, bestellung)
        assert len(scheine) == 1
        ls = scheine[0]
        assert ls["delivery_note_number"].startswith("LS-")
        assert ls["status"] == "ENTWURF"
        assert ls["notes"] is None
        assert ls["actual_delivery_date"] == geliefert["actual_delivery_date"]
        assert [(p["product_name"], _P4B_Decimal(str(p["quantity"])))
                for p in ls["packing_list"]["items"]] == [("Erbsen-Schale", _P4B_Decimal("10"))]

    def test_nachgetragener_liefertag(self, client):
        """Tagesplan eines vergangenen Tages: der Lieferschein trägt dessen Datum."""
        kunde = _p4b_kunde(client)
        tag = _p4b_date.today() - _p4b_timedelta(days=3)
        bestellung = _p4b_bestellung(client, kunde, liefertag=tag)

        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date=tag.isoformat())

        assert [ls["actual_delivery_date"] for ls in _p4b_lieferscheine(client, bestellung)] == [tag.isoformat()]

    def test_vorhandener_lieferschein_bleibt_der_einzige(self, client):
        """Wächter: Packliste aus dem Tagesplan legte ihn schon an."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text

        _p4b_status(client, bestellung, "GELIEFERT")

        assert [ls["id"] for ls in _p4b_lieferscheine(client, bestellung)] == [r.json()["id"]]

    def test_sammelaktion_legt_je_bestellung_einen_an(self, client):
        kunde = _p4b_kunde(client)
        erste, zweite = _p4b_bestellung(client, kunde), _p4b_bestellung(client, kunde)

        r = client.post("/api/v1/sales/orders/bulk-status",
                        json={"order_ids": [erste["id"], zweite["id"]], "status": "GELIEFERT"})

        assert r.status_code == 200, r.text
        assert [len(_p4b_lieferscheine(client, b)) for b in (erste, zweite)] == [1, 1]
        nummern = {_p4b_lieferscheine(client, b)[0]["delivery_note_number"] for b in (erste, zweite)}
        assert len(nummern) == 2

    def test_quittieren_legt_keinen_zweiten_an(self, client):
        """Wächter: Quittieren setzt die Bestellung auf Geliefert — über denselben Weg."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        r = client.post(f"/api/v1/sales/orders/{bestellung['id']}/delivery-notes", json={})
        assert r.status_code == 201, r.text

        r = client.patch(f"/api/v1/sales/delivery-notes/{r.json()['id']}/mark-delivered",
                         json={"signed_by": "Küche"})

        assert r.status_code == 200, r.text
        assert [ls["status"] for ls in _p4b_lieferscheine(client, bestellung)] == ["GELIEFERT"]

    def test_monatslauf_nimmt_die_ausgelieferte_bestellung_auf(self, client):
        """Monatskunde, im Tagesplan „Ausgeliefert“, ohne Packliste. (Die
        Abo-Entwürfe von KD-10022 erreichen „Ausgeliefert“ erst mit
        Paket-4-Abschnitt A, G10; hier eine bestätigte Bestellung.)"""
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date(2026, 3, 2))
        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date="2026-03-02")

        stand = _p4b_monat(client, "2026-03")
        assert [h["art"] for h in stand["hinweise"] if h["customer_id"] == kunde["id"]] == ["NICHT_QUITTIERT"]
        assert [(v["customer_id"], v["anzahl_lieferscheine"]) for v in stand["vorgeschlagen"]] == [(kunde["id"], 1)]

        r = client.post("/api/v1/invoices/monthly-proposals/run", params={"month": "2026-03"})

        assert r.status_code == 201, r.text
        assert [(a["customer_id"], a["art"]) for a in r.json()["angelegt"]] == [(kunde["id"], "WARE")]
        rechnung = client.get(f"/api/v1/invoices/{r.json()['angelegt'][0]['invoice_id']}").json()
        assert _P4B_Decimal(str(rechnung["subtotal"])) == _P4B_Decimal("25.00")

    def test_einzelkunde_erscheint_im_monatsdialog(self, client):
        """X07: Eine künftig ausgelieferte Bestellung eines Einzelkunden wird
        im Monatsdialog sichtbar (Hinweis EINZELABRECHNUNG mit Lieferschein).
        Der Altfall BE-20261008-0002 (GELIEFERT vor B, ohne Lieferschein)
        bleibt hier unsichtbar — ihn zeigt erst der Belegstatus (Abschnitt C)."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date(2026, 3, 4))
        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date="2026-03-04")
        ls = _p4b_lieferscheine(client, bestellung)[0]

        hinweise = [h for h in _p4b_monat(client, "2026-03")["hinweise"] if h["customer_id"] == kunde["id"]]

        assert [(h["art"], h["belege"]) for h in hinweise] == [("EINZELABRECHNUNG", [ls["delivery_note_number"]])]

    def test_rechnung_aus_bestellung_belegt_den_lieferschein(self, client):
        """Kein zweiter Weg zur Doppelabrechnung: Der Lieferschein hängt an der
        Rechnung, der Sammellauf sieht die Bestellung nicht mehr."""
        from app.models.documents import DeliveryNote
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")

        assert r.status_code == 201, r.text
        ls_id = _p4b_uuid.UUID(_p4b_lieferscheine(client, bestellung)[0]["id"])
        with _P4B_Session() as db:
            assert str(db.get(DeliveryNote, ls_id).invoice_id) == r.json()["id"]
        heute = _p4b_date.today()
        r = client.post("/api/v1/invoices/batch-run/preview", json={
            "period_from": (heute - _p4b_timedelta(days=31)).isoformat(), "period_to": heute.isoformat()})
        assert r.json()["kunden"] == []
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4BLieferscheinBeimAusliefern -q -p no:cacheprovider 2>&1 | tail -10
```

Erwartet: `6 failed, 2 passed`. Rot: `test_ausliefern_legt_den_lieferschein_an` (`assert 0 == 1`, `len([])`), `test_nachgetragener_liefertag` (`assert [] == ['<heute−3>']`), `test_sammelaktion_legt_je_bestellung_einen_an` (`assert [0, 0] == [1, 1]`), `test_monatslauf_nimmt_die_ausgelieferte_bestellung_auf` (`['OHNE_LIEFERSCHEIN', 'KEINE_LIEFERUNGEN'] == ['NICHT_QUITTIERT']`), `test_einzelkunde_erscheint_im_monatsdialog` und `test_rechnung_aus_bestellung_belegt_den_lieferschein` (je `IndexError: list index out of range`). Grün: Wächter `test_vorhandener_lieferschein_bleibt_der_einzige`, `test_quittieren_legt_keinen_zweiten_an`.

- [ ] **Step 3: Implementierung.**

Neue Datei `backend/app/services/lieferschein_service.py`:

```python
"""Lieferschein anlegen — eine Regel für „Neuer LS“, die Packliste im
Tagesplan und das Ausliefern (Paket 4, B; G31, X07).

Abgerechnet wird über Lieferscheine: Sammel- und Monatslauf nehmen je
Bestellung einen noch nicht abgerechneten Lieferschein
(invoices._abrechenbare_lieferscheine), die Rechnung aus der Bestellung
belegt ihn (InvoiceService.create_invoice_from_order), ein Storno gibt ihn
frei. Eine gelieferte Bestellung ohne Lieferschein fehlte im Monatslauf
still — er meldete sie nur als OHNE_LIEFERSCHEIN. Deshalb legt der Wechsel
auf GELIEFERT einen an, wenn die Bestellung noch keinen hat
(order_status_service.setze_status). Committet nie.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.documents import DeliveryNote, PackingList, PackingListItem
from app.models.enums import DeliveryNoteStatus
from app.models.order import Order
from app.schemas.documents import PackingListItemCreate


def naechste_belegnummer(db: Session, model, number_col, prefix: str, today: date) -> str:
    """Generiert {PREFIX}-YYYYMMDD-NNNN sequenziell (AB, LS, PL)."""
    date_part = today.strftime("%Y%m%d")
    full_prefix = f"{prefix}-{date_part}"
    last = db.execute(
        select(model)
        .where(number_col.like(f"{full_prefix}-%"))
        .order_by(number_col.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_num = (int(getattr(last, number_col.key).split("-")[-1]) + 1) if last else 1
    return f"{full_prefix}-{next_num:04d}"


def lieferschein_anlegen(
    db: Session,
    order: Order,
    *,
    notes: Optional[str] = None,
    packing_items: Optional[list[PackingListItemCreate]] = None,
    total_weight_g: Optional[Decimal] = None,
    total_packages: Optional[int] = None,
    actual_delivery_date: Optional[date] = None,
) -> DeliveryNote:
    """Lieferschein (ENTWURF) samt Packliste anlegen. Ohne packing_items
    1:1 aus den Bestellpositionen (ohne Pfand-Erweiterungen). Prüft weder
    Positionen noch vorhandene Lieferscheine — das tun die Aufrufer.
    Committet nicht."""
    today = date.today()
    ls_number = naechste_belegnummer(
        db, DeliveryNote, DeliveryNote.delivery_note_number, "LS", today
    )
    pl_number = naechste_belegnummer(
        db, PackingList, PackingList.packing_list_number, "PL", today
    )

    note = DeliveryNote(
        order_id=order.id,
        delivery_note_number=ls_number,
        status=DeliveryNoteStatus.ENTWURF,
        notes=notes,
        actual_delivery_date=actual_delivery_date,
    )
    db.add(note)
    db.flush()  # note.id

    packing = PackingList(
        delivery_note_id=note.id,
        packing_list_number=pl_number,
        total_weight_g=total_weight_g,
        total_packages=total_packages,
    )
    db.add(packing)
    db.flush()  # packing.id

    # Items: explizite Liste ODER 1:1 aus Order-Lines
    if packing_items:
        items_to_create = packing_items
    else:
        items_to_create = [
            PackingListItemCreate(
                order_line_id=line.id,
                product_name=line.beschreibung or "Position",
                quantity=line.quantity,
                unit=line.unit,
                batch_number=line.batch_number,
                harvest_id=line.harvest_id,
                sort_order=line.position,
            )
            for line in order.lines
        ]

    for idx, item in enumerate(items_to_create, start=1):
        db.add(PackingListItem(
            packing_list_id=packing.id,
            order_line_id=item.order_line_id,
            sort_order=item.sort_order or idx,
            product_name=item.product_name,
            quantity=item.quantity,
            unit=item.unit,
            batch_number=item.batch_number,
            harvest_id=item.harvest_id,
            is_returnable_container=item.is_returnable_container,
            container_type=item.container_type,
            container_count=item.container_count,
        ))
    db.flush()
    return note


def lieferschein_beim_ausliefern(db: Session, order: Order) -> Optional[DeliveryNote]:
    """Beim Wechsel auf GELIEFERT: Lieferschein anlegen, wenn die Bestellung
    noch keinen hat (z. B. Tagesplan „Ausgeliefert“ ohne Packliste, Abo-
    Lieferung). Status ENTWURF wie jeder neue Lieferschein — quittiert hat der
    Kunde nichts; er trägt den Liefertag der Bestellung. Ein vorhandener
    Lieferschein bleibt der einzige (Gernot liefert nicht in Teilen). Ohne
    Positionen keiner. Committet nicht."""
    vorhanden = db.execute(
        select(DeliveryNote.id).where(DeliveryNote.order_id == order.id).limit(1)
    ).scalar_one_or_none()
    if vorhanden is not None or not order.lines:
        return None
    return lieferschein_anlegen(db, order, actual_delivery_date=order.actual_delivery_date)
```

`backend/app/api/v1/documents.py` — Importzeile aus `pdf_service`: diesen Block

```python
from app.services.pdf_service import PDFService, load_company_settings
```

ersetzen durch

```python
from app.services.pdf_service import PDFService, load_company_settings
from app.services.lieferschein_service import lieferschein_anlegen, naechste_belegnummer
```

`backend/app/api/v1/documents.py` — Helfer `_next_document_number` (wird Alias, AB nutzt ihn weiter): diesen Block

```python
def _next_document_number(db, model, number_col, prefix: str, today: date) -> str:
    """Generiert {PREFIX}-YYYYMMDD-NNNN sequenziell."""
    date_part = today.strftime("%Y%m%d")
    full_prefix = f"{prefix}-{date_part}"
    last = db.execute(
        select(model)
        .where(number_col.like(f"{full_prefix}-%"))
        .order_by(number_col.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_num = (int(getattr(last, number_col.key).split("-")[-1]) + 1) if last else 1
    return f"{full_prefix}-{next_num:04d}"
```

ersetzen durch

```python
# {PREFIX}-YYYYMMDD-NNNN: eine Nummernregel für AB, LS und PL (Paket 4, B)
_next_document_number = naechste_belegnummer
```

`backend/app/api/v1/documents.py` — in `create_delivery_note`, ab `today = date.today()` bis zum Ende der Funktion (die Prüfungen davor bleiben): diesen Block

```python
    today = date.today()
    ls_number = _next_document_number(
        db, DeliveryNote, DeliveryNote.delivery_note_number, "LS", today
    )
    pl_number = _next_document_number(
        db, PackingList, PackingList.packing_list_number, "PL", today
    )

    note = DeliveryNote(
        order_id=order.id,
        delivery_note_number=ls_number,
        status=DeliveryNoteStatus.ENTWURF,
        notes=data.notes,
    )
    db.add(note)
    db.flush()  # note.id

    packing = PackingList(
        delivery_note_id=note.id,
        packing_list_number=pl_number,
        total_weight_g=data.total_weight_g,
        total_packages=data.total_packages,
    )
    db.add(packing)
    db.flush()  # packing.id

    # Items: explizite Liste ODER 1:1 aus Order-Lines
    if data.packing_items:
        items_to_create = data.packing_items
    else:
        items_to_create = [
            PackingListItemCreate(
                order_line_id=line.id,
                product_name=line.beschreibung or "Position",
                quantity=line.quantity,
                unit=line.unit,
                batch_number=line.batch_number,
                harvest_id=line.harvest_id,
                sort_order=line.position,
            )
            for line in order.lines
        ]

    for idx, item in enumerate(items_to_create, start=1):
        db.add(PackingListItem(
            packing_list_id=packing.id,
            order_line_id=item.order_line_id,
            sort_order=item.sort_order or idx,
            product_name=item.product_name,
            quantity=item.quantity,
            unit=item.unit,
            batch_number=item.batch_number,
            harvest_id=item.harvest_id,
            is_returnable_container=item.is_returnable_container,
            container_type=item.container_type,
            container_count=item.container_count,
        ))

    db.commit()
    db.refresh(note)
    return note
```

ersetzen durch

```python
    # Paket 4, B: dieselbe Anlage wie beim Ausliefern (lieferschein_service)
    note = lieferschein_anlegen(
        db, order,
        notes=data.notes,
        packing_items=data.packing_items,
        total_weight_g=data.total_weight_g,
        total_packages=data.total_packages,
    )

    db.commit()
    db.refresh(note)
    return note
```

`backend/app/api/v1/documents.py` — Importe, die danach ungenutzt sind (`PackingListItem`, `PackingListItemCreate`): diesen Block

```python
from app.models.documents import (
    OrderConfirmation, DeliveryNote, PackingList, PackingListItem,
)
```

ersetzen durch

```python
from app.models.documents import (
    OrderConfirmation, DeliveryNote, PackingList,
)
```

und diesen Block

```python
    DeliveryNoteCreate, DeliveryNoteResponse, DeliveryNoteMarkDelivered,
    PackingListItemCreate, BelegVersandRequest,
```

ersetzen durch

```python
    DeliveryNoteCreate, DeliveryNoteResponse, DeliveryNoteMarkDelivered,
    BelegVersandRequest,
```

`backend/app/services/order_status_service.py` — Importzeile aus `order_fulfillment_service`: diesen Block

```python
from app.services.order_fulfillment_service import deduct_inventory_for_order
```

ersetzen durch

```python
from app.services.order_fulfillment_service import deduct_inventory_for_order
from app.services.lieferschein_service import lieferschein_beim_ausliefern
```

`backend/app/services/order_status_service.py` — in `setze_status`, Bestandsabzug: diesen Block

```python
    if neu == OrderStatus.GELIEFERT:
        try:
            deduct_inventory_for_order(db, order, commit=False)
```

ersetzen durch

```python
    if neu == OrderStatus.GELIEFERT:
        # Jede gelieferte Bestellung hat einen Lieferschein — Monats- und
        # Sammellauf rechnen über ihn ab (Paket 4, B; G31, X07).
        lieferschein_beim_ausliefern(db, order)
        try:
            deduct_inventory_for_order(db, order, commit=False)
```

Prüfen: `grep -c '_next_document_number' backend/app/api/v1/documents.py` → `2` (Alias und Aufruf in `create_confirmation`); `grep -c 'PackingListItem' backend/app/api/v1/documents.py` → `0`.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `8 passed`. Dazu alle B-Klassen: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4BFakturiert tests/test_paket4.py::TestP4BAusstellungsdatum tests/test_paket4.py::TestP4BLieferscheinBeimAusliefern -q -p no:cacheprovider 2>&1 | tail -1` → `17 passed`.
- [ ] **Statisch:** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/lieferschein_service.py app/api/v1/documents.py app/services/order_status_service.py app/services/invoice_service.py app/api/v1/invoices.py tests/test_paket4.py` → keine Ausgabe, Exit 0. `cd backend && /opt/homebrew/bin/ruff check --select F401 app/services/lieferschein_service.py app/api/v1/documents.py app/services/order_status_service.py` → genau ein Befund, der Altbefund `app/api/v1/documents.py:…: F401 [*] \`decimal.Decimal\` imported but unused` (auf `df84f7b` schon da; nicht beheben). Fehlt `ruff` unter dem Pfad: „nicht ausführbar“ melden.
- [ ] **Vollauf (Prozedur V):** N = vorher + 8; Abgleich leer (gemessen: kein Bestandstest reagiert auf den neuen Lieferschein).
- [ ] **Commit:**

```bash
git add backend/app/services/lieferschein_service.py backend/app/api/v1/documents.py backend/app/services/order_status_service.py backend/tests/test_paket4.py
git commit -m "feat(lieferschein): Ausliefern legt den fehlenden Lieferschein an — Monats- und Sammellauf sehen jede Lieferung (P4-B.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10 (B.4): Belegdialog bietet für fakturierte Bestellungen keine Rechnung an (G66, Oberfläche)

**Files:**
- Modify: `frontend/src/components/domain/OrderDocumentsModal.tsx` (`rechnungMoeglich`, Text bei leerer Rechnungsliste)

**Interfaces:**
- Consumes: `order.status` (`'FAKTURIERT'` in `types/index.ts`), 409 aus B.1 als Rückhalt.
- Texte: kein Knopf „Rechnung aus Bestellung“; statt „Noch keine Rechnung zu dieser Bestellung.“ steht „Als „Fakturiert“ gekennzeichnet: außerhalb von NovaERP abgerechnet (z. B. über DATEV). Eine Rechnung ist hier nicht möglich.“

**Review Focus (B.4):** Belegdialog einer der 574 Bestellungen (z. B. `BE-20261006-0001`): Text statt Knopf; Lieferschein-Teil unverändert. Bestellung `GELIEFERT` ohne Rechnung (z. B. `BE-20261008-0002`): Knopf wie bisher.

- [ ] **Step 1: Ausgangszählung.** `grep -c 'fakturiert' frontend/src/components/domain/OrderDocumentsModal.tsx` → `0`.
- [ ] **Step 2: Implementierung.**

`frontend/src/components/domain/OrderDocumentsModal.tsx` — vor dem `return`, Knopfbedingung: diesen Block

```tsx
  // Ohne frisch geladene Liste kein Knopf: lieber einmal zu wenig anbieten als doppelt berechnen.
  const rechnungMoeglich = order.status !== 'STORNIERT' && invoicesQuery.isSuccess && !invoicesQuery.isFetching && !aktiveRechnung;
```

ersetzen durch

```tsx
  // Fakturiert = außerhalb von NovaERP abgerechnet (z. B. über DATEV); der
  // Server lehnt jede Rechnung dazu mit 409 ab (Paket 4, B; G66).
  const fakturiert = order.status === 'FAKTURIERT';
  // Ohne frisch geladene Liste kein Knopf: lieber einmal zu wenig anbieten als doppelt berechnen.
  const rechnungMoeglich = order.status !== 'STORNIERT' && !fakturiert && invoicesQuery.isSuccess && !invoicesQuery.isFetching && !aktiveRechnung;
```

`frontend/src/components/domain/OrderDocumentsModal.tsx` — Abschnitt „Rechnungen“, leere Liste: diesen Block

```tsx
          ) : invoices.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">Noch keine Rechnung zu dieser Bestellung.</p>
          ) : (
```

ersetzen durch

```tsx
          ) : invoices.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400 italic">
              {fakturiert
                ? 'Als „Fakturiert“ gekennzeichnet: außerhalb von NovaERP abgerechnet (z. B. über DATEV). Eine Rechnung ist hier nicht möglich.'
                : 'Noch keine Rechnung zu dieser Bestellung.'}
            </p>
          ) : (
```

- [ ] **Step 3: Prüfen.** `grep -c 'fakturiert' frontend/src/components/domain/OrderDocumentsModal.tsx` → `3`. `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe. (Kein Rot: keine Frontend-Tests; Browser im Review Focus.)
- [ ] **Commit:**

```bash
git add frontend/src/components/domain/OrderDocumentsModal.tsx
git commit -m "feat(belege): Belegdialog bietet für fakturierte Bestellungen keine Rechnung an (P4-B.4)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11 (B.5): Menge und Einzelpreis einer Entwurfsposition ändern (G21)

**Files:**
- Modify: `backend/app/api/v1/invoices.py` (`update_invoice_line`: Mengensperre vor der Feldschleife, Entscheidung B-E6)
- Modify: `backend/tests/test_paket4.py` (Block B.5 anhängen)
- Create: `frontend/src/services/positionsaenderung.ts` (ohne Importe)
- Create: `frontend/tests/unit/positionsaenderung.check.ts`
- Modify: `frontend/src/pages/Invoices.tsx` (Import; in `InvoiceDetail`: Zustand und Mutation vor `deleteLineMutation`, Hinweis unter „Rechnungsdatum“, Positionstabelle)

**Interfaces:**
- Produces (API): `PATCH /invoices/{id}/lines/{line_id}` antwortet 409 mit „Die Menge stammt aus den Lieferscheinen dieser Sammel- bzw. Monatsrechnung. Entwurf verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten.“, wenn `quantity` sich ändert und die Position Einträge in `invoice_line_sources` hat. Sonst unverändert (Preis, Rabatt, Steuersatz, Text; Rechnung aus Bestellung; eine unverändert mitgeschickte Menge).
- Produces (Frontend): `zahlAusEingabe(eingabe, nachkommastellen) -> number` (NaN bei ungültig, auch beim mehrdeutigen Tausenderpunkt `1.000`), `eingabeAusZahl(wert) -> string`, `positionsaenderung(alt, menge, preis) -> { fehler } | { daten: { quantity?, unit_price? } }`.
- Consumes: `invoicesApi.updateLine(invoiceId, lineId, data)` (vorhanden), `PATCH /invoices/{id}/lines/{line_id}` (vorhanden; 400 für Nicht-Entwürfe, 409 Leergutbeleg, 422 Grenzen, neu 409 Sammelmenge). `InvoiceLineSource` ist in `invoices.py` schon modulweit importiert (Abschnitt Sammelrechnungslauf, `from app.models.invoice import InvoiceLineSource`), `select` ebenso. Die Tests bauen den Monatsentwurf über B.3 (Lieferschein beim Ausliefern).
- Texte: Knöpfe „Ändern“, „Speichern“, „Abbrechen“; Toasts „Position geändert“, „Position konnte nicht geändert werden“ (Servertext), Prüftexte aus `positionsaenderung`; Hinweis „Beim Finalisieren gilt der Tag der Ausstellung; das Zahlungsziel in Tagen bleibt.“

**Review Focus (B.5):** Entwurf in „Rechnungswesen“ und im Belegdialog: „Ändern“ → Menge `2,5` → Enter → Summe, MwSt und Gesamt neu; Escape im Feld verwirft die Zeile, **der Dialog bleibt offen** (Rechnungsdialog und Belegdialog); `1.000` oder `0` → Toast, nichts gesendet; unverändert speichern → schließt ohne Anfrage. Monatsentwurf (Sammelposition): Menge ändern → Toast mit dem Servertext (Korrekturweg), die Zeile bleibt in Arbeit; Preis ändern → gespeichert, PDF-Anlage „Enthaltene Lieferscheine“ ergibt die Nettosumme. Festgeschriebene Rechnung: keine Knöpfe. Leergutbeleg: keine Knöpfe (`isDraft` falsch). Spaltenbreite der Aktionsspalte im Belegdialog (`size="lg"`).

- [ ] **Step 1: Backend-Test.** Block ans Dateiende von `backend/tests/test_paket4.py` anhängen:

```python


_P4B_SAMMELMENGE = (
    "Die Menge stammt aus den Lieferscheinen dieser Sammel- bzw. Monatsrechnung. "
    "Entwurf verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten."
)


def _p4b_monatsentwurf(client, kunde):
    """Monatsrechnung März 2026 aus zwei Lieferungen à 10 × 2,50 €: eine
    Sammelposition mit zwei Quellen (invoice_line_sources), wie sie Gernot
    ab 01.11. für seine Monatskunden prüft. Die Lieferscheine legt das
    Ausliefern an (B.3)."""
    bestellungen = []
    for tag in (2, 9):
        bestellung = _p4b_bestellung(client, kunde, liefertag=_p4b_date(2026, 3, tag))
        _p4b_status(client, bestellung, "GELIEFERT", actual_delivery_date=f"2026-03-{tag:02d}")
        bestellungen.append(bestellung)
    r = client.post("/api/v1/invoices/monthly-proposals/run", params={"month": "2026-03"})
    assert r.status_code == 201, r.text
    rechnung = client.get(f"/api/v1/invoices/{r.json()['angelegt'][0]['invoice_id']}").json()
    return rechnung, bestellungen


def _p4b_netto_und_anlage(client, rechnung):
    """Nettosumme der Rechnung und Netto je Lieferschein, wie in der
    PDF-Anlage „Enthaltene Lieferscheine“ (netto_je_lieferschein)."""
    netto = client.get(f"/api/v1/invoices/{rechnung['id']}").json()["subtotal"]
    r = client.get(f"/api/v1/invoices/{rechnung['id']}/delivery-notes")
    assert r.status_code == 200, r.text
    return (_P4B_Decimal(str(netto)),
            [_P4B_Decimal(str(ls["betrag_netto"])) for ls in r.json()])


class TestP4BSammelpositionMenge:
    """G21 mit Sammel- und Monatsrechnung (B-E6): Die Menge einer
    Sammelposition steht je Lieferschein in invoice_line_sources, die Anlage
    „Enthaltene Lieferscheine“ rechnet daraus. Eine Mengenänderung nur an
    der Position ließ Rechnung (37,50 €) und Anlage (25,00 + 25,00 €)
    auseinanderlaufen."""

    def test_menge_einer_sammelposition_abgelehnt(self, client):
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        rechnung, _ = _p4b_monatsentwurf(client, kunde)
        zeile = rechnung["lines"][0]

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}", json={"quantity": 15})

        assert r.status_code == 409, r.text
        assert r.json()["detail"] == _P4B_SAMMELMENGE
        assert _p4b_netto_und_anlage(client, rechnung) == (
            _P4B_Decimal("50.00"), [_P4B_Decimal("25.00"), _P4B_Decimal("25.00")])

    def test_preis_einer_sammelposition_aenderbar(self, client):
        """Die Anlage rechnet mit dem Einzelpreis der Position und bleibt
        stimmig. Eine unverändert mitgeschickte Menge ist keine Änderung."""
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        rechnung, _ = _p4b_monatsentwurf(client, kunde)
        zeile = rechnung["lines"][0]

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{zeile['id']}",
                         json={"quantity": 20, "unit_price": "3.00"})

        assert r.status_code == 200, r.text
        assert _p4b_netto_und_anlage(client, rechnung) == (
            _P4B_Decimal("60.00"), [_P4B_Decimal("30.00"), _P4B_Decimal("30.00")])

    def test_menge_bei_rechnung_aus_bestellung_aenderbar(self, client):
        """Wächter: Rechnung aus Bestellung hat keine invoice_line_sources;
        ihre Anlage rechnet aus den Positionen selbst."""
        kunde = _p4b_kunde(client)
        bestellung = _p4b_bestellung(client, kunde)
        _p4b_status(client, bestellung, "GELIEFERT")
        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        rechnung = client.get(f"/api/v1/invoices/{r.json()['id']}").json()

        r = client.patch(f"/api/v1/invoices/{rechnung['id']}/lines/{rechnung['lines'][0]['id']}",
                         json={"quantity": 8})

        assert r.status_code == 200, r.text
        assert _p4b_netto_und_anlage(client, rechnung) == (_P4B_Decimal("20.00"), [_P4B_Decimal("20.00")])

    def test_korrekturweg_aus_der_meldung(self, client):
        """Wächter: Der Weg aus der Meldung führt zum Ziel — Entwurf
        verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten."""
        kunde = _p4b_kunde(client, "LfA Förderbank Bayern", invoice_mode="MONATLICH")
        rechnung, (erste, _) = _p4b_monatsentwurf(client, kunde)

        r = client.delete(f"/api/v1/invoices/{rechnung['id']}")
        assert r.status_code == 204, r.text
        zeile_id = client.get(f"/api/v1/sales/orders/{erste['id']}").json()["lines"][0]["id"]
        r = client.patch(f"/api/v1/sales/orders/{erste['id']}/lines/{zeile_id}", json={"quantity": 5})
        assert r.status_code == 200, r.text
        r = client.post("/api/v1/invoices/monthly-proposals/run", params={"month": "2026-03"})
        assert r.status_code == 201, r.text
        neu = client.get(f"/api/v1/invoices/{r.json()['angelegt'][0]['invoice_id']}").json()

        assert _p4b_netto_und_anlage(client, neu) == (
            _P4B_Decimal("37.50"), [_P4B_Decimal("12.50"), _P4B_Decimal("25.00")])
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4BSammelpositionMenge -q -p no:cacheprovider 2>&1 | tail -6
```

Erwartet: `1 failed, 3 passed`. Rot: `test_menge_einer_sammelposition_abgelehnt` (`assert 200 == 409`). Grün: `test_preis_einer_sammelposition_aenderbar`, Wächter `test_menge_bei_rechnung_aus_bestellung_aenderbar` und `test_korrekturweg_aus_der_meldung`.

- [ ] **Step 3: Mengensperre.** `backend/app/api/v1/invoices.py` — in `update_invoice_line`, vor der Feldschleife (D.2 ändert erst den Block nach der Schleife): diesen Block

```python
    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    satz_vorher = line.tax_rate
```

ersetzen durch

```python
    line = db.get(InvoiceLine, line_id)
    if not line or line.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail="Position nicht gefunden")

    update_data = data.model_dump(exclude_unset=True)
    # Sammel- und Monatsrechnung: Die Menge einer Position steht je
    # Lieferschein in invoice_line_sources; die Anlage „Enthaltene
    # Lieferscheine“ (PDF, GET /{id}/delivery-notes) rechnet Quellmenge mal
    # Einzelpreis. Eine neue Menge nur hier ließe Rechnung und Anlage
    # auseinanderlaufen, und welcher Lieferschein weniger hatte, weiß nur die
    # Bestellung. Preis, Rabatt, Steuersatz und Text bleiben änderbar
    # (Paket 4, B; G21). InvoiceLineSource: modulweiter Import beim Sammellauf.
    neue_menge = update_data.get("quantity")
    if neue_menge is not None and neue_menge != line.quantity and db.scalar(
        select(InvoiceLineSource.id).where(InvoiceLineSource.invoice_line_id == line.id).limit(1)
    ) is not None:
        raise HTTPException(
            status_code=409,
            detail="Die Menge stammt aus den Lieferscheinen dieser Sammel- bzw. Monatsrechnung. "
                   "Entwurf verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten.",
        )
    satz_vorher = line.tax_rate
```

Prüfen: `grep -c 'InvoiceLineSource' backend/app/api/v1/invoices.py` → `4` (vorher `2`: Import und Sammellauf); `grep -c 'Lauf neu starten' backend/app/api/v1/invoices.py` → `1`.

- [ ] **Step 4: Grün.** Befehl aus Step 2 → `4 passed`. `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/invoices.py tests/test_paket4.py` → keine Ausgabe, Exit 0.
- [ ] **Vollauf (Prozedur V):** N = vorher + 4; Abgleich leer.

- [ ] **Step 5: Node-Prüfung zuerst.** Neue Datei `frontend/tests/unit/positionsaenderung.check.ts`:

```ts
// Prüft positionsaenderung ohne Browser und ohne Testframework (Paket 4, B; G21).
// Lauf: node tests/unit/positionsaenderung.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { eingabeAusZahl, positionsaenderung } from '../../src/services/positionsaenderung.ts';

const MENGE_FALSCH = { fehler: 'Menge: eine Zahl größer als 0 mit höchstens 3 Nachkommastellen' };
const PREIS_FALSCH = { fehler: 'Einzelpreis: eine Zahl ab 0 mit höchstens 4 Nachkommastellen' };
// Die API liefert Dezimalzahlen je nach Weg als Zahl oder als Text ("10.000")
const alt = { quantity: '10.000', unit_price: 2.5 };

const faelle: Array<[string, string, unknown]> = [
  ['10', '2,50', { daten: {} }],                              // nichts geändert
  ['8', '2,5', { daten: { quantity: 8 } }],                   // nur Menge
  ['10', '2,75', { daten: { unit_price: 2.75 } }],            // nur Preis, Komma
  ['12,5', '3.10', { daten: { quantity: 12.5, unit_price: 3.1 } }], // beides, Punkt
  [' 10 ', ' 0 ', { daten: { unit_price: 0 } }],              // Preis 0 erlaubt, Leerzeichen egal
  ['0,125', '0,0833', { daten: { quantity: 0.125, unit_price: 0.0833 } }],
  ['0', '2,5', MENGE_FALSCH],
  ['', '2,5', MENGE_FALSCH],
  ['-1', '2,5', MENGE_FALSCH],
  ['1,2345', '2,5', MENGE_FALSCH],                            // 4 Nachkommastellen
  ['zehn', '2,5', MENGE_FALSCH],
  ['10', '', PREIS_FALSCH],
  ['10', '-2', PREIS_FALSCH],
  ['10', '2,12345', PREIS_FALSCH],                            // 5 Nachkommastellen
  ['10', '1.000,00', PREIS_FALSCH],                           // Tausenderpunkt
  ['1.000', '2,5', MENGE_FALSCH],                             // mehrdeutig: 1000 oder 1?
  ['10', '1.000', PREIS_FALSCH],                              // mehrdeutig, nicht raten
];

for (const [menge, preis, erwartet] of faelle) {
  assert.deepEqual(positionsaenderung(alt, menge, preis), erwartet, `${menge} / ${preis}`);
}
assert.equal(eingabeAusZahl('10.000'), '10');
assert.equal(eingabeAusZahl(2.5), '2,5');
assert.equal(eingabeAusZahl('0.0833'), '0,0833');
console.log(`positionsaenderung.check: ${faelle.length + 3} Fälle ok`);
```

Run: `cd frontend && node tests/unit/positionsaenderung.check.ts` → Rot: `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '…/frontend/src/services/positionsaenderung.ts'`.

- [ ] **Step 6: Reine Funktion.** Neue Datei `frontend/src/services/positionsaenderung.ts`:

```ts
/**
 * Menge und Einzelpreis einer Position im Rechnungsentwurf ändern (Paket 4, B;
 * G21: „Entwurf prüfen – Positionen editierbar (Menge, Preis, Position
 * löschen)“). Aus den Eingabefeldern wird die Änderung für
 * PATCH /invoices/{id}/lines/{line_id}: nur geänderte Felder. Der Server
 * rechnet Zeile und Summen neu und lehnt festgeschriebene Rechnungen ab.
 *
 * Bewusst ohne Importe: tests/unit/positionsaenderung.check.ts lädt die Datei
 * direkt mit Node.
 */

export interface PositionsWerte {
  quantity: number | string
  unit_price: number | string
}

export type Positionsaenderung =
  | { fehler: string }
  | { daten: { quantity?: number; unit_price?: number } }

/** Eingabe "2,5" oder "2.5" → 2.5. Keine Zahl, negativ, Tausenderpunkte oder
 *  mehr Nachkommastellen als die Spalte speichert → NaN. "1.000" ist
 *  mehrdeutig (deutscher Tausenderpunkt: 1000; Dezimalpunkt: 1) und wird
 *  abgelehnt statt geraten; "0.125", "3.10" und "1,000" bleiben eindeutig. */
export function zahlAusEingabe(eingabe: string, nachkommastellen: number): number {
  const roh = eingabe.trim();
  if (/^[1-9]\d{0,2}\.\d{3}$/.test(roh)) return NaN;
  const text = roh.replace(',', '.');
  const muster = new RegExp(`^\\d+(\\.\\d{1,${nachkommastellen}})?$`);
  return muster.test(text) ? Number(text) : NaN;
}

/** Wert für das Eingabefeld: 2.5 → "2,5", "10.000" → "10". */
export function eingabeAusZahl(wert: number | string): string {
  const zahl = Number(wert);
  return Number.isFinite(zahl) ? String(zahl).replace('.', ',') : '';
}

/** Menge: Spalte Numeric(10, 3); Einzelpreis: Numeric(10, 4). */
export function positionsaenderung(alt: PositionsWerte, menge: string, preis: string): Positionsaenderung {
  const neueMenge = zahlAusEingabe(menge, 3);
  if (!(neueMenge > 0)) return { fehler: 'Menge: eine Zahl größer als 0 mit höchstens 3 Nachkommastellen' };
  const neuerPreis = zahlAusEingabe(preis, 4);
  if (!(neuerPreis >= 0)) return { fehler: 'Einzelpreis: eine Zahl ab 0 mit höchstens 4 Nachkommastellen' };
  const daten: { quantity?: number; unit_price?: number } = {};
  if (neueMenge !== Number(alt.quantity)) daten.quantity = neueMenge;
  if (neuerPreis !== Number(alt.unit_price)) daten.unit_price = neuerPreis;
  return { daten };
}
```

Run: `cd frontend && node tests/unit/positionsaenderung.check.ts` → `positionsaenderung.check: 20 Fälle ok`.

- [ ] **Step 7: Rechnungsentwurf.**

`frontend/src/pages/Invoices.tsx` — Importzeile `getErrorMessage` (O.5 ersetzt die beiden Zeilen darüber, diese bleibt): diesen Block

```tsx
import { getErrorMessage } from '../services/errors';
```

ersetzen durch

```tsx
import { getErrorMessage } from '../services/errors';
import { eingabeAusZahl, positionsaenderung } from '../services/positionsaenderung';
```

`frontend/src/pages/Invoices.tsx` — in `InvoiceDetail`, vor `deleteLineMutation`: diesen Block

```tsx
  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => invoicesApi.deleteLine(invoice.id, lineId),
```

ersetzen durch

```tsx
  // Menge und Einzelpreis einer Position im Entwurf ändern (Paket 4, B; G21).
  // Immer nur eine Zeile in Arbeit; der Server rechnet Zeile und Summen neu.
  const [zeileInArbeit, setZeileInArbeit] = useState<{ id: string; menge: string; preis: string } | null>(null);
  const updateLineMutation = useMutation({
    mutationFn: ({ lineId, daten }: { lineId: string; daten: { quantity?: number; unit_price?: number } }) =>
      invoicesApi.updateLine(invoice.id, lineId, daten),
    onSuccess: () => {
      invalidate();
      setZeileInArbeit(null);
      toast.success('Position geändert');
    },
    onError: (e: any) => toast.error(getErrorMessage(e, 'Position konnte nicht geändert werden')),
  });
  const zeileSpeichern = (line: { id: string; quantity: number; unit_price: number }) => {
    if (!zeileInArbeit) return;
    const ergebnis = positionsaenderung(line, zeileInArbeit.menge, zeileInArbeit.preis);
    if ('fehler' in ergebnis) {
      toast.error(ergebnis.fehler);
      return;
    }
    if (Object.keys(ergebnis.daten).length === 0) {
      setZeileInArbeit(null);
      return;
    }
    updateLineMutation.mutate({ lineId: line.id, daten: ergebnis.daten });
  };

  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => invoicesApi.deleteLine(invoice.id, lineId),
```

`frontend/src/pages/Invoices.tsx` — in `InvoiceDetail`, Feld „Rechnungsdatum *“ des Entwurfs: diesen Block

```tsx
              <input
                type="date"
                value={headerEdit.invoice_date}
                onChange={(e) => { setHeaderEdit({ ...headerEdit, invoice_date: e.target.value }); setHeaderDirty(true); }}
                className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
              />
```

ersetzen durch

```tsx
              <input
                type="date"
                value={headerEdit.invoice_date}
                onChange={(e) => { setHeaderEdit({ ...headerEdit, invoice_date: e.target.value }); setHeaderDirty(true); }}
                className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
              />
              {/* Paket 4, B: festgeschrieben wird immer mit dem Ausstellungstag */}
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Beim Finalisieren gilt der Tag der Ausstellung; das Zahlungsziel in Tagen bleibt.
              </p>
```

`frontend/src/pages/Invoices.tsx` — in `InvoiceDetail`, Tabellenkopf der Positionen: diesen Block

```tsx
                <th className="text-right py-2">Summe</th>
                {isDraft && <th className="w-8"></th>}
```

ersetzen durch

```tsx
                <th className="text-right py-2">Summe</th>
                {isDraft && <th className="w-40"></th>}
```

`frontend/src/pages/Invoices.tsx` — in `InvoiceDetail`, Zellen Menge/Preis/Summe und Anfang der Aktionszelle (der Löschknopf `×` danach bleibt unverändert): diesen Block

```tsx
                  <td className="text-right py-2">
                    {line.quantity} {line.unit}
                  </td>
                  <td className="text-right py-2">{line.unit_price.toFixed(2)} €</td>
                  <td className="text-right py-2">{line.line_total.toFixed(2)} €</td>
                  {isDraft && (
                    <td className="text-right py-2">
                      <button
```

ersetzen durch

```tsx
                  {zeileInArbeit?.id === line.id ? (
                    <>
                      <td className="text-right py-2">
                        <div className="flex items-center justify-end gap-1">
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label="Menge"
                            value={zeileInArbeit.menge}
                            onChange={(e) => setZeileInArbeit({ ...zeileInArbeit, menge: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') zeileSpeichern(line);
                              // Nur die Zeile verwerfen: Modal.tsx schließt bei Escape
                              // über einen keydown-Listener auf document den Dialog.
                              if (e.key === 'Escape') { e.stopPropagation(); setZeileInArbeit(null); }
                            }}
                            className="w-20 px-2 py-1 text-right border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
                          />
                          <span>{line.unit}</span>
                        </div>
                      </td>
                      <td className="text-right py-2">
                        <div className="flex items-center justify-end gap-1">
                          <input
                            type="text"
                            inputMode="decimal"
                            aria-label="Einzelpreis"
                            value={zeileInArbeit.preis}
                            onChange={(e) => setZeileInArbeit({ ...zeileInArbeit, preis: e.target.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') zeileSpeichern(line);
                              // Nur die Zeile verwerfen: Modal.tsx schließt bei Escape
                              // über einen keydown-Listener auf document den Dialog.
                              if (e.key === 'Escape') { e.stopPropagation(); setZeileInArbeit(null); }
                            }}
                            className="w-24 px-2 py-1 text-right border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white rounded-md"
                          />
                          <span>€</span>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="text-right py-2">
                        {line.quantity} {line.unit}
                      </td>
                      <td className="text-right py-2">{line.unit_price.toFixed(2)} €</td>
                    </>
                  )}
                  <td className="text-right py-2">{line.line_total.toFixed(2)} €</td>
                  {isDraft && zeileInArbeit?.id === line.id && (
                    <td className="text-right py-2 whitespace-nowrap">
                      <button
                        type="button"
                        disabled={updateLineMutation.isPending}
                        onClick={() => zeileSpeichern(line)}
                        className="mr-3 text-minga-600 hover:text-minga-800 dark:text-minga-400"
                      >
                        Speichern
                      </button>
                      <button
                        type="button"
                        onClick={() => setZeileInArbeit(null)}
                        className="text-gray-500 hover:text-gray-700 dark:text-gray-400"
                      >
                        Abbrechen
                      </button>
                    </td>
                  )}
                  {isDraft && zeileInArbeit?.id !== line.id && (
                    <td className="text-right py-2 whitespace-nowrap">
                      <button
                        type="button"
                        title="Menge und Einzelpreis ändern"
                        disabled={updateLineMutation.isPending}
                        onClick={() => setZeileInArbeit({
                          id: line.id,
                          menge: eingabeAusZahl(line.quantity),
                          preis: eingabeAusZahl(line.unit_price),
                        })}
                        className="mr-3 text-gray-600 hover:text-gray-900 dark:text-gray-300"
                      >
                        Ändern
                      </button>
                      <button
```

- [ ] **Step 8: Prüfen.** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe. `grep -rn 'invoicesApi.updateLine' frontend/src | wc -l` → `1`. `grep -c "if (e.key === 'Escape') { e.stopPropagation(); setZeileInArbeit(null); }" frontend/src/pages/Invoices.tsx` → `2`. Paket-3-Abnahme (Stoppregel 4):

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -q -p no:cacheprovider -k "TestAbnahmeSepaBerlin or TestAbnahmeRechnungsberechtigung" 2>&1 | tail -1
```
→ `5 passed, 462 deselected`.

- [ ] **Commit:**

```bash
git add backend/app/api/v1/invoices.py backend/tests/test_paket4.py frontend/src/services/positionsaenderung.ts frontend/tests/unit/positionsaenderung.check.ts frontend/src/pages/Invoices.tsx
git commit -m "feat(rechnung): Menge und Einzelpreis einer Entwurfsposition direkt in der Tabelle ändern; Menge einer Sammelposition nur über die Bestellung (P4-B.5)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12 (B.6): Suche nach Nummer, Kunde oder Kundennummer in jedem Reiter (G05)

**Files:**
- Create: `frontend/src/services/rechnungssuche.ts` (ohne Importe)
- Create: `frontend/tests/unit/rechnungssuche.check.ts`
- Modify: `frontend/src/pages/Invoices.tsx` (Import; in `Invoices()`: `filteredInvoices`, `tabs`/`displayInvoices`, `<Tabs …/>`, Suchfeld)

**Interfaces:**
- Produces: `rechnungPasstZurSuche(rechnung: { invoice_number; customer_name?; customer_number? }, suche) -> boolean`.
- Consumes: `Invoice.customer_name`, `Invoice.customer_number` (API liefert beide).
- Verhalten: Suche wirkt in „Alle“, „Offen“, „Überfällig“, „Bezahlt“; Reiterzähler = Treffer mit aktueller Suche; Suche oder Reiterwechsel → Seite 1.

**Review Focus (B.6):** „Ökoring“ in „Offen“ und „Bezahlt“; `KD-10006`; `00010`; zwei Wörter („kern gmbh“); Zähler; auf Seite 2 suchen → Seite 1. Überfällig-Liste (eigener Endpunkt) filtert ebenso.

- [ ] **Step 1: Node-Prüfung zuerst.** Neue Datei `frontend/tests/unit/rechnungssuche.check.ts`:

```ts
// Prüft rechnungPasstZurSuche ohne Browser und ohne Testframework (Paket 4, B; G05).
// Lauf: node tests/unit/rechnungssuche.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { rechnungPasstZurSuche } from '../../src/services/rechnungssuche.ts';

const oekoring = { invoice_number: 'RE-2026-00010', customer_name: 'Ökoring Handels GmbH', customer_number: 'KD-10006' };
const entwurf = { invoice_number: 'ENTWURF-75939B849826', customer_name: 'Großer Kern GmbH' };
const ohneKunde = { invoice_number: 'RE-2026-00001', customer_name: null };

const faelle: Array<[typeof oekoring | typeof entwurf | typeof ohneKunde, string, boolean]> = [
  [oekoring, '', true],                    // leere Suche zeigt alles
  [oekoring, '   ', true],
  [oekoring, 'RE-2026-00010', true],       // Nummer
  [oekoring, '00010', true],               // Teil der Nummer
  [oekoring, 'ökoring', true],             // Kundenname, Groß/klein egal
  [oekoring, 'ÖKORING', true],
  [oekoring, 'handels öko', true],         // jedes Wort, Reihenfolge egal
  [oekoring, 'kd-10006', true],            // Kundennummer
  [oekoring, 'ökoring 00011', false],      // ein Wort passt nicht
  [oekoring, 'Kern', false],
  [entwurf, 'entwurf', true],              // Entwurf ohne Nummer
  [entwurf, 'großer', true],
  [ohneKunde, '00001', true],              // ohne Kundenname kein Absturz
  [ohneKunde, 'gmbh', false],
];

for (const [rechnung, suche, erwartet] of faelle) {
  assert.equal(rechnungPasstZurSuche(rechnung, suche), erwartet, `${rechnung.invoice_number} / "${suche}"`);
}
console.log(`rechnungssuche.check: ${faelle.length} Fälle ok`);
```

Run: `cd frontend && node tests/unit/rechnungssuche.check.ts` → Rot: `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '…/frontend/src/services/rechnungssuche.ts'`.

- [ ] **Step 2: Reine Funktion.** Neue Datei `frontend/src/services/rechnungssuche.ts`:

```ts
/**
 * Suche der Rechnungsliste „nach Nummer oder Kunde“ (Paket 4, B; G05).
 *
 * Gilt in jedem Reiter (Alle, Offen, Überfällig, Bezahlt) — bis Paket 4
 * wirkte sie nur unter „Alle“. Jedes Wort der Eingabe muss in der
 * Rechnungsnummer, im Kundennamen oder in der Kundennummer vorkommen;
 * Groß- und Kleinschreibung zählen nicht. Gesucht wird in der geladenen
 * Liste (die neuesten 100 Rechnungen, LISTENGRENZE in Invoices.tsx).
 *
 * Bewusst ohne Importe: tests/unit/rechnungssuche.check.ts lädt die Datei
 * direkt mit Node.
 */

export interface Suchbar {
  invoice_number: string
  customer_name?: string | null
  customer_number?: string | null
}

export function rechnungPasstZurSuche(rechnung: Suchbar, suche: string): boolean {
  const woerter = suche.toLocaleLowerCase('de-DE').split(/\s+/).filter(Boolean);
  if (woerter.length === 0) return true;
  const text = [rechnung.invoice_number, rechnung.customer_name, rechnung.customer_number]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase('de-DE');
  return woerter.every((wort) => text.includes(wort));
}
```

Run: `cd frontend && node tests/unit/rechnungssuche.check.ts` → `rechnungssuche.check: 14 Fälle ok`.

- [ ] **Step 3: Rechnungsliste.**

`frontend/src/pages/Invoices.tsx` — Importzeile `getErrorMessage`: diesen Block

```tsx
import { getErrorMessage } from '../services/errors';
```

ersetzen durch

```tsx
import { getErrorMessage } from '../services/errors';
import { rechnungPasstZurSuche } from '../services/rechnungssuche';
```

`frontend/src/pages/Invoices.tsx` — in `Invoices()`, nach `stornoMutation`: diesen Block

```tsx
  const filteredInvoices = invoices.filter(
    (invoice) =>
      invoice.invoice_number.toLowerCase().includes(search.toLowerCase()) ||
      invoice.customer_name?.toLowerCase().includes(search.toLowerCase())
  );
```

ersetzen durch

```tsx
  // Suche „nach Nummer oder Kunde“ — in jedem Reiter (Paket 4, B; G05)
  const passtZurSuche = (invoice: Invoice) => rechnungPasstZurSuche(invoice, search);
```

`frontend/src/pages/Invoices.tsx` — in `Invoices()`, Reiter und angezeigte Liste: diesen Block

```tsx
  const tabs = [
    { id: 'all', label: 'Alle', count: invoices.length },
    { id: 'open', label: 'Offen', count: invoices.filter((i) => i.status === 'OFFEN').length },
    { id: 'overdue', label: 'Überfällig', count: overdueInvoices.length },
    { id: 'paid', label: 'Bezahlt', count: invoices.filter((i) => i.status === 'BEZAHLT').length },
  ];

  const displayInvoices =
    activeTab === 'overdue'
      ? overdueInvoices
      : activeTab === 'open'
        ? invoices.filter((i) => i.status === 'OFFEN')
        : activeTab === 'paid'
          ? invoices.filter((i) => i.status === 'BEZAHLT')
          : filteredInvoices;
```

ersetzen durch

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

`frontend/src/pages/Invoices.tsx` — Reiterleiste: diesen Block

```tsx
      <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} className="mb-6" />
```

ersetzen durch

```tsx
      {/* Neuer Reiter oder neue Suche: zurück auf Seite 1, sonst bleibt ein
          Treffer auf einer leeren Seite unsichtbar. Kein useEffect: die
          Paket-3-Abnahme rendert diese Seite mit einem Ersatz, der nur
          useState kennt. */}
      <Tabs tabs={tabs} activeTab={activeTab} onChange={(id) => { setActiveTab(id); setCurrentPage(1); }} className="mb-6" />
```

`frontend/src/pages/Invoices.tsx` — Suchfeld in der `FilterBar`: diesen Block

```tsx
            value={search}
            onChange={(e) => setSearch(e.target.value)}
```

ersetzen durch

```tsx
            value={search}
            onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
```

- [ ] **Step 4: Prüfen.** `grep -c 'filteredInvoices' frontend/src/pages/Invoices.tsx` → `0`. `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe. Paket-3-Abnahme wie in B.5 Step 8 → `5 passed, 462 deselected`. `cd frontend && npm run build 2>&1 | tail -1` → `✓ built in …`.
- [ ] **Commit:**

```bash
git add frontend/src/services/rechnungssuche.ts frontend/tests/unit/rechnungssuche.check.ts frontend/src/pages/Invoices.tsx
git commit -m "fix(rechnung): Suche nach Nummer, Kunde oder Kundennummer wirkt in jedem Reiter (P4-B.6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13 (B.7): Abschluss B — Prüfungen, Vollauf, Build, Meldung (ohne Commit)

**Files:** keine Änderung.

- [ ] **Step 1:** Alle B-Klassen:

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4BFakturiert tests/test_paket4.py::TestP4BAusstellungsdatum tests/test_paket4.py::TestP4BLieferscheinBeimAusliefern tests/test_paket4.py::TestP4BSammelpositionMenge -q -p no:cacheprovider 2>&1 | tail -1
```

→ `21 passed`. `cd frontend && node tests/unit/positionsaenderung.check.ts && node tests/unit/rechnungssuche.check.ts && node tests/unit/dateiname.check.ts` → `20 Fälle ok`, `14 Fälle ok`, `8 Fälle ok` (nach O zusätzlich `node tests/unit/belegpfad.check.ts` → `35 Fälle ok`).
- [ ] **Step 2: Prozedur V** → N = Stand vor B.1 + 21, Abgleich leer (im Gesamtplan errechnet 1857).
- [ ] **Step 3: Statisch** (Befehle aus B.3) → wie dort.
- [ ] **Step 4: Frontend** — `tsc` ohne Ausgabe, `npm run build` → `✓ built in …`.
- [ ] **Step 5: Diff.** `git diff --stat <Basis-B>..HEAD` → genau diese 14 Dateien: `backend/app/api/v1/documents.py`, `backend/app/api/v1/invoices.py`, `backend/app/services/invoice_service.py`, `backend/app/services/lieferschein_service.py`, `backend/app/services/order_status_service.py`, `backend/tests/test_dunning.py`, `backend/tests/test_gernot_261008_paket3.py`, `backend/tests/test_paket4.py`, `frontend/src/components/domain/OrderDocumentsModal.tsx`, `frontend/src/pages/Invoices.tsx`, `frontend/src/services/positionsaenderung.ts`, `frontend/src/services/rechnungssuche.ts`, `frontend/tests/unit/positionsaenderung.check.ts`, `frontend/tests/unit/rechnungssuche.check.ts`. `git log --oneline <Basis-B>..HEAD` → sechs Commits (B.1–B.6).
- [ ] **Step 6: Abschlussmeldung** (kurz, mit Zeigern): `<Basis-B>`, Commit-Hashes, Rot/Grün je Task (erwartet vs. gemessen), Prozedur-V-Zeilen, `ruff`, `tsc`, Build, Node-Prüfungen, Paket-3-Abnahme; jede selbst behobene Anker- oder Redaktionsabweichung mit Datei und Funktion. Browser und Produktion macht der Manager.

---

## Abschnitt C — Belegstatus-Übersicht und Dateinamen mit Kundenname — Tasks 14–19 (C.1–C.6)

> **Rahmen:** Arbeitsort, Tests, Commits, Stoppregeln, Baseline und Prozedur V stehen im Kopf des Plans (Global Constraints). C.1–C.6 = Tasks 14–19. Ausnahme von „Bestehende Tests ändert kein Task“: C.2 Step 6 (= Task 15, Step 6; C-E12, 11 erwartete Dateinamen in `backend/tests/test_gernot_261008_paket3.py`). Die Abschlussmeldung in Task 19 ist ein Zwischenstand — nicht anhalten, danach folgt P4-D. Runbooks R-C0–R-C3 und die Offenen Punkte von C stehen am Ende des Plans.

**Goal:** Zwei Wünsche aus Gernots Feedback vom 08.10.2026:
- **Belegstatus (G14, G15, X07; G19 als Datenquelle):** Eine eigene Seite „Belegstatus“ zeigt je Bestellung, ob Lieferschein und Rechnung erstellt sind, ob die Rechnung versendet ist und ob sie bezahlt ist. Filter: Zeitraum (Liefertag), Kunde und „nur unvollständige“. Unvollständig heißt: geliefert, aber ohne Rechnung, nur mit Rechnungsentwurf oder mit nicht versendeter Rechnung. Dazu ein Endpunkt `GET /api/v1/belegstatus` mit Filtern und Seiten. Er hat dieselben Rechte wie die Rechnungen. Der FAKTURIERT-Altbestand, der vor NovaERP über DATEV abgerechnet wurde, erscheint als „extern (DATEV)“ und nicht als Lücke. Gernots Worte (B2): „Eine Übersicht, in der pro Bestellung sichtbar ist: Lieferschein erstellt ✔/✘, Rechnung erstellt ✔/✘, Rechnung versendet ✔/✘ (optional: bezahlt)“ und „Neue Seite/Tab „Belegstatus“ (oder Spalten in der Bestellliste) mit Filtern (Zeitraum, Kunde, „unvollständig“)“.
- **Dateinamen (G37, G38):** Download (Content-Disposition), Mailanhang und Versandprotokoll heißen künftig `<Belegnummer>_<Kundenname>.pdf`, z. B. `LS-20261008-0001_Fruchthof-Nagel-GmbH.pdf`. Der Kundenname wird bereinigt und auf 50 Zeichen begrenzt. Das gilt für Lieferschein, Rechnung (auch Sammel- und Monatsrechnung), Auftragsbestätigung und Packliste. Gernots Worte (B7): „Soll: `LS-20261008-001_Fruchthof-Nagel-GmbH.pdf` (Belegnr + Kundenname, Sonderzeichen/Umlaute/Leerzeichen sanitizen, Länge begrenzen). Gilt für Lieferschein, Rechnung, Sammelrechnung – beim Download und beim E-Mail-Anhang.“

**Architecture:**
- **Keine Schemaänderung, keine Migration** (`tenancy._auto_migrate` bleibt unberührt).
- **Dateinamen:** `app/services/beleg_dateiname.py` bekommt die reine Funktion `kundenteil(name)` und den Parameter `kunde` an `beleg_dateiname`, außerdem `bestellkunde(order)` und `rechnung_kunde(invoice)`. `rechnung_dateiname` setzt den Kunden selbst. `belegversand.versende_beleg` und `markiere_ohne_mail` reichen `kunde` durch. Die Aufrufer in `documents.py` (AB, LS, PL) und `invoices.py` (Rechnungsversand) übergeben ihn.
- **Belegstatus:** neues Modul `app/services/belegstatus.py` (Regeln, fünf Abfragen) und `app/schemas/belegstatus.py`. Der neue Router `app/api/v1/belegstatus.py` hängt in `main.py` mit `_deps_geld`.
- **Frontend:** `services/belegstatus.ts` (Typen und Anzeige, ohne Importe, Node-Prüfung), `services/belegstatusApi.ts` und `pages/Belegstatus.tsx`. Dazu eine Route in `App.tsx`, ein Navigationspunkt in `Layout.tsx`, ein Eintrag in der Schnellsuche (`CommandPalette.tsx`) und die Rollentexte in `rollen.ts`.

**Tech Stack:** FastAPI + SQLAlchemy 2.0, SQLite je Mandant, Pydantic v2, React 18 + TypeScript 5.9, TanStack Query 5, Node ≥ 23.6 (TypeScript ohne Build für `tests/unit/*.check.ts`).

**Ausgangsstand:** Geplant und durchgespielt auf `main` @ `df84f7b`. Ausgeführt wird C **nach** dem Merge von D/F/O (Plan `/tmp/n0910/plan.md`). Dieser Merge ist inzwischen auf `main` @ `521ed6d` („docs: Nachtrag 09.10. live …“). Kein Anker von C wird von D, F oder O geändert (siehe „Überschneidungen mit D/F/O“). Deshalb **setzt kein Schritt D/F/O voraus**. Die Revision hat C auf `521ed6d` vollständig nachgespielt (siehe Prüfstand). Rückt `main` vor Paket 4 weiter vor, spielt der Manager C dort erneut nach.

**Vorbedingung V-C1:** erfüllt — die Ausnahme C.2 Step 6 steht in den Global Constraints („Bestehende Tests“), zusammen mit denen von B und P4-D.

### Zuordnung der IDs

| ID | Wunsch | Status vorher (Abgleich, Kritik) | Hier |
|---|---|---|---|
| G14 | Übersicht je Bestellung: LS ✔/✘, RE ✔/✘, versendet ✔/✘, bezahlt | OFFEN | C.3 (Server), C.4/C.5 (Seite) |
| G15 | Filter Zeitraum, Kunde, „unvollständig“ | OFFEN | C.3 (`von`, `bis`, `kunde_id`, `nur_unvollstaendig`, Seiten), C.5 |
| G19 | Versand protokollieren (Grundlage für G14) | LIVE (Protokoll seit Paket 3; in Prod 0 Zeilen) | C.3 liest Protokoll **und** `sent_at` (C-E4); keine Änderung am Protokoll |
| X07 | Einzelkunden: je Lieferung eine Rechnung; „geliefert, nicht berechnet“ sichtbar | LIVE_TEILWEISE | C.3: `OHNE_RECHNUNG`. Prod 09.10.: BE-20261007-0003, BE-20261008-0002 (ohne LS), BE-20261008-0006. Kein Automatismus (Offener Punkt 6) |
| G37 | Download: Belegnummer + bereinigter Kundenname | OFFEN (Kritik korrigiert von LIVE_TEILWEISE) | C.1 (Regel), C.2 (Endpunkte) |
| G38 | Mailanhang: ebenso | OFFEN (Kritik korrigiert) | C.2 (`versende_beleg`, Versandprotokoll) |

### Prüfstand (gemessen, Repo unverändert)

- **Basis** `df84f7b` (`git archive`, `frontend/node_modules` als Symlink). Prozedur V ergab `14 failed, 1644 passed, 2 skipped, 1 error`, die Fehlernamen sind die 15 Baseline-Namen.
- **Nachspiel dieser Fassung aus dem Plantext** in `/tmp/p4-kopie-c5rev2`, frisch per `git archive df84f7b`, mit `/tmp/p4-c5rev-skripte/nachspiel.sh` (Protokoll `nachspiel-df84f7b.log`). Das Skript `/tmp/p4-c5rev-skripte/apply.py <Kopie> <Schritte>` liest die 90 `C-BLOCK`-Marker und übernimmt sie mechanisch. Ergebnis: `test_paket4.py` mit Kopf angelegt, 4 Anhänge, 7 neue Dateien (3 Backend, 4 Frontend) und 39 Ersetzungen mit je genau einem Treffer, Commits C.1–C.5. Alle Rot/Grün-Zahlen in den Steps stammen aus diesem Lauf:
  - Rot: C.1 `24 failed` (1/15/8 Meldungen), C.2 `7 failed` (7 Diff-Zeilen wie zitiert), C.3 `15 failed` (3/2/1/9/9/1), C.4 `ERR_MODULE_NOT_FOUND` bzw. `1 failed`, C.5 genau ein TS2307.
  - Grün: 24, 31, 15, 1 und 47 passed. Paket 3 zuerst `11 failed, 456 passed` (genau die 11), nach C.2 Step 6 `467 passed`. ruff F821/F823 Exit 0, `tsc` still, `npm run build` ✓, keine neuen Dateien in `node_modules`.
  - Prozedur V: 1644 → 1675 (nach C.2) → 1690 (nach C.3) → 1691 (Ende), jeweils `14 failed, 2 skipped, 1 error`, Abgleich leer. `git diff --stat` zeigt genau 18 Dateien.
- **Nachspiel auf dem gemergten `main` @ `521ed6d`** (D/F/O samt aller Nachbesserungen, live) in `/tmp/p4-kopie-c5rev-main` und noch einmal mit dem Skript in `/tmp/p4-kopie-c5rev-main2` (Protokoll `nachspiel-521ed6d.log`, gleich dem von `df84f7b` bis auf N):
  - Alle 39 Anker haben je 1 Treffer.
  - C-Klassen `47 passed`. `test_gernot_261008_paket3.py` `467 passed`, `test_nachtrag_0910.py` `174 passed`. ruff Exit 0.
  - `belegstatus.check` 29 Fälle ok, `tsc` still, Build ✓, Render-Probe in allen sechs Zuständen ok.
  - Prozedur V: vor C `14 failed, 1818 passed, 2 skipped, 1 error`, dann 1849 → 1864 → `1865 passed` (+47). Die Namen sind gleich der Baseline.
  - Zwischenstände mit demselben Ergebnis (+47 bzw. +44, Namen gleich): `60710b1` (D/F/O-Zweig, 1770 → 1817, Revision) und `bd56901` (Vorfassung im Review, 1709 → 1753).
  - Die Commits nach `bd56901` berühren keine Stelle von C. `invoices.py` ändert sich dort nur im Import aus `kontenrahmen` und in `update_invoice_line`.
- **Render-Probe der Seite** (ad hoc, nicht Teil der Tasks): `cd frontend && node /tmp/p4-c5rev-skripte/render-probe.js` rendert `Belegstatus.tsx` mit `react-dom/server` und Attrappen für Query, API, Layout und Dialog in sechs Zuständen. Ausgabe: `ok daten`, `ok leer`, `ok 403`, `ok fehler`, `ok server`, `ok zeitraum`.
  - Geprüft wurden unter anderem „LS-20261009-0001“, „Rechnung fehlt“, „nicht versendet“, „Monatsrechnung ab 01.11.2026“, „extern (DATEV)“, „Nur unvollständige (2)“, „Keine Bestellungen im Zeitraum“, „Keine Berechtigung für den Belegstatus“ und „Bitte prüfe die Verbindung zum Server“.
  - In allen sechs Zuständen stehen die Filter. „Erneut versuchen“ steht genau bei `fehler` und `server`, `server` zeigt den Text des Servers.
  - `zeitraum` (von 09.10., bis 01.10.): Die Abfrage ist aus (`enabled: false`). Es erscheinen „„von“ liegt nach „bis““ am Feld (`aria-invalid="true"`) und „Zeitraum ungültig“ in der Karte. Es erscheinen weder Zeilen noch die Zahl der vorigen Antwort.
  - Die Vorfassung der Seite fällt in dieser Probe durch.
- **Gegenproben (Mutationen an `app/services/belegstatus.py`, `/tmp/p4-c5rev-skripte/mutanten.py`):** Jede der folgenden Mutationen macht genau einen Test rot:
  - Protokoll ignoriert
  - Monatskunde sofort fällig
  - extern nie
  - Storno ignoriert (`and o.id not in mit_storno` entfernt)
  - `tag <= heute` statt `<`
  - Entwurf vor festgeschrieben
  - quittierter LS ignoriert

  Danach waren wieder alle 15 grün.
- **Gegenproben an `kundenteil`** (`/tmp/p4-c5rev-skripte/mutanten-c1.py`):
  - Apostroph erst nach NFKD entfernt: genau `test_bereinigung[akut-als-apostroph]` rot.
  - ø/æ/œ/ł/đ nicht umgeschrieben: genau `[nordisch]` und `[polnisch-kroatisch]` rot.
  - Wortschnitt bei `schnitt > 0`: genau `test_laenge_an_der_wortgrenze` rot.
- **Produktion `minga`, nur lesend** (`mode=ro`, Skripte unter `/tmp/p4-c-skripte`, `/tmp/p4-c-runbook`; Stand 09.10.2026):
  - **Bestellungen:**
    - 598 gesamt: 574 FAKTURIERT, 8 GELIEFERT, 3 BESTAETIGT, 11 ENTWURF, 2 STORNIERT.
    - Alle 574 FAKTURIERT haben **keine** aktive Rechnung im System. Sie gelten als extern abgerechnet.
  - **Lieferscheine:** 11, davon 10 ENTWURF und 1 GELIEFERT.
  - **Rechnungen:**
    - 7 vom Typ RECHNUNG: 4 offen (RE-2026-00001, -00005, -00008, -00010; die ersten beiden mit `sent_at`) und 3 storniert. Die 3 stornierten hängen an BE-20261007-0004 (RE-2026-00004) und BE-20261007-0005 (RE-2026-00002, -00003). Beide Bestellungen stehen auf GELIEFERT und haben eine aktive Neuausstellung. 0 FAKTURIERT-Bestellungen haben nur stornierte Rechnungen (`/tmp/p4-c5rev-skripte/storno-zaehlen.py`).
    - Dazu 3 Gutschriften (Stornos).
    - 7 Belege tragen eine `order_id`, 2 Lieferscheine eine `invoice_id`.
  - **Versand und Zahlungen:** `document_dispatches` hat 0 Zeilen, `payments` 0 Zeilen.
  - **Kunden:** 37 EINZELN, 9 MONATLICH.
  - **Belegstatus-Regeln als SQL-Spiegel** (`/tmp/p4-c-runbook/belegstatus-erwartung.py`, mit der Storno-Regel aus C-E3, Stichtag 09.10., in der Revision erneut gemessen): 596 Bestellungen ohne Storno, extern 574, **unvollständig 5**. Das sind die drei aus X07 sowie BE-20261007-0004 (RE-2026-00008) und BE-20261007-0005 (RE-2026-00010), beide nicht versendet.
  - **Kundennamen:** 46 Kunden. Sonderzeichen in Prod: `& ' ( ) , - . / Ö ß ä ö ü`. Mit `kundenteil` ist der längste bereinigte Name 48 Zeichen lang (roh 50). 0 werden gekürzt, 0 werden leer. Die Nachbesserungen der Revision (Akut, ø/æ/œ/ł/đ, Mindestlänge beim Wortschnitt) treffen keinen Prod-Namen.
- **Nicht gemessen:**
  - die Oberfläche im Browser (Manager-Abnahme R-C2)
  - der Mailversand an einen echten Server

### Entscheidungen (Manager; Gernot kann widersprechen, siehe „Offene Punkte“)

- **C-E1 — Eigene Seite statt Spalten in der Bestellliste.**
  - Die Bestellliste sehen auch Planung und Halle (`Layout.tsx`, `_deps_auftraege`). Rechnungs-, Versand- und Zahlstatus gehören nur zu den Rollen mit Rechnungssicht (`_deps_geld`: Admin, Vertrieb, Buchhaltung).
  - Die Bestellliste lädt höchstens 100 Bestellungen samt Positionen und hat eigene Filter. Die Seite „Belegstatus“ braucht Liefertag-Zeitraum, Kunde, „unvollständig“ und Seiten vom Server.
  - Je Zeile öffnet „Belege“ den vorhandenen Belege-Dialog der Bestellung (`OrderDocumentsModal`). Dort legt Gernot die fehlende Rechnung an oder versendet sie. Danach lädt die Zeile neu.
- **C-E2 — Ein Endpunkt `GET /api/v1/belegstatus` in eigenem Router mit `_deps_geld`.**
  - Er steht nicht in `invoices.py`. Dort ändert D mehrere Stellen (Importe, `update_invoice_line`, DATEV-Endpunkte), und eine Route `/invoices/belegstatus` müsste vor `/{invoice_id}` stehen, sonst antwortet der Server mit 422.
  - Parameter: `von`, `bis` (Liefertag), `kunde_id`, `nur_unvollstaendig`, `page`, `page_size` (höchstens 100, `PaginationParams`).
  - Antwort: `items`, `total`, `unvollstaendig` (Zahl für den Filter, unabhängig von `nur_unvollstaendig`) und `heute` (Stichtag Berlin).
  - `von > bis` ergibt 422 „„von“ liegt nach „bis““.
- **C-E3 — Regeln.** Es sind dieselben Wege wie bei Sammel- und Monatslauf, eine Quelle: `app/services/belegstatus.py`.
  - **Liefertag:** `actual_delivery_date`, sonst `requested_delivery_date`. Danach filtert der Zeitraum, absteigend sortiert, bei gleichem Tag nach Bestellnummer absteigend.
  - **Rechnung der Bestellung:** nicht storniert, Typ RECHNUNG. Sie hängt über `Invoice.order_id` oder über einen Lieferschein der Bestellung (`DeliveryNote.invoice_id`, Sammel- und Monatsrechnung) an der Bestellung, wie `InvoiceService.aktive_rechnung_zur_bestellung`. Eine festgeschriebene geht dem Entwurf vor. `sammelrechnung` ist wahr, wenn die Rechnung nicht über `order_id` an genau dieser Bestellung hängt.
  - **Geliefert:** Status GELIEFERT oder FAKTURIERT, ein quittierter Lieferschein, oder BESTAETIGT/IN_PRODUKTION mit Liefertag **vor** heute (Berlin). Gelieferte Bestellungen bleiben oft auf BESTAETIGT (Spec A1). Am Liefertag selbst ist eine bestätigte Bestellung noch nicht „geliefert“, die Halle fährt vielleicht erst. ENTWURF gilt ohne quittierten Lieferschein nie als geliefert (in Prod 7 alte Entwürfe, meist Abo, Offener Punkt 3).
  - **Fällig:** beim Einzelkunden ab dem Liefertag, beim Monatskunden ab dem 1. des Folgemonats. An diesem Tag legt der Monatslauf (B5) den Entwurf an, danach zeigt die Zeile `RECHNUNG_ENTWURF`, bis Gernot freigibt.
  - **Unvollständig (`luecken`, genau ein Code):** gilt, wenn die Bestellung geliefert, nicht extern abgerechnet und fällig ist, und einer dieser Fälle zutrifft:
    - `OHNE_RECHNUNG` (keine Rechnung)
    - `RECHNUNG_ENTWURF` (nur Entwurf)
    - `NICHT_VERSENDET` (festgeschrieben, nicht versendet)
  - **Extern abgerechnet:** FAKTURIERT ohne Rechnung im System. Das ist der Altbestand über DATEV, Spec-Nachtrag 08.10.2026, dieselbe Regel wie `_abrechenbare_lieferscheine`. Keine Lücke. Ohne Lieferschein zeigt die LS-Spalte „— extern“, Versand und Zahlung zeigen „—“.
  - **Storno schließt „extern“ aus:** Hängt an der Bestellung eine stornierte Rechnung (`Invoice.order_id`, Typ RECHNUNG), gilt sie nie als extern abgerechnet. FAKTURIERT setzt nur der Status-Endpunkt von Hand (oder der Import). `cancel_invoice` setzt den Bestellstatus nicht zurück. Ohne Neuausstellung zeigt die Zeile deshalb `OHNE_RECHNUNG` statt „extern (DATEV)“. Das Muster „storniert und neu“ kommt in Prod vor (BE-20261007-0005), betroffen sind heute 0 Bestellungen.
    - Grenze: Eine stornierte Sammel- oder Monatsrechnung hat keine `order_id`, und `cancel_invoice` löst ihre Lieferscheine (R1.6). Sie bleibt unsichtbar wie im Sammellauf (Offener Punkt 15).
    - Kosten: keine weitere Abfrage. Die Abfrage über `Invoice.order_id` liest jetzt auch stornierte Rechnungen und sortiert sie in Python aus.
  - **Stornierte Bestellungen fehlen.** Rechnungen ohne Bestellung (Leergut, von Hand) erscheinen nicht, denn die Übersicht ist je Bestellung.
- **C-E4 — Versendet = `sent_at` oder Versandprotokoll.**
  - `sent_at` setzt nur ein erfolgreicher Mailversand (Paket 3, Q2). Die Rechnungen aus der Zeit vor dem Protokoll haben nur `sent_at` (in Prod tragen RE-2026-00001 und RE-2026-00005 `sent_at`, im Protokoll stehen 0 Zeilen).
  - Ein Eintrag im Protokoll zählt auch ohne `sent_at`. Das gilt etwa für ein künftiges „ohne Mail als versendet markieren“ für Rechnungen (Offener Punkt 5).
  - `versendet_am` ist `sent_at`, sonst die erste Protokollzeile.
- **C-E5 — Bezahlt ist nur Anzeige** (`status == BEZAHLT`, sonst der Zahlstatus als Text), nie eine Lücke. Gernot: „optional: bezahlt“. Mahnwesen und offene Posten zeigt die Rechnungsseite.
- **C-E6 — Fehlender Lieferschein ist ✘ (grau), aber keine Lücke.**
  - Der Auftrag definiert „unvollständig“ als „geliefert, aber ohne Rechnung bzw. Rechnung nicht versendet“.
  - In Prod hat BE-20261007-0008 eine versendete Rechnung ohne Lieferschein. Das ist kein Fehler, wenn direkt aus der Bestellung abgerechnet wird.
  - Für Monatskunden meldet der Monatsdialog fehlende Lieferscheine schon (`OHNE_LIEFERSCHEIN`).
  - Ob ein fehlender LS künftig auch als Lücke zählt, ist Offener Punkt 1.
- **C-E7 — Seiten im Server nach dem Filtern in Python.**
  - „Unvollständig“ ist abgeleitet: Liefertag, Rechnungswege, Protokoll, Monatsregel. In SQL stünden die Regeln doppelt.
  - `minga` hat rund 600 Bestellungen. Der Endpunkt macht fünf Abfragen ohne N+1, die Auswahl der Bestellungen geht als Unterabfrage hinein. Die Vorgabe der Seite ist „von“ = 1. des Vormonats.
- **C-E8 — Dateiname `<Nummer>_<Kundenteil>.pdf`; Umlaute werden umgeschrieben, nicht erhalten.**
  - **Aufbau:**
    - Das Präfix (`RE-`, `LS-`, `AB-`, `PL-`, `Entwurf-`) bleibt vorn. Das braucht die Sortierung im Ordner und O.
    - Der Unterstrich trennt Nummer und Kunde eindeutig, denn der Kundenteil enthält nie „_“.
    - Ohne brauchbaren Namen (leer, nur Zeichen) bleibt es bei `<Nummer>.pdf`.
  - **Umlaute:** ä→ae, ö→oe, ü→ue, ß→ss (Ä→Ae …). Buchstaben, die NFKD nicht zerlegt, werden ebenso umgeschrieben: ø→oe, æ→ae, œ→oe, ł→l, đ→d (große entsprechend). Sonst fielen sie weg (`Søren` → `S-ren`). Andere Akzente entfallen (é→e). Apostrophe entfallen ebenso, auch der Akut „´“ (SIMPE'L, SIMPE´L → SIMPEL). Sie werden **vor** NFKD entfernt, denn NFKD macht aus „´“ ein Leerzeichen. Jede Folge anderer Zeichen wird „-“, also Leerzeichen, &, Punkt, Komma, Klammer und /. Gründe für das Umschreiben:
    1. Gernot verlangt es ausdrücklich („Sonderzeichen/Umlaute/Leerzeichen sanitizen“).
    2. ZIP aus dem Windows-Explorer (OEM-Codepage) und ältere Mailprogramme (RFC 2231) verstümmeln Umlaute in Dateinamen. DATEV-Belegupload und Steuerberater bekommen die Datei oft genau so.
    3. macOS legt Namen zerlegt ab (NFD). Gleich aussehende Namen sind dann byte-verschieden. Das ergibt Dubletten in OneDrive/Dropbox, und O fragt dann nicht „ersetzen?“.
    4. Heute weichen `filename=` (ASCII-Ersatz, ä→a, „Okoring“) und `filename*` voneinander ab. Mit reinem ASCII sind beide gleich.
  - **Deutsch umschreiben statt Akzent streichen,** damit „Mueller“ entsteht und nicht „Muller“.
  - **Rechtsformzusätze bleiben** als Wörter: `Ferdinand-Bierbichler-GmbH-Co-KG`, `Muenchner-Tafel-e-V`.
  - **Länge:** höchstens 50 Zeichen, gekürzt an einer Wortgrenze. Bliebe dabei weniger als die Hälfte (25 Zeichen), wird hart geschnitten, damit „A“ + Leerzeichen + 60 × „B“ nicht zu „A“ wird, sondern zu `A-` + 48 × `B`. Ein einzelnes überlanges Wort wird ebenso hart geschnitten. In Prod passt jeder der 46 Kunden ungekürzt, der längste hat 48 Zeichen. Der ganze Name bleibt unter 100 Zeichen (`attachment_filename` String(100)). Windows-Pfade bleiben auch im Belegordner weit unter 260.
- **C-E9 — Welcher Kundenname.** Es ist der Name, den das PDF druckt.
  - **Rechnung:** `rechnungsempfaenger(invoice, ist_entwurf)["name"]`. Bei einer festgeschriebenen Rechnung ist das der beim Festschreiben eingefrorene Empfänger (GoBD). Eine spätere Umbenennung des Kunden ändert den Dateinamen einer ausgestellten Rechnung nicht. Beim Entwurf gilt der aktuelle Kunde.
  - **AB, LS, PL:** `order.customer.name`, wie im PDF.
- **C-E10 — Geltungsbereich.**
  - **Gilt für:** Download, Mailanhang und Versandprotokoll von AB, LS, PL und Rechnung, also auch Sammel-, Monats-, Storno- und Leergutrechnung, denn sie laufen alle über `rechnung_dateiname` bzw. `/invoices/{id}/send`.
  - **Gilt nicht für:**
    - die Mahnung (`Zahlungserinnerung_<Nr>_Stufe<n>.pdf`)
    - DATEV- und SEPA-Exporte
    - die Ersatznamen im Frontend (`${nummer}.pdf`). Sie gelten nur, wenn der Kopf fehlt. CORS gibt `Content-Disposition` frei.
  - Gernot nannte LS, RE und Sammelrechnung. AB und PL folgen derselben Funktion im selben Dialog. Eine Regel für alle ist weniger überraschend (Offener Punkt 2).
- **C-E11 — Kein 409 durch die Umstellung.**
  - Der Versandnachweis (AB, LS) vergleicht `attachment_sha256`, also die Prüfsumme des PDF-Inhalts, nie den Dateinamen. Der Name steht nicht im PDF.
  - Belegt durch `test_erneuter_versand_nach_der_umstellung_ohne_409`:
    1. Zuerst geht der Beleg unter dem alten Namen hinaus (Protokollzeile auf `<Nummer>.pdf` gesetzt).
    2. Der erneute Versand antwortet mit 200.
    3. Beide Zeilen haben dieselbe Prüfsumme, die neue trägt den neuen Namen.
  - Rechnungen kennen keinen Inhaltsvergleich.
- **C-E12 — Bestandstests: 11 Erwartungen in `tests/test_gernot_261008_paket3.py` werden umgestellt.**
  - Die Tests `TestQ3Downloads` (4), `TestQ3Mailanhang` (3), `TestQ1AndereWege::test_mailen_eines_entwurfs_schreibt_fest_mit_echter_nummer` und je ein Versandtest aus `TestQ2AbVersand`, `TestQ2LsVersand` und `TestQ2Rechnungsversand` halten die alte Regel `{Nummer}.pdf` fest. Gemessen werden genau diese 11 rot.
  - Geändert wird nur der erwartete Name. Jede Zeile bekommt den Zusatz `# Paket 4, C`.
  - Das ist die einzige Ausnahme von „bestehende Tests unverändert“. Gernot will genau dieses Verhalten ändern.
  - `TestQ3Dateiname` (Regel ohne Kunde) bleibt unverändert grün. Die Paket-3-Abnahmetests (`TestAbnahme…`) berührt C nicht.
  - **Manager-Freigabe (Vorbedingung V-C1) — erfüllt:** Diese Ausnahme steht in den Global Constraints des Plans („Bestehende Tests“), zusammen mit denen von B und D (Text unter Offener Punkt 8). Abschnitt A schreibt „Bestehende Tests ändert kein Task“. Ohne den Eintrag widersprechen sich C.2 Step 6 und die Gesamtregeln. Der Hinweis für Worker von C nennt die Ausnahme zusätzlich, wie B und D es für ihre tun.
- **C-E13 — Rollen.** Der Navigationspunkt „Belegstatus“ unter „Vertrieb“ steht direkt hinter „Rechnungen“, mit denselben Rollen (`ADMIN`, `SALES`, `ACCOUNTING`). Die Halle und die Planung sehen ihn nicht, der Server antwortet ihnen mit 403. Die Rollentexte in `rollen.ts` nennen den Belegstatus, wie es der Kommentar dort verlangt („Wer die Matrix in main.py ändert, muss diese Texte mitziehen.“).
  - Die Schnellsuche (`CommandPalette.tsx`) bekommt „Belegstatus“ direkt hinter „Rechnungen“. Sie filtert heute nicht nach Rollen (nur „Benutzerverwaltung“ nach Admin), „Rechnungen“ steht dort für alle. „Belegstatus“ folgt dieser Regel. Wer keine Rechte hat, sieht auf der Seite „Keine Berechtigung für den Belegstatus“.
- **C-E14 — Fehler und ungültiger Zeitraum lassen die Filter stehen.**
  - Die Datumsfelder sperren mit `min`/`max` nur den Kalender. Per Tastatur geht „von“ nach „bis“. Der Server antwortet darauf mit 422.
  - Deshalb fragt die Seite bei „von“ > „bis“ nicht (`enabled: false`). Am Feld „bis“ steht „„von“ liegt nach „bis““, in der Karte „Zeitraum ungültig“. Zeilen und die Zahl der vorigen Antwort (`keepPreviousData`) werden nicht gezeigt.
  - Jeder Abfragefehler steht in der Karte unter der FilterBar, nie statt der Seite. Bei 403 steht „Keine Berechtigung für den Belegstatus“ ohne Knopf. Ohne Antwort steht der Verbindungshinweis, sonst der Text des Servers. In beiden Fällen gibt es „Erneut versuchen“.

### Überschneidungen mit D/F/O

Geprüft gegen `/tmp/n0910/plan.md` und am Code von `main` @ `521ed6d`. Jeder der 39 Anker von C fehlt im Plantext (`grep -cF` = 0) und hat auf `521ed6d` genau 1 Treffer. Keine Datei von C wird von D/F/O an derselben Stelle geändert.

| Datei | Stelle in C | D/F/O-Task | Stelle dort | Folge |
|---|---|---|---|---|
| `backend/app/services/belegversand.py` | Modul-Docstring (Zeile „Anhang heißt wie der Beleg …“), Signaturen und Dateinamen in `versende_beleg` und `markiere_ohne_mail` | **F.3 (Nachtrag-Task 8)** | `gruss` ersetzt, neu `absendername` davor | Getrennte Funktionen. Beide Reihenfolgen gehen, kein Schritt setzt F voraus. Die F-Tests prüfen Text und Betreff der Mail, nicht `attachment_filename`. `test_ab_nach_dem_setzen_der_firmendaten_erneut_sendbar` vergleicht Prüfsummen und bleibt grün (C-E11). |
| `backend/app/api/v1/invoices.py` | Importzeile aus `beleg_dateiname`; Aufruf `versende_beleg(...)` in `send_invoice_email` | **D.2–D.4 (Nachtrag-Tasks 2–4)** | Importzeilen aus `datev_service`, `kontenrahmen`, `app.schemas.invoice`; `update_invoice_line`, `export_datev`, `download_datev_export`, neu `GET /invoices/datev-export/einstellungen` | Getrennte Zeilen und Funktionen. Beide Reihenfolgen gehen. |
| `frontend/src/components/domain/OrderDocumentsModal.tsx` | nur importiert (`OrderDocumentsModal`, Props `open`/`onClose`/`order`) | **O.4 (Nachtrag-Task 14)** | `belegPdf`, `downloadInvoicePdf`, Knöpfe AB/LS/PL | Props und Export bleiben. Nach O laufen die Downloads im Dialog, auch vom Belegstatus aus, über `belegHerunterladen`. |
| `frontend/src/services/api.ts` | **nicht geändert**. C nutzt `export default api`, `salesApi.getOrder` und `salesApi.listCustomers` | **D.5 (Nachtrag-Task 5), O.4 (Nachtrag-Task 14)** | `invoicesApi`, vor `AppSettingResponse`; `documentsApi` | Kein Anker in `api.ts`. Deshalb steht die Belegstatus-API in einer eigenen Datei `belegstatusApi.ts`. |
| Dateinamen (fachlich) | Server liefert `<Nummer>_<Kunde>.pdf` | **O (Nachtrag-Tasks 11–15), O-E1, O-E3, O-E4** | Der Belegordner speichert `dateinameAusHeader(kopf, ersatzname)` unter `<Belegart>/<JJJJ-MM>/` | **O funktioniert unverändert.** Die Belegart kommt aus dem Objekt, nicht aus dem Namen (O-E1). Der Monat kommt aus dem Belegdatum. O speichert den neuen Namen, `sichererName` ändert ihn nicht (nur `A–Z a–z 0–9 - _ .`, Test `test_kopf_ascii_filename_gleich_filename_stern`). Die O-Tests (`TestOBelegordner`) arbeiten mit eigenen Köpfen und bleiben grün. **Wirkung:** Die Texte „`<Belegnummer>.pdf`“ in O-Ziel, O-Abnahme C2/C3/C5/C13/C16 und O-Offener-Punkt 2 heißen nach Paket 4 „`<Belegnummer>_<Kunde>.pdf`“. Liegt ein Beleg schon unter dem alten Namen im Belegordner, legt ein neuer Download die neue Datei **daneben**, ohne Ersetzen-Rückfrage, weil der Name ein anderer ist. Das passiert einmal je Beleg und ist kein Fehler (Runbook R-C3, Nachricht an Gernot). |
| Belegstatus „extern (DATEV)“ (fachlich) | FAKTURIERT ohne Rechnung | **D (Nachtrag-Tasks 1–5)** | DATEV-Export im Kontenrahmen, Exportsperre | Keine Code-Berührung. Belegstatus liest `datev_exported` nicht. „extern (DATEV)“ meint den Altbestand vor NovaERP, nicht D's Export. |
| `backend/tests/` | `test_paket4.py` (neu/angehängt), `test_gernot_261008_paket3.py` (11 Erwartungen, C-E12) | D/F/O: `test_nachtrag_0910.py` | — | Keine gemeinsame Testdatei. D/F/O ändern `test_gernot_261008_paket3.py` nicht (n0910 „Nicht geändert“). Keine Erwartung in `test_nachtrag_0910.py` hängt am Server-Dateinamen (`grep` nach `content-disposition`/`attachment_filename`: nur O-Attrappen). |
| `main.py`, `App.tsx`, `Layout.tsx`, `CommandPalette.tsx`, `rollen.ts`, `documents.py` | Router, Route, Navigation, Schnellsuche, Rollentexte, AB/LS/PL | — | n0910: `main.py` und `Layout.tsx` „Nicht geändert“, `App.tsx`, `CommandPalette.tsx`, `rollen.ts` und `documents.py` kommen nicht vor; `git diff df84f7b..521ed6d` berührt keine dieser Dateien | Keine Überschneidung mit D/F/O. **Innerhalb Paket 4:** Andere Abschnitte könnten an denselben Ankern einfügen, etwa an `from app.api.v1 import sepa`, am `invoices.router`-Block, an der `invoices`-Route oder an den Einträgen „Rechnungen“. Alle Einfügungen von C stehen **hinter** dem Anker, und der Anker selbst bleibt unverändert. |

**Innerhalb Paket 4** (nicht verlangt, geprüft gegen `/tmp/p4/A.md`, `B.md`, `D.md`, Stand 09.10. 18:47): Keiner der 39 Anker von C kommt dort vor, auch keine der Zielzeilen in `rollen.ts`, `Layout.tsx` und `CommandPalette.tsx`.
- **B:**
  - `documents.py`: die Importzeilen aus `pdf_service`/`app.models.documents`/`app.schemas.documents`, `_next_document_number` und `create_delivery_note`
  - `invoices.py`: `add_invoice_line`, `update_invoice_line`
  - `invoice_service.py`: `BestellungFakturiert`, `festschreiben`
  - `test_gernot_261008_paket3.py`: `TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum`
  - außerdem `OrderDocumentsModal.tsx` und `Invoices.tsx`
  - **Fachlich, B-E1 (`BestellungFakturiert`):** Nach B antwortet `POST /invoices/from-order/{id}` für eine FAKTURIERT-Bestellung mit 409. Deshalb legt `test_fakturiert_ohne_rechnung_ist_extern_abgerechnet` (C.3) die Rechnungen an, **bevor** es FAKTURIERT setzt. So läuft der Test vor und nach B grün. Gemessen mit den vier B.1-Ersetzungen aus `B.md` in einer Kopie (`/tmp/p4-c5rev-skripte/b1-simulation.py`): `TestP4CBelegstatus` und die Dateinamen-Tests haben `22 passed`. Die Vorfassung des Tests scheitert dort mit `assert 409 == 201`.
  - **Fachlich, B-E1 und Storno-Regel (C-E3):** Eine FAKTURIERT-Bestellung, deren einzige NovaERP-Rechnung storniert ist, zeigt `OHNE_RECHNUNG`. Nach B lässt sie sich in NovaERP nicht neu berechnen (409), und der Belegdialog bietet den Knopf nicht an (B.4). Die Zeile bleibt so lange eine Lücke, bis der Manager den Widerspruch auflöst (Offener Punkt 15). In Prod gibt es 0 solche Fälle.
- **D (Paket 4):**
  - `rollen.ts`: Text „Produktion“, neue Konstanten vor `rollenInfo`. C ändert die Texte „Vertrieb“ und „Buchhaltung“.
  - `Customers.tsx`, `core/rollen.py`, `sales.py`, `schemas/customer.py`
  - `test_gernot_261008_paket3.py`: zwei Tests aus Q4/Q7
  - `App.tsx`, `Layout.tsx` und `CommandPalette.tsx` bleiben in D unberührt (E-D7 Variante a). D prüft dort nur `'nav-customers'`/`'action-new-customer'` (Zählung 2), und der neue Eintrag `nav-belegstatus` ändert diese Zählung nicht.

Alles davon liegt neben den Stellen von C. Gemeinsam nutzen alle Abschnitte den Kopf von `test_paket4.py`. C legt ihn nur an, wenn er fehlt.

### File Structure (C)

18 Dateien, davon 7 neu. Commits: 5 (C.1–C.5). C.6 committet nichts.

| Datei | Task | Verantwortung |
|---|---|---|
| `backend/app/services/beleg_dateiname.py` | C.1, C.2 | `KUNDE_MAX_ZEICHEN`, `kundenteil`, `beleg_dateiname(…, kunde=)`, `bestellkunde`, `rechnung_kunde`, `rechnung_dateiname` mit Kunde |
| `backend/app/services/belegversand.py` | C.2 | `versende_beleg(…, kunde=)`, `markiere_ohne_mail(…, kunde=)`, Docstring |
| `backend/app/api/v1/documents.py` | C.2 | Import `bestellkunde`; AB/LS markieren und versenden; Downloads AB/LS/PL |
| `backend/app/api/v1/invoices.py` | C.2 | Import `rechnung_kunde`; `send_invoice_email` → `versende_beleg(…, kunde=)` |
| `backend/tests/test_gernot_261008_paket3.py` | C.2 | 11 erwartete Dateinamen (C-E12) |
| `backend/app/schemas/belegstatus.py` | C.3 | **neu**: `BelegstatusLieferschein`, `BelegstatusRechnung`, `BelegstatusZeile`, `BelegstatusListe` |
| `backend/app/services/belegstatus.py` | C.3 | **neu**: `belegstatus(db, *, heute, von, bis, kunde_id)`, `rechnung_faellig_ab`, Codes `OHNE_RECHNUNG`/`RECHNUNG_ENTWURF`/`NICHT_VERSENDET` |
| `backend/app/api/v1/belegstatus.py` | C.3 | **neu**: `GET /belegstatus` |
| `backend/app/main.py` | C.3 | Import, `include_router` hinter `invoices.router` mit `_deps_geld` |
| `backend/tests/test_paket4.py` | C.1–C.4 | ggf. **neu** (Kopf), Blöcke C anhängen: 47 Tests |
| `frontend/tests/unit/belegstatus.check.ts` | C.4 | **neu**: Node-Prüfung, 29 Fälle |
| `frontend/src/services/belegstatus.ts` | C.4 | **neu**, ohne Importe: Typen, `datumKurz`, `heuteBerlin`, `vorgabeVon`, vier Zellen, `LUECKEN_TEXT` |
| `frontend/src/services/belegstatusApi.ts` | C.5 | **neu**: `belegstatusApi.liste(filter)` |
| `frontend/src/pages/Belegstatus.tsx` | C.5 | **neu**: Seite |
| `frontend/src/App.tsx` | C.5 | Import, Route `belegstatus` |
| `frontend/src/components/common/Layout.tsx` | C.5 | Icon `ListChecks`, Navigationspunkt |
| `frontend/src/components/common/CommandPalette.tsx` | C.5 | Icon `ListChecks`, Eintrag `nav-belegstatus` hinter `nav-invoices` |
| `frontend/src/services/rollen.ts` | C.5 | Rollentexte Vertrieb, Buchhaltung |

**Nicht geändert (geprüft):** `tenancy.py`, die Modelle, `pdf_service.py` (nur gelesen: `rechnungsempfaenger`), `email_service.py`, `frontend/src/services/api.ts`, `frontend/src/services/dateiname.ts`, `Orders.tsx`, `Invoices.tsx`, `OrderDocumentsModal.tsx`, `Settings.tsx`, alle Paket-3-Abnahmetests (`TestAbnahme…`).

### Rahmen C (vor Task 14)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis C>` in den Bericht.
- Es gelten die Global Constraints des Plans: Tests nur in `test_paket4.py` (`TestP4C…`, `_p4c_…`, `_P4C_…`), Ausnahme C.2 Step 6, Node ≥ 23.6 im PATH (`TestP4CBelegstatusAnzeige` ruft `node` aus pytest auf, nie überspringen), „Lauf C“, Prozedur V, Frontend, Statisch, Stoppregeln 1–5. **Stoppregel 4** umfasst in C: C.2 Step 5 zeigt **andere** rote Paket-3-Tests als die 11 genannten.
- **N durch C:** +24 (C.1), +31 (nach C.2), +46 (nach C.3), +47 (nach C.4, Ende). Gemessen auf `df84f7b` 1644 → 1675 → 1690 → 1691, auf `main` @ `521ed6d` 1818 → 1849 → 1864 → 1865; im Gesamtplan (nach A und B) errechnet 1857 → 1881 → 1888 → 1903 → 1904. Maßgeblich sind die Namen.

---

### Task 14 (C.1): Dateiname-Regel — Nummer und bereinigter Kundenname

**Files:**
- Create or append: `backend/tests/test_paket4.py`
- Modify: `backend/app/services/beleg_dateiname.py` (Modul-Docstring, `beleg_dateiname`; davor neu `KUNDE_MAX_ZEICHEN`, `_UMLAUTE`, `_APOSTROPHE`, `_TRENNER`, `kundenteil`)

**Interfaces:**
- Produces:
  - `kundenteil(name: Optional[str]) -> str` (leer, wenn nichts übrig bleibt) und `KUNDE_MAX_ZEICHEN = 50`.
  - `beleg_dateiname(nummer, *, entwurf=False, kunde=None) -> str`. Ohne `kunde` ist das Ergebnis byte-gleich mit heute, `TestQ3Dateiname` bleibt grün.
- Consumes: `ENTWURF_PRAEFIX`, `_VERBOTEN` (bestehend).

**Review Focus (C.1):**
- Umlaute werden deutsch umgeschrieben (Ae/Oe/Ue groß, ae/oe/ue/ss klein). Zerlegte Umlaute (NFD) werden vorher zusammengesetzt. ø/æ/œ/ł/đ werden umgeschrieben statt verworfen.
- Apostrophe trennen kein Wort, auch der Akut „´“ nicht. Sie werden vor NFKD entfernt.
- Gekürzt wird an der Wortgrenze. Ein Wort, das genau an der Grenze endet, bleibt ganz. Bliebe weniger als die Hälfte, wird hart geschnitten.
- Der Name enthält nur `[A-Za-z0-9._-]`.

- [ ] **Step 1: Testdatei und Testblock**

Fehlt `backend/tests/test_paket4.py`, wird sie mit genau diesem Kopf angelegt. Gibt es die Datei schon, weil ein anderer Abschnitt von Paket 4 vorher lief, bleibt ihr Kopf, wie er ist:

<!-- C-BLOCK: c-kopf -->
```python
"""Paket 4 — Tests (Abschnitte A, B, C, D).

Jeder Abschnitt hängt seinen Block ans Dateiende. Klassen TestP4A…/TestP4B…/
TestP4C…/TestP4D…, Helfer _p4a_…/_p4b_…/_p4c_…/_p4d_…, keine autouse-Fixture,
Fixture client aus tests/conftest.py. Einzeltests über Klassen-IDs, nie -k.
"""
```

Dann diesen Block ans Dateiende anhängen. Er beginnt mit zwei Leerzeilen:

<!-- C-BLOCK: c1-tests -->
```python


# ---------------------------------------- Abschnitt C: Dateiname mit Kundenname (C.1)
import pytest  # noqa: E402


class TestP4CDateiname:
    """Gernot 08.10. (B7): LS-20261008-001_Fruchthof-Nagel-GmbH.pdf — Nummer,
    Unterstrich, bereinigter Kundenname. Die Regel, ohne Datenbank."""

    def test_nummer_und_kunde(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("LS-20261008-0001", kunde="Fruchthof Nagel GmbH") == (
            "LS-20261008-0001_Fruchthof-Nagel-GmbH.pdf")
        assert beleg_dateiname("RE-2026-00008", kunde="Großer Kern GmbH") == "RE-2026-00008_Grosser-Kern-GmbH.pdf"

    @pytest.mark.parametrize("name, teil", [
        # Kundennamen aus Produktion (minga, 09.10.2026)
        pytest.param("Ökoring Handels GmbH", "Oekoring-Handels-GmbH", id="umlaut-vorn"),
        pytest.param("Ferdinand Bierbichler GmbH & Co. KG", "Ferdinand-Bierbichler-GmbH-Co-KG", id="gmbh-co-kg"),
        pytest.param("SIMPE'L regional&unverpackt", "SIMPEL-regional-unverpackt", id="apostroph-und"),
        pytest.param("BODAN Großhandel für Naturkost GmbH", "BODAN-Grosshandel-fuer-Naturkost-GmbH", id="eszett"),
        pytest.param("Münchner Tafel e. V.", "Muenchner-Tafel-e-V", id="e-v"),
        pytest.param("Engelsberger Hofladen (R. u. D. Reichlmayr GbR)",
                     "Engelsberger-Hofladen-R-u-D-Reichlmayr-GbR", id="klammern"),
        pytest.param("Restaurant Eschenrieder Hof/Golfclub Sohyl Sediq",
                     "Restaurant-Eschenrieder-Hof-Golfclub-Sohyl-Sediq", id="schraegstrich"),
        pytest.param("Cafe Lido Gastronomiebetriebs GmbH & Co.KG", "Cafe-Lido-Gastronomiebetriebs-GmbH-Co-KG",
                     id="co-kg-ohne-leerzeichen"),
        # Akzente, zerlegte Umlaute (macOS), Leerraum, Anführungszeichen
        pytest.param("Café Crème", "Cafe-Creme", id="akzente"),
        pytest.param("Mu\u0308nchner Gru\u0308nkern", "Muenchner-Gruenkern", id="nfd"),
        pytest.param("  Hofladen\t\"Süd\"\n ", "Hofladen-Sued", id="leerraum"),
        pytest.param("ÄÖÜ äöü ß", "AeOeUe-aeoeue-ss", id="alle-umlaute"),
        # Akut als Apostroph (NFKD machte daraus ein Leerzeichen) und Buchstaben,
        # die NFKD nicht zerlegt (sie fielen sonst weg)
        pytest.param("SIMPE´L Hofladen", "SIMPEL-Hofladen", id="akut-als-apostroph"),
        pytest.param("Søren Ærø Œuvre", "Soeren-Aeroe-Oeuvre", id="nordisch"),
        pytest.param("Łódź Đurić", "Lodz-Duric", id="polnisch-kroatisch"),
    ])
    def test_bereinigung(self, name, teil):
        from app.services.beleg_dateiname import kundenteil
        assert kundenteil(name) == teil

    def test_laenge_an_der_wortgrenze(self):
        from app.services.beleg_dateiname import KUNDE_MAX_ZEICHEN, kundenteil
        assert KUNDE_MAX_ZEICHEN == 50
        lang = "Bayerische Landesanstalt für Landwirtschaft Institut für Ökologischen Landbau"
        assert kundenteil(lang) == "Bayerische-Landesanstalt-fuer-Landwirtschaft"
        # Wort endet genau an der Grenze: bleibt ganz
        assert kundenteil("A" * 50 + " GmbH") == "A" * 50
        # ein einziges langes Wort: harter Schnitt
        assert kundenteil("X" * 70) == "X" * 50
        # der Wortschnitt ließe weniger als die Hälfte übrig ("A"): harter Schnitt
        assert kundenteil("A " + "B" * 60) == "A-" + "B" * 48

    @pytest.mark.parametrize("kunde", [None, "", "   ", "!!!", "„“"], ids=["none", "leer", "leerzeichen", "zeichen", "anfuehrung"])
    def test_ohne_brauchbaren_namen_wie_bisher(self, kunde):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("RE-2026-00002", kunde=kunde) == "RE-2026-00002.pdf"

    def test_entwurf_mit_kunde(self):
        from app.services.beleg_dateiname import beleg_dateiname
        assert beleg_dateiname("ENTWURF-AB12CD34EF56", kunde="Ökoring Handels GmbH") == (
            "Entwurf-AB12CD34EF56_Oekoring-Handels-GmbH.pdf")
        assert beleg_dateiname("RE-2026-00003", entwurf=True, kunde="Ökoring Handels GmbH") == (
            "Entwurf-RE-2026-00003_Oekoring-Handels-GmbH.pdf")

    def test_kopf_ascii_filename_gleich_filename_stern(self):
        """Nur A–Z, a–z, 0–9, '-', '_', '.': filename= und filename* tragen
        denselben Namen, und der Belegordner (O, sichererName) ändert nichts."""
        import re
        from app.services.beleg_dateiname import beleg_dateiname, content_disposition
        name = beleg_dateiname("AB-20261009-0001", kunde="Hamberger Großmarkt GmbH & Co. KG")
        assert name == "AB-20261009-0001_Hamberger-Grossmarkt-GmbH-Co-KG.pdf"
        assert re.fullmatch(r"[A-Za-z0-9._-]+", name)
        assert content_disposition(name) == f"attachment; filename=\"{name}\"; filename*=UTF-8''{name}"

```

Prüfen: `grep -c '^class TestP4CDateiname' backend/tests/test_paket4.py` → `1`.

- [ ] **Step 2: Rot bestätigen**

Run: Lauf C mit `tests/test_paket4.py::TestP4CDateiname` (ohne `| tail -1`, um die Meldungen zu sehen).
Erwartet: **`24 failed`**. Die Meldungen (`… 2>&1 | grep -E '^E   [A-Za-z]' | sort | uniq -c`):
```
   1 E   ImportError: cannot import name 'KUNDE_MAX_ZEICHEN' from 'app.services.beleg_dateiname' (…/backend/app/services/beleg_dateiname.py)
  15 E   ImportError: cannot import name 'kundenteil' from 'app.services.beleg_dateiname' (…/backend/app/services/beleg_dateiname.py)
   8 E   TypeError: beleg_dateiname() got an unexpected keyword argument 'kunde'
```

- [ ] **Step 3: Implementierung**

In `backend/app/services/beleg_dateiname.py` den Anfang des Modul-Docstrings

<!-- C-BLOCK: c1-doc-alt -->
```python
"""Dateinamen der Belege (B7, Gernot 08.10.2026).

Ein Beleg heißt wie seine Nummer: ``RE-2026-00002.pdf``,
``AB-20261008-0001.pdf``, ``LS-20261008-0001.pdf``, ``PL-20261008-0001.pdf``.
Download (Content-Disposition) und Mailanhang nehmen dieselbe Funktion.
```

ersetzen durch:

<!-- C-BLOCK: c1-doc-neu -->
```python
"""Dateinamen der Belege (B7, Gernot 08.10.2026; Kundenname: Paket 4, C).

Ein Beleg heißt wie seine Nummer, dahinter der bereinigte Kundenname:
``RE-2026-00002_Oekoring-Handels-GmbH.pdf``,
``LS-20261008-0001_Fruchthof-Nagel-GmbH.pdf`` (AB und PL ebenso). Ohne
brauchbaren Kundennamen nur die Nummer. Download (Content-Disposition),
Mailanhang und Versandprotokoll nehmen dieselbe Funktion. Der Name trägt nur
A–Z, a–z, 0–9, "-", "_" und ".": filename= und filename* sind gleich, und
Windows, macOS, ZIP-Archive und Mailprogramme nehmen ihn unverändert.
```

Die Zeilen ab „Ein Rechnungsentwurf heißt …“ bleiben. Dann die Funktion

<!-- C-BLOCK: c1-alt -->
```python
def beleg_dateiname(nummer: Optional[str], *, entwurf: bool = False) -> str:
    """``{Nummer}.pdf``; Platzhalter ``ENTWURF-…`` oder ``entwurf=True`` → ``Entwurf-….pdf``."""
    name = _VERBOTEN.sub("_", (nummer or "").strip())
    if name.startswith(ENTWURF_PRAEFIX):
        name = name[len(ENTWURF_PRAEFIX):]
        entwurf = True
    name = name or "Beleg"
    return f"Entwurf-{name}.pdf" if entwurf else f"{name}.pdf"
```

ersetzen durch:

<!-- C-BLOCK: c1-neu -->
```python
#: Höchstlänge des Kundenteils nach der Bereinigung. Alle 46 Kunden von
#: MingaGreens passen ungekürzt (längster bereinigt 48 Zeichen, 09.10.2026);
#: der ganze Name bleibt unter 100 Zeichen (document_dispatches.attachment_filename).
KUNDE_MAX_ZEICHEN = 50
# Umlaute wie im Deutschen umschreiben (Müller → Mueller, nicht Muller); dazu
# die Buchstaben, die NFKD nicht zerlegt (ø, æ, œ, ł, đ) — sie fielen sonst weg
_UMLAUTE = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS",
    "ø": "oe", "Ø": "Oe", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
})
# Apostrophe fallen weg (SIMPE'L → SIMPEL), statt ein Wort zu teilen — vor
# NFKD, denn NFKD macht aus dem Akut "´" ein Leerzeichen
_APOSTROPHE = re.compile(r"['’‘`´ʼ]")
_TRENNER = re.compile(r"[^A-Za-z0-9]+")


def kundenteil(name: Optional[str]) -> str:
    """Kundenname als Teil eines Dateinamens (Gernot 08.10.2026, B7).

    Umlaute und ß werden umgeschrieben (ä → ae), ebenso ø/æ/œ (→ oe/ae/oe)
    und ł/đ (→ l/d); andere Akzente entfallen (é → e), Apostrophe ebenso
    (auch "´"); jede Folge anderer Zeichen (Leerzeichen, &, Punkt, Klammer, /)
    wird ein "-". Rechtsformzusätze bleiben:
    "Ferdinand Bierbichler GmbH & Co. KG" → "Ferdinand-Bierbichler-GmbH-Co-KG".
    Höchstens KUNDE_MAX_ZEICHEN Zeichen, gekürzt an einer Wortgrenze; bliebe
    dabei weniger als die Hälfte, wird hart geschnitten (ebenso ein einzelnes
    überlanges Wort). Leer, wenn nichts übrig bleibt.
    """
    text = _APOSTROPHE.sub("", unicodedata.normalize("NFC", name or "").translate(_UMLAUTE))
    text = "".join(z for z in unicodedata.normalize("NFKD", text) if not unicodedata.combining(z))
    teil = _TRENNER.sub("-", text).strip("-")
    if len(teil) > KUNDE_MAX_ZEICHEN:
        kopf = teil[:KUNDE_MAX_ZEICHEN + 1]  # endet ein Wort genau an der Grenze, bleibt es ganz
        schnitt = kopf.rfind("-")
        # Wortgrenze nur, wenn mindestens die Hälfte bleibt ("A-BBB…" nicht zu "A")
        teil = kopf[:schnitt] if schnitt >= KUNDE_MAX_ZEICHEN // 2 else teil[:KUNDE_MAX_ZEICHEN]
    return teil.strip("-")


def beleg_dateiname(nummer: Optional[str], *, entwurf: bool = False, kunde: Optional[str] = None) -> str:
    """``{Nummer}_{Kunde}.pdf`` (Kunde über ``kundenteil``), ohne brauchbaren
    Kundennamen ``{Nummer}.pdf``. Platzhalter ``ENTWURF-…`` oder
    ``entwurf=True`` → ``Entwurf-…``."""
    name = _VERBOTEN.sub("_", (nummer or "").strip())
    if name.startswith(ENTWURF_PRAEFIX):
        name = name[len(ENTWURF_PRAEFIX):]
        entwurf = True
    name = name or "Beleg"
    if entwurf:
        name = f"Entwurf-{name}"
    teil = kundenteil(kunde)
    return f"{name}_{teil}.pdf" if teil else f"{name}.pdf"
```

Prüfen: `grep -n '^def \|^KUNDE_MAX_ZEICHEN' backend/app/services/beleg_dateiname.py` → in dieser Reihenfolge `KUNDE_MAX_ZEICHEN = 50`, `def kundenteil(`, `def beleg_dateiname(`, `def rechnung_dateiname(`, `def content_disposition(`.

- [ ] **Step 4: Grün bestätigen**

Run: Lauf C mit `tests/test_paket4.py::TestP4CDateiname` → **`24 passed`**.
Dann `tests/test_gernot_261008_paket3.py::TestQ3Dateiname` → **`6 passed`**, danach die ganze Datei `tests/test_gernot_261008_paket3.py` → **`467 passed`**. Noch übergibt kein Aufrufer `kunde`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/beleg_dateiname.py backend/tests/test_paket4.py
git commit -m "feat(belege): Dateiname aus Belegnummer und bereinigtem Kundennamen als reine Regel (P4-C.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 15 (C.2): Download, Mailanhang und Versandprotokoll mit Kundennamen

**Files:**
- Append: `backend/tests/test_paket4.py`
- Modify: `backend/app/services/beleg_dateiname.py` (`rechnung_dateiname`; davor neu `bestellkunde`, `rechnung_kunde`)
- Modify: `backend/app/services/belegversand.py` (Docstring, `versende_beleg`, `markiere_ohne_mail`)
- Modify: `backend/app/api/v1/documents.py` (Import, `send_confirmation`, `download_confirmation_pdf`, `send_delivery_note`, `download_delivery_note_pdf`, `download_packing_list_pdf`)
- Modify: `backend/app/api/v1/invoices.py` (Import, `send_invoice_email`)
- Modify: `backend/tests/test_gernot_261008_paket3.py` (11 Erwartungen, C-E12)

**Interfaces:**
- Produces:
  - `bestellkunde(order) -> Optional[str]` und `rechnung_kunde(invoice) -> Optional[str]`.
  - `versende_beleg(…, kunde: Optional[str] = None)` und `markiere_ohne_mail(…, kunde: Optional[str] = None)`. Ohne `kunde` gilt das alte Verhalten, so in `TestQ2Versandprotokoll::test_versand_schreibt_protokollzeile`.
  - `DocumentDispatch.attachment_filename` trägt den neuen Namen.
- Consumes:
  - `kundenteil`, `beleg_dateiname(…, kunde=)` (C.1)
  - `pdf_service.rechnungsempfaenger` (bestehend, Paket 3 Q1.6)

**Review Focus (C.2):**
- Bei einer festgeschriebenen Rechnung kommt der Name aus dem eingefrorenen Empfänger, nicht aus dem Kundenstamm (C-E9).
- Mail, Protokoll und Download heißen gleich.
- Der 409 des Versandnachweises hängt nur an der Prüfsumme (C-E11).
- In `test_gernot_261008_paket3.py` ändern sich nur Erwartungswerte.

- [ ] **Step 1: Tests anhängen**

Diesen Block ans Ende von `backend/tests/test_paket4.py` anhängen:

<!-- C-BLOCK: c2-tests -->
```python


# ---------------------------------------- Abschnitt C: Download und Mailanhang (C.2)

def _p4c_kunde(client, name="Fruchthof Nagel GmbH", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "HANDEL", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def _p4c_bestellung(client, kunde, liefertag=None) -> str:
    from datetime import date
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (liefertag or date.today()).isoformat(),
        "lines": [{"product_name": "Erbsen-Schale", "quantity": 10, "unit": "STK",
                   "unit_price": 2.50, "tax_rate": "REDUZIERT"}],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _p4c_rechnung(client, order_id, finalisieren=True) -> dict:
    r = client.post(f"/api/v1/invoices/from-order/{order_id}")
    assert r.status_code == 201, r.text
    if finalisieren:
        f = client.post(f"/api/v1/invoices/{r.json()['id']}/finalize")
        assert f.status_code == 200, f.text
        return f.json()
    return r.json()


def _p4c_kopf(name: str) -> str:
    return f"attachment; filename=\"{name}\"; filename*=UTF-8''{name}"


@pytest.fixture
def _p4c_mails(monkeypatch):
    """Beleg-Mails abfangen (belegversand.send_email), SMTP über die Umgebung 'konfiguriert'."""
    from app.services.email_service import VersandErgebnis
    monkeypatch.setenv("SMTP_HOST", "smtp.farm.example")
    monkeypatch.setenv("SMTP_USER", "versand@farm.example")
    gesendet = []

    def senden(**kw):
        gesendet.append(kw)
        return VersandErgebnis(message_id=f"<p4c{len(gesendet)}@test.example>")

    monkeypatch.setattr("app.services.belegversand.send_email", senden)
    return gesendet


class TestP4CDateinameDownloads:
    """Download (Content-Disposition) mit Kundennamen: AB, LS, PL, Rechnung, Sammelrechnung."""

    def test_ab_lieferschein_packliste(self, client):
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH")
        order_id = _p4c_bestellung(client, kunde)
        ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={}).json()
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).json()

        r_ab = client.get(f"/api/v1/sales/confirmations/{ab['id']}/pdf")
        r_ls = client.get(f"/api/v1/sales/delivery-notes/{ls['id']}/pdf")
        r_pl = client.get(f"/api/v1/sales/delivery-notes/{ls['id']}/packing-list/pdf")

        assert r_ab.headers["content-disposition"] == _p4c_kopf(
            f"{ab['confirmation_number']}_Oekoring-Handels-GmbH.pdf")
        assert r_ls.headers["content-disposition"] == _p4c_kopf(
            f"{ls['delivery_note_number']}_Oekoring-Handels-GmbH.pdf")
        assert r_pl.headers["content-disposition"] == _p4c_kopf(
            f"{ls['packing_list']['packing_list_number']}_Oekoring-Handels-GmbH.pdf")

    def test_rechnung_nimmt_den_namen_vom_beleg(self, client):
        """Ausgestellt: der beim Festschreiben eingefrorene Empfängername (wie im
        PDF, GoBD) — eine spätere Umbenennung des Kunden ändert den Namen nicht.
        Entwurf: der aktuelle Kundenname."""
        kunde = _p4c_kunde(client)
        rechnung = _p4c_rechnung(client, _p4c_bestellung(client, kunde))
        entwurf = _p4c_rechnung(client, _p4c_bestellung(client, kunde), finalisieren=False)
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"name": "Fruchthof Nagel KG"})
        assert r.status_code == 200, r.text

        r_re = client.get(f"/api/v1/invoices/{rechnung['id']}/pdf")
        r_ent = client.get(f"/api/v1/invoices/{entwurf['id']}/pdf")

        assert r_re.headers["content-disposition"] == _p4c_kopf(
            f"{rechnung['invoice_number']}_Fruchthof-Nagel-GmbH.pdf")
        platzhalter = entwurf["invoice_number"].removeprefix("ENTWURF-")
        assert r_ent.headers["content-disposition"] == _p4c_kopf(
            f"Entwurf-{platzhalter}_Fruchthof-Nagel-KG.pdf")

    def test_sammelrechnung(self, client):
        from datetime import date
        kunde = _p4c_kunde(client, "Hamberger Großmarkt GmbH")
        for _ in range(2):
            order_id = _p4c_bestellung(client, kunde)
            assert client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).status_code == 201
        heute = date.today().isoformat()
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": heute, "period_to": heute, "customer_ids": [kunde["id"]]})
        assert r.status_code == 201, r.text
        sammel = r.json()["rechnungen"][0]
        f = client.post(f"/api/v1/invoices/{sammel['id']}/finalize")
        assert f.status_code == 200, f.text

        r_pdf = client.get(f"/api/v1/invoices/{sammel['id']}/pdf")

        assert r_pdf.headers["content-disposition"] == _p4c_kopf(
            f"{f.json()['invoice_number']}_Hamberger-Grossmarkt-GmbH.pdf")


class TestP4CDateinameMail:
    """Mailanhang und Versandprotokoll heißen wie der Download."""

    def test_rechnung_mailen(self, client, _p4c_mails):
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH")
        rechnung = _p4c_rechnung(client, _p4c_bestellung(client, kunde))

        r = client.post(f"/api/v1/invoices/{rechnung['id']}/send", json={"to": ["rechnung@oekoring.example"]})

        assert r.status_code == 200, r.text
        name = f"{rechnung['invoice_number']}_Oekoring-Handels-GmbH.pdf"
        assert _p4c_mails[0]["attachment_filename"] == name
        assert r.json()["attachment_filename"] == name

    def test_entwurf_mailen_heisst_wie_die_ausgestellte_rechnung(self, client, _p4c_mails):
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH")
        entwurf = _p4c_rechnung(client, _p4c_bestellung(client, kunde), finalisieren=False)

        r = client.post(f"/api/v1/invoices/{entwurf['id']}/send", json={"to": ["rechnung@oekoring.example"]})

        assert r.status_code == 200, r.text
        assert r.json()["attachment_filename"] == f"{r.json()['document_number']}_Oekoring-Handels-GmbH.pdf"

    def test_ab_und_lieferschein_mailen_und_markieren(self, client, _p4c_mails):
        kunde = _p4c_kunde(client)
        order_id = _p4c_bestellung(client, kunde)
        ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={}).json()
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).json()

        r_ab = client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send", json={"to": ["einkauf@fruchthof.example"]})
        r_ls = client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send", json={})  # ohne Mail: nur markiert

        assert r_ab.status_code == 200, r_ab.text
        assert r_ls.status_code == 200, r_ls.text
        assert _p4c_mails[0]["attachment_filename"] == f"{ab['confirmation_number']}_Fruchthof-Nagel-GmbH.pdf"
        assert r_ab.json()["dispatches"][0]["attachment_filename"] == (
            f"{ab['confirmation_number']}_Fruchthof-Nagel-GmbH.pdf")
        assert r_ls.json()["dispatches"][0]["status"] == "NUR_MARKIERT"
        assert r_ls.json()["dispatches"][0]["attachment_filename"] == (
            f"{ls['delivery_note_number']}_Fruchthof-Nagel-GmbH.pdf")

    def test_erneuter_versand_nach_der_umstellung_ohne_409(self, client, _p4c_mails):
        """Der Versandnachweis vergleicht die Prüfsumme des PDF-Inhalts, nicht
        den Dateinamen: Ein Beleg, der vor dem Deploy als „AB-….pdf“ hinausging,
        geht danach erneut hinaus — unter dem neuen Namen, mit derselben Prüfsumme."""
        from app.models.documents import DocumentDispatch
        from tests.conftest import TestingSessionLocal
        kunde = _p4c_kunde(client)
        order_id = _p4c_bestellung(client, kunde)
        ab = client.post(f"/api/v1/sales/orders/{order_id}/confirmations", json={}).json()
        ls = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={}).json()
        assert client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send",
                            json={"to": ["einkauf@fruchthof.example"]}).status_code == 200
        assert client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send",
                           json={"to": ["einkauf@fruchthof.example"]}).status_code == 200
        with TestingSessionLocal() as db:  # Stand vor dem Deploy: Name nur die Nummer
            for zeile in db.query(DocumentDispatch).all():
                zeile.attachment_filename = f"{zeile.document_number}.pdf"
            db.commit()

        r_ab = client.patch(f"/api/v1/sales/confirmations/{ab['id']}/send", json={"to": ["chef@fruchthof.example"]})
        r_ls = client.post(f"/api/v1/sales/delivery-notes/{ls['id']}/send", json={"to": ["chef@fruchthof.example"]})

        assert r_ab.status_code == 200, r_ab.text
        assert r_ls.status_code == 200, r_ls.text
        for antwort, nummer in ((r_ab, ab["confirmation_number"]), (r_ls, ls["delivery_note_number"])):
            namen = sorted(d["attachment_filename"] for d in antwort.json()["dispatches"])
            assert namen == sorted([f"{nummer}.pdf", f"{nummer}_Fruchthof-Nagel-GmbH.pdf"])
            assert len({d["attachment_sha256"] for d in antwort.json()["dispatches"]}) == 1
        assert len(_p4c_mails) == 4
```

Prüfen: `grep -c '^class TestP4CDateinameDownloads\|^class TestP4CDateinameMail\|^def _p4c_mails' backend/tests/test_paket4.py` → `3`.

- [ ] **Step 2: Rot bestätigen**

Run: Lauf C mit `tests/test_paket4.py::TestP4CDateinameDownloads tests/test_paket4.py::TestP4CDateinameMail`.
Erwartet: **`7 failed`**, jeder an einem Namen ohne Kunden (`… 2>&1 | grep -E '^E   [A-Za-z]|^tests/test_paket4.py:[0-9]+: in'`):
```
… in test_ab_lieferschein_packliste
E   assert 'attachment; ...1009-0001.pdf' == 'attachment; ...dels-GmbH.pdf'
… in test_rechnung_nimmt_den_namen_vom_beleg
E   assert 'attachment; ...026-00001.pdf' == 'attachment; ...agel-GmbH.pdf'
… in test_sammelrechnung
E   assert 'attachment; ...026-00001.pdf' == 'attachment; ...arkt-GmbH.pdf'
… in test_rechnung_mailen
E   AssertionError: assert 'RE-2026-00001.pdf' == 'RE-2026-0000...dels-GmbH.pdf'
… in test_entwurf_mailen_heisst_wie_die_ausgestellte_rechnung
E   AssertionError: assert 'RE-2026-00001.pdf' == 'RE-2026-0000...dels-GmbH.pdf'
… in test_ab_und_lieferschein_mailen_und_markieren
E   AssertionError: assert 'AB-20261009-0001.pdf' == 'AB-20261009-...agel-GmbH.pdf'
… in test_erneuter_versand_nach_der_umstellung_ohne_409
E   AssertionError: assert ['AB-20261009...009-0001.pdf'] == ['AB-20261009...gel-GmbH.pdf']
```
Gemessen am 09.10.2026. AB- und LS-Nummern tragen das Serverdatum, an einem anderen Tag steht dort dessen Datum.

- [ ] **Step 3: Kunde für Rechnung und Bestellung — `beleg_dateiname.py`**

Die Funktion

<!-- C-BLOCK: c2-dn-alt -->
```python
def rechnung_dateiname(invoice) -> str:
    """Dateiname für den Download einer Rechnung: Entwürfe heißen ``Entwurf-…``.

    Nicht für den Mailanhang: ``POST /invoices/{id}/send`` stellt einen
    Entwurf mit dem Versand aus, der Anhang heißt wie die Rechnung
    (``beleg_dateiname(invoice.invoice_number)``).
    """
    return beleg_dateiname(invoice.invoice_number, entwurf=invoice.status == InvoiceStatus.ENTWURF)
```

ersetzen durch:

<!-- C-BLOCK: c2-dn-neu -->
```python
def bestellkunde(order) -> Optional[str]:
    """Kundenname für AB, Lieferschein und Packliste: der Name, den ihr PDF
    druckt (order.customer.name)."""
    return getattr(getattr(order, "customer", None), "name", None)


def rechnung_kunde(invoice) -> Optional[str]:
    """Kundenname für Download und Mailanhang einer Rechnung: der Empfänger
    im PDF (pdf_service.rechnungsempfaenger) — bei ausgestellten Rechnungen
    der beim Festschreiben eingefrorene Name, beim Entwurf der aktuelle."""
    from app.services.pdf_service import rechnungsempfaenger
    return rechnungsempfaenger(invoice, invoice.status == InvoiceStatus.ENTWURF).get("name")


def rechnung_dateiname(invoice) -> str:
    """Dateiname für den Download einer Rechnung: Entwürfe heißen ``Entwurf-…``.

    Nicht für den Mailanhang: ``POST /invoices/{id}/send`` stellt einen
    Entwurf mit dem Versand aus, der Anhang heißt wie die Rechnung
    (``beleg_dateiname(invoice.invoice_number, kunde=rechnung_kunde(invoice))``).
    """
    return beleg_dateiname(
        invoice.invoice_number, entwurf=invoice.status == InvoiceStatus.ENTWURF, kunde=rechnung_kunde(invoice),
    )
```

- [ ] **Step 4: Durchreichen — `belegversand.py`, `documents.py`, `invoices.py`**

`backend/app/services/belegversand.py`, fünf Ersetzungen:

(a) Modul-Docstring, die Zeile

<!-- C-BLOCK: c2-bv1-alt -->
```python
- Anhang heißt wie der Beleg (`beleg_dateiname`, Q3).
```

ersetzen durch

<!-- C-BLOCK: c2-bv1-neu -->
```python
- Anhang heißt wie der Beleg: Nummer und Kundenname (`beleg_dateiname`, Q3;
  Kundenname Paket 4, C — Parameter `kunde`).
```

(b) Signatur von `versende_beleg`, ihr Ende

<!-- C-BLOCK: c2-bv2-alt -->
```python
    delivery_note_id: Optional[UUID] = None,
    invoice_id: Optional[UUID] = None,
) -> DocumentDispatch:
```

ersetzen durch

<!-- C-BLOCK: c2-bv2-neu -->
```python
    delivery_note_id: Optional[UUID] = None,
    invoice_id: Optional[UUID] = None,
    kunde: Optional[str] = None,
) -> DocumentDispatch:
```

(c) in `versende_beleg` die Zeile

<!-- C-BLOCK: c2-bv3-alt -->
```python
    dateiname = beleg_dateiname(document_number)
```

ersetzen durch

<!-- C-BLOCK: c2-bv3-neu -->
```python
    dateiname = beleg_dateiname(document_number, kunde=kunde)
```

(d) Signatur von `markiere_ohne_mail`, ihr Ende

<!-- C-BLOCK: c2-bv4-alt -->
```python
    confirmation_id: Optional[UUID] = None,
    delivery_note_id: Optional[UUID] = None,
) -> DocumentDispatch:
```

ersetzen durch

<!-- C-BLOCK: c2-bv4-neu -->
```python
    confirmation_id: Optional[UUID] = None,
    delivery_note_id: Optional[UUID] = None,
    kunde: Optional[str] = None,
) -> DocumentDispatch:
```

(e) in `markiere_ohne_mail` die Zeile

<!-- C-BLOCK: c2-bv5-alt -->
```python
        attachment_filename=beleg_dateiname(document_number),
```

ersetzen durch

<!-- C-BLOCK: c2-bv5-neu -->
```python
        attachment_filename=beleg_dateiname(document_number, kunde=kunde),
```

`backend/app/api/v1/documents.py`, acht Ersetzungen:

(a) Importzeile

<!-- C-BLOCK: c2-doc1-alt -->
```python
from app.services.beleg_dateiname import beleg_dateiname, content_disposition
```

ersetzen durch

<!-- C-BLOCK: c2-doc1-neu -->
```python
from app.services.beleg_dateiname import beleg_dateiname, bestellkunde, content_disposition
```

(b) in `send_confirmation` die Markierung ohne Mail

<!-- C-BLOCK: c2-doc2-alt -->
```python
        markiere_ohne_mail(
            db, doc_type=DispatchDocType.AB, document_number=conf.confirmation_number,
            pdf=pdf, user=user, customer_id=order.customer_id, order_id=order.id,
            confirmation_id=conf.id,
        )
```

ersetzen durch

<!-- C-BLOCK: c2-doc2-neu -->
```python
        markiere_ohne_mail(
            db, doc_type=DispatchDocType.AB, document_number=conf.confirmation_number,
            pdf=pdf, user=user, customer_id=order.customer_id, order_id=order.id,
            confirmation_id=conf.id, kunde=bestellkunde(order),
        )
```

(c) in `send_confirmation` das Ende des Aufrufs `versende_beleg(`

<!-- C-BLOCK: c2-doc3-alt -->
```python
            customer_id=order.customer_id,
            order_id=order.id,
            confirmation_id=conf.id,
        )
```

ersetzen durch

<!-- C-BLOCK: c2-doc3-neu -->
```python
            customer_id=order.customer_id,
            order_id=order.id,
            confirmation_id=conf.id,
            kunde=bestellkunde(order),
        )
```

(d) in `download_confirmation_pdf`

<!-- C-BLOCK: c2-doc4-alt -->
```python
        headers={"Content-Disposition": content_disposition(beleg_dateiname(conf.confirmation_number))},
```

ersetzen durch

<!-- C-BLOCK: c2-doc4-neu -->
```python
        headers={"Content-Disposition": content_disposition(
            beleg_dateiname(conf.confirmation_number, kunde=bestellkunde(conf.order)))},
```

(e) in `send_delivery_note` die Markierung ohne Mail

<!-- C-BLOCK: c2-doc5-alt -->
```python
        markiere_ohne_mail(
            db, doc_type=DispatchDocType.LS, document_number=note.delivery_note_number,
            pdf=pdf, user=user, customer_id=order.customer_id if order else None,
            order_id=note.order_id, delivery_note_id=note.id,
        )
```

ersetzen durch

<!-- C-BLOCK: c2-doc5-neu -->
```python
        markiere_ohne_mail(
            db, doc_type=DispatchDocType.LS, document_number=note.delivery_note_number,
            pdf=pdf, user=user, customer_id=order.customer_id if order else None,
            order_id=note.order_id, delivery_note_id=note.id, kunde=bestellkunde(order),
        )
```

(f) in `send_delivery_note` das Ende des Aufrufs `versende_beleg(`

<!-- C-BLOCK: c2-doc6-alt -->
```python
            customer_id=order.customer_id if order else None,
            order_id=note.order_id,
            delivery_note_id=note.id,
        )
```

ersetzen durch

<!-- C-BLOCK: c2-doc6-neu -->
```python
            customer_id=order.customer_id if order else None,
            order_id=note.order_id,
            delivery_note_id=note.id,
            kunde=bestellkunde(order),
        )
```

(g) in `download_delivery_note_pdf`

<!-- C-BLOCK: c2-doc7-alt -->
```python
        headers={"Content-Disposition": content_disposition(beleg_dateiname(note.delivery_note_number))},
```

ersetzen durch

<!-- C-BLOCK: c2-doc7-neu -->
```python
        headers={"Content-Disposition": content_disposition(
            beleg_dateiname(note.delivery_note_number, kunde=bestellkunde(note.order)))},
```

(h) in `download_packing_list_pdf`

<!-- C-BLOCK: c2-doc8-alt -->
```python
        headers={"Content-Disposition": content_disposition(beleg_dateiname(note.packing_list.packing_list_number))},
```

ersetzen durch

<!-- C-BLOCK: c2-doc8-neu -->
```python
        headers={"Content-Disposition": content_disposition(
            beleg_dateiname(note.packing_list.packing_list_number, kunde=bestellkunde(note.order)))},
```

`backend/app/api/v1/invoices.py`, zwei Ersetzungen:

(a) Importzeile

<!-- C-BLOCK: c2-inv1-alt -->
```python
from app.services.beleg_dateiname import beleg_dateiname, content_disposition, rechnung_dateiname
```

ersetzen durch

<!-- C-BLOCK: c2-inv1-neu -->
```python
from app.services.beleg_dateiname import beleg_dateiname, content_disposition, rechnung_dateiname, rechnung_kunde
```

(b) in `send_invoice_email` das Ende des Aufrufs `versende_beleg(`

<!-- C-BLOCK: c2-inv2-alt -->
```python
            customer_id=invoice.customer_id,
            order_id=invoice.order_id,
            invoice_id=invoice.id,
        )
```

ersetzen durch

<!-- C-BLOCK: c2-inv2-neu -->
```python
            customer_id=invoice.customer_id,
            order_id=invoice.order_id,
            invoice_id=invoice.id,
            kunde=rechnung_kunde(invoice),
        )
```

Prüfen: `grep -c 'kunde=' backend/app/api/v1/documents.py backend/app/api/v1/invoices.py backend/app/services/belegversand.py` → `documents.py:7`, `invoices.py:1`, `belegversand.py:2`. `get_invoice_pdf` bleibt unverändert, es nimmt `rechnung_dateiname`.

- [ ] **Step 5: Grün und Umfeld**

Run: Lauf C mit `tests/test_paket4.py::TestP4CDateiname tests/test_paket4.py::TestP4CDateinameDownloads tests/test_paket4.py::TestP4CDateinameMail` → **`31 passed`**.
Dann `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -rf -q -p no:cacheprovider 2>&1 | tail -14`. Erwartet: **`11 failed, 456 passed`**, genau diese 11 (C-E12; sonst Stoppregel 4):
```
FAILED tests/test_gernot_261008_paket3.py::TestQ1AndereWege::test_mailen_eines_entwurfs_schreibt_fest_mit_echter_nummer
FAILED tests/test_gernot_261008_paket3.py::TestQ3Downloads::test_rechnung_heisst_wie_ihre_nummer
FAILED tests/test_gernot_261008_paket3.py::TestQ3Downloads::test_rechnungsentwurf_heisst_entwurf
FAILED tests/test_gernot_261008_paket3.py::TestQ3Downloads::test_entwurf_mit_platzhalter
FAILED tests/test_gernot_261008_paket3.py::TestQ3Downloads::test_ab_lieferschein_und_packliste
FAILED tests/test_gernot_261008_paket3.py::TestQ3Mailanhang::test_ausgestellte_rechnung_mailen
FAILED tests/test_gernot_261008_paket3.py::TestQ3Mailanhang::test_altentwurf_mailen
FAILED tests/test_gernot_261008_paket3.py::TestQ3Mailanhang::test_ab_mailen
FAILED tests/test_gernot_261008_paket3.py::TestQ2AbVersand::test_eine_mail_an_mehrere
FAILED tests/test_gernot_261008_paket3.py::TestQ2LsVersand::test_lieferschein_per_mail
FAILED tests/test_gernot_261008_paket3.py::TestQ2Rechnungsversand::test_eine_mail_an_mehrere_mit_protokoll
```
Jeder davon scheitert nur am Namen. Die Kunden dieser Tests heißen „Fruchthof Nagel“ (`_q3_kunde`) bzw. „Ökoring Handels GmbH“ (`_q1_kunde`, `_q2_kunde`).

- [ ] **Step 6: Erwartungen der 11 Bestandstests umstellen (C-E12)**

In `backend/tests/test_gernot_261008_paket3.py` die folgenden elf Ersetzungen vornehmen. Geändert wird jeweils nur der erwartete Name:

(1) `TestQ1AndereWege::test_mailen_eines_entwurfs_schreibt_fest_mit_echter_nummer`: diesen Block

<!-- C-BLOCK: c2-p3-01-alt -->
```python
        assert gesendet["attachment_filename"] == f"{_q1_nr(1)}.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-01-neu -->
```python
        assert gesendet["attachment_filename"] == f"{_q1_nr(1)}_Oekoring-Handels-GmbH.pdf"  # Paket 4, C
```

(2) `TestQ3Downloads::test_rechnung_heisst_wie_ihre_nummer`: diesen Block

<!-- C-BLOCK: c2-p3-02-alt -->
```python
        assert r.headers["content-disposition"] == _q3_kopf(f"{nummer}.pdf")
```

ersetzen durch

<!-- C-BLOCK: c2-p3-02-neu -->
```python
        assert r.headers["content-disposition"] == _q3_kopf(f"{nummer}_Fruchthof-Nagel.pdf")  # Paket 4, C
```

(3) `TestQ3Downloads::test_rechnungsentwurf_heisst_entwurf`: diesen Block

<!-- C-BLOCK: c2-p3-03-alt -->
```python
        assert r.headers["content-disposition"] == _q3_kopf("Entwurf-RE-2026-00003.pdf")
```

ersetzen durch

<!-- C-BLOCK: c2-p3-03-neu -->
```python
        assert r.headers["content-disposition"] == _q3_kopf("Entwurf-RE-2026-00003_Fruchthof-Nagel.pdf")  # Paket 4, C
```

(4) `TestQ3Downloads::test_entwurf_mit_platzhalter`: diesen Block

<!-- C-BLOCK: c2-p3-04-alt -->
```python
        assert r.headers["content-disposition"] == _q3_kopf("Entwurf-AB12CD34EF56.pdf")
```

ersetzen durch

<!-- C-BLOCK: c2-p3-04-neu -->
```python
        assert r.headers["content-disposition"] == _q3_kopf("Entwurf-AB12CD34EF56_Fruchthof-Nagel.pdf")  # Paket 4, C
```

(5) `TestQ3Downloads::test_ab_lieferschein_und_packliste`: diesen Block

<!-- C-BLOCK: c2-p3-05-alt -->
```python
        assert r_ab.headers["content-disposition"] == _q3_kopf(f"{ab['confirmation_number']}.pdf")
        assert r_ls.headers["content-disposition"] == _q3_kopf(f"{ls['delivery_note_number']}.pdf")
        assert r_pl.headers["content-disposition"] == _q3_kopf(
            f"{ls['packing_list']['packing_list_number']}.pdf")
```

ersetzen durch

<!-- C-BLOCK: c2-p3-05-neu -->
```python
        # Paket 4, C: Nummer und Kundenname
        assert r_ab.headers["content-disposition"] == _q3_kopf(f"{ab['confirmation_number']}_Fruchthof-Nagel.pdf")
        assert r_ls.headers["content-disposition"] == _q3_kopf(f"{ls['delivery_note_number']}_Fruchthof-Nagel.pdf")
        assert r_pl.headers["content-disposition"] == _q3_kopf(
            f"{ls['packing_list']['packing_list_number']}_Fruchthof-Nagel.pdf")
```

(6) `TestQ3Mailanhang::test_ausgestellte_rechnung_mailen`: diesen Block

<!-- C-BLOCK: c2-p3-06-alt -->
```python
        assert versendet["attachment_filename"] == f"{nummer}.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-06-neu -->
```python
        assert versendet["attachment_filename"] == f"{nummer}_Fruchthof-Nagel.pdf"  # Paket 4, C
```

(7) `TestQ3Mailanhang::test_altentwurf_mailen`: diesen Block

<!-- C-BLOCK: c2-p3-07-alt -->
```python
        assert versendet["attachment_filename"] == "RE-2026-00003.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-07-neu -->
```python
        assert versendet["attachment_filename"] == "RE-2026-00003_Fruchthof-Nagel.pdf"  # Paket 4, C
```

(8) `TestQ3Mailanhang::test_ab_mailen`: diesen Block

<!-- C-BLOCK: c2-p3-08-alt -->
```python
        assert versendet["attachment_filename"] == f"{ab['confirmation_number']}.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-08-neu -->
```python
        assert versendet["attachment_filename"] == f"{ab['confirmation_number']}_Fruchthof-Nagel.pdf"  # Paket 4, C
```

(9) `TestQ2AbVersand::test_eine_mail_an_mehrere`: diesen Block

<!-- C-BLOCK: c2-p3-09-alt -->
```python
        assert dateiname == f"{ab['confirmation_number']}.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-09-neu -->
```python
        assert dateiname == f"{ab['confirmation_number']}_Oekoring-Handels-GmbH.pdf"  # Paket 4, C
```

(10) `TestQ2LsVersand::test_lieferschein_per_mail`: diesen Block

<!-- C-BLOCK: c2-p3-10-alt -->
```python
        assert dateiname == f"{ls['delivery_note_number']}.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-10-neu -->
```python
        assert dateiname == f"{ls['delivery_note_number']}_Oekoring-Handels-GmbH.pdf"  # Paket 4, C
```

(11) `TestQ2Rechnungsversand::test_eine_mail_an_mehrere_mit_protokoll`: diesen Block

<!-- C-BLOCK: c2-p3-11-alt -->
```python
        assert dateiname == f"{detail['invoice_number']}.pdf"
```

ersetzen durch

<!-- C-BLOCK: c2-p3-11-neu -->
```python
        assert dateiname == f"{detail['invoice_number']}_Oekoring-Handels-GmbH.pdf"  # Paket 4, C
```


- [ ] **Step 7: Grün, statisch, Vollauf**

Run: `tests/test_gernot_261008_paket3.py` (ganze Datei, Lauf C) → **`467 passed`**. Die Paket-3-Abnahmetests sind darin enthalten und unverändert.
Run: `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/beleg_dateiname.py app/services/belegversand.py app/api/v1/documents.py app/api/v1/invoices.py` → keine Ausgabe, Exit 0.
Run: Prozedur V → Abgleich leer, N = Ausgang + 31 (gemessen auf `df84f7b`: `14 failed, 1675 passed, 2 skipped, 1 error`, auf `521ed6d`: `1849 passed`; im Gesamtplan errechnet `1888 passed`).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/beleg_dateiname.py backend/app/services/belegversand.py backend/app/api/v1/documents.py backend/app/api/v1/invoices.py backend/tests/test_gernot_261008_paket3.py backend/tests/test_paket4.py
git commit -m "feat(belege): Download, Mailanhang und Versandprotokoll heissen Belegnummer_Kunde.pdf (P4-C.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 16 (C.3): Belegstatus — Regeln und Endpunkt `GET /api/v1/belegstatus`

**Files:**
- Append: `backend/tests/test_paket4.py`
- Create: `backend/app/schemas/belegstatus.py`, `backend/app/services/belegstatus.py`, `backend/app/api/v1/belegstatus.py`
- Modify: `backend/app/main.py` (Import unter `from app.api.v1 import sepa`, `include_router` hinter dem Block `invoices.router`)

**Interfaces:**
- Produces:
  - **Aufruf:** `GET /api/v1/belegstatus?von&bis&kunde_id&nur_unvollstaendig&page&page_size` → `BelegstatusListe {items, total, unvollstaendig, heute}`.
  - **Zeile:** `BelegstatusZeile` mit `order_id`, `order_number`, `order_status`, `customer_id`, `customer_name`, `abrechnung`, `liefertag`, `geliefert`, `lieferscheine[{id, nummer, status}]`, `rechnung{id, nummer, status, sammelrechnung, versendet_am, bezahlt} | null`, `extern_abgerechnet`, `rechnung_faellig_ab`, `luecken[]` und `unvollstaendig`.
  - **Rechte:** wie `/invoices` (`_deps_geld`). Planung und Halle bekommen 403.
  - **Service:** `belegstatus(db, *, heute, von=None, bis=None, kunde_id=None) -> list[dict]`, `rechnung_faellig_ab(liefertag, monatlich) -> date`.
- Consumes:
  - `order_status_service.heute_berlin`, `Pagination` (`app.api.deps`)
  - die Modelle `Order`, `DeliveryNote`, `Invoice`, `DocumentDispatch` und `InvoiceMode`

**Review Focus (C.3):**
- Die Regeln in C-E3/C-E4 gelten genau so, auch „Storno schließt extern aus“ (`mit_storno`).
- Es gibt keine Abfrage je Bestellung (fünf Abfragen). Die stornierten Rechnungen kommen aus derselben Abfrage über `Invoice.order_id`.
- Der Test zu FAKTURIERT legt Rechnungen an, bevor er FAKTURIERT setzt. So bleibt er nach P4-B (B-E1: 409 für FAKTURIERT) grün.
- `unvollstaendig` in der Antwort zählt auch bei `nur_unvollstaendig=false`.
- Die Tests fixieren den Stichtag über `app.api.v1.belegstatus.heute_berlin`. Der Endpunkt muss `heute_berlin` deshalb **in sein Modul importieren** und dort aufrufen.

- [ ] **Step 1: Tests anhängen**

Diesen Block ans Ende von `backend/tests/test_paket4.py` anhängen:

<!-- C-BLOCK: c3-tests -->
```python


# ---------------------------------------- Abschnitt C: Belegstatus (C.3)
_P4C_HEUTE = "2026-10-09"


def _p4c_heute(monkeypatch, tag=_P4C_HEUTE):
    """Stichtag des Belegstatus festlegen (der Endpunkt rechnet in Berlin)."""
    from datetime import date
    monkeypatch.setattr("app.api.v1.belegstatus.heute_berlin", lambda: date.fromisoformat(tag))


def _p4c_auftrag(client, kunde, liefertag, status="GELIEFERT", lieferschein=True, ls_status=None) -> str:
    """Bestellung mit Liefertag und Status (direkt gesetzt), auf Wunsch mit Lieferschein."""
    import uuid
    from datetime import date
    from app.models.documents import DeliveryNote
    from app.models.enums import DeliveryNoteStatus, OrderStatus
    from app.models.order import Order
    from tests.conftest import TestingSessionLocal
    order_id = _p4c_bestellung(client, kunde, date.fromisoformat(liefertag))
    if lieferschein:
        r = client.post(f"/api/v1/sales/orders/{order_id}/delivery-notes", json={})
        assert r.status_code == 201, r.text
    with TestingSessionLocal() as db:
        db.get(Order, uuid.UUID(order_id)).status = OrderStatus(status)
        if ls_status:
            for ls in db.query(DeliveryNote).filter(DeliveryNote.order_id == uuid.UUID(order_id)):
                ls.status = DeliveryNoteStatus(ls_status)
        db.commit()
    return order_id


def _p4c_status(client, **params) -> dict:
    r = client.get("/api/v1/belegstatus", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _p4c_zeile(liste, order_id) -> dict:
    treffer = [z for z in liste["items"] if z["order_id"] == order_id]
    assert len(treffer) == 1, liste
    return treffer[0]


class TestP4CBelegstatus:
    """Gernot 08.10. (B2): je Bestellung Lieferschein ✔/✘, Rechnung ✔/✘,
    versendet ✔/✘, bezahlt; Filter Zeitraum, Kunde, „unvollständig“
    (geliefert, aber ohne Rechnung bzw. Rechnung nicht versendet)."""

    def test_einzelkunde_geliefert_ohne_rechnung(self, client, monkeypatch):
        """X07: gelieferte Bestellungen von Einzelkunden ohne Rechnung — mit
        Lieferschein und ohne (Abo, BE-20261008-0002)."""
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client, "Naturkostinsel GmbH")
        mit_ls = _p4c_auftrag(client, kunde, "2026-10-08")
        ohne_ls = _p4c_auftrag(client, kunde, "2026-10-08", lieferschein=False)

        liste = _p4c_status(client, von="2026-10-01")

        assert (liste["total"], liste["unvollstaendig"], liste["heute"]) == (2, 2, _P4C_HEUTE)
        a, b = _p4c_zeile(liste, mit_ls), _p4c_zeile(liste, ohne_ls)
        assert [len(a["lieferscheine"]), len(b["lieferscheine"])] == [1, 0]
        assert a["lieferscheine"][0]["status"] == "ENTWURF"
        for z in (a, b):
            assert (z["customer_name"], z["abrechnung"], z["liefertag"]) == ("Naturkostinsel GmbH", "EINZELN", "2026-10-08")
            assert (z["geliefert"], z["rechnung"], z["extern_abgerechnet"]) == (True, None, False)
            assert (z["luecken"], z["unvollstaendig"], z["rechnung_faellig_ab"]) == (["OHNE_RECHNUNG"], True, "2026-10-08")

    def test_entwurf_nicht_versendet_versendet_bezahlt(self, client, monkeypatch, _p4c_mails):
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        auftraege = [_p4c_auftrag(client, kunde, "2026-10-08") for _ in range(4)]
        entwurf = _p4c_rechnung(client, auftraege[0], finalisieren=False)
        offen = _p4c_rechnung(client, auftraege[1])
        versendet = _p4c_rechnung(client, auftraege[2])
        bezahlt = _p4c_rechnung(client, auftraege[3])
        for rechnung in (versendet, bezahlt):
            r = client.post(f"/api/v1/invoices/{rechnung['id']}/send", json={"to": ["rechnung@fruchthof.example"]})
            assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/invoices/{bezahlt['id']}/payments",
                        json={"payment_date": _P4C_HEUTE, "amount": str(bezahlt["total"])})
        assert r.status_code in (200, 201), r.text

        liste = _p4c_status(client)

        z = [_p4c_zeile(liste, o) for o in auftraege]
        assert [x["luecken"] for x in z] == [["RECHNUNG_ENTWURF"], ["NICHT_VERSENDET"], [], []]
        assert [x["rechnung"]["id"] for x in z] == [entwurf["id"], offen["id"], versendet["id"], bezahlt["id"]]
        assert [x["rechnung"]["nummer"] for x in z[1:]] == [
            offen["invoice_number"], versendet["invoice_number"], bezahlt["invoice_number"]]
        assert z[0]["rechnung"]["nummer"].startswith("ENTWURF-")
        assert [x["rechnung"]["status"] for x in z] == ["ENTWURF", "OFFEN", "OFFEN", "BEZAHLT"]
        assert [x["rechnung"]["versendet_am"] is not None for x in z] == [False, False, True, True]
        assert [x["rechnung"]["bezahlt"] for x in z] == [False, False, False, True]
        assert [x["rechnung"]["sammelrechnung"] for x in z] == [False] * 4
        assert liste["unvollstaendig"] == 2

    def test_eintrag_im_versandprotokoll_zaehlt_als_versendet(self, client, monkeypatch):
        """Ein Eintrag im Versandprotokoll (auch „ohne Mail markiert“) zählt
        wie sent_at — sent_at setzt nur ein Mailversand (Paket 3, Q2)."""
        import uuid
        from datetime import datetime
        from app.models.documents import DocumentDispatch
        from app.models.enums import DispatchDocType, DispatchStatus
        from tests.conftest import TestingSessionLocal
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        order_id = _p4c_auftrag(client, kunde, "2026-10-08")
        rechnung = _p4c_rechnung(client, order_id)
        with TestingSessionLocal() as db:
            db.add(DocumentDispatch(
                doc_type=DispatchDocType.RE, document_number=rechnung["invoice_number"],
                invoice_id=uuid.UUID(rechnung["id"]), order_id=uuid.UUID(order_id),
                status=DispatchStatus.NUR_MARKIERT, to_addrs=[], cc_addrs=[],
                sent_at=datetime(2026, 10, 8, 15, 0)))
            db.commit()

        z = _p4c_zeile(_p4c_status(client), order_id)

        assert (z["rechnung"]["versendet_am"], z["luecken"]) == ("2026-10-08T15:00:00", [])

    def test_festgeschriebene_rechnung_geht_dem_entwurf_vor(self, client, monkeypatch):
        """Zwei Rechnungen zu einer Bestellung (z. B. ein vergessener Entwurf):
        angezeigt wird die festgeschriebene."""
        import uuid
        from app.models.invoice import Invoice
        from tests.conftest import TestingSessionLocal
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        order_id = _p4c_auftrag(client, kunde, "2026-10-08")
        fest = _p4c_rechnung(client, order_id)
        entwurf = _p4c_rechnung(client, _p4c_auftrag(client, kunde, "2026-10-08"), finalisieren=False)
        with TestingSessionLocal() as db:
            db.get(Invoice, uuid.UUID(entwurf["id"])).order_id = uuid.UUID(order_id)
            db.commit()

        z = _p4c_zeile(_p4c_status(client), order_id)

        assert (z["rechnung"]["id"], z["luecken"]) == (fest["id"], ["NICHT_VERSENDET"])

    def test_monatskunde_erst_ab_dem_folgemonat(self, client, monkeypatch):
        """Monatskunden rechnet der Monatslauf am 1. des Folgemonats ab —
        vorher ist die fehlende Rechnung keine Lücke."""
        kunde = _p4c_kunde(client, "Ökoring Handels GmbH", invoice_mode="MONATLICH")
        order_id = _p4c_auftrag(client, kunde, "2026-10-08")

        _p4c_heute(monkeypatch, "2026-10-31")
        vorher = _p4c_zeile(_p4c_status(client), order_id)
        _p4c_heute(monkeypatch, "2026-11-01")
        nachher = _p4c_zeile(_p4c_status(client), order_id)

        assert (vorher["abrechnung"], vorher["rechnung_faellig_ab"]) == ("MONATLICH", "2026-11-01")
        assert (vorher["luecken"], vorher["unvollstaendig"]) == ([], False)
        assert (nachher["luecken"], nachher["unvollstaendig"]) == (["OHNE_RECHNUNG"], True)

    def test_sammelrechnung_ueber_den_lieferschein(self, client, monkeypatch):
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client, "Hamberger Großmarkt GmbH")
        auftraege = [_p4c_auftrag(client, kunde, "2026-10-08", ls_status="GELIEFERT") for _ in range(2)]
        r = client.post("/api/v1/invoices/batch-run/commit", json={
            "period_from": "2026-10-01", "period_to": "2026-10-09", "customer_ids": [kunde["id"]]})
        assert r.status_code == 201, r.text
        sammel = r.json()["rechnungen"][0]
        assert client.post(f"/api/v1/invoices/{sammel['id']}/finalize").status_code == 200

        liste = _p4c_status(client)

        for order_id in auftraege:
            z = _p4c_zeile(liste, order_id)
            assert (z["rechnung"]["id"], z["rechnung"]["sammelrechnung"]) == (sammel["id"], True)
            assert z["lieferscheine"][0]["status"] == "GELIEFERT"
            assert z["luecken"] == ["NICHT_VERSENDET"]

    def test_fakturiert_ohne_rechnung_ist_extern_abgerechnet(self, client, monkeypatch):
        """Altbestand (574 Bestellungen in Produktion): FAKTURIERT, über DATEV
        abgerechnet, ohne Rechnung im System — keine Lücke. Wurde die
        NovaERP-Rechnung storniert und nicht neu ausgestellt, fehlt sie: Der
        Storno setzt FAKTURIERT nicht zurück, „extern“ wäre dann falsch.
        Die Rechnungen entstehen vor der Kennzeichnung FAKTURIERT — danach
        lehnt der Server neue Rechnungen ab (Paket 4, B-E1)."""
        import uuid
        from app.models.enums import OrderStatus
        from app.models.order import Order
        from tests.conftest import TestingSessionLocal
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        extern = _p4c_auftrag(client, kunde, "2026-08-14", status="FAKTURIERT", lieferschein=False)
        im_system = _p4c_auftrag(client, kunde, "2026-10-08")
        _p4c_rechnung(client, im_system)
        storniert = _p4c_auftrag(client, kunde, "2026-10-08")
        r = client.post(f"/api/v1/invoices/{_p4c_rechnung(client, storniert)['id']}/cancel",
                        json={"reason": "Preisfehler", "reason_code": "PREISFEHLER"})
        assert r.status_code == 200, r.text
        with TestingSessionLocal() as db:  # wie der Status-Endpunkt: GELIEFERT → FAKTURIERT
            for order_id in (im_system, storniert):
                db.get(Order, uuid.UUID(order_id)).status = OrderStatus.FAKTURIERT
            db.commit()

        liste = _p4c_status(client)

        e, i, s = _p4c_zeile(liste, extern), _p4c_zeile(liste, im_system), _p4c_zeile(liste, storniert)
        assert (e["extern_abgerechnet"], e["rechnung"], e["luecken"], e["geliefert"]) == (True, None, [], True)
        assert (i["extern_abgerechnet"], i["luecken"]) == (False, ["NICHT_VERSENDET"])
        assert (s["extern_abgerechnet"], s["rechnung"], s["luecken"]) == (False, None, ["OHNE_RECHNUNG"])

    def test_wann_eine_bestellung_als_geliefert_gilt(self, client, monkeypatch):
        """GELIEFERT/FAKTURIERT, ein quittierter Lieferschein, oder BESTAETIGT/
        IN_PRODUKTION mit Liefertag vor heute (Spec A1: gelieferte Bestellungen
        bleiben oft auf BESTAETIGT). ENTWURF ohne Quittung nie; storniert fehlt."""
        _p4c_heute(monkeypatch)
        kunde = _p4c_kunde(client)
        faelle = {
            "bestaetigt_gestern": (_p4c_auftrag(client, kunde, "2026-10-08", status="BESTAETIGT"), True),
            "bestaetigt_heute": (_p4c_auftrag(client, kunde, "2026-10-09", status="BESTAETIGT"), False),
            "in_produktion_vorgestern": (_p4c_auftrag(client, kunde, "2026-10-07", status="IN_PRODUKTION"), True),
            "entwurf_alt": (_p4c_auftrag(client, kunde, "2026-09-14", status="ENTWURF", lieferschein=False), False),
            "entwurf_quittiert": (_p4c_auftrag(client, kunde, "2026-10-09", status="ENTWURF", ls_status="GELIEFERT"), True),
            "geliefert_morgen": (_p4c_auftrag(client, kunde, "2026-10-10", status="GELIEFERT"), True),
        }
        storniert = _p4c_auftrag(client, kunde, "2026-10-08", status="STORNIERT")

        liste = _p4c_status(client)

        ist = {name: _p4c_zeile(liste, oid)["geliefert"] for name, (oid, _) in faelle.items()}
        assert ist == {name: soll for name, (_, soll) in faelle.items()}
        assert storniert not in [z["order_id"] for z in liste["items"]]
        luecken = {name: _p4c_zeile(liste, oid)["luecken"] for name, (oid, _) in faelle.items()}
        assert luecken == {
            "bestaetigt_gestern": ["OHNE_RECHNUNG"], "bestaetigt_heute": [],
            "in_produktion_vorgestern": ["OHNE_RECHNUNG"], "entwurf_alt": [],
            "entwurf_quittiert": ["OHNE_RECHNUNG"],
            "geliefert_morgen": [],  # fällig erst ab dem Liefertag
        }

    def test_filter_reihenfolge_und_seiten(self, client, monkeypatch):
        _p4c_heute(monkeypatch)
        nagel = _p4c_kunde(client)
        kern = _p4c_kunde(client, "Großer Kern GmbH")
        n1 = _p4c_auftrag(client, nagel, "2026-10-08")                          # unvollständig
        n2 = _p4c_auftrag(client, nagel, "2026-10-12", status="BESTAETIGT")     # Zukunft
        k1 = _p4c_auftrag(client, kern, "2026-09-30")                           # unvollständig
        k2 = _p4c_auftrag(client, kern, "2026-10-05")                           # unvollständig

        alle = _p4c_status(client)
        assert [z["order_id"] for z in alle["items"]] == [n2, n1, k2, k1]   # Liefertag absteigend
        assert (alle["total"], alle["unvollstaendig"]) == (4, 3)

        oktober = _p4c_status(client, von="2026-10-01", bis="2026-10-09")
        assert [z["order_id"] for z in oktober["items"]] == [n1, k2]
        assert _p4c_status(client, kunde_id=kern["id"])["total"] == 2

        nur = _p4c_status(client, nur_unvollstaendig="true")
        assert [z["order_id"] for z in nur["items"]] == [n1, k2, k1]
        assert (nur["total"], nur["unvollstaendig"]) == (3, 3)

        seite2 = _p4c_status(client, nur_unvollstaendig="true", page=2, page_size=2)
        assert [z["order_id"] for z in seite2["items"]] == [k1]
        assert (seite2["total"], seite2["unvollstaendig"]) == (3, 3)

    def test_von_nach_bis_wird_abgelehnt(self, client):
        r = client.get("/api/v1/belegstatus", params={"von": "2026-10-09", "bis": "2026-10-01"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"] == "„von“ liegt nach „bis“"

    @pytest.mark.parametrize("rollen, code", [
        (["accounting"], 200), (["sales"], 200), (["admin"], 200),
        (["production_planner"], 403), (["production_staff"], 403),
    ], ids=["buchhaltung", "vertrieb", "admin", "planung", "halle"])
    def test_rechte_wie_die_rechnungen(self, client, rollen, code):
        """Wie /invoices (main.py: _deps_geld): Admin, Vertrieb, Buchhaltung."""
        from app.api.deps import get_current_user
        from app.main import app

        async def benutzer():
            return {"id": "123e4567-e89b-12d3-a456-426614174099", "username": "p4c",
                    "email": "p4c@example.com", "roles": rollen}
        app.dependency_overrides[get_current_user] = benutzer

        assert client.get("/api/v1/belegstatus").status_code == code
```

Prüfen: `grep -c '^class TestP4CBelegstatus' backend/tests/test_paket4.py` → `1`.

- [ ] **Step 2: Rot bestätigen**

Run: Lauf C mit `tests/test_paket4.py::TestP4CBelegstatus`.
Erwartet: **`15 failed`**. Die Meldungen (`… 2>&1 | grep -E '^E   [A-Za-z]' | sort | uniq -c`):
```
   3 E   AssertionError: assert 404 == 200
   2 E   AssertionError: assert 404 == 403
   1 E   AssertionError: {"detail":"Not Found"}
   9 E   ImportError: import error in app.api.v1.belegstatus: No module named 'app.api.v1.belegstatus'
   9 E   ModuleNotFoundError: No module named 'app.api.v1.belegstatus'
   1 E   assert 404 == 422
```
Die neun Tests mit Stichtag scheitern an `monkeypatch.setattr` (je zwei Zeilen). `test_von_nach_bis_wird_abgelehnt` scheitert an 404, die fünf Rechte-Tests an 404.

- [ ] **Step 3: Schema, Regeln, Endpunkt**

`backend/app/schemas/belegstatus.py` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c3-schema -->
```python
"""Belegstatus je Bestellung (Paket 4, Abschnitt C; Gernot 08.10.2026, B2)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class BelegstatusLieferschein(BaseModel):
    id: UUID
    nummer: str
    status: str  # ENTWURF | AUSGESTELLT | GELIEFERT


class BelegstatusRechnung(BaseModel):
    id: UUID
    nummer: str  # Entwurf: Platzhalter ENTWURF-…, die Oberfläche zeigt „Entwurf“
    status: str  # InvoiceStatus
    sammelrechnung: bool  # über einen Lieferschein zugeordnet (Sammel-/Monatsrechnung)
    versendet_am: Optional[datetime] = None
    bezahlt: bool


class BelegstatusZeile(BaseModel):
    order_id: UUID
    order_number: str
    order_status: str
    customer_id: UUID
    customer_name: str
    abrechnung: str  # EINZELN | MONATLICH (Customer.invoice_mode)
    liefertag: date
    geliefert: bool
    lieferscheine: list[BelegstatusLieferschein]
    rechnung: Optional[BelegstatusRechnung] = None
    extern_abgerechnet: bool
    rechnung_faellig_ab: date
    luecken: list[str]  # OHNE_RECHNUNG | RECHNUNG_ENTWURF | NICHT_VERSENDET
    unvollstaendig: bool


class BelegstatusListe(BaseModel):
    items: list[BelegstatusZeile]
    total: int  # Zeilen nach allen Filtern (auch nur_unvollstaendig)
    unvollstaendig: int  # unvollständige Zeilen in Zeitraum und Kunde
    heute: date  # Stichtag (Berlin)
```

`backend/app/services/belegstatus.py` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c3-service -->
```python
"""Belegstatus je Bestellung (Paket 4, Abschnitt C; Gernot 08.10.2026, B2).

Eine Zeile je nicht stornierter Bestellung: Lieferschein erstellt, Rechnung
erstellt, Rechnung versendet, bezahlt. Schreibt nichts.

Regeln (dieselben Wege wie Sammel- und Monatslauf):
- Liefertag = tatsächliches, sonst Wunschlieferdatum der Bestellung.
- Rechnung der Bestellung = nicht stornierte Rechnung vom Typ RECHNUNG über
  Invoice.order_id oder über einen Lieferschein der Bestellung
  (wie InvoiceService.aktive_rechnung_zur_bestellung); eine
  festgeschriebene geht dem Entwurf vor.
- Versendet = Invoice.sent_at (erster erfolgreicher Mailversand, Paket 3
  Q2), sonst der erste Eintrag der Rechnung im Versandprotokoll
  (document_dispatches, auch „ohne Mail markiert“). Rechnungen von vor dem
  Protokoll haben nur sent_at.
- Geliefert = Status GELIEFERT oder FAKTURIERT, ein quittierter
  Lieferschein, oder BESTAETIGT/IN_PRODUKTION mit Liefertag vor heute
  (gelieferte Bestellungen bleiben oft auf BESTAETIGT stehen, Spec A1).
- FAKTURIERT ohne Rechnung im System = extern abgerechnet (Altbestand über
  DATEV, Spec-Nachtrag 08.10.2026) — keine Lücke. Hat die Bestellung eine
  stornierte Rechnung (Invoice.order_id), ist sie nie extern: Der Storno
  setzt FAKTURIERT nicht zurück, ohne Neuausstellung fehlt die Rechnung.
- Fällig ist die Rechnung beim Einzelkunden ab dem Liefertag, beim
  Monatskunden ab dem 1. des Folgemonats (Monatslauf, B5).
- Unvollständig = geliefert, nicht extern abgerechnet, fällig und: ohne
  Rechnung (OHNE_RECHNUNG), nur Entwurf (RECHNUNG_ENTWURF) oder nicht
  versendet (NICHT_VERSENDET).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.customer import InvoiceMode
from app.models.documents import DeliveryNote, DocumentDispatch
from app.models.enums import DeliveryNoteStatus, OrderStatus
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.models.order import Order

OHNE_RECHNUNG = "OHNE_RECHNUNG"
RECHNUNG_ENTWURF = "RECHNUNG_ENTWURF"
NICHT_VERSENDET = "NICHT_VERSENDET"

_GELIEFERT = (OrderStatus.GELIEFERT, OrderStatus.FAKTURIERT)
_UNTERWEGS = (OrderStatus.BESTAETIGT, OrderStatus.IN_PRODUKTION)


def rechnung_faellig_ab(liefertag: date, monatlich: bool) -> date:
    """Einzelkunde: der Liefertag. Monatskunde: der 1. des Folgemonats."""
    if not monatlich:
        return liefertag
    return (liefertag.replace(day=1) + timedelta(days=32)).replace(day=1)


def belegstatus(
    db: Session,
    *,
    heute: date,
    von: Optional[date] = None,
    bis: Optional[date] = None,
    kunde_id: Optional[UUID] = None,
) -> list[dict]:
    """Alle Zeilen im Zeitraum (Liefertag) und für den Kunden, neueste zuerst.

    Fünf Abfragen, keine je Bestellung; die Auswahl der Bestellungen geht als
    Unterabfrage in die Abfragen nach Lieferscheinen und Rechnungen.
    """
    liefertag = func.coalesce(Order.actual_delivery_date, Order.requested_delivery_date)
    bedingungen = [Order.status != OrderStatus.STORNIERT]
    if von:
        bedingungen.append(liefertag >= von)
    if bis:
        bedingungen.append(liefertag <= bis)
    if kunde_id:
        bedingungen.append(Order.customer_id == kunde_id)
    auswahl = select(Order.id).where(*bedingungen)

    auftraege = db.execute(
        select(Order).options(joinedload(Order.customer)).where(*bedingungen)
        .order_by(liefertag.desc(), Order.order_number.desc())
    ).scalars().all()

    lieferscheine: dict[UUID, list[DeliveryNote]] = {}
    for ls in db.execute(
        select(DeliveryNote).where(DeliveryNote.order_id.in_(auswahl))
        .order_by(DeliveryNote.delivery_note_number)
    ).scalars():
        lieferscheine.setdefault(ls.order_id, []).append(ls)

    aktiv = (Invoice.invoice_type == InvoiceType.RECHNUNG, Invoice.status != InvoiceStatus.STORNIERT)
    rechnungen: dict[UUID, dict[UUID, Invoice]] = {}
    # Bestellungen mit stornierter Rechnung sind nie „extern abgerechnet“: Der
    # Storno setzt FAKTURIERT nicht zurück. Eine stornierte Sammel- oder
    # Monatsrechnung hängt danach an keinem Lieferschein mehr (R1.6) und
    # bleibt hier unsichtbar — wie im Sammellauf.
    mit_storno: set[UUID] = set()
    for inv in db.execute(
        select(Invoice).where(Invoice.order_id.in_(auswahl), Invoice.invoice_type == InvoiceType.RECHNUNG)
    ).scalars():
        if inv.status == InvoiceStatus.STORNIERT:
            mit_storno.add(inv.order_id)
        else:
            rechnungen.setdefault(inv.order_id, {})[inv.id] = inv
    for order_id, inv in db.execute(
        select(DeliveryNote.order_id, Invoice)
        .join(Invoice, DeliveryNote.invoice_id == Invoice.id)
        .where(DeliveryNote.order_id.in_(auswahl), *aktiv)
    ).all():
        rechnungen.setdefault(order_id, {})[inv.id] = inv

    rechnung_ids = {inv_id for je_auftrag in rechnungen.values() for inv_id in je_auftrag}
    protokoll: dict[UUID, datetime] = dict(db.execute(
        select(DocumentDispatch.invoice_id, func.min(DocumentDispatch.sent_at))
        .where(DocumentDispatch.invoice_id.in_(rechnung_ids))
        .group_by(DocumentDispatch.invoice_id)
    ).all()) if rechnung_ids else {}

    zeilen = []
    for o in auftraege:
        tag = o.actual_delivery_date or o.requested_delivery_date
        kunde = o.customer
        monatlich = kunde is not None and kunde.invoice_mode == InvoiceMode.MONATLICH
        notes = lieferscheine.get(o.id, [])
        # festgeschrieben vor Entwurf, dann nach Nummer
        kandidaten = sorted(
            rechnungen.get(o.id, {}).values(),
            key=lambda r: (r.status == InvoiceStatus.ENTWURF, r.invoice_number),
        )
        rechnung = kandidaten[0] if kandidaten else None
        extern = rechnung is None and o.status == OrderStatus.FAKTURIERT and o.id not in mit_storno
        geliefert = (
            o.status in _GELIEFERT
            or any(n.status == DeliveryNoteStatus.GELIEFERT for n in notes)
            or (o.status in _UNTERWEGS and tag < heute)
        )
        faellig_ab = rechnung_faellig_ab(tag, monatlich)
        versendet_am = None if rechnung is None else (rechnung.sent_at or protokoll.get(rechnung.id))

        luecken: list[str] = []
        if geliefert and not extern and heute >= faellig_ab:
            if rechnung is None:
                luecken.append(OHNE_RECHNUNG)
            elif rechnung.status == InvoiceStatus.ENTWURF:
                luecken.append(RECHNUNG_ENTWURF)
            elif versendet_am is None:
                luecken.append(NICHT_VERSENDET)

        zeilen.append({
            "order_id": o.id,
            "order_number": o.order_number,
            "order_status": o.status.value,
            "customer_id": o.customer_id,
            "customer_name": kunde.name if kunde else "",
            "abrechnung": (InvoiceMode.MONATLICH if monatlich else InvoiceMode.EINZELN).value,
            "liefertag": tag,
            "geliefert": geliefert,
            "lieferscheine": [
                {"id": n.id, "nummer": n.delivery_note_number, "status": n.status.value} for n in notes
            ],
            "rechnung": None if rechnung is None else {
                "id": rechnung.id,
                "nummer": rechnung.invoice_number,
                "status": rechnung.status.value,
                "sammelrechnung": rechnung.order_id != o.id,
                "versendet_am": versendet_am,
                "bezahlt": rechnung.status == InvoiceStatus.BEZAHLT,
            },
            "extern_abgerechnet": extern,
            "rechnung_faellig_ab": faellig_ab,
            "luecken": luecken,
            "unvollstaendig": bool(luecken),
        })
    return zeilen
```

`backend/app/api/v1/belegstatus.py` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c3-api -->
```python
"""Belegstatus (Paket 4, Abschnitt C): GET /api/v1/belegstatus.

Rechte wie die Rechnungen (main.py: _deps_geld — Admin, Vertrieb,
Buchhaltung): die Übersicht zeigt Rechnungs-, Versand- und Zahlstatus.
Regeln: app/services/belegstatus.py.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.deps import DBSession, Pagination
from app.schemas.belegstatus import BelegstatusListe
from app.services.belegstatus import belegstatus
from app.services.order_status_service import heute_berlin

router = APIRouter(prefix="/belegstatus", tags=["Belegstatus"])


@router.get("", response_model=BelegstatusListe)
def belegstatus_liste(
    db: DBSession,
    pagination: Pagination,
    von: Optional[date] = None,
    bis: Optional[date] = None,
    kunde_id: Optional[UUID] = None,
    nur_unvollstaendig: bool = False,
):
    """Je Bestellung: Lieferschein erstellt, Rechnung erstellt, versendet, bezahlt.

    - **von** / **bis**: Liefertag (tatsächlich, sonst Wunschtermin)
    - **kunde_id**: ein Kunde
    - **nur_unvollstaendig**: nur geliefert, aber ohne Rechnung, mit
      Rechnungsentwurf oder Rechnung nicht versendet
    - **page** / **page_size**: Seiten (höchstens 100 je Seite)

    `unvollstaendig` zählt die Lücken in Zeitraum und Kunde, auch wenn
    `nur_unvollstaendig` aus ist (Zahl am Filter).
    """
    if von and bis and von > bis:
        raise HTTPException(status_code=422, detail="„von“ liegt nach „bis“")
    heute = heute_berlin()
    zeilen = belegstatus(db, heute=heute, von=von, bis=bis, kunde_id=kunde_id)
    unvollstaendig = [z for z in zeilen if z["unvollstaendig"]]
    auswahl = unvollstaendig if nur_unvollstaendig else zeilen
    return {
        "items": auswahl[pagination.offset:pagination.offset + pagination.page_size],
        "total": len(auswahl),
        "unvollstaendig": len(unvollstaendig),
        "heute": heute,
    }
```

In `backend/app/main.py` die Zeile

<!-- C-BLOCK: c3-main1-alt -->
```python
from app.api.v1 import sepa
```

ersetzen durch

<!-- C-BLOCK: c3-main1-neu -->
```python
from app.api.v1 import sepa
from app.api.v1 import belegstatus
```

und den Block

<!-- C-BLOCK: c3-main2-alt -->
```python
app.include_router(
    invoices.router,
    prefix="/api/v1",
    dependencies=_deps_geld,
)
```

ersetzen durch

<!-- C-BLOCK: c3-main2-neu -->
```python
app.include_router(
    invoices.router,
    prefix="/api/v1",
    dependencies=_deps_geld,
)

# Belegstatus je Bestellung (Paket 4, C): zeigt Rechnungs-, Versand- und
# Zahlstatus — dieselben Rollen wie die Rechnungen
app.include_router(
    belegstatus.router,
    prefix="/api/v1",
    dependencies=_deps_geld,
)
```

Prüfen: `grep -n 'belegstatus' backend/app/main.py` → genau zwei Zeilen: `from app.api.v1 import belegstatus` und `    belegstatus.router,`.

- [ ] **Step 4: Grün, statisch, Vollauf**

Run: Lauf C mit `tests/test_paket4.py::TestP4CBelegstatus` → **`15 passed`**.
Run: `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/schemas/belegstatus.py app/services/belegstatus.py app/api/v1/belegstatus.py app/main.py` → keine Ausgabe, Exit 0.
Run: Prozedur V → Abgleich leer, N = Ausgang + 46 (gemessen auf `df84f7b`: `14 failed, 1690 passed, 2 skipped, 1 error`, auf `521ed6d`: `1864 passed`; im Gesamtplan errechnet `1903 passed`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/belegstatus.py backend/app/services/belegstatus.py backend/app/api/v1/belegstatus.py backend/app/main.py backend/tests/test_paket4.py
git commit -m "feat(belegstatus): je Bestellung Lieferschein, Rechnung, Versand, Zahlung mit Filtern und Seiten (P4-C.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 17 (C.4): Anzeige des Belegstatus als reine Funktionen mit Node-Prüfung

**Files:**
- Create: `frontend/tests/unit/belegstatus.check.ts`
- Create: `frontend/src/services/belegstatus.ts`
- Append: `backend/tests/test_paket4.py` (`TestP4CBelegstatusAnzeige`: die Node-Prüfung im Vollauf)

**Interfaces:**
- Produces:
  - **Typen:** `Luecke`, `BelegstatusLieferschein`, `BelegstatusRechnung`, `BelegstatusZeile`, `BelegstatusListe`, `BelegstatusFilter`, `Zelle {zeichen, text, ton}`.
  - **Texte:** `LUECKEN_TEXT`.
  - **Funktionen:** `datumKurz(wert)`, `heuteBerlin(jetzt?)`, `vorgabeVon(heute)`, `lieferscheinZelle(z)`, `rechnungZelle(z)`, `versandZelle(z)`, `zahlungZelle(z)`.
- Consumes: die Antwortform aus C.3.

**Review Focus (C.4):**
- `ton: 'luecke'` erscheint nur, wenn die Zelle einen Code aus `z.luecken` erklärt. Der fehlende LS ist grau (C-E6).
- `versendet_am` ist UTC ohne Zone und wird in Berlin angezeigt.
- Die Datei hat **keine Importe**, sie wird direkt mit Node geladen.

- [ ] **Step 1: Prüfskript und Test**

`frontend/tests/unit/belegstatus.check.ts` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c4-check -->
```ts
// Prüft die Anzeige des Belegstatus ohne Browser und ohne Testframework (Paket 4, Abschnitt C).
// Lauf: node tests/unit/belegstatus.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import {
  LUECKEN_TEXT, datumKurz, heuteBerlin, lieferscheinZelle, rechnungZelle, versandZelle, vorgabeVon, zahlungZelle,
} from '../../src/services/belegstatus.ts';
import type { BelegstatusZeile } from '../../src/services/belegstatus.ts';

let faelle = 0;
function gleich(ist: unknown, soll: unknown, was: string): void {
  assert.deepEqual(ist, soll, was);
  faelle += 1;
}

function zeile(teil: Partial<BelegstatusZeile>): BelegstatusZeile {
  return {
    order_id: 'o1', order_number: 'BE-20261008-0006', order_status: 'GELIEFERT',
    customer_id: 'k1', customer_name: 'Ferdinand Bierbichler GmbH & Co. KG', abrechnung: 'EINZELN',
    liefertag: '2026-10-09', geliefert: true, lieferscheine: [], rechnung: null,
    extern_abgerechnet: false, rechnung_faellig_ab: '2026-10-09', luecken: [], unvollstaendig: false,
    ...teil,
  };
}
const ls = { id: 'l1', nummer: 'LS-20261009-0001', status: 'GELIEFERT' };
const re = (teil: Record<string, unknown> = {}) => ({
  id: 'r1', nummer: 'RE-2026-00008', status: 'OFFEN', sammelrechnung: false,
  versendet_am: null as string | null, bezahlt: false, ...teil,
});

// Datum: Tag wie geschrieben, Zeitstempel ohne Zone = UTC, angezeigt in Berlin
gleich(datumKurz('2026-10-08'), '08.10.2026', 'Tag');
gleich(datumKurz('2026-10-08T06:19:56.168045'), '08.10.2026', 'Zeitstempel vom Server');
gleich(datumKurz('2026-10-31T23:30:00'), '01.11.2026', 'UTC 23:30 = Berlin 00:30 am 1.11.');
gleich(datumKurz(null), '', 'ohne Datum');
gleich(datumKurz('kein Datum'), '', 'unlesbar');

// Stichtag und Vorgabe „von“ (1. des Vormonats)
gleich(heuteBerlin(new Date('2026-10-08T22:30:00Z')), '2026-10-09', 'heute in Berlin');
gleich(vorgabeVon('2026-10-09'), '2026-09-01', 'Vormonat');
gleich(vorgabeVon('2027-01-15'), '2026-12-01', 'Jahreswechsel');

// Lieferschein
gleich(lieferscheinZelle(zeile({ lieferscheine: [ls] })), { zeichen: '✔', text: 'LS-20261009-0001', ton: 'ok' }, 'LS da');
gleich(lieferscheinZelle(zeile({ lieferscheine: [ls, { ...ls, nummer: 'LS-20261009-0002' }] })).text,
  'LS-20261009-0001, LS-20261009-0002', 'zwei LS');
gleich(lieferscheinZelle(zeile({})), { zeichen: '✘', text: 'fehlt', ton: 'neutral' }, 'LS fehlt (keine Lücke)');
gleich(lieferscheinZelle(zeile({ extern_abgerechnet: true })), { zeichen: '—', text: 'extern', ton: 'neutral' }, 'extern');

// Rechnung
gleich(rechnungZelle(zeile({ luecken: ['OHNE_RECHNUNG'] })), { zeichen: '✘', text: 'fehlt', ton: 'luecke' }, 'RE fehlt');
gleich(rechnungZelle(zeile({ rechnung: re({ status: 'ENTWURF', nummer: 'ENTWURF-AB12' }), luecken: ['RECHNUNG_ENTWURF'] })),
  { zeichen: '◐', text: 'Entwurf', ton: 'luecke' }, 'Entwurf');
gleich(rechnungZelle(zeile({ rechnung: re() })), { zeichen: '✔', text: 'RE-2026-00008', ton: 'ok' }, 'RE da');
gleich(rechnungZelle(zeile({ rechnung: re({ sammelrechnung: true }) })).text, 'RE-2026-00008 (Sammelrechnung)', 'Sammel');
gleich(rechnungZelle(zeile({ extern_abgerechnet: true })), { zeichen: '✔', text: 'extern (DATEV)', ton: 'neutral' }, 'extern');
gleich(rechnungZelle(zeile({ abrechnung: 'MONATLICH', rechnung_faellig_ab: '2026-11-01' })),
  { zeichen: '—', text: 'Monatsrechnung ab 01.11.2026', ton: 'neutral' }, 'Monatskunde');
gleich(rechnungZelle(zeile({ geliefert: false, liefertag: '2026-10-12', rechnung_faellig_ab: '2026-10-12' })),
  { zeichen: '—', text: 'nicht geliefert', ton: 'neutral' }, 'noch nicht geliefert');
gleich(rechnungZelle(zeile({ rechnung_faellig_ab: '2026-10-12', liefertag: '2026-10-12' })),
  { zeichen: '—', text: 'fällig ab 12.10.2026', ton: 'neutral' }, 'geliefert, noch nicht fällig');

// Versand
gleich(versandZelle(zeile({ rechnung: re(), luecken: ['NICHT_VERSENDET'] })),
  { zeichen: '✘', text: 'nicht versendet', ton: 'luecke' }, 'nicht versendet');
gleich(versandZelle(zeile({ rechnung: re({ versendet_am: '2026-10-08T06:19:56.168045' }) })),
  { zeichen: '✔', text: '08.10.2026', ton: 'ok' }, 'versendet');
gleich(versandZelle(zeile({ rechnung: re({ status: 'ENTWURF' }) })), { zeichen: '—', text: '', ton: 'neutral' }, 'Entwurf');
gleich(versandZelle(zeile({})), { zeichen: '—', text: '', ton: 'neutral' }, 'ohne RE');

// Zahlung (nur Anzeige, keine Lücke)
gleich(zahlungZelle(zeile({ rechnung: re({ status: 'BEZAHLT', bezahlt: true }) })), { zeichen: '✔', text: 'bezahlt', ton: 'ok' }, 'bezahlt');
gleich(zahlungZelle(zeile({ rechnung: re({ status: 'UEBERFAELLIG' }) })), { zeichen: '✘', text: 'überfällig', ton: 'neutral' }, 'überfällig');
gleich(zahlungZelle(zeile({ rechnung: re({ status: 'TEILBEZAHLT' }) })).text, 'teilbezahlt', 'teilbezahlt');
gleich(zahlungZelle(zeile({})), { zeichen: '—', text: '', ton: 'neutral' }, 'ohne RE');

// Texte der Lücken
gleich(Object.keys(LUECKEN_TEXT), ['OHNE_RECHNUNG', 'RECHNUNG_ENTWURF', 'NICHT_VERSENDET'], 'Lückenarten wie der Server');

console.log(`belegstatus.check: ${faelle} Fälle ok`);
```

Diesen Block ans Ende von `backend/tests/test_paket4.py` anhängen:

<!-- C-BLOCK: c4-test -->
```python


class TestP4CBelegstatusAnzeige:
    """Anzeige der Spalten (frontend/src/services/belegstatus.ts): die
    Node-Prüfung läuft im Vollauf mit (wie die Node-Tests aus Paket 3 und O)."""

    def test_node_pruefung(self):
        import os
        import subprocess
        from pathlib import Path
        r = subprocess.run(
            ["node", "tests/unit/belegstatus.check.ts"],
            cwd=Path(__file__).resolve().parents[2] / "frontend",
            env={**os.environ, "TZ": "UTC"}, capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip() == "belegstatus.check: 29 Fälle ok"
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd frontend && node tests/unit/belegstatus.check.ts`. Erwartet ist ein Abbruch mit `Error [ERR_MODULE_NOT_FOUND]: Cannot find module '…/frontend/src/services/belegstatus.ts' imported from …/frontend/tests/unit/belegstatus.check.ts`.
Run: Lauf C mit `tests/test_paket4.py::TestP4CBelegstatusAnzeige`. Erwartet: **`1 failed`** (`AssertionError` mit `ERR_MODULE_NOT_FOUND` im Text).

- [ ] **Step 3: Modul anlegen**

`frontend/src/services/belegstatus.ts` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c4-modul -->
```ts
/**
 * Belegstatus je Bestellung (Paket 4, Abschnitt C; Gernot 08.10.2026, B2):
 * Typen der Antwort von GET /belegstatus und die Anzeige der Spalten
 * Lieferschein, Rechnung, Versand und Zahlung. Die Regeln (geliefert, fällig,
 * unvollständig) stehen im Server: backend/app/services/belegstatus.py.
 *
 * Bewusst ohne Importe: tests/unit/belegstatus.check.ts lädt die Datei direkt
 * mit Node (wie dateiname.ts).
 */

export type Luecke = 'OHNE_RECHNUNG' | 'RECHNUNG_ENTWURF' | 'NICHT_VERSENDET';

export interface BelegstatusLieferschein {
  id: string;
  nummer: string;
  status: string;
}

export interface BelegstatusRechnung {
  id: string;
  /** Entwurf: Platzhalter ENTWURF-… (keine Nummer) */
  nummer: string;
  status: string;
  sammelrechnung: boolean;
  versendet_am: string | null;
  bezahlt: boolean;
}

export interface BelegstatusZeile {
  order_id: string;
  order_number: string;
  order_status: string;
  customer_id: string;
  customer_name: string;
  abrechnung: 'EINZELN' | 'MONATLICH';
  liefertag: string;
  geliefert: boolean;
  lieferscheine: BelegstatusLieferschein[];
  rechnung: BelegstatusRechnung | null;
  extern_abgerechnet: boolean;
  rechnung_faellig_ab: string;
  luecken: Luecke[];
  unvollstaendig: boolean;
}

export interface BelegstatusListe {
  items: BelegstatusZeile[];
  total: number;
  /** unvollständige Zeilen in Zeitraum und Kunde (Zahl am Filter) */
  unvollstaendig: number;
  heute: string;
}

export interface BelegstatusFilter {
  von?: string;
  bis?: string;
  kunde_id?: string;
  nur_unvollstaendig?: boolean;
  page?: number;
  page_size?: number;
}

export const LUECKEN_TEXT: Record<Luecke, string> = {
  OHNE_RECHNUNG: 'Rechnung fehlt',
  RECHNUNG_ENTWURF: 'Rechnung nur als Entwurf',
  NICHT_VERSENDET: 'Rechnung nicht versendet',
};

/** Eine Zelle der Übersicht. ton 'luecke' nur, wenn die Zelle eine Lücke der Zeile erklärt. */
export interface Zelle {
  zeichen: '✔' | '✘' | '◐' | '—';
  text: string;
  ton: 'ok' | 'luecke' | 'neutral';
}

const NUR_TAG = /^(\d{4})-(\d{2})-(\d{2})$/;
const MIT_ZONE = /(Z|[+-]\d{2}:?\d{2})$/i;

/**
 * TT.MM.JJJJ. Ein Tag „2026-10-08“ gilt wie geschrieben; ein Zeitstempel ohne
 * Zone ist UTC (der Server speichert sent_at in UTC) und wird in Berliner
 * Zeit angezeigt. Leer ohne oder bei unlesbarem Wert.
 */
export function datumKurz(wert: string | null | undefined): string {
  if (!wert) return '';
  const tag = NUR_TAG.exec(wert);
  if (tag) return `${tag[3]}.${tag[2]}.${tag[1]}`;
  const zeit = new Date(MIT_ZONE.test(wert) ? wert : `${wert}Z`);
  if (Number.isNaN(zeit.getTime())) return '';
  return new Intl.DateTimeFormat('de-DE', {
    timeZone: 'Europe/Berlin', day: '2-digit', month: '2-digit', year: 'numeric',
  }).format(zeit);
}

/** Heute in Berlin als JJJJ-MM-TT. */
export function heuteBerlin(jetzt: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(jetzt);
}

/** Vorgabe für „von“: der 1. des Vormonats. */
export function vorgabeVon(heute: string): string {
  const [jahr, monat] = heute.split('-').map(Number);
  return monat === 1 ? `${jahr - 1}-12-01` : `${jahr}-${String(monat - 1).padStart(2, '0')}-01`;
}

export function lieferscheinZelle(z: BelegstatusZeile): Zelle {
  if (z.lieferscheine.length) {
    return { zeichen: '✔', text: z.lieferscheine.map((l) => l.nummer).join(', '), ton: 'ok' };
  }
  if (z.extern_abgerechnet) return { zeichen: '—', text: 'extern', ton: 'neutral' };
  return { zeichen: '✘', text: 'fehlt', ton: 'neutral' };
}

export function rechnungZelle(z: BelegstatusZeile): Zelle {
  const r = z.rechnung;
  if (r && r.status === 'ENTWURF') {
    return { zeichen: '◐', text: 'Entwurf', ton: z.luecken.includes('RECHNUNG_ENTWURF') ? 'luecke' : 'neutral' };
  }
  if (r) return { zeichen: '✔', text: r.sammelrechnung ? `${r.nummer} (Sammelrechnung)` : r.nummer, ton: 'ok' };
  if (z.extern_abgerechnet) return { zeichen: '✔', text: 'extern (DATEV)', ton: 'neutral' };
  if (z.luecken.includes('OHNE_RECHNUNG')) return { zeichen: '✘', text: 'fehlt', ton: 'luecke' };
  if (!z.geliefert) return { zeichen: '—', text: 'nicht geliefert', ton: 'neutral' };
  if (z.abrechnung === 'MONATLICH') {
    return { zeichen: '—', text: `Monatsrechnung ab ${datumKurz(z.rechnung_faellig_ab)}`, ton: 'neutral' };
  }
  return { zeichen: '—', text: `fällig ab ${datumKurz(z.rechnung_faellig_ab)}`, ton: 'neutral' };
}

export function versandZelle(z: BelegstatusZeile): Zelle {
  const r = z.rechnung;
  if (!r || r.status === 'ENTWURF') return { zeichen: '—', text: '', ton: 'neutral' };
  if (r.versendet_am) return { zeichen: '✔', text: datumKurz(r.versendet_am), ton: 'ok' };
  return { zeichen: '✘', text: 'nicht versendet', ton: z.luecken.includes('NICHT_VERSENDET') ? 'luecke' : 'neutral' };
}

const ZAHLSTATUS: Record<string, string> = {
  OFFEN: 'offen',
  TEILBEZAHLT: 'teilbezahlt',
  UEBERFAELLIG: 'überfällig',
  MAHNVERFAHREN: 'Mahnverfahren',
};

/** Zahlung: nur Anzeige (Gernot: „optional: bezahlt“), nie eine Lücke. */
export function zahlungZelle(z: BelegstatusZeile): Zelle {
  const r = z.rechnung;
  if (!r || r.status === 'ENTWURF') return { zeichen: '—', text: '', ton: 'neutral' };
  if (r.bezahlt) return { zeichen: '✔', text: 'bezahlt', ton: 'ok' };
  return { zeichen: '✘', text: ZAHLSTATUS[r.status] ?? r.status, ton: 'neutral' };
}
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd frontend && node tests/unit/belegstatus.check.ts && node tests/unit/dateiname.check.ts && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: `belegstatus.check: 29 Fälle ok`, `dateiname.check: 8 Fälle ok`, danach keine Ausgabe von `tsc`.
Run: Lauf C mit `tests/test_paket4.py::TestP4CBelegstatusAnzeige` → **`1 passed`**.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/belegstatus.ts frontend/tests/unit/belegstatus.check.ts backend/tests/test_paket4.py
git commit -m "feat(belegstatus): Anzeige der Spalten als reine Funktionen mit Node-Pruefung (P4-C.4)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 18 (C.5): Seite „Belegstatus“, Route, Navigation, Rollentexte

**Files:**
- Modify: `frontend/src/App.tsx` (Import hinter `Invoices`, Route hinter `invoices`)
- Modify: `frontend/src/components/common/Layout.tsx` (lucide-Import `ListChecks`, Navigationspunkt hinter „Rechnungen“)
- Modify: `frontend/src/components/common/CommandPalette.tsx` (lucide-Import `ListChecks`, Eintrag hinter `nav-invoices`)
- Modify: `frontend/src/services/rollen.ts` (Beschreibung Vertrieb und Buchhaltung)
- Create: `frontend/src/services/belegstatusApi.ts`, `frontend/src/pages/Belegstatus.tsx`

**Interfaces:**
- Produces: Route `/belegstatus`, Navigationspunkt „Belegstatus“ (`ADMIN`, `SALES`, `ACCOUNTING`), Schnellsuche „Belegstatus“, `belegstatusApi.liste(filter) -> Promise<BelegstatusListe>`.
- Consumes:
  - aus `services/api.ts`: `export default api`, `salesApi.listCustomers`, `salesApi.getOrder`
  - `OrderDocumentsModal` (Props `open`, `onClose`, `order`)
  - aus `components/ui`: `Table`, `Pagination`, `Combobox`, `Input` (Prop `error`), `Badge`, `Button`, `OrderStatusBadge`, `EmptyState`
  - `getErrorMessage` (`services/errors`)
  - `PageHeader` und `FilterBar` (`components/common/Layout`)
  - alles aus C.4

**Review Focus (C.5):**
- Die Filter setzen die Seite auf 1 zurück.
- Die Vorgabe „von“ ist der 1. des Vormonats in Berlin.
- Fehler stehen in der Karte unter der FilterBar, die Filter bleiben bedienbar (C-E14). Bei 403 erscheint „Keine Berechtigung für den Belegstatus“ ohne Knopf. Ohne Antwort erscheint der Verbindungshinweis, sonst der Text des Servers, beide mit „Erneut versuchen“.
- „von“ > „bis“ (per Tastatur möglich): Es gibt keine Abfrage (`enabled: false`). Am Feld „bis“ steht „„von“ liegt nach „bis““, in der Karte „Zeitraum ungültig“. Es erscheinen keine Zeilen und keine Zahl der vorigen Antwort.
- „Belege“ lädt die Bestellung und öffnet den vorhandenen Dialog. Beim Schließen lädt die Liste neu.
- Die Zahl hinter „Nur unvollständige (n)“ ist `unvollstaendig` der Antwort.

- [ ] **Step 1: Route, Navigation, Rollentexte**

`frontend/src/App.tsx`, die Zeile

<!-- C-BLOCK: c5-app1-alt -->
```tsx
import Invoices from './pages/Invoices';
```

ersetzen durch

<!-- C-BLOCK: c5-app1-neu -->
```tsx
import Invoices from './pages/Invoices';
import Belegstatus from './pages/Belegstatus';
```

und die Zeile

<!-- C-BLOCK: c5-app2-alt -->
```tsx
          <Route path="invoices" element={<Invoices />} />
```

ersetzen durch

<!-- C-BLOCK: c5-app2-neu -->
```tsx
          <Route path="invoices" element={<Invoices />} />
          <Route path="belegstatus" element={<Belegstatus />} />
```

`frontend/src/components/common/Layout.tsx`, in der lucide-Importliste die Zeile

<!-- C-BLOCK: c5-layout1-alt -->
```tsx
  Receipt,
```

ersetzen durch

<!-- C-BLOCK: c5-layout1-neu -->
```tsx
  Receipt,
  ListChecks,
```

und im Abschnitt „Vertrieb“ den Eintrag

<!-- C-BLOCK: c5-layout2-alt -->
```tsx
      {
        name: 'Rechnungen',
        href: '/invoices',
        icon: Receipt,
        roles: ['ADMIN', 'SALES', 'ACCOUNTING'],
      },
```

ersetzen durch

<!-- C-BLOCK: c5-layout2-neu -->
```tsx
      {
        name: 'Rechnungen',
        href: '/invoices',
        icon: Receipt,
        roles: ['ADMIN', 'SALES', 'ACCOUNTING'],
      },
      {
        // Paket 4, C: je Bestellung Lieferschein, Rechnung, Versand, Zahlung —
        // Rollen wie die Rechnungen (Server: _deps_geld)
        name: 'Belegstatus',
        href: '/belegstatus',
        icon: ListChecks,
        roles: ['ADMIN', 'SALES', 'ACCOUNTING'],
      },
```

`frontend/src/services/rollen.ts`, Beschreibung „Vertrieb“, die Zeile

<!-- C-BLOCK: c5-rollen1-alt -->
```ts
      'Preislisten und Auswertungen. Kein Zugriff auf Tagesplan und Produktion.',
```

ersetzen durch

<!-- C-BLOCK: c5-rollen1-neu -->
```ts
      'Preislisten, Auswertungen und Belegstatus. Kein Zugriff auf Tagesplan und Produktion.',
```

und Beschreibung „Buchhaltung“, die Zeile

<!-- C-BLOCK: c5-rollen2-alt -->
```ts
      'Rechnungen, Zahlungen, Mahnungen, DATEV-Export, Preislisten und Auswertungen; ' +
```

ersetzen durch

<!-- C-BLOCK: c5-rollen2-neu -->
```ts
      'Rechnungen, Belegstatus, Zahlungen, Mahnungen, DATEV-Export, Preislisten und Auswertungen; ' +
```

`frontend/src/components/common/CommandPalette.tsx` (Schnellsuche), in der lucide-Importliste die Zeilen

<!-- C-BLOCK: c5-cmd1-alt -->
```tsx
  Receipt,
  Tag,
```

ersetzen durch

<!-- C-BLOCK: c5-cmd1-neu -->
```tsx
  Receipt,
  ListChecks,
  Tag,
```

und den Eintrag „Rechnungen“

<!-- C-BLOCK: c5-cmd2-alt -->
```tsx
      { id: 'nav-invoices', label: 'Rechnungen', section: 'Navigation', icon: Receipt, action: () => go('/invoices'), keywords: ['rechnung', 'invoice'] },
```

ersetzen durch

<!-- C-BLOCK: c5-cmd2-neu -->
```tsx
      { id: 'nav-invoices', label: 'Rechnungen', section: 'Navigation', icon: Receipt, action: () => go('/invoices'), keywords: ['rechnung', 'invoice'] },
      { id: 'nav-belegstatus', label: 'Belegstatus', section: 'Navigation', icon: ListChecks, action: () => go('/belegstatus'), keywords: ['beleg', 'lieferschein', 'versendet', 'unvollständig'] },
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet ist genau eine Fehlermeldung: `src/App.tsx(…): error TS2307: Cannot find module './pages/Belegstatus' or its corresponding type declarations.` (Exit 2).

- [ ] **Step 3: API und Seite**

`frontend/src/services/belegstatusApi.ts` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c5-api -->
```ts
/**
 * Belegstatus (Paket 4, Abschnitt C): GET /belegstatus. Eigene Datei statt
 * api.ts — dort ändern D und O die Abschnitte invoicesApi und documentsApi.
 */
import api from './api';
import type { BelegstatusFilter, BelegstatusListe } from './belegstatus';

export const belegstatusApi = {
  /** Leere Filter gehen nicht mit; nur_unvollstaendig nur, wenn gesetzt. */
  liste: (filter: BelegstatusFilter) =>
    api.get<BelegstatusListe>('/belegstatus', {
      params: Object.fromEntries(
        Object.entries(filter).filter(([, wert]) => wert !== undefined && wert !== '' && wert !== false),
      ),
    }).then((r) => r.data),
};
```

`frontend/src/pages/Belegstatus.tsx` mit genau diesem Inhalt anlegen:

<!-- C-BLOCK: c5-seite -->
```tsx
import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { AlertCircle, CalendarX, FileText } from 'lucide-react';
import { PageHeader, FilterBar } from '../components/common/Layout';
import { OrderDocumentsModal } from '../components/domain/OrderDocumentsModal';
import {
  Badge, Button, Combobox, EmptyState, Input, OrderStatusBadge, Pagination, Table, useToast,
  type ComboboxOption, type Column,
} from '../components/ui';
import { salesApi } from '../services/api';
import { belegstatusApi } from '../services/belegstatusApi';
import {
  LUECKEN_TEXT, datumKurz, heuteBerlin, lieferscheinZelle, rechnungZelle, versandZelle, vorgabeVon, zahlungZelle,
  type BelegstatusZeile, type Zelle,
} from '../services/belegstatus';
import { getErrorMessage } from '../services/errors';
import { Order } from '../types';

/**
 * Belegstatus (Paket 4, Abschnitt C; Gernot 08.10.2026, B2): je Bestellung
 * Lieferschein erstellt, Rechnung erstellt, Rechnung versendet, bezahlt.
 * Filter Zeitraum (Liefertag), Kunde und „nur unvollständige“. Rechte wie die
 * Rechnungen (Admin, Vertrieb, Buchhaltung); die Halle sieht die Seite nicht.
 */

const SEITE = 50;
const ZEITRAUM_FALSCH = '„von“ liegt nach „bis“';

const TON_KLASSE: Record<Zelle['ton'], string> = {
  ok: 'text-emerald-700 dark:text-emerald-300',
  luecke: 'text-red-700 dark:text-red-300 font-medium',
  neutral: 'text-gray-500 dark:text-gray-400',
};

function ZellenText({ zelle }: { zelle: Zelle }) {
  return (
    <span className={`whitespace-nowrap ${TON_KLASSE[zelle.ton]}`}>
      <span aria-hidden="true">{zelle.zeichen}</span>
      {zelle.text && <span className="ml-1">{zelle.text}</span>}
    </span>
  );
}

export default function Belegstatus() {
  const toast = useToast();
  const [von, setVon] = useState(() => vorgabeVon(heuteBerlin()));
  const [bis, setBis] = useState('');
  const [kundeId, setKundeId] = useState('');
  const [nurUnvollstaendig, setNurUnvollstaendig] = useState(false);
  const [seite, setSeite] = useState(1);
  const [belegeOrder, setBelegeOrder] = useState<Order | null>(null);
  const [oeffnet, setOeffnet] = useState<string | null>(null);

  // min/max sperren nur den Kalender, per Tastatur geht „von“ nach „bis“: Dann
  // fragt die Seite den Server nicht (er antwortete 422), die Filter bleiben bedienbar
  const zeitraumFalsch = von !== '' && bis !== '' && von > bis;
  const filter = { von, bis, kunde_id: kundeId, nur_unvollstaendig: nurUnvollstaendig, page: seite, page_size: SEITE };
  const statusQuery = useQuery({
    queryKey: ['belegstatus', filter],
    queryFn: () => belegstatusApi.liste(filter),
    placeholderData: keepPreviousData,
    enabled: !zeitraumFalsch,
  });

  const kundenQuery = useQuery({
    queryKey: ['customers', 'belegstatus'],
    queryFn: () => salesApi.listCustomers({ page_size: 500 }),
  });
  const kundenOptionen: ComboboxOption[] = [
    { value: '', label: 'Alle Kunden' },
    ...(kundenQuery.data?.items ?? [])
      .map((k) => ({ value: k.id, label: k.name }))
      .sort((a, b) => a.label.localeCompare(b.label, 'de')),
  ];

  // Jeder Filterwechsel beginnt wieder auf Seite 1
  const neu = <T,>(setzen: (wert: T) => void) => (wert: T) => { setzen(wert); setSeite(1); };

  const belegeOeffnen = async (z: BelegstatusZeile) => {
    setOeffnet(z.order_id);
    try {
      setBelegeOrder(await salesApi.getOrder(z.order_id));
    } catch (e) {
      toast.error(getErrorMessage(e, 'Bestellung konnte nicht geladen werden'));
    } finally {
      setOeffnet(null);
    }
  };
  const belegeSchliessen = () => {
    setBelegeOrder(null);
    if (!zeitraumFalsch) void statusQuery.refetch(); // Rechnung angelegt oder versendet: Zeile neu
  };

  // Fehler stehen in der Karte unter den Filtern, nie statt der Filter
  const fehlerStatus = (statusQuery.error as { response?: { status?: number } } | null)?.response?.status;
  const keineBerechtigung = fehlerStatus === 403;
  const fehlerText = keineBerechtigung
    ? 'Den Belegstatus sehen Admin, Vertrieb und Buchhaltung.'
    : fehlerStatus
      ? getErrorMessage(statusQuery.error, `Der Server antwortet mit Fehler ${fehlerStatus}.`)
      : 'Bitte prüfe die Verbindung zum Server und versuche es erneut.';
  // Bei ungültigem Zeitraum keine Zahlen der vorigen Abfrage (keepPreviousData)
  const daten = zeitraumFalsch ? undefined : statusQuery.data;
  const spalten: Column<BelegstatusZeile>[] = [
    {
      key: 'order_number',
      header: 'Bestellung',
      render: (z) => (
        <div className="space-y-1">
          <div className="font-medium text-gray-900 dark:text-white">{z.order_number}</div>
          <OrderStatusBadge status={z.order_status} />
        </div>
      ),
    },
    {
      key: 'customer_name',
      header: 'Kunde',
      render: (z) => (
        <div>
          <div>{z.customer_name}</div>
          {z.abrechnung === 'MONATLICH' && <div className="text-xs text-gray-500">Monatsrechnung</div>}
        </div>
      ),
    },
    { key: 'liefertag', header: 'Liefertag', render: (z) => datumKurz(z.liefertag) },
    { key: 'lieferschein', header: 'Lieferschein', render: (z) => <ZellenText zelle={lieferscheinZelle(z)} /> },
    { key: 'rechnung', header: 'Rechnung', render: (z) => <ZellenText zelle={rechnungZelle(z)} /> },
    { key: 'versand', header: 'Versendet', render: (z) => <ZellenText zelle={versandZelle(z)} /> },
    { key: 'zahlung', header: 'Bezahlt', render: (z) => <ZellenText zelle={zahlungZelle(z)} /> },
    {
      key: 'luecken',
      header: 'Lücke',
      render: (z) => (
        <div className="flex flex-wrap gap-1">
          {z.luecken.map((l) => <Badge key={l} variant="danger" size="sm">{LUECKEN_TEXT[l]}</Badge>)}
        </div>
      ),
    },
    {
      key: 'aktion',
      header: '',
      align: 'right',
      render: (z) => (
        <Button size="sm" variant="secondary" icon={<FileText className="w-4 h-4" />}
          loading={oeffnet === z.order_id} onClick={() => void belegeOeffnen(z)}>
          Belege
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Belegstatus"
        subtitle="Je Bestellung: Lieferschein, Rechnung, Versand und Zahlung"
      />

      <FilterBar>
        <Input type="date" label="Liefertag von" value={von} max={bis || undefined}
          onChange={(e) => neu(setVon)(e.target.value)} />
        <Input type="date" label="bis" value={bis} min={von || undefined}
          error={zeitraumFalsch ? ZEITRAUM_FALSCH : undefined}
          onChange={(e) => neu(setBis)(e.target.value)} />
        <Combobox label="Kunde" options={kundenOptionen} value={kundeId} onChange={neu(setKundeId)}
          placeholder="Alle Kunden" />
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 self-end pb-2">
          <input type="checkbox" checked={nurUnvollstaendig}
            onChange={(e) => neu(setNurUnvollstaendig)(e.target.checked)} />
          Nur unvollständige{daten ? ` (${daten.unvollstaendig})` : ''}
        </label>
      </FilterBar>

      <p className="text-sm text-gray-500 dark:text-gray-400">
        Unvollständig: geliefert, aber ohne Rechnung, nur mit Rechnungsentwurf oder Rechnung nicht versendet —
        bei Monatskunden ab dem 1. des Folgemonats. „extern (DATEV)“: vor NovaERP abgerechnet (Status Fakturiert).
        Stornierte Bestellungen fehlen.
      </p>

      <div className="card overflow-hidden">
        {zeitraumFalsch ? (
          <EmptyState
            icon={<CalendarX className="w-16 h-16" />}
            title="Zeitraum ungültig"
            description="„Liefertag von“ liegt nach „bis“ — bitte eines der beiden Daten ändern."
          />
        ) : statusQuery.isError ? (
          <EmptyState
            icon={<AlertCircle className="w-16 h-16 text-red-400" />}
            title={keineBerechtigung ? 'Keine Berechtigung für den Belegstatus' : 'Belegstatus konnte nicht geladen werden'}
            description={fehlerText}
            action={keineBerechtigung ? undefined : (
              <Button variant="secondary" loading={statusQuery.isFetching} onClick={() => void statusQuery.refetch()}>
                Erneut versuchen
              </Button>
            )}
          />
        ) : (
          <>
            <Table
              columns={spalten}
              data={daten?.items ?? []}
              keyExtractor={(z) => z.order_id}
              loading={statusQuery.isLoading}
              emptyMessage={nurUnvollstaendig ? 'Keine unvollständigen Bestellungen im Zeitraum' : 'Keine Bestellungen im Zeitraum'}
            />
            {daten && daten.total > SEITE && (
              <Pagination
                currentPage={seite}
                totalPages={Math.ceil(daten.total / SEITE)}
                totalItems={daten.total}
                itemsPerPage={SEITE}
                onPageChange={setSeite}
              />
            )}
          </>
        )}
      </div>

      <OrderDocumentsModal open={!!belegeOrder} onClose={belegeSchliessen} order={belegeOrder} />
    </div>
  );
}
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
Run: `cd frontend && npm run build` → `✓ built in …`.
Prüfen: `grep -c "belegstatus" frontend/src/App.tsx frontend/src/components/common/Layout.tsx frontend/src/components/common/CommandPalette.tsx` → `App.tsx:1`, `Layout.tsx:1`, `CommandPalette.tsx:1` (Route, `href` bzw. die Zeile `nav-belegstatus`). `grep -c 'Belegstatus' frontend/src/services/rollen.ts` → `2`. `grep -c 'enabled: !zeitraumFalsch' frontend/src/pages/Belegstatus.tsx` → `1`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/common/Layout.tsx frontend/src/components/common/CommandPalette.tsx frontend/src/services/rollen.ts frontend/src/services/belegstatusApi.ts frontend/src/pages/Belegstatus.tsx
git commit -m "feat(belegstatus): Seite Belegstatus mit Filtern, Seiten und Belege-Dialog; Navigation wie Rechnungen (P4-C.5)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 19 (C.6): Abschluss C — Vollauf, statische Prüfung, Meldung (ohne Commit)

- [ ] **Step 1:** Prozedur V. Der Abgleich ist leer, N = Ausgang + 47 (gemessen auf `df84f7b`: `14 failed, 1691 passed, 2 skipped, 1 error`, auf `521ed6d`: `1865 passed`; im Gesamtplan errechnet `1904 passed`).
- [ ] **Step 2:** Lauf C mit `tests/test_paket4.py::TestP4CDateiname tests/test_paket4.py::TestP4CDateinameDownloads tests/test_paket4.py::TestP4CDateinameMail tests/test_paket4.py::TestP4CBelegstatus tests/test_paket4.py::TestP4CBelegstatusAnzeige` → **`47 passed`**. Dazu `tests/test_gernot_261008_paket3.py` → `467 passed`.
- [ ] **Step 3:** `cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/services/beleg_dateiname.py app/services/belegversand.py app/api/v1/documents.py app/api/v1/invoices.py app/schemas/belegstatus.py app/services/belegstatus.py app/api/v1/belegstatus.py app/main.py tests/test_paket4.py tests/test_gernot_261008_paket3.py` → keine Ausgabe, Exit 0.
- [ ] **Step 4:** `cd frontend && node tests/unit/belegstatus.check.ts && ./node_modules/.bin/tsc --noEmit -p . && npm run build 2>&1 | tail -1` → `belegstatus.check: 29 Fälle ok`, dann `✓ built in …`.
- [ ] **Step 5:** `git diff --stat <Basis C>..HEAD` → genau die 18 Dateien aus „File Structure (C)“. `git log --oneline <Basis C>..HEAD` → fünf Commits C.1–C.5. `<Basis C>` ist `git rev-parse HEAD` vor C.1 und steht im Bericht.
- [ ] **Step 6: Abschlussmeldung C** (Zwischenstand, nicht anhalten). Sie enthält Basis C, die Summenzeilen aus Step 1 und 2, Exit-Codes, Diff-Stat, Commits und jede Abweichung samt Stoppregel-5-Korrekturen.

---

## Abschnitt P4-D — Rechte der Rolle Produktion bei Kunden-Stammdaten (G41, B8; G40/G42–G44/G60 als Umfeld) — Tasks 20–23 (P4-D.1–P4-D.4)

> **Rahmen:** Arbeitsort, Tests, Commits, Stoppregeln, Baseline und Prozedur V stehen im Kopf des Plans (Global Constraints). Dieser Abschnitt heißt im Plan **P4-D**, seine Tasks **P4-D.1–P4-D.4** = Tasks 20–23 (so in Code-Kommentaren, Commit-Betreffen und Berichten; „D.1“–„D.4“ im Text dieses Abschnitts meinen sie, „D/F/O“ und „Nachtrag-Task“ den Nachtrag 09.10.). Ausnahme von „Bestehende Tests ändert kein Task“: P4-D.2 Step 5 (= Task 21, Step 5; E-D6). Die Abschlussmeldung in Task 23 ist ein Zwischenstand — nicht anhalten, danach folgt Task 24. Abnahme RF-D1–RF-D5, Runbooks R-D0–R-D2 und die Offenen Punkte von P4-D stehen am Ende des Plans.

**Ziel:** Gernots Wunsch für den Mitarbeiter-Login vom 08.10. (B8, G41) wird in der Rolle `production_staff` („Produktion“, intern „die Halle“) **für die Kunden-Stammdaten** umgesetzt. Seine Worte: „Mitarbeiter: Tagesplan, Packen, Ausliefern; kein Rechnungswesen/DATEV/Stammdaten-Löschen“. Dazu kommt unsere Zusage vom 09.10.: „Rolle ‚Produktion‘ ohne Rechnungen/Konditionen“. Gernot hat darauf mit „Danke!“ geantwortet (G60). Bestellungen, AB und Lieferscheine anlegen und versenden bleibt erlaubt (G42, G43). Kunden anlegen und ändern bleibt der Halle in Server und Oberfläche erlaubt, ohne Konditionen und ohne Löschen (Gernot, 03.09.; E-D1, E-D7). **Nicht umgesetzt** ist „kein Stammdaten-Löschen“ außerhalb der Kunden: Die Halle kann Lagerorte weiter über die Schnittstelle deaktivieren (I-D1).

**Befund (gemessen auf `df84f7b` in `/tmp/p4-kopie-d`):** Alle Schreib- und Löschrouten, die `production_staff` passieren lässt (Werkzeug `/tmp/p4-d-tools/delete_routes.py`, Status ≠ 403):
- **Löschen von Kunden-Stammdaten offen:** `DELETE /api/v1/sales/customers/{id}/addresses/{id}` und `DELETE …/contacts/{id}`. Beide haben keine Rollenprüfung, weil der Sales-Router über `_deps_auftraege` (`app/main.py`) für die Halle schreibbar ist. Die übrigen offenen DELETE-Routen sind keine Stammdaten: Zusatzaufgaben, Bestellentwurf, Bestellposition, Leergut-Rücknahme.
- **Deaktivieren ist Löschen über einen anderen Weg:** `DELETE /customers/{id}` ist nur kaufmännisch und deaktiviert Kunden mit Belegen (Soft-Delete). Dasselbe geht für Halle und Planung aber über `PATCH /customers/{id}` mit `{"aktiv": false}` (gemessen: 200). Zurückholen geht über `POST /customers/{id}/reactivate` (Halle: 200).
- **Konditionen sichtbar:**
  - `GET /sales/customers`, `GET /sales/customers/{id}` und die Antwort auf `PATCH` liefern der Halle alle Konditionen: Zahlungsziel, Rabatt, Skonto, Kreditlimit, Preisliste, DATEV-Konto, Pfand- und Abrechnungsart, Zahlungsart, `payment_days`.
  - `GET /sales/customers/{id}/prices` liefert die Sonderpreisliste. In Produktion gibt es 91 Sonderpreise.
  - Die 400-Meldung des Kreditlimits in `create_order` nennt Limit und offene Summe.
- **Oberfläche (Halle erreicht die Kundenseite mit einem Klick):**
  - Die Route `/customers` (`App.tsx`) ist ungeschützt. Der Menüpunkt „Kunden“ (`Layout.tsx`) steht nur bei `ADMIN`, `SALES` und `ACCOUNTING`.
  - Die Befehlspalette bietet aber **allen Rollen** „Kunden“ und „Neuen Kunden anlegen“ an (`frontend/src/components/common/CommandPalette.tsx`, Einträge `'nav-customers'` und `'action-new-customer'`, ohne Rollenfilter). Sie öffnet sich über den sichtbaren Kopfknopf „Suchen… Strg+K“ (`Layout.tsx` rendert `<CommandPalette>` ungefiltert, nur `istAdmin` steuert die Benutzerverwaltung).
  - Auf der Seite legt die Halle heute Kunden an und ändert sie. `CustomerForm` in `Customers.tsx` ist der einzige Aufrufer von `salesApi.createCustomer`. Der Server erlaubt es ausdrücklich (Paket-3-Test `test_halle_legt_kunden_mit_standardkonditionen_an`: „Neuanlage aus dem Formular … erlaubt (Gernot, 03.09.)“).
  - Dort sieht die Halle heute auch Konditionen, den Sonderpreis-Knopf und den Excel-Import (Server: `/imports` → 403). Der Papierkorb für Adressen und Ansprechpartner hat keine Rollenprüfung.
  - Der Löschfehler wird verschluckt, denn die Mutation hat kein `onError`.
  - Einen Knopf „Kunde löschen“ gibt es nicht: Den Lösch-Dialog in `Customers()` öffnet nichts, `setDeletingCustomer` wird nur mit `null` aufgerufen.
- **Schon dicht (Wachhund in D.2):** Für die Halle sind alle Routen unter `/api/v1/invoices`, `/price-lists`, `/sepa` und `/analytics` gesperrt, ebenso DATEV-Debitorenexport, Sonderpreise schreiben und Katalogpreis. Von den 53 geprüften Routen×Methoden antworten 52 mit 403. Offen ist nur `GET /sales/customers/{customer_id}/prices` (s. o.). `GET /products/{id}` liefert `prices: null`: Die ORM-Beziehung heißt `price_list_items`, deshalb kommen keine Preislistenpositionen mit.
- **Produktion lesend (09.10.):**
  - 46 Kunden, davon 8 inaktiv. Kein Kunde hat ein Kreditlimit, 1 hat Rabatt, 4 haben ein abweichendes Zahlungsziel.
  - 0 Adressen, 4 Ansprechpartner, 91 Sonderpreise.
  - `benutzer_audit` hat 0 Zeilen: Über die Benutzerverwaltung (B8) wurde noch kein Login angelegt. Konten, die vorher direkt in Keycloak entstanden, erfasst die Tabelle nicht (sie wird nur von `app/api/v1/users.py` geschrieben). Wer Kunden, Adressen oder Ansprechpartner geändert oder gelöscht hat, speichert das System nicht.
  - Prod läuft mit FastAPI 0.109.0 und Pydantic 2.5.3.

**Ausgangsstand:** `main` nach dem Merge des Nachtrags D/F/O (`/tmp/n0910/plan.md`). Geplant und gemessen ist der Abschnitt auf `df84f7b`. D/F/O ändert keine Datei dieses Abschnitts (siehe „Überschneidungen“), deshalb gelten alle Anker unverändert.

**Abschnittsregeln:** Es gelten die Global Constraints des Plans (Arbeitsort, Tests `TestP4D…`/`_p4d_…`/`_P4D_…`, Bestehende Tests mit der Ausnahme P4-D.2 Step 5, Commits, Stoppregeln 1–5; „Kein Stopp“ ist dort Regel 5).

### Entscheidungen mit Begründung (Manager)

- **E-D1 — Adressen und Ansprechpartner löschen nur Rollen ohne die Halle** (`ROLLEN_OHNE_HALLE` = admin, sales, accounting, production_planner).
  - Begründung: Gernot sagt „kein Stammdaten-Löschen“. Die Rollengruppe ist dieselbe wie bei Sonderpreisen und Empfängern (T5 R2, Paket 3). Die Planung behält ihr heutiges Recht, Gernots Satz betrifft die Mitarbeiter.
  - **Anlegen und Ändern bleiben für die Halle offen, im Server und in der Oberfläche.** Das hat Gernot am 03.09. ausdrücklich festgelegt: „bei Ausfall der Betriebsleitung müssen die Mitarbeiter erfassen können“ (`main.py`, `_deps_auftraege`; Paket-3-Test `test_halle_legt_kunden_mit_standardkonditionen_an`). G41 verlangt nur „kein Stammdaten-Löschen“, G60 nur „ohne Konditionen“. Deshalb bleibt die Kundenseite für die Halle erreichbar, nur ohne Konditionen und ohne Löschen (E-D7). Ob Gernot das heute noch so will, bestätigt Frage F-D1. Sie blockiert den Deploy nicht, weil P4-D den heutigen Stand nur einschränkt.
- **E-D2 — Den Aktiv-Schalter des Kunden ändern nur kaufmännische Rollen** (`KAUFMAENNISCHE_ROLLEN` = admin, sales, accounting). Das gilt für `PATCH aktiv` in beide Richtungen und für `POST /reactivate`.
  - Begründung: `delete_customer` deaktiviert Kunden mit Belegen und ist schon heute nur kaufmännisch (Paket-3-Test `test_halle_darf_keinen_kunden_loeschen`). Derselbe Schritt über `PATCH` war ein Seiteneingang. Deshalb fällt hier auch die **Planung** heraus (gemessen: heute 200).
  - Umsetzung als eigene Liste `KUNDENFELD_AKTIV` in `kundenfeldschutz`, nicht als Eintrag in `KUNDENFELDER_KAUFMAENNISCH`. Grund: `aktiv` ist keine Kondition und wird nicht ausgeblendet, und der Paket-3-Wachhund `TestQ4KundenfelderEingeordnet` führt `aktiv` als frei und bliebe sonst nicht grün.
  - Wie beim Feldschutz greift die Regel nur bei einer echten Änderung, denn das Kundenformular schickt `aktiv` immer mit.
  - **Rückweg:** Soll die Planung doch deaktivieren dürfen, wird der Block in `kundenfeldschutz` auf `hat_rolle(user, ROLLEN_OHNE_HALLE)` umgestellt. Dann kippt `test_planung_deaktiviert_keinen_kunden`.
- **E-D3 — In Kundenantworten an die Halle stehen die Konditionen als `null`** (Liste, Detail, Antwort auf `PATCH`).
  - Die Felder stehen in `KUNDENANTWORT_KONDITIONEN`: alle aus `KUNDENFELDER_KAUFMAENNISCH`, sodass ein neues Konditionsfeld automatisch mit ausgeblendet wird, dazu `price_list_name`, `payment_days`, `pfand_monatlich_ab` und `zahlungsart`.
  - **Mechanik:** Eine Funktion `sales._kundenantwort(customer, user)` setzt die Felder per `model_copy(update=…)` auf `null`. Dafür werden die Konditionsfelder in `CustomerResponse` `Optional`. Für alle anderen Rollen bleiben die Werte gleich.
  - Ein eigenes Schema nur für die Halle wäre die Alternative. Es hätte zwei Antworttypen je Route bedeutet, und der Frontend-Typ `Customer` führt die Felder ohnehin schon als optional (`types/index.ts`).
  - Gemessen: Die Maskierung funktioniert auch mit der Prod-Version FastAPI 0.109.0 / Pydantic 2.5.3 (lokaler Docker, `/tmp/p4-d-tools/repro109.py`).
  - **Die Antwort auf `POST /customers` bleibt unverändert.** Die Halle legt nur mit Standardkonditionen an (`kundenfeldschutz`), die Antwort verrät also nichts, und der Paket-3-Test `test_halle_legt_kunden_mit_standardkonditionen_an` bleibt wörtlich grün.
  - `reactivate` braucht keine Maskierung: Die Halle darf die Route nach E-D2 nicht mehr aufrufen.
  - **Regel für Clients der Halle:** Sie schicken die Konditionsfelder nicht zurück. Das Kundenformular hält sich daran (P4-D.3, `ohneKonditionen`), der Test `test_halle_speichert_das_formular_ohne_konditionen` sichert es im Server ab. Schickt ein Client sie trotzdem, gilt:
    - `pfand_abrechnung: null` oder `invoice_mode: null` lehnt schon die Validierung in `CustomerUpdate` mit **422** ab („… darf nicht leer sein“).
    - Jedes andere Konditionsfeld, das vom gespeicherten Wert abweicht, lehnt `kundenfeldschutz` mit **403** ab („Abrechnungsrelevante Kundenfelder … Formular veraltet“). Das gilt für `null` ebenso wie für eine Formularvorgabe wie `NET_14` oder `0` (gemessen auf `df84f7b`).
- **E-D4 — Die Sonderpreisliste je Kunde lesen nur Rollen ohne die Halle.** Der gültige Preis je Produkt (`effective-price`) bleibt offen, denn das Bestellformular braucht ihn, und Bestellung und AB tragen Preise (Gernot 08.10., G42/G43).
  - In Kauf genommen: Die Halle sieht beim Bestellen den Preis des gewählten Produkts, auch wenn es ein Sonderpreis ist (Frage F-D3).
  - Die Oberfläche lädt die Liste nur in `CustomerPricesModal` auf der Kundenseite. Das Bestellformular nutzt allein `getEffective`.
- **E-D5 — Ohne Beträge meldet die Halle nur, dass das Kreditlimit überschritten ist.** Das Limit ist eine Kondition (`credit_limit`). Produktion hat heute kein Limit gesetzt, die Regel gilt also vorsorglich.
- **E-D6 — Zwei Paket-3-Tests schreiben das alte Leserecht fest und werden gezielt angepasst.**
  - `TestQ4SonderpreiseDatevKatalogpreis::test_halle_liest_sonderpreis_fuers_bestellformular` verlangt heute 200 auf die Sonderpreisliste. Neu verlangt er 403 auf die Liste und weiter 200 auf `effective-price`. Seine Absicht „fürs Bestellformular“ bleibt damit erhalten.
  - `TestQ7Feldschutz::test_halle_aendert_die_abrechnungsart_nicht` liest am Ende `invoice_mode` als Halle. Neu liest er als Admin. Seine Absicht „Halle ändert die Abrechnungsart nicht“ bleibt erhalten.
  - Begründung: Gernots Zusage vom 09.10. geht der Paket-3-Annahme „Lesen der Sonderpreise bleibt offen (Bestellformular)“ vor. Die Liste brauchte das Bestellformular nie.
  - Die Abnahmetests von D/F/O (`TestAbnahmeSepaBerlin`, `TestAbnahmeRechnungsberechtigung`) liegen in derselben Datei, werden aber nicht berührt.
- **E-D7 — Oberfläche: Die Kundenseite bleibt für die Halle offen, ohne Konditionen und ohne Löschen** (**Variante a**). Der Plan wählt sie, weil sie Gernots Festlegung vom 03.09. und G41/G60 zugleich erfüllt. Der Manager bestätigt die Wahl vor der Ausführung; Variante b steht am Ende dieses Punkts.
  - Kein Wächter vor `/customers`. `App.tsx`, `Layout.tsx` (Menü) und `CommandPalette.tsx` bleiben unverändert. Die Halle erreicht die Seite weiter über „Suchen… Strg+K“ → „Kunden“ bzw. „Neuen Kunden anlegen“ (Befund „Oberfläche“).
  - **Für die Halle** (Login ohne `ROLLEN_OHNE_HALLE`) zeigt `Customers.tsx`:
    - kein Zahlungsziel und keinen Konditionsblock. Darin steht auch „Preise auf Lieferschein andrucken“; der Wert geht unverändert mit;
    - keinen Sonderpreis-Knopf (der Server sperrt die Liste, D.2) und keinen Excel-Import (`/imports` ist `_deps_vertrieb`, Halle 403);
    - den Aktiv-Schalter gesperrt mit Hinweis, wie bei der Planung;
    - Haupt-E-Mail und die drei Empfängerlisten **nach der Neuanlage** gesperrt mit Hinweis. Das ist die Paket-3-Regel `KUNDENFELDER_EMPFAENGER`; bei der Neuanlage bleiben sie frei;
    - keinen Papierkorb bei Adressen und Ansprechpartnern.
  - **Ihr Payload enthält keine Konditionsfelder** (`ohneKonditionen` mit `KUNDEN_KONDITIONSFELDER` = Schlüssel von `KUNDENFELDER_KAUFMAENNISCH`, per Node-Prüfung gegen das Backend). Das ist nötig, weil D.2 maskiert: Die heutige Form würde aus `null` die Vorgaben `NET_14`, `0`, `EINZELN` und `JE_LIEFERUNG` machen und beim Ändern 403 bzw. 422 bekommen (E-D3). Neue Kunden der Halle bekommen damit die Standardkonditionen des Servers.
  - Der Leergut-Knopf der Kundenkarte erscheint nur bei `pfand_abrechnung === 'MONATLICH'`. Für die Halle ist der Wert `null`, also fehlt der Knopf. Die Rücknahme im Tagesplan nutzt `/leergut` und bleibt (E-D10).
  - **Für die Planung** (in `ROLLEN_OHNE_HALLE`, nicht kaufmännisch): Zahlungsziel, Konditionen und Aktiv-Schalter stehen gesperrt mit Hinweis da. Sie sieht den Papierkorb, der Excel-Import und der Sonderpreis-Knopf bleiben.
  - Ein Löschfehler erscheint als Meldung (`onError`).
  - **Variante b (nicht geplant):** Halle ganz ohne Kundenseite. Das wäre eine Abweichung von Gernots Festlegung vom 03.09. Dann müsste F-D1 vor dem Deploy an Gernot gehen. D.3 bräuchte einen Wächter vor `/customers` und müsste in `CommandPalette.tsx` die Einträge `'nav-customers'` und `'action-new-customer'` für die Halle ausblenden. Befund, E-D1 und F-D1 wären dafür neu zu schreiben, und Kunden anlegen müsste auch im Server gesperrt werden. Wählt der Manager Variante b, wird D.3 neu geplant. Dieser Text führt sie nicht aus.
- **E-D8 — Die Rollenlisten der Oberfläche stehen an einer Stelle** (`services/rollen.ts`, neben den Rollentexten der Benutzerverwaltung): `ROLLEN_OHNE_HALLE`, `KAUFMAENNISCHE_ROLLEN`, `KUNDEN_KONDITIONSFELDER`. Eine Node-Prüfung vergleicht alle drei mit `backend/app/core/rollen.py`, damit Server und Oberfläche nicht auseinanderlaufen. Der Rollentext „Produktion“ in der Benutzerverwaltung lautet danach: „… Kunden anlegen und ändern, ohne Konditionen und ohne Löschen. Kein Zugriff auf Rechnungen, DATEV, Preislisten, Auswertungen und Einstellungen.“ Er sagt bewusst nicht „löscht keine Stammdaten“, weil das für Lagerorte nicht gilt (I-D1).
- **E-D9 — Keine Migration und keine Datenänderung in Produktion** (siehe Runbook R-D0).
- **E-D10 — Bewusst nicht enthalten** (Offene Punkte):
  - Abos: Paket 3 hat sie für die Halle offen gelassen, weil sie keine Preise tragen.
  - Stammdaten außerhalb der Kunden: Lagerorte anlegen, ändern und über `is_active` deaktivieren sowie die Growroom-Kapazität (intern I-D1).
  - Das Leergutkonto (`/leergut/kunden`, Pfandart lesbar): Die Halle braucht es für die Rücknahme im Tagesplan (Paket 3, Q6).
  - Eine Umbenennung der Rolle in „Mitarbeiter“ (F-D5).

### Überschneidungen mit D/F/O (Nachtrag 09.10., `/tmp/n0910/plan.md`)

| Datei / Stelle | dieser Abschnitt | D/F/O | Ergebnis |
|---|---|---|---|
| `backend/app/api/v1/sales.py` | D.1 (drei Decorators), D.2 (Import, `_kundenantwort`, `list_customers`, `get_customer`, `create_customer`, `update_customer`, Sonderpreisliste, `create_order`/Kreditlimit) | nicht berührt (nicht unter den 21 Dateien in „File Structure“, per `grep` im Plantext geprüft) | keine Überschneidung |
| `backend/app/core/rollen.py` | D.1 (`KUNDENFELD_AKTIV`, `kundenfeldschutz`), D.2 (`KUNDENANTWORT_KONDITIONEN`, `sieht_konditionen`) | nicht berührt | keine |
| `backend/app/schemas/customer.py` | D.2 (`CustomerResponse`) | nicht berührt (D/F/O ändert nur `schemas/invoice.py`) | keine |
| `backend/tests/test_gernot_261008_paket3.py` | D.2 Step 5: zwei Tests in `TestQ4SonderpreiseDatevKatalogpreis` und `TestQ7Feldschutz` | D/F/O ändert die Datei nicht und misst sie als Umfeld (`467 passed`). O verlässt sich auf `TestAbnahmeSepaBerlin`/`TestAbnahmeRechnungsberechtigung` (Stoppregel 4 dort) | andere Klassen, keine Überschneidung. D/F/O läuft vorher; die Zusage „bleibt unverändert“ gilt für D/F/O, P4-D.2 ändert die Datei danach. Die Zählung bleibt 467, die D/F/O-Abnahmetests laufen in Prozedur V mit (gemessen grün, auch nach D.3) |
| `backend/tests/test_paket4.py` | neu bzw. angehängt | D/F/O nutzt `test_nachtrag_0910.py` | keine |
| `frontend/src/pages/Customers.tsx`, `frontend/src/services/rollen.ts`, `frontend/tests/unit/rollen.check.ts` | D.3 | nicht berührt (D/F/O: `Settings.tsx`, `Invoices.tsx`, `api.ts`, `OrderDocumentsModal.tsx`, `Tagesplan.tsx`, `SepaEinzugsliste.tsx`, neue Dateien) | keine |
| `frontend/src/App.tsx`, `frontend/src/components/common/Layout.tsx`, `frontend/src/components/common/CommandPalette.tsx` | nicht berührt (E-D7 Variante a; die Vorbereitung prüft nur, dass die zwei Palettenpunkte da sind) | nicht berührt (`git diff df84f7b..bd56901` ohne Treffer; D/F/O-Plan: „`Layout.tsx` … nicht geändert“) | keine |
| **Semantisch:** Route `GET /api/v1/invoices/datev-export/einstellungen` | Der Wachhund in D.2 (`TestP4DHalleOhneGeldUndKonditionen`) prüft jede Route unter `/api/v1/invoices` als Halle → 403 | Nachtrag-Task 4 (D.4 DATEV) legt sie im Rechnungsrouter an, Halle 403 (dort getestet) | wird nach dem Merge automatisch mitgeprüft, Routenzahl 53 → 54. Die Schwelle `>= 50` gilt für beide Stände. **Setzt D/F/O nicht voraus.** |
| **Semantisch:** Belegordner (O), Firmendaten (F) | — | Die Halle sieht die Einstellungen nicht (O-E6), die Packliste nutzt den Rückfall-Download | keine Berührung |
| **Prozedur V (Zählung)** | +14 (D.1), +19 (D.2) | nach D/F/O `1709 passed` | auf `df84f7b` gemessen: `1644 → 1658 → 1677`. Auf `bd56901` (D/F/O) gemessen: `1709 → 1742`, falls kein anderer Paket-4-Abschnitt vorher Tests anhängt. Maßgeblich sind die **Namen** |

**Ergebnis:** Kein Step dieses Abschnitts „setzt D/F/O voraus“. Alle Anker liegen in Dateien, die D/F/O nicht ändert.

### Prüfstand (in Kopien, Repo unverändert)

- **Nachspiel-Werkzeug:** `/tmp/p4-drev-tools/nachspiel.sh <Kopie> [Plandatei]` wendet diesen Text Step für Step an (`apply_range.py`: Blöcke „diesen Block … ersetzen durch …“ mit Anker genau einmal, Testblöcke, Node-Prüfung). Nach jedem Step misst es Rot und Grün. Am Ende laufen `tsc`, Build, die `grep`-Zählungen und Prozedur V. Jeder Anker wurde in jeder Kopie genau einmal gefunden: D.1 6 Ersetzungen und 1 Anhang, D.2 15 und 1, D.3 28 Ersetzungen und die Node-Datei.
- **`/tmp/p4-kopie-drev-a`** (frisch aus `git archive df84f7b`, `frontend/node_modules` als Symlink):
  - Vorbereitung: alle `grep`-Zählungen wie angegeben, die 5 Hashes stimmen.
  - **D.1:** `5 failed, 9 passed` → `14 passed`. Umfeld Paket 3 + Rollen `487 passed`.
  - **D.2:** `7 failed, 12 passed`, Meldungen wie angegeben, → `19 passed`. Danach Paket 3 `2 failed, 485 passed` mit genau den beiden Tests aus E-D6, nach Step 5 `487 passed`. D-Klassen gesamt `33 passed`. `ruff exit 0`.
  - **D.3:** Node-Prüfung rot mit den zwei Zeilen aus Step 2, dann `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`. `tsc exit 0`, Build `✓ built`, alle `grep`-Zählungen wie angegeben.
  - **Prozedur V:** `14 failed, 1677 passed, 2 skipped, 1 error`, `comm`-Abgleich leer. Basis auf `df84f7b`: `14 failed, 1644 passed, 2 skipped, 1 error`.
- **`/tmp/p4-kopie-drev-dfo`** (aus `feat/nachtrag-0910` @ `bd56901`, Stand nach D/F/O): Alle Rot/Grün-Zahlen sind identisch, der Wachhund zählt 54 Routen. `test_nachtrag_0910.py` hat `65 passed`. `belegpfad.check`, `dateiname.check` und `rollen.check` sind ok. Prozedur V: `14 failed, 1742 passed, 2 skipped, 1 error`, `comm` leer. Die 8 geänderten Dateien sind byte-gleich mit `/tmp/p4-kopie-drev-a`. `git rev-parse` zeigt: Alle 8 Dateien sowie `App.tsx`, `Layout.tsx` und `CommandPalette.tsx` sind auf `df84f7b` und `bd56901` gleich.
- **`/tmp/p4-kopie-drev-git`** (`df84f7b` mit eigenem Git-Verlauf): Die drei Commit-Befehle aus D.1, D.2 und D.3 liefen wörtlich. D.4 Step 2 zeigt die drei Betreffe, `git diff --stat HEAD~3..HEAD` ohne Pfad zeigt genau die 8 Dateien, und `git status --short` ist danach leer.
- **Erste Prüfung (vor der Überarbeitung, `/tmp/p4-kopie-dpruef`, `/tmp/p4-kopie-dpruef-dfo`):** Die Backend-Dateien von D.1 und D.2 sind byte-gleich geblieben, neu ist nur der Test `test_halle_speichert_das_formular_ohne_konditionen`.
- **Prod-Versionen:** Die Maskierung per `model_copy(update=…)` mit `Optional`-Feldern unter FastAPI 0.109.0 / Pydantic 2.5.3 (Python 3.11, lokaler Docker, `/tmp/p4-d-tools/repro109.py`) liefert `null` in Einzel- und Listenantwort, ohne Maske die Werte.
- **Nicht gemessen:** Oberfläche im Browser (→ Abnahme RF-D1 bis RF-D5), Stand nach dem echten Merge von D/F/O auf `main` (Nachspiel durch den Manager, I-D4).

### Vorbereitung P4-D (vor Task 20)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis-P4-D>` in den Bericht.
- Ausgangsstand P4-D samt der fünf Datei-Hashes: in „Vorbereitung (vor Task 1)“ geprüft. Seither haben Task 3 (`sales.py`) und Task 18 (`rollen.ts`) zwei dieser Dateien an anderen Stellen geändert — erwartet, die Hashes werden hier nicht erneut geprüft. Die Anker von P4-D sind davon unberührt (Anker-Nachspiel, Prüfstand im Kopf). Fehlt beim Step ein Anker inhaltlich: Stoppregel 1.

---

### Task 20 (P4-D.1): Mitarbeiter löschen keine Kundenstammdaten — Adressen, Ansprechpartner, Aktiv-Schalter

**Files:**
- Modify: `backend/app/core/rollen.py` (neue Konstante `KUNDENFELD_AKTIV` vor `_HINWEIS_VERALTET`, Docstring und Rumpf von `kundenfeldschutz`)
- Modify: `backend/app/api/v1/sales.py` (Decorators von `reactivate_customer`, `delete_address`, `delete_contact`)
- Create/Modify: `backend/tests/test_paket4.py` (Kopf, falls die Datei fehlt; Block D.1 anhängen)

**Interfaces:**
- Produces:
  - `DELETE /api/v1/sales/customers/{customer_id}/addresses/{address_id}` und `DELETE …/contacts/{contact_id}`: Ein Login ohne `ROLLEN_OHNE_HALLE` bekommt 403 `{"detail": "Keine Berechtigung für diese Aktion"}` (`require_role`). Alle anderen bekommen wie bisher 204 bzw. 404.
  - `POST /api/v1/sales/customers/{customer_id}/reactivate`: nur `KAUFMAENNISCHE_ROLLEN`, sonst 403 „Keine Berechtigung für diese Aktion“.
  - `PATCH /api/v1/sales/customers/{customer_id}` mit geändertem `aktiv` von einem Login ohne `KAUFMAENNISCHE_ROLLEN`: 403 `"Kunden deaktivieren und reaktivieren nur Verwaltung, Vertrieb und Buchhaltung: Aktiv. Nicht selbst geändert? Dann ist das Formular veraltet – bitte neu laden."`. Es wird nichts geschrieben. Ein unverändertes `aktiv` ist kein Fehler.
  - `app.core.rollen.KUNDENFELD_AKTIV = {"aktiv": "Aktiv"}`.
- Consumes: `_ohne_halle`, `_nur_kaufmaennisch` (`sales.py`), `geaenderte_felder`, `_ablehnen`, `hat_rolle` (`rollen.py`).
- Unverändert: Adressen und Ansprechpartner anlegen und ändern (Halle erlaubt), `delete_customer` (schon kaufmännisch), `KUNDENFELDER_KAUFMAENNISCH`/`KUNDENFELDER_EMPFAENGER`. Der Wachhund `TestQ4KundenfelderEingeordnet` bleibt grün.

**Review Focus (D.1):** Das Formular der Planung schickt `aktiv` unverändert mit, das bleibt 200. Ein Halle-Login mit Zusatzrolle `sales` darf alles: `hat_rolle` prüft „mindestens eine“.

- [ ] **Step 1: Testdatei anlegen (nur falls sie fehlt) und Block D.1 ans Dateiende anhängen.**

```bash
test -f backend/tests/test_paket4.py || printf '"""Paket 4 — neue Tests aller Abschnitte. Jeder Abschnitt hat eigene Präfixe\n(Klassen TestP4A…/TestP4B…/TestP4C…/TestP4D…, Helfer _p4a_…/_p4b_…/_p4c_…/_p4d_…).\nKeine autouse-Fixture; Einzeltests über Klassen-IDs, nie -k."""\n' > backend/tests/test_paket4.py
```

Block (unverändert ans Dateiende; die zwei Leerzeilen am Anfang gehören dazu):

```python


# =============================================================================
# Abschnitt D — Rechte der Rolle Produktion bei Kunden-Stammdaten (G41, B8)
# Präfixe: Klassen TestP4D…, Helfer _p4d_…, Konstanten _P4D_…
# =============================================================================
import pytest

from app.api.deps import get_current_user
from app.main import app

_P4D_USER_ID = "123e4567-e89b-12d3-a456-426614174000"
# Rollen außer der Halle (app.core.rollen.ROLLEN_OHNE_HALLE) bzw. kaufmännisch
# (KAUFMAENNISCHE_ROLLEN) — als eigene Listen, damit ein Test eine geänderte
# Matrix bemerkt.
_P4D_OHNE_HALLE = ["admin", "sales", "accounting", "production_planner"]
_P4D_KAUFMAENNISCH = ["admin", "sales", "accounting"]


def _p4d_als(*rollen):
    """Login mit genau diesen Rollen (Muster tests/test_rollen.py::_als).
    Das client-Fixture setzt das Login beim nächsten Test neu."""
    async def override():
        return {"id": _P4D_USER_ID, "username": "p4d", "email": "p4d@example.com",
                "roles": list(rollen)}
    app.dependency_overrides[get_current_user] = override


def _p4d_verwaltung():
    """Zurück auf das Standard-Login des client-Fixtures (conftest.py)."""
    _p4d_als("admin", "production_planner")


def _p4d_kunde(client, **felder):
    """Kunde, angelegt von der Verwaltung (darf auch Konditionen setzen)."""
    _p4d_verwaltung()
    r = client.post("/api/v1/sales/customers", json={
        "name": "Großer Kern", "typ": "GASTRO", "email": "kueche@grosser-kern.de",
        "liefertage": [1, 3], "confirmation_emails": ["ab@grosser-kern.de"], **felder})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_adresse(client, kunde, **felder):
    _p4d_verwaltung()
    r = client.post(f"/api/v1/sales/customers/{kunde['id']}/addresses", json={
        "address_type": "SHIPPING", "is_default": True, "strasse": "Lieferhof",
        "hausnummer": "3", "plz": "80331", "ort": "München", **felder})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_kontakt(client, kunde):
    _p4d_verwaltung()
    r = client.post(f"/api/v1/sales/customers/{kunde['id']}/contacts",
                    json={"name": "Anna Koch", "email": "anna@grosser-kern.de"})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_kunde_db(kunde_id):
    from uuid import UUID
    from app.models.customer import Customer
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        k = db.get(Customer, UUID(kunde_id))
        return {"aktiv": k.aktiv, "discount_percent": k.discount_percent,
                "payment_terms": k.payment_terms.value, "telefon": k.telefon}


class TestP4DStammdatenLoeschen:
    """G41 (Gernot, 08.10. B8): Mitarbeiter löschen keine Stammdaten. Adressen und
    Ansprechpartner löschen nur Rollen ohne die Halle (wie Sonderpreise, T5 R2);
    Anlegen und Ändern bleiben der Halle erlaubt (Gernot, 03.09.)."""

    def test_halle_loescht_keine_adresse(self, client):
        kunde = _p4d_kunde(client)
        adresse = _p4d_adresse(client, kunde)
        _p4d_als("production_staff")

        r = client.delete(f"/api/v1/sales/customers/{kunde['id']}/addresses/{adresse['id']}")

        assert r.status_code == 403, r.text
        _p4d_verwaltung()
        ids = [a["id"] for a in client.get(f"/api/v1/sales/customers/{kunde['id']}/addresses").json()]
        assert adresse["id"] in ids

    def test_halle_loescht_keinen_ansprechpartner(self, client):
        kunde = _p4d_kunde(client)
        kontakt = _p4d_kontakt(client, kunde)
        _p4d_als("production_staff")

        r = client.delete(f"/api/v1/sales/customers/{kunde['id']}/contacts/{kontakt['id']}")

        assert r.status_code == 403, r.text
        _p4d_verwaltung()
        ids = [c["id"] for c in client.get(f"/api/v1/sales/customers/{kunde['id']}/contacts").json()]
        assert kontakt["id"] in ids

    @pytest.mark.parametrize("rolle", _P4D_OHNE_HALLE)
    def test_rollen_ohne_halle_loeschen_adresse_und_ansprechpartner(self, client, rolle):
        kunde = _p4d_kunde(client)
        adresse = _p4d_adresse(client, kunde)
        kontakt = _p4d_kontakt(client, kunde)
        _p4d_als(rolle)

        assert client.delete(
            f"/api/v1/sales/customers/{kunde['id']}/addresses/{adresse['id']}").status_code == 204
        assert client.delete(
            f"/api/v1/sales/customers/{kunde['id']}/contacts/{kontakt['id']}").status_code == 204

    def test_halle_legt_adresse_und_ansprechpartner_weiter_an_und_aendert_sie(self, client):
        """Gernot, 03.09.: bei Ausfall der Betriebsleitung erfassen die Mitarbeiter."""
        kunde = _p4d_kunde(client)
        _p4d_als("production_staff")

        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/addresses", json={
            "address_type": "SHIPPING", "strasse": "Hof", "plz": "80331", "ort": "München"})
        assert r.status_code == 201, r.text
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}/addresses/{r.json()['id']}",
                         json={"lieferhinweise": "Tor 2"})
        assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/contacts", json={"name": "Ben"})
        assert r.status_code == 201, r.text
        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}/contacts/{r.json()['id']}",
                         json={"telefon": "089 1"})
        assert r.status_code == 200, r.text


class TestP4DKundeAktivSchalter:
    """Deaktivieren ist die weiche Form des Löschens: DELETE /customers deaktiviert
    einen Kunden mit Belegen und ist nur kaufmännisch (Q4-Liste). Derselbe Schritt
    über PATCH aktiv bzw. sein Gegenstück /reactivate folgt derselben Regel."""

    def test_halle_deaktiviert_keinen_kunden(self, client):
        kunde = _p4d_kunde(client)
        _p4d_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False})

        assert r.status_code == 403, r.text
        assert r.json()["detail"].startswith(
            "Kunden deaktivieren und reaktivieren nur Verwaltung, Vertrieb und Buchhaltung: Aktiv.")
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is True

    def test_planung_deaktiviert_keinen_kunden(self, client):
        kunde = _p4d_kunde(client)
        _p4d_als("production_planner")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False})

        assert r.status_code == 403, r.text
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is True

    def test_halle_reaktiviert_keinen_kunden(self, client):
        kunde = _p4d_kunde(client)
        assert client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False}).status_code == 200
        _p4d_als("production_staff")

        assert client.post(f"/api/v1/sales/customers/{kunde['id']}/reactivate").status_code == 403
        assert client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": True}).status_code == 403
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is False

    @pytest.mark.parametrize("rolle", _P4D_KAUFMAENNISCH)
    def test_kaufmaennische_rollen_deaktivieren_und_reaktivieren(self, client, rolle):
        kunde = _p4d_kunde(client)
        _p4d_als(rolle)

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"aktiv": False})
        assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/reactivate")
        assert r.status_code == 200, r.text
        assert _p4d_kunde_db(kunde["id"])["aktiv"] is True

    def test_unveraendertes_aktiv_bleibt_fuer_die_halle_erlaubt(self, client):
        """Ein Formular schickt aktiv immer mit; ohne Änderung ist das kein Deaktivieren."""
        kunde = _p4d_kunde(client)
        _p4d_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                         json={"aktiv": True, "telefon": "089 123"})

        assert r.status_code == 200, r.text
        assert _p4d_kunde_db(kunde["id"])["telefon"] == "089 123"
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4DStammdatenLoeschen tests/test_paket4.py::TestP4DKundeAktivSchalter -q -p no:cacheprovider 2>&1 | tail -8
```

Erwartet: **`5 failed, 9 passed`**.
- Rot:
  - `test_halle_loescht_keine_adresse` (`assert 204 == 403`)
  - `test_halle_loescht_keinen_ansprechpartner` (`assert 204 == 403`)
  - `test_halle_deaktiviert_keinen_kunden` (`assert 200 == 403`, Text = Kundenantwort mit `"aktiv":false`)
  - `test_planung_deaktiviert_keinen_kunden` (`assert 200 == 403`)
  - `test_halle_reaktiviert_keinen_kunden` (`assert 200 == 403` beim `reactivate`)
- Grün bleiben die Wächter:
  - `test_rollen_ohne_halle_loeschen_adresse_und_ansprechpartner[admin|sales|accounting|production_planner]`
  - `test_halle_legt_adresse_und_ansprechpartner_weiter_an_und_aendert_sie`
  - `test_kaufmaennische_rollen_deaktivieren_und_reaktivieren[admin|sales|accounting]`
  - `test_unveraendertes_aktiv_bleibt_fuer_die_halle_erlaubt`

- [ ] **Step 3: Implementierung.**

`backend/app/core/rollen.py`, Konstante vor dem Hinweistext: diesen Block

```python
_HINWEIS_VERALTET = " Nicht selbst geändert? Dann ist das Formular veraltet – bitte neu laden."
```

ersetzen durch

```python
# Aktiv-Schalter des Kunden (P4-D.1; Gernot 08.10. B8: Mitarbeiter löschen
# keine Stammdaten). Deaktivieren ist die weiche Form des Löschens:
# delete_customer (sales.py) deaktiviert einen Kunden mit Belegen und ist nur
# KAUFMAENNISCHE_ROLLEN erlaubt. PATCH aktiv (beide Richtungen) und
# /reactivate folgen derselben Regel. Eigene Liste statt Eintrag in
# KUNDENFELDER_KAUFMAENNISCH: "aktiv" ist keine Kondition und wird nicht
# ausgeblendet.
KUNDENFELD_AKTIV = {"aktiv": "Aktiv"}

_HINWEIS_VERALTET = " Nicht selbst geändert? Dann ist das Formular veraltet – bitte neu laden."
```

`backend/app/core/rollen.py`, Docstring von `kundenfeldschutz`: diesen Block

```python
    - Empfänger (KUNDENFELDER_EMPFAENGER): nur ROLLEN_OHNE_HALLE; bei der
      Neuanlage frei.
```

ersetzen durch

```python
    - Empfänger (KUNDENFELDER_EMPFAENGER): nur ROLLEN_OHNE_HALLE; bei der
      Neuanlage frei.
    - Aktiv-Schalter (KUNDENFELD_AKTIV): nur KAUFMAENNISCHE_ROLLEN (P4-D.1).
```

`backend/app/core/rollen.py`, in `kundenfeldschutz` im kaufmännischen Zweig: diesen Block

```python
            _ablehnen(
                "Abrechnungsrelevante Kundenfelder ändern nur Verwaltung, Vertrieb und Buchhaltung",
                KUNDENFELDER_KAUFMAENNISCH, geaendert, neuanlage=neuanlage,
            )
    if neuanlage or hat_rolle(user, ROLLEN_OHNE_HALLE):
```

ersetzen durch

```python
            _ablehnen(
                "Abrechnungsrelevante Kundenfelder ändern nur Verwaltung, Vertrieb und Buchhaltung",
                KUNDENFELDER_KAUFMAENNISCH, geaendert, neuanlage=neuanlage,
            )
        geaendert = geaenderte_felder(KUNDENFELD_AKTIV, neu, vorher)
        if geaendert and not neuanlage:
            _ablehnen(
                "Kunden deaktivieren und reaktivieren nur Verwaltung, Vertrieb und Buchhaltung",
                KUNDENFELD_AKTIV, geaendert, neuanlage=False,
            )
    if neuanlage or hat_rolle(user, ROLLEN_OHNE_HALLE):
```

`backend/app/api/v1/sales.py`, Decorator von `reactivate_customer`: diesen Block

```python
@router.post("/customers/{customer_id}/reactivate", response_model=CustomerResponse)
```

ersetzen durch

```python
# Gegenstück zum Deaktivieren in delete_customer: dieselben Rollen (P4-D.1).
@router.post("/customers/{customer_id}/reactivate", response_model=CustomerResponse, dependencies=_nur_kaufmaennisch)
```

`backend/app/api/v1/sales.py`, Decorator von `delete_address`: diesen Block

```python
@router.delete("/customers/{customer_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
```

ersetzen durch

```python
# Mitarbeiter löschen keine Stammdaten (Gernot, 08.10. B8; P4-D.1):
# Löschen nur ohne die Halle, Anlegen und Ändern bleiben offen (Gernot, 03.09.).
@router.delete("/customers/{customer_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=_ohne_halle)
```

`backend/app/api/v1/sales.py`, Decorator von `delete_contact`: diesen Block

```python
@router.delete("/customers/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
```

ersetzen durch

```python
# Wie delete_address: Löschen nur ohne die Halle (P4-D.1).
@router.delete("/customers/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=_ohne_halle)
```

- [ ] **Step 4: Grün und Umfeld.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4DStammdatenLoeschen tests/test_paket4.py::TestP4DKundeAktivSchalter -q -p no:cacheprovider 2>&1 | tail -1
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py tests/test_rollen.py -q -p no:cacheprovider 2>&1 | tail -1
grep -c 'dependencies=_ohne_halle' backend/app/api/v1/sales.py        # 5
grep -c 'dependencies=_nur_kaufmaennisch' backend/app/api/v1/sales.py # 3
grep -c 'KUNDENFELD_AKTIV' backend/app/core/rollen.py                  # 4
```

Erwartet: `14 passed`, dann `487 passed`. Die `grep`-Zählungen wie im Kommentar.

- [ ] **Step 5: Commit.**

```bash
git add backend/app/core/rollen.py backend/app/api/v1/sales.py backend/tests/test_paket4.py
git commit -m "feat(rechte): Mitarbeiter löschen keine Kundenstammdaten — Adressen, Ansprechpartner, Aktiv-Schalter (P4-D.1)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 21 (P4-D.2): Konditionen für die Halle ausgeblendet — Kundenantworten, Sonderpreisliste, Kreditlimit-Meldung; Wachhund Geld/DATEV/Konditionen

**Files:**
- Modify: `backend/app/schemas/customer.py` (`CustomerResponse`: Konditionsfelder `Optional`)
- Modify: `backend/app/core/rollen.py` (`KUNDENANTWORT_KONDITIONEN` vor `_HINWEIS_VERALTET`, `sieht_konditionen` nach `hat_rolle`)
- Modify: `backend/app/api/v1/sales.py`: Import aus `app.core.rollen`, neue Funktion `_kundenantwort` nach `_ohne_halle`, `list_customers`, `get_customer`, `create_customer` (nur Kommentar), `update_customer`, Decorator von `list_customer_prices`, `create_order` (Kreditlimit)
- Modify: `backend/tests/test_gernot_261008_paket3.py` (genau zwei Tests und ein Klassen-Docstring, Step 5, E-D6)
- Modify: `backend/tests/test_paket4.py` (Block D.2 anhängen)

**Interfaces:**
- Produces:
  - `app.core.rollen.KUNDENANTWORT_KONDITIONEN` (Tupel aus 15 Feldnamen) und `sieht_konditionen(user) -> bool` (= `hat_rolle(user, ROLLEN_OHNE_HALLE)`).
  - `app.api.v1.sales._kundenantwort(customer, user) -> CustomerResponse`.
  - `GET /api/v1/sales/customers`, `GET /api/v1/sales/customers/{id}` und die Antwort auf `PATCH /api/v1/sales/customers/{id}`: Ein Login ohne `ROLLEN_OHNE_HALLE` bekommt alle 15 Felder als `null`. Alle anderen Felder kommen unverändert (Name, Nummer, E-Mail, Empfängerlisten, Liefertage, Aktiv, Adresse …).
  - `POST /api/v1/sales/customers`: Die Antwort bleibt unverändert (E-D3).
  - Vertrag für das Kundenformular der Halle (D.3): Ein `PATCH` mit den Formularfeldern ohne Konditionen gibt 200 und lässt die Konditionen stehen. Mit den Formularvorgaben `NET_14`/`0` statt der ausgeblendeten Werte kommt 403.
  - `CustomerResponse`: Die Konditionsfelder sind `Optional`, in OpenAPI also nullable. Der Frontend-Typ `Customer` hat sie schon optional, eine Änderung an `types/index.ts` ist nicht nötig.
  - `GET /api/v1/sales/customers/{id}/prices`: nur `ROLLEN_OHNE_HALLE`, sonst 403 „Keine Berechtigung für diese Aktion“.
  - `POST /api/v1/sales/orders`, Kreditlimit überschritten, für ein Login ohne `ROLLEN_OHNE_HALLE`: 400 `"Kreditlimit des Kunden überschritten. Bitte Verwaltung, Vertrieb oder Buchhaltung fragen."`. Für alle anderen kommt die Meldung wie bisher mit Beträgen.
- Consumes: `hat_rolle`, `ROLLEN_OHNE_HALLE`, `KUNDENFELDER_KAUFMAENNISCH` (`rollen.py`), Helfer aus Block D.1 (`_p4d_als`, `_p4d_verwaltung`, `_p4d_kunde`, `_p4d_adresse`, `_p4d_kunde_db`).
- Unverändert: `GET …/effective-price/{product_id}` (Bestellformular), `OrderResponse`, Belegkette, Leergut, `kundenfeldschutz` (vergleicht weiter mit den gespeicherten Werten).

**Review Focus (D.2):**
- Nachdem die Halle einen Kunden ändert, sind die Konditionen in der Datenbank unverändert. Die Tests prüfen Rabatt und Zahlungsziel, einmal mit einem Einzelfeld, einmal mit dem vollständigen Formular ohne Konditionen (`test_halle_speichert_das_formular_ohne_konditionen`, der Server-Vertrag für D.3).
- Eine Halle mit Zusatzrolle sieht alles.
- Der Wachhund zählt mindestens 50 geprüfte Routen×Methoden. Gemessen 53, nach D/F/O 54; im Gesamtplan 55 (mit `GET /api/v1/belegstatus` aus C.3, in der Zusammenführung zu `_PRAEFIXE` ergänzt).

- [ ] **Step 1: Block D.2 ans Dateiende von `backend/tests/test_paket4.py` anhängen** (unverändert, mit den zwei Leerzeilen am Anfang):

```python


from decimal import Decimal

# Konditionen eines Kunden in Antworten (app.core.rollen.KUNDENANTWORT_KONDITIONEN):
# die Felder aus KUNDENFELDER_KAUFMAENNISCH plus die nur lesbaren Ableitungen.
_P4D_KONDITIONSFELDER = {
    "payment_terms", "credit_limit", "price_list_id", "discount_percent", "skonto_percent",
    "skonto_days", "packaging_fee_amount", "packaging_fee_percent", "datev_account",
    "pfand_abrechnung", "invoice_mode",
    "price_list_name", "payment_days", "pfand_monatlich_ab", "zahlungsart",
}


def _p4d_preisliste():
    from app.models.product import PriceList
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        liste = PriceList(name="Gastro 2026", code="GASTRO26")
        db.add(liste)
        db.commit()
        return str(liste.id)


def _p4d_kunde_mit_konditionen(client, **felder):
    konditionen = {
        "payment_terms": "NET_30", "discount_percent": "5", "skonto_percent": "2",
        "skonto_days": 10, "credit_limit": "5000", "packaging_fee_amount": "4.5",
        "packaging_fee_percent": "1", "datev_account": "10077",
        "pfand_abrechnung": "MONATLICH", "invoice_mode": "MONATLICH",
        "price_list_id": _p4d_preisliste(),
    }
    return _p4d_kunde(client, **{**konditionen, **felder})


def _p4d_produkt(client, sku="KRESSE-50", preis="2.50"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    from tests.conftest import TestingSessionLocal
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code="STK").first()
        if unit is None:
            unit = UnitOfMeasure(code="STK", name="Stück", symbol="Stk",
                                 category=UnitCategory.COUNT, is_base_unit=True)
            db.add(unit)
            db.commit()
        unit_id = str(unit.id)
    _p4d_verwaltung()
    r = client.post("/api/v1/products", json={
        "sku": sku, "name": "Kresse 50 g", "base_price": preis,
        "category": "MICROGREEN", "base_unit_id": unit_id})
    assert r.status_code == 201, r.text
    return r.json()


def _p4d_bestellung(client, kunde, produkt, preis="2.50"):
    from datetime import date, timedelta
    return client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": (date.today() + timedelta(days=3)).isoformat(),
        "lines": [{"product_id": produkt["id"], "product_name": produkt["name"],
                   "quantity": 3, "unit": "STK", "unit_price": preis}],
    })


class TestP4DKonditionenAusgeblendet:
    """Gernot, 09.10. („Rolle Produktion ohne Rechnungen/Konditionen“: „Danke!“):
    Kundenantworten an die Halle tragen keine Konditionen — weder Liste noch
    Detail noch die Antwort auf eine Änderung. Reaktivieren darf sie nicht (P4-D.1)."""

    def test_konditionsliste_deckt_den_feldschutz_ab(self):
        from app.core.rollen import KUNDENANTWORT_KONDITIONEN, KUNDENFELDER_KAUFMAENNISCH
        assert set(KUNDENFELDER_KAUFMAENNISCH) <= set(KUNDENANTWORT_KONDITIONEN)
        assert set(KUNDENANTWORT_KONDITIONEN) == _P4D_KONDITIONSFELDER

    def test_halle_sieht_in_liste_und_detail_keine_konditionen(self, client):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff")

        liste = client.get("/api/v1/sales/customers", params={"search": "Großer Kern"})
        detail = client.get(f"/api/v1/sales/customers/{kunde['id']}")

        assert liste.status_code == 200, liste.text
        assert detail.status_code == 200, detail.text
        for antwort in (liste.json()["items"][0], detail.json()):
            assert {f: antwort[f] for f in _P4D_KONDITIONSFELDER} == dict.fromkeys(_P4D_KONDITIONSFELDER)
            # Was die Halle für Bestellung und Belegversand braucht, bleibt.
            assert antwort["id"] == kunde["id"]
            assert antwort["name"] == "Großer Kern"
            assert antwort["customer_number"] == kunde["customer_number"]
            assert antwort["email"] == "kueche@grosser-kern.de"
            assert antwort["confirmation_emails"] == ["ab@grosser-kern.de"]
            assert antwort["liefertage"] == [1, 3]
            assert antwort["aktiv"] is True

    def test_halle_bekommt_beim_speichern_keine_konditionen_zurueck(self, client):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff")

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json={"telefon": "089 777"})

        assert r.status_code == 200, r.text
        assert {f: r.json()[f] for f in _P4D_KONDITIONSFELDER} == dict.fromkeys(_P4D_KONDITIONSFELDER)
        gespeichert = _p4d_kunde_db(kunde["id"])
        assert gespeichert["telefon"] == "089 777"
        assert str(gespeichert["discount_percent"]) == "5.00"
        assert gespeichert["payment_terms"] == "NET_30"

    def test_halle_neuanlage_zeigt_nur_standardkonditionen_danach_keine(self, client):
        """Die Halle legt nur mit Standardkonditionen an (Paket 3, kundenfeldschutz);
        die Antwort darauf verrät nichts und bleibt wie bisher (Paket-3-Test
        test_halle_legt_kunden_mit_standardkonditionen_an). Danach liest sie den
        Kunden ohne Konditionen."""
        _p4d_als("production_staff")

        r = client.post("/api/v1/sales/customers", json={"name": "Fruchthof Nagel", "typ": "HANDEL"})

        assert r.status_code == 201, r.text
        k = r.json()
        assert (k["payment_terms"], k["discount_percent"], k["pfand_abrechnung"], k["invoice_mode"],
                k["credit_limit"], k["price_list_id"]) == ("NET_14", "0.00", "JE_LIEFERUNG", "EINZELN", None, None)
        detail = client.get(f"/api/v1/sales/customers/{k['id']}").json()
        assert {f: detail[f] for f in _P4D_KONDITIONSFELDER} == dict.fromkeys(_P4D_KONDITIONSFELDER)

    @pytest.mark.parametrize("rolle", _P4D_OHNE_HALLE)
    def test_rollen_ohne_halle_sehen_die_konditionen(self, client, rolle):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als(rolle)

        k = client.get(f"/api/v1/sales/customers/{kunde['id']}").json()

        assert (k["payment_terms"], k["discount_percent"], k["credit_limit"], k["datev_account"]) == (
            "NET_30", "5.00", "5000.00", "10077")
        assert (k["payment_days"], k["pfand_abrechnung"], k["invoice_mode"]) == (30, "MONATLICH", "MONATLICH")
        assert k["price_list_id"] == kunde["price_list_id"] is not None
        assert k["pfand_monatlich_ab"] is not None

    def test_halle_mit_zusaetzlicher_vertriebsrolle_sieht_die_konditionen(self, client):
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff", "sales")

        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["discount_percent"] == "5.00"

    def test_halle_speichert_das_formular_ohne_konditionen(self, client):
        """Kundenformular der Halle (P4-D.3, Customers.tsx mit ohneKonditionen):
        dieselben Felder wie das Formular, ohne Konditionen — gespeichert wird,
        die Konditionen bleiben. Schickt ein Client stattdessen die Vorgaben des
        Formulars (aus null wird NET_14 und 0), lehnt der Server ab (E-D3)."""
        kunde = _p4d_kunde_mit_konditionen(client)
        _p4d_als("production_staff")
        k = client.get(f"/api/v1/sales/customers/{kunde['id']}").json()
        formular = {
            "name": k["name"], "typ": k["typ"], "customer_number": k["customer_number"] or "",
            "email": k["email"] or "", "telefon": "089 555", "adresse": k["adresse"] or "",
            "ust_id": k["ust_id"] or "", "liefertage": k["liefertage"],
            "show_prices_on_delivery_note": k["show_prices_on_delivery_note"],
            "confirmation_emails": k["confirmation_emails"],
            "delivery_note_emails": k["delivery_note_emails"],
            "invoice_emails": k["invoice_emails"], "aktiv": k["aktiv"],
        }

        r = client.patch(f"/api/v1/sales/customers/{kunde['id']}", json=formular)

        assert r.status_code == 200, r.text
        gespeichert = _p4d_kunde_db(kunde["id"])
        assert (gespeichert["telefon"], gespeichert["payment_terms"], str(gespeichert["discount_percent"])) == (
            "089 555", "NET_30", "5.00")
        vorgaben = client.patch(f"/api/v1/sales/customers/{kunde['id']}",
                                json={**formular, "payment_terms": "NET_14", "discount_percent": 0})
        assert vorgaben.status_code == 403, vorgaben.text


class TestP4DSonderpreiseUndBestellung:
    """Sonderpreise sind Konditionen: die Liste je Kunde liest die Halle nicht mehr.
    Den einen gültigen Preis je Produkt für das Bestellformular liest sie weiter
    (Paket 3, test_halle_liest_sonderpreis_fuers_bestellformular) — Bestellungen
    und AB tragen Preise (Gernot, 08.10. B8)."""

    def _sonderpreis(self, client, kunde, produkt):
        _p4d_verwaltung()
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices",
                        json={"product_id": produkt["id"], "unit_price": "1.99"})
        assert r.status_code == 201, r.text

    def test_halle_liest_keine_sonderpreisliste(self, client):
        kunde = _p4d_kunde(client)
        produkt = _p4d_produkt(client)
        self._sonderpreis(client, kunde, produkt)
        _p4d_als("production_staff")

        r = client.get(f"/api/v1/sales/customers/{kunde['id']}/prices")

        assert r.status_code == 403, r.text
        r = client.get(f"/api/v1/sales/customers/{kunde['id']}/effective-price/{produkt['id']}")
        assert r.status_code == 200, r.text
        assert Decimal(r.json()["unit_price"]) == Decimal("1.99")

    @pytest.mark.parametrize("rolle", _P4D_OHNE_HALLE)
    def test_rollen_ohne_halle_lesen_die_sonderpreisliste(self, client, rolle):
        kunde = _p4d_kunde(client)
        produkt = _p4d_produkt(client)
        self._sonderpreis(client, kunde, produkt)
        _p4d_als(rolle)

        r = client.get(f"/api/v1/sales/customers/{kunde['id']}/prices")

        assert r.status_code == 200, r.text
        assert [Decimal(p["unit_price"]) for p in r.json()] == [Decimal("1.99")]

    def test_halle_legt_bestellung_mit_lieferadresse_an(self, client):
        """Ablauf des Bestellformulars (CreateOrderModal): Kundenliste, gültiger
        Preis, Speichern. Die Lieferadresse setzt der Server aus dem Kundenstamm."""
        kunde = _p4d_kunde_mit_konditionen(client, credit_limit=None)
        _p4d_adresse(client, kunde)
        produkt = _p4d_produkt(client)
        _p4d_als("production_staff")

        ids = [k["id"] for k in client.get("/api/v1/sales/customers").json()["items"]]
        preis = client.get(f"/api/v1/sales/customers/{kunde['id']}/effective-price/{produkt['id']}")
        r = _p4d_bestellung(client, kunde, produkt, preis.json()["unit_price"])

        assert kunde["id"] in ids
        assert r.status_code == 201, r.text
        assert r.json()["delivery_address"]["strasse"] == "Lieferhof"
        assert r.json()["customer_name"] == "Großer Kern"

    def test_kreditlimit_meldung_ohne_betraege_fuer_die_halle(self, client):
        kunde = _p4d_kunde(client, credit_limit="1")
        produkt = _p4d_produkt(client)
        _p4d_als("production_staff")

        r = _p4d_bestellung(client, kunde, produkt)

        assert r.status_code == 400, r.text
        assert r.json()["detail"] == (
            "Kreditlimit des Kunden überschritten. Bitte Verwaltung, Vertrieb oder Buchhaltung fragen.")
        _p4d_verwaltung()
        r = _p4d_bestellung(client, kunde, produkt)
        assert r.status_code == 400, r.text
        assert r.json()["detail"].startswith("Kreditlimit überschritten: Limit 1.00 EUR")


class TestP4DHalleOhneGeldUndKonditionen:
    """Wachhund (G41: kein Rechnungswesen, kein DATEV; G60: keine Konditionen):
    jede Route der Geldseite und jede Konditionsroute antwortet der Halle mit 403
    — auch Routen, die später dazukommen (z. B. GET /invoices/datev-export/einstellungen
    aus dem Nachtrag 09.10.)."""

    # /api/v1/belegstatus: Belegstatus aus Paket 4, C.3 (_deps_geld wie /invoices)
    _PRAEFIXE = ("/api/v1/invoices", "/api/v1/price-lists", "/api/v1/sepa", "/api/v1/analytics", "/api/v1/belegstatus")
    _EINZELN = {
        "/api/v1/sales/customers/export/datev",
        "/api/v1/sales/customers/{customer_id}/prices",
        "/api/v1/sales/customer-prices/{price_id}",
        "/api/v1/products/{product_id}/price",
    }

    def test_jede_geld_und_konditionsroute_sperrt_die_halle(self, client):
        import re
        from fastapi.routing import APIRoute
        _p4d_als("production_staff")
        geprueft, offen = [], []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if not (route.path.startswith(self._PRAEFIXE) or route.path in self._EINZELN):
                continue
            pfad = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-0000000000ff", route.path)
            for methode in sorted(route.methods - {"HEAD", "OPTIONS"}):
                geprueft.append(f"{methode} {route.path}")
                code = client.request(methode, pfad, json={}).status_code
                if code != 403:
                    offen.append(f"{methode} {route.path} -> {code}")

        assert offen == []
        assert len(geprueft) >= 50, geprueft

    def test_produktdetail_zeigt_der_halle_keine_preislistenpositionen(self, client):
        produkt = _p4d_produkt(client)
        _p4d_als("production_staff")

        r = client.get(f"/api/v1/products/{produkt['id']}")

        assert r.status_code == 200, r.text
        assert r.json()["prices"] is None
```

- [ ] **Step 2: Rot.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4DKonditionenAusgeblendet tests/test_paket4.py::TestP4DSonderpreiseUndBestellung tests/test_paket4.py::TestP4DHalleOhneGeldUndKonditionen -q -p no:cacheprovider 2>&1 | tail -9
```

Erwartet: **`7 failed, 12 passed`**.
- Rot:
  - `test_konditionsliste_deckt_den_feldschutz_ab` (`ImportError: cannot import name 'KUNDENANTWORT_KONDITIONEN'`)
  - `test_halle_sieht_in_liste_und_detail_keine_konditionen`, `test_halle_bekommt_beim_speichern_keine_konditionen_zurueck` und `test_halle_neuanlage_zeigt_nur_standardkonditionen_danach_keine`: je `assert {'credit_limi…', …} == {'credit_limi…': None, …}`. Beim dritten scheitert erst der Abruf nach der Neuanlage, die Antwort der Neuanlage selbst ist schon heute richtig.
  - `test_halle_liest_keine_sonderpreisliste` (`assert 200 == 403`)
  - `test_kreditlimit_meldung_ohne_betraege_fuer_die_halle` (Diff: `- Kreditlimit des Kunden überschritten. Bitte Verwaltung, Vertrieb oder Buchhaltung fragen.` / `+ Kreditlimit überschritten: Limit 1.00 EUR, offene Bestellungen 0.00 EUR, neue Bestellung ~8.02 EUR`)
  - `test_jede_geld_und_konditionsroute_sperrt_die_halle` (`assert ['GET /api/v1/sales/customers/{customer_id}/prices -> 404'] == []`)
- Grün bleiben die Wächter:
  - `test_rollen_ohne_halle_sehen_die_konditionen[4 Rollen]`
  - `test_halle_mit_zusaetzlicher_vertriebsrolle_sieht_die_konditionen`
  - `test_halle_speichert_das_formular_ohne_konditionen` (Vertrag für das Formular aus P4-D.3; schon heute grün, muss nach der Maskierung grün bleiben)
  - `test_rollen_ohne_halle_lesen_die_sonderpreisliste[4 Rollen]`
  - `test_halle_legt_bestellung_mit_lieferadresse_an`
  - `test_produktdetail_zeigt_der_halle_keine_preislistenpositionen`

- [ ] **Step 3: Implementierung.**

`backend/app/schemas/customer.py`, in `CustomerResponse`: diesen Block

```python
    payment_terms: PaymentTerms
    credit_limit: Optional[Decimal]
    price_list_id: Optional[UUID]
    discount_percent: Decimal
    skonto_percent: Decimal = Decimal("0")
    skonto_days: int = 0
    packaging_fee_amount: Decimal = Decimal("0")
    packaging_fee_percent: Decimal = Decimal("0")
    show_prices_on_delivery_note: bool = False
    pfand_abrechnung: PfandAbrechnung = PfandAbrechnung.JE_LIEFERUNG
    # Stichtag des Leergutkontos (nur bei MONATLICH, vom Server gesetzt)
    pfand_monatlich_ab: Optional[date] = None
    invoice_mode: InvoiceMode = InvoiceMode.EINZELN
```

ersetzen durch

```python
    # Konditionen: Logins ohne ROLLEN_OHNE_HALLE (die Halle) bekommen sie als
    # null (app.core.rollen.KUNDENANTWORT_KONDITIONEN, sales._kundenantwort;
    # P4-D.2). Deshalb Optional, auch wo der Kundenstamm immer einen Wert hat.
    payment_terms: Optional[PaymentTerms]
    credit_limit: Optional[Decimal]
    price_list_id: Optional[UUID]
    discount_percent: Optional[Decimal]
    skonto_percent: Optional[Decimal] = Decimal("0")
    skonto_days: Optional[int] = 0
    packaging_fee_amount: Optional[Decimal] = Decimal("0")
    packaging_fee_percent: Optional[Decimal] = Decimal("0")
    show_prices_on_delivery_note: bool = False
    pfand_abrechnung: Optional[PfandAbrechnung] = PfandAbrechnung.JE_LIEFERUNG
    # Stichtag des Leergutkontos (nur bei MONATLICH, vom Server gesetzt)
    pfand_monatlich_ab: Optional[date] = None
    invoice_mode: Optional[InvoiceMode] = InvoiceMode.EINZELN
```

`backend/app/core/rollen.py`, Konstante vor dem Hinweistext. Nach D.1 steht dort `KUNDENFELD_AKTIV` darüber, der Anker ist trotzdem eindeutig: diesen Block

```python
_HINWEIS_VERALTET = " Nicht selbst geändert? Dann ist das Formular veraltet – bitte neu laden."
```

ersetzen durch

```python
# Konditionen in Kundenantworten (P4-D.2; Gernot 09.10. zu „Rolle Produktion
# ohne Rechnungen/Konditionen“: „Danke!“). Logins ohne ROLLEN_OHNE_HALLE
# bekommen sie als null: alle Felder aus KUNDENFELDER_KAUFMAENNISCH (ein neues
# Feld dort ist damit auch ausgeblendet) und die nur lesbaren Ableitungen.
KUNDENANTWORT_KONDITIONEN = (
    *KUNDENFELDER_KAUFMAENNISCH,
    "price_list_name",     # Name der Preisliste
    "payment_days",        # Zahlungsziel in Tagen (aus payment_terms)
    "pfand_monatlich_ab",  # Stichtag des Leergutkontos
    "zahlungsart",         # Überweisung oder Lastschrift (B10)
)

_HINWEIS_VERALTET = " Nicht selbst geändert? Dann ist das Formular veraltet – bitte neu laden."
```

`backend/app/core/rollen.py`, nach `hat_rolle`: diesen Block

```python
def hat_rolle(user: dict, rollen: Iterable[str]) -> bool:
    """True, wenn das Login mindestens eine der Rollen hat."""
    return bool(set(user.get("roles", [])) & set(rollen))
```

ersetzen durch

```python
def hat_rolle(user: dict, rollen: Iterable[str]) -> bool:
    """True, wenn das Login mindestens eine der Rollen hat."""
    return bool(set(user.get("roles", [])) & set(rollen))


def sieht_konditionen(user: dict) -> bool:
    """Sieht das Login die Konditionen eines Kunden? Alle außer der Halle (P4-D.2)."""
    return hat_rolle(user, ROLLEN_OHNE_HALLE)
```

`backend/app/api/v1/sales.py`, Import: diesen Block

```python
from app.core.rollen import KAUFMAENNISCHE_ROLLEN, ROLLEN_OHNE_HALLE, kundenfeldschutz, standardwerte
```

ersetzen durch

```python
from app.core.rollen import (
    KAUFMAENNISCHE_ROLLEN, KUNDENANTWORT_KONDITIONEN, ROLLEN_OHNE_HALLE,
    kundenfeldschutz, sieht_konditionen, standardwerte,
)
```

`backend/app/api/v1/sales.py`, nach den Rechte-Listen am Modulkopf: diesen Block

```python
_ohne_halle = [Depends(require_role(ROLLEN_OHNE_HALLE))]
```

ersetzen durch

```python
_ohne_halle = [Depends(require_role(ROLLEN_OHNE_HALLE))]


def _kundenantwort(customer: Customer, user: dict) -> CustomerResponse:
    """Kundenantwort; an die Halle ohne Konditionen (P4-D.2).

    Gernot, 09.10.: Rolle „Produktion“ ohne Rechnungen und Konditionen. Die Halle
    liest Kunden weiter für Bestellformular und Belegversand (Name, Nummer,
    E-Mail-Empfänger, Liefertage), die Konditionen kommen als null.
    """
    antwort = CustomerResponse.model_validate(customer)
    if sieht_konditionen(user):
        return antwort
    return antwort.model_copy(update=dict.fromkeys(KUNDENANTWORT_KONDITIONEN))
```

`backend/app/api/v1/sales.py`, Signatur von `list_customers`: diesen Block

```python
async def list_customers(
    db: DBSession,
    pagination: Pagination,
```

ersetzen durch

```python
async def list_customers(
    db: DBSession,
    pagination: Pagination,
    user: CurrentUser,
```

`backend/app/api/v1/sales.py`, Antwort von `list_customers`: diesen Block

```python
        items=[CustomerResponse.model_validate(c) for c in customers],
```

ersetzen durch

```python
        items=[_kundenantwort(c, user) for c in customers],
```

`backend/app/api/v1/sales.py`, `get_customer`: diesen Block

```python
async def get_customer(customer_id: UUID, db: DBSession):
    """Einzelnen Kunden abrufen."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kunde nicht gefunden"
        )
    return CustomerResponse.model_validate(customer)
```

ersetzen durch

```python
async def get_customer(customer_id: UUID, db: DBSession, user: CurrentUser):
    """Einzelnen Kunden abrufen."""
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kunde nicht gefunden"
        )
    return _kundenantwort(customer, user)
```

`backend/app/api/v1/sales.py`, Ende von `create_customer` (nur Kommentar, die Antwort bleibt): diesen Block

```python
    customer = Customer(**data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)
```

ersetzen durch

```python
    customer = Customer(**data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    # Auch an die Halle mit Konditionen: sie legt nur mit Standardkonditionen an
    # (kundenfeldschutz oben), die Antwort verrät also nichts (P4-D.2). Liste,
    # Detail und Änderung blenden sie aus (_kundenantwort).
    return CustomerResponse.model_validate(customer)
```

`backend/app/api/v1/sales.py`, Ende von `update_customer`: diesen Block

```python
    kundenfeldschutz(user, update_data, {f: getattr(customer, f, None) for f in update_data})
    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return CustomerResponse.model_validate(customer)
```

ersetzen durch

```python
    kundenfeldschutz(user, update_data, {f: getattr(customer, f, None) for f in update_data})
    for field, value in update_data.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return _kundenantwort(customer, user)
```

`backend/app/api/v1/sales.py`, Decorator von `list_customer_prices`: diesen Block

```python
@router.get("/customers/{customer_id}/prices", response_model=list[CustomerPriceResponse])
```

ersetzen durch

```python
# Sonderpreise sind Konditionen: die Liste liest die Halle nicht (P4-D.2). Den
# gültigen Preis je Produkt fürs Bestellformular liefert get_effective_price.
@router.get("/customers/{customer_id}/prices", response_model=list[CustomerPriceResponse], dependencies=_ohne_halle)
```

`backend/app/api/v1/sales.py`, in `create_order` die Kreditlimit-Prüfung. Die bisherige Meldung mit Beträgen bleibt darunter unverändert: diesen Block

```python
        if open_order_total + estimated_total > customer.credit_limit:
            raise HTTPException(
```

ersetzen durch

```python
        if open_order_total + estimated_total > customer.credit_limit:
            # Das Limit ist eine Kondition: die Halle erfährt, dass es
            # überschritten ist, aber keine Beträge (P4-D.2).
            if not sieht_konditionen(user):
                raise HTTPException(
                    status_code=400,
                    detail="Kreditlimit des Kunden überschritten. Bitte Verwaltung, Vertrieb oder Buchhaltung fragen.",
                )
            raise HTTPException(
```

- [ ] **Step 4: Grün (neu) und erwartetes Rot im Paket-3-Umfeld.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4DKonditionenAusgeblendet tests/test_paket4.py::TestP4DSonderpreiseUndBestellung tests/test_paket4.py::TestP4DHalleOhneGeldUndKonditionen -q -p no:cacheprovider 2>&1 | tail -1
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py tests/test_rollen.py -q -p no:cacheprovider 2>&1 | grep -E "^FAILED|passed|failed"
```

Erwartet:
- zuerst `19 passed`;
- dann genau **`2 failed, 485 passed`**:
  - `FAILED tests/test_gernot_261008_paket3.py::TestQ4SonderpreiseDatevKatalogpreis::test_halle_liest_sonderpreis_fuers_bestellformular` mit `{"detail":"Keine Berechtigung für diese Aktion"}` / `assert 403 == 200`
  - `FAILED tests/test_gernot_261008_paket3.py::TestQ7Feldschutz::test_halle_aendert_die_abrechnungsart_nicht` mit `assert None == 'EINZELN'`

Das ist der in E-D6 beschriebene Altbestand. Jeder andere rote Test greift Stoppregel 2.

- [ ] **Step 5: Die zwei Paket-3-Tests anpassen (E-D6, nur diese Blöcke).**

`backend/tests/test_gernot_261008_paket3.py`, Docstring der Klasse `TestQ4SonderpreiseDatevKatalogpreis`: diesen Block

```python
    """T5 R2, soweit Gernots Entscheidung vom 03.09. (Kunden und Bestellungen
    erfassen) unberührt bleibt: Sonderpreise pflegen alle außer der Halle, den
    DATEV-Debitorenexport ziehen nur Verwaltung, Vertrieb und Buchhaltung.
    Lesen der Sonderpreise bleibt offen (Bestellformular)."""
```

ersetzen durch

```python
    """T5 R2, soweit Gernots Entscheidung vom 03.09. (Kunden und Bestellungen
    erfassen) unberührt bleibt: Sonderpreise pflegen alle außer der Halle, den
    DATEV-Debitorenexport ziehen nur Verwaltung, Vertrieb und Buchhaltung.
    Den gültigen Preis je Produkt liest die Halle fürs Bestellformular; die
    Sonderpreisliste des Kunden seit P4-D.2 nicht mehr (Konditionen, Gernot 09.10.)."""
```

`backend/tests/test_gernot_261008_paket3.py`, in `test_halle_liest_sonderpreis_fuers_bestellformular`: diesen Block. Die Zeile `assert liste.status_code == 200, liste.text` steht zweimal in der Datei, der Zweizeiler nur einmal.

```python
        assert liste.status_code == 200, liste.text
        assert wirksam.status_code == 200, wirksam.text
```

ersetzen durch

```python
        assert liste.status_code == 403, liste.text  # seit P4-D.2 (vorher 200)
        assert wirksam.status_code == 200, wirksam.text
```

`backend/tests/test_gernot_261008_paket3.py`, in `TestQ7Feldschutz.test_halle_aendert_die_abrechnungsart_nicht`: diesen Block

```python
        assert geaendert.status_code == 403, geaendert.text
        assert formular.status_code == 200, formular.text
        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["invoice_mode"] == "EINZELN"
```

ersetzen durch

```python
        assert geaendert.status_code == 403, geaendert.text
        assert formular.status_code == 200, formular.text
        # Seit P4-D.2 liest die Halle invoice_mode nicht mehr (null): Kontrolle als Verwaltung.
        _q7_rolle(["admin"])
        assert client.get(f"/api/v1/sales/customers/{kunde['id']}").json()["invoice_mode"] == "EINZELN"
```

- [ ] **Step 6: Grün, Umfeld, statische Prüfung.**

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py tests/test_rollen.py -q -p no:cacheprovider 2>&1 | tail -1
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_paket4.py::TestP4DStammdatenLoeschen tests/test_paket4.py::TestP4DKundeAktivSchalter tests/test_paket4.py::TestP4DKonditionenAusgeblendet tests/test_paket4.py::TestP4DSonderpreiseUndBestellung tests/test_paket4.py::TestP4DHalleOhneGeldUndKonditionen -q -p no:cacheprovider 2>&1 | tail -1
cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/sales.py app/core/rollen.py app/schemas/customer.py; echo "ruff exit $?"
grep -c '_kundenantwort(' backend/app/api/v1/sales.py                # 4
grep -c 'CustomerResponse.model_validate(' backend/app/api/v1/sales.py # 3
grep -c 'dependencies=_ohne_halle' backend/app/api/v1/sales.py         # 6
grep -c 'sieht_konditionen(user)' backend/app/api/v1/sales.py          # 2
```

Erwartet:
- `487 passed`
- `33 passed`
- keine `ruff`-Ausgabe und `ruff exit 0`; fehlt `ruff` unter `/opt/homebrew/bin`: „nicht ausführbar“ melden, nicht ersetzen
- die `grep`-Zählungen wie im Kommentar

- [ ] **Step 7: Commit.**

```bash
git add backend/app/schemas/customer.py backend/app/core/rollen.py backend/app/api/v1/sales.py backend/tests/test_paket4.py backend/tests/test_gernot_261008_paket3.py
git commit -m "feat(rechte): Halle sieht keine Kundenkonditionen — Kundenantworten, Sonderpreisliste, Kreditlimit-Meldung (P4-D.2)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 22 (P4-D.3): Oberfläche — Kundenseite je Rolle: die Halle ohne Konditionen, Sonderpreise und Löschen

**Files:**
- Create: `frontend/tests/unit/rollen.check.ts` (Node-Prüfung)
- Modify: `frontend/src/services/rollen.ts` (Rollentext „Produktion“; neu `ROLLEN_OHNE_HALLE`, `KAUFMAENNISCHE_ROLLEN`, `KUNDEN_KONDITIONSFELDER`, `hatEineRolle`, `ohneKonditionen` vor `rollenInfo`)
- Modify: `frontend/src/pages/Customers.tsx`:
  - Import;
  - in `Customers`: `ohneHalle`, Excel-Import, Sonderpreis-Knopf;
  - in `CustomerForm`: `kaufmaennisch`, `ohneHalle`, `empfaengerGesperrt`, Payload, Haupt-E-Mail, Zahlungsziel, Konditionsblock, sechs Konditionsfelder, Empfänger, Aktiv;
  - in `AddressList` und `ContactList`: `onError`, `darfLoeschen`, Papierkorb.

**Interfaces:**
- Produces (`services/rollen.ts`):
  - `ROLLEN_OHNE_HALLE: readonly MandantenRolle[]` (`admin`, `sales`, `accounting`, `production_planner`)
  - `KAUFMAENNISCHE_ROLLEN` (`admin`, `sales`, `accounting`)
  - `KUNDEN_KONDITIONSFELDER`: die 11 Schlüssel von `KUNDENFELDER_KAUFMAENNISCH`
  - `hatEineRolle(rollen: readonly string[] | undefined, gesucht: readonly string[]): boolean`
  - `ohneKonditionen<T extends object>(daten: T): Partial<T>`: Kopie ohne die Konditionsfelder. Die Vorlage bleibt unverändert.
- Produces (Oberfläche): Kundenseite je Rolle wie in E-D7 beschrieben. Die Halle speichert ohne Konditionsfelder.
- Consumes: `useAuth().user.roles` (Token-Rollen, klein geschrieben), `getErrorMessage`, den Server-Vertrag aus D.2 (`test_halle_speichert_das_formular_ohne_konditionen`).
- Unverändert:
  - `App.tsx` (kein Wächter), `Layout.tsx` (Menü), `CommandPalette.tsx`: Die Halle erreicht die Seite weiter über „Suchen… Strg+K“ (E-D7);
  - `types/index.ts`, `api.ts`, `CustomerCard`;
  - `CreateOrderModal`/`EditOrderModal`/`OrderDocumentsModal`/`BelegVersand` (Bestellanlage und Belegversand der Halle, siehe Test `test_halle_legt_bestellung_mit_lieferadresse_an`);
  - der Lösch-Dialog in `Customers()`: Ihn öffnet kein Knopf (`setDeletingCustomer` nur mit `null`).

**Review Focus (D.3):**
- Payload der Halle bei Neuanlage und Änderung: keines der 11 Konditionsfelder.
- `show_prices_on_delivery_note` ist keine Kondition (nicht in `KUNDENFELDER_KAUFMAENNISCH`). Für die Halle ist es ausgeblendet und geht unverändert mit.
- Die Planung sieht alles wie bisher, Konditionen und Aktiv aber gesperrt.
- Für die Oberfläche gibt es keinen automatischen Test. Die Node-Prüfung deckt die drei Listen, `hatEineRolle` und `ohneKonditionen` ab, D.2 den Server-Vertrag. Den Rest prüft die Abnahme RF-D1 bis RF-D5.

- [ ] **Step 1: Node-Prüfung anlegen.** Datei `frontend/tests/unit/rollen.check.ts`:

```ts
// Prüft die Rollengruppen und die Konditionsfelder der Oberfläche gegen das
// Backend (P4-D.3), ohne Browser und ohne Testframework.
// Lauf: node tests/unit/rollen.check.ts  (Node >= 23.6: TypeScript ohne Build)
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  KAUFMAENNISCHE_ROLLEN, KUNDEN_KONDITIONSFELDER, ROLLEN_OHNE_HALLE, hatEineRolle, ohneKonditionen,
} from '../../src/services/rollen.ts';

// Gegenstück: backend/app/core/rollen.py (Konstanten, zwei Listen, KUNDENFELDER_KAUFMAENNISCH)
const py = readFileSync(new URL('../../../backend/app/core/rollen.py', import.meta.url), 'utf8');
const konstanten = new Map(
  [...py.matchAll(/^([A-Z]+) = "([a-z_]+)"$/gm)].map((m) => [m[1], m[2]] as [string, string]),
);
const liste = (name: string): string[] => {
  const m = py.match(new RegExp(`^${name} = \\[([A-Z, ]+)\\]$`, 'm'));
  assert.ok(m, `${name} nicht in rollen.py gefunden`);
  return m[1].split(',').map((s) => konstanten.get(s.trim()) ?? `?${s.trim()}`);
};
assert.deepEqual([...ROLLEN_OHNE_HALLE].sort(), liste('ROLLEN_OHNE_HALLE').sort());
assert.deepEqual([...KAUFMAENNISCHE_ROLLEN].sort(), liste('KAUFMAENNISCHE_ROLLEN').sort());
const block = py.match(/^KUNDENFELDER_KAUFMAENNISCH = \{\n([\s\S]*?)^\}$/m);
assert.ok(block, 'KUNDENFELDER_KAUFMAENNISCH nicht in rollen.py gefunden');
const konditionen = [...block[1].matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => m[1]);
assert.equal(konditionen.length, 11, `KUNDENFELDER_KAUFMAENNISCH: ${konditionen.join(', ')}`);
assert.deepEqual([...KUNDEN_KONDITIONSFELDER].sort(), konditionen.sort());

const faelle: Array<[string[] | undefined, readonly string[], boolean]> = [
  [undefined, ROLLEN_OHNE_HALLE, false],
  [[], ROLLEN_OHNE_HALLE, false],
  [['production_staff'], ROLLEN_OHNE_HALLE, false],
  [['production_staff', 'sales'], ROLLEN_OHNE_HALLE, true],
  [['production_planner'], ROLLEN_OHNE_HALLE, true],
  [['production_planner'], KAUFMAENNISCHE_ROLLEN, false],
  [['accounting'], KAUFMAENNISCHE_ROLLEN, true],
  [['offline_access', 'uma_authorization'], KAUFMAENNISCHE_ROLLEN, false],
];
for (const [rollen, gesucht, erwartet] of faelle) {
  assert.equal(hatEineRolle(rollen, gesucht), erwartet, `${JSON.stringify(rollen)} in ${gesucht.join('/')}`);
}

// Kundenformular der Halle (Customers.tsx): ohne Konditionen, alles andere bleibt.
const formular = {
  name: 'Großer Kern', telefon: '089 1', aktiv: true, show_prices_on_delivery_note: true,
  confirmation_emails: ['ab@grosser-kern.de'], payment_terms: 'NET_14', discount_percent: 0,
  skonto_percent: 0, skonto_days: 0, packaging_fee_amount: 0, packaging_fee_percent: 0,
  invoice_mode: 'EINZELN', pfand_abrechnung: 'JE_LIEFERUNG',
};
assert.deepEqual(ohneKonditionen(formular), {
  name: 'Großer Kern', telefon: '089 1', aktiv: true, show_prices_on_delivery_note: true,
  confirmation_emails: ['ab@grosser-kern.de'],
});
assert.equal(formular.payment_terms, 'NET_14', 'ohneKonditionen ändert die Vorlage nicht');
console.log(`rollen.check: 3 Listen wie im Backend, ${faelle.length} Fälle ok, Formular ohne Konditionen ok`);
```

- [ ] **Step 2: Rot.**

```bash
cd frontend && node tests/unit/rollen.check.ts 2>&1 | grep -E "SyntaxError|rollen.check"
```

Erwartet genau zwei Zeilen. Der Pfadteil vor `frontend/` hängt vom Worktree ab:

```text
file:///…/frontend/tests/unit/rollen.check.ts:7
SyntaxError: The requested module '../../src/services/rollen.ts' does not provide an export named 'KAUFMAENNISCHE_ROLLEN'
```

- [ ] **Step 3: `frontend/src/services/rollen.ts`.**

Rollentext der Rolle `production_staff`: diesen Block

```ts
      'Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen. ' +
      'Kein Zugriff auf Rechnungen, Preislisten, Auswertungen und Einstellungen.',
```

ersetzen durch

```ts
      'Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen; ' +
      'Kunden anlegen und ändern, ohne Konditionen und ohne Löschen. ' +
      'Kein Zugriff auf Rechnungen, DATEV, Preislisten, Auswertungen und Einstellungen.',
```

Vor `rollenInfo`: diesen Block

```ts
export function rollenInfo(rolle: string | null | undefined): RollenInfo | undefined {
```

ersetzen durch

```ts
/*
 * Rollengruppen wie im Backend (backend/app/core/rollen.py; Gegenprüfung:
 * frontend/tests/unit/rollen.check.ts). Die Rollen kommen klein geschrieben
 * aus dem Token (useAuth().user.roles).
 */
/** Alle außer der Halle: sehen Kundenkonditionen und Sonderpreise, löschen Adressen und Ansprechpartner. */
export const ROLLEN_OHNE_HALLE: readonly MandantenRolle[] = ['admin', 'sales', 'accounting', 'production_planner'];
/** Kaufmännisch: ändern Konditionen, deaktivieren und reaktivieren Kunden. */
export const KAUFMAENNISCHE_ROLLEN: readonly MandantenRolle[] = ['admin', 'sales', 'accounting'];
/**
 * Konditionen eines Kunden (Backend: KUNDENFELDER_KAUFMAENNISCH). Die Halle
 * bekommt sie als null (P4-D.2) und schickt sie beim Speichern nicht mit:
 * Aus null machte das Formular seine Vorgaben, und der Server lehnte ab.
 */
export const KUNDEN_KONDITIONSFELDER = [
  'payment_terms', 'credit_limit', 'price_list_id', 'discount_percent', 'skonto_percent',
  'skonto_days', 'packaging_fee_amount', 'packaging_fee_percent', 'datev_account',
  'pfand_abrechnung', 'invoice_mode',
] as const;

/** Hat das Login (Rollen aus dem Token) mindestens eine der gesuchten Rollen? */
export function hatEineRolle(rollen: readonly string[] | undefined, gesucht: readonly string[]): boolean {
  return !!rollen?.some((r) => gesucht.includes(r));
}

/** Kopie der Kundendaten ohne die Konditionsfelder (Kundenformular der Halle, P4-D.3). */
export function ohneKonditionen<T extends object>(daten: T): Partial<T> {
  const konditionen: readonly string[] = KUNDEN_KONDITIONSFELDER;
  return Object.fromEntries(
    Object.entries(daten).filter(([feld]) => !konditionen.includes(feld)),
  ) as Partial<T>;
}

export function rollenInfo(rolle: string | null | undefined): RollenInfo | undefined {
```

- [ ] **Step 4: Grün (Node).**

```bash
cd frontend && node tests/unit/rollen.check.ts
```

Erwartet: `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`.

- [ ] **Step 5: `frontend/src/pages/Customers.tsx`, Seite `Customers`.**

Import: diesen Block

```tsx
import { useAuth } from '../context/AuthContext';
```

ersetzen durch

```tsx
import { useAuth } from '../context/AuthContext';
import { KAUFMAENNISCHE_ROLLEN, ROLLEN_OHNE_HALLE, hatEineRolle, ohneKonditionen } from '../services/rollen';
```

Kopf von `Customers`: diesen Block

```tsx
export default function Customers() {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
```

ersetzen durch

```tsx
export default function Customers() {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Die Halle pflegt Kunden ohne Konditionen (P4-D.3): kein Sonderpreis-Knopf,
  // kein Excel-Import — der Server sperrt beides für sie (P4-D.2, /imports).
  const { user } = useAuth();
  const ohneHalle = hatEineRolle(user?.roles, ROLLEN_OHNE_HALLE);
```

Excel-Import: diesen Block

```tsx
            <ExcelImport entity="customers" onImported={() => queryClient.invalidateQueries({ queryKey: ['customers'] })} />
```

ersetzen durch

```tsx
            {ohneHalle && (
              <ExcelImport entity="customers" onImported={() => queryClient.invalidateQueries({ queryKey: ['customers'] })} />
            )}
```

Sonderpreis-Knopf der Kundenkarte: diesen Block

```tsx
              <button
                className="absolute top-3 right-3 text-gray-400 hover:text-amber-600 dark:text-gray-500 dark:hover:text-amber-300"
                title="Sonderpreise verwalten"
                onClick={(e) => { e.stopPropagation(); setPricesFor(customer); }}
              >
                <Tag className="w-4 h-4" />
              </button>
```

ersetzen durch

```tsx
              {ohneHalle && (
                <button
                  className="absolute top-3 right-3 text-gray-400 hover:text-amber-600 dark:text-gray-500 dark:hover:text-amber-300"
                  title="Sonderpreise verwalten"
                  onClick={(e) => { e.stopPropagation(); setPricesFor(customer); }}
                >
                  <Tag className="w-4 h-4" />
                </button>
              )}
```

- [ ] **Step 6: `frontend/src/pages/Customers.tsx`, Formular `CustomerForm`.**

Nach `istAdmin`: diesen Block

```tsx
  const istAdmin = !!user?.roles?.includes('admin');
```

ersetzen durch

```tsx
  const istAdmin = !!user?.roles?.includes('admin');
  // Konditionen und Aktiv-Schalter ändern nur Verwaltung, Vertrieb, Buchhaltung —
  // wie der Server (kundenfeldschutz, P4-D.1). Die Planung sieht die Werte gesperrt.
  const kaufmaennisch = hatEineRolle(user?.roles, KAUFMAENNISCHE_ROLLEN);
  // Die Halle sieht keine Konditionen (der Server liefert null, P4-D.2) und
  // schickt sie nicht mit (P4-D.3). Haupt-E-Mail und Empfänger ändert sie nur
  // bei der Neuanlage (kundenfeldschutz, Paket 3).
  const ohneHalle = hatEineRolle(user?.roles, ROLLEN_OHNE_HALLE);
  const empfaengerGesperrt = !!customer && !ohneHalle;
```

Speichern: diesen Block

```tsx
      let saved: Customer;
      if (customer) {
        saved = await salesApi.updateCustomer(customer.id, payload);
      } else {
        saved = await salesApi.createCustomer(payload);
      }
```

ersetzen durch

```tsx
      // Halle: ohne Konditionsfelder. Sonst würden aus den ausgeblendeten Werten
      // (null) die Vorgaben des Formulars, und der Server lehnte ab (P4-D.3).
      // Neue Kunden der Halle bekommen die Standardkonditionen des Servers.
      const daten = ohneHalle ? payload : ohneKonditionen(payload);
      let saved: Customer;
      if (customer) {
        saved = await salesApi.updateCustomer(customer.id, daten);
      } else {
        saved = await salesApi.createCustomer(daten);
      }
```

Haupt-E-Mail, 10 Leerzeichen Einzug: diesen Block

```tsx
          label="E-Mail (Hauptkontakt)"
```

ersetzen durch

```tsx
          label="E-Mail (Hauptkontakt)"
          disabled={empfaengerGesperrt}
```

Zahlungsziel: diesen Block

```tsx
        <Select
          label="Zahlungsziel"
          options={paymentTermsOptions}
          value={formData.payment_terms}
          onChange={(e) => setFormData({ ...formData, payment_terms: e.target.value })}
        />
```

ersetzen durch

```tsx
        {ohneHalle && (
          <Select
            label="Zahlungsziel"
            disabled={!kaufmaennisch}
            options={paymentTermsOptions}
            value={formData.payment_terms}
            onChange={(e) => setFormData({ ...formData, payment_terms: e.target.value })}
          />
        )}
```

Beginn des Konditionsblocks: diesen Block

```tsx
      {/* Rabatte + Skonto + Verpackungsgebühr */}
      <div className="bg-gray-50 dark:bg-gray-700/30 p-4 rounded-lg space-y-3">
        <h4 className="font-medium text-sm text-gray-700 dark:text-gray-300">Konditionen</h4>
```

ersetzen durch

```tsx
      {/* Rabatte + Skonto + Verpackungsgebühr — nicht für die Halle (P4-D.3) */}
      {ohneHalle && (
      <div className="bg-gray-50 dark:bg-gray-700/30 p-4 rounded-lg space-y-3">
        <h4 className="font-medium text-sm text-gray-700 dark:text-gray-300">Konditionen</h4>
        {!kaufmaennisch && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Konditionen ändern Verwaltung, Vertrieb und Buchhaltung.
          </p>
        )}
```

Ende des Konditionsblocks (die Zeile `</div>` direkt vor dem Kommentar „Belegversand“): diesen Block

```tsx
      </div>

      {/* Belegversand (Paket 3, Q2): eine Mail an alle Adressen der Belegart */}
```

ersetzen durch

```tsx
      </div>
      )}

      {/* Belegversand (Paket 3, Q2): eine Mail an alle Adressen der Belegart */}
```

Die sechs Konditionsfelder (12 Leerzeichen Einzug, je Block genau ein Treffer):

```tsx
            label="Jahresrabatt %"
```

ersetzen durch

```tsx
            label="Jahresrabatt %"
            disabled={!kaufmaennisch}
```

```tsx
            label="Skonto %"
```

ersetzen durch

```tsx
            label="Skonto %"
            disabled={!kaufmaennisch}
```

```tsx
            label="Skontofrist (Tage)"
```

ersetzen durch

```tsx
            label="Skontofrist (Tage)"
            disabled={!kaufmaennisch}
```

```tsx
            label="Verpackungsgebühr (€)"
```

ersetzen durch

```tsx
            label="Verpackungsgebühr (€)"
            disabled={!kaufmaennisch}
```

```tsx
            label="Pfandabrechnung"
```

ersetzen durch

```tsx
            label="Pfandabrechnung"
            disabled={!kaufmaennisch}
```

```tsx
            label="Abrechnung"
```

ersetzen durch

```tsx
            label="Abrechnung"
            disabled={!kaufmaennisch}
```

Hinweis im Block „Belegversand“: diesen Block

```tsx
          Leer = Haupt-E-Mail des Kunden.
        </p>
```

ersetzen durch

```tsx
          Leer = Haupt-E-Mail des Kunden.
        </p>
        {empfaengerGesperrt && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Haupt-E-Mail und Empfänger ändern Verwaltung, Vertrieb, Buchhaltung und Planung.
          </p>
        )}
```

Die drei Empfängerlisten (12 Leerzeichen Einzug, je Block genau ein Treffer):

```tsx
            label="Auftragsbestätigung an"
```

ersetzen durch

```tsx
            label="Auftragsbestätigung an"
            disabled={empfaengerGesperrt}
```

```tsx
            label="Lieferschein an"
```

ersetzen durch

```tsx
            label="Lieferschein an"
            disabled={empfaengerGesperrt}
```

```tsx
            label="Rechnung an"
```

ersetzen durch

```tsx
            label="Rechnung an"
            disabled={empfaengerGesperrt}
```

Aktiv-Schalter, Checkbox: diesen Block

```tsx
          checked={formData.aktiv}
          onChange={(e) => setFormData({ ...formData, aktiv: e.target.checked })}
```

ersetzen durch

```tsx
          checked={formData.aktiv}
          disabled={!kaufmaennisch}
          onChange={(e) => setFormData({ ...formData, aktiv: e.target.checked })}
```

Aktiv-Schalter, Beschriftung: diesen Block

```tsx
        <span className="text-sm text-gray-700 dark:text-gray-300">Aktiv</span>
```

ersetzen durch

```tsx
        <span className="text-sm text-gray-700 dark:text-gray-300">Aktiv</span>
        {!kaufmaennisch && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            (deaktivieren und reaktivieren Verwaltung, Vertrieb, Buchhaltung)
          </span>
        )}
```

- [ ] **Step 7: `frontend/src/pages/Customers.tsx`, `AddressList` und `ContactList`.**

In `AddressList`, Löschen: diesen Block

```tsx
  const deleteMutation = useMutation({
    mutationFn: (id: string) => salesApi.deleteAddress(customerId, id),
    onSuccess: () => { invalidate(); toast.success('Adresse gelöscht'); },
  });
```

ersetzen durch

```tsx
  const deleteMutation = useMutation({
    mutationFn: (id: string) => salesApi.deleteAddress(customerId, id),
    onSuccess: () => { invalidate(); toast.success('Adresse gelöscht'); },
    onError: (e) => toast.error(getErrorMessage(e, 'Löschen fehlgeschlagen')),
  });
  // Löschen nur ohne die Halle — wie der Server (P4-D.1)
  const { user } = useAuth();
  const darfLoeschen = hatEineRolle(user?.roles, ROLLEN_OHNE_HALLE);
```

In `AddressList`, Papierkorb: diesen Block

```tsx
              <Button type="button" variant="ghost" size="sm" icon={<Trash className="w-4 h-4" />} onClick={() => deleteMutation.mutate(a.id)} />
```

ersetzen durch

```tsx
              {darfLoeschen && (
                <Button type="button" variant="ghost" size="sm" icon={<Trash className="w-4 h-4" />} onClick={() => deleteMutation.mutate(a.id)} />
              )}
```

In `ContactList`, Löschen: diesen Block

```tsx
    mutationFn: (contactId: string) => salesApi.deleteContact(customerId, contactId),
    onSuccess: () => {
      invalidate();
      toast.success('Ansprechpartner gelöscht');
    },
  });
```

ersetzen durch

```tsx
    mutationFn: (contactId: string) => salesApi.deleteContact(customerId, contactId),
    onSuccess: () => {
      invalidate();
      toast.success('Ansprechpartner gelöscht');
    },
    onError: (e) => toast.error(getErrorMessage(e, 'Löschen fehlgeschlagen')),
  });
  // Löschen nur ohne die Halle — wie der Server (P4-D.1)
  const { user } = useAuth();
  const darfLoeschen = hatEineRolle(user?.roles, ROLLEN_OHNE_HALLE);
```

In `ContactList`, Papierkorb: diesen Block

```tsx
              <Button
                type="button"
                variant="ghost"
                size="sm"
                icon={<Trash className="w-4 h-4" />}
                onClick={() => deleteMutation.mutate(c.id)}
              />
```

ersetzen durch

```tsx
              {darfLoeschen && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  icon={<Trash className="w-4 h-4" />}
                  onClick={() => deleteMutation.mutate(c.id)}
                />
              )}
```

- [ ] **Step 8: Prüfen.**

```bash
cd frontend && ./node_modules/.bin/tsc --noEmit -p . ; echo "tsc exit $?"
cd frontend && npm run build 2>&1 | tail -1
cd frontend && node tests/unit/rollen.check.ts
grep -c 'disabled={!kaufmaennisch}' frontend/src/pages/Customers.tsx     # 8
grep -c 'disabled={empfaengerGesperrt}' frontend/src/pages/Customers.tsx # 4
grep -c 'ohneHalle && (' frontend/src/pages/Customers.tsx                # 4
grep -c 'ohneKonditionen(payload)' frontend/src/pages/Customers.tsx      # 1
grep -c 'darfLoeschen && (' frontend/src/pages/Customers.tsx             # 2
grep -c "Löschen fehlgeschlagen" frontend/src/pages/Customers.tsx        # 2
git status --short frontend/src/App.tsx frontend/src/components/common/   # keine Ausgabe
```

Erwartet:
- `tsc` ohne Ausgabe, `tsc exit 0`
- Build endet mit `✓ built in …`; die Warnung „Some chunks are larger than 500 kB“ ist Altbestand
- `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`
- die `grep`-Zählungen wie im Kommentar; `git status` ohne Ausgabe (Menü, Palette und Routen unberührt, E-D7)

- [ ] **Step 9: Commit.**

```bash
git add frontend/tests/unit/rollen.check.ts frontend/src/services/rollen.ts frontend/src/pages/Customers.tsx
git commit -m "feat(rechte): Kundenseite je Rolle — Halle ohne Konditionen, Sonderpreise und Löschen; Planung ändert Konditionen und Aktiv nicht (P4-D.3)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 23 (P4-D.4): Abschluss D — Vollauf, statische Prüfung, Meldung (ohne Commit)

- [ ] **Step 1: Prozedur V** (Kopf) → `14 failed, N passed, 2 skipped, 1 error in …s` und **keine** Zeile vor `--- Ende Abgleich`. N dient nur zur Orientierung: im Gesamtplan errechnet 1937 (Stand vor Task 20: 1904, +14 aus P4-D.1, +19 aus P4-D.2); einzeln gemessen auf `df84f7b` 1677 (1644 + 33), auf `bd56901` 1742 (1709 + 33).

- [ ] **Step 2: Statik und Oberfläche erneut.**

```bash
cd backend && /opt/homebrew/bin/ruff check --select F821,F823 app/api/v1/sales.py app/core/rollen.py app/schemas/customer.py; echo "ruff exit $?"
cd frontend && node tests/unit/rollen.check.ts && ./node_modules/.bin/tsc --noEmit -p . ; echo "tsc exit $?"
git log --format=%s -3
git diff --stat HEAD~3..HEAD
```

Erwartet:
- `ruff exit 0`, die Node-Zeile wie in D.3, `tsc exit 0`;
- `git log`: die drei Betreffe von P4-D.3, P4-D.2 und P4-D.1, neueste zuerst. Sonst stoppen und melden, denn dann stimmt `HEAD~3` nicht;
- `git diff --stat` läuft **ohne Pfadangabe**, damit auch eine versehentliche Änderung woanders auffällt. Er nennt genau diese 8 Dateien und keine weitere: `backend/app/api/v1/sales.py`, `backend/app/core/rollen.py`, `backend/app/schemas/customer.py`, `backend/tests/test_gernot_261008_paket3.py`, `backend/tests/test_paket4.py`, `frontend/src/pages/Customers.tsx`, `frontend/src/services/rollen.ts`, `frontend/tests/unit/rollen.check.ts`. Eine weitere Datei greift Stoppregel 2.

- [ ] **Step 3: Meldung an den Manager (Zwischenstand, nicht anhalten, falls weitere Abschnitte folgen).** Inhalt:
  - die drei Commit-Hashes;
  - Rot und Grün je Task wörtlich;
  - Summenzeile und `comm`-Ausgabe der Prozedur V;
  - besondere Vorkommnisse, zum Beispiel selbst behobene Ankerfehler mit `grep -n`-Beleg.

---

## Abschluss

### Task 24: Abschluss Paket 4 — Gesamtprüfung und Gesamtmeldung

**Files:** keine Änderung.

- [ ] **Step 1: Alle Paket-4-Tests** (Befehl „Alle Paket-4-Tests“ aus Global Constraints) → `119 passed` (18 A + 21 B + 47 C + 33 P4-D).
- [ ] **Step 2: Bestands- und Abnahmetests** — `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket3.py -q -p no:cacheprovider 2>&1 | tail -1` → `467 passed`; Paket-3-Abnahme (Befehl aus Global Constraints) → `5 passed, 462 deselected` (Stoppregel 4); `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_nachtrag_0910.py -q -p no:cacheprovider 2>&1 | tail -1` → `174 passed` (D/F/O unverändert).
- [ ] **Step 3: Node-Prüfungen** — `cd frontend && node tests/unit/positionsaenderung.check.ts && node tests/unit/rechnungssuche.check.ts && node tests/unit/belegstatus.check.ts && node tests/unit/rollen.check.ts && node tests/unit/dateiname.check.ts && node tests/unit/belegpfad.check.ts` → `positionsaenderung.check: 20 Fälle ok`, `rechnungssuche.check: 14 Fälle ok`, `belegstatus.check: 29 Fälle ok`, `rollen.check: 3 Listen wie im Backend, 8 Fälle ok, Formular ohne Konditionen ok`, `dateiname.check: 8 Fälle ok`, `belegpfad.check: 35 Fälle ok`.
- [ ] **Step 4: Prozedur V** — gilt der Lauf aus Task 23 Step 1, wenn seitdem nichts geändert wurde (`git status --porcelain` sauber); sonst neu → `14 failed, N passed, 2 skipped, 1 error` (auf `521ed6d` gemessen N = 1937), Abgleich leer.
- [ ] **Step 5: Statisch über alle geänderten Python-Dateien** — `git diff --name-only <Basis>..HEAD -- '*.py' | xargs /opt/homebrew/bin/ruff check --select F821,F823` (aus dem Wurzelverzeichnis, 20 Dateien) → keine Ausgabe, Exit-Code 0.
- [ ] **Step 6: Frontend** — `tsc` ohne Ausgabe, `npm run build` mit `✓ built`.
- [ ] **Step 7: Diff und Commits** — `git diff --stat <Basis>..HEAD` → genau die 39 Dateien aus „File Structure“; `git log --oneline <Basis>..HEAD` → 19 Commits in der Reihenfolge P4-A.1–A.5, P4-B.1–B.6, P4-C.1–C.5, P4-D.1–D.3; `git log --format=%B <Basis>..HEAD | grep -c 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>'` → `19`; `git status --porcelain` → nur die sauberen `??`-Einträge.
- [ ] **Step 8: Gesamtmeldung** (kurz, mit Zeigern; die Abschlussmeldungen A, B, C, P4-D gehen darin auf): `<Basis>`, `<Basis-B>`, `<Basis C>`, `<Basis-P4-D>`; Commit-Hash je Task; Rot/Grün je Task (erwartet vs. gemessen); Summenzeilen der Prozedur V je Abschnitt; Ergebnisse von Step 1–7; jede selbst behobene Anker- oder Redaktionsabweichung mit Datei und Funktion. Hinweis: Browser-Prüfungen und Produktionsschritte macht der Manager.

---

## Abnahme (Manager, im Arbeitsbaum nachmessen — nicht dem Bericht glauben)

- **Gesamt:** `tests/test_paket4.py` `119 passed`; `tests/test_gernot_261008_paket3.py` `467 passed`, Paket-3-Abnahme `5 passed`; `tests/test_nachtrag_0910.py` `174 passed`; Prozedur V `14 failed, N passed, 2 skipped, 1 error`, Abgleich leer; `ruff` F821/F823 über die 20 Python-Dateien ohne Befund; sechs Node-Prüfungen wie in Task 24 Step 3; `tsc` ohne Ausgabe, Build `✓ built`; Diff genau die 39 Dateien aus „File Structure“, 19 Commits mit `Co-Authored-By`-Zeile.
- **A** (Diff `<Basis-A>..<Basis-B>`): A-Klassen `TestP4AStueckliste`, `TestP4AEntwurfPacken`, `TestP4ATagesplanKnoepfe` `18 passed`; genau die 9 Dateien aus Task 6 Step 3; 5 Commits.
- **B** (Diff `<Basis-B>..<Basis C>`): B-Klassen `21 passed`; genau die 14 Dateien aus Task 13 Step 5; 6 Commits.
- **C** (Diff `<Basis C>..<Basis-P4-D>`): C-Klassen `47 passed`; genau die 18 Dateien aus „File Structure (C)“; 5 Commits.
- **P4-D** (Diff `<Basis-P4-D>..HEAD`): D-Klassen `33 passed`; genau die 8 Dateien aus Task 23 Step 2; 3 Commits. Wachhund: `geprueft` enthält `GET /api/v1/belegstatus` (55 Routen×Methoden).

## Manager-Abnahme (kein Worker-Task; jede Schreibaktion mit Freigabe)

Zugriff wie immer: `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103`, `C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)` (der Containername wechselt je Deploy), Skripte per `docker exec -i "$C" python3 - < skript.py`; lesend immer `mode=ro`, Backups WAL-sicher (Memory `novaerp-ssh-wal-backup`). Festgeschriebene Rechnungen werden nie geändert (GoBD).

**Ablauf rund um den gemeinsamen Deploy** (Einzelheiten in den Unterabschnitten A, B, C, P4-D):
0. **Vor dem Dispatch:**
   - **Nachspiel des Gesamtplans**, nur nötig, wenn `main` seit `521ed6d` vorgerückt ist (auf `521ed6d` ist der Endstand gemessen, Prüfstand): frische Kopie (`git archive main | tar -x -C /tmp/p4-kopie-<kürzel>`, `frontend/node_modules` als Symlink), dann `python3 -I /tmp/p4-merge-tools/apply_all.py <Kopie> /tmp/p4/plan.md` (erwartet `{'ersetzt': 143, 'neu': 14, 'anhang': 13, 'fehler': 0}`, keine Zeile `FEHLER` oder `UNKLAR`) und die Prüfungen aus Task 24 Steps 1–6. Rot/Grün je Task zeigt erst der Worker-Lauf.
   - **E-D7 Variante a bestätigen** (Kundenseite für die Halle offen, ohne Konditionen und Löschen); sonst P4-D.3 neu planen.
   - **Worktree anlegen** (Global Constraints) und Codex mit `.git` in `writable_roots` und `mcp_servers={}` starten.
1. **Lokal, vor dem Deploy:** RF-D1–RF-D5 (P4-D, lokales Backend je Rolle); Ü1–Ü6 soweit lokal möglich (Kopie der Demo- bzw. `minga`-DB); B.5 Escape im echten Belegdialog.
2. **Produktion lesend, vor dem Deploy:** A-R1 Schritt 0 (**Pflicht**: RE-2026-00001 und RE-2026-00005 als PDF ablegen, Stand vor Paket 4) und Schritt 1 (Trockenlauf); R-B1 (erwartet `0`, `0`, `['BE-20261007-0008', 'BE-20261008-0002']`); R-C1 (Erwartung Belegstatus am Abnahmetag festhalten); R-D0 (nichts zu tun).
3. **Testmandant `abnahme`, vor dem Deploy:** Vorbereitung A (P4A-Produkte, Kunde, E1–E5 im alten Formular; Tagesplan-Tab offen lassen).
4. **Deploy** einmal für A, B, C und P4-D (Backups `*-vor-deploy-<hash>-*.db` für minga, demo, demo.seed). Kein Datenschritt vor dem Deploy.
5. **Live:** `/health` 200, Startlog ohne Fehler; openapi enthält `/api/v1/belegstatus`; R-D1 (`CustomerResponse.payment_terms` nullable); RA1–RA9 in `abnahme`; R-C2 Punkte 1–8 in `minga` (nichts versenden, nichts anlegen); R-B2 (1) beim ersten echten „Ausgeliefert“.
6. **Schreibend, nur mit ausdrücklicher Freigabe:** A-R1 Schritte 2–6 (24 Mixe `is_bundle = 1`; WAL-sicheres Backup, `APPLY`, Nachkontrolle; danach RA2m, RA8m, RA9m in `minga` nur ansehen); R-D2 (Rechte live; Weg 1 ohne Testbenutzer bevorzugt, Weg 2 legt einen Benutzer in Keycloak und `benutzer_audit` an).
7. **Gernot informieren** in einer Nachricht: R-C3 (Belegstatus, Dateinamen), R-B2 (0) (BE-20261008-0002 von Hand berechnen), dazu die gebündelten Fragen unter „Offene Punkte“.
8. **Später:** R-B2 (2) am 01.11.2026 nach 06:30 (erster Monatslauf mit Lieferscheinen aus B.3, lesend); R-B3 nach Gernots Antwort zu den sieben Alt-Entwürfen (Backup, Trockenlauf, Freigabe, `APPLY`).

### A — Tagesplan und Produktion

#### Oberfläche (RA1–RA9 in `abnahme`; in `minga` nur ansehen)

**Wo geklickt wird.** Jede Probe, die etwas ändert, läuft im **Testmandanten `abnahme`** (`https://abnahme.novaerp.de`, Admin `abnahme-admin@novaerp.de`, Passwort in `~/.secrets/novaerp-abnahme-admin`, nie ausgeben). Im Mandanten **`minga` wird nur angesehen**:
- kein Klick auf „Gepackt“, „Ausgeliefert“, „Bestätigen“, keine Sammelaktion;
- kein „Packliste“ (legt einen Lieferschein mit Nummer an, wenn noch keiner existiert);
- kein Speichern im Produktformular.

Grund: „Gepackt“ und „Ausgeliefert“ bestätigen echte Kundenbestellungen, „Ausgeliefert“ ist unumkehrbar (Bestand, Leergut, kein Storno). Ein echter Mix auf „Variabel“ fällt still aus dem Sortenbedarf, solange er variabel ist (`get_packaging_plan` addiert für ein variables Bundle ohne Auswahl nichts).

**Vorbereitung in `abnahme`, am Abnahmetag vor dem Deploy** (altes Formular; so entsteht der Prod-Zustand „Stückliste da, `is_bundle` 0“ nach):
1. Produkte anlegen: „P4A Snackbox Erbse“ (SKU `P4A-ERB`, Kategorie Microgreen), „P4A Snackbox Radieschen“ (`P4A-RAD`), „P4A Genussmix (VPE 6)“ (`P4A-MIX`, Kategorie Bundle). Im Mix „Fest (Mischkiste)“, Stückliste Erbse 1 und Radieschen 1, dann „Speichern“.
2. Kunde „P4A Packkunde“.
3. Bestellungen im Formular (bleiben Entwurf), Liefertage relativ zum Abnahmetag:
   - E1: morgen, 5 × `P4A-MIX`;
   - E2: heute, 2 × `P4A-MIX`;
   - E3: gestern, 1 × `P4A-ERB`;
   - E4: morgen, 1 × `P4A-ERB`, danach in der Bestellliste „Bestätigen“;
   - E5: morgen, 1 × `P4A-MIX`.
4. Den Tagesplan von heute in einem Tab öffnen und offen lassen (RA7).

**Nach dem Deploy, in `abnahme`:**
1. **RA1 Produktformular:** `P4A-MIX` öffnen und ohne Änderung speichern. Erneut öffnen: „Fest (Mischkiste)“ ist gewählt, die Stückliste ist da. In Produkte und Bestellung erscheint 📦 vor dem Namen.
   - Auf „Variabel“ umstellen und speichern: Die Stückliste verschwindet aus dem Formular. Im Sortenbedarf von heute fallen E1, E2 und E5 heraus.
   - Zurück auf „Fest“ und speichern: Der Mix wird wieder aufgelöst.
2. **RA2 Sortenbedarf (Tagesplan heute):**
   - Sorten: „P4A Snackbox Erbse“ 9 (5 + 2 + 1 aus Mixen, 1 aus E4) und „P4A Snackbox Radieschen“ 8, je mit „inkl. P4A Genussmix (VPE 6)“.
   - Umschalter „Artikel“: „P4A Genussmix (VPE 6)“ 8 mit Einheit · 3 Bestellungen, „P4A Snackbox Erbse“ 1 · 1 Bestellung.
3. **RA3 Gepackt (Entwurf):** E1 zeigt in Verpacken „Gepackt“ mit Tooltip.
   - Ein Klick zeigt den Toast „BE-… bestätigt und als gepackt markiert“. Die Zeile wandert nach „Bereits gepackt“, der Sortenbedarf sinkt sofort um 5 je Sorte.
   - Im Verlauf von E1 stehen zwei Einträge: Bestätigt („Beim Packen im Tagesplan bestätigt“) und Gepackt.
4. **RA4 Ausgeliefert (Entwurf, Liefertag heute):** E2 in Ausliefern → „Ausgeliefert“. Der Toast lautet „… bestätigt und ausgeliefert“, Lieferdatum heute, Bestandsbuchung im Verlauf bzw. in den Bewegungen (ohne Bestand nur Warnung).
5. **RA5 Zwei Geräte:** Gerät 1 klickt „Gepackt“ auf E5, Gerät 2 klickt danach dieselbe Zeile ohne Neuladen. Gerät 2 zeigt den Fehler-Toast „Statuswechsel nicht möglich: Gepackt → Gepackt“ und lädt neu. Im Verlauf von E5 steht genau ein CONFIRM.
6. **RA6 Bestellliste unverändert:** E3 bekommt dort weiter „Bestätigen“ (nicht klicken). Sammelaktion „Gepackt“ nur mit E3 markiert: Toast „Keine der 1 markierten Bestellungen kann auf „Gepackt" gesetzt werden“, nichts geändert. (Mit einer bestätigten Bestellung in der Auswahl würde die Sammelaktion diese packen und E3 nur melden.)
7. **RA7 Alter Tab:** Der vor dem Deploy geöffnete Tagesplan zeigt bei Entwürfen weiter „erst bestätigen“. „Gepackt“ auf E4 (bestätigt) funktioniert dort wie in Paket 2.
8. **RA8 Belege:** Für E2 (geliefert) im Belegdialog den Lieferschein anlegen bzw. öffnen (in `abnahme` erlaubt). Unter der Position „P4A Genussmix (VPE 6)“ steht eine graue Zeile „P4A Snackbox Erbse | P4A Snackbox Radieschen“.
9. **RA9 Vergangener Entwurf:** Tagesplan von gestern. E3 zeigt in Verpacken „erst bestätigen“ (Tooltip „Liefertag vorbei — …“) und in Ausliefern nur das Badge „Entwurf“, keinen Knopf.

**In `minga`, nur ansehen (nach A-R1):**
- **RA2m Sortenbedarf, Packtag 11.10.:** BE-20261011-0001 (5 × Genussmix) erscheint als „BIO Snackbox | Amaranth/Erbse/Mizuna/Radieschen/Senf/Sonnenblume“ mit je 5 und „inkl. BIO Genussmix (VPE 6)“, wie im A-R1-Trockenlauf, Punkt 5. Dazu kommen Einzelartikel desselben Tags als Artikel. Umschalter „Artikel“: „BIO Genussmix (VPE 6) 5 Kisten · 1 Bestellung“.
- **RA9m Alt-Entwürfe:** Tagesplan 17.09.2026: BE-20260917-0002 und BE-20260917-0003 stehen in Ausliefern ohne „Ausgeliefert“. Tagesplan 16.09. bzw. 17.09. (ihre Packtage): Verpacken zeigt „erst bestätigen“. Ebenso 07.10. für BE-20261007-0001.
- **RA8m Belege:** RE-2026-00005 als PDF öffnen (reiner Abruf) und mit der Ablage aus A-R1 Schritt 0 vergleichen. Erwartet: neu ist die graue Inhaltszeile unter den Mix-Positionen, sonst gleich.

**Aufräumen in `abnahme`:** nicht nötig, die P4A-Daten bleiben als Abnahmespur. Wer E1 und E5 nicht gepackt stehen lassen will, storniert sie in der Bestellliste.

#### A-R1: Die 24 Mixe mit Stückliste als festes Bundle kennzeichnen (G11, G74)

**Ausführung durch den Manager, nicht durch den Codex-Worker.** Das Skript liegt nur hier im Runbook, es kommt kein Code ins Repo.
- **Alles läuft vom Mac aus.** Das Skript liegt lokal unter `/tmp/p4a-r1.py` und geht über die Standardeingabe von `ssh` in `docker exec -i … python3 -`. Auf dem Server entsteht nichts außer unter `/root/backups`. Logs entstehen lokal und werden per `scp` nach `/root/backups` kopiert.
- Schritt 0 (Belege ablegen) ist Pflicht und läuft **vor dem Deploy** von Paket 4.
- Schritt 1 ist rein lesend und darf jederzeit laufen.
- Geschrieben wird nur in Schritt 5, **nach dem Deploy von A.1** und mit Freigabe. Ohne APPLY öffnet das Skript die DB mit `mode=ro` und führt nur SELECT aus.

Einmal je Shell (zsh oder bash) definieren, gilt für alle Schritte:

```bash
p4ssh() { ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103 "$@"; }
```

Skript lokal als `/tmp/p4a-r1.py` speichern (Inhalt unverändert):

```python
"""Runbook A-R1 (Paket 4, Abschnitt A): Mixe mit Stückliste als festes Bundle kennzeichnen.

Trockenlauf (Standard): Datenbank nur lesend (mode=ro), nichts wird geschrieben.
Schreiben nur mit Argument APPLY (python3 - APPLY) und nur nach Freigabe.

Setzt products.is_bundle = 1 für genau die Artikel, die eine Stückliste haben,
nicht variabel sind und noch is_bundle = 0 tragen (Stand 09.10.2026: 24).
Rechnungen, Bestellungen und Belege werden nicht angefasst (GoBD).
"""
import json
import sqlite3
import sys
from datetime import date, datetime, timezone

APPLY = len(sys.argv) > 1 and sys.argv[1] == "APPLY"
DB = "/data/tenants/minga.db"

# Stand der Lesung am 09.10.2026 (Abgleich Paket 4). Weicht die Menge ab, hat
# jemand inzwischen Stücklisten gepflegt: abbrechen und neu lesen, nicht raten.
ERWARTET = {
    "MG-11001", "MG-11002", "MG-11003", "MG-11004", "MG-11005", "MG-11006",
    "MG-11007", "MG-11008", "MG-11009", "MG-11010", "MG-11011", "MG-11012",
    "MG-11013", "MG-11014", "MG-11015", "MG-11036", "MG-11038", "MG-12020",
    "MG-12021", "MG-12022", "MG-12023", "MG-12024", "MG-12025", "MG-14005",
}

if APPLY:
    con = sqlite3.connect(DB, isolation_level=None)
else:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
q = lambda sql, *a: con.execute(sql, a).fetchall()


def abbruch(text):
    print("ABBRUCH:", text)
    sys.exit(2)


print("Modus:", "APPLY" if APPLY else "TROCKENLAUF (nur lesen)")

kandidaten = q("""
    select p.id, p.sku, p.name, p.category, p.is_bundle, p.is_variable_bundle,
           count(bc.id) as komponenten
    from products p join bundle_components bc on bc.parent_product_id = p.id
    where coalesce(p.is_bundle, 0) = 0 and coalesce(p.is_variable_bundle, 0) = 0
    group by p.id order by p.sku""")
skus = {r["sku"] for r in kandidaten}
print(f"1) Kandidaten (Stückliste, nicht variabel, is_bundle=0): {len(kandidaten)}")
for r in kandidaten:
    print(f"   {r['sku']}  {r['name']}  [{r['category']}]  {r['komponenten']} Komponenten")

# Vorbedingungen
if skus != ERWARTET:
    abbruch(f"Kandidaten weichen vom Stand 09.10. ab: neu {sorted(skus - ERWARTET)}, "
            f"fehlen {sorted(ERWARTET - skus)}")
fremd = [r["sku"] for r in kandidaten if r["category"] != "BUNDLE"]
if fremd:
    abbruch(f"Kandidaten außerhalb der Kategorie BUNDLE: {fremd}")
verschachtelt = q("""
    select pp.sku as mix, cp.sku as kind from bundle_components bc
    join products pp on pp.id = bc.parent_product_id
    join products cp on cp.id = bc.child_product_id
    where exists (select 1 from bundle_components x where x.parent_product_id = cp.id)""")
if verschachtelt:
    abbruch("Verschachtelte Stücklisten (der Tagesplan löst nur eine Ebene auf): "
            + ", ".join(f"{r['mix']}→{r['kind']}" for r in verschachtelt))
print("2) Vorbedingungen erfüllt: genau die 24 SKUs, alle BUNDLE, keine verschachtelte Stückliste")

ids = [r["id"] for r in kandidaten]
platz = ",".join("?" * len(ids))

# Nebenwirkung Beleg-PDF: line_desc_cell druckt bei is_bundle die Komponenten
# als graue Zusatzzeile. PDFs entstehen beim Abruf neu; die Rechnungsdaten
# bleiben unverändert.
rechnungen = q(f"""
    select i.invoice_number, i.status, i.sent_at, count(*) as positionen
    from invoices i join invoice_lines il on il.invoice_id = i.id
    where il.product_id in ({platz}) and i.status <> 'ENTWURF'
    group by i.id order by i.invoice_number""", *ids)
print(f"3) Festgeschriebene Rechnungen mit diesen Artikeln (PDF bekommt beim nächsten Abruf "
      f"eine graue Inhaltszeile je Mix-Position): {len(rechnungen)}")
for r in rechnungen:
    print(f"   {r['invoice_number']}  {r['status']}  versendet {r['sent_at']}  {r['positionen']} Pos.")

heute = date.today()
offen = q(f"""
    select o.order_number, o.status, o.requested_delivery_date as liefertag,
           coalesce(o.packing_date, date(o.requested_delivery_date, '-1 day')) as packtag,
           p.sku, l.quantity
    from orders o join order_lines l on l.order_id = o.id join products p on p.id = l.product_id
    where l.product_id in ({platz})
      and o.status in ('ENTWURF', 'BESTAETIGT', 'IN_PRODUKTION')
      and o.requested_delivery_date >= ?
    order by packtag, o.order_number""", *ids, heute.isoformat())
print(f"4) Offene Bestellungen ab {heute:%d.%m.} mit diesen Artikeln: {len(offen)}")
for r in offen:
    print(f"   Packtag {r['packtag']}  {r['order_number']}  {r['status']}  {r['sku']} × {r['quantity']}")

# Erwarteter Sortenbedarf nach APPLY für den nächsten Packtag mit Mixen (nur
# ENTWURF/BESTAETIGT, wie der Tagesplan) — zum Abgleich mit der Oberfläche.
packtage = sorted({r["packtag"] for r in offen
                   if r["status"] in ("ENTWURF", "BESTAETIGT") and r["packtag"] >= heute.isoformat()})
if packtage:
    tag = packtage[0]
    bedarf = q(f"""
        select cp.name as sorte, sum(l.quantity * bc.quantity) as menge
        from orders o join order_lines l on l.order_id = o.id
        join bundle_components bc on bc.parent_product_id = l.product_id
        join products cp on cp.id = bc.child_product_id
        where l.product_id in ({platz}) and o.status in ('ENTWURF', 'BESTAETIGT')
          and coalesce(o.packing_date, date(o.requested_delivery_date, '-1 day')) = ?
        group by cp.id order by cp.name""", *ids, tag)
    print(f"5) Erwarteter Sortenanteil aus Mixen am Packtag {tag} (ohne Einzelartikel):")
    for r in bedarf:
        print(f"   {r['sorte']}: {r['menge']:g}")
else:
    print(f"5) Kein offener Packtag ab {heute:%d.%m.} mit Mixen")

if not APPLY:
    print("TROCKENLAUF beendet — nichts geschrieben.")
    sys.exit(0)

jetzt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
con.execute("BEGIN IMMEDIATE")
cur = con.execute(f"""
    update products set is_bundle = 1, updated_at = ?
    where id in ({platz}) and coalesce(is_bundle, 0) = 0 and coalesce(is_variable_bundle, 0) = 0""",
    (jetzt, *ids))
if cur.rowcount != len(ERWARTET):
    con.execute("ROLLBACK")
    abbruch(f"{cur.rowcount} Zeilen statt {len(ERWARTET)} — zurückgerollt")
con.execute("COMMIT")
nachher = q(f"select sku, is_bundle, is_variable_bundle, updated_at from products where id in ({platz}) order by sku", *ids)
protokoll = {
    "runbook": "Paket 4 A-R1", "zeit_utc": jetzt, "geaendert": cur.rowcount,
    "feld": "products.is_bundle 0 -> 1",
    "artikel": [dict(r) for r in nachher],
}
print("APPLY: geschrieben", cur.rowcount)
print("PROTOKOLL", json.dumps(protokoll, ensure_ascii=False))
```

0. **Belege ablegen (Pflicht, vor dem Deploy, am besten sofort).** RE-2026-00001 und RE-2026-00005 sind festgeschrieben und versendet. Ihre PDF entsteht bei jedem Abruf neu aus den aktuellen Stammdaten (`pdf_service.line_desc_cell`). Sie ändert sich, sobald einer ihrer Mixe `is_bundle=1` trägt: nach A-R1, aber auch schon vorher, wenn Gernot nach dem Deploy einen dieser Mixe speichert (A.1 heilt beim Speichern), und schon heute kurzzeitig, wenn er eine Komponente hinzufügt (`add_bundle_component` setzt das Kennzeichen bis zum nächsten Speichern).
   - Im Browser als Admin in `minga`: Rechnungen → RE-2026-00001 → PDF, ebenso RE-2026-00005. Das ist ein reiner Abruf (`GET /api/v1/invoices/{id}/pdf`).
   - Dann lokal:

```bash
A=/tmp/minga-p4a-belege-$(date +%Y%m%d-%H%M%S); mkdir -p "$A"
mv ~/Downloads/RE-2026-00001*.pdf ~/Downloads/RE-2026-00005*.pdf "$A"/   # liegen sie im Belegordner (O), von dort nehmen
(cd "$A" && shasum -a 256 *.pdf | tee SHA256.txt)
scp -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes -r "$A" root@49.12.191.103:/root/backups/
p4ssh "ls -l /root/backups/$(basename "$A")"
```

   - Erwartet: zwei PDFs und `SHA256.txt` unter `/root/backups/minga-p4a-belege-…`.
   - **Aussagekraft:** Die Ablage hält den Stand vor Paket 4 fest, nicht sicher den versendeten. MG-12025 (auf RE-2026-00005) hat seit 08.10. 02:43:55 eine Stückliste, versendet wurde um 06:18:43. Ob `is_bundle` dazwischen 1 war (dann trug schon die versendete PDF die graue Zeile), zeigen die Daten nicht mehr, denn `updated_at` steht inzwischen auf 09.10. 11:32:25. Maßgeblich für die Akte bleibt die versendete PDF. Liegt sie Gernot im Postausgang vor, diese dazulegen.
1. **Trockenlauf (lesend).**

```bash
p4ssh 'C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1); docker exec -i "$C" python3 -' < /tmp/p4a-r1.py | tee /tmp/p4a-r1-trocken-$(date +%Y%m%d-%H%M%S).log
```

   Am 09.10.2026 mit genau diesem Befehl gelaufen, Ergebnis:
   - 24 Kandidaten (MG-11001 … MG-14005, alle BUNDLE, 1–6 Komponenten), Vorbedingungen erfüllt.
   - 2 festgeschriebene Rechnungen mit diesen Artikeln: RE-2026-00001 (OFFEN, versendet 08.10. 06:19, 2 Pos.) und RE-2026-00005 (OFFEN, versendet 08.10. 06:18, 5 Pos.).
   - 5 offene Positionen.
   - Packtag 11.10.: je 5 × Snackbox Amaranth, Erbse, Mizuna, Radieschen, Senf und Sonnenblume.
   - **Vor APPLY wiederholen.** Bricht er mit „Kandidaten weichen … ab“ ab, hat Gernot inzwischen Stücklisten gepflegt bzw. Mixe gespeichert (A.1 heilt beim Speichern). Dann `ERWARTET` auf den neuen Stand setzen und nur mit erneuter Freigabe weitermachen. Sind es 0 Kandidaten, ist nichts zu tun.
2. **Vorbedingung Deploy:** Paket 4 mit A.1 und A.2 ist live, Schritt 0 ist erledigt. Probe: In `abnahme` einen Mix speichern (Abnahme RA1), `is_bundle` bleibt 1. Ohne den Deploy setzt das nächste Speichern im alten Formular das Kennzeichen zurück.
3. **Freigabe einholen**, mit Nennung der Nebenwirkungen:
   - Sortenbedarf und Packliste zeigen Sorten statt Mixe.
   - Beleg-PDFs drucken unter jeder Mix-Position eine graue Inhaltszeile. Das gilt auch für den **erneuten Abruf** von RE-00001 und RE-00005. Deren Rechnungsdaten bleiben unverändert (GoBD), der Stand vor Paket 4 liegt aus Schritt 0 unter `/root/backups`, die versendeten PDFs liegen bei den Kunden.
   - Der Bestandsabzug bei „Geliefert“ bucht Komponenten statt des Mixes. Bei Einheit STK/Kisten wie bisher nur mit Warnung, ohne Gramm-Abzug.
   - Die Mixe tragen 📦 und fehlen in der Sortenauswahl variabler Bundles (es gibt keine).
4. **Backup (WAL-sicher), vor APPLY.** Das Skript läuft auf dem Server über `bash -s`. Darum steht `docker exec` hier **ohne** `-i`, sonst verschluckt es den Rest des Skripts.

```bash
p4ssh 'bash -s' <<'EOF'
set -e
C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)
ZIEL=/root/backups/minga-p4a-bundle-$(date +%Y%m%d-%H%M%S).db
docker exec "$C" python3 -c "import sqlite3; s=sqlite3.connect('file:/data/tenants/minga.db?mode=ro', uri=True); d=sqlite3.connect('/tmp/minga-backup.db'); s.backup(d); d.close(); print(sqlite3.connect('/tmp/minga-backup.db').execute('pragma integrity_check').fetchone())"
docker cp "$C":/tmp/minga-backup.db "$ZIEL"
docker exec "$C" rm -f /tmp/minga-backup.db
ls -l "$ZIEL"
EOF
```

   Erwartet: `('ok',)` und die Backup-Datei mit Größe.
5. **APPLY** (nur mit Freigabe):

```bash
LOG=/tmp/minga-p4a-bundle-$(date +%Y%m%d-%H%M%S).log
p4ssh 'C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1); docker exec -i "$C" python3 - APPLY' < /tmp/p4a-r1.py | tee "$LOG"
scp -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes "$LOG" root@49.12.191.103:/root/backups/
```

   - Erwartet: `APPLY: geschrieben 24` und eine Zeile `PROTOKOLL {…}` (Audit: Zeit, Feld, 24 Artikel mit neuem Stand). Das Log liegt danach lokal und unter `/root/backups` neben dem Backup.
   - Bei einer anderen Zahl rollt das Skript zurück und meldet `ABBRUCH`.
6. **Nachkontrolle (lesend):**

```bash
p4ssh 'C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1); docker exec -i "$C" python3 -' <<'EOF'
import sqlite3
c = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
print(c.execute("select count(*) from products p where coalesce(is_bundle,0)=0 and coalesce(is_variable_bundle,0)=0 and exists (select 1 from bundle_components bc where bc.parent_product_id=p.id)").fetchone()[0],
      c.execute("select count(*) from products where is_bundle=1").fetchone()[0])
EOF
```

   Erwartet: `0 25` (zweite Zahl größer, wenn Gernot inzwischen neue Mixe angelegt hat; vor APPLY am 09.10. gemessen: `24 1`). Danach RA2m und RA8m in `minga` (nur ansehen). **Rückweg:** Backup aus Schritt 4 zurückspielen (Wartungsfenster), oder gezielt `update products set is_bundle=0` für die 24 SKUs aus dem Protokoll. Das zweite nur mit Freigabe, denn danach wäre G11 wieder offen.

#### A-R2: Entwürfe mit vergangenem Liefertag (G13 Teil 1, G66, G80) — kein neues Runbook

Am 09.10. lesend bestätigt (`mode=ro`): **7 Entwürfe** mit Liefertag vor heute.
- BE-20260914-0001, BE-20260921-0001, BE-20260928-0001, BE-20261005-0001: LfA, „Abo-Lieferung: Unknown“, 4 × 2,00 €.
- BE-20260917-0002 (Klara Düran, 2 Pos.), BE-20260917-0003 (Bierbichler, die falsch erfasste Bestellung aus G80, soll storniert werden), BE-20261007-0001 (Gemüsebau Kiening, Lieferung 07.10., G66).

**Bezug zu A.3–A.5:** Der Tagesplan bietet für sie weder „Gepackt“ noch „Ausgeliefert“ an, und der Server lehnt beides ab (A-E3, Tests `test_vergangener_entwurf_*`). Ein versehentlicher Klick im Tagesplan eines vergangenen Tages kann sie also nicht mehr bestätigen oder liefern. Das Aufräumen muss deshalb nicht vor dem Deploy passieren. Offen bleibt der Weg über die Bestellliste („Bestätigen“, dann „Geliefert“): das ist bewusst die Büro-Entscheidung.

**Aufräumen:** nicht in A.
- Alle sieben: **R-B3** in Abschnitt B (je Bestellung FAKTURIERT oder STORNIERT, nach Gernots Antwort, mit Backup, Trockenlauf und Freigabe).
- Die vier LfA-Entwürfe hängen zusätzlich an **Runbook B, Schritt 7** aus `docs/superpowers/plans/2026-10-08-paket2-tagesplan-status.md` („### Runbook B: LfA-Entwürfe und Abo-Lauf (A5)“). Es wartet auf Gernots Antwort (geliefert/berechnet, Menge, Einheit, Preis).
- Bis dahin Gernot bitten, diese sieben in der Bestellliste nicht zu bestätigen (Frage 4).

### B — Abrechnung: Runbooks R-B1–R-B3 (kein Worker-Task; jede Schreibaktion nur mit Freigabe)

Zugriff wie immer: `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103`, `C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)`, Skripte per `docker exec -i "$C" python3 - < skript.py`.

**R-B1 — vor dem Deploy, nur lesend.** Prüft, dass B.1/B.2 in Prod nichts Bestehendes blockieren: keine Rechnung (gleich welcher Status) an einer `FAKTURIERT`-Bestellung, kein Rechnungsentwurf mit echter Nummer. Stand 09.10.: `0`, `0`.

```python
import sqlite3
c = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
print("Rechnungen an FAKTURIERT:", c.execute("""select count(*) from invoices i join orders o
  on (i.order_id = o.id or i.id in (select invoice_id from delivery_notes d where d.order_id = o.id))
  where o.status = 'FAKTURIERT'""").fetchone()[0])
print("Entwürfe mit echter Nummer:", c.execute("""select count(*) from invoices
  where status = 'ENTWURF' and invoice_number not like 'ENTWURF-%'""").fetchone()[0])
print("GELIEFERT ohne Lieferschein:", [r[0] for r in c.execute("""select order_number from orders o
  where status = 'GELIEFERT' and not exists (select 1 from delivery_notes d where d.order_id = o.id)
  order by order_number""")])
```

Erwartet: `0`, `0`, `['BE-20261007-0008', 'BE-20261008-0002']` (sortiert; `group_concat` ohne Sortierung lieferte am 09.10. die umgekehrte Reihenfolge, gemessen 09.10. mit dieser Abfrage, SQLite 3.46.1). Weicht eine der ersten beiden Zahlen ab: vor dem Deploy klären (betroffene Entwürfe ließen sich nach B.1 nicht mehr festschreiben bzw. bekämen beim Festschreiben das heutige Datum).

**R-B2 — nach dem Deploy und am 01.11.2026, nur lesend.** (0) **Gernot sagen** (Nachricht zum Deploy): „`BE-20261008-0002` (Dorint, Lieferung 08.10.) ist geliefert und noch nicht berechnet. Sie hat keinen Lieferschein und erscheint deshalb weder im Monatsdialog noch künftig automatisch. Bitte im Belegdialog der Bestellung „Rechnung aus Bestellung“ anlegen und festschreiben.“ Nach Abschnitt C steht sie bis dahin auf der Seite „Belegstatus“ unter „Rechnung fehlt“ (`OHNE_RECHNUNG`). Für die LfA-Abo-Lieferungen (KD-10022) dazu: „Ausgeliefert“ im Tagesplan erst nach Abschnitt A auch für Entwürfe, sonst vorher in der Bestellliste bestätigen (Offener Punkt 2). (1) Nach dem ersten „Ausgeliefert“ im Tagesplan: die Bestellung hat genau einen Lieferschein `ENTWURF` mit Liefertag. (2) Am 01.11. nach 06:30: `billing_runs` hat einen Lauf `MONAT_AUTO` für `2026-10` mit Status `FERTIG`; Monatsentwürfe (`invoices.batch_key = 'MONAT-2026-10'`) für jeden Monatskunden mit gelieferten Oktober-Bestellungen; im Dialog „Monatsrechnungen“ (Oktober) kein `OHNE_LIEFERSCHEIN` für Bestellungen im Status `GELIEFERT`. Die Altfälle aus R-B1 (`BE-20261008-0002`, Einzelkunde Dorint) bleiben ohne Lieferschein; sie werden nicht nachgezogen — Gernot berechnet `BE-20261008-0002` per „Rechnung aus Bestellung“ (geht ohne Lieferschein; Hinweis an ihn unter (0)). Vor Abschnitt A: Oktober-Bestellungen von KD-10022 im Status `ENTWURF` erscheinen in der dritten Abfrage und im Dialog unter `OHNE_LIEFERSCHEIN` — das ist dann erwartet (Offener Punkt 2), kein Fehler von B. **Keine Schreibaktion nötig.**

```python
import sqlite3
c = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
print(c.execute("select monat, art, status, gestartet_am, ergebnis from billing_runs order by gestartet_am desc limit 3").fetchall())
print(c.execute("""select c.customer_number, i.status, i.total from invoices i join customers c on c.id = i.customer_id
  where i.batch_key = 'MONAT-2026-10'""").fetchall())
print(c.execute("""select o.order_number, o.status, c.customer_number from orders o join customers c on c.id = o.customer_id
  where c.invoice_mode = 'MONATLICH' and coalesce(o.actual_delivery_date, o.requested_delivery_date) between '2026-10-01' and '2026-10-31'
  and not exists (select 1 from delivery_notes d where d.order_id = o.id) and o.status not in ('STORNIERT', 'FAKTURIERT')""").fetchall())
```

**R-B3 — Alt-Bestellentwürfe bis 07.10. (G66, Rest), Schreiben nur nach Gernots Antwort (Offener Punkt 1) und mit Freigabe.** Sieben Bestellungen stehen mit Liefertag bis 07.10. auf `ENTWURF`, ohne Rechnung und ohne Lieferschein: `BE-20260914-0001`, `BE-20260921-0001`, `BE-20260928-0001`, `BE-20261005-0001` (LfA, Abo), `BE-20260917-0002` (Klara Düran), `BE-20260917-0003` (Bierbichler), `BE-20261007-0001` (Gemüsebau Kiening, heute Monatskunde). Je Bestellung entscheidet Gernot: **geliefert und über DATEV abgerechnet** → `FAKTURIERT`; **nicht geliefert** → `STORNIERT`. Bewusst direkt in der Datenbank wie die Korrektur vom 09.10. (`BULK_STATUS_CHANGE`), nicht über `setze_status`: der Weg `ENTWURF → BESTAETIGT → GELIEFERT → FAKTURIERT` würde nach B.3 Lieferscheine anlegen und Bestand abbuchen. Ablauf: (1) WAL-sicheres Backup (Memory „NovaERP SSH + WAL-Backup“, Anlass `p4b-altentwuerfe`); (2) Trockenlauf; (3) mit Freigabe `APPLY`; (4) Trockenlauf erneut → „nichts zu tun“.

```python
# r_b3_altentwuerfe.py — Trockenlauf: python3 -   APPLY: python3 - APPLY
import json, sqlite3, sys, uuid
from datetime import datetime, timezone
ZIEL = {  # nach Gernots Antwort füllen, z. B. "BE-20260917-0002": "STORNIERT"
}
GRUND = {"FAKTURIERT": "Über DATEV abgerechnet (Altbestand bis 07.10.2026, Auskunft Gernot <Datum>)",
         "STORNIERT": "Nie geliefert (Altentwurf bis 07.10.2026, Auskunft Gernot <Datum>)"}
APPLY = sys.argv[1:] == ["APPLY"]
c = sqlite3.connect("/data/tenants/minga.db" if APPLY else "file:/data/tenants/minga.db?mode=ro", uri=not APPLY)
c.execute("pragma busy_timeout = 5000")
jetzt = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
todo = []
for nummer, ziel in ZIEL.items():
    assert ziel in GRUND, ziel
    row = c.execute("select id, status, requested_delivery_date from orders where order_number = ?", (nummer,)).fetchone()
    assert row, f"{nummer} fehlt"
    oid, status, tag = row
    if status == ziel:
        continue
    assert status == "ENTWURF", f"{nummer}: Status {status}, erwartet ENTWURF"
    assert tag <= "2026-10-07", f"{nummer}: Liefertag {tag}"
    assert c.execute("select count(*) from invoices where order_id = ?", (oid,)).fetchone()[0] == 0, f"{nummer}: Rechnung vorhanden"
    assert c.execute("select count(*) from delivery_notes where order_id = ?", (oid,)).fetchone()[0] == 0, f"{nummer}: Lieferschein vorhanden"
    todo.append((nummer, oid, ziel))
print("Änderungen:", [(n, z) for n, _, z in todo] or "nichts zu tun")
if APPLY and todo:
    with c:
        for nummer, oid, ziel in todo:
            c.execute("update orders set status = ?, updated_at = ? where id = ? and status = 'ENTWURF'", (ziel, jetzt, oid))
            c.execute("""insert into order_audit_logs (id, order_id, action, old_values, new_values, user_name, created_at, reason)
                         values (?, ?, 'BULK_STATUS_CHANGE', ?, ?, 'systemkorrektur', ?, ?)""",
                      (uuid.uuid4().hex, oid, json.dumps({"status": "ENTWURF"}), json.dumps({"status": ziel}), jetzt, GRUND[ziel]))
    print("geschrieben:", len(todo))
```

Danach lesend: `select order_number, status from orders where order_number in (…)` und je ein Audit-Eintrag `BULK_STATUS_CHANGE`. Die LfA-Abo-Bestellungen ab 12.10. betrifft das nicht (Offener Punkt 2). Geprüft gegen eine Probe-Datenbank mit dem Schema aus den Modellen (`/tmp/p4b-rb3`): Trockenlauf listet, `APPLY` schreibt Status, `updated_at` und je einen Audit-Eintrag, zweiter Trockenlauf „nichts zu tun“.

### C — Belegstatus und Dateinamen: Runbooks R-C0–R-C3 (nur mit Freigabe; kein Worker-Task)

**R-C0 — Datenkorrekturen: keine.**
- Belegstatus und Dateinamen leiten alles aus vorhandenen Daten ab.
- Der FAKTURIERT-Altbestand (574 Bestellungen) bleibt, wie er ist, und erscheint als „extern (DATEV)“.
- Die fünf unvollständigen Bestellungen vom 09.10. bearbeitet Gernot im Belege-Dialog: Rechnung anlegen bzw. versenden. Das ist seine Entscheidung, keine Korrektur durch uns.
- Festgeschriebene Rechnungen werden nicht angefasst (GoBD). Ihr Dateiname kommt aus dem eingefrorenen Empfänger.

**R-C1 — Vor dem Deploy (lesend, kein Backup nötig): Erwartung festhalten.**
```bash
ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 -o BatchMode=yes root@49.12.191.103 'C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1); docker exec -i "$C" python3 - <JJJJ-MM-TT des Abnahmetags>' < /tmp/p4-c-runbook/belegstatus-erwartung.py
```
Das Skript (`/tmp/p4-c-runbook/belegstatus-erwartung.py`, Inhalt unten, byte-gleich) öffnet nur `mode=ro` und bildet die Regeln aus C-E3/C-E4 in SQL nach, auch „Storno schließt extern aus“. Gemessen am 09.10.2026, in der Revision mit der Storno-Regel erneut gemessen, gleiche Ausgabe:
```
Stichtag 2026-10-09: 596 Bestellungen ohne Storno, extern abgerechnet 574, unvollständig 5
2026-10-09 | BE-20261008-0006 | Ferdinand Bierbichler GmbH & Co. KG | EINZELN | OHNE_RECHNUNG | - | LS-20261009-0001
2026-10-08 | BE-20261008-0002 | Dorint Hotels Betriebs GmbH | EINZELN | OHNE_RECHNUNG | - | -
2026-10-08 | BE-20261007-0005 | Ökoring Handels GmbH | EINZELN | NICHT_VERSENDET | RE-2026-00010 | LS-20261007-0003
2026-10-08 | BE-20261007-0004 | Großer Kern GmbH | EINZELN | NICHT_VERSENDET | RE-2026-00008 | LS-20261007-0004
2026-10-08 | BE-20261007-0003 | Naturkostinsel gmbh & co. kg | EINZELN | OHNE_RECHNUNG | - | LS-20261007-0005
```

Inhalt von `/tmp/p4-c-runbook/belegstatus-erwartung.py` (nur lesend):

```python
# Paket 4, C — Manager-Abnahme: erwartete unvollständige Bestellungen in minga,
# nur lesend (mode=ro), dieselben Regeln wie app/services/belegstatus.py.
# Lauf: docker exec -i "$C" python3 - [JJJJ-MM-TT] < belegstatus-erwartung.py
import sqlite3, sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

heute = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(ZoneInfo("Europe/Berlin")).date()
c = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
q = lambda s, *a: c.execute(s, a).fetchall()

auftraege = q("""select o.id, o.order_number, o.status, coalesce(o.actual_delivery_date, o.requested_delivery_date),
                        cu.invoice_mode, cu.name
                 from orders o left join customers cu on cu.id = o.customer_id
                 where o.status != 'STORNIERT'""")
ls = {}
for order_id, nummer, status in q("select order_id, delivery_note_number, status from delivery_notes"):
    ls.setdefault(order_id, []).append((nummer, status))
aktiv = "i.invoice_type = 'RECHNUNG' and i.status != 'STORNIERT'"
re = {}
for order_id, inv_id, nummer, status, sent_at in q(f"""
        select i.order_id, i.id, i.invoice_number, i.status, i.sent_at from invoices i where i.order_id is not null and {aktiv}
        union
        select d.order_id, i.id, i.invoice_number, i.status, i.sent_at from delivery_notes d join invoices i on i.id = d.invoice_id where {aktiv}"""):
    re.setdefault(order_id, {})[inv_id] = (nummer, status, sent_at)
protokoll = dict(q("select invoice_id, min(sent_at) from document_dispatches where invoice_id is not null group by invoice_id"))
# Bestellungen mit stornierter Rechnung sind nie „extern“ (der Storno setzt FAKTURIERT nicht zurück)
storniert = {r[0] for r in q("""select distinct order_id from invoices
                                where order_id is not null and invoice_type = 'RECHNUNG' and status = 'STORNIERT'""")}

extern = luecken = 0
zeilen = []
for oid, nr, status, tag, modus, kunde in auftraege:
    tag = date.fromisoformat(tag[:10])
    kandidaten = sorted(re.get(oid, {}).items(), key=lambda kv: (kv[1][1] == "ENTWURF", kv[1][0]))
    rechnung = kandidaten[0] if kandidaten else None
    if rechnung is None and status == "FAKTURIERT" and oid not in storniert:
        extern += 1
        continue
    geliefert = (status in ("GELIEFERT", "FAKTURIERT") or any(s == "GELIEFERT" for _, s in ls.get(oid, []))
                 or (status in ("BESTAETIGT", "IN_PRODUKTION") and tag < heute))
    faellig = tag if modus != "MONATLICH" else (tag.replace(day=1) + timedelta(days=32)).replace(day=1)
    if not geliefert or heute < faellig:
        continue
    if rechnung is None:
        grund = "OHNE_RECHNUNG"
    elif rechnung[1][1] == "ENTWURF":
        grund = "RECHNUNG_ENTWURF"
    elif not (rechnung[1][2] or protokoll.get(rechnung[0])):
        grund = "NICHT_VERSENDET"
    else:
        continue
    zeilen.append((tag.isoformat(), nr, kunde, modus, grund, rechnung[1][0] if rechnung else "-",
                   ",".join(n for n, _ in ls.get(oid, [])) or "-"))
print(f"Stichtag {heute}: {len(auftraege)} Bestellungen ohne Storno, extern abgerechnet {extern}, unvollständig {len(zeilen)}")
for z in sorted(zeilen, reverse=True):
    print(" | ".join(z))
```

**R-C2 — Nach dem Deploy: Abnahme im Browser** (`minga.novaerp.de`, Rolle Admin; nichts versenden, nichts anlegen):
1. Die Navigation „Vertrieb“ zeigt „Belegstatus“ direkt unter „Rechnungen“. Die Vorgabe ist Liefertag von = 1. des Vormonats. Die Schnellsuche („Suchen… Strg+K“, Eingabe „beleg“) bietet „Belegstatus“ an.
1a. **Zeitraum per Tastatur verdreht:** „bis“ auf den 01.10. tippen, „von“ auf den 09.10. Erwartet sind „„von“ liegt nach „bis““ am Feld und „Zeitraum ungültig“ in der Karte, ohne Zeilen. Die Filter bleiben stehen. „von“ zurück auf den 01.10. setzen: Die Liste lädt wieder, ohne die Seite neu zu laden.
2. „Nur unvollständige (n)“: Das n und die Zeilen stimmen mit R-C1 am selben Tag überein.
3. Die Spalten zeigen ✔/✘/◐/—. FAKTURIERT-Bestellungen aus dem August zeigen „extern (DATEV)“, wenn man „von“ auf den 01.08. setzt.
4. Ein Monatskunde (BE-20261007-0006) zeigt „Monatsrechnung ab 01.11.2026“ und ist nicht unvollständig.
5. Der Filter Kunde (Combobox) wirkt. Ab 51 Zeilen gibt es Seiten.
6. „Belege“ öffnet den Belege-Dialog der Bestellung. „Schließen“ lädt die Liste neu.
7. **Dateiname:** Im Belege-Dialog von BE-20261007-0004 das LS-PDF und die Rechnung herunterladen. Erwartet: `LS-20261007-0004_Grosser-Kern-GmbH.pdf` und `RE-2026-00008_Grosser-Kern-GmbH.pdf`. Mit Belegordner (O) liegt die Datei unter `Belege/Lieferscheine/2026-10/…`.
8. **Rechte:** Als Buchhaltung bzw. Vertrieb ist die Seite sichtbar. Als Planung oder Halle fehlt der Navigationspunkt, und ein direkter Aufruf von `/belegstatus` zeigt „Keine Berechtigung für den Belegstatus“.

**R-C3 — Nachricht an Gernot (Vorschlag):**
> **Neu: Belegstatus** (Vertrieb → Belegstatus). Je Bestellung siehst du, ob Lieferschein und Rechnung da sind, ob die Rechnung versendet und ob sie bezahlt ist. Du kannst nach Zeitraum, Kunde und „nur unvollständige“ filtern. Unvollständig heißt: geliefert, aber ohne Rechnung, nur als Entwurf oder nicht versendet. Bei Monatskunden gilt das ab dem 1. des Folgemonats. Bestellungen, die vor NovaERP über DATEV abgerechnet wurden, stehen als „extern (DATEV)“ da. Heute sind es 5 offene: drei gelieferte Bestellungen ohne Rechnung (Naturkostinsel, Dorint, Bierbichler) und zwei Rechnungen, die noch nicht versendet sind (RE-2026-00008 Großer Kern, RE-2026-00010 Ökoring). Über „Belege“ kommst du direkt in den Belege-Dialog der Bestellung.
> **Dateinamen:** PDFs heißen jetzt `Belegnummer_Kunde.pdf`, z. B. `LS-20261008-0001_Fruchthof-Nagel-GmbH.pdf`. Das gilt beim Download und im Mailanhang, für Lieferschein, Rechnung, Sammelrechnung, Auftragsbestätigung und Packliste. Umlaute werden umgeschrieben (Ökoring → Oekoring), Leer- und Sonderzeichen werden „-“, Länge höchstens 50 Zeichen. Hast du einen Beleg schon vorher in deinen Belegordner gespeichert, liegt er dort unter dem alten Namen. Ein neuer Download legt die neue Datei einmalig daneben.

### P4-D — Rechte der Rolle Produktion

#### Oberfläche (RF-D1–RF-D5, lokal; kein Worker-Task)

**Aufbau lokal**, Muster der Paket-3-Abnahme:
- Backend:
  ```bash
  cd backend && AUTH_DISABLED=true DEV_ROLES=<rolle> TENANTS_DIR=/tmp/p4-d-abnahme/tenants DEFAULT_TENANTS=dev REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python /tmp/paket3/q4work/run_backend.py 8104
  ```
  Der Starter liegt noch unter `/tmp/paket3/q4work/run_backend.py`.
- Frontend:
  ```bash
  cd frontend && VITE_AUTH_DISABLED=true VITE_DEV_ROLES=<rolle> VITE_API_URL=http://localhost:8104 ./node_modules/.bin/vite --port 5173 --strictPort
  ```
- Testdaten erst mit leerem `DEV_ROLES` anlegen: einen Kunden mit E-Mail, Rabatt, Zahlungsziel 30 Tage, Pfandabrechnung monatlich, Lieferadresse, Ansprechpartner und einem Sonderpreis. Ohne E-Mail scheitert das Speichern im Formular für alle Rollen (I-D5). Danach je Rolle neu starten.

- **RF-D1 (`production_staff`):** Kopfknopf „Suchen… Strg+K“ → „Kunden“. Die Kundenseite öffnet sich (E-D7).
  - Die Kundenkarten haben keinen Sonderpreis-Knopf und keinen Leergut-Knopf. Im Kopf steht „Neuer Kunde“, aber kein Excel-Import.
  - „Details“ zeigt kein Zahlungsziel und keinen Konditionsblock. Aktiv, Haupt-E-Mail und die drei Empfängerlisten sind gesperrt und tragen Hinweise.
  - Eine neue Telefonnummer speichern geht („Kunde aktualisiert“). Im Netzwerk-Tab enthält der `PATCH`-Body keines der 11 Konditionsfelder, und die Antwort trägt `payment_terms: null`.
  - Adresse und Ansprechpartner hinzufügen geht. Einen Papierkorb gibt es nicht.
  - „Neuer Kunde“ mit Name und E-Mail anlegen geht. Der `POST`-Body enthält keine Konditionen. Danach als Admin geprüft: Der Kunde hat `NET_14`, Rabatt 0, `JE_LIEFERUNG` und `EINZELN`.
  - Ein Kunde mit Zahlungsziel 30 Tage aus den Testdaten behält es nach dem Speichern durch die Halle (Admin-Ansicht).
- **RF-D2 (`production_staff`):** Ablauf Bestellungen → „Neue Bestellung“.
  - Der Kunde steht in der Auswahl. Der Sonderpreis wird vorbelegt. Speichern geht.
  - Im Belege-Dialog die AB anlegen. „Versenden“ ist mit den Empfängern des Kunden vorbelegt.
  - Lieferschein, Packliste im Tagesplan.
  - Im Netzwerk-Tab: Die Antwort von `GET /api/v1/sales/customers` trägt `payment_terms: null`, `discount_percent: null` usw.
- **RF-D3 (`production_planner`):** `/customers` öffnen (Strg+K → „Kunden“), Kunden bearbeiten.
  - Zahlungsziel, Rabatt, Skonto, Skontofrist, Verpackungsgebühr, Pfandabrechnung, Abrechnung und Aktiv sind gesperrt und tragen die Hinweise. „Preise auf Lieferschein andrucken“, Haupt-E-Mail und Empfänger bleiben änderbar.
  - Eine neue Telefonnummer speichern geht.
  - Der Papierkorb bei Adresse und Ansprechpartner ist da, Löschen geht. Sonderpreis-Knopf und Excel-Import sind da.
- **RF-D4 (`admin`, `sales`, `accounting`):** Kundenseite wie vorher, mit Sonderpreis-, Leergut-Knopf und Excel-Import. Konditionen und Aktiv sind änderbar. Deaktivieren und Reaktivieren gehen.
- **RF-D5:** Admin → Benutzerverwaltung → Rollentext „Produktion“ lautet: „Der Mitarbeiter-Login. Tagesplan, Aussaat, Ernten und Lagerbuchungen; Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen; Kunden anlegen und ändern, ohne Konditionen und ohne Löschen. Kein Zugriff auf Rechnungen, DATEV, Preislisten, Auswertungen und Einstellungen.“

#### Runbooks R-D0–R-D2 (Produktion; jede Schreibaktion nur mit Freigabe)

- **R-D0 — Keine Datenkorrektur nötig.**
  - Der Abschnitt ändert weder Schema noch Daten (kein `_auto_migrate`).
  - Lesend am 09.10. geprüft (`/tmp/p4-d-tools/prod_lesen.py`, `mode=ro`): `benutzer_audit` hat 0 Zeilen. Über die Benutzerverwaltung (B8) ist also noch kein Mitarbeiter-Login entstanden. Konten, die vorher direkt in Keycloak angelegt wurden, erfasst die Tabelle nicht.
  - 46 Kunden, davon 8 inaktiv, 0 Adressen, 4 Ansprechpartner. Für die 8 inaktiven Kunden gibt es keine Hinweise auf Mitarbeiter-Logins. Wer sie deaktiviert hat, speichert das System nicht, das Skript fragt es auch nicht ab. Eine Korrektur ist ohnehin nicht nötig: Deaktivieren lässt sich zurücknehmen, und P4-D ändert keine Daten.
  - Festgeschriebene Rechnungen sind nicht betroffen (GoBD).
- **R-D1 — Nach dem Deploy, lesend.** Prüfen, ob die Live-OpenAPI die neue Form trägt:
  ```bash
  curl -s https://minga.novaerp.de/openapi.json | jq '.components.schemas.CustomerResponse.properties.payment_terms'
  ```
  Erwartet: ein `anyOf` mit `{"type": "null"}`. Wenn die OpenAPI live nicht offen ist: entfällt. Dazu das Startlog des neuen Containers ohne Fehler, der Containername wechselt je Deploy.
- **R-D2 — Rechte live prüfen (nur mit Freigabe; schreibt in Keycloak und `benutzer_audit`).** Empfohlen ist **Weg 1**: Gernot meldet sich mit seinem ersten echten Mitarbeiter-Login an und prüft den lesenden Teil von RF-D1 und RF-D2. So entsteht kein Testbenutzer in Produktion. Er braucht dazu nur lesende Schritte: Strg+K → „Kunden“, einen Kunden über „Details“ öffnen und ohne Speichern schließen, das Bestellformular öffnen und ohne Speichern schließen. **Weg 2** (Manager):
  1. In Admin → Benutzerverwaltung einen Benutzer „P4 Test Produktion“ mit Rolle Produktion anlegen.
  2. Nur lesend prüfen. Die Kundenseite (Strg+K → „Kunden“) zeigt keine Konditionen, keinen Sonderpreis-Knopf und keinen Papierkorb. Im Netzwerk-Tab stehen die Konditionen auf `null`, und `GET …/customers/{id}/prices` gibt 403. **Nichts** speichern, keine Bestellung, nichts löschen.
  3. Den Benutzer sofort deaktivieren.
  4. Die zwei Zeilen in `benutzer_audit` (anlegen, deaktivieren) im Abnahmeprotokoll nennen.

## Offene Punkte

Die Nummern gelten je Abschnitt: „Offener Punkt n“ bzw. „Frage n“ im Text eines Abschnitts meint dessen Liste hier.

### Fragen an Gernot — gebündelt für eine Nachricht (Manager-Abnahme, Schritt 7)

Mehrere Abschnitte stellen dieselbe Frage; sie geht **einmal** hinaus:
1. **Entwürfe im Tagesplan** (A Frage 1 = B Offener Punkt 2): „Gepackt“/„Ausgeliefert“ bestätigt einen Entwurf bis zu seinem Liefertag — passt das, oder sollen Entwürfe immer erst im Büro bestätigt werden? Dazu: Werden die LfA-Abo-Lieferungen tatsächlich ausgeliefert?
2. **Sieben Alt-Entwürfe mit Liefertag bis 07.10.** (A Frage 4 = B Offener Punkt 1 = C Offener Punkt 3; Runbook R-B3): je Bestellung „geliefert und über DATEV abgerechnet“ oder „nicht geliefert“; für die vier LfA-Entwürfe die Angaben aus Runbook B von Paket 2. Bis zur Antwort in der Bestellliste nicht bestätigen.
3. **Kisten und Mix-Snackboxen im Sortenbedarf** (A Frage 2), **Gastrotray und Gastrokisten** (A Frage 3).
4. **Lieferschein ohne Quittung** (B Offener Punkt 3); Hinweise B Offener Punkt 7 (BE-20261008-0002 von Hand berechnen, Text R-B2 (0)) und 8 (Menge in Sammelrechnungen).
5. **Belegstatus und Dateinamen** (C Offene Punkte 1, 2, 4, 5, 6, 7; Nachricht R-C3).
6. **Rechte der Mitarbeiter** (P4-D F-D1–F-D5; F-D1 blockiert den Deploy nicht).

### A — Tagesplan und Produktion

**Fragen an Gernot**

1. **Gepackt bestätigt Entwürfe (G10, A-E3):** „Wenn du im Tagesplan bei einer Bestellung, die noch Entwurf ist, auf ‚Gepackt‘ oder ‚Ausgeliefert‘ klickst, gilt sie damit auch als bestätigt. Im Verlauf der Bestellung steht dann ‚Beim Packen im Tagesplan bestätigt‘. Das geht bis zum Liefertag; Entwürfe, deren Liefertag vorbei ist, musst du in der Bestellliste bestätigen oder stornieren. Passt das so, oder sollen Entwürfe immer erst im Büro bestätigt werden?“ Ist er dagegen, schaltet eine Ein-Zeilen-Änderung im Tagesplan die Bestätigung ab (A-E3).
2. **Kisten und Mix-Snackboxen im Sortenbedarf (G11, G74):**
   - **Kisten:** Die 39 Artikel „BIO Kiste | X (VPE 6)“ bzw. „(VPE 12)“ (z. B. „BIO Kiste | Erbse (VPE 6)“) stehen im Sortenbedarf als „1 Kiste“, nicht als 6 Snackboxen. Zu jeder gibt es namensgleich eine „BIO Snackbox | X“. Frage: „Ist eine ‚BIO Kiste | Erbse (VPE 6)‘ genau 6 × ‚BIO Snackbox | Erbse‘? Dann hinterlegen wir das für alle 39 Kisten, und im Sortenbedarf erscheinen Snackboxen.“ Bei Ja folgt Paket 5, mit Runbook (Stückliste je Kiste) und Formular (Stückliste auch außerhalb der Kategorie BUNDLE sichtbar).
   - **Snackbox Brotzeitmix und Salatmix:** MG-10005 „BIO Snackbox | Brotzeitmix“ und MG-10020 „BIO Snackbox | Salatmix“ (Kategorie MICROGREEN, ohne Stückliste; dazu die Kisten MG-11019, MG-11034, MG-12004, MG-12019) stehen im Sortenbedarf als eine Sorte. Im Saatgut gibt es „Brotzeitmix“ und „Salatmix“ als je eine Sorte. Frage: „Wächst die Brotzeitmix- bzw. Salatmix-Schale aus einer fertigen Saatgutmischung in einer Schale? Dann bleibt sie im Sortenbedarf eine Sorte, und es ist nichts zu tun. Oder stellst du sie beim Packen aus mehreren Sorten zusammen? Dann bekommt sie eine Stückliste wie die Mixe.“ Bei „zusammengestellt“: Stückliste im Produktformular (nach dem Deploy wirksam) bzw. Paket 5 für die Kisten.
3. **Gastrotray und Gastrokisten (G13, G11):**
   - **Gastrotray:** „Was liegt im ‚BIO Gastrotray (1-8 Sorten)‘ für Staatsministerium (5 Stück, Montag), Dorint (4, Donnerstag) und LfA (4, Montag)? Immer dieselben Sorten je Kunde?“ Bei festen Sorten je Kunde sind Abo-Positionen je Sorte möglich (B6, live). Offen ist dabei die Preisfrage. Bei wechselnden Sorten: Sortenauswahl am Abo (neues Feature).
   - **Gastrokisten Erbse, Radieschen und Rettich (MG-14002–14004):** Wie bei „Gastrokiste Brotzeitmix“ (15 × Snackbox) kann Gernot die Stückliste selbst im Produktformular anlegen. Nach dem Deploy bleibt sie wirksam.
4. **Sieben Entwürfe mit vergangenem Liefertag (A-R2):** dieselbe Frage wie Abschnitt B, Offener Punkt 1 (R-B3), nur einmal stellen: je Bestellung „geliefert und über DATEV abgerechnet“ oder „nicht geliefert“. Dazu für die vier LfA-Entwürfe die Angaben aus Runbook B (Paket 2). Bis zur Antwort: diese sieben in der Bestellliste nicht bestätigen. Im Tagesplan sind sie nach Paket 4 gesperrt.

**Intern (Manager)**

5. **Belege werden live gerendert:** `pdf_service.line_desc_cell` liest beim PDF-Abruf die aktuellen Stammdaten (Bundle-Inhalt, Sorte, GTIN). Jede Stammdatenänderung ändert die erneut abgerufene PDF festgeschriebener Rechnungen, nicht nur A-R1. Abhilfe ist eine PDF-Ablage beim Festschreiben (eigenes Paket).
6. **Einheiten in Bestellungen** sind uneinheitlich (`STK`, `Stück`, `Kisten`; Prod: 729 Positionen mit Mixen in „Kisten“, 117 in STK/Stück). Der Sortenbedarf zeigt deshalb keine Einheit (A-E6). Das ist ein Stammdatenthema mit Gernot.
7. **Variable Bundles ohne Sortenauswahl** fallen weiter still aus dem Sortenbedarf (Kritik G11). In Produktion gibt es keine variablen Bundles, Import und Abo-Lauf lassen sie ohne Auswahl nicht zu. Nicht in A.
8. **Ein Mix, dessen letzte Komponente entfernt wird,** behält `is_bundle=1` (Bestand). Im Packplan zählt er dann als Einzelartikel, der Bestandsabzug meldet „hat keine Komponenten konfiguriert“. Nicht in A.
9. **Zwei API-Wege bestätigen ohne `bestaetigen`:** `POST /sales/orders/{id}/status` mit `status=BESTAETIGT` und `POST /sales/orders/bulk-status` setzen ENTWURF → BESTAETIGT über das bloße `setze_status`: ohne Prüfung „ohne Positionen“, ohne `confirmed_delivery_date`, Audit STATUS_CHANGE bzw. BULK_STATUS_CHANGE statt CONFIRM. Die Oberfläche nutzt sie für Entwürfe nicht (A-E3). Keine Regression. Wer sie angleichen will: BESTAETIGT aus ENTWURF in beiden Endpunkten über `bestaetigen` führen, mit eigenen Tests für die geänderten Antworten. Eigenes kleines Paket.

### B — Abrechnung (Fragen an Gernot bzw. Manager)

1. **(Gernot) Sieben Bestellentwürfe bis 07.10.** (Liste in R-B3): je Bestellung „geliefert und über DATEV abgerechnet“ oder „nicht geliefert“? Bis zur Antwort bleiben sie `ENTWURF`; der Monatsdialog September/Oktober meldet sie unter `OHNE_LIEFERSCHEIN`.
2. **(Gernot; Paket-4-Abschnitt A, G10) Abo-Bestellungen entstehen als Entwurf.** Der Abo-Lauf legt `ENTWURF` an (`subscription_tasks`); für Entwürfe zeigt der Tagesplan kein „Ausgeliefert“, und `ENTWURF → GELIEFERT` ist nicht erlaubt. **Abschnitt A (A.3–A.5)** schließt den Weg: „Ausgeliefert“ bestätigt den Entwurf im selben Schritt (`setze_status_im_tagesplan` → `bestaetigen` + `setze_status`), B.3 legt dabei den Lieferschein an (gemessen mit A + B, Prüfstand). Ohne A führen erst „Bestätigen“ in der Bestellliste und dann „Ausgeliefert“ über B.3 in den Monatslauf. Die LfA-Bestellungen (KD-10022, montags) stehen seit 14.09. unbestätigt (4 × `ENTWURF`, Prod 09.10.); KD-10012 hat seit 01.09. keine Bestellung. Ohne A **und** „Ausgeliefert“ fehlen sie am 01.11. in der Monatsrechnung (nur Hinweis `OHNE_LIEFERSCHEIN`). Frage an Gernot: Werden die LfA-Lieferungen tatsächlich ausgeliefert? A's Frage 1 (Entwurf beim Ausliefern bestätigen) entscheidet den Weg.
3. **(Gernot) Lieferschein ohne Quittung.** Der beim Ausliefern angelegte Lieferschein ist ein Entwurf; der Monatsdialog meldet ihn unter „ohne Quittung — abgerechnet wird die Bestellmenge“. Für Gernot ohne Teillieferungen richtig; stört der Hinweis, wäre „Ausgeliefert = quittiert“ eine spätere Entscheidung (Lieferschein dann gesperrt, Unterschrift leer).
4. **(Manager) Suche nur in den 100 neuesten Rechnungen.** Reicht bis etwa Rechnung 100 (heute 10). Danach Serversuche (`GET /invoices?suche=`) — eigener Punkt, nicht in B.
5. **(Manager) Übersicht „geliefert, nicht berechnet“ (G14)** für Einzelkunden: B macht **künftige** Lieferungen (mit Lieferschein aus B.3) im Monatsdialog als `EINZELABRECHNUNG` sichtbar; Altfälle ohne Lieferschein wie `BE-20261008-0002` nicht. Die Übersicht je Bestellung ist Abschnitt C (Seite „Belegstatus“, C.3 `OHNE_RECHNUNG`), nicht B.
6. **(Manager) Nachspiel auf dem gemergten Stand:** B ist auf `bd56901` (D/F/O vollständig) und in der Überarbeitung auf `1bfa032` (mit den Nachbesserungen D/F) nachgespielt; der endgültige Merge-Stand von `feat/nachtrag-0910` (nach Nachtrag-Task 17 und Manager-Abnahme) kann davon abweichen — Anker dann mit den Ausgangsständen in „Vorbereitung (vor Task 1)“ prüfen; Gesamtnachspiel: Manager-Abnahme, Schritt 0.
7. **(Gernot, Info) `BE-20261008-0002` von Hand berechnen.** Geliefert 08.10., Einzelkunde Dorint, ohne Lieferschein und ohne Rechnung. B.3 wirkt nur auf künftige „Ausgeliefert“; der Monatsdialog zeigt die Bestellung nicht. Weg: Belegdialog → „Rechnung aus Bestellung“ → festschreiben. Sichtbar als Lücke erst mit Abschnitt C (Belegstatus, „Rechnung fehlt“). Text an Gernot: R-B2 (0).
8. **(Gernot, Info) Menge in Monats- und Sammelrechnungen** (B-E6): Preis, Löschen und Hinzufügen gehen im Entwurf direkt; eine andere **Menge** einer zusammengefassten Position nicht — der Entwurf zeigt dann „Entwurf verwerfen, Menge in der Bestellung korrigieren, Lauf neu starten“. In Rechnungen aus einer Bestellung geht auch die Menge direkt.

### C — Belegstatus und Dateinamen

**Für Gernot:**
1. **Fehlender Lieferschein als Lücke?** Heute zeigt die Spalte „Lieferschein“ ein graues ✘, und die Bestellung gilt deshalb nicht als unvollständig (C-E6). Soll ein fehlender Lieferschein bei gelieferten Bestellungen auch unter „nur unvollständige“ fallen? In Prod ist BE-20261007-0008 so ein Fall: Rechnung versendet, kein LS.
2. **AB und Packliste mit Kundennamen?** Gewünscht hast du LS, RE und Sammelrechnung. Wir haben AB und Packliste gleich mitgezogen (C-E10). Passt das, oder sollen die beiden nur die Nummer tragen?
3. **Alte Bestellentwürfe:** 7 Bestellungen stehen mit Liefertag vor heute noch auf „Entwurf“ (14.09.–07.10., meist Abo-Entwürfe von Monatskunden, z. B. BE-20260914-0001). Sie zählen nicht als geliefert. Sind sie geliefert worden? Dann bestätigen bzw. quittieren, sonst stornieren.
4. **Umlaute im Dateinamen:** `Ökoring` wird `Oekoring`, `Großer Kern` wird `Grosser-Kern`. Lieber Umlaute behalten? Der Preis wäre, dass ZIP-Archive aus Windows und manche Mailprogramme die Namen verstümmeln (C-E8).
5. **Rechnung „als versendet markieren“ ohne Mail** (Post, persönliche Übergabe): Für Rechnungen gibt es das nicht, nur für AB und Lieferschein. Solche Rechnungen bleiben im Belegstatus „nicht versendet“. Brauchst du das? Der Belegstatus zählt einen solchen Protokolleintrag schon als versendet (C-E4). Fehlen würden der Knopf und der Endpunkt.
6. **Automatisch eine Rechnung je Lieferung** für Einzelkunden (X07): zum Beispiel ein Rechnungsentwurf, sobald der Lieferschein quittiert ist? Heute macht der Belegstatus die Lücke nur sichtbar.
7. **Mahnung, DATEV-, SEPA-Dateien:** Sie heißen weiter `Zahlungserinnerung_<Nr>_Stufe<n>.pdf`, `DATEV_Export_<von>_<bis>.csv` und `Lastschrift-Einreichung_<Tag>.csv`, ohne Kunden. Die Exporte betreffen mehrere Kunden. Soll die Mahnung den Kunden tragen?

**Intern (Manager):**
8. **Vorbedingung V-C1 — erledigt im Gesamtplan** (Global Constraints, „Bestehende Tests“, mit Tasknummern). Ursprünglicher Text: C.2 Step 6 ändert 11 Erwartungen in `tests/test_gernot_261008_paket3.py`. Abschnitt A schreibt im Hinweis für Worker „Bestehende Tests ändert kein Task“. B und D nennen ihre Ausnahmen nur im eigenen Abschnitt. In die Global Constraints von Paket 4 gehört deshalb wörtlich:
   > **Bestehende Tests** ändert kein Task, mit genau diesen Ausnahmen: B.2 Step 5 (B-E3: `test_gernot_261008_paket3.py::TestQ1Festschreiben::test_altentwurf_behaelt_re_nummer_und_datum`, `test_dunning.py::test_dunning_email_sending`), C.2 Step 6 (C-E12: 11 erwartete Dateinamen in `test_gernot_261008_paket3.py`, je mit `# Paket 4, C`), D.2 Step 5 (E-D6: zwei Tests in `test_gernot_261008_paket3.py`, `TestQ4SonderpreiseDatevKatalogpreis` und `TestQ7Feldschutz`). Weitere Änderungen an Bestandstests sind ein Stoppgrund.

   Der Hinweis für Worker und die Global Constraints (C) nennen die Ausnahme von C zusätzlich. Die Angaben zu B und D stammen aus `B.md`/`D.md` vom 09.10. 18:47. Ändern B oder D ihre Ausnahmen, wird der Satz nachgezogen.
9. **Nachspiel auf dem gemergten Stand:** In der Revision ist es auf `main` @ `521ed6d` erledigt (Prüfstand): dieselben Anker-Treffer und dieselben Rot/Grün-Ausgaben, V 1818 → 1865. Rückt `main` vor Paket 4 weiter vor, wird mit `/tmp/p4-c5rev-skripte/nachspiel.sh <neue Kopie> <Commit> /Users/nikolajunser-richter/minga-greens-erp` erneut nachgespielt. Erwartet ist dasselbe Protokoll wie `/tmp/p4-c5rev-skripte/nachspiel-df84f7b.log`, bis auf N.
10. **O-Texte nachziehen:** Ziel, Abnahme C2/C3/C5/C13/C16 und Offener Punkt 2 nennen „`<Belegnummer>.pdf`“. Nach Paket 4 heißt es „`<Belegnummer>_<Kunde>.pdf`“. Die Nachricht an Gernot zu O sollte das gleich so sagen.
11. **Ersatznamen im Frontend** (`${nummer}.pdf` in `OrderDocumentsModal`, `Invoices.tsx`, nach O in `belegHerunterladen`-Aufrufen): Sie gelten nur, wenn `Content-Disposition` fehlt. Unverändert gelassen, damit C die von O umgebauten Stellen nicht berührt.
12. **Rechnungen ohne Bestellung** (Leergutbelege, Rechnungen von Hand) tauchen im Belegstatus nicht auf, denn er zeigt je Bestellung. Ihr Versandstand steht in der Rechnungsliste („versendet an …“).
13. **G19-Rest** (nicht in C): Gescheiterte Versuche und Mahnungen laufen am Versandprotokoll vorbei. Das ist für den Belegstatus ohne Belang.
14. **Routenschutz im Frontend:** Es gibt keinen. P4-D baut nach E-D7 Variante a keinen Wächter (`NurFuerRollen` entfällt). Wie bei `/invoices` schützt der Server (403), und die Seite zeigt „Keine Berechtigung für den Belegstatus“ unter den Filtern. Die Schnellsuche zeigt „Belegstatus“ allen Rollen, so wie heute „Rechnungen“. Kommt später ein Rollenfilter für Route oder Schnellsuche, gilt für beide Einträge dieselbe Rolle.
15. **FAKTURIERT mit storniertem NovaERP-Beleg** (C-E3, Review-Hinweis):
    - Heute gibt es 0 Fälle. Entsteht einer, zeigt der Belegstatus `OHNE_RECHNUNG`.
    - Nach P4-B (B-E1) lehnt NovaERP eine Neuausstellung mit 409 ab, und der Belegdialog bietet sie nicht an. Gernot kann die Lücke dann nicht selbst schließen.
    - Der Manager entscheidet je Fall per Runbook mit Trockenlauf/APPLY, Backup und Audit:
      - Die Bestellung war extern abgerechnet: Die Stornierung war die Korrektur einer Doppelabrechnung. Dann bleibt der Fall als bekannte Ausnahme notiert. Eine Daten-Kennzeichnung gibt es dafür nicht.
      - Sie ist unberechnet: Dann wird der Status zurückgesetzt und neu berechnet.
    - Eine stornierte Sammel- oder Monatsrechnung (ohne `order_id`, Lieferscheine bei Storno gelöst) sieht die Regel nicht. Ebenso sieht der Sammellauf `_abrechenbare_lieferscheine` sie nicht, er schließt FAKTURIERT ganz aus.
    - Ein vollständiger Schutz bräuchte den Weg über `invoice_line_sources`, also eine sechste Abfrage. Darauf wurde wegen 0 Fällen verzichtet.

### P4-D — Rechte der Rolle Produktion

**Fragen an Gernot:**
- **F-D1 (Bestätigung, blockiert den Deploy nicht; alte T5-Frage F2):** „Mitarbeiter können über die Suche oben (Strg+K → ‚Kunden‘) neue Kunden anlegen und Kundendaten ändern: Adressen, Ansprechpartner, Telefon und Liefertage. Konditionen sehen sie nicht, und löschen können sie nichts. So hast du es am 03.09. festgelegt (‚bei Ausfall der Betriebsleitung müssen die Mitarbeiter erfassen können‘). Soll das so bleiben?“
  - Wenn **ja**: Optional ein kleiner Folgeauftrag, der „Kunden“ auch ins Menü der Rolle Produktion aufnimmt (`Layout.tsx`, Eintrag `'/customers'`). Server und Seite sind nach P4-D fertig.
  - Wenn **nein**: Das ist die Variante b aus E-D7, ein eigener Folgeauftrag. Kunden anlegen und ändern wird im Server für die Halle gesperrt (T5 R2), `/customers` bekommt einen Wächter, und die Palettenpunkte `'nav-customers'`/`'action-new-customer'` werden für die Halle ausgeblendet.
- **F-D2:** „Sollen Mitarbeiter Abos anlegen, ändern oder beenden dürfen?“ Heute geht das über die Schnittstelle, das Menü zeigt Abos nicht.
- **F-D3:** „Beim Bestellen sehen Mitarbeiter den gültigen Preis je Produkt, auch einen Sonderpreis, weil Bestellung und Auftragsbestätigung Preise tragen. Die Sonderpreisliste und die Konditionen des Kunden sehen sie nicht. Passt das so?“
- **F-D4:** „Kunden deaktivieren und reaktivieren können nur du, der Vertrieb und die Buchhaltung, nicht die Produktionsplanung. Passt das?“ (E-D2, Rückweg dort.)
- **F-D5:** „In der Software heißt die Rolle ‚Produktion‘, du schreibst ‚Mitarbeiter‘. Sollen wir sie umbenennen?“ Das wäre nur der Text in `services/rollen.ts` und `Layout.tsx`, die technische Rolle bleibt `production_staff`.

**Intern (Manager):**
- **I-D1 — „kein Stammdaten-Löschen“ außerhalb der Kunden.** Die Halle darf noch:
  - Lagerorte anlegen, ändern und **deaktivieren**: `POST`/`PATCH /api/v1/inventory/locations` (`_deps_lager`). `PATCH /api/v1/inventory/locations/{id}` mit `{"is_active": false}` gibt als `production_staff` 200 (gemessen in `/tmp/p4-kopie-drev` auf `df84f7b`). Nach E-D2 ist Deaktivieren Löschen über einen anderen Weg. Einen Weg in der Oberfläche gibt es nicht: Das Menü „Lagerorte“ steht nur bei `ADMIN` und `PRODUCTION_PLANNER`, die Befehlspalette hat keinen Eintrag `/locations`, und `Locations.tsx` hat keinen Deaktivieren-Knopf;
  - die Gesamtzahl der Growroom-Stellplätze setzen: `PUT /api/v1/production/growroom-capacity` (`_deps_produktion`). Das widerspricht dem Kommentar `# Kapazitäten plant nur die Planung` in `main.py`.

  Gemessen mit `/tmp/p4-d-tools/delete_routes.py POST,PATCH,PUT`. Das ist nicht Teil dieses Abschnitts (Kunden-Stammdaten), sondern ein eigener kleiner Abschnitt mit `require_role(ROLLEN_OHNE_HALLE)` an den drei Routen.
- **I-D2 — Wachhund-Kommentar veraltet.** `_Q4_FREIE_KUNDENFELDER` in `test_gernot_261008_paket3.py` heißt dort „Kundenfelder, die die Halle ändern darf“ und enthält `aktiv`. Seit P4-D.1 heißt „frei“ nur noch „ohne Konditions- und Empfängerschutz“. Der Test bleibt grün. Den Kommentar fasst dieser Abschnitt nicht an (E-D6: nur die zwei nötigen Tests).
- **I-D3 — G40/G39 unverändert.** Mitarbeiter-Logins legt Gernot selbst an. `benutzer_audit` ist leer, über B8 ist also noch keiner entstanden. Telefon im Benutzerprofil (G39) ist nicht Teil dieses Abschnitts.
- **I-D4 — Nachspiel nach D/F/O:** `/tmp/p4-drev-tools/nachspiel.sh <Kopie>` wendet diesen Text Step für Step an (Standard-Plandatei `/tmp/p4/D.md`). `/tmp/p4-d-tools/replay.sh` nutzt dagegen die Blöcke des Entwurfs vor der Überarbeitung und gilt nicht mehr. Auf `bd56901` ist das Nachspiel schon gemessen (Prüfstand). Für den gemergten Stand die Kopie aus dem Merge-Commit ziehen (`git archive <merge> | tar -x -C /tmp/p4-kopie-…`, `node_modules` als Symlink). Erwartet werden dieselben Rot/Grün-Zahlen, die Prozedur V mit N = 1742 und eine Routenzahl im Wachhund von 54 (im Gesamtplan 55: `GET /api/v1/belegstatus` aus C.3, in der Zusammenführung zu `_PRAEFIXE` ergänzt).
- **I-D5 — Nebenbefunde außerhalb von D, nicht durch D verursacht:**
  - Das Kundenformular schickt eine leere Haupt-E-Mail als `""`. `EmailStr` lehnt das mit 422 ab, für **alle** Rollen. Ein Kunde ohne E-Mail lässt sich im Formular also weder anlegen noch speichern (gemessen auf `df84f7b`). Kandidat für einen Fix im Formular (`""` → `null`).
  - Die Befehlspalette filtert nur die Benutzerverwaltung nach Rolle. Der Halle bietet sie auch „Rechnungen“, „Analytics“, „Einstellungen“ und „Neue Rechnung erstellen“ an, und dort antwortet der Server mit 403. Für „Kunden“ ist das nach E-D7 gewollt.
  - Einen Knopf „Kunde löschen“ gibt es in der Kundenliste nicht. Der Lösch-Dialog mit `deleteMutation` in `Customers()` ist toter Code. Seine allgemeine Meldung „Fehler beim Löschen“ sieht deshalb niemand.

### Nicht in diesem Plan (aus dem Abgleich; Zuordnung durch den Manager)

- **G81 — Liefertag nachträglich ändern** (LIVE_TEILWEISE): `update_order` bestimmt den Packtag nicht neu; Bestellungen mit festem Packtag stehen danach am falschen Tag im Tagesplan. Eigener kleiner Fix.
- **G07 — Brutto je Steuersatz im Rechnungs-PDF** (LIVE_TEILWEISE): Netto und Steuer je Satz sind ausgewiesen (§ 14 Abs. 4 Nr. 8 UStG erfüllt), ein Brutto-Block je Satz fehlt.
- **G08, G45, G46, G47, G75 — DATEV** (EXTF-Kopf, Belegbilder, Testexport mit dem Steuerberater): Offene Punkte D des Nachtrags 09.10.; der Export bleibt für `minga` gesperrt, bis der Steuerberater bestätigt.
- **G17 — Versanddialog mit Checkboxen** (LIVE_TEILWEISE): Adressen stehen als Text je Zeile, abwählen heißt löschen.
- **G33 — Einheit „Kiste“** (LIVE_TEILWEISE): eine schlichte Einheit für unverpackte Gastrokisten fehlt.
- **G73 — Naturkostinsel, zwei Filialen mit eigenem SEPA-Mandat** (OFFEN): fachlich neu (Mandat je Filiale bzw. Lieferadresse), Antwort an Gernot steht aus.
- **G85–G88, G91 — Growroom** (laut Kritik LIVE_TEILWEISE bzw. OFFEN): Stellplätze nur beim Statuswechsel gebucht, Freigabe nur über die Ernte, „belegt“ zeigt 395 Kisten aus 69 veralteten Importchargen (Datenbereinigung mit Runbook nötig), Regalplatz nur bei der Aussaat wählbar. Eigenes Paket.
- **G39 — Telefon und Adresse im Benutzerprofil** (laut Kritik OFFEN); **G40** — Mitarbeiter-Logins legt Gernot selbst an (`benutzer_audit` leer).
- **G80 — Bierbichler BE-20260917-0003 stornieren:** über R-B3 mit Gernots Antwort (Frage 2 oben); bis dahin im Tagesplan gesperrt (A).
- **G71 — Gläubiger-ID** bestätigen lassen (Gernot); **X04** SEPA-Vorankündigungsfrist, **X05** RE-00002/-00004 in lexoffice, **X06** Update an Gernot (Bereinigung erledigt, Monatslauf) — Nachrichten, kein Code.
- **Kritik „missed“ (02.10.):** Meldung „keine Saatgutcharge im Lager“ beim Anlegen einer Wachstumscharge, neuer Wareneingang (Borretsch) bei „Alle Lagerorte“ unsichtbar — Befund vor einem Fix prüfen (eigener Bugfix).
- **I-D1 — „kein Stammdaten-Löschen“ außerhalb der Kunden** (Lagerorte deaktivieren, Growroom-Kapazität setzen für die Halle): eigener kleiner Abschnitt mit `require_role(ROLLEN_OHNE_HALLE)` an drei Routen.
- **Mit dem Nachtrag 09.10. live** (Gernot informiert sich über die Nachricht zu D/F/O): G56 (Belegordner), G61/G62 (Firmendaten-Karte, Grußformel), G76 (SKR04, Export gesperrt bis zur Bestätigung).
