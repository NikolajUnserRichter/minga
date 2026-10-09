# B6 — Abos mit mehreren Produkten — Implementation Plan

> **Hinweis für Worker (Codex, ohne Netzwerk):** Diesen Plan Task für Task in der Reihenfolge der Nummern abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Lies vor jedem Task seinen Abschnitt frisch aus der Plandatei (sie kann während des Laufs ergänzt werden). Kein Task wird übersprungen, zusammengefasst oder auf eigenes Urteil verkürzt. **Stoppregeln** stehen unter „Global Constraints". Eigene Patch- oder Ankerfehler sind **kein** Stoppgrund: auf Funktions-/Klassennamen und die zitierten Zeilen ankern, nach jedem Patch mit `grep -n` prüfen, dass genau die gemeinte Stelle geändert ist. Das **Runbook** und die **Abnahme** am Ende sind Manager-Arbeit, kein Worker-Task.

**Goal:** Ein Abo trägt beliebig viele Positionen (Produkt bzw. Verpackungsvariante, Menge, Einheit) in der neuen Tabelle `subscription_items`. Der Abo-Lauf (05:00 und „Heute verarbeiten") legt je Abo und Liefertag **eine** Bestellung mit **allen** Positionen an. Die fünf Bestands-Abos in Produktion (3 aktiv, alle MG-14001 Gastrotray, wöchentlich; 2 inaktiv) werden beim Start verlustfrei migriert: ihr bisheriger Kopf (`product_id`, `product_variant_id`, `seed_id`, `menge`, `einheit`) wird Position 1, idempotent in `tenancy._auto_migrate`. Die Abo-Seite bekommt eine Positionsliste (hinzufügen, entfernen, Variante, Menge, Einheit).

**Architecture:** Neues Modell `SubscriptionItem` (`backend/app/models/customer.py`, Tabelle `subscription_items`, legt `create_all` an) mit Beziehung `Subscription.positionen` (sortiert nach `position`, `cascade="all, delete-orphan"`). Kein Preisfeld (Entscheidung E1). Die Kopffelder des Abos bleiben und **spiegeln Position 1** (`Subscription.kopf_aus_erster_position()`), weil SQLite-Bestandsschemata sie `NOT NULL` führen und Altleser (Prognose, alte Browser-Tabs) sie lesen; der Abo-Lauf liest nur noch Positionen. Die Migration ist `app/services/abo_positionen.positionen_nachtragen(db)` (nur Abos ohne Position), aufgerufen in einem eigenen `try`-Block in `_auto_migrate` vor dem A3-Korrekturblock — damit greift sie bei jedem Start (`init_all_existing_tenants`), bei `provision_tenant` und nach jedem Demo-Reset. Der Lauf: `abo_position(db, sub, heute, quelle, nr)` baut eine Bestellposition aus einer Abo-Position (Preisregel und Satz unverändert aus Paket 2), neu `abo_positionen(db, sub, heute)` baut alle (alles oder nichts, E3), `_create_order_from_subscription` hängt sie an eine Bestellung. Die API (`sales.py`) nimmt `positionen` an, prüft sie beim Speichern (`_abo_positionen_bauen`, E4) und liefert sie in jeder Antwort; die alten Einzelfelder bleiben gültig und ergeben eine Position. Pfand braucht keinen Sonderweg (E5).

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`), SQLite je Mandant (`tenancy._auto_migrate`: nur neue Tabellen über `create_all` und `ADD COLUMN`), Pydantic v2, APScheduler (05:00-Lauf), React 18 + TypeScript, TanStack Query 5.

**Ausgangsstand:** `main` **nach dem Merge von Paket 3** (Branch `feat/paket3-belegfluss` inkl. B8 Benutzerverwaltung). Paket 3 ist seit 09.10.2026 07:54 live (main `f4362b8`); `main` steht bei der Revision dieses Plans auf `a08e102` = `f4362b8` plus zwei reine Doku-Commits (`git diff --stat f4362b8 a08e102`: nur `docs/`). Geplant und durchgespielt auf `feat/paket3-belegfluss` @ `be56843`, nachgeprüft auf `f4362b8` und nach dem Review erneut auf `a08e102` (siehe Prüfstand). Keine Zeilennummern als Anker: maßgeblich sind Funktions-/Klassennamen und zitierte Zeilen.

**Spec:** `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, Features-Tabelle Zeile **B6** („Ein Produkt je Abo; fehlt: `subscription_items`, Generator, Migration", Aufwand L) und Abschnitt „Abweichungen vom Feedback-Dokument" (Mehrfach-Liefertage und Einheit Kiste sind im Formular vorhanden; Fälligkeit hat Paket 2 repariert). Gernots Wunsch (08.10.): Abos mit mehreren Produkten je Lieferung.

## Prüfstand (alles in Kopien unter `/tmp`, Repo und Worktree `minga-paket3` unverändert)

Maßgeblich für den Worker sind allein die Zahlen in den Steps. Die ersten fünf Punkte sind der Stand **vor** dem Review (Testdatei mit 32 Tests, Vollauf 1631 bzw. 1643 passed); aktuell ist der Punkt „Nachspiel der Revision auf `a08e102`" (33 Tests, 1644 passed).

- **Baseline** `feat/paket3-belegfluss` @ `be56843`, Kopie `/tmp/b6-kopie-p3`: Prozedur V → `14 failed, 1599 passed, 2 skipped, 1 error`, Fehlernamen = Liste in „Global Constraints".
- **Rot/Grün je Task, frisch nachgespielt** auf einer zweiten Kopie (`/tmp/b6-kopie-replay`, `git archive be56843`), mit genau den Test- und Code-Blöcken dieses Plans: Task 1 5 failed → 5 passed; Task 2 4 failed/5 passed → 9 passed; Task 3 7 failed/10 passed → 17 passed; Task 4 12 failed/20 passed → 32 passed; Task 5 `tsc` 2 Fehler → sauber, `vite build` `✓ built`. Testdatei des Nachspiels byte-gleich mit der Entwicklungskopie.
- **Vollauf mit allen Tasks:** `14 failed, 1631 passed, 2 skipped, 1 error`, Fehlernamen identisch mit der Baseline. `ruff --select F821,F823` über die geänderten Python-Dateien: nur der Altbefund `SepaMandat` in `models/customer.py` (Paket 3, schon auf `be56843`).
- **Nachprüfung auf `f4362b8`** (Paket-3-HEAD am 09.10. morgens, `/tmp/b6-kopie-head`): Tasks 1–3 und 5 unverändert anwendbar; in Task 4 hält der Anker der Schema-Änderung (Bereich von `class SubscriptionCreate` bis vor `class SubscriptionResponse`), ein starrer Patch dagegen nicht (neue Importzeile `pydantic_core` direkt darunter). Vollauf `14 failed, 1643 passed, 2 skipped, 1 error`, Baseline-Namen. `tsc` sauber.
- **Worker-Nachspiel aus dem Plantext:** Ein Skript hat die Code-Blöcke dieses Plans mechanisch mit den hier beschriebenen Ankern (zitierte Zeilen, Bereiche zwischen Funktions-/Klassennamen) auf eine frische Kopie von `f4362b8` angewendet (`/tmp/b6-kopie-sim`): Rot/Grün je Task genau wie in den Steps angegeben, Paket-2-Test in Task 4 Step 6 `1 failed` → `1 passed`, `tsc` 2 Fehler → sauber, Vollauf mit Baseline-Namen (`1643 passed`), Build `✓ built`, alle Prüf-`grep`s der Steps mit den genannten Treffern. Die Ergebnisdateien sind byte-gleich mit der Entwicklungskopie, außer `schemas/customer.py` (dort nur die Paket-3-Zeilen von `f4362b8`). Die sieben Prüfungen der Vorbereitung und der Hash der Abo-Seite stimmen gegen den Paket-3-Worktree (lesend geprüft).
- **Migration und Gleichheitsprobe** auf einer simulierten Vor-B6-Mandanten-DB (mit dem Code von `be56843` angelegt: 3 aktive MG-14001-Abos, 1 inaktives Kisten-Abo, 1 inaktives Sorten-Abo): Prüfskript vorher „Tabelle subscription_items: fehlt"; Gleichheitsprobe mit B6-Code `Abweichungen: 0` (jede Bestellposition nach neuem Weg gleich der nach altem Weg, das Sorten-Abo auf beiden Wegen mit derselben Überspringen-Meldung); danach `positionen_gesamt: 5`, keine Abweichung Kopf/Position 1.
- **Review 09.10. (unabhängig, `/tmp/b6-kopie-rev`, `git archive f4362b8`):** Plan wörtlich ausführbar, alle Zahlen reproduziert (Rot/Grün je Task, Paket-2-Test, Umfeld `1 failed, 211 passed`, Prozedur V `1643 passed` mit Baseline-Namen, `tsc`, Build, `ruff`); Migration über alle drei Wege (`init_all_existing_tenants`, `provision_tenant`, `reset_demo_from_seed`), Lauf, Pfand (E5) und Rechte (E6) am Code bestätigt; `npm run build` im Worktree schreibt nicht in das über den Symlink geteilte `node_modules` des Hauptrepos. Eingearbeitet: Einheit der Einzelfelder ohne Längengrenze gab 500 (Task 4, neuer Test); Startlog-Zeile in B1 erscheint nicht (nur `logger.info`, das Backend richtet kein Logging ein); Lücke beim erneuten Deploy nach einer Rücknahme (Runbook); Bearbeiten-Dialog aktivierte jedes Abo beim Speichern (E10) und zeigte ein nicht mehr wählbares Produkt als leeres Feld (Task 5).
- **Nachspiel der Revision auf `a08e102`** (`/tmp/b6-kopie-rv2`, Blöcke dieses Plans mechanisch mit seinen Ankern angewendet): Task 1 5 failed → 5 passed; Task 2 4 failed/5 passed → 9 passed; Task 3 7 failed/10 passed → 17 passed; Task 4 **13 failed/20 passed → 33 passed** (neuer Test `test_einzelfelder_pruefen_die_einheit_wie_eine_position`); Paket-2-Test `1 failed` → `1 passed`; Umfeld `1 failed, 211 passed`; Basis-Vollauf `14 failed, 1611 passed, 2 skipped, 1 error`, nach Task 4 `14 failed, 1644 passed, 2 skipped, 1 error`, beide mit Baseline-Namen; `tsc` 2 Fehler → sauber; Build `✓ built` (danach nichts Neueres im geteilten `node_modules`); `ruff` F821/F823 nur `SepaMandat`; Diff genau die 12 Dateien aus Task 6 Step 5. Gegenprobe: ohne die Längengrenze an `SubscriptionCreate.einheit` scheitert der neue Test an `ValidationError … for SubscriptionPositionIn` aus dem Handler (in Produktion der 500er), mit ihr ist er grün. Die sieben Prüfungen der Vorbereitung und der Hash der Abo-Seite stimmen auf `a08e102`.
- **Nicht gemessen:** Oberfläche im Browser (keine Frontend-Tests im Repo; Review Focus, Abnahme), echte Produktionsdaten (Runbook A3 macht das auf einer Kopie des Backups).

## Entscheidungen (Manager, im Plan getroffen — Gernot kann widersprechen, siehe „Offene Punkte")

- **E1 — Kein Preis je Position.** Der Preis kommt im Lauf wie bisher aus Sonderpreis des Kunden (`resolve_unit_price`, Stichtag Liefertag), Variantenpreis, Basispreis. Grund: Paket 3 (Q4, Plan Abschnitt „Abweichung von T5 R2 bei den Abos") lässt Abos für die Halle offen, **weil** `SubscriptionCreate`/`SubscriptionUpdate` keine Preisfelder haben; Sonderpreise pflegen nur `ROLLEN_OHNE_HALLE` (`sales.py`, `_ohne_halle` an `/customers/{id}/prices`). Ein Preisfeld im Abo wäre ein zweiter Preisweg an dieser Sperre vorbei. `SubscriptionPositionIn` hat `extra="forbid"`: ein mitgeschicktes `unit_price` ist 422, kein stilles Weglassen.
- **E2 — Kopffelder bleiben und spiegeln Position 1.** `_auto_migrate` kann keine Spalte entfernen oder `NOT NULL` lösen; `menge`/`einheit` sind `NOT NULL`. Altleser: `forecasting._calculate_subscription_demand` (Kopf `seed_id`, `menge`), Abo-Liste (`product_name`), ein vor dem Deploy geöffneter Browser-Tab (schickt `product_id`/`menge`/`einheit`). Geschrieben wird der Kopf nur noch aus den Positionen (`kopf_aus_erster_position`). Der Lauf liest nur Positionen.
- **E3 — Alles oder nichts je Abo und Liefertag.** Scheitert eine Position (Produkt deaktiviert, Variante passt nicht, variables Bundle, ohne Produkt und Sorte), fällt die ganze Abo-Lieferung des Tages aus, mit Meldung „Position n: …" im Log und im Toast von „Heute verarbeiten". Eine stille Teillieferung wäre schlimmer. Die Doppelanlagesperre (`_abo_bestellung_vorhanden`, Paket 2) bleibt je Abo und Tag.
- **E4 — Prüfen beim Speichern.** Die API lehnt ab, was der Lauf nie liefern könnte (gleiche Texte wie `_abo_produkt`). Der Lauf überspringt solche Positionen weiterhin, falls ein Produkt **nach** dem Speichern deaktiviert oder zum variablen Bundle wird. Dafür ändert Task 4 einen Paket-2-Test (`test_variables_bundle_wird_uebersprungen` legt sein Abo über die API auf ein variables Bundle an; das gibt jetzt 400).
- **E5 — Pfand ohne Sonderweg im Lauf.** Eine Pfandkiste ist eine normale Abo-Position (Produkt mit `is_deposit`). Wohin sie abgerechnet wird, entscheiden die normalen Wege, nicht der Lauf: `invoice_service.ist_clearing_pfand` (Rechnung aus Bestellung, `create_invoice_from_order`; Sammel- und Monatslauf, Kandidatenzeilen in `invoices.py`) lässt sie bei `KEINE` und bei `MONATLICH` ab Stichtag weg; `order_fulfillment_service` bucht beim Übergang nach GELIEFERT die Leergut-Ausgabe (`leergut_service.buche_ausgaben`); die Leergutabrechnung macht der Monatslauf. Abo-Bestellungen sind gewöhnliche ENTWURF-Bestellungen und durchlaufen diese Wege. Beleg: `TestB6Pfand` (Task 3).
- **E6 — Rechte unverändert.** Abos hängen am Router `sales` mit `_deps_auftraege` (`main.py`): alle fünf Rollen lesen und schreiben, auch `production_staff`. Die Oberfläche zeigt der Halle die Seite nicht (`Layout.tsx`, Eintrag „Abonnements" ohne `PRODUCTION_STAFF`). B6 ändert daran nichts (Paket 3, offene Frage 2 an Gernot bleibt offen). Beleg: `test_rechte_wie_bisher_auch_die_halle_legt_abos_an`.
- **E7 — Rückfall auf den Kopf.** Ein Abo ohne Position (Nachtragen beim Start gescheitert — `_auto_migrate` loggt nur; `scripts/seed_data.py` legt Abos nur mit Kopf an) liefert seinen Kopf wie vor B6, mit Warnung im Log, statt still nichts.
- **E8 — Positionen ersetzen statt einzeln patchen.** `PATCH /sales/subscriptions/{id}` mit `positionen` ersetzt die ganze Liste (neue IDs; nichts verweist auf Positions-IDs). `menge`/`einheit` wie bisher ändern die einzige Position; bei mehreren Positionen 400.
- **E9 — Einheit wie bisher** freier Text, 1–20 Zeichen (Spalte `String(20)`). Neu geprüft auch über die alten Einzelfelder (`SubscriptionCreate.einheit`, `SubscriptionUpdate.einheit`): 422 statt bisher 201 beim Anlegen bzw. 200 beim Ändern; ohne diese Grenze würde `als_positionen()` daraus einen 500 machen und das Formular könnte das Abo danach nicht mehr speichern. Betrifft nur Fremd-Clients, die Oberfläche sendet feste Codes. Mit Variante gilt im Lauf deren Verpackungseinheit (Paket 2); das Formular setzt sie und sperrt das Feld. Keine Umrechnung zwischen Einheiten (Paket 2, Regel 2).
- **E10 — Status im Bearbeiten-Dialog nur über einen Schalter.** Die Abo-Seite seit August schickt beim Speichern immer `aktiv: true`: Wer ein inaktives Abo öffnet und speichert, aktiviert es still wieder, und der nächste Lauf liefert (Produktion: 2 inaktive Abos). Einen anderen Weg zum Wiederaktivieren hat die Seite nicht (die Tabelle kennt nur „Deaktivieren"). B6 ersetzt das feste `true` durch den Schalter „Aktiv (wird an den Liefertagen beliefert)" im Bearbeiten-Dialog, vorbelegt mit dem gespeicherten Status. Die API bleibt unverändert.

## Global Constraints

- **Arbeitsort:** Worktree `/Users/nikolajunser-richter/minga-b6`, Branch `feat/b6-abo-positionen`, vom Manager vor dem Dispatch aus `main` (nach Merge Paket 3) angelegt: `git worktree add ../minga-b6 -b feat/b6-abo-positionen main` und `ln -s /Users/nikolajunser-richter/minga-greens-erp/frontend/node_modules frontend/node_modules`. Jeder Befehl beginnt im Worktree-Wurzelverzeichnis.
- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` und `backend/venv311` sind kaputt.
- **Einzeltest:** `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_b6_abo_positionen.py -q -p no:cacheprovider`
- **Neue Tests** nur in `backend/tests/test_b6_abo_positionen.py`, Helfer mit Präfix `_b6_`. Fixture `client` aus `tests/conftest.py`. Bestehende Erwartungen ändert nur Task 4 (genau ein Paket-2-Test, begründet in E4).
- **Baseline nach Paket 3** (Fehlernamen, **nie die Anzahl** vergleichen; 14 failed + 1 error):
  ```
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
  ```
  `test_features.py::TestFeatures::test_subscription_processing` scheitert an `async def` ohne Plugin, nicht am Abo-Code; er bleibt rot.
- **Kein Netzwerk:** kein `npm install`, kein `git pull`/`push`, kein `curl`. **Kein Deploy, keine Verbindung zum Produktionsserver.**
- **Commits** nur mit den im Task genannten Dateien, nie `git add -A` oder `git add .`. Erwartete unversionierte Einträge, die **sauber** sind und nie committet werden: `frontend/node_modules` (Symlink), `backend/data/` (die Testsuite legt `backend/data/tenants/dev.db` samt `-wal`/`-shm` an — gemessen auch auf dem Basisstand), `.claude-flow/`, `.swarm/`, die unversionierte Plandatei, `frontend/dist/`.
- **Commit-Nachricht** endet mit der Zeile `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` (Muster: `git commit -m "<Betreff>" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"`).
- **Frontend-Prüfung:** `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut), Build `cd frontend && npm run build` (endet mit `✓ built in …`; die Warnung „Some chunks are larger than 500 kB" ist Altbestand). `tsconfig.json` hat `noUnusedLocals`. Playwright gehört nicht zur Worker-Prüfung.
- **Nie** `process_daily_subscriptions` oder den Knopf „Heute verarbeiten" ohne Patch auf `SessionLocal` aufrufen (`backend/data/tenants/dev.db` wäre das Ziel). Die Tests dieses Plans patchen ihn (`_b6_lauf`).
- **UI-Texte auf Deutsch.**
- **Stoppregeln:**
  1. Ein zitierter Anker fehlt, **weil der Code inhaltlich anders aussieht** (Funktion fehlt, andere Logik, anderer Rückgabewert): stoppen und die exakte Fundstelle bzw. Fehlerausgabe melden.
  2. Rot oder Grün weicht nach korrekt angewendetem Schritt von der Erwartung ab (andere Anzahl, anderer Testname, andere Fehlermeldung): stoppen, exakte Ausgabe melden. Nicht „passend machen". Die erwarteten Meldungen sind inhaltlich gemeint: pytest kürzt lange Werte in der `assert`-Zeile (z. B. `[(2, Decimal(...'), 'SCHALE')] == [(1, Decimal(...'), 'SCHALE')]`), maßgeblich sind die vollständigen Werte bzw. die Diff-Zeilen darunter (`At index 0 diff: …`, `Right contains …`). Eine solche Kürzung ist kein Stoppgrund.
  3. Prozedur V zeigt einen Fehlernamen, der nicht in der Baseline steht, oder ein Baseline-Name fehlt: stoppen, `comm`-Ausgabe melden.
  4. `git hash-object frontend/src/pages/Abonnements.tsx` weicht in der Vorbereitung ab: Task 5 Step 4 (Datei ersetzen) nicht ausführen, Tasks 1–4 normal, dann stoppen und melden.
  5. **Kein Stopp:** eigene Patch-/Ankerfehler (Leerzeichen, Mehrfachtreffer durch zu kurzen Anker, Tippfehler) — selbst beheben, mit `grep -n` belegen, in der Abschlussmeldung vermerken. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht ebenso.

## Prozedur V (Vollauf mit Namensabgleich)

```bash
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/b6-voll.txt 2>&1; tail -1 /tmp/b6-voll.txt; grep -E '^(FAILED|ERROR) ' /tmp/b6-voll.txt | sed 's/ - .*//' | sort > /tmp/b6-namen.txt; comm -3 /tmp/b6-baseline-namen.txt /tmp/b6-namen.txt; echo "--- Ende Abgleich"
```

Erwartet: letzte Zeile `14 failed, N passed, 2 skipped, 1 error in …s` (N wächst mit jedem Task), **keine** Zeile zwischen der Summenzeile und `--- Ende Abgleich`. Dauer ca. 1 min. `/tmp/b6-baseline-namen.txt` entsteht in der Vorbereitung.

## Review Focus

Was **kein automatischer Test** abdeckt (keine Frontend-Tests im Repo); der Manager prüft es im Browser (Abnahme, Prüfungen O1–O8):

1. **Bestands-Abo bearbeiten** (MG-14001, migriert): Der Dialog zeigt genau eine Position mit Produkt, Menge, Einheit; „Speichern" ohne Änderung lässt Kopf und Position gleich (Task 5, `openEditModal`). → O2.
2. **Variante wählen:** Einheit springt auf die Verpackungseinheit der Variante und ist gesperrt; Rückwechsel auf „Ohne Variante" gibt das Feld frei. Ein Einheitencode außerhalb der Liste (z. B. `STK` aus einer Variante) erscheint als zusätzliche Option statt als leeres Feld. → O3.
3. **Abo mit deaktiviertem Produkt:** Die Produktauswahl der Position zeigt den bisherigen Namen (`bezeichnung`) ausgegraut mit Hinweis „nicht mehr wählbar" statt eines leeren Felds (`produktOptionenFuer`; die Liste lädt nur aktive Produkte ohne variable Bundles). „Speichern" zeigt den Servertext „Position n: Produkt … ist deaktiviert" als Toast (`getErrorMessage`) statt „Fehler beim Aktualisieren"; speichern lässt sich erst mit einem anderen Produkt oder ohne diese Position. Deaktivieren geht weiter über die Tabelle (schickt nur `aktiv: false`). → O5.
4. **Letzte Position:** Der Entfernen-Knopf der einzigen Position ist gesperrt; das Formular schickt nie eine leere Liste (die API antwortete sonst 422). → O4.
5. **„Heute verarbeiten" mit einem kaputten Abo:** Der Toast nennt Kunde und „Position n: …" (Text aus `process_today_subscriptions`, unverändert). → O6.
6. **Status beim Bearbeiten (E10):** Ein inaktives Abo öffnen und speichern lässt es inaktiv; der Schalter „Aktiv" aktiviert es bewusst wieder. → O9.

Getestet (Review Focus der Tasks): Position 1 = Kopf nach Migration (Task 2), Idempotenz und Demo-Reset (Task 2), eine Bestellung mit allen Positionen und Doppelsperre (Task 3), alles oder nichts (Task 3), Pfand je Abrechnungsart (Task 3), 422 bei Preisfeld, 422 statt 500 bei zu langer Einheit über die Einzelfelder, 400/404 bei unbrauchbarer Position, Ersetzen und Atomarität beim PATCH, Rechte (Task 4).

## File Structure

| Datei | Verantwortung | Task |
|---|---|---|
| `backend/app/models/customer.py` | **neu** `SubscriptionItem` (Tabelle `subscription_items`, `bezeichnung`), `Subscription.positionen`, `Subscription.kopf_aus_erster_position()`, Import `ProductVariant` am Dateiende | 1 |
| `backend/app/models/__init__.py` | Export `SubscriptionItem` | 1 |
| `backend/app/services/abo_positionen.py` | **neu** — `positionen_nachtragen(db) -> int` (Bestands-Abos: Kopf wird Position 1, idempotent) | 2 |
| `backend/app/tenancy.py` | `_auto_migrate`: eigener `try`-Block vor dem A3-Korrekturblock | 2 |
| `backend/app/tasks/subscription_tasks.py` | `abo_position(db, sub, heute, quelle=None, nr=1)`, **neu** `abo_positionen`, `_create_order_from_subscription` mit allen Positionen | 3 |
| `backend/app/schemas/customer.py` | **neu** `SubscriptionPositionIn` (`extra="forbid"`), `SubscriptionPositionResponse`; `SubscriptionCreate` (`positionen`, Einzelfelder optional, `einheit` 1–20 Zeichen, `als_positionen()`), `SubscriptionUpdate` (`positionen`, `einheit` 1–20 Zeichen), `SubscriptionResponse.positionen`; Import `model_validator` | 4 |
| `backend/app/api/v1/sales.py` | Abo-Bereich: `_ABO_LADEN`, `_abo_antwort`, `_abo_positionen_bauen`, `_abo_laden`, `list_subscriptions`, `create_subscription`, `update_subscription`; Importe | 4 |
| `backend/tests/test_b6_abo_positionen.py` | **neu** — alle Tests dieses Plans | 1–4 |
| `backend/tests/test_gernot_261008_paket2.py` | `TestP4AboPosition.test_variables_bundle_wird_uebersprungen`: Abo auf normales Produkt, danach Produkt per PATCH zum variablen Bundle | 4 |
| `frontend/src/types/index.ts` | **neu** `SubscriptionPosition`; `Subscription.positionen`, `product_variant_id` | 5 |
| `frontend/src/services/api.ts` | **neu** `SubscriptionPositionInput`; `subscriptionsApi.create`/`update` mit `positionen` | 5 |
| `frontend/src/pages/Abonnements.tsx` | Positionsliste im Dialog, Spalte „Positionen je Lieferung", Servertexte im Toast, nicht mehr wählbares Produkt sichtbar, Schalter „Aktiv" im Bearbeiten-Dialog (E10) | 5 |

Nicht geändert (geprüft): `process_today_subscriptions` und `abo_lauf` (Rückmeldung, Doppelsperre, Mandant), `ist_faellig`, `_abo_produkt`, `main.py` (Rechte), `Layout.tsx` (Navigation), `invoice_service.py`, `leergut_service.py`, `forecasting.py`, `scripts/seed_data.py`.

## Vorbereitung (vor Task 1)

- [ ] **Basis festhalten:** `git rev-parse HEAD` → Hash als `<Basis>` in den Bericht schreiben (eine Shell-Variable reicht nicht, jeder Befehl läuft in einer eigenen Shell).
- [ ] **Arbeitsbaum:** `git status --porcelain` → nur die in „Global Constraints" als sauber genannten `??`-Einträge. Jede `M`-, `A`- oder `D`-Zeile: stoppen und melden, nichts committen oder zurücksetzen.
- [ ] **Ausgangsstand prüfen** (alle sieben müssen passen, sonst stoppen und die Ausgabe melden):
  ```bash
  grep -c '^def abo_lauf(db, heute: date) -> dict:' backend/app/tasks/subscription_tasks.py        # 1 (Paket 2)
  grep -c '^def abo_position(db, sub, heute: date) -> OrderLine:' backend/app/tasks/subscription_tasks.py   # 1
  test -f backend/app/services/leergut_service.py && test -f backend/app/core/rollen.py && echo paket3   # paket3
  grep -c 'Der Korrekturblock A3 darunter bleibt der letzte Block' backend/app/tenancy.py   # 1
  grep -c '^_deps_auftraege = _rollen(SALES, BUCHHALTUNG, PLANER, PRODUKTION)' backend/app/main.py   # 1
  grep -rn 'SubscriptionItem\|subscription_items' backend/app frontend/src | wc -l   # 0
  test -e backend/tests/test_b6_abo_positionen.py && echo vorhanden || echo fehlt   # fehlt
  ```
- [ ] **Abo-Seite unverändert seit August:** `git hash-object frontend/src/pages/Abonnements.tsx` → `4f19b3072844da15bf00281a33fe823e49da21bc`. Abweichung: Stoppregel 4.
- [ ] **Baseline-Namen erzeugen:**
  ```bash
  cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py -rfE -p no:cacheprovider > /tmp/b6-voll-basis.txt 2>&1; tail -1 /tmp/b6-voll-basis.txt; grep -E '^(FAILED|ERROR) ' /tmp/b6-voll-basis.txt | sed 's/ - .*//' | sort > /tmp/b6-baseline-namen.txt; cat /tmp/b6-baseline-namen.txt
  ```
  Erwartet: `14 failed, … passed, 2 skipped, 1 error`, die 15 Namen exakt wie in „Global Constraints". Abweichung: stoppen und melden.

---

### Task 1: Modell — Positionen in eigener Tabelle

**Files:**
- Create: `backend/tests/test_b6_abo_positionen.py`
- Modify: `backend/app/models/customer.py` (Klasse `Subscription`, neue Klasse `SubscriptionItem`, Importzeile am Dateiende)
- Modify: `backend/app/models/__init__.py` (Import und `__all__`)

**Interfaces:**
- Produces:
  - `class SubscriptionItem(Base)`, `__tablename__ = "subscription_items"`; Spalten `id`, `subscription_id` (FK `subscriptions.id`, `ondelete="CASCADE"`, Index), `position: int`, `product_id`, `product_variant_id` (beide FK, `ondelete="SET NULL"`), `seed_id` (FK `seeds.id`), `menge: Decimal` (`Numeric(10, 2)`, NOT NULL), `einheit: str` (`String(20)`, NOT NULL), `created_at`. Beziehungen `subscription`, `product`, `variante`, `seed`. Property `bezeichnung -> Optional[str]` („Produkt — Variante", sonst Sorte, sonst `None`).
  - `Subscription.positionen: list[SubscriptionItem]` (`order_by` `SubscriptionItem.position`, `cascade="all, delete-orphan"`).
  - `Subscription.kopf_aus_erster_position() -> None`.
  - Test-Helfer `_b6_einheit`, `_b6_produkt`, `_b6_pfandkiste`, `_b6_variante`, `_b6_kunde`, `_b6_uuid`, `_b6_abo_db`, `_b6_positionen`, `_b6_bestellungen`, `_b6_anlegen`, `_b6_lauf`, Konstanten `_B6_MO`, `_B6_DO`; Tasks 2–4 nutzen sie.

**Review Focus (Task 1):** Reihenfolge kommt aus `position`, nicht aus der Einfügereihenfolge; Löschen eines Abos (auch über das harte Löschen eines Kunden ohne Belege) nimmt die Positionen mit.

- [ ] **Step 1: Testdatei anlegen**

`backend/tests/test_b6_abo_positionen.py` mit genau diesem Inhalt anlegen:

```python
"""B6 — Abos mit mehreren Produkten (Gernot, Feedback 08.10.2026).

Bis B6 trug ein Abo genau ein Produkt (Kopffelder product_id,
product_variant_id, seed_id, menge, einheit). Seit B6 trägt es Positionen in
der Tabelle subscription_items: Produkt bzw. Verpackungsvariante, Menge,
Einheit, kein Preis. Der Abo-Lauf legt je Abo und Liefertag EINE Bestellung
mit allen Positionen an. Bestands-Abos bekommen ihre Kopfdaten als Position 1
(tenancy._auto_migrate, idempotent). Der Kopf spiegelt Position 1.

Alle Helfer tragen das Präfix _b6_.
"""
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal

_B6_MO = date(2026, 10, 5)   # Montag
_B6_DO = date(2026, 10, 8)   # Donnerstag


@pytest.fixture(autouse=True)
def _b6_ohne_prognose_anstoss(monkeypatch):
    """Bestellungen stoßen per Celery eine Prognose an; ohne Redis hängt das."""
    monkeypatch.setattr("app.api.v1.sales._trigger_forecast_update", lambda *a, **k: None)


# ---------------------------------------------------------------- Helfer

def _b6_einheit(code="STK", name="Stück"):
    from app.models.unit import UnitOfMeasure, UnitCategory
    with TestingSessionLocal() as db:
        unit = db.query(UnitOfMeasure).filter_by(code=code).first()
        if unit is None:
            unit = UnitOfMeasure(code=code, name=name, category=UnitCategory.COUNT)
            db.add(unit)
            db.commit()
        return str(unit.id)


def _b6_produkt(client, name, sku, preis, **extra):
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "category": "MICROGREEN", "base_unit_id": _b6_einheit(), **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _b6_pfandkiste(client):
    return _b6_produkt(client, "IFCO-Kiste", "B6-IFCO", "4.00",
                       category="PFAND", is_deposit=True, tax_rate="STANDARD")


def _b6_variante(client, produkt, code="KISTE_12", suffix="12er Mehrwegkiste", preis="48.00"):
    r = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
        "packaging_unit_id": _b6_einheit(code, suffix),
        "name_suffix": suffix, "price_override": preis, "items_per_pack": 12,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _b6_kunde(client, name="Café Kleinberger", **extra):
    r = client.post("/api/v1/sales/customers", json={"name": name, "typ": "GASTRO", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _b6_uuid(wert):
    return uuid.UUID(wert) if wert else None


def _b6_abo_db(kunde_id, positionen, **kopf):
    """Abo direkt in der DB anlegen, mit Positionen in der angegebenen
    Reihenfolge (Tasks 1-3 laufen vor der API aus Task 4). Ohne Angabe
    spiegelt der Kopf die erste Position."""
    from app.models.customer import Subscription, SubscriptionItem, SubscriptionInterval
    erste = positionen[0] if positionen else {}
    werte = {
        "intervall": SubscriptionInterval.WOECHENTLICH, "liefertage": [3],
        "gueltig_von": _B6_MO,
        "product_id": _b6_uuid(erste.get("product_id")),
        "product_variant_id": _b6_uuid(erste.get("product_variant_id")),
        "seed_id": _b6_uuid(erste.get("seed_id")),
        "menge": Decimal(str(erste.get("menge", 1))),
        "einheit": erste.get("einheit", "STUECK"),
    }
    werte.update(kopf)
    with TestingSessionLocal() as db:
        sub = Subscription(kunde_id=uuid.UUID(kunde_id), **werte)
        for nr, pos in enumerate(positionen, start=1):
            sub.positionen.append(SubscriptionItem(
                position=pos.get("position", nr),
                product_id=_b6_uuid(pos.get("product_id")),
                product_variant_id=_b6_uuid(pos.get("product_variant_id")),
                seed_id=_b6_uuid(pos.get("seed_id")),
                menge=Decimal(str(pos["menge"])),
                einheit=pos.get("einheit", "STUECK"),
            ))
        db.add(sub)
        db.commit()
        return str(sub.id)


def _b6_positionen(abo_id):
    """(position, bezeichnung, menge, einheit) je Position aus der DB."""
    from app.models.customer import Subscription
    with TestingSessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(abo_id))
        return [(p.position, p.bezeichnung, p.menge, p.einheit) for p in sub.positionen]


def _b6_bestellungen(abo_id=None):
    """Bestellungen (optional nur die eines Abos) mit ihren Positionen."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.order import Order
    with TestingSessionLocal() as db:
        q = select(Order).options(selectinload(Order.lines)).order_by(Order.order_number)
        if abo_id:
            q = q.where(Order.notes.contains(f"Abo {abo_id}"))
        return [
            {
                "id": str(o.id),
                "requested_delivery_date": o.requested_delivery_date,
                "total_net": o.total_net, "total_gross": o.total_gross,
                "lines": [
                    {
                        "position": l.position,
                        "product_id": str(l.product_id) if l.product_id else None,
                        "product_variant_id": str(l.product_variant_id) if l.product_variant_id else None,
                        "beschreibung": l.beschreibung, "unit": l.unit,
                        "quantity": l.quantity, "unit_price": l.unit_price,
                        "tax_rate": l.tax_rate.value, "line_net": l.line_net,
                    }
                    for l in sorted(o.lines, key=lambda l: l.position)
                ],
            }
            for o in db.execute(q).scalars().all()
        ]


def _b6_anlegen(abo_id, heute=_B6_DO):
    """Abo-Bestellung anlegen wie der Lauf, ohne Fälligkeitsprüfung."""
    from app.models.customer import Subscription
    from app.tasks.subscription_tasks import _create_order_from_subscription
    with TestingSessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(abo_id))
        _create_order_from_subscription(db, sub, heute)
        db.commit()


def _b6_lauf(heute=_B6_DO):
    """Der echte Lauf (Scheduler 05:00) gegen die Test-DB."""
    from app.tasks.subscription_tasks import process_daily_subscriptions
    with patch("app.tasks.subscription_tasks.SessionLocal", TestingSessionLocal):
        return process_daily_subscriptions(heute=heute)


# ------------------------------------------------ Task 1: Modell

class TestB6Modell:
    """Positionen in eigener Tabelle, sortiert, mit Anzeigenamen; sie hängen am Abo."""

    def test_positionen_kommen_nach_positionsnummer(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(kunde["id"], [
            {"product_id": kresse["id"], "menge": 3, "position": 2},
            {"product_id": snack["id"], "menge": 2, "position": 1},
        ])

        assert _b6_positionen(abo_id) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2.00"), "STUECK"),
            (2, "Kresse Schale", Decimal("3.00"), "STUECK"),
        ]

    def test_bezeichnung_aus_variante_und_sorte(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kiste = _b6_variante(client, snack)
        sorte = client.post("/api/v1/seeds", json={
            "name": "Gartenkresse", "keimdauer_tage": 3, "wachstumsdauer_tage": 3,
            "erntefenster_min_tage": 6, "erntefenster_optimal_tage": 7,
            "erntefenster_max_tage": 8, "ertrag_gramm_pro_tray": 350,
        }).json()
        abo_id = _b6_abo_db(kunde["id"], [
            # Variante ohne product_id: Name über das Elternprodukt
            {"product_variant_id": kiste["id"], "menge": 1, "einheit": "KISTE_12"},
            {"seed_id": sorte["id"], "menge": 100, "einheit": "G"},
            {"menge": 1},
        ])

        assert [b for _, b, _, _ in _b6_positionen(abo_id)] == [
            "BIO Snackbox | Amaranth — 12er Mehrwegkiste", "Gartenkresse", None,
        ]

    def test_kopf_spiegelt_die_erste_position(self, client):
        from app.models.customer import Subscription
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(
            kunde["id"],
            [{"product_id": kresse["id"], "menge": 3, "einheit": "SCHALE"},
             {"product_id": snack["id"], "menge": 2}],
            product_id=uuid.UUID(snack["id"]), menge=Decimal("9"), einheit="STUECK",
        )
        with TestingSessionLocal() as db:
            sub = db.get(Subscription, uuid.UUID(abo_id))
            sub.kopf_aus_erster_position()
            db.commit()
            assert (str(sub.product_id), sub.menge, sub.einheit) == (
                kresse["id"], Decimal("3.00"), "SCHALE")

    def test_abo_loeschen_loescht_seine_positionen(self, client):
        from sqlalchemy import func, select
        from app.models.customer import Subscription, SubscriptionItem
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo_id = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2}] * 2)
        with TestingSessionLocal() as db:
            db.delete(db.get(Subscription, uuid.UUID(abo_id)))
            db.commit()
            assert db.execute(select(func.count()).select_from(SubscriptionItem)).scalar() == 0

    def test_kunde_ohne_belege_loeschen_nimmt_abo_und_positionen_mit(self, client):
        """DELETE /customers löscht Kunden ohne Bestellungen und Rechnungen hart
        (Paket 3, Q5.1); das Abo hängt per ORM-Kaskade daran."""
        from sqlalchemy import func, select
        from app.models.customer import SubscriptionItem
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2}])

        r = client.delete(f"/api/v1/sales/customers/{kunde['id']}")

        assert r.status_code == 204, r.text
        with TestingSessionLocal() as db:
            assert db.execute(select(func.count()).select_from(SubscriptionItem)).scalar() == 0
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_b6_abo_positionen.py -q -p no:cacheprovider`
Erwartet: **5 failed**, jeder mit `ImportError: cannot import name 'SubscriptionItem' from 'app.models.customer'`.

- [ ] **Step 3: Beziehung `positionen` an `Subscription`**

In `backend/app/models/customer.py`, Klasse `Subscription`, die Zeile (im Bestand genau einmal vorhanden)

```python
    product: Mapped[Optional["Product"]] = relationship("Product", foreign_keys=[product_id])
```

ersetzen durch:

```python
    product: Mapped[Optional["Product"]] = relationship("Product", foreign_keys=[product_id])
    # B6 (Gernot, 08.10.2026): mehrere Produkte je Lieferung. Seit B6 liest
    # der Abo-Lauf nur noch die Positionen; product_id, product_variant_id,
    # seed_id, menge und einheit oben spiegeln Position 1 (NOT NULL im
    # Bestandsschema, Altleser wie die Prognose).
    positionen: Mapped[list["SubscriptionItem"]] = relationship(
        "SubscriptionItem",
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by="SubscriptionItem.position",
    )
```

- [ ] **Step 4: `kopf_aus_erster_position` und Klasse `SubscriptionItem`**

In derselben Datei den `__repr__` von `Subscription`

```python
    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, kunde_id={self.kunde_id})>"
```

ersetzen durch (enthält den unveränderten `__repr__` und danach die neue Klasse):

```python
    def kopf_aus_erster_position(self) -> None:
        """Kopf-Spiegel: product_id, product_variant_id, seed_id, menge und
        einheit des Abos = Position 1. Ohne Positionen bleibt der Kopf."""
        if not self.positionen:
            return
        erste = self.positionen[0]
        self.product_id = erste.product_id
        self.product_variant_id = erste.product_variant_id
        self.seed_id = erste.seed_id
        self.menge = erste.menge
        self.einheit = erste.einheit

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, kunde_id={self.kunde_id})>"


class SubscriptionItem(Base):
    """Position eines Abos (B6): Produkt bzw. Verpackungsvariante, Menge, Einheit.

    Der Abo-Lauf legt je Abo und Liefertag EINE Bestellung mit allen
    Positionen an (subscription_tasks.abo_positionen). Kein Preisfeld: Der
    Preis kommt wie in create_order aus Sonderpreis, Variante und Basispreis.
    Paket 3 (Q4) lässt Abos für die Halle offen, weil sie keine Preise tragen.
    seed_id nur für Legacy-Abos über die Sorte (Migration, Mandanten ohne
    Produkte).
    """
    __tablename__ = "subscription_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="SET NULL")
    )
    product_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    seed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("seeds.id"), nullable=True
    )
    menge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    einheit: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="positionen")
    product: Mapped[Optional["Product"]] = relationship("Product", foreign_keys=[product_id])
    variante: Mapped[Optional["ProductVariant"]] = relationship(
        "ProductVariant", foreign_keys=[product_variant_id]
    )
    seed: Mapped[Optional["Seed"]] = relationship("Seed")

    @property
    def bezeichnung(self) -> Optional[str]:
        """Anzeigename wie die Bestellposition: "Produkt — Variante", sonst die Sorte."""
        produkt = self.product or (self.variante.parent_product if self.variante else None)
        if produkt is not None:
            if self.variante is not None and self.variante.name_suffix:
                return f"{produkt.name} — {self.variante.name_suffix}"
            return produkt.name
        if self.seed is not None:
            return self.seed.name
        return None

    def __repr__(self) -> str:
        return f"<SubscriptionItem(subscription_id={self.subscription_id}, position={self.position})>"
```

Danach am Dateiende die Zeile

```python
from app.models.product import PriceList, Product
```

ersetzen durch:

```python
from app.models.product import PriceList, Product, ProductVariant
```

Prüfen: `grep -n 'class SubscriptionItem\|def kopf_aus_erster_position\|positionen: Mapped' backend/app/models/customer.py` → je genau ein Treffer; `grep -c 'relationship("Product", foreign_keys=\[product_id\])' backend/app/models/customer.py` → `2` (Abo und Position).

- [ ] **Step 5: Export**

In `backend/app/models/__init__.py` im Block `from app.models.customer import (` die Zeile `    Subscription,` um eine Zeile `    SubscriptionItem,` direkt darunter ergänzen, und in `__all__` unter `    "Subscription",` die Zeile `    "SubscriptionItem",`. Prüfen: `grep -n 'SubscriptionItem' backend/app/models/__init__.py` → 2 Treffer.

- [ ] **Step 6: Grün bestätigen**

Run: wie Step 2. Erwartet: **5 passed**.

- [ ] **Step 7: Umfeld**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260817.py tests/test_gernot_260821.py tests/test_gernot_261008_paket2.py tests/test_features.py tests/test_demo_reset_migration.py tests/test_demo_reset.py -q -p no:cacheprovider 2>&1 | tail -3`
Erwartet: einziger Fehlschlag `tests/test_features.py::TestFeatures::test_subscription_processing` (Baseline). Gemessen: `1 failed, 211 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/customer.py backend/app/models/__init__.py backend/tests/test_b6_abo_positionen.py
git commit -m "feat(abo): Positionen je Abo in eigener Tabelle subscription_items (B6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migration — Bestands-Abos bekommen ihren Kopf als Position 1

**Files:**
- Create: `backend/app/services/abo_positionen.py`
- Modify: `backend/app/tenancy.py` (`_auto_migrate`, neuer Block vor dem A3-Korrekturblock)
- Modify: `backend/tests/test_b6_abo_positionen.py` (Block anhängen)

**Interfaces:**
- Consumes: `Subscription.positionen`, `SubscriptionItem` (Task 1); `tenancy.provision_tenant`, `tenancy.registry`, `tenancy._auto_migrate`, `demo_reset_service.snapshot_demo_seed`/`reset_demo_from_seed`.
- Produces: `app.services.abo_positionen.positionen_nachtragen(db: Session) -> int` — committet nicht; Anzahl der nachgetragenen Abos.

**Review Focus (Task 2):** verlustfrei (alle fünf Kopffelder, auch inaktive Abos, auch Sorten-Abos); idempotent (zweiter Start legt nichts an); ein Abo mit Positionen bleibt unberührt, selbst wenn sein Kopf abweicht; der Demo-Reset (Golden Seed ohne Positionen) trägt sie nach. Die Tests laufen gegen eine echte Mandanten-DB-Datei in `tmp_path` (WAL, `foreign_keys=ON`) mit einem Schema **ohne** `subscription_items`, wie in Produktion vor dem Deploy.

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_b6_abo_positionen.py` zwei Leerzeilen und dann anhängen:

```python
# ------------------------------------------------ Task 2: Migration

def _b6_mandant(tmp_path, monkeypatch, slug="b6alt"):
    """Mandanten-DB wie in Produktion (WAL, foreign_keys=ON) in tmp_path."""
    from app import tenancy
    monkeypatch.setattr(tenancy, "TENANTS_DIR", tmp_path)
    tenancy.registry.dispose_all()
    tenancy.provision_tenant(slug, seed_defaults=False)
    return tenancy.registry.get_engine(slug)


def _b6_bestand_vor_b6(engine):
    """Stand vor B6: drei Abos nur mit Kopf (Produkt, Variante, Sorte; eins
    inaktiv) und ein Schema ohne subscription_items."""
    from sqlalchemy.orm import Session
    from app.models.customer import Customer, CustomerType, Subscription, SubscriptionInterval
    from app.models.product import Product, ProductVariant
    from app.models.seed import Seed
    from app.models.unit import UnitOfMeasure, UnitCategory
    with Session(engine) as db:
        stk = UnitOfMeasure(code="STK", name="Stück", category=UnitCategory.COUNT)
        kiste = UnitOfMeasure(code="KISTE_12", name="Kiste", category=UnitCategory.COUNT)
        kunde = Customer(name="Gastro Süd", typ=CustomerType.GASTRO)
        db.add_all([stk, kiste, kunde])
        db.flush()
        tray = Product(sku="MG-14001", name="Gastrotray", category="MICROGREEN",
                       base_unit_id=stk.id, base_price=Decimal("18.00"))
        db.add(tray)
        db.flush()
        variante = ProductVariant(parent_product_id=tray.id, packaging_unit_id=kiste.id,
                                  name_suffix="12er Mehrwegkiste")
        sorte = Seed(name="Gartenkresse", keimdauer_tage=3, wachstumsdauer_tage=3,
                     erntefenster_min_tage=6, erntefenster_optimal_tage=7,
                     erntefenster_max_tage=8, ertrag_gramm_pro_tray=350)
        db.add_all([variante, sorte])
        db.flush()
        gemeinsam = dict(kunde_id=kunde.id, intervall=SubscriptionInterval.WOECHENTLICH,
                         liefertage=[1, 4], gueltig_von=_B6_MO)
        abos = [
            Subscription(product_id=tray.id, menge=Decimal("3"), einheit="STUECK", **gemeinsam),
            Subscription(product_id=tray.id, product_variant_id=variante.id,
                         menge=Decimal("1"), einheit="KISTE_12", **gemeinsam),
            Subscription(seed_id=sorte.id, menge=Decimal("150"), einheit="G",
                         aktiv=False, **gemeinsam),
        ]
        db.add_all(abos)
        db.commit()
        erwartet = {
            str(a.id): [(1, a.product_id, a.product_variant_id, a.seed_id, a.menge, a.einheit)]
            for a in abos
        }
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE subscription_items")
    return erwartet


def _b6_positionen_je_abo(engine):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models.customer import Subscription
    with Session(engine) as db:
        return {
            str(sub.id): [(p.position, p.product_id, p.product_variant_id, p.seed_id, p.menge, p.einheit)
                          for p in sub.positionen]
            for sub in db.execute(select(Subscription)).scalars().all()
        }


def _b6_start(engine):
    """Was init_all_existing_tenants und der Demo-Reset beim Start tun."""
    from app import tenancy
    from app.database import Base
    Base.metadata.create_all(bind=engine)
    tenancy._auto_migrate(engine)


class TestB6Migration:
    """Bestands-Abos verlustfrei: der Kopf wird Position 1, einmal."""

    def test_bestands_abos_bekommen_ihren_kopf_als_position_1(self, tmp_path, monkeypatch):
        from app import tenancy
        engine = _b6_mandant(tmp_path, monkeypatch)
        try:
            erwartet = _b6_bestand_vor_b6(engine)

            _b6_start(engine)

            assert _b6_positionen_je_abo(engine) == erwartet
        finally:
            tenancy.registry.dispose_all()

    def test_zweiter_start_legt_nichts_doppelt_an(self, tmp_path, monkeypatch):
        from app import tenancy
        engine = _b6_mandant(tmp_path, monkeypatch)
        try:
            erwartet = _b6_bestand_vor_b6(engine)

            _b6_start(engine)
            _b6_start(engine)

            assert _b6_positionen_je_abo(engine) == erwartet
        finally:
            tenancy.registry.dispose_all()

    def test_abo_mit_positionen_bleibt_unberuehrt(self, tmp_path, monkeypatch):
        """Nachgetragen wird nur bei Abos ohne Position; ein Abo mit zwei
        Positionen behält beide, auch wenn sein Kopf anders aussieht."""
        from sqlalchemy.orm import Session
        from app import tenancy
        from app.models.customer import Subscription, SubscriptionItem
        engine = _b6_mandant(tmp_path, monkeypatch)
        try:
            erwartet = _b6_bestand_vor_b6(engine)
            _b6_start(engine)
            abo_id = next(iter(erwartet))
            with Session(engine) as db:
                sub = db.get(Subscription, uuid.UUID(abo_id))
                sub.positionen.append(SubscriptionItem(
                    position=2, product_id=sub.product_id, menge=Decimal("5"), einheit="SCHALE"))
                db.commit()

            _b6_start(engine)

            positionen = _b6_positionen_je_abo(engine)[abo_id]
            assert [(p[0], p[4], p[5]) for p in positionen] == [
                (1, Decimal("3.00"), "STUECK"), (2, Decimal("5.00"), "SCHALE")]
        finally:
            tenancy.registry.dispose_all()

    def test_demo_reset_traegt_positionen_nach(self, tmp_path, monkeypatch):
        """Der Golden Seed (demo.seed.db) bleibt auf dem Stand vor B6; der
        Reset um 03:30 ruft create_all und _auto_migrate."""
        from app import tenancy
        from app.services.demo_reset_service import reset_demo_from_seed, snapshot_demo_seed
        engine = _b6_mandant(tmp_path, monkeypatch, slug="demo")
        try:
            erwartet = _b6_bestand_vor_b6(engine)
            snapshot_demo_seed("demo")

            ergebnis = reset_demo_from_seed("demo")

            assert ergebnis["migriert"] is True
            assert _b6_positionen_je_abo(tenancy.registry.get_engine("demo")) == erwartet
        finally:
            tenancy.registry.dispose_all()
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_b6_abo_positionen.py -q -p no:cacheprovider`
Erwartet: **4 failed, 5 passed.** Rot sind die vier `TestB6Migration`-Tests: drei mit `AssertionError: assert {'…': []} == {'…'…)]}` und darunter `Differing items:` je Abo `{'<id>': []} != {'<id>': [(1, UUID(…), …)]}` (keine Positionen nach dem Start), `test_abo_mit_positionen_bleibt_unberuehrt` mit `assert [(2, Decimal(...'), 'SCHALE')] == [(1, Decimal(...'), 'SCHALE')]` und darunter `At index 0 diff: (2, Decimal('5.00'), 'SCHALE') != (1, Decimal('3.00'), 'STUECK')` sowie `Right contains one more item: (2, Decimal('5.00'), 'SCHALE')` (Kopfzeilen von pytest gekürzt, siehe Stoppregel 2).

- [ ] **Step 3: Service anlegen**

`backend/app/services/abo_positionen.py` mit genau diesem Inhalt anlegen:

```python
"""Abo-Positionen (B6, Gernot 08.10.2026): Bestandsabos nachtragen.

Bis B6 trug ein Abo genau ein Produkt in seinen Kopffeldern (product_id,
product_variant_id, seed_id, menge, einheit). Seit B6 liest der Abo-Lauf nur
noch subscription_items. tenancy._auto_migrate ruft positionen_nachtragen bei
jedem Start und nach jedem Demo-Reset.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Subscription, SubscriptionItem


def positionen_nachtragen(db: Session) -> int:
    """Jedes Abo ohne Position bekommt seinen Kopf als Position 1.

    Idempotent: Abos mit mindestens einer Position bleiben unberührt. Auch
    inaktive Abos und Abos ohne Produkt und Sorte werden übernommen, so wie
    sie sind: verlustfrei, der Abo-Lauf überspringt Letztere wie bisher mit
    Meldung. Committet nicht.
    """
    ohne_position = db.execute(
        select(Subscription).where(~Subscription.positionen.any())
    ).scalars().all()
    for sub in ohne_position:
        sub.positionen.append(SubscriptionItem(
            position=1,
            product_id=sub.product_id,
            product_variant_id=sub.product_variant_id,
            seed_id=sub.seed_id,
            menge=sub.menge,
            einheit=sub.einheit,
        ))
    db.flush()
    return len(ohne_position)
```

- [ ] **Step 4: Aufruf in `_auto_migrate`**

In `backend/app/tenancy.py`, Funktion `_auto_migrate`, direkt **vor** der Kommentarzeile

```python
    # Einmalige Datenkorrektur (A3, 08.10.2026): Steuersatz offener
```

diesen Block einfügen (eine Leerzeile danach, Einrückung vier Leerzeichen wie die Nachbarblöcke):

```python
    # Abo-Positionen (B6): Bestands-Abos bekommen ihren Kopf (Produkt,
    # Variante, Sorte, Menge, Einheit) als Position 1 — nur Abos ohne
    # Position, also idempotent. Die Tabelle subscription_items legt
    # create_all an. Eigener try-Block; der Korrekturblock A3 bleibt der
    # letzte Block.
    try:
        from sqlalchemy.orm import Session as _AboSession
        from app.services.abo_positionen import positionen_nachtragen
        if inspector.has_table("subscriptions") and inspector.has_table("subscription_items"):
            with _AboSession(engine) as session:
                anzahl = positionen_nachtragen(session)
                session.commit()
            if anzahl:
                logger.info(f"[auto-migrate] Abo-Positionen für {anzahl} Abos nachgetragen")
    except Exception as e:
        logger.error(f"[auto-migrate] Abo-Positionen fehlgeschlagen: {e}")
```

Prüfen: `grep -n 'Abo-Positionen (B6)\|Einmalige Datenkorrektur (A3' backend/app/tenancy.py` → der B6-Block steht vor dem A3-Block; der A3-Block bleibt der letzte `try`-Block der Funktion.

- [ ] **Step 5: Grün bestätigen**

Run: wie Step 2. Erwartet: **9 passed.**

- [ ] **Step 6: Umfeld und Prozedur V**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_demo_reset_migration.py tests/test_demo_reset.py -q -p no:cacheprovider 2>&1 | tail -1` → alle passed.
Dann **Prozedur V**: keine Zeile im Abgleich.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/abo_positionen.py backend/app/tenancy.py backend/tests/test_b6_abo_positionen.py
git commit -m "feat(abo): Bestands-Abos bekommen ihren Kopf als Position 1, idempotent beim Start (B6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Abo-Lauf — eine Bestellung je Abo und Liefertag mit allen Positionen

**Files:**
- Modify: `backend/app/tasks/subscription_tasks.py` (`abo_position`, neue Funktion `abo_positionen`, `_create_order_from_subscription`)
- Modify: `backend/tests/test_b6_abo_positionen.py` (Block anhängen)

**Interfaces:**
- Consumes: `Subscription.positionen` (Task 1); unverändert aus Paket 2: `_abo_produkt(db, quelle)` (liest nur `product_variant_id`, `product_id`, `seed_id` — passt für Abo und Position), `resolve_unit_price`, `steuersatz_der_position`, `_abo_bestellung_vorhanden`, `abo_lauf`, `AboUebersprungen`.
- Produces:
  - `abo_position(db, sub, heute: date, quelle=None, nr: int = 1) -> OrderLine` — `quelle` = Abo-Position; ohne Angabe das Abo selbst (Kopf, Stand vor B6). Bisherige Aufrufe `abo_position(db, sub, heute)` verhalten sich wie vorher.
  - `abo_positionen(db, sub, heute: date) -> list[OrderLine]` — alle Positionen in Reihenfolge, Positionsnummern 1..n; ohne Positionen der Kopf (E7); wirft `AboUebersprungen` (bei mehreren Positionen mit Präfix `Position n: `), bevor etwas angelegt ist.

**Review Focus (Task 3):** Der Lauf liest die Positionen, nicht den Kopf (`test_lauf_liest_die_positionen_nicht_den_kopf`); eine kaputte Position verhindert die ganze Bestellung, der Lauf beliefert die anderen Abos und meldet „Position n: …"; ein zweiter Lauf am selben Tag legt nichts doppelt an; Pfand folgt der Pfandabrechnung des Kunden über `create_invoice_from_order`. `test_abo_ohne_position_liefert_seinen_kopf` ist schon vor diesem Task grün (Absicherung von E7).

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_b6_abo_positionen.py` zwei Leerzeilen und dann anhängen:

```python
# ------------------------------------------------ Task 3: Abo-Lauf

def _b6_zeilen(bestellung):
    return [(l["position"], l["beschreibung"], l["quantity"], l["unit"], l["unit_price"],
             l["tax_rate"], l["line_net"]) for l in bestellung["lines"]]


class TestB6AboLauf:
    """Eine Bestellung je Abo und Liefertag, mit allen Positionen."""

    def _drei_positionen(self, client, kunde):
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        kiste = _b6_variante(client, kresse, preis="30.00")
        pfand = _b6_pfandkiste(client)
        r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices", json={
            "product_id": snack["id"], "unit_price": "4.20", "valid_from": "2026-09-01",
        })
        assert r.status_code in (200, 201), r.text
        return [
            {"product_id": snack["id"], "menge": 2},
            {"product_id": kresse["id"], "product_variant_id": kiste["id"], "menge": 1},
            {"product_id": pfand["id"], "menge": 1},
        ]

    def test_eine_bestellung_mit_allen_positionen(self, client):
        kunde = _b6_kunde(client)
        abo_id = _b6_abo_db(kunde["id"], self._drei_positionen(client, kunde))

        ergebnis = _b6_lauf(_B6_DO)

        assert ergebnis["erstellt"] == 1
        [bestellung] = _b6_bestellungen(abo_id)
        assert bestellung["requested_delivery_date"] == _B6_DO
        # Sonderpreis vor Variantenpreis vor Basispreis, Satz aus dem Produktstamm,
        # Einheit der Variante (wie create_order und Paket 2, A5)
        assert _b6_zeilen(bestellung) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2.000"), "STUECK", Decimal("4.20"), "REDUZIERT", Decimal("8.40")),
            (2, "Kresse Schale — 12er Mehrwegkiste", Decimal("1.000"), "KISTE_12", Decimal("30.00"), "REDUZIERT", Decimal("30.00")),
            (3, "IFCO-Kiste", Decimal("1.000"), "STUECK", Decimal("4.00"), "STANDARD", Decimal("4.00")),
        ]
        assert bestellung["total_net"] == Decimal("42.40")

    def test_zweiter_lauf_am_selben_tag_legt_nichts_doppelt_an(self, client):
        kunde = _b6_kunde(client)
        abo_id = _b6_abo_db(kunde["id"], self._drei_positionen(client, kunde))

        _b6_lauf(_B6_DO)
        zweiter = _b6_lauf(_B6_DO)

        assert (zweiter["erstellt"], zweiter["bereits_vorhanden"]) == (0, 1)
        [bestellung] = _b6_bestellungen(abo_id)
        assert len(bestellung["lines"]) == 3

    def test_lauf_liest_die_positionen_nicht_den_kopf(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(kunde["id"], [{"product_id": kresse["id"], "menge": 2}],
                            product_id=uuid.UUID(snack["id"]), menge=Decimal("9"))

        _b6_anlegen(abo_id)

        [bestellung] = _b6_bestellungen(abo_id)
        assert [(l["product_id"], l["quantity"]) for l in bestellung["lines"]] == [
            (kresse["id"], Decimal("2.000"))]

    def test_abo_ohne_position_liefert_seinen_kopf(self, client):
        """Rückfall, falls das Nachtragen beim Start scheiterte (_auto_migrate
        loggt nur): Das Abo liefert weiter sein Kopfprodukt statt nichts."""
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo_id = _b6_abo_db(kunde["id"], [], product_id=uuid.UUID(snack["id"]),
                            menge=Decimal("2"), einheit="STUECK")

        _b6_anlegen(abo_id)

        [bestellung] = _b6_bestellungen(abo_id)
        assert _b6_zeilen(bestellung) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2.000"), "STUECK", Decimal("4.50"), "REDUZIERT", Decimal("9.00"))]

    def test_eine_kaputte_position_ueberspringt_das_ganze_abo(self, client):
        """Alles oder nichts: keine Teillieferung ohne Hinweis. Die Meldung nennt die Position."""
        from app.tasks.subscription_tasks import AboUebersprungen
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo_id = _b6_abo_db(kunde["id"], [
            {"product_id": snack["id"], "menge": 2},
            {"product_id": kresse["id"], "menge": 1},
        ])
        r = client.delete(f"/api/v1/products/{kresse['id']}")  # Soft-Delete: is_active = False
        assert r.status_code == 204, r.text

        with pytest.raises(AboUebersprungen, match="^Position 2: Produkt Kresse Schale ist deaktiviert$"):
            _b6_anlegen(abo_id)
        assert _b6_bestellungen() == []

    def test_lauf_meldet_das_kaputte_abo_und_beliefert_die_anderen(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        gut = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2},
                                       {"product_id": snack["id"], "menge": 1, "einheit": "SCHALE"}])
        kaputt = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2},
                                          {"menge": 1}])

        ergebnis = _b6_lauf(_B6_DO)

        assert ergebnis["erstellt"] == 1
        assert ergebnis["uebersprungen"] == [{
            "abo_id": kaputt, "kunde": "Café Kleinberger",
            "grund": "Position 2: Abo hat weder Produkt noch Sorte",
        }]
        assert len(_b6_bestellungen(gut)[0]["lines"]) == 2
        assert _b6_bestellungen(kaputt) == []


