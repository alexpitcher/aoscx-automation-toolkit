"""
Enhanced PyAOS-CX Automation Toolkit - Main Flask Application
"""
import logging
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
    data = request.json or {}
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