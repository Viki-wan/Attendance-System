"""
Student Model
Represents students with face recognition capabilities
"""

from datetime import datetime
from app import db
from sqlalchemy import event
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib


class Student(db.Model):
    """
    Student Model
    Represents students enrolled in the system with face recognition data
    """
    __tablename__ = 'students'
    
    # Primary Fields
    student_id = db.Column(db.String(20), primary_key=True)
    fname = db.Column(db.String(100), nullable=False)
    lname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(15), unique=True)
    password = db.Column(db.String(255))
    
    # Academic Information
    course = db.Column(db.String(20))
    year_of_study = db.Column(db.Integer, default=1)
    current_semester = db.Column(db.String(10), default='1.1')
    
    # Face Recognition Data
    image_path = db.Column(db.String(255))  # Path to original student photo
    image_hash = db.Column(db.String(64))  # Hash for duplicate detection
    face_encoding = db.Column(db.LargeBinary)  # Serialized face encoding
    face_only_path = db.Column(db.String(255))  # Path to cropped face image
    face_encoding_path = db.Column(db.String(255))  # Path to encoding file
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    attendance_records = db.relationship(
        'Attendance', 
        back_populates='student', 
        lazy='dynamic', 
        cascade='all, delete-orphan'
    )
    
    student_courses = db.relationship(
        'StudentCourse', 
        back_populates='student', 
        lazy='dynamic', 
        cascade='all, delete-orphan'
    )
    
    # FIXED: Added overlaps to prevent conflict with Instructor.notifications
    notifications = db.relationship(
        'Notification', 
        foreign_keys='Notification.user_id',
        primaryjoin="and_(Student.student_id==foreign(Notification.user_id), Notification.user_type=='student')",
        lazy='dynamic',
        cascade='all, delete-orphan',
        overlaps="notifications"  # THIS FIXES THE WARNING
    )
    
    def __repr__(self):
        return f'<Student {self.student_id}: {self.full_name}>'
    
    @property
    def full_name(self):
        """Get student's full name"""
        return f"{self.fname} {self.lname}"
    
    def set_password(self, password):
        """Hash and set password"""
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches"""
        if not self.password:
            return False
        return check_password_hash(self.password, password)
    
    def calculate_image_hash(self, image_data):
        """
        Calculate hash of image for duplicate detection
        
        Args:
            image_data: Binary image data
            
        Returns:
            str: SHA256 hash of image
        """
        return hashlib.sha256(image_data).hexdigest()
    
    def has_face_encoding(self):
        """Check if student has face encoding registered"""
        return self.face_encoding is not None
    
    def to_dict(self, include_sensitive=False):
        """
        Convert student to dictionary
        
        Args:
            include_sensitive: Include sensitive fields like password hash
            
        Returns:
            dict: Student data
        """
        data = {
            'student_id': self.student_id,
            'fname': self.fname,
            'lname': self.lname,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'course': self.course,
            'year_of_study': self.year_of_study,
            'current_semester': self.current_semester,
            'is_active': self.is_active,
            'has_face_encoding': self.has_face_encoding(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            data.update({
                'image_path': self.image_path,
                'face_only_path': self.face_only_path,
                'face_encoding_path': self.face_encoding_path,
                'image_hash': self.image_hash
            })
        
        return data
    
    def get_attendance_records(self, start_date=None, end_date=None, course_code=None):
        """
        Get attendance records with optional filters
        
        Args:
            start_date: Filter from this date
            end_date: Filter until this date
            course_code: Filter by course
            
        Returns:
            List of Attendance objects
        """
        from app.models.attendance import Attendance
        from app.models.session import ClassSession
        
        query = self.attendance_records.join(ClassSession)
        
        if start_date:
            query = query.filter(ClassSession.date >= start_date)
        
        if end_date:
            query = query.filter(ClassSession.date <= end_date)
        
        if course_code:
            from app.models.class_ import Class
            query = query.join(Class).filter(Class.course_code == course_code)
        
        return query.order_by(ClassSession.date.desc()).all()
    
    def get_attendance_stats(self, start_date=None, end_date=None, course_code=None):
        """
        Get attendance statistics for student
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            course_code: Optional course filter
            
        Returns:
            dict: Attendance statistics
        """
        from app.models.attendance import Attendance
        from app.models.session import ClassSession
        from sqlalchemy import func
        
        # Base query
        query = db.session.query(
            func.count(Attendance.id).label('total_records'),
            func.sum(db.case((Attendance.status == 'Present', 1), else_=0)).label('present_count'),
            func.sum(db.case((Attendance.status == 'Absent', 1), else_=0)).label('absent_count'),
            func.sum(db.case((Attendance.status == 'Late', 1), else_=0)).label('late_count'),
            func.sum(db.case((Attendance.status == 'Excused', 1), else_=0)).label('excused_count')
        ).filter(
            Attendance.student_id == self.student_id
        ).join(ClassSession)
        
        # Apply filters
        if start_date:
            query = query.filter(ClassSession.date >= start_date)
        
        if end_date:
            query = query.filter(ClassSession.date <= end_date)
        
        if course_code:
            from app.models.class_ import Class
            query = query.join(Class).filter(Class.course_code == course_code)
        
        result = query.first()
        
        total = result.total_records or 0
        present = result.present_count or 0
        absent = result.absent_count or 0
        late = result.late_count or 0
        excused = result.excused_count or 0
        
        return {
            'total_sessions': total,
            'present': present,
            'absent': absent,
            'late': late,
            'excused': excused,
            'attendance_rate': round((present / total * 100), 2) if total > 0 else 0,
            'present_or_late': present + late,
            'present_or_late_rate': round(((present + late) / total * 100), 2) if total > 0 else 0
        }
    
    def get_courses(self, semester=None, year=None, status='Active'):
        """
        Get courses enrolled by student
        
        Args:
            semester: Optional semester filter
            year: Optional year filter
            status: Enrollment status filter
            
        Returns:
            List of Course objects
        """
        from app.models.course import Course, StudentCourse
        
        query = Course.query.join(StudentCourse).filter(
            StudentCourse.student_id == self.student_id
        )
        
        if semester:
            query = query.filter(StudentCourse.semester == semester)
        
        if year:
            query = query.filter(StudentCourse.year == year)
        
        if status:
            query = query.filter(StudentCourse.status == status)
        
        return query.all()
    
    def get_current_courses(self):
        """Get courses for current semester and year"""
        return self.get_courses(
            semester=self.current_semester,
            year=self.year_of_study,
            status='Active'
        )
    
    def enroll_in_course(self, course_code, semester=None, year=None):
        """
        Enroll student in a course
        
        Args:
            course_code: Course code to enroll in
            semester: Semester (defaults to current)
            year: Year (defaults to current)
            
        Returns:
            StudentCourse object
        """
        from app.models.course import StudentCourse
        
        semester = semester or self.current_semester
        year = year or self.year_of_study
        
        # Check if already enrolled
        existing = StudentCourse.query.filter_by(
            student_id=self.student_id,
            course_code=course_code,
            semester=semester,
            year=year
        ).first()
        
        if existing:
            if existing.status != 'Active':
                existing.reactivate()
            return existing
        
        # Create new enrollment
        enrollment = StudentCourse(
            student_id=self.student_id,
            course_code=course_code,
            semester=semester,
            year=year,
            status='Active'
        )
        db.session.add(enrollment)
        db.session.commit()
        
        return enrollment
    
    def drop_course(self, course_code, semester=None, year=None):
        """
        Drop a course
        
        Args:
            course_code: Course code to drop
            semester: Semester (defaults to current)
            year: Year (defaults to current)
            
        Returns:
            bool: True if dropped successfully
        """
        from app.models.course import StudentCourse
        
        semester = semester or self.current_semester
        year = year or self.year_of_study
        
        enrollment = StudentCourse.query.filter_by(
            student_id=self.student_id,
            course_code=course_code,
            semester=semester,
            year=year
        ).first()
        
        if enrollment:
            enrollment.drop()
            return True
        
        return False
    
    def get_unread_notifications(self):
        """Get unread notifications for student"""
        return self.notifications.filter_by(is_read=False).order_by(
            db.desc('created_at')
        ).all()
    
    def activate(self):
        """Activate the student account"""
        self.is_active = True
        db.session.commit()
    
    def deactivate(self):
        """Deactivate the student account (soft delete)"""
        self.is_active = False
        db.session.commit()
    
    @staticmethod
    def get_active_students():
        """Get all active students"""
        return Student.query.filter_by(is_active=True).order_by(Student.student_id).all()
    
    @staticmethod
    def get_by_course(course_code, year=None, semester=None):
        """
        Get students by course
        
        Args:
            course_code: Course code
            year: Optional year filter
            semester: Optional semester filter
            
        Returns:
            List of Student objects
        """
        query = Student.query.filter_by(course=course_code, is_active=True)
        
        if year:
            query = query.filter_by(year_of_study=year)
        
        if semester:
            query = query.filter_by(current_semester=semester)
        
        return query.order_by(Student.student_id).all()
    
    @staticmethod
    def get_without_face_encoding():
        """Get students who haven't registered face encoding"""
        return Student.query.filter(
            Student.face_encoding.is_(None),
            Student.is_active == True
        ).order_by(Student.student_id).all()
    
    @staticmethod
    def search(query):
        """
        Search students by ID, name, email, or phone
        
        Args:
            query: Search string
            
        Returns:
            List of matching Student objects
        """
        search_pattern = f'%{query}%'
        return Student.query.filter(
            db.or_(
                Student.student_id.ilike(search_pattern),
                Student.fname.ilike(search_pattern),
                Student.lname.ilike(search_pattern),
                Student.email.ilike(search_pattern),
                Student.phone.ilike(search_pattern)
            ),
            Student.is_active == True
        ).order_by(Student.student_id).all()
    
    @staticmethod
    def find_by_image_hash(image_hash):
        """
        Find student by image hash (duplicate detection)
        
        Args:
            image_hash: SHA256 hash of image
            
        Returns:
            Student object or None
        """
        return Student.query.filter_by(image_hash=image_hash).first()


# Event listeners for automatic timestamp updates
@event.listens_for(Student, 'before_update')
def receive_before_update(mapper, connection, target):
    """Update the updated_at timestamp before updating"""
    target.updated_at = datetime.utcnow()