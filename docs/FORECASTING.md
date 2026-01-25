# Minga-Greens ERP - Forecasting Dokumentation

## Übersicht

Das Forecasting-Modul ist ein zentraler Bestandteil des Minga-Greens ERP-Systems. Es ermöglicht:

- **Absatzprognosen** basierend auf historischen Daten
- **Automatische Produktionsplanung** mit Tray-Berechnungen
- **Kapazitätswarnungen** bei Engpässen
- **Forecast Accuracy Tracking** zur kontinuierlichen Verbesserung

---

## Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                    FORECASTING SERVICE                           │
│                   (Port 8001, separater Container)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Daten-     │    │   Modell-    │    │   Ausgabe-   │      │
│  │   Pipeline   │ → │   Training   │ → │   Generator  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  • Sales History     • Prophet          • Forecasts            │
│  • Subscriptions     • ARIMA            • Produktionsplan      │
│  • Feiertage DE      • Ensemble         • Warnungen            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Modelle

### Prophet (Hauptmodell)

Prophet ist ein von Meta entwickeltes Zeitreihen-Forecasting-Tool, ideal für:

- **Saisonalität**: Wöchentliche und jährliche Muster
- **Feiertage**: Deutsche Feiertage werden automatisch berücksichtigt
- **Robustheit**: Gute Performance auch bei fehlenden Daten

**Konfiguration:**
```python
Prophet(
    weekly_seasonality=True,     # Wochentags-Muster
    yearly_seasonality=True,     # Jahreszeit-Effekte
    holidays=german_holidays,    # Deutsche Feiertage
    changepoint_prior_scale=0.05 # Trendänderungs-Sensitivität
)
```

### SimpleForecaster (Fallback)

Wird verwendet wenn:
- Weniger als 30 Tage historische Daten vorliegen
- Prophet fehlschlägt

**Methode:** Gleitende Durchschnitte mit Wochentags-Faktoren

---

## Datenquellen

### 1. Historische Bestellungen

```sql
SELECT liefer_datum, SUM(menge)
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
WHERE oi.seed_id = :seed_id
  AND o.status != 'STORNIERT'
GROUP BY liefer_datum
```

### 2. Abonnements

Regelmäßige Bestellungen werden als Baseline addiert:

```python
def subscription_demand(subscriptions, date):
    weekday = date.weekday()
    return sum(
        sub.menge
        for sub in subscriptions
        if weekday in sub.liefertage
    )
```

### 3. Feiertage

Deutsche Feiertage mit `holidays` Library:
- Reduzierte Nachfrage an Feiertagen (Gastronomie geschlossen)
- Erhöhte Nachfrage vor Feiertagen

---

## Forecast-Berechnung

### Schritt 1: Historische Daten laden

```python
# Letzte 90 Tage
historical = load_sales_history(seed_id, days_back=90)
```

### Schritt 2: Prophet Training

```python
forecaster = ProphetForecaster()
df = forecaster.prepare_data(historical)
forecaster.train(df, include_holidays=True)
```

### Schritt 3: Prognose erstellen

```python
forecast = forecaster.forecast(horizon_days=14)
# Returns: date, predicted, lower_bound, upper_bound
```

### Schritt 4: Abonnements addieren

```python
for fc in forecast:
    sub_demand = calculate_subscription_demand(fc.date)
    fc.total = fc.predicted + sub_demand
```

---

## Produktionsplanung

### Tray-Berechnung

```python
def berechne_trays(forecast_menge, seed):
    ertrag = seed.ertrag_gramm_pro_tray
    verlust_faktor = 1 - (seed.verlustquote_prozent / 100)
    effektiver_ertrag = ertrag * verlust_faktor

    return math.ceil(forecast_menge / effektiver_ertrag)
```

**Beispiel:**
- Forecast: 3.500g Sonnenblume
- Ertrag/Tray: 350g
- Verlustquote: 5%
- Effektiver Ertrag: 332,5g
- Benötigte Trays: ceil(3500 / 332,5) = **11 Trays**

### Aussaat-Datum Rückrechnung

