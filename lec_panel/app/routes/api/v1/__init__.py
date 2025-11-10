"""
API v1 Package
Registers all API v1 endpoint blueprints
"""
from flask import Blueprint, jsonify
from datetime import datetime

# Create main API v1 blueprint
api_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


def register_api_blueprints(app):
    """
    Register all API v1 blueprints with the Flask app
    
    Usage in app/__init__.py:
        from app.routes.api.v1 import register_api_blueprints
        register_api_blueprints(app)
    """
    # Import blueprints here to avoid circular imports
    from app.routes.api.v1.auth import bp as auth_bp
    from app.routes.api.v1.sessions import bp as sessions_bp
    from app.routes.api.v1.attendance import bp as attendance_bp
    from app.routes.api.v1.students import bp as students_bp
    from app.routes.api.v1.classes import bp as classes_bp
    from app.routes.api.v1.reports import bp as reports_bp
    from app.routes.api.v1.dashboard import bp as dashboard_bp
    
    # Register all blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(dashboard_bp)
    
    # Register the main API info blueprint
    app.register_blueprint(api_bp)
    
    print("✅ API v1 blueprints registered successfully")
    print("   - Authentication: /api/v1/auth/*")
    print("   - Sessions: /api/v1/sessions/*")
    print("   - Attendance: /api/v1/attendance/*")
    print("   - Students: /api/v1/students/*")
    print("   - Classes: /api/v1/classes/*")
    print("   - Reports: /api/v1/reports/*")
    print("   - Dashboard: /api/v1/dashboard/*")


# API information endpoint
@api_bp.route('/', methods=['GET'])
def api_info():
    """
    Get API information and available endpoints
    
    Returns:
        API version, description, and endpoint list
    """
    return jsonify({
        'api_version': 'v1',
        'name': 'Flask Attendance System API',
        'description': 'RESTful API for Face Recognition Attendance System',
        'authentication': 'JWT Bearer Token',
        'documentation': '/api/v1/docs',
        'endpoints': {
            'authentication': {
                'login': 'POST /api/v1/auth/login',
                'refresh': 'POST /api/v1/auth/refresh',
                'logout': 'POST /api/v1/auth/logout',
                'verify': 'GET /api/v1/auth/verify',
                'profile': 'GET /api/v1/auth/profile',
                'change_password': 'POST /api/v1/auth/change-password'
            },
            'sessions': {
                'list': 'GET /api/v1/sessions',
                'get': 'GET /api/v1/sessions/<id>',
                'create': 'POST /api/v1/sessions',
                'update': 'PUT /api/v1/sessions/<id>',
                'delete': 'DELETE /api/v1/sessions/<id>',
                'statistics': 'GET /api/v1/sessions/statistics'
            },
            'attendance': {
                'get_session_attendance': 'GET /api/v1/sessions/<id>/attendance',
                'mark_attendance': 'POST /api/v1/sessions/<id>/attendance',
                'bulk_mark': 'POST /api/v1/sessions/<id>/attendance/bulk',
                'get_record': 'GET /api/v1/attendance/<id>',
                'update_record': 'PUT /api/v1/attendance/<id>',
                'delete_record': 'DELETE /api/v1/attendance/<id>',
                'summary': 'GET /api/v1/sessions/<id>/attendance/summary'
            },
            'students': {
                'list': 'GET /api/v1/students',
                'get': 'GET /api/v1/students/<id>',
                'attendance_history': 'GET /api/v1/students/<id>/attendance',
                'statistics': 'GET /api/v1/students/<id>/statistics',
                'import': 'POST /api/v1/students/import'
            },
            'classes': {
                'list': 'GET /api/v1/classes',
                'get': 'GET /api/v1/classes/<id>',
                'roster': 'GET /api/v1/classes/<id>/students',
                'sessions': 'GET /api/v1/classes/<id>/sessions',
                'statistics': 'GET /api/v1/classes/<id>/statistics'
            },
            'reports': {
                'session_report': 'GET /api/v1/reports/session/<id>',
                'class_report': 'GET /api/v1/reports/class/<id>',
                'student_report': 'GET /api/v1/reports/student/<id>',
                'custom_report': 'POST /api/v1/reports/generate'
            },
            'dashboard': {
                'stats': 'GET /api/v1/dashboard/stats',
                'today_sessions': 'GET /api/v1/dashboard/today-sessions',
                'alerts': 'GET /api/v1/dashboard/alerts',
                'notifications': 'GET /api/v1/dashboard/notifications',
                'mark_notification_read': 'POST /api/v1/dashboard/notifications/<id>/mark-read',
                'upcoming_sessions': 'GET /api/v1/dashboard/upcoming-sessions'
            }
        },
        'rate_limits': {
            'standard': '100 requests per hour',
            'login': '10 requests per 15 minutes',
            'token_refresh': '20 requests per hour'
        },
        'response_format': {
            'success': {
                'success': True,
                'message': 'string',
                'data': 'object|array',
                'timestamp': 'ISO 8601 datetime'
            },
            'error': {
                'success': False,
                'message': 'string',
                'error_code': 'string',
                'timestamp': 'ISO 8601 datetime',
                'details': 'object (optional)'
            }
        }
    }), 200


# Health check endpoint
@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    API health check
    
    Returns:
        API health status
    """
    return jsonify({
        'status': 'healthy',
        'api_version': 'v1',
        'timestamp': datetime.utcnow().isoformat(),
        'uptime': 'OK'
    }), 200


# CORS preflight handler (if CORS is enabled)
@api_bp.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """
    Handle CORS preflight requests
    """
    from flask import make_response
    
    response = make_response()
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Max-Age'] = '3600'
    
    return response, 200