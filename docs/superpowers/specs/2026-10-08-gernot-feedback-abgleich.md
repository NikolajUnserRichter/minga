# Gernot-Feedback 08.10.2026 — Abgleich mit dem Code und Umsetzungsplan

Quelle: Feedback-Dokument zu den Mails von Gernot Kleinberger vom 07./08.10.2026 (Kunde live seit 08.10.2026).
Stand der Analyse: `main` @ `c4a1832`, Produktionsdaten Mandant `minga` vom 08.10.2026.

Jede Aussage ist am Code oder an Produktionsdaten belegt. Die Bug-Diagnosen wurden von unabhängigen Prüfern angegriffen; zwei ursprüngliche Diagnosen (A3-Mechanismus, A4-Fix) sind dabei widerlegt und hier korrigiert.

---

## Sofortmaßnahmen — vor jedem Code

1. **Kein DATEV-Export auslösen**, bis Paket 1 umgesetzt und mit dem Steuerberater abgestimmt ist. Der Export bucht falsch (B9). Bisher ist keine Rechnung exportiert.
2. **RE-2026-00002 und RE-2026-00004 nicht über das System stornieren.** Der Storno mehrzeiliger Rechnungen summiert nur die erste Zeile (nachgestellt: −10,70 € statt −17,84 €).
3. **Keinen Sammelrechnungslauf starten**, bis Paket 1 live ist. Rechnungen „aus Bestellung" verknüpfen ihre Lieferscheine nicht; der Sammellauf würde die Bestellungen hinter RE-00002/3/4 ein zweites Mal berechnen (Lückenprüfung 08.10., `invoices.py` ~528–534, `invoice_service.py` ~174–213).
4. **Gernot informieren** — Pfand-Steuersatz, betroffene Rechnungen, DATEV-Stopp, Sammellauf-Stopp.

---

## Abweichungen vom Feedback-Dokument

| Annahme im Dokument | Tatsächlich |
|---|---|
| PostgreSQL | SQLite pro Mandant; Schemaänderungen über `tenancy._auto_migrate` (nur `ADD COLUMN`) |
| Status `GEPACKT`, `AUSGELIEFERT` | Existieren nicht. Vorhanden: `ENTWURF, BESTAETIGT, IN_PRODUKTION, GELIEFERT, FAKTURIERT, STORNIERT` |
| A1: Status wird nicht gespeichert | Wird gespeichert. Ursache: Sammelaktion mit Erfolgsmeldung ohne Wirkung |
| A3: Steuersatz am Produkt falsch | Produktstamm korrekt (19 %). Bestellformular und Schema setzen fest 7 % |
| B1: Bundle-Stückliste fehlt | Existiert und wird im Packplan aufgelöst. Es fehlen die Rezepturen (26 von 30 Mixes) |
| B4: Entwurf-Bearbeitung fehlt | Backend kann es; Summe wird beim Löschen nicht neu berechnet, Knopf schwer erreichbar |
| B6: Mehrfach-Liefertage, Einheit Kiste fehlen | Beides im Formular vorhanden; Fehler in der Fälligkeitsprüfung macht Mehrfachauswahl wirkungslos |
| B8: Profilfelder ergänzen | Benutzerverwaltung ist eine Attrappe (LocalStorage, sieben erfundene Nutzer, kein Backend) |
| B9 „siehe A4" | Gemeint ist A3 |

---

## Bugs

### A1 — „Ausgeliefert" wird nicht angezeigt
**Ursache:** Die Sammelaktion „Geliefert" (`Orders.tsx` ~142–155) filtert `BESTAETIGT` still heraus und meldet trotzdem Erfolg; `handleBulkReady` ebenso. Kein Übergang `BESTAETIGT → GELIEFERT` (`sales.py` ~1200). Tagesplan-Karte „Ausliefern" ohne Knopf, zeigt rohen Enum-Wert (`production.py:537`, `:737`). Zwei inkonsistente Wege nach `GELIEFERT`: Status-Endpunkt (quittiert keinen Lieferschein, kein `actual_delivery_date`) und Lieferschein-Quittieren (umgeht Übergangsregeln, kein Audit-Log).
**Fix:** Knopf „Ausgeliefert" im Tagesplan; `BESTAETIGT → GELIEFERT` erlauben; Sammelaktionen ehrlich; beide Wege vereinheitlichen; Bezeichnungen statt Enum-Werten; Tagesplan nach Statuswechsel neu laden. — **S–M**

