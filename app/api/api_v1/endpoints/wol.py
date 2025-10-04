"""
Wake-on-LAN API endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import List
import structlog

from app.models.host import WOLRequest, WOLResponse, HostResponse
from app.services.wol_service import WOLService
from app.core.redis_client import redis_client

logger = structlog.get_logger(__name__)
router = APIRouter()

# Initialize WOL service
wol_service = WOLService()


@router.post("/wake", response_model=WOLResponse)
async def wake_host(request: WOLRequest):
    """Send Wake-on-LAN packet to wake a host"""
    try:
        response = await wol_service.send_wol_packet(request)
        
        logger.info("WOL request processed", 
                   ip=request.ip_address, 
                   success=response.success)
        
        return response
        
    except Exception as e:
        logger.error("WOL request failed", 
                    ip=request.ip_address, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packet")


@router.post("/wake/{ip_address}", response_model=WOLResponse)
async def wake_host_by_ip(ip_address: str):
    """Wake a host by IP address (uses stored MAC address)"""
    try:
        response = await wol_service.wake_host(ip_address)
        
        logger.info("WOL request processed by IP", 
                   ip=ip_address, 
                   success=response.success)
        
        return response
        
    except Exception as e:
        logger.error("WOL request failed", 
                    ip=ip_address, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packet")


@router.post("/wake/mac/{mac_address}", response_model=WOLResponse)
async def wake_host_by_mac(mac_address: str):
    """Wake a host by MAC address only"""
    try:
        response = await wol_service.wake_host_by_mac(mac_address)
        
        logger.info("WOL request processed by MAC", 
                   mac=mac_address, 
                   success=response.success)
        
        return response
        
    except Exception as e:
        logger.error("WOL request failed", 
                    mac=mac_address, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to send Wake-on-LAN packet")


@router.get("/wakeable", response_model=List[HostResponse])
async def get_wakeable_hosts():
    """Get all hosts that have WOL enabled and MAC addresses"""
    try:
        hosts = await redis_client.get_all_hosts()
        
        # Filter for hosts with WOL enabled and MAC addresses
        wakeable_hosts = [
            h for h in hosts 
            if h.get('wol_enabled', False) and h.get('mac_address')
        ]
        
        # Convert to HostResponse objects
        host_responses = [HostResponse(**host) for host in wakeable_hosts]
        
        logger.info("Retrieved wakeable hosts", count=len(host_responses))
        
        return host_responses
        
    except Exception as e:
        logger.error("Failed to get wakeable hosts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve wakeable hosts")


@router.post("/test/{ip_address}")
async def test_wol_capability(ip_address: str):
    """Test if a host is capable of receiving WOL packets"""
    try:
        host_data = await redis_client.get_host(ip_address)
        
        if not host_data:
            raise HTTPException(status_code=404, detail="Host not found")
        
        mac_address = host_data.get('mac_address')
        wol_enabled = host_data.get('wol_enabled', False)
        
        if not mac_address:
            return {
                "ip_address": ip_address,
                "wol_capable": False,
                "reason": "No MAC address available"
            }
        
        if not wol_enabled:
            return {
                "ip_address": ip_address,
                "wol_capable": False,
                "reason": "WOL is disabled for this host"
            }
        
        # TODO: Implement actual WOL capability test
        # For now, just check if we have the required information
        return {
            "ip_address": ip_address,
            "wol_capable": True,
            "mac_address": mac_address,
            "reason": "Host has MAC address and WOL enabled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test WOL capability", 
                    ip=ip_address, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to test WOL capability")


