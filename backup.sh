#!/bin/bash

# Lozinka za postgres korisnika
export PGPASSWORD='Lav231055!'

# Datum u formatu YYYY/MM/DD
YEAR=$(date +%Y)
MONTH=$(date +%m)
DAY=$(date +%d)

# Folder za backup
BACKUP_DIR="/home/lav/backup/$YEAR/$MONTH/$DAY"
mkdir -p "$BACKUP_DIR"

# Fajl za backup
BACKUP_FILE="$BACKUP_DIR/mrkdb.backup"

# Pokretanje pg_dump
pg_dump --host=localhost --port=5433 --username=postgres \
  --format=custom --file="$BACKUP_FILE" mrkdb

echo "Backup završen. Fajl: $BACKUP_FILE"

