"""
API Response Utilities
Standardized JSON response formatting for API endpoints
"""

from typing import Any, Optional, Dict
from flask import jsonify


def success_response(
    message: str = "Success",
    data: Optional[Any] = None,
    status_code: int = 200
) -> Dict:
    """
    Generate a standardized success response
    
    Args:
        message: Success message
        data: Optional data payload
        status_code: HTTP status code (default: 200)
        
    Returns:
        Dictionary with success structure
    """
    response = {
        'success': True,
        'message': message
    }
    
    if data is not None:
        response['data'] = data
    
    return response


def error_response(
    message: str = "An error occurred",
    errors: Optional[Dict] = None,
    status_code: int = 400
) -> Dict:
    """
    Generate a standardized error response
    
    Args:
        message: Error message
        errors: Optional detailed error dictionary
        status_code: HTTP status code (default: 400)
        
    Returns:
        Dictionary with error structure
    """
    response = {
        'success': False,
        'error': message
    }
    
    if errors:
        response['errors'] = errors
    
    return response


def paginated_response(
    items: list,
    page: int,
    per_page: int,
    total_items: int,
    message: str = "Success"
) -> Dict:
    """
    Generate a paginated response
    
    Args:
        items: List of items for current page
        page: Current page number
        per_page: Items per page
        total_items: Total number of items
        message: Optional message
        
    Returns:
        Dictionary with paginated structure
    """
    total_pages = (total_items + per_page - 1) // per_page
    
    return {
        'success': True,
        'message': message,
        'data': items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
    }


def validation_error_response(errors: Dict[str, list]) -> Dict:
    """
    Generate a validation error response
    
    Args:
        errors: Dictionary of field names and their error messages
        
    Returns:
        Dictionary with validation error structure
    """
    return {
        'success': False,
        'error': 'Validation failed',
        'errors': errors
    }


def not_found_response(resource: str = "Resource") -> Dict:
    """
    Generate a not found response
    
    Args:
        resource: Name of the resource that wasn't found
        
    Returns:
        Dictionary with not found structure
    """
    return {
        'success': False,
        'error': f'{resource} not found'
    }


def unauthorized_response(message: str = "Unauthorized access") -> Dict:
    """
    Generate an unauthorized response
    
    Args:
        message: Unauthorized message
        
    Returns:
        Dictionary with unauthorized structure
    """
    return {
        'success': False,
        'error': message,
        'code': 'UNAUTHORIZED'
    }


def forbidden_response(message: str = "Access denied") -> Dict:
    """
    Generate a forbidden response
    
    Args:
        message: Forbidden message
        
    Returns:
        Dictionary with forbidden structure
    """
    return {
        'success': False,
        'error': message,
        'code': 'FORBIDDEN'
    }


# Convenience function for JSON responses
def json_response(data: Dict, status_code: int = 200):
    """
    Generate a Flask JSON response
    
    Args:
        data: Response data dictionary
        status_code: HTTP status code
        
    Returns:
        Flask JSON response
    """
    response = jsonify(data)
    response.status_code = status_code
    return response