"""
Setup Verification Script
Run this script to verify all components are working correctly
Usage: python test_setup.py
"""

import sys
import time
from datetime import datetime


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_status(test_name, passed, message=""):
    """Print test status"""
    status = "✓ PASS" if passed else "✗ FAIL"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} - {test_name}")
    if message:
        print(f"       {message}")


def test_imports():
    """Test required Python packages"""
    print_header("Testing Python Packages")
    
    tests_passed = 0
    tests_total = 0
    
    # Test Redis
    tests_total += 1
    try:
        import redis
        print_status("Redis package", True, f"Version: {redis.__version__}")
        tests_passed += 1
    except ImportError as e:
        print_status("Redis package", False, f"Error: {e}")
    
    # Test Flask
    tests_total += 1
    try:
        import flask
        print_status("Flask package", True, f"Version: {flask.__version__}")
        tests_passed += 1
    except ImportError as e:
        print_status("Flask package", False, f"Error: {e}")
    
    # Test SQLAlchemy
    tests_total += 1
    try:
        import sqlalchemy
        print_status("SQLAlchemy package", True, f"Version: {sqlalchemy.__version__}")
        tests_passed += 1
    except ImportError as e:
        print_status("SQLAlchemy package", False, f"Error: {e}")
    
    return tests_passed, tests_total


def test_redis_connection():
    """Test Redis connection"""
    print_header("Testing Redis Connection")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        import redis
        
        # Test connection
        tests_total += 1
        try:
            r = redis.from_url('redis://localhost:6379/0', socket_connect_timeout=2)
            r.ping()
            print_status("Redis connection", True, "Connected to localhost:6379")
            tests_passed += 1
            
            # Test set/get
            tests_total += 1
            r.set('test_key', 'test_value')
            value = r.get('test_key')
            if value == b'test_value':
                print_status("Redis set/get", True, "Read/write working")
                tests_passed += 1
                r.delete('test_key')
            else:
                print_status("Redis set/get", False, "Value mismatch")
            
            # Test TTL
            tests_total += 1
            r.setex('test_ttl', 10, 'value')
            ttl = r.ttl('test_ttl')
            if ttl > 0 and ttl <= 10:
                print_status("Redis TTL", True, f"TTL: {ttl} seconds")
                tests_passed += 1
                r.delete('test_ttl')
            else:
                print_status("Redis TTL", False, f"Invalid TTL: {ttl}")
            
            # Get Redis info
            info = r.info('server')
            print(f"\n       Redis Server Info:")
            print(f"       - Version: {info.get('redis_version', 'N/A')}")
            print(f"       - Uptime: {info.get('uptime_in_seconds', 0)} seconds")
            
        except redis.ConnectionError as e:
            print_status("Redis connection", False, f"Cannot connect: {e}")
        except Exception as e:
            print_status("Redis connection", False, f"Error: {e}")
    
    except ImportError:
        print_status("Redis package", False, "Package not installed")
    
    return tests_passed, tests_total


def test_flask_app():
    """Test Flask application"""
    print_header("Testing Flask Application")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from app import create_app, db
        
        # Create app
        tests_total += 1
        try:
            app = create_app()
            print_status("Flask app creation", True, "App created successfully")
            tests_passed += 1
            
            with app.app_context():
                # Test database connection
                tests_total += 1
                try:
                    db.session.execute('SELECT 1')
                    print_status("Database connection", True, "Database accessible")
                    tests_passed += 1
                except Exception as e:
                    print_status("Database connection", False, f"Error: {e}")
                
                # Test cache initialization
                tests_total += 1
                cache = app.extensions.get('cache')
                if cache:
                    print_status("Cache initialization", True, "Cache manager loaded")
                    tests_passed += 1
                    
                    # Test cache operations
                    tests_total += 1
                    try:
                        cache.set('test_cache', {'data': 'test'}, ttl=60)
                        result = cache.get('test_cache')
                        if result and result.get('data') == 'test':
                            print_status("Cache operations", True, "Set/get working")
                            tests_passed += 1
                            cache.delete('test_cache')
                        else:
                            print_status("Cache operations", False, "Value mismatch")
                    except Exception as e:
                        print_status("Cache operations", False, f"Error: {e}")
                    
                    # Get cache stats
                    stats = cache.get_stats()
                    print(f"\n       Cache Statistics:")
                    print(f"       - Type: {stats.get('type', 'unknown')}")
                    print(f"       - Total Keys: {stats.get('total_keys', 0)}")
                    print(f"       - Hit Rate: {stats.get('hit_rate', 0):.1f}%")
                else:
                    print_status("Cache initialization", False, "Cache not initialized")
                
        except Exception as e:
            print_status("Flask app creation", False, f"Error: {e}")
    
    except ImportError as e:
        print_status("Flask imports", False, f"Import error: {e}")
    
    return tests_passed, tests_total


