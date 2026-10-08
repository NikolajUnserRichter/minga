# T3 — Pfand: Kunden-Option oder monatliches Leergutkonto mit Retouren

Stand: `main` @ `c4a1832`, nur Code gelesen, keine Produktionsdaten. **Belegt** heißt: im Code gesehen, mit Datei:Zeile. **Annahme** heißt: nicht im Code prüfbar.
*Prüfnachtrag:* Während der Prüfung ist `main` auf `efcea00` (A6-Hotfix) weitergegangen. Geändert wurden nur `api/v1/imports.py` (+5 Zeilen: `:97-98` → `:102-103`, `:227-228` → `:232-233`), `frontend/src/pages/Orders.tsx` und ein neuer Test. Alle anderen Belege gelten unverändert. Die `imports.py`-Belege unten beziehen sich auf `c4a1832`.
Bezug: Spezifikation `docs/superpowers/specs/2026-10-08-gernot-feedback-abgleich.md` (A3, B4, B5, Paket 1, offene Entscheidungen 4 und 6).

**Kurzantwort an Gernot:** Ja, das geht, und sein zweiter Vorschlag ist der bessere. Wir empfehlen ihn mit einer Ausnahme für IFCO-Clearing-Kunden. Pro Kunde gibt es dann eine Einstellung mit drei Werten: *je Lieferung auf der Rechnung* (heutiges Verhalten), *monatlich über das Leergutkonto* oder *gar nicht (IFCO-Clearing)*. Bei „monatlich“ zählt man Rückgaben nur noch als Stückzahl. Am Monatsende entsteht ein Beleg mit „ausgegeben“ und „zurück“. Stornos und Einzelgutschriften fürs Pfand fallen weg. **Vorbehalt:** Die monatliche Abrechnung setzt voraus, dass der Steuerberater die Kisten als Transporthilfsmittel einordnet und die Saldierung billigt (R1, Fragen an den Steuerberater 1–4). Bis dahin ist nur der Teil „gar nicht (IFCO)“ ohne Risiko.

---

## 1. Ist-Zustand (belegt)

### 1.1 Produktstamm
- Es gibt die Kategorie `PFAND`, gedacht für Pfandgebinde mit 19 % (`backend/app/models/product.py:29`).
- Jedes Produkt hat die Felder `is_deposit` und `deposit_value` (`models/product.py:258-260`).
- Wer ein Produkt mit Kategorie PFAND anlegt, bekommt automatisch `is_deposit = true`. Ist kein Steuersatz angegeben, setzt das System `STANDARD` (19 %) (`api/v1/products.py:87-95`).
- Im Import heißen die Spalten `pfand` und `pfandwert` (`api/v1/imports.py:97-98`). Die Beispielzeile hat Kategorie `PACKAGING` und Satz `STANDARD` (`imports.py:227-228`). Dass der Import den Pfandsatz auf 7 % zurücksetzt (Spezifikation A3), ist auch im Code belegt: Bei leerer Spalte `tax_rate` setzt `_import_products` `REDUZIERT` und überschreibt damit bestehende Produkte (`imports.py:422`, `:424-428` @ `c4a1832`).
- *Prüfnachtrag:* Die Automatik „Kategorie PFAND ⇒ `is_deposit`“ gibt es **nur** im Anlage-Endpunkt (`products.py:89-90`), nicht im Import. Ein importierter Artikel mit Kategorie `PFAND` und leerer Spalte `pfand` bekommt kein Pfandkennzeichen, weil leere Zellen `None` ergeben (`imports.py:150-152` @ `c4a1832`). Jede Regel, die auf `is_deposit` filtert, übersieht ihn (siehe R3).
- **`deposit_value` wird nirgends verwendet.** Gespeichert und angezeigt wird er nur in Schema, Service und `frontend/src/pages/Products.tsx:590-599`. Der Hinweistext dort sagt, dieser Wert werde „auf der Rechnung als ‚darin enthaltenes Pfand‘ ausgewiesen“ (`Products.tsx:599`). Das stimmt nicht. Ausgewiesen wird der Brutto-Zeilenbetrag der Pfandposition (`models/invoice.py:170-172`), und der kommt aus `base_price` bzw. dem Kundenpreis.

### 1.2 Bestellung: Pfand ist eine Handposition
- **Pfandzeilen entstehen nicht automatisch.** Wer Pfand berechnen will, wählt das Pfandprodukt von Hand als normale Position:
  - Das Bestellformular lädt alle aktiven Produkte (`frontend/src/components/domain/CreateOrderModal.tsx:64`) und schickt immer fest `REDUZIERT` mit (`:177`).
  - `create_order` übernimmt die Positionen 1:1 und fügt nichts hinzu (`api/v1/sales.py:1018-1031`).
  - *Prüfnachtrag, weitere Codepfade:* Bestellzeilen entstehen außerdem in `add_order_line` (`sales.py:1289`, Zeile `:1328`), im Bestell-Import (`imports.py:610` @ `c4a1832`), im Shopify-Import (`services/shopify_service.py:208`, fest 19 %) und im Abo-Lauf (`subscription_tasks.py:149`). Keiner dieser Wege erzeugt eine Pfandzeile automatisch.
  - *Prüfnachtrag, Rollen:* Mitarbeiter mit `production_staff` können das Pfandprodukt heute **gar nicht auswählen**. `GET /api/v1/products` hängt an `_deps_vertrieb` ohne `PRODUKTION` (`main.py:124`, `:716-720`). Das Formular fällt dann auf die Saatgutliste zurück (`CreateOrderModal.tsx:68-97`) und schickt deren ID als `product_id`. `create_order` antwortet darauf mit 404 (`sales.py:938-943`). Gernot will aber, dass die Mitarbeiter Bestellungen anlegen (B8). Das betrifft jede Pfandregel, die eine Pfandzeile über `product_id` erkennt. (Belegt über die Codekette, im Browser nicht nachgestellt.)
- `OrderLine` hat kein eigenes Pfandkennzeichen (`models/order.py:226-311`). Ob eine Zeile Pfand ist, sieht man nur über `product_id` und dann `Product.is_deposit`.
- Die Menge muss größer als 0 sein (`schemas/order.py:32`). Eine Rückgabe als Minusposition in einer Bestellung geht also nicht.
- Die Einheiten `KISTE_12` und `KISTE_6` (`tenancy.py:376-377`, `CreateOrderModal.tsx:420-421`) sind reine Mengeneinheiten. Sie erzeugen keine Pfandzeile.
- Abo-Bestellungen haben genau eine Position, und die hat keine `product_id` (`tasks/subscription_tasks.py:149-158`; vgl. A5 und B6). Kisten aus Abo-Lieferungen tauchen damit nirgends auf.
- Nebenbefund: Pfandzeilen landen im Sortenbedarf und im Packplan. Der Else-Zweig zählt jede Einzelposition (`api/v1/production.py:712-765`, besonders `:763-765`).
- Bestandsabzug bei Lieferung: Eine Pfandzeile in „Stk“ lässt sich nicht in Gramm umrechnen. Das System gibt nur eine Warnung aus und zieht nichts ab (`services/order_fulfillment_service.py:41-54`, `:199-204`).

