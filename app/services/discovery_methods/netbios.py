"""
NetBIOS/SMB discovery method
"""

import ipaddress
from typing import List
import structlog
import asyncio
import socket

from app.models.host import Host, DiscoveryMethod
from app.services.discovery_methods.base import BaseDiscoveryMethod

logger = structlog.get_logger(__name__)


class NetBIOSDiscovery(BaseDiscoveryMethod):
    """NetBIOS/SMB-based host discovery"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.NETBIOS)
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using NetBIOS/SMB"""
        hosts = []
        
        try:
            # Get list of IPs to scan
            ips_to_scan = [str(ip) for ip in network.hosts()]
            
            # Scan in batches to avoid overwhelming the network
            batch_size = 50
            for i in range(0, len(ips_to_scan), batch_size):
                batch = ips_to_scan[i:i + batch_size]
                batch_hosts = await self._scan_batch(batch)
                hosts.extend(batch_hosts)
                
                # Small delay between batches
                await asyncio.sleep(0.1)
            
            logger.info("NetBIOS discovery completed", hosts_found=len(hosts))
            
        except Exception as e:
            logger.error("NetBIOS discovery failed", error=str(e))
        
        return hosts
    
    async def _scan_batch(self, ips: List[str]) -> List[Host]:
        """Scan a batch of IP addresses"""
        tasks = [self._scan_host(ip) for ip in ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        hosts = []
        for result in results:
            if isinstance(result, Host):
                hosts.append(result)
            elif isinstance(result, Exception):
                logger.debug("Host scan failed", error=str(result))
        
        return hosts
    
    async def _scan_host(self, ip: str) -> Host:
        """Scan a single host for NetBIOS information"""
        try:
            # Try to get hostname via reverse DNS
            hostname = await self._get_hostname(ip)
            
            # Try to detect if it's a Windows/SMB host
            is_windows = await self._is_windows_host(ip)
            
            # Try to get MAC address via ARP
            mac_address = await self._get_mac_address(ip)
            
            if hostname or is_windows or mac_address:
                host = self._create_host(
                    ip_address=ip,
                    hostname=hostname,
                    mac_address=mac_address,
                    device_type="windows" if is_windows else "netbios"
                )
                return host
            
        except Exception as e:
            logger.debug("Failed to scan host", ip=ip, error=str(e))
        
        # Return None if no useful information found
        return None
    
    async def _get_hostname(self, ip: str) -> str:
        """Get hostname via reverse DNS lookup"""
        try:
            def reverse_lookup():
                try:
                    return socket.gethostbyaddr(ip)[0]
                except (socket.herror, socket.gaierror, socket.timeout):
                    return None
            
            loop = asyncio.get_event_loop()
            hostname = await loop.run_in_executor(None, reverse_lookup)
            return hostname
        except Exception:
            return None
    
    async def _is_windows_host(self, ip: str) -> bool:
        """Check if host is running Windows/SMB services"""
        try:
            # Check common Windows ports
            windows_ports = [139, 445, 135, 3389]
            
            for port in windows_ports:
                if await self._check_port(ip, port):
                    return True
            
            return False
        except Exception:
            return False
    
    async def _check_port(self, ip: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a port is open on the host"""
        try:
            def check_port():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                try:
                    result = sock.connect_ex((ip, port))
                    return result == 0
                finally:
                    sock.close()
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, check_port)
        except Exception:
            return False
    
    async def _get_mac_address(self, ip: str) -> str:
        """Get MAC address via ARP table lookup"""
        try:
            import subprocess
            import re
            
            def get_mac():
                try:
                    # Try different ARP commands based on OS
                    result = subprocess.run(
                        ['arp', '-n', ip], 
                        capture_output=True, 
                        text=True, 
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        # Parse ARP output
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            if ip in line:
                                # Extract MAC address
                                mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', line)
                                if mac_match:
                                    return mac_match.group(0).replace('-', ':').upper()
                    
                    return None
                except Exception:
                    return None
            
            loop = asyncio.get_event_loop()
            mac = await loop.run_in_executor(None, get_mac)
            return mac
        except Exception:
            return None


