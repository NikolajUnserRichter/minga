# T2 — SEPA-Lastschriftmandat am Kunden (B10)

Stand: `main` @ `c4a1832`. Grundlage sind der Code und ein lokaler Testlauf. Produktionsdaten habe ich nicht gesehen. Zweitprüfung am Code am 08.10.: Korrekturen und Ergänzungen sind eingearbeitet und in Abschnitt 6 aufgelistet.
- **Belegt** heißt: im Code gesehen, mit Datei:Zeile.
- **Annahme** heißt: im Code nicht prüfbar.
- **Fachwissen** heißt: SEPA-Regelwerk. Es ist nicht im Code belegbar und mit Bank oder Steuerberater zu bestätigen.

Bezug: Spezifikation `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md`, Entscheidung 12 (B10). Ebenso Pakete 1 und 3 sowie Gernots Antworten zu B3, B4, B5 und B8 vom 08.10.

**Kurzantwort an Gernot:** Das geht. Drei Punkte bauen wir anders als gewünscht.
1. **Die Gläubiger-ID kommt in die Firmendaten.** Sie gehört MingaGreens, nicht dem Kunden. In der Kundenmaske erscheint sie nur zur Ansicht.
2. **Im Hinweis steht ein konkretes Einzugsdatum statt „frühestmöglich“.** Eine Vorabankündigung braucht Betrag und Datum.
3. **Lastschriftrechnungen laufen nicht mehr ins Mahnwesen.** Dafür gibt es eine Liste „Einzug fällig“, die nach dem Einzug per Klick als bezahlt gebucht wird.

---

## 1. Ist-Zustand (belegt)

### 1.1 Kundenmodell: keine Bankdaten, keine Zahlungsart
- `Customer` hat **kein** Feld für IBAN, BIC, Bank, Kontoinhaber, Mandat oder Zahlungsart (`backend/app/models/customer.py:122-217`).
- Vorhanden sind diese Felder:
  - `ust_id`, `steuernummer` (`:155-156`)
  - `payment_terms` (`:159-161`) mit den Werten `PREPAID, COD, NET_7…NET_60` (`:38-45`)
  - `credit_limit` (`:162`)
  - Skonto (`:172-174`)
  - `datev_account` (`:185`)
- Das Zahlungsziel in Tagen kommt aus `payment_days` (`:258-269`).
- Die Schemas spiegeln das (`backend/app/schemas/customer.py:84-124` Create, `:127-172` Update, `:175-205` Response). Kein Bankfeld.
- Das Kundenformular hat die Bereiche Stammdaten, Zahlungsziel und „Konditionen“ (Rabatt, Skonto, Verpackung, Preise auf Lieferschein). Ein Bankbereich fehlt (`frontend/src/pages/Customers.tsx:227-450`, Zahlungsziel `:249-256` und `:359-364`, Konditionen `:367-415`). Der TS-Typ `Customer` hat ebenfalls kein Bankfeld (`frontend/src/types/index.ts:154-174`).

### 1.2 Die Zahlungsart „Lastschrift“ gibt es nur an der Zahlung
- Das Enum `PaymentMethod.LASTSCHRIFT = "LASTSCHRIFT"` existiert (`backend/app/models/enums.py:47-54`, Wert `:54`; „SEPA-Lastschrift“ steht dort nur als Kommentar). Benutzt wird es nur an `Payment.payment_method`, also an der einzelnen erfassten Zahlung (`backend/app/models/invoice.py:328-330`).
- `Invoice` hat keine Zahlungsart (`models/invoice.py:21-130`).
- Nebenbefund: Das Zahlungsformular bietet `KARTE` an (`frontend/src/pages/Invoices.tsx:814-820`, Typ `types/index.ts:592`). Das Backend-Enum kennt `EC` und `KREDITKARTE`, aber kein `KARTE`. Das Schema validiert gegen das Enum (`schemas/invoice.py:83`). Wer „Karte“ wählt, bekommt also 422.

### 1.3 Firmendaten und Bankverbindung der Firma
- Firmendaten liegen als Schlüssel-Wert-Paare in `app_settings` (`backend/app/models/app_setting.py:17-28`). Die bekannten Schlüssel stehen in `KNOWN_SETTINGS` (`backend/app/services/settings_service.py:20-52`).
  - Darunter sind `COMPANY_BANK_NAME`, `COMPANY_IBAN` und `COMPANY_BIC` (`:39-42`).
  - **Eine Gläubiger-ID gibt es nicht.**
- Das PDF lädt genau die Schlüssel aus `COMPANY_KEYS` (`backend/app/services/pdf_service.py:15-19`, `:108-113`). Die Fußzeile druckt Bank, IBAN und BIC der Firma (`:173-178`).
- Ändern geht über `PATCH /api/v1/admin/settings`. Der Endpunkt prüft nur, ob der Schlüssel bekannt ist, nicht den Inhalt (`backend/app/api/v1/admin.py:64-87`). Auch `set_setting` validiert nicht (`settings_service.py:70-72`).
- `get_setting` fällt ohne DB-Wert auf die **Umgebungsvariable** gleichen Namens zurück (`settings_service.py:55-62`), und `load_company_settings` nutzt diesen Rückfall (`pdf_service.py:112-113`). Umgebungsvariablen gelten für **alle** Mandanten im Container. Eine Gläubiger-ID, die jemand in Coolify als Variable setzt, stünde also auch auf den Belegen anderer Mandanten (z. B. Demo).
- Lesen dürfen `/admin/settings` nur Admins (`_deps_admin`, `main.py:137`, `:807-811`). Die Buchhaltung kommt dort nicht hin.
- **Für die Firmendaten gibt es keine echte Oberfläche.** Die Karte „Firmendaten“ unter Einstellungen speichert nur im LocalStorage des Browsers (`frontend/src/pages/Settings.tsx:71-74`). Vorbelegt ist sie mit Fantasiewerten wie „Breisacher Str. 12“ und „DE328451962“ (`:24-34`). Das PDF sieht diese Werte nie. Gepflegt wird nach Doku nur per `curl` gegen die API (`docs/wave-2026-06-deliverables.md:182-200`).
  - Annahme: Ob die COMPANY_*-Werte im Mandanten `minga` gesetzt sind, ist ohne Produktionszugriff nicht prüfbar.
- `branding.py` enthält nur Editionen und Farben, keine Firmen- oder Bankdaten (`backend/app/branding.py:25-74`).

### 1.4 Rechnungsmail
- Der Text steht fest im Endpunkt `POST /invoices/{id}/send` (`backend/app/api/v1/invoices.py:223-275`).
  - Text: `invoices.py:254-261`
  - Betreff `Rechnung … — Minga Greens`: `:254`
  - Zeile „Fällig am:“: `:259`
  - Gruß „Ihr Minga-Greens-Team“: `:260`
- Es gibt **einen** Empfänger als Query-Parameter (`:227`). Das Frontend fragt ihn per `window.prompt` ab (`frontend/src/components/domain/OrderDocumentsModal.tsx:104-115`, `frontend/src/services/api.ts:783-784`).
- Versendet wird reiner Text über SMTP aus den DB-Einstellungen (`backend/app/services/email_service.py:40-106`).
- Das Schema `InvoiceSendRequest` mit `email_cc`, `email_subject` und `email_body` existiert (`schemas/invoice.py:239-245`). Es wird importiert (`invoices.py:21`), aber **nirgends benutzt**.

