import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QApplication, QLabel, 
                            QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
                            QDateEdit, QHeaderView, QFileDialog, QMessageBox, 
                            QCheckBox, QGroupBox, QGridLayout, QMainWindow)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QAbstractPrintDialog
from PyQt5.QtGui import QTextDocument

from admin.attendance_report_service import AttendanceReportService


class ViewAttendanceWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 View Attendance Reports")
        self.setGeometry(300, 200, 1000, 700)
        self.setObjectName("ViewAttendanceWindow")
        
        # Initialize services
        self.report_service = AttendanceReportService()
        
        # Initialize UI
        self.init_ui()
        
        # Set default date range to today
        today = QDate.currentDate()
        self.date_from.setDate(today)
        self.date_to.setDate(today)
        
        # Load initial data
        self.load_filter_data()
        self.apply_filters()
        
    def init_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title
        title_label = QLabel("Attendance Reports", self)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; margin: 10px 0;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Filters section
        filter_group = QGroupBox("Report Filters", self)
        filter_layout = QGridLayout()
        
        # Date filters
        date_label = QLabel("Date Range:", self)
        self.date_from = QDateEdit(self)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setCalendarPopup(True)
        
        date_to_label = QLabel("to", self)
        date_to_label.setAlignment(Qt.AlignCenter)
        
        self.date_to = QDateEdit(self)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        
        filter_layout.addWidget(date_label, 0, 0)
        filter_layout.addWidget(self.date_from, 0, 1)
        filter_layout.addWidget(date_to_label, 0, 2)
        filter_layout.addWidget(self.date_to, 0, 3)
        
        # Course filter
        course_label = QLabel("Course:", self)
        self.course_filter = QComboBox(self)
        self.course_filter.setMinimumWidth(150)
        filter_layout.addWidget(course_label, 0, 4)
        filter_layout.addWidget(self.course_filter, 0, 5)
        
        # Class filter
        class_label = QLabel("Class:", self)
        self.class_filter = QComboBox(self)
        self.class_filter.setMinimumWidth(150)
        filter_layout.addWidget(class_label, 1, 0)
        filter_layout.addWidget(self.class_filter, 1, 1)
        
        # Student filter
        student_label = QLabel("Student:", self)
        self.student_filter = QComboBox(self)
        self.student_filter.setMinimumWidth(150)
        filter_layout.addWidget(student_label, 1, 2)
        filter_layout.addWidget(self.student_filter, 1, 3)
        
        # Status filter
        status_label = QLabel("Status:", self)
        self.status_filter = QComboBox(self)
        self.status_filter.addItems(["All", "Present", "Absent"])
        filter_layout.addWidget(status_label, 1, 4)
        filter_layout.addWidget(self.status_filter, 1, 5)
        
        # Year of study filter
        year_label = QLabel("Year of Study:", self)
        self.year_filter = QComboBox(self)
        self.year_filter.addItem("All Years")
        self.year_filter.addItem("1st Year")
        self.year_filter.addItem("2nd Year")
        self.year_filter.addItem("3rd Year")
        self.year_filter.addItem("4th Year")
        filter_layout.addWidget(year_label, 2, 0)
        filter_layout.addWidget(self.year_filter, 2, 1)
        
        # Additional options for reports
        options_layout = QHBoxLayout()
        
        self.include_absent_cb = QCheckBox("Include Absent Students", self)
        self.include_absent_cb.setChecked(True)
        options_layout.addWidget(self.include_absent_cb)
        
        self.group_by_date_cb = QCheckBox("Group by Date", self)
        options_layout.addWidget(self.group_by_date_cb)
        
        self.group_by_class_cb = QCheckBox("Group by Class", self)
        options_layout.addWidget(self.group_by_class_cb)
        
        filter_layout.addLayout(options_layout, 2, 2, 1, 4)
        
        # Apply filters button
        filter_button_layout = QHBoxLayout()
        
        self.filter_button = QPushButton("Apply Filters", self)
        self.filter_button.clicked.connect(self.apply_filters)
        self.filter_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        filter_button_layout.addWidget(self.filter_button)
        
        self.reset_button = QPushButton("Reset Filters", self)
        self.reset_button.clicked.connect(self.reset_filters)
        self.reset_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; padding: 8px;")
        filter_button_layout.addWidget(self.reset_button)
        
        filter_layout.addLayout(filter_button_layout, 3, 0, 1, 6)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # Stats summary section
        stats_layout = QHBoxLayout()
        
        # Total sessions
        self.sessions_label = QLabel("Total Sessions: 0", self)
        self.sessions_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e6f7ff; border-radius: 5px;")
        stats_layout.addWidget(self.sessions_label)
        
        # Total students
        self.students_label = QLabel("Total Students: 0", self)
        self.students_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e6f7ff; border-radius: 5px;")
        stats_layout.addWidget(self.students_label)
        
        # Present count
        self.present_label = QLabel("Present: 0", self)
        self.present_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #e6ffed; border-radius: 5px;")
        stats_layout.addWidget(self.present_label)
        
        # Absent count
        self.absent_label = QLabel("Absent: 0", self)
        self.absent_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #ffebee; border-radius: 5px;")
        stats_layout.addWidget(self.absent_label)
        
        # Attendance rate
        self.rate_label = QLabel("Attendance Rate: 0%", self)
        self.rate_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #fff9c4; border-radius: 5px;")
        stats_layout.addWidget(self.rate_label)
        
        layout.addLayout(stats_layout)
        
        # Attendance data table
        table_label = QLabel("Attendance Records:", self)
        table_label.setStyleSheet("font-size: 12pt; font-weight: bold; margin-top: 10px;")
        layout.addWidget(table_label)
        
        self.attendance_table = QTableWidget(self)
        self.attendance_table.setColumnCount(7)
        self.attendance_table.setHorizontalHeaderLabels(
            ["Student ID", "Student Name", "Course", "Class", "Date", "Time", "Status"]
        )
        header = self.attendance_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.attendance_table)
        
        # Export buttons
        export_layout = QHBoxLayout()
        
        self.export_csv_button = QPushButton("Export to CSV", self)
        self.export_csv_button.clicked.connect(self.export_to_csv)
        self.export_csv_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        export_layout.addWidget(self.export_csv_button)
        
        self.export_pdf_button = QPushButton("Export to PDF", self)
        self.export_pdf_button.clicked.connect(self.export_to_pdf)
        self.export_pdf_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        export_layout.addWidget(self.export_pdf_button)
        
        self.print_button = QPushButton("Print Report", self)
        self.print_button.clicked.connect(self.print_report)
        self.print_button.setStyleSheet("background-color: #9c27b0; color: white; font-weight: bold; padding: 8px;")
        export_layout.addWidget(self.print_button)
        
        self.student_report_button = QPushButton("Student-wise Report", self)
        self.student_report_button.clicked.connect(self.generate_student_report)
        self.student_report_button.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; padding: 8px;")
        export_layout.addWidget(self.student_report_button)
        
        self.class_report_button = QPushButton("Class-wise Report", self)
        self.class_report_button.clicked.connect(self.generate_class_report)
        self.class_report_button.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; padding: 8px;")
        export_layout.addWidget(self.class_report_button)
        
        layout.addLayout(export_layout)
        
        # Connect year_filter to update_class_filter
        self.year_filter.currentIndexChanged.connect(self.update_class_filter)
        
    def load_filter_data(self):
        """Load data for filter dropdowns"""
        # Load courses
        courses = self.report_service.get_all_courses()
        self.course_filter.clear()
        self.course_filter.addItem("All Courses")
        for course in courses:
            self.course_filter.addItem(f"{course['course_code']} - {course['course_name']}", course['course_code'])
        
        # Load classes
        classes = self.report_service.get_all_classes()
        self.class_filter.clear()
        self.class_filter.addItem("All Classes")
        for class_item in classes:
            display_text = f"{class_item['class_id']} - {class_item['class_name']}"
            self.class_filter.addItem(display_text, class_item['class_id'])
        
        # Load students
        students = self.report_service.get_all_students()
        self.student_filter.clear()
        self.student_filter.addItem("All Students")
        for student in students:
            display_text = f"{student['student_id']} - {student['name']}"
            self.student_filter.addItem(display_text, student['student_id'])
            
        # Connect signal for course filter to update classes
        self.course_filter.currentIndexChanged.connect(self.update_class_filter)
        
    def update_class_filter(self):
        """Update class filter based on selected course and year"""
        course_code = None
        if self.course_filter.currentIndex() > 0:
            course_code = self.course_filter.currentData()
        year = self.year_filter.currentIndex()
        year = None if year == 0 else year

        classes = self.report_service.get_classes_by_course_and_year(course_code, year)
        self.class_filter.clear()
        self.class_filter.addItem("All Classes")
        for class_item in classes:
            display_text = f"{class_item['class_id']} - {class_item['class_name']}"
            self.class_filter.addItem(display_text, class_item['class_id'])
            
    def reset_filters(self):
        """Reset all filters to default"""
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_to.setDate(QDate.currentDate())
        self.course_filter.setCurrentIndex(0)
        self.class_filter.setCurrentIndex(0)
        self.student_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.year_filter.setCurrentIndex(0)
        self.include_absent_cb.setChecked(True)
        self.group_by_date_cb.setChecked(False)
        self.group_by_class_cb.setChecked(False)
        
        # Apply reset filters
        self.apply_filters()
            
    def apply_filters(self):
        """Apply selected filters and update the table"""
        # Get filter values
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        # Fix course filter extraction
        course = None
        if self.course_filter.currentIndex() > 0:
            course = self.course_filter.currentData()
        
        class_id = None
        if self.class_filter.currentIndex() > 0:
            class_id = self.class_filter.currentData()
            
        student_id = None
        if self.student_filter.currentIndex() > 0:
            student_id = self.student_filter.currentData()
            
        status = self.status_filter.currentText()
        status = None if status == "All" else status
        
        year = self.year_filter.currentIndex()
        year = None if year == 0 else year
        
        include_absent = self.include_absent_cb.isChecked()
        
        # Get attendance data based on filters
        attendance_data = self.report_service.get_filtered_attendance(
            date_from, date_to, course, class_id, student_id, status, include_absent, year
        )
        
        # Update stats
        self.update_stats_summary(attendance_data)
        
        # Apply grouping if needed
        if self.group_by_date_cb.isChecked():
            attendance_data = self.report_service.group_by_date(attendance_data)
        elif self.group_by_class_cb.isChecked():
            attendance_data = self.report_service.group_by_class(attendance_data)
        
        # Update the table
        self.update_attendance_table(attendance_data)
        
    def update_stats_summary(self, attendance_data):
        """Update the statistics summary labels"""
        # Count unique sessions, students, present and absent records
        sessions = set()
        students = set()
        present_count = 0
        absent_count = 0

        for record in attendance_data:
            # Use (date, time, class_id) as a unique session identifier
            if 'date' in record and 'time' in record and 'class_id' in record:
                sessions.add((record['date'], record['time'], record['class_id']))
            if 'student_id' in record:
                students.add(record['student_id'])
            if 'status' in record:
                if record['status'] == 'Present':
                    present_count += 1
                elif record['status'] == 'Absent':
                    absent_count += 1

        total_records = present_count + absent_count
        attendance_rate = (present_count / total_records) * 100 if total_records > 0 else 0

        # Update labels
        self.sessions_label.setText(f"Total Sessions: {len(sessions)}")
        self.students_label.setText(f"Total Students: {len(students)}")
        self.present_label.setText(f"Present: {present_count}")
        self.absent_label.setText(f"Absent: {absent_count}")
        self.rate_label.setText(f"Attendance Rate: {attendance_rate:.1f}%")
        
    def update_attendance_table(self, attendance_data):
        """Update the attendance table with filtered data"""
        self.attendance_table.setRowCount(0)
        
        for record in attendance_data:
            row = self.attendance_table.rowCount()
            self.attendance_table.insertRow(row)
            
            # Add data to cells
            self.attendance_table.setItem(row, 0, QTableWidgetItem(str(record.get('student_id', ''))))
            self.attendance_table.setItem(row, 1, QTableWidgetItem(str(record.get('student_name', ''))))
            self.attendance_table.setItem(row, 2, QTableWidgetItem(str(record.get('course_code', ''))))
            self.attendance_table.setItem(row, 3, QTableWidgetItem(str(record.get('class_name', ''))))
            self.attendance_table.setItem(row, 4, QTableWidgetItem(str(record.get('date', ''))))
            self.attendance_table.setItem(row, 5, QTableWidgetItem(str(record.get('time', ''))))
            
            # Set status with color coding
            status = record.get('status', '')
            status_item = QTableWidgetItem(status)
            
            if status == 'Present':
                status_item.setBackground(QColor(200, 255, 200))  # Light green
            elif status == 'Absent':
                status_item.setBackground(QColor(255, 200, 200))  # Light red
                
            self.attendance_table.setItem(row, 6, status_item)
    
    def export_to_csv(self):
        """Export current attendance data to CSV"""
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save CSV Report", 
            f"Attendance_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        
        if file_name:
            try:
                # Get current table data
                rows = self.attendance_table.rowCount()
                cols = self.attendance_table.columnCount()
                
                # Write to CSV
                with open(file_name, 'w', encoding='utf-8') as f:
                    # Write header
                    header = []
                    for col in range(cols):
                        header.append(self.attendance_table.horizontalHeaderItem(col).text())
                    f.write(','.join(header) + '\n')
                    
                    # Write data rows
                    for row in range(rows):
                        row_data = []
                        for col in range(cols):
                            item = self.attendance_table.item(row, col)
                            row_data.append(item.text() if item else '')
                        f.write(','.join(row_data) + '\n')
                
                QMessageBox.information(self, "Export Successful", 
                                       f"Report exported successfully to {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error exporting report: {str(e)}")
    
    def export_to_pdf(self):
        """Export current attendance data to PDF"""
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save PDF Report", 
            f"Attendance_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
            "PDF Files (*.pdf)"
        )
        
        if file_name:
            try:
                # Create a printer and set to PDF
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(file_name)
                
                # Get report title based on filters
                report_title = "Attendance Report"
                if self.course_filter.currentIndex() > 0:
                    report_title += f" - {self.course_filter.currentText()}"
                if self.class_filter.currentIndex() > 0:
                    report_title += f" - {self.class_filter.currentText().split(' - ')[1]}"
                if self.year_filter.currentIndex() > 0:
                    report_title += f" - Year {self.year_filter.currentText()}"
                
                date_range = f"{self.date_from.date().toString('yyyy-MM-dd')} to {self.date_to.date().toString('yyyy-MM-dd')}"
                
                # Create HTML content for the PDF
                html_content = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; }}
                        h1 {{ text-align: center; margin-bottom: 10px; }}
                        h3 {{ text-align: center; margin-top: 5px; color: #666; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background-color: #f2f2f2; }}
                        .present {{ background-color: #c8ffc8; }}
                        .absent {{ background-color: #ffc8c8; }}
                        .stats {{ display: flex; justify-content: space-between; margin: 15px 0; }}
                        .stat-item {{ padding: 8px; border-radius: 5px; background-color: #f0f0f0; }}
                    </style>
                </head>
                <body>
                    <h1>{report_title}</h1>
                    <h3>Period: {date_range}</h3>
                    
                    <div class="stats">
                        <span class="stat-item">Sessions: {self.sessions_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Students: {self.students_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Present: {self.present_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Absent: {self.absent_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Rate: {self.rate_label.text().split(': ')[1]}</span>
                    </div>
                    
                    <table>
                        <tr>
                """
                
                # Add table headers
                for col in range(self.attendance_table.columnCount()):
                    header_text = self.attendance_table.horizontalHeaderItem(col).text()
                    html_content += f"<th>{header_text}</th>"
                
                html_content += "</tr>"
                
                # Add table data
                for row in range(self.attendance_table.rowCount()):
                    html_content += "<tr>"
                    
                    for col in range(self.attendance_table.columnCount()):
                        item = self.attendance_table.item(row, col)
                        cell_text = item.text() if item else ""
                        
                        # Add class for status column
                        css_class = ""
                        if col == 6:  # Status column
                            if cell_text == "Present":
                                css_class = " class='present'"
                            elif cell_text == "Absent":
                                css_class = " class='absent'"
                                
                        html_content += f"<td{css_class}>{cell_text}</td>"
                        
                    html_content += "</tr>"
                
                html_content += f"""
                    </table>
                    <p style="margin-top: 20px; text-align: center; color: #666;">
                        Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </body>
                </html>
                """
                
                # Create a document and set the HTML
                document = QTextDocument()
                document.setHtml(html_content)
                
                # Print to PDF
                document.print_(printer)
                
                QMessageBox.information(self, "Export Successful", 
                                      f"Report exported successfully to {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Error exporting report: {str(e)}")
    
    def print_report(self):
        """Print the current attendance report"""
        try:
            # Create a printer
            printer = QPrinter(QPrinter.HighResolution)
            
            # Show print dialog
            print_dialog = QPrintDialog(printer, self)
            if print_dialog.exec_() == QPrintDialog.Accepted:
                # Get report title based on filters
                report_title = "Attendance Report"
                if self.course_filter.currentIndex() > 0:
                    report_title += f" - {self.course_filter.currentText()}"
                if self.class_filter.currentIndex() > 0:
                    report_title += f" - {self.class_filter.currentText().split(' - ')[1]}"
                if self.year_filter.currentIndex() > 0:
                    report_title += f" - Year {self.year_filter.currentText()}"
                
                date_range = f"{self.date_from.date().toString('yyyy-MM-dd')} to {self.date_to.date().toString('yyyy-MM-dd')}"
                
                # Create HTML content for printing
                html_content = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; }}
                        h1 {{ text-align: center; margin-bottom: 10px; }}
                        h3 {{ text-align: center; margin-top: 5px; color: #666; }}
                        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                        th {{ background-color: #f2f2f2; }}
                        .present {{ background-color: #c8ffc8; }}
                        .absent {{ background-color: #ffc8c8; }}
                        .stats {{ display: flex; justify-content: space-between; margin: 15px 0; }}
                        .stat-item {{ padding: 8px; border-radius: 5px; background-color: #f0f0f0; }}
                    </style>
                </head>
                <body>
                    <h1>{report_title}</h1>
                    <h3>Period: {date_range}</h3>
                    
                    <div class="stats">
                        <span class="stat-item">Sessions: {self.sessions_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Students: {self.students_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Present: {self.present_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Absent: {self.absent_label.text().split(': ')[1]}</span>
                        <span class="stat-item">Rate: {self.rate_label.text().split(': ')[1]}</span>
                    </div>
                    
                    <table>
                        <tr>
                """
                
                # Add table headers
                for col in range(self.attendance_table.columnCount()):
                    header_text = self.attendance_table.horizontalHeaderItem(col).text()
                    html_content += f"<th>{header_text}</th>"
                
                html_content += "</tr>"
                
                # Add table data
                for row in range(self.attendance_table.rowCount()):
                    html_content += "<tr>"
                    
                    for col in range(self.attendance_table.columnCount()):
                        item = self.attendance_table.item(row, col)
                        cell_text = item.text() if item else ""
                        
                        # Add class for status column
                        css_class = ""
                        if col == 6:  # Status column
                            if cell_text == "Present":
                                css_class = " class='present'"
                            elif cell_text == "Absent":
                                css_class = " class='absent'"
                                
                        html_content += f"<td{css_class}>{cell_text}</td>"
                        
                    html_content += "</tr>"
                
                html_content += """
                    </table>
                    <p style="margin-top: 20px; text-align: center; color: #666;">
                        Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </p>
                </body>
                </html>
                """.format(datetime=datetime)
                
                # Create a document and set the HTML
                document = QTextDocument()
                document.setHtml(html_content)
                
                # Print the document
                document.print_(printer)
                
        except Exception as e:
            QMessageBox.critical(self, "Print Failed", f"Error printing report: {str(e)}")
    
    def generate_student_report(self):
        """Generate a student-wise attendance report"""
        if self.attendance_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No attendance data to generate report")
            return
        
        try:
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save Student Report", 
                f"Student_Attendance_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                "PDF Files (*.pdf)"
            )
            
            if file_name:
                # Create a printer and set to PDF
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(file_name)
                
                # Get report data grouped by student
                date_from = self.date_from.date().toString("yyyy-MM-dd")
                date_to = self.date_to.date().toString("yyyy-MM-dd")
                
                # Fix course filter extraction
                course = None
                if self.course_filter.currentIndex() > 0:
                    course = self.course_filter.currentData()
                
                class_id = None
                if self.class_filter.currentIndex() > 0:
                    class_id = self.class_filter.currentData()
                
                year = self.year_filter.currentIndex()
                year = None if year == 0 else year
                
                # Get the include_absent value from the checkbox
                include_absent = self.include_absent_cb.isChecked()
                
                # Get student-wise report data
                report_data = self.report_service.generate_student_wise_report(
                    date_from, date_to, course, class_id, year, include_absent
                )
                
                # Generate HTML content for the report
                html_content = """
                <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; }
                        h1 { text-align: center; margin-bottom: 10px; }
                        h3 { text-align: center; margin-top: 5px; color: #666; }
                        h2 { margin-top: 30px; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
                        table { width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }
                        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                        th { background-color: #f2f2f2; }
                        .present { color: green; }
                        .absent { color: red; }
                        .student-summary { background-color: #f9f9f9; padding: 10px; margin: 15px 0; border-radius: 5px; }
                        .page-break { page-break-after: always; }
                        .summary-item { display: inline-block; margin-right: 20px; font-weight: bold; }
                    </style>
                </head>
                <body>
                    <h1>Student Attendance Report</h1>
                    <h3>Period: """ + f"{date_from} to {date_to}</h3>"
                
                # Add each student's data
                for i, student in enumerate(report_data):
                    # Add page break except for first student
                    if i > 0:
                        html_content += '<div class="page-break"></div>'
                    
                    html_content += f"""
                    <h2>Student: {student['name']} ({student['student_id']})</h2>
                    
                    <div class="student-summary">
                        <div class="summary-item">Course: {student.get('course_code', 'Multiple')}</div>
                        <div class="summary-item">Class: {student.get('class_name', 'Multiple')}</div>
                        <div class="summary-item">Present: {student['present_count']}</div>
                        <div class="summary-item">Absent: {student['absent_count']}</div>
                        <div class="summary-item">Total Sessions: {student['total_sessions']}</div>
                        <div class="summary-item">Attendance Rate: {student['attendance_rate']:.1f}%</div>
                    </div>
                    
                    <h3>Attendance Details</h3>
                    <table>
                        <tr>
                            <th>Date</th>
                            <th>Class</th>
                            <th>Course</th>
                            <th>Time</th>
                            <th>Status</th>
                        </tr>
                    """
                    
                    # Add attendance records for this student
                    for record in student['attendance_records']:
                        status_class = "present" if record['status'] == 'Present' else "absent"
                        html_content += f"""
                        <tr>
                            <td>{record['date']}</td>
                            <td>{record['class_name']}</td>
                            <td>{record['course_code']}</td>
                            <td>{record['time']}</td>
                            <td class="{status_class}">{record['status']}</td>
                        </tr>
                        """
                    
                    html_content += "</table>"
                    
                    # Add attendance trend if available
                    if 'monthly_attendance' in student:
                        html_content += """
                        <h3>Monthly Attendance Trend</h3>
                        <table>
                            <tr>
                                <th>Month</th>
                                <th>Present</th>
                                <th>Absent</th>
                                <th>Rate</th>
                            </tr>
                        """
                        
                        for month_data in student['monthly_attendance']:
                            month_rate = month_data['present'] / (month_data['present'] + month_data['absent']) * 100 if (month_data['present'] + month_data['absent']) > 0 else 0
                            html_content += f"""
                            <tr>
                                <td>{month_data['month']}</td>
                                <td>{month_data['present']}</td>
                                <td>{month_data['absent']}</td>
                                <td>{month_rate:.1f}%</td>
                            </tr>
                            """
                        
                        html_content += "</table>"
                
                # Close HTML document
                html_content += """
                    <p style="text-align: center; margin-top: 20px; color: #666;">
                        Generated on: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
                    </p>
                </body>
                </html>
                """
                
                # Create a document and set the HTML
                document = QTextDocument()
                document.setHtml(html_content)
                
                # Print to PDF
                document.print_(printer)
                
                QMessageBox.information(self, "Report Generated", 
                                    f"Student-wise report exported successfully to {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Report Generation Failed", f"Error generating report: {str(e)}")
    
    def generate_class_report(self):
        """Generate a class-wise attendance report"""
        if self.attendance_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No attendance data to generate report")
            return
        
        try:
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save Class Report", 
                f"Class_Attendance_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                "PDF Files (*.pdf)"
            )
            
            if file_name:
                # Create a printer and set to PDF
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(file_name)
                
                # Get report data grouped by class
                date_from = self.date_from.date().toString("yyyy-MM-dd")
                date_to = self.date_to.date().toString("yyyy-MM-dd")
                
                # Fix course filter extraction
                course = None
                if self.course_filter.currentIndex() > 0:
                    course = self.course_filter.currentData()
                
                class_id = None
                if self.class_filter.currentIndex() > 0:
                    class_id = self.class_filter.currentData()
                
                year = self.year_filter.currentIndex()
                year = None if year == 0 else year
                
                # Get the include_absent value from the checkbox
                include_absent = self.include_absent_cb.isChecked()
                
                # Get class-wise report data
                report_data = self.report_service.generate_class_wise_report(
                    date_from, date_to, course, class_id, year, include_absent
                )
                
                # Generate HTML content for the report
                html_content = """
                <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; }
                        h1 { text-align: center; margin-bottom: 10px; }
                        h3 { text-align: center; margin-top: 5px; color: #666; }
                        h2 { margin-top: 30px; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
                        table { width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }
                        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                        th { background-color: #f2f2f2; }
                        .present { color: green; }
                        .absent { color: red; }
                        .class-summary { background-color: #f9f9f9; padding: 10px; margin: 15px 0; border-radius: 5px; }
                        .page-break { page-break-after: always; }
                        .summary-item { display: inline-block; margin-right: 20px; font-weight: bold; }
                    </style>
                </head>
                <body>
                    <h1>Class Attendance Report</h1>
                    <h3>Period: """ + f"{date_from} to {date_to}</h3>"
                
                # Add each class's data
                for i, class_data in enumerate(report_data):
                    # Add page break except for first class
                    if i > 0:
                        html_content += '<div class="page-break"></div>'
                    
                    html_content += f"""
                    <h2>Class: {class_data['class_name']} ({class_data['class_id']})</h2>
                    
                    <div class="class-summary">
                        <div class="summary-item">Course: {class_data['course_code']}</div>
                        <div class="summary-item">Total Students: {class_data['total_students']}</div>
                        <div class="summary-item">Total Sessions: {class_data['total_sessions']}</div>
                        <div class="summary-item">Average Attendance: {class_data['average_attendance']:.1f}%</div>
                    </div>
                    
                    <h3>Session Summary</h3>
                    <table>
                        <tr>
                            <th>Date</th>
                            <th>Time</th>
                            <th>Present</th>
                            <th>Absent</th>
                            <th>Attendance Rate</th>
                        </tr>
                    """
                    
                    # Add session data for this class
                    for session in class_data['sessions']:
                        attendance_rate = session['present_count'] / (session['present_count'] + session['absent_count']) * 100 if (session['present_count'] + session['absent_count']) > 0 else 0
                        html_content += f"""
                        <tr>
                            <td>{session['date']}</td>
                            <td>{session['time']}</td>
                            <td class="present">{session['present_count']}</td>
                            <td class="absent">{session['absent_count']}</td>
                            <td>{attendance_rate:.1f}%</td>
                        </tr>
                        """
                    
                    html_content += "</table>"
                    
                    # Add student attendance summary
                    html_content += """
                    <h3>Student Attendance Summary</h3>
                    <table>
                        <tr>
                            <th>Student ID</th>
                            <th>Student Name</th>
                            <th>Present</th>
                            <th>Absent</th>
                            <th>Attendance Rate</th>
                        </tr>
                    """
                    
                    for student in class_data['students']:
                        attendance_rate = student['present_count'] / (student['present_count'] + student['absent_count']) * 100 if (student['present_count'] + student['absent_count']) > 0 else 0
                        html_content += f"""
                        <tr>
                            <td>{student['student_id']}</td>
                            <td>{student['name']}</td>
                            <td class="present">{student['present_count']}</td>
                            <td class="absent">{student['absent_count']}</td>
                            <td>{attendance_rate:.1f}%</td>
                        </tr>
                        """
                    
                    html_content += "</table>"
                
                # Close HTML document
                html_content += """
                    <p style="text-align: center; margin-top: 20px; color: #666;">
                        Generated on: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """
                    </p>
                </body>
                </html>
                """
                
                # Create a document and set the HTML
                document = QTextDocument()
                document.setHtml(html_content)
                
                # Print to PDF
                document.print_(printer)
                
                QMessageBox.information(self, "Report Generated", 
                                    f"Class-wise report exported successfully to {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "Report Generation Failed", f"Error generating report: {str(e)}")

    

    