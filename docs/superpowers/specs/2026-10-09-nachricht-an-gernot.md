Betreff: NovaERP – Update 09.10.: Rechnungen bereinigt, DATEV auf SKR04, Belegordner

Hallo Gernot,

danke für deine Antworten im Word-Dokument und die Liste der Monatskunden. Ich habe alles eingearbeitet – hier der Stand und am Ende ein paar Fragen.

RECHNUNGEN BEREINIGT

- Großer Kern: RE-2026-00004 ist storniert (Stornorechnung RE-2026-00007). Neu ausgestellt als RE-2026-00008 über 421,19 €, die Pfandkiste jetzt mit 19 %.
- Ökoring: RE-2026-00002 ist storniert (RE-2026-00006). Die neue Rechnung ohne Pfand (IFCO-Clearing) ist RE-2026-00010 über 115,56 €. Dazwischen gibt es RE-2026-00003 und RE-2026-00009: RE-00003 trug noch das Datum 07.10., also vor der Lieferung am 08.10. Ich habe sie deshalb noch einmal storniert und mit heutigem Datum neu ausgestellt.
- Bitte RE-2026-00008 und RE-2026-00010 wie gewohnt verschicken. Die Stornorechnungen musst du den Kunden nicht schicken, weil die ursprünglichen Rechnungen laut deiner Auskunft nie bei ihnen waren.
- Klara Düran: RE-2026-00005 hängt jetzt an der gelieferten Bestellung BE-20261007-0008.
- Die 574 importierten Bestellungen bis 07.10. stehen auf „Fakturiert“ (über DATEV abgerechnet). Sie kommen in keinem Sammel- oder Monatslauf mehr vor. Bitte lege für diese alten Bestellungen auch keine Rechnung über „Rechnung aus Bestellung“ an – die Sperre dafür kommt mit dem nächsten Update.
- Geliefert, aber noch ohne Rechnung sind: BE-20261007-0003 (Naturkostinsel, 08.10.), BE-20261008-0002 (Dorint, Abo, 08.10.) und BE-20261008-0006 (Bierbichler, 09.10.). Bitte jeweils im Belegdialog „Rechnung aus Bestellung“ anlegen und festschreiben.

MONATLICHE SAMMELRECHNUNG

Die 9 Kunden aus deiner Liste sind umgestellt, der Schalter ist an. Am 1. November morgens liegen die Entwürfe für Oktober bereit – du prüfst und gibst frei, verschickt wird nichts automatisch.

NEU SEIT HEUTE ABEND

DATEV
- Der Export bucht jetzt im Kontenrahmen SKR04 (Erlöse 7 % auf 4300, 19 % auf 4400). Für MingaGreens ist SKR04 fest eingestellt.
- Der DATEV-Export bleibt gesperrt, bis dein Steuerberater die Kontierung bestätigt hat. Im Export-Dialog steht der Hinweis. Sobald die Bestätigung da ist, schalte ich ihn frei.

Firmendaten
- Die Karte „Firmendaten“ in den Einstellungen hat bisher nur im Browser gespeichert – das war unser Fehler. Jetzt speichert sie auf dem Server. Eintragen musst du nichts: Briefkopf und Fußzeile deiner Belege kommen weiter aus den Belegvorlagen (Admin → Belegvorlagen), und die Mails grüßen mit „MingaGreens GmbH“.

Belegordner – deine Frage nach dem Speicherort
- In Chrome oder Edge am Computer: Einstellungen → „Belegordner“ → „Belegordner wählen“, zum Beispiel einen Ordner „Belege“ in deinen Dokumenten. Danach landen alle PDFs dort, sortiert nach Belegart und Monat, zum Beispiel Belege/Rechnungen/2026-10/RE-2026-00010.pdf.
- Der Browser fragt nach jedem Neustart einmal, ob NovaERP auf den Ordner zugreifen darf. Mit „Bei jedem Besuch zulassen“ entfällt die Frage. Falls du einmal „Nicht zulassen“ klickst: alle NovaERP-Tabs schließen und die Seite neu öffnen.
- Die Einstellung gilt je Browser und Rechner. Auf dem Tablet und in Safari oder Firefox bleibt es beim normalen Download.
- Probier es bitte einmal aus und sag mir, ob es klappt – die Freigabe-Frage des Browsers lässt sich nur von Hand testen.

IM NÄCHSTEN UPDATE (in Arbeit)

- Mixe erscheinen im Sortenbedarf als Einzelsorten. Deine Rezepturen sind da, nur waren die Mixe im System nicht als Mix gekennzeichnet. Das korrigiere ich mit dem Update – du musst nichts neu eingeben.
- „Gepackt“ und „Ausgeliefert“ im Tagesplan gehen auch bei Bestellungen, die noch Entwurf sind, und bestätigen sie dabei.
- „Ausgeliefert“ legt den Lieferschein automatisch an, damit jede Lieferung in der Monatsrechnung landet.
- Neue Seite „Belegstatus“: je Bestellung Lieferschein, Rechnung, versendet, bezahlt – mit Filtern nach Zeitraum, Kunde und „nur unvollständige“.
- Dateinamen mit Kundenname, zum Beispiel LS-20261008-001_Fruchthof-Nagel-GmbH.pdf.
- Im Rechnungsentwurf Menge und Preis direkt in der Tabelle ändern; die Suche wirkt in allen Reitern.
- Rolle „Produktion“: sieht keine Preise und Konditionen der Kunden mehr und kann keine Adressen oder Ansprechpartner löschen.
- Bestellungen, die schon über DATEV abgerechnet sind, lassen sich nicht noch einmal berechnen.

