"""
System Settings Model
Stores global system configuration and settings
"""
from datetime import datetime
from app import db


class Settings(db.Model):
    __tablename__ = 'settings'
    
    setting_key = db.Column(db.String(100), primary_key=True)
    setting_value = db.Column(db.Text)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='general')
    is_system = db.Column(db.Integer, default=0)  # 1 = system setting (not user-editable)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Settings {self.setting_key}={self.setting_value}>'
    
    @classmethod
    def get_value(cls, key, default=None):
        """Get a setting value by key"""
        setting = cls.query.get(key)
        return setting.setting_value if setting else default
    
    @classmethod
    def get_int(cls, key, default=0):
        """Get setting as integer"""
        value = cls.get_value(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def get_float(cls, key, default=0.0):
        """Get setting as float"""
        value = cls.get_value(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def get_bool(cls, key, default=False):
        """Get setting as boolean"""
        value = cls.get_value(key, default)
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    @classmethod
    def set_value(cls, key, value, description=None, category='general', is_system=0):
        """Set or update a setting"""
        setting = cls.query.get(key)
        if setting:
            # Don't allow updating system settings
            if setting.is_system:
                raise ValueError(f"Cannot update system setting: {key}")
            setting.setting_value = str(value)
            if description:
                setting.description = description
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(
                setting_key=key,
                setting_value=str(value),
                description=description,
                category=category,
                is_system=is_system
            )
            db.session.add(setting)
        db.session.commit()
        return setting
    
    @classmethod
    def get_by_category(cls, category):
        """Get all settings in a category"""
        return cls.query.filter_by(category=category).all()
    
    @classmethod
    def get_all_editable(cls):
        """Get all non-system settings"""
        return cls.query.filter_by(is_system=0).all()
    
    @classmethod
    def delete_setting(cls, key):
        """Delete a setting (only non-system settings)"""
        setting = cls.query.get(key)
        if setting:
            if setting.is_system:
                raise ValueError(f"Cannot delete system setting: {key}")
            db.session.delete(setting)
            db.session.commit()
            return True
        return False
    
    @classmethod
    def initialize_defaults(cls):
        """Initialize default settings if they don't exist"""
        defaults = [
            # Face Recognition Settings
            ('face_recognition_threshold', '0.6', 'Threshold for face recognition accuracy', 'face_recognition', 0),
            ('face_encoding_version', '1.0', 'Face encoding algorithm version', 'face_recognition', 1),
            ('camera_quality_threshold', '720', 'Minimum camera quality requirement', 'camera', 0),
            
            # Session Settings
            ('session_timeout_minutes', '30', 'Session timeout in minutes', 'session', 0),
            ('max_session_duration', '180', 'Maximum session duration in minutes', 'session', 0),
            ('auto_mark_late_threshold', '10', 'Minutes after start time to mark as late', 'attendance', 0),
            
            # Dashboard Settings
            ('auto_refresh_interval', '30', 'Dashboard auto-refresh interval in seconds', 'dashboard', 0),
            
            # Report Settings
            ('attendance_report_limit', '1000', 'Maximum records in attendance report', 'reports', 0),
            
            # Notification Settings
            ('notification_retention_days', '30', 'Days to keep notifications', 'notifications', 0),
            
            # System Metrics
            ('system_metrics_retention_days', '90', 'Days to keep system metrics', 'metrics', 0),
            
            # Security Settings
            ('password_min_length', '8', 'Minimum password length', 'security', 0),
            ('max_login_attempts', '5', 'Maximum failed login attempts before lockout', 'security', 0),
            ('lockout_duration_minutes', '15', 'Account lockout duration in minutes', 'security', 0),
            
            # Email Settings
            ('smtp_enabled', 'false', 'Enable email notifications', 'email', 0),
            ('smtp_server', '', 'SMTP server address', 'email', 0),
            ('smtp_port', '587', 'SMTP server port', 'email', 0),
            
            # System Info
            ('system_name', 'Face Recognition Attendance System', 'System name', 'general', 0),
            ('institution_name', '', 'Institution name', 'general', 0),
            ('timezone', 'UTC', 'System timezone', 'general', 0),
        ]
        
        for key, value, description, category, is_system in defaults:
            if not cls.query.get(key):
                setting = cls(
                    setting_key=key,
                    setting_value=value,
                    description=description,
                    category=category,
                    is_system=is_system
                )
                db.session.add(setting)
        
        db.session.commit()
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'setting_key': self.setting_key,
            'setting_value': self.setting_value,
            'description': self.description,
            'category': self.category,
            'is_system': bool(self.is_system),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Settings category constants
class SettingsCategory:
    """Constants for settings categories"""
    GENERAL = 'general'
    FACE_RECOGNITION = 'face_recognition'
    CAMERA = 'camera'
    SESSION = 'session'
    ATTENDANCE = 'attendance'
    DASHBOARD = 'dashboard'
    REPORTS = 'reports'
    NOTIFICATIONS = 'notifications'
    METRICS = 'metrics'
    SECURITY = 'security'
    EMAIL = 'email'