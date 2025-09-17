#!/usr/bin/env python3
"""
Clean up any lingering sessions on the switch.
"""

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def cleanup_sessions():
    """Try to cleanup sessions by waiting or by trying different approaches."""
    switch_ip = "10.201.1.203"
    
    # Method 1: Try to get current sessions info
    try:
        # Try to get session info without authentication
        response = requests.get(f"https://{switch_ip}/rest/v10.09", verify=False, timeout=5)
        print(f"Base endpoint response: {response.status_code}")
    except Exception as e:
        print(f"Base endpoint error: {e}")
    
    # Method 2: Try to force session cleanup by attempting logout on potential session IDs
    # This is not really feasible without knowing session IDs
    
    print("Session cleanup attempted. Please wait 10-15 minutes for sessions to timeout naturally,")
    print("or reboot the switch if you have CLI access.")
    print("\nAlternatively, check switch session limits with:")
    print("- show aaa sessions")
    print("- show https-server sessions")

if __name__ == "__main__":
    cleanup_sessions()