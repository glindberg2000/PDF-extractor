#!/bin/bash

# Create backup directory with timestamp
BACKUP_DIR="backups/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Backing up main database (Port 5432)..."
docker exec postgres_container pg_dump -U ${POSTGRES_USER} -d mydatabase > "$BACKUP_DIR/main_database.sql"

echo "Backing up test database (Port 5433)..."
docker exec postgres_test pg_dump -U newuser -d mydatabase > "$BACKUP_DIR/test_database.sql"

echo "Backing up migrations..."
cp -r pdf_extractor_web/profiles/migrations "$BACKUP_DIR/"

echo "Backing up memory bank..."
cp -r cline_docs "$BACKUP_DIR/"

echo "Creating code snapshot..."
git add .
git commit -m "Backup snapshot $(date +%Y%m%d_%H%M%S)"

echo "Creating backup metadata..."
cat > "$BACKUP_DIR/metadata.txt" << EOF
Backup created: $(date)
Git commit: $(git rev-parse HEAD)
Database versions:
- Main: $(docker exec postgres_container psql -U ${POSTGRES_USER} -d mydatabase -c "SELECT version();" | tail -n 3 | head -n 1)
- Test: $(docker exec postgres_test psql -U newuser -d mydatabase -c "SELECT version();" | tail -n 3 | head -n 1)
EOF

echo "Creating restore script..."
cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash

# Restore main database
echo "Restoring main database..."
docker exec -i postgres_container psql -U ${POSTGRES_USER} -d mydatabase < main_database.sql

# Restore test database
echo "Restoring test database..."
docker exec -i postgres_test psql -U newuser -d mydatabase < test_database.sql

# Restore migrations
echo "Restoring migrations..."
cp -r migrations/* ../pdf_extractor_web/profiles/migrations/

# Restore memory bank
echo "Restoring memory bank..."
cp -r cline_docs/* ../cline_docs/

echo "Restore complete!"
EOF

chmod +x "$BACKUP_DIR/restore.sh"

echo "Backup complete! Files stored in $BACKUP_DIR" 