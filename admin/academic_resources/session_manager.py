import sqlite3
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                           QTableWidgetItem, QPushButton, QLabel, QDialog, 
                           QMessageBox, QComboBox, QDateEdit, QGroupBox, QCheckBox)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtCore import QTimer
from config.utils_constants import DATABASE_PATH
from admin.academic_resources.class_session_dialog import ClassSessionDialog

class SessionManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sessionManagerWidget")
        self.setWindowTitle("Session Management")

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_session_statuses)
        self.status_timer.start(60000)  # Update every minute
        
        # Main layout
        layout = QVBoxLayout()
        
        # Title and description
        title_label = QLabel("Class Session Management", self)
        title_label.setObjectName("sessionManagerTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        description_label = QLabel("Manage class sessions and schedules", self)
        description_label.setObjectName("sessionManagerDescription")
        description_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(description_label)
        
        # Filter section
        filter_group = QGroupBox("Filter Options")
        filter_group.setObjectName("sessionFilterGroup")
        filter_layout = QHBoxLayout()
        
        # Date filter
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("Date:"))
        self.date_filter = QDateEdit()
        self.date_filter.setObjectName("sessionDateFilter")
        self.date_filter.setToolTip("Select a specific date to filter sessions")
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_filter)
        filter_layout.addLayout(date_layout)
        
        # Show only today checkbox
        self.today_only_checkbox = QCheckBox("Show only today's sessions")
        self.today_only_checkbox.setObjectName("sessionTodayCheckbox")
        self.today_only_checkbox.setToolTip("When checked, only displays sessions scheduled for today")
        self.today_only_checkbox.stateChanged.connect(self.update_date_filter_state)
        filter_layout.addWidget(self.today_only_checkbox)
        
        # Class filter
        class_layout = QVBoxLayout()
        class_layout.addWidget(QLabel("Class:"))
        self.class_filter = QComboBox()
        self.class_filter.setObjectName("sessionClassFilter")
        self.class_filter.setToolTip("Filter sessions by specific class")
        self.class_filter.addItem("All Classes", None)
        self.load_classes_for_filter()
        class_layout.addWidget(self.class_filter)
        filter_layout.addLayout(class_layout)
        
        # Status filter
        status_layout = QVBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.setObjectName("sessionStatusFilter")
        self.status_filter.setToolTip("Filter sessions by their current status")
        self.status_filter.addItems(["All Statuses", "scheduled", "in-progress", "completed", "cancelled"])
        status_layout.addWidget(self.status_filter)
        filter_layout.addLayout(status_layout)
        
        # Apply filter button
        self.apply_filter_button = QPushButton("Apply Filter")
        self.apply_filter_button.clicked.connect(self.load_sessions)
        self.apply_filter_button.setObjectName("sessionFilterButton")
        self.apply_filter_button.setToolTip("Apply the selected filters to the sessions table")
        filter_layout.addWidget(self.apply_filter_button)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # Container for table and no sessions label (to maintain consistent space)
        self.table_container = QWidget()
        self.table_layout = QVBoxLayout(self.table_container)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Table for displaying sessions
        self.sessions_table = QTableWidget()
        self.sessions_table.setObjectName("sessionsTable")
        self.sessions_table.setColumnCount(7)
        self.sessions_table.setToolTip("Table displaying all class sessions")
        
        # Set up table dimensions
        self.sessions_table.horizontalHeader().setDefaultSectionSize(120)  # Default column width
        self.sessions_table.verticalHeader().setDefaultSectionSize(60)     # Default row height
        
        # Specific column widths
        self.sessions_table.setColumnWidth(0, 60)     # ID column (narrower)
        self.sessions_table.setColumnWidth(1, 250)    # Class column (wider)
        self.sessions_table.setColumnWidth(2, 100)    # Date column
        self.sessions_table.setColumnWidth(3, 80)     # Start Time column
        self.sessions_table.setColumnWidth(4, 80)     # End Time column
        self.sessions_table.setColumnWidth(5, 100)    # Status column
        
        self.sessions_table.setHorizontalHeaderLabels(["ID", "Class", "Date", "Start Time", "End Time", "Status", "Actions"])
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.horizontalHeader().setStretchLastSection(True)
        self.table_layout.addWidget(self.sessions_table)
        
        # No sessions label - positioned within the same container as the table
        self.no_sessions_label = QLabel("No sessions found for the selected filters")
        self.no_sessions_label.setObjectName("noSessionsLabel")
        self.no_sessions_label.setAlignment(Qt.AlignCenter)
        self.no_sessions_label.setStyleSheet("font-size: 14px; color: #555; padding: 40px 0;")
        self.no_sessions_label.hide()  # Hidden by default
        self.table_layout.addWidget(self.no_sessions_label)
        
        layout.addWidget(self.table_container)
        
        # Buttons for managing sessions
        buttons_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add New Session")
        self.add_button.setObjectName("sessionAddButton")
        self.add_button.setToolTip("Create a new class session")
        self.add_button.clicked.connect(self.add_session)
        buttons_layout.addWidget(self.add_button)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("sessionRefreshButton")
        self.refresh_button.setToolTip("Refresh the sessions table with current data")
        self.refresh_button.clicked.connect(self.load_sessions)
        buttons_layout.addWidget(self.refresh_button)
        
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
        # Initial load of sessions - unchecked by default to show all sessions
        self.today_only_checkbox.setChecked(False)
        self.update_date_filter_state()
        
        # Initial load of all sessions
        self.load_sessions()
    
    def resizeEvent(self, event):
        """Handle resize events to keep no sessions label properly sized"""
        super().resizeEvent(event)
        # Ensure no_sessions_label fills the same space as the table
        if self.no_sessions_label.isVisible():
            self.no_sessions_label.setMinimumWidth(self.sessions_table.width())
            self.no_sessions_label.setMinimumHeight(300)  # Reasonable height for visibility
    
    def update_date_filter_state(self):
        """Update the date filter enabled state based on the 'today only' checkbox"""
        self.date_filter.setEnabled(not self.today_only_checkbox.isChecked())
    
    def load_classes_for_filter(self):
        """Load classes for the filter dropdown"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT c.class_id, c.class_name, co.course_name
                FROM classes c
                JOIN courses co ON c.course_code = co.course_code
                ORDER BY c.class_name
            """)
            
            classes = cursor.fetchall()
            conn.close()
            
            for class_data in classes:
                class_id, class_name, course_name = class_data
                self.class_filter.addItem(f"{class_name} ({course_name})", class_id)
                
        except Exception as e:
            print(f"❌ Error loading classes for filter: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not load classes: {e}")
    
    def load_sessions(self):
        """Load sessions based on filter criteria"""
        self.update_session_statuses()
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Base query
            query = """
                SELECT s.session_id, c.class_name, co.course_name, s.date, 
                       s.start_time, s.end_time, s.status, s.class_id
                FROM class_sessions s
                JOIN classes c ON s.class_id = c.class_id
                JOIN courses co ON c.course_code = co.course_code
                WHERE 1=1
            """
            params = []
            
            # Apply date filter
            if self.today_only_checkbox.isChecked():
                today = datetime.now().strftime('%Y-%m-%d')
                query += " AND s.date = ?"
                params.append(today)
            else:
                selected_date = self.date_filter.date().toString('yyyy-MM-dd')
                query += " AND s.date = ?"
                params.append(selected_date)
            
            # Apply class filter
            if self.class_filter.currentData():
                query += " AND s.class_id = ?"
                params.append(self.class_filter.currentData())
            
            # Apply status filter
            if self.status_filter.currentText() != "All Statuses":
                query += " AND s.status = ?"
                params.append(self.status_filter.currentText())
            
            # Order by date and start time
            query += " ORDER BY s.date, s.start_time"
            
            cursor.execute(query, params)
            sessions = cursor.fetchall()
            conn.close()
            
            # Display results in table
            self.display_sessions(sessions)
                
        except Exception as e:
            print(f"❌ Error loading sessions: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not load sessions: {e}")
    
    def display_sessions(self, sessions):
        """Display the sessions in the table"""
        self.sessions_table.setRowCount(0)
        
        # Check if there are no sessions to display
        if not sessions:
            # Create filter description text
            filter_text = ""
            if self.today_only_checkbox.isChecked():
                filter_text = "today"
            else:
                filter_text = f"on {self.date_filter.date().toString('yyyy-MM-dd')}"
                
            if self.class_filter.currentData():
                filter_text += f" for {self.class_filter.currentText()}"
                
            if self.status_filter.currentText() != "All Statuses":
                filter_text += f" with status '{self.status_filter.currentText()}'"
                
            self.no_sessions_label.setText(f"No sessions found {filter_text}")
            
            # Make sure the label takes up the same space as the table would
            self.no_sessions_label.setMinimumWidth(self.sessions_table.width())
            self.no_sessions_label.setMinimumHeight(300)  # Provide enough vertical space
            
            self.sessions_table.hide()
            self.no_sessions_label.show()
            return
        else:
            self.no_sessions_label.hide()
            self.sessions_table.show()
        
        for row_index, session in enumerate(sessions):
            session_id, class_name, course_name, date, start_time, end_time, status, class_id = session
            
            self.sessions_table.insertRow(row_index)
            
            # Set session data in the table
            id_item = QTableWidgetItem(str(session_id))
            id_item.setToolTip(f"Session ID: {session_id}")
            self.sessions_table.setItem(row_index, 0, id_item)
            
            class_item = QTableWidgetItem(f"{class_name} ({course_name})")
            class_item.setToolTip(f"Class: {class_name}\nCourse: {course_name}")
            self.sessions_table.setItem(row_index, 1, class_item)
            
            date_item = QTableWidgetItem(date)
            date_item.setToolTip(f"Session Date: {date}")
            self.sessions_table.setItem(row_index, 2, date_item)
            
            start_item = QTableWidgetItem(start_time)
            start_item.setToolTip(f"Start Time: {start_time}")
            self.sessions_table.setItem(row_index, 3, start_item)
            
            end_item = QTableWidgetItem(end_time)
            end_item.setToolTip(f"End Time: {end_time}")
            self.sessions_table.setItem(row_index, 4, end_item)
            
            status_item = QTableWidgetItem(status)
            status_item.setToolTip(f"Session Status: {status}")
            self.sessions_table.setItem(row_index, 5, status_item)
            
            # Add action buttons
            action_cell = QWidget()
            action_layout = QHBoxLayout(action_cell)
            action_layout.setContentsMargins(2, 2, 2, 2)
            
            edit_button = QPushButton("Edit")
            edit_button.setObjectName("sessionEditButton")
            edit_button.setToolTip(f"Edit session #{session_id}")
            edit_button.setProperty("session_id", session_id)
            edit_button.clicked.connect(lambda _, sid=session_id: self.edit_session(sid))
            action_layout.addWidget(edit_button)
            
            delete_button = QPushButton("Delete")
            delete_button.setObjectName("sessionDeleteButton")
            delete_button.setToolTip(f"Delete session #{session_id}")
            delete_button.setProperty("session_id", session_id)
            delete_button.clicked.connect(lambda _, sid=session_id: self.delete_session(sid))
            action_layout.addWidget(delete_button)
            
            action_cell.setLayout(action_layout)
            self.sessions_table.setCellWidget(row_index, 6, action_cell)

    def update_session_statuses(self):
        """Update statuses of sessions based on current date and time"""
        try:
            current_datetime = datetime.now()
            current_date = current_datetime.strftime('%Y-%m-%d')
            current_time = current_datetime.strftime('%H:%M:%S')

            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()

            # 1. Mark as 'missed' any session where end_time < now and status is 'scheduled'
            cursor.execute("""
                UPDATE class_sessions
                SET status = 'missed'
                WHERE (date < ? OR (date = ? AND end_time < ?))
                AND status = 'scheduled'
            """, (current_date, current_date, current_time))

            # 2. Mark as 'in-progress' any session where start_time <= now <= end_time and status is 'scheduled'
            cursor.execute("""
                UPDATE class_sessions
                SET status = 'in-progress'
                WHERE date = ?
                AND start_time <= ?
                AND end_time >= ?
                AND status = 'scheduled'
            """, (current_date, current_time, current_time))

            # 3. Mark as 'completed' any session where end_time < now and status is 'in-progress'
            cursor.execute("""
                UPDATE class_sessions
                SET status = 'completed'
                WHERE (date < ? OR (date = ? AND end_time < ?))
                AND status = 'in-progress'
            """, (current_date, current_date, current_time))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"❌ Error updating session statuses: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not update session statuses: {e}")
    
    def add_session(self):
        """Open dialog to add a new session"""
        class_id = self.class_filter.currentData() if self.class_filter.currentIndex() > 0 else None
        dialog = ClassSessionDialog(self, class_id=class_id)
        
        if dialog.exec_() == QDialog.Accepted:
            self.load_sessions()
    
    def edit_session(self, session_id):
        """Open dialog to edit an existing session"""
        dialog = ClassSessionDialog(self, session_id=session_id)
        
        if dialog.exec_() == QDialog.Accepted:
            self.load_sessions()
    
    def delete_session(self, session_id):
        """Delete a session after confirmation"""
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion",
            "Are you sure you want to delete this session?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM class_sessions WHERE session_id = ?", (session_id,))
                
                conn.commit()
                conn.close()
                
                QMessageBox.information(self, "Success", "Session deleted successfully")
                self.load_sessions()
                
            except Exception as e:
                print(f"❌ Error deleting session: {e}")
                QMessageBox.warning(self, "Database Error", f"Could not delete session: {e}")