class TestB6Pfand:
    """Pfand aus dem Abo folgt der Pfandabrechnung des Kunden über die normalen
    Wege: Die Abo-Bestellung trägt die Pfandposition wie jede Bestellung, die
    Rechnung lässt sie bei IFCO-Clearing weg (invoice_service.ist_clearing_pfand),
    das Leergutkonto (MONATLICH) bucht beim Übergang nach GELIEFERT. Der Lauf
    selbst kennt pfand_abrechnung nicht."""

    def _rechnungszeilen(self, client, kunde):
        from sqlalchemy import select
        from app.models.invoice import InvoiceLine
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        pfand = _b6_pfandkiste(client)
        abo_id = _b6_abo_db(kunde["id"], [{"product_id": snack["id"], "menge": 2},
                                          {"product_id": pfand["id"], "menge": 2}])
        _b6_lauf(_B6_DO)
        [bestellung] = _b6_bestellungen(abo_id)
        assert [l["beschreibung"] for l in bestellung["lines"]] == [
            "BIO Snackbox | Amaranth", "IFCO-Kiste"]

        r = client.post(f"/api/v1/invoices/from-order/{bestellung['id']}")
        assert r.status_code == 201, r.text
        with TestingSessionLocal() as db:
            return [
                (l.description, l.is_deposit, l.tax_rate.value)
                for l in db.execute(select(InvoiceLine).where(
                    InvoiceLine.invoice_id == uuid.UUID(r.json()["id"]))).scalars().all()
            ]

    def test_ifco_clearing_pfand_steht_nicht_auf_der_rechnung(self, client):
        kunde = _b6_kunde(client, pfand_abrechnung="KEINE")
        assert self._rechnungszeilen(client, kunde) == [
            ("BIO Snackbox | Amaranth", False, "REDUZIERT")]

    def test_pfand_je_lieferung_steht_auf_der_rechnung(self, client):
        kunde = _b6_kunde(client, pfand_abrechnung="JE_LIEFERUNG")
        assert sorted(self._rechnungszeilen(client, kunde)) == [
            ("BIO Snackbox | Amaranth", False, "REDUZIERT"), ("IFCO-Kiste", True, "STANDARD")]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_b6_abo_positionen.py -q -p no:cacheprovider`
Erwartet: **7 failed, 10 passed.** Rot: `test_eine_bestellung_mit_allen_positionen` (nur Position 1 kommt an: „Right contains 2 more items"), `test_zweiter_lauf_am_selben_tag_legt_nichts_doppelt_an` (`assert 1 == 3`), `test_lauf_liest_die_positionen_nicht_den_kopf` (Kopfprodukt mit Menge 9 statt Positionsprodukt mit 2), `test_eine_kaputte_position_ueberspringt_das_ganze_abo` (`DID NOT RAISE`), `test_lauf_meldet_das_kaputte_abo_und_beliefert_die_anderen` (`assert 2 == 1`), beide `TestB6Pfand`-Tests (`Right contains one more item: 'IFCO-Kiste'`). Grün bleibt u. a. `test_abo_ohne_position_liefert_seinen_kopf`.

- [ ] **Step 3: `abo_position` verallgemeinern, `abo_positionen` neu**

In `backend/app/tasks/subscription_tasks.py` den ganzen Bereich ab `def abo_position(db, sub, heute: date) -> OrderLine:` bis **vor** `def liefertag_heute() -> date:` ersetzen durch (zwei Leerzeilen vor `def liefertag_heute` bleiben):

```python
def abo_position(db, sub, heute: date, quelle=None, nr: int = 1) -> OrderLine:
    """Bestellposition `nr` einer Abo-Lieferung an `heute`.

    `quelle` ist die Abo-Position (SubscriptionItem, B6); ohne Angabe das Abo
    selbst (Kopffelder, Stand vor B6). Produkt, Variante, Sorte, Menge und
    Einheit kommen aus der Quelle, der Kunde aus dem Abo.

    Preis wie in create_order (sales.py, Positionsschleife): Sonderpreis des
    Kunden (resolve_unit_price, Stichtag = Liefertag) vor Variantenpreis vor
    Basispreis. Steuersatz aus dem Produktstamm. Einheit der Variante, sonst
    die der Position. Wirft AboUebersprungen, bevor etwas angelegt ist.
    """
    from app.api.v1.sales import _calculate_line_amounts

    quelle = sub if quelle is None else quelle
    produkt, variante = _abo_produkt(db, quelle)

    preis, ist_sonderpreis = resolve_unit_price(
        db, customer_id=sub.kunde_id, product_id=produkt.id,
        default=produkt.base_price, on_date=heute,
    )
    name = produkt.name
    einheit = quelle.einheit
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
        position=nr,
        product_id=produkt.id,
        product_variant_id=variante.id if variante is not None else None,
        seed_id=quelle.seed_id,
        beschreibung=name,
        # Durchgehend Decimal: Decimal * float wirft.
        quantity=Decimal(str(quelle.menge)),
        unit=einheit,
        unit_price=Decimal(str(preis or 0)),
        tax_rate=steuersatz_der_position(
            db, produkt.id, variante.id if variante is not None else None, None
        ),
        requested_delivery_date=heute,
    )
    _calculate_line_amounts(line)
    return line


