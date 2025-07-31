import sqlite3
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
from PyQt5.QtCore import Qt
from datetime import datetime

class SessionSelector(QDialog):
    def __init__(self, session_service=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Class Session")
        self.setGeometry(300, 300, 400, 200)
        
        self.selected_session = None
        
        # Use provided session_service or create a new connection directly
        self.session_service = session_service
        self.conn = sqlite3.connect("attendance.db")
        
        self.init_ui()
        self.load_sessions()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Instructions
        self.info_label = QLabel("Select a session for today:", self)
        layout.addWidget(self.info_label)
        
        # Course selection
        self.course_label = QLabel("Course:", self)
        layout.addWidget(self.course_label)
        
        self.course_combo = QComboBox(self)
        self.course_combo.currentIndexChanged.connect(self.on_course_selected)
        layout.addWidget(self.course_combo)
        
        # Class selection
        self.class_label = QLabel("Class:", self)
        layout.addWidget(self.class_label)
        
        self.class_combo = QComboBox(self)
        self.class_combo.currentIndexChanged.connect(self.on_class_selected)
        layout.addWidget(self.class_combo)
        
        # Session selection
        self.session_label = QLabel("Session Time:", self)
        layout.addWidget(self.session_label)
        
        self.session_combo = QComboBox(self)
        layout.addWidget(self.session_combo)
        
        # Filter options
        self.filter_label = QLabel("Filter By:", self)
        layout.addWidget(self.filter_label)
        
        self.semester_combo = QComboBox(self)
        self.semester_combo.addItem("All Semesters")
        # Load semesters from database
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT semester FROM student_courses ORDER BY semester")
        for semester in cursor.fetchall():
            if semester[0]:  # Only add if not NULL
                self.semester_combo.addItem(semester[0])
        layout.addWidget(self.semester_combo)
        
        # Buttons
        self.select_button = QPushButton("Select", self)
        self.select_button.clicked.connect(self.accept)
        layout.addWidget(self.select_button)
        
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
        
        self.setLayout(layout)
    
    def load_sessions(self):
        """Load today's sessions from database"""
        try:
            cursor = self.conn.cursor()
            
            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Get available courses for today
            cursor.execute("""
                SELECT DISTINCT c.course_code, c.course_name 
                FROM class_sessions cs
                JOIN classes cl ON cs.class_id = cl.class_id
                JOIN courses c ON cl.course_code = c.course_code
                WHERE cs.date = ? AND cs.status = 'scheduled'
            """, (today,))
            
            courses = cursor.fetchall()
            
            if not courses:
                self.info_label.setText("No sessions scheduled for today")
                self.select_button.setEnabled(False)
                return
                
            # Populate course combo box
            self.course_combo.addItem("-- Select Course --")
            for course_code, course_name in courses:
                self.course_combo.addItem(f"{course_code}: {course_name}", course_code)
            
        except Exception as e:
            print(f"Error loading sessions: {e}")
    
    def on_course_selected(self):
        """Handle course selection"""
        self.class_combo.clear()
        self.session_combo.clear()
        
        index = self.course_combo.currentIndex()
        if index <= 0:
            return
            
        course_code = self.course_combo.itemData(index)
        
        try:
            cursor = self.conn.cursor()
            
            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Get classes for selected course today
            # Add filter for year and semester if applicable
            semester = self.semester_combo.currentText()
            semester_filter = "" if semester == "All Semesters" else f"AND cl.semester = '{semester}'"
            
            cursor.execute(f"""
                SELECT DISTINCT cl.class_id, cl.class_name 
                FROM class_sessions cs
                JOIN classes cl ON cs.class_id = cl.class_id
                WHERE cl.course_code = ? AND cs.date = ? AND cs.status = 'scheduled'
                {semester_filter}
            """, (course_code, today))
            
            classes = cursor.fetchall()
            
            # Populate class combo box
            self.class_combo.addItem("-- Select Class --")
            for class_id, class_name in classes:
                self.class_combo.addItem(class_name, class_id)
            
        except Exception as e:
            print(f"Error loading classes: {e}")
    
    def on_class_selected(self):
        """Handle class selection"""
        self.session_combo.clear()
        
        index = self.class_combo.currentIndex()
        if index <= 0:
            return
            
        class_id = self.class_combo.itemData(index)
        
        try:
            cursor = self.conn.cursor()
            
            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Get sessions for selected class today
            cursor.execute("""
                SELECT session_id, start_time, end_time, status
                FROM class_sessions
                WHERE class_id = ? AND date = ? AND status = 'scheduled'
                ORDER BY start_time
            """, (class_id, today))
            
            sessions = cursor.fetchall()
            
            # Populate session combo box
            current_time = datetime.now().time()
            current_time_str = current_time.strftime("%H:%M:%S")
            
            for session_id, start_time, end_time, status in sessions:
                display_text = f"{start_time} - {end_time if end_time else 'End'}"
                
                # Highlight current session
                if start_time <= current_time_str and (not end_time or current_time_str <= end_time):
                    display_text += " (Current)"
                    
                self.session_combo.addItem(display_text, session_id)
            
        except Exception as e:
            print(f"Error loading sessions: {e}")
    
    def get_selected_session(self):
        """Get the full details of the selected session"""
        if not self.session_combo.currentData():
            return None
            
        session_id = self.session_combo.currentData()
        
        try:
            cursor = self.conn.cursor()
            
            # Get complete session details
            cursor.execute("""
                SELECT cs.session_id, cs.class_id, cs.date, cs.start_time, cs.end_time,
                       c.class_name, co.course_name, i.instructor_name, cl.year, cl.semester
                FROM class_sessions cs
                JOIN classes c ON cs.class_id = c.class_id
                JOIN courses co ON c.course_code = co.course_code
                LEFT JOIN class_instructors ci ON c.class_id = ci.class_id
                LEFT JOIN instructors i ON ci.instructor_id = i.instructor_id
                JOIN classes cl ON cs.class_id = cl.class_id
                WHERE cs.session_id = ?
            """, (session_id,))
            
            session_data = cursor.fetchone()
            
            if not session_data:
                return None
                
            # Format as dictionary
            return {
                'session_id': session_data[0],
                'class_id': session_data[1],
                'date': session_data[2],
                'start_time': session_data[3],
                'end_time': session_data[4],
                'class_name': session_data[5],
                'course_name': session_data[6],
                'instructor_name': session_data[7],
                'year': session_data[8],
                'semester': session_data[9]
            }
            
        except Exception as e:
            print(f"Error getting session details: {e}")
            return None
    
    def __del__(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()