### 1.5 Rechnungs-PDF: kein Zahlungshinweis
- `generate_invoice_pdf` (`pdf_service.py:187-432`) druckt Kopf, Meta-Block, Positionen und Summen. Danach folgen Skonto-Hinweis (`:337-349`), Reverse Charge, Eigentumsvorbehalt, Lieferscheinliste, Dank und Fußzeile mit Firmen-IBAN (`:415-427`).
- **Fälligkeitsdatum und Zahlungsziel stehen nicht auf der Rechnung.** `due_date` kommt nur in der Mahnung vor (`:577-605`). Die Mahnung beruft sich damit auf ein Datum, das der Kunde nur aus dem Mailtext kennt, und das auch nur bei Versand über das System.
- **Das PDF wird bei jedem Abruf neu aus Live-Daten erzeugt** (`invoices.py:466-494`). Die Anschrift kommt live vom Kunden (`pdf_service.py:256`, `:78-105`), nicht aus dem Snapshot `invoice.billing_address` (`models/invoice.py:71`). Ein Lastschrifthinweis, der live aus dem Kundenstamm gelesen würde, veränderte also nachträglich alte Rechnungen.
- `invoice.header_text` und `invoice.footer_text` (`models/invoice.py:102-103`) druckt das PDF **nicht**. Sie gehen nur an lexoffice (`backend/app/services/lexoffice_service.py:58-59`).
- Vorlagen:
  - Abschnitte je Belegart in `DEFAULT_SECTIONS` (`backend/app/models/document_template.py:33-45`).
  - Texte in `DEFAULT_TEXTS` (`:114-121`). Eine Ersetzungsfunktion `apply_placeholders` existiert (`backend/app/services/document_template_service.py:29-36`, Hülle `get_text` `:64-69`). **Kein PDF-Erzeuger ruft sie auf**, die Platzhalter werden heute nirgends ersetzt (Suche nach `apply_placeholders`/`get_text(` im Backend: nur die Definitionen). Der SEPA-Text wäre der erste echte Nutzer.
  - Ein unbekannter Abschnittsschlüssel gilt als eingeschaltet (`:47-54`). Ein neuer Abschnitt erscheint also auch bei schon gespeicherten Vorlagen.
  - Die Vorlagen-Oberfläche kennt nur vier feste Textfelder (`frontend/src/pages/DocumentTemplates.tsx:15-20`). Nebenbefund: `intro_text` und `outro_text` wertet das Rechnungs-PDF nicht aus. `thanks_text` und `ownership_text` werden ausgewertet, fehlen aber in der Oberfläche.
  - Die Platzhalterliste im Editor kommt vom Backend: `PLACEHOLDERS_BY_TYPE` (`backend/app/api/v1/document_templates.py:34-48`). Für Rechnungen gibt es dort schon `{total_gross}` und `{due_date}`. Das Rechnungs-PDF selbst ruft `apply_placeholders` heute nicht auf: `thanks_text` und `ownership_text` gehen roh hinein (`pdf_service.py:363-368`, `:407-412`).
  - **Nebenbefund: Die Vorschau der Rechnungsvorlage ist heute kaputt.** `GET /document-templates/RECHNUNG/preview.pdf` (`document_templates.py:224`) rendert `build_dummy_invoice()` (`backend/app/services/document_template_service.py:164-191`). Diesem Ersatzobjekt fehlen `service_period_start`, `order` und `total_deposit`. Der Abbruch passiert in `pdf_service.py:247` mit `AttributeError` (lokal am 08.10. reproduziert). Jedes neue Rechnungsfeld, das das PDF liest (z. B. `sepa_hinweis`), muss also auch im Ersatzobjekt stehen oder per `getattr(..., None)` gelesen werden.

### 1.6 Fälligkeit und Mahnwesen
- Fälligkeit = Rechnungsdatum + `customer.payment_days` (`backend/app/services/invoice_service.py:55-58`).
- Alle Rechnungsarten laufen über `create_invoice`: manuell (`invoices.py:111`), aus Bestellung (`invoice_service.py:186`), Sammellauf (`invoices.py:604`), Abo-Task (`tasks/invoice_tasks.py:252`; der Task ist im Scheduler nicht eingeplant, `scheduler_service.py:87-105`) und Gutschrift/Storno (`invoice_service.py:321-329`). Es gibt also **eine** Stelle für die Anlage.
  - **Aber:** `create_invoice` ist für Zahlungsart und Mandat der falsche Zeitpunkt. Ein Entwurf kann danach noch den Kunden wechseln. `InvoiceUpdate` enthält `customer_id` und `due_date` (`schemas/invoice.py:147-153`), `PATCH /invoices/{id}` übernimmt sie per `setattr` (`invoices.py:157-159`). Die Kopfdaten-Maske nutzt genau das (`frontend/src/pages/Invoices.tsx:1002-1009`). Ein beim Anlegen gesetztes Mandat gehörte dann zum falschen Kunden.
- **Nach `OFFEN` führen fünf Wege, nicht zwei:**
  1. `finalize_invoice` setzt `OFFEN` und `sent_at`, auch ohne Mail (`invoice_service.py:218-239`).
  2. `/send` setzt `OFFEN` direkt, ohne `finalize_invoice`. Das PDF für den Anhang entsteht **vorher** (`invoices.py:250`, `:270-273`).
  3. Der Sammellauf setzt `OFFEN` direkt, ohne `finalize_invoice` und ohne `sent_at` (`invoices.py:645`). Das ist der Weg für Gernots monatliche Sammelrechnung (B5).
  4. Die Stornorechnung wird direkt `OFFEN` (`invoice_service.py:348`).
  5. `PATCH /invoices/{id}` mit `{"status": "OFFEN"}` auf einen Entwurf. `InvoiceUpdate` enthält `status` (`schemas/invoice.py:153`), geprüft wird nur, dass die Rechnung noch Entwurf ist (`invoices.py:154-159`).
- `BEZAHLT` setzen zwei Wege: `record_payment` (`invoice_service.py:277-281`) und der lexoffice-Abgleich, der ohne `Payment`-Datensatz `paid_amount = total` setzt (`backend/app/services/lexoffice_service.py:161-165`, Endpunkt `backend/app/api/v1/integrations.py:243`). Die an lexoffice übertragene Rechnung trägt nur `introduction`/`remark` aus `header_text`/`footer_text` und keinen Zahlungshinweis (`lexoffice_service.py:51-60`).
  - Annahme: Ob lexoffice im Mandanten `minga` aktiv ist (`LEXOFFICE_ENABLED`, DB-Einstellung), ist ohne Produktionszugriff nicht prüfbar.
- Automatik:
  - Der Scheduler läuft standardmäßig (`backend/app/services/scheduler_service.py:66`), je Mandant (`:30-57`).
  - Um 08:00 setzt er überfällige `OFFEN`/`TEILBEZAHLT` auf `UEBERFAELLIG` (`:98`, `backend/app/tasks/invoice_tasks.py:40-52`).
  - Um 09:00 mahnt er dreistufig per Mail (`:99`, `invoice_tasks.py:106-171`). Stufe 1 kommt 3 Tage nach Fälligkeit, Stufe 2 nach 14 und Stufe 3 nach 28 Tagen, mit Gebühren 5 € und 10 € (`backend/app/config.py:54-58`). Ab Stufe 2 steht der Status auf `MAHNVERFAHREN` (`invoice_tasks.py:170-171`).
  - Der Mailtext sagt „Bitte überweisen Sie den Betrag …“ (`backend/app/core/email.py:89`).
- Der Mahnversand nutzt SMTP aus den **Umgebungsvariablen** (`core/email.py:13-14`, `:31`, `:50-59`; Default `localhost:1025`, `config.py:42-49`), nicht aus dem Admin-Center.
  - Annahme: Ob in Produktion `SMTP_HOST` als Umgebungsvariable gesetzt ist und die Mahnmails wirklich rausgehen, kann ich nicht prüfen.
  - Der Statuswechsel auf `UEBERFAELLIG` passiert in jedem Fall.
- Zusätzlich setzen `GET /invoices/overdue` (`invoices.py:71-77`, mit Commit) und `InvoiceService.check_overdue_invoices` (`invoice_service.py:355-388`) den Status bei jedem Aufruf. `Invoice.is_overdue` (`models/invoice.py:186-191`) und der Mahnknopf (`frontend/src/pages/Invoices.tsx:432-459`; Endpunkt `invoices.py:183-220`, Sperre nur für bezahlt und storniert, `:203-204`) kennen keine Ausnahme.
- **Ein Kriterium „Lastschrift“ gibt es an keiner dieser Stellen.**
- Testlauf vom 08.10.: `tests/test_dunning.py` ist grün (1 passed, ohne Cache und Bytecode, keine Repo-Änderung). Jede überfällige Rechnung mit Kunden-E-Mail bekommt nach drei Tagen Stufe 1, egal wie der Kunde zahlt.

### 1.7 Zahlung erfassen
- `record_payment` summiert die Zahlungen und setzt `BEZAHLT` bzw. `TEILBEZAHLT` (`invoice_service.py:241-283`). Das Schema verlangt `amount > 0` (`schemas/invoice.py:82`).
- Es gibt keinen Endpunkt, um eine Zahlung zu löschen oder zurückzunehmen (nur GET und POST, `invoices.py:386-412`). **Eine Rücklastschrift lässt sich heute nicht abbilden.**
- `record_payment` setzt den Status nur nach oben: `BEZAHLT` ab vollem Betrag, `TEILBEZAHLT` ab > 0. Fällt `paid_amount` auf 0 zurück, bleibt der alte Status stehen (`invoice_service.py:277-281`). Eine Gegenbuchung allein macht aus `BEZAHLT` also nicht wieder `OFFEN`.

