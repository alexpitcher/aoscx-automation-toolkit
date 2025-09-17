"""
Enhanced PyAOS-CX Automation Toolkit - Main Flask Application
"""
import logging
import time
from flask import Flask, request, jsonify, render_template, redirect, make_response, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from typing import Dict, Any, List, Optional
import requests
from config.settings import Config
from config.switch_inventory import inventory, SwitchInfo
from core.direct_rest_manager import direct_rest_manager
from core.switch_manager_factory import switch_manager_factory
from core.switch_diagnostics import run_diagnostics
from core.exceptions import (
    SessionLimitError, InvalidCredentialsError, ConnectionTimeoutError,
    PermissionDeniedError, APIUnavailableError, CentralManagedError,
    VLANOperationError, UnknownSwitchError, SwitchConnectionError
)
from core.api_logger import api_logger
from core.cache import get_cached_or_fetch, interface_cache, vlan_cache, invalidate_switch_cache

# Capability cache for switch-specific features
capability_cache = {}
CAPABILITY_CACHE_TTL = 60  # seconds

# Legacy cache variables - now using TTL cache from core.cache
# interface_cache = {}  # Now imported from core.cache
INTERFACE_CACHE_TTL = 300  # seconds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def capabilities_for(switch_ip: str, session_obj=None) -> Dict[str, Any]:
    """Get cached capabilities for a switch or detect them."""
    current_time = time.time()
    
    # Check cache first
    if switch_ip in capability_cache:
        cached = capability_cache[switch_ip]
        if current_time - cached['timestamp'] < CAPABILITY_CACHE_TTL:
            return cached['capabilities']
    
    # Need to detect capabilities
    if not session_obj:
        try:
            session_obj = direct_rest_manager._authenticate(switch_ip)
        except Exception as e:
            logger.warning(f"Failed to authenticate for capability detection on {switch_ip}: {e}")
            # Return conservative defaults
            return {
                'poe_supported': False,
                'cpu_supported': False,
                'expected_psu_slots': 1,
                'expected_fan_zones': 1
            }
    
    capabilities = detect_switch_capabilities(switch_ip, session_obj)
    
    # Cache the result
    capability_cache[switch_ip] = {
        'capabilities': capabilities,
        'timestamp': current_time
    }
    
    return capabilities

