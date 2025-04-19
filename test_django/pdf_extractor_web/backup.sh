#!/bin/bash

# Backup script for PDF Extractor Django project
# This script creates a complete backup of the database and migrations
# Includes verification steps to ensure backup integrity

# Configuration
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_PATH"

echo "Starting backup process at $(date)"

# Verify PostgreSQL is running
if ! pg_isready -h localhost -p 5432; then
    echo "Error: PostgreSQL is not running on port 5432"
    exit 1
fi

# Backup the database
echo "Backing up database..."
pg_dump -h localhost -p 5432 -U newuser -d mydatabase -F c -f "$BACKUP_PATH/database.dump"

# Verify database backup
if [ ! -f "$BACKUP_PATH/database.dump" ]; then
    echo "Error: Database backup failed"
    exit 1
fi

# Backup migrations
echo "Backing up migrations..."
cp -r profiles/migrations "$BACKUP_PATH/"

# Verify migrations backup
if [ ! -d "$BACKUP_PATH/migrations" ]; then
    echo "Error: Migrations backup failed"
    exit 1
fi

# Create metadata file
echo "Creating metadata..."
cat > "$BACKUP_PATH/metadata.json" << EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "database": {
        "name": "mydatabase",
        "host": "localhost",
        "port": 5432,
        "user": "newuser"
    },
    "migrations": {
        "path": "profiles/migrations",
        "count": $(find profiles/migrations -type f -name "*.py" | wc -l)
    },
    "directory_structure": {
        "type": "flattened",
        "settings_path": "settings.py",
        "wsgi_path": "wsgi.py"
    }
}
EOF

# Create git snapshot
echo "Creating git snapshot..."
git rev-parse HEAD > "$BACKUP_PATH/git_commit.txt"
git status >> "$BACKUP_PATH/git_status.txt"

echo "Backup completed successfully at $(date)"
echo "Backup location: $BACKUP_PATH"
echo "Contents:"
ls -la "$BACKUP_PATH" 