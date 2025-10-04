"""
RouterOS API discovery method
"""

import ipaddress
from typing import List, Optional
import structlog

from app.models.host import Host, DiscoveryMethod, HostStatus
from app.core.config import settings
from app.services.discovery_methods.base import BaseDiscoveryMethod
from app.services.dhcp_analyzer import DHCPAnalyzer

logger = structlog.get_logger(__name__)


class RouterOSAPIDiscovery(BaseDiscoveryMethod):
    """RouterOS API discovery using librouteros"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.ROUTEROS_API)
        self.host = settings.ROUTEROS_HOST
        self.username = settings.ROUTEROS_USERNAME
        self.password = settings.ROUTEROS_PASSWORD
        self.port = settings.ROUTEROS_PORT
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using RouterOS API"""
        hosts = []
        
        logger.info("Starting RouterOS API discovery", 
                   routeros_host=self.host, 
                   routeros_port=self.port,
                   network=str(network))
        
        if not all([self.host, self.username, self.password]):
            logger.debug("RouterOS API discovery skipped - credentials not configured")
            return hosts
        
        try:
            import librouteros
            from librouteros import connect
            
            logger.debug("Connecting to RouterOS API", 
                        host=self.host, port=self.port, username=self.username)
            
            # Connect to RouterOS
            api = connect(
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.port
            )
            
            logger.info("Successfully connected to RouterOS API")
            
            # Get DHCP leases with detailed information
            logger.debug("Requesting DHCP leases from RouterOS API")
            dhcp_leases = api('/ip/dhcp-server/lease/print')
            
            logger.info("Retrieved DHCP leases from RouterOS API", 
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
                            # Extract additional information from DHCP lease
                            client_id = lease.get('client-id', '')
                            comment = lease.get('comment', '')
                            class_id = lease.get('class-id', '')
                            status = lease.get('status', 'active')
                            server = lease.get('server', '')
                            expires_after = lease.get('expires-after', '')
                            last_seen = lease.get('last-seen', '')
                            active_address = lease.get('active-address', '')
                            active_mac = lease.get('active-mac-address', '')
                            
                            # Get vendor information from MAC address
                            vendor = self._get_vendor_from_mac(mac)
                            
                            # Infer OS from class_id
                            inferred_os = self._infer_os_from_class_id(class_id)
                            
                            # Build OS info from available data
                            os_info_parts = []
                            if client_id:
                                os_info_parts.append(f"Client-ID: {client_id}")
                            if expires_after:
                                os_info_parts.append(f"Expires: {expires_after}")
                            if last_seen:
                                os_info_parts.append(f"Last seen: {last_seen}")
                            if server:
                                os_info_parts.append(f"DHCP Server: {server}")
                            
                            os_info = '; '.join(os_info_parts) if os_info_parts else None
                            
                            # Use active information if available
                            final_ip = active_address if active_address else ip
                            final_mac = active_mac if active_mac else mac
                            
                            # Analyze DHCP lease for additional information
                            lease_data = {
                                'mac_address': final_mac,
                                'hostname': hostname,
                                'os_info': os_info,
                                'client_id': client_id,
                                'comment': comment,
                                'class_id': class_id
                            }
                            inferred_info = DHCPAnalyzer.analyze_dhcp_lease(lease_data)
                            logger.debug("DHCP analysis result", ip=final_ip, inferred=inferred_info)
                            
                            # Use inferred information if available
                            final_vendor = vendor or inferred_info.get('vendor')
                            final_device_type = f"dhcp_lease_{status}"
                            if inferred_info.get('device_type'):
                                final_device_type = f"{final_device_type}_{inferred_info['device_type']}"
                            
                            # Enhance OS info with inferred information
                            enhanced_os_info = os_info or ""
                            # Use class_id inference first, then DHCP analyzer
                            final_inferred_os = inferred_os or inferred_info.get('os')
                            if final_inferred_os:
                                enhanced_os_info += f"; Inferred OS: {final_inferred_os}" if enhanced_os_info else f"Inferred OS: {final_inferred_os}"
                            if inferred_info.get('confidence', 0) > 50:
                                enhanced_os_info += f"; Confidence: {inferred_info['confidence']}%" if enhanced_os_info else f"Confidence: {inferred_info['confidence']}%"
                            
                            # Determine host status based on DHCP lease
                            host_status = self._determine_host_status(status, last_seen, expires_after)
                            
                            # Create host with inferred information
                            host_kwargs = {
                                'ip_address': final_ip,
                                'mac_address': final_mac,
                                'hostname': hostname,
                                'vendor': final_vendor,
                                'device_type': final_device_type,
                                'os_info': enhanced_os_info,
                                'status': host_status,
                            }
                            
                            # Add inferred fields if they exist
                            if final_inferred_os:
                                host_kwargs['inferred_os'] = final_inferred_os
                            if inferred_info.get('device_type'):
                                host_kwargs['inferred_device_type'] = inferred_info['device_type']
                            if inferred_info.get('confidence'):
                                host_kwargs['inference_confidence'] = inferred_info['confidence']
                            
                            logger.debug("Creating host with kwargs", ip=final_ip, kwargs=host_kwargs)
                            host = self._create_host(**host_kwargs)
                            hosts.append(host)
                    except ValueError:
                        continue
            
            # Get ARP table with additional information
            arp_table = api('/ip/arp/print')
            for entry in arp_table:
                if 'address' in entry and 'mac-address' in entry:
                    ip = entry['address']
                    mac = entry['mac-address']
                    interface = entry.get('interface', '')
                    comment = entry.get('comment', '')
                    dhcp = entry.get('dhcp', 'false')
                    invalid = entry.get('invalid', 'false')
                    dynamic = entry.get('dynamic', 'false')
                    published = entry.get('published', 'false')
                    
                    # Check if IP is in our network range
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if ip_obj in network:
                            # Check if we already have this host from DHCP
                            existing = any(h.ip_address == ip for h in hosts)
                            if not existing:
                                # Try to get vendor information from MAC address
                                vendor = self._get_vendor_from_mac(mac)
                                
                                # Build OS info from ARP data
                                arp_info_parts = []
                                if dhcp == 'true':
                                    arp_info_parts.append('DHCP')
                                if dynamic == 'true':
                                    arp_info_parts.append('Dynamic')
                                if published == 'true':
                                    arp_info_parts.append('Published')
                                if invalid == 'true':
                                    arp_info_parts.append('Invalid')
                                if interface:
                                    arp_info_parts.append(f"Interface: {interface}")
                                if comment:
                                    arp_info_parts.append(f"Comment: {comment}")
                                
                                os_info = '; '.join(arp_info_parts) if arp_info_parts else None
                                
                                # Determine host status based on ARP entry
                                host_status = self._determine_arp_host_status(dynamic, invalid, published)
                                
                                host = self._create_host(
                                    ip_address=ip,
                                    mac_address=mac,
                                    vendor=vendor,
                                    device_type=f"arp_entry_{interface}",
                                    os_info=os_info,
                                    status=host_status
                                )
                                hosts.append(host)
                    except ValueError:
                        continue
            
            # Get DHCP server information
            try:
                dhcp_servers = api('/ip/dhcp-server/print')
                for server in dhcp_servers:
                    server_interface = server.get('interface', '')
                    server_address = server.get('address', '')
                    server_authoritative = server.get('authoritative', 'no')
                    server_disabled = server.get('disabled', 'no')
                    
                    # Create a host entry for the DHCP server itself
                    if server_address and server_address not in [h.ip_address for h in hosts]:
                        try:
                            ip_obj = ipaddress.ip_address(server_address)
                            if ip_obj in network:
                                host = self._create_host(
                                    ip_address=server_address,
                                    mac_address=None,  # DHCP server MAC not available here
                                    hostname=f"DHCP-Server-{server_interface}",
                                    device_type="dhcp_server",
                                    os_info=f"Interface: {server_interface}; Authoritative: {server_authoritative}; Disabled: {server_disabled}"
                                )
                                hosts.append(host)
                        except ValueError:
                            continue
            except Exception as e:
                logger.debug("Failed to get DHCP server info", error=str(e))
            
            api.close()
            logger.info("RouterOS API discovery completed", hosts_found=len(hosts))
            
        except ImportError:
            logger.error("librouteros not available - RouterOS API discovery disabled")
        except Exception as e:
            logger.error("RouterOS API discovery failed", error=str(e))
        
        return hosts
    
    def _get_vendor_from_mac(self, mac_address: str) -> str:
        """Get vendor information from MAC address OUI"""
        try:
            # Extract first 3 octets (OUI) from MAC address
            oui = ':'.join(mac_address.split(':')[:3]).upper()
            
            # Common vendor OUIs (sorted by OUI, deduplicated)
            vendor_map = {
                '00:03:FF': 'Microsoft',
                '00:0C:29': 'VMware',
                '00:15:5D': 'Microsoft Hyper-V',
                '00:16:3E': 'Xen',
                '00:1B:44': 'Cisco Systems',
                '00:1C:14': 'VMware',
                '00:1C:42': 'Parallels',
                '00:50:56': 'VMware',
                '02:00:4C:4F': 'Microsoft',
                '08:00:27': 'Oracle VirtualBox',
                '0A:00:27': 'Oracle VirtualBox',
                '14:88:A9': 'ASUSTeK Computer',
                '1A:C3:AF': 'Apple',
                '52:54:00': 'QEMU',
                '70:85:C2': 'Apple',
                '80:CA:4B': 'Apple',
                'A8:A1:59': 'LG Electronics',
                'D8:50:E6': 'Apple',
                'D8:5E:D3': 'Apple',
                # Add more vendor OUIs as needed
            }
            
            if oui in vendor_map:
                return vendor_map[oui]
            
            # Try to get vendor from online OUI database (optional)
            # This could be implemented with an API call or local database
            return None
            
        except Exception:
            return None
    
    def _infer_os_from_class_id(self, class_id: str) -> Optional[str]:
        """Infer OS from DHCP class ID"""
        if not class_id:
            return None
            
        class_id_lower = class_id.lower()
        
        # Windows detection
        if 'msft' in class_id_lower:
            if '5.0' in class_id_lower:
                return "Windows 2000"
            elif '6.0' in class_id_lower:
                return "Windows Vista/Server 2008"
            elif '6.1' in class_id_lower:
                return "Windows 7/Server 2008 R2"
            elif '6.2' in class_id_lower:
                return "Windows 8/Server 2012"
            elif '6.3' in class_id_lower:
                return "Windows 8.1/Server 2012 R2"
            elif '10.0' in class_id_lower:
                return "Windows 10/11/Server 2016+"
            else:
                return "Windows (Unknown Version)"
        
        # Android detection
        if 'android' in class_id_lower:
            if 'dhcp-13' in class_id_lower:
                return "Android 13+"
            elif 'dhcp-12' in class_id_lower:
                return "Android 12"
            elif 'dhcp-11' in class_id_lower:
                return "Android 11"
            elif 'dhcp-10' in class_id_lower:
                return "Android 10"
            else:
                return "Android (Unknown Version)"
        
        # iOS detection
        if 'iphone' in class_id_lower or 'ipad' in class_id_lower:
            return "iOS"
        
        # Linux detection
        if 'linux' in class_id_lower or 'ubuntu' in class_id_lower or 'debian' in class_id_lower:
            return "Linux"
        
        # RouterOS detection
        if 'routeros' in class_id_lower or 'mikrotik' in class_id_lower:
            return "RouterOS"
        
        # Generic DHCP clients
        if 'udhcp' in class_id_lower:
            return "Linux (udhcp client)"
        
        # Custom class IDs
        if 'lguap' in class_id_lower:
            return "LG U+ AP (Custom)"
        
        return None
    
    def _determine_host_status(self, lease_status: str, last_seen: str, expires_after: str) -> HostStatus:
        """Determine host status based on DHCP lease information"""
        try:
            # Parse lease status
            if lease_status.lower() in ['bound', 'active']:
                # Check if lease is recent (within last 24 hours)
                if last_seen:
                    # For now, consider all DHCP bound leases as online
                    # In a real implementation, you might ping the host or check last seen time
                    return HostStatus.ONLINE
                return HostStatus.ONLINE
            elif lease_status.lower() in ['offered', 'waiting']:
                return HostStatus.UNKNOWN
            else:
                return HostStatus.OFFLINE
        except Exception:
            return HostStatus.UNKNOWN
    
    def _determine_arp_host_status(self, dynamic: str, invalid: str, published: str) -> HostStatus:
        """Determine host status based on ARP entry information"""
        try:
            if invalid.lower() == 'true':
                return HostStatus.OFFLINE
            elif dynamic.lower() == 'true':
                # Dynamic ARP entries are usually active
                return HostStatus.ONLINE
            elif published.lower() == 'true':
                # Published ARP entries are usually static/active
                return HostStatus.ONLINE
            else:
                return HostStatus.UNKNOWN
        except Exception:
            return HostStatus.UNKNOWN

