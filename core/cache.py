"""
Simple TTL (Time-To-Live) cache for switch API data.

Provides a lightweight in-memory cache with automatic expiration
to reduce API calls to switches and improve performance.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable


class TTLCache:
    """Thread-safe TTL cache with automatic expiration."""
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize TTL cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
        """
        self.default_ttl = default_ttl
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists and not expired, None otherwise
        """
        with self.lock:
            if key not in self.cache:
                return None
                
            entry = self.cache[key]
            if time.time() > entry['expires_at']:
                # Entry expired, remove it
                del self.cache[key]
                return None
                
            return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        if ttl is None:
            ttl = self.default_ttl
            
        with self.lock:
            self.cache[key] = {
                'value': value,
                'expires_at': time.time() + ttl,
                'created_at': time.time()
            }
    
    def get_or_set(self, key: str, fetch_fn: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Get cached value or fetch and cache if not available.
        
        Args:
            key: Cache key
            fetch_fn: Function to call if cache miss
            ttl: Time-to-live in seconds (uses default if None)
            
        Returns:
            Cached or freshly fetched value
        """
        # Try to get from cache first
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value
            
        # Cache miss - fetch and store
        fresh_value = fetch_fn()
        self.set(key, fresh_value, ttl)
        return fresh_value
    
    def invalidate(self, key: str) -> None:
        """
        Remove specific key from cache.
        
        Args:
            key: Cache key to remove
        """
        with self.lock:
            self.cache.pop(key, None)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Remove all keys matching pattern.
        
        Args:
            pattern: Pattern to match (simple substring match)
            
        Returns:
            Number of keys removed
        """
        removed_count = 0
        with self.lock:
            keys_to_remove = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.cache[key]
                removed_count += 1
        return removed_count
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self.lock:
            self.cache.clear()
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self.lock:
            current_time = time.time()
            total_entries = len(self.cache)
            expired_entries = sum(1 for entry in self.cache.values() 
                                if current_time > entry['expires_at'])
            
            return {
                'total_entries': total_entries,
                'active_entries': total_entries - expired_entries,
                'expired_entries': expired_entries,
                'cache_hit_ratio': getattr(self, '_hit_ratio', 0.0)
            }
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of expired entries removed
        """
        removed_count = 0
        current_time = time.time()
        
        with self.lock:
            keys_to_remove = [
                key for key, entry in self.cache.items()
                if current_time > entry['expires_at']
            ]
            for key in keys_to_remove:
                del self.cache[key]
                removed_count += 1
                
        return removed_count


# Global cache instances for different data types
switch_cache = TTLCache(default_ttl=300)  # 5 minutes
interface_cache = TTLCache(default_ttl=300)  # 5 minutes  
vlan_cache = TTLCache(default_ttl=300)  # 5 minutes


def get_cached_or_fetch(cache: TTLCache, switch_ip: str, cache_key: str, 
                       fetch_fn: Callable[[], Any], ttl: Optional[int] = None) -> Any:
    """
    Helper function to get cached data or fetch fresh data.
    
    Args:
        cache: TTL cache instance to use
        switch_ip: Switch IP address
        cache_key: Key for this specific data type
        fetch_fn: Function to fetch fresh data
        ttl: Optional TTL override
        
    Returns:
        Cached or fresh data
    """
    full_key = f"{switch_ip}:{cache_key}"
    return cache.get_or_set(full_key, fetch_fn, ttl)


def invalidate_switch_cache(switch_ip: str) -> None:
    """
    Invalidate all cached data for a specific switch.
    
    Args:
        switch_ip: Switch IP address
    """
    pattern = f"{switch_ip}:"
    switch_cache.invalidate_pattern(pattern)
    interface_cache.invalidate_pattern(pattern)
    vlan_cache.invalidate_pattern(pattern)