### 1.8 Rechte: wer sähe Bankdaten am Kunden?
- Die Rollenmatrix steht in `backend/app/main.py:82-137`, die Durchsetzung in `require_access` (`backend/app/api/deps.py:126-152`).
- Die Kunden-Endpunkte liegen im `sales.router` unter `_deps_auftraege` = Vertrieb, Buchhaltung, Planung **und Halle (`production_staff`), lesend und schreibend** (`main.py:119-122`, `:701-706`).
- `update_customer` übernimmt jedes Feld aus `CustomerUpdate` per `setattr` (`backend/app/api/v1/sales.py:129-145`). Ein IBAN-Feld am Kunden-Schema könnte also jeder Hallen-Login lesen **und ändern**.
- `DELETE /sales/customers/{id}` löscht Kunden ohne Bestellungen und Rechnungen **hart**, andere werden deaktiviert (`sales.py:148-172`, Prüfung `models/customer.py:219-224`). Auch das darf die Halle (`_deps_auftraege`). Die Mandanten-SQLite erzwingt Fremdschlüssel (`PRAGMA foreign_keys=ON`, `backend/app/tenancy.py:131`).
- Rechnungen liegen unter `_deps_geld` = Vertrieb und Buchhaltung (`main.py:125`, `:740-744`), Einstellungen unter `_deps_admin` (`:137`, `:807-811`).
- Der DATEV-Debitorenexport `GET /sales/customers/export/datev` liegt ebenfalls unter `_deps_auftraege` (`sales.py:439-443`). Er hat eine leere IBAN-Spalte mit dem Kommentar „IBAN if we had it“ (`backend/app/services/datev_service.py:225`, `:241`).
- Anhänge sind für **alle** Rollen lesbar (`main.py:133`, `:801-805`), zulässige Entitäten siehe `backend/app/models/attachment.py:19`. Ein eingescanntes Mandat gehört dort nicht ohne eigene Rechteprüfung hin.
- Gernot (B8, 08.10.): Mitarbeiter legen Bestellungen, AB und Lieferscheine an und versenden sie. **Rechnungen bleiben beim Admin.** Bankdaten gehören folgerichtig auf die Geldseite, nicht zur Halle.

### 1.9 IBAN-Prüfung
- Im Code gibt es keine.
- In `.venv/lib/python3.14/site-packages` liegt **keine** passende Bibliothek: kein `schwifty`, kein `python-stdnum`, kein `pydantic_extra_types`. Ohne Netzwerk ist nichts installierbar.
- Die Prüfung nach ISO 13616 (Modulo 97) ist mit der Standardbibliothek in zehn Zeilen machbar. Lokal geprüft: `DE89 3704 0044 0532 0130 00` gilt, mit einer geänderten Ziffer nicht.
- Dieselbe Rechnung prüft die Gläubiger-ID. Die Prüfziffer wird über nationale Kennung + Land + „00“ gebildet, ohne die Geschäftsbereichskennung `ZZZ`. Lokal geprüft: `DE98ZZZ09999999999` gilt.
- **Gernots Beispiel `DE75ZZZ0002442146`** hat eine passende Prüfziffer (75), aber 17 statt 18 Zeichen. Vermutlich fehlt eine führende Null. Die Prüfziffer bleibt davon unberührt, also fiele der Fehler ohne Längenprüfung nicht auf.
- `dateutil` ist installiert (`dateutil.easter`) und als direkte Abhängigkeit festgeschrieben (`backend/requirements.txt:34`, `python-dateutil==2.8.2`). Damit sind die Bankfeiertage (TARGET2) für die Verschiebung auf den nächsten Bankarbeitstag ohne neue Abhängigkeit berechenbar.
- Den Banknamen aus der BLZ ableiten geht nicht: das BLZ-Verzeichnis der Bundesbank liegt nicht vor. „Bank“ bleibt Freitext.
- `cryptography` ist installiert, wird aber für Feldverschlüsselung nirgends genutzt.

### 1.10 Migrationen
- Neue Tabellen legt `Base.metadata.create_all` je Mandant an (`backend/app/tenancy.py:228`, `:255`).
- Neue Spalten in bestehenden Tabellen gehen nur über `_add_col_if_missing` in `_auto_migrate` (`tenancy.py:265-281`). Fremdschlüssel werden dort als `CHAR(32)` angelegt (z. B. `:337`).

### 1.11 SEPA-fachlich (Fachwissen, nicht im Code belegbar)
- **Vorabankündigung (Pre-Notification):** Sie muss den Kunden vor dem Einzug erreichen und **Betrag und Fälligkeitsdatum** nennen. In Deutschland stehen üblicherweise auch Mandatsreferenz und Gläubiger-ID darin.
  - Die Frist beträgt 14 Kalendertage vor Fälligkeit, wenn nichts anderes vereinbart ist. Viele Mandatsformulare oder AGB verkürzen sie, z. B. auf 1 bis 5 Tage.
  - Sie darf auf der Rechnung stehen, und der Versand per Mail ist zulässig.
- **Gernots Text erfüllt das nur teilweise:**
  - Mandatsreferenz, Gläubiger-ID, Konto und Bank: vorhanden.
  - Betrag: nur als „den Rechnungsbetrag“. Besser ist der Betrag als Zahl, zumal bei Skonto oder Pfandverrechnung (siehe T3) Rechnungs- und Einzugsbetrag auseinanderfallen können.
  - **Datum: fehlt.** „Zum frühestmöglichen Zeitpunkt“ ist kein Fälligkeitsdatum.
- **Mandatsart:**
  - CORE (Basislastschrift): Der Kunde kann 8 Wochen lang ohne Begründung zurückbuchen lassen.
  - B2B (Firmenlastschrift): nur für Unternehmer, keine Erstattung. Die Bank des Kunden muss das Mandat vorher bestätigt haben, sonst wird die Lastschrift zurückgegeben.
  - Für einen späteren XML-Export ist die Art Pflicht.
- **Pflichtdaten im Lastschriftsatz:** Mandatsreferenz (bis 35 Zeichen, eindeutig je Gläubiger-ID), Datum der Unterschrift, Name des Kontoinhabers, IBAN. Die BIC ist im Inland und EWR seit 2016 entbehrlich. Gernots Liste fehlt der **Kontoinhaber**. Er weicht beim Kunden „Restaurant X“ oft ab, etwa als Inhaber oder GmbH.
- **Ablauf:** Ein Mandat verfällt nach 36 Monaten ohne Einzug.
- **Vorlagefrist bei der Bank:** 1 Bankarbeitstag vor Fälligkeit, für CORE und B2B.
- **Gläubiger-ID:** wird von der Bundesbank an den **Zahlungsempfänger** vergeben, hier MingaGreens. Sie ist für alle Mandate gleich und in Deutschland 18 Zeichen lang. Sie gehört also in die Firmendaten, nicht an den Kunden.

---

## 2. Lücken gegenüber Gernots Wunsch

| # | Lücke | Beleg |
|---|---|---|
| L1 | Kein Ort für Mandatsreferenz, Datum, IBAN, Bank, Kontoinhaber, Mandatsart | `models/customer.py:122-217` |
| L2 | Keine Zahlungsart am Kunden und an der Rechnung („Lastschriftmandat“ auswählbar) | `models/customer.py`, `models/invoice.py:21-130` |
| L3 | Keine Gläubiger-ID in den Firmendaten, keine Oberfläche für Firmendaten überhaupt | `settings_service.py:20-52`, `Settings.tsx:71-74` |
| L4 | Mailtext fest im Code, kein Lastschrifthinweis | `invoices.py:254-261` |
| L5 | Rechnungs-PDF ohne Zahlungshinweis und ohne Fälligkeitsdatum | `pdf_service.py:187-432` |
| L6 | PDF wird live erzeugt: Ohne Snapshot ändert ein Mandatswechsel alte Rechnungen | `invoices.py:466-494`, `pdf_service.py:256` |
| L7 | Kein Einzugsdatum mit Vorabankündigungsfrist und Bankarbeitstag | `invoice_service.py:55-58` |
| L8 | Lastschriftrechnungen werden überfällig gesetzt und automatisch gemahnt („bitte überweisen“) | `invoice_tasks.py:40-52`, `:106-171`, `core/email.py:89` |
| L9 | Keine Liste „Einzug fällig“, kein Sammelbuchen des Einzugs, keine Rücklastschrift | `invoices.py:386-412`, `schemas/invoice.py:82` |
| L10 | Bankdaten am Kunden-Schema wären für die Halle lesbar und änderbar | `main.py:122`, `:701-706`, `sales.py:139-141` |
| L11 | Keine IBAN- und Gläubiger-ID-Prüfung, keine Bibliothek | `.venv` (1.9) |
| L12 | Firmen-IBAN in der Fußzeile ohne „bitte nicht überweisen“ → Gefahr der Doppelzahlung | `pdf_service.py:173-178` |
| L13 | Fünf Wege nach `OFFEN`, nur einer über `finalize_invoice`; Kundenwechsel im Entwurf möglich | `invoices.py:157-159`, `:272`, `:645`, `invoice_service.py:236`, `:348`, `schemas/invoice.py:147-153` |
| L14 | lexoffice-Weg: kein Zahlungshinweis im Payload, Abgleich setzt `BEZAHLT` ohne Zahlungsdatensatz | `lexoffice_service.py:51-60`, `:161-165` |
| L15 | Hartes Löschen von Kunden ohne Belege, Fremdschlüssel aktiv → ein Mandat würde das Löschen mit 500 abbrechen oder (mit Cascade) Mandatsnachweise vernichten | `sales.py:165-167`, `tenancy.py:131` |

