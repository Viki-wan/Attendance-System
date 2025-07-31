import os
from datetime import timedelta
from pathlib import Path

class Config:
    """Application configuration class"""
    
    # Basic Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')
    
    # Set the database path to the project root's attendance.db
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATABASE = str(BASE_DIR / 'attendance.db')
    STUDENT_IMAGES_PATH = 'student_images'
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    
    # Upload configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Face recognition settings
    FACE_RECOGNITION_TOLERANCE = 0.6
    FACE_RECOGNITION_MODEL = 'hog'  # or 'cnn' for better accuracy but slower
    
    # Camera settings
    CAMERA_INDEX = 0
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    CAMERA_FPS = 30
    
    # Attendance settings
    ATTENDANCE_THRESHOLD = 0.6
    MAX_UNKNOWN_FACES = 5
    SESSION_TIMEOUT_MINUTES = 30
    
    # Notification settings
    ENABLE_NOTIFICATIONS = True
    NOTIFICATION_SOUND = True
    
    # Security settings
    CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    
    # Performance settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or 'app.log'
    
    # Email configuration (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Pagination settings
    ITEMS_PER_PAGE = 20
    
    # Theme settings
    DEFAULT_THEME = 'light'
    AVAILABLE_THEMES = ['light', 'dark']
    
    # Report settings
    REPORT_FORMATS = ['pdf', 'excel', 'csv']
    REPORT_CACHE_TIMEOUT = 3600
    
    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        
        # Set up logging
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            file_handler = RotatingFileHandler(
                Config.LOG_FILE, 
                maxBytes=10240000, 
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Lecturer Panel startup')

class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    
class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Use PostgreSQL in production
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://user:password@localhost/lecturer_panel'
    
class TestingConfig(Config):
    """Testing environment configuration"""
    TESTING = True
    DEBUG = True
    DATABASE_PATH = ':memory:'  # In-memory database for testing
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}