### A2 — Spalte „Kunde" leer
**Ursache:** Schema und Frontend kennen `customer_name`, das Modell nicht; nichts befüllt es. Betrifft Liste, Detail, „Überfällig", ebenso `customer_number`.
**Fix:** Properties am Modell + `joinedload`. Zusätzlich: Rechnungsliste kürzt still auf 20. — **S**

### A3 — Pfand mit 7 % statt 19 %
**Ursache:** `CreateOrderModal.tsx:177` sendet fest `REDUZIERT`; `schemas/order.py:35` Default `REDUZIERT`. Fallback in `sales.py` greift nie. `create_invoice_from_order` nimmt den Satz der Bestellposition statt des Produkts.
**Betroffen:** RE-00002 (Ökoring, versendet), RE-00003 (Ökoring, Entwurf), RE-00004 (Großer Kern, versendet). Keine an DATEV.
**Fix:** Produktsatz serverseitig verbindlich; Frontend ohne festen Satz; Sammelrechnung übergibt `product_id`; **PDF weist Steuer je Satz aus (§ 14 Abs. 4 Nr. 8 UStG, fehlt heute)**; Rundung angleichen; **Storno reparieren**, dann RE-00002/4 stornieren und neu ausstellen; Datenkorrektur offener Bestellpositionen. Nebenbefunde: Produktimport setzt Pfand auf 7 % zurück; Shopify pauschal 19 %. — **M**

### A4 — Sortenbedarf enthält gepackte Bestellungen
**Ursache:** Keine Aktion „gepackt"; beim Packen stehen Bestellungen auf `BESTAETIGT`. **Ursprünglicher Fix (nur umbenennen) widerlegt.**
**Fix:** Knopf „Gepackt" in der Verpacken-Karte setzt `IN_PRODUKTION`, das in der Oberfläche „Gepackt" heißt (zugestimmt). Gepackte raus aus Sortenbedarf und Verpacken, bleiben in Ausliefern. Filter in Python — `production.py:523` speist beide Karten. — **S–M**

### A5 — Abo-Bestellungen ohne Produkt (neu)
**Ursache:** `subscription_tasks.py` sucht nur über `seed_id`; alle Abos haben `product_id`. Bei `seed_id = None` → `WHERE products.seed_id IS NULL` → Preis und Satz eines beliebigen Produkts ohne Saatgut.
**Belegt:** LfA Förderbank Bayern, vier Entwürfe seit 14.09., „Abo-Lieferung: Unknown", Preis 2,00 €.
**Fix:** `product_id` + Variante übernehmen; Preis und Satz vom Produkt; Rückfüllung der vier Entwürfe über `Order.notes`; Fälligkeitsprüfung für mehrere Liefertage reparieren; Abo-Rechnungstask (nicht eingeplant, fest 7 %, 0,08 €) entfernen. — **S–M**

