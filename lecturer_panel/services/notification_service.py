"""
Notification Service for Face Recognition Attendance System
Handles in-app notifications, alerts, and system messages for lecturers
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from lecturer_panel.utils.helpers import log_error
from lecturer_panel.services.database_service import DatabaseService


class NotificationService:
    """Service for managing notifications and alerts"""
    
    def __init__(self):
        self.db_service = DatabaseService()
        self.notification_types = ['info', 'warning', 'success', 'error']
        self.priorities = ['low', 'normal', 'high', 'urgent']
        self.user_types = ['instructor', 'student', 'admin']
    
    def create_notification(self, user_id: str, user_type: str, title: str, 
                          message: str, notification_type: str = 'info',
                          priority: str = 'normal', expires_at: Optional[datetime] = None,
                          action_url: Optional[str] = None) -> Dict:
        """Create a new notification"""
        try:
            # Validate inputs
            if user_type not in self.user_types:
                return {'success': False, 'message': 'Invalid user type'}
            if notification_type not in self.notification_types:
                return {'success': False, 'message': 'Invalid notification type'}
            if priority not in self.priorities:
                return {'success': False, 'message': 'Invalid priority level'}
            if expires_at is None:
                expires_at = datetime.now() + timedelta(days=30)
            query = '''
                INSERT INTO notifications 
                (user_id, user_type, title, message, type, priority, expires_at, action_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            params = (user_id, user_type, title, message, notification_type, priority, expires_at, action_url)
            with self.db_service.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                notification_id = cursor.lastrowid
                conn.commit()
            return {
                'success': True, 
                'notification_id': notification_id,
                'message': 'Notification created successfully'
            }
        except Exception as e:
            log_error(f"Error creating notification: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to create notification'}

    def get_user_notifications(self, user_id: str, user_type: str, 
                             unread_only: bool = False, limit: int = 50) -> List[Dict]:
        """Get notifications for a specific user"""
        try:
            query = '''
                SELECT id, title, message, type, priority, is_read, 
                       created_at, expires_at, action_url
                FROM notifications 
                WHERE user_id = ? AND user_type = ? 
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            '''
            params = [user_id, user_type]
            if unread_only:
                query += ' AND is_read = 0'
            query += ' ORDER BY priority DESC, created_at DESC LIMIT ?'
            params.append(limit)
            results = self.db_service.execute_query(query, tuple(params), fetch='all')
            notifications = []
            for row in results:
                notification = {
                    'id': row['id'],
                    'title': row['title'],
                    'message': row['message'],
                    'type': row['type'],
                    'priority': row['priority'],
                    'is_read': bool(row['is_read']),
                    'created_at': row['created_at'],
                    'expires_at': row['expires_at'],
                    'action_url': row['action_url'],
                    'time_ago': self._get_time_ago(row['created_at'])
                }
                notifications.append(notification)
            return notifications
        except Exception as e:
            log_error(f"Error getting user notifications: {str(e)}", "NOTIFICATION_ERROR")
            return []

    def mark_notification_read(self, notification_id: int, user_id: str) -> Dict:
        """Mark a notification as read"""
        try:
            # Verify notification belongs to user
            query = 'SELECT user_id FROM notifications WHERE id = ?'
            result = self.db_service.execute_query(query, (notification_id,), fetch='one')
            if not result or result['user_id'] != user_id:
                return {'success': False, 'message': 'Notification not found'}
            update_query = 'UPDATE notifications SET is_read = 1 WHERE id = ?'
            self.db_service.execute_query(update_query, (notification_id,))
            return {'success': True, 'message': 'Notification marked as read'}
        except Exception as e:
            log_error(f"Error marking notification as read: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to mark notification as read'}

    def mark_all_read(self, user_id: str, user_type: str) -> Dict:
        """Mark all notifications as read for a user"""
        try:
            update_query = '''
                UPDATE notifications 
                SET is_read = 1 
                WHERE user_id = ? AND user_type = ? AND is_read = 0
            '''
            updated_count = self.db_service.execute_query(update_query, (user_id, user_type))
            return {
                'success': True, 
                'message': f'Marked {updated_count} notifications as read'
            }
        except Exception as e:
            log_error(f"Error marking all notifications as read: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to mark notifications as read'}

    def delete_notification(self, notification_id: int, user_id: str) -> Dict:
        """Delete a notification"""
        try:
            # Verify notification belongs to user
            query = 'SELECT user_id FROM notifications WHERE id = ?'
            result = self.db_service.execute_query(query, (notification_id,), fetch='one')
            if not result or result['user_id'] != user_id:
                return {'success': False, 'message': 'Notification not found'}
            delete_query = 'DELETE FROM notifications WHERE id = ?'
            self.db_service.execute_query(delete_query, (notification_id,))
            return {'success': True, 'message': 'Notification deleted successfully'}
        except Exception as e:
            log_error(f"Error deleting notification: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to delete notification'}

    def get_notification_count(self, user_id: str, user_type: str, 
                             unread_only: bool = True) -> int:
        """Get notification count for a user"""
        try:
            query = '''
                SELECT COUNT(*) as count FROM notifications 
                WHERE user_id = ? AND user_type = ?
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            '''
            params = [user_id, user_type]
            if unread_only:
                query += ' AND is_read = 0'
            result = self.db_service.execute_query(query, tuple(params), fetch='one')
            return result['count'] if result else 0
        except Exception as e:
            log_error(f"Error getting notification count: {str(e)}", "NOTIFICATION_ERROR")
            return 0

    def cleanup_expired_notifications(self) -> Dict:
        """Clean up expired notifications"""
        try:
            delete_query = '''
                DELETE FROM notifications 
                WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
            '''
            deleted_count = self.db_service.execute_query(delete_query)
            return {
                'success': True, 
                'message': f'Cleaned up {deleted_count} expired notifications'
            }
        except Exception as e:
            log_error(f"Error cleaning up notifications: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to clean up notifications'}
    
    def send_session_reminder(self, instructor_id: int, session_info: Dict) -> Dict:
        """Send session reminder notification"""
        try:
            title = f"Session Reminder: {session_info.get('class_name', 'Unknown Class')}"
            message = f"Your session for {session_info.get('class_name')} is starting in 15 minutes at {session_info.get('start_time')}."
            
            return self.create_notification(
                user_id=str(instructor_id),
                user_type='instructor',
                title=title,
                message=message,
                notification_type='info',
                priority='normal',
                expires_at=datetime.now() + timedelta(hours=2)
            )
            
        except Exception as e:
            log_error(f"Error sending session reminder: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to send session reminder'}
    
    def send_attendance_alert(self, instructor_id: int, session_info: Dict, 
                            attendance_percentage: float) -> Dict:
        """Send low attendance alert"""
        try:
            title = f"Low Attendance Alert"
            message = f"Attendance for {session_info.get('class_name')} is {attendance_percentage:.1f}%. Consider following up with absent students."
            
            return self.create_notification(
                user_id=str(instructor_id),
                user_type='instructor',
                title=title,
                message=message,
                notification_type='warning',
                priority='high',
                expires_at=datetime.now() + timedelta(days=1)
            )
            
        except Exception as e:
            log_error(f"Error sending attendance alert: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to send attendance alert'}
    
    def send_system_notification(self, message: str, notification_type: str = 'info',
                               priority: str = 'normal', target_users: List[str] = None) -> Dict:
        """Send system-wide notification"""
        try:
            if target_users is None:
                # Get all active instructors
                conn = sqlite3.connect('database.db') # Assuming database.db is the correct path
                cursor = conn.cursor()
                cursor.execute('SELECT instructor_id FROM instructors WHERE is_active = 1')
                target_users = [str(row[0]) for row in cursor.fetchall()]
                conn.close()
            
            success_count = 0
            for user_id in target_users:
                result = self.create_notification(
                    user_id=user_id,
                    user_type='instructor',
                    title='System Notification',
                    message=message,
                    notification_type=notification_type,
                    priority=priority
                )
                if result['success']:
                    success_count += 1
            
            return {
                'success': True,
                'message': f'Sent notification to {success_count} users'
            }
            
        except Exception as e:
            log_error(f"Error sending system notification: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to send system notification'}
    
    def send_session_dismissal_notification(self, instructor_id: int, session_info: Dict,
                                          reason: str) -> Dict:
        """Send session dismissal notification"""
        try:
            title = f"Session Dismissed: {session_info.get('class_name', 'Unknown Class')}"
            message = f"Your session has been dismissed. Reason: {reason}"
            
            return self.create_notification(
                user_id=str(instructor_id),
                user_type='instructor',
                title=title,
                message=message,
                notification_type='warning',
                priority='high',
                expires_at=datetime.now() + timedelta(days=7)
            )
            
        except Exception as e:
            log_error(f"Error sending dismissal notification: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to send dismissal notification'}
    
    def send_camera_quality_alert(self, instructor_id: int, quality_score: float) -> Dict:
        """Send camera quality alert"""
        try:
            title = "Camera Quality Alert"
            message = f"Camera quality is below recommended threshold ({quality_score:.1f}%). Please check your camera setup."
            
            return self.create_notification(
                user_id=str(instructor_id),
                user_type='instructor',
                title=title,
                message=message,
                notification_type='warning',
                priority='normal',
                expires_at=datetime.now() + timedelta(hours=6)
            )
            
        except Exception as e:
            log_error(f"Error sending camera quality alert: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to send camera quality alert'}
    
    def get_notification_settings(self, instructor_id: int) -> Dict:
        """Get notification settings for an instructor"""
        try:
            conn = sqlite3.connect('database.db') # Assuming database.db is the correct path
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT notification_settings FROM lecturer_preferences 
                WHERE instructor_id = ?
            ''', (instructor_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return json.loads(result[0])
            else:
                # Return default settings
                return {
                    'session_reminders': True,
                    'attendance_alerts': True,
                    'system_notifications': True,
                    'camera_quality_alerts': True,
                    'email_notifications': False,
                    'push_notifications': True
                }
                
        except Exception as e:
            log_error(f"Error getting notification settings: {str(e)}", "NOTIFICATION_ERROR")
            return {}
    
    def update_notification_settings(self, instructor_id: int, settings: Dict) -> Dict:
        """Update notification settings for an instructor"""
        try:
            conn = sqlite3.connect('database.db') # Assuming database.db is the correct path
            cursor = conn.cursor()
            
            settings_json = json.dumps(settings)
            
            cursor.execute('''
                UPDATE lecturer_preferences 
                SET notification_settings = ?, updated_at = CURRENT_TIMESTAMP
                WHERE instructor_id = ?
            ''', (settings_json, instructor_id))
            
            if cursor.rowcount == 0:
                # Insert new preferences record
                cursor.execute('''
                    INSERT INTO lecturer_preferences (instructor_id, notification_settings)
                    VALUES (?, ?)
                ''', (instructor_id, settings_json))
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'message': 'Notification settings updated successfully'}
            
        except Exception as e:
            log_error(f"Error updating notification settings: {str(e)}", "NOTIFICATION_ERROR")
            return {'success': False, 'message': 'Failed to update notification settings'}
    
    def _get_time_ago(self, timestamp: str) -> str:
        """Get human-readable time ago string"""
        try:
            created_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            now = datetime.now()
            diff = now - created_time
            
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            else:
                return "Just now"
                
        except Exception:
            return "Unknown"
    
    def get_dashboard_notifications(self, instructor_id: int, limit: int = 5) -> List[Dict]:
        """Get notifications for dashboard widget"""
        try:
            notifications = self.get_user_notifications(
                user_id=str(instructor_id),
                user_type='instructor',
                unread_only=False,
                limit=limit
            )
            
            # Add badge colors based on type and priority
            for notification in notifications:
                notification['badge_color'] = self._get_badge_color(
                    notification['type'], 
                    notification['priority']
                )
            
            return notifications
            
        except Exception as e:
            log_error(f"Error getting dashboard notifications: {str(e)}", "NOTIFICATION_ERROR")
            return []
    
    def _get_badge_color(self, notification_type: str, priority: str) -> str:
        """Get badge color based on notification type and priority"""
        if priority == 'urgent':
            return 'danger'
        elif priority == 'high':
            return 'warning'
        elif notification_type == 'success':
            return 'success'
        elif notification_type == 'error':
            return 'danger'
        elif notification_type == 'warning':
            return 'warning'
        else:
            return 'info'