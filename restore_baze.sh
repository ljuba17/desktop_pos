#!/bin/bash

# Lozinka za postgres korisnika - uvek u navodnicima!
export PGPASSWORD='Lav231055!'

PG_RESTORE="/usr/bin/pg_restore"
HOST="localhost"
PORT="5432"
USER="postgres"
DB="mrkdb"

BACKUPDIR="/home/lav/backup"

echo "========================================"
echo "   RESTORE POSTGRESQL BEKAPA"
echo "========================================"
echo "Dostupni bekapi:"
echo "----------------------------------------"

# Ispis dostupnih bekapa u formatu yyyy-mm-dd
find "$BACKUPDIR" -type f -name "mrkdb.backup" | sed "s|$BACKUPDIR/||" | cut -d'/' -f1-3 | sort | uniq | \
while read line; do
    # linija je oblika YYYY/MM/DD -> prebacujemo u YYYY-MM-DD
    echo "$line" | sed 's|/|-|g'
done

echo "----------------------------------------"
read -p "Unesite datum (yyyy-mm-dd): " DATUM

# Parsiranje datuma
GODINA=$(echo "$DATUM" | cut -d'-' -f1)
MESEC=$(echo "$DATUM" | cut -d'-' -f2)
DAN=$(echo "$DATUM" | cut -d'-' -f3)

FILE="$BACKUPDIR/$GODINA/$MESEC/$DAN/mrkdb.backup"

if [ -f "$FILE" ]; then
    echo "Pokrećem restore sa fajla: $FILE"
    $PG_RESTORE --host=$HOST --port=$PORT --username=$USER \
      --dbname=$DB --verbose "$FILE"
    echo "----------------------------------------"
    echo "Restore završen uspešno."
else
    echo "Greška: Fajl ne postoji!"
    echo "Očekivana putanja: $FILE"
fi