### A6 — Importierte Zukunftsbestellungen stehen auf „Geliefert" (neu, Nachtrag 08.10. mittags)
**Ursache:** `imports.py` `_import_order_history` (~547–562) setzt bei leerer Status-Spalte `GELIEFERT` und `actual_delivery_date = lieferdatum` — gebaut für Historie, auch bei Lieferdaten in der Zukunft. Knopf heißt „Historie importieren", Vorlage zeigt nur `GELIEFERT`. Folge: Bestellung fehlt im Tagesplan und Packplan, Positionen lassen sich nicht ergänzen (`EditOrderModal.tsx` ~151, ~316–350), Storno unmöglich.
**Belegt (Produktion, lesend):** Sieben Importläufe am 08.10., 49 Bestellungen auf `GELIEFERT`; 46 rückdatiert (16.09.–07.10.), eine vom 08.10. (Klara Düran), zwei in der Zukunft: BE-20261008-0004 (Großer Kern, 10.10.), BE-20261011-0001 (Fruchthof Nagel, 12.10.). Keine Lagerbewegungen, keine Rechnungen.
**Erledigt 08.10. (freigegeben):** WAL-sicheres Backup `/root/backups/minga-vor-importfix-20261008-104517.db`; beide Zukunftsbestellungen auf `BESTAETIGT`, `actual_delivery_date` geleert, je ein Audit-Eintrag „Import-Korrektur". Geprüft: erscheinen im Tagesplan 09./10.10. bzw. 11./12.10.
**Fix (Hotfix, freigegeben):** Leere Status-Spalte → Lieferdatum vor heute (Europe/Berlin) = `GELIEFERT`, sonst `BESTAETIGT`; `GELIEFERT` mit Zukunftsdatum wird abgelehnt; Knopf „Bestellungen importieren"; Vorlage zeigt beide Fälle. Commit `efcea00` (Worker GPT-5.6 Sol, geprüft), **live seit 08.10.2026 13:56** (Backups `*-vor-deploy-efcea00-20261008-115012.db`; Live-Prüfung: neuer Code im Container, Bundle ohne „Historie importieren", `/health` 200). — **S**
**Offen:** Die 46 rückdatierten Bestellungen haben keinen Lieferschein — der Sammellauf erfasst sie nicht. Klären, ob sie noch abgerechnet werden müssen.

---

## Features

| | Ist | Fehlt | Aufwand |
|---|---|---|---|
| **B1** | Stückliste + Auflösung im Packplan | Rezepturen für 26 Mixes (Gernot); A5; variable Bundles ohne Auswahl fallen heraus | S + Daten |
| **B2** | Lieferschein-/Rechnungs-/Zahlungsstatus; `OrderDocumentsModal` teilweise | `sent_at` unzuverlässig (Finalisieren setzt es ohne Mail); kein Versandlog; Modal lädt nur 20 neueste Rechnungen | M |
| **B3** | SMTP-Versand, ein Empfänger per `window.prompt` | Belegversand-Kennzeichen, Popup, mehrere Empfänger, Versandlog, Lieferschein-Versand | M |
| **B4** | `ENTWURF` + Finalisieren, Positionen per API löschbar | Summe nach Löschen; Knopf erreichbar; Sammelrechnung als Entwurf; Nummer erst beim Finalisieren (NOT NULL → Platzhalter); `pfand_via_clearing` | M–L |
| **B5** | Vorschau + Festschreiben | `invoice_mode`; Dialog zeigt Ausgeschlossene; **leere Kundenliste = alle Kunden** | M |
| **B6** | Ein Produkt je Abo | `subscription_items`, Generator, Migration | L |
| **B7** | `{Nr}.pdf` | Frontend überschreibt selbst; Backend + Frontend; auch AB und Packliste | S |
| **B8** | Keycloak-Anlage nur intern | **Oberfläche ist Attrappe**; echte Endpunkte. **Sicherheitskritisch:** ein Realm für alle Mandanten, Trennung nur über `tenant_slug` | L |
| **B9** | CSV, Erlöse je Satz | **Bucht falsch:** Sollzeile falsche Richtung, Kopfkonto 8300 überschreibt Konten je Satz, Spalten verschoben, Storno negativ, Stornierte exportiert, kein Wiederholungsexport. Kein EXTF-Kopf, keine PDF-Anhänge | L (Korrektur M) |

---

## Nachtrag 08.10. nachmittags — Entscheidungen zu Gernots Antworten

Grundlage: geprüfte Analysen in `2026-10-08-nachtrag/` (T1 Import, T2 SEPA, T3 Pfand, T4 Monatsrechnung, T5 Rechte und Versand). Entscheidungen sind Empfehlungen, die gelten, solange Gernot nicht widerspricht.