```python
def berechne_aussaat_datum(ernte_datum, seed):
    wachstumstage = seed.keimdauer_tage + seed.wachstumsdauer_tage
    return ernte_datum - timedelta(days=wachstumstage)
```

---

## Warnungen

Das System generiert automatisch Warnungen:

| Typ | Beschreibung | Schweregrad |
|-----|--------------|-------------|
| `UNTERDECKUNG` | Aussaat-Datum liegt in der Vergangenheit | Hoch |
| `KAPAZITAET` | Regalkapazität überschritten | Hoch |
| `KAPAZITAET` | Regalkapazität > 90% | Mittel |
| `SAATGUT_NIEDRIG` | Saatgut-Bestand niedrig | Mittel |

---

## Forecast Accuracy

### MAPE (Mean Absolute Percentage Error)

```python
def berechne_mape(forecast, actual):
    if forecast == 0:
        return 0
    return abs((actual - forecast) / forecast) * 100
```

### Bewertung

| MAPE | Bewertung |
|------|-----------|
| < 10% | Exzellent |
| 10-20% | Gut |
| 20-30% | Akzeptabel |
| > 30% | Verbesserungsbedarf |

### Automatische Berechnung

Celery Task läuft täglich um 23:00:
```python
@celery_app.task
def calculate_forecast_accuracy():
    yesterday = date.today() - timedelta(days=1)

    for forecast in get_forecasts(datum=yesterday):
        actual = get_actual_sales(forecast.seed_id, yesterday)
        accuracy = ForecastAccuracy(
            forecast_id=forecast.id,
            ist_menge=actual
        )
        accuracy.berechne_abweichungen()
```

---

## Manual Override

Production Planner können Forecasts manuell anpassen:

```http
PATCH /api/v1/forecasting/forecasts/{id}/override
{
    "override_menge": 5000,
    "override_grund": "Großveranstaltung am Wochenende"
}
```

**Wichtig:** Override-Grund wird für Audit-Trail gespeichert.

---

## API Endpoints

### Forecasts generieren

```http
POST /api/v1/forecasting/forecasts/generate
{
    "seed_ids": ["uuid1", "uuid2"],
    "horizont_tage": 14,
    "modell_typ": "PROPHET"
}
```

### Produktionsvorschläge generieren

```http
POST /api/v1/forecasting/production-suggestions/generate?horizont_tage=14
```

### Wochenzusammenfassung

```http
GET /api/v1/forecasting/weekly-summary?kalenderwoche=5&jahr=2026
```

---

## Best Practices

### 1. Datenqualität

- Mindestens 30 Tage historische Daten für Prophet
- Bestellungen immer mit korrektem Lieferdatum erfassen
- Stornierte Bestellungen als solche markieren

### 2. Regelmäßige Überprüfung

- Wöchentlicher Accuracy-Report prüfen
- Bei MAPE > 30% manuelle Analyse

### 3. Override sparsam einsetzen

- Nur bei bekannten Events (Messen, Feiertage, etc.)
- Immer Grund dokumentieren

### 4. Kapazitäten aktuell halten

- Regalkapazität regelmäßig aktualisieren
- Tray-Bestand pflegen

---

## Erweiterungen (Roadmap)

1. **Wetterdaten-Integration**
   - Temperatur beeinflusst Wachstum
   - API: OpenWeatherMap

2. **Multi-Standort**
   - Forecasts pro Produktionsstandort

3. **Machine Learning Ensemble**
   - Kombination mehrerer Modelle
   - Automatische Modellauswahl

4. **Externe Events**
   - Kalender-Integration
   - Messen, Festivals, etc.

---

## Troubleshooting

### Prophet-Fehler

```
RuntimeError: Stan model ... not found
```

**Lösung:** Prophet Container neu bauen:
```bash
docker compose build --no-cache forecasting
```

### Keine Forecasts generiert

1. Prüfen ob historische Daten existieren
2. Prüfen ob Produkt aktiv ist
3. Logs prüfen: `docker compose logs forecasting`

### Accuracy nicht berechnet

Celery Beat Status prüfen:
```bash
docker compose logs celery-beat
```
