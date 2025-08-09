#!/bin/bash

set -e

BACKUP_PATH=$1

if [ -z "$BACKUP_PATH" ]; then
    echo "Usage: $0 <backup_path>"
    echo "Available backups:"
    ls -la ./backups/
    exit 1
fi

if [ ! -d "$BACKUP_PATH" ]; then
    echo "❌ Backup directory not found: $BACKUP_PATH"
    exit 1
fi

echo "🔄 Restoring from backup: $BACKUP_PATH"

# Stop services
echo "🛑 Stopping services..."
docker-compose down

# Restore database
if [ -f "$BACKUP_PATH/database.sql.gz" ]; then
    echo "📊 Restoring database..."
    
    # Start only database
    docker-compose up -d db
    sleep 10
    
    # Drop and recreate database
    docker-compose exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS ai_intern_prod;"
    docker-compose exec -T db psql -U postgres -c "CREATE DATABASE ai_intern_prod;"
    
    # Restore data
    gunzip -c $BACKUP_PATH/database.sql.gz | docker-compose exec -T db psql -U postgres -d ai_intern_prod
fi

# Restore files
if [ -f "$BACKUP_PATH/uploads.tar.gz" ]; then
    echo "📁 Restoring uploaded files..."
    rm -rf ./uploads
    tar -xzf $BACKUP_PATH/uploads.tar.gz
fi

# Restore configuration
if [ -f "$BACKUP_PATH/.env.production" ]; then
    echo "⚙️ Restoring configuration..."
    cp $BACKUP_PATH/.env.production ./
fi

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d

echo "✅ Restore completed"
