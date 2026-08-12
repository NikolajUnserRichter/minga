# Gernot-Feedback: Bugs, Belege, Reset, Verbesserungen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline, batch mit Checkpoints). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle 8 gemeldeten Bugs fixen, Belege an Minga-Vorlagen angleichen, Prod-Daten-Reset (Saatgut/Chargen) mit g/kg-Ursachenfix, danach Verbesserungen (Phase 4 separat).

**Architecture:** Punkt-Fixes in bestehenden Modulen (FastAPI backend `backend/app`, React `frontend/src`); PDF-Anpassungen zentral in `pdf_service.py`; Prod-Reset als einmalige, gebackupte SQL-Operation auf minga.db via SSH/Container.

**Tech Stack:** FastAPI/SQLAlchemy/SQLite-per-Tenant, React/TS, ReportLab, pytest.

## Global Constraints

- Tenant-Migrationen via `tenancy._auto_migrate` (SQLite kann NOT NULL nicht lockern); Alembic nur zur Konsistenz.
- Bestehende Belege/Tenants dürfen sich nicht ändern, außer wo explizit gewünscht.
- Alle Fixes mit Test oder Live-Verify; Deploy via Coolify-Webhook, Verify auf demo.
- Prod-Reset NUR mit vorherigem Backup der minga.db.

---

## Phase 1 — Bugfixes (Root Causes bestätigt)

### Task 1: Verpackung-Tab weiß (Bug 1)
**Files:** Modify `frontend/src/pages/Inventory.tsx:634` (+ :249), `frontend/src/types/index.ts:687`
Backend liefert `sku`, Frontend liest `article_number` → `undefined.toLowerCase()` crasht sobald erste VERPACKUNG-Position existiert.
- [ ] TS-Typ `PackagingInventory`: `article_number` → `sku` (+ `supplier_name` prüfen)
- [ ] Inventory.tsx: alle `item.article_number`-Zugriffe auf `item.sku ?? ''` mit Optional-Chaining
- [ ] tsc + manueller Check

### Task 2: Template-Downloads 401 (Bug 2)
**Files:** Modify `frontend/src/components/common/ExcelImport.tsx:28-30, 51-55`
Raw `fetch` ohne Authorization-Header gegen auth-pflichtigen Router.
- [ ] Download+Upload über die geteilte axios-Instanz (`responseType: 'blob'`) statt fetch
- [ ] tsc + Live-Verify nach Deploy (Kunden-Template lädt)

### Task 3: Erntedaten-Berechnung (Bug 3)
**Files:** Modify `backend/app/api/v1/production.py:68-75`, `frontend/src/components/domain/SowingForm.tsx:84-86`
Erntefenster_*_tage sind Tage AB AUSSAAT (Gartenkresse: Keim 3 + Wachstum 3 → Fenster 6/7/8). Code addiert Keimdauer doppelt.
- [ ] Backend: `days=seed.erntefenster_*_tage` (Keimdauer raus)
- [ ] Frontend-Vorschau identisch fixen
- [ ] Test: Aussaat + optimal=7 → erwartete_ernte_optimal = Aussaat+7

### Task 4: Chargen-Übersicht „Unbekannt" (Bug 4)
**Files:** Modify `backend/app/api/v1/production.py` (list/get grow-batches), `backend/app/models/production.py`
`GrowBatchResponse.seed_name` wird nie befüllt.
- [ ] Property `seed_name` am GrowBatch-Model (`seed_batch.seed.name`, null-safe)
- [ ] `list_grow_batches`: joinedload bis Seed durchziehen (`joinedload(GrowBatch.seed_batch).joinedload(SeedBatch.seed)`)
- [ ] Test: Liste liefert seed_name

### Task 5: Abonnements weiß (Bug 5)
**Files:** Modify `frontend/src/pages/Abonnements.tsx:345, :595`
Produkt-Abos: `sub.seed_id.slice()` auf null.
- [ ] `sub.product_name || sub.seed_name || (sub.product_id ?? sub.seed_id ?? '').slice(0,8) || '—'` an beiden Stellen
- [ ] tsc