### 1.3 Lieferschein und Packliste
- Das Lieferschein-PDF druckt alle Bestellpositionen, also auch die Pfandzeile (`services/pdf_service.py:759-780`). Ein Feld für zurückgenommenes Leergut gibt es nicht.
- `PackingListItem` hat die Felder `is_returnable_container`, `container_type` und `container_count` (`models/documents.py:178-183`). Das Packlisten-PDF hat dafür einen eigenen Block „Pfand-Container (Mehrweg)“ (`pdf_service.py:846-879`).
  - **Diese Felder werden nie befüllt.** Die Oberfläche legt den Lieferschein immer mit `{}` an, und zwar an zwei Stellen: `OrderDocumentsModal.tsx:118` und der Packlisten-Knopf im Tagesplan (`frontend/src/pages/Tagesplan.tsx:61`). Dann werden die Positionen 1:1 aus den Bestellzeilen übernommen, mit `is_returnable_container = false` (`api/v1/documents.py:230-255`).
  - Befüllt wird der Block nur in der Vorschau der Belegvorlagen (`services/document_template_service.py:241-243`).
- Beim Quittieren gibt man nur Name und Datum ein, keine Leergutmenge (`api/v1/documents.py:278-326`, `OrderDocumentsModal.tsx:255-271`).
- *Prüfnachtrag:* Auch die **Auftragsbestätigung** druckt jede Bestellzeile mit Preis und die Bestellsummen, also auch Pfand (`pdf_service.py:688-716`). Nach Gernots Antwort zu B8 legen die Mitarbeiter AB an und versenden sie.

### 1.4 Rechnung
- `InvoiceLine.is_deposit` gibt es (`models/invoice.py:281-282`). Gesetzt wird es nur in `add_line`, und nur wenn eine `product_id` mitkommt (`services/invoice_service.py:163`).
- `Invoice.total_deposit` ist die Bruttosumme der Pfandzeilen. Sie erscheint nachrichtlich als „darin enthaltenes Pfand“ (`models/invoice.py:170-172`, `pdf_service.py:321-327`, `frontend/src/pages/Invoices.tsx:1307-1313`).
- Eine Rechnung aus einer Bestellung übernimmt alle Zeilen, auch Pfand, mit dem Steuersatz der Bestellzeile (`invoice_service.py:193-208`).
- Die Sammelrechnung fasst nach Beschreibung, Einheit, Preis und Satz zusammen und reicht keine `product_id` weiter (`api/v1/invoices.py:564-566`, `:618-625`). Folgen:
  - `is_deposit` bleibt `false`.
  - Der Pfandhinweis fehlt.
  - ~~Pfand lässt sich dort heute nicht herausfiltern. Der A3-Fix „Sammelrechnung übergibt `product_id`“ ist Voraussetzung.~~ *Korrigiert:* Ein Filter ist schon heute möglich. `_aggregiere` läuft über die **Bestellzeilen** (`invoices.py:564`), und die tragen `product_id` samt Beziehung `product` (`models/order.py:248-250`, `:309`). Ein Ausschluss über `line.product.is_deposit` vor der Aggregation braucht den A3-Fix nicht. Der A3-Fix bleibt nötig, damit Pfandzeilen in der Sammelrechnung `is_deposit` und den Pfandhinweis bekommen (Kunden mit *je Lieferung*).
- *Prüfnachtrag:* Der **Jahresrabatt des Kunden** wird bei jeder neuen Rechnung automatisch gesetzt (`invoice_service.py:60-62`). Er mindert die Zwischensumme über **alle** Zeilen, auch Pfand (`models/invoice.py:147-152`, `:158-161`). `total_deposit` rechnet dagegen ohne Rabatt (`models/invoice.py:171`). Folgen:
  - Bei Kunden mit Jahresrabatt wird Pfand heute rabattiert, und der Hinweis „darin enthaltenes Pfand“ ist zu hoch.
  - Mit `discount_percent=0` lässt sich das nicht abschalten, denn 0 gilt als „nicht überschrieben“ (`invoice_service.py:61`).
- **Eine Rückgabe lässt sich nirgends gutschreiben.**
  - Neue Rechnungszeilen brauchen eine Menge größer 0 (`schemas/invoice.py:37`) und einen Preis von mindestens 0 (`:28`).
  - Negative Zeilen entstehen nur intern beim Storno (`invoice_service.py:333-345`).
  - Der PATCH einer Zeile hat keine Grenze (`schemas/invoice.py:44-51`). Das wäre ein technisches Schlupfloch, kein Ablauf.
- Ein Storno erzeugt nur dann einen Gegenbeleg, wenn `total > 0` (`invoice_service.py:319`). Einen Beleg mit negativem Saldo kann man mit der heutigen Logik nicht sauber stornieren.
- Belege im Status OFFEN mit Fälligkeit laufen in die Überfälligkeitsprüfung und ins Mahnwesen (`invoice_service.py:355-379`, `tasks/invoice_tasks.py:81ff`). Für Stornobelege ist das schon als Paket-1-Punkt geplant. *Prüfnachtrag:* Die Überfälligkeitsprüfung gibt es **zweimal** mit je eigener Abfrage: `InvoiceService.check_overdue_invoices` (`invoice_service.py:362-388`) und den täglich eingeplanten Task `tasks/invoice_tasks.py:28-56` (Job `scheduler_service.py:98`). Ein Mahnstopp für Minus- oder Leergutbelege muss beide Stellen und den Mahnlauf (`invoice_tasks.py:81`) abdecken.
- *Prüfnachtrag:* Belege vom Typ `GUTSCHRIFT` lassen sich nicht stornieren (`invoice_service.py:303-304`). Ein Erstattungsbeleg fürs Leergut darf diesen Typ deshalb nicht bekommen.
- Für DATEV gibt es nur die Erlöskonten 8300, 8400 und 8100 (`models/invoice.py:381-388`), kein eigenes Pfandkonto.
- Der Rechnungstyp `GUTSCHRIFT` steht heute für „Gutschrift/Stornorechnung“ (`models/enums.py:43`).

### 1.5 Kunde
- Am Kunden gibt es kein Merkmal für Pfand oder Abrechnungsart (`models/customer.py:155-191`). `pfand_via_clearing` existiert noch nicht; die Spezifikation führt es bei B4 als fehlend.
- Vorbild für ein Kundenmerkmal mit Wirkung auf Belege ist `show_prices_on_delivery_note`:
  - Modell: `customer.py:182`
  - Migration: `tenancy.py:304`
  - Schema: `schemas/customer.py:115/163/194`
  - Formular: `Customers.tsx:406-414`
- **Warnbeispiel:** `packaging_fee_amount` und `packaging_fee_percent` werden gespeichert, aber nirgends verrechnet (`customer.py:176-179`; laut grep nur Schema, Migration und Formular). Eine Kundeneinstellung ohne Wirkung darf sich hier nicht wiederholen.

### 1.6 Lager
- Es gibt den Artikeltyp `PFANDKISTE` im Verpackungslager (`models/inventory.py:45`, `:340`) und einen Wareneingang dafür (`Inventory.tsx:927-1049`).
- Dieser Lagerartikel ist nicht mit dem Pfandprodukt (`Product.is_deposit`) verbunden.
- Den Bewegungstyp `RUECKGABE` gibt es (`models/inventory.py:36`), er wird aber nie gebucht. Er taucht nur im Report-Mapping (`api/v1/reports.py:41`) und als Anzeigetext „Retoure“ auf (`frontend/src/pages/Warenfluss.tsx:24`).

