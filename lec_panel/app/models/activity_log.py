"""
Activity Log Model
Tracks all user activities for security audit and monitoring
"""
from datetime import datetime, timedelta
from app import db
from sqlalchemy import Index


class ActivityLog(db.Model):
    __tablename__ = 'activity_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'instructor', 'student', 'admin'
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))  # IPv6 support
    user_agent = db.Column(db.String(255))
    session_id = db.Column(db.String(100))  # Flask session ID
    
    # Index for performance
    __table_args__ = (
        Index('idx_activity_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_activity_type_timestamp', 'activity_type', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<ActivityLog {self.user_id} - {self.activity_type}>'
    
    @classmethod
    def log_activity(cls, user_id, user_type, activity_type, description=None, 
                     ip_address=None, user_agent=None, session_id=None):
        """
        Convenience method to log an activity
        
        Args:
            user_id: ID of the user performing the action
            user_type: Type of user (instructor, student, admin)
            activity_type: Type of activity (login, logout, create_session, etc.)
            description: Optional detailed description
            ip_address: User's IP address
            user_agent: User's browser/client information
            session_id: Flask session identifier
        """
        log = cls(
            user_id=user_id,
            user_type=user_type,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    @classmethod
    def get_user_activities(cls, user_id, limit=50, activity_type=None):
        """Get recent activities for a specific user"""
        query = cls.query.filter_by(user_id=user_id)
        if activity_type:
            query = query.filter_by(activity_type=activity_type)
        return query.order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def get_recent_activities(cls, hours=24, user_type=None):
        """Get activities from the last N hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = cls.query.filter(cls.timestamp >= cutoff)
        if user_type:
            query = query.filter_by(user_type=user_type)
        return query.order_by(cls.timestamp.desc()).all()
    
    @classmethod
    def get_suspicious_activities(cls, hours=24):
        """Get potentially suspicious activities"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        suspicious_types = [
            'failed_login', 
            'unauthorized_access', 
            'permission_denied',
            'multiple_login_attempts'
        ]
        return cls.query.filter(
            cls.timestamp >= cutoff,
            cls.activity_type.in_(suspicious_types)
        ).order_by(cls.timestamp.desc()).all()
    
    @classmethod
    def get_login_history(cls, user_id, limit=10):
        """Get login history for a user"""
        return cls.query.filter_by(
            user_id=user_id,
            activity_type='login'
        ).order_by(cls.timestamp.desc()).limit(limit).all()
    
    @classmethod
    def cleanup_old_logs(cls, days=90):
        """Delete logs older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = cls.query.filter(cls.timestamp < cutoff).delete()
        db.session.commit()
        return deleted
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'activity_type': self.activity_type,
            'description': self.description,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent
        }


# Common activity type constants
class ActivityType:
    """Constants for activity types"""
    LOGIN = 'login'
    LOGOUT = 'logout'
    FAILED_LOGIN = 'failed_login'
    PASSWORD_CHANGE = 'password_change'
    PASSWORD_RESET = 'password_reset'
    
    CREATE_SESSION = 'create_session'
    START_ATTENDANCE = 'start_attendance'
    END_ATTENDANCE = 'end_attendance'
    MARK_ATTENDANCE = 'mark_attendance'
    EDIT_ATTENDANCE = 'edit_attendance'
    
    ADD_STUDENT = 'add_student'
    EDIT_STUDENT = 'edit_student'
    DELETE_STUDENT = 'delete_student'
    
    VIEW_REPORT = 'view_report'
    EXPORT_REPORT = 'export_report'
    
    CHANGE_SETTINGS = 'change_settings'
    UNAUTHORIZED_ACCESS = 'unauthorized_access'
    PERMISSION_DENIED = 'permission_denied'