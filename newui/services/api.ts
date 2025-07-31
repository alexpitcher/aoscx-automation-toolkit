/**
 * API Service Layer for AOS-CX Automation Toolkit
 * Connects to Flask backend running on port 5001
 */

const API_BASE_URL = 'http://localhost:5001/api';

interface ApiResponse<T = any> {
  [key: string]: T;
}

interface SwitchResponse {
  switches: Array<{
    id: string;
    name: string;
    ip_address: string;
    model?: string;
    status: 'online' | 'offline' | 'error';
    last_seen?: string;
    firmware_version?: string;
    error_message?: string;
  }>;
  count: number;
}

interface VLANResponse {
  vlans: Array<{
    id: number;
    name: string;
    admin_state?: string;
    oper_state?: string;
  }>;
}

interface TestConnectionResponse {
  status: 'online' | 'offline' | 'error';
  ip_address: string;
  firmware_version?: string;
  model?: string;
  last_seen?: string;
  error_message?: string;
}

interface CreateVLANRequest {
  switch_ip: string;
  vlan_id: number;
  name: string;
}

interface BulkVLANRequest {
  switch_ips: string[];
  vlans: Array<{
    vlan_id: number;
    name: string;
  }>;
}

class ApiService {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Network error' }));
        throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // Switch Management
  async getSwitches(): Promise<SwitchResponse> {
    return this.request<SwitchResponse>('/switches');
  }

  async addSwitch(ipAddress: string, name?: string): Promise<ApiResponse> {
    return this.request('/switches', {
      method: 'POST',
      body: JSON.stringify({
        ip_address: ipAddress,
        name: name || undefined
      }),
    });
  }

  async removeSwitch(switchIp: string): Promise<ApiResponse> {
    return this.request(`/switches/${switchIp}`, {
      method: 'DELETE',
    });
  }

  async testConnection(switchIp: string): Promise<TestConnectionResponse> {
    return this.request<TestConnectionResponse>(`/switches/${switchIp}/test`);
  }

  // VLAN Management
  async getVLANs(switchIp: string, loadDetails: boolean = true): Promise<VLANResponse> {
    const params = new URLSearchParams({
      switch_ip: switchIp,
      load_details: loadDetails.toString()
    });
    return this.request<VLANResponse>(`/vlans?${params}`);
  }

  async createVLAN(switchIp: string, vlanId: number, name: string): Promise<ApiResponse> {
    return this.request('/vlans', {
      method: 'POST',
      body: JSON.stringify({
        switch_ip: switchIp,
        vlan_id: vlanId,
        name: name
      }),
    });
  }

  async deleteVLAN(switchIp: string, vlanId: number): Promise<ApiResponse> {
    return this.request(`/vlans/${vlanId}`, {
      method: 'DELETE',
      body: JSON.stringify({
        switch_ip: switchIp
      }),
    });
  }

  // Bulk Operations
  async bulkCreateVLANs(switchIps: string[], vlans: Array<{ vlan_id: number; name: string }>): Promise<ApiResponse> {
    return this.request('/bulk/vlans', {
      method: 'POST',
      body: JSON.stringify({
        switch_ips: switchIps,
        vlans: vlans
      }),
    });
  }

  // System Status
  async getSystemStatus(): Promise<ApiResponse> {
    return this.request('/status');
  }

  // Configuration Management
  async exportConfiguration(): Promise<ApiResponse> {
    return this.request('/config/export');
  }

  async importConfiguration(config: object): Promise<ApiResponse> {
    return this.request('/config/import', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  // Debug Endpoints (for development)
  async debugAuth(switchIp: string): Promise<ApiResponse> {
    return this.request(`/debug/test-auth/${switchIp}`);
  }
}

export const apiService = new ApiService();