### Task 6: Bestellungen-Filter „Offen" 422 (Bug 6)
**Files:** Modify `frontend/src/pages/Orders.tsx:29`, `backend/app/api/v1/sales.py` (list_orders), `frontend/src/pages/Orders.tsx` Fehleranzeige
`OFFEN` ist kein OrderStatus.
- [ ] Backend: `status`-Param als String akzeptieren, Alias `OFFEN` → `IN (ENTWURF, BESTAETIGT, IN_PRODUKTION)`, sonst Enum-Parse
- [ ] Frontend: 422-Detail lesbar rendern (kein `[object Object]`)
- [ ] Test: `GET /sales/orders?status=OFFEN` → 200

### Task 7: DATEV-Export 500 (Bug 7)
**Files:** Modify `backend/app/api/v1/invoices.py:410, :433`; Test `backend/tests/test_datev_export.py`
`db: Session = Depends(DBSession)` erzeugt ungebundene Session (Annotated-Alias als Factory).
- [ ] Beide Signaturen auf `db: DBSession`
- [ ] API-Test: POST datev-export → 200/CSV

### Task 8: Verpackungsplan (Bug 8)
**Files:** Modify `backend/app/api/v1/production.py:326-378`, `frontend/src/pages/Production.tsx` (Anzeige)
Nur BESTAETIGT/IN_PRODUKTION mit Lieferdatum == target.
- [ ] Plan für Tag X: Lieferungen X+1 (Standard-Packtag) UND X (same-day), gruppiert mit `pack_reason`/Lieferdatum je Order
- [ ] ENTWURF-Bestellungen mitzählen, als „(Entwurf)" markiert
- [ ] Test: Bestellung morgen → erscheint im Plan heute

**Checkpoint 1:** pytest (production/sales/documents-Suiten) + tsc, Commit.

## Phase 2 — Belege an Vorlagen angleichen (alle Belegarten, pdf_service.py)

### Task 9: Kopf-Metablock
- [ ] Rechtsblock ergänzt: Kunden-Nr., „Ihre USt-IdNr." (customer.ust_id), Auftragsnummer (order.customer_reference), auf RE/LS/AB
### Task 10: Positionsspalten
- [ ] Artikel-Nr. (SKU) als eigene Spalte; EAN/GTIN als Zusatzzeile unter Beschreibung (wenn vorhanden)
- [ ] Fixed-Bundle: Komponentenliste („Radieschen | Erbse | …") unter Bundle-Name
- [ ] Einheiten-Label-Mapping (KARTON_6 → „Karton (6 Schalen)" bzw. „Kisten"-Kurzform aus UnitOfMeasure.symbol)
### Task 11: Texte/Labels
- [ ] Rabatt-Label pro Template konfigurierbar (`texts.discount_label`, Default „Rabatt"); Minga setzt „Jahresbonus und Verpackungspauschale"
- [ ] AB-Hinweistext als Default-Text ergänzen
### Task 12: LS-Summenblock bei Preis-Flag
- [ ] Wenn `show_prices_on_delivery_note`: zusätzlich USt-Spalte + Zwischensumme/USt/Endbetrag (wie Alt-Beleg Fruchthof)

**Checkpoint 2:** PDF-Content-Tests erweitern, Commit, Deploy, Live-Verify demo.

## Phase 3 — Reset + g/kg-Fix (Prod minga, freigegeben 12.08.)

### Task 13: g/kg-Ursache
- [ ] Wareneingang Saatgut: explizite Einheitenwahl g/kg im Frontend, Backend nimmt `unit` entgegen (Default kg bleibt)
### Task 14: Reset minga
- [ ] Backup minga.db (Container `/data/tenants/minga.db` → lokal, Zeitstempel)
- [ ] Löschen: harvests, grow_batches, seed_batches, seed-inventory (+ inventory_movements seed), Capacity-Belegung zurücksetzen
- [ ] Verify: Liste leer, App gesund

## Phase 4 — Verbesserungen (separat, Reihenfolge 3→5→1→2→6; Dienstplan (4) zurückgestellt)
- (3) Saatgut-Stammdaten voll editierbar (BIO-Flag) — Edit-Dialog erweitern
- (5) Substrattyp pro Sorte + Anzeige SowingForm/Arbeitsanweisung
- (1) Wachstumsparameter-Override pro Saatgutcharge
- (2) Sommer-/Winterzyklus (AppSetting + Zusatztage pro Sorte)
- (6) Tagesplan-Seite (Einweichen/Aussaat/Verpacken/Ausliefern)
- (7)(8) Go-Live-Importer: Wachstumschargen + Bestellungen 2026 (Excel)