def abo_positionen(db, sub, heute: date) -> list[OrderLine]:
    """Alle Bestellpositionen einer Abo-Lieferung an `heute` (B6).

    Quelle sind die Abo-Positionen (subscription_items) in ihrer Reihenfolge.
    Ein Abo ohne Position, etwa wenn das Nachtragen beim Start scheiterte
    (tenancy._auto_migrate loggt nur), liefert seinen Kopf wie vor B6.

    Alles oder nichts: Scheitert eine Position, wirft die Funktion
    AboUebersprungen, bevor etwas angelegt ist, und das ganze Abo fällt für
    diesen Tag aus. Eine Teillieferung ohne Hinweis wäre schlimmer als eine
    gemeldete ausgefallene Lieferung. Bei mehreren Positionen nennt die
    Meldung die Position ("Position 2: Produkt … ist deaktiviert").
    """
    quellen = list(getattr(sub, "positionen", None) or [])
    if not quellen:
        if hasattr(sub, "positionen"):
            logger.warning("[abo] Abo %s hat keine Position, liefert den Kopf", sub.id)
        quellen = [sub]
    zeilen = []
    for nr, quelle in enumerate(quellen, start=1):
        try:
            zeilen.append(abo_position(db, sub, heute, quelle, nr))
        except AboUebersprungen as grund:
            if len(quellen) > 1:
                raise AboUebersprungen(f"Position {nr}: {grund}") from grund
            raise
    return zeilen
