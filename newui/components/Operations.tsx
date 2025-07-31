import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { 
  Download, 
  Upload, 
  Settings, 
  RefreshCw,
  FileText,
  Archive,
  Zap,
  Shield,
  BarChart3,
  Clock,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { AppState } from '../App';
import { toast } from 'sonner@2.0.3';

interface OperationsProps {
  appState: AppState;
  refreshData: () => Promise<void>;
}

export function Operations({ appState, refreshData }: OperationsProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const { switches, vlans, selectedSwitches } = appState;

  const onlineCount = switches.filter(sw => sw.status === 'online').length;
  const errorCount = switches.filter(sw => sw.status === 'error').length;

  const handleFullExport = async () => {
    setIsExporting(true);
    setExportProgress(0);
    
    try {
      // Simulate export progress
      for (let i = 0; i <= 100; i += 10) {
        setExportProgress(i);
        await new Promise(resolve => setTimeout(resolve, 200));
      }
      
      toast.success('Configuration export completed successfully');
    } catch (error) {
      toast.error('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
      setExportProgress(0);
    }
  };

  const handleSelectedExport = async () => {
    if (selectedSwitches.length === 0) {
      toast.error('Please select switches first');
      return;
    }

    toast.success(`Exporting configuration for ${selectedSwitches.length} selected switches`);
  };

  const handleBulkTest = async () => {
    if (selectedSwitches.length === 0) {
      toast.error('Please select switches first');
      return;
    }

    toast.success(`Running health check on ${selectedSwitches.length} switches`);
  };

  const handleBulkUpdate = async () => {
    if (selectedSwitches.length === 0) {
      toast.error('Please select switches first');
      return;
    }

    toast.success(`Updating configuration on ${selectedSwitches.length} switches`);
  };

  const systemHealth = onlineCount / switches.length * 100;

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold">Operations Center</h2>
        <p className="text-sm text-muted-foreground">
          Bulk operations and system management
        </p>
      </div>

      {/* System Health Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 size={18} />
            System Health
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">Overall Health</span>
            <span className="text-sm font-medium">{Math.round(systemHealth)}%</span>
          </div>
          <Progress value={systemHealth} className="h-2" />
          
          <div className="grid grid-cols-2 gap-4 mt-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-green-600" />
              <span className="text-sm">{onlineCount} Online</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertCircle size={16} className="text-red-600" />
              <span className="text-sm">{errorCount} Issues</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Operations */}
      <Card>
        <CardHeader>
          <CardTitle>Bulk Operations</CardTitle>
          <p className="text-sm text-muted-foreground">
            {selectedSwitches.length > 0 
              ? `${selectedSwitches.length} switches selected`
              : 'Select switches from the Switches tab to enable bulk operations'
            }
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button 
            variant="outline" 
            className="w-full justify-start h-12"
            onClick={handleBulkTest}
            disabled={selectedSwitches.length === 0}
          >
            <Zap size={16} className="mr-3" />
            Run Health Check on Selected
          </Button>

          <Button 
            variant="outline" 
            className="w-full justify-start h-12"
            onClick={handleBulkUpdate}
            disabled={selectedSwitches.length === 0}
          >
            <Settings size={16} className="mr-3" />
            Update Configuration
          </Button>

          <Button 
            variant="outline" 
            className="w-full justify-start h-12"
            onClick={handleSelectedExport}
            disabled={selectedSwitches.length === 0}
          >
            <Download size={16} className="mr-3" />
            Export Selected Switches
          </Button>
        </CardContent>
      </Card>

      {/* Export Operations */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration Export</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isExporting && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Exporting configurations...</span>
                <span>{exportProgress}%</span>
              </div>
              <Progress value={exportProgress} className="h-2" />
            </div>
          )}

          <div className="space-y-3">
            <Button 
              variant="outline" 
              className="w-full justify-start h-12"
              onClick={handleFullExport}
              disabled={isExporting}
            >
              <Archive size={16} className="mr-3" />
              Export All Configurations
            </Button>

            <Button variant="outline" className="w-full justify-start h-12">
              <FileText size={16} className="mr-3" />
              Export VLAN Configurations
            </Button>

            <Button variant="outline" className="w-full justify-start h-12">
              <Upload size={16} className="mr-3" />
              Import Configuration
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Quick Stats */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Statistics</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Total Switches</span>
            <Badge variant="secondary">{switches.length}</Badge>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Active VLANs</span>
            <Badge variant="secondary">{vlans.length}</Badge>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Total Ports</span>
            <Badge variant="secondary">
              {switches.reduce((sum, sw) => sum + sw.portCount, 0)}
            </Badge>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Online Switches</span>
            <Badge className="bg-green-100 text-green-800">{onlineCount}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* System Operations */}
      <Card>
        <CardHeader>
          <CardTitle>System Operations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button 
            variant="outline" 
            className="w-full justify-start h-12"
            onClick={refreshData}
          >
            <RefreshCw size={16} className="mr-3" />
            Refresh All Data
          </Button>

          <Button variant="outline" className="w-full justify-start h-12">
            <Shield size={16} className="mr-3" />
            Security Audit
          </Button>

          <Button variant="outline" className="w-full justify-start h-12">
            <Clock size={16} className="mr-3" />
            Schedule Maintenance
          </Button>

          <Button variant="outline" className="w-full justify-start h-12">
            <Settings size={16} className="mr-3" />
            System Settings
          </Button>
        </CardContent>
      </Card>

      {/* Recent Operations */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Operations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-green-600" />
              <span className="text-sm">Configuration backup</span>
            </div>
            <span className="text-xs text-muted-foreground">2 min ago</span>
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-green-600" />
              <span className="text-sm">Health check completed</span>
            </div>
            <span className="text-xs text-muted-foreground">5 min ago</span>
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="text-green-600" />
              <span className="text-sm">VLAN configuration updated</span>
            </div>
            <span className="text-xs text-muted-foreground">12 min ago</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}