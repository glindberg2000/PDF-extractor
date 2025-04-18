#!/bin/bash

# Check if backup directory is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_directory>"
    echo "Example: $0 backups/backup_20250417_204218"
    exit 1
fi

BACKUP_DIR=$1

# Verify backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo "Error: Backup directory $BACKUP_DIR does not exist"
    exit 1
fi

# Verify required files exist
if [ ! -f "$BACKUP_DIR/main_database.sql" ] || [ ! -f "$BACKUP_DIR/test_database.sql" ]; then
    echo "Error: Required database backup files not found in $BACKUP_DIR"
    exit 1
fi

echo "Starting rollback process..."
echo "This will restore both code and database to the state in $BACKUP_DIR"
read -p "Are you sure you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled"
    exit 1
fi

# Step 1: Restore code
echo "Restoring code..."
if [ -d "$BACKUP_DIR/pdf_extractor_web" ]; then
    echo "Found code backup, restoring..."
    rm -rf test_django/pdf_extractor_web
    cp -r "$BACKUP_DIR/pdf_extractor_web" test_django/
    echo "Code restored"
else
    echo "No code backup found, skipping code restore"
fi

# Step 2: Restore databases
echo "Restoring databases..."
echo "Restoring main database..."
docker exec -i postgres_container psql -U ${POSTGRES_USER} -d mydatabase < "$BACKUP_DIR/main_database.sql"

echo "Restoring test database..."
docker exec -i postgres_test psql -U newuser -d mydatabase < "$BACKUP_DIR/test_database.sql"

# Step 3: Restore migrations
echo "Restoring migrations..."
if [ -d "$BACKUP_DIR/migrations" ]; then
    rm -rf test_django/pdf_extractor_web/profiles/migrations
    cp -r "$BACKUP_DIR/migrations" test_django/pdf_extractor_web/profiles/
    echo "Migrations restored"
else
    echo "No migrations backup found, skipping migrations restore"
fi

# Step 4: Restore memory bank
echo "Restoring memory bank..."
if [ -d "$BACKUP_DIR/cline_docs" ]; then
    rm -rf cline_docs
    cp -r "$BACKUP_DIR/cline_docs" .
    echo "Memory bank restored"
else
    echo "No memory bank backup found, skipping memory bank restore"
fi

echo "Rollback complete!"
echo "Please restart the Django server to apply changes" 