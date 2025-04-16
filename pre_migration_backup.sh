#!/bin/bash

# Run the main backup script
./backup.sh

# Create a special migration backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MIGRATION_BACKUP_DIR="backups/migration_backups/pre_${TIMESTAMP}"

# Copy current migration state
mkdir -p "${MIGRATION_BACKUP_DIR}"
cp -r pdf_extractor_web/profiles/migrations/* "${MIGRATION_BACKUP_DIR}/"

# Create migration-specific restore script
cat > "${MIGRATION_BACKUP_DIR}/restore_migrations.sh" << 'EOF'
#!/bin/bash

# Restore migrations
echo "Restoring migrations..."
rm -rf ../../pdf_extractor_web/profiles/migrations
cp -r . ../../pdf_extractor_web/profiles/migrations/

# Reset Django migration state
echo "Resetting Django migration state..."
cd ../../pdf_extractor_web
python manage.py migrate profiles zero --fake
cd ../..

echo "Migration restore complete!"
EOF

chmod +x "${MIGRATION_BACKUP_DIR}/restore_migrations.sh"

echo "Pre-migration backup created at: ${MIGRATION_BACKUP_DIR}" 