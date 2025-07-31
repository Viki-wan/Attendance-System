import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QApplication, QLabel, 
                           QPushButton, QHBoxLayout, QTableWidget, 
                           QTableWidgetItem, QHeaderView, QFrame, 
                           QScrollArea, QSizePolicy, QSpacerItem,
                           QComboBox, QGroupBox, QRadioButton, QButtonGroup)
from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtChart import QChart, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis, QChartView

# Import local modules
sys.path.append('..')  # Add parent directory to path
from admin.db_service import DatabaseService
from utils.db_queries import DatabaseQueries
from widgets.attendance_chart import AttendanceBarChart
from widgets.stat_card import StatCard
from widgets.filter_panel import FilterPanel
from widgets.collapsible_section import CollapsibleSection

class ComparisonReportWindow(QWidget):
    """Window for comparative analysis of attendance data"""
    
    def __init__(self, db_service=None, use_shared_filter=False):
        super().__init__()
        self.setWindowTitle("Attendance Comparison Report")
        self.setObjectName("ComparisonReportWindow")
        
        # Initialize services
        self.db_service = db_service or DatabaseService()
        self.db_queries = DatabaseQueries(self.db_service)
        
        # Track if using shared filter
        self.use_shared_filter = use_shared_filter
        self.filter_panel = None
        
        # Track current comparison types
        self.primary_comparison = "course"
        self.secondary_comparison = "year"
        
        # Setup UI
        self.init_ui()
        
        # Load initial data
        if not self.use_shared_filter:
            self.load_data()
        
    def init_ui(self):
        """Initialize the UI components"""
        main_layout = QVBoxLayout()
        
        # Only create filter panel if not using shared one
        if not self.use_shared_filter:
            # Header with title and filters
            header_layout = QHBoxLayout()
            
            title_label = QLabel("Comparative Attendance Analysis")
            title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #2c3e50;")
            header_layout.addWidget(title_label)
            
            # Spacer to push date controls to the right
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
            title_label = QLabel("Comparative Attendance Analysis")
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
        
        # Comparison selection in collapsible section
        comparison_section = CollapsibleSection("Comparison Settings", True)
        comparison_layout = QHBoxLayout()
        
        # Primary comparison group
        primary_group = QGroupBox("Primary Comparison")
        primary_layout = QVBoxLayout()
        
        self.primary_course = QRadioButton("Course")
        self.primary_course.setChecked(True)
        self.primary_year = QRadioButton("Year of Study")
        self.primary_semester = QRadioButton("Semester")
        self.primary_time = QRadioButton("Time of Day")
        self.primary_instructor = QRadioButton("Instructor")
        
        self.primary_button_group = QButtonGroup()
        self.primary_button_group.addButton(self.primary_course)
        self.primary_button_group.addButton(self.primary_year)
        self.primary_button_group.addButton(self.primary_semester)
        self.primary_button_group.addButton(self.primary_time)
        self.primary_button_group.addButton(self.primary_instructor)
        self.primary_button_group.buttonClicked.connect(self.on_comparison_changed)
        
        primary_layout.addWidget(self.primary_course)
        primary_layout.addWidget(self.primary_year)
        primary_layout.addWidget(self.primary_semester)
        primary_layout.addWidget(self.primary_time)
        primary_layout.addWidget(self.primary_instructor)
        primary_group.setLayout(primary_layout)
        comparison_layout.addWidget(primary_group)
        
        # Secondary comparison group
        secondary_group = QGroupBox("Secondary Comparison (Breakdown)")
        secondary_layout = QVBoxLayout()
        
        self.secondary_none = QRadioButton("None")
        self.secondary_course = QRadioButton("Course")
        self.secondary_year = QRadioButton("Year of Study")
        self.secondary_year.setChecked(True)
        self.secondary_semester = QRadioButton("Semester")
        self.secondary_time = QRadioButton("Time of Day")
        self.secondary_instructor = QRadioButton("Instructor")
        
        self.secondary_button_group = QButtonGroup()
        self.secondary_button_group.addButton(self.secondary_none)
        self.secondary_button_group.addButton(self.secondary_course)
        self.secondary_button_group.addButton(self.secondary_year)
        self.secondary_button_group.addButton(self.secondary_semester)
        self.secondary_button_group.addButton(self.secondary_time)
        self.secondary_button_group.addButton(self.secondary_instructor)
        self.secondary_button_group.buttonClicked.connect(self.on_comparison_changed)
        
        secondary_layout.addWidget(self.secondary_none)
        secondary_layout.addWidget(self.secondary_course)
        secondary_layout.addWidget(self.secondary_year)
        secondary_layout.addWidget(self.secondary_semester)
        secondary_layout.addWidget(self.secondary_time)
        secondary_layout.addWidget(self.secondary_instructor)
        secondary_group.setLayout(secondary_layout)
        comparison_layout.addWidget(secondary_group)
        
        apply_comparison = QPushButton("Apply Comparison")
        apply_comparison.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        apply_comparison.clicked.connect(self.load_data)
        comparison_layout.addWidget(apply_comparison)
        
        comparison_section.setContentLayout(comparison_layout)
        self.scroll_layout.addWidget(comparison_section)
        
        # Main comparison chart section in collapsible section
        primary_chart_section = CollapsibleSection("Primary Comparison", True)
        primary_chart_layout = QVBoxLayout()
        
        # Bar chart for primary comparison
        self.primary_chart = AttendanceBarChart()
        self.primary_chart.setMinimumHeight(300)
        primary_chart_layout.addWidget(self.primary_chart)
        
        primary_chart_section.setContentLayout(primary_chart_layout)
        self.scroll_layout.addWidget(primary_chart_section)
        
        # Secondary comparison section in collapsible section
        secondary_chart_section = CollapsibleSection("Breakdown by Secondary Factor", True)
        secondary_chart_layout = QVBoxLayout()
        
        # Custom chart view for secondary comparison
        self.chart_view = QChartView()
        self.chart_view.setMinimumHeight(350)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        secondary_chart_layout.addWidget(self.chart_view)
        
        secondary_chart_section.setContentLayout(secondary_chart_layout)
        self.scroll_layout.addWidget(secondary_chart_section)
        
        # Store references to collapsible sections for managing visibility
        self.secondary_chart_section = secondary_chart_section
        
        # Complete the scroll area setup
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)
    
    def on_comparison_changed(self, button):
        """Handle comparison type selection"""
        # Update primary comparison
        if button in self.primary_button_group.buttons():
            if button == self.primary_course:
                self.primary_comparison = "course"
            elif button == self.primary_year:
                self.primary_comparison = "year"
            elif button == self.primary_semester:
                self.primary_comparison = "semester"
            elif button == self.primary_time:
                self.primary_comparison = "time"
            elif button == self.primary_instructor:
                self.primary_comparison = "instructor"
                
            # Disable this option in secondary comparison
            if button == self.primary_course:
                self.secondary_course.setEnabled(False)
                if self.secondary_course.isChecked():
                    self.secondary_none.setChecked(True)
                    self.secondary_comparison = "none"
            elif button == self.primary_year:
                self.secondary_year.setEnabled(False)
                if self.secondary_year.isChecked():
                    self.secondary_none.setChecked(True)
                    self.secondary_comparison = "none"
            elif button == self.primary_semester:
                self.secondary_semester.setEnabled(False)
                if self.secondary_semester.isChecked():
                    self.secondary_none.setChecked(True)
                    self.secondary_comparison = "none"
            elif button == self.primary_time:
                self.secondary_time.setEnabled(False)
                if self.secondary_time.isChecked():
                    self.secondary_none.setChecked(True)
                    self.secondary_comparison = "none"
            elif button == self.primary_instructor:
                self.secondary_instructor.setEnabled(False)
                if self.secondary_instructor.isChecked():
                    self.secondary_none.setChecked(True)
                    self.secondary_comparison = "none"
            
            # Re-enable all other options
            self.secondary_course.setEnabled(self.primary_comparison != "course")
            self.secondary_year.setEnabled(self.primary_comparison != "year")
            self.secondary_semester.setEnabled(self.primary_comparison != "semester")
            self.secondary_time.setEnabled(self.primary_comparison != "time")
            self.secondary_instructor.setEnabled(self.primary_comparison != "instructor")
                
        # Update secondary comparison
        elif button in self.secondary_button_group.buttons():
            if button == self.secondary_none:
                self.secondary_comparison = "none"
            elif button == self.secondary_course:
                self.secondary_comparison = "course"
            elif button == self.secondary_year:
                self.secondary_comparison = "year"
            elif button == self.secondary_semester:
                self.secondary_comparison = "semester"
            elif button == self.secondary_time:
                self.secondary_comparison = "time"
            elif button == self.secondary_instructor:
                self.secondary_comparison = "instructor"
    
    def load_data(self):
        """Load data for the comparison report"""
        # Get filter values
        if self.use_shared_filter and self.filter_panel:
            filters = self.filter_panel.get_current_filters()
            start_date = filters.get('start_date')
            end_date = filters.get('end_date')
        elif self.filter_panel:  # Add this check
            # Use local filter panel
            start_date = self.filter_panel.get_start_date()
            end_date = self.filter_panel.get_end_date()
        else:
            # Handle case where no filter panel is available
            start_date = QDate.currentDate().addDays(-90)  # Default to last 90 days
            end_date = QDate.currentDate()
            print("Warning: No filter panel available, using default date range")
        
        # Update primary comparison data
        self.update_primary_comparison(start_date, end_date)
        
        # Update secondary comparison if applicable
        if self.secondary_comparison != "none":
            self.update_secondary_comparison(start_date, end_date)
            self.secondary_chart_section.setVisible(True)
        else:
            self.secondary_chart_section.setVisible(False)
    
    def on_filter_changed(self):
        """Handle filter changes"""
        self.load_data()
    
    def update_primary_comparison(self, start_date, end_date):
        """Update the primary comparison chart"""
        # Get comparative analysis data based on primary comparison type
        comparison_data = self.db_queries.get_comparative_analysis(
            start_date, end_date, compare_by=self.primary_comparison
        )
        
        # If no data available
        if not comparison_data:
            self.primary_chart.clear_data(f"No {self.primary_comparison} data available for selected period")
            return
        
        # Sort data by attendance percentage in descending order
        sorted_data = sorted(comparison_data, key=lambda x: x['attendance_percentage'], reverse=True)
        
        # Prepare data for chart
        labels = [item['category_name'] for item in sorted_data]
        values = [item['attendance_percentage'] for item in sorted_data]
        
        # Get appropriate chart title based on comparison type
        title_mapping = {
            "course": "Attendance by Course",
            "year": "Attendance by Year of Study",
            "semester": "Attendance by Semester",
            "time": "Attendance by Time of Day",
            "instructor": "Attendance by Instructor"
        }
        
        chart_title = title_mapping.get(self.primary_comparison, "Attendance Comparison")
        
        # Update chart
        self.primary_chart.set_data(
            labels, values, f"{chart_title} (%)",
            bar_colors=self.get_attendance_colors(values)
        )
    
    def update_secondary_comparison(self, start_date, end_date):
        """Update the secondary comparison chart (grouped comparison)"""
        # Get data for both primary and secondary comparisons
        primary_data = self.db_queries.get_comparative_analysis(
            start_date, end_date, compare_by=self.primary_comparison
        )
        
        # If no primary data, clear chart
        if not primary_data:
            self.create_empty_chart("No data available for selected comparison")
            return
            
        # Sort primary data by attendance percentage (descending)
        primary_data = sorted(primary_data, key=lambda x: x['attendance_percentage'], reverse=True)
        
        # Get top 5 categories from primary comparison for readability
        top_categories = primary_data[:5]
        
        # Get secondary breakdown for each primary category
        all_breakdown_data = []
        for category in top_categories:
            breakdown_data = self.db_queries.get_comparative_breakdown(
                start_date, end_date,
                primary_type=self.primary_comparison,
                primary_id=category['category_id'],
                secondary_type=self.secondary_comparison
            )
            
            if breakdown_data:
                all_breakdown_data.append({
                    'primary_name': category['category_name'],
                    'breakdown': breakdown_data
                })
        
        # If no breakdown data, clear chart
        if not all_breakdown_data:
            self.create_empty_chart("No breakdown data available")
            return
            
        # Create grouped bar chart for secondary comparison
        self.create_grouped_chart(all_breakdown_data)
    
    def create_grouped_chart(self, all_data):
        """Create a grouped bar chart for secondary comparison"""
        # Create chart
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Create a bar series for each primary category
        bar_series = QBarSeries()
        
        # Get all unique secondary categories across all breakdowns
        all_secondary_categories = set()
        for data in all_data:
            for breakdown in data['breakdown']:
                all_secondary_categories.add(breakdown['category_name'])
        
        # Sort secondary categories alphabetically
        secondary_categories = sorted(list(all_secondary_categories))
        
        # Create a bar set for each primary category
        for data in all_data:
            bar_set = QBarSet(str(data['primary_name']))  # Convert to string
            
            # Map secondary categories to their attendance percentages
            category_to_value = {
                item['category_name']: item['attendance_percentage'] 
                for item in data['breakdown']
            }
            
            # Add values for each secondary category
            for category in secondary_categories:
                bar_set.append(category_to_value.get(category, 0))
                
            # Add bar set to series
            bar_series.append(bar_set)
            
        # Add series to chart
        chart.addSeries(bar_series)
        
        # Create axes
        axis_x = QBarCategoryAxis()
        # Convert all categories to strings
        string_categories = [str(category) for category in secondary_categories]
        axis_x.append(string_categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        bar_series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setTitleText("Attendance (%)")
        chart.addAxis(axis_y, Qt.AlignLeft)
        bar_series.attachAxis(axis_y)
        
        # Set chart title based on comparison types
        primary_type_map = {
            "course": "Courses", 
            "year": "Years", 
            "semester": "Semesters",
            "time": "Times",
            "instructor": "Instructors"
        }
        
        secondary_type_map = {
            "course": "Course", 
            "year": "Year", 
            "semester": "Semester",
            "time": "Time",
            "instructor": "Instructor"
        }
        
        chart.setTitle(f"Top {primary_type_map.get(self.primary_comparison, 'Categories')} by {secondary_type_map.get(self.secondary_comparison, 'Category')}")
        
        # Apply theme
        chart.setTheme(QChart.ChartThemeLight)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        
        # Set the chart in the chart view
        self.chart_view.setChart(chart)
    
    def update_report(self, filters):
        """Update the report with the given filters"""
        # Store reference to the shared filter panel if provided
        if 'filter_panel' in filters:
            self.filter_panel = filters['filter_panel']
            self.use_shared_filter = True
        
        # Apply the filters
        self.load_data()
    
    def create_empty_chart(self, message):
        """Create an empty chart with a message"""
        chart = QChart()
        chart.setTitle(message)
        chart.legend().hide()
        self.chart_view.setChart(chart)
    
    def get_attendance_colors(self, values):
        """Generate colors for bars based on attendance rates"""
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