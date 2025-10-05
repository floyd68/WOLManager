# Docker Troubleshooting Guide

## Redis Connection Issues

### Problem
When running WOLManager in Docker, you may encounter Redis connection errors:
```
Error 111 connecting to localhost:6379. Connection refused.
Failed to merge host data
```

### Root Cause
The application is configured with `network_mode: host` which means:
- The application runs with the host's network stack
- Redis service name `redis` is not resolvable
- Must connect to `localhost:6379` instead of `redis:6379`

### Solution 1: Use Current Configuration (Recommended)
The current `docker-compose.yml` is configured correctly:
```yaml
wolmanager:
  environment:
    - REDIS_URL=redis://localhost:6379/0  # ✅ Correct for host networking
  network_mode: host
```

### Solution 2: Use Alternative Configuration
If you prefer Docker's default networking, use `docker-compose-alternative.yml`:
```bash
docker-compose -f docker-compose-alternative.yml up -d
```

**Note**: This may require additional configuration for network discovery to access the host network.

### Testing Redis Connection

1. **Test Redis from host:**
   ```bash
   redis-cli ping
   ```

2. **Test Redis from within container:**
   ```bash
   docker exec -it wolmanager-app python test_docker_redis.py
   ```

3. **Check application health:**
   ```bash
   curl http://localhost:8000/health
   ```

### Network Discovery Considerations

When using `network_mode: host`:
- ✅ Application can discover devices on the host network
- ✅ No additional network configuration needed
- ✅ WOL broadcasts work directly

When using Docker's default networking:
- ❌ Application may not see host network devices
- ❌ Requires additional configuration for network access
- ⚠️ May need `--network host` or similar configuration

### Verification Steps

1. **Start services:**
   ```bash
   docker-compose up -d
   ```

2. **Check Redis is running:**
   ```bash
   docker-compose ps redis
   redis-cli ping
   ```

3. **Check application health:**
   ```bash
   curl http://localhost:8000/health
   ```

4. **Start discovery:**
   ```bash
   curl -X POST http://localhost:8000/api/v1/discovery/start
   ```

5. **Check for hosts:**
   ```bash
   curl http://localhost:8000/api/v1/hosts
   ```

### Common Issues

1. **Redis not starting:** Check if port 6379 is already in use
2. **Application not connecting:** Verify REDIS_URL is correct for your network mode
3. **No hosts discovered:** Check network configuration and RouterOS settings
4. **Permission denied:** Ensure Docker has necessary permissions for network access

### Logs and Debugging

```bash
# View application logs
docker-compose logs wolmanager

# View Redis logs
docker-compose logs redis

# Check Redis connectivity
docker exec -it wolmanager-redis redis-cli ping

# Check application connectivity
docker exec -it wolmanager-app curl http://localhost:8000/health
```
