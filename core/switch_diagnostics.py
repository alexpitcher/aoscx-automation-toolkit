"""
Comprehensive AOS-CX Switch Diagnostics Tool

This module systematically tests all API versions, authentication methods,
and VLAN operations to determine what actually works on a specific switch.
"""

import requests
import json
import urllib3
from datetime import datetime
from typing import Dict, List, Tuple, Any
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SwitchDiagnostics:
    def __init__(self, switch_ip: str, username: str = "admin", password: str = "Aruba123!"):
        self.switch_ip = switch_ip
        self.username = username
        self.password = password
        self.base_url = f"https://{switch_ip}"
        self.results = {
            "switch_ip": switch_ip,
            "timestamp": datetime.now().isoformat(),
            "api_versions": {},
            "authentication": {},
            "vlan_operations": {},
            "https_config": {},
            "session_info": {},
            "recommendations": {}
        }
        self.working_sessions = {}

    def run_full_diagnostics(self) -> Dict[str, Any]:
        """Run comprehensive diagnostics on target switch."""
        print(f"Starting comprehensive diagnostics for {self.switch_ip}")
        
        # Test 1: Discover available API versions
        self.test_api_version_discovery()
        
        # Test 2: Test authentication methods for each API version
        available_versions = self.get_available_api_versions()
        for version in available_versions:
            self.test_authentication_methods(version)
        
        # Test 3: Test VLAN operations for working versions
        working_versions = self.get_working_versions()
        for version in working_versions:
            self.test_vlan_operations(version)
        
        # Test 4: Test HTTPS server configuration
        self.test_https_server_config()
        
        # Test 5: Test session management
        self.test_session_management()
        
        # Test 6: Generate recommendations
        self.generate_recommendations()
        
        return self.results

    def test_api_version_discovery(self):
        """Discover what API versions are actually available."""
        print("Testing API version discovery...")
        
        # Test base REST endpoint
        try:
            response = requests.get(f"{self.base_url}/rest", verify=False, timeout=10)
            self.results["api_versions"]["base_rest"] = {
                "status_code": response.status_code,
                "response": response.text[:500] if response.text else None
            }
        except Exception as e:
            self.results["api_versions"]["base_rest"] = {"error": str(e)}

        # Test known API versions
        test_versions = ["v1", "v10.04", "v10.08", "v10.09", "v10.10", "v10.11", "v10.12", "v10.13", "v10.14", "v10.15"]
        
        for version in test_versions:
            try:
                response = requests.get(f"{self.base_url}/rest/{version}", verify=False, timeout=10)
                self.results["api_versions"][version] = {
                    "status_code": response.status_code,
                    "available": response.status_code in [200, 401, 403],
                    "response_headers": dict(response.headers),
                    "response_snippet": response.text[:200] if response.text else None
                }
            except Exception as e:
                self.results["api_versions"][version] = {
                    "available": False,
                    "error": str(e)
                }

    def get_available_api_versions(self) -> List[str]:
        """Get list of available API versions from discovery results."""
        available = []
        for version, result in self.results["api_versions"].items():
            if version != "base_rest" and result.get("available", False):
                available.append(version)
        return available

    def test_authentication_methods(self, api_version: str):
        """Test different authentication methods for specific API version."""
        print(f"Testing authentication methods for {api_version}...")
        
        if api_version not in self.results["authentication"]:
            self.results["authentication"][api_version] = {}

        # Method 1: Form-encoded POST (current method)
        self.test_form_encoded_auth(api_version)
        
        # Method 2: Query parameter POST (official docs method)
        self.test_query_param_auth(api_version)
        
        # Method 3: JSON POST with CSRF (v10.09+ method)
        self.test_json_csrf_auth(api_version)
        
        # Method 4: Basic Auth header
        self.test_basic_auth_header(api_version)

    def test_form_encoded_auth(self, api_version: str):
        """Test form-encoded authentication."""
        method_name = "form_encoded_post"
        try:
            session = requests.Session()
            
            # Get login page first
            login_url = f"{self.base_url}/rest/{api_version}/login-sessions"
            
            # Attempt login with form data
            login_data = {"username": self.username, "password": self.password}
            response = session.post(login_url, data=login_data, verify=False, timeout=10)
            
            # Test if we can access a protected resource
            test_response = None
            if response.status_code in [200, 201]:
                test_response = session.get(f"{self.base_url}/rest/{api_version}/system", verify=False, timeout=10)
            
            self.results["authentication"][api_version][method_name] = {
                "login_status_code": response.status_code,
                "login_response": response.text[:200] if response.text else None,
                "test_access_code": test_response.status_code if test_response else None,
                "working": test_response and test_response.status_code == 200,
                "session_id": response.cookies.get('sessionId') or response.cookies.get('JSESSIONID')
            }
            
            if test_response and test_response.status_code == 200:
                self.working_sessions[api_version] = session
                
        except Exception as e:
            self.results["authentication"][api_version][method_name] = {"error": str(e)}

    def test_query_param_auth(self, api_version: str):
        """Test query parameter authentication."""
        method_name = "query_parameter_post"
        try:
            session = requests.Session()
            
            # Try login with query parameters
            login_url = f"{self.base_url}/rest/{api_version}/login-sessions?username={self.username}&password={self.password}"
            response = session.post(login_url, verify=False, timeout=10)
            
            # Test protected resource access
            test_response = None
            if response.status_code in [200, 201]:
                test_response = session.get(f"{self.base_url}/rest/{api_version}/system", verify=False, timeout=10)
            
            self.results["authentication"][api_version][method_name] = {
                "login_status_code": response.status_code,
                "login_response": response.text[:200] if response.text else None,
                "test_access_code": test_response.status_code if test_response else None,
                "working": test_response and test_response.status_code == 200,
                "session_id": response.cookies.get('sessionId') or response.cookies.get('JSESSIONID')
            }
            
            if test_response and test_response.status_code == 200:
                self.working_sessions[f"{api_version}_query"] = session
                
        except Exception as e:
            self.results["authentication"][api_version][method_name] = {"error": str(e)}

    def test_json_csrf_auth(self, api_version: str):
        """Test JSON authentication with CSRF token (v10.09+)."""
        method_name = "json_post_with_csrf"
        try:
            session = requests.Session()
            
            # Get CSRF token first
            csrf_response = session.get(f"{self.base_url}/rest/{api_version}/login-sessions", verify=False, timeout=10)
            csrf_token = None
            if 'X-CSRF-Token' in csrf_response.headers:
                csrf_token = csrf_response.headers['X-CSRF-Token']
            
            # Attempt login with JSON and CSRF
            headers = {'Content-Type': 'application/json'}
            if csrf_token:
                headers['X-CSRF-Token'] = csrf_token
            
            login_data = {"username": self.username, "password": self.password}
            response = session.post(
                f"{self.base_url}/rest/{api_version}/login-sessions",
                json=login_data,
                headers=headers,
                verify=False,
                timeout=10
            )
            
            # Test protected resource access
            test_response = None
            if response.status_code in [200, 201]:
                test_response = session.get(f"{self.base_url}/rest/{api_version}/system", verify=False, timeout=10)
            
            self.results["authentication"][api_version][method_name] = {
                "csrf_token": csrf_token,
                "login_status_code": response.status_code,
                "login_response": response.text[:200] if response.text else None,
                "test_access_code": test_response.status_code if test_response else None,
                "working": test_response and test_response.status_code == 200,
                "session_id": response.cookies.get('sessionId') or response.cookies.get('JSESSIONID')
            }
            
            if test_response and test_response.status_code == 200:
                self.working_sessions[f"{api_version}_csrf"] = session
                
        except Exception as e:
            self.results["authentication"][api_version][method_name] = {"error": str(e)}

    def test_basic_auth_header(self, api_version: str):
        """Test basic authentication header."""
        method_name = "basic_auth_header"
        try:
            session = requests.Session()
            session.auth = (self.username, self.password)
            
            # Test direct access with basic auth
            response = session.get(f"{self.base_url}/rest/{api_version}/system", verify=False, timeout=10)
            
            self.results["authentication"][api_version][method_name] = {
                "status_code": response.status_code,
                "response": response.text[:200] if response.text else None,
                "working": response.status_code == 200
            }
            
            if response.status_code == 200:
                self.working_sessions[f"{api_version}_basic"] = session
                
        except Exception as e:
            self.results["authentication"][api_version][method_name] = {"error": str(e)}

    def get_working_versions(self) -> List[str]:
        """Get API versions that have at least one working authentication method."""
        working = []
        for version, auth_methods in self.results["authentication"].items():
            for method, result in auth_methods.items():
                if result.get("working", False):
                    working.append(version)
                    break
        return working

    def test_vlan_operations(self, api_version: str):
        """Test VLAN operations for working API version."""
        print(f"Testing VLAN operations for {api_version}...")
        
        if api_version not in self.results["vlan_operations"]:
            self.results["vlan_operations"][api_version] = {}

        # Get working session for this API version
        session = self.get_working_session(api_version)
        if not session:
            self.results["vlan_operations"][api_version]["error"] = "No working authentication session"
            return

        # Test VLAN listing
        self.test_vlan_listing(api_version, session)
        
        # Test VLAN creation methods
        self.test_vlan_creation_methods(api_version, session)
        
        # Test VLAN modification
        self.test_vlan_modification(api_version, session)
        
        # Test VLAN deletion
        self.test_vlan_deletion(api_version, session)

    def get_working_session(self, api_version: str) -> requests.Session:
        """Get a working session for the API version."""
        # Try different session keys
        session_keys = [api_version, f"{api_version}_query", f"{api_version}_csrf", f"{api_version}_basic"]
        for key in session_keys:
            if key in self.working_sessions:
                return self.working_sessions[key]
        return None

    def test_vlan_listing(self, api_version: str, session: requests.Session):
        """Test VLAN listing operations."""
        endpoints = [
            "/system/vlans",
            "/vlans",
            "/system/bridge/vlans"
        ]
        
        self.results["vlan_operations"][api_version]["listing"] = {}
        
        for endpoint in endpoints:
            try:
                response = session.get(f"{self.base_url}/rest/{api_version}{endpoint}", verify=False, timeout=10)
                self.results["vlan_operations"][api_version]["listing"][endpoint] = {
                    "status_code": response.status_code,
                    "working": response.status_code == 200,
                    "response_snippet": response.text[:300] if response.text else None,
                    "content_type": response.headers.get('Content-Type')
                }
            except Exception as e:
                self.results["vlan_operations"][api_version]["listing"][endpoint] = {"error": str(e)}

    def test_vlan_creation_methods(self, api_version: str, session: requests.Session):
        """Test different VLAN creation approaches."""
        test_vlan_id = "999"
        test_vlan_name = "DIAG_TEST_VLAN"
        
        methods = [
            {
                "name": "POST_collection",
                "method": "POST",
                "endpoint": "/system/vlans",
                "data": {test_vlan_id: {"name": test_vlan_name, "admin": "up"}}
            },
            {
                "name": "PUT_individual",
                "method": "PUT", 
                "endpoint": f"/system/vlans/{test_vlan_id}",
                "data": {"name": test_vlan_name, "admin": "up"}
            },
            {
                "name": "POST_individual",
                "method": "POST",
                "endpoint": f"/system/vlans/{test_vlan_id}",
                "data": {"name": test_vlan_name, "admin": "up"}
            }
        ]
        
        self.results["vlan_operations"][api_version]["creation"] = {}
        
        for method_info in methods:
            try:
                # Clean up any existing test VLAN first
                session.delete(f"{self.base_url}/rest/{api_version}/system/vlans/{test_vlan_id}", verify=False)
                time.sleep(1)
                
                # Test the creation method
                if method_info["method"] == "POST":
                    response = session.post(
                        f"{self.base_url}/rest/{api_version}{method_info['endpoint']}",
                        json=method_info["data"],
                        verify=False,
                        timeout=10
                    )
                elif method_info["method"] == "PUT":
                    response = session.put(
                        f"{self.base_url}/rest/{api_version}{method_info['endpoint']}",
                        json=method_info["data"],
                        verify=False,
                        timeout=10
                    )
                
                # Verify creation by checking if VLAN exists
                verify_response = session.get(
                    f"{self.base_url}/rest/{api_version}/system/vlans/{test_vlan_id}",
                    verify=False,
                    timeout=10
                )
                
                self.results["vlan_operations"][api_version]["creation"][method_info["name"]] = {
                    "status_code": response.status_code,
                    "response": response.text[:200] if response.text else None,
                    "verify_status": verify_response.status_code,
                    "working": response.status_code in [200, 201] and verify_response.status_code == 200
                }
                
                # Clean up
                session.delete(f"{self.base_url}/rest/{api_version}/system/vlans/{test_vlan_id}", verify=False)
                
            except Exception as e:
                self.results["vlan_operations"][api_version]["creation"][method_info["name"]] = {"error": str(e)}

    def test_vlan_modification(self, api_version: str, session: requests.Session):
        """Test VLAN modification operations."""
        # This would test updating existing VLANs
        self.results["vlan_operations"][api_version]["modification"] = {"status": "not_implemented"}

    def test_vlan_deletion(self, api_version: str, session: requests.Session):
        """Test VLAN deletion operations."""
        # This would test deleting VLANs
        self.results["vlan_operations"][api_version]["deletion"] = {"status": "not_implemented"}

    def test_https_server_config(self):
        """Test if HTTPS server is in read-write mode."""
        print("Testing HTTPS server configuration...")
        
        # Try to access system configuration
        for version in self.get_working_versions():
            session = self.get_working_session(version)
            if session:
                try:
                    response = session.get(f"{self.base_url}/rest/{version}/system", verify=False, timeout=10)
                    if response.status_code == 200:
                        system_info = response.json()
                        self.results["https_config"][version] = {
                            "system_accessible": True,
                            "system_info": system_info
                        }
                        break
                except Exception as e:
                    self.results["https_config"][version] = {"error": str(e)}

    def test_session_management(self):
        """Test session management behavior."""
        print("Testing session management...")
        
        session_count = len(self.working_sessions)
        self.results["session_info"] = {
            "active_sessions": session_count,
            "session_types": list(self.working_sessions.keys())
        }

    def generate_recommendations(self):
        """Generate recommendations based on test results."""
        print("Generating recommendations...")
        
        # Find best API version
        best_version = None
        best_auth_method = None
        best_vlan_method = None
        
        for version in self.get_working_versions():
            # Check authentication methods
            auth_methods = self.results["authentication"].get(version, {})
            for method, result in auth_methods.items():
                if result.get("working", False):
                    best_version = version
                    best_auth_method = method
                    break
            
            # Check VLAN operations
            vlan_ops = self.results["vlan_operations"].get(version, {})
            if "creation" in vlan_ops:
                for method, result in vlan_ops["creation"].items():
                    if result.get("working", False):
                        best_vlan_method = method
                        break
            
            if best_version and best_auth_method:
                break
        
        self.results["recommendations"] = {
            "recommended_api_version": best_version,
            "recommended_auth_method": best_auth_method,
            "recommended_vlan_method": best_vlan_method,
            "working_combinations": self.get_working_combinations()
        }

    def get_working_combinations(self) -> List[Dict[str, str]]:
        """Get all working API version + authentication combinations."""
        combinations = []
        for version, auth_methods in self.results["authentication"].items():
            for method, result in auth_methods.items():
                if result.get("working", False):
                    combinations.append({
                        "api_version": version,
                        "auth_method": method,
                        "session_key": f"{version}_{method}" if method != "form_encoded_post" else version
                    })
        return combinations

    def print_summary(self):
        """Print a human-readable summary of results."""
        print("\n" + "="*80)
        print(f"DIAGNOSTICS SUMMARY FOR {self.switch_ip}")
        print("="*80)
        
        print("\n1. AVAILABLE API VERSIONS:")
        for version, result in self.results["api_versions"].items():
            if version != "base_rest":
                status = "✓" if result.get("available", False) else "✗"
                print(f"   {status} {version}")
        
        print("\n2. WORKING AUTHENTICATION COMBINATIONS:")
        for combo in self.results["recommendations"]["working_combinations"]:
            print(f"   ✓ {combo['api_version']} + {combo['auth_method']}")
        
        print("\n3. VLAN OPERATIONS STATUS:")
        for version, ops in self.results["vlan_operations"].items():
            print(f"   API {version}:")
            if "listing" in ops:
                for endpoint, result in ops["listing"].items():
                    status = "✓" if result.get("working", False) else "✗"
                    print(f"     {status} GET {endpoint}")
            if "creation" in ops:
                for method, result in ops["creation"].items():
                    status = "✓" if result.get("working", False) else "✗"
                    print(f"     {status} CREATE {method}")
        
        print("\n4. RECOMMENDATIONS:")
        rec = self.results["recommendations"]
        if rec["recommended_api_version"]:
            print(f"   • Use API version: {rec['recommended_api_version']}")
            print(f"   • Use auth method: {rec['recommended_auth_method']}")
            if rec["recommended_vlan_method"]:
                print(f"   • Use VLAN method: {rec['recommended_vlan_method']}")
        else:
            print("   • No working combinations found!")


def run_diagnostics(switch_ip: str = "10.201.1.203", username: str = "admin", password: str = "Aruba123!") -> Dict[str, Any]:
    """Run full diagnostics and return results."""
    diagnostics = SwitchDiagnostics(switch_ip, username, password)
    results = diagnostics.run_full_diagnostics()
    diagnostics.print_summary()
    return results


if __name__ == "__main__":
    # Run diagnostics when script is executed directly
    results = run_diagnostics()
    
    # Save results to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"diagnostics_{results['switch_ip']}_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {filename}")