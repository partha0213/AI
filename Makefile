.PHONY: help build up down logs shell test clean backup restore

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker images
	docker-compose build

up: ## Start services
	docker-compose up -d

down: ## Stop services
	docker-compose down

logs: ## Show logs
	docker-compose logs -f

shell: ## Access API container shell
	docker-compose exec api bash

test: ## Run tests
	docker-compose exec api pytest tests/ -v

migrate: ## Run database migrations
	docker-compose exec api alembic upgrade head

backup: ## Create backup
	./scripts/backup.sh

restore: ## Restore from backup (usage: make restore BACKUP_PATH=./backups/20240101_120000)
	./scripts/restore.sh $(BACKUP_PATH)

clean: ## Clean up Docker resources
	docker-compose down -v
	docker system prune -f

health: ## Check service health
	./scripts/health-check.sh

deploy-prod: ## Deploy to production
	./scripts/deploy.sh production

deploy-dev: ## Deploy to development
	./scripts/deploy.sh development

init-monitoring: ## Initialize monitoring setup
	./scripts/init-monitoring.sh

ssl-setup: ## Set up SSL certificates
	./scripts/ssl-setup.sh
# Add these to your existing Makefile

migrate: ## Run database migrations
	./scripts/migrate.sh upgrade

migrate-down: ## Rollback last migration
	./scripts/migrate.sh downgrade -1

migrate-history: ## Show migration history
	./scripts/migrate.sh history

migrate-current: ## Show current migration
	./scripts/migrate.sh current

new-migration: ## Generate new migration (usage: make new-migration MESSAGE="description")
	./scripts/generate-migration.sh "$(MESSAGE)"

db-reset: ## Reset database (WARNING: destroys all data)
	./scripts/db-reset.sh
