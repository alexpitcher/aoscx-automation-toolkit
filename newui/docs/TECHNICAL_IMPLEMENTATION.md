# AOS-CX Mobile Dashboard - Technical Implementation Guide

## Overview

The AOS-CX Mobile Dashboard is a responsive web application for managing HPE Aruba CX switches. It provides a mobile-first interface that connects to your existing Flask backend running the PyAOS-CX automation toolkit.

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Mobile Dashboard  │    │   Flask Backend     │    │   Aruba CX Switches │
│   (React/TypeScript)│────│   (Python/PyAOS-CX)│────│   (REST API)        │
│   Port: 3000        │    │   Port: 5001        │    │   Port: 443         │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Prerequisites

### Backend Requirements
- Flask backend with PyAOS-CX already running on port 5001
- Python environment with required dependencies
- Network access to Aruba CX switches
- Valid switch credentials configured

### Frontend Requirements
- Node.js 18+ and npm/yarn
- Modern web browser with ES2020+ support
- Network access to Flask backend

## Installation & Setup

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd aos-cx-mobile-dashboard

# Install dependencies
npm install
```

### 2. Configure API Endpoint

Update the API base URL in `/services/api.ts`:

```typescript
// For development
const API_BASE_URL = 'http://localhost:5001/api';

// For production
const API_BASE_URL = 'https://your-backend-server.com/api';
```

### 3. Start the Development Server

```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000`

## API Integration

### Backend Endpoints Used

The dashboard integrates with these Flask backend endpoints:

#### Switch Management
- `GET /api/switches` - List all switches
- `POST /api/switches` - Add new switch
- `DELETE /api/switches/{ip}` - Remove switch
- `GET /api/switches/{ip}/test` - Test connection

#### VLAN Management
- `GET /api/vlans?switch_ip={ip}` - List VLANs
- `POST /api/vlans` - Create VLAN
- `DELETE /api/vlans/{id}` - Delete VLAN

#### Bulk Operations
- `POST /api/bulk/vlans` - Create VLANs on multiple switches

#### System Operations
- `GET /api/status` - System status
- `GET /api/config/export` - Export configuration
- `POST /api/config/import` - Import configuration

### Data Models

#### Switch Object
```typescript
interface Switch {
  id: string;           // Unique identifier
  name: string;         // User-friendly name
  ip_address: string;   // Management IP
  model?: string;       // Switch model
  status: 'online' | 'offline' | 'error';
  last_seen?: string;   // ISO timestamp
  firmware_version?: string;
  error_message?: string;
}
```

#### VLAN Object
```typescript
interface VLAN {
  id: number;           // VLAN ID (1-4094)
  name: string;         // VLAN name
  admin_state?: string; // Administrative state
  oper_state?: string;  // Operational state
}
```

## Error Handling

### Backend Error Types

The dashboard handles specific error types from the backend:

#### Central Management Errors
- **Status Code**: 403
- **Error Type**: `central_management`
- **Handling**: Display warning about Central-managed switches

#### Permission Errors
- **Status Code**: 403
- **Error Type**: `permission_denied`
- **Handling**: Show authentication/permission guidance

#### Network Errors
- **Status Code**: 503
- **Handling**: Display connectivity issues and retry options

### Frontend Error Handling

```typescript
try {
  await apiService.createVLAN(switchIp, vlanId, name);
  toast.success('VLAN created successfully');
} catch (error: any) {
  if (error.message.includes('Central')) {
    toast.error('Switch is Central-managed. Use Aruba Central for VLAN operations.');
  } else {
    toast.error(error.message || 'Operation failed');
  }
}
```

## Mobile Optimization

### Responsive Breakpoints
- **Mobile**: 375px - 767px (primary target)
- **Tablet**: 768px - 1023px
- **Desktop**: 1024px+

### Touch Interactions
- Minimum 44px touch targets
- Swipe gestures for navigation
- Pull-to-refresh functionality
- Long-press context menus

### Performance Optimizations
- Component lazy loading
- API response caching
- Optimized bundle splitting
- Progressive Web App features

## Production Deployment

### Build for Production

```bash
npm run build
```

### Environment Configuration

Create `.env.production`:

```env
REACT_APP_API_URL=https://your-backend-server.com/api
REACT_APP_ENVIRONMENT=production
```

### Web Server Configuration

#### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-dashboard.com;
    root /var/www/aos-cx-dashboard/build;
    index index.html;

    # Handle client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to backend
    location /api/ {
        proxy_pass http://localhost:5001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Enable gzip compression
    gzip on;
    gzip_types text/css application/javascript application/json;
}
```

#### Apache Configuration
```apache
<VirtualHost *:80>
    ServerName your-dashboard.com
    DocumentRoot /var/www/aos-cx-dashboard/build
    
    # Enable client-side routing
    RewriteEngine On
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule . /index.html [L]
    
    # API proxy
    ProxyPreserveHost On
    ProxyPass /api/ http://localhost:5001/api/
    ProxyPassReverse /api/ http://localhost:5001/api/
</VirtualHost>
```

### Docker Deployment

```dockerfile
# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Security Considerations

### Network Security
- Use HTTPS in production
- Implement proper CORS policies
- Network segmentation for switch management

### Authentication
- Backend handles switch authentication
- Consider implementing user authentication for dashboard access
- Use environment variables for sensitive configuration

### Data Validation
- Input validation on both client and server
- IP address format validation
- VLAN ID range validation (1-4094)

## Monitoring & Logging

### Frontend Monitoring
- Error boundary implementation
- Performance monitoring with Web Vitals
- User interaction analytics

### Backend Integration
- Switch connection status monitoring
- API response time tracking
- Error rate monitoring

## Troubleshooting

### Common Issues

#### Switch Connection Failures
- Verify network connectivity
- Check switch credentials
- Ensure REST API is enabled on switch
- Verify Central management status

#### VLAN Creation Errors
- Check Central management status
- Verify user permissions
- Ensure VLAN ID is not in use
- Check network connectivity

#### UI Not Loading
- Verify backend is running on port 5001
- Check CORS configuration
- Verify API endpoint URLs
- Check browser console for errors

### Debug Endpoints

The backend provides debug endpoints for troubleshooting:

```bash
# Test authentication to specific switch
curl http://localhost:5001/debug/test-auth/192.168.1.10
```

## Performance Optimization

### Bundle Size Optimization
- Code splitting by route
- Tree shaking unused code
- Lazy loading components
- Image optimization

### Runtime Performance
- React.memo for expensive components
- useMemo for heavy calculations
- Virtual scrolling for large lists
- Debounced API calls

### Caching Strategy
- Service worker for offline capability
- API response caching
- Static asset caching
- Background data refresh

## Browser Compatibility

### Supported Browsers
- Chrome 88+
- Firefox 85+
- Safari 14+
- Edge 88+

### Mobile Browsers
- iOS Safari 14+
- Chrome Mobile 88+
- Samsung Internet 13+

## Development Guidelines

### Code Style
- TypeScript strict mode
- ESLint configuration
- Prettier formatting
- Component documentation

### Testing Strategy
- Unit tests with Jest
- Component tests with React Testing Library
- Integration tests for API calls
- E2E tests with Playwright

### Git Workflow
- Feature branch development
- PR reviews required
- Automated CI/CD pipeline
- Semantic versioning