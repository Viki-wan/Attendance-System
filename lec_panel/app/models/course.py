"""
Course Model
Represents academic courses in the system
"""

from datetime import datetime
from app import db
from sqlalchemy import event


class Course(db.Model):
    """
    Course Model
    Represents academic courses that instructors teach and students enroll in
    """
    __tablename__ = 'courses'
    
    # Primary Fields
    course_code = db.Column(db.String(20), primary_key=True)
    course_name = db.Column(db.String(200), nullable=False)
    faculty = db.Column(db.String(100))
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    classes = db.relationship('Class', back_populates='course', lazy='dynamic', cascade='all, delete-orphan')
    instructor_courses = db.relationship('InstructorCourse', back_populates='course', lazy='dynamic', cascade='all, delete-orphan')
    student_courses = db.relationship('StudentCourse', back_populates='course', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Course {self.course_code}: {self.course_name}>'
    
    def to_dict(self):
        """Convert course to dictionary"""
        return {
            'course_code': self.course_code,
            'course_name': self.course_name,
            'faculty': self.faculty,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'total_classes': self.classes.count(),
            'total_instructors': self.instructor_courses.count(),
            'total_students': self.student_courses.count()
        }
    
    @property
    def active_classes(self):
        """Get all active classes for this course"""
        return self.classes.filter_by(is_active=True).all()
    
    @property
    def instructors(self):
        """Get all instructors teaching this course"""
        from app.models.user import Instructor
        return Instructor.query.join(InstructorCourse).filter(
            InstructorCourse.course_code == self.course_code,
            Instructor.is_active == True
        ).all()
    
    @property
    def students(self):
        """Get all students enrolled in this course"""
        from app.models.student import Student
        return Student.query.join(StudentCourse).filter(
            StudentCourse.course_code == self.course_code,
            StudentCourse.status == 'Active',
            Student.is_active == True
        ).all()
    
    def is_taught_by(self, instructor):
        """
        Check if course is taught by specific instructor
        
        Args:
            instructor: Instructor object or instructor_id
            
        Returns:
            bool: True if instructor teaches this course
        """
        instructor_id = instructor.instructor_id if hasattr(instructor, 'instructor_id') else instructor
        return self.instructor_courses.filter_by(instructor_id=instructor_id).first() is not None
    
    def get_instructors_for_semester(self, semester, year):
        """
        Get instructors teaching this course in specific semester
        
        Args:
            semester: Semester code (e.g., '1.1', '1.2')
            year: Academic year
            
        Returns:
            List of Instructor objects
        """
        from app.models.user import Instructor
        return Instructor.query.join(InstructorCourse).filter(
            InstructorCourse.course_code == self.course_code,
            InstructorCourse.semester == semester,
            InstructorCourse.year == year
        ).all()
    
    def get_students_for_semester(self, semester, year):
        """
        Get students enrolled in this course for specific semester
        
        Args:
            semester: Semester code (e.g., '1.1', '1.2')
            year: Academic year
            
        Returns:
            List of Student objects
        """
        from app.models.student import Student
        return Student.query.join(StudentCourse).filter(
            StudentCourse.course_code == self.course_code,
            StudentCourse.semester == semester,
            StudentCourse.year == year,
            StudentCourse.status == 'Active'
        ).all()
    
    def get_coordinator(self, semester=None, year=None):
        """
        Get course coordinator
        
        Args:
            semester: Optional semester filter
            year: Optional year filter
            
        Returns:
            Instructor object or None
        """
        from app.models.user import Instructor
        query = Instructor.query.join(InstructorCourse).filter(
            InstructorCourse.course_code == self.course_code,
            InstructorCourse.is_coordinator == True
        )
        
        if semester:
            query = query.filter(InstructorCourse.semester == semester)
        if year:
            query = query.filter(InstructorCourse.year == year)
        
        return query.first()
    
    def activate(self):
        """Activate the course"""
        self.is_active = True
        db.session.commit()
    
    def deactivate(self):
        """Deactivate the course (soft delete)"""
        self.is_active = False
        db.session.commit()
    
    @staticmethod
    def get_active_courses():
        """Get all active courses"""
        return Course.query.filter_by(is_active=True).order_by(Course.course_code).all()
    
    @staticmethod
    def get_by_faculty(faculty):
        """Get courses by faculty"""
        return Course.query.filter_by(faculty=faculty, is_active=True).order_by(Course.course_code).all()
    
    @staticmethod
    def search(query):
        """
        Search courses by code or name
        
        Args:
            query: Search string
            
        Returns:
            List of matching Course objects
        """
        search_pattern = f'%{query}%'
        return Course.query.filter(
            db.or_(
                Course.course_code.ilike(search_pattern),
                Course.course_name.ilike(search_pattern)
            ),
            Course.is_active == True
        ).order_by(Course.course_code).all()


class InstructorCourse(db.Model):
    """
    Junction table for Instructor-Course many-to-many relationship
    Tracks which instructors teach which courses in which semester
    """
    __tablename__ = 'instructor_courses'
    
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.String(20), db.ForeignKey('instructors.instructor_id'), nullable=False)
    course_code = db.Column(db.String(20), db.ForeignKey('courses.course_code'), nullable=False)
    semester = db.Column(db.String(10))
    year = db.Column(db.Integer)
    is_coordinator = db.Column(db.Boolean, default=False)
    
    # Relationships
    instructor = db.relationship('Instructor', back_populates='instructor_courses')
    course = db.relationship('Course', back_populates='instructor_courses')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('instructor_id', 'course_code', 'semester', 'year', name='uix_instructor_course_semester'),
    )
    
    def __repr__(self):
        return f'<InstructorCourse {self.instructor_id} -> {self.course_code}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'instructor_id': self.instructor_id,
            'course_code': self.course_code,
            'semester': self.semester,
            'year': self.year,
            'is_coordinator': self.is_coordinator
        }


class StudentCourse(db.Model):
    """
    Junction table for Student-Course many-to-many relationship
    Tracks student enrollments in courses
    """
    __tablename__ = 'student_courses'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('students.student_id'), nullable=False)
    course_code = db.Column(db.String(20), db.ForeignKey('courses.course_code'), nullable=False)
    semester = db.Column(db.String(10))
    year = db.Column(db.Integer)
    enrollment_date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Active')  # Active, Dropped, Completed, Failed
    
    # Relationships
    student = db.relationship('Student', back_populates='student_courses')
    course = db.relationship('Course', back_populates='student_courses')
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('student_id', 'course_code', 'semester', 'year', name='uix_student_course_semester'),
        db.CheckConstraint("status IN ('Active', 'Dropped', 'Completed', 'Failed')", name='check_enrollment_status')
    )
    
    def __repr__(self):
        return f'<StudentCourse {self.student_id} -> {self.course_code}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'course_code': self.course_code,
            'semester': self.semester,
            'year': self.year,
            'enrollment_date': self.enrollment_date.isoformat() if self.enrollment_date else None,
            'status': self.status
        }
    
    def drop(self):
        """Drop the course enrollment"""
        self.status = 'Dropped'
        db.session.commit()
    
    def complete(self):
        """Mark course as completed"""
        self.status = 'Completed'
        db.session.commit()
    
    def fail(self):
        """Mark course as failed"""
        self.status = 'Failed'
        db.session.commit()
    
    def reactivate(self):
        """Reactivate the enrollment"""
        self.status = 'Active'
        db.session.commit()


# Event listeners for automatic timestamp updates
@event.listens_for(Course, 'before_update')
def receive_before_update(mapper, connection, target):
    """Update the updated_at timestamp before updating"""
    target.updated_at = datetime.utcnow()