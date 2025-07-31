import React, { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Loader2, Router, Wifi, AlertCircle } from 'lucide-react';
import { toast } from 'sonner@2.0.3';

interface AddSwitchSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAddSwitch: (ipAddress: string, name?: string) => Promise<void>;
}

interface FormData {
  name: string;
  ipAddress: string;
}

export function AddSwitchSheet({ open, onOpenChange, onAddSwitch }: AddSwitchSheetProps) {
  const [formData, setFormData] = useState<FormData>({
    name: '',
    ipAddress: ''
  });
  const [isConnecting, setIsConnecting] = useState(false);
  const [errors, setErrors] = useState<Partial<FormData>>({});

  const validateIP = (ip: string) => {
    const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipRegex.test(ip);
  };

  const validateForm = () => {
    const newErrors: Partial<FormData> = {};

    if (!formData.ipAddress.trim()) {
      newErrors.ipAddress = 'IP address is required';
    } else if (!validateIP(formData.ipAddress)) {
      newErrors.ipAddress = 'Please enter a valid IP address';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsConnecting(true);

    try {
      await onAddSwitch(
        formData.ipAddress.trim(), 
        formData.name.trim() || undefined
      );
      
      toast.success(`Switch ${formData.ipAddress} added successfully`);
      onOpenChange(false);
      resetForm();
    } catch (error: any) {
      console.error('Failed to add switch:', error);
      toast.error(error.message || 'Failed to add switch. Please check the IP address and try again.');
    } finally {
      setIsConnecting(false);
    }
  };

  const resetForm = () => {
    setFormData({ name: '', ipAddress: '' });
    setErrors({});
  };

  const handleClose = () => {
    if (!isConnecting) {
      onOpenChange(false);
      resetForm();
    }
  };

  return (
    <Sheet open={open} onOpenChange={handleClose}>
      <SheetContent side="bottom" className="h-[90vh] overflow-auto">
        <SheetHeader className="mb-6">
          <SheetTitle className="flex items-center gap-2">
            <Router size={20} />
            Add New Switch
          </SheetTitle>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Switch Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Switch Name (Optional)</Label>
            <Input
              id="name"
              type="text"
              placeholder="e.g., Core-SW-01"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            />
          </div>

          {/* IP Address */}
          <div className="space-y-2">
            <Label htmlFor="ipAddress">IP Address</Label>
            <Input
              id="ipAddress"
              type="text"
              placeholder="192.168.1.10"
              value={formData.ipAddress}
              onChange={(e) => setFormData(prev => ({ ...prev, ipAddress: e.target.value }))}
              className={errors.ipAddress ? 'border-red-500' : ''}
            />
            {errors.ipAddress && (
              <div className="flex items-center gap-1 text-sm text-red-600">
                <AlertCircle size={14} />
                {errors.ipAddress}
              </div>
            )}
          </div>

          {/* Info Box */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <Wifi size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-green-800">
                <p className="font-medium mb-1">Switch Requirements</p>
                <ul className="list-disc list-inside space-y-1 text-xs">
                  <li>HPE Aruba CX switch with REST API enabled</li>
                  <li>Valid credentials configured in backend</li>
                  <li>Network connectivity to switch management interface</li>
                  <li>Switch must not be Central-managed for full functionality</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isConnecting}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isConnecting}
              className="flex-1 bg-[#01A982] hover:bg-[#01A982]/90"
            >
              {isConnecting ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Adding Switch...
                </>
              ) : (
                'Add Switch'
              )}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  );
}