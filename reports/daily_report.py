"""
Daily Report View - Shows attendance data for a specific day
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QTableWidget, QTableWidgetItem, QDateEdit,
                            QPushButton, QHeaderView, QSplitter)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QColor

from widgets.stat_card import StatCard
from widgets.attendance_chart import AttendancePieChart

class DailyReportView(QWidget):
    """Widget for viewing daily attendance reports"""
    
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
        
        # Top row of stat cards
        stats_layout = QHBoxLayout()
        
        self.total_classes_card = StatCard("Total Classes", "0")
        self.total_students_card = StatCard("Total Students", "0")
        self.avg_attendance_card = StatCard("Avg. Attendance", "0%")
        
        stats_layout.addWidget(self.total_classes_card)
        stats_layout.addWidget(self.total_students_card)
        stats_layout.addWidget(self.avg_attendance_card)
        
        # Attendance table
        table_label = QLabel("Class Sessions")
        table_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Class", "Course", "Start Time", "End Time", 
            "Instructor", "Attendance", "Rate"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.show_class_details)
        
        # Chart and table in a splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Chart widget
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        
        chart_title = QLabel("Attendance Breakdown")
        chart_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        chart_layout.addWidget(chart_title)
        
        self.chart = AttendancePieChart()
        chart_layout.addWidget(self.chart)
        
        # Table widget
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.addWidget(table_label)
        table_layout.addWidget(self.table)
        
        # Add to splitter
        splitter.addWidget(chart_widget)
        splitter.addWidget(table_widget)
        splitter.setSizes([300, 400])
        
        # Add components to main layout
        layout.addLayout(stats_layout)
        layout.addWidget(splitter, 1)
        
        self.setLayout(layout)
        
    def update_report(self, filters):
        """Update the report with new filter settings"""
        self.current_filters = filters
        
        # Get the selected date
        selected_date = filters.get('date', datetime.now().strftime("%Y-%m-%d"))
        
        # Fetch data
        self.attendance_data = self.db.get_daily_attendance(selected_date)
        
        # Update UI with data
        self.update_stats()
        self.update_table()
        self.update_chart()
    
    def update_stats(self):
        """Update the statistic cards"""
        if self.attendance_data is None or self.attendance_data.empty:
            self.total_classes_card.set_value("0")
            self.total_students_card.set_value("0")
            self.avg_attendance_card.set_value("0%")
            return
        
        # Calculate statistics
        total_classes = len(self.attendance_data)
        total_students = self.attendance_data['total_students'].sum() if not self.attendance_data.empty else 0
        total_present = self.attendance_data['present_count'].sum() if not self.attendance_data.empty else 0
        
        # Calculate average attendance rate
        if total_students > 0:
            avg_rate = total_present / total_students * 100
        else:
            avg_rate = 0
        
        # Update cards
        self.total_classes_card.set_value(str(total_classes))
        self.total_students_card.set_value(str(total_students))
        self.avg_attendance_card.set_value(f"{avg_rate:.1f}%")
        
        # Set card colors based on attendance rate
        if avg_rate < 60:
            self.avg_attendance_card.set_color("#ff4444")  # Red for low attendance
        elif avg_rate < 80:
            self.avg_attendance_card.set_color("#ffbb33")  # Orange for medium attendance
        else:
            self.avg_attendance_card.set_color("#00C851")  # Green for good attendance
    
    def update_table(self):
        """Update the attendance table"""
        self.table.setRowCount(0)
        
        if self.attendance_data is None or self.attendance_data.empty:
            return
            
        self.table.setRowCount(len(self.attendance_data))
        
        for i, (_, row) in enumerate(self.attendance_data.iterrows()):
            # Calculate attendance rate
            rate = row['present_count'] / row['total_students'] * 100 if row['total_students'] > 0 else 0
            
            # Set cell values
            self.table.setItem(i, 0, QTableWidgetItem(row['class_name']))
            self.table.setItem(i, 1, QTableWidgetItem(row['course_code']))
            self.table.setItem(i, 2, QTableWidgetItem(row['start_time']))
            self.table.setItem(i, 3, QTableWidgetItem(row['end_time']))
            self.table.setItem(i, 4, QTableWidgetItem(str(row['instructor_name'])))
            self.table.setItem(i, 5, QTableWidgetItem(f"{row['present_count']} / {row['total_students']}"))
            
            rate_item = QTableWidgetItem(f"{rate:.1f}%")
            
            # Color code based on attendance rate
            if rate < 60:
                rate_item.setForeground(QColor("#ff4444"))  # Red for low attendance
            elif rate < 80:
                rate_item.setForeground(QColor("#ffbb33"))  # Orange for medium attendance
            else:
                rate_item.setForeground(QColor("#00C851"))  # Green for good attendance
                
            self.table.setItem(i, 6, rate_item)
            
            # Store session_id as hidden data for the first cell
            self.table.item(i, 0).setData(Qt.UserRole, row['session_id'])
    
    def update_chart(self):
        """Update the attendance chart"""
        if self.attendance_data is None or self.attendance_data.empty:
            self.chart.clear()
            return
        
        # Prepare data for the chart
        present_total = self.attendance_data['present_count'].sum()
        total_students = self.attendance_data['total_students'].sum()
        absent_total = total_students - present_total
        
        # Update the chart
        data = [
            ('Present', present_total),
            ('Absent', absent_total)
        ]
        self.chart.update_chart(data)
    
    def show_class_details(self, index):
        """Show detailed view of a selected class session"""
        # Get the session_id from the clicked row
        session_id = self.table.item(index.row(), 0).data(Qt.UserRole)
        
        # TODO: Implement session details dialog
        print(f"Show details for session {session_id}")
    
    def export_pdf(self, filename, filters):
        """Export the current report as PDF"""
        # Ensure we have data
        if self.attendance_data is None or self.attendance_data.empty:
            raise ValueError("No data to export")
        
        # Get the selected date
        selected_date = filters.get('date', datetime.now().strftime("%Y-%m-%d"))
        
        # Generate PDF
        self.report_generator.generate_daily_report_pdf(
            filename, 
            selected_date,
            self.attendance_data
        )
    
    def export_csv(self, filename, filters):
        """Export the current report as CSV"""
        # Ensure we have data
        if self.attendance_data is None or self.attendance_data.empty:
            raise ValueError("No data to export")
            
        # Save DataFrame to CSV
        self.attendance_data.to_csv(filename, index=False)