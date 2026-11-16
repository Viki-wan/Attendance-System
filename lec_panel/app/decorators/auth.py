"""
Custom Authentication and Authorization Decorators
Provides role-based access control and ownership validation
"""
from functools import wraps
from flask import redirect, url_for, flash, abort, request, current_app
from flask_login import current_user
from app.models.user import Instructor


def login_required(f):
    """
    Decorator to require authentication for a route.
    Redirects to login if user is not authenticated.
    
    Usage:
        @login_required
        def my_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def active_account_required(f):
    """
    Decorator to ensure user account is active.
    Combines login requirement with active status check.
    
    Usage:
        @active_account_required
        def my_route():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        if not current_user.is_active:
            flash('Your account has been deactivated. Please contact the administrator.', 'danger')
            return redirect(url_for('auth.logout'))
        
        return f(*args, **kwargs)
    return decorated_function


def owns_session(f):
    """
    Decorator to verify instructor owns/created the session.
    Expects 'session_id' parameter in route or request args.
    
    Usage:
        @owns_session
        def view_session(session_id):
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Get session_id from route parameters or query string
        session_id = kwargs.get('session_id') or request.args.get('session_id')
        
        if not session_id:
            current_app.logger.warning(f"Session ownership check failed: No session_id provided")
            abort(400, description="Session ID is required")
        
        # Check ownership
        if not current_user.owns_session(session_id):
            current_app.logger.warning(
                f"Unauthorized session access attempt by {current_user.instructor_id} "
                f"for session {session_id}"
            )
            abort(403, description="You don't have permission to access this session")
        
        return f(*args, **kwargs)
    return decorated_function


def owns_class(f):
    """
    Decorator to verify instructor is assigned to the class.
    Expects 'class_id' parameter in route or request args.
    
    Usage:
        @owns_class
        def view_class(class_id):
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Get class_id from route parameters or query string
        class_id = kwargs.get('class_id') or request.args.get('class_id')
        
        if not class_id:
            current_app.logger.warning(f"Class ownership check failed: No class_id provided")
            abort(400, description="Class ID is required")
        
        # Check ownership
        if not current_user.owns_class(class_id):
            current_app.logger.warning(
                f"Unauthorized class access attempt by {current_user.instructor_id} "
                f"for class {class_id}"
            )
            abort(403, description="You don't have permission to access this class")
        
        return f(*args, **kwargs)
    return decorated_function


def instructor_only(f):
    """
    Decorator to restrict access to instructors only.
    Can be extended later if other user types are added (admin, student).
    
    Usage:
        @instructor_only
        def instructor_dashboard():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Check if user is an Instructor instance
        if not isinstance(current_user._get_current_object(), Instructor):
            current_app.logger.warning(
                f"Non-instructor access attempt to instructor-only route by {current_user.get_id()}"
            )
            abort(403, description="This page is only accessible to instructors")
        
        return f(*args, **kwargs)
    return decorated_function


def owns_course(f):
    """
    Decorator to verify instructor teaches the course.
    Expects 'course_code' parameter in route or request args.
    
    Usage:
        @owns_course
        def view_course(course_code):
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Get course_code from route parameters or query string
        course_code = kwargs.get('course_code') or request.args.get('course_code')
        
        if not course_code:
            current_app.logger.warning(f"Course ownership check failed: No course_code provided")
            abort(400, description="Course code is required")
        
        # Check if instructor teaches this course
        from app.models.associations import instructor_courses
        from app import db
        
        result = db.session.query(instructor_courses).filter_by(
            instructor_id=current_user.instructor_id,
            course_code=course_code
        ).first()
        
        if not result:
            current_app.logger.warning(
                f"Unauthorized course access attempt by {current_user.instructor_id} "
                f"for course {course_code}"
            )
            abort(403, description="You don't have permission to access this course")
        
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """
    Decorator for API endpoints that require authentication.
    Returns JSON error responses instead of redirects.
    
    Usage:
        @api_login_required
        def api_endpoint():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return {
                'success': False,
                'error': 'Authentication required',
                'message': 'Please log in to access this endpoint'
            }, 401
        
        return f(*args, **kwargs)
    return decorated_function


def api_owns_session(f):
    """
    API version of owns_session decorator.
    Returns JSON error responses.
    
    Usage:
        @api_owns_session
        def api_session_endpoint(session_id):
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return {
                'success': False,
                'error': 'Authentication required',
                'message': 'Please log in to access this endpoint'
            }, 401
        
        # Get session_id from route parameters or request JSON
        session_id = kwargs.get('session_id')
        if not session_id and request.is_json:
            session_id = request.json.get('session_id')
        
        if not session_id:
            return {
                'success': False,
                'error': 'Missing parameter',
                'message': 'session_id is required'
            }, 400
        
        # Check ownership
        if not current_user.owns_session(session_id):
            current_app.logger.warning(
                f"API: Unauthorized session access by {current_user.instructor_id} "
                f"for session {session_id}"
            )
            return {
                'success': False,
                'error': 'Forbidden',
                'message': 'You don\'t have permission to access this session'
            }, 403
        
        return f(*args, **kwargs)
    return decorated_function


