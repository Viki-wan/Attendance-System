"""
API Authentication Endpoints
JWT-based authentication for API access
"""
from flask import Blueprint, request, g
from werkzeug.security import check_password_hash
from app.utils.api_response import APIResponse
from app.utils.jwt_manager import JWTManager, jwt_required
from app.middleware.rate_limiter import rate_limit
from app.models.user import Instructor
from app.models.activity_log import ActivityLog
from app import db
from datetime import datetime

bp = Blueprint('api_auth', __name__, url_prefix='/api/v1/auth')


@bp.route('/login', methods=['POST'])
@rate_limit(limit=10, window=900)  # 10 requests per 15 minutes
def login():
    """
    Authenticate user and return JWT token
    
    Request Body:
        {
            "instructor_id": "string",
            "password": "string"
        }
    
    Returns:
        {
            "success": true,
            "message": "Login successful",
            "data": {
                "access_token": "jwt_token",
                "refresh_token": "refresh_token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "user": {
                    "instructor_id": "...",
                    "instructor_name": "...",
                    "email": "...",
                    "faculty": "..."
                }
            }
        }
    """
    data = request.get_json()
    
    # Validation
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    instructor_id = data.get('instructor_id')
    password = data.get('password')
    
    if not instructor_id or not password:
        return APIResponse.validation_error({
            'instructor_id': 'Instructor ID is required' if not instructor_id else None,
            'password': 'Password is required' if not password else None
        })
    
    # Find instructor
    instructor = Instructor.query.filter_by(instructor_id=instructor_id).first()
    
    if not instructor or not check_password_hash(instructor.password, password):
        # Log failed attempt
        ActivityLog.log_activity(
            user_id=instructor_id,
            user_type='instructor',
            activity_type='failed_api_login',
            description=f'Failed API login attempt for {instructor_id}'
        )
        return APIResponse.error(
            "Invalid credentials",
            error_code='INVALID_CREDENTIALS',
            status_code=401
        )
    
    # Check if account is active
    if not instructor.is_active:
        return APIResponse.error(
            "Account is deactivated",
            error_code='ACCOUNT_INACTIVE',
            status_code=403
        )
    
    # Generate tokens
    access_token = JWTManager.generate_token(
        user_id=instructor.instructor_id,
        user_type='instructor',
        expires_in=3600  # 1 hour
    )
    
    refresh_token = JWTManager.generate_refresh_token(
        user_id=instructor.instructor_id,
        user_type='instructor'
    )
    
    # Update last login
    instructor.last_login = datetime.utcnow()
    db.session.commit()
    
    # Log successful login
    ActivityLog.log_activity(
        user_id=instructor.instructor_id,
        user_type='instructor',
        activity_type='api_login',
        description=f'Successful API login for {instructor.instructor_name}'
    )
    
    # Response data
    response_data = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'expires_in': 3600,
        'user': {
            'instructor_id': instructor.instructor_id,
            'instructor_name': instructor.instructor_name,
            'email': instructor.email,
            'faculty': instructor.faculty,
            'phone': instructor.phone
        }
    }
    
    return APIResponse.success(
        data=response_data,
        message="Login successful"
    )


@bp.route('/refresh', methods=['POST'])
@rate_limit(limit=20, window=3600)  # 20 requests per hour
def refresh_token():
    """
    Refresh access token using refresh token
    
    Request Body:
        {
            "refresh_token": "string"
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "access_token": "new_jwt_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        }
    """
    data = request.get_json()
    
    if not data or not data.get('refresh_token'):
        return APIResponse.error("Refresh token is required", status_code=400)
    
    refresh_token = data.get('refresh_token')
    
    # Verify refresh token
    is_valid, payload, error_msg = JWTManager.verify_token(refresh_token)
    
    if not is_valid:
        return APIResponse.unauthorized(f"Invalid refresh token: {error_msg}")
    
    # Generate new access token
    access_token = JWTManager.generate_token(
        user_id=payload['user_id'],
        user_type=payload['user_type'],
        expires_in=3600
    )
    
    response_data = {
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': 3600
    }
    
    return APIResponse.success(
        data=response_data,
        message="Token refreshed successfully"
    )


@bp.route('/logout', methods=['POST'])
@jwt_required
def logout():
    """
    Logout user (token revocation)
    Note: Actual revocation requires Redis/database token blacklist
    
    Returns:
        {
            "success": true,
            "message": "Logged out successfully"
        }
    """
    # Log logout activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type=g.user_type,
        activity_type='api_logout',
        description=f'API logout for {g.user_id}'
    )
    
    # In production, add token to blacklist in Redis
    # redis_client.setex(f"blacklist:{token}", expiration, "1")
    
    return APIResponse.success(message="Logged out successfully")


