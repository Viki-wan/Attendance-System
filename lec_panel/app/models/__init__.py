"""
Models package initialization
Exports all models for easy importing
"""

# Import models in dependency order to avoid circular imports
from app.models.user import Instructor
from app.models.course import Course, StudentCourse
from app.models.class_model import Class, ClassInstructor
from app.models.student import Student
from app.models.session import ClassSession
from app.models.attendance import Attendance
from app.models.notification import Notification, NotificationTemplates
from app.models.timetable import Timetable, Holiday
from app.models.session_dismissal import SessionDismissal
from app.models.settings import Settings
from app.models.activity_log import ActivityLog
from app.models.lecturer_preferences import LecturerPreference
from app.models.system_metric import SystemMetric

# Export all models
__all__ = [
    'Instructor',
    'Course',
    'StudentCourse',
    'Class',
    'ClassInstructor',
    'Student',
    'ClassSession',
    'Attendance',
    'Notification',
    'NotificationTemplates',
    'Timetable',
    'Holiday',
    'SessionDismissal',
    'Settings',
    'LecturerPreference',
    'ActivityLog',
    'SystemMetric'
]