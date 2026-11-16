"""
Cache Clear Script
Run this to clear all cached dashboard data and see fresh results
"""

from app import create_app, db
from app.utils.cache_manager import cache, init_cache

app = create_app('development')

with app.app_context():
    print("=" * 80)
    print("CLEARING CACHE")
    print("=" * 80)
    
    # Get cache from app extensions (where it's actually stored)
    cache_instance = None
    try:
        from flask import current_app
        cache_instance = current_app.extensions.get('cache')
        print(f"Cache from extensions: {cache_instance}")
    except Exception as e:
        print(f"Could not get cache from extensions: {e}")
    
    # Fallback: Initialize cache directly
    if cache_instance is None:
        from app.utils.cache_manager import CacheManager
        cache_instance = CacheManager()
        print(f"Created new CacheManager: {cache_instance}")
    
    if cache_instance and cache_instance.redis:
        try:
            # Method 1: Clear specific instructor dashboard cache
            instructor_id = 'L2025001'
            from datetime import date
            today = date.today()
            cache_key = f"dashboard:{instructor_id}:{today.isoformat()}"
            
            deleted = cache.delete(cache_key)
            print(f"✓ Deleted cache key: {cache_key} - Result: {deleted}")
            
            # Method 2: Clear all dashboard cache using pattern
            pattern = "dashboard:*"
            deleted_count = cache.delete_pattern(pattern)
            print(f"✓ Deleted {deleted_count} dashboard cache keys")
            
            # Method 3: Clear statistics cache
            stats_key = f"dashboard_stats:{instructor_id}"
            cache.delete(stats_key)
            print(f"✓ Deleted stats cache: {stats_key}")
            
            # Check cache stats
            stats = cache.get_stats()
            print(f"\nCache Statistics:")
            print(f"  Type: {stats.get('type')}")
            print(f"  Total keys: {stats.get('total_keys', 'N/A')}")
            print(f"  Hit rate: {stats.get('hit_rate', 0):.2f}%")
            
            print("\n" + "=" * 80)
            print("CACHE CLEARED SUCCESSFULLY!")
            print("Now refresh your browser to see fresh data")
            print("=" * 80)
            
        except Exception as e:
            print(f"✗ Error clearing cache: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("✗ Cache not available (Redis not connected)")
        print("Dashboard should work fine without cache")