def detect_switch_capabilities(switch_ip: str, session_obj) -> Dict[str, Any]:
    """Detect switch capabilities through endpoint probing."""
    capabilities = {
        'poe_supported': False,
        'cpu_supported': False,
        'expected_psu_slots': 1,
        'expected_fan_zones': 1,
        'port_count': 0,
        'platform_name': '',
        'lldp_supported': False
    }
    
    # Get system info first for platform detection
    try:
        system_url = f"https://{switch_ip}/rest/v10.09/system"
        system_response = session_obj.get(system_url, timeout=10, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', system_url, {}, None, system_response.status_code, system_response.text, 0)
        
        if system_response.status_code == 200:
            system_data = system_response.json()
            platform_name = system_data.get('platform_name', '').lower()
            capabilities['platform_name'] = platform_name
            
            # Platform-specific capability inference based on probe results
            if '6200' in platform_name:
                capabilities['poe_supported'] = _check_chassis_poe_support(switch_ip, session_obj)
                capabilities['expected_psu_slots'] = 1
                capabilities['expected_fan_zones'] = 0
            elif '6300' in platform_name:
                # PoE-capable but endpoints don't work via REST API
                # Check chassis for PoE power data instead
                capabilities['poe_supported'] = _check_chassis_poe_support(switch_ip, session_obj)
                capabilities['expected_psu_slots'] = 2
                capabilities['expected_fan_zones'] = 0  # No fan monitoring on 6300
            elif '9300' in platform_name:
                capabilities['poe_supported'] = False  # High-speed switches don't have PoE
                capabilities['expected_psu_slots'] = 2
                capabilities['expected_fan_zones'] = 4
            elif '10000' in platform_name:
                capabilities['poe_supported'] = False  # Core switches don't have PoE
                capabilities['expected_psu_slots'] = 2
                capabilities['expected_fan_zones'] = 2
            else:
                # Conservative defaults
                capabilities['expected_psu_slots'] = 1
                capabilities['expected_fan_zones'] = 1
                
    except Exception as e:
        logger.debug(f"System info probe failed for {switch_ip}: {e}")
    
    # Test CPU support - all probed switches failed these endpoints
    # Based on probe results, these endpoints return 400 on all tested platforms
    capabilities['cpu_supported'] = False
    
    # Test LLDP support
    try:
        lldp_url = f"https://{switch_ip}/rest/v10.09/system/lldp"
        lldp_response = session_obj.get(lldp_url, timeout=5, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', lldp_url, {}, None, lldp_response.status_code, lldp_response.text, 0)
        
        if lldp_response.status_code == 200:
            capabilities['lldp_supported'] = True
    except Exception as e:
        logger.debug(f"LLDP probe failed for {switch_ip}: {e}")
    
    # Get port count from interfaces
    try:
        interfaces_url = f"https://{switch_ip}/rest/v10.09/system/interfaces"
        interfaces_response = session_obj.get(interfaces_url, timeout=10, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', interfaces_url, {}, None, interfaces_response.status_code, interfaces_response.text, 0)
        
        if interfaces_response.status_code == 200:
            interfaces_list = interfaces_response.json()
            # Count physical interfaces only
            physical_interfaces = [k for k in interfaces_list.keys() 
                                 if ':' not in k and k.startswith('1/1/')]
            capabilities['port_count'] = len(physical_interfaces)
    except Exception as e:
        logger.debug(f"Interface count probe failed for {switch_ip}: {e}")
    
    logger.info(f"Detected capabilities for {switch_ip}: {capabilities}")
    return capabilities

def _check_chassis_poe_support(switch_ip: str, session_obj) -> bool:
    """Check if chassis has PoE power data (alternative to REST PoE endpoints)."""
    try:
        chassis_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1"
        chassis_response = session_obj.get(chassis_url, timeout=5, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', chassis_url, {}, None, chassis_response.status_code, chassis_response.text, 0)
        
        if chassis_response.status_code == 200:
            chassis_data = chassis_response.json()
            # Check if chassis has PoE power information
            return 'poe_power' in chassis_data
    except Exception as e:
        logger.debug(f"Chassis PoE check failed for {switch_ip}: {e}")
    return False

def get_cached_interfaces(switch_ip: str, session_obj=None) -> Dict[str, Any]:
    """Get cached interface data or fetch and cache if stale."""
    current_time = time.time()
    
    # Check cache first
    if switch_ip in interface_cache:
        cached = interface_cache[switch_ip]
        if current_time - cached['timestamp'] < INTERFACE_CACHE_TTL:
            return cached['data']
        else:
            # Stale data - return immediately and refresh in background
            # For now, we'll refresh synchronously to keep it simple
            pass
    
    # Need to fetch interface data
    if not session_obj:
        try:
            session_obj = direct_rest_manager._authenticate(switch_ip)
        except Exception as e:
            logger.warning(f"Failed to authenticate for interface caching on {switch_ip}: {e}")
            return {'interfaces': [], 'total_count': 0}
    
    interface_data = _fetch_bulk_interfaces(switch_ip, session_obj)
    
    # Cache the result
    interface_cache[switch_ip] = {
        'data': interface_data,
        'timestamp': current_time
    }
    
    return interface_data

def _fetch_interfaces_individually(switch_ip: str, session_obj, interfaces_list: Dict[str, str]) -> Dict[str, Any]:
    """Fallback method to fetch interface data individually when bulk call returns URLs.
    Uses concurrent fetches and short timeouts to avoid hangs on large port counts.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    physical_interface_names = [name for name in interfaces_list.keys()
                                if ':' not in name and name.startswith('1/1/')]
    physical_interfaces = []

    def fetch_one(name: str):
        try:
            encoded_name = name.replace('/', '%2F')
            iface_url = f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded_name}"
            resp = session_obj.get(iface_url, timeout=2.5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', iface_url, {}, None, resp.status_code, resp.text, 0)
            if resp.status_code != 200:
                return None
            iface_data = resp.json()
            admin_state = iface_data.get('admin_state', 'unknown')
            link_state = iface_data.get('link_state', 'unknown')
            if admin_state == 'down':
                status = 'disabled'
            elif admin_state == 'up' and link_state == 'up':
                status = 'up'
            else:
                status = 'down'
            link_speed = iface_data.get('link_speed', 0) or 0
            speed_display = _format_interface_speed(link_speed)
            vlan_tag = iface_data.get('vlan_tag', {})
            vlan_trunks = iface_data.get('vlan_trunks', {})
            untagged_vlan = None
            if isinstance(vlan_tag, dict) and vlan_tag:
                untagged_vlan = int(list(vlan_tag.keys())[0])
            tagged_vlans = []
            if isinstance(vlan_trunks, dict):
                tagged_vlans = [int(vlan_id) for vlan_id in vlan_trunks.keys()]
            return {
                'name': name,
                'admin_state': admin_state,
                'link_state': link_state,
                'status': status,
                'link_speed': link_speed,
                'speed_display': speed_display,
                'type': iface_data.get('type', 'unknown'),
                'description': iface_data.get('description', '') or '',
                'mtu': iface_data.get('mtu', 1500) or 1500,
                'untagged_vlan': untagged_vlan,
                'tagged_vlans': tagged_vlans
            }
        except Exception as e:
            logger.debug(f"Failed to fetch interface {name}: {e}")
            return None

    # Fetch concurrently with a reasonable worker count
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, name): name for name in physical_interface_names}
        for future in as_completed(futures):
            result = future.result()
            if result:
                physical_interfaces.append(result)

    # Sort for consistency
    physical_interfaces.sort(key=lambda x: _natural_sort_key(x['name']))
    return {'interfaces': physical_interfaces, 'total_count': len(physical_interfaces)}

def _fetch_bulk_interfaces(switch_ip: str, session_obj) -> Dict[str, Any]:
    """Fetch all interface data in bulk with VLAN attributes - returns physical and management interfaces."""
    try:
        # Single bulk call with VLAN attributes
        bulk_url = f"https://{switch_ip}/rest/v10.09/system/interfaces?attributes=name,admin_state,link_state,link_speed,type,description,vlan_tag,vlan_trunks,mtu"
        interfaces_response = session_obj.get(bulk_url, timeout=15, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', bulk_url, {}, None, interfaces_response.status_code, interfaces_response.text, 0)
        
        if interfaces_response.status_code != 200:
            logger.warning(f"Bulk interfaces call failed with {interfaces_response.status_code}")
            return {'interfaces': [], 'total_count': 0}
            
        interfaces_data = interfaces_response.json()
        
        # Check if we got URLs instead of actual data (some switches don't support attributes parameter)
        sample_key = next(iter(interfaces_data)) if interfaces_data else None
        sample_value = interfaces_data.get(sample_key, {}) if sample_key else {}
        
        if isinstance(sample_value, str) and sample_value.startswith('/rest/'):
            logger.info(f"Switch {switch_ip} returned URLs instead of data, falling back to individual calls")
            return _fetch_interfaces_individually(switch_ip, session_obj, interfaces_data)
        
        # Separate physical and management interfaces
        physical_interfaces = []
        management_interfaces = []
        for name, iface_data in interfaces_data.items():
            lower_name = name.lower()
            is_mgmt = lower_name.startswith('mgmt') or iface_data.get('type', '').lower() == 'mgmt'
            is_physical = (':' not in name and name.startswith('1/1/'))
            if not (is_mgmt or is_physical):
                continue
                # Normalize interface data
                admin_state = iface_data.get('admin_state', 'unknown')
                link_state = iface_data.get('link_state', 'unknown')
                
                # Apply state normalization rules
                if admin_state == 'down':
                    status = 'disabled'
                elif admin_state == 'up' and link_state == 'up':
                    status = 'up'
                else:
                    status = 'down'
                
                # Format speed for display
                link_speed = iface_data.get('link_speed', 0) or 0
                speed_display = _format_interface_speed(link_speed)
                
                # Process VLAN membership
                vlan_tag = iface_data.get('vlan_tag', {})
                vlan_trunks = iface_data.get('vlan_trunks', {})
                
                # Extract untagged VLAN ID (vlan_tag is a dict with VLAN ID as key)
                untagged_vlan = None
                if isinstance(vlan_tag, dict) and vlan_tag:
                    untagged_vlan = int(list(vlan_tag.keys())[0])
                
                # Extract tagged VLANs (vlan_trunks is a dict with VLAN IDs as keys)
                tagged_vlans = []
                if isinstance(vlan_trunks, dict):
                    tagged_vlans = [int(vlan_id) for vlan_id in vlan_trunks.keys()]
                
                interface = {
                    'name': name,
                    'admin_state': admin_state,
                    'link_state': link_state,
                    'status': status,
                    'speed': link_speed,
                    'speed_display': speed_display,
                    'type': iface_data.get('type', 'unknown'),
                    'description': iface_data.get('description', '') or '',
                    'mtu': iface_data.get('mtu', 0) or 0,
                    'untagged_vlan': untagged_vlan,
                    'tagged_vlans': tagged_vlans
                }
                
                if is_mgmt:
                    # Attempt to enrich with IP info from detailed endpoint
                    try:
                        encoded = name.replace('/', '%2F')
                        detail_url = f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded}"
                        det_resp = session_obj.get(detail_url, timeout=5, verify=Config.SSL_VERIFY)
                        api_logger.log_api_call('GET', detail_url, {}, None, det_resp.status_code, det_resp.text, 0)
                        if det_resp.status_code == 200:
                            det = det_resp.json()
                            ipv4 = det.get('ip4_address') or det.get('ip_address')
                            if not ipv4 and isinstance(det.get('ipv4'), dict):
                                ipv4 = det['ipv4'].get('address') or det['ipv4'].get('primary')
                            ipv6 = det.get('ip6_address') or det.get('ipv6')
                            interface['ipv4'] = ipv4
                            interface['ipv6'] = ipv6
                    except Exception as e:
                        logger.debug(f"Mgmt interface detail fetch failed for {name}: {e}")
                    management_interfaces.append(interface)
                else:
                    physical_interfaces.append(interface)
        
        # Sort interfaces naturally by name
        physical_interfaces.sort(key=lambda x: _natural_sort_key(x['name']))
        management_interfaces.sort(key=lambda x: _natural_sort_key(x['name']))
        
        logger.info(f"Fetched {len(physical_interfaces)} interfaces for {switch_ip} in bulk")
        
        return {
            'interfaces': physical_interfaces,
            'management': management_interfaces,
            'total_count': len(physical_interfaces)
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch bulk interfaces for {switch_ip}: {e}")
        return {'interfaces': [], 'management': [], 'total_count': 0}

def _format_interface_speed(link_speed):
    """Format interface speed for display."""
    if not link_speed or link_speed == 0:
        return 'Unknown'
    elif link_speed >= 100000:
        return f'{link_speed // 1000}G'
    elif link_speed >= 1000:
        return f'{link_speed // 1000}G'
    else:
        return f'{link_speed}M'

def _natural_sort_key(interface_name):
    """Generate sort key for natural sorting of interface names like 1/1/1, 1/1/10."""
    import re
    parts = re.split(r'(\d+)', interface_name)
    return [int(part) if part.isdigit() else part for part in parts]

def _fetch_interface_poe(switch_ip: str, session_obj, interface_name: str) -> Dict[str, Any]:
    """Fetch per-interface PoE data with fallback endpoints."""
    encoded_name = interface_name.replace('/', '%2F')
    
    # Try per-interface PoE endpoints
    poe_endpoints = [
        f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded_name}/poe",
        f"https://{switch_ip}/rest/v10.09/system/poe/ports/{encoded_name}"
    ]
    
    for poe_url in poe_endpoints:
        try:
            poe_response = session_obj.get(poe_url, timeout=3, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', poe_url, {}, None, poe_response.status_code, poe_response.text, 0)
            
            if poe_response.status_code == 200:
                poe_data = poe_response.json()
                return {
                    'enabled': poe_data.get('enabled', False),
                    'class': poe_data.get('class', 'N/A'),
                    'watts': poe_data.get('power_drawn', 0) or poe_data.get('watts', 0)
                }
        except Exception as e:
            logger.debug(f"PoE fetch failed for {interface_name} at {poe_url}: {e}")
    
    return None

def _fetch_interface_lldp_neighbors(switch_ip: str, session_obj, interface_name: str) -> List[Dict[str, Any]]:
    """Fetch LLDP neighbors for specific interface using correct AOS-CX API structure."""
    encoded_name = interface_name.replace('/', '%2F')
    neighbors = []
    
    try:
        # Get LLDP neighbors list first
        lldp_neighbors_url = f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded_name}/lldp_neighbors"
        lldp_response = session_obj.get(lldp_neighbors_url, timeout=5, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', lldp_neighbors_url, {}, None, lldp_response.status_code, lldp_response.text, 0)
        
        if lldp_response.status_code == 200:
            neighbors_list = lldp_response.json()
            
            # neighbors_list is a dict with neighbor keys like "98:8f:00:c7:55:4f,98:8f:00:c7:55:4f"
            if isinstance(neighbors_list, dict):
                for neighbor_key, neighbor_url in neighbors_list.items():
                    try:
                        # Extract the encoded neighbor key from the URL path
                        encoded_neighbor_key = neighbor_key.replace(':', '%3A').replace(',', ',')
                        neighbor_detail_url = f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded_name}/lldp_neighbors/{encoded_neighbor_key}"
                        
                        neighbor_response = session_obj.get(neighbor_detail_url, timeout=3, verify=Config.SSL_VERIFY)
                        api_logger.log_api_call('GET', neighbor_detail_url, {}, None, neighbor_response.status_code, neighbor_response.text, 0)
                        
                        if neighbor_response.status_code == 200:
                            neighbor_data = neighbor_response.json()
                            
                            # Extract meaningful neighbor information
                            neighbor_info = {
                                'chassis_id': neighbor_data.get('chassis_id', ''),
                                'port_id': neighbor_data.get('port_id', ''),
                                'system_name': neighbor_data.get('system_name', ''),
                                'system_description': neighbor_data.get('system_description', ''),
                                'port_description': neighbor_data.get('port_description', '')
                            }
                            
                            neighbors.append(neighbor_info)
                        else:
                            logger.debug(f"Failed to get LLDP neighbor detail for {neighbor_key}: {neighbor_response.status_code}")
                            
                    except Exception as neighbor_error:
                        logger.debug(f"Error processing LLDP neighbor {neighbor_key}: {neighbor_error}")
                        continue
        else:
            logger.debug(f"LLDP neighbors endpoint returned {lldp_response.status_code} for {interface_name}")
            
    except Exception as e:
        logger.debug(f"LLDP neighbors fetch failed for {interface_name}: {e}")
    
    return neighbors

def _calculate_vlan_membership(interfaces: List[Dict[str, Any]]) -> Dict[int, Dict[str, int]]:
    """Calculate VLAN membership counts from interface VLAN data."""
    membership = {}
    
    for interface in interfaces:
        # Count untagged VLAN membership
        untagged_vlan = interface.get('untagged_vlan')
        if untagged_vlan is not None:
            if untagged_vlan not in membership:
                membership[untagged_vlan] = {'tagged': 0, 'untagged': 0}
            membership[untagged_vlan]['untagged'] += 1
        
        # Count tagged VLAN membership
        tagged_vlans = interface.get('tagged_vlans', [])
        for vlan_id in tagged_vlans:
            if vlan_id not in membership:
                membership[vlan_id] = {'tagged': 0, 'untagged': 0}
            membership[vlan_id]['tagged'] += 1
    
    return membership

# Initialize Flask application
app = Flask(__name__)
# Ensure correct scheme/host when running behind reverse proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# Validate configuration on startup
config_errors = Config.validate()
if config_errors:
    logger.error("Configuration errors found:")
    for error in config_errors:
        logger.error(f"  - {error}")
    raise SystemExit("Please fix configuration errors before starting the application")

app.config['SECRET_KEY'] = Config.SECRET_KEY

# Initialize default switches from configuration
for switch_ip in Config.DEFAULT_SWITCHES:
    inventory.add_switch(switch_ip)
    logger.info(f"Added default switch: {switch_ip}")

@app.route('/')
def dashboard():
    """Launch to the mobile UI by default; desktop only when explicitly requested."""
    # Preserve ability to access desktop explicitly
    force_desktop = request.args.get('desktop', '').lower() == 'true'
    if not force_desktop:
        return redirect('/mobile')
    return render_template('dashboard.html')

@app.route('/mobile')
def mobile_dashboard():
    """Render the mobile-first dashboard."""
    return render_template('mobile_dashboard.html')

@app.route('/favicon.ico')
def favicon():
    """Serve the app favicon from the static directory."""
    return send_from_directory('static', 'cxedit-icon.jpg')

@app.route('/healthz')
def healthz():
    """Simple health check endpoint for reverse proxy/monitors."""
    return jsonify({"status": "ok"}), 200

# Switch management endpoints
@app.route('/api/switches', methods=['GET'])
def get_switches():
    """Get all switches in inventory."""
    switches = [switch.to_dict() for switch in inventory.get_all_switches()]
    return jsonify({
        'switches': switches,
        'count': inventory.get_switch_count()
    })

@app.route('/api/switches', methods=['POST'])
def add_switch():
    """Add a new switch to inventory with support for both direct and Central connections."""
    try:
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Request data: {request.data}")
        data = request.get_json() or {}
        logger.info(f"Parsed data: {data}")
        if not data and request.data:
            # Try to parse manually if automatic parsing fails
            import json
            data = json.loads(request.data.decode('utf-8'))
    except Exception as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Request data: {request.data}")
        logger.error(f"Request content type: {request.content_type}")
        return jsonify({'error': 'Invalid JSON in request body'}), 400
    
    connection_type = data.get('connection_type', 'direct').strip().lower()
    
    if connection_type == 'central':
        return add_central_switch(data)
    else:
        return add_direct_switch(data)

def add_direct_switch(data):
    """Add a direct-connected switch."""
    ip_address = data.get('ip_address', '').strip()
    name = data.get('name', '').strip() or None
    username = data.get('username', '').strip() or None
    password = data.get('password', '') if data.get('password') is not None else None
    
    if not ip_address:
        return jsonify({'error': 'IP address is required'}), 400
    
    if not inventory.is_valid_ip(ip_address):
        return jsonify({'error': 'Invalid IP address format'}), 400
    
    # Check if switch already exists
    if inventory.get_switch(ip_address):
        return jsonify({'error': f'Switch {ip_address} already exists'}), 400
    
    # Try to add switch with credential fallback logic
    try:
        success = False
        credentials_used = None
        
        if username and password is not None:
            # User provided credentials - try them first
            try:
                logger.info(f"Testing user-provided credentials for {ip_address}: {username}")
                result = direct_rest_manager.test_connection_with_credentials(ip_address, username, password)
                logger.info(f"User credential test successful for {ip_address}")
                success = True
                credentials_used = f"{username}/***"
                # Store credentials for future use
                inventory.store_credentials(ip_address, username, password)
                
            except SessionLimitError as e:
                # Handle session limit with cleanup option
                logger.warning(f"Session limit reached for {ip_address}")
                return jsonify({
                    'error': str(e),
                    'error_type': e.error_type,
                    'suggestion': e.suggestion,
                    'switch_ip': ip_address,
                    'can_retry': True,
                    'cleanup_available': True
                }), 429  # Too Many Requests
                
            except (InvalidCredentialsError, PermissionDeniedError) as e:
                # Don't try defaults for explicit credential errors
                logger.warning(f"User credential error for {ip_address}: {e}")
                return jsonify(e.to_dict()), 401
                
            except (ConnectionTimeoutError, APIUnavailableError, CentralManagedError) as e:
                # These are not credential issues, return immediately
                logger.error(f"Connection/API error for {ip_address}: {e}")
                return jsonify(e.to_dict()), 503
                
            except UnknownSwitchError as e:
                logger.error(f"Unknown error for {ip_address}: {e}")
                return jsonify(e.to_dict()), 500
                
            except Exception as e:
                logger.error(f"Unexpected error for {ip_address}: {e}")
                return jsonify(UnknownSwitchError(ip_address, response_text=str(e)).to_dict()), 500
        
        if not success:
            # Try default credentials automatically (no user credentials provided or user credentials failed)
            if not username and password is None:
                logger.info(f"No user credentials provided, trying default credentials for {ip_address}")
            else:
                logger.info(f"User credentials failed, trying default credentials for {ip_address}")
            
            default_credentials = [
                ('admin', 'Aruba123!'),  # Our confirmed working password
                ('admin', 'admin'),
                ('admin', ''),
                ('admin', None)
            ]
            
            for try_username, try_password in default_credentials:
                try:
                    logger.info(f"Trying default credential {try_username}/{try_password or '(blank)'} for {ip_address}")
                    result = direct_rest_manager.test_connection_with_credentials(ip_address, try_username, try_password)
                    logger.info(f"Default credential test result for {ip_address}: status={result.get('status')}")
                    if result.get('status') == 'online':
                        success = True
                        credentials_used = f"default:{try_username}/{try_password if try_password else '(blank)'}"
                        # Store working credentials
                        inventory.store_credentials(ip_address, try_username, try_password)
                        break
                except Exception as e:
                    logger.info(f"Default credential {try_username}/{try_password or '(blank)'} failed for {ip_address}: {e}")
                    continue
        
        if not success:
            # Try any saved credentials from previous successful connections
            saved_creds = inventory.get_saved_credentials(ip_address)
            if saved_creds:
                try:
                    result = direct_rest_manager.test_connection_with_credentials(ip_address, saved_creds['username'], saved_creds['password'])
                    if result.get('status') == 'online':
                        success = True
                        credentials_used = f"saved credentials"
                except Exception as e:
                    logger.debug(f"Saved credential failed for {ip_address}: {e}")
        
        if success:
            # Add to inventory
            if inventory.add_switch(ip_address, name):
                switch_info = inventory.get_switch(ip_address)
                logger.info(f"Successfully added switch: {ip_address} using {credentials_used}")
                # Immediately retrieve device data to enrich cache and UI
                try:
                    result = switch_manager_factory.test_connection(switch_info)
                    # switch_manager updates inventory status; prefer enriched dict if available
                    enriched = {
                        **switch_info.to_dict(),
                        **{k: v for k, v in result.items() if k in ['status','last_seen','firmware_version','model','api_version','error_message']}
                    }
                except Exception as e:
                    logger.warning(f"Post-add device info retrieval failed for {ip_address}: {e}")
                    enriched = switch_info.to_dict()
                return jsonify({
                    'status': 'success',
                    'message': f'Switch {ip_address} added successfully using {credentials_used}',
                    'switch': enriched
                })
            else:
                return jsonify({
                    'error': 'Failed to add switch to inventory',
                    'error_type': 'internal_error',
                    'suggestion': 'Please try again or contact administrator.'
                }), 500
        else:
            # This should not happen with the new logic, but keeping as fallback
            logger.warning(f"All authentication attempts failed for {ip_address}")
            return jsonify(InvalidCredentialsError(ip_address, username or "unknown").to_dict()), 401
            
    except Exception as e:
        logger.error(f"Error adding switch {ip_address}: {e}")
        return jsonify({'error': f'Error adding switch: {str(e)}'}), 500

def add_central_switch(data):
    """Add a Central-managed switch."""
    device_serial = data.get('device_serial', '').strip()
    name = data.get('name', '').strip() or None
    client_id = data.get('client_id', '').strip()
    client_secret = data.get('client_secret', '').strip()
    customer_id = data.get('customer_id', '').strip()
    base_url = data.get('base_url', '').strip() or 'https://apigw-prod2.central.arubanetworks.com'
    
    # Validation
    if not device_serial:
        return jsonify({'error': 'Device serial number is required for Central-managed switches'}), 400
    
    if not all([client_id, client_secret, customer_id]):
        return jsonify({'error': 'Client ID, Client Secret, and Customer ID are required for Central connection'}), 400
    
    # Check if Central switch already exists
    switch_key = f"central:{device_serial}"
    if inventory.get_switch(switch_key):
        return jsonify({'error': f'Central device {device_serial} already exists'}), 400
    
    try:
        # Test Central connection
        if inventory.add_central_switch(device_serial, name, client_id, client_secret, customer_id, base_url):
            switch_info = inventory.get_switch(switch_key)
            
            # Test the Central connection
            result = switch_manager_factory.test_connection(switch_info)
            
            if result.get('status') == 'online':
                logger.info(f"Added new Central switch: {device_serial}")
                return jsonify({
                    'message': f'Central device {device_serial} added successfully',
                    'switch': switch_info.to_dict()
                })
            else:
                # Remove from inventory if connection test failed
                inventory.remove_switch(switch_key)
                return jsonify({
                    'error': f'Failed to connect to Central device: {result.get("error_message", "Unknown error")}',
                    'error_type': 'central_connection_failed'
                }), 401
        else:
            return jsonify({'error': 'Failed to add Central device to inventory'}), 500
            
    except Exception as e:
        logger.error(f"Error adding Central switch {device_serial}: {e}")
        return jsonify({'error': f'Error adding Central device: {str(e)}'}), 500

@app.route('/api/switches/<switch_ip>', methods=['DELETE'])
def remove_switch(switch_ip: str):
    """Remove a switch from inventory."""
    if not inventory.get_switch(switch_ip):
        return jsonify({'error': f'Switch {switch_ip} not found'}), 404
    
    if inventory.remove_switch(switch_ip):
        return jsonify({'message': f'Switch {switch_ip} removed successfully'})
    else:
        return jsonify({'error': 'Failed to remove switch'}), 500

@app.route('/api/switches/<switch_ip>/test', methods=['GET'])
def test_switch_connection(switch_ip: str):
    """Test connection to a specific switch using appropriate manager."""
    switch_info = inventory.get_switch(switch_ip)
    if not switch_info:
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        result = switch_manager_factory.test_connection(switch_info)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing connection to {switch_ip}: {e}")
        return jsonify({
            'status': 'error',
            'ip_address': switch_ip,
            'error_message': str(e)
        })

@app.route('/api/switch/test', methods=['GET'])
def test_switch_connection_query():
    """Test connection using a query parameter to avoid path issues behind some proxies."""
    switch_ip = request.args.get('switch_ip', '').strip()
    if not switch_ip:
        return jsonify({'error': 'switch_ip parameter is required'}), 400
    switch_info = inventory.get_switch(switch_ip)
    if not switch_info:
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    try:
        result = switch_manager_factory.test_connection(switch_info)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing connection to {switch_ip}: {e}")
        return jsonify({
            'status': 'error',
            'ip_address': switch_ip,
            'error_message': str(e)
        })

@app.route('/api/vlans', methods=['GET'])
def get_vlans():
    """Get VLANs from a specific switch using appropriate manager."""
    switch_ip = request.args.get('switch_ip')
    load_details = request.args.get('load_details', 'true').lower() == 'true'
    
    if not switch_ip:
        return jsonify({'error': 'switch_ip parameter is required'}), 400
    
    switch_info = inventory.get_switch(switch_ip)
    if not switch_info:
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        vlans = switch_manager_factory.list_vlans(switch_info, load_details=load_details)
        return jsonify({'vlans': vlans})
    except Exception as e:
        logger.error(f"Error listing VLANs on {switch_ip}: {e}")
        
        # Enhanced error messaging for Central management
        error_msg = str(e)
        if "Central management" in error_msg or "blocked" in error_msg:
            return jsonify({
                'error': error_msg,
                'error_type': 'central_management',
                'suggestion': 'This switch appears to be Central-managed. Use Aruba Central for VLAN operations.'
            }), 403
        else:
            return jsonify({'error': error_msg}), 503

@app.route('/api/vlans', methods=['POST'])
def create_vlan():
    """Create a VLAN on a specific switch using appropriate manager."""
    data = request.json or {}
    switch_ip = data.get('switch_ip')
    vlan_id = data.get('vlan_id')
    name = data.get('name')
    
    # Validation
    if not all([switch_ip, vlan_id, name]):
        return jsonify({'error': 'switch_ip, vlan_id, and name are required'}), 400
    
    switch_info = inventory.get_switch(switch_ip)
    if not switch_info:
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        vlan_id = int(vlan_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'vlan_id must be a valid integer'}), 400
    
    try:
        message = switch_manager_factory.create_vlan(switch_info, vlan_id, name)
        logger.info(f"VLAN creation request: {switch_ip} - VLAN {vlan_id} ({name})")
        return jsonify({
            'status': 'success',
            'message': message
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating VLAN on {switch_ip}: {e}")
        
        # Enhanced error messaging for Central management
        error_msg = str(e)
        if "Central" in error_msg or "blocked" in error_msg or "410" in error_msg:
            return jsonify({
                'error': error_msg,
                'error_type': 'central_management',
                'suggestion': 'This switch is Central-managed. Use Aruba Central interface for VLAN creation.'
            }), 403
        elif "Permission denied" in error_msg or "403" in error_msg:
            return jsonify({
                'error': error_msg,
                'error_type': 'permission_denied',
                'suggestion': 'Check user permissions or Central management status.'
            }), 403
        else:
            return jsonify({'error': error_msg}), 500

@app.route('/api/vlans/<int:vlan_id>', methods=['DELETE'])
def delete_vlan():
    """Delete a VLAN from a specific switch using appropriate manager."""
    data = request.json or {}
    switch_ip = data.get('switch_ip')
    vlan_id = int(request.view_args['vlan_id'])
    
    if not switch_ip:
        return jsonify({'error': 'switch_ip is required in request body'}), 400
    
    switch_info = inventory.get_switch(switch_ip)
    if not switch_info:
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        message = switch_manager_factory.delete_vlan(switch_info, vlan_id)
        logger.info(f"VLAN deletion request: {switch_ip} - VLAN {vlan_id}")
        return jsonify({
            'status': 'success',
            'message': message
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error deleting VLAN on {switch_ip}: {e}")
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

# Bulk operations endpoints
@app.route('/api/bulk/vlans', methods=['POST'])
def bulk_create_vlans():
    """Create VLANs on multiple switches."""
    data = request.json or {}
    switch_ips = data.get('switch_ips', [])
    vlans = data.get('vlans', [])  # List of {'vlan_id': int, 'name': str}
    
    if not switch_ips:
        return jsonify({'error': 'switch_ips list is required'}), 400
    
    if not vlans:
        return jsonify({'error': 'vlans list is required'}), 400
    
    results = []
    
    for switch_ip in switch_ips:
        if not inventory.get_switch(switch_ip):
            results.append({
                'switch_ip': switch_ip,
                'status': 'error',
                'message': f'Switch {switch_ip} not found in inventory'
            })
            continue
        
        switch_results = []
        for vlan_data in vlans:
            try:
                vlan_id = int(vlan_data.get('vlan_id'))
                vlan_name = vlan_data.get('name', '').strip()
                
                if not vlan_name:
                    switch_results.append({
                        'vlan_id': vlan_id,
                        'status': 'error',
                        'message': 'VLAN name is required'
                    })
                    continue
                
                message = direct_rest_manager.create_vlan(switch_ip, vlan_id, vlan_name)
                switch_results.append({
                    'vlan_id': vlan_id,
                    'status': 'success',
                    'message': message
                })
                
            except Exception as e:
                switch_results.append({
                    'vlan_id': vlan_data.get('vlan_id'),
                    'status': 'error',
                    'message': str(e)
                })
        
        results.append({
            'switch_ip': switch_ip,
            'vlans': switch_results
        })
    
    return jsonify({'results': results})

# Status and monitoring endpoints
@app.route('/api/status', methods=['GET'])
def get_system_status():
    """Get overall system status."""
    switch_counts = inventory.get_switch_count()
    online_switches = inventory.get_online_switches()
    
    return jsonify({
        'switches': switch_counts,
        'online_switches': [switch.to_dict() for switch in online_switches],
        'timestamp': inventory.get_all_switches()[0].last_seen.isoformat() if online_switches else None
    })

# Configuration and utility endpoints
@app.route('/api/config/export', methods=['GET'])
def export_configuration():
    """Export current configuration for backup."""
    switches = [switch.to_dict() for switch in inventory.get_all_switches()]
    
    config_export = {
        'version': '1.0',
        'switches': switches,
        'settings': {
            'api_version': Config.API_VERSION,
            'ssl_verify': Config.SSL_VERIFY
        }
    }
    
    return jsonify(config_export)

@app.route('/api/config/import', methods=['POST'])
def import_configuration():
    """Import configuration from backup."""
    data = request.json or {}
    
    if 'switches' not in data:
        return jsonify({'error': 'Invalid configuration format'}), 400
    
    imported_count = 0
    errors = []
    
    for switch_data in data['switches']:
        ip_address = switch_data.get('ip_address')
        name = switch_data.get('name')
        
        if not ip_address:
            errors.append('Missing IP address in switch data')
            continue
        
        if inventory.add_switch(ip_address, name):
            imported_count += 1
        else:
            errors.append(f'Failed to import switch {ip_address}')
    
    return jsonify({
        'imported_count': imported_count,
        'errors': errors
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/switches/<switch_ip>/cleanup-sessions', methods=['POST'])
def cleanup_switch_sessions(switch_ip: str):
    """Attempt to cleanup sessions on a specific switch."""
    try:
        logger.info(f"Attempting session cleanup for {switch_ip}")
        success = direct_rest_manager.attempt_session_cleanup(switch_ip)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Session cleanup completed for {switch_ip}',
                'suggestion': 'You can now try connecting again.'
            })
        else:
            return jsonify({
                'status': 'partial',
                'message': f'Session cleanup attempted for {switch_ip}',
                'suggestion': 'Please wait 5-10 minutes for sessions to timeout naturally, or try again.'
            })
            
    except Exception as e:
        logger.error(f"Error during session cleanup for {switch_ip}: {e}")
        return jsonify({
            'error': f'Session cleanup failed: {str(e)}',
            'error_type': 'cleanup_failed',
            'suggestion': 'Please wait for natural session timeout or reboot the switch.'
        }), 500

# Debug endpoint to test route registration
@app.route('/api/debug/test')
def debug_test():
    """Debug endpoint to test route registration."""
    logger.info("Debug test route called")
    return jsonify({'status': 'success', 'message': 'Route registration working'})

# API Logging endpoints
@app.route('/api/logs/calls')
def get_api_call_logs():
    """Get recent API call logs with optional filtering."""
    logger.info("get_api_call_logs route called")
    limit = request.args.get('limit', 50, type=int)
    switch_ip = request.args.get('switch_ip')
    category = request.args.get('category')
    success_only = request.args.get('success_only')
    since = request.args.get('since')  # For polling new entries
    
    # Convert string 'true'/'false' to boolean
    if success_only is not None:
        success_only = success_only.lower() == 'true'
    
    try:
        calls = api_logger.get_recent_calls(
            limit=limit,
            switch_ip=switch_ip,
            category=category,
            success_only=success_only,
            since=since
        )
        stats = api_logger.get_call_statistics()
        
        return jsonify({
            'calls': calls,
            'statistics': stats,
            'total_returned': len(calls)
        })
    except Exception as e:
        logger.error(f"Error retrieving API call logs: {e}")
        return jsonify({'error': f'Error retrieving logs: {str(e)}'}), 500

@app.route('/api/logs/clear', methods=['POST'])
def clear_api_logs():
    """Clear all API call logs."""
    try:
        cleared_count = api_logger.clear_history()
        logger.info(f"API call logs cleared by user - {cleared_count} entries removed")
        return jsonify({
            'message': f'API call logs cleared successfully',
            'cleared_entries': cleared_count
        })
    except Exception as e:
        logger.error(f"Error clearing API logs: {e}")
        return jsonify({'error': f'Error clearing logs: {str(e)}'}), 500

@app.route('/api/logs/export')
def export_api_logs():
    """Export API logs in specified format."""
    format_type = request.args.get('format', 'json').lower()
    
    try:
        if format_type not in ['json', 'csv']:
            return jsonify({'error': 'Supported formats: json, csv'}), 400
            
        exported_data = api_logger.export_logs(format_type)
        
        # Set appropriate content type and filename
        if format_type == 'csv':
            response = make_response(exported_data)
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = 'attachment; filename=api_logs.csv'
        else:
            response = make_response(exported_data)
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = 'attachment; filename=api_logs.json'
            
        return response
    except Exception as e:
        logger.error(f"Error exporting API logs: {e}")
        return jsonify({'error': f'Error exporting logs: {str(e)}'}), 500

def normalize_status(raw_status: str) -> str:
    """Normalize raw status strings to consistent values."""
    if not raw_status:
        return "unknown"
    
    status_lower = str(raw_status).lower().strip()
    
    # Map specific known good statuses first (more specific)
    if status_lower in ["ok", "good", "normal", "up", "online", "operational", "active", "running"]:
        return "ok"
    # Map specific fault patterns (be more specific about faults)
    elif any(fault in status_lower for fault in ["fault_", "error_", "failed", "critical"]):
        return "error"
    elif any(warn in status_lower for warn in ["warning_", "alert_", "degraded"]):
        return "warning"
    # If we just get a simple status without underscore, it's likely OK
    elif status_lower in ["normal", "ready", "present", "enabled"]:
        return "ok"
    else:
        # Default to unknown for unrecognized statuses rather than assuming error
        return "unknown"

def get_human_readable_status(raw_status: str) -> str:
    """Convert raw status enums to human-readable labels."""
    if not raw_status:
        return "Unknown"
    
    # Handle specific fault patterns with descriptive labels
    status_upper = str(raw_status).upper().strip()
    
    if status_upper == "FAULT__INPUT":
        return "Input fault"
    elif status_upper.startswith("FAULT__"):
        fault_type = status_upper.replace("FAULT__", "").replace("_", " ").lower()
        return f"{fault_type.capitalize()} fault"
    elif status_upper.startswith("WARNING__"):
        warning_type = status_upper.replace("WARNING__", "").replace("_", " ").lower()
        return f"{warning_type.capitalize()} warning"
    elif status_upper in ["OK", "GOOD", "NORMAL", "UP", "ONLINE", "OPERATIONAL", "ACTIVE", "RUNNING"]:
        return "OK"
    else:
        return raw_status.replace("_", " ").title()

def get_cpu_usage(switch_ip: str, session_obj, capabilities: Dict[str, Any]) -> tuple:
    """Get CPU usage percentage and status."""
    if not capabilities.get('cpu_supported', False):
        return None, "na"
    
    # Use the discovered CPU endpoint if available
    cpu_endpoint = capabilities.get('cpu_endpoint')
    if not cpu_endpoint:
        return None, "na"
    
    try:
        cpu_response = session_obj.get(cpu_endpoint, timeout=5, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', cpu_endpoint, {}, None, cpu_response.status_code, cpu_response.text, 0)
        
        if cpu_response.status_code == 200:
            cpu_data = cpu_response.json()
            
            # Try to extract CPU percentage from various possible fields
            cpu_percentage = None
            
            # Try direct fields first
            for field in ['cpu_utilization', 'utilization', 'usage_percent', 'cpu_usage']:
                if field in cpu_data:
                    cpu_percentage = cpu_data[field]
                    break
            
            # If not found, look deeper in nested structures
            if cpu_percentage is None and isinstance(cpu_data, dict):
                for key, value in cpu_data.items():
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if any(cpu_key in subkey.lower() for cpu_key in ['cpu', 'utilization']):
                                if isinstance(subvalue, (int, float)):
                                    cpu_percentage = subvalue
                                    break
                        if cpu_percentage is not None:
                            break
            
            if cpu_percentage is not None:
                cpu_percentage = int(float(cpu_percentage))
                if cpu_percentage > 90:
                    return cpu_percentage, "error"
                elif cpu_percentage > 75:
                    return cpu_percentage, "warning"
                else:
                    return cpu_percentage, "ok"
                    
    except Exception as e:
        logger.debug(f"Error getting CPU usage for {switch_ip}: {e}")
    
    return None, "na"

@app.route('/api/switches/<switch_ip>/overview')
def get_switch_overview(switch_ip: str):
    """Get real switch overview data including model, ports, PoE, power, fans, CPU (cached)."""
    def fetch_overview():
        # Inner function contains the existing logic; used for caching
        # Two-attempt authentication with session cleanup on failure
        session_obj = None
        
        for attempt in range(2):
            try:
                session_obj = direct_rest_manager._authenticate(switch_ip)
                logger.info(f"Authentication successful for {switch_ip} on attempt {attempt + 1}")
                break
            except Exception as auth_error:
                logger.warning(f"Auth attempt {attempt + 1} failed for {switch_ip}: {auth_error}")
                if attempt == 0:
                    # First attempt failed, clean up sessions and retry
                    logger.info(f"Cleaning up sessions for {switch_ip} before retry")
                    direct_rest_manager.cleanup_session(switch_ip)
                    time.sleep(1)  # Brief delay before retry
                else:
                    # Second attempt failed, give up
                    logger.error(f"Authentication failed after 2 attempts for {switch_ip}")
                    raise Exception(f'Authentication failed: {str(auth_error)}')
        
        if not session_obj:
            raise Exception('Failed to authenticate to switch')
        
        # Get switch capabilities (reuse existing session)
        capabilities = capabilities_for(switch_ip, session_obj)
        
        # Get system information  
        system_response = session_obj.get(
            f"https://{switch_ip}/rest/v10.09/system",
            timeout=10,
            verify=Config.SSL_VERIFY
        )
        
        if system_response.status_code != 200:
            return jsonify({'error': f'Failed to get system information: {system_response.status_code}'}), 500
            
        system_data = system_response.json()
        api_logger.log_api_call('GET', f"https://{switch_ip}/rest/v10.09/system", {}, None, system_response.status_code, system_response.text, 0)
        
        # Get power supplies status and health info
        power_status = "unknown"
        power_supplies_info = []
        expected_psu_slots = capabilities.get('expected_psu_slots', 1)
        
        try:
            power_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/power_supplies"
            power_response = session_obj.get(power_url, timeout=5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', power_url, {}, None, power_response.status_code, power_response.text, 0)
            
            if power_response.status_code == 200:
                power_supplies = power_response.json()
                if power_supplies:
                    psu_statuses = []
                    for psu_key in power_supplies.keys():
                        try:
                            ps_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/power_supplies/{psu_key.replace('/', '%2F')}"
                            ps_response = session_obj.get(ps_url, timeout=5, verify=Config.SSL_VERIFY)
                            api_logger.log_api_call('GET', ps_url, {}, None, ps_response.status_code, ps_response.text, 0)
                            
                            if ps_response.status_code == 200:
                                ps_data = ps_response.json()
                                raw_status = ps_data.get('status', 'unknown')
                                raw_input_status = ps_data.get('input_status', 'unknown')
                                normalized_status = normalize_status(raw_status)
                                normalized_input_status = normalize_status(raw_input_status)
                                psu_statuses.append(normalized_status)
                                
                                # Create detailed PSU info with proper error messages
                                psu_detail = {
                                    'id': psu_key,
                                    'bay_label': f"PSU {psu_key.split('/')[-1]}" if '/' in psu_key else f"PSU {psu_key}",
                                    'status': normalized_status,
                                    'input_status': normalized_input_status
                                }
                                
                                power_supplies_info.append({
                                    'slot': psu_key,
                                    'status': normalized_status,
                                    'raw_status': raw_status,
                                    'detail': psu_detail
                                })
                        except Exception as e:
                            logger.debug(f"Error getting PSU {psu_key} status: {e}")
                    
                    # Determine overall power status
                    if any(status == "error" for status in psu_statuses):
                        power_status = "error"
                    elif any(status == "warning" for status in psu_statuses):
                        power_status = "warning"
                    elif all(status == "ok" for status in psu_statuses):
                        power_status = "ok"
                    else:
                        power_status = "unknown"
        except Exception as e:
            logger.debug(f"Error getting power status: {e}")
        
        # Get fan status
        fan_status = "unknown"
        fans_info = []
        
        try:
            fans_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/fans"
            fans_response = session_obj.get(fans_url, timeout=5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', fans_url, {}, None, fans_response.status_code, fans_response.text, 0)
            
            if fans_response.status_code == 200:
                fans = fans_response.json()
                if fans:
                    fan_statuses = []
                    for fan_key in fans.keys():
                        try:
                            fan_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/fans/{fan_key.replace('/', '%2F')}"
                            fan_response = session_obj.get(fan_url, timeout=5, verify=Config.SSL_VERIFY)
                            api_logger.log_api_call('GET', fan_url, {}, None, fan_response.status_code, fan_response.text, 0)
                            
                            if fan_response.status_code == 200:
                                fan_data = fan_response.json()
                                raw_status = fan_data.get('status', 'unknown')
                                normalized_status = normalize_status(raw_status)
                                fan_statuses.append(normalized_status)
                                fans_info.append({
                                    'slot': fan_key,
                                    'status': normalized_status,
                                    'raw_status': raw_status
                                })
                        except Exception as e:
                            logger.debug(f"Error getting fan {fan_key} status: {e}")
                    
                    # Determine overall fan status
                    if any(status == "error" for status in fan_statuses):
                        fan_status = "error"
                    elif any(status == "warning" for status in fan_statuses):
                        fan_status = "warning"
                    elif all(status == "ok" for status in fan_statuses):
                        fan_status = "ok"
                    else:
                        fan_status = "unknown"
        except Exception as e:
            logger.debug(f"Error getting fan status: {e}")
            
        # Get interface count (to determine port count)
        port_count = "unknown"
        try:
            interfaces_url = f"https://{switch_ip}/rest/v10.09/system/interfaces"
            interfaces_response = session_obj.get(interfaces_url, timeout=10, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', interfaces_url, {}, None, interfaces_response.status_code, interfaces_response.text, 0)
            
            if interfaces_response.status_code == 200:
                interfaces = interfaces_response.json()
                # Count physical interfaces (excluding sub-interfaces)
                physical_ports = [iface for iface in interfaces.keys() if ':' not in iface and iface.startswith('1/1/')]
                port_count = str(len(physical_ports))
        except Exception as e:
            logger.debug(f"Error getting interface count: {e}")
        
        # Get CPU usage using capabilities
        cpu_usage, cpu_status = get_cpu_usage(switch_ip, session_obj, capabilities)
        
        # Get PoE status from chassis subsystem data
        poe_status = "N/A"
        poe_details = {}
        if capabilities.get('poe_supported', False):
            try:
                # Use chassis-level PoE data since REST PoE endpoints return 404
                chassis_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1"
                chassis_response = session_obj.get(chassis_url, timeout=5, verify=Config.SSL_VERIFY)
                api_logger.log_api_call('GET', chassis_url, {}, None, chassis_response.status_code, chassis_response.text, 0)
                
                if chassis_response.status_code == 200:
                    chassis_data = chassis_response.json()
                    poe_power = chassis_data.get('poe_power', {})
                    if poe_power:
                        # Extract PoE power information
                        available_power = poe_power.get('available_power', 0)
                        drawn_power = poe_power.get('drawn_power', 0)
                        reserved_power = poe_power.get('reserved_power', 0)
                        
                        if available_power > 0:
                            # Calculate PoE utilization
                            utilization = (drawn_power / available_power) * 100 if available_power > 0 else 0
                            
                            # Set status based on utilization
                            if utilization > 95:
                                poe_status = "warning"  # Near capacity
                            elif utilization > 0:
                                poe_status = "ok"
                            else:
                                poe_status = "ok"  # Available but not in use
                            
                            # Store PoE details for UI
                            poe_details = {
                                'available_power': available_power,
                                'drawn_power': drawn_power,
                                'reserved_power': reserved_power,
                                'utilization_percent': round(utilization, 1),
                                'status': poe_status
                            }
                        else:
                            poe_status = "error"  # PoE subsystem present but no available power
                    else:
                        poe_status = "unknown"  # No PoE data in chassis - might not have PoE
                else:
                    poe_status = "unknown"
            except Exception as e:
                logger.debug(f"Error getting PoE status from chassis: {e}")
                poe_status = "unknown"
        
        # Get model information
        platform_name = system_data.get('platform_name', 'Unknown')
        hostname = system_data.get('applied_hostname', 'Unknown')
        firmware_version = system_data.get('firmware_version', 'Unknown')
        
        # Calculate health status
        health_status = "ONLINE"
        health_reasons = []
        
        # Check for specific PSU errors
        psu_errors = [psu for psu in power_supplies_info if psu['status'] == 'error']
        psu_warnings = [psu for psu in power_supplies_info if psu['status'] == 'warning']
        
        # Check for specific fan errors
        fan_errors = [fan for fan in fans_info if fan['status'] == 'error']
        fan_warnings = [fan for fan in fans_info if fan['status'] == 'warning']
        
        # Check for errors
        if psu_errors:
            health_status = "ERRORS"
            for psu in psu_errors:
                bay_label = psu.get('detail', {}).get('bay_label', f"PSU {psu['slot']}")
                readable_status = get_human_readable_status(psu['raw_status'])
                health_reasons.append(f"{bay_label}: {readable_status}")
        elif fan_errors:
            health_status = "ERRORS"
            for fan in fan_errors:
                readable_status = get_human_readable_status(fan['raw_status'])
                health_reasons.append(f"Fan {fan['slot']}: {readable_status}")
        elif cpu_status == "error":
            health_status = "ERRORS" 
            health_reasons.append("CPU utilization critically high")
            
        # Check for degraded conditions
        elif health_status == "ONLINE":  # Only if no errors
            if len(power_supplies_info) < expected_psu_slots:
                health_status = "DEGRADED"
                health_reasons.append(f"Only {len(power_supplies_info)} of {expected_psu_slots} PSU present")
            elif psu_warnings:
                health_status = "DEGRADED"
                for psu in psu_warnings:
                    bay_label = psu.get('detail', {}).get('bay_label', f"PSU {psu['slot']}")
                    readable_status = get_human_readable_status(psu['raw_status'])
                    health_reasons.append(f"{bay_label}: {readable_status}")
            elif fan_warnings:
                health_status = "DEGRADED"
                for fan in fan_warnings:
                    readable_status = get_human_readable_status(fan['raw_status'])
                    health_reasons.append(f"Fan {fan['slot']}: {readable_status}")
            elif cpu_status == "warning":
                health_status = "DEGRADED"
                health_reasons.append("CPU utilization high")
        
        # Update inventory switch status to reflect PSU/fan errors on dashboard counts
        if psu_errors or fan_errors:
            reason = "; ".join([
                psu.get('detail', {}).get('bay_label', f"PSU {psu['slot']}") + ": " + get_human_readable_status(psu['raw_status'])
                for psu in psu_errors
            ] + [
                f"Fan {fan['slot']}: " + get_human_readable_status(fan['raw_status'])
                for fan in fan_errors
            ])
            inventory.update_switch_status(switch_ip, 'error', error_message=reason)
        else:
            # Keep existing status if degraded/ok but ensure not lingering error
            inventory.update_switch_status(switch_ip, 'online')

        overview_data = {
            'model': f"Aruba CX {platform_name}",
            'hostname': hostname,
            'firmware_version': firmware_version,
            'port_count': port_count,
            'poe_status': poe_status,
            'poe_details': poe_details,
            'power_status': power_status,
            'fan_status': fan_status,
            'cpu_status': cpu_status,
            'cpu_usage': cpu_usage,
            'health': {
                'status': health_status,
                'reasons': health_reasons[:3]  # Limit to first 3 reasons
            },
            'psu_details': [psu.get('detail', {}) for psu in power_supplies_info if psu.get('detail')],
            'uptime': system_data.get('boot_time', 0),
            'management_ip': system_data.get('mgmt_intf_status', {}).get('ip', switch_ip)
        }
        
        return overview_data
    try:
        # Attempt to use cache for overview (60s TTL)
        overview = get_cached_or_fetch(switch_cache, switch_ip, 'overview', fetch_overview, ttl=60)
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/overview', {}, None, 200, str(overview), 0)
        return jsonify(overview)
    except Exception as e:
        logger.error(f"Error getting overview for {switch_ip}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_response = {'error': f'Failed to get switch overview: {str(e)}'}
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/overview', {}, None, 500, str(error_response), 0)
        return jsonify(error_response), 500

@app.route('/api/switches/<switch_ip>/vlans')
def get_switch_vlans(switch_ip: str):
    """Get real VLAN data from the switch."""
    try:
        # Two-attempt authentication with session cleanup on failure
        session_obj = None
        
        for attempt in range(2):
            try:
                session_obj = direct_rest_manager._authenticate(switch_ip)
                logger.info(f"Authentication successful for VLANs on {switch_ip} on attempt {attempt + 1}")
                break
            except Exception as auth_error:
                logger.warning(f"VLANs auth attempt {attempt + 1} failed for {switch_ip}: {auth_error}")
                if attempt == 0:
                    logger.info(f"Cleaning up sessions for VLANs call on {switch_ip}")
                    direct_rest_manager.cleanup_session(switch_ip)
                    time.sleep(1)
                else:
                    logger.error(f"VLANs authentication failed after 2 attempts for {switch_ip}")
                    error_response = {'error': f'Authentication failed: {str(auth_error)}'}
                    api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/vlans', {}, None, 401, str(error_response), 0)
                    return jsonify(error_response), 401
        
        if not session_obj:
            error_response = {'error': 'Failed to authenticate to switch'}
            api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/vlans', {}, None, 401, str(error_response), 0)
            return jsonify(error_response), 401
        
        # Get VLANs list
        vlans_url = f"https://{switch_ip}/rest/v10.09/system/vlans"
        vlans_response = session_obj.get(vlans_url, timeout=10, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', vlans_url, {}, None, vlans_response.status_code, vlans_response.text, 0)
        
        if vlans_response.status_code != 200:
            error_response = {'error': f'Failed to get VLANs: {vlans_response.status_code}'}
            api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/vlans', {}, None, 500, str(error_response), 0)
            return jsonify(error_response), 500
            
        vlans_list = vlans_response.json()
        vlans_data = []
        
        # Get cached interfaces to calculate VLAN membership
        try:
            interfaces_data = _fetch_bulk_interfaces(switch_ip, session_obj)
            vlan_membership = _calculate_vlan_membership(interfaces_data.get('interfaces', []))
        except Exception as e:
            logger.warning(f"Failed to get interface data for VLAN membership: {e}")
            vlan_membership = {}
        
        # Get details for each VLAN
        for vlan_id, vlan_url in vlans_list.items():
            try:
                vlan_detail_url = f"https://{switch_ip}/rest/v10.09/system/vlans/{vlan_id}"
                vlan_response = session_obj.get(vlan_detail_url, timeout=5, verify=Config.SSL_VERIFY)
                api_logger.log_api_call('GET', vlan_detail_url, {}, None, vlan_response.status_code, vlan_response.text, 0)
                
                if vlan_response.status_code == 200:
                    vlan_data = vlan_response.json()
                    vlan_int_id = int(vlan_id)
                    membership = vlan_membership.get(vlan_int_id, {'tagged': 0, 'untagged': 0})
                    
                    vlans_data.append({
                        'id': vlan_int_id,
                        'name': vlan_data.get('name', f'VLAN{vlan_id}'),
                        'admin_state': vlan_data.get('admin', 'unknown'),
                        'oper_state': vlan_data.get('oper_state', 'unknown'),
                        'description': vlan_data.get('description', ''),
                        'tagged_interfaces': membership['tagged'],
                        'untagged_interfaces': membership['untagged']
                    })
                else:
                    logger.warning(f"Failed to get VLAN {vlan_id} details: {vlan_response.status_code}")
                    vlan_int_id = int(vlan_id)
                    membership = vlan_membership.get(vlan_int_id, {'tagged': 0, 'untagged': 0})
                    
                    vlans_data.append({
                        'id': vlan_int_id,
                        'name': f'VLAN{vlan_id}',
                        'admin_state': 'unknown',
                        'oper_state': 'unknown',
                        'description': '',
                        'tagged_interfaces': membership['tagged'],
                        'untagged_interfaces': membership['untagged']
                    })
            except Exception as e:
                logger.warning(f"Error getting VLAN {vlan_id} details: {e}")
                # Add basic VLAN info even if details fail
                vlan_int_id = int(vlan_id)
                membership = vlan_membership.get(vlan_int_id, {'tagged': 0, 'untagged': 0})
                
                vlans_data.append({
                    'id': vlan_int_id,
                    'name': f'VLAN{vlan_id}',
                    'admin_state': 'unknown',
                    'oper_state': 'unknown',
                    'description': '',
                    'tagged_interfaces': membership['tagged'],
                    'untagged_interfaces': membership['untagged']
                })
        
        # Sort by VLAN ID
        vlans_data.sort(key=lambda x: x['id'])
        
        result = {'vlans': vlans_data, 'total_count': len(vlans_data)}
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/vlans', {}, None, 200, str(result), 0)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting VLANs for {switch_ip}: {e}")
        error_response = {'error': f'Failed to get VLANs: {str(e)}'}
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/vlans', {}, None, 500, str(error_response), 0)
        return jsonify(error_response), 500

@app.route('/api/switches/<switch_ip>/interfaces')
def get_switch_interfaces(switch_ip: str):
    """Get interface data using cached bulk fetch with optional LLDP."""
    try:
        # Get include parameters for additional data
        include_lldp = request.args.get('include') == 'lldp'
        
        def fetch_interfaces():
            # Two-attempt authentication with session cleanup on failure
            session_obj = None
            for attempt in range(2):
                try:
                    session_obj = direct_rest_manager._authenticate(switch_ip)
                    logger.info(f"Authentication successful for interfaces on {switch_ip} on attempt {attempt + 1}")
                    break
                except Exception as auth_error:
                    logger.warning(f"Interfaces auth attempt {attempt + 1} failed for {switch_ip}: {auth_error}")
                    if attempt == 0:
                        logger.info(f"Cleaning up sessions for interfaces call on {switch_ip}")
                        direct_rest_manager.cleanup_session(switch_ip)
                        time.sleep(1)
                    else:
                        raise auth_error
            
            if not session_obj:
                raise Exception('Failed to authenticate to switch')
            
            # Fetch bulk interfaces with VLAN data
            interfaces_data = _fetch_bulk_interfaces(switch_ip, session_obj)
            
            # Add LLDP neighbors if requested (per-port calls but cached)
            if include_lldp and interfaces_data.get('interfaces'):
                enhanced_interfaces = []
                for interface in interfaces_data['interfaces']:
                    enhanced_interface = interface.copy()
                    
                    # Fetch LLDP neighbors for this interface
                    try:
                        lldp_neighbors = _fetch_interface_lldp_neighbors(switch_ip, session_obj, interface['name'])
                        enhanced_interface['lldp_neighbors'] = lldp_neighbors
                        enhanced_interface['lldp_count'] = len(lldp_neighbors)
                    except Exception as e:
                        logger.debug(f"LLDP fetch failed for {interface['name']}: {e}")
                        enhanced_interface['lldp_neighbors'] = []
                        enhanced_interface['lldp_count'] = 0
                    
                    enhanced_interfaces.append(enhanced_interface)
                
                interfaces_data['interfaces'] = enhanced_interfaces
            
            return interfaces_data
        
        # Use cache with 5-minute TTL
        cache_key = f"interfaces_bulk{'_lldp' if include_lldp else ''}"
        try:
            interfaces_data = get_cached_or_fetch(interface_cache, switch_ip, cache_key, fetch_interfaces)
        except Exception as cache_error:
            logger.warning(f"Cache error, falling back to direct fetch: {cache_error}")
            interfaces_data = fetch_interfaces()

        # Ensure management interface is present using system mgmt_intf_status if not found in bulk
        try:
            if not interfaces_data.get('management'):
                # Reuse existing authenticated session to get system mgmt status
                session_obj = direct_rest_manager._authenticate(switch_ip)
                sys_url = f"https://{switch_ip}/rest/v10.09/system"
                sys_resp = session_obj.get(sys_url, timeout=5, verify=Config.SSL_VERIFY)
                api_logger.log_api_call('GET', sys_url, {}, None, sys_resp.status_code, sys_resp.text, 0)
                if sys_resp.status_code == 200:
                    sys_data = sys_resp.json()
                    mgmt = sys_data.get('mgmt_intf_status') or {}
                    ipv4 = mgmt.get('ip') or mgmt.get('ip_address') or mgmt.get('ipv4')
                    status = (mgmt.get('status') or mgmt.get('link_state') or 'unknown').lower()
                    # Normalize status to up/down/disabled
                    if status == 'down':
                        norm = 'disabled'
                    elif status == 'up' or ipv4:
                        norm = 'up'
                    else:
                        norm = 'down'
                    interfaces_data['management'] = [{
                        'name': 'mgmt',
                        'admin_state': 'up' if norm == 'up' else 'down',
                        'link_state': 'up' if norm == 'up' else 'down',
                        'status': norm,
                        'description': 'Management interface',
                        'ipv4': ipv4 or '',
                        'ipv6': mgmt.get('ipv6') or ''
                    }]
        except Exception as e:
            logger.debug(f"Failed to populate management interface from system: {e}")
        
        result = {
            'interfaces': interfaces_data.get('interfaces', []),
            'management': interfaces_data.get('management', []),
            'total_count': interfaces_data.get('total_count', 0)
        }
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/interfaces', {}, None, 200, str(result), 0)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting interfaces for {switch_ip}: {e}")
        error_response = {'error': f'Failed to get interfaces: {str(e)}'}
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/interfaces', {}, None, 500, str(error_response), 0)
        return jsonify(error_response), 500

@app.route('/api/switches/<switch_ip>/vlans/<int:vlan_id>', methods=['PATCH'])
def edit_vlan(switch_ip: str, vlan_id: int):
    """Edit a VLAN on the switch."""
    try:
        data = request.get_json() or {}
        
        # Two-attempt authentication with session cleanup on failure
        session = None
        for attempt in range(2):
            try:
                session = direct_rest_manager._authenticate(switch_ip)
                break
            except Exception as auth_error:
                if attempt == 0:
                    direct_rest_manager.cleanup_session(switch_ip)
                    time.sleep(1)
                else:
                    return jsonify({'error': f'Authentication failed: {str(auth_error)}'}), 401
        
        # Build update payload
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'description' in data:
            update_data['description'] = data['description']
        if 'admin_state' in data:
            update_data['admin'] = data['admin_state']
            
        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400
            
        # PATCH the VLAN
        patch_response = session.patch(
            f"https://{switch_ip}/rest/v10.09/system/vlans/{vlan_id}",
            json=update_data,
            timeout=10,
            verify=Config.SSL_VERIFY
        )
        
        if patch_response.status_code in [200, 204]:
            result = {'status': 'success', 'message': f'VLAN {vlan_id} updated successfully'}
            api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/vlans/{vlan_id}', {}, None, 200, str(result), 0)
            return jsonify(result)
        else:
            error_response = {'error': f'Failed to update VLAN: {patch_response.text}'}
            api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/vlans/{vlan_id}', {}, None, patch_response.status_code, str(error_response), 0)
            return jsonify(error_response), patch_response.status_code
            
    except Exception as e:
        logger.error(f"Error editing VLAN {vlan_id} on {switch_ip}: {e}")
        error_response = {'error': f'Failed to edit VLAN: {str(e)}'}
        api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/vlans/{vlan_id}', {}, None, 500, str(error_response), 0)
        return jsonify(error_response), 500

@app.route('/api/switches/<switch_ip>/interfaces/<path:interface_name>', methods=['PATCH'])
def edit_interface(switch_ip: str, interface_name: str):
    """Edit an interface on the switch."""
    try:
        data = request.get_json() or {}
        
        # Two-attempt authentication with session cleanup on failure
        session = None
        for attempt in range(2):
            try:
                session = direct_rest_manager._authenticate(switch_ip)
                break
            except Exception as auth_error:
                if attempt == 0:
                    direct_rest_manager.cleanup_session(switch_ip)
                    time.sleep(1)
                else:
                    return jsonify({'error': f'Authentication failed: {str(auth_error)}'}), 401
        
        # Build update payload
        update_data = {}
        if 'description' in data:
            update_data['description'] = data['description']
        if 'admin_state' in data:
            update_data['admin_state'] = data['admin_state']
        if 'mtu' in data:
            try:
                update_data['mtu'] = int(data['mtu'])
            except (ValueError, TypeError):
                return jsonify({'error': 'MTU must be a valid integer'}), 400
                
        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        # URL encode interface name
        encoded_name = interface_name.replace('/', '%2F')
        
        # PATCH the interface
        patch_response = session.patch(
            f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded_name}",
            json=update_data,
            timeout=10,
            verify=Config.SSL_VERIFY
        )
        
        url_path = f'/api/switches/{switch_ip}/interfaces/{interface_name}'
        if patch_response.status_code in [200, 204]:
            result = {'status': 'success', 'message': f'Interface {interface_name} updated successfully'}
            api_logger.log_api_call('PATCH', url_path, {}, update_data, 200, str(result), 0)
            return jsonify(result)
        else:
            error_response = {'error': f'Failed to update interface: {patch_response.text}'}
            api_logger.log_api_call('PATCH', url_path, {}, update_data, patch_response.status_code, str(error_response), 0)
            return jsonify(error_response), patch_response.status_code
            
    except Exception as e:
        logger.error(f"Error editing interface {interface_name} on {switch_ip}: {e}")
        error_response = {'error': f'Failed to edit interface: {str(e)}'}
        api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/interfaces/{interface_name}', {}, None, 500, str(error_response), 0)
        return jsonify(error_response), 500

@app.route('/api/diagnostics/<switch_ip>')
def run_switch_diagnostics(switch_ip: str):
    """Run comprehensive diagnostics on a specific switch."""
    try:
        results = run_diagnostics(switch_ip, username="admin", password="Aruba123!")
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error running diagnostics on {switch_ip}: {e}")
        return jsonify({
            'error': f'Error running diagnostics: {str(e)}',
            'switch_ip': switch_ip
        }), 500

@app.route('/debug/test-auth/<switch_ip>', methods=['GET'])
def test_authentication_debug(switch_ip: str):
    """Debug authentication to see what's happening."""
    try:
        session = direct_rest_manager._authenticate(switch_ip)
        
        # Try to get system info
        response = session.get(
            f"https://{switch_ip}/rest/v10.09/system",
            timeout=10,
            verify=Config.SSL_VERIFY
        )
        
        return jsonify({
            'auth_success': True,
            'session_cookies': str(session.cookies),
            'system_request_status': response.status_code,
            'system_request_response': response.text[:500] if response.status_code == 200 else response.text
        })
        
    except Exception as e:
        return jsonify({
            'auth_success': False,
            'error': str(e)
        }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {error}", exc_info=True)
    return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    logger.info("Starting Enhanced PyAOS-CX Automation Toolkit")
    logger.info(f"Configuration: API Version {Config.API_VERSION}, SSL Verify: {Config.SSL_VERIFY}")
    logger.info(f"Default switches: {Config.DEFAULT_SWITCHES}")
    
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=Config.FLASK_DEBUG,
        use_reloader=False
    )
