"""
Helper functions for the lecturer panel application
"""
import re
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, flash, request
import sqlite3
import os
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.config import Config

def get_current_user():
    """Get current user information from session"""
    print("[DEBUG] Session contents:", dict(session))  # Debug print
    print("[DEBUG] Database path:", get_database_path())  # Debug print
    if 'user_id' not in session:
        print("[DEBUG] No user_id in session")  # Debug print
        return None
    
    try:
        conn = sqlite3.connect(get_database_path())
        cursor = conn.cursor()
        
        # Get instructor information
        cursor.execute('''
            SELECT instructor_id, instructor_name, email, phone, faculty, 
                   created_at, updated_at, last_login, is_active
            FROM instructors
            WHERE instructor_id = ? AND is_active = 1
        ''', (session['user_id'],))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'instructor_id': result[0],
                'instructor_name': result[1],
                'email': result[2],
                'phone': result[3],
                'faculty': result[4],
                'created_at': result[5],
                'updated_at': result[6],
                'last_login': result[7],
                'is_active': result[8]
            }
        else:
            # User not found or inactive, clear session
            print(f"[DEBUG] User record for '{session['user_id']}': None (not found or inactive)")  # Debug print
            session.clear()
            return None
            
    except Exception as e:
        log_error(f"Error getting current user: {str(e)}", "USER_ERROR")
        print(f"[DEBUG] Exception in get_current_user: {str(e)}")  # Debug print
        return None


def validate_password_strength(password):
    """
    Validate password strength requirements
    - At least 8 characters long
    - Contains uppercase letter
    - Contains lowercase letter
    - Contains numeric character
    - Contains special character (optional but recommended)
    """
    if len(password) < 8:
        return False
    
    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        return False
    
    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        return False
    
    # Check for numeric character
    if not re.search(r'\d', password):
        return False
    
    return True

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    # Remove any non-digit characters
    phone_digits = re.sub(r'\D', '', phone)
    
    # Check if it's a valid length (assuming 10-15 digits)
    if len(phone_digits) < 10 or len(phone_digits) > 15:
        return False
    
    return True

def sanitize_input(input_string):
    """Sanitize user input to prevent XSS"""
    if not input_string:
        return ""
    
    # Remove potential HTML tags
    clean_input = re.sub(r'<[^>]+>', '', str(input_string))
    # Remove potential script tags
    clean_input = re.sub(r'<script[^>]*>.*?</script>', '', clean_input, flags=re.IGNORECASE | re.DOTALL)
    
    return clean_input.strip()

def generate_session_token():
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

def hash_password(password):
    """Hash password with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + password_hash.hex()

def verify_password(password, stored_hash):
    """Verify password against stored hash"""
    if len(stored_hash) < 32:
        return False
    
    salt = stored_hash[:32]
    stored_password_hash = stored_hash[32:]
    
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    
    return password_hash.hex() == stored_password_hash

def format_datetime(dt, format_string="%Y-%m-%d %H:%M:%S"):
    """Format datetime object to string"""
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt
    
    if isinstance(dt, datetime):
        return dt.strftime(format_string)
    
    return str(dt)

def get_time_ago(timestamp):
    """Get human-readable time ago string"""
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return "Unknown"
    
    now = datetime.now()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def calculate_attendance_percentage(present_count, total_sessions):
    """Calculate attendance percentage"""
    if total_sessions == 0:
        return 0.0
    
    return round((present_count / total_sessions) * 100, 2)

def generate_report_filename(report_type, course_code=None, date_range=None):
    """Generate filename for reports"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if course_code and date_range:
        return f"{report_type}_{course_code}_{date_range}_{timestamp}.pdf"
    elif course_code:
        return f"{report_type}_{course_code}_{timestamp}.pdf"
    else:
        return f"{report_type}_{timestamp}.pdf"

def is_valid_session_time(start_time, end_time):
    """Validate session time format and logic"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        
        # Check if end time is after start time
        return end > start
    except ValueError:
        return False

def get_current_semester():
    """Get current semester based on current date"""
    now = datetime.now()
    month = now.month
    
    # Assuming academic year starts in September
    if month >= 9 or month <= 12:
        return "1.1"  # First semester
    elif month >= 1 and month <= 4:
        return "1.2"  # Second semester
    else:
        return "1.3"  # Third semester/summer

def log_error(error_message, error_type="GENERAL", additional_info=None):
    """Log error to file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = f"[{timestamp}] {error_type}: {error_message}"
    if additional_info:
        log_entry += f" | Additional Info: {additional_info}"
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Write to log file
    with open("logs/error.log", "a") as f:
        f.write(log_entry + "\n")