### 1.7 Was wir wiederverwenden können
- **Migration:** Neue Tabellen legt `create_all` bei jedem Start an (`tenancy.py:255`), für neue Mandanten auch beim Anlegen (`tenancy.py:228-231`). Neue Spalten kommen über `_add_col_if_missing`, nur per `ADD COLUMN` (`tenancy.py:270-282`). *Prüfnachtrag:* Der nächtliche Demo-Reset kopiert nur den Golden-Seed zurück und ruft weder `create_all` noch `_auto_migrate` auf (`services/demo_reset_service.py:58-71`). Siehe R11.
- **Schutz vor Doppelabrechnung:**
  - `delivery_notes.invoice_id` (`models/documents.py:88-93`); ein Storno setzt es zurück (`invoice_service.py:310-316`).
  - Herkunftstabelle `InvoiceLineSource` (`models/invoice.py:353-369`).
- **Leistungszeitraum am Beleg:** `service_period_start/_end` (`models/invoice.py:59-62`).
- **Monatsjob je Mandant:** Das Muster gibt es schon (`services/scheduler_service.py:30-57`, Job am Monatsersten in `:100`). *Prüfnachtrag:* Einen Speicher für Hinweise oder Benachrichtigungen gibt es nicht (kein Modell in `backend/app/models/`). Ein Job, der „nur einen Hinweis“ erzeugt, hätte also kein Ziel (siehe 4.3).
- **Gemeinsamer Lieferpunkt:** Beide Wege nach `GELIEFERT` rufen `deduct_inventory_for_order` auf (`sales.py:1229-1238`, `documents.py:308-312`). Die Funktion läuft über `inventory_deducted_at` nur einmal (`order_fulfillment_service.py:130-131`). *Prüfnachtrag:* Es gibt einen dritten Weg. Der Bestell-Import legt Bestellungen direkt mit `GELIEFERT` an, ohne Bestandsabzug (`imports.py:547-551` @ `c4a1832`; seit `efcea00` nur noch bei Lieferdatum in der Vergangenheit). Auf diesem Weg entstünde keine Leergut-Ausgabe (siehe R-3).
- **Rollen:**
  - Die Belegkette dürfen auch die Mitarbeiter bedienen (`main.py:129`, Router `:794-799`).
  - Rechnungen dürfen nur Admin, Vertrieb und Buchhaltung (`main.py:125`, Router `:740-744`).
  - Das passt zu Gernots Antwort auf B8 (Mitarbeiter legen Bestellungen und Belege an, Rechnungen bleiben beim Admin), aber **nur, solange die Mitarbeiter-Logins `production_staff` bleiben**. Mit der Rolle `sales` kämen sie an die Rechnungen (`main.py:125`).
  - *Prüfnachtrag:* `production_staff` sieht die Kundenseite nicht im Menü (`frontend/src/components/common/Layout.tsx:178-181`: ADMIN, SALES, ACCOUNTING) und kann den Produktkatalog nicht lesen (siehe 1.2). Auf eine Rückgabe-Erfassung in der Kundenansicht kommt die Halle deshalb nicht (siehe 4.4).

---

## 2. Lücken gegenüber Gernots Wunsch

| # | Lücke | Beleg |
|---|---|---|
| L1 | Kein Kundenmerkmal: Pfand steht immer auf der Rechnung, auch bei IFCO-Clearing-Kunden wie Ökoring | 1.4, 1.5 |
| L2 | Keine Erfassung von Rückgaben, kein Kistensaldo je Kunde | 1.2, 1.3 |
| L3 | Rückgaben lassen sich nicht gutschreiben, nur per Storno des ganzen Belegs. Genau das „Hin- und Herbuchen“, das Gernot loswerden will | 1.4 |
| L4 | Die Sammelrechnung reicht keine `product_id` an die Rechnungszeile weiter. Pfandzeilen dort haben daher weder `is_deposit` noch Pfandhinweis. Herausfiltern ließen sie sich aber schon heute über die Bestellzeile (1.4, korrigiert) | `invoices.py:564-566`, `:618-625` |
| L5 | Pfand hängt an einer Handposition: wird sie vergessen, wird nichts berechnet. Abos haben gar kein Pfand | 1.2 |
| L6 | Das Lager `PFANDKISTE` ist weder mit Lieferungen noch mit Rückgaben verbunden | 1.6 |
| L7 | Belege mit negativem Saldo: laufen ins Mahnwesen, Storno erst ab `total > 0`, Bezeichnung „Gutschrift“ | 1.4 |
| L8 | Pfandzeilen verfälschen Sortenbedarf und Packplan | `production.py:763-765` |
| L9 | *(Prüfnachtrag)* Der Jahresrabatt rabattiert auch Pfand, und der Pfandhinweis rechnet ohne Rabatt | `invoice_service.py:60-62`, `models/invoice.py:147-171` |
| L10 | *(Prüfnachtrag)* Mitarbeiter (`production_staff`) können kein Produkt, also auch kein Pfandprodukt, auswählen und kommen nicht auf die Kundenseite | `main.py:124`, `:716-720`; `Layout.tsx:178-181` |

---

## 3. Bewertung der Varianten

| Kriterium | **A** Kunden-Option „Pfand nicht auf Rechnung“ (= Paket-1-Merkmal) | **B** Leergutkonto für alle, Pfand nie auf der Rechnung | **C** Kunden-Einstellung mit drei Werten |
|---|---|---|---|
| Ökoring / IFCO-Clearing richtig | ja | **nein**: der Monatslauf würde Pfand berechnen, das über IFCO abgerechnet wird | ja (Wert *gar nicht*) |
| Rückgaben ohne Storno oder Gutschrift | **nein**: Knuspr bekommt Pfand je Rechnung, Rückgaben bleiben ohne Weg (L3) | ja | ja (Wert *monatlich*) |
| Deploy ändert nichts von selbst | ja | nein: alle Kunden wechseln sofort | ja (Standardwert *je Lieferung*) |
| Steuerliches Risiko | gering | mittel: Monatsabrechnung und Saldierung sind vom Steuerberater zu bestätigen | wie B, aber kundenweise und schrittweise einführbar |
| Aufwand | S (ohnehin Teil von Paket 1) | M–L | Stufe 1: S (in Paket 1), Stufe 2: M–L |
| Bestehende Tests | bleiben grün | *(Prüfnachtrag)* brechen: `test_gernot_260821.py:724` (Rechnung aus Bestellung erwartet `total_deposit` 10,71) muss umgeschrieben werden | bleiben grün, solange der Standardwert *je Lieferung* ist |

**Empfehlung: Variante C.**
1. **Gernots Alternative stimmt im Kern.** Ein monatlicher Saldo aus „ausgegeben minus zurück“ ersetzt viele Einzelgutschriften. Pro Kunde und Monat entsteht genau ein Pfandbeleg, Rückgaben werden nur als Stückzahl gezählt. Damit verschwinden L2, L3 und L7 für den Alltag.
2. **Ohne Ausnahme ist sie falsch für IFCO-Kunden.** Bei Ökoring (und laut Spezifikation vermutlich Bodan) läuft das Pfand über IFCO. Ein Monatslauf würde es ein zweites Mal berechnen. Deshalb braucht es den Wert *gar nicht*, und der ist zugleich Gernots Haken „Pfand von Rechnung ausnehmen“.
3. ***Je Lieferung* bleibt nur als heutiger Zustand.** Es ist der Standardwert nach der Migration. So ändert ein Deploy nichts, bevor Gernot einen Kunden bewusst umstellt. ~~Laut Gernot ist das Ziel, dass alle Nicht-IFCO-Kunden auf *monatlich* laufen.~~ *Korrigiert (Annahme statt Aussage):* Gernot hat zwei Wege angeboten und nach unserer Meinung gefragt. Festgelegt hat er sich nicht. Knuspr bekommt heute Pfand auf jeder Rechnung, und er wollte das per Haken so lassen können. Wenn er der Empfehlung folgt, laufen alle Nicht-IFCO-Kunden auf *monatlich*, und der Wert *je Lieferung* kann später ausgeblendet werden. Das klären Fragen 2 und 7.
4. **Paket 1 sollte das Merkmal gleich mit Werten statt als Ja/Nein bauen.** Also ein Feld `pfand_abrechnung` mit zunächst nur `JE_LIEFERUNG` und `KEINE` statt `pfand_via_clearing BOOLEAN`. Sonst gibt es später zwei Wahrheiten oder eine zweite Datenumstellung. Der Aufwand in Paket 1 ist gleich (S).

