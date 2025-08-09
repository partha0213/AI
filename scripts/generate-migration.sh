#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <migration_message>"
    echo "Example: $0 'Add user authentication tables'"
    exit 1
fi

MESSAGE="$1"

echo "🔄 Generating new migration: $MESSAGE"

# Check if we're in Docker environment
if [ -f "docker-compose.yml" ]; then
    echo "📦 Using Docker environment..."
    docker-compose exec api alembic revision --autogenerate -m "$MESSAGE"
else
    echo "🐍 Using local environment..."
    alembic revision --autogenerate -m "$MESSAGE"
fi

echo "✅ Migration generated successfully"
echo "📝 Don't forget to review the generated migration file before applying!"