---

## 3. Vorschlag

Leitlinien:
1. Bankdaten in **eigener Tabelle** und **eigenem Router** auf der Geldseite.
2. Gläubiger-ID **einmal** in den Firmendaten.
3. Der Hinweis wird beim **Festschreiben** als **Snapshot** an der Rechnung eingefroren. Das gilt für jeden Weg nach `OFFEN`, nicht nur für `finalize_invoice` (1.6). Erst dort werden auch Zahlungsart und Mandat bestimmt.
4. Lastschriftrechnungen sind **nicht mahnfähig**, solange der Einzug aussteht.
5. **Kein SEPA-XML** in diesem Schritt.

### 3.1 Datenmodell (SQLite: neue Tabelle über `create_all`, Spalten über `_auto_migrate`)

**Neue Tabelle `sepa_mandates`** (neues Modell `backend/app/models/sepa_mandate.py`):

| Spalte | Typ | Regel |
|---|---|---|
| `id` | UUID | PK |
| `customer_id` | FK `customers.id` | **kein Cascade.** Kunden ohne Belege werden heute hart gelöscht (`sales.py:165-167`). Deshalb `Customer.can_be_deleted()` (`models/customer.py:219-224`) um „hat kein Mandat“ erweitern: Ein Kunde mit Mandat wird nur deaktiviert. Sonst bricht das Löschen an `PRAGMA foreign_keys=ON` (`tenancy.py:131`) mit 500 ab, oder ein Cascade vernichtet den Mandatsnachweis, den der Gläubiger aufbewahren muss |
| `mandatsreferenz` | String(35), unique | 1–35 Zeichen aus `A-Z a-z 0-9 + ? / - : ( ) . , '`, ohne Leerzeichen, nicht mit `/` beginnend oder endend, kein `//`. Annahme: Zeichensatz nach DK-Spezifikation; spätestens beim XML-Export gegenprüfen |
| `mandatsart` | String(4) | `CORE` oder `B2B`, Default `CORE` |
| `unterschrieben_am` | Date | Pflicht, nicht in der Zukunft |
| `kontoinhaber` | String(70) | Pflicht, vorbelegt mit dem Kundennamen |
| `iban` | String(34) | normalisiert (Großbuchstaben, ohne Leerzeichen), Modulo-97-Prüfung, DE = 22 Stellen |
| `bic` | String(11), optional | Format `^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$` |
| `bank_name` | String(100), optional | Freitext |
| `widerrufen_am` | Date, optional | gesetzt = inaktiv |
| `letzter_einzug_am` | Date, optional | für die Warnung vor dem Verfall nach 36 Monaten |
| `aenderungen` | JSON | nur anhängen: `{am, von, feld, alt, neu}`, IBAN dabei **maskiert**. Achtung: Ein in-place `append` auf eine JSON-Spalte erkennt SQLAlchemy nicht. Im Repo gibt es weder `MutableList` noch `flag_modified`. Also die Liste neu zuweisen, oder besser eine eigene Tabelle `sepa_mandat_aenderungen` anlegen |
| `created_at/updated_at/created_by/updated_by` | | `created_by` aus `user["username"]` (`deps.py:91-98`) |

- Höchstens **ein aktives Mandat je Kunde** über einen partiellen Unique-Index: `Index(..., "customer_id", unique=True, sqlite_where=text("widerrufen_am IS NULL"))`. `create_all` legt ihn mit an.

**Neue Spalten über `_auto_migrate`** (`tenancy.py:283ff`):
- `customers.zahlungsart VARCHAR(20) DEFAULT 'UEBERWEISUNG'`. Werte `UEBERWEISUNG | LASTSCHRIFT`, das vorhandene `PaymentMethod` (`enums.py:47-54`) wird wiederverwendet.
- `invoices.zahlungsart VARCHAR(20)`. NULL heißt Altbestand = Überweisung.
  - **SQL-Falle:** Wenn man „mahnfähig“ als `NOT (zahlungsart = 'LASTSCHRIFT' AND …)` schreibt, wird es bei NULL zu NULL. Damit fielen **alle Altrechnungen** aus Überfällig-Lauf und Mahnwesen. NULL muss ausdrücklich als Überweisung zählen: `or_(zahlungsart.is_(None), zahlungsart != 'LASTSCHRIFT', lastschrift_status == 'RUECKLASTSCHRIFT')`. Die Regressionstests dafür gibt es schon und müssen grün bleiben: `tests/test_dunning.py:8-49`, `tests/test_production_readiness.py:117-263`, `tests/test_services.py:271-291`.
- `invoices.sepa_mandat_id CHAR(32)`
- `invoices.sepa_hinweis TEXT`: der fertige Hinweistext, eingefroren beim Festschreiben (Regel 2).
- `invoices.lastschrift_status VARCHAR(20)`: `AUSSTEHEND | EINGEZOGEN | RUECKLASTSCHRIFT`.

**Firmendaten** (`settings_service.py:20-52`, zusätzlich in `COMPANY_KEYS`, `pdf_service.py:15-19`):
- `COMPANY_SEPA_GLAEUBIGER_ID`, Label „Gläubiger-Identifikationsnummer (SEPA)“. Prüfung: Format, Modulo 97, DE = 18 Zeichen.
- `SEPA_VORABANKUENDIGUNG_TAGE`, Label „Vorabankündigung: Tage vor Einzug“. Leer bedeutet 14.
- Geprüft wird im `PATCH /admin/settings` mit einem Prüfer je Schlüssel (`admin.py:64-87`). Bei Fehler: 422 mit Klartext.
- Gelesen wird die Gläubiger-ID **ohne Umgebungs-Rückfall**: `get_setting(db, key, env_fallback=False)` (`settings_service.py:55-62`). Sie gehört genau einem Mandanten. Ist sie nicht gesetzt, gibt es keine Lastschrift (422 bzw. 409), statt dass ein globaler Wert greift.

**Kleine Prüfmodule** (neu: `backend/app/services/sepa_service.py`, nur Standardbibliothek plus `dateutil`):
- `iban_gueltig(s)` und `iban_normalisieren(s)`
- `iban_maskiert(s)` → `DE26 xxxx xxxx xxxx xxxx 77` (Gernots Schreibweise: Land, Prüfziffer, letzte 2 Stellen)
- `glaeubiger_id_gueltig(s)`
- `naechster_bankarbeitstag(d)`: Wochenende und TARGET2-Feiertage (Neujahr, Karfreitag, Ostermontag, 1. Mai, 25. und 26.12.) über `dateutil.easter`
- `einzugsdatum(rechnungsdatum, payment_days, frist, heute)` = nächster Bankarbeitstag von `max(Rechnungsdatum + Zahlungsziel, heute + Frist)`
- `vorabankuendigung_text(invoice, mandat, settings, tmpl)`: eine Funktion für PDF und Mail

