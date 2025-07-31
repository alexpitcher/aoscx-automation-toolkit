import React, { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Network, Router, AlertCircle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner@2.0.3';
import { Switch, VLAN } from '../App';

interface CreateVLANSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateVLAN: (vlan: Omit<VLAN, 'id'>) => void;
  switches: Switch[];
}

interface FormData {
  name: string;
  vlanId: string;
  description: string;
  switchIds: string[];
  ports: string;
}

export function CreateVLANSheet({ open, onOpenChange, onCreateVLAN, switches }: CreateVLANSheetProps) {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    vlanId: '',
    description: '',
    switchIds: [],
    ports: ''
  });
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [isCreating, setIsCreating] = useState(false);

  const validateForm = () => {
    const newErrors: Partial<FormData> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'VLAN name is required';
    }

    const vlanIdNum = parseInt(formData.vlanId);
    if (!formData.vlanId.trim()) {
      newErrors.vlanId = 'VLAN ID is required';
    } else if (isNaN(vlanIdNum) || vlanIdNum < 1 || vlanIdNum > 4094) {
      newErrors.vlanId = 'VLAN ID must be between 1 and 4094';
    }

    if (formData.switchIds.length === 0) {
      newErrors.switchIds = 'Select at least one switch';
    }

    if (!formData.ports.trim()) {
      newErrors.ports = 'Port configuration is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsCreating(true);

    try {
      // Simulate VLAN creation delay
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const newVLAN: Omit<VLAN, 'id'> = {
        name: formData.name,
        vlanId: parseInt(formData.vlanId),
        description: formData.description,
        switchIds: formData.switchIds,
        ports: formData.ports.split(',').map(p => p.trim()).filter(Boolean)
      };

      onCreateVLAN(newVLAN);
      toast.success(`VLAN ${formData.name} created successfully on ${formData.switchIds.length} switch${formData.switchIds.length !== 1 ? 'es' : ''}`);
      onOpenChange(false);
      resetForm();
    } catch (error) {
      toast.error('Failed to create VLAN. Please try again.');
    } finally {
      setIsCreating(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      vlanId: '',
      description: '',
      switchIds: [],
      ports: ''
    });
    setErrors({});
  };

  const handleClose = () => {
    if (!isCreating) {
      onOpenChange(false);
      resetForm();
    }
  };

  const toggleSwitch = (switchId: string) => {
    setFormData(prev => ({
      ...prev,
      switchIds: prev.switchIds.includes(switchId)
        ? prev.switchIds.filter(id => id !== switchId)
        : [...prev.switchIds, switchId]
    }));
  };

  const selectAllSwitches = () => {
    setFormData(prev => ({
      ...prev,
      switchIds: switches.map(sw => sw.id)
    }));
  };

  const clearSwitchSelection = () => {
    setFormData(prev => ({ ...prev, switchIds: [] }));
  };

  return (
    <Sheet open={open} onOpenChange={handleClose}>
      <SheetContent side="bottom" className="h-[90vh] overflow-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Network size={20} />
            Create New VLAN
          </SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* VLAN Basic Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">VLAN Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* VLAN Name */}
              <div className="space-y-2">
                <Label htmlFor="name">VLAN Name</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="e.g., Guest WiFi"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  className={errors.name ? 'border-red-500' : ''}
                />
                {errors.name && (
                  <div className="flex items-center gap-1 text-sm text-red-600">
                    <AlertCircle size={14} />
                    {errors.name}
                  </div>
                )}
              </div>

              {/* VLAN ID */}
              <div className="space-y-2">
                <Label htmlFor="vlanId">VLAN ID</Label>
                <Input
                  id="vlanId"
                  type="number"
                  placeholder="100"
                  min="1"
                  max="4094"
                  value={formData.vlanId}
                  onChange={(e) => setFormData(prev => ({ ...prev, vlanId: e.target.value }))}
                  className={errors.vlanId ? 'border-red-500' : ''}
                />
                {errors.vlanId && (
                  <div className="flex items-center gap-1 text-sm text-red-600">
                    <AlertCircle size={14} />
                    {errors.vlanId}
                  </div>
                )}
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  placeholder="Brief description of this VLAN's purpose"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={2}
                />
              </div>
            </CardContent>
          </Card>

          {/* Switch Selection */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center justify-between">
                Target Switches
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={selectAllSwitches}>
                    Select All
                  </Button>
                  <Button type="button" variant="outline" size="sm" onClick={clearSwitchSelection}>
                    Clear
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {switches.map((switch_) => (
                <div key={switch_.id} className="flex items-center space-x-3">
                  <Checkbox
                    id={`switch-${switch_.id}`}
                    checked={formData.switchIds.includes(switch_.id)}
                    onCheckedChange={() => toggleSwitch(switch_.id)}
                  />
                  <div className="flex items-center gap-2 flex-1">
                    <CheckCircle2 size={16} className="text-green-600" />
                    <div>
                      <div className="font-medium">{switch_.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {switch_.ipAddress} • {switch_.model}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              
              {switches.length === 0 && (
                <div className="text-center py-4 text-muted-foreground">
                  <Router className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No online switches available</p>
                </div>
              )}

              {errors.switchIds && (
                <div className="flex items-center gap-1 text-sm text-red-600">
                  <AlertCircle size={14} />
                  {errors.switchIds}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Port Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Port Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="ports">Port Ranges</Label>
                <Input
                  id="ports"
                  type="text"
                  placeholder="e.g., 1-8, 10, 15-20"
                  value={formData.ports}
                  onChange={(e) => setFormData(prev => ({ ...prev, ports: e.target.value }))}
                  className={errors.ports ? 'border-red-500' : ''}
                />
                {errors.ports && (
                  <div className="flex items-center gap-1 text-sm text-red-600">
                    <AlertCircle size={14} />
                    {errors.ports}
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Specify port ranges or individual ports (comma-separated)
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isCreating}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isCreating || switches.length === 0}
              className="flex-1 bg-[#0052cc] hover:bg-[#0052cc]/90"
            >
              {isCreating ? 'Creating VLAN...' : 'Create VLAN'}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}