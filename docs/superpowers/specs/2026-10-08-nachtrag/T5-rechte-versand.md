# T5: Mitarbeiter-Rechte (B8) und Belegversand an mehrere Empfänger (B3)

Stand: `main` @ `c4a1832`, Analyse am 08.10.2026. Es wurde nur gelesen: keine Datei im Repo geändert, kein Zugriff auf Produktion.
Kennzeichnung: **belegt** heißt im Code gesehen oder im Probelauf gemessen. **Annahme** heißt im Code nicht prüfbar.

Probelauf: `/tmp/nachtrag_probe/probe_t5.py`. Das Skript nutzt den FastAPI-TestClient gegen die echte `app.main.app` mit leerer In-Memory-SQLite und überschreibt `get_current_user` je Rolle, genauso wie `backend/tests/test_rollen.py:21-29`. Gemessen wird nur, ob die Rolle durchkommt (403 oder nicht). `git status` war vor und nach dem Lauf gleich.
Nachprüfung (08.10.): Der Probelauf wurde wiederholt, alle Werte der Tabelle in 1.2 stimmen. Ein zweiter Probelauf `/tmp/nachtrag_probe2/probe_ls_doppelt.py` nach demselben Muster misst Risiko 12. Auch danach war `git status` unverändert. `tests/test_rollen.py` und `tests/test_dunning.py` laufen grün (21 passed).

---

## Kurzfassung

- **Entscheidung 3 (Mitarbeiter-Login = `production_staff`) passt weiterhin.** Nötig sind zwei kleine Korrekturen an der Matrix. Eine neue Rolle braucht es nicht.
- Über die API darf `production_staff` heute schon Bestellungen anlegen, AB anlegen und versenden sowie LS anlegen und quittieren. An Rechnungen kommt die Rolle nicht heran. Das deckt Gernots Wunsch fast ab.
- **Die Bestellerfassung bricht aber in der Oberfläche ab:** Die Produktliste antwortet dieser Rolle mit 403. Das Formular „Neue Bestellung" fällt dann still auf die Saatgut-Liste zurück (10 € je g). Beim Speichern kommt 404 „Produkt … nicht gefunden". Im Formular „Bestellung bearbeiten" bleibt die Produktauswahl leer.
- **Gleichzeitig darf die Rolle zu viel:** Über denselben Router ändert sie Kundenkonditionen, Sonderpreise und Abos und kann den DATEV-Debitorenexport abrufen.
- **Gefahr durch die neuen Rechte:** Legt jemand zu einer Bestellung einen zweiten Lieferschein an, berechnet der Sammellauf die Bestellung doppelt (im Probelauf gemessen, Risiko 12). Das sollte vor der Freigabe an Mitarbeiter gesperrt sein.
- **Einen Lieferschein-Versand gibt es für niemanden.**
- **Der heutige Versand ist dünn:** ein Empfänger per `window.prompt`, ohne vorbelegte Adresse und ohne Protokoll. Die Rechnungsmail nennt fest „Minga Greens".
- **B3:** drei Empfängerlisten je Kunde (AB, LS, RE), eine Mail mit allen Adressen im To, Cc nur optional, eine Tabelle als Versandprotokoll für die Anzeige „versendet an (1) …, (2) …". Wer was versenden darf, folgt aus dem Router, in dem der Endpunkt liegt (AB und LS in der Belegkette, RE im Rechnungsrouter).
- **Aufwand:** B8-Minimum S (R1–R4), dazu S für die LS-Sperre (L1) und S für den Demo-Reset (D1). B3 M, Selbstverwaltung der Benutzer im Mandanten L (Paket 4).

---

## 1 Ist-Zustand (belegt)

### 1.1 Wie die Rechte-Matrix umgesetzt ist

- Die fünf Rollen sind Konstanten in `backend/app/main.py:82-88`: `admin`, `sales`, `production_planner` (PLANER), `production_staff` (PRODUKTION), `accounting` (BUCHHALTUNG).
- `_rollen(*lesen, schreiben=None)` baut je Router eine Abhängigkeit aus `get_current_user` und `require_access(lesen, schreiben)`. `admin` ist immer in beiden Listen (`main.py:91-104`).
- `require_access` unterscheidet nur nach HTTP-Methode: GET/HEAD/OPTIONS gilt als Lesen, alles andere als Schreiben (`api/deps.py:123`, `:126-152`).
- **Geprüft wird nur auf Router-Ebene**, beim `include_router` (`main.py:673-838`).
  - `require_access` wird nur in `main.py:80,100` verwendet.
  - `require_role` (`deps.py:104-119`) ist an keinem Endpunkt verdrahtet (grep über `backend/app`).
  - Es gibt also keine Rechteprüfung pro Endpunkt.
- Die Rollen kommen aus `realm_access.roles` des Keycloak-Tokens (`deps.py:87-89`). Der Mandant kommt aus dem Claim `tenant_slug` und wird mit der Subdomain abgeglichen (`deps.py:71-85`).
- Im Frontend steuern die Rollen nur, was angezeigt wird:
  - Navigation je Rolle: `components/common/Layout.tsx:58-257`.
  - Angezeigte Rolle = höchste Rolle nach Rangfolge: `Layout.tsx:288-299`.
  - Startseite der reinen Hallenrolle ist der Tagesplan: `App.tsx:33-38`.
- Vorhandene Tests in `backend/tests/test_rollen.py` prüfen auf Router-Ebene. Unter anderem: Halle darf Bestellungen und LS, aber keine Rechnungen oder Preislisten (Z. 86-105, 200-204).

### 1.2 Was jede Rolle heute darf

Legende: R = lesen, W = schreiben, – = 403. `admin` darf überall alles.

| Bereich | Router · Abhängigkeit | sales | production_planner | production_staff | accounting |
|---|---|---|---|---|---|
| Bestellungen anlegen, ändern, bestätigen, Status setzen, Entwurf löschen | `sales.router` · `_deps_auftraege` (`main.py:122`, `:701-706`) | RW | RW | RW | RW |
| Kundenstamm inkl. Zahlungsziel, Kreditlimit, Rabatt, DATEV-Konto (`schemas/customer.py:149-166`), Adressen, Ansprechpartner (`sales.py:110-282`, `:393-437`) | derselbe Router | RW | RW | RW | RW |
| Kunden-Sonderpreise (`sales.py:283-370`) | derselbe Router | RW | RW | RW | RW |
| DATEV-Debitorenexport (`sales.py:439-455`) | derselbe Router | R | R | R | R |
| Abos und „Abo-Lauf heute" (`sales.py:458-589`) | derselbe Router | RW | RW | RW | RW |
| AB anlegen und versenden, LS und Packliste anlegen, LS quittieren, PDFs | `documents.router` · `_deps_belege` (`main.py:129`, `:794-799`) | RW | RW | RW | RW |
| Rechnungen: anlegen, finalisieren, versenden, stornieren, Zahlungen, Sammellauf, DATEV | `invoices.router` · `_deps_geld` (`main.py:125`, `:740-744`) | RW | – | – | RW |
| Preislisten | `_deps_geld` (`main.py:734-738`) | RW | – | – | RW |
| Produkte inkl. `base_price` (`schemas/product.py:253`), Produktgruppen, Wachstumspläne | `_deps_vertrieb` (`main.py:124`, `:716-732`) | RW | RW | **–** | RW |
| Excel-Importe | `_deps_vertrieb` (`main.py:788-792`) | RW | RW | – | RW |
| Tagesplan, Chargen, Ernten | `_deps_produktion` (`main.py:108`, `:680-685`) | – | RW | RW | – |
| Auswertungen | `_deps_geld` (`main.py:813-818`) | RW | – | – | RW |
| Einstellungen, Belegvorlagen, Integrationen | `_deps_admin` (`main.py:137`, `:776-780`, `:807-811`, `:827-831`) | – | – | – | – |

