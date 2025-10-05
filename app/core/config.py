"""
Configuration settings for WOLManager
"""

from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    
    # Redis settings
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    
    # Discovery settings
    DISCOVERY_INTERVAL: int = 300  # seconds
    NETWORK_RANGE: str = "192.168.1.0/24"
    DISCOVERY_EARLY_TERMINATION: bool = True  # Stop discovery when high-priority methods succeed
    DISCOVERY_MIN_HOSTS_THRESHOLD: int = 5  # Minimum hosts to trigger early termination
    
    # RouterOS settings
    ROUTEROS_HOST: Optional[str] = None
    ROUTEROS_USERNAME: Optional[str] = None
    ROUTEROS_PASSWORD: Optional[str] = None
    ROUTEROS_PORT: int = 8728
    
    # SNMP settings
    SNMP_COMMUNITY: str = "public"
    SNMP_TIMEOUT: int = 5
    
    # WOL settings
    WOL_BROADCAST_ADDRESS: str = "192.168.1.255"
    WOL_PORT: int = 9
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


