import redis
import json
from typing import Dict, Any, Optional
from config import settings


class RedisClient:
    """Simple Redis client for session management"""
    
    def __init__(self, db: Optional[int] = None):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=db if db is not None else settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )
        # Test connection
        try:
            self.client.ping()
            print(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT} (DB: {db if db is not None else settings.REDIS_DB})")
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
            json_data = json.dumps(data, default=str)
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
    
    def get(self, key: str) -> Optional[str]:
        """Get string value by key"""
        try:
            return self.client.get(key)
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set string value with optional expiration"""
        try:
            result = self.client.set(key, value, ex=ex)
            return result is True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    def setex(self, key: str, value: str, time: int) -> bool:
        """Set string value with expiration time"""
        try:
            result = self.client.setex(key, time, value)
            return result is True
        except Exception as e:
            print(f"Redis setex error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            result = self.client.delete(key)
            return result > 0
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def setex_json(self, key: str, time: int, data: Dict[str, Any]) -> bool:
        """Set JSON data with expiration time"""
        try:
            json_data = json.dumps(data, default=str)
            result = self.client.setex(key, time, json_data)
            return result is True
        except Exception as e:
            print(f"Redis setex_json error: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON data by key"""
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Redis get_json error: {e}")
            return None