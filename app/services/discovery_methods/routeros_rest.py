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
        
        logger.info("Starting RouterOS REST discovery", 
                   routeros_host=self.host, 
                   network=str(network))
        
        if not all([self.host, self.username, self.password]):
            logger.debug("RouterOS REST discovery skipped - credentials not configured")
            return hosts
        
        try:
            # Create HTTP client with basic auth for RouterOS REST API
            auth = httpx.BasicAuth(self.username, self.password)
            
            async with httpx.AsyncClient(auth=auth) as client:
                
                # Get DHCP leases
                logger.debug("Requesting DHCP leases from RouterOS", 
                           url=f"http://{self.host}/rest/ip/dhcp-server/lease")
                
                dhcp_response = await client.get(
                    f"http://{self.host}/rest/ip/dhcp-server/lease",
                    timeout=10
                )
                
                logger.debug("DHCP leases response", 
                           status_code=dhcp_response.status_code,
                           content_length=len(dhcp_response.content) if dhcp_response.content else 0)
                
                if dhcp_response.status_code == 200:
                    dhcp_leases = dhcp_response.json()
                    logger.info("Retrieved DHCP leases from RouterOS", 
                              total_leases=len(dhcp_leases))
                    
                    dhcp_hosts_added = 0
                    for lease in dhcp_leases:
                        logger.debug("Processing DHCP lease", lease_data=lease)
                        
                        if 'address' in lease and 'mac-address' in lease:
                            ip = lease['address']
                            mac = lease['mac-address']
                            hostname = lease.get('host-name', '')
                            
                            logger.debug("DHCP lease details", 
                                       ip=ip, mac=mac, hostname=hostname,
                                       lease_fields=list(lease.keys()))
                            
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
                                    dhcp_hosts_added += 1
                                    
                                    logger.debug("Added host from DHCP lease", 
                                               ip=ip, mac=mac, hostname=hostname)
                                else:
                                    logger.debug("DHCP lease IP outside network range", 
                                               ip=ip, network=str(network))
                            except ValueError as e:
                                logger.warning("Invalid IP address in DHCP lease", 
                                             ip=ip, error=str(e))
                                continue
                        else:
                            logger.debug("DHCP lease missing required fields", 
                                       lease_data=lease,
                                       has_address='address' in lease,
                                       has_mac='mac-address' in lease)
                    
                    logger.info("DHCP lease processing completed", 
                              total_leases=len(dhcp_leases),
                              hosts_added=dhcp_hosts_added)
                else:
                    logger.warning("Failed to retrieve DHCP leases", 
                                 status_code=dhcp_response.status_code,
                                 response_text=dhcp_response.text[:200])
                
                # Get ARP table
                logger.debug("Requesting ARP table from RouterOS", 
                           url=f"http://{self.host}/rest/ip/arp")
                
                arp_response = await client.get(
                    f"http://{self.host}/rest/ip/arp",
                    timeout=10
                )
                
                logger.debug("ARP table response", 
                           status_code=arp_response.status_code,
                           content_length=len(arp_response.content) if arp_response.content else 0)
                
                if arp_response.status_code == 200:
                    arp_table = arp_response.json()
                    logger.info("Retrieved ARP table from RouterOS", 
                              total_entries=len(arp_table))
                    
                    arp_hosts_added = 0
                    arp_hosts_skipped = 0
                    for entry in arp_table:
                        logger.debug("Processing ARP entry", arp_data=entry)
                        
                        if 'address' in entry and 'mac-address' in entry:
                            ip = entry['address']
                            mac = entry['mac-address']
                            
                            logger.debug("ARP entry details", 
                                       ip=ip, mac=mac,
                                       entry_fields=list(entry.keys()))
                            
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
                                        arp_hosts_added += 1
                                        
                                        logger.debug("Added host from ARP entry", 
                                                   ip=ip, mac=mac)
                                    else:
                                        arp_hosts_skipped += 1
                                        logger.debug("Skipped ARP entry - host already exists from DHCP", 
                                                   ip=ip, mac=mac)
                                else:
                                    logger.debug("ARP entry IP outside network range", 
                                               ip=ip, network=str(network))
                            except ValueError as e:
                                logger.warning("Invalid IP address in ARP entry", 
                                             ip=ip, error=str(e))
                                continue
                        else:
                            logger.debug("ARP entry missing required fields", 
                                       arp_data=entry,
                                       has_address='address' in entry,
                                       has_mac='mac-address' in entry)
                    
                    logger.info("ARP table processing completed", 
                              total_entries=len(arp_table),
                              hosts_added=arp_hosts_added,
                              hosts_skipped=arp_hosts_skipped)
                else:
                    logger.warning("Failed to retrieve ARP table", 
                                 status_code=arp_response.status_code,
                                 response_text=arp_response.text[:200])
                
                logger.info("RouterOS REST discovery completed", 
                          total_hosts_found=len(hosts),
                          dhcp_hosts=len([h for h in hosts if h.device_type == "dhcp_lease"]),
                          arp_hosts=len([h for h in hosts if h.device_type == "arp_entry"]))
                
                # Log final host data for debugging
                for i, host in enumerate(hosts):
                    logger.debug("Final host data", 
                               host_index=i,
                               ip=host.ip_address,
                               mac=host.mac_address,
                               hostname=host.hostname,
                               device_type=host.device_type,
                               discovery_method=host.discovery_method)
                
        except Exception as e:
            logger.error("RouterOS REST discovery failed", 
                        error=str(e),
                        error_type=type(e).__name__)
        
        logger.info("RouterOS REST discovery finished", 
                  total_hosts_returned=len(hosts))
        return hosts


