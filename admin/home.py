import sys
import sqlite3
import datetime
import os
import csv
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLineEdit, QFrame, QStackedWidget, QGridLayout, QScrollArea, QSizePolicy,
    QSpacerItem, QMessageBox, QToolTip
)
from PyQt5.QtGui import QFont, QPixmap, QCursor
from PyQt5.QtCore import Qt, QTimer, QDateTime, pyqtSignal, QObject
from admin.start_attendance_window import StartAttendanceWindow
from admin.view_attendance import ViewAttendanceWindow
from admin.register_student import RegisterStudentWindow
import cv2


class UnknownFacesCounter(QObject):
    """Thread-safe counter for unknown faces with signal support"""
    count_updated = pyqtSignal(int)
    
    def __init__(self, folder_path):
        super().__init__()
        self._folder_path = folder_path
        self._last_count = 0
        self._last_check_time = 0
        self._lock = threading.Lock()
    
    def count_images(self):
        """Count image files in the folder in a background thread"""
        thread = threading.Thread(target=self._perform_count)
        thread.daemon = True
        thread.start()
    
    def _perform_count(self):
        """Actual counting operation, runs in background thread"""
        current_time = datetime.datetime.now().timestamp()
        
        # Only count if more than 30 seconds have passed since last count
        with self._lock:
            time_since_last = current_time - self._last_check_time
            if time_since_last < 30 and self._last_check_time > 0:
                # Just emit the stored count without recounting
                self.count_updated.emit(self._last_count)
                return
        
        try:
            if os.path.exists(self._folder_path):
                count = len([f for f in os.listdir(self._folder_path) 
                           if os.path.isfile(os.path.join(self._folder_path, f)) 
                           and f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            else:
                count = 0
                
            with self._lock:
                self._last_count = count
                self._last_check_time = current_time
                
            # Emit signal with the count
            self.count_updated.emit(count)
        except Exception as e:
            print(f"Error counting unknown faces: {e}")
            # Return last known count on error
            with self._lock:
                self.count_updated.emit(self._last_count)


class HomeWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._last_statistics_update = datetime.datetime.min
        self._last_activity_update = datetime.datetime.min
        self._last_system_status_check = datetime.datetime.min

        self.setWindowTitle("🏠 Admin Dashboard")
        self.setGeometry(100, 100, 900, 600)
        self.setContentsMargins(10, 10, 10, 10)
        self.setObjectName("HomeWindow")  # For QSS targeting

        # Path to unknown faces folder
        self.unknown_faces_folder = "unknown_faces"
        # Make sure the folder exists
        if not os.path.exists(self.unknown_faces_folder):
            os.makedirs(self.unknown_faces_folder)
        
        # Initialize unknown faces counter
        self.unknown_counter = UnknownFacesCounter(self.unknown_faces_folder)
        self.unknown_counter.count_updated.connect(self.update_unknown_count)

        # Get the global stylesheet
        self.setStyleSheet(QApplication.instance().styleSheet())

        # 🔹 **Main Layout**
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)
        
        # ✅ **Create a scrollable content area**
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.scroll_content = QWidget()
        self.content_area = QVBoxLayout(self.scroll_content)
        self.content_area.setSpacing(15)  # Add breathing room between widgets
        self.scroll_area.setWidget(self.scroll_content)
        
        # Add scroll area to main layout
        self.main_layout.addWidget(self.scroll_area, 7)  # 70% of the width

        
        # ✅ **Notification Area**
        self.notification_layout = QVBoxLayout()
        self.notification_label = None  # Will be created when needed
        self.content_area.addLayout(self.notification_layout)


        # ✅ **Header with Search and Time**
        self.create_header()

        # ✅ **Quick Stats Overview Row**
        self.create_quick_stats_row()

        # ✅ **Action Buttons with Clear Labels**
        self.create_action_buttons()

        # ✅ **Main Dashboard Content in Grid Layout**
        self.create_main_content_grid()

        # ✅ **System Status Footer**
        self.create_system_status_footer()

        # ✅ **Right Sidebar (Quick Stats & Profile)**
        self.right_panel = self.create_right_panel()
        self.main_layout.addWidget(self.right_panel, 3)  # 30% of the width

        # 🔹 **Update Data Timer**
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)  # Update every second
        
        # Access theme manager if available
        self.theme_manager = QApplication.instance().property("theme_manager")
        
        # Initial data load
        self.load_statistics()
        self.load_recent_activity()

    def create_header(self):
        """Creates the header with search and time display."""
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QVBoxLayout(header_frame)  # Changed to QVBoxLayout for vertical stacking
        header_layout.setContentsMargins(0, 0, 0, 10)
        
        # Top row with title and logo
        title_container = QFrame()
        title_container.setObjectName("TitleContainer")
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 18)  # Added bottom margin
        
        logo_label = QLabel("👁️")
        logo_label.setFont(QFont("Arial", 24))
        logo_label.setObjectName("DashboardLogo")
        
        dashboard_title = QLabel("Attendance Monitoring System")
        dashboard_title.setFont(QFont("Arial", 22, QFont.Bold))  # Increased font size
        dashboard_title.setObjectName("DashboardTitle")
        dashboard_title.setAlignment(Qt.AlignCenter)  # Center the title
        
        title_layout.addWidget(logo_label, 1)
        title_layout.addWidget(dashboard_title, 5)  # Give more space to title
        title_layout.addStretch(1)
        
        # Bottom row with search and time
        controls_container = QFrame()
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search bar with improved styling
        search_container = QFrame()
        search_container.setObjectName("SearchContainer")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search students or records...")
        self.search_bar.setObjectName("DashboardSearchBar")
        self.search_bar.setFixedHeight(55)
        self.search_bar.setMinimumWidth(300)  # Set minimum width for search bar
        
        search_layout.addWidget(self.search_bar)
        
        # Time label
        time_container = QFrame()
        time_container.setObjectName("TimeContainer")
        time_layout = QHBoxLayout(time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Arial", 12))
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setObjectName("TimeLabel")
        self.time_label.setMinimumWidth(220)  # Ensure time has enough space
        
        time_layout.addWidget(self.time_label)
        
        # Add bottom row elements with better proportions
        controls_layout.addWidget(search_container, 7)  # More space for search
        controls_layout.addWidget(time_container, 4)  # Less space for time
        
        # Add all components to header
        header_layout.addWidget(title_container)
        header_layout.addWidget(controls_container)
        
        self.content_area.addWidget(header_frame)

    def create_quick_stats_row(self):
        """Creates a row of quick statistics."""
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsOverview")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(0, 8, 0, 8)
        
        # Total Students Stat
        self.total_students_label = QLabel("--")
        self.total_students_label.setObjectName("StatNumber")
        self.total_students_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.total_students_label.setAlignment(Qt.AlignCenter)
        
        total_students_box = QFrame()
        total_students_box.setObjectName("StatBox")
        total_students_box.setToolTip("Total number of registered students\n"
                                      "Shows all students in the system")
        total_box_layout = QVBoxLayout(total_students_box)
        total_box_layout.addWidget(self.total_students_label)
        total_box_layout.addWidget(QLabel("👥 Total Students"))
        
        # Today's Attendance Stat
        self.today_attendance_label = QLabel("--%")
        self.today_attendance_label.setObjectName("StatNumber")
        self.today_attendance_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.today_attendance_label.setAlignment(Qt.AlignCenter)
        
        attendance_box = QFrame()
        attendance_box.setObjectName("StatBox")
        attendance_box.setToolTip("Attendance rate for today\n"
                                  "Percentage of students present")
        attendance_box_layout = QVBoxLayout(attendance_box)
        attendance_box_layout.addWidget(self.today_attendance_label)
        attendance_box_layout.addWidget(QLabel("📊 Today's Attendance"))
        
        # Unknown Faces Stat - Modified to use directory count and clickable
        self.unknown_faces_label = QLabel("0")
        self.unknown_faces_label.setObjectName("StatNumber")
        self.unknown_faces_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.unknown_faces_label.setAlignment(Qt.AlignCenter)
        self.unknown_faces_label.setCursor(QCursor(Qt.PointingHandCursor))
        self.unknown_faces_label.mousePressEvent = self.open_unknown_faces
        
        unknown_box = QFrame()
        unknown_box.setObjectName("StatBox")
        unknown_box.setToolTip("Number of unrecognized faces detected\n"
                               "Click to review and manage unknown faces")
        unknown_box.setCursor(QCursor(Qt.PointingHandCursor))
        unknown_box.mousePressEvent = self.open_unknown_faces
        
        unknown_title = QLabel("🔴 Unknown Faces")
        unknown_title.setCursor(QCursor(Qt.PointingHandCursor))
        unknown_title.mousePressEvent = self.open_unknown_faces
        
        unknown_box_layout = QVBoxLayout(unknown_box)
        unknown_box_layout.addWidget(self.unknown_faces_label)
        unknown_box_layout.addWidget(unknown_title)
        
        stats_layout.addWidget(total_students_box)
        stats_layout.addWidget(attendance_box)
        stats_layout.addWidget(unknown_box)
        
        self.content_area.addWidget(stats_frame)

    def create_action_buttons(self):
        """Creates improved action buttons with better visual design."""
        actions_frame = QFrame()
        actions_frame.setObjectName("actionCard")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setSpacing(15) 
        actions_layout.setContentsMargins(0, 8, 0, 8)
        
        # Start Attendance Button - Improved
        self.start_attendance_btn = QPushButton()
        self.start_attendance_btn.setObjectName("startAttendanceCard")
        self.start_attendance_btn.setToolTip("Begin facial recognition attendance tracking\n"
                                            "Capture student attendance using camera")
        self.start_attendance_btn.setMinimumHeight(150)  # Increased height
        self.start_attendance_btn.setMinimumWidth(180)  # Set minimum width
        self.start_attendance_btn.setCursor(QCursor(Qt.PointingHandCursor))
        start_layout = QVBoxLayout()
        start_layout.setAlignment(Qt.AlignCenter)
        start_layout.setContentsMargins(15, 20, 15, 20)  # Increased padding
        
        start_icon = QLabel("📸")
        start_icon.setFont(QFont("Arial", 22))  # Larger icon
        start_icon.setAlignment(Qt.AlignCenter)
        start_icon.setObjectName("actionIcon")
        
        start_text = QLabel("Start Attendance")
        start_text.setFont(QFont("Arial", 14, QFont.Bold))  # Better font
        start_text.setAlignment(Qt.AlignCenter)
        start_text.setObjectName("actionTitle")
        
        start_desc = QLabel("Take attendance with face recognition")
        start_desc.setAlignment(Qt.AlignCenter)
        start_desc.setObjectName("actionDescription")
        start_desc.setWordWrap(True)
        
        start_layout.addWidget(start_icon)
        start_layout.addWidget(start_text)
        start_layout.addWidget(start_desc)
        self.start_attendance_btn.clicked.connect(self.open_start_attendance)
        self.start_attendance_btn.setLayout(start_layout)
        
        # View Records Button - Improved
        self.view_records_btn = QPushButton()
        self.view_records_btn.setObjectName("viewRecordsCard")
        self.view_records_btn.setToolTip("View detailed attendance records\n"
                                        "Browse historical attendance data")
        self.view_records_btn.setMinimumHeight(150)  # Increased height
        self.view_records_btn.setMinimumWidth(180)  # Set minimum width
        self.view_records_btn.setCursor(QCursor(Qt.PointingHandCursor))
        records_layout = QVBoxLayout()
        records_layout.setAlignment(Qt.AlignCenter)
        records_layout.setContentsMargins(15, 20, 15, 20)  # Increased padding
        
        records_icon = QLabel("📊")  
        records_icon.setFont(QFont("Arial", 24))  # Larger icon
        records_icon.setAlignment(Qt.AlignCenter)
        records_icon.setObjectName("actionIcon")
        
        records_text = QLabel("View Records")
        records_text.setFont(QFont("Arial", 14, QFont.Bold))  # Better font
        records_text.setAlignment(Qt.AlignCenter)
        records_text.setObjectName("actionTitle")
        
        records_desc = QLabel("Check attendance history and reports")
        records_desc.setAlignment(Qt.AlignCenter)
        records_desc.setObjectName("actionDescription")
        records_desc.setWordWrap(True)
        
        records_layout.addWidget(records_icon)
        records_layout.addWidget(records_text)
        records_layout.addWidget(records_desc)
        self.view_records_btn.setLayout(records_layout)
        self.view_records_btn.clicked.connect(self.open_view_records)

        # Add Student Button - Improved
        self.add_student_btn = QPushButton()
        self.add_student_btn.setObjectName("addStudentCard")
        self.add_student_btn.setToolTip("Register new students in the system\n"
                                        "Add student details and facial data")
        self.add_student_btn.setMinimumHeight(150)  # Increased height
        self.add_student_btn.setMinimumWidth(180)  # Set minimum width
        self.add_student_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_layout = QVBoxLayout()
        add_layout.setAlignment(Qt.AlignCenter)
        add_layout.setContentsMargins(15, 20, 15, 20)  # Increased padding
        
        add_icon = QLabel("👤")
        add_icon.setFont(QFont("Arial", 24))  # Larger icon
        add_icon.setAlignment(Qt.AlignCenter)
        add_icon.setObjectName("actionIcon")
        
        add_text = QLabel("Add Student")
        add_text.setFont(QFont("Arial", 14, QFont.Bold))  # Better font
        add_text.setAlignment(Qt.AlignCenter)
        add_text.setObjectName("actionTitle")
        
        add_desc = QLabel("Register new students in the system")
        add_desc.setAlignment(Qt.AlignCenter)
        add_desc.setObjectName("actionDescription")
        add_desc.setWordWrap(True)
        
        add_layout.addWidget(add_icon)
        add_layout.addWidget(add_text)
        add_layout.addWidget(add_desc)
        self.add_student_btn.setLayout(add_layout)
        self.add_student_btn.clicked.connect(self.open_add_student)
        
        actions_layout.addWidget(self.start_attendance_btn)
        actions_layout.addWidget(self.view_records_btn)
        actions_layout.addWidget(self.add_student_btn)
        
        self.content_area.addWidget(actions_frame)

    def create_main_content_grid(self):
        """Creates a grid layout for main content cards."""
        grid_frame = QFrame()
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setSpacing(12)  # Space between grid items
        
        # Recent Activity Card - Taller, spans 2 rows
        self.recent_activity_card = self.create_card("📌 Recent Activity")
        self.recent_activity_list = QLabel("Loading recent logs...")
        self.recent_activity_list.setObjectName("ActivityList")
        self.recent_activity_list.setWordWrap(True)
        self.recent_activity_card.layout().addWidget(self.recent_activity_list)
        
        # Analytics Card
        self.analytics_card = self.create_card("📊 Attendance Trends")
        self.analytics_card.layout().addWidget(QLabel("Attendance graph will be displayed here."))
        
        # Monthly Report Card
        self.monthly_report_card = self.create_card("📆 Monthly Summary")
        self.monthly_report_card.layout().addWidget(QLabel("Monthly attendance statistics will appear here."))
        
        # Add cards to grid
        grid_layout.addWidget(self.recent_activity_card, 0, 0, 2, 1)  # Spans 2 rows
        grid_layout.addWidget(self.analytics_card, 0, 1, 1, 1)
        grid_layout.addWidget(self.monthly_report_card, 1, 1, 1, 1)
        
        self.content_area.addWidget(grid_frame)

    def create_system_status_footer(self):
        """Creates a footer with system status indicators."""
        status_frame = QFrame()
        status_frame.setObjectName("StatusPanel")
        status_layout = QHBoxLayout(status_frame)
        
        self.last_update_time = QLabel("Last updated: Just now")
        self.last_update_time.setAlignment(Qt.AlignRight)

      
        status_layout.addStretch()
        status_layout.addWidget(self.last_update_time)
        
        self.content_area.addWidget(status_frame)

    def create_card(self, title):
        """Creates a styled card UI for dashboard widgets."""
        card = QFrame()
        card.setObjectName("DashboardCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)  # Add internal padding
        
        label = QLabel(title)
        label.setFont(QFont("Arial", 14, QFont.Bold))
        label.setObjectName("CardTitle")
        
        # Add a subtle separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("CardSeparator")
        
        layout.addWidget(label)
        layout.addWidget(separator)
        layout.addSpacing(10)  # Space after title
        
        return card

    def create_right_panel(self):
        panel = QFrame()
        panel.setFixedWidth(250)  # Slightly narrower
        panel.setObjectName("RightPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Admin Profile Section
        profile_section = QFrame()
        profile_section.setObjectName("ProfileSection")
        profile_layout = QVBoxLayout(profile_section)
        
        profile_pic = QLabel()
        profile_pic.setPixmap(QPixmap("icons/admin_profile.png").scaled(80, 80, Qt.KeepAspectRatio))
        profile_pic.setAlignment(Qt.AlignCenter)
        
        admin_name = QLabel("Admin Name")
        admin_name.setFont(QFont("Arial", 14, QFont.Bold))
        admin_name.setAlignment(Qt.AlignCenter)
        admin_name.setObjectName("AdminName")
        
        admin_role = QLabel("System Administrator")
        admin_role.setAlignment(Qt.AlignCenter)
        admin_role.setObjectName("AdminRole")
        
        profile_layout.addWidget(profile_pic)
        profile_layout.addWidget(admin_name)
        profile_layout.addWidget(admin_role)

        # System Information Section
        system_section = QFrame()
        system_section.setObjectName("SystemSection")
        system_layout = QVBoxLayout(system_section)
        
        system_title = QLabel("System Status")
        system_title.setFont(QFont("Arial", 12, QFont.Bold))
        system_title.setObjectName("SystemTitle")
        
        self.database_status = QLabel("🟢 Database: Connected")
        self.camera_status = QLabel("🟢 Camera: Connected")
        self.last_backup = QLabel("🔄 Last Backup: Today")
        
        system_layout.addWidget(system_title)
        system_layout.addWidget(self.database_status)
        system_layout.addWidget(self.camera_status)
        system_layout.addWidget(self.last_backup)
        
        # Quick Actions Section
        actions_section = QFrame()
        actions_section.setObjectName("ActionsSection")
        actions_layout = QVBoxLayout(actions_section)
        
        actions_title = QLabel("Quick Actions")
        actions_title.setFont(QFont("Arial", 12, QFont.Bold))
        actions_title.setObjectName("ActionsTitle")
        
        backup_btn = QPushButton("💾 Backup Data")
        backup_btn.setObjectName("ActionButton")
        backup_btn.setToolTip("Create a backup of the attendance database\n"
                            "Preserves all current student and attendance records")
        backup_btn.setMinimumHeight(36)
        backup_btn.clicked.connect(self.backup_database)

        export_btn = QPushButton("📊 Export Reports")
        export_btn.setObjectName("ActionButton")
        export_btn.setToolTip("Generate CSV reports for attendance\n"
                                "Create daily and monthly attendance summaries")
        export_btn.setMinimumHeight(36) 
        export_btn.clicked.connect(self.export_reports)

        actions_layout.addWidget(actions_title)
        actions_layout.addWidget(backup_btn)
        actions_layout.addWidget(export_btn)
        
        # Add all sections to panel
        layout.addWidget(profile_section)
        layout.addWidget(system_section)
        layout.addWidget(actions_section)
        layout.addStretch()  # Push remaining widgets to bottom

        # Theme toggle button
        theme_btn = QPushButton("🌓 Toggle Theme")
        theme_btn.setObjectName("ActionButton")
        theme_btn.setToolTip("Switch between light and dark themes\n"
                                "Adjust the application's visual appearance")
        theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(theme_btn)
        
        # Logout button
        logout_btn = QPushButton("🚪 Logout")
        logout_btn.setObjectName("ActionButton")
        logout_btn.setToolTip("Exit the current session\n"
                                  "Return to the login screen")
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)

        return panel
    def backup_database(self):
        """Creates a backup of the attendance database"""
        try:
            # Get current date and time for filename
            now = datetime.datetime.now()
            backup_filename = f"backup_attendance_{now.strftime('%Y%m%d_%H%M%S')}.db"
            backup_dir = "backups"
            
            # Create backup directory if it doesn't exist
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            backup_path = os.path.join(backup_dir, backup_filename)
            
            # Connect to the source database
            source_conn = sqlite3.connect("attendance.db")
            
            # Create a new database file for the backup
            dest_conn = sqlite3.connect(backup_path)
            
            # Copy the data using the iterdump method
            with dest_conn:
                source_conn.backup(dest_conn)
                
            source_conn.close()
            dest_conn.close()
            
            # Update the last backup label
            self.last_backup.setText(f"🔄 Last Backup: {now.strftime('%H:%M:%S')}")
            
            QMessageBox.information(self, "Backup Complete", 
                            f"Database backed up successfully to {backup_path}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", 
                            f"Could not create backup: {str(e)}")
            print(f"Error creating backup: {e}")

    def export_reports(self):
        """Exports attendance reports to CSV files"""
        try:
            # Create export directory if it doesn't exist
            export_dir = "reports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
                
            # Get current date for filename
            today = datetime.date.today().strftime('%Y%m%d')
            
            # Connect to database
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            
            # Export daily attendance report
            daily_report_path = os.path.join(export_dir, f"daily_attendance_{today}.csv")
            with open(daily_report_path, 'w', newline='') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(['Name', 'Status', 'Time', 'Student ID', 'Class', ])
                
                # Get today's attendance records
                current_date = datetime.date.today().strftime('%Y-%m-%d')
                cursor.execute("""
                    SELECT s.name, a.status, a.timestamp, ses.course_name, ses.class_name
                    FROM attendance a
                    JOIN students s ON a.student_id = s.student_id
                    WHERE a.timestamp = ?
                    ORDER BY s.name                              
                               
                """, (current_date,))
                
                for row in cursor.fetchall():
                    csv_writer.writerow(row)
            
            # Export monthly summary report
            month_start = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
            month_end = datetime.date.today().strftime('%Y-%m-%d')
            monthly_report_path = os.path.join(export_dir, f"monthly_attendance_{today[:6]}.csv")
            
            with open(monthly_report_path, 'w', newline='') as csv_file:
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(['Student ID', 'Name', 'Present Days', 'Absent Days', 'Attendance Rate'])
                
                # Get monthly attendance statistics
                cursor.execute("""
                    SELECT s.student_id, s.name,
                        SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_days,
                        SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_days
                    FROM students s
                    LEFT JOIN attendance a ON s.student_id = a.student_id
                    WHERE a.date BETWEEN ? AND ?
                    GROUP BY s.student_id
                    ORDER BY s.name
                """, (month_start, month_end))
                
                for row in cursor.fetchall():
                    student_id, name, present_days, absent_days = row
                    total_days = present_days + absent_days
                    attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
                    csv_writer.writerow([student_id, name, present_days, absent_days, f"{attendance_rate:.1f}%"])
            
            conn.close()
            
            QMessageBox.information(self, "Export Complete", 
                            f"Reports exported successfully to the '{export_dir}' directory:\n\n"
                            f"- Daily attendance: {os.path.basename(daily_report_path)}\n"
                            f"- Monthly summary: {os.path.basename(monthly_report_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", 
                            f"Could not export reports: {str(e)}")
            print(f"Error exporting reports: {e}")

    def open_start_attendance(self):
        """Opens the Start Attendance window."""
        try:
            from admin.start_attendance_window import StartAttendanceWindow
            self.start_attendance_window = StartAttendanceWindow()
            self.start_attendance_window.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open Start Attendance window: {str(e)}")
            print(f"Error opening Start Attendance window: {e}")

    def open_view_records(self):
        """Opens the View Records window."""
        try:
            # Replace with your actual import and class name
            from admin.view_attendance import ViewAttendanceWindow
            self.view_attendance = ViewAttendanceWindow()
            self.view_attendance.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open View Records window: {str(e)}")
            print(f"Error opening View Records window: {e}")

    def open_add_student(self):
        """Opens the Add Student window."""
        try:
            # Replace with your actual import and class name
            from admin.register_student import RegisterStudentWindow
            self.register_student = RegisterStudentWindow()
            self.register_student.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open Add Student window: {str(e)}")
            print(f"Error opening Add Student window: {e}")

    def update_data(self):
        """Optimized method to update dynamic data in the dashboard."""
        now = datetime.datetime.now()
        
        # Always update time display
        self.time_label.setText(now.strftime("%H:%M:%S | %A, %b %d"))
        self.last_update_time.setText(f"Last updated: {now.strftime('%H:%M:%S')}")
        
        # Optimize update frequencies
        try:
            # Check statistics every 30 seconds
            if (now - self._last_statistics_update).total_seconds() >= 30:
                self.load_statistics()
                self._last_statistics_update = now
            
            # Check recent activity every 15 seconds
            if (now - self._last_activity_update).total_seconds() >= 15:
                self.load_recent_activity()
                self._last_activity_update = now
            
            # Check system status every minute
            if (now - self._last_system_status_check).total_seconds() >= 60:
                self.check_system_status()
                self._last_system_status_check = now
        
        except Exception as e:
            # Log the error or show a notification
            print(f"Dashboard update error: {e}")
            
            # Optional: Show a less intrusive error notification
            QToolTip.showText(
                self.mapToGlobal(self.rect().center()), 
                f"Dashboard update failed: {str(e)}", 
                self, 
                self.rect(), 
                3000  # Show for 3 seconds
            )


    def load_statistics(self):
        """Load statistics from the database and unknown faces from folder."""
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()

            # Count total students
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]

            # Count today's attendance using the updated schema
            today = datetime.date.today().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(DISTINCT a.student_id) 
                FROM attendance a
                JOIN class_sessions cs ON a.session_id = cs.session_id
                WHERE cs.date = ? AND a.status = 'Present'
            """, (today,))
            today_attendance = cursor.fetchone()[0]

            self.total_students_label.setText(f"{total_students}")
            
            attendance_rate = (today_attendance / total_students) * 100 if total_students else 0
            self.today_attendance_label.setText(f"{attendance_rate:.1f}%")
            
            # Trigger unknown faces count in background thread
            self.unknown_counter.count_images()

            conn.close()
        except Exception as e:
            self.total_students_label.setText("--")
            self.today_attendance_label.setText("--%")
            print(f"Error loading statistics: {e}")
            self.database_status.setText("🔴 Database: Error")
                        
    def update_unknown_count(self, count):
        """Update the UI with the unknown faces count (called via signal)"""
        self.unknown_faces_label.setText(f"{count}")
        
        # Show or hide the notification
        if count > 0:
            self.show_unknown_notification(count)
        else:
            self.hide_unknown_notification()

    def show_unknown_notification(self, count):
        """Display a clickable notification for unknown faces"""
        if not self.notification_label:
            self.notification_label = QLabel()
            self.notification_label.setObjectName("NotificationLabel")
            self.notification_label.setStyleSheet("""
                QLabel#NotificationLabel {
                    background-color: #ffcc00;
                    color: #333333;
                    border-radius: 4px;
                    padding: 8px;
                    font-weight: bold;
                }
                QLabel#NotificationLabel:hover {
                    background-color: #e6b800;
                }
            """)
            self.notification_label.setCursor(QCursor(Qt.PointingHandCursor))
            self.notification_label.mousePressEvent = self.open_unknown_faces
            self.notification_layout.addWidget(self.notification_label)
        
        self.notification_label.setText(f"🔔 {count} unknown {'face' if count == 1 else 'faces'} detected! Click here to review.")
        self.notification_label.setVisible(True)

    def hide_unknown_notification(self):
        """Hide the notification when there are no unknown faces"""
        if self.notification_label:
            self.notification_label.setVisible(False)

    def open_unknown_faces(self, event=None):
        """Open the unknown faces review window"""
        # Check if there are any unknown faces
        count = int(self.unknown_faces_label.text())
        if count == 0:
            QMessageBox.information(self, "No Unknown Faces", 
                                "There are currently no unknown faces to review.")
            return
            
        # Create and show the unknown faces review dialog
        # Fixed: Properly import from ui.review_unknown_window
        from admin.review_unknown_window import ReviewUnknownFacesWindow
        
        # Fixed: Create the ReviewUnknownFacesWindow instance correctly
        self.unknown_review = ReviewUnknownFacesWindow()
        
        # Connect the signal to update our counter when faces are processed
        # This requires a signal to be defined in the ReviewUnknownFacesWindow class
        # For now, we'll update manually after window closes
        self.unknown_review.setWindowModality(Qt.ApplicationModal)
        self.unknown_review.show()
        
        # When the window is closed, update the counter
        self.unknown_review.destroyed.connect(self.refresh_unknown_faces)

    def refresh_unknown_faces(self):
        """Refresh the unknown faces count after reviewing"""
        # Force a refresh of unknown faces count
        self.unknown_counter.count_images()

    def update_after_review(self, remaining_count):
        """Update the UI after the unknown faces review is complete"""
        # Update the counter immediately instead of waiting for the timer
        self.unknown_faces_label.setText(str(remaining_count))
        
        # Update notification status
        if remaining_count > 0:
            self.show_unknown_notification(remaining_count)
        else:
            self.hide_unknown_notification()
        
        # Force a refresh of statistics
        self.load_statistics()

    def load_recent_activity(self):
        """Load the latest 5 attendance logs."""
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()

            # Updated query to match the schema
            cursor.execute("""
                SELECT s.fname, s.lname, a.status, a.timestamp, c.course_name, cl.class_name 
                FROM attendance a
                JOIN students s ON a.student_id = s.student_id
                JOIN class_sessions cs ON a.session_id = cs.session_id
                JOIN classes cl ON cs.class_id = cl.class_id
                JOIN courses c ON cl.course_code = c.course_code
                ORDER BY a.timestamp DESC LIMIT 5
            """)
            logs = cursor.fetchall()
            
            # Add code to display logs in the UI
            # ...

            conn.close()
        except Exception as e:
            print(f"Error loading recent activity: {e}")

    def check_system_status(self):
        """Check database and camera connections."""
        # Check database connection
        try:
            conn = sqlite3.connect("attendance.db")
            conn.cursor()
            conn.close()
            self.database_status.setText("🟢 Database: Connected")
        except sqlite3.Error as e:
            self.database_status.setText("🔴 Database: Disconnected")
            print(f"Database error: {e}")
                
        # Check camera connection
        try:
            camera = cv2.VideoCapture(0)
            if camera.isOpened():
                self.camera_status.setText("🟢 Camera: Connected")
            else:
                self.camera_status.setText("🔴 Camera: Disconnected")
            camera.release()
        except Exception as e:
            self.camera_status.setText("🔴 Camera: Error")
            print(f"Camera error: {e}")
            
    def toggle_theme(self):
        theme_manager = QApplication.instance().property("theme_manager")
        
        if theme_manager:
            print("🌓 Theme toggle requested")
            theme_manager.toggle_theme()
        else:
            print("⚠️ Theme manager not available - cannot toggle theme")
            QMessageBox.warning(self, "Theme Error", 
                        "The theme manager is not available. Please restart the application.")    
                
    def logout(self):
        reply = QMessageBox.question(
            self, 
            'Confirm Logout', 
            'Are you sure you want to logout?',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Log logout attempt
        self.log_activity('user_logout')
        
        def secure_logout():
            """Perform secure logout operations."""
            # Clear sensitive data from memory (if any)
            self.clear_sensitive_data()
            
            # Find the top-level AdminDashboard window
            parent_window = self
            while parent_window.parent() is not None:
                parent_window = parent_window.parent()
            
            # If the top-level window is an AdminDashboard, use its logout method
            if hasattr(parent_window, 'logout'):
                parent_window.logout()
            else:
                # Fallback if no suitable parent is found
                from admin.login_window import LoginWindow
                self.login_window = LoginWindow()
                self.login_window.show()
                self.close()
        
        # Use QTimer for delayed, secure logout
        QTimer.singleShot(100, secure_logout)


    def log_activity(self, activity_type):
        """Log user activities."""
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                INSERT INTO activity_log (activity_type, timestamp) 
                VALUES (?, ?)
            """, (activity_type, timestamp))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging activity: {e}")

    def clear_sensitive_data(self):
        """Clear any sensitive data from memory."""
        # Reset or clear any sensitive class attributes
        # Example implementations:
        self.search_bar.clear()  # Clear search bar
        
        # If you have any sensitive data like session tokens, reset them
        if hasattr(self, 'session_token'):
            self.session_token = None
        
        # You can add more specific clearing methods as needed
        print("Sensitive data cleared during logout")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    home = HomeWindow()
    home.show()
    sys.exit(app.exec_())