WAS DU SELBST ERLEDIGEN KANNST

- RE-2026-00008 und RE-2026-00010 verschicken, die drei Bestellungen oben berechnen.
- SEPA-Mandate am Kunden eintragen (Referenz, IBAN, Datum): LEKKEREI (KD-10005), MKW Gastro (KD-10035), Naturkostinsel (KD-10007) und Wagner Gastro (KD-10013).
- Naturkostinsel: die zweite Filiale als eigenen Kunden anlegen, mit ihrem eigenen Mandat.
- Growroom: in der Produktion einmal die Gesamtzahl deiner Stellplätze eintragen.

WAS ICH VON DIR BRAUCHE

1. Sieben alte Bestellungen stehen noch als Entwurf mit Liefertag bis 07.10.: BE-20260914-0001, BE-20260921-0001, BE-20260928-0001, BE-20261005-0001 (alle LfA, Abo), BE-20260917-0002 (Klara Düran), BE-20260917-0003 (Bierbichler – die falsch erfasste aus deinem Buglog) und BE-20261007-0001 (Gemüsebau Kiening). Je Bestellung: geliefert und über DATEV abgerechnet, oder nicht geliefert? Bis zu deiner Antwort bitte nicht bestätigen.
2. Gläubiger-ID: Eingetragen ist DE75ZZZ00002442146. In deinem Word steht „DE7S2ZZ…“ – ich gehe von einem Tippfehler aus. Stimmt DE75ZZZ00002442146?
3. SEPA-Vorankündigung: In den Einstellungen stehen 7 Tage (üblich sind 14). Steht diese kürzere Frist so in deinen Mandaten?
4. lexoffice: Hast du RE-2026-00002 oder RE-2026-00004 auch in lexoffice angelegt? Dann müssten sie dort ebenfalls storniert werden.
5. Entwürfe im Tagesplan: Ab dem nächsten Update bestätigt „Gepackt“ bzw. „Ausgeliefert“ einen Entwurf mit – bis zu seinem Liefertag. Passt das, oder sollen Entwürfe immer erst im Büro bestätigt werden?
6. Snackbox Brotzeitmix und Salatmix: Wachsen sie aus einer fertigen Saatgutmischung in einer Schale (dann ist nichts zu tun), oder stellst du sie beim Packen aus mehreren Sorten zusammen (dann bekommen sie eine Rezeptur wie die Mixe)?
7. Kisten: Ist eine „BIO Kiste | Erbse (VPE 6)“ genau 6 × „BIO Snackbox | Erbse“? Dann hinterlegen wir das für alle Kisten, und der Sortenbedarf zeigt Snackboxen statt Kisten.
8. Gastrotray (Staatsministerium, Dorint, LfA): Liegen da je Kunde immer dieselben Sorten drin? Welche?
9. Mitarbeiter: Sie können Kunden anlegen und Kundendaten ändern (Adressen, Ansprechpartner, Liefertage), sehen aber keine Konditionen und löschen nichts – so wie du es am 03.09. festgelegt hast. Soll das so bleiben? Und sollen sie Abos anlegen oder ändern dürfen?
10. Growroom: 69 importierte Chargen stehen noch auf „erntereif“ und belegen rechnerisch 395 Kisten. Sind die alle längst geerntet? Dann schließe ich sie ab, und die Stellplatzübersicht stimmt wieder.

BITTE AN DEINEN STEUERBERATER WEITERGEBEN

- Kontierung im SKR04 bestätigen: Erlöse 7 % auf 4300, 19 % (Pfandkiste) auf 4400, Zahlungen auf Bank 1800 bzw. Kasse 1600. Heute laufen alle Rechnungen über einen Sammeldebitor 10000 – braucht er Einzeldebitoren je Kunde?
- Welches Importformat: DATEV-Buchungsstapel (mit Berater- und Mandantennummer, Beginn des Wirtschaftsjahres, Sachkontenlänge) für Rechnungswesen bzw. Unternehmen online? Sollen die Rechnungs-PDFs als Belegbilder mitgehen?
- Pfand für IFCO-Kisten mit 19 % als Transporthilfsmittel – richtig so? Darf Leergut monatlich in einem Beleg verrechnet werden?
- E-Rechnungspflicht: ab 2027 oder erst ab 2028? Bitte gib mir früh Bescheid, falls 2027 – NovaERP erzeugt E-Rechnungen (XRechnung/ZUGFeRD) noch nicht.

Viele Grüße
Nikolaj
