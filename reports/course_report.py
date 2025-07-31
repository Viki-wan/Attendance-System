"""
Course Report View - Shows attendance analytics for a specific course
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QTableWidget, QTableWidgetItem, QComboBox,
                            QPushButton, QHeaderView, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QColor

from widgets.stat_card import StatCard
from widgets.attendance_chart import AttendanceLineChart, AttendancePieChart

class CourseReportView(QWidget):
    """Widget for viewing course-specific attendance reports"""
    
    def __init__(self, db, report_generator):
        super().__init__()
        self.db = db
        self.report_generator = report_generator
        
        # Store current data
        self.attendance_data = None
        self.current_filters = {}
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout()
        
        # Course info header
        course_info_layout = QHBoxLayout()
        
        self.course_title = QLabel("Select a course to view attendance data")
        self.course_title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        
        course_info_layout.addWidget(self.course_title)
        course_info_layout.addStretch()
        
        # Stat cards row
        stats_layout = QHBoxLayout()
        
        self.sessions_card = StatCard("Total Sessions", "0")
        self.attendance_rate_card = StatCard("Attendance Rate", "0%")
        self.students_card = StatCard("Enrolled Students", "0")
        self.avg_students_card = StatCard("Avg. Students per Session", "0")
        
        stats_layout.addWidget(self.sessions_card)
        stats_layout.addWidget(self.attendance_rate_card)
        stats_layout.addWidget(self.students_card)
        stats_layout.addWidget(self.avg_students_card)
        
        # Chart and table in a splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Charts widget
        charts_widget = QWidget()
        charts_layout = QVBoxLayout(charts_widget)
        
        trend_title = QLabel("Attendance Trend")
        trend_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        charts_layout.addWidget(trend_title)
        
        self.trend_chart = AttendanceLineChart()
        charts_layout.addWidget(self.trend_chart)
        
        # Table widget
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        
        table_title = QLabel("Session Details")
        table_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        table_layout.addWidget(table_title)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Date", "Time", "Present", "Total", "Rate", "Notes"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        table_layout.addWidget(self.table)
        
        # Add to splitter
        splitter.addWidget(charts_widget)
        splitter.addWidget(table_widget)
        splitter.setSizes([300, 400])
        
        # Add components to main layout
        layout.addLayout(course_info_layout)
        layout.addLayout(stats_layout)
        layout.addWidget(splitter, 1)
        
        self.setLayout(layout)
        
    def update_report(self, filters):
        """Update the report with new filter settings"""
        self.current_filters = filters
        
        # Get course code and date range
        course_code = filters.get('course')
        start_date = filters.get('date_from')
        end_date = filters.get('date_to')
        
        if not course_code:
            # No course selected
            self.course_title.setText("Select a course to view attendance data")
            self.attendance_data = None
            self.update_stats()
            self.update_table()
            self.update_charts()
            return
        
        # Fetch data
        self.attendance_data = self.db.get_course_attendance(course_code, start_date, end_date)
        
        # Update the course title
        courses = self.db.fetch_all_courses()
        course_name = next((c['name'] for c in courses if c['code'] == course_code), course_code)
        self.course_title.setText(f"{course_code}: {course_name}")
        
        # Update UI with data
        self.update_stats()
        self.update_table()
        self.update_charts()
    
    def update_stats(self):
        """Update the statistic cards"""
        if self.attendance_data is None or self.attendance_data.empty:
            self.sessions_card.set_value("0")
            self.attendance_rate_card.set_value("0%")
            self.students_card.set_value("0")
            self.avg_students_card.set_value("0")
            return
        
        # Calculate statistics
        total_sessions = len(self.attendance_data)
        total_students = self.attendance_data['total_students'].iloc[0] if not self.attendance_data.empty else 0
        total_present = self.attendance_data['present_count'].sum() if not self.attendance_data.empty else 0
        
        # Total possible attendances
        total_possible = total_students * total_sessions
        
        # Calculate attendance rate
        if total_possible > 0:
            attendance_rate = total_present / total_possible * 100
        else:
            attendance_rate = 0
        
        # Calculate average students per session
        avg_students = total_present / total_sessions if total_sessions > 0 else 0
        
        # Update cards
        self.sessions_card.set_value(str(total_sessions))
        self.attendance_rate_card.set_value(f"{attendance_rate:.1f}%")
        self.students_card.set_value(str(total_students))
        self.avg_students_card.set_value(f"{avg_students:.1f}")
        
        # Set card colors based on attendance rate
        if attendance_rate < 60:
            self.attendance_rate_card.set_color("#ff4444")  # Red for low attendance
        elif attendance_rate < 80:
            self.attendance_rate_card.set_color("#ffbb33")  # Orange for medium attendance
        else:
            self.attendance_rate_card.set_color("#00C851")  # Green for good attendance
    
    def update_table(self):
        """Update the sessions table"""
        self.table.setRowCount(0)
        
        if self.attendance_data is None or self.attendance_data.empty:
            return
            
        self.table.setRowCount(len(self.attendance_data))
        
        for i, (_, row) in enumerate(self.attendance_data.iterrows()):
            # Calculate attendance rate
            rate = row['present_count'] / row['total_students'] * 100 if row['total_students'] > 0 else 0
            
            # Format date and time
            date_str = row['date']
            time_str = row['start_time']
            
            # Set cell values
            self.table.setItem(i, 0, QTableWidgetItem(date_str))
            self.table.setItem(i, 1, QTableWidgetItem(time_str))
            self.table.setItem(i, 2, QTableWidgetItem(str(row['present_count'])))
            self.table.setItem(i, 3, QTableWidgetItem(str(row['total_students'])))
            
            rate_item = QTableWidgetItem(f"{rate:.1f}%")
            
            # Color code based on attendance rate
            if rate < 60:
                rate_item.setForeground(QColor("#ff4444"))  # Red for low attendance
            elif rate < 80:
                rate_item.setForeground(QColor("#ffbb33"))  # Orange for medium attendance
            else:
                rate_item.setForeground(QColor("#00C851"))  # Green for good attendance
                
            self.table.setItem(i, 4, rate_item)
            
            # Add notes based on attendance rate
            notes = ""
            if rate < 60:
                notes = "Low attendance"
            elif rate < 70:
                notes = "Below average"
            elif rate > 90:
                notes = "Excellent attendance"
                
            self.table.setItem(i, 5, QTableWidgetItem(notes))
            
            # Store session_id as hidden data for the first cell
            self.table.item(i, 0).setData(Qt.UserRole, row['session_id'])
    
    def update_charts(self):
        """Update attendance trend chart"""
        if self.attendance_data is None or self.attendance_data.empty:
            self.trend_chart.clear()
            return
        
        # Prepare data for the chart - sort by date
        df = self.attendance_data.sort_values('date')
        
        dates = df['date'].tolist()
        rates = []
        
        for _, row in df.iterrows():
            rate = row['present_count'] / row['total_students'] * 100 if row['total_students'] > 0 else 0
            rates.append(rate)
        
        # Update the chart
        self.trend_chart.update_chart(dates, rates, "Attendance Rate (%)")
    
    def export_pdf(self, filename, filters):
        """Export the current report as PDF"""
        # Ensure we have data
        if self.attendance_data is None or self.attendance_data.empty:
            raise ValueError("No data to export")
        
        # Get course information
        course_code = filters.get('course')
        start_date = filters.get('date_from')
        end_date = filters.get('date_to')
        
        courses = self.db.fetch_all_courses()
        course_name = next((c['name'] for c in courses if c['code'] == course_code), course_code)
        
        # Generate PDF
        self.report_generator.generate_course_report_pdf(
            filename, 
            course_code,
            course_name,
            start_date,
            end_date,
            self.attendance_data
        )
    
    def export_csv(self, filename, filters):
        """Export the current report as CSV"""
        # Ensure we have data
        if self.attendance_data is None or self.attendance_data.empty:
            raise ValueError("No data to export")
            
        # Save DataFrame to CSV
        self.attendance_data.to_csv(filename, index=False)