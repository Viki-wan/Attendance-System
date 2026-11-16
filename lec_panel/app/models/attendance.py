"""
Attendance Model
Tracks student attendance for class sessions with face recognition integration.
"""
from datetime import datetime
from app import db
from sqlalchemy import Index


class Attendance(db.Model):
    """
    Attendance records for students in class sessions.
    
    Attributes:
        id: Primary key
        student_id: Foreign key to students table
        session_id: Foreign key to class_sessions table
        timestamp: When attendance was marked
        status: Present, Absent, Late, Excused
        marked_by: Instructor who marked attendance
        method: face_recognition, manual, api
        confidence_score: Face recognition confidence (0.0-1.0)
        notes: Additional notes or reasons
    """
    __tablename__ = 'attendance'
    
    # Status constants
    STATUS_PRESENT = 'Present'
    STATUS_ABSENT = 'Absent'
    STATUS_LATE = 'Late'
    STATUS_EXCUSED = 'Excused'
    
    VALID_STATUSES = [STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_EXCUSED]
    
    # Method constants
    METHOD_FACE_RECOGNITION = 'face_recognition'
    METHOD_MANUAL = 'manual'
    METHOD_API = 'api'
    METHOD_BULK_IMPORT = 'bulk_import'
    
    VALID_METHODS = [METHOD_FACE_RECOGNITION, METHOD_MANUAL, METHOD_API, METHOD_BULK_IMPORT]
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Keys
    student_id = db.Column(
        db.String(50), 
        db.ForeignKey('students.student_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    session_id = db.Column(
        db.Integer, 
        db.ForeignKey('class_sessions.session_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    marked_by = db.Column(
        db.String(50),
        db.ForeignKey('instructors.instructor_id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Attendance Details
    timestamp = db.Column(
        db.DateTime, 
        nullable=False, 
        default=datetime.utcnow,
        index=True
    )
    status = db.Column(
        db.String(20), 
        nullable=False, 
        default=STATUS_ABSENT
    )
    method = db.Column(
        db.String(30), 
        nullable=False, 
        default=METHOD_FACE_RECOGNITION
    )
    confidence_score = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships# NEW - Use back_populates
    student = db.relationship(
        'Student',
        back_populates='attendance_records'
    )
    # NEW - Use back_populates
    session = db.relationship(
        'ClassSession',
        back_populates='attendance_records'
    )
    marker = db.relationship(
        'Instructor',
        foreign_keys=[marked_by],
        overlaps="attendance_records"
    )
    
    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('student_id', 'session_id', name='uq_student_session'),
        Index('idx_attendance_status', 'status'),
        Index('idx_attendance_method', 'method'),
        Index('idx_attendance_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<Attendance {self.student_id} - Session {self.session_id} - {self.status}>'
    
    # ======================
    # Validation Methods
    # ======================
    
    @staticmethod
    def validate_status(status):
        """Validate attendance status."""
        if status not in Attendance.VALID_STATUSES:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(Attendance.VALID_STATUSES)}")
        return True
    
    @staticmethod
    def validate_method(method):
        """Validate marking method."""
        if method not in Attendance.VALID_METHODS:
            raise ValueError(f"Invalid method. Must be one of: {', '.join(Attendance.VALID_METHODS)}")
        return True
    
    @staticmethod
    def validate_confidence_score(score):
        """Validate confidence score range."""
        if score is not None and (score < 0.0 or score > 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return True
    
    def validate(self):
        """Validate attendance record."""
        self.validate_status(self.status)
        self.validate_method(self.method)
        if self.confidence_score is not None:
            self.validate_confidence_score(self.confidence_score)
        
        # Face recognition method should have confidence score
        if self.method == self.METHOD_FACE_RECOGNITION and self.confidence_score is None:
            raise ValueError("Face recognition method requires confidence_score")
        
        return True
    
    # ======================
    # Property Methods
    # ======================
    
    @property
    def is_present(self):
        """Check if student was present."""
        return self.status == self.STATUS_PRESENT
    
    @property
    def is_absent(self):
        """Check if student was absent."""
        return self.status == self.STATUS_ABSENT
    
    @property
    def is_late(self):
        """Check if student was late."""
        return self.status == self.STATUS_LATE
    
    @property
    def is_excused(self):
        """Check if absence was excused."""
        return self.status == self.STATUS_EXCUSED
    
    @property
    def was_marked_automatically(self):
        """Check if attendance was marked by face recognition."""
        return self.method == self.METHOD_FACE_RECOGNITION
    
    @property
    def was_marked_manually(self):
        """Check if attendance was marked manually."""
        return self.method == self.METHOD_MANUAL
    
    @property
    def minutes_after_start(self):
        """Calculate how many minutes after session start the attendance was marked."""
        if not self.session:
            return None
        
        session_datetime = datetime.combine(
            datetime.strptime(self.session.date, '%Y-%m-%d').date(),
            datetime.strptime(self.session.start_time, '%H:%M').time()
        )
        
        delta = self.timestamp - session_datetime
        return int(delta.total_seconds() / 60)
    
    @property
    def is_verified(self):
        """Check if attendance is verified (high confidence or manual)."""
        if self.method == self.METHOD_MANUAL:
            return True
        if self.method == self.METHOD_FACE_RECOGNITION:
            return self.confidence_score and self.confidence_score >= 0.6
        return False
    
    # ======================
    # Modification Methods
    # ======================
    
    def mark_present(self, confidence_score=None, method=METHOD_FACE_RECOGNITION, marked_by=None, notes=None):
        """Mark student as present."""
        self.status = self.STATUS_PRESENT
        self.method = method
        self.confidence_score = confidence_score
        self.marked_by = marked_by
        self.notes = notes
        self.timestamp = datetime.utcnow()
        self.validate()
        return self
    
    def mark_absent(self, marked_by=None, notes=None):
        """Mark student as absent."""
        self.status = self.STATUS_ABSENT
        self.method = self.METHOD_MANUAL
        self.confidence_score = None
        self.marked_by = marked_by
        self.notes = notes
        self.timestamp = datetime.utcnow()
        return self
    
    def mark_late(self, confidence_score=None, method=METHOD_FACE_RECOGNITION, marked_by=None, notes=None):
        """Mark student as late."""
        self.status = self.STATUS_LATE
        self.method = method
        self.confidence_score = confidence_score
        self.marked_by = marked_by
        self.notes = notes
        self.timestamp = datetime.utcnow()
        self.validate()
        return self
    
    def excuse_absence(self, marked_by, reason):
        """Excuse a student's absence."""
        self.status = self.STATUS_EXCUSED
        self.method = self.METHOD_MANUAL
        self.marked_by = marked_by
        self.notes = f"Excused: {reason}"
        self.timestamp = datetime.utcnow()
        return self
    
    def update_status(self, new_status, marked_by, notes=None):
        """Update attendance status (for corrections)."""
        self.validate_status(new_status)
        self.status = new_status
        self.marked_by = marked_by
        self.method = self.METHOD_MANUAL
        if notes:
            self.notes = f"Corrected: {notes}"
        self.timestamp = datetime.utcnow()
        return self
    
    # ======================
    # Query Helper Methods
    # ======================
    
    @staticmethod
    def get_by_session(session_id):
        """Get all attendance records for a session."""
        return Attendance.query.filter_by(session_id=session_id).all()
    
    @staticmethod
    def get_by_student(student_id):
        """Get all attendance records for a student."""
        return Attendance.query.filter_by(student_id=student_id).order_by(Attendance.timestamp.desc()).all()
    
    @staticmethod
    def get_by_student_and_session(student_id, session_id):
        """Get attendance record for specific student and session."""
        return Attendance.query.filter_by(
            student_id=student_id,
            session_id=session_id
        ).first()
    
    @staticmethod
    def exists(student_id, session_id):
        """Check if attendance record exists."""
        return Attendance.query.filter_by(
            student_id=student_id,
            session_id=session_id
        ).first() is not None
    
    @staticmethod
    def get_present_for_session(session_id):
        """Get all students marked present for a session."""
        return Attendance.query.filter_by(
            session_id=session_id,
            status=Attendance.STATUS_PRESENT
        ).all()
    
    @staticmethod
    def get_absent_for_session(session_id):
        """Get all students marked absent for a session."""
        return Attendance.query.filter_by(
            session_id=session_id,
            status=Attendance.STATUS_ABSENT
        ).all()
    
    @staticmethod
    def get_late_for_session(session_id):
        """Get all students marked late for a session."""
        return Attendance.query.filter_by(
            session_id=session_id,
            status=Attendance.STATUS_LATE
        ).all()
    
    @staticmethod
    def get_by_date_range(student_id, start_date, end_date):
        """Get student's attendance records within date range."""
        from app.models.session import ClassSession
        
        return db.session.query(Attendance).join(ClassSession).filter(
            Attendance.student_id == student_id,
            ClassSession.date >= start_date,
            ClassSession.date <= end_date
        ).order_by(ClassSession.date.desc()).all()
    
    @staticmethod
    def get_by_course(student_id, course_code):
        """Get student's attendance for a specific course."""
        from app.models.session import ClassSession
        from app.models.class_model import Class
        
        return db.session.query(Attendance).join(
            ClassSession, Attendance.session_id == ClassSession.session_id
        ).join(
            Class, ClassSession.class_id == Class.class_id
        ).filter(
            Attendance.student_id == student_id,
            Class.course_code == course_code
        ).all()
    
    # ======================
    # Statistics Methods
    # ======================
    
    @staticmethod
    def get_student_statistics(student_id, course_code=None):
        """
        Get attendance statistics for a student.
        
        Returns:
            dict: {
                'total_sessions': int,
                'present': int,
                'absent': int,
                'late': int,
                'excused': int,
                'attendance_rate': float
            }
        """
        query = Attendance.query.filter_by(student_id=student_id)
        
        if course_code:
            from app.models.session import ClassSession
            from app.models.class_model import Class
            
            query = query.join(ClassSession).join(Class).filter(
                Class.course_code == course_code
            )
        
        records = query.all()
        
        total = len(records)
        present = sum(1 for r in records if r.status == Attendance.STATUS_PRESENT)
        absent = sum(1 for r in records if r.status == Attendance.STATUS_ABSENT)
        late = sum(1 for r in records if r.status == Attendance.STATUS_LATE)
        excused = sum(1 for r in records if r.status == Attendance.STATUS_EXCUSED)
        
        # Calculate attendance rate (Present + Late counted as attended)
        attended = present + late
        attendance_rate = (attended / total * 100) if total > 0 else 0.0
        
        return {
            'total_sessions': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'attended': attended,
            'attendance_rate': round(attendance_rate, 2)
        }
    
    @staticmethod
    def get_session_statistics(session_id):
        """
        Get attendance statistics for a session.
        
        Returns:
            dict: {
                'total_students': int,
                'present': int,
                'absent': int,
                'late': int,
                'excused': int,
                'attendance_rate': float,
                'pending': int
            }
        """
        from app.models.session import ClassSession
        
        session = ClassSession.query.get(session_id)
        if not session:
            return None
        
        records = Attendance.get_by_session(session_id)
        
        present = sum(1 for r in records if r.status == Attendance.STATUS_PRESENT)
        absent = sum(1 for r in records if r.status == Attendance.STATUS_ABSENT)
        late = sum(1 for r in records if r.status == Attendance.STATUS_LATE)
        excused = sum(1 for r in records if r.status == Attendance.STATUS_EXCUSED)
        
        total_students = session.total_students
        marked = len(records)
        pending = total_students - marked
        
        # Calculate attendance rate
        attended = present + late
        attendance_rate = (attended / total_students * 100) if total_students > 0 else 0.0
        
        return {
            'total_students': total_students,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'marked': marked,
            'pending': pending,
            'attendance_rate': round(attendance_rate, 2)
        }
    
    @staticmethod
    def get_low_attendance_students(course_code, threshold=75.0):
        """
        Get students with attendance below threshold for a course.
        
        Args:
            course_code: Course code
            threshold: Minimum attendance percentage (default 75%)
        
        Returns:
            list: [(student, attendance_rate), ...]
        """
        from app.models.student import Student
        from app.models.course import StudentCourse
        
        # Get all students enrolled in the course
        enrollments = StudentCourse.query.filter_by(
            course_code=course_code,
            status='Active'
        ).all()
        
        low_attendance = []
        
        for enrollment in enrollments:
            stats = Attendance.get_student_statistics(
                enrollment.student_id, 
                course_code
            )
            
            if stats['attendance_rate'] < threshold and stats['total_sessions'] > 0:
                student = Student.query.get(enrollment.student_id)
                low_attendance.append((student, stats['attendance_rate']))
        
        # Sort by attendance rate (lowest first)
        low_attendance.sort(key=lambda x: x[1])
        
        return low_attendance
    
    # ======================
    # Serialization
    # ======================
    
    def to_dict(self, include_relations=False):
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'student_id': self.student_id,
            'session_id': self.session_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'method': self.method,
            'confidence_score': self.confidence_score,
            'notes': self.notes,
            'marked_by': self.marked_by,
            'is_present': self.is_present,
            'is_verified': self.is_verified,
            'minutes_after_start': self.minutes_after_start
        }
        
        if include_relations:
            if self.student:
                data['student'] = {
                    'student_id': self.student.student_id,
                    'name': f"{self.student.fname} {self.student.lname}",
                    'email': self.student.email
                }
            
            if self.marker:
                data['marked_by_name'] = self.marker.instructor_name
        
        return data