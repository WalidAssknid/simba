#!/bin/bash

# SIMBA Database Restore Script
# Restores database from backup files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="../backups"
LOG_FILE="../logs/restore.log"
DB_CONTAINER="simba-2025-db-1"

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

# Function to print colored messages
print_step() {
    echo -e "${BLUE}📋 $1${NC}"
    log "STEP: $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR: $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    log "WARNING: $1"
}

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -la $BACKUP_DIR/simba_backup_*.sql.gz 2>/dev/null || echo "No backups found"
    echo ""
    echo "Use 'latest' to restore from the most recent backup:"
    echo "  $0 latest"
    exit 1
fi

# Handle 'latest' keyword
if [ "$1" = "latest" ]; then
    BACKUP_FILE="$BACKUP_DIR/latest_backup.sql.gz"
    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "Latest backup not found"
        exit 1
    fi
else
    BACKUP_FILE="$1"
    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
fi

print_step "Starting database restore from: $(basename $BACKUP_FILE)"

# Check if database container is running
if ! docker ps | grep -q $DB_CONTAINER; then
    print_error "Database container $DB_CONTAINER is not running"
    exit 1
fi

# Warning about data loss
print_warning "⚠️  WARNING: This will COMPLETELY REPLACE the current database!"
print_warning "All current data will be lost. Make sure you have a recent backup."
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a backup of current database before restore
print_step "Creating backup of current database before restore..."
../scripts/backup.sh
print_success "Current database backed up"

# Decompress backup if needed
TEMP_SQL_FILE="/tmp/restore_temp.sql"
if [[ $BACKUP_FILE == *.gz ]]; then
    print_step "Decompressing backup file..."
    zcat $BACKUP_FILE > $TEMP_SQL_FILE
else
    cp $BACKUP_FILE $TEMP_SQL_FILE
fi

# Stop application containers to prevent connections
print_step "Stopping application containers..."
docker-compose stop web chainlit || true

# Drop and recreate database
print_step "Dropping and recreating database..."
docker exec $DB_CONTAINER psql -U simba_user -d postgres -c "DROP DATABASE IF EXISTS simba_db;"
docker exec $DB_CONTAINER psql -U simba_user -d postgres -c "CREATE DATABASE simba_db;"

# Restore database
print_step "Restoring database from backup..."
docker exec -i $DB_CONTAINER psql -U simba_user -d simba_db < $TEMP_SQL_FILE

if [ $? -eq 0 ]; then
    print_success "Database restored successfully"
    
    # Clean up temporary file
    rm -f $TEMP_SQL_FILE
    
    # Restart application containers
    print_step "Restarting application containers..."
    docker-compose start web chainlit
    
    # Wait for services to be ready
    print_step "Waiting for services to be ready..."
    sleep 10
    
    # Health check
    if curl -f http://localhost:8000 > /dev/null 2>&1; then
        print_success "Application is responding after restore"
    else
        print_warning "Application might not be ready yet. Check logs: docker-compose logs"
    fi
    
    print_success "Database restore completed successfully!"
    
else
    print_error "Database restore failed"
    rm -f $TEMP_SQL_FILE
    
    # Restart containers anyway
    docker-compose start web chainlit
    exit 1
fi 