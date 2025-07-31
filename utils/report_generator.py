import os
import csv
from datetime import datetime
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QTextDocument, QColor, QPageSize
from PyQt5.QtCore import Qt, QSizeF, QMarginsF, QUrl
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for non-interactive mode

class ReportGenerator:
    """Utility class for generating PDF and CSV reports from attendance data"""
    
    def __init__(self, parent_widget=None):
        """Initialize the report generator
        
        Args:
            parent_widget: The parent widget for file dialogs
        """
        self.parent = parent_widget
        self.temp_chart_path = "temp_chart.png"
    
    def generate_pdf_report(self, report_title, report_data, report_type="general", include_charts=True, chart_data=None):
        """Generate a PDF report based on attendance data
        
        Args:
            report_title (str): Title of the report
            report_data (dict): Dictionary containing report data 
            report_type (str): Type of report (daily, course, trend, etc.)
            include_charts (bool): Whether to include charts in the report
            chart_data (dict): Data for generating charts if include_charts is True
            
        Returns:
            bool: True if report was generated successfully, False otherwise
        """ 
        
        parent = self.parent if isinstance(self.parent, QWidget) else None
        
        # Ask user for save location
        file_name, _ = QFileDialog.getSaveFileName(
            parent, 
            "Save PDF Report",
            f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            "PDF Files (*.pdf)"
        )
        
        if not file_name:
            return False
            
        try:
            # Create printer with custom settings
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_name)
            printer.setPageSize(QPageSize(QPageSize.A4))
            printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPrinter.Millimeter)
            
            # Create HTML document
            document = QTextDocument()
            
            # Generate HTML content based on report type
            html_content = self._generate_html_report(report_title, report_data, report_type, include_charts, chart_data)
            document.setHtml(html_content)
            
            # Print document to PDF
            document.print_(printer)
            
            # Clean up any temporary files
            self._cleanup_temp_files()
            
            # Notify success - use parent only if it's a QWidget
            if parent:
                QMessageBox.information(parent, "Export Successful", 
                                    f"Report successfully exported to {file_name}")
            
            return True
            
        except Exception as e:
            if parent:
                QMessageBox.critical(parent, "Export Failed", 
                                f"Failed to generate PDF report: {str(e)}")
            
            # Clean up any temporary files
            self._cleanup_temp_files()
            return False
        

    
    def generate_csv_report(self, report_title, report_data, report_type="general"):
        """Generate a CSV report based on attendance data
        
        Args:
            report_title (str): Title of the report
            report_data (dict): Dictionary containing report data
            report_type (str): Type of report (daily, course, trend, etc.)
            
        Returns:
            bool: True if report was generated successfully, False otherwise
        """
       
        parent = self.parent if isinstance(self.parent, QWidget) else None
        
        # Ask user for save location
        file_name, _ = QFileDialog.getSaveFileName(
            parent, 
            "Save CSV Report",
            f"{report_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        
        if not file_name:
            return False
            
        try:
            # Generate CSV content based on report type
            with open(file_name, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                
                # Write headers and data based on report type
                if report_type == "daily":
                    self._write_daily_report_csv(writer, report_data)
                elif report_type == "course":
                    self._write_course_report_csv(writer, report_data)
                elif report_type == "trend":
                    self._write_trend_report_csv(writer, report_data)
                elif report_type == "instructor":
                    self._write_instructor_report_csv(writer, report_data)
                elif report_type == "comparison":
                    self._write_comparison_report_csv(writer, report_data)
                else:
                    # Generic attendance data
                    self._write_general_attendance_csv(writer, report_data)
            
            # Notify success - use parent only if it's a QWidget
            if parent:
                QMessageBox.information(parent, "Export Successful", 
                                    f"CSV report successfully exported to {file_name}")
            
            return True
            
        except Exception as e:
            if parent:
                QMessageBox.critical(parent, "Export Failed", 
                                f"Failed to generate CSV report: {str(e)}")
            return False   
         
    def _generate_html_report(self, report_title, report_data, report_type, include_charts, chart_data):
        """Generate HTML content for the report based on report type
        
        Args:
            report_title (str): Title of the report
            report_data (dict): Dictionary containing report data
            report_type (str): Type of report (daily, course, trend, etc.)
            include_charts (bool): Whether to include charts in the report
            chart_data (dict): Data for generating charts
            
        Returns:
            str: HTML content for the report
        """
        # Start with basic HTML template
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 30px; }}
                h1 {{ color: #2c3e50; text-align: center; margin-bottom: 20px; }}
                h2 {{ color: #3498db; margin-top: 25px; margin-bottom: 10px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; color: #333; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .stat-card {{ 
                    display: inline-block; 
                    width: 22%; 
                    margin: 1%; 
                    padding: 10px; 
                    border-radius: 5px; 
                    background-color: #f8f9fa; 
                    text-align: center;
                }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #3498db; }}
                .stat-label {{ font-size: 14px; color: #7f8c8d; }}
                .chart-container {{ text-align: center; margin: 20px 0; }}
                .footer {{ margin-top: 30px; text-align: center; font-size: 12px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <h1>{report_title}</h1>
            <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        """
        
        # Add report specific content based on report type
        if report_type == "daily":
            html += self._generate_daily_report_html(report_data, include_charts, chart_data)
        elif report_type == "course":
            html += self._generate_course_report_html(report_data, include_charts, chart_data)
        elif report_type == "trend":
            html += self._generate_trend_report_html(report_data, include_charts, chart_data)
        elif report_type == "instructor":
            html += self._generate_instructor_report_html(report_data, include_charts, chart_data)
        elif report_type == "comparison":
            html += self._generate_comparison_report_html(report_data, include_charts, chart_data)
        else:
            # Generic attendance report
            html += self._generate_general_attendance_html(report_data)
        
        # Close HTML document
        html += """
            <div class="footer">
                <p>Generated by Attendance Management System</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_daily_report_html(self, report_data, include_charts, chart_data):
        """Generate HTML for daily attendance report"""
        html = ""
        
        # Add report date and course info
        html += f"""
            <div class="details">
                <p><strong>Date:</strong> {report_data.get('date', 'N/A')}</p>
                <p><strong>Course:</strong> {report_data.get('course_code', 'All Courses')} - {report_data.get('course_name', '')}</p>
                <p><strong>Class:</strong> {report_data.get('class_name', 'All Classes')}</p>
            </div>
        """
        
        # Add statistics
        html += """
            <h2>Attendance Summary</h2>
            <div>
        """
        
        # Create stat cards
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            
            html += f"""
                <div class="stat-card">
                    <div class="stat-value">{formatted_value}</div>
                    <div class="stat-label">{formatted_name}</div>
                </div>
            """
        
        html += "</div>"
        
        # Include chart if requested
        if include_charts and chart_data and 'daily_attendance' in chart_data:
            chart_path = self._create_chart(
                chart_data['daily_attendance'].get('labels', []),
                chart_data['daily_attendance'].get('values', []),
                "Daily Attendance",
                "Sessions",
                "Attendance %"
            )
            if chart_path:
                html += f"""
                    <div class="chart-container">
                        <h2>Daily Attendance Chart</h2>
                        <img src="{chart_path}" alt="Daily Attendance Chart" style="max-width: 100%;">
                    </div>
                """
        
        # Add attendance table
        html += """
            <h2>Attendance Details</h2>
            <table>
                <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Time</th>
                </tr>
        """
        
        # Add students data
        for student in report_data.get('attendance_records', []):
            status_color = "#4CAF50" if student.get('status', '') == "Present" else "#F44336"
            html += f"""
                <tr>
                    <td>{student.get('student_id', '')}</td>
                    <td>{student.get('name', '')}</td>
                    <td style="color: {status_color}; font-weight: bold;">{student.get('status', '')}</td>
                    <td>{student.get('timestamp', '')}</td>
                </tr>
            """
        
        html += "</table>"
        
        # Add absent students if available
        absent_students = report_data.get('absent_students', [])
        if absent_students:
            html += """
                <h2>Absent Students</h2>
                <table>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                    </tr>
            """
            
            for student in absent_students:
                html += f"""
                    <tr>
                        <td>{student.get('student_id', '')}</td>
                        <td>{student.get('name', '')}</td>
                    </tr>
                """
            
            html += "</table>"
        
        return html
    
    def _generate_course_report_html(self, report_data, include_charts, chart_data):
        """Generate HTML for course attendance report"""
        html = ""
        
        # Add course details
        html += f"""
            <div class="details">
                <p><strong>Course:</strong> {report_data.get('course_code', 'N/A')} - {report_data.get('course_name', '')}</p>
                <p><strong>Period:</strong> {report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}</p>
                <p><strong>Instructor:</strong> {report_data.get('instructor_name', 'Multiple Instructors')}</p>
            </div>
        """
        
        # Add statistics
        html += """
            <h2>Course Statistics</h2>
            <div>
        """
        
        # Create stat cards
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            
            html += f"""
                <div class="stat-card">
                    <div class="stat-value">{formatted_value}</div>
                    <div class="stat-label">{formatted_name}</div>
                </div>
            """
        
        html += "</div>"
        
        # Include chart if requested
        if include_charts and chart_data:
            if 'attendance_by_session' in chart_data:
                chart_path = self._create_chart(
                    chart_data['attendance_by_session'].get('labels', []),
                    chart_data['attendance_by_session'].get('values', []),
                    "Attendance by Session",
                    "Sessions",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Attendance by Session</h2>
                            <img src="{chart_path}" alt="Attendance by Session Chart" style="max-width: 100%;">
                        </div>
                    """
            
            if 'attendance_by_student' in chart_data:
                chart_path = self._create_bar_chart(
                    chart_data['attendance_by_student'].get('labels', [])[:10],  # Top 10 for readability
                    chart_data['attendance_by_student'].get('values', [])[:10],
                    "Top Students Attendance Rate",
                    "Students",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Top Students Attendance Rate</h2>
                            <img src="{chart_path}" alt="Top Students Chart" style="max-width: 100%;">
                        </div>
                    """
        
        # Add sessions table
        html += """
            <h2>Session Details</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Present</th>
                    <th>Total Students</th>
                    <th>Attendance %</th>
                </tr>
        """
        
        # Add sessions data
        for session in report_data.get('sessions', []):
            attendance_percentage = session.get('attendance_percentage', 0)
            color = self._get_percentage_color(attendance_percentage)
            
            html += f"""
                <tr>
                    <td>{session.get('date', '')}</td>
                    <td>{session.get('start_time', '')}</td>
                    <td>{session.get('end_time', '')}</td>
                    <td>{session.get('present_count', 0)}</td>
                    <td>{session.get('total_students', 0)}</td>
                    <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                </tr>
            """
        
        html += "</table>"
        
        # Add students summary if available
        students = report_data.get('students', [])
        if students:
            html += """
                <h2>Student Attendance Summary</h2>
                <table>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Present Sessions</th>
                        <th>Total Sessions</th>
                        <th>Attendance %</th>
                    </tr>
            """
            
            for student in students:
                attendance_percentage = student.get('attendance_percentage', 0)
                color = self._get_percentage_color(attendance_percentage)
                
                html += f"""
                    <tr>
                        <td>{student.get('student_id', '')}</td>
                        <td>{student.get('name', '')}</td>
                        <td>{student.get('present_sessions', 0)}</td>
                        <td>{student.get('total_sessions', 0)}</td>
                        <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                    </tr>
                """
            
            html += "</table>"
        
        return html
    
    def _generate_trend_report_html(self, report_data, include_charts, chart_data):
        """Generate HTML for trend analysis report"""
        html = ""
        
        # Add report details
        html += f"""
            <div class="details">
                <p><strong>Period:</strong> {report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}</p>
                <p><strong>Filter:</strong> {report_data.get('filter_description', 'All Data')}</p>
            </div>
        """
        
        # Add statistics
        html += """
            <h2>Attendance Statistics</h2>
            <div>
        """
        
        # Create stat cards
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            
            html += f"""
                <div class="stat-card">
                    <div class="stat-value">{formatted_value}</div>
                    <div class="stat-label">{formatted_name}</div>
                </div>
            """
        
        html += "</div>"
        
        # Include charts if requested
        if include_charts and chart_data:
            if 'trend_over_time' in chart_data:
                chart_path = self._create_line_chart(
                    chart_data['trend_over_time'].get('labels', []),
                    chart_data['trend_over_time'].get('values', []),
                    "Attendance Trend Over Time",
                    "Date",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Attendance Trend Over Time</h2>
                            <img src="{chart_path}" alt="Trend Chart" style="max-width: 100%;">
                        </div>
                    """
            
            if 'course_comparison' in chart_data:
                chart_path = self._create_bar_chart(
                    chart_data['course_comparison'].get('labels', []),
                    chart_data['course_comparison'].get('values', []),
                    "Course Attendance Comparison",
                    "Courses",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Course Attendance Comparison</h2>
                            <img src="{chart_path}" alt="Course Comparison Chart" style="max-width: 100%;">
                        </div>
                    """
            
            if 'time_analysis' in chart_data:
                chart_path = self._create_bar_chart(
                    chart_data['time_analysis'].get('labels', []),
                    chart_data['time_analysis'].get('values', []),
                    "Attendance by Time of Day",
                    "Time Slot",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Attendance by Time of Day</h2>
                            <img src="{chart_path}" alt="Time Analysis Chart" style="max-width: 100%;">
                        </div>
                    """
        
        # Add trend data table
        html += """
            <h2>Attendance Trend Data</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Sessions</th>
                    <th>Students Present</th>
                    <th>Total Students</th>
                    <th>Attendance %</th>
                </tr>
        """
        
        # Add trend data
        for item in report_data.get('trend_data', []):
            attendance_percentage = item.get('attendance_percentage', 0)
            color = self._get_percentage_color(attendance_percentage)
            
            html += f"""
                <tr>
                    <td>{item.get('date', '')}</td>
                    <td>{item.get('sessions', 0)}</td>
                    <td>{item.get('students_present', 0)}</td>
                    <td>{item.get('total_students', 0)}</td>
                    <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                </tr>
            """
        
        html += "</table>"
        
        return html
    
    def _generate_instructor_report_html(self, report_data, include_charts, chart_data):
        """Generate HTML for instructor effectiveness report"""
        html = ""
        
        # Add report details
        html += f"""
            <div class="details">
                <p><strong>Period:</strong> {report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}</p>
                <p><strong>Instructor:</strong> {report_data.get('instructor_name', 'All Instructors')}</p>
            </div>
        """
        
        # Include charts if requested
        if include_charts and chart_data:
            if 'instructor_comparison' in chart_data:
                chart_path = self._create_bar_chart(
                    chart_data['instructor_comparison'].get('labels', []),
                    chart_data['instructor_comparison'].get('values', []),
                    "Attendance % by Instructor",
                    "Instructors",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Instructor Effectiveness Comparison</h2>
                            <img src="{chart_path}" alt="Instructor Comparison Chart" style="max-width: 100%;">
                        </div>
                    """
            
            if 'instructor_courses' in chart_data:
                chart_path = self._create_bar_chart(
                    chart_data['instructor_courses'].get('labels', []),
                    chart_data['instructor_courses'].get('values', []),
                    "Course Attendance for Selected Instructor",
                    "Courses",
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Course Attendance for Instructor</h2>
                            <img src="{chart_path}" alt="Instructor Courses Chart" style="max-width: 100%;">
                        </div>
                    """
        
        # Add instructor data table
        html += """
            <h2>Instructor Performance Data</h2>
            <table>
                <tr>
                    <th>Instructor</th>
                    <th>Total Sessions</th>
                    <th>Total Students</th>
                    <th>Students Attended</th>
                    <th>Attendance %</th>
                    <th>Performance Rating</th>
                </tr>
        """
        
        # Add instructor data
        for instructor in report_data.get('instructors', []):
            attendance_percentage = instructor.get('attendance_percentage', 0)
            color = self._get_percentage_color(attendance_percentage)
            rating = instructor.get('performance', '')
            rating_color = self._get_rating_color(rating)
            
            html += f"""
                <tr>
                    <td>{instructor.get('instructor_name', '')}</td>
                    <td>{instructor.get('total_sessions', 0)}</td>
                    <td>{instructor.get('total_students', 0)}</td>
                    <td>{instructor.get('attended_students', 0)}</td>
                    <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                    <td style="color: {rating_color}; font-weight: bold;">{rating}</td>
                </tr>
            """
        
        html += "</table>"
        
        # Add course data if specific instructor is selected
        if 'instructor_courses' in report_data:
            html += """
                <h2>Course Performance for Selected Instructor</h2>
                <table>
                    <tr>
                        <th>Course Code</th>
                        <th>Course Name</th>
                        <th>Sessions</th>
                        <th>Students Attended</th>
                        <th>Total Students</th>
                        <th>Attendance %</th>
                    </tr>
            """
            
            for course in report_data.get('instructor_courses', []):
                attendance_percentage = course.get('attendance_percentage', 0)
                color = self._get_percentage_color(attendance_percentage)
                
                html += f"""
                    <tr>
                        <td>{course.get('course_code', '')}</td>
                        <td>{course.get('course_name', '')}</td>
                        <td>{course.get('sessions', 0)}</td>
                        <td>{course.get('students_attended', 0)}</td>
                        <td>{course.get('total_students', 0)}</td>
                        <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                    </tr>
                """
            
            html += "</table>"
        
        return html
    
    def _generate_comparison_report_html(self, report_data, include_charts, chart_data):
        """Generate HTML for comparative analysis report"""
        html = ""
        
        # Add report details
        html += f"""
            <div class="details">
                <p><strong>Period:</strong> {report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}</p>
                <p><strong>Comparison Type:</strong> {report_data.get('comparison_type', 'N/A')}</p>
            </div>
        """
        
        # Include charts if requested
        if include_charts and chart_data:
            if 'comparison_chart' in chart_data:
                chart_path = self._create_bar_chart(
                    chart_data['comparison_chart'].get('labels', []),
                    chart_data['comparison_chart'].get('values', []),
                    f"Attendance Comparison by {report_data.get('comparison_type', 'Category')}",
                    report_data.get('comparison_type', 'Category'),
                    "Attendance %"
                )
                if chart_path:
                    html += f"""
                        <div class="chart-container">
                            <h2>Attendance Comparison</h2>
                            <img src="{chart_path}" alt="Comparison Chart" style="max-width: 100%;">
                        </div>
                    """
        
        # Add comparison data table
        html += f"""
            <h2>Attendance Comparison by {report_data.get('comparison_type', 'Category')}</h2>
            <table>
                <tr>
                    <th>{report_data.get('comparison_type', 'Category')}</th>
                    <th>Sessions</th>
                    <th>Students Present</th>
                    <th>Total Students</th>
                    <th>Attendance %</th>
                </tr>
        """
        
        # Add comparison data
        for item in report_data.get('comparison_data', []):
            attendance_percentage = item.get('attendance_percentage', 0)
            color = self._get_percentage_color(attendance_percentage)
            
            html += f"""
                <tr>
                    <td>{item.get('category_name', '')}</td>
                    <td>{item.get('sessions', 0)}</td>
                    <td>{item.get('students_present', 0)}</td>
                    <td>{item.get('total_students', 0)}</td>
                    <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                </tr>
            """
        
        html += "</table>"
        
        return html
    
    def _generate_general_attendance_html(self, report_data):
        """Generate HTML for general attendance report"""
        html = ""
        
        # Add report details
        html += f"""
            <div class="details">
                <p><strong>Period:</strong> {report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}</p>
                <p><strong>Filter:</strong> {report_data.get('filter_description', 'All Records')}</p>
            </div>
        """
        
        # Add attendance summary
        html += """
            <h2>Attendance Summary</h2>
            <div>
        """
        
        # Create stat cards
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            
            html += f"""
                <div class="stat-card">
                    <div class="stat-value">{formatted_value}</div>
                    <div class="stat-label">{formatted_name}</div>
                </div>
            """
        
        html += "</div>"
        
        # Add overall attendance table
        html += """
            <h2>Overall Attendance</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Course</th>
                    <th>Class</th>
                    <th>Session Time</th>
                    <th>Students Present</th>
                    <th>Total Students</th>
                    <th>Attendance %</th>
                </tr>
        """
        
        # Add attendance data
        for session in report_data.get('sessions', []):
            attendance_percentage = session.get('attendance_percentage', 0)
            color = self._get_percentage_color(attendance_percentage)
            
            html += f"""
                <tr>
                    <td>{session.get('date', '')}</td>
                    <td>{session.get('course_code', '')} - {session.get('course_name', '')}</td>
                    <td>{session.get('class_name', '')}</td>
                    <td>{session.get('start_time', '')} - {session.get('end_time', '')}</td>
                    <td>{session.get('present_count', 0)}</td>
                    <td>{session.get('total_students', 0)}</td>
                    <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                </tr>
            """
        
        html += "</table>"
        
        # Add student summary if available
        students = report_data.get('student_summary', [])
        if students:
            html += """
                <h2>Student Attendance Summary</h2>
                <table>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Total Classes</th>
                        <th>Classes Attended</th>
                        <th>Attendance %</th>
                    </tr>
            """
            
            for student in students:
                attendance_percentage = student.get('attendance_percentage', 0)
                color = self._get_percentage_color(attendance_percentage)
                
                html += f"""
                    <tr>
                        <td>{student.get('student_id', '')}</td>
                        <td>{student.get('name', '')}</td>
                        <td>{student.get('total_classes', 0)}</td>
                        <td>{student.get('classes_attended', 0)}</td>
                        <td style="color: {color}; font-weight: bold;">{attendance_percentage:.2f}%</td>
                    </tr>
                """
            
            html += "</table>"
        
        return html

    def _write_daily_report_csv(self, writer, report_data):
        """Write daily attendance report data to CSV"""
        # Write report metadata
        writer.writerow(['Daily Attendance Report'])
        writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Date', report_data.get('date', 'N/A')])
        writer.writerow(['Course', f"{report_data.get('course_code', 'All Courses')} - {report_data.get('course_name', '')}"]) 
        writer.writerow(['Class', report_data.get('class_name', 'All Classes')])
        writer.writerow([])  # Empty row for separation
        
        # Write statistics
        writer.writerow(['Attendance Summary'])
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            writer.writerow([formatted_name, formatted_value])
        
        writer.writerow([])  # Empty row for separation
        
        # Write attendance details
        writer.writerow(['Attendance Details'])
        writer.writerow(['Student ID', 'Name', 'Status', 'Time'])
        
        for student in report_data.get('attendance_records', []):
            writer.writerow([
                student.get('student_id', ''),
                student.get('name', ''),
                student.get('status', ''),
                student.get('timestamp', '')
            ])
        
        writer.writerow([])  # Empty row for separation
        
        # Write absent students if available
        absent_students = report_data.get('absent_students', [])
        if absent_students:
            writer.writerow(['Absent Students'])
            writer.writerow(['Student ID', 'Name'])
            
            for student in absent_students:
                writer.writerow([
                    student.get('student_id', ''),
                    student.get('name', '')
                ])

    def _write_course_report_csv(self, writer, report_data):
        """Write course attendance report data to CSV"""
        # Write report metadata
        writer.writerow(['Course Attendance Report'])
        writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Course', f"{report_data.get('course_code', 'N/A')} - {report_data.get('course_name', '')}"]) 
        writer.writerow(['Period', f"{report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}"]) 
        writer.writerow(['Instructor', report_data.get('instructor_name', 'Multiple Instructors')])
        writer.writerow([])  # Empty row for separation
        
        # Write statistics
        writer.writerow(['Course Statistics'])
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            writer.writerow([formatted_name, formatted_value])
        
        writer.writerow([])  # Empty row for separation
        
        # Write session details
        writer.writerow(['Session Details'])
        writer.writerow(['Date', 'Start Time', 'End Time', 'Present', 'Total Students', 'Attendance %'])
        
        for session in report_data.get('sessions', []):
            writer.writerow([
                session.get('date', ''),
                session.get('start_time', ''),
                session.get('end_time', ''),
                session.get('present_count', 0),
                session.get('total_students', 0),
                f"{session.get('attendance_percentage', 0):.2f}%"
            ])
        
        writer.writerow([])  # Empty row for separation
        
        # Write student summary if available
        students = report_data.get('students', [])
        if students:
            writer.writerow(['Student Attendance Summary'])
            writer.writerow(['Student ID', 'Name', 'Present Sessions', 'Total Sessions', 'Attendance %'])
            
            for student in students:
                writer.writerow([
                    student.get('student_id', ''),
                    student.get('name', ''),
                    student.get('present_sessions', 0),
                    student.get('total_sessions', 0),
                    f"{student.get('attendance_percentage', 0):.2f}%"
                ])

    def _write_trend_report_csv(self, writer, report_data):
        """Write trend analysis report data to CSV"""
        # Write report metadata
        writer.writerow(['Attendance Trend Report'])
        writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Period', f"{report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}"]) 
        writer.writerow(['Filter', report_data.get('filter_description', 'All Data')])
        writer.writerow([])  # Empty row for separation
        
        # Write statistics
        writer.writerow(['Attendance Statistics'])
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            writer.writerow([formatted_name, formatted_value])
        
        writer.writerow([])  # Empty row for separation
        
        # Write trend data
        writer.writerow(['Attendance Trend Data'])
        writer.writerow(['Date', 'Sessions', 'Students Present', 'Total Students', 'Attendance %'])
        
        for item in report_data.get('trend_data', []):
            writer.writerow([
                item.get('date', ''),
                item.get('sessions', 0),
                item.get('students_present', 0),
                item.get('total_students', 0),
                f"{item.get('attendance_percentage', 0):.2f}%"
            ])

    def _write_instructor_report_csv(self, writer, report_data):
        """Write instructor effectiveness report data to CSV"""
        # Write report metadata
        writer.writerow(['Instructor Effectiveness Report'])
        writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Period', f"{report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}"]) 
        writer.writerow(['Instructor', report_data.get('instructor_name', 'All Instructors')])
        writer.writerow([])  # Empty row for separation
        
        # Write instructor data
        writer.writerow(['Instructor Performance Data'])
        writer.writerow(['Instructor', 'Total Sessions', 'Total Students', 'Students Attended', 'Attendance %', 'Performance Rating'])
        
        for instructor in report_data.get('instructors', []):
            writer.writerow([
                instructor.get('instructor_name', ''),
                instructor.get('total_sessions', 0),
                instructor.get('total_students', 0),
                instructor.get('attended_students', 0),
                f"{instructor.get('attendance_percentage', 0):.2f}%",
                instructor.get('performance', '')
            ])
        
        writer.writerow([])  # Empty row for separation
        
        # Write course data if specific instructor is selected
        if 'instructor_courses' in report_data:
            writer.writerow(['Course Performance for Selected Instructor'])
            writer.writerow(['Course Code', 'Course Name', 'Sessions', 'Students Attended', 'Total Students', 'Attendance %'])
            
            for course in report_data.get('instructor_courses', []):
                writer.writerow([
                    course.get('course_code', ''),
                    course.get('course_name', ''),
                    course.get('sessions', 0),
                    course.get('students_attended', 0),
                    course.get('total_students', 0),
                    f"{course.get('attendance_percentage', 0):.2f}%"
                ])

    def _write_comparison_report_csv(self, writer, report_data):
        """Write comparative analysis report data to CSV"""
        # Write report metadata
        writer.writerow(['Attendance Comparison Report'])
        writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Period', f"{report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}"]) 
        writer.writerow(['Comparison Type', report_data.get('comparison_type', 'N/A')])
        writer.writerow([])  # Empty row for separation
        
        # Write comparison data
        writer.writerow([f"Attendance Comparison by {report_data.get('comparison_type', 'Category')}"]) 
        writer.writerow([report_data.get('comparison_type', 'Category'), 'Sessions', 'Students Present', 'Total Students', 'Attendance %'])
        
        for item in report_data.get('comparison_data', []):
            writer.writerow([
                item.get('category_name', ''),
                item.get('sessions', 0),
                item.get('students_present', 0),
                item.get('total_students', 0),
                f"{item.get('attendance_percentage', 0):.2f}%"
            ])

    def _write_general_attendance_csv(self, writer, report_data):
        """Write general attendance report data to CSV"""
        # Write report metadata
        writer.writerow(['General Attendance Report'])
        writer.writerow(['Generated on', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Period', f"{report_data.get('start_date', 'N/A')} to {report_data.get('end_date', 'N/A')}"]) 
        writer.writerow(['Filter', report_data.get('filter_description', 'All Records')])
        writer.writerow([])  # Empty row for separation
        
        # Write statistics
        writer.writerow(['Attendance Summary'])
        stats = report_data.get('stats', {})
        for stat_name, stat_value in stats.items():
            formatted_name = ' '.join(word.capitalize() for word in stat_name.replace('_', ' ').split())
            formatted_value = stat_value
            if isinstance(stat_value, float):
                formatted_value = f"{stat_value:.2f}%"
            writer.writerow([formatted_name, formatted_value])
        
        writer.writerow([])  # Empty row for separation
        
        # Write overall attendance data
        writer.writerow(['Overall Attendance'])
        writer.writerow(['Date', 'Course', 'Class', 'Session Time', 'Students Present', 'Total Students', 'Attendance %'])
        
        for session in report_data.get('sessions', []):
            writer.writerow([
                session.get('date', ''),
                f"{session.get('course_code', '')} - {session.get('course_name', '')}",
                session.get('class_name', ''),
                f"{session.get('start_time', '')} - {session.get('end_time', '')}",
                session.get('present_count', 0),
                session.get('total_students', 0),
                f"{session.get('attendance_percentage', 0):.2f}%"
            ])
        
        writer.writerow([])  # Empty row for separation
        
        # Write student summary if available
        students = report_data.get('student_summary', [])
        if students:
            writer.writerow(['Student Attendance Summary'])
            writer.writerow(['Student ID', 'Name', 'Total Classes', 'Classes Attended', 'Attendance %'])
            
            for student in students:
                writer.writerow([
                    student.get('student_id', ''),
                    student.get('name', ''),
                    student.get('total_classes', 0),
                    student.get('classes_attended', 0),
                    f"{student.get('attendance_percentage', 0):.2f}%"
                ])

    def _create_chart(self, labels, values, title, x_label, y_label):
        """Create a simple chart and save it to a temporary file
        
        Args:
            labels (list): Labels for the x-axis
            values (list): Values for the chart
            title (str): Chart title
            x_label (str): Label for the x-axis
            y_label (str): Label for the y-axis
            
        Returns:
            str: Path to the saved chart image, or None if failed
        """
        try:
            # Create a new figure with a default size
            plt.figure(figsize=(10, 6))
            
            # Create the chart (default to bar chart)
            plt.bar(labels, values, color='#3498db')
            
            # Set chart title and labels
            plt.title(title, fontsize=16, pad=20)
            plt.xlabel(x_label, fontsize=12, labelpad=10)
            plt.ylabel(y_label, fontsize=12, labelpad=10)
            
            # Add a grid
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # Rotate x labels if there are many
            if len(labels) > 5:
                plt.xticks(rotation=45, ha='right')
            
            # Adjust layout
            plt.tight_layout()
            
            # Save the chart to a temporary file
            plt.savefig(self.temp_chart_path, dpi=100)
            plt.close()
            
            return self.temp_chart_path
        except Exception as e:
            print(f"Error creating chart: {str(e)}")
            return None

    def _create_line_chart(self, labels, values, title, x_label, y_label):
        """Create a line chart and save it to a temporary file
        
        Args:
            labels (list): Labels for the x-axis
            values (list): Values for the chart
            title (str): Chart title
            x_label (str): Label for the x-axis
            y_label (str): Label for the y-axis
            
        Returns:
            str: Path to the saved chart image, or None if failed
        """
        try:
            # Create a new figure with a default size
            plt.figure(figsize=(10, 6))
            
            # Create the line chart
            plt.plot(labels, values, marker='o', linestyle='-', color='#3498db', linewidth=2)
            
            # Set chart title and labels
            plt.title(title, fontsize=16, pad=20)
            plt.xlabel(x_label, fontsize=12, labelpad=10)
            plt.ylabel(y_label, fontsize=12, labelpad=10)
            
            # Add a grid
            plt.grid(True, linestyle='--', alpha=0.7)
            
            # Rotate x labels if there are many
            if len(labels) > 5:
                plt.xticks(rotation=45, ha='right')
            
            # Adjust layout
            plt.tight_layout()
            
            # Save the chart to a temporary file
            plt.savefig(self.temp_chart_path, dpi=100)
            plt.close()
            
            return self.temp_chart_path
        except Exception as e:
            print(f"Error creating line chart: {str(e)}")
            return None

    def _create_bar_chart(self, labels, values, title, x_label, y_label):
        """Create a bar chart and save it to a temporary file
        
        Args:
            labels (list): Labels for the x-axis
            values (list): Values for the chart
            title (str): Chart title
            x_label (str): Label for the x-axis
            y_label (str): Label for the y-axis
            
        Returns:
            str: Path to the saved chart image, or None if failed
        """
        try:
            # Create a new figure with a default size
            plt.figure(figsize=(10, 6))
            
            # Create the bar chart with a colorful palette
            bars = plt.bar(labels, values, color='#3498db')
            
            # Set chart title and labels
            plt.title(title, fontsize=16, pad=20)
            plt.xlabel(x_label, fontsize=12, labelpad=10)
            plt.ylabel(y_label, fontsize=12, labelpad=10)
            
            # Add a grid
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{height:.1f}%' if height < 100 else f'{int(height)}',
                        ha='center', va='bottom', fontsize=9)
            
            # Rotate x labels if there are many
            if len(labels) > 5:
                plt.xticks(rotation=45, ha='right')
            
            # Adjust layout
            plt.tight_layout()
            
            # Save the chart to a temporary file
            plt.savefig(self.temp_chart_path, dpi=100)
            plt.close()
            
            return self.temp_chart_path
        except Exception as e:
            print(f"Error creating bar chart: {str(e)}")
            return None

    def _create_pie_chart(self, labels, values, title):
        """Create a pie chart and save it to a temporary file
        
        Args:
            labels (list): Labels for the pie slices
            values (list): Values for the pie slices
            title (str): Chart title
            
        Returns:
            str: Path to the saved chart image, or None if failed
        """
        try:
            # Create a new figure with a default size
            plt.figure(figsize=(8, 8))
            
            # Create the pie chart
            plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, 
                    shadow=False, wedgeprops={'edgecolor': 'white', 'linewidth': 1})
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            plt.axis('equal')
            
            # Set chart title
            plt.title(title, fontsize=16, pad=20)
            
            # Add legend
            plt.legend(labels, loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
            
            # Adjust layout
            plt.tight_layout()
            
            # Save the chart to a temporary file
            plt.savefig(self.temp_chart_path, dpi=100)
            plt.close()
            
            return self.temp_chart_path
        except Exception as e:
            print(f"Error creating pie chart: {str(e)}")
            return None

    def _create_stacked_bar_chart(self, categories, series_data, series_names, title, x_label, y_label):
        """Create a stacked bar chart and save it to a temporary file
        
        Args:
            categories (list): Categories for the x-axis
            series_data (list): List of data series (each a list of values)
            series_names (list): Names of each data series
            title (str): Chart title
            x_label (str): Label for the x-axis
            y_label (str): Label for the y-axis
            
        Returns:
            str: Path to the saved chart image, or None if failed
        """
        try:
            # Create a new figure with a default size
            plt.figure(figsize=(10, 6))
            
            # Create a stacked bar chart
            bottom = [0] * len(categories)
            for i, data in enumerate(series_data):
                plt.bar(categories, data, bottom=bottom, label=series_names[i])
                bottom = [sum(x) for x in zip(bottom, data)]
            
            # Set chart title and labels
            plt.title(title, fontsize=16, pad=20)
            plt.xlabel(x_label, fontsize=12, labelpad=10)
            plt.ylabel(y_label, fontsize=12, labelpad=10)
            
            # Add a grid
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # Add legend
            plt.legend()
            
            # Rotate x labels if there are many
            if len(categories) > 5:
                plt.xticks(rotation=45, ha='right')
            
            # Adjust layout
            plt.tight_layout()
            
            # Save the chart to a temporary file
            plt.savefig(self.temp_chart_path, dpi=100)
            plt.close()
            
            return self.temp_chart_path
        except Exception as e:
            print(f"Error creating stacked bar chart: {str(e)}")
            return None

    def _get_percentage_color(self, percentage):
        """Get color for percentage value display
        
        Args:
            percentage (float): Percentage value
            
        Returns:
            str: Hex color code
        """
        if percentage >= 90:
            return "#4CAF50"  # Green
        elif percentage >= 75:
            return "#8BC34A"  # Light Green
        elif percentage >= 60:
            return "#FFC107"  # Amber
        elif percentage >= 50:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red

    def _get_rating_color(self, rating):
        """Get color for rating value display
        
        Args:
            rating (str): Rating value (Excellent, Good, Average, etc.)
            
        Returns:
            str: Hex color code
        """
        if rating == "Excellent":
            return "#4CAF50"  # Green
        elif rating == "Good":
            return "#8BC34A"  # Light Green
        elif rating == "Average":
            return "#FFC107"  # Amber
        elif rating == "Below Average":
            return "#FF9800"  # Orange
        elif rating == "Poor":
            return "#F44336"  # Red
        else:
            return "#000000"  # Default black

    def _cleanup_temp_files(self):
        """Remove temporary files created during report generation"""
        try:
            if os.path.exists(self.temp_chart_path):
                os.remove(self.temp_chart_path)
        except Exception as e:
            print(f"Error cleaning up temporary files: {str(e)}")