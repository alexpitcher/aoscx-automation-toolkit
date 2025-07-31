import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { 
  Plus, 
  Network, 
  Router,
  MoreVertical,
  Trash2,
  Edit,
  Copy
} from 'lucide-react';
import { CreateVLANSheet } from './CreateVLANSheet';
import { VLANDetailSheet } from './VLANDetailSheet';
import { AppState, VLAN } from '../App';

interface VLANsProps {
  appState: AppState;
  addVLAN: (vlan: Omit<VLAN, 'id'>) => void;
  removeVLAN: (vlanId: string) => void;
}

export function VLANs({ appState, addVLAN, removeVLAN }: VLANsProps) {
  const [showCreateSheet, setShowCreateSheet] = useState(false);
  const [selectedVLAN, setSelectedVLAN] = useState<VLAN | null>(null);
  const { vlans, switches } = appState;

  const getVLANSwitchNames = (vlan: VLAN) => {
    return vlan.switchIds
      .map(id => switches.find(sw => sw.id === id)?.name)
      .filter(Boolean)
      .join(', ');
  };

  const onlineSwitches = switches.filter(sw => sw.status === 'online');

  return (
    <div className="p-4 space-y-4">
      {/* Header with Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">VLAN Management</h2>
          <p className="text-sm text-muted-foreground">
            {vlans.length} VLANs configured across {switches.length} switches
          </p>
        </div>
        <Button 
          onClick={() => setShowCreateSheet(true)} 
          size="sm" 
          className="bg-[#0052cc] hover:bg-[#0052cc]/90"
          disabled={onlineSwitches.length === 0}
        >
          <Plus size={16} />
          Create
        </Button>
      </div>

      {/* No Online Switches Warning */}
      {onlineSwitches.length === 0 && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-yellow-800">
              <Router size={16} />
              <span className="text-sm font-medium">
                No online switches available for VLAN configuration
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* VLAN Statistics */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center mb-2">
              <Network className="h-6 w-6 text-[#0052cc]" />
            </div>
            <div className="text-2xl font-semibold">{vlans.length}</div>
            <div className="text-sm text-muted-foreground">Total VLANs</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center mb-2">
              <Router className="h-6 w-6 text-green-600" />
            </div>
            <div className="text-2xl font-semibold">{onlineSwitches.length}</div>
            <div className="text-sm text-muted-foreground">Online Switches</div>
          </CardContent>
        </Card>
      </div>

      {/* VLAN List */}
      <div className="space-y-3">
        {vlans.map((vlan) => (
          <Card key={vlan.id} className="relative">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                {/* VLAN Info */}
                <div 
                  className="flex-1 cursor-pointer"
                  onClick={() => setSelectedVLAN(vlan)}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <Network size={18} className="text-[#0052cc]" />
                    <div>
                      <div className="font-medium">{vlan.name}</div>
                      <div className="text-sm text-muted-foreground">VLAN {vlan.vlanId}</div>
                    </div>
                    <Badge variant="secondary" className="ml-auto">
                      {vlan.switchIds.length} switch{vlan.switchIds.length !== 1 ? 'es' : ''}
                    </Badge>
                  </div>

                  {vlan.description && (
                    <p className="text-sm text-muted-foreground mb-2">
                      {vlan.description}
                    </p>
                  )}

                  <div className="space-y-1 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">Switches:</span>
                      <span className="truncate">{getVLANSwitchNames(vlan) || 'None'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">Ports:</span>
                      <span>{vlan.ports.join(', ') || 'Not configured'}</span>
                    </div>
                  </div>
                </div>

                {/* Action Menu */}
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-8 w-8 p-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedVLAN(vlan);
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
      {vlans.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <Network className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-medium mb-2">No VLANs configured</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Create your first VLAN to segment network traffic
            </p>
            <Button 
              onClick={() => setShowCreateSheet(true)} 
              className="bg-[#0052cc] hover:bg-[#0052cc]/90"
              disabled={onlineSwitches.length === 0}
            >
              <Plus size={16} className="mr-2" />
              Create VLAN
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create VLAN Sheet */}
      <CreateVLANSheet
        open={showCreateSheet}
        onOpenChange={setShowCreateSheet}
        onCreateVLAN={addVLAN}
        switches={onlineSwitches}
      />

      {/* VLAN Detail Sheet */}
      <VLANDetailSheet
        vlan={selectedVLAN}
        switches={switches}
        open={!!selectedVLAN}
        onOpenChange={(open) => !open && setSelectedVLAN(null)}
        onRemove={removeVLAN}
      />
    </div>
  );
}