```

- [ ] **Step 4: `_create_order_from_subscription` hängt alle Positionen an**

In derselben Datei, Funktion `_create_order_from_subscription`:

(a) den Docstring

```python
    """Erstellt eine Order aus einem Abo für den Liefertag `heute`.

    Wirft AboUebersprungen, ohne etwas anzulegen, wenn kein eindeutiges
    Produkt feststeht.
    """
```

ersetzen durch:

```python
    """Erstellt eine Order aus einem Abo für den Liefertag `heute`, mit
    einer Bestellposition je Abo-Position (B6).

    Wirft AboUebersprungen, ohne etwas anzulegen, wenn für eine Position kein
    eindeutiges Produkt feststeht.
    """
```

(b) die Zeilen

```python
    # Zuerst die Position: steht kein Produkt fest, entsteht auch kein Kopf.
    line = abo_position(db, sub, heute)
```

ersetzen durch:

```python
    # Zuerst die Positionen: steht für eine kein Produkt fest, entsteht auch
    # kein Kopf (alles oder nichts, abo_positionen).
    zeilen = abo_positionen(db, sub, heute)
```

(c) die Zeile `    order.lines.append(line)` (direkt vor `    _calculate_order_totals(order)`) ersetzen durch:

```python
    for line in zeilen:
        order.lines.append(line)