---

## 4. Vorschlag

### 4.1 Datenmodell (SQLite, nur `ADD COLUMN` bzw. neue Tabelle)

**Stufe 1 (Paket 1)**
```sql
-- tenancy._auto_migrate
ALTER TABLE customers ADD COLUMN pfand_abrechnung VARCHAR(20) DEFAULT 'JE_LIEFERUNG';
-- Werte: JE_LIEFERUNG | MONATLICH | KEINE   (MONATLICH erst ab Stufe 2 wählbar)
```

**Stufe 2: neue Tabelle `leergut_bewegungen`** (über `create_all`, `tenancy.py:255`)

| Spalte | Typ | Zweck |
|---|---|---|
| `id` | UUID | |
| `customer_id` | FK customers, Index | Konto |
| `product_id` | FK products (`is_deposit`) | Kistenart |
| `art` | VARCHAR(20) | `AUSGABE` \| `RUECKNAHME` \| `KORREKTUR` \| `ANFANGSBESTAND` |
| `menge` | INTEGER, immer > 0 | Stück; das Vorzeichen ergibt sich aus `art`. *Prüfnachtrag:* Für KORREKTUR fehlte eine Spalte für die Richtung. Deshalb zwei Werte `KORREKTUR_PLUS` \| `KORREKTUR_MINUS` statt `KORREKTUR`. |
| `einzelwert` | NUMERIC(10,2) | Pfandwert zum Buchungszeitpunkt (`deposit_value`, ersatzweise `base_price`). *Prüfnachtrag:* Ausgabe und Rücknahme brauchen **dieselbe Quelle**, also nicht den Preis der Bestellzeile, der Kundenpreis oder Handpreis sein kann (`sales.py:954-963`). Sonst geht der Saldo bei gleicher Stückzahl nicht auf null. `deposit_value` ist heute optional (`schemas/product.py:270`) und sollte für `is_deposit`-Artikel vor Stufe 2 Pflicht werden. |
| `leistungsdatum` | DATE, Index | Liefer- bzw. Rückgabetag; daraus folgt die Zuordnung zum Monat |
| `order_line_id` | FK order_lines, **UNIQUE** (falls gesetzt) | Herkunft der Ausgabe; verhindert eine doppelte Buchung |
| `delivery_note_id` | FK delivery_notes, NULL | Rückgabe beim Quittieren |
| `invoice_id` | FK invoices, NULL | gesetzt = abgerechnet (Schutz vor Doppelabrechnung wie `delivery_notes.invoice_id`); ein Storno setzt NULL |
| `bereits_berechnet` | BOOLEAN DEFAULT 0 | für `ANFANGSBESTAND`: zählt im Kistensaldo, aber nicht in der Abrechnung |
| `erfasst_von`, `erfasst_am`, `notiz` | | Nachvollziehbarkeit; abgerechnete Zeilen sind unveränderlich |

Optional: `ALTER TABLE invoices ADD COLUMN beleg_art VARCHAR(20)` mit dem Wert `'LEERGUT'` für Filter und Belegtitel. Damit muss `InvoiceType` nicht erweitert werden. *Prüfnachtrag:* Auch ein Erstattungsbeleg (Saldo < 0) bleibt `RECHNUNG` mit `beleg_art = 'LEERGUT'` und wird **nicht** `GUTSCHRIFT`. Sonst wäre er nicht stornierbar (`invoice_service.py:303-304`) und trüge die nach § 14 Abs. 4 Nr. 10 UStG belegte Bezeichnung.

**Stufe 3 (optional, Paket 4):**
- `products.lager_artikel_id` verbindet das Pfandprodukt mit dem `PFANDKISTE`-Lagerartikel. Ausgabe und Rückgabe buchen dann `AUSGANG` bzw. `RUECKGABE` (bisher ungenutzt, `inventory.py:36`).
- Zuordnung Verpackungseinheit → Pfandartikel (`KISTE_12` → 1 × E2-Kiste) für automatische Pfandzeilen. Das geht nur, wenn Gernot bestätigt, dass jede `KISTE_12` eine Pfandkiste ist.

### 4.2 Regeln

- **R-1 Rechnungsfilter (Stufe 1).** Eine Hilfsfunktion `pfand_auf_rechnung(customer)` gilt genau dann, wenn der Wert `JE_LIEFERUNG` ist. Sie wird an zwei Stellen angewendet:
  - `create_invoice_from_order` (`invoice_service.py:193-208`)
  - Sammelrechnung `_aggregiere` (`invoices.py:564`)

  Dort werden Positionen mit `product.is_deposit` übersprungen. Auf dem Lieferschein bleiben sie stehen, weil sie dokumentieren, wie viele Kisten übergeben wurden. Der Abo-Rechnungstask wird nach A5 ohnehin entfernt.
  - *Prüfnachtrag:* In `_aggregiere` geht das über `line.product` der Bestellzeile, ohne auf den A3-Fix zu warten (1.4).
  - *Prüfnachtrag:* Der Filter gehört **nicht** in `add_line`. Handrechnungen (`POST /invoices`, `/invoices/{id}/lines`) und der Storno (`invoice_service.py:334-345`) müssen Pfand weiter tragen können. Sonst brechen `test_deposit.py:8` und `test_pfand_rabatt.py:49`.
  - *Prüfnachtrag:* Eine Pfand-Bestellzeile, die schon eine Leergutbewegung hat, wird **unabhängig von der aktuellen Kundeneinstellung** übersprungen. Das ist die Gegenrichtung zur Ausnahme in R-2. Ohne diese Regel würde eine Lieferung, die unter `MONATLICH` ins Konto ging, nach einem Wechsel auf `JE_LIEFERUNG` ein zweites Mal berechnet.
- **R-2 Ausgabe buchen (Stufe 2).** Beim Übergang auf `GELIEFERT` wird für Kunden mit `MONATLICH` je Pfand-Bestellzeile eine `AUSGABE` gebucht. Das geschieht an derselben Stelle wie der Bestandsabzug (`sales.py:1229`, `documents.py:308`) und in derselben Transaktion. `order_line_id` ist UNIQUE, eine Wiederholung bucht also nichts doppelt.
  - Ausnahme: Hat die Bestellzeile schon eine Rechnungszeile (`InvoiceLine.order_item_id`), wird keine Ausgabe gebucht. Das schützt beim Wechsel der Abrechnungsart.
  - *Prüfnachtrag:* Diese Prüfung allein reicht nicht. Die Sammelrechnung setzt kein `order_item_id` (`invoices.py:618-625`), sie verknüpft nur über `delivery_notes.invoice_id` und `InvoiceLineSource`. Zusätzlich gilt deshalb: Steckt ein Lieferschein der Bestellung schon in einer Rechnung (`DeliveryNote.invoice_id IS NOT NULL`, `models/documents.py:91-93`), wird keine Ausgabe gebucht.
