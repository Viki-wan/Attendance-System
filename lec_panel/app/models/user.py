"""
Instructor (User) Model
Handles instructor authentication and profile management
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from config.constants import USER_TYPES


class Instructor(UserMixin, db.Model):
    """
    Instructor model for authentication and profile management.
    Implements Flask-Login's UserMixin for session management.
    """
    __tablename__ = 'instructors'
    
    # Primary key
    instructor_id = db.Column(db.String(50), primary_key=True)
    
    # Profile information
    instructor_name = db.Column(db.String(200), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    faculty = db.Column(db.String(100), nullable=True)
    
    # Authentication
    password = db.Column(db.String(255), nullable=False)
    
    # Account status
    is_active = db.Column(db.Integer, default=1)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships (based on schema)
    # Class assignments through junction table
    class_instructors = db.relationship(
        'ClassInstructor', 
        back_populates='instructor', 
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    # Course assignments through junction table
    instructor_courses = db.relationship(
        'InstructorCourse',
        back_populates='instructor',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    # Sessions created by this instructor
    sessions = db.relationship(
        'ClassSession',
        foreign_keys='ClassSession.created_by',
        back_populates='instructor',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    # Attendance records marked by this instructor
    attendance_records = db.relationship(
        'Attendance',
        foreign_keys='Attendance.marked_by',
        lazy='dynamic',
        overlaps="marker"
    )
    
    # Session dismissals
    session_dismissals = db.relationship(
        'SessionDismissal',
        back_populates='instructor',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    
    # Preferences (one-to-one)
    preferences = db.relationship(
        'LecturerPreference',
        back_populates='instructor',
        uselist=False,
        cascade='all, delete-orphan'
    )
    
    # System metrics for this instructor
    metrics = db.relationship(
        'SystemMetric',
        back_populates='instructor',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    # Activity logs
    activity_logs = db.relationship(
        'ActivityLog',
        foreign_keys='ActivityLog.user_id',
        primaryjoin='and_(ActivityLog.user_id==Instructor.instructor_id, ActivityLog.user_type=="instructor")',
        lazy='dynamic',
        overlaps="logs"
    )
    
    # Notifications
    notifications = db.relationship(
        'Notification',
        foreign_keys='Notification.user_id',
        primaryjoin='and_(Notification.user_id==Instructor.instructor_id, Notification.user_type=="instructor")',
        lazy='dynamic',
        cascade='all, delete-orphan',
        overlaps="notifications"
    )
    
    def __repr__(self):
        return f'<Instructor {self.instructor_id}: {self.instructor_name}>'
    
    # Flask-Login required methods
    def get_id(self):
        """Return the instructor_id for session management"""
        return str(self.instructor_id)
    
    @property
    def is_authenticated(self):
        """Always return True for authenticated users"""
        return True
    
    @property
    def is_anonymous(self):
        """Instructors are never anonymous"""
        return False
    
    def is_active_user(self):
        """Check if account is active"""
        return bool(self.is_active)
    
    # Password methods
    def set_password(self, password):
        """
        Hash and set the instructor's password.
        
        Args:
            password (str): Plain text password
        """
        self.password = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """
        Verify the provided password against the stored hash.
        
        Args:
            password (str): Plain text password to verify
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self.password, password)
    
    def is_first_time_login(self):
        """
        Check if this is the first-time login.
        True if password is still default (instructor_id) and never logged in.
        
        Returns:
            bool: True if first-time login required
        """
        return self.check_password(self.instructor_id) and self.last_login is None
    
    def requires_password_change(self):
        """
        Check if password change is required.
        Alias for is_first_time_login for better semantic clarity.
        
        Returns:
            bool: True if password change required
        """
        return self.is_first_time_login()
    
    def update_last_login(self):
        """Update the last_login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def deactivate(self):
        """Deactivate the instructor account"""
        self.is_active = 0
        db.session.commit()
    
    def activate(self):
        """Activate the instructor account"""
        self.is_active = 1
        db.session.commit()
    
    # Profile methods
    def update_profile(self, **kwargs):
        """
        Update instructor profile fields.
        
        Args:
            **kwargs: Field names and values to update
        """
        allowed_fields = ['instructor_name', 'email', 'phone', 'faculty']
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(self, field, value)
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    def change_password(self, old_password, new_password):
        """
        Change instructor password with verification.
        
        Args:
            old_password (str): Current password for verification
            new_password (str): New password to set
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.check_password(old_password):
            return False, "Current password is incorrect"
        
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters"
        
        self.set_password(new_password)
        self.updated_at = datetime.utcnow()
        db.session.commit()
        
        return True, "Password changed successfully"
    
    # Authorization helpers
    def owns_session(self, session_id):
        """
        Check if instructor owns/teaches a specific session.
        
        Args:
            session_id (int): Session ID to check
            
        Returns:
            bool: True if instructor owns the session
        """
        return self.sessions.filter_by(session_id=session_id).first() is not None
    
    def owns_class(self, class_id):
        """
        Check if instructor is assigned to a specific class.
        
        Args:
            class_id (str): Class ID to check
            
        Returns:
            bool: True if instructor teaches the class
        """
        return self.class_instructors.filter_by(class_id=class_id).first() is not None
    
    def teaches_course(self, course_code):
        """
        Check if instructor teaches a specific course.
        
        Args:
            course_code (str): Course code to check
            
        Returns:
            bool: True if instructor teaches the course
        """
        return self.instructor_courses.filter_by(course_code=course_code).first() is not None
    
    def get_user_type(self):
        """Return user type for activity logging"""
        return USER_TYPES.get('INSTRUCTOR', 'instructor')
    
    def get_assigned_classes(self, active_only=True):
        """
        Get all classes assigned to this instructor.
        
        Args:
            active_only (bool): Only return active classes
            
        Returns:
            list: List of Class objects
        """
        from app.models.class_model import Class, ClassInstructor
        
        query = db.session.query(Class).join(
            ClassInstructor, ClassInstructor.class_id == Class.class_id
        ).filter(ClassInstructor.instructor_id == self.instructor_id)
        
        if active_only:
            query = query.filter(Class.is_active == True)
        
        return query.all()
    
    def get_assigned_courses(self, semester=None, year=None):
        """
        Get all courses assigned to this instructor.
        
        Args:
            semester (str): Filter by semester
            year (int): Filter by year
            
        Returns:
            list: List of Course objects
        """
        from app.models.course import Course
        query = db.session.query(Course).join(
            'instructor_courses'
        ).filter_by(instructor_id=self.instructor_id)
        
        if semester:
            query = query.filter_by(semester=semester)
        if year:
            query = query.filter_by(year=year)
        
        return query.all()
    
    def get_upcoming_sessions(self, limit=5):
        """
        Get upcoming sessions for this instructor.
        
        Args:
            limit (int): Maximum number of sessions to return
            
        Returns:
            list: List of ClassSession objects
        """
        from datetime import date
        from app.models.session import ClassSession
        
        return self.sessions.filter(
            ClassSession.date >= date.today().isoformat(),
            ClassSession.status.in_(['scheduled', 'ongoing'])
        ).order_by(
            ClassSession.date.asc(),
            ClassSession.start_time.asc()
        ).limit(limit).all()
    
    def get_recent_sessions(self, limit=10):
        """
        Get recent sessions for this instructor.
        
        Args:
            limit (int): Maximum number of sessions to return
            
        Returns:
            list: List of ClassSession objects
        """
        from app.models.session import ClassSession
        
        return self.sessions.order_by(
            ClassSession.date.desc(),
            ClassSession.start_time.desc()
        ).limit(limit).all()
    
    def get_unread_notifications(self):
        """
        Get unread notifications for this instructor.
        
        Returns:
            list: List of Notification objects
        """
        return self.notifications.filter_by(is_read=0).order_by(
            'created_at desc'
        ).all()
    
    def get_preferences(self):
        """
        Get or create preferences for this instructor.
        
        Returns:
            LecturerPreference: Preferences object
        """
        if not self.preferences:
            from app.models.lecturer_preferences import LecturerPreference
            prefs = LecturerPreference(instructor_id=self.instructor_id)
            db.session.add(prefs)
            db.session.commit()
        
        return self.preferences
    
    # Performance metrics helper methods
    def get_performance_metrics(self, days=30):
        """
        Get performance metrics for this instructor over specified days.
        
        Args:
            days (int): Number of days to look back
            
        Returns:
            dict: Performance metrics summary
        """
        from datetime import timedelta
        from app.models.system_metric import SystemMetric
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get average response times
        avg_response = SystemMetric.get_average_metric(
            'api_response_time',
            start_date=cutoff_date,
            instructor_id=self.instructor_id
        )
        
        # Get session metrics
        avg_attendance_rate = SystemMetric.get_average_metric(
            'attendance_rate',
            start_date=cutoff_date,
            instructor_id=self.instructor_id
        )
        
        # Get total sessions conducted
        total_sessions = self.sessions.filter(
            ClassSession.created_at >= cutoff_date,
            ClassSession.status == 'completed'
        ).count()
        
        return {
            'period_days': days,
            'total_sessions': total_sessions,
            'avg_response_time_ms': avg_response or 0,
            'avg_attendance_rate': avg_attendance_rate or 0,
            'calculated_at': datetime.utcnow().isoformat()
        }
    
    # Query methods
    @staticmethod
    def get_by_email(email):
        """
        Fetch instructor by email.
        
        Args:
            email (str): Email address
            
        Returns:
            Instructor: Instructor object or None
        """
        return Instructor.query.filter_by(email=email).first()
    
    @staticmethod
    def get_by_phone(phone):
        """
        Fetch instructor by phone number.
        
        Args:
            phone (str): Phone number
            
        Returns:
            Instructor: Instructor object or None
        """
        return Instructor.query.filter_by(phone=phone).first()
    
    @staticmethod
    def get_active_instructors():
        """
        Fetch all active instructors.
        
        Returns:
            list: List of active Instructor objects
        """
        return Instructor.query.filter_by(is_active=1).all()
    
    @staticmethod
    def get_by_faculty(faculty):
        """
        Fetch instructors by faculty.
        
        Args:
            faculty (str): Faculty name
            
        Returns:
            list: List of Instructor objects
        """
        return Instructor.query.filter_by(faculty=faculty, is_active=1).all()
    
    @staticmethod
    def search(query):
        """
        Search instructors by name, email, or phone.
        
        Args:
            query (str): Search query
            
        Returns:
            list: List of matching Instructor objects
        """
        search_pattern = f"%{query}%"
        return Instructor.query.filter(
            db.or_(
                Instructor.instructor_name.ilike(search_pattern),
                Instructor.email.ilike(search_pattern),
                Instructor.phone.ilike(search_pattern)
            )
        ).filter_by(is_active=1).all()
    
    # Serialization
    def to_dict(self, include_sensitive=False):
        """
        Convert instructor to dictionary.
        
        Args:
            include_sensitive (bool): Include sensitive fields
            
        Returns:
            dict: Instructor data
        """
        data = {
            'instructor_id': self.instructor_id,
            'instructor_name': self.instructor_name,
            'email': self.email,
            'phone': self.phone,
            'faculty': self.faculty,
            'is_active': bool(self.is_active),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        
        return data