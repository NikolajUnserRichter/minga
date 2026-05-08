# Minga-Greens ERP

Open-Source On-Premise ERP-System für Microgreens-Produktion.

## Features

- **Produktionsmanagement**: Vollständiger Lebenszyklus von Saatgut bis Ernte
- **Rückverfolgbarkeit**: Chargen-Tracking von Seed-Batch bis Verkauf
- **Forecasting**: KI-gestützte Absatzprognosen mit Prophet
- **Produktionsplanung**: Automatische Aussaat- und Erntevorschläge
- **Kundenverwaltung**: B2B-Kunden, Abonnements, Bestellungen
- **Reporting**: BI-Dashboards mit Metabase

## Technologie-Stack

| Komponente | Technologie |
|------------|-------------|
| Backend | Python, FastAPI |
| Datenbank | PostgreSQL 15 |
| Forecasting | Prophet, statsmodels |
| Frontend | React, TypeScript, Vite |
| Auth | Keycloak |
| BI | Metabase |
| Queue | Redis, Celery |
| Deployment | Docker Compose |

## Schnellstart

### Voraussetzungen

- Docker & Docker Compose
- Git

### Installation

```bash
# Repository klonen
git clone https://github.com/minga-greens/erp.git
cd minga-greens-erp

# Umgebungsvariablen konfigurieren
cp .env.example .env
# Bearbeite .env und setze sichere Passwörter

# Services starten
docker compose up -d

# Datenbank initialisieren
docker compose exec backend alembic upgrade head

# Beispieldaten laden (optional)
docker compose exec backend python scripts/seed_data.py
```

### Zugriff

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| Keycloak | http://localhost:8080 |
| Metabase | http://localhost:3001 |

### Standard-Login

- **Admin**: admin / admin (bitte sofort ändern!)

## Projektstruktur

```
minga-greens-erp/
├── backend/          # FastAPI REST API
├── forecasting/      # Prophet Forecasting Service
├── frontend/         # React UI
├── workers/          # Celery Background Tasks
├── keycloak/         # Auth Konfiguration
├── metabase/         # BI Dashboards
├── scripts/          # Hilfsskripte
└── docs/             # Dokumentation
```

## Dokumentation

- [Installation](docs/INSTALLATION.md)
- [API-Referenz](docs/API.md)
- [Forecasting](docs/FORECASTING.md)

## Entwicklung

```bash
# Backend im Dev-Modus
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend im Dev-Modus
cd frontend
npm install
npm run dev
```

## Temporäres Hosting (kostenlos für ein paar Tage)

Für schnelle Demos kann das Projekt als **Single-Service** auf Railway (Trial Credits) deployed werden.

### Was dabei läuft

- Frontend + Backend in **einem Container**
- SQLite für temporäre Demo-Daten
- Auth-Bypass aktiv (für Demo-Zwecke)

### Deploy-Schritte (Railway)

1. Neues Projekt auf Railway erstellen und dieses Git-Repo verbinden
2. Root `Dockerfile` verwenden (wird automatisch erkannt)
3. In den Service-Variablen setzen:

```bash
AUTH_DISABLED=true
DATABASE_URL=sqlite:////data/minga_demo.db
VITE_AUTH_DISABLED=true
```

4. Optional: Persistent Volume auf `/data` anlegen, damit Daten nach Redeploy erhalten bleiben
5. Deploy starten und die erzeugte Railway-URL öffnen

### Wichtige Hinweise

- Diese Variante ist **nur für temporäre Tests/Demos** gedacht.
- Für Produktion weiter die Docker-Compose-Architektur mit Postgres/Redis/Keycloak verwenden.

## Lizenz

MIT License - siehe [LICENSE](LICENSE)

## Support

Bei Fragen: info@minga-greens.de
