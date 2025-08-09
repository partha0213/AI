#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"

echo -e "${GREEN}🚀 Starting deployment for $ENVIRONMENT environment${NC}"

# Check if required files exist
if [ ! -f ".env.$ENVIRONMENT" ]; then
    echo -e "${RED}❌ Environment file .env.$ENVIRONMENT not found${NC}"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ docker-compose.yml not found${NC}"
    exit 1
fi

# Create backup directory
echo -e "${YELLOW}📦 Creating backup directory${NC}"
mkdir -p $BACKUP_DIR

# Backup database if running
if docker-compose ps | grep -q "ai_intern_db"; then
    echo -e "${YELLOW}🗃️ Backing up database${NC}"
    docker-compose exec -T db pg_dump -U postgres ai_intern_prod > $BACKUP_DIR/database_backup.sql
fi

# Backup uploaded files
if [ -d "./uploads" ]; then
    echo -e "${YELLOW}📁 Backing up uploaded files${NC}"
    cp -r ./uploads $BACKUP_DIR/
fi

# Load environment variables
echo -e "${YELLOW}🔧 Loading environment variables${NC}"
set -a
source .env.$ENVIRONMENT
set +a

# Build and deploy
echo -e "${YELLOW}🏗️ Building Docker images${NC}"
docker-compose build --no-cache

echo -e "${YELLOW}🔄 Stopping existing containers${NC}"
docker-compose down

echo -e "${YELLOW}🚀 Starting new containers${NC}"
docker-compose up -d

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to be healthy${NC}"
sleep 30

# Check service health
echo -e "${YELLOW}🏥 Checking service health${NC}"
for service in api db redis; do
    if docker-compose ps | grep -q "$service.*Up.*healthy"; then
        echo -e "${GREEN}✅ $service is healthy${NC}"
    else
        echo -e "${RED}❌ $service is not healthy${NC}"
        docker-compose logs $service
        exit 1
    fi
done

# Run database migrations
echo -e "${YELLOW}🗄️ Running database migrations${NC}"
docker-compose exec api alembic upgrade head

# Run post-deployment tests
echo -e "${YELLOW}🧪 Running post-deployment tests${NC}"
./scripts/health-check.sh

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}📋 Backup saved to: $BACKUP_DIR${NC}"
echo -e "${GREEN}🌐 Application is running at: https://your-domain.com${NC}"
