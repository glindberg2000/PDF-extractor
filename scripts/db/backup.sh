#!/bin/bash

# Backup script for PDF Extractor Django project
# Version: 2.0.0
# Last Updated: 2025-04-19
#
# This script creates a complete backup of:
# 1. PostgreSQL databases (both main and test instances)
# 2. Django project files and migrations
# 3. Git state
#
# Backup Location:
# - All backups are stored in /Users/greg/iCloud Drive (Archive)/repos/PDF-extractor/backups/
# - Each backup is in a timestamped directory (e.g., backup_20250419_004856/)
#
# Backup Structure:
# Each backup directory contains:
# - database_main.dump: Main database backup (port 5432)
# - database_test.dump: Test database backup (port 5433)
# - main_instance/: Django project files and migrations
# - metadata.json: Backup metadata including timestamps and counts
# - git_commit.txt: Current git commit hash
# - git_status.txt: Working directory status
#
# Database Backup Process:
# - Uses docker exec to run pg_dump inside the containers
# - Writes dumps to local filesystem
# - Verifies container status before backup
#
# Usage:
# ./backup.sh backup    # Create a new backup
# ./backup.sh restore <backup_path>  # Restore from backup
#
# Dependencies:
# - Docker containers must be running
# - PostgreSQL client tools in containers
# - Git for version control
#
# Safety Features:
# - Verifies container status before operations
# - Creates metadata for verification
# - Maintains separate backup directories
# - Includes git state for reproducibility

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
BACKUP_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

