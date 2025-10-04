"""
RouterOS REST API discovery method
"""

import ipaddress
from typing import List
import structlog
import httpx

from app.models.host import Host, DiscoveryMethod
from app.core.config import settings
from app.services.discovery_methods.base import BaseDiscoveryMethod

logger = structlog.get_logger(__name__)


class RouterOSRestDiscovery(BaseDiscoveryMethod):
    """RouterOS REST API discovery"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.ROUTEROS_REST)
        self.host = settings.ROUTEROS_HOST
        self.username = settings.ROUTEROS_USERNAME
        self.password = settings.ROUTEROS_PASSWORD
        self.port = 80  # REST API port
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using RouterOS REST API"""
        hosts = []
        
        if not all([self.host, self.username, self.password]):
            logger.debug("RouterOS REST discovery skipped - credentials not configured")
            return hosts
        
        try:
            # Create HTTP client with basic auth for RouterOS REST API
            auth = httpx.BasicAuth(self.username, self.password)
            
            async with httpx.AsyncClient(auth=auth) as client:
                
                # Get DHCP leases
                dhcp_response = await client.get(
                    f"http://{self.host}/rest/ip/dhcp-server/lease",
                    timeout=10
                )
                
                if dhcp_response.status_code == 200:
                    dhcp_leases = dhcp_response.json()
                    for lease in dhcp_leases:
                        if 'address' in lease and 'mac-address' in lease:
                            ip = lease['address']
                            mac = lease['mac-address']
                            hostname = lease.get('host-name', '')
                            
                            # Check if IP is in our network range
                            try:
                                ip_obj = ipaddress.ip_address(ip)
                                if ip_obj in network:
                                    host = self._create_host(
                                        ip_address=ip,
                                        mac_address=mac,
                                        hostname=hostname,
                                        device_type="dhcp_lease"
                                    )
                                    hosts.append(host)
                            except ValueError:
                                continue
                
                # Get ARP table
                arp_response = await client.get(
                    f"http://{self.host}/rest/ip/arp",
                    timeout=10
                )
                
                if arp_response.status_code == 200:
                    arp_table = arp_response.json()
                    for entry in arp_table:
                        if 'address' in entry and 'mac-address' in entry:
                            ip = entry['address']
                            mac = entry['mac-address']
                            
                            # Check if IP is in our network range
                            try:
                                ip_obj = ipaddress.ip_address(ip)
                                if ip_obj in network:
                                    # Check if we already have this host from DHCP
                                    existing = any(h.ip_address == ip for h in hosts)
                                    if not existing:
                                        host = self._create_host(
                                            ip_address=ip,
                                            mac_address=mac,
                                            device_type="arp_entry"
                                        )
                                        hosts.append(host)
                            except ValueError:
                                continue
                
                logger.info("RouterOS REST discovery completed", hosts_found=len(hosts))
                
        except Exception as e:
            logger.error("RouterOS REST discovery failed", error=str(e))
        
        return hosts


