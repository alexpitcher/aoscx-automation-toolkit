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
    SWITCH_PASSWORD = os.getenv('SWITCH_PASSWORD', 'Aruba123!')
    
    # API settings
    API_VERSION = os.getenv('API_VERSION', '10.15')
    SSL_VERIFY = os.getenv('SSL_VERIFY', 'False').lower() == 'true'
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Default switches - now empty to avoid dead connections
    DEFAULT_SWITCHES = []
    
    @classmethod
    def validate(cls) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # SWITCH_PASSWORD is now optional since we have credential fallback
        pass
            
        # Remove validation for DEFAULT_SWITCHES since we no longer require them
            
        return errors