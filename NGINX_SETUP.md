# Nginx Reverse Proxy Setup for WOLManager

This guide explains how to set up Nginx as a reverse proxy for WOLManager to improve security, performance, and enable SSL termination.

## Quick Setup

### Automatic Setup (Recommended)

Run the provided setup script:

```bash
./setup-nginx.sh
```

This script will:
- Install Nginx if not already installed
- Check if WOLManager is running
- Ask for your configuration preference (HTTP or HTTPS)
- Configure and start Nginx
- Test the setup

### Manual Setup

#### 1. Install Nginx

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install nginx
```

**CentOS/RHEL:**
```bash
sudo yum install nginx
# or
sudo dnf install nginx
```

#### 2. Configure Nginx

**For HTTP only:**
```bash
sudo cp nginx.conf /etc/nginx/sites-available/wolmanager
sudo ln -sf /etc/nginx/sites-available/wolmanager /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/default  # Remove default site
```

**For HTTPS with SSL:**
```bash
# Update domain name in nginx-ssl.conf first
sudo cp nginx-ssl.conf /etc/nginx/sites-available/wolmanager-ssl
sudo ln -sf /etc/nginx/sites-available/wolmanager-ssl /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/default  # Remove default site
```

#### 3. Test and Start Nginx

```bash
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
sudo systemctl enable nginx
```

## SSL Certificate Setup

### Using Let's Encrypt (Recommended)

1. **Install Certbot:**
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   ```

2. **Obtain SSL certificate:**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

3. **Auto-renewal setup:**
   ```bash
   sudo crontab -e
   # Add this line:
   0 12 * * * /usr/bin/certbot renew --quiet
   ```

### Using Custom SSL Certificates

Place your certificates at:
- Certificate: `/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/your-domain.com/privkey.pem`

Update the paths in `nginx-ssl.conf` if using different locations.

## Docker Compose Setup

### With Nginx Container

Use the provided Docker Compose configuration:

```bash
# Start all services including Nginx
docker-compose -f docker-compose-nginx.yml up -d

# Check status
docker-compose -f docker-compose-nginx.yml ps

# View logs
docker-compose -f docker-compose-nginx.yml logs nginx
```

### Configuration Options

The Nginx configuration includes:

- **Security headers** (HSTS, XSS protection, etc.)
- **Gzip compression** for better performance
- **Static file caching** for improved load times
- **WebSocket support** for real-time features
- **Proper proxy headers** for correct client information
- **Health check endpoint** for monitoring

## Configuration Files

### nginx.conf
- Basic HTTP configuration
- Suitable for development and internal use
- No SSL/TLS encryption

### nginx-ssl.conf
- Full HTTPS configuration with SSL/TLS
- Security headers and modern SSL settings
- HTTP to HTTPS redirect
- Production-ready configuration

### docker-compose-nginx.yml
- Complete Docker setup with Nginx
- Includes Redis, WOLManager, and Nginx services
- Uses host networking for network discovery

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check if WOLManager is running on port 8000
   - Verify firewall settings
   - Check Nginx error logs: `sudo tail -f /var/log/nginx/error.log`

2. **SSL Certificate Issues**
   - Verify certificate paths in configuration
   - Check certificate validity: `openssl x509 -in certificate.pem -text -noout`
   - Ensure proper file permissions

3. **Static Files Not Loading**
   - Check file permissions and paths
   - Verify proxy_pass configuration
   - Clear browser cache

### Useful Commands

```bash
# Check Nginx status
sudo systemctl status nginx

# Test Nginx configuration
sudo nginx -t

# Reload Nginx configuration
sudo systemctl reload nginx

# View Nginx logs
sudo tail -f /var/log/nginx/wolmanager_access.log
sudo tail -f /var/log/nginx/wolmanager_error.log

# Check WOLManager health through Nginx
curl http://localhost/health
curl https://your-domain.com/health
```

### Log Locations

- **Access logs:** `/var/log/nginx/wolmanager_access.log`
- **Error logs:** `/var/log/nginx/wolmanager_error.log`
- **SSL access logs:** `/var/log/nginx/wolmanager_ssl_access.log`
- **SSL error logs:** `/var/log/nginx/wolmanager_ssl_error.log`

## Performance Optimization

### Caching

The configuration includes:
- Static file caching (1 hour)
- API endpoint no-cache headers
- Gzip compression for text-based content

### Security

Security features include:
- HSTS (HTTP Strict Transport Security)
- XSS protection
- Content type sniffing protection
- Frame options
- Content Security Policy

### Monitoring

Monitor your setup with:
```bash
# Check Nginx metrics
nginx -V  # Version and modules
curl -I http://localhost/health  # Response headers

# Monitor logs
sudo tail -f /var/log/nginx/wolmanager_access.log | grep -E "(GET|POST)"
```

## Customization

### Adding Custom Headers

Edit the Nginx configuration to add custom headers:

```nginx
add_header X-Custom-Header "value" always;
```

### Modifying Timeouts

Adjust timeouts for your needs:

```nginx
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
```

### Load Balancing

For multiple WOLManager instances, add upstream configuration:

```nginx
upstream wolmanager_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

location / {
    proxy_pass http://wolmanager_backend;
    # ... other proxy settings
}
```

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review Nginx error logs
3. Verify WOLManager is running correctly
4. Test direct connection to WOLManager (bypassing Nginx)
