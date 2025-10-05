#!/bin/bash

# WOLManager Nginx Setup Script
# This script helps set up Nginx as a reverse proxy for WOLManager

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

print_status "Setting up Nginx reverse proxy for WOLManager..."

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
    print_status "Installing Nginx..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y nginx
    elif command -v yum &> /dev/null; then
        sudo yum install -y nginx
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y nginx
    else
        print_error "Package manager not found. Please install Nginx manually."
        exit 1
    fi
    print_success "Nginx installed successfully"
else
    print_success "Nginx is already installed"
fi

# Check if WOLManager is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    print_warning "WOLManager is not running on port 8000"
    print_status "Please start WOLManager first:"
    echo "  cd /path/to/WOLManager"
    echo "  source venv/bin/activate"
    echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

print_success "WOLManager is running and accessible"

# Ask user for configuration choice
echo ""
print_status "Choose Nginx configuration:"
echo "1) HTTP only (port 80)"
echo "2) HTTP + HTTPS with SSL (ports 80, 443)"
echo "3) Skip Nginx setup"
read -p "Enter your choice (1-3): " choice

case $choice in
    1)
        print_status "Setting up HTTP configuration..."
        sudo cp nginx.conf /etc/nginx/sites-available/wolmanager
        
        # Enable the site
        sudo ln -sf /etc/nginx/sites-available/wolmanager /etc/nginx/sites-enabled/default
        
        # Remove default site if it exists
        sudo rm -f /etc/nginx/sites-enabled/default
        
        # Test configuration
        if sudo nginx -t; then
            print_success "Nginx configuration is valid"
            
            # Restart Nginx
            sudo systemctl restart nginx
            sudo systemctl enable nginx
            
            print_success "Nginx has been configured and restarted"
            print_status "WOLManager is now accessible at: http://localhost"
        else
            print_error "Nginx configuration test failed"
            exit 1
        fi
        ;;
    2)
        print_status "Setting up HTTP + HTTPS configuration..."
        
        # Ask for domain name
        read -p "Enter your domain name (e.g., example.com): " domain
        
        if [ -z "$domain" ]; then
            print_error "Domain name is required for SSL setup"
            exit 1
        fi
        
        # Update SSL config with domain
        sed "s/your-domain.com/$domain/g" nginx-ssl.conf > /tmp/wolmanager-ssl.conf
        sudo cp /tmp/wolmanager-ssl.conf /etc/nginx/sites-available/wolmanager-ssl
        rm /tmp/wolmanager-ssl.conf
        
        # Enable the site
        sudo ln -sf /etc/nginx/sites-available/wolmanager-ssl /etc/nginx/sites-enabled/default
        
        # Remove default site if it exists
        sudo rm -f /etc/nginx/sites-enabled/default
        
        print_warning "SSL certificates are required for HTTPS"
        print_status "You can obtain free SSL certificates using Let's Encrypt:"
        echo "  sudo apt-get install certbot python3-certbot-nginx"
        echo "  sudo certbot --nginx -d $domain"
        echo ""
        print_status "Or place your SSL certificates at:"
        echo "  Certificate: /etc/letsencrypt/live/$domain/fullchain.pem"
        echo "  Private Key: /etc/letsencrypt/live/$domain/privkey.pem"
        
        # Test configuration
        if sudo nginx -t; then
            print_success "Nginx configuration is valid"
            
            # Restart Nginx
            sudo systemctl restart nginx
            sudo systemctl enable nginx
            
            print_success "Nginx has been configured and restarted"
            print_status "WOLManager is now accessible at:"
            echo "  HTTP:  http://$domain (will redirect to HTTPS)"
            echo "  HTTPS: https://$domain"
        else
            print_error "Nginx configuration test failed"
            exit 1
        fi
        ;;
    3)
        print_status "Skipping Nginx setup"
        exit 0
        ;;
    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

# Show status
echo ""
print_status "Nginx setup complete!"
print_status "Useful commands:"
echo "  Check Nginx status: sudo systemctl status nginx"
echo "  View Nginx logs:    sudo tail -f /var/log/nginx/wolmanager_*.log"
echo "  Test configuration: sudo nginx -t"
echo "  Reload Nginx:       sudo systemctl reload nginx"

# Test the setup
if curl -s http://localhost/health > /dev/null; then
    print_success "WOLManager is accessible through Nginx reverse proxy!"
else
    print_warning "WOLManager might not be accessible through Nginx. Check logs for issues."
fi
