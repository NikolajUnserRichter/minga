# Benutzerverwaltung (B8) — Implementation Plan

> **Für agentische Worker:** Diesen Plan Task für Task abarbeiten, Backend (Task 1–7) vor Frontend (Task 8–12). Schritte nutzen Checkbox-Syntax (`- [ ]`). Kein Task wird übersprungen, zusammengefasst oder umgestellt. Inhaltliche Widersprüche zwischen Plan und Code, vor allem beim Vertrag in Task 8: stoppen und mit exakter Ausgabe melden, nicht selbst anpassen. Rein redaktionelle Unstimmigkeiten mit eindeutiger Absicht: selbst auflösen und in der Abschlussmeldung nennen. Kein Netzwerk, kein Deploy, kein Zugriff auf Produktion oder Keycloak; Keycloak ist in allen Tests gemockt.

**Goal:** Ein Mandanten-Admin verwaltet die Benutzer **seines** Mandanten selbst: anlegen (mit Einmalpasswort), Vorname, Nachname und Rolle ändern, deaktivieren und wieder aktivieren (nie löschen), Passwort zurücksetzen — über echte Keycloak-Aufrufe statt der localStorage-Attrappe mit sieben erfundenen Nutzern. Benutzer anderer Mandanten sind für ihn unsichtbar und unveränderlich. Die Oberfläche zeigt die fünf Rollen mit deutscher Bezeichnung und je einem Satz, was sie dürfen; der Mitarbeiter-Login ist `production_staff`.

**Architecture:** Backend: neuer Router `backend/app/api/v1/users.py` unter `/api/v1/users`, eingehängt mit `_deps_admin` (nur Rolle `admin`). Der Mandant kommt aus dem Host **und** aus dem Token-Claim `tenant_slug`; beide müssen gesetzt und gleich sein, aus dem Body kommt er nie (`extra="forbid"`). Die Keycloak-Logik liegt als neuer Abschnitt am Ende von `backend/app/services/keycloak_admin.py`, neben dem unveränderten `create_tenant_user`. Jede Funktion mit Keycloak-User-ID liest zuerst den Benutzer und verlangt `attributes.tenant_slug == [mandant]`, sonst 404 mit demselben Body wie bei einer unbekannten ID. Vor jedem Schreiben prüft der Dienst zusätzlich, dass das Ziel ein gewöhnliches Mandanten-Konto ist (keine Client-Rollen außer `account`, keine Gruppen, keine fremden oder zusammengesetzten Realm-Rollen), sonst 409 „vom Support verwaltet". Die Liste fragt Keycloak über `q=tenant_slug:<slug>` und filtert exakt in Python. Zugang nur über einen Service-Account im Realm der Token-Prüfung (`settings.keycloak_realm`), sonst 503; das Token wird je Prozess wiederverwendet. Schreibende Aufrufe sind je Mandant gebremst (30 je Minute und Prozess, dann 429). Im Demo-Mandanten und mit den öffentlichen Demo-Logins wird nie geschrieben. Audit als WARNING-Logzeile der Kategorie `app.audit.benutzer`. Frontend: dünner axios-Client `usersApi` in `services/api.ts` nach dem Vertrag, Rollentexte an einer Stelle (`services/rollen.ts`), Seite `pages/Users.tsx` mit eigener Admin-Prüfung, Lade- und Fehlerzustand, Rückfragen und einmaliger Passwortanzeige; die Befehlspalette zeigt den Eintrag nur Administratoren. Durchgesetzt werden Rechte und Mandantentrennung ausschließlich im Backend.

**Tech Stack:** FastAPI + Pydantic v2, httpx (Keycloak-Admin-REST), pytest mit `httpx.MockTransport` als Keycloak-Ersatz; React 18 + TypeScript (strict, `noUnusedLocals`), TanStack Query 5, axios, Tailwind, Playwright (nur Abnahme, gemockte API).

**Spec:** `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md` (B8, Paket 4, Entscheidungen 3 und 6, Gernots Antwort 11) und die geprüfte Analyse `docs/superpowers/specs/2026-10-08-nachtrag/T5-rechte-versand.md` (1.4, 1.5, 3.2 R3–R5, Risiken 2 und 3, Fragen F1, F6, F11).

**Stand und Prototyp:** `main` @ `efcea00`. Der gesamte Code dieses Plans lief am 08.10.2026 in Wegwerf-Kopien außerhalb des Repos, in Plan-Reihenfolge, die Codeblöcke wörtlich aus diesem Plan. Backend (`git archive efcea00 backend`): die Rot-/Grün-Zahlen in den Schritten sind gemessen; Vollauf danach 15 failed / 627 passed / 2 skipped / 1 error, dieselben 16 Fehlernamen wie die Baseline. Frontend (`git archive efcea00 frontend`): `tsc` ohne Ausgabe, `npm run build` ok, Abnahme-Spec 10 von 10 grün gegen den lokalen Dev-Server; dieselbe Spec gegen unverändertes `main` 10 von 10 rot. Die 119 Tests aus Task 1–5 und 7 liefen in der U1-Prüfung zusätzlich auf den Produktions-Pins (Python 3.11, fastapi 0.109.0, pydantic 2.5.3, httpx 0.26.0) grün; für den Test aus Task 6 ist das nicht wiederholt (er nutzt nur Standardbibliothek und `Depends`).

**Zusammenführung der Teilpläne** (U1 Backend, U2 Frontend; beim Zusammensetzen entschieden):

1. **Kein master-Rückfall ohne eigenen Nachtrag.** Task 1 ist schon geschlossen: `_users_cfg` nimmt nur den Service-Account, den master-Admin nur mit `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN=1` (Entwicklung und Test). Der U2-Nachtrag N1, der den Schalter ganz entfernt, entfällt. Deploy-Gate D7 prüft, dass der Schalter in Coolify fehlt; ob er ganz weg soll, ist Offener Punkt M16.
2. **Die Schreibbremse aus dem U2-Nachtrag N2 ist Task 6.** Der 409 bei vergebener E-Mail bleibt wie in Task 3 im Audit `ANLAGE_ABGELEHNT` mit `ziel_email` im Klartext (Test `TestAnlegen::test_email_vergeben`). Die N2-Variante `ANLAGE_KONFLIKT` mit SHA-256 statt Klartext ist nicht übernommen, Offener Punkt M7.
3. **Service-Account mit `view-realm`.** Rollen: `realm-management` → `manage-users`, `view-users`, `view-realm`. T5 R5 nennt nur die ersten beiden; `view-realm` (nur lesend) braucht `_rolle_rep` für `GET /roles/<rolle>` vor jeder Anlage und jedem Rollenwechsel. **Annahme** aus dem Keycloak-Quelltext; Manager-Abnahme B misst es an Keycloak 22, Offener Punkt M17.
4. Zeilenverweise auf den früheren U1-Arbeitsstand sind durch Funktionsnamen ersetzt. Code-Kommentare und der Spec-Titel nennen „B8" statt „U1"/„U2"; sonst ist der Code wörtlich der der Teilpläne.

**Abhängigkeiten**

- **Code:** keine. Basis `main` @ `efcea00`; nichts aus Paket 1, 2 oder 3 nötig.
- **Entscheidung 6 (Feldschutz):** Mitarbeiter-Logins (`production_staff`) erst vergeben, wenn der B8-Kern aus Paket 3 live ist: Halle liest Produkte (T5 R1), Rechnungsteil im Belege-Dialog für die Halle ausgeblendet (R3), Feldschutz der abrechnungsrelevanten Kundenfelder (`pfand_abrechnung`, später `invoice_mode`, Bankdaten) gegen `production_staff`, ein Lieferschein je Bestellung. Vorher sehen solche Logins im Bestellformular Saatgut statt Produkte und das Speichern endet mit 404 (T5 1.3), sie dürfen abrechnungsrelevante Kundenfelder ändern, und der Rollentext „Bestellungen … anlegen" stimmt in der Oberfläche erst nach R1. **Deshalb Deploy dieses Plans erst nach dem B8-Kern.**
- **Deploy:** Backend und Frontend gemeinsam; ohne Backend antwortet `GET /api/v1/users` mit 404 (Catch-all `main.py:1029`) und die Seite zeigt nur den Fehlerzustand. Kein Deploy, solange ein Deploy-Gate D1–D9 rot ist. Die Endpunkte sind nach dem Deploy für jeden Mandanten-Admin per API erreichbar, auch ohne Oberfläche: „unsichtbar" ist kein Schutz.
- **Paket 3, R3** (Attrappe in `pages/Users.tsx` durch einen Hinweis ersetzen oder den Menüpunkt entfernen) trifft dieselben Dateien. Landet R3 vorher, ersetzt Task 10 `Users.tsx` vollständig; fehlt dann der Menüeintrag `/users` (`Layout.tsx:249-254`), stoppt Task 11 Step 3.
- **Paket 3, R4** (Plattform-Endpunkte `/api/v1/platform/tenants/{slug}/users`) soll `list_tenant_users`, `create_user_for_tenant` und `update_tenant_user` aus Task 1–4 nutzen statt eines zweiten Keycloak-Pfads. Die Dienstfunktionen prüfen ID (UUID), Mandant und Supportkonto selbst.
- **Paket 3, R1/R2** ändert `main.py:716-732` und will die Rollen-Konstanten nach `app/core/rollen.py` verschieben. Getrennte Hunks zu Task 2. Wandert `ALLE_ROLLEN`, zieht der Import in `test_rollenlisten_stimmen_ueberein` (Task 2) mit.

**Überschneidungen mit Paket 1 und Paket 2** (geprüft am 08.10.2026 abends gegen `feat/paket1-steuer-rechnung` @ `d8e1db2`, 32 Dateien, und `feat/paket2-tagesplan-status` @ `4c16bea`, 31 Dateien; `git diff --name-only main...<branch>`):

- Gemeinsam ist nur `frontend/src/services/api.ts`, in getrennten Hunks. Paket 1: `priceListsApi` (`@@ -708`), `invoicesApi` (`@@ -738`, `@@ -771`), `documentsApi` (`@@ -1382`). Paket 2: Importblock (`@@ -12`), `DayPlanOrder` (`@@ -141`), `productionApi` (`@@ -231`, `@@ -241`), `salesApi` (`@@ -381`). Task 10 ändert nur den Block zwischen den Ankern `// ============== Users API (Mock Data) ==============` und `// ==================== GROWTH-TIMELINE-EVENTS ====================` (auf `main` Zeile 1015/1123, auf Paket 1 1017/1125, auf Paket 2 1031/1139). Textkonflikt: keiner erwartet.
- `frontend/src/types/index.ts` ändern beide Pakete; dieser Plan nicht.
- `frontend/src/components/ui/Badge.tsx` und `components/ui/index.ts` ändert Paket 2. Dieser Plan importiert nur daraus; die Varianten (`success | warning | danger | info | gray | purple`) bleiben auf dem Branch gleich.
- `backend/app/tenancy.py`: Paket 1 ergänzt `_auto_migrate` um 16 Zeilen; `get_request_tenant` (heute `tenancy.py:394-396`) rückt auf etwa 410. Dieser Plan importiert nur `get_request_tenant` und `DEFAULT_TENANT_SLUG`.
- Keine weitere Datei dieses Plans steht im Diff eines der beiden Branches (`main.py`, `keycloak_admin.py`, `api/v1/users.py`, `schemas/user.py`, `test_benutzerverwaltung.py`, `services/rollen.ts`, `UserCard.tsx`, `pages/Users.tsx`, `CommandPalette.tsx`, `Layout.tsx`, `tests/e2e/benutzerverwaltung.spec.ts`).
- Dieser Plan fasst `invoices.py`, `sales.py`, `production.py`, `documents.py`, `Orders.tsx`, `Tagesplan.tsx`, `Invoices.tsx`, `OrderDocumentsModal.tsx` und das Kundenformular (`Customers.tsx`) nicht an.

## Manager-Entscheidungen 08.10.2026 (verbindlich — gehen den Tasks vor)

Der Plan wurde auf `efcea00` geplant; Ausgangsstand ist jetzt `main` = `4cb9b92` (Paket 1 deployt). Zeilenangaben können sich verschoben haben — über die zitierten Anker finden.

- **E-M1 Audit dauerhaft:** Jede Benutzeraktion (Anlegen, Ändern, Deaktivieren/Aktivieren, Passwort-Reset, abgelehnte Anlage) wird zusätzlich zum Log in eine neue Tabelle `benutzer_audit` der Mandanten-DB geschrieben (Modell in `backend/app/models/`, entsteht per `create_all`; Spalten: id CHAR(32), zeitpunkt, aktion, ziel_user_id, ziel_email bzw. ziel_email_sha256, ausgefuehrt_von, details JSON). Eigener Task **6b** nach Task 6, Test zuerst; GET-Endpunkt ist nicht nötig.
- **E-M6 Demo:** Im Mandanten `demo` liefert `GET /users` nur Konten, deren E-Mail in `DEMO_USERS` (`backend/app/api/v1/platform.py`) steht. `BenutzerListResponse` bekommt ein Feld `schreibgeschuetzt: bool` (true im Demo-Mandanten); das Frontend (Task 10) blendet danach „Neuer Benutzer", „Bearbeiten", „Deaktivieren" und „Passwort zurücksetzen" aus. Umsetzung in Task 2 (Filter, Feld) und Task 10 (Ausblenden), je mit Test bzw. tsc/Build und Abnahme-Spec (Task 12).
- **E-M7 Hash statt Klartext:** Beim 409 wegen vergebener E-Mail schreibt das Audit `ANLAGE_KONFLIKT` mit `ziel_email_sha256` (SHA-256 der kleingeschriebenen Adresse) statt `ANLAGE_ABGELEHNT` mit Klartext. Task 3 und `TestAnlegen::test_email_vergeben` entsprechend.
- **E-M8:** bleibt wie geplant.
- **E-M16 Schalter entfernen:** `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN` wird nicht eingebaut; `_users_cfg` nimmt ausschließlich den Service-Account. Tests nutzen Mocks des Service-Accounts. Task 1 entsprechend; Deploy-Gate D7 prüft nur noch die Service-Account-Variablen.
- **E-M17:** `view-realm` für den Service-Account ist freigegeben (nur lesend).
- **Deploy:** nicht vor dem B8-Kern aus Paket 3 (Feldschutz, Halle liest Produkte); Keycloak-Konfiguration des Service-Accounts ist ein Betriebsschritt mit Freigabe.

## Global Constraints

