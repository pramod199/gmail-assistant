import redis.asyncio as redis
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client with proper connection lifecycle management"""

    def __init__(self, db: Optional[int] = None):
        self._client: Optional[redis.Redis] = None
        self._is_connected = False
        self._connection_lock = asyncio.Lock()
        self._db = db if db is not None else settings.REDIS_DB

    async def connect(self):
        """Initialize Redis connection with health checks"""
        async with self._connection_lock:
            if self._client is None:
                try:
                    self._client = redis.Redis(
                        host=settings.REDIS_HOST,
                        port=settings.REDIS_PORT,
                        db=self._db,
                        password=settings.REDIS_PASSWORD,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        retry_on_error=[ConnectionError, TimeoutError],
                        health_check_interval=30
                    )
                    await self._client.ping()
                    self._is_connected = True
                    logger.info(f"Successfully connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT} (DB: {self._db})")
                except Exception as e:
                    logger.error(f"Failed to connect to Redis: {e}")
                    self._client = None
                    self._is_connected = False
                    raise ConnectionError(f"Redis connection failed: {e}")

    async def get_client(self) -> redis.Redis:
        """Get Redis client with automatic reconnection"""
        if self._client is None or not self._is_connected:
            await self.connect()

        if self._client is None:
            raise ConnectionError("Redis client failed to initialize.")

        # Test connection health
        try:
            await self._client.ping()
        except Exception as e:
            logger.warning(f"Redis connection lost, attempting to reconnect: {e}")
            self._is_connected = False
            await self.connect()

        return self._client

    async def close(self):
        """Close Redis connection properly"""
        async with self._connection_lock:
            if self._client:
                try:
                    await self._client.close()
                except Exception as e:
                    logger.error(f"Error closing Redis connection: {e}")
                finally:
                    self._client = None
                    self._is_connected = False
                    logger.info("Redis connection closed.")

    def is_connected(self) -> bool:
        """Check if Redis is currently connected"""
        return self._is_connected

    async def hget(self, hash_name: str, key: str) -> Optional[Dict[str, Any]]:
        """Get data from hash"""
        try:
            client = await self.get_client()
            data = await client.hget(hash_name, key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis hget error: {e}")
            return None

    async def hset(self, hash_name: str, key: str, data: Dict[str, Any]) -> bool:
        """Set data in hash"""
        try:
            client = await self.get_client()
            json_data = json.dumps(data)
            await client.hset(hash_name, key, json_data)
            return True
        except Exception as e:
            logger.error(f"Redis hset error: {e}")
            return False

    async def hdel(self, hash_name: str, key: str) -> bool:
        """Delete key from hash"""
        try:
            client = await self.get_client()
            result = await client.hdel(hash_name, key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis hdel error: {e}")
            return False

    async def hgetall(self, hash_name: str) -> Dict[str, Dict[str, Any]]:
        """Get all data from hash"""
        try:
            client = await self.get_client()
            raw_data = await client.hgetall(hash_name)
            parsed_data = {}
            for key, value in raw_data.items():
                try:
                    parsed_data[key] = json.loads(value)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON for key {key}")
                    continue
            return parsed_data
        except Exception as e:
            logger.error(f"Redis hgetall error: {e}")
            return {}

    async def get(self, key: str) -> Optional[str]:
        """Get string value by key"""
        try:
            client = await self.get_client()
            return await client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set string value with optional expiration"""
        try:
            client = await self.get_client()
            result = await client.set(key, value, ex=ex)
            return result is True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    async def setex(self, key: str, value: str, time: int) -> bool:
        """Set string value with expiration time"""
        try:
            client = await self.get_client()
            result = await client.setex(key, time, value)
            return result is True
        except Exception as e:
            logger.error(f"Redis setex error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            client = await self.get_client()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def set_json(self, key: str, data: Dict[str, Any], ex: Optional[int] = None) -> bool:
        """Set JSON data with optional expiration"""
        try:
            client = await self.get_client()
            json_data = json.dumps(data)
            result = await client.set(key, json_data, ex=ex)
            return result is True
        except Exception as e:
            logger.error(f"Redis set_json error: {e}")
            return False

    async def setex_json(self, key: str, time: int, data: Dict[str, Any]) -> bool:
        """Set JSON data with expiration time"""
        try:
            client = await self.get_client()
            json_data = json.dumps(data)
            result = await client.setex(key, time, json_data)
            return result is True
        except Exception as e:
            logger.error(f"Redis setex_json error: {e}")
            return False

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON data by key"""
        try:
            client = await self.get_client()
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get_json error: {e}")
            return None

    async def sadd(self, key: str, *values) -> bool:
        """Add values to a set"""
        try:
            client = await self.get_client()
            await client.sadd(key, *values)
            return True
        except Exception as e:
            logger.error(f"Redis sadd error: {e}")
            return False

    async def srem(self, key: str, *values) -> bool:
        """Remove values from a set"""
        try:
            client = await self.get_client()
            result = await client.srem(key, *values)
            return result > 0
        except Exception as e:
            logger.error(f"Redis srem error: {e}")
            return False

    async def smembers(self, key: str) -> set:
        """Get all members of a set"""
        try:
            client = await self.get_client()
            return await client.smembers(key)
        except Exception as e:
            logger.error(f"Redis smembers error: {e}")
            return set()

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            client = await self.get_client()
            result = await client.exists(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False

    async def expire(self, key: str, time: int) -> bool:
        """Set expiration time for a key"""
        try:
            client = await self.get_client()
            result = await client.expire(key, time)
            return result is True
        except Exception as e:
            logger.error(f"Redis expire error: {e}")
            return False

    async def keys(self, pattern: str) -> list:
        """Get keys matching pattern"""
        try:
            client = await self.get_client()
            return await client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []

    async def incrbyfloat(self, key: str, amount: float) -> Optional[float]:
        """Increment float value"""
        try:
            client = await self.get_client()
            return await client.incrbyfloat(key, amount)
        except Exception as e:
            logger.error(f"Redis incrbyfloat error: {e}")
            return None


# Global Redis client instance
redis_service = RedisClient()


# Dependency to get Redis client in routes
async def get_redis():
    """Dependency function to get Redis client"""
    return await redis_service.get_client()