"""
Base class for discovery methods
"""

from abc import ABC, abstractmethod
from typing import List
import ipaddress
from app.models.host import Host, DiscoveryMethod


class BaseDiscoveryMethod(ABC):
    """Base class for all discovery methods"""
    
    def __init__(self, method: DiscoveryMethod):
        self.method = method
    
    @abstractmethod
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts in the given network range"""
        pass
    
    def _create_host(self, ip_address: str, **kwargs) -> Host:
        """Create a Host object with the discovery method set"""
        return Host(
            ip_address=ip_address,
            discovery_method=self.method,
            **kwargs
        )


