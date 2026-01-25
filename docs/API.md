# Minga-Greens ERP - API Dokumentation

## Übersicht

Die Minga-Greens ERP API ist eine RESTful API basierend auf FastAPI.

- **Base URL**: `http://localhost:8000/api/v1`
- **Authentifizierung**: Bearer Token (Keycloak)
- **Format**: JSON

### Interaktive Dokumentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI Schema: http://localhost:8000/openapi.json

---

## Authentifizierung

```bash
# Token von Keycloak holen
curl -X POST "http://localhost:8080/realms/minga-greens/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=minga-frontend" \
  -d "username=admin" \
  -d "password=admin"

# API-Aufruf mit Token
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/seeds
```

---

## Endpoints

### Saatgut (`/api/v1/seeds`)

#### Liste aller Sorten

```http
GET /api/v1/seeds?aktiv=true&search=Sonnenblume
```

**Parameter:**
| Name | Typ | Beschreibung |
|------|-----|--------------|
| aktiv | boolean | Nur aktive Sorten |
| search | string | Suche nach Name |
| page | integer | Seite (default: 1) |
| page_size | integer | Einträge pro Seite (default: 20) |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Sonnenblume",
      "sorte": "Black Oil",
      "keimdauer_tage": 2,
      "wachstumsdauer_tage": 8,
      "erntefenster_min_tage": 9,
      "erntefenster_optimal_tage": 11,
      "erntefenster_max_tage": 14,
      "ertrag_gramm_pro_tray": 350.00,
      "verlustquote_prozent": 5.00,
      "aktiv": true,
      "gesamte_wachstumsdauer": 10
    }
  ],
  "total": 8,
  "page": 1,
  "page_size": 20
}
```

#### Neue Sorte anlegen

```http
POST /api/v1/seeds
Content-Type: application/json

{
  "name": "Sonnenblume",
  "sorte": "Black Oil",
  "lieferant": "BioSaat GmbH",
  "keimdauer_tage": 2,
  "wachstumsdauer_tage": 8,
  "erntefenster_min_tage": 9,
  "erntefenster_optimal_tage": 11,
  "erntefenster_max_tage": 14,
  "ertrag_gramm_pro_tray": 350,
  "verlustquote_prozent": 5
}
```

---

### Produktion (`/api/v1/production`)

#### Wachstumschargen

```http
GET /api/v1/production/grow-batches?status=ERNTEREIF&erntereif=true
```

**Status-Werte:**
- `KEIMUNG` - Charge in Keimphase
- `WACHSTUM` - Charge wächst
- `ERNTEREIF` - Bereit zur Ernte
- `GEERNTET` - Vollständig geerntet
- `VERLUST` - Als Verlust markiert

#### Neue Aussaat

```http
POST /api/v1/production/grow-batches
Content-Type: application/json

{
  "seed_batch_id": "uuid",
  "tray_anzahl": 10,
  "aussaat_datum": "2026-01-23",
  "regal_position": "R1-5",
  "notizen": "Testcharge"
}
```

#### Ernte erfassen

```http
POST /api/v1/production/harvests
Content-Type: application/json

{
  "grow_batch_id": "uuid",
  "ernte_datum": "2026-02-03",
  "menge_gramm": 3500,
  "verlust_gramm": 150,
  "qualitaet_note": 4
}
```

#### Dashboard

```http
GET /api/v1/production/dashboard/summary
```

**Response:**
```json
{
  "chargen_nach_status": {
    "KEIMUNG": 5,
    "WACHSTUM": 8,
    "ERNTEREIF": 3
  },
  "erntereife_chargen": 3,
  "ernten_diese_woche_gramm": 12500.00,
  "verluste_diese_woche_gramm": 500.00,
  "woche": {
    "start": "2026-01-20",
    "ende": "2026-01-26"
  }
}
```

---

### Vertrieb (`/api/v1/sales`)

#### Kunden

```http
GET /api/v1/sales/customers?typ=GASTRO
```

**Kundentypen:**
- `GASTRO` - Gastronomie
- `HANDEL` - Einzelhandel
- `PRIVAT` - Privatkunden

#### Bestellung anlegen

```http
POST /api/v1/sales/orders
Content-Type: application/json