- **R-3 Nachzug im Monatslauf.** Viele Bestellungen erreichen `GELIEFERT` heute nie (A1). Deshalb werden fehlende Ausgaben im Monatslauf nachgebucht. Das betrifft Bestellungen des Zeitraums, die nicht `STORNIERT` oder `ENTWURF` sind und eine Pfandzeile, aber keine Bewegung haben.
  - *Korrigiert:* Die **Vorschau zeigt** diese Bestellungen nur als „wird nachgebucht“ an. **Gebucht wird erst beim Festschreiben.** Die Vorschau darf nichts schreiben; das ist schon für die Sammelrechnung so festgelegt (`invoices.py:575`, „rechnet, schreibt nichts (R2.6)“).
  - *Prüfnachtrag:* Der Nachzug braucht einen **Stichtag**, nämlich die Einführung von Stufe 2. Ältere Kisten kommen nur über `ANFANGSBESTAND` ins Konto. Sonst zieht der Nachzug auch importierte Altbestellungen nach (`GELIEFERT` ohne Lieferschein, A6: 46 Bestellungen vom 16.09. bis 07.10.), die womöglich schon im Altsystem berechnet wurden (R7).
- **R-4 Rückgabe.** Eine Rückgabe wird nur als Stückzahl erfasst, ohne Geldbetrag. Erfassen dürfen auch die Mitarbeiter. *Prüfnachtrag:* Die Auswahl der Kistenart darf nicht über `GET /api/v1/products` laufen, denn das ist für `production_staff` gesperrt (`main.py:716-720`). Die Pfandartikel kommen über einen eigenen Lese-Endpunkt in der Belegkette (siehe 4.3).
- **R-5 Monatslauf.** Pro Kunde mit `MONATLICH` und offenen Bewegungen bis `period_to` entsteht ein Beleg:
  - Pro Pfandartikel zwei Zeilen: „Leergut ausgegeben (E2-Kiste) +n × Wert“ und „Leergut zurückgenommen −m × Wert“.
  - Steuersatz vom Produkt (nach Paket 1: 19 %), Leistungszeitraum = Monat.
  - Die Bewegungen bekommen `invoice_id`.
  - Saldo > 0: Rechnung.
  - Saldo < 0: Erstattungsbeleg (kann nicht gemahnt werden; dafür die Paket-1-Lösung für Stornobelege wiederverwenden).
  - Saldo = 0: Beleg oder bloße Markierung „ausgeglichen“, je nach Antwort des Steuerberaters.
  - *Prüfnachtrag, Rabatt:* Der Leergutbeleg darf den Jahresrabatt des Kunden nicht erben. `create_invoice` setzt ihn automatisch, und eine übergebene 0 ändert daran nichts (`invoice_service.py:60-62`). Der Lauf muss `discount_percent` nach dem Anlegen ausdrücklich auf 0 setzen, oder `create_invoice` bekommt einen Schalter dafür.
  - *Prüfnachtrag, Belegtyp:* Typ `RECHNUNG` mit `beleg_art = 'LEERGUT'`, nicht `GUTSCHRIFT` (4.1).
- **R-6 Zusammenspiel mit B5.** Bekommt der Kunde die monatliche Sammelrechnung (Gernot: „monatlich fix“), hängt der Leergutblock als eigener Abschnitt an dieselbe Rechnung. Das ergibt einen Beleg pro Kunde und Monat, und ein negativer Gesamtbetrag kommt praktisch nicht vor. Sonst entsteht ein eigener Leergutbeleg. Welche der beiden Formen gewünscht ist, ist eine Frage an Gernot (siehe 6).
  - *Prüfnachtrag:* Einen eigenen Leergutbeleg braucht es auch dann, wenn ein Sammelrechnungskunde im Monat **nur Kisten zurückgibt**, aber nichts geliefert bekommt. Der Sammellauf erzeugt Rechnungen nur aus Lieferscheinen (`invoices.py:521-545`).
  - *Prüfnachtrag:* In der Sammelrechnung wirkt der Rechnungsrabatt auf alle Zeilen (`models/invoice.py:147-161`), also auch auf die Leergutzeilen. Vor dem Zusammenlegen muss der Rabatt Pfandzeilen ausnehmen. Das ist eine Änderung an `calculate_totals` und berührt `test_pfand_rabatt.py` (Einmalrabatt).
- **R-7 Storno.** Ein Storno des Leergutbelegs setzt `invoice_id` der Bewegungen auf NULL, wie bei `invoice_service.py:310-316`. Der nächste Lauf berechnet sie neu.
- **R-8 Korrekturen.** Nicht abgerechnete Bewegungen darf man ändern oder löschen. Abgerechnete werden nur über eine Gegenbuchung (`KORREKTUR_PLUS`/`KORREKTUR_MINUS`) berichtigt.
- **R-9 Kistensaldo.** Der Saldo ist die Summe aller Bewegungen inklusive Anfangsbestand. Er ist unabhängig von der Abrechnung und zeigt, wie viele Kisten beim Kunden stehen.

### 4.3 Endpunkte

| Methode, Pfad | Router / Rollen | Zweck |
|---|---|---|
| `PATCH /api/v1/sales/customers/{id}` **und `POST /api/v1/sales/customers`** + Feld `pfand_abrechnung` | sales (`_deps_auftraege`, mit Mitarbeitern) | **Schutz auf Feldebene:** nur Admin, Vertrieb, Buchhaltung (siehe Risiko R4). *Prüfnachtrag:* Der Schutz muss auch die Neuanlage abdecken (`sales.py:110-125`). Er darf nur greifen, wenn sich der Wert **ändert**. Das Kundenformular schickt nämlich immer alle Felder mit (`Customers.tsx:270-285`). Ein pauschales 403 bei vorhandenem Feld würde den Mitarbeitern jede Kundenänderung sperren. |
| `GET /api/v1/sales/customers/{id}/leergut?bis=` | Belegkette | Saldo je Kistenart (Stück, €), Bewegungen |
| *(Prüfnachtrag)* `GET /api/v1/sales/leergut/artikel` | Belegkette (mit Mitarbeitern) | Liste der Pfandartikel (`is_deposit`) für die Auswahl „Kistenart“. Nötig, weil `/api/v1/products` für `production_staff` gesperrt ist (`main.py:716-720`) |
| `POST /api/v1/sales/customers/{id}/leergut/ruecknahmen` `{leistungsdatum, product_id, menge, notiz}` | Belegkette (`main.py:129`, mit Mitarbeitern) | Rückgabe ohne Lieferung (Kunde bringt Kisten, Abholung) |
| `PATCH`/`DELETE …/leergut/{bewegung_id}` | Belegkette | nur solange `invoice_id IS NULL` |
| `PATCH /api/v1/sales/delivery-notes/{id}/mark-delivered` + `leergut_zurueck: [{product_id, menge}]` | Belegkette | Rückgabe direkt beim Quittieren |
| Tagesplan-Aktion „Ausgeliefert“ (aus A1) + dasselbe Feld | Produktion | Fahrer zählt beim Kunden |
| `POST /api/v1/invoices/leergut-run/preview` und `/commit` `{period_from, period_to, customer_ids, invoice_date}` | Rechnungen (`_deps_geld`) | Ablauf wie `batch-run`; Standardzeitraum = Vormonat |
| ~~Monatsjob `leergut-vorschlag` (Monatserster, Muster `scheduler_service.py:100`)~~ | — | ~~erstellt nur eine Vorschau bzw. einen Hinweis~~ *Korrigiert:* Einen Speicher für Hinweise gibt es nicht (1.7), und eine Vorschau schreibt nichts. Ein Job hätte also nichts zu tun. Stattdessen rechnet die Rechnungsseite ab dem Monatsersten **beim Öffnen** einen Hinweis aus („Monatsabrechnung Oktober offen: n Kunden“), Grundlage ist die Vorschau-Abfrage. Festgeschrieben wird von Hand. Kein Beleg wird automatisch angelegt, solange die Nummer schon beim Anlegen vergeben wird (`invoice_service.py:53`; „Nummer beim Finalisieren“ kommt in Paket 3). Das beantwortet auch Gernots B5-Rückfrage „automatisch erstellt und vorgeschlagen?“: vorgeschlagen ja, erstellt erst nach seinem Klick. |

