import React, { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { 
  Router, 
  Wifi, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle,
  Trash2,
  Settings,
  Activity,
  Network,
  Download,
  RefreshCw
} from 'lucide-react';
import { Switch } from '../App';
import { toast } from 'sonner@2.0.3';

interface SwitchDetailSheetProps {
  switch_: Switch | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRemove: (switchId: string) => void;
}

export function SwitchDetailSheet({ switch_, open, onOpenChange, onRemove }: SwitchDetailSheetProps) {
  const [isTestingConnection, setIsTestingConnection] = useState(false);

  if (!switch_) return null;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle2 size={20} className="text-green-600" />;
      case 'offline': return <XCircle size={20} className="text-gray-500" />;
      case 'error': return <AlertTriangle size={20} className="text-red-600" />;
      default: return <XCircle size={20} className="text-gray-500" />;
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'online': return 'bg-green-100 text-green-800';
      case 'offline': return 'bg-gray-100 text-gray-800';
      case 'error': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    
    try {
      // Simulate connection test
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Simulate test result
      const testResult = Math.random() > 0.3;
      
      if (testResult) {
        toast.success('Connection test successful');
      } else {
        toast.error('Connection test failed');
      }
    } catch (error) {
      toast.error('Connection test failed');
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleRemove = () => {
    if (confirm(`Are you sure you want to remove ${switch_.name}? This action cannot be undone.`)) {
      onRemove(switch_.id);
      onOpenChange(false);
      toast.success(`Switch ${switch_.name} removed`);
    }
  };

  const handleExportConfig = () => {
    toast.success('Configuration export started');
    // Simulate export
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="h-[90vh] overflow-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Router size={20} />
            {switch_.name}
          </SheetTitle>
        </SheetHeader>

        <div className="space-y-6">
          {/* Status Header */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  {getStatusIcon(switch_.status)}
                  <div>
                    <div className="font-medium">{switch_.name}</div>
                    <div className="text-sm text-muted-foreground">{switch_.ipAddress}</div>
                  </div>
                </div>
                <Badge className={getStatusBadgeClass(switch_.status)}>
                  {switch_.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Model</div>
                  <div className="font-medium">{switch_.model}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Ports</div>
                  <div className="font-medium">{switch_.portCount}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">VLANs</div>
                  <div className="font-medium">{switch_.vlanCount}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Uptime</div>
                  <div className="font-medium">{switch_.uptime}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                variant="outline" 
                className="w-full justify-start h-12"
                onClick={handleTestConnection}
                disabled={isTestingConnection}
              >
                <Activity size={16} className={`mr-3 ${isTestingConnection ? 'animate-spin' : ''}`} />
                {isTestingConnection ? 'Testing Connection...' : 'Test Connection'}
              </Button>

              <Button variant="outline" className="w-full justify-start h-12">
                <Network size={16} className="mr-3" />
                Manage VLANs
              </Button>

              <Button 
                variant="outline" 
                className="w-full justify-start h-12"
                onClick={handleExportConfig}
              >
                <Download size={16} className="mr-3" />
                Export Configuration
              </Button>

              <Button variant="outline" className="w-full justify-start h-12">
                <Settings size={16} className="mr-3" />
                Advanced Settings
              </Button>
            </CardContent>
          </Card>

          {/* System Information */}
          <Card>
            <CardHeader>
              <CardTitle>System Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last Seen</span>
                <span>{switch_.lastSeen.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Management IP</span>
                <span>{switch_.ipAddress}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Switch Model</span>
                <span>{switch_.model}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Port Count</span>
                <span>{switch_.portCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Active VLANs</span>
                <span>{switch_.vlanCount}</span>
              </div>
            </CardContent>
          </Card>

          {/* Network Stats */}
          <Card>
            <CardHeader>
              <CardTitle>Network Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">CPU Usage</span>
                <span className="text-green-600">12%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Memory Usage</span>
                <span className="text-blue-600">34%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Temperature</span>
                <span>42°C</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Power Consumption</span>
                <span>125W</span>
              </div>
            </CardContent>
          </Card>

          {/* Danger Zone */}
          <Card className="border-red-200">
            <CardHeader>
              <CardTitle className="text-red-600">Danger Zone</CardTitle>
            </CardHeader>
            <CardContent>
              <Button 
                variant="destructive" 
                className="w-full justify-start h-12"
                onClick={handleRemove}
              >
                <Trash2 size={16} className="mr-3" />
                Remove Switch
              </Button>
              <p className="text-xs text-muted-foreground mt-2">
                This action cannot be undone. The switch will be removed from the inventory.
              </p>
            </CardContent>
          </Card>
        </div>
      </SheetContent>
    </Sheet>
  );
}