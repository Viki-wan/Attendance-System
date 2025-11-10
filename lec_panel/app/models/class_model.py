"""
Class Model
Represents class groups (e.g., Year 1 Semester 1, Year 2 Semester 2)
"""

from datetime import datetime
from app import db
from sqlalchemy import event


class Class(db.Model):
    """
    Class Model
    Represents a class group that takes specific courses together
    E.g., "BSSE Year 1 Semester 1", "BBIT Year 2 Semester 2"
    """
    __tablename__ = 'classes'
    
    # Primary Fields
    class_id = db.Column(db.String(20), primary_key=True)
    course_code = db.Column(db.String(20), db.ForeignKey('courses.course_code'), nullable=False)
    class_name = db.Column(db.String(200), nullable=False)
    year = db.Column(db.Integer, default=1, nullable=False)
    semester = db.Column(db.String(10), default='1.1', nullable=False)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    course = db.relationship('Course', back_populates='classes')
    sessions = db.relationship('ClassSession', back_populates='class_', lazy='dynamic', cascade='all, delete-orphan')
    class_instructors = db.relationship('ClassInstructor', back_populates='class_', lazy='dynamic', cascade='all, delete-orphan')
    timetables = db.relationship('Timetable', back_populates='class_', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Class {self.class_id}: {self.class_name}>'
    
    def to_dict(self):
        """Convert class to dictionary"""
        return {
            'class_id': self.class_id,
            'course_code': self.course_code,
            'class_name': self.class_name,
            'year': self.year,
            'semester': self.semester,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'total_sessions': self.sessions.count(),
            'total_instructors': self.class_instructors.count(),
            'course_name': self.course.course_name if self.course else None
        }
    
    @property
    def instructors(self):
        """Get all instructors assigned to this class"""
        from app.models.user import Instructor
        return Instructor.query.join(ClassInstructor).filter(
            ClassInstructor.class_id == self.class_id,
            Instructor.is_active == True
        ).all()
    
    @property
    def students(self):
        """
        Get all students in this class
        Based on course, year, and semester
        """
        from app.models.student import Student
        return Student.query.filter_by(
            course=self.course_code,
            year_of_study=self.year,
            current_semester=self.semester,
            is_active=True
        ).all()
    
    @property
    def student_count(self):
        """Get total number of students in this class"""
        from app.models.student import Student
        return Student.query.filter_by(
            course=self.course_code,
            year_of_study=self.year,
            current_semester=self.semester,
            is_active=True
        ).count()
    
    @property
    def active_timetable(self):
        """Get active timetable entries for this class"""
        return self.timetables.filter_by(is_active=True).all()
    
    def is_assigned_to(self, instructor):
        """
        Check if class is assigned to specific instructor
        
        Args:
            instructor: Instructor object or instructor_id
            
        Returns:
            bool: True if instructor is assigned to this class
        """
        instructor_id = instructor.instructor_id if hasattr(instructor, 'instructor_id') else instructor
        return self.class_instructors.filter_by(instructor_id=instructor_id).first() is not None
    
    def get_sessions(self, status=None, start_date=None, end_date=None):
        """
        Get sessions for this class with optional filters
        
        Args:
            status: Filter by session status (scheduled, ongoing, completed, etc.)
            start_date: Filter sessions from this date
            end_date: Filter sessions up to this date
            
        Returns:
            List of ClassSession objects
        """
        from app.models.session import ClassSession
        query = self.sessions
        
        if status:
            query = query.filter_by(status=status)
        
        if start_date:
            query = query.filter(ClassSession.date >= start_date)
        
        if end_date:
            query = query.filter(ClassSession.date <= end_date)
        
        return query.order_by(ClassSession.date.desc(), ClassSession.start_time.desc()).all()
    
    def get_upcoming_sessions(self, limit=5):
        """
        Get upcoming scheduled sessions
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of ClassSession objects
        """
        from app.models.session import ClassSession
        from datetime import date
        
        return self.sessions.filter(
            ClassSession.date >= date.today(),
            ClassSession.status == 'scheduled'
        ).order_by(
            ClassSession.date.asc(),
            ClassSession.start_time.asc()
        ).limit(limit).all()
    
    def get_completed_sessions(self, limit=None):
        """
        Get completed sessions
        
        Args:
            limit: Optional limit on number of sessions
            
        Returns:
            List of ClassSession objects
        """
        from app.models.session import ClassSession
        query = self.sessions.filter_by(status='completed').order_by(
            ClassSession.date.desc(),
            ClassSession.start_time.desc()
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_attendance_stats(self, start_date=None, end_date=None):
        """
        Get attendance statistics for this class
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            dict: Attendance statistics
        """
        from app.models.session import ClassSession
        from app.models.attendance import Attendance
        from sqlalchemy import func
        
        query = db.session.query(
            func.count(ClassSession.session_id).label('total_sessions'),
            func.sum(ClassSession.attendance_count).label('total_present'),
            func.sum(ClassSession.total_students).label('total_expected')
        ).filter(
            ClassSession.class_id == self.class_id,
            ClassSession.status == 'completed'
        )
        
        if start_date:
            query = query.filter(ClassSession.date >= start_date)
        
        if end_date:
            query = query.filter(ClassSession.date <= end_date)
        
        result = query.first()
        
        total_sessions = result.total_sessions or 0
        total_present = result.total_present or 0
        total_expected = result.total_expected or 0
        
        return {
            'total_sessions': total_sessions,
            'total_present': total_present,
            'total_expected': total_expected,
            'attendance_rate': round((total_present / total_expected * 100), 2) if total_expected > 0 else 0,
            'average_attendance_per_session': round(total_present / total_sessions, 2) if total_sessions > 0 else 0
        }
    
    def assign_instructor(self, instructor_id):
        """
        Assign an instructor to this class
        
        Args:
            instructor_id: Instructor ID to assign
            
        Returns:
            ClassInstructor object
        """
        # Check if already assigned
        existing = ClassInstructor.query.filter_by(
            class_id=self.class_id,
            instructor_id=instructor_id
        ).first()
        
        if existing:
            return existing
        
        # Create new assignment
        assignment = ClassInstructor(
            class_id=self.class_id,
            instructor_id=instructor_id
        )
        db.session.add(assignment)
        db.session.commit()
        
        return assignment
    
    def remove_instructor(self, instructor_id):
        """
        Remove an instructor from this class
        
        Args:
            instructor_id: Instructor ID to remove
            
        Returns:
            bool: True if removed successfully
        """
        assignment = ClassInstructor.query.filter_by(
            class_id=self.class_id,
            instructor_id=instructor_id
        ).first()
        
        if assignment:
            db.session.delete(assignment)
            db.session.commit()
            return True
        
        return False
    
    def activate(self):
        """Activate the class"""
        self.is_active = True
        db.session.commit()
    
    def deactivate(self):
        """Deactivate the class (soft delete)"""
        self.is_active = False
        db.session.commit()
    
    @staticmethod
    def get_active_classes():
        """Get all active classes"""
        return Class.query.filter_by(is_active=True).order_by(Class.class_id).all()
    
    @staticmethod
    def get_by_course(course_code):
        """Get classes by course code"""
        return Class.query.filter_by(course_code=course_code, is_active=True).order_by(
            Class.year, Class.semester
        ).all()
    
    @staticmethod
    def get_by_instructor(instructor_id):
        """Get classes assigned to specific instructor"""
        return Class.query.join(ClassInstructor).filter(
            ClassInstructor.instructor_id == instructor_id,
            Class.is_active == True
        ).order_by(Class.class_id).all()
    
    @staticmethod
    def search(query):
        """
        Search classes by ID or name
        
        Args:
            query: Search string
            
        Returns:
            List of matching Class objects
        """
        search_pattern = f'%{query}%'
        return Class.query.filter(
            db.or_(
                Class.class_id.ilike(search_pattern),
                Class.class_name.ilike(search_pattern)
            ),
            Class.is_active == True
        ).order_by(Class.class_id).all()


class ClassInstructor(db.Model):
    """
    Junction table for Class-Instructor many-to-many relationship
    Tracks which instructors are assigned to which classes
    """
    __tablename__ = 'class_instructors'
    
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(20), db.ForeignKey('classes.class_id'), nullable=False)
    instructor_id = db.Column(db.String(20), db.ForeignKey('instructors.instructor_id'), nullable=False)
    assigned_date = db.Column(db.Date, default=datetime.utcnow)
    
    # Relationships
    class_ = db.relationship('Class', back_populates='class_instructors')
    instructor = db.relationship('Instructor', back_populates='class_instructors')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('class_id', 'instructor_id', name='uix_class_instructor'),
    )
    
    def __repr__(self):
        return f'<ClassInstructor {self.instructor_id} -> {self.class_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'class_id': self.class_id,
            'instructor_id': self.instructor_id,
            'assigned_date': self.assigned_date.isoformat() if self.assigned_date else None
        }


# Event listeners for automatic timestamp updates
@event.listens_for(Class, 'before_update')
def receive_before_update(mapper, connection, target):
    """Update the updated_at timestamp before updating"""
    target.updated_at = datetime.utcnow()