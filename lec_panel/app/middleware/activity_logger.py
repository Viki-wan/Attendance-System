# app/middleware/activity_logger.py
"""
Activity logging middleware for audit trails and security monitoring.
Tracks all user actions for compliance and debugging purposes.
"""

from app.models.activity_log import ActivityLog
from app import db
from flask import request, g
from flask_login import current_user
from datetime import datetime
import json


class ActivityLogger:
    """Middleware for logging user activities."""
    
    # Activity type constants
    AUTH_LOGIN = 'auth_login'
    AUTH_LOGOUT = 'auth_logout'
    AUTH_FAILED = 'auth_failed'
    
    SESSION_CREATE = 'session_create'
    SESSION_START = 'session_start'
    SESSION_END = 'session_end'
    SESSION_DISMISS = 'session_dismiss'
    
    ATTENDANCE_MARK = 'attendance_mark'
    ATTENDANCE_EDIT = 'attendance_edit'
    ATTENDANCE_DELETE = 'attendance_delete'
    
    STUDENT_CREATE = 'student_create'
    STUDENT_UPDATE = 'student_update'
    STUDENT_DELETE = 'student_delete'
    
    CLASS_CREATE = 'class_create'
    CLASS_UPDATE = 'class_update'
    CLASS_DELETE = 'class_delete'
    
    REPORT_GENERATE = 'report_generate'
    REPORT_EXPORT = 'report_export'
    
    SETTINGS_UPDATE = 'settings_update'
    PREFERENCES_UPDATE = 'preferences_update'
    
    @staticmethod
    def log_activity(user_id, user_type, activity_type, description=None, extra_data=None):
        """
        Log an activity to the database.
        
        Args:
            user_id: User identifier
            user_type: 'instructor', 'student', or 'admin'
            activity_type: Type of activity (use constants)
            description: Human-readable description
            extra_data: Dictionary of additional data
        """
        try:
            # Build description
            if description is None:
                description = ActivityLogger._generate_description(
                    activity_type, extra_data
                )
            
            # Add request context if available
            if extra_data is None:
                extra_data = {}
            
            if request:
                extra_data['ip_address'] = request.remote_addr
                extra_data['user_agent'] = request.headers.get('User-Agent', '')
                extra_data['endpoint'] = request.endpoint
                extra_data['method'] = request.method
            
            # Create log entry
            log_entry = ActivityLog(
                user_id=user_id,
                user_type=user_type,
                activity_type=activity_type,
                description=description,
                timestamp=datetime.now()
            )
            
            db.session.add(log_entry)
            db.session.commit()
            
            return log_entry
        
        except Exception as e:
            # Don't let logging failures break the app
            db.session.rollback()
            print(f"Activity logging failed: {e}")
            return None
    
    @staticmethod
    def _generate_description(activity_type, extra_data):
        """Generate human-readable description based on activity type."""
        descriptions = {
            ActivityLogger.AUTH_LOGIN: "User logged in",
            ActivityLogger.AUTH_LOGOUT: "User logged out",
            ActivityLogger.AUTH_FAILED: "Failed login attempt",
            ActivityLogger.SESSION_CREATE: "Created new session",
            ActivityLogger.SESSION_START: "Started attendance session",
            ActivityLogger.SESSION_END: "Ended attendance session",
            ActivityLogger.SESSION_DISMISS: "Dismissed session",
            ActivityLogger.ATTENDANCE_MARK: "Marked attendance",
            ActivityLogger.ATTENDANCE_EDIT: "Edited attendance record",
            ActivityLogger.ATTENDANCE_DELETE: "Deleted attendance record",
            ActivityLogger.STUDENT_CREATE: "Registered new student",
            ActivityLogger.STUDENT_UPDATE: "Updated student information",
            ActivityLogger.STUDENT_DELETE: "Deleted student",
            ActivityLogger.CLASS_CREATE: "Created new class",
            ActivityLogger.CLASS_UPDATE: "Updated class information",
            ActivityLogger.CLASS_DELETE: "Deleted class",
            ActivityLogger.REPORT_GENERATE: "Generated report",
            ActivityLogger.REPORT_EXPORT: "Exported report",
            ActivityLogger.SETTINGS_UPDATE: "Updated system settings",
            ActivityLogger.PREFERENCES_UPDATE: "Updated user preferences"
        }
        
        base_desc = descriptions.get(activity_type, "Performed activity")
        
        # Add extra context if available
        if extra_data:
            if 'session_id' in extra_data:
                base_desc += f" (Session: {extra_data['session_id']})"
            if 'student_id' in extra_data:
                base_desc += f" (Student: {extra_data['student_id']})"
            if 'class_id' in extra_data:
                base_desc += f" (Class: {extra_data['class_id']})"
        
        return base_desc
    
    @staticmethod
    def log_current_user(activity_type, description=None, **extra_data):
        """Convenience method to log activity for current user."""
        if not current_user.is_authenticated:
            return None
        
        return ActivityLogger.log_activity(
            user_id=current_user.instructor_id,
            user_type='instructor',
            activity_type=activity_type,
            description=description,
            extra_data=extra_data
        )
    
    @staticmethod
    def get_user_activities(user_id, user_type, limit=50, offset=0):
        """Retrieve activity history for a user."""
        activities = ActivityLog.query.filter(
            ActivityLog.user_id == user_id,
            ActivityLog.user_type == user_type
        ).order_by(
            ActivityLog.timestamp.desc()
        ).limit(limit).offset(offset).all()
        
        return activities
    
    @staticmethod
    def get_recent_activities(hours=24, limit=100):
        """Get recent system-wide activities."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        activities = ActivityLog.query.filter(
            ActivityLog.timestamp >= cutoff
        ).order_by(
            ActivityLog.timestamp.desc()
        ).limit(limit).all()
        
        return activities
    
    @staticmethod
    def get_activities_by_type(activity_type, limit=50):
        """Get activities of a specific type."""
        activities = ActivityLog.query.filter(
            ActivityLog.activity_type == activity_type
        ).order_by(
            ActivityLog.timestamp.desc()
        ).limit(limit).all()
        
        return activities
    
    @staticmethod
    def get_failed_login_attempts(hours=1):
        """Get recent failed login attempts for security monitoring."""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        attempts = ActivityLog.query.filter(
            ActivityLog.activity_type == ActivityLogger.AUTH_FAILED,
            ActivityLog.timestamp >= cutoff
        ).order_by(
            ActivityLog.timestamp.desc()
        ).all()
        
        return attempts
    
    @staticmethod
    def cleanup_old_logs(days=90):
        """Delete activity logs older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)
        
        deleted = ActivityLog.query.filter(
            ActivityLog.timestamp < cutoff
        ).delete()
        
        db.session.commit()
        return deleted


# Decorator for automatic activity logging
def log_activity(activity_type, description_template=None):
    """
    Decorator to automatically log activities.
    
    Usage:
        @log_activity(ActivityLogger.SESSION_START, "Started session {session_id}")
        def start_session(session_id):
            ...
    """
    def decorator(f):
        def wrapped(*args, **kwargs):
            result = f(*args, **kwargs)
            
            # Generate description
            description = description_template
            if description and kwargs:
                try:
                    description = description.format(**kwargs)
                except KeyError:
                    pass
            
            # Log the activity
            if current_user.is_authenticated:
                ActivityLogger.log_current_user(
                    activity_type=activity_type,
                    description=description,
                    **kwargs
                )
            
            return result
        
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator


from datetime import timedelta