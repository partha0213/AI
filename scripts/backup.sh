#!/bin/bash

set -e

# Configuration
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
RETENTION_DAYS=30
S3_BUCKET=${S3_BACKUP_BUCKET:-""}

echo "🗃️ Starting backup process"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
echo "📊 Backing up database..."
docker-compose exec -T db pg_dump -U postgres -h localhost ai_intern_prod | gzip > $BACKUP_DIR/database.sql.gz

# Files backup
echo "📁 Backing up uploaded files..."
if [ -d "./uploads" ]; then
    tar -czf $BACKUP_DIR/uploads.tar.gz ./uploads
fi

# Configuration backup
echo "⚙️ Backing up configuration..."
cp .env.production $BACKUP_DIR/
cp docker-compose.yml $BACKUP_DIR/
cp -r nginx/ $BACKUP_DIR/ 2>/dev/null || true

# Logs backup
echo "📋 Backing up logs..."
if [ -d "./logs" ]; then
    tar -czf $BACKUP_DIR/logs.tar.gz ./logs
fi

# Upload to S3 if configured
if [ ! -z "$S3_BUCKET" ]; then
    echo "☁️ Uploading backup to S3..."
    aws s3 sync $BACKUP_DIR s3://$S3_BUCKET/backups/$(basename $BACKUP_DIR)/
fi

# Clean old backups
echo "🧹 Cleaning old backups..."
find ./backups -type d -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true

echo "✅ Backup completed: $BACKUP_DIR"
