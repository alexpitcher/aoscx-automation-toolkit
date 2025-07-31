import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { 
  RefreshCw, 
  Router, 
  Wifi, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle,
  TrendingUp,
  Activity,
  Network
} from 'lucide-react';
import { AppState, Switch } from '../App';

interface DashboardProps {
  appState: AppState;
  refreshData: () => Promise<void>;
  testConnection: (switchIp: string) => Promise<any>;
}

export function Dashboard({ appState, refreshData, testConnection }: DashboardProps) {
  const { switches, isLoading, lastRefresh } = appState;
  
  const onlineCount = switches.filter(sw => sw.status === 'online').length;
  const offlineCount = switches.filter(sw => sw.status === 'offline').length;
  const errorCount = switches.filter(sw => sw.status === 'error').length;

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online': return 'text-green-600';
      case 'offline': return 'text-gray-500';
      case 'error': return 'text-red-600';
      default: return 'text-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle2 size={16} className="text-green-600" />;
      case 'offline': return <XCircle size={16} className="text-gray-500" />;
      case 'error': return <AlertTriangle size={16} className="text-red-600" />;
      default: return <XCircle size={16} className="text-gray-500" />;
    }
  };

  const handleQuickTest = async (switchIp: string) => {
    try {
      await testConnection(switchIp);
    } catch (error) {
      console.error('Quick test failed:', error);
    }
  };

  const systemHealth = switches.length > 0 ? (onlineCount / switches.length) * 100 : 0;

  return (
    <div className="p-4 space-y-6">
      {/* Quick Stats */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center mb-2">
              <Router className="h-6 w-6 text-[#01A982]" />
            </div>
            <div className="text-2xl font-semibold">{switches.length}</div>
            <div className="text-sm text-muted-foreground">Total Switches</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center mb-2">
              <Activity className="h-6 w-6 text-green-600" />
            </div>
            <div className="text-2xl font-semibold text-green-600">{onlineCount}</div>
            <div className="text-sm text-muted-foreground">Online</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center mb-2">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
            <div className="text-2xl font-semibold text-red-600">{errorCount}</div>
            <div className="text-sm text-muted-foreground">Errors</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center mb-2">
              <TrendingUp className="h-6 w-6 text-[#01A982]" />
            </div>
            <div className="text-2xl font-semibold">{Math.round(systemHealth)}%</div>
            <div className="text-sm text-muted-foreground">Health</div>
          </CardContent>
        </Card>
      </div>

      {/* Status Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Network Status
            <Button 
              variant="outline" 
              size="sm" 
              onClick={refreshData}
              disabled={isLoading}
              className="h-8"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={20} className="text-green-600" />
              <span>Online Switches</span>
            </div>
            <Badge variant="secondary" className="bg-green-100 text-green-800">
              {onlineCount}
            </Badge>
          </div>
          
          {offlineCount > 0 && (
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <XCircle size={20} className="text-gray-500" />
                <span>Offline Switches</span>
              </div>
              <Badge variant="secondary" className="bg-gray-100 text-gray-800">
                {offlineCount}
              </Badge>
            </div>
          )}
          
          {errorCount > 0 && (
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <AlertTriangle size={20} className="text-red-600" />
                <span>Error Switches</span>
              </div>
              <Badge variant="destructive">
                {errorCount}
              </Badge>
            </div>
          )}

          {switches.length === 0 && (
            <div className="text-center py-4 text-muted-foreground">
              <Router className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No switches configured</p>
              <p className="text-xs">Add switches to get started</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Switch Status List */}
      {switches.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Switch Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {switches.slice(0, 4).map((switch_) => (
                <div key={switch_.ip_address} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(switch_.status)}
                    <div>
                      <div className="font-medium">{switch_.name || switch_.ip_address}</div>
                      <div className="text-sm text-muted-foreground">
                        {switch_.ip_address}
                        {switch_.model && ` • ${switch_.model}`}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <Badge 
                      variant={switch_.status === 'online' ? 'default' : 'secondary'}
                      className={
                        switch_.status === 'online' 
                          ? 'bg-green-100 text-green-800' 
                          : switch_.status === 'error'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-gray-100 text-gray-800'
                      }
                    >
                      {switch_.status}
                    </Badge>
                    {switch_.last_seen && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(switch_.last_seen).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-3">
          <Button 
            variant="outline" 
            className="h-12 flex flex-col gap-1"
            onClick={() => window.location.hash = '#switches'}
          >
            <Router size={16} />
            <span className="text-xs">Add Switch</span>
          </Button>
          <Button 
            variant="outline" 
            className="h-12 flex flex-col gap-1"
            onClick={() => window.location.hash = '#vlans'}
          >
            <Network size={16} />
            <span className="text-xs">Manage VLANs</span>
          </Button>
          <Button 
            variant="outline" 
            className="h-12 flex flex-col gap-1"
            onClick={refreshData}
            disabled={isLoading}
          >
            <Activity size={16} className={isLoading ? 'animate-spin' : ''} />
            <span className="text-xs">Refresh All</span>
          </Button>
          <Button 
            variant="outline" 
            className="h-12 flex flex-col gap-1"
            onClick={() => window.location.hash = '#operations'}
          >
            <TrendingUp size={16} />
            <span className="text-xs">Operations</span>
          </Button>
        </CardContent>
      </Card>

      {/* Last Updated */}
      <div className="text-center text-xs text-muted-foreground pb-4">
        Last updated: {lastRefresh.toLocaleString()}
      </div>
    </div>
  );
}