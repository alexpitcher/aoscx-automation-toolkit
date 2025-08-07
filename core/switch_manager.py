 """
 Enhanced PyAOS-CX wrapper with safety features, caching API version and credentials per switch.
 """
import urllib3
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager
import threading

from pyaoscx.session import Session
from pyaoscx.vlan import Vlan
from pyaoscx.pyaoscx_factory import PyaoscxFactory
from pyaoscx.device import Device

from config.settings import Config
from config.switch_inventory import inventory

# Suppress InsecureRequestWarning for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class SwitchConnectionError(Exception):
    """Raised when unable to connect to switch."""
    pass

class SwitchOperationError(Exception):
    """Raised when switch operation fails.""" 
    pass

class SwitchManager:
    """Enhanced PyAOS-CX wrapper with safety features and per-switch caching."""
    def __init__(self):
        self.config = Config()
        # cache of successful API version per switch IP
        self._version_cache: Dict[str, str] = {}
        # cache of credentials per switch IP
        self._cred_cache: Dict[str, (str, str)] = {}
        # per-switch lock to prevent concurrent session race
        self._locks: Dict[str, threading.Lock] = {}

    @contextmanager
    def get_session(self, switch_ip: str):
        """
        Context manager for switch sessions with automatic cleanup, using cached API version and credentials.
        """
        # ensure a lock exists for this switch
        if switch_ip not in self._locks:
            self._locks[switch_ip] = threading.Lock()

        # acquire per-switch lock
        with self._locks[switch_ip]:
            # determine api version and credentials
            api_version = self._version_cache.get(switch_ip, self.config.API_VERSION)
            user, pwd = self._cred_cache.get(
                switch_ip,
                (self.config.SWITCH_USER, self.config.SWITCH_PASSWORD)
            )

            session = None
            try:
                # create session with cached or default version
                session = Session(switch_ip, api_version)
                # disable SSL verify if configured
                if not self.config.SSL_VERIFY:
                    try:
                        session.session.verify = False
                    except AttributeError:
                        pass

                # open using cached or default credentials
                session.open(user, pwd)
                logger.debug(f"Authenticated to {switch_ip} with API v{api_version} as {user}")
                # on success, store caches
                self._version_cache[switch_ip] = api_version
                self._cred_cache[switch_ip] = (user, pwd)
                logger.info(f"Opened session to switch {switch_ip} (v{api_version})")
                yield session

            except Exception as e:
                error_msg = f"Failed to connect/auth to switch {switch_ip} (v{api_version}): {e}"
                logger.error(error_msg)
                inventory.update_switch_status(switch_ip, "error", error_msg)
                raise SwitchConnectionError(error_msg)

            finally:
                if session:
                    try:
                        session.close()
                        logger.debug(f"Closed session to switch {switch_ip}")
                    except Exception as e:
                        logger.warning(f"Error closing session to {switch_ip}: {e}")

    def test_connection(self, switch_ip: str) -> Dict[str, Any]:
        """
        Test connection to a switch and return status information.
        """
        try:
            with self.get_session(switch_ip) as session:
                device = Device(session)
                device.get()

                result = {
                    'status': 'online',
                    'ip_address': switch_ip,
                    'firmware_version': getattr(device, 'firmware_version', None),
                    'model': getattr(device, 'platform_name', None),
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
        """
        Retrieve all VLANs from a switch.
        """
        try:
            with self.get_session(switch_ip) as session:
                vlan_dict = Vlan.get_all(session)
                vlan_list = []

                for vid, vlan_obj in vlan_dict.items():
                    try:
                        vlan_obj.get()
                        vlan_list.append({
                            'id': vlan_obj.id,
                            'name': vlan_obj.name or f"VLAN{vlan_obj.id}",
                            'admin_state': getattr(vlan_obj, 'admin_state', None),
                            'oper_state': getattr(vlan_obj, 'oper_state', None)
                        })
                    except Exception as e:
                        logger.warning(f"Error getting details for VLAN {vid}: {e}")
                        vlan_list.append({
                            'id': vid,
                            'name': f"VLAN{vid}",
                            'admin_state': 'unknown',
                            'oper_state': 'unknown'
                        })

                logger.info(f"Retrieved {len(vlan_list)} VLANs from {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return sorted(vlan_list, key=lambda x: x['id'])

        except SwitchConnectionError:
            raise
        except Exception as e:
            error_msg = f"Error listing VLANs on {switch_ip}: {e}"
            logger.error(error_msg)
            if '403' in str(e) or 'Forbidden' in str(e):
                raise SwitchOperationError(f"Permission denied: {error_msg}")
            raise SwitchOperationError(error_msg)

    def create_vlan(self, switch_ip: str, vlan_id: int, name: str) -> str:
        """
        Create a VLAN on a switch with validation.
        """
        if not (1 <= vlan_id <= 4094):
            raise ValueError(f"VLAN ID must be between 1 and 4094, got {vlan_id}")
        if not name or not name.strip():
            raise ValueError("VLAN name cannot be empty")
        name = name.strip()

        try:
            with self.get_session(switch_ip) as session:
                existing_vlans = Vlan.get_all(session)
                if vlan_id in existing_vlans:
                    logger.info(f"VLAN {vlan_id} already exists on {switch_ip}")
                    return f"VLAN {vlan_id} already exists on {switch_ip}"

                factory = PyaoscxFactory(session)
                vlan = factory.vlan(vlan_id, name)

                if vlan:
                    logger.info(f"Successfully created VLAN {vlan_id} ({name}) on {switch_ip}")
                    inventory.update_switch_status(switch_ip, "online")
                    return f"Successfully created VLAN {vlan_id} ('{name}') on {switch_ip}"
                else:
                    raise SwitchOperationError("VLAN creation returned None")

        except SwitchConnectionError:
            raise
        except Exception as e:
            error_msg = f"Error creating VLAN {vlan_id} on {switch_ip}: {e}"
            logger.error(error_msg)
            if '403' in str(e) or 'Forbidden' in str(e):
                raise SwitchOperationError(f"Permission denied: {error_msg}")
            raise SwitchOperationError(error_msg)

    def delete_vlan(self, switch_ip: str, vlan_id: int) -> str:
        """
        Delete a VLAN from a switch with safety checks.
        """
        if vlan_id == 1:
            raise ValueError("Cannot delete default VLAN 1")

        try:
            with self.get_session(switch_ip) as session:
                existing_vlans = Vlan.get_all(session)
                if vlan_id not in existing_vlans:
                    return f"VLAN {vlan_id} does not exist on {switch_ip}"

                vlan = existing_vlans[vlan_id]
                vlan.delete()

                logger.info(f"Successfully deleted VLAN {vlan_id} from {switch_ip}")
                inventory.update_switch_status(switch_ip, "online")
                return f"Successfully deleted VLAN {vlan_id} from {switch_ip}"

        except SwitchConnectionError:
            raise
        except Exception as e:
            error_msg = f"Error deleting VLAN {vlan_id} from {switch_ip}: {e}"
            logger.error(error_msg)
            if '403' in str(e) or 'Forbidden' in str(e):
                raise SwitchOperationError(f"Permission denied: {error_msg}")
            raise SwitchOperationError(error_msg)

# Global switch manager instance
switch_manager = SwitchManager()
