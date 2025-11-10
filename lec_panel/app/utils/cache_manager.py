# app/utils/cache_manager.py
"""
Redis-based caching system for high-performance data access.
Reduces database load and improves response times for frequently accessed data.
Enhanced with statistics, monitoring, and fallback support.
"""

import redis
import json
import pickle
from functools import wraps
from datetime import timedelta
import time
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages Redis cache operations with automatic serialization."""
    
    def __init__(self, redis_client=None):
        """Initialize cache manager with Redis client."""
        self.redis = redis_client
        self._stats = {'hits': 0, 'misses': 0}
        
        # Try to initialize if not provided
        if self.redis is None:
            self.redis = self._get_redis_client()
    
    @staticmethod
    def _get_redis_client():
        """Get Redis client from Flask app config or environment."""
        try:
            # Try to get from Flask context first
            from flask import current_app
            redis_url = current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            client = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=2)
            # Test connection
            client.ping()
            logger.info(f'Redis connected: {redis_url}')
            return client
        except Exception as e:
            # If Flask context not available or Redis not running, try direct connection
            try:
                import os
                redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
                client = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=2)
                client.ping()
                logger.info(f'Redis connected: {redis_url}')
                return client
            except Exception as e2:
                logger.warning(f'Redis connection failed: {e2}, using in-memory cache')
                return None  # Will use in-memory fallback
    
    def set(self, key, value, ttl=3600):
        """
        Set a value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be serialized)
            ttl: Time to live in seconds (default 1 hour)
        """
        try:
            if self.redis is None:
                return False
            
            serialized = pickle.dumps(value)
            self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def get(self, key):
        """
        Get a value from cache.
        
        Returns:
            Cached value or None if not found/expired
        """
        try:
            if self.redis is None:
                self._stats['misses'] += 1
                return None
            
            data = self.redis.get(key)
            if data:
                self._stats['hits'] += 1
                return pickle.loads(data)
            else:
                self._stats['misses'] += 1
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self._stats['misses'] += 1
            return None
    
    def delete(self, key):
        """Delete a key from cache."""
        try:
            if self.redis is None:
                return False
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def delete_pattern(self, pattern):
        """
        Delete all keys matching a pattern.
        
        Example: delete_pattern('session:*') deletes all session cache
        """
        try:
            if self.redis is None:
                return 0
            
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += self.redis.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.error(f"Cache pattern delete error: {e}")
            return 0
    
    def exists(self, key):
        """Check if a key exists in cache."""
        if self.redis is None:
            return False
        return self.redis.exists(key) > 0
    
    def ttl(self, key):
        """Get remaining time to live for a key in seconds."""
        if self.redis is None:
            return -1
        return self.redis.ttl(key)
    
    def increment(self, key, amount=1):
        """Increment a counter."""
        if self.redis is None:
            return None
        return self.redis.incrby(key, amount)
    
    def decrement(self, key, amount=1):
        """Decrement a counter."""
        if self.redis is None:
            return None
        return self.redis.decrby(key, amount)
    
    def clear_all(self):
        """Clear all cache keys (use with caution)"""
        try:
            if self.redis is None:
                return 0
            
            # Get all keys with app prefix
            from flask import current_app
            prefix = current_app.config.get('CACHE_KEY_PREFIX', 'attendance:')
            pattern = f"{prefix}*"
            
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += self.redis.delete(*keys)
                if cursor == 0:
                    break
            
            logger.info(f'Cleared {deleted} cache keys')
            return deleted
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    def get_stats(self):
        """Get cache statistics"""
        stats = {
            'type': 'redis' if self.redis else 'memory',
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'total_requests': self._stats['hits'] + self._stats['misses'],
        }
        
        if stats['total_requests'] > 0:
            stats['hit_rate'] = (stats['hits'] / stats['total_requests']) * 100
        else:
            stats['hit_rate'] = 0
        
        if self.redis:
            try:
                info = self.redis.info()
                stats['memory_used'] = info.get('used_memory_human', 'N/A')
                stats['total_keys'] = self.redis.dbsize()
                stats['connected_clients'] = info.get('connected_clients', 0)
            except:
                pass
        
        return stats


# Global cache instance - will be initialized properly when app starts
cache = None


def init_cache():
    """Initialize global cache instance"""
    global cache
    cache = CacheManager()
    return cache


# Caching decorators
def cached(key_prefix, ttl=3600):
    """
    Decorator to cache function results.
    
    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds
    
    Usage:
        @cached('session', ttl=300)
        def get_session(session_id):
            return ClassSession.query.get(session_id)
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Skip caching if cache not available
            if cache is None:
                return f(*args, **kwargs)
            
            # Build cache key from function arguments
            cache_key = f"{key_prefix}:{f.__name__}:"
            cache_key += ":".join(str(arg) for arg in args)
            cache_key += ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapped
    return decorator


def cache_key(*args, **kwargs):
    """Generate a cache key from arguments."""
    parts = [str(arg) for arg in args]
    parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return ":".join(parts)


