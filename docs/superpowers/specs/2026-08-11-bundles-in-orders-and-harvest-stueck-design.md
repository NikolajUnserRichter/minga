# Design: Bundles in Bestellungen + Ernte in Stück

Datum: 2026-08-11 · Quelle: Pilot-Feedback Minga Greens

## Problem 1: Mischkisten (Bundles) nicht in Bestellung auswählbar

**Befund:** Das Datenmodell und die Bestell-UI unterstützen Bundles bereits vollständig
(`Product.is_bundle`, `BundleComponent`, Fulfillment bucht Komponenten aus,
`CreateOrderModal` rendert Bundles mit 📦-Präfix). Die Bundles erscheinen trotzdem nicht,
weil `GET /products` mit `page_size=20` paginiert und ohne Sortierung liefert. Das
Bestellformular lädt ohne Pagination-Parameter → nur die ersten 20 Produkte (in
Einfüge-Reihenfolge) erscheinen; später angelegte Bundles fallen ab.

**Fix:**
- Backend `list_products`: stabile Sortierung `ORDER BY name`, eigener
  `page_size`-Parameter mit Obergrenze 500 (Produktkatalog eines Microgreens-Betriebs
  bleibt weit darunter).
- Frontend: `productsApi.list` bekommt `page_size`; `CreateOrderModal`, `Products`-Seite
  und Bundle-Komponenten-Picker laden mit `page_size=500`.

Kein Datenmodell- oder Fulfillment-Change nötig.

## Problem 2: Ernte-Popup nur in Gramm

**Anforderung:** Minga erntet nicht geschnitten, sondern verkauft ganze Schalen →
Erfassung in Stück. Eine Anzuchtkiste = 15 Stk (Standard) bzw. 21 Stk (anderes Format).
Für andere Nutzer/Tenants soll Gramm weiter möglich sein → Umschalter g/Stk.

**Datenmodell (`Harvest`):**
- `einheit: String(10)`, Default `"G"` — Werte `"G" | "STK"` (bestehende Datensätze bleiben korrekt)
- `menge_stueck: Integer, nullable` / `verlust_stueck: Integer, nullable`
- `stueck_pro_kiste: Integer, nullable` (15/21, dokumentiert das Kistenformat der Ernte)
- `menge_gramm` bleibt NOT NULL; STK-Ernten speichern dort `0`. (Tenant-DBs sind
  SQLite und werden über `tenancy._auto_migrate` per idempotenter `ALTER TABLE`
  migriert — SQLite kann NOT NULL nicht nachträglich lockern, und `0` verfälscht
  keine Gramm-Summen. Wir rechnen bewusst nicht Stück→Gramm um.)
- Migration: neue Spalten in `_auto_migrate` (trifft Prod-Tenants beim Boot) und
  Alembic-Revision `018_harvest_stueck` (hält das Alembic-Schema konsistent)

**Validierung (Pydantic):** `einheit=G` → `menge_gramm > 0` erforderlich;
`einheit=STK` → `menge_stueck > 0` erforderlich.

**Konsumenten von `menge_gramm` (Null-Guards):**
- Dashboard-KPI: `weekly_harvest_kg` summiert nur G-Ernten (SUM ignoriert NULL);
  neu `weekly_harvest_stueck` für STK-Ernten, Anzeige im Dashboard-KPI.
- `analytics.get_yield_stats`: Zeilen mit `total_harvest IS NULL` überspringen.
- `inventory_service` Traceability: `quantity_g` null-sicher + `quantity_stk` ergänzen.

**UI (`HarvestForm`):**
- Umschalter **Stk | g**, Default **Stk**; letzte Wahl wird in `localStorage` gemerkt
  (Tenants, die wiegen, landen nach der ersten Ernte automatisch wieder bei g).
- Bei Stk: Feld „Stk pro Kiste" mit Schnellwahl 15 (Standard) / 21, frei editierbar.
  Erwartungswert = `tray_anzahl × stk_pro_kiste`, ±5%-Toleranz wie bisher.
- Bei g: bisheriges Verhalten (Erwartung aus `ertrag_gramm_pro_tray`).
- Ernte-Liste (`Harvests.tsx`) zeigt Menge einheitsbewusst (kg bzw. Stk), Summenkarte
  getrennt.

**Verworfen:** Umrechnung Stk→g über Durchschnittsgewicht (erfundene Daten verfälschen
Analytics); eigenes Kistenformat-Stammdatum am GrowBatch (YAGNI — Formatwahl im
Popup genügt, Wert wird an der Ernte persistiert).
