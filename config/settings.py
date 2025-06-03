"""
Application configuration and settings management.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration from environment variables."""
    
    # Switch credentials
    SWITCH_USER = os.getenv('SWITCH_USER', 'admin')
    SWITCH_PASSWORD = os.getenv('SWITCH_PASSWORD', '')
    
    # API settings
    API_VERSION = os.getenv('API_VERSION', '10.15')
    SSL_VERIFY = os.getenv('SSL_VERIFY', 'False').lower() == 'true'
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Default switches
    DEFAULT_SWITCHES = os.getenv('DEFAULT_SWITCHES', '').split(',')
    DEFAULT_SWITCHES = [ip.strip() for ip in DEFAULT_SWITCHES if ip.strip()]
    
    @classmethod
    def validate(cls) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        if not cls.SWITCH_PASSWORD:
            errors.append("SWITCH_PASSWORD is required")
            
        if not cls.DEFAULT_SWITCHES:
            errors.append("DEFAULT_SWITCHES must contain at least one IP address")
            
        return errors