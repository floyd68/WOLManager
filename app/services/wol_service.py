"""
Wake-on-LAN service for WOLManager
"""

import socket
import struct
from typing import Optional, Dict, Any
import structlog

from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.host import WOLRequest, WOLResponse

logger = structlog.get_logger(__name__)


class WOLService:
    """Wake-on-LAN service"""
    
    def __init__(self):
        self.broadcast_address = settings.WOL_BROADCAST_ADDRESS
        self.port = settings.WOL_PORT
    
    async def send_wol_packet(self, request: WOLRequest) -> WOLResponse:
        """Send Wake-on-LAN packet to wake a host"""
        try:
            # Get MAC address from request or lookup from database
            mac_address = request.mac_address
            
            if not mac_address:
                # Try to get MAC address from stored host data
                host_data = await redis_client.get_host(request.ip_address)
                if host_data and host_data.get('mac_address'):
                    mac_address = host_data['mac_address']
                else:
                    return WOLResponse(
                        success=False,
                        message="MAC address not provided and not found in database",
                        ip_address=request.ip_address,
                        mac_address=None
                    )
            
            # Validate MAC address format
            if not self._is_valid_mac(mac_address):
                return WOLResponse(
                    success=False,
                    message="Invalid MAC address format",
                    ip_address=request.ip_address,
                    mac_address=mac_address
                )
            
            # Create and send WOL packet
            success = await self._send_wol_packet(
                mac_address, 
                request.broadcast_address or self.broadcast_address
            )
            
            if success:
                logger.info("WOL packet sent successfully", 
                           ip=request.ip_address, 
                           mac=mac_address)
                return WOLResponse(
                    success=True,
                    message="Wake-on-LAN packet sent successfully",
                    ip_address=request.ip_address,
                    mac_address=mac_address
                )
            else:
                return WOLResponse(
                    success=False,
                    message="Failed to send Wake-on-LAN packet",
                    ip_address=request.ip_address,
                    mac_address=mac_address
                )
                
        except Exception as e:
            logger.error("WOL packet send failed", 
                        ip=request.ip_address, 
                        error=str(e))
            return WOLResponse(
                success=False,
                message=f"Error sending Wake-on-LAN packet: {str(e)}",
                ip_address=request.ip_address,
                mac_address=request.mac_address
            )
    
    async def _send_wol_packet(self, mac_address: str, broadcast_address: str) -> bool:
        """Send the actual WOL packet"""
        try:
            # Convert MAC address to bytes
            mac_bytes = self._mac_to_bytes(mac_address)
            
            # Create WOL packet: 6 bytes of 0xFF + 16 repetitions of MAC address
            wol_packet = b'\xff' * 6 + mac_bytes * 16
            
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            try:
                # Send packet
                sock.sendto(wol_packet, (broadcast_address, self.port))
                return True
            finally:
                sock.close()
                
        except Exception as e:
            logger.error("WOL packet creation/send failed", 
                        mac=mac_address, 
                        broadcast=broadcast_address, 
                        error=str(e))
            return False
    
    def _mac_to_bytes(self, mac_address: str) -> bytes:
        """Convert MAC address string to bytes"""
        # Remove separators and convert to bytes
        mac_clean = mac_address.replace(':', '').replace('-', '')
        return bytes.fromhex(mac_clean)
    
    def _is_valid_mac(self, mac_address: str) -> bool:
        """Validate MAC address format"""
        import re
        
        # Allow various MAC address formats
        patterns = [
            r'^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}$',
            r'^[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}$',
            r'^[0-9a-fA-F]{12}$'
        ]
        
        return any(re.match(pattern, mac_address) for pattern in patterns)
    
    async def wake_host(self, ip_address: str, mac_address: Optional[str] = None) -> WOLResponse:
        """Convenience method to wake a host by IP"""
        request = WOLRequest(
            ip_address=ip_address,
            mac_address=mac_address
        )
        return await self.send_wol_packet(request)
    
    async def wake_host_by_mac(self, mac_address: str, broadcast_address: Optional[str] = None) -> WOLResponse:
        """Convenience method to wake a host by MAC address only"""
        request = WOLRequest(
            ip_address="unknown",  # Not needed for MAC-only wake
            mac_address=mac_address,
            broadcast_address=broadcast_address
        )
        return await self.send_wol_packet(request)


