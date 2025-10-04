"""
Host management API endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import structlog

from app.models.host import Host, HostCreate, HostUpdate, HostResponse
from app.core.redis_client import redis_client

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/wol-registered")
async def get_wol_registered_hosts():
    """Get all hosts registered for Wake-on-LAN broadcasts"""
    try:
        hosts = await redis_client.get_all_hosts()
        
        # Filter hosts that are registered for WOL
        wol_hosts = [host for host in hosts if host.get('wol_enabled', False)]
        
        # Convert to HostResponse objects
        host_responses = [HostResponse(**host) for host in wol_hosts]
        
        logger.info("Retrieved WOL registered hosts", count=len(host_responses))
        
        return {
            "hosts": host_responses,
            "count": len(host_responses),
            "total_hosts": len(hosts)
        }
        
    except Exception as e:
        logger.error("Failed to get WOL registered hosts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve WOL registered hosts")


@router.get("/", response_model=List[HostResponse])
async def get_hosts(
    status: Optional[str] = Query(None, description="Filter by status"),
    wol_enabled: Optional[bool] = Query(None, description="Filter by WOL enabled"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of hosts to return")
):
    """Get all hosts with optional filtering"""
    try:
        hosts = await redis_client.get_all_hosts()
        
        # Apply filters
        if status:
            hosts = [h for h in hosts if h.get('status') == status]
        
        if wol_enabled is not None:
            hosts = [h for h in hosts if h.get('wol_enabled') == wol_enabled]
        
        # Limit results
        hosts = hosts[:limit]
        
        # Convert to HostResponse objects
        host_responses = [HostResponse(**host) for host in hosts]
        
        logger.info("Retrieved hosts", count=len(host_responses), filters={
            'status': status,
            'wol_enabled': wol_enabled,
            'limit': limit
        })
        
        return host_responses
        
    except Exception as e:
        logger.error("Failed to get hosts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve hosts")


@router.get("/{ip_address}", response_model=HostResponse)
async def get_host(ip_address: str):
    """Get a specific host by IP address"""
    try:
        host_data = await redis_client.get_host(ip_address)
        
        if not host_data:
            raise HTTPException(status_code=404, detail="Host not found")
        
        host_response = HostResponse(**host_data)
        logger.info("Retrieved host", ip=ip_address)
        
        return host_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get host", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve host")


@router.post("/", response_model=HostResponse)
async def create_host(host: HostCreate):
    """Create a new host"""
    try:
        # Check if host already exists
        existing = await redis_client.get_host(host.ip_address)
        if existing:
            raise HTTPException(status_code=409, detail="Host already exists")
        
        # Create host data
        host_data = host.dict()
        host_data['status'] = 'unknown'
        
        # Store in Redis
        success = await redis_client.set_host(host_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create host")
        
        # Retrieve the created host
        created_host = await redis_client.get_host(host.ip_address)
        host_response = HostResponse(**created_host)
        
        logger.info("Created host", ip=host.ip_address)
        return host_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create host", ip=host.ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create host")


@router.put("/{ip_address}", response_model=HostResponse)
async def update_host(ip_address: str, host_update: HostUpdate):
    """Update an existing host"""
    try:
        # Check if host exists
        existing = await redis_client.get_host(ip_address)
        if not existing:
            raise HTTPException(status_code=404, detail="Host not found")
        
        # Prepare update data (only non-None values)
        update_data = {k: v for k, v in host_update.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        # Update host
        success = await redis_client.update_host(ip_address, update_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update host")
        
        # Retrieve the updated host
        updated_host = await redis_client.get_host(ip_address)
        host_response = HostResponse(**updated_host)
        
        logger.info("Updated host", ip=ip_address, updates=update_data)
        return host_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update host", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update host")


@router.delete("/{ip_address}")
async def delete_host(ip_address: str):
    """Delete a host"""
    try:
        # Check if host exists
        existing = await redis_client.get_host(ip_address)
        if not existing:
            raise HTTPException(status_code=404, detail="Host not found")
        
        # Delete host
        success = await redis_client.delete_host(ip_address)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete host")
        
        logger.info("Deleted host", ip=ip_address)
        return {"message": "Host deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete host", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete host")


@router.post("/{ip_address}/register-wol")
async def register_host_for_wol(ip_address: str):
    """Register a host for Wake-on-LAN broadcasts"""
    try:
        host_data = await redis_client.get_host(ip_address)
        
        if not host_data:
            raise HTTPException(status_code=404, detail="Host not found")
        
        # Check if host has MAC address (required for WOL)
        if not host_data.get('mac_address'):
            raise HTTPException(status_code=400, detail="Host must have a MAC address to register for WOL")
        
        # Update host to enable WOL
        updates = {'wol_enabled': True}
        success = await redis_client.update_host(ip_address, updates)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to register host for WOL")
        
        logger.info("Host registered for WOL", ip=ip_address, mac=host_data.get('mac_address'))
        
        return {
            "message": f"Host {ip_address} successfully registered for Wake-on-LAN broadcasts",
            "ip_address": ip_address,
            "mac_address": host_data.get('mac_address'),
            "wol_enabled": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to register host for WOL", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to register host for WOL")


@router.post("/{ip_address}/unregister-wol")
async def unregister_host_from_wol(ip_address: str):
    """Unregister a host from Wake-on-LAN broadcasts"""
    try:
        host_data = await redis_client.get_host(ip_address)
        
        if not host_data:
            raise HTTPException(status_code=404, detail="Host not found")
        
        # Update host to disable WOL
        updates = {'wol_enabled': False}
        success = await redis_client.update_host(ip_address, updates)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to unregister host from WOL")
        
        logger.info("Host unregistered from WOL", ip=ip_address)
        
        return {
            "message": f"Host {ip_address} successfully unregistered from Wake-on-LAN broadcasts",
            "ip_address": ip_address,
            "wol_enabled": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unregister host from WOL", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to unregister host from WOL")


@router.get("/{ip_address}/status")
async def get_host_status(ip_address: str):
    """Get host status and connectivity information"""
    try:
        host_data = await redis_client.get_host(ip_address)
        
        if not host_data:
            raise HTTPException(status_code=404, detail="Host not found")
        
        # TODO: Implement actual connectivity check
        # For now, return the stored status
        status_info = {
            "ip_address": ip_address,
            "status": host_data.get('status', 'unknown'),
            "last_seen": host_data.get('last_seen'),
            "wol_enabled": host_data.get('wol_enabled', False)
        }
        
        logger.info("Retrieved host status", ip=ip_address)
        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get host status", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve host status")

