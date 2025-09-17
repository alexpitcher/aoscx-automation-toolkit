import React, { useState, useEffect } from 'react';
import { Dashboard } from './components/Dashboard';
import { Switches } from './components/Switches';
import { VLANs } from './components/VLANs';
import { Operations } from './components/Operations';
import { BottomNavigation } from './components/BottomNavigation';
import { Toaster } from './components/ui/sonner';
import { apiService } from './services/api';

export interface Switch {
  id: string;
  name: string;
  ip_address: string;
  model?: string;
  status: 'online' | 'offline' | 'error';
  last_seen?: string;
  firmware_version?: string;
  error_message?: string;
}

export interface VLAN {
  id: number;
  name: string;
  admin_state?: string;
  oper_state?: string;
}

export interface AppState {
  switches: Switch[];
  vlans: VLAN[];
  selectedSwitches: string[];
  isLoading: boolean;
  lastRefresh: Date;
  selectedSwitchIp?: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [appState, setAppState] = useState<AppState>({
    switches: [],
    vlans: [],
    selectedSwitches: [],
    isLoading: false,
    lastRefresh: new Date(),
    selectedSwitchIp: undefined
  });

  // Load initial data
  useEffect(() => {
    loadSwitches();
  }, []);

  // Auto-refresh data every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadSwitches();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const loadSwitches = async () => {
    try {
      setAppState(prev => ({ ...prev, isLoading: true }));
      const response = await apiService.getSwitches();
      setAppState(prev => ({
        ...prev,
        switches: response.switches || [],
        lastRefresh: new Date(),
        isLoading: false
      }));
    } catch (error) {
      console.error('Error loading switches:', error);
      setAppState(prev => ({ ...prev, isLoading: false }));
    }
  };

  const loadVLANs = async (switchIp: string) => {
    try {
      setAppState(prev => ({ ...prev, isLoading: true }));
      const response = await apiService.getVLANs(switchIp);
      setAppState(prev => ({
        ...prev,
        vlans: response.vlans || [],
        selectedSwitchIp: switchIp,
        lastRefresh: new Date(),
        isLoading: false
      }));
    } catch (error) {
      console.error('Error loading VLANs:', error);
      setAppState(prev => ({ ...prev, isLoading: false }));
    }
  };

  const updateAppState = (updates: Partial<AppState>) => {
    setAppState(prev => ({ ...prev, ...updates }));
  };

  const addSwitch = async (ipAddress: string, name?: string) => {
    try {
      await apiService.addSwitch(ipAddress, name);
      await loadSwitches(); // Reload to get updated list
    } catch (error) {
      console.error('Error adding switch:', error);
      throw error;
    }
  };

  const removeSwitch = async (switchIp: string) => {
    try {
      await apiService.removeSwitch(switchIp);
      setAppState(prev => ({
        ...prev,
        switches: prev.switches.filter(sw => sw.ip_address !== switchIp),
        selectedSwitches: prev.selectedSwitches.filter(ip => ip !== switchIp)
      }));
    } catch (error) {
      console.error('Error removing switch:', error);
      throw error;
    }
  };

  const testConnection = async (switchIp: string) => {
    try {
      const result = await apiService.testConnection(switchIp);
      // Update switch status in local state
      setAppState(prev => ({
        ...prev,
        switches: prev.switches.map(sw => 
          sw.ip_address === switchIp 
            ? { ...sw, status: result.status as any, last_seen: result.last_seen }
            : sw
        )
      }));
      return result;
    } catch (error) {
      console.error('Error testing connection:', error);
      throw error;
    }
  };

  const createVLAN = async (switchIp: string, vlanId: number, name: string) => {
    try {
      await apiService.createVLAN(switchIp, vlanId, name);
      // Reload VLANs if we're viewing this switch
      if (appState.selectedSwitchIp === switchIp) {
        await loadVLANs(switchIp);
      }
    } catch (error) {
      console.error('Error creating VLAN:', error);
      throw error;
    }
  };

  const refreshData = async () => {
    await loadSwitches();
    if (appState.selectedSwitchIp) {
      await loadVLANs(appState.selectedSwitchIp);
    }
  };

  const renderActiveTab = () => {
    const props = {
      appState,
      updateAppState,
      addSwitch,
      removeSwitch,
      testConnection,
      createVLAN,
      loadVLANs,
      refreshData
    };

    switch (activeTab) {
      case 'dashboard':
        return <Dashboard {...props} />;
      case 'switches':
        return <Switches {...props} />;
      case 'vlans':
        return <VLANs {...props} />;
      case 'operations':
        return <Operations {...props} />;
      default:
        return <Dashboard {...props} />;
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="bg-[#01A982] text-white p-4 shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-white">CXEdit</h1>
            <p className="text-xs text-green-100 opacity-90">HPE Aruba Network Management</p>
          </div>
          <div className="text-right">
            <div className="text-xs text-green-100 opacity-90">
              Last updated: {appState.lastRefresh.toLocaleTimeString()}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-auto" style={{ paddingBottom: 'calc(5rem + env(safe-area-inset-bottom))' }}>
        {renderActiveTab()}
      </main>

      {/* Bottom Navigation */}
      <BottomNavigation activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Toast Notifications */}
      <Toaster />
    </div>
  );
}
