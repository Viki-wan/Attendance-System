"""
Comprehensive Celery Setup Verification
This script checks if your Celery configuration is correct
"""

import sys
import os

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_imports():
    """Test all required imports"""
    print_header("1. Testing Imports")
    
    required = {
        'redis': 'Redis',
        'celery': 'Celery',
        'flask': 'Flask',
    }
    
    all_ok = True
    for module, name in required.items():
        try:
            __import__(module)
            print(f"   ✅ {name}: OK")
        except ImportError:
            print(f"   ❌ {name}: MISSING - run: pip install {module}")
            all_ok = False
    
    return all_ok

def test_redis_connection():
    """Test Redis connection"""
    print_header("2. Testing Redis Connection")
    
    try:
        import redis
        from dotenv import load_dotenv
        load_dotenv()
        
        redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
        print(f"   Connecting to: {redis_url}")
        
        r = redis.from_url(redis_url)
        if r.ping():
            print("   ✅ Redis connection: SUCCESS")
            
            info = r.info()
            print(f"   Redis version: {info['redis_version']}")
            print(f"   Used memory: {info['used_memory_human']}")
            return True
        else:
            print("   ❌ Redis connection: FAILED")
            return False
            
    except Exception as e:
        print(f"   ❌ Redis error: {e}")
        print("\n   💡 Solution:")
        print("      1. Start Redis in WSL2: sudo service redis-server start")
        print("      2. Check .env file has: REDIS_URL=redis://127.0.0.1:6379/0")
        return False

def test_config():
    """Test configuration"""
    print_header("3. Testing Configuration")
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check environment variables
        celery_broker = os.getenv('CELERY_BROKER_URL', 'NOT SET')
        celery_backend = os.getenv('CELERY_RESULT_BACKEND', 'NOT SET')
        celery_enabled = os.getenv('ENABLE_CELERY', 'true').lower() == 'true'
        
        print(f"   ENABLE_CELERY: {celery_enabled}")
        print(f"   CELERY_BROKER_URL: {celery_broker}")
        print(f"   CELERY_RESULT_BACKEND: {celery_backend}")
        
        # Check if Redis URLs
        if 'redis' in celery_broker.lower() and 'redis' in celery_backend.lower():
            print("   ✅ Using Redis (correct)")
            return True
        elif 'amqp' in celery_broker.lower():
            print("   ❌ Using AMQP/RabbitMQ (incorrect)")
            print("\n   💡 Fix: Update .env file:")
            print("      CELERY_BROKER_URL=redis://127.0.0.1:6379/0")
            print("      CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0")
            return False
        else:
            print("   ⚠️  Broker configuration unclear")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_app_celery_instance():
    """Test Celery instance from app"""
    print_header("4. Testing App Celery Instance")
    
    try:
        from app import create_app, celery
        
        app = create_app()
        
        print(f"   Celery app name: {celery.main}")
        print(f"   Broker: {celery.conf.broker_url}")
        print(f"   Backend: {celery.conf.result_backend}")
        
        # Check if using Redis
        if 'redis' in celery.conf.broker_url.lower():
            print("   ✅ Celery instance using Redis")
            return True
        elif 'amqp' in celery.conf.broker_url.lower():
            print("   ❌ Celery instance using AMQP (should be Redis)")
            print("\n   💡 This means celery_worker.py needs to be fixed")
            return False
        else:
            print("   ⚠️  Unknown broker type")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_celery_worker_file():
    """Test celery_worker.py configuration"""
    print_header("5. Testing celery_worker.py")
    
    try:
        with open('celery_worker.py', 'r') as f:
            content = f.read()
        
        # Check for app context push
        if 'app.app_context().push()' in content:
            print("   ✅ App context push: Found")
        else:
            print("   ❌ App context push: MISSING")
            print("      Add this after creating app: app.app_context().push()")
            return False
        
        # Check for conf.update
        if 'celery_app.conf.update' in content or 'celery.conf.update' in content:
            print("   ✅ Celery configuration: Found")
        else:
            print("   ⚠️  Celery configuration: Not found")
            print("      Should update celery.conf with app.config values")
        
        return True
        
    except FileNotFoundError:
        print("   ❌ celery_worker.py not found!")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_task_import():
    """Test importing a task"""
    print_header("6. Testing Task Import")
    
    try:
        print("   Importing task...")
        from app.tasks.face_processing import preload_class_faces_task
        
        print(f"   Task name: {preload_class_faces_task.name}")
        print(f"   Task broker: {preload_class_faces_task.app.conf.broker_url}")
        
        if 'redis' in preload_class_faces_task.app.conf.broker_url.lower():
            print("   ✅ Task using Redis broker")
            return True
        else:
            print(f"   ❌ Task using wrong broker")
            return False
            
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_send_task():
    """Test sending a task"""
    print_header("7. Testing Task Sending")
    
    try:
        from app import create_app, celery
        
        app = create_app()
        with app.app_context():
            print("   Attempting to send test task...")
            
            # Create a simple test task
            @celery.task(name='test_task')
            def test_task():
                return "Hello from Celery!"
            
            result = test_task.apply_async()
            print(f"   ✅ Task sent successfully!")
            print(f"   Task ID: {result.id}")
            print(f"   Status: {result.status}")
            
            if result.status == 'PENDING':
                print("\n   ℹ️  Task is pending (waiting for worker)")
                print("      Start worker: start_celery.bat")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Error sending task: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_summary(results):
    """Print summary and recommendations"""
    print_header("SUMMARY")
    
    tests = [
        ("Imports", results[0]),
        ("Redis Connection", results[1]),
        ("Configuration", results[2]),
        ("App Celery Instance", results[3]),
        ("celery_worker.py", results[4]),
        ("Task Import", results[5]),
        ("Task Sending", results[6])
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {name}")
    
    print(f"\n   Score: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   🎉 All tests passed!")
        print("\n   Next steps:")
        print("   1. Start Celery worker:")
        print("      python -m celery -A celery_worker.celery worker --loglevel=info --pool=solo")
        print("   2. Start your Flask app")
    else:
        print("\n   ⚠️  Some tests failed. Follow the solutions above.")
        
        if not results[1]:
            print("\n   🔴 CRITICAL: Redis is not running")
            print("      Start Redis first: sudo service redis-server start (in WSL2)")
        
        if not results[2]:
            print("\n   🔴 CRITICAL: Configuration is wrong")
            print("      Fix .env file with correct Redis URLs")
        
        if not results[4]:
            print("\n   🔴 CRITICAL: celery_worker.py needs fixing")
            print("      Replace with the fixed version provided")

def main():
    """Run all tests"""
    print("\n🔍 Celery Setup Verification")
    print("   Checking your Celery and Redis configuration...\n")
    
    results = []
    
    # Run tests
    results.append(test_imports())
    results.append(test_redis_connection())
    results.append(test_config())
    results.append(test_app_celery_instance())
    results.append(test_celery_worker_file())
    results.append(test_task_import())
    results.append(test_send_task())
    
    # Print summary
    print_summary(results)
    
    # Exit code
    sys.exit(0 if all(results) else 1)

if __name__ == '__main__':
    main()