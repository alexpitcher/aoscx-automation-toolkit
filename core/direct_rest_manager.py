"""
Direct REST API implementation with VLAN name support and Central management detection.
"""
import requests
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import urllib3

from config.settings import Config
from config.switch_inventory import inventory

# Suppress InsecureRequestWarning for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class DirectRestManager:
    """Direct REST API manager with VLAN names and Central management detection."""
    
    def __init__(self):
        self.config = Config()
        self.sessions = {}  # Cache authentication cookies
        self.switch_api_versions = {}  # Track which API version works per switch
        self.session_timeouts = {}  # Track when sessions should expire
        
    def cleanup_session(self, switch_ip: str, force_logout: bool = True):
        """Explicitly cleanup session for a switch."""
        if switch_ip in self.sessions:
            try:
                if force_logout:
                    session = self.sessions[switch_ip]
                    base_url = self._get_base_url(switch_ip)
                    # Attempt explicit logout
                    logout_response = session.post(f"{base_url}/logout", timeout=5)
                    logger.debug(f"Logout response for {switch_ip}: {logout_response.status_code}")
            except Exception as e:
                logger.debug(f"Error during logout for {switch_ip}: {e}")
            finally:
                # Always remove from cache
                self.sessions.pop(switch_ip, None)
                self.session_timeouts.pop(switch_ip, None)
                logger.info(f"Cleaned up session for {switch_ip}")

    def cleanup_all_sessions(self):
        """Clean up all cached sessions."""
        switch_ips = list(self.sessions.keys())
        for switch_ip in switch_ips:
            self.cleanup_session(switch_ip, force_logout=True)
        logger.info("Cleaned up all sessions")
    
    def test_connection_with_credentials(self, switch_ip: str, username: str, password: str) -> Dict[str, Any]:
        """Test connection to switch with specific credentials."""
        try:
            # Create a temporary session for testing
            test_session = requests.Session()
            test_session.verify = Config.SSL_VERIFY
            
            # Attempt authentication
            auth_url = f"https://{switch_ip}/rest/{Config.API_VERSION}/login"
            auth_data = {
                'username': username,
                'password': password or ''
            }
            
            logger.debug(f"Testing authentication to {switch_ip} with username: {username}")
            
            auth_response = test_session.post(
                auth_url,
                json=auth_data,
                timeout=10,
                verify=Config.SSL_VERIFY
            )
            
            if auth_response.status_code == 200:
                # Test system access
                system_url = f"https://{switch_ip}/rest/{Config.API_VERSION}/system"
                system_response = test_session.get(
                    system_url,
                    timeout=10,
                    verify=Config.SSL_VERIFY
                )
                
                if system_response.status_code == 200:
                    system_info = system_response.json()
                    
                    # Cleanup test session
                    try:
                        test_session.post(f"https://{switch_ip}/rest/{Config.API_VERSION}/logout", timeout=5)
                    except:
                        pass
                    
                    return {
                        'status': 'online',
                        'ip_address': switch_ip,
                        'firmware_version': system_info.get('firmware_version', 'Unknown'),
                        'model': system_info.get('platform_name', 'Unknown'),
                        'last_seen': datetime.now().isoformat()
                    }
                else:
                    logger.warning(f"Authentication succeeded but system access failed for {switch_ip}: {system_response.status_code}")
                    return {
                        'status': 'error',
                        'ip_address': switch_ip,
                        'error_message': f'System access failed (HTTP {system_response.status_code})'
                    }
            elif auth_response.status_code == 401:
                return {
                    'status': 'error',
                    'ip_address': switch_ip,
                    'error_message': 'Authentication failed - invalid credentials'
                }
            else:
                return {
                    'status': 'error',
                    'ip_address': switch_ip,
                    'error_message': f'Authentication request failed (HTTP {auth_response.status_code})'
                }
                
        except requests.exceptions.ConnectTimeout:
            return {
                'status': 'offline',
                'ip_address': switch_ip,
                'error_message': 'Connection timeout'
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'offline',
                'ip_address': switch_ip,
                'error_message': 'Connection refused'
            }
        except Exception as e:
            logger.error(f"Error testing credentials for {switch_ip}: {e}")
            return {
                'status': 'error',
                'ip_address': switch_ip,
                'error_message': str(e)
            }

    def _is_session_valid(self, switch_ip: str, session: requests.Session) -> bool:
        """Check if session is still valid."""
        try:
            # Check if session has expired based on our timeout
            if switch_ip in self.session_timeouts:
                if time.time() > self.session_timeouts[switch_ip]:
                    logger.debug(f"Session for {switch_ip} has expired")
                    return False
            
            # Quick validation request
            base_url = self._get_base_url(switch_ip)
            response = session.get(f"{base_url}/system", timeout=5)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 401:
                logger.debug(f"Session for {switch_ip} is unauthorized")
                return False
            else:
                logger.debug(f"Session validation failed for {switch_ip}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.debug(f"Session validation error for {switch_ip}: {e}")
            return False
        
    def _detect_api_version(self, switch_ip: str) -> str:
        """Detect which API version to use for this switch."""
        if switch_ip in self.switch_api_versions:
            return self.switch_api_versions[switch_ip]
            
        # Test API versions in order of preference
        test_versions = ['v1', 'v10.09', 'v10.04', 'latest']
        
        for version in test_versions:
            try:
                session = requests.Session()
                session.verify = self.config.SSL_VERIFY
                
                auth_url = f"https://{switch_ip}/rest/{version}/login"
                auth_data = f"username={self.config.SWITCH_USER}&password={self.config.SWITCH_PASSWORD}"
                
                response = session.post(
                    auth_url,
                    data=auth_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    # Test if VLAN operations work with this version
                    vlans_url = f"https://{switch_ip}/rest/{version}/system/vlans"
                    vlans_response = session.get(vlans_url, timeout=10)
                    
                    if vlans_response.status_code == 200:
                        logger.info(f"Switch {switch_ip}: Using API version {version}")
                        self.switch_api_versions[switch_ip] = version
                        # Clean up test session
                        try:
                            session.post(f"https://{switch_ip}/rest/{version}/logout", timeout=5)
                        except:
                            pass
                        return version
                    elif vlans_response.status_code == 410:
                        logger.info(f"Switch {switch_ip}: API {version} auth works but VLANs blocked (Central?)")
                        continue
                        
            except Exception as e:
                logger.debug(f"API version {version} failed for {switch_ip}: {e}")
                continue
        
        # Default fallback
        default_version = 'v10.09'
        logger.warning(f"Switch {switch_ip}: No optimal API version found, using {default_version}")
        self.switch_api_versions[switch_ip] = default_version
        return default_version
    
    def _get_base_url(self, switch_ip: str) -> str:
        """Get base URL for REST API with proper version detection."""
        api_version = self._detect_api_version(switch_ip)
        return f"https://{switch_ip}/rest/{api_version}"
    
    def _authenticate(self, switch_ip: str) -> requests.Session:
        """Authenticate and return session with improved session management."""
        # Check existing session first
        if switch_ip in self.sessions:
            session = self.sessions[switch_ip]
            if self._is_session_valid(switch_ip, session):
                logger.debug(f"Reusing valid session for {switch_ip}")
                return session
            else:
                # Session expired or invalid, clean it up
                logger.debug(f"Session invalid for {switch_ip}, creating new one")
                self.cleanup_session(switch_ip, force_logout=False)
        
        # Create new session with retry logic for session limits
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                session = requests.Session()
                session.verify = self.config.SSL_VERIFY
                
                base_url = self._get_base_url(switch_ip)
                auth_url = f"{base_url}/login"
                auth_data = f"username={self.config.SWITCH_USER}&password={self.config.SWITCH_PASSWORD}"
                
                logger.debug(f"Authentication attempt {attempt + 1} for {switch_ip}")
                
                response = session.post(
                    auth_url,
                    data=auth_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    # Check if we got session cookies
                    if 'Set-Cookie' in response.headers or session.cookies:
                        # Set session timeout (15 minutes from now)
                        self.session_timeouts[switch_ip] = time.time() + (15 * 60)
                        self.sessions[switch_ip] = session
                        logger.info(f"Successfully authenticated to {switch_ip} (attempt {attempt + 1})")
                        return session
                    else:
                        raise Exception("Authentication succeeded but no session cookie received")
                        
                elif response.status_code == 503 and "session limit" in response.text.lower():
                    # Handle session limit specifically
                    logger.warning(f"Session limit reached on {switch_ip}, attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        # Try to clean up any existing sessions and wait
                        self.cleanup_session(switch_ip, force_logout=True)
                        logger.info(f"Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise Exception(f"Session limit reached after {max_retries} attempts")
                else:
                    # Other authentication failures
                    error_msg = f"Authentication failed: {response.status_code} - {response.text[:200]}"
                    if attempt == max_retries - 1:
                        raise Exception(error_msg)
                    logger.warning(f"{error_msg}, retrying...")
                    
            except requests.exceptions.RequestException as e:
                error_msg = f"Connection error during authentication: {str(e)}"
                if attempt == max_retries - 1:
                    raise Exception(error_msg)
                logger.warning(f"{error_msg}, retrying...")
                time.sleep(retry_delay)
        
        raise Exception(f"Authentication failed after {max_retries} attempts")
    
    def _detect_central_management(self, switch_ip: str, session: requests.Session) -> tuple[bool, str]:
        """Detect if switch is Central-managed by testing write operations."""
        try:
            base_url = self._get_base_url(switch_ip)
            
            # Test write operation by attempting invalid VLAN creation
            test_response = session.post(
                f"{base_url}/system/vlans", 
                json={"id": 99999, "name": "central_test", "admin": "up"}, 
                timeout=5
            )
            
            if test_response.status_code == 410:
                return True, "Central management detected - write operations blocked"
            elif test_response.status_code == 400:
                # 400 Bad Request means endpoint works but data is invalid (good sign)
                return False, "Direct API access available"
            elif test_response.status_code == 403:
                return True, "Write operations forbidden - likely Central managed"
            else:
                return False, f"API test response: {test_response.status_code}"
                
        except Exception as e:
            logger.debug(f"Central detection error for {switch_ip}: {e}")
            return False, "Unable to determine management type"
    
    def test_connection(self, switch_ip: str) -> Dict[str, Any]:
        """Test connection to switch with Central management detection."""
        try:
            session = self._authenticate(switch_ip)
            base_url = self._get_base_url(switch_ip)
            
            # Get system information
            response = session.get(f"{base_url}/system", timeout=10)
            
            if response.status_code == 200:
                system_info = response.json()
                
                # Detect Central management
                is_central_managed, central_msg = self._detect_central_management(switch_ip, session)
                
                result = {
                    'status': 'online',
                    'ip_address': switch_ip,
                    'firmware_version': system_info.get('software_version'),
                    'model': system_info.get('platform_name'),
                    'api_version': self.switch_api_versions.get(switch_ip, 'unknown'),
                    'is_central_managed': is_central_managed,
                    'management_info': central_msg,
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
                'is_central_managed': False,
                'management_info': None,
                'last_seen': None
            }
            inventory.update_switch_status(switch_ip, "error", error_msg)
            return result
        finally:
            # Clean up session after connection test
            self.cleanup_session(switch_ip, force_logout=True)
    
    def list_vlans(self, switch_ip: str, load_details: bool = True) -> List[Dict[str, Any]]:
        """
        List VLANs with REAL VLAN NAMES using depth=2 parameter or individual requests.
        """
        try:
            session = self._authenticate(switch_ip)
            base_url = self._get_base_url(switch_ip)
            api_version = self.switch_api_versions.get(switch_ip, 'v1')
            
            if load_details and api_version in ['v10.04', 'v10.09', 'v10.15', 'latest']:
                # Use depth=2 and selector=configuration for bulk VLAN details (v10.x APIs)
                response = session.get(
                    f"{base_url}/system/vlans?depth=2&selector=configuration", 
                    timeout=15
                )
                
                if response.status_code == 200:
                    vlans_data = response.json()
                    vlan_list = []
                    
                    logger.info(f"Retrieved detailed VLANs using depth=2 from {switch_ip}")
                    
                    for vlan_id_str, vlan_detail in vlans_data.items():
                        try:
                            vlan_id_num = int(vlan_id_str)
                            if not (1 <= vlan_id_num <= 4094):
                                continue
                            
                            vlan_list.append({
                                'id': vlan_id_num,
                                'name': vlan_detail.get('name', f'VLAN{vlan_id_num}'),
                                'admin_state': vlan_detail.get('admin', 'unknown'),
                                'oper_state': 'up',  # Not available in configuration selector
                                'details_loaded': True
                            })
                            
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error processing VLAN {vlan_id_str}: {e}")
                            continue
                    
                    logger.info(f"Retrieved {len(vlan_list)} VLANs with names from {switch_ip}")
                    inventory.update_switch_status(switch_ip, "online")
                    return sorted(vlan_list, key=lambda x: x['id'])
                
            # Fallback: Get VLAN list first, then individual details
            response = session.get(f"{base_url}/system/vlans", timeout=10)
            
            if response.status_code == 200:
                vlans_data = response.json()
                vlan_list = []
                
                logger.info(f"VLAN response type: {type(vlans_data)} on {switch_ip}")
                
                # Handle different response formats
                if isinstance(vlans_data, dict):
                    # Dictionary format: {"1": "/rest/vX.X/system/vlans/1", ...}
                    logger.info(f"Processing {len(vlans_data)} VLANs (dict format) from {switch_ip}")
                    
                    for vlan_id_str, vlan_uri in vlans_data.items():
                        try:
                            vlan_id_num = int(vlan_id_str)
                            if not (1 <= vlan_id_num <= 4094):
                                continue
                            
                            if load_details:
                                # Get detailed information for each VLAN
                                try:
                                    vlan_detail_response = session.get(f"{base_url}/system/vlans/{vlan_id_num}", timeout=5)
                                    if vlan_detail_response.status_code == 200:
                                        vlan_detail = vlan_detail_response.json()
                                        vlan_name = vlan_detail.get('name', f'VLAN{vlan_id_num}')
                                        admin_state = vlan_detail.get('admin', 'unknown')
                                        oper_state = vlan_detail.get('oper_state', 'unknown')
                                    else:
                                        vlan_name = f'VLAN{vlan_id_num}'
                                        admin_state = 'unknown'
                                        oper_state = 'unknown'
                                except Exception as e:
                                    logger.warning(f"Error getting details for VLAN {vlan_id_num}: {e}")
                                    vlan_name = f'VLAN{vlan_id_num}'
                                    admin_state = 'unknown'
                                    oper_state = 'unknown'
                            else:
                                # Basic information only
                                vlan_name = f'VLAN{vlan_id_num}'
                                admin_state = 'up'
                                oper_state = 'up'
                            
                            vlan_list.append({
                                'id': vlan_id_num,
                                'name': vlan_name,
                                'admin_state': admin_state,
                                'oper_state': oper_state,
                                'details_loaded': load_details
                            })
                            
                        except (ValueError, requests.RequestException) as e:
                            logger.warning(f"Error processing VLAN {vlan_id_str}: {e}")
                            continue
                            
                elif isinstance(vlans_data, list):
                    # List format: ["/rest/v1/system/vlans/1", ...]
                    logger.info(f"Processing {len(vlans_data)} VLANs (list format) from {switch_ip}")
                    
                    for vlan_uri in vlans_data:
                        try:
                            if isinstance(vlan_uri, str):
                                vlan_id_str = vlan_uri.split('/')[-1]
                                vlan_id_num = int(vlan_id_str)
                                
                                if not (1 <= vlan_id_num <= 4094):
                                    continue
                                
                                if load_details:
                                    # Get detailed information for each VLAN
                                    try:
                                        vlan_detail_response = session.get(f"{base_url}/system/vlans/{vlan_id_num}", timeout=5)
                                        if vlan_detail_response.status_code == 200:
                                            vlan_detail = vlan_detail_response.json()
                                            vlan_name = vlan_detail.get('name', f'VLAN{vlan_id_num}')
                                            admin_state = vlan_detail.get('admin', 'up')
                                            oper_state = vlan_detail.get('oper_state', 'up')
                                        else:
                                            vlan_name = f'VLAN{vlan_id_num}'
                                            admin_state = 'unknown'
                                            oper_state = 'unknown'
                                    except Exception as e:
                                        logger.warning(f"Error getting details for VLAN {vlan_id_num}: {e}")
                                        vlan_name = f'VLAN{vlan_id_num}'
                                        admin_state = 'unknown'
                                        oper_state = 'unknown'
                                else:
                                    # Basic information only
                                    vlan_name = f'VLAN{vlan_id_num}'
                                    admin_state = 'up'
                                    oper_state = 'up'
                                
                                vlan_list.append({
                                    'id': vlan_id_num,
                                    'name': vlan_name,
                                    'admin_state': admin_state,
                                    'oper_state': oper_state,
                                    'details_loaded': load_details
                                })
                                
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error processing VLAN URI {vlan_uri}: {e}")
                            continue
                else:
                    raise Exception(f"Unexpected VLAN response format: {type(vlans_data)}")
                
                logger.info(f"Retrieved {len(vlan_list)} VLANs from {switch_ip} (details_loaded={load_details})")
                inventory.update_switch_status(switch_ip, "online")
                return sorted(vlan_list, key=lambda x: x['id'])
                
            elif response.status_code == 410:
                error_msg = f"VLAN listing blocked (Central management restricts direct access)"
                logger.error(error_msg)
                raise Exception(error_msg)
            else:
                error_msg = f"Failed to list VLANs: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            # Clean up session on any error to prevent session buildup
            if "session limit" in str(e).lower():
                logger.warning(f"Session limit detected, cleaning up sessions for {switch_ip}")
                self.cleanup_session(switch_ip, force_logout=True)
            
            error_msg = f"Error listing VLANs on {switch_ip}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def create_vlan(self, switch_ip: str, vlan_id: int, name: str) -> str:
        """Create VLAN with enhanced Central management error messages."""
        # Input validation
        if not (1 <= vlan_id <= 4094):
            raise ValueError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")
        
        if not name or not name.strip():
            raise ValueError("VLAN name cannot be empty")
        
        name = name.strip()
        
        try:
            session = self._authenticate(switch_ip)
            base_url = self._get_base_url(switch_ip)
            api_version = self.switch_api_versions.get(switch_ip, 'v1')
            
            # Check if VLAN already exists
            check_response = session.get(
                f"{base_url}/system/vlans/{vlan_id}",
                timeout=10,
                verify=self.config.SSL_VERIFY
            )
            
            if check_response.status_code == 200:
                logger.info(f"VLAN {vlan_id} already exists on {switch_ip}")
                return f"VLAN {vlan_id} already exists on {switch_ip}"
            
            # Create VLAN using appropriate method based on API version
            if api_version == 'v1':
                # v1 API uses POST to collection endpoint
                vlan_data = {
                    "name": name,
                    "id": vlan_id,
                    "type": "static", 
                    "admin": "up"
                }
                
                response = session.post(
                    f"{base_url}/system/vlans",  # Collection endpoint
                    json=vlan_data,
                    timeout=10,
                    verify=self.config.SSL_VERIFY
                )
                expected_status = 201  # Created
                
            else:
                # v10.x APIs use PUT to individual resource
                vlan_data = {
                    "name": name,
                    "admin": "up"
                }
                
                response = session.put(
                    f"{base_url}/system/vlans/{vlan_id}",  # Individual resource
                    json=vlan_data,
                    timeout=10,
                    verify=self.config.SSL_VERIFY
                )
                expected_status = 200  # OK
            
            if response.status_code == expected_status:
                logger.info(f"Successfully created VLAN {vlan_id} ({name}) on {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return f"Successfully created VLAN {vlan_id} ('{name}') on {switch_ip}"
            elif response.status_code == 410:
                error_msg = (f"VLAN creation blocked - This switch appears to be managed by Aruba Central. "
                            f"Central restricts direct API write operations to maintain control. "
                            f"Use Central's interface for VLAN management or switch to standalone management.")
                logger.error(error_msg)
                raise Exception(error_msg)
            elif response.status_code == 403:
                error_msg = (f"Permission denied - Either insufficient user privileges or Central management restrictions. "
                            f"Verify admin credentials and check if switch is Central-managed.")
                logger.error(error_msg)
                raise Exception(error_msg)
            else:
                error_msg = f"Failed to create VLAN: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            # Clean up session on error
            if "session limit" in str(e).lower():
                self.cleanup_session(switch_ip, force_logout=True)
            
            error_msg = f"Error creating VLAN {vlan_id} on {switch_ip}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def delete_vlan(self, switch_ip: str, vlan_id: int) -> str:
        """Delete VLAN using direct REST API with session management."""
        # Safety check: don't delete default VLANs
        if vlan_id == 1:
            raise ValueError("Cannot delete default VLAN 1")
        
        try:
            session = self._authenticate(switch_ip)
            base_url = self._get_base_url(switch_ip)
            
            # Check if VLAN exists
            check_response = session.get(f"{base_url}/system/vlans/{vlan_id}", timeout=10)
            
            if check_response.status_code == 404:
                return f"VLAN {vlan_id} does not exist on {switch_ip}"
            
            # Delete VLAN
            response = session.delete(f"{base_url}/system/vlans/{vlan_id}", timeout=10)
            
            if response.status_code in [200, 204]:
                logger.info(f"Successfully deleted VLAN {vlan_id} from {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return f"Successfully deleted VLAN {vlan_id} from {switch_ip}"
            elif response.status_code == 410:
                error_msg = f"VLAN deletion blocked (Central management restricts write operations)"
                logger.error(error_msg)
                raise Exception(error_msg)
            else:
                error_msg = f"Failed to delete VLAN: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            # Clean up session on error
            if "session limit" in str(e).lower():
                self.cleanup_session(switch_ip, force_logout=True)
                
            error_msg = f"Error deleting VLAN {vlan_id} from {switch_ip}: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

# Global direct REST manager instance
direct_rest_manager = DirectRestManager()