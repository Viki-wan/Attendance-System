"""
Real-time Dashboard Service
Handles live updates, WebSocket events, and real-time data broadcasting
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import current_app
from flask_socketio import emit, join_room, leave_room
from lecturer_panel.config import Config
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.services.attendance_service import AttendanceService
from lecturer_panel.services.session_service import SessionService
from lecturer_panel.utils.helpers import log_error


def get_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_dashboard_stats(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(*) as total_sessions,
                   SUM(cs.status = 'completed') as completed,
                   SUM(cs.status = 'ongoing') as ongoing,
                   AVG(CASE WHEN cs.total_students > 0 THEN 100.0 * cs.attendance_count / cs.total_students ELSE 0 END) as avg_attendance
            FROM class_sessions cs
            JOIN class_instructors ci ON cs.class_id = ci.class_id
            WHERE ci.instructor_id = ? AND cs.date = ?
        ''', (user_id, today))
        row = cur.fetchone()
        return {
            'total_sessions': row['total_sessions'] or 0,
            'completed': row['completed'] or 0,
            'ongoing': row['ongoing'] or 0,
            'avg_attendance': round(row['avg_attendance'] or 0, 1)
        }

def get_sessions(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time, cs.status, cs.attendance_count, cs.total_students, c.class_name
            FROM class_sessions cs
            JOIN class_instructors ci ON cs.class_id = ci.class_id
            JOIN classes c ON cs.class_id = c.class_id
            WHERE ci.instructor_id = ? AND cs.date = ?
            ORDER BY cs.start_time
        ''', (user_id, today))
        sessions = []
        for row in cur.fetchall():
            progress = int(100 * row['attendance_count'] / row['total_students']) if row['total_students'] else 0
            sessions.append({
                'title': row['class_name'],
                'time': f"{row['start_time']} - {row['end_time']}",
                'location': row['class_id'],
                'progress': progress,
                'status': row['status'].capitalize()
            })
        return sessions

def get_activity_feed(user_id):
    icon_map = {
        'login': 'fa-sign-in-alt',
        'logout': 'fa-sign-out-alt',
        'attendance_marked': 'fa-check',
        'session_created': 'fa-calendar-plus',
        'session_updated': 'fa-edit',
        'session_dismissed': 'fa-times',
        'bulk_attendance': 'fa-users',
        'password_changed': 'fa-key',
        'account_created': 'fa-user-plus',
        'default': 'fa-info-circle'
    }
    color_map = {
        'login': 'var(--primary-color)',
        'logout': 'var(--secondary-color)',
        'attendance_marked': 'var(--success-color)',
        'session_created': 'var(--primary-color)',
        'session_updated': 'var(--warning-color)',
        'session_dismissed': 'var(--danger-color)',
        'bulk_attendance': 'var(--success-color)',
        'password_changed': 'var(--warning-color)',
        'account_created': 'var(--success-color)',
        'default': 'var(--secondary-color)'
    }
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT activity_type, description, timestamp
            FROM activity_log
            WHERE user_id = ? AND user_type = 'instructor'
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (user_id,))
        feed = []
        for row in cur.fetchall():
            icon = icon_map.get(row['activity_type'], icon_map['default'])
            color = color_map.get(row['activity_type'], color_map['default'])
            dt = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            delta = datetime.now() - dt
            if delta.days > 0:
                time_ago = f"{delta.days}d ago"
            elif delta.seconds > 3600:
                time_ago = f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                time_ago = f"{delta.seconds // 60}m ago"
            else:
                time_ago = "Just now"
            feed.append({
                'icon': icon,
                'color': color,
                'text': row['description'] or row['activity_type'].replace('_', ' ').capitalize(),
                'time_ago': time_ago
            })
        return feed

def get_attendance_summary(user_id):
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    with get_db() as conn:
        cur = conn.cursor()
        # This week
        cur.execute('''
            SELECT AVG(CASE WHEN cs.total_students > 0 THEN 100.0 * cs.attendance_count / cs.total_students ELSE 0 END) as week
            FROM class_sessions cs
            JOIN class_instructors ci ON cs.class_id = ci.class_id
            WHERE ci.instructor_id = ? AND cs.date >= ?
        ''', (user_id, week_ago.strftime('%Y-%m-%d')))
        week = cur.fetchone()['week'] or 0
        # This month
        cur.execute('''
            SELECT AVG(CASE WHEN cs.total_students > 0 THEN 100.0 * cs.attendance_count / cs.total_students ELSE 0 END) as month
            FROM class_sessions cs
            JOIN class_instructors ci ON cs.class_id = ci.class_id
            WHERE ci.instructor_id = ? AND cs.date >= ?
        ''', (user_id, month_ago.strftime('%Y-%m-%d')))
        month = cur.fetchone()['month'] or 0
        # This semester (all time)
        cur.execute('''
            SELECT AVG(CASE WHEN cs.total_students > 0 THEN 100.0 * cs.attendance_count / cs.total_students ELSE 0 END) as semester
            FROM class_sessions cs
            JOIN class_instructors ci ON cs.class_id = ci.class_id
            WHERE ci.instructor_id = ?
        ''', (user_id,))
        semester = cur.fetchone()['semester'] or 0
        return {
            'week': round(week, 1),
            'month': round(month, 1),
            'semester': round(semester, 1)
        }

def get_camera_status(user_id):
    # Placeholder: In a real system, query system_metrics or a live service.
    return {
        'online': True,
        'resolution': '1080p',
        'light_quality': 'Good',
        'recognition_rate': 95
    }


class RealTimeDashboardService:
    """Service for handling real-time dashboard updates and WebSocket communications"""
    
    def __init__(self):
        self.db_service = DatabaseService()
        self.attendance_service = AttendanceService()
        self.session_service = SessionService()
    
    def get_live_dashboard_data(self, user_id: int) -> Dict:
        """
        Get complete dashboard data for real-time updates
        
        Args:
            user_id: Instructor user ID
            
        Returns:
            Dict with all dashboard widget data
        """
        try:
            # Get all dashboard components
            stats = get_dashboard_stats(user_id)
            sessions = get_sessions(user_id)
            activity_feed = get_activity_feed(user_id)
            attendance_summary = get_attendance_summary(user_id)
            camera_status = get_camera_status(user_id)
            active_session = self._get_active_session_data(user_id)
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'stats': stats,
                    'sessions': sessions,
                    'activity_feed': activity_feed,
                    'attendance_summary': attendance_summary,
                    'camera_status': camera_status,
                    'active_session': active_session
                }
            }
            
        except Exception as e:
            log_error(f"Error getting live dashboard data: {str(e)}", "REALTIME_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to get dashboard data'}
    
    def _get_live_stats(self, user_id: int) -> Dict:
        """Get live statistics for dashboard"""
        conn = self.db_service.get_connection()
        cursor = conn.cursor()
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Total sessions today
            cursor.execute('''
                SELECT COUNT(*) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date = ?
            ''', (user_id, today))
            total_sessions = cursor.fetchone()[0]
            
            # Completed sessions today
            cursor.execute('''
                SELECT COUNT(*) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date = ? AND cs.status = 'completed'
            ''', (user_id, today))
            completed_sessions = cursor.fetchone()[0]
            
            # Ongoing sessions
            cursor.execute('''
                SELECT COUNT(*) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date = ? AND cs.status = 'ongoing'
            ''', (user_id, today))
            ongoing_sessions = cursor.fetchone()[0]
            
            # Average attendance rate for the week
            week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT AVG(
                    CASE 
                        WHEN cs.total_students > 0 
                        THEN (cs.attendance_count * 100.0 / cs.total_students)
                        ELSE 0 
                    END
                ) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date >= ? AND cs.status = 'completed'
            ''', (user_id, week_start))
            avg_attendance = cursor.fetchone()[0] or 0
            
            # Total students across all classes
            cursor.execute('''
                SELECT COUNT(DISTINCT sc.student_id) FROM student_courses sc
                JOIN classes c ON sc.course_code = c.course_code
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ?
            ''', (user_id,))
            total_students = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions,
                'ongoing_sessions': ongoing_sessions,
                'scheduled_sessions': total_sessions - completed_sessions - ongoing_sessions,
                'avg_attendance': round(avg_attendance, 1),
                'total_students': total_students,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            conn.close()
            log_error(f"Error getting live stats: {str(e)}", "REALTIME_SERVICE_ERROR")
            return {}
    
    def _get_live_sessions(self, user_id: int) -> List[Dict]:
        """Get live session data"""
        try:
            sessions = self.session_service.get_today_sessions()
            live_sessions = []
            
            for session in sessions:
                # Calculate progress based on time
                progress = self._calculate_session_progress(session)
                
                # Get real-time attendance count
                attendance_count = self._get_session_attendance_count(session['session_id'])
                
                live_sessions.append({
                    'session_id': session['session_id'],
                    'title': f"{session.get('course_code', '')} - {session.get('class_name', '')}",
                    'time': f"{session['start_time'][:5]} - {session['end_time'][:5]}",
                    'status': session['status'],
                    'progress': progress,
                    'attendance_count': attendance_count,
                    'total_students': session.get('total_students', 0),
                    'attendance_rate': round((attendance_count / session.get('total_students', 1)) * 100, 1) if session.get('total_students', 0) > 0 else 0
                })
            
            return live_sessions
            
        except Exception as e:
            log_error(f"Error getting live sessions: {str(e)}", "REALTIME_SERVICE_ERROR")
            return []
    
    def _get_live_activity_feed(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get live activity feed"""
        conn = self.db_service.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT activity_type, description, timestamp
                FROM activity_log
                WHERE user_id = ? AND user_type = 'instructor'
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (str(user_id), limit))
            
            activities = cursor.fetchall()
            activity_feed = []
            
            for activity in activities:
                activity_type = activity[0]
                description = activity[1]
                timestamp = datetime.fromisoformat(activity[2])
                time_ago = self._get_time_ago(timestamp)
                
                # Map activity types to icons and colors
                icon_map = {
                    'attendance_mark': {'icon': 'fa-check-circle', 'color': '#10b981'},
                    'session_start': {'icon': 'fa-play-circle', 'color': '#3b82f6'},
                    'session_end': {'icon': 'fa-stop-circle', 'color': '#ef4444'},
                    'login': {'icon': 'fa-sign-in-alt', 'color': '#8b5cf6'},
                    'camera_check': {'icon': 'fa-camera', 'color': '#f59e0b'}
                }
                
                icon_info = icon_map.get(activity_type, {'icon': 'fa-info-circle', 'color': '#6b7280'})
                
                activity_feed.append({
                    'type': activity_type,
                    'text': description,
                    'time_ago': time_ago,
                    'icon': icon_info['icon'],
                    'color': icon_info['color'],
                    'timestamp': timestamp.isoformat()
                })
            
            conn.close()
            return activity_feed
            
        except Exception as e:
            conn.close()
            log_error(f"Error getting activity feed: {str(e)}", "REALTIME_SERVICE_ERROR")
            return []
    
    def _get_live_attendance_summary(self, user_id: int) -> Dict:
        """Get live attendance summary"""
        conn = self.db_service.get_connection()
        cursor = conn.cursor()
        
        try:
            today = datetime.now()
            week_start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            month_start = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            semester_start = (today - timedelta(days=120)).strftime('%Y-%m-%d')
            
            # Weekly attendance rate
            cursor.execute('''
                SELECT AVG(
                    CASE 
                        WHEN cs.total_students > 0 
                        THEN (cs.attendance_count * 100.0 / cs.total_students)
                        ELSE 0 
                    END
                ) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date >= ? AND cs.status = 'completed'
            ''', (user_id, week_start))
            week_rate = cursor.fetchone()[0] or 0
            
            # Monthly attendance rate
            cursor.execute('''
                SELECT AVG(
                    CASE 
                        WHEN cs.total_students > 0 
                        THEN (cs.attendance_count * 100.0 / cs.total_students)
                        ELSE 0 
                    END
                ) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date >= ? AND cs.status = 'completed'
            ''', (user_id, month_start))
            month_rate = cursor.fetchone()[0] or 0
            
            # Semester attendance rate
            cursor.execute('''
                SELECT AVG(
                    CASE 
                        WHEN cs.total_students > 0 
                        THEN (cs.attendance_count * 100.0 / cs.total_students)
                        ELSE 0 
                    END
                ) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date >= ? AND cs.status = 'completed'
            ''', (user_id, semester_start))
            semester_rate = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'week': round(week_rate, 1),
                'month': round(month_rate, 1),
                'semester': round(semester_rate, 1),
                'trend': self._calculate_attendance_trend(user_id)
            }
            
        except Exception as e:
            conn.close()
            log_error(f"Error getting attendance summary: {str(e)}", "REALTIME_SERVICE_ERROR")
            return {'week': 0, 'month': 0, 'semester': 0, 'trend': 'stable'}
    
    def _get_live_camera_status(self, user_id: int) -> Dict:
        """Get live camera status"""
        # This would integrate with actual camera system
        # For now, return simulated data
        return {
            'online': True,
            'resolution': '1080p',
            'fps': 30,
            'light_quality': 'Good',
            'recognition_rate': 92.5,
            'last_check': datetime.now().isoformat(),
            'devices_connected': 1
        }
    
    def _get_active_session_data(self, user_id: int) -> Optional[Dict]:
        """Get current active session data"""
        try:
            active_session = self.session_service.get_current_active_session()
            if not active_session:
                return None
            
            session_id = active_session['session_id']
            attendance_data = self.attendance_service.get_session_attendance(session_id)
            
            if attendance_data['success']:
                return {
                    'session_id': session_id,
                    'class_name': active_session.get('class_name', ''),
                    'course_code': active_session.get('course_code', ''),
                    'start_time': active_session['start_time'],
                    'end_time': active_session['end_time'],
                    'status': active_session['status'],
                    'attendance': attendance_data['statistics'],
                    'duration': self._get_session_duration(active_session)
                }
            
            return None
            
        except Exception as e:
            log_error(f"Error getting active session data: {str(e)}", "REALTIME_SERVICE_ERROR")
            return None
    
    def broadcast_attendance_update(self, session_id: int, student_id: str, status: str):
        """Broadcast attendance update to connected clients"""
        try:
            socketio = current_app.socketio
            
            # Get updated session data
            attendance_data = self.attendance_service.get_session_attendance(session_id)
            
            if attendance_data['success']:
                update_data = {
                    'type': 'attendance_update',
                    'session_id': session_id,
                    'student_id': student_id,
                    'status': status,
                    'statistics': attendance_data['statistics'],
                    'timestamp': datetime.now().isoformat()
                }
                
                # Broadcast to session room
                socketio.emit('attendance_updated', update_data, room=f'session_{session_id}')
                
                # Broadcast to dashboard
                socketio.emit('dashboard_update', {
                    'type': 'attendance_counter',
                    'data': update_data
                })
                
        except Exception as e:
            log_error(f"Error broadcasting attendance update: {str(e)}", "REALTIME_SERVICE_ERROR")
    
    def broadcast_session_status_change(self, session_id: int, old_status: str, new_status: str):
        """Broadcast session status change"""
        try:
            socketio = current_app.socketio
            
            update_data = {
                'type': 'session_status_change',
                'session_id': session_id,
                'old_status': old_status,
                'new_status': new_status,
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast to all connected clients
            socketio.emit('session_status_changed', update_data)
            
        except Exception as e:
            log_error(f"Error broadcasting session status change: {str(e)}", "REALTIME_SERVICE_ERROR")
    
    def broadcast_dashboard_refresh(self, user_id: int):
        """Broadcast dashboard refresh signal"""
        try:
            socketio = current_app.socketio
            dashboard_data = self.get_live_dashboard_data(user_id)
            
            if dashboard_data['success']:
                socketio.emit('dashboard_refresh', dashboard_data['data'], room=f'user_{user_id}')
                
        except Exception as e:
            log_error(f"Error broadcasting dashboard refresh: {str(e)}", "REALTIME_SERVICE_ERROR")
    
    def _calculate_session_progress(self, session: Dict) -> int:
        """Calculate session progress percentage"""
        try:
            now = datetime.now()
            start_time = datetime.strptime(f"{session['date']} {session['start_time']}", '%Y-%m-%d %H:%M:%S')
            end_time = datetime.strptime(f"{session['date']} {session['end_time']}", '%Y-%m-%d %H:%M:%S')
            
            if now < start_time:
                return 0
            elif now > end_time:
                return 100
            else:
                total_duration = (end_time - start_time).total_seconds()
                elapsed = (now - start_time).total_seconds()
                return min(100, max(0, int((elapsed / total_duration) * 100)))
                
        except Exception:
            return 0
    
    def _get_session_attendance_count(self, session_id: int) -> int:
        """Get real-time attendance count for a session"""
        conn = self.db_service.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT COUNT(*) FROM attendance
                WHERE session_id = ? AND status IN ('Present', 'Late')
            ''', (session_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
            
        except Exception:
            if conn:
                conn.close()
            return 0
    
    def _get_time_ago(self, timestamp: datetime) -> str:
        """Get human-readable time ago string"""
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
    
    def _calculate_attendance_trend(self, user_id: int) -> str:
        """Calculate attendance trend (improving, declining, stable)"""
        conn = self.db_service.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get last 2 weeks data
            two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
            one_week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            # First week average
            cursor.execute('''
                SELECT AVG(
                    CASE 
                        WHEN cs.total_students > 0 
                        THEN (cs.attendance_count * 100.0 / cs.total_students)
                        ELSE 0 
                    END
                ) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date >= ? AND cs.date < ? AND cs.status = 'completed'
            ''', (user_id, two_weeks_ago, one_week_ago))
            first_week = cursor.fetchone()[0] or 0
            
            # Second week average
            cursor.execute('''
                SELECT AVG(
                    CASE 
                        WHEN cs.total_students > 0 
                        THEN (cs.attendance_count * 100.0 / cs.total_students)
                        ELSE 0 
                    END
                ) FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE ci.instructor_id = ? AND cs.date >= ? AND cs.status = 'completed'
            ''', (user_id, one_week_ago))
            second_week = cursor.fetchone()[0] or 0
            
            conn.close()
            
            if abs(second_week - first_week) < 2:
                return 'stable'
            elif second_week > first_week:
                return 'improving'
            else:
                return 'declining'
                
        except Exception:
            if conn:
                conn.close()
            return 'stable'
    
    def _get_session_duration(self, session: Dict) -> str:
        """Get formatted session duration"""
        try:
            start_time = datetime.strptime(session['start_time'], '%H:%M:%S')
            now = datetime.now()
            current_time = now.time()
            
            # Convert to datetime for calculation
            session_start = datetime.combine(now.date(), start_time.time())
            session_current = datetime.combine(now.date(), current_time)
            
            if session_current < session_start:
                return "Not started"
            
            duration = session_current - session_start
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60
            
            if hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
                
        except Exception:
            return "Unknown"


# WebSocket Event Handlers
def setup_socketio_events(socketio):
    """Setup SocketIO event handlers"""
    
    @socketio.on('join_dashboard')
    def handle_join_dashboard(data):
        """Handle client joining dashboard room"""
        user_id = data.get('user_id')
        if user_id:
            join_room(f'user_{user_id}')
            emit('joined_dashboard', {'status': 'success'})
    
    @socketio.on('leave_dashboard')
    def handle_leave_dashboard(data):
        """Handle client leaving dashboard room"""
        user_id = data.get('user_id')
        if user_id:
            leave_room(f'user_{user_id}')
    
    @socketio.on('join_session')
    def handle_join_session(data):
        """Handle client joining session room for attendance updates"""
        session_id = data.get('session_id')
        if session_id:
            join_room(f'session_{session_id}')
            emit('joined_session', {'session_id': session_id, 'status': 'success'})
    
    @socketio.on('leave_session')
    def handle_leave_session(data):
        """Handle client leaving session room"""
        session_id = data.get('session_id')
        if session_id:
            leave_room(f'session_{session_id}')
    
    @socketio.on('request_dashboard_update')
    def handle_dashboard_update_request(data):
        """Handle manual dashboard update request"""
        user_id = data.get('user_id')
        if user_id:
            service = RealTimeDashboardService()
            service.broadcast_dashboard_refresh(user_id)
    
    @socketio.on('ping')
    def handle_ping():
        """Handle ping for connection keepalive"""
        emit('pong', {'timestamp': datetime.now().isoformat()})