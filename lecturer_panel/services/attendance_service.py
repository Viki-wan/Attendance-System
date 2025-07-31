"""
Attendance Service
Handles all attendance-related operations including marking, validation, and session management
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from lecturer_panel.utils.helpers import get_database_path, log_error
from flask import current_app


class AttendanceService:
    """Service class for handling attendance operations"""
    
    def __init__(self):
        self.db_path = get_database_path()
    
    def mark_attendance(self, student_id: str, session_id: int, status: str = 'Present',
                       marked_by: int = None, method: str = 'manual', 
                       confidence_score: float = None, notes: str = None) -> Dict:
        """
        Mark attendance for a student in a session
        
        Args:
            student_id: Student ID
            session_id: Session ID
            status: Attendance status ('Present', 'Absent', 'Late', 'Excused')
            marked_by: Instructor ID who marked the attendance
            method: Method used ('manual', 'face_recognition', 'bulk_manual')
            confidence_score: Face recognition confidence score (if applicable)
            notes: Additional notes
            
        Returns:
            Dict with success status and message
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Validate inputs
            if status not in ['Present', 'Absent', 'Late', 'Excused']:
                return {'success': False, 'message': 'Invalid attendance status'}
            
            # Check if student exists
            cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
            if not cursor.fetchone():
                return {'success': False, 'message': 'Student not found'}
            
            # Check if session exists
            cursor.execute('SELECT session_id, status FROM class_sessions WHERE session_id = ?', (session_id,))
            session_result = cursor.fetchone()
            if not session_result:
                return {'success': False, 'message': 'Session not found'}
            
            session_status = session_result[1]
            if session_status not in ['ongoing', 'scheduled']:
                return {'success': False, 'message': 'Cannot mark attendance for completed or cancelled session'}
            
            # Check if student is enrolled in the class
            cursor.execute('''
                SELECT sc.student_id FROM student_courses sc
                JOIN classes c ON sc.course_code = c.course_code
                JOIN class_sessions cs ON c.class_id = cs.class_id
                WHERE sc.student_id = ? AND cs.session_id = ?
            ''', (student_id, session_id))
            
            if not cursor.fetchone():
                return {'success': False, 'message': 'Student not enrolled in this class'}
            
            # Insert or update attendance record
            cursor.execute('''
                INSERT OR REPLACE INTO attendance 
                (student_id, session_id, status, marked_by, method, confidence_score, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, session_id, status, marked_by, method, confidence_score, notes, datetime.now()))
            
            conn.commit()
            conn.close()
            
            # Log the attendance marking
            self._log_attendance_action(student_id, session_id, status, marked_by, method)
            
            # --- SocketIO emit for real-time dashboard update ---
            try:
                conn2 = sqlite3.connect(self.db_path)
                cursor2 = conn2.cursor()
                cursor2.execute('''
                    SELECT attendance_count, total_students FROM class_sessions WHERE session_id = ?
                ''', (session_id,))
                row = cursor2.fetchone()
                attendance_count = row[0] if row else 0
                total_students = row[1] if row else 0
                conn2.close()
                current_app.socketio.emit('attendance_update', {
                    'session_id': session_id,
                    'attendance_count': attendance_count,
                    'total_students': total_students
                }, broadcast=True)
            except Exception as e:
                log_error(f"SocketIO emit error: {str(e)}", "SOCKETIO_EMIT_ERROR")
            # --- End SocketIO emit ---
            
            return {
                'success': True,
                'message': f'Attendance marked as {status} for student {student_id}'
            }
            
        except Exception as e:
            log_error(f"Error marking attendance: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to mark attendance'}
    
    def get_session_attendance(self, session_id: int) -> Dict:
        """
        Get attendance records for a specific session
        
        Args:
            session_id: Session ID
            
        Returns:
            Dict with attendance data and statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get session details
            cursor.execute('''
                SELECT cs.*, c.class_name, co.course_name, co.course_code
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN courses co ON c.course_code = co.course_code
                WHERE cs.session_id = ?
            ''', (session_id,))
            
            session_data = cursor.fetchone()
            if not session_data:
                return {'success': False, 'message': 'Session not found'}
            
            # Get attendance records with student details
            cursor.execute('''
                SELECT s.student_id, s.fname, s.lname, s.email,
                       COALESCE(a.status, 'Absent') as status,
                       a.timestamp, a.confidence_score, a.method, a.notes
                FROM students s
                LEFT JOIN attendance a ON s.student_id = a.student_id AND a.session_id = ?
                JOIN student_courses sc ON s.student_id = sc.student_id
                JOIN classes c ON sc.course_code = c.course_code
                WHERE c.class_id = ?
                ORDER BY s.lname, s.fname
            ''', (session_id, session_data[1]))  # class_id is at index 1
            
            attendance_records = cursor.fetchall()
            
            # Format attendance data
            attendance_list = []
            for record in attendance_records:
                attendance_list.append({
                    'student_id': record[0],
                    'name': f"{record[1]} {record[2]}",
                    'email': record[3],
                    'status': record[4],
                    'timestamp': record[5],
                    'confidence_score': record[6],
                    'method': record[7],
                    'notes': record[8]
                })
            
            # Calculate statistics
            total_students = len(attendance_records)
            present_count = sum(1 for record in attendance_records if record[4] == 'Present')
            late_count = sum(1 for record in attendance_records if record[4] == 'Late')
            absent_count = sum(1 for record in attendance_records if record[4] == 'Absent')
            excused_count = sum(1 for record in attendance_records if record[4] == 'Excused')
            
            statistics = {
                'total_students': total_students,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'attendance_rate': round((present_count / total_students * 100) if total_students > 0 else 0, 1),
                'participation_rate': round(((present_count + late_count) / total_students * 100) if total_students > 0 else 0, 1)
            }
            
            conn.close()
            
            return {
                'success': True,
                'session_info': {
                    'session_id': session_data[0],
                    'class_id': session_data[1],
                    'class_name': session_data[9],
                    'course_name': session_data[10],
                    'course_code': session_data[11],
                    'date': session_data[2],
                    'start_time': session_data[3],
                    'end_time': session_data[4],
                    'status': session_data[5]
                },
                'attendance': attendance_list,
                'statistics': statistics
            }
            
        except Exception as e:
            log_error(f"Error getting session attendance: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to get session attendance'}
    
    def update_session_count(self, session_id: int) -> bool:
        """
        Update the attendance count for a session
        
        Args:
            session_id: Session ID
            
        Returns:
            bool: Success status
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count present and late students
            cursor.execute('''
                SELECT COUNT(*) FROM attendance
                WHERE session_id = ? AND status IN ('Present', 'Late')
            ''', (session_id,))
            
            attendance_count = cursor.fetchone()[0]
            
            # Update session record
            cursor.execute('''
                UPDATE class_sessions
                SET attendance_count = ?
                WHERE session_id = ?
            ''', (attendance_count, session_id))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            log_error(f"Error updating session count: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return False
    
    def get_student_attendance_history(self, student_id: str, course_code: str = None,
                                     start_date: str = None, end_date: str = None) -> Dict:
        """
        Get attendance history for a specific student
        
        Args:
            student_id: Student ID
            course_code: Optional course filter
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            Dict with attendance history and statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query with optional filters
            query = '''
                SELECT cs.date, cs.start_time, cs.end_time, c.class_name, co.course_name, co.course_code,
                       a.status, a.timestamp, a.method, a.confidence_score
                FROM attendance a
                JOIN class_sessions cs ON a.session_id = cs.session_id
                JOIN classes c ON cs.class_id = c.class_id
                JOIN courses co ON c.course_code = co.course_code
                WHERE a.student_id = ?
            '''
            
            params = [student_id]
            
            if course_code:
                query += ' AND co.course_code = ?'
                params.append(course_code)
            
            if start_date:
                query += ' AND cs.date >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND cs.date <= ?'
                params.append(end_date)
            
            query += ' ORDER BY cs.date DESC, cs.start_time DESC'
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            # Format attendance history
            attendance_history = []
            for record in records:
                attendance_history.append({
                    'date': record[0],
                    'start_time': record[1],
                    'end_time': record[2],
                    'class_name': record[3],
                    'course_name': record[4],
                    'course_code': record[5],
                    'status': record[6],
                    'timestamp': record[7],
                    'method': record[8],
                    'confidence_score': record[9]
                })
            
            # Calculate statistics
            total_sessions = len(records)
            present_count = sum(1 for record in records if record[6] == 'Present')
            late_count = sum(1 for record in records if record[6] == 'Late')
            absent_count = sum(1 for record in records if record[6] == 'Absent')
            excused_count = sum(1 for record in records if record[6] == 'Excused')
            
            statistics = {
                'total_sessions': total_sessions,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'excused': excused_count,
                'attendance_rate': round((present_count / total_sessions * 100) if total_sessions > 0 else 0, 1),
                'participation_rate': round(((present_count + late_count) / total_sessions * 100) if total_sessions > 0 else 0, 1)
            }
            
            conn.close()
            
            return {
                'success': True,
                'student_id': student_id,
                'attendance_history': attendance_history,
                'statistics': statistics
            }
            
        except Exception as e:
            log_error(f"Error getting student attendance history: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to get attendance history'}
    
    def get_class_attendance_summary(self, class_id: str, start_date: str = None, 
                                   end_date: str = None) -> Dict:
        """
        Get attendance summary for a class
        
        Args:
            class_id: Class ID
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            Dict with class attendance summary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query with optional date filters
            query = '''
                SELECT cs.session_id, cs.date, cs.start_time, cs.end_time,
                       cs.attendance_count, cs.total_students, cs.status
                FROM class_sessions cs
                WHERE cs.class_id = ?
            '''
            
            params = [class_id]
            
            if start_date:
                query += ' AND cs.date >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND cs.date <= ?'
                params.append(end_date)
            
            query += ' ORDER BY cs.date DESC, cs.start_time DESC'
            
            cursor.execute(query, params)
            sessions = cursor.fetchall()
            
            # Format session data
            session_list = []
            total_sessions = 0
            total_attendance = 0
            
            for session in sessions:
                session_data = {
                    'session_id': session[0],
                    'date': session[1],
                    'start_time': session[2],
                    'end_time': session[3],
                    'attendance_count': session[4] or 0,
                    'total_students': session[5] or 0,
                    'status': session[6],
                    'attendance_rate': round((session[4] / session[5] * 100) if session[5] > 0 else 0, 1)
                }
                session_list.append(session_data)
                
                if session[6] == 'completed':
                    total_sessions += 1
                    total_attendance += session[4] or 0
            
            # Calculate overall statistics
            avg_attendance = round((total_attendance / total_sessions) if total_sessions > 0 else 0, 1)
            
            conn.close()
            
            return {
                'success': True,
                'class_id': class_id,
                'sessions': session_list,
                'summary': {
                    'total_sessions': len(sessions),
                    'completed_sessions': total_sessions,
                    'average_attendance': avg_attendance,
                    'total_attendance': total_attendance
                }
            }
            
        except Exception as e:
            log_error(f"Error getting class attendance summary: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to get class attendance summary'}
    
    def validate_attendance_session(self, session_id: int, instructor_id: int) -> Dict:
        """
        Validate if an instructor can manage attendance for a session
        
        Args:
            session_id: Session ID
            instructor_id: Instructor ID
            
        Returns:
            Dict with validation result
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if session exists and instructor has access
            cursor.execute('''
                SELECT cs.session_id, cs.status, cs.class_id
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN class_instructors ci ON c.class_id = ci.class_id
                WHERE cs.session_id = ? AND ci.instructor_id = ?
            ''', (session_id, instructor_id))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return {
                    'success': False,
                    'message': 'Session not found or access denied'
                }
            
            session_status = result[1]
            if session_status not in ['ongoing', 'scheduled']:
                return {
                    'success': False,
                    'message': f'Cannot modify attendance for {session_status} session'
                }
            
            return {
                'success': True,
                'session_id': result[0],
                'status': result[1],
                'class_id': result[2]
            }
            
        except Exception as e:
            log_error(f"Error validating attendance session: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to validate session'}
    
    def _log_attendance_action(self, student_id: str, session_id: int, status: str, 
                             marked_by: int, method: str):
        """
        Log attendance marking action
        
        Args:
            student_id: Student ID
            session_id: Session ID
            status: Attendance status
            marked_by: Instructor ID
            method: Marking method
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            description = f"Marked {student_id} as {status} in session {session_id} using {method}"
            
            cursor.execute('''
                INSERT INTO activity_log (user_id, user_type, activity_type, description)
                VALUES (?, 'instructor', 'attendance_mark', ?)
            ''', (str(marked_by), description))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            log_error(f"Error logging attendance action: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
    
    def get_attendance_trends(self, class_id: str = None, course_code: str = None,
                            days: int = 30) -> Dict:
        """
        Get attendance trends for analysis
        
        Args:
            class_id: Optional class filter
            course_code: Optional course filter
            days: Number of days to analyze
            
        Returns:
            Dict with trend data
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Calculate start date
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Build query
            query = '''
                SELECT cs.date, 
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present,
                       SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late,
                       SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent,
                       COUNT(*) as total
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                LEFT JOIN attendance a ON cs.session_id = a.session_id
                WHERE cs.date >= ? AND cs.status = 'completed'
            '''
            
            params = [start_date]
            
            if class_id:
                query += ' AND c.class_id = ?'
                params.append(class_id)
            
            if course_code:
                query += ' AND c.course_code = ?'
                params.append(course_code)
            
            query += ' GROUP BY cs.date ORDER BY cs.date'
            
            cursor.execute(query, params)
            trends = cursor.fetchall()
            
            # Format trend data
            trend_data = []
            for trend in trends:
                trend_data.append({
                    'date': trend[0],
                    'present': trend[1],
                    'late': trend[2],
                    'absent': trend[3],
                    'total': trend[4],
                    'attendance_rate': round((trend[1] / trend[4] * 100) if trend[4] > 0 else 0, 1)
                })
            
            conn.close()
            
            return {
                'success': True,
                'trends': trend_data,
                'period': {
                    'start_date': start_date,
                    'end_date': datetime.now().strftime('%Y-%m-%d'),
                    'days': days
                }
            }
            
        except Exception as e:
            log_error(f"Error getting attendance trends: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to get attendance trends'}

    def bulk_mark_attendance(self, session_id: int, student_ids: list, status: str, marked_by: int, method: str = 'bulk_manual') -> dict:
        """
        Mark attendance for multiple students in bulk.
        Returns a summary of successes and failures.
        """
        success_count = 0
        failed_count = 0
        for student_id in student_ids:
            result = self.mark_attendance(student_id, session_id, status, marked_by, method)
            if result['success']:
                success_count += 1
            else:
                failed_count += 1
        return {
            'success': True,
            'message': f'Bulk attendance completed: {success_count} successful, {failed_count} failed',
            'success_count': success_count,
            'failed_count': failed_count
        }

    def start_session(self, class_id: str, instructor_id: int) -> dict:
        """
        Create a new attendance session for a class and instructor.
        Returns session info and success status.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            start_time = datetime.now().strftime('%H:%M')
            end_time = (datetime.now() + timedelta(minutes=90)).strftime('%H:%M')
            # Insert new session
            cursor.execute('''
                INSERT INTO class_sessions (class_id, date, start_time, end_time, status, created_by)
                VALUES (?, ?, ?, ?, 'ongoing', ?)
            ''', (class_id, today, start_time, end_time, instructor_id))
            session_id = cursor.lastrowid
            # Get total students for this class
            cursor.execute('''
                SELECT COUNT(*) FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                JOIN classes c ON sc.course_code = c.course_code
                WHERE c.class_id = ?
            ''', (class_id,))
            total_students = cursor.fetchone()[0]
            # Update session with total students
            cursor.execute('''
                UPDATE class_sessions SET total_students = ? WHERE session_id = ?
            ''', (total_students, session_id))
            conn.commit()
            conn.close()
            return {
                'success': True,
                'session_id': session_id,
                'message': 'Session started successfully',
                'total_students': total_students
            }
        except Exception as e:
            log_error(f"Error starting session: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to start session'}

    def end_session(self, session_id: int, instructor_id: int) -> dict:
        """
        Mark a session as completed and update end time.
        Returns success status and message.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            end_time = datetime.now().strftime('%H:%M')
            cursor.execute('''
                UPDATE class_sessions 
                SET status = 'completed', end_time = ? 
                WHERE session_id = ?
            ''', (end_time, session_id))
            conn.commit()
            conn.close()
            # --- SocketIO emit for real-time dashboard update ---
            try:
                current_app.socketio.emit('session_status_update', {
                    'session_id': session_id,
                    'status': 'completed'
                }, broadcast=True)
            except Exception as e:
                log_error(f"SocketIO emit error: {str(e)}", "SOCKETIO_EMIT_ERROR")
            # --- End SocketIO emit ---
            return {
                'success': True,
                'message': 'Session ended successfully'
            }
        except Exception as e:
            log_error(f"Error ending session: {str(e)}", "ATTENDANCE_SERVICE_ERROR")
            return {'success': False, 'message': 'Failed to end session'}