@bp.route('/verify', methods=['GET'])
@jwt_required
def verify_token():
    """
    Verify current token validity
    
    Returns:
        {
            "success": true,
            "data": {
                "user_id": "...",
                "user_type": "...",
                "expires_at": "..."
            }
        }
    """
    token = JWTManager.extract_token_from_header()
    is_valid, payload, error_msg = JWTManager.verify_token(token)
    
    if not is_valid:
        return APIResponse.unauthorized(error_msg)
    
    response_data = {
        'user_id': payload['user_id'],
        'user_type': payload['user_type'],
        'issued_at': payload['iat'],
        'expires_at': payload['exp']
    }
    
    return APIResponse.success(
        data=response_data,
        message="Token is valid"
    )


@bp.route('/change-password', methods=['POST'])
@jwt_required
def change_password():
    """
    Change user password
    
    Request Body:
        {
            "current_password": "string",
            "new_password": "string"
        }
    
    Returns:
        {
            "success": true,
            "message": "Password changed successfully"
        }
    """
    from werkzeug.security import generate_password_hash
    
    data = request.get_json()
    
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    # Validation
    if not current_password or not new_password:
        return APIResponse.validation_error({
            'current_password': 'Current password is required' if not current_password else None,
            'new_password': 'New password is required' if not new_password else None
        })
    
    if len(new_password) < 8:
        return APIResponse.validation_error({
            'new_password': 'Password must be at least 8 characters'
        })
    
    # Get instructor
    instructor = Instructor.query.filter_by(instructor_id=g.user_id).first()
    
    if not instructor:
        return APIResponse.not_found("Instructor")
    
    # Verify current password
    if not check_password_hash(instructor.password, current_password):
        return APIResponse.error(
            "Current password is incorrect",
            error_code='INVALID_PASSWORD',
            status_code=400
        )
    
    # Update password
    instructor.password = generate_password_hash(new_password)
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='password_change',
        description='Password changed via API'
    )
    
    return APIResponse.success(message="Password changed successfully")


@bp.route('/profile', methods=['GET'])
@jwt_required
def get_profile():
    """
    Get current user profile
    
    Returns:
        {
            "success": true,
            "data": {
                "instructor_id": "...",
                "instructor_name": "...",
                "email": "...",
                "phone": "...",
                "faculty": "...",
                "created_at": "...",
                "last_login": "..."
            }
        }
    """
    instructor = Instructor.query.filter_by(instructor_id=g.user_id).first()
    
    if not instructor:
        return APIResponse.not_found("Instructor")
    
    profile_data = {
        'instructor_id': instructor.instructor_id,
        'instructor_name': instructor.instructor_name,
        'email': instructor.email,
        'phone': instructor.phone,
        'faculty': instructor.faculty,
        'created_at': instructor.created_at.isoformat() if instructor.created_at else None,
        'last_login': instructor.last_login.isoformat() if instructor.last_login else None,
        'is_active': instructor.is_active
    }
    
    return APIResponse.success(
        data=profile_data,
        message="Profile retrieved successfully"
    )


@bp.route('/profile', methods=['PUT'])
@jwt_required
@rate_limit(limit=20, window=3600)  # 20 updates per hour
def update_profile():
    """
    Update user profile
    
    Request Body:
        {
            "instructor_name": "string",
            "email": "string",
            "phone": "string",
            "faculty": "string"
        }
    
    Returns:
        {
            "success": true,
            "message": "Profile updated successfully"
        }
    """
    data = request.get_json()
    
    if not data:
        return APIResponse.error("Request body is required", status_code=400)
    
    instructor = Instructor.query.filter_by(instructor_id=g.user_id).first()
    
    if not instructor:
        return APIResponse.not_found("Instructor")
    
    # Update fields if provided
    if 'instructor_name' in data:
        instructor.instructor_name = data['instructor_name']
    
    if 'email' in data:
        # Check if email already exists
        existing = Instructor.query.filter(
            Instructor.email == data['email'],
            Instructor.instructor_id != g.user_id
        ).first()
        if existing:
            return APIResponse.validation_error({
                'email': 'Email already in use'
            })
        instructor.email = data['email']
    
    if 'phone' in data:
        instructor.phone = data['phone']
    
    if 'faculty' in data:
        instructor.faculty = data['faculty']
    
    db.session.commit()
    
    # Log activity
    ActivityLog.log_activity(
        user_id=g.user_id,
        user_type='instructor',
        activity_type='profile_update',
        description='Profile updated via API'
    )
    
    return APIResponse.success(message="Profile updated successfully")