### 4.4 Oberfläche
- **Kundenformular** (Block `Customers.tsx:367-414`): Auswahlfeld „Pfand abrechnen“ mit den Optionen „je Lieferung auf der Rechnung“, „monatlich über Leergutkonto“ und „gar nicht (IFCO-Clearing)“. Darunter steht ein Satz, was die gewählte Option bewirkt.
- **Kundendetail, Reiter „Leergut“:**
  - Saldo je Kistenart in Stück und €
  - Bewegungsliste mit Herkunft (Lieferschein, Tagesplan, Hand) und Abrechnungsstatus
  - Knopf „Rückgabe erfassen“
  - *Korrigiert:* Eine Kundendetailseite mit Reitern gibt es nicht. Kunden erscheinen als Karten, Zusatzfunktionen öffnen sich als Dialog (Muster `CustomerPricesModal`, `Customers.tsx:210`). Gebaut wird also ein Dialog „Leergutkonto“. Diese Seite sieht nur ADMIN/SALES/ACCOUNTING (`Layout.tsx:178-181`). Für die Halle braucht „Rückgabe ohne Lieferung“ deshalb einen zweiten Einstieg: im Tagesplan oder auf der Bestellseite, die `PRODUCTION_STAFF` sieht (`Layout.tsx:187-190`), mit Kundenauswahl.
- **Tagesplan, Karte „Ausliefern“:** Der neue Knopf „Ausgeliefert“ (A1) öffnet einen kleinen Dialog mit „Leergut zurück“ je Kistenart. Vorbelegt ist 0, daneben steht als Hinweis „beim Kunden: 14“.
- **Lieferschein quittieren** (`OrderDocumentsModal.tsx:255-271`): dasselbe Feld.
- **Lieferschein-PDF:** optionale Zeile „Leergut zurückgenommen: ____“ zum Handausfüllen, falls der Fahrer auf Papier zählt.
- **Rechnungen:** Knopf „Leergutabrechnung“ neben „Sammelrechnung“ (`Invoices.tsx:234`, Dialog wie `:577`), mit Zeitraum, Vorschau je Kunde (negative Salden markiert) und Festschreiben.
- **Rechnung aus Bestellung:** Hinweis „Pfand (3 Kisten) läuft über das Leergutkonto“, damit niemand die fehlende Zeile für einen Fehler hält.

### 4.5 Tests (pytest; Muster: `tests/test_sammelrechnung.py`, `test_pfand_rabatt.py`, `test_storno.py`, `test_rollen.py`)
1. `KEINE`: Bei einer Rechnung aus einer Bestellung und in Vorschau und Festschreiben der Sammelrechnung fehlen die Pfandzeilen. Der Lieferschein führt sie weiter.
2. `JE_LIEFERUNG`: Verhalten unverändert (Regression, `total_deposit` wie heute).
3. `MONATLICH`: Lieferung mit 10 Kisten ergibt genau eine `AUSGABE`. Ein zweiter Statuswechsel oder ein erneutes Quittieren bucht nichts dazu. Die Rechnung aus der Bestellung hat keine Pfandzeile.
4. Monatslauf: 10 aus, 4 zurück ergibt einen Beleg mit +10 und −4 Zeilen, 19 %, Gesamt = 6 × Wert × 1,19, Leistungszeitraum gesetzt. Ein zweiter Lauf ergibt nichts.
5. Saldo < 0 (2 aus, 5 zurück): Erstattungsbeleg mit negativem Betrag, Typ nicht `GUTSCHRIFT`, stornierbar. Er taucht **nicht** in `InvoiceService.check_overdue_invoices`, **nicht** im eingeplanten Task `tasks/invoice_tasks.py:28` und nicht im Mahnlauf auf.
6. Saldo = 0: Verhalten je nach Antwort des Steuerberaters (Beleg mit 0,00 € oder Markierung).
7. Storno des Leergutbelegs: Die Bewegungen sind wieder offen, der nächste Lauf berechnet sie.
8. Nachzug: Eine Bestellung ohne `GELIEFERT`, aber mit Lieferdatum im Zeitraum, erscheint in der Vorschau als „wird nachgebucht“. Die Vorschau legt **keine** Bewegung an, erst das Festschreiben. Bestellungen vor dem Stichtag bleiben draußen.
9. Wechsel `JE_LIEFERUNG` → `MONATLICH`: Eine schon fakturierte Pfandzeile erzeugt keine Ausgabe, auch wenn sie über eine **Sammelrechnung** fakturiert wurde (nur `delivery_notes.invoice_id` gesetzt, kein `order_item_id`). Gegenrichtung `MONATLICH` → `JE_LIEFERUNG`: Eine Pfandzeile mit Bewegung kommt nicht mehr auf die Rechnung.
10. Monatsgrenze: Lieferung am 31.10. gehört in den Oktober, eine Rückgabe am 02.11. in den November.
11. Rollen: `production_staff` darf eine Rückgabe erfassen (201) und die Pfandartikel lesen (`/sales/leergut/artikel`). Er erhält 403 für den Leergutlauf und für eine **Änderung** von `pfand_abrechnung`, auch bei der Neuanlage. Ein PATCH mit unverändertem `pfand_abrechnung` (volles Formular) geht dagegen durch (200).
12. Migration: Altes Schema plus `_auto_migrate` ergibt die Spalte mit Standardwert `JE_LIEFERUNG`. `create_all` legt die neue Tabelle an.
13. Kombination mit B5: Die Monats-Sammelrechnung mit Leergutblock weist Steuer getrennt je Satz aus (7 % Ware, 19 % Pfand).
14. Nebenbefund L8: Pfandzeilen fehlen in `komponenten` des Packplans.
15. *(Prüfnachtrag)* Rabatt: Ein Kunde mit 5 % Jahresrabatt erhält einen Leergutbeleg ohne Rabatt. In der Monats-Sammelrechnung bleibt der Rabatt auf die Ware beschränkt.
16. *(Prüfnachtrag)* Bestehende Regressionstests bleiben unverändert grün: `test_deposit.py:8`, `test_pfand_rabatt.py:49`, `test_gernot_260821.py:724` (Rechnung aus Bestellung mit Pfand, Standardwert `JE_LIEFERUNG`).

