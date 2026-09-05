# Bestandsaufnahme: Release Storno / Sammelrechnung / Import / Warenfluss / Inventur

Schritt 1 laut Anforderungsdokument (05.09.2026): bestehendes Datenmodell lesen,
bevor irgendetwas gebaut wird. Ergebnis vorweg: **das zentrale
Bestands-Bewegungsjournal existiert bereits** — AP4b ist zu großen Teilen da,
die Umsetzungsreihenfolge ändert sich entsprechend.

## Korrekturen an den Annahmen des Dokuments

Das Dokument nennt PostgreSQL, Celery/Redis und Alembic. Tatsächlich gilt:

| Annahme im Dokument | Realität im System |
| --- | --- |
| PostgreSQL | **SQLite je Mandant** (`/data/tenants/<slug>.db`, WAL) |
| Alembic-Migrationen | **Alembic ist Legacy.** Neue Tabellen legt `Base.metadata.create_all` beim Boot an; neue Spalten gehen über `tenancy._auto_migrate` / `_add_col_if_missing` |
| Celery/Redis-Tasks | **Celery wurde durch APScheduler ersetzt.** Imports laufen synchron — bei den Datenmengen (hunderte Zeilen) angemessen, R3.8 wird ohne Task-Queue erfüllt |
| „DB-Sequence bzw. SELECT … FOR UPDATE" | SQLite kennt beides nicht; das transaktionssichere Muster ist `_next_document_number` in `documents.py` (max+1 unter Unique-Constraint) — für Rechnungen analog |

## Was bereits existiert

### Bewegungsjournal (≈ AP4b `stock_movements`)

`InventoryMovement` in `app/models/inventory.py:386` ist das geforderte Journal:
vorzeichenbehaftete `quantity`, `unit`, **`movement_date` (historisch buchbar)**,
`quantity_before/after`, Referenzen auf Order/OrderLine/GrowBatch/Harvest plus
`reference_number`, `created_by`, `reason`.

- `MovementType`: EINGANG, AUSGANG, PRODUKTION, ERNTE, VERLUST, KORREKTUR, UMLAGERUNG, RUECKGABE — deckt EINKAUF/VERBRAUCH/ERNTE/VERKAUF/AUSSCHUSS/INVENTURKORREKTUR/RETOURE ab.
- `InventoryItemType`: SAATGUT, VERPACKUNG, FERTIGWARE, SUBSTRAT, PFANDKISTE, HANDELSWARE, SONSTIGES.
- Gebucht wird aus `inventory_service` (receive_seed_batch, consume_seed_for_sowing, receive_harvest, ship_goods, record_loss, receive/consume_packaging), `procurement_service`, `order_fulfillment_service`, `seed_mix`.

**Lücken:** (1) Substrat wird über `PackagingInventory.article_type='SUBSTRAT'`
geführt (mengenmäßig, keine eigene Tabelle nötig) — aber `receive_packaging`
und `consume_packaging` buchen **hart `item_type=VERPACKUNG`**: im Journal sind
Substrat- und Verpackungsflüsse nicht unterscheidbar, das bricht R5.7.
(2) Unveränderlichkeit ist nicht erzwungen (keine Gegenbuchungs-Konvention).
(3) Kein Index auf (item_type, movement_date) — bei SQLite-Größenordnung
unkritisch, günstig mitzunehmen.

### Inventur (≈ AP6, Grundgerüst)

`InventoryCount`/`InventoryCountItem` + Service: `create_inventory_count`
(füllt Positionen mit Soll-Snapshot `system_quantity`), `add_count_item`
(Fund-Positionen), `finalize_inventory_count` (bucht KORREKTUR-Bewegungen und
gleicht Bestände an). Endpunkte unter `/inventory/counts`.

**Lücken:** Inventurtyp (JAHRES/STICHPROBE/ANLASS), `geprueft_von`,
Zählliste-PDF (Blindzählung), Differenzschwellwert mit Pflicht-Bemerkung,
Bewertung (Preisansatz), PDF mit Unterschriftsfeldern + XLSX-Export,
Vorjahresvergleich. Korrekturen buchen mit `now()` statt Stichtag.

