# AOS-CX Mobile Dashboard - Deployment Guide

## Quick Start

### Prerequisites Checklist
- [ ] Flask backend running on port 5001
- [ ] Python environment with PyAOS-CX dependencies
- [ ] Node.js 18+ installed
- [ ] Network access between dashboard and backend
- [ ] Aruba CX switches accessible from backend

### 5-Minute Setup

```bash
# 1. Install dependencies
npm install

# 2. Configure API endpoint (if different from localhost:5001)
# Edit /services/api.ts line 7:
# const API_BASE_URL = 'http://your-backend-ip:5001/api';

# 3. Start development server
npm run dev

# 4. Open browser to http://localhost:3000
```

## Production Deployment Options

### Option 1: Static Hosting (Recommended)

Deploy as static files with reverse proxy to backend.

#### Build Process
```bash
# Create production build
npm run build

# Files will be in ./build/ directory
ls -la build/
```

#### Nginx Setup
```bash
# Install nginx
sudo apt update && sudo apt install nginx

# Copy files
sudo cp -r build/* /var/www/html/

# Configure nginx
sudo nano /etc/nginx/sites-available/aos-cx-dashboard
```

Nginx configuration:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/html;
    index index.html;

    # Serve static files
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API calls to Flask backend
    location /api/ {
        proxy_pass http://your-backend-server:5001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and start:
```bash
sudo ln -s /etc/nginx/sites-available/aos-cx-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option 2: Docker Deployment

#### Dockerfile
```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Docker Compose
```yaml
version: '3.8'
services:
  dashboard:
    build: .
    ports:
      - "3000:80"
    environment:
      - API_URL=http://backend:5001/api
    depends_on:
      - backend

  backend:
    image: your-backend-image
    ports:
      - "5001:5001"
    volumes:
      - ./config:/app/config
    environment:
      - FLASK_ENV=production
```

Deploy:
```bash
docker-compose up -d
```

### Option 3: Cloud Deployment

#### Vercel
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel --prod

# Configure environment variables in Vercel dashboard
# REACT_APP_API_URL=https://your-backend.herokuapp.com/api
```

#### Netlify
```bash
# Build and deploy
npm run build
netlify deploy --prod --dir=build

# Configure redirects for API
echo '/api/* https://your-backend-server.com/api/:splat 200' >> build/_redirects
```

## Environment Configuration

### Development Environment

Create `.env.development`:
```env
REACT_APP_API_URL=http://localhost:5001/api
REACT_APP_ENVIRONMENT=development
REACT_APP_ENABLE_DEBUG=true
```

### Production Environment

Create `.env.production`:
```env
REACT_APP_API_URL=https://your-backend-server.com/api
REACT_APP_ENVIRONMENT=production
REACT_APP_ENABLE_DEBUG=false
```

### Runtime Configuration

For dynamic configuration, create `public/config.js`:
```javascript
window.APP_CONFIG = {
  API_URL: 'http://your-backend-server:5001/api',
  COMPANY_NAME: 'Your Company',
  SUPPORT_EMAIL: 'support@yourcompany.com'
};
```

Load in `public/index.html`:
```html
<script src="/config.js"></script>
```

Access in app:
```typescript
const config = (window as any).APP_CONFIG || {};
const API_URL = config.API_URL || 'http://localhost:5001/api';
```

## Network Architecture

### Typical Deployment Topology

```
Internet
    │
    ├── Load Balancer (HTTPS)
    │
    ├── Web Server (Dashboard)
    │   └── Static Files + API Proxy
    │
    ├── Application Server (Flask Backend)
    │   └── PyAOS-CX + Switch Management
    │
    └── Management Network
        └── Aruba CX Switches
```

### Security Considerations

#### HTTPS Configuration
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    # ... rest of configuration
}
```

#### Firewall Rules
```bash
# Allow web traffic
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Restrict backend access (only from web server)
sudo ufw allow from web-server-ip to any port 5001

# Allow switch management traffic
sudo ufw allow from backend-ip to switch-network port 443
```

## Backend Integration

### Flask Backend Configuration

Ensure your Flask backend has proper CORS configuration:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=['http://localhost:3000', 'https://your-dashboard-domain.com'])
```

### API Endpoint Verification

Test backend connectivity:
```bash
# Check if backend is running
curl http://localhost:5001/api/switches

