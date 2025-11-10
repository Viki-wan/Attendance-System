"""
Flask Attendance System Configuration
Environment-based configuration classes for different deployment scenarios
Enhanced with Redis caching, Celery, and performance monitoring
"""

import os
from datetime import timedelta
from pathlib import Path


class Config:
    """Base configuration with common settings"""
    
    # Application
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    APP_NAME = 'Face Recognition Attendance System'
    APP_VERSION = '1.0.0'
    
    # Base directories
    BASE_DIR = Path(__file__).resolve().parent.parent
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    FACE_ENCODINGS_FOLDER = UPLOAD_FOLDER / 'face_encodings'
    STUDENT_PHOTOS_FOLDER = UPLOAD_FOLDER / 'student_photos'
    FACE_ONLY_FOLDER = UPLOAD_FOLDER / 'face_only'
    REPORTS_FOLDER = UPLOAD_FOLDER / 'reports'
    
    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'echo': False
    }
    
    # Session
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    
    # File uploads
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    MAX_IMAGE_SIZE = (1920, 1080)
    
    # Face Recognition Settings
    FACE_RECOGNITION_TOLERANCE = float(os.environ.get('FACE_RECOGNITION_TOLERANCE', '0.6'))
    FACE_RECOGNITION_MODEL = 'hog'  # 'hog' or 'cnn'
    FACE_DETECTION_CONFIDENCE = 0.5
    MIN_FACE_SIZE = (100, 100)
    
    # Camera Settings
    CAMERA_RESOLUTION = (640, 480)
    CAMERA_FPS = 30
    CAMERA_QUALITY_THRESHOLD = 720
    FRAME_PROCESS_INTERVAL = 500  # milliseconds
    
    # Session Management
    SESSION_TIMEOUT_MINUTES = 30
    AUTO_MARK_LATE_THRESHOLD_MINUTES = 10
    MAX_SESSION_DURATION_MINUTES = 180
    SESSION_GRACE_PERIOD_MINUTES = 5
    
    # Redis Configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_URL = os.environ.get('REDIS_URL') or f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    
    # Cache Configuration
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))
    CACHE_KEY_PREFIX = 'attendance:'
    
    # Cache TTL Settings (in seconds)
    CACHE_TTL_DASHBOARD = int(os.environ.get('CACHE_TTL_DASHBOARD', 300))
    CACHE_TTL_SESSION = int(os.environ.get('CACHE_TTL_SESSION', 7200))
    CACHE_TTL_STUDENT_LIST = int(os.environ.get('CACHE_TTL_STUDENT_LIST', 3600))
    CACHE_TTL_FACE_ENCODING = int(os.environ.get('CACHE_TTL_FACE_ENCODING', 86400))
    CACHE_TTL_STATS = int(os.environ.get('CACHE_TTL_STATS', 300))
    CACHE_TTL_REPORT = int(os.environ.get('CACHE_TTL_REPORT', 1800))
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or REDIS_URL
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or REDIS_URL
    CELERY_TASK_SERIALIZER = os.environ.get('CELERY_TASK_SERIALIZER', 'json')
    CELERY_RESULT_SERIALIZER = os.environ.get('CELERY_RESULT_SERIALIZER', 'json')
    CELERY_ACCEPT_CONTENT = [os.environ.get('CELERY_ACCEPT_CONTENT', 'json')]
    CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'UTC')
    CELERY_ENABLE_UTC = os.environ.get('CELERY_ENABLE_UTC', 'true').lower() in ['true', 'on', '1']
    CELERY_TASK_TRACK_STARTED = os.environ.get('CELERY_TASK_TRACK_STARTED', 'true').lower() in ['true', 'on', '1']
    CELERY_TASK_TIME_LIMIT = int(os.environ.get('CELERY_TASK_TIME_LIMIT', 300))
    CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', 240))
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'false').lower() in ['true', 'on', '1']
    CELERY_TASK_EAGER_PROPAGATES = os.environ.get('CELERY_TASK_EAGER_PROPAGATES', 'false').lower() in ['true', 'on', '1']
    
    # SocketIO Configuration
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_LOGGER = True
    SOCKETIO_ENGINEIO_LOGGER = True
    
    # Email Configuration (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@attendance.edu')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = BASE_DIR / 'logs' / 'app.log'
    
    # Performance Monitoring
    SLOW_QUERY_THRESHOLD = 0.5  # seconds
    ENABLE_QUERY_LOGGING = True
    ENABLE_PERFORMANCE_METRICS = True
    
    # API Settings
    API_RATE_LIMIT = '100 per hour'
    API_VERSION = 'v1'
    
    # Pagination
    ITEMS_PER_PAGE = 20
    MAX_ITEMS_PER_PAGE = 100
    
    # Reports
    REPORT_RETENTION_DAYS = 30
    MAX_REPORT_RECORDS = 1000
    
    # Notifications
    NOTIFICATION_RETENTION_DAYS = 30
    MAX_NOTIFICATIONS_PER_USER = 50
    
    # Activity Logging
    ACTIVITY_LOG_RETENTION_DAYS = 90
    
    # System Metrics
    METRICS_RETENTION_DAYS = 90
    METRICS_COLLECTION_INTERVAL = 60  # seconds
    
    # Dashboard
    DASHBOARD_REFRESH_INTERVAL = 30  # seconds
    
    # Timezone
    TIMEZONE = os.environ.get('TIMEZONE', 'UTC')
    
    # Feature Flags
    ENABLE_MFA = os.environ.get('ENABLE_MFA', 'false').lower() in ['true', 'on', '1']
    ENABLE_API = os.environ.get('ENABLE_API', 'true').lower() in ['true', 'on', '1']
    ENABLE_WEBSOCKET = os.environ.get('ENABLE_WEBSOCKET', 'true').lower() in ['true', 'on', '1']
    ENABLE_CELERY = os.environ.get('ENABLE_CELERY', 'true').lower() in ['true', 'on', '1']
    ENABLE_CACHE = os.environ.get('ENABLE_CACHE', 'true').lower() in ['true', 'on', '1']
    
    @staticmethod
    def init_app(app):
        """Initialize application with config-specific settings"""
        # Create required directories
        for folder in [
            Config.UPLOAD_FOLDER,
            Config.FACE_ENCODINGS_FOLDER,
            Config.STUDENT_PHOTOS_FOLDER,
            Config.FACE_ONLY_FOLDER,
            Config.REPORTS_FOLDER,
            Config.BASE_DIR / 'logs'
        ]:
            folder.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development environment configuration"""
    
    DEBUG = True
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        f'sqlite:///{Config.BASE_DIR}/attendance.db'
    SQLALCHEMY_ECHO = True
    
    # Security (relaxed for development)
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Face Recognition (faster for development)
    FACE_RECOGNITION_MODEL = 'hog'
    
    # Redis Configuration (for caching and Celery)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 60
    
    # Session storage (using Redis)
    SESSION_TYPE = 'redis'
    SESSION_REDIS = REDIS_URL
    
    # Celery Configuration (ENABLED for development)
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', REDIS_URL)
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = os.environ.get('TIMEZONE', 'Africa/Nairobi')
    CELERY_ENABLE_UTC = True
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 300
    CELERY_TASK_SOFT_TIME_LIMIT = 240
    
    # Development: Set to True to run tasks synchronously (for debugging)
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'false').lower() in ['true', 'on', '1']
    CELERY_TASK_EAGER_PROPAGATES = os.environ.get('CELERY_TASK_EAGER_PROPAGATES', 'false').lower() in ['true', 'on', '1']
    
    # SocketIO - Threading mode for Windows (NO Redis message queue)
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE', 'threading')
    # Note: SOCKETIO_MESSAGE_QUEUE intentionally NOT set for threading mode
    # Only use message queue with eventlet/gevent in production
    
    # Cache TTLs (shorter for development)
    CACHE_TTL_DASHBOARD = 60
    CACHE_TTL_SESSION = 300
    CACHE_TTL_STUDENT_LIST = 300
    CACHE_TTL_FACE_ENCODING = 1800
    CACHE_TTL_STATS = 60
    CACHE_TTL_REPORT = 300
    
    # Logging
    LOG_LEVEL = 'DEBUG'
    ENABLE_QUERY_LOGGING = True
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Development-specific initialization
        print('\n' + '='*60)
        print('🚀 Running in DEVELOPMENT mode')
        print('='*60)
        
        # Database info
        print(f'💾 Database: {app.config.get("SQLALCHEMY_DATABASE_URI")}')
        
        # Redis status
        if app.config.get('ENABLE_CACHE'):
            redis_url = app.config.get("REDIS_URL")
            print(f'📦 Redis Cache: {redis_url}')
            
            # Test Redis connection
            try:
                import redis
                r = redis.from_url(redis_url)
                if r.ping():
                    print('   ✅ Redis connection: OK')
                else:
                    print('   ❌ Redis connection: FAILED')
            except Exception as e:
                print(f'   ❌ Redis connection error: {e}')
        
        # Celery status
        celery_enabled = app.config.get('ENABLE_CELERY')
        if celery_enabled:
            broker_url = app.config.get('CELERY_BROKER_URL')
            print(f'⚙️  Celery: ENABLED')
            print(f'   Broker: {broker_url}')
            
            # Check if tasks should run eagerly
            if app.config.get('CELERY_TASK_ALWAYS_EAGER'):
                print('   ⚠️  Tasks running SYNCHRONOUSLY (eager mode)')
            else:
                print('   ℹ️  Tasks running ASYNCHRONOUSLY')
                print('   📝 Start worker: celery -A celery_worker.celery worker --loglevel=info --pool=solo')
            
            # Test Celery connection
            try:
                import redis
                r = redis.from_url(broker_url)
                if r.ping():
                    print('   ✅ Celery broker connection: OK')
                else:
                    print('   ❌ Celery broker connection: FAILED')
            except Exception as e:
                print(f'   ⚠️  Celery broker not accessible: {e}')
                print('   💡 Tip: Make sure Redis is running and start Celery worker')
        else:
            print('⚙️  Celery: DISABLED')
        
        # WebSocket mode
        if app.config.get('ENABLE_WEBSOCKET'):
            ws_mode = app.config.get("SOCKETIO_ASYNC_MODE", "disabled")
            print(f'🔌 WebSocket: {ws_mode.upper()} mode')
            if ws_mode == 'threading':
                print('   ℹ️  No message queue (single process only)')
        
        print('='*60 + '\n')


class TestingConfig(Config):
    """Testing environment configuration"""
    
    DEBUG = True
    TESTING = True
    
    # Database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Security (disabled for testing)
    WTF_CSRF_ENABLED = False
    
    # Session
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    
    # Redis (use separate DB for testing)
    REDIS_DB = 1
    REDIS_URL = f'redis://{Config.REDIS_HOST}:{Config.REDIS_PORT}/1'
    
    # Cache (disabled for testing)
    CACHE_TYPE = 'simple'
    ENABLE_CACHE = False
    
    # Celery (run tasks synchronously in tests)
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    ENABLE_CELERY = True  # Enabled but runs synchronously
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        print('🧪 Running in TESTING mode')


class ProductionConfig(Config):
    """Production environment configuration"""
    
    DEBUG = False
    TESTING = False
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{Config.BASE_DIR}/attendance.db'
    SQLALCHEMY_ECHO = False
    
    # Security (strict for production)
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    WTF_CSRF_ENABLED = True
    
    # Face Recognition (accurate for production)
    FACE_RECOGNITION_MODEL = 'cnn'
    
    # Cache (optimized for production)
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_TTL_DASHBOARD = 300
    CACHE_TTL_SESSION = 7200
    
    # Celery (fully async in production)
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    
    # SocketIO (use eventlet with message queue in production)
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_MESSAGE_QUEUE = Config.REDIS_URL
    
    # Performance
    SLOW_QUERY_THRESHOLD = 1.0
    ENABLE_QUERY_LOGGING = False
    
    # Error handling
    PROPAGATE_EXCEPTIONS = False
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)
        
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        # File handler
        file_handler = RotatingFileHandler(
            Config.LOG_FILE,
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Attendance System startup (Production)')


class DockerConfig(ProductionConfig):
    """Docker container configuration"""
    
    # Database (use PostgreSQL in Docker)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://attendance:attendance@db:5432/attendance_db'
    
    # Redis (Docker service name)
    REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
    REDIS_URL = f'redis://{REDIS_HOST}:{Config.REDIS_PORT}/{Config.REDIS_DB}'
    CACHE_REDIS_URL = REDIS_URL
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    
    @staticmethod
    def init_app(app):
        ProductionConfig.init_app(app)
        
        # Docker-specific logging (stdout for container logs)
        import logging
        import sys
        
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'docker': DockerConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Get configuration object by name"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return config.get(config_name, DevelopmentConfig)