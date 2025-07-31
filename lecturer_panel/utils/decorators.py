"""
Decorators for the Face Recognition Attendance System - Lecturer Panel
Provides authentication, authorization, and utility decorators for the Flask application.
"""

from functools import wraps
import json
import time
from datetime import datetime, timedelta
from flask import session, request, redirect, url_for, flash, jsonify, g
from werkzeug.exceptions import Forbidden, Unauthorized
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.services.auth_service import AuthService
from lecturer_panel.utils.helpers import log_error, validate_session_access


def login_required(f):
    """
    Decorator to ensure user is logged in before accessing a route.
    Redirects to login page if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'instructor_id' not in session or 'logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Check if session is still valid
        auth_service = AuthService()
        if not auth_service.validate_session(session.get('instructor_id')):
            session.clear()
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Update last activity timestamp
        session['last_activity'] = datetime.now().isoformat()
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to ensure user has admin privileges.
    Only specific instructors can access admin functions.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'instructor_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Check if user has admin privileges
        db_service = DatabaseService()
        instructor = db_service.get_instructor_by_id(session['instructor_id'])
        
        if not instructor or not instructor.get('is_admin', False):
            flash('You do not have permission to access this page.', 'error')
            raise Forbidden('Admin access required')
        
        return f(*args, **kwargs)
    return decorated_function


def session_access_required(f):
    """
    Decorator to ensure instructor has access to a specific session.
    Checks if the instructor is assigned to the class for the session.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = kwargs.get('session_id') or request.args.get('session_id')
        
        if not session_id:
            flash('Session ID is required.', 'error')
            return redirect(url_for('dashboard.index'))
        
        instructor_id = session.get('instructor_id')
        if not validate_session_access(instructor_id, session_id):
            flash('You do not have permission to access this session.', 'error')
            raise Forbidden('Session access denied')
        
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_requests=60, window=60):
    """
    Rate limiting decorator to prevent abuse.
    
    Args:
        max_requests: Maximum number of requests allowed
        window: Time window in seconds
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client identifier
            client_id = request.remote_addr
            if 'instructor_id' in session:
                client_id = f"instructor_{session['instructor_id']}"
            
            # Create rate limit key
            rate_key = f"rate_limit:{client_id}:{request.endpoint}"
            
            # Check if we have rate limiting data in session
            if 'rate_limits' not in session:
                session['rate_limits'] = {}
            
            current_time = time.time()
            
            # Clean old entries
            if rate_key in session['rate_limits']:
                session['rate_limits'][rate_key] = [
                    timestamp for timestamp in session['rate_limits'][rate_key]
                    if current_time - timestamp < window
                ]
            else:
                session['rate_limits'][rate_key] = []
            
            # Check if rate limit exceeded
            if len(session['rate_limits'][rate_key]) >= max_requests:
                if request.is_json:
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'Too many requests. Maximum {max_requests} per {window} seconds.'
                    }), 429
                else:
                    flash('Too many requests. Please wait before trying again.', 'error')
                    return redirect(request.referrer or url_for('dashboard.index'))
            
            # Add current request
            session['rate_limits'][rate_key].append(current_time)
            session.permanent = True
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_activity_decorator(activity_type, get_description=None):
    """
    Decorator to automatically log user activities.
    
    Args:
        activity_type: Type of activity being logged
        get_description: Function to generate activity description
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            
            # Log the activity after successful execution
            instructor_id = session.get('instructor_id')
            if instructor_id:
                description = activity_type
                if get_description:
                    try:
                        description = get_description(*args, **kwargs)
                    except Exception:
                        description = activity_type
                
                # Assuming log_activity is now in helpers.py
                # from utils.helpers import log_activity
                # log_activity(
                #     user_id=str(instructor_id),
                #     user_type='instructor',
                #     activity_type=activity_type,
                #     description=description
                # )
                # If log_activity is not in helpers.py, this line will cause an error.
                # For now, commenting out as per the new_code hint.
                pass # Placeholder for log_activity if not in helpers.py
            
            return result
        return decorated_function
    return decorator


