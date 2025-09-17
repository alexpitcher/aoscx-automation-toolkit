#!/usr/bin/env python3
"""
Test the fixed DirectRestManager implementation against 10.201.1.203
"""

import sys
sys.path.append('.')

from core.direct_rest_manager import direct_rest_manager
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_fixed_implementation():
    """Test the fixed implementation with confirmed working methods."""
    switch_ip = "10.201.1.203"
    test_vlans = [995, 996, 997, 998, 999]
    
    print(f"\n{'='*80}")
    print(f"TESTING FIXED IMPLEMENTATION AGAINST {switch_ip}")
    print(f"{'='*80}")
    
    # Test 1: Connection test
    print("\n1. Testing connection...")
    try:
        result = direct_rest_manager.test_connection_with_credentials(switch_ip, "admin", "Aruba123!")
        print(f"   Status: {result['status']}")
        print(f"   Firmware: {result.get('firmware_version', 'N/A')}")
        print(f"   Model: {result.get('model', 'N/A')}")
        print(f"   API Version: {result.get('api_version', 'N/A')}")
        if result['status'] != 'online':
            print(f"   Error: {result.get('error_message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"   Connection test failed: {e}")
        return False
    
    # Test 2: VLAN listing
    print("\n2. Testing VLAN listing...")
    try:
        vlans = direct_rest_manager.list_vlans(switch_ip, load_details=True)
        print(f"   Found {len(vlans)} VLANs")
        # Show first few VLANs
        for vlan in vlans[:5]:
            print(f"   VLAN {vlan['id']}: {vlan['name']} (admin: {vlan['admin_state']})")
        if len(vlans) > 5:
            print(f"   ... and {len(vlans) - 5} more")
    except Exception as e:
        print(f"   VLAN listing failed: {e}")
        return False
    
    # Test 3: VLAN creation
    print("\n3. Testing VLAN creation...")
    created_vlans = []
    for vlan_id in test_vlans:
        try:
            result = direct_rest_manager.create_vlan(switch_ip, vlan_id, f"TEST_VLAN_{vlan_id}")
            print(f"   ✓ VLAN {vlan_id}: {result}")
            created_vlans.append(vlan_id)
        except Exception as e:
            print(f"   ✗ VLAN {vlan_id}: Failed - {e}")
    
    # Test 4: Verify created VLANs appear in listing
    print("\n4. Verifying created VLANs...")
    try:
        vlans = direct_rest_manager.list_vlans(switch_ip, load_details=True)
        created_vlan_dict = {v['id']: v for v in vlans}
        
        for vlan_id in created_vlans:
            if vlan_id in created_vlan_dict:
                vlan = created_vlan_dict[vlan_id]
                print(f"   ✓ VLAN {vlan_id}: {vlan['name']} (verified in listing)")
            else:
                print(f"   ✗ VLAN {vlan_id}: Not found in listing")
    except Exception as e:
        print(f"   Verification failed: {e}")
    
    # Test 5: Clean up test VLANs
    print("\n5. Cleaning up test VLANs...")
    for vlan_id in created_vlans:
        try:
            result = direct_rest_manager.delete_vlan(switch_ip, vlan_id)
            print(f"   ✓ VLAN {vlan_id}: {result}")
        except Exception as e:
            print(f"   ✗ VLAN {vlan_id}: Delete failed - {e}")
    
    # Clean up sessions
    direct_rest_manager.cleanup_all_sessions()
    
    print(f"\n{'='*80}")
    print("TESTING COMPLETE")
    print(f"{'='*80}")
    
    return True

if __name__ == "__main__":
    test_fixed_implementation()