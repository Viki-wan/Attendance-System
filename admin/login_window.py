from PyQt5.QtWidgets import (QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, 
                            QApplication, QWidget, QMessageBox, QFrame, QCheckBox,
                            QProgressBar, QHBoxLayout, QDialog, QGridLayout)  # type: ignore
from PyQt5.QtCore import Qt  # type: ignore
from PyQt5.QtGui import QFont  # type: ignore
import os
import sys

# Ensure the project root is on sys.path so that `config` can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.utils_constants import DATABASE_PATH
from admin.login_attempt_tracker import LoginAttemptTracker
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

        # Initialize attributes that are later assigned in other methods
        self.student_dashboard = None
        self.admin_window = None

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

        # Removed student-specific "Forgot Password" flow

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
            # Admin authentication only
            cursor.execute("SELECT password FROM admin WHERE username = ?", (username,))
            admin_result = cursor.fetchone()

            if not admin_result:
                QMessageBox.warning(self, "Login Failed", "Incorrect username or password.")
                self.handle_failed_login(username)
                return

            stored_hash_text = admin_result[0] or ""
            # Normalize to string and trim whitespace to avoid subtle mismatches
            if isinstance(stored_hash_text, (bytes, bytearray)):
                stored_hash_text = stored_hash_text.decode('utf-8', errors='ignore')
            stored_hash_text = str(stored_hash_text).strip()

            if stored_hash_text.startswith(('$2a$', '$2b$', '$2y$')):
                stored_hash_bytes = stored_hash_text.encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash_bytes):
                    self.open_admin_dashboard()
                    self.login_attempt_tracker.reset_attempts(username)
                else:
                    self.handle_failed_login(username)
            # Legacy SHA-256 hex string
            elif len(stored_hash_text) == 64 and all(c in '0123456789abcdef' for c in stored_hash_text.lower()):
                hashed_input = hashlib.sha256(password.encode('utf-8')).hexdigest()
                if hashed_input.lower() == stored_hash_text.lower():
                    self.open_admin_dashboard()
                    self.login_attempt_tracker.reset_attempts(username)
                else:
                    self.handle_failed_login(username)
            # Plaintext fallback (not recommended, but handled for legacy db)
            else:
                if password == stored_hash_text:
                    self.open_admin_dashboard()
                    self.login_attempt_tracker.reset_attempts(username)
                else:
                    self.handle_failed_login(username)

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {str(e)}")
        finally:
            conn.close()

    # Student-related flows removed

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
    
    # Student-specific forgot password removed
    
    def open_admin_dashboard(self):
        """Opens the Admin Dashboard after successful login."""
        from admin.admin_dashboard import AdminDashboard
        self.admin_window = AdminDashboard()
        self.admin_window.show()
        self.close()