"""
Input validation and safety checks for network operations.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Raised when validation fails."""
    pass

class NetworkValidator:
    """Validates network configuration inputs and operations."""
    
    # Reserved VLANs that should not be modified
    RESERVED_VLANS = {1}  # Default VLAN
    
    # Valid VLAN ID range
    MIN_VLAN_ID = 1
    MAX_VLAN_ID = 4094
    
    # Valid VLAN name pattern (alphanumeric, dashes, underscores)
    VLAN_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,32}$')
    
    # IP address pattern
    IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    
    @classmethod
    def validate_ip_address(cls, ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate IP address format.
        Returns (is_valid, error_message).
        """
        if not ip_address or not isinstance(ip_address, str):
            return False, "IP address must be a non-empty string"
        
        ip_address = ip_address.strip()
        
        if not cls.IP_PATTERN.match(ip_address):
            return False, "IP address must be in format x.x.x.x"
        
        # Check each octet is in valid range
        try:
            octets = ip_address.split('.')
            for octet in octets:
                num = int(octet)
                if num < 0 or num > 255:
                    return False, f"IP address octet {num} is out of range (0-255)"
        except ValueError:
            return False, "IP address contains invalid characters"
        
        # Check for reserved/special addresses
        if ip_address.startswith('0.') or ip_address.startswith('255.'):
            return False, "IP address appears to be reserved"
            
        return True, None
    
    @classmethod
    def validate_vlan_id(cls, vlan_id: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate VLAN ID.
        Returns (is_valid, error_message).
        """
        try:
            vlan_id = int(vlan_id)
        except (ValueError, TypeError):
            return False, "VLAN ID must be a valid integer"
        
        if vlan_id < cls.MIN_VLAN_ID or vlan_id > cls.MAX_VLAN_ID:
            return False, f"VLAN ID must be between {cls.MIN_VLAN_ID} and {cls.MAX_VLAN_ID}"
        
        if vlan_id in cls.RESERVED_VLANS:
            return False, f"VLAN ID {vlan_id} is reserved and cannot be modified"
        
        return True, None
    
    @classmethod
    def validate_vlan_name(cls, vlan_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate VLAN name.
        Returns (is_valid, error_message).
        """
        if not vlan_name or not isinstance(vlan_name, str):
            return False, "VLAN name must be a non-empty string"
        
        vlan_name = vlan_name.strip()
        
        if not vlan_name:
            return False, "VLAN name cannot be empty or just whitespace"
        
        if len(vlan_name) > 32:
            return False, "VLAN name cannot exceed 32 characters"
        
        if not cls.VLAN_NAME_PATTERN.match(vlan_name):
            return False, "VLAN name can only contain letters, numbers, dashes, and underscores"
        
        # Check for reserved names
        reserved_names = {'default', 'management', 'native'}
        if vlan_name.lower() in reserved_names:
            return False, f"VLAN name '{vlan_name}' is reserved"
        
        return True, None
    
    @classmethod
    def validate_vlan_operation(cls, operation: str, vlan_id: Any, vlan_name: str = None) -> List[str]:
        """
        Validate a complete VLAN operation.
        Returns list of error messages (empty if valid).
        """
        errors = []
        
        # Validate operation type
        valid_operations = {'create', 'delete', 'modify'}
        if operation not in valid_operations:
            errors.append(f"Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}")
        
        # Validate VLAN ID
        is_valid, error = cls.validate_vlan_id(vlan_id)
        if not is_valid:
            errors.append(error)
        
        # Validate VLAN name for create/modify operations
        if operation in {'create', 'modify'} and vlan_name is not None:
            is_valid, error = cls.validate_vlan_name(vlan_name)
            if not is_valid:
                errors.append(error)
        
        # Special validation for delete operations
        if operation == 'delete':
            try:
                vlan_id_int = int(vlan_id)
                if vlan_id_int in cls.RESERVED_VLANS:
                    errors.append(f"Cannot delete reserved VLAN {vlan_id_int}")
            except (ValueError, TypeError):
                pass  # VLAN ID validation will catch this
        
        return errors
    
    @classmethod
    def validate_bulk_operation(cls, operations: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Validate a bulk operation request.
        Returns dict mapping operation index to list of errors.
        """
        all_errors = {}
        vlan_ids_in_batch = set()
        
        for i, operation in enumerate(operations):
            errors = []
            
            # Check required fields
            if 'operation' not in operation:
                errors.append("Missing 'operation' field")
            if 'vlan_id' not in operation:
                errors.append("Missing 'vlan_id' field")
            
            if errors:
                all_errors[str(i)] = errors
                continue
            
            # Validate individual operation
            op_errors = cls.validate_vlan_operation(
                operation['operation'],
                operation['vlan_id'],
                operation.get('vlan_name')
            )
            
            # Check for duplicate VLAN IDs in same batch
            try:
                vlan_id = int(operation['vlan_id'])
                if vlan_id in vlan_ids_in_batch:
                    op_errors.append(f"Duplicate VLAN ID {vlan_id} in batch operation")
                else:
                    vlan_ids_in_batch.add(vlan_id)
            except (ValueError, TypeError):
                pass  # Individual validation will catch this
            
            if op_errors:
                all_errors[str(i)] = op_errors
        
        return all_errors
    
    @classmethod
    def sanitize_input(cls, input_value: str, max_length: int = 255) -> str:
        """
        Sanitize string input by removing potentially dangerous characters.
        """
        if not isinstance(input_value, str):
            return str(input_value)
        
        # Remove control characters and limit length
        sanitized = ''.join(char for char in input_value if ord(char) >= 32)
        return sanitized[:max_length].strip()
    
    @classmethod
    def is_safe_operation(cls, switch_ip: str, operation: str, **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Determine if an operation is safe to perform in production.
        Returns (is_safe, warning_message).
        """
        warnings = []
        
        # Check for production IP ranges (common production subnets)
        production_prefixes = ['10.', '172.', '192.168.']
        if any(switch_ip.startswith(prefix) for prefix in production_prefixes):
            warnings.append(f"Operating on production network ({switch_ip})")
        
        # Check for potentially disruptive operations
        if operation == 'delete' and 'vlan_id' in kwargs:
            try:
                vlan_id = int(kwargs['vlan_id'])
                if vlan_id <= 10:  # Low-numbered VLANs often critical
                    warnings.append(f"Deleting low-numbered VLAN {vlan_id} (may be critical)")
            except (ValueError, TypeError):
                pass
        
        # Bulk operations are inherently riskier
        if operation.startswith('bulk_'):
            warnings.append("Bulk operation affects multiple configurations")
        
        # Return safety assessment
        is_safe = len(warnings) == 0
        warning_msg = '; '.join(warnings) if warnings else None
        
        return is_safe, warning_msg

# Global validator instance
validator = NetworkValidator()