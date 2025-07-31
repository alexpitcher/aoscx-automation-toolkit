# API Integration Guide - AOS-CX Mobile Dashboard

## Overview

This guide details how the mobile dashboard integrates with your existing Flask backend that uses PyAOS-CX for switch management.

## Backend API Reference

Your Flask backend exposes these endpoints that the dashboard consumes:

### Switch Management Endpoints

#### GET `/api/switches`
Returns all switches in inventory.

**Response:**
```json
{
  "switches": [
    {
      "id": "192.168.1.10",
      "name": "Core-SW-01",
      "ip_address": "192.168.1.10",
      "model": "Aruba CX 6400",
      "status": "online",
      "last_seen": "2024-01-15T10:30:00Z",
      "firmware_version": "10.09",
      "error_message": null
    }
  ],
  "count": 1
}
```

#### POST `/api/switches`
Adds a new switch to inventory.

**Request:**
```json
{
  "ip_address": "192.168.1.11",
  "name": "Access-SW-02"  // optional
}
```

**Response:**
```json
{
  "message": "Switch 192.168.1.11 added successfully",
  "switch": {
    "id": "192.168.1.11",
    "name": "Access-SW-02",
    "ip_address": "192.168.1.11",
    "status": "offline",
    "last_seen": null
  }
}
```

#### DELETE `/api/switches/{ip_address}`
Removes a switch from inventory.

**Response:**
```json
{
  "message": "Switch 192.168.1.11 removed successfully"
}
```

#### GET `/api/switches/{ip_address}/test`
Tests connection to a specific switch.

**Response:**
```json
{
  "status": "online",
  "ip_address": "192.168.1.10",
  "firmware_version": "10.09.1020",
  "model": "Aruba CX 6400 48G",
  "last_seen": "2024-01-15T10:30:00Z",
  "error_message": null
}
```

### VLAN Management Endpoints

#### GET `/api/vlans?switch_ip={ip}&load_details={true|false}`
Lists VLANs on a specific switch.

**Parameters:**
- `switch_ip` (required): IP address of the switch
- `load_details` (optional): Whether to load detailed VLAN information (default: true)

**Response:**
```json
{
  "vlans": [
    {
      "id": 1,
      "name": "default",
      "admin_state": "up",
      "oper_state": "up"
    },
    {
      "id": 100,
      "name": "Guest_WiFi",
      "admin_state": "up",
      "oper_state": "up"
    }
  ]
}
```

#### POST `/api/vlans`
Creates a VLAN on a specific switch.

**Request:**
```json
{
  "switch_ip": "192.168.1.10",
  "vlan_id": 200,
  "name": "IoT_Devices"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully created VLAN 200 ('IoT_Devices') on 192.168.1.10"
}
```

#### DELETE `/api/vlans/{vlan_id}`
Deletes a VLAN from a specific switch.

**Request:**
```json
{
  "switch_ip": "192.168.1.10"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully deleted VLAN 200 from 192.168.1.10"
}
```

### Bulk Operations

#### POST `/api/bulk/vlans`
Creates VLANs on multiple switches.

**Request:**
```json
{
  "switch_ips": ["192.168.1.10", "192.168.1.11"],
  "vlans": [
    {
      "vlan_id": 300,
      "name": "Servers"
    },
    {
      "vlan_id": 400,
      "name": "Printers"
    }
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "switch_ip": "192.168.1.10",
      "vlans": [
        {
          "vlan_id": 300,
          "status": "success",
          "message": "Successfully created VLAN 300 ('Servers') on 192.168.1.10"
        }
      ]
    }
  ]
}
```

### System Endpoints

#### GET `/api/status`
Returns overall system status.

**Response:**
```json
{
  "switches": 3,
  "online_switches": [
    {
      "ip_address": "192.168.1.10",
      "name": "Core-SW-01",
      "status": "online",
      "last_seen": "2024-01-15T10:30:00Z"
    }
  ],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### GET `/api/config/export` 
Exports current configuration.

**Response:**
```json
{
  "version": "1.0",
  "switches": [...],
  "settings": {
    "api_version": "v10.09",
    "ssl_verify": false
  }
}
```

## Frontend API Service Implementation

The dashboard uses a centralized API service located in `/services/api.ts`:

### Configuration

```typescript
const API_BASE_URL = 'http://localhost:5001/api';

class ApiService {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Network error' }));
      throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  }
}
```

### Usage Examples

#### Loading Switches
```typescript
import { apiService } from '../services/api';

