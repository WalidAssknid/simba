#!/bin/bash

# SIMBA Disk Cleanup Script
# Comprehensive Docker and system cleanup for production

set -e

echo "🧹 SIMBA Production Disk Cleanup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

show_disk_usage() {
    echo ""
    echo -e "${BLUE}💾 Current Disk Usage:${NC}"
    df -h | grep -E "(Filesystem|/dev/)" | head -20
    echo ""
}

cleanup_docker_aggressive() {
    print_step "Aggressive Docker cleanup (preserving running containers)..."
    
    # Get currently running containers to preserve them
    RUNNING_CONTAINERS=$(docker ps -q)
    
    print_step "Removing stopped containers..."
    docker container prune -f || true
    
    print_step "Removing unused images (keeping base images)..."
    docker image prune -a -f || true
    
    print_step "Removing unused volumes (except database)..."
    # Get volume names that contain 'db' or 'postgres' to preserve
    DB_VOLUMES=$(docker volume ls -q | grep -E "(db|postgres)" || true)
    if [ ! -z "$DB_VOLUMES" ]; then
        print_warning "Preserving database volumes: $DB_VOLUMES"
        # Remove all volumes except database ones
        docker volume ls -q | grep -v -E "(db|postgres)" | xargs -r docker volume rm 2>/dev/null || true
    else
        docker volume prune -f || true
    fi
    
    print_step "Removing unused networks..."
    docker network prune -f || true
    
    print_step "Removing build cache..."
    docker builder prune -a -f || true
    
    print_step "Removing dangling images..."
    DANGLING=$(docker images -f "dangling=true" -q)
    if [ ! -z "$DANGLING" ]; then
        docker rmi $DANGLING 2>/dev/null || true
    fi
    
    print_success "Aggressive Docker cleanup completed"
}

cleanup_system_logs() {
    print_step "Cleaning system logs..."
    
    # Clean journal logs older than 3 days
    sudo journalctl --vacuum-time=3d 2>/dev/null || print_warning "Could not clean journalctl logs"
    
    # Clean package cache if apt is available
    if command -v apt-get &> /dev/null; then
        sudo apt-get clean 2>/dev/null || print_warning "Could not clean apt cache"
    fi
    
    print_success "System logs cleaned"
}

# Main cleanup execution
show_disk_usage

print_step "Starting comprehensive cleanup..."

# Check if we should preserve running containers
if docker ps | grep -q "simba"; then
    print_warning "SIMBA containers are running. Cleanup will preserve them."
    read -p "Continue with cleanup? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Cleanup cancelled"
        exit 1
    fi
fi

cleanup_docker_aggressive
cleanup_system_logs

show_disk_usage

print_success "🎉 Disk cleanup completed!"

# Show recommendations
echo ""
echo -e "${YELLOW}📝 Recommendations:${NC}"
echo "  • Run this cleanup before deployments if /var usage > 85%"
echo "  • Monitor disk usage with: df -h"
echo "  • Check Docker usage with: docker system df"
echo "  • Consider expanding /var partition if cleanups become frequent"
echo "" 