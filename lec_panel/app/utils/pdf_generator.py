"""
PDF Generator - Generate professional PDF reports using WeasyPrint
Supports various report layouts with charts and tables
"""

from weasyprint import HTML, CSS
from datetime import datetime
import matplotlib.pyplot as plt
import io
import base64
from jinja2 import Template


class PDFGenerator:
    """Generate PDF reports with professional styling"""
    
    def __init__(self):
        self.base_css = """
        @page {
            size: A4;
            margin: 2cm;
            @top-center {
                content: "Attendance Report";
                font-family: Arial, sans-serif;
                font-size: 10pt;
                color: #666;
            }
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-family: Arial, sans-serif;
                font-size: 9pt;
                color: #666;
            }
        }
        
        body {
            font-family: 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        
        .header {
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        .header h1 {
            color: #2c3e50;
            margin: 0;
            font-size: 24pt;
        }
        
        .header .subtitle {
            color: #7f8c8d;
            font-size: 12pt;
            margin-top: 10px;
        }
        
        .info-section {
            background: #ecf0f1;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }
        
        .info-section h3 {
            margin-top: 0;
            color: #2c3e50;
            font-size: 14pt;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        
        .info-item {
            padding: 5px 0;
        }
        
        .info-label {
            font-weight: bold;
            color: #34495e;
        }
        
        .stats-container {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 30px 0;
        }
        
        .stat-box {
            background: #fff;
            border: 2px solid #ecf0f1;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        
        .stat-box.success {
            border-color: #27ae60;
        }
        
        .stat-box.warning {
            border-color: #f39c12;
        }
        
        .stat-box.danger {
            border-color: #e74c3c;
        }
        
        .stat-box.info {
            border-color: #3498db;
        }
        
        .stat-value {
            font-size: 32pt;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .stat-box.success .stat-value {
            color: #27ae60;
        }
        
        .stat-box.warning .stat-value {
            color: #f39c12;
        }
        
        .stat-box.danger .stat-value {
            color: #e74c3c;
        }
        
        .stat-box.info .stat-value {
            color: #3498db;
        }
        
        .stat-label {
            font-size: 10pt;
            color: #7f8c8d;
            text-transform: uppercase;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 10pt;
        }
        
        th {
            background: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }
        
        td {
            border: 1px solid #ddd;
            padding: 10px;
        }
        
        tr:nth-child(even) {
            background: #f9f9f9;
        }
        
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 9pt;
            text-transform: uppercase;
        }
        
        .status-present {
            background: #d4edda;
            color: #155724;
        }
        
        .status-late {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-absent {
            background: #f8d7da;
            color: #721c24;
        }
        
        .status-excused {
            background: #d1ecf1;
            color: #0c5460;
        }
        
        .chart-container {
            text-align: center;
            margin: 30px 0;
            page-break-inside: avoid;
        }
        
        .chart-container img {
            max-width: 100%;
            height: auto;
        }
        
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            font-size: 9pt;
            color: #7f8c8d;
            text-align: center;
        }
        
        h2 {
            color: #2c3e50;
            border-left: 5px solid #3498db;
            padding-left: 15px;
            margin-top: 30px;
            font-size: 16pt;
        }
        
        .alert-box {
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        
        .alert-box h4 {
            color: #856404;
            margin-top: 0;
        }
        """
    
    def generate_session_report(self, report_data, output_path=None):
        """
        Generate PDF report for a single session
        
        Args:
            report_data: Session report data from ReportService
            output_path: Path to save PDF (optional)
            
        Returns:
            bytes: PDF content if output_path is None, else None
        """
        session_info = report_data['session_info']
        stats = report_data['statistics']
        students = report_data['students']
        
        # Generate chart
        chart_base64 = self._generate_donut_chart(
            [stats['present'], stats['late'], stats['absent']],
            ['Present', 'Late', 'Absent'],
            ['#27ae60', '#f39c12', '#e74c3c']
        )
        
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Session Report</title>
        </head>
        <body>
            <div class="header">
                <h1>Session Attendance Report</h1>
                <div class="subtitle">{{ session_info.course_name }} - {{ session_info.class_name }}</div>
                <div class="subtitle">{{ session_info.date }} | {{ session_info.start_time }} - {{ session_info.end_time }}</div>
            </div>
            
            <div class="info-section">
                <h3>Session Information</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Session ID:</span> {{ session_info.session_id }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Class ID:</span> {{ session_info.class_id }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Course Code:</span> {{ session_info.course_code }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Status:</span> {{ session_info.status|upper }}
                    </div>
                </div>
            </div>
            
            <div class="stats-container">
                <div class="stat-box success">
                    <div class="stat-label">Present</div>
                    <div class="stat-value">{{ stats.present }}</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-label">Late</div>
                    <div class="stat-value">{{ stats.late }}</div>
                </div>
                <div class="stat-box danger">
                    <div class="stat-label">Absent</div>
                    <div class="stat-value">{{ stats.absent }}</div>
                </div>
                <div class="stat-box info">
                    <div class="stat-label">Attendance Rate</div>
                    <div class="stat-value">{{ stats.attendance_rate }}%</div>
                </div>
            </div>
            
            <div class="chart-container">
                <h3>Attendance Distribution</h3>
                <img src="data:image/png;base64,{{ chart }}" alt="Attendance Chart">
            </div>
            
            <h2>Student Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Time</th>
                        <th>Method</th>
                    </tr>
                </thead>
                <tbody>
                    {% for student in students %}
                    <tr>
                        <td>{{ student.student_id }}</td>
                        <td>{{ student.name }}</td>
                        <td>
                            <span class="status-badge status-{{ student.status|lower }}">
                                {{ student.status }}
                            </span>
                        </td>
                        <td>{{ student.timestamp or '-' }}</td>
                        <td>{{ student.method or '-' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            {% if session_info.notes %}
            <div class="info-section">
                <h3>Session Notes</h3>
                <p>{{ session_info.notes }}</p>
            </div>
            {% endif %}
            
            <div class="footer">
                <p>Generated on {{ generated_at }}</p>
                <p>Face Recognition Attendance System</p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            session_info=session_info,
            stats=stats,
            students=students,
            chart=chart_base64,
            generated_at=report_data['generated_at']
        )
        
        return self._render_pdf(html_content, output_path)
    
    def generate_class_report(self, report_data, output_path=None):
        """Generate PDF report for class summary"""
        class_info = report_data['class_info']
        stats = report_data['statistics']
        sessions = report_data['sessions']
        students = report_data['students']
        
        # Generate attendance trend chart
        dates = [s['date'] for s in sessions[-10:]]  # Last 10 sessions
        rates = [s['attendance_rate'] for s in sessions[-10:]]
        trend_chart = self._generate_line_chart(dates, rates, 'Date', 'Attendance %')
        
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Class Report</title>
        </head>
        <body>
            <div class="header">
                <h1>Class Attendance Report</h1>
                <div class="subtitle">{{ class_info.class_name }}</div>
                <div class="subtitle">{{ class_info.course_code }} - {{ class_info.course_name }}</div>
            </div>
            
            <div class="info-section">
                <h3>Class Information</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Class ID:</span> {{ class_info.class_id }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Total Students:</span> {{ class_info.total_students }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Year:</span> {{ class_info.year }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Semester:</span> {{ class_info.semester }}
                    </div>
                </div>
            </div>
            
            <div class="stats-container">
                <div class="stat-box info">
                    <div class="stat-label">Total Sessions</div>
                    <div class="stat-value">{{ period.total_sessions }}</div>
                </div>
                <div class="stat-box success">
                    <div class="stat-label">Completed</div>
                    <div class="stat-value">{{ period.completed_sessions }}</div>
                </div>
                <div class="stat-box info">
                    <div class="stat-label">Avg Attendance</div>
                    <div class="stat-value">{{ stats.average_attendance_rate }}%</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-label">Total Absent</div>
                    <div class="stat-value">{{ stats.total_absent }}</div>
                </div>
            </div>
            
            <div class="chart-container">
                <h3>Attendance Trend (Last 10 Sessions)</h3>
                <img src="data:image/png;base64,{{ trend_chart }}" alt="Trend Chart">
            </div>
            
            <h2>Student Performance Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Present</th>
                        <th>Late</th>
                        <th>Absent</th>
                        <th>Rate</th>
                    </tr>
                </thead>
                <tbody>
                    {% for student in students %}
                    <tr>
                        <td>{{ student.student_id }}</td>
                        <td>{{ student.name }}</td>
                        <td>{{ student.present }}</td>
                        <td>{{ student.late }}</td>
                        <td>{{ student.absent }}</td>
                        <td>
                            <strong style="color: {% if student.attendance_rate >= 75 %}#27ae60{% else %}#e74c3c{% endif %}">
                                {{ student.attendance_rate }}%
                            </strong>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <div class="footer">
                <p>Report Period: {{ period.start_date }} to {{ period.end_date }}</p>
                <p>Generated on {{ generated_at }}</p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            class_info=class_info,
            period=report_data['period'],
            stats=stats,
            sessions=sessions,
            students=students,
            trend_chart=trend_chart,
            generated_at=report_data['generated_at']
        )
        
        return self._render_pdf(html_content, output_path)
    
    def generate_student_report(self, report_data, output_path=None):
        """Generate PDF report for individual student"""
        student_info = report_data['student_info']
        class_info = report_data['class_info']
        stats = report_data['statistics']
        history = report_data['attendance_history']
        
        # Generate status chart
        chart = self._generate_donut_chart(
            [stats['present'], stats['late'], stats['absent']],
            ['Present', 'Late', 'Absent'],
            ['#27ae60', '#f39c12', '#e74c3c']
        )
        
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Student Report</title>
        </head>
        <body>
            <div class="header">
                <h1>Student Attendance Report</h1>
                <div class="subtitle">{{ student_info.name }}</div>
                <div class="subtitle">{{ student_info.student_id }}</div>
            </div>
            
            <div class="info-section">
                <h3>Student Information</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-label">Email:</span> {{ student_info.email }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Phone:</span> {{ student_info.phone }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Course:</span> {{ student_info.course }}
                    </div>
                    <div class="info-item">
                        <span class="info-label">Year:</span> {{ student_info.year }}
                    </div>
                </div>
            </div>
            
            <div class="info-section">
                <h3>Class Information</h3>
                <p><strong>{{ class_info.class_name }}</strong> - {{ class_info.course_code }}: {{ class_info.course_name }}</p>
            </div>
            
            <div class="stats-container">
                <div class="stat-box success">
                    <div class="stat-label">Present</div>
                    <div class="stat-value">{{ stats.present }}</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-label">Late</div>
                    <div class="stat-value">{{ stats.late }}</div>
                </div>
                <div class="stat-box danger">
                    <div class="stat-label">Absent</div>
                    <div class="stat-value">{{ stats.absent }}</div>
                </div>
                <div class="stat-box info">
                    <div class="stat-label">Rate</div>
                    <div class="stat-value">{{ stats.attendance_rate }}%</div>
                </div>
            </div>
            
            {% if stats.attendance_rate < 75 %}
            <div class="alert-box">
                <h4>⚠️ Low Attendance Alert</h4>
                <p>This student's attendance rate is below the recommended 75% threshold.</p>
            </div>
            {% endif %}
            
            <div class="chart-container">
                <h3>Attendance Distribution</h3>
                <img src="data:image/png;base64,{{ chart }}" alt="Attendance Chart">
            </div>
            
            <h2>Attendance History</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Time</th>
                        <th>Status</th>
                        <th>Marked At</th>
                        <th>Method</th>
                    </tr>
                </thead>
                <tbody>
                    {% for record in history %}
                    <tr>
                        <td>{{ record.date }}</td>
                        <td>{{ record.start_time }} - {{ record.end_time }}</td>
                        <td>
                            <span class="status-badge status-{{ record.status|lower }}">
                                {{ record.status }}
                            </span>
                        </td>
                        <td>{{ record.timestamp or '-' }}</td>
                        <td>{{ record.method or '-' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <div class="footer">
                <p>Generated on {{ generated_at }}</p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            student_info=student_info,
            class_info=class_info,
            stats=stats,
            history=history,
            chart=chart,
            generated_at=report_data['generated_at']
        )
        
        return self._render_pdf(html_content, output_path)
    
    def generate_alert_report(self, report_data, output_path=None):
        """Generate PDF report for low attendance alerts"""
        alert_info = report_data['alert_info']
        students = report_data['students']
        
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Low Attendance Alert</title>
        </head>
        <body>
            <div class="header">
                <h1>⚠️ Low Attendance Alert Report</h1>
                <div class="subtitle">Students Below {{ alert_info.threshold }}% Attendance</div>
            </div>
            
            <div class="alert-box">
                <h4>Alert Summary</h4>
                <p><strong>{{ alert_info.total_at_risk }}</strong> students have attendance below the {{ alert_info.threshold }}% threshold.</p>
                <p>Instructor: {{ alert_info.instructor_name }}</p>
            </div>
            
            <h2>At-Risk Students</h2>
            <table>
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Class</th>
                        <th>Course</th>
                        <th>Attended</th>
                        <th>Missed</th>
                        <th>Rate</th>
                    </tr>
                </thead>
                <tbody>
                    {% for student in students %}
                    <tr>
                        <td>{{ student.student_id }}</td>
                        <td>{{ student.name }}</td>
                        <td>{{ student.class_name }}</td>
                        <td>{{ student.course_code }}</td>
                        <td>{{ student.attended }}/{{ student.total_sessions }}</td>
                        <td>{{ student.sessions_missed }}</td>
                        <td>
                            <strong style="color: {% if student.attendance_rate < 50 %}#e74c3c{% elif student.attendance_rate < 65 %}#f39c12{% else %}#f39c12{% endif %}">
                                {{ student.attendance_rate }}%
                            </strong>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            
            <div class="footer">
                <p>Generated on {{ generated_at }}</p>
                <p>Please follow up with these students regarding their attendance.</p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            alert_info=alert_info,
            students=students,
            generated_at=report_data['generated_at']
        )
        
        return self._render_pdf(html_content, output_path)
    
    # ========== Helper Methods ==========
    
    def _render_pdf(self, html_content, output_path=None):
        """Render HTML to PDF"""
        html = HTML(string=html_content)
        css = CSS(string=self.base_css)
        
        if output_path:
            html.write_pdf(output_path, stylesheets=[css])
            return None
        else:
            return html.write_pdf(stylesheets=[css])
    
    def _generate_donut_chart(self, values, labels, colors):
        """Generate donut chart and return as base64 string"""
        fig, ax = plt.subplots(figsize=(8, 6))
        
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            wedgeprops=dict(width=0.5)
        )
        
        # Style the text
        for text in texts:
            text.set_fontsize(12)
            text.set_weight('bold')
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(10)
            autotext.set_weight('bold')
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode()
        plt.close()
        
        return image_base64
    
    def _generate_line_chart(self, x_data, y_data, xlabel, ylabel):
        """Generate line chart and return as base64 string"""
        fig, ax = plt.subplots(figsize=(10, 5))
        
        ax.plot(x_data, y_data, marker='o', linewidth=2, markersize=8, color='#3498db')
        ax.set_xlabel(xlabel, fontsize=12, weight='bold')
        ax.set_ylabel(ylabel, fontsize=12, weight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode()
        plt.close()
        
        return image_base64