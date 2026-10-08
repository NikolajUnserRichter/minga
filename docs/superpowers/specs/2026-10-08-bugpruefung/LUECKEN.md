**Ergänzungen zu A1–A4 (nur gelesen, keine Datei geändert, kein Zugriff auf Produktion)**

**1. Doppelte Abrechnung (höchstes Risiko, vor dem nächsten Sammelrechnungslauf klären)**
- backend/app/services/invoice_service.py:174-213: `create_invoice_from_order` hat keine Sperre gegen eine zweite Rechnung zur selben Bestellung. Sie hängt die Lieferscheine nicht an die Rechnung (`DeliveryNote.invoice_id` bleibt leer) und setzt die Bestellung nicht auf FAKTURIERT. FAKTURIERT setzt im Code nur der manuelle Statuswechsel.
- backend/app/api/v1/invoices.py:528-534: Der Sammellauf nimmt jeden Lieferschein mit `invoice_id IS NULL`, auch solche auf ENTWURF. Die Lieferscheine zu RE-00002/3/4 (über from-order entstanden) würden deshalb im nächsten Lauf ein zweites Mal berechnet. Für RE-00001 und RE-00005 ist offen, auf welchem Weg sie entstanden sind. In Produktion lesend prüfen: `delivery_notes.invoice_id` der zugehörigen Bestellungen.
- backend/app/api/v1/documents.py:186-215: Eine Bestellung kann beliebig viele Lieferscheine bekommen (Knopf in OrderDocumentsModal.tsx:215). backend/app/api/v1/invoices.py:561-569 zählt `order.lines` für jeden Lieferschein neu, also wird doppelt berechnet. Wenn der A1-Fix den Lieferschein künftig automatisch anlegt oder quittiert, verschärft sich das.
- frontend/src/components/domain/OrderDocumentsModal.tsx:45 und :288-295: Die Rechnungssuche je Bestellung sieht nur die 20 neuesten Rechnungen. Der Knopf "Rechnung aus Bestellung" ist immer sichtbar. Ab Rechnung 21 zeigt das Modal bei älteren Bestellungen "keine Rechnung" an, und ein Klick erzeugt eine doppelte Rechnung.

**2. Weitere Stellen mit festem Steuersatz (A3)**
- backend/app/services/invoice_service.py:110-163 und :335-345: Den Fix "Produktsatz gewinnt" nicht in `add_line` einbauen. Der Storno ruft `add_line` mit `product_id` auf. Die Pfandzeilen der Stornorechnung zu RE-00002/4 bekämen dann 19 %, das Original hat 7 %, und der Storno ergibt nicht mehr null. Der Fix gehört in die Anlage der Bestellpositionen und in `create_invoice_from_order`.
- backend/app/api/v1/sales.py:968-976: Bei einer Position nur mit Variante (ohne `product_id`) ist `product` leer. Der Produktsatz muss dann aus `variant.parent_product` kommen.
- backend/app/api/v1/products.py:140-142: PATCH auf `category=PFAND` oder `is_deposit=true` setzt den Satz nicht auf 19 %. Beim Anlegen (Z. 86-95) passiert das, beim Ändern nicht.
- backend/app/api/v1/imports.py:423: Ein Produktimport ohne Spalte `category` setzt bestehende Pfandartikel auf MICROGREEN. Das ist ein eigener Fehler, zusätzlich zum bekannten Steuersatz-Fehler.
- backend/app/services/invoice_service.py:197-207: from-order übergibt `discount_percent` nicht, der Positionsrabatt fehlt also auch hier, nicht nur in der Sammelrechnung. Zusätzlich wird als Leistungsdatum `requested_delivery_date` genommen statt `actual_delivery_date` (Z. 181-185). Die Neuausstellung von RE-00002/4 läuft über genau diesen Weg.

**3. Rohe Enum-Werte, die die Verifizierer nicht genannt haben (A1-Muster)**
- frontend/src/components/domain/OrderDocumentsModal.tsx:171, :229, :305: Status von Auftragsbestätigung, Lieferschein und Rechnung erscheinen roh (ENTWURF, VERSENDET, OFFEN, UEBERFAELLIG, TEILBEZAHLT).
- frontend/src/pages/Tagesplan.tsx:102: Aussaat-Status VORGESCHLAGEN oder GENEHMIGT kommt roh aus backend/app/api/v1/production.py:448.
- frontend/src/pages/Forecasting.tsx:371: `suggestion.status` roh, obwohl `SuggestionStatusBadge` existiert (Badge.tsx:78-93).
- frontend/src/pages/Production.tsx:603: `batch.status` roh, obwohl `GrowBatchStatusBadge` existiert.
- frontend/src/pages/Invoices.tsx:128: lexoffice-Status roh (open, paid, voided).
- backend/app/api/v1/forecasting.py:935 und :1021: Fehlertexte mit rohem Enum-Wert.