**Regeln:**
1. **Rechnung anlegen** (`invoice_service.py:30-108`): Nur ein **vorläufiges** `due_date = einzugsdatum(...)`, wenn der Kunde Lastschriftkunde ist und `invoice_type == RECHNUNG` ist. Das zeigt dem Bearbeiter im Entwurf das voraussichtliche Einzugsdatum. Zahlungsart, Mandat und `lastschrift_status` werden hier **nicht** gesetzt, denn der Entwurf kann noch den Kunden wechseln (1.6). **Gutschriften und Stornos** (`invoice_service.py:321`) bekommen nie eine Lastschrift; die Prüfung läuft über `invoice_type`, weil auch der Storno über `create_invoice` entsteht.
2. **Festschreiben: eine Funktion für alle Wege nach `OFFEN`**, z. B. `InvoiceService.festschreiben(invoice)`. Sie wird aufgerufen in `finalize_invoice` (`invoice_service.py:236`), in `/send` **vor** der PDF-Erzeugung (`invoices.py:250`, `:271-272`) und im Sammellauf (`invoices.py:645`). Die Stornorechnung (`invoice_service.py:348`) ruft sie ebenfalls auf; für Gutschriften tut sie nichts. `status` fliegt aus `InvoiceUpdate` (`schemas/invoice.py:153`), oder `PATCH` lehnt `status` ab. Sonst bleibt ein Weg nach `OFFEN` ohne Hinweis. Die Funktion macht Folgendes:
   - Zahlungsart und aktives Mandat **des aktuellen Kunden** ermitteln. Ist der Kunde Lastschriftkunde, aber ohne aktives Mandat oder ohne Gläubiger-ID → 409 mit Klartext, kein stiller Rückfall auf Überweisung. Im Sammellauf bricht das nicht den ganzen Lauf ab: Die betroffene Rechnung bleibt Entwurf und steht als Warnung in der Antwort.
   - `zahlungsart = LASTSCHRIFT`, `sepa_mandat_id`, `lastschrift_status = AUSSTEHEND` setzen.
   - `due_date = max(due_date, einzugsdatum ab heute)` setzen.
   - Den Text rendern und in `sepa_hinweis` einfrieren.
   - Ein späterer Versand nutzt den Snapshot. Liegt das Einzugsdatum dann näher als die Frist → 409 „Vorabankündigungsfrist nicht einhaltbar“ und die Aktion „Einzugsdatum neu setzen“. Die ist nur bei `AUSSTEHEND` ohne Zahlung erlaubt und wird im `internal_notes` protokolliert.
   - Das passt zu Paket 3: Dort wird die Rechnungsnummer ohnehin erst beim Finalisieren vergeben. Paket 3 sollte dieselbe Funktion nutzen, statt einen sechsten Weg anzulegen.
3. **Text** (Default in `DEFAULT_TEXTS["RECHNUNG"]["sepa_text"]`, `document_template.py:114-121`, Platzhalter über `apply_placeholders`):
   > Den Rechnungsbetrag von {betrag} buchen wir am {einzugsdatum} per SEPA-Lastschrift zum Mandat {mandatsreferenz} zu der Gläubiger-ID {glaeubiger_id} von Ihrem Konto {iban_maskiert} bei der {bank} ab. Bitte überweisen Sie den Betrag nicht und sorgen Sie für ausreichende Deckung.

   Gernots Wortlaut bleibt, „zum frühest möglichen Zeitpunkt“ wird zu „am {einzugsdatum}“. Die volle IBAN steht nie in Mail oder PDF.
4. **Nicht mahnfähig:** `zahlungsart == LASTSCHRIFT` und `lastschrift_status != RUECKLASTSCHRIFT`. NULL zählt als Überweisung (siehe SQL-Falle oben). Das wird **ein** gemeinsames Prädikat. `is_overdue` ist eine Python-Property, die Läufe sind SQL-Abfragen. Das Prädikat muss daher in beiden Formen existieren, am saubersten als `hybrid_property` am Modell `Invoice`. Es greift in:
   - `check_overdue_invoices`, Service und Task (`invoice_service.py:373-380`, `invoice_tasks.py:40-46`)
   - `send_payment_reminders` (`invoice_tasks.py:106-114`)
   - `Invoice.is_overdue` (`models/invoice.py:186-191`)
   - `POST /payment-reminder` (`invoices.py:203-204`, liefert 400)

   **Mit Paket 1 abstimmen:** „Stornobeleg ohne Mahnung“ braucht dieselbe Stelle. Das Prädikat dort anlegen, T2 erweitert es.
5. **Einzug buchen:** Die Sammelaktion legt je Rechnung `Payment(payment_method=LASTSCHRIFT, amount=Restbetrag, reference=Mandatsreferenz)` an, über das vorhandene `record_payment` (`invoice_service.py:241-283`). Danach `lastschrift_status = EINGEZOGEN` und `mandat.letzter_einzug_am = Datum`.
   - **Auch andere Zahlungswege** müssen die Rechnung aus der Einzugsliste nehmen. Gemeint sind eine von Hand erfasste Zahlung (`POST /invoices/{id}/payments`, `invoices.py:395-412`) und der lexoffice-Abgleich (`lexoffice_service.py:161-165`). Sonst steht eine bezahlte Rechnung weiter auf `AUSSTEHEND` und würde ein zweites Mal eingezogen. Lösung: `record_payment` setzt bei vollem Betrag `EINGEZOGEN`, und die Arbeitsliste filtert zusätzlich auf offenen Restbetrag (siehe `GET /sepa/faellig`).
6. **Rücklastschrift (Phase B):** Eine Gegenbuchung über den Service. Das Modell erlaubt negative Beträge, nur das API-Schema nicht (`schemas/invoice.py:82`). Danach `lastschrift_status = RUECKLASTSCHRIFT` und Status `OFFEN` mit neuer Frist. Den Status muss der Service **ausdrücklich** zurücksetzen, weil `record_payment` bei `paid_amount = 0` nichts ändert (`invoice_service.py:277-281`). Ab da läuft die Rechnung normal ins Mahnwesen. Optional mit Gebühr als eigene Position.
7. **Skonto-Hinweis** (`pdf_service.py:337-349`): Bei Lastschrift wird er unterdrückt oder umformuliert, je nach Antwort auf Frage 5.

### 3.2 Endpunkte

Neuer Router `backend/app/api/v1/sepa.py` mit Präfix `/api/v1/sepa` und neuer Rechtegruppe `_deps_bank = _rollen(BUCHHALTUNG)`, also Admin und Buchhaltung, lesend wie schreibend (`main.py:91-104`). Vorbehaltlich Frage 8.

| Methode und Pfad | Zweck |
|---|---|
| `GET /sepa/kunden/{customer_id}/mandate` | Mandate des Kunden inkl. Historie (volle IBAN nur hier). Die Antwort enthält auch die **Gläubiger-ID** aus den Firmendaten, denn die Buchhaltung darf `/admin/settings` nicht lesen (`main.py:137`, `:807-811`) |
| `POST /sepa/kunden/{customer_id}/mandate` | Mandat anlegen; 409 bei schon aktivem Mandat oder doppelter Referenz; 422 bei ungültiger IBAN |
| `PATCH /sepa/mandate/{id}` | Kontoinhaber, IBAN, BIC, Bank ändern (Eintrag in `aenderungen`); Referenz und Datum nach erstem Einzug gesperrt |
| `POST /sepa/mandate/{id}/widerruf` | `widerrufen_am` setzen; stellt die Zahlungsart des Kunden auf Überweisung zurück und meldet offene `AUSSTEHEND`-Rechnungen |
| `PUT /sepa/kunden/{customer_id}/zahlungsart` | Umschalten Überweisung ↔ Lastschrift; Lastschrift verlangt aktives Mandat **und** gesetzte Gläubiger-ID (sonst 422) |
| `GET /sepa/faellig?bis=YYYY-MM-DD` | Arbeitsliste: `AUSSTEHEND`, `status IN (OFFEN, TEILBEZAHLT, UEBERFAELLIG)` (also kein Entwurf, nichts Bezahltes, nichts Storniertes), Restbetrag > 0, `sepa_hinweis IS NOT NULL`, `due_date <= bis`. Mit Kunde, Restbetrag, Einzugsdatum, Mandat, IBAN, Kennzeichen „überfällig seit X Tagen“ (intern, keine Mahnung) und „Hinweis nicht über das System versendet“, wenn `/send` nie lief |
| `POST /sepa/einzug` | `{invoice_ids, datum}` → bucht den Einzug (Regel 5) |
| `POST /sepa/ruecklastschrift/{invoice_id}` | Phase B (Regel 6) |
| `POST /sepa/rechnungen/{invoice_id}/einzugsdatum` | Einzugsdatum neu setzen (Regel 2), nur `AUSSTEHEND` ohne Zahlung |

