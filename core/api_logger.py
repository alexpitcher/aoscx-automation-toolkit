"""
API Call Logger for comprehensive debugging and monitoring.
Tracks all REST API calls with request/response details, timing, and success status.
"""

import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)

class APILogger:
    """Comprehensive API call logger with thread-safe operations."""
    
    def __init__(self, max_history: int = 100):
        self.call_history: List[Dict[str, Any]] = []
        self.max_history = max_history
        self._lock = Lock()
        logger.info(f"APILogger initialized with max_history={max_history}")
    
    def log_api_call(self, 
                     method: str, 
                     url: str, 
                     headers: Dict[str, str], 
                     request_data: Any, 
                     response_code: int, 
                     response_text: str, 
                     duration_ms: float,
                     switch_ip: Optional[str] = None) -> None:
        """Log a complete API call with all details."""
        
        # Extract switch IP from URL if not provided
        if not switch_ip and '://' in url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                switch_ip = parsed.hostname
            except Exception:
                switch_ip = 'unknown'
        
        # Sanitize sensitive data
        sanitized_headers = self._sanitize_headers(headers)
        sanitized_data = self._sanitize_request_data(request_data)
        
        call_entry = {
            'id': len(self.call_history) + 1,
            'timestamp': datetime.now().isoformat(),
            'switch_ip': switch_ip,
            'method': method.upper(),
            'url': url,
            'headers': sanitized_headers,
            'request_data': sanitized_data,
            'response_code': response_code,
            'response_text': self._truncate_response(response_text),
            'response_size': len(response_text) if response_text else 0,
            'duration_ms': round(duration_ms, 2),
            'success': 200 <= response_code < 400,
            'category': self._categorize_call(url, method)
        }
        
        with self._lock:
            self.call_history.append(call_entry)
            if len(self.call_history) > self.max_history:
                self.call_history.pop(0)
        
        # Log to console with appropriate level
        log_level = logging.INFO if call_entry['success'] else logging.WARNING
        logger.log(log_level, 
                  f"API {method} {url} -> {response_code} ({duration_ms:.0f}ms)")
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Remove sensitive information from headers."""
        sanitized = {}
        sensitive_headers = {'authorization', 'cookie', 'set-cookie', 'x-auth-token'}
        
        for key, value in (headers or {}).items():
            if key.lower() in sensitive_headers:
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_request_data(self, data: Any) -> str:
        """Sanitize request data, hiding passwords and secrets."""
        if not data:
            return ""
        
        try:
            if isinstance(data, dict):
                sanitized = {}
                for key, value in data.items():
                    if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'token']):
                        sanitized[key] = '***REDACTED***'
                    else:
                        sanitized[key] = value
                return str(sanitized)
            elif isinstance(data, str):
                # Handle query string parameters with passwords
                if 'password=' in data.lower():
                    import re
                    data = re.sub(r'password=[^&]*', 'password=***REDACTED***', data, flags=re.IGNORECASE)
                return data
            else:
                return str(data)
        except Exception as e:
            logger.debug(f"Error sanitizing request data: {e}")
            return str(data)
    
    def _truncate_response(self, response_text: str, max_length: int = 1000) -> str:
        """Truncate long response text for storage efficiency."""
        if not response_text:
            return ""
        
        if len(response_text) <= max_length:
            return response_text
        
        return response_text[:max_length] + f"...[truncated, full length: {len(response_text)} chars]"
    
    def _categorize_call(self, url: str, method: str) -> str:
        """Categorize API calls for better organization."""
        url_lower = url.lower()
        
        if 'login' in url_lower or 'auth' in url_lower:
            return 'authentication'
        elif 'vlan' in url_lower:
            return 'vlan_management'
        elif 'system' in url_lower:
            return 'system_info'
        elif 'logout' in url_lower:
            return 'session_cleanup'
        elif method.upper() in ['GET']:
            return 'data_retrieval'
        elif method.upper() in ['POST', 'PUT', 'PATCH']:
            return 'configuration'
        elif method.upper() in ['DELETE']:
            return 'deletion'
        else:
            return 'general'
    
    def get_recent_calls(self, limit: int = 20, 
                        switch_ip: Optional[str] = None,
                        category: Optional[str] = None,
                        success_only: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get recent API calls with optional filtering."""
        with self._lock:
            calls = list(self.call_history)
        
        # Apply filters
        if switch_ip:
            calls = [call for call in calls if call.get('switch_ip') == switch_ip]
        
        if category:
            calls = [call for call in calls if call.get('category') == category]
        
        if success_only is not None:
            calls = [call for call in calls if call.get('success') == success_only]
        
        # Return most recent calls first
        return calls[-limit:] if limit else calls
    
    def get_call_statistics(self) -> Dict[str, Any]:
        """Get statistics about API calls."""
        with self._lock:
            calls = list(self.call_history)
        
        if not calls:
            return {
                'total_calls': 0,
                'success_rate': 0,
                'average_duration': 0,
                'categories': {},
                'switches': {}
            }
        
        total_calls = len(calls)
        successful_calls = len([c for c in calls if c['success']])
        success_rate = (successful_calls / total_calls) * 100
        
        # Calculate average duration
        durations = [c['duration_ms'] for c in calls if c['duration_ms']]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Category breakdown
        categories = {}
        for call in calls:
            cat = call.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        # Switch breakdown
        switches = {}
        for call in calls:
            switch = call.get('switch_ip', 'unknown')
            switches[switch] = switches.get(switch, 0) + 1
        
        return {
            'total_calls': total_calls,
            'successful_calls': successful_calls,
            'failed_calls': total_calls - successful_calls,
            'success_rate': round(success_rate, 1),
            'average_duration': round(avg_duration, 2),
            'categories': categories,
            'switches': switches,
            'last_call': calls[-1]['timestamp'] if calls else None
        }
    
    def clear_history(self) -> int:
        """Clear all call history and return number of cleared entries."""
        with self._lock:
            cleared_count = len(self.call_history)
            self.call_history.clear()
        
        logger.info(f"Cleared {cleared_count} API call log entries")
        return cleared_count
    
    def export_logs(self, format: str = 'json') -> str:
        """Export logs in specified format for debugging."""
        with self._lock:
            calls = list(self.call_history)
        
        if format.lower() == 'json':
            import json
            return json.dumps({
                'exported_at': datetime.now().isoformat(),
                'total_calls': len(calls),
                'statistics': self.get_call_statistics(),
                'calls': calls
            }, indent=2)
        elif format.lower() == 'csv':
            import io
            import csv
            
            output = io.StringIO()
            if calls:
                fieldnames = calls[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(calls)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")

# Global API logger instance
api_logger = APILogger()