### Chargen-Import (≈ AP3, erste Fassung)

`_import_grow_batches` in `imports.py:622` + „Chargen-Import"-Knopf in der
Produktion. CSV/XLSX mit Vorlage und Beispielzeile existieren
(`GET /imports/template/grow_batches`). Idempotent über (Sorte, Aussaatdatum,
Kistenzahl); Status wird aus Erntefenster hergeleitet; optionale Ernte wird
angelegt.

**Lücken:** kein Dry-Run/Zeilenreport (erster Fehler bricht alles ab), kein
`import_run_id`/Rollback, keine `source`-Kennzeichnung, **keine
Bestandswirkung** (Saatgut-Charge wird als Marker mit Menge 0 angelegt, keine
Bewegungen — R3.5 fehlt komplett), Ernte erzeugt keine ERNTE-Bewegung, Spalten
für Substrat/Ausschuss/Los/Lieferant/externe_chargennummer fehlen.

### Stornierung (≈ AP1, Grundgerüst)

`POST /invoices/{id}/cancel` + `InvoiceService.cancel_invoice` existieren:
setzt Original auf STORNIERT, erzeugt GUTSCHRIFT mit negativen Positionen und
`original_invoice_id`-Referenz, Nummer aus dem regulären Kreis.

**Lücken:** R1.4 Stornogrund-Auswahlliste (nur Freitext in internal_notes),
R1.6 Lieferschein-Freigabe (es gibt **gar keinen Lieferschein↔Rechnung-Link**),
R1.7 eine GUTSCHRIFT ist selbst stornierbar (nur STORNIERT-Status wird
geprüft), Schreibschutz des Originals fehlt, PDF-Titel/Hinweiszeile
„Stornorechnung" fehlt.

### Sammelrechnung (AP2) — nicht vorhanden

Nur `POST /invoices/from-order/{id}`. `DeliveryNote` trägt keinen
Abrechnungsstatus und keinen Rechnungsbezug → Doppelabrechnungsschutz braucht
neue Spalte `invoice_id` am Lieferschein (via `_add_col_if_missing`) und die
Tabelle `invoice_line_sources` (neu, `create_all`).

### Warenfluss-Reports (AP5) — nicht vorhanden

Keine Report-Endpunkte; die Datengrundlage (Journal mit historischem
`movement_date`) ist aber vollständig. `get_stock_overview` und
`get_traceability` existieren als Bausteine.

## Angepasste Umsetzungsreihenfolge

Da das Journal existiert, entfällt „AP4b zuerst bauen". Stattdessen:

1. **AP4b-Härtung** (klein): Substrat-Bestand klären, Unveränderlichkeit + Gegenbuchung, Index.
2. **AP3 v2**: Dry-Run-Report, import_run_id/Rollback, Bestandswirkung (R3.5), neue Spalten.
3. **AP5**: Warenfluss-Reports auf dem Journal (macht den Import sofort prüfbar).
4. **AP1**: Lücken schließen (Grund-Auswahlliste, LS-Freigabe, Storno-Sperren, PDF).
5. **AP2**: Sammelrechnung (setzt LS↔Rechnung-Link aus AP1/R1.6 voraus).
6. **AP4a**: Chargen-Grid (nutzt Import-Validierung aus AP3 v2).
7. **AP6**: Inventur-Ausbau auf dem Grundgerüst.

## Offene Punkte — entschieden am 05.09.2026

1. Verpackungen/Substrate: **nur mengenmäßig** (losgenau bleibt allein das Saatgut — dort sitzt der Zertifizierungsnachweis).
2. Bewertung Inventur: **letzter Einkaufspreis** (liegt als `purchase_price` am Bestand; Methode als Feld, damit später umstellbar).
3. Angebrochene Gebinde: **in Gewicht zählen** (Saatgut durchgängig kg, Anbruch wird gewogen).
4. Sammelrechnung: **nur Lieferscheine**, keine Abo-Pauschalen (Abos erzeugen Bestellungen mit Lieferscheinen und laufen so automatisch mit).
