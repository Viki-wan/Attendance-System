"""
Session Model
Represents class sessions for attendance tracking
"""

from datetime import datetime, date, time, timedelta
from app import db
from sqlalchemy import event, and_, or_


class ClassSession(db.Model):
    """
    ClassSession Model
    Represents individual class sessions where attendance is taken
    """
    __tablename__ = 'class_sessions'
    
    # Primary Fields
    session_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    class_id = db.Column(db.String(20), db.ForeignKey('classes.class_id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    # Status: scheduled, ongoing, completed, cancelled, dismissed, missed
    status = db.Column(db.String(20), default='scheduled', nullable=False)
    
    # Instructor
    created_by = db.Column(db.String(20), db.ForeignKey('instructors.instructor_id'))
    
    # Attendance Tracking
    attendance_count = db.Column(db.Integer, default=0)
    total_students = db.Column(db.Integer, default=0)
    
    # Additional Information
    session_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    class_ = db.relationship('Class', back_populates='sessions')
    instructor = db.relationship('Instructor', back_populates='sessions')
    attendance_records = db.relationship('Attendance', back_populates='session', lazy='dynamic', cascade='all, delete-orphan')
    dismissal = db.relationship('SessionDismissal', back_populates='session', uselist=False, cascade='all, delete-orphan')
    metrics = db.relationship('SystemMetric', back_populates='session', lazy='dynamic', cascade='all, delete-orphan')
    
    # Table constraints
    __table_args__ = (
        db.CheckConstraint("status IN ('scheduled', 'ongoing', 'completed', 'cancelled', 'missed', 'dismissed')", name='check_session_status'),
    )
    
    def __repr__(self):
        return f'<ClassSession {self.session_id}: {self.class_id} on {self.date}>'
    
    def get_day_name(self) -> str:
        """Get the day name for this session's date"""
        if isinstance(self.date, str):
            session_date = datetime.strptime(self.date, '%Y-%m-%d').date()
        else:
            session_date = self.date
        return session_date.strftime('%A')

    @property
    def duration_minutes(self):
        """Calculate session duration in minutes"""
        if self.start_time and self.end_time:
            start = datetime.combine(date.today(), self.start_time)
            end = datetime.combine(date.today(), self.end_time)
            return int((end - start).total_seconds() / 60)
        return 0
    
    @property
    def attendance_rate(self):
        """Calculate attendance rate percentage"""
        if self.total_students > 0:
            return round((self.attendance_count / self.total_students) * 100, 2)
        return 0.0
    
    @property
    def is_past(self):
        """Check if session is in the past"""
        now = datetime.now()
        session_datetime = datetime.combine(self.date, self.end_time)
        return session_datetime < now
    
    @property
    def is_ongoing(self):
        """Check if session is currently ongoing"""
        now = datetime.now()
        session_start = datetime.combine(self.date, self.start_time)
        session_end = datetime.combine(self.date, self.end_time)
        return session_start <= now <= session_end
    
    @property
    def is_upcoming(self):
        """Check if session is upcoming"""
        now = datetime.now()
        session_start = datetime.combine(self.date, self.start_time)
        return session_start > now
    
    @property
    def can_start(self):
        """Check if session can be started"""
        # Can start if scheduled and within 15 minutes before start time
        if self.status != 'scheduled':
            return False
        
        now = datetime.now()
        session_start = datetime.combine(self.date, self.start_time)
        early_start_time = session_start - timedelta(minutes=15)
        
        return early_start_time <= now <= session_start + timedelta(hours=1)
    
    @property
    def time_until_start(self):
        """Get time remaining until session starts (in minutes)"""
        if self.is_past or self.is_ongoing:
            return 0
        
        now = datetime.now()
        session_start = datetime.combine(self.date, self.start_time)
        delta = session_start - now
        return int(delta.total_seconds() / 60)
    
    def to_dict(self, include_attendance=False):
        """
        Convert session to dictionary
        
        Args:
            include_attendance: Include attendance records
            
        Returns:
            dict: Session data
        """
        data = {
            'session_id': self.session_id,
            'class_id': self.class_id,
            'class_name': self.class_.class_name if self.class_ else None,
            'course_code': self.class_.course_code if self.class_ else None,
            'date': self.date.isoformat() if self.date else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'duration_minutes': self.duration_minutes,
            'status': self.status,
            'created_by': self.created_by,
            'instructor_name': self.instructor.instructor_name if self.instructor else None,
            'attendance_count': self.attendance_count,
            'total_students': self.total_students,
            'attendance_rate': self.attendance_rate,
            'session_notes': self.session_notes,
            'is_past': self.is_past,
            'is_ongoing': self.is_ongoing,
            'is_upcoming': self.is_upcoming,
            'can_start': self.can_start,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_attendance:
            data['attendance_records'] = [att.to_dict() for att in self.attendance_records.all()]
        
        return data
    
    def is_owned_by(self, instructor):
        """
        Check if session is owned by specific instructor
        
        Args:
            instructor: Instructor object or instructor_id
            
        Returns:
            bool: True if instructor owns/created this session
        """
        instructor_id = instructor.instructor_id if hasattr(instructor, 'instructor_id') else instructor
        return self.created_by == instructor_id
    
    def can_be_accessed_by(self, instructor):
        """
        Check if instructor can access this session
        (Either creator or assigned to the class)
        
        Args:
            instructor: Instructor object or instructor_id
            
        Returns:
            bool: True if instructor can access
        """
        instructor_id = instructor.instructor_id if hasattr(instructor, 'instructor_id') else instructor
        
        # Check if creator
        if self.created_by == instructor_id:
            return True
        
        # Check if assigned to class
        if self.class_:
            return self.class_.is_assigned_to(instructor_id)
        
        return False
    
    def start_session(self):
        """Start the session (mark as ongoing)"""
        if self.status == 'scheduled' and self.can_start:
            self.status = 'ongoing'
            
            # Update total students count
            if self.class_:
                self.total_students = self.class_.student_count
            
            db.session.commit()
            return True
        return False
    
    def complete_session(self):
        """Complete the session"""
        if self.status == 'ongoing':
            self.status = 'completed'
            db.session.commit()
            return True
        return False
    
    def cancel_session(self):
        """Cancel the session"""
        if self.status in ['scheduled', 'ongoing']:
            self.status = 'cancelled'
            db.session.commit()
            return True
        return False
    
    def dismiss_session(self, instructor_id, reason, rescheduled_to=None, rescheduled_time=None, notes=None):
        """
        Dismiss the session with reason
        
        Args:
            instructor_id: ID of instructor dismissing
            reason: Reason for dismissal
            rescheduled_to: Optional rescheduled date
            rescheduled_time: Optional rescheduled time
            notes: Additional notes
            
        Returns:
            SessionDismissal object
        """
        from app.models.session_dismissal import SessionDismissal
        
        if self.status not in ['scheduled', 'ongoing']:
            return None
        
        self.status = 'dismissed'
        
        # Create dismissal record
        dismissal = SessionDismissal(
            session_id=self.session_id,
            instructor_id=instructor_id,
            reason=reason,
            rescheduled_to=rescheduled_to,
            rescheduled_time=rescheduled_time,
            notes=notes,
            status='rescheduled' if rescheduled_to else 'dismissed'
        )
        
        db.session.add(dismissal)
        db.session.commit()
        
        return dismissal
    
    def mark_attendance(self, student_id, status='Present', marked_by=None, method='face_recognition', confidence_score=None, notes=None):
        """
        Mark attendance for a student
        
        Args:
            student_id: Student ID
            status: Attendance status (Present, Absent, Late, Excused)
            marked_by: Instructor ID who marked (optional)
            method: Method used (face_recognition, manual, etc.)
            confidence_score: Recognition confidence (for face recognition)
            notes: Additional notes
            
        Returns:
            Attendance object
        """
        from app.models.attendance import Attendance
        
        # Check if already marked
        existing = Attendance.query.filter_by(
            session_id=self.session_id,
            student_id=student_id
        ).first()
        
        if existing:
            # Update existing record
            existing.status = status
            existing.marked_by = marked_by
            existing.method = method
            existing.confidence_score = confidence_score
            existing.notes = notes
            existing.timestamp = datetime.utcnow()
        else:
            # Create new record
            existing = Attendance(
                session_id=self.session_id,
                student_id=student_id,
                status=status,
                marked_by=marked_by,
                method=method,
                confidence_score=confidence_score,
                notes=notes
            )
            db.session.add(existing)
        
        # Update attendance count
        self.update_attendance_count()
        
        db.session.commit()
        return existing
    
    def update_attendance_count(self):
        """Update the attendance count for this session"""
        from app.models.attendance import Attendance
        self.attendance_count = Attendance.query.filter_by(
            session_id=self.session_id,
            status='Present'
        ).count()
    
    def get_attendance_summary(self):
        """
        Get attendance summary for this session
        
        Returns:
            dict: Attendance summary statistics
        """
        from app.models.attendance import Attendance
        from sqlalchemy import func
        
        result = db.session.query(
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == 'Present', 1), else_=0)).label('present'),
            func.sum(db.case((Attendance.status == 'Absent', 1), else_=0)).label('absent'),
            func.sum(db.case((Attendance.status == 'Late', 1), else_=0)).label('late'),
            func.sum(db.case((Attendance.status == 'Excused', 1), else_=0)).label('excused')
        ).filter(Attendance.session_id == self.session_id).first()
        
        return {
            'total': result.total or 0,
            'present': result.present or 0,
            'absent': result.absent or 0,
            'late': result.late or 0,
            'excused': result.excused or 0,
            'attendance_rate': self.attendance_rate
        }
    
    def get_present_students(self):
        """Get list of students marked present"""
        from app.models.attendance import Attendance
        from app.models.student import Student
        
        return Student.query.join(Attendance).filter(
            Attendance.session_id == self.session_id,
            Attendance.status == 'Present'
        ).all()
    
    def get_absent_students(self):
        """Get list of students marked absent or not marked"""
        from app.models.student import Student
        from app.models.attendance import Attendance
        
        if not self.class_:
            return []
        
        # Get all students in class
        all_students = self.class_.students
        
        # Get students with attendance records
        marked_students = db.session.query(Attendance.student_id).filter(
            Attendance.session_id == self.session_id
        ).all()
        marked_ids = [s[0] for s in marked_students]
        
        # Return students not marked or marked absent
        return [s for s in all_students if s.student_id not in marked_ids or 
                Attendance.query.filter_by(session_id=self.session_id, student_id=s.student_id, status='Absent').first()]
    
    @staticmethod
    def get_by_instructor(instructor_id, status=None, start_date=None, end_date=None):
        """
        Get sessions by instructor with optional filters
        
        Args:
            instructor_id: Instructor ID
            status: Optional status filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of ClassSession objects
        """
        query = ClassSession.query.filter_by(created_by=instructor_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if start_date:
            query = query.filter(ClassSession.date >= start_date)
        
        if end_date:
            query = query.filter(ClassSession.date <= end_date)
        
        return query.order_by(ClassSession.date.desc(), ClassSession.start_time.desc()).all()
    
    @staticmethod
    def get_today_sessions(instructor_id=None):
        """
        Get today's sessions
        
        Args:
            instructor_id: Optional instructor filter
            
        Returns:
            List of ClassSession objects
        """
        query = ClassSession.query.filter_by(date=date.today())
        
        if instructor_id:
            query = query.filter_by(created_by=instructor_id)
        
        return query.order_by(ClassSession.start_time).all()
    
    @staticmethod
    def get_upcoming_sessions(instructor_id=None, limit=10):
        """
        Get upcoming sessions
        
        Args:
            instructor_id: Optional instructor filter
            limit: Maximum number of sessions
            
        Returns:
            List of ClassSession objects
        """
        query = ClassSession.query.filter(
            ClassSession.date >= date.today(),
            ClassSession.status == 'scheduled'
        )
        
        if instructor_id:
            query = query.filter_by(created_by=instructor_id)
        
        return query.order_by(ClassSession.date, ClassSession.start_time).limit(limit).all()
    
    @staticmethod
    def check_conflicts(class_id, date_value, start_time, end_time, exclude_session_id=None):
        """
        Check for session conflicts
        
        Args:
            class_id: Class ID
            date_value: Session date
            start_time: Start time
            end_time: End time
            exclude_session_id: Session ID to exclude from check
            
        Returns:
            List of conflicting ClassSession objects
        """
        query = ClassSession.query.filter(
            ClassSession.class_id == class_id,
            ClassSession.date == date_value,
            ClassSession.status.in_(['scheduled', 'ongoing']),
            or_(
                and_(ClassSession.start_time <= start_time, ClassSession.end_time > start_time),
                and_(ClassSession.start_time < end_time, ClassSession.end_time >= end_time),
                and_(ClassSession.start_time >= start_time, ClassSession.end_time <= end_time)
            )
        )
        
        if exclude_session_id:
            query = query.filter(ClassSession.session_id != exclude_session_id)
        
        return query.all()


# Event listeners for automatic timestamp updates
@event.listens_for(ClassSession, 'before_update')
def receive_before_update(mapper, connection, target):
    """Update the updated_at timestamp before updating"""
    target.updated_at = datetime.utcnow()