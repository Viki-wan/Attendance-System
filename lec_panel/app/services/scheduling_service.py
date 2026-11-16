# app/services/scheduling_service.py
"""
Intelligent scheduling service for automatic session creation and timetable management.
Handles recurring sessions, conflict detection, and holiday awareness.
"""

from app.models.class_session import ClassSession
from app.models.timetable import Timetable
from app.models.holiday import Holiday
from app.extensions import db
from datetime import datetime, timedelta, time
from sqlalchemy import and_


class SchedulingService:
    """Manages automated scheduling and timetable operations."""
    
    @staticmethod
    def create_sessions_from_timetable(class_id, start_date, end_date, instructor_id):
        """
        Generate class sessions from timetable for a date range.
        Skips holidays and weekends (if not in timetable).
        """
        timetable_entries = Timetable.query.filter(
            and_(
                Timetable.class_id == class_id,
                Timetable.is_active == True
            )
        ).all()
        
        if not timetable_entries:
            return [], "No timetable found for this class"
        
        # Get holidays in the date range
        holidays = Holiday.query.filter(
            and_(
                Holiday.date >= start_date,
                Holiday.date <= end_date
            )
        ).all()
        holiday_dates = {h.date for h in holidays}
        
        sessions_created = []
        conflicts = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip if holiday
            if current_date in holiday_dates:
                current_date += timedelta(days=1)
                continue
            
            # Get day of week (0=Monday in Python, but schema uses 0=Sunday)
            day_of_week = (current_date.weekday() + 1) % 7
            
            # Find matching timetable entry
            for entry in timetable_entries:
                if entry.day_of_week == day_of_week:
                    # Check for conflicts
                    conflict = SchedulingService._check_session_conflict(
                        class_id, current_date, entry.start_time, entry.end_time
                    )
                    
                    if conflict:
                        conflicts.append({
                            'date': current_date,
                            'time': entry.start_time,
                            'conflict': conflict
                        })
                        continue
                    
                    # Create session
                    session = ClassSession(
                        class_id=class_id,
                        date=current_date.strftime('%Y-%m-%d'),
                        start_time=entry.start_time,
                        end_time=entry.end_time,
                        status='scheduled',
                        created_by=instructor_id
                    )
                    db.session.add(session)
                    sessions_created.append(session)
            
            current_date += timedelta(days=1)
        
        if sessions_created:
            db.session.commit()
        
        return sessions_created, conflicts
    
    @staticmethod
    def _check_session_conflict(class_id, date, start_time, end_time):
        """Check if a session conflicts with existing sessions."""
        date_str = date.strftime('%Y-%m-%d')
        
        existing = ClassSession.query.filter(
            and_(
                ClassSession.class_id == class_id,
                ClassSession.date == date_str,
                ClassSession.status != 'cancelled'
            )
        ).all()
        
        for session in existing:
            # Check time overlap
            if SchedulingService._times_overlap(
                start_time, end_time,
                session.start_time, session.end_time
            ):
                return f"Conflicts with existing session at {session.start_time}"
        
        return None
    
    @staticmethod
    def _times_overlap(start1, end1, start2, end2):
        """Check if two time ranges overlap."""
        # Convert strings to time objects if needed
        if isinstance(start1, str):
            start1 = datetime.strptime(start1, '%H:%M').time()
        if isinstance(end1, str):
            end1 = datetime.strptime(end1, '%H:%M').time()
        if isinstance(start2, str):
            start2 = datetime.strptime(start2, '%H:%M').time()
        if isinstance(end2, str):
            end2 = datetime.strptime(end2, '%H:%M').time()
        
        return start1 < end2 and start2 < end1
    
    @staticmethod
    def get_next_session_time(class_id):
        """Get the next scheduled session time based on timetable."""
        now = datetime.now()
        current_day = (now.weekday() + 1) % 7
        
        # Get timetable for this class
        entries = Timetable.query.filter(
            and_(
                Timetable.class_id == class_id,
                Timetable.is_active == True
            )
        ).order_by(Timetable.day_of_week, Timetable.start_time).all()
        
        if not entries:
            return None
        
        # Look for next session in the next 7 days
        for i in range(8):
            check_date = now.date() + timedelta(days=i)
            check_day = (check_date.weekday() + 1) % 7
            
            for entry in entries:
                if entry.day_of_week == check_day:
                    session_datetime = datetime.combine(
                        check_date,
                        datetime.strptime(entry.start_time, '%H:%M').time()
                    )
                    
                    if session_datetime > now:
                        return {
                            'date': check_date,
                            'start_time': entry.start_time,
                            'end_time': entry.end_time,
                            'datetime': session_datetime
                        }
        
        return None
    
    @staticmethod
    def suggest_session_time(class_id, preferred_date=None):
        """Suggest available time slots for a session."""
        if preferred_date is None:
            preferred_date = datetime.now().date()
        
        # Get timetable
        day_of_week = (preferred_date.weekday() + 1) % 7
        timetable_entries = Timetable.query.filter(
            and_(
                Timetable.class_id == class_id,
                Timetable.day_of_week == day_of_week,
                Timetable.is_active == True
            )
        ).all()
        
        suggestions = []
        for entry in timetable_entries:
            conflict = SchedulingService._check_session_conflict(
                class_id, preferred_date, entry.start_time, entry.end_time
            )
            
            suggestions.append({
                'start_time': entry.start_time,
                'end_time': entry.end_time,
                'available': conflict is None,
                'conflict_reason': conflict
            })
        
        return suggestions
    
    @staticmethod
    def auto_schedule_today(instructor_id):
        """Automatically create sessions for today based on timetables."""
        from app.models.class_instructors import ClassInstructor
        
        today = datetime.now().date()
        day_of_week = (today.weekday() + 1) % 7
        
        # Get instructor's classes
        class_assignments = ClassInstructor.query.filter_by(
            instructor_id=instructor_id
        ).all()
        
        sessions_created = []
        for assignment in class_assignments:
            # Check if session already exists
            existing = ClassSession.query.filter(
                and_(
                    ClassSession.class_id == assignment.class_id,
                    ClassSession.date == today.strftime('%Y-%m-%d')
                )
            ).first()
            
            if existing:
                continue
            
            # Get timetable for today
            timetable_entry = Timetable.query.filter(
                and_(
                    Timetable.class_id == assignment.class_id,
                    Timetable.day_of_week == day_of_week,
                    Timetable.is_active == True
                )
            ).first()
            
            if timetable_entry:
                session = ClassSession(
                    class_id=assignment.class_id,
                    date=today.strftime('%Y-%m-%d'),
                    start_time=timetable_entry.start_time,
                    end_time=timetable_entry.end_time,
                    status='scheduled',
                    created_by=instructor_id
                )
                db.session.add(session)
                sessions_created.append(session)
        
        if sessions_created:
            db.session.commit()
        
        return sessions_created
    
    @staticmethod
    def reschedule_session(session_id, new_date, new_start_time, new_end_time):
        """Reschedule an existing session to a new time."""
        session = ClassSession.query.get(session_id)
        if not session:
            return False, "Session not found"
        
        # Check for conflicts
        conflict = SchedulingService._check_session_conflict(
            session.class_id, 
            datetime.strptime(new_date, '%Y-%m-%d').date(),
            new_start_time, 
            new_end_time
        )
        
        if conflict:
            return False, conflict
        
        session.date = new_date
        session.start_time = new_start_time
        session.end_time = new_end_time
        db.session.commit()
        
        return True, "Session rescheduled successfully"