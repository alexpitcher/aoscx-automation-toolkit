import React from 'react';
import { BarChart3, Router, Network, Settings } from 'lucide-react';

interface BottomNavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { id: 'switches', label: 'Switches', icon: Router },
  { id: 'vlans', label: 'VLANs', icon: Network },
  { id: 'operations', label: 'Operations', icon: Settings }
];

export function BottomNavigation({ activeTab, onTabChange }: BottomNavigationProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-border z-50">
      <div className="flex">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`flex-1 px-2 py-3 flex flex-col items-center justify-center min-h-[60px] touch-manipulation ${
                isActive 
                  ? 'text-[#01A982] bg-green-50' 
                  : 'text-muted-foreground'
              }`}
            >
              <Icon size={20} className="mb-1" />
              <span className="text-xs">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}