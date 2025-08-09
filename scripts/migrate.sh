#!/bin/bash

set -e

COMMAND=${1:-"upgrade"}
TARGET=${2:-"head"}

echo "🗄️ Running database migration: $COMMAND $TARGET"

# Check if we're in Docker environment
if [ -f "docker-compose.yml" ]; then
    echo "📦 Using Docker environment..."
    
    # Make sure database is running
    docker-compose up -d db
    sleep 5
    
    # Run migration
    case $COMMAND in
        "upgrade")
            docker-compose exec api alembic upgrade $TARGET
            ;;
        "downgrade")
            docker-compose exec api alembic downgrade $TARGET
            ;;
        "current")
            docker-compose exec api alembic current
            ;;
        "history")
            docker-compose exec api alembic history
            ;;
        "show")
            docker-compose exec api alembic show $TARGET
            ;;
        *)
            echo "❌ Unknown command: $COMMAND"
            echo "Available commands: upgrade, downgrade, current, history, show"
            exit 1
            ;;
    esac
else
    echo "🐍 Using local environment..."
    alembic $COMMAND $TARGET
fi

echo "✅ Migration completed successfully"