- **Pfand (B4, T3):** Variante C — Kundenfeld `pfand_abrechnung` mit drei Werten: `JE_LIEFERUNG` (Pfand auf jeder Rechnung, z. B. Knuspr), `KEINE` (IFCO-Clearing, z. B. Ökoring), später `MONATLICH` (Leergutkonto: ausgegeben minus Retouren, einmal im Monat abgerechnet). Paket 1 baut das Feld mit `JE_LIEFERUNG`/`KEINE` (statt eines Ja/Nein-Feldes `pfand_via_clearing`), Paket 3 ergänzt `MONATLICH` mit Retouren-Erfassung (Dialog plus Einstieg für die Halle). Saldierung und Steuerentstehung muss der Steuerberater bestätigen.
- **Monatsrechnung (B5, T4):** Am 1. des Folgemonats um 06:30 entstehen Monats-Sammelrechnungen als **Entwurf**; nur der Admin gibt frei, nichts geht automatisch raus. Letzter Schritt von Paket 3 (braucht Nummer beim Finalisieren und Doppelabrechnungssperre). Sofort-Fixes (FAKTURIERT-Bestellungen nicht erneut abrechnen, Rabatt, Lieferschein-Doppelzählung) gehören zur Doppelabrechnungssperre in Paket 1.
- **Versand (B3, T5):** Eine Mail, alle Adressen im „An"-Feld. Empfängerlisten je Kunde und Belegart, Versandprotokoll, Lieferschein-Versand neu. Paket 3.
- **Mitarbeiter (B8, T5):** `production_staff` bleibt; die Rolle darf per API schon Bestellungen, AB und Lieferscheine anlegen, AB versenden, Lieferscheine quittieren; Rechnungen sind gesperrt. **Vor Freigabe an Gernots Team Pflicht:** Halle darf Produkte lesen (heute zeigt das Bestellformular für die Rolle Saatgut statt Produkte, Speichern endet mit 404), ein Lieferschein je Bestellung (sonst doppelte Abrechnung, gemessen 15,00 € statt 7,50 €), Rechnungsteil im Belege-Dialog für die Halle ausblenden. Logins sofort per `create_tenant_user`, sobald Gernot Namen und E-Mails nennt.
- **SEPA (B10, T2):** Eigene Tabelle `sepa_mandates` (Mandatsreferenz, IBAN mit Modulo-97-Prüfung, BIC/Bank, Mandatsdatum, Art CORE/B2B), Zahlungsart am Kunden, Gläubiger-ID **einmal in den Firmeneinstellungen** (gehört MingaGreens, nicht dem Kunden). Hinweis mit maskierter IBAN in Mail und PDF, als Snapshot beim Festschreiben (gemeinsame Funktion für alle Wege nach OFFEN). Lastschriftrechnungen laufen nicht ins Mahnwesen. Nur Admin und Buchhaltung sehen Bankdaten. Kein SEPA-XML in diesem Schritt. Paket 3.
- **Import (A6-Rest, T1):** Unvollständige Bestellungen bei fehlerhaften Zeilen verhindern, Bestelldatum/Status/Einheit prüfen, Adresse und Audit-Eintrag setzen. Paket 2.

## Umsetzungsstand und Merge-Folgepunkte (08.10. abends)

