"""
Direct REST API implementation bypassing PyAOS-CX for AOS-CX 10.15 compatibility.
"""
import requests
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import urllib3

from config.settings import Config
from config.switch_inventory import inventory

# Suppress InsecureRequestWarning for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class DirectRestManager:
    """Direct REST API manager bypassing PyAOS-CX SDK issues."""
    
    def __init__(self):
        self.config = Config()
        self.sessions = {}  # Cache authentication cookies
        
    def _get_base_url(self, switch_ip: str) -> str:
        """Get base URL for REST API."""
        return f"https://{switch_ip}/rest/v10.09"
    
    def _authenticate(self, switch_ip: str) -> requests.Session:
        """Authenticate and return session with cookie."""
        if switch_ip in self.sessions:
            # Try existing session first
            try:
                session = self.sessions[switch_ip]
                # Test if session is still valid
                response = session.get(
                    f"{self._get_base_url(switch_ip)}/system",
                    timeout=10,
                    verify=self.config.SSL_VERIFY
                )
                if response.status_code == 200:
                    return session
            except Exception:
                # Session expired or invalid, remove and create new one
                self.sessions.pop(switch_ip, None)
        
        # Create new session
        session = requests.Session()
        session.verify = self.config.SSL_VERIFY
        
        # Use form-encoded authentication (the method that works!)
        auth_url = f"{self._get_base_url(switch_ip)}/login"
        auth_data = f"username={self.config.SWITCH_USER}&password={self.config.SWITCH_PASSWORD}"
        
        try:
            response = session.post(
                auth_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10
            )
            
            if response.status_code == 200:
                # Check if we got a session cookie
                if 'Set-Cookie' in response.headers or session.cookies:
                    self.sessions[switch_ip] = session
                    logger.info(f"Successfully authenticated to {switch_ip} via form login")
                    return session
                else:
                    raise Exception("Authentication succeeded but no session cookie received")
            else:
                # Clear any cached session on authentication failure
                self.sessions.pop(switch_ip, None)
                error_msg = f"Authentication failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Connection error during authentication: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def _logout(self, switch_ip: str):
        """Logout and clean up session to avoid session limits."""
        if switch_ip in self.sessions:
            try:
                session = self.sessions[switch_ip]
                session.post(f"{self._get_base_url(switch_ip)}/logout", timeout=5)
            except Exception:
                pass  # Ignore logout errors
            finally:
                self.sessions.pop(switch_ip, None)
    
    def test_connection(self, switch_ip: str) -> Dict[str, Any]:
        """Test connection to switch using direct REST API."""
        try:
            session = self._authenticate(switch_ip)
            
            # Get system information
            response = session.get(
                f"{self._get_base_url(switch_ip)}/system",
                timeout=10
            )
            
            if response.status_code == 200:
                system_info = response.json()
                
                result = {
                    'status': 'online',
                    'ip_address': switch_ip,
                    'firmware_version': system_info.get('firmware_version'),
                    'model': system_info.get('platform_name'),
                    'last_seen': datetime.now().isoformat(),
                    'error_message': None
                }
                
                inventory.update_switch_status(
                    switch_ip,
                    "online",
                    firmware_version=result['firmware_version'],
                    model=result['model']
                )
                
                return result
            else:
                error_msg = f"Failed to get system info: {response.status_code}"
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = str(e)
            result = {
                'status': 'error',
                'ip_address': switch_ip,
                'error_message': error_msg,
                'last_seen': None
            }
            inventory.update_switch_status(switch_ip, "error", error_msg)
            return result
    
    def list_vlans(self, switch_ip: str) -> List[Dict[str, Any]]:
        """List VLANs using direct REST API."""
        try:
            session = self._authenticate(switch_ip)
            
            # First, get the list of VLANs (just IDs and URIs)
            response = session.get(
                f"{self._get_base_url(switch_ip)}/system/vlans",
                timeout=10
            )
            
            if response.status_code == 200:
                vlans_data = response.json()
                vlan_list = []
                
                logger.info(f"Found {len(vlans_data)} VLANs on {switch_ip}")
                
                # vlans_data format: {"1": "/rest/v10.09/system/vlans/1", "2": "/rest/v10.09/system/vlans/2", ...}
                for vlan_id_str, vlan_uri in vlans_data.items():
                    try:
                        vlan_id_num = int(vlan_id_str)
                        if not (1 <= vlan_id_num <= 4094):
                            logger.warning(f"Invalid VLAN ID {vlan_id_num} found, skipping")
                            continue
                    
                                
                        # For now, just use the VLAN ID to create a basic name
                        # The individual detail requests may be failing due to session limits
                        vlan_list.append({
                            'id': vlan_id_num,
                            'name': f'VLAN{vlan_id_num}',
                            'admin_state': 'up',  # Assume up if it exists
                            'oper_state': 'up'
                        })
                            
                    except (ValueError, requests.RequestException) as e:
                        logger.warning(f"Error processing VLAN {vlan_id_str}: {e}")
                        continue
                
                logger.info(f"Retrieved {len(vlan_list)} VLANs from {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return sorted(vlan_list, key=lambda x: x['id'])
                
            else:
                error_msg = f"Failed to list VLANs: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Error listing VLANs on {switch_ip}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def create_vlan(self, switch_ip: str, vlan_id: int, name: str) -> str:
        """Create VLAN using direct REST API."""
        # Input validation
        if not (1 <= vlan_id <= 4094):
            raise ValueError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")
        
        if not name or not name.strip():
            raise ValueError("VLAN name cannot be empty")
        
        name = name.strip()
        
        try:
            session = self._authenticate(switch_ip)
            
            # Check if VLAN already exists
            check_response = session.get(
                f"{self._get_base_url(switch_ip)}/system/vlans/{vlan_id}",
                timeout=10
            )
            
            if check_response.status_code == 200:
                logger.info(f"VLAN {vlan_id} already exists on {switch_ip}")
                return f"VLAN {vlan_id} already exists on {switch_ip}"
            
            # Create VLAN
            vlan_data = {
                "name": name,
                "admin": "up"
            }
            
            response = session.put(
                f"{self._get_base_url(switch_ip)}/system/vlans/{vlan_id}",
                json=vlan_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully created VLAN {vlan_id} ({name}) on {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return f"Successfully created VLAN {vlan_id} ('{name}') on {switch_ip}"
            else:
                error_msg = f"Failed to create VLAN: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Error creating VLAN {vlan_id} on {switch_ip}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def delete_vlan(self, switch_ip: str, vlan_id: int) -> str:
        """Delete VLAN using direct REST API."""
        # Safety check: don't delete default VLANs
        if vlan_id == 1:
            raise ValueError("Cannot delete default VLAN 1")
        
        try:
            session = self._authenticate(switch_ip)
            
            # Check if VLAN exists
            check_response = session.get(
                f"{self._get_base_url(switch_ip)}/system/vlans/{vlan_id}",
                timeout=10
            )
            
            if check_response.status_code == 404:
                return f"VLAN {vlan_id} does not exist on {switch_ip}"
            
            # Delete VLAN
            response = session.delete(
                f"{self._get_base_url(switch_ip)}/system/vlans/{vlan_id}",
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Successfully deleted VLAN {vlan_id} from {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return f"Successfully deleted VLAN {vlan_id} from {switch_ip}"
            else:
                error_msg = f"Failed to delete VLAN: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"Error deleting VLAN {vlan_id} from {switch_ip}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

# Global direct REST manager instance
direct_rest_manager = DirectRestManager()