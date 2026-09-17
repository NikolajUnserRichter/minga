# Sonderpreise & Bestelländerung — Implementation Plan

> **For agentic workers:** Diesen Plan Task für Task abarbeiten. Schritte nutzen Checkbox-Syntax (`- [ ]`). Kein Task wird übersprungen oder zusammengefasst; wenn ein Schritt nicht funktioniert, melden statt umplanen.

**Goal:** Kundenspezifische Sonderpreise greifen bei der Bestellerfassung, und eine erfasste Bestellung lässt sich nachträglich ändern oder stornieren.

**Architecture:** Die Endpunkte für Bearbeiten und Stornieren *existieren*, aber drei von ihnen sind defekt und werfen 500 — das wurde am laufenden System nachgewiesen (siehe „Verifizierter Ausgangsbefund"). Reihenfolge deshalb: erst das Backend reparieren, dann die Oberfläche darauf bauen. Vier Backend-Defekte (Sonderpreis-Überschreibung durch Varianten, `PATCH /orders/{id}`, Positions-PATCH/DELETE, Statusroute), danach das Bestellformular auf den effektiven Preis umstellen und ein neues `EditOrderModal` ergänzen.

## Verifizierter Ausgangsbefund

Gegen die echte App gemessen (TestClient, `.venv`, 17.09.2026) — **nicht** aus dem Code abgeleitet:

```
Bestellung anlegen              201
PATCH Lieferdatum als ENTWURF   200
Bestellung bestätigen           200
PATCH Lieferdatum als BESTÄTIGT 500   ← Gernots Punkt 2
PATCH Position (Menge ändern)   500   ← Gernots Punkt 3
DELETE Position                 500   ← Gernots Punkt 3
```

Traceback bei den Positions-Endpunkten: `InvalidRequestError: The unique() method must be invoked on this Result, as it contains results that include joined eager loads against collections`.

Wer diesen Plan umsetzt, darf also **nicht** annehmen, ein Endpunkt funktioniere, nur weil er registriert ist.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (Mapped/mapped_column), SQLite pro Mandant, React + TypeScript, TanStack Query, Tailwind, `react-hot-toast`.

**Spec:** `260917_Buglog_Sprouddesk-MingaGreens.docx` (Gernot Kleinberger, 17.09.2026) — Punkte 1–3, plus ein bei der Analyse gefundener vierter Defekt.

## Global Constraints

- **Testumgebung:** Ausschließlich `/Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python`. `backend/venv` (3.9) und `backend/venv311` sind kaputt. Vollauf: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
- **Test-Baseline: 15 failed / 457 passed / 2 skipped / 1 error.** Diese 15 sind Altlasten. Nach jeder Änderung die *Liste* der Fehler vergleichen, nicht die Zahl. Neue Namen in der Liste = Regression.
- **Keine Schema-Änderung in diesem Plan.** Falls doch eine nötig scheint: stoppen und melden, nicht eigenmächtig eine Spalte anlegen (Migrationen laufen über `tenancy._auto_migrate`, nicht über Alembic).
- **Sprache:** Alle UI-Texte, Fehlermeldungen und Commit-Messages auf Deutsch. Die Oberfläche formuliert sachlich ("Lieferdatum ändern"), sie duzt und siezt nicht.
- **Geldbeträge** im Backend immer `Decimal`, nie `float`.
- Neue Tests gehören nach `backend/tests/test_gernot_260917.py` (Konvention: `test_gernot_<JJMMTT>.py`, siehe `test_gernot_260824.py`).

---

### Task 1: Varianten-Zweig darf den Sonderpreis nicht überschreiben

Der Backend-Lookup in `create_order` löst den Kundenpreis korrekt auf (`sales.py:949-958`), aber direkt danach überschreibt der Varianten-Zweig (`sales.py:975-978`) das Ergebnis bedingungslos mit `variant.price_override` bzw. `product.base_price`. Bei jedem Produkt mit Verpackungsvariante ist der Sonderpreis damit wirkungslos — auch nach dem Frontend-Fix aus Task 2.

**Files:**
- Modify: `backend/app/api/v1/sales.py:926-978`
- Test: `backend/tests/test_gernot_260917.py` (neu)

**Interfaces:**
- Consumes: `app.services.pricing_service.resolve_unit_price(db, customer_id, product_id, default, on_date) -> tuple[Decimal, bool]`
- Produces: keine neue Signatur. Verhaltensvertrag für Task 2: Schickt der Client `unit_price = 0` oder `null`, ermittelt der Server den Preis selbst, und ein Sonderpreis schlägt sowohl `base_price` als auch `variant.price_override`.

- [ ] **Step 1: Failing Test schreiben**

Neue Datei `backend/tests/test_gernot_260917.py`:

```python
"""Gernot-Feedback vom 17.09.2026 — Bestellerfassung.

(1) Hinterlegte Sonderpreise wurden in der Bestellung nicht angezeigt und
    nicht übernommen (AB-20260917-0001, Kunde Ferdinand Bierbichler).
"""
from decimal import Decimal

import pytest


def _kunde(client, name="Ferdinand Bierbichler GmbH & Co. KG"):
    # Pflichtfeld heißt "typ" (CustomerType: GASTRO | HANDEL | GEWERBE | PRIVAT).
    # Ein Feld "kundengruppe" gibt es nicht — der Endpunkt antwortet dann mit 422.
    r = client.post("/api/v1/sales/customers", json={
        "name": name, "typ": "GASTRO",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _produkt(client, name, sku, preis, **extra):
    r = client.post("/api/v1/products", json={
        "name": name, "sku": sku, "base_price": str(preis),
        "einheit": "STK", **extra,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


def _sonderpreis(client, kunde, produkt, preis):
    r = client.post(f"/api/v1/sales/customers/{kunde['id']}/prices", json={
        "product_id": produkt["id"], "unit_price": str(preis),
        "valid_from": "2026-09-03",
    })
    assert r.status_code in (200, 201), r.text
    return r.json()


class TestSonderpreisInBestellung:
    """Punkt 1: Sonderpreis schlägt Listenpreis und Varianten-Override."""

    def test_sonderpreis_schlaegt_basispreis(self, client):
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Gourmetmix (VPE 6)", "MG-11002", Decimal("12.99"))
        _sonderpreis(client, kunde, produkt, Decimal("12.49"))

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"], "quantity": 2,
                "unit": "STK", "unit_price": 0, "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("12.49")

    def test_sonderpreis_schlaegt_varianten_override(self, client):
        """Regression: der Varianten-Zweig hat den Sonderpreis überschrieben."""
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Kiste | Erbse", "MG-12005", Decimal("12.49"))
        _sonderpreis(client, kunde, produkt, Decimal("11.99"))

        rv = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
            "name_suffix": "VPE 6", "price_override": "12.49",
        })
        assert rv.status_code in (200, 201), rv.text
        variante = rv.json()

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"],
                "product_variant_id": variante["id"],
                "quantity": 2, "unit": "STK", "unit_price": 0,
                "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("11.99")

    def test_expliziter_preis_bleibt_unangetastet(self, client):
        """Ein bewusst gesetzter Preis darf nicht wegoptimiert werden."""
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Genussmix (VPE 6)", "MG-11001", Decimal("11.99"))
        _sonderpreis(client, kunde, produkt, Decimal("11.99"))

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"], "quantity": 1,
                "unit": "STK", "unit_price": "9.50", "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("9.50")

    def test_mitgesendeter_preis_ueberlebt_die_variante(self, client):
        """DER Test, der zählt.

        Nach Task 2 schickt das Frontend immer einen konkreten Preis — nämlich
        den bereits aufgelösten Sonderpreis. Der Varianten-Zweig darf ihn dann
        NICHT mehr überschreiben. Ohne diesen Test bleiben die drei Tests
        darüber grün, während Gernots Bug in der echten Oberfläche weiterlebt,
        weil dort nie ein Preis von 0 ankommt.
        """
        kunde = _kunde(client)
        produkt = _produkt(client, "BIO Kiste | Erbse", "MG-12005", Decimal("12.49"))
        _sonderpreis(client, kunde, produkt, Decimal("11.99"))

        rv = client.post(f"/api/v1/products/{produkt['id']}/variants", json={
            "name_suffix": "VPE 6", "price_override": "12.49",
        })
        assert rv.status_code in (200, 201), rv.text

        r = client.post("/api/v1/sales/orders", json={
            "customer_id": kunde["id"],
            "requested_delivery_date": "2026-09-18",
            "lines": [{
                "product_id": produkt["id"],
                "product_variant_id": rv.json()["id"],
                "quantity": 2, "unit": "STK",
                "unit_price": "11.99",          # <- so verhält sich das neue Frontend
                "product_name": produkt["name"],
            }],
        })
        assert r.status_code == 201, r.text
        assert Decimal(str(r.json()["lines"][0]["unit_price"])) == Decimal("11.99")
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260917.py -v`

Erwartet: **zwei** Fehlschläge — `test_sonderpreis_schlaegt_varianten_override` und `test_mitgesendeter_preis_ueberlebt_die_variante`, beide mit `12.49 != 11.99`. Die anderen beiden sind bereits grün. Sieht das Bild anders aus, **stoppen und melden**, dann ist die Ursache eine andere als analysiert.

Prüfen, ob die Hilfsfunktionen zu den echten Endpunkten passen (`base_price`, Variantenpfad `POST /products/{id}/variants`). Weichen sie ab, die Helfer an die tatsächlichen Schemata anpassen — die Testabsicht bleibt gleich.

- [ ] **Step 3: Minimalen Fix implementieren**

In `backend/app/api/v1/sales.py`, `create_order`. Die Regel, die am Ende gelten muss, in einem Satz: **ein vom Client mitgeschickter Preis ist verbindlich und wird von nichts mehr überschrieben; nur wenn keiner kommt, ermittelt der Server ihn — Kundenpreis vor Varianten-Override vor Basispreis.**

Ein bloßes Flag „stammt aus dem Kundenpreis" reicht dafür NICHT. Sobald das Frontend aus Task 2 den aufgelösten Sonderpreis mitschickt, läuft der Lookup-Zweig gar nicht mehr, das Flag bliebe `False`, und der Varianten-Zweig würde den korrekten Preis wieder überschreiben — der Bug wäre zurück, während die Tests grün bleiben.

Vor der Positionsschleife (bei `line_price = line_data.unit_price`, ca. Zeile 931) ergänzen:

```python
        # Hat der Client einen Preis mitgeschickt? Dann ist er verbindlich —
        # gleich ob aus dem Sonderpreis-Lookup des Formulars oder von Hand
        # eingetragen. Weder Kundenpreis noch Varianten-Override fassen ihn danach an.
        client_hat_preis = line_data.unit_price not in (None, 0, Decimal("0"))
        line_price = line_data.unit_price
        preis_ist_kundenspezifisch = False
```

Den Kundenpreis-Zweig (ca. Zeile 949-958) auf die neue Bedingung umstellen:

```python
            if not client_hat_preis:
                from datetime import date as _date
                cp_price, is_cp = _resolve_unit_price(
                    db,
                    customer_id=order_data.customer_id,
                    product_id=line_data.product_id,
                    default=product.base_price,
                    on_date=_date.today(),
                )
                line_price = cp_price
                preis_ist_kundenspezifisch = is_cp
```

Im Varianten-Zweig (ca. Zeile 975-978) den Preisteil doppelt bedingen:

```python
            # Weder ein mitgeschickter Preis noch ein Kundenpreis darf hier
            # überschrieben werden. Ein Sonderpreis gilt für das Produkt
            # einschließlich seiner Verpackungsvarianten.
            if not client_hat_preis and not preis_ist_kundenspezifisch:
                if variant.price_override is not None:
                    line_price = variant.price_override
                elif product and product.base_price is not None:
                    line_price = product.base_price
```

Name und Einheit aus der Variante werden weiterhin unbedingt gesetzt — nur die Preiszuweisung wandert in die Bedingung.

- [ ] **Step 4: Tests laufen lassen, grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260917.py -v`
Erwartet: 4 passed.

- [ ] **Step 5: Gesamtsuite gegen die Baseline prüfen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
Erwartet: 15 failed / 461 passed / 2 skipped / 1 error — dieselben 15 Namen wie in der Baseline. Steht ein neuer Name in der Liste, ist das eine Regression: beheben, nicht wegdiskutieren.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/sales.py backend/tests/test_gernot_260917.py
git commit -m "fix(bestellung): Sonderpreis wird von Verpackungsvariante nicht mehr überschrieben"
```

---

### Task 2: Bestellformular zieht den effektiven Preis

Ursache von Gernots Punkt 1: `CreateOrderModal` setzt bei Produktauswahl `unit_price = selectedItem.price` (Listenpreis) und sendet den mit. Das Backend wertet jeden Preis ≠ 0 als bewussten Override und überspringt den Lookup aus Task 1. Der Client `customerPricesApi.getEffective` existiert bereits in `api.ts:1148` und wird nirgends benutzt.

**Files:**
- Modify: `frontend/src/components/domain/CreateOrderModal.tsx:190-218` (Preisauflösung), sowie Kundenwechsel-Handler und Positions-Rendering
- Test: manuell im Browser (Schritt 6) — das Repo hat für Modals keine Unit-Tests

**Interfaces:**
- Consumes: `customerPricesApi.getEffective(customerId, productId) → { unit_price: string; is_customer_specific: boolean; base_price: string | null }`
- Produces: `OrderLineRow` bekommt zwei Felder — `is_customer_specific: boolean` und `price_manually_edited: boolean`

- [ ] **Step 1: Zeilen-Typ um die zwei Flags erweitern**

In `CreateOrderModal.tsx` im `OrderLineRow`-Interface (ca. Zeile 22) ergänzen:

```ts
    is_customer_specific: boolean;
    price_manually_edited: boolean;
```

Und im Default-Zeilenobjekt (ca. Zeile 32, wo `unit_price: 0` steht):

```ts
    is_customer_specific: false,
    price_manually_edited: false,
```

- [ ] **Step 2: Preisauflösung als eigene Funktion**

Oberhalb von `updateLine` einfügen. Die Funktion ist async und schreibt per funktionalem `setLines`, damit sie nicht auf einem veralteten `lines`-Stand arbeitet:

```ts
    const resolvePriceForLine = async (index: number, productId: string) => {
        if (!customerId || !productId) return;
        try {
            const eff = await customerPricesApi.getEffective(customerId, productId);
            setLines((prev) => {
                const next = [...prev];
                if (!next[index] || next[index].product_id !== productId) return prev;
                if (next[index].price_manually_edited) return prev;
                next[index] = {
                    ...next[index],
                    unit_price: Number(eff.unit_price),
                    is_customer_specific: eff.is_customer_specific,
                };
                return next;
            });
        } catch {
            // Kein Sonderpreis ermittelbar: der bereits gesetzte Listenpreis bleibt stehen.
        }
    };
```

`customerPricesApi` oben importieren, falls noch nicht vorhanden — es liegt im selben Modul wie `salesApi` in `frontend/src/services/api.ts`.

- [ ] **Step 3: `updateLine` anbinden**

In `updateLine` (ca. Zeile 194-203) den Produktzweig ergänzen. Der Listenpreis bleibt als Sofortanzeige stehen, die Auflösung korrigiert ihn gleich darauf:

```ts
        if (field === 'product_id') {
            const selectedItem = availableItems.find(p => p.id === value);
            if (selectedItem) {
                newLines[index].product_name = selectedItem.name;
                newLines[index].unit_price = selectedItem.price;
                newLines[index].unit = selectedItem.unit || 'g';
                newLines[index].product_variant_id = '';
                newLines[index].is_customer_specific = false;
                newLines[index].price_manually_edited = false;
            }
            if (value) {
                loadVariantsForProduct(value);
                void resolvePriceForLine(index, value);
            }
        }
```

Im Varianten-Zweig (ca. Zeile 205-215) den Preis nur setzen, wenn kein Sonderpreis gilt:

```ts
            if (variant) {
                if (variant.packaging_unit_code) newLines[index].unit = variant.packaging_unit_code;
                if (variant.price_override !== null && !newLines[index].is_customer_specific) {
                    newLines[index].unit_price = Number(variant.price_override);
                }
                if (variant.name_suffix) {
                    newLines[index].product_name = `${availableItems.find(p => p.id === newLines[index].product_id)?.name || ''} — ${variant.name_suffix}`;
                }
            }
```

Und ganz am Anfang von `updateLine`, damit eine Handeingabe die Auflösung dauerhaft schlägt:

```ts
        if (field === 'unit_price') {
            newLines[index].price_manually_edited = true;
            newLines[index].is_customer_specific = false;
        }
```

- [ ] **Step 4: Kundenwechsel löst Neuberechnung aus**

Wird der Kunde gewechselt, nachdem Positionen erfasst sind, gelten andere Sonderpreise. `useEffect` ergänzen (nach den bestehenden Effects):

```ts
    useEffect(() => {
        if (!customerId) return;
        lines.forEach((l, i) => {
            if (l.product_id && !l.price_manually_edited) void resolvePriceForLine(i, l.product_id);
        });
        // Absichtlich nur an customerId gebunden: die Auflösung soll beim
        // Kundenwechsel laufen, nicht bei jeder Mengenänderung.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [customerId]);
```

- [ ] **Step 5: Sonderpreis sichtbar machen**

Gernot hat ausdrücklich gemeldet, dass der Sonderpreis *nicht angezeigt* wird. Im Positions-Rendering direkt unter dem Preis-Input (ca. Zeile 383-385) ergänzen:

```tsx
                                {line.is_customer_specific && (
                                    <span className="mt-1 inline-block text-xs font-medium text-green-700 dark:text-green-400">
                                        Sonderpreis
                                    </span>
                                )}
```

- [ ] **Step 6: Im Browser gegen Gernots Fall prüfen**

Build: `cd frontend && npm run build` — muss ohne TypeScript-Fehler durchlaufen.

Dann `npm run dev`, Kunde mit hinterlegten Sonderpreisen wählen und exakt Gernots Bestellung nachstellen:

| Art.-Nr. | Menge | erwarteter Preis |
|---|---|---|
| MG-11001 | 10 | 11,99 € |
| MG-11002 | 2 | **12,49 €** (vorher 12,99 €) |
| MG-12004 | 10 | 10,99 € |
| MG-12005 | 2 | **11,99 €** (vorher 12,49 €) |

Alle vier müssen das Label „Sonderpreis" tragen. Netto muss **278,76 €** ergeben statt der fehlerhaften 280,76 € (10×11,99 + 2×12,49 + 10×10,99 + 2×11,99 = 119,90 + 24,98 + 109,90 + 23,98). Screenshot für Gernot aufheben.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/domain/CreateOrderModal.tsx
git commit -m "fix(bestellung): Sonderpreise werden im Bestellformular geladen und ausgewiesen"
```

---

### Task 3: Kaputte Statusroute reparieren

Bei der Analyse gefunden, von Gernot nicht gemeldet: `salesApi.updateOrderStatus` ruft `POST /sales/orders/{id}/status/{status}`. Diese Route existiert nicht — das Backend hat `POST /orders/{order_id}/status` und erwartet den Status im Body. Zusätzlich ist `'BEREIT'` in `OrderStatus` gar nicht definiert (gültig: `ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT`). Die Buttons „Bereit" und „Geliefert" in der Bestellliste laufen einzeln und als Sammelaktion ins Leere.

Das reicht tiefer als zunächst angenommen: `BEREIT` steht an **11 Stellen in 5 Dateien**, und das Frontend führt ein eigenes Statusmodell, das nicht zum Backend passt.

```
frontend/src/types/index.ts:197            'OFFEN' | 'BESTAETIGT' | 'IN_PRODUKTION' | 'BEREIT' | 'GELIEFERT' | 'STORNIERT'
frontend/src/components/ui/Badge.tsx:68    BEREIT: { label: 'Bereit', variant: 'success' }
frontend/src/components/domain/OrderCard.tsx:22   canMarkDelivered = order.status === 'BEREIT'
frontend/src/pages/Sales.tsx:55,101,378    updateOrderStatus(id, 'BEREIT') + Filter + Detailansicht
frontend/src/pages/Orders.tsx:33,77,103,117,339
```

Backend-Wahrheit (`app/models/enums.py:56-63`): `ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT`. Das Frontend erfindet `OFFEN` und `BEREIT` und kennt `ENTWURF` und `FAKTURIERT` nicht. Abbildung: `OFFEN → ENTWURF`, `BEREIT → IN_PRODUKTION`, `FAKTURIERT` neu aufnehmen.

**Files:**
- Modify: `frontend/src/services/api.ts:363-364`
- Modify: `frontend/src/types/index.ts:197`
- Modify: `frontend/src/components/ui/Badge.tsx:68`
- Modify: `frontend/src/components/domain/OrderCard.tsx:22`
- Modify: `frontend/src/pages/Orders.tsx:33, 77, 103, 117, 339`
- Modify: `frontend/src/pages/Sales.tsx:55, 101, 378`

**Interfaces:**
- Produces: `salesApi.updateOrderStatus(id: string, status: string, reason?: string) → Promise<Order>` — sendet jetzt einen Body `{ status, reason }`. Task 4 baut darauf auf.

- [ ] **Step 1: Client auf Body umstellen**

In `frontend/src/services/api.ts`:

```ts
  updateOrderStatus: (id: string, status: string, reason?: string) =>
    api.post<Order>(`/sales/orders/${id}/status`, { status, reason }).then(r => r.data),
```

- [ ] **Step 2: Statusmodell des Frontends an das Backend angleichen**

Zuerst den Typ in `frontend/src/types/index.ts:197` wahrheitsgemäß machen:

```ts
export type OrderStatus = 'ENTWURF' | 'BESTAETIGT' | 'IN_PRODUKTION' | 'GELIEFERT' | 'FAKTURIERT' | 'STORNIERT'
```

Danach zeigt der TypeScript-Compiler jede verbliebene Stelle von selbst an — `npm run build` ist hier das Suchwerkzeug, nicht die Zeilenliste oben. Jede gemeldete Stelle nach dieser Abbildung korrigieren:

| alt (erfunden) | neu (Backend) | Beschriftung für Gernot |
|---|---|---|
| `OFFEN` | `ENTWURF` | „Entwurf" |
| `BEREIT` | `IN_PRODUKTION` | „In Produktion" |
| — | `FAKTURIERT` | „Fakturiert" (neu ergänzen) |

In `Badge.tsx:68` den Schlüssel `BEREIT` auf `IN_PRODUKTION` umbenennen und Einträge für `ENTWURF` und `FAKTURIERT` ergänzen, sonst zeigt die Liste bei diesen Status ein leeres Abzeichen.

**Nicht übersehen:** `frontend/src/pages/Sales.tsx:55` enthält denselben defekten Aufruf wie `Orders.tsx:77`. Beide Seiten müssen umgestellt werden, sonst bleibt der Fehler auf einer davon bestehen.

- [ ] **Step 2b: Prüfen, ob noch eine erfundene Konstante übrig ist**

Run: `cd frontend && grep -rn "BEREIT" src --include="*.ts" --include="*.tsx"`
Erwartet: **keine Treffer.** `BEREIT` hat im ganzen System keine legitime Verwendung.

Run: `cd frontend && grep -rn "'OFFEN'" src --include="*.ts" --include="*.tsx"`
Erwartet: **nur Treffer im Rechnungskontext.** `OFFEN` ist ein gültiger Rechnungsstatus (`enums.py:33` — „Gesendet, wartet auf Zahlung") und gehört zu Recht in `InvoiceStatus` (`types/index.ts:588`). Solche Treffer bleiben unverändert. Zu ändern ist nur, wo `OFFEN` als *Bestell*status verwendet wird.

Jeder verbleibende Bestellstatus-Treffer ist eine Stelle, die zur Laufzeit still ins Leere läuft — der Compiler fängt Vergleiche gegen Stringliterale nicht überall ab.

- [ ] **Step 3: Übergangsfehler sichtbar machen**

Das Backend antwortet bei ungültigem Übergang mit 400 und einer präzisen Meldung (`Ungültiger Statusübergang: X → Y`). Die soll der Anwender sehen statt einer generischen Meldung. In den `catch`-Blöcken von `handleMarkReady`/`handleMarkDelivered` und den Sammelaktionen:

```ts
        } catch (e: any) {
            toast.error(e?.response?.data?.detail ?? 'Status konnte nicht geändert werden');
        }
