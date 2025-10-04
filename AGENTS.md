# WOLManager

A Modern and fancy web service for scanning and store local network host information and send WOL broadcast using Pythoin FastAPI.

## Features
- **Multiple Discovery Methods**: Supports RouterOS API(librouteros), RouterOS RestAPI, SNMP, NetBIOS/SMB, mDNS/zeroconf, ARP
- **Priority-based Discovery**: Tries discovery methods in order of reliability and speed
- **Redis/Valkey Storage**: Fast and reliable storage for host information
- **Modern Web UI**: Beautiful dashboard with real-time updates and interactive charts, White & Gray based 4colorschemes
- **RESTful API**: Complete API for integration with other tools
- **Background Discovery**: Automatic periodic network scanning
- **Host Management**: Update, delete, and manage host information for WOL Broadcast

## Discovery Methods (in priority order)

1. **RouterOS API**: Direct integration with Mikrotik routers for comprehensive host information via librouteros
2. **RouterOS RestAPI**: Direct integration with Mikrotik routers for comprehensive host information
3. **SNMP**: Network device discovery using SNMP protocol
4. **NetBIOS/SMB**: Windows and SMB-based host discovery
5. **mDNS/zeroconf**: Bonjour/Avahi service discovery
6. **ARP**: Address Resolution Protocol table scanning