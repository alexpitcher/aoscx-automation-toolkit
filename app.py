"""
Enhanced PyAOS-CX Automation Toolkit - Main Flask Application
"""
import logging
from flask import Flask, request, jsonify, render_template, redirect
from typing import Dict, Any
import requests
from config.settings import Config
from config.switch_inventory import inventory, SwitchInfo
from core.direct_rest_manager import direct_rest_manager

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
    """Add a new switch to inventory with credential handling."""
    data = request.json or {}
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
                logger.info(f"Trying user-provided credentials for {ip_address}: {username}")
                result = direct_rest_manager.test_connection_with_credentials(ip_address, username, password)
                logger.info(f"User credential test result for {ip_address}: status={result.get('status')}")
                if result.get('status') == 'online':
                    success = True
                    credentials_used = f"{username}/***"
                    # Store credentials for future use
                    inventory.store_credentials(ip_address, username, password)
            except Exception as e:
                logger.warning(f"User-provided credentials failed for {ip_address}: {e}")
        
        if not success:
            # Try default credential combinations
            logger.info(f"Trying default credentials for {ip_address}")
            default_credentials = [
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
                        credentials_used = f"{try_username}/{try_password if try_password else '(blank)'}"
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
                logger.info(f"Added new switch: {ip_address} using {credentials_used}")
                return jsonify({
                    'message': f'Switch {ip_address} added successfully using {credentials_used}',
                    'switch': switch_info.to_dict()
                })
            else:
                return jsonify({'error': 'Failed to add switch to inventory'}), 500
        else:
            # All authentication attempts failed
            logger.warning(f"All authentication attempts failed for {ip_address}")
            error_msg = f'Failed to authenticate to switch {ip_address}. Tried default credentials (admin/admin, admin/blank) and any saved credentials. Please verify the IP address is correct and the switch is reachable.'
            return jsonify({
                'error': error_msg,
                'error_type': 'authentication_failed',
                'suggestion': 'Please check the IP address and provide correct credentials using the credentials section.'
            }), 401
            
    except Exception as e:
        logger.error(f"Error adding switch {ip_address}: {e}")
        return jsonify({'error': f'Error adding switch: {str(e)}'}), 500

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
    """Test connection to a specific switch."""
    if not inventory.get_switch(switch_ip):
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        result = direct_rest_manager.test_connection(switch_ip)
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
    """Get VLANs from a specific switch with detailed names."""
    switch_ip = request.args.get('switch_ip')
    load_details = request.args.get('load_details', 'true').lower() == 'true'
    
    if not switch_ip:
        return jsonify({'error': 'switch_ip parameter is required'}), 400
    
    if not inventory.get_switch(switch_ip):
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        # Enable detailed loading by default for better UX
        vlans = direct_rest_manager.list_vlans(switch_ip, load_details=load_details)
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
    """Create a VLAN on a specific switch with enhanced error handling."""
    data = request.json or {}
    switch_ip = data.get('switch_ip')
    vlan_id = data.get('vlan_id')
    name = data.get('name')
    
    # Validation
    if not all([switch_ip, vlan_id, name]):
        return jsonify({'error': 'switch_ip, vlan_id, and name are required'}), 400
    
    if not inventory.get_switch(switch_ip):
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        vlan_id = int(vlan_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'vlan_id must be a valid integer'}), 400
    
    try:
        message = direct_rest_manager.create_vlan(switch_ip, vlan_id, name)
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
    """Delete a VLAN from a specific switch."""
    data = request.json or {}
    switch_ip = data.get('switch_ip')
    vlan_id = int(request.view_args['vlan_id'])
    
    if not switch_ip:
        return jsonify({'error': 'switch_ip is required in request body'}), 400
    
    if not inventory.get_switch(switch_ip):
        return jsonify({'error': f'Switch {switch_ip} not found in inventory'}), 404
    
    try:
        message = switch_manager.delete_vlan(switch_ip, vlan_id)
        logger.info(f"VLAN deletion request: {switch_ip} - VLAN {vlan_id}")
        return jsonify({
            'status': 'success',
            'message': message
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except SwitchConnectionError as e:
        logger.error(f"Connection error for {switch_ip}: {e}")
        return jsonify({'error': str(e)}), 503
    except SwitchOperationError as e:
        logger.error(f"Operation error for {switch_ip}: {e}")
        return jsonify({'error': str(e)}), 403
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