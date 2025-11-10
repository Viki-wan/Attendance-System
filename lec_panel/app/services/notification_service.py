"""
Notification Service
Handles notification creation, delivery, and management
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from app import db
from app.models.notification import Notification, NotificationTemplates
from app.models.session import ClassSession
from app.models.attendance import Attendance
from app.models.user import Instructor
from app.models.student import Student
from app.models.settings import Settings


class NotificationService:
    """Service layer for notification operations"""
    
    # ==================== CREATE NOTIFICATIONS ====================
    
    @staticmethod
    def create_notification(user_id: str, user_type: str, title: str, 
                          message: str, notification_type: str = 'info',
                          priority: str = 'normal', action_url: str = None,
                          expires_in_days: int = None) -> Tuple[Optional[Notification], Optional[str]]:
        """
        Create a notification for a user
        
        Args:
            user_id: User identifier
            user_type: 'instructor', 'student', 'admin'
            title: Notification title
            message: Notification message
            notification_type: 'info', 'warning', 'success', 'error'
            priority: 'low', 'normal', 'high', 'urgent'
            action_url: Optional URL to navigate to
            expires_in_days: Days until expiration
        
        Returns:
            Tuple of (Notification object, error message)
        """
        try:
            notification = Notification.create_notification(
                user_id=user_id,
                user_type=user_type,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                action_url=action_url,
                expires_in_days=expires_in_days
            )
            return notification, None
        except Exception as e:
            return None, str(e)
    
    # ==================== RETRIEVE NOTIFICATIONS ====================
    
    @staticmethod
    def get_user_notifications(user_id: str, user_type: str, 
                              include_read: bool = False,
                              page: int = 1, per_page: int = 20) -> Dict:
        """
        Get paginated notifications for a user
        
        Args:
            user_id: User identifier
            user_type: User type
            include_read: Include read notifications
            page: Page number
            per_page: Items per page
        
        Returns:
            Dictionary with notifications and pagination info
        """
        try:
            offset = (page - 1) * per_page
            
            notifications = Notification.get_user_notifications(
                user_id=user_id,
                user_type=user_type,
                include_read=include_read,
                limit=per_page,
                offset=offset
            )
            
            total_count = Notification.query.filter_by(
                user_id=user_id,
                user_type=user_type
            ).filter(
                db.or_(
                    Notification.expires_at.is_(None),
                    Notification.expires_at > datetime.utcnow()
                )
            )
            
            if not include_read:
                total_count = total_count.filter_by(is_read=0)
            
            total_count = total_count.count()
            
            return {
                'notifications': [n.to_dict() for n in notifications],
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'has_next': (page * per_page) < total_count,
                'has_prev': page > 1
            }
        except Exception as e:
            return {
                'notifications': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'has_next': False,
                'has_prev': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_unread_count(user_id: str, user_type: str) -> int:
        """Get count of unread notifications"""
        return Notification.get_unread_count(user_id, user_type)
    
    @staticmethod
    def get_recent_notifications(user_id: str, user_type: str, 
                                limit: int = 5) -> List[Notification]:
        """Get most recent notifications"""
        return Notification.get_user_notifications(
            user_id=user_id,
            user_type=user_type,
            include_read=False,
            limit=limit
        )
    
    # ==================== UPDATE NOTIFICATIONS ====================
    
    @staticmethod
    def mark_as_read(notification_id: int, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Mark notification as read (with ownership check)
        
        Args:
            notification_id: Notification ID
            user_id: User making the request
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                return False, "Notification not found"
            
            if notification.user_id != user_id:
                return False, "Unauthorized"
            
            notification.mark_as_read()
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def mark_as_unread(notification_id: int, user_id: str) -> Tuple[bool, Optional[str]]:
        """Mark notification as unread (with ownership check)"""
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                return False, "Notification not found"
            
            if notification.user_id != user_id:
                return False, "Unauthorized"
            
            notification.mark_as_unread()
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def mark_all_as_read(user_id: str, user_type: str) -> Tuple[bool, Optional[str]]:
        """Mark all notifications as read for a user"""
        try:
            Notification.mark_all_as_read(user_id, user_type)
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def delete_notification(notification_id: int, user_id: str) -> Tuple[bool, Optional[str]]:
        """Delete a notification (with ownership check)"""
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                return False, "Notification not found"
            
            if notification.user_id != user_id:
                return False, "Unauthorized"
            
            db.session.delete(notification)
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, str(e)
    
    # ==================== SESSION-RELATED NOTIFICATIONS ====================
    
    @staticmethod
    def notify_session_missed(session_id: int) -> Tuple[bool, Optional[str]]:
        """
        Notify instructor that a scheduled session was missed
        
        Args:
            session_id: Session ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            session = ClassSession.query.get(session_id)
            if not session or not session.created_by:
                return False, "Session or instructor not found"
            
            # Get class and course information
            class_info = Class.query.get(session.class_id)
            course_name = class_info.course.course_name if class_info and class_info.course else "Unknown Course"
            class_name = class_info.class_name if class_info else session.class_id
            
            # Create notification for instructor
            notification = Notification.create_notification(
                user_id=session.created_by,
                user_type='instructor',
                title='Session Missed',
                message=f'Your scheduled session for {course_name} ({class_name}) on {session.date} at {session.start_time} was not started and has been marked as missed.',
                notification_type='warning',
                priority='high',
                action_url=f'/sessions/{session_id}',
                expires_in_days=7
            )
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def notify_session_starting_soon(session_id: int) -> Tuple[bool, Optional[str]]:
        """
        Notify instructor that session is starting soon (15 min before)
        
        Args:
            session_id: Session ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            session = ClassSession.query.get(session_id)
            if not session or not session.created_by:
                return False, "Session or instructor not found"
            
            NotificationTemplates.session_starting_soon(
                instructor_id=session.created_by,
                session=session
            )
            return True, None
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def notify_session_dismissed(session_id: int, reason: str) -> Tuple[int, Optional[str]]:
        """
        Notify all students in class that session was dismissed
        
        Args:
            session_id: Session ID
            reason: Dismissal reason
        
        Returns:
            Tuple of (number of notifications sent, error_message)
        """
        try:
            session = ClassSession.query.get(session_id)
            if not session:
                return 0, "Session not found"
            
            count = NotificationTemplates.session_dismissed(
                class_id=session.class_id,
                session=session,
                reason=reason
            )
            return count, None
        except Exception as e:
            return 0, str(e)
    
    @staticmethod
    def notify_session_rescheduled(session_id: int, old_date: str, 
                                  new_date: str, new_time: str) -> Tuple[int, Optional[str]]:
        """Notify students about rescheduled session"""
        try:
            session = ClassSession.query.get(session_id)
            if not session:
                return 0, "Session not found"
            
            count = NotificationTemplates.session_rescheduled(
                class_id=session.class_id,
                old_date=old_date,
                new_date=new_date,
                new_time=new_time
            )
            return count, None
        except Exception as e:
            return 0, str(e)
    
    @staticmethod
    def notify_low_attendance(session_id: int) -> Tuple[bool, Optional[str]]:
        """
        Alert instructor if session had low attendance
        
        Args:
            session_id: Session ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            session = ClassSession.query.get(session_id)
            if not session or not session.created_by:
                return False, "Session or instructor not found"
            
            # Get threshold from settings
            threshold_setting = Settings.get_setting('low_attendance_threshold')
            threshold = float(threshold_setting) if threshold_setting else 70.0
            
            if session.attendance_rate < threshold:
                NotificationTemplates.low_attendance_alert(
                    instructor_id=session.created_by,
                    session=session,
                    attendance_rate=session.attendance_rate
                )
                return True, None
            
            return False, "Attendance rate is above threshold"
        except Exception as e:
            return False, str(e)
    
    # ==================== STUDENT ATTENDANCE NOTIFICATIONS ====================
    
    @staticmethod
    def notify_student_low_attendance(student_id: str, course_code: str) -> Tuple[bool, Optional[str]]:
        """
        Warn student about low attendance in a course
        
        Args:
            student_id: Student ID
            course_code: Course code
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            from app.models.course import Course
            
            student = Student.query.get(student_id)
            course = Course.query.get(course_code)
            
            if not student or not course:
                return False, "Student or course not found"
            
            # Calculate attendance rate
            attendance_rate = student.calculate_attendance_rate(course_code)
            
            # Get threshold
            threshold_setting = Settings.get_setting('low_attendance_threshold')
            threshold = float(threshold_setting) if threshold_setting else 70.0
            
            if attendance_rate < threshold:
                NotificationTemplates.student_low_attendance(
                    student_id=student_id,
                    course_name=course.course_name,
                    attendance_rate=round(attendance_rate, 1),
                    threshold=threshold
                )
                return True, None
            
            return False, "Attendance rate is acceptable"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def check_and_notify_all_low_attendance_students() -> Dict:
        """
        Check all students and notify those with low attendance
        (Background task - run daily/weekly)
        
        Returns:
            Dictionary with statistics
        """
        try:
            from app.models.course import Course
            
            threshold_setting = Settings.get_setting('low_attendance_threshold')
            threshold = float(threshold_setting) if threshold_setting else 70.0
            
            notified_count = 0
            students_checked = 0
            
            # Get all active students
            students = Student.query.filter_by(is_active=1).all()
            
            for student in students:
                students_checked += 1
                
                # Get student's courses
                enrollments = student.get_courses()
                
                for enrollment in enrollments:
                    if enrollment.status != 'Active':
                        continue
                    
                    attendance_rate = student.calculate_attendance_rate(
                        enrollment.course_code
                    )
                    
                    if attendance_rate < threshold:
                        success, _ = NotificationService.notify_student_low_attendance(
                            student_id=student.student_id,
                            course_code=enrollment.course_code
                        )
                        if success:
                            notified_count += 1
            
            return {
                'success': True,
                'students_checked': students_checked,
                'notifications_sent': notified_count,
                'threshold': threshold
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'students_checked': 0,
                'notifications_sent': 0
            }
    
    @staticmethod
    def notify_attendance_marked(student_id: str, session_id: int) -> Tuple[bool, Optional[str]]:
        """Confirm to student that their attendance was marked"""
        try:
            session = ClassSession.query.get(session_id)
            if not session:
                return False, "Session not found"
            
            NotificationTemplates.attendance_marked_success(
                student_id=student_id,
                session=session
            )
            return True, None
        except Exception as e:
            return False, str(e)
    
    # ==================== BROADCAST NOTIFICATIONS ====================
    
    @staticmethod
    def broadcast_to_all_instructors(title: str, message: str,
                                    notification_type: str = 'info',
                                    priority: str = 'normal',
                                    action_url: str = None) -> Tuple[int, Optional[str]]:
        """
        Send notification to all active instructors
        
        Returns:
            Tuple of (count, error_message)
        """
        try:
            count = Notification.broadcast_to_all_instructors(
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                action_url=action_url
            )
            return count, None
        except Exception as e:
            return 0, str(e)
    
    @staticmethod
    def broadcast_to_class(class_id: str, title: str, message: str,
                          notification_type: str = 'info',
                          priority: str = 'normal',
                          action_url: str = None) -> Tuple[int, Optional[str]]:
        """
        Send notification to all students in a class
        
        Returns:
            Tuple of (count, error_message)
        """
        try:
            count = Notification.broadcast_to_class_students(
                class_id=class_id,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                action_url=action_url
            )
            return count, None
        except Exception as e:
            return 0, str(e)
    
    @staticmethod
    def announce_system_maintenance(title: str, message: str, 
                                   scheduled_time: str) -> Tuple[int, Optional[str]]:
        """Broadcast system maintenance notification"""
        try:
            count = NotificationTemplates.system_maintenance(
                title=title,
                message=message,
                scheduled_time=scheduled_time
            )
            return count, None
        except Exception as e:
            return 0, str(e)
    
    @staticmethod
    def announce_new_feature(title: str, description: str) -> Tuple[int, Optional[str]]:
        """Announce new features to all users"""
        try:
            count = NotificationTemplates.new_feature_announcement(
                title=title,
                description=description
            )
            return count, None
        except Exception as e:
            return 0, str(e)
    
    # ==================== CLEANUP OPERATIONS ====================
    
    @staticmethod
    def cleanup_expired_notifications() -> Dict:
        """
        Delete expired notifications (maintenance task)
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            deleted_count = Notification.delete_expired()
            return {
                'success': True,
                'deleted': deleted_count,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'deleted': 0
            }
    
    @staticmethod
    def cleanup_old_read_notifications(days_old: int = None) -> Dict:
        """
        Delete old read notifications (maintenance task)
        
        Args:
            days_old: Delete notifications older than this (from settings if None)
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            if days_old is None:
                retention_setting = Settings.get_setting('notification_retention_days')
                days_old = int(retention_setting) if retention_setting else 30
            
            deleted_count = Notification.delete_old_read_notifications(days_old)
            return {
                'success': True,
                'deleted': deleted_count,
                'days_old': days_old,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'deleted': 0
            }
    
    # ==================== SCHEDULED TASKS ====================
    
    @staticmethod
    def send_session_reminders() -> Dict:
        """
        Send reminders for sessions starting soon
        Background task - run every 15 minutes
        
        Returns:
            Dictionary with statistics
        """
        try:
            now = datetime.utcnow()
            reminder_time = now + timedelta(minutes=15)
            
            # Find sessions starting in 15 minutes
            sessions = ClassSession.query.filter(
                ClassSession.status == 'scheduled',
                ClassSession.date == reminder_time.date(),
                ClassSession.start_time >= reminder_time.time(),
                ClassSession.start_time <= (reminder_time + timedelta(minutes=1)).time()
            ).all()
            
            notified_count = 0
            for session in sessions:
                success, _ = NotificationService.notify_session_starting_soon(
                    session.session_id
                )
                if success:
                    notified_count += 1
            
            return {
                'success': True,
                'sessions_checked': len(sessions),
                'reminders_sent': notified_count,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'reminders_sent': 0
            }
    
    @staticmethod
    def check_completed_sessions_for_low_attendance() -> Dict:
        """
        Check recently completed sessions for low attendance
        Background task - run daily
        
        Returns:
            Dictionary with statistics
        """
        try:
            # Get threshold
            threshold_setting = Settings.get_setting('low_attendance_threshold')
            threshold = float(threshold_setting) if threshold_setting else 70.0
            
            # Check sessions completed in last 24 hours
            yesterday = datetime.utcnow() - timedelta(hours=24)
            
            sessions = ClassSession.query.filter(
                ClassSession.status == 'completed',
                ClassSession.updated_at >= yesterday
            ).all()
            
            notified_count = 0
            for session in sessions:
                if session.attendance_rate < threshold:
                    success, _ = NotificationService.notify_low_attendance(
                        session.session_id
                    )
                    if success:
                        notified_count += 1
            
            return {
                'success': True,
                'sessions_checked': len(sessions),
                'alerts_sent': notified_count,
                'threshold': threshold,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'alerts_sent': 0
            }