```

Prüfen: `grep -n 'abo_position(\|abo_positionen(\|order.lines.append' backend/app/tasks/subscription_tasks.py` → `def abo_position(`, `def abo_positionen(`, der Aufruf `abo_position(db, sub, heute, quelle, nr)` in `abo_positionen`, der Aufruf `abo_positionen(db, sub, heute)` in `_create_order_from_subscription`, genau ein `order.lines.append(line)`.

- [ ] **Step 5: Grün bestätigen**

Run: wie Step 2. Erwartet: **17 passed.**

- [ ] **Step 6: Umfeld**

Run: wie Task 1 Step 7. Erwartet: einziger Fehlschlag `test_features.py::TestFeatures::test_subscription_processing`. (Die `_FakeSub`-Tests in `test_gernot_260817.py` haben kein Attribut `positionen` und laufen über den Kopf-Rückfall; alle Paket-2-Abo-Tests bleiben grün.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks/subscription_tasks.py backend/tests/test_b6_abo_positionen.py
git commit -m "feat(abo): Abo-Lauf legt eine Bestellung mit allen Positionen an, alles oder nichts (B6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Schnittstelle — Positionen anlegen, ändern, lesen

**Files:**
- Modify: `backend/app/schemas/customer.py` (Import `model_validator`; Bereich `SubscriptionCreate`/`SubscriptionUpdate`; `SubscriptionResponse`)
- Modify: `backend/app/api/v1/sales.py` (Importe; Abo-Bereich von `# ============== Subscription Endpoints ==============` bis vor `@router.post("/subscriptions/process-today"`)
- Modify: `backend/tests/test_gernot_261008_paket2.py` (`TestP4AboPosition.test_variables_bundle_wird_uebersprungen`)
- Modify: `backend/tests/test_b6_abo_positionen.py` (Block anhängen)

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `SubscriptionPositionIn` (`product_id`, `product_variant_id`, `seed_id` optional; `menge > 0`; `einheit` 1–20 Zeichen; `extra="forbid"`), `SubscriptionPositionResponse` (`id`, `position`, `product_id`, `product_variant_id`, `seed_id`, `menge`, `einheit`, `bezeichnung`).
  - `SubscriptionCreate.positionen: Optional[list[SubscriptionPositionIn]]` (1–50), `menge`/`einheit` jetzt optional, `einheit` 1–20 Zeichen wie in `SubscriptionPositionIn` (E9); Validator: entweder `positionen` oder Einzelfelder (sonst 422); `als_positionen()`.
  - `SubscriptionUpdate.positionen` (1–50, ersetzt die Liste), `einheit` 1–20 Zeichen (E9); Validator: nicht zusammen mit `menge`/`einheit` (422).
  - `SubscriptionResponse.positionen: list[SubscriptionPositionResponse]`.
  - `sales._abo_positionen_bauen(db, positionen) -> list[SubscriptionItem]` (400/404 mit den Texten aus `_abo_produkt`, bei mehreren Positionen mit Präfix `Position n: `; Variante ohne `product_id` bekommt ihr Elternprodukt), `sales._abo_laden(db, sub_id)`, `sales._abo_antwort(sub)`, `sales._ABO_LADEN`.
- API (unverändert die Pfade): `GET/POST /api/v1/sales/subscriptions`, `PATCH /api/v1/sales/subscriptions/{id}`; `POST …/process-today` unberührt.

**Review Focus (Task 4):** 422 bei Preisfeld (E1); Einheit über die Einzelfelder länger als 20 Zeichen → 422, kein 500 (E9); unbrauchbare Position → nichts gespeichert; ungültiger PATCH lässt das Abo unverändert (erst prüfen, dann ändern); alte Einzelfelder funktionieren für Abos mit einer Position (alter Browser-Tab, `test_gernot_260821.py`), bei mehreren Positionen klare 400; Rechte unverändert (E6).

- [ ] **Step 1: Tests anhängen**

Ans Ende von `backend/tests/test_b6_abo_positionen.py` zwei Leerzeilen und dann anhängen:

```python
# ------------------------------------------------ Task 4: Schnittstelle

def _b6_abo_api(client, kunde, positionen=None, erwartet=201, **felder):
    body = {"kunde_id": kunde["id"], "intervall": "WOECHENTLICH", "liefertage": [0, 3],
            "gueltig_von": _B6_MO.isoformat(), **felder}
    if positionen is not None:
        body["positionen"] = positionen
    r = client.post("/api/v1/sales/subscriptions", json=body)
    assert r.status_code == erwartet, r.text
    return r.json()


def _b6_kurz(antwort):
    """(position, bezeichnung, menge, einheit) aus einer API-Antwort."""
    return [(p["position"], p["bezeichnung"], Decimal(str(p["menge"])), p["einheit"])
            for p in antwort["positionen"]]


class TestB6Schnittstelle:
    """POST/PATCH/GET /sales/subscriptions mit Positionen; alte Einzelfelder bleiben gültig."""

    def test_anlegen_mit_positionen(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        kiste = _b6_variante(client, kresse, preis="30.00")
        pfand = _b6_pfandkiste(client)

        abo = _b6_abo_api(client, kunde, [
            {"product_id": snack["id"], "menge": 2, "einheit": "STUECK"},
            # Variante ohne product_id: die API ergänzt das Elternprodukt
            {"product_variant_id": kiste["id"], "menge": 1, "einheit": "KISTE_12"},
            {"product_id": pfand["id"], "menge": 1, "einheit": "STUECK"},
        ])

        assert _b6_kurz(abo) == [
            (1, "BIO Snackbox | Amaranth", Decimal("2"), "STUECK"),
            (2, "Kresse Schale — 12er Mehrwegkiste", Decimal("1"), "KISTE_12"),
            (3, "IFCO-Kiste", Decimal("1"), "STUECK"),
        ]
        assert abo["positionen"][1]["product_id"] == kresse["id"]
        # Kopf = Position 1 (Altleser: Liste, Prognose)
        assert (abo["product_id"], Decimal(str(abo["menge"])), abo["einheit"], abo["product_name"]) == (
            snack["id"], Decimal("2"), "STUECK", "BIO Snackbox | Amaranth")
        assert _b6_kurz(client.get("/api/v1/sales/subscriptions").json()["items"][0]) == _b6_kurz(abo)

    def test_anlegen_wie_bisher_mit_einem_produkt(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")

        abo = _b6_abo_api(client, kunde, product_id=snack["id"], menge=2, einheit="KISTE_6")

        assert _b6_kurz(abo) == [(1, "BIO Snackbox | Amaranth", Decimal("2"), "KISTE_6")]

    def test_abo_aus_der_schnittstelle_wird_beliefert(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo = _b6_abo_api(client, kunde, [
            {"product_id": snack["id"], "menge": 2, "einheit": "STUECK"},
            {"product_id": kresse["id"], "menge": 3, "einheit": "SCHALE"},
        ])

        _b6_lauf(_B6_DO)

        [bestellung] = _b6_bestellungen(abo["id"])
        assert [(l["beschreibung"], l["quantity"], l["unit"]) for l in bestellung["lines"]] == [
            ("BIO Snackbox | Amaranth", Decimal("2.000"), "STUECK"),
            ("Kresse Schale", Decimal("3.000"), "SCHALE"),
        ]

    @pytest.mark.parametrize("felder", [
        {},                                                    # nichts
        {"positionen": []},                                    # leere Liste
        {"menge": 2, "einheit": "STUECK"},                     # ohne Produkt
    ])
    def test_ohne_position_wird_abgelehnt(self, client, felder):
        kunde = _b6_kunde(client)
        body = {"kunde_id": kunde["id"], "intervall": "WOECHENTLICH",
                "gueltig_von": _B6_MO.isoformat(), **felder}
        r = client.post("/api/v1/sales/subscriptions", json=body)
        assert r.status_code in (400, 422), r.text

    def test_positionen_und_einzelprodukt_zugleich_werden_abgelehnt(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        _b6_abo_api(client, kunde, [{"product_id": snack["id"], "menge": 2, "einheit": "STUECK"}],
                    erwartet=422, product_id=snack["id"], menge=1, einheit="STUECK")

    def test_einzelfelder_pruefen_die_einheit_wie_eine_position(self, client):
        """Einheit 1-20 Zeichen auch über die alten Einzelfelder: 422 statt 500
        (Review 09.10.) und keine Einheit, mit der das Formular das Abo danach
        nicht mehr speichern könnte."""
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")

        fehler = _b6_abo_api(client, kunde, erwartet=422, product_id=snack["id"], menge=1, einheit="X" * 21)
        assert [(f["type"], f["loc"][-1]) for f in fehler["detail"]] == [("string_too_long", "einheit")]

        abo = _b6_abo_api(client, kunde, product_id=snack["id"], menge=2, einheit="STUECK")
        r = client.patch(f"/api/v1/sales/subscriptions/{abo['id']}", json={"einheit": "X" * 21})
        assert r.status_code == 422, r.text
        assert _b6_positionen(abo["id"]) == [(1, "BIO Snackbox | Amaranth", Decimal("2.00"), "STUECK")]

    def test_position_mit_preis_wird_abgelehnt(self, client):
        """Abos tragen keine Preise (Paket 3, Q4): Darum dürfen auch Mitarbeiter
        sie anlegen. Ein Preisfeld in einer Position ist ein Fehler, kein
        stilles Weglassen."""
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        fehler = _b6_abo_api(client, kunde, [{"product_id": snack["id"], "menge": 2, "einheit": "STUECK",
                                              "unit_price": "1.00"}], erwartet=422)
        assert [(f["type"], f["loc"][-1]) for f in fehler["detail"]] == [("extra_forbidden", "unit_price")]

    def test_unbrauchbare_positionen_werden_beim_speichern_abgelehnt(self, client):
        """Was der Lauf nie liefern kann, lehnt schon die Schnittstelle ab."""
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        fremde_kiste = _b6_variante(client, kresse)
        tray = _b6_produkt(client, "Gastrotray 4 Sorten", "B6-TRAY", "18.00",
                           is_variable_bundle=True, variable_bundle_min_slots=4,
                           variable_bundle_max_slots=4)
        alt = _b6_produkt(client, "Alte Kresse", "B6-ALT", "3.00")
        assert client.delete(f"/api/v1/products/{alt['id']}").status_code == 204
        gut = {"product_id": snack["id"], "menge": 1, "einheit": "STUECK"}
        fremd = str(uuid.uuid4())

        faelle = [
            ({"product_id": snack["id"], "product_variant_id": fremde_kiste["id"],
              "menge": 1, "einheit": "KISTE_12"}, 400, "Position 2: Variante gehört nicht zum gewählten Produkt"),
            ({"product_id": tray["id"], "menge": 1, "einheit": "STUECK"}, 400,
             "Position 2: Gastrotray 4 Sorten ist ein variables Bundle und braucht eine Sortenauswahl"),
            ({"product_id": alt["id"], "menge": 1, "einheit": "STUECK"}, 400,
             "Position 2: Produkt Alte Kresse ist deaktiviert"),
            ({"product_id": fremd, "menge": 1, "einheit": "STUECK"}, 404,
             f"Position 2: Produkt {fremd} nicht gefunden"),
            ({"menge": 1, "einheit": "STUECK"}, 400, "Position 2: Bitte Produkt oder Saatgut auswählen"),
        ]
        for position, code, text in faelle:
            r = client.post("/api/v1/sales/subscriptions", json={
                "kunde_id": kunde["id"], "intervall": "WOECHENTLICH",
                "gueltig_von": _B6_MO.isoformat(), "positionen": [gut, position],
            })
            assert (r.status_code, r.json().get("detail")) == (code, text)
        assert client.get("/api/v1/sales/subscriptions").json()["total"] == 0

    def test_positionen_aendern_ersetzt_die_liste(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        kresse = _b6_produkt(client, "Kresse Schale", "B6-KRESSE", "3.00")
        abo = _b6_abo_api(client, kunde, product_id=snack["id"], menge=2, einheit="STUECK")

        r = client.patch(f"/api/v1/sales/subscriptions/{abo['id']}", json={"positionen": [
            {"product_id": kresse["id"], "menge": 4, "einheit": "SCHALE"},
            {"product_id": snack["id"], "menge": 1, "einheit": "STUECK"},
        ]})

        assert r.status_code == 200, r.text
        assert _b6_kurz(r.json()) == [
            (1, "Kresse Schale", Decimal("4"), "SCHALE"),
            (2, "BIO Snackbox | Amaranth", Decimal("1"), "STUECK"),
        ]
        assert (r.json()["product_name"], Decimal(str(r.json()["menge"]))) == ("Kresse Schale", Decimal("4"))
        assert _b6_positionen(abo["id"]) == [
            (1, "Kresse Schale", Decimal("4.00"), "SCHALE"),
            (2, "BIO Snackbox | Amaranth", Decimal("1.00"), "STUECK"),
        ]

    def test_ungueltige_aenderung_laesst_das_abo_unveraendert(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo = _b6_abo_api(client, kunde, product_id=snack["id"], menge=2, einheit="STUECK")

        r = client.patch(f"/api/v1/sales/subscriptions/{abo['id']}", json={
            "intervall": "TAEGLICH",
            "positionen": [{"product_id": str(uuid.uuid4()), "menge": 1, "einheit": "STUECK"}],
        })

        assert r.status_code == 404, r.text
        nachher = client.get("/api/v1/sales/subscriptions").json()["items"][0]
        assert nachher["intervall"] == "WOECHENTLICH"
        assert _b6_kurz(nachher) == [(1, "BIO Snackbox | Amaranth", Decimal("2"), "STUECK")]

    def test_menge_wie_bisher_aendert_die_einzige_position(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo = _b6_abo_api(client, kunde, product_id=snack["id"], menge=2, einheit="STUECK")

        r = client.patch(f"/api/v1/sales/subscriptions/{abo['id']}", json={"menge": 5, "einheit": "SCHALE"})

        assert r.status_code == 200, r.text
        assert _b6_kurz(r.json()) == [(1, "BIO Snackbox | Amaranth", Decimal("5"), "SCHALE")]

    def test_menge_wie_bisher_bei_mehreren_positionen_wird_abgelehnt(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo = _b6_abo_api(client, kunde, [
            {"product_id": snack["id"], "menge": 2, "einheit": "STUECK"},
            {"product_id": snack["id"], "menge": 1, "einheit": "SCHALE"},
        ])

        r = client.patch(f"/api/v1/sales/subscriptions/{abo['id']}", json={"menge": 5})

        assert r.status_code == 400, r.text
        assert r.json()["detail"] == (
            "Das Abo hat mehrere Positionen. Menge und Einheit bitte je Position ändern.")

    def test_deaktivieren_behaelt_die_positionen(self, client):
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")
        abo = _b6_abo_api(client, kunde, [
            {"product_id": snack["id"], "menge": 2, "einheit": "STUECK"},
            {"product_id": snack["id"], "menge": 1, "einheit": "SCHALE"},
        ])

        r = client.patch(f"/api/v1/sales/subscriptions/{abo['id']}", json={"aktiv": False})

        assert r.status_code == 200, r.text
        assert len(r.json()["positionen"]) == 2

    def test_rechte_wie_bisher_auch_die_halle_legt_abos_an(self, client):
        """Abos hängen am Router sales (_deps_auftraege in main.py): alle fünf
        Rollen lesen und schreiben, wie vor B6. Die Oberfläche zeigt der Halle
        die Abo-Seite nicht (Layout.tsx). Ohne Preisfeld bleibt das so (Paket 3, Q4)."""
        from app.api.deps import get_current_user
        from app.main import app
        kunde = _b6_kunde(client)
        snack = _b6_produkt(client, "BIO Snackbox | Amaranth", "B6-SNACK", "4.50")

        async def halle():
            return {"id": "123e4567-e89b-12d3-a456-426614174077", "username": "halle",
                    "email": "halle@example.com", "roles": ["production_staff"]}
        app.dependency_overrides[get_current_user] = halle

        abo = _b6_abo_api(client, kunde, [{"product_id": snack["id"], "menge": 2, "einheit": "STUECK"}])
        assert len(abo["positionen"]) == 1
        fehler = _b6_abo_api(client, kunde, [{"product_id": snack["id"], "menge": 2, "einheit": "STUECK",
                                              "unit_price": "0.01"}], erwartet=422)
        assert [(f["type"], f["loc"][-1]) for f in fehler["detail"]] == [("extra_forbidden", "unit_price")]
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_b6_abo_positionen.py -q -p no:cacheprovider`
Erwartet: **13 failed, 20 passed.** Rot sind alle `TestB6Schnittstelle`-Tests außer den drei Fällen von `test_ohne_position_wird_abgelehnt` (schon heute 422 bzw. 400 — Absicherung). Typische Meldungen: `422 == 201` mit `"loc":["body","menge"],"msg":"Field required"`, `KeyError: 'positionen'`, `[('missing', 'menge'), …] == [('extra_forbidden', 'unit_price')]`; `test_einzelfelder_pruefen_die_einheit_wie_eine_position` mit `assert 201 == 422` (heute wird die 21 Zeichen lange Einheit angenommen).

- [ ] **Step 3: Schemas**

In `backend/app/schemas/customer.py`:

(a) die Importzeile

```python
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
```

ersetzen durch:

```python
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator, model_validator
```

(b) den ganzen Bereich ab `class SubscriptionCreate(SubscriptionBase):` bis **vor** `class SubscriptionResponse(SubscriptionBase):` (heute die Klassen `SubscriptionCreate` und `SubscriptionUpdate`) ersetzen durch:

```python
class SubscriptionPositionIn(BaseModel):
    """Position eines Abos (B6): Produkt bzw. Verpackungsvariante, Menge, Einheit.

    Kein Preisfeld: Der Preis kommt im Abo-Lauf wie in create_order aus
    Sonderpreis, Variante und Basispreis. Paket 3 (Q4) lässt Abos für die
    Halle offen, weil sie keine Preise tragen. extra="forbid": ein
    mitgeschicktes unit_price o. ä. ist ein Fehler (422), kein stilles Weglassen.
    """
    model_config = ConfigDict(extra="forbid")

    product_id: Optional[UUID] = Field(None, description="Produkt-ID")
    product_variant_id: Optional[UUID] = Field(None, description="Verpackungs-Variante")
    seed_id: Optional[UUID] = Field(None, description="Saatgut-ID (Legacy)")
    menge: Decimal = Field(..., gt=0, description="Menge je Lieferung")
    einheit: str = Field(..., min_length=1, max_length=20, description="Einheit (STUECK, SCHALE, KISTE_12 …)")


class SubscriptionPositionResponse(BaseModel):
    """Position eines Abos in der Antwort (B6)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int
    product_id: Optional[UUID] = None
    product_variant_id: Optional[UUID] = None
    seed_id: Optional[UUID] = None
    menge: Decimal
    einheit: str
    # "Produkt — Variante" bzw. Sorte (SubscriptionItem.bezeichnung)
    bezeichnung: Optional[str] = None


class SubscriptionCreate(SubscriptionBase):
    """Schema zum Erstellen eines Abonnements.

    Seit B6 mit `positionen` (ein oder mehrere Produkte je Lieferung). Die
    Einzelfelder product_id/product_variant_id/seed_id mit menge und einheit
    gelten weiter und ergeben genau eine Position; beides zugleich ist ein
    Fehler (422).
    """
    kunde_id: UUID = Field(..., description="Kunden-ID")
    seed_id: Optional[UUID] = Field(None, description="Saatgut-ID (Legacy)")
    product_id: Optional[UUID] = Field(None, description="Produkt-ID")
    product_variant_id: Optional[UUID] = Field(None, description="Verpackungs-Variante")
    menge: Optional[Decimal] = Field(None, gt=0, description="Bestellmenge (ohne positionen)")
    # Grenzen wie SubscriptionPositionIn.einheit: als_positionen() baut daraus
    # eine Position, ein zu langer Wert wäre dort ein 500 statt 422.
    einheit: Optional[str] = Field(None, min_length=1, max_length=20, description="Einheit (ohne positionen)")
    positionen: Optional[list[SubscriptionPositionIn]] = Field(
        None, min_length=1, max_length=50, description="Positionen je Lieferung (B6)"
    )

    @model_validator(mode="after")
    def _positionen_oder_einzelprodukt(self):
        einzelfelder = (self.product_id, self.product_variant_id, self.seed_id, self.menge, self.einheit)
        if self.positionen is not None:
            if any(wert is not None for wert in einzelfelder):
                raise ValueError(
                    "Entweder positionen oder product_id/seed_id mit menge und einheit, nicht beides"
                )
        elif self.menge is None or not self.einheit:
            raise ValueError("Bitte mindestens eine Position angeben (positionen oder menge und einheit)")
        return self

    def als_positionen(self) -> list[SubscriptionPositionIn]:
        """Die Positionen des neuen Abos; die Einzelfelder ergeben genau eine."""
        if self.positionen is not None:
            return self.positionen
        return [SubscriptionPositionIn(
            product_id=self.product_id, product_variant_id=self.product_variant_id,
            seed_id=self.seed_id, menge=self.menge, einheit=self.einheit,
        )]


class SubscriptionUpdate(BaseModel):
    """Schema zum Aktualisieren eines Abonnements.

    `positionen` ersetzt die ganze Liste (B6). menge/einheit wie bisher ändern
    die einzige Position; bei mehreren Positionen antwortet die API mit 400.
    """
    menge: Optional[Decimal] = Field(None, gt=0)
    # Grenzen wie SubscriptionPositionIn.einheit: der Wert landet in der Position
    einheit: Optional[str] = Field(None, min_length=1, max_length=20)
    intervall: Optional[SubscriptionInterval] = None
    liefertage: Optional[list[int]] = None
    gueltig_bis: Optional[date] = None
    aktiv: Optional[bool] = None
    positionen: Optional[list[SubscriptionPositionIn]] = Field(None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def _positionen_oder_menge(self):
        if self.positionen is not None and (self.menge is not None or self.einheit is not None):
            raise ValueError("Entweder positionen oder menge/einheit ändern, nicht beides")
        return self
```

(c) in `class SubscriptionResponse(SubscriptionBase):` nach der Zeile `    product_name: Optional[str] = None` (letztes Feld der Klasse, direkt vor `class SubscriptionListResponse`) ergänzen:

```python

    # B6: alle Positionen; die Kopffelder oben spiegeln Position 1
    positionen: list[SubscriptionPositionResponse] = []
```

Prüfen: `grep -n '^class Subscription' backend/app/schemas/customer.py` → in dieser Reihenfolge `SubscriptionBase`, `SubscriptionPositionIn`, `SubscriptionPositionResponse`, `SubscriptionCreate`, `SubscriptionUpdate`, `SubscriptionResponse`, `SubscriptionListResponse`. `grep -c 'positionen: list\[SubscriptionPositionResponse\]' backend/app/schemas/customer.py` → 1. `grep -c 'einheit: .*min_length=1, max_length=20' backend/app/schemas/customer.py` → 3 (Position, Create, Update).

- [ ] **Step 4: Endpunkte**

In `backend/app/api/v1/sales.py`:

(a) Importe:
- `from sqlalchemy.orm import joinedload` → `from sqlalchemy.orm import joinedload, selectinload`
- In `from app.models.customer import Customer, CustomerType, Contact, CustomerAddress, AddressType, Subscription` am Zeilenende `, SubscriptionItem` ergänzen.
- Im Block `from app.schemas.customer import (` die Zeile `    SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse, SubscriptionListResponse` ersetzen durch die zwei Zeilen
  ```python
      SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse, SubscriptionListResponse,
      SubscriptionPositionIn,
  ```

(b) den ganzen Bereich ab der Zeile `# ============== Subscription Endpoints ==============` bis **vor** `@router.post("/subscriptions/process-today", status_code=status.HTTP_200_OK)` ersetzen durch (enthält `list_subscriptions`, `create_subscription`, `update_subscription` vollständig; `process_today_subscriptions` bleibt unverändert):

```python
# ============== Subscription Endpoints ==============

# Abo mit Kunde, Kopfnamen und allen Positionen samt Produkt, Variante, Sorte
_ABO_LADEN = (
    joinedload(Subscription.kunde),
    joinedload(Subscription.seed),
    joinedload(Subscription.product),
    selectinload(Subscription.positionen).options(
        joinedload(SubscriptionItem.product),
        joinedload(SubscriptionItem.variante).joinedload(ProductVariant.parent_product),
        joinedload(SubscriptionItem.seed),
    ),
)


def _abo_antwort(sub: Subscription) -> SubscriptionResponse:
    """Antwort mit Kunden- und Produktnamen; Positionen über from_attributes."""
    response = SubscriptionResponse.model_validate(sub)
    response.kunde_name = sub.kunde.name if sub.kunde else None
    response.seed_name = sub.seed.name if sub.seed else None
    # Produkt-Abos (Bundles/Kartons) haben kein seed — ohne product_name
    # fällt die UI auf die UUID zurück ("7f4322c5" statt "Genussmix Karton").
    response.product_name = sub.product.name if sub.product else None
    return response


def _abo_positionen_bauen(db: DBSession, positionen: list[SubscriptionPositionIn]) -> list[SubscriptionItem]:
    """Abo-Positionen prüfen und als SubscriptionItem 1..n bauen (B6).

    Abgelehnt wird, was der Abo-Lauf nie liefern könnte
    (subscription_tasks._abo_produkt): unbekanntes Produkt bzw. unbekannte
    Variante oder Sorte, eine Variante eines anderen Produkts, ein
    deaktiviertes Produkt, ein variables Bundle (braucht eine Sortenauswahl,
    die ein Abo nicht hat) und eine Position ohne Produkt und Sorte. Bei
    mehreren Positionen nennt die Meldung die Nummer ("Position 2: …").
    Eine Variante ohne product_id bekommt ihr Elternprodukt.
    """
    mehrere = len(positionen) > 1

    def ablehnen(code: int, text: str, nr: int):
        raise HTTPException(status_code=code, detail=f"Position {nr}: {text}" if mehrere else text)

    items = []
    for nr, pos in enumerate(positionen, start=1):
        product_id = pos.product_id
        if pos.product_variant_id:
            variante = db.get(ProductVariant, pos.product_variant_id)
            if variante is None:
                ablehnen(404, "Verpackungs-Variante nicht gefunden", nr)
            if product_id and variante.parent_product_id != product_id:
                ablehnen(400, "Variante gehört nicht zum gewählten Produkt", nr)
            product_id = variante.parent_product_id
        if product_id:
            produkt = db.get(Product, product_id)
            if produkt is None:
                ablehnen(404, f"Produkt {product_id} nicht gefunden", nr)
            if produkt.is_active is False:
                ablehnen(400, f"Produkt {produkt.name} ist deaktiviert", nr)
            if produkt.is_variable_bundle:
                ablehnen(400, f"{produkt.name} ist ein variables Bundle und braucht eine Sortenauswahl", nr)
        elif pos.seed_id:
            if db.get(Seed, pos.seed_id) is None:
                ablehnen(404, f"Saatgut {pos.seed_id} nicht gefunden", nr)
        else:
            ablehnen(400, "Bitte Produkt oder Saatgut auswählen", nr)
        items.append(SubscriptionItem(
            position=nr,
            product_id=product_id,
            product_variant_id=pos.product_variant_id,
            seed_id=pos.seed_id,
            menge=pos.menge,
            einheit=pos.einheit,
        ))
    return items


def _abo_laden(db: DBSession, sub_id: UUID) -> Optional[Subscription]:
    return db.execute(
        select(Subscription).options(*_ABO_LADEN).where(Subscription.id == sub_id)
    ).unique().scalar_one_or_none()


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_subscriptions(
    db: DBSession,
    pagination: Pagination,
    kunde_id: Optional[UUID] = None,
    aktiv: Optional[bool] = None
):
    """
    Abonnements abrufen.

    Filter:
    - **kunde_id**: Abos eines bestimmten Kunden
    - **aktiv**: Nur aktive Abos
    """
    query = select(Subscription).options(*_ABO_LADEN)

    if kunde_id:
        query = query.where(Subscription.kunde_id == kunde_id)
    if aktiv is not None:
        query = query.where(Subscription.aktiv == aktiv)

    # Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0

    # Paginated Results
    query = query.offset(pagination.offset).limit(pagination.page_size)
    subscriptions = db.execute(query).scalars().unique().all()

    return SubscriptionListResponse(items=[_abo_antwort(sub) for sub in subscriptions], total=total)


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(sub_data: SubscriptionCreate, db: DBSession):
    """
    Neues Abonnement anlegen.

    Wichtig für Forecasting: Regelmäßige Bestellungen werden automatisch
    in die Absatzprognose einbezogen.
    """
    # Validierung
    customer = db.get(Customer, sub_data.kunde_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Kunde nicht gefunden")

    # B6: ein oder mehrere Produkte je Lieferung. Die alten Einzelfelder
    # (product_id bzw. seed_id mit menge/einheit) ergeben genau eine Position.
    positionen = _abo_positionen_bauen(db, sub_data.als_positionen())
    payload = sub_data.model_dump(exclude={
        "positionen", "product_id", "product_variant_id", "seed_id", "menge", "einheit",
    })
    subscription = Subscription(**payload, positionen=positionen)
    subscription.kopf_aus_erster_position()
    db.add(subscription)
    db.commit()

    return _abo_antwort(_abo_laden(db, subscription.id))


@router.patch("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def update_subscription(sub_id: UUID, sub_data: SubscriptionUpdate, db: DBSession):
    """Abonnement aktualisieren. `positionen` ersetzt die ganze Liste (B6)."""
    subscription = _abo_laden(db, sub_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="Abonnement nicht gefunden")

    update_data = sub_data.model_dump(exclude_unset=True)
    update_data.pop("positionen", None)
    # Zuerst prüfen, dann ändern: eine abgelehnte Position lässt das Abo unverändert.
    neue_positionen = (
        _abo_positionen_bauen(db, sub_data.positionen) if sub_data.positionen is not None else None
    )
    einzeln = {feld: update_data.pop(feld) for feld in ("menge", "einheit") if feld in update_data}
    if einzeln and len(subscription.positionen) > 1:
        raise HTTPException(
            status_code=400,
            detail="Das Abo hat mehrere Positionen. Menge und Einheit bitte je Position ändern.",
        )

    for field, value in update_data.items():
        setattr(subscription, field, value)
    # Bis B6 änderte das Formular Menge und Einheit des Kopfes; bei einem Abo
    # mit einer Position gilt das weiter für diese Position.
    for feld, wert in einzeln.items():
        setattr(subscription, feld, wert)
        for position in subscription.positionen:
            setattr(position, feld, wert)
    if neue_positionen is not None:
        subscription.positionen = neue_positionen
        subscription.kopf_aus_erster_position()

    db.commit()

    # Produkt-Abos (Bundles/Kartons) haben kein seed. Ohne die Null-Prüfung
    # in _abo_antwort endete jedes Speichern und jedes Deaktivieren eines
    # Produkt-Abos in einem 500er — in der UI "Fehler beim Aktualisieren".
    return _abo_antwort(_abo_laden(db, sub_id))
```

Prüfen: `grep -n '^async def \(list\|create\|update\|process_today\)_subscription' backend/app/api/v1/sales.py` → vier Treffer; `grep -n '^def _abo_\|^_ABO_LADEN' backend/app/api/v1/sales.py` → `_ABO_LADEN`, `_abo_antwort`, `_abo_positionen_bauen`, `_abo_laden`; `grep -c 'response.seed_name = (seed.name if seed else' backend/app/api/v1/sales.py` → 0.

- [ ] **Step 5: Grün bestätigen**

Run: wie Step 2. Erwartet: **33 passed.**

- [ ] **Step 6: Paket-2-Test an E4 anpassen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_261008_paket2.py -q -p no:cacheprovider -k variables_bundle`
Erwartet (rot, gewollt): `1 failed` mit `AssertionError: {"detail":"Gastrotray 4 Sorten ist ein variables Bundle und braucht eine Sortenauswahl"}` / `assert 400 == 201`.

In `backend/tests/test_gernot_261008_paket2.py`, Methode `TestP4AboPosition.test_variables_bundle_wird_uebersprungen`, die Zeilen

```python
        tray = _p4_produkt(client, "Gastrotray 4 Sorten", "P4-TRAY", "18.00",
                           is_variable_bundle=True, variable_bundle_min_slots=4,
                           variable_bundle_max_slots=4)
        abo = _p4_abo(client, kunde, product_id=tray["id"])
```

ersetzen durch:

```python
        tray = _p4_produkt(client, "Gastrotray 4 Sorten", "P4-TRAY", "18.00")
        abo = _p4_abo(client, kunde, product_id=tray["id"])
        # Seit B6 lehnt schon das Anlegen ein variables Bundle ab; der Lauf
        # muss es trotzdem überspringen, wenn das Produkt erst danach eins wird.
        r = client.patch(f"/api/v1/products/{tray['id']}", json={
            "is_variable_bundle": True, "variable_bundle_min_slots": 4,
            "variable_bundle_max_slots": 4,
        })
        assert r.status_code == 200, r.text
```

Run: wie oben. Erwartet: `1 passed`.

- [ ] **Step 7: Umfeld und Prozedur V**

Run: wie Task 1 Step 7. Erwartet: einziger Fehlschlag `test_features.py::TestFeatures::test_subscription_processing`. Dann **Prozedur V**: keine Zeile im Abgleich (gemessen `14 failed, 1644 passed, 2 skipped, 1 error` auf `a08e102`).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/customer.py backend/app/api/v1/sales.py backend/tests/test_b6_abo_positionen.py backend/tests/test_gernot_261008_paket2.py
git commit -m "feat(abo): Positionen über die Schnittstelle anlegen, ersetzen und lesen; unbrauchbare Positionen beim Speichern abgelehnt (B6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Oberfläche — Positionsliste auf der Abo-Seite

**Files:**
- Modify: `frontend/src/types/index.ts` (`interface Subscription`, neu `SubscriptionPosition`)
- Modify: `frontend/src/services/api.ts` (`subscriptionsApi.create`/`update`, neu `SubscriptionPositionInput`)
- Replace: `frontend/src/pages/Abonnements.tsx` (ganze Datei)

**Interfaces:**
- Consumes: API aus Task 4 (`positionen` in Anfrage und Antwort, `bezeichnung`), `productsApi.listVariants`, `getErrorMessage` (`frontend/src/services/errors.ts`).
- Produces: `SubscriptionPosition`, `SubscriptionPositionInput`; Abo-Seite mit Positionsliste (Produkt, Variante, Menge, Einheit; „Position hinzufügen"; Entfernen, letzte Position gesperrt); Tabellenspalte „Positionen je Lieferung"; variable Bundles nicht wählbar; ein gespeichertes, nicht mehr wählbares Produkt erscheint ausgegraut mit seinem Namen (`produktOptionenFuer`); Schalter „Aktiv" im Bearbeiten-Dialog statt festem `aktiv: true` (E10).

**Review Focus (Task 5):** siehe „Review Focus" oben, Punkte 1–6. Keine Preisanzeige im Abo (E1), stattdessen der Hinweistext unter der Liste.

- [ ] **Step 1: Typen**

In `frontend/src/types/index.ts` den Anfang von `interface Subscription`

```ts
export interface Subscription {
  id: string
  kunde_id: string
  // Entweder Saatgut ODER Produkt-Abo — beide optional befüllt
  seed_id: string | null
  product_id?: string | null
  menge: number
  einheit: string
```

ersetzen durch:

```ts
/** Position eines Abos (B6): Produkt bzw. Variante, Menge, Einheit — kein Preis. */
export interface SubscriptionPosition {
  id: string
  position: number
  product_id: string | null
  product_variant_id: string | null
  /** Legacy: Sorten-Abo ohne Produkt */
  seed_id: string | null
  menge: number
  einheit: string
  /** "Produkt — Variante" bzw. Sorte */
  bezeichnung: string | null
}

export interface Subscription {
  id: string
  kunde_id: string
  // Kopf = Position 1 (B6); maßgeblich sind die Positionen
  seed_id: string | null
  product_id?: string | null
  product_variant_id?: string | null
  menge: number
  einheit: string
  positionen: SubscriptionPosition[]
```

- [ ] **Step 2: API-Client**

In `frontend/src/services/api.ts`:

(a) direkt vor der Zeile `// Subscriptions API` (über `export const subscriptionsApi = {`) einfügen:

```ts
/** Neue bzw. geänderte Abo-Position (B6). Kein Preisfeld: die API lehnt es mit 422 ab. */
export interface SubscriptionPositionInput {
  product_id?: string
  product_variant_id?: string
  seed_id?: string
  menge: number
  einheit: string
}

```

(b) in `subscriptionsApi` die Methoden `create` und `update` (von `  create: (data: {` bis einschließlich der Zeile `  }>) =>` von `update`)

```ts
  create: (data: {
    kunde_id: string
    product_id?: string
    seed_id?: string
    menge: number
    einheit: string
    intervall: 'TAEGLICH' | 'WOECHENTLICH' | 'ZWEIWOECHENTLICH' | 'MONATLICH'
    liefertage?: number[]
    gueltig_von: string
    gueltig_bis?: string
  }) =>
    api.post<Subscription>('/sales/subscriptions', data).then(r => r.data),

  update: (id: string, data: Partial<{
    menge: number
    einheit: string
    intervall: 'TAEGLICH' | 'WOECHENTLICH' | 'ZWEIWOECHENTLICH' | 'MONATLICH'
    liefertage: number[]
    gueltig_bis: string
    aktiv: boolean
  }>) =>
```

ersetzen durch:

```ts
  create: (data: {
    kunde_id: string
    intervall: 'TAEGLICH' | 'WOECHENTLICH' | 'ZWEIWOECHENTLICH' | 'MONATLICH'
    liefertage?: number[]
    gueltig_von: string
    gueltig_bis?: string
    positionen: SubscriptionPositionInput[]
  }) =>
    api.post<Subscription>('/sales/subscriptions', data).then(r => r.data),

  // positionen ersetzt die ganze Liste (B6)
  update: (id: string, data: Partial<{
    intervall: 'TAEGLICH' | 'WOECHENTLICH' | 'ZWEIWOECHENTLICH' | 'MONATLICH'
    liefertage: number[]
    gueltig_bis: string
    aktiv: boolean
    positionen: SubscriptionPositionInput[]
  }>) =>
```

- [ ] **Step 3: Rot bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: genau **2 Fehler**, beide in `src/pages/Abonnements.tsx`, beide `error TS2353: Object literal may only specify known properties` — einmal `'menge' does not exist in type 'Partial<{ intervall: …; positionen: SubscriptionPositionInput[]; }>'` (Aufruf von `updateMutation.mutate`), einmal `'product_id' does not exist in type '{ kunde_id: string; …; positionen: SubscriptionPositionInput[]; }'` (Aufruf von `createMutation.mutate`).

- [ ] **Step 4: Abo-Seite ersetzen**

Nur wenn die Vorbereitung den Hash `4f19b3072844da15bf00281a33fe823e49da21bc` bestätigt hat (sonst Stoppregel 4). `frontend/src/pages/Abonnements.tsx` vollständig durch diesen Inhalt ersetzen:

```tsx
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { subscriptionsApi, salesApi, seedsApi, productsApi } from '../services/api';
import { getErrorMessage } from '../services/errors';
import { PageHeader, FilterBar } from '../components/common/Layout';
import {
    Modal,
    EmptyState,
    Input,
    Combobox,
    useToast,
    InlineLoader,
    Badge,
} from '../components/ui';
import { Plus, RefreshCw, Calendar, User, Leaf, Trash2, Edit2, Play, X } from 'lucide-react';
import type { Subscription, SubscriptionPosition, Customer, Seed, SubscriptionInterval, ProductVariant } from '../types';

const INTERVAL_LABELS: Record<SubscriptionInterval, string> = {
    TAEGLICH: 'Täglich',
    WOECHENTLICH: 'Wöchentlich',
    ZWEIWOECHENTLICH: 'Zweiwöchentlich',
    MONATLICH: 'Monatlich',
};

const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

// Einheiten der Abo-Position (wie bisher im Formular)
const EINHEITEN: Array<{ value: string; label: string }> = [
    { value: 'GRAMM', label: 'Gramm' },
    { value: 'BUND', label: 'Bund' },
    { value: 'SCHALE', label: 'Schale' },
    { value: 'STUECK', label: 'Stück' },
    { value: 'TRAY', label: 'Tray (8 Schalen)' },
    { value: 'KISTE_12', label: 'Mehrwegkiste (12 Schalen)' },
    { value: 'KISTE_6', label: 'Mehrwegkiste (6 Schalen)' },
    { value: 'KARTON_6', label: 'Karton (6 Schalen)' },
];

const einheitLabel = (code: string) => EINHEITEN.find(e => e.value === code)?.label ?? code;

// Eine Zeile im Formular. Kein Preis: der Abo-Lauf nimmt Sonderpreis,
// Variantenpreis bzw. Basispreis wie das Bestellformular (B6).
interface PositionRow {
    product_id: string;
    product_variant_id: string;
    seed_id: string;
    menge: string;
    einheit: string;
    /** Anzeigename der gespeicherten Position (nur Bearbeiten), falls ihr Produkt nicht mehr wählbar ist */
    bisher?: string;
}

const leerePosition = (): PositionRow => ({
    product_id: '',
    product_variant_id: '',
    seed_id: '',
    menge: '',
    einheit: 'STUECK',
});

const heuteIso = () => new Date().toISOString().split('T')[0];

const leeresFormular = () => ({
    kunde_id: '',
    intervall: 'WOECHENTLICH' as SubscriptionInterval,
    liefertage: [] as number[],
    gueltig_von: heuteIso(),
    gueltig_bis: '',
    // Nur im Bearbeiten-Dialog sichtbar; Speichern ändert den Status nur über diesen Schalter
    aktiv: true,
    positionen: [leerePosition()],
});

// Positionen eines Abos für Tabelle und Dialoge; ohne Positionen (vor B6) der Kopf
const positionenVon = (sub: Subscription): Array<Pick<SubscriptionPosition, 'menge' | 'einheit' | 'bezeichnung'>> =>
    sub.positionen && sub.positionen.length > 0
        ? sub.positionen
        : [{ menge: sub.menge, einheit: sub.einheit, bezeichnung: sub.product_name || sub.seed_name || null }];

export default function Abonnements() {
    const toast = useToast();
    const queryClient = useQueryClient();

    // Filter state
    const [kundeFilter, setKundeFilter] = useState<string>('');
    const [aktivFilter, setAktivFilter] = useState<string>('');

    // Modal state
    const [isCreating, setIsCreating] = useState(false);
    const [editingSub, setEditingSub] = useState<Subscription | null>(null);
    const [deletingSub, setDeletingSub] = useState<Subscription | null>(null);

    // Form state
    const [formData, setFormData] = useState(leeresFormular);
    const [variantenJeProdukt, setVariantenJeProdukt] = useState<Record<string, ProductVariant[]>>({});

    // Data queries
    const { data: subscriptionsData, isLoading } = useQuery({
        queryKey: ['subscriptions', kundeFilter, aktivFilter],
        queryFn: () =>
            subscriptionsApi.list({
                kunde_id: kundeFilter || undefined,
                aktiv: aktivFilter === '' ? undefined : aktivFilter === 'true',
            }),
    });

    const { data: customersData } = useQuery({
        queryKey: ['customers', 'active'],
        queryFn: () => salesApi.listCustomers({ aktiv: true }),
    });

    const { data: productsData } = useQuery({
        queryKey: ['products', 'active'],
        queryFn: () => productsApi.list({ is_active: true }),
    });
    const products = productsData || [];
    // Variable Bundles (Gastrotray mit Sortenwahl) brauchen eine Auswahl je
    // Bestellung; ein Abo hat keine, die API lehnt sie ab.
    const produktOptionen = products
        .filter((p) => !p.is_variable_bundle)
        .map((p) => ({ value: p.id, label: `${p.is_bundle ? '📦 ' : ''}${p.name}` }));
    // Ein gespeichertes Produkt, das nicht mehr wählbar ist (deaktiviert oder
    // inzwischen variables Bundle), bleibt sichtbar statt eines leeren Felds.
    const produktOptionenFuer = (pos: PositionRow) =>
        !productsData || !pos.product_id || produktOptionen.some((o) => o.value === pos.product_id)
            ? produktOptionen
            : [
                { value: pos.product_id, label: pos.bisher || 'Bisheriges Produkt', hint: 'nicht mehr wählbar', disabled: true },
                ...produktOptionen,
            ];

    const { data: seedsData } = useQuery({
        queryKey: ['seeds', 'active'],
        queryFn: () => seedsApi.list({ aktiv: true }),
    });

    const ladeVarianten = async (productId: string) => {
        if (!productId || variantenJeProdukt[productId] !== undefined) return;
        try {
            const varianten = await productsApi.listVariants(productId);
            setVariantenJeProdukt((prev) => ({ ...prev, [productId]: varianten }));
        } catch {
            setVariantenJeProdukt((prev) => ({ ...prev, [productId]: [] }));
        }
    };

    // Mutations
    const createMutation = useMutation({
        mutationFn: (data: Parameters<typeof subscriptionsApi.create>[0]) =>
            subscriptionsApi.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
            setIsCreating(false);
            resetForm();
            toast.success('Abonnement erfolgreich erstellt');
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Fehler beim Erstellen des Abonnements'));
        },
    });

    const updateMutation = useMutation({
        mutationFn: ({ id, data }: { id: string; data: Parameters<typeof subscriptionsApi.update>[1] }) =>
            subscriptionsApi.update(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
            setEditingSub(null);
            resetForm();
            toast.success('Abonnement aktualisiert');
        },
        onError: (error) => {
            toast.error(getErrorMessage(error, 'Fehler beim Aktualisieren'));
        },
    });

    const deleteMutation = useMutation({
        mutationFn: (id: string) => subscriptionsApi.update(id, { aktiv: false }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
            setDeletingSub(null);
            toast.success('Abonnement deaktiviert');
        },
        onError: () => {
            toast.error('Fehler beim Deaktivieren');
        },
    });

    const processMutation = useMutation({
        mutationFn: () => subscriptionsApi.processToday(),
        onSuccess: (result) => {
            toast.success(`Abonnements verarbeitet: ${result?.message || 'Erfolgreich'}`);
        },
        onError: () => {
            toast.error('Fehler bei der Verarbeitung');
        },
    });

    const resetForm = () => {
        setFormData(leeresFormular());
    };

    // Positionen bearbeiten
    const setzePosition = (index: number, aenderung: Partial<PositionRow>) => {
        setFormData((prev) => ({
            ...prev,
            positionen: prev.positionen.map((p, i) => (i === index ? { ...p, ...aenderung } : p)),
        }));
    };

    const waehleProdukt = (index: number, productId: string) => {
        // Neues Produkt: Variante und Legacy-Sorte gehören nicht mehr dazu
        setzePosition(index, { product_id: productId, product_variant_id: '', seed_id: '' });
        void ladeVarianten(productId);
    };

    const waehleVariante = (index: number, productId: string, variantId: string) => {
        const variante = (variantenJeProdukt[productId] || []).find((v) => v.id === variantId);
        // Mit Variante gilt ihre Verpackungseinheit (so rechnet auch der Abo-Lauf)
        setzePosition(index, {
            product_variant_id: variantId,
            ...(variante?.packaging_unit_code ? { einheit: variante.packaging_unit_code } : {}),
        });
    };

    const positionHinzufuegen = () => {
        setFormData((prev) => ({ ...prev, positionen: [...prev.positionen, leerePosition()] }));
    };

    const positionEntfernen = (index: number) => {
        setFormData((prev) => ({
            ...prev,
            positionen: prev.positionen.length > 1 ? prev.positionen.filter((_, i) => i !== index) : prev.positionen,
        }));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (!editingSub && !formData.kunde_id) {
            toast.error('Bitte einen Kunden wählen');
            return;
        }
        if (formData.positionen.some((p) => !p.product_id && !p.seed_id)) {
            toast.error('Bitte in jeder Position ein Produkt wählen');
            return;
        }
        if (formData.positionen.some((p) => !(parseFloat(p.menge) > 0))) {
            toast.error('Jede Position braucht eine Menge größer 0');
            return;
        }

        const positionen = formData.positionen.map((p) => ({
            product_id: p.product_id || undefined,
            product_variant_id: p.product_variant_id || undefined,
            seed_id: p.product_id ? undefined : p.seed_id || undefined,
            menge: parseFloat(p.menge),
            einheit: p.einheit,
        }));

        if (editingSub) {
            updateMutation.mutate({
                id: editingSub.id,
                data: {
                    intervall: formData.intervall,
                    liefertage: formData.liefertage,
                    gueltig_bis: formData.gueltig_bis || undefined,
                    aktiv: formData.aktiv,
                    positionen,
                },
            });
        } else {
            createMutation.mutate({
                kunde_id: formData.kunde_id,
                intervall: formData.intervall,
                liefertage: formData.liefertage.length > 0 ? formData.liefertage : undefined,
                gueltig_von: formData.gueltig_von,
                gueltig_bis: formData.gueltig_bis || undefined,
                positionen,
            });
        }
    };

    const openEditModal = (sub: Subscription) => {
        const positionen: PositionRow[] = sub.positionen && sub.positionen.length > 0
            ? sub.positionen.map((p) => ({
                product_id: p.product_id || '',
                product_variant_id: p.product_variant_id || '',
                seed_id: p.seed_id || '',
                menge: String(p.menge),
                einheit: p.einheit,
                bisher: p.bezeichnung || undefined,
            }))
            : [{
                product_id: sub.product_id || '',
                product_variant_id: sub.product_variant_id || '',
                seed_id: sub.seed_id || '',
                menge: String(sub.menge),
                einheit: sub.einheit,
                bisher: sub.product_name || undefined,
            }];
        positionen.forEach((p) => { void ladeVarianten(p.product_id); });
        setFormData({
            kunde_id: sub.kunde_id,
            intervall: sub.intervall,
            liefertage: sub.liefertage || [],
            gueltig_von: sub.gueltig_von,
            gueltig_bis: sub.gueltig_bis || '',
            aktiv: sub.aktiv,
            positionen,
        });
        setEditingSub(sub);
    };

    const toggleLiefertag = (day: number) => {
        setFormData(prev => ({
            ...prev,
            liefertage: prev.liefertage.includes(day)
                ? prev.liefertage.filter(d => d !== day)
                : [...prev.liefertage, day].sort(),
        }));
    };

    // Derived data
    const subscriptions = subscriptionsData?.items || [];
    const customers = customersData?.items || [];
    const seeds = seedsData?.items || [];

    // Statistics
    const totalActive = subscriptions.filter(s => s.ist_aktiv).length;
    const totalInactive = subscriptions.filter(s => !s.ist_aktiv).length;

    const selectClassName = "w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-minga-500 focus:border-minga-500";

    return (
        <div className="space-y-6">
            <PageHeader
                title="Abonnements"
                subtitle={`${subscriptions.length} Abonnements, ${totalActive} aktiv`}
                actions={
                    <div className="flex gap-2">
                        <button
                            className="btn btn-secondary"
                            onClick={() => processMutation.mutate()}
                            disabled={processMutation.isPending}
                        >
                            <Play className="w-4 h-4" />
                            Heute verarbeiten
                        </button>
                        <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                            <Plus className="w-4 h-4" />
                            Neues Abonnement
                        </button>
                    </div>
                }
            />

            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                            <RefreshCw className="w-6 h-6 text-green-600 dark:text-green-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Aktive Abonnements</p>
                            <p className="text-2xl font-bold text-green-600 dark:text-green-400">{totalActive}</p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-gray-100 dark:bg-gray-700 rounded-lg">
                            <RefreshCw className="w-6 h-6 text-gray-600 dark:text-gray-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Inaktive Abonnements</p>
                            <p className="text-2xl font-bold text-gray-600 dark:text-gray-400">{totalInactive}</p>
                        </div>
                    </div>
                </div>

                <div className="card">
                    <div className="card-body flex items-center gap-4">
                        <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                            <User className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-500 dark:text-gray-400">Kunden mit Abo</p>
                            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                                {new Set(subscriptions.map(s => s.kunde_id)).size}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Filters */}
            <FilterBar>
                <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-gray-400" />
                    <select
                        value={kundeFilter}
                        onChange={(e) => setKundeFilter(e.target.value)}
                        className={`${selectClassName} w-48`}
                    >
                        <option value="">Alle Kunden</option>
                        {customers.map((customer: Customer) => (
                            <option key={customer.id} value={customer.id}>
                                {customer.name}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={aktivFilter}
                        onChange={(e) => setAktivFilter(e.target.value)}
                        className={`${selectClassName} w-40`}
                    >
                        <option value="">Alle Status</option>
                        <option value="true">Nur Aktive</option>
                        <option value="false">Nur Inaktive</option>
                    </select>
                </div>
            </FilterBar>

            {/* Subscriptions Table */}
            {isLoading ? (
                <div className="flex items-center justify-center h-64">
                    <InlineLoader text="Lade Abonnements..." />
                </div>
            ) : subscriptions.length === 0 ? (
                <EmptyState
                    title="Keine Abonnements gefunden"
                    description="Erstellen Sie ein neues Abonnement für wiederkehrende Bestellungen."
                    action={
                        <button className="btn btn-primary" onClick={() => setIsCreating(true)}>
                            <Plus className="w-4 h-4" />
                            Erstes Abonnement erstellen
                        </button>
                    }
                />
            ) : (
                // overflow-x-auto statt -hidden: sonst werden Status/Aktionen
                // auf schmalen Bildschirmen abgeschnitten statt scrollbar
                <div className="card overflow-x-auto">
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Kunde</th>
                                <th>Positionen je Lieferung</th>
                                <th>Intervall</th>
                                <th>Liefertage</th>
                                <th>Gültigkeit</th>
                                <th>Status</th>
                                <th className="text-right">Aktionen</th>
                            </tr>
                        </thead>
                        <tbody>
                            {subscriptions.map((sub: Subscription) => (
                                <tr key={sub.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                    <td className="font-medium">
                                        <div className="flex items-center gap-2">
                                            <User className="w-4 h-4 text-gray-400" />
                                            {sub.kunde_name || sub.kunde_id.slice(0, 8)}
                                        </div>
                                    </td>
                                    <td>
                                        <ul className="space-y-0.5">
                                            {positionenVon(sub).map((p, i) => (
                                                <li key={i} className="flex items-center gap-2">
                                                    <Leaf className="w-4 h-4 text-green-500 shrink-0" />
                                                    <span className="font-semibold tabular-nums">
                                                        {Number(p.menge).toLocaleString('de-DE')}
                                                    </span>
                                                    <span className="text-gray-500 dark:text-gray-400">{einheitLabel(p.einheit)}</span>
                                                    <span>{p.bezeichnung || '—'}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </td>
                                    <td>
                                        <Badge variant="info">
                                            {INTERVAL_LABELS[sub.intervall]}
                                        </Badge>
                                    </td>
                                    <td>
                                        {sub.liefertage && sub.liefertage.length > 0 ? (
                                            <div className="flex gap-1">
                                                {sub.liefertage.map(day => (
                                                    <span
                                                        key={day}
                                                        className="px-1.5 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 rounded"
                                                    >
                                                        {WEEKDAYS[day]}
                                                    </span>
                                                ))}
                                            </div>
                                        ) : (
                                            <span className="text-gray-400">-</span>
                                        )}
                                    </td>
                                    <td className="text-sm text-gray-500 dark:text-gray-400">
                                        <div className="flex items-center gap-1">
                                            <Calendar className="w-3 h-3" />
                                            {new Date(sub.gueltig_von).toLocaleDateString('de-DE')}
                                            {sub.gueltig_bis && (
                                                <> - {new Date(sub.gueltig_bis).toLocaleDateString('de-DE')}</>
                                            )}
                                        </div>
                                    </td>
                                    <td>
                                        <Badge variant={sub.ist_aktiv ? 'success' : 'gray'}>
                                            {sub.ist_aktiv ? 'Aktiv' : 'Inaktiv'}
                                        </Badge>
                                    </td>
                                    <td className="text-right">
                                        <div className="flex justify-end gap-1">
                                            <button
                                                className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
                                                onClick={() => openEditModal(sub)}
                                                title="Bearbeiten"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button
                                                className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                                                onClick={() => setDeletingSub(sub)}
                                                title="Deaktivieren"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Create/Edit Modal */}
            <Modal
                open={isCreating || !!editingSub}
                onClose={() => {
                    setIsCreating(false);
                    setEditingSub(null);
                    resetForm();
                }}
                title={editingSub ? 'Abonnement bearbeiten' : 'Neues Abonnement'}
            >
                <form onSubmit={handleSubmit} className="space-y-4">
                    {!editingSub && (
                        <Combobox
                            label="Kunde *"
                            value={formData.kunde_id}
                            onChange={(v) => setFormData({ ...formData, kunde_id: v })}
                            placeholder="Kunde suchen…"
                            options={customers.map((c: Customer) => ({ value: c.id, label: c.name }))}
                        />
                    )}

                    {/* Positionen je Lieferung (B6): mehrere Produkte, je mit Menge und Einheit */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Positionen je Lieferung *
                        </label>
                        <div className="space-y-3">
                            {formData.positionen.map((pos, index) => {
                                const varianten = variantenJeProdukt[pos.product_id] || [];
                                return (
                                    <div
                                        key={index}
                                        className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 space-y-2"
                                    >
                                        <div className="flex items-start gap-2">
                                            <div className="flex-1">
                                                {products.length === 0 && seeds.length > 0 ? (
                                                    <select
                                                        value={pos.seed_id}
                                                        onChange={(e) => setzePosition(index, { seed_id: e.target.value, product_id: '', product_variant_id: '' })}
                                                        className={selectClassName}
                                                        aria-label={`Saatgut Position ${index + 1}`}
                                                    >
                                                        <option value="">(Keine Produkte angelegt — Saatgut wählen)</option>
                                                        {seeds.map((seed: Seed) => (
                                                            <option key={seed.id} value={seed.id}>{seed.name}</option>
                                                        ))}
                                                    </select>
                                                ) : (
                                                    <Combobox
                                                        value={pos.product_id}
                                                        onChange={(v) => waehleProdukt(index, v)}
                                                        placeholder="Produkt suchen…"
                                                        options={produktOptionenFuer(pos)}
                                                    />
                                                )}
                                            </div>
                                            <button
                                                type="button"
                                                className="p-2 text-gray-500 dark:text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded disabled:opacity-40 disabled:cursor-not-allowed"
                                                onClick={() => positionEntfernen(index)}
                                                disabled={formData.positionen.length === 1}
                                                title="Position entfernen"
                                                aria-label={`Position ${index + 1} entfernen`}
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                            {varianten.length > 0 ? (
                                                <select
                                                    value={pos.product_variant_id}
                                                    onChange={(e) => waehleVariante(index, pos.product_id, e.target.value)}
                                                    className={selectClassName}
                                                    aria-label={`Variante Position ${index + 1}`}
                                                >
                                                    <option value="">Ohne Variante</option>
                                                    {varianten.map((v) => (
                                                        <option key={v.id} value={v.id}>
                                                            {v.name_suffix || v.packaging_unit_code || 'Variante'}
                                                        </option>
                                                    ))}
                                                </select>
                                            ) : (
                                                <div className="hidden sm:block" />
                                            )}
                                            <Input
                                                type="number"
                                                step="0.01"
                                                min="0"
                                                placeholder="Menge"
                                                aria-label={`Menge Position ${index + 1}`}
                                                value={pos.menge}
                                                onChange={(e) => setzePosition(index, { menge: e.target.value })}
                                                required
                                            />
                                            <select
                                                value={pos.einheit}
                                                onChange={(e) => setzePosition(index, { einheit: e.target.value })}
                                                className={selectClassName}
                                                disabled={!!pos.product_variant_id}
                                                title={pos.product_variant_id ? 'Einheit der Variante' : undefined}
                                                aria-label={`Einheit Position ${index + 1}`}
                                            >
                                                {!EINHEITEN.some((e) => e.value === pos.einheit) && (
                                                    <option value={pos.einheit}>{pos.einheit}</option>
                                                )}
                                                {EINHEITEN.map((e) => (
                                                    <option key={e.value} value={e.value}>{e.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        <button
                            type="button"
                            className="btn btn-secondary btn-sm mt-2"
                            onClick={positionHinzufuegen}
                        >
                            <Plus className="w-4 h-4" />
                            Position hinzufügen
                        </button>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            Alle Positionen kommen an jedem Liefertag in eine Bestellung. Preise wie im
                            Bestellformular: Sonderpreis des Kunden, sonst Varianten- bzw. Produktpreis.
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Intervall *
                        </label>
                        <select
                            value={formData.intervall}
                            onChange={(e) => setFormData({ ...formData, intervall: e.target.value as SubscriptionInterval })}
                            className={selectClassName}
                        >
                            {Object.entries(INTERVAL_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>
                                    {label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Liefertage
                        </label>
                        <div className="flex gap-2">
                            {WEEKDAYS.map((day, index) => (
                                <button
                                    key={index}
                                    type="button"
                                    onClick={() => toggleLiefertag(index)}
                                    className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                                        formData.liefertage.includes(index)
                                            ? 'bg-minga-50 dark:bg-minga-900/300 text-white border-minga-500'
                                            : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-minga-300'
                                    }`}
                                >
                                    {day}
                                </button>
                            ))}
                        </div>
                    </div>

                    {!editingSub && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Gültig ab *
                            </label>
                            <Input
                                type="date"
                                value={formData.gueltig_von}
                                onChange={(e) => setFormData({ ...formData, gueltig_von: e.target.value })}
                                required
                            />
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Gültig bis (optional)
                        </label>
                        <Input
                            type="date"
                            value={formData.gueltig_bis}
                            onChange={(e) => setFormData({ ...formData, gueltig_bis: e.target.value })}
                        />
                    </div>

                    {editingSub && (
                        <label className="flex items-center gap-2">
                            <input
                                type="checkbox"
                                checked={formData.aktiv}
                                onChange={(e) => setFormData({ ...formData, aktiv: e.target.checked })}
                                className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-minga-600 dark:text-minga-400 focus:ring-minga-500"
                            />
                            <span className="text-sm text-gray-700 dark:text-gray-300">
                                Aktiv (wird an den Liefertagen beliefert)
                            </span>
                        </label>
                    )}

                    <div className="flex justify-end gap-3 pt-4 border-t dark:border-gray-700">
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => {
                                setIsCreating(false);
                                setEditingSub(null);
                                resetForm();
                            }}
                        >
                            Abbrechen
                        </button>
                        <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={createMutation.isPending || updateMutation.isPending}
                        >
                            {editingSub ? 'Speichern' : 'Erstellen'}
                        </button>
                    </div>
                </form>
            </Modal>

            {/* Delete Confirmation Modal */}
            <Modal
                open={!!deletingSub}
                onClose={() => setDeletingSub(null)}
                title="Abonnement deaktivieren"
            >
                <div className="space-y-4">
                    <p className="text-gray-600 dark:text-gray-400">
                        Möchten Sie das Abonnement für{' '}
                        <strong>{deletingSub?.kunde_name}</strong> (
                        {deletingSub
                            ? positionenVon(deletingSub).map((p) => p.bezeichnung || '—').join(', ')
                            : '—'}
                        ) wirklich deaktivieren?
                    </p>
                    <div className="flex justify-end gap-3">
                        <button className="btn btn-secondary" onClick={() => setDeletingSub(null)}>
                            Abbrechen
                        </button>
                        <button
                            className="btn btn-danger"
                            onClick={() => deletingSub && deleteMutation.mutate(deletingSub.id)}
                            disabled={deleteMutation.isPending}
                        >
                            Deaktivieren
                        </button>
                    </div>
                </div>
            </Modal>
        </div>
    );
}
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
Run: `cd frontend && npm run build 2>&1 | tail -3` → endet mit `✓ built in …`.
Prüfen: `grep -c 'aktiv: true,' frontend/src/pages/Abonnements.tsx` → 1 (nur die Vorbelegung in `leeresFormular`); `grep -c 'aktiv: formData.aktiv' frontend/src/pages/Abonnements.tsx` → 1.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/services/api.ts frontend/src/pages/Abonnements.tsx
git commit -m "feat(abo): Abo-Seite mit Positionsliste — mehrere Produkte je Lieferung (B6)" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Abschluss — Schluss-Vollauf, statische Prüfung, Build, Abschlussmeldung

