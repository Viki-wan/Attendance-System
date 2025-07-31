import sys
import cv2
import numpy as np
import face_recognition
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QApplication, QLabel, 
                            QPushButton, QTableWidget, QTableWidgetItem, 
                            QProgressBar, QMessageBox, QComboBox, QHBoxLayout,
                            QHeaderView, QDialog, QTextEdit, QFileDialog)
from PyQt5.QtCore import Qt, QTimer, QDate
 
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtGui import QColor, QTextDocument

from admin.face_recognition_service import FaceRecognitionService
from admin.db_service import DatabaseService
from admin.session_service import SessionService
from admin.view_attendance import ViewAttendanceWindow
from config.utils_constants import *

class StartAttendanceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📡 Start Attendance")
        self.setGeometry(300, 200, 800, 600)
        self.setObjectName("StartAttendanceWindow")
        self.setStyleSheet(QApplication.instance().styleSheet())

        # Initialize services
        self.db_service = DatabaseService()
        self.session_service = SessionService(self.db_service)
        self.settings = self.db_service.load_settings()
        self.face_service = FaceRecognitionService(self.settings, self.db_service)
        
        # Session tracking variables
        self.current_session = None
        self.session_id = None
        self.class_id = None
        self.attendance_running = False
        self.last_unknown_save_time = 0
        
        # Setup UI
        self.init_ui()
        
        # Load face data
        self.refresh_known_faces()
        
        # Track recognized students
        self.recognized_students = {}
        self.match_counter = {}
        self.unknown_counter = 0
        self.expected_students = []
        self.cap = None

    def init_ui(self):
        layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("🔄 System Ready...", self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14pt; font-weight: bold; margin: 10px 0;")
        layout.addWidget(self.status_label)
        
        # Session selection combo box
        session_header = QLabel("Select Today's Session:", self)
        session_header.setStyleSheet("font-size: 12pt; font-weight: bold;")
        layout.addWidget(session_header)
        
        self.session_combo = QComboBox(self)
        self.session_combo.setMinimumHeight(30)
        self.session_combo.currentIndexChanged.connect(self.session_selected)
        layout.addWidget(self.session_combo)
        
        # Session info display box
        self.session_info_label = QLabel("No active session", self)
        self.session_info_label.setAlignment(Qt.AlignCenter)
        self.session_info_label.setStyleSheet("font-size: 12pt; border: 1px solid #ccc; padding: 5px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.session_info_label)
        
        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v%")
        self.progress_bar.setStyleSheet("QProgressBar {border: 1px solid grey; border-radius: 2px; text-align: center;} QProgressBar::chunk {background-color: #3add36; width: 1px;}")
        layout.addWidget(self.progress_bar)
        
        # Attendance table
        table_header = QLabel("Expected Students:", self)
        table_header.setStyleSheet("font-size: 12pt; font-weight: bold; margin-top: 10px;")
        layout.addWidget(table_header)
        
        self.attendance_table = QTableWidget(self)
        self.attendance_table.setColumnCount(3)
        self.attendance_table.setHorizontalHeaderLabels(["Student ID", "Name", "Status"])
        self.attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.attendance_table.setStyleSheet("QTableWidget {border: 1px solid #ccc;}")
        layout.addWidget(self.attendance_table)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 Refresh Sessions")
        self.refresh_button.clicked.connect(self.load_today_sessions)
        self.refresh_button.setStyleSheet("QPushButton {background-color: #f0f0f0; padding: 8px;}")
        button_layout.addWidget(self.refresh_button)
        
        self.start_button = QPushButton("▶ Start Attendance")
        self.start_button.clicked.connect(self.start_attendance)
        self.start_button.setStyleSheet("QPushButton {background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;}")
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("⏹ Stop Attendance")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_attendance)
        self.stop_button.setStyleSheet("QPushButton {background-color: #f44336; color: white; font-weight: bold; padding: 8px;}")
        button_layout.addWidget(self.stop_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Timer for processing
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        
        # Load today's sessions
        self.load_today_sessions()
        
        # Check for auto-start setting
        self.check_auto_start()

    def load_today_sessions(self):
        """Load today's sessions into the combo box"""
        self.session_combo.clear()
        self.attendance_table.setRowCount(0)
        
        # Use the session service to get sessions
        sessions = self.session_service.get_today_sessions()
        if not sessions:
            self.session_combo.addItem("No sessions scheduled for today")
            self.start_button.setEnabled(False)
            return
            
        # Add a default selection prompt
        self.session_combo.addItem("-- Select a session --")
        
        # Get current and upcoming sessions
        current_sessions, upcoming_sessions = self.session_service.filter_sessions_by_time(sessions)
        
        # Combine current and upcoming sessions
        active_sessions = current_sessions + upcoming_sessions
        
        # Filter out completed sessions
        active_sessions = [s for s in active_sessions if s.get('status') != 'completed']
        
        # If no active sessions, show message
        if not active_sessions:
            self.session_combo.addItem("No active or upcoming sessions")
            self.start_button.setEnabled(False)
            return
        
        # Add filtered sessions to combo box with improved display format
        for session in active_sessions:
            session_id = session['session_id']
            class_id = session['class_id']
            course_code = session.get('course_code', 'Unknown')
            class_name = session.get('class_name', 'Unknown Class')
            start_time = session['start_time']
            end_time = session['end_time'] if session['end_time'] else "End"
            
            # Format display text as: class_id, course name, time
            display_text = f"{class_id} - {course_code}: {class_name} | {start_time}"
            
            # Add indicator if session is in progress
            if session in current_sessions:
                display_text += " [IN PROGRESS]"
            
            self.session_combo.addItem(display_text, session)
        
        # If there's exactly one current session, select it automatically
        if len(current_sessions) == 1:
            for i in range(self.session_combo.count()):
                if i > 0:  # Skip the "Select a session" item
                    session_data = self.session_combo.itemData(i)
                    if session_data and session_data['session_id'] == current_sessions[0]['session_id']:
                        self.session_combo.setCurrentIndex(i)
                        break
        
        # Enable start button if there are active sessions
        self.start_button.setEnabled(self.session_combo.count() > 1)
        
    def check_auto_start(self):
        """Check if attendance should auto-start based on settings"""
        if self.settings.get("auto_start", "0") == "1":
            # Try to find an active session first (by database status)
            active_session = self.session_service.get_current_active_session()
            
            if active_session:
                # Find and select this session in the combo box
                for i in range(self.session_combo.count()):
                    if i > 0:  # Skip the "Select a session" item
                        session_data = self.session_combo.itemData(i)
                        if session_data and session_data['session_id'] == active_session['session_id']:
                            self.session_combo.setCurrentIndex(i)
                            # Only auto-start if the session is eligible
                            if self.is_session_eligible_for_attendance():
                                QTimer.singleShot(1000, self.start_attendance)
                            break
            else:
                # If no active session by status, check by time
                sessions = self.session_service.get_today_sessions()
                current_sessions, upcoming_sessions = self.session_service.filter_sessions_by_time(sessions)
                
                # Auto-start if there's exactly one current session
                if len(current_sessions) == 1:
                    # Find and select this session in the combo box
                    for i in range(self.session_combo.count()):
                        if i > 0:  # Skip the "Select a session" item
                            session_data = self.session_combo.itemData(i)
                            if session_data and session_data['session_id'] == current_sessions[0]['session_id']:
                                self.session_combo.setCurrentIndex(i)
                                QTimer.singleShot(1000, self.start_attendance)
                                break
                # If no current sessions, check upcoming ones
                elif not current_sessions and len(upcoming_sessions) == 1:
                    # Find and select this session in the combo box
                    for i in range(self.session_combo.count()):
                        if i > 0:  # Skip the "Select a session" item
                            session_data = self.session_combo.itemData(i)
                            if session_data and session_data['session_id'] == upcoming_sessions[0]['session_id']:
                                self.session_combo.setCurrentIndex(i)
                                QTimer.singleShot(1000, self.start_attendance)
                                break

    def session_selected(self):
        """Handle session selection from combo box"""
        self.update_session_display()
        
        # Load expected students for this session if valid
        if self.class_id:
            self.load_expected_students()
    
    def update_session_display(self):
        """Updates the session information display"""
        index = self.session_combo.currentIndex()
        if index <= 0:  # No valid selection
            self.session_info_label.setText("No active session")
            self.class_id = None
            self.session_id = None
            self.current_session = None
            return
            
        # Get selected session data
        session_data = self.session_combo.itemData(index)
        if not session_data:
            return
            
        # Format display text using available keys
        course_code = session_data.get('course_code', 'Unknown')
        class_name = session_data.get('class_name', 'Unknown Class')
        
        session_info = (f"Session: {course_code} - {class_name}\n"
                    f"Date: {session_data['date']} | Time: {session_data['start_time']} - {session_data['end_time'] or 'End'}")
        
        # Add instructor if available 
        if 'instructor_name' in session_data and session_data['instructor_name']:
            session_info += f"\nInstructor: {session_data['instructor_name']}"
            
        self.session_info_label.setText(session_info)
        
        # Store current session data
        self.current_session = session_data
        self.session_id = session_data['session_id']
        self.class_id = session_data['class_id']
        
    def load_expected_students(self):
        """Load the list of students expected in this class"""
        if not self.class_id or not self.session_id:
            return
            
        # Clear existing table
        self.attendance_table.setRowCount(0)
        
        # Get students for this session using the improved method
        self.expected_students = self.db_service.get_session_students(self.session_id)
        
        # If no students found, try the fallback approach
        if not self.expected_students:
            conn = self.db_service.get_connection()
            cursor = conn.cursor()
            
            # Get class details
            cursor.execute("""
                SELECT course_code, year, semester 
                FROM classes 
                WHERE class_id = ?
            """, (self.class_id,))
            
            class_details = cursor.fetchone()
            conn.close()
            
            if class_details:
                course_code, year, semester = class_details
                
                # Use your existing query approach as fallback
                conn = self.db_service.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT s.student_id, s.fname, s.lname
                    FROM students s
                    JOIN student_courses sc ON s.student_id = sc.student_id
                    WHERE sc.course_code = ?
                    AND s.year_of_study = ?
                    AND s.current_semester = ?
                    ORDER BY s.lname, s.fname
                """, (course_code, year, semester))
                
                expected_students_data = cursor.fetchall()
                cursor.close()
                conn.close()
                
                # Convert to expected format - combining fname and lname
                self.expected_students = [
                    {'student_id': student[0], 'name': f"{student[1]} {student[2]}"} 
                    for student in expected_students_data
                ]
        
        # Get any students already marked present from the attendance table
        if self.session_id:
            # Use the new get_session_attendance method
            attendance_records = self.db_service.get_session_attendance(self.session_id)
            present_ids = [record['student_id'] for record in attendance_records if record['status'] == 'Present']
        else:
            present_ids = []
        
        # Populate table with expected students
        for student in self.expected_students:
            row = self.attendance_table.rowCount()
            self.attendance_table.insertRow(row)
            
            # Add student details
            self.attendance_table.setItem(row, 0, QTableWidgetItem(student['student_id']))
            self.attendance_table.setItem(row, 1, QTableWidgetItem(student['name']))
            
            # Set status based on whether they're already marked present
            status = "Present" if student['student_id'] in present_ids else "Absent"
            status_item = QTableWidgetItem(status)
            
            # Color code the status
            if status == "Present":
                status_item.setBackground(QColor(200, 255, 200))  # Light green
            else:
                status_item.setBackground(QColor(255, 200, 200))  # Light red
                
            self.attendance_table.setItem(row, 2, status_item)

    def refresh_known_faces(self):
        """Reload known faces from the face recognition service"""
        self.known_faces, self.student_ids = self.face_service.load_known_faces()
        
        # Store the original IDs with underscores (for file operations)
        self.student_ids_original = self.student_ids.copy()
        
        # Normalize student IDs to match database format (replacing underscores with slashes)
        self.student_ids = [sid.replace('_', '/') for sid in self.student_ids]
        
        print(f"✅ Loaded {len(self.known_faces)} known faces")

    def start_attendance(self):
        """Start the attendance process"""
        # Get selected session
        index = self.session_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "No Session Selected", 
                            "Please select a class session before starting attendance")
            return
            
        # Update session info
        self.update_session_display()
        
        # Validate session
        if not self.session_id or not self.class_id:
            QMessageBox.warning(self, "Session Error", "Invalid session selected")
            return
        
        # Check if session is eligible for attendance (in progress or starting within 5 minutes)
        if not self.is_session_eligible_for_attendance():
            QMessageBox.warning(self, "Session Timing Error", 
                        "Attendance can only be started for sessions that are currently in progress or starting within 5 minutes")
            return
            
        # Make sure we have expected students loaded
        self.load_expected_students()     
        # Get student IDs for this class only
        self.class_student_ids = [s['student_id'] for s in self.expected_students]
        print("Class student IDs:")
        for sid in self.class_student_ids:
            print(f"  - {sid}")
        
        print("Face recognition student IDs:")
        for sid in self.student_ids:
            print(f"  - {sid}")

        
        # Check which students have registered faces (using database format with slashes)
        registered_face_students = set(self.student_ids)  # These are already normalized in refresh_known_faces
        class_students_with_faces = set(self.class_student_ids).intersection(registered_face_students)
        
        print(f"Total students in class: {len(self.class_student_ids)}")
        print(f"Total students with registered faces: {len(registered_face_students)}")
        print(f"Students in this class with registered faces: {len(class_students_with_faces)}")

        if not class_students_with_faces:
            # No students in this class have registered faces
            QMessageBox.warning(self, "No Registered Faces", 
                            "No students in this class have registered face data.\nAsk students to register their faces first.")
            return
            
        # Filter known faces to only include students in this class
        self.class_known_faces = []
        self.class_student_ids_for_recognition = []
        
        for face, student_id in zip(self.known_faces, self.student_ids):
            if student_id in self.class_student_ids:
                self.class_known_faces.append(face)
                self.class_student_ids_for_recognition.append(student_id)
        
        if not self.class_known_faces:
            QMessageBox.warning(self, "No Registered Faces", "No students in this class have registered face data")
            return
        
        # Show loading status
        self.status_label.setText("🔄 Initializing camera...")
        self.progress_bar.setValue(10)
        QApplication.processEvents()  # Force UI update
        
        # Initialize camera with loading feedback
        self.status_label.setText("🔄 Opening camera...")
        self.progress_bar.setValue(30)
        QApplication.processEvents()
        
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Camera Error", "Could not open webcam")
            self.status_label.setText("❌ Camera error")
            self.progress_bar.setValue(0)
            return
        
        # Update UI to show loading progress
        self.status_label.setText("🔄 Preparing face recognition...")
        self.progress_bar.setValue(70)
        QApplication.processEvents()
        
        # Update UI state
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.session_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        
        # Update final status
        self.status_label.setText("✅ Attendance system active")
        self.progress_bar.setValue(100)
        QApplication.processEvents()
        
        # Initialize tracking variables
        self.match_counter = {}  # Track repeated matches for known faces
        self.unknown_counter = 0  # Track repeated unknown face appearances
        self.attendance_running = True
        
        # Start the recognition loop
        self.run_face_recognition()

    def is_session_eligible_for_attendance(self):
        """Check if the selected session is eligible for attendance tracking"""
        if not self.current_session:
            return False
            
        current_time = datetime.now().time().strftime("%H:%M:%S")
        start_time = self.current_session['start_time']
        end_time = self.current_session['end_time']
        
        # Session is already in progress
        if start_time <= current_time and (not end_time or end_time == "End" or current_time <= end_time):
            return True
            
        # Session is starting within next 5 minutes
        five_min_future = (datetime.now() + timedelta(minutes=5)).time().strftime("%H:%M:%S")
        if start_time > current_time and start_time <= five_min_future:
            return True
            
        return False

    def run_face_recognition(self):
        """Run the face recognition process in a loop"""
        required_matches = int(self.settings.get("required_matches", "3"))
        
        while self.attendance_running:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Check light conditions
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            avg_brightness = gray.mean()

            if avg_brightness < 20:  # Too dark
                cv2.putText(frame, "Low light detected", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow("Attendance System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # Detect faces
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")

            if not face_locations:
                cv2.putText(frame, "No face detected", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                self.unknown_counter = 0  # Reset counter
                cv2.imshow("Attendance System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # Get face encodings
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            # Process each detected face
            for face_encoding, face_location in zip(face_encodings, face_locations):
                # Compare with class-specific known faces
                student_id, name, is_known = self.face_service.recognize_face(
                    face_encoding, 
                    self.class_known_faces,
                    self.class_student_ids_for_recognition,
                    float(self.settings.get("face_recognition_sensitivity", "50")) / 100
                )
                
                if is_known:
                    # Original ID format from face recognition (with underscores)
                    original_student_id = student_id
                    
                    # Convert to database format (with slashes) for database operations
                    normalized_student_id = original_student_id.replace('_', '/')
                    
                    # Count repeated recognitions using database format
                    self.match_counter[normalized_student_id] = self.match_counter.get(normalized_student_id, 0) + 1
                    
                    # Mark attendance after required matches
                    if self.match_counter[normalized_student_id] == required_matches:
                        if self.db_service.mark_attendance(normalized_student_id, self.session_id):
                            self.update_student_status(normalized_student_id, "Present")
                else:
                    # Handle unknown face - this is someone not enrolled in this class
                    self.unknown_counter += 1
                    
                    # Save unknown face if enabled and seen multiple times
                    if (self.settings.get("save_unknown_faces", "1") == "1" and 
                        self.unknown_counter >= required_matches):
                        current_time = datetime.now().timestamp()
                        # Only save once every 10 seconds to avoid too many files
                        if current_time - self.last_unknown_save_time > 10:
                            self.face_service.save_unknown_face(
                                frame, 
                                face_location,
                                self.settings
                            )
                            self.last_unknown_save_time = current_time
                        self.unknown_counter = 0  # Reset counter

                # Draw face box
                top, right, bottom, left = face_location
                color = (0, 255, 0) if is_known else (0, 0, 255)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # Display name
                label = f"{name} ({student_id})" if is_known else "Unknown Person"
                cv2.putText(frame, label, (left, top - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Display the frame
            cv2.imshow("Attendance System", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            # Process UI events
            QApplication.processEvents()

        # Cleanup
        if self.cap and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()



    def stop_attendance(self):
        """Stop the attendance process"""
        self.attendance_running = False
        
        # Reset UI
        self.status_label.setText("✅ Attendance Stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.session_combo.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.timer.stop()
        
        # Release resources
        if self.cap and self.cap.isOpened():
            self.cap.release()
        cv2.destroyAllWindows()
        
        # Update session end time
        if self.session_id:
            self.db_service.update_session_end_time(self.session_id)
            
        # Show summary
        self.show_attendance_summary()
        
    def show_attendance_summary(self):
        """Show a detailed summary of the attendance session with option to view full report"""
        if not self.session_id:
            return
        
        # Get attendance records for this session using the new method
        attendance_records = self.db_service.get_session_attendance(self.session_id)
        present_students = [record['student_id'] for record in attendance_records if record['status'] == 'Present']
        
        # Get total expected students
        total_students = len(self.expected_students)
        present_count = len(present_students)
        absent_count = total_students - present_count
        
        # Create list of present and absent students
        present_students_names = [student['name'] for student in self.expected_students 
                        if student['student_id'] in present_students]
        absent_students = [student['name'] for student in self.expected_students 
                        if student['student_id'] not in present_students]
                        
        dialog = QDialog(self)
        dialog.setWindowTitle("Attendance Summary")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Create summary text
        summary = f"<h2>Attendance Session Summary</h2>"
        summary += f"<p><b>Course:</b> {self.current_session['course_code']}<br>"
        summary += f"<b>Class:</b> {self.current_session['class_name']}<br>"
        summary += f"<b>Date:</b> {self.current_session['date']}<br>"
        summary += f"<b>Time:</b> {self.current_session['start_time']} - {datetime.now().strftime('%H:%M:%S')}</p>"
        
        # Add attendance statistics
        attendance_percentage = int(present_count/total_students*100) if total_students > 0 else 0
        summary += f"<h3>Statistics</h3>"
        summary += f"<p><b>Students Present:</b> {present_count} / {total_students} ({attendance_percentage}%)<br>"
        summary += f"<b>Students Absent:</b> {absent_count}</p>"
        
        # Add present students list
        summary += f"<h3>Present Students ({present_count})</h3>"
        if present_students_names:
            summary += "<ul>"
            for student in present_students_names:
                summary += f"<li>{student}</li>"
            summary += "</ul>"
        else:
            summary += "<p>No students present.</p>"
        
        # Add absent students list
        summary += f"<h3>Absent Students ({absent_count})</h3>"
        if absent_students:
            summary += "<ul>"
            for student in absent_students:
                summary += f"<li>{student}</li>"
            summary += "</ul>"
        else:
            summary += "<p>No students absent.</p>"
        
        # Display the summary
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(summary)
        layout.addWidget(text_edit)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        
        view_report_button = QPushButton("View Full Report")
        view_report_button.clicked.connect(lambda: self.open_attendance_report(
            self.current_session['date'], 
            self.current_session['course_code'])
        )
        
        export_button = QPushButton("Export PDF")
        export_button.clicked.connect(lambda: self.export_session_report_to_pdf(summary))
        
        button_layout.addWidget(export_button)
        button_layout.addWidget(view_report_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        dialog.exec_()

    def open_attendance_report(self, date, course_code):
        """Open the attendance report window with pre-filtered data"""
                
        # Create and show the report window
        self.report_window = ViewAttendanceWindow()
        
        # Pre-filter the report for this session
        self.report_window.date_from.setDate(QDate.fromString(date, "yyyy-MM-dd"))
        self.report_window.date_to.setDate(QDate.fromString(date, "yyyy-MM-dd"))
        
        # Find and select the course in the dropdown
        index = self.report_window.course_filter.findText(course_code)
        if index >= 0:
            self.report_window.course_filter.setCurrentIndex(index)
        
        # If we have a class ID, select it as well
        if self.class_id:
            for i in range(self.report_window.class_filter.count()):
                class_data = self.report_window.class_filter.itemText(i)
                if class_data.startswith(str(self.class_id)):
                    self.report_window.class_filter.setCurrentIndex(i)
                    break
        
        # Trigger the filter application
        self.report_window.apply_filters()
        
        # Show the window
        self.report_window.show()

    def export_session_report_to_pdf(self, html_content):
        """Export the session report to PDF"""
                
        # Create a printer and set to PDF
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        
        # Get file name from user
        file_name, _ = QFileDialog.getSaveFileName(self, "Export PDF", 
                                                f"Attendance_{self.current_session['date']}_{self.current_session['class_name']}.pdf", 
                                                "PDF Files (*.pdf)")
        
        if file_name:
            # Set the output file name
            printer.setOutputFileName(file_name)
            
            # Create a document and add the HTML content
            document = QTextDocument()
            document.setHtml(html_content)
            
            # Print the document to the PDF file
            document.print_(printer)      
            QMessageBox.information(self, "Export Complete", f"Report exported to {file_name}")


    def update_student_status(self, student_id, status):
        """Update a student's status in the attendance table"""
        for row in range(self.attendance_table.rowCount()):
            if self.attendance_table.item(row, 0).text() == student_id:
                status_item = QTableWidgetItem(status)
                
                # Color code the status
                if status == "Present":
                    status_item.setBackground(QColor(200, 255, 200))  # Light green
                else:
                    status_item.setBackground(QColor(255, 200, 200))  # Light red
                    
                self.attendance_table.setItem(row, 2, status_item)
                return True
                
        return False

    def update_progress(self):
        """Updates progress bar during attendance"""
        current_value = self.progress_bar.value()
        if current_value < 100:
            self.progress_bar.setValue(current_value + 5)