def api_owns_class(f):
    """
    API version of owns_class decorator.
    Returns JSON error responses.
    
    Usage:
        @api_owns_class
        def api_class_endpoint(class_id):
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return {
                'success': False,
                'error': 'Authentication required',
                'message': 'Please log in to access this endpoint'
            }, 401
        
        # Get class_id from route parameters or request JSON
        class_id = kwargs.get('class_id')
        if not class_id and request.is_json:
            class_id = request.json.get('class_id')
        
        if not class_id:
            return {
                'success': False,
                'error': 'Missing parameter',
                'message': 'class_id is required'
            }, 400
        
        # Check ownership
        if not current_user.owns_class(class_id):
            current_app.logger.warning(
                f"API: Unauthorized class access by {current_user.instructor_id} "
                f"for class {class_id}"
            )
            return {
                'success': False,
                'error': 'Forbidden',
                'message': 'You don\'t have permission to access this class'
            }, 403
        
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(max_requests=100, window=3600):
    """
    Simple rate limiting decorator using session storage.
    For production, use Redis-based rate limiting.
    
    Args:
        max_requests (int): Maximum requests allowed
        window (int): Time window in seconds
    
    Usage:
        @rate_limit(max_requests=10, window=60)
        def my_route():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This is a placeholder - implement Redis-based rate limiting in production
            # For now, just pass through
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """
    Decorator for admin-only routes.
    Placeholder for future admin functionality.
    
    Usage:
        @admin_required
        def admin_dashboard():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Check if user is admin (will be implemented when admin model is created)
        # For now, deny all access
        abort(403, description="Admin access required")
        
        return f(*args, **kwargs)
    return decorated_function


# Utility function for checking multiple ownerships
def check_ownership(resource_type, resource_id):
    """
    Generic ownership checking function.
    
    Args:
        resource_type (str): Type of resource ('session', 'class', 'course')
        resource_id: ID of the resource
        
    Returns:
        bool: True if current user owns the resource
    """
    if not current_user.is_authenticated:
        return False
    
    if resource_type == 'session':
        return current_user.owns_session(resource_id)
    elif resource_type == 'class':
        return current_user.owns_class(resource_id)
    elif resource_type == 'course':
        from app.models.associations import instructor_courses
        from app import db
        
        result = db.session.query(instructor_courses).filter_by(
            instructor_id=current_user.instructor_id,
            course_code=resource_id
        ).first()
        return result is not None
    
    return False

def instructor_required(f):
    """
    Decorator to ensure user is an instructor
    Usage: @instructor_required
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('auth.login', next=request.url))
        
        # Check if user has instructor_id attribute
        if not hasattr(current_user, 'instructor_id'):
            flash('Access denied: Instructor privileges required', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

# Create alias for consistency with route naming
lecturer_required = instructor_required