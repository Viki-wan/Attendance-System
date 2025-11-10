"""
Session Service - Business Logic for Session Management
Handles session CRUD, eligibility checks, conflict detection, and lifecycle management
"""

from datetime import datetime, timedelta, time as dt_time
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_, or_, func, text
from sqlalchemy.orm import joinedload, selectinload
from flask import current_app

from app import db
from app.models.session import ClassSession
from app.models.class_model import Class
from app.models.student import Student
from app.models.attendance import Attendance
from app.models.user import Instructor
from app.models.timetable import Timetable
from app.models.settings import Settings
from app.models.session_dismissal import SessionDismissal
from app.models.course import StudentCourse
from app.services.notification_service import NotificationService


class SessionService:
    """Manages all session-related operations"""
    
    def __init__(self):
        self.notification_service = NotificationService()
    
    @staticmethod
    def get_current_semester():
        """
        Determine current semester based on date
        Semester 1: September - December
        Semester 2: January - April
        Holiday: May - August (defaults to Semester 2 for filtering)
        
        Returns:
            str: Current semester ('1' or '2')
        """
        now = datetime.now()
        month = now.month
        
        if month in [9, 10, 11, 12]:
            return '1'  # Semester 1
        elif month in [1, 2, 3, 4]:
            return '2'  # Semester 2
        else:
            # May-August is holiday period, default to last active semester
            return '2'

    @staticmethod
    def is_in_semester(date: Optional[datetime] = None) -> bool:
        """Check if current date is within an active semester (not holidays)"""
        if date is None:
            date = datetime.now()
        
        month = date.month
        # Semester 1: Sep-Dec (9-12), Semester 2: Jan-Apr (1-4)
        return (1 <= month <= 4) or (9 <= month <= 12)

    def update_missed_sessions(self) -> int:
        """
        Automatically mark sessions as 'missed' if they weren't started during allocated time
        Should be run periodically (e.g., every hour via cron job)
        
        Returns:
            Number of sessions marked as missed
        """
        current_time = datetime.now()
        time_window = self._get_setting('session_start_window_minutes', 15)
        
        # Find scheduled sessions where the start window has passed
        missed_sessions = ClassSession.query.filter(
            ClassSession.status == 'scheduled',
            ClassSession.date < current_time.date()
        ).all()
        
        # Also check today's sessions where time has passed
        today_missed = ClassSession.query.filter(
            ClassSession.status == 'scheduled',
            ClassSession.date == current_time.date()
        ).all()
        
        count = 0
        for session in missed_sessions + today_missed:
            session_datetime = datetime.strptime(
                f"{session.date} {session.start_time}",
                "%Y-%m-%d %H:%M:%S"
            )
            latest_start = session_datetime + timedelta(minutes=time_window)
            
            if current_time > latest_start:
                session.status = 'missed'
                session.session_notes = (session.session_notes or '') + \
                    f"\n[AUTO] Session marked as missed on {current_time.strftime('%Y-%m-%d %H:%M')}"
                count += 1
                
                # Log activity
                self._log_activity(
                    session.created_by,
                    'session_auto_missed',
                    f'Session {session.session_id} automatically marked as missed'
                )
                
                # Notify instructor
                self.notification_service.notify_session_missed(session.session_id)
        
        if count > 0:
            try:
                db.session.commit()
                current_app.logger.info(f"Marked {count} sessions as missed")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating missed sessions: {str(e)}")
                return 0
        
        return count
    
    
    # ==================== SESSION RETRIEVAL ====================
    
    def get_instructor_sessions(
        self,
        instructor_id: str,
        filters: Optional[Dict] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Tuple[List[ClassSession], int]:
        """
        Get all sessions for an instructor with filtering and pagination
        Now includes automatic semester filtering
        """
        # Auto-update missed sessions before retrieval
        self.update_missed_sessions()
        
        query = ClassSession.query.join(
            Class, ClassSession.class_id == Class.class_id
        ).join(
            db.Table('class_instructors'),
            and_(
                db.Table('class_instructors').c.class_id == Class.class_id,
                db.Table('class_instructors').c.instructor_id == instructor_id
            )
        ).options(
            joinedload(ClassSession.class_).joinedload(Class.course)
        )
        
        # Apply semester filter based on current date
        current_semester = SessionService.get_current_semester()

        query = query.filter(Class.semester == current_semester)
        
        # Apply filters
        if filters:
            if filters.get('date_from'):
                query = query.filter(ClassSession.date >= filters['date_from'])
            
            if filters.get('date_to'):
                query = query.filter(ClassSession.date <= filters['date_to'])
            
            if filters.get('status'):
                query = query.filter(ClassSession.status == filters['status'])
            
            if filters.get('class_id'):
                query = query.filter(ClassSession.class_id == filters['class_id'])
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        sessions = query.order_by(
            ClassSession.date.desc(),
            ClassSession.start_time.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        return sessions.items, total_count
    
    def get_instructor_classes_for_current_semester(self, instructor_id: str) -> List[Dict]:
        """
        Get instructor's classes filtered by current semester
        
        Returns:
            List of class dictionaries with class_id, class_name, course_name
        """
        current_semester = SessionService.get_current_semester()

        
        classes = db.session.execute(
            text("""
                SELECT DISTINCT c.class_id, c.class_name, co.course_name, c.semester
                FROM classes c
                JOIN class_instructors ci ON c.class_id = ci.class_id
                JOIN courses co ON c.course_code = co.course_code
                WHERE ci.instructor_id = :instructor_id
                AND c.is_active = 1
                AND c.semester = :semester
                ORDER BY c.class_name
            """),
            {'instructor_id': instructor_id, 'semester': current_semester}
        ).fetchall()
        
        return [
            {
                'class_id': row[0],
                'class_name': row[1],
                'course_name': row[2],
                'semester': row[3]
            }
            for row in classes
        ]
    
    def get_session_by_id(self, session_id: int) -> Optional[ClassSession]:
        """Get session with all related data"""
        return ClassSession.query.options(
            joinedload(ClassSession.class_).joinedload(Class.course),
            joinedload(ClassSession.instructor)
        ).get(session_id)
    
    def get_upcoming_sessions(
        self,
        instructor_id: str,
        days_ahead: int = 7
    ) -> List[ClassSession]:
        """Get instructor's upcoming sessions with auto-update"""
        # Update missed sessions first
        self.update_missed_sessions()
        
        today = datetime.now().date()
        end_date = today + timedelta(days=days_ahead)
        
        # Don't filter by status - get all upcoming sessions
        sessions, _ = self.get_instructor_sessions(
            instructor_id,
            filters={
                'date_from': today.isoformat(),
                'date_to': end_date.isoformat()
                # Remove the status filter to show all sessions
            },
            per_page=100
        )
        
        return sessions
        
    def get_todays_sessions(self, instructor_id: str) -> List[ClassSession]:
        """Get today's sessions for instructor"""
        # Update missed sessions first
        self.update_missed_sessions()
        
        today = datetime.now().date().isoformat()
        
        sessions, _ = self.get_instructor_sessions(
            instructor_id,
            filters={'date_from': today, 'date_to': today},
            per_page=50
        )
        
        return sessions
    
    # ==================== SESSION CREATION ====================
    
    def create_session(
        self,
        class_id: str,
        date: str,
        start_time: str,
        end_time: str,
        instructor_id: str,
        notes: Optional[str] = None
    ) -> Tuple[Optional[ClassSession], Optional[str]]:
        """
        Create a new session with conflict detection
        
        Returns:
            Tuple of (session, error_message)
        """
        # Validate class ownership
        if not self._instructor_owns_class(instructor_id, class_id):
            return None, "You don't have permission to create sessions for this class"
        
        # Check for conflicts
        has_conflict, conflict_msg = self.check_session_conflicts(
            class_id, date, start_time, end_time, instructor_id
        )
        
        if has_conflict:
            return None, conflict_msg
        
        # Get expected student count
        student_count = self._get_class_student_count(class_id)
        
        # Create session
        session = ClassSession(
            class_id=class_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            status='scheduled',
            created_by=instructor_id,
            total_students=student_count,
            session_notes=notes
        )
        
        try:
            db.session.add(session)
            db.session.commit()
            
            # Log activity
            self._log_activity(
                instructor_id,
                'session_created',
                f'Created session for class {class_id} on {date}'
            )
            
            return session, None
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating session: {str(e)}")
            return None, "Failed to create session"
    
    def create_sessions_from_timetable(
        self,
        start_date: datetime,
        end_date: datetime,
        class_id: Optional[str] = None,
        instructor_id: Optional[str] = None
    ) -> Tuple[int, List[str]]:
        """
        Auto-generate sessions from timetable with semester awareness
        
        Args:
            start_date: Start date for generation
            end_date: End date for generation
            class_id: Optional specific class (None = all classes)
            instructor_id: Optional filter by instructor
            
        Returns:
            Tuple of (created_count, errors_list)
        """
        created_count = 0
        errors = []
        
        # Get current semester
        current_semester = SessionService.get_current_semester()

        
        # Get timetable entries
        query = Timetable.query.filter(Timetable.is_active == True)
        if class_id:
            query = query.filter(Timetable.class_id == class_id)
        
        # Join with classes to filter by semester
        query = query.join(Class, Timetable.class_id == Class.class_id)\
                     .filter(Class.semester == current_semester)
        
        timetable_entries = query.all()
        
        # Check holidays
        holidays = self._get_holidays(start_date, end_date)
        
        # Generate sessions for each day in range
        current_date = start_date
        while current_date <= end_date:
            # Skip holidays and non-semester periods
            if current_date.date() in holidays or not self.is_in_semester(current_date):
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()  # Monday=0, Sunday=6
            # Convert to schema format (Sunday=0)
            schema_day = 0 if day_of_week == 6 else day_of_week + 1
            
            # Find matching timetable entries
            for entry in timetable_entries:
                if entry.day_of_week != schema_day:
                    continue
                
                # Check if session already exists
                existing = ClassSession.query.filter_by(
                    class_id=entry.class_id,
                    date=current_date.date().isoformat(),
                    start_time=entry.start_time
                ).first()
                
                if existing:
                    continue
                
                # Get instructor for this class
                instructor = self._get_class_instructor(entry.class_id)
                if not instructor:
                    errors.append(f"No instructor assigned to {entry.class_id}")
                    continue
                
                # Filter by instructor if specified
                if instructor_id and instructor.instructor_id != instructor_id:
                    continue
                
                # Check conflicts
                has_conflict, _ = self.check_session_conflicts(
                    entry.class_id,
                    current_date.date().isoformat(),
                    entry.start_time,
                    entry.end_time,
                    instructor.instructor_id
                )
                
                if has_conflict:
                    continue
                
                # Create session
                session, error = self.create_session(
                    class_id=entry.class_id,
                    date=current_date.date().isoformat(),
                    start_time=entry.start_time,
                    end_time=entry.end_time,
                    instructor_id=instructor.instructor_id,
                    notes="Auto-generated from timetable"
                )
                
                if session:
                    created_count += 1
                else:
                    errors.append(error)
            
            current_date += timedelta(days=1)
        
        return created_count, errors
    
    # ==================== SESSION ELIGIBILITY ====================
    
    def can_start_session(
        self,
        session_id: int,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """
        Check if session can be started now
        
        Returns:
            Tuple of (can_start, reason)
        """
        session = self.get_session_by_id(session_id)
        if not session:
            return False, "Session not found"
        
        if session.status == 'ongoing':
            return False, "Session is already ongoing"
        
        if session.status in ['completed', 'cancelled', 'dismissed']:
            return False, f"Session is already {session.status}"
        
        # Get time window setting (default ±15 minutes)
        time_window = self._get_setting('session_start_window_minutes', 15)
        
        if current_time is None:
            current_time = datetime.now()
        
        # Parse session date and time
        session_datetime = datetime.strptime(
            f"{session.date} {session.start_time}",
            "%Y-%m-%d %H:%M:%S"
        )
        
        # Calculate time window
        earliest_start = session_datetime - timedelta(minutes=time_window)
        latest_start = session_datetime + timedelta(minutes=time_window)
        
        if current_time < earliest_start:
            minutes_until = int((earliest_start - current_time).total_seconds() / 60)
            return False, f"Too early. Session can be started in {minutes_until} minutes"
        
        if current_time > latest_start:
            return False, "Session start window has passed. Please reschedule."
        
        return True, "Session can be started"
    
    def get_session_eligibility_status(self, session_id: int) -> Dict:
        """Get detailed eligibility status for UI"""
        can_start, reason = self.can_start_session(session_id)
        session = self.get_session_by_id(session_id)
        
        return {
            'can_start': can_start,
            'reason': reason,
            'status': session.status if session else 'not_found',
            'is_past': self._is_session_past(session) if session else True
        }
    
    # ==================== SESSION LIFECYCLE ====================
    
    def start_session(
        self,
        session_id: int,
        instructor_id: str
    ) -> Tuple[bool, str]:
        """
        Start a session (begin attendance capture)
        
        Returns:
            Tuple of (success, message)
        """
        session = self.get_session_by_id(session_id)
        if not session:
            return False, "Session not found"
        
        # Verify ownership
        if not self._instructor_owns_session(instructor_id, session_id):
            return False, "You don't have permission to start this session"
        
        # Check eligibility
        can_start, reason = self.can_start_session(session_id)
        if not can_start:
            return False, reason
        
        # Update status
        session.status = 'ongoing'
        
        # Initialize attendance records for all expected students
        self._initialize_attendance_records(session_id)
        
        try:
            db.session.commit()
            
            # Log activity
            self._log_activity(
                instructor_id,
                'session_started',
                f'Started session {session_id} for class {session.class_id}'
            )
            
            # Send notifications to students
            self.notification_service.notify_session_started(session_id)
            
            return True, "Session started successfully"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error starting session: {str(e)}")
            return False, "Failed to start session"
    
    def end_session(
        self,
        session_id: int,
        instructor_id: str,
        notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        End a session and finalize attendance
        
        Returns:
            Tuple of (success, message)
        """
        session = self.get_session_by_id(session_id)
        if not session:
            return False, "Session not found"
        
        # Verify ownership
        if not self._instructor_owns_session(instructor_id, session_id):
            return False, "You don't have permission to end this session"
        
        if session.status != 'ongoing':
            return False, "Session is not ongoing"
        
        # Mark absent students
        self._mark_absent_students(session_id)
        
        # Mark late students based on threshold
        self._apply_late_threshold(session_id)
        
        # Update session
        session.status = 'completed'
        if notes:
            session.session_notes = (session.session_notes or '') + f"\nEnd notes: {notes}"
        
        # Update statistics
        session.attendance_count = self._count_present_students(session_id)
        
        try:
            db.session.commit()
            
            # Log activity
            self._log_activity(
                instructor_id,
                'session_ended',
                f'Ended session {session_id}. Attendance: {session.attendance_count}/{session.total_students}'
            )
            
            # Send low attendance alerts if needed
            self._check_low_attendance_alert(session_id)
            
            return True, "Session ended successfully"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error ending session: {str(e)}")
            return False, "Failed to end session"
    
    def dismiss_session(
        self,
        session_id: int,
        instructor_id: str,
        reason: str,
        reschedule_date: Optional[str] = None,
        reschedule_time: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Dismiss/cancel a session with optional rescheduling
        
        Returns:
            Tuple of (success, message)
        """
        session = self.get_session_by_id(session_id)
        if not session:
            return False, "Session not found"
        
        # Verify ownership
        if not self._instructor_owns_session(instructor_id, session_id):
            return False, "You don't have permission to dismiss this session"
        
        if session.status in ['completed', 'cancelled']:
            return False, f"Cannot dismiss {session.status} session"
        
        # Create dismissal record
        dismissal = SessionDismissal(
            session_id=session_id,
            instructor_id=instructor_id,
            reason=reason,
            rescheduled_to=reschedule_date,
            rescheduled_time=reschedule_time,
            status='rescheduled' if reschedule_date else 'dismissed'
        )
        
        # Update session status
        session.status = 'dismissed'
        
        try:
            db.session.add(dismissal)
            
            # Create rescheduled session if date provided
            if reschedule_date and reschedule_time:
                new_session, error = self.create_session(
                    class_id=session.class_id,
                    date=reschedule_date,
                    start_time=reschedule_time,
                    end_time=session.end_time,
                    instructor_id=instructor_id,
                    notes=f"Rescheduled from {session.date}. Reason: {reason}"
                )
                
                if not new_session:
                    db.session.rollback()
                    return False, f"Failed to reschedule: {error}"
            
            db.session.commit()
            
            # Log activity
            self._log_activity(
                instructor_id,
                'session_dismissed',
                f'Dismissed session {session_id}. Reason: {reason}'
            )
            
            # Notify students
            self.notification_service.notify_session_dismissed(
                session_id, reason, reschedule_date
            )
            
            return True, "Session dismissed successfully"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error dismissing session: {str(e)}")
            return False, "Failed to dismiss session"
    
    def suggest_reschedule_dates(
        self,
        session_id: int,
        days_ahead: int = 14
    ) -> List[Dict]:
        """
        Suggest available reschedule dates based on timetable
        
        Returns:
            List of dicts with available slots
        """
        session = self.get_session_by_id(session_id)
        if not session:
            return []
        
        suggestions = []
        
        # Get class timetable
        timetable_entries = Timetable.query.filter_by(
            class_id=session.class_id,
            is_active=True
        ).all()
        
        # Get instructor
        instructor = self._get_class_instructor(session.class_id)
        if not instructor:
            return []
        
        # Check next N days
        start_date = datetime.now() + timedelta(days=1)
        end_date = start_date + timedelta(days=days_ahead)
        holidays = self._get_holidays(start_date, end_date)
        
        current_date = start_date
        while current_date <= end_date:
            if current_date.date() in holidays:
                current_date += timedelta(days=1)
                continue
            
            day_of_week = current_date.weekday()
            schema_day = 0 if day_of_week == 6 else day_of_week + 1
            
            for entry in timetable_entries:
                if entry.day_of_week != schema_day:
                    continue
                
                # Check if slot is available
                has_conflict, _ = self.check_session_conflicts(
                    session.class_id,
                    current_date.date().isoformat(),
                    entry.start_time,
                    entry.end_time,
                    instructor.instructor_id
                )
                
                if not has_conflict:
                    suggestions.append({
                        'date': current_date.date().isoformat(),
                        'start_time': entry.start_time,
                        'end_time': entry.end_time,
                        'day_name': current_date.strftime('%A')
                    })
            
            current_date += timedelta(days=1)
        
        return suggestions[:10]  # Return top 10 suggestions
    
    # ==================== CONFLICT DETECTION ====================
    
    def check_session_conflicts(
        self,
        class_id: str,
        date: str,
        start_time: str,
        end_time: str,
        instructor_id: str,
        exclude_session_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Check for session conflicts
        
        Returns:
            Tuple of (has_conflict, conflict_message)
        """
        # Check for same class conflicts
        class_conflict = ClassSession.query.filter(
            ClassSession.class_id == class_id,
            ClassSession.date == date,
            ClassSession.status.in_(['scheduled', 'ongoing']),
            or_(
                and_(
                    ClassSession.start_time <= start_time,
                    ClassSession.end_time > start_time
                ),
                and_(
                    ClassSession.start_time < end_time,
                    ClassSession.end_time >= end_time
                ),
                and_(
                    ClassSession.start_time >= start_time,
                    ClassSession.end_time <= end_time
                )
            )
        )
        
        if exclude_session_id:
            class_conflict = class_conflict.filter(
                ClassSession.session_id != exclude_session_id
            )
        
        if class_conflict.first():
            return True, "Another session already scheduled for this class at this time"
        
        # Check for instructor conflicts
        instructor_sessions = ClassSession.query.join(
            Class, ClassSession.class_id == Class.class_id
        ).join(
            db.Table('class_instructors'),
            and_(
                db.Table('class_instructors').c.class_id == Class.class_id,
                db.Table('class_instructors').c.instructor_id == instructor_id
            )
        ).filter(
            ClassSession.date == date,
            ClassSession.status.in_(['scheduled', 'ongoing']),
            or_(
                and_(
                    ClassSession.start_time <= start_time,
                    ClassSession.end_time > start_time
                ),
                and_(
                    ClassSession.start_time < end_time,
                    ClassSession.end_time >= end_time
                ),
                and_(
                    ClassSession.start_time >= start_time,
                    ClassSession.end_time <= end_time
                )
            )
        )
        
        if exclude_session_id:
            instructor_sessions = instructor_sessions.filter(
                ClassSession.session_id != exclude_session_id
            )
        
        conflict = instructor_sessions.first()
        if conflict:
            return True, f"You have another session scheduled at this time for class {conflict.class_id}"
        
        return False, ""
    
    # ==================== STUDENT MANAGEMENT ====================
    
    def get_expected_students(self, session_id: int) -> List[Dict]:
        """Get list of students expected to attend session"""
        session = self.get_session_by_id(session_id)
        if not session:
            return []
        
        # Get students enrolled in this class's course
        students = db.session.query(Student, Attendance).join(
            StudentCourse, Student.student_id == StudentCourse.student_id
        ).join(
            Class, StudentCourse.course_code == Class.course_code
        ).outerjoin(
            Attendance,
            and_(
                Attendance.student_id == Student.student_id,
                Attendance.session_id == session_id
            )
        ).filter(
            Class.class_id == session.class_id,
            Student.is_active == 1,
            StudentCourse.status == 'Active'
        ).all()
        
        result = []
        for student, attendance in students:
            result.append({
                'student_id': student.student_id,
                'name': f"{student.fname} {student.lname}",
                'email': student.email,
                'image_path': student.image_path,
                'has_encoding': student.face_encoding is not None,
                'attendance_status': attendance.status if attendance else 'Absent',
                'attendance_time': attendance.timestamp if attendance else None,
                'confidence_score': attendance.confidence_score if attendance else None
            })
        
        return result
    
    def calculate_session_statistics(self, session_id: int) -> Dict:
        """Calculate comprehensive session statistics"""
        session = self.get_session_by_id(session_id)
        if not session:
            return {}
        
        expected_students = self.get_expected_students(session_id)
        total_expected = len(expected_students)
        
        # Count by status
        present = sum(1 for s in expected_students if s['attendance_status'] == 'Present')
        late = sum(1 for s in expected_students if s['attendance_status'] == 'Late')
        absent = sum(1 for s in expected_students if s['attendance_status'] == 'Absent')
        excused = sum(1 for s in expected_students if s['attendance_status'] == 'Excused')
        
        # Calculate percentages
        attendance_rate = (present + late) / total_expected * 100 if total_expected > 0 else 0
        
        # Students without face encodings
        no_encoding = sum(1 for s in expected_students if not s['has_encoding'])
        
        return {
            'total_expected': total_expected,
            'present': present,
            'late': late,
            'absent': absent,
            'excused': excused,
            'attendance_rate': round(attendance_rate, 2),
            'students_without_encoding': no_encoding,
            'session_status': session.status,
            'start_time': session.start_time,
            'end_time': session.end_time
        }
    
    # ==================== HELPER METHODS ====================
    
    def _instructor_owns_class(self, instructor_id: str, class_id: str) -> bool:
        """Check if instructor is assigned to class"""
        result = db.session.execute(
            text("""
                SELECT 1 FROM class_instructors 
                WHERE instructor_id = :instructor_id 
                AND class_id = :class_id
            """),
            {'instructor_id': instructor_id, 'class_id': class_id}
        ).first()
        return result is not None
    
    def _instructor_owns_session(self, instructor_id: str, session_id: int) -> bool:
        """Check if instructor owns session"""
        session = ClassSession.query.get(session_id)
        if not session:
            return False
        return self._instructor_owns_class(instructor_id, session.class_id)
    
    def _get_class_student_count(self, class_id: str) -> int:
        """Get number of students enrolled in class"""
        count = db.session.execute(
            text("""
                SELECT COUNT(DISTINCT s.student_id)
                FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                JOIN classes c ON sc.course_code = c.course_code
                WHERE c.class_id = :class_id
                AND s.is_active = 1
                AND sc.status = 'Active'
            """),
            {'class_id': class_id}
        ).scalar()
        return count or 0
    
    def _get_class_instructor(self, class_id: str) -> Optional[Instructor]:
        """Get primary instructor for class"""
        result = db.session.execute(
            text("""
                SELECT instructor_id FROM class_instructors 
                WHERE class_id = :class_id 
                ORDER BY assigned_date ASC 
                LIMIT 1
            """),
            {'class_id': class_id}
        ).first()
        
        if result:
            return Instructor.query.get(result[0])
        return None
    
    def _initialize_attendance_records(self, session_id: int):
        """Create empty attendance records for all expected students"""
        session = self.get_session_by_id(session_id)
        if not session:
            return
        
        # Get all enrolled students
        students = db.session.execute(
            text("""
                SELECT DISTINCT s.student_id
                FROM students s
                JOIN student_courses sc ON s.student_id = sc.student_id
                JOIN classes c ON sc.course_code = c.course_code
                WHERE c.class_id = :class_id
                AND s.is_active = 1
                AND sc.status = 'Active'
            """),
            {'class_id': session.class_id}
        ).fetchall()
        
        for student_row in students:
            # Check if record exists
            existing = Attendance.query.filter_by(
                student_id=student_row[0],
                session_id=session_id
            ).first()
            
            if not existing:
                attendance = Attendance(
                    student_id=student_row[0],
                    session_id=session_id,
                    status='Absent',
                    method='pending'
                )
                db.session.add(attendance)
        
        db.session.flush()
    
    def _mark_absent_students(self, session_id: int):
        """Mark students without attendance as absent"""
        db.session.execute(
            text("""
                UPDATE attendance 
                SET status = 'Absent', method = 'auto'
                WHERE session_id = :session_id 
                AND status NOT IN ('Present', 'Late', 'Excused')
            """),
            {'session_id': session_id}
        )
    
    def _apply_late_threshold(self, session_id: int):
        """Mark students as late based on threshold setting"""
        session = self.get_session_by_id(session_id)
        if not session:
            return
        
        # Get late threshold (default 10 minutes)
        late_threshold = self._get_setting('auto_mark_late_threshold', 10)
        
        # Calculate cutoff time
        session_start = datetime.strptime(
            f"{session.date} {session.start_time}",
            "%Y-%m-%d %H:%M:%S"
        )
        late_cutoff = session_start + timedelta(minutes=late_threshold)
        
        # Mark late students
        db.session.execute(
            text("""
                UPDATE attendance 
                SET status = 'Late'
                WHERE session_id = :session_id 
                AND status = 'Present'
                AND timestamp > :cutoff
            """),
            {'session_id': session_id, 'cutoff': late_cutoff}
        )
    
    def _count_present_students(self, session_id: int) -> int:
        """Count students marked as present or late"""
        count = db.session.execute(
            text("""
                SELECT COUNT(*) FROM attendance 
                WHERE session_id = :session_id 
                AND status IN ('Present', 'Late')
            """),
            {'session_id': session_id}
        ).scalar()
        return count or 0
    
    def _is_session_past(self, session: ClassSession) -> bool:
        """Check if session time has passed"""
        session_end = datetime.strptime(
            f"{session.date} {session.end_time}",
            "%Y-%m-%d %H:%M:%S"
        )
        return datetime.now() > session_end
    
    def _get_holidays(self, start_date: datetime, end_date: datetime) -> set:
        """Get set of holiday dates in range"""
        from app.models.holiday import Holiday
        
        holidays = Holiday.query.filter(
            Holiday.date >= start_date.date(),
            Holiday.date <= end_date.date()
        ).all()
        
        return {h.date for h in holidays}
    
    def _get_setting(self, key: str, default: any) -> any:
        """Get system setting value"""
        setting = Settings.query.filter_by(setting_key=key).first()
        if setting:
            try:
                return type(default)(setting.setting_value)
            except:
                return default
        return default
    
    def _log_activity(self, user_id: str, activity_type: str, description: str):
        """Log activity to activity_log table"""
        from app.models.activity_log import ActivityLog
        
        log = ActivityLog(
            user_id=user_id,
            user_type='instructor',
            activity_type=activity_type,
            description=description
        )
        db.session.add(log)
        db.session.flush()
    
    def _check_low_attendance_alert(self, session_id: int):
        """Send alert if attendance is below threshold"""
        stats = self.calculate_session_statistics(session_id)
        
        # Get threshold from settings (default 70%)
        threshold = self._get_setting('low_attendance_threshold', 70)
        
        if stats['attendance_rate'] < threshold:
            session = self.get_session_by_id(session_id)
            self.notification_service.notify_low_attendance(
                session_id,
                stats['attendance_rate'],
                session.created_by
            )