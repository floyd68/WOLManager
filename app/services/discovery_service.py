"""
Network discovery service for WOLManager
"""

import asyncio
import ipaddress
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.host import Host, DiscoveryMethod, HostStatus
from app.services.discovery_methods import (
    RouterOSAPIDiscovery,
    RouterOSRestDiscovery,
    SNMPDiscovery,
    NetBIOSDiscovery,
    mDNSDiscovery,
    ARPDiscovery
)
from app.services.data_quality import HostMerger, DataQualityScorer

logger = structlog.get_logger(__name__)


class DiscoveryService:
    """Main discovery service that orchestrates all discovery methods"""
    
    def __init__(self):
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.discovery_methods = [
            RouterOSAPIDiscovery(),
            RouterOSRestDiscovery(),
            SNMPDiscovery(),
            NetBIOSDiscovery(),
            mDNSDiscovery(),
            ARPDiscovery()
        ]
    
    async def start(self):
        """Start the discovery service"""
        if self.running:
            logger.warning("Discovery service is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._discovery_loop())
        logger.info("Discovery service started")
    
    async def stop(self):
        """Stop the discovery service"""
        if not self.running:
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Discovery service stopped")
    
    async def _discovery_loop(self):
        """Main discovery loop"""
        while self.running:
            try:
                await self.run_discovery()
                
                # Update Redis status if connected
                if redis_client.redis:
                    await redis_client.redis.set("discovery:status", "running")
                    await redis_client.redis.set("discovery:last_run", datetime.now().isoformat())
                else:
                    logger.warning("Redis not connected - skipping status update")
                
                # Wait for next interval
                await asyncio.sleep(settings.DISCOVERY_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in discovery loop", error=str(e))
                if redis_client.redis:
                    await redis_client.redis.set("discovery:status", f"error: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def run_discovery(self) -> List[Host]:
        """Run discovery using all available methods"""
        logger.info("Starting network discovery")
        discovered_hosts = []
        
        # Get network range
        try:
            network = ipaddress.ip_network(settings.NETWORK_RANGE, strict=False)
        except ValueError as e:
            logger.error("Invalid network range", error=str(e), range=settings.NETWORK_RANGE)
            return discovered_hosts
        
        # Try each discovery method in priority order
        # Stop early if high-priority methods find sufficient hosts (if enabled)
        high_priority_threshold = settings.DISCOVERY_MIN_HOSTS_THRESHOLD
        high_priority_hosts = 0
        
        for method in self.discovery_methods:
            try:
                logger.info("Running discovery method", method=method.__class__.__name__)
                hosts = await method.discover(network)
                
                for host in hosts:
                    discovered_hosts.append(host)
                
                # Check if this is a high-priority method (RouterOS API or REST)
                if method.__class__.__name__ in ['RouterOSAPIDiscovery', 'RouterOSRestDiscovery']:
                    high_priority_hosts += len(hosts)
                
                logger.info("Discovery method completed", 
                           method=method.__class__.__name__, 
                           hosts_found=len(hosts))
                
                # Early termination: if we have enough high-priority hosts and total hosts
                if (settings.DISCOVERY_EARLY_TERMINATION and
                    high_priority_hosts >= high_priority_threshold and 
                    len(discovered_hosts) >= high_priority_threshold):
                    logger.info("Early termination: sufficient high-priority hosts found",
                               high_priority_hosts=high_priority_hosts,
                               total_hosts=len(discovered_hosts),
                               threshold=high_priority_threshold)
                    break
                
            except Exception as e:
                logger.error("Discovery method failed", 
                           method=method.__class__.__name__, 
                           error=str(e))
                continue
        
        # Merge hosts with quality-aware logic
        if discovered_hosts:
            logger.info("Merging discovered hosts", total_before_merge=len(discovered_hosts))
            discovered_hosts = HostMerger.merge_hosts(discovered_hosts)
            logger.info("Host merge completed", total_after_merge=len(discovered_hosts))
        
        # Store merged hosts
        for host in discovered_hosts:
            await self._store_host(host)
        
        logger.info("Network discovery completed", total_hosts=len(discovered_hosts))
        return discovered_hosts
    
    async def discover_single_host(self, ip_address: str) -> Optional[Host]:
        """Discover a single host using all methods with quality-aware merge"""
        try:
            ip_obj = ipaddress.ip_address(ip_address)
            network = ipaddress.ip_network(f"{ip_obj}/32", strict=False)
        except ValueError:
            logger.error("Invalid IP address", ip=ip_address)
            return None
        
        discovered_hosts = []
        
        for method in self.discovery_methods:
            try:
                hosts = await method.discover(network)
                discovered_hosts.extend(hosts)
            except Exception as e:
                logger.error("Single host discovery failed", 
                           method=method.__class__.__name__, 
                           ip=ip_address, 
                           error=str(e))
                continue
        
        if discovered_hosts:
            # Merge hosts with quality-aware logic
            merged_hosts = HostMerger.merge_hosts(discovered_hosts)
            if merged_hosts:
                best_host = merged_hosts[0]
                await self._store_host(best_host)
                return best_host
        
        return None
    
    async def _store_host(self, host: Host):
        """Store host information in Redis with quality-aware merge"""
        try:
            # Check if Redis is connected
            if not redis_client.redis:
                logger.warning("Redis not connected - skipping host storage", ip=host.ip_address)
                return
                
            host_data = host.dict()
            host_data["last_seen"] = datetime.now().isoformat()
            
            # Use quality-aware merge instead of direct storage
            success = await redis_client.merge_host_data(host.ip_address, host_data)
            
            if success:
                logger.debug("Host stored/merged", ip=host.ip_address, method=host.discovery_method)
            else:
                logger.warning("Failed to store/merge host", ip=host.ip_address, method=host.discovery_method)
        except Exception as e:
            logger.error("Failed to store host", ip=host.ip_address, error=str(e))
    
    async def get_discovery_status(self) -> Dict[str, Any]:
        """Get discovery service status"""
        return await redis_client.get_discovery_status()
    
    async def force_discovery(self) -> List[Host]:
        """Force an immediate discovery run"""
        logger.info("Forcing immediate discovery")
        return await self.run_discovery()

