Betreff: NovaERP – Update: was seit gestern neu ist und was ich noch von dir brauche

Hallo Gernot,

danke für deine Antworten. Seit gestern Abend und heute früh ist einiges live gegangen – hier der Überblick und am Ende die offenen Fragen.

NEU IM SYSTEM

Tagesplan und Bestellungen
- Im Tagesplan gibt es die Knöpfe „Gepackt“ und „Ausgeliefert“. Gepackte Bestellungen fallen aus dem Sortenbedarf, bleiben aber unter „Ausliefern“ stehen.
- Der Status heißt überall auf Deutsch, die Bestellliste zeigt die neuesten 100 und die Suche findet jetzt auch Bestellnummern, Kundenbestellnummern und Kundennamen.
- Bestell-Import: Bestellungen mit Lieferdatum heute oder später kommen als „Bestätigt“ an. Eine Datei wird nur ganz oder gar nicht übernommen, alle Fehler siehst du auf einmal. Deine zwei Zukunftsbestellungen (Großer Kern 10.10., Fruchthof Nagel 12.10.) habe ich zurückgesetzt.
- Abo-Bestellungen tragen jetzt das richtige Produkt, deinen Kundenpreis und den richtigen Steuersatz.

Rechnungen
- Pfand bekommt den Steuersatz aus dem Produkt, die IFCO-Kiste also 19 %. Die Rechnung weist die Steuer je Satz getrennt aus.
- Entwürfe tragen noch keine Rechnungsnummer – die Nummer wird erst beim Finalisieren lückenlos vergeben. Sammelrechnungen entstehen als Entwurf, du prüfst und gibst frei.
- Schutz vor Doppelabrechnung: zu einer Bestellung gibt es nur eine Rechnung. Bestellungen mit Rechnung lassen sich nicht mehr ändern, stornieren oder löschen, ohne vorher die Rechnung zu stornieren.
- „Zahlung erfassen“ funktioniert jetzt (vorher kam immer ein Fehler).
- Die Rechnungsliste zeigt wieder die Kundennamen.

Versand
- Am Kunden hinterlegst du die Empfänger je Belegart (Auftragsbestätigung, Lieferschein, Rechnung). Eine Mail geht an alle Adressen, im Beleg steht „versendet an …“.
- Lieferscheine kannst du jetzt auch per Mail verschicken. Die PDF-Dateien heißen wie die Belegnummer.

Pfand je Kunde
Du stellst je Kunde ein, wie Pfand abgerechnet wird:
- „Pfand auf jeder Rechnung“ (z. B. Knuspr),
- „Pfand nicht auf der Rechnung“ (IFCO-Clearing, z. B. Ökoring),
- „Pfand monatlich über das Leergutkonto“: Ausgaben zählt das System mit, Rücknahmen erfasst du (auch direkt im Tagesplan), einmal im Monat entsteht ein Leergutbeleg als Entwurf.

Monatliche Sammelrechnung
Je Kunde kannst du „monatliche Sammelrechnung“ wählen. Ist der Schalter in den Einstellungen an, liegen am 1. des Folgemonats morgens die Entwürfe bereit. Verschickt wird nichts automatisch – du prüfst und gibst frei.

SEPA-Lastschrift
Die Gläubiger-ID trägst du einmal in den Einstellungen ein, das Mandat (Referenz, IBAN, Bank, Datum) am Kunden. Rechnung und Mail nennen dann Mandat, Einzugsdatum und die gekürzte IBAN. Lastschriftrechnungen laufen nicht ins Mahnwesen. Für die Bank gibt es eine Einzugsliste als CSV.

Mitarbeiter-Zugänge legst du jetzt selbst an
Links unter Admin → Benutzerverwaltung: „Neuer Benutzer“, Name, E-Mail und Rolle wählen. Das System zeigt ein Einmalpasswort, das gibst du weiter; beim ersten Login vergibt der Mitarbeiter sein eigenes Passwort. Dort kannst du auch Rollen ändern, Zugänge deaktivieren und Passwörter zurücksetzen.
Die Rolle „Produktion“ darf Bestellungen sowie Auftragsbestätigungen und Lieferscheine anlegen und versenden, sieht aber keine Rechnungen und keine Konditionen. Für ein gemeinsames Hallen-Tablet empfehle ich einen eigenen Zugang mit dieser Rolle.

BITTE BIS ZUM NÄCHSTEN UPDATE NICHT
- keinen DATEV-Export auslösen – der Export ist korrigiert, die Kontierung soll aber erst dein Steuerberater bestätigen,
- keinen Sammelrechnungslauf starten, bis wir RE-2026-00002 bis -00005 gemeinsam bereinigt haben,
- RE-2026-00002 und -00004 nicht selbst stornieren – die korrigieren wir zusammen per Storno und neuer Rechnung.

WAS ICH VON DIR BRAUCHE (wichtigste zuerst)
1. Welche Kunden rechnen Pfand über IFCO-Clearing ab – nur Ökoring und Bodan?
2. RE-2026-00002 (Ökoring) und RE-2026-00004 (Großer Kern): Sind sie schon bezahlt? An welchem Tag wurde tatsächlich geliefert, am 07. oder 08.10.? Hast du sie auch an lexoffice übertragen?
3. Die 46 importierten Bestellungen vom 16.09. bis 07.10.: Sind die schon im alten System abgerechnet, oder sollen sie über NovaERP abgerechnet werden?
4. Klara Düran: Die Rechnung RE-2026-00005 hängt an der Bestellung, die du als doppelten Import storniert hast. Geliefert wurde die zweite Bestellung (BE-20261007-0008, gleiche Positionen). Ich verknüpfe die Rechnung mit der gelieferten Bestellung, damit sie nicht ein zweites Mal berechnet wird – passt das?
5. Gibt es Teillieferungen, also mehr als einen Lieferschein pro Bestellung?
6. Welche Kunden sollen monatlich abgerechnet werden? Und Knuspr: Pfand auf jeder Rechnung oder monatlich?
7. SEPA: Haben deine Kunden eine Basislastschrift (CORE) oder eine Firmenlastschrift (B2B) unterschrieben? Steht im Mandat eine kürzere Frist für die Vorankündigung als 14 Tage? Welche Kunden haben schon ein Mandat? Und bitte prüf die Gläubiger-ID – in deinem Beispiel hat sie 17 statt 18 Zeichen.
8. Die Rezepturen der 26 Mixe, die noch keine Stückliste haben: welche Sorten in welcher Menge?

BITTE AN DEINEN STEUERBERATER WEITERGEBEN
- Pfand für IFCO-Kisten mit 19 % als Transporthilfsmittel – richtig so?
- Darf Leergut (raus und zurück) monatlich in einem Beleg verrechnet werden?
- DATEV: Buchungsstapel-Datei (EXTF) oder DATEV Unternehmen online? Dazu Berater- und Mandantennummer, Beginn des Wirtschaftsjahres, Sachkontenlänge, Kontenrahmen (SKR03?) und die Debitorennummern.
- Gilt für euch die E-Rechnungspflicht ab 2027 oder erst ab 2028?

Viele Grüße
Nikolaj
