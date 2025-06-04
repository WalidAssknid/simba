#!/bin/bash

# SIMBA Quick Redeploy Script
# For applying template changes and frontend updates quickly

set -e

echo "🔄 Quick redeployment for template/frontend changes..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.prod.yml"

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if containers are running
if ! docker ps | grep -q "simba.*web"; then
    print_error "Web container is not running. Please run full deploy first: ./deploy.sh"
    exit 1
fi

print_step "Stopping web and chainlit containers..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE stop web chainlit

print_step "Removing containers to force rebuild..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE rm -f web chainlit

print_step "Removing web volume to clear cached templates..."
docker volume rm "${PWD##*/}_web" 2>/dev/null || print_warning "Web volume not found"

print_step "Rebuilding containers with fresh templates..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE build --no-cache web chainlit

print_step "Starting updated containers..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE up -d web chainlit

print_step "Waiting for services to be ready..."
sleep 10

print_step "Collecting static files..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python manage.py collectstatic --noinput

print_step "Clearing any cached templates..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
import django
django.setup()
from django.core.cache import cache
cache.clear()
print('✅ Template cache cleared')
" 2>/dev/null || print_warning "Cache clearing failed"

# Quick health check
print_step "Quick health check..."
sleep 5
if curl -f http://localhost:8000 > /dev/null 2>&1; then
    print_success "✨ Quick redeploy completed! Your template changes should now be visible."
else
    print_warning "Service might still be starting. Check: docker compose -f $COMPOSE_FILE logs web"
fi

echo ""
echo -e "${GREEN}🎉 Template changes deployed!${NC}"
echo -e "${BLUE}📱 Visit: https://simba-refact.irit.fr${NC}"
echo "" 