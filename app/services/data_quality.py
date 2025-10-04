"""
Data quality scoring and merge logic for host information
"""

from typing import Dict, Any, Optional, List
from app.models.host import Host, DiscoveryMethod
import structlog

logger = structlog.get_logger(__name__)


class DataQualityScorer:
    """Scores host data quality based on discovery method and available information"""
    
    # Discovery method quality scores (higher = better)
    METHOD_SCORES = {
        DiscoveryMethod.ROUTEROS_API: 100,
        DiscoveryMethod.ROUTEROS_REST: 95,
        DiscoveryMethod.SNMP: 80,
        DiscoveryMethod.NETBIOS: 70,
        DiscoveryMethod.MDNS: 60,
        DiscoveryMethod.ARP: 50,
    }
    
    # Information completeness scores
    FIELD_SCORES = {
        'ip_address': 10,      # Always present, base score
        'mac_address': 20,     # Very important for WOL
        'hostname': 15,        # Very useful for identification
        'vendor': 10,          # Useful for device identification
        'device_type': 8,      # Useful for categorization
        'os_info': 12,         # Useful for detailed info
        'notes': 5,            # Nice to have
    }
    
    @classmethod
    def score_host(cls, host: Host) -> int:
        """Calculate quality score for a host"""
        score = 0
        
        # Base score from discovery method
        method_score = cls.METHOD_SCORES.get(host.discovery_method, 0)
        score += method_score
        
        # Bonus for information completeness
        for field, field_score in cls.FIELD_SCORES.items():
            value = getattr(host, field, None)
            if value is not None and value != "":
                score += field_score
        
        # Bonus for rich OS info
        if host.os_info and len(host.os_info) > 20:
            score += 5
        
        # Bonus for detailed device type
        if host.device_type and '_' in host.device_type:
            score += 3
        
        return score
    
    @classmethod
    def get_method_quality(cls, method: DiscoveryMethod) -> int:
        """Get base quality score for a discovery method"""
        return cls.METHOD_SCORES.get(method, 0)


class HostMerger:
    """Merges host information from multiple discovery methods with quality awareness"""
    
    @classmethod
    def merge_hosts(cls, hosts: List[Host]) -> List[Host]:
        """Merge multiple host entries for the same IP address"""
        if not hosts:
            return hosts
        
        # Group hosts by IP address
        ip_groups = {}
        for host in hosts:
            ip = host.ip_address
            if ip not in ip_groups:
                ip_groups[ip] = []
            ip_groups[ip].append(host)
        
        merged_hosts = []
        
        # Merge each IP group
        for ip, host_list in ip_groups.items():
            if len(host_list) == 1:
                merged_hosts.append(host_list[0])
            else:
                merged_host = cls._merge_host_group(host_list)
                merged_hosts.append(merged_host)
        
        return merged_hosts
    
    @classmethod
    def _merge_host_group(cls, hosts: List[Host]) -> Host:
        """Merge a group of hosts with the same IP address"""
        if len(hosts) == 1:
            return hosts[0]
        
        # Sort by quality score (highest first)
        scored_hosts = [(DataQualityScorer.score_host(host), host) for host in hosts]
        scored_hosts.sort(key=lambda x: x[0], reverse=True)
        
        # Use the highest quality host as base
        best_host = scored_hosts[0][1]
        logger.debug("Merging hosts", ip=best_host.ip_address, count=len(hosts), 
                    best_method=best_host.discovery_method, best_score=scored_hosts[0][0])
        
        # Create merged host
        merged_data = {
            'ip_address': best_host.ip_address,
            'mac_address': best_host.mac_address,
            'hostname': best_host.hostname,
            'vendor': best_host.vendor,
            'device_type': best_host.device_type,
            'os_info': best_host.os_info,
            'discovery_method': best_host.discovery_method,
            'status': best_host.status,
            'last_seen': best_host.last_seen,
            'wol_enabled': best_host.wol_enabled,
            'notes': best_host.notes,
            'inferred_os': best_host.inferred_os,
            'inferred_device_type': best_host.inferred_device_type,
            'inference_confidence': best_host.inference_confidence
        }
        
        # Merge information from other hosts if it's better
        for score, host in scored_hosts[1:]:
            merged_data = cls._merge_host_data(merged_data, host)
        
        # Create final merged host
        merged_host = Host(**merged_data)
        
        # Log the merge result
        logger.info("Host merged", 
                   ip=merged_host.ip_address,
                   final_method=merged_host.discovery_method,
                   final_score=DataQualityScorer.score_host(merged_host),
                   sources=len(hosts))
        
        return merged_host
    
    @classmethod
    def _merge_host_data(cls, base_data: Dict[str, Any], other_host: Host) -> Dict[str, Any]:
        """Merge data from another host into base data"""
        merged = base_data.copy()
        
        # Merge MAC address (prefer non-null)
        if not merged['mac_address'] and other_host.mac_address:
            merged['mac_address'] = other_host.mac_address
        
        # Merge hostname (prefer non-empty, longer names)
        if not merged['hostname'] or (other_host.hostname and len(other_host.hostname) > len(merged['hostname'] or '')):
            merged['hostname'] = other_host.hostname
        
        # Merge vendor (prefer non-null)
        if not merged['vendor'] and other_host.vendor:
            merged['vendor'] = other_host.vendor
        
        # Merge device type (prefer more specific)
        if not merged['device_type'] or cls._is_more_specific_device_type(other_host.device_type, merged['device_type']):
            merged['device_type'] = other_host.device_type
        
        # Merge OS info (prefer longer, more detailed)
        if not merged['os_info'] or (other_host.os_info and len(other_host.os_info) > len(merged['os_info'] or '')):
            merged['os_info'] = other_host.os_info
        
        # Merge notes (prefer non-null)
        if not merged['notes'] and other_host.notes:
            merged['notes'] = other_host.notes
        
        # Merge discovery method (keep the best one)
        if DataQualityScorer.get_method_quality(other_host.discovery_method) > DataQualityScorer.get_method_quality(base_data['discovery_method']):
            merged['discovery_method'] = other_host.discovery_method
        
        # Merge status (prefer online > unknown > offline)
        if cls._is_better_status(other_host.status, merged['status']):
            merged['status'] = other_host.status
        
        # Merge inferred fields (prefer non-null)
        if not merged.get('inferred_os') and other_host.inferred_os:
            merged['inferred_os'] = other_host.inferred_os
        if not merged.get('inferred_device_type') and other_host.inferred_device_type:
            merged['inferred_device_type'] = other_host.inferred_device_type
        if not merged.get('inference_confidence') and other_host.inference_confidence:
            merged['inference_confidence'] = other_host.inference_confidence
        
        return merged
    
    @classmethod
    def _is_more_specific_device_type(cls, new_type: Optional[str], current_type: Optional[str]) -> bool:
        """Check if new device type is more specific than current"""
        if not new_type:
            return False
        if not current_type:
            return True
        
        # More specific if it has more parts (separated by _)
        new_parts = new_type.split('_')
        current_parts = current_type.split('_')
        
        if len(new_parts) > len(current_parts):
            return True
        
        # Prefer certain prefixes
        preferred_prefixes = ['dhcp_lease', 'arp_entry', 'snmp', 'netbios']
        for prefix in preferred_prefixes:
            if new_type.startswith(prefix) and not current_type.startswith(prefix):
                return True
        
        return False
    
    @classmethod
    def _is_better_status(cls, new_status, current_status) -> bool:
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
