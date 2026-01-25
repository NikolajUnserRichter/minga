# Minga-Greens ERP - Installationsanleitung

## Voraussetzungen

### Hardware
- **Minimum**: 4 GB RAM, 2 CPU Cores, 20 GB SSD
- **Empfohlen**: 8 GB RAM, 4 CPU Cores, 50 GB SSD

### Software
- Docker 24.0+
- Docker Compose 2.20+
- Git

### Betriebssystem
- Ubuntu Server 22.04 LTS (empfohlen)
- Debian 12
- macOS 13+ (Entwicklung)

---

## Schnellinstallation

```bash
# 1. Repository klonen
git clone https://github.com/minga-greens/erp.git
cd minga-greens-erp

# 2. Umgebungsvariablen konfigurieren
cp .env.example .env
nano .env  # Passwörter anpassen!

# 3. Services starten
docker compose up -d

# 4. Warten bis alle Services healthy sind
docker compose ps

# 5. Datenbank initialisieren
docker compose exec backend alembic upgrade head

# 6. Beispieldaten laden (optional)
docker compose exec backend python scripts/seed_data.py

# 7. System testen
curl http://localhost:8000/health
```

---

## Detaillierte Installation

### 1. System vorbereiten

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git

# Docker installieren
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Logout/Login erforderlich

# Docker Compose Plugin
sudo apt install -y docker-compose-plugin
```

### 2. Repository klonen

```bash
cd /opt
sudo git clone https://github.com/minga-greens/erp.git minga-greens-erp
sudo chown -R $USER:$USER minga-greens-erp
cd minga-greens-erp
```

### 3. Konfiguration

Erstellen Sie die `.env` Datei:

```bash
cp .env.example .env
```

Bearbeiten Sie die Datei und setzen Sie **sichere Passwörter**:

```env
# Datenbank
POSTGRES_USER=minga
POSTGRES_PASSWORD=IhrSicheresPasswort123!
POSTGRES_DB=minga_erp

# Backend
SECRET_KEY=MindestensZweiundDreissigZeichenLangerKey

# Keycloak
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=AdminPasswort456!
```

### 4. Services starten

```bash
# Alle Services starten
docker compose up -d

# Logs beobachten
docker compose logs -f

# Status prüfen
docker compose ps
```

### 5. Datenbank initialisieren

```bash
# Migrations ausführen
docker compose exec backend alembic upgrade head

# Beispieldaten laden (nur für Tests/Demo)
docker compose exec backend python scripts/seed_data.py
```

### 6. Keycloak konfigurieren

1. Öffnen Sie http://localhost:8080
2. Login mit Admin-Credentials
3. Der Realm "minga-greens" wird automatisch importiert
4. Standard-Benutzer (Passwörter ändern!):
   - `admin` / `admin`
   - `planner` / `planner`
   - `staff` / `staff`

---

## Zugriff

| Service | URL | Beschreibung |
|---------|-----|--------------|
| Frontend | http://localhost:3000 | React Benutzeroberfläche |
| API Docs | http://localhost:8000/docs | Swagger API Dokumentation |
| API ReDoc | http://localhost:8000/redoc | Alternative API Docs |
| Keycloak | http://localhost:8080 | Benutzerverwaltung |
| Metabase | http://localhost:3001 | BI & Reporting |

---

## Produktions-Deployment

### SSL/TLS mit nginx

```nginx
server {
    listen 443 ssl http2;
    server_name erp.minga-greens.de;

    ssl_certificate /etc/letsencrypt/live/erp.minga-greens.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/erp.minga-greens.de/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /auth {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Automatische Backups

```bash
# Crontab bearbeiten
crontab -e

# Tägliches Backup um 2:00 Uhr
0 2 * * * cd /opt/minga-greens-erp && docker compose exec -T backend bash /app/scripts/backup.sh >> /var/log/minga-backup.log 2>&1
```

### Systemd Service

```ini
# /etc/systemd/system/minga-greens.service
[Unit]
Description=Minga-Greens ERP
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/minga-greens-erp
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable minga-greens
sudo systemctl start minga-greens
```

---

## Fehlerbehebung

### Container startet nicht

```bash
# Logs prüfen
docker compose logs backend

# Container neu bauen
docker compose build --no-cache backend
docker compose up -d backend
```

### Datenbank-Verbindungsfehler

```bash
# Postgres Status prüfen
docker compose exec postgres pg_isready

# Manuell verbinden
docker compose exec postgres psql -U minga -d minga_erp
```

### Port bereits belegt

```bash
# Prüfen welcher Prozess den Port nutzt
sudo lsof -i :8000

# Alternative Ports in docker-compose.yml konfigurieren
```

---

## Updates

```bash
cd /opt/minga-greens-erp

# Backup erstellen
docker compose exec backend bash /app/scripts/backup.sh

# Neueste Version holen
git pull origin main

# Container neu bauen
docker compose build

# Services neu starten
docker compose up -d

# Migrations ausführen
docker compose exec backend alembic upgrade head
```

---

## Support

- GitHub Issues: https://github.com/minga-greens/erp/issues
- E-Mail: support@minga-greens.de
