# Implementation Wave 2026-06 — Deliverables Report

## 1. Implementation Summary

Diese Wave deckt **25+ Anforderungen** aus dem strukturierten Backlog ab.
Aufgeteilt in 7 in sich abgeschlossene Batches plus E2E-Test-Suite.

### Batch 1 — Quick-Wins
- A4.1 Customer-Search "Alle Typen" findet Ökoring
- A4.2 Order-History-Import case-insensitive + Umlaute
- A6 / B1.1 Bundles im Order/Subscription-Modal sichtbar
- B3 Default-Einheit "STK" statt "g"

### Batch 2 — File-Upload + Error-Handling
- A1 Datei-Upload bei Saatgut-Wareneingang (Zertifikate, Lieferschein, Bilder)
- A2 Order-Loading-Error mit Detail + Retry

### Batch 3 — Customer-Stammdaten erweitert
- B4 Auto-Kundennummer (KD-NNNNN) + Anzeige auf Belegen
- B5 Zahlungsziele konfigurierbar (PREPAID/COD/NET_7/14/30/60)
- B6 Skonto-Felder (% + Tage)
- B7 Verpackungsgebühr + Jahresrabatt

### Batch 4 — Wachstumscharge
- A3.1 GrowBatch nach Anlegen sichtbar (Critical-Bug, items vs flat array)
- D1 Wachstumspläne editierbar (PATCH + UI-Modal)
- C1 Saatgut-Charge UX: harte Validierung + Hinweis-Text

### Batch 5 — Production-Timeline-Events
- A3.2 Soaking-Workflow (SOAKING_STARTED, SOAKING_COMPLETED)
- A3.3 Production-Milestones (Sowing/Germination/Grow/Cooling/Packaging)
- Volle Event-Tabelle mit Mitarbeiter + Notizen + Timestamp

### Batch 6 — Searchable Dropdowns
- B2 Generischer Combobox-Component (Live-Filter, Pfeil-Nav, Enter)
- Integriert in OrderModal (Kunde + Produkt) + Subscription-Modal

### Batch 7 — Belege
- B1.2 Subscription-Creation-Error gefixt (Product vs Saatgut)
- B8 Legal-Compliance Gap-Analyse als docs/legal-compliance-belege.md
- B9 Zahlungserinnerung (3 Stufen) mit PDF + Endpoint

## 2. List of Changed/Added Files

### Backend
- `backend/app/models/customer.py` — Skonto + Verpackung Felder
- `backend/app/models/attachment.py` — seed_inventory entity_type
- `backend/app/models/growth_event.py` — **NEU**: GrowthBatchEvent
- `backend/app/models/app_setting.py` — (unverändert, bestand schon)
- `backend/app/models/__init__.py` — Exports
- `backend/app/schemas/customer.py` — Skonto + Verpackung Felder
- `backend/app/api/v1/imports.py` — Unicode-Normalize für Umlaut-Lookup
- `backend/app/api/v1/sales.py` — Auto-Kundennummer + Subscription-Fix
- `backend/app/api/v1/invoices.py` — payment-reminder Endpoint
- `backend/app/api/v1/production.py` — Timeline-Events Endpoints
- `backend/app/api/v1/attachments.py` — seed_inventory + ENTITY_MODELS
- `backend/app/services/invoice_service.py` — Customer-Default-Discount
- `backend/app/services/pdf_service.py` — Customer-Number + PaymentReminder PDF
- `backend/app/main.py` — Auto-Migration für SQLite

