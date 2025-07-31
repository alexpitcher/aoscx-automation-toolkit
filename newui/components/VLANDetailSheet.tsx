import React from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { 
  Network, 
  Router,
  Trash2,
  Edit,
  Copy,
  Download
} from 'lucide-react';
import { VLAN, Switch } from '../App';
import { toast } from 'sonner@2.0.3';

interface VLANDetailSheetProps {
  vlan: VLAN | null;
  switches: Switch[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRemove: (vlanId: string) => void;
}

export function VLANDetailSheet({ vlan, switches, open, onOpenChange, onRemove }: VLANDetailSheetProps) {
  if (!vlan) return null;

  const getVLANSwitches = () => {
    return vlan.switchIds
      .map(id => switches.find(sw => sw.id === id))
      .filter(Boolean) as Switch[];
  };

  const vlanSwitches = getVLANSwitches();

  const handleRemove = () => {
    if (confirm(`Are you sure you want to remove VLAN ${vlan.name}? This action cannot be undone.`)) {
      onRemove(vlan.id);
      onOpenChange(false);
      toast.success(`VLAN ${vlan.name} removed`);
    }
  };

  const handleCopy = () => {
    toast.success('VLAN configuration copied to clipboard');
  };

  const handleExport = () => {
    toast.success('VLAN configuration export started');
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="h-[90vh] overflow-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Network size={20} />
            {vlan.name}
          </SheetTitle>
        </SheetHeader>

        <div className="space-y-6">
          {/* VLAN Overview */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="font-medium text-lg">{vlan.name}</div>
                  <div className="text-sm text-muted-foreground">VLAN ID: {vlan.vlanId}</div>
                </div>
                <Badge variant="secondary">
                  {vlan.switchIds.length} switch{vlan.switchIds.length !== 1 ? 'es' : ''}
                </Badge>
              </div>

              {vlan.description && (
                <p className="text-sm text-muted-foreground mb-4">
                  {vlan.description}
                </p>
              )}

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">VLAN ID</div>
                  <div className="font-medium">{vlan.vlanId}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Switches</div>
                  <div className="font-medium">{vlan.switchIds.length}</div>
                </div>
                <div className="col-span-2">
                  <div className="text-muted-foreground">Port Configuration</div>
                  <div className="font-medium">{vlan.ports.join(', ')}</div>
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
              <Button variant="outline" className="w-full justify-start h-12">
                <Edit size={16} className="mr-3" />
                Edit VLAN Configuration
              </Button>

              <Button 
                variant="outline" 
                className="w-full justify-start h-12"
                onClick={handleCopy}
              >
                <Copy size={16} className="mr-3" />
                Copy Configuration
              </Button>

              <Button 
                variant="outline" 
                className="w-full justify-start h-12"
                onClick={handleExport}
              >
                <Download size={16} className="mr-3" />
                Export to Script
              </Button>
            </CardContent>
          </Card>

          {/* Associated Switches */}
          <Card>
            <CardHeader>
              <CardTitle>Associated Switches</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {vlanSwitches.map((switch_) => (
                <div key={switch_.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-3">
                    <Router size={16} className="text-[#0052cc]" />
                    <div>
                      <div className="font-medium">{switch_.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {switch_.ipAddress}
                      </div>
                    </div>
                  </div>
                  <Badge 
                    className={
                      switch_.status === 'online' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-gray-100 text-gray-800'
                    }
                  >
                    {switch_.status}
                  </Badge>
                </div>
              ))}

              {vlanSwitches.length === 0 && (
                <div className="text-center py-4 text-muted-foreground">
                  <Router className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No switches configured</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* VLAN Statistics */}
          <Card>
            <CardHeader>
              <CardTitle>Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Ports</span>
                <span>{vlan.ports.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Active Switches</span>
                <span>{vlanSwitches.filter(sw => sw.status === 'online').length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Configuration Status</span>
                <span className="text-green-600">Active</span>
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
                Remove VLAN
              </Button>
              <p className="text-xs text-muted-foreground mt-2">
                This will remove the VLAN from all associated switches. This action cannot be undone.
              </p>
            </CardContent>
          </Card>
        </div>
      </SheetContent>
    </Sheet>
  );
}