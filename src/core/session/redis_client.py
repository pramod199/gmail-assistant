import redis
import json
from typing import Dict, Any, Optional
from ...config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


class RedisClient:
    """Simple Redis client for session management"""
    
    def __init__(self):
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        # Test connection
        try:
            self.client.ping()
            print(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            raise ConnectionError(f"Redis connection failed: {e}")
    
    def hget(self, hash_name: str, key: str) -> Optional[Dict[str, Any]]:
        """Get data from hash"""
        try:
            data = self.client.hget(hash_name, key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Redis hget error: {e}")
            return None
    
    def hset(self, hash_name: str, key: str, data: Dict[str, Any]) -> bool:
        """Set data in hash"""
        try:
            json_data = json.dumps(data)
            result = self.client.hset(hash_name, key, json_data)
            return True
        except Exception as e:
            print(f"Redis hset error: {e}")
            return False
    
    def hdel(self, hash_name: str, key: str) -> bool:
        """Delete key from hash"""
        try:
            result = self.client.hdel(hash_name, key)
            return result > 0
        except Exception as e:
            print(f"Redis hdel error: {e}")
            return False
    
    def hgetall(self, hash_name: str) -> Dict[str, Dict[str, Any]]:
        """Get all data from hash"""
        try:
            raw_data = self.client.hgetall(hash_name)
            parsed_data = {}
            for key, value in raw_data.items():
                try:
                    parsed_data[key] = json.loads(value)
                except json.JSONDecodeError:
                    print(f"Failed to parse JSON for key {key}")
                    continue
            return parsed_data
        except Exception as e:
            print(f"Redis hgetall error: {e}")
            return {}