### Frontend
- `frontend/src/types/index.ts` — Customer + Invoice neue Felder
- `frontend/src/services/api.ts` — listEvents, generatePaymentReminder, adminApi
- `frontend/src/components/ui/Combobox.tsx` — **NEU**: Searchable Dropdown
- `frontend/src/components/ui/index.ts` — Combobox-Export
- `frontend/src/components/domain/CreateOrderModal.tsx` — Combobox + Bundle-Label
- `frontend/src/components/domain/GrowthTimelineModal.tsx` — **NEU**: Timeline-UI
- `frontend/src/components/domain/GrowBatchCard.tsx` — Timeline-Button
- `frontend/src/components/domain/SowingForm.tsx` — Saatgut-Charge-Warnung
- `frontend/src/components/domain/StockCorrectionModal.tsx` — Defensive Initial-Value
- `frontend/src/pages/Customers.tsx` — Kundennummer + Konditionen-Block
- `frontend/src/pages/Inventory.tsx` — Field-Mismatch-Fix + Attachments
- `frontend/src/pages/Orders.tsx` — Error-Handling mit Retry
- `frontend/src/pages/Products.tsx` — GrowPlan-Edit
- `frontend/src/pages/Production.tsx` — Timeline-Integration
- `frontend/src/pages/Invoices.tsx` — Mahnung-Button
- `frontend/src/pages/Abonnements.tsx` — Combobox

### Test / Doc Artefakte
- `frontend/tests/e2e/full-suite.spec.ts` — Playwright-Suite
- `frontend/playwright.config.ts` — Playwright-Config
- `scripts/api-smoke-test.sh` — curl-API-Suite
- `docs/legal-compliance-belege.md` — Gap-Analyse §14 UStG
- `docs/wave-2026-06-deliverables.md` — dieser Report

## 3. Database Changes

### Neue Tabellen
- `growth_batch_events(id, grow_batch_id, event_type, occurred_at, employee_name, notes, extra, created_at)` — Production-Timeline

### Neue Spalten (auto-migrate beim Startup)
- `customers.skonto_percent` (NUMERIC 5,2)
- `customers.skonto_days` (INTEGER)
- `customers.packaging_fee_amount` (NUMERIC 10,2)
- `customers.packaging_fee_percent` (NUMERIC 5,2)

### Erweiterte Enums
- `attachment.entity_type` += `seed_inventory`
- `growth_event_type` — 11 Werte (SOAKING/SOWING/MOVED/PACKAGING/NOTE)

## 4. New API Endpoints

| Method | Path | Beschreibung |
|---|---|---|
| GET | `/production/grow-batches/{id}/events` | Timeline-Events listen |
| POST | `/production/grow-batches/{id}/events` | Neuer Timeline-Event |
| GET | `/production/event-types` | Bekannte Event-Typen + Labels |
| POST | `/invoices/{id}/payment-reminder?level=1..3&dunning_fee=…` | Zahlungserinnerung PDF |
| POST | `/attachments/seed_inventory/{id}` | File-Upload für Saatgut-Charge |
| GET | `/admin/settings` | (bereits da) SMTP-Settings GUI-fähig |

## 5. Geänderte API-Verhalten

- `POST /sales/customers` — generiert KD-NNNNN automatisch wenn customer_number leer
- `POST /sales/subscriptions` — akzeptiert product_id ODER seed_id (vorher nur seed_id, daher 404)
- `GET /sales/customers?page_size=500` — Frontend setzt Default (vorher limitiert auf 20)
- `GET /production/grow-batches` — gibt flach `[]` zurück (Frontend war bisher `.items`-orientiert)
- `_get_customer` im History-Import — Unicode-Normalize (NFC + casefold) statt SQL-lower

## 6. Playwright Test Suite Overview

**Datei**: `frontend/tests/e2e/full-suite.spec.ts`

| Test-Bereich | Anzahl Test-Cases | Abdeckung |
|---|---|---|
| Customer Management | 3 | Create / Search-Umlaut / Edit |
| Products + Bundles | 2 | MICROGREEN + Variable-Bundle |
| Orders | 3 | Produkt-Bestellung / Bundle-Bestellung / Belegkette |
| Saatgut-Wareneingang | 1 | Attachment-Upload |
| Wachstumschargen | 2 | Visible-after-Create / 10-Step-Timeline |
| Wachstumspläne | 1 | Create + Edit |
| Subscriptions | 1 | Create mit product_id |
| Documents | 1 | Zahlungserinnerung-PDF-Download |
| **Total** | **14** | alle akzeptanzkritischen User-Flows |

**Lauf**:
```bash
cd frontend
BASE_URL=https://… BASIC_AUTH_USER=… BASIC_AUTH_PASS=… npx playwright test
```

Reports in `frontend/playwright-report/index.html`.

