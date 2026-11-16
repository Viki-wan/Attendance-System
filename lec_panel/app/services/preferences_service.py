# app/services/preferences_service.py
"""
Service layer for managing instructor preferences.
Handles UI customization, notifications, and system behavior preferences.
Uses SQLAlchemy ORM for database operations.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from app.models.lecturer_preferences import LecturerPreference
from app.models.user import Instructor
from app import db


class PreferencesService:
    """Service for managing instructor preferences using SQLAlchemy ORM."""
    
    # Default preference values
    DEFAULT_PREFERENCES = {
        'theme': 'light',
        'dashboard_layout': 'default',
        'auto_refresh_interval': 30,
        'default_session_duration': 90,
        'timezone': 'UTC',
        'language': 'en',
        'notification_settings': {
            'email_notifications': True,
            'push_notifications': True,
            'attendance_alerts': True,
            'session_reminders': True,
            'low_attendance_threshold': 75
        }
    }
    
    @staticmethod
    def get_preferences(instructor_id: str) -> Optional[LecturerPreference]:
        """
        Get preferences for an instructor.
        Creates default preferences if they don't exist.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            LecturerPreference object or None
        """
        prefs = LecturerPreference.query.filter_by(
            instructor_id=instructor_id
        ).first()
        
        if prefs:
            return prefs
        else:
            # Create default preferences
            return PreferencesService._create_default_preferences(instructor_id)
    
    @staticmethod
    def _create_default_preferences(instructor_id: str) -> LecturerPreference:
        """
        Create default preferences for an instructor.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            Newly created LecturerPreference object
        """
        prefs = LecturerPreference(
            instructor_id=instructor_id,
            theme=PreferencesService.DEFAULT_PREFERENCES['theme'],
            dashboard_layout=PreferencesService.DEFAULT_PREFERENCES['dashboard_layout'],
            notification_settings=PreferencesService.DEFAULT_PREFERENCES['notification_settings'],
            auto_refresh_interval=PreferencesService.DEFAULT_PREFERENCES['auto_refresh_interval'],
            default_session_duration=PreferencesService.DEFAULT_PREFERENCES['default_session_duration'],
            timezone=PreferencesService.DEFAULT_PREFERENCES['timezone'],
            language=PreferencesService.DEFAULT_PREFERENCES['language']
        )
        
        db.session.add(prefs)
        db.session.commit()
        
        return prefs
    
    @staticmethod
    def update_preferences(instructor_id: str, updates: Dict[str, Any]) -> LecturerPreference:
        """
        Update preferences for an instructor.
        
        Args:
            instructor_id: The instructor's ID
            updates: Dictionary of preference updates
            
        Returns:
            Updated LecturerPreference object
        """
        # Ensure preferences exist
        prefs = PreferencesService.get_preferences(instructor_id)
        
        # Update fields
        for key, value in updates.items():
            if key == 'notification_settings':
                # Merge notification settings
                if isinstance(value, dict):
                    current_settings = prefs.notification_settings or {}
                    current_settings.update(value)
                    prefs.notification_settings = current_settings
                else:
                    prefs.notification_settings = value
            elif key in ['theme', 'dashboard_layout', 'timezone', 'language']:
                setattr(prefs, key, value)
            elif key in ['auto_refresh_interval', 'default_session_duration']:
                setattr(prefs, key, int(value))
        
        # Update timestamp (handled by trigger, but can be explicit)
        prefs.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return prefs
    
    @staticmethod
    def get_notification_settings(instructor_id: str) -> Dict[str, Any]:
        """
        Get notification settings for an instructor.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            Dictionary of notification settings
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        
        if prefs and prefs.notification_settings:
            return prefs.notification_settings
        
        return PreferencesService.DEFAULT_PREFERENCES['notification_settings']
    
    @staticmethod
    def update_notification_settings(
        instructor_id: str, 
        settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update notification settings for an instructor.
        
        Args:
            instructor_id: The instructor's ID
            settings: Dictionary of notification settings
            
        Returns:
            Updated notification settings
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        
        # Get current settings and merge with updates
        current_settings = prefs.notification_settings or {}
        current_settings.update(settings)
        
        prefs.notification_settings = current_settings
        prefs.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return current_settings
    
    @staticmethod
    def reset_to_defaults(instructor_id: str) -> LecturerPreference:
        """
        Reset all preferences to default values.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            Reset LecturerPreference object
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        
        # Reset all fields to defaults
        prefs.theme = PreferencesService.DEFAULT_PREFERENCES['theme']
        prefs.dashboard_layout = PreferencesService.DEFAULT_PREFERENCES['dashboard_layout']
        prefs.notification_settings = PreferencesService.DEFAULT_PREFERENCES['notification_settings']
        prefs.auto_refresh_interval = PreferencesService.DEFAULT_PREFERENCES['auto_refresh_interval']
        prefs.default_session_duration = PreferencesService.DEFAULT_PREFERENCES['default_session_duration']
        prefs.timezone = PreferencesService.DEFAULT_PREFERENCES['timezone']
        prefs.language = PreferencesService.DEFAULT_PREFERENCES['language']
        prefs.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return prefs
    
    @staticmethod
    def delete_preferences(instructor_id: str) -> bool:
        """
        Delete preferences for an instructor.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            True if deleted successfully
        """
        prefs = LecturerPreference.query.filter_by(
            instructor_id=instructor_id
        ).first()
        
        if prefs:
            db.session.delete(prefs)
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def get_preference_value(
        instructor_id: str, 
        preference_key: str, 
        default: Any = None
    ) -> Any:
        """
        Get a specific preference value.
        
        Args:
            instructor_id: The instructor's ID
            preference_key: The preference key to retrieve
            default: Default value if preference not found
            
        Returns:
            The preference value or default
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        return getattr(prefs, preference_key, default)
    
    @staticmethod
    def set_preference_value(
        instructor_id: str, 
        preference_key: str, 
        value: Any
    ) -> LecturerPreference:
        """
        Set a specific preference value.
        
        Args:
            instructor_id: The instructor's ID
            preference_key: The preference key to set
            value: The value to set
            
        Returns:
            Updated LecturerPreference object
        """
        return PreferencesService.update_preferences(
            instructor_id, 
            {preference_key: value}
        )
    
    @staticmethod
    def export_preferences(instructor_id: str) -> Dict[str, Any]:
        """
        Export all preferences as a dictionary for backup.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            Dictionary containing all preferences
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        
        return {
            'theme': prefs.theme,
            'dashboard_layout': prefs.dashboard_layout,
            'auto_refresh_interval': prefs.auto_refresh_interval,
            'default_session_duration': prefs.default_session_duration,
            'timezone': prefs.timezone,
            'language': prefs.language,
            'notification_settings': prefs.notification_settings,
            'exported_at': datetime.now().isoformat()
        }
    
    @staticmethod
    def import_preferences(
        instructor_id: str, 
        import_data: Dict[str, Any]
    ) -> LecturerPreference:
        """
        Import preferences from a backup dictionary.
        
        Args:
            instructor_id: The instructor's ID
            import_data: Dictionary containing preferences to import
            
        Returns:
            Updated LecturerPreference object
        """
        # Remove metadata fields
        import_data = import_data.copy()
        import_data.pop('exported_at', None)
        import_data.pop('instructor_id', None)
        
        # Validate and sanitize data
        valid_keys = {
            'theme', 'dashboard_layout', 'auto_refresh_interval',
            'default_session_duration', 'timezone', 'language',
            'notification_settings'
        }
        
        sanitized_data = {
            k: v for k, v in import_data.items() 
            if k in valid_keys
        }
        
        return PreferencesService.update_preferences(instructor_id, sanitized_data)
    
    @staticmethod
    def get_all_preferences_for_instructor(instructor_id: str) -> Dict[str, Any]:
        """
        Get all preferences and settings for an instructor as a dictionary.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            Dictionary containing all preferences
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        
        return {
            'id': prefs.id,
            'instructor_id': prefs.instructor_id,
            'theme': prefs.theme,
            'dashboard_layout': prefs.dashboard_layout,
            'notification_settings': prefs.notification_settings,
            'auto_refresh_interval': prefs.auto_refresh_interval,
            'default_session_duration': prefs.default_session_duration,
            'timezone': prefs.timezone,
            'language': prefs.language,
            'created_at': prefs.created_at.isoformat() if prefs.created_at else None,
            'updated_at': prefs.updated_at.isoformat() if prefs.updated_at else None
        }
    
    @staticmethod
    def validate_preference_value(key: str, value: Any) -> bool:
        """
        Validate a preference value.
        
        Args:
            key: The preference key
            value: The value to validate
            
        Returns:
            True if valid, False otherwise
        """
        validations = {
            'theme': lambda v: v in ['light', 'dark'],
            'dashboard_layout': lambda v: isinstance(v, str),
            'auto_refresh_interval': lambda v: isinstance(v, int) and 10 <= v <= 300,
            'default_session_duration': lambda v: isinstance(v, int) and 30 <= v <= 240,
            'timezone': lambda v: isinstance(v, str),
            'language': lambda v: isinstance(v, str) and len(v) == 2,
        }
        
        if key in validations:
            try:
                return validations[key](value)
            except:
                return False
        
        return True
    
    @staticmethod
    def bulk_update_for_instructors(
        instructor_ids: list, 
        updates: Dict[str, Any]
    ) -> int:
        """
        Bulk update preferences for multiple instructors.
        Useful for system-wide updates.
        
        Args:
            instructor_ids: List of instructor IDs
            updates: Dictionary of preference updates
            
        Returns:
            Number of instructors updated
        """
        count = 0
        for instructor_id in instructor_ids:
            try:
                PreferencesService.update_preferences(instructor_id, updates)
                count += 1
            except Exception:
                db.session.rollback()
                continue
        
        return count
    
    @staticmethod
    def get_preferences_with_instructor(instructor_id: str) -> Optional[Dict[str, Any]]:
        """
        Get preferences along with instructor information.
        Demonstrates ORM relationship usage.
        
        Args:
            instructor_id: The instructor's ID
            
        Returns:
            Dictionary with preferences and instructor info
        """
        prefs = PreferencesService.get_preferences(instructor_id)
        
        if not prefs:
            return None
        
        # Access instructor via relationship (if defined in model)
        instructor = Instructor.query.get(instructor_id)
        
        return {
            'preferences': {
                'theme': prefs.theme,
                'dashboard_layout': prefs.dashboard_layout,
                'notification_settings': prefs.notification_settings,
                'auto_refresh_interval': prefs.auto_refresh_interval,
                'default_session_duration': prefs.default_session_duration,
                'timezone': prefs.timezone,
                'language': prefs.language
            },
            'instructor': {
                'instructor_id': instructor.instructor_id,
                'name': instructor.instructor_name,
                'email': instructor.email
            } if instructor else None
        }
    
    @staticmethod
    def get_instructors_with_theme(theme: str) -> list:
        """
        Get all instructors using a specific theme.
        Example of querying by preference value.
        
        Args:
            theme: Theme name ('light' or 'dark')
            
        Returns:
            List of instructor IDs
        """
        prefs_list = LecturerPreference.query.filter_by(theme=theme).all()
        return [prefs.instructor_id for prefs in prefs_list]
    
    @staticmethod
    def get_preference_statistics() -> Dict[str, Any]:
        """
        Get statistics about preference usage across all instructors.
        Useful for analytics and system optimization.
        
        Returns:
            Dictionary with preference statistics
        """
        total_prefs = LecturerPreference.query.count()
        
        # Theme distribution
        light_count = LecturerPreference.query.filter_by(theme='light').count()
        dark_count = LecturerPreference.query.filter_by(theme='dark').count()
        
        # Average refresh interval
        all_prefs = LecturerPreference.query.all()
        avg_refresh = sum(p.auto_refresh_interval for p in all_prefs) / total_prefs if total_prefs > 0 else 0
        avg_session_duration = sum(p.default_session_duration for p in all_prefs) / total_prefs if total_prefs > 0 else 0
        
        return {
            'total_instructors_with_prefs': total_prefs,
            'theme_distribution': {
                'light': light_count,
                'dark': dark_count
            },
            'averages': {
                'auto_refresh_interval': round(avg_refresh, 2),
                'default_session_duration': round(avg_session_duration, 2)
            }
        }