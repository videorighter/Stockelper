#!/bin/bash

# Stockelper LLM Server Deployment Script
# This script helps deploy the Stockelper LLM server with proper configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

# Check if Docker is installed and running
check_docker() {
    log_step "Checking Docker Installation"
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Docker and Docker Compose are available"
}

# Check if .env file exists
check_env_file() {
    log_step "Checking Environment Configuration"
    
    if [ ! -f ".env" ]; then
        log_warn ".env file not found. Creating from template..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_warn "Please edit .env file with your API keys and configuration before continuing."
            log_info "Required configurations:"
            echo "  - Database password"
            echo "  - OpenAI API key"
            echo "  - Anthropic API key (optional)"
            echo "  - Tavily API key"
            echo "  - Langfuse cloud configuration"
            echo "  - Neo4j configuration"
            echo "  - MongoDB configuration"
            echo "  - KIS API configuration (optional)"
            echo ""
            read -p "Press Enter after configuring .env file to continue..."
        else
            log_error ".env.example file not found. Cannot create .env file."
            exit 1
        fi
    else
        log_success ".env file found"
    fi
}

# Validate required environment variables
validate_env() {
    log_step "Validating Environment Variables"
    
    source .env
    
    required_vars=(
        "DB_PASSWORD"
        "YOUR_OPENAI_API_KEY"
        "YOUR_TAVILY_API_KEY"
        "YOUR_LANGFUSE_CLOUD_HOST"
        "YOUR_LANGFUSE_PUBLIC_KEY"
        "YOUR_LANGFUSE_SECRET_KEY"
        "YOUR_NEO4J_URI"
        "YOUR_NEO4J_USERNAME"
        "YOUR_NEO4J_PASSWORD"
        "YOUR_MONGODB_URI"
    )
    
    missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ] || [[ "${!var}" == *"<"* ]] || [[ "${!var}" == *"your-"* ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_error "Missing or incomplete environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        log_error "Please configure these variables in .env file"
        exit 1
    fi
    
    log_success "All required environment variables are configured"
}

# Build and start services
deploy_services() {
    log_step "Building and Starting Services"
    
    log_info "Building Docker images..."
    docker-compose build --no-cache
    
    log_info "Starting services..."
    docker-compose up -d
    
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        log_success "Services are running"
    else
        log_error "Some services failed to start"
        docker-compose logs
        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    log_step "Verifying Deployment"
    
    # Wait for services to be fully ready
    log_info "Waiting for services to initialize..."
    sleep 30
    
    # Check database connectivity
    log_info "Checking database connectivity..."
    if docker-compose exec -T stockelper-db pg_isready -U stockelper; then
        log_success "Database is ready"
    else
        log_error "Database is not ready"
        return 1
    fi
    
    # Check API health
    log_info "Checking API health..."
    max_attempts=10
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            log_success "API is healthy"
            break
        else
            log_info "Attempt $attempt/$max_attempts: API not ready yet..."
            sleep 10
            ((attempt++))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "API health check failed"
        return 1
    fi
    
    return 0
}

# Show deployment info
show_info() {
    log_step "Deployment Complete"
    
    echo ""
    log_success "Stockelper LLM Server is now running!"
    echo ""
    echo "Access URLs:"
    echo "  🌐 API Server: http://localhost:8000"
    echo "  📖 API Documentation: http://localhost:8000/docs"
    echo "  ❤️  Health Check: http://localhost:8000/health"
    echo "  🗄️  Database: localhost:5432 (stockelper/stockelper)"
    echo ""
    echo "Useful Commands:"
    echo "  📊 View logs: docker-compose logs -f"
    echo "  🔄 Restart: docker-compose restart"
    echo "  🛑 Stop: docker-compose down"
    echo "  🗑️  Clean up: docker-compose down -v"
    echo ""
    echo "Next Steps:"
    echo "  1. Test the API with: curl http://localhost:8000/health"
    echo "  2. Check the API documentation at http://localhost:8000/docs"
    echo "  3. Monitor your Langfuse dashboard for observability"
    echo ""
}

# Main deployment function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 Stockelper LLM Server Deployment            ║"
    echo "║                     Open Source Version                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_docker
    check_env_file
    validate_env
    deploy_services
    
    if verify_deployment; then
        show_info
    else
        log_error "Deployment verification failed. Check logs with: docker-compose logs"
        exit 1
    fi
}

# Handle script arguments
case "${1:-}" in
    "stop")
        log_info "Stopping Stockelper LLM Server..."
        docker-compose down
        log_success "Services stopped"
        ;;
    "restart")
        log_info "Restarting Stockelper LLM Server..."
        docker-compose restart
        log_success "Services restarted"
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "clean")
        log_warn "This will remove all containers and volumes. Are you sure? (y/N)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            docker-compose down -v
            docker system prune -f
            log_success "Cleanup complete"
        else
            log_info "Cleanup cancelled"
        fi
        ;;
    "help"|"-h"|"--help")
        echo "Stockelper LLM Server Deployment Script"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  (no command)  Deploy the LLM server"
        echo "  stop          Stop all services"
        echo "  restart       Restart all services"
        echo "  logs          Show service logs"
        echo "  clean         Remove all containers and volumes"
        echo "  help          Show this help message"
        ;;
    "")
        main
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