Frontend: ein e2e-Durchlauf (`frontend/tests/e2e`) Tagesplan → „Ausgeliefert“ mit 3 Kisten zurück → Dialog „Leergutkonto“ zeigt den neuen Saldo.

### 4.6 Aufwand

| Baustein | Aufwand | Wann |
|---|---|---|
| Stufe 1: `pfand_abrechnung` (`JE_LIEFERUNG`/`KEINE`), Filter in Rechnung-aus-Bestellung und Sammelrechnung, Formularfeld, Feldschutz, Tests 1, 2, 12 | **S** | Paket 1 (ersetzt `pfand_via_clearing`) |
| Leergut-Journal, Ausgabe-Buchung, Nachzug | **M** | Paket 3 |
| Rückgabe-Erfassung: Endpunkte (inkl. Pfandartikel-Liste für die Halle), Dialog „Leergutkonto“ (statt Kundenreiter, siehe 4.4), Halle-Einstieg ohne Kundenseite, Quittier-Feld, Tagesplan-Dialog | **M** | Paket 3; Tagesplan-Teil nach A1 (Paket 2) |
| Leergut-Monatslauf und Beleg: PDF, Leistungszeitraum, Erstattung, Mahnsperre (beide Überfälligkeits-Pfade), Storno, Rabatt-Ausnahme für Pfand, Einbindung in B5 | **M** | Paket 3, nach B5 und den Paket-1-Fixes zu Storno und Mahnwesen |
| Anfangsbestand (Import oder Erfassungsmaske) | **S** | mit der Einführung von Stufe 2 |
| Nebenbefund L8 (Pfand aus Packplan und Sortenbedarf) | **S** | Paket 2 |
| Optional Stufe 3: Lagerkopplung `PFANDKISTE`, automatische Pfandzeile aus Verpackungseinheit | **M** | Paket 4 |
| **Gesamt Stufe 2** | **L** (≈ 3 × M) | |

---

## 5. Risiken

- **R1 Steuerliche Einordnung entscheidet über B und C.** Getrennte Monatsabrechnung ist nur vertretbar, wenn die Kiste ein Transporthilfsmittel ist, also eine eigenständige Leistung (Annahme, vgl. Spezifikation Entscheidung 4). Wäre sie eine Warenumschließung, gehörte das Pfand als Nebenleistung zur Ware, zum Satz der Ware und auf deren Rechnung. ~~Dann bliebe nur Variante A.~~ *Korrigiert:* Dann entfiele der eigene Leergutbeleg. Möglich blieben Variante A oder der Leergutblock in der monatlichen Sammelrechnung der Ware (R-6), dann zum Satz der Ware. Diese Einschätzung ist eine Annahme und vom Steuerberater zu bestätigen.
- **R2 Abhängigkeiten.**
  - ~~Ohne A3 (Sammelrechnung mit `product_id`) greift der Filter dort nicht.~~ *Korrigiert:* Der Filter in der Sammelrechnung greift auch ohne A3, weil er auf der Bestellzeile arbeitet (1.4). Ohne A3 fehlen dort nur `is_deposit` und der Pfandhinweis für Kunden mit *je Lieferung*.
  - Ohne A1 erreichen Bestellungen `GELIEFERT` selten. Darum gibt es den Nachzug (R-3).
  - Ohne die Paket-1-Fixes (Storno mehrzeiliger Belege, kein Mahnwesen für Minusbelege) darf der Leergutlauf nicht live gehen.
- **R3 Pfand hängt an Handpositionen.** Eine vergessene Pfandzeile wird nie berechnet. Pfand als Freitext ohne `product_id` erkennt das System nicht. *Annahme:* Wie Pfand in Produktion erfasst wurde, ist ungeprüft (laut Spezifikation A3 enthalten RE-00002, RE-00003 und RE-00004 Pfand). Vor Stufe 2 sollten die Bestellzeilen in Produktion nur lesend geprüft werden.
  - *Prüfnachtrag:* Lesend prüfen sollte man dabei auch, ob jeder Pfandartikel `is_deposit = 1` trägt. Ein per Import angelegter Artikel mit Kategorie `PFAND` hat das Kennzeichen sonst nicht (1.1), und der Filter übersieht ihn. Alternative: Der Filter prüft `is_deposit OR category = 'PFAND'`.
  - *Prüfnachtrag:* Solange `production_staff` den Produktkatalog nicht lesen kann (L10), können von Mitarbeitern angelegte Bestellungen keine erkennbare Pfandzeile haben. Das muss vor oder mit B8 gelöst werden, zum Beispiel mit Lesezugriff der Halle auf `/products`. Sonst wirkt Stufe 1 bei diesen Bestellungen nicht.
- **R4 Rollen.** Der Kunden-PATCH liegt im `sales`-Router, und dort haben die Mitarbeiter Schreibrecht (`main.py:122`, `:701-706`). Ohne Schutz auf Feldebene könnte die Halle die Abrechnungsart umstellen. *Prüfnachtrag:* Das gilt auch für die Neuanlage (`POST /customers`). Weil das Formular alle Felder schickt, muss der Schutz auf eine Änderung des Werts prüfen (4.3). Dass die Halle Rückgaben erfasst, ist gewollt. Ein Zählfehler kostet aber Geld. Deshalb `erfasst_von` speichern, abgerechnete Zeilen sperren und den Saldo in der Vorschau sichtbar machen.
- **R5 Belege mit negativem Saldo.** Sie betreffen Mahnwesen (`invoice_service.py:355-379` **und** `tasks/invoice_tasks.py:28-56`), Storno (`:319`; und `GUTSCHRIFT` gar nicht stornierbar, `:303-304`), DATEV-Vorzeichen (B9) und die Bezeichnung „Gutschrift“ (`enums.py:43`). Wo die Leergutzeilen in die Monats-Sammelrechnung eingehen (R-6), tritt das selten auf, verschwindet aber nicht.
- **R6 Nummernvergabe.** Es dürfen keine Belegentwürfe automatisch angelegt werden, solange die RE-Nummer schon beim Anlegen vergeben wird (`invoice_service.py:53`). Verworfene Entwürfe würden sonst Nummernlücken erzeugen. Bis Paket 3 also nur eine Vorschau, die beim Öffnen gerechnet wird (4.3, ohne Monatsjob).
- **R7 Altbestand.** Kisten, die vor dem Go-live oder auf RE-00002/00004 (mit 7 %, Korrektur in Paket 1) berechnet wurden, gehören als `ANFANGSBESTAND` mit `bereits_berechnet = 1` ins Konto. Sonst wird doppelt berechnet, oder Kisten werden erstattet, die nie berechnet wurden.
  - *Prüfnachtrag, Paket-1-Korrektur:* RE-00002 und RE-00003 sind laut Spezifikation A3 Ökoring-Rechnungen mit Pfand. Ist Ökoring IFCO-Clearing-Kunde (Wert `KEINE`), dann darf die Neuausstellung in Paket 1 das Pfand **gar nicht** mehr enthalten, statt es nur von 7 % auf 19 % zu korrigieren. Gernots Antwort auf Frage 1 muss also **vor** der Korrektur von RE-00002/00003 vorliegen.
  - *Prüfnachtrag:* Importierte Altbestellungen (A6) gehören über den Stichtag aus dem Nachzug heraus (R-3).
