
PRESENTATION_MODE = True
import os
import cv2
import shutil
import sqlite3
import pickle
import numpy as np
import re 
import imagehash
import face_recognition
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGroupBox, QApplication, QPushButton, 
    QLineEdit, QFormLayout, QMessageBox, QSizePolicy, QComboBox, QSpinBox,  QProgressBar, QTabWidget, QCheckBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer
from admin.webcam_window import WebcamWindow
from config.utils_constants import ENCODING_DIR
from PIL import Image, ImageOps

# Constants
IMAGE_DIR = "student_images"
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

class ValidatingTabWidget(QTabWidget):
    """Custom tab widget that validates before allowing tab changes"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.validator = None
    
    def setValidator(self, validator_function):
        """Set the validator function that returns True/False for tab changes"""
        self.validator = validator_function
    
    def mousePressEvent(self, event):
        """Intercept mouse clicks on tab bar"""
        tab_bar = self.tabBar()
        clicked_index = tab_bar.tabAt(event.pos())
        current_index = self.currentIndex()
        
        # If click is outside tabs or going backward, use default behavior
        if clicked_index == -1 or clicked_index <= current_index:
            super().mousePressEvent(event)
            return
        
        # For forward movement, check with validator
        if self.validator and not self.validator(current_index, clicked_index):
            # Validation failed, ignore the click
            event.ignore()
        else:
            # Validation passed, allow normal handling
            super().mousePressEvent(event)


class RegisterStudentWindow(QMainWindow):
    def __init__(self, image_path=None, parent_window=None):
        super().__init__()
        
        self.setWindowTitle("Register Student")
        self.setMinimumSize(800, 600)  # Larger size for better layout
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Apply stylesheet for modern look
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 12px;
            }
            QLabel#title {
                font-size: 24px;
                font-weight: bold;
                color: #2196F3;
                padding: 10px;
            }
            QLabel#section_title {
                font-size: 16px;
                font-weight: bold;
                color: #424242;
                padding: 5px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QGroupBox {
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 16px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2196F3;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom-color: white;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                width: 10px;
            }
        """)

        # Central Widget
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header with logo and title
        header_layout = QHBoxLayout()
        logo_label = QLabel()
        if os.path.exists("icons/school_logo.png"):
            logo_pixmap = QPixmap("icons/school_logo.png").scaled(64, 64, Qt.KeepAspectRatio)
            logo_label.setPixmap(logo_pixmap)
        header_layout.addWidget(logo_label)
        
        title_label = QLabel("Student Registration")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label, 1)
        main_layout.addLayout(header_layout)

        # Progress indicator
        self.progress_layout = QHBoxLayout()
        self.progress_indicator = QProgressBar()
        self.progress_indicator.setRange(0, 100)
        self.progress_indicator.setValue(33)  # Start at step 1 of 3
        self.progress_indicator.setTextVisible(True)
        self.progress_indicator.setFormat("Step 1 of 3: Enter Information")
        self.progress_layout.addWidget(self.progress_indicator)
        main_layout.addLayout(self.progress_layout)

        # Split into two columns: Tab widget on left, image on right
        content_layout = QHBoxLayout()
        
        # Tab widget for form sections
        self.tab_widget = QTabWidget()
        self.tab_widget = QTabWidget()
        
        # Disable tab clicking entirely
        self.tab_widget.tabBar().setEnabled(False)
        
        # Make sure tab widget still shows the tabs visually
        self.tab_widget.setTabBarAutoHide(False)
        self.tab_widget.setDocumentMode(True)  # Option
        
        # Tab 1: Personal Information
        personal_tab = QWidget()
        personal_layout = QFormLayout(personal_tab)
        personal_layout.setSpacing(12)
        personal_layout.setContentsMargins(20, 20, 20, 20)
        
        # First Name field
        self.fname_input = QLineEdit()
        self.fname_input.setPlaceholderText("Enter first name")
        self.fname_input.textChanged.connect(self.block_numbers_in_name)
        personal_layout.addRow("First Name:", self.fname_input)
        
        # Last Name field
        self.lname_input = QLineEdit()
        self.lname_input.setPlaceholderText("Enter last name")
        self.lname_input.textChanged.connect(self.block_numbers_in_name)
        personal_layout.addRow("Last Name:", self.lname_input)
        
        # Student ID field
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Format: S00/00000/YY")
        self.id_input.textChanged.connect(self.on_student_id_changed)
        personal_layout.addRow("Student ID:", self.id_input)
        
        # Email field
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Enter email address")
        personal_layout.addRow("Email:", self.email_input)
        
        # Phone field
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Format: 07XXXXXXXX")
        personal_layout.addRow("Phone:", self.phone_input)
        
        self.tab_widget.addTab(personal_tab, "📋 Personal Info")
        
        # Tab 2: Academic Information
        academic_tab = QWidget()
        academic_layout = QFormLayout(academic_tab)
        academic_layout.setSpacing(12)
        academic_layout.setContentsMargins(20, 20, 20, 20)
        
        # Course selection combobox
        self.course_combo = QComboBox()
        self.course_combo.setPlaceholderText("Select course")
        self.load_courses()  # Load courses from database
        academic_layout.addRow("Course:", self.course_combo)        

        # Year of study
        self.year_input = QSpinBox()
        self.year_input.setRange(1, 6)
        self.year_input.setValue(1)
        self.year_input.valueChanged.connect(self.update_semester_options)
        academic_layout.addRow("Year of Study:", self.year_input)
        
        
        # Current semester
        self.semester_input = QComboBox()
        self.semester_input.addItems(["1.1", "1.2", "2.1", "2.2", "3.1", "3.2", "4.1", "4.2"])
        self.update_semester_options(self.year_input.value())
        academic_layout.addRow("Current Semester:", self.semester_input)
        
        self.tab_widget.addTab(academic_tab, "🎓 Academic Info")
        
        # Tab 3: Photo Capture
        photo_tab = QWidget()
        photo_layout = QVBoxLayout(photo_tab)
        photo_layout.setSpacing(12)
        photo_layout.setContentsMargins(20, 20, 20, 20)
        
        photo_instructions = QLabel(
            "Please ensure that:\n"
            "• Student's face is clearly visible\n"
            "• Lighting is adequate\n"
            "• Background is plain\n"
            "• Only one face is present in the frame"
        )
        photo_instructions.setStyleSheet("background-color: #E3F2FD; padding: 10px; border-radius: 4px;")
        photo_layout.addWidget(photo_instructions)
        
        self.capture_button = QPushButton("📷 Capture Photo")
        photo_layout.addWidget(self.capture_button, alignment=Qt.AlignCenter)
        
        self.tab_widget.addTab(photo_tab, "📸 Photo")
        
        content_layout.addWidget(self.tab_widget, 1)
        
        # Right side: Image preview and quality indicators
        image_panel = QGroupBox("Student Photo")
        image_layout = QVBoxLayout(image_panel)
        image_layout.setContentsMargins(20, 20, 20, 20)
        image_layout.setSpacing(12)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(240, 320)
        self.image_label.setPixmap(QPixmap("icons/profile_placeholder.png").scaled(240, 320, Qt.KeepAspectRatio))
        self.image_label.setStyleSheet("border: 1px solid #ddd; background-color: white;")
        image_layout.addWidget(self.image_label)
        
        # Quality indicators
        self.quality_box = QGroupBox("Image Quality")
        quality_layout = QFormLayout(self.quality_box)
        
        self.face_status_label = QLabel("No face detected")
        self.blur_status_label = QLabel("No image captured")
        self.similarity_status_label = QLabel("Not checked yet")
        
        quality_layout.addRow("Face Detection:", self.face_status_label)
        quality_layout.addRow("Image Clarity:", self.blur_status_label)
        quality_layout.addRow("Similarity Check:", self.similarity_status_label)
        
        self.quality_box.setVisible(False)  # Initially hidden until image captured
        image_layout.addWidget(self.quality_box)
        
        content_layout.addWidget(image_panel, 1)
        
        main_layout.addLayout(content_layout)    
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.back_button = QPushButton("⬅️ Previous")
        self.next_button = QPushButton("Next ➡️")
        self.submit_button = QPushButton("✅ Register Student")
        self.cancel_button = QPushButton("❌ Cancel")
        
        button_layout.addWidget(self.back_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)

        # Store references
        self.parent_window = parent_window
        self.captured_image_path = image_path
        self.captured_frame = None
        self.face_only_path = None  # Store path to face-only image for hashing
        self.temp_files = []  # Track temporary files for cleanup
        self.skip_similarity_check = False  # Flag to bypass similarity check

        # Connect signals
        self.capture_button.clicked.connect(self.open_webcam)
        self.back_button.clicked.connect(self.go_to_previous_tab)
        self.next_button.clicked.connect(self.go_to_next_tab)
        self.submit_button.clicked.connect(self.register_student)
        self.cancel_button.clicked.connect(self.close)
        self.tab_widget.currentChanged.connect(self.update_tab_buttons)

        # Initial button states
        self.update_tab_buttons(0)  # Start with first tab

        # Add upload photo button to the photo tab
        photo_button_layout = QHBoxLayout()
        self.upload_button = QPushButton("📁 Upload Photo")
        self.upload_button.clicked.connect(self.upload_photo)
        photo_button_layout.addWidget(self.upload_button)
        photo_button_layout.addWidget(self.capture_button)
        photo_layout.insertLayout(2, photo_button_layout)  # Insert below instructions
        
        # Add a checkbox to bypass similarity check for presentations
        self.presentation_mode_check = QCheckBox("Presentation Mode (bypass similarity check)")
        self.presentation_mode_check.setChecked(PRESENTATION_MODE)  # Use constant from top of file
        self.presentation_mode_check.stateChanged.connect(self.toggle_presentation_mode)
        photo_layout.addWidget(self.presentation_mode_check)

        # Display image if provided
        if self.captured_image_path:
            self.set_image(self.captured_image_path)
            self.quality_box.setVisible(True)
            self.update_quality_indicators()

        self.image_blur_info = None

    def update_tab_buttons(self, tab_index):
        """Update button states based on the current tab"""
        total_tabs = self.tab_widget.count()
        
        # Determine which buttons should be visible
        is_first_tab = tab_index == 0
        is_last_tab = tab_index == total_tabs - 1
        
        # Update Previous button
        self.back_button.setVisible(not is_first_tab)
        self.back_button.setEnabled(not is_first_tab)
        
        # Update Next/Submit buttons
        self.next_button.setVisible(not is_last_tab)
        self.next_button.setEnabled(not is_last_tab)
        
        # Show Submit button only on last tab
        self.submit_button.setVisible(is_last_tab)
        
        # Update progress indicator
        self.update_progress(tab_index)
        
        # If on the photo tab, ensure quality box visibility is properly set
        if tab_index == 2:  # Photo tab
            self.quality_box.setVisible(self.captured_image_path is not None)

    def go_to_previous_tab(self):
        """Navigate to the previous tab"""
        current_index = self.tab_widget.currentIndex()
        if current_index > 0:
            self.tab_widget.setCurrentIndex(current_index - 1)

    def go_to_next_tab(self):
        """Validate current tab and navigate to the next tab if valid"""
        current_index = self.tab_widget.currentIndex()
        
        # Validate current tab
        if current_index == 0:  # Personal Info tab
            if not self.validate_personal_info():
                return
        elif current_index == 1:  # Academic Info tab
            if not self.validate_academic_info():
                return
                
        # Proceed to next tab
        if current_index < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current_index + 1)

    def validate_personal_info(self):
        """Validate fields in the personal info tab"""
        # Check required fields
        if not self.fname_input.text().strip():
            QMessageBox.warning(self, "Missing Information", "Please enter first name.")
            self.fname_input.setFocus()
            return False
            
        if not self.lname_input.text().strip():
            QMessageBox.warning(self, "Missing Information", "Please enter last name.")
            self.lname_input.setFocus()
            return False
            
        if not self.id_input.text().strip():
            QMessageBox.warning(self, "Missing Information", "Please enter student ID.")
            self.id_input.setFocus()
            return False
            
        # Validate format of fields
        if not self.validate_student_id():
            self.id_input.setFocus()
            return False
            
        if not self.validate_name():
            return False
            
        # All validations passed
        return True
    
    def validate_academic_info(self):
        """Validate fields in the academic info tab"""
        # Check if a course is selected
        if self.course_combo.currentIndex() <= 0:
            QMessageBox.warning(self, "Missing Information", "Please select a course.")
            self.course_combo.setFocus()
            return False
        
        # All validations passed
        return True

    def upload_photo(self):
        """Allow user to upload a photo instead of capturing with webcam"""
        from PyQt5.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Student Photo", 
            "", 
            "Image Files (*.jpg *.jpeg *.png)"
        )
        
        if file_path:
            try:
                # Copy the selected file to a temporary location
                student_id = self.id_input.text().strip()
                if not student_id:
                    QMessageBox.warning(self, "Missing ID", "Please enter Student ID before uploading photo")
                    return
                    
                sanitized_id = student_id.replace('/', '_')
                temp_path = os.path.join(IMAGE_DIR, f"temp_{sanitized_id}.jpg")
                
                # Convert to jpg if needed and resize
                img = Image.open(file_path)
                img = ImageOps.exif_transpose(img)  # Handle rotation
                img = img.convert('RGB')  # Convert to RGB mode
                
                # Resize if too large while maintaining aspect ratio
                max_size = 800
                if max(img.width, img.height) > max_size:
                    if img.width > img.height:
                        new_width = max_size
                        new_height = int(img.height * max_size / img.width)
                    else:
                        new_height = max_size
                        new_width = int(img.width * max_size / img.height)
                    img = img.resize((new_width, new_height), Image.LANCZOS)
                    
                img.save(temp_path, 'JPEG', quality=90)
                self.temp_files.append(temp_path)
                
                # Process uploaded image similar to captured one
                frame = cv2.imread(temp_path)
                self.process_photo(frame, temp_path)
                
            except Exception as e:
                QMessageBox.warning(self, "Upload Error", f"Error processing uploaded image: {e}")



    def update_progress(self, tab_index):
        """Update the progress indicator based on the current tab"""
        if tab_index == 0:  # Personal Info
            self.progress_indicator.setValue(33)
            self.progress_indicator.setFormat("Step 1 of 3: Personal Information")
        elif tab_index == 1:  # Academic Info
            self.progress_indicator.setValue(66)
            self.progress_indicator.setFormat("Step 2 of 3: Academic Information")
        elif tab_index == 2:  # Photo
            self.progress_indicator.setValue(100)
            self.progress_indicator.setFormat("Step 3 of 3: Photo Capture")
    
    def go_back(self):
        """Go back to previous tab"""
        current_index = self.tab_widget.currentIndex()
        if current_index > 0:
            self.tab_widget.setCurrentIndex(current_index - 1)

    def process_photo(self, frame, temp_path):
        """Process photo regardless of source (webcam or upload)"""
        # Store frame for later use
        self.captured_frame = frame.copy() if frame is not None else None
        
        # Check image quality
        blur_value, is_blurry, blur_message = self.check_image_quality(temp_path)
        self.image_blur_info = {
            'value': blur_value,
            'is_blurry': is_blurry,
            'message': blur_message
        }
        
        # Extract face and enhance image
        enhanced_path, face_path = self.enhance_image(temp_path, blur_value)
        if enhanced_path:
            self.temp_files.append(enhanced_path)
        if face_path:
            self.temp_files.append(face_path)
            
        self.captured_image_path = enhanced_path if enhanced_path else temp_path
        self.face_only_path = face_path  # Store face-only path for hashing
        self.set_image(self.captured_image_path)
        
        # Make quality indicators visible
        self.quality_box.setVisible(True)
        self.update_quality_indicators()


    def update_quality_indicators(self):
        """Update the image quality indicators after capture"""
        if not self.captured_image_path:
            return
            
        # Update face detection status
        if self.face_only_path and os.path.exists(self.face_only_path):
            self.face_status_label.setText("✅ Face detected")
            self.face_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.face_status_label.setText("❌ No face detected")
            self.face_status_label.setStyleSheet("color: red; font-weight: bold;")
            
        # Update blur status if available
        if hasattr(self, 'image_blur_info') and self.image_blur_info:
            blur_value = self.image_blur_info['value']
            is_blurry = self.image_blur_info['is_blurry']
            
            if is_blurry:
                if blur_value < 50:
                    status = f"❌ Severely blurry ({blur_value:.1f})"
                    color = "red"
                elif blur_value < 100:
                    status = f"⚠️ Moderately blurry ({blur_value:.1f})"
                    color = "orange"
                else:
                    status = f"⚠️ Slightly blurry ({blur_value:.1f})"
                    color = "orange"
            else:
                status = f"✅ Clear image ({blur_value:.1f})"
                color = "green"
                
            self.blur_status_label.setText(status)
            self.blur_status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            self.blur_status_label.setText("Not analyzed")
            
        # Update similarity status
        self.similarity_status_label.setText("Will check on registration")

    def validate_name(self):
        """Ensure first and last names contain only letters and spaces."""
        fname = self.fname_input.text().strip()
        lname = self.lname_input.text().strip()
        
        if not fname.replace(" ", "").isalpha():
            QMessageBox.warning(self, "Invalid First Name", "First name can only contain letters and spaces.")
            self.fname_input.clear()
            return False
            
        if not lname.replace(" ", "").isalpha():
            QMessageBox.warning(self, "Invalid Last Name", "Last name can only contain letters and spaces.")
            self.lname_input.clear()
            return False
            
        return True
    
    def setup_year_semester_validation(self):
        # Connect the year input's valueChanged signal to a custom slot
        self.year_input.valueChanged.connect(self.update_semester_options)
        
        # Initial update to set correct options based on default year
        self.update_semester_options(self.year_input.value())

    def suggest_year_from_registration(self, registration_id):
        """Suggest academic year based on registration number and current date"""
        import datetime
        
        # Extract the enrollment year from registration number (format: S00/00000/YY)
        match = re.match(r"^S\d{2}/\d{5}/(\d{2})$", registration_id)
        if not match:
            return 1  # Default to first year if format doesn't match
        
        enrollment_year = int(match.group(1))
        
        # Get current year's last two digits
        current_year = datetime.datetime.now().year % 100
        
        # Calculate years since enrollment
        years_enrolled = current_year - enrollment_year
        
        # Handle academic period
        current_month = datetime.datetime.now().month
        # Adjust for academic calendar - assuming academic year starts in September
        if current_month < 9:  # Before September, still in the same academic year
            academic_year = years_enrolled
        else:  # September and after, new academic year has started
            academic_year = years_enrolled + 1
        
        # Handle special cases
        if academic_year < 1:
            return 1
        elif academic_year > 6:  # Assuming maximum 6 years for a program
            return 6
        else:
            return academic_year


    def determine_current_semester(self):
        """Determine the current semester based on today's date
        and student's registration year"""
        import datetime
        
        today = datetime.date.today()
        month = today.month
        
        # Get registration year from ID if available
        student_id = self.id_input.text().strip()
        reg_year = None
        
        match = re.match(r"^S\d{2}/\d{5}/(\d{2})$", student_id)
        if match:
            reg_year = int(match.group(1))
        
        # Determine base semester from month
        if 9 <= month <= 12:
            # First semester (September to December)
            base_semester = 1
        elif 1 <= month <= 4:
            # Second semester (January to April)
            base_semester = 2
        else:
            # Default to first semester during break months
            base_semester = 1
        
        # Special adjustments for specific cohorts
        if reg_year == 24:  # 2024 cohort
            # Currently in second semester of first year
            return 2 if self.year_input.value() == 1 else base_semester
        
        # General case - just return the base semester
        return base_semester
    
    def update_semester_options(self, year):
        """Update semester options based on selected year and current academic period"""
        # Store the current text before clearing (if possible)
        current_text = self.semester_input.currentText()
        
        # Block signals temporarily to prevent unintended side effects
        self.semester_input.blockSignals(True)
        
        # Clear all existing items
        self.semester_input.clear()
        
        # Add the relevant semesters for the selected year
        self.semester_input.addItem(f"{year}.1")
        self.semester_input.addItem(f"{year}.2")
        
        # Determine the current academic semester
        current_semester = self.determine_current_semester()
        
        # Set the default semester based on the academic period
        default_semester = f"{year}.{current_semester}"
        
        # Try to select the current academic semester by default
        index = self.semester_input.findText(default_semester)
        if index >= 0:
            self.semester_input.setCurrentIndex(index)
        else:
            # If not found (shouldn't happen), set to first item
            self.semester_input.setCurrentIndex(0)
        
        # Try to restore previous selection if valid and if this isn't the first load
        if current_text:
            prev_index = self.semester_input.findText(current_text)
            if prev_index >= 0:
                self.semester_input.setCurrentIndex(prev_index)
        
        # Unblock signals
        self.semester_input.blockSignals(False)   

    def block_numbers_in_name(self):
        """Prevent numbers from being typed in the name field."""
        text = self.fname_input.text()
        self.fname_input.setText(re.sub(r"\d+", "", text))  # Remove digits dynamically

        text = self.lname_input.text()
        self.lname_input.setText(re.sub(r"\d+", "", text))  # Remove digits dynamically


    def validate_student_id(self):
        """Ensure student ID follows S00/00000/YY format with valid course code and year range."""
        student_id = self.id_input.text().strip()
        pattern = r"^(S\d{2})/\d{5}/(\d{2})$"
        
        match = re.match(pattern, student_id)
        if not match:
            QMessageBox.warning(self, "Invalid ID", "Student ID must be in the format S00/00000/YY.")
            return False
        
        # Extract the course code and year of enrollment
        course_code = match.group(1)
        enrollment_year = int(match.group(2))
        
        # Validate year range
        if enrollment_year < 17 or enrollment_year > 25:
            QMessageBox.warning(self, "Invalid Year", "Enrollment year must be between 17 and 25.")
            return False
        
        # Validate course code exists in database
        if not self.is_valid_course_code(course_code):
            QMessageBox.warning(self, "Invalid Course Code", 
                            f"Course code '{course_code}' is not recognized. Student ID must start with a valid course code.")
            return False
        
        return True
    
    def is_valid_course_code(self, code):
        """Check if course code exists in the database."""
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            
            # Check if the course code exists
            cursor.execute("SELECT COUNT(*) FROM courses WHERE course_code = ?", (code,))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False

    def on_student_id_changed(self):
        """Auto-select course based on student ID and suggest year of study"""
        student_id = self.id_input.text().strip()
        pattern = r"^(S\d{2})/\d{5}/\d{2}$"
        
        match = re.match(pattern, student_id)
        if match:
            course_code = match.group(1)
            # Find and select the matching course in the combobox
            self.select_course_by_code(course_code)
            
            # Suggest year of study based on registration number
            suggested_year = self.suggest_year_from_registration(student_id)
            
            # Update year input
            self.year_input.setValue(suggested_year)
            
            # Show an informational tooltip about the suggested year
            self.year_input.setToolTip(f"Year {suggested_year} suggested based on registration number.\n"
                                    f"Adjust manually for deferred or special cases.")
            
            # Highlight the year field briefly to draw attention
            self.year_input.setStyleSheet("background-color: #FFFF99;")  # Light yellow highlight
            
            # Reset the highlight after a short delay using a timer
            QTimer.singleShot(2000, lambda: self.year_input.setStyleSheet(""))

    def select_course_by_code(self, course_code):
        """Select the course in the combobox matching the given code."""
        # Find the index of the course in the combobox
        index = -1
        for i in range(self.course_combo.count()):
            item_data = self.course_combo.itemData(i)
            if item_data == course_code:
                index = i
                break
        
        # Select the course if found
        if index > 0:
            self.course_combo.setCurrentIndex(index)
        else:
            # Reset to default selection if no match
            self.course_combo.setCurrentIndex(0)
    

    def load_courses(self):
        """Load courses from database into the combobox."""
        try:
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            
            # Get courses from database
            cursor.execute("SELECT course_code, course_name FROM courses ORDER BY course_name")
            courses = cursor.fetchall()
            
            # Clear existing items
            self.course_combo.clear()
            
            # Add a default empty option
            self.course_combo.addItem("-- Select Course --", "")
            
            # Add courses to combobox
            for course_code, course_name in courses:
                display_text = f"{course_name} ({course_code})"
                self.course_combo.addItem(display_text, course_code)
                
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            # Add fallback option if database fetch fails
            self.course_combo.clear()
            self.course_combo.addItem("Unable to load courses", "")

    def set_image(self, image_path):
        """Display the image in the UI"""
        if not os.path.exists(image_path):
            print(f"Error: Image path does not exist: {image_path}")
            return
            
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio))
            self.captured_image_path = image_path
        else:
            print(f"Error: Failed to load image from {image_path}")

    def open_webcam(self):
        """Opens the webcam window for capturing a photo."""
        self.webcam_window = WebcamWindow(self)
        self.webcam_window.show()


    def save_photo(self, frame):
        """Saves the captured frame and previews it"""
        student_id = self.id_input.text().strip()

        if not student_id:
            QMessageBox.warning(self, "Missing ID", "Please enter Student ID before capturing")
            return

        sanitized_id = student_id.replace('/', '_')
        temp_path = os.path.join(IMAGE_DIR, f"temp_{sanitized_id}.jpg")
        
        try:
            # Attempt to write the image
            success = cv2.imwrite(temp_path, frame)
            
            print(f"Image write successful: {success}")
            print(f"Full path used: {temp_path}")
            
            if not success:
                QMessageBox.warning(self, "Image Save Error", "Failed to save the image")
                return
            
            self.temp_files.append(temp_path)  # Track temp file
        
        except Exception as e:
            print(f"Error writing image: {e}")
            QMessageBox.warning(self, "Image Save Error", f"Could not save image: {e}")
            return

        # Process the captured photo
        self.process_photo(frame, temp_path)
    
    def toggle_presentation_mode(self, state):
        """Toggle presentation mode to bypass similarity checks"""
        self.skip_similarity_check = (state == Qt.Checked)
        if self.skip_similarity_check:
            self.similarity_status_label.setText("⚠️ Similarity check disabled (presentation mode)")
            self.similarity_status_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.similarity_status_label.setText("Will check on registration")
            self.similarity_status_label.setStyleSheet("")


    def check_image_quality(self, image_path):
        """
        Check image quality metrics and determine if image is suitable
        Returns (blur_value, is_blurry, message)
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                return 0, True, "Failed to load image"
            
            # Convert to grayscale for blur detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate Laplacian variance - lower values indicate blurrier images
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Threshold depends on image size and typical lighting conditions
            # These thresholds may need adjustment
            if lap_var < 50:
                blur_level = "severely blurry"
                is_blurry = True
            elif lap_var < 100:
                blur_level = "moderately blurry"
                is_blurry = True
            elif lap_var < 150:
                blur_level = "slightly blurry"
                is_blurry = True
            else:
                blur_level = "acceptable quality"
                is_blurry = False
            
            message = f"Image is {blur_level}"
            return lap_var, is_blurry, message
            
        except Exception as e:
            print(f"Error checking image quality: {e}")
            return 0, True, f"Error checking image quality: {e}"

    def enhance_image(self, image_path, blur_value=0):
        """Apply image enhancements and extract face for better recognition"""
        try:
            # Load and process image
            image = cv2.imread(image_path)
            if image is None:
                return None, None
                
            # Apply deblurring if needed
            if blur_value < 150:
                # Apply different deblurring techniques based on blur level
                if blur_value < 80:
                    # For very blurry images, try blind deconvolution
                    # This is a simplified version, a more complex algorithm might be used
                    kernel_size = 5
                    deblurred = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
                    # Use unsharp mask to enhance edges
                    gaussian = cv2.GaussianBlur(deblurred, (0, 0), 3.0)
                    image = cv2.addWeighted(deblurred, 1.5, gaussian, -0.5, 0)
                else:
                    # For moderately blurry images, sharpen edges
                    kernel = np.array([[-1, -1, -1], 
                                      [-1, 9, -1], 
                                      [-1, -1, -1]])
                    image = cv2.filter2D(image, -1, kernel)
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Try multiple face detection methods
            # First try face_recognition (more accurate but slower)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_image)
            
            # If no face found, try OpenCV's Haar cascade (faster but less accurate)
            if not face_locations:
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
                
                if len(faces) > 0:
                    x, y, w, h = faces[0]
                    face_locations = [(y, x + w, y + h, x)]  # Convert to face_recognition format (top, right, bottom, left)
            
            # Check if multiple faces detected - reject image if so
            if len(face_locations) > 1:
                QMessageBox.warning(self, "Multiple Faces Detected", 
                                   "Multiple faces detected in the image. Please capture an image with only the student's face.")
                return None, None
            
            # Process detected face
            face_path = None
            if face_locations:
                # Extract face coordinates
                top, right, bottom, left = face_locations[0]
                
                # Add padding (20% of face width)
                face_width = right - left
                face_height = bottom - top
                pad_x = int(0.2 * face_width)
                pad_y = int(0.2 * face_height)
                
                # Ensure coordinates stay within image bounds
                left = max(0, left - pad_x)
                top = max(0, top - pad_y)
                right = min(image.shape[1], right + pad_x)
                bottom = min(image.shape[0], bottom + pad_y)
                
                # Extract face region
                face_img = image[top:bottom, left:right]
                
                # Draw rectangle on original image
                cv2.rectangle(image, (left, top), (right, bottom), (0, 255, 0), 2)
                
                # Save face-only image for hash computation
                face_path = image_path.replace(".jpg", "_face.jpg")
                cv2.imwrite(face_path, face_img)
                
                # Perform additional face-specific enhancements
                face_enhanced = self.enhance_face(face_img)
                if face_enhanced is not None:
                    cv2.imwrite(face_path, face_enhanced)
            
            # Always save enhanced full image
            enhanced_path = image_path.replace(".jpg", "_enhanced.jpg")
            cv2.imwrite(enhanced_path, image)
            
            return enhanced_path, face_path
                
        except Exception as e:
            print(f"Enhancement error: {e}")
            return None, None

    def enhance_face(self, face_img):
        """Apply specific enhancements to the face image"""
        try:
            # Convert to LAB color space for better color enhancement
            lab = cv2.cvtColor(face_img, cv2.COLOR_BGR2LAB)
            
            # Split the LAB image into L, A, and B channels
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L-channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            
            # Merge the CLAHE enhanced L-channel with the A and B channels
            merged = cv2.merge((cl, a, b))
            
            # Convert back to BGR color space
            enhanced_face = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
            
            # Apply additional sharpening if needed
            kernel = np.array([[-1, -1, -1], 
                              [-1, 9, -1], 
                              [-1, -1, -1]])
            enhanced_face = cv2.filter2D(enhanced_face, -1, kernel)
            
            return enhanced_face
        except Exception as e:
            print(f"Face enhancement error: {e}")
            return None

    def compute_phash(self, image_path, face_only_path=None):
        """Compute perceptual hash prioritizing face if available"""
        try:
            # If face extraction succeeded, use that for hashing
            if face_only_path and os.path.exists(face_only_path):
                try:
                    # Process face image
                    face_image = Image.open(face_only_path).convert("L")
                    face_image = ImageOps.exif_transpose(face_image)
                    face_image = face_image.resize((128, 128))
                    face_image = ImageOps.autocontrast(face_image)
                    return str(imagehash.phash(face_image)), True  # Return with flag indicating face was used
                except Exception as e:
                    print(f"Face hash computation failed: {e}, falling back to full image")
            
            # Fall back to full image if face extraction failed or caused an error
            full_image = Image.open(image_path).convert("L")
            full_image = ImageOps.exif_transpose(full_image)
            full_image = full_image.resize((128, 128))
            full_image = ImageOps.autocontrast(full_image)
            return str(imagehash.phash(full_image)), False  # Return with flag indicating full image was used
            
        except Exception as e:
            print(f"Hash computation error: {e}")
            return None, False

    def get_dynamic_threshold(self, conn):
        """Calculate a dynamic threshold based on dataset variance"""
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students")
            count = cursor.fetchone()[0]
            
            # For small datasets, use a conservative threshold
            if count < 10:
                return 10  # Default threshold for small datasets
                
            # For larger datasets, calculate based on existing hash differences
            cursor.execute("SELECT image_hash FROM students WHERE image_hash IS NOT NULL")
            hashes = [row[0] for row in cursor.fetchall() if row[0]]
            
            if len(hashes) < 2:
                return 10  # Not enough data for analysis
                
            # Calculate differences between all pairs (limited to 100 random pairs for performance)
            import random
            if len(hashes) > 15:  # If we have many hashes
                # Sample pairs to avoid O(n²) comparison
                pairs = []
                for _ in range(min(100, len(hashes) * 2)):
                    i, j = random.sample(range(len(hashes)), 2)
                    pairs.append((hashes[i], hashes[j]))
            else:
                # For small datasets, compare all pairs
                pairs = [(hashes[i], hashes[j]) 
                         for i in range(len(hashes)) 
                         for j in range(i+1, len(hashes))]
            
            # Calculate Hamming distances
            distances = []
            for hash1, hash2 in pairs:
                dist = sum(ch1 != ch2 for ch1, ch2 in zip(hash1, hash2))
                distances.append(dist)
                
            if not distances:
                return 10
                
            # Perform statistical analysis
            mean_dist = sum(distances) / len(distances)
            std_dev = (sum((d - mean_dist)**2 for d in distances) / len(distances))**0.5
            
            # Set threshold at 1/3 of the mean distance but not less than 5
            # This assumes genuine matches should be significantly closer than random pairs
            dynamic_threshold = max(5, int(mean_dist / 3))
            
            print(f"Dynamic threshold calculated: {dynamic_threshold} (from mean: {mean_dist:.2f}, std: {std_dev:.2f})")
            return dynamic_threshold
            
        except Exception as e:
            print(f"Error calculating dynamic threshold: {e}")
            return 10  # Fall back to default threshold
        
    def reset_form(self):
        """Reset all form elements for registering another student"""
        # Reset text inputs
        self.fname_input.clear()
        self.lname_input.clear()
        self.id_input.clear()
        
        # Reset image display
        self.image_label.setPixmap(QPixmap("icons/profile_placeholder.png").scaled(200, 200, Qt.KeepAspectRatio))
        
        # Reset stored image paths
        self.captured_image_path = None
        self.face_only_path = None
        self.captured_frame = None
        
        # Clean up any remaining temp files
        self.cleanup_temp_files()
        
        # Reset focus to the first input field
        self.name_input.setFocus()

    def is_similar_image(self, new_image_path, conn, face_only_path=None):
        """Check if image is similar to existing ones using dynamic threshold and face priority"""

        if self.skip_similarity_check:
            print("Skipping similarity check (presentation mode active)")
            return False, None, None, "Similarity check bypassed (presentation mode)"
        # Add a check at the beginning of this method
        if hasattr(self, 'skip_similarity_check') and self.skip_similarity_check:
            return False, None, None, None  # Skip similarity check completely
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, image_path, image_hash, face_encoding FROM students")
            results = cursor.fetchall()
            
            # Calculate dynamic threshold based on existing data
            phash_threshold = self.get_dynamic_threshold(conn)
            face_tolerance = 0.55  # Face recognition tolerance
            
            # Compute hash for new image, prioritizing face
            new_hash, used_face = self.compute_phash(new_image_path, face_only_path)
            if not new_hash:
                return False, None, "Failed to compute hash", "warning"

            # Load face for new image
            new_image = face_recognition.load_image_file(new_image_path)
            new_encodings = face_recognition.face_encodings(new_image)

            has_face = len(new_encodings) > 0
            face_warning = None
            
            if not has_face:
                face_warning = "⚠️ No face detected in image - using only image similarity"
            
            # Check against all existing students
            for student_id, existing_path, existing_hash, encoding_blob in results:
                # Compare face encodings if available
                if has_face and encoding_blob:
                    try:
                        # Deserialize the list of encodings
                        existing_encodings = pickle.loads(encoding_blob)
                        
                        # Compare against each stored encoding
                        for existing_encoding in existing_encodings:
                            face_distance = face_recognition.face_distance([existing_encoding], new_encodings[0])[0]
                            if face_distance < face_tolerance:
                                return True, student_id, f"Face similarity: {face_distance:.2f}", None
                    except Exception as e:
                        print(f"Face comparison error: {e}")
                
                # Compare hashes
                if existing_hash and new_hash:
                    try:
                        hash_diff = sum(ch1 != ch2 for ch1, ch2 in zip(new_hash, existing_hash))
                        if hash_diff <= phash_threshold:
                            return True, student_id, f"Image similarity: {hash_diff}/{len(new_hash)} (threshold: {phash_threshold})", None
                    except Exception as e:
                        print(f"Hash comparison error: {e}")

            # Return with warning if necessary
            return False, None, None, face_warning
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False, None, f"Database error: {e}", None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False, None, f"Error: {e}", None

    def generate_augmented_encodings(self, image):
        """Generate multiple face encodings with slight augmentations for better recognition"""
        try:
            # Original encoding
            original_encodings = face_recognition.face_encodings(image)
            if not original_encodings:
                return []
                
            original_encoding = original_encodings[0]
            augmented_encodings = [original_encoding]
            
            # Convert to PIL for augmentations
            pil_image = Image.fromarray(image)
            
            # Slight brightness variations (+/- 10%)
            for factor in [0.9, 1.1]:
                try:
                    # Apply brightness adjustment
                    enhancer = ImageOps.autocontrast(pil_image)
                    # Convert back to numpy array
                    adjusted = np.array(enhancer)
                    # Get encodings from the adjusted image
                    adjusted_encodings = face_recognition.face_encodings(adjusted)
                    if adjusted_encodings:
                        augmented_encodings.append(adjusted_encodings[0])
                except Exception as e:
                    print(f"Error generating brightness augmentation: {e}")
            
            # Small rotations (+/- 5 degrees)
            for angle in [-5, 5]:
                try:
                    # Apply rotation
                    rotated = pil_image.rotate(angle)
                    # Convert back to numpy array
                    rotated_array = np.array(rotated)
                    # Get encodings from the rotated image
                    rotated_encodings = face_recognition.face_encodings(rotated_array)
                    if rotated_encodings:
                        augmented_encodings.append(rotated_encodings[0])
                except Exception as e:
                    print(f"Error generating rotation augmentation: {e}")
            
            print(f"Generated {len(augmented_encodings)} augmented face encodings")
            return augmented_encodings
            
        except Exception as e:
            print(f"Error in augmentation: {e}")
            return []
        
    def register_student(self):
        """Register student with comprehensive duplicate checking"""
        if not self.validate_name() or not self.validate_student_id():
            return  # Stop if validation fails
        if not self.captured_image_path:
            QMessageBox.warning(self, "Missing Photo", "Please capture or upload a photo first")
            return
        
        # Make sure all previous tabs are valid
        if not self.validate_personal_info() or not self.validate_academic_info():
            return
        
        # Get all input values
        first_name = self.fname_input.text().strip()
        last_name = self.lname_input.text().strip()
        student_id = self.id_input.text().strip()
        
        # Get selected course
        selected_index = self.course_combo.currentIndex()
        if selected_index <= 0:  # Check if a valid option is selected (not the default)
            QMessageBox.warning(self, "Missing Information", "Please select a course.")
            return
        
        course_code = self.course_combo.itemData(selected_index)  # Get the course_code stored as item data
        
        # Get additional input values
        year = self.year_input.value()
        semester = self.semester_input.currentText()
        email = self.email_input.text().strip()
        phone = self.phone_input.text().strip()

        sanitized_id = student_id.replace('/', '_')

        # Validate inputs
        if not first_name or not student_id or not last_name:
            QMessageBox.warning(self, "Incomplete Data", "Please fill all fields")
            return
        
        if not self.captured_image_path or not os.path.exists(self.captured_image_path):
            QMessageBox.warning(self, "Missing Photo", "Please capture a photo first")
            return

        # Check for blur only once, using stored info if available
        if hasattr(self, 'image_blur_info') and self.image_blur_info:
            blur_value = self.image_blur_info['value']
            is_blurry = self.image_blur_info['is_blurry']
            blur_message = self.image_blur_info['message']
        else:
            # Fallback to checking if we somehow don't have the info
            blur_value, is_blurry, blur_message = self.check_image_quality(self.captured_image_path)
        
        # Show blur warning only once during registration
        if is_blurry:
            response = QMessageBox.warning(
                self,
                "Low Quality Image",
                f"{blur_message}\n\nThe image appears to be blurry (blur value: {blur_value:.2f}).\n"
                "This may reduce recognition accuracy.\n\n"
                "Do you want to continue with registration?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if response == QMessageBox.No:
                return
                
        # Create encoding directory if it doesn't exist
        if not os.path.exists(ENCODING_DIR):
            try:
                os.makedirs(ENCODING_DIR)
                print(f"Created encoding directory: {ENCODING_DIR}")
            except Exception as e:
                QMessageBox.critical(self, "Directory Error", f"Failed to create encoding directory: {e}")
                return
        
        # Define encoding path
        encoding_path = os.path.join(ENCODING_DIR, f"student_{sanitized_id}_encodings.pkl")
        print(f"Encoding path: {encoding_path}")

        try:
            # Initialize database connection
            conn = sqlite3.connect("attendance.db")
            cursor = conn.cursor()
            
            # Check for duplicate ID
            cursor.execute("SELECT student_id FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone():
                QMessageBox.warning(self, "Duplicate ID", "A student with this ID already exists")
                return

            # Check for similar images with enhanced face-priority
            duplicate_found, existing_student_id, reason, warning = self.is_similar_image(
                self.captured_image_path, 
                conn,
                self.face_only_path
            )
            
            if duplicate_found:
                QMessageBox.warning(
                    self, 
                    "Duplicate Detected", 
                    f"Similar image found for Student ID: {existing_student_id}\n{reason}"
                )
                return
                
            if warning:
                # Show warning but allow registration to continue
                response = QMessageBox.warning(
                    self,
                    "Registration Warning",
                    f"{warning}\n\nDo you want to continue with registration?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if response == QMessageBox.No:
                    return
            # Compute optimized hash
            image_hash, used_face = self.compute_phash(self.captured_image_path, self.face_only_path)
            if not image_hash:
                QMessageBox.warning(self, "Processing Error", "Failed to process the image")
                return

            # Face detection and encoding with augmentation
            image = face_recognition.load_image_file(self.captured_image_path)
            
            # Check for multiple faces again - explicit rejection
            face_locations = face_recognition.face_locations(image)
            if len(face_locations) > 1:
                QMessageBox.warning(
                    self,
                    "Multiple Faces Detected",
                    "Multiple faces were detected in the image. Please capture an image with only the student's face.",
                    QMessageBox.Ok
                )
                return
                
            # Generate multiple augmented encodings for better recognition
            augmented_encodings = self.generate_augmented_encodings(image)

            # Set encoding_blob based on whether we have encodings
            if augmented_encodings:
                # Serialize the encodings to a blob for database storage
                encoding_blob = pickle.dumps(augmented_encodings)
                
                # Save to file - make sure the directory exists
                try:
                    with open(encoding_path, 'wb') as f:
                        pickle.dump(augmented_encodings, f)
                    print(f"Successfully saved encodings to {encoding_path}")
                except IOError as e:
                    QMessageBox.warning(
                        self,
                        "File Save Error",
                        f"Failed to save encodings to file: {e}\nContinuing with database only storage."
                    )
                    # We'll continue with just the database blob in this case
            else:
                QMessageBox.warning(
                    self,
                    "No Face Detected",
                    "No face was detected in the image. Please capture a new photo with a clearly visible face.",
                    QMessageBox.Ok
                )
                return  

            # Final image path
            final_image_path = os.path.join(IMAGE_DIR, f"{sanitized_id}.jpg")
            
            # Copy image to final location if needed
            if self.captured_image_path != final_image_path:
                shutil.copy2(self.captured_image_path, final_image_path)
            
            # Also save face-only image if available
            face_image_path = None
            if self.face_only_path and os.path.exists(self.face_only_path):
                face_image_path = os.path.join(IMAGE_DIR, f"{sanitized_id}_face.jpg")
                shutil.copy2(self.face_only_path, face_image_path)
            
            # Debug print for verification
            print(f"Encoding path saved to DB: {encoding_path}")
            print(f"Encoding blob size: {len(encoding_blob) if encoding_blob else 0} bytes")
            
            # Insert student into database with all additional fields
            cursor.execute("""
                 INSERT INTO students (fname, lname, student_id, image_path, image_hash, face_encoding, 
                                face_only_path, course, year_of_study, email, phone, 
                                current_semester, face_encoding_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (first_name, last_name, student_id, final_image_path, image_hash, encoding_blob, 
            face_image_path, course_code, year, email, phone, semester, encoding_path))
                        
            # Insert student course enrollment
            cursor.execute(
                """
                INSERT INTO student_courses 
                (student_id, course_code, semester, enrollment_date)
                VALUES (?, ?, ?, date('now'))
                """,
                (student_id, course_code, semester)
            )
            
            # Log the activity
            cursor.execute(
                """
                INSERT INTO activity_log 
                (user_id, activity_type, timestamp)
                VALUES (?, ?, datetime('now', 'localtime'))
                """,
                ("admin", f"Student registered: {student_id}")
            )
            
            conn.commit()
            
            # Show success message with details
            success_msg = "Student registered successfully"
            if not encoding_blob:
                success_msg += "\n\nNote: No face detected. Recognition may be less accurate."
            elif not used_face:
                success_msg += "\n\nNote: Full image used for hashing, not just the face."
                
            # Show number of encodings stored
            if encoding_blob:
                num_encodings = len(augmented_encodings)
                success_msg += f"\n\nStored {num_encodings} face encodings for improved recognition."
                
                response = QMessageBox.information(
                    self, 
                    "Success", 
                    success_msg + "\n\nWould you like to register another student?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                self.cleanup_temp_files()

                if response == QMessageBox.Yes:
                    # Reset the form for another registration
                    self.reset_form()
                else:
                    # Close the window and refresh parent window if it exists
                    if hasattr(self, 'parent_window') and self.parent_window:
                        self.parent_window.refresh_student_list()
                    self.close()
            
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()  # This will print the full stack trace to console for debugging
        finally:
            if conn:
                conn.close()
                
    def cleanup_temp_files(self):
        """Clean up temporary files with improved safety checks"""
        for path in self.temp_files:
            try:
                # Safety checks before deletion
                if path and os.path.exists(path) and os.path.isfile(path):
                    # Verify it's in the correct directory and has temp in the name
                    if os.path.dirname(path) == os.path.abspath(IMAGE_DIR) and "temp_" in os.path.basename(path):
                        os.remove(path)
                        print(f"Removed temp file: {path}")
                    else:
                        print(f"Skipping deletion of non-temp file: {path}")
            except Exception as e:
                print(f"Error removing temp file {path}: {e}")
        
        # Clear the list after cleanup
        self.temp_files = []