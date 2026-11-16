"""
Flask Application Factory
Initialize and configure the Flask application with all extensions
Enhanced with Redis caching, performance monitoring, and optimized context processors
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
import time

from dotenv import load_dotenv

from flask import Flask, render_template, jsonify, request, redirect, url_for, g
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_mail import Mail
from flask_cors import CORS
from celery import Celery
from flask_wtf.csrf import CSRFProtect
import click


from config.config import get_config
from app.utils.swagger_config import init_swagger
# Import the template filters from the separate file
from app.utils.template_filters import register_template_filters
from config.constants import UserType, AttendanceStatus, SessionStatus

load_dotenv()

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
socketio = SocketIO()
celery = Celery()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_name=None):
    """
    Application factory pattern
    Creates and configures the Flask application
    
    Args:
        config_name: Configuration to use (development, testing, production)
        
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)
    config.init_app(app)
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Initialize cache
    initialize_cache(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Configure logging
    configure_logging(app)

    # Register custom filters - ONLY ONCE, from template_filters.py
    register_template_filters(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Context processors
    register_context_processors(app)
    
    # Request handlers for performance monitoring
    register_request_handlers(app)
    
    # Initialize Swagger/API documentation
    init_swagger(app)
    
    return app


def initialize_cache(app):
    """Initialize Redis cache with fallback to in-memory cache"""
    if not app.config.get('ENABLE_CACHE', True):
        app.logger.info('Cache disabled by configuration')
        return
    
    try:
        from app.utils import cache_manager
        
        # Initialize global cache instance
        cache_instance = cache_manager.init_cache()
        
        # Store in app extensions
        app.extensions['cache'] = cache_instance
        
        # Test the connection
        if cache_instance.redis:
            cache_instance.set('_test', 'test', ttl=10)
            if cache_instance.get('_test') == 'test':
                app.logger.info(f'✓ Redis cache initialized: {app.config.get("REDIS_URL")}')
                cache_instance.delete('_test')
            else:
                app.logger.warning('Cache test failed, using in-memory fallback')
        else:
            app.logger.info('✓ In-memory cache initialized (Redis not available)')
            
    except Exception as e:
        app.logger.warning(f'Cache initialization error: {e}')
        app.logger.info('Continuing without cache')


def initialize_extensions(app):
    """Initialize Flask extensions"""
    
    # Database
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Mail
    from app.services.email_service import mail as email_mail
    email_mail.init_app(app)
    mail.init_app(app)

    csrf.init_app(app)
    
    # Authentication
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @app.context_processor
    def inject_csrf_token():
        """Make csrf_token available in all templates"""
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)
    
    
    # CORS (for API endpoints)
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', '*'),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # SocketIO (for real-time features)
    if app.config.get('ENABLE_WEBSOCKET', False):
        async_mode = app.config.get('SOCKETIO_ASYNC_MODE', 'threading')
        
        # Configure socketio based on async mode
        socketio_config = {
            'async_mode': async_mode,
            'cors_allowed_origins': "*",
            'logger': app.config.get('DEBUG', False),
            'engineio_logger': app.config.get('DEBUG', False)
        }
        
        # Only add message_queue if NOT using threading mode
        if async_mode != 'threading':
            message_queue = app.config.get('SOCKETIO_MESSAGE_QUEUE')
            if message_queue:
                socketio_config['message_queue'] = message_queue
        
        socketio.init_app(app, **socketio_config)
        app.logger.info(f'✓ SocketIO initialized with {async_mode} mode')
    
    # Celery (for background tasks)
    if app.config.get('ENABLE_CELERY', False):
        configure_celery(app)

def configure_celery(app):
    """Configure Celery for background task processing"""
    
    # Get configuration values
    broker_url = app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # Update Celery configuration
    celery.conf.update(
        broker_url=broker_url,
        result_backend=result_backend,
        task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
        result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
        accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
        timezone=app.config.get('CELERY_TIMEZONE', 'UTC'),
        enable_utc=app.config.get('CELERY_ENABLE_UTC', True),
        task_track_started=app.config.get('CELERY_TASK_TRACK_STARTED', True),
        task_time_limit=app.config.get('CELERY_TASK_TIME_LIMIT', 300),
        task_soft_time_limit=app.config.get('CELERY_TASK_SOFT_TIME_LIMIT', 240),
    )
    
    # Create a custom task class that runs within Flask app context
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    
    # Verify configuration
    app.logger.info(f'✓ Celery configured with broker: {broker_url}')

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    from app.models.user import Instructor
    return Instructor.query.get(user_id)


def register_request_handlers(app):
    """Register request handlers for performance monitoring"""
    
    @app.before_request
    def before_request():
        """Track request start time"""
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """Log slow requests"""
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            
            # Log slow requests
            if elapsed > app.config.get('SLOW_QUERY_THRESHOLD', 1.0):
                app.logger.warning(
                    f'Slow request: {request.method} {request.path} '
                    f'took {elapsed:.3f}s'
                )
            
            # Add timing header for debugging
            if app.debug:
                response.headers['X-Request-Duration'] = f'{elapsed:.3f}s'
        
        return response


def register_blueprints(app):
    """Register Flask blueprints (routes)"""
    
    # Authentication routes
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Help/Support routes
    from app.routes.help import help_bp
    app.register_blueprint(help_bp, url_prefix='/help')
    
    # Lecturer routes - Dashboard
    from app.routes.lecturer.dashboard import dashboard_bp
    app.register_blueprint(dashboard_bp)
    
    # Lecturer routes - Sessions (using name='lecturer_sessions')
    from app.routes.lecturer.sessions import sessions_bp
    app.register_blueprint(sessions_bp)
    
    # Lecturer routes - Attendance (using name='lecturer_attendance')
    from app.routes.lecturer.attendance import attendance_bp
    app.register_blueprint(attendance_bp)
    
    # Lecturer routes - Reports
    from app.routes.lecturer.reports import reports_bp
    app.register_blueprint(reports_bp)
    
    # Lecturer routes - Preferences
    from app.routes.lecturer.preferences import preferences_bp
    app.register_blueprint(preferences_bp)
    
    # Try to import optional blueprints
    try:
        from app.routes.lecturer.timetable import timetable_bp
        app.register_blueprint(timetable_bp)
    except ImportError:
        pass
    
    try:
        from app.routes.lecturer.dismissals import dismissals_bp
        app.register_blueprint(dismissals_bp)
    except ImportError:
        pass
    
    # API routes (if enabled)
    if app.config.get('ENABLE_API', False):
        from app.routes.api.v1 import api_bp
        app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Main/Home route
    @app.route('/')
    def index():
        """Redirect to appropriate dashboard"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring"""
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': app.config.get('APP_VERSION', '1.0.0')
        }
        
        # Check cache
        try:
            cache = app.extensions.get('cache')
            if cache:
                cache.set('_health_check', 'ok', ttl=10)
                if cache.get('_health_check') == 'ok':
                    health_data['cache'] = 'ok'
                    cache.delete('_health_check')
                else:
                    health_data['cache'] = 'degraded'
            else:
                health_data['cache'] = 'disabled'
        except Exception as e:
            health_data['cache'] = f'error: {str(e)}'
        
        # Check database
        try:
            db.session.execute('SELECT 1')
            health_data['database'] = 'ok'
        except Exception as e:
            health_data['database'] = f'error: {str(e)}'
            health_data['status'] = 'unhealthy'
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        return jsonify(health_data), status_code