Weitere Änderungen an bestehenden Endpunkten:
- **Kunden-Schema** (`schemas/customer.py:175-205`): **nur** `zahlungsart` und `lastschrift_aktiv: bool`, nur lesend. **Nicht** in `CustomerCreate` und `CustomerUpdate` aufnehmen, sonst kann die Halle es über `sales.py:139-141` umschalten. Keine IBAN im Kunden-Schema.
- **Rechnungs-Schema** (`schemas/invoice.py:161-214`): `zahlungsart`, `lastschrift_status`, `sepa_hinweis`. Der Hinweis enthält nur die maskierte IBAN und ist daher unter `_deps_geld` unbedenklich.
- **`/invoices/{id}/send`:** Für Lastschrift wird `Fällig am:` durch `sepa_hinweis` ersetzt (`invoices.py:259`). Den Mailtext baut `sepa_service`, damit der Umbau in B3 (mehrere Empfänger, Paket 3) ihn ohne Konflikt übernimmt.
- **Mehrere Empfänger (B3, Gernot 08.10.):** Der Hinweis steht einmal im Text der gemeinsamen Mail. Keine Zusatzarbeit.
- **Monatliche Sammelrechnung (B5):** Jede Monatsrechnung eines Lastschriftkunden bekommt automatisch Einzugsdatum und Hinweis. Ein Einzug je Monat. **Voraussetzung:** Der Sammellauf ruft `festschreiben` auf (Regel 2), denn heute setzt er `OFFEN` an `finalize_invoice` vorbei (`invoices.py:645`). Wenn Paket 3 die Monatsrechnung künftig automatisch als Entwurf vorschlägt, entsteht der Hinweis erst beim Freigeben. Entwürfe stehen nie in der Einzugsliste.
- **lexoffice** (`lexoffice_service.py:51-60`): Ist lexoffice aktiv, schreibt der Push den eingefrorenen `sepa_hinweis` in `remark`, sonst fehlt der Hinweis auf dem lexoffice-Beleg. Der Abgleich auf `paid` setzt `lastschrift_status = EINGEZOGEN` (Regel 5).
- **DATEV-Debitorenexport** (`sales.py:439-443`, `datev_service.py:241`): Die IBAN-Spalte **leer lassen**, solange der Export unter `_deps_auftraege` liegt. Später entweder unter `_deps_geld` verschieben oder ganz in B9 aufgehen lassen.

### 3.3 Oberfläche
- **Kundenformular** (`Customers.tsx:227-450`):
  - Neue Karte „Zahlung / SEPA-Lastschriftmandat“, **nur für Admin und Buchhaltung** (Rollen aus `frontend/src/context/AuthContext.tsx:86`; das Backend setzt es ohnehin durch). Darin steht auch die Auswahl *Überweisung / SEPA-Lastschrift (Mandat)*. Sie speichert über `PUT /sepa/kunden/{id}/zahlungsart` und **nicht** über `salesApi.updateCustomer`. Das Formular schickt heute sein ganzes `formData` an `PATCH /sales/customers` (`Customers.tsx:270-283`). Ein Feld `zahlungsart` dort liefe ins Leere oder öffnete die Lücke für die Halle wieder.
  - Die Karte erscheint wie Adressen und Ansprechpartner erst **nach dem ersten Speichern** (`Customers.tsx:427-437`), weil die Mandats-Endpunkte die Kunden-ID brauchen.
  - Inhalt der Karte:
    - Mandatsreferenz, Mandatsart (Basis/Firmen), Datum des Mandats, Kontoinhaber, IBAN mit Sofortprüfung und Gruppierung, BIC (optional), Bank.
    - **Gläubiger-ID nur zur Ansicht**, geliefert von `GET /sepa/kunden/{id}/mandate` (nicht von `/admin/settings`, das liefert der Buchhaltung 403). Den Link „in den Einstellungen ändern“ sieht nur der Admin.
    - Knopf „Widerrufen“ und eine Historie früherer Mandate.
  - Alle anderen Rollen sehen nur das Abzeichen „Zahlung per Lastschrift“.
  - Gernots fünf Felder sind damit alle in der Maske, die Gläubiger-ID eben nur zur Ansicht.
- **Einstellungen** (`Settings.tsx:104-154`): Die LocalStorage-Attrappe „Firmendaten“ wird durch eine echte Karte ersetzt. Sie liest und schreibt `/admin/settings`, nach dem Muster der `SmtpSettingsCard` (`:583ff`). Inhalt: Firmenname, Adresse, USt-IdNr., Steuernummer, Kontakt, Bank, IBAN, BIC, **Gläubiger-ID**, **Vorabankündigungsfrist**. Das behebt nebenbei, dass Gernot heute Fantasiewerte sieht.
- **Rechnungsliste** (`Invoices.tsx`):
  - Abzeichen „Lastschrift · Einzug 22.10.“
  - Knopf „Mahnung“ bei Lastschrift ausblenden (`:432-459`), außer nach einer Rücklastschrift.
  - Neuer Reiter „Lastschrift-Einzüge“ mit der Arbeitsliste, Ankreuzen und „Als eingezogen buchen“.
  - Nebenbei `KARTE` → `EC`/`KREDITKARTE` (`:814-820`).
- **Rechnungs-PDF:** neuer Abschnitt `payment_hint` in `DEFAULT_SECTIONS["RECHNUNG"]` (`document_template.py:33-45`), gerendert nach dem Summenblock (`pdf_service.py:335`):
  - Lastschrift → `sepa_hinweis`.
  - Überweisung → „Zahlbar bis {due_date} ohne Abzug unter Angabe der Rechnungsnummer.“ Damit kennt der Kunde das Datum, auf das sich die Mahnung beruft (1.5). Diese Zeile ändert alle Rechnungen; sie ist in der Vorlage abschaltbar. Bei Skontokunden „ohne Abzug“ weglassen, sonst widerspricht die Zeile dem Skonto-Hinweis (`pdf_service.py:337-349`). Weil das PDF live erzeugt wird (1.5), erscheint die Zeile auch beim erneuten Abruf alter Rechnungen. Deshalb nur drucken, wenn die Rechnung nach dem Release festgeschrieben wurde, oder den Text ebenfalls einfrieren.
  - Fehlt die Bank am Mandat, entfällt „bei der {bank}“ ganz, statt „bei der  ab“ zu drucken.
- **Vorlagen-Oberfläche:**
  - Textfeld `sepa_text` in `TEXT_FIELDS` (`DocumentTemplates.tsx:15-20`).
  - Die Platzhalter kommen in `PLACEHOLDERS_BY_TYPE["RECHNUNG"]` (`document_templates.py:34-48`), weil der Editor seine Liste von dort lädt. Dabei die vorhandenen Namen weiterverwenden (`{total_gross}`, `{due_date}`) und nur die neuen ergänzen (`{mandatsreferenz}`, `{glaeubiger_id}`, `{iban_maskiert}`, `{bank}`). Der Mustertext oben nutzt `{betrag}`/`{einzugsdatum}` nur zur Lesbarkeit.
  - Die Abschnittsliste muss für schon gespeicherte Vorlagen mit den Defaults zusammengeführt werden, sonst ist `payment_hint` dort nicht schaltbar (es bleibt aber eingeschaltet, `document_template_service.py:47-54`).
  - `build_dummy_invoice` (`document_template_service.py:164-191`) um die fehlenden Felder und um ein Lastschrift-Beispiel ergänzen. Die Vorschau ist heute schon kaputt (1.5), ohne Reparatur sieht Gernot den neuen Abschnitt im Editor nie.

### 3.4 Tests

Neue Datei `backend/tests/test_sepa_mandat.py`. Muster: `test_rollen.py:21-33` (`als_rolle`), `test_documents_preise.py:17-44` (`_pdf_text`), `test_dunning.py:8-49`, `test_storno.py`.

