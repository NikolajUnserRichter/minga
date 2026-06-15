# Legal-Compliance Gap-Analyse — Belege

Stand: 2026-06-15 · Bezug: §§ 14, 14a UStG; HGB; GoBD.

Diese Analyse vergleicht die aktuellen Felder unserer generierten Belege
(Auftragsbestätigung, Lieferschein, Rechnung, Mahnung) mit den
**gesetzlich vorgeschriebenen Pflichtangaben** im deutschen B2B-Geschäft.

---

## 1. Rechnung (§ 14 Abs. 4 UStG)

| Pflichtangabe | Aktuell | Status | Hinweis |
|---|---|---|---|
| Vollständiger Name + Anschrift Aussteller | ❌ Nur "Minga Greens" Logo | **FEHLT** | Im PDF-Header ergänzen aus Settings/Firmendaten |
| Vollständiger Name + Anschrift Empfänger | ✅ Customer.name + billing_address Snapshot | OK | wenn Adresse hinterlegt |
| Steuernummer ODER USt-IdNr. des Ausstellers | ❌ | **FEHLT** | Aus Settings (z.B. `COMPANY_USTID`) ergänzen |
| Ausstellungsdatum (= Rechnungsdatum) | ✅ | OK | |
| Fortlaufende Rechnungsnummer (einmalig) | ✅ RE-YYYY-NNNNN | OK | |
| Menge und Art / Bezeichnung Leistung | ✅ description + quantity + unit | OK | |
| Leistungs-/Lieferdatum | ✅ delivery_date | OK | |
| Netto-Entgelt pro Steuersatz | ✅ tax_amount + subtotal | OK | |
| Steuersatz | ✅ tax_rate enum | OK | |
| Steuerbetrag | ✅ tax_amount | OK | |
| Hinweis bei Steuerfreiheit / Reverse-Charge | ⚠️ | Teilweise | bei TaxRate.STEUERFREI keinen Vermerk |
| Aufbewahrungspflicht-Hinweis bei Privatleistung | ❌ | optional | nur bei B2C-Bau o.ä. nötig |

**Kritische Lücken (Rechnung):**
1. **Aussteller-Adresse** komplett (Straße, PLZ, Ort, Land)
2. **USt-IdNr. oder Steuernummer** des Ausstellers
3. **Bankverbindung** (üblich, nicht zwingend)
4. Bei Skonto: **Skonto-Hinweis** ("3% Skonto bei Zahlung innerhalb 10 Tagen")

**Empfehlung Sofort-Umsetzung:**
- Neue Settings im Admin-Center: `COMPANY_NAME`, `COMPANY_ADDRESS_LINE1/2`,
  `COMPANY_USTID`, `COMPANY_STEUERNR`, `COMPANY_BANK_NAME`, `COMPANY_IBAN`,
  `COMPANY_BIC`
- PDF-Service liest diese und rendert Briefkopf-Block
- Skonto-Hinweis automatisch ergänzt wenn `customer.skonto_percent > 0`
- Reverse-Charge-Hinweis bei TaxRate.STEUERFREI für EU-Lieferungen

---

## 2. Auftragsbestätigung (AB)

Auftragsbestätigungen sind **rechtlich keine Pflicht**, aber Best-Practice
für Buchhaltung und Audit-Trail.

| Soll-Feld | Aktuell | Status |
|---|---|---|
| AB-Nummer | ✅ AB-YYYYMMDD-NNNN | OK |
| Datum | ✅ | OK |
| Kunde + Adresse | ✅ + Customer-Number | OK (nach letzter Wave) |
| Positionen + Preise | ✅ | OK |
| Lieferdatum | ✅ requested_delivery_date | OK |
| Zahlungsbedingungen | ❌ | **FEHLT** |
| AGB-Verweis | ⚠️ | optional |

**Empfehlung:** Zahlungsziel-Text aus Customer.payment_days unten anhängen.

---

## 3. Lieferschein

Pflichtangaben analog HGB für Warenverkehr:

| Soll-Feld | Aktuell | Status |
|---|---|---|
| Lieferschein-Nummer | ✅ LS-YYYYMMDD-NNNN | OK |
| Datum | ✅ | OK |
| Empfänger + Anschrift | ✅ delivery_address | OK wenn gepflegt |
| Liefer-/Versanddatum | ✅ | OK |
| Artikelbezeichnung + Menge | ✅ | OK |
| Charge / Batch-Number (LMHV) | ⚠️ batch_number an Position | OK wenn aus Harvest übernommen |
| Unterschriftsfeld Empfänger | ✅ | OK |
| Hinweis Eigentumsvorbehalt | ❌ | Empfehlung |

**Lebensmittelrecht (LMHV)** zusätzlich:
- ✅ Charge nachverfolgbar (Harvest → SeedBatch → Seed)
- ⚠️ MHD/Verbrauchsdatum: nicht automatisch auf LS gedruckt (aktuell nur in
  packing_list_items optional)
- ⚠️ Bio-Zertifikat-Nummer: in Lieferanten gepflegt, aber nicht auf LS

---

## 4. Verpackungsliste (Packing List)

Nicht gesetzlich vorgeschrieben, aber Best-Practice für Versand:

| Soll-Feld | Aktuell | Status |
|---|---|---|
| Pos. + Produkt + Menge + Einheit | ✅ | OK |
| Charge | ✅ batch_number | OK |
| Pfand-Container (KISTE_12 etc.) | ✅ separater Block | OK |
| Gesamtgewicht | ✅ total_weight_g | OK |
| Anzahl Packstücke | ✅ total_packages | OK |
| Versand-Datum / Spediteur | ❌ | optional |

---

## 5. Mahnungen / Zahlungserinnerung

Neu im System: 3-Stufen-Modell

| Soll-Feld | Aktuell | Status |
|---|---|---|
| Bezug auf Original-Rechnung | ✅ | OK |
| Mahnstufe / Bezeichnung | ✅ "Zahlungserinnerung" / "1./2. Mahnung" | OK |
| Tage überfällig | ✅ | OK |
| Offener Betrag | ✅ | OK |
| Mahngebühr (ab Stufe 2) | ✅ als Query-Param | OK, sollte ggf. aus Settings/Customer kommen |
| Frist zur Zahlung | ✅ Text 7 Tage | OK |
| Bankverbindung | ❌ | **FEHLT** |
| Verzugszinsen-Hinweis (§ 288 BGB) | ❌ | Empfehlung Stufe 3 |

---

## Empfohlene Sofort-Maßnahmen (priorisiert)

1. **Firmendaten in Settings + auf alle PDFs** (Aussteller-Block, IBAN, USt-IdNr)
2. **Skonto-Hinweis** auf Rechnung wenn customer.skonto_percent > 0
3. **Bankverbindung** auf Rechnung + Mahnung
4. **Reverse-Charge-Vermerk** bei TaxRate.STEUERFREI + EU-Empfänger
5. **Eigentumsvorbehalt-Klausel** im Footer von LS/Rechnung
6. **MHD-Druck auf Lieferschein** bei Lebensmittel-Positionen

Diese Punkte sind backlog für eine Folge-Iteration (geschätzt 4-6h);
strukturell sind alle Datenquellen bereits vorhanden.
