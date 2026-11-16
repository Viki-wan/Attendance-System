"""
API Response Utilities
Standardized response formatting for Flask API endpoints
"""
from flask import jsonify
from typing import Any, Optional, Dict, List
from datetime import datetime


class APIResponse:
    """Standardized API response formatter"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", 
                status_code: int = 200, meta: Optional[Dict] = None) -> tuple:
        """
        Format successful API response
        
        Args:
            data: Response payload
            message: Success message
            status_code: HTTP status code
            meta: Additional metadata (pagination, etc.)
            
        Returns:
            Tuple of (jsonify response, status_code)
        """
        response = {
            'success': True,
            'message': message,
            'data': data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if meta:
            response['meta'] = meta
            
        return jsonify(response), status_code
    
    @staticmethod
    def error(message: str, error_code: str = None, 
              status_code: int = 400, details: Any = None) -> tuple:
        """
        Format error API response
        
        Args:
            message: Error message
            error_code: Custom error code
            status_code: HTTP status code
            details: Additional error details
            
        Returns:
            Tuple of (jsonify response, status_code)
        """
        response = {
            'success': False,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if error_code:
            response['error_code'] = error_code
            
        if details:
            response['details'] = details
            
        return jsonify(response), status_code
    
    @staticmethod
    def paginated(data: List, page: int, per_page: int, 
                  total: int, message: str = "Success") -> tuple:
        """
        Format paginated API response
        
        Args:
            data: List of items
            page: Current page number
            per_page: Items per page
            total: Total items count
            message: Response message
            
        Returns:
            Tuple of (jsonify response, status_code)
        """
        total_pages = (total + per_page - 1) // per_page
        
        meta = {
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        return APIResponse.success(data=data, message=message, meta=meta)
    
    @staticmethod
    def created(data: Any, message: str = "Resource created successfully",
                resource_id: Any = None) -> tuple:
        """Format response for resource creation"""
        if resource_id:
            meta = {'resource_id': resource_id}
        else:
            meta = None
            
        return APIResponse.success(
            data=data, 
            message=message, 
            status_code=201,
            meta=meta
        )
    
    @staticmethod
    def no_content(message: str = "Operation completed successfully") -> tuple:
        """Format response for successful deletion or no content"""
        return APIResponse.success(message=message, status_code=204)
    
    @staticmethod
    def unauthorized(message: str = "Authentication required") -> tuple:
        """Format unauthorized response"""
        return APIResponse.error(
            message=message,
            error_code='UNAUTHORIZED',
            status_code=401
        )
    
    @staticmethod
    def forbidden(message: str = "Access denied") -> tuple:
        """Format forbidden response"""
        return APIResponse.error(
            message=message,
            error_code='FORBIDDEN',
            status_code=403
        )
    
    @staticmethod
    def not_found(resource: str = "Resource") -> tuple:
        """Format not found response"""
        return APIResponse.error(
            message=f"{resource} not found",
            error_code='NOT_FOUND',
            status_code=404
        )
    
    @staticmethod
    def validation_error(errors: Dict) -> tuple:
        """Format validation error response"""
        return APIResponse.error(
            message="Validation failed",
            error_code='VALIDATION_ERROR',
            status_code=422,
            details=errors
        )
    
    @staticmethod
    def rate_limit_exceeded(retry_after: int = 3600) -> tuple:
        """Format rate limit exceeded response"""
        return APIResponse.error(
            message="Rate limit exceeded",
            error_code='RATE_LIMIT_EXCEEDED',
            status_code=429,
            details={'retry_after': retry_after}
        )
    
    @staticmethod
    def server_error(message: str = "Internal server error") -> tuple:
        """Format server error response"""
        return APIResponse.error(
            message=message,
            error_code='INTERNAL_ERROR',
            status_code=500
        )


# Convenience functions
def success_response(*args, **kwargs):
    """Shortcut for success response"""
    return APIResponse.success(*args, **kwargs)


def error_response(*args, **kwargs):
    """Shortcut for error response"""
    return APIResponse.error(*args, **kwargs)


def paginated_response(*args, **kwargs):
    """Shortcut for paginated response"""
    return APIResponse.paginated(*args, **kwargs)