```

- [ ] **Step 4: Im Browser prüfen**

`cd frontend && npm run build` muss sauber sein. Dann im Dev-Server eine bestätigte Bestellung auf „In Produktion" und danach auf „Geliefert" setzen — beides muss funktionieren und die Liste aktualisieren. Eine Bestellung im Status ENTWURF auf „Geliefert" setzen muss die Backend-Meldung als Toast zeigen, nicht stumm scheitern.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api.ts \
        frontend/src/types/index.ts \
        frontend/src/components/ui/Badge.tsx \
        frontend/src/components/domain/OrderCard.tsx \
        frontend/src/pages/Orders.tsx \
        frontend/src/pages/Sales.tsx
git commit -m "fix(bestellung): Statuswechsel rief eine nicht existierende Route mit ungültigem Status"
```

---

### Task 3b: Die drei defekten Bearbeiten-Endpunkte reparieren

**Dieser Task muss vor Task 4 fertig sein.** Das Edit-Modal baut auf genau diesen Endpunkten auf, und alle drei werfen heute 500 (nachgewiesen, siehe „Verifizierter Ausgangsbefund" oben). Würde Task 4 zuerst gebaut, klickte Gernot in eine Oberfläche, hinter der jeder Aufruf scheitert.

Zwei unabhängige Ursachen:

1. **`PATCH /orders/{id}`** — `update_order` liest in `sales.py:1097` `order_data.change_reason`, aber `OrderUpdate` (`schemas/order.py:153-163`) hat dieses Feld nicht. Bei einem Entwurf fällt das nicht auf, weil der Audit-Log-Block nur für `status != ENTWURF` läuft. Sobald die Bestellung bestätigt ist, schlägt `AttributeError` durch.
2. **`PATCH`/`DELETE` auf Positionen** — beide lösen `joinedload(Order.lines)` mit `.scalar_one_or_none()` auf, ohne vorher `.unique()` zu rufen. SQLAlchemy 2.0 wirft dafür `InvalidRequestError`. `update_order` eine Funktion weiter oben macht es richtig (`.unique().scalar_one_or_none()`) — das ist die Vorlage.

**Files:**
- Modify: `backend/app/schemas/order.py:153-163` (`OrderUpdate`)
- Modify: `backend/app/api/v1/sales.py:1077` (Feld-Schleife), `:1386` und `:1456` (`.unique()`)
- Test: `backend/tests/test_gernot_260917.py` (erweitern)

**Interfaces:**
- Produces: `PATCH /sales/orders/{id}` akzeptiert zusätzlich `change_reason: Optional[str]`; die drei Endpunkte antworten für bestätigte Bestellungen mit 200 bzw. 204. Task 4 setzt das voraus.

- [ ] **Step 1: Failing Tests schreiben**

An `backend/tests/test_gernot_260917.py` anhängen:

```python
def _bestellung(client, kunde):
    r = client.post("/api/v1/sales/orders", json={
        "customer_id": kunde["id"],
        "requested_delivery_date": "2026-09-18",
        "lines": [{
            "product_name": "Freitext-Position", "quantity": 1,
            "unit": "STK", "unit_price": "5.00",
        }],
    })
    assert r.status_code == 201, r.text
    return r.json()


class TestBestellungAendern:
    """Punkte 2 und 3: eine bestätigte Bestellung muss änderbar sein."""

    def test_lieferdatum_der_bestaetigten_bestellung_aendern(self, client):
        """Gernots Punkt 2. Als Entwurf ging das schon, als bestätigt kam ein 500."""
        kunde = _kunde(client, "Änderungs-Testkunde")
        best = _bestellung(client, kunde)
        assert client.post(f"/api/v1/sales/orders/{best['id']}/confirm", json={}).status_code == 200

        r = client.patch(f"/api/v1/sales/orders/{best['id']}",
                         json={"requested_delivery_date": "2026-09-19"})
        assert r.status_code == 200, r.text
        assert r.json()["requested_delivery_date"] == "2026-09-19"

    def test_aenderungsgrund_wird_angenommen(self, client):
        kunde = _kunde(client, "Grund-Testkunde")
        best = _bestellung(client, kunde)
        client.post(f"/api/v1/sales/orders/{best['id']}/confirm", json={})

        r = client.patch(f"/api/v1/sales/orders/{best['id']}", json={
            "requested_delivery_date": "2026-09-19",
            "change_reason": "Kunde hat telefonisch verschoben",
        })
        assert r.status_code == 200, r.text

    def test_position_aendern_und_entfernen(self, client):
        """Gernots Punkt 3. Beide Endpunkte lieferten 500."""
        kunde = _kunde(client, "Positions-Testkunde")
        best = _bestellung(client, kunde)
        lid = best["lines"][0]["id"]

        r = client.patch(f"/api/v1/sales/orders/{best['id']}/lines/{lid}",
                         json={"quantity": 3})
        assert r.status_code == 200, r.text

        r = client.delete(f"/api/v1/sales/orders/{best['id']}/lines/{lid}")
        assert r.status_code == 204, r.text
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260917.py::TestBestellungAendern -v`

Erwartet: alle drei FAIL mit 500. Genau dieses Bild wurde am 17.09. gemessen — kommt ein anderes heraus, **stoppen und melden**.

- [ ] **Step 3: `change_reason` ins Schema**

In `backend/app/schemas/order.py`, `OrderUpdate` (nach Zeile 163):

```python
    change_reason: Optional[str] = Field(None, description="Grund der Änderung, landet im Audit-Log")
```

Das ist **keine** Datenbank-Schema-Änderung — die Spalte `reason` existiert im Audit-Log-Modell bereits. Die Global Constraint „Keine Schema-Änderung" ist damit nicht verletzt, hier also nicht stoppen.

- [ ] **Step 4: `change_reason` aus der Feld-Schleife nehmen**

In `backend/app/api/v1/sales.py`, `update_order`, ca. Zeile 1078:

```python
        if field in ("lines", "change_reason"):
            continue  # Lines separat behandelt; change_reason ist kein Order-Feld
```

Ohne das schriebe `setattr` ein Feld auf das Order-Objekt, das es nicht gibt, und der Grund tauchte als Schein-Änderung im Audit-Diff auf.

- [ ] **Step 5: `.unique()` bei den Positions-Endpunkten**

In `backend/app/api/v1/sales.py` in `update_order_line` (ca. Zeile 1386) und `delete_order_line` (ca. Zeile 1456) jeweils:

```python
    order = db.execute(
        select(Order)
        .options(joinedload(Order.lines))
        .where(Order.id == order_id)
    ).unique().scalar_one_or_none()
```

Nur `.unique()` einfügen — identisch zu `update_order` in derselben Datei. Sonst nichts ändern.

- [ ] **Step 5b: Antwort vollständig serialisieren**

Der `.unique()`-Fix legt einen dahinterliegenden Defekt frei: die Endpunkte kommen jetzt bis zum Antwortaufbau und scheitern dort mit `ValidationError: 7 validation errors for OrderLineResponse`. Es fehlen `seed_id`, `product_sku`, `product_description`, `harvest_id`, `batch_number`, `created_at`, `updated_at`.

Betroffen sind **beide** handgebauten Antworten: `add_order_line` (ca. Zeile 1365) und `update_order_line` (ca. Zeile 1436). `add_order_line` ist damit heute ebenfalls kaputt — Task 4 braucht ihn für „Position hinzufügen".

Die korrekte Vorlage steht in derselben Datei bei **Zeile 740-764** und wird 1:1 übernommen. Die sieben fehlenden Zuweisungen lauten:

```python
            seed_id=line.seed_id,
            product_sku=line.product_sku,
            product_description=line.beschreibung,  # Mapping beschreibung -> product_description
            harvest_id=line.harvest_id,
            batch_number=line.batch_number,
            created_at=line.created_at,
            updated_at=line.updated_at,
```

Zusätzlich `product_variant_id=line.product_variant_id` und `variable_bundle_selections=line.variable_bundle_selections` übernehmen, falls sie an der jeweiligen Stelle fehlen — die Vorlage bei 740 hat beide.

Sechs der sieben Felder existieren als Spalten auf `OrderLine`; nur `product_description` ist abgeleitet und kommt aus `line.beschreibung`. Das Schema **nicht** aufweichen: die Felder als optional zu deklarieren würde die funktionierende Vorlage bei 740 stillschweigend mitverändern.

- [ ] **Step 6: Tests grün bestätigen**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/test_gernot_260917.py -v`
Erwartet: 7 passed (4 aus Task 1, 3 neue).

- [ ] **Step 7: Gesamtsuite gegen die Baseline**

Run: `cd backend && /Users/nikolajunser-richter/minga-greens-erp/.venv/bin/python -m pytest tests/ -q --ignore=tests/test_forecast_engine.py`
Erwartet: dieselben 15 Altlast-Namen, keine neuen.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/order.py backend/app/api/v1/sales.py backend/tests/test_gernot_260917.py
git commit -m "fix(bestellung): PATCH und Positions-Endpunkte warfen 500 statt zu ändern"
```

---

### Task 4: Bestellung bearbeiten und stornieren

Die Endpunkte sind ab Task 3b tatsächlich benutzbar. Was fehlt, ist die Oberfläche: unter `components/domain/` gibt es nur `CreateOrderModal`, `OrderCard`, `OrderDocumentsModal` — kein Bearbeiten-Modal.

**Files:**
- Create: `frontend/src/components/domain/EditOrderModal.tsx`
- Modify: `frontend/src/services/api.ts` (vier fehlende Methoden)
- Modify: `frontend/src/pages/Orders.tsx` (Modal einhängen, Aktion an der Zeile)

**Interfaces:**
- Consumes: `salesApi.updateOrderStatus(id, status, reason?)` aus Task 3
- Produces: `EditOrderModal({ open, order, onClose }: { open: boolean; order: Order | null; onClose: () => void })`

- [ ] **Step 1: Fehlende API-Methoden ergänzen**

In `frontend/src/services/api.ts` bei `salesApi`, direkt nach `updateOrderStatus`:

```ts
  updateOrder: (id: string, data: {
    requested_delivery_date?: string
    confirmed_delivery_date?: string
    packing_date?: string
    customer_reference?: string
    notes?: string
    change_reason?: string
  }) => api.patch<Order>(`/sales/orders/${id}`, data).then(r => r.data),

  addOrderLine: (orderId: string, data: {
    product_id?: string
    product_variant_id?: string
    product_name: string
    quantity: number
    unit: string
    unit_price: number
  }) => api.post(`/sales/orders/${orderId}/lines`, data).then(r => r.data),

  updateOrderLine: (orderId: string, lineId: string, data: {
    quantity?: number
    unit_price?: number
    product_name?: string
  }) => api.patch(`/sales/orders/${orderId}/lines/${lineId}`, data).then(r => r.data),

  deleteOrderLine: (orderId: string, lineId: string) =>
    api.delete(`/sales/orders/${orderId}/lines/${lineId}`).then(r => r.data),
```

- [ ] **Step 2: `EditOrderModal` anlegen**

Neue Datei `frontend/src/components/domain/EditOrderModal.tsx`. Aufbau als drei Blöcke in einem Modal: Kopfdaten, Positionen, Stornieren. Das Modal orientiert sich an `CreateOrderModal` (gleiche Modal-Hülle, gleiche Button-Komponenten), ist aber bewusst eine eigene Datei — `CreateOrderModal` ist bereits über 400 Zeilen, und Bearbeiten arbeitet gegen andere Endpunkte (Einzel-PATCH statt Sammel-POST).

Kernverhalten, das implementiert sein muss:

```tsx
    // Kopfdaten: ein PATCH mit nur den geänderten Feldern
    const saveHeader = async () => {
        await salesApi.updateOrder(order.id, {
            requested_delivery_date: deliveryDate || undefined,
            customer_reference: customerReference || undefined,
            notes: notes || undefined,
            change_reason: changeReason || undefined,
        });
        await queryClient.invalidateQueries({ queryKey: ['orders'] });
        toast.success('Bestellung aktualisiert');
    };

    // Position ändern: PATCH pro Zeile, erst beim Verlassen des Feldes
    const saveLine = async (lineId: string, quantity: number, unitPrice: number) => {
        await salesApi.updateOrderLine(order.id, lineId, {
            quantity, unit_price: unitPrice,
        });
        await queryClient.invalidateQueries({ queryKey: ['orders'] });
    };

    // Position entfernen: mit Rückfrage, weil unwiderruflich
    const removeLine = async (lineId: string, bezeichnung: string) => {
        if (!window.confirm(`Position "${bezeichnung}" aus der Bestellung entfernen?`)) return;
        await salesApi.deleteOrderLine(order.id, lineId);
        await queryClient.invalidateQueries({ queryKey: ['orders'] });
        toast.success('Position entfernt');
    };

    // Stornieren: Grund ist Pflicht, landet im Audit-Log
    const cancelOrder = async () => {
        if (!cancelReason.trim()) return toast.error('Bitte einen Stornogrund angeben');
        if (!window.confirm('Bestellung wirklich stornieren? Das lässt sich nicht rückgängig machen.')) return;
        await salesApi.updateOrderStatus(order.id, 'STORNIERT', cancelReason);
        await queryClient.invalidateQueries({ queryKey: ['orders'] });
        toast.success('Bestellung storniert');
        onClose();
    };
```

Für „Position hinzufügen" die Produktauswahl aus `CreateOrderModal` wiederverwenden und den Preis über `customerPricesApi.getEffective` auflösen — sonst reißt Task 2 hier wieder auf. Der Aufruf ist derselbe wie in Task 2, Step 2.

- [ ] **Step 3: Zustände abfangen, die das Backend ablehnt**

Das Backend weist bearbeitete Stornos ab (`sales.py:1068`: „Stornierte Bestellung kann nicht bearbeitet werden") und lässt STORNIERT nur aus ENTWURF und BESTAETIGT zu. Die UI muss das vorher zeigen statt den Anwender in einen 400 laufen zu lassen:

```tsx
    const istStorniert = order.status === 'STORNIERT';
    const stornierbar = order.status === 'ENTWURF' || order.status === 'BESTAETIGT';
```

Bei `istStorniert` alle Eingaben deaktivieren und einen Hinweis zeigen. Den Stornieren-Block nur rendern, wenn `stornierbar`; sonst den Grund nennen ("Eine Bestellung in Produktion kann nicht mehr storniert werden").

- [ ] **Step 4: In der Bestellliste einhängen**

In `frontend/src/pages/Orders.tsx` analog zu `OrderDocumentsModal` (ca. Zeile 264) einen State `editOrder` anlegen, das Modal rendern und in der Bestellzeile eine Aktion „Bearbeiten" ergänzen, die `setEditOrder(order)` aufruft.

- [ ] **Step 5: Gegen Gernots drei Fälle prüfen**

`cd frontend && npm run build` muss sauber sein. Dann im Dev-Server durchspielen:

1. **Lieferdatum korrigieren** (sein Punkt 2): Bestellung mit Lieferdatum 17.09. anlegen, **bestätigen**, dann öffnen und auf 18.09. ändern, speichern, Liste neu laden — Datum muss 18.09. zeigen. Die Prüfung an einem Entwurf durchzuführen ist wertlos: dort funktionierte es auch vorher schon, der 500er kam erst nach dem Bestätigen.
2. **Menge ändern und Position ergänzen** (Punkt 3): bei einer Position die Menge ändern, eine weitere Position hinzufügen — der Preis der neuen Position muss der Sonderpreis sein, die Gesamtsumme muss sich mitrechnen.
3. **Position entfernen und stornieren** (Punkt 3): eine Position löschen, danach die Bestellung mit Grund stornieren — Status muss STORNIERT sein und das Modal beim erneuten Öffnen gesperrt.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/domain/EditOrderModal.tsx frontend/src/services/api.ts frontend/src/pages/Orders.tsx
git commit -m "feat(bestellung): Bestellungen nachträglich bearbeiten und stornieren"
```

---

## Abnahme

Fertig ist der Plan, wenn alle vier zutreffen:

1. Gernots Bestellung von Ferdinand Bierbichler ergibt netto **278,76 €**, alle vier Positionen zeigen „Sonderpreis".
2. Das Lieferdatum einer **bestätigten** Bestellung lässt sich auf den Folgetag ändern (nicht nur bei einem Entwurf — genau dort lag der 500er).
3. Positionen lassen sich ergänzen, ändern und entfernen; eine Bestellung lässt sich mit Grund stornieren.
4. Die Gesamtsuite zeigt dieselben 15 Altlast-Fehler wie die Baseline, plus die neuen grünen Tests aus `test_gernot_260917.py`.

Deploy erst danach, und nach dem Deploy-Verify-Flow: build lokal → commit/push → Coolify-Deploy triggern → Status pollen bis `finished`.
