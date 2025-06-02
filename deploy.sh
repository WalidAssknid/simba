#!/bin/bash

# SIMBA Production Deploy Script
# Production deployment script for SIMBA project

set -e  

echo "🚀 Starting SIMBA production deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="simba-2025"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deploy.log"

mkdir -p logs backups

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
    log "STEP: $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    log "SUCCESS: $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    log "ERROR: $1"
}

print_step "Running pre-deployment checks..."

if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available"
    exit 1
fi

print_success "Docker and Docker Compose are available"

# Production configuration
ENVIRONMENT="production"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"
HOST_CHECK="simba-refact.irit.fr"

print_step "Deploying to production environment"

if [ ! -f $COMPOSE_FILE ]; then
    print_error "Compose file $COMPOSE_FILE not found"
    exit 1
fi

if [ ! -f $ENV_FILE ]; then
    print_error "$ENV_FILE not found. Please create it with production settings."
    print_error "Required variables: DEBUG=False, ALLOWED_HOSTS=simba-refact.irit.fr, SECRET_KEY=..."
    exit 1
fi

if docker ps | grep -q "simba.*db"; then
    print_step "Creating database backup..."
    ./scripts/backup.sh || print_warning "Backup failed or no existing database"
else
    print_step "No existing database found, skipping backup"
fi

print_step "Stopping existing containers..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE down || true
print_success "Containers stopped"

print_step "Pulling latest Docker images..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE pull || print_warning "Some images may need to be built locally"

print_step "Building and starting containers..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE up --build -d

print_step "Waiting for services to be ready..."
sleep 15

print_step "Running database migrations..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python manage.py migrate

print_step "Setting all users as email verified for production..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simba.settings')
import django
django.setup()
from django.utils import timezone
from simbaapp.models import User

# Mark all users as email verified
users_updated = User.objects.filter(is_email_verified=False).update(
    is_email_verified=True,
    email_verified_at=timezone.now()
)

print(f'✅ Marked {users_updated} users as email verified')

# Show user status
total_users = User.objects.count()
verified_users = User.objects.filter(is_email_verified=True).count()
print(f'📊 Total users: {total_users}, Verified: {verified_users}')
"

print_step "Collecting static files..."
ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec -T web python manage.py collectstatic --noinput
print_success "Static files collected"

# Health check
print_step "Performing health check..."
if curl -f http://localhost:8000 > /dev/null 2>&1; then
    print_success "Application is responding on port 8000 (nginx proxy)"
else
    print_warning "Application might not be ready yet. Check logs: ENVIRONMENT=production docker compose -f $COMPOSE_FILE logs"
fi

# Show running containers
print_step "Deployment status:"
ENVIRONMENT=production docker compose -f $COMPOSE_FILE ps

# Show version information
if [ -f version.py ]; then
    VERSION=$(python3 -c "import sys; sys.path.append('.'); from version import get_version; print(get_version())" 2>/dev/null || echo "unknown")
    print_success "SIMBA v$VERSION deployed successfully to production!"
else
    print_success "SIMBA deployed successfully to production!"
fi

# Show useful commands
echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo "  • View logs: ENVIRONMENT=production docker compose -f $COMPOSE_FILE logs -f"
echo "  • Stop application: ENVIRONMENT=production docker compose -f $COMPOSE_FILE down"
echo "  • Restart application: ENVIRONMENT=production docker compose -f $COMPOSE_FILE restart"
echo "  • Access shell: ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec web bash"
echo "  • View database: ENVIRONMENT=production docker compose -f $COMPOSE_FILE exec db psql -U simba_user -d simba_db"

echo ""
echo -e "${YELLOW}🔗 Production URLs:${NC}"
echo "  • Main application: https://simba-refact.irit.fr"
echo "  • Chainlit: https://simba-refact.irit.fr/chainlit/"
echo ""

echo ""
echo -e "${YELLOW}🔧 Environment Variables:${NC}"
echo "  • ENVIRONMENT=production"
echo "  • SIMBA_API_URL_PROD=https://simba-refact.irit.fr/api"
echo "  • CHAINLIT_URL_PROD=https://simba-refact.irit.fr/chainlit"
echo ""

log "Production deployment completed successfully" 