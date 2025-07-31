from PyQt5.QtWidgets import (QVBoxLayout, QLabel, QPushButton, 
                            QComboBox, QDialog, QDateEdit, QTimeEdit,
                            QFormLayout, QGroupBox, QHBoxLayout, QTabWidget,
                            QListWidget, QListWidgetItem, QMessageBox)
from PyQt5.QtCore import Qt, QDate, QTime
import sqlite3
from datetime import datetime, timedelta

class ClassSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Class Session")
        self.setGeometry(300, 300, 500, 400)
        
        # Create tab widget for different selection methods
        self.tab_widget = QTabWidget()
        
        # Create the two main tabs
        self.create_scheduled_sessions_tab()
        self.create_manual_selection_tab()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.scheduled_sessions_widget, "Today's Sessions")
        self.tab_widget.addTab(self.manual_selection_widget, "Custom Selection")
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tab_widget)
        
        # Confirm button
        self.confirm_btn = QPushButton("Start Attendance")
        self.confirm_btn.clicked.connect(self.on_confirm_clicked)
        main_layout.addWidget(self.confirm_btn)
        
        self.setLayout(main_layout)
        
        # Initialize session data
        self.selected_session = None
        
        # Populate data on load
        self.populate_scheduled_sessions()
        self.populate_course_dropdown()
        
        # Connect signals
        self.session_list.itemClicked.connect(self.on_session_selected)
        
    def create_scheduled_sessions_tab(self):
        """Create the tab for selecting scheduled sessions."""
        self.scheduled_sessions_widget = QGroupBox()
        layout = QVBoxLayout()
        
        # Session date selection
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Date:"))
        self.date_selector = QDateEdit()
        self.date_selector.setDate(QDate.currentDate())
        self.date_selector.setCalendarPopup(True)
        date_layout.addWidget(self.date_selector)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.populate_scheduled_sessions)
        date_layout.addWidget(self.refresh_btn)
        layout.addLayout(date_layout)
        
        # Sessions list
        layout.addWidget(QLabel("Available Sessions:"))
        self.session_list = QListWidget()
        layout.addWidget(self.session_list)
        
        # Session details
        self.session_details = QLabel("Select a session to view details")
        layout.addWidget(self.session_details)
        
        self.scheduled_sessions_widget.setLayout(layout)
        
    def create_manual_selection_tab(self):
        """Create the tab for manual course/instructor/class selection."""
        self.manual_selection_widget = QGroupBox()
        layout = QFormLayout()
        
        # Course Selection
        self.course_combo = QComboBox()
        self.course_combo.currentIndexChanged.connect(self.update_instructor_combo)
        layout.addRow("Select Course:", self.course_combo)
        
        # Instructor Selection
        self.instructor_combo = QComboBox()
        self.instructor_combo.currentIndexChanged.connect(self.update_class_combo)
        layout.addRow("Select Instructor:", self.instructor_combo)
        
        # Class Selection
        self.class_combo = QComboBox()
        layout.addRow("Select Class:", self.class_combo)
        
        # Date and time
        self.manual_date = QDateEdit()
        self.manual_date.setDate(QDate.currentDate())
        self.manual_date.setCalendarPopup(True)
        layout.addRow("Date:", self.manual_date)
        
        # Start time
        self.manual_start_time = QTimeEdit()
        self.manual_start_time.setTime(QTime.currentTime())
        layout.addRow("Start Time:", self.manual_start_time)
        
        # End time (Added)
        self.manual_end_time = QTimeEdit()
        # Set default end time to current time + 1 hour
        current_time = QTime.currentTime()
        end_time = QTime(current_time.hour() + 1, current_time.minute())
        self.manual_end_time.setTime(end_time)
        layout.addRow("End Time:", self.manual_end_time)
        
        self.manual_selection_widget.setLayout(layout)
    
    def populate_scheduled_sessions(self):
        """Populate the sessions list with scheduled sessions for the selected date."""
        self.session_list.clear()
        
        selected_date = self.date_selector.date().toString("yyyy-MM-dd")
        
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Get all scheduled sessions for the selected date
        cursor.execute("""
            SELECT cs.session_id, c.course_name, cl.class_name, i.instructor_name, 
                   cs.start_time, cs.end_time, cs.status
            FROM class_sessions cs
            JOIN classes cl ON cs.class_id = cl.class_id
            JOIN courses c ON cl.course_code = c.course_code
            JOIN class_instructors ci ON cl.class_id = ci.class_id
            JOIN instructors i ON ci.instructor_id = i.instructor_id
            WHERE cs.date = ? AND cs.status IN ('scheduled', 'active')
            ORDER BY cs.start_time
        """, (selected_date,))
        
        sessions = cursor.fetchall()
        conn.close()
        
        if not sessions:
            # Add a placeholder item if no sessions found
            item = QListWidgetItem("No sessions scheduled for this date")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.session_list.addItem(item)
            return
            
        # Add sessions to list
        current_time = datetime.now().time()
        
        for session in sessions:
            session_id, course_name, class_name, instructor_name, start_time, end_time, status = session
            
            # Format display text
            display_text = f"{start_time} - {end_time} - {course_name}: {class_name}"
            
            # Create list item
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, session)  # Store full session data
            
            # Highlight active or upcoming sessions
            try:
                # Handle time format with or without seconds
                if len(start_time.split(':')) == 2:  # Format is HH:MM
                    session_time = datetime.strptime(start_time, "%H:%M").time()
                else:  # Format is HH:MM:SS
                    session_time = datetime.strptime(start_time, "%H:%M:%S").time()
                
                time_diff = datetime.combine(datetime.today(), session_time) - datetime.combine(datetime.today(), current_time)
                
                # Highlight based on timing
                if status == 'active':
                    item.setBackground(Qt.green)  # Active sessions in green
                elif time_diff.total_seconds() < 0:  # Session has started
                    item.setBackground(Qt.cyan)  # Past start time in cyan
                elif time_diff.total_seconds() > 0 and time_diff.total_seconds() < 3600:
                    item.setBackground(Qt.yellow)  # Starting within an hour in yellow
            except ValueError as e:
                # Handle time parsing errors gracefully
                print(f"Error parsing time: {e}")
                
            self.session_list.addItem(item)
    
    def on_session_selected(self, item):
        """Handle selection of a session from the list."""
        session_data = item.data(Qt.UserRole)
        if not session_data:
            return
            
        session_id, course_name, class_name, instructor_name, start_time, end_time, status = session_data
            
        # Update details display
        details = f"<b>{course_name}</b> - {class_name}<br>"
        details += f"Instructor: {instructor_name}<br>"
        details += f"Time: {start_time} - {end_time}<br>"
        details += f"Status: {status}"
        self.session_details.setText(details)
        
        # Store the selected session details
        self.selected_session = self.get_session_details(session_id)
    
    def populate_course_dropdown(self):
        """Populate course dropdown in manual selection tab."""
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Fetch courses
        cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_name")
        courses = cursor.fetchall()
        conn.close()
        
        self.course_combo.clear()
        self.course_combo.addItem("-- Select Course --", None)
        for course in courses:
            self.course_combo.addItem(course[1], course[0])  # Display name, store code as data
    
    def update_instructor_combo(self):
        """Update instructor combo based on selected course."""
        self.instructor_combo.clear()
        
        course_idx = self.course_combo.currentIndex()
        if course_idx <= 0:  # No selection or invalid selection
            return
            
        course_code = self.course_combo.currentData()
        
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Get instructors who teach this course
        cursor.execute("""
            SELECT DISTINCT i.instructor_id, i.instructor_name 
            FROM instructors i
            JOIN instructor_courses ic ON i.instructor_id = ic.instructor_id
            WHERE ic.course_code = ?
            ORDER BY i.instructor_name
        """, (course_code,))
        
        instructors = cursor.fetchall()
        conn.close()
        
        self.instructor_combo.addItem("-- Select Instructor --", None)
        for instructor in instructors:
            self.instructor_combo.addItem(instructor[1], instructor[0])
    
    def update_class_combo(self):
        """Update class combo box based on selected course and instructor."""
        self.class_combo.clear()
        
        course_idx = self.course_combo.currentIndex()
        instructor_idx = self.instructor_combo.currentIndex()
        
        if course_idx <= 0 or instructor_idx <= 0:  # No valid selection
            return
            
        course_code = self.course_combo.currentData()
        instructor_id = self.instructor_combo.currentData()
        
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Find classes that match the course and instructor
        cursor.execute("""
            SELECT c.class_id, c.class_name 
            FROM classes c
            JOIN class_instructors ci ON c.class_id = ci.class_id
            WHERE c.course_code = ? AND ci.instructor_id = ?
            ORDER BY c.class_name
        """, (course_code, instructor_id))
        
        classes = cursor.fetchall()
        conn.close()
        
        if not classes:
            self.class_combo.addItem("No classes found", None)
            return
            
        for class_data in classes:
            self.class_combo.addItem(class_data[1], class_data[0])
    
    def get_session_details(self, session_id):
        """Get complete details for a session by ID."""
        conn = sqlite3.connect("attendance.db")
        cursor = conn.cursor()
        
        # Get session details
        cursor.execute("""
            SELECT cs.class_id, cs.date, cs.start_time, cs.end_time, cl.class_name, 
                   c.course_code, c.course_name, i.instructor_id, i.instructor_name
            FROM class_sessions cs
            JOIN classes cl ON cs.class_id = cl.class_id
            JOIN courses c ON cl.course_code = c.course_code
            JOIN class_instructors ci ON cl.class_id = ci.class_id
            JOIN instructors i ON ci.instructor_id = i.instructor_id
            WHERE cs.session_id = ?
        """, (session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
            
        class_id, date, start_time, end_time, class_name, course_code, course_name, instructor_id, instructor_name = result
        
        # Create session details dictionary
        session_details = {
            'class_id': class_id,
            'date': date,
            'start_time': start_time,
            'end_time': end_time,
            'status': 'active',
            'course_code': course_code,
            'instructor_id': instructor_id,
            'course_name': course_name,
            'instructor_name': instructor_name,
            'class_name': class_name,
            'session_id': session_id  # Include the existing session ID
        }
        
        return session_details
    
    def get_selected_session(self):
        """Return the currently selected session details."""
        # If a session was selected from the list
        if self.tab_widget.currentIndex() == 0 and self.selected_session:
            return self.selected_session
            
        # If manual selection was used
        elif self.tab_widget.currentIndex() == 1:
            course_idx = self.course_combo.currentIndex()
            instructor_idx = self.instructor_combo.currentIndex()
            class_idx = self.class_combo.currentIndex()
            
            if course_idx <= 0 or instructor_idx <= 0 or class_idx <= 0:
                return None
                
            # Get selected values
            course_code = self.course_combo.currentData()
            course_name = self.course_combo.currentText()
            instructor_id = self.instructor_combo.currentData()
            instructor_name = self.instructor_combo.currentText()
            class_id = self.class_combo.currentData()
            class_name = self.class_combo.currentText()
            
            # Get date and time
            selected_date = self.manual_date.date().toString("yyyy-MM-dd")
            selected_start_time = self.manual_start_time.time().toString("HH:mm")
            selected_end_time = self.manual_end_time.time().toString("HH:mm")
            
            # Create session details
            session_details = {
                'class_id': class_id,
                'date': selected_date,
                'start_time': selected_start_time,
                'end_time': selected_end_time,  # Include end time
                'status': 'active',
                'course_code': course_code,
                'instructor_id': instructor_id,
                'course_name': course_name,
                'instructor_name': instructor_name,
                'class_name': class_name
            }
            
            return session_details
            
        return None
        
    def on_confirm_clicked(self):
        """Handle confirm button click with session time validation."""
        session = self.get_selected_session()
        
        if not session:
            QMessageBox.warning(self, "Selection Error", "Please select a valid session.")
            return
            
        # Check if session has started
        current_time = datetime.now().time()
        current_date = datetime.now().date()
        
        # Parse session date
        session_date = datetime.strptime(session['date'], "%Y-%m-%d").date()
        
        # Parse start time (handle both formats)
        try:
            if len(session['start_time'].split(':')) == 2:  # Format is HH:MM
                session_start_time = datetime.strptime(session['start_time'], "%H:%M").time()
            else:  # Format is HH:MM:SS
                session_start_time = datetime.strptime(session['start_time'], "%H:%M:%S").time()
        except ValueError:
            # Fallback to simpler parsing if standard formats fail
            parts = session['start_time'].split(':')
            if len(parts) >= 2:
                session_start_time = datetime.time(int(parts[0]), int(parts[1]))
            else:
                QMessageBox.warning(self, "Time Format Error", 
                                  f"Invalid start time format: {session['start_time']}")
                return
                
        # Compare dates and times
        if session_date > current_date:
            QMessageBox.warning(self, "Future Session", 
                              "Cannot start attendance for a future session.")
            return
            
        if session_date == current_date and session_start_time > current_time:
            QMessageBox.warning(self, "Future Session", 
                              "Cannot start attendance for a session that has not started yet.")
            return
            
        # All validations passed
        self.accept()