"""
Redis client for WOLManager
"""

import json
from typing import Any, Dict, List, Optional
import redis.asyncio as redis
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)


class RedisClient:
    """Async Redis client wrapper"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
    
    async def ping(self):
        """Ping Redis server"""
        if not self.redis:
            await self.connect()
        return await self.redis.ping()
    
    async def set_host(self, host_data: Dict[str, Any]) -> bool:
        """Store host information"""
        try:
            host_key = f"host:{host_data['ip_address']}"
            
            # Convert None values to empty strings for Redis
            cleaned_data = {}
            for key, value in host_data.items():
                if value is None:
                    cleaned_data[key] = ""
                else:
                    cleaned_data[key] = str(value)
            
            logger.debug("Storing host data", ip=host_data['ip_address'], keys=list(cleaned_data.keys()))
            await self.redis.hset(host_key, mapping=cleaned_data)
            await self.redis.sadd("hosts", host_data['ip_address'])
            await self.redis.expire(host_key, 86400)  # 24 hours
            return True
        except Exception as e:
            logger.error("Failed to set host", error=str(e), host=host_data)
            return False
    
    async def get_host(self, ip_address: str) -> Optional[Dict[str, Any]]:
        """Get host information by IP"""
        try:
            host_key = f"host:{ip_address}"
            host_data = await self.redis.hgetall(host_key)
            
            logger.debug("Retrieved host data from Redis", ip=ip_address, keys=list(host_data.keys()))
            
            if not host_data:
                return None
            
            # Convert empty strings back to None for optional fields
            cleaned_data = {}
            optional_fields = {'hostname', 'vendor', 'device_type', 'os_info', 'notes', 'inferred_os', 'inferred_device_type'}
            
            for key, value in host_data.items():
                if key in optional_fields and value == "":
                    cleaned_data[key] = None
                elif key == 'wol_enabled':
                    # Convert string back to boolean
                    cleaned_data[key] = value.lower() == 'true'
                elif key == 'status':
                    # Handle status enum conversion
                    if value.startswith('HostStatus.'):
                        cleaned_data[key] = value.split('.', 1)[1].lower()
                    else:
                        cleaned_data[key] = value
                elif key == 'discovery_method':
                    # Handle discovery method enum conversion
                    if value.startswith('DiscoveryMethod.'):
                        cleaned_data[key] = value.split('.', 1)[1].lower()
                    else:
                        cleaned_data[key] = value
                elif key == 'inference_confidence':
                    # Convert string back to integer
                    try:
                        cleaned_data[key] = int(value) if value else None
                    except ValueError:
                        cleaned_data[key] = None
                else:
                    cleaned_data[key] = value
            
            return cleaned_data
        except Exception as e:
            logger.error("Failed to get host", error=str(e), ip=ip_address)
            return None
    
    async def get_all_hosts(self) -> List[Dict[str, Any]]:
        """Get all hosts"""
        try:
            hosts = []
            host_ips = await self.redis.smembers("hosts")
            logger.info("Retrieved host IPs from Redis", count=len(host_ips), ips=list(host_ips))
            
            for ip in host_ips:
                try:
                    host_data = await self.get_host(ip)
                    if host_data:
                        hosts.append(host_data)
                        logger.debug("Added host to list", ip=ip)
                    else:
                        logger.warning("No host data found", ip=ip)
                except Exception as e:
                    logger.error("Failed to get host data", ip=ip, error=str(e))
                    continue
            
            logger.info("Retrieved all hosts", count=len(hosts))
            return hosts
        except Exception as e:
            logger.error("Failed to get all hosts", error=str(e))
            return []
    
    async def delete_host(self, ip_address: str) -> bool:
        """Delete host information"""
        try:
            host_key = f"host:{ip_address}"
            await self.redis.delete(host_key)
            await self.redis.srem("hosts", ip_address)
            return True
        except Exception as e:
            logger.error("Failed to delete host", error=str(e), ip=ip_address)
            return False
    
    async def update_host(self, ip_address: str, updates: Dict[str, Any]) -> bool:
        """Update host information"""
        try:
            host_key = f"host:{ip_address}"
            
            # Convert None values to empty strings for Redis
            cleaned_updates = {}
            for key, value in updates.items():
                if value is None:
                    cleaned_updates[key] = ""
                else:
                    cleaned_updates[key] = str(value)
            
            await self.redis.hset(host_key, mapping=cleaned_updates)
            return True
        except Exception as e:
            logger.error("Failed to update host", error=str(e), ip=ip_address)
            return False
    
    async def merge_host_data(self, ip_address: str, new_host_data: Dict[str, Any]) -> bool:
        """Merge new host data with existing data using quality-aware logic"""
        try:
            host_key = f"host:{ip_address}"
            
            # Get existing host data
            existing_data = await self.redis.hgetall(host_key)
            
            if not existing_data:
                # No existing data, store new data directly
                return await self.set_host(new_host_data)
            
            # Convert existing data back to proper types
            existing_host = await self.get_host(ip_address)
            if not existing_host:
                return await self.set_host(new_host_data)
            
            # Import here to avoid circular imports
            from app.services.data_quality import DataQualityScorer
            from app.models.host import Host
            
            # Create Host objects for comparison
            existing_host_obj = Host(**existing_host)
            new_host_obj = Host(**new_host_data)
            
            # Score both hosts
            existing_score = DataQualityScorer.score_host(existing_host_obj)
            new_score = DataQualityScorer.score_host(new_host_obj)
            
            logger.debug("Host data merge comparison", 
                        ip=ip_address, 
                        existing_score=existing_score, 
                        new_score=new_score)
            
            if new_score > existing_score:
                # New data is better, store it
                logger.info("New host data is better quality", ip=ip_address, new_score=new_score)
                return await self.set_host(new_host_data)
            else:
                # Existing data is better or equal, but merge individual fields that might be better
                logger.debug("Existing host data is better quality", ip=ip_address, existing_score=existing_score)
                
                # Merge specific fields that might be better in new data
                merged_data = existing_host.copy()
                
                # Update status if new status is better
                if self._is_better_status(new_host_obj.status, existing_host_obj.status):
                    merged_data['status'] = new_host_obj.status
                    logger.debug("Updated status", ip=ip_address, new_status=new_host_obj.status)
                
                # Update last_seen if new data is more recent
                if new_host_data.get('last_seen') and (
                    not existing_host.get('last_seen') or 
                    new_host_data['last_seen'] > existing_host.get('last_seen')
                ):
                    merged_data['last_seen'] = new_host_data['last_seen']
                
                # Update inferred fields if they're missing in existing data
                if not existing_host.get('inferred_os') and new_host_obj.inferred_os:
                    merged_data['inferred_os'] = new_host_obj.inferred_os
                if not existing_host.get('inferred_device_type') and new_host_obj.inferred_device_type:
                    merged_data['inferred_device_type'] = new_host_obj.inferred_device_type
                if not existing_host.get('inference_confidence') and new_host_obj.inference_confidence:
                    merged_data['inference_confidence'] = new_host_obj.inference_confidence
                
                # Only update if there were changes
                if merged_data != existing_host:
                    return await self.set_host(merged_data)
                
                return True
                
        except Exception as e:
            logger.error("Failed to merge host data", error=str(e), ip=ip_address)
            return False
    
    def _is_better_status(self, new_status, current_status) -> bool:
        """Check if new status is better than current status"""
        # Status priority: online > unknown > offline
        status_priority = {
            'online': 3,
            'unknown': 2,
            'offline': 1
        }
        
        new_priority = status_priority.get(new_status, 0)
        current_priority = status_priority.get(current_status, 0)
        
        return new_priority > current_priority
    
    async def get_discovery_status(self) -> Dict[str, Any]:
        """Get discovery service status"""
        try:
            status = await self.redis.get("discovery:status")
            last_run = await self.redis.get("discovery:last_run")
            return {
                "status": status or "unknown",
                "last_run": last_run,
                "interval": settings.DISCOVERY_INTERVAL
            }
        except Exception as e:
            logger.error("Failed to get discovery status", error=str(e))
            return {"status": "error", "last_run": None, "interval": settings.DISCOVERY_INTERVAL}


# Global Redis client instance
redis_client = RedisClient()