**Zusätzlich**: `scripts/api-smoke-test.sh` — pure curl/bash, schneller
Gate gegen die Demo-API, ~30 Assertions in 10 Bereichen.

## 7. Test Execution Results

Siehe separates Run-Log unten + `frontend/playwright-report/` nach UI-Lauf.

## 8. Remaining Known Issues / Backlog

Aus B8-Gap-Analyse abgeleitet:

### Update Commit b5e888a — Backlog jetzt umgesetzt:
1. ✅ Firmendaten-Block auf allen PDFs (USt-IdNr, IBAN, Adresse) → render_company_header/footer_block
2. ✅ Skonto-Hinweis-Text auf Rechnung → automatisch wenn customer.skonto_percent > 0
3. ✅ Bankverbindung auf Rechnung + Mahnung → render_company_footer_block aus Settings
4. ✅ Reverse-Charge-Vermerk bei STEUERFREI → automatisch wenn eine Line steuerfrei
6. ✅ Eigentumsvorbehalt-Klausel auf Rechnung → fester Footer-Text
7. ✅ Charge + MHD-Spalten auf Lieferschein → aus OrderLine + Harvest.seed_batch.mhd

### Update Commit 60a5610 — ALLE deferred Items umgesetzt:
5. ✅ **Customer-spezifische Preislisten** — `customer_prices`-Tabelle,
   `pricing_service.resolve_unit_price()`, Order-Engine nutzt
   Customer-Preis vor Default. UI: Tag-Button auf Customer-Karte →
   CustomerPricesModal mit Combobox-Suche, Gültigkeitszeitraum, Liste.
   API: GET/POST `/sales/customers/{id}/prices`, PATCH/DELETE
   `/sales/customer-prices/{id}`, GET `/sales/customers/{id}/effective-price/{product_id}`.
8. ✅ **Bundle-Inventory-Deduction** — `order_fulfillment_service.deduct_inventory_for_order()`
   bucht beim GELIEFERT-Übergang FIFO aus `finished_goods_inventory` für:
   - Reguläre Produkte → product_id × quantity
   - FIXED Bundles → jede Bundle-Komponente × line.menge
   - VARIABLE Bundles → jede `variable_bundle_selection` × line.menge
   Idempotent über `orders.inventory_deducted_at` (Auto-Migrate). Hook in
   `documents.mark_delivered` und `sales.update_order_status`.
9. ✅ **Order-History-Import mit Bundle-Sorten** — Neue optionale
   Excel-Spalte `bundle_selections` als JSON-String wie
   `[{"sku": "MG-SONNE", "quantity": 1}]`. Wird über SKU aufgelöst und
   nach `OrderLine.variable_bundle_selections` geschrieben.

### Konfiguration der Firmendaten

Damit die Compliance-Verbesserungen sichtbar werden, müssen die Settings
einmalig im Admin-Center gepflegt sein. Schnellster Pfad via API:

```bash
curl -X PATCH https://.../api/v1/admin/settings \
  -H "Content-Type: application/json" \
  -d '{
    "COMPANY_NAME": "Minga Greens GmbH",
    "COMPANY_ADDRESS_LINE1": "Musterstraße 1",
    "COMPANY_ADDRESS_LINE2": "80331 München",
    "COMPANY_USTID": "DE123456789",
    "COMPANY_BANK_NAME": "Stadtsparkasse München",
    "COMPANY_IBAN": "DE12 1234 5678 9012 3456 78",
    "COMPANY_BIC": "SSKMDEMM"
  }'
```

Ohne diese Werte fällt das PDF wieder auf "Minga Greens" als Fallback zurück.

## 9. Deployment Notes

Alle Änderungen sind auf der Railway-Demo unter
`https://minga-greens-temp-demo-production.up.railway.app` live.

- 8 Commits (5335e21 → 4a82d4c)
- Auto-Migration läuft beim Startup ohne RESET_DB
- Bestehende Daten erhalten

Login für Tester:
- `Thomas@minga-greens.de` / `MingaTest2026!`
- `gernot@minga-greens.de` / `MingaTest2026!`

---

**Autor**: Claude Opus 4.7 (1M context)
**Datum**: 2026-06-15
