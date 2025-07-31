import sqlite3
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                           QLineEdit, QPushButton, QLabel, QMessageBox, 
                           QListWidget, QApplication, QListWidgetItem, QComboBox, QGroupBox,
                           QScrollArea, QWidget, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QIcon, QFont
from config.utils_constants import DATABASE_PATH
import re

class InstructorDialog(QDialog):
    def __init__(self, parent=None, instructor_id=None):
        super().__init__(parent)
        
        # Get the global stylesheet
        self.setStyleSheet(QApplication.instance().styleSheet())

        self.instructor_id = instructor_id
        self.is_edit_mode = instructor_id is not None
        
        if self.is_edit_mode:
            self.setWindowTitle("Edit Instructor")
        else:
            self.setWindowTitle("Add New Instructor")
        
        # Allow resizing for better responsiveness
        self.setMinimumSize(650, 500)
        self.setGeometry(300, 200, 700, 550)
        self.setup_ui()
        
        if self.is_edit_mode:
            self.load_instructor_data()
        
        self.name_edit.installEventFilter(self)
    
    def setup_ui(self):
        """Set up the dialog UI elements"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Create a scroll area for the entire content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)
        
        # Instructor details form with improved styling
        details_group = QGroupBox("Instructor Details")
        details_group.setFont(QFont("", 10, QFont.Bold))
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(20, 25, 20, 20)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Create styled form fields
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter instructor name")
        form_layout.addRow("Name:", self.name_edit)
        
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Enter email address")
        form_layout.addRow("Email:", self.email_edit)
        
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Enter phone number")
        form_layout.addRow("Phone:", self.phone_edit)

        # Consistent styling for all input elements
        input_style = """
            QLineEdit, QComboBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px;
                background-color: #fcfcfc;
                min-height: 18px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #4a86e8;
                background-color: #f0f7ff;
            }
            QComboBox::drop-down {
                border: 0px;
                padding-right: 10px;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 15px;
                background-color: #f9f9f9;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #444;
            }
        """
        details_group.setStyleSheet(input_style)
        details_group.setLayout(form_layout)
        scroll_layout.addWidget(details_group)
        
        # Course assignment section with improved layout
        courses_group = QGroupBox("Assigned Courses")
        courses_group.setFont(QFont("", 10, QFont.Bold))
        courses_layout = QVBoxLayout()
        courses_layout.setSpacing(15)
        courses_layout.setContentsMargins(20, 25, 20, 20)
        
        # Available courses section with search filter
        course_select_layout = QHBoxLayout()
        course_select_layout.setSpacing(10)
        
        course_label = QLabel("Available Courses:")
        course_label.setFixedWidth(120)
        course_select_layout.addWidget(course_label)
        
        self.course_combo = QComboBox()
        self.course_combo.setMinimumWidth(250)
        self.load_available_courses()
        course_select_layout.addWidget(self.course_combo)
        
        self.add_course_button = QPushButton("Add Course")
        self.add_course_button.setIcon(QIcon("icons/add.png")) # Add an icon if available
        self.add_course_button.setStyleSheet("""
            QPushButton {
                background-color: #e7f3ff;
                border: 1px solid #4a86e8;
                border-radius: 4px;
                padding: 8px 15px;
                color: #2d6fd2;
            }
            QPushButton:hover {
                background-color: #d0e7ff;
            }
            QPushButton:pressed {
                background-color: #b8d8ff;
            }
        """)
        course_select_layout.addWidget(self.add_course_button)
        self.add_course_button.clicked.connect(self.add_course_to_instructor)
        
        courses_layout.addLayout(course_select_layout)
        
        # Assigned courses list with better visual feedback
        assigned_label = QLabel("Assigned Courses:")
        assigned_label.setFont(QFont("", 9, QFont.Bold))
        courses_layout.addWidget(assigned_label)
        
        self.assigned_courses_list = QListWidget()
        self.assigned_courses_list.setMinimumHeight(150)
        self.assigned_courses_list.setAlternatingRowColors(True)
        self.assigned_courses_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                padding: 5px;
            }
            QListWidget::item {
                border-bottom: 1px solid #eee;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #e7f3ff;
                color: #2d6fd2;
            }
            QListWidget::item:alternate {
                background-color: #f9f9f9;
            }
        """)
        courses_layout.addWidget(self.assigned_courses_list)
        
        self.remove_course_button = QPushButton("Remove Selected Course")
        self.remove_course_button.setIcon(QIcon("icons/remove.png")) # Add an icon if available
        self.remove_course_button.setStyleSheet("""
            QPushButton {
                background-color: #fee7e7;
                border: 1px solid #e74c3c;
                border-radius: 4px;
                padding: 8px 15px;
                color: #c0392b;
            }
            QPushButton:hover {
                background-color: #fdd6d6;
            }
            QPushButton:pressed {
                background-color: #fcc5c5;
            }
        """)
        self.remove_course_button.clicked.connect(self.remove_course_from_instructor)
        courses_layout.addWidget(self.remove_course_button)
        
        courses_group.setLayout(courses_layout)
        scroll_layout.addWidget(courses_group)
        
        # Set the scroll content and add to main layout
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # Bottom buttons with improved styling
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.setContentsMargins(0, 10, 0, 0)
        
        # Add a spacer to push buttons to the right
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.save_button = QPushButton("Save")
        self.save_button.setMinimumWidth(100)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4a86e8;
                border: 1px solid #2d6fd2;
                border-radius: 4px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3b77d9;
            }
            QPushButton:pressed {
                background-color: #2d6fd2;
            }
        """)
        self.save_button.clicked.connect(self.save_instructor)
        button_layout.addWidget(self.save_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def eventFilter(self, obj, event):
        if obj == self.name_edit and event.type() == QEvent.KeyPress:
            key = event.text()
            # Allow only letters, spaces, hyphens, apostrophes, and navigation keys
            allowed_keys = (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Left, Qt.Key_Right, Qt.Key_Tab, Qt.Key_Home, Qt.Key_End)
            if key and not re.match(r"[A-Za-z\s\-']", key) and event.key() not in allowed_keys:
                return True  # Ignore the event
        return super().eventFilter(obj, event)
    
    # Keep all other methods unchanged
    def load_available_courses(self):
        """Load available courses for the combo box"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_name")
            courses = cursor.fetchall()
            
            conn.close()
            
            self.course_combo.clear()
            # Add a helpful prompt as the first item
            self.course_combo.addItem("-- Select a course --", None)
            for course in courses:
                course_code, course_name = course
                self.course_combo.addItem(f"{course_name} ({course_code})", course_code)
            
        except Exception as e:
            print(f"❌ Error loading courses: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not load courses: {e}")
    
    def load_instructor_data(self):
        """Load existing instructor data for editing"""
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            # Get instructor details
            cursor.execute("""
                SELECT instructor_name, email, phone
                FROM instructors 
                WHERE instructor_id = ?
            """, (self.instructor_id,))
            
            instructor = cursor.fetchone()
            
            if not instructor:
                QMessageBox.warning(self, "Error", "Instructor not found")
                self.reject()
                return
            
            name, email, phone = instructor
            
            # Set values in the form
            self.name_edit.setText(name)
            self.email_edit.setText(email or "")
            self.phone_edit.setText(phone or "")
            
            # Load assigned courses
            cursor.execute("""
                SELECT c.course_code, c.course_name
                FROM instructor_courses ic
                JOIN courses c ON ic.course_code = c.course_code
                WHERE ic.instructor_id = ?
            """, (self.instructor_id,))
            
            assigned_courses = cursor.fetchall()
            conn.close()
            
            # Display assigned courses
            self.assigned_courses_list.clear()
            for course in assigned_courses:
                course_code, course_name = course
                item = QListWidgetItem(f"{course_name} ({course_code})")
                item.setData(Qt.UserRole, course_code)
                self.assigned_courses_list.addItem(item)
                
        except Exception as e:
            print(f"❌ Error loading instructor data: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not load instructor data: {e}")
            self.reject()
    
    def add_course_to_instructor(self):
        """Add selected course to instructor's assigned courses list"""
        if self.course_combo.count() == 0 or self.course_combo.currentData() is None:
            QMessageBox.information(self, "Information", "Please select a course to add")
            return
        
        course_code = self.course_combo.currentData()
        course_text = self.course_combo.currentText()
        
        # Check if course is already assigned
        for i in range(self.assigned_courses_list.count()):
            item = self.assigned_courses_list.item(i)
            if item.data(Qt.UserRole) == course_code:
                QMessageBox.information(self, "Information", "This course is already assigned to the instructor")
                return
        
        # Add to list
        item = QListWidgetItem(course_text)
        item.setData(Qt.UserRole, course_code)
        self.assigned_courses_list.addItem(item)
        
        # Visual feedback
        self.assigned_courses_list.scrollToItem(item)
        self.assigned_courses_list.setCurrentItem(item)
        
        # Reset selection
        self.course_combo.setCurrentIndex(0)
    
    def remove_course_from_instructor(self):
        """Remove selected course from instructor's assigned courses list"""
        selected_items = self.assigned_courses_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Information", "Please select a course to remove")
            return
        
        for item in selected_items:
            self.assigned_courses_list.takeItem(self.assigned_courses_list.row(item))
    
    def validate_input(self):
        """Validate user input"""
        name = self.name_edit.text().strip()
        phone = self.phone_edit.text().strip()
        email = self.email_edit.text().strip()
        assigned_courses_count = self.assigned_courses_list.count()

        # Name validation
        if not name:
            QMessageBox.warning(self, "Input Error", "Instructor name is required")
            self.name_edit.setFocus()
            return False
        if not re.match(r"^[A-Za-z\s\-']+$", name):
            QMessageBox.warning(self, "Input Error", "Name should only contain letters, spaces, hyphens, or apostrophes")
            self.name_edit.setFocus()
            return False

        # Phone validation (Kenyan format: 07XXXXXXXX)
        if not phone:
            QMessageBox.warning(self, "Input Error", "Phone number is required")
            self.phone_edit.setFocus()
            return False
        if not re.match(r"^07\d{8}$", phone):
            QMessageBox.warning(self, "Input Error", "Phone number must be in the format 07XXXXXXXX (Kenyan mobile number)")
            self.phone_edit.setFocus()
            return False

        # Email validation (if provided)
        if email:
            if not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", email):
                QMessageBox.warning(self, "Input Error", "Please enter a valid email address")
                self.email_edit.setFocus()
                return False

        # At least one course assigned
        if assigned_courses_count == 0:
            QMessageBox.warning(self, "Input Error", "At least one course must be assigned to the instructor")
            return False

        return True
    
    def save_instructor(self):
        """Save the instructor to the database"""
        if not self.validate_input():
            return
        
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            name = self.name_edit.text().strip()
            email = self.email_edit.text().strip() or None
            phone = self.phone_edit.text().strip()
            
            if self.is_edit_mode:
                # Update existing instructor
                cursor.execute("""
                    UPDATE instructors SET 
                    instructor_name = ?,
                    email = ?,
                    phone = ?
                    WHERE instructor_id = ?
                """, (name, email, phone, self.instructor_id))
                
                # Get assigned courses
                assigned_courses = []
                for i in range(self.assigned_courses_list.count()):
                    course_code = self.assigned_courses_list.item(i).data(Qt.UserRole)
                    assigned_courses.append(course_code)
                
                # Delete existing course assignments
                cursor.execute("DELETE FROM instructor_courses WHERE instructor_id = ?", 
                              (self.instructor_id,))
                
                # Add new course assignments
                for course_code in assigned_courses:
                    cursor.execute("""
                        INSERT INTO instructor_courses (instructor_id, course_code)
                        VALUES (?, ?)
                    """, (self.instructor_id, course_code))
                
                message = "Instructor updated successfully"
            else:
                # Insert new instructor
                cursor.execute("""
                    INSERT INTO instructors (instructor_name, email, phone)
                    VALUES (?, ?, ?)
                """, (name, email, phone))
                
                # Get the new instructor ID
                instructor_id = cursor.lastrowid
                
                # Add course assignments
                for i in range(self.assigned_courses_list.count()):
                    course_code = self.assigned_courses_list.item(i).data(Qt.UserRole)
                    cursor.execute("""
                        INSERT INTO instructor_courses (instructor_id, course_code)
                        VALUES (?, ?)
                    """, (instructor_id, course_code))
                
                message = "Instructor created successfully"
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Success", message)
            self.accept()
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                if "instructor_name" in str(e):
                    QMessageBox.warning(self, "Input Error", "An instructor with this name already exists.")
                elif "phone" in str(e):
                    QMessageBox.warning(self, "Input Error", "An instructor with this phone number already exists.")
                else:
                    QMessageBox.warning(self, "Database Error", f"Unique constraint error: {e}")
            else:
                QMessageBox.warning(self, "Database Error", f"Database integrity error: {e}")
        except Exception as e:
            print(f"❌ Error saving instructor: {e}")
            QMessageBox.warning(self, "Database Error", f"Could not save instructor: {e}")