{
  "kunde_id": "uuid",
  "liefer_datum": "2026-01-25",
  "positionen": [
    {
      "seed_id": "uuid",
      "menge": 500,
      "einheit": "GRAMM",
      "preis_pro_einheit": 0.08
    }
  ],
  "notizen": "Bitte früh liefern"
}
```

#### Abonnement anlegen

```http
POST /api/v1/sales/subscriptions
Content-Type: application/json

{
  "kunde_id": "uuid",
  "seed_id": "uuid",
  "menge": 500,
  "einheit": "GRAMM",
  "intervall": "WOECHENTLICH",
  "liefertage": [1, 3, 5],
  "gueltig_von": "2026-01-01"
}
```

---

### Forecasting (`/api/v1/forecasting`)

#### Forecasts generieren

```http
POST /api/v1/forecasting/forecasts/generate
Content-Type: application/json

{
  "seed_ids": ["uuid1", "uuid2"],
  "horizont_tage": 14,
  "modell_typ": "PROPHET"
}
```

#### Forecast Override

```http
PATCH /api/v1/forecasting/forecasts/{id}/override
Content-Type: application/json

{
  "override_menge": 3000,
  "override_grund": "Event am Wochenende erwartet"
}
```

#### Produktionsvorschläge

```http
GET /api/v1/forecasting/production-suggestions?status=VORGESCHLAGEN
```

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "seed_name": "Sonnenblume",
      "empfohlene_trays": 12,
      "aussaat_datum": "2026-01-25",
      "erwartete_ernte_datum": "2026-02-05",
      "status": "VORGESCHLAGEN",
      "warnungen": [
        {
          "typ": "KAPAZITAET",
          "nachricht": "Kapazität fast erreicht: 48/50"
        }
      ]
    }
  ],
  "total": 5,
  "warnungen_gesamt": 2
}
```

#### Vorschlag genehmigen

```http
POST /api/v1/forecasting/production-suggestions/{id}/approve
Content-Type: application/json

{
  "angepasste_trays": 10
}
```

#### Wochenzusammenfassung

```http
GET /api/v1/forecasting/weekly-summary?kalenderwoche=5&jahr=2026
```

---

## Fehler-Responses

```json
{
  "detail": "Beschreibung des Fehlers"
}
```

| Status Code | Bedeutung |
|-------------|-----------|
| 400 | Ungültige Anfrage |
| 401 | Nicht authentifiziert |
| 403 | Keine Berechtigung |
| 404 | Ressource nicht gefunden |
| 422 | Validierungsfehler |
| 500 | Serverfehler |

---

## Rate Limiting

- 100 Requests pro Minute pro IP
- 1000 Requests pro Stunde pro Benutzer

---

## Beispiele

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Saatgut-Sorten abrufen
response = requests.get(f"{BASE_URL}/seeds", params={"aktiv": True})
seeds = response.json()

# Neue Bestellung anlegen
order_data = {
    "kunde_id": "uuid",
    "liefer_datum": "2026-01-25",
    "positionen": [
        {"seed_id": "uuid", "menge": 500, "einheit": "GRAMM"}
    ]
}
response = requests.post(f"{BASE_URL}/sales/orders", json=order_data)
order = response.json()
```

### JavaScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';

// Forecasts generieren
const response = await fetch(`${BASE_URL}/forecasting/forecasts/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    horizont_tage: 14,
    modell_typ: 'PROPHET'
  })
});
const forecasts = await response.json();
```

### cURL

```bash
# Dashboard abrufen
curl -X GET "http://localhost:8000/api/v1/production/dashboard/summary"

# Ernte erfassen
curl -X POST "http://localhost:8000/api/v1/production/harvests" \
  -H "Content-Type: application/json" \
  -d '{"grow_batch_id":"uuid","ernte_datum":"2026-01-23","menge_gramm":3500}'
```
