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

# Import zeroconf at module level to avoid scope issues
try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    Zeroconf = None
    ServiceBrowser = None
    ServiceListener = None


class mDNSDiscovery(BaseDiscoveryMethod):
    """mDNS/zeroconf-based service discovery"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.MDNS)
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using mDNS/zeroconf"""
        hosts = []
        
        logger.info("Starting mDNS discovery", network=str(network))
        
        if not ZEROCONF_AVAILABLE:
            logger.error("zeroconf not available - mDNS discovery disabled")
            return hosts
        
        try:
            # Create zeroconf instance
            logger.debug("Creating Zeroconf instance")
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
            
            logger.info("Starting mDNS service discovery", 
                       service_types=service_types,
                       total_types=len(service_types))
            
            # Discover services
            discovered_services = await self._discover_services(zeroconf, service_types)
            
            logger.info("mDNS service discovery completed", 
                       services_found=len(discovered_services))
            
            # Convert services to hosts
            hosts_added = 0
            hosts_skipped = 0
            for i, service in enumerate(discovered_services):
                logger.debug("Processing mDNS service", 
                           service_index=i,
                           service_name=service.get('name'),
                           service_type=service.get('type'))
                
                host = await self._service_to_host(service, network)
                if host:
                    hosts.append(host)
                    hosts_added += 1
                    logger.debug("Added host from mDNS service", 
                               ip=host.ip_address,
                               hostname=host.hostname,
                               device_type=host.device_type)
                else:
                    hosts_skipped += 1
                    logger.debug("Skipped mDNS service - could not convert to host", 
                               service_name=service.get('name'),
                               service_type=service.get('type'))
            
            zeroconf.close()
            logger.info("mDNS discovery completed", 
                       total_services=len(discovered_services),
                       hosts_added=hosts_added,
                       hosts_skipped=hosts_skipped,
                       final_hosts=len(hosts))
            
        except Exception as e:
            logger.error("mDNS discovery failed", error=str(e))
        
        return hosts
    
    async def _discover_services(self, zeroconf, service_types: List[str]) -> List[dict]:
        """Discover mDNS services"""
        class MDNSServiceListener:
            def __init__(self):
                self.services = []
            
            def add_service(self, zeroconf, service_type, name):
                # Get service info
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    self.services.append({
                        'type': service_type,
                        'name': name,
                        'info': info
                    })
                    logger.debug("Added mDNS service", service_type=service_type, name=name)
            
            def remove_service(self, zeroconf, service_type, name):
                # Remove service from list
                self.services = [s for s in self.services if not (s['type'] == service_type and s['name'] == name)]
                logger.debug("Removed mDNS service", service_type=service_type, name=name)
            
            def update_service(self, zeroconf, service_type, name):
                # Update service info
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    for i, service in enumerate(self.services):
                        if service['type'] == service_type and service['name'] == name:
                            self.services[i]['info'] = info
                            logger.debug("Updated mDNS service", service_type=service_type, name=name)
                            break
        
        # Create service browser
        listener = MDNSServiceListener()
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
            service_name = service['name']
            service_type = service['type']
            
            logger.debug("Converting mDNS service to host", 
                       service_name=service_name,
                       service_type=service_type,
                       addresses_count=len(info.addresses) if info.addresses else 0)
            
            # Get IP address
            addresses = info.addresses
            if not addresses:
                logger.debug("No addresses in mDNS service", service_name=service_name)
                return None
            
            # Use first IPv4 address
            ip = None
            for addr in addresses:
                try:
                    ip_obj = ipaddress.ip_address(addr)
                    if isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj in network:
                        ip = str(ip_obj)
                        logger.debug("Found IPv4 address in network range", 
                                   ip=ip, network=str(network))
                        break
                    else:
                        logger.debug("Address not in network range", 
                                   addr=str(addr), network=str(network))
                except ValueError as e:
                    logger.debug("Invalid address format", addr=str(addr), error=str(e))
                    continue
            
            if not ip:
                logger.debug("No valid IPv4 address found in mDNS service", 
                           service_name=service_name)
                return None
            
            # Extract hostname and device info
            hostname = service_name.split('.')[0]
            
            # Determine device type based on service
            device_type = self._get_device_type(service_type)
            
            # Get additional info from TXT records
            properties = {}
            if info.properties:
                properties = {k.decode(): v.decode() for k, v in info.properties.items()}
                logger.debug("Extracted TXT properties", 
                           properties=properties,
                           service_name=service_name)
            
            # Extract vendor info if available
            vendor = properties.get('manufacturer') or properties.get('model')
            
            logger.debug("Creating host from mDNS service", 
                       ip=ip, hostname=hostname, vendor=vendor,
                       device_type=device_type, service_type=service_type)
            
            host = self._create_host(
                ip_address=ip,
                hostname=hostname,
                vendor=vendor,
                device_type=device_type,
                os_info=properties.get('os')
            )
            
            return host
            
        except Exception as e:
            logger.debug("Failed to convert service to host", 
                        service_name=service.get('name', 'unknown'),
                        error=str(e), error_type=type(e).__name__)
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