def timed_cache(key_prefix, ttl=3600):
    """
    Decorator that caches function results and logs execution time.
    
    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            
            # Skip caching if cache not available
            if cache is None:
                result = f(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f'{f.__name__} took {elapsed:.3f}s (cache not available)')
                return result
            
            # Build cache key
            cache_key = f"{key_prefix}:{f.__name__}:"
            cache_key += ":".join(str(arg) for arg in args)
            cache_key += ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                elapsed = time.time() - start_time
                logger.info(f'{f.__name__} cache hit (took {elapsed:.3f}s)')
                return result
            
            # Execute function
            result = f(*args, **kwargs)
            elapsed = time.time() - start_time
            
            # Cache result
            cache.set(cache_key, result, ttl)
            
            logger.info(f'{f.__name__} took {elapsed:.3f}s (cached for {ttl}s)')
            
            return result
        
        return wrapped
    return decorator


class SessionCache:
    """Specialized cache for session data."""
    
    @staticmethod
    def set_active_session(session_id, data, ttl=7200):
        """Cache active session data (2 hour default)."""
        if cache is None:
            return False
        key = f"active_session:{session_id}"
        return cache.set(key, data, ttl)
    
    @staticmethod
    def get_active_session(session_id):
        """Get active session from cache."""
        if cache is None:
            return None
        key = f"active_session:{session_id}"
        return cache.get(key)
    
    @staticmethod
    def delete_active_session(session_id):
        """Remove session from cache."""
        if cache is None:
            return False
        key = f"active_session:{session_id}"
        return cache.delete(key)
    
    @staticmethod
    def cache_session_students(session_id, students, ttl=3600):
        """Cache list of students for a session."""
        if cache is None:
            return False
        key = f"session_students:{session_id}"
        return cache.set(key, students, ttl)
    
    @staticmethod
    def get_session_students(session_id):
        """Get cached student list."""
        if cache is None:
            return None
        key = f"session_students:{session_id}"
        return cache.get(key)


class FaceEncodingCache:
    """Specialized cache for face encodings."""
    
    @staticmethod
    def cache_encoding(student_id, encoding, ttl=86400):
        """Cache face encoding (24 hour default)."""
        if cache is None:
            return False
        key = f"face_encoding:{student_id}"
        return cache.set(key, encoding, ttl)
    
    @staticmethod
    def get_encoding(student_id):
        """Get cached face encoding."""
        if cache is None:
            return None
        key = f"face_encoding:{student_id}"
        return cache.get(key)
    
    @staticmethod
    def cache_all_encodings(class_id, encodings, ttl=86400):
        """Cache all face encodings for a class."""
        if cache is None:
            return False
        key = f"class_encodings:{class_id}"
        return cache.set(key, encodings, ttl)
    
    @staticmethod
    def get_all_encodings(class_id):
        """Get all cached encodings for a class."""
        if cache is None:
            return None
        key = f"class_encodings:{class_id}"
        return cache.get(key)
    
    @staticmethod
    def invalidate_class_cache(class_id):
        """Invalidate all encoding cache for a class."""
        if cache is None:
            return 0
        pattern = f"class_encodings:{class_id}"
        return cache.delete(pattern)


class DashboardCache:
    """Cache for dashboard statistics."""
    
    @staticmethod
    def cache_stats(instructor_id, stats, ttl=300):
        """Cache dashboard stats (5 minute default)."""
        if cache is None:
            return False
        key = f"dashboard_stats:{instructor_id}"
        return cache.set(key, stats, ttl)
    
    @staticmethod
    def get_stats(instructor_id):
        """Get cached dashboard stats."""
        if cache is None:
            return None
        key = f"dashboard_stats:{instructor_id}"
        return cache.get(key)
    
    @staticmethod
    def invalidate_stats(instructor_id):
        """Invalidate dashboard cache."""
        if cache is None:
            return False
        key = f"dashboard_stats:{instructor_id}"
        return cache.delete(key)


class ReportCache:
    """Cache for generated reports."""
    
    @staticmethod
    def cache_report(report_id, report_data, ttl=1800):
        """Cache generated report (30 minute default)."""
        if cache is None:
            return False
        key = f"report:{report_id}"
        return cache.set(key, report_data, ttl)
    
    @staticmethod
    def get_report(report_id):
        """Get cached report."""
        if cache is None:
            return None
        key = f"report:{report_id}"
        return cache.get(key)
    
    @staticmethod
    def delete_report(report_id):
        """Delete cached report."""
        if cache is None:
            return False
        key = f"report:{report_id}"
        return cache.delete(key)


# Cache warming utilities
def warm_instructor_cache(instructor_id):
    """Pre-load commonly accessed data for an instructor."""
    if cache is None:
        return 0
    
    from app.models.class_session import ClassSession
    from app.models.class_instructors import ClassInstructor
    from datetime import datetime, timedelta
    
    # Cache upcoming sessions
    tomorrow = (datetime.now() + timedelta(days=1)).date()
    sessions = ClassSession.query.filter(
        ClassSession.created_by == instructor_id,
        ClassSession.date <= tomorrow.strftime('%Y-%m-%d'),
        ClassSession.status.in_(['scheduled', 'ongoing'])
    ).all()
    
    for session in sessions:
        SessionCache.set_active_session(session.session_id, session)
    
    # Cache assigned classes
    assignments = ClassInstructor.query.filter_by(
        instructor_id=instructor_id
    ).all()
    
    key = f"instructor_classes:{instructor_id}"
    cache.set(key, assignments, ttl=3600)
    
    return len(sessions)


def clear_user_cache(user_id, user_type='instructor'):
    """Clear all cache for a specific user."""
    if cache is None:
        return 0
    
    patterns = [
        f"dashboard_stats:{user_id}",
        f"instructor_classes:{user_id}",
        f"preferences:{user_id}",
        f"notifications:{user_id}:*"
    ]
    
    total_deleted = 0
    for pattern in patterns:
        total_deleted += cache.delete_pattern(pattern)
    
    return total_deleted