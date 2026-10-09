Hallo Gernot,

danke für deine Antworten. Kurz zum Stand und was ich noch von dir brauche.

**Seit gestern Abend bzw. heute früh live**
- **Bestell-Import:** Bestellungen mit Lieferdatum heute oder später kommen als „Bestätigt“ an. Der Import nimmt eine Datei nur ganz oder gar nicht und zeigt alle Fehler auf einmal. Deine zwei Zukunftsbestellungen (Großer Kern 10.10., Fruchthof Nagel 12.10.) habe ich zurückgesetzt.
- **Tagesplan:** Knöpfe „Gepackt“ und „Ausgeliefert“. Gepackte Bestellungen fallen aus dem Sortenbedarf, bleiben aber unter „Ausliefern“. Status heißen jetzt überall auf Deutsch.
- **Pfand:** neue Bestellungen bekommen den Satz aus dem Produkt, die IFCO-Kiste also 19 %. Je Kunde kannst du einstellen „Pfand nicht auf der Rechnung (IFCO-Clearing)“.
- **Rechnungen:** Die PDF weist die Steuer je Satz aus. Rechnungsliste mit Kundennamen und den neuesten 100. „Zahlung erfassen“ funktioniert jetzt (vorher kam immer ein Fehler).
- **Schutz vor Doppelabrechnung:** keine zweite Rechnung zur selben Bestellung. Bestellungen mit Rechnung lassen sich nicht mehr ändern, stornieren oder löschen, ohne vorher die Rechnung zu stornieren.
- **Abos:** Abo-Bestellungen tragen Produkt, deinen Kundenpreis und den richtigen Steuersatz.
- **Rechnungsnummer erst beim Finalisieren:** Entwürfe tragen keine RE-Nummer mehr, die Nummer kommt lückenlos beim Ausstellen. Sammelrechnungen entstehen als Entwurf, du prüfst und gibst frei.
- **Belegversand:** Am Kunden hinterlegst du Empfänger je Belegart (AB, Lieferschein, Rechnung). Eine Mail geht an alle Adressen, im Beleg steht „versendet an …“. Lieferscheine kannst du jetzt auch mailen. PDFs heißen wie die Belegnummer.
- **SEPA-Lastschrift:** Gläubiger-ID in den Einstellungen, Mandat am Kunden. Rechnung und Mail nennen Mandat, Einzugsdatum und die maskierte IBAN. Lastschriftrechnungen laufen nicht ins Mahnwesen. Einzugsliste mit CSV für die Bank.
- **Leergutkonto:** Je Kunde „Pfand monatlich“: Ausgaben werden mitgezählt, Rücknahmen erfasst du (auch im Tagesplan), einmal im Monat entsteht ein Leergutbeleg als Entwurf.
- **Monatsrechnung:** Je Kunde „monatliche Sammelrechnung“. Ist der Schalter in den Einstellungen an, liegen am 1. des Folgemonats morgens die Entwürfe bereit. Bis du Monatskunden einstellst, passiert nichts.
- **Mitarbeiter-Zugänge legst du jetzt selbst an:** links unter Admin → Benutzerverwaltung. „Neuer Benutzer“, Name, E-Mail, Rolle wählen — das System zeigt ein Einmalpasswort, das gibst du weiter; beim ersten Login vergibt der Mitarbeiter sein eigenes Passwort. Dort kannst du auch Rollen ändern, Zugänge deaktivieren und Passwörter zurücksetzen. Die Halle (Rolle Produktion) sieht Produkte, Tagesplan und Lieferscheine, aber keine Rechnungen und keine Konditionen.

**Bitte bis zum nächsten Update nicht**
- keinen DATEV-Export auslösen (der Export ist korrigiert, die Kontierung soll aber erst dein Steuerberater bestätigen),
- keinen Sammelrechnungslauf starten, bis wir RE-00002 bis -00005 gemeinsam bereinigt haben,
- RE-2026-00002 und -00004 nicht selbst stornieren (wir korrigieren sie gemeinsam per Storno und neuer Rechnung).

**Zu deinen Fragen**
- **Pfand:** Ja, das geht. Du stellst je Kunde ein: „Pfand auf jeder Rechnung" (z. B. Knuspr), „kein Pfand auf der Rechnung" (IFCO-Clearing, z. B. Ökoring) oder „monatlich über das Leergutkonto". Beim Leergutkonto wird erfasst, was rausgeht und was zurückkommt, und einmal im Monat abgerechnet. Alle drei Einstellungen sind jetzt da.
- **Mitarbeiter:** Sie dürfen Bestellungen, Auftragsbestätigungen und Lieferscheine anlegen und versenden, Rechnungen bleiben bei dir.

**Was ich bald von dir brauche (wichtigste zuerst)**
1. Welche Kunden rechnen Pfand über IFCO-Clearing ab? Nur Ökoring und Bodan?
2. RE-00002 (Ökoring) und RE-00004 (Großer Kern): Schon bezahlt? An welchem Tag wurde tatsächlich geliefert (07. oder 08.10.)? Hast du sie auch an lexoffice übertragen?
3. Die 46 importierten Bestellungen vom 16.09. bis 07.10.: Hast du die schon im alten System abgerechnet, oder sollen sie über NovaERP abgerechnet werden? Und Klara Düran: Die Rechnung RE-2026-00005 hängt an der Bestellung, die du als doppelten Import storniert hast. Geliefert wurde die zweite Bestellung (BE-20261007-0008, gleiche Positionen). Ich verknüpfe die Rechnung mit der gelieferten Bestellung, damit sie nicht ein zweites Mal berechnet wird — passt das so?
4. Mitarbeiter: Legst du die Zugänge selbst an, oder soll ich das für dich übernehmen? Für ein gemeinsames Hallen-Tablet empfehle ich einen eigenen Zugang mit der Rolle Produktion.
5. Gibt es Teillieferungen, also mehr als einen Lieferschein pro Bestellung?
6. Welche Kunden sollen monatlich abgerechnet werden? Und Knuspr: Pfand auf jeder Rechnung oder monatlich?
7. SEPA: Haben deine Kunden eine Basislastschrift (CORE) oder eine Firmenlastschrift (B2B) unterschrieben? Steht im Mandat eine kürzere Frist für die Vorankündigung als 14 Tage? Bitte prüf die Gläubiger-ID, im Beispiel hat sie 17 statt 18 Zeichen. Welche Kunden haben schon ein Mandat?
8. Rezepturen der 26 Mixes, die noch keine Stückliste haben (welche Sorten in welcher Menge).

**Bitte an deinen Steuerberater weitergeben**
- Pfand für IFCO-Kisten mit 19 % als Transporthilfsmittel — richtig so?
- Darf Leergut (raus und zurück) monatlich in einem Beleg verrechnet werden?
- DATEV: Buchungsstapel-Datei (EXTF) oder DATEV Unternehmen online? Berater- und Mandantennummer, Beginn des Wirtschaftsjahres, Sachkontenlänge, Kontenrahmen (SKR03?), Debitorennummern.
- Gilt für euch die E-Rechnungspflicht ab 2027 oder ab 2028?

Viele Grüße
Nikolaj