const loadSwitches = async () => {
  try {
    const response = await apiService.getSwitches();
    setSwitches(response.switches);
  } catch (error) {
    console.error('Failed to load switches:', error);
    toast.error('Failed to load switches');
  }
};
```

#### Testing Connection
```typescript
const testConnection = async (switchIp: string) => {
  try {
    const result = await apiService.testConnection(switchIp);
    if (result.status === 'online') {
      toast.success(`Switch ${switchIp} is online`);
    } else {
      toast.error(`Switch ${switchIp} is ${result.status}: ${result.error_message}`);
    }
  } catch (error) {
    toast.error(`Connection test failed: ${error.message}`);
  }
};
```

#### Creating VLANs
```typescript
const createVLAN = async (switchIp: string, vlanId: number, name: string) => {
  try {
    await apiService.createVLAN(switchIp, vlanId, name);
    toast.success(`VLAN ${vlanId} created successfully`);
    // Refresh VLAN list
    await loadVLANs(switchIp);
  } catch (error) {
    if (error.message.includes('Central')) {
      toast.error('Switch is Central-managed. Use Aruba Central for VLAN operations.');
    } else {
      toast.error(`Failed to create VLAN: ${error.message}`);
    }
  }
};
```

## Error Handling

### Backend Error Types

The Flask backend returns specific error types that the dashboard handles:

#### Central Management Errors
```json
{
  "error": "Switch is Central-managed and blocks direct configuration",
  "error_type": "central_management",
  "suggestion": "Use Aruba Central interface for VLAN creation."
}
```

Dashboard handling:
```typescript
if (error.error_type === 'central_management') {
  toast.error('Switch is Central-managed. Use Aruba Central for configuration.');
}
```

#### Permission Errors
```json
{
  "error": "Permission denied: Check user permissions or Central management status",
  "error_type": "permission_denied",
  "suggestion": "Check user permissions or Central management status."
}
```

#### Network/Connection Errors
```json
{
  "error": "Connection error during authentication: HTTPSConnectionPool(host='10.202.0.208', port=443)",
  "error_type": "connection_error"
}
```

### Frontend Error Handling Pattern

```typescript
const handleApiError = (error: any, operation: string) => {
  console.error(`${operation} failed:`, error);
  
  if (error.message.includes('Central')) {
    toast.error('Switch is Central-managed. Use Aruba Central for this operation.');
  } else if (error.message.includes('Permission denied')) {
    toast.error('Permission denied. Check user credentials.');
  } else if (error.message.includes('Connection')) {
    toast.error('Connection failed. Check network connectivity.');
  } else {
    toast.error(`${operation} failed: ${error.message}`);
  }
};
```

## Real-time Updates

### Polling Strategy

The dashboard implements polling to keep data current:

```typescript
useEffect(() => {
  const interval = setInterval(() => {
    loadSwitches(); // Refresh every 30 seconds
  }, 30000);

  return () => clearInterval(interval);
}, []);
```

### Pull-to-Refresh

Mobile-optimized refresh functionality:

```typescript
const [isRefreshing, setIsRefreshing] = useState(false);

const handleRefresh = async () => {
  setIsRefreshing(true);
  try {
    await Promise.all([
      loadSwitches(),
      loadVLANs(selectedSwitchIp)
    ]);
  } finally {
    setIsRefreshing(false);
  }
};
```

## Data Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React UI      │    │   API Service   │    │   Flask Backend │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Dashboard   │─┼────┼─│ getSwitches │─┼────┼─│ /api/swit.. │ │
│ │ Switches    │ │    │ │ testConn..  │ │    │ │ /api/vlans  │ │
│ │ VLANs       │ │    │ │ createVLAN  │ │    │ │ /api/bulk/  │ │
│ │ Operations  │ │    │ │ bulkOps     │ │    │ │ /api/status │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────── State ───────┴──── HTTP/JSON ───────┘
```

## Configuration Examples

### Development Setup

```typescript
// services/api.ts
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5001/api';
```

### Production Setup with Proxy

```nginx
# nginx.conf
location /api/ {
    proxy_pass http://backend-server:5001/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Handle CORS
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods "GET, POST, DELETE, OPTIONS";
    add_header Access-Control-Allow-Headers "Content-Type, Authorization";
}
```

Then set frontend to use same origin:
```typescript
const API_BASE_URL = `/api`; // Use relative URL for proxy
```

## Testing API Integration

### Manual Testing

```bash
# Test backend directly
curl http://localhost:5001/api/switches

# Test through dashboard proxy (if configured)
curl http://localhost:3000/api/switches

# Test VLAN creation
curl -X POST http://localhost:5001/api/vlans \
  -H "Content-Type: application/json" \
  -d '{"switch_ip": "192.168.1.10", "vlan_id": 123, "name": "Test"}'
```

### Automated Testing

```typescript
// api.test.ts
describe('API Service', () => {
  test('should fetch switches', async () => {
    const mockResponse = { switches: [], count: 0 };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });

    const result = await apiService.getSwitches();
    expect(result).toEqual(mockResponse);
  });
});
```

This API integration guide provides everything needed to connect the mobile dashboard to your existing Flask backend running PyAOS-CX automation.