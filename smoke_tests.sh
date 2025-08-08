#!/bin/bash
# Smoke tests for AOS-CX Automation Toolkit API endpoints
# Tests all GET and PATCH endpoints with curl and jq validation

set -e  # Exit on any error

BASE_URL="http://localhost:5001"
SWITCH_IP="10.201.1.203"

echo "=== AOS-CX API Smoke Tests ==="
echo "Base URL: $BASE_URL"
echo "Test Switch: $SWITCH_IP"
echo

# Function to test endpoint and validate JSON response
test_endpoint() {
    local method=$1
    local endpoint=$2
    local expected_fields=$3
    local data=${4:-""}
    
    echo "Testing: $method $endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s "$BASE_URL$endpoint")
    elif [ "$method" = "POST" ]; then
        response=$(curl -s -X POST -H "Content-Type: application/json" -d "$data" "$BASE_URL$endpoint")
    elif [ "$method" = "PATCH" ]; then
        response=$(curl -s -X PATCH -H "Content-Type: application/json" -d "$data" "$BASE_URL$endpoint")
    fi
    
    # Check if response is valid JSON
    if ! echo "$response" | jq . >/dev/null 2>&1; then
        echo "  ❌ Invalid JSON response"
        echo "  Response: $response"
        return 1
    fi
    
    # Check for error field
    if echo "$response" | jq -e '.error' >/dev/null 2>&1; then
        echo "  ⚠️  API Error: $(echo "$response" | jq -r '.error')"
        return 1
    fi
    
    # Validate expected fields if provided
    if [ -n "$expected_fields" ]; then
        for field in $expected_fields; do
            if ! echo "$response" | jq -e ".$field" >/dev/null 2>&1; then
                echo "  ❌ Missing expected field: $field"
                return 1
            fi
        done
    fi
    
    echo "  ✅ Success"
    echo "  Response: $(echo "$response" | jq -c . | cut -c1-100)..."
    return 0
}

echo "1. Testing Switch Inventory Endpoints"
echo "-----------------------------------"
test_endpoint "GET" "/api/switches" "switches count"

echo
echo "2. Testing Switch Overview Endpoint"
echo "----------------------------------"
test_endpoint "GET" "/api/switches/$SWITCH_IP/overview" "model hostname firmware_version port_count poe_status power_status fan_status cpu_usage"

echo
echo "3. Testing VLANs Endpoints"
echo "-------------------------"
test_endpoint "GET" "/api/switches/$SWITCH_IP/vlans" "vlans total_count"

echo
echo "4. Testing Interfaces Endpoints" 
echo "-------------------------------"
test_endpoint "GET" "/api/switches/$SWITCH_IP/interfaces" "interfaces total_count"

echo
echo "5. Testing PATCH Endpoints - SKIPPED (read-only mode)"
echo "---------------------------------------------------"
echo "Skipping PATCH tests to avoid making configuration changes to the switch"

echo
echo "6. Testing API Logs Endpoint"
echo "----------------------------"
test_endpoint "GET" "/api/logs/calls" "calls statistics"

echo
echo "=== All Tests Complete ==="
echo "Check above for any ❌ failures or ⚠️ warnings"