"""
Notification Model
Handles system notifications for instructors, students, and admins
"""

from datetime import datetime, timedelta
from app import db
from sqlalchemy import Index


class Notification(db.Model):
    """
    Notifications for users (instructors, students, admins)
    """
    __tablename__ = 'notifications'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # User Information
    user_id = db.Column(db.String(50), nullable=False, index=True)
    user_type = db.Column(db.String(20), nullable=False)  # 'instructor', 'student', 'admin'
    
    # Notification Content
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'info', 'warning', 'success', 'error'
    
    # Status
    is_read = db.Column(db.Integer, default=0)  # 0 = unread, 1 = read
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Optional expiration
    
    # Action
    action_url = db.Column(db.String(500), nullable=True)  # Optional URL to navigate to
    
    # Priority
    priority = db.Column(db.String(20), default='normal')  # 'low', 'normal', 'high', 'urgent'
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            user_type.in_(['instructor', 'student', 'admin']),
            name='check_user_type'
        ),
        db.CheckConstraint(
            type.in_(['info', 'warning', 'success', 'error']),
            name='check_notification_type'
        ),
        db.CheckConstraint(
            priority.in_(['low', 'normal', 'high', 'urgent']),
            name='check_priority'
        ),
        Index('idx_notifications_user_read', 'user_id', 'is_read'),
        Index('idx_notifications_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.title} for {self.user_id}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': bool(self.is_read),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'action_url': self.action_url,
            'priority': self.priority,
            'time_ago': self.get_time_ago()
        }
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = 1
        db.session.commit()
        return True
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        self.is_read = 0
        db.session.commit()
        return True
    
    def is_expired(self):
        """Check if notification has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def get_time_ago(self):
        """Get human-readable time since creation"""
        if not self.created_at:
            return "Unknown"
        
        now = datetime.utcnow()
        diff = now - self.created_at
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    
    def get_icon_class(self):
        """Get Bootstrap icon class based on type"""
        icons = {
            'info': 'bi-info-circle',
            'warning': 'bi-exclamation-triangle',
            'success': 'bi-check-circle',
            'error': 'bi-x-circle'
        }
        return icons.get(self.type, 'bi-bell')
    
    def get_badge_class(self):
        """Get Bootstrap badge class based on type"""
        badges = {
            'info': 'bg-info',
            'warning': 'bg-warning',
            'success': 'bg-success',
            'error': 'bg-danger'
        }
        return badges.get(self.type, 'bg-secondary')
    
    def get_priority_badge_class(self):
        """Get Bootstrap badge class based on priority"""
        badges = {
            'low': 'bg-secondary',
            'normal': 'bg-primary',
            'high': 'bg-warning',
            'urgent': 'bg-danger'
        }
        return badges.get(self.priority, 'bg-primary')
    
    # Static Methods for Creating Notifications
    
    @staticmethod
    def create_notification(user_id, user_type, title, message, 
                          notification_type='info', priority='normal',
                          action_url=None, expires_in_days=None):
        """
        Create a new notification
        
        Args:
            user_id: User identifier
            user_type: 'instructor', 'student', 'admin'
            title: Notification title
            message: Notification message
            notification_type: 'info', 'warning', 'success', 'error'
            priority: 'low', 'normal', 'high', 'urgent'
            action_url: Optional URL to navigate to
            expires_in_days: Number of days until expiration (None = never)
        
        Returns:
            Notification object
        """
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        notification = Notification(
            user_id=user_id,
            user_type=user_type,
            title=title,
            message=message,
            type=notification_type,
            priority=priority,
            action_url=action_url,
            expires_at=expires_at
        )
        
        db.session.add(notification)
        db.session.commit()
        
        return notification
    
    @staticmethod
    def get_user_notifications(user_id, user_type, include_read=False, 
                              limit=None, offset=0):
        """
        Get notifications for a specific user
        
        Args:
            user_id: User identifier
            user_type: User type
            include_read: Include read notifications
            limit: Maximum number to return
            offset: Pagination offset
        
        Returns:
            List of Notification objects
        """
        query = Notification.query.filter_by(
            user_id=user_id,
            user_type=user_type
        )
        
        # Filter expired notifications
        query = query.filter(
            db.or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        )
        
        if not include_read:
            query = query.filter_by(is_read=0)
        
        query = query.order_by(Notification.created_at.desc())
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def get_unread_count(user_id, user_type):
        """Get count of unread notifications for user"""
        return Notification.query.filter_by(
            user_id=user_id,
            user_type=user_type,
            is_read=0
        ).filter(
            db.or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        ).count()
    
    @staticmethod
    def mark_all_as_read(user_id, user_type):
        """Mark all notifications as read for a user"""
        Notification.query.filter_by(
            user_id=user_id,
            user_type=user_type,
            is_read=0
        ).update({'is_read': 1})
        
        db.session.commit()
        return True
    
    @staticmethod
    def delete_expired():
        """Delete expired notifications (cleanup task)"""
        deleted_count = Notification.query.filter(
            Notification.expires_at.isnot(None),
            Notification.expires_at < datetime.utcnow()
        ).delete()
        
        db.session.commit()
        return deleted_count
    
    @staticmethod
    def delete_old_read_notifications(days_old=30):
        """
        Delete old read notifications (cleanup task)
        
        Args:
            days_old: Delete read notifications older than this many days
        
        Returns:
            Number of notifications deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        deleted_count = Notification.query.filter(
            Notification.is_read == 1,
            Notification.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        return deleted_count
    
    @staticmethod
    def broadcast_to_all_instructors(title, message, notification_type='info',
                                     priority='normal', action_url=None, expires_in_days=None):
        """
        Send notification to all active instructors
        
        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            action_url: Optional action URL
            expires_in_days: Number of days until expiration (None = never)
        
        Returns:
            Number of notifications created
        """
        from app.models.instructor import Instructor
        
        instructors = Instructor.query.filter_by(is_active=1).all()
        count = 0
        
        for instructor in instructors:
            Notification.create_notification(
                user_id=instructor.instructor_id,
                user_type='instructor',
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                action_url=action_url,
                expires_in_days=expires_in_days
            )
            count += 1
        
        return count
    
    @staticmethod
    def broadcast_to_class_students(class_id, title, message, 
                                    notification_type='info', priority='normal',
                                    action_url=None, expires_in_days=None):
        """
        Send notification to all students in a class
        
        Args:
            class_id: Class identifier
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            action_url: Optional action URL
            expires_in_days: Number of days until expiration (None = never)
        
        Returns:
            Number of notifications created
        """
        from app.models.class_ import Class
        
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return 0
        
        students = class_obj.get_students()
        count = 0
        
        for student in students:
            Notification.create_notification(
                user_id=student.student_id,
                user_type='student',
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                action_url=action_url,
                expires_in_days=expires_in_days
            )
            count += 1
        
        return count


# Notification Templates for Common Scenarios

class NotificationTemplates:
    """Pre-defined notification templates"""
    
    @staticmethod
    def session_starting_soon(instructor_id, session):
        """Notify instructor that session is starting soon"""
        class_obj = getattr(session, 'class')
        return Notification.create_notification(
            user_id=instructor_id,
            user_type='instructor',
            title='Session Starting Soon',
            message=f'Your session for {class_obj.class_name} starts in 15 minutes at {session.start_time}.',
            notification_type='info',
            priority='high',
            action_url=f'/lecturer/sessions/{session.session_id}',
            expires_in_days=1
        )
    
    @staticmethod
    def low_attendance_alert(instructor_id, session, attendance_rate):
        """Alert instructor about low attendance"""
        class_obj = getattr(session, 'class')
        return Notification.create_notification(
            user_id=instructor_id,
            user_type='instructor',
            title='Low Attendance Alert',
            message=f'Session {class_obj.class_name} on {session.date} had only {attendance_rate}% attendance.',
            notification_type='warning',
            priority='normal',
            action_url=f'/lecturer/sessions/{session.session_id}',
            expires_in_days=7
        )
    
    @staticmethod
    def session_dismissed(class_id, session, reason):
        """Notify students that session was dismissed"""
        from app.models.class_ import Class
        class_obj = Class.query.get(class_id)
        
        if not class_obj:
            return 0
        
        return Notification.broadcast_to_class_students(
            class_id=class_id,
            title='Session Dismissed',
            message=f'The session for {class_obj.class_name} on {session.date} has been dismissed. Reason: {reason}',
            notification_type='warning',
            priority='high',
            expires_in_days=3
        )
    
    @staticmethod
    def session_rescheduled(class_id, old_date, new_date, new_time):
        """Notify students about rescheduled session"""
        return Notification.broadcast_to_class_students(
            class_id=class_id,
            title='Session Rescheduled',
            message=f'Session originally scheduled for {old_date} has been rescheduled to {new_date} at {new_time}.',
            notification_type='info',
            priority='high',
            expires_in_days=7
        )
    
    @staticmethod
    def student_low_attendance(student_id, course_name, attendance_rate, threshold):
        """Warn student about low attendance"""
        return Notification.create_notification(
            user_id=student_id,
            user_type='student',
            title='Low Attendance Warning',
            message=f'Your attendance in {course_name} is {attendance_rate}%, below the required {threshold}%. Please improve your attendance.',
            notification_type='warning',
            priority='urgent',
            expires_in_days=14
        )
    
    @staticmethod
    def attendance_marked_success(student_id, session):
        """Confirm attendance was marked"""
        class_obj = getattr(session, 'class')
        return Notification.create_notification(
            user_id=student_id,
            user_type='student',
            title='Attendance Marked',
            message=f'Your attendance for {class_obj.class_name} on {session.date} has been recorded.',
            notification_type='success',
            priority='low',
            expires_in_days=1
        )
    
    @staticmethod
    def system_maintenance(title, message, scheduled_time):
        """Broadcast system maintenance notification"""
        count = 0
        
        # Notify all instructors
        count += Notification.broadcast_to_all_instructors(
            title=title,
            message=f'{message} Scheduled for: {scheduled_time}',
            notification_type='warning',
            priority='high'
        )
        
        # Could also notify students and admins here
        
        return count
    
    @staticmethod
    def new_feature_announcement(title, description):
        """Announce new features to all users"""
        return Notification.broadcast_to_all_instructors(
            title=f'New Feature: {title}',
            message=description,
            notification_type='info',
            priority='low',
            expires_in_days=7
        )