def register_error_handlers(app):
    """Register error handlers for common HTTP errors"""
    
    @app.errorhandler(400)
    def bad_request(error):
        if request_wants_json():
            return jsonify({
                'error': 'Bad Request',
                'message': str(error),
                'status_code': 400
            }), 400
        return render_template('errors/400.html', error=error), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        if request_wants_json():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication required',
                'status_code': 401
            }), 401
        return render_template('errors/401.html', error=error), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        if request_wants_json():
            return jsonify({
                'error': 'Forbidden',
                'message': 'Access denied',
                'status_code': 403
            }), 403
        return render_template('errors/403.html', error=error), 403
    
    @app.errorhandler(404)
    def not_found(error):
        if request_wants_json():
            return jsonify({
                'error': 'Not Found',
                'message': 'Resource not found',
                'status_code': 404
            }), 404
        return render_template('errors/404.html', error=error), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Internal Server Error: {error}')
        if request_wants_json():
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }), 500
        return render_template('errors/500.html', error=error), 500
    
    @app.errorhandler(503)
    def service_unavailable(error):
        if request_wants_json():
            return jsonify({
                'error': 'Service Unavailable',
                'message': 'Service temporarily unavailable',
                'status_code': 503
            }), 503
        return render_template('errors/503.html', error=error), 503


