# WOLManager

A Modern and fancy web service for scanning and storing local network host information and sending WOL broadcasts using Python FastAPI.

## Features

- **Multiple Discovery Methods**: Supports RouterOS API(librouteros), RouterOS RestAPI, SNMP, NetBIOS/SMB, mDNS/zeroconf, ARP
- **Priority-based Discovery**: Tries discovery methods in order of reliability and speed
- **Redis/Valkey Storage**: Fast and reliable storage for host information
- **Modern Web UI**: Beautiful dashboard with real-time updates and interactive charts, White & Gray based 4 color schemes
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

## Installation

### Prerequisites

- Python 3.8+
- Redis or Valkey server
- Network access to your local network

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd WOLManager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure the application:
```bash
cp env.example .env
# Edit .env with your configuration
```

4. Start Redis (if not already running):
```bash
# Ubuntu/Debian
sudo systemctl start redis-server

# macOS with Homebrew
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

5. Run the application:
```bash
python -m app.main
```

The application will be available at `http://localhost:8000`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DEBUG` | Debug mode | `false` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `REDIS_PASSWORD` | Redis password | - |
| `DISCOVERY_INTERVAL` | Discovery interval in seconds | `300` |
| `NETWORK_RANGE` | Network range to scan | `192.168.1.0/24` |
| `ROUTEROS_HOST` | RouterOS host IP | - |
| `ROUTEROS_USERNAME` | RouterOS username | - |
| `ROUTEROS_PASSWORD` | RouterOS password | - |
| `ROUTEROS_PORT` | RouterOS API port | `8728` |
| `SNMP_COMMUNITY` | SNMP community string | `public` |
| `SNMP_TIMEOUT` | SNMP timeout in seconds | `5` |
| `WOL_BROADCAST_ADDRESS` | WOL broadcast address | `192.168.1.255` |
| `WOL_PORT` | WOL port | `9` |
| `SECRET_KEY` | Secret key for security | - |

### RouterOS Configuration

To use RouterOS discovery methods, configure the following in your `.env` file:

```env
ROUTEROS_HOST=192.168.1.1
ROUTEROS_USERNAME=admin
ROUTEROS_PASSWORD=your_password
ROUTEROS_PORT=8728
```

### SNMP Configuration

For SNMP discovery, ensure your network devices have SNMP enabled:

```env
SNMP_COMMUNITY=public
SNMP_TIMEOUT=5
```

## Usage

### Web Interface

1. Open your browser and navigate to `http://localhost:8000`
2. Use the dashboard to:
   - View discovered hosts
   - Start/stop discovery service
   - Send Wake-on-LAN packets
   - Manage host information
   - View statistics and charts

### API Endpoints

#### Hosts
- `GET /api/v1/hosts` - Get all hosts
- `GET /api/v1/hosts/{ip}` - Get specific host
- `POST /api/v1/hosts` - Create new host
- `PUT /api/v1/hosts/{ip}` - Update host
- `DELETE /api/v1/hosts/{ip}` - Delete host

#### Wake-on-LAN
- `POST /api/v1/wol/wake` - Send WOL packet
- `POST /api/v1/wol/wake/{ip}` - Wake host by IP
- `POST /api/v1/wol/wake/mac/{mac}` - Wake host by MAC
- `GET /api/v1/wol/wakeable` - Get wakeable hosts

#### Discovery
- `POST /api/v1/discovery/start` - Start discovery service
- `POST /api/v1/discovery/stop` - Stop discovery service
- `POST /api/v1/discovery/run` - Force discovery run
- `GET /api/v1/discovery/status` - Get discovery status
- `GET /api/v1/discovery/statistics` - Get discovery statistics

### Example API Usage

```bash
# Get all hosts
curl http://localhost:8000/api/v1/hosts

# Wake a host
curl -X POST http://localhost:8000/api/v1/wol/wake/192.168.1.100

# Start discovery
curl -X POST http://localhost:8000/api/v1/discovery/start
```

## Development

### Project Structure

```
WOLManager/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── core/
│   │   ├── config.py          # Configuration settings
│   │   └── redis_client.py    # Redis client wrapper
│   ├── models/
│   │   └── host.py            # Pydantic models
│   ├── services/
│   │   ├── discovery_service.py      # Main discovery service
│   │   ├── wol_service.py           # Wake-on-LAN service
│   │   └── discovery_methods/        # Individual discovery methods
│   ├── api/
│   │   └── api_v1/
│   │       ├── api.py         # API router
│   │       └── endpoints/     # API endpoints
│   ├── templates/
│   │   └── index.html         # Web UI template
│   └── static/
│       └── js/
│           └── app.js         # Frontend JavaScript
├── requirements.txt           # Python dependencies
├── env.example               # Environment configuration example
└── README.md                 # This file
```

### Running in Development Mode

```bash
# Install development dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Support

### Build and Run

```bash
# Build the image
docker build -t wolmanager .

# Run with Redis
docker-compose up -d
```

### Docker Compose

```yaml
version: '3.8'
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
  
  wolmanager:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
```

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   - Ensure Redis is running
   - Check Redis URL in configuration
   - Verify network connectivity

2. **Discovery Not Working**
   - Check network range configuration
   - Verify RouterOS credentials (if using)
   - Ensure SNMP is enabled on network devices
   - Check firewall settings

3. **WOL Not Working**
   - Verify MAC addresses are correct
   - Check if hosts support Wake-on-LAN
   - Ensure WOL is enabled in BIOS
   - Check network configuration

### Logs

The application uses structured logging. Check the console output for detailed error messages.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the documentation
- Review the troubleshooting section


