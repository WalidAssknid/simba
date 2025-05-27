#!/bin/bash

# SIMBA Deploy Script
# Automated deployment script for SIMBA project

set -e  

echo "🚀 Starting SIMBA deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'r

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

ENVIRONMENT=${1:-"development"}
case $ENVIRONMENT in
    "production"|"prod")
        ENVIRONMENT="production"
        COMPOSE_FILE="docker-compose.prod.yml"
        ENV_FILE=".env.production"
        HOST_CHECK="simba-refact.irit.fr"
        ;;
    "staging")
        ENVIRONMENT="staging"
        COMPOSE_FILE="docker-compose.staging.yml"
        ENV_FILE=".env.staging"
        HOST_CHECK="localhost"
        ;;
    *)
        ENVIRONMENT="development"
        COMPOSE_FILE="docker-compose.yml"
        ENV_FILE=".env"
        HOST_CHECK="localhost:8000"
        ;;
esac

print_step "Deploying to $ENVIRONMENT environment"

if [ ! -f $COMPOSE_FILE ]; then
    print_error "Compose file $COMPOSE_FILE not found"
    exit 1
fi

if [ "$ENVIRONMENT" = "production" ]; then
    if [ ! -f $ENV_FILE ]; then
        print_warning "$ENV_FILE not found. Please create it with production settings."
        print_warning "Required variables: DEBUG=False, ALLOWED_HOSTS=simba-refact.irit.fr, SECRET_KEY=..."
        
        cat > $ENV_FILE << 'EOF'

# Production Environment - CONFIGURE THESE VALUES
DEBUG=False
SECRET_KEY=CHANGE-THIS-SECRET-KEY-IN-PRODUCTION
ALLOWED_HOSTS=simba-refact.irit.fr
DATABASE_URL=postgresql://simba_user:CHANGE-DB-PASSWORD@db:5432/simba_db
POSTGRES_PASSWORD=CHANGE-DB-PASSWORD
OPENAI_API_KEY=your-openai-api-key-here

EOF
        print_warning "Created template $ENV_FILE - PLEASE CONFIGURE IT BEFORE DEPLOYING!"
        exit 1
    fi
fi

if [ "$ENVIRONMENT" = "production" ]; then
    if docker ps | grep -q "simba.*db"; then
        print_step "Creating database backup..."
        ./scripts/backup.sh || print_warning "Backup failed or no existing database"
    else
        print_step "No existing database found, skipping backup"
    fi
fi

print_step "Stopping existing containers..."
docker compose -f $COMPOSE_FILE down || true
print_success "Containers stopped"

if [ "$ENVIRONMENT" = "production" ]; then
    print_step "Pulling latest Docker images..."
    docker compose -f $COMPOSE_FILE pull || print_warning "Some images may need to be built locally"
fi

print_step "Building and starting containers..."
docker compose -f $COMPOSE_FILE up --build -d

print_step "Waiting for services to be ready..."
sleep 15

print_step "Running database migrations..."
docker compose -f $COMPOSE_FILE exec -T web python manage.py migrate

if [ "$ENVIRONMENT" = "production" ]; then
    print_step "Collecting static files..."
    docker compose -f $COMPOSE_FILE exec -T web python manage.py collectstatic --noinput
    print_success "Static files collected"
fi

# Health check
print_step "Performing health check..."
if [ "$ENVIRONMENT" = "production" ]; then
    if curl -f http://localhost:8000 > /dev/null 2>&1; then
        print_success "Application is responding on port 8000 (nginx proxy)"
    else
        print_warning "Application might not be ready yet. Check logs: docker compose -f $COMPOSE_FILE logs"
    fi
else    
    if curl -f http://localhost:8000 > /dev/null 2>&1; then
        print_success "Application is responding on port 8000"
    else
        print_warning "Application might not be ready yet. Check logs: docker compose -f $COMPOSE_FILE logs"
    fi
fi

# Show running containers
print_step "Deployment status:"
docker compose -f $COMPOSE_FILE ps

# Show version information
if [ -f version.py ]; then
    VERSION=$(python3 -c "import sys; sys.path.append('.'); from version import get_version; print(get_version())" 2>/dev/null || echo "unknown")
    print_success "SIMBA v$VERSION deployed successfully to $ENVIRONMENT!"
else
    print_success "SIMBA deployed successfully to $ENVIRONMENT!"
fi

# Show useful commands
echo ""
echo -e "${BLUE}📝 Useful commands:${NC}"
echo "  • View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "  • Stop application: docker compose -f $COMPOSE_FILE down"
echo "  • Restart application: docker compose -f $COMPOSE_FILE restart"
echo "  • Access shell: docker compose -f $COMPOSE_FILE exec web bash"
echo "  • View database: docker compose -f $COMPOSE_FILE exec db psql -U simba_user -d simba_db"

if [ "$ENVIRONMENT" = "production" ]; then
    echo ""
    echo -e "${YELLOW}🔗 Production URLs:${NC}"
    echo "  • Main application: https://simba-refact.irit.fr"
    echo "  • Chainlit: https://simba-refact.irit.fr/chainlit/"
    echo ""
    echo -e "${YELLOW}⚙️  Internal Configuration:${NC}"
    echo "  • Nginx proxy: localhost:8000 → containers"
    echo "  • Web container: internal port 8000"
    echo "  • Chainlit container: internal port 8500"
    echo ""
    echo -e "${YELLOW}🔒 Security reminders:${NC}"
    echo "  • Configure SSL certificates in nginx/prod.conf"
    echo "  • Set strong passwords in $ENV_FILE"
    echo "  • Ensure external proxy forwards to port 8000"
    echo "  • Set up automated backups with cron"
fi

log "Deployment completed successfully" 