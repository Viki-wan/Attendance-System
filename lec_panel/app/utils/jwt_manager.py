"""
JWT Token Manager
Handles token generation, validation, and refresh
"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, current_app
from typing import Dict, Optional, Tuple
import secrets


class JWTManager:
    """JWT token management"""
    
    @staticmethod
    def generate_token(user_id: str, user_type: str = 'instructor',
                       expires_in: int = 3600) -> str:
        """
        Generate JWT access token
        
        Args:
            user_id: User identifier
            user_type: Type of user (instructor, student, admin)
            expires_in: Token expiration in seconds (default 1 hour)
            
        Returns:
            JWT token string
        """
        payload = {
            'user_id': user_id,
            'user_type': user_type,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'jti': secrets.token_urlsafe(16)  # JWT ID for revocation
        }
        
        secret_key = current_app.config.get('SECRET_KEY', 'dev-secret-key')
        token = jwt.encode(payload, secret_key, algorithm='HS256')
        return token
    
    @staticmethod
    def generate_refresh_token(user_id: str, user_type: str = 'instructor') -> str:
        """
        Generate refresh token (30 days expiration)
        
        Args:
            user_id: User identifier
            user_type: Type of user
            
        Returns:
            Refresh token string
        """
        return JWTManager.generate_token(
            user_id, 
            user_type, 
            expires_in=30 * 24 * 3600  # 30 days
        )
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """
        Decode and validate JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            secret_key = current_app.config.get('SECRET_KEY', 'dev-secret-key')
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return None  # Token expired
        except jwt.InvalidTokenError:
            return None  # Invalid token
    
    @staticmethod
    def verify_token(token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verify token and return validation result
        
        Args:
            token: JWT token string
            
        Returns:
            Tuple of (is_valid, payload, error_message)
        """
        try:
            secret_key = current_app.config.get('SECRET_KEY', 'dev-secret-key')
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return True, payload, None
        except jwt.ExpiredSignatureError:
            return False, None, "Token has expired"
        except jwt.InvalidTokenError as e:
            return False, None, f"Invalid token: {str(e)}"
    
    @staticmethod
    def extract_token_from_header() -> Optional[str]:
        """
        Extract token from Authorization header
        
        Returns:
            Token string or None
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        return parts[1]
    
    @staticmethod
    def get_current_user_from_token() -> Optional[Dict]:
        """
        Get current user information from request token
        
        Returns:
            User info dict or None
        """
        token = JWTManager.extract_token_from_header()
        if not token:
            return None
        
        payload = JWTManager.decode_token(token)
        return payload


def jwt_required(f):
    """
    Decorator to require valid JWT token
    
    Usage:
        @jwt_required
        def protected_route():
            # Access current_user via g.current_user
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import g
        from app.utils.api_response import APIResponse
        
        token = JWTManager.extract_token_from_header()
        if not token:
            return APIResponse.unauthorized("Token is missing")
        
        is_valid, payload, error_msg = JWTManager.verify_token(token)
        if not is_valid:
            return APIResponse.unauthorized(error_msg)
        
        # Store user info in Flask's g object
        g.current_user = payload
        g.user_id = payload.get('user_id')
        g.user_type = payload.get('user_type')
        
        return f(*args, **kwargs)
    
    return decorated_function


def instructor_api_required(f):
    """
    Decorator to require instructor JWT token
    
    Usage:
        @instructor_api_required
        def instructor_only_route():
            pass
    """
    @wraps(f)
    @jwt_required
    def decorated_function(*args, **kwargs):
        from flask import g
        from app.utils.api_response import APIResponse
        
        if g.user_type != 'instructor':
            return APIResponse.forbidden("Instructor access required")
        
        return f(*args, **kwargs)
    
    return decorated_function


def api_owns_resource(resource_type: str):
    """
    Decorator to verify ownership of resource
    
    Args:
        resource_type: Type of resource (session, class, etc.)
        
    Usage:
        @api_owns_resource('session')
        def update_session(session_id):
            pass
    """
    def decorator(f):
        @wraps(f)
        @instructor_api_required
        def decorated_function(*args, **kwargs):
            from flask import g
            from app.utils.api_response import APIResponse
            from app.models.session import ClassSession
            from app.models.class_model import Class
            
            # Get resource ID from kwargs
            resource_id = kwargs.get(f'{resource_type}_id')
            if not resource_id:
                return APIResponse.error("Resource ID not provided")
            
            # Check ownership based on resource type
            if resource_type == 'session':
                resource = ClassSession.query.get(resource_id)
                if not resource:
                    return APIResponse.not_found("Session")
                if resource.created_by != g.user_id:
                    return APIResponse.forbidden("You don't own this session")
                    
            elif resource_type == 'class':
                resource = Class.query.get(resource_id)
                if not resource:
                    return APIResponse.not_found("Class")
                # Check if instructor is assigned to this class
                from app.models.class_instructor import ClassInstructor
                assignment = ClassInstructor.query.filter_by(
                    class_id=resource_id,
                    instructor_id=g.user_id
                ).first()
                if not assignment:
                    return APIResponse.forbidden("You are not assigned to this class")
            
            # Store resource in g for use in route
            g.resource = resource
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator