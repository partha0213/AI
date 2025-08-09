#!/bin/bash

set -e

echo "⚠️  WARNING: This will completely reset the database!"
echo "📊 All data will be lost!"
read -p "Are you sure? (type 'yes' to continue): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Operation cancelled"
    exit 1
fi

echo "🗑️ Resetting database..."

# Stop all services
docker-compose down

# Remove database volume
docker volume rm ai-virtual-intern-backend_postgres_data 2>/dev/null || true

# Start database
docker-compose up -d db
sleep 10

# Run migrations
docker-compose exec api alembic upgrade head

echo "✅ Database reset completed"
echo "🏃 Starting all services..."
docker-compose up -d