**Files:** keine Änderung (nur bei einem Befund aus Step 3 bzw. 4, dann mit Meldung).

- [ ] **Step 1: Testdatei komplett**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_b6_abo_positionen.py -v -p no:cacheprovider 2>&1 | tail -3` → **33 passed.**

- [ ] **Step 2: Prozedur V** → keine Zeile im Abgleich.

- [ ] **Step 3: Undefinierte Namen**

Run: `git diff --name-only <Basis>..HEAD -- '*.py' | xargs /opt/homebrew/bin/ruff check --select F821,F823`
Erwartet: höchstens der Altbefund `backend/app/models/customer.py:…: F821 Undefined name \`SepaMandat\`` (Paket 3, Typannotation `Mapped[list["SepaMandat"]]`). Jeder andere Befund: beheben (Import ergänzen), Schritt wiederholen, in der Meldung nennen. Ist `ruff` nicht unter `/opt/homebrew/bin/ruff` vorhanden: Schritt als „nicht ausführbar" melden, nicht ersetzen.

- [ ] **Step 4: Frontend** — `tsc` ohne Ausgabe, `npm run build` mit `✓ built`.

- [ ] **Step 5: Diff-Prüfung**

Run: `git diff --stat <Basis>..HEAD` → genau diese 12 Dateien: `backend/app/api/v1/sales.py`, `backend/app/models/__init__.py`, `backend/app/models/customer.py`, `backend/app/schemas/customer.py`, `backend/app/services/abo_positionen.py`, `backend/app/tasks/subscription_tasks.py`, `backend/app/tenancy.py`, `backend/tests/test_b6_abo_positionen.py`, `backend/tests/test_gernot_261008_paket2.py`, `frontend/src/pages/Abonnements.tsx`, `frontend/src/services/api.ts`, `frontend/src/types/index.ts`.
Run: `git log --oneline <Basis>..HEAD` → fünf Commits (Tasks 1–5).
Run: `git status --porcelain` → nur die als sauber genannten `??`-Einträge.

