#!/usr/bin/env python3
"""
Debug script to test different API version endpoints
Run this to figure out which auth endpoints actually work
"""
import requests
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_auth_endpoints():
    """Test different authentication endpoints to find what works"""
    
    switch_ip = "10.202.0.37"  # Your failing switch
    username = "admin"
    password = "Apitche1switch"
    
    # Different API versions to test
    api_versions = [
        "v1",
        "v10.04", 
        "v10.09",
        "v10.15",
        "latest"
    ]
    
    # Different auth paths to test
    auth_paths = [
        "login",
        "login-sessions", 
        "auth",
        "session"
    ]
    
    for api_version in api_versions:
        for auth_path in auth_paths:
            print(f"\n{'='*60}")
            print(f"Testing: https://{switch_ip}/rest/{api_version}/{auth_path}")
            print(f"{'='*60}")
            
            session = requests.Session()
            session.verify = False
            
            # Test form-encoded auth
            auth_url = f"https://{switch_ip}/rest/{api_version}/{auth_path}"
            auth_data = f"username={username}&password={password}"
            
            try:
                response = session.post(
                    auth_url,
                    data=auth_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=10
                )
                
                print(f"Status: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                print(f"Cookies: {dict(session.cookies)}")
                print(f"Body: {response.text[:200]}...")
                
                if response.status_code == 200:
                    print("✅ SUCCESS - This endpoint works!")
                    
                    # Test if we can use this session
                    test_url = f"https://{switch_ip}/rest/{api_version}/system"
                    test_response = session.get(test_url, timeout=10)
                    print(f"System endpoint test: {test_response.status_code}")
                    
                elif response.status_code == 410:
                    print("❌ 410 Gone - Endpoint deprecated/removed")
                elif response.status_code == 404:
                    print("❌ 404 Not Found - Endpoint doesn't exist")
                elif response.status_code == 401:
                    print("⚠️  401 Unauthorized - Endpoint exists but auth failed")
                else:
                    print(f"⚠️  {response.status_code} - Unexpected response")
                    
            except requests.exceptions.RequestException as e:
                print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_auth_endpoints()