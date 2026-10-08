# T1 — Bestell-Import legt Zukunftsbestellungen als geliefert an

Stand: erste Fassung gegen `main` @ `c4a1832`. **Geprüft und nachgezogen am 08.10.2026 gegen `main` @ `efcea00`** („fix(import): Zukunftsbestellungen nicht mehr als geliefert anlegen", laut Spezifikation live seit 08.10. 13:56, Spec:63). Keine Repo-Datei geändert, kein Zugriff auf Produktion.

Zeilennummern: ohne Zusatz gilt `c4a1832`. `efcea00` ändert nur `backend/app/api/v1/imports.py`, eine Zeile in `frontend/src/pages/Orders.tsx` (Z. 200) und legt `backend/tests/test_import_bestellungen_zukunft.py` an (`git show --stat efcea00`). Alle anderen Belege gelten in beiden Ständen. Für `imports.py` im neuen Stand steht „@efcea00".

Wie die Aussagen belegt sind:
- **belegt (Code)**: im Quelltext gelesen.
- **belegt (Lauf)**: nachgestellt außerhalb des Repos mit In-Memory-SQLite und der Wurzel-`.venv`. Repro 1: `/tmp/nachtrag/repro/test_t1_repro.py` (gegen `c4a1832`). Repro 2: `/tmp/nachtrag/repro_pruefung/test_t1_pruefung.py` (gegen `efcea00`).
- **belegt (Spec)**: steht in `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md` und wurde dort lesend an Produktion geprüft. Hier nicht nachprüfbar.
- **Annahme**: nicht geprüft, muss gegen Produktion oder mit Gernot geklärt werden.

## Kernbefund

**Ursache (c4a1832):** Der Import kannte nur eine Regel. Bei leerem oder ungültigem Status wurde die Bestellung `GELIEFERT`, mit `actual_delivery_date = lieferdatum`, und zwar unabhängig vom Lieferdatum (`imports.py:547-551`, `:561`).

**Seit `efcea00` behoben (belegt (Code), 6 Tests grün):**
- Leerer Status: Lieferdatum vor heute (Europe/Berlin) → `GELIEFERT`, sonst `BESTAETIGT` mit `confirmed_delivery_date` (`imports.py@efcea00:42-43`, `:554-561`, `:586-595`).
- `GELIEFERT` oder `FAKTURIERT` mit Zukunftsdatum → 400, der ganze Lauf wird zurückgerollt (`:568-576`, `:790-792`).
- Der Knopf heißt jetzt „Bestellungen importieren" (`Orders.tsx:200`). Vorlage und Hinweistext zeigen auch den Zukunftsfall (`imports.py@efcea00:245`, `:256-261`).

**Datenkorrektur der zwei Zukunftsbestellungen: erledigt** (belegt (Spec), Spec:61-62). Betroffen waren BE-20261008-0004 (Großer Kern, 10.10.) und BE-20261011-0001 (Fruchthof Nagel, 12.10.). Beide stehen jetzt auf `BESTAETIGT`, `actual_delivery_date` ist leer, je ein Audit-Eintrag „Import-Korrektur" existiert, und beide erscheinen im Tagesplan. Damit ist die Bedingung aus 1.5 erfüllt. Der frühere „Eilt"-Hinweis und das Korrekturskript sind überholt (3.4).

**Zählung aufgelöst:** 49 = 46 rückdatiert + 1 mit Lieferdatum 08.10. (Klara Düran) + 2 Zukunft (belegt (Spec), Spec:61).

**Was offen bleibt:**
1. Import-Lücken, die `efcea00` nicht schließt (belegt (Lauf), Repro 2, Abschnitt 1.1):
   - Eine Bestellung mit Lieferdatum heute bekommt keinen Packtag und fehlt deshalb in „Verpacken".
   - Ungültige Statuswerte laufen still durch die Datumsregel.
   - Bei Zeilenfehlern entsteht ein Teilimport: Die Bestellung wird ohne die fehlerhafte Position angelegt, und ein erneuter Upload überspringt sie.
   - Das Bestelldatum wird nicht auf Plausibilität geprüft.
   - Eine leere Einheit wird zu `g`.
   - Es fehlen Adress-Schnappschuss, `created_by` und Audit-Eintrag.
2. Abrechnung der **47** GELIEFERT-Bestellungen ohne Lieferschein (46 + Klara Düran). Der Sammellauf erfasst sie nicht.
3. Nachprüfung der zwei korrigierten Bestellungen: Lieferadresse auf dem Lieferschein, Packtag Sonntag 11.10., Bestelldatum 11.10. in der Zukunft.

---

## 1. Ist-Zustand (belegt)

### 1.1 Der Importweg

| Schritt | Stelle |
|---|---|
| Knopf auf der Bestellseite, Entity `order_history`; Text bis c4a1832 „Historie importieren", seit efcea00 „Bestellungen importieren" | `frontend/src/pages/Orders.tsx:198-203`, `:200` |
| Der Knopf wird ohne Rollenprüfung gerendert. Die Bestellseite ist auch für die Halle sichtbar | `Orders.tsx:198-203`, `frontend/src/components/common/Layout.tsx:187-189` |
| Komponente: Upload direkt per Dateiauswahl, keine Vorschau. Toast „x angelegt · y übersprungen", bei Zeilenfehlern rot mit max. 3 Fehlerzeilen | `frontend/src/components/common/ExcelImport.tsx:43-72`, `:59-61` |
| Endpunkt `POST /api/v1/imports/{entity}`, ohne `CurrentUser` | `backend/app/api/v1/imports.py:745-761` (`@efcea00:779-796`) |
| Rechte: Import-Router = `_deps_vertrieb` (Sales, Buchhaltung, Planung, Admin). **Nicht** die Halle. Ein Halle-Login bekommt beim Klick 403 | `backend/app/main.py:124`, `:788-792` |
| Spalte `status` optional, Typ `enum:ENTWURF\|…\|STORNIERT` | `imports.py:117` |
| Ungültige Enum-Werte werden stumm zu `None`. Groß-/Kleinschreibung egal, Umlaut nicht („Bestätigt" ≠ `BESTAETIGT`) | `imports.py:175-178` |
| c4a1832: `status_str = head.get("status") or "GELIEFERT"`. efcea00: leer → Datumsregel. Der `ValueError`-Zweig bleibt in beiden Ständen toter Code, weil `_coerce` vorher filtert | `imports.py:547-551`; `@efcea00:555-566` |
| `actual_delivery_date`: c4a1832 bei GELIEFERT ohne Datumsvergleich. efcea00: bei GELIEFERT/FAKTURIERT, und Zukunft wird abgelehnt | `imports.py:561`; `@efcea00:568-576`, `:591-595` |
| Die Bestellung entsteht ohne `billing_address`/`delivery_address`, `packing_date` und `created_by`. `confirmed_delivery_date` setzt erst efcea00 (bei BESTAETIGT/IN_PRODUKTION) | `imports.py:555-569`; `@efcea00:580-603` |
| Bestellnummer `BE-<bestelldatum>-NNNN`. Das Bestelldatum wird nicht geprüft, auch nicht auf „nach dem Lieferdatum" oder „in der Zukunft" | `imports.py:457-480`, `:553` |
| Einheit leer → `"g"` (auch nach efcea00) | `imports.py:617`; `@efcea00:651` |
| Preis immer aus der Datei (Pflichtspalte) | `imports.py:116`, `:618` |
| Steuersatz aus dem **Produktstamm** | `imports.py:620` |
| Kein Audit-Eintrag, kein Forecast-Trigger, keine Lagerbuchung | `imports.py:483-631` |
| **Kein** „alles oder nichts": Zeilen mit fehlender oder unlesbarer Pflichtspalte werden schon beim Parsen verworfen, der Rest wird importiert und committet. Nur Fehler im Importer selbst (unbekannter Kunde/SKU, efcea00 auch GELIEFERT+Zukunft) brechen den ganzen Lauf ab | `imports.py:350-357`, `:751-761`; `@efcea00:357-364`, `:785-796` |
| Idempotenz über `customer_reference == bestell_nr_extern`, je Bestellung (nicht je Position) und über **alle** Kunden | `imports.py:531-537` (`@efcea00:538-544`) |
| Docstring „Importiert historische Bestellungen für Forecast-Training" | `imports.py:484` |

**Belegt (Lauf), Repro 1 gegen c4a1832** (heute = 08.10.):
```
ORDER ALT-1 GELIEFERT actual= 2026-09-19 confirmed= None unit= g delivery_address= None created_by= None
ORDER NEU-1 GELIEFERT actual= 2026-10-10 confirmed= None unit= g delivery_address= None created_by= None
ORDER NEU-2 GELIEFERT actual= 2026-10-10 confirmed= None unit= STK ...   <- Datei: status "Bestätigt"
DAYPLAN 200 verpacken= []
ADD_LINE 400 'Positionen können nicht hinzugefügt werden bei Status GELIEFERT'
STATUS->BESTAETIGT 400 'Ungültiger Statusübergang: GELIEFERT → BESTAETIGT'
AUDIT []
```

**Belegt (Lauf), Repro 2 gegen efcea00** (heute = 08.10.):
```
IMPORT 200 {'created': 6, 'updated': 0, 'errors': ["Zeile 6: 'einzelpreis' fehlt"]}
ORDER BESTELL-ZUKUNFT BE-20261011-0001 BESTAETIGT ... lines= 1      <- Bestelldatum 11.10. > Lieferdatum 10.10., angenommen
ORDER GEL-HEUTE  BE-20261008-0004 GELIEFERT actual= 2026-10-08 ...  <- Datei: GELIEFERT, Lieferdatum heute
ORDER HEUTE      BE-20261008-0001 BESTAETIGT confirmed= 2026-10-08 packing= None eff_packing= 2026-10-07
ORDER OFFEN-NEU  BE-20261008-0002 BESTAETIGT ... unit= ['g']        <- Datei: status "offen", Einheit leer
ORDER UMLAUT-ALT BE-20261003-0001 GELIEFERT actual= 2026-10-04      <- Datei: "Bestätigt", Lieferdatum vergangen
ORDER ZWEI-POS   BE-20261008-0003 BESTAETIGT ... lines= 1           <- Datei: 2 Zeilen, 2. ohne Preis
DAYPLAN heute verpacken= [] ausliefern= ['BE-20261008-0001']
```

### 1.2 Folgen für eine Zukunftsbestellung mit Status GELIEFERT (Stand c4a1832; seit efcea00 nur noch Altbestand)

- **Tagesplan/Packplan:** Geladen werden nur `ENTWURF, BESTAETIGT, IN_PRODUKTION` (`production.py:515-526`, `:523`; Packplan `:662-677`, `:673`). Die Bestellung fehlt also in „Verpacken" und „Ausliefern" (`:548-549`).
- **Bearbeiten:**
  - „Position hinzufügen" ist im Frontend nur bei ENTWURF/BESTAETIGT zu sehen (`EditOrderModal.tsx:151`, `:315`, `:348-350`). Das Backend lehnt es ebenfalls ab (`sales.py:1310-1314`).
  - Menge und Preis vorhandener Zeilen lassen sich dagegen ändern, auch **im Dialog**: gesperrt ist nur bei STORNIERT (`EditOrderModal.tsx:152`, `:307-309`). `PATCH …/lines/{id}` prüft keinen Status (`sales.py:1392-1442`).
  - Löschen geht ebenfalls, solange mehr als eine Zeile bleibt (`sales.py:1472-1520`, `:1494`).
- **Stornieren:** Im UI nicht möglich (`EditOrderModal.tsx:151`, `:354`). Der Status-Endpunkt erlaubt nur `GELIEFERT → FAKTURIERT` (`sales.py:1198-1205`).
- **Rückweg per UI:** gibt es nicht. `PATCH /orders/{id}` kennt weder `status` noch `actual_delivery_date` (`schemas/order.py:153-164`). Er kennt aber `confirmed_delivery_date`, `packing_date`, `billing_address` und `delivery_address` (`:160-163`). Der Bearbeiten-Dialog sendet davon **nichts**, nur Lieferdatum, Referenz und Notiz (`EditOrderModal.tsx:180-188`). Einen Packtag gibt es nur im Anlege-Dialog (`CreateOrderModal.tsx:187`).
- **Belege (AB und LS teilen `_build_document`, `pdf_service.py:437`, `:741`, `:834`):**
  - „Lieferadresse" steht nur auf dem Beleg, wenn der Adress-Schnappschuss existiert (`pdf_service.py:489-497`). Der Import legt keinen an.
  - „Datum:" ist das **Bestelldatum** (`pdf_service.py:480`). Bei BE-20261011-0001 steht dort also der 11.10.2026 (Bestelldatum laut Nummer in der Zukunft, Annahme aus der Nummernlogik `imports.py:467`).
  - `customer_reference` erscheint als „Auftragsnummer" (`:487-488`).
  - Die Positionen des LS kommen live aus `order.lines` (`:759`). Die Packliste ist dagegen ein Schnappschuss vom Anlegen des LS (`documents.py:226-256`).
- **Lager:** Der Import bucht nichts ab. Das spätere Quittieren bucht ebenfalls nichts ab, solange `actual_delivery_date` gesetzt ist (siehe 1.5).

### 1.3 Frage (1): Was der normale Weg zusätzlich tut — und was eine Zukunftsbestellung davon braucht

Normaler Weg = `create_order` (`sales.py:817-1054`) + `confirm_order` (`sales.py:1118-1171`); das Frontend bestätigt über `/confirm` (`Orders.tsx:80`, `api.ts:374-382`).

| Aspekt | Normaler Weg | Import (efcea00) | Braucht eine importierte Zukunftsbestellung das? |
|---|---|---|---|
| Kunde aktiv | Abbruch bei deaktiviertem Kunden `sales.py:830-831` | keine Prüfung | **Ja**, als Fehler |
| Kreditlimit | Summe offener Bestellungen (ENTWURF/BESTAETIGT/IN_PRODUKTION) + neue > Limit → 400 `sales.py:833-863` | keine Prüfung | **Als Warnung**, nicht als Sperre. Die Bestellungen sind beim Kunden schon zugesagt. Nach dem Import zählen sie aber für das Limit (Risiko 4.2) |
| Bestellnummer | `BE-<heute>-NNNN` `sales.py:592-616` | `BE-<bestelldatum>-NNNN` `imports.py:457-480` | Format in Ordnung. Es **fehlt** eine Plausibilität: Bestelldatum ≤ heute und ≤ Lieferdatum. Sonst trägt die Nummer ein künftiges Datum, und AB/LS zeigen es als „Datum" (1.2) |
| Adress-Schnappschuss | Rechnungs- und Lieferadresse vom Kunden inkl. Adresszusatz `sales.py:879-901` | fehlt | **Ja**, sonst fehlt die Lieferadresse auf LS und AB (1.2) |
| Packtag | `Order.resolve_packing_date` `sales.py:905-907`, `order.py:176-189` | fehlt auch nach efcea00 | **Ja** für Lieferdatum = heute: Ohne den Wert läge der Packtag gestern, die Bestellung fiele aus „Verpacken". Belegt (Lauf), Repro 2: `verpacken= []`, `ausliefern= ['BE-20261008-0001']` |
| Startstatus | `ENTWURF` `sales.py:919` | Datei oder Datumsregel | umgesetzt (3.1) |
| `created_by` | Benutzer `sales.py:921` | `None` | **Ja**, damit nachvollziehbar ist, wer importiert hat |
| Preis / Sonderpreis | Ein mitgeschickter Preis ist verbindlich, sonst Kundenpreis zum heutigen Datum, sonst Basispreis; Varianten-Override `sales.py:934-988`, `pricing_service.py:47-59` | Preis immer aus der Datei | Optional: leere Preisspalte → gleicher Lookup; Abweichung vom Sonderpreis → Warnung |
| Steuersatz | Satz der Position, Default `REDUZIERT` `sales.py:1028`; das Formular sendet fest `REDUZIERT` (Spec A3) | **Produktsatz** `imports.py:620` | Hier ist der Import sogar korrekter. Nach Paket 1 sind beide Wege gleich |
| Verpackungsvariante | `product_variant_id`, Einheit aus `packaging_unit` `sales.py:966-988` | nicht ausdrückbar | Annahme: nur nötig, wenn Gernot Varianten nutzt |
| Variables Bundle | Auswahl Pflicht, Slot-Grenzen geprüft `sales.py:990-1016` | nur SKU-Auflösung, keine Pflicht, keine Grenzen `imports.py:583-608` | **Ja**, sonst fällt die Sortenauswahl im Packplan heraus (Spec B1) |
| Menge > 0, Preis ≥ 0 | Schema `schemas/order.py:32-34` | keine Prüfung | **Ja** |
| Einheit | Formular-Default `STK` („es wird aktuell nichts abgewogen verkauft") `CreateOrderModal.tsx:81-82` | Default `g`, keine Prüfung `imports.py:617` | **Ja**. Bei `g` stehen „12 g" auf Lieferschein und Rechnung, und der Lagerabzug rechnet in Gramm (`order_fulfillment_service.py:49-54`) |
| Bestätigen | Status BESTAETIGT, `confirmed_delivery_date`, Audit `CONFIRM`, Forecast-Trigger `sales.py:1152-1169` | Status und `confirmed_delivery_date` seit efcea00, kein Audit | Audit fehlt noch (als `IMPORT`). `confirmed_delivery_date` wirkt nur als Antwortfeld (`sales.py:777`, sonst kein Leser im Code) |
| Auftragsbestätigung | **nicht** automatisch, nur manuell über `OrderDocumentsModal` → `documents.py:73-97` | — | Nein. Der Kunde hat im Altsystem schon bestätigt; eine AB-Mail würde verwirren |
| Produktionsvorschläge | entstehen nur aus Forecasts (`forecasting.py:792ff`), nicht aus dem Bestätigen | — | Nein |
| Lagerreservierung | `reserve_for_order` ist definiert (`inventory_service.py:229`), wird aber **nirgends aufgerufen** (grep) | — | Nein, der normale Weg macht das auch nicht |
| Lagerabzug | nur beim Übergang auf GELIEFERT (`sales.py:1229-1247`, `documents.py:304-321`) | — | Nicht beim Import. Später beim Quittieren, und dafür muss `actual_delivery_date` leer sein |
| Forecast | `_trigger_forecast_update` fire-and-forget `sales.py:40-46`, `:1052`, `:1169` | — | Nein. Die Forecast-Engine filtert auf `OrderLine.seed_id` (`forecast_engine.py:33-35`, ebenso `forecast_tasks.py:196-200`), und **weder** `create_order` (`sales.py:1018-1031`) **noch** der Import (`imports.py:610-622`) setzen `seed_id`. Der Trigger bleibt also auf beiden Wegen ohne Wirkung |

### 1.4 Frage (4): Die GELIEFERT-Bestellungen ohne Lieferschein (46 rückdatiert + 1 vom 08.10.)

- **Anzahl:** 47 statt 46. Die Bestellung von Klara Düran (Lieferdatum 08.10.) steht ebenfalls auf GELIEFERT und hat keinen Lieferschein (belegt (Spec), Spec:61; „ohne LS" ist eine Annahme, weil die Spec das nur für die 46 sagt, Spec:64).
- **Sammellauf erfasst sie nicht.** Die Auswahl läuft ausschließlich über `delivery_notes` mit `invoice_id IS NULL` (`invoices.py:521-545`, `:528-535`). Belegt (Lauf): Die Vorschau über die letzten 40 Tage liefert `kunden: []`.
- **Rechnung „aus Bestellung":**
  - Funktioniert auch für GELIEFERT-Importe (`invoices.py:130-140`, `invoice_service.py:177-216`). `delivery_date` = Lieferdatum (`:189`).
  - Es gibt **keine** Statusprüfung, und der Code setzt nirgends `order.invoice_id` oder `FAKTURIERT` (grep: keine Zuweisung). Belegt (Lauf): `RE-2026-00001`, die Bestellung bleibt `GELIEFERT` mit `invoice_id None`.
  - Damit fehlt jeder Schutz gegen Doppelabrechnung (Spec, Sofortmaßnahme 3).
- **Nachträglicher Lieferschein:** Möglich, `create_delivery_note` prüft keinen Status (`documents.py:185-261`). Die LS-Nummer trägt das **heutige** Datum (`:200-203`, belegt (Lauf): `LS-20261008-0003`).
  - Unquittiert: Leistungsdatum = Lieferdatum der Bestellung (`invoices.py:539`). Die Bestellung erscheint im Sammellauf ihres Zeitraums (belegt (Lauf)).
  - Quittiert **ohne** Datum: Das LS-Datum wird **heute** (`documents.py:294`), und die Bestellung rutscht aus dem September-Lauf (belegt (Lauf)).
  - Quittiert **mit** `actual_delivery_date = Lieferdatum`: Das Leistungsdatum stimmt. Weil `order.actual_delivery_date` schon gesetzt ist, ändern sich weder Status noch Lager (`documents.py:296-300`). Für die Historie ist das erwünscht.
  - **Genau ein LS je Bestellung.** Der Sammellauf zählt **je Lieferschein alle Positionen der Bestellung** (`invoices.py:555-569`). Zwei LS zu einer Bestellung rechnen sie doppelt ab. Belegt (Lauf), Repro 2: Bestellung mit Menge 2 und zwei LS → Vorschau `anzahl_lieferscheine 2`, Menge `4.0`.
- **Pfand:** Der Sammellauf summiert **alle** Positionen der Bestellung, Pfand eingeschlossen (`invoices.py:564-569`). Gernot hat zu B4 zwei Wege genannt und fragt nach unserer Einschätzung (Spec:109): (a) je Kunde „Pfand von Rechnung ausnehmen" (Ökoring ja, Knuspr nein), entspricht `pfand_via_clearing` in Paket 1; (b) Pfand nie auf der Lieferrechnung, dafür eine monatliche Pfand-Sammelrechnung mit Eingabemaske für Pfandretouren. Bis eine der beiden Varianten live ist, käme Pfand auch für Ökoring auf die Sammelrechnung. Ob die Importdatei Pfandzeilen enthält: Annahme, read-only prüfbar (3.4).
- **Umsatz-Analytics:** Rechnungsbasiert, nur OFFEN/BEZAHLT, nach `invoice_date` (`analytics.py:28-38`). Die 47 tauchen erst mit einer Rechnung auf, und zwar im Monat des Rechnungsdatums (Sammellauf: `invoice_date` oder heute, `invoices.py:606`).
- **Vertriebsseite „Umsatz (geliefert)":** Summiert alle **geladenen** GELIEFERT-Bestellungen (`Sales.tsx:127-135`, `:182-183`). Die 47 fließen dort ein. Die zwei Zukunftsbestellungen seit der Korrektur nicht mehr.
- **Forecast:** Unabhängig vom Status unsichtbar (1.3, `seed_id`). Der Docstring-Zweck „für Forecast-Training" (`imports.py:484`) wird nicht erreicht.
- **Kreditlimit/„OFFEN"-Filter:** GELIEFERT zählt nicht als offen (`sales.py:840-842`, `:690-691`).

**Wie Gernot die 47 abrechnen könnte, falls das Altsystem sie noch nicht berechnet hat** (erst nach Paket 1, Sofortmaßnahme 3):
1. Je Bestellung **genau einen** Lieferschein anlegen und ihn **mit** `actual_delivery_date = Lieferdatum` quittieren. Das geht per Skript über die API, sonst 47 × UI. Lieferscheine darf laut Matrix auch die Halle anlegen (`main.py:129`, `_deps_belege`). Den Sammellauf dürfen nur Sales, Buchhaltung und Admin (`main.py:125`, `:740-744`); das passt zu B8 („Rechnungen bleiben beim Admin").
2. Passend zu Gernots Antwort zu B5 („monatlich fix") werden keine eigenen Teilzeiträume gebildet:
   - **September:** ein Lauf 01.–30.09. Er erfasst die Lieferungen ab 16.09.
   - **Oktober:** Die Lieferungen 01.–08.10. laufen im regulären Oktober-Lauf am Monatsende mit, zusammen mit allen neuen Lieferscheinen.
   - Ein Extra-Lauf „01.–07.10." würde eine zweite Oktober-Rechnung je Kunde erzeugen.
3. **Nicht** über „Rechnung aus Bestellung": keine Verknüpfung, und ein späterer Lieferschein würde doppelt abrechnen.

**Falls das Altsystem sie schon berechnet hat:** Die Bestellungen auf `FAKTURIERT` setzen. Der Status-Endpunkt erlaubt `GELIEFERT → FAKTURIERT` mit Audit-Eintrag (`sales.py:1202`, `:1217-1224`). Zusätzlich muss Paket 1 („Doppelabrechnung sperren") den Sammellauf auf `FAKTURIERT` prüfen; heute schließt er nur `STORNIERT` aus (`invoices.py:533`). Sonst würde jeder später angelegte Lieferschein die Ware nochmals berechnen. Das gilt auch, falls die Pfand-Sammelrechnung aus B4 (b) auf Lieferscheinen aufsetzt (Annahme, Bauweise offen).

### 1.5 Frage (5): Folgeobjekte und warum `actual_delivery_date` geleert werden muss

`mark_delivered` übernimmt Status und Lagerabzug nur, wenn `order.actual_delivery_date` leer ist (`documents.py:296-300`, `:304-321`). Belegt (Lauf):
```
Z-A (nur Status zurück, actual bleibt): LS quittiert -> Order-Status BESTAETIGT, inventory_deducted_at None
Z-B (Status zurück + actual NULL):      LS quittiert -> Order-Status GELIEFERT,  inventory_deducted_at gesetzt
```
Bei Z-A bliebe die Bestellung für immer im Tagesplan, und die Ware würde nie abgebucht. Die Produktionskorrektur vom 08.10. hat `actual_delivery_date` geleert (belegt (Spec), Spec:62), entspricht also Z-B.

### 1.6 Frage (6): Bestehende Tests zum Import

| Test | Was er festschreibt | Betroffen von weiteren Änderungen? |
|---|---|---|
| `backend/tests/test_gernot_260821.py:38-53` | Beispielblatt existiert; jede Pflichtspalte ist in der **ersten** Beispielzeile gefüllt | Nein. Neue Beispielzeilen müssen alle Pflichtspalten füllen |
| `:55-59` | Erstes Blatt heißt „Daten" und ist aktiv | Nein |
| `:62-69` | Ein unverändertes Template importiert 0 Zeilen (inkl. `order_history`) und liefert `errors == []` | Nein. Eine neue Typzeile wie `[orderstatus]` beginnt mit „[" und wird übersprungen (`imports.py:340`) |
| `:71-84`, `:86-101` | Beispielblatt wird nie gelesen; altes Einblatt-Template (nur `customers`) | Nein |
| **neu (efcea00)** `backend/tests/test_import_bestellungen_zukunft.py:90-123` | Leer + Zukunft → BESTAETIGT, `confirmed_delivery_date`, im Tagesplan „Verpacken", `POST …/lines` → 201 | — |
| `:126-141` | Leer + Vergangenheit → GELIEFERT mit `actual_delivery_date` | — |
| `:144-159` | Leer + heute → BESTAETIGT. Prüft **nicht** den Tagesplan; der Packtag-Fehler (1.3) bleibt dadurch unentdeckt | Ja, ergänzen (3.5) |
| `:162-184` | GELIEFERT + Zukunft → 400, auch die gültige Nachbarbestellung wird nicht angelegt | — |
| `:187-202` | Ausdrücklich BESTAETIGT in der Vergangenheit bleibt BESTAETIGT, ohne Warnung | Ja, falls eine Warnung kommt (Antwortformat) |
| `:205-221` | Beispielblatt enthält eine Zukunftszeile mit leerem Status | — |
| `frontend/tests/e2e/import-upload.spec.ts:68-84` | Upload geht als multipart raus, kaputte Datei → 400 + Alert; nutzt das erste `input[type=file]` der Seite | **Ja**, falls der Upload in einen Dialog wandert |
| `:97-106` | Template-Knopf „Template", Dateiname `template_order_history.xlsx`. Die Umbenennung in efcea00 betrifft den Test nicht | Ja, falls Knopf oder Dateiname umbenannt werden |

Belegt (Lauf) gegen efcea00: `pytest tests/test_import_bestellungen_zukunft.py tests/test_gernot_260821.py -k "…TestImportTemplates…"` → 25 passed (19 + 6). **Kein** Test prüft Einheit, Packtag bei „heute", Teilimport, ungültige Statuswerte oder den Adress-Schnappschuss.

---

## 2. Lücken

Stand efcea00. „Geschlossen" heißt: im Code behoben und durch Tests abgedeckt.

1. ~~Statusregel ohne Datumsbezug~~ **geschlossen** (efcea00). **Offen:** Ungültige Werte („offen", „Bestätigt") werden still nach der Datumsregel behandelt statt als Fehler gemeldet (belegt (Lauf), Repro 2).
2. ~~Widerspruch „GELIEFERT + Zukunftsdatum"~~ **geschlossen** (efcea00).
3. Es fehlen gegenüber `create_order` noch: Adress-Schnappschuss, **Packtag (Same-Day fällt aus „Verpacken")**, `created_by` und die Prüfungen (Kunde aktiv, Menge, Preis, variables Bundle). Ebenso der Kreditlimit-Hinweis und die Plausibilität des Bestelldatums. `confirmed_delivery_date` ist seit efcea00 gesetzt.
4. Einheit `g` als Default, das Formular nimmt `STK`.
5. Kein Audit, kein Import-Lauf, kein Rollback. Importierte Bestellungen sind nur über `created_by IS NULL` + `customer_reference` erkennbar. Shopify-Bestellungen erfüllen das auch (`shopify_service.py:193-200`); siehe Abgrenzung in 3.4.
6. Keine Vorschau. Das Ergebnis sagt nicht, was als „geliefert" und was als „offen" angelegt wurde.
7. ~~Benennung „Historie importieren", Vorlage nur GELIEFERT~~ **geschlossen** (efcea00). **Offen:** Der Hinweistext sagt „heute oder später = BESTAETIGT (erscheint im Tagesplan)" (`imports.py@efcea00:259-260`). Für „heute" stimmt das nur für „Ausliefern" (1.3).
8. `customer_reference` ist zugleich Idempotenzschlüssel **und** Kundenbestellnummer, die als „Auftragsnummer" auf AB und LS steht. Eine echte Kunden-PO oder Shopify-Referenz mit derselben Nummer führt dazu, dass die Bestellung beim Import still übersprungen wird.
9. Kein UI-Weg zurück von GELIEFERT. Der einzige API-Weg ist `POST /sales/orders/bulk-status` (`sales.py:1544-1585`):
   - Er prüft **keine** Übergänge, setzt `actual_delivery_date` nicht zurück und bucht nichts.
   - Er ist für alle Rollen von `_deps_auftraege` erreichbar, **auch die Halle** (`main.py:119-122`, `:701-706`).
   - Das Frontend nutzt ihn nicht (grep).
   - Nebenbefund: Die Halle hat diese Rechte schon seit 03.09.; mit echten Mitarbeiter-Logins aus B8 (Benutzerverwaltung bisher Attrappe, Spec:30) gibt es mehr Konten, die ihn erreichen.
10. **Neu: Teilimport.** Eine Zeile mit fehlender oder unlesbarer Pflichtspalte (Preis, Datum, Menge) wird verworfen, die übrigen Zeilen derselben Bestellung werden angelegt (`imports.py:350-357`; belegt (Lauf), Repro 2: `ZWEI-POS` mit 1 von 2 Positionen, HTTP 200). Korrigiert Gernot die Zeile und lädt erneut hoch, überspringt die Idempotenz die ganze Bestellung (`imports.py:531-537`). Die Position kommt dann nie an.
11. **Neu: Bestelldatum ohne Prüfung.** Ein künftiges Bestelldatum oder eines nach dem Lieferdatum wird angenommen (belegt (Lauf), Repro 2: `BE-20261011-0001`). Produktion hat genau diesen Fall: BE-20261011-0001 (Fruchthof Nagel) trägt laut Nummer das Bestelldatum 11.10. (belegt (Spec), Spec:61; Ableitung aus `imports.py:467`).
12. **Neu: Halle sieht den Import-Knopf, darf aber nicht importieren** (`Layout.tsx:187-189`, `Orders.tsx:198-203` gegen `main.py:788-792`). Nach B8 („Mitarbeiter legen Bestellungen an") ist das eine 403-Falle.
13. **Neu (Nebenbefund für Paket 1):** Zwei Lieferscheine zu einer Bestellung → doppelte Menge im Sammellauf (`invoices.py:555-569`; belegt (Lauf)). Relevant für die 10.10.-Bestellung, zu der schon ein LS existiert (3.4).
14. **Nebenbefund Rollen:** Der Import-Router hängt geschlossen an `_deps_vertrieb`. Sales und Buchhaltung können damit Saatgut, Lieferanten und Produkte per Excel schreiben, obwohl Stammdaten sonst nur die Planung schreibt (`main.py:112`, `:124`, `:788-792`).

---

## 3. Vorschlag

### 3.1 Frage (2): Statusregel bei fehlender Spalte — **umgesetzt in efcea00**

Umgesetzt (belegt (Code), `imports.py@efcea00:554-576`): Lieferdatum **< heute (Europe/Berlin)** → `GELIEFERT` mit `actual_delivery_date`. Lieferdatum **≥ heute** → `BESTAETIGT` mit `confirmed_delivery_date`. Die Entscheidung BESTAETIGT statt ENTWURF ist freigegeben (Spec:63).

Begründung bleibt gültig: Bestätigen löst nur aus (`sales.py:1152-1169`):
- Status BESTAETIGT,
- bestätigtes Lieferdatum,
- Audit-Eintrag,
- einen wirkungslosen Forecast-Trigger.

Keine Mail, keine AB, keine Reservierung, keine Lagerbuchung (1.3). BESTAETIGT beim Import ist damit gleichwertig zu einem späteren Klick. Dafür erscheint die Bestellung ohne Zusatzschritt im Tagesplan und bleibt bearbeitbar und stornierbar.

**Noch offen gegenüber dem Vorschlag:**

| Fall | efcea00 | Vorschlag |
|---|---|---|
| leer, Lieferdatum = heute | BESTAETIGT, **kein Packtag** → fehlt in „Verpacken" | `packing_date = Order.resolve_packing_date(lieferdatum, None)` (`order.py:176-189`). Achtung: Die Methode nutzt `date.today()` (Serverzeit, `order.py:186`), die Statusregel dagegen Europe/Berlin. Für den Import das Berliner Datum übergeben bzw. die Methode angleichen |
| `GELIEFERT`/`FAKTURIERT`, Lieferdatum > heute | 400, Lauf zurückgerollt | erledigt |
| `GELIEFERT`, Lieferdatum = heute | erlaubt, still | Warnung „Bestand wird nicht abgebucht, kein Lieferschein" |
| `ENTWURF`/`BESTAETIGT`/`IN_PRODUKTION`, Lieferdatum < heute | erlaubt, still (Test `:187-202`) | Warnung „offene Bestellung in der Vergangenheit — erscheint in keinem Tagesplan, zählt aufs Kreditlimit" |
| ungültiger Wert („offen", „xyz") | still → Datumsregel | **Zeilenfehler** |
| UI-Bezeichnungen mit Umlaut („Bestätigt", „In Produktion", „Geliefert"; vgl. `Orders.tsx:29-37`) | still → Datumsregel | auf die Enum-Werte abbilden |

### 3.2 Frage (3): Benennung und Hinweise

- **Knopf:** erledigt („Bestellungen importieren", `Orders.tsx:200`). **Offen:** Der Toast nennt die Aufteilung nicht. Vorschlag: „46 als geliefert (ohne Lieferschein, nicht im Sammellauf) · 2 als bestätigt (im Tagesplan) · 0 übersprungen". Zusätzlich den Knopf für reine Halle-Logins ausblenden (Lücke 12), solange der Import beim Vertrieb bleibt.
- **Vorlage:** erledigt, `EXT-1002` liegt jetzt in der Zukunft mit leerem Status (`imports.py@efcea00:245`). Optional die beiden GELIEFERT-Zeilen ebenfalls mit leerem Status zeigen, damit die Regel sichtbar wird.
- **Hinweistext:** teilweise erledigt (`imports.py@efcea00:256-261`). Ergänzen:
  - „Geliefert = ohne Lagerabzug, ohne Lieferschein, nicht im Sammellauf."
  - „Gültige Status-Werte: ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT."
  - „Einheit leer = STK" (erst nach der Code-Änderung).
  - „Eine Bestellung mit fehlerhafter Zeile wird nicht angelegt" (erst nach Lücke 10).
- **Docstrings** angleichen: `imports.py:1-8` (`order_history` und `grow_batches` fehlen in der Liste) und `:484` („Forecast-Training", siehe 1.4).

### 3.3 Datenmodell, Endpunkte, Oberfläche

**Stufe A — Rest im bestehenden Import (S, ca. ½–1 Tag; Statusregel ist erledigt)**
- **Packtag** bei Lieferdatum ≤ heute setzen (3.1). Das ist der einzige verbliebene Punkt, an dem eine importierte offene Bestellung im Tagesplan fehlt.
- **Teilimport verhindern:**
  - Hat eine Zeile einer `bestell_nr_extern` einen Parse-Fehler, wird die ganze Bestellung nicht angelegt und als Fehler gemeldet.
  - Alternative: Bei Parse-Fehlern bricht der Lauf komplett ab (wie bei unbekanntem Kunden).
  - `_parse_rows` (`imports.py:317-358`) wird auch von den Stammdaten-Importen genutzt. Die Änderung gehört deshalb in `_import_order_history` bzw. `import_entity` für `order_history`, nicht in den gemeinsamen Parser.
- **Status roh lesen**, damit „leer" und „ungültig" unterscheidbar sind. Dafür ein eigener Typ `orderstatus` statt `enum:` in `COLUMNS`. Die Typzeile der Vorlage zeigt dann `[orderstatus]` statt der Werteliste; die Werte stehen deshalb im Hinweistext (3.2). Test `:62-69` bleibt grün (Zeile beginnt mit „[").
- Adress-Schnappschuss: die Logik aus `sales.py:879-901` in einen Helfer ziehen und von beiden Wegen nutzen.
- `import_entity` bekommt `user: CurrentUser` und setzt `created_by`. Dazu je Bestellung ein `OrderAuditLog(action="IMPORT", new_values={status, datei, bestell_nr_extern})`.
- Prüfungen:
  - Kunde aktiv, Menge > 0, Preis ≥ 0.
  - Bestelldatum ≤ heute und ≤ Lieferdatum.
  - Variables Bundle mit Auswahl und Slot-Grenzen (nur für Bestellungen ab heute).
  - Einheit leer → `STK`. Unbekannte Einheit → Warnung (Liste wie im Formular, `EditOrderModal.tsx:330-334`, plus `units_of_measure`).
- Kreditlimit: nur Warnung.
- Antwort rückwärtskompatibel erweitern: `{created, updated, errors, warnings, status_counts}`. `ExcelImport.tsx:56-64` zeigt `warnings` und die Aufteilung an.
- Frontend: Import-Knopf nur für Rollen mit Schreibrecht auf `/imports` rendern (Lücke 12).

**Stufe B — Zweistufiger Import mit Vorschau und Rollback (M, 1,5–2 Tage)**

Gleiches Muster wie der Chargen-Import v2 (`imports.py:764-1244`, `models/import_run.py:21-43`):
- `POST /imports/order-history/validate`: schreibt nichts. Liefert einen Report je Bestellung mit Kunde, Lieferdatum, **vorgeschlagenem Status**, Summe, Warnungen und Fehlern. Zwei Pfadsegmente, kollidiert also nicht mit `POST /imports/{entity}`.
- `POST /imports/order-history/commit`: legt einen `ImportRun` mit `entity="order_history"` an. Eine Option „künftige als Entwurf" ist möglich. Default bleibt BESTAETIGT (Spec:63).
- `DELETE /imports/runs/{id}` erweitern (heute nur Chargen, `imports.py@efcea00:1218ff`):
  - Er löscht die Bestellungen des Laufs.
  - Er **blockiert** bei Folgeobjekten: Lieferschein, AB, Rechnung (`invoices.order_id`, `invoice_lines.order_item_id`), Lagerbewegung, Audit-Eintrag ≠ IMPORT.
- Datenmodell, nur `ADD COLUMN` über `_add_col_if_missing` (Muster `tenancy.py:288-290`, `:333-335`):
  - `orders.import_run_id CHAR(32)`.
  - Optional `orders.external_order_number VARCHAR(100)` als eigener Idempotenzschlüssel, damit `customer_reference` wieder nur die Kundenbestellnummer ist (Lücke 8).
  - **Achtung:** Die 49 vorhandenen Importe haben diese Spalte leer. Prüft die Idempotenz nur noch `external_order_number`, legt ein erneuter Upload von Gernots Datei alle 49 doppelt an. Deshalb entweder beim Migrieren rückfüllen (`UPDATE orders SET external_order_number = customer_reference WHERE …`, Abgrenzung wie in 3.4) oder bis auf Weiteres **beide** Spalten prüfen.
  - Einen UNIQUE-Constraint kann `ADD COLUMN` nicht anlegen. Möglich wäre ein separater `CREATE UNIQUE INDEX IF NOT EXISTS` (Muster `tenancy.py:354`), aber erst nach Bereinigung möglicher Dubletten.
- Oberfläche:
  - Dialog statt direkter Dateiauswahl, mit Vorlage, Datei, Vorschau-Tabelle mit Statusspalte („wird Geliefert" / „wird Bestätigt") und Knopf „Importieren".
  - Danach eine Liste der Importläufe mit „Rückgängig".
  - Der E2E-Test `import-upload.spec.ts:60` sucht das erste `input[type=file]` und muss angepasst werden.

**Stufe C — Härtung `bulk-status` (S, gehört zu Paket 2/A1 „beide Wege vereinheitlichen")**
- Dieselbe Übergangstabelle wie `sales.py:1198-1205` und derselbe Lagerabzug bei GELIEFERT, oder den ungenutzten Endpunkt entfernen. Kein Backend- oder E2E-Test nutzt ihn (grep).

**Einordnung:** Die Datenkorrektur ist erledigt (3.4). Stufe A passt in Paket 2 (Tagesplan und Status), Stufe B in Paket 3 (Belegfluss). Ob B nötig ist, hängt davon ab, ob der Import nur einmal zum Go-Live gebraucht wurde (Frage an Gernot). Lücke 13 (Doppel-LS) gehört zu Paket 1 „Doppelabrechnung sperren".

### 3.4 Frage (5): Datenkorrektur der zwei Zukunftsbestellungen — erledigt, Nachprüfung

**Erledigt am 08.10.** (belegt (Spec), Spec:62):
- Backup `/root/backups/minga-vor-importfix-20261008-104517.db`.
- BE-20261008-0004 und BE-20261011-0001 → `BESTAETIGT`, `actual_delivery_date` NULL, Audit „Import-Korrektur".
- Im Tagesplan 09./10.10. bzw. 11./12.10. geprüft.

Das Korrekturskript und die SQL-Variante aus der ersten Fassung sind **zurückgezogen**. Sie verlangten `status = 'GELIEFERT'` und würden jetzt abbrechen bzw. 0 Zeilen ändern.

**Nachprüfung, nur lesend** (Produktion, Mandant `minga`):
```sql
-- 1) Die zwei korrigierten: welche Felder fehlen noch?
SELECT order_number, status, requested_delivery_date, confirmed_delivery_date, actual_delivery_date,
       packing_date, inventory_deducted_at, invoice_id,
       delivery_address IS NULL AS ohne_lieferadresse, billing_address IS NULL AS ohne_rechnungsadresse,
       date(order_date) AS bestelldatum
FROM orders WHERE order_number IN ('BE-20261008-0004', 'BE-20261011-0001');
-- 2) Lieferschein(e) und Audit
SELECT o.order_number, d.delivery_note_number, d.status, d.actual_delivery_date, d.invoice_id
FROM delivery_notes d JOIN orders o ON o.id = d.order_id
WHERE o.order_number IN ('BE-20261008-0004', 'BE-20261011-0001');      -- erwartet: höchstens 1 LS je Bestellung
SELECT o.order_number, a.action, a.reason, a.created_at
FROM order_audit_logs a JOIN orders o ON o.id = a.order_id
WHERE o.order_number IN ('BE-20261008-0004', 'BE-20261011-0001');
-- 3) Die Bestellung vom 08.10. (Klara Düran) und die 46: GELIEFERT ohne Lieferschein
SELECT o.order_number, c.name, o.requested_delivery_date, o.actual_delivery_date,
       (SELECT count(*) FROM delivery_notes d WHERE d.order_id = o.id) AS lieferscheine
FROM orders o JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'GELIEFERT' AND o.created_by IS NULL AND date(o.created_at) = '2026-10-08'
ORDER BY o.requested_delivery_date;                                    -- erwartet 47 Zeilen, lieferscheine = 0
-- 4) Einheiten und Pfand in den Importen (für die Fragen an Gernot)
SELECT ol.unit, count(*) FROM order_lines ol JOIN orders o ON o.id = ol.order_id
 WHERE o.created_by IS NULL AND date(o.created_at) = '2026-10-08' GROUP BY ol.unit;
SELECT p.sku, count(*) FROM order_lines ol JOIN orders o ON o.id = ol.order_id JOIN products p ON p.id = ol.product_id
 WHERE o.created_by IS NULL AND date(o.created_at) = '2026-10-08' AND p.is_deposit = 1 GROUP BY p.sku;
```
Hinweise:
- **Abgrenzung der Importe:** Ein Filter nur auf `created_by IS NULL AND customer_reference IS NOT NULL` erfasst auch Shopify-Bestellungen (`shopify_service.py:193-200`) und Abo-Bestellungen ohne Benutzer. Deshalb zusätzlich das Anlagedatum 08.10. (Spec: „sieben Importläufe am 08.10.") und das Ergebnis gegen `customer_reference` gegenlesen. `created_at` ist UTC (`order.py:128`).
- UUIDs liegen als `CHAR(32)` hex ohne Bindestriche vor. Enum-Spalten speichern den Namen (`'GELIEFERT'`).

**Nachkorrektur, nur falls die Prüfung Lücken zeigt.** Jede Nachkorrektur einzeln vorlegen, das ist für Produktionsdaten Pflicht (Spec:100).
- **Lieferadresse (funktional relevant, LS/AB-PDF):** Der Weg geht über die reguläre API, nicht über SQL: `PATCH /api/v1/sales/orders/{id}` mit `delivery_address`, `billing_address` und `change_reason` (`schemas/order.py:153-164`, `sales.py:1057-1115`).
  - Vorteile: Schema-Prüfung, Benutzer und Audit `UPDATE` mit Grund entstehen automatisch (`sales.py:1099-1108`). Belegt (Lauf), Repro 2: `PATCH 200`, Audit `('UPDATE', 'Nachkorrektur T1')`.
  - Inhalt wie `sales.py:879-901`. `AddressSchema` verlangt `strasse`, `plz` und `ort` (`schemas/order.py:16-24`).
  - Im Bearbeiten-Dialog gibt es dafür **kein** Feld (1.2). Also per API mit gültigem Token eines Vertriebs- oder Admin-Kontos auf dem Mandanten `minga`.
  - Das LS-PDF wird bei jedem Abruf neu erzeugt (`documents.py:328-345`) und zeigt die Adresse danach.
- **`confirmed_delivery_date`:** rein kosmetisch, kein Leser außer dem Antwortfeld (`sales.py:777`). Nur mitziehen, wenn ohnehin gepatcht wird.
- **Packtag BE-20261011-0001:** Der Standard ergibt **Sonntag 11.10.** (`order.py:168-174`). Wird sonntags nicht gepackt, `packing_date = 2026-10-10` per `PATCH` setzen (`schemas/order.py:161`). Das geht nur per API, der Dialog hat kein Packtag-Feld (1.2). Frage an Gernot.
- **Lieferschein der 10.10.-Bestellung:**
  - Status ENTWURF/AUSGESTELLT → **unverändert lassen**. Quittieren am 10.10. setzt dann GELIEFERT und bucht ab (belegt (Lauf), Z-B).
  - **Keinen zweiten LS anlegen**, auch nicht nach einer Positionsänderung, sonst rechnet der Sammellauf doppelt ab (Lücke 13).
  - Kommen nach dem Anlegen des LS Positionen hinzu, steht auf dem LS-PDF der neue Stand (live, `pdf_service.py:759`), auf der Packliste der alte (Schnappschuss, `documents.py:226-256`).
  - Status GELIEFERT (quittiert) oder `invoice_id` gesetzt → mit Gernot klären. Ein quittierter Beleg ist laut `is_locked` unveränderlich (`models/documents.py:111-112`).

**Die 46 rückdatierten und die vom 08.10.:** **keine** Korrektur an Status oder Datum. Wie sie abgerechnet werden, hängt von Gernots Antwort ab (1.4).

### 3.5 Tests (Erweiterung von `backend/tests/test_import_bestellungen_zukunft.py`)

Erledigt durch efcea00: leer + Zukunft → BESTAETIGT, im Tagesplan, Position hinzufügbar; leer + Vergangenheit → GELIEFERT; GELIEFERT + Zukunft → 400 mit Rollback; Vorlage mit Zukunftszeile (1.6).

Offen:
1. Leer + Lieferdatum heute → `packing_date` = heute; erscheint in `day-plan(heute)` unter „Verpacken" **und** „Ausliefern". Mit efcea00 ist dieser Test heute rot (Repro 2).
2. „Bestätigt" → BESTAETIGT; „offen" → Zeilenfehler (heute: Datumsregel).
3. Zwei Zeilen einer Bestellung, eine ohne Preis → Bestellung nicht angelegt, Fehler nennt die Bestellung. Danach Re-Upload der korrigierten Datei → Bestellung mit **beiden** Positionen.
4. Bestelldatum in der Zukunft bzw. nach dem Lieferdatum → Zeilenfehler.
5. Einheit leer → `STK`.
6. Adress-Schnappschuss gesetzt; LS-PDF enthält „Lieferadresse" und den Adresszusatz (Muster `test_gernot_260821.py:428-436`).
7. Ende-zu-Ende: Zukunftsimport → LS anlegen → quittieren → Bestellung GELIEFERT und `inventory_deducted_at` gesetzt.
8. `created_by` gesetzt; Audit `IMPORT` vorhanden.
9. Zweiter Upload derselben Datei → alle übersprungen (Idempotenz bleibt), auch nach Einführung von `external_order_number` für Altbestände ohne diesen Wert.
10. Rollen: Upload als `production_staff` → 403; der Knopf ist für diese Rolle nicht gerendert.
11. Stufe B: `validate` schreibt nichts; `commit` legt einen ImportRun an; Rollback löscht die Bestellungen und liefert 409, sobald ein Lieferschein existiert.
12. Stufe C: `bulk-status` mit `GELIEFERT → BESTAETIGT` → 400.
13. Paket 1: zweiter LS zu einer Bestellung → Sammellauf rechnet sie nur einmal ab (Repro 2 als Vorlage).
14. E2E `import-upload.spec.ts` an den Dialog anpassen (Datei-Input erst nach Öffnen des Dialogs).

---

## 4. Risiken

1. ~~Zeitkritisch: Packtag 09.10.~~ Erledigt durch die Korrektur (Spec:62). **Neu zeitkritisch:** BE-20261011-0001 hat den Standard-Packtag **Sonntag 11.10.** Wird sonntags nicht gepackt, fehlt die Bestellung am Samstag im Tagesplan (Annahme zur Arbeitswoche).
2. **Kreditlimit:** Die zwei korrigierten und alle künftig als BESTAETIGT importierten Bestellungen zählen als offen (`sales.py:840-842`). Eine danach erfasste Bestellung desselben Kunden kann am Limit scheitern.
3. **Same-Day-Import:** Bestellungen mit Lieferdatum heute erscheinen nur unter „Ausliefern", nicht unter „Verpacken" (belegt (Lauf)). Der Hinweistext verspricht etwas anderes.
4. **Teilimport:** Eine fehlerhafte Zeile führt zu einer unvollständigen Bestellung, und der Re-Upload repariert sie nicht (Lücke 10). Annahme: Die sieben Läufe am 08.10. könnten solche Wiederholungen sein; prüfbar über Bestellungen mit weniger Positionen als in Gernots Datei.
5. **Doppelabrechnung:**
   - Waren die 47 im Altsystem schon berechnet, berechnet jeder nachträgliche Lieferschein sie im Sammellauf ein zweites Mal. Gegenmittel: FAKTURIERT setzen plus Sperre in Paket 1.
   - Unabhängig davon verdoppelt jeder zweite LS zu einer Bestellung die Menge (Lücke 13).
6. **Pfand vor Paket 1:** Der Sammellauf nimmt Pfandzeilen mit (`invoices.py:564-569`), auch bei IFCO-Clearing-Kunden. Das gilt gleich, welche B4-Variante kommt.
7. **„Heute" ist nicht überall gleich:**
   - Die Statusregel nutzt Europe/Berlin (`imports.py@efcea00:42-43`).
   - Packtag (`order.py:186`), Bestellnummer (`sales.py:598`) und Belegnummern (`documents.py:84`, `:200`) nutzen `date.today()`, also die Serverzeit (Annahme: Container in UTC).
   - Zwischen 00:00 und 02:00 MESZ weichen beide Werte voneinander ab.
8. **Bulk-Status-Endpunkt:** ungeprüfte Statuswechsel, auch für die Halle erreichbar (Lücke 9). Mit echten Mitarbeiter-Logins (B8) gibt es mehr Konten mit Zugriff, solange er nicht gehärtet ist.
9. **Produktion:** Jede Nachkorrektur nur nach WAL-sicherem Backup und einzeln vorgelegt (Spec:100). Bevorzugt über die reguläre API mit Audit statt direkt in SQLite.
10. **Verhaltensänderung (efcea00, live):**
    - Zukunftsbestellungen landen als BESTAETIGT direkt im Tagesplan.
    - Vergangene Lieferdaten werden weiter still GELIEFERT, ohne Lieferschein und damit ohne Abrechnung.
    - Beides muss Gernot wissen, bevor er weitere Dateien hochlädt.

## 5. Fragen an Gernot / Steuerberater

Nur Punkte, die der Code nicht beantwortet:
1. Gernot: Sind die 46 Bestellungen vom 16.09.–07.10. und die vom 08.10. (Klara Düran) bereits im Altsystem berechnet, oder sollen sie über NovaERP abgerechnet werden?
2. Gernot: Ist die Bestellung von Klara Düran (Lieferdatum 08.10.) tatsächlich ausgeliefert? Sie steht auf „Geliefert", ohne Lieferschein und ohne Lagerabzug.
3. Gernot: Ist der Lieferschein zur 10.10.-Bestellung (Großer Kern) schon gedruckt, mitgegeben oder unterschrieben, oder kann er bis zur Auslieferung offen bleiben?
4. Gernot: Wird sonntags gepackt? Sonst setzen wir für die Lieferung an Fruchthof Nagel am Montag 12.10. den Packtag auf Samstag 10.10.
5. Gernot: Für Fruchthof Nagel ist als Bestelldatum der 11.10. eingespielt, und so steht es auf AB und Lieferschein. War das gewollt, oder ein Versehen in der Datei?
6. Gernot: Welche Einheit war gemeint, wo die Spalte „einheit" leer war — Stück/Schale oder Gramm?
7. Gernot: War der Import eine einmalige Übernahme zum Go-Live, oder sollen regelmäßig Bestellungen per Datei kommen? Davon hängt ab, ob sich Vorschau und Rückgängig lohnen. Sollen dann auch Mitarbeiter-Logins importieren dürfen, oder bleibt das bei Ihnen bzw. im Vertrieb?
8. Gernot: Ist „bestell_nr_extern" Ihre alte Auftragsnummer oder die Bestellnummer des Kunden? Sie steht heute als „Auftragsnummer" auf AB und Lieferschein.
9. Gernot: Ist das Pfand aus den importierten Lieferungen (16.09.–08.10.) schon im Altsystem bzw. über IFCO verrechnet? Gilt das unabhängig davon, ob Pfand künftig je Kunde von der Rechnung ausgenommen wird oder über eine monatliche Pfand-Sammelrechnung läuft? Davon hängt ab, ob diese Lieferungen in der ersten Pfand-Abrechnung mitzählen.
10. Steuerberater: Falls die September-Lieferungen noch nicht berechnet sind, reicht im Oktober eine Sammelrechnung je Kunde mit Leistungszeitraum September? Oder gibt es Vorgaben zum Rechnungsdatum bzw. zur Zuordnung zum Leistungsmonat in der Buchhaltung? Die Oktober-Lieferungen bis 08.10. würden mit dem regulären Oktober-Lauf abgerechnet.

---

## Prüfvermerk (08.10.2026, gegen `efcea00`)

Korrekturen gegenüber der ersten Fassung:
- Stand nachgezogen: Hotfix `efcea00` ist auf `main` und laut Spec live. Die Statusregel, die Ablehnung von GELIEFERT+Zukunft, der neue Knopf und die Vorlage sind umgesetzt (Kernbefund, 2, 3.1, 3.2, 1.6).
- Die Datenkorrektur der zwei Zukunftsbestellungen ist laut Spec:62 erledigt. Der „Eilt"-Hinweis, das Python-Skript und die SQL-Variante sind zurückgezogen, das Skript würde an `status != GELIEFERT` abbrechen. Ersetzt durch Nachprüfung und Nachkorrektur per API (3.4).
- Die Zählung ist aufgelöst: 46 + 1 (Klara Düran, 08.10.) + 2 = 49 (Spec:61). Abzurechnen sind deshalb 47, nicht 46.
- „Ein einziges commit (alles oder nichts)" war falsch. Zeilen-Parsefehler führen zum Teilimport, und der Re-Upload überspringt die Bestellung (1.1, Lücke 10, belegt (Lauf)).
- `main.py:787-790` → `:788-792`.
- „Packtag im Bearbeiten-Dialog setzen" war falsch. Der Dialog hat kein Packtag- und kein Adressfeld, das geht nur per API (1.2, 3.4).
- „SQL-Alternative ohne Adresse, Adresse nur per Skript" war falsch. `PATCH /orders/{id}` nimmt `delivery_address`/`billing_address` samt Audit an (belegt (Lauf)).
- Zeilen bearbeiten bzw. löschen bei GELIEFERT geht auch im UI und über `DELETE …/lines`, nicht nur per `PATCH`-API (1.2).
- Abrechnung: Ein Lauf „01.–07.10." widerspricht B5 „monatlich fix". Die Oktober-Lieferungen gehören in den regulären Oktober-Lauf (1.4).
- B4 war verkürzt wiedergegeben. Gernot nennt zwei Varianten und fragt nach unserer Einschätzung (1.4, Frage 9).
- Neu: Zweiter Lieferschein verdoppelt den Sammellauf (belegt (Lauf)), mit Bezug auf den bestehenden LS der 10.10.-Bestellung (Lücke 13, 3.4).
- Neu: Same-Day-Import fehlt auch nach efcea00 in „Verpacken" (belegt (Lauf)).
- Neu: Bestelldatum ohne Plausibilität, Produktionsfall BE-20261011-0001.
- Neu: Halle sieht den Import-Knopf, bekommt aber 403 (B8).
- Stufe B: Eine Idempotenz nur über `external_order_number` hätte die 49 Altimporte beim Re-Upload dupliziert. Rückfüllung oder Doppelprüfung ergänzt.
- Die Abgrenzung der Importe über `created_by IS NULL` erfasst auch Shopify-Bestellungen. Der Filter ist um das Anlagedatum ergänzt.
- `confirmed_delivery_date` hat keinen funktionalen Leser (`sales.py:777`). Nachkorrektur nur optional.
- Die Frage „Bestätigt oder Entwurf" ist entfallen, sie ist entschieden (Spec:63). Neu sind die Fragen zu Sonntags-Packtag, Bestelldatum 11.10., Klara Düran und Import-Recht für Mitarbeiter.
- Kleinere Belegkorrekturen: `documents.py:303-319` → `:304-321`, `forecasting.py:793` → `:792`, `documents.py:73-98` → `:73-97`, `Orders.tsx:28-36` → `:29-37`.
