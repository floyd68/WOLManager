#!/usr/bin/env python3
"""
Test script to verify Redis connection in Docker environment
"""

import asyncio
import os
import sys
from app.core.redis_client import redis_client

async def test_redis_connection():
    """Test Redis connection"""
    print("Testing Redis connection...")
    
    # Get Redis URL from environment
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    print(f"Redis URL: {redis_url}")
    
    try:
        # Test connection
        await redis_client.connect()
        
        if redis_client.redis:
            # Test ping
            result = await redis_client.redis.ping()
            print(f"✅ Redis ping successful: {result}")
            
            # Test set/get
            await redis_client.redis.set("test_key", "test_value")
            value = await redis_client.redis.get("test_key")
            print(f"✅ Redis set/get successful: {value}")
            
            # Clean up
            await redis_client.redis.delete("test_key")
            print("✅ Redis test completed successfully")
            
        else:
            print("❌ Redis client not connected")
            return False
            
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_redis_connection())
    sys.exit(0 if success else 1)
