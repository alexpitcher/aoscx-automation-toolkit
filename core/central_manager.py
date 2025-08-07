"""
Aruba Central API integration for managing Central-managed switches.
"""
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

try:
    from pycentral.base import ArubaCentralBase
    from pycentral.configuration import Devices
    from pycentral.monitoring import Sites
    PYCENTRAL_AVAILABLE = True
except ImportError:
    # Create dummy classes for type hints when pycentral is not available
    class ArubaCentralBase:
        pass
    
    class Devices:
        pass
    
    PYCENTRAL_AVAILABLE = False
    logging.warning("pycentral not available - Central integration disabled")

from config.switch_inventory import inventory

logger = logging.getLogger(__name__)

class CentralManager:
    """Aruba Central API manager with unified interface matching DirectRestManager."""
    
    def __init__(self):
        """Initialize Central manager."""
        self.central_connections = {}  # Cache Central connections per set of credentials
        self.device_cache = {}  # Cache device info to reduce API calls
        self.device_cache_timeout = 300  # 5 minutes
        
        if not PYCENTRAL_AVAILABLE:
            logger.error("pycentral library not available - install with: pip install pycentral")
    
    def _get_central_connection(self, client_id: str, client_secret: str, customer_id: str, base_url: str) -> Optional[ArubaCentralBase]:
        """Get or create Central API connection."""
        if not PYCENTRAL_AVAILABLE:
            raise Exception("pycentral library not available")
        
        # Create connection key for caching
        conn_key = f"{base_url}:{customer_id}:{client_id}"
        
        if conn_key in self.central_connections:
            return self.central_connections[conn_key]
        
        try:
            central_info = {
                "client_id": client_id,
                "client_secret": client_secret,
                "customer_id": customer_id,
                "base_url": base_url
            }
            
            central = ArubaCentralBase(central_info=central_info)
            
            # Test connection by getting token
            token_info = central.getToken()
            if not token_info or token_info.get('status_code') != 200:
                raise Exception(f"Failed to authenticate with Central: {token_info}")
            
            self.central_connections[conn_key] = central
            logger.info(f"Successfully connected to Aruba Central at {base_url}")
            return central
            
        except Exception as e:
            logger.error(f"Failed to connect to Central: {e}")
            raise Exception(f"Central connection failed: {str(e)}")
    
    def _get_device_info(self, central: ArubaCentralBase, device_serial: str) -> Optional[Dict[str, Any]]:
        """Get device information from Central."""
        try:
            # Check cache first
            cache_key = f"{device_serial}_{int(time.time() // self.device_cache_timeout)}"
            if cache_key in self.device_cache:
                return self.device_cache[cache_key]
            
            # Get device inventory
            devices = Devices()
            devices.session = central.session
            
            # Get all devices and find our target
            response = devices.get_devices()
            if response.get('status_code') != 200:
                raise Exception(f"Failed to get device inventory: {response}")
            
            devices_list = response.get('data', {}).get('devices', [])
            
            for device in devices_list:
                if device.get('serial') == device_serial:
                    # Cache the result
                    self.device_cache[cache_key] = device
                    return device
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting device info for {device_serial}: {e}")
            return None
    
    def test_connection(self, central_config: Dict[str, str]) -> Dict[str, Any]:
        """Test connection to Central-managed device."""
        try:
            # Extract Central configuration
            client_id = central_config.get('client_id')
            client_secret = central_config.get('client_secret')
            customer_id = central_config.get('customer_id')
            base_url = central_config.get('base_url', 'https://apigw-prod2.central.arubanetworks.com')
            device_serial = central_config.get('device_serial')
            
            if not all([client_id, client_secret, customer_id, device_serial]):
                return {
                    'status': 'error',
                    'device_serial': device_serial,
                    'error_message': 'Missing required Central configuration (client_id, client_secret, customer_id, device_serial)'
                }
            
            # Get Central connection
            central = self._get_central_connection(client_id, client_secret, customer_id, base_url)
            
            # Get device information
            device_info = self._get_device_info(central, device_serial)
            
            if not device_info:
                return {
                    'status': 'error',
                    'device_serial': device_serial,
                    'error_message': f'Device {device_serial} not found in Central inventory'
                }
            
            # Check device status
            device_status = device_info.get('status', 'unknown').lower()
            if device_status != 'up':
                return {
                    'status': 'offline',
                    'device_serial': device_serial,
                    'error_message': f'Device status: {device_status}'
                }
            
            return {
                'status': 'online',
                'device_serial': device_serial,
                'ip_address': device_info.get('ip_address', 'Unknown'),
                'firmware_version': device_info.get('firmware_version', 'Unknown'),
                'model': device_info.get('model', 'Unknown'),
                'site': device_info.get('site', 'Unknown'),
                'is_central_managed': True,
                'management_info': 'Managed by Aruba Central',
                'last_seen': datetime.now().isoformat(),
                'error_message': None
            }
            
        except Exception as e:
            logger.error(f"Error testing Central connection: {e}")
            return {
                'status': 'error',
                'device_serial': central_config.get('device_serial', 'unknown'),
                'error_message': str(e)
            }
    
    def list_vlans(self, central_config: Dict[str, str]) -> List[Dict[str, Any]]:
        """List VLANs from Central-managed device."""
        try:
            # Extract configuration
            client_id = central_config.get('client_id')
            client_secret = central_config.get('client_secret')
            customer_id = central_config.get('customer_id')
            base_url = central_config.get('base_url', 'https://apigw-prod2.central.arubanetworks.com')
            device_serial = central_config.get('device_serial')
            
            if not all([client_id, client_secret, customer_id, device_serial]):
                raise Exception('Missing required Central configuration')
            
            # Get Central connection
            central = self._get_central_connection(client_id, client_secret, customer_id, base_url)
            
            # Get VLANs using Central configuration API
            # Note: Central API endpoints may vary - this is a representative implementation
            api_url = f"/configuration/v1/devices/{device_serial}/vlans"
            
            response = central.command(apiMethod="GET", apiPath=api_url)
            
            if response.get('status_code') != 200:
                raise Exception(f"Failed to get VLANs from Central: {response}")
            
            vlans_data = response.get('data', {}).get('vlans', [])
            vlan_list = []
            
            for vlan in vlans_data:
                vlan_list.append({
                    'id': vlan.get('vlan_id', 0),
                    'name': vlan.get('name', f"VLAN{vlan.get('vlan_id', 0)}"),
                    'admin_state': vlan.get('admin_state', 'unknown'),
                    'oper_state': vlan.get('oper_state', 'unknown'),
                    'details_loaded': True,
                    'source': 'central'
                })
            
            logger.info(f"Retrieved {len(vlan_list)} VLANs from Central for device {device_serial}")
            return sorted(vlan_list, key=lambda x: x['id'])
            
        except Exception as e:
            error_msg = f"Error listing VLANs from Central: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def create_vlan(self, central_config: Dict[str, str], vlan_id: int, name: str) -> str:
        """Create VLAN through Central API."""
        # Input validation
        if not (1 <= vlan_id <= 4094):
            raise ValueError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")
        
        if not name or not name.strip():
            raise ValueError("VLAN name cannot be empty")
        
        name = name.strip()
        
        try:
            # Extract configuration
            client_id = central_config.get('client_id')
            client_secret = central_config.get('client_secret')
            customer_id = central_config.get('customer_id')
            base_url = central_config.get('base_url', 'https://apigw-prod2.central.arubanetworks.com')
            device_serial = central_config.get('device_serial')
            
            if not all([client_id, client_secret, customer_id, device_serial]):
                raise Exception('Missing required Central configuration')
            
            # Get Central connection
            central = self._get_central_connection(client_id, client_secret, customer_id, base_url)
            
            # Create VLAN using Central configuration API
            api_url = f"/configuration/v1/devices/{device_serial}/vlans"
            
            vlan_data = {
                "vlan_id": vlan_id,
                "name": name,
                "admin_state": "up"
            }
            
            response = central.command(
                apiMethod="POST",
                apiPath=api_url,
                apiData=vlan_data
            )
            
            if response.get('status_code') in [200, 201]:
                logger.info(f"Successfully created VLAN {vlan_id} ({name}) via Central for device {device_serial}")
                return f"Successfully created VLAN {vlan_id} ('{name}') via Aruba Central for device {device_serial}"
            else:
                error_msg = f"Failed to create VLAN via Central: {response}"
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Error creating VLAN {vlan_id} via Central: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def delete_vlan(self, central_config: Dict[str, str], vlan_id: int) -> str:
        """Delete VLAN through Central API."""
        # Safety check: don't delete default VLANs
        if vlan_id == 1:
            raise ValueError("Cannot delete default VLAN 1")
        
        try:
            # Extract configuration
            client_id = central_config.get('client_id')
            client_secret = central_config.get('client_secret')
            customer_id = central_config.get('customer_id')
            base_url = central_config.get('base_url', 'https://apigw-prod2.central.arubanetworks.com')
            device_serial = central_config.get('device_serial')
            
            if not all([client_id, client_secret, customer_id, device_serial]):
                raise Exception('Missing required Central configuration')
            
            # Get Central connection
            central = self._get_central_connection(client_id, client_secret, customer_id, base_url)
            
            # Delete VLAN using Central configuration API
            api_url = f"/configuration/v1/devices/{device_serial}/vlans/{vlan_id}"
            
            response = central.command(apiMethod="DELETE", apiPath=api_url)
            
            if response.get('status_code') in [200, 204]:
                logger.info(f"Successfully deleted VLAN {vlan_id} via Central for device {device_serial}")
                return f"Successfully deleted VLAN {vlan_id} via Aruba Central for device {device_serial}"
            else:
                error_msg = f"Failed to delete VLAN via Central: {response}"
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Error deleting VLAN {vlan_id} via Central: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def bounce_port(self, central_config: Dict[str, str], interface: str) -> str:
        """Bounce interface through Central Actions API."""
        try:
            # Extract configuration
            client_id = central_config.get('client_id')
            client_secret = central_config.get('client_secret')
            customer_id = central_config.get('customer_id')
            base_url = central_config.get('base_url', 'https://apigw-prod2.central.arubanetworks.com')
            device_serial = central_config.get('device_serial')
            
            if not all([client_id, client_secret, customer_id, device_serial]):
                raise Exception('Missing required Central configuration')
            
            # Get Central connection
            central = self._get_central_connection(client_id, client_secret, customer_id, base_url)
            
            # Bounce port using Central Actions API
            api_url = "/platform/device_inventory/v1/devices/action"
            
            action_data = {
                "device_list": [device_serial],
                "action": "bounce_interface",
                "parameters": {
                    "interface": interface
                }
            }
            
            response = central.command(
                apiMethod="POST",
                apiPath=api_url,
                apiData=action_data
            )
            
            if response.get('status_code') in [200, 202]:
                logger.info(f"Successfully initiated port bounce for {interface} via Central for device {device_serial}")
                return f"Successfully initiated port bounce for {interface} via Aruba Central for device {device_serial}"
            else:
                error_msg = f"Failed to bounce port via Central: {response}"
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Error bouncing port {interface} via Central: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

# Global Central manager instance
central_manager = CentralManager()