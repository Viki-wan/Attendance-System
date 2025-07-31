# attendance_report_generator.py
import csv
import os
from datetime import datetime
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QRectF, QSizeF
from admin.db_service import DatabaseService

class AttendanceReportGenerator:
    """Generate attendance reports in various formats"""
    
    def __init__(self, db_service):
        """Initialize with database service
        
        Args:
            db_service (DatabaseService): Instance of DatabaseService
        """
        self.db_service = db_service or DatabaseService
        
    def generate_pdf_report(self, file_path, filters):
        """Generate a PDF report of attendance data
        
        Args:
            file_path (str): Path to save the PDF file
            filters (dict): Filters applied to the data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get attendance data from the database service
            attendance_data = self.db_service.get_filtered_attendance(filters)
            if not attendance_data:
                return False
                
            # Set up the printer
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(file_path)
            printer.setPageSize(QPrinter.A4)
            printer.setPageMargins(20, 20, 20, 20, QPrinter.Millimeter)
            
            # Create painter
            painter = QPainter()
            if not painter.begin(printer):
                return False
                
            # Set font
            font = painter.font()
            
            # Calculate page size in pixels
            page_rect = printer.pageRect(QPrinter.DevicePixel)
            page_width = page_rect.width()
            
            # Draw header
            y_pos = 100
            font.setPointSize(18)
            font.setBold(True)
            painter.setFont(font)
            header_text = "Attendance Report"
            painter.drawText(0, y_pos, page_width, 30, Qt.AlignHCenter, header_text)
            
            # Draw subheader with date range
            y_pos += 40
            font.setPointSize(12)
            painter.setFont(font)
            subheader = f"Period: {filters['from_date']} to {filters['to_date']}"
            painter.drawText(0, y_pos, page_width, 20, Qt.AlignHCenter, subheader)
            
            # Add filter information
            y_pos += 40
            font.setPointSize(10)
            painter.setFont(font)
            
            filter_text = "Filters: "
            if filters.get('course_code'):
                filter_text += f"Course: {filters['course_code']}, "
            if filters.get('class_id'):
                filter_text += f"Class: {filters['class_id']}, "
            if filters.get('student_search'):
                filter_text += f"Student: {filters['student_search']}, "
                
            if filter_text == "Filters: ":
                filter_text += "None"
            else:
                filter_text = filter_text.rstrip(", ")
                
            painter.drawText(50, y_pos, page_width - 100, 20, Qt.AlignLeft, filter_text)
            
            # Draw summary statistics
            y_pos += 40
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(50, y_pos, page_width - 100, 20, Qt.AlignLeft, "Summary:")
            
            font.setBold(False)
            painter.setFont(font)
            
            # Calculate statistics
            total_records = len(attendance_data)
            present_count = sum(1 for record in attendance_data if record['status'] == 'Present')
            absent_count = total_records - present_count
            attendance_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0
            
            # Display summary stats
            y_pos += 30
            painter.drawText(70, y_pos, page_width - 140, 20, Qt.AlignLeft, f"Total Records: {total_records}")
            y_pos += 20
            painter.drawText(70, y_pos, page_width - 140, 20, Qt.AlignLeft, f"Present: {present_count}")
            y_pos += 20
            painter.drawText(70, y_pos, page_width - 140, 20, Qt.AlignLeft, f"Absent: {absent_count}")
            y_pos += 20
            painter.drawText(70, y_pos, page_width - 140, 20, Qt.AlignLeft, f"Attendance Rate: {attendance_rate}%")
            
            # Draw attendance chart if requested
            if filters.get('include_chart'):
                # Check if we can import the necessary modules
                try:
                    from attendance.attendance_statistics import AttendanceStatistics
                    from attendance.attendance_chart_widget import AttendanceChartWidget
                    
                    # Calculate chart data
                    stats = AttendanceStatistics(self.db_service)
                    chart_data = stats.calculate_statistics(filters)['attendance_data']
                    
                    # Create temporary chart widget
                    chart = AttendanceChartWidget()
                    chart.resize(page_width - 100, 200)
                    chart.update_chart(chart_data)
                    
                    # Render chart to pixmap
                    pixmap = QPixmap(chart.size())
                    pixmap.fill(Qt.white)
                    chart_painter = QPainter(pixmap)
                    chart.render(chart_painter)
                    chart_painter.end()
                    
                    # Draw chart title
                    y_pos += 50
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(50, y_pos, page_width - 100, 20, Qt.AlignLeft, "Attendance Trend:")
                    
                    # Draw chart
                    y_pos += 30
                    painter.drawPixmap(50, y_pos, pixmap)
                    y_pos += pixmap.height() + 30
                except ImportError:
                    print("Chart modules not available, skipping chart generation")
            
            # Draw table header
            y_pos += 30
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(50, y_pos, page_width - 100, 20, Qt.AlignLeft, "Attendance Records:")
            
            # Table headers
            y_pos += 30
            col_widths = [100, 80, 120, 100, 150, 80]
            headers = ["Date", "Course", "Class", "Student ID", "Name", "Status"]
            
            x_pos = 50
            for i, header in enumerate(headers):
                painter.drawText(x_pos, y_pos, col_widths[i], 20, Qt.AlignLeft, header)
                x_pos += col_widths[i]
                
            y_pos += 20
            painter.drawLine(50, y_pos, page_width - 50, y_pos)
            
            # Table data
            y_pos += 20
            font.setBold(False)
            painter.setFont(font)
            
            records_per_page = 25
            record_height = 20
            current_record = 0
            
            for record in attendance_data:
                # Check if we need a new page
                if current_record > 0 and current_record % records_per_page == 0:
                    printer.newPage()
                    y_pos = 50
                    
                    # Redraw table header
                    font.setBold(True)
                    painter.setFont(font)
                    
                    x_pos = 50
                    for i, header in enumerate(headers):
                        painter.drawText(x_pos, y_pos, col_widths[i], 20, Qt.AlignLeft, header)
                        x_pos += col_widths[i]
                        
                    y_pos += 20
                    painter.drawLine(50, y_pos, page_width - 50, y_pos)
                    y_pos += 20
                    
                    font.setBold(False)
                    painter.setFont(font)
                
                # Draw record
                x_pos = 50
                painter.drawText(x_pos, y_pos, col_widths[0], record_height, Qt.AlignLeft, record['date'])
                x_pos += col_widths[0]
                
                painter.drawText(x_pos, y_pos, col_widths[1], record_height, Qt.AlignLeft, record['course_code'])
                x_pos += col_widths[1]
                
                painter.drawText(x_pos, y_pos, col_widths[2], record_height, Qt.AlignLeft, record['class_name'])
                x_pos += col_widths[2]
                
                painter.drawText(x_pos, y_pos, col_widths[3], record_height, Qt.AlignLeft, record['student_id'])
                x_pos += col_widths[3]
                
                painter.drawText(x_pos, y_pos, col_widths[4], record_height, Qt.AlignLeft, record['name'])
                x_pos += col_widths[4]
                
                painter.drawText(x_pos, y_pos, col_widths[5], record_height, Qt.AlignLeft, record['status'])
                
                y_pos += record_height
                current_record += 1
            
            # Draw footer
            painter.drawLine(50, page_rect.height() - 50, page_width - 50, page_rect.height() - 50)
            footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            painter.drawText(0, page_rect.height() - 30, page_width, 20, Qt.AlignHCenter, footer_text)
            
            # End painter
            painter.end()
            return True
            
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return False
    
    def generate_csv_report(self, file_path, filters):
        """Generate a CSV report of attendance data
        
        Args:
            file_path (str): Path to save the CSV file
            filters (dict): Filters applied to the data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get attendance data from the database service
            attendance_data = self.db_service.get_filtered_attendance(filters)
            if not attendance_data:
                return False
                
            # Create CSV file
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Define CSV header
                fieldnames = ['Date', 'Course', 'Class', 'Student ID', 'Name', 'Status', 'Time']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data
                for record in attendance_data:
                    writer.writerow({
                        'Date': record['date'],
                        'Course': record['course_code'],
                        'Class': record['class_name'],
                        'Student ID': record['student_id'],
                        'Name': record['name'],
                        'Status': record['status'],
                        'Time': record['timestamp']
                    })
                    
            return True
            
        except Exception as e:
            print(f"Error generating CSV: {e}")
            return False