- [ ] **Step 6: Abschlussmeldung** (kurz, mit Zeigern, kein Roh-Dump):
  - Basis-Hash, Commit-Hashes je Task.
  - Rot/Grün je Task als Zahlen (erwartet vs. gemessen).
  - Prozedur-V-Summenzeile und „Abgleich leer".
  - `ruff`-Ergebnis, `tsc`/Build-Ergebnis.
  - Jede selbst aufgelöste Anker- oder Redaktionsabweichung mit Datei und Funktionsname.
  - Hinweis: Runbook und Abnahme sind Manager-Arbeit.

---

## Abnahme (Manager)

**Automatisch (nachmessen, nicht dem Bericht glauben):** Worktree `minga-b6`: Testdatei 33 passed; Prozedur V ohne Abweichung; `tsc` und Build; Diff genau 12 Dateien; `ruff` F821/F823 nur Altbefund.

**Bewusst abnehmen (Manager-Entscheid):** Task 4 Step 6 **ändert** einen bestehenden Paket-2-Test, `TestP4AboPosition.test_variables_bundle_wird_uebersprungen` (E4): Das Abo wird auf ein normales Produkt angelegt, das Produkt danach per PATCH zum variablen Bundle gemacht. Die Absicht bleibt (der Lauf überspringt ein Produkt, das nach dem Speichern zum variablen Bundle wurde); nur der Weg dorthin ändert sich, weil die API ein variables Bundle schon beim Anlegen ablehnt. Alle anderen Abo-Tests aus Paket 2 (Mandant des Knopfs, Doppelsperre, Storno-Fall) laufen unverändert grün. Das weicht wörtlich von „bestehende Abo-Tests bleiben grün" ab — mit `git diff <Basis>..HEAD -- backend/tests/test_gernot_261008_paket2.py` prüfen, dass genau diese Methode geändert ist.

**Echtdaten:** Runbook A3 (Gleichheitsprobe) auf einer Kopie des aktuellen Backups mit `Abweichungen: 0`.

