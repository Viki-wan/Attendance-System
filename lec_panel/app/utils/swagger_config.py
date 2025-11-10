# app/utils/swagger_config.py
"""
Swagger/OpenAPI Configuration for Flask Attendance System API
"""

from flask import Blueprint
from flask_swagger_ui import get_swaggerui_blueprint
from flask import jsonify, current_app
import json

# Swagger UI Configuration
SWAGGER_URL = '/api/docs'
API_URL = '/api/swagger.json'

# Create Swagger UI blueprint
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "Face Recognition Attendance System API",
        'defaultModelsExpandDepth': 3,
        'defaultModelExpandDepth': 3,
        'docExpansion': 'list',
        'supportedSubmitMethods': ['get', 'post', 'put', 'delete', 'patch'],
        'validatorUrl': None
    }
)


def get_swagger_spec():
    """Generate OpenAPI 3.0 specification"""
    
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Face Recognition Attendance System API",
            "description": """
# Face Recognition Attendance System API

This API provides endpoints for managing attendance sessions using face recognition technology.

## Authentication
All endpoints (except `/auth/login`) require JWT authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your_token>
```

## Ownership & Access Control
- Instructors can only access their own sessions and related data
- All endpoints validate ownership before returning data
- Attempting to access unauthorized resources returns 403 Forbidden

## Rate Limiting
- API requests are limited to 100 per hour per user
- Rate limit info is included in response headers

## Pagination
List endpoints support pagination using `page` and `per_page` query parameters:
- Default: `page=1`, `per_page=20`
- Maximum: `per_page=100`
            """,
            "version": "1.0.0",
            "contact": {
                "name": "API Support",
                "email": "support@attendance-system.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": "/api/v1",
                "description": "Production API"
            },
            {
                "url": "http://localhost:5000/api/v1",
                "description": "Development API"
            }
        ],
        "tags": [
            {
                "name": "Authentication",
                "description": "User authentication and token management"
            },
            {
                "name": "Sessions",
                "description": "Class session management"
            },
            {
                "name": "Attendance",
                "description": "Attendance marking and retrieval"
            },
            {
                "name": "Students",
                "description": "Student management"
            },
            {
                "name": "Reports",
                "description": "Attendance reports and analytics"
            },
            {
                "name": "Classes",
                "description": "Class management"
            }
        ],
        "paths": {
            "/auth/login": {
                "post": {
                    "tags": ["Authentication"],
                    "summary": "User login",
                    "description": "Authenticate user and receive JWT token",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/LoginRequest"
                                },
                                "example": {
                                    "username": "john.doe",
                                    "password": "secure_password123"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Login successful",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/LoginResponse"
                                    }
                                }
                            }
                        },
                        "401": {
                            "description": "Invalid credentials",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Error"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/auth/refresh": {
                "post": {
                    "tags": ["Authentication"],
                    "summary": "Refresh JWT token",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Token refreshed",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/TokenResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/sessions": {
                "get": {
                    "tags": ["Sessions"],
                    "summary": "List instructor's sessions",
                    "description": "Get all sessions belonging to the authenticated instructor",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "schema": {"type": "integer", "default": 1},
                            "description": "Page number"
                        },
                        {
                            "name": "per_page",
                            "in": "query",
                            "schema": {"type": "integer", "default": 20},
                            "description": "Items per page"
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["scheduled", "ongoing", "completed", "cancelled"]
                            },
                            "description": "Filter by session status"
                        },
                        {
                            "name": "date_from",
                            "in": "query",
                            "schema": {"type": "string", "format": "date"},
                            "description": "Filter sessions from this date"
                        },
                        {
                            "name": "date_to",
                            "in": "query",
                            "schema": {"type": "string", "format": "date"},
                            "description": "Filter sessions until this date"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Sessions list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SessionListResponse"
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "tags": ["Sessions"],
                    "summary": "Create new session",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/SessionCreate"
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Session created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Session"
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Error"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/sessions/{session_id}": {
                "get": {
                    "tags": ["Sessions"],
                    "summary": "Get session details",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "Session ID"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Session details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SessionDetailed"
                                    }
                                }
                            }
                        },
                        "403": {
                            "description": "Access denied - not session owner"
                        },
                        "404": {
                            "description": "Session not found"
                        }
                    }
                },
                "put": {
                    "tags": ["Sessions"],
                    "summary": "Update session",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/SessionUpdate"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Session updated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Session"
                                    }
                                }
                            }
                        }
                    }
                },
                "delete": {
                    "tags": ["Sessions"],
                    "summary": "Delete session",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "204": {
                            "description": "Session deleted"
                        }
                    }
                }
            },
            "/sessions/{session_id}/start": {
                "post": {
                    "tags": ["Sessions"],
                    "summary": "Start attendance session",
                    "description": "Start face recognition for a session",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Session started",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "message": {"type": "string"},
                                            "session_id": {"type": "integer"},
                                            "status": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/sessions/{session_id}/end": {
                "post": {
                    "tags": ["Sessions"],
                    "summary": "End attendance session",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Session ended"
                        }
                    }
                }
            },
            "/attendance": {
                "get": {
                    "tags": ["Attendance"],
                    "summary": "Get attendance records",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "query",
                            "schema": {"type": "integer"},
                            "description": "Filter by session"
                        },
                        {
                            "name": "student_id",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Filter by student"
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["Present", "Absent", "Late", "Excused"]
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Attendance records",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/AttendanceListResponse"
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "tags": ["Attendance"],
                    "summary": "Mark attendance manually",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/AttendanceCreate"
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Attendance marked"
                        }
                    }
                }
            },
            "/students": {
                "get": {
                    "tags": ["Students"],
                    "summary": "List students in instructor's classes",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "class_id",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Filter by class"
                        },
                        {
                            "name": "search",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Search by name or student ID"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Student list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/StudentListResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/students/{student_id}/attendance": {
                "get": {
                    "tags": ["Students"],
                    "summary": "Get student attendance history",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "student_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Attendance history",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/StudentAttendanceResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/reports/session/{session_id}": {
                "get": {
                    "tags": ["Reports"],
                    "summary": "Generate session report",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "session_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"}
                        },
                        {
                            "name": "format",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["json", "pdf", "excel", "csv"]
                            },
                            "description": "Report format"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Report generated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SessionReport"
                                    }
                                },
                                "application/pdf": {},
                                "application/vnd.ms-excel": {}
                            }
                        }
                    }
                }
            },
            "/classes": {
                "get": {
                    "tags": ["Classes"],
                    "summary": "List instructor's classes",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Classes list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ClassListResponse"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Enter your JWT token"
                }
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {"type": "string"},
                        "message": {"type": "string"}
                    }
                },
                "LoginRequest": {
                    "type": "object",
                    "required": ["username", "password"],
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string", "format": "password"}
                    }
                },
                "LoginResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "token": {"type": "string"},
                        "refresh_token": {"type": "string"},
                        "user": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "username": {"type": "string"},
                                "name": {"type": "string"},
                                "email": {"type": "string"}
                            }
                        }
                    }
                },
                "TokenResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "token": {"type": "string"}
                    }
                },
                "Session": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "integer"},
                        "class_id": {"type": "string"},
                        "class_name": {"type": "string"},
                        "date": {"type": "string", "format": "date"},
                        "start_time": {"type": "string", "format": "time"},
                        "end_time": {"type": "string", "format": "time"},
                        "status": {
                            "type": "string",
                            "enum": ["scheduled", "ongoing", "completed", "cancelled"]
                        },
                        "attendance_count": {"type": "integer"},
                        "total_students": {"type": "integer"},
                        "created_at": {"type": "string", "format": "date-time"}
                    }
                },
                "SessionDetailed": {
                    "allOf": [
                        {"$ref": "#/components/schemas/Session"},
                        {
                            "type": "object",
                            "properties": {
                                "attendance_records": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Attendance"}
                                },
                                "session_notes": {"type": "string"}
                            }
                        }
                    ]
                },
                "SessionCreate": {
                    "type": "object",
                    "required": ["class_id", "date", "start_time", "end_time"],
                    "properties": {
                        "class_id": {"type": "string"},
                        "date": {"type": "string", "format": "date"},
                        "start_time": {"type": "string", "format": "time"},
                        "end_time": {"type": "string", "format": "time"},
                        "session_notes": {"type": "string"}
                    }
                },
                "SessionUpdate": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "format": "date"},
                        "start_time": {"type": "string", "format": "time"},
                        "end_time": {"type": "string", "format": "time"},
                        "status": {"type": "string"},
                        "session_notes": {"type": "string"}
                    }
                },
                "SessionListResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Session"}
                        },
                        "pagination": {
                            "$ref": "#/components/schemas/Pagination"
                        }
                    }
                },
                "Attendance": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "student_id": {"type": "string"},
                        "student_name": {"type": "string"},
                        "session_id": {"type": "integer"},
                        "status": {
                            "type": "string",
                            "enum": ["Present", "Absent", "Late", "Excused"]
                        },
                        "timestamp": {"type": "string", "format": "date-time"},
                        "method": {"type": "string"},
                        "confidence_score": {"type": "number"},
                        "notes": {"type": "string"}
                    }
                },
                "AttendanceCreate": {
                    "type": "object",
                    "required": ["student_id", "session_id", "status"],
                    "properties": {
                        "student_id": {"type": "string"},
                        "session_id": {"type": "integer"},
                        "status": {"type": "string"},
                        "notes": {"type": "string"}
                    }
                },
                "AttendanceListResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Attendance"}
                        },
                        "pagination": {
                            "$ref": "#/components/schemas/Pagination"
                        }
                    }
                },
                "Student": {
                    "type": "object",
                    "properties": {
                        "student_id": {"type": "string"},
                        "fname": {"type": "string"},
                        "lname": {"type": "string"},
                        "email": {"type": "string"},
                        "course": {"type": "string"},
                        "year_of_study": {"type": "integer"},
                        "current_semester": {"type": "string"}
                    }
                },
                "StudentListResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Student"}
                        },
                        "pagination": {
                            "$ref": "#/components/schemas/Pagination"
                        }
                    }
                },
                "StudentAttendanceResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "student": {"$ref": "#/components/schemas/Student"},
                        "attendance_records": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Attendance"}
                        },
                        "statistics": {
                            "type": "object",
                            "properties": {
                                "total_sessions": {"type": "integer"},
                                "present": {"type": "integer"},
                                "absent": {"type": "integer"},
                                "late": {"type": "integer"},
                                "attendance_rate": {"type": "number"}
                            }
                        }
                    }
                },
                "SessionReport": {
                    "type": "object",
                    "properties": {
                        "session": {"$ref": "#/components/schemas/SessionDetailed"},
                        "statistics": {
                            "type": "object",
                            "properties": {
                                "present_count": {"type": "integer"},
                                "absent_count": {"type": "integer"},
                                "late_count": {"type": "integer"},
                                "attendance_rate": {"type": "number"}
                            }
                        }
                    }
                },
                "Class": {
                    "type": "object",
                    "properties": {
                        "class_id": {"type": "string"},
                        "class_name": {"type": "string"},
                        "course_code": {"type": "string"},
                        "year": {"type": "integer"},
                        "semester": {"type": "string"},
                        "student_count": {"type": "integer"}
                    }
                },
                "ClassListResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Class"}
                        }
                    }
                },
                "Pagination": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "total_items": {"type": "integer"},
                        "total_pages": {"type": "integer"},
                        "has_next": {"type": "boolean"},
                        "has_prev": {"type": "boolean"}
                    }
                }
            }
        }
    }
    
    return spec


# Blueprint for serving the spec
api_docs_bp = Blueprint('api_docs', __name__)

@api_docs_bp.route('/swagger.json')
def swagger_spec():
    """Return OpenAPI specification as JSON"""
    return jsonify(get_swagger_spec())


def init_swagger(app):
    """Initialize Swagger UI with the Flask app"""
    app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)
    app.register_blueprint(api_docs_bp, url_prefix='/api')
    
    # Add custom CSS for branding (optional)
    @app.context_processor
    def inject_swagger_url():
        return {'swagger_url': SWAGGER_URL}