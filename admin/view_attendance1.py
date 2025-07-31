# view_attendance.py
import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QApplication, 
                            QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                            QComboBox, QDateEdit, QGroupBox, QLineEdit,
                            QHeaderView, QMessageBox, QFileDialog, QCheckBox)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor

from admin.db_service import DatabaseService
from attendance.attendance_report_generator import AttendanceReportGenerator
from attendance.attendance_statistics import AttendanceStatistics
from attendance.attendance_chart_widget import AttendanceChartWidget

class ViewAttendanceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 View Attendance Reports")
        self.setGeometry(300, 200, 1000, 700)
        self.setObjectName("ViewAttendanceWindow")
        self.setStyleSheet(QApplication.instance().styleSheet())
        
        # Initialize services
        self.db_service = DatabaseService()
        self.report_generator = AttendanceReportGenerator(self.db_service)
        self.statistics = AttendanceStatistics(self.db_service)
        
        # Setup UI
        self.init_ui()
        
        # Load initial data
        self.load_filter_options()
        self.apply_filters()
        
    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout()
        
        # Add filters section
        filter_section = self.create_filter_section()
        main_layout.addLayout(filter_section)
        
        # Create main content area with splitter
        content_layout = QHBoxLayout()
        
        # Add attendance table 
        table_section = self.create_table_section()
        content_layout.addLayout(table_section, 7)  # 70% of width
        
        # Add statistics panel
        stats_section = self.create_statistics_section()
        content_layout.addLayout(stats_section, 3)  # 30% of width
        
        main_layout.addLayout(content_layout)
        
        # Add action buttons at bottom
        action_layout = self.create_action_buttons()
        main_layout.addLayout(action_layout)
        
        self.setLayout(main_layout)
    
    def create_filter_section(self):
        """Create the filter controls section"""
        filter_layout = QHBoxLayout()
        
        # Date range filter
        date_group = QGroupBox("Date Filter")
        date_layout = QHBoxLayout()
        
        date_layout.addWidget(QLabel("From:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-7))  # Default to one week ago
        date_layout.addWidget(self.from_date)
        
        date_layout.addWidget(QLabel("To:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())  # Default to today
        date_layout.addWidget(self.to_date)
        
        date_group.setLayout(date_layout)
        filter_layout.addWidget(date_group)
        
        # Course & Class filters
        class_group = QGroupBox("Course & Class Filter")
        class_layout = QHBoxLayout()
        
        class_layout.addWidget(QLabel("Course:"))
        self.course_filter = QComboBox()
        self.course_filter.currentIndexChanged.connect(self.update_class_filter)
        class_layout.addWidget(self.course_filter)
        
        class_layout.addWidget(QLabel("Class:"))
        self.class_filter = QComboBox()
        class_layout.addWidget(self.class_filter)
        
        class_group.setLayout(class_layout)
        filter_layout.addWidget(class_group)
        
        # Student filter
        student_group = QGroupBox("Student Filter")
        student_layout = QHBoxLayout()
        
        self.student_filter = QLineEdit()
        self.student_filter.setPlaceholderText("Search by student ID or name...")
        student_layout.addWidget(self.student_filter)
        
        student_group.setLayout(student_layout)
        filter_layout.addWidget(student_group)
        
        # Filter buttons
        filter_button_layout = QVBoxLayout()
        
        self.apply_filter_btn = QPushButton("Apply Filters")
        self.apply_filter_btn.clicked.connect(self.apply_filters)
        filter_button_layout.addWidget(self.apply_filter_btn)
        
        self.reset_filter_btn = QPushButton("Reset Filters")
        self.reset_filter_btn.clicked.connect(self.reset_filters)
        filter_button_layout.addWidget(self.reset_filter_btn)
        
        filter_layout.addLayout(filter_button_layout)
        
        return filter_layout
    
    def create_table_section(self):
        """Create the attendance data table section"""
        table_layout = QVBoxLayout()
        
        # Table header
        self.table_header = QLabel("Attendance Records")
        self.table_header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        table_layout.addWidget(self.table_header)
        
        # Create table
        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(7)
        self.attendance_table.setHorizontalHeaderLabels([
            "Date", "Course", "Class", "Student ID", "Name", "Status", "Time"
        ])
        self.attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.attendance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.attendance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attendance_table.setSortingEnabled(True)
        table_layout.addWidget(self.attendance_table)
        
        # Records counter
        self.records_counter = QLabel("No records found")
        table_layout.addWidget(self.records_counter)
        
        return table_layout
    
    def create_statistics_section(self):
        """Create the statistics panel"""
        stats_layout = QVBoxLayout()
        
        # Statistics header
        stats_header = QLabel("Statistics")
        stats_header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        stats_layout.addWidget(stats_header)
        
        # Statistics group
        stats_group = QGroupBox("Attendance Summary")
        group_layout = QVBoxLayout()
        
        # Overall statistics
        self.total_sessions_label = QLabel("Total Sessions: 0")
        group_layout.addWidget(self.total_sessions_label)
        
        self.avg_attendance_label = QLabel("Average Attendance: 0%")
        group_layout.addWidget(self.avg_attendance_label)
        
        self.total_students_label = QLabel("Total Students: 0")
        group_layout.addWidget(self.total_students_label)
        
        stats_group.setLayout(group_layout)
        stats_layout.addWidget(stats_group)
        
        # Add chart widget
        self.chart_widget = AttendanceChartWidget()
        stats_layout.addWidget(self.chart_widget)
        
        return stats_layout
    
    def create_action_buttons(self):
        """Create action buttons at the bottom"""
        action_layout = QHBoxLayout()
        
        # Export options
        export_group = QGroupBox("Export Options")
        export_layout = QHBoxLayout()
        
        self.export_pdf_btn = QPushButton("Export to PDF")
        self.export_pdf_btn.clicked.connect(self.export_to_pdf)
        export_layout.addWidget(self.export_pdf_btn)
        
        self.export_csv_btn = QPushButton("Export to CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        export_layout.addWidget(self.export_csv_btn)
        
        # Include chart checkbox
        self.include_chart_cb = QCheckBox("Include chart in report")
        self.include_chart_cb.setChecked(True)
        export_layout.addWidget(self.include_chart_cb)
        
        export_group.setLayout(export_layout)
        action_layout.addWidget(export_group)
        
        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        action_layout.addWidget(self.close_btn)
        
        return action_layout
    
    def load_filter_options(self):
        """Load data for filter dropdowns"""
        # Load course list
        self.course_filter.clear()
        self.course_filter.addItem("All Courses", None)
        
        courses = self.db_service.get_courses()
        for course in courses:
            self.course_filter.addItem(course['course_code'], course['course_code'])
        
        # Load classes list initially with all classes
        self.update_class_filter()
        
    def update_class_filter(self):
        """Update class filter based on selected course"""
        selected_course = self.course_filter.currentData()
        
        self.class_filter.clear()
        self.class_filter.addItem("All Classes", None)
        
        if selected_course:
            classes = self.db_service.get_classes_by_course(selected_course)
        else:
            classes = self.db_service.get_classes()
            
        for class_item in classes:
            self.class_filter.addItem(f"{class_item['class_id']} - {class_item['class_name']}", class_item['class_id'])
    
    def apply_filters(self):
        """Apply selected filters and update data display"""
        # Get filter values
        from_date = self.from_date.date().toString("yyyy-MM-dd")
        to_date = self.to_date.date().toString("yyyy-MM-dd")
        course_code = self.course_filter.currentData()
        class_id = self.class_filter.currentData()
        student_search = self.student_filter.text().strip()
        
        # Build filter criteria
        filters = {
            'from_date': from_date,
            'to_date': to_date,
            'course_code': course_code,
            'class_id': class_id,
            'student_search': student_search
        }
        
        # Get filtered attendance data
        attendance_data = self.db_service.get_filtered_attendance(filters)
        
        # Update table
        self.update_attendance_table(attendance_data)
        
        # Update statistics
        self.update_statistics(filters)
        
    def update_attendance_table(self, attendance_data):
        """Update attendance table with filtered data"""
        self.attendance_table.setRowCount(0)
        
        for row_idx, record in enumerate(attendance_data):
            self.attendance_table.insertRow(row_idx)
            
            # Set data for each column
            self.attendance_table.setItem(row_idx, 0, QTableWidgetItem(record['date']))
            self.attendance_table.setItem(row_idx, 1, QTableWidgetItem(record['course_code']))
            self.attendance_table.setItem(row_idx, 2, QTableWidgetItem(record['class_name']))
            self.attendance_table.setItem(row_idx, 3, QTableWidgetItem(record['student_id']))
            self.attendance_table.setItem(row_idx, 4, QTableWidgetItem(record['name']))
            
            status_item = QTableWidgetItem(record['status'])
            if record['status'] == 'Present':
                status_item.setBackground(QColor(200, 255, 200))  # Light green
            else:
                status_item.setBackground(QColor(255, 200, 200))  # Light red
            self.attendance_table.setItem(row_idx, 5, status_item)
            
            self.attendance_table.setItem(row_idx, 6, QTableWidgetItem(record['timestamp']))
        
        # Update record counter
        record_count = self.attendance_table.rowCount()
        self.records_counter.setText(f"Found {record_count} attendance records")
        self.table_header.setText(f"Attendance Records ({record_count})")
    
    def update_statistics(self, filters):
        """Update statistics panel with calculated data"""
        stats = self.statistics.calculate_statistics(filters)
        
        # Update labels
        self.total_sessions_label.setText(f"Total Sessions: {stats['total_sessions']}")
        self.avg_attendance_label.setText(f"Average Attendance: {stats['attendance_rate']}%")
        self.total_students_label.setText(f"Total Students: {stats['total_students']}")
        
        # Update chart
        self.chart_widget.update_chart(stats['attendance_data'])
    
    def reset_filters(self):
        """Reset all filters to default values"""
        self.from_date.setDate(QDate.currentDate().addDays(-7))
        self.to_date.setDate(QDate.currentDate())
        self.course_filter.setCurrentIndex(0)
        self.student_filter.clear()
        
        # Apply the reset filters
        self.apply_filters()
    
    def export_to_pdf(self):
        """Export current attendance data to PDF"""
        # Get current filter settings
        filters = {
            'from_date': self.from_date.date().toString("yyyy-MM-dd"),
            'to_date': self.to_date.date().toString("yyyy-MM-dd"),
            'course_code': self.course_filter.currentData(),
            'class_id': self.class_filter.currentData(),
            'student_search': self.student_filter.text().strip(),
            'include_chart': self.include_chart_cb.isChecked()
        }
        
        # Get file name from user
        default_filename = f"Attendance_Report_{filters['from_date']}_{filters['to_date']}.pdf"
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", default_filename, "PDF Files (*.pdf)"
        )
        
        if not file_name:
            return
            
        # Generate and save the report
        if self.report_generator.generate_pdf_report(file_name, filters):
            QMessageBox.information(self, "Export Complete", f"Report saved to {file_name}")
        else:
            QMessageBox.warning(self, "Export Failed", "Failed to generate PDF report")
    
    def export_to_csv(self):
        """Export current attendance data to CSV"""
        # Get current filter settings
        filters = {
            'from_date': self.from_date.date().toString("yyyy-MM-dd"),
            'to_date': self.to_date.date().toString("yyyy-MM-dd"),
            'course_code': self.course_filter.currentData(),
            'class_id': self.class_filter.currentData(),
            'student_search': self.student_filter.text().strip()
        }
        
        # Get file name from user
        default_filename = f"Attendance_Data_{filters['from_date']}_{filters['to_date']}.csv"
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", default_filename, "CSV Files (*.csv)"
        )
        
        if not file_name:
            return
            
        # Generate and save the report
        if self.report_generator.generate_csv_report(file_name, filters):
            QMessageBox.information(self, "Export Complete", f"Data exported to {file_name}")
        else:
            QMessageBox.warning(self, "Export Failed", "Failed to generate CSV report")