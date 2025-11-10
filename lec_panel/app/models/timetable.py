"""
Timetable Model
Manages recurring class schedules and automatic session creation.
"""
from datetime import datetime, date, timedelta
from app import db
from sqlalchemy import Index, and_, or_


class Timetable(db.Model):
    """
    Recurring class timetable entries.
    
    Attributes:
        id: Primary key
        class_id: Foreign key to classes table
        day_of_week: 0=Sunday, 1=Monday, ..., 6=Saturday
        start_time: Session start time (HH:MM)
        end_time: Session end time (HH:MM)
        is_active: Whether this schedule is currently active
        effective_from: When this schedule starts
        effective_to: When this schedule ends (optional)
    """
    __tablename__ = 'timetable'
    
    # Day constants
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    
    DAY_NAMES = {
        SUNDAY: 'Sunday',
        MONDAY: 'Monday',
        TUESDAY: 'Tuesday',
        WEDNESDAY: 'Wednesday',
        THURSDAY: 'Thursday',
        FRIDAY: 'Friday',
        SATURDAY: 'Saturday'
    }
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Keys
    class_id = db.Column(
        db.String(50),
        db.ForeignKey('classes.class_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Schedule Details
    day_of_week = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    
    # Status and Validity
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    effective_from = db.Column(
        db.Date,
        nullable=False,
        default=date.today
    )
    effective_to = db.Column(db.Date, nullable=True)
    
    # Relationships
    class_ = db.relationship(
    'Class',
    back_populates='timetables'
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_timetable_class_day', 'class_id', 'day_of_week'),
        Index('idx_timetable_active', 'is_active'),
        Index('idx_timetable_dates', 'effective_from', 'effective_to'),
    )
    
    def __repr__(self):
        return f'<Timetable {self.class_id} - {self.day_name} {self.start_time}>'
    
    # ======================
    # Validation Methods
    # ======================
    
    @staticmethod
    def validate_day_of_week(day):
        """Validate day of week (0-6)."""
        if not isinstance(day, int) or day < 0 or day > 6:
            raise ValueError("day_of_week must be an integer between 0 (Sunday) and 6 (Saturday)")
        return True
    
    @staticmethod
    def validate_time_format(time_str):
        """Validate time format (HH:MM)."""
        try:
            datetime.strptime(time_str, '%H:%M')
            return True
        except ValueError:
            raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM (24-hour)")
    
    def validate_time_range(self):
        """Validate that end_time is after start_time."""
        start = datetime.strptime(self.start_time, '%H:%M').time()
        end = datetime.strptime(self.end_time, '%H:%M').time()
        
        if end <= start:
            raise ValueError("end_time must be after start_time")
        
        return True
    
    def validate_date_range(self):
        """Validate effective date range."""
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return True
    
    def validate(self):
        """Validate timetable entry."""
        self.validate_day_of_week(self.day_of_week)
        self.validate_time_format(self.start_time)
        self.validate_time_format(self.end_time)
        self.validate_time_range()
        self.validate_date_range()
        return True
    
    # ======================
    # Property Methods
    # ======================
    
    @property
    def day_name(self):
        """Get day name (e.g., 'Monday')."""
        return self.DAY_NAMES.get(self.day_of_week, 'Unknown')
    
    @property
    def duration_minutes(self):
        """Calculate duration in minutes."""
        start = datetime.strptime(self.start_time, '%H:%M')
        end = datetime.strptime(self.end_time, '%H:%M')
        delta = end - start
        return int(delta.total_seconds() / 60)
    
    @property
    def is_currently_effective(self):
        """Check if timetable entry is currently effective."""
        today = date.today()
        
        if not self.is_active:
            return False
        
        if today < self.effective_from:
            return False
        
        if self.effective_to and today > self.effective_to:
            return False
        
        return True
    
    @property
    def time_display(self):
        """Get formatted time display (e.g., '09:00 - 10:30')."""
        return f"{self.start_time} - {self.end_time}"
    
    def is_effective_on(self, check_date):
        """Check if timetable is effective on a specific date."""
        if not self.is_active:
            return False
        
        if check_date < self.effective_from:
            return False
        
        if self.effective_to and check_date > self.effective_to:
            return False
        
        # Check if day of week matches
        if check_date.weekday() != ((self.day_of_week - 1) % 7):
            # Convert: 0=Sunday to 6=Monday in weekday() format
            return False
        
        return True
    
    # ======================
    # Modification Methods
    # ======================
    
    def deactivate(self):
        """Deactivate this timetable entry."""
        self.is_active = False
        return self
    
    def activate(self):
        """Activate this timetable entry."""
        self.is_active = True
        return self
    
    def set_end_date(self, end_date):
        """Set the effective end date."""
        if end_date < self.effective_from:
            raise ValueError("End date must be after start date")
        self.effective_to = end_date
        return self
    
    def update_schedule(self, start_time=None, end_time=None, day_of_week=None):
        """Update schedule details."""
        if start_time:
            self.validate_time_format(start_time)
            self.start_time = start_time
        
        if end_time:
            self.validate_time_format(end_time)
            self.end_time = end_time
        
        if day_of_week is not None:
            self.validate_day_of_week(day_of_week)
            self.day_of_week = day_of_week
        
        self.validate_time_range()
        return self
    
    # ======================
    # Conflict Detection
    # ======================
    
    def check_conflicts(self, instructor_id=None):
        """
        Check for scheduling conflicts.
        
        Args:
            instructor_id: Optional instructor to check conflicts for
        
        Returns:
            list: List of conflicting timetable entries
        """
        # Base query for same day and overlapping times
        query = Timetable.query.filter(
            Timetable.id != self.id,
            Timetable.day_of_week == self.day_of_week,
            Timetable.is_active == True
        )
        
        if instructor_id:
            # Check conflicts for specific instructor
            from app.models.class_model import Class, ClassInstructor
            
            query = query.join(Class).join(ClassInstructor).filter(
                ClassInstructor.instructor_id == instructor_id
            )
        else:
            # Check conflicts for same class
            query = query.filter(Timetable.class_id == self.class_id)
        
        all_entries = query.all()
        
        # Check time overlaps
        conflicts = []
        my_start = datetime.strptime(self.start_time, '%H:%M').time()
        my_end = datetime.strptime(self.end_time, '%H:%M').time()
        
        for entry in all_entries:
            # Check date range overlap
            if self.effective_to and entry.effective_from > self.effective_to:
                continue
            if entry.effective_to and self.effective_from > entry.effective_to:
                continue
            
            # Check time overlap
            entry_start = datetime.strptime(entry.start_time, '%H:%M').time()
            entry_end = datetime.strptime(entry.end_time, '%H:%M').time()
            
            if (my_start < entry_end and my_end > entry_start):
                conflicts.append(entry)
        
        return conflicts
    
    def has_conflicts(self, instructor_id=None):
        """Check if there are any conflicts."""
        return len(self.check_conflicts(instructor_id)) > 0
    
    # ======================
    # Session Generation
    # ======================
    
    def generate_session_for_date(self, target_date):
        """
        Generate a class session for a specific date based on this timetable entry.
        
        Args:
            target_date: Date to generate session for
        
        Returns:
            ClassSession: New session object (not yet saved to DB)
        """
        from app.models.session import ClassSession
        
        if not self.is_effective_on(target_date):
            return None
        
        # Check if session already exists
        existing = ClassSession.query.filter_by(
            class_id=self.class_id,
            date=target_date.strftime('%Y-%m-%d'),
            start_time=self.start_time
        ).first()
        
        if existing:
            return None  # Session already exists
        
        # Create new session
        session = ClassSession(
            class_id=self.class_id,
            date=target_date.strftime('%Y-%m-%d'),
            start_time=self.start_time,
            end_time=self.end_time,
            status='scheduled'
        )
        
        return session
    
    @staticmethod
    def generate_sessions_for_date_range(start_date, end_date, class_id=None):
        """
        Generate sessions for all active timetables within a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            class_id: Optional class filter
        
        Returns:
            list: List of created ClassSession objects
        """
        from app.models.session import ClassSession
        
        query = Timetable.query.filter(Timetable.is_active == True)
        
        if class_id:
            query = query.filter(Timetable.class_id == class_id)
        
        timetables = query.all()
        
        created_sessions = []
        current_date = start_date
        
        while current_date <= end_date:
            for timetable in timetables:
                if timetable.is_effective_on(current_date):
                    # Check if it's not a holiday
                    if not Holiday.is_holiday(current_date):
                        session = timetable.generate_session_for_date(current_date)
                        if session:
                            created_sessions.append(session)
            
            current_date += timedelta(days=1)
        
        return created_sessions
    
    # ======================
    # Query Helper Methods
    # ======================
    
    @staticmethod
    def get_by_class(class_id, active_only=True):
        """Get all timetable entries for a class."""
        query = Timetable.query.filter_by(class_id=class_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Timetable.day_of_week, Timetable.start_time).all()
    
    @staticmethod
    def get_by_day(day_of_week, active_only=True):
        """Get all timetable entries for a specific day."""
        query = Timetable.query.filter_by(day_of_week=day_of_week)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.order_by(Timetable.start_time).all()
    
    @staticmethod
    def get_today_schedule(class_id=None):
        """Get today's timetable entries."""
        today = date.today()
        day_of_week = (today.weekday() + 1) % 7  # Convert to 0=Sunday
        
        query = Timetable.query.filter(
            Timetable.day_of_week == day_of_week,
            Timetable.is_active == True,
            Timetable.effective_from <= today,
            or_(Timetable.effective_to.is_(None), Timetable.effective_to >= today)
        )
        
        if class_id:
            query = query.filter_by(class_id=class_id)
        
        return query.order_by(Timetable.start_time).all()
    
    @staticmethod
    def get_instructor_schedule(instructor_id, day_of_week=None):
        """Get timetable for a specific instructor."""
        from app.models.class_model import Class, ClassInstructor
        
        query = db.session.query(Timetable).join(
            Class, Timetable.class_id == Class.class_id
        ).join(
            ClassInstructor, Class.class_id == ClassInstructor.class_id
        ).filter(
            ClassInstructor.instructor_id == instructor_id,
            Timetable.is_active == True
        )
        
        if day_of_week is not None:
            query = query.filter(Timetable.day_of_week == day_of_week)
        
        return query.order_by(
            Timetable.day_of_week,
            Timetable.start_time
        ).all()
    
    @staticmethod
    def get_week_schedule(class_id):
        """Get full week schedule for a class."""
        entries = Timetable.get_by_class(class_id, active_only=True)
        
        # Organize by day
        week_schedule = {day: [] for day in range(7)}
        
        for entry in entries:
            week_schedule[entry.day_of_week].append(entry)
        
        return week_schedule
    
    # ======================
    # Bulk Operations
    # ======================
    
    @staticmethod
    def bulk_create(class_id, schedules):
        """
        Bulk create timetable entries.
        
        Args:
            class_id: Class ID
            schedules: List of dicts with keys: day_of_week, start_time, end_time
        
        Returns:
            list: Created Timetable objects
        """
        entries = []
        
        for schedule in schedules:
            entry = Timetable(
                class_id=class_id,
                day_of_week=schedule['day_of_week'],
                start_time=schedule['start_time'],
                end_time=schedule['end_time'],
                effective_from=schedule.get('effective_from', date.today())
            )
            entry.validate()
            entries.append(entry)
        
        return entries
    
    @staticmethod
    def deactivate_all_for_class(class_id):
        """Deactivate all timetable entries for a class."""
        Timetable.query.filter_by(class_id=class_id).update({'is_active': False})
        return True
    
    # ======================
    # Serialization
    # ======================
    
    def to_dict(self, include_relations=False):
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'class_id': self.class_id,
            'day_of_week': self.day_of_week,
            'day_name': self.day_name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'time_display': self.time_display,
            'duration_minutes': self.duration_minutes,
            'is_active': self.is_active,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'is_currently_effective': self.is_currently_effective
        }
        
        if include_relations and self.class_obj:
            data['class'] = {
                'class_id': self.class_obj.class_id,
                'class_name': self.class_obj.class_name,
                'course_code': self.class_obj.course_code
            }
        
        return data


class Holiday(db.Model):
    """
    Holiday calendar to skip session generation.
    
    Attributes:
        id: Primary key
        name: Holiday name
        date: Holiday date
        description: Optional description
        is_recurring: Whether holiday recurs yearly
    """
    __tablename__ = 'holidays'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Holiday {self.name} - {self.date}>'
    
    @staticmethod
    def is_holiday(check_date):
        """Check if a date is a holiday."""
        # Check exact date match
        if Holiday.query.filter_by(date=check_date).first():
            return True
        
        # Check recurring holidays (same month and day)
        recurring = Holiday.query.filter_by(is_recurring=True).all()
        for holiday in recurring:
            if holiday.date.month == check_date.month and holiday.date.day == check_date.day:
                return True
        
        return False
    
    @staticmethod
    def get_upcoming_holidays(days=30):
        """Get upcoming holidays within specified days."""
        from_date = date.today()
        to_date = from_date + timedelta(days=days)
        
        return Holiday.query.filter(
            Holiday.date >= from_date,
            Holiday.date <= to_date
        ).order_by(Holiday.date).all()
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date.isoformat(),
            'description': self.description,
            'is_recurring': self.is_recurring
        }