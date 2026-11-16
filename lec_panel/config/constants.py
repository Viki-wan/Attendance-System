"""
System Constants
Centralized constants for the Face Recognition Attendance System
"""

# User Types
class UserType:
    ADMIN = 'admin'
    INSTRUCTOR = 'instructor'
    STUDENT = 'student'
    
    ALL = [ADMIN, INSTRUCTOR, STUDENT]


# Activity Types
class ActivityType:
    LOGIN = 'login'
    LOGOUT = 'logout'
    LOGIN_FAILED = 'login_failed'
    SESSION_CREATED = 'session_created'
    SESSION_STARTED = 'session_started'
    SESSION_ENDED = 'session_ended'
    SESSION_DISMISSED = 'session_dismissed'
    ATTENDANCE_MARKED = 'attendance_marked'
    ATTENDANCE_CORRECTED = 'attendance_corrected'
    STUDENT_REGISTERED = 'student_registered'
    STUDENT_UPDATED = 'student_updated'
    FACE_ENCODING_UPDATED = 'face_encoding_updated'
    REPORT_GENERATED = 'report_generated'
    SETTINGS_CHANGED = 'settings_changed'
    PASSWORD_CHANGED = 'password_changed'
    PASSWORD_RESET = 'password_reset'
    PROFILE_UPDATED = 'profile_updated'
    ACCOUNT_CREATED = 'account_created'
    ACCOUNT_ACTIVATED = 'account_activated'
    ACCOUNT_DEACTIVATED = 'account_deactivated'


# Attendance Status
class AttendanceStatus:
    PRESENT = 'Present'
    ABSENT = 'Absent'
    LATE = 'Late'
    EXCUSED = 'Excused'
    
    ALL = [PRESENT, ABSENT, LATE, EXCUSED]
    
    # Status colors for UI
    COLORS = {
        PRESENT: '#28a745',   # Green
        ABSENT: '#dc3545',    # Red
        LATE: '#ffc107',      # Yellow
        EXCUSED: '#17a2b8'    # Blue
    }


# Session Status
class SessionStatus:
    SCHEDULED = 'scheduled'
    ONGOING = 'ongoing'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    DISMISSED = 'dismissed'
    
    ALL = [SCHEDULED, ONGOING, COMPLETED, CANCELLED, DISMISSED]
    
    # Status badges for UI
    BADGES = {
        SCHEDULED: 'info',
        ONGOING: 'success',
        COMPLETED: 'secondary',
        CANCELLED: 'danger',
        DISMISSED: 'warning'
    }


# Attendance Method
class AttendanceMethod:
    FACE_RECOGNITION = 'face_recognition'
    MANUAL = 'manual'
    RFID = 'rfid'
    QR_CODE = 'qr_code'
    
    ALL = [FACE_RECOGNITION, MANUAL, RFID, QR_CODE]


# Notification Types
class NotificationType:
    INFO = 'info'
    WARNING = 'warning'
    SUCCESS = 'success'
    ERROR = 'error'
    
    ALL = [INFO, WARNING, SUCCESS, ERROR]


# Notification Priority
class NotificationPriority:
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    URGENT = 'urgent'
    
    ALL = [LOW, NORMAL, HIGH, URGENT]


# Enrollment Status
class EnrollmentStatus:
    ACTIVE = 'Active'
    DROPPED = 'Dropped'
    COMPLETED = 'Completed'
    FAILED = 'Failed'
    
    ALL = [ACTIVE, DROPPED, COMPLETED, FAILED]


# Dismissal Status
class DismissalStatus:
    DISMISSED = 'dismissed'
    RESCHEDULED = 'rescheduled'
    CANCELLED = 'cancelled'
    
    ALL = [DISMISSED, RESCHEDULED, CANCELLED]


# Days of Week
class DayOfWeek:
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    
    NAMES = {
        SUNDAY: 'Sunday',
        MONDAY: 'Monday',
        TUESDAY: 'Tuesday',
        WEDNESDAY: 'Wednesday',
        THURSDAY: 'Thursday',
        FRIDAY: 'Friday',
        SATURDAY: 'Saturday'
    }
    
    SHORT_NAMES = {
        SUNDAY: 'Sun',
        MONDAY: 'Mon',
        TUESDAY: 'Tue',
        WEDNESDAY: 'Wed',
        THURSDAY: 'Thu',
        FRIDAY: 'Fri',
        SATURDAY: 'Sat'
    }


