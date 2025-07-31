import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import { 
  Plus, 
  Router, 
  Wifi, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle,
  MoreVertical,
  Trash2,
  Settings,
  Activity
} from 'lucide-react';
import { AddSwitchSheet } from './AddSwitchSheet';
import { SwitchDetailSheet } from './SwitchDetailSheet';
import { AppState, Switch } from '../App';

interface SwitchesProps {
  appState: AppState;
  updateAppState: (updates: Partial<AppState>) => void;
  addSwitch: (switch_: Omit<Switch, 'id'>) => void;
  removeSwitch: (switchId: string) => void;
}

export function Switches({ appState, updateAppState, addSwitch, removeSwitch }: SwitchesProps) {
  const [showAddSheet, setShowAddSheet] = useState(false);
  const [selectedSwitch, setSelectedSwitch] = useState<Switch | null>(null);
  const { switches, selectedSwitches } = appState;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online': return <CheckCircle2 size={16} className="text-green-600" />;
      case 'offline': return <XCircle size={16} className="text-gray-500" />;
      case 'error': return <AlertTriangle size={16} className="text-red-600" />;
      default: return <XCircle size={16} className="text-gray-500" />;
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

  const toggleSwitchSelection = (switchId: string) => {
    const newSelected = selectedSwitches.includes(switchId)
      ? selectedSwitches.filter(id => id !== switchId)
      : [...selectedSwitches, switchId];
    
    updateAppState({ selectedSwitches: newSelected });
  };

  const selectAllSwitches = () => {
    const allOnline = switches.filter(sw => sw.status === 'online').map(sw => sw.id);
    updateAppState({ selectedSwitches: allOnline });
  };

  const clearSelection = () => {
    updateAppState({ selectedSwitches: [] });
  };

  return (
    <div className="p-4 space-y-4">
      {/* Header with Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Switch Inventory</h2>
          <p className="text-sm text-muted-foreground">
            {switches.length} switches • {switches.filter(sw => sw.status === 'online').length} online
          </p>
        </div>
        <Button onClick={() => setShowAddSheet(true)} size="sm" className="bg-[#0052cc] hover:bg-[#0052cc]/90">
          <Plus size={16} />
          Add
        </Button>
      </div>

      {/* Bulk Actions */}
      {selectedSwitches.length > 0 && (
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium">
                  {selectedSwitches.length} selected
                </span>
                <Button variant="outline" size="sm" onClick={clearSelection}>
                  Clear
                </Button>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Settings size={16} />
                  Configure
                </Button>
                <Button variant="outline" size="sm">
                  <Activity size={16} />
                  Test
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Selection Actions */}
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={selectAllSwitches}>
          Select Online
        </Button>
        {selectedSwitches.length > 0 && (
          <Button variant="outline" size="sm" onClick={clearSelection}>
            Clear ({selectedSwitches.length})
          </Button>
        )}
      </div>

      {/* Switch List */}
      <div className="space-y-3">
        {switches.map((switch_) => (
          <Card key={switch_.id} className="relative">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                {/* Selection Checkbox */}
                <Checkbox
                  checked={selectedSwitches.includes(switch_.id)}
                  onCheckedChange={() => toggleSwitchSelection(switch_.id)}
                  disabled={switch_.status !== 'online'}
                  className="mt-1"
                />

                {/* Switch Info */}
                <div 
                  className="flex-1 cursor-pointer"
                  onClick={() => setSelectedSwitch(switch_)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(switch_.status)}
                      <span className="font-medium">{switch_.name}</span>
                    </div>
                    <Badge className={getStatusBadgeClass(switch_.status)}>
                      {switch_.status}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground mb-3">
                    <div>IP: {switch_.ipAddress}</div>
                    <div>Model: {switch_.model}</div>
                    <div>Ports: {switch_.portCount}</div>
                    <div>VLANs: {switch_.vlanCount}</div>
                  </div>

                  {switch_.status === 'online' && (
                    <div className="text-xs text-muted-foreground">
                      Uptime: {switch_.uptime}
                    </div>
                  )}
                  
                  {switch_.status !== 'online' && (
                    <div className="text-xs text-muted-foreground">
                      Last seen: {switch_.lastSeen.toLocaleString()}
                    </div>
                  )}
                </div>

                {/* Action Menu */}
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-8 w-8 p-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedSwitch(switch_);
                  }}
                >
                  <MoreVertical size={16} />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Empty State */}
      {switches.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <Router className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-medium mb-2">No switches configured</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Add your first Aruba switch to get started
            </p>
            <Button onClick={() => setShowAddSheet(true)} className="bg-[#0052cc] hover:bg-[#0052cc]/90">
              <Plus size={16} className="mr-2" />
              Add Switch
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Add Switch Sheet */}
      <AddSwitchSheet
        open={showAddSheet}
        onOpenChange={setShowAddSheet}
        onAddSwitch={addSwitch}
      />

      {/* Switch Detail Sheet */}
      <SwitchDetailSheet
        switch_={selectedSwitch}
        open={!!selectedSwitch}
        onOpenChange={(open) => !open && setSelectedSwitch(null)}
        onRemove={removeSwitch}
      />
    </div>
  );
}