# Minga-Greens ERP — Backup-Strategie

## Übersicht

| Komponente      | Methode              | Intervall     | Aufbewahrung | Speicherort          |
|-----------------|----------------------|---------------|--------------|----------------------|
| PostgreSQL DB   | `pg_dump --Fc`       | Täglich 2:00  | 30 Tage      | `/backups/` + Remote |
| Redis           | RDB-Snapshot         | Stündlich      | 24 Stunden   | Docker Volume        |
| Uploads/Medien  | rsync                | Täglich 3:00  | 30 Tage      | Remote               |
| Keycloak DB     | Via PostgreSQL-Dump  | Täglich 2:00  | 30 Tage      | `/backups/`          |
| Konfiguration   | Git-Repository       | Bei Änderung  | Unbegrenzt   | GitHub               |

---

## 1. Datenbank-Backup (PostgreSQL)

### Automatisches tägliches Backup

Das Script `scripts/backup.sh` erstellt ein komprimiertes Backup im `custom`-Format:

```bash
# Manuell ausführen
docker compose exec backend /app/scripts/backup.sh

# Oder direkt auf dem Host
PGPASSWORD=<password> pg_dump \
  -h localhost -U minga -d minga_erp \
  --format=custom --compress=9 \
  -f /backups/minga_erp_backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Cron-Job (auf dem Host)

```bash
# /etc/cron.d/minga-backup
0 2 * * * root docker compose -f /opt/minga-greens-erp/docker-compose.yml exec -T backend /app/scripts/backup.sh >> /var/log/minga-backup.log 2>&1
```

### Backup-Rotation

- Tägliche Backups: 30 Tage
- Wöchentliche Backups (Sonntag): 12 Wochen
- Monatliche Backups (1. des Monats): 12 Monate

```bash
# Wöchentlich (Sonntag) in separates Verzeichnis kopieren
0 3 * * 0 cp /backups/minga_erp_backup_$(date +%Y%m%d)*.sql.gz /backups/weekly/
# Monatlich (1. des Monats)
0 3 1 * * cp /backups/minga_erp_backup_$(date +%Y%m%d)*.sql.gz /backups/monthly/
```

---

## 2. Restore

### Vollständige Wiederherstellung

```bash
# Container stoppen
docker compose stop backend celery-worker celery-beat

# Restore
PGPASSWORD=<password> pg_restore \
  -h localhost -U minga -d minga_erp \
  --clean --if-exists \
  /backups/minga_erp_backup_YYYYMMDD_HHMMSS.sql.gz

# Container starten
docker compose start backend celery-worker celery-beat
```

### Point-in-Time Recovery (PITR)

Für kritische Produktionsumgebungen kann WAL-Archivierung aktiviert werden:

```yaml
# postgresql.conf (in docker-compose)
environment:
  POSTGRES_INITDB_ARGS: "--wal-segsize=16"
  # In custom postgresql.conf:
  # archive_mode = on
  # archive_command = 'cp %p /backups/wal/%f'
```

---

## 3. Remote-Backup (Off-Site)

### Option A: Rsync zu zweitem Server

```bash
# In /etc/cron.d/minga-backup-remote
30 3 * * * root rsync -az --delete /backups/ backup@remote-server:/backups/minga-greens/
```

### Option B: S3-kompatibel (z.B. Hetzner Object Storage)

```bash
# Installation: apt install s3cmd
s3cmd put /backups/minga_erp_backup_*.sql.gz s3://minga-backups/daily/
```

---

## 4. Backup-Verifizierung

### Automatischer Test (wöchentlich)

```bash
#!/bin/bash
# scripts/verify_backup.sh
LATEST=$(ls -t /backups/minga_erp_backup_*.sql.gz | head -1)

# In temporäre DB restoren
createdb -h localhost -U minga minga_erp_verify
pg_restore -h localhost -U minga -d minga_erp_verify "$LATEST"

# Grundlegende Prüfungen
psql -h localhost -U minga -d minga_erp_verify -c "SELECT count(*) FROM customers;"
psql -h localhost -U minga -d minga_erp_verify -c "SELECT count(*) FROM orders;"
psql -h localhost -U minga -d minga_erp_verify -c "SELECT count(*) FROM invoices;"

# Aufräumen
dropdb -h localhost -U minga minga_erp_verify

echo "Backup-Verifizierung abgeschlossen: $(date)"
```

---

## 5. Monitoring

### Backup-Überwachung

```bash
# Prüfe ob Backup der letzten 25 Stunden existiert
find /backups -name "minga_erp_backup_*.sql.gz" -mmin -1500 | grep -q . \
  || echo "WARNUNG: Kein aktuelles Backup gefunden!" | mail -s "Backup Alert" admin@minga-greens.de
```

### Health-Check Endpunkt

Der `/health/detailed`-Endpunkt prüft u.a. ob die DB erreichbar ist.

---

## 6. Disaster Recovery

### RTO / RPO

| Metrik | Ziel       | Begründung                      |
|--------|------------|---------------------------------|
| RPO    | ≤ 24h      | Tägliches Backup                |
| RTO    | ≤ 2h       | Docker-basierter Neustart       |

### Wiederherstellungs-Checkliste

1. **Server bereitstellen** (Netcup VPS neu aufsetzen)
2. **Docker + Compose installieren**
3. **Repository klonen**: `git clone <repo-url>`
4. **`.env` wiederherstellen** (aus sicherem Speicher)
5. **Backup restoren** (siehe Abschnitt 2)
6. **Keycloak-Realm importieren**: `docker compose exec keycloak /opt/keycloak/bin/kc.sh import --dir /opt/keycloak/data/import`
7. **SSL-Zertifikate**: Caddy holt automatisch neue Let's-Encrypt-Zertifikate
8. **DNS prüfen**: A-Record zeigt auf neuen Server
9. **Funktionstest**: Dashboard, Login, Bestellungen prüfen
