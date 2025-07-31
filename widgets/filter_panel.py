from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QComboBox, QDateEdit, QPushButton, QFrame,
                           QSizePolicy, QSpacerItem)
from PyQt5.QtCore import QDate, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from admin.db_service import DatabaseService

class FilterPanel(QWidget):
    """
    A reusable filter panel for attendance reports.
    
    This widget provides date range selection, course filtering,
    instructor filtering, and other common filters needed across reports.
    """
    
    # Signal emitted when any filter changes
    filter_changed = pyqtSignal()
    
    def __init__(self, db_service, show_course=True, show_class=True, show_date_range=True, compact_mode=False):
        super().__init__()
        # Remove redundant initialization
        self.db_service = DatabaseService()
        self.db_service = db_service

        self.show_course = show_course
        self.show_class = show_class
        self.show_date_range = show_date_range
        self.compact_mode = compact_mode
        
        # Set default date range (current semester)
        self.start_date = QDate.currentDate().addDays(-90)  # ~ 3 months ago
        self.end_date = QDate.currentDate()
        
        # Initialize UI
        self.init_ui()
        
        # Load filter data
        self.load_filter_data() 

    def init_ui(self):
        """Initialize the UI components"""
        # Create main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Frame for nicer appearance
        filter_frame = QFrame()
        filter_frame.setFrameShape(QFrame.StyledPanel)
        filter_frame.setFrameShadow(QFrame.Raised)
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(5, 5, 5, 5)
    
        if self.show_date_range:
            # Date range selection
            date_layout = QVBoxLayout()
            
            # Start date
            start_date_layout = QHBoxLayout()
            if not self.compact_mode:
                start_date_label = QLabel("From:")
                start_date_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
                start_date_layout.addWidget(start_date_label)
            self.start_date_edit = QDateEdit(self.start_date)
            self.start_date_edit.setCalendarPopup(True)
            self.start_date_edit.dateChanged.connect(self.on_date_changed)
            if self.compact_mode:
                self.start_date_edit.setDisplayFormat("MMM d, yyyy")
                self.start_date_edit.setPlaceholderText("From Date")
            
            start_date_layout.addWidget(self.start_date_edit)
            date_layout.addLayout(start_date_layout)
            
            # End date
            end_date_layout = QHBoxLayout()
            if not self.compact_mode:
                end_date_label = QLabel("To:")
                end_date_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
                end_date_layout.addWidget(end_date_label)
            self.end_date_edit = QDateEdit(self.end_date)
            self.end_date_edit.setCalendarPopup(True)
            self.end_date_edit.dateChanged.connect(self.on_date_changed)
            if self.compact_mode:
                self.end_date_edit.setDisplayFormat("MMM d, yyyy")
                self.end_date_edit.setPlaceholderText("To Date")
            
            end_date_layout.addWidget(self.end_date_edit)
            date_layout.addLayout(end_date_layout)
            
            filter_layout.addLayout(date_layout)
            
            # Vertical separator
            separator = QFrame()
            separator.setFrameShape(QFrame.VLine)
            separator.setFrameShadow(QFrame.Sunken)
            filter_layout.addWidget(separator)
            
        if self.show_course:
            # Course selection
            course_layout = QVBoxLayout()
            if not self.compact_mode:
                course_label = QLabel("Course:")
                course_layout.addWidget(course_label)
            self.course_combo = QComboBox()
            self.course_combo.setMinimumWidth(150)
            # Connect course combo to update instructor filter
            self.course_combo.currentIndexChanged.connect(self.on_course_changed)
            if self.compact_mode:
                self.course_combo.setPlaceholderText("Select Course")
            
            course_layout.addWidget(self.course_combo)
            filter_layout.addLayout(course_layout)
        
        # Instructor selection
        instructor_layout = QVBoxLayout()
        if not self.compact_mode:
            instructor_label = QLabel("Instructor:")
            instructor_layout.addWidget(instructor_label)
        self.instructor_combo = QComboBox()
        self.instructor_combo.setMinimumWidth(150)
        # Connect instructor combo to update class filter
        self.instructor_combo.currentIndexChanged.connect(self.on_instructor_changed)
        if self.compact_mode:
            self.instructor_combo.setPlaceholderText("Select Instructor")
        
        instructor_layout.addWidget(self.instructor_combo)
        filter_layout.addLayout(instructor_layout)

        # Class selection (if enabled)
        if hasattr(self, 'show_class') and self.show_class:
            class_layout = QVBoxLayout()
            if not self.compact_mode:
                class_label = QLabel("Class:")
                class_layout.addWidget(class_label)
            self.class_combo = QComboBox()
            self.class_combo.setMinimumWidth(150)
            self.class_combo.currentIndexChanged.connect(self.on_filter_changed)
            if self.compact_mode:
                self.class_combo.setPlaceholderText("Select Class")
            
            class_layout.addWidget(self.class_combo)
            filter_layout.addLayout(class_layout)
        
        # Year of study selection
        year_layout = QVBoxLayout()
        if not self.compact_mode:
            year_label = QLabel("Year of Study:")
            year_layout.addWidget(year_label)
        self.year_combo = QComboBox()
        self.year_combo.addItems(["All Years", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"])
        self.year_combo.currentIndexChanged.connect(self.on_year_changed)
        if self.compact_mode:
            self.year_combo.setPlaceholderText("Select Year")
        
        year_layout.addWidget(self.year_combo)
        filter_layout.addLayout(year_layout)
        
        # Semester selection
        semester_layout = QVBoxLayout()
        if not self.compact_mode:
            semester_label = QLabel("Semester:")
            semester_layout.addWidget(semester_label)
        self.semester_combo = QComboBox()
        self.semester_combo.addItems(["All Semesters", "Semester 1", "Semester 2", "Summer"])
        self.semester_combo.currentIndexChanged.connect(self.on_filter_changed)
        if self.compact_mode:
            self.semester_combo.setPlaceholderText("Select Semester")
        
        semester_layout.addWidget(self.semester_combo)
        filter_layout.addLayout(semester_layout)
        
        # Quick date presets
        preset_layout = QVBoxLayout()
        if not self.compact_mode:
            preset_label = QLabel("Quick Select:")
            preset_layout.addWidget(preset_label)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "Custom Range", 
            "Today", 
            "This Week", 
            "This Month", 
            "This Semester",
            "This Year",
            "Last Week",
            "Last Month"
        ])
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        if self.compact_mode:
            self.preset_combo.setPlaceholderText("Date Range")
        
        preset_layout.addWidget(self.preset_combo)
        filter_layout.addLayout(preset_layout)
        
        # Reset button
        reset_layout = QVBoxLayout()
        if not self.compact_mode:
            reset_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_filters)
        reset_layout.addWidget(self.reset_button)
        filter_layout.addLayout(reset_layout)
        
        main_layout.addWidget(filter_frame)        
    def get_class_id(self):
        """
        Get the selected class ID (if class selection is enabled)
        
        Returns:
            int: The selected class ID or None for "All Classes"
        """
        if hasattr(self, 'class_combo'):
            return self.class_combo.currentData()
        return None
    
    
    def get_single_date(self):
        """
        Get a single date for reports that only need one date
        
        Returns:
            QDate: For date range panels, returns the start date.
                For single date panels, returns the selected date.
        """
        if hasattr(self, 'start_date_edit'):
            return self.start_date_edit.date()
        elif hasattr(self, 'date_edit'):
            return self.date_edit.date()
        else:
            # Default to current date if no date fields exist
            return QDate.currentDate()
        
    def set_default_dates(self, start_date, end_date):
        """
        Set the date range pickers to the specified dates
        
        Args:
            start_date (QDate): The start date to set
            end_date (QDate): The end date to set
        """
        if self.show_date_range:
            # Block signals to prevent triggering filter_changed multiple times
            self.start_date_edit.blockSignals(True)
            self.end_date_edit.blockSignals(True)
            
            # Set the dates
            self.start_date_edit.setDate(start_date)
            self.end_date_edit.setDate(end_date)
            
            # Update stored dates
            self.start_date = start_date
            self.end_date = end_date
            
            # Unblock signals
            self.start_date_edit.blockSignals(False)
            self.end_date_edit.blockSignals(False)

    def set_date_range(self, start_date, end_date):
        """
        Set the date range pickers to the specified dates
        
        Args:
            start_date (QDate): The start date to set
            end_date (QDate): The end date to set
        """
        if self.show_date_range:
            # Block signals to prevent triggering filter_changed multiple times
            self.start_date_edit.blockSignals(True)
            self.end_date_edit.blockSignals(True)
            
            # Set the dates
            self.start_date_edit.setDate(start_date)
            self.end_date_edit.setDate(end_date)
            
            # Update stored dates
            self.start_date = start_date
            self.end_date = end_date
            
            # Unblock signals
            self.start_date_edit.blockSignals(False)
            self.end_date_edit.blockSignals(False)

    def get_current_filters(self):
        """
        Get a dictionary of all current filter values
        
        Returns:
            dict: Dictionary containing all filter values
        """
        filters = {
            'start_date': self.get_start_date(),
            'end_date': self.get_end_date(),
            'instructor_id': self.get_instructor_id(),
            'year': self.get_year_of_study(),
            'semester': self.get_semester()
        }
        
        # Only add these if they're shown in the UI
        if self.show_course:
            filters['course_code'] = self.get_course_code()
        
        if self.show_class:
            filters['class_id'] = self.get_class_id()
        
        return filters

    def set_filters(self, start_date=None, end_date=None, course_code=None, 
                    instructor_id=None, class_id=None, year=None, semester=None):
        """
       
        """
        # Block signals to prevent multiple updates
        self.blockSignals(True)
        
        # Set dates if provided
        if start_date and end_date and self.show_date_range:
            self.start_date_edit.setDate(start_date)
            self.end_date_edit.setDate(end_date)
            self.start_date = start_date
            self.end_date = end_date
        
        # Set course if provided and shown
        if course_code is not None and self.show_course:
            index = self.course_combo.findData(course_code)
            if index >= 0:
                self.course_combo.setCurrentIndex(index)
        
        # Set instructor if provided
        if instructor_id is not None:
            index = self.instructor_combo.findData(instructor_id)
            if index >= 0:
                self.instructor_combo.setCurrentIndex(index)
        
        # Set class if provided and shown
        if class_id is not None and self.show_class:
            if hasattr(self, 'class_combo'):
                index = self.class_combo.findData(class_id)
                if index >= 0:
                    self.class_combo.setCurrentIndex(index)
        
        # Set year if provided
        if year is not None:
            index = year if year > 0 else 0
            self.year_combo.setCurrentIndex(min(index, self.year_combo.count() - 1))
        
        # Set semester if provided
        if semester is not None:
            if semester == "Semester 1":
                self.semester_combo.setCurrentIndex(1)
            elif semester == "Semester 2":
                self.semester_combo.setCurrentIndex(2)
            elif semester == "Summer":
                self.semester_combo.setCurrentIndex(3)
            else:
                self.semester_combo.setCurrentIndex(0)
        
        # Unblock signals
        self.blockSignals(False)
        
        # Emit signal for one update
        self.filter_changed.emit()

    def load_filter_data(self):
        """Load data for filter dropdowns from database"""
        # Block signals to prevent multiple filter_changed emissions
        if self.show_course:
            self.course_combo.blockSignals(True)
            # Clear existing items
            self.course_combo.clear()
            # Add default "All" options
            self.course_combo.addItem("All Courses", None)
            # Load courses
            courses = self.db_service.get_courses()
            for course in courses:
                self.course_combo.addItem(f"{course['course_code']} - {course['course_name']}", course['course_code'])
            self.course_combo.blockSignals(False)
        
        # Load all instructors (initially)
        self.load_instructors()
        
        # If class filter is enabled, load all classes (initially)
        if hasattr(self, 'show_class') and self.show_class and hasattr(self, 'class_combo'):
            self.load_classes()
    
    def load_instructors(self, course_code=None):
        """
        Load instructors for the filter dropdown, optionally filtered by course
        
        Args:
            course_code (str, optional): Course code to filter instructors by
        """
        self.instructor_combo.blockSignals(True)
        self.instructor_combo.clear()
        self.instructor_combo.addItem("All Instructors", None)
        
        if course_code:
            # Get instructors for the specific course
            instructors = self.db_service.get_instructors_by_course(course_code)
        else:
            # Get all instructors
            instructors = self.db_service.get_instructors()
            
        for instructor in instructors:
            self.instructor_combo.addItem(
                f"{instructor['first_name']} {instructor['last_name']}", 
                instructor['instructor_id']
            )
        
        self.instructor_combo.blockSignals(False)
    
    def load_classes(self, instructor_id=None, year=None):
        """
        Load classes for the filter dropdown, optionally filtered by instructor and year
        
        Args:
            instructor_id (int, optional): Instructor ID to filter classes by
            year (int, optional): Year of study to filter classes by
        """
        if hasattr(self, 'class_combo'):
            self.class_combo.blockSignals(True)
            self.class_combo.clear()
            self.class_combo.addItem("All Classes", None)
            
            # Get classes with filters
            if instructor_id or year:
                # Get filtered classes
                classes = self.db_service.get_filtered_classes(instructor_id, year)
            else:
                # Get all classes
                classes = self.db_service.get_classes()
                
            for class_info in classes:
                self.class_combo.addItem(f"{class_info['class_id']} - {class_info['class_name']}", class_info['class_id'])
            
            self.class_combo.blockSignals(False) 

    def on_year_changed(self, index):
        """
        Handle year of study selection change - update classes filter
        """
        year = None
        if index > 0:  # If not "All Years"
            year = index
        
        # Get current instructor filter
        instructor_id = self.instructor_combo.currentData()
        
        # Reload classes based on the selected year and instructor
        if hasattr(self, 'class_combo'):
            self.load_classes(instructor_id, year)
        
        # Emit filter changed signal
        self.filter_changed.emit()   

    def on_course_changed(self, index):
        """
        Handle course selection change - update instructors filter
        """
        course_code = self.course_combo.currentData()
        # Reload instructors based on the selected course
        self.load_instructors(course_code)
        # Reset class filter when course changes
        if hasattr(self, 'class_combo'):
            self.load_classes()
        # Emit filter changed signal
        self.filter_changed.emit()
    
    def on_instructor_changed(self, index):
        """
        Handle instructor selection change - update classes filter
        """
        instructor_id = self.instructor_combo.currentData()
        
        # Get current year filter
        year = None
        year_index = self.year_combo.currentIndex()
        if year_index > 0:  # If not "All Years"
            year = year_index
        
        # Reload classes based on the selected instructor and year
        if hasattr(self, 'class_combo'):
            self.load_classes(instructor_id, year)
            
        # Emit filter changed signal
        self.filter_changed.emit()        
    def on_date_changed(self):
        """Handle date range changes"""
        # Ensure end date is not before start date
        start_date = self.start_date_edit.date()
        end_date = self.end_date_edit.date()
        
        if end_date < start_date:
            self.end_date_edit.setDate(start_date)
        
        # Update stored dates
        self.start_date = self.start_date_edit.date()
        self.end_date = self.end_date_edit.date()
        
        # Reset preset to "Custom Range"
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)
        
        # Emit filter changed signal
        self.filter_changed.emit()
        
    def on_filter_changed(self):
        """Handle non-date filter changes"""
        # Emit filter changed signal
        self.filter_changed.emit()
        
    def on_preset_changed(self, index):
        """Handle date preset selection"""
        if index == 0:  # Custom Range
            return
            
        # Block date edit signals to prevent double filter_changed emission
        self.start_date_edit.blockSignals(True)
        self.end_date_edit.blockSignals(True)
        
        today = QDate.currentDate()
        
        if index == 1:  # Today
            self.start_date_edit.setDate(today)
            self.end_date_edit.setDate(today)
        elif index == 2:  # This Week
            day_of_week = today.dayOfWeek()
            week_start = today.addDays(-(day_of_week - 1))
            self.start_date_edit.setDate(week_start)
            self.end_date_edit.setDate(today)
        elif index == 3:  # This Month
            month_start = QDate(today.year(), today.month(), 1)
            self.start_date_edit.setDate(month_start)
            self.end_date_edit.setDate(today)
        elif index == 4:  # This Semester
            # Approximate semester dates
            year = today.year()
            month = today.month()
            
            if month >= 1 and month <= 5:
                # Spring semester (January - May)
                self.start_date_edit.setDate(QDate(year, 1, 15))
                self.end_date_edit.setDate(QDate(year, 5, 15))
            elif month >= 8 and month <= 12:
                # Fall semester (August - December)
                self.start_date_edit.setDate(QDate(year, 8, 15))
                self.end_date_edit.setDate(QDate(year, 12, 15))
            else:
                # Summer term (June - July) or other periods
                self.start_date_edit.setDate(QDate(year, 6, 1))
                self.end_date_edit.setDate(QDate(year, 7, 31))
        elif index == 5:  # This Year
            year_start = QDate(today.year(), 1, 1)
            self.start_date_edit.setDate(year_start)
            self.end_date_edit.setDate(today)
        elif index == 6:  # Last Week
            last_week_end = today.addDays(-today.dayOfWeek())
            last_week_start = last_week_end.addDays(-6)
            self.start_date_edit.setDate(last_week_start)
            self.end_date_edit.setDate(last_week_end)
        elif index == 7:  # Last Month
            last_month = today.addMonths(-1)
            month_start = QDate(last_month.year(), last_month.month(), 1)
            month_end = QDate(today.year(), today.month(), 1).addDays(-1)
            self.start_date_edit.setDate(month_start)
            self.end_date_edit.setDate(month_end)
            
        # Update stored dates
        self.start_date = self.start_date_edit.date()
        self.end_date = self.end_date_edit.date()
        
        # Unblock signals
        self.start_date_edit.blockSignals(False)
        self.end_date_edit.blockSignals(False)
        
        # Emit filter changed signal
        self.filter_changed.emit()
        
    def reset_filters(self):
        """Reset all filters to default values"""
        # Block signals
        self.blockSignals(True)
        
        # Reset date range to last 90 days
        default_start = QDate.currentDate().addDays(-90)
        default_end = QDate.currentDate()
        self.start_date_edit.setDate(default_start)
        self.end_date_edit.setDate(default_end)
        self.start_date = default_start
        self.end_date = default_end
        
        # Reset combos to "All" options
        if self.show_course:
            self.course_combo.setCurrentIndex(0)
        self.instructor_combo.setCurrentIndex(0)
        if hasattr(self, 'class_combo'):
            self.class_combo.setCurrentIndex(0)
        self.year_combo.setCurrentIndex(0)
        self.semester_combo.setCurrentIndex(0)
        
        # Reset preset to "Custom Range"
        self.preset_combo.setCurrentIndex(0)
        
        # Reload all instructors and classes
        self.load_instructors()
        if hasattr(self, 'class_combo'):
            self.load_classes()
        
        # Unblock signals
        self.blockSignals(False)
        
        # Emit filter changed signal
        self.filter_changed.emit()
        
    def get_start_date(self):
        """
        Get the selected start date
        
        Returns:
            QDate: The selected start date
        """
        return self.start_date
        
    def get_end_date(self):
        """
        Get the selected end date
        
        Returns:
            QDate: The selected end date
        """
        return self.end_date
        
    def get_course_code(self):
        """
        Get the selected course code
        
        Returns:
            str: The selected course code or None for "All Courses"
        """
        return self.course_combo.currentData()
        
    def get_instructor_id(self):
        """
        Get the selected instructor ID
        
        Returns:
            int: The selected instructor ID or None for "All Instructors"
        """
        return self.instructor_combo.currentData()
        
    def get_year_of_study(self):
        """
        Get the selected year of study
        
        Returns:
            int: The selected year of study (1-5) or 0 for "All Years"
        """
        index = self.year_combo.currentIndex()
        return index if index > 0 else None
        
    def get_semester(self):
        """
        Get the selected semester
        
        Returns:
            str: The selected semester or None for "All Semesters"
        """
        index = self.semester_combo.currentIndex()
        if index == 0:
            return None
        elif index == 1:
            return "Semester 1"
        elif index == 2:
            return "Semester 2"
        elif index == 3:
            return "Summer"
        
    def set_course(self, course_code):
        """
        Set the course filter to the specified course code
        
        Args:
            course_code (str): The course code to select
        """
        if self.show_course:
            index = self.course_combo.findData(course_code)
            if index >= 0:
                self.course_combo.setCurrentIndex(index)

    def set_instructor(self, instructor_id):
        """
        Set the instructor filter to the specified instructor ID
        
        Args:
            instructor_id (int): The instructor ID to select
        """
        index = self.instructor_combo.findData(instructor_id)
        if index >= 0:
            self.instructor_combo.setCurrentIndex(index)