# Semesters
class Semester:
    FIRST_FIRST = '1.1'
    FIRST_SECOND = '1.2'
    SECOND_FIRST = '2.1'
    SECOND_SECOND = '2.2'
    THIRD_FIRST = '3.1'
    THIRD_SECOND = '3.2'
    FOURTH_FIRST = '4.1'
    FOURTH_SECOND = '4.2'
    
    ALL = [
        FIRST_FIRST, FIRST_SECOND,
        SECOND_FIRST, SECOND_SECOND,
        THIRD_FIRST, THIRD_SECOND,
        FOURTH_FIRST, FOURTH_SECOND
    ]
    
    @staticmethod
    def get_year(semester):
        """Extract year from semester string"""
        return int(semester.split('.')[0])
    
    @staticmethod
    def get_term(semester):
        """Extract term from semester string"""
        return int(semester.split('.')[1])


# Report Types
class ReportType:
    SESSION_SUMMARY = 'session_summary'
    STUDENT_HISTORY = 'student_history'
    COURSE_ANALYTICS = 'course_analytics'
    ATTENDANCE_TRENDS = 'attendance_trends'
    LOW_ATTENDANCE = 'low_attendance'
    CLASS_PERFORMANCE = 'class_performance'
    INSTRUCTOR_SUMMARY = 'instructor_summary'
    
    ALL = [
        SESSION_SUMMARY,
        STUDENT_HISTORY,
        COURSE_ANALYTICS,
        ATTENDANCE_TRENDS,
        LOW_ATTENDANCE,
        CLASS_PERFORMANCE,
        INSTRUCTOR_SUMMARY
    ]


# Export Formats
class ExportFormat:
    PDF = 'pdf'
    EXCEL = 'excel'
    CSV = 'csv'
    JSON = 'json'
    
    ALL = [PDF, EXCEL, CSV, JSON]
    
    MIME_TYPES = {
        PDF: 'application/pdf',
        EXCEL: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        CSV: 'text/csv',
        JSON: 'application/json'
    }


# Setting Categories
class SettingCategory:
    GENERAL = 'general'
    FACE_RECOGNITION = 'face_recognition'
    SESSION = 'session'
    ATTENDANCE = 'attendance'
    CAMERA = 'camera'
    NOTIFICATIONS = 'notifications'
    METRICS = 'metrics'
    DASHBOARD = 'dashboard'
    REPORTS = 'reports'
    SECURITY = 'security'
    
    ALL = [
        GENERAL,
        FACE_RECOGNITION,
        SESSION,
        ATTENDANCE,
        CAMERA,
        NOTIFICATIONS,
        METRICS,
        DASHBOARD,
        REPORTS,
        SECURITY
    ]


# Dashboard Widget Types
class WidgetType:
    TODAY_SESSIONS = 'today_sessions'
    QUICK_START = 'quick_start'
    ATTENDANCE_STATS = 'attendance_stats'
    LOW_ATTENDANCE = 'low_attendance'
    RECENT_ACTIVITIES = 'recent_activities'
    CLASS_PERFORMANCE = 'class_performance'
    UPCOMING_SESSIONS = 'upcoming_sessions'
    NOTIFICATIONS = 'notifications'


# Chart Types
class ChartType:
    LINE = 'line'
    BAR = 'bar'
    PIE = 'pie'
    DOUGHNUT = 'doughnut'
    AREA = 'area'


# Face Recognition Error Codes
class FaceRecognitionError:
    NO_FACE_DETECTED = 'NO_FACE_DETECTED'
    MULTIPLE_FACES = 'MULTIPLE_FACES'
    POOR_IMAGE_QUALITY = 'POOR_IMAGE_QUALITY'
    FACE_TOO_SMALL = 'FACE_TOO_SMALL'
    ENCODING_FAILED = 'ENCODING_FAILED'
    NO_MATCH_FOUND = 'NO_MATCH_FOUND'
    LOW_CONFIDENCE = 'LOW_CONFIDENCE'
    CAMERA_ERROR = 'CAMERA_ERROR'


# HTTP Status Messages
class HTTPMessage:
    SUCCESS = 'Operation completed successfully'
    CREATED = 'Resource created successfully'
    UPDATED = 'Resource updated successfully'
    DELETED = 'Resource deleted successfully'
    BAD_REQUEST = 'Invalid request data'
    UNAUTHORIZED = 'Authentication required'
    FORBIDDEN = 'Access denied'
    NOT_FOUND = 'Resource not found'
    CONFLICT = 'Resource already exists'
    INTERNAL_ERROR = 'Internal server error'


