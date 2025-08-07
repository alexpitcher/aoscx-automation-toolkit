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
    
    # Connection type and Central configuration
    connection_type: str = "direct"  # "direct" or "central"
    device_serial: Optional[str] = None  # For Central-managed devices
    client_id: Optional[str] = None      # Central OAuth2 credentials
    client_secret: Optional[str] = None
    customer_id: Optional[str] = None
    base_url: Optional[str] = None       # Central API base URL
    site: Optional[str] = None           # Central site information
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'ip_address': self.ip_address,
            'name': self.name or self.ip_address,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'firmware_version': self.firmware_version,
            'model': self.model,
            'error_message': self.error_message,
            'connection_type': self.connection_type,
            'device_serial': self.device_serial,
            'site': self.site
        }

class SwitchInventory:
    """Manages the inventory of Aruba CX switches."""
    
    def __init__(self):
        self._switches: Dict[str, SwitchInfo] = {}
        self._credentials: Dict[str, Dict[str, str]] = {}  # Store credentials per switch
        
    def add_switch(self, ip_address: str, name: Optional[str] = None, 
                   connection_type: str = "direct", **kwargs) -> bool:
        """Add a switch to the inventory."""
        if connection_type == "direct":
            if not self.is_valid_ip(ip_address):
                return False
        
        self._switches[ip_address] = SwitchInfo(
            ip_address=ip_address,
            name=name,
            connection_type=connection_type,
            **kwargs
        )
        logger.info(f"Added {connection_type} switch {ip_address} to inventory")
        return True
    
    def add_central_switch(self, device_serial: str, name: Optional[str] = None,
                          client_id: str = None, client_secret: str = None,
                          customer_id: str = None, base_url: str = None) -> bool:
        """Add a Central-managed switch to the inventory."""
        # Use device serial as the key for Central devices
        switch_key = f"central:{device_serial}"
        
        self._switches[switch_key] = SwitchInfo(
            ip_address=switch_key,  # Use as identifier
            name=name or device_serial,
            connection_type="central",
            device_serial=device_serial,
            client_id=client_id,
            client_secret=client_secret,
            customer_id=customer_id,
            base_url=base_url or "https://apigw-prod2.central.arubanetworks.com"
        )
        logger.info(f"Added Central-managed switch {device_serial} to inventory")
        return True
    
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
    
    def store_credentials(self, switch_ip: str, username: str, password: str) -> None:
        """Store credentials for a switch."""
        self._credentials[switch_ip] = {
            'username': username,
            'password': password or ''
        }
        logger.debug(f"Stored credentials for switch {switch_ip}")
    
    def get_saved_credentials(self, switch_ip: str) -> Optional[Dict[str, str]]:
        """Get saved credentials for a switch."""
        return self._credentials.get(switch_ip)
    
    def remove_credentials(self, switch_ip: str) -> None:
        """Remove stored credentials for a switch."""
        if switch_ip in self._credentials:
            del self._credentials[switch_ip]
            logger.debug(f"Removed credentials for switch {switch_ip}")
    
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