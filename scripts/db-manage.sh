# scripts/db-manage.sh
#!/bin/bash

set -e

COMMAND=$1
shift

case $COMMAND in
    "init")
        echo "🏗️ Initializing database..."
        docker-compose up -d db
        sleep 10
        docker-compose exec api alembic upgrade head
        echo "✅ Database initialized"
        ;;
    "migrate")
        echo "🔄 Running migrations..."
        ./scripts/migrate.sh upgrade $@
        ;;
    "rollback")
        STEPS=${1:-1}
        echo "⏪ Rolling back $STEPS migration(s)..."
        ./scripts/migrate.sh downgrade -$STEPS
        ;;
    "seed")
        echo "🌱 Seeding database with sample data..."
        docker-compose exec api python scripts/seed_data.py
        ;;
    "backup")
        echo "💾 Creating database backup..."
        ./scripts/backup.sh
        ;;
    "status")
        echo "📊 Database status:"
        ./scripts/migrate.sh current
        ./scripts/migrate.sh history --verbose
        ;;
    *)
        echo "Available commands:"
        echo "  init     - Initialize database with migrations"
        echo "  migrate  - Run pending migrations"
        echo "  rollback [steps] - Rollback migrations (default: 1)"
        echo "  seed     - Seed database with sample data"
        echo "  backup   - Create database backup"
        echo "  status   - Show migration status"
        ;;
esac
