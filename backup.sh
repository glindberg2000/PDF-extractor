#!/bin/bash

# Configuration
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Create backup directory
mkdir -p "${BACKUP_PATH}"

# 1. Database Backup
echo "Backing up database..."
pg_dump -U postgres pdf_extractor > "${BACKUP_PATH}/database.sql"

# 2. Migrations Backup
echo "Backing up migrations..."
cp -r profiles/migrations "${BACKUP_PATH}/migrations"

# 3. Code Snapshot
echo "Creating code snapshot..."
git add .
git commit -m "Backup snapshot ${TIMESTAMP}" --no-verify
git tag "backup_${TIMESTAMP}"

# 4. Create metadata
echo "Creating backup metadata..."
cat > "${BACKUP_PATH}/metadata.txt" << EOF
Backup created: ${TIMESTAMP}
Git commit: $(git rev-parse HEAD)
Database size: $(du -h "${BACKUP_PATH}/database.sql" | cut -f1)
Migration count: $(find "${BACKUP_PATH}/migrations" -name "*.py" | wc -l)
EOF

# 5. Create restore script
echo "Creating restore script..."
cat > "${BACKUP_PATH}/restore.sh" << 'EOF'
#!/bin/bash

# Restore database
echo "Restoring database..."
psql -U postgres pdf_extractor < database.sql

# Restore migrations
echo "Restoring migrations..."
rm -rf ../profiles/migrations
cp -r migrations ../profiles/

# Restore git state
echo "Restoring git state..."
git reset --hard HEAD
git clean -fd
git checkout backup_${TIMESTAMP}

echo "Restore complete!"
EOF

chmod +x "${BACKUP_PATH}/restore.sh"

# 6. Create backup manifest
echo "Creating backup manifest..."
cat > "${BACKUP_DIR}/manifest.txt" << EOF
${TIMESTAMP}: ${BACKUP_NAME}
EOF

echo "Backup completed successfully!"
echo "Backup location: ${BACKUP_PATH}"
echo "To restore, run: ${BACKUP_PATH}/restore.sh" 