# Validation Patterns
class ValidationPattern:
    EMAIL = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    PHONE = r'^\+?1?\d{9,15}$'
    STUDENT_ID = r'^[A-Z0-9]{6,12}$'
    INSTRUCTOR_ID = r'^[A-Z0-9]{6,12}$'
    COURSE_CODE = r'^[A-Z]{3,4}\d{3,4}$'
    CLASS_ID = r'^[A-Z0-9-]{6,20}$'


# Cache Keys
class CacheKey:
    FACE_ENCODING = 'face_encoding:{student_id}'
    SESSION_DATA = 'session:{session_id}'
    USER_SESSIONS = 'user_sessions:{instructor_id}'
    ATTENDANCE_COUNT = 'attendance_count:{session_id}'
    DASHBOARD_STATS = 'dashboard_stats:{instructor_id}'
    STUDENT_LIST = 'student_list:{class_id}'
    
    # Cache TTL (seconds)
    TTL_SHORT = 300      # 5 minutes
    TTL_MEDIUM = 1800    # 30 minutes
    TTL_LONG = 3600      # 1 hour
    TTL_DAY = 86400      # 24 hours


# WebSocket Events
class SocketEvent:
    # Client to Server
    CONNECT = 'connect'
    DISCONNECT = 'disconnect'
    JOIN_SESSION = 'join_session'
    LEAVE_SESSION = 'leave_session'
    PROCESS_FRAME = 'process_frame'
    MARK_ATTENDANCE = 'mark_attendance'
    
    # Server to Client
    STUDENT_RECOGNIZED = 'student_recognized'
    ATTENDANCE_MARKED = 'attendance_marked'
    SESSION_PROGRESS = 'session_progress'
    CAMERA_STATUS = 'camera_status'
    UNKNOWN_FACE = 'unknown_face_detected'
    ERROR = 'error'
    SESSION_STARTED = 'session_started'
    SESSION_ENDED = 'session_ended'


# Celery Task Names
class CeleryTask:
    PROCESS_FACE_ENCODING = 'tasks.face_processing.process_face_encoding'
    BATCH_FACE_ENCODING = 'tasks.face_processing.batch_face_encoding'
    GENERATE_REPORT = 'tasks.report_generation.generate_report'
    SEND_NOTIFICATION = 'tasks.notification.send_notification'
    CLEANUP_OLD_DATA = 'tasks.maintenance.cleanup_old_data'
    BACKUP_DATABASE = 'tasks.maintenance.backup_database'
    CALCULATE_METRICS = 'tasks.metrics.calculate_metrics'


# File Upload Limits
class UploadLimit:
    MAX_IMAGE_SIZE_MB = 5
    MAX_BATCH_IMAGES = 50
    MAX_CSV_SIZE_MB = 10
    MAX_EXCEL_SIZE_MB = 10


# Pagination Defaults
class Pagination:
    DEFAULT_PAGE = 1
    DEFAULT_PER_PAGE = 20
    MAX_PER_PAGE = 100


# Date Formats
class DateFormat:
    DATE = '%Y-%m-%d'
    TIME = '%H:%M:%S'
    DATETIME = '%Y-%m-%d %H:%M:%S'
    DISPLAY_DATE = '%d %b %Y'
    DISPLAY_TIME = '%I:%M %p'
    DISPLAY_DATETIME = '%d %b %Y, %I:%M %p'
    ISO8601 = '%Y-%m-%dT%H:%M:%S.%fZ'


# Permission Levels
class Permission:
    READ = 'read'
    WRITE = 'write'
    DELETE = 'delete'
    ADMIN = 'admin'
    
    ALL = [READ, WRITE, DELETE, ADMIN]


# Default Values
class Defaults:
    SESSION_DURATION = 90  # minutes
    LATE_THRESHOLD = 10    # minutes
    GRACE_PERIOD = 5       # minutes
    TIMEZONE = 'UTC'
    LANGUAGE = 'en'
    THEME = 'light'
    ITEMS_PER_PAGE = 20
    FACE_RECOGNITION_TOLERANCE = 0.6


# API Response Codes
class APIResponseCode:
    SUCCESS = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# ============================================================================
# BACKWARD COMPATIBILITY LAYER
# Dictionary-based constants for legacy code compatibility
# ============================================================================

# User Types Dictionary
USER_TYPES = {
    'ADMIN': UserType.ADMIN,
    'INSTRUCTOR': UserType.INSTRUCTOR,
    'STUDENT': UserType.STUDENT
}

