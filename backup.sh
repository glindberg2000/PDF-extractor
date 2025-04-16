#!/bin/bash

# Configuration
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Database configuration (update these values)
DB_NAME="pdf_extractor"
DB_USER="greg"
DB_PASSWORD=""

# Create backup directory
mkdir -p "${BACKUP_PATH}"

# 1. Database Backup
echo "Backing up database..."
if [ -n "$DB_PASSWORD" ]; then
    PGPASSWORD="${DB_PASSWORD}" pg_dump -U "${DB_USER}" "${DB_NAME}" > "${BACKUP_PATH}/database.sql"
else
    pg_dump -U "${DB_USER}" "${DB_NAME}" > "${BACKUP_PATH}/database.sql"
fi

# 2. Migrations Backup
echo "Backing up migrations..."
cp -r pdf_extractor_web/profiles/migrations "${BACKUP_PATH}/migrations"

# 3. Memory Bank Backup
echo "Backing up memory bank..."
cp -r cline_docs "${BACKUP_PATH}/cline_docs"

# 4. Code Snapshot
echo "Creating code snapshot..."
git add .
git commit -m "Backup snapshot ${TIMESTAMP}" --no-verify
git tag "backup_${TIMESTAMP}"

# 5. Create metadata
echo "Creating backup metadata..."
cat > "${BACKUP_PATH}/metadata.txt" << EOF
Backup created: ${TIMESTAMP}
Git commit: $(git rev-parse HEAD)
Database size: $(du -h "${BACKUP_PATH}/database.sql" | cut -f1)
Migration count: $(find "${BACKUP_PATH}/migrations" -name "*.py" | wc -l)
Database: ${DB_NAME}
User: ${DB_USER}
Memory Bank: cline_docs
EOF

# 6. Create restore script
echo "Creating restore script..."
cat > "${BACKUP_PATH}/restore.sh" << EOF
#!/bin/bash

# Database configuration (update these values)
DB_NAME="pdf_extractor"
DB_USER="greg"
DB_PASSWORD=""

# Restore database
echo "Restoring database..."
if [ -n "\$DB_PASSWORD" ]; then
    PGPASSWORD="\${DB_PASSWORD}" psql -U "\${DB_USER}" "\${DB_NAME}" < database.sql
else
    psql -U "\${DB_USER}" "\${DB_NAME}" < database.sql
fi

# Restore migrations
echo "Restoring migrations..."
rm -rf ../pdf_extractor_web/profiles/migrations
cp -r migrations ../pdf_extractor_web/profiles/

# Restore memory bank
echo "Restoring memory bank..."
rm -rf ../cline_docs/*
cp -r cline_docs/* ../cline_docs/

# Restore git state
echo "Restoring git state..."
git reset --hard HEAD
git clean -fd
git checkout backup_${TIMESTAMP}

echo "Restore complete!"
EOF

chmod +x "${BACKUP_PATH}/restore.sh"

# 7. Create backup manifest
echo "Creating backup manifest..."
cat > "${BACKUP_DIR}/manifest.txt" << EOF
${TIMESTAMP}: ${BACKUP_NAME}
EOF

echo "Backup completed successfully!"
echo "Backup location: ${BACKUP_PATH}"
echo "To restore, run: ${BACKUP_PATH}/restore.sh" 