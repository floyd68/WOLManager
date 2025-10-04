"""
Enhanced DHCP lease analyzer for inferring OS, device, and vendor information
"""

import re
from typing import Optional, Dict, Any, Tuple
import structlog

logger = structlog.get_logger(__name__)


class DHCPAnalyzer:
    """Enhanced DHCP analyzer with comprehensive device detection"""
    
    # Enhanced OUI vendor mappings (sorted by OUI, deduplicated)
    OUI_VENDORS = {
        '000000': 'Xerox',
        '00000C': 'Cisco',
        '00014F': 'Dell',
        '000163': 'Apple',
        '0003FF': 'Microsoft',
        '000420': 'Intel',
        '00059A': 'HP',
        '000A95': 'Netgear',
        '000C29': 'VMware',
        '00155D': 'Microsoft Hyper-V',
        '00163E': 'Xen',
        '001A2B': 'TP-Link',
        '001B44': 'Cisco Systems',
        '001C14': 'VMware',
        '001C42': 'Parallels',
        '005056': 'VMware',
        '080027': 'Oracle VirtualBox',
        '0A0027': 'Oracle VirtualBox',
        '14DDA9': 'ASUSTek',
        '1488A9': 'ASUSTeK Computer',
        '1AC3AF': 'Apple',
        '525400': 'QEMU',
        '7085C2': 'Dell',
        '80CA4B': 'Xiaomi',
        'A8A159': 'LG Electronics',
        'D850E6': 'TP-Link',
        'D85ED3': 'Apple',
    }
    
    @classmethod
    def analyze_dhcp_lease(cls, lease_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced DHCP lease analysis using comprehensive detection strategy.
        """
        inferred_info = {
            "os": None,
            "device_type": None,
            "vendor": None,
            "confidence": 0
        }

        # Extract data
        mac_address = lease_data.get('mac_address', '').upper()
        hostname = lease_data.get('hostname', '') or ''
        os_info_str = lease_data.get('os_info', '') or ''
        
        # Parse additional fields from os_info string
        client_id = cls._extract_client_id(os_info_str)
        comment = cls._extract_comment(os_info_str)
        class_id = cls._extract_class_id(os_info_str)

        # Use enhanced detection
        device_type, os_detected, vendor = cls._enhanced_device_detection(
            hostname, client_id, comment, class_id, mac_address
        )
        
        inferred_info.update({
            "device_type": device_type,
            "os": os_detected,
            "vendor": vendor,
            "confidence": cls._calculate_confidence(hostname, client_id, comment, class_id, os_detected, vendor)
        })

        logger.debug("Enhanced DHCP analysis result", 
                    lease_data=lease_data, 
                    inferred_info=inferred_info)
        
        return inferred_info
    
    @classmethod
    def _enhanced_device_detection(cls, hostname: str, client_id: str, 
                                 comment: str, class_id: str, mac_address: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Enhanced device detection using RouterOS-specific information."""
        if not hostname:
            hostname = ""
        if not client_id:
            client_id = ""
        if not comment:
            comment = ""
        if not class_id:
            class_id = ""
        if not mac_address:
            mac_address = ""
        
        hostname_lower = hostname.lower()
        client_id_lower = client_id.lower()
        comment_lower = comment.lower()
        class_id_lower = class_id.lower()
        mac_lower = mac_address.lower()
        
        # Initialize return values
        device_type = "unknown_device"
        os_info = None
        vendor = None
        
        # Vendor Detection from MAC address (needed for OS detection)
        vendor = cls._detect_vendor_from_mac(mac_address)
        
        # OS Detection from Class ID and Client ID
        os_info = cls._detect_os_from_class_id(class_id)
        if not os_info:
            os_info = cls._detect_os_from_client_id(client_id, vendor)
        
        # Enhanced device type detection
        device_type = cls._determine_enhanced_device_type(
            hostname, client_id, comment, class_id, os_info
        )
        
        return device_type, os_info, vendor
    
    @classmethod
    def _detect_os_from_class_id(cls, class_id: str) -> Optional[str]:
        """Detect operating system from DHCP class ID."""
        if not class_id:
            return None
        
        class_id_lower = class_id.lower()
        
        # Windows detection
        if 'msft' in class_id_lower:
            if '5.0' in class_id_lower:
                return "Windows 2000"
            elif '6.0' in class_id_lower:
                return "Windows Vista/Server 2008"
            elif '6.1' in class_id_lower:
                return "Windows 7/Server 2008 R2"
            elif '6.2' in class_id_lower:
                return "Windows 8/Server 2012"
            elif '6.3' in class_id_lower:
                return "Windows 8.1/Server 2012 R2"
            elif '10.0' in class_id_lower:
                return "Windows 10/11/Server 2016+"
            else:
                return "Windows (Unknown Version)"
        
        # Android detection
        if 'android' in class_id_lower:
            if 'dhcp-13' in class_id_lower:
                return "Android 13+"
            elif 'dhcp-12' in class_id_lower:
                return "Android 12"
            elif 'dhcp-11' in class_id_lower:
                return "Android 11"
            elif 'dhcp-10' in class_id_lower:
                return "Android 10"
            else:
                return "Android (Unknown Version)"
        
        # iOS detection
        if 'iphone' in class_id_lower or 'ipad' in class_id_lower:
            return "iOS"
        
        # Linux detection
        if 'linux' in class_id_lower or 'ubuntu' in class_id_lower or 'debian' in class_id_lower:
            return "Linux"
        
        # RouterOS detection
        if 'routeros' in class_id_lower or 'mikrotik' in class_id_lower:
            return "RouterOS"
        
        # Generic DHCP clients
        if 'udhcp' in class_id_lower:
            return "Linux (udhcp client)"
        
        # Custom class IDs
        if 'lguap' in class_id_lower:
            return "LG U+ AP (Custom)"
        
        return None
    
    @classmethod
    def _detect_os_from_client_id(cls, client_id: str, vendor: str = None) -> Optional[str]:
        """Detect operating system from DHCP Client ID patterns."""
        if not client_id:
            return None
        
        client_id_lower = client_id.lower()
        
        # Windows Client ID pattern: "1:XX:XX:XX:XX:XX:X" (MAC address format, last byte can be 1 or 2 hex digits)
        if re.match(r'^1:([0-9a-f]{2}:){5}[0-9a-f]{1,2}$', client_id):
            # Check vendor to avoid false positives
            if vendor:
                vendor_lower = vendor.lower()
                if 'apple' in vendor_lower:
                    return "macOS"  # Apple devices using standard DHCP
                elif 'intel' in vendor_lower or 'dell' in vendor_lower or 'hp' in vendor_lower:
                    return "Windows"  # Common Windows vendors
                elif 'xiaomi' in vendor_lower:
                    return "Android"  # Xiaomi devices are typically Android
            # Default to Windows for standard DHCP client ID format
            return "Windows"
        
        # Windows Client ID pattern: "MSFT 5.0", "MSFT 6.0", etc.
        if re.match(r'^msft \d+\.\d+', client_id_lower):
            return "Windows"
        
        # Android Client ID patterns
        if 'android' in client_id_lower or 'dhcp-1' in client_id_lower:
            return "Android"
        
        # iOS Client ID patterns
        if 'iphone' in client_id_lower or 'ipad' in client_id_lower:
            return "iOS"
        
        # Linux Client ID patterns
        if 'dhcpcd' in client_id_lower or 'udhcp' in client_id_lower or 'isc-dhclient' in client_id_lower:
            return "Linux"
        
        return None
    
    @classmethod
    def _detect_vendor_from_mac(cls, mac_address: str) -> Optional[str]:
        """Detect vendor from MAC address OUI."""
        if not mac_address or len(mac_address) < 8:
            return None
        
        # Extract OUI (first 3 bytes)
        try:
            # Split by colon and take first 3 parts, then join without separators
            mac_parts = mac_address.split(':')
            if len(mac_parts) >= 3:
                oui = ''.join(mac_parts[:3]).upper()
            else:
                return None
        except:
            return None
        
        return cls.OUI_VENDORS.get(oui)
    
    @classmethod
    def _determine_enhanced_device_type(cls, hostname: str, client_id: str, 
                                      comment: str, class_id: str, os_info: Optional[str]) -> str:
        """Enhanced device type determination using all available information."""
        hostname_lower = hostname.lower()
        client_id_lower = client_id.lower()
        comment_lower = comment.lower()
        class_id_lower = class_id.lower()
        
        # Router/Network equipment
        if any(keyword in hostname_lower for keyword in ['router', 'gateway', 'switch', 'ap-', 'access-point', 'rt-', 'ac3200']):
            return "network_device"
        
        # Mobile devices
        if any(keyword in hostname_lower for keyword in ['iphone', 'ipad', 'android', 'mobile', 'phone', 'tablet']):
            return "mobile_device"
        
        # Computers/Laptops
        if any(keyword in hostname_lower for keyword in ['pc', 'laptop', 'desktop', 'computer', 'workstation', 'right-computer']):
            return "computer"
        
        # Servers
        if any(keyword in hostname_lower for keyword in ['server', 'srv', 'nas', 'backup']):
            return "server"
        
        # IoT/Smart devices
        if any(keyword in hostname_lower for keyword in ['iot', 'smart', 'sensor', 'camera', 'doorbell']):
            return "iot_device"
        
        # Gaming devices
        if any(keyword in hostname_lower for keyword in ['ps4', 'ps5', 'xbox', 'nintendo', 'gaming']):
            return "gaming_device"
        
        # Check client ID patterns
        if 'android' in client_id_lower:
            return "mobile_device"
        if 'iphone' in client_id_lower or 'ipad' in client_id_lower:
            return "mobile_device"
        
        # Check comment patterns
        if any(keyword in comment_lower for keyword in ['printer', 'print']):
            return "printer"
        if any(keyword in comment_lower for keyword in ['tv', 'television', 'smart-tv']):
            return "media_device"
        
        # Check class ID patterns
        if 'msft' in class_id_lower:
            return "computer"
        if 'android' in class_id_lower:
            return "mobile_device"
        if 'iphone' in class_id_lower or 'ipad' in class_id_lower:
            return "mobile_device"
        
        # Check OS info
        if os_info and 'windows' in os_info.lower():
            return "computer"
        if os_info and 'android' in os_info.lower():
            return "mobile_device"
        if os_info and 'ios' in os_info.lower():
            return "mobile_device"
        if os_info and 'linux' in os_info.lower():
            return "computer"
        
        # Default based on naming patterns
        if hostname_lower.startswith(('win-', 'desktop-', 'laptop-')):
            return "computer"
        if hostname_lower.startswith(('android-', 'iphone-', 'ipad-')):
            return "mobile_device"
        
        return "dhcp_client"
    
    @classmethod
    def _extract_client_id(cls, os_info: str) -> str:
        """Extract client ID from OS info string."""
        if not os_info:
            return ""
        
        # Look for Client-ID pattern
        client_id_match = re.search(r'Client-ID:\s*([^;]+)', os_info, re.IGNORECASE)
        if client_id_match:
            return client_id_match.group(1).strip()
        
        return ""
    
    @classmethod
    def _extract_comment(cls, os_info: str) -> str:
        """Extract comment from OS info string."""
        if not os_info:
            return ""
        
        # Look for Comment pattern
        comment_match = re.search(r'Comment:\s*([^;]+)', os_info, re.IGNORECASE)
        if comment_match:
            return comment_match.group(1).strip()
        
        return ""
    
    @classmethod
    def _extract_class_id(cls, os_info: str) -> str:
        """Extract class ID from OS info string."""
        if not os_info:
            return ""
        
        # Look for Class-ID pattern
        class_id_match = re.search(r'Class-ID:\s*([^;]+)', os_info, re.IGNORECASE)
        if class_id_match:
            return class_id_match.group(1).strip()
        
        return ""
    
    @classmethod
    def _calculate_confidence(cls, hostname: str, client_id: str, comment: str, 
                            class_id: str, os_detected: Optional[str], vendor: Optional[str]) -> int:
        """Calculate confidence score for the detection."""
        confidence = 0
        
        # Base confidence for having data
        if hostname:
            confidence += 10
        if client_id:
            confidence += 20
        if comment:
            confidence += 15
        if class_id:
            confidence += 25
        
        # Bonus for OS detection
        if os_detected:
            confidence += 30
        
        # Bonus for vendor detection
        if vendor:
            confidence += 20
        
        # Bonus for specific patterns
        if any(keyword in hostname.lower() for keyword in ['router', 'gateway', 'switch', 'ap-']):
            confidence += 15
        if any(keyword in hostname.lower() for keyword in ['iphone', 'ipad', 'android']):
            confidence += 15
        if any(keyword in hostname.lower() for keyword in ['pc', 'laptop', 'desktop']):
            confidence += 15
        
        return min(confidence, 100)