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

# Function to check database connectivity
check_db_connection() {
    local container=$1
    local user=$2
    if ! docker exec $container psql -U $user -d mydatabase -c "SELECT 1;" >/dev/null 2>&1; then
        echo "Error: Cannot connect to database in $container"
        return 1
    fi
    return 0
}

# Function to verify backup file
verify_backup() {
    local file=$1
    if [ ! -f "$file" ]; then
        echo "Error: Backup file $file not found"
        return 1
    fi
    # Check if file is a valid SQL dump
    if ! head -n 1 "$file" | grep -q "PostgreSQL database dump"; then
        echo "Error: $file does not appear to be a valid PostgreSQL dump"
        return 1
    fi
    return 0
}

# Function to restore main database
restore_main() {
    echo "Preparing to restore main database..."
    
    # Verify backup file
    if ! verify_backup "main_database.sql"; then
        return 1
    fi
    
    # Check database connection
    if ! check_db_connection "postgres_container" "${POSTGRES_USER}"; then
        return 1
    }
    
    echo "Creating temporary backup of current main database..."
    docker exec postgres_container pg_dump -U ${POSTGRES_USER} -d mydatabase > "pre_restore_main_$(date +%Y%m%d_%H%M%S).sql"
    
    echo "Restoring main database..."
    if docker exec -i postgres_container psql -U ${POSTGRES_USER} -d mydatabase < main_database.sql; then
        echo "Main database restored successfully!"
        return 0
    else
        echo "Error: Failed to restore main database"
        return 1
    fi
}

# Function to restore test database
restore_test() {
    echo "Preparing to restore test database..."
    
    # Verify backup file
    if ! verify_backup "test_database.sql"; then
        return 1
    }
    
    # Check database connection
    if ! check_db_connection "postgres_test" "newuser"; then
        return 1
    }
    
    echo "Creating temporary backup of current test database..."
    docker exec postgres_test pg_dump -U newuser -d mydatabase > "pre_restore_test_$(date +%Y%m%d_%H%M%S).sql"
    
    echo "Restoring test database..."
    if docker exec -i postgres_test psql -U newuser -d mydatabase < test_database.sql; then
        echo "Test database restored successfully!"
        return 0
    else
        echo "Error: Failed to restore test database"
        return 1
    fi
}

# Function to restore migrations
restore_migrations() {
    echo "Restoring migrations..."
    if [ ! -d "migrations" ]; then
        echo "Error: migrations directory not found"
        return 1
    fi
    cp -r migrations/* ../pdf_extractor_web/profiles/migrations/
    echo "Migrations restored!"
}

# Function to restore memory bank
restore_memory_bank() {
    echo "Restoring memory bank..."
    if [ ! -d "cline_docs" ]; then
        echo "Error: cline_docs directory not found"
        return 1
    fi
    cp -r cline_docs/* ../cline_docs/
    echo "Memory bank restored!"
}

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [--main] [--test] [--migrations] [--memory-bank]"
    echo "Options:"
    echo "  --main         Restore main database"
    echo "  --test         Restore test database"
    echo "  --migrations   Restore migrations"
    echo "  --memory-bank  Restore memory bank"
    exit 1
fi

# Process command line arguments
RESTORE_MAIN=0
RESTORE_TEST=0
RESTORE_MIGRATIONS=0
RESTORE_MEMORY_BANK=0

for arg in "$@"; do
    case $arg in
        --main)
            RESTORE_MAIN=1
            ;;
        --test)
            RESTORE_TEST=1
            ;;
        --migrations)
            RESTORE_MIGRATIONS=1
            ;;
        --memory-bank)
            RESTORE_MEMORY_BANK=1
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

# Perform selected restore operations
if [ $RESTORE_MAIN -eq 1 ]; then
    restore_main
fi

if [ $RESTORE_TEST -eq 1 ]; then
    restore_test
fi

if [ $RESTORE_MIGRATIONS -eq 1 ]; then
    restore_migrations
fi

if [ $RESTORE_MEMORY_BANK -eq 1 ]; then
    restore_memory_bank
fi

echo "Restore operations completed!"
EOF

chmod +x "$BACKUP_DIR/restore.sh"

echo "Backup complete! Files stored in $BACKUP_DIR" 