#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/^[A-Z]/ {print}')
else
    echo "Error: .env file not found!"
    exit 1
fi

# Directory for backups
BACKUP_DIR="/Users/greg/iCloud Drive (Archive)/repos/PDF-extractor/backups"
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
TEMP_ERROR_LOG="/tmp/pg_dump_error.log"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create the backup with error logging
echo "Creating backup..."
docker exec postgres_container pg_dump -U newuser mydatabase > "$BACKUP_DIR/$BACKUP_FILE" 2> "$TEMP_ERROR_LOG"

# Check if backup was successful and not empty
if [ $? -eq 0 ] && [ -s "$BACKUP_DIR/$BACKUP_FILE" ]; then
    echo "Backup created successfully: $BACKUP_FILE"
    echo "Backup size: $(ls -lh "$BACKUP_DIR/$BACKUP_FILE" | awk '{print $5}')"
    
    # Keep only the 5 most recent backups
    cd "$BACKUP_DIR"
    ls -t *.sql | tail -n +6 | xargs -I {} rm -- {}
    
    echo "Cleaned up old backups. Keeping 5 most recent."
else
    echo "Backup failed!"
    if [ -f "$TEMP_ERROR_LOG" ]; then
        echo "Error details:"
        cat "$TEMP_ERROR_LOG"
    fi
    rm -f "$BACKUP_DIR/$BACKUP_FILE"  # Remove failed backup file
fi

# Clean up
rm -f "$TEMP_ERROR_LOG" 