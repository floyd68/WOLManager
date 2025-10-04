"""
Host models for WOLManager
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DiscoveryMethod(str, Enum):
    """Discovery method enumeration"""
    ROUTEROS_API = "routeros_api"
    ROUTEROS_REST = "routeros_rest"
    SNMP = "snmp"
    NETBIOS = "netbios"
    MDNS = "mdns"
    ARP = "arp"


class HostStatus(str, Enum):
    """Host status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class Host(BaseModel):
    """Host information model"""
    
    ip_address: str = Field(..., description="IP address of the host")
    mac_address: Optional[str] = Field(None, description="MAC address")
    hostname: Optional[str] = Field(None, description="Hostname")
    vendor: Optional[str] = Field(None, description="Hardware vendor")
    device_type: Optional[str] = Field(None, description="Device type")
    os_info: Optional[str] = Field(None, description="Operating system information")
    discovery_method: Optional[DiscoveryMethod] = Field(None, description="Method used for discovery")
    status: HostStatus = Field(HostStatus.UNKNOWN, description="Current status")
    last_seen: Optional[datetime] = Field(None, description="Last time the host was seen")
    wol_enabled: bool = Field(True, description="Whether WOL is enabled for this host")
    notes: Optional[str] = Field(None, description="Additional notes")
    inferred_os: Optional[str] = Field(None, description="Inferred operating system")
    inferred_device_type: Optional[str] = Field(None, description="Inferred device type")
    inference_confidence: Optional[int] = Field(None, description="Confidence level of inference (0-100)")
    
    class Config:
        use_enum_values = True


class HostCreate(BaseModel):
    """Host creation model"""
    
    ip_address: str = Field(..., description="IP address of the host")
    mac_address: Optional[str] = Field(None, description="MAC address")
    hostname: Optional[str] = Field(None, description="Hostname")
    vendor: Optional[str] = Field(None, description="Hardware vendor")
    device_type: Optional[str] = Field(None, description="Device type")
    os_info: Optional[str] = Field(None, description="Operating system information")
    wol_enabled: bool = Field(True, description="Whether WOL is enabled for this host")
    notes: Optional[str] = Field(None, description="Additional notes")


class HostUpdate(BaseModel):
    """Host update model"""
    
    mac_address: Optional[str] = Field(None, description="MAC address")
    hostname: Optional[str] = Field(None, description="Hostname")
    vendor: Optional[str] = Field(None, description="Hardware vendor")
    device_type: Optional[str] = Field(None, description="Device type")
    os_info: Optional[str] = Field(None, description="Operating system information")
    status: Optional[HostStatus] = Field(None, description="Current status")
    wol_enabled: Optional[bool] = Field(None, description="Whether WOL is enabled for this host")
    notes: Optional[str] = Field(None, description="Additional notes")


class HostResponse(BaseModel):
    """Host response model"""
    
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    device_type: Optional[str] = None
    os_info: Optional[str] = None
    discovery_method: Optional[DiscoveryMethod] = None
    status: HostStatus
    last_seen: Optional[datetime] = None
    wol_enabled: bool
    notes: Optional[str] = None
    inferred_os: Optional[str] = None
    inferred_device_type: Optional[str] = None
    inference_confidence: Optional[int] = None
    
    class Config:
        from_attributes = True


class WOLRequest(BaseModel):
    """Wake-on-LAN request model"""
    
    ip_address: str = Field(..., description="IP address of the host to wake")
    mac_address: Optional[str] = Field(None, description="MAC address (optional if host exists)")
    broadcast_address: Optional[str] = Field(None, description="Broadcast address (optional)")


class WOLResponse(BaseModel):
    """Wake-on-LAN response model"""
    
    success: bool
    message: str
    ip_address: str
    mac_address: Optional[str]

