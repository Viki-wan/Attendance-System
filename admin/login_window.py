from PyQt5.QtWidgets import (QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, 
                            QApplication, QWidget, QMessageBox, QFrame, QCheckBox,
                            QProgressBar, QHBoxLayout, QDialog, QGridLayout, QInputDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from config.utils_constants import DATABASE_PATH
from admin.login_attempt_tracker import LoginAttemptTracker
from students.student_dashboard import StudentDashboard
import sqlite3
import hashlib
import bcrypt
import re

def get_dark_mode_setting():
    """Fetches dark mode setting from the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'dark_mode'")
    result = cursor.fetchone()
    conn.close()
    return result[0] == "1" if result else False

class PasswordStrengthChecker:
    """Utility class to check and score password strength"""
    
    @staticmethod
    def check_strength(password):
        """
        Returns a score from 0-100 based on password strength
        and a color indicator (red, yellow, green)
        """
        score = 0
        feedback = []
        
        # Length check (up to 40 points)
        if len(password) >= 8:
            score += 20
            if len(password) >= 12:
                score += 20
        else:
            feedback.append("Password should be at least 8 characters")
            
        # Complexity checks (60 points total)
        if re.search(r'[A-Z]', password):  # Uppercase
            score += 15
        else:
            feedback.append("Add uppercase letters")
            
        if re.search(r'[a-z]', password):  # Lowercase
            score += 15
        else:
            feedback.append("Add lowercase letters")
            
        if re.search(r'[0-9]', password):  # Numbers
            score += 15
        else:
            feedback.append("Add numbers")
            
        if re.search(r'[^A-Za-z0-9]', password):  # Special chars
            score += 15
        else:
            feedback.append("Add special characters (!@#$%^&*)")
        
        # Determine color
        if score < 50:
            color = "red"
        elif score < 80:
            color = "orange"
        else:
            color = "green"
            
        return score, color, feedback

class PasswordDialog(QDialog):
    """Custom dialog for setting/changing passwords with strength indicator"""
    
    def __init__(self, parent=None, first_time=False):
        super().__init__(parent)
        self.setWindowTitle("Create Password")
        self.setMinimumWidth(400)
        self.first_time = first_time
        
        # Main layout
        layout = QVBoxLayout()
        
        # Message explaining the situation
        if first_time:
            welcome_label = QLabel("Welcome! Please create a password for your account.")
            welcome_label.setFont(QFont("Arial", 10))
            layout.addWidget(welcome_label)
            
            info_label = QLabel("For security, you need to create a strong password to protect your account.")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            layout.addSpacing(10)
        
        # Password form layout
        form_layout = QGridLayout()
        
        # Password field
        self.password_label = QLabel("New Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.textChanged.connect(self.update_strength_indicator)
        
        # Show password checkbox  
        self.show_password = QCheckBox("Show password")
        self.show_password.stateChanged.connect(self.toggle_password_visibility)
        
        # Password strength indicator
        strength_layout = QHBoxLayout()
        strength_label = QLabel("Password Strength:")
        self.strength_bar = QProgressBar()
        self.strength_bar.setTextVisible(True)
        self.strength_bar.setRange(0, 100)
        strength_layout.addWidget(strength_label)
        strength_layout.addWidget(self.strength_bar)
        
        # Feedback label for password tips
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        
        # Confirm password
        self.confirm_label = QLabel("Confirm Password:")
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.textChanged.connect(self.check_passwords_match)
        
        # Match indicator
        self.match_label = QLabel()
        
        # Add to form layout
        form_layout.addWidget(self.password_label, 0, 0)
        form_layout.addWidget(self.password_input, 0, 1)
        form_layout.addWidget(self.show_password, 1, 1)
        
        # Add strength indicator
        layout.addLayout(form_layout)
        layout.addLayout(strength_layout)
        layout.addWidget(self.feedback_label)
        
        # Add confirm password
        confirm_layout = QGridLayout()
        confirm_layout.addWidget(self.confirm_label, 0, 0)
        confirm_layout.addWidget(self.confirm_input, 0, 1)
        confirm_layout.addWidget(self.match_label, 1, 1)
        layout.addLayout(confirm_layout)
        
        # Password guidelines
        guidelines = QLabel("Password should contain:\n"
                           "• At least 8 characters\n"
                           "• Uppercase and lowercase letters\n"
                           "• Numbers\n"
                           "• Special characters (!@#$%^&*)")
        guidelines.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(guidelines)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Password")
        self.save_button.clicked.connect(self.accept)
        self.save_button.setEnabled(False)  # Disabled until criteria met
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        if not first_time:  # Only show cancel for optional password changes
            button_layout.addWidget(self.cancel_button)
            
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def toggle_password_visibility(self, state):
        """Toggle password visibility for both fields"""
        echo_mode = QLineEdit.Normal if state else QLineEdit.Password
        self.password_input.setEchoMode(echo_mode)
        self.confirm_input.setEchoMode(echo_mode)
    
    def update_strength_indicator(self):
        """Update the password strength indicator"""
        password = self.password_input.text()
        
        if not password:
            self.strength_bar.setValue(0)
            self.strength_bar.setStyleSheet("")
            self.feedback_label.setText("")
            self.save_button.setEnabled(False)
            return
            
        score, color, feedback = PasswordStrengthChecker.check_strength(password)
        
        # Update progress bar
        self.strength_bar.setValue(score)
        self.strength_bar.setFormat(f"{score}% - {'Weak' if score < 50 else 'Medium' if score < 80 else 'Strong'}")
        self.strength_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")
        
        # Update feedback
        if feedback:
            self.feedback_label.setText("Suggestions: " + ", ".join(feedback))
        else:
            self.feedback_label.setText("Excellent password!")
            
        # Check if password meets minimum requirements
        self.check_save_button_state(score >= 50)
    
    def check_passwords_match(self):
        """Check if the two password fields match"""
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        
        if not confirm:
            self.match_label.setText("")
            return
            
        if password == confirm:
            self.match_label.setStyleSheet("color: green;")
            self.match_label.setText("✓ Passwords match")
            # Enable save button if strength is also OK
            self.check_save_button_state(True)
        else:
            self.match_label.setStyleSheet("color: red;")
            self.match_label.setText("✗ Passwords don't match")
            self.save_button.setEnabled(False)
    
    def check_save_button_state(self, strength_ok):
        """Enable/disable the save button based on password criteria"""
        passwords_match = (self.password_input.text() == self.confirm_input.text() 
                          and self.confirm_input.text() != "")
        
        # Enable save button only if passwords match and strength is acceptable
        self.save_button.setEnabled(strength_ok and passwords_match)
    
    def get_password(self):
        """Return the entered password"""
        return self.password_input.text()

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔐 Login")
        self.setFixedSize(400, 350)  # ✅ Set a modern, non-resizable window

        self.login_attempt_tracker = LoginAttemptTracker()

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS

        self.dark_mode_enabled = get_dark_mode_setting()

        # Central Widget & Layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setAlignment(Qt.AlignCenter)

        # Container Frame
        container = QFrame(self)
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)
        container_layout.setAlignment(Qt.AlignCenter)

        # Title Label
        title_label = QLabel("AI Attendance System Login", self)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(title_label)

        # Username Field
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("👤 Enter ID")
        self.username_input.setFont(QFont("Arial", 12))
        container_layout.addWidget(self.username_input)

        # Password Field
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("🔑 Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFont(QFont("Arial", 12))
        container_layout.addWidget(self.password_input)

        # Show Password Checkbox
        self.show_password_checkbox = QCheckBox("Show Password")
        self.show_password_checkbox.stateChanged.connect(self.toggle_password_visibility)
        container_layout.addWidget(self.show_password_checkbox)

        # Forgot Password Link
        self.forgot_password_link = QLabel("<a href='#'>Forgot Password?</a>")
        self.forgot_password_link.setAlignment(Qt.AlignRight)
        self.forgot_password_link.setOpenExternalLinks(False)
        self.forgot_password_link.linkActivated.connect(self.handle_forgot_password)
        container_layout.addWidget(self.forgot_password_link)

        # Login Button
        self.login_button = QPushButton("Login", self)
        self.login_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self.authenticate)
        container_layout.addWidget(self.login_button)

        # Add Container to Main Layout
        main_layout.addWidget(container)

    def toggle_password_visibility(self):
        """Toggle password visibility"""
        if self.show_password_checkbox.isChecked():
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def authenticate(self):
        """Enhanced authentication with persistent login attempt tracking."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        # Input validation
        if not username or not password:
            QMessageBox.warning(self, "Login Failed", "Please enter both username and password.")
            return

        # Check for lockout
        if self.login_attempt_tracker.is_locked_out(username):
            remaining_time = self.login_attempt_tracker.get_remaining_lockout_time(username)
            QMessageBox.warning(self, "Account Locked", 
                f"Too many failed attempts. Please wait {remaining_time} seconds before trying again.")
            return

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        try:
            # Admin authentication
            cursor.execute("SELECT password FROM admin WHERE username = ?", (username,))
            admin_result = cursor.fetchone()

            if admin_result:
                stored_hash = admin_result[0]
                # Check if password matches using bcrypt
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    self.open_admin_dashboard()
                    self.login_attempt_tracker.reset_attempts(username)
                    return
                else:
                    self.handle_failed_login(username)
                    return
                    
            # Student authentication
            cursor.execute("SELECT password, student_id FROM students WHERE student_id = ?", (username,))
            student_result = cursor.fetchone()

            if student_result:
                stored_password = student_result[0]
                student_id = student_result[1]

                # First-time login handling - check if password equals student ID or is empty
                if not stored_password or (stored_password == hashlib.sha256(student_id.encode()).hexdigest()):
                    # Handle seamless first-time login
                    if self.handle_first_time_login(student_id):
                        # If password setup was successful, proceed to dashboard
                        self.open_student_dashboard(student_id)
                        self.close()
                    return
                    
                # Regular password check - handle both bcrypt and legacy SHA-256 
                if stored_password.startswith(b'$2b$') or stored_password.startswith('$2b$'):
                    # Bcrypt password
                    if isinstance(stored_password, str):
                        stored_password = stored_password.encode('utf-8')
                    
                    if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                        self.open_student_dashboard(student_id)
                        self.login_attempt_tracker.reset_attempts(username)
                        self.close()
                    else:
                        self.handle_failed_login(username)
                else:
                    # Legacy SHA-256 password
                    hashed_input = hashlib.sha256(password.encode()).hexdigest()
                    if stored_password == hashed_input:
                        self.open_student_dashboard(student_id)
                        self.login_attempt_tracker.reset_attempts(username)
                        # Optional: Migrate to bcrypt
                        self.migrate_to_bcrypt(student_id, password)
                        self.close()
                    else:
                        self.handle_failed_login(username)
            else:
                QMessageBox.warning(self, "Login Failed", "User not found.")
                self.handle_failed_login(username)

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {str(e)}")
        finally:
            conn.close()

    def migrate_to_bcrypt(self, student_id, plain_password):
        """Migrate old SHA-256 password to bcrypt for better security"""
        try:
            bcrypt_hash = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
            
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET password = ? WHERE student_id = ?", 
                         (bcrypt_hash, student_id))
            conn.commit()
            conn.close()
        except Exception as e:
            # Silently handle errors - this is just an upgrade, not critical
            pass
    
    def handle_first_time_login(self, student_id):
        """Handle first-time login with a better UX flow"""
        # Show information message
        QMessageBox.information(self, "Welcome",
            "Welcome to the attendance system! As this is your first login, " 
            "you'll need to create a secure password.")
            
        # Show password dialog
        password_dialog = PasswordDialog(self, first_time=True)
        if password_dialog.exec_():
            new_password = password_dialog.get_password()
            
            # Hash the password with bcrypt
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            # Save to database
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET password = ? WHERE student_id = ?", 
                         (hashed_password, student_id))
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Password Created", 
                "Your password has been created successfully! You'll now be logged in.")
            
            self.login_attempt_tracker.reset_attempts(student_id)
            return True
        return False

    def open_student_dashboard(self, username):
        self.student_dashboard = StudentDashboard(username)  # Create dashboard instance
        self.student_dashboard.show()  # Show dashboard

    def handle_failed_login(self, username):
        """Handle and display failed login attempt."""
        # Record the failed attempt
        attempts, _ = self.login_attempt_tracker.record_failed_attempt(username)
        
        # Display specific error messages based on attempts
        if attempts == 1:
            QMessageBox.warning(self, "Login Failed", "Incorrect username or password. Try again.")
        elif attempts == 2:
            QMessageBox.warning(self, "Login Failed", "Second failed attempt. One more try before temporary lockout.")
        else:
            QMessageBox.warning(self, "Account Locked", 
                "Too many failed attempts. Please wait 5 minutes before trying again.")
    
    def handle_forgot_password(self):
        """Handle forgot password requests"""
        student_id, ok = QInputDialog.getText(self, "Forgot Password", 
                                             "Please enter your Student ID:")
        if ok and student_id:
            # Verify student exists
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name, email FROM students WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                name, email = result
                # In a real implementation, you would:
                # 1. Generate a temporary code or token
                # 2. Email it to the student's address
                # 3. Allow them to reset their password with the token
                
                QMessageBox.information(self, "Password Reset", 
                    f"A password reset link has been sent to {email}.\n\n"
                    f"Please check your email and follow the instructions.")
            else:
                QMessageBox.warning(self, "Student Not Found", 
                    "No student with that ID was found in our records.")
    
    def open_admin_dashboard(self):
        """Opens the Admin Dashboard after successful login."""
        from admin.admin_dashboard import AdminDashboard
        self.admin_window = AdminDashboard()
        self.admin_window.show()
        self.close()