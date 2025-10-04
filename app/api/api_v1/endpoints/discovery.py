"""
Network discovery API endpoints
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
import structlog

from app.models.host import HostResponse
from app.services.discovery_service import DiscoveryService
from app.core.redis_client import redis_client

logger = structlog.get_logger(__name__)
router = APIRouter()

# Initialize discovery service
discovery_service = DiscoveryService()


@router.post("/start")
async def start_discovery(background_tasks: BackgroundTasks):
    """Start the discovery service"""
    try:
        await discovery_service.start()
        
        logger.info("Discovery service started")
        return {"message": "Discovery service started successfully"}
        
    except Exception as e:
        logger.error("Failed to start discovery service", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to start discovery service")


@router.post("/stop")
async def stop_discovery():
    """Stop the discovery service"""
    try:
        await discovery_service.stop()
        
        logger.info("Discovery service stopped")
        return {"message": "Discovery service stopped successfully"}
        
    except Exception as e:
        logger.error("Failed to stop discovery service", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to stop discovery service")


@router.post("/run", response_model=List[HostResponse])
async def run_discovery():
    """Force an immediate discovery run"""
    try:
        hosts = await discovery_service.force_discovery()
        
        # Convert to HostResponse objects
        host_responses = [HostResponse(**host.dict()) for host in hosts]
        
        logger.info("Discovery run completed", hosts_found=len(host_responses))
        
        return host_responses
        
    except Exception as e:
        logger.error("Discovery run failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to run discovery")


@router.get("/status")
async def get_discovery_status():
    """Get discovery service status"""
    try:
        status = await discovery_service.get_discovery_status()
        
        logger.info("Retrieved discovery status")
        return status
        
    except Exception as e:
        logger.error("Failed to get discovery status", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve discovery status")


@router.post("/discover/{ip_address}", response_model=HostResponse)
async def discover_single_host(ip_address: str):
    """Discover a single host"""
    try:
        host = await discovery_service.discover_single_host(ip_address)
        
        if not host:
            raise HTTPException(status_code=404, detail="Host not found or not discoverable")
        
        host_response = HostResponse(**host.dict())
        
        logger.info("Single host discovery completed", ip=ip_address)
        return host_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Single host discovery failed", 
                    ip=ip_address, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Failed to discover host")


@router.get("/methods")
async def get_discovery_methods():
    """Get available discovery methods and their status"""
    try:
        methods = []
        
        for method in discovery_service.discovery_methods:
            method_info = {
                "name": method.__class__.__name__,
                "type": method.method.value,
                "description": method.__class__.__doc__ or "No description available"
            }
            
            # Check if method is configured
            if hasattr(method, 'host') and method.host:
                method_info["configured"] = True
            elif hasattr(method, 'community') and method.community:
                method_info["configured"] = True
            else:
                method_info["configured"] = True  # Most methods don't require configuration
        
            methods.append(method_info)
        
        logger.info("Retrieved discovery methods", count=len(methods))
        return {"methods": methods}
        
    except Exception as e:
        logger.error("Failed to get discovery methods", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve discovery methods")


@router.get("/statistics")
async def get_discovery_statistics():
    """Get discovery statistics"""
    try:
        hosts = await redis_client.get_all_hosts()
        
        # Calculate statistics
        total_hosts = len(hosts)
        
        # Group by discovery method
        method_counts = {}
        for host in hosts:
            method = host.get('discovery_method', 'unknown')
            method_counts[method] = method_counts.get(method, 0) + 1
        
        # Group by status
        status_counts = {}
        for host in hosts:
            status = host.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Group by device type
        device_type_counts = {}
        for host in hosts:
            device_type = host.get('device_type', 'unknown')
            device_type_counts[device_type] = device_type_counts.get(device_type, 0) + 1
        
        statistics = {
            "total_hosts": total_hosts,
            "by_discovery_method": method_counts,
            "by_status": status_counts,
            "by_device_type": device_type_counts
        }
        
        logger.info("Retrieved discovery statistics")
        return statistics
        
    except Exception as e:
        logger.error("Failed to get discovery statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve discovery statistics")


