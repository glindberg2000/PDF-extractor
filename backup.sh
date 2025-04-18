#!/bin/bash

# Configuration
BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Database configurations
MAIN_DB_NAME="mydatabase"
MAIN_DB_USER="newuser"
MAIN_DB_PASSWORD=""
MAIN_PORT="8001"

TEST_DB_NAME="test_database"
TEST_DB_USER="newuser"
TEST_DB_PASSWORD=""
TEST_PORT="8000"

# Create backup directory
mkdir -p "${BACKUP_PATH}"

# 1. Main Database Backup (Port 8001)
echo "Backing up main database (Port ${MAIN_PORT})..."
if [ -n "$MAIN_DB_PASSWORD" ]; then
    PGPASSWORD="${MAIN_DB_PASSWORD}" pg_dump -U "${MAIN_DB_USER}" "${MAIN_DB_NAME}" > "${BACKUP_PATH}/main_database.sql"
else
    pg_dump -U "${MAIN_DB_USER}" "${MAIN_DB_NAME}" > "${BACKUP_PATH}/main_database.sql"
fi

# 2. Test Database Backup (Port 8000)
echo "Backing up test database (Port ${TEST_PORT})..."
if [ -n "$TEST_DB_PASSWORD" ]; then
    PGPASSWORD="${TEST_DB_PASSWORD}" pg_dump -U "${TEST_DB_USER}" "${TEST_DB_NAME}" > "${BACKUP_PATH}/test_database.sql"
else
    pg_dump -U "${TEST_DB_USER}" "${TEST_DB_NAME}" > "${BACKUP_PATH}/test_database.sql"
fi

# 3. Migrations Backup (both versions)
echo "Backing up migrations..."
mkdir -p "${BACKUP_PATH}/migrations"
cp -r pdf_extractor_web/profiles/migrations/* "${BACKUP_PATH}/migrations/"
cp -r test_django/pdf_extractor_web/profiles/migrations/* "${BACKUP_PATH}/migrations/"

# 4. Memory Bank Backup
echo "Backing up memory bank..."
cp -r cline_docs "${BACKUP_PATH}/cline_docs"

# 5. Code Snapshot
echo "Creating code snapshot..."
git add .
git commit -m "Backup snapshot ${TIMESTAMP}" --no-verify
git tag "backup_${TIMESTAMP}"

# 6. Create metadata
echo "Creating backup metadata..."
cat > "${BACKUP_PATH}/metadata.txt" << EOF
Backup created: ${TIMESTAMP}
Git commit: $(git rev-parse HEAD)

Main Instance (Port ${MAIN_PORT}):
Database: ${MAIN_DB_NAME}
User: ${MAIN_DB_USER}
Database size: $(du -h "${BACKUP_PATH}/main_database.sql" | cut -f1)

Test Instance (Port ${TEST_PORT}):
Database: ${TEST_DB_NAME}
User: ${TEST_DB_USER}
Database size: $(du -h "${BACKUP_PATH}/test_database.sql" | cut -f1)

Migration count: $(find "${BACKUP_PATH}/migrations" -name "*.py" | wc -l)
Memory Bank: cline_docs
EOF

# 7. Create restore script
echo "Creating restore script..."
cat > "${BACKUP_PATH}/restore.sh" << EOF
#!/bin/bash

# Restore main database
echo "Restoring main database..."
if [ -n "$MAIN_DB_PASSWORD" ]; then
    PGPASSWORD="${MAIN_DB_PASSWORD}" psql -U "${MAIN_DB_USER}" "${MAIN_DB_NAME}" < main_database.sql
else
    psql -U "${MAIN_DB_USER}" "${MAIN_DB_NAME}" < main_database.sql
fi

# Restore test database
echo "Restoring test database..."
if [ -n "$TEST_DB_PASSWORD" ]; then
    PGPASSWORD="${TEST_DB_PASSWORD}" psql -U "${TEST_DB_USER}" "${TEST_DB_NAME}" < test_database.sql
else
    psql -U "${TEST_DB_USER}" "${TEST_DB_NAME}" < test_database.sql
fi

# Restore migrations
echo "Restoring migrations..."
cp -r migrations/* pdf_extractor_web/profiles/migrations/
cp -r migrations/* test_django/pdf_extractor_web/profiles/migrations/

# Restore memory bank
echo "Restoring memory bank..."
cp -r cline_docs/* ../cline_docs/

echo "Restore complete!"
EOF

chmod +x "${BACKUP_PATH}/restore.sh"

echo "Backup complete! Files stored in ${BACKUP_PATH}" 