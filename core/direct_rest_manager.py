"""
Direct REST API implementation with VLAN name support and Central management detection (DEBUG VERSION).
"""
import requests
import json
import logging
import time
import http.client as http_client
from typing import Dict, List, Any, Optional
from datetime import datetime
import urllib3

from config.settings import Config
from config.switch_inventory import inventory
from core.exceptions import (
    SessionLimitError, InvalidCredentialsError, ConnectionTimeoutError,
    PermissionDeniedError, APIUnavailableError, CentralManagedError,
    VLANOperationError, UnknownSwitchError
)
from core.api_logger import api_logger

# Suppress InsecureRequestWarning for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Disable HTTP wire-level debugging for cleaner output
http_client.HTTPConnection.debuglevel = 0
logging.basicConfig(level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests.packages.urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class DirectRestManager:
    """Direct REST API manager with VLAN names and Central management detection."""
    
    def __init__(self):
        self.config = Config()
        self.sessions: Dict[str, requests.Session] = {}
        self.switch_api_versions: Dict[str, str] = {}
        self.session_timeouts: Dict[str, float] = {}
    
    def _log_api_call(self, method: str, url: str, headers: Dict, data: Any, 
                     response: requests.Response, start_time: float, switch_ip: str = None):
        """Helper method to log API calls with comprehensive details."""
        duration_ms = (time.time() - start_time) * 1000
        
        # Extract switch IP from URL if not provided
        if not switch_ip:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                switch_ip = parsed.hostname
            except Exception:
                switch_ip = 'unknown'
        
        api_logger.log_api_call(
            method=method,
            url=url,
            headers=headers,
            request_data=data,
            response_code=response.status_code,
            response_text=response.text,
            duration_ms=duration_ms,
            switch_ip=switch_ip
        )

    def cleanup_session(self, switch_ip: str, force_logout: bool = True):
        if switch_ip in self.sessions:
            try:
                if force_logout:
                    sess = self.sessions[switch_ip]
                    base = self._get_base_url(switch_ip)
                    resp = sess.post(f"{base}/logout", timeout=5)
                    logger.debug(f"LOGOUT {base}/logout: {resp.status_code}")
            except Exception as e:
                logger.debug(f"Logout error for {switch_ip}: {e}")
            finally:
                self.sessions.pop(switch_ip, None)
                self.session_timeouts.pop(switch_ip, None)
                logger.info(f"Cleaned session for {switch_ip}")

    def cleanup_all_sessions(self):
        for ip in list(self.sessions.keys()):
            self.cleanup_session(ip, force_logout=True)
        logger.info("All sessions cleaned up")

    def attempt_session_cleanup(self, switch_ip: str) -> bool:
        """
        Attempt to clean up sessions when session limit is reached.
        Returns True if cleanup appears successful, False otherwise.
        """
        try:
            logger.info(f"Attempting session cleanup for {switch_ip}")
            
            # Method 1: Try to logout any known sessions
            if switch_ip in self.sessions:
                self.cleanup_session(switch_ip, force_logout=True)
            
            # Method 2: Try multiple session cleanup attempts
            # Sometimes switches need multiple attempts to clear stale sessions
            cleanup_attempts = [
                ("admin", "admin"),
                ("admin", ""),
                ("admin", None),
                (self.config.SWITCH_USER, self.config.SWITCH_PASSWORD)
            ]
            
            for username, password in cleanup_attempts:
                try:
                    # Create temporary session to attempt logout
                    temp_session = requests.Session()
                    temp_session.verify = self.config.SSL_VERIFY
                    
                    # Try to login and immediately logout to clear a session slot
                    auth_url = f"https://{switch_ip}/rest/v10.09/login?username={username}&password={password or ''}"
                    response = temp_session.post(auth_url, headers={'accept': '*/*'}, data="", timeout=5)
                    
                    if response.status_code == 200:
                        # Successful login, now logout
                        logout_url = f"https://{switch_ip}/rest/v10.09/logout"
                        temp_session.post(logout_url, timeout=5)
                        logger.info(f"Cleared session for {username} on {switch_ip}")
                        return True
                    
                except Exception as e:
                    logger.debug(f"Cleanup attempt failed for {username}: {e}")
                    continue
            
            logger.warning(f"Session cleanup unsuccessful for {switch_ip}")
            return False
            
        except Exception as e:
            logger.error(f"Error during session cleanup for {switch_ip}: {e}")
            return False

    def parse_auth_error(self, switch_ip: str, username: str, response: requests.Response) -> Exception:
        """
        Parse authentication error response and return appropriate exception.
        """
        status_code = response.status_code
        response_text = response.text.lower()
        
        # Session limit errors
        if "session limit" in response_text or "too many sessions" in response_text:
            return SessionLimitError(switch_ip, response.text.strip())
        
        # Invalid credentials
        if status_code == 401:
            if "login failed" in response_text or "unauthorized" in response_text:
                return InvalidCredentialsError(switch_ip, username, response.text.strip())
        
        # Permission denied
        if status_code == 403:
            return PermissionDeniedError(switch_ip, username)
        
        # API not found
        if status_code == 404:
            return APIUnavailableError(switch_ip, f"API endpoint not found: {response.text.strip()}")
        
        # API deprecated/removed
        if status_code == 410:
            if "central" in response_text or "blocked" in response_text:
                return CentralManagedError(switch_ip)
            return APIUnavailableError(switch_ip, f"API deprecated: {response.text.strip()}")
        
        # Default unknown error
        return UnknownSwitchError(switch_ip, status_code, response.text.strip())

    def test_connection_with_credentials(self, switch_ip: str, username: str, password: str) -> Dict[str, Any]:
        """Test connection using confirmed working method with proper error handling."""
        try:
            sess = requests.Session()
            sess.verify = Config.SSL_VERIFY
            
            # Use confirmed working method: query parameter POST to v10.09
            auth_url = f"https://{switch_ip}/rest/v10.09/login?username={username}&password={password}"
            logger.info(f"Testing credentials for {username}@{switch_ip}")
            
            # Log authentication attempt
            start_time = time.time()
            headers = {'accept': '*/*'}
            request_data = f"username={username}&password=***"
            
            resp = sess.post(auth_url, headers=headers, data="", timeout=10, verify=sess.verify)
            self._log_api_call('POST', auth_url, headers, request_data, resp, start_time, switch_ip)
            logger.info(f"LOGIN status: {resp.status_code}")
            
            if resp.status_code == 200 and sess.cookies.get_dict():
                # Test system access
                sys_url = f"https://{switch_ip}/rest/v10.09/system"
                start_time = time.time()
                s2 = sess.get(sys_url, timeout=10, verify=sess.verify)
                self._log_api_call('GET', sys_url, {}, None, s2, start_time, switch_ip)
                logger.info(f"SYSTEM access status: {s2.status_code}")
                
                if s2.status_code == 200:
                    info = s2.json()
                    # Store successful session for reuse
                    self.sessions[switch_ip] = sess
                    self.session_timeouts[switch_ip] = time.time() + 900
                    
                    return {
                        'status': 'online',
                        'ip_address': switch_ip,
                        'firmware_version': info.get('software_version', 'Unknown'),
                        'model': info.get('platform_name', 'Unknown'),
                        'api_version': 'v10.09',
                        'last_seen': datetime.now().isoformat()
                    }
                else:
                    # Authentication worked but system access failed
                    raise PermissionDeniedError(switch_ip, username, "system information access")
            else:
                # Parse the specific authentication error
                auth_error = self.parse_auth_error(switch_ip, username, resp)
                raise auth_error
                
        except requests.exceptions.ConnectTimeout:
            raise ConnectionTimeoutError(switch_ip, "Connection timeout")
        except requests.exceptions.ConnectionError:
            raise ConnectionTimeoutError(switch_ip, "Network connection failed")
        except (SessionLimitError, InvalidCredentialsError, PermissionDeniedError, 
                APIUnavailableError, CentralManagedError, UnknownSwitchError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error testing connection to {switch_ip}: {e}")
            raise UnknownSwitchError(switch_ip, response_text=str(e))

    def _is_session_valid(self, switch_ip: str, session: requests.Session) -> bool:
        if switch_ip in self.session_timeouts and time.time() > self.session_timeouts[switch_ip]:
            logger.debug(f"Session expired for {switch_ip}")
            return False
        url = f"{self._get_base_url(switch_ip)}/system"
        r = session.get(url, timeout=5)
        logger.debug(f"Validate session GET {url}: {r.status_code}")
        return r.status_code == 200

    def get_supported_versions(self, switch_ip: str) -> List[str]:
        """Get supported API versions from the switch."""
        try:
            response = requests.get(f"https://{switch_ip}/rest", verify=self.config.SSL_VERIFY, timeout=10)
            if response.status_code == 200:
                versions_data = response.json()
                return list(versions_data.keys())
            return ['v10.09']  # Fallback to confirmed working version
        except Exception as e:
            logger.debug(f"Error getting supported versions: {e}")
            return ['v10.09']  # Fallback to confirmed working version
    
    def _detect_api_version(self, switch_ip: str) -> str:
        """Use confirmed working API version v10.09."""
        if switch_ip in self.switch_api_versions:
            return self.switch_api_versions[switch_ip]
        
        # Use confirmed working version directly
        self.switch_api_versions[switch_ip] = 'v10.09'
        logger.debug(f"Using confirmed working API version v10.09 for {switch_ip}")
        return 'v10.09'

    def _get_base_url(self, switch_ip: str) -> str:
        """Get base URL using confirmed working API version v10.09."""
        return f"https://{switch_ip}/rest/v10.09"

    def _authenticate(self, switch_ip: str) -> requests.Session:
        """Authenticate using confirmed working method: query parameter POST to v10.09."""
        if switch_ip in self.sessions:
            sess = self.sessions[switch_ip]
            if self._is_session_valid(switch_ip, sess):
                logger.debug(f"Reusing valid session for {switch_ip}")
                return sess
            self.cleanup_session(switch_ip, force_logout=False)
        
        sess = requests.Session()
        sess.verify = self.config.SSL_VERIFY
        
        # Use confirmed working method: query parameter POST to v10.09
        auth_url = f"https://{switch_ip}/rest/v10.09/login?username={self.config.SWITCH_USER}&password={self.config.SWITCH_PASSWORD}"
        logger.debug(f"Authenticating with query parameters: {auth_url}")
        resp = sess.post(auth_url, headers={'accept': '*/*'}, data="", timeout=10, verify=sess.verify)
        logger.debug(f"AUTH LOGIN {resp.status_code}\nHEADERS: {resp.headers}\nBODY: {resp.text!r}")
        logger.debug(f"Cookies after AUTH_LOGIN: {sess.cookies.get_dict()}")
        
        if resp.status_code == 200 and sess.cookies.get_dict():
            self.sessions[switch_ip] = sess
            self.session_timeouts[switch_ip] = time.time() + 900  # 15 minute timeout
            return sess
        else:
            if resp.status_code == 404:
                raise Exception(f"Login endpoint not found - switch may not support session authentication")
            elif resp.status_code == 401:
                raise Exception(f"Invalid credentials for {switch_ip}")
            elif resp.status_code == 410:
                raise Exception(f"Login endpoint deprecated for {switch_ip}")
            else:
                raise Exception(f"Failed to authenticate to {switch_ip}: {resp.status_code} - {resp.text}")

    def _detect_central_management(self, switch_ip: str, session: requests.Session) -> tuple[bool,str]:
        url = f"{self._get_base_url(switch_ip)}/system/vlans"
        r = session.post(url, json={"id":99999,"name":"central_test","admin":"up"}, timeout=5)
        logger.debug(f"CENTRAL test POST {url}: {r.status_code}\nBODY: {r.text!r}")
        if r.status_code in (410,403):
            return True, 'Central-managed'
        if r.status_code == 400:
            return False, 'Direct API OK'
        return False, f'Unexpected {r.status_code}'

    def test_connection(self, switch_ip: str) -> Dict[str, Any]:
        try:
            sess = self._authenticate(switch_ip)
            base = self._get_base_url(switch_ip)
            r = sess.get(f"{base}/system", timeout=10)
            logger.debug(f"GET {base}/system: {r.status_code}")
            if r.status_code != 200:
                raise Exception(f"System info failed: {r.status_code}")
            info = r.json()
            cm, msg = self._detect_central_management(switch_ip, sess)
            res = {
                'status':'online',
                'ip_address':switch_ip,
                'firmware_version':info.get('software_version'),
                'model':info.get('platform_name'),
                'api_version':self.switch_api_versions.get(switch_ip),
                'is_central_managed':cm,
                'management_info':msg,
                'last_seen':datetime.now().isoformat(),
                'error_message':None
            }
            inventory.update_switch_status(switch_ip,'online',firmware_version=res['firmware_version'],model=res['model'])
            return res
        except Exception as e:
            msg = str(e)
            inventory.update_switch_status(switch_ip,'error',msg)
            return {
                'status':'error',
                'ip_address':switch_ip,
                'error_message':msg,
                'is_central_managed':False,
                'management_info':None,
                'last_seen':None
            }
        finally:
            self.cleanup_session(switch_ip, force_logout=True)

    def list_vlans(self, switch_ip: str, load_details: bool = True) -> List[Dict[str, Any]]:
        """List VLANs with real names, supports depth=2 for v10.x."""
        session = self._authenticate(switch_ip)
        base = self._get_base_url(switch_ip)
        version = self.switch_api_versions.get(switch_ip,'v1')
        # Attempt bulk details
        if load_details and version in ['v10.04','v10.09','latest']:
            r = session.get(f"{base}/system/vlans?depth=2&selector=configuration", timeout=15)
            logger.debug(f"Depth-2 VLAN GET: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                vlans=[]
                for vid,det in data.items():
                    try:
                        vid_num = int(vid)
                        if 1<=vid_num<=4094:
                            vlans.append({
                                'id':vid_num,
                                'name':det.get('name',f'VLAN{vid_num}'),
                                'admin_state':det.get('admin','unknown'),
                                'oper_state':'up',
                                'details_loaded':True
                            })
                    except Exception:
                        continue
                inventory.update_switch_status(switch_ip,'online')
                return sorted(vlans,key=lambda x: x['id'])
        # Fallback
        r = session.get(f"{base}/system/vlans", timeout=10)
        logger.debug(f"Basic VLAN list GET: {r.status_code}")
        if r.status_code != 200:
            if r.status_code==410:
                raise Exception('VLAN listing blocked')
            raise Exception(f"VLAN list failed: {r.status_code}")
        data = r.json()
        vlans = []
        if isinstance(data, dict):
            for vid, uri in data.items():
                try:
                    vid_num=int(vid)
                    if not (1<=vid_num<=4094): continue
                    # fetch detail if requested
                    if load_details:
                        dr = session.get(f"{base}/system/vlans/{vid_num}", timeout=5)
                        if dr.status_code==200:
                            det=dr.json()
                            name=det.get('name',f'VLAN{vid_num}')
                            admin=det.get('admin','unknown')
                            oper=det.get('oper_state','unknown')
                        else:
                            name=f'VLAN{vid_num}'
                            admin=oper='unknown'
                    else:
                        name=f'VLAN{vid_num}'; admin=oper='up'
                    vlans.append({'id':vid_num,'name':name,'admin_state':admin,'oper_state':oper,'details_loaded':load_details})
                except Exception:
                    continue
        elif isinstance(data, list):
            for uri in data:
                try:
                    vid_num=int(uri.rstrip('/').split('/')[-1])
                    if not (1<=vid_num<=4094): continue
                    # same detail fetch logic as above
                    dr = session.get(f"{base}/system/vlans/{vid_num}", timeout=5)
                    if dr.status_code==200:
                        det=dr.json()
                        name=det.get('name',f'VLAN{vid_num}')
                        admin=det.get('admin','up')
                        oper=det.get('oper_state','up')
                    else:
                        name=f'VLAN{vid_num}'; admin=oper='unknown'
                    vlans.append({'id':vid_num,'name':name,'admin_state':admin,'oper_state':oper,'details_loaded':load_details})
                except Exception:
                    continue
        inventory.update_switch_status(switch_ip,'online')
        return sorted(vlans,key=lambda x: x['id'])

    def create_vlan(self, switch_ip: str, vlan_id: int, name: str) -> str:
        """Create VLAN using confirmed working method: POST to collection endpoint."""
        if not (1 <= vlan_id <= 4094):
            raise ValueError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")
        if not name.strip():
            raise ValueError("VLAN name cannot be empty")
        
        session = self._authenticate(switch_ip)
        base = self._get_base_url(switch_ip)
        
        # Check if VLAN already exists
        start_time = time.time()
        cr = session.get(f"{base}/system/vlans/{vlan_id}", timeout=10)
        self._log_api_call('GET', f"{base}/system/vlans/{vlan_id}", {}, None, cr, start_time, switch_ip)
        logger.debug(f"VLAN {vlan_id} exists check: {cr.status_code}")
        if cr.status_code == 200:
            return f"VLAN {vlan_id} already exists on {switch_ip}"
        
        # Use confirmed working method: POST to collection endpoint
        payload = {
            "name": name,
            "id": vlan_id,
            "type": "static",
            "admin": "up"
        }
        
        start_time = time.time()
        resp = session.post(f"{base}/system/vlans", json=payload, timeout=10)
        self._log_api_call('POST', f"{base}/system/vlans", {'Content-Type': 'application/json'}, payload, resp, start_time, switch_ip)
        logger.debug(f"Create VLAN response: {resp.status_code}\nBODY: {resp.text}")
        
        if resp.status_code == 201:  # Expected success code for POST creation
            inventory.update_switch_status(switch_ip, 'online')
            return f"Successfully created VLAN {vlan_id} ('{name}') on {switch_ip}"
        elif resp.status_code == 400:
            raise Exception(f"Invalid VLAN data: {resp.text}")
        elif resp.status_code == 403:
            raise Exception(f"Permission denied - check user privileges: {resp.text}")
        elif resp.status_code == 410:
            raise Exception(f"VLAN creation blocked - switch may be Central-managed: {resp.text}")
        elif resp.status_code == 404:
            raise Exception(f"VLAN endpoint not found - API version issue: {resp.text}")
        else:
            raise Exception(f"Failed to create VLAN: {resp.status_code} - {resp.text}")

    def delete_vlan(self, switch_ip: str, vlan_id: int) -> str:
        if vlan_id==1:
            raise ValueError("Cannot delete default VLAN 1")
        session = self._authenticate(switch_ip)
        base = self._get_base_url(switch_ip)
        dr = session.get(f"{base}/system/vlans/{vlan_id}", timeout=10)
        logger.debug(f"Delete VLAN exists check: {dr.status_code}")
        if dr.status_code==404:
            return f"VLAN {vlan_id} does not exist on {switch_ip}"
        resp = session.delete(f"{base}/system/vlans/{vlan_id}", timeout=10)
        logger.debug(f"Delete VLAN response: {resp.status_code}\nBODY: {resp.text}")
        if resp.status_code in (200,204):
            inventory.update_switch_status(switch_ip,'online')
            return f"Successfully deleted VLAN {vlan_id} from {switch_ip}"
        if resp.status_code == 410:
            raise Exception("VLAN deletion blocked (Central-managed)")
        raise Exception(f"Failed to delete VLAN: {resp.status_code} - {resp.text}")

# Global instance
direct_rest_manager = DirectRestManager()