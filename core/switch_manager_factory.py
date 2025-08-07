"""
Factory pattern for selecting appropriate switch manager based on detection logic.
"""
import logging
from typing import Dict, Any, Union
from config.switch_inventory import SwitchInfo
from core.direct_rest_manager import direct_rest_manager
from core.central_manager import central_manager

logger = logging.getLogger(__name__)

class SwitchManagerFactory:
    """Factory for selecting the appropriate manager for switch operations."""
    
    def __init__(self):
        self.detection_cache = {}  # Cache Central detection results
        self.cache_timeout = 3600  # 1 hour cache
    
    def get_manager_for_switch(self, switch_info: SwitchInfo):
        """Get the appropriate manager based on switch configuration and detection."""
        
        # If explicitly configured as Central, use Central manager
        if switch_info.connection_type == "central":
            logger.debug(f"Using Central manager for {switch_info.ip_address} (explicitly configured)")
            return central_manager, self._get_central_config(switch_info)
        
        # For direct connections, use existing detection logic
        elif switch_info.connection_type == "direct":
            logger.debug(f"Using Direct manager for {switch_info.ip_address}")
            return direct_rest_manager, switch_info.ip_address
        
        # Fallback to direct manager
        else:
            logger.warning(f"Unknown connection type {switch_info.connection_type}, defaulting to direct")
            return direct_rest_manager, switch_info.ip_address
    
    def _get_central_config(self, switch_info: SwitchInfo) -> Dict[str, str]:
        """Extract Central configuration from switch info."""
        return {
            'client_id': switch_info.client_id,
            'client_secret': switch_info.client_secret,
            'customer_id': switch_info.customer_id,
            'base_url': switch_info.base_url or 'https://apigw-prod2.central.arubanetworks.com',
            'device_serial': switch_info.device_serial
        }
    
    def test_connection(self, switch_info: SwitchInfo) -> Dict[str, Any]:
        """Test connection using appropriate manager."""
        manager, config = self.get_manager_for_switch(switch_info)
        
        if manager == central_manager:
            return manager.test_connection(config)
        else:
            # Use direct manager with existing detection logic
            result = manager.test_connection(config)
            
            # If Central management is detected via the existing logic,
            # we can suggest switching to Central configuration
            if result.get('is_central_managed'):
                result['suggestion'] = (
                    "This switch appears to be Central-managed. "
                    "Consider adding it as a Central device for full functionality."
                )
            
            return result
    
    def list_vlans(self, switch_info: SwitchInfo, load_details: bool = True) -> list:
        """List VLANs using appropriate manager."""
        manager, config = self.get_manager_for_switch(switch_info)
        
        if manager == central_manager:
            return manager.list_vlans(config)
        else:
            return manager.list_vlans(config, load_details)
    
    def create_vlan(self, switch_info: SwitchInfo, vlan_id: int, name: str) -> str:
        """Create VLAN using appropriate manager."""
        manager, config = self.get_manager_for_switch(switch_info)
        
        if manager == central_manager:
            return manager.create_vlan(config, vlan_id, name)
        else:
            return manager.create_vlan(config, vlan_id, name)
    
    def delete_vlan(self, switch_info: SwitchInfo, vlan_id: int) -> str:
        """Delete VLAN using appropriate manager."""
        manager, config = self.get_manager_for_switch(switch_info)
        
        if manager == central_manager:
            return manager.delete_vlan(config, vlan_id)
        else:
            return manager.delete_vlan(config, vlan_id)
    
    def detect_and_update_management_type(self, switch_info: SwitchInfo) -> Dict[str, Any]:
        """
        Use existing DirectRestManager detection to identify Central management
        and potentially update the switch configuration.
        """
        if switch_info.connection_type == "central":
            # Already configured as Central, no need to detect
            return {
                'is_central_managed': True,
                'management_info': 'Explicitly configured as Central-managed',
                'detection_method': 'configuration'
            }
        
        # Use the existing detection logic in DirectRestManager
        try:
            result = direct_rest_manager.test_connection(switch_info.ip_address)
            
            if result.get('is_central_managed'):
                logger.info(f"Detected Central management for {switch_info.ip_address}")
                
                # Update the switch info to reflect Central management detection
                switch_info.error_message = (
                    "Detected as Central-managed. Add as Central device for full functionality."
                )
                
                return {
                    'is_central_managed': True,
                    'management_info': result.get('management_info'),
                    'detection_method': 'api_test',
                    'suggestion': 'Convert to Central configuration'
                }
            else:
                return {
                    'is_central_managed': False,
                    'management_info': result.get('management_info'),
                    'detection_method': 'api_test'
                }
                
        except Exception as e:
            logger.error(f"Error detecting management type for {switch_info.ip_address}: {e}")
            return {
                'is_central_managed': False,
                'management_info': f'Detection failed: {str(e)}',
                'detection_method': 'error'
            }

# Global factory instance
switch_manager_factory = SwitchManagerFactory()