# app/models/lecturer_preferences.py
"""
Lecturer Preferences Model
Stores UI preferences, notification settings, and system behavior preferences for instructors.
"""

from app import db
from datetime import datetime
from sqlalchemy.dialects.sqlite import JSON


class LecturerPreference(db.Model):
    """Model for storing instructor preferences."""
    
    __tablename__ = 'lecturer_preferences'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key
    instructor_id = db.Column(
        db.String(50), 
        db.ForeignKey('instructors.instructor_id'),
        nullable=False,
        unique=True
    )
    
    # UI Preferences
    theme = db.Column(db.String(20), default='light', nullable=False)
    dashboard_layout = db.Column(db.String(50), default='default', nullable=False)
    
    # Notification Settings (stored as JSON)
    notification_settings = db.Column(
        JSON,
        default={
            'email_notifications': True,
            'push_notifications': True,
            'attendance_alerts': True,
            'session_reminders': True,
            'low_attendance_threshold': 75
        }
    )
    
    # System Behavior
    auto_refresh_interval = db.Column(db.Integer, default=30, nullable=False)  # seconds
    default_session_duration = db.Column(db.Integer, default=90, nullable=False)  # minutes
    
    # Localization
    timezone = db.Column(db.String(50), default='UTC', nullable=False)
    language = db.Column(db.String(10), default='en', nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    instructor = db.relationship(
        'Instructor',
        back_populates='preferences',
        foreign_keys=[instructor_id]
    )
    
    def __repr__(self):
        return f'<LecturerPreference {self.instructor_id} - Theme: {self.theme}>'
    
    def to_dict(self):
        """Convert preference object to dictionary."""
        return {
            'id': self.id,
            'instructor_id': self.instructor_id,
            'theme': self.theme,
            'dashboard_layout': self.dashboard_layout,
            'notification_settings': self.notification_settings,
            'auto_refresh_interval': self.auto_refresh_interval,
            'default_session_duration': self.default_session_duration,
            'timezone': self.timezone,
            'language': self.language,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def email_notifications_enabled(self):
        """Check if email notifications are enabled."""
        return self.notification_settings.get('email_notifications', True)
    
    @property
    def push_notifications_enabled(self):
        """Check if push notifications are enabled."""
        return self.notification_settings.get('push_notifications', True)
    
    @property
    def attendance_alerts_enabled(self):
        """Check if attendance alerts are enabled."""
        return self.notification_settings.get('attendance_alerts', True)
    
    @property
    def session_reminders_enabled(self):
        """Check if session reminders are enabled."""
        return self.notification_settings.get('session_reminders', True)
    
    @property
    def low_attendance_threshold(self):
        """Get low attendance threshold percentage."""
        return self.notification_settings.get('low_attendance_threshold', 75)
    
    def is_dark_mode(self):
        """Check if dark mode is enabled."""
        return self.theme == 'dark'
    
    def should_send_notification(self, notification_type):
        """
        Check if a specific notification type should be sent.
        
        Args:
            notification_type: Type of notification (email, push, attendance_alert, session_reminder)
            
        Returns:
            bool: True if notification should be sent
        """
        type_map = {
            'email': 'email_notifications',
            'push': 'push_notifications',
            'attendance_alert': 'attendance_alerts',
            'session_reminder': 'session_reminders'
        }
        
        setting_key = type_map.get(notification_type)
        if setting_key:
            return self.notification_settings.get(setting_key, True)
        
        return True
    
    def update_notification_setting(self, key, value):
        """
        Update a specific notification setting.
        
        Args:
            key: Setting key
            value: New value
        """
        if self.notification_settings is None:
            self.notification_settings = {}
        
        self.notification_settings[key] = value
        self.updated_at = datetime.utcnow()
    
    @staticmethod
    def get_default_preferences():
        """Get default preference values as dictionary."""
        return {
            'theme': 'light',
            'dashboard_layout': 'default',
            'notification_settings': {
                'email_notifications': True,
                'push_notifications': True,
                'attendance_alerts': True,
                'session_reminders': True,
                'low_attendance_threshold': 75
            },
            'auto_refresh_interval': 30,
            'default_session_duration': 90,
            'timezone': 'UTC',
            'language': 'en'
        }