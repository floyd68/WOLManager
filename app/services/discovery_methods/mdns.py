"""
mDNS/zeroconf discovery method
"""

import ipaddress
from typing import List
import structlog
import asyncio

from app.models.host import Host, DiscoveryMethod
from app.services.discovery_methods.base import BaseDiscoveryMethod

logger = structlog.get_logger(__name__)


class mDNSDiscovery(BaseDiscoveryMethod):
    """mDNS/zeroconf-based service discovery"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.MDNS)
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using mDNS/zeroconf"""
        hosts = []
        
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
            from zeroconf._protocol import RecordUpdateListener
            
            # Create zeroconf instance
            zeroconf = Zeroconf()
            
            # Service types to discover
            service_types = [
                "_http._tcp.local.",
                "_https._tcp.local.",
                "_ssh._tcp.local.",
                "_smb._tcp.local.",
                "_workstation._tcp.local.",
                "_device-info._tcp.local.",
                "_airplay._tcp.local.",
                "_raop._tcp.local.",
            ]
            
            # Discover services
            discovered_services = await self._discover_services(zeroconf, service_types)
            
            # Convert services to hosts
            for service in discovered_services:
                host = await self._service_to_host(service, network)
                if host:
                    hosts.append(host)
            
            zeroconf.close()
            logger.info("mDNS discovery completed", hosts_found=len(hosts))
            
        except ImportError:
            logger.error("zeroconf not available - mDNS discovery disabled")
        except Exception as e:
            logger.error("mDNS discovery failed", error=str(e))
        
        return hosts
    
    async def _discover_services(self, zeroconf, service_types: List[str]) -> List[dict]:
        """Discover mDNS services"""
        discovered = []
        
        def service_discovered(zeroconf, service_type, name, info):
            discovered.append({
                'type': service_type,
                'name': name,
                'info': info
            })
        
        def service_removed(zeroconf, service_type, name):
            pass
        
        def service_updated(zeroconf, service_type, name, info):
            # Update existing service
            for i, service in enumerate(discovered):
                if service['name'] == name:
                    discovered[i]['info'] = info
                    break
        
        class ServiceListener:
            def __init__(self):
                self.services = []
            
            def add_service(self, zeroconf, service_type, name, info):
                self.services.append({
                    'type': service_type,
                    'name': name,
                    'info': info
                })
            
            def remove_service(self, zeroconf, service_type, name):
                pass
            
            def update_service(self, zeroconf, service_type, name, info):
                for i, service in enumerate(self.services):
                    if service['name'] == name:
                        self.services[i]['info'] = info
                        break
        
        # Create service browser
        listener = ServiceListener()
        browser = ServiceBrowser(zeroconf, service_types, listener)
        
        # Wait for discovery
        await asyncio.sleep(10)  # Give time for discovery
        
        # Clean up
        browser.cancel()
        
        return listener.services
    
    async def _service_to_host(self, service: dict, network: ipaddress.IPv4Network) -> Host:
        """Convert mDNS service to Host object"""
        try:
            info = service['info']
            
            # Get IP address
            addresses = info.addresses
            if not addresses:
                return None
            
            # Use first IPv4 address
            ip = None
            for addr in addresses:
                try:
                    ip_obj = ipaddress.ip_address(addr)
                    if isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj in network:
                        ip = str(ip_obj)
                        break
                except ValueError:
                    continue
            
            if not ip:
                return None
            
            # Extract hostname and device info
            hostname = service['name'].split('.')[0]
            service_type = service['type']
            
            # Determine device type based on service
            device_type = self._get_device_type(service_type)
            
            # Get additional info from TXT records
            properties = {}
            if info.properties:
                properties = {k.decode(): v.decode() for k, v in info.properties.items()}
            
            # Extract vendor info if available
            vendor = properties.get('manufacturer') or properties.get('model')
            
            host = self._create_host(
                ip_address=ip,
                hostname=hostname,
                vendor=vendor,
                device_type=device_type,
                os_info=properties.get('os')
            )
            
            return host
            
        except Exception as e:
            logger.debug("Failed to convert service to host", error=str(e))
            return None
    
    def _get_device_type(self, service_type: str) -> str:
        """Determine device type from service type"""
        if '_http._tcp' in service_type:
            return 'web_server'
        elif '_https._tcp' in service_type:
            return 'secure_web_server'
        elif '_ssh._tcp' in service_type:
            return 'ssh_server'
        elif '_smb._tcp' in service_type:
            return 'smb_server'
        elif '_workstation._tcp' in service_type:
            return 'workstation'
        elif '_device-info._tcp' in service_type:
            return 'device_info'
        elif '_airplay._tcp' in service_type:
            return 'airplay_device'
        elif '_raop._tcp' in service_type:
            return 'airtunes_device'
        else:
            return 'mdns_service'