| # | Test | Erwartung |
|---|---|---|
| 1 | IBAN gültig, ungültig, mit Leerzeichen, klein geschrieben | 201 und normalisiert / 422 |
| 2 | Gläubiger-ID `DE98ZZZ09999999999` / `DE75ZZZ0002442146` (17 Zeichen) | ok / 422 „18 Zeichen erwartet“ |
| 3 | Zweites aktives Mandat oder doppelte Referenz | 409 |
| 4 | Rollen: `production_staff` und `sales` auf `/sepa/...` | 403; `accounting` und `admin` 200 |
| 5 | `GET /sales/customers` und `/sales/customers/{id}` für jede Rolle | JSON ohne Schlüssel `iban`, `kontoinhaber`, `mandatsreferenz` |
| 6 | `PATCH /sales/customers/{id}` mit `zahlungsart` als `production_staff` | 200, das Feld wird ignoriert (Pydantic verwirft unbekannte Felder, `CustomerUpdate` hat keine `extra`-Einstellung, `schemas/customer.py:127`); Zahlungsart unverändert |
| 7 | Lastschrift setzen ohne Mandat oder ohne Gläubiger-ID | 422 |
| 8 | Rechnung für Lastschriftkunden anlegen und festschreiben | Entwurf: vorläufiges `due_date`, noch kein Mandat. Nach dem Festschreiben: `zahlungsart=LASTSCHRIFT`, `due_date >= heute + Frist`, Bankarbeitstag (Fall Karfreitag) |
| 9 | Festschreiben (Finalisieren, `/send`, Sammellauf) | `sepa_hinweis` enthält Betrag, Datum, Referenz, Gläubiger-ID und maskierte IBAN, **nicht** die volle IBAN |
| 10 | Snapshot: IBAN am Mandat ändern, dann PDF der alten Rechnung | alter Text unverändert (`_pdf_text`) |
| 11 | `/send` mit gemocktem `send_email` | Text enthält den Hinweis, keine Zeile „Fällig am“, keine volle IBAN |
| 12 | Mahnwesen: Lastschriftrechnung 10 Tage nach Fälligkeit | bleibt `OFFEN` in Service und Task; `send_payment_reminders` → 0; `/payment-reminder` → 400; `is_overdue` False |
| 13 | Einzug buchen | `BEZAHLT`, Zahlung `LASTSCHRIFT`, `letzter_einzug_am` gesetzt |
| 14 | Gutschrift/Storno zu einer Lastschriftrechnung | kein Lastschrifthinweis, keine Lastschrift |
| 15 | Widerruf mit offener `AUSSTEHEND`-Rechnung | Kunde → Überweisung, Antwort listet die Rechnung |
| 16 | Phase B: Rücklastschrift | Rechnung `OFFEN`, `RUECKLASTSCHRIFT`, danach mahnfähig |
| 17 | Sammellauf (`POST /invoices/batch-run/commit`) mit einem Lastschrift- und einem Überweisungskunden | Lastschriftrechnung hat `sepa_hinweis` und Einzugsdatum, die andere nicht |
| 18 | Altrechnung mit `zahlungsart = NULL`, 10 Tage überfällig | wird `UEBERFAELLIG` und bekommt Stufe 1 (NULL-Falle). Dazu bleiben `test_dunning.py`, `test_production_readiness.py:117-263` und `test_services.py:271-291` grün |
| 19 | Entwurf eines Lastschriftkunden | erscheint **nicht** in `GET /sepa/faellig` |
| 20 | Lastschriftrechnung von Hand über `POST /invoices/{id}/payments` voll bezahlt | verschwindet aus `GET /sepa/faellig`, `lastschrift_status = EINGEZOGEN` |
| 21 | Entwurf: Kunde per `PATCH /invoices/{id}` von Lastschrift- auf Überweisungskunden umgestellt, dann festschreiben | kein Mandat, kein Hinweis; umgekehrt das Mandat des **neuen** Kunden |
| 22 | `PATCH /invoices/{id}` mit `{"status": "OFFEN"}` | Status bleibt `ENTWURF` (Feld ignoriert) oder 422, in keinem Fall `OFFEN` ohne Festschreiben |
| 23 | Kunde ohne Belege, aber mit Mandat, löschen | 204, Kunde deaktiviert, Mandat bleibt; kein 500 |
| 24 | `GET /document-templates/RECHNUNG/preview.pdf` | 200 (heute `AttributeError`, 1.5) |

Frontend: `tsc --noEmit` und Build. Ein Playwright-Lauf für die Mandatskarte ist optional.

Laufen mit der Wurzel-`.venv`. Die bekannte Baseline von 15 Fehlern darf nicht wachsen. Hinweis: Die Test-SQLite (`tests/conftest.py:16`) schaltet `PRAGMA foreign_keys` nicht ein wie die Mandanten-DB (`tenancy.py:131`). Test 23 muss das Pragma selbst setzen, sonst bleibt der 500 unentdeckt.

### 3.5 Aufwand

| Baustein | Aufwand |
|---|---|
| Datenmodell, Migration, Prüfer (IBAN, Gläubiger-ID, Referenz, Bankarbeitstag) | S |
| Mandats-Router, Zahlungsart, Rechtegruppe | S |
| Einzugsdatum, Festschreiben an allen Wegen nach `OFFEN` (Finalisieren, `/send`, Sammellauf, Storno, `PATCH`-Sperre), PDF-Abschnitt, Mailtext, Vorlagentext, lexoffice-`remark` | M |
| Vorlagen-Vorschau reparieren (Ersatzobjekt) | S |
| Ausnahme vom Mahnwesen (Prädikat, 2 Tasks, Service, Property, Endpunkt, Knopf) | S |
| Arbeitsliste „Einzug fällig“ + Einzug buchen | S–M |
| Frontend: Mandatskarte, echte Firmendaten-Karte, Rechnungsliste, Vorlagenfeld | M |
| Tests | S–M |
| **Kern (Phase A)** | **M** |
| Phase B: Rücklastschrift mit Gebühr | S–M |
| Später, nur als Option: SEPA-XML (pain.008) aus der Arbeitsliste, DATEV-Debitoren mit IBAN, Mandats-Scan als geschützter Anhang | — |

**Reihenfolge:**
1. Nach Paket 1, wegen des gemeinsamen Mahn-Prädikats und weil der Storno sauber sein muss.
2. Parallel zu oder nach dem Versand-Umbau in Paket 3 (B3). Den Textbaustein gleich als Service anlegen, damit es keinen Konflikt gibt. Paket 3 („Nummer beim Finalisieren“) ändert dieselben Wege nach `OFFEN`. Die Festschreib-Funktion aus Regel 2 deshalb **einmal** anlegen und von beiden nutzen lassen.

---

## 4. Risiken

1. **Doppelzahlung:** Die Firmen-IBAN steht in jeder Fußzeile (`pdf_service.py:173-178`). Ohne „bitte nicht überweisen“ zahlt mancher Kunde zusätzlich. Ist im Text oben enthalten.
2. **Vorabankündigung ohne Datum:** Mit Gernots Wortlaut „frühestmöglich“ fehlt das Fälligkeitsdatum (Fachwissen, 1.11). Das kann zu Rückgaben oder Beschwerden führen, bei CORE 8 Wochen lang ohne Begründung.
3. **Nachträglich veränderte Rechnungen:** Ohne Snapshot schreibt das live erzeugte PDF (`invoices.py:466-494`) alte Rechnungen um, sobald sich das Mandat ändert. Gleiches Muster besteht heute schon bei der Anschrift (`pdf_service.py:256`). Nebenbefund für Paket 1 und 3.
4. **Rechteleck:** IBAN-Felder am Kunden-Schema wären für `production_staff` lesbar **und änderbar** (`main.py:122`, `sales.py:139-141`). Ebenso landete eine IBAN im DATEV-Debitorenexport (`sales.py:439`) oder ein Mandats-Scan in den Anhängen (`main.py:133`). Deshalb gibt es eigene Tabelle, eigenen Router und kein Feld in `CustomerUpdate`.
5. **Laufende Mahnautomatik:** Die Statuswechsel um 08:00 passieren sicher. Ob die Mahnmails um 09:00 rausgehen, hängt an der Umgebungsvariable `SMTP_HOST` (`core/email.py:50`). Das ist im Betrieb zu prüfen, weil ich keinen Produktionszugriff habe.
   - Bis T2 live ist: Lastschrift-Einzüge sofort als Zahlung erfassen. Oder Gernot darauf hinweisen, dass solche Rechnungen als „überfällig“ erscheinen.
   - Die Mahnmail sagt „bitte überweisen“ (`core/email.py:89`).
6. **Gutschriften bei Lastschriftkunden** (Storno, monatliche Pfandverrechnung aus T3): Einen negativen Betrag kann man nicht einziehen. Ohne Regel (Frage 6) entstehen Erstattungen von Hand.
7. **Skonto:** Der PDF-Hinweis „bei Zahlung innerhalb X Tagen …“ (`pdf_service.py:337-349`) passt nicht zur Lastschrift. Ob der Abzug beim Einzug vorgenommen wird, ist offen (Frage 5).
8. **Firmenlastschrift (B2B):** Hat die Bank des Kunden das Mandat nicht bestätigt, kommt die Lastschrift zurück. Die Mandatsart muss deshalb gepflegt werden.
9. **Ablauf nach 36 Monaten:** `letzter_einzug_am` vorsehen. Eine Warnung genügt vorerst.
10. **Datenschutz:**
    - Die IBAN liegt im Klartext in der Mandanten-SQLite und in den WAL-Backups.
    - Bei Einzelunternehmern (Gastro) ist sie ein personenbezogenes Datum.
    - Feldverschlüsselung wäre mit dem installierten `cryptography` möglich, verlangt aber Schlüsselverwaltung. Empfehlung: vorerst Rechte und Änderungsprotokoll, Verschlüsselung als Option.