**4. Statuswege, die beim A1-Fix mitgezogen werden müssen**
- backend/app/api/v1/sales.py:1544-1585 (`POST /orders/bulk-status`): keine Prüfung der Übergänge, kein Bestandsabzug, kein `actual_delivery_date`. Das Frontend nutzt den Endpunkt nicht, er ist aber per API erreichbar. Entweder an dieselbe Übergangsregel binden oder entfernen.
- backend/app/api/v1/sales.py:1201: IN_PRODUKTION → STORNIERT ist nicht erlaubt. Wird IN_PRODUKTION zu "Gepackt", lässt sich eine gepackte Bestellung nicht mehr stornieren (EditOrderModal.tsx:151 spiegelt das).
- backend/app/api/v1/documents.py:294 und :299, dazu OrderDocumentsModal.tsx:125: Wenn jemand die Lieferscheine der fünf Bestellungen jetzt nachträglich quittiert, ist `actual_delivery_date` = heute, weil die Oberfläche nur `signed_by` mitschickt. Das echte Lieferdatum 07./08.10. muss beim Nachtragen explizit gesetzt werden.

**5. A4: Demo-Umgebung**
- backend/app/services/demo_reset_service.py:68-71: Der Reset kopiert den Golden-Seed zurück, ohne `_auto_migrate` laufen zu lassen. `registry.get_engine` (tenancy.py:76) migriert ebenfalls nicht. Eine neue Spalte `orders.packed_at` fehlt also nach dem Reset um 03:30, und die Demo wirft Fehler bis zum nächsten Neustart. Nach dem Reset migrieren oder den Seed neu ziehen.

**6. Tests, die das heutige Verhalten festschreiben**
- backend/tests/test_gernot_bugfixes.py:140 erwartet `order_ref["status"] == "Entwurf"`. Der Test wird rot, wenn production.py:737 auf rohe Werte mit Übersetzung im Frontend umgestellt wird.
- backend/tests/test_pfand_rabatt.py:39-47 und backend/tests/test_gernot_260821.py:705-708: Ein bewusst auf 7 % gesetzter Pfandartikel muss 7 % behalten. Der Fix darf also nicht bei jedem `is_deposit` 19 % erzwingen, er muss `product.tax_rate` übernehmen.
- backend/tests/test_pfand_rabatt.py:49-75: Bei manuellen Rechnungszeilen gilt der Satz vom Client.
- backend/tests/test_gernot_260821.py:486-504: Positionen ohne `product_id` mit ausdrücklichem Satz. Der Rückfall ohne Produkt muss den Client-Wert behalten.
- backend/tests/test_gernot_260817.py:187-206: Zählt verpacken und ausliefern. Eine Same-Day-Bestellung muss weiter in beiden Listen stehen.
- Kein Test erwartet BESTAETIGT → GELIEFERT als ungültig, keiner erwartet `customer_name = null`, keiner setzt den 7-%-Rückfall voraus. Die Frontend-E2E-Tests prüfen keine Status-Bezeichnungen.

**7. Korrekturweg für RE-2026-00002 und RE-2026-00004**
- Vorhanden ist nur der Vollstorno: backend/app/api/v1/invoices.py:278-302, in der Oberfläche Invoices.tsx:395-396 für OFFEN, TEILBEZAHLT, UEBERFAELLIG und BEZAHLT. Danach eine neue Rechnung über from-order. Dass die Stornorechnung die 7 % übernimmt, ist korrekt.
- Eine Teilkorrektur oder Differenz-Gutschrift ist nicht möglich, weil manuelle Zeilen positiv sein müssen (backend/app/schemas/invoice.py:131). Einen Stornogrund "Steuersatz" gibt es nicht, nur SONSTIGES (schemas/invoice.py:251-254, Invoices.tsx:555-559).
- Die Stornorechnung bekommt Status OFFEN und ein Fälligkeitsdatum. Der geplante Job (scheduler_service.py:98-99) markiert sie dann als überfällig (backend/app/tasks/invoice_tasks.py:40-45; ebenso invoice_service.py:374-380) und verschickt eine Mahnung über einen negativen Betrag (invoice_tasks.py:105-150). Ausgleichen lässt sie sich nicht, weil Zahlungen größer null sein müssen (schemas/invoice.py:82). Außerdem zählt sie im Dashboard dauerhaft als offen (Dashboard.tsx:82, :336).
- Falls RE-00002/4 schon bezahlt sind: Der Storno lässt `paid_amount` an der alten Rechnung stehen. Es gibt keine Verrechnung mit der neuen Rechnung, die neue Rechnung läuft also ins Mahnwesen. Die Zahlung muss man dort von Hand erfassen.
- Bestellpositionen korrigieren geht per `PATCH /sales/orders/{id}/lines/{line_id}` mit `{"tax_rate":"STANDARD"}`, und zwar in jedem Status (backend/app/api/v1/sales.py:1393-1425). Das Audit-Log hält aber nur Menge und Preis fest (Z. 1415-1418, 1437-1440), die Satzänderung wird nicht protokolliert. In der Oberfläche fehlt das Feld (api.ts:405-409).
- Rechnungszeilen auf keinen Fall direkt in der DB ändern: Das PDF wird bei jedem Abruf aus der DB erzeugt, ein Archiv gibt es nicht (invoices.py:466-500). Eine Änderung schriebe das bereits versendete Dokument rückwirkend um (GoBD).
- DATEV: Die Stornorechnung geht mit negativem Umsatz in den Export (backend/app/services/datev_service.py:81, :118). DATEV erwartet positive Beträge mit Soll/Haben-Kennzeichen.
- lexoffice (nur relevant, falls dort übertragen wurde): Es gibt keinen Weg für Gutschriften. Ein Storno würde über `/v1/invoices` mit negativen Mengen geschickt (lexoffice_service.py:35-47, 99-113), und der Status "voided" wird nicht zurückgeholt (Z. 151-166).