def request_wants_json():
    """Check if request prefers JSON response"""
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > request.accept_mimetypes['text/html']


def configure_logging(app):
    """Configure application logging"""
    
    if not app.debug and not app.testing:
        # Create logs directory if it doesn't exist
        log_dir = Path(app.config.get('LOG_FILE', 'logs/app.log')).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File handler
        file_handler = RotatingFileHandler(
            app.config.get('LOG_FILE', 'logs/app.log'),
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            app.config.get('LOG_FORMAT', 
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
        ))
        file_handler.setLevel(logging.INFO)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # Add handlers
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Attendance System startup')


def register_cli_commands(app):
    """Register custom CLI commands"""
    
    @app.cli.command()
    def init_db():
        """Initialize the database with tables and default data"""
        from app.utils.db_init import initialize_database
        click.echo('Initializing database...')
        initialize_database()
        click.echo('✓ Database initialized successfully!')
    
    @app.cli.command()
    def create_indexes():
        """Create database indexes for performance"""
        click.echo('Creating database indexes...')
        
        try:
            # Session indexes
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_class_sessions_instructor_date 
                ON class_sessions(created_by, date, status)
            """)
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_class_sessions_date 
                ON class_sessions(date)
            """)
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_class_sessions_status 
                ON class_sessions(status)
            """)
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_class_sessions_class_date 
                ON class_sessions(class_id, date, status)
            """)
            
            # Attendance indexes
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_attendance_student_session 
                ON attendance(student_id, session_id, status)
            """)
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_attendance_status 
                ON attendance(status)
            """)
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_attendance_session 
                ON attendance(session_id)
            """)
            
            # Notification indexes
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_user 
                ON notifications(user_id, user_type, created_at)
            """)
            db.session.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_unread 
                ON notifications(user_id, user_type, is_read)
            """)
            
            db.session.commit()
            click.echo('✓ Database indexes created successfully!')
            
        except Exception as e:
            db.session.rollback()
            click.echo(f'✗ Error creating indexes: {e}')
    
    @app.cli.command()
    def cache_stats():
        """Show cache statistics"""
        cache = app.extensions.get('cache')
        if not cache:
            click.echo('Cache not initialized')
            return
        
        stats = cache.get_stats()
        click.echo('\n=== Cache Statistics ===')
        click.echo(f'Type: {stats.get("type", "unknown")}')
        click.echo(f'Total Keys: {stats.get("total_keys", 0)}')
        
        if stats.get('type') == 'redis':
            click.echo(f'Memory Used: {stats.get("memory_used", "N/A")}')
            click.echo(f'Connected Clients: {stats.get("connected_clients", "N/A")}')
    
    @app.cli.command()
    def clear_cache():
        """Clear all cache"""
        cache = app.extensions.get('cache')
        if not cache:
            click.echo('Cache not initialized')
            return
        
        if click.confirm('Are you sure you want to clear all cache?'):
            cache.clear_all()
            click.echo('✓ Cache cleared successfully!')
    
    @app.cli.command()
    def create_admin():
        """Create an admin user"""
        from app.models.user import Admin
        from werkzeug.security import generate_password_hash
        
        username = click.prompt('Username', type=str)
        password = click.prompt('Password', type=str, hide_input=True, 
                               confirmation_prompt=True)
        
        existing_admin = Admin.query.filter_by(username=username).first()
        if existing_admin:
            click.echo(f'Admin user "{username}" already exists!')
            return
        
        admin = Admin(
            username=username,
            password=generate_password_hash(password)
        )
        db.session.add(admin)
        db.session.commit()
        click.echo(f'✓ Admin user "{username}" created successfully!')
    
    @app.cli.command()
    def test_face_recognition():
        """Test face recognition setup"""
        click.echo('Testing face recognition...')
        try:
            import face_recognition
            import cv2
            click.echo('✓ face_recognition library loaded')
            click.echo('✓ OpenCV loaded')
            click.echo('Face recognition setup is working!')
        except ImportError as e:
            click.echo(f'✗ Error: {e}')
    
    @app.cli.command()
    @click.option('--days', default=30, help='Number of days of data to clean')
    def cleanup_old_data(days):
        """Clean up old data from database"""
        from datetime import timedelta
        from app.models.activity_log import ActivityLog
        from app.models.notification import Notification
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Clean old activity logs
        deleted_logs = ActivityLog.query.filter(
            ActivityLog.timestamp < cutoff_date
        ).delete()
        
        # Clean old read notifications
        deleted_notifications = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).delete()
        
        db.session.commit()
        
        click.echo(f'✓ Cleaned up {deleted_logs} activity logs and '
                  f'{deleted_notifications} notifications')


def register_context_processors(app):
    """Register template context processors"""
    
    @app.context_processor
    def inject_globals():
        """Inject global variables into all templates"""
        unread_count = 0
        if current_user.is_authenticated:
            from app.models.notification import Notification
            unread_count = Notification.query.filter_by(
                user_id=current_user.instructor_id,
                user_type='instructor',
                is_read=False
            ).count()
        
        return {
            'app_name': app.config.get('APP_NAME', 'Attendance System'),
            'app_version': app.config.get('APP_VERSION', '1.0.0'),
            'current_year': datetime.now().year,
            'unread_notifications': unread_count,
            'support_email': app.config.get('SUPPORT_EMAIL', 'support@example.com'),
            'UserType': UserType,
            'AttendanceStatus': AttendanceStatus,
            'SessionStatus': SessionStatus
        }
    
    @app.context_processor
    def utility_processor():
        """Inject utility functions into templates"""
        
        def get_status_badge(status, status_type='attendance'):
            """Get Bootstrap badge class for status"""
            if status_type == 'attendance':
                badge_map = {
                    'Present': 'success',
                    'Absent': 'danger',
                    'Late': 'warning',
                    'Excused': 'info'
                }
                return badge_map.get(status, 'secondary')
            
            elif status_type == 'session':
                badge_map = {
                    'scheduled': 'primary',
                    'ongoing': 'success',
                    'completed': 'secondary',
                    'cancelled': 'danger',
                    'dismissed': 'warning'
                }
                return badge_map.get(status, 'secondary')
            
            return 'secondary'
        
        def percentage_color(value):
            """Get color class for percentage value"""
            try:
                val = float(value)
                if val >= 75:
                    return 'text-success'
                elif val >= 50:
                    return 'text-warning'
                else:
                    return 'text-danger'
            except (ValueError, TypeError):
                return 'text-muted'
        
        return {
            'get_status_badge': get_status_badge,
            'percentage_color': percentage_color,
            'now': datetime.now
        }


def create_celery_app(app=None):
    """
    Create a Celery application configured with Flask context
    Used for running Celery workers
    """
    app = app or create_app()
    configure_celery(app)
    return celery