def test_database_indexes():
    """Test database indexes"""
    print_header("Testing Database Indexes")
    
    tests_passed = 0
    tests_total = 1
    
    try:
        from app import create_app, db
        
        app = create_app()
        with app.app_context():
            # Check for performance indexes
            result = db.session.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name LIKE 'idx_%'
            """)
            indexes = [row[0] for row in result.fetchall()]
            
            if indexes:
                print_status("Database indexes", True, f"Found {len(indexes)} indexes")
                tests_passed += 1
                
                print("\n       Indexes found:")
                for idx in indexes:
                    print(f"       - {idx}")
            else:
                print_status("Database indexes", False, "No performance indexes found")
                print("       Run: flask create-indexes")
    
    except Exception as e:
        print_status("Database indexes", False, f"Error: {e}")
    
    return tests_passed, tests_total


def test_performance():
    """Test basic performance"""
    print_header("Testing Performance")
    
    tests_passed = 0
    tests_total = 0
    
    try:
        from app import create_app
        
        app = create_app()
        with app.app_context():
            cache = app.extensions.get('cache')
            
            if cache:
                # Test cache speed
                tests_total += 1
                
                # Write performance
                start = time.time()
                for i in range(100):
                    cache.set(f'perf_test_{i}', f'value_{i}', ttl=60)
                write_time = time.time() - start
                
                # Read performance
                start = time.time()
                for i in range(100):
                    cache.get(f'perf_test_{i}')
                read_time = time.time() - start
                
                # Cleanup
                for i in range(100):
                    cache.delete(f'perf_test_{i}')
                
                print(f"       Write 100 keys: {write_time:.3f}s ({write_time*10:.1f}ms per key)")
                print(f"       Read 100 keys: {read_time:.3f}s ({read_time*10:.1f}ms per key)")
                
                if write_time < 1.0 and read_time < 0.5:
                    print_status("Cache performance", True, "Performance acceptable")
                    tests_passed += 1
                else:
                    print_status("Cache performance", False, "Performance below expectations")
    
    except Exception as e:
        print_status("Performance test", False, f"Error: {e}")
    
    return tests_passed, tests_total


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  FLASK ATTENDANCE SYSTEM - SETUP VERIFICATION")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    
    total_passed = 0
    total_tests = 0
    
    # Run all tests
    passed, total = test_imports()
    total_passed += passed
    total_tests += total
    
    passed, total = test_redis_connection()
    total_passed += passed
    total_tests += total
    
    passed, total = test_flask_app()
    total_passed += passed
    total_tests += total
    
    passed, total = test_database_indexes()
    total_passed += passed
    total_tests += total
    
    passed, total = test_performance()
    total_passed += passed
    total_tests += total
    
    # Print summary
    print_header("SUMMARY")
    
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n  Tests Passed: {total_passed}/{total_tests}")
    print(f"  Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("\n  🎉 All tests passed! Your setup is ready.")
        status_code = 0
    elif success_rate >= 80:
        print("\n  ⚠️  Most tests passed. Review failures above.")
        status_code = 0
    else:
        print("\n  ❌ Multiple tests failed. Please review the errors above.")
        status_code = 1
    
    print("\n" + "=" * 70 + "\n")
    
    return status_code


if __name__ == '__main__':
    sys.exit(main())