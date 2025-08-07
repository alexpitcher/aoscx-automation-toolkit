"""
Custom exceptions for specific authentication and switch operation failures.
Provides structured error handling with user-friendly messages.
"""

class SwitchConnectionError(Exception):
    """Base class for all switch connection errors."""
    def __init__(self, message: str, error_type: str, suggestion: str = None, switch_ip: str = None):
        super().__init__(message)
        self.error_type = error_type
        self.suggestion = suggestion or ""
        self.switch_ip = switch_ip
        
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON responses."""
        return {
            'error': str(self),
            'error_type': self.error_type,
            'suggestion': self.suggestion,
            'switch_ip': self.switch_ip
        }

class SessionLimitError(SwitchConnectionError):
    """Switch has reached maximum session limit."""
    def __init__(self, switch_ip: str, session_info: str = None):
        message = f"Switch session limit reached for {switch_ip}"
        if session_info:
            message += f": {session_info}"
        suggestion = (
            "Switch has too many active sessions. This typically resolves automatically within "
            "5-10 minutes. You can: 1) Wait for sessions to timeout naturally, "
            "2) Use the 'Clear Sessions' button to attempt cleanup, or "
            "3) Reboot the switch if you have CLI access."
        )
        super().__init__(message, 'session_limit', suggestion, switch_ip)

class InvalidCredentialsError(SwitchConnectionError):
    """Authentication failed due to invalid username/password."""
    def __init__(self, switch_ip: str, username: str, details: str = None):
        message = f"Invalid credentials for user '{username}' on switch {switch_ip}"
        if details:
            message += f": {details}"
        suggestion = (
            "Please check your username and password. Common issues: "
            "1) Verify username (usually 'admin'), "
            "2) Check password for typos, "
            "3) Ensure user has admin privileges, "
            "4) Check if account is locked due to failed attempts."
        )
        super().__init__(message, 'invalid_credentials', suggestion, switch_ip)
        self.username = username

class ConnectionTimeoutError(SwitchConnectionError):
    """Cannot reach switch due to network/connectivity issues."""
    def __init__(self, switch_ip: str, timeout_details: str = None):
        message = f"Cannot reach switch {switch_ip}"
        if timeout_details:
            message += f": {timeout_details}"
        suggestion = (
            "Network connectivity issue. Please check: "
            "1) IP address is correct, "
            "2) Switch is powered on and reachable via ping, "
            "3) No firewall blocking HTTPS (port 443), "
            "4) Switch is on the same network/VLAN."
        )
        super().__init__(message, 'connection_timeout', suggestion, switch_ip)

class PermissionDeniedError(SwitchConnectionError):
    """User authenticated but lacks required permissions."""
    def __init__(self, switch_ip: str, username: str, operation: str = None):
        message = f"User '{username}' lacks required permissions on switch {switch_ip}"
        if operation:
            message += f" for operation: {operation}"
        suggestion = (
            "Authentication succeeded but user lacks admin privileges. "
            "1) Ensure user has admin/manager role, "
            "2) Check user permissions in switch configuration, "
            "3) Some operations require full admin access."
        )
        super().__init__(message, 'permission_denied', suggestion, switch_ip)
        self.username = username

class APIUnavailableError(SwitchConnectionError):
    """Switch REST API is not available or misconfigured."""
    def __init__(self, switch_ip: str, api_details: str = None):
        message = f"REST API unavailable on switch {switch_ip}"
        if api_details:
            message += f": {api_details}"
        suggestion = (
            "Switch REST API is not properly configured. Please check: "
            "1) HTTPS server is enabled, "
            "2) REST API access is enabled, "
            "3) API version v10.09 is supported, "
            "4) HTTPS server mode is set to 'read-write' (not read-only)."
        )
        super().__init__(message, 'api_unavailable', suggestion, switch_ip)

class CentralManagedError(SwitchConnectionError):
    """Switch is managed by Aruba Central, direct API blocked."""
    def __init__(self, switch_ip: str):
        message = f"Switch {switch_ip} is managed by Aruba Central"
        suggestion = (
            "This switch is managed by Aruba Central and blocks direct API access. "
            "1) Use Aruba Central interface for management, "
            "2) Add this as a Central-managed device instead, "
            "3) Disable Central management if local control is needed."
        )
        super().__init__(message, 'central_managed', suggestion, switch_ip)

class VLANOperationError(SwitchConnectionError):
    """VLAN operation failed."""
    def __init__(self, switch_ip: str, operation: str, vlan_id: int = None, details: str = None):
        message = f"VLAN {operation} failed on switch {switch_ip}"
        if vlan_id:
            message += f" for VLAN {vlan_id}"
        if details:
            message += f": {details}"
        suggestion = (
            "VLAN operation failed. Common issues: "
            "1) VLAN ID already exists (for creation), "
            "2) VLAN ID doesn't exist (for modification/deletion), "
            "3) VLAN is in use and cannot be deleted, "
            "4) Switch is in read-only mode or Central-managed."
        )
        super().__init__(message, 'vlan_operation_error', suggestion, switch_ip)
        self.operation = operation
        self.vlan_id = vlan_id

class UnknownSwitchError(SwitchConnectionError):
    """Unexpected error from switch."""
    def __init__(self, switch_ip: str, status_code: int = None, response_text: str = None):
        message = f"Unexpected error from switch {switch_ip}"
        if status_code:
            message += f" (HTTP {status_code})"
        if response_text:
            message += f": {response_text}"
        suggestion = (
            "An unexpected error occurred. This may indicate: "
            "1) Switch firmware issue, "
            "2) Unsupported API version, "
            "3) Switch configuration problem, "
            "4) Network instability. Please check switch logs and try again."
        )
        super().__init__(message, 'unknown_error', suggestion, switch_ip)
        self.status_code = status_code
        self.response_text = response_text