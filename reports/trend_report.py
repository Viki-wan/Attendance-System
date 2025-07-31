import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QApplication, QLabel, 
    QPushButton, QHBoxLayout, QDateEdit, QComboBox,
    QFrame, QScrollArea, QSizePolicy, QSpacerItem,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

# Import local modules
sys.path.append('..')  # Add parent directory to path
from admin.db_service import DatabaseService
from utils.db_queries import DatabaseQueries
from widgets.attendance_chart import AttendanceBarChart
from widgets.attendance_line_chart import AttendanceLineChart
from widgets.stat_card import StatCard
from widgets.filter_panel import FilterPanel
from widgets.collapsible_section import CollapsibleSection

class TrendReportWindow(QWidget):
    """Window for viewing attendance trends over time"""
    
    def __init__(self, db_service=None, use_shared_filter=False):
        super().__init__()
        self.setWindowTitle("Attendance Trends Analysis")
        self.setObjectName("TrendReportWindow")
        
        # Initialize services
        self.db_service = db_service or DatabaseService()
        self.db_queries = DatabaseQueries(self.db_service)
        
        # Track if we're using a shared filter panel
        self.use_shared_filter = use_shared_filter
        
        # Setup UI
        self.init_ui()
        
        # Load initial data if not using shared filter
        if not self.use_shared_filter:
            self.load_data()
        
    def init_ui(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Header with title and filter panel (only if not using shared filter)
        if not self.use_shared_filter:
            header_layout = QHBoxLayout()
            
            title_label = QLabel("Attendance Trends Analysis")
            title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #2c3e50;")
            header_layout.addWidget(title_label)
            
            # Spacer to push filter panel to the right
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
            title_label = QLabel("Attendance Trends Analysis")
            title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #2c3e50;")
            main_layout.addWidget(title_label)
        
        # Create a scroll area for the content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container for scrollable content
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add stats cards in collapsible section
        stats_section = CollapsibleSection("Key Statistics", True)
        stats_layout = QHBoxLayout()
        
        # Initialize stat cards
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
        self.max_attendance_card = StatCard(
            "Highest Attendance", 
            "0%", 
            "trending-up", 
            "#FF9800"
        )
        self.min_attendance_card = StatCard(
            "Lowest Attendance", 
            "0%", 
            "trending-down", 
            "#F44336"
        )
        
        stats_layout.addWidget(self.total_sessions_card)
        stats_layout.addWidget(self.avg_attendance_card)
        stats_layout.addWidget(self.max_attendance_card)
        stats_layout.addWidget(self.min_attendance_card)
        
        stats_section.setContentLayout(stats_layout)
        self.scroll_layout.addWidget(stats_section)
        
        # Line chart for attendance trends in collapsible section
        trend_section = CollapsibleSection("Attendance Trend Over Time", True)
        trend_layout = QVBoxLayout()
        
        self.line_chart = AttendanceLineChart()
        self.line_chart.setMinimumHeight(300)
        trend_layout.addWidget(self.line_chart)
        
        trend_section.setContentLayout(trend_layout)
        self.scroll_layout.addWidget(trend_section)
        
        # Course comparison section in collapsible section
        course_section = CollapsibleSection("Course Attendance Comparison", True)
        course_layout = QVBoxLayout()
        
        self.course_chart = AttendanceBarChart()
        self.course_chart.setMinimumHeight(300)
        course_layout.addWidget(self.course_chart)
        
        course_section.setContentLayout(course_layout)
        self.scroll_layout.addWidget(course_section)
        
        # Time of day analysis section in collapsible section
        time_section = CollapsibleSection("Time of Day Attendance Analysis", True)
        time_layout = QVBoxLayout()
        
        self.time_chart = AttendanceBarChart()
        self.time_chart.setMinimumHeight(300)
        time_layout.addWidget(self.time_chart)
        
        time_section.setContentLayout(time_layout)
        self.scroll_layout.addWidget(time_section)
        
        # Day of week analysis section
        dow_section = CollapsibleSection("Day of Week Attendance Analysis", True)
        dow_layout = QVBoxLayout()
        
        self.dow_chart = AttendanceBarChart()
        self.dow_chart.setMinimumHeight(300)
        dow_layout.addWidget(self.dow_chart)
        
        dow_section.setContentLayout(dow_layout)
        self.scroll_layout.addWidget(dow_section)
        
        # Complete the scroll area setup
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)
    
    def load_data(self):
        """Load initial data for the report"""
        if not self.use_shared_filter:
            start_date = self.filter_panel.get_start_date()
            end_date = self.filter_panel.get_end_date()
            course_code = self.filter_panel.get_course_code()
            instructor_id = self.filter_panel.get_instructor_id()
            
            # Update all report components
            self.update_report({
                'start_date': start_date,
                'end_date': end_date,
                'course_code': course_code,
                'instructor_id': instructor_id
            })
    
    def on_filter_changed(self):
        """Handle filter changes"""
        if not self.use_shared_filter:
            self.load_data()
    
    def update_stats_cards(self, filters):
        """Update the statistics cards"""
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        course_code = filters.get('course_code')
        instructor_id = filters.get('instructor_id')
        
        stats = self.db_queries.get_attendance_summary_stats(
            start_date, end_date, course_code, None, instructor_id
        )
        
        self.total_sessions_card.set_value(str(stats['total_sessions']))
        self.avg_attendance_card.set_value(f"{stats['avg_attendance']:.1f}%")
        self.max_attendance_card.set_value(f"{stats['max_attendance']:.1f}%")
        self.min_attendance_card.set_value(f"{stats['min_attendance']:.1f}%")
    
    def update_trend_chart(self, filters):
        """Update the trend line chart"""
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        course_code = filters.get('course_code')
        instructor_id = filters.get('instructor_id')
        
        trend_data = self.db_queries.get_attendance_trend_data(
            start_date, end_date, course_code, None, instructor_id
        )
        
        # Prepare data for chart
        labels = [item['date_label'] for item in trend_data]
        values = [item['attendance_percentage'] for item in trend_data]
        
        # Update chart with period text in title
        period_text = f"{start_date.toString('yyyy-MM-dd')} to {end_date.toString('yyyy-MM-dd')}"
        self.line_chart.set_data(labels, values, f"Attendance Trend ({period_text})")

    def update_course_chart(self, filters):
        """Update the course comparison chart"""
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        
        course_data = self.db_queries.get_course_attendance_data(start_date, end_date)
        
        # Prepare data for chart
        labels = [item['course_code'] for item in course_data]
        values = [item['attendance_percentage'] for item in course_data]
        
        # Update chart
        self.course_chart.set_data(labels, values, "Course Attendance Percentage")
    
    def update_time_chart(self, filters):
        """Update the time of day analysis chart"""
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        course_code = filters.get('course_code')
        instructor_id = filters.get('instructor_id')
        
        time_data = self.db_queries.get_time_analysis_data(start_date, end_date)
        
        # Prepare data for chart
        labels = [item['time_slot'] for item in time_data]
        values = [item['attendance_percentage'] for item in time_data]
        
        # Update chart
        self.time_chart.set_data(labels, values, "Attendance by Time of Day")
    
    def update_day_of_week_chart(self, filters):
        """Update the day of week analysis chart"""
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        course_code = filters.get('course_code')
        instructor_id = filters.get('instructor_id')
        
        # Use the existing comparative analysis method with 'day_of_week' parameter
        dow_data = self.db_queries.get_comparative_analysis(start_date, end_date, 'day_of_week')
        
        # Prepare data for chart
        labels = [item['category_name'] for item in dow_data]
        values = [item['attendance_percentage'] for item in dow_data]
        
        # Update chart
        self.dow_chart.set_data(labels, values, "Attendance by Day of Week")
    
    def update_report(self, filters):
        """Update the report with the given filters"""
        # Update all report components
        self.update_stats_cards(filters)
        self.update_trend_chart(filters)
        self.update_course_chart(filters)
        self.update_time_chart(filters)
        self.update_day_of_week_chart(filters)