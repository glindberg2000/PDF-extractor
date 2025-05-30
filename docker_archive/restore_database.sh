#!/bin/bash

# Database connection details
DB_NAME="mydatabase"
DB_USER="newuser"
DB_PASSWORD="newpassword"
DB_HOST="localhost"
DB_PORT="5432"

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Backup file ${BACKUP_FILE} not found!"
    exit 1
fi

# Decompress backup
echo "Decompressing backup..."
gunzip -c "${BACKUP_FILE}" > temp_backup.sql

# Restore database with specific connection details
echo "Restoring database..."
PGPASSWORD="${DB_PASSWORD}" psql \
    -U "${DB_USER}" \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -d "${DB_NAME}" \
    < temp_backup.sql

# Clean up
rm temp_backup.sql

echo "Database restore completed!" 