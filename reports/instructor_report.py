import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QApplication, QLabel, 
                           QPushButton, QHBoxLayout, QTableWidget, 
                           QTableWidgetItem, QHeaderView, QFrame, 
                           QScrollArea, QSizePolicy, QSpacerItem)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor

# Import local modules
sys.path.append('..')  # Add parent directory to path
from admin.db_service import DatabaseService
from utils.db_queries import DatabaseQueries
from widgets.attendance_chart import AttendanceBarChart
from widgets.stat_card import StatCard
from widgets.filter_panel import FilterPanel
from widgets.collapsible_section import CollapsibleSection

class InstructorReportWindow(QWidget):
    """Window for analyzing instructor effectiveness"""
    
    def __init__(self, db_service=None, use_shared_filter=False):
        super().__init__()
        self.setWindowTitle("Instructor Effectiveness Report")
        self.setGeometry(300, 200, 1000, 700)
        self.setObjectName("InstructorReportWindow")
        
        # Initialize services
        self.db_service = db_service or DatabaseService()
        self.db_queries = DatabaseQueries(self.db_service)
        
        # Keep track of shared filter flag
        self.use_shared_filter = use_shared_filter
        
        # Setup UI
        self.init_ui()
        
        # Load initial data if not using shared filter
        if not self.use_shared_filter:
            self.load_data()
        
    def init_ui(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Only create filter panel if not using shared filter
        if not self.use_shared_filter:
            # Header with title and filters
            header_layout = QHBoxLayout()
            
            title_label = QLabel("Instructor Effectiveness Analysis")
            title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #2c3e50;")
            header_layout.addWidget(title_label)
            
            # Spacer to push filter controls to the right
            header_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
            
            # Filter panel
            self.filter_panel = FilterPanel(self.db_service)
            self.filter_panel.filter_changed.connect(self.on_filter_changed)
            header_layout.addWidget(self.filter_panel)
            
            main_layout.addLayout(header_layout)
            
            # Add a horizontal line
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setLineWidth(1)
            main_layout.addWidget(line)
        else:
            # Just add title when using shared filter
            title_label = QLabel("Instructor Effectiveness Analysis")
            title_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2c3e50;")
            main_layout.addWidget(title_label)
        
        # Create a scroll area for the content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container for scrollable content
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        
        # Stats cards in collapsible section
        stats_section = CollapsibleSection("Instructor Performance Summary", True)
        stats_layout = QHBoxLayout()
        
        # Create stat cards
        self.total_sessions_card = StatCard(
            "Total Sessions", 
            "0", 
            "calendar", 
            "#4CAF50"
        )
        
        self.avg_attendance_card = StatCard(
            "Average Attendance", 
            "0%", 
            "users", 
            "#2196F3"
        )
        
        self.best_instructor_card = StatCard(
            "Best Performer", 
            "N/A", 
            "award", 
            "#FF9800"
        )
        
        self.below_avg_card = StatCard(
            "Below Average", 
            "0", 
            "alert-triangle", 
            "#F44336"
        )
        
        # Add cards to layout
        stats_layout.addWidget(self.total_sessions_card)
        stats_layout.addWidget(self.avg_attendance_card)
        stats_layout.addWidget(self.best_instructor_card)
        stats_layout.addWidget(self.below_avg_card)
        
        stats_section.setContentLayout(stats_layout)
        self.scroll_layout.addWidget(stats_section)
        
        # Instructor effectiveness overview section
        overview_section = CollapsibleSection("Instructor Attendance Overview", True)
        overview_layout = QVBoxLayout()
        
        # Bar chart for instructor comparison
        self.instructor_chart = AttendanceBarChart()
        self.instructor_chart.setMinimumHeight(300)
        overview_layout.addWidget(self.instructor_chart)
        
        overview_section.setContentLayout(overview_layout)
        self.scroll_layout.addWidget(overview_section)
        
        # Instructor detailed table section
        table_section = CollapsibleSection("Instructor Detailed Performance", True)
        table_layout = QVBoxLayout()
        
        # Instructor data table
        self.instructor_table = QTableWidget()
        self.instructor_table.setColumnCount(6)
        self.instructor_table.setHorizontalHeaderLabels([
            "Instructor", "Total Sessions", "Total Students", 
            "Attended Students", "Attendance %", "Performance"
        ])
        self.instructor_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.instructor_table.setMinimumHeight(300)
        table_layout.addWidget(self.instructor_table)
        
        table_section.setContentLayout(table_layout)
        self.scroll_layout.addWidget(table_section)
        
        # Course popularity by instructor section
        course_section = CollapsibleSection("Course Attendance by Selected Instructor", True)
        course_layout = QVBoxLayout()
        
        self.course_chart = AttendanceBarChart()
        self.course_chart.setMinimumHeight(250)
        course_layout.addWidget(self.course_chart)
        
        course_section.setContentLayout(course_layout)
        self.scroll_layout.addWidget(course_section)
        
        # Complete the scroll area setup
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)
    
    def load_data(self):
        """Load data for the report"""
        if hasattr(self, 'filter_panel'):
            start_date = self.filter_panel.get_start_date()
            end_date = self.filter_panel.get_end_date()
            instructor_id = self.filter_panel.get_instructor_id()
            
            # Update instructor comparison chart and table
            self.update_instructor_data(start_date, end_date)
            
            # If a specific instructor is selected, update course chart
            if instructor_id:
                self.update_instructor_courses(start_date, end_date, instructor_id)
                
            # Update stat cards
            self.update_summary_stats(start_date, end_date)
    
    def on_filter_changed(self):
        """Handle filter changes"""
        self.load_data()
    
    def update_summary_stats(self, start_date, end_date):
        """Update the summary statistics cards"""
        # Get summary data
        stats = self.db_queries.get_instructor_summary_stats(start_date, end_date)
        
        # Update stat cards
        self.total_sessions_card.set_value(str(stats.get('total_sessions', 0)))
        self.avg_attendance_card.set_value(f"{stats.get('avg_attendance', 0):.1f}%")
        self.best_instructor_card.set_value(stats.get('best_instructor', 'N/A'))
        self.below_avg_card.set_value(str(stats.get('below_avg_count', 0)))
    
    def update_instructor_data(self, start_date, end_date):
        """Update the instructor comparison chart and table"""
        # Get instructor effectiveness data
        instructor_data = self.db_queries.get_instructor_effectiveness_data(start_date, end_date)
        
        # Prepare data for chart
        labels = [item['instructor_name'] for item in instructor_data]
        values = [item['attendance_percentage'] for item in instructor_data]
        
        # Update chart
        self.instructor_chart.set_data(
            labels, values, "Attendance Percentage by Instructor",
            bar_colors=self.get_performance_colors(values)
        )
        
        # Update table
        self.instructor_table.setRowCount(0)
        for row, data in enumerate(instructor_data):
            self.instructor_table.insertRow(row)
            
            # Add instructor name
            self.instructor_table.setItem(row, 0, QTableWidgetItem(data['instructor_name']))
            
            # Add total sessions
            sessions_item = QTableWidgetItem(str(data['total_sessions']))
            sessions_item.setTextAlignment(Qt.AlignCenter)
            self.instructor_table.setItem(row, 1, sessions_item)
            
            # Add total students
            students_item = QTableWidgetItem(str(data['total_students']))
            students_item.setTextAlignment(Qt.AlignCenter)
            self.instructor_table.setItem(row, 2, students_item)
            
            # Add attended students
            attended_item = QTableWidgetItem(str(data['attended_students']))
            attended_item.setTextAlignment(Qt.AlignCenter)
            self.instructor_table.setItem(row, 3, attended_item)
            
            # Add attendance percentage
            percentage_item = QTableWidgetItem(f"{data['attendance_percentage']:.2f}%")
            percentage_item.setTextAlignment(Qt.AlignCenter)
            self.instructor_table.setItem(row, 4, percentage_item)
            
            # Add performance rating
            performance = self.get_performance_rating(data['attendance_percentage'])
            performance_item = QTableWidgetItem(performance)
            performance_item.setTextAlignment(Qt.AlignCenter)
            
            # Set background color based on performance
            if performance == "Excellent":
                performance_item.setBackground(QColor(200, 255, 200))  # Light green
            elif performance == "Good":
                performance_item.setBackground(QColor(220, 240, 220))  # Pale green
            elif performance == "Average":
                performance_item.setBackground(QColor(255, 255, 200))  # Light yellow
            elif performance == "Below Average":
                performance_item.setBackground(QColor(255, 230, 200))  # Light orange
            else:  # Poor
                performance_item.setBackground(QColor(255, 200, 200))  # Light red
                
            self.instructor_table.setItem(row, 5, performance_item)

    def update_report(self, filters):
        """Update the report with the given filters from shared filter panel"""
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        instructor_id = filters.get('instructor_id')
        
        if start_date and end_date:
            # Update instructor comparison chart and table
            self.update_instructor_data(start_date, end_date)
            
            # Update summary stats
            self.update_summary_stats(start_date, end_date)
            
            # If a specific instructor is selected, update course chart
            if instructor_id:
                self.update_instructor_courses(start_date, end_date, instructor_id)
            else:
                # Clear the course chart if no instructor selected
                self.course_chart.clear_data("Select an instructor to view course performance")
    
    def update_instructor_courses(self, start_date, end_date, instructor_id):
        """Update the course chart for a specific instructor"""
        # Get comparative analysis data filtered by course for this instructor
        course_data = self.db_queries.get_comparative_analysis(
            start_date, end_date, compare_by='course'
        )
        
        # Filter data to only include courses taught by this instructor
        instructor_courses = self.db_service.get_instructor_courses(instructor_id)
        instructor_course_codes = [course['course_code'] for course in instructor_courses]
        
        filtered_course_data = [
            item for item in course_data 
            if item['category_id'] in instructor_course_codes
        ]
        
        # Prepare data for chart
        labels = [item['category_name'] for item in filtered_course_data]
        values = [item['attendance_percentage'] for item in filtered_course_data]
        
        # Update chart
        if labels and values:
            self.course_chart.set_data(
                labels, values, "Course Attendance for Selected Instructor",
                bar_colors=self.get_performance_colors(values)
            )
        else:
            # No data available for this instructor
            self.course_chart.clear_data("No course data available for selected instructor")
    
    def get_performance_rating(self, attendance_percentage):
        """Get a textual performance rating based on attendance percentage"""
        if attendance_percentage >= 90:
            return "Excellent"
        elif attendance_percentage >= 80:
            return "Good"
        elif attendance_percentage >= 70:
            return "Average"
        elif attendance_percentage >= 60:
            return "Below Average"
        else:
            return "Poor"
    
    def get_performance_colors(self, values):
        """Generate colors for bars based on performance"""
        colors = []
        for value in values:
            if value >= 90:
                colors.append("#4CAF50")  # Green
            elif value >= 80:
                colors.append("#8BC34A")  # Light Green
            elif value >= 70:
                colors.append("#FFEB3B")  # Yellow
            elif value >= 60:
                colors.append("#FFC107")  # Amber
            else:
                colors.append("#F44336")  # Red
        
        return colors