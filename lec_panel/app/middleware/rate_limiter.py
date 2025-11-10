"""
Rate Limiter Middleware
Implements token bucket algorithm for API rate limiting
"""
from functools import wraps
from flask import request, g
from datetime import datetime, timedelta
from typing import Dict, Optional
import time


class RateLimiter:
    """
    In-memory rate limiter using token bucket algorithm
    For production, use Redis-based implementation
    """
    
    # In-memory storage (use Redis in production)
    _storage: Dict[str, Dict] = {}
    
    @staticmethod
    def _get_identifier() -> str:
        """
        Get unique identifier for rate limiting
        Uses JWT user_id if available, otherwise IP address
        """
        # Try to get user_id from JWT
        if hasattr(g, 'user_id') and g.user_id:
            return f"user:{g.user_id}"
        
        # Fall back to IP address
        return f"ip:{request.remote_addr}"
    
    @staticmethod
    def _get_bucket(identifier: str, limit: int, window: int) -> Dict:
        """
        Get or create token bucket for identifier
        
        Args:
            identifier: Unique identifier (user_id or IP)
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            Bucket dictionary with tokens and reset time
        """
        now = time.time()
        
        if identifier not in RateLimiter._storage:
            # Create new bucket
            RateLimiter._storage[identifier] = {
                'tokens': limit,
                'last_update': now,
                'reset_time': now + window
            }
        
        bucket = RateLimiter._storage[identifier]
        
        # Refill tokens if window has passed
        if now >= bucket['reset_time']:
            bucket['tokens'] = limit
            bucket['reset_time'] = now + window
            bucket['last_update'] = now
        
        return bucket
    
    @staticmethod
    def check_rate_limit(limit: int = 100, window: int = 3600) -> tuple:
        """
        Check if request is within rate limit
        
        Args:
            limit: Maximum requests per window
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        identifier = RateLimiter._get_identifier()
        bucket = RateLimiter._get_bucket(identifier, limit, window)
        
        # Check if tokens available
        if bucket['tokens'] > 0:
            bucket['tokens'] -= 1
            bucket['last_update'] = time.time()
            return True, bucket['tokens'], int(bucket['reset_time'])
        
        # Rate limit exceeded
        return False, 0, int(bucket['reset_time'])
    
    @staticmethod
    def get_rate_limit_headers(remaining: int, reset_time: int, limit: int) -> Dict[str, str]:
        """
        Generate rate limit headers
        
        Args:
            remaining: Remaining requests
            reset_time: Unix timestamp of reset
            limit: Total limit
            
        Returns:
            Dictionary of headers
        """
        return {
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': str(remaining),
            'X-RateLimit-Reset': str(reset_time),
            'X-RateLimit-Reset-After': str(max(0, reset_time - int(time.time())))
        }
    
    @staticmethod
    def clear_limits(identifier: Optional[str] = None):
        """Clear rate limits (for testing or admin reset)"""
        if identifier:
            RateLimiter._storage.pop(identifier, None)
        else:
            RateLimiter._storage.clear()


def rate_limit(limit: int = 100, window: int = 3600):
    """
    Decorator to apply rate limiting to routes
    
    Args:
        limit: Maximum requests per window (default 100)
        window: Time window in seconds (default 3600 = 1 hour)
        
    Usage:
        @rate_limit(limit=60, window=3600)
        def my_api_endpoint():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from app.utils.api_response import APIResponse
            
            # Check rate limit
            is_allowed, remaining, reset_time = RateLimiter.check_rate_limit(limit, window)
            
            # Add rate limit headers to response
            headers = RateLimiter.get_rate_limit_headers(remaining, reset_time, limit)
            
            if not is_allowed:
                retry_after = reset_time - int(time.time())
                response, status_code = APIResponse.rate_limit_exceeded(retry_after)
                response.headers.update(headers)
                return response, status_code
            
            # Execute route
            result = f(*args, **kwargs)
            
            # Add headers to response
            if isinstance(result, tuple):
                response, status_code = result
                response.headers.update(headers)
                return response, status_code
            else:
                result.headers.update(headers)
                return result
        
        return decorated_function
    return decorator


# Preset rate limit decorators
def standard_rate_limit(f):
    """Standard rate limit: 100 requests/hour"""
    return rate_limit(limit=100, window=3600)(f)


def strict_rate_limit(f):
    """Strict rate limit: 30 requests/hour"""
    return rate_limit(limit=30, window=3600)(f)


def generous_rate_limit(f):
    """Generous rate limit: 500 requests/hour"""
    return rate_limit(limit=500, window=3600)(f)


# Redis-based Rate Limiter (for production)
class RedisRateLimiter:
    """
    Redis-based rate limiter for distributed systems
    Requires Redis connection
    """
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def check_rate_limit(self, identifier: str, limit: int, window: int) -> tuple:
        """
        Check rate limit using Redis
        
        Args:
            identifier: Unique identifier
            limit: Maximum requests
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        key = f"rate_limit:{identifier}"
        now = time.time()
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, now - window)
        
        # Count current requests
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(now): now})
        
        # Set expiration
        pipe.expire(key, window)
        
        results = pipe.execute()
        current_count = results[1]
        
        if current_count < limit:
            return True, limit - current_count - 1, int(now + window)
        
        return False, 0, int(now + window)


# Example Redis integration (commented out - enable in production)
"""
from redis import Redis
from flask import current_app

def get_redis_rate_limiter():
    redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
    redis_client = Redis.from_url(redis_url)
    return RedisRateLimiter(redis_client)
"""