from PyQt5.QtWidgets import QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, QApplication, QWidget, QMessageBox, QFrame, QCheckBox
from PyQt5.QtCore import Qt  
from PyQt5.QtGui import QFont
from config.utils_constants import DATABASE_PATH

import sqlite3
import hashlib

def get_dark_mode_setting():
    """Fetches dark mode setting from the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'dark_mode'")
    result = cursor.fetchone()
    conn.close()
    return result[0] == "1" if result else False

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔐 Login")
        self.setFixedSize(400, 350)  # ✅ Set a modern, non-resizable window

        self.setStyleSheet(QApplication.instance().styleSheet())  # ✅ Inherit global QSS

        self.dark_mode_enabled = get_dark_mode_setting()

        # Central Widget & Layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setAlignment(Qt.AlignCenter)

        # Container Frame
        container = QFrame(self)
        container.setStyleSheet("background: rgba(50, 50, 50, 0.8); border-radius: 10px;")
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(15)
        container_layout.setAlignment(Qt.AlignCenter)

        # Title Label
        title_label = QLabel("Modern Login System UI", self)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(title_label)

        # Username Field
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("👤 Username")
        self.username_input.setFont(QFont("Arial", 12))
        container_layout.addWidget(self.username_input)

        # Password Field
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("🔑 Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFont(QFont("Arial", 12))
        container_layout.addWidget(self.password_input)

        # Remember Me Checkbox
        self.remember_me = QCheckBox("Remember Me", self)
        self.remember_me.setFont(QFont("Arial", 11))
        container_layout.addWidget(self.remember_me)

        # Login Button
        self.login_button = QPushButton("Login", self)
        self.login_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self.authenticate)  # ✅ Connect to authentication method
        container_layout.addWidget(self.login_button)

        # Add Container to Main Layout
        main_layout.addWidget(container)

        self.apply_dark_mode()

    def apply_dark_mode(self):
        """Applies dark mode based on user settings."""
        if self.dark_mode_enabled:
            self.setStyleSheet("""
                QMainWindow { background-color: #2B2B2B; }
                QLabel { color: white; }
                QLineEdit {
                    background-color: #3A3A3A; color: #FFFFFF; 
                    border: 1px solid #555; border-radius: 6px; padding: 10px;
                }
                QPushButton {
                    background-color: #007BFF; color: white; 
                    border: 2px solid #0056b3;  
                    border-radius: 6px; padding: 10px; font-weight: bold;
                }
                QPushButton:hover { background-color: #0056b3; }
                QCheckBox { color: white; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: white; }
                QLabel { color: black; }
                QLineEdit {
                    background-color: #F5F5F5; color: #000; 
                    border: 1px solid #CCC; border-radius: 6px; padding: 10px;
                }
                QPushButton {
                    background-color: #007BFF; color: white; 
                    border: 2px solid #0056b3;  
                    border-radius: 6px; padding: 10px; font-weight: bold;
                }
                QPushButton:hover { background-color: #0056b3; }
                QCheckBox { color: black; }
            """)

    def authenticate(self):
        """Handles authentication by checking username & hashed password."""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Login Failed", "Please enter both username and password.")
            return

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM admin WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()

        # ✅ Verify hashed password
        if result and result[0] == hashlib.sha256(password.encode()).hexdigest():
            self.open_admin_dashboard()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

    def open_admin_dashboard(self):
        """Opens the Admin Dashboard after successful login."""
        from ui.admin_dashboard import AdminDashboard
        self.admin_window = AdminDashboard()
        self.admin_window.show()
        self.close()
