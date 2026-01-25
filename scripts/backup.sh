#!/bin/bash
# Minga-Greens ERP - Backup Script
# Erstellt ein Backup der PostgreSQL Datenbank

set -e

# Konfiguration
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="minga_erp_backup_${TIMESTAMP}.sql.gz"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "======================================"
echo "Minga-Greens ERP - Datenbank Backup"
echo "======================================"
echo ""

# Prüfen ob Backup-Verzeichnis existiert
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR"
    echo -e "${GREEN}Backup-Verzeichnis erstellt: $BACKUP_DIR${NC}"
fi

# Backup erstellen
echo "Erstelle Backup..."
PGPASSWORD="${POSTGRES_PASSWORD:-minga_secret}" pg_dump \
    -h "${POSTGRES_HOST:-postgres}" \
    -U "${POSTGRES_USER:-minga}" \
    -d "${POSTGRES_DB:-minga_erp}" \
    --format=custom \
    --compress=9 \
    -f "${BACKUP_DIR}/${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Backup erfolgreich erstellt: ${BACKUP_FILE}${NC}"

    # Backup-Größe anzeigen
    SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    echo "Größe: $SIZE"

    # Alte Backups löschen (älter als 30 Tage)
    echo ""
    echo "Bereinige alte Backups (> 30 Tage)..."
    find "$BACKUP_DIR" -name "minga_erp_backup_*.sql.gz" -mtime +30 -delete

    # Anzahl verbleibender Backups
    COUNT=$(ls -1 "${BACKUP_DIR}"/minga_erp_backup_*.sql.gz 2>/dev/null | wc -l)
    echo "Verbleibende Backups: $COUNT"
else
    echo -e "${RED}Backup fehlgeschlagen!${NC}"
    exit 1
fi

echo ""
echo "======================================"
echo "Backup abgeschlossen"
echo "======================================"