- **Bankdaten:** Der Kundenstamm hat keine Bankfelder (`models/customer.py:120-200`; Kommentar „IBAN if we had it" in `datev_service.py:241`). Sie kommen erst mit B10 (Spec, Entscheidung 12).
- **Preise:**
  - Das AB-PDF enthält immer Einzelpreis und Netto (`pdf_service.py:689-699`).
  - Der LS zeigt Preise nur, wenn beim Kunden `show_prices_on_delivery_note` gesetzt ist (`pdf_service.py:752-779`).
  - Im Bestellformular ist der Einzelpreis frei editierbar (`CreateOrderModal.tsx:429-430`).

Ergebnis des Probelaufs. „ok" heißt nicht 403; 404 und 422 auf der leeren DB zählen als durchgekommen.

```
Endpunkt                                         staff   planner  sales   accounting
GET    /api/v1/products                          403     ok       ok      ok
GET    /api/v1/products/{id}/variants            403     ok       ok      ok
GET    /api/v1/sales/customers                   ok      ok       ok      ok
PATCH  /api/v1/sales/customers/{id}              ok      ok       ok      ok
DELETE /api/v1/sales/customers/{id}              ok      ok       ok      ok
POST   /api/v1/sales/customers/{id}/prices       ok      ok       ok      ok
GET    /api/v1/sales/customers/export/datev      ok      ok       ok      ok
POST   /api/v1/sales/subscriptions               ok      ok       ok      ok
POST   /api/v1/sales/orders                      ok      ok       ok      ok
PATCH  /api/v1/sales/confirmations/{id}/send     ok      ok       ok      ok
POST   /api/v1/sales/orders/{id}/delivery-notes  ok      ok       ok      ok
GET    /api/v1/invoices                          403     403      ok      ok
POST   /api/v1/invoices/from-order/{id}          403     403      ok      ok
POST   /api/v1/invoices/{id}/send                403     403      ok      ok
GET    /api/v1/price-lists                       403     403      ok      ok
GET    /api/v1/production/day-plan               ok      ok       403     403
```

### 1.3 Gernots Wunsch im Vergleich mit `production_staff` heute

| Gernot (08.10.) | API | Oberfläche |
|---|---|---|
| Bestellungen anlegen | erlaubt | **Bricht ab.** `CreateOrderModal.tsx:62-65` und `EditOrderModal.tsx:153-157` laden `productsApi.list` und bekommen 403. Im **Anlegen-Formular** ist `productsData` danach `undefined`. Damit schaltet sich der Saatgut-Ersatz ein (`CreateOrderModal.tsx:69-73`, `:76-96`). Gezeigt werden Saatgut-Sorten mit Preis 10 und Einheit g. `GET /seeds` ist für die Halle lesbar (`_deps_stammdaten`, `main.py:112`). Beim Speichern geht die Saatgut-ID als `product_id` an den Server. Der antwortet mit 404 „Produkt … nicht gefunden" (`sales.py:938-944`). Im **Bearbeiten-Formular** gibt es keinen Ersatz, dort bleibt die Produktauswahl leer. Der Excel-Import geht ebenfalls nicht (`_deps_vertrieb`). |
| AB anlegen und versenden | erlaubt (`documents.py:73-157`) | Knopf vorhanden (`OrderDocumentsModal.tsx:154-195`), Empfänger per `window.prompt` |
| LS anlegen | erlaubt (`documents.py:185-260`) | vorhanden (`OrderDocumentsModal.tsx:211-218`; im Tagesplan `Tagesplan.tsx:60-62`) |
| LS versenden | **gibt es für keine Rolle**, `documents.py` hat keinen Endpunkt dafür | – |
| Rechnungen nur beim Admin | Die Hallenrolle ist gesperrt (`_deps_geld`). `sales` und `accounting` dürfen aber ebenfalls. | Das Belege-Modal zeigt der Hallenrolle trotzdem den Rechnungsteil: Die Liste bekommt 403 und bleibt leer, „Rechnung aus Bestellung" endet mit einer Fehlermeldung (`OrderDocumentsModal.tsx:43-47`, `:282-296`). |
| nicht gewünscht: Kundenkonditionen, Sonderpreise, DATEV-Export, Abos | **erlaubt** (derselbe Router) | Die Navigation blendet Kunden und Abos für die Halle aus (`Layout.tsx:177-181`, `:197-202`). Die API ist trotzdem offen. |

### 1.4 Rollen gelten realmweit: welche Mandanten betroffen sind

- Es gibt einen Keycloak-Realm je Deployment:
  - `config.py:39` (`keycloak_realm`, Standard `minga-greens`).
  - Das Token wird gegen genau diesen Realm geprüft (`core/security.py:69`).
  - Der Admin-Helfer liest dieselbe Variable `KEYCLOAK_REALM`, hat aber den Standard `novaerp` (`services/keycloak_admin.py:42`).
  - Die Standardwerte im Code passen also nicht zusammen. `docker-compose.prod.yml:38` setzt sogar `minga-greens`. Welcher Realm in Produktion gilt, steht nicht im Code. **Annahme** laut Betriebsnotiz zur Demo: `novaerp` (Token-URL `auth.novaerp.de/realms/novaerp`). Vor jedem Keycloak-Schritt `KEYCLOAK_REALM` im laufenden Container prüfen.
- Rollen sind Realm-Rollen (`deps.py:87-89`). Die Matrix steht als Code in `main.py` und gilt für jeden Mandanten dieser Instanz.
- Wer `production_staff` haben kann:
  - Demo: `DEMO_USERS` enthält admin, sales, accounting und production_planner, **aber keinen production_staff** (`api/v1/platform.py:229-234`). Ändert man die Rechte von production_staff, ändert sich an der Demo nichts.
  - Neue Mandanten: Beim Onboarding wird nur ein `admin` angelegt (`platform.py:134-147`).
  - Damit bleiben nur Nutzer, die jemand von Hand in Keycloak angelegt hat.
  - **Annahme:** Aktiv sind nur die Mandanten `minga` und `demo` (Betriebsnotiz vom 02.10.), und Gernots Mitarbeiter-Logins gibt es noch nicht (Notiz „Mitarbeiter-Accounts offen" vom 02.09.). Vor dem Rollout prüfen: `GET /admin/realms/<realm>/roles/production_staff/users`, Realmname wie oben aus `KEYCLOAK_REALM`.
- Achtung: Eine Änderung an `sales`, `accounting` oder `production_planner` träfe die Demo-Logins ben, clara und paul.

### 1.5 Benutzeranlage heute

- Die Benutzerverwaltung im Frontend ist eine Attrappe:
  - Sieben erfundene Nutzer liegen im localStorage. `create`, `update` und `delete` schreiben nur dorthin (`services/api.ts:1015-1121`).
  - Die Seite `pages/Users.tsx:44-245` nutzt diese Attrappe.
  - Ein dort „angelegter" Mitarbeiter existiert also nicht.
- Einen echten Weg gibt es nur intern: `create_tenant_user(email, tenant_slug, role, …)` (`keycloak_admin.py:74-173`).
  - Legt den Nutzer an, setzt das Attribut `tenant_slug` und weist die Realm-Rolle zu.
  - Bricht hart ab, wenn die Rolle im Realm fehlt (`:140-164`).
  - Aufgerufen wird die Funktion nur an zwei Stellen: beim Mandanten-Onboarding mit Rolle admin (`platform.py:141-147`) und beim Anlegen der Demo-Logins (`platform.py:255-276`).
  - Einen Endpunkt für beliebige weitere Nutzer gibt es nicht.
- Der Helfer meldet sich bei Keycloak als Admin des **master-Realms** an (`keycloak_admin.py:52-66`), also mit Vollzugriff auf alle Mandanten.

### 1.6 Belegversand heute

| Beleg | Endpunkt | Empfänger | Nach dem Versand |
|---|---|---|---|
| AB | `PATCH /api/v1/sales/confirmations/{id}/send`, Body `{sent_to_email?: str}` (`documents.py:111-157`, `schemas/documents.py:20-21`) | ein String; leer heißt „nur Status setzen" (`documents.py:130`) | Status VERSENDET, `sent_at` und `sent_to_email` String(200) werden gesetzt (`documents.py:152-154`, `models/documents.py:44-45`). Danach ist die AB gesperrt und kann nicht erneut versendet werden (`documents.py:124-125`). |
| LS | gibt es nicht | – | Der Status `AUSGESTELLT` existiert (`models/enums.py:75`), wird aber nirgends gesetzt. |
| Rechnung | `POST /api/v1/invoices/{id}/send?to_email=…` (`invoices.py:223-275`), Pflicht-Parameter in der Query | ein String, nicht geprüft | `sent_at` wird gesetzt, ENTWURF wird zu OFFEN (`invoices.py:270-272`). Der Empfänger wird nicht gespeichert. |
| Mahnung (automatisch) | Scheduler-Job `payment-reminders` täglich 09:00 je Mandant (`scheduler_service.py:98`, Schleife über die Mandanten `:30-57`), Versand in `tasks/invoice_tasks.py:149-163` | fest `customer.email` | Läuft über einen **zweiten Mailweg** (`core/email.py:12-69`): SMTP aus Umgebungsvariablen (`config.py:43-51`) statt aus den Mandanten-Einstellungen. |
| Mahnung (von Hand) | `POST /api/v1/invoices/{id}/payment-reminder` (`invoices.py:183-220`) | – | **Verschickt keine Mail**, erzeugt nur das PDF zum Herunterladen. Setzt trotzdem `reminder_level` und `last_reminder_sent_at` (`:208-213`). Gehört ins Versandprotokoll nur, wenn später ein Mailversand dazukommt. |

- `send_email` kann wenig:
  - nimmt genau einen Empfänger (`services/email_service.py:40-48`; `msg["To"] = to`, `:77`)
  - wertet die Rückgabe von `send_message` nicht aus, also auch keine abgelehnten Empfänger (`:95`, `:104`)
  - setzt keine Message-ID und kennt kein Cc
  - lehnt Host `localhost` ab (`:65`)
- Es gibt ein ungenutztes Schema mit Cc-Feld: `InvoiceSendRequest` (`schemas/invoice.py:239-245`). Es wird in `invoices.py:21` importiert, aber nicht verwendet.
- Frontend:
  - Einziger Aufrufer ist `OrderDocumentsModal.tsx`, mit `window.prompt` (`:111-115`).
  - Der Prompt wird **ohne Vorbelegung** aufgerufen (`:189`, `:324`). Nicht einmal die Haupt-E-Mail des Kunden wird vorgeschlagen.
  - Die Rechnungsseite hat keinen Versandknopf.
- Kundenfelder:
  - Vorhanden: `email` (Hauptkontakt, `models/customer.py:141`), `ansprechpartner_email` (`:148`) und eine Ansprechpartner-Tabelle mit Rolle ALLGEMEIN/EINKAUF/VERTRIEB/BUCHHALTUNG/TECHNIK (`models/customer.py:275-300`; Oberfläche `Customers.tsx:603-660`).
  - **Es gibt kein Feld für Rechnungs- oder Beleg-E-Mail** und kein Merkmal „Belege per Mail".
- Wer versendet hat, steht nirgends. Die Versand-Endpunkte bekommen den Nutzer gar nicht übergeben (`documents.py:112`, `invoices.py:224-228`).
- Mailtexte:
  - Die Rechnungsmail nennt fest „— Minga Greens" und „Ihr Minga-Greens-Team" (`invoices.py:254`, `:260`). Für jeden anderen Mandanten ist das falsch.
  - Die AB-Mail endet mit „Ihr Team" (`documents.py:142`).
- PDFs werden bei jedem Abruf neu erzeugt und nicht gespeichert (`invoices.py:466-494`, `documents.py:160-180`).
- `sent_at` der Rechnung wird schon beim Finalisieren gesetzt, auch ohne Mail (`services/invoice_service.py:237`). Dasselbe gilt für die Gutschrift beim Storno (`invoice_service.py:349`).
- AB- und LS-PDF sind keine Momentaufnahme. Sie werden bei jedem Abruf aus den **aktuellen** Bestellpositionen erzeugt (`pdf_service.py:680`, `:690-700` für die AB; `:745`, `:760` für den LS). Positionen lassen sich im Status BESTAETIGT weiter ändern (`sales.py:1310`), auch wenn die AB schon VERSENDET ist. Die Sperre gilt nur für den AB-Status (`models/documents.py:60-61`), nicht für den Inhalt.

---

## 2 Lücken

**B8**
1. Die Hallenrolle kann in der Oberfläche keine Bestellung anlegen, weil die Produkte 403 liefern.
2. Die Hallenrolle darf per API Kundenkonditionen, Sonderpreise und Abos ändern und den DATEV-Debitorenexport abrufen. Die Rechte sind nur pro Router geregelt, das ist zu grob. Mit B10 (IBAN und Mandat im Kundenstamm) wird das kritisch: Was im Kundenobjekt steht, kann die Halle mitlesen.
3. Das Belege-Modal zeigt der Hallenrolle den Rechnungsteil, der dann mit 403-Fehlern endet.
4. Es gibt keine echte Benutzeranlage. Die Attrappe täuscht eine vor.
5. Es gibt keinen Demo-Login mit production_staff, die Rolle lässt sich also nirgends live testen.
6. „Rechnungen nur beim Admin" gilt heute nicht für sales und accounting. Für Minga zählt das nur, wenn solche Logins vergeben werden.
7. Nichts verhindert einen zweiten Lieferschein zur selben Bestellung. Der Sammellauf berechnet die Bestellung dann doppelt (Risiko 12, im Probelauf gemessen).

**B3**
1. Je Kunde und Belegart gibt es keine hinterlegten Empfänger.
2. Pro Mail geht nur ein Empfänger raus, es gibt kein Cc und keine Adressprüfung. Bei der Rechnung ist der Empfänger ein freier Query-String.
3. Es gibt keinen LS-Versand.
4. Es gibt kein Versandprotokoll (wer, wann, an wen, was, mit welchem Ergebnis). Die AB speichert einen String, die Rechnung gar nichts. `sent_at` sagt bei Rechnungen nichts aus, weil es schon beim Finalisieren gesetzt wird.
5. Eine versendete AB lässt sich nicht erneut senden, etwa an eine vergessene zweite Adresse.
6. Die automatische Mahnung läuft an allem vorbei: eigener Mailweg, nur `customer.email`.
7. Die Mailtexte nennen fest „Minga Greens".

---

## 3 Vorschlag

### 3.1 Welche Rolle

**`production_staff` bleibt der Mitarbeiter-Login.**

Warum:
- Die Rolle deckt Gernots Wunsch schon fast ab: Bestellungen und Belegkette offen, Rechnungen gesperrt (Tabelle 1.3).
- Die anderen Rollen passen schlechter:
  - `sales` hat Rechnungen und Preislisten, aber keinen Tagesplan. Das widerspricht „Rechnungen bleiben beim Admin".
  - `production_planner` hat zwar keine Rechnungen, darf aber Produkte samt Basispreis, Sorten-Stammdaten, Kapazitäten, Einkauf, Importe und Prognosen ändern (`main.py:110-127`). Das ist zu viel für Mitarbeiter.
  - Eine neue Rolle (etwa `office_staff`) kostet M, ohne fachlich etwas zu bringen, solange in der Halle und im Büro dieselben Leute arbeiten. Zu ändern wären:
    - Realm-Rolle in Keycloak anlegen
    - Konstanten und Matrix in `main.py`, dazu die Schreibrollen-Liste in `main.py:458`
    - Dev-Rollen in `deps.py:44`, `security.py:58`, `AuthContext.tsx:29`
    - in `Layout.tsx` Typ, Rangfolge und Navigation
    - `App.tsx:35-37`
    - Tests
  - Sinnvoll wäre eine eigene Rolle nur, wenn Gernot Hallen-Tablets von Büro-Mitarbeitern trennen will (Frage F1).
- Die Matrix-Änderung gilt realmweit. R1 und fast alles aus R2 betreffen laut Code nur production_staff-Nutzer. Die Demo-Logins haben diese Rolle nicht, und beim Onboarding wird sie nie vergeben (1.4).
  - **Ausnahme:** Die Sperre des DATEV-Debitorenexports in R2 (nur noch admin, sales, accounting) nimmt das Recht auch `production_planner` weg. Das trifft alle Planer-Logins, darunter den Demo-Login paul (`platform.py:233`). In der Oberfläche merkt Paul davon nichts, weil die Planung den Menüpunkt Kunden gar nicht sieht (`Layout.tsx:177-180`). Über die API ändert sich aber sein Recht.

### 3.2 B8: Arbeitspakete

**R1: Halle darf Produkte lesen (S)**
- In `main.py:716-732` die Router für Produkte, Produktgruppen und Wachstumspläne von `_deps_vertrieb` umstellen auf `_rollen(SALES, BUCHHALTUNG, PLANER, PRODUKTION, schreiben=[SALES, BUCHHALTUNG, PLANER])`. Wer schreiben darf, bleibt wie heute.
- Folge: Die Halle kann Produkte mit `base_price` und die Preislisten-Positionen in `ProductDetailResponse` lesen (`schemas/product.py:356`). Das ist vertretbar: Laut Gernot erfassen Mitarbeiter Bestellungen mit Preisen und versenden AB mit Preisen. Der Preislisten-Router selbst bleibt bei `_deps_geld`.
  - Neu ist die Einsicht ohnehin kaum. Über den Sales-Router liest die Halle schon heute die Sonderpreise je Kunde (`sales.py:283-296`) und `unit_price` samt `base_price` je Produkt (`sales.py:372-389`).
- Vor R1 nicht ausliefern: Ohne R1 legt das Anlegen-Formular Bestellungen mit Saatgut-IDs an und scheitert erst beim Speichern (1.3).

**R2: Kundenstamm und Geldsachen im Sales-Router absichern (S–M)**
- Die Rollen-Konstanten aus `main.py` in ein eigenes Modul verschieben (etwa `app/core/rollen.py`), damit die Router sie ohne zirkulären Import nutzen können.
- An einzelnen Endpunkten eine zusätzliche Abhängigkeit setzen. FastAPI verlangt dann beide Prüfungen (Router und Endpunkt):
  - Kunde anlegen, ändern, löschen, reaktivieren sowie Adressen und Ansprechpartner (`sales.py:110-190`, `:205-282`, `:405-437`): schreiben dürfen nur noch admin, sales, accounting und planner, also wie heute ohne die Halle.
  - Sonderpreise schreiben (`sales.py:298-370`): ebenso.
  - DATEV-Debitorenexport (`sales.py:439`): nur noch admin, sales und accounting, und zwar schon beim Lesen.
  - Abos schreiben und `process-today` (`sales.py:503-589`): ohne die Halle.
- Kunden lesen darf die Halle weiterhin. Das braucht sie für das Bestellformular und den Empfängervorschlag.
- **Achtung, Rücknahme einer früheren Entscheidung:** Der Router steht für die Halle offen, weil Gernot am 03.09. festgelegt hat: „Aufträge: **Kunden und Bestellungen**. Ausdrücklich auch für die Halle — bei Ausfall der Betriebsleitung müssen die Mitarbeiter erfassen können" (`main.py:119-122`). Die Kunden-Sperre aus R2 nimmt das zurück. F2 muss deshalb **vor** R2 beantwortet sein, nicht danach. Ohne Antwort zuerst nur Sonderpreise, Konditionen, DATEV-Export und Abos sperren, Kundenanlage und Adressen offen lassen.
- Wenn Mitarbeiter Kunden anlegen dürfen (F2): nur `POST /customers` freigeben. Die Konditionsfelder setzt der Server dabei auf Standardwerte. Die Oberfläche zeigt der Halle die Kundenseite heute gar nicht (`Layout.tsx:177-180`), es bräuchte also auch einen Menüpunkt.
- Für B10 gleich mit festhalten: Mandats- und Bankdaten nicht ins `CustomerResponse` aufnehmen, sondern über einen eigenen Endpunkt im Geld-Bereich ausliefern. Dann greift die Router-Matrix von selbst.

**R3: Oberfläche anpassen (S)**
- `OrderDocumentsModal`: Den Rechnungsteil nur für admin, sales und accounting anzeigen (über `useUser()`, `Layout.tsx:277`).
- Benutzerverwaltung: Bis R4 bzw. R5 die Attrappe durch den Hinweis „Benutzer legt der Support an" ersetzen oder den Menüpunkt entfernen. So legt niemand Scheinnutzer an.

**R4: Mitarbeiter anlegen, kleinster echter Weg (S)**
- Sofort, ohne Code, als Betriebsschritt:
  - In Keycloak (Realm laut 1.4 im Container prüfen, **Annahme** `novaerp`) den Nutzer mit Attribut `tenant_slug=minga`, Realm-Rolle `production_staff` und temporärem Passwort anlegen. Gleichwertig: im App-Container `create_tenant_user(email=…, tenant_slug="minga", role="production_staff")` aufrufen.
  - Vorher prüfen, dass die Realm-Rolle existiert (`keycloak_admin.py:142-153`). Der Helfer legt den Nutzer **vor** der Rollenprüfung an (`:104-126`). Fehlt die Rolle, bleibt ein Nutzer ohne Rolle zurück. Er kommt nirgends hin, aber ein zweiter Aufruf scheitert an der 409 (`:123-124`), und die Rolle muss dann von Hand zugewiesen werden.
  - Das Passwort nur an den Mitarbeiter geben, nicht in Logs oder Chats.
- Kleinster Schritt mit Code: Plattform-Endpunkte hinter `X-Platform-Admin-Key`:
  - `POST /api/v1/platform/tenants/{slug}/users`, Body `{email, role, first_name, last_name}`.
    - Rolle nur aus der Liste {production_staff, sales, accounting, production_planner}; admin nur über das Onboarding.
    - Der Mandant muss existieren (`registry.exists`).
    - Das Einmalpasswort wird genau einmal zurückgegeben.
  - `GET /api/v1/platform/tenants/{slug}/users`: Keycloak-Suche nach dem Attribut `tenant_slug` über `q=tenant_slug:<slug>`. Die Version der Client-Bibliothek keycloak-js (`frontend/package.json:18`, ^26) sagt nichts über die Server-Version. Im Repo ist der Server auf `quay.io/keycloak/keycloak:22.0` festgelegt (`docker-compose.yml:152`). **Annahme, nicht im Code prüfbar:** Produktion läuft auf ≥ 22, und die Attributsuche über `q=` gibt es dort. Vor dem Bau einmal gegen den Produktions-Keycloak testen.
  - `POST /api/v1/platform/tenants/{slug}/users/{id}/disable`: vorher prüfen, dass der `tenant_slug` des Nutzers zum `slug` passt.
  - Ein Knopf dafür in admin.novaerp.de.
- Demo: `DEMO_USERS` um einen production_staff-Login ergänzen, etwa „Mia Mitarbeiterin" (`platform.py:229-234`), danach `POST /platform/demo/seed-users`. Dann ist die Rolle live testbar.

**R5: Selbstverwaltung im Mandanten (L, Paket 4, wie in der Spec)**
- `/api/v1/users` unter `_deps_admin`.
- `tenant_slug` immer aus dem Token nehmen, nie aus dem Request-Body.
- Rollen nur aus einer festen Liste.
- Vor jeder Änderung das `tenant_slug`-Attribut des Zielnutzers prüfen.
- Keycloak über einen Service-Account im Realm ansprechen, der nur `manage-users` und `view-users` hat, statt über den master-Admin.

### 3.3 B3: Belegversand an mehrere Empfänger

**Grundsatz (nach Gernot): eine Mail, alle hinterlegten Adressen im To.** Die Adressen gehören gleichrangigen Adressaten derselben Firma, sie dürfen sich gegenseitig sehen. Cc gibt es nur als optionales Zusatzfeld im Dialog, Bcc an Kunden gar nicht. Optional kann eine Bcc-Kopie ans eigene Postfach gehen (Mandanten-Einstellung, Frage F4).

**Datenmodell**
- `customers` bekommt drei neue Spalten über `_auto_migrate` (`tenancy.py:270-281`): `confirmation_emails`, `delivery_note_emails`, `invoice_emails`.
  - Im Modell als `JSON` (Liste von Adressen), in der DDL als `TEXT`. In `_auto_migrate` wurde bisher keine JSON-Spalte angelegt; SQLAlchemy-JSON speichert auf SQLite ohnehin Text.
  - Ist die Liste leer oder NULL, wird `customers.email` verwendet.
  - Geprüfte Alternative: Kennzeichen an `contacts` (`receives_ab`, `receives_ls`, `receives_re`). Das wäre sauberer normalisiert. Aber Funktionspostfächer wie „rechnung@kunde.de" sind keine Personen, und Gernot müsste je Kontakt Haken setzen. Für sein Beispiel sind Spalten am Kunden direkter. Die E-Mails der Ansprechpartner erscheinen im Dialog als Vorschläge.
- Neue Tabelle `document_dispatches` als Versandprotokoll. Sie entsteht beim Start über `create_all` (`tenancy.py:228`, `:255`). Felder:
  - `id`, `doc_type` (AB | LS | RE | MAHNUNG)
  - je ein Fremdschlüssel `confirmation_id`, `delivery_note_id`, `invoice_id`, alle nullable; genau einer ist gesetzt
  - `order_id` (nullable, für die Abfrage je Bestellung) und `customer_id`
  - `to_addrs` (JSON), `cc_addrs` (JSON), `bcc_self` (bool), `subject`, `attachment_filename`, `attachment_sha256`
  - `status` (GESENDET | TEILWEISE | FEHLER | NUR_MARKIERT), `refused` (JSON, vom SMTP abgelehnte Adressen), `error` (Text)
  - `message_id`, `sent_at`, `sent_by_name` (preferred_username)
  - `sent_by_id` als **String**, nicht als UUID: Basic-Auth-Nutzer haben IDs wie `basic-auth:name` (`deps.py:52`). Das vorhandene `OrderAuditLog.user_id` ist UUID (`models/order.py:384`) und taugt dafür nicht.
- `order_confirmations.sent_to_email` bleibt als Kurzanzeige (Adressen verkettet, auf 200 Zeichen gekürzt). Maßgeblich ist das Protokoll.

**Mailversand (`email_service.py`) (E1)**
- Neue Signatur: `send_email(db, to: list[str] | str, cc: list[str] | None = None, bcc: list[str] | None = None, attachments=…) -> SendResult`.
  - Ein einzelner String bleibt für alte Aufrufer erlaubt (`admin.py:94`).
  - Mehrere Anhänge gleich vorsehen (siehe Risiko 10).
- Adressen prüfen:
  - mit `email-validator`, das schon Abhängigkeit ist (`requirements.txt:25`; `EmailStr` in `schemas/customer.py:78`)
  - klein schreiben, Dubletten entfernen
  - höchstens 10 Adressen
  - Umlaute im lokalen Teil (Gernots Beispiel „einkäufer@kunde.de" im Spec, Entscheidung 8) lehnen: `email-validator` lässt sie standardmäßig zu. `smtplib.send_message` bricht aber mit `SMTPNotSupportedError` ab, wenn der Server kein SMTPUTF8 anbietet. Das wäre heute ein 502. **Annahme:** Ob IONOS SMTPUTF8 kann, ist nicht geprüft. Bis dahin solche Adressen schon beim Speichern mit einer klaren Meldung ablehnen (`allow_smtputf8=False`).
- Header: `To: a, b`, `Cc`, `Message-ID` über `email.utils.make_msgid`.
- Senden mit `smtp.send_message(msg, to_addrs=to+cc+bcc)`. Die Rückgabe (abgelehnte Empfänger) auswerten und das Protokoll dann auf TEILWEISE setzen.

**Endpunkte**
- **AB:** `PATCH /api/v1/sales/confirmations/{id}/send`, Body erweitert um `to: list[EmailStr] | None`, `cc: list[EmailStr] = []` und `use_customer_recipients: bool = False`. Ein eigener `only_mark`-Schalter entfällt, das leistet der leere Body (nächster Punkt).
  - **Ein leerer Body behält seine heutige Bedeutung „nur als versendet markieren"** (`documents.py:115-116`, `:130`). Das schickt das heutige Frontend bei leerer Eingabe (`OrderDocumentsModal.tsx:96`). Die Empfänger aus dem Kundenstamm nimmt der Server nur bei ausdrücklichem `use_customer_recipients: true`. Ein leerer Body darf **nicht** heißen „an die Kundenliste senden". Sonst verschickt ein Browser-Tab mit dem alten Frontend, der nach dem Deploy noch offen ist, beim „nur markieren" eine echte Mail an den Kunden.
  - Mit `use_customer_recipients: true` nimmt der Server die AB-Liste des Kunden, sonst `customers.email`. Ist beides leer: 400 „Kein Empfänger hinterlegt".
  - `sent_to_email` wird übergangsweise weiter akzeptiert.
  - Steht die AB schon auf VERSENDET, darf sie erneut versendet werden. Dann entsteht nur eine neue Protokollzeile, der Status bleibt.
  - **Aber:** Das PDF entsteht aus den aktuellen Bestellpositionen (1.6). Erneut senden ist deshalb nur erlaubt, wenn sich die Bestellung seit dem ersten Versand nicht geändert hat. Prüfen lässt sich das so: PDF neu erzeugen und seine SHA-256 mit `attachment_sha256` der ersten Protokollzeile vergleichen. `orders.updated_at` (`models/order.py:129-131`) taugt dafür nicht, weil es sich auch bei jedem Statuswechsel ändert. Hat sich das PDF geändert, kommt 409 „Bestellung geändert — bitte neue AB anlegen". Ohne diese Prüfung ginge unter derselben AB-Nummer ein anderer Inhalt an den Kunden.
- **LS (neu):** `POST /api/v1/sales/delivery-notes/{id}/send` mit demselben Body und denselben Regeln für den leeren Body. Anhang ist das LS-PDF, die Packliste optional (Frage F5). Der Status wechselt von ENTWURF auf AUSGESTELLT. Ein Lieferschein mit Status GELIEFERT bleibt inhaltlich gesperrt, darf aber als Kopie versendet werden.
- **Rechnung:** `POST /api/v1/invoices/{id}/send` auf einen JSON-Body umstellen. Dafür `InvoiceSendRequest` wieder verwenden, mit `to: list` statt `email_to` und `cc` statt `email_cc`.
  - Den Query-Parameter `to_email` übergangsweise weiter annehmen.
  - Sonst bleibt alles wie heute: STORNIERT ist gesperrt, ENTWURF wird zu OFFEN. Das Verhalten beim Finalisieren mit Paket 1 abstimmen (B4-Kern).
  - Außerdem setzen das Finalisieren (`invoice_service.py:237`) und die Gutschrift beim Storno (`invoice_service.py:349`) `sent_at` nicht mehr. Ob eine Rechnung versendet ist, zeigt dann das Protokoll (B2). Weder Tests noch Frontend lesen `invoices.sent_at` aus (grep über `backend/tests` und `frontend/src`). Das Frontend kennt `sent_at` nur am AB-Typ (`api.ts:1304`).
- **Protokoll lesen:**
  - `GET /api/v1/sales/orders/{id}/dispatches` im Belegketten-Router, nur AB und LS.
  - `GET /api/v1/invoices/{id}/dispatches` im Rechnungsrouter, Rechnungen und Mahnungen.
  - Zusätzlich ein Feld `last_dispatch` (Kurzform) in `OrderConfirmationResponse`, `DeliveryNoteResponse` und `InvoiceResponse`. Dann zeigen die Listen „versendet an …" ohne weitere Abfrage.
- Die drei Versand-Endpunkte bekommen `user: CurrentUser` als Parameter (wie in `sales.py:1259`).
- Mailtexte: den Firmennamen aus `load_company_settings` nehmen statt fest „Minga Greens".
- **Mahnlauf:** `invoice_tasks.py:149` auf `invoice_emails` umstellen (bei leerer Liste `email`), ins Protokoll schreiben und auf `app/services/email_service.send_email` mit dem SMTP des Mandanten wechseln. Zusammen mit „Stornobeleg ohne Mahnung" aus Paket 1 umsetzen.
  - Dabei bricht ein bestehender, heute grüner Test: `tests/test_dunning.py:35-49` ersetzt `app.tasks.invoice_tasks.email_service` und prüft `kwargs["email_to"]`. Er muss mit umgebaut werden. Die Mahntests in `test_production_readiness.py` (`test_dunning_level1/2/3`) stehen schon auf der Liste der 15 bekannten Fehler (Betriebsnotiz Testumgebung).

**Rechte**
- Wer versenden darf, folgt aus der vorhandenen Router-Aufteilung. Sonderlogik ist nicht nötig:
  - AB- und LS-Versand liegen im Belegketten-Router: Die Halle darf.
  - Der Rechnungsversand liegt im Rechnungsrouter: Die Halle bekommt 403.
  - Die Empfängerlisten im Kundenstamm pflegen nach R2 nur admin, sales, accounting und planner.
- Mitarbeiter können im Dialog Adressen für diesen einen Versand ergänzen, aber nicht als Standard beim Kunden speichern. Ob freie Adressen überhaupt erlaubt sind: Frage F3.
- Protokollzeilen zu Rechnungen liefert der Belegketten-Endpunkt nicht aus. Die Halle sieht also nicht, wann Rechnungen verschickt wurden.

**Oberfläche**
- Neue Komponente `SendDocumentDialog` ersetzt `window.prompt`:
  - Kopfzeile: Belegart, Nummer, Kunde.
  - Empfänger als Chips. Vorbelegt mit der Kundenliste der Belegart, sonst mit der Haupt-E-Mail. Vorschläge aus den Ansprechpartnern. Das Format wird schon beim Tippen geprüft.
  - „Cc hinzufügen", standardmäßig eingeklappt.
  - Nur bei der AB: „Nur als versendet markieren (ohne Mail)".
  - Für Rollen, die den Kundenstamm ändern dürfen: Haken „Als Standard für diesen Kunden speichern".
  - Bei Erfolg ein Toast, etwa „AB AB-20261008-0003 versendet an (1) rechnung@kunde.de, (2) einkaeufer@kunde.de". Bei TEILWEISE eine Warnung mit den abgelehnten Adressen.
- `OrderDocumentsModal`:
  - Unter jedem Beleg die Protokollzeilen, etwa „08.10.2026 14:12 · anna · an (1) …, (2) …".
  - Ein Knopf „Erneut senden".
  - Der LS bekommt einen Knopf „Versenden".
- Kundenformular (`Customers.tsx`): neuer Abschnitt „Belegversand" mit drei Feldern für mehrere Adressen (AB, Lieferschein, Rechnung) und dem Hinweis „leer = Haupt-E-Mail".
- Nach „Neue AB" bzw. „Neuer LS" öffnet sich der Dialog direkt, wenn beim Kunden Adressen hinterlegt sind. Das „Belegversand-Kennzeichen" aus der Spec braucht dann kein eigenes Feld: Ist die Liste nicht leer, ist Versand vorgesehen.

### 3.4 Tests

**Backend (pytest, nach dem Muster von `test_rollen.py`)**
- Rollen, `production_staff`:
  - GET `/products` nicht 403, POST `/products` 403
  - PATCH `/sales/customers/{id}` 403, POST `/sales/customers/{id}/prices` 403
  - GET `/sales/customers/export/datev` 403, POST `/sales/subscriptions` 403
  - GET `/sales/customers` nicht 403, POST `/sales/orders` nicht 403
  - PATCH `/sales/confirmations/{id}/send` nicht 403, POST `/sales/delivery-notes/{id}/send` nicht 403
  - POST `/invoices/{id}/send` 403, GET `/invoices/{id}/dispatches` 403
- Rollen, Regression für die Demo-Rollen:
  - sales, accounting und planner dürfen Kunden weiter ändern.
  - Für sales und accounting ist der Rechnungsversand nicht 403.
- Versand (`smtplib.SMTP` per monkeypatch durch eine Attrappe ersetzen, die Nachricht und die Empfänger im SMTP-Umschlag mitschreibt):
  - Zwei Empfänger ergeben genau eine Nachricht; `To` enthält beide, der Umschlag beide.
  - Cc steht im Header und im Umschlag, Bcc nur im Umschlag.
  - Ungültige Adresse oder CRLF ergibt 422. Dubletten werden entfernt. Mehr als 10 Adressen ergeben 422.
  - Lehnt der SMTP eine Adresse ab, steht im Protokoll TEILWEISE mit `refused`.
  - Ein leerer Body `{}` an `/confirmations/{id}/send` setzt nur den Status und verschickt **keine** Mail (die Attrappe zählt 0 Nachrichten).
  - Mit `use_customer_recipients: true` greift die Kundenliste der Belegart, dann `customers.email`, sonst 400.
  - Eine Adresse mit Umlaut im lokalen Teil ergibt 422 mit klarer Meldung (solange SMTPUTF8 nicht geklärt ist).
  - Die Protokollzeile enthält den Absender-Login und `attachment_sha256` = SHA-256 des gesendeten PDFs.
  - Eine AB nach VERSENDET erneut senden ergibt eine zweite Protokollzeile, der Status bleibt. Wurde nach dem ersten Versand eine Position ergänzt, gibt es 409 und keine Mail.
  - LS senden setzt ENTWURF auf AUSGESTELLT.
  - Eine stornierte Rechnung ergibt 400 und keine Protokollzeile.
  - Der Mailtext enthält den Firmennamen aus den Einstellungen, nicht „Minga Greens".
- Migration: Eine alte Mandanten-DB ohne die neuen Spalten bekommt sie über `_auto_migrate`. Bestehende Kunden lassen sich ohne Fehler lesen, die Felder sind leer bzw. NULL.
- Plattform (R4):
  - Eine Rolle außerhalb der erlaubten Liste ergibt 400.
  - `disable` für einen Nutzer eines anderen Mandanten ergibt 403 bzw. 404.
  - Keycloak wird per `monkeypatch` ersetzt, entweder `httpx.Client` oder die Funktionen in `keycloak_admin.py`. Eine Mock-Bibliothek wie respx oder pytest-httpx ist keine Abhängigkeit (`requirements.txt:19` hat nur `httpx==0.26.0`). Bisher testet keine Datei unter `backend/tests` den Keycloak-Helfer.
- Bestandstests, die mitgeändert werden müssen: `tests/test_dunning.py` (E5, siehe 3.3). `test_rollen.py` (20 Tests, heute grün) bleibt unverändert gültig: Keiner seiner Aufrufe wird durch R1/R2 gesperrt.
- Lieferschein (Risiko 12): Ein zweiter `POST /sales/orders/{id}/delivery-notes` zur selben Bestellung ergibt 409. Alternativ, falls Teillieferungen gewollt sind (F10): Der Sammellauf berechnet je Lieferschein nur dessen Packlistenmengen statt aller Bestellpositionen.
- Demo-Reset (Risiko 11): Nach `reset_demo_from_seed` mit einem Seed im alten Schema sind die neuen Spalten und die Tabelle vorhanden.

**Frontend**
- `npm run build` (enthält `tsc`) als Typprüfung. Unit-Tests gibt es im Frontend nicht, nur Playwright.
- Playwright (`frontend/tests/e2e`): Ein Demo-Login mit production_staff (nach R4) legt eine Bestellung an, erzeugt eine AB, versendet sie an zwei Adressen und sieht keinen Rechnungsteil.
  - SMTP in der Testumgebung: Mailpit unter `127.0.0.1`. `email_service.py:65` lehnt den Hostnamen `localhost` ab.

### 3.5 Aufwand und Reihenfolge

| Paket | Inhalt | Aufwand |
|---|---|---|
| R1 | Halle darf Produkte lesen | S |
| R2 | Sales-Router pro Endpunkt absichern | S–M |
| R3 | Rechnungsteil für die Halle ausblenden, Attrappe entschärfen | S |
| R4 | Plattform-Endpunkte für Benutzeranlage, Demo-Login production_staff | S |
| R5 | Selbstverwaltung der Benutzer im Mandanten | L |
| E1 | `send_email` mit mehreren Empfängern, Prüfung, Message-ID | S |
| E2 | Empfänger-Spalten am Kunden und Formular | S |
| E3 | Versandprotokoll, drei Versand-Endpunkte, LS-Versand | M |
| E4 | `SendDocumentDialog` und Anzeige des Protokolls | M |
| E5 | Mahnlauf auf den neuen Mailweg umstellen, `test_dunning.py` anpassen | S (mit Paket 1) |
| L1 | Zweiten Lieferschein je Bestellung sperren (409) oder Sammellauf auf Packlistenmengen umstellen (Risiko 12) | S, **vor** der Freigabe an Mitarbeiter |
| D1 | Demo-Reset migriert nach dem Kopieren (Risiko 11) | S, vor dem ersten Deploy mit E2/E3 oder Paket 1 |

- R1–R3 und L1 direkt nach Paket 1 oder parallel dazu. Sie berühren `main.py`, `sales.py`, `documents.py` und `OrderDocumentsModal.tsx`. Mitarbeiter-Logins (R4) erst vergeben, wenn R1 und L1 live sind. Sonst stößt Gernots Team sofort auf die Saatgut-Liste im Bestellformular (1.3) und kann doppelte Lieferscheine erzeugen.
- Den Betriebsweg aus R4 kann man sofort gehen, sobald Gernot Namen und Adressen liefert.
- E1–E4 bilden B3 und gehören in Paket 3.
- Konflikt beachten: Paket 1 fügt ebenfalls eine Kundenspalte hinzu (Pfand über IFCO-Clearing) und ändert das Kundenformular. E2 deshalb erst auf dem Stand nach Paket 1 bauen.

---

## 4 Risiken

1. **Realmweite Wirkung.** Jede Matrix-Änderung gilt für alle Mandanten der Instanz. Laut Code trifft das fast nur production_staff-Nutzer, also weder Demo- noch Onboarding-Nutzer. Ausnahme ist die DATEV-Sperre aus R2: Sie trifft auch `production_planner`, darunter den Demo-Login paul (3.1). Ob in Produktion weitere existieren, ist eine Annahme: Vor dem Rollout die Liste der production_staff-Nutzer aus Keycloak ziehen.
2. **Master-Admin-Zugang.** Die Benutzeranlage über die Plattform nutzt den Admin des master-Realms (`keycloak_admin.py:52-66`). Ein Fehler in der Mandantenprüfung gäbe Zugriff auf fremde Mandanten. Deshalb R4 nur hinter dem Plattform-Schlüssel, mit fester Rollenliste und Mandantenprüfung vor jeder Änderung. R5 erst mit einem eingeschränkten Service-Account.
3. **Demo-Logins im Live-Mandanten möglich, aber nur für neue Demo-Logins.** `POST /api/v1/platform/demo/seed-users` nimmt `slug` als Parameter (`platform.py:256`). Die vier vorhandenen Demo-Logins sind dabei nicht betroffen. Weil sie schon im Realm stehen, scheitert ihre Anlage mit 409 (`keycloak_admin.py:123-124`). Der Endpunkt meldet sie als „skipped" (`platform.py:273-275`) und legt nichts an. **Annahme:** Die Logins existieren, so steht es in der Betriebsnotiz zur Demo. Gefährlich wird es bei jedem **neu** in `DEMO_USERS` aufgenommenen Login, etwa „Mia" aus R4. Läuft der erste Aufruf versehentlich mit `slug=minga`, entsteht er im Live-Mandanten mit dem bekannten Passwort `demo1234`. Danach scheitert die Anlage für `demo` an der 409. Geschützt ist das nur durch den Plattform-Schlüssel. Empfehlung (S, vor der Erweiterung von `DEMO_USERS`): den Endpunkt fest auf `slug == "demo"` beschränken.
4. **Freie Empfängeradressen.** Mitarbeiter können eine AB samt Preisen an beliebige Adressen schicken. Abmildern lässt sich das durch das Protokoll mit Login. Optional nur hinterlegte Adressen zulassen (Frage F3).
5. **Sichtbare Adressen im To.** Alle Empfänger sehen alle Adressen. Gehört eine Adresse zu einer anderen Organisation (etwa dem externen Buchhaltungsbüro des Kunden), braucht es aus Datenschutzgründen Cc oder eine getrennte Mail.
6. **Teilzustellung.** Der SMTP-Server kann einzelne Empfänger ablehnen, ohne dass die ganze Mail scheitert. Ohne Auswertung (so ist es heute) würde „versendet" angezeigt, obwohl eine Adresse nichts bekommen hat.
7. **GoBD und Nachweis.** PDFs werden bei jedem Abruf neu erzeugt. Ändern sich Vorlage, Firmendaten oder bei AB und LS die Bestellpositionen (1.6), lässt sich das versendete PDF nicht mehr genau reproduzieren. Die Prüfsumme im Protokoll belegt, was verschickt wurde, ersetzt aber keine Archivierung (Frage F7). Falls PDFs gespeichert werden sollen: Die Ablage über `storage_service` liegt außerhalb der SQLite-DB des Mandanten. **Annahme:** Die WAL-Backups erfassen sie nicht. Das ist zu prüfen.
8. **Zwei Mailwege.** Der Mahnlauf nutzt das SMTP aus den Umgebungsvariablen und `customer.email` (`core/email.py`, `invoice_tasks.py:149`). Bis zur Umstellung gehen Mahnungen an andere Adressen als Rechnungen, mit dem Absender aus der Umgebung (`config.py:50-51`). **Annahme, nicht geprüft:** In Produktion ist dieses SMTP nicht gesetzt (Standard `localhost:1025`). Dann scheitern Mahnmails still und die Mahnstufe bleibt stehen.
9. **Paralleländerungen.** Paket 1 und Paket 3 ändern beide die Tabelle `customers` und das Kundenformular. Das gibt Konflikte, also die Reihenfolge einhalten.
10. **E-Rechnung.** **Annahme zur Rechtslage, nicht im Code; vom Steuerberater bestätigen lassen:** Ab 01.01.2027 müssen Unternehmen mit mehr als 800.000 € Vorjahresumsatz inländische B2B-Rechnungen als E-Rechnung (XRechnung oder ZUGFeRD) ausstellen, alle übrigen ab 01.01.2028. Im Code gibt es dafür nichts (grep nach `zugferd|xrechnung|factur-x`: kein Treffer). Der Versandweg aus E1 sollte deshalb mehrere Anhänge tragen können.
11. **Der Demo-Reset spielt das alte Schema zurück (belegt).** Neue Spalten (E2) und die Tabelle `document_dispatches` (E3) entstehen nur beim Start (`main.py:150` → `tenancy.py:240-262`) oder beim Onboarding (`tenancy.py:214-237`). Der nächtliche Reset um 03:30 kopiert aber `demo.seed.db` einfach über `demo.db`, ohne `create_all` und `_auto_migrate` (`services/demo_reset_service.py:58-72`). Ist der Golden Seed älter als der Deploy, fehlen der Demo ab dem ersten Reset die neuen Spalten. Bis zum nächsten Neustart enden dann alle Kundenabfragen mit Fehler 500. Das gilt genauso für die Kundenspalte aus Paket 1. Abhilfe (S): nach dem Kopieren `create_all` und `_auto_migrate` auf die Demo-Engine anwenden oder nach jedem Deploy mit Schemaänderung einen neuen Golden Seed ziehen.
12. **Zweiter Lieferschein, doppelte Rechnung (im Probelauf gemessen).** `create_delivery_note` prüft nicht, ob es zur Bestellung schon einen Lieferschein gibt (`documents.py:185-260`). „Neuer LS" im Belege-Modal hat keine Sperre (`OrderDocumentsModal.tsx:211-218`), anders als der Packlisten-Knopf im Tagesplan (`Tagesplan.tsx:60-61`). Der Sammellauf rechnet je Lieferschein **alle** Bestellpositionen (`invoices.py:548-570`). Probelauf `/tmp/nachtrag_probe2/probe_ls_doppelt.py`: Eine Bestellung über 3 Stück zu je 2,50 € bekam zwei Lieferscheine, beide als `production_staff` angelegt. Die Vorschau des Sammellaufs zeigte 6 Stück und 15,00 € netto statt 7,50 €. Für Mitarbeiter mit dem Recht „Lieferscheine anlegen" reicht ein zweiter Klick auf „Neuer LS", etwa wenn der erste LS schon über die Packliste im Tagesplan entstanden ist. Fachlich gehört das zu „Doppelabrechnung sperren" aus Paket 1. Die Spec beschreibt dort bisher nur den Fall „Rechnung aus Bestellung" plus Sammellauf, nicht zwei Lieferscheine. Bis dahin entweder einen zweiten LS je Bestellung mit 409 sperren oder vor jedem Sammellauf die Vorschau auf „anzahl_lieferscheine" prüfen (F10).

---

## 5 Fragen an Gernot und den Steuerberater

Nur was der Code nicht beantworten kann.

**Gernot**
- F1: Sollen alle Mitarbeiter dieselben Rechte bekommen, oder willst du Hallen-Tablets (nur Tagesplan und Packen) von Mitarbeitern trennen, die Bestellungen und Belege bearbeiten?
- F2: Dürfen Mitarbeiter neue Kunden anlegen oder Kundendaten (Adresse, Ansprechpartner, Liefertage) ändern, oder nur vorhandene Kunden in Bestellungen auswählen?
- F3: Dürfen Mitarbeiter beim Versand selbst Adressen eintippen, oder nur an die beim Kunden hinterlegten Adressen senden?
- F4: Möchtest du von jeder versendeten Rechnung und AB eine Kopie (Bcc) in ein eigenes Postfach bekommen, und wenn ja, in welches?
- F5: Soll der Lieferschein per Mail mit oder ohne Packliste verschickt werden?
- F6: Wer außer dir bekommt einen Login (Name und E-Mail je Mitarbeiter), und soll jemand Vertriebs- oder Buchhaltungsrechte bekommen, mit denen er heute auch Rechnungen sehen und versenden könnte?
- F8: Dürfen Mitarbeiter in Bestellungen Preise ändern, oder sollen sie nur den hinterlegten Preis übernehmen?
- F10: Gibt es zu einer Bestellung je mehr als einen Lieferschein, etwa bei Teillieferungen? Wenn nein, sperren wir den zweiten (Risiko 12). Wenn ja, muss die Sammelrechnung je Lieferschein nur die tatsächlich gelieferten Mengen berechnen.
- F11: Dein ursprünglicher B8-Wunsch war „Profilfelder ergänzen" (Spec, Abweichungen). Welche Felder brauchst du je Mitarbeiter außer Vor- und Nachname und E-Mail (z. B. Telefon, Kürzel auf Belegen)?

**Steuerberater**
- F7: Reicht es, Rechnungen bei Bedarf neu zu erzeugen und im Versandprotokoll Empfänger, Zeitpunkt und Prüfsumme des PDFs festzuhalten, oder muss die versendete PDF-Datei bzw. die Mail selbst unveränderbar archiviert werden?
- F9: Gilt für die MingaGreens GmbH die Pflicht zur E-Rechnung ab 01.01.2027 oder erst ab 01.01.2028 (Umsatz 2026 über oder unter 800.000 €)?
