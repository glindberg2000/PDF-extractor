#!/bin/bash

# Set variables
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="database_backups"
BACKUP_FILE="${BACKUP_DIR}/test_django_backup_${TIMESTAMP}.sql"

# Database connection details
DB_NAME="mydatabase"
DB_USER="newuser"
DB_PASSWORD="newpassword"
DB_HOST="localhost"
DB_PORT="5432"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Create backup using Docker to ensure correct PostgreSQL version
echo "Creating database backup for test_django using Docker..."
docker run --rm \
    -e PGPASSWORD="${DB_PASSWORD}" \
    --network host \
    postgres:17 \
    pg_dump \
    -U "${DB_USER}" \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    --no-comments \
    --no-privileges \
    --no-tablespaces \
    --no-unlogged-table-data \
    --no-sync \
    --format=plain \
    > "${BACKUP_FILE}"

# Verify backup was created
if [ -s "${BACKUP_FILE}" ]; then
    # Compress backup
    echo "Compressing backup..."
    gzip "${BACKUP_FILE}"
    echo "Backup created successfully: ${BACKUP_FILE}.gz"
else
    echo "Error: Backup file is empty or was not created!"
    exit 1
fi 