- **R8 Pfandwert ändert sich.** Der Wert wird je Bewegung festgehalten. Zu welchem Wert ältere Kisten bei der Rückgabe erstattet werden, ist offen (siehe Frage an Gernot).
- **R9 Lieferschein mit Preisen.** Bei `KEINE` oder `MONATLICH` und `show_prices_on_delivery_note` zeigt der Lieferschein den Pfandpreis in der Summe (`pdf_service.py:779-808`), die Rechnung aber nicht. Wer beide vergleicht, wird irritiert. Empfehlung: Pfandzeilen auf dem Lieferschein ohne Preis, wenn nicht `JE_LIEFERUNG`. *Prüfnachtrag:* Dasselbe gilt **immer** für die Auftragsbestätigung. Sie druckt Pfand mit Preis in Netto, MwSt und Gesamt (`pdf_service.py:688-716`, Summen aus `order.total_*`), und nach B8 versenden sie künftig die Mitarbeiter.
- **R10 Fehlender Beleg bei Saldo 0.** Kommt der Steuerberater zum Ergebnis, dass Ausgabe und Rücknahme je für sich abzurechnen sind, muss auch ein Monat mit Saldo 0 einen Beleg mit beiden Zeilen erzeugen. Der Vorschlag weist deshalb immer beide Zeilen aus.
- **R11 Demo-Mandant (Prüfnachtrag).** Der nächtliche Demo-Reset kopiert den Golden-Seed zurück, ohne `create_all` oder `_auto_migrate` (`services/demo_reset_service.py:58-71`). Ist der Seed älter als die neue Spalte `customers.pfand_abrechnung`, dann fehlt sie nach dem Reset um 03:30 bis zum nächsten Neustart. Jede Kundenabfrage schlägt dann fehl. Nach dem Deploy muss deshalb der Seed neu eingefroren werden (`POST /demo/snapshot`, `platform.py:238-245`), oder der Reset bekommt danach `create_all` und `_auto_migrate`. Das gilt genauso für die neue Tabelle.

---

## 6. Fragen (nur, was der Code nicht beantworten kann)

**An Gernot**
1. Welche Kunden rechnen Pfand über IFCO-Clearing ab, nur Ökoring und Bodan? (Spezifikation, Entscheidung 6) *Prüfnachtrag:* Die Antwort wird **vor** der Paket-1-Korrektur von RE-00002/00003 (Ökoring) gebraucht (R7).
2. Akzeptiert Knuspr eine monatliche Leergutabrechnung, oder braucht Knuspr das Pfand auf jeder Lieferrechnung?
3. Welche Pfandartikel gibt es (E2-Kiste, IFCO-Kiste, Mehrwegtray) mit welchem Pfandwert? Werden ältere Kisten nach einer Wertänderung zum alten oder zum neuen Wert erstattet?
4. Wie viele Kisten stehen heute bei welchem Kunden, und ist dafür schon Pfand berechnet worden (RE-00002/00004, Altsystem)?
5. Wer zählt das Leergut und wann: der Fahrer beim Kunden oder jemand beim Ausladen im Betrieb?
6. Wenn mehr zurückkommt als ausgegeben wurde: Soll der Betrag monatlich erstattet oder mit der nächsten Warenrechnung verrechnet werden?
7. Soll das Leergut im selben Monatsbeleg wie die Ware stehen (eine Sammelrechnung) oder als eigener Leergutbeleg?
8. Ist jede Lieferung in `KISTE_12`/`KISTE_6` automatisch eine Pfandkiste, sodass die Pfandzeile automatisch entstehen könnte?
9. Sollen bei IFCO-Kunden die Kistenmengen trotzdem mitgezählt werden, z. B. für den Abgleich mit IFCO?

**An den Steuerberater** (Fundstellen nur als Prüfhinweis, nicht als Auskunft)
1. Sind E2- und IFCO-Kisten (und Mehrwegtrays) Transporthilfsmittel, also eine eigenständige Leistung zu 19 %, und keine Warenumschließungen (vgl. Abschn. 3.10 Abs. 5a UStAE)?
2. Ist die Rücknahme eine Entgeltminderung bei MingaGreens (§ 17 UStG) oder eine Rücklieferung des Kunden? Darf MingaGreens sie selbst als Minusposition abrechnen?
3. Dürfen Ausgabe und Rücknahme eines Monats in einem Beleg als zwei Zeilen saldiert werden, und braucht es bei Saldo 0 trotzdem einen Beleg?
4. Ist eine monatliche statt lieferungsbezogene Pfandabrechnung zulässig? Welche Rolle spielen Soll- oder Ist-Versteuerung und der Voranmeldungszeitraum? Entsteht die Steuer im Liefermonat (§ 13 Abs. 1 Nr. 1 a UStG), auch wenn der Beleg im Folgemonat datiert ist? Reicht der Leistungszeitraum auf dem Beleg (§ 14 Abs. 4 Nr. 6 UStG)?
5. Wie muss der Beleg bei negativem Saldo heißen und behandelt werden? „Gutschrift“ ist nach § 14 Abs. 4 Nr. 10 UStG der Abrechnung durch den Leistungsempfänger vorbehalten.
6. Braucht das Pfand in DATEV ein eigenes Erlöskonto, und welches?
7. Muss das Pfand bei IFCO-Clearing-Kunden auf der Rechnung von MingaGreens erscheinen, zumindest nachrichtlich?

---

## 7. Prüfvermerk (Gegenprüfung am Code, 08.10.2026)

Alle Datei:Zeile-Belege wurden an `c4a1832` nachgeprüft. Die meisten stimmen. Korrigiert wurden Zeilenversätze (`main.py` Router, `documents.py:308-312`, `scheduler_service.py:30-57`, `order_fulfillment_service.py:199-204`) und inhaltlich:
- Pfand lässt sich in der Sammelrechnung **ohne** A3-Fix herausfiltern (1.4, L4, R2).
- R-3: Die Vorschau bucht nicht nach, erst das Festschreiben. Dazu kommt ein Stichtag gegen importierte Altbestellungen.
- R-2/R-1: Der Doppelabrechnungsschutz deckt jetzt auch die Sammelrechnung (`delivery_notes.invoice_id`) und die Gegenrichtung des Moduswechsels ab.
- Der Monatsjob entfällt, weil es keinen Hinweisspeicher gibt. Stattdessen rechnet die Rechnungsseite die Vorschau beim Öffnen.
- Eine „Kundendetailseite mit Reiter“ gibt es nicht, und die Kundenseite ist für die Halle unsichtbar. Gebaut werden ein Dialog und ein Einstieg für die Halle.
- Feldschutz `pfand_abrechnung`: Er gilt auch für die Neuanlage und greift nur bei einer Änderung des Werts (das Formular schickt alle Felder).
- R1: „nur Variante A“ ist abgeschwächt, weil der Leergutblock in der Sammelrechnung zum Warensatz möglich bliebe.
- „Laut Gernot ist das Ziel …“ ist als Annahme gekennzeichnet.

Neu aufgenommen wurden:
- Jahresrabatt auf Pfand (L9, R-5, R-6, Test 15)
- `production_staff` ohne Produktkatalog (L10, R-4, R3)
- Import-Pfandartikel ohne `is_deposit`
- zweiter Überfälligkeits-Pfad
- `GUTSCHRIFT` nicht stornierbar
- Auftragsbestätigung (R9)
- Ökoring-Rechnungen in der Paket-1-Korrektur (R7)
- Demo-Reset ohne Migration (R11)
- bestehende Regressionstests (Test 16, Variantentabelle)
- weitere Codepfade (Tagesplan-Lieferschein, Import, Shopify, `add_order_line`)
