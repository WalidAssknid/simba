#!/bin/bash

# SIMBA Quick Redeploy Script
# For applying template changes and frontend updates quickly
# Optimized for low disk space environments

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

check_disk_space() {
    local var_usage=$(df /var | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$var_usage" -gt 90 ]; then
        print_warning "Disk space is getting low (/var at ${var_usage}%). Running cleanup..."
        return 1
    fi
    return 0
}

cleanup_docker() {
    print_step "Cleaning up Docker resources to free space..."
    
    # Remove unused containers
    docker container prune -f >/dev/null 2>&1 || true
    
    # Remove unused images
    docker image prune -f >/dev/null 2>&1 || true
    
    # Remove unused networks
    docker network prune -f >/dev/null 2>&1 || true
    
    # Remove build cache
    docker builder prune -f >/dev/null 2>&1 || true
    
    print_success "Docker cleanup completed"
}

# Check if containers are running
if ! docker ps | grep -q "simba.*web"; then
    print_error "Web container is not running. Please run full deploy first: ./deploy.sh"
    exit 1
fi

# Check disk space and cleanup if necessary
if ! check_disk_space; then
    cleanup_docker
fi

print_step "Stopping web and chainlit containers..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE stop web chainlit

print_step "Removing containers to force rebuild..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE rm -f web chainlit

print_step "Removing web volume to clear cached templates..."
docker volume rm "${PWD##*/}_web" 2>/dev/null || print_warning "Web volume not found"

# Clean up again before rebuild if space is still tight
if ! check_disk_space; then
    print_step "Additional cleanup before rebuild..."
    # Remove dangling images specifically
    docker rmi $(docker images -f "dangling=true" -q) 2>/dev/null || true
fi

print_step "Rebuilding containers (using cache for efficiency)..."
# Remove --no-cache to save space and time, only rebuild if source changed
ENVIRONMENT=production docker compose -f $COMPOSE_FILE build web chainlit

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

# Final cleanup
print_step "Final cleanup..."
cleanup_docker

# Quick health check
print_step "Quick health check..."
sleep 5
if curl -f http://localhost:8000 > /dev/null 2>&1; then
    print_success "✨ Quick redeploy completed! Your template changes should now be visible."
else
    print_warning "Service might still be starting. Check: docker compose -f $COMPOSE_FILE logs web"
fi

# Show disk usage
print_step "Current disk usage:"
df -h /var | tail -1 | awk '{print "  /var: " $3 " used, " $4 " available (" $5 " full)"}'

echo ""
echo -e "${GREEN}🎉 Template changes deployed with optimized disk usage!${NC}"
echo -e "${BLUE}📱 Visit: https://simba-refact.irit.fr${NC}"
echo "" 