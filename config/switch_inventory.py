"""
Switch inventory management for multi-switch operations.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class SwitchInfo:
    """Information about a managed switch."""
    ip_address: str
    name: Optional[str] = None
    status: str = "unknown"  # online, offline, error, unknown
    last_seen: Optional[datetime] = None
    firmware_version: Optional[str] = None
    model: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'ip_address': self.ip_address,
            'name': self.name or self.ip_address,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'firmware_version': self.firmware_version,
            'model': self.model,
            'error_message': self.error_message
        }

class SwitchInventory:
    """Manages the inventory of Aruba CX switches."""
    
    def __init__(self):
        self._switches: Dict[str, SwitchInfo] = {}
        
    def add_switch(self, ip_address: str, name: Optional[str] = None) -> bool:
        """Add a switch to the inventory."""
        if self.is_valid_ip(ip_address):
            self._switches[ip_address] = SwitchInfo(
                ip_address=ip_address,
                name=name
            )
            logger.info(f"Added switch {ip_address} to inventory")
            return True
        return False
    
    def remove_switch(self, ip_address: str) -> bool:
        """Remove a switch from the inventory."""
        if ip_address in self._switches:
            del self._switches[ip_address]
            logger.info(f"Removed switch {ip_address} from inventory")
            return True
        return False
    
    def get_switch(self, ip_address: str) -> Optional[SwitchInfo]:
        """Get switch information by IP address."""
        return self._switches.get(ip_address)
    
    def get_all_switches(self) -> List[SwitchInfo]:
        """Get all switches in inventory."""
        return list(self._switches.values())
    
    def update_switch_status(self, ip_address: str, status: str, 
                           error_message: Optional[str] = None,
                           firmware_version: Optional[str] = None,
                           model: Optional[str] = None):
        """Update switch status and metadata."""
        if ip_address in self._switches:
            switch = self._switches[ip_address]
            switch.status = status
            switch.last_seen = datetime.now() if status == "online" else switch.last_seen
            switch.error_message = error_message
            if firmware_version:
                switch.firmware_version = firmware_version
            if model:
                switch.model = model
    
    def get_online_switches(self) -> List[SwitchInfo]:
        """Get only switches that are currently online."""
        return [switch for switch in self._switches.values() 
                if switch.status == "online"]
    
    def get_switch_count(self) -> Dict[str, int]:
        """Get count of switches by status."""
        counts = {"total": len(self._switches), "online": 0, "offline": 0, "error": 0}
        for switch in self._switches.values():
            if switch.status in counts:
                counts[switch.status] += 1
        return counts
    
    @staticmethod
    def is_valid_ip(ip_address: str) -> bool:
        """Basic IP address validation."""
        try:
            parts = ip_address.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except (ValueError, AttributeError):
            return False

# Global inventory instance
inventory = SwitchInventory()