- **Paket 1 live seit 08.10.2026 20:57** (main `4cb9b92`; Worker GPT-6 Astra für 29 Tasks, GPT-5.6 Sol für Demo-Reset-Migration und Abnahme-Fixes, Manager für Zahlungsart-Optionen). Backups `*-vor-deploy-4cb9b92-20261008-185542.db`. Live geprüft: `/health` 200, openapi mit `pfand_abrechnung`/`erneut_exportieren`/`FALSCHER_STEUERSATZ`, Bundle mit „IFCO-Clearing", Marker in minga/demo/demo.seed, Korrektur nur BE-20261007-0003 (Pfand 19 %, 28,57 €), Rechnungen unverändert, L2/L3 für minga ohne Befund. Manager-Entscheid unterwegs: Ein nie ausgestellter Entwurf bekommt keine Stornorechnung; S1-Test finalisiert vorher. **Runbook Teil 3 (Korrektur RE-00002/3/4) wartet auf Gernots Antworten und Freigabe.**
- **B8 Benutzerverwaltung** läuft (Worker GPT-6 Astra, Worktree `minga-b8`, Plan `2026-10-08-b8-benutzerverwaltung.md`, 12 Tasks + 6b). Manager-Entscheidungen: Audit dauerhaft in Tabelle `benutzer_audit`; Demo zeigt nur `DEMO_USERS` und blendet Schreibknöpfe aus; fremde E-Mail im Konflikt-Audit nur als SHA-256; Master-Admin-Schalter entfällt; `view-realm` für den Service-Account freigegeben. **Deploy erst nach dem B8-Kern aus Paket 3**; Keycloak-Service-Account ist ein Betriebsschritt mit Freigabe.
- **Abnahme Paket 2 (Tasks 1–22, 08.10.):** Gernots Fälle 9/9, Oberfläche 16/17 (Doppelklick „Gepackt" ohne Abstand: zweiter Request mit Fehler-Toast, Daten korrekt), Review 12/12. Nacharbeiten im Merge-Lauf: Storno-Sperre bei aktiver Rechnung, Packtag nach Berliner Tag, einheitliches Leistungsdatum, Bestellliste bis 100 neueste, Knöpfe während der Anfrage gesperrt, Verpackungsplan-Datum Berlin. Hinweis im Plan „Gastrotray = variables Bundle" stimmt für Minga nicht (MG-14001 ist kein variables Bundle) — nicht an Gernot weitergeben.
- **Paket 2 live seit 08.10.2026 22:28** (main `6e30723`, inkl. Import-Härtung P5, Merge mit Paket 1, Task 24, Nacharbeiten a–f). Backups `*-vor-deploy-6e30723-20261008-202705.db`. Live geprüft: `/health` 200, openapi mit `BulkStatusResult`, Bundle mit „Ausgeliefert"/„Bereits gepackt", `order_status_service` im Container, Startlog ohne Fehler. Delta-Abnahme auf frischer Prod-Kopie: Echtdaten 11/12, Review 10/10.
- **Paket 2.1 live seit 08.10.2026 23:54** (main `5c069b1`, Worker GPT-6 Astra, 5 Commits; Backups `*-vor-deploy-5c069b1-20261008-215237.db`; Echtdaten-Prüfung: RE-00003 finalisieren/versenden → 409, Positionen berechneter Bestellung → 409, stornierte Bestellung berechnen → 409; Migration ändert keine Daten). Behobene Lücken: (1) Finalisieren/Versenden/Status-PATCH eines Entwurfs, wenn zur Bestellung schon eine aktive Rechnung besteht — **akut: RE-00003 ließe sich neben RE-00002 finalisieren (Ökoring doppelt)**; (2) Bestellpositionen nach Berechnung änderbar, Differenz wird nie berechnet; (3) stornierte Bestellung lässt sich noch berechnen; (4) Löschen einer Entwurfsbestellung mit Rechnung; (5) Sammelrechnungs-PDF-Anlage nutzt die neue Leistungsdatum-Regel nicht. Offen (niedrig): Packtag wird beim Ändern des Liefertags nicht neu bestimmt.
- **Paket 2** (Arbeitsstand vor Deploy) (Worker GPT-6 Astra, Worktree `minga-paket2`, Plan `2026-10-08-paket2-tagesplan-status.md`, Tasks 1–23; Task 24 nach Merge von Paket 1). Entschieden: E1 Plan-Default (Dashboard „offen" = bestätigt + gepackt), E3 `refetchOnWindowFocus: 'always'` für Tages- und Packplan, E5 Paket-1-Test bestätigt die Bestellung vor dem Quittieren.
- **Beim Merge nachziehen:** (1) Leistungsdatum überall `note.actual_delivery_date or order.actual_delivery_date or order.requested_delivery_date` (Sammelrechnung und Rechnung aus Bestellung); (2) ein künftiges automatisches `FAKTURIERT` nur über `order_status_service.setze_status`; (3) Paket-1-Runbook R3: Bestellung vor dem Quittieren bestätigen, Liefertag aus dem Feld, Lieferdatum wird bei bereits gelieferten Bestellungen nur nachgetragen; (4) Rechnungsliste Platzhalter `–` angleichen (E4); (5) Konflikte in `OrderDocumentsModal.tsx` laut Paket-2-Plan, Abschnitt „Überschneidungen", Punkt 6 (Probe-Merge 08.10.: nur zwei Import-Zeilen, 743 Tests ohne neuen Fehler, tsc sauber); (6) **Bestellung mit aktiver Rechnung nicht stornierbar** — Prüfung in `order_status_service.setze_status` für `STORNIERT` (Abnahme Paket 1: so entstand RE-00005 an einer stornierten Bestellung).
- **Abnahme Paket 1 (08.10.):** Gernots Fälle 16/16, Oberfläche M1–M5 bis auf „Zahlung erfassen" (422, besteht schon auf main), Rechte und Demo-Logins geprüft. **Blocker gefunden und in Arbeit:** PATCH auf Produktgruppe, Wachstumsplan, Preisliste und Preislistenposition lief in `NameError` (Patch aus Task 4 an fünf statt einer Stelle). Fix-Runde: dieser Blocker plus „Zahlung erfassen". Offen für Paket 3: `production_planner`/`production_staff` können `pfand_abrechnung` setzen (Feldschutz); Stornorechnung im Belege-Dialog anzeigen; Zeile „darin enthaltenes Pfand" im Storno-PDF.
- **Datenbefund (Paket-1-Abnahme, schon vor Paket 1):** RE-2026-00005 (Klara Düran, 360,37 €, versendet 08.10. 06:18) hängt an BE-20261008-0001, die Gernot um 07:26 als „Doppelter Import" storniert hat. Geliefert wurde BE-20261007-0008 mit identischen Positionen. Risiko: Diese Bestellung kann einzeln ein zweites Mal berechnet werden (die Sperre greift je `order_id`). Nach dem Deploy als Datenkorrektur vorlegen (BE-20261007-0008 als berechnet kennzeichnen bzw. Rechnung umhängen) und Gernot bestätigen lassen. Kein DATEV-Export, kein Mahnlauf davor.
- **Import-Härtung (A6-Rest)** wird als Abschnitt P5 geplant und nach Task 23 an Paket 2 angehängt; zusätzlich `IN_PRODUKTION` mit Lieferdatum ab heute auf `BESTAETIGT` abbilden oder ablehnen und `imports._today_berlin` auf `order_status_service.heute_berlin` umstellen.

## Paketierung

**Paket 1 — Steuer und Rechnung (akut):** A3 vollständig · PDF je Satz · Storno · DATEV-Korrektur · B4-Kern · Korrektur RE-00002/3/4 · Rechnungsliste ohne 20er-Kürzung · **Doppelabrechnung sperren** · **Stornobeleg ohne Mahnung** (beides aus der Lückenprüfung vom 08.10.: Stornorechnung steht heute auf OFFEN, läuft ins Mahnwesen mit negativem Betrag)
· `pfand_abrechnung` statt `pfand_via_clearing` · ein Lieferschein je Bestellung
**Paket 2 — Tagesplan und Status:** A1 · A4 · A2 · A5 · Import-Härtung (A6-Rest)
**Paket 3 — Belegfluss:** B2 · B3 · B7 · Nummer beim Finalisieren · B8-Kern (Halle liest Produkte, Rechnungen ausgeblendet) · B10 SEPA · Leergutkonto `MONATLICH` · zuletzt B5 Monatsentwürfe
**Paket 4 — Größeres:** B6 · B8-Benutzerverwaltung · B9-Rest (EXTF nach Steuerberater) · B1-Rezepturen

---

## Offene Entscheidungen

**Von dir — entschieden am 08.10.2026 („passt für mich"):**
1. ✅ Paketreihenfolge wie oben: Paket 1 zuerst.
2. ✅ Rechnungsnummer erst beim Finalisieren über einen Platzhalter `ENTWURF-…` für Entwürfe (Umsetzung in Paket 3). Bestehende Entwürfe behalten ihre RE-Nummer.
3. ✅ B8: Mitarbeiter-Login = Rolle `production_staff` (im Plan so vorgeschlagen, mit dem Plan freigegeben). → Wird nach Gernots Antwort vom 08.10. (Mitarbeiter legen Bestellungen, AB und Lieferscheine an und versenden sie) überprüft.
4. ✅ 08.10. mittags („okay fix all"): alle Pakete umsetzen, A6-Import-Fix als Hotfix vorab.
6. ✅ 08.10. (Manager, Plan Paket 1 N1/N2): „Sammelrechnung als Entwurf" kommt in Paket 3 zusammen mit „Nummer erst beim Finalisieren"; Paket 1 lässt `batch_run_commit` auf `OFFEN`. Mit `MONATLICH` (Paket 3) wird `ist_clearing_pfand` erweitert und die Rechnungsliste zusätzlich nach `created_at desc` sortiert. Feldschutz für abrechnungsrelevante Kundenfelder (`pfand_abrechnung`, später `invoice_mode`, Bankdaten) gegen `production_staff` kommt mit dem B8-Kern in Paket 3; **Mitarbeiter-Logins erst danach anlegen.**
5. ✅ 08.10. Deploy-Freigabe für diese Pakete: geprüfte Pakete direkt deployen — vorher WAL-sicheres Backup, danach Live-Prüfung. **Korrekturen an Produktionsdaten (Storno/Neuausstellung RE-00002/3/4, LfA-Entwürfe, Lieferschein-Verknüpfungen) weiterhin einzeln vorlegen.**

**Von Gernot bzw. Steuerberater:**
4. Pfand 19 %: IFCO-Kiste als Transporthilfsmittel bestätigen.
5. DATEV: EXTF-Buchungsstapel oder Unternehmen online? Berater-/Mandantennummer, WJ-Beginn, Sachkontenlänge, Debitorenkonten.
6. Welche Kunden rechnen Pfand über IFCO-Clearing ab — nur Ökoring und Bodan?
7. B1: Rezepturen der 26 Mixes.
8. ✅ B3 (Gernot, 08.10.): **Eine Mail mit mehreren Empfängern**, z. B. „Rechnung versendet an (1) rechnung@kunde.de, (2) einkäufer@kunde.de".
9. ✅ B5 (Gernot, 08.10.): **Monatlich fix.** Rückfrage von ihm: Wird sie am Monatsende automatisch erstellt und vorgeschlagen?
10. ✅ B4-Pfand (Gernot, 08.10.): Pro Kunde wählbar „Pfand von Rechnung ausnehmen" (Ökoring ja, Knuspr nein) — **oder** als Alternative: Pfand nie auf der Lieferrechnung, monatliche Pfand-Sammelrechnung, Eingabemaske für Pfandretouren, die dort verrechnet werden. Er fragt nach unserer Einschätzung.
11. ✅ B8 (Gernot, 08.10.): Mitarbeiter dürfen **Bestellungen anlegen sowie Auftragsbestätigungen und Lieferscheine anlegen und versenden. Rechnungen bleiben beim Admin.** → Entscheidung 3 (`production_staff`) wird daraufhin überprüft.
12. **B10 — SEPA-Lastschriftmandat (neu, 08.10.):** Kundenstamm mit Mandatsreferenz, Gläubiger-ID, Kontonummer, Bank, Mandatsdatum; Zahlungsart „Lastschriftmandat"; Hinweis in der Rechnungsmail mit maskierter IBAN.