- **Python ausschließlich** über `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python` (`backend/venv` und `backend/venv311` sind kaputt).
- **Einzeltests:** `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/<datei> -v -p no:cacheprovider`.
- **Vollauf:** nur nach der „Prozedur Vollauf" unten. Nur Fehlernamen vergleichen, nie Anzahlen.
- **Frontend-Prüfung** (aus `frontend/`): `./node_modules/.bin/tsc --noEmit -p .` (keine Ausgabe = gut) und `npm run build` (`tsc && vite build`, endet mit `✓ built in …`; die Warnung „Some chunks are larger than 500 kB" gab es schon vorher). `tsconfig.json` hat `noUnusedLocals` und `noUnusedParameters`: Jeder ungenutzte Import bricht den Build. `tsc -p .` prüft `tests/` nicht (`"include": ["src"]`); die Spec übersetzt erst Playwright.
- **Kein Netzwerk** in der Codex-Sandbox: kein `npm install`, kein `pip install`, kein `git pull`. Keycloak ist in allen Backend-Tests durch `httpx.MockTransport` ersetzt (Test-Naht `keycloak_admin._http_client`). Die Tests setzen Dummy-Umgebungsvariablen per `monkeypatch`; echte `KEYCLOAK_*`-Werte werden nie gebraucht, gelesen oder ausgegeben. Einen Dev-Server oder Browser startet der Worker nicht; die Playwright-Abnahme fährt der Manager.
- **Keine Geheimnisse ausgeben:** kein Passwort, Token oder Secret in Logs, Fehlermeldungen, Commit-Texten oder `console.*`. Fehlermeldungen an den Client enthalten nur den HTTP-Status, nie den Antworttext von Keycloak. Im Frontend steht ein Einmalpasswort nur im React-State, solange sein Dialog offen ist (nie localStorage, nie URL). Die beiden Mutationen mit Passwort in der Antwort haben `gcTime: 0`, und `passwortMutation.reset()` läuft beim Schließen des Dialogs.
- **Kein Hard-Delete:** keine DELETE-Route, kein `DELETE /admin/realms/{realm}/users/{id}`, kein `usersApi.delete`. Deaktivieren heißt `PATCH {enabled: false}`.
- **Mandant nie aus dem Request:** Request-Schemas mit `extra="forbid"`; das Frontend schickt nie `tenant_slug` oder `attributes`.
- **Rollen:** Ein Mandanten-Admin vergibt nur `admin`, `sales`, `production_planner`, `production_staff`, `accounting`. Keine Plattform- oder Realm-Rollen (`realm-admin`, `offline_access`, `default-roles-…` usw.). Die Plattform-Admin-API (`backend/app/api/v1/platform.py`, Header `X-Platform-Admin-Key`) bleibt unberührt.
- **Kein master-Admin in Produktion:** `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN` gibt es nur für Entwicklung und Test. Der Worker setzt keine Umgebungsvariable außerhalb der Tests (`monkeypatch`).
- **Profilfelder:** Vorname, Nachname, E-Mail (nur beim Anlegen; sie ist der Benutzername), Rolle, aktiv. Telefon und Kürzel werden nicht gebaut (F11 offen, „Offene Punkte für Gernot" 1).
- **Nicht anfassen:** `backend/app/api/v1/invoices.py`, `sales.py`, `production.py`, `documents.py`, `platform.py`, `backend/app/api/deps.py`, `backend/app/tenancy.py`, `backend/tests/conftest.py`, `frontend/src/pages/Orders.tsx`, `Tagesplan.tsx`, `Invoices.tsx`, `Customers.tsx`, `frontend/src/components/domain/OrderDocumentsModal.tsx`, `frontend/src/types/index.ts`, `frontend/tests/e2e/full-suite.spec.ts`. Paket 1 und 2 ändern diese parallel. Kein Deploy, kein Zugriff auf Produktion oder Keycloak.
- **Neue Backend-Tests** ausschließlich in `backend/tests/test_benutzerverwaltung.py`.
- Fehler- und UI-Texte auf Deutsch.

## Prozedur Vollauf

Aus `backend/`. Im Prototyp dauerte der Lauf 45 Sekunden.

```bash
cd backend
sort > /tmp/b8-soll.txt <<'EOF'
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
FAILED tests/test_services.py::TestInvoiceService::test_invoice_totals_update
FAILED tests/test_services.py::TestInvoiceService::test_record_full_payment
FAILED tests/test_services.py::TestInvoiceService::test_record_partial_payment
EOF
REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q -p no:cacheprovider --ignore=tests/test_forecast_engine.py > /tmp/b8-vollauf.log 2>&1; tail -1 /tmp/b8-vollauf.log
grep -E "^(FAILED|ERROR)" /tmp/b8-vollauf.log | sed 's/ - .*//' | sort > /tmp/b8-ist.txt
diff /tmp/b8-soll.txt /tmp/b8-ist.txt && echo "Fehlernamen wie Baseline"
```

Erwartet: `diff` ohne Ausgabe, danach `Fehlernamen wie Baseline`. Das sind die 16 Baseline-Namen (15 FAILED, 1 ERROR); keiner stammt aus `test_benutzerverwaltung.py`. Die Schlusszeile von `tail` ist nur Information: Im Prototyp stand nach Task 7 dort `15 failed, 627 passed, 2 skipped, 1 error`. Die Zahl der bestandenen Tests wächst mit jedem Release; sie wird nie verglichen. Gibt `diff` etwas aus: stoppen und die Ausgabe von `diff` wörtlich melden.

## Review Focus (fünf Zustände ohne Testabdeckung, je ein Task)

Für diese fünf Zustände gibt es keinen automatischen Test, weil Keycloak-Attrappe, Testclient oder Dev-Nutzer sie nicht herstellen können. Der Reviewer prüft sie am Code; was sich messen lässt, misst die Manager-Abnahme.

1. **Task 1: echter Keycloak statt `FakeKeycloak`.** Die Attrappe legt Keycloak-Verhalten fest, das nur angenommen ist: `q=tenant_slug:<slug>` liefert Teiltreffer, ein `PUT /users/{id}` ohne `attributes` löscht die Attribute, `GET /users/{id}/role-mappings` antwortet mit `realmMappings`/`clientMappings`, eine Anlage antwortet 201 mit `Location`-Header, `GET /roles/<rolle>` ist für den Service-Account lesbar. Prüfen: Die Mandantentrennung hängt nie an der `q`-Suche allein (`_gehoert_zum_mandanten` in `_mandanten_reps` und `_lade_mandanten_user`), jeder `PUT /users/{id}` schickt die volle Darstellung samt `attributes`, und `_neue_user_id` verlangt ohne `Location` genau einen exakten Treffer. Gemessen wird das erst in Manager-Abnahme B (Keycloak 22) und in den Deploy-Gates D1–D3 (Produktionsversion).
2. **Task 4: Wettlauf um den letzten Admin.** `update_tenant_user` zählt mit `_aktive_admins` und schreibt danach, ohne Sperre über Prozesse hinweg. Zwei gleichzeitige PATCH-Aufrufe, in denen sich zwei Admins gegenseitig herabstufen oder deaktivieren, sehen beide noch einen anderen aktiven Admin; danach hat der Mandant keinen mehr. Prüfen: Die Reihenfolge ist Prüfung vor dem ersten Schreiben und öffnet keine weitere Lücke, und `verliert_admin` deckt Herabstufen und Deaktivieren ab. Das Restrisiko ist akzeptiert, Gernot erfährt es vor der Freigabe („Offene Punkte für Gernot" 3); wiederherstellen kann nur der Plattform-Betrieb (Offener Punkt M9).
3. **Task 6: Schreibbremse je Prozess.** `_schreibzeiten` liegt im Speicher eines Prozesses. Bei vier Gunicorn-Workern (`docker-compose.prod.yml:26-31`; **Annahme:** in Coolify ebenso) sind es bis zu 120 schreibende Aufrufe je Minute und Mandant, ein Neustart setzt zurück, und Lesen (`GET /users`, je Benutzer ein Keycloak-Aufruf) bleibt ungebremst. Der Test sieht nur einen Prozess. Prüfen: Schlüssel ist der Mandant aus `_mandant_schreiben`, nie IP oder Body; die Demo-Sperre (403) greift vor der Bremse, ein gesperrter Aufruf zählt nicht (Offener Punkt M8).
4. **Task 10: Einmalpasswort nach dem Schließen weg.** Die Spec prüft nur, dass Esc den Dialog nicht schließt und das Passwort nach „Passwort ist notiert" nicht mehr im DOM steht. Nicht geprüft ist, dass es auch aus dem MutationCache von TanStack Query verschwindet. Prüfen: `gcTime: 0` an `anlegenMutation` und `passwortMutation`, `passwortMutation.reset()` und `setEinmalPasswort(null)` im `onClose` von `EinmalPasswortDialog`, kein `console.*`, kein `localStorage.setItem`, kein Passwort in einer URL.
5. **Task 11: Weg für Nicht-Admins.** Der Dev-Nutzer (`DEV_USER`, `frontend/src/context/AuthContext.tsx:24-30`) hat immer alle Rollen; Spec und lokale Sichtprüfung sehen nur den Admin. Ungetestet: Für `sales`, `accounting`, `production_planner` und `production_staff` fehlt „Benutzerverwaltung" in der Befehlspalette, und `/users` zeigt „Kein Zugriff" ohne Abfrage (Seite aus Task 10). Prüfen: `istAdmin={user.role === 'ADMIN'}` in `Layout.tsx`, die Bedingung `...(istAdmin ? [...] : [])` und die `useMemo`-Abhängigkeit `[go, istAdmin]` in `CommandPalette.tsx`. Live-Prüfung L4 nach dem Deploy; das Backend weist Nicht-Admins ohnehin mit 403 ab (`TestZugriff::test_nur_admin_liest`).

## Sicherheits-Abnahme

Jedes Angriffsszenario mit dem Test, der es abdeckt. Backend-Tests in `backend/tests/test_benutzerverwaltung.py` (Klasse::Test), Frontend-Tests als Titel in `frontend/tests/e2e/benutzerverwaltung.spec.ts`. Abgenommen ist ein Szenario, wenn seine Tests grün sind (Task 7, Manager-Abnahme A).

| # | Angriff | Erwartet | Test | Task |
|---|---|---|---|---|
| S1 | Admin von Mandant A liest einen Benutzer von B per ID | 404 mit demselben Body wie eine unbekannte ID; Audit `FREMDZUGRIFF_ABGEWIESEN` | `TestFremderMandantLesen::test_fremd_wie_unbekannt`, `TestFremderMandantLesen::test_fremdzugriff_im_audit`, `TestDienstLesen::test_fremder_benutzer_ist_nicht_gefunden` | 1, 2 |
| S2 | Konten mit ähnlichem oder fehlendem `tenant_slug` (`devx`, `xdev`, kein Attribut) tauchen auf | nicht in der Liste, 404 beim Einzelabruf | `TestDienstLesen::test_liste_filtert_exakt`, `TestListe::test_nur_eigener_mandant`, `TestFremderMandantLesen::test_benutzer_ohne_attribut_ist_fremd`, `TestFremderMandantLesen::test_aehnlicher_slug_ist_fremd` | 1, 2 |
| S3 | Slug erweitert die Keycloak-Suche (`dev tenant_slug:fremdfirma`) | Fehler vor jedem Keycloak-Aufruf | `TestDienstLesen::test_slug_kann_die_suche_nicht_erweitern` | 1 |
| S4 | Pfad-Tricks in der ID (`../roles/admin`, `<id>?first=0`), auch über die Dienstfunktionen | 404 bzw. 422; Keycloak wird nicht erreicht | `TestDienstLesen::test_id_ohne_uuid_erreicht_keycloak_nicht`, `TestFremderMandantLesen::test_ungueltige_id`, `TestPasswort::test_dienst_prueft_id_selbst` | 1, 2, 5 |
| S5 | Fremden Benutzer deaktivieren, umbenennen oder zum Admin machen | 404, kein schreibender Keycloak-Aufruf | `TestFremderMandantAendern::test_404_und_kein_schreibzugriff`, `TestFremderMandantAendern::test_benutzer_ohne_attribut` | 4 |
| S6 | Passwort eines fremden Benutzers zurücksetzen | 404, kein Passwort gesetzt | `TestPasswort::test_fremd_404_und_kein_schreibzugriff` | 5 |
| S7 | Betreiber- oder Supportkonto mit eigenem `tenant_slug` übernehmen (Client-Rolle `realm-admin`, Gruppe, fremde oder zusammengesetzte Realm-Rolle) | 409 „vom Support verwaltet", kein Schreiben, Audit `SUPPORTKONTO_ABGEWIESEN`; gewöhnliches Konto bleibt änderbar | `TestPasswort::test_supportkonto_nicht_uebernehmbar`, `TestSupportkontenAendern::test_abgewiesen_ohne_schreibzugriff`, Gegenprobe `TestAendern::test_standardkonto_ist_aenderbar` | 4, 5 |
| S8 | Mandant über den Body setzen (`tenant_slug`, `attributes`) | 422, kein Schreiben; das Frontend schickt genau vier Felder | `TestAnlegen::test_mandant_aus_body_abgelehnt`; Spec „Anlegen schickt genau die vier Felder und zeigt das Einmalpasswort einmal" | 3, 12 |
| S9 | Realm- oder Plattformrolle vergeben (`realm-admin`, `offline_access`, `readonly`, `ADMIN`, leer) | 422 (API) bzw. `RolleNichtErlaubt` (Dienst), kein Keycloak-Aufruf; drei Rollenlisten gleich | `TestAnlegen::test_rolle_ausserhalb_allowlist`, `TestAendern::test_rolle_ausserhalb_allowlist`, `TestAnlegen::test_dienst_prueft_rolle_selbst`, `TestAendern::test_dienst_prueft_rolle_selbst`, `test_rollenlisten_stimmen_ueberein` | 2, 3, 4 |
| S10 | App-Rolle ist in Keycloak zusammengesetzt (vergäbe mehr, z. B. `realm-management`) oder fehlt | 503, nichts angelegt bzw. nichts geschrieben | `TestAnlegen::test_zusammengesetzte_rolle_nicht_vergeben`, `TestAnlegen::test_rolle_fehlt_im_realm_nichts_angelegt`, `TestAendern::test_fehlende_rolle_nichts_geschrieben` | 3, 4 |
| S11 | Nicht-Admin (`sales`, `production_planner`, `production_staff`, `accounting`) ruft die API | 403 ohne Keycloak-Aufruf | `TestZugriff::test_nur_admin_liest`, `TestAnlegen::test_nur_admin_legt_an`, `TestAendern::test_nur_admin_aendert`, `TestPasswort::test_nur_admin` | 2–5 |
| S12 | Token ohne Mandant (Basic-Auth, `AUTH_DISABLED`), Token eines anderen Mandanten, Token ohne `sub` | 403 ohne Keycloak-Aufruf; der Selbstschutz greift nicht ins Leere | `TestZugriff::test_ohne_mandant_im_token`, `TestZugriff::test_token_anderer_mandant`, `TestZugriff::test_ohne_sub_im_token`, `TestSchutzregeln::test_ohne_sub_kein_selbstdeaktivieren` | 2, 4 |
| S13 | Demo-Besucher mit öffentlichem Login sperrt Demo-Konten oder setzt ihre Passwörter zurück | im Mandanten `demo` lesen ja, schreiben 403 | `TestAnlegen::test_demo_gesperrt`, `TestAendern::test_demo_gesperrt`, `TestPasswort::test_demo_gesperrt`; Spec „Demo: Liste lesbar, Schreiben endet mit dem 403 im Klartext" | 3–5, 12 |
| S14 | Öffentlicher Demo-Login mit verstelltem `tenant_slug` schreibt in einem fremden Mandanten | 403 in jedem Mandanten (Benutzername oder E-Mail aus `DEMO_USERS`) | `TestAnlegen::test_demo_login_schreibt_in_keinem_mandanten` (POST; PATCH und Reset hängen an derselben Abhängigkeit `MandantSchreiben`) | 3 |
| S15 | Halb angelegter Benutzer bleibt aktiv, oder das Aufräumen deaktiviert einen Fremden | deaktiviert und ohne Rolle; der Fremde bleibt unberührt | `TestAnlegen::test_attribut_nicht_gespeichert_keine_rolle`, `TestAnlegen::test_lesen_nach_anlage_scheitert_deaktiviert`, `TestAnlegen::test_rueckfall_suche_trifft_keinen_fremden` | 3 |
| S16 | Ein `PUT` verliert `tenant_slug`, das Konto fällt aus dem Mandanten | Attribute bleiben erhalten | `TestAendern::test_name_aendern_behaelt_mandant` | 4 |
| S17 | Aussperren: sich selbst deaktivieren oder herabstufen, letzten aktiven Admin verlieren | 409 | `TestSchutzregeln::test_selbst_deaktivieren`, `TestSchutzregeln::test_selbst_herabstufen`, `TestSchutzregeln::test_letzter_aktiver_admin`; Spec „das eigene Konto ist vor Aussperren geschützt" | 4, 10, 12 |
| S18 | Konto hart löschen | keine DELETE-Route (405); das Frontend ruft nie DELETE | `TestZugriff::test_kein_loeschen`, `test_routen_vollstaendig_ohne_loeschen`, `TestAendern::test_deaktivieren_statt_loeschen`; Spec „Deaktivieren fragt nach, löscht nie und lässt sich rückgängig machen" | 2, 4, 7, 12 |
| S19 | Kompromittiertes oder deaktiviertes Konto bleibt per Refresh-Token angemeldet | `POST /users/{id}/logout` nach Deaktivieren, Rollenwechsel und Reset; der Reset liefert das Passwort auch, wenn der Logout scheitert | `TestPasswort::test_reset_beendet_sitzungen`, `TestAendern::test_rollenwechsel_beendet_sitzungen`, `TestAendern::test_deaktivieren_statt_loeschen`, `TestPasswort::test_logout_scheitert_passwort_trotzdem_geliefert` | 4, 5 |
| S20 | Stiller Rückfall auf den master-Admin (ein Fehler träfe alle Realms) | 503 „Service-Account fehlt" ohne Keycloak-Aufruf; master nur mit Schalter | `TestDienstLesen::test_ohne_service_account_geschlossen`, `TestDienstLesen::test_master_admin_nur_mit_freigabe`, `TestDienstLesen::test_service_account_im_zielrealm`, `TestAusfallLesen::test_nicht_eingerichtet` | 1, 2 |
| S21 | Verwaltung im falschen Realm (Default `novaerp` aus `_cfg()`) | Realm = `settings.keycloak_realm` | `TestDienstLesen::test_realm_wie_tokenpruefung` | 1 |
| S22 | Keycloak mit Anmeldungen fluten (eine je Request) | ein Token je Prozess und Laufzeit; nach 401 genau eine Neuanmeldung | `TestDienstLesen::test_token_wird_wiederverwendet`, `TestDienstLesen::test_abgelaufenes_token_wird_einmal_erneuert` | 1 |
| S23 | Schreibaufrufe in Serie; fremde E-Mail-Adressen per 409 abklopfen | ab dem 31. schreibenden Aufruf je Minute 429 ohne Keycloak, Lesen frei, eigener Zähler je Mandant; jeder 409 im Audit `ANLAGE_ABGELEHNT` | `TestSchreibbremse::test_schreibbremse_je_mandant`, `TestAnlegen::test_email_vergeben` | 3, 6 |
| S24 | Passwort landet in Logzeilen oder Zwischenspeichern | kein Passwort im Log; `Cache-Control: no-store` an beiden Antworten mit Passwort | `TestAnlegen::test_audit_ohne_passwort`, `TestPasswort::test_audit_ohne_passwort`, `TestAnlegen::test_mitarbeiter_anlegen`, `TestPasswort::test_reset_liefert_einmalpasswort` | 3, 5 |
| S25 | Teilweise Änderung ohne Spur | alles ohne Schreiben Prüfbare vor dem ersten Schreiben; Rest im Audit `BENUTZER_TEILWEISE_GEAENDERT` | `TestAendern::test_fehlende_rolle_nichts_geschrieben`, `TestAendern::test_teilweise_geaendert_im_audit` | 4 |
| S26 | Ladefehler erscheint als leere Liste, der Admin legt Konten doppelt an | Fehlerzustand mit Serverwortlaut, kein „Neuer Benutzer" | Spec „ein Ladefehler erscheint als Fehler, nicht als leere Liste" | 10, 12 |
| S27 | Konto mit mehreren Rollen verliert beim Umbenennen Rollen | PATCH enthält nur geänderte Felder; eine gewählte Rolle wird die einzige | Spec „mehrere Rollen: Umbenennen behält sie, die höchste wählen stuft darauf zurück", „Rolle ändern schickt nur die Rolle" | 10, 12 |

**Ohne automatischen Test, deshalb Gate oder Review:**

- Benutzer ändert sein eigenes `tenant_slug` über Account-Konsole oder Account-REST-API und wechselt damit den Mandanten (besteht unabhängig von diesem Plan, falls der Realm es zulässt): Deploy-Gate D5, lokal nachgestellt in Manager-Abnahme B, Zeile K8.
- Selbstregistrierung mit eigenen Attributen: D5.
- App-Rolle `admin` oder `default-roles-<realm>` enthält `realm-management`-Rollen: D3. Der Code vergibt keine zusammengesetzte App-Rolle (S10), lässt die Standardrolle aber als einzige zusammengesetzte zu.
- Service-Account mit mehr Rechten als nötig, master-Schalter in Produktion gesetzt: D7.
- Konten mit `realm-management`-Rollen und Kunden-`tenant_slug`: D6 (der Code weist sie mit 409 ab, S7).
- Nicht-Admin in der Oberfläche: Review Focus 5, Live-Prüfung L4.
- Wettlauf um den letzten Admin: Review Focus 2.
- Ein schon ausgestelltes Access-Token gilt nach Deaktivieren oder Reset bis zu seinem Ablauf weiter: Offener Punkt M4.

## File Structure

| Datei | Verantwortung | Task |
|---|---|---|
| `backend/app/services/keycloak_admin.py` | Modulkopf (Docstring, Imports, Logger), neuer Abschnitt „Benutzerverwaltung je Mandant" am Dateiende; bestehende Zeilen unverändert | 1, 3, 4, 5 |
| `backend/app/schemas/user.py` | **neu** — Request-/Response-Schemas, `Rolle` als `Literal` | 2 |
| `backend/app/api/v1/users.py` | **neu** — Router `/users`, Mandanten-Abhängigkeit, Demo-Sperre, Schreibbremse, Fehlerabbildung, Audit | 2, 3, 4, 5, 6 |
| `backend/app/main.py` | Importzeile nach Z. 34, `include_router` mit `_deps_admin` nach dem `admin.router`-Block (Z. 807–811) | 2 |
| `backend/tests/test_benutzerverwaltung.py` | **neu** — Keycloak-Attrappe und alle Backend-Tests dieses Plans | 1–7 |
| `frontend/src/services/rollen.ts` | **neu** — fünf Mandanten-Rollen, deutsche Bezeichnung, Beschreibung, Hinweis | 9 |
| `frontend/src/services/api.ts` | Attrappe raus, `usersApi` und Typen nach dem Vertrag (nur der Block zwischen den beiden Ankerkommentaren) | 10 |
| `frontend/src/components/domain/UserCard.tsx` | Karte je Benutzer: Rollen, Status, Aktionen | 10 |
| `frontend/src/pages/Users.tsx` | Seite: Admin-Prüfung, Liste, Formular, Rückfragen, Einmalpasswort | 10 |
| `frontend/src/components/common/CommandPalette.tsx` | Eintrag „Benutzerverwaltung" nur für Administratoren | 11 |
| `frontend/src/components/common/Layout.tsx` | reicht `istAdmin` an die Befehlspalette (nur der Aufruf `:594`) | 11 |
| `frontend/tests/e2e/benutzerverwaltung.spec.ts` | **neu** — Abnahme-Spec mit gemockter API (übersprungen ohne `U2_ABNAHME_URL`) | 12 |

Task 8 liest nur. Insgesamt zwölf Dateien; `git diff --stat efcea00..HEAD` zeigt am Ende genau diese.

## Referenz: HTTP-Vertrag

Router `prefix="/users"`, eingebunden mit `prefix="/api/v1"` und `dependencies=_deps_admin`. Das Frontend ruft über `${API_URL}/api/v1` (`frontend/src/services/api.ts:21-28`).

| Methode und Pfad | Body | Erfolg | Fehler |
|---|---|---|---|
| `GET /api/v1/users` | – | 200 `{items: Benutzer[], total}`, sortiert nach Nachname, Vorname, E-Mail | 403 keine Admin-Rolle / kein Keycloak-Login dieses Mandanten / Token ohne `sub`; 503 Keycloak nicht erreichbar oder nicht eingerichtet (auch: Service-Account fehlt) |
| `POST /api/v1/users` | `{email, first_name, last_name, role}` | 201 `Benutzer` + `temporary_password`, Header `Cache-Control: no-store` | 422 Validierung (Rolle, E-Mail, Umlaut, Zusatzfelder wie `tenant_slug`); 409 E-Mail vergeben; 403 Demo-Mandant oder Demo-Login; 429 Schreibbremse; 503 (auch: Rolle fehlt oder ist zusammengesetzt; halb angelegt und deaktiviert); 502 |
| `GET /api/v1/users/{id}` | – | 200 `Benutzer` (vom Frontend nicht genutzt) | 404; 422 keine UUID |
| `PATCH /api/v1/users/{id}` | Teilmenge von `{first_name, last_name, role, enabled}`, mindestens ein Feld; **kein** `email` | 200 `Benutzer` | 404; 409 Schutzregel oder „vom Support verwaltet"; 422; 403 Demo; 429; 503; 502 |
| `POST /api/v1/users/{id}/reset-password` | – | 200 `{user: Benutzer, temporary_password}`, `Cache-Control: no-store` | 404; 409 „vom Support verwaltet"; 403 Demo; 429; 503; 502 |

`Benutzer` = `{id, email, first_name, last_name, role: Rolle | null, roles: Rolle[], enabled, created_at: ISO-Zeit | null, is_self}`; `Rolle` = `"admin" | "production_planner" | "sales" | "accounting" | "production_staff"` (klein, wie im Token). `role` ist die höchste App-Rolle nach Rangfolge, `roles` alle direkt zugewiesenen App-Rollen. `PATCH role` setzt **genau** diese eine App-Rolle und entfernt alle anderen App-Rollen, auch wenn `role` gleich der bisher höchsten ist (bei `roles = ['sales', 'accounting']` macht `{role: 'sales'}` daraus `['sales']`). Andere Realm-Rollen (`offline_access` usw.) bleiben. Viele Bestandskonten haben mehrere App-Rollen; `keycloak/realm-export.json` gibt `admin`, `thomas` und `gernot` je `admin`, `production_planner`, `production_staff` und `sales`. Deaktivieren, Rollenwechsel und Passwort-Reset beenden die Sitzungen des Zielbenutzers. Ein DELETE gibt es nicht (405). `last_login` und `phone` der Attrappe gibt es nicht.

Feste Fehlertexte, immer als `detail` (`getErrorMessage`, `frontend/src/services/errors.ts:10-32`, zeigt sie im Klartext):

- 404 `Benutzer nicht gefunden.` — fremd und unbekannt identisch.
- 409 `Diese E-Mail-Adresse ist bereits vergeben.` · `Das eigene Konto kann nicht deaktiviert werden.` · `Die eigene Admin-Rolle kann nur ein anderer Admin ändern.` · `Der letzte aktive Admin des Mandanten kann nicht deaktiviert oder herabgestuft werden.` · `Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden.`
- 403 `Benutzerverwaltung nur mit einem Keycloak-Login dieses Mandanten.` · `In der Demo können Benutzer nicht geändert werden.` · `Mit einem Demo-Login können Benutzer nicht geändert werden.`; dazu der 403 aus `require_access` für Nicht-Admins.
- 429 `Zu viele Änderungen in kurzer Zeit. Bitte in einer Minute erneut versuchen.`
- 503 `Benutzerverwaltung derzeit nicht verfügbar: …`, z. B. `… Benutzerverwaltung ist nicht eingerichtet (Service-Account fehlt: KEYCLOAK_USERS_CLIENT_ID/_SECRET).`
- 502 `Keycloak hat die Anfrage abgelehnt: …`
- 400 nur bei Aufruf der Dienstfunktion mit fremder Rolle (`RolleNichtErlaubt`); über die API greift vorher die 422.

**Für das Frontend:** `role` im PATCH nur mitschicken, wenn sie im Formular gewählt wurde; bei mehreren Rollen ist keine vorgewählt. Deaktivieren und Aktivieren laufen über `PATCH {enabled}`. Im Mandanten `demo` enden `POST /users`, `PATCH /users/{id}` und `POST /users/{id}/reset-password` immer mit dem Demo-403; `GET /users` bleibt erlaubt. Die Oberfläche zeigt die Schreibknöpfe trotzdem (Offener Punkt M6).

## Referenz: Ausgangsbefund (am Code belegt, `efcea00`)

**Backend und Keycloak**

- **Mandant des Requests:** `tenant_middleware` (`main.py:316-354`) löst den Slug aus dem Host (`tenancy.resolve_slug_from_host`, `tenancy.py:174-205`; `localhost` → `DEFAULT_TENANT_SLUG`, `tenancy.py:186-188`, Standard `dev`, `tenancy.py:53`) und legt ihn in `request.state` ab (`set_request_tenant`, gelesen über `get_request_tenant`, `tenancy.py:394-400`). Für `/api/`-Pfade ohne Slug antwortet die Middleware 404 (`main.py:334-340`); `/api/v1/platform` und der Admin-/Apex-Host laufen ohne Mandant.
- **Mandant im Token:** `get_current_user` (`api/deps.py:26-98`) liest den Claim `tenant_slug` (`:73`), lehnt Host ≠ Token mit 403 ab (`:76-80`) und ebenso Host gesetzt, Claim fehlt (`:81-85`). Rückgabe enthält `"tenant_slug": token_tenant` (`:95`). **Ausnahmen ohne `tenant_slug`:** `AUTH_DISABLED` (`:38-46`, alle fünf Rollen) und Basic-Auth (`:49-57`, `admin` bei Rolle FULL). Beide überspringen die Mandantenprüfung; die Benutzerverwaltung lässt sie deshalb nicht herein (Task 2, `_mandant`).
- **Rollen:** fünf Konstanten `main.py:82-88` (`ALLE_ROLLEN`), `_deps_admin = _rollen()` (`main.py:137`) heißt: lesen und schreiben nur `admin` (`_rollen`, `main.py:91-104`; `require_access`, `deps.py:126-152`). Realm-Rollen aus `realm_access.roles` (`deps.py:87-89`). Rangfolge im Frontend `ROLLEN_RANGFOLGE` (`frontend/src/components/common/Layout.tsx:288-294`): admin, production_planner, sales, accounting, production_staff.
- **Keycloak-Helfer heute** (`services/keycloak_admin.py`): `_cfg()` (`:40-49`) liest `KEYCLOAK_URL`, `KEYCLOAK_REALM` (Default **`novaerp`**), `KEYCLOAK_ADMIN_USER/_PASSWORD`; `_admin_token` (`:52-66`) meldet sich als **master-Realm-Admin** an; `_gen_password` (`:69-71`, 16 Zeichen + `!A9`); `create_tenant_user` (`:74-173`) legt an mit `attributes.tenant_slug`, `credentials[].temporary`, `requiredActions: []`, sucht die ID per `username`+`exact`, prüft die Rolle **erst nach** der Anlage (`:147-153`) und weist sie direkt zu (`:154-164`). Liste, Ändern, Deaktivieren, Passwort-Reset gibt es nicht. Kein Aufruf von `execute-actions-email` im Repo (grep).
- **Realm-Mismatch der Defaults:** Die Token-Prüfung nutzt `settings.keycloak_realm` (`config.py:39`, Default `minga-greens`; `core/security.py:69`), der Helfer `os.environ["KEYCLOAK_REALM"]` mit Default `novaerp`. In Produktion setzt dieselbe Variable beide (T5 1.4). Task 1 nimmt für die Benutzerverwaltung **`get_settings().keycloak_realm`** — garantiert den Realm, aus dem das Token des Aufrufers stammt.
- **Onboarding:** `platform.create_tenant` (`platform.py:72-157`) ruft `create_tenant_user(..., role="admin", temporary_password=bool(not admin_password))` (`:141-147`) und gibt das Passwort genau einmal in `result["admin_user"]` zurück (`:148-153`). Task 3 und Task 5 übernehmen dieses Muster (Einmalpasswort, temporär) für Anlegen und Reset.
- **Demo:** Tenant `demo` mit öffentlich bekannten Logins (`DEMO_USERS`, `DEMO_PASSWORD = "demo1234"`, `platform.py:229-235`; `anna@demo.novaerp.de` ist `admin`). Der nächtliche Reset kopiert nur die SQLite-Datei (`demo_reset_service.py:58-72`, `shutil.copy2` `:70`), **Keycloak bleibt unberührt**. Ohne Sperre könnte jeder Demo-Besucher als Anna Ben, Clara und Paul deaktivieren oder ihre Passwörter zurücksetzen — dauerhaft. Deshalb sperrt Task 3 im Mandanten `demo` jedes Schreiben (403 „In der Demo können Benutzer nicht geändert werden."), Lesen bleibt erlaubt. Diese Sperre bleibt; schreibende Abnahmen laufen nie auf der Demo. Konstante `DEFAULT_DEMO_SLUG = "demo"` (`demo_reset_service.py:19`).
- **Audit:** Einzige Audit-Tabelle ist `order_audit_logs` (`models/order.py:354-397`) mit Pflicht-Fremdschlüssel `order_id` (`:364`) — für Benutzeraktionen untauglich. Die App konfiguriert kein Logging (kein `basicConfig`/`dictConfig` unter `backend/app`; Start ohne Log-Konfiguration: `Dockerfile:44` `uvicorn app.main:app`, `docker-compose.prod.yml:25-31` gunicorn nur mit `--access-logfile -`). INFO aus `app.*` verwirft Pythons lastResort-Handler (gibt erst ab WARNING aus). Betriebszeilen, die im Log stehen sollen, schreibt das Repo mit `logger.warning` (`main.py:161`, `:200`). Task 2 schreibt die Audit-Zeile ebenso als WARNING.
- **Tests:** `client`-Fixture (`tests/conftest.py:59-80`) überschreibt `get_current_user` und nutzt `base_url="http://localhost"`; Muster für Rollen-Overrides in `tests/test_rollen.py:21-29`. Bisher testet keine Datei den Keycloak-Helfer (T5 3.4). `httpx.MockTransport` ist Teil von httpx (`requirements.txt:19`; in `.venv` 0.28.1) — keine neue Abhängigkeit.
- **Keycloak-Server-Version:** im Repo `quay.io/keycloak/keycloak:22.0` (`docker-compose.yml:152`), Produktion nicht im Code prüfbar. **Annahme:** Attributsuche `q=key:value` auf `GET /admin/realms/{realm}/users` vorhanden (Keycloak ≥ 15) — ob exakt oder als Teiltreffer, hängt von der Version ab; deshalb der Python-Filter. **Annahme:** Ein `PUT /users/{id}` ohne `attributes` kann je nach Version (User Profile ab 24) Attribute verwerfen; deshalb schreibt Task 4 immer die vollständige Darstellung samt `attributes` zurück.
- **Darf ein Benutzer sein eigenes `tenant_slug` ändern? Im Repo nicht abgesichert.** Keycloak 22.0 (`docker-compose.yml:152`) startet ohne die Option `--spi-user-profile-legacy-user-profile-read-only-attributes` (`docker-compose.prod.yml:45`). `keycloak/realm-export.json` enthält keine User-Profile-Konfiguration und beschreibt den Realm `minga-greens` (`:2`). Der Produktions-Realm `novaerp` steht nicht im Repo. **Annahme aus der Keycloak-Dokumentation, nicht im Repo prüfbar:** Unter Version 24 mit dem alten User-Profile, oder ab 24 mit `unmanagedAttributePolicy=ENABLED`, kann ein Benutzer eigene Attribute über die Account-Konsole bzw. die Account-REST-API ändern. Dann wechselt jeder Login den Mandanten, auch die öffentlichen Demo-Logins (`demo1234`): `tenant_slug=minga` setzen, neues Token holen, und `deps.py:76-85` lässt ihn auf `minga.novaerp.de` als Admin herein. Diese Lücke besteht schon heute. Mit diesem Plan käme die dauerhafte Übernahme auf Keycloak-Ebene dazu: eigenen Admin anlegen, Gernots Passwort zurücksetzen. Deshalb Deploy-Gate D5. Im Code schreibt zusätzlich kein öffentlicher Demo-Login in irgendeinem Mandanten (Task 3, `_mandant_schreiben`). `editUsernameAllowed` ist im Repo-Realm `false` (`realm-export.json:11`). Der Benutzername taugt daher als Merkmal, die E-Mail nicht sicher.
- **Rollen außerhalb der App-Rollen:** `GET /users/{id}/role-mappings/realm` liefert nur direkte Realm-Rollen. Client-Rollen (`realm-management`: `realm-admin`, `manage-users` …) und Gruppen sieht diese Abfrage nicht. Ein Betreiber- oder Support-Konto mit `tenant_slug` eines Mandanten wirkte in der Liste wie ein gewöhnlicher Benutzer. Ein Passwort-Reset würde es dem Mandanten-Admin übergeben, und damit den ganzen Realm. Deshalb liest der Dienst vor jedem Schreiben (Task 4, `_pruefe_verwaltbar`) `GET /users/{id}/role-mappings` (Realm und Clients) und `GET /users/{id}/groups`.
- **Kein Rate-Limit auf neuen Routen:** `Limiter(..., default_limits=["120/minute"])` (`main.py:62`) wirkt ohne `SlowAPIMiddleware` nicht. Registriert sind nur `app.state.limiter` und der Exception-Handler (`main.py:298-299`), begrenzt sind nur die dekorierten Routen `main.py:928` und `:992`. Task 1 vermeidet deshalb eine Keycloak-Anmeldung je Request (Token-Cache), Task 6 bremst schreibende Aufrufe je Mandant; Lesen bleibt ungebremst (Offener Punkt M8).

**Frontend**

- **Attrappe:** `frontend/src/services/api.ts:1015-1121`, der Block zwischen `// ============== Users API (Mock Data) ==============` und `// ==================== GROWTH-TIMELINE-EVENTS ====================`.
  - `MOCK_USERS_KEY = 'minga-mock-users'` (`:1019`), sieben erfundene Nutzer `defaultMockUsers` (`:1021-1029`).
  - `getMockUsers` schreibt sie beim ersten Aufruf in den localStorage (`:1031-1038`).
  - `usersApi.list/get/create/update/delete` arbeiten nur darauf (`:1044-1121`); `delete` löscht hart.
  - Der Block importiert mitten in der Datei `import type { User, UserRole } from '../types'` (`:1016`).
- **Einziger Aufrufer:** `frontend/src/pages/Users.tsx` (Route `users`, `App.tsx:83`). `components/domain/UserCard.tsx` wird nur dort verwendet (grep über `frontend/src`). Fehler erscheinen ohne Serverdetail (`Users.tsx:57-59`, `:248-249`). Der Löschdialog warnt „kann nicht rückgängig gemacht werden" (`:198-208`).
- **Rollenbasiertes Ausblenden heute:**
  - Menü: Jeder Eintrag in `navigationSections` trägt `roles`. Die Benutzerverwaltung hat `roles: ['ADMIN']` (`Layout.tsx:249-254`). Gefiltert wird in `Layout.tsx:371-380` (`item.roles.includes(user.role)`).
  - `user.role` ist die höchste Rolle aus dem Token (`ROLLEN_RANGFOLGE`, `rolleAusToken`, `Layout.tsx:288-303`). `ADMIN` gilt genau dann, wenn das Token `admin` enthält.
  - Seiten lesen die Rolle über `useUser()` (`Layout.tsx:277-283`). Muster: `Dashboard.tsx:35-36` (Rolle lesen), `:79` (Sichtbarkeit), `:83` (`enabled:` an der Abfrage).
  - **Lücke 1:** Die Routen haben keinen Schutz (`App.tsx:45-87`). `/users` ist per URL für jede Rolle erreichbar.
  - **Lücke 2:** Die Befehlspalette (Strg+K) listet „Benutzerverwaltung" für jede Rolle (`CommandPalette.tsx:72`; die Datei prüft keine Rolle). Sie wird nur in `Layout.tsx:594` gerendert, innerhalb des `UserContext.Provider` (`:390-596`).
  - Das Backend sperrt trotzdem: Task 2 hängt den Router an `_deps_admin` (`main.py:137`).
- **Fehlertexte:** `getErrorMessage(error, fallback)` in `frontend/src/services/errors.ts:10-32` (String-`detail`, FastAPI-422-Listen, Objekt mit `msg`).
- **Dialoge:** `Modal` (`components/ui/Modal.tsx`) schließt per Voreinstellung über Esc (`closeOnEscape = true`, `:32-41`) und über das X im Kopf, sobald ein `title` gesetzt ist (`:75-86`). `closeOnBackdrop={false}` allein schützt ein Einmalpasswort also nicht vor einem versehentlichen Esc.
- `User`/`UserRole` (`types/index.ts:345-357`) beschreiben den **angemeldeten** Benutzer (`Layout.tsx:41`, `:328-334`) und bleiben unverändert.
- **tsc-Baseline** `main` @ `efcea00`: `./node_modules/.bin/tsc --noEmit -p .` ohne Ausgabe (geprüft 08.10.). `tsconfig.json` hat `noUnusedLocals` und `noUnusedParameters`: Jeder ungenutzte Import bricht den Build.
- Frontend-Unit-Tests gibt es nicht. Playwright liegt unter `frontend/tests/e2e` (`playwright.config.ts`: `testDir: './tests/e2e'`, `retries: 1`). Die vorhandenen Specs laufen gegen die Demo mit echtem Login.

---

## Tasks (Backend: 1–7, Frontend: 8–12)

### Task 1: Keycloak-Dienst — Zugang, Mandantenprüfung, Lesen

**Files:**
- Modify: `backend/app/services/keycloak_admin.py:1-20` (Modulkopf), Dateiende (neuer Abschnitt)
- Create: `backend/tests/test_benutzerverwaltung.py`

**Interfaces:**
- Consumes: `_require_safe_slug` (`keycloak_admin.py:33-37`), `_gen_password` (`:69-71`, ab Task 3), `KeycloakAdminError` (`:23-24`), `app.config.get_settings`. `_admin_token` (`:52-66`) wird **nicht** benutzt: Es liefert kein `expires_in`, das der Token-Cache braucht.
- Produces (in `app.services.keycloak_admin`):
  - `MANDANTEN_ROLLEN: tuple[str, ...]` = `("admin", "production_planner", "sales", "accounting", "production_staff")`
  - Ausnahmen, alle Unterklassen von `KeycloakAdminError`: `KeycloakNichtErreichbar`, `KeycloakNichtGefunden(fremd: bool = False)` mit Attribut `.fremd`, `KeycloakKonflikt`, `BenutzerSchutzregel`, `BenutzerVomSupportVerwaltet` (Unterklasse von `BenutzerSchutzregel`, fester Text „Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden."), `RolleNichtErlaubt`
  - `_http_client() -> httpx.Client` — Test-Naht
  - `_require_user_id(user_id) -> str` — kanonische UUID, sonst `KeycloakNichtGefunden()`
  - `_users_cfg() -> dict` — fail-closed: nur Service-Account (`KEYCLOAK_USERS_CLIENT_ID`/`_SECRET`), master-Admin nur mit `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN=1`, sonst `KeycloakNichtErreichbar` „… nicht eingerichtet (Service-Account fehlt …)"
  - `_neues_token(c, client) -> tuple[str, float]`, `_users_token(c, client, *, erneuern=False) -> str`; Cache `_token_cache` (Modulvariable, Tests setzen sie je Test zurück), `_token_lock`
  - `_Benutzerzugang` (Kontextmanager; `.call(method, path, **kw) -> httpx.Response`, `.c` = Konfiguration); bildet `httpx.TransportError` und HTTP ≥ 500 auf `KeycloakNichtErreichbar` ab; nach HTTP 401 genau eine Neuanmeldung
  - `_gehoert_zum_mandanten(rep, tenant_slug) -> bool`, `_lade_mandanten_user(kc, user_id, tenant_slug) -> dict`, `_rollen_mappings(kc, user_id) -> list[dict]`, `_app_rollen(kc, user_id) -> list[str]`, `_als_benutzer(rep, rollen) -> dict` (Schlüssel `id, email, first_name, last_name, enabled, roles, role, created_at`), `_mandanten_reps(kc, tenant_slug) -> list[dict]`
  - `list_tenant_users(tenant_slug: str) -> list[dict]`, `get_tenant_user(tenant_slug: str, user_id: str) -> dict`
- Produces (Test): `FakeKeycloak` (mit `client_mappings`, `groups`, `fehler_bei`, `token_abgelehnt`, `token_calls()`), Fixture `kc` (Service-Account gesetzt, Token-Cache leer), Konstanten `MANDANT`, `FREMD`, `REALM`, `ADMIN_ID`, `APP_ROLLEN`, `STANDARDROLLE`, `TOKEN_PFAD`. Die Attrappe kann bereits alles, was Tasks 2–7 brauchen; sie wird später nicht mehr geändert.

- [ ] **Step 1: Testdatei mit Keycloak-Attrappe und Dienst-Tests anlegen**

`backend/tests/test_benutzerverwaltung.py`:

```python
"""Benutzerverwaltung je Mandant (Paket 4, B8).

Ein Keycloak-Realm für alle Mandanten, getrennt nur über das Benutzerattribut
tenant_slug. Geprüft wird vor allem, dass ein Mandanten-Admin Benutzer anderer
Mandanten weder sieht noch ändern kann. Keycloak ist vollständig durch einen
httpx.MockTransport ersetzt — kein Netzwerk.
"""
import copy
import json
import re
import uuid
from typing import get_args

import httpx
import pytest

from app.api.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.services import keycloak_admin
from app.tenancy import DEFAULT_TENANT_SLUG

# base_url=localhost → tenant_middleware setzt DEFAULT_TENANT_SLUG (tenancy.py:186-188)
MANDANT = DEFAULT_TENANT_SLUG
FREMD = "fremdfirma"
REALM = get_settings().keycloak_realm
ADMIN_ID = "11111111-1111-4111-8111-111111111111"
APP_ROLLEN = ("admin", "production_planner", "sales", "accounting", "production_staff")
STANDARDROLLE = f"default-roles-{REALM.lower()}"
TOKEN_PFAD = "/protocol/openid-connect/token"


class FakeKeycloak:
    """Keycloak-Admin-API im Speicher.

    Die q-Attributsuche liefert absichtlich TEILTREFFER (q=tenant_slug:dev
    trifft auch 'devx'), damit der exakte Python-Filter greifen muss. Ein PUT
    ohne "attributes" löscht die Attribute — der ungünstigste Fall je nach
    Keycloak-Version.
    """

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.mappings: dict[str, set] = {}
        self.client_mappings: dict[str, dict[str, list[str]]] = {}
        self.groups: dict[str, list[str]] = {}
        self.roles = {n: {"id": f"rid-{n}", "name": n, "composite": False}
                      for n in (*APP_ROLLEN, "readonly", "offline_access", "uma_authorization",
                                "realm-admin")}
        self.roles[STANDARDROLLE] = {"id": "rid-default", "name": STANDARDROLLE, "composite": True}
        self.calls: list[tuple] = []
        self.passwords: dict[str, dict] = {}
        self.down = False
        self.fehler_500 = False
        self.fehler_bei: tuple | None = None   # (Methode, Pfad ab /users…) → 500
        self.token_abgelehnt = 0               # so viele Admin-Aufrufe → 401
        self.attribute_verwerfen = False

    def add_user(self, email, tenant, roles=(), enabled=True, uid=None, first="Vor", last="Nach",
                 client_roles=None, groups=()):
        uid = uid or str(uuid.uuid4())
        self.users[uid] = {
            "id": uid, "username": email, "email": email,
            "firstName": first, "lastName": last, "enabled": enabled,
            "emailVerified": True, "createdTimestamp": 1759900000000,
            "attributes": {"tenant_slug": [tenant]} if tenant else {},
            "requiredActions": [],
        }
        self.mappings[uid] = set(roles)
        self.client_mappings[uid] = dict(client_roles or {})
        self.groups[uid] = list(groups)
        return uid

    def schreibende_calls(self, uid=None):
        return [c for c in self.calls if c[0] in ("POST", "PUT", "DELETE")
                and TOKEN_PFAD not in c[1]
                and (uid is None or uid in c[1])]

    def token_calls(self):
        return [c[1] for c in self.calls if c[1].endswith(TOKEN_PFAD)]

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("Verbindung abgelehnt", request=request)
        path = request.url.path
        body = None
        if request.content and request.headers.get("content-type", "").startswith("application/json"):
            body = json.loads(request.content)
        self.calls.append((request.method, path, dict(request.url.params), body))
        if path.endswith(TOKEN_PFAD):
            return httpx.Response(200, json={"access_token": "test-token", "expires_in": 300})
        if self.token_abgelehnt:
            self.token_abgelehnt -= 1
            return httpx.Response(401, json={"error": "HTTP 401 Unauthorized"})
        if self.fehler_500:
            return httpx.Response(500, json={"error": "boom"})
        m = re.fullmatch(r"/admin/realms/([^/]+)(/.*)", path)
        assert m, f"unerwarteter Pfad {path}"
        realm, rest = m.groups()
        assert realm == REALM, f"falscher Realm {realm}"
        meth = request.method
        if self.fehler_bei == (meth, rest):
            return httpx.Response(500, json={"error": "boom"})

        if rest == "/users" and meth == "GET":
            p = request.url.params
            if "q" in p:
                key, val = p["q"].split(":", 1)
                treffer = [u for u in self.users.values()
                           if any(val in v for v in u["attributes"].get(key, []))]
            elif "username" in p:
                treffer = [u for u in self.users.values() if u["username"] == p["username"]]
            else:
                treffer = list(self.users.values())
            first, mx = int(p.get("first", 0)), int(p.get("max", 100))
            return httpx.Response(200, json=copy.deepcopy(treffer[first:first + mx]))
        if rest == "/users" and meth == "POST":
            if any(u["username"] == body["username"] for u in self.users.values()):
                return httpx.Response(409, json={"errorMessage": "User exists with same username"})
            uid = str(uuid.uuid4())
            rep = {k: v for k, v in body.items() if k != "credentials"}
            rep["id"] = uid
            rep["createdTimestamp"] = 1759900000000
            if self.attribute_verwerfen:
                rep["attributes"] = {}
            self.users[uid] = rep
            self.mappings[uid] = {STANDARDROLLE}
            self.client_mappings[uid] = {}
            self.groups[uid] = []
            self.passwords[uid] = body["credentials"][0]
            return httpx.Response(201, headers={"Location": f"{request.url}/{uid}"})
        m = re.fullmatch(r"/roles/([^/]+)", rest)
        if m and meth == "GET":
            r = self.roles.get(m.group(1))
            return httpx.Response(200, json=r) if r else httpx.Response(404, json={"error": "Could not find role"})
        m = re.fullmatch(r"/users/([^/]+)(/.*)?", rest)
        if m:
            uid, sub = m.group(1), m.group(2) or ""
            if uid not in self.users:
                return httpx.Response(404, json={"error": "User not found"})
            if sub == "" and meth == "GET":
                return httpx.Response(200, json=copy.deepcopy(self.users[uid]))
            if sub == "" and meth == "PUT":
                u = self.users[uid]
                for k in ("firstName", "lastName", "enabled", "email"):
                    if k in body:
                        u[k] = body[k]
                u["attributes"] = body.get("attributes") or {}
                return httpx.Response(204)
            if sub == "/role-mappings" and meth == "GET":
                rep = {}
                if self.mappings[uid]:
                    rep["realmMappings"] = [self.roles[n] for n in sorted(self.mappings[uid])]
                if self.client_mappings[uid]:
                    rep["clientMappings"] = {
                        c: {"id": f"cid-{c}", "client": c,
                            "mappings": [{"id": f"crid-{n}", "name": n, "composite": False} for n in namen]}
                        for c, namen in self.client_mappings[uid].items()
                    }
                return httpx.Response(200, json=rep)
            if sub == "/groups" and meth == "GET":
                return httpx.Response(200, json=[{"id": f"gid-{g}", "name": g, "path": f"/{g}"}
                                                 for g in self.groups[uid]])
            if sub == "/role-mappings/realm":
                if meth == "GET":
                    return httpx.Response(200, json=[self.roles[n] for n in sorted(self.mappings[uid])])
                if meth == "POST":
                    self.mappings[uid] |= {r["name"] for r in body}
                    return httpx.Response(204)
                if meth == "DELETE":
                    self.mappings[uid] -= {r["name"] for r in body}
                    return httpx.Response(204)
            if sub == "/logout" and meth == "POST":
                return httpx.Response(204)
            if sub == "/reset-password" and meth == "PUT":
                self.passwords[uid] = body
                return httpx.Response(204)
        raise AssertionError(f"FakeKeycloak kennt {meth} {rest} nicht")


@pytest.fixture
def kc(monkeypatch):
    fake = FakeKeycloak()
    monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak.test")
    monkeypatch.setenv("KEYCLOAK_USERS_CLIENT_ID", "novaerp-users")
    monkeypatch.setenv("KEYCLOAK_USERS_CLIENT_SECRET", "nur-im-test")
    for name in ("KEYCLOAK_ADMIN_USER", "KEYCLOAK_ADMIN_PASSWORD", "KEYCLOAK_USERS_ALLOW_MASTER_ADMIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(keycloak_admin, "_token_cache", {})
    monkeypatch.setattr(
        keycloak_admin, "_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(fake.handler)),
    )
    fake.add_user("chefin@beispielfirma.de", MANDANT, roles={"admin", STANDARDROLLE}, uid=ADMIN_ID,
                  first="Gerda", last="Chefin")
    return fake


class TestDienstLesen:
    """keycloak_admin direkt, ohne API."""

    def test_liste_filtert_exakt(self, kc):
        eigen = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        kc.add_user("x@fremdfirma.de", FREMD, roles={"admin"})
        kc.add_user("y@aehnlich.de", f"{MANDANT}x", roles={"admin"})
        kc.add_user("z@aehnlich.de", f"x{MANDANT}", roles={"admin"})
        kc.add_user("ohne@ohneattribut.de", None, roles={"admin"})
        ids = [b["id"] for b in keycloak_admin.list_tenant_users(MANDANT)]
        assert sorted(ids) == sorted([ADMIN_ID, eigen])
        suche = [c for c in kc.calls if c[0] == "GET" and c[1].endswith("/users")]
        assert suche[0][2]["q"] == f"tenant_slug:{MANDANT}"
        assert kc.schreibende_calls() == []

    def test_rollen_in_rangfolge_ohne_fremde_realmrollen(self, kc):
        uid = kc.add_user("ben@beispielfirma.de", MANDANT,
                          roles={"production_staff", "sales", "offline_access", "readonly"})
        b = keycloak_admin.get_tenant_user(MANDANT, uid)
        assert b["roles"] == ["sales", "production_staff"]
        assert b["role"] == "sales"

    def test_fremder_benutzer_ist_nicht_gefunden(self, kc):
        fremd = kc.add_user("x@fremdfirma.de", FREMD)
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden) as e:
            keycloak_admin.get_tenant_user(MANDANT, fremd)
        assert e.value.fremd is True
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden) as e:
            keycloak_admin.get_tenant_user(MANDANT, str(uuid.uuid4()))
        assert e.value.fremd is False

    def test_slug_kann_die_suche_nicht_erweitern(self, kc):
        with pytest.raises(keycloak_admin.KeycloakAdminError):
            keycloak_admin.list_tenant_users(f"{MANDANT} tenant_slug:{FREMD}")
        assert kc.calls == []

    @pytest.mark.parametrize("uid", ["../roles/admin", f"{ADMIN_ID}/../../roles/admin",
                                     f"{ADMIN_ID}?first=0", "kein-uuid", ""])
    def test_id_ohne_uuid_erreicht_keycloak_nicht(self, kc, uid):
        """httpx löst '..' im Pfad auf: /users/../roles/admin wäre /roles/admin."""
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden):
            keycloak_admin.get_tenant_user(MANDANT, uid)
        assert kc.calls == []

    def test_realm_wie_tokenpruefung(self, kc, monkeypatch):
        """Nicht der KEYCLOAK_REALM-Default 'novaerp' aus _cfg()."""
        monkeypatch.delenv("KEYCLOAK_REALM", raising=False)
        keycloak_admin.list_tenant_users(MANDANT)
        admin_pfade = [c[1] for c in kc.calls if "/admin/realms/" in c[1]]
        assert admin_pfade and all(p.startswith(f"/admin/realms/{REALM}/") for p in admin_pfade)

    def test_service_account_im_zielrealm(self, kc):
        keycloak_admin.list_tenant_users(MANDANT)
        assert kc.token_calls() == [f"/realms/{REALM}{TOKEN_PFAD}"]

    def test_ohne_service_account_geschlossen(self, kc, monkeypatch):
        """T5 Risiko 2: kein stiller Rückfall auf den master-Admin."""
        monkeypatch.delenv("KEYCLOAK_USERS_CLIENT_SECRET")
        monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "test-admin")
        monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "nur-im-test")
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="Service-Account fehlt"):
            keycloak_admin.list_tenant_users(MANDANT)
        assert kc.calls == []

    def test_master_admin_nur_mit_freigabe(self, kc, monkeypatch):
        monkeypatch.delenv("KEYCLOAK_USERS_CLIENT_ID")
        monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "test-admin")
        monkeypatch.setenv("KEYCLOAK_ADMIN_PASSWORD", "nur-im-test")
        monkeypatch.setenv("KEYCLOAK_USERS_ALLOW_MASTER_ADMIN", "1")
        keycloak_admin.list_tenant_users(MANDANT)
        assert kc.token_calls() == [f"/realms/master{TOKEN_PFAD}"]

    def test_token_wird_wiederverwendet(self, kc):
        """Ohne Cache löste jeder Aufruf eine eigene Keycloak-Anmeldung aus."""
        for _ in range(3):
            keycloak_admin.list_tenant_users(MANDANT)
        assert len(kc.token_calls()) == 1

    def test_abgelaufenes_token_wird_einmal_erneuert(self, kc):
        keycloak_admin.list_tenant_users(MANDANT)
        kc.token_abgelehnt = 1
        assert [b["id"] for b in keycloak_admin.list_tenant_users(MANDANT)] == [ADMIN_ID]
        assert len(kc.token_calls()) == 2

    def test_nicht_erreichbar(self, kc):
        kc.down = True
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="nicht erreichbar"):
            keycloak_admin.list_tenant_users(MANDANT)

    def test_serverfehler(self, kc):
        kc.fehler_500 = True
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar):
            keycloak_admin.list_tenant_users(MANDANT)

    def test_nicht_eingerichtet(self, kc, monkeypatch):
        monkeypatch.delenv("KEYCLOAK_URL")
        with pytest.raises(keycloak_admin.KeycloakNichtErreichbar, match="nicht eingerichtet"):
            keycloak_admin.list_tenant_users(MANDANT)
        assert kc.calls == []
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **18 errors** — die Fixture `kc` scheitert mit `AttributeError: <module 'app.services.keycloak_admin' …> has no attribute '_token_cache'`.

- [ ] **Step 3: Modulkopf erweitern**

In `backend/app/services/keycloak_admin.py` diesen Block (Z. 7–20)

```python
Auth gegen Keycloak: master-Realm-Admin via Env
    KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD
Ziel-Realm: KEYCLOAK_REALM (Default: novaerp)
Keycloak-Basis-URL: KEYCLOAK_URL
"""
from __future__ import annotations

import os
import re
import secrets
import string
from typing import Optional

import httpx
```

ersetzen durch

```python
Auth gegen Keycloak: master-Realm-Admin via Env
    KEYCLOAK_ADMIN_USER, KEYCLOAK_ADMIN_PASSWORD
Ziel-Realm: KEYCLOAK_REALM (Default: novaerp)
Keycloak-Basis-URL: KEYCLOAK_URL

Benutzerverwaltung je Mandant (unten, /api/v1/users): Realm = settings.keycloak_realm,
also derselbe Realm wie die Token-Prüfung (core/security.py). Zugang NUR über einen
Service-Account im Ziel-Realm (KEYCLOAK_USERS_CLIENT_ID, KEYCLOAK_USERS_CLIENT_SECRET;
Client-Rollen manage-users, view-users, view-realm). Fehlt er, antwortet die
Benutzerverwaltung mit 503. Den master-Admin nimmt sie nur mit
KEYCLOAK_USERS_ALLOW_MASTER_ADMIN=1 (Entwicklung/Test, nicht Produktion).
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import string
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
```

`app.config` importiert nichts aus `app` (nur `pydantic_settings`), ein Zirkelimport entsteht nicht. `platform.py` importiert dieses Modul ohnehin erst in den Funktionen. Alle bisherigen Zeilen bleiben in derselben Reihenfolge stehen; der Block ergänzt nur (Prüfung in Task 7 Step 4).

- [ ] **Step 4: Abschnitt „Benutzerverwaltung je Mandant" ans Dateiende**

Nach `is_configured()` (letzte Funktion, Z. 228–233) mit zwei Leerzeilen Abstand anhängen:

```python
# ---------------------------------------------------------------------------
# Benutzerverwaltung je Mandant (Paket 4, B8)
#
# Ein Realm für alle Mandanten: getrennt wird NUR über das Attribut
# tenant_slug. Deshalb prüft jede Funktion hier vor jedem Lesen oder
# Schreiben, dass der Zielbenutzer genau diesen tenant_slug trägt. Ein
# Benutzer eines anderen Mandanten ist für den Aufrufer "nicht gefunden".
# ---------------------------------------------------------------------------

#: Rollen, die ein Mandanten-Admin vergeben darf. Reihenfolge = Rangfolge wie
#: ROLLEN_RANGFOLGE in frontend/src/components/common/Layout.tsx.
MANDANTEN_ROLLEN: tuple[str, ...] = (
    "admin", "production_planner", "sales", "accounting", "production_staff",
)

_SEITE = 100
_MAX_SEITEN = 10
_master_warnung_gegeben = False
#: Admin-Token je Zugang, bis kurz vor Ablauf: {(url, realm, konto): (token, gültig_bis)}.
_token_cache: dict[tuple, tuple[str, float]] = {}
_token_lock = threading.Lock()


class KeycloakNichtErreichbar(KeycloakAdminError):
    """Keycloak antwortet nicht oder mit 5xx, oder der Zugang fehlt bzw. wird abgelehnt."""


class KeycloakNichtGefunden(KeycloakAdminError):
    """Benutzer gibt es nicht — oder er gehört zu einem anderen Mandanten."""

    def __init__(self, fremd: bool = False) -> None:
        super().__init__("Benutzer nicht gefunden.")
        self.fremd = fremd


class KeycloakKonflikt(KeycloakAdminError):
    """E-Mail-Adresse ist im Realm schon vergeben."""


class BenutzerSchutzregel(KeycloakAdminError):
    """Änderung würde den eigenen Zugang sperren oder den Mandanten ohne Admin lassen."""


class BenutzerVomSupportVerwaltet(BenutzerSchutzregel):
    """Konto hat Rechte außerhalb der App-Rollen (Client-Rollen, Gruppen, fremde
    oder zusammengesetzte Realm-Rollen). Ein Mandanten-Admin ändert es nicht."""

    def __init__(self) -> None:
        super().__init__("Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden.")


class RolleNichtErlaubt(KeycloakAdminError):
    """Rolle liegt außerhalb von MANDANTEN_ROLLEN."""


def _http_client() -> httpx.Client:
    """Fabrik für den HTTP-Client. Tests hängen hier einen httpx.MockTransport ein."""
    return httpx.Client(verify=True, timeout=15)


def _require_user_id(user_id: str) -> str:
    """Keycloak-IDs sind UUIDs. Alles andere ist "nicht gefunden", bevor es in
    einen URL-Pfad gelangt — httpx löst '..' auf (/users/../roles/admin wäre
    /roles/admin), '?' finge eine Query an."""
    try:
        return str(uuid.UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError):
        raise KeycloakNichtGefunden() from None


def _users_cfg() -> dict:
    """Zugang der Benutzerverwaltung.

    Realm = der Realm, gegen den die App Tokens prüft (settings.keycloak_realm,
    core/security.py:69) — nicht der KEYCLOAK_REALM-Default 'novaerp' aus _cfg().
    Sonst verwaltete ein Mandanten-Admin Benutzer in einem anderen Realm als dem,
    aus dem sein Token stammt.

    Nur ein Service-Account im Ziel-Realm (T5 R5, Risiko 2). Ohne ihn: 503,
    kein stiller Rückfall auf den master-Admin. Den gibt es nur ausdrücklich mit
    KEYCLOAK_USERS_ALLOW_MASTER_ADMIN=1 (Entwicklung/Test).
    """
    url = os.environ.get("KEYCLOAK_URL", "").rstrip("/")
    realm = get_settings().keycloak_realm
    svc_id = os.environ.get("KEYCLOAK_USERS_CLIENT_ID", "").strip()
    svc_secret = os.environ.get("KEYCLOAK_USERS_CLIENT_SECRET", "")
    if not url:
        raise KeycloakNichtErreichbar("Benutzerverwaltung ist nicht eingerichtet (KEYCLOAK_URL fehlt).")
    if svc_id and svc_secret:
        return {"url": url, "realm": realm, "svc_id": svc_id, "svc_secret": svc_secret}
    if os.environ.get("KEYCLOAK_USERS_ALLOW_MASTER_ADMIN", "").strip() == "1":
        admin_user = os.environ.get("KEYCLOAK_ADMIN_USER", "")
        admin_pw = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "")
        if admin_user and admin_pw:
            return {"url": url, "realm": realm, "admin_user": admin_user, "admin_pw": admin_pw}
    raise KeycloakNichtErreichbar(
        "Benutzerverwaltung ist nicht eingerichtet "
        "(Service-Account fehlt: KEYCLOAK_USERS_CLIENT_ID/_SECRET)."
    )


def _neues_token(c: dict, client: httpx.Client) -> tuple[str, float]:
    """Anmeldung bei Keycloak. Rückgabe: (Token, gültig bis — monotone Uhr, 30 s Puffer)."""
    global _master_warnung_gegeben
    if "svc_id" in c:
        url = f"{c['url']}/realms/{c['realm']}/protocol/openid-connect/token"
        daten = {"grant_type": "client_credentials",
                 "client_id": c["svc_id"], "client_secret": c["svc_secret"]}
    else:
        if not _master_warnung_gegeben:
            logger.warning(
                "[keycloak] Benutzerverwaltung nutzt den master-Admin "
                "(KEYCLOAK_USERS_ALLOW_MASTER_ADMIN=1) — nur für Entwicklung/Test."
            )
            _master_warnung_gegeben = True
        url = f"{c['url']}/realms/master/protocol/openid-connect/token"
        daten = {"grant_type": "password", "client_id": "admin-cli",
                 "username": c["admin_user"], "password": c["admin_pw"]}
    try:
        r = client.post(url, data=daten, headers={"Content-Type": "application/x-www-form-urlencoded"})
    except httpx.TransportError as e:
        raise KeycloakNichtErreichbar("Keycloak ist nicht erreichbar.") from e
    if r.status_code != 200:
        raise KeycloakNichtErreichbar(
            f"Anmeldung der Benutzerverwaltung bei Keycloak abgelehnt (HTTP {r.status_code})."
        )
    antwort = r.json()
    laufzeit = float(antwort.get("expires_in") or 60)
    return antwort["access_token"], time.monotonic() + max(0.0, laufzeit - 30)


def _users_token(c: dict, client: httpx.Client, *, erneuern: bool = False) -> str:
    """Token aus dem Prozess-Cache; neu anmelden erst kurz vor Ablauf."""
    schluessel = (c["url"], c["realm"], c.get("svc_id") or f"master:{c.get('admin_user')}")
    with _token_lock:
        if erneuern:
            _token_cache.pop(schluessel, None)
        eintrag = _token_cache.get(schluessel)
        if eintrag and eintrag[1] > time.monotonic():
            return eintrag[0]
    token, gueltig_bis = _neues_token(c, client)
    with _token_lock:
        _token_cache[schluessel] = (token, gueltig_bis)
    return token


class _Benutzerzugang:
    """Eine Keycloak-Sitzung je API-Aufruf: Client, Token, Basis-URL des Realms."""

    def __init__(self) -> None:
        self.c = _users_cfg()
        self.base = f"{self.c['url']}/admin/realms/{self.c['realm']}"
        self.client = _http_client()
        try:
            self.h = {"Authorization": f"Bearer {_users_token(self.c, self.client)}"}
        except Exception:
            self.client.close()
            raise

    def __enter__(self) -> "_Benutzerzugang":
        return self

    def __exit__(self, *exc) -> None:
        self.client.close()

    def _senden(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            return self.client.request(method, f"{self.base}{path}", headers=self.h, **kw)
        except httpx.TransportError as e:
            raise KeycloakNichtErreichbar("Keycloak ist nicht erreichbar.") from e

    def call(self, method: str, path: str, **kw) -> httpx.Response:
        r = self._senden(method, path, **kw)
        if r.status_code == 401:
            # Token aus dem Cache abgelaufen oder widerrufen: einmal neu anmelden.
            self.h = {"Authorization": f"Bearer {_users_token(self.c, self.client, erneuern=True)}"}
            r = self._senden(method, path, **kw)
        if r.status_code >= 500:
            raise KeycloakNichtErreichbar(f"Keycloak meldet einen Serverfehler (HTTP {r.status_code}).")
        return r


def _gehoert_zum_mandanten(rep: dict, tenant_slug: str) -> bool:
    """Genau ein Wert, genau dieser Mandant. Fehlt das Attribut: fremd."""
    return (rep.get("attributes") or {}).get("tenant_slug") == [tenant_slug]


def _lade_mandanten_user(kc: _Benutzerzugang, user_id: str, tenant_slug: str) -> dict:
    user_id = _require_user_id(user_id)
    r = kc.call("GET", f"/users/{user_id}")
    if r.status_code == 404:
        raise KeycloakNichtGefunden()
    if r.status_code != 200:
        raise KeycloakAdminError(f"Benutzer konnte nicht gelesen werden (HTTP {r.status_code}).")
    rep = r.json()
    if not _gehoert_zum_mandanten(rep, tenant_slug):
        raise KeycloakNichtGefunden(fremd=True)
    return rep


def _rollen_mappings(kc: _Benutzerzugang, user_id: str) -> list[dict]:
    r = kc.call("GET", f"/users/{user_id}/role-mappings/realm")
    if r.status_code != 200:
        raise KeycloakAdminError(f"Rollen konnten nicht gelesen werden (HTTP {r.status_code}).")
    return r.json()


def _app_rollen(kc: _Benutzerzugang, user_id: str) -> list[str]:
    """Direkt zugewiesene App-Rollen, in Rangfolge. Andere Realm-Rollen fallen heraus."""
    namen = {m.get("name") for m in _rollen_mappings(kc, user_id)}
    return [r for r in MANDANTEN_ROLLEN if r in namen]


def _als_benutzer(rep: dict, rollen: list[str]) -> dict:
    ts = rep.get("createdTimestamp")
    return {
        "id": rep["id"],
        "email": rep.get("email") or rep.get("username") or "",
        "first_name": rep.get("firstName") or "",
        "last_name": rep.get("lastName") or "",
        "enabled": bool(rep.get("enabled", False)),
        "roles": rollen,
        "role": rollen[0] if rollen else None,
        "created_at": datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None,
    }


def _mandanten_reps(kc: _Benutzerzugang, tenant_slug: str) -> list[dict]:
    """Alle Benutzer des Mandanten: Keycloak-Attributsuche plus exakter Filter in Python.

    Die q-Suche kann je nach Keycloak-Version auch Teiltreffer liefern
    (q=tenant_slug:minga träfe minga-test). Maßgeblich ist der Python-Filter.
    """
    treffer: list[dict] = []
    first = 0
    for _ in range(_MAX_SEITEN):
        r = kc.call("GET", "/users", params={
            "q": f"tenant_slug:{tenant_slug}",
            "exact": "true",
            "briefRepresentation": "false",
            "first": first,
            "max": _SEITE,
        })
        if r.status_code != 200:
            raise KeycloakAdminError(f"Benutzerliste konnte nicht gelesen werden (HTTP {r.status_code}).")
        seite = r.json()
        treffer.extend(seite)
        if len(seite) < _SEITE:
            break
        first += _SEITE
    else:
        raise KeycloakAdminError("Mehr als 1000 Treffer — Benutzerliste wäre unvollständig.")
    return [u for u in treffer if _gehoert_zum_mandanten(u, tenant_slug)]


def list_tenant_users(tenant_slug: str) -> list[dict]:
    tenant_slug = _require_safe_slug(tenant_slug)
    with _Benutzerzugang() as kc:
        benutzer = [_als_benutzer(u, _app_rollen(kc, u["id"])) for u in _mandanten_reps(kc, tenant_slug)]
    return sorted(benutzer, key=lambda b: (b["last_name"].lower(), b["first_name"].lower(), b["email"]))


def get_tenant_user(tenant_slug: str, user_id: str) -> dict:
    tenant_slug = _require_safe_slug(tenant_slug)
    user_id = _require_user_id(user_id)
    with _Benutzerzugang() as kc:
        rep = _lade_mandanten_user(kc, user_id, tenant_slug)
        return _als_benutzer(rep, _app_rollen(kc, user_id))
```

Bestehende Funktionen (`_cfg`, `_admin_token`, `create_tenant_user`, `add_tenant_redirect_uri`, `is_configured`) **nicht** ändern.

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **18 passed**.

- [ ] **Step 6: Nachbarn**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_rollen.py tests/test_demo_reset.py -q -p no:cacheprovider`
Erwartet: alle grün (Modul `keycloak_admin` wird von `platform.py` importiert).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/keycloak_admin.py backend/tests/test_benutzerverwaltung.py
git commit -m "feat(benutzer): Keycloak-Zugriff je Mandant — lesen nur mit passendem tenant_slug"
```

---

### Task 2: Router `/api/v1/users` — Liste und Einzelabruf, nur im eigenen Mandanten

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/api/v1/users.py`
- Modify: `backend/app/main.py:34` (Import), `:807-811` (nach dem `admin.router`-Block)
- Test: `backend/tests/test_benutzerverwaltung.py` (anhängen)

**Interfaces:**
- Consumes: Task 1; `CurrentUser` (`api/deps.py:101`); `get_request_tenant` (`tenancy.py:394-396`); `_deps_admin` (`main.py:137`); `DEFAULT_DEMO_SLUG` (`services/demo_reset_service.py:19`); `DEMO_USERS` (`api/v1/platform.py:229-234`, nur importiert).
- Produces:
  - `app.schemas.user`: `Rolle` (Literal), `BenutzerResponse`, `BenutzerListResponse`, `BenutzerCreate`, `BenutzerUpdate`, `BenutzerAngelegtResponse`, `PasswortZurueckgesetztResponse` (Create/Update/Passwort werden ab Task 3 benutzt; die Datei entsteht hier vollständig)
  - `app.api.v1.users`: `router` (Präfix `/users`), `_mandant` / `Mandant` (403 auch bei Token ohne `sub`), `_audit(aktion, mandant, user, **felder)`, `_fehler(e, mandant, user, ziel_id=None) -> HTTPException`, `_antwort(b, user) -> BenutzerResponse`, Logger `app.audit.benutzer`
  - Routen `GET /api/v1/users`, `GET /api/v1/users/{user_id}`
  - Fehlerabbildung: `KeycloakNichtGefunden` → 404 „Benutzer nicht gefunden." (bei `.fremd` zusätzlich Audit `FREMDZUGRIFF_ABGEWIESEN`), `BenutzerVomSupportVerwaltet` → 409 mit Audit `SUPPORTKONTO_ABGEWIESEN`, `KeycloakKonflikt`/`BenutzerSchutzregel` → 409, `RolleNichtErlaubt` → 400, `KeycloakNichtErreichbar` → 503 „Benutzerverwaltung derzeit nicht verfügbar: …", übrige `KeycloakAdminError` → 502
  - Test-Helfer `_als(rollen, tenant, uid, username, email)`, Fixture `admin`, `_audit_zeilen(caplog)`

- [ ] **Step 1: Tests anhängen**

An `backend/tests/test_benutzerverwaltung.py` anhängen:

```python
def _als(rollen=("admin",), tenant=MANDANT, uid=ADMIN_ID,
         username="chefin@beispielfirma.de", email="chefin@beispielfirma.de"):
    async def override():
        u = {"id": uid, "username": username, "email": email, "roles": list(rollen)}
        if tenant is not None:
            u["tenant_slug"] = tenant
        return u
    app.dependency_overrides[get_current_user] = override


@pytest.fixture
def admin(client, kc):
    vorher = app.dependency_overrides.get(get_current_user)
    _als()
    yield client
    app.dependency_overrides[get_current_user] = vorher


def _audit_zeilen(caplog):
    return [json.loads(r.getMessage().split(" ", 1)[1])
            for r in caplog.records if r.name == "app.audit.benutzer"]


class TestZugriff:
    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin_liest(self, admin, kc, rolle):
        _als(rollen=(rolle,))
        assert admin.get("/api/v1/users").status_code == 403
        assert admin.get(f"/api/v1/users/{ADMIN_ID}").status_code == 403
        assert kc.calls == []

    def test_ohne_mandant_im_token(self, admin, kc):
        """Basic-Auth und AUTH_DISABLED liefern keinen tenant_slug (deps.py:38-57)."""
        _als(tenant=None)
        assert admin.get("/api/v1/users").status_code == 403
        assert kc.calls == []

    def test_ohne_sub_im_token(self, admin, kc):
        """Ohne Benutzer-ID griffe der Selbstschutz ins Leere (acting_user_id 'None')."""
        _als(uid=None)
        assert admin.get("/api/v1/users").status_code == 403
        assert kc.calls == []

    def test_token_anderer_mandant(self, admin, kc):
        _als(tenant=FREMD)
        assert admin.get("/api/v1/users").status_code == 403
        assert kc.calls == []

    def test_kein_loeschen(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.delete(f"/api/v1/users/{uid}").status_code == 405
        assert uid in kc.users


class TestListe:
    def test_nur_eigener_mandant(self, admin, kc):
        eigen = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        kc.add_user("x@fremdfirma.de", FREMD, roles={"admin"})
        kc.add_user("y@aehnlich.de", f"{MANDANT}x", roles={"admin"})
        r = admin.get("/api/v1/users")
        assert r.status_code == 200, r.text
        assert sorted(b["id"] for b in r.json()["items"]) == sorted([ADMIN_ID, eigen])
        assert r.json()["total"] == 2

    def test_felder_und_eigener_eintrag(self, admin, kc):
        kc.add_user("ben@beispielfirma.de", MANDANT, roles={"sales"}, first="Ben", last="Verkauf")
        items = {b["email"]: b for b in admin.get("/api/v1/users").json()["items"]}
        assert items["chefin@beispielfirma.de"]["is_self"] is True
        ben = items["ben@beispielfirma.de"]
        assert ben["is_self"] is False
        assert (ben["first_name"], ben["last_name"], ben["role"], ben["enabled"]) == ("Ben", "Verkauf", "sales", True)
        assert ben["created_at"].startswith("2025-10-08")


class TestFremderMandantLesen:
    def test_fremd_wie_unbekannt(self, admin, kc):
        fremd = kc.add_user("x@fremdfirma.de", FREMD)
        r = admin.get(f"/api/v1/users/{fremd}")
        unbekannt = admin.get(f"/api/v1/users/{uuid.uuid4()}")
        assert r.status_code == unbekannt.status_code == 404
        assert r.json() == unbekannt.json() == {"detail": "Benutzer nicht gefunden."}

    def test_benutzer_ohne_attribut_ist_fremd(self, admin, kc):
        uid = kc.add_user("svc@intern.de", None)
        assert admin.get(f"/api/v1/users/{uid}").status_code == 404
        assert ("GET", f"/admin/realms/{REALM}/users/{uid}") in [c[:2] for c in kc.calls]

    def test_aehnlicher_slug_ist_fremd(self, admin, kc):
        uid = kc.add_user("y@aehnlich.de", f"{MANDANT}x", roles={"admin"})
        assert admin.get(f"/api/v1/users/{uid}").status_code == 404
        assert ("GET", f"/admin/realms/{REALM}/users/{uid}") in [c[:2] for c in kc.calls]

    def test_ungueltige_id(self, admin, kc):
        assert admin.get("/api/v1/users/kein-uuid").status_code == 422
        assert admin.get("/api/v1/users/..%2F..%2Froles").status_code in (404, 422)
        assert kc.calls == []

    def test_fremdzugriff_im_audit(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        fremd = kc.add_user("x@fremdfirma.de", FREMD)
        admin.get(f"/api/v1/users/{fremd}")
        z = _audit_zeilen(caplog)
        assert z[-1]["aktion"] == "FREMDZUGRIFF_ABGEWIESEN"
        assert (z[-1]["ziel_id"], z[-1]["mandant"], z[-1]["von_id"]) == (fremd, MANDANT, ADMIN_ID)


class TestAusfallLesen:
    def test_nicht_erreichbar(self, admin, kc):
        kc.down = True
        r = admin.get("/api/v1/users")
        assert r.status_code == 503
        assert r.json()["detail"] == "Benutzerverwaltung derzeit nicht verfügbar: Keycloak ist nicht erreichbar."

    @pytest.mark.parametrize("variable", ["KEYCLOAK_URL", "KEYCLOAK_USERS_CLIENT_ID"])
    def test_nicht_eingerichtet(self, admin, kc, monkeypatch, variable):
        monkeypatch.delenv(variable)
        r = admin.get("/api/v1/users")
        assert r.status_code == 503
        assert "nicht eingerichtet" in r.json()["detail"]
        assert kc.calls == []


def test_rollenlisten_stimmen_ueberein():
    from app.main import ALLE_ROLLEN
    from app.schemas.user import Rolle
    assert set(get_args(Rolle)) == set(keycloak_admin.MANDANTEN_ROLLEN) == set(ALLE_ROLLEN)
    assert keycloak_admin.MANDANTEN_ROLLEN == APP_ROLLEN
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **18 failed, 19 passed**. Grün sind die 18 Tests aus Task 1 und `TestZugriff::test_kein_loeschen` (die SPA-Fallback-Route `main.py:1029` kennt nur GET und antwortet auf DELETE mit 405). `test_rollenlisten_stimmen_ueberein` scheitert an `ModuleNotFoundError: No module named 'app.schemas.user'`, die übrigen daran, dass `/api/v1/users` noch 404 liefert (erwartet 200, 403, 422 oder 503).

- [ ] **Step 3: Schemas anlegen**

`backend/app/schemas/user.py`:

```python
"""Schemas der Benutzerverwaltung je Mandant (Paket 4, B8).

Der Mandant kommt nie aus dem Body: ``extra="forbid"`` lehnt ein mitgeschicktes
``tenant_slug`` (oder ``attributes``) mit 422 ab.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

#: Muss mit keycloak_admin.MANDANTEN_ROLLEN übereinstimmen (Test prüft das).
Rolle = Literal["admin", "production_planner", "sales", "accounting", "production_staff"]


class BenutzerResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: Optional[Rolle] = Field(None, description="Höchste App-Rolle nach Rangfolge; None = keine")
    roles: list[Rolle] = []
    enabled: bool
    created_at: Optional[datetime] = None
    is_self: bool = False


class BenutzerListResponse(BaseModel):
    items: list[BenutzerResponse]
    total: int


class BenutzerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: Rolle

    @field_validator("email")
    @classmethod
    def _nur_ascii(cls, v: str) -> str:
        if not v.isascii():
            raise ValueError("E-Mail-Adresse bitte ohne Umlaute oder Sonderzeichen.")
        return v.lower()


class BenutzerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[Rolle] = None
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def _mindestens_ein_feld(self):
        if all(v is None for v in (self.first_name, self.last_name, self.role, self.enabled)):
            raise ValueError("Keine Änderung angegeben.")
        return self


class BenutzerAngelegtResponse(BenutzerResponse):
    temporary_password: str = Field(..., description="Einmalpasswort — wird nur jetzt angezeigt")


class PasswortZurueckgesetztResponse(BaseModel):
    user: BenutzerResponse
    temporary_password: str = Field(..., description="Einmalpasswort — wird nur jetzt angezeigt")
```

`app/schemas/__init__.py` **nicht** ändern (der Router importiert direkt aus `app.schemas.user`).

- [ ] **Step 4: Router anlegen**

`backend/app/api/v1/users.py`:

```python
"""Benutzerverwaltung je Mandant (Paket 4, B8).

Nur Rolle ``admin`` (Router-Abhängigkeit ``_deps_admin`` in main.py). Der
Mandant kommt aus dem Host (tenant_middleware) UND aus dem Token-Claim
``tenant_slug``; beide müssen gesetzt und gleich sein. Ein Benutzer eines
anderen Mandanten ist "nicht gefunden" (404), nie "verboten" (403) — sonst
verriete die Antwort, dass es die ID gibt.

Kein Löschen: Benutzer werden deaktiviert (``enabled: false``).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import CurrentUser
from app.api.v1.platform import DEMO_USERS
from app.schemas.user import (
    BenutzerAngelegtResponse, BenutzerCreate, BenutzerListResponse, BenutzerResponse,
    BenutzerUpdate, PasswortZurueckgesetztResponse,
)
from app.services import keycloak_admin as kc
from app.services.demo_reset_service import DEFAULT_DEMO_SLUG
from app.tenancy import get_request_tenant

router = APIRouter(prefix="/users", tags=["Benutzer"])

#: Eigene Logger-Kategorie für den Audit-Trail. WARNING, weil die App kein
#: Logging konfiguriert (uvicorn ohne --log-config): INFO aus app.* verwirft
#: Pythons lastResort-Handler, WARNING landet im Container-Log.
audit_logger = logging.getLogger("app.audit.benutzer")


def _mandant(request: Request, user: CurrentUser) -> str:
    """Mandant des Requests. Basic-Auth- und AUTH_DISABLED-Nutzer haben keinen
    tenant_slug im Token und kommen hier nicht durch; ein Token ohne ``sub``
    (Benutzer-ID) auch nicht — sonst griffe der Selbstschutz ins Leere."""
    host_mandant = get_request_tenant(request)
    token_mandant = user.get("tenant_slug")
    if not user.get("id") or not host_mandant or not token_mandant or host_mandant != token_mandant:
        raise HTTPException(
            status_code=403,
            detail="Benutzerverwaltung nur mit einem Keycloak-Login dieses Mandanten.",
        )
    return host_mandant


Mandant = Annotated[str, Depends(_mandant)]


def _audit(aktion: str, mandant: str, user: dict, **felder) -> None:
    zeile = {
        "aktion": aktion,
        "mandant": mandant,
        "von_id": user.get("id"),
        "von_name": user.get("username"),
        "zeit": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **felder,
    }
    audit_logger.warning(
        "[benutzer-audit] %s", json.dumps(zeile, ensure_ascii=False, sort_keys=True, default=str)
    )


def _fehler(e: kc.KeycloakAdminError, mandant: str, user: dict, ziel_id: str | None = None) -> HTTPException:
    if isinstance(e, kc.KeycloakNichtGefunden):
        if e.fremd:
            _audit("FREMDZUGRIFF_ABGEWIESEN", mandant, user, ziel_id=ziel_id)
        return HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    if isinstance(e, kc.BenutzerVomSupportVerwaltet):
        _audit("SUPPORTKONTO_ABGEWIESEN", mandant, user, ziel_id=ziel_id)
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, (kc.KeycloakKonflikt, kc.BenutzerSchutzregel)):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, kc.RolleNichtErlaubt):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, kc.KeycloakNichtErreichbar):
        return HTTPException(status_code=503, detail=f"Benutzerverwaltung derzeit nicht verfügbar: {e}")
    return HTTPException(status_code=502, detail=f"Keycloak hat die Anfrage abgelehnt: {e}")


def _antwort(b: dict, user: dict) -> BenutzerResponse:
    return BenutzerResponse(**b, is_self=(b["id"] == str(user.get("id"))))


@router.get("", response_model=BenutzerListResponse)
def list_users(mandant: Mandant, user: CurrentUser):
    try:
        benutzer = kc.list_tenant_users(mandant)
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user)
    items = [_antwort(b, user) for b in benutzer]
    return BenutzerListResponse(items=items, total=len(items))


@router.get("/{user_id}", response_model=BenutzerResponse)
def get_user(user_id: UUID, mandant: Mandant, user: CurrentUser):
    try:
        b = kc.get_tenant_user(mandant, str(user_id))
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user, str(user_id))
    return _antwort(b, user)
```

Die Importe `Response`, `BenutzerAngelegtResponse`, `BenutzerCreate`, `BenutzerUpdate`, `PasswortZurueckgesetztResponse`, `DEMO_USERS` und `DEFAULT_DEMO_SLUG` werden erst in Task 3–5 benutzt; sie stehen hier schon, damit spätere Tasks nur anhängen.

- [ ] **Step 5: Router einhängen**

In `backend/app/main.py` nach Z. 34 `from app.api.v1 import seo_dashboard` eine eigene Zeile einfügen (nicht die lange Importzeile Z. 30 erweitern — vermeidet Konflikte mit anderen Paketen):

```python
from app.api.v1 import users as benutzer
```

Direkt nach dem Block

```python
app.include_router(
    admin.router,
    prefix="/api/v1",
    dependencies=_deps_admin,
)
```

(Z. 807–811) einfügen:

```python

# Benutzerverwaltung je Mandant: nur der Mandanten-Admin (Paket 4, B8)
app.include_router(
    benutzer.router,
    prefix="/api/v1",
    dependencies=_deps_admin,
)
```

Der Block muss vor dem Catch-All `@app.get("/{full_path:path}")` (`main.py:1029`) stehen — das ist an dieser Stelle der Fall.

- [ ] **Step 6: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **37 passed**.

- [ ] **Step 7: Nachbarn**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_rollen.py -q -p no:cacheprovider`
Erwartet: alle grün.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/user.py backend/app/api/v1/users.py backend/app/main.py backend/tests/test_benutzerverwaltung.py
git commit -m "feat(benutzer): /api/v1/users — Liste und Einzelabruf nur im eigenen Mandanten"
```

---

### Task 3: Benutzer anlegen — Einmalpasswort, feste Rollenliste, Demo gesperrt

**Files:**
- Modify: `backend/app/services/keycloak_admin.py` (anhängen)
- Modify: `backend/app/api/v1/users.py` (anhängen)
- Test: `backend/tests/test_benutzerverwaltung.py` (anhängen)

**Interfaces:**
- Consumes: Tasks 1, 2.
- Produces:
  - `keycloak_admin._deaktivieren_best_effort(kc, user_id, username) -> bool` (sperrt nur, wenn der Benutzername der ID stimmt), `keycloak_admin._rolle_rep(kc, role) -> dict` (404 → `KeycloakNichtErreichbar` „Rolle '…' fehlt in Keycloak — bitte den Support informieren."; `composite: true` → `KeycloakNichtErreichbar` „… zusammengesetzt …"), `keycloak_admin._neue_user_id(kc, antwort, username) -> str` (Location-Header, sonst genau ein exakter Treffer)
  - `keycloak_admin.create_user_for_tenant(*, tenant_slug, email, first_name, last_name, role) -> dict` (Benutzer-Dict plus `temporary_password`)
  - `users.DEMO_MANDANT` (= `"demo"`), `users.DEMO_LOGINS`, `users._ist_demo_login(user)`, `users._mandant_schreiben`, `users.MandantSchreiben`
  - Route `POST /api/v1/users`; Audit `BENUTZER_ANGELEGT` mit `ziel_id`, `ziel_email`, `rolle`; bei 409 Audit `ANLAGE_ABGELEHNT` mit `ziel_email`
  - Test-Helfer `_neu(admin, **kw)`

- [ ] **Step 1: Tests anhängen**

```python
def _neu(admin, **kw):
    body = {"email": "lena@beispielfirma.de", "first_name": "Lena", "last_name": "Lager",
            "role": "production_staff", **kw}
    return admin.post("/api/v1/users", json=body)


class TestAnlegen:
    def test_mitarbeiter_anlegen(self, admin, kc):
        r = _neu(admin)
        assert r.status_code == 201, r.text
        assert r.headers["cache-control"] == "no-store"
        b = r.json()
        assert (b["role"], b["roles"], b["enabled"]) == ("production_staff", ["production_staff"], True)
        assert len(b["temporary_password"]) >= 16
        assert kc.users[b["id"]]["attributes"] == {"tenant_slug": [MANDANT]}
        assert kc.mappings[b["id"]] == {STANDARDROLLE, "production_staff"}
        assert kc.passwords[b["id"]] == {"type": "password", "value": b["temporary_password"], "temporary": True}

    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin_legt_an(self, admin, kc, rolle):
        _als(rollen=(rolle,))
        assert _neu(admin).status_code == 403
        assert kc.calls == []

    def test_mandant_aus_body_abgelehnt(self, admin, kc):
        assert _neu(admin, tenant_slug=FREMD).status_code == 422
        assert _neu(admin, attributes={"tenant_slug": [FREMD]}).status_code == 422
        assert kc.schreibende_calls() == []

    @pytest.mark.parametrize("rolle", ["realm-admin", "readonly", "offline_access", "ADMIN", ""])
    def test_rolle_ausserhalb_allowlist(self, admin, kc, rolle):
        assert _neu(admin, role=rolle).status_code == 422
        assert kc.schreibende_calls() == []

    def test_rolle_fehlt_im_realm_nichts_angelegt(self, admin, kc):
        del kc.roles["production_staff"]
        r = _neu(admin)
        assert r.status_code == 503, r.text
        assert "production_staff" in r.json()["detail"]
        assert kc.schreibende_calls() == []

    def test_zusammengesetzte_rolle_nicht_vergeben(self, admin, kc):
        """Enthielte eine App-Rolle in Produktion z. B. realm-management-Rollen,
        vergäbe der Mandanten-Admin mehr, als die Allowlist zeigt."""
        kc.roles["sales"]["composite"] = True
        r = _neu(admin, role="sales")
        assert r.status_code == 503, r.text
        assert "zusammengesetzt" in r.json()["detail"]
        assert kc.schreibende_calls() == []

    def test_email_vergeben(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        fremd = kc.add_user("lena@beispielfirma.de", FREMD)
        r = _neu(admin)
        assert r.status_code == 409
        assert r.json()["detail"] == "Diese E-Mail-Adresse ist bereits vergeben."
        assert kc.schreibende_calls(fremd) == []
        assert kc.users[fremd]["attributes"] == {"tenant_slug": [FREMD]}
        z = _audit_zeilen(caplog)
        assert (z[-1]["aktion"], z[-1]["ziel_email"], z[-1]["von_id"]) == (
            "ANLAGE_ABGELEHNT", "lena@beispielfirma.de", ADMIN_ID)

    def test_email_klein_geschrieben(self, admin, kc):
        r = _neu(admin, email="Lena.Lager@Beispielfirma.DE")
        assert r.status_code == 201, r.text
        assert kc.users[r.json()["id"]]["username"] == "lena.lager@beispielfirma.de"

    def test_umlaut_in_email(self, admin, kc):
        assert _neu(admin, email="jürgen@beispielfirma.de").status_code == 422
        assert kc.schreibende_calls() == []

    def test_attribut_nicht_gespeichert_keine_rolle(self, admin, kc):
        kc.attribute_verwerfen = True
        r = _neu(admin)
        assert r.status_code == 502, r.text
        neu = next(u for u in kc.users.values() if u["username"] == "lena@beispielfirma.de")
        assert neu["enabled"] is False
        assert kc.mappings[neu["id"]] == {STANDARDROLLE}

    def test_lesen_nach_anlage_scheitert_deaktiviert(self, admin, kc, monkeypatch):
        """Keycloak legt an und fällt dann aus: der Benutzer bleibt nicht aktiv ohne Rolle."""
        orig = kc.handler
        ausgefallen = []

        def handler(request):
            angelegt = any(c[0] == "POST" and c[1].endswith("/users") for c in kc.calls)
            if (angelegt and not ausgefallen and request.method == "GET"
                    and re.fullmatch(rf"/admin/realms/{REALM}/users/[0-9a-f-]+", request.url.path)):
                ausgefallen.append(request.url.path)
                return httpx.Response(503, json={"error": "kurz weg"})
            return orig(request)

        monkeypatch.setattr(keycloak_admin, "_http_client",
                            lambda: httpx.Client(transport=httpx.MockTransport(handler)))
        r = _neu(admin)
        assert r.status_code == 503, r.text
        neu = next(u for u in kc.users.values() if u["username"] == "lena@beispielfirma.de")
        assert neu["enabled"] is False
        assert kc.mappings[neu["id"]] == {STANDARDROLLE}
        assert "deaktiviert" in r.json()["detail"]

    def test_rueckfall_suche_trifft_keinen_fremden(self, admin, kc, monkeypatch):
        """201 ohne Location-Header und eine username-Suche mit Teiltreffern:
        weder Weiterarbeit noch Deaktivierung darf einen anderen Benutzer treffen."""
        fremd = kc.add_user("xlena@beispielfirma.de", FREMD, roles={"admin"})
        kc.attribute_verwerfen = True
        orig = kc.handler

        def handler(request):
            pfad = request.url.path
            if pfad == f"/admin/realms/{REALM}/users" and request.method == "POST":
                antwort = orig(request)
                return httpx.Response(201) if antwort.status_code == 201 else antwort
            if pfad == f"/admin/realms/{REALM}/users" and "username" in request.url.params:
                kc.calls.append(("GET", pfad, dict(request.url.params), None))
                name = request.url.params["username"]
                treffer = sorted((u for u in kc.users.values() if name in u["username"]),
                                 key=lambda u: u["username"] != "xlena@beispielfirma.de")
                return httpx.Response(200, json=copy.deepcopy(treffer))
            return orig(request)

        monkeypatch.setattr(keycloak_admin, "_http_client",
                            lambda: httpx.Client(transport=httpx.MockTransport(handler)))
        r = _neu(admin)
        assert r.status_code == 502, r.text
        assert kc.schreibende_calls(fremd) == []
        assert kc.users[fremd]["enabled"] is True
        neu = next(u for u in kc.users.values() if u["username"] == "lena@beispielfirma.de")
        assert neu["enabled"] is False

    def test_demo_gesperrt(self, admin, kc, monkeypatch):
        """Demo-Logins sind öffentlich; der Demo-Reset setzt Keycloak nicht zurück."""
        from app.api.v1 import users
        assert users.DEMO_MANDANT == "demo"
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        assert admin.get("/api/v1/users").status_code == 200
        assert _neu(admin).status_code == 403
        assert kc.schreibende_calls() == []

    @pytest.mark.parametrize("username,email", [
        ("anna@demo.novaerp.de", "anna@demo.novaerp.de"),
        ("anna@demo.novaerp.de", "umbenannt@beispielfirma.de"),
        ("ANNA@demo.novaerp.de", None),
    ])
    def test_demo_login_schreibt_in_keinem_mandanten(self, admin, kc, username, email):
        """Öffentlicher Demo-Login (demo1234) mit verstelltem tenant_slug: Mandant
        ist nicht 'demo', die Slug-Sperre griffe nicht — die Login-Sperre schon."""
        _als(username=username, email=email)
        assert _neu(admin, role="admin").status_code == 403
        assert kc.schreibende_calls() == []

    def test_nicht_erreichbar(self, admin, kc):
        kc.down = True
        r = _neu(admin)
        assert r.status_code == 503
        assert "nicht erreichbar" in r.json()["detail"]

    def test_audit_ohne_passwort(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        r = _neu(admin)
        z = _audit_zeilen(caplog)
        assert len(z) == 1
        assert (z[0]["aktion"], z[0]["mandant"], z[0]["von_id"]) == ("BENUTZER_ANGELEGT", MANDANT, ADMIN_ID)
        assert (z[0]["ziel_id"], z[0]["ziel_email"], z[0]["rolle"]) == (r.json()["id"], "lena@beispielfirma.de", "production_staff")
        assert r.json()["temporary_password"] not in caplog.text

    def test_dienst_prueft_rolle_selbst(self, kc):
        with pytest.raises(keycloak_admin.RolleNichtErlaubt):
            keycloak_admin.create_user_for_tenant(tenant_slug=MANDANT, email="a@beispielfirma.de",
                                                  first_name="A", last_name="B", role="realm-admin")
        assert kc.calls == []
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **26 failed, 37 passed** — alle neuen Tests rot (POST antwortet 405, `create_user_for_tenant` fehlt, `users.DEMO_MANDANT` fehlt).

- [ ] **Step 3: Dienst — Anlegen**

An `backend/app/services/keycloak_admin.py` anhängen:

```python
_HALB_ANGELEGT = (
    "Benutzer wurde angelegt, die Rolle aber nicht zugewiesen. Er ist deaktiviert; "
    "bitte über „Bearbeiten“ Rolle setzen und aktivieren."
)
_HALB_ANGELEGT_AKTIV = (
    "Benutzer wurde angelegt, die Rolle aber nicht zugewiesen, und er konnte nicht "
    "deaktiviert werden — bitte den Support informieren."
)


def _deaktivieren_best_effort(kc: _Benutzerzugang, user_id: str, username: str) -> bool:
    """Kein Hard-Delete: ein halb angelegter Benutzer wird gesperrt, nicht gelöscht.

    Nur, wenn die ID wirklich zu dem gerade angelegten Benutzernamen gehört —
    sonst träfe ein Fehler bei der ID-Ermittlung einen fremden Benutzer.
    Rückgabe: True, wenn er jetzt deaktiviert ist."""
    try:
        r = kc.call("GET", f"/users/{_require_user_id(user_id)}")
        if r.status_code == 200 and r.json().get("username") == username:
            p = kc.call("PUT", f"/users/{user_id}", json={**r.json(), "enabled": False})
            if p.status_code in (200, 204):
                return True
    except KeycloakAdminError:
        pass
    logger.error("[keycloak] Benutzer %s konnte nach Fehler nicht deaktiviert werden", user_id)
    return False


def _rolle_rep(kc: _Benutzerzugang, role: str) -> dict:
    r = kc.call("GET", f"/roles/{role}")
    if r.status_code == 404:
        raise KeycloakNichtErreichbar(
            f"Rolle '{role}' fehlt in Keycloak — bitte den Support informieren."
        )
    if r.status_code != 200:
        raise KeycloakAdminError(f"Rolle '{role}' konnte nicht gelesen werden (HTTP {r.status_code}).")
    rolle = r.json()
    if rolle.get("composite"):
        # Eine zusammengesetzte Rolle vergäbe mehr als ihren Namen (z. B. realm-management).
        raise KeycloakNichtErreichbar(
            f"Rolle '{role}' ist in Keycloak zusammengesetzt und wird hier nicht vergeben — "
            "bitte den Support informieren."
        )
    return rolle


def _neue_user_id(kc: _Benutzerzugang, antwort: httpx.Response, username: str) -> str:
    """ID des gerade angelegten Benutzers: aus dem Location-Header, sonst über
    eine Suche, die genau EINEN Treffer mit genau diesem Benutzernamen verlangt."""
    kandidat = antwort.headers.get("Location", "").rstrip("/").rsplit("/", 1)[-1]
    try:
        return _require_user_id(kandidat)
    except KeycloakNichtGefunden:
        pass
    lookup = kc.call("GET", "/users", params={"username": username, "exact": "true"})
    treffer = [u for u in (lookup.json() if lookup.status_code == 200 else [])
               if u.get("username") == username]
    if len(treffer) != 1:
        logger.error("[keycloak] Neu angelegter Benutzer nicht eindeutig wiedergefunden (%d Treffer)", len(treffer))
        raise KeycloakAdminError("Benutzer angelegt, aber nicht eindeutig wiedergefunden — bitte den Support informieren.")
    return _require_user_id(treffer[0]["id"])


def create_user_for_tenant(
    *, tenant_slug: str, email: str, first_name: str, last_name: str, role: str,
) -> dict:
    """Legt einen Benutzer im Mandanten an. Rückgabe enthält das Einmalpasswort.

    Reihenfolge ist Absicht:
      1. Rolle im Realm prüfen — VOR der Anlage (create_tenant_user prüft erst
         danach und hinterlässt bei fehlender Rolle einen Benutzer ohne Rechte).
      2. Anlegen mit tenant_slug-Attribut, Passwort temporär.
      3. Prüfen, dass Keycloak das Attribut gespeichert hat — VOR der Rollenvergabe.
      4. Rolle zuweisen.
    Scheitert 3 oder 4 (auch durch Ausfall), wird der Benutzer deaktiviert, nicht gelöscht.
    """
    tenant_slug = _require_safe_slug(tenant_slug)
    if role not in MANDANTEN_ROLLEN:
        raise RolleNichtErlaubt(f"Rolle '{role}' ist nicht erlaubt.")
    email = email.strip().lower()
    pw = _gen_password()
    with _Benutzerzugang() as kc:
        rolle = _rolle_rep(kc, role)
        r = kc.call("POST", "/users", json={
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": True,
            "requiredActions": [],
            "attributes": {"tenant_slug": [tenant_slug]},
            "credentials": [{"type": "password", "value": pw, "temporary": True}],
        })
        if r.status_code == 409:
            raise KeycloakKonflikt("Diese E-Mail-Adresse ist bereits vergeben.")
        if r.status_code not in (201, 204):
            raise KeycloakAdminError(f"Benutzer-Anlage abgelehnt (HTTP {r.status_code}).")
        user_id = _neue_user_id(kc, r, email)

        try:
            rep = kc.call("GET", f"/users/{user_id}")
            if rep.status_code != 200 or not _gehoert_zum_mandanten(rep.json(), tenant_slug):
                raise KeycloakAdminError(
                    "Keycloak hat das Attribut tenant_slug nicht gespeichert (User-Profile prüfen). "
                    "Der Benutzer wurde deaktiviert und hat keine Rolle."
                )
            z = kc.call("POST", f"/users/{user_id}/role-mappings/realm", json=[rolle])
            if z.status_code >= 400:
                raise KeycloakNichtErreichbar(_HALB_ANGELEGT)
        except KeycloakNichtErreichbar as e:
            gesperrt = _deaktivieren_best_effort(kc, user_id, email)
            raise KeycloakNichtErreichbar(_HALB_ANGELEGT if gesperrt else _HALB_ANGELEGT_AKTIV) from e
        except KeycloakAdminError:
            _deaktivieren_best_effort(kc, user_id, email)
            raise
        benutzer = _als_benutzer(rep.json(), [role])
    return {**benutzer, "temporary_password": pw}
```

- [ ] **Step 4: Router — Demo-Sperre und POST**

An `backend/app/api/v1/users.py` anhängen:

```python
#: Die Demo hat öffentlich bekannte Logins (platform.py: DEMO_USERS, DEMO_PASSWORD).
#: Keycloak-Änderungen setzt der nächtliche Demo-Reset NICHT zurück (er kopiert
#: nur die SQLite-Datei) — ein Besucher könnte sonst Demo-Logins sperren.
DEMO_MANDANT = DEFAULT_DEMO_SLUG
#: Die öffentlichen Demo-Logins schreiben in KEINEM Mandanten — auch nicht, wenn
#: ihr tenant_slug verstellt wurde (B8-Plan, Deploy-Gate D5). Benutzername UND E-Mail,
#: weil sich die E-Mail je nach Realm-Einstellung selbst ändern lässt.
DEMO_LOGINS = frozenset(u["email"].lower() for u in DEMO_USERS)


def _ist_demo_login(user: dict) -> bool:
    return any((user.get(k) or "").strip().lower() in DEMO_LOGINS for k in ("username", "email"))


def _mandant_schreiben(mandant: Mandant, user: CurrentUser) -> str:
    if mandant == DEMO_MANDANT:
        raise HTTPException(status_code=403, detail="In der Demo können Benutzer nicht geändert werden.")
    if _ist_demo_login(user):
        raise HTTPException(status_code=403, detail="Mit einem Demo-Login können Benutzer nicht geändert werden.")
    return mandant


MandantSchreiben = Annotated[str, Depends(_mandant_schreiben)]


@router.post("", response_model=BenutzerAngelegtResponse, status_code=201)
def create_user(body: BenutzerCreate, mandant: MandantSchreiben, user: CurrentUser, response: Response):
    try:
        b = kc.create_user_for_tenant(
            tenant_slug=mandant, email=body.email, first_name=body.first_name,
            last_name=body.last_name, role=body.role,
        )
    except kc.KeycloakAdminError as e:
        if isinstance(e, kc.KeycloakKonflikt):
            # Die 409 verrät, dass die Adresse irgendwo im Realm existiert: festhalten.
            _audit("ANLAGE_ABGELEHNT", mandant, user, ziel_email=body.email, grund="E-Mail vergeben")
        raise _fehler(e, mandant, user)
    _audit("BENUTZER_ANGELEGT", mandant, user, ziel_id=b["id"], ziel_email=b["email"], rolle=body.role)
    response.headers["Cache-Control"] = "no-store"
    pw = b.pop("temporary_password")
    return BenutzerAngelegtResponse(**_antwort(b, user).model_dump(), temporary_password=pw)
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **63 passed**.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/keycloak_admin.py backend/app/api/v1/users.py backend/tests/test_benutzerverwaltung.py
git commit -m "feat(benutzer): Benutzer anlegen mit Einmalpasswort, Rolle nur aus fester Liste"
```

---

### Task 4: Name, Rolle, aktiv ändern — eigener Zugang und letzter Admin geschützt

**Files:**
- Modify: `backend/app/services/keycloak_admin.py` (anhängen)
- Modify: `backend/app/api/v1/users.py` (anhängen)
- Test: `backend/tests/test_benutzerverwaltung.py` (anhängen)

**Interfaces:**
- Consumes: Tasks 1–3 (`_rolle_rep`, `MandantSchreiben`).
- Produces:
  - `keycloak_admin._pruefe_verwaltbar(kc, user_id) -> None` (liest `GET /users/{id}/role-mappings` und `GET /users/{id}/groups`; `BenutzerVomSupportVerwaltet` bei Client-Rollen außer `account`, Gruppen, Realm-Rollen außerhalb `MANDANTEN_ROLLEN` + `offline_access`, `uma_authorization`, `default-roles-<realm>` oder zusammengesetzten Rollen), Konstanten `_STANDARD_REALM_ROLLEN`, `_STANDARD_CLIENT`
  - `keycloak_admin._sitzungen_beenden(kc, user_id) -> None` (`POST /users/{id}/logout`; Fehlschlag auch bei Ausfall nur geloggt)
  - `keycloak_admin._aktive_admins(kc, tenant_slug, ohne) -> int`, `keycloak_admin._setze_rolle(kc, user_id, neu, rollen_alt, erledigt) -> None` (`neu` = Rollen-Darstellung aus `_rolle_rep`; erst alte App-Rollen entfernen, dann neue zuweisen — scheitert Schritt 2, hat der Benutzer weniger Rechte, nicht mehr; `erledigt["roles"]` hält den Zwischenstand)
  - `keycloak_admin.update_tenant_user(*, tenant_slug, user_id, acting_user_id, first_name=None, last_name=None, enabled=None, role=None) -> tuple[dict, dict]` — zweites Element `{feld: [alt, neu]}`, für Rollen `{"roles": [[alt…], [neu]]}`. Reihenfolge: ID, Mandant, Supportkonto, Schutzregeln, Rolle im Realm (`_rolle_rep`) — erst dann schreiben. Scheitert ein Schreibschritt, trägt die Ausnahme `teil_aenderungen`.
  - Schutzregeln (`BenutzerSchutzregel` → 409): eigenes Konto nicht deaktivieren; eigene Admin-Rolle nicht entziehen; aktiven Admin nicht deaktivieren/herabstufen, wenn danach kein anderer aktiver Benutzer des Mandanten mit direkter `admin`-Zuordnung bleibt
  - Nach Deaktivieren oder Rollenwechsel `_sitzungen_beenden`
  - Route `PATCH /api/v1/users/{user_id}`; Audit `BENUTZER_GEAENDERT` mit `aenderungen` (nur wenn sich etwas geändert hat); bei Fehlschlag mit `teil_aenderungen` Audit `BENUTZER_TEILWEISE_GEAENDERT` mit `aenderungen` und `fehler`
  - Test-Helfer `_supportkonto(kc, art)`, Liste `SUPPORTKONTEN`

- [ ] **Step 1: Tests anhängen**

```python
def _supportkonto(kc, art):
    """Konto mit tenant_slug dieses Mandanten, aber mehr Rechten, als die App-Rollen zeigen."""
    if art == "client_rolle":
        return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"admin"},
                           client_roles={"realm-management": ["realm-admin"]})
    if art == "gruppe":
        return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"admin"}, groups=["support"])
    if art == "fremde_realmrolle":
        return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"admin", "realm-admin"})
    kc.roles["sales"]["composite"] = True
    return kc.add_user("betrieb@novaerp.de", MANDANT, roles={"sales"})


SUPPORTKONTEN = ["client_rolle", "gruppe", "fremde_realmrolle", "zusammengesetzt"]


class TestAendern:
    def test_name_aendern_behaelt_mandant(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.patch(f"/api/v1/users/{uid}", json={"first_name": "Helena"})
        assert r.status_code == 200, r.text
        assert r.json()["first_name"] == "Helena"
        assert kc.users[uid]["attributes"] == {"tenant_slug": [MANDANT]}

    def test_rolle_wechseln_genau_eine_approlle(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT,
                          roles={"production_staff", "sales", "offline_access"})
        r = admin.patch(f"/api/v1/users/{uid}", json={"role": "accounting"})
        assert r.status_code == 200, r.text
        assert kc.mappings[uid] == {"accounting", "offline_access"}
        assert r.json()["roles"] == ["accounting"]

    def test_rollenwechsel_beendet_sitzungen(self, admin, kc):
        b = kc.add_user("b@beispielfirma.de", MANDANT, roles={"admin"})
        assert admin.patch(f"/api/v1/users/{b}", json={"role": "sales"}).status_code == 200
        assert ("POST", f"/admin/realms/{REALM}/users/{b}/logout") in [c[:2] for c in kc.calls]

    def test_standardkonto_ist_aenderbar(self, admin, kc):
        """Keycloak-Standardrollen und die Account-Konsole machen kein Supportkonto."""
        uid = kc.add_user("lena@beispielfirma.de", MANDANT,
                          roles={"production_staff", STANDARDROLLE, "offline_access", "uma_authorization"},
                          client_roles={"account": ["manage-account", "view-profile"]})
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": False}).status_code == 200

    def test_deaktivieren_statt_loeschen(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.patch(f"/api/v1/users/{uid}", json={"enabled": False})
        assert r.status_code == 200, r.text
        assert kc.users[uid]["enabled"] is False
        assert ("POST", f"/admin/realms/{REALM}/users/{uid}/logout") in [c[:2] for c in kc.calls]
        assert not [c for c in kc.calls if c[0] == "DELETE" and c[1].endswith(f"/users/{uid}")]

    def test_reaktivieren(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, enabled=False)
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": True}).json()["enabled"] is True

    def test_leerer_patch(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.patch(f"/api/v1/users/{uid}", json={}).status_code == 422

    def test_email_aendern_nicht_vorgesehen(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.patch(f"/api/v1/users/{uid}", json={"email": "neu@beispielfirma.de"}).status_code == 422

    def test_rolle_ausserhalb_allowlist(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.patch(f"/api/v1/users/{uid}", json={"role": "realm-admin"}).status_code == 422
        assert kc.schreibende_calls(uid) == []

    def test_fehlende_rolle_nichts_geschrieben(self, admin, kc):
        """Rolle wird VOR dem ersten Schreiben gelesen — kein halb geänderter Benutzer."""
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, first="Lena")
        del kc.roles["accounting"]
        r = admin.patch(f"/api/v1/users/{uid}",
                        json={"enabled": False, "first_name": "Helena", "role": "accounting"})
        assert r.status_code == 503, r.text
        assert kc.schreibende_calls(uid) == []
        assert kc.users[uid]["enabled"] is True and kc.users[uid]["firstName"] == "Lena"

    def test_teilweise_geaendert_im_audit(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, first="Lena")
        kc.fehler_bei = ("POST", f"/users/{uid}/role-mappings/realm")
        r = admin.patch(f"/api/v1/users/{uid}", json={"first_name": "Helena", "role": "sales"})
        assert r.status_code == 503, r.text
        z = _audit_zeilen(caplog)
        assert (z[-1]["aktion"], z[-1]["ziel_id"]) == ("BENUTZER_TEILWEISE_GEAENDERT", uid)
        assert z[-1]["aenderungen"] == {"first_name": ["Lena", "Helena"], "roles": [["production_staff"], []]}

    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin_aendert(self, admin, kc, rolle):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        _als(rollen=(rolle,))
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": False}).status_code == 403
        assert kc.calls == []

    def test_demo_gesperrt(self, admin, kc, monkeypatch):
        from app.api.v1 import users
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"last_name": "X"}).status_code == 403
        assert kc.schreibende_calls() == []

    def test_nicht_erreichbar(self, admin, kc):
        kc.down = True
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"last_name": "X"}).status_code == 503

    def test_audit_mit_aenderungen(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"}, first="Lena")
        admin.patch(f"/api/v1/users/{uid}", json={"first_name": "Helena", "role": "sales"})
        z = _audit_zeilen(caplog)
        assert z[-1]["aktion"] == "BENUTZER_GEAENDERT" and z[-1]["ziel_id"] == uid
        assert z[-1]["aenderungen"] == {"first_name": ["Lena", "Helena"],
                                        "roles": [["production_staff"], ["sales"]]}

    def test_dienst_prueft_rolle_selbst(self, kc):
        with pytest.raises(keycloak_admin.RolleNichtErlaubt):
            keycloak_admin.update_tenant_user(tenant_slug=MANDANT, user_id=ADMIN_ID,
                                              acting_user_id="x", role="realm-admin")
        assert kc.calls == []


class TestFremderMandantAendern:
    @pytest.mark.parametrize("body", [
        {"enabled": False}, {"role": "admin"}, {"first_name": "Gehackt"},
    ])
    def test_404_und_kein_schreibzugriff(self, admin, kc, body):
        fremd = kc.add_user("x@fremdfirma.de", FREMD, roles={"production_staff"})
        r = admin.patch(f"/api/v1/users/{fremd}", json=body)
        unbekannt = admin.patch(f"/api/v1/users/{uuid.uuid4()}", json=body)
        assert r.status_code == 404, r.text
        assert r.json() == unbekannt.json() == {"detail": "Benutzer nicht gefunden."}
        assert kc.schreibende_calls(fremd) == []
        assert kc.users[fremd]["enabled"] is True and kc.users[fremd]["firstName"] == "Vor"
        assert kc.mappings[fremd] == {"production_staff"}

    def test_benutzer_ohne_attribut(self, admin, kc):
        uid = kc.add_user("svc@intern.de", None)
        assert admin.patch(f"/api/v1/users/{uid}", json={"enabled": False}).status_code == 404
        assert kc.schreibende_calls(uid) == []


class TestSupportkontenAendern:
    @pytest.mark.parametrize("art", SUPPORTKONTEN)
    @pytest.mark.parametrize("body", [{"enabled": False}, {"role": "production_staff"}, {"first_name": "X"}])
    def test_abgewiesen_ohne_schreibzugriff(self, admin, kc, caplog, art, body):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = _supportkonto(kc, art)
        r = admin.patch(f"/api/v1/users/{uid}", json=body)
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden."
        assert kc.schreibende_calls(uid) == []
        assert kc.users[uid]["enabled"] is True and kc.users[uid]["firstName"] == "Vor"
        assert (_audit_zeilen(caplog)[-1]["aktion"], _audit_zeilen(caplog)[-1]["ziel_id"]) == (
            "SUPPORTKONTO_ABGEWIESEN", uid)


class TestSchutzregeln:
    def test_selbst_deaktivieren(self, admin, kc):
        kc.add_user("zweite@beispielfirma.de", MANDANT, roles={"admin"})
        r = admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"enabled": False})
        assert r.status_code == 409
        assert kc.users[ADMIN_ID]["enabled"] is True

    def test_ohne_sub_kein_selbstdeaktivieren(self, admin, kc):
        """Token ohne sub: acting_user_id wäre 'None', der Selbstschutz griffe nicht."""
        kc.add_user("zweite@beispielfirma.de", MANDANT, roles={"admin"})
        _als(uid=None)
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"enabled": False}).status_code == 403
        assert kc.users[ADMIN_ID]["enabled"] is True
        assert kc.schreibende_calls() == []

    def test_selbst_herabstufen(self, admin, kc):
        kc.add_user("zweite@beispielfirma.de", MANDANT, roles={"admin"})
        r = admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"role": "sales"})
        assert r.status_code == 409
        assert kc.mappings[ADMIN_ID] == {"admin", STANDARDROLLE}

    def test_eigenen_namen_aendern_erlaubt(self, admin, kc):
        assert admin.patch(f"/api/v1/users/{ADMIN_ID}", json={"last_name": "Neu"}).status_code == 200

    def test_letzter_aktiver_admin(self, admin, kc):
        """Der Aufrufer hat admin nur im Token (z. B. über eine Gruppe); in
        Keycloak ist B der einzige direkte, aktive Admin des Mandanten."""
        kc.mappings[ADMIN_ID] = set()
        b = kc.add_user("b@beispielfirma.de", MANDANT, roles={"admin"})
        kc.add_user("fremdadmin@fremdfirma.de", FREMD, roles={"admin"})
        kc.add_user("inaktiv@beispielfirma.de", MANDANT, roles={"admin"}, enabled=False)
        assert admin.patch(f"/api/v1/users/{b}", json={"role": "sales"}).status_code == 409
        assert admin.patch(f"/api/v1/users/{b}", json={"enabled": False}).status_code == 409
        assert kc.mappings[b] == {"admin"} and kc.users[b]["enabled"] is True
        kc.add_user("c@beispielfirma.de", MANDANT, roles={"admin"})
        assert admin.patch(f"/api/v1/users/{b}", json={"role": "sales"}).status_code == 200
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **40 failed, 63 passed** — PATCH antwortet 405, `update_tenant_user` fehlt.

- [ ] **Step 3: Dienst — Ändern**

An `backend/app/services/keycloak_admin.py` anhängen:

```python
#: Realm-Rollen, die Keycloak jedem Benutzer gibt; sie machen kein Supportkonto.
#: Dazu kommt die Standardrolle "default-roles-<realm>" (Name aus dem Realm).
_STANDARD_REALM_ROLLEN = ("offline_access", "uma_authorization")
#: Client-Rollen der Account-Konsole betreffen nur das eigene Konto.
_STANDARD_CLIENT = "account"


def _pruefe_verwaltbar(kc: _Benutzerzugang, user_id: str) -> None:
    """Schreiben nur auf gewöhnliche Mandanten-Konten.

    Ein Konto mit passendem tenant_slug kann mehr Rechte haben, als _app_rollen
    zeigt: Client-Rollen (realm-management: realm-admin, manage-users …),
    Gruppen, fremde oder zusammengesetzte Realm-Rollen. Wer so ein Konto per
    Passwort-Reset übernimmt, verwaltet danach den ganzen Realm — alle Mandanten.
    """
    r = kc.call("GET", f"/users/{user_id}/role-mappings")
    if r.status_code != 200:
        raise KeycloakAdminError(f"Rollen konnten nicht gelesen werden (HTTP {r.status_code}).")
    zuordnung = r.json() or {}
    erlaubt = {*MANDANTEN_ROLLEN, *_STANDARD_REALM_ROLLEN}
    standard = f"default-roles-{kc.c['realm'].lower()}"
    for rolle in zuordnung.get("realmMappings") or []:
        if rolle.get("name") == standard:
            continue
        if rolle.get("name") not in erlaubt or rolle.get("composite"):
            raise BenutzerVomSupportVerwaltet()
    for client, eintrag in (zuordnung.get("clientMappings") or {}).items():
        if client != _STANDARD_CLIENT and (eintrag or {}).get("mappings"):
            raise BenutzerVomSupportVerwaltet()
    g = kc.call("GET", f"/users/{user_id}/groups", params={"briefRepresentation": "true"})
    if g.status_code != 200:
        raise KeycloakAdminError(f"Gruppen konnten nicht gelesen werden (HTTP {g.status_code}).")
    if g.json():
        raise BenutzerVomSupportVerwaltet()


def _sitzungen_beenden(kc: _Benutzerzugang, user_id: str) -> None:
    """Refresh-Tokens ungültig machen. Ein schon ausgestelltes Access-Token gilt
    bis zu seinem Ablauf weiter (die App prüft Tokens lokal, security.py:62-82).
    Ein Fehlschlag wird nur geloggt: die eigentliche Änderung ist schon geschehen,
    beim Reset ginge sonst das neue Einmalpasswort verloren."""
    try:
        out = kc.call("POST", f"/users/{user_id}/logout")
        if out.status_code < 400:
            return
        grund = f"HTTP {out.status_code}"
    except KeycloakNichtErreichbar as e:
        grund = str(e)
    logger.warning("[keycloak] Sitzungen von %s nicht beendet (%s)", user_id, grund)


def _aktive_admins(kc: _Benutzerzugang, tenant_slug: str, ohne: str) -> int:
    return sum(
        1
        for u in _mandanten_reps(kc, tenant_slug)
        if u["id"] != ohne and u.get("enabled") and "admin" in _app_rollen(kc, u["id"])
    )


def _setze_rolle(kc: _Benutzerzugang, user_id: str, neu: dict, rollen_alt: list[str],
                 erledigt: dict) -> None:
    """Genau eine App-Rolle. Erst alte entfernen, dann neue zuweisen: scheitert
    der zweite Schritt, hat der Benutzer weniger Rechte, nicht mehr. ``erledigt``
    hält fest, was schon geschrieben ist (für das Audit bei Fehlschlag)."""
    alt = [m for m in _rollen_mappings(kc, user_id)
           if m.get("name") in MANDANTEN_ROLLEN and m.get("name") != neu["name"]]
    if alt:
        r = kc.call("DELETE", f"/users/{user_id}/role-mappings/realm", json=alt)
        if r.status_code >= 400:
            raise KeycloakAdminError(f"Alte Rolle konnte nicht entfernt werden (HTTP {r.status_code}).")
        erledigt["roles"] = [rollen_alt, [n for n in rollen_alt if n == neu["name"]]]
    r = kc.call("POST", f"/users/{user_id}/role-mappings/realm", json=[neu])
    if r.status_code >= 400:
        raise KeycloakAdminError(
            f"Rolle '{neu['name']}' konnte nicht zugewiesen werden (HTTP {r.status_code}); "
            "der Benutzer hat jetzt keine App-Rolle."
        )
    erledigt["roles"] = [rollen_alt, [neu["name"]]]


def update_tenant_user(
    *,
    tenant_slug: str,
    user_id: str,
    acting_user_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    enabled: Optional[bool] = None,
    role: Optional[str] = None,
) -> tuple[dict, dict]:
    """Ändert Name, Aktiv-Status und/oder Rolle. Rückgabe: (Benutzer, Änderungen {feld: [alt, neu]}).

    Alles, was scheitern kann, ohne dass etwas geschrieben ist (Mandant, Supportkonto,
    Schutzregeln, Rolle im Realm), wird VOR dem ersten Schreiben geprüft. Scheitert
    danach ein Schreibschritt, trägt die Ausnahme ``teil_aenderungen``.
    """
    tenant_slug = _require_safe_slug(tenant_slug)
    user_id = _require_user_id(user_id)
    if role is not None and role not in MANDANTEN_ROLLEN:
        raise RolleNichtErlaubt(f"Rolle '{role}' ist nicht erlaubt.")
    with _Benutzerzugang() as kc:
        rep = _lade_mandanten_user(kc, user_id, tenant_slug)
        _pruefe_verwaltbar(kc, user_id)
        rollen_alt = _app_rollen(kc, user_id)

        ist_selbst = user_id == acting_user_id
        if ist_selbst and enabled is False:
            raise BenutzerSchutzregel("Das eigene Konto kann nicht deaktiviert werden.")
        if ist_selbst and role is not None and role != "admin":
            raise BenutzerSchutzregel("Die eigene Admin-Rolle kann nur ein anderer Admin ändern.")
        verliert_admin = "admin" in rollen_alt and (
            (role is not None and role != "admin") or enabled is False
        )
        if verliert_admin and rep.get("enabled") and _aktive_admins(kc, tenant_slug, ohne=user_id) == 0:
            raise BenutzerSchutzregel(
                "Der letzte aktive Admin des Mandanten kann nicht deaktiviert oder herabgestuft werden."
            )
        neue_rolle = _rolle_rep(kc, role) if role is not None and rollen_alt != [role] else None

        put_aenderungen: dict = {}
        neu = dict(rep)
        for feld, kc_feld, wert in (
            ("first_name", "firstName", first_name),
            ("last_name", "lastName", last_name),
            ("enabled", "enabled", enabled),
        ):
            if wert is not None and rep.get(kc_feld) != wert:
                put_aenderungen[feld] = [rep.get(kc_feld), wert]
                neu[kc_feld] = wert

        aenderungen: dict = {}
        try:
            if put_aenderungen:
                # Ganze Darstellung zurückschreiben, Attribute unverändert: je nach
                # Keycloak-Version löscht ein PUT ohne "attributes" sonst tenant_slug.
                neu["attributes"] = rep.get("attributes")
                r = kc.call("PUT", f"/users/{user_id}", json=neu)
                if r.status_code not in (200, 204):
                    raise KeycloakAdminError(f"Änderung abgelehnt (HTTP {r.status_code}).")
                aenderungen.update(put_aenderungen)
            if neue_rolle is not None:
                _setze_rolle(kc, user_id, neue_rolle, rollen_alt, aenderungen)
        except KeycloakAdminError as e:
            e.teil_aenderungen = dict(aenderungen)
            raise
        if "roles" in aenderungen or aenderungen.get("enabled") == [True, False]:
            # Deaktiviert oder Rechte geändert: laufende Sitzungen beenden.
            _sitzungen_beenden(kc, user_id)

        rep_neu = _lade_mandanten_user(kc, user_id, tenant_slug)
        return _als_benutzer(rep_neu, _app_rollen(kc, user_id)), aenderungen
```

- [ ] **Step 4: Router — PATCH**

An `backend/app/api/v1/users.py` anhängen:

```python
@router.patch("/{user_id}", response_model=BenutzerResponse)
def update_user(user_id: UUID, body: BenutzerUpdate, mandant: MandantSchreiben, user: CurrentUser):
    try:
        b, aenderungen = kc.update_tenant_user(
            tenant_slug=mandant, user_id=str(user_id), acting_user_id=str(user.get("id")),
            first_name=body.first_name, last_name=body.last_name,
            enabled=body.enabled, role=body.role,
        )
    except kc.KeycloakAdminError as e:
        teil = getattr(e, "teil_aenderungen", None)
        if teil:
            _audit("BENUTZER_TEILWEISE_GEAENDERT", mandant, user, ziel_id=str(user_id),
                   aenderungen=teil, fehler=str(e))
        raise _fehler(e, mandant, user, str(user_id))
    if aenderungen:
        _audit("BENUTZER_GEAENDERT", mandant, user, ziel_id=b["id"], ziel_email=b["email"],
               aenderungen=aenderungen)
    return _antwort(b, user)
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **103 passed**.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/keycloak_admin.py backend/app/api/v1/users.py backend/tests/test_benutzerverwaltung.py
git commit -m "feat(benutzer): Name, Rolle und aktiv ändern — eigener Zugang und letzter Admin geschützt"
```

---

### Task 5: Passwort zurücksetzen

**Files:**
- Modify: `backend/app/services/keycloak_admin.py` (anhängen)
- Modify: `backend/app/api/v1/users.py` (anhängen)
- Test: `backend/tests/test_benutzerverwaltung.py` (anhängen)

**Interfaces:**
- Consumes: Tasks 1–4 (`_pruefe_verwaltbar`, `_sitzungen_beenden`, `_supportkonto`, `SUPPORTKONTEN`).
- Produces: `keycloak_admin.reset_tenant_user_password(*, tenant_slug, user_id) -> {"user": dict, "temporary_password": str}` (Reihenfolge: ID, Mandant, `_pruefe_verwaltbar`, dann `PUT /users/{id}/reset-password` mit `temporary: true` — Keycloak verlangt beim nächsten Login ein eigenes Passwort —, danach `_sitzungen_beenden`); Route `POST /api/v1/users/{user_id}/reset-password`; Audit `PASSWORT_ZURUECKGESETZT`.

- [ ] **Step 1: Tests anhängen**

```python
class TestPasswort:
    def test_reset_liefert_einmalpasswort(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 200, r.text
        assert r.headers["cache-control"] == "no-store"
        assert r.json()["user"]["id"] == uid
        assert kc.passwords[uid] == {"type": "password", "value": r.json()["temporary_password"], "temporary": True}

    def test_reset_beendet_sitzungen(self, admin, kc):
        """Nach einem kompromittierten Konto bliebe der Angreifer sonst per Refresh-Token drin."""
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        assert admin.post(f"/api/v1/users/{uid}/reset-password").status_code == 200
        schreibend = [c[:2] for c in kc.schreibende_calls(uid)]
        assert schreibend == [("PUT", f"/admin/realms/{REALM}/users/{uid}/reset-password"),
                              ("POST", f"/admin/realms/{REALM}/users/{uid}/logout")]

    def test_logout_scheitert_passwort_trotzdem_geliefert(self, admin, kc):
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        kc.fehler_bei = ("POST", f"/users/{uid}/logout")
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 200, r.text
        assert kc.passwords[uid]["value"] == r.json()["temporary_password"]

    def test_fremd_404_und_kein_schreibzugriff(self, admin, kc):
        fremd = kc.add_user("x@fremdfirma.de", FREMD, roles={"production_staff"})
        r = admin.post(f"/api/v1/users/{fremd}/reset-password")
        unbekannt = admin.post(f"/api/v1/users/{uuid.uuid4()}/reset-password")
        assert r.status_code == 404
        assert r.json() == unbekannt.json()
        assert kc.schreibende_calls(fremd) == [] and fremd not in kc.passwords

    @pytest.mark.parametrize("art", SUPPORTKONTEN)
    def test_supportkonto_nicht_uebernehmbar(self, admin, kc, caplog, art):
        """Angriff: Mandanten-Admin setzt das Passwort eines Betreiberkontos mit
        tenant_slug seines Mandanten zurück und verwaltet danach den ganzen Realm."""
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = _supportkonto(kc, art)
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 409, r.text
        assert "temporary_password" not in r.text
        assert kc.schreibende_calls(uid) == [] and uid not in kc.passwords
        assert _audit_zeilen(caplog)[-1]["aktion"] == "SUPPORTKONTO_ABGEWIESEN"

    @pytest.mark.parametrize("rolle", ["sales", "production_planner", "production_staff", "accounting"])
    def test_nur_admin(self, admin, kc, rolle):
        _als(rollen=(rolle,))
        assert admin.post(f"/api/v1/users/{ADMIN_ID}/reset-password").status_code == 403
        assert kc.calls == []

    def test_demo_gesperrt(self, admin, kc, monkeypatch):
        from app.api.v1 import users
        monkeypatch.setattr(users, "DEMO_MANDANT", MANDANT)
        assert admin.post(f"/api/v1/users/{ADMIN_ID}/reset-password").status_code == 403
        assert kc.schreibende_calls() == []

    def test_audit_ohne_passwort(self, admin, kc, caplog):
        caplog.set_level("WARNING", logger="app.audit.benutzer")
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        pw = admin.post(f"/api/v1/users/{uid}/reset-password").json()["temporary_password"]
        z = _audit_zeilen(caplog)
        assert (z[-1]["aktion"], z[-1]["ziel_id"]) == ("PASSWORT_ZURUECKGESETZT", uid)
        assert pw not in caplog.text

    def test_dienst_prueft_id_selbst(self, kc):
        """T5 R4 will die Dienstfunktionen auch hinter Plattform-Endpunkten nutzen."""
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden):
            keycloak_admin.reset_tenant_user_password(tenant_slug=MANDANT, user_id="../roles/admin")
        with pytest.raises(keycloak_admin.KeycloakNichtGefunden):
            keycloak_admin.update_tenant_user(tenant_slug=MANDANT, user_id="../roles/admin",
                                              acting_user_id=ADMIN_ID, enabled=False)
        assert kc.calls == []
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **15 failed, 103 passed** — POST `…/reset-password` antwortet 405, `reset_tenant_user_password` fehlt.

- [ ] **Step 3: Dienst — Passwort**

An `backend/app/services/keycloak_admin.py` anhängen:

```python
def reset_tenant_user_password(*, tenant_slug: str, user_id: str) -> dict:
    """Setzt ein neues temporäres Passwort (wie beim Onboarding) und beendet die
    Sitzungen. Keycloak verlangt beim nächsten Login ein eigenes Passwort.
    Rückgabe enthält es genau einmal."""
    tenant_slug = _require_safe_slug(tenant_slug)
    user_id = _require_user_id(user_id)
    with _Benutzerzugang() as kc:
        rep = _lade_mandanten_user(kc, user_id, tenant_slug)
        _pruefe_verwaltbar(kc, user_id)
        pw = _gen_password()
        r = kc.call("PUT", f"/users/{user_id}/reset-password",
                    json={"type": "password", "value": pw, "temporary": True})
        if r.status_code not in (200, 204):
            raise KeycloakAdminError(f"Passwort konnte nicht gesetzt werden (HTTP {r.status_code}).")
        _sitzungen_beenden(kc, user_id)
        benutzer = _als_benutzer(rep, _app_rollen(kc, user_id))
    return {"user": benutzer, "temporary_password": pw}
```

- [ ] **Step 4: Router — Reset**

An `backend/app/api/v1/users.py` anhängen:

```python
@router.post("/{user_id}/reset-password", response_model=PasswortZurueckgesetztResponse)
def reset_password(user_id: UUID, mandant: MandantSchreiben, user: CurrentUser, response: Response):
    try:
        r = kc.reset_tenant_user_password(tenant_slug=mandant, user_id=str(user_id))
    except kc.KeycloakAdminError as e:
        raise _fehler(e, mandant, user, str(user_id))
    _audit("PASSWORT_ZURUECKGESETZT", mandant, user, ziel_id=r["user"]["id"], ziel_email=r["user"]["email"])
    response.headers["Cache-Control"] = "no-store"
    return PasswortZurueckgesetztResponse(
        user=_antwort(r["user"], user), temporary_password=r["temporary_password"],
    )
```

- [ ] **Step 5: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **118 passed**.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/keycloak_admin.py backend/app/api/v1/users.py backend/tests/test_benutzerverwaltung.py
git commit -m "feat(benutzer): Passwort zurücksetzen mit Einmalpasswort"
```

---

### Task 6: Schreibbremse je Mandant für Anlegen, Ändern und Passwort-Reset

**Files:**
- Modify: `backend/app/api/v1/users.py` (Importblock, neuer Block direkt nach `MandantSchreiben = …`, Signaturen von `create_user`, `update_user`, `reset_password`)
- Test: `backend/tests/test_benutzerverwaltung.py` (anhängen; Fixture `admin` in Step 3)

**Interfaces:**
- Consumes: Tasks 2–5 (`MandantSchreiben`, `_neu`, Fixture `admin`, `FakeKeycloak.schreibende_calls`, `kc.passwords`).
- Produces (in `app.api.v1.users`): `SCHREIBEN_JE_MINUTE = 30`, `_schreibzeiten` (`defaultdict[str, deque]`), `_schreib_sperre`, `_schreibbremse(mandant) -> str` (429 „Zu viele Änderungen in kurzer Zeit. Bitte in einer Minute erneut versuchen."), `MandantSchreibenGebremst`. Die drei schreibenden Routen hängen an `MandantSchreibenGebremst`; `GET` bleibt ungebremst. Test `TestSchreibbremse::test_schreibbremse_je_mandant`.

**Warum kein `@limiter.limit` aus `main.py`:** Die globale Grenze `Limiter(default_limits=["120/minute"])` (`main.py:62`) wirkt ohne `SlowAPIMiddleware` nicht (eingebunden sind nur `app.state.limiter` und der Exception-Handler, `main.py:298-299`). `users.py` kann `limiter` nicht aus `app.main` importieren, ohne einen Kreisimport (`main.py` importiert die Router). Außerdem antwortet `_rate_limit_exceeded_handler` von slowapi 0.1.9 mit `{"error": "Rate limit exceeded: …"}` statt `detail`; `getErrorMessage` zeigte dann nur den Fallback. Schlüssel ist der Mandant, nicht die IP: Hinter dem Proxy teilten sich sonst womöglich alle Mandanten einen Zähler (**Annahme:** Proxy-Header von Uvicorn bzw. Gunicorn sind im Repo nicht konfiguriert).

**Angriff, den der Test nachstellt:** Ein Mandanten-Admin feuert schreibende Aufrufe in Serie, etwa um fremde E-Mail-Adressen per 409 abzuklopfen oder Keycloak zu fluten. Ab dem 31. schreibenden Aufruf in einer Minute antwortet die API mit 429, ohne Keycloak zu berühren. Lesen bleibt frei, ein anderer Mandant hat einen eigenen Zähler.

- [ ] **Step 1: Test anhängen**

An `backend/tests/test_benutzerverwaltung.py` anhängen:

```python
class TestSchreibbremse:
    """Die globale slowapi-Grenze wirkt nicht (keine SlowAPIMiddleware): ohne eigene
    Bremse könnte ein Mandanten-Admin Keycloak mit Schreibaufrufen fluten und
    fremde E-Mail-Adressen per 409 in Serie abklopfen."""

    def test_schreibbremse_je_mandant(self, admin, kc, monkeypatch):
        from app.api.v1 import users as benutzer_api
        monkeypatch.setattr(benutzer_api, "SCHREIBEN_JE_MINUTE", 3)
        uid = kc.add_user("lena@beispielfirma.de", MANDANT, roles={"production_staff"})
        for _ in range(3):
            assert admin.post(f"/api/v1/users/{uid}/reset-password").status_code == 200
        passwort, schreibend = kc.passwords[uid], len(kc.schreibende_calls())
        r = admin.post(f"/api/v1/users/{uid}/reset-password")
        assert r.status_code == 429
        assert r.json()["detail"] == "Zu viele Änderungen in kurzer Zeit. Bitte in einer Minute erneut versuchen."
        assert _neu(admin, email="neu@beispielfirma.de").status_code == 429
        assert admin.patch(f"/api/v1/users/{uid}", json={"first_name": "X"}).status_code == 429
        assert (kc.passwords[uid], len(kc.schreibende_calls())) == (passwort, schreibend)
        assert admin.get("/api/v1/users").status_code == 200  # Lesen bleibt frei
        assert benutzer_api._schreibbremse(FREMD) == FREMD  # anderer Mandant, eigener Zähler
```

- [ ] **Step 2: Rot bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **1 failed, 118 passed** — `test_schreibbremse_je_mandant` scheitert mit `AttributeError: <module 'app.api.v1.users' …> has no attribute 'SCHREIBEN_JE_MINUTE'`.

- [ ] **Step 3: Router — Schreibbremse**

In `backend/app/api/v1/users.py` ersetzen:

```python
import json
import logging
from datetime import datetime, timezone
```

durch:

```python
import json
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
```

Ersetzen:

```python
MandantSchreiben = Annotated[str, Depends(_mandant_schreiben)]
```

durch:

```python
MandantSchreiben = Annotated[str, Depends(_mandant_schreiben)]

#: Schreibbremse je Mandant für Anlegen, Ändern und Passwort-Reset. Die globale
#: Grenze in main.py (Limiter(default_limits=...)) wirkt nicht, weil keine
#: SlowAPIMiddleware eingebunden ist. Zähler im Prozess, also je Worker — wie
#: slowapi ohne storage_uri. Bremst das Abklopfen fremder E-Mail-Adressen (409)
#: und Lastspitzen gegen Keycloak (jede Anlage und jede Änderung ruft es mehrfach).
SCHREIBEN_JE_MINUTE = 30
_schreibzeiten: defaultdict[str, deque] = defaultdict(deque)
_schreib_sperre = threading.Lock()


def _schreibbremse(mandant: MandantSchreiben) -> str:
    jetzt = time.monotonic()
    with _schreib_sperre:
        zeiten = _schreibzeiten[mandant]
        while zeiten and jetzt - zeiten[0] >= 60:
            zeiten.popleft()
        if len(zeiten) >= SCHREIBEN_JE_MINUTE:
            raise HTTPException(
                status_code=429,
                detail="Zu viele Änderungen in kurzer Zeit. Bitte in einer Minute erneut versuchen.",
            )
        zeiten.append(jetzt)
    return mandant


MandantSchreibenGebremst = Annotated[str, Depends(_schreibbremse)]
```

In den Signaturen von `create_user`, `update_user` und `reset_password` jeweils `mandant: MandantSchreiben` durch `mandant: MandantSchreibenGebremst` ersetzen, sonst nichts:

```python
def create_user(body: BenutzerCreate, mandant: MandantSchreibenGebremst, user: CurrentUser, response: Response):
```

```python
def update_user(user_id: UUID, body: BenutzerUpdate, mandant: MandantSchreibenGebremst, user: CurrentUser):
```

```python
def reset_password(user_id: UUID, mandant: MandantSchreibenGebremst, user: CurrentUser, response: Response):
```

`_schreibbremse` hängt an `MandantSchreiben`. Die Demo-Sperre (403) greift also zuerst, ein gesperrter Aufruf zählt nicht. Der `except`-Block in `create_user` (Audit `ANLAGE_ABGELEHNT`) bleibt unverändert.

In `backend/tests/test_benutzerverwaltung.py`, Fixture `admin`, ersetzen (sonst stoßen die über 30 schreibenden Tests dieser Datei an die Bremse):

```python
def admin(client, kc):
    vorher = app.dependency_overrides.get(get_current_user)
```

durch:

```python
def admin(client, kc):
    from app.api.v1 import users as benutzer_api
    benutzer_api._schreibzeiten.clear()  # Schreibbremse je Test frisch
    vorher = app.dependency_overrides.get(get_current_user)
```

- [ ] **Step 4: Grün bestätigen**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **119 passed**.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/users.py backend/tests/test_benutzerverwaltung.py
git commit -m "fix(benutzer): Schreibbremse je Mandant für Anlegen, Ändern und Passwort-Reset"
```

---

### Task 7: Abschluss Backend — Routenwächter, Vollauf, Umfang

**Files:**
- Test: `backend/tests/test_benutzerverwaltung.py` (anhängen)

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces: Wächtertest gegen eine spätere DELETE-Route.

- [ ] **Step 1: Wächtertest anhängen**

```python
def test_routen_vollstaendig_ohne_loeschen():
    pfade = app.openapi()["paths"]
    assert set(pfade["/api/v1/users"]) == {"get", "post"}
    assert set(pfade["/api/v1/users/{user_id}"]) == {"get", "patch"}
    assert set(pfade["/api/v1/users/{user_id}/reset-password"]) == {"post"}
```

- [ ] **Step 2: Datei grün**

Run: `cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -v -p no:cacheprovider`
Erwartet: **120 passed**.

- [ ] **Step 3: Vollauf und Fehlernamen vergleichen**

Run: den Block aus „Prozedur Vollauf" (oben im Plan), unverändert.
Erwartet: `diff` ohne Ausgabe, dann `Fehlernamen wie Baseline`. Im Prototyp lautete die Schlusszeile `15 failed, 627 passed, 2 skipped, 1 error`.

- [ ] **Step 4: Umfang prüfen**

Run: `git diff --stat efcea00..HEAD` (startet der Worker auf einem neueren `main`, dessen Commit statt `efcea00`)
Erwartet: genau fünf Dateien — `backend/app/main.py`, `backend/app/services/keycloak_admin.py`, `backend/app/schemas/user.py`, `backend/app/api/v1/users.py`, `backend/tests/test_benutzerverwaltung.py`. Kein Frontend, kein `platform.py`, kein `deps.py`, kein `tenancy.py`, kein `conftest.py`.

Run: `git diff efcea00..HEAD -- backend/app/services/keycloak_admin.py | grep -cE '^-([^-]|$)'`
Erwartet: `0` — in `keycloak_admin.py` wird keine bestehende Zeile entfernt oder geändert, nur ergänzt (im Prototyp gemessen).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_benutzerverwaltung.py
git commit -m "test(benutzer): Routenwächter — Benutzer werden deaktiviert, nicht gelöscht"
```

---

### Task 8: Vertrag am Code prüfen (keine Änderung)

**Files:**
- Read: `backend/app/api/v1/users.py`, `backend/app/schemas/user.py`, `backend/app/main.py`, `backend/app/services/keycloak_admin.py`

**Interfaces:**
- Consumes: Tasks 1–7 und den Abschnitt „Referenz: HTTP-Vertrag". Das Frontend (Task 10 und 12) baut auf genau diesen Pfaden, Feldnamen und Wortlauten auf. Weicht der Code ab, gilt der Code. Dann aber **stoppen und melden**, Task 10 nicht auf eigene Faust umbauen.

- [ ] **Step 1: Backend ist im Arbeitsstand**

Run (aus dem Repo-Wurzelverzeichnis):
```bash
test -f backend/app/api/v1/users.py && test -f backend/app/schemas/user.py && echo Backend-da
```
Erwartet: `Backend-da`. Sonst stoppen: „Backend aus Task 1–7 fehlt".

- [ ] **Step 2: Pfade, Einbindung, Rollen**

Run:
```bash
grep -n 'APIRouter(prefix=' backend/app/api/v1/users.py
grep -n '@router\.' backend/app/api/v1/users.py
grep -n -A3 'benutzer.router\|users.router' backend/app/main.py
grep -n '^Rolle = ' backend/app/schemas/user.py
```
Erwartet:
- `prefix="/users"`.
- Genau diese fünf Dekoratoren: `@router.get("", …)`, `@router.get("/{user_id}", …)`, `@router.post("", …, status_code=201)`, `@router.patch("/{user_id}", …)`, `@router.post("/{user_id}/reset-password", …)`. Kein `@router.delete`.
- Die Einbindung mit `prefix="/api/v1"` und `dependencies=_deps_admin`.
- `Rolle = Literal[…]` mit genau `admin`, `production_planner`, `sales`, `accounting`, `production_staff`.

- [ ] **Step 3: Feldnamen der Schemas**

Run:
```bash
sed -n '/^class BenutzerResponse/,$p' backend/app/schemas/user.py | grep -nE '^class |^    [a-z_]+:'
```
Erwartet, Klasse für Klasse:
- `BenutzerResponse`: `id`, `email`, `first_name`, `last_name`, `role`, `roles`, `enabled`, `created_at`, `is_self`
- `BenutzerListResponse`: `items`, `total`
- `BenutzerCreate`: `email`, `first_name`, `last_name`, `role`
- `BenutzerUpdate`: `first_name`, `last_name`, `role`, `enabled` (**kein** `email`)
- `BenutzerAngelegtResponse(BenutzerResponse)`: `temporary_password`
- `PasswortZurueckgesetztResponse`: `user`, `temporary_password`

- [ ] **Step 4: Demo-Sperre, Wortlaut wie in der Spec (Task 12)**

Run: `grep -n 'In der Demo können Benutzer nicht geändert werden.' backend/app/api/v1/users.py`
Erwartet: genau ein Treffer, in `_mandant_schreiben` (`raise HTTPException(status_code=403, …)`).

- [ ] **Step 5: Service-Account-Pflicht und Schreibbremse**

Run (aus dem Repo-Wurzelverzeichnis):
```bash
grep -n 'Service-Account fehlt' backend/app/services/keycloak_admin.py
grep -n 'MandantSchreibenGebremst\|^SCHREIBEN_JE_MINUTE = ' backend/app/api/v1/users.py
cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -q -p no:cacheprovider -k "ohne_service_account or master_admin_nur_mit_freigabe or schreibbremse"
```
Erwartet:
1. Genau ein Treffer, im Fehlertext von `_users_cfg` (`"(Service-Account fehlt: KEYCLOAK_USERS_CLIENT_ID/_SECRET)."`).
2. Fünf Zeilen: `SCHREIBEN_JE_MINUTE = 30`, `MandantSchreibenGebremst = Annotated[str, Depends(_schreibbremse)]` und die Signaturen von `create_user`, `update_user`, `reset_password` mit `mandant: MandantSchreibenGebremst`.
3. `3 passed, 117 deselected`.

- [ ] **Step 6: Ergebnis festhalten.** Stimmt alles, in der Abschlussmeldung vermerken: „Vertrag geprüft, identisch; Demo-Sperre, Service-Account-Pflicht und Schreibbremse vorhanden". Gibt es eine Abweichung, etwa einen anderen Pfad, `DELETE` statt `enabled`, eine flache statt verschachtelte Antwort, `email` im Update oder einen anderen Wortlaut der Demo-Sperre: stoppen und die Ausgaben von Step 2 bis 5 wörtlich melden. Kein Commit in diesem Task.

---

### Task 9: Rollen mit deutscher Bezeichnung und Beschreibung

**Files:**
- Create: `frontend/src/services/rollen.ts`

**Interfaces:**
- Produces: `type MandantenRolle` (die fünf Realm-Rollen, Kleinschreibung wie im Token), `interface RollenInfo {wert, label, beschreibung, hinweis?, badge}`, `MANDANTEN_ROLLEN: RollenInfo[]`, `rollenInfo(rolle)`. Wird in Task 10 von `api.ts`, `UserCard.tsx` und `Users.tsx` genutzt.

**Herleitung der Texte** (Rechte-Matrix `backend/app/main.py` @ `efcea00`, seit `c4a1832` unverändert, gemessen in T5 1.2). Die Bezeichnungen sind dieselben wie in `Layout.tsx:259-265` (`roleDisplayNames`) und `UserCard.tsx:6-12` (`roleConfig`):

| Rolle (Bezeichnung) | Aussage im Text | Beleg in `main.py` |
|---|---|---|
| `production_staff` (Produktion) | Tagesplan, Aussaat, Ernten | `_deps_produktion` `:108` → `production.router` `:680` |
| | Lagerbuchungen | `_deps_lager` `:114` (`schreiben=[PLANER, PRODUKTION]`) → `inventory.router` `:746`, `procurement.stock_router` `:770` |
| | Bestellungen | `_deps_auftraege` `:122` → `sales.router` `:701` |
| | Auftragsbestätigungen, Lieferscheine | `_deps_belege` `:129` → `documents.router` `:794` |
| | kein Zugriff auf Rechnungen, Preislisten, Auswertungen | `_deps_geld` `:125` → `invoices.router` `:740`, `price_lists_router` `:734`, `analytics.router` `:813` |
| | kein Zugriff auf Einstellungen | `_deps_admin` `:137` → `admin.router` `:807`, `document_templates.router` `:827`, `integrations.router` `:776` |
| `production_planner` (Produktionsplanung) | Kapazitäten, Dienstplan | `_deps_kapazitaet` `:110` → `:752`; `_deps_dienstplan` `:116` → `staff.router` `:687` |
| | Sorten, Lieferanten | `_deps_stammdaten` `:112` (`schreiben=[PLANER]`) → `seeds.router` `:673`, `suppliers.router` `:758` |
| | Produkte, Einkauf | `_deps_vertrieb` `:124` → `products.*` `:716-732`, `procurement.router` `:764` |
| | Prognosen | `_deps_planung` `:127` (`schreiben=[PLANER]`) → `forecasting.router` `:708` |
| | kein Zugriff auf Rechnungen, Preislisten, Auswertungen | `_deps_geld` `:125` ohne `PLANER` |
| `sales` (Vertrieb) | Kunden, Bestellungen, Abos, Belege, Produkte | `:701`, `:794`, `:716-732` |
| | Preislisten, Rechnungen, Auswertungen | `_deps_geld` `:125` |
| | kein Tagesplan, keine Produktion | `_deps_produktion` `:108` ohne `SALES` |
| `accounting` (Buchhaltung) | Rechnungen, Zahlungen, Mahnungen, DATEV-Export | `invoices.router` `:740` (`_deps_geld`); Mahnung und DATEV liegen im Rechnungsrouter (T5 1.2, 1.6) |
| `admin` (Administrator) | alle Bereiche, zusätzlich Einstellungen, Belegvorlagen, Integrationen, Benutzerverwaltung | `_rollen` nimmt `admin` immer in Lesen und Schreiben auf (`:91-104`); `_deps_admin` `:137` |

Der Hinweis „Darf Rechnungen anlegen, finalisieren und versenden" bei `sales` und `accounting` ist Absicht. Gernot will Rechnungen nur beim Admin (Spec, Entscheidung 11). Die Matrix erlaubt sie diesen beiden Rollen aber (T5, Lücke 6). Wer eine dieser Rollen vergibt, soll das sehen.

- [ ] **Step 1: Datei anlegen**

`frontend/src/services/rollen.ts`:

```ts
/**
 * Rollen, die ein Mandanten-Admin in der Benutzerverwaltung vergeben darf.
 *
 * Genau die fünf Realm-Rollen der Rechte-Matrix (backend/app/main.py:
 * Konstanten ADMIN … BUCHHALTUNG, Zuordnung je Router über die _deps_*-Listen).
 * Plattform- und Realm-Rollen gehören nicht hierher; der Server lehnt alles
 * außerhalb dieser Liste ab.
 *
 * Die Beschreibungen fassen die Matrix in Alltagssprache zusammen. Wer die
 * Matrix in main.py ändert, muss diese Texte mitziehen.
 */

export type MandantenRolle =
  | 'admin'
  | 'sales'
  | 'production_planner'
  | 'production_staff'
  | 'accounting';

export interface RollenInfo {
  wert: MandantenRolle;
  label: string;
  beschreibung: string;
  /** Rechte, über die der Admin beim Vergeben stolpern soll. */
  hinweis?: string;
  badge: 'success' | 'info' | 'warning' | 'purple' | 'gray';
}

/** Reihenfolge = Auswahlliste: von wenig zu viel Rechten, Mitarbeiter zuerst. */
export const MANDANTEN_ROLLEN: RollenInfo[] = [
  {
    wert: 'production_staff',
    label: 'Produktion',
    beschreibung:
      'Der Mitarbeiter-Login. Tagesplan, Aussaat, Ernten und Lagerbuchungen; ' +
      'Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen. ' +
      'Kein Zugriff auf Rechnungen, Preislisten, Auswertungen und Einstellungen.',
    badge: 'warning',
  },
  {
    wert: 'production_planner',
    label: 'Produktionsplanung',
    beschreibung:
      'Plant die Produktion: Tagesplan, Aussaat, Ernten, Kapazitäten, Dienstplan, ' +
      'Sorten, Lieferanten, Produkte, Einkauf und Prognosen; dazu Bestellungen, Auftragsbestätigungen und Lieferscheine. ' +
      'Kein Zugriff auf Rechnungen, Preislisten und Auswertungen.',
    badge: 'success',
  },
  {
    wert: 'sales',
    label: 'Vertrieb',
    beschreibung:
      'Kunden, Bestellungen, Abos, Auftragsbestätigungen, Lieferscheine, Produkte, ' +
      'Preislisten und Auswertungen. Kein Zugriff auf Tagesplan und Produktion.',
    hinweis: 'Darf Rechnungen anlegen, finalisieren und versenden.',
    badge: 'info',
  },
  {
    wert: 'accounting',
    label: 'Buchhaltung',
    beschreibung:
      'Rechnungen, Zahlungen, Mahnungen, DATEV-Export, Preislisten und Auswertungen; ' +
      'dazu Kunden, Bestellungen und Belege. Kein Zugriff auf Tagesplan und Produktion.',
    hinweis: 'Darf Rechnungen anlegen, finalisieren und versenden.',
    badge: 'gray',
  },
  {
    wert: 'admin',
    label: 'Administrator',
    beschreibung:
      'Alle Bereiche, zusätzlich Einstellungen, Belegvorlagen, Integrationen und diese Benutzerverwaltung.',
    hinweis: 'Kann selbst Benutzer anlegen, Rollen vergeben und Konten deaktivieren.',
    badge: 'purple',
  },
];

export function rollenInfo(rolle: string | null | undefined): RollenInfo | undefined {
  return MANDANTEN_ROLLEN.find((r) => r.wert === rolle);
}
```

- [ ] **Step 2: Typprüfung**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .`
Erwartet: keine Ausgabe. Die Datei wird noch nicht importiert. Das ist erlaubt, weil `noUnusedLocals` nur innerhalb einer Datei wirkt.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/rollen.ts
git commit -m "feat(benutzer): Rollen mit deutscher Bezeichnung und Beschreibung der Rechte"
```

---

### Task 10: API-Client, Karte und Seite auf die echten Endpunkte umstellen

**Files:**
- Modify: `frontend/src/services/api.ts`, nur der Block zwischen `// ============== Users API (Mock Data) ==============` (heute `:1015`) und `// ==================== GROWTH-TIMELINE-EVENTS ====================` (heute `:1123`)
- Modify (vollständig ersetzen): `frontend/src/components/domain/UserCard.tsx`
- Modify (vollständig ersetzen): `frontend/src/pages/Users.tsx`

**Interfaces:**
- Consumes: Endpunkte aus Task 1–6 laut Vertrag (geprüft in Task 8); `MandantenRolle`, `MANDANTEN_ROLLEN`, `rollenInfo` aus Task 9; `getErrorMessage` (`services/errors.ts:10`); `useUser`, `PageHeader`, `FilterBar` (`components/common/Layout.tsx`); `Alert`, `Button`, `Input`, `Select`, `Modal` (mit `closeOnBackdrop`, `Modal.tsx:6-15`), `ConfirmDialog` (`Modal.tsx:101-111`), `EmptyState`, `useToast` aus `components/ui`.
- Produces: `usersApi.list|create|update|resetPassword`, Typen `MandantenBenutzer`, `BenutzerListe`, `BenutzerAnlegen`, `BenutzerAendern`, `BenutzerAngelegt`, `PasswortZurueckgesetzt` (exportiert aus `services/api.ts`); `anzeigeName(b)` (exportiert aus `UserCard.tsx`).

Die drei Dateien wandern in **einem** Commit: Nach dem Austausch des API-Blocks kompilieren die alte Seite und die alte Karte nicht mehr (`usersApi.delete`, `User` mit `name`).

- [ ] **Step 1: Anker prüfen**

Run: `grep -n "Users API (Mock Data)\|GROWTH-TIMELINE-EVENTS" frontend/src/services/api.ts`
Erwartet: genau zwei Zeilen, zuerst `Users API (Mock Data)`, dann `GROWTH-TIMELINE-EVENTS`. Die Zeilennummern sind egal: Auf `main` @ `efcea00` stehen sie bei `1015:`/`1123:`, nach Paket 1 bei `1017:`/`1125:`, nach Paket 2 bei `1031:`/`1139:` (Stand 08.10. abends), nach beiden noch weiter unten. Andere Anzahl oder andere Reihenfolge: stoppen und melden.

- [ ] **Step 2: Attrappe durch den echten Client ersetzen**

In `frontend/src/services/api.ts` alles **von** der Zeile `// ============== Users API (Mock Data) ==============` **bis vor** die Zeile `// ==================== GROWTH-TIMELINE-EVENTS ====================` löschen. Dazu gehören der Import `import type { User, UserRole } from '../types'`, `MOCK_USERS_KEY`, `defaultMockUsers`, `getMockUsers`, `saveMockUsers` und das alte `usersApi`. Die GROWTH-Zeile bleibt stehen. An die Stelle kommt der folgende Block, gefolgt von genau einer Leerzeile. Der `import type` mitten in der Datei folgt dem bisherigen Muster an dieser Stelle. So bleibt die Änderung ein einziger Hunk, getrennt von der Importzeile, die Paket 2 nach `:14` einfügt.

```ts
// ============== Benutzerverwaltung (Mandant, Keycloak über das Backend) ==============
// Früher stand hier eine Attrappe mit erfundenen Nutzern im localStorage;
// angelegt wurde dort niemand. Den alten Speicher räumt pages/Users.tsx weg.
// Jetzt spricht die Seite mit /api/v1/users (Paket 4, B8). Den Mandanten nimmt
// das Backend immer aus Host und Token, nie aus diesen Daten.
import type { MandantenRolle } from './rollen'

/** backend/app/schemas/user.py: BenutzerResponse */
export interface MandantenBenutzer {
  id: string
  email: string
  first_name: string
  last_name: string
  /** Höchste der fünf Mandanten-Rollen; null = keine, der Benutzer kommt nirgends hin. */
  role: MandantenRolle | null
  roles: MandantenRolle[]
  enabled: boolean
  created_at: string | null
  /** Das eigene Konto des angemeldeten Admins. */
  is_self: boolean
}

/** BenutzerListResponse */
export interface BenutzerListe {
  items: MandantenBenutzer[]
  total: number
}

/** BenutzerCreate. Ein tenant_slug im Body wird vom Server mit 422 abgelehnt. */
export interface BenutzerAnlegen {
  email: string
  first_name: string
  last_name: string
  role: MandantenRolle
}

/** BenutzerUpdate. Die E-Mail ist nicht änderbar. */
export interface BenutzerAendern {
  first_name?: string
  last_name?: string
  role?: MandantenRolle
  enabled?: boolean
}

/** BenutzerAngelegtResponse: das Einmalpasswort kommt genau einmal. */
export interface BenutzerAngelegt extends MandantenBenutzer {
  temporary_password: string
}

/** PasswortZurueckgesetztResponse */
export interface PasswortZurueckgesetzt {
  user: MandantenBenutzer
  temporary_password: string
}

export const usersApi = {
  list: () =>
    api.get<BenutzerListe>('/users').then(r => r.data),

  create: (data: BenutzerAnlegen) =>
    api.post<BenutzerAngelegt>('/users', data).then(r => r.data),

  /** Name, Rolle und Aktiv-Status. Deaktivieren = { enabled: false }; gelöscht wird nie. */
  update: (id: string, data: BenutzerAendern) =>
    api.patch<MandantenBenutzer>(`/users/${id}`, data).then(r => r.data),

  resetPassword: (id: string) =>
    api.post<PasswortZurueckgesetzt>(`/users/${id}/reset-password`).then(r => r.data),
}
```

- [ ] **Step 3: Karte ersetzen**

`frontend/src/components/domain/UserCard.tsx` vollständig ersetzen. Neu sind: alle Rollen als Abzeichen oder „Keine Rolle", „Deaktiviert", „(Sie)", „Angelegt am". Aktionen: Bearbeiten, Passwort zurücksetzen, Deaktivieren (fehlt am eigenen Konto) bzw. Aktivieren. Es gibt kein „Löschen" mehr. Telefon und „Zuletzt aktiv" fallen weg, weil das Backend sie nicht liefert („Offene Punkte für Gernot" 1 und 5).

```tsx
import { Badge } from '../ui';
import { Mail, Edit2, Shield, KeyRound, UserX, UserCheck, CalendarPlus } from 'lucide-react';
import type { MandantenBenutzer } from '../../services/api';
import { rollenInfo } from '../../services/rollen';

/** Vor- und Nachname; fehlen beide, die E-Mail. */
export function anzeigeName(b: MandantenBenutzer): string {
    return [b.first_name, b.last_name].filter(Boolean).join(' ') || b.email;
}

interface UserCardProps {
    user: MandantenBenutzer;
    onEdit: () => void;
    onDeaktivieren: () => void;
    onAktivieren: () => void;
    onPasswort: () => void;
    /** Während eine Änderung läuft, keine zweite auslösen. */
    gesperrt?: boolean;
}

export function UserCard({ user, onEdit, onDeaktivieren, onAktivieren, onPasswort, gesperrt = false }: UserCardProps) {
    const name = anzeigeName(user);
    const initialen =
        [user.first_name, user.last_name]
            .filter(Boolean)
            .map((n) => n[0])
            .join('')
            .toUpperCase() || user.email.slice(0, 1).toUpperCase();

    return (
        <div className={`card card-hover ${user.enabled ? '' : 'opacity-60'}`}>
            <div className="card-body">
                <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-minga-100 dark:bg-minga-900/50 flex items-center justify-center text-minga-700 dark:text-minga-400 font-semibold text-lg flex-shrink-0">
                        {initialen}
                    </div>

                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-gray-900 dark:text-white truncate">{name}</h3>
                            {user.is_self && <span className="text-xs text-gray-500 dark:text-gray-400">(Sie)</span>}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                            {user.roles.length === 0 && <Badge variant="danger">Keine Rolle</Badge>}
                            {user.roles.map((r) => {
                                const info = rollenInfo(r);
                                return (
                                    <Badge key={r} variant={info?.badge ?? 'gray'}>
                                        <Shield className="w-3 h-3 mr-1" />
                                        {info?.label ?? r}
                                    </Badge>
                                );
                            })}
                            {!user.enabled && <Badge variant="gray">Deaktiviert</Badge>}
                        </div>
                    </div>
                </div>

                <div className="mt-4 space-y-2">
                    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <Mail className="w-4 h-4 text-gray-400" />
                        <span className="truncate">{user.email}</span>
                    </div>
                    {user.created_at && (
                        <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                            <CalendarPlus className="w-4 h-4 text-gray-400" />
                            <span>
                                Angelegt am{' '}
                                {new Date(user.created_at).toLocaleDateString('de-DE', {
                                    day: '2-digit',
                                    month: '2-digit',
                                    year: 'numeric',
                                })}
                            </span>
                        </div>
                    )}
                </div>

                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 flex flex-wrap gap-2">
                    <button className="btn btn-ghost btn-sm" onClick={onEdit} disabled={gesperrt}>
                        <Edit2 className="w-4 h-4" />
                        Bearbeiten
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={onPasswort} disabled={gesperrt || !user.enabled}>
                        <KeyRound className="w-4 h-4" />
                        Passwort zurücksetzen
                    </button>
                    {user.enabled ? (
                        // Das eigene Konto nicht anbieten: wer sich selbst sperrt, kommt nicht mehr hinein.
                        // Der Server lehnt es ohnehin mit 409 ab.
                        !user.is_self && (
                            <button
                                className="btn btn-ghost btn-sm text-red-600 dark:text-red-400 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                                onClick={onDeaktivieren}
                                disabled={gesperrt}
                            >
                                <UserX className="w-4 h-4" />
                                Deaktivieren
                            </button>
                        )
                    ) : (
                        <button className="btn btn-ghost btn-sm" onClick={onAktivieren} disabled={gesperrt}>
                            <UserCheck className="w-4 h-4" />
                            Aktivieren
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
```

- [ ] **Step 4: Seite ersetzen**

`frontend/src/pages/Users.tsx` vollständig ersetzen. Aufbau:
- `Users`: prüft `useUser().user.role === 'ADMIN'`. Sonst zeigt die Seite „Kein Zugriff" und fragt nichts ab.
- `Benutzerverwaltung`:
  - räumt `minga-mock-users` aus dem localStorage
  - Liste mit Skelett beim Laden; Fehlerzustand mit dem Wortlaut des Servers und „Erneut versuchen"
  - Kennzahlen, Suche, Rollenfilter
  - Warnung bei aktiven Benutzern ohne Rolle
  - Rückfrage vor dem Deaktivieren und vor dem Passwort-Reset
- `BenutzerFormular`:
  - beim Anlegen: alle vier Felder, Rolle vorbelegt mit `production_staff`
  - beim Bearbeiten: nur geänderte Felder, E-Mail gesperrt
  - mehrere Rollen: keine vorgewählt. Ohne Auswahl bleiben alle; jede gewählte Rolle, auch die höchste, wird geschickt und bleibt als einzige.
  - eigene Rolle nicht wählbar
  - das Formular-Modal schließt nicht über Esc (sonst wären die Eingaben weg)
- `EinmalPasswortDialog`: zeigt das Passwort einmal, mit Kopieren-Knopf; schließt weder über einen Klick daneben noch über Esc. Beim Schließen verwirft die Seite auch das Mutations-Ergebnis (`passwortMutation.reset()`); beide Mutationen mit Passwort in der Antwort haben `gcTime: 0`.

```tsx
import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Search, Users as UsersIcon, UserCheck, UserX, ShieldAlert, Copy } from 'lucide-react';
import { usersApi } from '../services/api';
import type { MandantenBenutzer, BenutzerAendern, BenutzerAngelegt } from '../services/api';
import { MANDANTEN_ROLLEN, rollenInfo } from '../services/rollen';
import type { MandantenRolle } from '../services/rollen';
import { getErrorMessage } from '../services/errors';
import { PageHeader, FilterBar, useUser } from '../components/common/Layout';
import { UserCard, anzeigeName } from '../components/domain/UserCard';
import { StatCard } from '../components/domain/StatCard';
import { SkeletonStatCard, SkeletonCard } from '../components/ui/Skeleton';
import {
    Alert,
    Button,
    Input,
    Select,
    Modal,
    ConfirmDialog,
    EmptyState,
    useToast,
    SelectOption,
} from '../components/ui';

/** Schlüssel der früheren Attrappe. Die Daten darin sind erfunden und werden entfernt. */
const ALTER_ATTRAPPEN_SPEICHER = 'minga-mock-users';

const BENUTZER_KEY = ['mandanten-benutzer'];

const rollenFilterOptionen: SelectOption[] = [
    { value: 'alle', label: 'Alle Rollen' },
    ...MANDANTEN_ROLLEN.map((r) => ({ value: r.wert, label: r.label })),
    { value: 'ohne', label: 'Ohne Rolle' },
];

interface EinmalPasswort {
    anmeldename: string;
    passwort: string;
}

export default function Users() {
    // Gleiche Regel wie der Menüpunkt (Layout.tsx, Abschnitt „Admin", roles: ['ADMIN']).
    // Die Route in App.tsx ist nicht geschützt; ohne diese Prüfung käme jede Rolle
    // per URL auf die Seite. Durchgesetzt wird das Recht im Backend (403).
    const { user } = useUser();
    if (user.role !== 'ADMIN') {
        return (
            <EmptyState
                icon={<ShieldAlert className="w-16 h-16" />}
                title="Kein Zugriff"
                description="Die Benutzerverwaltung ist nur für Administratoren freigegeben."
            />
        );
    }
    return <Benutzerverwaltung />;
}

function Benutzerverwaltung() {
    const toast = useToast();
    const queryClient = useQueryClient();

    const [suche, setSuche] = useState('');
    const [rollenFilter, setRollenFilter] = useState('alle');
    const [anlegen, setAnlegen] = useState(false);
    const [bearbeiten, setBearbeiten] = useState<MandantenBenutzer | null>(null);
    const [zuDeaktivieren, setZuDeaktivieren] = useState<MandantenBenutzer | null>(null);
    const [passwortFuer, setPasswortFuer] = useState<MandantenBenutzer | null>(null);
    const [einmalPasswort, setEinmalPasswort] = useState<EinmalPasswort | null>(null);

    // Die frühere Attrappe hat erfundene Nutzer im Browser abgelegt. Weg damit,
    // damit sie niemand mehr für echte Konten hält.
    useEffect(() => {
        try {
            localStorage.removeItem(ALTER_ATTRAPPEN_SPEICHER);
        } catch {
            /* Speicher gesperrt (privater Modus): nichts zu tun */
        }
    }, []);

    const benutzerQuery = useQuery({
        queryKey: BENUTZER_KEY,
        queryFn: () => usersApi.list(),
        // Ein Rechte- oder Keycloak-Fehler behebt sich nicht durch Wiederholen.
        retry: false,
    });

    const neuLaden = () => queryClient.invalidateQueries({ queryKey: BENUTZER_KEY });

    const statusMutation = useMutation({
        mutationFn: ({ b, aktiv }: { b: MandantenBenutzer; aktiv: boolean }) =>
            usersApi.update(b.id, { enabled: aktiv }),
        onSuccess: (b, { aktiv }) => {
            neuLaden();
            setZuDeaktivieren(null);
            toast.success(
                aktiv
                    ? `${anzeigeName(b)} ist wieder aktiv.`
                    : `${anzeigeName(b)} ist deaktiviert und kann sich nicht mehr anmelden.`,
            );
        },
        onError: (e) => toast.error(getErrorMessage(e, 'Status konnte nicht geändert werden')),
    });

    const passwortMutation = useMutation({
        mutationFn: (b: MandantenBenutzer) => usersApi.resetPassword(b.id),
        // Die Antwort enthält das Einmalpasswort: nicht im MutationCache halten.
        gcTime: 0,
        onSuccess: (r) => {
            setPasswortFuer(null);
            setEinmalPasswort({ anmeldename: r.user.email, passwort: r.temporary_password });
        },
        onError: (e) => toast.error(getErrorMessage(e, 'Passwort konnte nicht zurückgesetzt werden')),
    });

    if (benutzerQuery.isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <div className="flex items-center justify-between">
                    <div className="space-y-2">
                        <div className="skeleton h-7 w-48" />
                        <div className="skeleton h-4 w-32" />
                    </div>
                    <div className="skeleton h-10 w-36 rounded-lg" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <SkeletonStatCard />
                    <SkeletonStatCard />
                    <SkeletonStatCard />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <SkeletonCard />
                    <SkeletonCard />
                    <SkeletonCard />
                </div>
            </div>
        );
    }

    if (benutzerQuery.isError) {
        // Nie still als leere Liste zeigen: Wer „keine Benutzer" sieht, legt sonst
        // Konten doppelt an.
        return (
            <div className="space-y-6">
                <PageHeader title="Benutzerverwaltung" />
                <Alert variant="danger" title="Benutzer konnten nicht geladen werden">
                    {getErrorMessage(benutzerQuery.error, 'Unbekannter Fehler')}
                </Alert>
                <Button variant="secondary" onClick={() => benutzerQuery.refetch()} loading={benutzerQuery.isFetching}>
                    Erneut versuchen
                </Button>
            </div>
        );
    }

    const benutzer = benutzerQuery.data?.items ?? [];
    const s = suche.trim().toLowerCase();
    const gefiltert = benutzer
        .filter((b) =>
            rollenFilter === 'alle'
                ? true
                : rollenFilter === 'ohne'
                  ? b.roles.length === 0
                  : b.roles.includes(rollenFilter as MandantenRolle),
        )
        .filter((b) => !s || anzeigeName(b).toLowerCase().includes(s) || b.email.toLowerCase().includes(s))
        .sort(
            (a, b) =>
                Number(b.enabled) - Number(a.enabled) || anzeigeName(a).localeCompare(anzeigeName(b), 'de'),
        );
    const aktive = benutzer.filter((b) => b.enabled).length;
    const aktivOhneRolle = benutzer.filter((b) => b.enabled && b.roles.length === 0).length;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Benutzerverwaltung"
                subtitle={`${benutzer.length} Benutzer in diesem Betrieb`}
                actions={
                    <Button icon={<Plus className="w-4 h-4" />} onClick={() => setAnlegen(true)}>
                        Neuer Benutzer
                    </Button>
                }
            />

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <StatCard title="Gesamt" value={benutzer.length} icon={<UsersIcon className="w-5 h-5" />} variant="primary" />
                <StatCard title="Aktiv" value={aktive} icon={<UserCheck className="w-5 h-5" />} variant="success" />
                <StatCard
                    title="Deaktiviert"
                    value={benutzer.length - aktive}
                    icon={<UserX className="w-5 h-5" />}
                    variant="warning"
                />
            </div>

            {aktivOhneRolle > 0 && (
                <Alert variant="warning">
                    {aktivOhneRolle === 1
                        ? 'Ein aktiver Benutzer hat keine Rolle und kommt nach der Anmeldung nirgends hin.'
                        : `${aktivOhneRolle} aktive Benutzer haben keine Rolle und kommen nach der Anmeldung nirgends hin.`}{' '}
                    Bitte über „Bearbeiten" eine Rolle zuweisen.
                </Alert>
            )}

            <FilterBar>
                <div className="flex-1 max-w-md">
                    <Input
                        placeholder="Suchen nach Name oder E-Mail..."
                        value={suche}
                        onChange={(e) => setSuche(e.target.value)}
                        startIcon={<Search className="w-4 h-4" />}
                    />
                </div>
                <Select options={rollenFilterOptionen} value={rollenFilter} onChange={(e) => setRollenFilter(e.target.value)} />
            </FilterBar>

            {gefiltert.length === 0 ? (
                <EmptyState
                    title="Keine Benutzer gefunden"
                    description={benutzer.length > 0 ? 'Suche oder Rollenfilter ändern.' : 'Legen Sie den ersten Benutzer an.'}
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {gefiltert.map((b) => (
                        <UserCard
                            key={b.id}
                            user={b}
                            gesperrt={statusMutation.isPending || passwortMutation.isPending}
                            onEdit={() => setBearbeiten(b)}
                            onDeaktivieren={() => setZuDeaktivieren(b)}
                            onAktivieren={() => statusMutation.mutate({ b, aktiv: true })}
                            onPasswort={() => setPasswortFuer(b)}
                        />
                    ))}
                </div>
            )}

            <Modal
                open={anlegen || !!bearbeiten}
                onClose={() => {
                    setAnlegen(false);
                    setBearbeiten(null);
                }}
                title={bearbeiten ? 'Benutzer bearbeiten' : 'Neuer Benutzer'}
                size="lg"
                closeOnBackdrop={false}
                closeOnEscape={false}
            >
                <BenutzerFormular
                    key={bearbeiten?.id ?? 'neu'}
                    benutzer={bearbeiten}
                    onAngelegt={(neu) => {
                        neuLaden();
                        setAnlegen(false);
                        setEinmalPasswort({ anmeldename: neu.email, passwort: neu.temporary_password });
                    }}
                    onGeaendert={(b) => {
                        neuLaden();
                        setBearbeiten(null);
                        toast.success(`${anzeigeName(b)} gespeichert.`);
                    }}
                    onAbbrechen={() => {
                        setAnlegen(false);
                        setBearbeiten(null);
                    }}
                />
            </Modal>

            <ConfirmDialog
                open={!!zuDeaktivieren}
                onClose={() => setZuDeaktivieren(null)}
                onConfirm={() => zuDeaktivieren && statusMutation.mutate({ b: zuDeaktivieren, aktiv: false })}
                title="Benutzer deaktivieren?"
                message={
                    zuDeaktivieren
                        ? `${anzeigeName(zuDeaktivieren)} (${zuDeaktivieren.email}) kann sich danach nicht mehr anmelden. ` +
                          'Das Konto bleibt erhalten und lässt sich jederzeit wieder aktivieren.'
                        : ''
                }
                confirmLabel="Deaktivieren"
                variant="danger"
                loading={statusMutation.isPending}
            />

            <ConfirmDialog
                open={!!passwortFuer}
                onClose={() => setPasswortFuer(null)}
                onConfirm={() => passwortFuer && passwortMutation.mutate(passwortFuer)}
                title="Passwort zurücksetzen?"
                message={
                    passwortFuer
                        ? `Das bisherige Passwort von ${anzeigeName(passwortFuer)} gilt danach nicht mehr. ` +
                          'Sie bekommen ein Einmalpasswort angezeigt; beim nächsten Anmelden muss ein eigenes gesetzt werden.'
                        : ''
                }
                confirmLabel="Zurücksetzen"
                variant="warning"
                loading={passwortMutation.isPending}
            />

            <EinmalPasswortDialog
                daten={einmalPasswort}
                onClose={() => {
                    setEinmalPasswort(null);
                    // Sonst hielte passwortMutation.data das Passwort, solange die Seite offen ist.
                    passwortMutation.reset();
                }}
            />
        </div>
    );
}

interface BenutzerFormularProps {
    /** null = neuen Benutzer anlegen */
    benutzer: MandantenBenutzer | null;
    onAngelegt: (neu: BenutzerAngelegt) => void;
    onGeaendert: (b: MandantenBenutzer) => void;
    onAbbrechen: () => void;
}

function BenutzerFormular({ benutzer, onAngelegt, onGeaendert, onAbbrechen }: BenutzerFormularProps) {
    const toast = useToast();
    const istSelbst = benutzer?.is_self ?? false;
    const [vorname, setVorname] = useState(benutzer?.first_name ?? '');
    const [nachname, setNachname] = useState(benutzer?.last_name ?? '');
    const [email, setEmail] = useState(benutzer?.email ?? '');
    // Mehrere Rollen: nichts vorwählen. Ohne Auswahl bleiben alle; wer eine wählt,
    // auch die höchste, behält nur diese (PATCH role setzt genau eine App-Rolle).
    const mehrereRollen = (benutzer?.roles.length ?? 0) > 1;
    // Neue Konten sind in aller Regel Mitarbeiter-Logins (Entscheidung B8).
    const [rolle, setRolle] = useState<MandantenRolle | null>(
        benutzer ? (mehrereRollen ? null : benutzer.role) : 'production_staff',
    );

    const anlegenMutation = useMutation({
        mutationFn: (r: MandantenRolle) =>
            usersApi.create({
                email: email.trim().toLowerCase(),
                first_name: vorname.trim(),
                last_name: nachname.trim(),
                role: r,
            }),
        // Die Antwort enthält das Einmalpasswort: nicht im MutationCache halten.
        gcTime: 0,
        onSuccess: onAngelegt,
        onError: (e) => toast.error(getErrorMessage(e, 'Benutzer konnte nicht angelegt werden')),
    });

    const aendernMutation = useMutation({
        mutationFn: ({ id, aenderung }: { id: string; aenderung: BenutzerAendern }) => usersApi.update(id, aenderung),
        onSuccess: onGeaendert,
        onError: (e) => toast.error(getErrorMessage(e, 'Änderung konnte nicht gespeichert werden')),
    });

    const laeuft = anlegenMutation.isPending || aendernMutation.isPending;

    const absenden = (e: React.FormEvent) => {
        e.preventDefault();
        if (!rolle && !mehrereRollen) {
            toast.error('Bitte eine Rolle wählen.');
            return;
        }
        if (!benutzer) {
            if (rolle) anlegenMutation.mutate(rolle);
            return;
        }
        // Nur Geändertes schicken: So bleibt beim Umbenennen die Rolle unangetastet,
        // und ein Benutzer mit mehreren Rollen behält sie, solange niemand eine wählt.
        const aenderung: BenutzerAendern = {};
        if (vorname.trim() !== benutzer.first_name) aenderung.first_name = vorname.trim();
        if (nachname.trim() !== benutzer.last_name) aenderung.last_name = nachname.trim();
        if (!istSelbst && rolle && (mehrereRollen || rolle !== benutzer.role)) aenderung.role = rolle;
        if (Object.keys(aenderung).length === 0) {
            toast.info('Keine Änderungen.');
            onAbbrechen();
            return;
        }
        aendernMutation.mutate({ id: benutzer.id, aenderung });
    };

    const weitereRollen = mehrereRollen && benutzer ? benutzer.roles : [];

    return (
        <form onSubmit={absenden} className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label="Vorname" required value={vorname} onChange={(e) => setVorname(e.target.value)} />
                <Input label="Nachname" required value={nachname} onChange={(e) => setNachname(e.target.value)} />
            </div>

            <Input
                label="E-Mail"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={!!benutzer}
                hint={
                    benutzer
                        ? 'Die Anmeldeadresse lässt sich nicht ändern. Für eine neue Adresse einen neuen Benutzer anlegen und den bisherigen deaktivieren.'
                        : 'Mit dieser Adresse meldet sich die Person an. Bitte ohne Umlaute.'
                }
            />

            <fieldset className="space-y-2" disabled={istSelbst}>
                <legend className="label label-required">Rolle</legend>
                {istSelbst && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                        Die eigene Rolle kann nur ein anderer Administrator ändern.
                    </p>
                )}
                {benutzer && benutzer.roles.length === 0 && (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                        Dieser Benutzer hat bisher keine Rolle. Bitte eine wählen.
                    </p>
                )}
                {weitereRollen.length > 0 && !istSelbst && (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                        Hat derzeit mehrere Rollen ({weitereRollen.map((r) => rollenInfo(r)?.label ?? r).join(', ')}).
                        Ohne Auswahl bleiben alle erhalten. Wird eine Rolle gewählt, bleibt nur diese.
                    </p>
                )}
                {MANDANTEN_ROLLEN.map((r) => (
                    <label
                        key={r.wert}
                        className={`flex items-start gap-3 rounded-lg border p-3 ${
                            rolle === r.wert
                                ? 'border-minga-500 bg-minga-50 dark:bg-minga-900/20'
                                : 'border-gray-200 dark:border-gray-700'
                        } ${istSelbst ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                        <input
                            type="radio"
                            name="rolle"
                            className="mt-1"
                            value={r.wert}
                            checked={rolle === r.wert}
                            onChange={() => setRolle(r.wert)}
                            required={!mehrereRollen}
                        />
                        <span>
                            <span className="block text-sm font-medium text-gray-900 dark:text-white">{r.label}</span>
                            <span className="block text-xs text-gray-600 dark:text-gray-400">{r.beschreibung}</span>
                            {r.hinweis && (
                                <span className="block text-xs text-amber-700 dark:text-amber-300 mt-1">{r.hinweis}</span>
                            )}
                        </span>
                    </label>
                ))}
            </fieldset>

            {!benutzer && (
                <p className="text-sm text-gray-600 dark:text-gray-400">
                    Nach dem Anlegen wird einmalig ein Passwort angezeigt. Beim ersten Anmelden setzt die Person ein
                    eigenes.
                </p>
            )}

            <div className="flex gap-3 pt-4 border-t dark:border-gray-700">
                <Button type="button" variant="secondary" onClick={onAbbrechen} disabled={laeuft}>
                    Abbrechen
                </Button>
                <Button type="submit" loading={laeuft} fullWidth>
                    {benutzer ? 'Speichern' : 'Anlegen'}
                </Button>
            </div>
        </form>
    );
}

function EinmalPasswortDialog({ daten, onClose }: { daten: EinmalPasswort | null; onClose: () => void }) {
    const toast = useToast();
    const kopieren = async () => {
        if (!daten) return;
        try {
            await navigator.clipboard.writeText(daten.passwort);
            toast.success('Passwort kopiert.');
        } catch {
            toast.warning('Kopieren nicht möglich. Bitte das Passwort markieren und von Hand kopieren.');
        }
    };

    return (
        <Modal
            open={!!daten}
            onClose={onClose}
            title="Einmalpasswort"
            size="sm"
            // Ein versehentliches Esc oder ein Klick daneben verwürfe das Passwort
            // unwiderruflich. Schließen nur über den Knopf oder das X.
            closeOnBackdrop={false}
            closeOnEscape={false}
            footer={<Button onClick={onClose}>Passwort ist notiert</Button>}
        >
            {daten && (
                <div className="space-y-4">
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                        Anmeldename: <span className="font-medium text-gray-900 dark:text-white">{daten.anmeldename}</span>
                    </p>
                    <div className="flex items-center gap-2">
                        <code
                            data-testid="einmalpasswort"
                            className="flex-1 select-all rounded bg-gray-100 dark:bg-gray-900 px-3 py-2 font-mono text-base"
                        >
                            {daten.passwort}
                        </code>
                        <Button type="button" variant="secondary" icon={<Copy className="w-4 h-4" />} onClick={kopieren}>
                            Kopieren
                        </Button>
                    </div>
                    <Alert variant="warning">
                        Das Passwort wird nur jetzt angezeigt und nirgends gespeichert. Bitte persönlich übergeben, nicht
                        per Chat oder E-Mail. Beim ersten Anmelden muss ein eigenes Passwort gesetzt werden.
                    </Alert>
                </div>
            )}
        </Modal>
    );
}
```

- [ ] **Step 5: Reste der Attrappe und verbotene Muster**

Run (aus dem Repo-Wurzelverzeichnis):
```bash
grep -rn "minga-mock-users" frontend/src
grep -rn "MOCK_USERS\|defaultMockUsers\|getMockUsers\|saveMockUsers" frontend/src
grep -rn "tenant_slug" frontend/src
grep -rn "console\." frontend/src/pages/Users.tsx frontend/src/components/domain/UserCard.tsx frontend/src/services/rollen.ts
grep -rn "usersApi\." frontend/src | grep -v "^frontend/src/services/api.ts"
```
Erwartet:
1. Genau ein Treffer: `frontend/src/pages/Users.tsx` mit `const ALTER_ATTRAPPEN_SPEICHER = 'minga-mock-users';`.
2. Keine Ausgabe.
3. Genau ein Treffer, der Kommentar über `BenutzerAnlegen` in `api.ts`.
4. Keine Ausgabe.
5. Nur `Users.tsx` mit `usersApi.list`, `usersApi.update` (2×), `usersApi.resetPassword`, `usersApi.create`. Kein `delete`, kein `get`.

- [ ] **Step 6: Typprüfung und Build**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
Run: `cd frontend && npm run build` → endet mit `✓ built in …`. Die Warnung „Some chunks are larger than 500 kB" gab es schon vorher.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/services/api.ts frontend/src/components/domain/UserCard.tsx frontend/src/pages/Users.tsx
git commit -m "feat(benutzer): Benutzerverwaltung spricht mit dem Backend statt mit der Attrappe"
```

---

### Task 11: Die Befehlspalette bietet die Benutzerverwaltung nur Administratoren an

**Files:**
- Modify: `frontend/src/components/common/CommandPalette.tsx:34-37` (Props), `:39` (Signatur), `:72` (Eintrag `nav-users`), `:79` (Abhängigkeiten von `useMemo`)
- Modify: `frontend/src/components/common/Layout.tsx:594` (Aufruf)

**Interfaces:**
- Produces: `CommandPalette` erwartet die Pflicht-Prop `istAdmin: boolean`. Einziger Aufrufer ist `Layout.tsx:594` (grep über `frontend/src`).

Warum über eine Prop und nicht über `useUser()` in der Palette: `Layout.tsx` importiert `CommandPalette` (`:37`). Ein Import von `useUser` aus `Layout` in die Palette ergäbe einen Kreisimport.

- [ ] **Step 1: Props und Signatur**

In `CommandPalette.tsx` ersetzen:

```tsx
interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
```

durch:

```tsx
interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  /** Admin-Ziele nur für Administratoren, wie im Menü (Layout.tsx, Abschnitt „Admin"). */
  istAdmin: boolean;
}

export default function CommandPalette({ open, onClose, istAdmin }: CommandPaletteProps) {
```

- [ ] **Step 2: Eintrag nur für Administratoren**

Die Zeile

```tsx
      { id: 'nav-users', label: 'Benutzerverwaltung', section: 'Navigation', icon: UserCog, action: () => go('/users'), keywords: ['benutzer'] },
```

ersetzen durch:

```tsx
      ...(istAdmin
        ? [{ id: 'nav-users', label: 'Benutzerverwaltung', section: 'Navigation', icon: UserCog, action: () => go('/users'), keywords: ['benutzer'] }]
        : []),
```

und die Abhängigkeitsliste von `useMemo` direkt danach von `[go],` auf `[go, istAdmin],` ändern.

`nav-settings` (`:71`) bleibt unverändert, auch wenn er dasselbe Muster hat (Offener Punkt M11).

- [ ] **Step 3: Aufruf in `Layout.tsx`**

`Layout.tsx:594`

```tsx
        <CommandPalette open={showCommandPalette} onClose={() => setShowCommandPalette(false)} />
```

ersetzen durch:

```tsx
        <CommandPalette
          open={showCommandPalette}
          onClose={() => setShowCommandPalette(false)}
          istAdmin={user.role === 'ADMIN'}
        />
```

`user` ist der Wert aus `Layout.tsx:328-334`. Dieselbe Regel gilt für den Menüeintrag (`:249-254`, `:377`).

Prüfen: `grep -n "href: '/users'" frontend/src/components/common/Layout.tsx` liefert genau einen Treffer mit `roles: ['ADMIN']` zwei Zeilen darunter. Fehlt der Eintrag, etwa weil Paket 3 R3 ihn entfernt hat: stoppen und melden.

- [ ] **Step 4: Typprüfung und Build**

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit -p .` → keine Ausgabe.
Run: `cd frontend && npm run build` → `✓ built in …`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/common/CommandPalette.tsx frontend/src/components/common/Layout.tsx
git commit -m "fix(navigation): Befehlspalette bot die Benutzerverwaltung jeder Rolle an"
```

---

### Task 12: Abnahme-Spec mit gemockter API

**Files:**
- Create: `frontend/tests/e2e/benutzerverwaltung.spec.ts`

**Interfaces:**
- Consumes:
  - `page.route` von Playwright (`@playwright/test` ^1.62, `package.json`)
  - der Dev-Nutzer `DEV_USER` aus `frontend/src/context/AuthContext.tsx:24-30`: alle Rollen, Anzeige-Rolle `ADMIN`
  - `API_URL` aus `api.ts:21` (`VITE_API_URL ?? …`)
  - `data-testid="einmalpasswort"` aus `Users.tsx` (Task 10)
- Produces: zehn Abnahmetests. Ohne die Umgebungsvariable `U2_ABNAHME_URL` werden sie übersprungen; ein Lauf gegen die Demo (`smoke-demo`, `full-suite`) bleibt also unberührt.

Die Attrappe in der Spec bildet den Backend-Vertrag aus Task 2–6 nach. Sie lehnt unbekannte Felder wie das Backend (`extra="forbid"`) mit 422 ab und das Deaktivieren des eigenen Kontos mit 409. Mit `{ demo: true }` lehnt sie wie die Demo-Sperre jedes Schreiben mit 403 und demselben Wortlaut ab. Die Tests vergleichen jeden Request-Body exakt (`toEqual`). Damit ist belegt, dass weder `tenant_slug` noch `email` im PATCH mitgeht.

**Nicht abgedeckt:** der Weg für Nicht-Admins („Kein Zugriff" auf `/users`, Palette ohne Eintrag). Der Dev-Nutzer ist fest Administrator (`frontend/src/context/AuthContext.tsx:24-30`), die Spec sieht also nur den Admin-Fall. Geprüft wird das am Code (Review Focus 5) und nach dem Deploy mit ben (Live-Prüfung L4).

Der Worker **schreibt** die Spec und prüft, dass Playwright sie lädt. Laufen lässt sie der Manager (Manager-Abnahme A4), weil sie einen Dev-Server und einen Browser braucht.

- [ ] **Step 1: Datei anlegen**

```ts
/**
 * Abnahme Benutzerverwaltung (Paket 4, B8), ohne Backend und ohne Keycloak.
 *
 * Läuft gegen einen lokalen Vite-Dev-Server mit VITE_AUTH_DISABLED=true. Der
 * Dev-Nutzer aus AuthContext.tsx hat alle Rollen und sieht die Seite deshalb
 * als Administrator. Alle Aufrufe an /api/v1/users beantwortet eine kleine
 * Attrappe im Browser. Sie folgt dem Backend-Vertrag (backend/app/schemas/user.py,
 * backend/app/api/v1/users.py). Andere API-Aufrufe enden mit 404.
 *
 * Lauf (aus frontend/):
 *   VITE_AUTH_DISABLED=true VITE_API_URL=http://localhost:5179 \
 *     ./node_modules/.bin/vite --port 5179 --strictPort &
 *   until curl -sf http://localhost:5179/ >/dev/null; do sleep 1; done
 *   U2_ABNAHME_URL=http://localhost:5179 ./node_modules/.bin/playwright test \
 *     tests/e2e/benutzerverwaltung.spec.ts --retries=0
 *
 * VITE_API_URL zeigt auf den Dev-Server selbst. So bleiben alle Aufrufe auf
 * demselben Origin, und die Attrappe braucht keine CORS-Header.
 */
import { test, expect, Page } from '@playwright/test';

const BASE = process.env.U2_ABNAHME_URL || '';
test.skip(!BASE, 'U2_ABNAHME_URL nicht gesetzt: nur gegen lokalen Dev-Server mit VITE_AUTH_DISABLED=true');

type Rolle = 'admin' | 'sales' | 'production_planner' | 'production_staff' | 'accounting';

interface Benutzer {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: Rolle | null;
  roles: Rolle[];
  enabled: boolean;
  created_at: string | null;
  is_self: boolean;
}

interface Aufruf {
  methode: string;
  pfad: string;
  body: unknown;
}

const ID_ICH = '11111111-1111-4111-8111-111111111111';
const ID_GERNOT = '22222222-2222-4222-8222-222222222222';
const ID_OHNE = '33333333-3333-4333-8333-333333333333';
const ID_NEU = '44444444-4444-4444-8444-444444444444';
const ID_MEHR = '55555555-5555-4555-8555-555555555555';

function startBestand(): Benutzer[] {
  return [
    { id: ID_ICH, email: 'admin@minga-greens.de', first_name: 'Admin', last_name: 'Minga',
      role: 'admin', roles: ['admin'], enabled: true, created_at: '2026-09-02T08:00:00Z', is_self: true },
    { id: ID_GERNOT, email: 'gernot@example.org', first_name: 'Gernot', last_name: 'Kleinberger',
      role: 'admin', roles: ['admin'], enabled: true, created_at: '2026-09-02T08:05:00Z', is_self: false },
    { id: ID_OHNE, email: 'ohne@example.org', first_name: 'Ohne', last_name: 'Rolle',
      role: null, roles: [], enabled: true, created_at: null, is_self: false },
    { id: ID_MEHR, email: 'mehr@example.org', first_name: 'Mehr', last_name: 'Rollen',
      role: 'sales', roles: ['sales', 'accounting'], enabled: true, created_at: null, is_self: false },
  ];
}

const TEMP_ANLAGE = 'Einmal-Test-1234!';
const TEMP_RESET = 'Neu-Test-5678!';
const ERLAUBT_PATCH = ['first_name', 'last_name', 'role', 'enabled'];
const DEMO_SPERRE = 'In der Demo können Benutzer nicht geändert werden.';

/** Hängt die Attrappe ein und liefert das Protokoll der Aufrufe. */
async function attrappe(
  page: Page,
  opts: { listeFehler?: { status: number; detail: string }; demo?: boolean } = {},
) {
  const db = startBestand();
  const aufrufe: Aufruf[] = [];

  // Zuerst registriert = zuletzt geprüft: alles Übrige unter /api/v1 → 404.
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'nicht gemockt' }) }),
  );

  await page.route('**/api/v1/users**', async (route) => {
    const req = route.request();
    const pfad = new URL(req.url()).pathname.replace(/^.*\/api\/v1/, '');
    const methode = req.method();
    const roh = req.postData();
    const body = roh ? JSON.parse(roh) : null;
    aufrufe.push({ methode, pfad, body });
    const json = (status: number, daten: unknown) =>
      route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(daten) });

    const teile = pfad.split('/').filter(Boolean); // ['users', id?, aktion?]
    const ziel = teile[1] ? db.find((b) => b.id === teile[1]) : undefined;

    if (methode === 'GET' && teile.length === 1) {
      if (opts.listeFehler) return json(opts.listeFehler.status, { detail: opts.listeFehler.detail });
      return json(200, { items: db, total: db.length });
    }
    // backend/app/api/v1/users.py, _mandant_schreiben: im Mandanten demo ist jedes Schreiben gesperrt, Lesen nicht.
    if (opts.demo && methode !== 'GET') return json(403, { detail: DEMO_SPERRE });
    if (methode === 'POST' && teile.length === 1) {
      const unbekannt = Object.keys(body).filter((k) => !['email', 'first_name', 'last_name', 'role'].includes(k));
      if (unbekannt.length) return json(422, { detail: [{ loc: ['body', unbekannt[0]], msg: 'Extra inputs are not permitted' }] });
      if (db.some((b) => b.email === body.email)) return json(409, { detail: 'Diese E-Mail-Adresse ist bereits vergeben.' });
      const neu: Benutzer = { id: ID_NEU, email: body.email, first_name: body.first_name, last_name: body.last_name,
        role: body.role, roles: [body.role], enabled: true, created_at: '2026-10-08T12:00:00Z', is_self: false };
      db.push(neu);
      return json(201, { ...neu, temporary_password: TEMP_ANLAGE });
    }
    if (!ziel) return json(404, { detail: 'Benutzer nicht gefunden.' });
    if (methode === 'PATCH' && teile.length === 2) {
      const unbekannt = Object.keys(body).filter((k) => !ERLAUBT_PATCH.includes(k));
      if (unbekannt.length) return json(422, { detail: [{ loc: ['body', unbekannt[0]], msg: 'Extra inputs are not permitted' }] });
      if (ziel.is_self && body.enabled === false) return json(409, { detail: 'Das eigene Konto kann nicht deaktiviert werden.' });
      if (body.first_name !== undefined) ziel.first_name = body.first_name;
      if (body.last_name !== undefined) ziel.last_name = body.last_name;
      if (body.enabled !== undefined) ziel.enabled = body.enabled;
      if (body.role !== undefined) { ziel.role = body.role; ziel.roles = [body.role]; }
      return json(200, ziel);
    }
    if (methode === 'POST' && teile[2] === 'reset-password') {
      return json(200, { user: ziel, temporary_password: TEMP_RESET });
    }
    return json(405, { detail: 'Nicht im Vertrag' });
  });

  return aufrufe;
}

const karte = (page: Page, email: string) => page.locator('.card', { hasText: email });

test.describe('Benutzerverwaltung (B8)', () => {
  test('zeigt die Antwort des Servers und räumt die alte Attrappe weg', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('minga-mock-users', JSON.stringify([
        { id: '1', name: 'Max Mustermann', email: 'max@minga-greens.de', role: 'ADMIN' },
      ]));
    });
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await expect(karte(page, 'gernot@example.org')).toBeVisible();
    await expect(page.getByText('Max Mustermann')).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem('minga-mock-users'))).toBeNull();
    expect(aufrufe.some((a) => a.methode === 'GET' && a.pfad === '/users')).toBe(true);

    // Benutzer ohne Rolle fallen auf
    await expect(karte(page, 'ohne@example.org').getByText('Keine Rolle')).toBeVisible();
    await expect(page.getByText('Ein aktiver Benutzer hat keine Rolle')).toBeVisible();
  });

  test('Anlegen schickt genau die vier Felder und zeigt das Einmalpasswort einmal', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await page.getByRole('button', { name: 'Neuer Benutzer' }).click();
    const dialog = page.getByRole('dialog');
    // Vorbelegt: Mitarbeiter-Login
    await expect(dialog.locator('input[type=radio][value="production_staff"]')).toBeChecked();
    await expect(dialog.getByText('Darf Rechnungen anlegen, finalisieren und versenden.').first()).toBeVisible();

    await dialog.getByLabel('Vorname').fill('Mia');
    // Esc verwirft das halb ausgefüllte Formular nicht
    await page.keyboard.press('Escape');
    await expect(dialog.getByLabel('Vorname')).toHaveValue('Mia');
    await dialog.getByLabel('Nachname').fill('Mitarbeiterin');
    await dialog.getByLabel('E-Mail').fill('Mia@Example.org');
    await dialog.getByRole('button', { name: 'Anlegen' }).click();

    await expect(page.getByTestId('einmalpasswort')).toHaveText(TEMP_ANLAGE);
    await expect(page.getByText('Anmeldename: mia@example.org')).toBeVisible();
    // Ein versehentliches Esc verwirft das Einmalpasswort nicht
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('einmalpasswort')).toHaveText(TEMP_ANLAGE);
    const anlage = aufrufe.find((a) => a.methode === 'POST' && a.pfad === '/users');
    expect(anlage?.body).toEqual({
      email: 'mia@example.org', first_name: 'Mia', last_name: 'Mitarbeiterin', role: 'production_staff',
    });

    await page.getByRole('button', { name: 'Passwort ist notiert' }).click();
    await expect(page.getByText(TEMP_ANLAGE)).toHaveCount(0);
    await expect(karte(page, 'mia@example.org')).toBeVisible();
  });

  test('Serverfehler erscheinen im Klartext', async ({ page }) => {
    await attrappe(page);
    await page.goto(`${BASE}/users`);

    await page.getByRole('button', { name: 'Neuer Benutzer' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Vorname').fill('Doppelt');
    await dialog.getByLabel('Nachname').fill('Angelegt');
    await dialog.getByLabel('E-Mail').fill('gernot@example.org');
    await dialog.getByRole('button', { name: 'Anlegen' }).click();

    await expect(page.getByText('Diese E-Mail-Adresse ist bereits vergeben.')).toBeVisible();
    await expect(page.getByTestId('einmalpasswort')).toHaveCount(0);
  });

  test('Deaktivieren fragt nach, löscht nie und lässt sich rückgängig machen', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await karte(page, 'gernot@example.org').getByRole('button', { name: 'Deaktivieren', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Benutzer deaktivieren?')).toBeVisible();
    expect(aufrufe.filter((a) => a.methode === 'PATCH')).toHaveLength(0);

    await dialog.getByRole('button', { name: 'Deaktivieren', exact: true }).click();
    await expect(karte(page, 'gernot@example.org').getByText('Deaktiviert')).toBeVisible();
    const patch = aufrufe.filter((a) => a.methode === 'PATCH');
    expect(patch).toHaveLength(1);
    expect(patch[0].pfad).toBe(`/users/${ID_GERNOT}`);
    expect(patch[0].body).toEqual({ enabled: false });
    expect(aufrufe.some((a) => a.methode === 'DELETE')).toBe(false);

    await karte(page, 'gernot@example.org').getByRole('button', { name: 'Aktivieren', exact: true }).click();
    await expect(karte(page, 'gernot@example.org').getByRole('button', { name: 'Deaktivieren', exact: true })).toBeVisible();
    expect(aufrufe.filter((a) => a.methode === 'PATCH')[1].body).toEqual({ enabled: true });
  });

  test('das eigene Konto ist vor Aussperren geschützt', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    const eigene = karte(page, 'admin@minga-greens.de');
    await expect(eigene.getByText('(Sie)')).toBeVisible();
    await expect(eigene.getByRole('button', { name: 'Deaktivieren', exact: true })).toHaveCount(0);

    await eigene.getByRole('button', { name: 'Bearbeiten' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.locator('input[type=radio][value="production_staff"]')).toBeDisabled();
    await expect(dialog.getByLabel('E-Mail')).toBeDisabled();
    await dialog.getByLabel('Vorname').fill('Chefin');
    await dialog.getByRole('button', { name: 'Speichern' }).click();

    await expect(eigene.getByText('Chefin Minga')).toBeVisible();
    const patch = aufrufe.find((a) => a.methode === 'PATCH');
    expect(patch?.pfad).toBe(`/users/${ID_ICH}`);
    expect(patch?.body).toEqual({ first_name: 'Chefin' });
  });

  test('Rolle ändern schickt nur die Rolle', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await karte(page, 'ohne@example.org').getByRole('button', { name: 'Bearbeiten' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.locator('input[type=radio][value="accounting"]').check();
    await dialog.getByRole('button', { name: 'Speichern' }).click();

    await expect(karte(page, 'ohne@example.org').getByText('Buchhaltung')).toBeVisible();
    expect(aufrufe.find((a) => a.methode === 'PATCH')?.body).toEqual({ role: 'accounting' });
  });

  test('mehrere Rollen: Umbenennen behält sie, die höchste wählen stuft darauf zurück', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);
    const mehr = karte(page, 'mehr@example.org');
    await expect(mehr.getByText('Buchhaltung')).toBeVisible();

    await mehr.getByRole('button', { name: 'Bearbeiten' }).click();
    let dialog = page.getByRole('dialog');
    await expect(dialog.locator('input[type=radio]:checked')).toHaveCount(0);
    await dialog.getByLabel('Nachname').fill('Umbenannt');
    await dialog.getByRole('button', { name: 'Speichern' }).click();
    await expect(mehr.getByText('Mehr Umbenannt')).toBeVisible();
    await expect(mehr.getByText('Buchhaltung')).toBeVisible();

    await mehr.getByRole('button', { name: 'Bearbeiten' }).click();
    dialog = page.getByRole('dialog');
    await dialog.locator('input[type=radio][value="sales"]').check();
    await dialog.getByRole('button', { name: 'Speichern' }).click();
    await expect(mehr.getByText('Buchhaltung')).toHaveCount(0);
    await expect(mehr.getByText('Vertrieb')).toBeVisible();

    const patch = aufrufe.filter((a) => a.methode === 'PATCH');
    expect(patch.map((a) => a.body)).toEqual([{ last_name: 'Umbenannt' }, { role: 'sales' }]);
  });

  test('Passwort zurücksetzen fragt nach und zeigt das neue Einmalpasswort', async ({ page }) => {
    const aufrufe = await attrappe(page);
    await page.goto(`${BASE}/users`);

    await karte(page, 'gernot@example.org').getByRole('button', { name: 'Passwort zurücksetzen' }).click();
    expect(aufrufe.filter((a) => a.pfad.endsWith('/reset-password'))).toHaveLength(0);
    await page.getByRole('dialog').getByRole('button', { name: 'Zurücksetzen' }).click();

    await expect(page.getByTestId('einmalpasswort')).toHaveText(TEMP_RESET);
    await expect(page.getByText('Anmeldename: gernot@example.org')).toBeVisible();
    expect(aufrufe.filter((a) => a.methode === 'POST' && a.pfad === `/users/${ID_GERNOT}/reset-password`)).toHaveLength(1);
  });

  test('ein Ladefehler erscheint als Fehler, nicht als leere Liste', async ({ page }) => {
    await attrappe(page, { listeFehler: { status: 503, detail: 'Benutzerverwaltung derzeit nicht verfügbar: Zeitüberschreitung' } });
    await page.goto(`${BASE}/users`);

    await expect(page.getByText('Benutzer konnten nicht geladen werden')).toBeVisible();
    await expect(page.getByText('Benutzerverwaltung derzeit nicht verfügbar: Zeitüberschreitung')).toBeVisible();
    await expect(page.getByText('Keine Benutzer gefunden')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Neuer Benutzer' })).toHaveCount(0);
  });

  test('Demo: Liste lesbar, Schreiben endet mit dem 403 im Klartext', async ({ page }) => {
    const aufrufe = await attrappe(page, { demo: true });
    await page.goto(`${BASE}/users`);
    await expect(karte(page, 'gernot@example.org')).toBeVisible();

    await page.getByRole('button', { name: 'Neuer Benutzer' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Vorname').fill('Sperr');
    await dialog.getByLabel('Nachname').fill('Probe');
    await dialog.getByLabel('E-Mail').fill('sperrprobe@example.org');
    await dialog.getByRole('button', { name: 'Anlegen' }).click();

    await expect(page.getByText(DEMO_SPERRE)).toBeVisible();
    await expect(page.getByTestId('einmalpasswort')).toHaveCount(0);
    expect(aufrufe.filter((a) => a.methode === 'POST')).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Playwright lädt die Spec (ohne Browser, ohne Netzwerk)**

Run: `cd frontend && ./node_modules/.bin/playwright test tests/e2e/benutzerverwaltung.spec.ts --list`
Erwartet: zehn Zeilen `[chromium] › benutzerverwaltung.spec.ts:… › Benutzerverwaltung (B8) › …` und am Ende `Total: 10 tests in 1 file`.

`tsc -p .` prüft `tests/` nicht (`tsconfig.json`: `"include": ["src"]`). Die Spec wird erst von Playwright übersetzt.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/benutzerverwaltung.spec.ts
git commit -m "test(benutzer): Abnahme der Benutzerverwaltung mit gemockter API"
```

---

## Abnahme

Fertig ist der Plan, wenn alle zutreffen:

1. `tests/test_benutzerverwaltung.py`: **120 passed**. „Prozedur Vollauf": `diff` ohne Ausgabe (dieselben 16 Fehlernamen wie die Baseline).
2. Ein Admin-Token des Mandanten A sieht in `GET /api/v1/users` nur Benutzer mit `tenant_slug == [A]`, auch wenn Keycloak Teiltreffer liefert.
3. `GET`, `PATCH` und `POST …/reset-password` auf eine ID eines anderen Mandanten: 404 mit demselben Body wie bei einer unbekannten ID, kein schreibender Keycloak-Aufruf, Audit `FREMDZUGRIFF_ABGEWIESEN`. Eine ID, die keine UUID ist, erreicht Keycloak auch über die Dienstfunktionen nicht.
4. `PATCH` und `POST …/reset-password` auf ein Konto des eigenen Mandanten mit Client-Rollen (außer `account`), Gruppen, fremden oder zusammengesetzten Realm-Rollen: 409 „vom Support verwaltet", kein schreibender Aufruf, Audit `SUPPORTKONTO_ABGEWIESEN`.
5. Nur `admin` kommt durch; `sales`, `production_planner`, `production_staff`, `accounting`, Basic-Auth, `AUTH_DISABLED` und Tokens ohne `sub` bekommen 403.
6. Rollen außerhalb der fünf App-Rollen: 422 (API) bzw. `RolleNichtErlaubt` (Dienst), ohne Keycloak-Aufruf. Zusammengesetzte Rollen werden nicht vergeben (503).
7. Deaktivieren statt löschen; keine DELETE-Route, kein DELETE aus dem Frontend. Ein halb angelegter Benutzer wird deaktiviert, auch wenn Keycloak nach der Anlage ausfällt; ein fremder Benutzer wird dabei nie getroffen.
8. Eigenes Konto: nicht deaktivierbar, Admin-Rolle nicht selbst entziehbar; der letzte aktive Admin bleibt. In der Oberfläche fehlt am eigenen Konto „Deaktivieren", die Rolle ist nicht wählbar.
9. Ohne Service-Account: 503 „nicht eingerichtet", kein Aufruf an Keycloak. Den master-Admin gibt es nur mit `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN=1`. Eine Anmeldung je Prozess und Token-Laufzeit, nicht je Request.
10. Keycloak nicht erreichbar oder 5xx: 503 „Benutzerverwaltung derzeit nicht verfügbar: …"; die Seite zeigt den Wortlaut als Fehler, nie eine leere Liste.
11. Demo-Mandant: lesen ja, schreiben 403. Öffentliche Demo-Logins schreiben in keinem Mandanten (403).
12. Schreibende Aufrufe je Mandant gebremst: ab dem 31. je Minute und Prozess 429, ohne Keycloak; Lesen frei.
13. Deaktivieren, Rollenwechsel und Passwort-Reset beenden die Sitzungen des Zielbenutzers.
14. Kein Passwort in Logzeilen. Das Einmalpasswort erscheint genau einmal in einem Dialog, der weder über Esc noch über einen Klick daneben schließt.
15. Das Frontend schickt nie `tenant_slug` oder `attributes`, im PATCH nur geänderte Felder.
16. `tsc --noEmit -p .` ohne Ausgabe, `npm run build` endet mit `✓ built`, `playwright test tests/e2e/benutzerverwaltung.spec.ts --list` zeigt `Total: 10 tests in 1 file`.
17. `git diff --stat efcea00..HEAD` (bzw. ab dem Startcommit des Workers): genau die zwölf Dateien aus „File Structure"; keine Datei aus „Nicht anfassen".

**Abschlussmeldung des Workers:** Hashes der elf Commits (Task 1–7 und 9–12; Task 8 committet nichts), die Ausgaben von Task 7 Step 3 und Step 4, Task 8 Step 2 bis 5, Task 10 Step 5 und Task 12 Step 2, dazu jede redaktionell aufgelöste Unstimmigkeit.

## Manager-Abnahme (lokal, gemockt oder gegen einen Keycloak-Testrealm)

Der Manager prüft am laufenden Code, nicht am Diff. Teil A ist Pflicht. Teil B ist die einzige Stelle vor der Produktion, an der echter Keycloak mit dem echten Code spricht; er ist vor dem ersten Deploy dringend empfohlen und ersetzt die Deploy-Gates nicht (Keycloak 22 aus dem Repo, die Produktionsversion prüft D1).

### A. Gemockt (Pflicht)

1. **Backend-Datei:**
   ```bash
   cd backend && REDIS_URL=memory:// /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_benutzerverwaltung.py -q -p no:cacheprovider
   ```
   Erwartet: `120 passed`.
2. **Vollauf** nach „Prozedur Vollauf": `Fehlernamen wie Baseline`.
3. **Typen und Build:**
   ```bash
   cd frontend && ./node_modules/.bin/tsc --noEmit -p . && npm run build
   ```
   Erwartet: keine tsc-Ausgabe, `✓ built`.
4. **Oberfläche gegen die gemockte API:**
   ```bash
   cd frontend
   VITE_AUTH_DISABLED=true VITE_API_URL=http://localhost:5179 ./node_modules/.bin/vite --port 5179 --strictPort &
   VITE_PID=$!
   for i in $(seq 1 60); do curl -sf http://localhost:5179/ >/dev/null && break; sleep 1; done
   U2_ABNAHME_URL=http://localhost:5179 ./node_modules/.bin/playwright test tests/e2e/benutzerverwaltung.spec.ts --retries=0 --reporter=list
   ```
   Erwartet: `10 passed`. Die Schleife wartet höchstens 60 s, bis der Server antwortet; nach einer Änderung an Konfiguration oder Abhängigkeiten baut Vite beim ersten Start den Abhängigkeits-Cache neu, ein festes `sleep 5` reicht dann nicht. **Gegenprobe** (am 08.10. gemessen): dieselbe Spec gegen unverändertes `main` @ `efcea00` ergibt `10 failed`, die Spec misst also die Änderung.
5. **Sichtprüfung** im Browser, gleicher Dev-Server, `http://localhost:5179/users` (ohne Playwright-Attrappe):
   - Die Seite zeigt den Fehlerzustand mit Text und „Erneut versuchen", keine leere Liste. Vite leitet `/api` an `http://localhost:8000` weiter (`vite.config.ts`, `server.proxy`); was dort läuft, bestimmt nur den Wortlaut (kein Server: Proxy-Fehler; ein Backend ohne diesen Plan: „Not Found"; eins mit diesem Plan und `AUTH_DISABLED`: „Benutzerverwaltung nur mit einem Keycloak-Login dieses Mandanten.").
   - Strg+K, „benu" eintippen: Als Admin erscheint „Benutzerverwaltung".
   - Danach den Dev-Server beenden: `kill $VITE_PID`. `vite.config.ts` setzt `host: true`, der Server lauscht sonst weiter im LAN.
6. **Diff-Umfang:**
   ```bash
   git diff --stat efcea00..HEAD
   git log --format=%s efcea00..HEAD
   ```
   Erwartet: genau die zwölf Dateien aus „File Structure", keine aus „Nicht anfassen"; elf Commits (Task 1–7, 9–12). Startet der Worker auf einem neueren `main`, dessen Commit statt `efcea00`.
7. **Review Focus 1–5** am Code abhaken.

### B. Lokaler Keycloak-Testrealm (empfohlen vor dem ersten Deploy)

Misst, was die Attrappe nur annimmt (Review Focus 1), ob der Service-Account `view-realm` braucht (Zusammenführung 3, Offener Punkt M17), und stellt den `tenant_slug`-Angriff aus D5 an einem eigenen Keycloak nach. Nichts davon berührt Produktion. **Nicht vorab gelaufen:** In der Planungsumgebung lief kein Keycloak. Die Keycloak-Seite (Startbefehl, Konsole, Account-REST-API) ist **Annahme** laut Keycloak-Dokumentation für Version 22; die Python-Seite nutzt nur Namen aus diesem Plan.

**Aufbau** (nur lokal; `admin`/`admin` gilt nur für diesen Wegwerf-Container):
```bash
docker run -d --name b8-keycloak -p 127.0.0.1:8180:8080 -v b8-keycloak-data:/opt/keycloak/data \
  -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak:22.0 start-dev
```
In der Admin-Konsole `http://localhost:8180/admin` einen Realm `b8-test` anlegen, darin:
1. Realm-Rollen `admin`, `sales`, `production_planner`, `production_staff`, `accounting` (nicht zusammengesetzt).
2. Client `b8-frontend`: OpenID Connect, „Client authentication" aus, „Direct access grants" an. Im dedizierten Client-Scope einen Mapper „User Attribute": Attribut `tenant_slug`, Token-Claim `tenant_slug`, Typ String, „Add to access token" an.
3. Client `novaerp-users`: „Client authentication" an, „Service accounts roles" an, „Standard flow" und „Direct access grants" aus. Unter „Service accounts roles" zunächst nur `realm-management` → `manage-users` und `view-users`. Das Secret unter „Credentials" nur in die Variable unten übernehmen.
4. Benutzer, Benutzername = E-Mail, „Email verified" an, Passwort nicht temporär (für alle dasselbe Testpasswort), Attribut `tenant_slug`:
   - `chef@dev.test`: `tenant_slug` = `dev`, Realm-Rolle `admin`
   - `lena@dev.test`: `dev`, `production_staff`
   - `x@fremd.test`: `fremd`, `production_staff`
   - `y@devx.test`: `devx`, `admin`
   - `betrieb@dev.test`: `dev`, `admin`, dazu Client-Rolle `realm-management` → `realm-admin`

`dev` ist `DEFAULT_TENANT_SLUG` (`tenancy.py:53`): Der Testclient mit `base_url="http://localhost"` landet in diesem Mandanten (`tenancy.py:186-188`), und `/api/v1/users` braucht keine Mandanten-Datenbank. Die `.venv` hat kein uvicorn; der `TestClient` ruft die echte App im Prozess auf, mit echten Tokens und echter Token-Prüfung (`core/security.py`, Issuer `KEYCLOAK_URL/realms/KEYCLOAK_REALM`).

**Probe** (aus `backend/`; Secret und Passwort werden eingelesen, nicht ausgegeben):
```bash
cd backend
export KEYCLOAK_URL=http://localhost:8180 KEYCLOAK_REALM=b8-test KEYCLOAK_USERS_CLIENT_ID=novaerp-users \
       REDIS_URL=memory:// TENANTS_DIR=/tmp/b8-tenants
read -rs KEYCLOAK_USERS_CLIENT_SECRET; export KEYCLOAK_USERS_CLIENT_SECRET
read -rs B8_PW; export B8_PW
/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python - <<'EOF'
import os, time, httpx
from jose import jwt
from fastapi.testclient import TestClient
from app.main import app
from app.services import keycloak_admin

KC, REALM = os.environ["KEYCLOAK_URL"], os.environ["KEYCLOAK_REALM"]

def token(benutzer):
    r = httpx.post(f"{KC}/realms/{REALM}/protocol/openid-connect/token",
                   data={"grant_type": "password", "client_id": "b8-frontend",
                         "username": benutzer, "password": os.environ["B8_PW"]})
    r.raise_for_status()
    return r.json()["access_token"]

def rep(benutzer):
    """Keycloak-Sicht über den Service-Account, unabhängig von der API."""
    with keycloak_admin._Benutzerzugang() as k:
        treffer = k.call("GET", "/users", params={"username": benutzer, "exact": "true"}).json()
        if not treffer:
            return None
        uid = treffer[0]["id"]
        rollen = sorted(m["name"] for m in k.call("GET", f"/users/{uid}/role-mappings/realm").json())
        return {**k.call("GET", f"/users/{uid}").json(), "rollen": rollen}

chef = TestClient(app, base_url="http://localhost", headers={"Authorization": f"Bearer {token('chef@dev.test')}"})
r = chef.get("/api/v1/users")
print("K1", r.status_code, sorted(b["email"] for b in r.json().get("items", [])))
neu_mail = f"neu-{int(time.time())}@dev.test"
r = chef.post("/api/v1/users", json={"email": neu_mail, "first_name": "Neu", "last_name": "Test", "role": "production_staff"})
print("K2", r.status_code, "Einmalpasswort erhalten" if r.status_code == 201 else r.json().get("detail"))
neu = rep(neu_mail)
print("K3", neu and (neu.get("attributes"), neu["rollen"], neu.get("enabled")))
if neu:
    r = chef.patch(f"/api/v1/users/{neu['id']}", json={"first_name": "Neuer"})
    print("K4", r.status_code, rep(neu_mail).get("attributes"))
x = rep("x@fremd.test")
r = chef.patch(f"/api/v1/users/{x['id']}", json={"first_name": "Gehackt"})
print("K5", r.status_code, r.json(), rep("x@fremd.test").get("firstName"))
b = rep("betrieb@dev.test")
r = chef.post(f"/api/v1/users/{b['id']}/reset-password")
print("K6", r.status_code, r.json().get("detail"))
if neu:
    r = chef.patch(f"/api/v1/users/{neu['id']}", json={"enabled": False})
    print("K7", r.status_code, rep(neu_mail).get("enabled"))
lt = token("lena@dev.test")
konto = httpx.get(f"{KC}/realms/{REALM}/account/", headers={"Authorization": f"Bearer {lt}", "Accept": "application/json"}).json()
konto.setdefault("attributes", {})["tenant_slug"] = ["fremd"]
r = httpx.post(f"{KC}/realms/{REALM}/account/", headers={"Authorization": f"Bearer {lt}"}, json=konto)
print("K8", r.status_code, jwt.get_unverified_claims(token("lena@dev.test")).get("tenant_slug"))
EOF
```

Erwartet:

| Zeile | Erwartet | Bedeutung, wenn nicht |
|---|---|---|
| K1 | `200 ['betrieb@dev.test', 'chef@dev.test', 'lena@dev.test']` (bei Wiederholung zusätzlich die `neu-…`-Konten), **ohne** `x@fremd.test` und `y@devx.test` | Mandantentrennung der Liste kaputt: stoppen |
| K2 | `201 Einmalpasswort erhalten` | `502 Keycloak hat die Anfrage abgelehnt: Rolle 'production_staff' konnte nicht gelesen werden (HTTP 403).` heißt: `view-realm` fehlt. Dem Service-Account `realm-management` → `view-realm` zuweisen, Probe wiederholen, Ergebnis für D7 notieren (Offener Punkt M17) |
| K3 | `({'tenant_slug': ['dev']}, ['default-roles-b8-test', 'production_staff'], True)` | Attribut nicht gespeichert oder falsche Rolle: stoppen |
| K4 | `200 {'tenant_slug': ['dev']}` | Ein `PUT` hat das Attribut verworfen (Review Focus 1): stoppen |
| K5 | `404 {'detail': 'Benutzer nicht gefunden.'}` und der bisherige Vorname | Fremdzugriff möglich: stoppen |
| K6 | `409 Dieser Benutzer wird vom Support verwaltet und kann hier nicht geändert werden.` | Supportkonto übernehmbar: stoppen |
| K7 | `200 False` | Deaktivieren wirkt nicht |
| K8 | `dev`, egal ob der POST mit 4xx abgelehnt oder mit 2xx ohne Wirkung angenommen wurde | `fremd` heißt: Keycloak 22 lässt Benutzer ihr `tenant_slug` selbst ändern. Dann in der Konsole bei `lena@dev.test` wieder `dev` eintragen, den Container mit derselben Datenablage und der Option `--spi-user-profile-legacy-user-profile-read-only-attributes=tenant_slug` neu starten (`docker rm -f b8-keycloak`, dann der `docker run` von oben mit der Option hinter `start-dev`; **Annahme:** Optionsname laut Keycloak-Dokumentation) und K8 wiederholen. Das Ergebnis zeigt, worauf D5 in Produktion achten muss |

Aufräumen: `docker rm -f b8-keycloak && docker volume rm b8-keycloak-data`.

## Deploy-Gates und Live-Prüfung (Betrieb, kein Worker, nach der Manager-Abnahme)

Betriebsschritte des Managers gegen Produktion. Nur lesen, außer im Testmandanten `abnahme` (D9); keine Secrets ausgeben. Ist ein Gate rot: kein Deploy. Ein rotes D5 betrifft auch den heutigen Betrieb: sofort melden und in Keycloak schließen, nicht bis zum Deploy warten. Realm laut Betriebsnotiz `novaerp`, Token-URL `https://auth.novaerp.de/realms/novaerp`, Frontend-Client `novaerp-frontend`; vorher mit D1 abgleichen.

- **D1 Realm und Version.** `KEYCLOAK_URL` und `KEYCLOAK_REALM` im laufenden Container lesen (nur Namen). Die Benutzerverwaltung nutzt `settings.keycloak_realm`; das muss der Realm sein, aus dem die Logins kommen. Keycloak-Version über das Image-Tag des laufenden Containers oder `GET /admin/serverinfo`.
- **D2 Attributsuche.** `GET /admin/realms/<realm>/users?q=tenant_slug:minga&exact=true&briefRepresentation=false&max=100` liefert die Minga-Benutzer **mit** `attributes.tenant_slug`. Dazu prüfen, ob Teiltreffer vorkommen: Für die Funktion egal (Python-Filter), für die Last nicht.
- **D3 Rollen.** `GET /admin/realms/<realm>/roles/<rolle>` liefert für `admin`, `sales`, `production_planner`, `production_staff`, `accounting` jeweils `"composite": false` (sonst antworten Anlegen und Rollenwechsel mit 503 und schreiben nichts; bei `admin` hätte sonst jeder Mandanten-Admin Keycloak-Adminrechte über alle Mandanten). `GET /admin/realms/<realm>/roles/default-roles-<realm>/composites` enthält keine `realm-management`-Rolle; der Code lässt die Standardrolle als einzige zusammengesetzte Rolle zu.
- **D4 Rollen über Gruppen.** Bekommen Bestandsbenutzer ihre App-Rollen über Gruppen oder zusammengesetzte Rollen? Der Code liest und setzt nur **direkte** Realm-Rollen-Zuordnungen (wie `create_tenant_user`, `keycloak_admin.py:154-159`); Konten in Gruppen gelten als Supportkonten und sind nur lesbar (409, Offener Punkt M10).
- **D5 `tenant_slug` ist für Benutzer nicht änderbar** (Pflicht; Lücke bestünde schon heute: Mit `anna@demo.novaerp.de`/`demo1234` und `tenant_slug=minga` käme ein Besucher mit dem nächsten Token als Admin auf `minga.novaerp.de`, weil `deps.py:76-85` nur Host gegen Claim prüft. Mit diesem Plan könnte er dort zusätzlich eigene Admins anlegen und Gernots Passwort zurücksetzen; die Regel zum letzten Admin greift nicht, weil anna mitzählt.)
  - (a) **Konfiguration.** Ab Keycloak 24: `GET /admin/realms/<realm>/users/profile` deklariert `tenant_slug` mit `permissions.edit == ["admin"]`, oder `unmanagedAttributePolicy` ist `ADMIN_EDIT`. Bei `ENABLED` können Benutzer es ändern; bei `ADMIN_VIEW` oder fehlender Policy speichert Keycloak ein undeklariertes `tenant_slug` beim Anlegen gar nicht (Anlage endet mit 502, Benutzer deaktiviert). Unter Version 24: Startoption `--spi-user-profile-legacy-user-profile-read-only-attributes` bzw. Umgebungsvariable `KC_SPI_USER_PROFILE_LEGACY_USER_PROFILE_READ_ONLY_ATTRIBUTES` enthält `tenant_slug` (im Repo fehlt sie, `docker-compose.prod.yml:45`), oder das Feature `declarative-user-profile` ist aktiv und `tenant_slug` nur für `admin` editierbar. **Annahme:** Optionsnamen laut Keycloak-Dokumentation. Manager-Abnahme B, Zeile K8 zeigt das Verhalten von Version 22.
  - (b) **Negativprobe, entscheidend.** Stellt den Angriff mit dem Testadmin aus D9 nach; das Ziel `abnahme-probe` existiert nicht, selbst ein Erfolg verschiebt den Testadmin nur in einen leeren Mandanten:
    ```bash
    KC=https://auth.novaerp.de; REALM=novaerp; CLIENT=novaerp-frontend   # Betriebsnotiz Demo-Umgebung; vorher mit D1 abgleichen
    read -rs TA_PW                                                      # Passwort des Testadmins aus D9, wird nicht ausgegeben
    token() { curl -s "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=password -d client_id=$CLIENT \
      --data-urlencode username=abnahme-admin@novaerp.de --data-urlencode "password=$TA_PW" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'; }
    claim() { python3 -c 'import sys,json,base64; p=sys.argv[1].split(".")[1]; p+="="*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p)).get("tenant_slug"))' "$1"; }
    TOK=$(token); claim "$TOK"                                           # erwartet: abnahme
    curl -s -H "Authorization: Bearer $TOK" -H 'Accept: application/json' "$KC/realms/$REALM/account/" \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); d.setdefault("attributes",{})["tenant_slug"]=["abnahme-probe"]; print(json.dumps(d))' > /tmp/g3-konto.json
    curl -s -o /dev/null -w '%{http_code}\n' -X POST "$KC/realms/$REALM/account/" \
      -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' --data @/tmp/g3-konto.json
    claim "$(token)"; rm -f /tmp/g3-konto.json                          # erwartet wieder: abnahme
    ```
    Grün, wenn der zweite `claim` `abnahme` liefert, egal ob der POST mit 4xx abgelehnt oder mit 2xx ohne Wirkung angenommen wurde. Rot, wenn er `abnahme-probe` liefert: Attribut in der Admin-Konsole zurücksetzen, (a) herstellen, Probe wiederholen.
  - (c) `editUsernameAllowed: false` im Realm (`GET /admin/realms/<realm>`); die Demo-Login-Sperre hängt am Benutzernamen.
  - (d) Realm settings → Login: „User registration" ist aus. Eine Selbstregistrierung mit eigenen Attributen umginge (a).
- **D6 Betreiberkonten.** Alle Inhaber von `realm-management`-Rollen mit ihrem `tenant_slug`: `GET /admin/realms/<realm>/clients?clientId=realm-management` → ID, dann `GET …/clients/<id>/roles/<rolle>/users` für `realm-admin`, `manage-users`, `manage-realm`, `manage-clients`, `impersonation`, dazu Gruppen mit solchen Rollen und ihre Mitglieder. Ein solches Konto mit dem `tenant_slug` eines Kunden weist der Code mit 409 ab (S7); es sollte trotzdem keinen tragen.
- **D7 Service-Account statt master-Admin** (T5 R5, Risiko 2):
  1. Im Realm aus D1 einen Client `novaerp-users` anlegen: vertraulich, „Service accounts" an, Standard Flow und Direct Access Grants aus. Service-Account-Rollen nur `realm-management` → `manage-users`, `view-users`, `view-realm` (letztere nur lesend, für `GET /roles/<rolle>`; ob nötig, zeigt Manager-Abnahme B, Zeile K2). Nie `realm-admin` oder `manage-realm`. Auch `manage-users` gilt realmweit; die Mandantentrennung bleibt Sache des Codes.
  2. In Coolify `KEYCLOAK_USERS_CLIENT_ID=novaerp-users` und `KEYCLOAK_USERS_CLIENT_SECRET` setzen; das Secret nirgends ausgeben. `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN` ist **nicht** gesetzt.
  3. Mit dem Token dieses Service-Accounts (nicht dem master-Admin): `GET /admin/realms/<realm>/roles/production_staff` antwortet 200, ebenso `GET …/users/<id>/role-mappings` und `GET …/users/<id>/groups`. Ohne Leserecht scheitert jedes Anlegen und jeder Rollenwechsel mit 502 „… Rolle 'production_staff' konnte nicht gelesen werden (HTTP 403)." (**Annahme** aus dem Keycloak-Quelltext, `RoleContainerResource.getRole`).
  4. Nach dem Deploy lädt die Benutzerliste (L1). „… nicht eingerichtet (Service-Account fehlt: …)" heißt: Variablen fehlen.
- **D8 Demo-Liste ist öffentlich.** Nach dem Deploy sieht jeder Besucher als anna Name und E-Mail aller Konten mit `tenant_slug=demo`. Vorher in der Admin-Konsole (Users → Attributsuche `tenant_slug` = `demo`) prüfen: genau anna, ben, clara, paul (`DEMO_USERS`, `platform.py:229-234`), keine echten Personen und keine Test- oder Betreiberkonten (Offener Punkt M6).
- **D9 Testmandant `abnahme`** für die schreibende Probe (einmalig, vor D5 (b)). Ein Mandant ohne öffentliche Logins, angelegt über die Plattform-API (`POST /api/v1/platform/tenants`, `platform.py:71-157`). Mit `admin_password` ist das Passwort nicht temporär (`platform.py:146`), deshalb funktioniert der Password-Grant in D5 (b):
  ```bash
  read -rs PAK                                    # PLATFORM_ADMIN_KEY aus Coolify, wird nicht ausgegeben
  TA_PW=$(openssl rand -base64 18)                # danach nur in den Passwortmanager übernehmen
  curl -s -X POST "https://admin.novaerp.de/api/v1/platform/tenants?slug=abnahme" \
    -H "X-Platform-Admin-Key: $PAK" -H 'Content-Type: application/json' \
    -d "{\"admin_email\":\"abnahme-admin@novaerp.de\",\"admin_password\":\"$TA_PW\"}" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("status"), d.get("url"), d.get("user_warning"), (d.get("admin_user") or {}).get("email"))'
  ```
  Erwartet: `created https://abnahme.novaerp.de None abnahme-admin@novaerp.de`. Danach auf dem Server `/usr/local/bin/novaerp-wildcard-sync.sh` für die neue Subdomain (Betriebsnotiz Prod-Topologie). Adressen unter `@novaerp.de`, damit keine fremde Adresse im gemeinsamen Realm belegt wird (Offener Punkt M3).

**Live-Prüfung nach dem Deploy** (Backend und Frontend zusammen, erst nach dem B8-Kern aus Paket 3 und mit D1–D9 grün; vorher WAL-sicheres Backup laut Deploy-Freigabe). Auf der Demo wird nur gelesen; geschrieben wird ausschließlich im Testmandanten `abnahme`.

- **L1 Demo, lesend und Sperre** (`demo.novaerp.de`, **anna**, admin, `platform.py:230`): Menü → Benutzerverwaltung lädt; „Service-Account fehlt" wäre D7. Die Liste zeigt genau anna, ben, clara und paul; anna trägt „(Sie)" und hat kein „Deaktivieren". „Neuer Benutzer" mit `sperrprobe@novaerp.de`, Rolle Produktion, „Anlegen": Der Toast zeigt „In der Demo können Benutzer nicht geändert werden.", es erscheint kein Einmalpasswort, nach dem Neuladen stehen weiter genau vier Konten da. Sonst auf der Demo nichts Schreibendes anklicken.
- **L2 Testmandant, schreibend gegen echtes Keycloak** (`https://abnahme.novaerp.de`, Testadmin aus D9):
  1. Als `abnahme-admin@novaerp.de` anmelden → Benutzerverwaltung: genau ein Eintrag mit „(Sie)", kein Konto aus `demo` oder `minga`.
  2. `abnahme-ma@novaerp.de` mit Rolle Produktion anlegen. Im Einmalpasswort-Dialog Esc drücken: Der Dialog bleibt offen. „Kopieren", dann „Passwort ist notiert". DevTools: Die Antwort von `POST /api/v1/users` enthält `temporary_password` und den Header `Cache-Control: no-store`; Local Storage enthält das Passwort nicht. Endet das Anlegen mit 502 „… Rolle 'production_staff' konnte nicht gelesen werden (HTTP 403).": D7 Punkt 1, `view-realm`.
  3. Privates Fenster: als `abnahme-ma` mit dem Einmalpasswort anmelden. Keycloak verlangt ein neues Passwort, danach landet das Konto im Tagesplan (`/day-plan`, `Startseite` in `App.tsx:32-39`).
  4. Als Admin „Passwort zurücksetzen" für `abnahme-ma` (Rückfrage erscheint): neues Einmalpasswort. Im privaten Fenster scheitert das selbst gesetzte Passwort, das neue verlangt wieder einen Wechsel.
  5. Als Admin `abnahme-ma` deaktivieren (Rückfrage erscheint). Danach scheitert die Anmeldung.
- **L3 Fremdzugriff gegen echtes Keycloak** (S1/S5 ohne Attrappe). Variablen und `token()` aus D5 (b):
  ```bash
  ANNA=$(curl -s "$KC/realms/$REALM/protocol/openid-connect/token" -d grant_type=password -d client_id=$CLIENT \
    -d username=anna@demo.novaerp.de -d password=demo1234 | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  BEN_ID=$(curl -s -H "Authorization: Bearer $ANNA" https://demo.novaerp.de/api/v1/users \
    | python3 -c 'import json,sys; print([b["id"] for b in json.load(sys.stdin)["items"] if b["email"]=="ben@demo.novaerp.de"][0])')
  TOK=$(token)
  curl -s -w ' %{http_code}\n' -X PATCH "https://abnahme.novaerp.de/api/v1/users/$BEN_ID" \
    -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d '{"first_name":"X"}'
  curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOK" https://demo.novaerp.de/api/v1/users
  ```
  Erwartet: `{"detail":"Benutzer nicht gefunden."} 404`, dann `403` (Token-Mandant ≠ Host, `deps.py:76-80`). Als anna heißt ben danach weiter „Ben". Kommt etwas anderes: sofort stoppen, Deploy zurücknehmen, ben in der Admin-Konsole prüfen. Ein Passwort-Reset gegen ein fremdes Konto wird absichtlich nicht probiert (ein Treffer gäbe ein Passwort aus und sperrte ben aus); das deckt `TestPasswort::test_fremd_404_und_kein_schreibzugriff`.
- **L4 Nicht-Admin** (`demo.novaerp.de`, **ben**, sales, `platform.py:231`, nur lesend): kein Menüpunkt; Strg+K mit „benu" findet „Benutzerverwaltung" nicht; `/users` direkt aufrufen zeigt „Kein Zugriff" (Review Focus 5).

## Offene Punkte für Manager und Betrieb

- **M1 Audit nur im Container-Log.** Logs überleben keinen Redeploy (Container werden je Deploy ersetzt, Betriebsnotiz Prod-Topologie). Dauerhafte Alternativen: eigene Tabelle je Mandant (entsteht per `create_all`; Demo-Reset-Risiko 11 aus T5 beachten) oder Keycloak-Admin-Events im Realm (Betriebsschritt). Entscheidung Manager.
- **M2 Passwort per Mail** (`PUT /users/{id}/execute-actions-email` mit `["UPDATE_PASSWORD"]`) nicht gebaut: braucht SMTP im Realm, im Code nicht prüfbar (`keycloak/realm-export.json` hat kein `smtpServer`). Heute wie beim Onboarding: Einmalpasswort, das der Admin persönlich weitergibt.
- **M3 E-Mail-Adressen im gemeinsamen Realm.** Ein 409 verrät realmweit, dass es eine Adresse gibt, auch bei einem anderen Mandanten (Kunden sind oft Konkurrenten); die Meldung nennt weder Mandant noch ID, vermeiden lässt es sich bei eindeutigen Benutzernamen nicht. Task 6 bremst das Abklopfen, Task 3 protokolliert jeden Treffer als `ANLAGE_ABGELEHNT`. Umgekehrt kann jeder Admin außerhalb der Demo jede freie Adresse dauerhaft belegen (kein Löschen; Konten entstehen wie beim Onboarding mit `emailVerified: true`). Folge: Das Onboarding eines Neukunden mit dieser Adresse legt den Mandanten ohne Login an (`user_warning`, `platform.py:154-155`), andere Mandanten bekommen 409 für ihre Mitarbeiter. Offen: Obergrenze für Anlagen je Mandant und Tag; `emailVerified: false` (hängt an `verifyEmail` und SMTP im Realm, M2). **Betriebsregel** (ins Betriebshandbuch): Bei einem solchen 409 ein vorhandenes Konto nie auf einen anderen Mandanten umhängen (`tenant_slug` ändern). Wer es angelegt hat, kennt sein Einmalpasswort und käme damit in den neuen Mandanten. Erst klären, wem die Adresse gehört; bis dahin bleibt das Konto deaktiviert, und der Kunde nimmt eine andere Adresse.
- **M4 Schon ausgestellte Access-Tokens.** Die App prüft Tokens lokal (`core/security.py:62-82`). Nach Deaktivieren, Rollenwechsel und Reset beendet der Code die Sitzungen (`/logout`), ein laufendes Access-Token gilt aber bis zu seinem Ablauf weiter (**Annahme:** Realm-Standard 5 Minuten, nicht im Code). Der Rückfragetext verspricht deshalb nur, dass keine neue Anmeldung möglich ist. Scheitert `/logout`, schreibt der Code nur eine WARNING, sonst ginge beim Reset das neue Einmalpasswort verloren.
- **M5 Onboarding-Pfad unverändert.** `create_tenant_user` prüft die Rolle weiterhin erst nach der Anlage (T5 R4, `keycloak_admin.py:147-153`). Bewusst nicht angefasst, um den Plattform-Pfad nicht zu berühren; Kandidat für einen kleinen Folgeschritt (Rolle vorab prüfen wie in `create_user_for_tenant`).
- **M6 Demo.** Schreiben ist im Demo-Mandanten gesperrt, die öffentlichen Demo-Logins sind es in jedem Mandanten. Lesen bleibt erlaubt: Jeder Besucher sieht **alle** Keycloak-Konten mit `tenant_slug=demo` samt Name und E-Mail, auch nicht öffentliche Test- oder Betreiberkonten, etwa „Mia" aus T5 R4, bevor sie in `DEMO_USERS` steht (D8). Die Oberfläche zeigt in der Demo „Neuer Benutzer", „Bearbeiten", „Deaktivieren" und „Passwort zurücksetzen", und jeder Knopf endet im Toast „In der Demo können Benutzer nicht geändert werden." — funktional richtig, für Interessenten unschön. Ausblenden kann das Frontend heute nicht, weil es den Mandanten nicht kennt (`AuthContextType.user` ohne `tenant_slug`, `frontend/src/context/AuthContext.tsx:8-20`; `Branding` ohne Slug, `frontend/src/context/BrandingContext.tsx`). Möglicher Weg: Das Backend liefert in `BenutzerListResponse` ein Feld `schreibgeschuetzt`, das Frontend blendet danach aus, je S. Zu entscheiden: so lassen und keine nicht öffentlichen Konten in `demo` anlegen, die Liste in der Demo auf `DEMO_USERS` beschränken, oder ausblenden. Soll die Demo das Ändern zeigen, bräuchte es eine Keycloak-seitige Rücksetzung.
- **M7 Klartext im 409-Audit.** `ANLAGE_ABGELEHNT` enthält `ziel_email` im Klartext, auch wenn die Adresse einem anderen Mandanten gehört. Die verworfene Variante aus dem U2-Nachtrag N2 schrieb stattdessen `ANLAGE_KONFLIKT` mit `ziel_email_sha256` (wiederholtes Abklopfen bleibt erkennbar, keine fremde Adresse im Log). Klartext hilft dem Betrieb bei der Betriebsregel aus M3, Hash schont die Daten des anderen Mandanten. Entscheidung Manager; ein Wechsel ändert `create_user` und `TestAnlegen::test_email_vergeben`, je S.
- **M8 Last.** Liste und Letzter-Admin-Prüfung lesen die Rollen je Benutzer einzeln (N+1 Keycloak-Aufrufe), in synchronen Endpunkten, die sich einen Threadpool mit allen Mandanten teilen; für wenige Dutzend Benutzer unkritisch. Über 1000 Treffer der Attributsuche: 502 statt unvollständiger Liste. Die Schreibbremse zählt je Prozess (Review Focus 3); Lesen ist ungebremst, im Demo-Mandanten kann jeder Besucher die Liste beliebig oft abrufen. Eine Obergrenze an Konten je Mandant gibt es nicht. Offen: `SlowAPIMiddleware` einbinden (wirkt auf alle Routen, eigener Schritt) oder `GET /users` zusätzlich bremsen, Kontenzahl begrenzen; je S.
- **M9 Wettlauf um den letzten Admin** (Review Focus 2). Wiederherstellung über die Keycloak-Admin-Konsole durch den Plattform-Betrieb.
- **M10 Supportkonten und Gruppen.** Konten mit Client-Rollen außer `account`, mit Gruppen, mit Realm-Rollen außerhalb der App- und Standardrollen oder mit zusammengesetzten Rollen ändert der Code nicht (409). Bekommen Mandanten-Benutzer in Produktion ihre App-Rollen über Gruppen (D4), kann der Mandanten-Admin sie nur sehen. Dann: Rollen auf direkte Zuordnung umstellen oder die Gruppenprüfung gezielt lockern.
- **M11 Weitere ungeschützte Ziele.** „Einstellungen" steht ebenfalls für jede Rolle in der Befehlspalette (`CommandPalette.tsx:71`), und alle Routen in `App.tsx` sind ohne Rollenprüfung. Im Backend ist alles gesperrt (`_deps_admin`). Nachziehen nach dem Muster von Task 11: S, nicht Teil dieses Plans.
- **M12 Rollentexte hängen an der Matrix.** `services/rollen.ts` fasst die Rechte-Matrix aus `main.py` zusammen; ein Test dafür existiert nicht. Ändert Paket 3 (R1/R2) die Matrix, bleiben die Texte richtig (Kundenkonditionen und DATEV-Export verspricht keiner Rolle außer `accounting`). Wer die Matrix danach weiter ändert, zieht die Texte mit.
- **M13 Testmandant `abnahme` bleibt stehen.** `abnahme-ma@novaerp.de` bleibt deaktiviert im Realm, `abnahme-admin@novaerp.de` aktiv, damit D5 (b) und L2 wiederholbar sind; das Passwort liegt nur im Passwortmanager. Gelöscht wird nichts: `DELETE /api/v1/platform/tenants/{slug}` entfernt nur die SQLite-Datei (`platform.py:188-209`), die Keycloak-Konten blieben. Wird der Mandant nicht mehr gebraucht, deaktiviert der Plattform-Betrieb `abnahme-admin` in der Admin-Konsole.
- **M14 Lokale Entwicklung.** Mit `AUTH_DISABLED` antwortet die Benutzerverwaltung mit 403 („nur mit einem Keycloak-Login dieses Mandanten"), die Seite zeigt dann den Fehlerzustand. Gewollt; echte Abläufe prüft Manager-Abnahme B oder die gemockte Spec.
- **M15 Admins eines Mandanten sind gleich mächtig.** Jeder Admin kann das Passwort eines anderen Admins zurücksetzen, sieht das Einmalpasswort und kann das Konto übernehmen. Eine technische Sperre (z. B. Reset eines Admins nur durch ihn selbst oder den Support) wäre eine Backend-Änderung, je S. Entscheidung Manager; Gernot wird informiert („Offene Punkte für Gernot" 3).
- **M16 Schalter `KEYCLOAK_USERS_ALLOW_MASTER_ADMIN` bleibt im Code** (Zusammenführung 1). Er nützt nur Entwicklung und Test; ein versehentlich gesetzter Schalter in Produktion brächte den master-Admin zurück. Alternative: Schalter entfernen (U2-Nachtrag N1), dann braucht auch die lokale Abnahme einen Service-Account (Manager-Abnahme B hat einen). Entscheidung Manager.
- **M17 `view-realm` für den Service-Account** (Zusammenführung 3). Abweichung von T5 R5 („nur `manage-users` und `view-users`"). Manager-Abnahme B, Zeile K2 misst an Keycloak 22, ob es ohne geht; in Produktion entscheidet D7.

## Offene Punkte für Gernot

1. **F11 — Weitere Profilfelder.** Sein ursprünglicher B8-Wunsch war „Profilfelder ergänzen". Gebaut sind Vorname, Nachname, E-Mail, Rolle und aktiv. Welche Felder braucht er je Mitarbeiter darüber hinaus, z. B. Telefon oder ein Kürzel auf Belegen? Nicht gebaut, weil es nicht ohne Zusatzaufwand geht: Ob der Realm frei gewählte Attribute speichert, hängt von seiner User-Profile-Einstellung ab (nicht im Code prüfbar), ein Kürzel auf Belegen braucht zusätzlich den Weg in die PDFs, und beide Felder müssten wie `tenant_slug` nur für Admins schreibbar sein (D5), sonst fälscht jeder sein Kürzel. Nach der Antwort: zwei Felder im Backend-Schema, zwei Eingaben im Formular, je S, plus PDF-Weg. Der Code schreibt beim Ändern alle vorhandenen Attribute unverändert zurück, ein späteres Feld bricht nichts.
2. **F6 — Wer bekommt welchen Login?** Name und E-Mail je Mitarbeiter. Mitarbeiter-Login ist „Produktion" (`production_staff`, Entscheidung 3). Wer „Vertrieb" oder „Buchhaltung" bekommt, kann heute auch Rechnungen anlegen, finalisieren und versenden (T5 Lücke 6); das widerspricht seiner Vorgabe „Rechnungen bleiben beim Admin" (Antwort 11). Die Rollenauswahl warnt nur. Dazu F1: Sollen Hallen-Tablets von Büro-Mitarbeitern getrennt werden? Heute bekommen beide dieselbe Rolle.
3. **Vor der Freigabe sagen** (zusammen mit Entscheidung 6):
   - Mitarbeiter-Logins erst anlegen, wenn der B8-Kern aus Paket 3 live ist; vorher bricht die Bestellerfassung für sie ab, und sie könnten abrechnungsrelevante Kundenfelder ändern.
   - Jeder Admin kann das Passwort eines anderen Admins zurücksetzen und das Konto übernehmen; die Admin-Rolle sparsam vergeben (M15).
   - Das Protokoll dieser Aktionen steht nur im Container-Log und geht beim nächsten Deploy verloren (M1).
   - Zwei Admins sollten sich nicht gleichzeitig gegenseitig herabstufen oder deaktivieren; beide Änderungen können durchgehen und den Mandanten ohne Admin lassen, wiederherstellen kann das nur der Plattform-Betrieb (M9).
   - Einmalpasswörter persönlich übergeben, nicht per Chat oder E-Mail; beim ersten Anmelden setzt die Person ein eigenes.
4. **E-Mail-Adresse nicht änderbar.** Sie ist der Anmeldename. Für eine neue Adresse einen neuen Benutzer anlegen und den bisherigen deaktivieren. Reicht ihm das?
5. **Was gegenüber der Attrappe wegfällt.** „Telefon" und „Zuletzt aktiv" zeigte die Attrappe mit erfundenen Werten; das echte System liefert sie nicht (Telefon hängt an F11, der letzte Login bräuchte Keycloak-Events). Die sieben erfundenen Nutzer verschwinden, „Löschen" wird „Deaktivieren".