# Test switch connection
curl -X GET http://localhost:5001/api/switches/192.168.1.10/test

# Test VLAN listing
curl http://localhost:5001/api/vlans?switch_ip=192.168.1.10
```

## Monitoring & Health Checks

### Application Health Check

Add health check endpoint to monitor dashboard:

```typescript
// /public/health
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0"
}
```

### Monitoring Script

```bash
#!/bin/bash
# health-check.sh

# Check dashboard availability
if curl -f http://localhost:3000/health > /dev/null 2>&1; then
    echo "Dashboard: OK"
else
    echo "Dashboard: FAILED"
    exit 1
fi

# Check backend connectivity
if curl -f http://localhost:5001/api/status > /dev/null 2>&1; then
    echo "Backend: OK"
else
    echo "Backend: FAILED"
    exit 1
fi

echo "All services healthy"
```

### Systemd Service

Create `/etc/systemd/system/aos-cx-dashboard.service`:
```ini
[Unit]
Description=AOS-CX Dashboard
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/aos-cx-dashboard
ExecStart=/usr/bin/nginx
ExecReload=/bin/kill -s HUP $MAINPID
PIDFile=/run/nginx.pid

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable aos-cx-dashboard
sudo systemctl start aos-cx-dashboard
```

## Troubleshooting

### Common Deployment Issues

#### 1. API Connection Failures
**Symptoms**: Dashboard loads but shows "No switches configured"

**Solutions**:
```bash
# Check backend connectivity
curl http://backend-server:5001/api/switches

# Verify CORS settings
# Check browser network tab for CORS errors

# Test from dashboard server
curl -H "Origin: http://dashboard-domain.com" \
     -H "Access-Control-Request-Method: GET" \
     http://backend-server:5001/api/switches
```

#### 2. Static Files Not Loading
**Symptoms**: White screen, console errors for missing files

**Solutions**:
```bash
# Check build output
ls -la build/

# Verify nginx configuration
sudo nginx -t

# Check file permissions
sudo chown -R www-data:www-data /var/www/html/
```

#### 3. Routing Issues
**Symptoms**: 404 errors on page refresh

**Solutions**:
```nginx
# Add to nginx config
location / {
    try_files $uri $uri/ /index.html;
}
```

#### 4. Performance Issues
**Symptoms**: Slow loading, high memory usage

**Solutions**:
```nginx
# Enable gzip compression
gzip on;
gzip_types text/css application/javascript application/json;

# Enable caching
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### Log Analysis

#### Nginx Access Logs
```bash
# Monitor real-time access
sudo tail -f /var/log/nginx/access.log

# Check for errors
sudo tail -f /var/log/nginx/error.log

# Analyze API calls
grep "/api/" /var/log/nginx/access.log | tail -20
```

#### Browser Developer Tools
1. Open Network tab
2. Check for failed API calls (red entries)
3. Verify response codes and timing
4. Check Console tab for JavaScript errors

## Backup & Recovery

### Configuration Backup
```bash
# Backup nginx configuration
sudo cp /etc/nginx/sites-available/aos-cx-dashboard \
       /backup/nginx-config-$(date +%Y%m%d).conf

# Backup application files
tar -czf /backup/dashboard-$(date +%Y%m%d).tar.gz \
         /var/www/html/
```

### Automated Backup Script
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup static files
tar -czf $BACKUP_DIR/dashboard-$DATE.tar.gz /var/www/html/

# Backup configuration
cp /etc/nginx/sites-available/aos-cx-dashboard $BACKUP_DIR/nginx-$DATE.conf

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "nginx-*.conf" -mtime +30 -delete

echo "Backup completed: $DATE"
```

## SSL/TLS Configuration

### Let's Encrypt Setup
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Manual SSL Setup
```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;
}
```

This deployment guide provides comprehensive instructions for getting the AOS-CX Mobile Dashboard running in production environments while maintaining security and performance best practices.