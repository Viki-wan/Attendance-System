import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QApplication, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, 
    QDateEdit, QFrame, QTabWidget, QGridLayout, QSpacerItem,
    QSizePolicy, QScrollArea, QHeaderView, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QDate, QDateTime, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPixmap, QIcon
from PyQt5.QtChart import QChart, QChartView, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QTextDocument

# Import report modules
from reports.daily_report import DailyReportWindow
from reports.course_report import CourseReportWindow
from reports.trend_report import TrendReportWindow
from reports.comparison_report import ComparisonReportWindow
from reports.instructor_report import InstructorReportWindow

# Import utilities and widgets
from utils.report_generator import ReportGenerator
from utils.db_queries import DatabaseQueries
from widgets.stat_card import StatCard
from widgets.filter_panel import FilterPanel


class ViewAttendanceWindow(QWidget):
    """Main window for viewing and analyzing attendance data"""
    
    def __init__(self, db_service=None):
        super().__init__()
        self.setWindowTitle("Attendance Analytics Dashboard")
        self.setGeometry(200, 100, 1200, 800)
        self.setObjectName("AttendanceWindow")
        self.setStyleSheet(QApplication.instance().styleSheet())
        
        # Store database service
        from admin.db_service import DatabaseService
        self.db_service = db_service or DatabaseService()
        
        # Create database query helper
        self.db_queries = DatabaseQueries(self.db_service)
        
        # Initialize report generator
        self.report_generator = ReportGenerator(self.db_service)
        
        # Setup UI
        self.init_ui()
        
        # Initial data load
        self.load_initial_data()
    
    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout()
        
        # Header with title and export buttons
        self.setup_header(main_layout)
        
        # Create a scroll area for the dashboard
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Create the content widget that will go inside the scroll area
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        
        # Add filter panel
        self.filter_panel = FilterPanel(self.db_service)
        self.filter_panel.filter_changed.connect(self.apply_filters)
        self.content_layout.addWidget(self.filter_panel)
        
        # Add dashboard content
        self.setup_dashboard(self.content_layout)
        
        # Add tab widget for different reports
        self.setup_report_tabs(self.content_layout)
        
        # Set the content widget as the scroll area's widget
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)
    
    def setup_header(self, layout):
        """Set up the header with title and action buttons"""
        header_layout = QHBoxLayout()
        
        # Title
        title_label = QLabel("Attendance Analytics Dashboard")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # Spacer to push buttons to the right
        header_layout.addStretch()
        
        # Export buttons
        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 16px;")
        export_pdf_btn.clicked.connect(self.export_pdf)
        
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px 16px;")
        export_csv_btn.clicked.connect(self.export_csv)
        
        header_layout.addWidget(export_pdf_btn)
        header_layout.addWidget(export_csv_btn)
        
        layout.addLayout(header_layout)
        
        # Add a horizontal line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
    
    def setup_dashboard(self, layout):
        """Set up the dashboard with summary statistics cards"""
        # Dashboard title
        dashboard_title = QLabel("Summary Statistics")
        dashboard_title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-top: 10px;")
        layout.addWidget(dashboard_title)
        
        # Stats cards layout (2x2 grid)
        stats_layout = QGridLayout()
        stats_layout.setContentsMargins(0, 10, 0, 10)
        stats_layout.setSpacing(15)
        
        # Create 4 stat cards
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
        
        self.lowest_attendance_card = StatCard(
            "Lowest Attendance", 
            "0%", 
            "trending-down", 
            "#F44336"
        )
        
        self.highest_attendance_card = StatCard(
            "Highest Attendance", 
            "0%", 
            "trending-up", 
            "#FF9800"
        )
        
        # Add cards to grid
        stats_layout.addWidget(self.total_sessions_card, 0, 0)
        stats_layout.addWidget(self.avg_attendance_card, 0, 1)
        stats_layout.addWidget(self.lowest_attendance_card, 1, 0)
        stats_layout.addWidget(self.highest_attendance_card, 1, 1)
        
        layout.addLayout(stats_layout)
        
        # Overview chart
        self.setup_overview_chart(layout)
    
    def setup_overview_chart(self, layout):
        """Set up the overview chart in the dashboard"""
        chart_title = QLabel("Attendance Overview")
        chart_title.setStyleSheet("font-size: 14pt; font-weight: bold; margin-top: 15px;")
        layout.addWidget(chart_title)
        
        # Create chart
        self.overview_chart = QChart()
        self.overview_chart.setTitle("Attendance Trends")
        self.overview_chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Initial empty chart
        chart_view = QChartView(self.overview_chart)
        chart_view.setRenderHint(QPainter.Antialiasing)
        chart_view.setMinimumHeight(250)
        
        layout.addWidget(chart_view)
    
    def setup_report_tabs(self, layout):
        """Set up tabs for different report types"""
        tab_widget = QTabWidget()
        tab_widget.setContentsMargins(0, 20, 0, 0)
        
        # Create report tabs
        self.daily_report = DailyReportWindow(self.db_service)
        self.course_report = CourseReportWindow(self.db_service)
        self.trend_report = TrendReportWindow(self.db_service)
        self.comparison_report = ComparisonReportWindow(self.db_service)
        self.instructor_report = InstructorReportWindow(self.db_service)
        
        # Add tabs
        tab_widget.addTab(self.daily_report, "Daily Reports")
        tab_widget.addTab(self.course_report, "Course Analysis")
        tab_widget.addTab(self.trend_report, "Attendance Trends")
        tab_widget.addTab(self.comparison_report, "Comparative Analysis")
        tab_widget.addTab(self.instructor_report, "Instructor Effectiveness")
        
        layout.addWidget(tab_widget)
    
    def load_initial_data(self):
        """Load initial data to populate the dashboard"""
        # Default to last 30 days
        end_date = QDate.currentDate()
        start_date = end_date.addDays(-30)
        
        # Set initial dates in the filter panel
        self.filter_panel.set_default_dates(start_date, end_date)
        
        # Load data with default filters
        self.apply_filters()
    
    def apply_filters(self):
        """Apply selected filters and refresh all reports"""
        # Get filter values from the filter panel
        filters = self.filter_panel.get_current_filters()
        
        # Update dashboard stats
        self.update_dashboard_stats(filters)
        
        # Update all report tabs
        self.daily_report.update_report(filters)
        self.course_report.update_report(filters)
        self.trend_report.update_report(filters)
        self.comparison_report.update_report(filters)
        self.instructor_report.update_report(filters)
    
    def update_dashboard_stats(self, filters):
        """Update the dashboard statistics based on filters"""
        # Get stats from database
        stats = self.db_queries.get_attendance_summary_stats(
            filters.get('start_date'),
            filters.get('end_date'),
            filters.get('course_code'),
            filters.get('class_id'),
            filters.get('instructor_id'),
            filters.get('year'),
            filters.get('semester')
        )
        
        # Update stat cards
        self.total_sessions_card.set_value(str(stats['total_sessions']))
        self.avg_attendance_card.set_value(f"{stats['avg_attendance']:.1f}%")
        self.lowest_attendance_card.set_value(f"{stats['min_attendance']:.1f}%")
        self.highest_attendance_card.set_value(f"{stats['max_attendance']:.1f}%")
        
        # Update overview chart
        self.update_overview_chart(filters)
    
    def update_overview_chart(self, filters):
        """Update the overview chart based on filters"""
        # Get chart data from database
        chart_data = self.db_queries.get_attendance_trend_data(
            filters.get('start_date'),
            filters.get('end_date'),
            filters.get('course_code'),
            filters.get('class_id'),
            filters.get('instructor_id')
        )
        
        # Clear previous data
        self.overview_chart.removeAllSeries()
        
        # Create bar set for attendance percentage
        attendance_set = QBarSet("Attendance %")
        attendance_set.setColor(QColor("#2196F3"))
        
        categories = []
        
        # Add data to bar set
        for entry in chart_data:
            attendance_set.append(entry['attendance_percentage'])
            categories.append(entry['date_label'])
        
        # Create bar series
        series = QBarSeries()
        series.append(attendance_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsOutsideEnd)
        
        # Add series to chart
        self.overview_chart.addSeries(series)
        
        # Create category axis
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        self.overview_chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        # Create value axis
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)
        axis_y.setTitleText("Attendance (%)")
        self.overview_chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Add title
        period_text = f"{filters.get('start_date').toString('yyyy-MM-dd')} to {filters.get('end_date').toString('yyyy-MM-dd')}"
        self.overview_chart.setTitle(f"Attendance Trend ({period_text})")
    
    def export_pdf(self):
        """Export the current report to PDF"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", "", "PDF Files (*.pdf)"
        )
        
        if file_path:
            # Get current filters
            filters = self.filter_panel.get_current_filters()
            
            # Generate and save the report
            success = self.report_generator.generate_pdf_report(file_path, filters)
            
            if success:
                QMessageBox.information(self, "Export Successful", 
                    "The attendance report was successfully exported to PDF.")
            else:
                QMessageBox.warning(self, "Export Failed", 
                    "Failed to export the attendance report.")
    
    def export_csv(self):
        """Export the current report data to CSV"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV Report", "", "CSV Files (*.csv)"
        )
        
        if file_path:
            # Get current filters
            filters = self.filter_panel.get_current_filters()
            
            # Generate and save the CSV
            success = self.report_generator.generate_csv_report(file_path, filters)
            
            if success:
                QMessageBox.information(self, "Export Successful", 
                    "The attendance data was successfully exported to CSV.")
            else:
                QMessageBox.warning(self, "Export Failed", 
                    "Failed to export the attendance data.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ViewAttendanceWindow()
    window.show()
    sys.exit(app.exec_())