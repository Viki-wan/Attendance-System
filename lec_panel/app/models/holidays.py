"""
Holidays Model
Manages public holidays and non-teaching days
"""
from datetime import datetime, date
from app import db


class Holiday(db.Model):
    __tablename__ = 'holidays'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)
    is_recurring = db.Column(db.Integer, default=0)  # 1 = repeats annually
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Holiday {self.name} - {self.date}>'
    
    @classmethod
    def create_holiday(cls, name, date, description=None, is_recurring=False):
        """
        Create a new holiday
        
        Args:
            name: Name of the holiday
            date: Date of the holiday
            description: Optional description
            is_recurring: True if holiday repeats annually
        """
        holiday = cls(
            name=name,
            date=date,
            description=description,
            is_recurring=1 if is_recurring else 0
        )
        db.session.add(holiday)
        db.session.commit()
        return holiday
    
    @classmethod
    def is_holiday(cls, check_date):
        """
        Check if a given date is a holiday
        
        Args:
            check_date: Date to check
        
        Returns:
            Holiday object if date is a holiday, None otherwise
        """
        # Check exact date match
        holiday = cls.query.filter_by(date=check_date).first()
        if holiday:
            return holiday
        
        # Check recurring holidays (same month and day)
        recurring_holidays = cls.query.filter_by(is_recurring=1).all()
        for holiday in recurring_holidays:
            if holiday.date.month == check_date.month and holiday.date.day == check_date.day:
                return holiday
        
        return None
    
    @classmethod
    def get_upcoming_holidays(cls, days=30):
        """Get holidays in the next N days"""
        today = date.today()
        end_date = today + timedelta(days=days)
        
        # Get holidays in date range
        holidays = cls.query.filter(
            cls.date >= today,
            cls.date <= end_date
        ).order_by(cls.date).all()
        
        # Add applicable recurring holidays
        recurring = cls.query.filter_by(is_recurring=1).all()
        for holiday in recurring:
            # Check if this recurring holiday falls in the range
            current_year_date = date(today.year, holiday.date.month, holiday.date.day)
            if today <= current_year_date <= end_date:
                # Create a temporary holiday object for this year
                temp_holiday = Holiday(
                    id=holiday.id,
                    name=holiday.name,
                    date=current_year_date,
                    description=holiday.description,
                    is_recurring=1
                )
                if not any(h.date == current_year_date and h.name == holiday.name for h in holidays):
                    holidays.append(temp_holiday)
        
        return sorted(holidays, key=lambda x: x.date)
    
    @classmethod
    def get_holidays_between(cls, start_date, end_date):
        """
        Get all holidays between two dates
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            List of Holiday objects
        """
        # Get exact date matches
        holidays = cls.query.filter(
            cls.date >= start_date,
            cls.date <= end_date
        ).all()
        
        # Add recurring holidays that fall in the range
        recurring = cls.query.filter_by(is_recurring=1).all()
        years = range(start_date.year, end_date.year + 1)
        
        for holiday in recurring:
            for year in years:
                try:
                    current_year_date = date(year, holiday.date.month, holiday.date.day)
                    if start_date <= current_year_date <= end_date:
                        # Check if we don't already have this date
                        if not any(h.date == current_year_date and h.name == holiday.name for h in holidays):
                            # Create temporary holiday for this occurrence
                            temp_holiday = Holiday(
                                id=holiday.id,
                                name=holiday.name,
                                date=current_year_date,
                                description=holiday.description,
                                is_recurring=1
                            )
                            holidays.append(temp_holiday)
                except ValueError:
                    # Handle leap year issues (Feb 29)
                    continue
        
        return sorted(holidays, key=lambda x: x.date)
    
    @classmethod
    def get_all_holidays(cls, year=None):
        """Get all holidays, optionally filtered by year"""
        if year:
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            return cls.get_holidays_between(start_date, end_date)
        else:
            return cls.query.order_by(cls.date).all()
    
    @classmethod
    def bulk_create(cls, holidays_list):
        """
        Create multiple holidays at once
        
        Args:
            holidays_list: List of dictionaries with holiday data
                         [{'name': 'Name', 'date': date_obj, 'description': '...', 'is_recurring': True}, ...]
        """
        for holiday_data in holidays_list:
            holiday = cls(
                name=holiday_data['name'],
                date=holiday_data['date'],
                description=holiday_data.get('description'),
                is_recurring=1 if holiday_data.get('is_recurring') else 0
            )
            db.session.add(holiday)
        
        db.session.commit()
    
    @classmethod
    def delete_holiday(cls, holiday_id):
        """Delete a holiday"""
        holiday = cls.query.get(holiday_id)
        if holiday:
            db.session.delete(holiday)
            db.session.commit()
            return True
        return False
    
    @classmethod
    def update_holiday(cls, holiday_id, **kwargs):
        """Update holiday details"""
        holiday = cls.query.get(holiday_id)
        if not holiday:
            return None
        
        for key, value in kwargs.items():
            if hasattr(holiday, key):
                if key == 'is_recurring':
                    value = 1 if value else 0
                setattr(holiday, key, value)
        
        db.session.commit()
        return holiday
    
    @classmethod
    def get_working_days_between(cls, start_date, end_date):
        """
        Calculate number of working days between two dates (excluding weekends and holidays)
        
        Args:
            start_date: Start date
            end_date: End date
        
        Returns:
            Number of working days
        """
        from datetime import timedelta
        
        holidays = cls.get_holidays_between(start_date, end_date)
        holiday_dates = {h.date for h in holidays}
        
        working_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Check if it's a weekday and not a holiday
            if current_date.weekday() < 5 and current_date not in holiday_dates:
                working_days += 1
            current_date += timedelta(days=1)
        
        return working_days
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'is_recurring': bool(self.is_recurring),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# Import timedelta at module level
from datetime import timedelta