**Oberfläche** (lokal gegen eine Kopie von `minga.db` oder die Demo-Kopie, Rolle admin, Browser):
- **O1** Neues Abo mit drei Positionen anlegen: Produkt, Produkt mit Variante „12er Mehrwegkiste", Pfandkiste. Tabelle zeigt drei Zeilen „Menge Einheit Bezeichnung".
- **O2** Bestands-Abo (migriert, MG-14001) öffnen: eine Position vorbelegt, Schalter „Aktiv" gesetzt; „Speichern" ohne Änderung → Toast „Abonnement aktualisiert", Liste unverändert.
- **O3** Variante wählen → Einheit springt auf die Verpackungseinheit und ist gesperrt; „Ohne Variante" → wieder frei.
- **O4** Position hinzufügen und wieder entfernen; die einzige Position lässt sich nicht entfernen.
- **O5** Produkt einer Position im Produktstamm deaktivieren, Abo öffnen → die Position zeigt den bisherigen Namen ausgegraut („nicht mehr wählbar"); speichern → Toast „Position n: Produkt … ist deaktiviert" (bzw. ohne Präfix bei einer Position). Deaktivieren über die Tabelle klappt.
- **O6** „Heute verarbeiten" für ein fälliges Abo mit drei Positionen → eine Bestellung mit drei Positionen; zweiter Klick → „0 Abo-Bestellungen angelegt. 1 schon vorhanden."
- **O7** Login als `production_staff`: Navigation ohne „Abonnements" (unverändert).
- **O8** Abo-Bestellung eines IFCO-Clearing-Kunden (`KEINE`) → Rechnung aus Bestellung ohne Pfandzeile; Lieferschein mit Pfandzeile.
- **O9** (E10) Ein inaktives Abo öffnen: Schalter „Aktiv" leer; „Speichern" ohne Änderung → Abo bleibt „Inaktiv". Erneut öffnen, Schalter setzen, speichern → „Aktiv". (Auf der lokalen Kopie; in Produktion die 2 inaktiven Abos nicht anfassen.)

## Runbook (Manager, kein Worker-Task)

Zugriff und Backup wie gewohnt: `ssh -i ~/.ssh/sprouddesk_hetzner_ed25519 root@49.12.191.103`, Container je Befehl neu holen: `C=$(docker ps --format "{{.Names}}" | grep n8ml32w2vs6b190ue2ianc84 | head -1)`. Im Container gibt es kein `sqlite3`-Binary; Skripte per `docker exec -i "$C" python3 - <args> < skript.py`. Lesen nur mit `mode=ro`. Die Skripte liegen unter `/tmp/b6/runbook/` (Inhalt unten) und werden vor dem Einsatz nach `/root/` auf den Server kopiert: `abo_pruefung.py` (nur lesend) und `gleichheitsprobe.py` (lokal) immer, `position1_aus_kopf.py` (schreibt) nur für den erneuten Deploy nach einer Rücknahme.

### Teil A — vor dem Deploy

- **A1 Backup:** WAL-sicheres Backup von `minga` und `demo` über die Backup-API (Muster aus dem Paket-1/2-Deploy), Ablage `/root/backups/<slug>-vor-deploy-b6-<JJJJMMTT-HHMMSS>.db`, `integrity_check` = `ok`. Pflicht vor jedem Schema-Deploy.
- **A2 Bestand lesen (Server, nur lesend):** `docker exec -i "$C" python3 - minga < /root/abo_pruefung.py` und dasselbe mit `demo`. Erwartet für `minga`: `5 Abos, davon 3 aktiv`, `Kopfspalten vollständig: True`, `Tabelle subscription_items: fehlt`, drei aktive Zeilen `MG-14001 Gastrotray … WOECHENTLICH`. Ausgabe lokal sichern (Vergleich in B2). Weicht der Bestand ab (z. B. ein Abo mit Variante oder ohne Produkt): festhalten, kein Abbruchgrund — die Migration übernimmt jeden Kopf, wie er ist.
- **A3 Gleichheitsprobe (lokal, auf einer Kopie des A1-Backups):** Kopie nach `/tmp/b6-probe/minga.db` (chmod 600), dann im B6-Worktree:
  `cd /Users/nikolajunser-richter/minga-b6/backend && PYTHONPATH=. TENANTS_DIR=/tmp/b6-probe REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python /tmp/b6/runbook/gleichheitsprobe.py minga <nächster Liefertag JJJJ-MM-TT>`
  Erwartet: je Abo `1 Position(en) GLEICH`, Schlusszeile `Abweichungen: 0`. Danach `python3 /tmp/b6/runbook/abo_pruefung.py minga /tmp/b6-probe/minga.db` → `positionen_gesamt` = Anzahl Abos, alle Listen leer, `positionen_ohne_abo: 0`. Kopie löschen (`rm -rf /tmp/b6-probe`). Bei einer Abweichung: **kein Deploy**, Befund an den Worker (Fix-Runde mit exakter Ausgabe).

### Teil B — nach dem Deploy (nur lesend)

- **B1 Startlog:** `docker logs "$C" 2>&1 | grep 'auto-migrate'` → **keine** Zeile `[auto-migrate] Abo-Positionen fehlgeschlagen` (und kein anderes `[auto-migrate] … failed`/`fehlgeschlagen`). Die Erfolgsmeldung `[auto-migrate] Abo-Positionen für n Abos nachgetragen` erscheint **nicht** im Container-Log: sie ist `logger.info`, und das Backend richtet kein Logging ein (kein `basicConfig`/`dictConfig`/`addHandler` in `backend/app`, `uvicorn` ohne Log-Konfiguration) — Python gibt dann nur Warnungen und Fehler aus, wie schon bei der Paket-3-Zeile `Empfänger-Snapshot … nachgetragen`. Den Nachweis der Migration führt allein B2. Eine Zeile `Abo-Positionen fehlgeschlagen` → sofort B2, dann entscheiden (der Lauf liefert dank E7 weiter den Kopf).
- **B2 Positionen prüfen:** `docker exec -i "$C" python3 - minga < /root/abo_pruefung.py` (und `demo`). Erwartet: `Tabelle subscription_items: vorhanden`, `positionen_gesamt: 5`, `abos_ohne_position: []`, `abos_mit_mehreren_positionen: {}`, `position_1_weicht_vom_kopf_ab: []`, `positionen_ohne_abo: 0`; die Abo-Zeilen gleich wie in A2.
- **B3 Live-Beweis:** `curl -s https://minga.novaerp.de/openapi.json | grep -c SubscriptionPositionIn` → mindestens 1. Bundle enthält „Positionen je Lieferung".
- **B4 Nach dem nächsten 05:00-Lauf an einem Liefertag** (lesend): die neuen Abo-Bestellungen haben je **eine** Position MG-14001 mit Menge und Einheit wie in A2 und dem Preis wie vor B6 (Skript unten, an Spalte 0; im Nachbau auf der simulierten DB je Abo eine Zeile wie `('BE-…', '2026-10-12', 1, 'Gastrotray 1 STUECK 18')`).

```bash
docker exec -i "$C" python3 - <<'EOF'
import sqlite3
con = sqlite3.connect("file:/data/tenants/minga.db?mode=ro", uri=True)
for row in con.execute("""
    SELECT o.order_number, o.requested_delivery_date, COUNT(l.id), GROUP_CONCAT(l.beschreibung || ' ' || l.quantity || ' ' || l.unit || ' ' || l.unit_price, ' | ')
    FROM orders o JOIN order_lines l ON l.order_id = o.id
    WHERE o.internal_notes = 'Subscription Run' AND o.created_at >= date('now', '-1 day')
    GROUP BY o.id ORDER BY o.order_number"""):
    print(row)
EOF
```

- **Rücknahme:** Code-Rollback auf den vorherigen Commit ist möglich; die Tabelle `subscription_items` bleibt liegen und stört den alten Code nicht (er liest den Kopf = Position 1). Abos, die **nach** dem Deploy mit mehreren Positionen angelegt wurden, liefern im alten Code nur ihre erste Position — vor einem Rollback mit `abo_pruefung.py` (`abos_mit_mehreren_positionen`) prüfen und Gernot informieren. Löscht der alte Code einen Kunden samt Abos, nimmt die Datenbank die Positionen mit (`ondelete="CASCADE"`, Mandanten-DB mit `PRAGMA foreign_keys=ON`).
- **Erneuter B6-Deploy nach einer Rücknahme:** Der alte Code ändert per PATCH Menge und Einheit nur im Kopf. `positionen_nachtragen` überspringt beim nächsten B6-Start jedes Abo, das schon Positionen hat, und der Lauf läse still die alte Menge aus Position 1. Darum **vor** dem erneuten Deploy: A1 (Backup), dann `docker exec -i "$C" python3 - minga < /root/abo_pruefung.py` (und `demo`) → `position_1_weicht_vom_kopf_ab` muss leer sein. Sonst `docker exec -i "$C" python3 - minga < /root/position1_aus_kopf.py` (setzt bei genau diesen Abos Position 1 auf die Kopfwerte, Positionen 2..n bleiben; schreibt, darum nur nach A1) und `abo_pruefung.py` erneut → Liste leer. Abos, die im alten Code neu angelegt wurden, stehen vorher unter `abos_ohne_position` und bekommen ihre Position beim Start. Nach dem Deploy B1 und B2 wie oben (B2 prüft `position_1_weicht_vom_kopf_ab: []` noch einmal). Nachgespielt auf einer simulierten Mandanten-DB: zwei im Kopf geänderte Abos (eines mit zwei Positionen) → Skript „bei 2 Abo(s)", danach Liste leer, Position 2 unverändert, zweiter Aufruf „bei 0 Abo(s)".

**`/tmp/b6/runbook/abo_pruefung.py`:**

```python
"""B6 Runbook: Abos und Abo-Positionen eines Mandanten lesen. Nur lesend (mode=ro).

Aufruf im Container:  docker exec -i "$C" python3 - minga < abo_pruefung.py
Lokal (Kopie):        python3 abo_pruefung.py minga /pfad/zur/minga.db
"""
import json
import sqlite3
import sys

slug = sys.argv[1] if len(sys.argv) > 1 else "minga"
pfad = sys.argv[2] if len(sys.argv) > 2 else f"/data/tenants/{slug}.db"
con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

spalten = {r["name"] for r in con.execute("PRAGMA table_info(subscriptions)")}
hat_items = con.execute(
    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'subscription_items'"
).fetchone() is not None
abos = con.execute("""
    SELECT s.id, s.aktiv, s.intervall, s.liefertage, s.menge, s.einheit,
           s.product_id, s.product_variant_id, s.seed_id, p.sku, p.name AS produkt,
           c.name AS kunde
    FROM subscriptions s
    LEFT JOIN products p ON p.id = s.product_id
    LEFT JOIN customers c ON c.id = s.kunde_id
    ORDER BY s.aktiv DESC, c.name, s.id
""").fetchall()

print(f"Mandant {slug}: {len(abos)} Abos, davon {sum(1 for a in abos if a['aktiv'])} aktiv")
print("Kopfspalten vollständig:",
      {"product_id", "product_variant_id", "seed_id", "menge", "einheit"} <= spalten)
print("Tabelle subscription_items:", "vorhanden" if hat_items else "fehlt")
for a in abos:
    print(f"  {a['id'][:8]}  {'aktiv  ' if a['aktiv'] else 'inaktiv'}  {a['kunde']}  "
          f"{a['sku'] or '-'} {a['produkt'] or '(ohne Produkt)'}  {a['menge']} {a['einheit']}  "
          f"{a['intervall']} {a['liefertage']}  Variante={'ja' if a['product_variant_id'] else 'nein'}  "
          f"Sorte={'ja' if a['seed_id'] else 'nein'}")

if hat_items:
    je_abo = {r["id"]: r["n"] for r in con.execute("""
        SELECT s.id, COUNT(i.id) AS n FROM subscriptions s
        LEFT JOIN subscription_items i ON i.subscription_id = s.id GROUP BY s.id""")}
    abweichend = [r["id"] for r in con.execute("""
        SELECT s.id FROM subscriptions s
        JOIN subscription_items i ON i.subscription_id = s.id AND i.position = 1
        WHERE NOT (i.product_id IS s.product_id AND i.product_variant_id IS s.product_variant_id
                   AND i.seed_id IS s.seed_id AND i.menge = s.menge AND i.einheit = s.einheit)""")]
    verwaist = con.execute("""
        SELECT COUNT(*) FROM subscription_items i
        LEFT JOIN subscriptions s ON s.id = i.subscription_id WHERE s.id IS NULL""").fetchone()[0]
    ergebnis = {
        "positionen_gesamt": sum(je_abo.values()),
        "abos_ohne_position": [i[:8] for i, n in je_abo.items() if n == 0],
        "abos_mit_mehreren_positionen": {i[:8]: n for i, n in je_abo.items() if n > 1},
        "position_1_weicht_vom_kopf_ab": [i[:8] for i in abweichend],
        "positionen_ohne_abo": verwaist,
    }
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2))
```

**`/tmp/b6/runbook/gleichheitsprobe.py`:**

```python
"""B6 Runbook A: Gleichheitsprobe auf einer LOKALEN KOPIE (nie auf dem Server).

Migriert die Kopie mit dem Code des B6-Branches (create_all + _auto_migrate) und
vergleicht je Abo die Bestellposition nach altem Weg (Kopf, abo_position ohne
Quelle = Stand vor B6) mit dem neuen Weg (abo_positionen). Legt keine Bestellung
an; schreibt nur die Migration in die Kopie.

Aufruf: cd <worktree>/backend && PYTHONPATH=. TENANTS_DIR=<ordner mit slug.db> REDIS_URL=memory:// \
        /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python <pfad>/gleichheitsprobe.py minga 2026-10-12
"""
import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app import tenancy
from app.database import Base
from app.models.customer import Subscription
from app.tasks.subscription_tasks import AboUebersprungen, abo_position, abo_positionen, ist_faellig

slug, tag = sys.argv[1], date.fromisoformat(sys.argv[2])
if not tenancy.registry.exists(slug):
    sys.exit(f"Keine Kopie {tenancy.registry.path_for(slug)}")
engine = tenancy.registry.get_engine(slug)
Base.metadata.create_all(bind=engine)
tenancy._auto_migrate(engine)


def felder(line):
    return (line.product_id, line.product_variant_id, line.beschreibung, line.quantity,
            line.unit, line.unit_price, line.tax_rate, line.line_net)


abweichungen = 0
with Session(engine) as db:
    for sub in db.execute(select(Subscription).order_by(Subscription.aktiv.desc())).scalars():
        kopf = f"{str(sub.id)[:8]} {'aktiv  ' if sub.aktiv else 'inaktiv'} {'fällig' if ist_faellig(sub, tag) else '-     '}"
        try:
            alt = abo_position(db, sub, tag)
        except AboUebersprungen as grund:
            alt = f"übersprungen: {grund}"
        try:
            neu = abo_positionen(db, sub, tag)
        except AboUebersprungen as grund:
            neu = f"übersprungen: {grund}"
        if isinstance(alt, str) or isinstance(neu, str):
            gleich = alt == neu
        else:
            gleich = len(neu) == 1 and felder(neu[0]) == felder(alt)
        abweichungen += 0 if gleich else 1
        print(kopf, len(sub.positionen), "Position(en)",
              "GLEICH" if gleich else f"ABWEICHUNG alt={alt if isinstance(alt, str) else felder(alt)} "
                                      f"neu={neu if isinstance(neu, str) else [felder(l) for l in neu]}")
    db.rollback()
print("Abweichungen:", abweichungen)
```

**`/tmp/b6/runbook/position1_aus_kopf.py`** (nur erneuter Deploy nach einer Rücknahme, schreibt):

```python
"""B6 Runbook, nur für einen erneuten B6-Deploy nach einer Rücknahme. SCHREIBT.

Im zurückgenommenen Code ändert PATCH menge/einheit nur den Kopf des Abos;
positionen_nachtragen überspringt beim nächsten B6-Start jedes Abo, das schon
Positionen hat, und der Lauf läse still die alte Position 1. Dieses Skript setzt
bei genau den Abos, deren Position 1 vom Kopf abweicht, Produkt, Variante,
Sorte, Menge und Einheit von Position 1 auf die Kopfwerte. Positionen 2..n
bleiben. Nur nach WAL-sicherem Backup (Runbook A1).

Aufruf im Container:  docker exec -i "$C" python3 - minga < position1_aus_kopf.py
Lokal (Kopie):        python3 position1_aus_kopf.py minga /pfad/zur/minga.db
"""
import sqlite3
import sys

slug = sys.argv[1] if len(sys.argv) > 1 else "minga"
pfad = sys.argv[2] if len(sys.argv) > 2 else f"/data/tenants/{slug}.db"
SPALTEN = ("product_id", "product_variant_id", "seed_id", "menge", "einheit")

con = sqlite3.connect(pfad, timeout=30)
with con:
    ids = [r[0] for r in con.execute("""
        SELECT i.id FROM subscription_items i
        JOIN subscriptions s ON s.id = i.subscription_id
        WHERE i.position = 1 AND NOT (
            i.product_id IS s.product_id AND i.product_variant_id IS s.product_variant_id
            AND i.seed_id IS s.seed_id AND i.menge = s.menge AND i.einheit = s.einheit)""")]
    setzen = ", ".join(
        f"{sp} = (SELECT s.{sp} FROM subscriptions s WHERE s.id = subscription_items.subscription_id)"
        for sp in SPALTEN
    )
    con.executemany(f"UPDATE subscription_items SET {setzen} WHERE id = ?", [(i,) for i in ids])
con.close()
print(f"Mandant {slug}: Position 1 aus dem Kopf übernommen bei {len(ids)} Abo(s)")
```

## Offene Punkte für Gernot

1. **Preis je Abo-Position:** B6 hinterlegt keinen Preis im Abo. Abo-Bestellungen bekommen wie jede Bestellung den Sonderpreis des Kunden (Kundenseite → Sonderpreise), sonst Varianten- bzw. Produktpreis. Reicht das, oder brauchst du einen eigenen Abo-Preis? (Dann nur für Büro und Vertrieb, nicht für die Halle — eigener Schritt.)
2. **Fehlt ein Produkt, fällt die ganze Abo-Lieferung des Tages aus** (z. B. ein Produkt wurde deaktiviert), mit Hinweis beim Knopf „Heute verarbeiten" und im Protokoll. Alternative: die übrigen Positionen trotzdem liefern und nur die fehlende melden. Was ist dir lieber?
3. **Mitarbeiter und Abos** (aus Paket 3 weiter offen): Über die Schnittstelle dürfen Mitarbeiter Abos anlegen und ändern; die Oberfläche zeigt ihnen die Seite nicht. Abos tragen weiter keine Preise. Sollen wir das sperren?
4. **Gastrotray mit Sortenwahl** (variables Bundle) lässt sich nicht abonnieren, weil ein Abo keine Sortenwahl je Lieferung hat. MG-14001 betrifft das nicht. Brauchst du das?
5. **Pfandkisten im Abo:** als eigene Position eintragen (z. B. „2 × IFCO-Kiste"). Abgerechnet wird automatisch nach der Pfandabrechnung des Kunden (je Lieferung, IFCO-Clearing, monatlich). Die Kistenzahl leitet das System nicht aus den Produkten ab — passt das?
6. **Kisten:** Für einen Kistenpreis die Verpackungsvariante „12er Mehrwegkiste" wählen (Preis der Variante). Die Einheit „Mehrwegkiste" ohne Variante rechnet nicht um: Menge × Produktpreis, als wäre der Produktpreis ein Kistenpreis.
7. **Unterschiedliche Mengen je Liefertag** (z. B. Montag 2 Kisten, Donnerstag 1) gehen in einem Abo nicht; dafür zwei Abos anlegen. Brauchst du das in einem?

## Nicht in B6 (bewusst, Stand vor B6 bleibt)

- **Prognose:** `forecasting._calculate_subscription_demand` zählt Abos weiter nur über den Kopf (`seed_id`, `menge`) — Produkt-Abos ohne Sorte zählen nicht, weitere Positionen auch nicht. Eigener Schritt (Prognose je Produkt).
- **Abo-Lauf** prüft weder Kreditlimit noch einen deaktivierten Kunden (`create_order` tut beides) und nicht `ProductVariant.is_active` (auch `create_order` nicht).
- **„Gültig ab"** wird im Formular mit `toISOString()` (UTC) vorbelegt — zwischen 0 und 2 Uhr Berliner Zeit der Vortag. Unverändert übernommen.
- **`scripts/seed_data.py`** legt Abos nur mit Kopf an; der nächste Start trägt die Positionen nach (E7 deckt die Zeit dazwischen).
- **Kein `GET /sales/subscriptions/{id}`** (der Client hat `subscriptionsApi.get`/`delete` ohne Endpunkt, Altbestand, ungenutzt).
