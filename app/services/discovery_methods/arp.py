"""
ARP table discovery method
"""

import ipaddress
from typing import List
import structlog
import asyncio
import subprocess
import re
import platform

from app.models.host import Host, DiscoveryMethod
from app.services.discovery_methods.base import BaseDiscoveryMethod

logger = structlog.get_logger(__name__)


class ARPDiscovery(BaseDiscoveryMethod):
    """ARP table-based host discovery"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.ARP)
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using ARP table"""
        hosts = []
        
        try:
            # Get ARP table entries
            arp_entries = await self._get_arp_table()
            
            for entry in arp_entries:
                ip = entry.get('ip')
                mac = entry.get('mac')
                
                if ip and mac:
                    # Check if IP is in our network range
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        if ip_obj in network:
                            host = self._create_host(
                                ip_address=ip,
                                mac_address=mac,
                                device_type="arp_entry"
                            )
                            hosts.append(host)
                    except ValueError:
                        continue
            
            logger.info("ARP discovery completed", hosts_found=len(hosts))
            
        except Exception as e:
            logger.error("ARP discovery failed", error=str(e))
        
        return hosts
    
    async def _get_arp_table(self) -> List[dict]:
        """Get ARP table entries"""
        try:
            system = platform.system().lower()
            
            if system == 'linux':
                return await self._get_linux_arp_table()
            elif system == 'darwin':  # macOS
                return await self._get_macos_arp_table()
            elif system == 'windows':
                return await self._get_windows_arp_table()
            else:
                logger.warning("Unsupported OS for ARP discovery", os=system)
                return []
                
        except Exception as e:
            logger.error("Failed to get ARP table", error=str(e))
            return []
    
    async def _get_linux_arp_table(self) -> List[dict]:
        """Get ARP table on Linux"""
        try:
            def read_arp():
                entries = []
                try:
                    # Read /proc/net/arp
                    with open('/proc/net/arp', 'r') as f:
                        lines = f.readlines()[1:]  # Skip header
                        
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 4:
                                ip = parts[0]
                                mac = parts[3]
                                
                                # Skip incomplete entries
                                if mac != "00:00:00:00:00:00":
                                    entries.append({'ip': ip, 'mac': mac})
                
                except Exception as e:
                    logger.debug("Failed to read /proc/net/arp", error=str(e))
                
                return entries
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, read_arp)
            
        except Exception as e:
            logger.error("Linux ARP table read failed", error=str(e))
            return []
    
    async def _get_macos_arp_table(self) -> List[dict]:
        """Get ARP table on macOS"""
        try:
            def run_arp():
                entries = []
                try:
                    result = subprocess.run(
                        ['arp', '-a'], 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        
                        for line in lines:
                            # Parse: hostname (192.168.1.1) at aa:bb:cc:dd:ee:ff [ether] on en0
                            match = re.match(r'.*\((\d+\.\d+\.\d+\.\d+)\).*at ([0-9a-fA-F:]+)', line)
                            if match:
                                ip = match.group(1)
                                mac = match.group(2)
                                entries.append({'ip': ip, 'mac': mac})
                
                except Exception as e:
                    logger.debug("Failed to run arp -a", error=str(e))
                
                return entries
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_arp)
            
        except Exception as e:
            logger.error("macOS ARP table read failed", error=str(e))
            return []
    
    async def _get_windows_arp_table(self) -> List[dict]:
        """Get ARP table on Windows"""
        try:
            def run_arp():
                entries = []
                try:
                    result = subprocess.run(
                        ['arp', '-a'], 
                        capture_output=True, 
                        text=True, 
                        timeout=10,
                        shell=True
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        
                        for line in lines:
                            # Parse: 192.168.1.1 aa-bb-cc-dd-ee-ff dynamic
                            match = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]+)', line)
                            if match:
                                ip = match.group(1)
                                mac = match.group(2).replace('-', ':')
                                entries.append({'ip': ip, 'mac': mac})
                
                except Exception as e:
                    logger.debug("Failed to run arp -a", error=str(e))
                
                return entries
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, run_arp)
            
        except Exception as e:
            logger.error("Windows ARP table read failed", error=str(e))
            return []


