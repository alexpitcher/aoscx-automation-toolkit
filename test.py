#!/usr/bin/env python3
"""
Test script to replicate the exact working curl command in Python
"""
import requests
import urllib3

# Disable SSL warnings like curl -k
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_working_auth():
    """Replicate the exact curl command that worked"""
    
    # Create session like curl with -c cookies.txt
    session = requests.Session()
    session.verify = False  # Like curl -k
    
    # Step 1: Login exactly like the working curl command
    login_url = "https://10.202.0.208/rest/v10.09/login"
    login_data = "username=admin&password=Apitche1switch"
    
    print(f"DEBUG: Login URL: {login_url}")
    print(f"DEBUG: Login data: {login_data}")
    
    login_response = session.post(
        login_url,
        data=login_data,  # Use data= not json=
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )
    
    print(f"DEBUG: Login response status: {login_response.status_code}")
    print(f"DEBUG: Login response headers: {login_response.headers}")
    print(f"DEBUG: Login response cookies: {session.cookies}")
    print(f"DEBUG: Login response body: {login_response.text[:200]}")
    
    if login_response.status_code != 200:
        print(f"ERROR: Login failed with {login_response.status_code}")
        return False
    
    # Step 2: Create VLAN exactly like working curl command
    vlan_url = "https://10.202.0.208/rest/v10.09/system/vlans/997"
    vlan_data = {"name": "TestPython", "admin": "up"}
    
    print(f"\nDEBUG: VLAN URL: {vlan_url}")
    print(f"DEBUG: VLAN data: {vlan_data}")
    print(f"DEBUG: Using session cookies: {session.cookies}")
    
    vlan_response = session.put(
        vlan_url,
        json=vlan_data,  # Use json= like curl -d with JSON
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    
    print(f"DEBUG: VLAN response status: {vlan_response.status_code}")
    print(f"DEBUG: VLAN response headers: {vlan_response.headers}")
    print(f"DEBUG: VLAN response body: {vlan_response.text}")
    
    if vlan_response.status_code in [200, 201]:
        print("SUCCESS: VLAN created successfully!")
        return True
    else:
        print(f"ERROR: VLAN creation failed with {vlan_response.status_code}")
        return False

if __name__ == "__main__":
    test_working_auth()