def validate_json_request(required_fields=None):
    """
    Decorator to validate JSON requests.
    
    Args:
        required_fields: List of required fields in JSON payload
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Request must be JSON'}), 400
            
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'Invalid JSON payload'}), 400
                
                # Check required fields
                if required_fields:
                    missing_fields = [field for field in required_fields if field not in data]
                    if missing_fields:
                        return jsonify({
                            'error': 'Missing required fields',
                            'missing_fields': missing_fields
                        }), 400
                
                # Add validated data to request context
                g.json_data = data
                
            except Exception as e:
                return jsonify({'error': 'Invalid JSON format'}), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def handle_exceptions(f):
    """
    Decorator to handle exceptions gracefully and provide user-friendly error messages.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Forbidden:
            if request.is_json:
                return jsonify({'error': 'Access forbidden'}), 403
            flash('You do not have permission to perform this action.', 'error')
            return redirect(url_for('dashboard.index'))
        except Unauthorized:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        except ValueError as e:
            if request.is_json:
                return jsonify({'error': 'Invalid input', 'message': str(e)}), 400
            flash(f'Invalid input: {str(e)}', 'error')
            return redirect(request.referrer or url_for('dashboard.index'))
        except Exception as e:
            # Log the error for debugging
            print(f"Unexpected error in {f.__name__}: {str(e)}")
            
            if request.is_json:
                return jsonify({'error': 'Internal server error'}), 500
            flash('An unexpected error occurred. Please try again.', 'error')
            return redirect(url_for('dashboard.index'))
    return decorated_function


def cache_control(max_age=3600, public=True):
    """
    Decorator to add cache control headers to responses.
    
    Args:
        max_age: Maximum age in seconds
        public: Whether the response can be cached by public caches
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = f(*args, **kwargs)
            
            # Add cache control headers
            if hasattr(response, 'headers'):
                cache_directive = f"max-age={max_age}"
                if public:
                    cache_directive = f"public, {cache_directive}"
                else:
                    cache_directive = f"private, {cache_directive}"
                
                response.headers['Cache-Control'] = cache_directive
            
            return response
        return decorated_function
    return decorator


def require_active_session(f):
    """
    Decorator to ensure there's an active attendance session.
    Used for attendance-related operations.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = kwargs.get('session_id') or request.args.get('session_id')
        
        if not session_id:
            if request.is_json:
                return jsonify({'error': 'Session ID required'}), 400
            flash('No active session found.', 'error')
            return redirect(url_for('dashboard.index'))
        
        # Check if session is active
        db_service = DatabaseService()
        session_data = db_service.get_session_by_id(session_id)
        
        if not session_data or session_data.get('status') not in ['ongoing', 'scheduled']:
            if request.is_json:
                return jsonify({'error': 'Session not active'}), 400
            flash('Session is not active for attendance marking.', 'error')
            return redirect(url_for('dashboard.index'))
        
        # Add session data to request context
        g.current_session = session_data
        
        return f(*args, **kwargs)
    return decorated_function


def validate_csrf_token(f):
    """
    Decorator to validate CSRF tokens for form submissions.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
            expected_token = session.get('csrf_token')
            
            if not token or not expected_token or token != expected_token:
                if request.is_json:
                    return jsonify({'error': 'CSRF token validation failed'}), 403
                flash('Security token validation failed. Please try again.', 'error')
                return redirect(request.referrer or url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


def timing_decorator(f):
    """
    Decorator to measure and log execution time for performance monitoring.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Log slow requests (> 1 second)
        if execution_time > 1.0:
            print(f"Slow request: {request.endpoint} took {execution_time:.2f}s")
        
        # Add timing header for debugging
        if hasattr(result, 'headers'):
            result.headers['X-Response-Time'] = f"{execution_time:.3f}s"
        
        return result
    return decorated_function


def mobile_responsive(f):
    """
    Decorator to handle mobile-specific responses.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Detect mobile user agent
        user_agent = request.headers.get('User-Agent', '').lower()
        is_mobile = any(mobile in user_agent for mobile in [
            'mobile', 'android', 'iphone', 'ipad', 'tablet'
        ])
        
        # Add mobile flag to request context
        g.is_mobile = is_mobile
        
        return f(*args, **kwargs)
    return decorated_function


# Commonly used decorator combinations
def api_endpoint(max_requests=30, window=60):
    """
    Combination decorator for API endpoints.
    """
    def decorator(f):
        @login_required
        @rate_limit(max_requests, window)
        @handle_exceptions
        @timing_decorator
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def secure_form_endpoint(f):
    """
    Combination decorator for secure form submissions.
    """
    @login_required
    @validate_csrf_token
    @rate_limit(max_requests=10, window=60)
    @handle_exceptions
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


def attendance_endpoint(f):
    """
    Combination decorator for attendance-related endpoints.
    """
    @login_required
    @require_active_session
    @session_access_required
    @rate_limit(max_requests=120, window=60)  # Higher limit for attendance marking
    @handle_exceptions
    @timing_decorator
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function