#!/usr/bin/env python3
"""
Simple authentication test to verify our method works.
"""

import sys
sys.path.append('.')

from core.direct_rest_manager import direct_rest_manager
import json

def test_auth():
    result = direct_rest_manager.test_connection_with_credentials(
        "10.201.1.203", 
        "admin", 
        "Aruba123!"
    )
    print("Authentication test result:")
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    test_auth()