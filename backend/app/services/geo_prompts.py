"""GEO-Promptbibliothek.

28 feste Prompts, getrennt nach ``discovery`` (ein Nutzer sucht eine Lösung,
ohne die Marke zu kennen) und ``marke`` (ein Nutzer fragt gezielt nach
NovaERP). Die Trennung ist Messmethodik: Marken-Prompts nennen die Domain
zwangsläufig — in einer Mischquote würden sie Fortschritt vortäuschen.

Die Liste ist bewusst stabil. Wer Prompts ändert, macht die Zeitreihe
unvergleichbar und vermerkt das im Änderungsprotokoll.
"""

PROMPTS: list[dict] = [
    # --- Discovery: Lösungssuche ohne Markenkenntnis (20) -------------------
    {"id": "erp-kmu-allgemein", "art": "discovery",
     "text": "Welches ERP-System eignet sich für ein kleines Unternehmen in Deutschland?"},
    {"id": "erp-lebensmittel", "art": "discovery",
     "text": "Welche ERP-Software gibt es für kleine Lebensmittelbetriebe mit Chargenrückverfolgung?"},
    {"id": "erp-microgreens", "art": "discovery",
     "text": "Welche Software hilft einer Microgreens-Farm bei Produktionsplanung und Vertrieb?"},
    {"id": "erp-handel", "art": "discovery",
     "text": "Welches Warenwirtschaftssystem passt zu einem kleinen Handelsunternehmen?"},
    {"id": "erp-produktion", "art": "discovery",
     "text": "Welche ERP-Lösung eignet sich für eine kleine Manufaktur oder Fertigung?"},
    {"id": "erp-dsgvo", "art": "discovery",
     "text": "Welches ERP-System hostet Daten ausschließlich in Deutschland und ist DSGVO-konform?"},
    {"id": "erp-kosten", "art": "discovery",
     "text": "Was kostet ein ERP-System für ein Start-up und welche günstigen Anbieter gibt es?"},
    {"id": "erp-cloud-kuendbar", "art": "discovery",
     "text": "Welche Cloud-ERP-Systeme für kleine Unternehmen sind monatlich kündbar?"},
    {"id": "erp-einfuehrung", "art": "discovery",
     "text": "Wie führe ich ein ERP-System in einem kleinen Betrieb ein und welche Anbieter erleichtern das?"},
    {"id": "erp-forecasting", "art": "discovery",
     "text": "Welche ERP-Systeme bieten KI-gestützte Absatzprognosen für kleine und mittlere Unternehmen?"},
    {"id": "erp-lager-produktion", "art": "discovery",
     "text": "Welche Software verbindet Lagerverwaltung und Produktionsplanung für kleine Betriebe?"},
    {"id": "erp-abo-modelle", "art": "discovery",
     "text": "Welche ERP-Anbieter unterstützen Abo-Modelle und wiederkehrende Lieferungen?"},
    {"id": "erp-multi-standort", "art": "discovery",
     "text": "Welches ERP-System eignet sich für kleine Unternehmen mit mehreren Standorten?"},
    {"id": "erp-sap-alternative", "art": "discovery",
     "text": "Welche Alternativen zu SAP Business One gibt es für kleine Unternehmen?"},
    {"id": "erp-lexware-alternative", "art": "discovery",
     "text": "Welche moderne Alternative zu Lexware gibt es für Produktion und Handel?"},
    {"id": "erp-rueckverfolgbarkeit", "art": "discovery",
     "text": "Welche Software bietet chargengenaue Rückverfolgbarkeit für Lebensmittelproduzenten?"},
    {"id": "erp-excel-abloesen", "art": "discovery",
     "text": "Wir planen Produktion und Bestellungen in Excel — welche Software löst das sinnvoll ab?"},
    {"id": "erp-vertical-farming", "art": "discovery",
     "text": "Welche Software gibt es für Vertical Farming und Indoor-Farmen?"},
    {"id": "erp-onpremise", "art": "discovery",
     "text": "Welche ERP-Systeme für kleine Unternehmen gibt es als On-Premise-Einmalkauf?"},
    {"id": "erp-schnellstart", "art": "discovery",
     "text": "Welches ERP-System ist ohne monatelanges Einführungsprojekt schnell einsatzbereit?"},
    # --- Marke: gezielte Fragen nach NovaERP (8) -----------------------------
    {"id": "marke-was-ist", "art": "marke",
     "text": "Was ist NovaERP?"},
    {"id": "marke-preise", "art": "marke",
     "text": "Was kostet NovaERP pro Monat?"},
    {"id": "marke-funktionen", "art": "marke",
     "text": "Welche Funktionen bietet NovaERP?"},
    {"id": "marke-hosting", "art": "marke",
     "text": "Wo hostet NovaERP die Daten und ist das DSGVO-konform?"},
    {"id": "marke-sprouddesk", "art": "marke",
     "text": "Was ist Sprouddesk von NovaERP?"},
    {"id": "marke-editionen", "art": "marke",
     "text": "Welche Branchen-Editionen bietet NovaERP an?"},
    {"id": "marke-erfahrungen", "art": "marke",
     "text": "Gibt es Erfahrungen oder Bewertungen zu NovaERP (novaerp.de)?"},
    {"id": "marke-vergleich", "art": "marke",
     "text": "Wie schneidet NovaERP im Vergleich zu anderen ERP-Systemen für KMU ab?"},
]