11. **Mehrmandantenfähigkeit:** Betreff und Gruß der Mail sind fest „Minga Greens“ (`invoices.py:254`, `:260`). Bei Gelegenheit auf `COMPANY_NAME` umstellen.
12. **Einzugsdatum nach spätem Versand:** Wird eine Rechnung finalisiert und erst Tage später versendet, oder als PDF manuell verschickt, kann die Frist reißen. Das fangen der 409 bei `/send` und „Einzugsdatum neu setzen“ ab. Beim manuellen Versand außerhalb des Systems greift das nicht. Die Einzugsliste kennzeichnet solche Rechnungen („Hinweis nicht über das System versendet“).
13. **Weg am Festschreiben vorbei:** Heute führen fünf Wege nach `OFFEN` (1.6), darunter der Sammellauf, der für B5 der Hauptweg wird. Wird nur `finalize_invoice` angepasst, gehen Monatsrechnungen von Lastschriftkunden **ohne** Vorabankündigung raus. Trotzdem stehen sie als `OFFEN` da und laufen ins Mahnwesen. Deshalb eine Festschreib-Funktion für alle Wege und Test 17/22.
14. **Doppelter Einzug:** Bucht jemand den Einzug von Hand als Zahlung, oder setzt der lexoffice-Abgleich `BEZAHLT` (`lexoffice_service.py:161-165`), dann bliebe die Rechnung ohne Filter auf Restbetrag und Status in der Einzugsliste stehen (Regel 5, Test 20).
15. **Mandantentrennung bei Firmendaten:** `get_setting` fällt auf Umgebungsvariablen zurück, und die gelten für alle Mandanten (`settings_service.py:55-62`). Für die Gläubiger-ID deshalb `env_fallback=False`. Für `COMPANY_IBAN` und Co. besteht das Muster schon heute (`pdf_service.py:112-113`), das ist ein Nebenbefund.
16. **Mandat am falschen Kunden:** Wird das Mandat schon beim Anlegen an die Rechnung gehängt, zieht ein Kundenwechsel im Entwurf (`Invoices.tsx:1002-1009`) vom Konto des alten Kunden ein. Deshalb wird es erst beim Festschreiben bestimmt (Regel 2, Test 21).

---

## 5. Fragen an Gernot bzw. Steuerberater (nur, was der Code nicht beantworten kann)

1. Welche Mandatsart haben Ihre Kunden unterschrieben: SEPA-Basislastschrift (CORE) oder SEPA-Firmenlastschrift (B2B)?
2. Steht in Ihrem Mandatsformular eine verkürzte Frist für die Vorabankündigung (z. B. 1 oder 5 Tage), oder gelten die üblichen 14 Tage?
3. Ist es für Sie in Ordnung, dass im Hinweis statt „zum frühest möglichen Zeitpunkt“ ein konkretes Einzugsdatum steht (z. B. „am 22.10.2026“)? Und was heißt „frühestmöglich“ bei Kunden mit Zahlungsziel (z. B. 14 Tage netto)? Ziehen Sie erst am Ende des Zahlungsziels ein (so ist der Vorschlag gerechnet), oder schon nach Ablauf der Ankündigungsfrist?
4. Wie lautet Ihre Gläubiger-ID genau? Das Beispiel DE75ZZZ0002442146 hat 17 statt 18 Zeichen.
5. Ziehen Sie bei Lastschriftkunden mit Skonto den Betrag abzüglich Skonto ein oder den vollen Rechnungsbetrag?
6. Wie sollen Gutschriften und Stornos bei Lastschriftkunden ausgeglichen werden: Überweisung an den Kunden oder Verrechnung mit dem nächsten Einzug?
7. Wie reichen Sie Lastschriften heute bei der Bank ein: Einzeleingabe im Online-Banking, Datei-Upload oder über ein Buchhaltungsprogramm?
8. Wer darf Bankdaten und Mandate sehen und pflegen: nur Sie als Admin, oder auch Buchhaltung bzw. Vertrieb?
9. Welche Kunden haben heute schon ein Lastschriftmandat, und gibt es offene Rechnungen an diese Kunden, die eingezogen werden?
10. Sollen bei einer Rücklastschrift die Bankgebühren an den Kunden weiterberechnet werden?
11. (Steuerberater) Sollen Debitoren-Stammdaten mit IBAN und Mandatsreferenz an DATEV übergeben werden, und soll der Lastschrifteinzug dort als eigene Zahlungsart erscheinen?
12. Übertragen oder versenden Sie Rechnungen auch über lexoffice? Dann muss der Lastschrifthinweis auch auf den lexoffice-Beleg (siehe 3.2).

---

## 6. Prüfvermerk (Zweitprüfung am Code, 08.10.)

Alle übrigen Datei:Zeile-Belege aus 1.1 bis 1.11 habe ich nachgeschlagen und als zutreffend befunden. `tests/test_dunning.py` ist erneut grün gelaufen (1 passed, ohne Cache und Bytecode). Korrigiert oder ergänzt wurde Folgendes:

1. **Enum-Wert:** Der Wert lautet `"LASTSCHRIFT"`, nicht `"SEPA-Lastschrift"` (`enums.py:54`). Das stand nur im Kommentar.
2. **Wege nach `OFFEN`:** Es sind fünf, nicht zwei. Neu belegt sind der Sammellauf (`invoices.py:645`), die Stornorechnung (`invoice_service.py:348`) und `PATCH` mit `status` (`schemas/invoice.py:153`, `invoices.py:157-159`). Regel 2 ist deshalb jetzt eine Festschreib-Funktion für alle Wege. Ohne sie gingen B5-Monatsrechnungen ohne Hinweis raus.
3. **Zeitpunkt für Mandat und Zahlungsart:** jetzt beim Festschreiben, nicht mehr in `create_invoice`. Grund: Im Entwurf kann der Kunde noch wechseln (`schemas/invoice.py:149`, `Invoices.tsx:1002-1009`).
4. **Einzugsliste:** Sie hätte Entwürfe gezeigt, weil `AUSSTEHEND` schon beim Anlegen gesetzt wurde. Sie hätte auch von Hand oder über lexoffice bezahlte Rechnungen gezeigt. Jetzt filtert sie auf Status, Restbetrag und Snapshot.
5. **NULL-Falle im Mahn-Prädikat** für Altrechnungen ergänzt, dazu die vorhandenen Regressionstests.
6. **Rücklastschrift:** `record_payment` setzt den Status bei `paid_amount = 0` nicht zurück (`invoice_service.py:277-281`).
7. **Kunden löschen:** Kunden ohne Belege werden hart gelöscht (`sales.py:165-167`), und die Fremdschlüssel sind aktiv (`tenancy.py:131`). Die Aussage „Kunden werden nur deaktiviert“ war also unvollständig. `can_be_deleted` muss Mandate berücksichtigen.
8. **Gläubiger-ID in der Kundenmaske:** Die Buchhaltung darf `/admin/settings` nicht lesen (`main.py:137`). Die ID kommt deshalb über den SEPA-Router.
9. **Umgebungs-Rückfall** in `get_setting` (`settings_service.py:55-62`) als Mandanten-Risiko ergänzt; die Gläubiger-ID wird ohne Rückfall gelesen.
10. **lexoffice als zweiter Belegweg** ergänzt (`lexoffice_service.py:51-60`, `:161-165`).
11. **Vorlagen:** Die Platzhalter liegen im Backend (`document_templates.py:34-48`). `apply_placeholders` wird von keinem PDF aufgerufen; die frühere Formulierung „ersetzt durch“ war irreführend. Die Rechnungsvorschau ist heute kaputt (`AttributeError` an `pdf_service.py:247`, lokal reproduziert).
12. **Test 6:** Erwartung präzisiert (200, Feld ignoriert). Test 8 angepasst. Tests 17 bis 24 neu.
13. **JSON-Änderungsprotokoll:** Hinweis auf die fehlende Mutationserkennung ergänzt.
14. **Kundenformular:** Die Zahlungsart-Auswahl liegt in der geschützten Karte und speichert über `/sepa`. Die Karte erscheint erst nach dem ersten Speichern.
15. **`dateutil`:** als direkte Abhängigkeit belegt (`requirements.txt:34`).
16. **Fragen 3 und 12** ergänzt: Was heißt „frühestmöglich“ bei Zahlungsziel? Ist lexoffice im Einsatz?
