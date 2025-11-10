"""
Custom Jinja2 Template Filters for DateTime Handling
Add this to your app/__init__.py or create a separate utils/template_filters.py file
"""

from datetime import datetime, date, time
from flask import Flask


def register_template_filters(app: Flask):
    """
    Register custom Jinja2 template filters for datetime handling.
    Call this function in your Flask app initialization.
    
    Usage in app/__init__.py:
        from app.utils.template_filters import register_template_filters
        
        def create_app():
            app = Flask(__name__)
            # ... other initialization
            register_template_filters(app)
            return app
    """
    
    @app.template_filter('format_date')
    def format_date(value, format='%Y-%m-%d'):
        """
        Format a date object to string.
        
        Args:
            value: date, datetime, or string
            format: strftime format string (default: '%Y-%m-%d')
            
        Returns:
            Formatted date string or 'N/A' if None
            
        Usage in templates:
            {{ session.date|format_date }}
            {{ session.date|format_date('%d/%m/%Y') }}
        """
        if value is None:
            return 'N/A'
        
        if isinstance(value, str):
            # Already a string, return as-is or try to parse
            return value
        
        if isinstance(value, (date, datetime)):
            return value.strftime(format)
        
        return str(value)
    
    
    @app.template_filter('format_time')
    def format_time(value, format='%H:%M'):
        """
        Format a time object to string.
        
        Args:
            value: time, datetime, or string
            format: strftime format string (default: '%H:%M')
            
        Returns:
            Formatted time string or 'N/A' if None
            
        Usage in templates:
            {{ session.start_time|format_time }}
            {{ session.start_time|format_time('%I:%M %p') }}
        """
        if value is None:
            return 'N/A'
        
        if isinstance(value, str):
            # Already a string, extract time portion
            return value[:5] if len(value) >= 5 else value
        
        if isinstance(value, (time, datetime)):
            return value.strftime(format)
        
        return str(value)
    
    
    @app.template_filter('format_datetime')
    def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
        """
        Format a datetime object to string.
        
        Args:
            value: datetime or string
            format: strftime format string (default: '%Y-%m-%d %H:%M:%S')
            
        Returns:
            Formatted datetime string or 'N/A' if None
            
        Usage in templates:
            {{ student.attendance_time|format_datetime }}
            {{ student.attendance_time|format_datetime('%d/%m/%Y %I:%M %p') }}
        """
        if value is None:
            return 'N/A'
        
        if isinstance(value, str):
            # Already a string, return as-is
            return value
        
        if isinstance(value, datetime):
            return value.strftime(format)
        
        return str(value)
    
    
    @app.template_filter('time_ago')
    def time_ago(value):
        """
        Convert a datetime to a human-readable "time ago" format.
        
        Args:
            value: datetime object
            
        Returns:
            Human-readable time difference (e.g., "5 minutes ago")
            
        Usage in templates:
            {{ notification.created_at|time_ago }}
        """
        if value is None:
            return 'N/A'
        
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except (ValueError, AttributeError):
                return value
        
        if not isinstance(value, datetime):
            return str(value)
        
        now = datetime.now()
        diff = now - value
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds / 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds / 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"
    
    
    @app.template_filter('duration')
    def duration(start, end):
        """
        Calculate duration between two time/datetime objects.
        
        Args:
            start: Start time/datetime
            end: End time/datetime
            
        Returns:
            Duration string (e.g., "1 hour 30 minutes")
            
        Usage in templates:
            {{ duration(session.start_time, session.end_time) }}
        """
        if start is None or end is None:
            return 'N/A'
        
        try:
            # Convert to datetime if they're time objects
            if isinstance(start, time) and isinstance(end, time):
                start_dt = datetime.combine(date.today(), start)
                end_dt = datetime.combine(date.today(), end)
            elif isinstance(start, datetime) and isinstance(end, datetime):
                start_dt = start
                end_dt = end
            else:
                return 'N/A'
            
            diff = end_dt - start_dt
            total_minutes = int(diff.total_seconds() / 60)
            
            if total_minutes < 60:
                return f"{total_minutes} minute{'s' if total_minutes != 1 else ''}"
            else:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                
                if minutes == 0:
                    return f"{hours} hour{'s' if hours != 1 else ''}"
                else:
                    return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        
        except Exception:
            return 'N/A'
    
    
    @app.template_filter('percentage')
    def percentage(value, total, decimals=1):
        """
        Calculate percentage and format it.
        
        Args:
            value: Numerator
            total: Denominator
            decimals: Number of decimal places (default: 1)
            
        Returns:
            Formatted percentage string
            
        Usage in templates:
            {{ stats.present|percentage(stats.total) }}
            {{ stats.present|percentage(stats.total, 2) }}
        """
        if total is None or total == 0:
            return '0%'
        
        try:
            pct = (float(value) / float(total)) * 100
            return f"{pct:.{decimals}f}%"
        except (ValueError, TypeError, ZeroDivisionError):
            return '0%'
    
    
    @app.template_filter('file_size')
    def file_size(bytes_size):
        """
        Convert bytes to human-readable file size.
        
        Args:
            bytes_size: Size in bytes
            
        Returns:
            Human-readable size (e.g., "1.5 MB")
            
        Usage in templates:
            {{ file.size|file_size }}
        """
        if bytes_size is None or bytes_size == 0:
            return '0 B'
        
        try:
            bytes_size = float(bytes_size)
            
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_size < 1024.0:
                    return f"{bytes_size:.1f} {unit}"
                bytes_size /= 1024.0
            
            return f"{bytes_size:.1f} PB"
        
        except (ValueError, TypeError):
            return '0 B'
    
    
    @app.template_filter('truncate_chars')
    def truncate_chars(value, length=50, suffix='...'):
        """
        Truncate string to specified length.
        
        Args:
            value: String to truncate
            length: Maximum length (default: 50)
            suffix: Suffix to add if truncated (default: '...')
            
        Returns:
            Truncated string
            
        Usage in templates:
            {{ student.notes|truncate_chars(100) }}
        """
        if value is None:
            return ''
        
        value = str(value)
        
        if len(value) <= length:
            return value
        
        return value[:length].rstrip() + suffix
    
    
    @app.template_filter('default_if_none')
    def default_if_none(value, default='N/A'):
        """
        Return default value if input is None.
        
        Args:
            value: Input value
            default: Default value (default: 'N/A')
            
        Returns:
            Original value or default
            
        Usage in templates:
            {{ student.phone|default_if_none('Not provided') }}
        """
        return value if value is not None else default
    
    
    @app.template_filter('status_badge')
    def status_badge(status):
        """
        Convert status string to Bootstrap badge class.
        
        Args:
            status: Status string (e.g., 'Present', 'Absent', 'Late')
            
        Returns:
            Bootstrap badge class string
            
        Usage in templates:
            <span class="badge {{ student.status|status_badge }}">{{ student.status }}</span>
        """
        status_map = {
            'Present': 'bg-success',
            'Absent': 'bg-secondary',
            'Late': 'bg-warning text-dark',
            'Excused': 'bg-info',
            'Scheduled': 'bg-primary',
            'Ongoing': 'bg-warning',
            'Completed': 'bg-success',
            'Cancelled': 'bg-danger',
            'Dismissed': 'bg-secondary',
            'Active': 'bg-success',
            'Inactive': 'bg-secondary',
        }
        
        return status_map.get(status, 'bg-secondary')
    
    
    # Return the app for chaining
    return app


# ============================================
# USAGE EXAMPLES IN TEMPLATES
# ============================================

"""
<!-- Date formatting -->
{{ session.date|format_date }}
{{ session.date|format_date('%d/%m/%Y') }}

<!-- Time formatting -->
{{ session.start_time|format_time }}
{{ session.start_time|format_time('%I:%M %p') }}

<!-- DateTime formatting -->
{{ student.attendance_time|format_datetime }}
{{ student.attendance_time|format_datetime('%d/%m/%Y %I:%M %p') }}

<!-- Time ago -->
{{ notification.created_at|time_ago }}

<!-- Duration -->
{{ duration(session.start_time, session.end_time) }}

<!-- Percentage -->
{{ stats.present|percentage(stats.total) }}
{{ stats.present|percentage(stats.total, 2) }}

<!-- File size -->
{{ upload.file_size|file_size }}

<!-- Truncate -->
{{ description|truncate_chars(100) }}

<!-- Default value -->
{{ student.email|default_if_none('No email') }}

<!-- Status badge -->
<span class="badge {{ student.status|status_badge }}">{{ student.status }}</span>
"""