# Activity Types Dictionary
ACTIVITY_TYPES = {
    'LOGIN': ActivityType.LOGIN,
    'LOGOUT': ActivityType.LOGOUT,
    'LOGIN_FAILED': ActivityType.LOGIN_FAILED,
    'SESSION_CREATED': ActivityType.SESSION_CREATED,
    'SESSION_STARTED': ActivityType.SESSION_STARTED,
    'SESSION_ENDED': ActivityType.SESSION_ENDED,
    'SESSION_DISMISSED': ActivityType.SESSION_DISMISSED,
    'ATTENDANCE_MARKED': ActivityType.ATTENDANCE_MARKED,
    'ATTENDANCE_CORRECTED': ActivityType.ATTENDANCE_CORRECTED,
    'STUDENT_REGISTERED': ActivityType.STUDENT_REGISTERED,
    'STUDENT_UPDATED': ActivityType.STUDENT_UPDATED,
    'FACE_ENCODING_UPDATED': ActivityType.FACE_ENCODING_UPDATED,
    'REPORT_GENERATED': ActivityType.REPORT_GENERATED,
    'SETTINGS_CHANGED': ActivityType.SETTINGS_CHANGED,
    'PASSWORD_CHANGED': ActivityType.PASSWORD_CHANGED,
    'PASSWORD_RESET': ActivityType.PASSWORD_RESET,
    'PROFILE_UPDATED': ActivityType.PROFILE_UPDATED,
    'ACCOUNT_CREATED': ActivityType.ACCOUNT_CREATED,
    'ACCOUNT_ACTIVATED': ActivityType.ACCOUNT_ACTIVATED,
    'ACCOUNT_DEACTIVATED': ActivityType.ACCOUNT_DEACTIVATED
}

# Attendance Status Dictionary
ATTENDANCE_STATUS = {
    'PRESENT': AttendanceStatus.PRESENT,
    'ABSENT': AttendanceStatus.ABSENT,
    'LATE': AttendanceStatus.LATE,
    'EXCUSED': AttendanceStatus.EXCUSED
}

# Session Status Dictionary
SESSION_STATUS = {
    'SCHEDULED': SessionStatus.SCHEDULED,
    'ONGOING': SessionStatus.ONGOING,
    'COMPLETED': SessionStatus.COMPLETED,
    'CANCELLED': SessionStatus.CANCELLED,
    'DISMISSED': SessionStatus.DISMISSED
}

# Attendance Method Dictionary
ATTENDANCE_METHOD = {
    'FACE_RECOGNITION': AttendanceMethod.FACE_RECOGNITION,
    'MANUAL': AttendanceMethod.MANUAL,
    'RFID': AttendanceMethod.RFID,
    'QR_CODE': AttendanceMethod.QR_CODE
}

# Enrollment Status Dictionary
ENROLLMENT_STATUS = {
    'ACTIVE': EnrollmentStatus.ACTIVE,
    'DROPPED': EnrollmentStatus.DROPPED,
    'COMPLETED': EnrollmentStatus.COMPLETED,
    'FAILED': EnrollmentStatus.FAILED
}

# Notification Types Dictionary
NOTIFICATION_TYPES = {
    'INFO': NotificationType.INFO,
    'WARNING': NotificationType.WARNING,
    'SUCCESS': NotificationType.SUCCESS,
    'ERROR': NotificationType.ERROR
}

# Notification Priority Dictionary
NOTIFICATION_PRIORITY = {
    'LOW': NotificationPriority.LOW,
    'NORMAL': NotificationPriority.NORMAL,
    'HIGH': NotificationPriority.HIGH,
    'URGENT': NotificationPriority.URGENT
}

# Report Types Dictionary
REPORT_TYPES = {
    'SESSION_SUMMARY': ReportType.SESSION_SUMMARY,
    'STUDENT_HISTORY': ReportType.STUDENT_HISTORY,
    'COURSE_ANALYTICS': ReportType.COURSE_ANALYTICS,
    'ATTENDANCE_TRENDS': ReportType.ATTENDANCE_TRENDS,
    'LOW_ATTENDANCE': ReportType.LOW_ATTENDANCE,
    'CLASS_PERFORMANCE': ReportType.CLASS_PERFORMANCE,
    'INSTRUCTOR_SUMMARY': ReportType.INSTRUCTOR_SUMMARY
}

# Export Formats Dictionary
EXPORT_FORMATS = {
    'PDF': ExportFormat.PDF,
    'EXCEL': ExportFormat.EXCEL,
    'CSV': ExportFormat.CSV,
    'JSON': ExportFormat.JSON
}

# Dismissal Status Dictionary
DISMISSAL_STATUS = {
    'DISMISSED': DismissalStatus.DISMISSED,
    'RESCHEDULED': DismissalStatus.RESCHEDULED,
    'CANCELLED': DismissalStatus.CANCELLED
}