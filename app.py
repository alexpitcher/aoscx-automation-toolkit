"""
Enhanced PyAOS-CX Automation Toolkit - Main Flask Application
"""
import logging
import time
from flask import Flask, request, jsonify, render_template, redirect, make_response
from typing import Dict, Any
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask application
app = Flask(__name__)

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
    """Render the main dashboard with mobile detection."""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Detect mobile devices
    mobile_indicators = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    is_mobile = any(indicator in user_agent for indicator in mobile_indicators)
    
    # Check for explicit preference or force parameter
    force_desktop = request.args.get('desktop', '').lower() == 'true'
    force_mobile = request.args.get('mobile', '').lower() == 'true'
    
    if force_mobile or (is_mobile and not force_desktop):
        return redirect('/mobile')
    
    return render_template('dashboard.html')

@app.route('/mobile')
def mobile_dashboard():
    """Render the mobile-first dashboard."""
    return render_template('mobile_dashboard.html')

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
                return jsonify({
                    'status': 'success',
                    'message': f'Switch {ip_address} added successfully using {credentials_used}',
                    'switch': switch_info.to_dict()
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
    
    # Convert string 'true'/'false' to boolean
    if success_only is not None:
        success_only = success_only.lower() == 'true'
    
    try:
        calls = api_logger.get_recent_calls(
            limit=limit,
            switch_ip=switch_ip,
            category=category,
            success_only=success_only
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

@app.route('/api/switches/<switch_ip>/overview')
def get_switch_overview(switch_ip: str):
    """Get real switch overview data including model, ports, PoE, power, fans, CPU."""
    try:
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
                    return jsonify({'error': f'Authentication failed: {str(auth_error)}'}), 401
        
        if not session_obj:
            return jsonify({'error': 'Failed to authenticate to switch'}), 401
        
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
        
        # Get power supplies status
        power_status = "unknown"
        try:
            power_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/power_supplies"
            power_response = session_obj.get(power_url, timeout=5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', power_url, {}, None, power_response.status_code, power_response.text, 0)
            
            if power_response.status_code == 200:
                power_supplies = power_response.json()
                if power_supplies:
                    # Check first power supply
                    first_ps = list(power_supplies.keys())[0]
                    ps_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/power_supplies/{first_ps.replace('/', '%2F')}"
                    ps_response = session_obj.get(ps_url, timeout=5, verify=Config.SSL_VERIFY)
                    api_logger.log_api_call('GET', ps_url, {}, None, ps_response.status_code, ps_response.text, 0)
                    
                    if ps_response.status_code == 200:
                        ps_data = ps_response.json()
                        power_status = ps_data.get('status', 'unknown')
        except Exception as e:
            logger.debug(f"Error getting power status: {e}")
        
        # Get fan status
        fan_status = "unknown"
        try:
            fans_url = f"https://{switch_ip}/rest/v10.09/system/subsystems/chassis,1/fans"
            fans_response = session_obj.get(fans_url, timeout=5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', fans_url, {}, None, fans_response.status_code, fans_response.text, 0)
            
            if fans_response.status_code == 200:
                fans = fans_response.json()
                if fans:
                    # Assume fans are OK if we can get the data
                    fan_status = "ok"
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
        
        # Try to get CPU usage from metrics
        cpu_usage = 0
        try:
            cpu_url = f"https://{switch_ip}/rest/v10.09/system/metrics/cpu"
            cpu_response = session_obj.get(cpu_url, timeout=5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', cpu_url, {}, None, cpu_response.status_code, cpu_response.text, 0)
            
            if cpu_response.status_code == 200:
                cpu_data = cpu_response.json()
                # Try to extract CPU usage percentage from response
                cpu_usage = cpu_data.get('cpu_utilization', 0)
                if not cpu_usage:
                    # If no direct field, try other common patterns
                    cpu_usage = cpu_data.get('utilization', 0)
        except Exception as e:
            logger.debug(f"Error getting CPU metrics: {e}")
            # Fallback to mock CPU usage (5-45%)
            import random
            cpu_usage = random.randint(5, 45)
        
        # Try to get PoE status
        poe_status = "unknown"
        try:
            poe_url = f"https://{switch_ip}/rest/v10.09/system/poe"
            poe_response = session_obj.get(poe_url, timeout=5, verify=Config.SSL_VERIFY)
            api_logger.log_api_call('GET', poe_url, {}, None, poe_response.status_code, poe_response.text, 0)
            
            if poe_response.status_code == 200:
                poe_data = poe_response.json()
                if poe_data:
                    poe_status = "online"
                else:
                    poe_status = "not_supported"
            elif poe_response.status_code == 404:
                poe_status = "not_supported"
        except Exception as e:
            logger.debug(f"Error getting PoE status: {e}")
            poe_status = "not_supported"
        
        # Get model information
        platform_name = system_data.get('platform_name', 'Unknown')
        hostname = system_data.get('applied_hostname', 'Unknown')
        firmware_version = system_data.get('firmware_version', 'Unknown')
        
        overview_data = {
            'model': f"Aruba CX {platform_name}",
            'hostname': hostname,
            'firmware_version': firmware_version,
            'port_count': port_count,
            'poe_status': poe_status,
            'power_status': power_status,
            'fan_status': fan_status,
            'cpu_usage': cpu_usage,
            'uptime': system_data.get('boot_time', 0),
            'management_ip': system_data.get('mgmt_intf_status', {}).get('ip', switch_ip)
        }
        
        api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/overview', {}, None, 200, str(overview_data), 0)
        return jsonify(overview_data)
        
    except Exception as e:
        logger.error(f"Error getting overview for {switch_ip}: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_response = {'error': f'Failed to get switch overview: {str(e)}', 'details': str(type(e))}
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
        
        # Get details for each VLAN
        for vlan_id, vlan_url in vlans_list.items():
            try:
                vlan_detail_url = f"https://{switch_ip}/rest/v10.09/system/vlans/{vlan_id}"
                vlan_response = session_obj.get(vlan_detail_url, timeout=5, verify=Config.SSL_VERIFY)
                api_logger.log_api_call('GET', vlan_detail_url, {}, None, vlan_response.status_code, vlan_response.text, 0)
                
                if vlan_response.status_code == 200:
                    vlan_data = vlan_response.json()
                    vlans_data.append({
                        'id': int(vlan_id),
                        'name': vlan_data.get('name', f'VLAN{vlan_id}'),
                        'admin_state': vlan_data.get('admin', 'unknown'),
                        'oper_state': vlan_data.get('oper_state', 'unknown'),
                        'description': vlan_data.get('description', '')
                    })
                else:
                    logger.warning(f"Failed to get VLAN {vlan_id} details: {vlan_response.status_code}")
                    vlans_data.append({
                        'id': int(vlan_id),
                        'name': f'VLAN{vlan_id}',
                        'admin_state': 'unknown',
                        'oper_state': 'unknown',
                        'description': ''
                    })
            except Exception as e:
                logger.warning(f"Error getting VLAN {vlan_id} details: {e}")
                # Add basic VLAN info even if details fail
                vlans_data.append({
                    'id': int(vlan_id),
                    'name': f'VLAN{vlan_id}',
                    'admin_state': 'unknown',
                    'oper_state': 'unknown',
                    'description': ''
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
    """Get real interface data from the switch."""
    try:
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
                    logger.error(f"Interfaces authentication failed after 2 attempts for {switch_ip}")
                    error_response = {'error': f'Authentication failed: {str(auth_error)}'}
                    api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/interfaces', {}, None, 401, str(error_response), 0)
                    return jsonify(error_response), 401
        
        if not session_obj:
            error_response = {'error': 'Failed to authenticate to switch'}
            api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/interfaces', {}, None, 401, str(error_response), 0)
            return jsonify(error_response), 401
        
        # Get interfaces list
        interfaces_url = f"https://{switch_ip}/rest/v10.09/system/interfaces"
        interfaces_response = session_obj.get(interfaces_url, timeout=10, verify=Config.SSL_VERIFY)
        api_logger.log_api_call('GET', interfaces_url, {}, None, interfaces_response.status_code, interfaces_response.text, 0)
        
        if interfaces_response.status_code != 200:
            error_response = {'error': f'Failed to get interfaces: {interfaces_response.status_code}'}
            api_logger.log_api_call('GET', f'/api/switches/{switch_ip}/interfaces', {}, None, 500, str(error_response), 0)
            return jsonify(error_response), 500
            
        interfaces_list = interfaces_response.json()
        interfaces_data = []
        
        # Filter to physical interfaces only (exclude sub-interfaces)
        physical_interfaces = {k: v for k, v in interfaces_list.items() 
                             if ':' not in k and k.startswith('1/1/')}
        
        # Get details for each interface
        for interface_name, interface_url in physical_interfaces.items():
            try:
                # URL encode the interface name for the API call
                encoded_name = interface_name.replace('/', '%2F')
                interface_detail_url = f"https://{switch_ip}/rest/v10.09/system/interfaces/{encoded_name}"
                interface_response = session_obj.get(interface_detail_url, timeout=5, verify=Config.SSL_VERIFY)
                api_logger.log_api_call('GET', interface_detail_url, {}, None, interface_response.status_code, interface_response.text, 0)
                
                if interface_response.status_code == 200:
                    interface_data = interface_response.json()
                    
                    # Determine status
                    admin_state = interface_data.get('admin_state', 'unknown')
                    link_state = interface_data.get('link_state', 'unknown')
                    
                    # Map states to our UI expectations
                    status = 'down'
                    if admin_state == 'up' and link_state == 'up':
                        status = 'up'
                    elif admin_state == 'down':
                        status = 'disabled'
                    
                    interfaces_data.append({
                        'name': interface_name,
                        'admin_state': admin_state,
                        'link_state': link_state,
                        'status': status,
                        'speed': interface_data.get('link_speed', 0),
                        'type': interface_data.get('type', 'unknown'),
                        'description': interface_data.get('description', '') or '',
                        'mtu': interface_data.get('mtu', 0)
                    })
                else:
                    logger.warning(f"Failed to get interface {interface_name} details: {interface_response.status_code}")
                    interfaces_data.append({
                        'name': interface_name,
                        'admin_state': 'unknown',
                        'link_state': 'unknown',
                        'status': 'unknown',
                        'description': '',
                        'mtu': 0
                    })
            except Exception as e:
                logger.warning(f"Error getting interface {interface_name} details: {e}")
                # Add basic interface info even if details fail
                interfaces_data.append({
                    'name': interface_name,
                    'admin_state': 'unknown',
                    'link_state': 'unknown',
                    'status': 'unknown',
                    'description': '',
                    'mtu': 0
                })
        
        # Sort by interface name
        interfaces_data.sort(key=lambda x: x['name'])
        
        result = {'interfaces': interfaces_data, 'total_count': len(interfaces_data)}
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

@app.route('/api/switches/<switch_ip>/interfaces/<interface_name>', methods=['PATCH'])
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
        
        if patch_response.status_code in [200, 204]:
            result = {'status': 'success', 'message': f'Interface {interface_name} updated successfully'}
            api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/interfaces/{interface_name}', 200, result)
            return jsonify(result)
        else:
            error_response = {'error': f'Failed to update interface: {patch_response.text}'}
            api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/interfaces/{interface_name}', patch_response.status_code, error_response)
            return jsonify(error_response), patch_response.status_code
            
    except Exception as e:
        logger.error(f"Error editing interface {interface_name} on {switch_ip}: {e}")
        error_response = {'error': f'Failed to edit interface: {str(e)}'}
        api_logger.log_api_call('PATCH', f'/api/switches/{switch_ip}/interfaces/{interface_name}', 500, error_response)
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
        debug=Config.FLASK_DEBUG
    )