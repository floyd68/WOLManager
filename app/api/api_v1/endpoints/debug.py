"""
Debug API endpoints for development and testing
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import structlog

from app.core.redis_client import redis_client
from app.services.data_quality import DataQualityScorer
from app.models.host import Host

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/hosts/quality-scores")
async def get_host_quality_scores():
    """Get quality scores for all hosts"""
    try:
        hosts = await redis_client.get_all_hosts()
        
        scored_hosts = []
        for host_data in hosts:
            try:
                host = Host(**host_data)
                score = DataQualityScorer.score_host(host)
                
                scored_hosts.append({
                    "ip_address": host.ip_address,
                    "discovery_method": host.discovery_method,
                    "device_type": host.device_type,
                    "quality_score": score,
                    "has_mac": bool(host.mac_address),
                    "has_hostname": bool(host.hostname),
                    "has_vendor": bool(host.vendor),
                    "has_os_info": bool(host.os_info),
                    "os_info_length": len(host.os_info) if host.os_info else 0
                })
            except Exception as e:
                logger.error("Failed to score host", ip=host_data.get('ip_address'), error=str(e))
                continue
        
        # Sort by quality score (highest first)
        scored_hosts.sort(key=lambda x: x['quality_score'], reverse=True)
        
        return {
            "hosts": scored_hosts,
            "total_hosts": len(scored_hosts),
            "average_score": sum(h['quality_score'] for h in scored_hosts) / len(scored_hosts) if scored_hosts else 0
        }
        
    except Exception as e:
        logger.error("Failed to get host quality scores", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get host quality scores")


@router.get("/hosts/{ip_address}/quality-score")
async def get_host_quality_score(ip_address: str):
    """Get quality score for a specific host"""
    try:
        host_data = await redis_client.get_host(ip_address)
        
        if not host_data:
            raise HTTPException(status_code=404, detail="Host not found")
        
        host = Host(**host_data)
        score = DataQualityScorer.score_host(host)
        
        # Get method quality score
        method_score = DataQualityScorer.get_method_quality(host.discovery_method)
        
        return {
            "ip_address": host.ip_address,
            "discovery_method": host.discovery_method,
            "method_quality_score": method_score,
            "total_quality_score": score,
            "hostname": host.hostname,
            "mac_address": host.mac_address,
            "vendor": host.vendor,
            "device_type": host.device_type,
            "os_info": host.os_info,
            "has_mac": bool(host.mac_address),
            "has_hostname": bool(host.hostname),
            "has_vendor": bool(host.vendor),
            "has_os_info": bool(host.os_info),
            "os_info_length": len(host.os_info) if host.os_info else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get host quality score", ip=ip_address, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get host quality score")


@router.get("/discovery-methods/quality-scores")
async def get_discovery_method_quality_scores():
    """Get quality scores for all discovery methods"""
    try:
        methods = []
        for method, score in DataQualityScorer.METHOD_SCORES.items():
            methods.append({
                "method": method.value,
                "quality_score": score
            })
        
        # Sort by quality score (highest first)
        methods.sort(key=lambda x: x['quality_score'], reverse=True)
        
        return {
            "methods": methods,
            "field_scores": DataQualityScorer.FIELD_SCORES
        }
        
    except Exception as e:
        logger.error("Failed to get discovery method quality scores", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get discovery method quality scores")