def get_database_path():
    """Get database path from config or environment"""
    return Config.DATABASE

def get_database_connection():
    """Get database connection"""
    import sqlite3
    db_path = get_database_path()
    return sqlite3.connect(db_path)

def create_backup_filename():
    """Create backup filename with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"backup_attendance_system_{timestamp}.db"

def validate_image_file(filename):
    """Validate image file extension"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_file_size_mb(file_path):
    """Get file size in MB"""
    if os.path.exists(file_path):
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / (1024 * 1024), 2)
    return 0

def truncate_text(text, max_length=100):
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def get_session_duration(start_time, end_time):
    """Calculate session duration in minutes"""
    try:
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        
        duration = end - start
        return int(duration.total_seconds() / 60)
    except ValueError:
        return 0

def format_duration(minutes):
    """Format duration in minutes to human readable format"""
    if minutes < 60:
        return f"{minutes} minutes"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"

def get_day_of_week(date_string):
    """Get day of week from date string"""
    try:
        date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        return date_obj.strftime("%A")
    except ValueError:
        return "Unknown"

def is_holiday(date_string, holidays_list):
    """Check if a date is a holiday"""
    return date_string in holidays_list

def get_next_class_date(current_date, timetable):
    """Get next class date based on timetable"""
    # This is a simplified implementation
    # In a real application, this would consider holidays, breaks, etc.
    current = datetime.strptime(current_date, "%Y-%m-%d")
    
    for i in range(1, 8):  # Check next 7 days
        next_date = current + timedelta(days=i)
        day_of_week = next_date.weekday()  # 0=Monday, 6=Sunday
        
        # Check if there's a class on this day
        if any(t['day_of_week'] == day_of_week for t in timetable):
            return next_date.strftime("%Y-%m-%d")
    
    return None

def generate_qr_code_data(session_id, instructor_id):
    """Generate QR code data for attendance"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data = f"SESSION:{session_id}:INSTRUCTOR:{instructor_id}:TIME:{timestamp}"
    return data

def validate_qr_code_data(qr_data):
    """Validate QR code data format"""
    parts = qr_data.split(':')
    if len(parts) != 6:
        return False
    
    if parts[0] != "SESSION" or parts[2] != "INSTRUCTOR" or parts[4] != "TIME":
        return False
    
    # Check if timestamp is within valid range (e.g., within last 5 minutes)
    try:
        timestamp = datetime.strptime(parts[5], "%Y%m%d%H%M%S")
        now = datetime.now()
        if (now - timestamp).total_seconds() > 300:  # 5 minutes
            return False
    except ValueError:
        return False
    
    return True

def get_system_stats():
    """Get basic system statistics"""
    db_path = get_database_path()
    
    stats = {
        'database_size': get_file_size_mb(db_path),
        'last_backup': 'Never',  # This would be stored in settings
        'uptime': '0 days',      # This would be calculated from app start time
        'memory_usage': '0 MB'   # This would use psutil or similar
    }
    
    return stats

def log_activity(user_id, user_type, activity_type, description=None):
    """Log user activity to the activity_log table."""
    try:
        db_service = DatabaseService()
        query = '''
            INSERT INTO activity_log (user_id, user_type, activity_type, description, timestamp)
            VALUES (?, ?, ?, ?, datetime('now'))
        '''
        db_service.execute_query(query, (str(user_id), user_type, activity_type, description))
    except Exception as e:
        log_error(f"Error logging activity: {str(e)}", "ACTIVITY_LOG_ERROR")

def validate_session_access(instructor_id, session_id):
    """Check if instructor has access to a session (is assigned to the class for the session)."""
    try:
        db_service = DatabaseService()
        query = '''
            SELECT cs.session_id
            FROM class_sessions cs
            JOIN classes c ON cs.class_id = c.class_id
            JOIN class_instructors ci ON c.class_id = ci.class_id
            WHERE cs.session_id = ? AND ci.instructor_id = ?
        '''
        result = db_service.execute_query(query, (session_id, instructor_id), fetch='one')
        return result is not None
    except Exception as e:
        log_error(f"Error validating session access: {str(e)}", "SESSION_ACCESS_ERROR")
        return False