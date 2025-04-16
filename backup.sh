#!/bin/bash

# Configuration
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Get database credentials from settings
DB_NAME=$(python -c "from pdf_extractor_web.settings import DATABASES; print(DATABASES['default']['NAME'])")
DB_USER=$(python -c "from pdf_extractor_web.settings import DATABASES; print(DATABASES['default']['USER'])")
DB_PASSWORD=$(python -c "from pdf_extractor_web.settings import DATABASES; print(DATABASES['default']['PASSWORD'])")

# Create backup directory
mkdir -p "${BACKUP_PATH}"

# 1. Database Backup
echo "Backing up database..."
PGPASSWORD="${DB_PASSWORD}" pg_dump -U "${DB_USER}" "${DB_NAME}" > "${BACKUP_PATH}/database.sql"

# 2. Migrations Backup
echo "Backing up migrations..."
cp -r pdf_extractor_web/profiles/migrations "${BACKUP_PATH}/migrations"

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
Database: ${DB_NAME}
User: ${DB_USER}
EOF

# 5. Create restore script
echo "Creating restore script..."
cat > "${BACKUP_PATH}/restore.sh" << EOF
#!/bin/bash

# Get database credentials from settings
DB_NAME=\$(python -c "from pdf_extractor_web.settings import DATABASES; print(DATABASES['default']['NAME'])")
DB_USER=\$(python -c "from pdf_extractor_web.settings import DATABASES; print(DATABASES['default']['USER'])")
DB_PASSWORD=\$(python -c "from pdf_extractor_web.settings import DATABASES; print(DATABASES['default']['PASSWORD'])")

# Restore database
echo "Restoring database..."
PGPASSWORD="\${DB_PASSWORD}" psql -U "\${DB_USER}" "\${DB_NAME}" < database.sql

# Restore migrations
echo "Restoring migrations..."
rm -rf ../pdf_extractor_web/profiles/migrations
cp -r migrations ../pdf_extractor_web/profiles/

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