#!/bin/bash

# SIMBA Database Backup Script
# Creates automated backups of the PostgreSQL database

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="../backups"
LOG_FILE="../logs/backup.log"
DB_CONTAINER="simba-2025-db-1"
MAX_BACKUPS=30

mkdir -p $BACKUP_DIR
mkdir -p ../logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

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

print_step "Starting database backup..."

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/simba_backup_$TIMESTAMP.sql"

if ! docker ps | grep -q $DB_CONTAINER; then
    print_error "Database container $DB_CONTAINER is not running"
    exit 1
fi

print_step "Creating database backup..."

docker exec $DB_CONTAINER pg_dump -U simba_user -d simba_db > $BACKUP_FILE

if [ $? -eq 0 ]; then
    gzip $BACKUP_FILE
    COMPRESSED_FILE="${BACKUP_FILE}.gz"
    
    FILE_SIZE=$(ls -lh $COMPRESSED_FILE | awk '{print $5}')
    
    print_success "Database backup created: $(basename $COMPRESSED_FILE) ($FILE_SIZE)"
    
    print_step "Cleaning up old backups (keeping last $MAX_BACKUPS)..."
    
    cd $BACKUP_DIR
    ls -t simba_backup_*.sql.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm
    
    REMAINING_BACKUPS=$(ls simba_backup_*.sql.gz 2>/dev/null | wc -l)
    print_success "Cleanup completed. $REMAINING_BACKUPS backups remaining."

    cd - > /dev/null
    ln -sf $(basename $COMPRESSED_FILE) $BACKUP_DIR/latest_backup.sql.gz
    
    log "Backup completed successfully: $COMPRESSED_FILE"
    
else
    print_error "Database backup failed"
    rm -f $BACKUP_FILE
    exit 1
fi

print_success "Backup process completed successfully!" 