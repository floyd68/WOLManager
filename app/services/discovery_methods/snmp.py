"""
SNMP discovery method
"""

import ipaddress
from typing import List
import structlog
import asyncio

from app.models.host import Host, DiscoveryMethod
from app.core.config import settings
from app.services.discovery_methods.base import BaseDiscoveryMethod

logger = structlog.get_logger(__name__)


class SNMPDiscovery(BaseDiscoveryMethod):
    """SNMP-based network discovery"""
    
    def __init__(self):
        super().__init__(DiscoveryMethod.SNMP)
        self.community = settings.SNMP_COMMUNITY
        self.timeout = settings.SNMP_TIMEOUT
    
    async def discover(self, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts using SNMP"""
        hosts = []
        
        try:
            from pysnmp.hlapi import (
                SnmpEngine, CommunityData, UdpTransportTarget, 
                ContextData, ObjectType, ObjectIdentity, nextCmd
            )
            
            # Get network devices (routers, switches) first
            gateway_ip = str(network.network_address + 1)
            
            # Try to discover from gateway device
            if await self._is_snmp_available(gateway_ip):
                gateway_hosts = await self._discover_from_device(gateway_ip, network)
                hosts.extend(gateway_hosts)
            
            # Try to discover from other potential network devices
            potential_devices = [
                str(network.network_address + 1),  # Gateway
                str(network.network_address + 2),  # Secondary gateway
                str(network.network_address + 254),  # Common gateway
            ]
            
            for device_ip in potential_devices:
                if device_ip != gateway_ip and await self._is_snmp_available(device_ip):
                    device_hosts = await self._discover_from_device(device_ip, network)
                    hosts.extend(device_hosts)
            
            logger.info("SNMP discovery completed", hosts_found=len(hosts))
            
        except ImportError:
            logger.error("pysnmp not available - SNMP discovery disabled")
        except Exception as e:
            logger.error("SNMP discovery failed", error=str(e))
        
        return hosts
    
    async def _is_snmp_available(self, ip: str) -> bool:
        """Check if SNMP is available on the device"""
        try:
            from pysnmp.hlapi import (
                SnmpEngine, CommunityData, UdpTransportTarget, 
                ContextData, ObjectType, ObjectIdentity, nextCmd
            )
            
            def check_snmp():
                for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                    SnmpEngine(),
                    CommunityData(self.community),
                    UdpTransportTarget((ip, 161), timeout=self.timeout),
                    ContextData(),
                    ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')),  # sysDescr
                    lexicographicMode=False
                ):
                    if errorIndication:
                        return False
                    elif errorStatus:
                        return False
                    else:
                        return True
                return False
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, check_snmp)
            
        except Exception:
            return False
    
    async def _discover_from_device(self, device_ip: str, network: ipaddress.IPv4Network) -> List[Host]:
        """Discover hosts from a specific SNMP device"""
        hosts = []
        
        try:
            from pysnmp.hlapi import (
                SnmpEngine, CommunityData, UdpTransportTarget, 
                ContextData, ObjectType, ObjectIdentity, nextCmd
            )
            
            def snmp_discovery():
                discovered_hosts = []
                
                # Get ARP table
                for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                    SnmpEngine(),
                    CommunityData(self.community),
                    UdpTransportTarget((device_ip, 161), timeout=self.timeout),
                    ContextData(),
                    ObjectType(ObjectIdentity('1.3.6.1.2.1.4.22.1.2')),  # ipNetToMediaPhysAddress
                    lexicographicMode=False
                ):
                    if errorIndication:
                        break
                    elif errorStatus:
                        break
                    else:
                        for varBind in varBinds:
                            oid, value = varBind
                            
                            # Extract IP and MAC from OID and value
                            oid_parts = str(oid).split('.')
                            if len(oid_parts) >= 6:
                                ip_parts = oid_parts[-4:]
                                ip = '.'.join(ip_parts)
                                mac = ':'.join([f"{b:02x}" for b in bytes(value)])
                                
                                # Check if IP is in our network range
                                try:
                                    ip_obj = ipaddress.ip_address(ip)
                                    if ip_obj in network:
                                        discovered_hosts.append({
                                            'ip': ip,
                                            'mac': mac,
                                            'source': 'snmp_arp'
                                        })
                                except ValueError:
                                    continue
                
                return discovered_hosts
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            discovered = await loop.run_in_executor(None, snmp_discovery)
            
            for item in discovered:
                host = self._create_host(
                    ip_address=item['ip'],
                    mac_address=item['mac'],
                    device_type=item['source']
                )
                hosts.append(host)
                
        except Exception as e:
            logger.error("SNMP discovery from device failed", device=device_ip, error=str(e))
        
        return hosts