# Use environment variables for database configuration
DB_USER=${DB_USER:-"newuser"}
DB_PASSWORD=${DB_PASSWORD:-"newpassword"}
DB_NAME=${DB_NAME:-"mydatabase"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT_MAIN=${DB_PORT_MAIN:-"5432"}
DB_PORT_TEST=${DB_PORT_TEST:-"5433"}

# Export password for PostgreSQL commands
export PGPASSWORD=$DB_PASSWORD

# Function to get container name
get_container_name() {
    local instance=$1
    if [ "$instance" = "main" ]; then
        echo "postgres_container"
    else
        echo "postgres_test"
    fi
}

# Function to verify PostgreSQL connection
verify_postgres() {
    local port=$1
    local instance=$2
    local container_name=$(get_container_name $instance)
    
    if ! docker ps | grep -q "$container_name"; then
        echo "Error: PostgreSQL container $container_name is not running"
        return 1
    fi
    return 0
}

# Function to backup database
backup_database() {
    local port=$1
    local instance=$2
    local container_name=$(get_container_name $instance)
    local backup_file="$BACKUP_PATH/database_${instance}.dump"
    
    echo "Backing up database on port $port ($instance)..."
    
    # Use docker exec to run pg_dump inside the container
    docker exec $container_name pg_dump -U $DB_USER -d $DB_NAME -F c > "$backup_file"
    
    if [ ! -f "$backup_file" ]; then
        echo "Error: Database backup failed for port $port"
        return 1
    fi
    return 0
}

# Function to restore database
restore_database() {
    local port=$1
    local instance=$2
    local container_name=$(get_container_name $instance)
    local backup_file="$BACKUP_PATH/database_${instance}.dump"
    
    if [ ! -f "$backup_file" ]; then
        echo "Error: Backup file not found for $instance"
        return 1
    fi
    
    echo "Restoring database on port $port ($instance)..."
    # Use docker exec to run pg_restore inside the container
    docker exec -i $container_name pg_restore -U $DB_USER -d $DB_NAME -c < "$backup_file"
    return $?
}

# Function to backup Django instance
backup_django_instance() {
    local instance_path=$1
    local instance_name=$2
    
    echo "Backing up Django instance: $instance_name"
    mkdir -p "$BACKUP_PATH/$instance_name"
    
    cd "$PROJECT_ROOT"
    
    # Backup migrations
    if [ -d "$instance_path/profiles/migrations" ]; then
        echo "Backing up migrations..."
        cp -r "$instance_path/profiles/migrations" "$BACKUP_PATH/$instance_name/"
    else
        echo "Warning: No migrations found in $instance_path/profiles/migrations"
    fi
    
    # Backup core files
    echo "Backing up core files..."
    for file in settings.py wsgi.py urls.py manage.py; do
        if [ -f "$instance_path/$file" ]; then
            cp "$instance_path/$file" "$BACKUP_PATH/$instance_name/"
        else
            echo "Warning: $file not found in $instance_path"
        fi
    done
}

# Function to restore Django instance
restore_django_instance() {
    local instance_path=$1
    local instance_name=$2
    
    if [ ! -d "$BACKUP_PATH/$instance_name" ]; then
        echo "Error: Backup not found for instance $instance_name"
        return 1
    fi
    
    echo "Restoring Django instance: $instance_name"
    cd "$PROJECT_ROOT"
    
    # Restore migrations
    if [ -d "$BACKUP_PATH/$instance_name/migrations" ]; then
        echo "Restoring migrations..."
        rm -rf "$instance_path/profiles/migrations"
        cp -r "$BACKUP_PATH/$instance_name/migrations" "$instance_path/profiles/"
    fi
    
    # Restore core files
    echo "Restoring core files..."
    for file in settings.py wsgi.py urls.py manage.py; do
        if [ -f "$BACKUP_PATH/$instance_name/$file" ]; then
            cp "$BACKUP_PATH/$instance_name/$file" "$instance_path/"
        fi
    done
}

# Main backup function
backup() {
    # Create backup directory
    mkdir -p "$BACKUP_PATH"
    echo "Starting backup process at $(date)"
    cd "$PROJECT_ROOT"

    # Backup PostgreSQL databases
    if verify_postgres $DB_PORT_MAIN "main"; then
        backup_database $DB_PORT_MAIN "main"
    fi
    
    if verify_postgres $DB_PORT_TEST "test"; then
        backup_database $DB_PORT_TEST "test"
    fi

    # Backup Django instances
    backup_django_instance "test_django/pdf_extractor_web" "main_instance"
    if [ -d "test_django/pdf_extractor_web_test" ]; then
        backup_django_instance "test_django/pdf_extractor_web_test" "test_instance"
    fi

    # Create metadata file
    echo "Creating metadata..."
    cat > "$BACKUP_PATH/metadata.json" << EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "databases": [
        {
            "name": "$DB_NAME",
            "host": "$DB_HOST",
            "port": $DB_PORT_MAIN,
            "user": "$DB_USER",
            "instance": "main"
        },
        {
            "name": "$DB_NAME",
            "host": "$DB_HOST",
            "port": $DB_PORT_TEST,
            "user": "$DB_USER",
            "instance": "test"
        }
    ],
    "django_instances": [
        {
            "name": "main_instance",
            "path": "test_django/pdf_extractor_web",
            "migrations_count": $(find test_django/pdf_extractor_web/profiles/migrations -type f -name "*.py" 2>/dev/null | wc -l || echo 0)
        }
    ],
    "environment": "development",
    "backup_script_version": "2.0.0"
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
}

# Main restore function
restore() {
    local backup_path=$1
    BACKUP_PATH=$backup_path
    
    if [ ! -d "$backup_path" ]; then
        echo "Error: Backup directory not found: $backup_path"
        exit 1
    fi
    
    echo "Starting restore process from $backup_path"
    cd "$PROJECT_ROOT"
    
    # Restore PostgreSQL databases
    if verify_postgres $DB_PORT_MAIN "main"; then
        restore_database $DB_PORT_MAIN "main"
    fi
    
    if verify_postgres $DB_PORT_TEST "test"; then
        restore_database $DB_PORT_TEST "test"
    fi
    
    # Restore Django instances
    restore_django_instance "test_django/pdf_extractor_web" "main_instance"
    if [ -d "test_django/pdf_extractor_web_test" ]; then
        restore_django_instance "test_django/pdf_extractor_web_test" "test_instance"
    fi
    
    echo "Restore completed successfully"
}

# Parse command line arguments
case "$1" in
    backup)
        backup
        ;;
    restore)
        if [ -z "$2" ]; then
            echo "Usage: $0 restore <backup_path>"
            exit 1
        fi
        restore "$2"
        ;;
    *)
        echo "Usage: $0 {backup|restore <backup_path>}"
        exit 1
        ;;
esac 