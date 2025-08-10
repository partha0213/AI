#!/bin/bash

set -e

# Enhanced backup script with error handling and monitoring
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_BASE_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$TIMESTAMP"
LOG_FILE="$PROJECT_DIR/logs/backup.log"
RETENTION_DAYS=30
S3_BUCKET=${S3_BACKUP_BUCKET:-""}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Error handling
handle_error() {
    log "${RED}ERROR: Backup failed at step: $1${NC}"
    # Send alert (implement your preferred alerting method)
    # curl -X POST "your-slack-webhook" -d '{"text":"Backup failed: '$1'"}'
    exit 1
}

log "${GREEN}Starting comprehensive backup process${NC}"

# Create backup directory
mkdir -p "$BACKUP_DIR" || handle_error "Creating backup directory"

# 1. Database backup with compression
log "${YELLOW}Backing up database...${NC}"
if docker-compose exec -T db pg_dump -U postgres -h localhost ai_intern_prod | gzip > "$BACKUP_DIR/database.sql.gz"; then
    log "${GREEN}✅ Database backup completed${NC}"
else
    handle_error "Database backup"
fi

# 2. Application files backup
log "${YELLOW}Backing up application files...${NC}"
if tar -czf "$BACKUP_DIR/app_files.tar.gz" -C "$PROJECT_DIR" app/ --exclude="app/__pycache__" --exclude="app/*.pyc"; then
    log "${GREEN}✅ Application files backup completed${NC}"
else
    handle_error "Application files backup"
fi

# 3. Configuration backup
log "${YELLOW}Backing up configuration...${NC}"
cp "$PROJECT_DIR/.env.production" "$BACKUP_DIR/" 2>/dev/null || log "${YELLOW}⚠️ Production env file not found${NC}"
cp "$PROJECT_DIR/docker-compose.yml" "$BACKUP_DIR/"
cp -r "$PROJECT_DIR/nginx/" "$BACKUP_DIR/" 2>/dev/null || log "${YELLOW}⚠️ Nginx config not found${NC}"

# 4. Uploaded files backup
log "${YELLOW}Backing up uploaded files...${NC}"
if [ -d "$PROJECT_DIR/uploads" ]; then
    tar -czf "$BACKUP_DIR/uploads.tar.gz" -C "$PROJECT_DIR" uploads/
    log "${GREEN}✅ Uploaded files backup completed${NC}"
else
    log "${YELLOW}⚠️ No uploads directory found${NC}"
fi

# 5. Logs backup (last 7 days)
log "${YELLOW}Backing up recent logs...${NC}"
if [ -d "$PROJECT_DIR/logs" ]; then
    find "$PROJECT_DIR/logs" -name "*.log" -mtime -7 -exec tar -czf "$BACKUP_DIR/logs.tar.gz" {} +
    log "${GREEN}✅ Logs backup completed${NC}"
else
    log "${YELLOW}⚠️ No logs directory found${NC}"
fi

# 6. Create backup manifest
cat > "$BACKUP_DIR/manifest.json" << EOF
{
    "backup_timestamp": "$TIMESTAMP",
    "backup_version": "1.0",
    "components": [
        "database",
        "application_files", 
        "configuration",
        "uploads",
        "logs"
    ],
    "retention_days": $RETENTION_DAYS,
    "created_by": "enhanced-backup.sh"
}
EOF

# 7. Calculate backup size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "${GREEN}✅ Backup completed successfully - Size: $BACKUP_SIZE${NC}"

# 8. Upload to S3 if configured
if [ ! -z "$S3_BUCKET" ]; then
    log "${YELLOW}Uploading backup to S3...${NC}"
    if aws s3 sync "$BACKUP_DIR" "s3://$S3_BUCKET/backups/$TIMESTAMP/" --delete; then
        log "${GREEN}✅ S3 upload completed${NC}"
    else
        log "${RED}❌ S3 upload failed${NC}"
    fi
fi

# 9. Clean old backups
log "${YELLOW}Cleaning old backups (older than $RETENTION_DAYS days)...${NC}"
find "$BACKUP_BASE_DIR" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true
log "${GREEN}✅ Old backups cleaned${NC}"

# 10. Send success notification
log "${GREEN}🎉 Backup process completed successfully!${NC}"
log "Backup location: $BACKUP_DIR"
log "Backup size: $BACKUP_SIZE"

# Optional: Send success notification to monitoring system
# curl -X POST "your-monitoring-endpoint" -d '{"status":"success","backup_size":"'$BACKUP_SIZE'"}'
